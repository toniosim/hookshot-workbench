#!/usr/bin/env python3
"""routes: the route library's command line (routelib.py). Game-derived data stays in the library folder ($ROUTELIB_DIR, else <harness>/routelib).

    routes.py import RUN... [--build B]            read finished runs (a folder with state.jsonl, or its pilot/live): tracks, stuck points, links, frontier
    routes.py import-tree DIR...                   every folder under DIR that holds a state.jsonl (a run imported once, whatever the folder)
    routes.py show [MAP]                           per map what is known: metres, verified edges, stuck clusters with causes, links, targets
    routes.py target add NAME --map M --at X Z [--y Y] [--age A] [--radius R] [--issue N] [--label T]
    routes.py target cover NAME --map M --from-steps steps.txt [--radius R] [--issue N]   the legs of a run as points to cover
    routes.py target list | remove NAME
    routes.py frontier NAME [--json]               the walked point nearest the target and how far it is
    routes.py route MAP --from X Y Z --to X Z      the library's way to the frontier, then the world model's plan beyond it (--world)
    routes.py backfill                             hearts lost at old stuck points, read from the runs' journals
    routes.py report                               what each run added (metres, new edges, frontier gain) and the targets' history
Hold subcommands (plan, check, saves, run, queue) are frontier.py's.
"""
import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import routelib  # noqa: E402

H = Path(os.environ.get('HS_HARNESS', str(HERE.parent.parent)))
DEFAULT_LIB = Path(os.environ.get('ROUTELIB_DIR') or H / 'routelib')


def world_of(a):
    w = a.world or os.environ.get('ROUTELIB_WORLD')
    return routelib.PrivateWorld(w) if w else None


def fmt_import(st):
    if st.get('skipped'):
        return f'{st["run"]}: {st["skipped"]}'
    gain = st.get('frontier_gain') or {}
    return (f'{st["run"]} build {st["build"]}: maps {", ".join(st["maps"])} | {st["metres"]} m of track | {st["new_nodes"]} new nodes, {st["new_edges"]} new edges '
            f'({st["new_two_way"]} now both ways) | {st["stuck"]} stuck steps, {st["new_clusters"]} new clusters | {st["links"]} links'
            + (f' | frontier gain {gain}' if gain else '') + (f' | first frontier {st["frontier_new"]}' if st.get('frontier_new') else ''))


def cmd_import(a):
    lib, world, rc = routelib.RouteLib(a.lib), world_of(a), 0
    for run in a.runs:
        try:
            print(fmt_import(lib.import_run(run, build=a.build, label=a.label, world=world)))
        except routelib.LibError as e:
            print(f'{run}: {e}', file=sys.stderr)
            rc = 2
    return rc


def find_runs(root):
    out = []
    for d, _dirs, files in os.walk(root):
        if 'state.jsonl' in files:
            out.append(Path(d))
    return sorted(out)


def cmd_import_tree(a):
    lib, world = routelib.RouteLib(a.lib), world_of(a)
    imported = skipped = 0
    runs = sorted({d for root in a.dirs for d in find_runs(root)}, key=lambda d: ((d / 'state.jsonl').stat().st_mtime, str(d)))   # (oldest first: the library's builds and 'what a run added' follow the order the runs were played)
    import time
    if True:
        for d in runs:
            if time.time() - (d / 'state.jsonl').stat().st_mtime < a.min_age:
                print(f'skipped {d}: still being written (modified under {a.min_age:g} s ago)')
                skipped += 1
                continue
            try:
                st = lib.import_run(d, build=a.build, world=world)
            except Exception as e:   # noqa: BLE001  (a run folder in an unknown layout is skipped, and said so)
                print(f'skipped {d}: {e}')
                skipped += 1
                continue
            if st.get('skipped'):
                skipped += 1
                continue
            imported += 1
            print(fmt_import(st))
    print(f'imported {imported}, skipped {skipped}')
    return 0


def cmd_show(a):
    lib = routelib.RouteLib(a.lib)
    if a.map and a.map not in lib.maps():
        print(f'no data for {a.map} in {lib.root}', file=sys.stderr)
        return 2
    print(routelib.describe(lib, [a.map] if a.map else None))
    return 0


def cmd_target(a):
    lib = routelib.RouteLib(a.lib)
    if a.action == 'add':
        lib.add_target(a.name, a.map, a.at[0], a.at[1], age=a.age, y=a.y, radius=a.radius, issue=a.issue, label=a.label)
        print(f'target {a.name}: {a.map} at {a.at}')
    elif a.action == 'cover':
        pts, seen = [], set()
        for ln in Path(a.from_steps).read_text().splitlines():
            w = ln.split('#', 1)[0].split()
            if len(w) >= 3 and w[0] in ('run', 'walk'):
                p = (round(float(w[1]), 2), round(float(w[2]), 2))
                if p not in seen:
                    seen.add(p)
                    pts.append(list(p))
        lib.add_cover(a.name, a.map, pts, radius=a.radius, issue=a.issue, label=a.label)
        print(f'target {a.name}: {len(pts)} legs on {a.map}')
    elif a.action == 'remove':
        with lib.locked():
            doc = lib._targets_doc()
            doc['targets'].pop(a.name, None)
            routelib._atomic(lib.root / 'targets.json', doc)
    else:
        for name, t in sorted(lib.targets().items()):
            f = lib._frontier_of(t)
            if not f['known']:
                print(f'{name}: {t["map"]} (issue {t.get("issue")}) no frontier yet')
            elif t['kind'] == 'cover':
                print(f'{name}: {t["map"]} (issue {t.get("issue")}) {f["reached_n"]} of {f["n"]} legs reached; frontier {f.get("pos")}')
            else:
                print(f'{name}: {t["map"]} (issue {t.get("issue")}) frontier {f["pos"]}, {f["remaining_m"]} m from the point' + (' (reached)' if f['reached'] else ''))
    return 0


