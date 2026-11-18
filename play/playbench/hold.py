"""One hold of a night, run inside the waiter's locks: take the pilot's committed head as a snapshot, play what is pending, score it, store it, draw the trend,
and queue the next hold when cells remain.

Order (so a short hold still leaves a result): snapshot -> smoke -> lanes checked -> cells played (runner.py) -> every finished cell scored and stored ->
evidence copied out of the snapshot -> the cost ledger merged into the dev copy's (the caps see it) -> the kernel's driver lines counted -> trend + chart ->
snapshot removed -> the next hold queued. A hold killed before it scored leaves its cell records and its snapshot; the next hold scores them first.
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import board  # noqa: E402
import config  # noqa: E402
import guard  # noqa: E402,F401  (puts the folder with hs_names.py on sys.path)
import nightly  # noqa: E402
import runner  # noqa: E402
import score  # noqa: E402
import store  # noqa: E402
import trend  # noqa: E402
import hs_names  # noqa: E402

SMOKE = (('pilot/pilot.py', 'run', '-h'), ('hsap.py', '-h'), ('pilot/test_metrics.py',))


def make_snapshot(repo, commit, dest):
    """The committed tree at `commit` in `dest` (beside hs_names.py: hsap finds it from its own place), with the dev copy's current ledger and caps laid over it
    (the caps count what has been spent; both files change without a commit)."""
    dest = Path(dest)
    if dest.exists():
        raise RuntimeError(f'{dest} exists')
    dest.mkdir(parents=True)
    subprocess.run(f'git -C {repo} archive {commit} | tar -x -C {dest}', shell=True, check=True)
    for name in ('ledger.jsonl', 'caps.json'):
        src = Path(repo) / 'pilot' / name
        if src.is_file():
            shutil.copy(src, dest / 'pilot' / name)
    (dest / 'pilot' / 'runs').mkdir(exist_ok=True)
    return dest


def smoke(snap, python):
    """The entry points start under -I and the pilot's own metrics test passes: a head that does not is not played. Returns '' or what failed."""
    for argv in SMOKE:
        r = subprocess.run([python, '-I', '-B', *argv], cwd=str(snap), capture_output=True, text=True, timeout=300)
        if r.returncode:
            return f'{" ".join(argv)}: exit {r.returncode}: {(r.stderr or r.stdout).strip()[-300:]}'
        if argv[:3] == ('pilot/pilot.py', 'run', '-h'):   # (a pilot that has lost an option the runner passes would fail every cell at its first second)
            lost = [f for f in runner.PILOT_FLAGS if f not in r.stdout]
            if lost:
                return f'pilot.py run -h lacks {lost}'
    return ''


def check_copies(copies):
    """(usable, problems): a lane needs a game copy that exists, is warm (cache/), has its executable and renderer, matches the first copy's build, and is not in use."""
    usable, problems, ref = [], {}, None
    busy = set()
    for p in Path('/proc').iterdir():
        if p.name.isdigit():
            for link in ('cwd', 'exe'):
                try:
                    busy.add(os.readlink(p / link))
                except OSError:
                    pass
    for c in copies:
        c = Path(c)
        if not c.is_dir():
            problems[str(c)] = 'missing'
            continue
        if not (c / 'cache').is_dir():
            problems[str(c)] = 'not warm (no cache/): its first start would compile every shader'
            continue
        try:
            names = hs_names.copy_names(c)
        except hs_names.NameError as e:
            problems[str(c)] = f'not a game copy: {e}'
            continue
        stamp = tuple((c / n).stat().st_size if (c / n).exists() else None for n in (names.executable, names.renderer)) + ((c / 'built-from.txt').read_text().strip()[:12] if (c / 'built-from.txt').exists() else '',)
        if None in stamp[:2]:
            problems[str(c)] = 'no executable or renderer'
            continue
        if ref is None:
            ref = stamp
        elif stamp != ref:
            problems[str(c)] = f'a different build from the first copy ({stamp} against {ref})'
            continue
        if any(b == str(c) or b.startswith(str(c) + '/') for b in busy):
            problems[str(c)] = 'a process is running in it'
            continue
        usable.append(str(c))
    return usable, problems


