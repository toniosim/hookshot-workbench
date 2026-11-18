#!/usr/bin/env python3
"""routelib: the route library. What every run learned about where Link can walk, kept per map so that the next run starts from the farthest
known point: tracks (state-tap positions with time, map, age and the step that moved Link), verified edges between points (walked once or both
ways), stuck points with a cause, attempts made at them, map-to-map links actually crossed, targets and their frontier (the walked point nearest
the place an issue names). Standard library only (and the harness's hs_names for the game's own file names); reads a finished run's state.jsonl / out.jsonl / steps.txt / placement.json and never a game.

    lib = RouteLib('/path/to/routelib')
    lib.import_run('<run folder>', world=PrivateWorld(...))      # tracks, stuck points, links, anchors, the targets' frontier
    lib.add_target('issue-817', 'SomeMap_Adult', x, z, age='adult')
    lib.frontier('issue-817')                                     # {'known', 'pos', 'remaining_m', 'reached', 'anchor', ...}
    lib.route('SomeMap_Adult', (x, y, z), (gx, gz), world=w)      # the library's way to the frontier, then the world model's plan beyond it
    Walker(lib, io, map=...).go((gx, gz))                          # closed loop: legs re-aimed from the live position, re-plan on drift

The merge rules, the data layout and the cause rules are in reports/PathLib.md (section 1). Game-derived data (coordinates, map names) lives only in
the library folder, which is private; nothing here names a place. Tests: test_routelib.py (python3 -I -B).
"""
import contextlib
import fcntl
import hashlib
import heapq
import json
import math
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
_H = HERE.parent.parent   # the harness folder (in a checkout of the workbench repository its root: hs_names.py sits in harness/ there), as pilot.py finds it
sys.path.insert(0, str(_H if (_H / 'hs_names.py').is_file() else _H / 'harness'))
import hs_names  # noqa: E402  (the game's log file names and its version line: one copy)

FORMAT = 'ls-routelib/1'
MIN_PT = 0.6           # a track keeps a point per 0.6 m moved (and the first and last point of every step)
JUMP_BASE, JUMP_SPEED, JUMP_VERT = 6.0, 10.0, 12.0   # a sample farther than 6 m + 10 m/s * dt (or 12 m up or down) from the one before is a warp, not a walk
GAP_MAX = 4.0          # no edge across a gap in the samples wider than this
SNAP_XZ, SNAP_Y = 1.0, 0.8     # a point within 1.0 m (x-z) and 0.8 m (height) of a node is that node
JOIN_D, JOIN_DY = 2.0, 0.5     # nodes of different tracks this near are joined (a route may use the join; it is not a verified edge)
VERT = 1.2             # an edge whose ends differ by this much in height is a drop, an up or a climb
CLUSTER_R = 2.0        # stuck points within 2 m are one cluster
PASSED_R = 1.5
MOVE_VERBS = ('walk', 'run', 'enter', 'pickup', 'approach', 'climb', 'stick', 'push', 'raw', 'until')
STUCK_RESULTS = ('stuck', 'blocked', 'held', 'timeout')
STUCK_VERBS = ('walk', 'run', 'enter', 'pickup', 'climb')
CAUSES = ('held', 'door-side', 'npc-crowd', 'ledge-up', 'drop-not-taken', 'wall', 'slow')
COST_STUCK, COST_AVOID = 40.0, 200.0
LEG_M = 12.0           # no leg of a route is longer than this: the walker looks at where Link is after each


class LibError(Exception):
    pass


# ------------------------------------------------------------------------------------------------------------------------ small helpers

def d2(a, b):
    return math.hypot(a[0] - b[0], a[2] - b[2])


def d2xz(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def r1(v):
    return round(float(v), 2)


def routelib_base(name):
    return re.sub(r'_(Child|Adult)(_Alternative)?$', '', name)


def age_of_map(name):
    if name.endswith('_Adult') or '_Adult_' in name:
        return 'adult'
    if name.endswith('_Child') or '_Child_' in name:
        return 'child'
    return None


def seg_dist(p, a, b):
    """(distance, t) of x-z point p to the segment a-b (x, z pairs)."""
    dx, dz = b[0] - a[0], b[1] - a[1]
    L = dx * dx + dz * dz
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / L))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dz), t


def now_iso():
    return time.strftime('%Y-%m-%dT%H:%M:%S')


def _safe(name):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', str(name)) or str(name).startswith('.'):
        raise LibError(f'a map or target name is letters, digits and _.- (got {name!r})')
    return str(name)


def _atomic(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(obj, separators=(',', ':')))
    os.replace(tmp, path)


# ------------------------------------------------------------------------------------------------------------------------ reading a run

def _jsonl(path):
    rows = []
    try:
        with open(path, errors='replace') as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    pass
    except OSError:
        pass
    return rows


def find_run_files(folder):
    """The folder that holds state.jsonl (the folder itself, its pilot/live or live)."""
    folder = Path(folder)
    for sub in ('', 'pilot/live', 'live'):
        d = folder / sub if sub else folder
        if (d / 'state.jsonl').is_file():
            return d
    raise LibError(f'{folder}: no state.jsonl (looked in ., pilot/live and live)')


def _normalise(r):
    """A state row of the bridge driver's journal as it is; a co-op observer's row ({w, frame, game: {t, map, pos, age, event, loading ...}}) in the same shape."""
    g = r.get('game')
    if isinstance(g, dict) and 'pos' not in r:
        r = dict(g, child=1 if g.get('age') == 'child' else 0 if g.get('age') == 'adult' else None, event=int(bool(g.get('event'))), loading=int(bool(g.get('loading'))))
    return r


BUILD_RE = hs_names.LOG_VERSION   # the log's first line is `<project> vX-N-gSHA (source S)`: group 1 is the version
LOG_NAMES = tuple(hs_names.Names(p).log for p in hs_names.PROJECTS)


def detect_build(live, out_rows):
    """The build id of a run: the version's git hash from the game's log ('<project> v3.0.0-rc.4-416-g63ddacdc9 (source ..)'), else the copy's
    built-from.txt (first 9 hex digits), else None."""
    live = Path(live)
    cands = [live.parent.parent / 'game', live.parent / 'game', live / 'game', live.parent.parent.parent / 'game']
    copy = tag = None
    for r in out_rows[:5]:
        m = re.search(r'hs-run\.sh (\S+) (\S+) \d+', r.get('text', '') or '') if r.get('ev') == 'note' else None
        if m:
            copy, tag = m.group(1), m.group(2)
            break
    if copy and tag:
        cands.append(Path(copy) / 'runs' / tag)
    for d in cands:
        for name in LOG_NAMES:
            try:
                with open(d / name, errors='replace') as f:
                    head = f.read(4000)
            except OSError:
                continue
            m = BUILD_RE.search(head)
            if m:
                g = re.search(r'-g([0-9a-f]+)$', m.group(1))
                return ('g' + g.group(1)) if g else m.group(1)
    if copy:
        try:
            sha = (Path(copy) / 'built-from.txt').read_text().split()[0]
            return sha[:9]
        except (OSError, IndexError):
            pass
    return None


def parse_want(src):
    """(verb, want [x, z] or None, radius or None) of an hsap step line."""
    w = (src or '').split('#', 1)[0].split()
    if not w:
        return '', None, None
    verb = w[0]
    want = rad = None
    if verb in ('walk', 'run', 'enter', 'pickup') and len(w) >= 3:
        try:
            want = [float(w[1]), float(w[2])]
        except ValueError:
            want = None
    if 'radius' in w:
        try:
            rad = float(w[w.index('radius') + 1])
        except (ValueError, IndexError):
            rad = None
    return verb, want, rad


