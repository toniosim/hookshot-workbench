"""Path planner on the game's own nav meshes, for the pilot's `walk` and `run` steps.

    import sys; sys.path.insert(0, '<the folder that holds worldmodel/>')
    from worldmodel import plan as wplan
    wplan.use('<data folder>')          # optional: else $PILOT_WORLD, else world/ beside worldmodel/
    r = wplan.plan('AreaA', (1.0, 2.0), (3.0, 4.0), from_y=5.0)

`plan(area, from_xz, to_xz, *, from_y=None, to_y=None, radius=1.0, doors='stop', max_drop=8.5)` returns a dict and
never raises for reasons of the game:
- `ok` True: `waypoints` [[x, z], ...] (the start left out, the goal last), `steps` the same as route lines
  (`run x z radius r`), `length` in metres, `source` 'navmesh', `legs` (walk/drop pieces with heights), `snap` how far
  the start and goal were moved onto walkable ground.
- `ok` False: `why` one of 'no-data', 'off-mesh', 'not-connected', 'needs-climb', 'needs-jump', 'needs-crawl',
  'needs-drop', 'needs-door' (needs-swim is never returned: water is not in the nav mesh); `detail` a sentence naming
  the obstacle; `near` [x, z] the reachable point to go to first (in front of the door, at the foot of a climbable, the
  edge to jump from; for 'off-mesh' the walkable point nearest the bad end; for 'not-connected' the reachable point
  nearest the goal); `waypoints`/`steps` lead to `near` when there is a way there; `after` names what lies beyond (the
  link's far end).
- always (once a way is found): `edges` the kinds of the way's pieces in order; `needed` every link the whole way
  uses, past the blocking one too, each with its kind, both ends `from`/`to` [x, y, z], height, gap, `allowed`, and the
  placed object it comes from (`actor`, `actor_pos`; a crawl also `other_pos`, its far marker); `gates` flag-gated
  walls and people on the way. 'not-connected' with a way: `unreached` {goal, nearest, distance, height,
  goal_piece_faces}: how far the reachable ground stops short of the goal and how much lower it is.
Walkable is the nav mesh the game's own characters use, eroded by its radius: the logged positions of a player lie on
it or within about 1 m of its edge where it presses against a wall or a door.
`available(area)` says without loading anything whether the area has data. From the folder that holds worldmodel/:
`python3 -m worldmodel.plan <area> <from x> <from z> <to x> <to z> [--from-y Y] [--to-y Y] [--doors through]`.
"""
import heapq
import json
import math
from pathlib import Path

from . import paths, tables

_data = None            # the data folder in use: use() sets it, else paths.data_dir() on first need
_cache = {}
_objects = None

# edge kinds between walkable pieces: walk (inside the mesh), drop (down a ledge: a walk or run step off it), climb-up /
# climb-down (a placed climbable: `climb up` is a pilot step, going down is not yet), ledge-up (onto a ledge 0.5 to
# 3 m higher: no step yet), jump (a gap at about the same level), crawl (a crawl space), swim (not in the data:
# water is not part of the nav mesh, so it is never returned)
PENALTY = {'drop': 2.0, 'jump': 8.0, 'ledge-up': 12.0, 'climb-up': 15.0, 'climb-down': 15.0, 'crawl': 10.0}
NEEDS = {'jump': 'needs-jump', 'ledge-up': 'needs-climb', 'climb-up': 'needs-climb', 'climb-down': 'needs-climb',
         'drop': 'needs-drop', 'crawl': 'needs-crawl'}


def use(data_dir=None, objects=None, areas=None):
    """Point the planner at a data folder (default: $PILOT_WORLD, else world/ beside worldmodel/) and forget every
    mesh and object list loaded so far. objects ({area: [object, ...]}, as objects.json) and areas ({area:
    navgraph.Area}) preload what a builder holds already; without them the planner reads objects.json and
    nav/<area>.json.gz from the folder."""
    global _data, _objects
    _data = Path(data_dir) if data_dir else None
    _cache.clear()
    _objects = objects
    if areas:
        _cache.update(areas)


