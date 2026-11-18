#!/usr/bin/env python3
"""pilot.world_plan() with $ROUTELIB_DIR: the planner is the library's (known way first, then the world model's plan), without it the world model's own; a
library that cannot be read is no failure. Made-up library; no game, no network.   python3 -I -B test_pilot_routelib.py"""
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pilot  # noqa: E402
import routelib  # noqa: E402

FAILS, CHECKS = [], [0]


def check(cond, what):
    CHECKS[0] += 1
    if not cond:
        FAILS.append(what)
        print('FAIL', what, flush=True)


def main():
    os.environ.pop('ROUTELIB_DIR', None)
    base = pilot.world_plan()
    check(base is None or base.__module__ == 'worldmodel.plan', 'without ROUTELIB_DIR the planner is the world model\'s own')
    with tempfile.TemporaryDirectory(prefix='test-pilot-routelib-') as t:
        os.environ['ROUTELIB_DIR'] = str(Path(t) / 'lib')
        p = pilot.world_plan()
        if base is not None:
            check(p is not base and callable(p) and p.__name__ == 'wrapped', 'with ROUTELIB_DIR the planner is the library\'s wrapper')
            r = p('NoSuchArea_Child', (0.0, 0.0), (5.0, 5.0), from_y=1.0, to_y=1.0, radius=2.0)
            check(isinstance(r, dict) and r.get('ok') is False, f'an area the library lacks goes to the world model ({r.get("why")})')
        (Path(t) / 'blocked').write_text('x')
        os.environ['ROUTELIB_DIR'] = str(Path(t) / 'blocked' / 'lib')
        check(pilot.world_plan() is not None or base is None, 'a library path that cannot be read is no failure')
    os.environ.pop('ROUTELIB_DIR', None)
    if FAILS:
        raise SystemExit(f'test_pilot_routelib: {len(FAILS)} of {CHECKS[0]} checks FAILED')
    print(f'test_pilot_routelib: all {CHECKS[0]} checks passed')


if __name__ == '__main__':
    main()