def cmd_frontier(a):
    lib = routelib.RouteLib(a.lib)
    try:
        f = lib.frontier(a.name)
    except routelib.LibError as e:
        print(e, file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(f, indent=1, default=str))
    else:
        print(f'{a.name}: ' + (f'frontier {f["pos"]}, {f["remaining_m"]} m from the point' if f['known'] and f['kind'] == 'point' else str(f)))
    return 0


def cmd_route(a):
    lib, world = routelib.RouteLib(a.lib), world_of(a)
    r = lib.route(a.map, a.start, a.to, age=a.age, radius=a.radius, world=world)
    if a.json:
        print(json.dumps(r, indent=1, default=str))
        return 0
    print(f'{a.map}: source {r["source"]}, {"complete" if r["complete"] else "not complete"}, known {r["known_m"]} m, beyond {r["beyond_m"]} m' + (f', why {r["why"]}: {r["detail"]}' if r['why'] else ''))
    if r['frontier']:
        print(f'frontier {r["frontier"]["pos"]}, {r["frontier"]["remaining_m"]} m from the goal')
    for s in r['steps']:
        print(s)
    return 0 if (r['steps'] or r['ok']) else 2


def cmd_backfill(a):
    print(f'{routelib.RouteLib(a.lib).backfill_life()} stuck records filled')
    return 0


def cmd_report(a):
    lib = routelib.RouteLib(a.lib)
    led = lib.runs()
    lines = ['| run | build | maps | metres | new nodes | new edges (now both ways) | stuck steps | new clusters | frontier gain |', '|---|---|---|---|---|---|---|---|---|']
    for r in led['runs']:
        lines.append(f'| {r["run"]} | {r["build"]} | {", ".join(r["maps"])} | {r["metres"]} | {r["new_nodes"]} | {r["new_edges"]} ({r["new_two_way"]}) | {r["stuck"]} | {r["new_clusters"]} | {r.get("frontier_gain") or ""} |')
    lines += ['', '| target | map | issue | row | remaining m | position |', '|---|---|---|---|---|---|']
    for name, t in sorted(lib.targets().items()):
        for h in t['history']:
            lines.append(f'| {name} | {t["map"]} | {t.get("issue")} | {h["run"]} | {h.get("remaining_m")}{(" (" + str(h["reached_n"]) + " of " + str(h["n"]) + " legs)") if "reached_n" in h else ""} | {h.get("pos")} |')
    print('\n'.join(lines))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--lib', default=str(DEFAULT_LIB))
    ap.add_argument('--world', help='the private world/ folder (stuck causes, the planner beyond the library); else $ROUTELIB_WORLD')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('import')
    p.add_argument('runs', nargs='+')
    p.add_argument('--build')
    p.add_argument('--label')
    p.set_defaults(fn=cmd_import)
    p = sub.add_parser('import-tree')
    p.add_argument('dirs', nargs='+')
    p.add_argument('--build')
    p.add_argument('--min-age', dest='min_age', type=float, default=120.0, help='leave a run whose state.jsonl changed this many seconds ago (a game still writing it)')
    p.set_defaults(fn=cmd_import_tree)
    p = sub.add_parser('show')
    p.add_argument('map', nargs='?')
    p.set_defaults(fn=cmd_show)
    p = sub.add_parser('target')
    p.add_argument('action', choices=('add', 'cover', 'list', 'remove'))
    p.add_argument('name', nargs='?')
    p.add_argument('--map')
    p.add_argument('--at', nargs=2, type=float, metavar=('X', 'Z'))
    p.add_argument('--y', type=float)
    p.add_argument('--age')
    p.add_argument('--radius', type=float, default=3.0)
    p.add_argument('--issue')
    p.add_argument('--label')
    p.add_argument('--from-steps', dest='from_steps')
    p.set_defaults(fn=cmd_target)
    p = sub.add_parser('frontier')
    p.add_argument('name')
    p.add_argument('--json', action='store_true')
    p.set_defaults(fn=cmd_frontier)
    p = sub.add_parser('route')
    p.add_argument('map')
    p.add_argument('--from', dest='start', nargs=3, type=float, required=True, metavar=('X', 'Y', 'Z'))
    p.add_argument('--to', nargs=2, type=float, required=True, metavar=('X', 'Z'))
    p.add_argument('--age')
    p.add_argument('--radius', type=float, default=2.5)
    p.add_argument('--json', action='store_true')
    p.set_defaults(fn=cmd_route)
    p = sub.add_parser('backfill')
    p.set_defaults(fn=cmd_backfill)
    p = sub.add_parser('report')
    p.set_defaults(fn=cmd_report)
    a = ap.parse_args(argv)
    if a.cmd == 'target' and a.action in ('add', 'cover') and not (a.name and a.map and (a.at if a.action == 'add' else a.from_steps)):
        ap.error('target add needs NAME --map --at X Z; target cover needs NAME --map --from-steps FILE')
    if a.cmd == 'target' and a.action == 'remove' and not a.name:
        ap.error('target remove needs a NAME')
    return a.fn(a)


if __name__ == '__main__':
    raise SystemExit(main())