class RunData:
    """A run folder read: state rows with game seconds, steps with windows, the placement, the start save."""

    def __init__(self, folder, label=None):
        self.live = find_run_files(folder)
        self.folder = Path(folder)
        self.state = [r for r in map(_normalise, _jsonl(self.live / 'state.jsonl')) if r.get('map') and isinstance(r.get('pos'), list) and len(r['pos']) == 3 and r.get('t') is not None]
        self.out = _jsonl(self.live / 'out.jsonl')
        if not self.state:
            raise LibError(f'{self.live}: state.jsonl has no position samples')
        try:
            self.placement = json.loads((self.live / 'placement.json').read_text())
        except (OSError, ValueError):
            self.placement = None
        tag = save = copy = None
        for r in self.out[:5]:
            if r.get('ev') == 'note':
                m = re.search(r'hs-run\.sh (\S+) (\S+) \d+(?: --user (\S+))?', r.get('text', '') or '')
                if m:
                    copy, tag, save = m.group(1), m.group(2), m.group(3)
                    break
        name = self.folder.name if self.folder.name not in ('live', 'pilot') else self.folder.parent.name
        if len(name) <= 2 and self.folder.parent.name:   # (a co-op observer's side folder is just `A` or `B`)
            name = f'{self.folder.parent.name}-{name}'
        self.tag, self.copy = label or tag or name, copy
        self.save = Path(save).name if save else None
        gp = next((r for r in self.out if r.get('ev') == 'gameplay'), None)
        t0 = None
        if gp and gp.get('frame') is not None:
            t0 = next((r['t'] for r in self.state if r.get('frame') == gp['frame']), None)
            if t0 is None:
                t0 = next((r['t'] for r in self.state if (r.get('frame') or 0) >= gp['frame']), None)
        self.t0 = t0 if t0 is not None else self.state[0]['t']
        self.rows = [r for r in self.state if r['t'] - self.t0 >= -0.05]
        h = hashlib.sha1(json.dumps(self.state[0], sort_keys=True).encode() + str(len(self.state)).encode()).hexdigest()[:6]
        self.run_id = f'{self.tag}-{h}'
        self.steps = []
        for e in self.out:
            if e.get('ev') == 'step' and e.get('t') is not None:
                verb, want, rad = parse_want(e.get('src'))
                end = float(e['t'])
                self.steps.append({'in': e.get('in'), 'verb': verb, 'result': e.get('result'), 't0': round(end - float(e.get('secs') or 0.0), 2), 't1': round(end, 2),
                                   'want': want, 'radius': rad, 'src': (e.get('src') or '')[:100], 'detail': e.get('detail') or '', 'moved': e.get('moved'), 'pos': e.get('pos')})
        try:
            self.ts = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime((self.live / 'state.jsonl').stat().st_mtime))
        except OSError:
            self.ts = now_iso()

    def step_at(self, ts, slack=(0.3, 0.15)):
        """The step that was running at game second ts (the latest started), or None."""
        best = None
        for s in self.steps:
            if s['t0'] - slack[0] <= ts <= s['t1'] + slack[1]:
                if best is None or s['t0'] >= best['t0']:
                    best = s
        return best


def make_tracks(rd, build, ts):
    """([tracks], [links], [stuck candidates]) of a RunData: points thinned, cut at a map change, a jump and a load; links from the map changes."""
    tracks, links, cur = [], [], None
    first_act = min((s['t0'] for s in rd.steps if s['verb'] not in ('watch', 'report', 'shot', 'end', 'save')), default=None)   # (the first step that does something: what came before is the harness's)
    prev = None            # the last row seen (loaded or not)
    loading_seen = False
    steps_kept = {}

    def new_track(row, origin, ts_):
        nonlocal cur
        age = 'child' if row.get('child') == 1 else 'adult' if row.get('child') == 0 else age_of_map(row['map'])
        cur = {'id': f'{rd.run_id}#{len(tracks)}', 'run': rd.run_id, 'build': build, 'age': age, 'origin': origin, 'ts': ts, 'map': row['map'],
               'save': rd.save, 'pts': [], 'steps': [], 'len_m': 0.0, '_last': None, '_n_rows': 0}
        tracks.append(cur)

    def keep(row, force=False):
        s = rd.step_at(row['t'] - rd.t0)
        sn = s['in'] if s else 0
        p = row['pos']
        last = cur['_last']
        if last is None or force or sn != last[4] or math.dist((p[0], p[1], p[2]), (last[1], last[2], last[3])) >= MIN_PT:
            pt = [round(row['t'] - rd.t0, 2), r1(p[0]), r1(p[1]), r1(p[2]), sn]
            if last is not None:
                cur['len_m'] += d2(pt[1:4], last[1:4]) if d2(pt[1:4], last[1:4]) <= GAP_MAX else 0.0
            cur['pts'].append(pt)
            cur['_last'] = pt
            cur.pop('_tail', None)
            if s and s['in'] not in steps_kept.setdefault(cur['id'], set()):
                steps_kept[cur['id']].add(s['in'])
        elif last is not None and last[0] != round(row['t'] - rd.t0, 2):
            cur['_tail'] = [round(row['t'] - rd.t0, 2), r1(p[0]), r1(p[1]), r1(p[2]), sn]

    for row in rd.rows:
        if row.get('loading'):
            loading_seen = True
            prev = row if prev is None else prev
            continue
        ts_ = row['t'] - rd.t0
        if cur is None:
            new_track(row, 'start', ts)
            keep(row, force=True)
            prev, loading_seen = row, False
            continue
        dt = max(0.0, row['t'] - prev['t'])
        p, q = row['pos'], prev['pos']
        horiz = math.hypot(p[0] - q[0], p[2] - q[2])
        changed = row['map'] != cur['map']
        jumped = horiz > JUMP_BASE + JUMP_SPEED * dt or abs(p[1] - q[1]) > JUMP_VERT + JUMP_SPEED * dt or (loading_seen and horiz > JUMP_BASE)
        if changed or jumped:
            _close(cur)
            step = rd.step_at(ts_, slack=(0.0, 0.15))   # (strictly inside it: a change just before a step began is not that step's)
            verb = step['verb'] if step else None
            origin, link_via = 'jump', None
            if changed:
                if verb in MOVE_VERBS and verb != 'until':
                    origin, link_via = 'arrival', 'walked'
                elif verb in ('cheat', 'teleport', 'warp'):
                    origin, link_via = 'warp', 'warp'
                elif rd.placement and rd.placement.get('ok') and rd.placement.get('to') == row['map'] and not any(t['origin'] == 'placed' for t in tracks):
                    origin = 'placed'
                elif routelib_base(cur['map']) == routelib_base(row['map']):
                    origin = 'jump'     # (an age switch: the harness's own)
                elif first_act is not None and ts_ >= first_act:
                    origin, link_via = 'arrival', 'event'   # (a step that does not walk was running: a text closed, a cutscene ended, the story moved Link)
                elif not rd.steps and (loading_seen or dt >= 1.5) and cur['len_m'] >= 30.0:   # (an observer's journal has no loading rows: a gap of 1.5 s or more is the load)
                    origin, link_via = 'arrival', 'seen'    # (a journal with no steps, a load after a real walk: Link went through a loading zone)
                else:
                    origin = 'jump'     # (before the first step, or a journal with no steps and no load: the harness's teleport, or unknown: no link)
            last = cur['_last'] or [0, q[0], q[1], q[2], 0]
            prev_map, prev_pos = cur['map'], [last[1], last[2], last[3]]
            new_track(row, origin, ts)
            keep(row, force=True)
            if link_via:
                links.append({'from_map': prev_map, 'from': prev_pos, 'to_map': row['map'], 'to': [r1(p[0]), r1(p[1]), r1(p[2])], 'via': link_via,
                              'step': step['src'] if step else None, 'count': 1, 'builds': [build], 'runs': [rd.run_id]})
        else:
            keep(row)
        prev, loading_seen = row, False
    if cur is not None:
        _close(cur)
    for t in tracks:
        t['steps'] = [{'in': s['in'], 'verb': s['verb'], 'result': s['result'], 't0': s['t0'], 't1': s['t1'], 'want': s['want'], 'src': s['src']}
                      for s in rd.steps if s['in'] in steps_kept.get(t['id'], ())]
        t['len_m'] = round(t['len_m'], 1)
        t.pop('_last', None)
        t.pop('_n_rows', None)
    tracks = [t for t in tracks if t['pts']]
    first_placed = next((i for i, t in enumerate(tracks) if t['origin'] == 'placed'), None)
    if first_placed:   # (the save's own place and the age switch before the debug teleport: Link stood still while the harness placed him)
        tracks = tracks[first_placed:]
    return tracks, links


def _close(cur):
    tail = cur.pop('_tail', None)
    if tail and cur['pts'] and cur['pts'][-1][0] != tail[0]:
        last = cur['pts'][-1]
        if d2(tail[1:4], last[1:4]) <= GAP_MAX:
            cur['len_m'] += d2(tail[1:4], last[1:4])
        cur['pts'].append(tail)


def map_at(rd, ts):
    """The map of the last state row at or before game second ts."""
    best = None
    for r in rd.rows:
        if r['t'] - rd.t0 <= ts + 0.05:
            best = r['map']
        else:
            break
    return best or rd.rows[0]['map']


# ------------------------------------------------------------------------------------------------------------------------ stuck causes

