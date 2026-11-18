#!/usr/bin/env python3
"""routes.py (the library's command line) on made-up runs: import (one run, a folder tree, a second time), show, targets and cover targets from a run's legs,
the frontier, the route (library then world), the report of what each run added, and the refusals. Made-up names; no game, no network.   python3 -I -B test_routes.py"""
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import routelib  # noqa: E402
import routes  # noqa: E402
import test_routelib as tr  # noqa: E402

FAILS, CHECKS = [], [0]


def check(cond, what):
    CHECKS[0] += 1
    if not cond:
        FAILS.append(what)
        print('FAIL', what, flush=True)


def call(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            rc = routes.main(argv)
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 2
    return rc, out.getvalue(), err.getvalue()


def run_checks(tmp):
    lib = str(tmp / 'lib')
    r = tr.FakeRun(tmp / 'tree' / 'a', 'tree-a', start=(0, 100, 0))
    r.leg('run 0 40 radius 2.5 timeout 30', [(0, 100, 40)], 'reached')
    r.leg('run 0 100 radius 2.5 timeout 30', [(0, 100, 60)], 'stuck', detail='40.00 m from the point; moved under 0.3 m in 2.5 s at 0.0 100.0 60.0')
    a = r.write(log=tr.build_log('v3.0.0-rc.4-1-gaaaa111'))
    r = tr.FakeRun(tmp / 'tree' / 'sub' / 'b', 'tree-b', start=(0, 100, 0))
    r.leg('run 0 80 radius 2.5 timeout 30', [(0, 100, 80)], 'reached')
    b = r.write(log=tr.build_log('v3.0.0-rc.4-2-gbbbb222'))
    (tmp / 'tree' / 'empty').mkdir()
    rc, out, err = call(['--lib', lib, 'import', str(a)])
    check(rc == 0 and 'tree-a' in out and 'gaaaa111' in out and 'new edges' in out, f'import prints the run, its build and what it added ({rc}, {out[:200]!r})')
    rc, out, err = call(['--lib', lib, 'import', str(a)])
    check(rc == 0 and 'already imported' in out, f'a second import says so ({out[:120]!r})')
    rc, out, err = call(['--lib', lib, 'import-tree', str(tmp / 'tree'), '--min-age', '0'])
    check(rc == 0 and 'tree-b' in out and 'imported 1' in out and 'skipped 1' in out, f'import-tree finds runs in folders and counts the imported and the skipped ({out[-300:]!r})')
    rc, out, err = call(['--lib', lib, 'show'])
    check(rc == 0 and 'Testland_Child' in out and 'stuck' in out and 'verified edges' in out, f'show lists the map ({out[:200]!r})')
    rc, out, err = call(['--lib', lib, 'show', 'Nowhere_Child'])
    check(rc != 0 and 'no data' in (out + err), 'show of a map with no data says so')
    rc, out, err = call(['--lib', lib, 'target', 'add', 'p1', '--map', 'Testland_Child', '--at', '0', '200', '--age', 'child', '--issue', '7', '--label', 'the place'])
    check(rc == 0, f'target add ({err})')
    rc, out, err = call(['--lib', lib, 'target', 'cover', 'legs', '--map', 'Testland_Child', '--from-steps', str(a / 'pilot' / 'live' / 'steps.txt')])
    check(rc == 0 and '2 legs' in out, f'a cover target from a run\'s legs ({out!r} {err})')
    rc, out, err = call(['--lib', lib, 'target', 'list'])
    check('p1' in out and 'legs' in out and 'frontier' in out, f'target list shows frontiers ({out[:300]!r})')
    rc, out, err = call(['--lib', lib, 'frontier', 'p1', '--json'])
    f = json.loads(out)
    check(rc == 0 and f['known'] and abs(f['pos'][2] - 80.0) < 3.0 and 119 < f['remaining_m'] < 122, f'frontier p1 is the best walked point ({f.get("pos")}, {f.get("remaining_m")})')
    rc, out, err = call(['--lib', lib, 'route', 'Testland_Child', '--from', '0', '100', '0', '--to', '0', '200', '--json'])
    r = json.loads(out)
    check(rc == 0 and r['source'] == 'library' and not r['complete'] and r['steps'] and r['frontier']['remaining_m'] > 100, f'route: the library as far as it goes ({r["source"]}, {len(r["steps"])} steps)')
    rc, out, err = call(['--lib', lib, 'route', 'Testland_Child', '--from', '0', '100', '0', '--to', '0', '60'])
    check(rc == 0 and 'complete' in out and 'run ' in out, f'route to a walked point prints the steps ({out[:200]!r})')
    rc, out, err = call(['--lib', lib, 'report'])
    check(rc == 0 and '| tree-a' in out and '| tree-b' in out and 'p1' in out and 'metres' in out, f'report: a row per run and the targets ({out[:300]!r})')
    rc, out, err = call(['--lib', lib, 'import', str(tmp / 'empty')])
    check(rc != 0 and 'state.jsonl' in (out + err), 'a folder with no run is refused')


def main():
    with tempfile.TemporaryDirectory(prefix='test-routes-') as t:
        run_checks(Path(t))
    if FAILS:
        raise SystemExit(f'test_routes: {len(FAILS)} of {CHECKS[0]} checks FAILED')
    print(f'test_routes: all {CHECKS[0]} checks passed')


if __name__ == '__main__':
    main()
