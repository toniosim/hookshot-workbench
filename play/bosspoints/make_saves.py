#!/usr/bin/env python3
"""bosspoints: build the saves of the local table with the save tool (a local tool that is not part of this repository).

    HS_MAKE_SAVE=/path/to/hs_make_save.py python3 -I -B make_saves.py (--out DIR | --lib) [--table FILE] [--only KEY,KEY]
                                                                       [--with NAME,...] [--game DIR] [--print]

One save tool run per start that has a "save": from the table's base save, at the start's place (`--start`), with the start's `--give` items and
`--flag NAME=VALUE` flags, as `python3 -I -B $HS_MAKE_SAVE --game GAME --from BASE --start ... --age ... --out ...`.
  --out DIR    write the saves as folders DIR/<save name> (a trial)       --lib    write library entries (`--out lib:NAME --kind added ...`)
  --only       build only the starts of these targets                      --with   also build the starts whose save is "optional" under these names
  --print      print the commands, one per line, and run nothing
HS_MAKE_SAVE is the path of the save tool; there is no default. The game folder is --game, else the table's "game".
"""
import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bosspoints_table as T  # noqa: E402

ENV_TOOL = 'HS_MAKE_SAVE'
DEFAULT_NOTE = 'written by bosspoints from the local table; local only'


def start_spec(map_name, x, y, z, facing):
    """The save tool's `--start Map:x,y,z,yaw` (yaw in radians)."""
    return '%s:%.2f,%.2f,%.2f,%.4f' % (map_name, x, y, z, T.yaw_rad(facing))


def command(table, st, tool, game, out, lib):
    """The argument list that builds one start's save."""
    sv = st['save']
    spec = sv['start'] or start_spec(st['map'], st['at']['x'], st['at']['y'], st['at']['z'], st['at']['facing'])
    cmd = [sys.executable, '-I', '-B', tool, '--game', game, '--from', table.base_save, '--start', spec, '--age', st['age']]
    cmd += ['--out', ('lib:' + sv['name']) if lib else str(Path(out) / sv['name'])]
    for item in sv['give']:
        cmd += ['--give', item]
    for flag in sv['flags']:
        cmd += ['--flag', flag]
    if lib:
        cmd += ['--kind', 'added', '--point', sv['point'] or '%s: %s player at %s' % (st['title'], st['age'], spec), '--note', sv['note'] or DEFAULT_NOTE]
    return cmd


def commands(table, tool, game, out, lib, only=None, optional=()):
    """[(save name, argument list)] in table order."""
    return [(st['save']['name'], command(table, st, tool, game, out, lib)) for st in table.select(only, optional) if st['save']]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--out', metavar='DIR', help='folder: write the saves there as DIR/<save name>')
    g.add_argument('--lib', action='store_true', help='write library entries')
    ap.add_argument('--table', metavar='FILE', help='the table file (default: $BOSSPOINTS_TABLE, else table.local.json beside this tool)')
    ap.add_argument('--only', metavar='KEY,KEY', help='target keys, comma separated')
    ap.add_argument('--with', dest='with_', default='', metavar='NAME,NAME', help='names of the optional saves to build too, comma separated')
    ap.add_argument('--game', metavar='DIR', help='folder of the extracted game files (default: the table\'s "game")')
    ap.add_argument('--print', dest='print_only', action='store_true', help='print the commands, run nothing')
    a = ap.parse_args(argv)
    try:
        table = T.load(a.table)
        tool = os.environ.get(ENV_TOOL)
        if not tool and not a.print_only:
            raise T.TableError(f'${ENV_TOOL} is not set: it names the save tool (hs_make_save.py), a local tool that is not part of this repository')
        game = a.game or table.game
        if not game:
            raise T.TableError('no game folder: pass --game DIR or set "game" in the table')
        rows = commands(table, tool or '$' + ENV_TOOL, game, a.out, a.lib, set(a.only.split(',')) if a.only else None, set(filter(None, a.with_.split(','))))
    except T.TableError as e:
        print('bosspoints: ' + str(e), file=sys.stderr)
        return 2
    if not rows:
        print('bosspoints: no start with a save is selected', file=sys.stderr)
        return 2
    if a.print_only:
        for _, cmd in rows:
            print(' '.join(c if c == '$' + ENV_TOOL else shlex.quote(c) for c in cmd))
        return 0
    if a.out:
        Path(a.out).mkdir(parents=True, exist_ok=True)
    results = []
    for name, cmd in rows:
        r = subprocess.run(cmd, capture_output=True, text=True)
        text = (r.stdout + r.stderr).strip()
        results.append((name, r.returncode, text))
        print('%-28s rc=%d  %s' % (name, r.returncode, text.splitlines()[-1][:200] if text else ''))
    return 1 if any(rc for _, rc, _ in results) else 0


if __name__ == '__main__':
    sys.exit(main())
