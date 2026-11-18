#!/usr/bin/env python3
"""Cut the benchmark course's segments from the pilot's own segment files.

  mkcourse.py --segments <pilot/segments> --out <bench/segments> [--hard-points <file.json>] [--bench-id ID] [--entries a,b]

For each entry of course.py: load its source segment, keep the goals it names (all targets, the first N, or for 'hard' the
targets nearest to the points of a local hard-points file: a JSON list of [x, z], made from the runs that got stuck),
set the budget and the decision limit, and write <out>/<entry id>.toml. The cut files are game-derived and stay local.
A follow entry also gets its ghost's route: the targets of one goal of another segment (ghost.json next to it).

The reader of TOML is the standard library's; the writer here knows the segment schema only (strings, numbers, booleans, lists,
inline tables of targets).
"""
import argparse
import json
import math
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import course  # noqa: E402

HARD_FALLBACK = (6, 12)   # without a hard-points file: the targets 6 to 12 of the first goal (the legs after the easy start)


def toml_value(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return json.dumps(v)   # a JSON string is a TOML basic string
    if isinstance(v, (list, tuple)):
        return '[' + ', '.join(toml_value(x) for x in v) + ']'
    if isinstance(v, dict):
        return '{' + ', '.join(f'{k} = {toml_value(x)}' for k, x in v.items()) + '}'
    raise TypeError(f'cannot write {type(v).__name__}')


def dumps_segment(seg, header=''):
    """A segment dict (as tomllib loads it) written back as TOML: top-level values, then one [[goal]] per goal."""
    out = [f'# {h}' for h in header.splitlines()] if header else []
    for k, v in seg.items():
        if k != 'goal':
            out.append(f'{k} = {toml_value(v)}')
    for g in seg.get('goal', []):
        out.append('')
        out.append('[[goal]]')
        for k, v in g.items():
            if k == 'targets':
                out.append('targets = [' + ',\n           '.join(toml_value(t) for t in v) + ']')
            else:
                out.append(f'{k} = {toml_value(v)}')
    return '\n'.join(out) + '\n'


def nearest_targets(targets, points, within=40.0):
    """For each point the nearest target (by its `at`), in the order of the targets along the route, kept once; a point with
    no target within `within` metres is left out."""
    picked = set()
    for x, z in points:
        best = min(((math.hypot(t['at'][0] - x, t['at'][1] - z), i) for i, t in enumerate(targets) if 'at' in t), default=None)
        if best and best[0] <= within:
            picked.add(best[1])
    return [targets[i] for i in sorted(picked)]


def cut(entry, segments_dir, hard_points=None, bench_id='bench'):
    """The cut segment (a dict) for a course entry, from <segments_dir>/<entry.source>.toml. Raises FileNotFoundError."""
    src = tomllib.loads((Path(segments_dir) / f'{entry.source}.toml').read_text())
    seg = {k: v for k, v in src.items() if k != 'goal'}
    seg['name'] = f'{bench_id}-{entry.id}'
    seg['what'] = f"{entry.kind} (benchmark course, cut from {entry.source})"
    seg['budget_seconds'] = entry.budget_s
    seg['wall'] = entry.wall_s
    seg['max_decisions'] = entry.max_decisions
    seg['save_after'] = False
    if entry.save:
        seg['save'] = entry.save
    goals = []
    wanted = entry.goals or {g['name']: None for g in src['goal']}
    by_name = {g['name']: g for g in src['goal']}
    for name, how in wanted.items():
        if name not in by_name:
            raise KeyError(f'{entry.source} has no goal {name!r}')
        g = dict(by_name[name])
        targets = list(g['targets'])
        if how == 'hard':
            picked = nearest_targets(targets, hard_points) if hard_points else []
            targets = picked or targets[HARD_FALLBACK[0]:HARD_FALLBACK[1]]
        elif isinstance(how, int):
            targets = targets[:how]
        g['targets'] = targets
        goals.append(g)
    seg['goal'] = goals
    seg['watch'] = sorted(set(seg.get('watch', [])))
    return seg


def ghost_route(entry, segments_dir):
    """The leader's route for a follow entry: the `at` points of the goal ghost_goal of segment ghost_source, in order."""
    src = tomllib.loads((Path(segments_dir) / f'{entry.ghost_source}.toml').read_text())
    g = next(g for g in src['goal'] if g['name'] == entry.ghost_goal)
    return {'area': src['area'], 'points': [list(t['at']) for t in g['targets'] if 'at' in t], 'y': [t.get('y') for t in g['targets'] if 'at' in t],
            'speed': entry.ghost_speed}


def make(segments_dir, out_dir, hard_points=None, bench_id='bench', entries=None):
    """Write every (or the named) entry's segment into out_dir; returns {entry id: path or the error text}."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    got = {}
    for e in course.COURSE:
        if entries and e.id not in entries:
            continue
        try:
            seg = cut(e, segments_dir, hard_points, bench_id)
            path = out_dir / f'{e.id}.toml'
            path.write_text(dumps_segment(seg, f'{e.kind}: cut from {e.source} by bench/mkcourse.py (game-derived, local)'))
            tomllib.loads(path.read_text())   # what was written must read back
            if e.follow:
                (out_dir / f'{e.id}.ghost.json').write_text(json.dumps(ghost_route(e, segments_dir)))
            got[e.id] = str(path)
        except (OSError, KeyError, StopIteration, ValueError) as err:
            got[e.id] = f'missing: {type(err).__name__}: {err}'
    return got


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--segments', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--hard-points')
    ap.add_argument('--bench-id', default='bench')
    ap.add_argument('--entries')
    a = ap.parse_args()
    points = json.loads(Path(a.hard_points).read_text()) if a.hard_points else None
    for k, v in make(a.segments, a.out, points, a.bench_id, set(a.entries.split(',')) if a.entries else None).items():
        print(f'{k:10s} {v}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