def kernel_lines(since_epoch):
    """The count of the kernel's driver lines (Xid, kmemsysDoCacheOp) since a time, or 'unknown' when the journal could not be read."""
    since = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(since_epoch))
    r = subprocess.run(['journalctl', '-k', '--since', since, '--no-pager'], capture_output=True, text=True)
    if r.returncode:
        return 'unknown'
    return sum(1 for ln in r.stdout.splitlines() if 'kmemsysDoCacheOp' in ln or 'NVRM: Xid' in ln)


def score_hold(hold_dir, night, cfg, st, cells_by_id, arms, pilot_dir, pilot_commit, local=None):
    """Score every cell record of a hold that has no stored result yet, store it and copy its evidence out; returns the rows added."""
    hold_dir, nd = Path(hold_dir), config.night_dir(cfg, night)
    try:
        mod = score.load_metrics(pilot_dir)
    except Exception as e:   # noqa: BLE001  scoring goes on without the pilot's numbers rather than not at all
        print(f'metrics.py of {pilot_dir} did not load ({type(e).__name__}: {e}): stuck/decisions/cost stay empty', flush=True)
        mod = None
    have = {(r['cell'], r['arm'], r['attempt']) for r in st.attempts(night)}
    added = []
    for f in sorted((hold_dir / 'cells').glob('*.json')):
        try:
            rec = json.loads(f.read_text())
        except ValueError:
            continue
        if 'tag' not in rec or (rec['cell'], rec['arm'], rec['attempt']) in have:
            continue
        cell, arm = cells_by_id[rec['cell']], arms[rec['arm']]
        row = score.score_cell(rec, cell, rec['arm'], arm, night, pilot_commit, mod, local)
        try:
            row['evidence'] = str(score.collect(rec, nd / 'runs' / rec['tag']))
            shutil.rmtree(Path(rec['copy']) / 'runs' / rec['tag'], ignore_errors=True)   # (the game's own run folder: its pictures are 1.5 MB each; the evidence is kept)
        except Exception as e:   # noqa: BLE001
            row['evidence'] = f'not collected: {e}'
        st.add_cell(row)
        added.append(row)
        print(f"scored {rec['tag']}: {'MET' if row['success'] else 'not met'} valid {row['valid']} ttg {row['time_to_goal_s']} stuck {row['stuck_s']} "
              f"decisions {row['decisions']} cost {row['cost_usd']} {row['why'][:80]}", flush=True)
    return added


def weekly_draft(cfg, st, night, force=False):
    """On the first night of the week (a Monday), or when forced: write the weekly draft for issue 1198 and its chart picture into the drafts folder (dated files;
    nothing is posted: Main reads and posts). Returns the draft's path or None."""
    import datetime
    import draft
    if not force and datetime.datetime.strptime(night, '%Y%m%d').weekday() != 0:
        return None
    history = st.all_counted()
    cells = [c.id for c in board.load()]
    arms = trend.arms_in(history, list(board.arms()))
    out = Path(cfg['drafts'])
    out.mkdir(parents=True, exist_ok=True)
    pic = f'pilot-1198-scoreboard-{night}.png'
    chart = Path(cfg['reports']) / 'trend' / 'chart.png'
    if chart.is_file():
        shutil.copy(chart, out / pic)
    path = out / f'pilot-1198-scoreboard-weekly-{night}.md'
    path.write_text(draft.weekly(history, cells, arms, {c.id: c.title for c in board.PUBLIC}, chart_name=pic, issue_url=cfg['issue_url']))
    return path


def export_trend(cfg, st, cells, arm_order):
    history = st.all_counted()
    arms = trend.arms_in(history, arm_order)
    return trend.write_all(history, cells, arms, Path(cfg['reports']) / 'trend')


