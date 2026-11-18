"""The scoreboard's nightly job: the plan of a night, the waiter that asks the lane for a hold, the chain from hold to hold, and the timer.

It reuses what the nightly playtest already has instead of a scheduler of its own: the quiet-window and measuring locks (a hold is ONE waiter: the same
`setsid env --default-signal=HUP flock -w 43200 <quiet> flock -x -w 43200 <measuring> timeout ...` every worker's hold uses; the dispatcher gives it its priority
by the name in its folder), the player-wins rule (guard.py: two quiet minutes before a night, a game of the user's stops the hold), the private config and
results-store habits (config.json, results.sqlite, WAL, first valid sample counts), the transient `systemd-run --user --on-calendar` timer of `hs-nightly.py arm`
(off until the user's word) and the spending caps of the pilot (a night's own allowance below them). Nothing of the nightly's tools is edited.

A night is a plan (`nights/<night>/plan.json`: the cells x arms, in pair order so the arms of a cell run side by side) played by holds of at most hold_s
seconds; each hold plays what is still pending, scores it, and queues the next hold if cells remain (one waiter at a time, never while one is queued).
"""
import datetime
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import board  # noqa: E402
import config  # noqa: E402
import guard  # noqa: E402

WAITER_FILE = 'waiter.json'


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')


def git(repo, *args, check=True):
    r = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f'git {" ".join(args)} in {repo}: {r.stderr.strip()[:300]}')
    return r.stdout.strip()


def pilot_has(repo, text, rev='HEAD'):
    """Whether the pilot's committed pilot.py (at `rev`, default the head of the dev repo) contains `text` (an arm's `requires`: a flag it needs)."""
    r = subprocess.run(['git', '-C', str(repo), 'show', f'{rev}:pilot/pilot.py'], capture_output=True, text=True)
    return r.returncode == 0 and text in r.stdout


def selected_arms(cfg):
    """{name: arm} of the arms the config plays every night (the table's order); an unknown name is an error, not a silent skip."""
    every = board.arms()
    want = cfg.get('arms')
    if not want:
        return every
    bad = [a for a in want if a not in every]
    if bad:
        raise ValueError(f'config arms {bad} are not in the arms table ({list(every)})')
    return {a: every[a] for a in every if a in want}


def available_arms(cfg, arms=None, rev='HEAD'):
    """({name: arm}, {name: why not}) of the arms the committed pilot (at `rev`) can play."""
    arms = arms or selected_arms(cfg)
    ok, no = {}, {}
    for name, a in arms.items():
        need = a.get('requires')
        if need and not pilot_has(cfg['pilot_repo'], need, rev):
            no[name] = f'the pilot at {rev} has no {need!r}'
        else:
            ok[name] = a
    return ok, no


def spend_ok(cfg, arms_needing_model, now=None):
    """(ok, text): whether a night of model arms fits under the pilot's caps with the allowance (read from its caps.json and ledger.jsonl)."""
    pilot = Path(cfg['pilot_repo']) / 'pilot'
    try:
        caps = json.loads((pilot / 'caps.json').read_text())
        night_cap, total_cap = float(caps['per_night_usd']), float(caps['total_usd'])
    except (OSError, ValueError, KeyError):
        return False, 'no readable caps.json: the pilot asks no model without one'
    now = now or datetime.datetime.now()
    start = (now.replace(hour=1, minute=0, second=0, microsecond=0) if 1 <= now.hour < 8 else now.replace(hour=0, minute=0, second=0, microsecond=0)).timestamp()
    night = total = 0.0
    try:
        for line in (pilot / 'ledger.jsonl').read_text().splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            c = float(r.get('cost_usd') or 0)
            total += c
            if r.get('ts', 0) >= start:
                night += c
    except OSError:
        pass
    allow = float(cfg['allowance_usd'])
    if not arms_needing_model:
        return True, 'no model arm'
    if night + allow > night_cap:
        return False, f'a night has spent {night:.2f} USD of {night_cap:.0f}; the allowance {allow:.2f} does not fit'
    if total + allow > total_cap:
        return False, f'{total:.2f} USD spent in all of {total_cap:.0f}; the allowance does not fit'
    return True, f'{night:.2f} of {night_cap:.0f} USD spent tonight, {total:.2f} of {total_cap:.0f} in all; allowance {allow:.2f}'


