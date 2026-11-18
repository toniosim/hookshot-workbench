#!/usr/bin/env python3
"""The pilot's capability scoreboard: a fixed set of cells (a save-placed start and a goal the game's state proves), played every night by the rules player and the
model arms, scored by a referee that reads the game's state, stored, and drawn as a trend.

  playbench.py check                      the board, the frozen files, the arms and the committed pilot, game-free (what a night would play)
  playbench.py plan [--night ID]          print the night's plan (nothing is written, nothing queued)
  playbench.py queue [--night ID] [--pilot-commit C] [--cells a,b] [--arms x,y] [--proof]   a manual night: write the plan, freeze the tools, queue hold 1 (ONE waiter) and stop
  playbench.py nightly [--rearm]          what the timer runs: wait for the player to be away, then as `queue`; --rearm arms the next night
  playbench.py hold --night ID --hold K --tools DIR     inside the waiter's locks: play, score, store, trend, queue the next hold
  playbench.py score --night ID --hold K  score the cell records of a hold that died before it scored (needs its snapshot)
  playbench.py trend                      the tables and chart from the store (reports/PlayBench-files/trend/)
  playbench.py draft [--out FILE]         the weekly draft for issue 1198 from the trend (nothing is posted)
  playbench.py status                     nights, the queued waiter, the last hold
  playbench.py copies --from COPY         make the lane copies by reflink from a warm game copy (and check they match)
  playbench.py rejudge --night ID --cells a,b --reason TEXT   judge stored runs again by the cells' current proofs (the old judgement is kept)
  playbench.py annotate --night ID --cells a,b --blocker TEXT   mark stored failed results as blocked by a known cause outside the pilot
  playbench.py refreeze --night ID        put the tools' committed head into the folder a QUEUED waiter will run (refused once its hold has started)
  playbench.py arm --user-authorized      arm tomorrow's night (the transient user timer); needs timer_enabled in playbench-local/config.json

Settings: playbench-local/config.json (defaults in config.py). The cells' places are private (board-local.json, segments/, saves/ in the same folder).
Every game run is windowless and goes through the shared lane (the waiter's quiet-window and measuring locks) and the card's gate (hs-run.sh, from hsap).
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import board  # noqa: E402
import config  # noqa: E402
import draft  # noqa: E402
import hold  # noqa: E402
import nightly  # noqa: E402
import score  # noqa: E402
import store  # noqa: E402
import trend  # noqa: E402

CHECK_CODE = r'''
import json, sys
pilot_dir, files = sys.argv[1], sys.argv[2:]
sys.path.insert(0, pilot_dir)
import pilot, sections
out = {}
for f in files:
    try:
        ch = sections.load_if_chapter(f) if f.endswith('.toml') else None
        seg = sections.segment_for(ch) if ch else pilot.Segment(f)
        out[f] = {'ok': True, 'chapter': bool(ch), 'goals': [(g.name, g.kind, g.cond.name) for g in seg.goals], 'watch': list(seg.watch), 'wall': seg.wall, 'save': seg.save}
    except Exception as e:
        out[f] = {'ok': False, 'error': f'{type(e).__name__}: {e}'}
print(json.dumps(out))
'''


def cmd_check(a, cfg):
    cells = board.load()
    arms = nightly.selected_arms(cfg)
    ok = True
    print(f'local folder {config.LOCAL}; pilot repo {cfg["pilot_repo"]} at {nightly.git(cfg["pilot_repo"], "rev-parse", "--short", "HEAD")}')
    avail, no = nightly.available_arms(cfg, arms)
    print('arms available:', ', '.join(avail), '| unavailable:', no or 'none')
    files = []
    total_wall = 0
    for c in cells:
        why = board.missing(c)
        total_wall += c.wall_s
        print(f'  {c.id:13s} {c.kind:7s} wall {c.wall_s:4d} s  {"MISSING: " + "; ".join(why) if why else "ready"}')
        if why:
            ok = False
            continue
        seg = config.LOCAL / 'segments' / c.segment
        files.append(str(seg))
        if c.kind == 'segment':
            text = seg.read_text()
            lost = [f for f in board.proof_flags(c.proof) if f not in text]
            if lost:
                print(f'    FAIL the segment does not watch {lost}: the state journal would not carry them')
                ok = False
    if files:
        pilot_dir = Path(cfg['pilot_repo']) / 'pilot'
        r = subprocess.run([cfg['python'], '-I', '-B', '-c', CHECK_CODE, str(pilot_dir), *files], capture_output=True, text=True, cwd=str(pilot_dir))
        try:
            res = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            print('FAIL the pilot could not load the segments:', (r.stderr or r.stdout)[-400:])
            return 1
        for f, v in res.items():
            if not v['ok']:
                print(f'    FAIL {Path(f).name}: {v["error"]}')
                ok = False
    n = len(avail)
    print(f'one night: {len(files)} cells x {n} arms = {len(files) * n} runs; worst case {total_wall * n} s of cell wall over {len(cfg["copies"])} lane(s): '
          f'{round(total_wall * n / max(1, len(cfg["copies"])) / (cfg["hold_s"] - cfg["reserve_s"]), 1)} hold(s) of {cfg["hold_s"]} s')
    return 0 if ok else 1


def cmd_plan(a, cfg):
    night = a.night or __import__('datetime').date.today().strftime('%Y%m%d')
    arms = nightly.selected_arms(cfg)
    model = [x for x, d in arms.items() if d.get('planner') or d['decider'] != 'rules']
    ok, note = nightly.spend_ok(cfg, model)
    plan = nightly.make_plan(cfg, night, arms=arms if ok else {k: v for k, v in arms.items() if k not in model}, spend_note=note)
    print(json.dumps(plan, indent=1))
    return 0


def cmd_queue(a, cfg):
    plan = nightly.start_night(cfg, a.night, wait_idle=not a.no_wait_idle, pilot_commit=a.pilot_commit, only_cells=a.cells.split(',') if a.cells else None,
                               only_arms=a.arms.split(',') if a.arms else None, proof=a.proof)
    print(json.dumps({k: plan.get(k) for k in ('night', 'skipped', 'waiter_pid', 'cells', 'arms', 'skipped_cells', 'skipped_arms', 'spend', 'tools_commit', 'pilot_commit')}, indent=1))
    return 1 if 'skipped' in plan else 0


def cmd_nightly(a, cfg):
    plan = nightly.start_night(cfg, a.night, wait_idle=True)
    print(json.dumps({k: plan.get(k) for k in ('night', 'skipped', 'waiter_pid', 'spend')}), flush=True)
    if a.rearm and cfg.get('timer_enabled'):
        info = nightly.arm_timer(cfg)
        print('rearmed', info['calendar'], flush=True)
    return 0


def cmd_hold(a, cfg):
    return hold.run_hold(a.night, a.hold, cfg, a.tools, chain=not a.no_chain)


def cmd_score(a, cfg):
    nd = config.night_dir(cfg, a.night)
    hd = nd / 'holds' / str(a.hold)
    idn = json.loads((hd / 'identity.json').read_text())
    st = store.Store(config.results_db())
    cells = {c.id: c for c in board.load()}
    rows = hold.score_hold(hd, a.night, cfg, st, cells, board.arms(), idn['pilot_dir'], idn['pilot_commit'])
    print(f'{len(rows)} cells scored')
    return 0


def cmd_trend(a, cfg):
    st = store.Store(config.results_db())
    files = hold.export_trend(cfg, st, [c.id for c in board.load()], list(board.arms()))
    for k, v in files.items():
        print(k, v)
    return 0


def cmd_draft(a, cfg):
    st = store.Store(config.results_db())
    history = st.all_counted()
    cells = [c.id for c in board.load()]
    arms = trend.arms_in(history, list(board.arms()))
    titles = {c.id: c.title for c in board.PUBLIC}
    chart = Path(cfg['reports']) / 'trend' / 'chart.png'
    if chart.is_file() and not a.out:
        __import__('shutil').copy(chart, Path(cfg['drafts']) / a.chart_name)
    text = draft.weekly(history, cells, arms, titles, chart_name=a.chart_name, issue_url=cfg['issue_url'])
    out = Path(a.out or Path(cfg['drafts']) / 'pilot-1198-scoreboard-weekly.md')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    print(out)
    return 0


def cmd_status(a, cfg):
    st = store.Store(config.results_db())
    for n in st.nights(a.last):
        c = st.counted(n['night'])
        solved = {}
        for (cell, arm), r in c.items():
            s = solved.setdefault(arm, [0, 0, 0])
            s[1] += 1 if r['valid'] else 0
            s[0] += 1 if r['valid'] and r['success'] else 0
            s[2] += 0 if r['valid'] else 1
        print(f"{n['night']} {n['status']:28s} pilot {n['pilot_commit']} build {n['build']} holds {n['holds']} " + ' '.join(f'{k}: {v[0]}/{v[1]} (+{v[2]} invalid)' for k, v in sorted(solved.items())))
    root = Path(cfg['reports']) / 'nights'
    for nd in sorted(root.glob('*')) if root.is_dir() else []:
        pid = nightly.live_waiter(nd)
        if pid:
            print(f'night {nd.name}: waiter {pid} alive ({(nd / nightly.WAITER_FILE).read_text()[:120].strip()})')
    return 0


def cmd_copies(a, cfg):
    src = Path(a.src)
    for c in cfg['copies']:
        dst = Path(c)
        if dst.exists():
            print(f'{dst}: exists, left alone')
            continue
        subprocess.run(['cp', '-a', '--reflink=always', str(src), str(dst)], check=True)
        for p in (dst / 'runs').glob('*'):
            subprocess.run(['rm', '-rf', str(p)], check=True)
        print(f'{dst}: cloned from {src}')
    usable, problems = hold.check_copies(cfg['copies'])
    print('usable:', usable, 'problems:', problems or 'none')
    return 0 if len(usable) == len(cfg['copies']) else 1


def cmd_rejudge(a, cfg):
    """Judge stored runs again by the cells' current proofs, on the evidence kept for them (a proof that was wrong, not a sample that was): the old judgement is kept in
    the store's `rejudged` table with the reason."""
    import gzip
    st = store.Store(config.results_db())
    cells = {c.id: c for c in board.load()}
    nd = config.night_dir(cfg, a.night)
    n = 0
    for old in st.attempts(a.night):
        if old['cell'] not in a.cells.split(','):
            continue
        ev = nd / 'runs' / old['tag']
        try:
            rows = [json.loads(x) for x in gzip.open(ev / 'state.jsonl.gz', 'rt')]
        except OSError:
            print(f"{old['tag']}: no kept journal, left alone")
            continue
        earlier = [r for r in st.rejudgements(a.night) if (r['cell'], r['arm'], r['attempt']) == (old['cell'], old['arm'], old['attempt'])]
        was_met = bool(old['success']) or any(json.loads(r['old_json'])['success'] for r in earlier)
        new = score.rejudge_row(json.loads(old['row_json']), cells[old['cell']], rows, ev / 'transcript.jsonl', ended_by_old_proof=was_met)
        st.rejudge(a.night, old['cell'], old['arm'], old['attempt'], new, a.reason, nightly.now_iso())
        print(f"{old['tag']}: success {old['success']} -> {new['success']}, time {old['time_to_goal_s']} -> {new['time_to_goal_s']}, progress {old['progress']} -> {new['progress']}")
        n += 1
    print(f'{n} result(s) rejudged')
    return 0