def _dir():
    global _data
    if _data is None:
        _data = paths.data_dir()
    return _data


def available(area):
    return (_dir() / 'nav' / f'{area}.json.gz').is_file()


def _area(area):
    """The area's nav mesh, ready for queries; a pickle beside the mesh file keeps the second process's load short
    (a large area: seconds from the mesh, a fraction of that from the pickle)."""
    if area not in _cache:
        import pickle
        from .navgraph import Area
        src = _dir() / 'nav' / f'{area}.json.gz'
        pk = _dir() / 'nav' / f'{area}.pickle'
        a = None
        if pk.is_file() and pk.stat().st_mtime >= src.stat().st_mtime:
            try:
                a = pickle.loads(pk.read_bytes())
            except Exception:
                a = None
        if a is None:
            a = Area(area, path=src)
            try:
                tmp = pk.with_suffix('.tmp')
                tmp.write_bytes(pickle.dumps(a, protocol=pickle.HIGHEST_PROTOCOL))
                tmp.replace(pk)
            except OSError:
                pass
        _cache[area] = a
    return _cache[area]


def _doors(area):
    global _objects
    if _objects is None:
        p = _dir() / 'objects.json'
        _objects = json.loads(p.read_text()) if p.is_file() else {}
    return [o for o in _objects.get(area, []) if o.get('kind') == 'door']


def _door_tables():
    """(regex of the flag names named in a door's text, what to set to open it) from the tables file; (None, '')
    when there is no tables file (the door text then names the door's own flag only)."""
    try:
        T = tables.load(paths.tables_path(_dir()))
    except tables.TablesMissing:
        return None, ''
    return T.plan.door_flag_re, T.plan.door_open_hint


def _xz(p):
    return [round(p[0], 2), round(p[2], 2)]


def _funnel(start, goal, portals):
    """Simple stupid funnel over portals [(left, right)] in x-z; points are (x, y, z). Returns corner points."""
    def tri(a, b, c):
        return (c[0] - a[0]) * (b[2] - a[2]) - (b[0] - a[0]) * (c[2] - a[2])

    def eq(a, b):
        return abs(a[0] - b[0]) < 1e-6 and abs(a[2] - b[2]) < 1e-6
    pts = [(start, start)] + portals + [(goal, goal)]
    path = [start]
    apex, left, right = start, start, start
    ai = li = ri = 0
    i = 1
    while i < len(pts):
        l, r = pts[i]
        if tri(apex, right, r) <= 0.0:
            if eq(apex, right) or tri(apex, left, r) > 0.0:
                right, ri = r, i
            else:
                path.append(left)
                apex, ai = left, li
                left = right = apex
                li = ri = ai
                i = ai + 1
                continue
        if tri(apex, left, l) >= 0.0:
            if eq(apex, left) or tri(apex, right, l) < 0.0:
                left, li = l, i
            else:
                path.append(right)
                apex, ai = right, ri
                left = right = apex
                li = ri = ai
                i = ai + 1
                continue
        i += 1
    if not eq(path[-1], goal):
        path.append(goal)
    return path


