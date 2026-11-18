#!/usr/bin/env python3
"""bosspoints: read a finished hold folder, print the per-run table, and (--panels) build one picture panel per run.

    python3 -I -B analyze_hold.py HOLDDIR [--table FILE] [--panels]

The table is used only to name the flag hashes the runs watched (every flag name of a `watch` item); without it (or without the world model,
which hashes the names) the hashes are printed as they are and a note says so on stderr.

What it reads (written by the hold runner; the hsap files are hsap's own):
  HOLDDIR/result.json            {"started_at", "finished_at", "elapsed_s", "kernel", "runs": [row]}; a row is {"id", "lane", "save", "started",
                                 "ended" (seconds), "returncode", "shots" (a count), "run_folder", "summary", "journal": {"gameplay", "areas",
                                 "events", "music", "flags_seen" {hash: [[value, t], ...]}, "steps" [{"src", "result", "detail"}], "last_state"}},
                                 or {"id", "lane", "skipped" | "error"}
  HOLDDIR/live/<id>/out.jsonl    hsap's events: {"ev": "step" | "state" ...}
  HOLDDIR/live/<id>/state.jsonl  hsap's state journal from the first sample after the load, before any step ran
  <run_folder>/shots/*.png       the run's pictures, the number in a file name = the present (frame) it was taken at
--panels needs $BOSSPOINTS_PANELS: a script `bash SCRIPT DEST.jpg COLUMNS IMAGE CAPTION [IMAGE CAPTION ...]` that writes one panel (and ImageMagick
if the script uses it); there is no default.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bosspoints_table as T  # noqa: E402

ENV_PANELS = 'BOSSPOINTS_PANELS'
CALM_SAMPLES = 30   # three calm seconds (about ten journal rows a second) = control


def names_of(table, flag_hash):
    """{'0x%08x' hash: flag name} for every flag the table's recipes watch."""
    return {'0x%08x' % flag_hash(n): n for n in table.watch_names()}


def read_states(live):
    states, steps = [], []
    p = live / 'out.jsonl'
    if not p.is_file():
        return states, steps
    for line in p.read_text(errors='replace').splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get('ev') == 'state':
            states.append(d)
        elif d.get('ev') == 'step':
            steps.append(d)
    return states, steps


def journal(live):
    """every row of the hsap state journal (live/state.jsonl): from the first sample after the load, before any step ran"""
    p = live / 'state.jsonl'
    rows = []
    if p.is_file():
        for line in p.read_text(errors='replace').splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    return rows


def first_state_rows(live):
    """the journal's first row: where the save put the player. (The out.jsonl `state` rows start only after control, by when a boot's button
    presses may already have moved him.)"""
    rows = journal(Path(live))
    return rows[0] if rows else None


def pre_control(live):
    """what happened between the first sample and the first three calm seconds: the journal's first place, how far the player moved, the events and music"""
    rows = journal(Path(live))
    if not rows:
        return None
    calm, end = 0, len(rows) - 1
    for i, x in enumerate(rows):
        calm = calm + 1 if x.get('map') and x.get('event') == 0 and x.get('loading') == 0 else 0
        if calm >= CALM_SAMPLES:
            end = i
            break
    pre = rows[:end + 1]
    p0 = rows[0].get('pos') or [0, 0, 0]
    moved = max(sum((a - b) ** 2 for a, b in zip(x.get('pos') or p0, p0)) ** 0.5 for x in pre)
    events = [(round(x['t'] - rows[0]['t'], 1), x['event']) for i, x in enumerate(pre) if i == 0 or x['event'] != pre[i - 1]['event']]
    return dict(map=rows[0].get('map'), pos=p0, facing=rows[0].get('facing'), child=rows[0].get('child'), moved=round(moved, 1), events=events[:8],
                music=sorted({x.get('music') or '' for x in pre} - {''}), seconds=round(rows[end]['t'] - rows[0]['t'], 1), life=(rows[0].get('life'), rows[end].get('life')))


def nearest_shot(shots, frame):
    best = None
    for s in shots:
        m = re.search(r'(\d+)', s.name)
        if m:
            n = int(m.group(1))
            if best is None or abs(n - frame) < abs(best[0] - frame):
                best = (n, s)
    return best[1] if best else None


def frame_at(states, t):
    best = None
    for s in states:
        if s.get('t') is not None and s.get('frame') is not None and (best is None or abs(s['t'] - t) < abs(best['t'] - t)):
            best = s
    return best['frame'] if best else None


