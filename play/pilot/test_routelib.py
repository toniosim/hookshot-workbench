#!/usr/bin/env python3
"""routelib.py on made-up runs (a run folder is written here the way hsap writes one: state.jsonl, out.jsonl, steps.txt, placement.json): the import
(tracks thinned and cut at a map change, a teleport and a load; steps aligned to samples; anchors; links), the derived graph (nodes, edges walked once
or both ways, drops and ups, joins, counts), the merge (one run twice = once, two builds, a contested edge, a resolved stuck point), the stuck causes
(rules over the step and a made-up world model), targets and frontiers (one place, a cover of legs, the gain per import), the route (the library's way,
the world model beyond it, an avoided stuck point, off the library), the planner wrapper, the closed-loop walker against a made-up world with a wall
and a drift, and the store (atomic, reloads equal). Made-up map names and coordinates; no game, no GPU, no network.   python3 -I -B test_routelib.py
"""
import json
import math
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import routelib  # noqa: E402
import hs_names  # noqa: E402  (routelib put the harness folder on sys.path: the game's own file names and log line come from it)

FAILS, CHECKS = [], [0]


def check(cond, what):
    CHECKS[0] += 1
    if not cond:
        FAILS.append(what)
        print('FAIL', what, flush=True)


# ---------------------------------------------------------------------------------------------------------- a made-up run on disk