def pair_items(cells, arm_names):
    """The night's items in pair order (the arms of one cell next to each other, so the lanes play them side by side)."""
    return [{'cell': c, 'arm': a} for c in cells for a in arm_names]


def make_plan(cfg, night, cell_list=None, arms=None, spend_note=None, tools_commit=None, pilot_commit=None, only_cells=None, proof=False):
    """The plan dict of a night over the cells that can be played and the arms the pilot can play. `skipped`: what was left out and why. `pilot_commit`: play
    this commit of the dev repo (a baseline night) instead of its head at admission."""
    cells = cell_list if cell_list is not None else board.load()
    if only_cells:
        unknown = sorted(set(only_cells) - {c.id for c in cells})
        if unknown:
            raise ValueError(f'unknown cells {unknown}')
        cells = [c for c in cells if c.id in only_cells]
    ready, skipped = [], {}
    for c in cells:
        why = board.missing(c)
        if why:
            skipped[c.id] = '; '.join(why)
        else:
            ready.append(c.id)
    ok, no = available_arms(cfg, arms, pilot_commit or 'HEAD')
    return {'night': night, 'created': now_iso(), 'cells': ready, 'arms': list(ok), 'items': pair_items(ready, list(ok)), 'skipped_cells': skipped, 'skipped_arms': no,
            'spend': spend_note, 'tools_commit': tools_commit, 'pilot_commit': pilot_commit, 'hold_s': cfg['hold_s'], 'proof': bool(proof)}


def freeze_tools(cfg, dest_root=None):
    """A copy of the committed playbench/ of tools_repo (git archive HEAD) under local/tools/<stamp>-<commit>: what a queued hold runs, whatever is committed
    meanwhile. Returns (folder holding playbench/, commit). The last 6 are kept."""
    repo = cfg['tools_repo']
    commit = git(repo, 'rev-parse', 'HEAD')
    root = Path(dest_root or cfg['tools_root'])
    root.mkdir(parents=True, exist_ok=True)
    dest = root / f'{time.strftime("%Y%m%d-%H%M%S")}-{commit[:9]}'
    dest.mkdir(parents=True, exist_ok=True)
    if not (dest / 'playbench').is_dir():   # (the same commit frozen twice in one second is the same copy)
        subprocess.run(f'git -C {repo} archive HEAD playbench | tar -x -C {dest}', shell=True, check=True)
    old = sorted(p for p in root.iterdir() if p.is_dir())[:-6]
    for p in old:
        shutil.rmtree(p, ignore_errors=True)
    return dest, commit[:9]


def waiter_command(cfg, tools_dir, night, hold):
    """The ONE waiter of a hold: the quiet-window lock, then the measuring lock exclusive, then `timeout` around the hold (the launcher makes the new session,
    as the others' `setsid` does; `setsid` here would fork and the recorded pid would be a dead parent). Its folder and its command line carry `PlayBench`
    (the dispatcher's priority key)."""
    return ['env', '--default-signal=HUP', f'PLAYBENCH_HARNESS={config.HARNESS}', f'PLAYBENCH_LOCAL={config.local_dir()}', 'flock', '-w', '43200', cfg['quiet_lock'], 'flock', '-x', '-w', '43200', cfg['measuring_lock'],
            'timeout', '--signal=TERM', '--kill-after=25', str(int(cfg['hold_s'])), cfg['python'], '-I', '-B', str(Path(tools_dir) / 'playbench' / 'playbench.py'),
            'hold', '--night', night, '--hold', str(hold), '--tools', str(tools_dir)]