def panel(out, row, j, panels_script, emit):
    """One panel of the pictures nearest to the key moments of a run: standing there, after the first `enter`, the first watched flag, the end."""
    live = out / 'live' / row['id']
    states, steps = read_states(live)
    shots = sorted((Path(row['run_folder']) / 'shots').glob('*.png'))
    if not shots or not states:
        return
    t_game = (j.get('gameplay') or {}).get('t') or 0.0
    moments = [('1. standing there, %.0f s after control' % (t_game + 3.5), t_game + 3.5)]
    ent = [s for s in steps if s['src'].startswith('enter')]
    if ent:
        moments.append(('2. after the enter step (%s)' % ent[0]['result'], ent[0]['t']))
    flipped = None
    for s in states:
        if any(v for v in (s.get('flags') or {}).values() if v):
            flipped = s['t']
            break
    if flipped is not None:
        moments.append(('3. first watched flag set (t %.0f s)' % flipped, flipped))
    moments.append(('%d. last state (t %.0f s)' % (len(moments) + 1, states[-1]['t']), states[-1]['t']))
    args = []
    for cap, t in moments:
        fr = frame_at(states, t)
        s = nearest_shot(shots, fr) if fr is not None else None
        if s:
            args += [str(s), cap]
    if args:
        dest = out / ('panel-%s.jpg' % row['id'])
        env = {'PANEL_W': '640', 'PANEL_H': '360', 'PATH': '/usr/bin:/bin:/usr/local/bin'}
        r = subprocess.run(['bash', panels_script, str(dest), '2'] + args, capture_output=True, text=True, env=env)
        emit('   panel:', dest, (r.stdout or r.stderr).strip()[:120])


def report(out, names, panels_script=None, emit=print):
    out = Path(out)
    res = json.loads((out / 'result.json').read_text())
    emit('hold: started %s finished %s elapsed %s s; kernel %s' % (res.get('started_at'), res.get('finished_at'), res.get('elapsed_s'), res.get('kernel')))
    for row in sorted(res['runs'], key=lambda r: (r.get('lane', ''), r.get('started', 0))):
        if row.get('skipped') or row.get('error'):
            emit('\n== %s (lane %s): %s' % (row['id'], row.get('lane'), row.get('skipped') or row.get('error')))
            continue
        j = row.get('journal') or {}
        emit('\n== %s (lane %s, save %s): rc %s, %.0f s, %s pictures' % (row['id'], row['lane'], row['save'], row.get('returncode'), row['ended'] - row['started'], row.get('shots')))
        emit('   gameplay:', j.get('gameplay'), '| areas:', j.get('areas'), '| events seen:', j.get('events'))
        emit('   before control (the journal, from the load):', pre_control(out / 'live' / row['id']))
        emit('   music:', j.get('music'))
        fl = {names.get(k, k): v for k, v in (j.get('flags_seen') or {}).items()}
        emit('   watched flags:', fl)
        emit('   steps:', [(s['src'].split()[0], s['result'], (s.get('detail') or '')[:60]) for s in j.get('steps', []) if s['src'].split()[0] in ('enter', 'walk', 'run', 'press', 'advance', 'talk')])
        emit('   last state:', j.get('last_state'))
        emit('   summary:', row.get('summary'))
        if panels_script and row.get('run_folder'):
            panel(out, row, j, panels_script, emit)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('hold', help='the finished hold folder (result.json, live/)')
    ap.add_argument('--table', help='the table file, to name the watched flags (default: $BOSSPOINTS_TABLE, else table.local.json beside this tool)')
    ap.add_argument('--panels', action='store_true', help=f'also build panel-<run id>.jpg per run with ${ENV_PANELS}')
    a = ap.parse_args(argv)
    panels = None
    if a.panels:
        panels = os.environ.get(ENV_PANELS)
        if not panels:
            print(f'bosspoints: --panels needs ${ENV_PANELS}: the panel script (bash SCRIPT DEST.jpg COLUMNS IMAGE CAPTION ...); it is not part of this repository', file=sys.stderr)
            return 2
    names = {}
    try:
        names = names_of(T.load(a.table), T.flag_hash_function())
    except T.TableError as e:
        print('bosspoints: flags are not named: ' + str(e), file=sys.stderr)
    if not (Path(a.hold) / 'result.json').is_file():
        print(f'bosspoints: {Path(a.hold) / "result.json"} does not exist: {a.hold} is not a finished hold folder', file=sys.stderr)
        return 2
    report(Path(a.hold).resolve(), names, panels)
    return 0


if __name__ == '__main__':
    sys.exit(main())
