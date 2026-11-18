#!/usr/bin/env python3
"""Rehearse the scoreboard's glue against a FAKE game: no GPU, no gate, no model, no API.

    python3 -I -B rehearse.py CELL[,CELL...] [--keep]

The real pilot (the committed head of the dev repo, cut by git archive like a hold does), the real hsap and the real runner, referee, score and store run against
`fake_game.py` (a simulated bridge with invented physics, from PilotChapters2's rehearsals; its `test_hsap` / `test_hsap_actions` modules come from the pilot tree).
It proves that the cell's command line is one the pilot accepts, that the state journal carries what the referee reads, and that a row comes out; it does NOT
prove that a cell is playable in the real game (the fake has no walls and invented ledges). Cells that have a scenario in the private `rehearsal-scenarios.json` can be rehearsed: the
start of the scenario is the cell's own start, so the start check passes.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import board  # noqa: E402
import config  # noqa: E402
import hold  # noqa: E402
import runner  # noqa: E402
import score  # noqa: E402
import store  # noqa: E402

def scenarios():
    """The fake game's scenario of each rehearsable cell (map, start, things): private (places), playbench-local/rehearsal-scenarios.json."""
    f = config.local_dir() / 'rehearsal-scenarios.json'
    try:
        return json.loads(f.read_text())
    except (OSError, ValueError):
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cells')
    ap.add_argument('--keep', action='store_true')
    ap.add_argument('--arm', default='rules')
    ap.add_argument('--commit', default='HEAD', help='the pilot commit to rehearse with (a game-free bisect: the first decisions of the run are printed)')
    a = ap.parse_args()
    cfg = config.load()
    root = Path(tempfile.mkdtemp(prefix='pb-rehearse-', dir='/tmp'))
    snap = config.HARNESS / 'playthrough-playbench-rehearsal'
    if snap.exists():
        shutil.rmtree(snap)
    commit = subprocess.check_output(['git', '-C', cfg['pilot_repo'], 'rev-parse', a.commit], text=True).strip()
    hold.make_snapshot(cfg['pilot_repo'], commit, snap)
    copy = root / 'rehearsal-copy'
    (copy / 'runs').mkdir(parents=True)
    cells = {c.id: c for c in board.load()}
    st = store.Store(root / 'results.sqlite')
    arms = board.arms()
    code = 0
    scens = scenarios()
    for cid in a.cells.split(','):
        if cid not in scens:
            print(f'{cid}: no scenario in {config.local_dir() / "rehearsal-scenarios.json"} (rehearsable: {", ".join(scens) or "none"})')
            return 2
        scen = root / f'{cid}.json'
        scen.write_text(json.dumps(scens[cid]))
        env = {'REHEARSE_TREE': str(snap), 'REHEARSE_HSAP': str(snap / 'hsap.py'), 'REHEARSE_HS_RUN': str(HERE / 'fake_hs_run.sh'),
               'REHEARSE_WRAP': str(HERE / 'hsap_wrap.py'), 'REHEARSE_SCENARIO': str(scen), 'HSAP_ANALOG': '1',
               **{str(k): str(v) for k, v in (cfg.get('game_env') or {}).items()}}   # (what a hold passes to every run: the config's game_env)
        night = time.strftime('%Y%m%d')
        plan = {'night': night, 'hold': 1, 'out': str(root / f'hold-{cid}'), 'pilot_dir': str(snap / 'pilot'), 'python': sys.executable, 'copies': [str(copy)], 'local': str(config.LOCAL),
                'items': [{'cell': cid, 'arm': a.arm, 'attempt': 1}], 'hold_s': 1000.0, 'reserve_s': 5, 'shots': 0, 'env': env, 'allowance_usd': None,
                'pilot_cmd': [sys.executable, '-I', '-B', str(HERE / 'rehearse_pilot.py')]}
        h = runner.Hold(plan, player_probe=lambda: [])
        t0 = time.time()
        h.play()
        rec = h.done[0]
        row = score.score_cell(rec, cells[cid], a.arm, arms[a.arm], night, commit[:9], score.load_metrics(snap / 'pilot'), config.LOCAL)
        print(f'--- {cid} ({time.time() - t0:.0f} s): success {row["success"]} valid {row["valid"]} ttg {row["time_to_goal_s"]} progress {row["progress"]} decisions {row["decisions"]} '
              f'stuck {row["stuck_s"]} cost {row["cost_usd"]} outcome {row["pilot_outcome"]}\n    why: {row["why"]}\n    referee: {json.dumps(row["referee"])[:400]}', flush=True)
        try:
            labels = [json.loads(x).get('choice') for x in (snap / 'pilot' / 'runs' / rec['tag'] / 'transcript.jsonl').read_text().splitlines() if '"decision"' in x][:6]
        except OSError:
            labels = []
        print(f'    first decisions at {commit[:9]}: {labels}', flush=True)
        try:
            steps = [x for x in (snap / 'pilot' / 'runs' / rec['tag'] / 'steps.txt').read_text().splitlines() if x.startswith(('ocarina', 'use'))][:6]
        except OSError:
            steps = []
        if steps:
            print(f'    first ocarina/use steps sent: {steps}', flush=True)
        if not row['success']:
            code = 1
            log = Path(plan['out']) / 'cells' / f"{rec['tag']}.log"
            print((log.read_text()[-1200:] if log.is_file() else 'no log'))
        st.add_cell(row)
    if not a.keep:
        shutil.rmtree(snap, ignore_errors=True)
        shutil.rmtree(root, ignore_errors=True)
    else:
        print('kept', snap, root)
    return code


if __name__ == '__main__':
    sys.exit(main())