def live_waiter(nd):
    """The pid of this night's queued waiter if it is still alive (a stopped flock waiter counts), else None."""
    f = Path(nd) / WAITER_FILE
    try:
        pid = json.loads(f.read_text())['pid']
    except (OSError, ValueError, KeyError):
        return None
    try:
        state = next((ln.split(':', 1)[1].strip() for ln in Path(f'/proc/{pid}/status').read_text().splitlines() if ln.startswith('State:')), 'Z')
    except OSError:
        return None
    return None if 'Z' in state or 'X' in state else pid


def queue_hold(cfg, night, hold, tools_dir, popen=subprocess.Popen, replacing=None):
    """Start the waiter for hold `hold` of `night` (refused while this night's previous waiter is alive: one waiter at a time; `replacing`: the pid of the
    previous waiter that IS the running hold queueing its successor). Returns the waiter's pid.
    The child closes every inherited descriptor: a hold that queues its successor still holds the lock, and a descriptor leaked into the successor would
    make it wait for a lock it holds itself."""
    nd = config.night_dir(cfg, night)
    nd.mkdir(parents=True, exist_ok=True)
    alive = live_waiter(nd)
    if alive and alive != replacing:
        raise RuntimeError(f'night {night}: the waiter {alive} is still alive: one waiter at a time')
    cmd = waiter_command(cfg, tools_dir, night, hold)
    log = open(nd / f'hold-{hold}.launcher.log', 'w')
    env = {k: v for k, v in os.environ.items() if not k.startswith('HSGATE_')}
    env['PILOT_OPENAI_KEY_FILE'] = cfg['key_file']
    p = popen(cmd, cwd=cfg['reports'], env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, close_fds=True, start_new_session=True)
    (nd / WAITER_FILE).write_text(json.dumps({'pid': p.pid, 'hold': hold, 'asked': now_iso(), 'command': cmd}, indent=1))
    return p.pid


def hold_started(night, hold, proc=Path('/proc')):
    """Whether python of this night's hold has started (the waiter is no longer only waiting for its locks)."""
    want = [b'playbench.py', b'hold', night.encode(), str(hold).encode()]
    try:
        entries = list(proc.iterdir())
    except OSError:
        return False
    for d in entries:
        if not d.name.isdigit():
            continue
        try:
            argv = (d / 'cmdline').read_bytes().split(b'\0')
        except OSError:
            continue
        if argv and argv[0].endswith((b'python3', b'python')) and all(any(w in a for a in argv) for w in want):
            return True
    return False


def refreeze(cfg, night):
    """Put the tools' current committed head into the folder a QUEUED waiter will run (its `--tools` path), so a fix made while the hold waits in the queue is the one
    that plays: the new copy is made beside it and swapped in with two renames. Refused once the hold's python has started. Updates the night's plan with the commit."""
    nd = config.night_dir(cfg, night)
    info = json.loads((nd / WAITER_FILE).read_text())
    if live_waiter(nd) is None:
        raise RuntimeError(f'night {night}: no waiter is alive')
    if hold_started(night, info['hold']):
        raise RuntimeError(f'night {night}: hold {info["hold"]} has started: its tools are in use')
    old = Path(info['command'][info['command'].index('--tools') + 1])
    new, commit = freeze_tools(cfg)
    prev = old.with_name(old.name + '.prev')
    shutil.rmtree(prev, ignore_errors=True)
    os.rename(old, prev)
    os.rename(new, old)
    shutil.rmtree(prev, ignore_errors=True)
    pf = nd / 'plan.json'
    plan = json.loads(pf.read_text())
    plan['tools_commit'] = commit
    pf.write_text(json.dumps(plan, indent=1))
    return old, commit


def pending_items(plan, counted, attempts_by_key, max_attempts):
    """The items still to play: those with no valid result, and fewer attempts than allowed. Each carries its next attempt number."""
    out = []
    for it in plan['items']:
        k = (it['cell'], it['arm'])
        row = counted.get(k)
        if row is not None and row['valid']:
            continue
        n = attempts_by_key.get(k, 0)
        if n < max_attempts:
            out.append({**it, 'attempt': n + 1})
    return out