def _search(A, starts, goals, allow):
    """A* over faces and the area's extra links from any start candidate [(face, point, snap)] to any goal candidate.
    Returns (chain [(face, came-from)], start point, goal point) or None."""
    links_from = {}
    for i, l in enumerate(A.xlinks):
        links_from.setdefault(l['a'], []).append(i)
    gface = {}
    for f, p, d in goals:
        if f not in gface or d < gface[f][1]:
            gface[f] = (p, d)
    gpts = [p for p, _d in gface.values()]

    def h(q):
        return min(math.dist((q[0], q[2]), (p[0], p[2])) for p in gpts)
    openq, came, gbest, spt = [], {}, {}, {}
    for f, p, d in starts:
        g0 = d * 2.0
        if g0 < gbest.get(f, 1e18):
            gbest[f] = g0
            came[f] = None
            spt[f] = p
            heapq.heappush(openq, (g0 + h(p), g0, f, p))
    while openq:
        _f, g, f, p = heapq.heappop(openq)
        if g > gbest.get(f, 1e18) + 1e-9:
            continue
        if f in gface:
            out = []
            node = f
            while True:
                prev = came[node]
                out.append((node, prev))
                if prev is None:
                    break
                node = prev[0]
            out.reverse()
            return out, spt[out[0][0]], gface[f][0]
        for o, a, b in A.nbr[f]:
            q = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)
            ng = g + math.dist((p[0], p[2]), (q[0], q[2])) + abs(q[1] - p[1]) * 0.5
            if ng < gbest.get(o, 1e18):
                gbest[o] = ng
                came[o] = (f, 'walk', a, b, None)
                heapq.heappush(openq, (ng + h(q), ng, o, q))
        for li in links_from.get(f, ()):
            l = A.xlinks[li]
            kind = l['kind']
            pen = PENALTY.get(kind, 20.0) * (1 if allow(l) else 50)
            pa, pb = tuple(l['pa']), tuple(l['pb'])
            ng = g + math.dist((p[0], p[2]), (pa[0], pa[2])) + math.dist((pa[0], pa[2]), (pb[0], pb[2])) + pen
            o = l['b']
            if ng < gbest.get(o, 1e18):
                gbest[o] = ng
                came[o] = (f, kind, pa, pb, l)
                heapq.heappush(openq, (ng + h(pb), ng, o, pb))
    return None


def _legs(A, chain, ps, pg):
    """Turn the face chain into legs: walk legs (funnelled corners) and link legs."""
    legs, portals, cur_start = [], [], ps
    for idx in range(1, len(chain)):
        face, prev = chain[idx]
        pf, kind, a, b, link = prev
        if kind == 'walk':
            ca = A.cen[pf]
            # order (left, right) as seen when leaving the previous face
            if (a[0] - ca[0]) * (b[2] - ca[2]) - (a[2] - ca[2]) * (b[0] - ca[0]) > 0:
                portals.append((b, a))
            else:
                portals.append((a, b))
        else:
            legs.append({'kind': 'walk', 'points': _funnel(cur_start, a, portals)})
            legs.append({'kind': kind, 'from': a, 'to': b, 'link': link})
            portals, cur_start = [], b
    legs.append({'kind': 'walk', 'points': _funnel(cur_start, pg, portals)})
    return legs


def _door_on(points, doors, reach=1.3, skip_start=1.5):
    """The first door whose place lies within reach of a walk leg: (index of the segment, door, point before it).
    A door within skip_start of the leg's start is the one the player stands in (opened already) and is passed. Of doors
    placed at one spot (an open and a closed model), the one the data ties to a flag is named."""
    s0 = points[0]
    for i in range(1, len(points)):
        a, b = points[i - 1], points[i]
        best = None
        for d in doors:
            x, y, z = d['pos']
            if min(a[1], b[1]) - 3.0 > y or max(a[1], b[1]) + 1.0 < y:
                continue
            if math.hypot(x - s0[0], z - s0[2]) <= skip_start:
                continue
            dx, dz = b[0] - a[0], b[2] - a[2]
            L = dx * dx + dz * dz
            t = 0.0 if L == 0 else max(0.0, min(1.0, ((x - a[0]) * dx + (z - a[2]) * dz) / L))
            cx, cz = a[0] + t * dx, a[2] + t * dz
            dist = math.hypot(x - cx, z - cz)
            if dist <= reach:
                key = (round(t, 1), 0 if d.get('flags') else 1)
                if best is None or key < best[0]:
                    seg = math.sqrt(L) or 1.0
                    back = max(0.0, t - 1.5 / seg)
                    best = (key, d, (a[0] + back * dx, a[1], a[2] + back * dz))
        if best:
            return i, best[1], best[2]
    return None


def _steps(wps, radius):
    out = []
    for i, (x, z) in enumerate(wps):
        r = radius if i == len(wps) - 1 else max(1.0, radius)
        out.append(f'run {x:.2f} {z:.2f} radius {r:g}')
    return out


def _thin(points, min_gap=0.75):
    out = []
    for p in points:
        if out and math.hypot(p[0] - out[-1][0], p[2] - out[-1][2]) < min_gap:
            out[-1] = p
            continue
        out.append(p)
    return out


