#!/usr/bin/env python3
"""bosspoints: write the scenario files of the local table (pilot/scenario.py's `ls-scenario/1`).

    python3 -I -B write_scenarios.py --out DIR [--table FILE] [--only KEY,KEY]

One file DIR/<start name>.toml for every start of the table that has "actions". The scenario is the generic frame (format, name, purpose
coverage, one player, the claim, the start's library save, `[at]` with `from = "save"` = start where the save puts the player, the checks) around the
start's own action list, whose "{var[i]}" values are replaced by the table's numbers. Each file is checked with scenario.py's `problems()` before
anything is written, and read back and compiled to hsap steps afterwards. The files hold what the table holds (game names and coordinates):
write them outside the repository.
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'pilot'))
import bosspoints_table as T  # noqa: E402
import scenario as S  # noqa: E402

DEFAULT_EXPECT = [{'check': 'crash'}, {'check': 'visual', 'subs': ['black', 'void', 'missing_textures']}]
DEFAULT_HEADER = 'written by bosspoints from the local table: game-derived, keep it out of any repository, issue or post'


def build(st):
    """The scenario dict of a start (see S.dumps for the key order the file gets)."""
    at = {'map': st['map'], 'age': st['age']}
    at.update(st['at'] or {})
    if st['save']:
        at['from'] = 'save'
    sc = {'format': S.FORMAT, 'name': st['name'], 'purpose': 'coverage', 'claim': st['claim'], 'players': 1}
    if st['save']:
        sc['save'] = st['save']['name']
    sc['at'] = at
    sc['action'] = T.subst(st['actions'], T.context(st))
    sc['expect'] = [dict(e) for e in (st['expect'] if st['expect'] is not None else DEFAULT_EXPECT)]
    return sc


def text_of(st, sc):
    return ''.join('# ' + line + '\n' for line in (st['header'] or [DEFAULT_HEADER])) + S.dumps(sc)


def write_all(table, out, only=None):
    """Writes the files; returns their names. Nothing is written when any scenario has problems (T.TableError names them)."""
    starts = [st for st in table.select(only) if st['actions']]
    if not starts:
        raise T.TableError(f'{table.path}: no start has "actions", so there is no scenario to write')
    built = []
    for st in starts:
        sc = build(st)
        errs = S.problems(sc)
        if errs:
            raise T.TableError(f'{table.path}: start {st["name"]!r}: the scenario has problems: ' + '; '.join(errs))
        built.append((st, sc))
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for st, sc in built:
        f = out / (st['name'] + '.toml')
        f.write_text(text_of(st, sc))
        S.compile_steps(S.load(f))
        written.append(f.name)
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', required=True, help='folder for the .toml files (outside the repository: they hold game data)')
    ap.add_argument('--table', help='the table file (default: $BOSSPOINTS_TABLE, else table.local.json beside this tool)')
    ap.add_argument('--only', help='target keys, comma separated')
    a = ap.parse_args(argv)
    try:
        table = T.load(a.table)
        written = write_all(table, a.out, set(a.only.split(',')) if a.only else None)
    except (T.TableError, S.ScenarioError) as e:
        print('bosspoints: ' + str(e), file=sys.stderr)
        return 2
    print('written', len(written), 'scenarios:', ' '.join(written))
    return 0


if __name__ == '__main__':
    sys.exit(main())