def cmd_annotate(a, cfg):
    """Mark the stored failed results of cells on a night as blocked by a known cause (the cell's own `blocker` in board-local.json does the same for later nights)."""
    st = store.Store(config.results_db())
    for cell in a.cells.split(','):
        print(f'{cell}: {st.annotate_blocker(a.night, cell, a.blocker)} failed result(s) marked blocked')
    return 0


def cmd_refreeze(a, cfg):
    old, commit = nightly.refreeze(cfg, a.night)
    print(f'tools {commit} are in {old}')
    return 0


def cmd_arm(a, cfg):
    info = nightly.arm_timer(cfg)
    print(json.dumps(info, indent=1))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('check')
    p = sub.add_parser('plan')
    p.add_argument('--night')
    p = sub.add_parser('queue')
    p.add_argument('--night')
    p.add_argument('--no-wait-idle', action='store_true', help='do not wait for two quiet player minutes first (a manual night the user knows about)')
    p.add_argument('--pilot-commit', help='play this commit of the dev repo (a baseline night) instead of its head at admission')
    p.add_argument('--cells', help='only these cells (comma-separated ids)')
    p.add_argument('--arms', help='only these arms (comma-separated names)')
    p.add_argument('--proof', action='store_true', help='a PROVING run (a few cells before a night to see that a fix works): not a night of the trend, its queued waiter gives way to a real night; name it with --night, e.g. 20261117-proof')
    p = sub.add_parser('nightly')
    p.add_argument('--night')
    p.add_argument('--rearm', action='store_true')
    p = sub.add_parser('hold')
    p.add_argument('--night', required=True)
    p.add_argument('--hold', type=int, required=True)
    p.add_argument('--tools', required=True)
    p.add_argument('--no-chain', action='store_true')
    p = sub.add_parser('score')
    p.add_argument('--night', required=True)
    p.add_argument('--hold', type=int, required=True)
    sub.add_parser('trend')
    p = sub.add_parser('draft')
    p.add_argument('--out')
    p.add_argument('--chart-name', default='pilot-1198-scoreboard.png')
    p = sub.add_parser('status')
    p.add_argument('--last', type=int, default=10)
    p = sub.add_parser('copies')
    p.add_argument('--from', dest='src', required=True)
    p = sub.add_parser('rejudge')
    p.add_argument('--night', required=True)
    p.add_argument('--cells', required=True, help='comma-separated cell ids')
    p.add_argument('--reason', required=True)
    p = sub.add_parser('annotate')
    p.add_argument('--night', required=True)
    p.add_argument('--cells', required=True)
    p.add_argument('--blocker', required=True)
    p = sub.add_parser('refreeze')
    p.add_argument('--night', required=True)
    p = sub.add_parser('arm')
    p.add_argument('--user-authorized', action='store_true', required=True, help="the user explicitly asked for the nightly timer")
    a = ap.parse_args(argv)
    for k in ('HSGATE_SLOT_DIR', 'HSGATE_INTEL_SLOT_DIR', 'HSGATE_SLOT_TEST', 'HSGATE_SLOT_NODESKTOP', 'HSGATE_IN_GATE', 'HSGATE_IN_INTEL_GATE'):
        os.environ.pop(k, None)
    cfg = config.load()
    return {'check': cmd_check, 'plan': cmd_plan, 'queue': cmd_queue, 'nightly': cmd_nightly, 'hold': cmd_hold, 'score': cmd_score, 'trend': cmd_trend,
            'draft': cmd_draft, 'status': cmd_status, 'copies': cmd_copies, 'arm': cmd_arm, 'refreeze': cmd_refreeze, 'rejudge': cmd_rejudge, 'annotate': cmd_annotate}[a.cmd](a, cfg)


if __name__ == '__main__':
    sys.exit(main())