def run_hold(night, hold, cfg, tools_dir, *, pilot_cmd=None, env=None, chain=True, python=None, db=None, queue_popen=subprocess.Popen):
    """The whole hold. Returns the exit code (0 played and scored; 3 the head failed its smoke checks; 4 no usable lane; 5 no plan)."""
    t0 = time.time()
    nd = config.night_dir(cfg, night)
    try:
        plan = json.loads((nd / 'plan.json').read_text())
    except (OSError, ValueError):
        print(f'no plan for night {night} in {nd}', flush=True)
        return 5
    python = python or cfg['python']
    st = store.Store(db or config.results_db())
    st.begin_night(night, nightly.now_iso(), plan)
    all_cells = board.load()
    cells_by_id = {c.id: c for c in all_cells}
    arms = board.arms()
    hold_dir = nd / 'holds' / str(hold)
    hold_dir.mkdir(parents=True, exist_ok=True)
    repo = cfg['pilot_repo']
    commit = nightly.git(repo, 'rev-parse', plan.get('pilot_commit') or 'HEAD')   # (a baseline night pins a commit; every other night plays the head)
    short = commit[:9]
    # leftovers of an earlier hold of this night that died before it scored
    for prev in sorted((nd / 'holds').iterdir()):
        info = prev / 'identity.json'
        if prev.name != str(hold) and info.is_file() and (prev / 'cells').is_dir():
            idn = json.loads(info.read_text())
            if Path(idn['pilot_dir']).is_dir():
                score_hold(prev, night, cfg, st, cells_by_id, arms, idn['pilot_dir'], idn['pilot_commit'])
    counted = st.counted(night)
    attempts = {}
    for r in st.attempts(night):
        attempts[(r['cell'], r['arm'])] = max(attempts.get((r['cell'], r['arm']), 0), r['attempt'])
    pending = nightly.pending_items(plan, counted, attempts, cfg['max_attempts'])
    if not pending:
        print('nothing pending: the night is complete', flush=True)
        st.end_night(night, 'complete', nightly.now_iso(), hold - 1)
        export_trend(cfg, st, [c.id for c in all_cells], list(arms))
        return 0
    usable, problems = check_copies(cfg['copies'])
    if not usable:
        print(f'no usable game copy: {problems}', flush=True)
        (hold_dir / 'abort.json').write_text(json.dumps({'why': 'no usable game copy', 'problems': problems}, indent=1))
        return 4
    snap = Path(config.HARNESS) / f'playthrough-playbench-{night}-h{hold}'
    pilot_dir = snap / 'pilot'
    fallback = None
    make_snapshot(repo, commit, snap)
    bad = smoke(snap, python)
    if bad:
        good = st.db.execute("SELECT pilot_commit FROM nights WHERE pilot_commit IS NOT NULL AND night<? ORDER BY night DESC LIMIT 1", (night,)).fetchone()
        print(f'the pilot head {short} failed its smoke checks: {bad}', flush=True)
        shutil.rmtree(snap, ignore_errors=True)
        if not good:
            (hold_dir / 'abort.json').write_text(json.dumps({'why': 'smoke failed, no earlier commit', 'smoke': bad}, indent=1))
            return 3
        fallback = good[0]
        full = nightly.git(repo, 'rev-parse', fallback)
        make_snapshot(repo, full, snap)
        bad2 = smoke(snap, python)
        if bad2:
            shutil.rmtree(snap, ignore_errors=True)
            (hold_dir / 'abort.json').write_text(json.dumps({'why': 'smoke failed at the head and at the last good commit', 'smoke': [bad, bad2]}, indent=1))
            return 3
        short = fallback
    st.night_identity(night, pilot_commit=short, tools_commit=plan.get('tools_commit'))
    (hold_dir / 'identity.json').write_text(json.dumps({'pilot_commit': short, 'pilot_dir': str(pilot_dir), 'fallback_from': commit[:9] if fallback else None,
                                                      'copies': usable, 'copy_problems': problems, 'tools': str(tools_dir), 'game_env': cfg.get('game_env') or {}}, indent=1))
    hold_plan = {'night': night, 'hold': hold, 'out': str(hold_dir), 'pilot_dir': str(pilot_dir), 'python': python, 'copies': usable, 'local': str(config.LOCAL),
                 'items': pending, 'hold_s': cfg['hold_s'] - (time.time() - t0), 'reserve_s': cfg['reserve_s'], 'shots': cfg['shots'],
                 'allowance_usd': cfg['allowance_usd'] if any(arms[a].get('planner') or arms[a]['decider'] != 'rules' for a in plan['arms']) else None,
                 'allowance_since': nightly.now_iso(), 'env': {'PILOT_OPENAI_KEY_FILE': cfg['key_file'], **{str(k): str(v) for k, v in (cfg.get('game_env') or {}).items()}, **(env or {})}, 'pilot_cmd': pilot_cmd}
    (hold_dir / 'plan.json').write_text(json.dumps(hold_plan, indent=1))
    h = runner.Hold(hold_plan)
    summary = h.play()
    rows = score_hold(hold_dir, night, cfg, st, cells_by_id, arms, pilot_dir, short)
    builds = [r['build'] for r in rows if r['build'] != 'unknown']
    if builds:
        st.night_identity(night, build=builds[0])
    merged = score.merge_ledger(pilot_dir, Path(repo) / 'pilot')
    klines = kernel_lines(t0)
    summary.update({'scored': len(rows), 'ledger_rows_merged': merged, 'kernel_driver_lines': klines, 'pilot_commit': short, 'fallback_from': commit[:9] if fallback else None,
                    'copies': usable, 'copy_problems': problems, 'seconds_total': round(time.time() - t0, 1)})
    (hold_dir / 'hold.json').write_text(json.dumps(summary, indent=1))
    export_trend(cfg, st, [c.id for c in all_cells], list(arms))
    shutil.rmtree(snap, ignore_errors=True)
    counted = st.counted(night)
    attempts = {}
    for r in st.attempts(night):
        attempts[(r['cell'], r['arm'])] = max(attempts.get((r['cell'], r['arm']), 0), r['attempt'])
    left = nightly.pending_items(plan, counted, attempts, cfg['max_attempts'])
    if summary['stopping'] == 'player':
        st.end_night(night, 'cut: the player\'s game appeared', nightly.now_iso(), hold)
    elif summary['stopping'] == 'no-play':
        st.end_night(night, 'aborted: the first runs never reached play (the game, a save or the lane is broken); not chained', nightly.now_iso(), hold)
    elif not left:
        st.end_night(night, 'complete', nightly.now_iso(), hold)
    elif hold >= cfg['max_holds_per_night'] or not chain:
        st.end_night(night, f'partial: {len(left)} of {len(plan["items"])} items not played', nightly.now_iso(), hold)
    else:
        try:
            replaced = json.loads((nd / nightly.WAITER_FILE).read_text()).get('pid')
        except (OSError, ValueError):
            replaced = None
        pid = nightly.queue_hold(cfg, night, hold + 1, tools_dir, popen=queue_popen, replacing=replaced)
        print(f'{len(left)} items left: hold {hold + 1} queued (waiter {pid})', flush=True)
    if not plan.get('proof') and (not [r for r in nightly.pending_items(plan, st.counted(night), attempts, cfg['max_attempts'])] or hold >= cfg['max_holds_per_night']):
        d = weekly_draft(cfg, st, night)
        if d:
            print(f'weekly draft written: {d}', flush=True)
    st.close()
    print(json.dumps({k: summary[k] for k in ('scored', 'stopping', 'kernel_driver_lines', 'seconds_total')}), flush=True)
    return 0