def classify_stuck(rec, world=None):
    """(cause, why) of a stuck record {verb, result, detail, at [x, y, z], want [x, z] or None, moved, map} (rules in reports/PathLib.md 1.2)."""
    res, verb, detail = rec.get('result'), rec.get('verb'), rec.get('detail') or ''
    at, want, mp = rec['at'], rec.get('want'), rec.get('map')
    if res == 'held':
        return 'held', 'an event holds Link (a text box or a scene)'
    dm = re.search(r'([0-9.]+) m from the point', detail)
    if verb == 'enter' and res == 'blocked' and (dm is None or float(dm.group(1)) <= 8.0):   # (blocked far from the door: the way to it was shut, not the door)
        return 'door-side', 'the enter step ended blocked: ' + (detail.split(';')[0] if detail else 'the way is shut')
    u = None
    if want:
        dx, dz = want[0] - at[0], want[1] - at[2]
        n = math.hypot(dx, dz)
        if n > 1e-3:
            u = (dx / n, dz / n)
    if world is not None and mp:
        doors = world.doors(mp, at[0], at[2], 2.6) if hasattr(world, 'doors') else []
        for dr in doors:
            if u is None or (dr[1] - at[0]) * u[0] + (dr[2] - at[2]) * u[1] >= -0.17 * max(1e-6, math.hypot(dr[1] - at[0], dr[2] - at[2])):
                return 'door-side', f'a door lies {math.hypot(dr[1] - at[0], dr[2] - at[2]):.1f} m from the stuck point on the way ({dr[3] if len(dr) > 3 else "door"})'
        near = world.persons(mp, at[0], at[2], 5.0) if hasattr(world, 'persons') else []
        close = [p for p in near if math.hypot(p[1] - at[0], p[2] - at[2]) <= 2.5]
        if close or len(near) >= 3:
            return 'npc-crowd', f'{len(close)} person object(s) within 2.5 m and {len(near)} within 5 m of the stuck point'
    if res == 'timeout' and (rec.get('moved') or 0) >= 3.0:
        return 'slow', f'the step ran out of time still moving ({rec.get("moved")} m)'
    if world is not None and mp and hasattr(world, 'props'):
        props = sorted(world.props(mp, at[0], at[2], 1.8), key=lambda o: math.hypot(o[1] - at[0], o[2] - at[2]))
        if props:
            o = props[0]
            return 'wall', f'a placed object lies {math.hypot(o[1] - at[0], o[2] - at[2]):.1f} m from the stuck point ({o[4]} {o[3]}): a prop or an invisible wall'
    if world is not None and mp and u is not None and hasattr(world, 'ground'):
        ahead = (at[0] + 1.5 * u[0], at[2] + 1.5 * u[1])
        g = world.ground(mp, ahead[0], ahead[1], at[1])
        if g is not None:
            dy = g - at[1]
            if dy >= 0.6:
                return 'ledge-up', f'the walkable ground 1.5 m ahead is {dy:.1f} m above Link: a ledge from below'
            if dy <= -1.5:
                return 'drop-not-taken', f'the walkable ground 1.5 m ahead is {-dy:.1f} m below Link: a drop that was not taken'
            return 'wall', 'walkable ground continues 1.5 m ahead at the same level and Link still stopped: a prop, an unmodelled wall or a person'
        return 'wall', 'no walkable ground 1.5 m ahead (the mesh ends): a wall or an edge'
    return 'wall', 'stopped with no event, no door and no person known: a wall or a prop'


def stuck_candidates(rd, tracks, build, world=None, ts=None):
    out = []
    for s in rd.steps:
        if s['result'] not in STUCK_RESULTS or s['verb'] not in STUCK_VERBS or not s.get('pos'):
            continue
        m = re.search(r'([0-9.]+) m from the point', s.get('detail') or '')
        d_want = float(m.group(1)) if m else None
        if s['result'] == 'timeout' and d_want is not None and s.get('radius') is not None and d_want <= s['radius']:
            continue
        mp = map_at(rd, s['t1'])
        lives = [(r['t'] - rd.t0, r['life']) for r in rd.rows if r.get('life') is not None and s['t0'] - 0.3 <= r['t'] - rd.t0 <= s['t1'] + 0.3]
        life_lost = max(0, lives[0][1] - min(l for _t, l in lives)) if lives else 0
        at = [r1(c) for c in s['pos']]
        rec = {'run': rd.run_id, 'build': build, 'ts': ts or rd.ts, 'step': s['in'], 'verb': s['verb'], 'src': s['src'], 'at': at, 'want': s['want'], 'd_want': d_want,
               'result': s['result'], 'detail': (s.get('detail') or '')[:160], 'moved': s.get('moved'), 'map': mp, 't': s['t1'], 'life_lost': life_lost}
        rec['cause'], rec['why'] = classify_stuck(rec, world)
        out.append(rec)
    return out


# ------------------------------------------------------------------------------------------------------------------------ the derived graph

class Node:
    __slots__ = ('i', 'x', 'y', 'z', 'n', 'tracks', 'builds')

    def __init__(self, i, x, y, z):
        self.i, self.x, self.y, self.z, self.n = i, x, y, z, 1
        self.tracks, self.builds = set(), set()

    @property
    def pos(self):
        return [r1(self.x), r1(self.y), r1(self.z)]


class Edge:
    __slots__ = ('lo', 'hi', 'fwd', 'back', 'kind', 'verbs', 'builds', 'ok', 'runs', 'join', 'contested', 'length')

    def __init__(self, lo, hi, join=False):
        self.lo, self.hi, self.fwd, self.back, self.kind, self.join = lo, hi, 0, 0, 'walk', join
        self.verbs, self.builds, self.ok, self.runs, self.contested, self.length = {}, set(), {}, set(), False, 0.0