def plan(area, from_xz, to_xz, *, from_y=None, to_y=None, radius=1.0, doors='stop', max_drop=8.5, snap=2.0,
         allow=('walk', 'drop')):
    res = {'ok': False, 'area': area, 'source': 'navmesh', 'waypoints': [], 'steps': [], 'length': 0.0,
           'why': None, 'detail': '', 'near': None, 'legs': []}
    if not available(area):
        res.update(source='straight', why='no-data', detail=f'no nav mesh for {area} (in {_dir() / "nav"})')
        return res
    A = _area(area)
    # the player's own position: never a floor more than 1 m above the feet (a ledge stood under)
    starts = A.candidates(from_xz[0], from_xz[1], from_y, snap=snap, above=1.0)
    if not starts:
        n = A.nearest(from_xz[0], from_xz[1], from_y, radius=25.0, dy=6.0)
        res.update(why='off-mesh', detail=f'start {from_xz} is not on walkable ground (more than {snap} m from it)',
                   near=_xz(n[2]) if n else None)
        return res
    goals = A.candidates(to_xz[0], to_xz[1], to_y, snap=snap)
    if not goals:
        n = A.nearest(to_xz[0], to_xz[1], to_y, radius=25.0, dy=6.0)
        res.update(why='off-mesh', detail=f'goal {to_xz} is not on walkable ground (more than {snap} m from it)',
                   near=_xz(n[2]) if n else None)
        return res

    allowed = set(allow)

    def link_ok(link):
        if link['kind'] not in allowed:
            return False
        return link['kind'] != 'drop' or -link['height'] <= max_drop

    found = _search(A, starts, goals, link_ok)
    unreached = None
    if found is None:
        # no way to the goal by any link kind: plan to the reachable place nearest the goal instead, so the answer
        # still names every link the way needs up to there (a crawl with its two ends, a climb...) and what is left
        pg0 = goals[0][1]
        near = _nearest_reachable(A, starts, pg0)
        if near is None:
            ps = starts[0][1]
            res.update(why='not-connected', detail=f'no walkable way, nor a known drop, jump, ledge, climb or crawl, from '
                       f'{_xz(ps)} (y {ps[1]:.1f}) to {_xz(pg0)} (y {pg0[1]:.1f}) in the nav mesh')
            return res
        nf, npt = near
        found = _search(A, starts, [(nf, npt, 0.0)], link_ok)
        if found is None:
            res.update(why='not-connected', detail='internal: the nearest reachable place could not be planned to')
            return res
        gc = A.comp[goals[0][0]]
        unreached = {'goal': [round(c, 2) for c in pg0], 'nearest': [round(c, 2) for c in npt],
                     'distance': round(math.dist((npt[0], npt[2]), (pg0[0], pg0[2])), 2),
                     'height': round(pg0[1] - npt[1], 2), 'goal_piece_faces': A.comp_size[gc]}
    chain, ps, pg = found
    res['snap'] = {'start': round(math.hypot(ps[0] - from_xz[0], ps[2] - from_xz[1]), 2),
                   'goal': round(math.hypot(pg[0] - to_xz[0], pg[2] - to_xz[1]), 2),
                   'start_y': round(ps[1], 2), 'goal_y': round(pg[1], 2)}
    legs = _legs(A, chain, ps, pg)
    door_list = _doors(area) if doors == 'stop' else []
    wps, length, blocked = [], 0.0, None
    prev = ps
    for leg in legs:
        if leg['kind'] == 'walk':
            pts = _thin(leg['points'])
            hit = _door_on(pts, door_list) if door_list else None
            if hit:
                i, d, before = hit
                pts = pts[:i] + [before]
                blocked = ('needs-door', d, before)
            for p in pts[1:]:
                if wps and math.hypot(p[0] - wps[-1][0], p[2] - wps[-1][2]) < 0.3:
                    continue
                length += math.dist((prev[0], prev[2]), (p[0], p[2]))
                wps.append(p)
                prev = p
            if blocked:
                break
        else:
            l = leg['link']
            if not link_ok(l):
                blocked = (NEEDS.get(l['kind'], 'needs-climb'), l, leg['from'])
                break
            for p in (leg['from'], leg['to']):
                if math.hypot(p[0] - prev[0], p[2] - prev[2]) > 0.3:
                    length += math.dist((prev[0], prev[2]), (p[0], p[2]))
                    wps.append(p)
                    prev = p
    res['legs'] = [{'kind': lg['kind'], **({'points': [[round(c, 2) for c in p] for p in lg['points']]}
                                            if lg['kind'] == 'walk' else
                                            {'from': [round(c, 2) for c in lg['from']], 'to': [round(c, 2) for c in lg['to']],
                                             'height': lg['link']['height'], 'actor': lg['link'].get('actor')})}
                   for lg in legs]
    # the kinds of edge the whole way uses, in order (walk legs collapsed), so a caller can tell what each piece needs
    res['edges'] = [lg['kind'] for lg in legs if lg['kind'] != 'walk' or len(lg['points']) > 1]
    # every link the whole way needs, past a blocking one too, with both ends: what a route must do there
    res['needed'] = []
    for lg in legs:
        if lg['kind'] == 'walk':
            continue
        l = lg['link']
        nd = {'kind': l['kind'], 'from': [round(c, 2) for c in l['pa']], 'to': [round(c, 2) for c in l['pb']],
              'height': l['height'], 'gap': l.get('gap'), 'allowed': link_ok(l)}
        for k in ('actor', 'actor_pos', 'other_pos'):
            if l.get(k) is not None:
                nd[k] = l[k]
        res['needed'].append(nd)
    if unreached:
        res['unreached'] = unreached
    res['waypoints'] = [_xz(p) for p in wps]
    res['length'] = round(length, 1)
    # walls and people that exist only under a flag and stand on the way: reported, not avoided,
    # since whether they are there depends on the save
    _doors(area)
    pts = [(ps[0], ps[2])] + [(p[0], p[2]) for p in wps]
    res['gates'] = []
    for o in _objects.get(area, []):
        pr = (o.get('flags') or {}).get('presence')
        if not pr or o['kind'] not in ('blocker', 'person'):
            continue
        reach = 1.5 + (max(o.get('scale') or [1, 1, 1]) if o['kind'] == 'blocker' else 0.5)
        x, _y, z = o['pos']
        for i in range(1, len(pts)):
            (ax, az), (bx, bz) = pts[i - 1], pts[i]
            dx, dz = bx - ax, bz - az
            L = dx * dx + dz * dz
            t = 0.0 if L == 0 else max(0.0, min(1.0, ((x - ax) * dx + (z - az) * dz) / L))
            if math.hypot(x - ax - t * dx, z - az - t * dz) <= reach:
                res['gates'].append({'object': o['gyaml'], 'pos': o['pos'], 'flag': pr['flag'],
                                     'present_when': f"{pr['flag']} is {'false' if pr.get('negated') else 'true'}"})
                break
    res['steps'] = _steps(res['waypoints'], radius)
    if blocked:
        why, what, at = blocked
        res['why'] = why
        res['near'] = _xz(at)
        if why == 'needs-door':
            fl = what.get('flags') or {}
            named = [fl['self']] if fl.get('self') else []
            rx, hint = _door_tables()
            named += [f for f in fl.get('logic', []) if rx and rx.search(f)]
            res['detail'] = (f"a door on the way: {what['gyaml']} at {[round(v, 1) for v in what['pos']]}"
                             + (f"; flags the data ties to it: {', '.join(named)}" if named else '')
                             + '; open it (walk into it facing it' + (f', until {hint}' if hint else '')
                             + ', press A), then plan on with doors=\'through\' or from beyond it')
            res['door'] = {'gyaml': what['gyaml'], 'pos': what['pos'], 'flags': named}
            res['after'] = [round(what['pos'][0], 2), round(what['pos'][2], 2)]
        else:
            k = what['kind']
            res['edge'] = k
            res['detail'] = (f"the way needs a {k} of {abs(what['height']):.1f} m"
                             + (f" (gap {what['gap']:.1f} m)" if k in ('jump', 'crawl') else '')
                             + (f" at {what['actor']} {what['actor_pos']}" if what.get('actor') else '')
                             + f" from {_xz(what['pa'])} (y {what['pa'][1]:.1f}) to {_xz(what['pb'])} (y {what['pb'][1]:.1f})"
                             + ('; the pilot has `climb up`' if k == 'climb-up' else
                                '; no pilot step for it yet' if k in ('climb-down', 'ledge-up', 'jump', 'crawl') else ''))
            res['after'] = _xz(what['pb'])
        if unreached:
            res['detail'] += (f"; beyond that the goal itself is not reached by any known link either (nearest reachable "
                              f"point {unreached['distance']} m from it, {unreached['height']:+.1f} m)")
        return res
    if unreached:
        u = unreached
        res['why'] = 'not-connected'
        res['near'] = _xz(u['nearest'])
        links_txt = '; '.join(f"{n['kind']} from {_xz(n['from'])} (y {n['from'][1]:.1f}) to {_xz(n['to'])} (y "
                              f"{n['to'][1]:.1f})" + (f" at {n['actor']} {n['actor_pos']}" if n.get('actor') else '')
                              for n in res['needed'])
        res['detail'] = (f"the goal {_xz(u['goal'])} (y {u['goal'][1]:.1f}, a walkable piece of {u['goal_piece_faces']} "
                         f"polygons) is reached by no known link; the way goes as far as {_xz(u['nearest'])} (y "
                         f"{u['nearest'][1]:.1f}), {u['distance']} m from it and {u['height']:+.1f} m"
                         + (f" below it: a step up higher than the ledge probe's 3 m, or a way the nav mesh lacks"
                            if u['height'] > 3.0 else '')
                         + (f"; links on the way there: {links_txt}" if links_txt else ''))
        return res
    res['ok'] = True
    return res