class FakeRun:
    """Writes a run folder like hsap's (folder/pilot/live/...). Link walks polylines at 6 m/s, a sample every 0.1 s (6 presents)."""

    def __init__(self, folder, tag, map='Testland_Child', start=(0.0, 100.0, 0.0), child=1, t0=5000.0, save='kid-save', copy=None, boot_rows=3):
        self.live = Path(folder) / 'pilot' / 'live'
        self.live.mkdir(parents=True, exist_ok=True)
        self.tag, self.map, self.pos, self.child = tag, map, list(start), child
        self.mono, self.frame, self.n_step, self.steps_txt, self.life = t0, 7000, 0, [], 16
        self.rows, self.out = [], []
        note = f'hs-run: /h/hs-run.sh {copy or "/g/.copy-a"} {tag} 250 --user /h/saves/{save} HOS_CONTROL=/tmp/x/control.sock'
        self.out.append({'ev': 'note', 'text': note, 'boot': 'continue'})
        for _ in range(boot_rows):   # (samples before the game is in play: not part of any track)
            self.sample(0.1)
        self.out.append({'ev': 'gameplay', 't': 0.0, 'frame': self.frame, 'area': map})
        self.t_game0 = self.mono
        self.sample(0.0)

    def sample(self, dt, loading=0, event=0):
        self.mono += dt
        self.frame += max(1, round(dt * 60))
        self.rows.append({'t': round(self.mono, 3), 'frame': self.frame, 'map': self.map, 'pos': [round(c, 2) for c in self.pos], 'facing': 0.0, 'camera': 180.0,
                          'event': event, 'loading': loading, 'life': self.life, 'max_life': 16, 'rupees': 1, 'prompt': 'Empty', 'music': '', 'changed': {}, 'child': self.child})

    def gt(self):
        return round(self.mono - self.t_game0, 2)

    def walk(self, pts, speed=6.0):
        """Samples along the polyline from here through pts; the metres walked."""
        total = 0.0
        for (x, y, z) in pts:
            d = math.dist((self.pos[0], self.pos[2]), (x, z))
            n = max(1, int(d / (speed * 0.1)))
            x0, y0, z0 = self.pos
            for i in range(1, n + 1):
                f = i / n
                self.pos = [x0 + (x - x0) * f, y0 + (y - y0) * f, z0 + (z - z0) * f]
                self.sample(0.1)
            total += d
        return total

    def leg(self, src, pts, result='reached', detail='', verb_moved=None, event=0, hurt=0):
        """One hsap step that walks pts and ends with result; the step event is written with the game seconds at its end."""
        self.n_step += 1
        self.steps_txt.append(src)
        t_in = self.mono
        walked = self.walk(pts)
        if hurt:   # (a boulder: hearts lost while Link stands there)
            for _ in range(hurt // 4):
                self.sample(1.0)
                self.life -= 4
                self.sample(0.2)
        if event:
            self.sample(0.7, event=1)
        secs = round(self.mono - t_in, 2)
        moved = verb_moved if verb_moved is not None else round(walked, 2)
        self.out.append({'ev': 'step', 'in': self.n_step, 'src': src, 'result': result, 'secs': secs, 'moved': moved, 'detail': detail or f'{0.5:.2f} m from the point',
                         'pos': [round(c, 2) for c in self.pos], 't': self.gt()})

    def wait(self, s, src=None):
        self.n_step += 1
        self.steps_txt.append(src or f'wait {s}')
        t_in = self.mono
        for _ in range(int(s / 0.1)):
            self.sample(0.1)
        self.out.append({'ev': 'step', 'in': self.n_step, 'src': src or f'wait {s}', 'result': 'done', 'secs': round(self.mono - t_in, 2), 'moved': 0.0, 'detail': '',
                         'pos': [round(c, 2) for c in self.pos], 't': self.gt()})

    def change_map(self, map, pos, src=None, via_step=True, loading_s=0.6):
        """A load: rows with loading=1 on the old map, then the new map from pos. With src the load happens inside a step that ends `entered`."""
        if src:
            self.n_step += 1
            self.steps_txt.append(src)
            t_in = self.mono
        for _ in range(int(loading_s / 0.1)):
            self.sample(0.1, loading=1)
        self.map, self.pos = map, list(pos)
        self.sample(0.1)
        self.sample(0.1)
        if src:
            self.out.append({'ev': 'step', 'in': self.n_step, 'src': src, 'result': 'entered', 'secs': round(self.mono - t_in, 2), 'moved': 3.0, 'detail': '',
                             'pos': [round(c, 2) for c in self.pos], 't': self.gt()})

    def jump(self, pos, map=None):
        """A teleport with no load rows (a debug warp): the position is somewhere else at the next sample."""
        self.pos = list(pos)
        if map:
            self.map = map
        self.sample(0.1)

    def write(self, placement=None, log=None, project=None):
        (self.live / 'state.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in self.rows))
        (self.live / 'out.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in self.out))
        (self.live / 'steps.txt').write_text(''.join(s + '\n' for s in self.steps_txt))
        if placement:
            (self.live / 'placement.json').write_text(json.dumps(placement))
        if log:
            g = Path(self.live).parent.parent / 'game'
            g.mkdir(exist_ok=True)
            (g / hs_names.Names(project or hs_names.PROJECTS[-1]).log).write_text(log)
        return Path(self.live).parent.parent


def build_log(version, source='c38d7c57', project=None):
    return f'[hos host] {project or hs_names.PROJECTS[-1]} {version} (source {source})\n[hos host] run_id: abc\n'


class FakeWorld:
    """What routelib asks of a world model (duck-typed): people, doors, the ground height and a planner. Made-up objects on a made-up map."""

    def __init__(self):
        self.people, self.door_list, self.prop_list, self.ground_fn, self.plan_calls, self.plan_result = [], [], [], (lambda m, x, z, y: y), [], None

    def persons(self, map, x, z, r):
        return [p for p in self.people if p[0] == map and math.hypot(p[1] - x, p[2] - z) <= r]

    def doors(self, map, x, z, r):
        return [d for d in self.door_list if d[0] == map and math.hypot(d[1] - x, d[2] - z) <= r]

    def ground(self, map, x, z, y):
        return self.ground_fn(map, x, z, y)

    def props(self, map, x, z, r):
        return [p for p in self.prop_list if p[0] == map and math.hypot(p[1] - x, p[2] - z) <= r]

    def plan(self, area, from_xz, to_xz, from_y=None, to_y=None, radius=1.0, **kw):
        self.plan_calls.append((area, tuple(from_xz), tuple(to_xz), radius))
        if self.plan_result is not None:
            return self.plan_result
        return {'ok': True, 'area': area, 'waypoints': [list(to_xz)], 'steps': [f'run {to_xz[0]:.2f} {to_xz[1]:.2f} radius {radius:g}'], 'length': math.dist(from_xz, to_xz), 'why': None, 'near': None}


def L(a, b):
    return math.dist((a[0], a[2]), (b[0], b[2]))


# ---------------------------------------------------------------------------------------------------------- the checks

def import_checks(tmp):
    lib = routelib.RouteLib(tmp / 'lib1')
    r = FakeRun(tmp / 'runA', 'runA-tag', start=(0.0, 100.0, 0.0), copy='/g/.copy-a')
    r.leg('run 0 30 radius 2.5 timeout 30', [(0, 100, 30)], 'reached')
    r.leg('run 20 30 radius 2.5 timeout 30', [(20, 100, 30)], 'reached')
    r.wait(1.0)
    run_a = r.write(placement={'ok': True, 'to': 'Testland_Child'}, log=build_log('v3.0.0-rc.4-416-gabc1234'))
    for project in hs_names.PROJECTS:   # (the log is named for the project the copy was built from; the version line says the same)
        other = FakeRun(tmp / f'run-{project}', f'run-{project}-tag', copy='/g/.copy-b')
        other.leg('run 0 10 radius 2.5 timeout 30', [(0, 100, 10)], 'reached')
        folder = other.write(placement={'ok': True, 'to': 'Testland_Child'}, log=build_log('v3.0.0-rc.4-416-gdef5678', project=project), project=project)
        check(routelib.detect_build(folder / 'pilot' / 'live', []) == 'gdef5678', f'the build is read from the {project} log')
    st = lib.import_run(run_a)
    check(st['run'].startswith('runA-tag') and st['build'] == 'gabc1234', f'the run id is the tag and the build is read from the log ({st.get("run")}, {st.get("build")})')
    m = lib.map('Testland_Child')
    check(len(m.tracks) == 1 and m.tracks[0]['age'] == 'child' and m.tracks[0]['build'] == 'gabc1234', f'one track, child, with its build ({[(t["age"], t["build"]) for t in m.tracks]})')
    pts = m.tracks[0]['pts']
    check(len(pts) < 120 and len(pts) > 40, f'the track is thinned to about one point per 0.6 m ({len(pts)} points for 50 m)')
    gaps = [L(a[1:4], b[1:4]) for a, b in zip(pts, pts[1:])]
    check(max(gaps) < 1.3, f'no gap in the thinned track is over 1.3 m ({max(gaps):.2f})')
    check(abs(pts[0][1]) < 0.2 and abs(pts[0][3]) < 0.2 and pts[0][0] >= 0.0, f'the track starts where Link was in play, not before ({pts[0]})')
    check(abs(sum(gaps) - 50.0) < 2.0, f'the track is 50 m long ({sum(gaps):.1f})')
    steps = m.tracks[0]['steps']
    check([s['verb'] for s in steps] == ['run', 'run', 'wait'] and steps[0]['want'] == [0.0, 30.0] and steps[0]['result'] == 'reached', f'the steps are kept with their points ({steps})')
    by_step = {}
    for p in pts:
        by_step.setdefault(p[4], 0)
        by_step[p[4]] += 1
    check(by_step.get(1, 0) > 20 and by_step.get(2, 0) > 20, f'points belong to the step that was running ({by_step})')
    check(st['metres'] > 45 and st['new_edges'] > 20 and st['new_nodes'] > 20, f'the first import adds metres, nodes and edges ({st})')
    # the same run again adds nothing and says so
    st2 = lib.import_run(run_a)
    check(st2.get('skipped') == 'already imported' and len(lib.map('Testland_Child').tracks) == 1, f'a run is imported once ({st2})')
    # the ledger
    led = json.loads((tmp / 'lib1' / 'runs.json').read_text())
    check(len(led['runs']) == 1 and led['runs'][0]['run'] == st['run'], f'one ledger row ({list(led)})')
    # anchors: the run's start
    anc = m.anchors()
    check(any(abs(a['pos'][0]) < 0.3 and abs(a['pos'][2]) < 0.3 and a['kind'] in ('start', 'placed') for a in anc), f'the start is an anchor ({anc})')

    # cut at a map change inside a step: two tracks, a walked link, an arrival anchor
    r = FakeRun(tmp / 'runB', 'runB', start=(0, 100, 0))
    r.leg('run 0 20 radius 2.5 timeout 30', [(0, 100, 20)], 'reached')
    r.change_map('Otherland_Child', (50.0, 90.0, 50.0), src='enter 0 25 through 0 30 timeout 40')
    r.leg('run 50 70 radius 2.5 timeout 30', [(50, 90, 70)], 'reached')
    run_b = r.write()
    lib.import_run(run_b, build='b1')
    check(sorted(lib.maps()) == ['Otherland_Child', 'Testland_Child'], f'two maps ({lib.maps()})')
    lk = lib.links()
    check(len(lk) == 1 and lk[0]['from_map'] == 'Testland_Child' and lk[0]['to_map'] == 'Otherland_Child' and lk[0]['via'] == 'walked', f'one walked link ({lk})')
    check(abs(lk[0]['from'][2] - 20) < 1.5 and abs(lk[0]['to'][0] - 50) < 0.5, f'link ends: where Link left and where he arrived ({lk[0]["from"]} -> {lk[0]["to"]})')
    o = lib.map('Otherland_Child')
    check(o.tracks[0]['origin'] == 'arrival' and any(a['kind'] == 'arrival' for a in o.anchors()), f'the far side starts at an arrival anchor ({o.tracks[0]["origin"]})')
    check(len(lib.map('Testland_Child').tracks) == 2, 'the first map has its two tracks')
    # loading rows are not walked
    check(all(abs(p[1] - 50) < 1.0 for p in o.tracks[0]['pts']), 'no track point of the far side lies in the load or on the old map')

    # a teleport (a debug warp) cuts the track and is no link; a cheat step marks a warp link
    r = FakeRun(tmp / 'runC', 'runC', start=(0, 100, 0))
    r.leg('run 0 10 radius 2.5 timeout 30', [(0, 100, 10)], 'reached')
    r.jump((80.0, 100.0, 80.0))
    r.leg('run 80 90 radius 2.5 timeout 30', [(80, 100, 90)], 'reached')
    lib.import_run(r.write(), build='b1')
    tr = [t for t in lib.map('Testland_Child').tracks if t['run'].startswith('runC')]
    check(len(tr) == 2 and tr[1]['origin'] == 'jump', f'a jump of 80 m starts a new track with origin jump ({[t["origin"] for t in tr]})')
    check(len(lib.links()) == 1, 'a warp inside a map is no link')
    r = FakeRun(tmp / 'runD', 'runD', start=(0, 100, 0))
    r.leg('run 0 10 radius 2.5 timeout 30', [(0, 100, 10)], 'reached')
    r.change_map('Thirdland_Adult', (1.0, 100.0, 1.0), src='cheat 1003')
    lib.import_run(r.write(), build='b1')
    vias = sorted(l['via'] for l in lib.links())
    check(vias == ['walked', 'warp'], f'a cheat step makes a warp link, kept apart from the walked one ({vias})')   # (runF below adds an event link)
    check(lib.map('Thirdland_Adult').tracks[0]['age'] in ('adult', 'child'), 'age is read')

    # a map change while a step that does not walk runs (a text closes and the story moves Link) is a link of its own kind; one before the first step, and an age switch, are not
    r = FakeRun(tmp / 'runF', 'runF', start=(0, 100, 0))
    r.n_step += 1
    r.steps_txt.append('watch Some_Flag')
    r.out.append({'ev': 'step', 'in': r.n_step, 'src': 'watch Some_Flag', 'result': 'done', 'secs': 0.0, 'moved': 0.0, 'detail': '', 'pos': [0, 100, 0], 't': 0.0})   # (a watch line at game second 0: not a step that acts)
    r.sample(0.3)
    r.change_map('Testland_Adult', (0.0, 100.0, 0.0), loading_s=0.0)       # (the harness's age switch before any step)
    r.change_map('Pre_Adult', (5.0, 100.0, 5.0), loading_s=0.0)            # (and its teleport: no step yet)
    r.leg('run 5 20 radius 2.5 timeout 30', [(5, 100, 20)], 'reached')
    r.change_map('Story_Adult', (9.0, 100.0, 9.0), src='advance timeout 25')
    r.leg('run 9 30 radius 2.5 timeout 30', [(9, 100, 30)], 'reached')
    lib.import_run(r.write(), build='b1')
    ev = [l for l in lib.links() if l['via'] == 'event']
    check(len(ev) == 1 and ev[0]['from_map'] == 'Pre_Adult' and ev[0]['to_map'] == 'Story_Adult', f'a story transition during an advance step is an event link ({lib.links()})')
    check(not any(l['to_map'] in ('Testland_Adult', 'Pre_Adult') for l in lib.links()), 'the harness\'s own age switch and teleport before the first step are no links')
    # a run that starts placed on another map than its first sample: the placement is the origin
    r = FakeRun(tmp / 'runE', 'runE', map='Testland_Child', start=(5, 100, 5))
    r.sample(0.5)
    r.change_map('Fieldland_Child', (200.0, 150.0, 300.0), loading_s=0.0)
    r.wait(2.0)
    lib.import_run(r.write(placement={'ok': True, 'to': 'Fieldland_Child', 'age': 'child', 'hour': 23}), build='b1')
    f = lib.map('Fieldland_Child')
    check(f.tracks and f.tracks[0]['origin'] == 'placed' and any(a['kind'] == 'placed' for a in f.anchors()), f'a placement is an origin and an anchor ({[t["origin"] for t in f.tracks]})')
    check(all(l['to_map'] != 'Fieldland_Child' for l in lib.links()), 'a placement is no link')
    return lib


def graph_checks(tmp):
    lib = routelib.RouteLib(tmp / 'lib2')
    # one walk A->B, then B->A (both ways), then a second walk A->C (once)
    r = FakeRun(tmp / 'g1', 'g1', start=(0, 100, 0))
    r.leg('run 20 0 radius 2.5 timeout 30', [(20, 100, 0)], 'reached')
    r.leg('run 0 0 radius 2.5 timeout 30', [(0, 100, 0)], 'reached')
    r.leg('run 0 20 radius 2.5 timeout 30', [(0, 100, 20)], 'reached')
    lib.import_run(r.write(), build='b1')
    g = lib.map('Testland_Child').graph()
    s = g.stats()
    check(s['both_ways'] >= 10 and s['once'] >= 10, f'a stretch walked there and back is both ways, one walked once ({s})')
    check(abs(s['metres'] - 40.0) < 4.0, f'the graph has about 40 m of edges (20 m twice counts once, plus 20 m: {s["metres"]})')
    # the same walk again in another run: counts rise, no new edge
    before = g.stats()['edges']
    r = FakeRun(tmp / 'g2', 'g2', start=(0, 100, 0))
    r.leg('run 20 0 radius 2.5 timeout 30', [(20, 100, 0)], 'reached')
    st = lib.import_run(r.write(), build='b2')
    g = lib.map('Testland_Child').graph()
    check(g.stats()['edges'] == before and st['new_edges'] == 0, f'the same walk in another run makes no new edge ({st["new_edges"]}, {g.stats()["edges"]} vs {before})')
    e = max(g.edges.values(), key=lambda e: e.fwd + e.back)
    check(e.fwd + e.back >= 3 and set(e.builds) >= {'b1', 'b2'}, f'its edges count the walks and name both builds ({e.fwd}, {e.back}, {e.builds})')
    # a drop and an up
    r = FakeRun(tmp / 'g3', 'g3', start=(100, 110, 0))
    r.leg('run 100 0 radius 2.5 timeout 30', [(100, 110, 5), (100, 100, 6), (100, 100, 12)], 'reached')
    r.leg('run 100 15 radius 2.5 timeout 30', [(100, 104, 14), (100, 104, 18)], 'reached')
    lib.import_run(r.write(), build='b1')
    g = lib.map('Testland_Child').graph()
    kinds = sorted({e.kind for e in g.edges.values()})
    check('drop' in kinds and 'up' in kinds, f'a 10 m drop and a 4 m rise are edges of their kinds ({kinds})')
    # nearest node, off the library
    n = g.nearest(10.2, 0.1, 100.0, max_d=3.0)
    check(n is not None and abs(n.x - 10.2) < 1.2, f'nearest finds the walked node ({n and (n.x, n.z)})')
    check(g.nearest(300, 300, 100.0, max_d=4.0) is None, 'nothing near a far point')
    check(g.nearest(10.2, 0.1, 140.0, max_d=3.0) is None, 'a node on another level is not near')
    # a second track within 1.2 m joins the first without being a verified edge
    r = FakeRun(tmp / 'g4', 'g4', start=(200.0, 100.0, 40.0))
    r.leg('run 220 40 radius 2.5 timeout 30', [(220, 100, 40)], 'reached')
    lib.import_run(r.write(), build='b1')
    before = lib.map('Testland_Child').graph().stats()
    r = FakeRun(tmp / 'g5', 'g5', start=(200.0, 100.0, 41.8))
    r.leg('run 220 41.8 radius 2.5 timeout 30', [(220, 100, 41.8)], 'reached')
    lib.import_run(r.write(), build='b1')
    g = lib.map('Testland_Child').graph()
    s = g.stats()
    check(s['joins'] > 10 and s['edges'] - before['edges'] < 25 + 5, f'a track 1.8 m beside another is joined to it, the joins counted apart from the verified edges ({before["edges"]} -> {s["edges"]} edges, {s["joins"]} joins)')
    rt = lib.route('Testland_Child', (200.0, 100.0, 40.0), (220.0, 41.8), age='child', radius=2.5)
    check(rt['complete'], 'a route may cross a join')


def stuck_checks(tmp):
    world = FakeWorld()
    lib = routelib.RouteLib(tmp / 'lib3')

    def one(name, src, result, detail, end, via_prompt=None, event=0, moved=0.0, world_=None):
        r = FakeRun(tmp / name, name, start=(0, 100, 0))
        r.leg('run 0 10 radius 2.5 timeout 30', [(0, 100, 10)], 'reached')
        r.leg(src, [(end[0], end[1], end[2])], result, detail=detail, event=event, verb_moved=moved)
        return lib.import_run(r.write(), build='b1', world=world_)
    # no world: wall
    one('s1', 'run 0 60 radius 2.5 timeout 30', 'stuck', '50.00 m from the point; moved under 0.3 m in 2.5 s at 0.0 100.0 10.0', (0, 100, 10.0))
    c = lib.map('Testland_Child').clusters()
    check(len(c) == 1 and c[0]['cause'] == 'wall' and c[0]['n'] == 1, f'no world model: a stuck walk is a wall ({c})')
    check(abs(c[0]['at'][2] - 10.0) < 0.5 and c[0]['want'] == [0.0, 60.0], f'the cluster has the place and the point it wanted ({c[0]["at"]}, {c[0]["want"]})')
    # held
    one('s2', 'run 0 60 radius 2.5 timeout 30', 'held', '50.00 m from the point; an event holds Link at 0.0 100.0 15.0', (0, 100, 15.0), event=1)
    c = {k['cause'] for k in lib.map('Testland_Child').clusters()}
    check('held' in c, f'an event that holds Link is `held` ({c})')
    # enter blocked
    one('s3', 'enter 0 40 through 0 45 timeout 40', 'blocked', 'the way is shut: 3.00 m from the point; moved under 0.3 m in 2.5 s at 0.0 100.0 20.0', (0, 100, 20.0))
    c = {k['cause'] for k in lib.map('Testland_Child').clusters()}
    check('door-side' in c, f'an enter that ended blocked next to its door is door-side ({c})')
    r = FakeRun(tmp / 's3b', 's3b', start=(200, 100, -40))
    r.leg('enter 200 140 through 200 145 timeout 40', [(200, 100, -30)], 'blocked', detail='the way is shut: 130.00 m from the point; moved under 0.3 m in 2.5 s at 200.0 100.0 -30.0')
    lib.import_run(r.write(), build='b1')
    c = [k for k in lib.map('Testland_Child').clusters() if abs(k['at'][0] - 200) < 1.0]
    check(c and c[0]['cause'] == 'wall', f'an enter blocked 130 m from its door is a wall on the way, not a door ({c and c[0]["cause"]})')
    # with a world: people near, a door near, a ledge, a drop
    world.people = [('Testland_Child', 0.5, 30.0), ('Testland_Child', 1.0, 31.5)]
    one('s4', 'run 0 90 radius 2.5 timeout 30', 'stuck', '60.00 m from the point; moved under 0.3 m in 2.5 s at 0.0 100.0 30.0', (0, 100, 30.0), world_=world)
    c = [k for k in lib.map('Testland_Child').clusters() if abs(k['at'][2] - 30.0) < 1.0]
    check(c and c[0]['cause'] == 'npc-crowd' and 'person' in c[0]['why'], f'a person within 2.5 m is an npc-crowd ({c and c[0]})')
    world.people = []
    world.door_list = [('Testland_Child', 0.3, 52.0)]
    one('s5', 'run 0 90 radius 2.5 timeout 30', 'stuck', '38.00 m from the point; moved under 0.3 m in 2.5 s at 0.0 100.0 50.0', (0, 100, 50.0), world_=world)
    c = [k for k in lib.map('Testland_Child').clusters() if abs(k['at'][2] - 50.0) < 1.0]
    check(c and c[0]['cause'] == 'door-side', f'a door ahead within 2.6 m is door-side ({c and c[0]["cause"]})')
    world.door_list = []
    world.ground_fn = lambda m, x, z, y: y + 1.2 if z > 60 else y
    one('s6', 'run 0 90 radius 2.5 timeout 30', 'stuck', '28.00 m from the point; moved under 0.3 m in 2.5 s at 0.0 100.0 62.0', (0, 100, 62.0), world_=world)
    c = [k for k in lib.map('Testland_Child').clusters() if abs(k['at'][2] - 62.0) < 1.0]
    check(c and c[0]['cause'] == 'ledge-up', f'ground 1.2 m higher 1.5 m ahead is a ledge from below ({c and c[0]["cause"]})')
    world.ground_fn = lambda m, x, z, y: y - 4.0 if z > 70 else y
    one('s7', 'run 0 90 radius 2.5 timeout 30', 'stuck', '18.00 m from the point; moved under 0.3 m in 2.5 s at 0.0 100.0 72.0', (0, 100, 72.0), world_=world)
    c = [k for k in lib.map('Testland_Child').clusters() if abs(k['at'][2] - 72.0) < 1.0]
    check(c and c[0]['cause'] == 'drop-not-taken', f'ground 4 m lower ahead is a drop not taken ({c and c[0]["cause"]})')
    world.ground_fn = lambda m, x, z, y: y
    world.prop_list = [('Testland_Child', 1.0, 83.0, 'Signboard_X', 'sign')]
    one('s8p', 'run 0 90 radius 2.5 timeout 30', 'stuck', '8.00 m from the point; moved under 0.3 m in 2.5 s at 0.0 100.0 82.0', (0, 100, 82.0), world_=world)
    c = [k for k in lib.map('Testland_Child').clusters() if abs(k['at'][2] - 82.0) < 1.0]
    check(c and c[0]['cause'] == 'wall' and 'Signboard_X' in c[0]['why'], f'a placed object next to the stuck point is named in the wall\'s why ({c and c[0]["why"]})')
    world.prop_list = []
    one('s8', 'run 0 90 radius 2.5 timeout 30', 'stuck', '8.00 m from the point; moved under 0.3 m in 2.5 s at 0.0 100.0 82.0', (0, 100, 82.0), world_=world)
    c = [k for k in lib.map('Testland_Child').clusters() if abs(k['at'][2] - 82.0) < 1.0]
    check(c and c[0]['cause'] == 'wall' and 'ahead' in c[0]['why'], f'open ground ahead and still stopped: a wall or a prop ({c and (c[0]["cause"], c[0]["why"])})')
    # a timeout that kept moving is slow
    r = FakeRun(tmp / 's9', 's9', start=(0, 100, 0))
    r.leg('run 0 200 radius 2.5 timeout 3', [(0, 100, 95)], 'timeout', detail='105.00 m from the point after 3 s', verb_moved=95.0)
    lib.import_run(r.write(), build='b1')
    c = [k for k in lib.map('Testland_Child').clusters() if abs(k['at'][2] - 95.0) < 1.0]
    check(c and c[0]['cause'] == 'slow', f'a timeout that was still moving is slow ({c and c[0]["cause"]})')

    # hearts lost while stopped: the record and the cluster say so (the cause stays: the cause words are the tactics' vocabulary)
    r = FakeRun(tmp / 's11', 's11', start=(300, 100, 0))
    r.leg('run 300 60 radius 2.5 timeout 30', [(300, 100, 10)], 'stuck', detail='50.00 m from the point; moved under 0.3 m in 2.5 s at 300.0 100.0 10.0', hurt=8)
    r.leg('run 300 60 radius 2.5 timeout 30', [(300, 100, 10.2)], 'stuck', detail='50.00 m from the point; moved under 0.3 m in 2.5 s at 300.0 100.0 10.2')
    lib.import_run(r.write(), build='b1')
    c = [k for k in lib.map('Testland_Child').clusters() if abs(k['at'][0] - 300) < 1.0]
    check(c and c[0]['life_lost'] == 8 and c[0]['hazard'] and c[0]['cause'] == 'wall', f'a stuck place where 8 quarter hearts were lost is a hazard, its cause words unchanged ({c and (c[0]["life_lost"], c[0]["hazard"], c[0]["cause"])})')
    check(not any(k['hazard'] for k in lib.map('Testland_Child').clusters() if abs(k['at'][0] - 300) > 1.0), 'no other cluster is a hazard')
    # records imported before hearts were counted get them from the run's own journal
    data = json.loads((tmp / 'lib3' / 'maps' / 'Testland_Child.json').read_text())
    for rec in data['stuck']:
        rec.pop('life_lost', None)
    (tmp / 'lib3' / 'maps' / 'Testland_Child.json').write_text(json.dumps(data))
    n = lib.backfill_life()
    c = [k for k in lib.map('Testland_Child').clusters() if abs(k['at'][0] - 300) < 1.0]
    check(n >= 2 and c and c[0]['life_lost'] == 8 and c[0]['hazard'], f'backfill_life reads the hearts lost from the runs\' journals ({n} records; {c and c[0]["life_lost"]})')
    check(lib.backfill_life() == 0, 'and finds nothing more to do')
    lib_hz = routelib.RouteLib(tmp / 'lib-hz')
    r = FakeRun(tmp / 'hz1', 'hz1', start=(0, 100, 0))
    r.leg('run 0 60 radius 2.5 timeout 30', [(0, 100, 10)], 'stuck', detail='50.00 m from the point; moved under 0.3 m in 2.5 s at 0.0 100.0 10.0', hurt=8)
    lib_hz.import_run(r.write(), build='b1')
    check('HAZARD: 8 quarter hearts' in routelib.describe(lib_hz), 'the listing of a place that cost hearts says hazard')
    # an attempt belongs to the nearest cluster only: two places 2.8 m apart, one attempt at the first
    r = FakeRun(tmp / 's12', 's12', start=(400, 100, 0))
    r.leg('run 400 60 radius 2.5 timeout 30', [(400, 100, 10)], 'stuck', detail='50.00 m from the point; moved under 0.3 m in 2.5 s at 400.0 100.0 10.0')
    r.leg('run 400 60 radius 2.5 timeout 30', [(400, 100, 12.8)], 'stuck', detail='47.20 m from the point; moved under 0.3 m in 2.5 s at 400.0 100.0 12.8')
    lib.import_run(r.write(), build='b1')
    lib.record_attempt('Testland_Child', [400.0, 100.0, 10.0], 'shift-L-3', 'worked', 8.0, 'b1', 'x')
    c = sorted([k for k in lib.map('Testland_Child').clusters() if abs(k['at'][0] - 400) < 1.0], key=lambda k: k['at'][2])
    check(len(c) == 2 and c[0]['resolved'] and c[0]['worked'] == ['shift-L-3'] and not c[1]['resolved'] and c[1]['tried'] == [], f'an attempt at one place does not resolve the place 2.8 m away ({[(k["at"][2], k["resolved"], k["tried"]) for k in c]})')
    # clusters merge: two runs stuck at the same spot, in two builds, one cause
    r = FakeRun(tmp / 's10', 's10', start=(0, 100, 0))
    r.leg('run 0 60 radius 2.5 timeout 30', [(0, 100, 10.6)], 'stuck', detail='49.40 m from the point; moved under 0.3 m in 2.5 s at 0.0 100.0 10.6')
    lib.import_run(r.write(), build='b2')
    c = [k for k in lib.map('Testland_Child').clusters() if abs(k['at'][2] - 10.3) < 1.5 and abs(k['at'][0]) < 1.0]
    check(len(c) == 1 and c[0]['n'] == 2 and sorted(c[0]['builds']) == ['b1', 'b2'], f'the same spot in two runs and two builds is one cluster ({c and (c[0]["n"], c[0]["builds"])})')
    # attempts: a failed one is remembered, a worked one resolves
    lib.record_attempt('Testland_Child', c[0]['at'], 'side-left-25', 'failed', 0.2, 'b2', 'x')
    c = [k for k in lib.map('Testland_Child').clusters() if abs(k['at'][2] - 10.3) < 1.5 and abs(k['at'][0]) < 1.0]
    check(c[0]['tried'] == ['side-left-25'] and not c[0]['resolved'], f'a failed attempt is listed and resolves nothing ({c[0]["tried"]}, {c[0]["resolved"]})')
    lib.record_attempt('Testland_Child', c[0]['at'], 'side-right-25', 'worked', 6.0, 'b2', 'x')
    c = [k for k in lib.map('Testland_Child').clusters() if abs(k['at'][2] - 10.3) < 1.5 and abs(k['at'][0]) < 1.0]
    check(c[0]['resolved'] and 'side-right-25' in c[0]['worked'], f'a worked attempt resolves the cluster ({c[0]["resolved"]}, {c[0]["worked"]})')
    # resolved by a later run that walks past it
    lib2 = routelib.RouteLib(tmp / 'lib3b')
    r = FakeRun(tmp / 'p1', 'p1', start=(0, 100, 0))
    r.leg('run 0 60 radius 2.5 timeout 30', [(0, 100, 20)], 'stuck', detail='40.00 m from the point; moved under 0.3 m in 2.5 s at 0.0 100.0 20.0')
    lib2.import_run(r.write(), build='b1', ts='2026-11-16T10:00:00')
    k = lib2.map('Testland_Child').clusters()
    check(len(k) == 1 and not k[0]['resolved'], 'one open stuck point')
    r = FakeRun(tmp / 'p2', 'p2', start=(0, 100, 0))
    r.leg('run 0 60 radius 2.5 timeout 30', [(0, 100, 20), (0, 100, 40)], 'reached')
    lib2.import_run(r.write(), build='b2', ts='2026-11-16T11:00:00')
    k = lib2.map('Testland_Child').clusters()
    check(len(k) == 1 and k[0]['resolved'] and 'walked past' in k[0]['resolved_by'], f'a later run that walks past it resolves it ({k and (k[0]["resolved"], k[0].get("resolved_by"))})')
    # the contested edge: walked in the old build, stuck in the new one
    lib3 = routelib.RouteLib(tmp / 'lib3c')
    r = FakeRun(tmp / 'q1', 'q1', start=(0, 100, 0))
    r.leg('run 0 60 radius 2.5 timeout 30', [(0, 100, 60)], 'reached')
    lib3.import_run(r.write(), build='old', ts='2026-11-16T10:00:00')
    r = FakeRun(tmp / 'q2', 'q2', start=(0, 100, 0))
    r.leg('run 0 60 radius 2.5 timeout 30', [(0, 100, 30)], 'stuck', detail='30.00 m from the point; moved under 0.3 m in 2.5 s at 0.0 100.0 30.0')
    lib3.import_run(r.write(), build='new', ts='2026-11-16T12:00:00')
    g = lib3.map('Testland_Child').graph()
    check(g.stats()['contested'] > 0, f'an edge walked in the old build and stopped at in the new one is contested ({g.stats()})')


def target_checks(tmp):
    lib = routelib.RouteLib(tmp / 'lib4')
    r = FakeRun(tmp / 't1', 't1', start=(0, 100, 0))
    r.leg('run 0 40 radius 2.5 timeout 30', [(0, 100, 40)], 'reached')
    r.leg('run 0 100 radius 2.5 timeout 30', [(0, 100, 60)], 'stuck', detail='40.00 m from the point; moved under 0.3 m in 2.5 s at 0.0 100.0 60.0')
    lib.add_target('place-one', 'Testland_Child', 0.0, 100.0, age='child', radius=3.0, issue='1', label='the place')
    check(lib.frontier('place-one')['known'] is False, 'no data yet: the frontier is unknown')
    lib.import_run(r.write(), build='b1')
    f = lib.frontier('place-one')
    check(f['known'] and abs(f['pos'][2] - 60.0) < 1.0 and abs(f['remaining_m'] - 40.0) < 1.5 and not f['reached'], f'the frontier is the walked point nearest the target ({f})')
    check(f['anchor'] and f['anchor']['kind'] in ('start', 'placed'), f'it is joined to an anchor ({f.get("anchor")})')
    h = json.loads((tmp / 'lib4' / 'targets.json').read_text())['targets']['place-one']['history']
    check(len(h) == 1 and abs(h[0]['remaining_m'] - 40.0) < 1.5, f'the import wrote the first frontier into the history ({h})')
    # a walked point is not the frontier when it is not joined to an anchor: a track that starts after a jump is its own island
    r = FakeRun(tmp / 't2', 't2', start=(0, 100, 0))
    r.leg('run 0 10 radius 2.5 timeout 30', [(0, 100, 10)], 'reached')
    r.jump((0.0, 100.0, 93.0))
    r.leg('run 0 99 radius 2.5 timeout 30', [(0, 100, 99)], 'reached')
    st = lib.import_run(r.write(), build='b1')
    f = lib.frontier('place-one')
    check(abs(f['pos'][2] - 60.0) < 1.0 and st['frontier_gain'].get('place-one', 0) == 0, f'a point reached after a warp does not count: no way back to it ({f["pos"]}, {st["frontier_gain"]})')
    # a better run improves it and the import says by how much
    r = FakeRun(tmp / 't3', 't3', start=(0, 100, 0))
    r.leg('run 0 90 radius 2.5 timeout 30', [(0, 100, 90)], 'reached')
    st = lib.import_run(r.write(), build='b1')
    f = lib.frontier('place-one')
    check(abs(f['remaining_m'] - 10.0) < 1.5 and 28.0 < st['frontier_gain']['place-one'] < 32.0, f'a run that gets closer moves the frontier, and the gain is read ({f["remaining_m"]}, {st["frontier_gain"]})')
    r = FakeRun(tmp / 't4', 't4', start=(0, 100, 0))
    r.leg('run 0 99 radius 2.5 timeout 30', [(0, 100, 99)], 'reached')
    lib.import_run(r.write(), build='b1')
    f = lib.frontier('place-one')
    check(f['reached'] and f['remaining_m'] <= 3.0, f'within the radius the target is reached ({f})')
    # a cover target over legs
    lib.add_cover('legs', 'Testland_Child', [[0, 20], [0, 50], [30, 30], [60, 60]], age='child', radius=3.0, issue='2')
    cv = lib.frontier('legs')
    check(cv['kind'] == 'cover' and cv['reached_n'] == 2 and cv['n'] == 4 and sorted(cv['unreached']) == [[30, 60 - 30], [60, 60]], f'a cover target counts the legs the library walked ({cv.get("reached_n")} of {cv.get("n")}, left {cv.get("unreached")})')
    # a target on a map the library lacks
    lib.add_target('far', 'Nowhere_Child', 1.0, 1.0)
    check(lib.frontier('far')['known'] is False, 'a target on an unknown map has no frontier')


def route_checks(tmp):
    lib = routelib.RouteLib(tmp / 'lib5')
    # an L-shaped walk: (0,0) -> (0,40) -> (40,40) -> and a stuck at (40,60)
    r = FakeRun(tmp / 'r1', 'r1', start=(0, 100, 0))
    r.leg('run 0 40 radius 2.5 timeout 30', [(0, 100, 40)], 'reached')
    r.leg('run 40 40 radius 2.5 timeout 30', [(40, 100, 40)], 'reached')
    r.leg('run 40 100 radius 2.5 timeout 30', [(40, 100, 60)], 'stuck', detail='40.00 m from the point; moved under 0.3 m in 2.5 s at 40.0 100.0 60.0')
    lib.import_run(r.write(), build='b1')
    w = FakeWorld()
    rt = lib.route('Testland_Child', (0.3, 100.0, 0.2), (40.0, 40.0), age='child', radius=2.5)
    check(rt['ok'] and rt['complete'] and rt['source'] == 'library', f'a goal on the walked ground is a complete library route ({rt.get("complete")})')
    check(abs(rt['length_m'] - 80.0) < 4.0 and 2 <= len(rt['waypoints']) <= 8, f'its length is the walk ({rt["length_m"]}, {len(rt["waypoints"])} waypoints)')
    check(all(s.startswith('run ') for s in rt['steps']) and rt['steps'][-1].split()[1:3] != ['0', '0'], f'steps are run lines ({rt["steps"]})')
    last = [float(v) for v in rt['steps'][-1].split()[1:3]]
    check(math.dist(last, (40, 40)) < 3.0, f'the last step is near the goal ({last})')
    # beyond the frontier: the goal at (40, 200): library to the stuck point, then the world's plan
    rt = lib.route('Testland_Child', (0, 100, 0), (40.0, 200.0), age='child', radius=2.5, world=w)
    check(rt['ok'] and not rt['complete'] and abs(rt['frontier']['pos'][2] - 60.0) < 1.5, f'the library runs to the frontier ({rt["frontier"]})')
    check(len(w.plan_calls) == 1 and abs(w.plan_calls[0][1][1] - 60.0) < 1.5 and w.plan_calls[0][2] == (40.0, 200.0), f'the world plans from the frontier to the goal ({w.plan_calls})')
    check(rt['beyond']['ok'] and rt['steps'][-1].startswith('run 40.00 200.00'), f'its steps follow the library steps ({rt["steps"][-2:]})')
    check(rt['known_m'] > 80 and rt['beyond_m'] > 100, f'known and beyond metres ({rt["known_m"]}, {rt["beyond_m"]})')
    # a world that cannot plan beyond: the answer keeps its why, the library part still runs
    w.plan_result = {'ok': False, 'why': 'not-connected', 'detail': 'no link', 'near': [40.0, 62.0], 'steps': [], 'waypoints': []}
    rt = lib.route('Testland_Child', (0, 100, 0), (40.0, 200.0), age='child', radius=2.5, world=w)
    check(not rt['ok'] and rt['why'] == 'not-connected' and rt['steps'] and rt['beyond']['why'] == 'not-connected', f'beyond cannot be planned: the route says why and keeps the known part ({rt["why"]}, {len(rt["steps"])} steps)')
    # a plan beyond that leads back, away from the goal (the mesh's reachable point nearest the goal is behind the frontier): its steps are not played
    w.plan_result = {'ok': False, 'why': 'not-connected', 'detail': 'no link', 'near': [40.0, 20.0], 'steps': ['run 40.00 20.00 radius 2.5'], 'waypoints': [[40.0, 20.0]]}
    rt = lib.route('Testland_Child', (0, 100, 0), (40.0, 200.0), age='child', radius=2.5, world=w)
    check(rt['steps'] == rt['lib_steps'] and not any('run 40.00 20.00' in x for x in rt['steps']) and rt['why'] == 'not-connected', f'beyond steps that lead away from the goal are left out ({rt["steps"][-2:]})')
    pw0 = routelib.planner(lib, w.plan, age='child')
    # off the library: start far from any node: the world plans alone
    w.plan_result = None
    w.plan_calls.clear()
    rt = lib.route('Testland_Child', (300, 100, 300), (40.0, 40.0), age='child', radius=2.5, world=w)
    check(rt['source'] == 'world' and rt['why_library'] == 'off-library' and len(w.plan_calls) == 1, f'a start off the library is planned by the world alone ({rt["source"]}, {rt.get("why_library")})')
    rt = lib.route('Testland_Child', (300, 100, 300), (40.0, 40.0), age='child', radius=2.5)
    check(not rt['ok'] and rt['why'] == 'off-library', f'with no world model: off-library ({rt["why"]})')
    # an avoided place makes the route go another way when there is one: a second path around
    r = FakeRun(tmp / 'r2', 'r2', start=(0, 100, 0))
    r.leg('run 60 0 radius 2.5 timeout 30', [(60, 100, 0)], 'reached')
    r.leg('run 60 40 radius 2.5 timeout 30', [(60, 100, 40)], 'reached')
    r.leg('run 40 40 radius 2.5 timeout 30', [(40, 100, 40)], 'reached')
    lib.import_run(r.write(), build='b1')
    direct = lib.route('Testland_Child', (0, 100, 0), (40.0, 40.0), age='child', radius=2.5)
    around = lib.route('Testland_Child', (0, 100, 0), (40.0, 40.0), age='child', radius=2.5, avoid=[(0.0, 20.0, 4.0)])
    check(abs(direct['length_m'] - 80) < 5 and abs(around['length_m'] - 120) < 6, f'avoiding the first path takes the longer one ({direct["length_m"]}, {around["length_m"]})')
    check(any(abs(float(s.split()[1]) - 60) < 3 for s in around['steps']) and not any(abs(float(s.split()[1])) < 2 and float(s.split()[2]) > 25 for s in around['steps']), f'the long way goes by x 60 and not up the avoided first path ({around["steps"]})')
    # an open stuck cluster costs: with only the stuck way the route still goes (the cost is not a wall)
    rt = lib.route('Testland_Child', (0, 100, 0), (40.0, 60.0), age='child', radius=2.5)
    check(rt['ok'], 'a stuck place is a cost, not a wall')
    # the planner wrapper has the planner's own shape
    pw = routelib.planner(lib, w.plan, age='child')
    w.plan_calls.clear()
    out = pw('Testland_Child', (0.0, 0.0), (40.0, 40.0), from_y=100.0, to_y=100.0, radius=2.5)
    check(out['ok'] and out['steps'] and out['source'] == 'library' and 'waypoints' in out and not w.plan_calls, f'the wrapped planner answers from the library and never asks the world when it is complete ({out["source"]})')
    out = pw('Testland_Child', (0.0, 0.0), (40.0, 200.0), from_y=100.0, to_y=None, radius=2.5)
    check(out['steps'] and len(w.plan_calls) == 1, f'beyond the library the wrapped planner asks the world ({len(w.plan_calls)} calls)')
    seen = []
    pw2 = routelib.planner(lib, lambda a, f, t, **k: (seen.append(k), w.plan(a, f, t, **k))[1], age='child')
    pw2('Testland_Child', (0.0, 0.0), (40.0, 200.0), from_y=100.0, to_y=None, radius=2.5, doors='through')
    check(seen and seen[0].get('doors') == 'through', f'the caller\'s own options reach the world model\'s plan ({seen[:1]})')
    out = pw('Elsewhere_Child', (0.0, 0.0), (40.0, 40.0), from_y=100.0, to_y=100.0, radius=2.5)
    check(w.plan_calls[-1][0] == 'Elsewhere_Child', f'a map the library lacks goes to the world model straight ({w.plan_calls[-1]})')


class WalledWorld:
    """A flat map with walls (axis-aligned rectangles in x, z): Link's `run x z radius r timeout t` goes straight, stops at a wall ('stuck') or arrives.
    A push after each leg (drift) moves him sideways by `drift` metres."""

    def __init__(self, walls, pos=(0.0, 100.0, 0.0), drift=0.0, map='Testland_Child'):
        self.walls, self.pos, self.drift, self.map, self.sent, self.leg_n = walls, list(pos), drift, map, [], 0
        self.recorded = []

    def blocked(self, x, z):
        return any(x0 <= x <= x1 and z0 <= z <= z1 for (x0, z0, x1, z1) in self.walls)

    def send(self, line):
        self.sent.append(line)
        w = line.split()
        if w[0] not in ('run', 'walk'):
            return {'ev': 'step', 'src': line, 'result': 'done', 'pos': list(self.pos), 'moved': 0.0, 'secs': 0.1}
        x, z, rad = float(w[1]), float(w[2]), float(w[w.index('radius') + 1]) if 'radius' in w else 1.5
        x0, z0 = self.pos[0], self.pos[2]
        d = math.dist((x0, z0), (x, z))
        n = max(1, int(d / 0.25))
        moved = 0.0
        res = 'reached'
        for i in range(1, n + 1):
            if math.dist((self.pos[0], self.pos[2]), (x, z)) <= rad:
                break
            px, pz = x0 + (x - x0) * i / n, z0 + (z - z0) * i / n
            if self.blocked(px, pz):
                res = 'stuck'
                break
            self.pos[0], self.pos[2] = px, pz
            moved = math.dist((x0, z0), (px, pz))
        self.leg_n += 1
        if res == 'reached' and self.drift:
            self.pos[0] += self.drift
        dd = math.dist((self.pos[0], self.pos[2]), (x, z))
        return {'ev': 'step', 'src': line, 'result': res, 'pos': [round(c, 2) for c in self.pos], 'moved': round(moved, 2), 'secs': round(moved / 6 + 0.1, 2),
                'detail': f'{dd:.2f} m from the point' + ('; moved under 0.3 m in 2.5 s at %.1f %.1f %.1f' % tuple(self.pos) if res == 'stuck' else '')}

    def state(self):
        return {'pos': list(self.pos), 'map': self.map, 'event': 0, 'loading': 0}


def walker_checks(tmp):
    lib = routelib.RouteLib(tmp / 'lib6')
    # the library knows a walk (0,0) -> (0,40) -> (40,40) -> (40,80); the made-up world has no wall on it
    r = FakeRun(tmp / 'w1', 'w1', start=(0, 100, 0))
    r.leg('run 0 40 radius 2.5 timeout 30', [(0, 100, 40)], 'reached')
    r.leg('run 40 40 radius 2.5 timeout 30', [(40, 100, 40)], 'reached')
    r.leg('run 40 80 radius 2.5 timeout 30', [(40, 100, 80)], 'reached')
    lib.import_run(r.write(), build='b1')
    io = WalledWorld([], pos=(0.2, 100, 0.1))
    recs = []
    wk = routelib.Walker(lib, io, map='Testland_Child', age='child', tol=3.0, record=recs.append)
    res = wk.go((40.0, 80.0), goal_radius=3.0)
    check(res['ok'] and res['stopped'] == 'reached' and res['replans'] == 0 and math.dist((io.pos[0], io.pos[2]), (40, 80)) <= 3.0, f'the walker plays the library route to the goal ({res})')
    check(len(io.sent) >= 3 and all(s.startswith('run ') and 'timeout' in s for s in io.sent), f'it sends run lines with a timeout ({io.sent[:3]})')
    # a drift of 5 m to the side after each leg: the walker sees it and re-plans from the live position
    io = WalledWorld([], pos=(0.2, 100, 0.1), drift=5.0)
    wk = routelib.Walker(lib, io, map='Testland_Child', age='child', tol=3.0, record=recs.append)
    res = wk.go((40.0, 80.0), goal_radius=3.0)
    check(res['replans'] >= 1 and res['drifts'] >= 1, f'a push off the line makes the walker plan again from where Link is ({res})')
    # a wall across the known path: stuck, recorded, re-planned, the same leg three times, then blocked at the wall
    io = WalledWorld([(-5, 20, 5, 22)], pos=(0.2, 100, 0.1))
    recs.clear()
    wk = routelib.Walker(lib, io, map='Testland_Child', age='child', tol=3.0, record=recs.append, max_replans=3)
    res = wk.go((40.0, 80.0), goal_radius=3.0)
    check(not res['ok'] and res['stopped'] == 'blocked' and abs(res['blocked_at'][2] - 19.7) < 1.5, f'a wall that was not there: blocked at it ({res.get("stopped")}, {res.get("blocked_at")})')
    check(len(recs) >= 1 and recs[0]['result'] == 'stuck' and recs[0]['want'][0] is not None, f'every stuck leg is recorded as it happens ({len(recs)})')
    check(res['replans'] <= 3 + 1, f'it does not go round forever ({res["replans"]})')
    # at the end of the known part the walker stops and says frontier
    io = WalledWorld([], pos=(0.2, 100, 0.1))
    wk = routelib.Walker(lib, io, map='Testland_Child', age='child', tol=3.0, record=recs.append)
    res = wk.go((40.0, 160.0), goal_radius=3.0)
    check(res['stopped'] == 'frontier' and abs(res['pos'][2] - 80.0) < 3.5, f'the known part is played and the walker stops at the frontier ({res["stopped"]}, {res["pos"]})')
    # a map change during a leg stops it
    class Changing(WalledWorld):
        def send(self, line):
            ev = super().send(line)
            if len(self.sent) == 2:
                self.map = 'Other_Child'
            return ev
    io = Changing([], pos=(0.2, 100, 0.1))
    wk = routelib.Walker(lib, io, map='Testland_Child', age='child', tol=3.0, record=recs.append)
    res = wk.go((40.0, 80.0), goal_radius=3.0)
    check(res['stopped'] == 'map-changed', f'a load during the route ends it ({res["stopped"]})')


def store_checks(tmp):
    lib = routelib.RouteLib(tmp / 'lib7')
    r = FakeRun(tmp / 'z1', 'z1', start=(0, 100, 0))
    r.leg('run 0 40 radius 2.5 timeout 30', [(0, 100, 40)], 'reached')
    lib.import_run(r.write(), build='b1')
    lib.add_target('t', 'Testland_Child', 0.0, 80.0)
    files = sorted(p.name for p in (tmp / 'lib7').rglob('*') if p.is_file())
    check(set(files) == {'lock', 'runs.json', 'targets.json', 'Testland_Child.json'}, f'files: {files}')
    check(not any(f.endswith('.tmp') for f in files), 'no temp file is left')
    lib2 = routelib.RouteLib(tmp / 'lib7')
    a, b = lib.map('Testland_Child'), lib2.map('Testland_Child')
    check(a.tracks == b.tracks and a.graph().stats() == b.graph().stats(), 'a second library object reads the same map')
    check(lib2.frontier('t')['known'], 'targets reload')
    data = json.loads((tmp / 'lib7' / 'maps' / 'Testland_Child.json').read_text())
    check(data['format'] == routelib.FORMAT and data['map'] == 'Testland_Child', f'format and map name in the file ({data["format"]})')
    check(routelib.RouteLib(tmp / 'lib7-new').maps() == [], 'a new library is empty')
    # a bad format is refused
    (tmp / 'lib8' / 'maps').mkdir(parents=True)
    (tmp / 'lib8' / 'maps' / 'X_Child.json').write_text(json.dumps({'format': 'other/9', 'map': 'X_Child'}))
    try:
        routelib.RouteLib(tmp / 'lib8').map('X_Child')
        check(False, 'a file of another format is refused')
    except routelib.LibError as e:
        check('format' in str(e), f'a file of another format is refused ({e})')
    # importing a folder with no state is an error that says so
    (tmp / 'empty').mkdir()
    try:
        lib.import_run(tmp / 'empty')
        check(False, 'a folder with no run is refused')
    except routelib.LibError as e:
        check('state.jsonl' in str(e), f'a folder with no run is refused ({e})')
    # a build from built-from.txt when the log has none
    r = FakeRun(tmp / 'z2' / 'x', 'z2', start=(0, 100, 0), copy=str(tmp / 'copyz'))
    r.leg('run 0 10 radius 2.5 timeout 30', [(0, 100, 10)], 'reached')
    (tmp / 'copyz').mkdir()
    (tmp / 'copyz' / 'built-from.txt').write_text('17c44b80f69a7088e38ce93757fa5749330a997e\n')
    st = lib.import_run(r.write())
    check(st['build'] == '17c44b80f', f'the build falls back to the copy\'s built-from ({st["build"]})')
    # a co-op observer's journal ({w, frame, game: {...}}) is read as it is, with no steps
    live = tmp / 'obs' / 'A'
    live.mkdir(parents=True)
    rows = []
    for i in range(60):
        rows.append({'w': 1.0 + i * 0.1, 'frame': 100 + i * 6, 'game': {'t': 500.0 + i * 0.1, 'frame': 100 + i * 6, 'map': 'Testland_Adult', 'pos': [0.0, 100.0, i * 0.6], 'facing': 0.0, 'camera': 180.0,
                                                                       'event': False, 'loading': False, 'age': 'adult', 'life': 16}})
    (live / 'state.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in rows))
    # (then a load with loading rows, after 36 m of walking: a walked link seen in a journal that has no steps; a change with no load rows is no link)
    mono = 500.0 + 60 * 0.1
    for i in range(6):
        rows.append({'w': 9.0 + i * 0.1, 'frame': 500 + i * 6, 'game': {'t': mono + i * 0.1, 'frame': 500 + i * 6, 'map': 'Testland_Adult', 'pos': [0.0, 100.0, 36.0], 'event': False, 'loading': True, 'age': 'adult'}})
    for i in range(30):
        rows.append({'w': 10.0 + i * 0.1, 'frame': 540 + i * 6, 'game': {'t': mono + 1.0 + i * 0.1, 'frame': 540 + i * 6, 'map': 'Seenland_Adult', 'pos': [3.0, 100.0, i * 0.6], 'event': False, 'loading': False, 'age': 'adult'}})
    rows.append({'w': 20.0, 'frame': 800, 'game': {'t': mono + 5.0, 'frame': 800, 'map': 'Jumpland_Adult', 'pos': [90.0, 100.0, 90.0], 'event': False, 'loading': False, 'age': 'adult'}})
    for i in range(10):
        rows.append({'w': 21.0 + i * 0.1, 'frame': 810 + i * 6, 'game': {'t': mono + 5.1 + i * 0.1, 'frame': 810 + i * 6, 'map': 'Jumpland_Adult', 'pos': [90.0, 100.0, 90.0 + i * 0.6], 'event': False, 'loading': False, 'age': 'adult'}})
    (live / 'state.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in rows))
    st = lib.import_run(live, build='obs')
    seen = [l for l in lib.links() if l['via'] == 'seen']
    check(len(seen) == 1 and seen[0]['from_map'] == 'Testland_Adult' and seen[0]['to_map'] == 'Seenland_Adult' and not any(l['to_map'] == 'Jumpland_Adult' for l in lib.links()), f'a load seen after a walk is a link even with no steps; a change with no load is none ({[ (l["to_map"], l["via"]) for l in lib.links()]})')
    live2 = tmp / 'obs2' / 'B'
    live2.mkdir(parents=True)
    rows2 = [{'w': 1.0 + i * 0.1, 'frame': 100 + i * 6, 'game': {'t': 900.0 + i * 0.1, 'frame': 100 + i * 6, 'map': 'Gapland_Adult', 'pos': [0.0, 100.0, i * 0.7], 'event': False, 'loading': False, 'age': 'adult'}} for i in range(70)]
    rows2 += [{'w': 9.0 + i * 0.1, 'frame': 600 + i * 6, 'game': {'t': 906.0 + 3.2 + i * 0.1, 'frame': 600 + i * 6, 'map': 'Beyond_Adult', 'pos': [5.0, 100.0, i * 0.6], 'event': False, 'loading': False, 'age': 'adult'}} for i in range(20)]
    (live2 / 'state.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in rows2))
    lib.import_run(live2, build='obs')
    check(any(l['from_map'] == 'Gapland_Adult' and l['to_map'] == 'Beyond_Adult' and l['via'] == 'seen' for l in lib.links()), 'a 3 s gap in the samples with a map change after a long walk is a load seen (observer journals carry no loading rows)')
    ta = lib.map('Testland_Adult').tracks
    check(len(ta) == 1 and ta[0]['age'] == 'adult' and st['metres'] > 30 and st['run'].startswith('obs-A'), f'an observer journal is imported as a track with no steps ({st.get("run")}, {st.get("metres")})')
    # the summary of what is known per map
    txt = routelib.describe(lib)
    check('Testland_Child' in txt and 'metres' in txt and 'stuck' in txt, f'describe lists each map with what is known ({txt[:200]!r})')


def run():
    with tempfile.TemporaryDirectory(prefix='test-routelib-') as t:
        tmp = Path(t)
        import_checks(tmp)
        graph_checks(tmp)
        stuck_checks(tmp)
        target_checks(tmp)
        route_checks(tmp)
        walker_checks(tmp)
        store_checks(tmp)


def main():
    run()
    if FAILS:
        raise SystemExit(f'test_routelib: {len(FAILS)} of {CHECKS[0]} checks FAILED')
    print(f'test_routelib: all {CHECKS[0]} checks passed')


if __name__ == '__main__':
    main()