class Graph:
    """Nodes (a point snapped within 1.0 m and 0.8 m of height) and the edges that consecutive track points make; built from the tracks every time."""

    def __init__(self):
        self.nodes, self.edges, self.cells = [], {}, {}
        self.adj = None

    def _cell(self, x, z):
        return (int(math.floor(x / 2.0)), int(math.floor(z / 2.0)))

    def _near(self, x, y, z, rxz, dy):
        cx, cz = self._cell(x, z)
        r = int(math.ceil(rxz / 2.0)) + 1
        best = None
        for gx in range(cx - r, cx + r + 1):
            for gz in range(cz - r, cz + r + 1):
                for i in self.cells.get((gx, gz), ()):
                    n = self.nodes[i]
                    dxz = math.hypot(n.x - x, n.z - z)
                    if dxz <= rxz and abs(n.y - y) <= dy:
                        k = dxz + 0.25 * abs(n.y - y)
                        if best is None or k < best[0]:
                            best = (k, n)
        return best[1] if best else None

    def node_at(self, x, y, z):
        n = self._near(x, y, z, SNAP_XZ, SNAP_Y)
        if n is None:
            n = Node(len(self.nodes), x, y, z)
            self.nodes.append(n)
            self.cells.setdefault(self._cell(x, z), []).append(n.i)
        else:
            n.x, n.y, n.z = (n.x * n.n + x) / (n.n + 1), (n.y * n.n + y) / (n.n + 1), (n.z * n.n + z) / (n.n + 1)
            n.n += 1
        return n

    @classmethod
    def build(cls, tracks, stuck=()):
        g = cls()
        for ti, t in enumerate(tracks):
            prev = None
            for p in t['pts']:
                n = g.node_at(p[1], p[2], p[3])
                n.tracks.add(ti)
                n.builds.add(t['build'])
                if prev is not None and prev[0] is not n and d2(p[1:4], prev[1]) <= GAP_MAX:
                    a, b = prev[0], n
                    lo, hi = (a, b) if a.i < b.i else (b, a)
                    e = g.edges.get((lo.i, hi.i))
                    if e is None:
                        e = g.edges[(lo.i, hi.i)] = Edge(lo.i, hi.i)
                    if a is lo:
                        e.fwd += 1
                    else:
                        e.back += 1
                    sn = p[4]
                    verb = next((s['verb'] for s in t['steps'] if s['in'] == sn), None) or 'none'
                    e.verbs[verb] = e.verbs.get(verb, 0) + 1
                    e.builds.add(t['build'])
                    e.runs.add(t['run'])
                    if t.get('ts') and t['ts'] > e.ok.get(t['build'], ''):
                        e.ok[t['build']] = t['ts']
                prev = (n, p[1:4])
        for e in g.edges.values():
            lo, hi = g.nodes[e.lo], g.nodes[e.hi]
            e.length = math.dist((lo.x, lo.y, lo.z), (hi.x, hi.y, hi.z))
            dy = hi.y - lo.y
            if abs(dy) >= VERT:
                up = e.fwd if dy > 0 else e.back
                down = e.back if dy > 0 else e.fwd
                e.kind = 'drop' if down and not up else 'up' if up and not down else 'climb'
        g._joins()
        g._contest(stuck)
        g.adj = None
        return g

    def _joins(self):
        for n in self.nodes:
            for gx in range(int(math.floor(n.x / 2.0)) - 1, int(math.floor(n.x / 2.0)) + 2):
                for gz in range(int(math.floor(n.z / 2.0)) - 1, int(math.floor(n.z / 2.0)) + 2):
                    for j in self.cells.get((gx, gz), ()):
                        if j <= n.i:
                            continue
                        m = self.nodes[j]
                        if (n.i, j) in self.edges or n.tracks & m.tracks:
                            continue
                        if math.hypot(n.x - m.x, n.z - m.z) <= JOIN_D and abs(n.y - m.y) <= JOIN_DY:
                            e = self.edges[(n.i, j)] = Edge(n.i, j, join=True)
                            e.length = math.dist((n.x, n.y, n.z), (m.x, m.y, m.z))

    def _contest(self, stuck):
        """An edge that an older build walked and that lies within 1.5 m of where a later build stopped, and that the later build never walked, is contested."""
        for s in stuck:
            at = s['at']
            for e in self.edges.values():
                if e.join or s['build'] in e.ok or not e.ok:
                    continue
                na, nb = self.nodes[e.lo], self.nodes[e.hi]
                dist, _t = seg_dist((at[0], at[2]), (na.x, na.z), (nb.x, nb.z))
                if dist <= PASSED_R and abs((na.y + nb.y) / 2 - at[1]) < 2.5 and s['ts'] > max(e.ok.values()):
                    e.contested = True

    def _adjacency(self):
        if self.adj is None:
            self.adj = [[] for _ in self.nodes]
            for e in self.edges.values():
                self.adj[e.lo].append((e.hi, e))
                self.adj[e.hi].append((e.lo, e))
        return self.adj

    def cost(self, e, a, b):
        """The cost of walking edge e from node a to node b, or None when it cannot be done (up a drop)."""
        L = max(e.length, 0.05)
        if e.join:
            return L * 1.3
        lo_hi = a == e.lo
        n_dir, n_rev = (e.fwd, e.back) if lo_hi else (e.back, e.fwd)
        ya, yb = self.nodes[a].y, self.nodes[b].y
        f = 1.0
        if e.kind == 'drop':
            if ya < yb:
                return None
            f = 1.1
        elif e.kind == 'up':
            f = 3.0 if ya < yb else 2.0
        elif e.kind == 'climb':
            f = 3.0
        elif not n_dir:
            f = 1.5
        if n_dir and not n_rev:
            f *= 1.05
        if e.contested:
            f *= 5.0
        return L * f

    def nearest(self, x, z, y=None, max_d=4.0):
        n = self._near(x, y if y is not None else 0.0, z, max_d, 1e9 if y is None else 3.0) if self.nodes else None
        return n

    def dijkstra(self, srcs, penalty=None):
        """({node: cost}, {node: previous}) from the source nodes; `penalty(node)` adds to the cost of entering a node."""
        adj = self._adjacency()
        dist, prev = {}, {}
        heap = []
        for s in srcs:
            dist[s] = 0.0
            heapq.heappush(heap, (0.0, s))
        while heap:
            d, a = heapq.heappop(heap)
            if d > dist.get(a, 1e18):
                continue
            for b, e in adj[a]:
                c = self.cost(e, a, b)
                if c is None:
                    continue
                nd = d + c + (penalty(self.nodes[b]) if penalty else 0.0)
                if nd < dist.get(b, 1e18):
                    dist[b], prev[b] = nd, a
                    heapq.heappush(heap, (nd, b))
        return dist, prev

    def reachable(self, srcs):
        return set(self.dijkstra(srcs)[0])

    def stats(self):
        v = [e for e in self.edges.values() if not e.join]
        return {'nodes': len(self.nodes), 'edges': len(v), 'both_ways': sum(1 for e in v if e.fwd and e.back), 'once': sum(1 for e in v if (e.fwd > 0) != (e.back > 0)),
                'joins': sum(1 for e in self.edges.values() if e.join), 'metres': round(sum(d2((self.nodes[e.lo].x, 0, self.nodes[e.lo].z), (self.nodes[e.hi].x, 0, self.nodes[e.hi].z)) for e in v), 1),
                'contested': sum(1 for e in v if e.contested), 'kinds': {k: sum(1 for e in v if e.kind == k) for k in ('walk', 'drop', 'up', 'climb') if any(e.kind == k for e in v)}}

    def edge_keys(self):
        return {k for k, e in self.edges.items() if not e.join}

    def two_way_keys(self):
        return {k for k, e in self.edges.items() if not e.join and e.fwd and e.back}


# ------------------------------------------------------------------------------------------------------------------------ one map

class MapData:
    def __init__(self, lib, name, data):
        self.lib, self.name, self.data = lib, name, data
        self._graph = self._clusters = None

    @property
    def tracks(self):
        return self.data['tracks']

    @property
    def stuck(self):
        return self.data['stuck']

    @property
    def attempts(self):
        return self.data['attempts']

    def touch(self):
        self._graph = self._clusters = None

    def graph(self):
        if self._graph is None:
            self._graph = Graph.build(self.tracks, self.stuck)
        return self._graph

    def anchors(self):
        out = []
        for ti, t in enumerate(self.tracks):
            if t['origin'] in ('start', 'placed', 'arrival') and t['pts']:
                p = t['pts'][0]
                out.append({'pos': [p[1], p[2], p[3]], 'kind': t['origin'], 'run': t['run'], 'track': ti})
        out += [dict(a) for a in self.data.get('anchors', [])]
        return out

    def anchor_nodes(self):
        g = self.graph()
        res = []
        for a in self.anchors():
            n = g.nearest(a['pos'][0], a['pos'][2], a['pos'][1], max_d=1.6)
            if n is not None:
                res.append((n.i, a))
        return res

    def clusters(self):
        if self._clusters is not None:
            return self._clusters
        cl = []
        for s in self.stuck:
            c = next((c for c in cl if d2(c['at'], s['at']) <= CLUSTER_R and abs(c['at'][1] - s['at'][1]) <= 3.0), None)
            if c is None:
                c = {'id': f'c{len(cl) + 1}', 'map': self.name, 'at': list(s['at']), 'n': 0, 'runs': [], 'builds': [], 'causes': {}, 'want': s.get('want'), 'wants': [],
                     'verbs': {}, 'last_ts': '', 'why': '', 'cause': 'wall', 'tried': [], 'worked': [], 'resolved': False, 'resolved_by': None, 'life_lost': 0, 'hazard': False, '_rec': []}
                cl.append(c)
            c['n'] += 1
            c['at'] = [r1((c['at'][i] * (c['n'] - 1) + s['at'][i]) / c['n']) for i in range(3)]
            if s['run'] not in c['runs']:
                c['runs'].append(s['run'])
            if s['build'] not in c['builds']:
                c['builds'].append(s['build'])
            c['causes'][s['cause']] = c['causes'].get(s['cause'], 0) + 1
            c['verbs'][s['verb']] = c['verbs'].get(s['verb'], 0) + 1
            if s.get('want') and s['want'] not in c['wants']:
                c['wants'].append(s['want'])
            c['want'] = s.get('want') or c['want']
            if s['ts'] >= c['last_ts']:
                c['last_ts'] = s['ts']
            c['_rec'].append(s)
            c['life_lost'] = max(c['life_lost'], int(s.get('life_lost') or 0))
            c['hazard'] = c['life_lost'] >= 4   # (a quarter-heart is 1: a heart or more lost while stopped here: something hurts him there)
        owned = {}   # (an attempt belongs to the nearest cluster within 3 m, not to every one: a way round that worked at one place says nothing of the place beside it)
        for a in self.attempts:
            near = min(((math.hypot(a['at'][0] - c['at'][0], a['at'][2] - c['at'][2]), c) for c in cl), key=lambda x: x[0], default=None)
            if near and near[0] <= CLUSTER_R + 1.0:
                owned.setdefault(near[1]['id'], []).append(a)
        for c in cl:
            order = {k: i for i, k in enumerate(CAUSES)}
            c['cause'] = sorted(c['causes'].items(), key=lambda kv: (-kv[1], order.get(kv[0], 99)))[0][0]
            c['why'] = next((r['why'] for r in reversed(c['_rec']) if r['cause'] == c['cause']), '')
            for a in owned.get(c['id'], ()):
                if a['attempt'] not in c['tried']:
                    c['tried'].append(a['attempt'])
                if a['result'] == 'worked':
                    c['worked'].append(a['attempt'])
            if c['worked']:
                c['resolved'], c['resolved_by'] = True, 'attempt ' + c['worked'][-1]
            else:
                by = self._walked_past(c)
                if by:
                    c['resolved'], c['resolved_by'] = True, by
            c.pop('_rec')
        self._clusters = cl
        return cl

    def _walked_past(self, c):
        ref = c['want']
        for t in self.tracks:
            if t['ts'] <= c['last_ts'] or t['run'] in c['runs']:
                continue
            pts = t['pts']
            for i, p in enumerate(pts):
                if d2(p[1:4], c['at']) <= PASSED_R and abs(p[2] - c['at'][1]) < 2.5:
                    for q in pts[i + 1:i + 60]:
                        if d2(q[1:4], c['at']) >= 4.0:
                            if ref:
                                a1 = math.atan2(ref[0] - c['at'][0], ref[1] - c['at'][2])
                                a2 = math.atan2(q[1] - c['at'][0], q[3] - c['at'][2])
                                if abs((a1 - a2 + math.pi) % (2 * math.pi) - math.pi) > math.radians(60):
                                    continue
                            return f'walked past (run {t["run"]}, build {t["build"]})'
                    break
        return None