def _nearest_reachable(A, starts, goal):
    """(face, point) of the place nearest the goal (x-z distance plus half the height difference) that is reachable
    from a start by walking and by links of any kind; None when nothing is reachable."""
    from .navgraph import seg_closest
    seen = set()
    stack = [f for f, _p, _d in starts]
    links_from = {}
    for l in A.xlinks:
        links_from.setdefault(l['a'], []).append(l['b'])
    while stack:
        f = stack.pop()
        if f in seen:
            continue
        seen.add(f)
        for o, _a, _b in A.nbr[f]:
            if o not in seen:
                stack.append(o)
        for o in links_from.get(f, ()):
            if o not in seen:
                stack.append(o)
    best = None
    gx, gy, gz = goal
    for f in seen:
        poly = A.F[f]
        if A.inside(f, gx, gz):
            d, px, pz = 0.0, gx, gz
        else:
            d, px, pz = 1e9, gx, gz
            n = len(poly)
            for k in range(n):
                a, b = A.V[poly[k]], A.V[poly[(k + 1) % n]]
                dd, qx, qz, _t = seg_closest(gx, gz, a[0], a[2], b[0], b[2])
                if dd < d:
                    d, px, pz = dd, qx, qz
        py = A.height(f, px, pz)
        key = d + abs(py - gy) * 0.5
        if best is None or key < best[0]:
            best = (key, f, (px, py, pz))
    return (best[1], best[2]) if best else None


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='plan a walk on the game\'s nav mesh')
    ap.add_argument('area')
    ap.add_argument('fx', type=float)
    ap.add_argument('fz', type=float)
    ap.add_argument('tx', type=float)
    ap.add_argument('tz', type=float)
    ap.add_argument('--from-y', type=float)
    ap.add_argument('--to-y', type=float)
    ap.add_argument('--doors', default='stop', choices=['stop', 'through'])
    a = ap.parse_args()
    r = plan(a.area, (a.fx, a.fz), (a.tx, a.tz), from_y=a.from_y, to_y=a.to_y, doors=a.doors)
    r.pop('legs', None)
    print(json.dumps(r, indent=1))