def arm_timer(cfg, at=None):
    """Arm the next night's transient user timer, as hs-nightly.py's `arm` does (no unit file is written). Needs timer_enabled in the private config."""
    if not cfg.get('timer_enabled'):
        raise RuntimeError('the timer is disabled: enabling it (timer_enabled in playbench-local/config.json) needs the user\'s explicit word')
    cal = at or subprocess.check_output(['date', '-d', 'tomorrow ' + cfg['timer_time'], '+%Y-%m-%d %H:%M:%S'], text=True).strip()
    unit = 'playbench-nightly-' + cal.replace(' ', '-').replace(':', '')
    argv = ['systemd-run', '--user', '--unit=' + unit, '--on-calendar=' + cal, '--timer-property=AccuracySec=60s', '--collect', cfg['python'], '-I', '-B',
            str(Path(cfg['tools_repo']) / 'playbench' / 'playbench.py'), 'nightly', '--rearm']
    r = subprocess.run(argv, capture_output=True, text=True)
    info = {'at': now_iso(), 'calendar': cal, 'unit': unit, 'command': argv, 'result': (r.stdout + r.stderr).strip(), 'rc': r.returncode}
    (config.LOCAL / 'timer.json').write_text(json.dumps(info, indent=1))
    if r.returncode:
        raise RuntimeError(f'systemd-run failed: {info["result"]}')
    return info


def start_night(cfg, night=None, *, wait_idle=True, popen=subprocess.Popen, probe=None, rearm=False, pilot_commit=None, only_cells=None, only_arms=None, proof=False, killer=os.kill):
    """What the timer runs: wait for two quiet player minutes, write the night's plan, freeze the tools and queue hold 1. Returns the plan (or {'skipped': why})."""
    night = night or datetime.date.today().strftime('%Y%m%d')
    nd = config.night_dir(cfg, night)
    if (nd / 'plan.json').is_file():
        return {'skipped': f'night {night} already has a plan (resume it with `hold`)'}
    for other in sorted((nd.parent).glob('*')) if nd.parent.is_dir() else []:
        pid = live_waiter(other)
        if other.name != night and pid:   # (one waiter at a time: an earlier night still waiting for the lane is not joined by a second)
            try:
                other_proof = bool(json.loads((other / 'plan.json').read_text()).get('proof'))
            except (OSError, ValueError):
                other_proof = False
            if other_proof and not proof:   # a proving run waiting for the lane gives way to a real night: its waiter is withdrawn (by pid: TERM, then CONT so a stopped flock gets it)
                killer(pid, signal.SIGTERM)
                killer(pid, signal.SIGCONT)
                (other / 'withdrawn.txt').write_text(f'withdrawn {now_iso()} for night {night}\n')
                continue
            return {'skipped': f'night {other.name} still has a waiter ({pid}) queued: one waiter at a time, no night {night}'}
    if wait_idle and not guard.wait_idle(cfg['idle_s'], cfg['idle_timeout_s'], **({'probe': probe} if probe else {})):
        return {'skipped': 'the user is playing: the player wins, no night tonight'}
    arms = selected_arms(cfg)
    if only_arms:
        unknown = sorted(set(only_arms) - set(arms) - set(board.arms()))
        if unknown:
            raise ValueError(f'unknown arms {unknown}')
        arms = {a: board.arms()[a] for a in only_arms}
    model = [a for a, d in arms.items() if d.get('planner') or d['decider'] != 'rules']
    ok, note = spend_ok(cfg, model)
    if not ok:
        arms = {a: d for a, d in arms.items() if a not in model}
        note = 'model arms dropped: ' + note
    tools_dir, tools_commit = freeze_tools(cfg)
    plan = make_plan(cfg, night, arms=arms, spend_note=note, tools_commit=tools_commit, pilot_commit=pilot_commit, only_cells=only_cells, proof=proof)
    nd.mkdir(parents=True, exist_ok=True)
    (nd / 'plan.json').write_text(json.dumps(plan, indent=1))
    if not plan['items']:
        return {'skipped': 'nothing to play', 'plan': plan}
    pid = queue_hold(cfg, night, 1, tools_dir, popen=popen)
    plan['waiter_pid'] = pid
    return plan