# ------------------------------------------------------------------------------------------------------------------------ the library

class RouteLib:
    def __init__(self, root):
        self.root = Path(root)
        self._maps = {}

    # -- storage
    @contextlib.contextmanager
    def locked(self):
        self.root.mkdir(parents=True, exist_ok=True)
        with open(self.root / 'lock', 'a') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

    def _read(self, path, empty):
        try:
            d = json.loads(Path(path).read_text())
        except OSError:
            return empty
        except ValueError as e:
            raise LibError(f'{path}: not JSON ({e})')
        if d.get('format') != FORMAT:
            raise LibError(f'{path}: format {d.get("format")!r}, expected {FORMAT}')
        return d

    def _map_path(self, name):
        return self.root / 'maps' / f'{_safe(name)}.json'

    def maps(self):
        d = self.root / 'maps'
        return sorted(p.stem for p in d.glob('*.json')) if d.is_dir() else []

    def map(self, name):
        p = self._map_path(name)
        try:
            st = p.stat()
            key = (st.st_mtime_ns, st.st_size)
        except OSError:
            key = None
        c = self._maps.get(name)
        if c and c[0] == key:
            return c[1]
        data = self._read(p, {'format': FORMAT, 'map': name, 'tracks': [], 'stuck': [], 'attempts': [], 'anchors': []})
        data.setdefault('anchors', [])
        m = MapData(self, name, data)
        self._maps[name] = (key, m)
        return m

    def _save_map(self, m):
        m.data['format'], m.data['map'] = FORMAT, m.name
        _atomic(self._map_path(m.name), m.data)
        m.touch()
        self._maps.pop(m.name, None)

    def runs(self):
        return self._read(self.root / 'runs.json', {'format': FORMAT, 'runs': [], 'builds': {}})

    def links(self):
        return self._read(self.root / 'links.json', {'format': FORMAT, 'links': []})['links']

    def _targets_doc(self):
        return self._read(self.root / 'targets.json', {'format': FORMAT, 'targets': {}})

    def targets(self):
        return self._targets_doc()['targets']

    # -- targets
    def add_target(self, name, map, x, z, age=None, y=None, radius=3.0, issue=None, label=None):
        with self.locked():
            doc = self._targets_doc()
            old = doc['targets'].get(_safe(name), {})
            doc['targets'][name] = {'name': name, 'kind': 'point', 'map': map, 'age': age or age_of_map(map), 'x': float(x), 'z': float(z), 'y': None if y is None else float(y),
                                    'radius': float(radius), 'issue': issue, 'label': label, 'history': old.get('history', [])}
            _atomic(self.root / 'targets.json', doc)
        self._baseline(name)

    def add_cover(self, name, map, points, age=None, radius=3.0, issue=None, label=None):
        with self.locked():
            doc = self._targets_doc()
            old = doc['targets'].get(_safe(name), {})
            doc['targets'][name] = {'name': name, 'kind': 'cover', 'map': map, 'age': age or age_of_map(map), 'points': [[float(a), float(b)] for a, b in points], 'radius': float(radius),
                                    'issue': issue, 'label': label, 'history': old.get('history', [])}
            _atomic(self.root / 'targets.json', doc)
        self._baseline(name)

    def _baseline(self, name):
        """The first row of a target's history when the library already has data for its map (so the first import after it can say what it gained)."""
        with self.locked():
            doc = self._targets_doc()
            t = doc['targets'][name]
            if t['history']:
                return
            f = self._frontier_of(t)
            if not f['known']:
                return
            t['history'].append({'run': 'baseline', 'ts': now_iso(), 'remaining_m': f['remaining_m'], 'pos': f.get('pos')} if t['kind'] == 'point' else
                                {'run': 'baseline', 'ts': now_iso(), 'reached_n': f['reached_n'], 'n': f['n'], 'remaining_m': f['remaining_m'], 'pos': f.get('pos')})
            _atomic(self.root / 'targets.json', doc)

    def add_anchor(self, map, pos, kind='save', name=None):
        """A place a run can start from that no run recorded (a save made at a frontier point)."""
        with self.locked():
            m = self.map(map)
            m.data['anchors'] = [a for a in m.data.get('anchors', []) if not (a.get('name') == name and name)]
            m.data['anchors'].append({'pos': [r1(c) for c in pos], 'kind': kind, 'name': name})
            self._save_map(m)

    def frontier(self, name, map_cache=None):
        t = self.targets().get(name)
        if t is None:
            raise LibError(f'no target {name!r}')
        return self._frontier_of(t)

    def _anchored_nodes(self, m):
        g = m.graph()
        srcs = [i for i, _a in m.anchor_nodes()]
        return g, srcs, g.reachable(srcs) if srcs else set()

    def _frontier_of(self, t):
        mp = t['map']
        base = {'name': t['name'], 'kind': t['kind'], 'map': mp, 'known': False, 'target': t}
        if mp not in self.maps():
            return base
        m = self.map(mp)
        g, srcs, reach = self._anchored_nodes(m)
        if not reach:
            return base
        anchor_of = {i: a for i, a in m.anchor_nodes()}
        if t['kind'] == 'cover':
            pts = t['points']
            done, left = [], []
            for p in pts:
                best = min(((math.hypot(g.nodes[i].x - p[0], g.nodes[i].z - p[1]), i) for i in reach), default=(1e9, None))
                (done if best[0] <= t['radius'] else left).append(p)
            base.update(known=True, n=len(pts), reached_n=len(done), unreached=left, reached_points=done, remaining_m=None)
            if left:
                best = min(((math.hypot(g.nodes[i].x - p[0], g.nodes[i].z - p[1]), i, p) for p in left for i in reach))
                nd = g.nodes[best[1]]
                base.update(pos=nd.pos, remaining_m=round(best[0], 1), nearest_leg=best[2])
            return base
        tx, tz, ty = t['x'], t['z'], t.get('y')
        best = None
        for i in reach:
            n = g.nodes[i]
            dd = math.hypot(n.x - tx, n.z - tz) + (0.5 * abs(n.y - ty) if ty is not None else 0.0)
            if best is None or dd < best[0] - 1e-9:
                best = (dd, i)
        n = g.nodes[best[1]]
        base.update(known=True, pos=n.pos, node=n.i, remaining_m=round(best[0], 1), reached=best[0] <= t['radius'],
                    anchor=anchor_of.get(best[1]) or self._nearest_anchor(m, n))
        return base

    def _nearest_anchor(self, m, n):
        a = m.anchors()
        return min(a, key=lambda x: math.hypot(x['pos'][0] - n.x, x['pos'][2] - n.z)) if a else None

    def _update_targets(self, maps, run_id, ts):
        """The history of every target on those maps; returns ({name: metres gained}, [names known for the first time])."""
        gain, new = {}, []
        with self.locked():
            doc = self._targets_doc()
            for name, t in doc['targets'].items():
                if t['map'] not in maps:
                    continue
                f = self._frontier_of(t)
                if not f['known']:
                    continue
                h = t['history']
                prev = h[-1] if h else None
                if t['kind'] == 'cover':
                    row = {'run': run_id, 'ts': ts, 'reached_n': f['reached_n'], 'n': f['n'], 'remaining_m': f['remaining_m'], 'pos': f.get('pos')}
                    better = prev is None or f['reached_n'] > prev.get('reached_n', 0)
                    if prev is not None and better:
                        gain[name] = float(f['reached_n'] - prev.get('reached_n', 0))
                else:
                    row = {'run': run_id, 'ts': ts, 'remaining_m': f['remaining_m'], 'pos': f['pos']}
                    better = prev is None or f['remaining_m'] < prev['remaining_m'] - 0.5
                    if prev is not None and better:
                        gain[name] = round(prev['remaining_m'] - f['remaining_m'], 1)
                if prev is None:
                    new.append(name)
                if better:
                    h.append(row)
            _atomic(self.root / 'targets.json', doc)
        return gain, new

    # -- import
    def import_run(self, folder, build=None, label=None, world=None, ts=None, force=False):
        rd = RunData(folder, label=label)
        build = build or detect_build(rd.live, rd.out) or 'unknown'
        ts = ts or rd.ts
        with self.locked():
            led = self.runs()
            if not force and any(r['run'] == rd.run_id for r in led['runs']):
                return {'run': rd.run_id, 'skipped': 'already imported', 'build': build}
            tracks, links, = make_tracks(rd, build, ts)
            stuck = stuck_candidates(rd, tracks, build, world, ts)
            touched = sorted({t['map'] for t in tracks} | {s['map'] for s in stuck})
            before = {}
            for mp in touched:
                m = self.map(mp)
                g = m.graph()
                before[mp] = (g.stats(), g.edge_keys(), g.two_way_keys(), len(m.clusters()))
            for t in tracks:
                self._assign_map(t)
            by_map = {}
            for t in tracks:
                by_map.setdefault(t['map'], []).append(t)
            after = {}
            for mp in touched:
                m = self.map(mp)
                for t in by_map.get(mp, []):
                    t2 = dict(t)
                    t2.pop('map', None)
                    m.tracks.append(t2)
                for s in stuck:
                    if s['map'] == mp:
                        s2 = {k: v for k, v in s.items() if k != 'map'}
                        s2['track'] = next((t['id'] for t in by_map.get(mp, []) if t['pts'] and t['pts'][0][0] <= s['t'] <= t['pts'][-1][0] + 0.5), None)
                        m.stuck.append(s2)
                m.touch()
                self._save_map(m)
                m = self.map(mp)
                g = m.graph()
                after[mp] = (g.stats(), g.edge_keys(), g.two_way_keys(), len(m.clusters()))
            self._merge_links(links)
            st = {'run': rd.run_id, 'tag': rd.tag, 'build': build, 'ts': ts, 'folder': str(rd.folder), 'maps': touched, 'steps': len(rd.steps), 'stuck': len(stuck),
                  'metres': round(sum(t['len_m'] for t in tracks), 1),
                  'new_nodes': sum(after[m_][0]['nodes'] - before[m_][0]['nodes'] for m_ in touched),
                  'new_edges': sum(len(after[m_][1] - before[m_][1]) for m_ in touched),
                  'new_two_way': sum(len(after[m_][2] - before[m_][2]) for m_ in touched),
                  'new_clusters': sum(after[m_][3] - before[m_][3] for m_ in touched), 'links': len(links),
                  'per_map': {m_: {'metres': round(sum(t['len_m'] for t in by_map.get(m_, [])), 1), 'new_edges': len(after[m_][1] - before[m_][1]),
                                   'new_two_way': len(after[m_][2] - before[m_][2]), 'edges': after[m_][0]['edges'], 'metres_known': after[m_][0]['metres']} for m_ in touched}}
        gain, new = self._update_targets(set(touched), rd.run_id, ts)
        st['frontier_gain'], st['frontier_new'] = gain, new
        with self.locked():
            led = self.runs()
            led['runs'].append(st)
            led['builds'].setdefault(build, {'first_ts': ts})
            led['builds'][build]['first_ts'] = min(led['builds'][build]['first_ts'], ts)
            _atomic(self.root / 'runs.json', led)
        return st

    @staticmethod
    def _assign_map(t):
        return t   # (the map is on the track already)

    def _merge_links(self, new):
        if not new:
            return
        doc = self._read(self.root / 'links.json', {'format': FORMAT, 'links': []})
        for l in new:
            m = next((o for o in doc['links'] if o['from_map'] == l['from_map'] and o['to_map'] == l['to_map'] and o['via'] == l['via'] and d2(o['from'], l['from']) <= 3.0 and d2(o['to'], l['to']) <= 3.0), None)
            if m is None:
                doc['links'].append(l)
            else:
                m['count'] += l['count']
                m['builds'] = sorted(set(m['builds']) | set(l['builds']))
                m['runs'] = sorted(set(m['runs']) | set(l['runs']))
        _atomic(self.root / 'links.json', doc)

    def record_attempt(self, map, at, attempt, result, progress_m, build, run, ts=None):
        with self.locked():
            m = self.map(map)
            m.attempts.append({'at': [r1(c) for c in at], 'attempt': attempt, 'result': result, 'progress_m': round(float(progress_m), 1), 'build': build, 'run': run, 'ts': ts or now_iso()})
            self._save_map(m)

    def backfill_life(self):
        """Stuck records imported before hearts were counted get `life_lost` from their run's journal (the ledger names the folder); returns how many were filled."""
        runs = {r['run']: r for r in self.runs()['runs']}
        filled = 0
        for name in self.maps():
            with self.locked():
                m = self.map(name)
                todo = [s for s in m.stuck if 'life_lost' not in s]
                if not todo:
                    continue
                cache = {}
                for s in todo:
                    row = runs.get(s['run'])
                    if row is None:
                        continue
                    try:
                        if s['run'] not in cache:
                            cache[s['run']] = RunData(row['folder'], label=row.get('tag'))
                        rd = cache[s['run']]
                    except LibError:
                        continue
                    step = next((x for x in rd.steps if x['in'] == s.get('step')), None)
                    if step is None:
                        continue
                    lives = [r['life'] for r in rd.rows if r.get('life') is not None and step['t0'] - 0.3 <= r['t'] - rd.t0 <= step['t1'] + 0.3]
                    s['life_lost'] = max(0, lives[0] - min(lives)) if lives else 0
                    filled += 1
                self._save_map(m)
        return filled

    def record_stuck(self, map, rec):
        """A stuck point written as it happens (the walker's record callback)."""
        with self.locked():
            m = self.map(map)
            s = {k: v for k, v in rec.items() if k != 'map'}
            m.stuck.append(s)
            self._save_map(m)

    # -- the route
    def route(self, map, start, goal, age=None, goal_y=None, radius=2.5, world=None, avoid=(), snap=4.0, timeout=None):
        return route(self, map, start, goal, age=age, goal_y=goal_y, radius=radius, world=world, avoid=avoid, snap=snap, timeout=timeout)


