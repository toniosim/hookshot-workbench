#!/usr/bin/env python3
"""bosspoints: write a hold's plan from the local table: one hsap step file per run, and plan.json.

    python3 -I -B plan_hold.py HOLDDIR --saves DIR [--table FILE]
        -> HOLDDIR/plan.json, HOLDDIR/steps/<run id>.txt

A hold plays several runs, each one hsap game from a library save and a step list; the runs of one lane play one after the other. The table's
"hold.runs" name the runs (lane, id, start, wall time); each run's step list is its own or its start's hold recipe, written line by line:
text lines (format strings over the start's names, see bosspoints_table.py), `watch` lines with the game's flag hashes, and `route` items
replaced by the world model planner's walk lines (needs the world model; it is loaded only when a recipe uses a watch or a route item).

plan.json: {"runs": [{"lane", "id", "save" (the library folder of the save: SAVES/<name>), "steps" (relative path), "wall", "note",
"expect" (a flag name or null), "save_name"}]}. --saves, else $BOSSPOINTS_SAVES, is the folder of the save library; there is no default.
"""
import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bosspoints_table as T  # noqa: E402

ENV_SAVES = 'BOSSPOINTS_SAVES'


class World:
    """The world model parts a plan may need, loaded on first use (tests pass stand-ins)."""

    def __init__(self, flag_hash=None, planner=None):
        self._hash, self._planner = flag_hash, planner

    def hash(self, name):
        if self._hash is None:
            self._hash = T.flag_hash_function()
        return self._hash(name)

    def planner(self):
        if self._planner is None:
            self._planner = T.planner_module()
        return self._planner


def route_lines(spec, ctx, planner):
    """(lines, outcome): the planner's steps from var `from` to var `to` (each with a timeout), as many as it gets: a drop or a gap ends it."""
    area = spec.get('map') or ctx['map']
    a, b = ctx[spec['from']], ctx[spec['to']]
    if not planner.available(area):
        return [], 'no plan'
    r = planner.plan(area, (a[0], a[2]), (b[0], b[2]), from_y=a[1], to_y=b[1], doors=spec.get('doors', 'through'), radius=spec.get('radius', 1.5))
    suffix = ' timeout %s' % spec.get('timeout', 20)
    lines = [s + suffix for s in (r.get('steps') or [])][:int(spec.get('max_steps', 14))]
    return lines, ('ok' if r['ok'] else '%s: %s' % (r.get('why'), (r.get('detail') or '')[:120]))


def expand(steps, ctx, world):
    """(lines, outcomes) of a recipe: text lines rendered, watch items hashed, route items planned."""
    lines, outcomes = [], []
    for item in steps:
        if isinstance(item, str):
            lines.append(T.render(item, ctx))
        elif 'watch' in item:
            lines.append('watch ' + ' '.join('0x%08x' % world.hash(n) for n in item['watch']))
        else:
            got, why = route_lines(item['route'], ctx, world.planner())
            lines += got
            outcomes.append(why)
    return lines, outcomes


def plan(table, hold, saves, world):
    """Writes plan.json and the step files into folder `hold`; returns the run records."""
    hold = Path(hold)
    (hold / 'steps').mkdir(parents=True, exist_ok=True)
    runs = []
    for r in table.runs:
        ctx = T.context(r['start'])
        lines, outcomes = expand(r['steps'], ctx, world)
        (hold / 'steps' / (r['id'] + '.txt')).write_text('\n'.join(lines) + '\n')
        note = T.render(r['note'], ctx, route='; '.join(outcomes)) if r['note'] is not None else None
        runs.append(dict(lane=r['lane'], id=r['id'], save=str(Path(saves) / r['save']), steps='steps/%s.txt' % r['id'], wall=r['wall'], note=note,
                         expect=r['expect'], save_name=r['save']))
    (hold / 'plan.json').write_text(json.dumps(dict(runs=runs), indent=1))
    return runs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('hold', help='the hold folder (plan.json and steps/ are written there)')
    ap.add_argument('--saves', help=f'folder of the save library (default: ${ENV_SAVES}; no other default)')
    ap.add_argument('--table', help='the table file (default: $BOSSPOINTS_TABLE, else table.local.json beside this tool)')
    a = ap.parse_args(argv)
    try:
        saves = a.saves or os.environ.get(ENV_SAVES)
        if not saves:
            raise T.TableError(f'no save library folder: pass --saves DIR or set ${ENV_SAVES}')
        table = T.load(a.table)
        if not table.runs:
            raise T.TableError(f'{table.path}: no "hold.runs" to plan')
        runs = plan(table, a.hold, saves, World())
    except T.TableError as e:
        print('bosspoints: ' + str(e), file=sys.stderr)
        return 2
    for r in runs:
        print(r['lane'], r['id'], r['save_name'], (r['note'] or '')[:100])
    return 0


if __name__ == '__main__':
    sys.exit(main())