# ------------------------------------------------------------------------------------------------------------------------ the route

def rdp(points, eps):
    """Ramer-Douglas-Peucker over (x, z) of [x, y, z] points; the first and last are kept."""
    if len(points) <= 2:
        return list(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        a, b = stack.pop()
        far, fi = -1.0, None
        for i in range(a + 1, b):
            dd, _t = seg_dist((points[i][0], points[i][2]), (points[a][0], points[a][2]), (points[b][0], points[b][2]))
            if dd > far:
                far, fi = dd, i
        if fi is not None and far > eps:
            keep[fi] = True
            stack += [(a, fi), (fi, b)]
    return [p for p, k in zip(points, keep) if k]


def thin_path(points, eps=1.2):
    """Waypoints [x, y, z] along a path: RDP with the vertical changes kept, no leg longer than LEG_M."""
    if not points:
        return []
    breaks = [0] + [i for i in range(1, len(points)) if abs(points[i][1] - points[i - 1][1]) >= VERT] + [len(points) - 1]
    out = [points[0]]
    for a, b in zip(breaks, breaks[1:]):
        if b <= a:
            continue
        seg = rdp(points[a:b + 1] if b + 1 <= len(points) else points[a:], eps)
        out += seg[1:]
    res = [out[0]]
    for p in out[1:]:
        q = res[-1]
        L = d2(p, q)
        if L > LEG_M:
            k = int(math.ceil(L / LEG_M))
            for j in range(1, k):
                f = j / k
                res.append([q[0] + (p[0] - q[0]) * f, q[1] + (p[1] - q[1]) * f, q[2] + (p[2] - q[2]) * f])
        res.append(p)
    return res


def step_lines(points, radius, timeout=None, verb='run'):
    """hsap `run x z radius r timeout t` lines to each point after the first (a leg's timeout from its length)."""
    out, prev = [], points[0]
    for p in points[1:]:
        L = d2(p, prev)
        t = timeout if timeout else min(30, 6 + int(math.ceil(L / 3.0)))
        out.append(f'{verb} {p[0]:.2f} {p[2]:.2f} radius {radius:g} timeout {int(t)}')
        prev = p
    return out


class _PlanWorld:
    def __init__(self, fn):
        self.fn = fn

    def plan(self, *a, **k):
        return self.fn(*a, **k)


def route(lib, map, start, goal, age=None, goal_y=None, radius=2.5, world=None, avoid=(), snap=4.0, timeout=None):
    """The library's way from `start` ([x, y, z]) toward `goal` ((x, z)) on `map`, then the world model's plan beyond the frontier (module doc)."""
    res = {'ok': False, 'complete': False, 'source': 'none', 'map': map, 'why': None, 'why_library': None, 'detail': '', 'frontier': None, 'waypoints': [], 'steps': [],
           'lib_steps': [], 'length_m': 0.0, 'known_m': 0.0, 'beyond_m': 0.0, 'beyond': None, 'contested': 0, 'near': None}
    goal = (float(goal[0]), float(goal[1]))

    def world_alone(why):
        res['why_library'] = why
        if world is None:
            res.update(why=why, detail='the library has no node near the start and no world model was given')
            return res
        b = world.plan(map, (start[0], start[2]), goal, from_y=start[1], to_y=goal_y, radius=radius)
        res.update(source='world', beyond=b, ok=bool(b.get('ok')), why=b.get('why'), detail=b.get('detail', ''), near=b.get('near'), waypoints=b.get('waypoints', []), steps=list(b.get('steps', [])),
                   beyond_m=b.get('length', 0.0))
        return res

    if map not in lib.maps():
        return world_alone('off-library')
    m = lib.map(map)
    g = m.graph()
    s = g.nearest(start[0], start[2], start[1], max_d=snap)
    if s is None:
        return world_alone('off-library')
    open_cl = [c for c in m.clusters() if not c['resolved']]
    av = list(avoid)

    def penalty(n):
        p = 0.0
        for c in open_cl:
            if math.hypot(n.x - c['at'][0], n.z - c['at'][2]) <= 2.5 and abs(n.y - c['at'][1]) < 2.5:
                p = COST_STUCK
                break
        for a in av:
            if math.hypot(n.x - a[0], n.z - a[1]) <= a[2]:
                p += COST_AVOID
                break
        return p

    dist, prev = g.dijkstra([s.i], penalty)
    best = None
    for i in dist:
        n = g.nodes[i]
        sc = math.hypot(n.x - goal[0], n.z - goal[1]) + (0.5 * abs(n.y - goal_y) if goal_y is not None else 0.0)
        if best is None or sc < best[0] - 1e-9 or (abs(sc - best[0]) <= 1e-9 and dist[i] < dist[best[1]]):
            best = (sc, i)
    sc, bi = best
    path = [bi]
    while path[-1] != s.i:
        path.append(prev[path[-1]])
    path.reverse()
    pts = [[start[0], start[1], start[2]]] if d2(start, g.nodes[s.i].pos) > 1.0 else []
    pts += [g.nodes[i].pos for i in path]
    ways = thin_path(pts)
    lib_steps = step_lines(ways, radius, timeout) if len(ways) > 1 else []
    bn = g.nodes[bi]
    complete = sc <= radius
    length = sum(d2(a, b) for a, b in zip(pts, pts[1:]))
    contested = sum(1 for a, b in zip(path, path[1:]) if g.edges.get((min(a, b), max(a, b))) and g.edges[(min(a, b), max(a, b))].contested)
    res.update(frontier={'pos': bn.pos, 'node': bi, 'remaining_m': round(sc, 1), 'start_node': s.i}, lib_steps=lib_steps, length_m=round(length, 1), known_m=round(length, 1), contested=contested,
               waypoints=[[r1(p[0]), r1(p[2])] for p in ways[1:]], steps=list(lib_steps), complete=complete, source='library')
    if complete:
        res['ok'] = True
        return res
    if world is None:
        res.update(why='frontier', detail=f'the library ends {sc:.1f} m from the goal; no world model was given')
        return res
    b = world.plan(map, (bn.x, bn.z), goal, from_y=bn.y, to_y=goal_y, radius=radius)
    res.update(beyond=b, beyond_m=b.get('length', 0.0), source='library+world' if lib_steps else 'world')
    if b.get('ok'):
        res['steps'] = lib_steps + list(b.get('steps', []))
        res['waypoints'] += list(b.get('waypoints', []))
        res['ok'] = True
        return res
    res.update(why=b.get('why'), detail=b.get('detail', ''), near=b.get('near'))
    # a plan that stops short is played only as far as it gets nearer the goal than the library's own frontier (the mesh's reachable point nearest the goal can lie behind it)
    last = b.get('near') or (b.get('waypoints') or [None])[-1]
    if last and math.hypot(last[0] - goal[0], last[1] - goal[1]) < sc - 1.0:
        res['steps'] = lib_steps + list(b.get('steps', []))
        res['waypoints'] += list(b.get('waypoints', []))
    else:
        res['source'] = 'library' if lib_steps else 'none'
    return res


def planner(lib, plan_fn, age=None):
    """The world model's plan(...) wrapped: the library's known way first, the world's plan beyond it. Same signature, the planner's own answer shape
    (ok, steps, waypoints, why, near, length) plus `source` and `library`; a map the library lacks, or a library that adds nothing, answers as plan_fn."""
    def wrapped(area, from_xz, to_xz, *, from_y=None, to_y=None, radius=1.0, **kw):
        world = _PlanWorld(lambda a, f, t, **k: plan_fn(a, f, t, **{**kw, **k}))   # (the caller's own options, `doors=...`, go on to the world model's plan)
        if area not in lib.maps() or from_y is None:
            return plan_fn(area, from_xz, to_xz, from_y=from_y, to_y=to_y, radius=radius, **kw)
        r = route(lib, area, (from_xz[0], from_y, from_xz[1]), to_xz, age=age, goal_y=to_y, radius=radius, world=world)
        if r['source'] == 'none':
            return plan_fn(area, from_xz, to_xz, from_y=from_y, to_y=to_y, radius=radius, **kw)
        if r['source'] == 'world' or (not r['lib_steps'] and not r['complete'] and r.get('beyond')):
            return r['beyond']   # (the library adds nothing here: the world model's own answer)
        out = {'ok': r['ok'], 'area': area, 'source': r['source'], 'waypoints': r['waypoints'], 'steps': r['steps'], 'length': round(r['known_m'] + r['beyond_m'], 1),
               'why': r['why'], 'detail': r['detail'], 'near': r['near'] or (r['frontier'] or {}).get('pos', [None, None, None])[::2], 'legs': [], 'library': {k: r[k] for k in ('known_m', 'complete', 'frontier', 'contested')}}
        if r.get('beyond'):
            for k in ('needed', 'gates', 'edges', 'unreached', 'door', 'after'):
                if k in r['beyond']:
                    out[k] = r['beyond'][k]
        return out
    return wrapped


# ------------------------------------------------------------------------------------------------------------------------ closed-loop playback

def stuck_from_event(ev, map, build, run, world=None, ts=None):
    """A stuck record from an hsap step event {src, result, detail, pos, moved} (the walker's and the push's own)."""
    verb, want, rad = parse_want(ev.get('src'))
    m = re.search(r'([0-9.]+) m from the point', ev.get('detail') or '')
    rec = {'run': run, 'build': build, 'ts': ts or now_iso(), 'step': ev.get('in'), 'verb': verb, 'src': (ev.get('src') or '')[:100], 'at': [r1(c) for c in ev['pos']], 'want': want,
           'd_want': float(m.group(1)) if m else None, 'result': ev.get('result'), 'detail': (ev.get('detail') or '')[:160], 'moved': ev.get('moved'), 'map': map, 't': ev.get('t', 0.0)}
    rec['cause'], rec['why'] = classify_stuck(rec, world)
    return rec


class Walker:
    """Plays a route from the library closed-loop through `io` (`send(line) -> step event`, `state() -> sample`): one leg at a time, the live position read
    before every leg; a leg that does not arrive is recorded and re-planned (the failed place avoided); a push off the planned line (`tol` metres) is a
    re-plan from where Link is. Ends `reached`, `frontier` (the known part is played), `blocked` (the same place stopped it `max_replans` times),
    `map-changed`, `held`, `cut` or `budget`."""

    def __init__(self, lib, io, *, map, age=None, world=None, tol=3.0, radius=2.5, timeout=None, max_replans=3, record=None, log=None, beyond=False, max_total=16, snap=8.0, build=None, run=None):
        self.lib, self.io, self.map, self.age, self.world = lib, io, map, age, world
        self.build, self.run = build, run
        self.radius, self.timeout, self.max_replans, self.record, self.beyond, self.max_total, self.snap = radius, timeout, max_replans, record, beyond, max_total, snap
        self.tol = max(tol, radius + 0.5)
        self.log = log or (lambda *_: None)

    def go(self, goal, goal_y=None, goal_radius=3.0):
        replans = drifts = sent = 0
        avoid, fails = [], {}
        res = {'ok': False, 'stopped': None, 'replans': 0, 'drifts': 0, 'sent': 0, 'pos': None, 'blocked_at': None, 'goal': list(goal), 'route': None}

        def done(stopped, ok=False, **kw):
            st = self.io.state() or {}
            res.update(ok=ok, stopped=stopped, replans=replans, drifts=drifts, sent=sent, pos=list(st.get('pos') or []), **kw)
            return res
        while True:
            st = self.io.state() or {}
            if st.get('map') not in (None, self.map):
                return done('map-changed')
            pos = st.get('pos')
            if not pos:
                return done('no-state')
            if d2(pos, (goal[0], 0, goal[1])) <= goal_radius:
                return done('reached', True)
            if replans > self.max_total:
                return done('budget')
            r = route(self.lib, self.map, pos, goal, age=self.age, goal_y=goal_y, radius=self.radius, world=self.world, avoid=avoid, snap=self.snap, timeout=self.timeout)
            res['route'] = {k: r[k] for k in ('complete', 'source', 'frontier', 'length_m', 'why', 'why_library')}
            lines = r['steps'] if (self.beyond or r['complete']) else r['lib_steps']
            if not lines:
                return done('off-library' if r.get('why_library') == 'off-library' and not r['ok'] else 'frontier')
            planned_prev = (pos[0], pos[2])
            replan = False
            for line in lines:
                wp = [float(v) for v in line.split()[1:3]]
                live = (self.io.state() or {}).get('pos') or pos
                if math.hypot(live[0] - planned_prev[0], live[2] - planned_prev[1]) > self.tol and planned_prev != (pos[0], pos[2]):
                    drifts += 1
                    replans += 1
                    replan = True
                    self.log(f'walker: {math.hypot(live[0] - planned_prev[0], live[2] - planned_prev[1]):.1f} m off the planned point: re-plan from {live}')
                    break
                ev = self.io.send(line)
                sent += 1
                if (self.io.state() or {}).get('map') not in (None, self.map):
                    return done('map-changed')
                if ev.get('result') == 'reached':
                    planned_prev = (wp[0], wp[1])
                    continue
                if ev.get('result') == 'cut':
                    return done('cut')
                rec = stuck_from_event(ev, self.map, self.build, self.run, self.world)
                if self.record:
                    self.record(rec)
                if ev.get('result') == 'held':
                    return done('held', blocked_at=list(ev.get('pos') or []))
                p = ev.get('pos') or pos
                key = (round(p[0] / 3.0), round(p[2] / 3.0))
                fails[key] = fails.get(key, 0) + 1
                avoid.append((p[0], p[2], 3.0))
                replans += 1
                if fails[key] >= self.max_replans:
                    return done('blocked', blocked_at=list(p))
                replan = True
                break
            if replan:
                continue
            st = self.io.state() or {}
            dist = d2(st.get('pos') or pos, (goal[0], 0, goal[1]))
            if dist <= goal_radius or (r['complete'] and dist <= goal_radius + self.radius):   # (a leg ends within its own radius of the route's last point)
                return done('reached', True)
            if r['complete']:
                if replans >= self.max_total:
                    return done('budget')
                replans += 1
                continue
            return done('frontier')


# ------------------------------------------------------------------------------------------------------------------------ a private world model

class PrivateWorld:
    """What routelib asks of a world model: the private `world/` data folder (objects.json, the nav meshes) read with the planner of `worldmodel/`. Reads data; names no place."""

    def __init__(self, world_dir):
        import sys
        self.dir = Path(world_dir)
        sys.path.insert(0, str(HERE.parent))
        from worldmodel import plan as wplan   # noqa: E402  (the code; the folder given is the data it reads)
        wplan.use(self.dir)
        self._plan = wplan
        try:
            self.objects = json.loads((self.dir / 'objects.json').read_text())
        except (OSError, ValueError):
            self.objects = {}

    def _objs(self, map, kind, x, z, r):
        out = []
        for o in self.objects.get(map, []):
            if o.get('kind') == kind:
                d = math.hypot(o['pos'][0] - x, o['pos'][2] - z)
                if d <= r:
                    out.append((map, o['pos'][0], o['pos'][2], o.get('gyaml')))
        return out

    def persons(self, map, x, z, r):
        return self._objs(map, 'person', x, z, r)

    def doors(self, map, x, z, r):
        return self._objs(map, 'door', x, z, r)

    def climbables(self, map, x, z, r):
        """Ivy, vines and ladders (the objects the climb step grabs) within r metres: (map, x, z, name)."""
        return self._objs(map, 'climbable', x, z, r)

    def props(self, map, x, z, r):
        out = []
        for kind in ('sign', 'blocker', 'shop', 'stone'):
            out += [o + (kind,) for o in self._objs(map, kind, x, z, r)]
        return out

    def ground(self, map, x, z, y):
        if not self._plan.available(map):
            return None
        n = self._plan._area(map).nearest(x, z, y, radius=1.0, dy=6.0)
        return n[2][1] if n else None

    def plan(self, area, from_xz, to_xz, **kw):
        return self._plan.plan(area, from_xz, to_xz, **kw)

    def start(self, area):
        try:
            starts = json.loads((self.dir / 'areas.json').read_text())[area]['starts']
        except (OSError, ValueError, KeyError, TypeError):
            return None
        for name in ('(default)', 'EntrancePos', area):
            if name in starts and starts[name].get('pos'):
                return list(starts[name]['pos'])
        first = next((v['pos'] for v in starts.values() if isinstance(v, dict) and v.get('pos')), None)
        return list(first) if first else None


# ------------------------------------------------------------------------------------------------------------------------ what is known

def describe(lib, maps=None):
    """Plain text: per map what the library knows (tracks, metres, nodes, edges, stuck clusters with causes), the links, the targets and their frontier."""
    out = []
    led = lib.runs()
    out.append(f'route library {lib.root}: {len(lib.maps())} maps, {len(led["runs"])} runs imported, builds {", ".join(sorted(led["builds"])) or "none"}')
    for name in (maps or lib.maps()):
        m = lib.map(name)
        g = m.graph()
        s = g.stats()
        cl = m.clusters()
        openc = [c for c in cl if not c['resolved']]
        out.append(f'{name}: {len(m.tracks)} tracks, {round(sum(t["len_m"] for t in m.tracks))} metres walked, {s["nodes"]} nodes, {s["edges"]} verified edges '
                   f'({s["both_ways"]} both ways, {s["once"]} once; {s["metres"]} m of ground; kinds {s["kinds"]}), {s["joins"]} joins, {s["contested"]} contested, '
                   f'{len(cl)} stuck clusters ({len(openc)} open), {len(m.anchors())} anchors, builds {sorted({t["build"] for t in m.tracks})}')
        for c in sorted(openc, key=lambda c: -c['n'])[:8]:
            out.append(f'    stuck {c["at"]} x{c["n"]} {c["cause"]}: {c["why"]} (wanted {c["want"]}; tried {c["tried"] or "nothing"})' + (f' HAZARD: {c["life_lost"]} quarter hearts lost there' if c.get('hazard') else ''))
    for l in lib.links():
        if maps and l['from_map'] not in maps and l['to_map'] not in maps:
            continue
        out.append(f'link {l["from_map"]} {l["from"]} -> {l["to_map"]} {l["to"]} via {l["via"]} x{l["count"]}')
    for name, t in sorted(lib.targets().items()):
        if maps and t['map'] not in maps:
            continue
        f = lib._frontier_of(t)
        if not f['known']:
            out.append(f'target {name} ({t["map"]}): no frontier yet (no anchored track on that map)')
        elif t['kind'] == 'cover':
            out.append(f'target {name} ({t["map"]}): {f["reached_n"]} of {f["n"]} legs reached')
        else:
            out.append(f'target {name} ({t["map"]}): frontier {f["pos"]}, {f["remaining_m"]} m from the point' + (' (reached)' if f['reached'] else ''))
    return '\n'.join(out)
