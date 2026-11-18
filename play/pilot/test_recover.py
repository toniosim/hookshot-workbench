#!/usr/bin/env python3
"""The pilot's stuck recovery, its guard in front of the decider, its bad-point memory and its human-like movement, without
the game: a fake game side (a thread that reads steps.txt and writes out.jsonl as the live channel does) walks Link on a flat
plane with posts, walls and low fences in it, takes 2.5 s of game time to find out it is stuck, and answers the roll, the
hop (a jump with the stick held) and the look-around the pilot sends.

    python3 test_recover.py

Run by test_pilot.py through run(). No game, no network, no model: the deciders here are counters and the rules.
"""
import json
import math
import os
import re
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import deciders  # noqa: E402
import humanize  # noqa: E402
import pilot  # noqa: E402
import recover  # noqa: E402
import tactics  # noqa: E402

RUN_MPS = 5     # the fake Link's running speed
BODY_M = 0.4      # how close to an obstacle's edge he can get


def check(cond, what):
    if not cond:
        raise SystemExit(f'FAILED: {what}')
    print(f'ok: {what}')


# ---- the fake game side

class Post:
    def __init__(self, x, z, r=1):
        self.x, self.z, self.r, self.low = x, z, r, False

    def clear(self, p):
        return math.hypot(p[0] - self.x, p[1] - self.z) - (self.r + BODY_M)


class Wall:
    """A fence from (ax, az) to (bx, bz); `low` ones can be jumped."""

    def __init__(self, a, b, low=False):
        self.a, self.b, self.low = a, b, low

    def clear(self, p):
        return recover.seg_dist(p, self.a, self.b)[0] - BODY_M


class FakeWorld(threading.Thread):
    """Link on a plane from `start` (x, z), camera along +z. A walk moves in a straight line until an obstacle is in the way
    (it then ends stuck after 2.5 s, as the real walk step reports it) or the radius is reached; sidestep, roll and hop are
    moves of their own length; the flag Final_Reached is set when Link is within 3 m of `final`."""

    def __init__(self, live, start=(0, 0), obstacles=(), final=None, area='Fake_Area', stop_short=0):
        super().__init__(daemon=True)
        self.live = Path(live)
        self.x, self.z = start
        self.obstacles, self.final, self.area = list(obstacles), final, area
        self.stop_short = stop_short   # a walk ends this far before its radius says (a planner that stops short)
        self.t, self.n, self.tick, self.lines = 0, 0, 0, 0
        self.watch, self.flags, self.stop = [], {'Final_Reached': 0}, False
        self.log = []   # every step line received, in order

    def emit(self, **e):
        with open(self.live / 'out.jsonl', 'a') as f:
            f.write(json.dumps(e) + '\n')

    def state(self, last):
        self.tick += 6
        if self.final and math.hypot(self.x - self.final[0], self.z - self.final[1]) < 3:
            self.flags['Final_Reached'] = 1
        self.emit(ev='state', why='wait', n=self.tick, t=round(self.t, 2), frame=self.tick, **{'in': self.lines},
                  pos=[self.x, 100, self.z], facing=0, camera=0, area=self.area, prompt='Empty', music='BGM_Fake',
                  scene=False, event=0, loading=0, life=12, max_life=12, rupees=0, last=last,
                  flags={k: self.flags.get(k) for k in self.watch}, changed=[])

    def collides(self, a, b, low_ok):
        for o in self.obstacles:
            if o.low and low_ok:
                continue
            cn, cp = o.clear(b), o.clear(a)
            if cn < 0 and cn < cp - 1e-9:
                return True
        return False

    def advance(self, dx, dz, dist, low_ok=False):
        """Move up to dist along the unit (dx, dz) in steps of 0.1 m; returns (moved, hit)."""
        cur, moved = (self.x, self.z), 0
        while moved < dist - 1e-9:
            step = min(0.1, dist - moved)
            nxt = (cur[0] + dx * step, cur[1] + dz * step)
            if self.collides(cur, nxt, low_ok):
                self.x, self.z = cur
                return moved, True
            cur, moved = nxt, moved + step
        self.x, self.z = cur
        return moved, False

    def walk(self, x, z, radius):
        d = math.hypot(x - self.x, z - self.z)
        if d <= radius:
            return 'reached', 0, f'{d:.2f} m from the point'
        radius += self.stop_short
        dx, dz = (x - self.x) / d, (z - self.z) / d
        moved, hit = self.advance(dx, dz, max(0, d - radius))
        self.t += moved / RUN_MPS
        left = math.hypot(x - self.x, z - self.z)
        if hit:
            self.t += 2.5
            return 'stuck', moved, f'{left:.2f} m from the point; moved under 0.3 m in 2.5 s at {self.x:.1f} 0 {self.z:.1f}'
        return 'reached', moved, f'{left:.2f} m from the point'

    def step(self, src):
        w = src.split()
        result, moved, detail = 'done', 0, ''
        if w[0] in ('walk', 'run'):
            kw = dict(zip(w[3::2], w[4::2])) if len(w) > 3 and not w[3][0].isdigit() else {}
            result, moved, detail = self.walk(float(w[1]), float(w[2]), float(kw.get('radius', w[3] if len(w) > 3 and not kw else 1)))
        elif w[0] == 'wait':
            self.t += float(w[1])
        elif w[0] == 'roll':
            ang = {n: a for a, n in humanize.DIRS}[w[1]]
            yaw = math.radians(-ang)   # camera 0, handedness +1
            moved, _ = self.advance(math.sin(yaw), math.cos(yaw), 2.8)
            self.t += 0.6
        elif w[0] == 'raw':
            m = re.search(r'LX=(-?\d+)\+LY=(-?\d+)/\d+,[0-9.]+:X/', w[1])
            if m:   # a hop: the stick toward a world yaw (camera 0), then X
                lx, ly = int(m.group(1)), int(m.group(2))
                yaw = -math.atan2(lx, ly)
                moved, _ = self.advance(math.sin(yaw), math.cos(yaw), 2.4, low_ok=True)
                self.t += 1
            else:
                self.t += float(w[-1])
        elif w[0] == 'until':
            name, _, val = w[2].partition('=')
            result = 'met' if str(self.flags.get(name)) == val else 'timeout'
            self.t += 0.1 if result == 'met' else float(w[w.index('timeout') + 1]) if 'timeout' in w else 1
        self.n += 1
        return {'ev': 'step', 'n': self.n, 'in': self.lines, 'src': src, 'result': result, 'secs': 1,
                'moved': round(moved, 2), 'pos': [self.x, 100, self.z], 'detail': detail, 't': round(self.t, 2)}

    def run(self):
        off, buf = 0, ''
        self.emit(ev='gameplay', t=0)
        self.state(None)
        waiting = True
        while not self.stop:
            data = (self.live / 'steps.txt').read_text()[off:]
            off += len(data)
            buf += data
            *whole, buf = buf.split('\n')
            last = None
            for line in whole:
                self.lines += 1
                w = line.split()
                if not w:
                    continue
                if w[0] == 'watch':
                    self.watch += w[1:]
                elif w[0] == 'end':
                    self.emit(ev='done', t=round(self.t, 2))
                    return
                else:
                    self.log.append(line)
                    e = self.step(line)
                    self.emit(**e)
                    last = {'src': e['src'], 'result': e['result'], 'moved': e['moved'], 'detail': e['detail']}
                    waiting = False
            if not waiting and last:
                self.state(last)
                waiting = True
            time.sleep(0.005)


def segment_text(targets, area='Fake_Area', max_decisions=120, extra=''):
    """A reach segment: the flag Final_Reached is set by the fake world when Link gets to its final point."""
    ts = ', '.join(f'{{name = "{n}", at = [{x}, {z}], kind = "reach", radius = {r}}}' for n, x, z, r in targets)
    return (f'name = "fake-recover"\nwhat = "made-up"\narea = "{area}"\nbudget_seconds = 900\nmax_decisions = {max_decisions}\n{extra}\n'
            f'[[goal]]\nname = "loop"\nflag = "Final_Reached=1"\nkind = "reach"\ntargets = [{ts}]\n')


class Counter:
    """A decider that counts the questions it is asked and answers by the rules (or by a fixed label)."""
    name = 'counter'
    stop_reason = None

    def __init__(self, label=None):
        self.asked, self.label, self.rules = 0, label, deciders.Rules()
        self.seen = []

    def choose(self, ctx):
        self.asked += 1
        self.seen.append([c.label for c in ctx.candidates])
        if self.label and self.label in [c.label for c in ctx.candidates]:
            return deciders.Choice(self.label, info={'request': {}})
        c = self.rules.choose(ctx)
        c.info = {'request': {}}
        return c


class StubPlanner:
    def __init__(self):
        self.calls, self.tried = 0, []

    def plan(self, seg, goals, tried):
        self.calls += 1
        self.tried.append(list(tried))
        names = [t.name for g in goals for t in g.targets]
        return ({'order': [g.name for g in goals], 'targets': [], 'drop': [], 'reason': 'stub'},
                {'request': {}, 'answer_text': '', 'latency_ms': 1, 'usage': None, 'cost_usd': 0, 'names': names})


def play(tmp, targets, obstacles, decider=None, start=(0, 0), final=None, recovery=True, human=None, bad=None, planner=None,
         plan=None, stop_short=0, max_decisions=120, area='Fake_Area', follows=None, extra='', eyes=None, tactics=None, hud=None):
    """One pilot run against a FakeWorld: (pilot, outcome, world, run_dir). hud: a function of the live folder that makes the Hud."""
    tmp = Path(tmp)
    seg_path = tmp / f'seg-{time.time_ns()}.toml'
    seg_path.write_text(segment_text(targets, area, max_decisions, extra))
    seg = pilot.Segment(seg_path)
    live = tmp / f'live-{time.time_ns()}'
    ch = pilot.Channel(live)
    ch.send(pilot.watch_lines(seg.watch))
    world = FakeWorld(live, start, obstacles, final or (targets[-1][1], targets[-1][2]), area, stop_short)
    world.start()
    assert ch.wait(lambda e: e['ev'] == 'gameplay', 5)
    st = ch.wait(lambda e: e['ev'] == 'state' and e['why'] == 'wait', 5)
    run_dir = tmp / f'run-{time.time_ns()}'
    run_dir.mkdir()
    p = pilot.Pilot(seg, decider or deciders.Rules(), ch, run_dir, run_dir.name, lambda: True, planner, max_decisions,
                    follows=follows, recovery=True if recovery else None, human=human, bad=bad, eyes=eyes, tactics=tactics,
                    **({'hud': hud(live)} if hud else {}))
    p.plan = plan
    outcome = p.run(st)
    ch.send(['end'])
    ch.wait(lambda e: e['ev'] == 'done', 5)
    return p, outcome, world, run_dir


def rows(run_dir, kind=None):
    out = [json.loads(x) for x in (run_dir / 'transcript.jsonl').read_text().splitlines()]
    return [r for r in out if kind is None or r['kind'] == kind]


def stuck_steps(world_log_events):
    return sum(1 for e in world_log_events if e['ev'] == 'step' and e['result'] == 'stuck')


def stuck_results(p):
    return sum(t['result'] == 'stuck' for t in p.tried)


# ---- unit checks: the monitor, the memory, the guard, the ladder, the shaping

def progress_checks():
    pr = recover.Progress()
    pr.anchor(0, (0, 0), 40)
    v = pr.observe(8, (0, 30), 10, 'reached', 30, None, 2.5)
    check(not v['stuck'] and pr.gained, 'ground gained (40 m to 10 m) is progress')
    v = pr.observe(10.5, (0, 30), 10, 'stuck', 0, 5, 2.5)
    check(v['stuck'] and v['why'] == 'blocked' and not pr.gained, 'a travel step that ended stuck is a block at once')
    pr = recover.Progress()
    pr.anchor(13, (0, 30), 10)
    v = pr.observe(14, (0, 30), 10, 'reached', 0, 0.5, 2.5)
    v = pr.observe(15, (0, 30), 10, 'reached', 0, 0.5, 2.5)
    check(not v['stuck'] and v['stalled_obs'] == 2, 'two steps without ground are not yet no-progress')
    v = pr.observe(16, (0, 30), 10, 'reached', 0, 0.5, 2.5)
    check(v['stuck'] and v['why'] == 'no-progress', 'three steps without ground are')
    pr = recover.Progress()
    pr.anchor(0, (0, 0), 12)
    pr.observe(2, (0, 0), 12, 'reached', 0, 0, 2.5)
    v = pr.observe(14, (0, 0), 12, 'reached', 0, 0, 2.5)
    check(v['stuck'] and v['stalled_s'] >= 10, 'two steps over a window of 10 s of game time are no-progress too')
    pr = recover.Progress()
    pr.anchor(0, (0, 0), 40)
    v = pr.observe(4, (0, 33), 7, 'reached', 33, 0, 2.5)
    pr.anchor(4, (0, 33), 7)
    v = pr.observe(5, (0, 33), 3.2, 'reached', 0, 0, 2.5)
    check(v['short'] and not v['stuck'] and v['why'] == 'short', 'reached at a stand-off point beyond the target\'s radius is `short`')
    check(not pr.observe(6, (0, 33), 3.2, 'held', 0, None, 2.5)['stuck'], 'a step held by an event says nothing')
    # a step that ended stuck INSIDE the target's radius (a door's placement point, a chest, a person) is an arrival, not a block: the ladder
    # has nothing to climb there (pi-solo-2a: 24 sidesteps in a row at a door frame, each "recovered" by arriving, each followed by the same block)
    pr = recover.Progress()
    pr.anchor(0, (0, 0), 12)
    v = pr.observe(3, (0, 10.7), 1.3, 'stuck', 0.2, 2.0, 1.5)
    check(not v['stuck'] and pr.gained and v['why'] is None, f'stuck 1.3 m from a target of radius 1.5 is no block: {v}')
    v = pr.observe(6, (0, 10.7), 1.3, 'stuck', 0.0, 2.0, 1.5)
    check(not v['stuck'] and v['stalled_obs'] == 0, 'and again: no ladder, no stalled count')
    pr = recover.Progress()
    pr.anchor(0, (0, 7.5), 4.5)
    v = pr.observe(3, (0, 8.0), 4.0, 'stuck', 0.2, 2.0, 1.5)
    check(v['stuck'] and v['why'] == 'blocked' and not pr.gained, 'stuck 4 m from a target of radius 1.5 is still a block')
    check(recover.is_blocked('stuck', 0, None) and not recover.is_blocked('stuck', 5, 0.4) and
          recover.is_blocked('timeout', 0.5, 3) and not recover.is_blocked('timeout', 20, 1) and
          not recover.is_blocked('reached', 0, 0), 'what counts as blocked: stuck a metre or more short, a timeout that gained nothing')


def badpoints_checks(tmp):
    bad = recover.BadPoints(tmp / 'cache-a')
    check(bad.load('Map_One') == [] and not (tmp / 'cache-a').exists(), 'no file is made by reading')
    e = bad.add('Map_One', 10, 20, 'soft', why='blocked by go', run='r1', target='t1', fix='sidestep-left')
    check((tmp / 'cache-a' / 'badpoints-Map_One.json').exists() and e['radius'] == 1.5 and e['kind'] == 'soft', 'one file per map, soft radius 1.5')
    bad.add('Map_Two', 1, 2, 'bad')
    check(bad.load('Map_Two') and bad.load('Map_One')[0]['x'] == 10 and len(bad.load('Map_One')) == 1, 'maps do not mix')
    e = bad.add('Map_One', 10.8, 20, 'bad', why='no rung got past it', run='r2')
    check(len(bad.load('Map_One')) == 1 and e['count'] == 2 and e['kind'] == 'bad' and e['radius'] == 2.5 and e['fix'] == 'sidestep-left' and
          abs(e['x'] - 10.4) < 1e-6 and e['runs'] == ['r1', 'r2'], 'a second point within 1.5 m merges: averaged, soft turns bad, fix and runs kept')
    bad.add('Map_One', 10, 30, 'bad', run='r2')
    check(len(bad.load('Map_One')) == 2, 'a point farther away is its own entry')
    check(bad.near('Map_One', 11, 21)['kind'] == 'bad' and bad.near('Map_One', 40, 40) is None and
          bad.near('Map_One', 10, 25, margin=0) is None and bad.near('Map_One', 10, 25, margin=2.6), 'near: inside the circle, margin widens it')
    other = recover.BadPoints(tmp / 'cache-a')
    check(other.load('Map_One')[0]['count'] == 2, 'another reader sees what was written')
    # concurrent writers (two pilots on one map): no entry lost
    def writer(i):
        recover.BadPoints(tmp / 'cache-b').add('Map_Race', 100 * i, 0, 'bad', run=f'r{i}')
    ths = [threading.Thread(target=writer, args=(i,)) for i in range(12)]
    [t.start() for t in ths]
    [t.join() for t in ths]
    check(len(recover.BadPoints(tmp / 'cache-b').load('Map_Race')) == 12, 'twelve writers at once lose no entry')
    check(recover.BadPoints.safe('../x/Map One') == '.._x_Map_One' and recover.BadPoints(tmp / 'cache-a').path('../../etc').parent == tmp / 'cache-a',
          'a map name cannot leave the cache folder')
    os.environ['PILOT_CACHE'] = str(tmp / 'cache-env')
    try:
        check(recover.BadPoints().dir == tmp / 'cache-env', '$PILOT_CACHE moves the cache folder')
    finally:
        del os.environ['PILOT_CACHE']
    # rerouting: a leg that crosses a circle gets a waypoint beside it, on the side away from the centre
    bad = recover.BadPoints(tmp / 'cache-c')
    bad.add('Map_R', 20, 0.5, 'bad', run='r')
    lines, det = bad.reroute('Map_R', (0, 0), ['run 40.00 0.00 radius 1 timeout 20'])
    wp = recover.parse_move(lines[0])
    check(len(lines) == 2 and len(det) == 1 and lines[1] == 'run 40.00 0.00 radius 1 timeout 20' and wp[2] < 0.5 - 2.5 and
          recover.seg_dist((20, 0.5), (0, 0), (wp[1], wp[2]))[0] > 2.5 and
          recover.seg_dist((20, 0.5), (wp[1], wp[2]), (40, 0))[0] > 2.4, f'a leg through a bad point is bent round it: {lines[0]}')
    lines2, det2 = bad.reroute('Map_R', (0, 0), ['run 40.00 30.00 radius 1 timeout 20'])
    check(lines2 == ['run 40.00 30.00 radius 1 timeout 20'] and not det2, 'a leg that misses every circle is untouched')
    lines3, det3 = bad.reroute('Map_R', (0, 0), ['run 20.00 0.50 radius 1 timeout 20'])
    check(lines3 == ['run 20.00 0.50 radius 1 timeout 20'] and not det3, 'a leg that ends inside a circle is left to the ladder')
    lines4, _ = bad.reroute('Map_R', (0, 0), ['press A', 'run 40.00 0.00 radius 1 timeout 20'])
    check(lines4[0] == 'press A' and len(lines4) == 3, 'other lines pass through, the move after them is bent')
    bad.add('Map_R', 20, 0.5, 'soft', fix='sidestep-left', run='r')   # (merges: still bad, the fix is kept)
    lines5, _ = bad.reroute('Map_R', (0, 0), ['run 40.00 0.00 radius 1 timeout 20'])
    check(recover.parse_move(lines5[0])[2] > 0.5 + 2.5, f'a past fix names the side: left of the way is +z here ({lines5[0]})')
    x, z = bad.nudge('Map_R', 20.5, 0.5)
    check(bad.near('Map_R', x, z) is None and math.hypot(x - 20, z - 0.5) > 2.5, 'nudge: a point inside a circle moves to its edge')

    class T:   # (a checkpoint)
        def __init__(self, name, x, z, r=2.5):
            self.name, self.x, self.z, self.radius, self.follow = name, x, z, r, None

    class G:
        def __init__(self, targets):
            self.targets = targets

    class S:
        area = 'Map_R'
        goals = [G([T('inside', 20.5, 0.5), T('far', 60, 5)])]
    moved = recover.nudge_segment(S, bad)
    t = S.goals[0].targets[0]
    check(len(moved) == 1 and bad.near('Map_R', t.x, t.z) is None and t.radius > 2.5 and S.goals[0].targets[1].x == 60,
          'a checkpoint inside a bad point moves out of it and its radius grows by the move; others stay')


def humanize_checks():
    st = {'pos': [0, 100, 0], 'camera': 0}
    lines = ['run 30.00 0.00 radius 1 timeout 20']
    off = humanize.Human(0, 7)
    check(off.shape('go', lines, st, None, 5).lines == lines and not off.shape('go', lines, st, None, 5).notes and off.reaction_s(5) == 0,
          'level 0: every line goes out as made')
    h2 = humanize.Human(2, 7)
    a, b = h2.shape('go', lines, st, None, 5), humanize.Human(2, 7).shape('go', lines, st, None, 5)
    check(a.lines == b.lines and a.notes == b.notes, 'the same seed and decision shape the same way')
    check(any(humanize.Human(2, s).shape('go', lines, st, None, 5).lines != a.lines for s in range(8, 14)), 'another seed shapes otherwise')
    check(any(humanize.Human(2, 7).shape('go', lines, st, None, n).lines != a.lines for n in range(6, 12)), 'decisions are drawn apart')
    waits = sorted(humanize.Human(2, 1).reaction_s(n) for n in range(2000))
    med = waits[1000]
    check(0.2 < med < 0.4 and waits[0] >= 0.12 and waits[-1] <= 1.5 and waits[1900] > med * 1.3,
          f'reaction delays: log-normal around 0.28 s, clipped to 0.12..1.5 s (median {med:.2f}, 95th {waits[1900]:.2f})')
    check(humanize.Human(1, 1).reaction_s(3) < humanize.Human(2, 1).reaction_s(3) < humanize.Human(3, 1).reaction_s(3), 'levels scale the delay')
    # what a long leg looks like at each level
    far = ['run 60.00 0.00 radius 1 timeout 25']
    shaped = [humanize.Human(2, s).shape('go', far, st, None, n) for s in range(40) for n in range(5)]
    curves = [s for s in shaped if s.notes.get('curve_waypoints')]
    check(len(curves) > 100, f'level 2 bends most long legs ({len(curves)} of {len(shaped)})')
    ok = True
    for s in curves:
        moves = [recover.parse_move(x) for x in s.lines if recover.parse_move(x)]
        final = moves[-1]
        ok &= final[1:3] == (60, 0) and s.lines[-1].startswith('run 60.00 0.00 radius 1 timeout 25')   # the last point and radius are the plan's
        for m in moves[:-1]:
            ok &= abs(m[2]) <= 1.4 + 1e-6 and 'radius 1.5' in ' '.join(m[3])   # a bump of at most 1.4 m, a loose radius
    check(ok, 'the last waypoint keeps its point and radius; the bump stays within 1.4 m; passed waypoints are loose')
    short = humanize.Human(3, 3).shape('go', ['run 5.00 0.00 radius 1 timeout 20'], st, None, 1)
    check(not short.notes.get('curve_waypoints') and not any('RLEFT' in x or 'RRIGHT' in x for x in short.lines), 'a short leg stays straight, with no look')

    class Door:
        kind, front = 'door', None
    check(not humanize.Human(3, 3).shape('go', far, st, Door, 1).notes.get('curve_waypoints'), 'no curve toward a door')
    check(not humanize.Human(3, 3).shape('go', far, st, None, 1, curves_ok=False).notes.get('curve_waypoints'), 'no curve where curves are not ok')
    check(humanize.Human(3, 3).shape('press-a', ['press A', 'wait 1'], st, None, 1).lines[-2:] == ['press A', 'wait 1'], 'a press is delayed, not changed')
    check(humanize.Human(3, 3).shape('recover:sidestep', far, st, None, 1).lines == far and
          humanize.Human(3, 3).shape('wait-goal', ['until flag X=1 timeout 40'], st, None, 1).lines == ['until flag X=1 timeout 40'] and
          humanize.Human(3, 3).shape('strike', ['raw 0:ZL/1500 1.8'], st, None, 1).lines == ['raw 0:ZL/1500 1.8'],
          'a recovery rung, a wait and a fight move go out as made')
    refused = humanize.Human(2, 4).shape('go', far, st, None, 9, validate=lambda a, b: False)
    check(not refused.notes.get('curve_waypoints'), 'waypoints the planner refuses are dropped')
    looks = [x for s in shaped for x in s.lines if x.startswith('raw ')]
    check(looks and all(re.fullmatch(r'raw 0:R(LEFT|RIGHT)/\d+(,[0-9.]+:R(LEFT|RIGHT)/\d+)? [0-9.]+', x) for x in looks), f'look-arounds are right-stick sequences ({looks[0]})')
    kw = [x for s in shaped for x in s.lines if x.startswith('run ') and ' noise ' in x]
    check(kw and all(re.fullmatch(r'run -?[0-9.]+ -?[0-9.]+ radius [0-9.]+ timeout \d+( mag 0\.5)? noise 3 seed \d+', x) for x in kw),
          f'move lines carry noise and seed words ({kw[0]})')
    mid = ['run 10.00 0.00 radius 1 timeout 20']
    check(any(' mag 0.5' in x for s in range(40) for n in range(5) for x in humanize.Human(2, s).shape('go', mid, st, None, n).lines),
          'some legs of 14 m or less are walked (mag 0.5)')
    check(not any(' mag 0.5' in x for s in shaped for x in s.lines), 'a long leg is always run')
    h3 = [humanize.Human(3, s).shape('go', far, st, None, n) for s in range(40) for n in range(5)]
    rolls = [s.notes['roll'] for s in h3 if s.notes.get('roll')]
    check(rolls and all(r == 'left' for r in rolls) and not any(s.notes.get('roll') for s in shaped),
          f'level 3 rolls along a long leg, toward it ({len(rolls)} times; a leg along +x with the camera along +z is left), level 2 does not')
    check(humanize.dir_name(90, 0) == 'left' and humanize.dir_name(-90, 0) == 'right' and humanize.dir_name(0, 0) == 'up' and
          recover.dir_name(135, 0) == humanize.dir_name(135, 0), 'direction words: the camera\'s yaw minus the wanted yaw, right positive')
    try:
        humanize.Human(4)
        check(False, 'level 4 is refused')
    except ValueError:
        check(True, 'level 4 is refused')


def ladder_checks():
    rec = recover.Recovery(None)
    rs = rec.new_state()
    ctx = {'pos': (0, 0), 'camera': 0, 'sign': 1, 'target': {'x': 0, 'z': 30, 'radius': 2.5},
           'go_lines': ['run 0.00 15.00 radius 1', 'run 0.00 30.00 radius 1'], 'hop_ok': True}
    rs.blocked = {'pos': (0, 0), 'lines': ['run 0.00 15.00 radius 1', 'run 0.00 30.00 radius 1'], 'idx': 0}
    seen = []
    for _ in range(6):
        a = rec.action(rs, ctx)
        seen.append(a)
    check([a.rung for a in seen] == list(recover.LADDER), f'the ladder in order: {[a.rung for a in seen]}')
    side, angle, roll, hop, nxt, replan = seen
    sx = recover.parse_move(side.lines[0])
    check(abs(math.hypot(sx[1], sx[2]) - 2.5) < 0.01 and sx[1] > 2.4 and side.lines[1:] == ctx['go_lines'],
          f'sidestep: 2.5 m to the left of the way (+x for a way along +z), then the plan ({side.lines[0]})')
    back, via = recover.parse_move(angle.lines[0]), recover.parse_move(angle.lines[1])
    check(back[2] < -1.9 and abs(back[1]) < 0.01 and via[1] < -2 and via[2] > back[2] and angle.lines[2:] == ctx['go_lines'],
          f'angle: back up 2 m, then out at 40 degrees to the other side ({angle.lines[:2]})')
    check(roll.lines[0] == 'roll up' and roll.lines[1] == 'wait 0.4' and roll.lines[2:] == ctx['go_lines'], 'roll: toward the target')
    m = re.fullmatch(r'raw 0:LX=(-?\d+)\+LY=(-?\d+)/800,0\.15:X/100 1\.2', hop.lines[0])
    check(m and int(m.group(1)) == 0 and int(m.group(2)) == 32767 and 'Y' not in hop.lines[0].replace('LY', ''), f'hop: stick toward the target, X, never Y ({hop.lines[0]})')
    check(nxt.lines == ['run 0.00 30.00 radius 1'], 'next-point: the route points after the one that ended stuck')
    check(replan.kind == 'replan' and not replan.lines, 'replan: no lines, the pilot plans, marks the point and leaves the target')
    rs2 = rec.new_state()
    rs2.blocked = {'pos': (0, 0), 'lines': ['run 0.00 30.00 radius 1'], 'idx': 0}
    ctx2 = dict(ctx, go_lines=['run 0.00 30.00 radius 1'], hop_ok=False, camera=None)
    check([rec.action(rs2, ctx2).rung for _ in range(3)] == ['sidestep', 'angle', 'replan'], 'no hop where hopping is not ok; no roll without a camera; no next-point without one')
    rs3 = rec.new_state()
    rs3.blocked = {'pos': (0, 0), 'lines': [], 'idx': None}
    rs3.learned, rs3.side = 'hop', -1
    first = rec.action(rs3, ctx)
    check(first.rung == 'hop', 'a rung learned for this spot goes first')
    ci = rec.close_in(ctx)
    cm = recover.parse_move(ci.lines[0])
    check(cm[1:3] == (0, 30) and 'radius 1.75' in ci.lines[0], 'close-in: a walk onto the target itself within 70 percent of its radius')
    check(recover.stick_for(90, 0) == (-32767, 0) and recover.stick_for(0, 90)[0] == 32767 and recover.stick_for(0, 0, -1) == (0, 32767),
          'stick_for: the camera\'s yaw minus the wanted yaw, right positive, handedness aside')


class T:
    def __init__(self, kind='reach', radius=2.5, last=False):
        self.kind, self.radius, self.follow, self.name, self.x, self.z = kind, radius, None, 't', 0, 30
        self.last = last


class C:
    def __init__(self, label, lines=()):
        self.label, self.lines, self.text = label, list(lines), ''


def gate_checks():
    rec = recover.Recovery(None)
    rs = rec.new_state()
    st = {'pos': [0, 100, 0], 'area': 'A', 'prompt': 'Empty', 'event': 0, 'loading': 0, 'flags': {}, 'life': 12}
    cands = [C('go', ['run 0 30']), C('settle'), C('next-target')]
    _, forced = rec.gate(rs, cands, T(), st, {})
    check(forced is None, 'two valid candidates: ask')
    _, forced = rec.gate(rs, [C('next-target')], T(), st, {})
    check(forced == ('choice', 'next-target', 'one valid candidate'), 'one candidate: no question')
    near = dict(st, pos=[0, 100, 28])
    cs, forced = rec.gate(rs, [C('go', ['run 0 30']), C('go-near'), C('press-a'), C('next-target'), C('give-up-goal')], T(), near, {}, dist=2)
    check(forced == ('choice', 'next-target', 'one valid candidate') and [c.label for c in cs] == ['next-target'],
          'within the radius of a reach target that is not the last: next-target, no question')
    cs, forced = rec.gate(rs, [C('go', ['run 0 30']), C('settle'), C('press-a'), C('next-target')], T(), near, {'last': True}, dist=2)
    check(forced is None and [c.label for c in cs] == ['settle', 'press-a', 'next-target'], 'on the last target the way there is not offered again, the rest is')
    cs, forced = rec.gate(rs, [C('talk-through'), C('go'), C('next-target')], T(), near, {}, dist=2)
    check(forced is None and [c.label for c in cs] == ['talk-through', 'next-target'], 'an event that holds Link keeps talk-through')
    # pi-solo-4: a rupee on a pond's floor (an item target of a collect goal that is not the last): Link stands on it, the pickup found nothing,
    # and the dive that follows must still be offered (the arrival rule used to leave only next-target, so the blue rupee was never dived for)
    cs, forced = rec.gate(rs, [C('pickup', ['pickup 0 30']), C('pickup-dive', ['pickup 0 30 dive 3']), C('next-target'), C('give-up-goal')], T('item', radius=0.5), near, {'history': [('pickup', 'none', 5.0, 0.02)]}, dist=0.3)
    check(forced is None and [c.label for c in cs] == ['pickup', 'pickup-dive', 'next-target'],
          f'an item target of a collect goal keeps its pickups when Link stands on it ({[c.label for c in cs]}, {forced})')
    cs, forced = rec.gate(rs, [C('go', ['run 0 30']), C('pickup', ['pickup 0 30']), C('next-target')], T('item', radius=0.5), near, {}, dist=0.3)
    check(forced is None and [c.label for c in cs] == ['pickup', 'next-target'], 'but the way there is still not offered again')
    cs, forced = rec.gate(rs, [C('pickup', ['pickup 0 30']), C('next-target')], T('item', radius=0.5), near, {'history': [('pickup', 'picked', 5.0, 0.02)]}, dist=0.3)
    check(forced == ('choice', 'next-target', 'one valid candidate'), 'after a pickup that took the item the target is left without a question')
    mem = {'blocked_lines': [((0, 0), ['run 0 30'])]}
    cs, forced = rec.gate(rs, [C('go', ['run 0 30']), C('go-near', ['walk 0 28']), C('settle')], T('door'), st, mem)
    check([c.label for c in cs] == ['go-near', 'settle'] and forced is None, 'a move that already ended stuck from here is not offered again')
    # an unchanged state
    rs = rec.new_state()
    two = [C('go', ['run 0 30']), C('settle')]
    rec.note_answer(rs, 'go', ['run 0 30'], st, two, True)
    _, forced = rec.gate(rs, two, T(), st, {})
    check(forced == ('recover', 'unchanged'), 'the same state after a move that went nowhere: recovery, not another question')
    rs = rec.new_state()
    waits = [C('wait-goal'), C('press-a'), C('next-target')]
    rec.note_answer(rs, 'wait-goal', ['until x'], st, waits, True)
    _, forced = rec.gate(rs, waits, T('wait'), st, {})
    check(forced == ('choice', 'wait-goal', 'state unchanged'), 'the same state after a wait: the last answer again, no question')
    rec.note_answer(rs, 'wait-goal', ['until x'], st, waits, False)
    rec.note_answer(rs, 'wait-goal', ['until x'], st, waits, False)
    _, forced = rec.gate(rs, waits, T('wait'), st, {})
    check(forced is None, 'after two repeats from the last answer the decider is asked again')
    moved = dict(st, pos=[3, 100, 4])
    rs = rec.new_state()
    rec.note_answer(rs, 'go', ['run 0 30'], st, two, True)
    _, forced = rec.gate(rs, two, T(), moved, {})
    check(forced is None, 'a state that changed is a new question')
    # identical answers in a row
    rs = rec.new_state()
    for _ in range(3):
        rec.note_answer(rs, 'go', ['run 0 30'], moved, two, True)
    _, forced = rec.gate(rs, two, T(), dict(moved, pos=[3, 100, 5]), {})
    check(rs.streak == 3 and forced == ('recover', 'identical answers'), 'three identical moves in a row without ground: recovery instead of another call')
    rec.note_answer(rs, 'go', ['run 0 31'], moved, two, True)
    check(rs.streak == 1, 'another line is another answer')
    # the monitor's verdicts steer the guard
    rs = rec.new_state()
    rs.progress.verdict = {'stuck': True, 'why': 'blocked', 'stalled_obs': 1, 'stalled_s': 2.5, 'short': False}
    check(rec.gate(rs, two, T(), st, {})[1] == ('recover', 'blocked'), 'a block: the ladder')
    rs.progress.verdict = {'stuck': False, 'why': 'short', 'stalled_obs': 0, 'stalled_s': 0, 'short': True}
    check(rec.gate(rs, two, T(), st, {})[1] == ('close-in', 'short') and
          rec.gate(rs, two, T('door'), st, {})[1] is None, 'short of a reach target: close in (a door\'s stand-off is meant)')


def unit_checks(tmp):
    progress_checks()
    badpoints_checks(tmp)
    humanize_checks()
    ladder_checks()
    gate_checks()


# ---- the pilot against the fake game side

def loop_scenario():
    """A square loop with a post on each leg: what a straight hop through S01's four places looked like."""
    targets = [('c1', 0, 40, 2.5), ('c2', 40, 40, 2.5), ('c3', 40, 0, 2.5), ('c4', 0, 8, 2.5)]
    return targets, [Post(0, 20), Post(20, 40), Post(40, 20), Post(20, 4)]


def s01_points():
    """The four places of S01 (the real ones from the cache folder when this PC has them, else made-up ones of the same shape)
    and which it is."""
    f = recover.HERE / 'cache' / 'regression-s01.json'
    if f.is_file():
        return [tuple(p) for p in json.loads(f.read_text())['points']], 'the four real places of S01'
    return [(41, 117), (31, 200), (-66, 354), (66, 260)], 'four made-up places'


def regression_checks(tmp):
    pts, which = s01_points()
    # without the recovery: a straight run through each place ends stuck, and the rules' own step round it takes a while
    base_stuck, base_t = 0, 0
    for i, (px, pz) in enumerate(pts):
        t = [(f's{i}', px + 14, pz, 2.5)]
        p, outcome, world, rd = play(tmp, t, [Post(px, pz)], start=(px - 14, pz), recovery=False)
        base_stuck += stuck_results(p)
        base_t += world.t
    check(base_stuck >= 4, f'{which}: without the recovery the loop ends stuck {base_stuck} times (one per place at least)')
    # with it: one block per place, each over within 10 s of game time, the rung that worked kept in the memory
    bad = recover.BadPoints(tmp / 'cache-s01')
    stuck_total, longest, fixes, t_with = 0, 0, [], 0
    for i, (px, pz) in enumerate(pts):
        t = [(f's{i}', px + 14, pz, 2.5)]
        p, outcome, world, rd = play(tmp, t, [Post(px, pz)], start=(px - 14, pz), bad=bad, area='Fake_Field')
        rs = p.recover_summary()
        check(outcome == 'solved', f'place {i + 1}: solved ({outcome})')
        stuck_total += stuck_results(p)
        longest = max(longest, rs['longest_s'])
        fixes += [e for e in rs['episodes'] if e['how'] == 'recovered']
        t_with += world.t
        check(rs['blocks'] == 1 and rs['recovered'] == 1 and rs['over_10s'] == 0 and rs['marked_bad'] == 0,
              f"place {i + 1}: one block, recovered in {rs['longest_s']}s of game time by {rs['rungs']}")
    check(stuck_total == len(pts) and longest <= 10, f'the loop ends stuck once per place and never for more than 10 s (longest {longest}s)')
    check(len(bad.load('Fake_Field')) == len(pts) and all(e['kind'] == 'soft' and e['fix'].startswith('sidestep') for e in bad.load('Fake_Field')),
          'each place is remembered with the rung that got past it')
    # the second time round the memory bends the route: nothing ends stuck
    stuck_again = 0
    for i, (px, pz) in enumerate(pts):
        t = [(f's{i}', px + 14, pz, 2.5)]
        p, outcome, world, rd = play(tmp, t, [Post(px, pz)], start=(px - 14, pz), bad=bad, area='Fake_Field')
        stuck_again += stuck_results(p)
        check(outcome == 'solved' and p.recover_summary()['blocks'] == 0, f'place {i + 1} again: solved with no block')
        check(any(r['kind'] == 'decision' and 'round 1 place' in json.dumps(r['candidates']) for r in rows(rd)), f'place {i + 1} again: the route was bent round it')
    check(stuck_again == 0, 'with the memory the same loop ends stuck 0 times')
    # the square loop, all four posts in one run
    targets, posts = loop_scenario()
    p, outcome, world, rd = play(tmp, targets, posts, final=(0, 8), area='Fake_Loop')
    s = p.recover_summary()
    check(outcome == 'solved' and s['blocks'] == 4 and s['recovered'] == 4 and s['over_10s'] == 0 and s['stuck_steps'] == 4,
          f"the loop with four posts: solved, 4 blocks all recovered, longest {s['longest_s']} s")
    decs = rows(rd, 'decision')
    check(sum(d['decider'] == 'recover' for d in decs) == sum(s['rungs'].values()) and
          all(d.get('no_request') == 'recover' for d in decs if d['decider'] == 'recover'),
          'every rung is a decision of its own with no question asked')
    check(all('recover' in d for d in decs) and set(decs[0]['recover']) == {'stuck', 'why', 'stalled_obs', 'stalled_s', 'rung', 'streak'},
          'every decision row carries the recover verdict (stuck, why, stalled_obs, stalled_s, rung, streak)')
    kinds = {r['status'] for r in rows(rd, 'recover')}
    check(kinds == {'blocked', 'recovered'}, f'recover rows: {sorted(kinds)}')


def rung_checks(tmp):
    # a post too big for the sidestep: the angle gets round it (a post of 2.2 m and Link's 0.4 m: the sidestep's 2.5 m is not enough)
    p, outcome, world, rd = play(tmp, [('t', 0, 40, 2.5)], [Post(0, 20, 2.2)], area='Fake_Big')
    rungs = [e['rung'] for e in rows(rd, 'recover') if e['status'] == 'recovered']
    s = p.recover_summary()
    check(outcome == 'solved' and rungs == ['angle'] and s['rungs'].get('recover:sidestep') == 1,
          f"a big post: the sidestep failed, the angle got round it ({s['rungs']}, recovered by {rungs})")
    # a low fence 60 m long: only the hop gets over it
    p, outcome, world, rd = play(tmp, [('t', 0, 40, 2.5)], [Wall((-30, 20), (30, 20), low=True)], area='Fake_Fence')
    rungs = [e['rung'] for e in rows(rd, 'recover') if e['status'] == 'recovered']
    check(outcome == 'solved' and rungs == ['hop'], f'a low fence: sidestep, angle and roll fail, the hop gets over it (recovered by {rungs})')
    check(any(x.startswith('raw 0:LX=') and ':X/' in x and 'Y' not in x.split(':X/')[1] for x in world.log), 'the hop was one stick-and-X sequence, no sword')
    # a route point nothing can reach (the middle of a post): the next route point, off to the left, is where Link goes on
    pf = lambda area, a, b, **kw: {'ok': True, 'steps': ['run 0.00 20.00 radius 1', 'run -15.00 17.00 radius 1', 'run 40.00 40.00 radius 1'], 'length': 70}  # noqa: E731
    p, outcome, world, rd = play(tmp, [('t', 40, 40, 2.5)], [Post(0, 20, 2)], plan=pf, area='Fake_Point')
    steps = [d['choice'] for d in rows(rd, 'decision')]
    rungs = [e['rung'] for e in rows(rd, 'recover') if e['status'] == 'recovered']
    check(outcome == 'solved' and rungs == ['next-point'] and 'recover:replan' not in steps,
          f'a route point inside a post: the next route point gets Link on ({outcome}, recovered by {rungs}; {steps})')
    # a target nothing gets to: the ladder is spent, the planner is asked again, the point is marked bad, the target is left
    box = [Wall((-10, 30), (10, 30)), Wall((-10, 30), (-10, 50)), Wall((10, 30), (10, 50)), Wall((-10, 50), (10, 50))]
    bad = recover.BadPoints(tmp / 'cache-box')
    planner = StubPlanner()
    targets = [('boxed', 0, 40, 2.5), ('after', 40, 0, 2.5)]
    p, outcome, world, rd = play(tmp, targets, box, bad=bad, planner=planner, area='Fake_Box')
    s = p.recover_summary()
    check(outcome == 'solved' and s['marked_bad'] == 1, f'an unreachable target: the ladder is spent, the point marked bad, the next target reached ({outcome})')
    entries = bad.load('Fake_Box')
    check(len(entries) == 1 and entries[0]['kind'] == 'bad' and entries[0]['why'] and entries[0]['targets'] == ['boxed'] and
          math.hypot(entries[0]['x'], entries[0]['z'] - 30) < 3, f'the bad point is on the file: {entries}')
    check(planner.calls >= 2 and s['planner_replans'] == 1, f"the planner was asked at the start and again at the stuck point ({planner.calls} calls)")
    last = planner.tried[-1]
    check(any(t['step'].startswith('recover:') for t in last) and any(t['step'] == 'recover:replan' and t['result'] == 'marked-bad' for t in last),
          'the planner is told which rungs were tried and that the point was marked bad')
    check(all(r in s['rungs'] for r in ('recover:sidestep', 'recover:angle', 'recover:roll', 'recover:hop', 'recover:replan')),
          f"every rung was tried before the end ({sorted(s['rungs'])})")
    # the next run: the segment's own checkpoint inside the bad point's circle moves out of it
    targets = [('boxed', 0, 31, 2.5), ('after', 40, 0, 2.5)]
    p, outcome, world, rd = play(tmp, targets, box, bad=bad, area='Fake_Box')
    nud = rows(rd, 'bad-points')
    check(nud and nud[0]['nudged'][0]['target'] == 'boxed', 'a checkpoint inside a remembered bad point is moved out of it at the start')
    # the memory is per map: another map is not affected
    p, outcome, world, rd = play(tmp, [('t', 0, 31, 2.5)], [], bad=bad, area='Fake_Other')
    check(outcome == 'solved' and not rows(rd, 'bad-points'), 'another map: nothing is moved')
    # an unfixable block where the target is reached by the model after all: a block can also end without a rung
    p, outcome, world, rd = play(tmp, [('t', 0, 40, 2.5)], [], area='Fake_Free')
    check(outcome == 'solved' and p.recover_summary()['blocks'] == 0, 'no obstacle, no block')


def sticky_go_checks(tmp):
    """PT-H5: the planner's stand-off point lies outside the target's own radius, the walk to it `reached` with 0 m moved,
    and the model answered `go` again and again."""
    stand = lambda area, a, b, **kw: {'ok': True, 'steps': [f'run {b[0]:.2f} {b[1] - 3.2:.2f} radius 1'], 'length': 30}  # noqa: E731
    targets = [('sign', 0, 40, 2.5), ('next', 40, 40, 2.5)]
    d_old = Counter('go')
    p0, out0, w0, rd0 = play(tmp, targets, [], decider=d_old, plan=stand, recovery=False, max_decisions=25)
    check(out0.startswith('budget') and d_old.asked == 25, f'without the guard: 25 questions, all `go`, the budget ends the run ({out0})')
    d_new = Counter('go')
    p1, out1, w1, rd1 = play(tmp, targets, [], decider=d_new, plan=stand, max_decisions=25)
    check(out1 == 'solved' and d_new.asked <= 4, f'with the guard: solved, {d_new.asked} questions ({out1})')
    labels = [d['choice'] for d in rows(rd1, 'decision')]
    check('recover:close-in' in labels, f'the stand-off point is closed in on, not asked about again: {labels}')
    # a model that insists on `go` where nothing changes: capped, then the ladder, not another question (the stand-off point
    # is Link's own place and the target lies in a closed pen: close-in ends stuck, every rung fails)
    always = lambda area, a, b, **kw: {'ok': True, 'steps': ['run 0.00 0.00 radius 1'], 'length': 1}  # noqa: E731
    pen = [Wall((-10, 30), (10, 30)), Wall((-10, 30), (-10, 50)), Wall((10, 30), (10, 50)), Wall((-10, 50), (10, 50))]
    d3 = Counter('go')
    p2, out2, w2, rd2 = play(tmp, [('far', 0, 40, 2.5)], pen, decider=d3, plan=always, max_decisions=40)
    s = p2.recover_summary()
    check(d3.asked <= 3 and s['blocks'] >= 1 and s['marked_bad'] == 1 and out2.startswith('gave up'),
          f"a go that never goes anywhere: {d3.asked} questions, then the ladder ({sorted(s['rungs'])}), the point marked bad, the target left")


def identical_answer_checks(tmp):
    """A model that presses A at a place where nothing happens, for ever: the unchanged state is answered from the last answer
    twice, then asked again; after six identical answers the target is left, not asked about a seventh time."""
    d = Counter('press-a')
    p, outcome, world, rd = play(tmp, [('a', 0, 20, 2.5), ('b', 0, 40, 2.5)], [], decider=d, max_decisions=120, area='Fake_Press')
    decs = rows(rd, 'decision')
    per = {}
    for x in decs:
        per.setdefault(x['target'], []).append(x)
    check(outcome.startswith('gave up') and len(decs) <= 18 and all(len(v) <= 8 for v in per.values()),
          f'a press with nothing changing ends at the cap: {len(decs)} decisions in all ({outcome})')
    check(d.asked <= 8, f'and costs {d.asked} questions, not one per decision')
    first = per['a']
    check([x['choice'] for x in first][-1] == 'next-target' and first[-1]['decider'] == 'gate' and first[-1].get('no_request') == 'identical answers' and
          sum(1 for x in first if x.get('no_request') == 'state unchanged') >= 2,
          f"decisions on the first target: {[(x['choice'], x.get('no_request')) for x in first]}")
    check(all(t.status == 'failed' for g in p.seg.goals for t in g.targets), 'both targets were left as failed')


def no_question_checks(tmp):
    targets = [('a', 0, 20, 2.5), ('b', 0, 40, 2.5), ('c', 0, 60, 2.5), ('d', 0, 80, 2.5)]
    d = Counter()
    p, outcome, world, rd = play(tmp, targets, [], decider=d)
    decs = rows(rd, 'decision')
    forced = [x for x in decs if x['decider'] == 'gate']
    check(outcome == 'solved' and d.asked == len(decs) - len(forced) and len(forced) >= 3 and all(x['choice'] == 'next-target' for x in forced),
          f'{len(forced)} of {len(decs)} decisions needed no question: next-target after arriving ({d.asked} asked)')
    check(all(len(c) >= 2 for c in d.seen), 'the decider was never asked about fewer than two candidates')
    check(p.recover_summary()['no_question'].get('one valid candidate') == len(forced), 'summary: counted by reason')
    # the same run without the guard asks about every decision
    d2 = Counter()
    p2, out2, w2, rd2 = play(tmp, targets, [], decider=d2, recovery=False)
    check(d2.asked == len(rows(rd2, 'decision')) and d2.asked > d.asked, f'without the guard every decision is a question ({d2.asked} against {d.asked})')


def follow_checks(tmp):
    """A follower that starts on another map: the pilot reads its own state again and goes on when the maps agree."""
    path = Path(tmp) / f'other-{time.time_ns()}.json'
    path.write_text(json.dumps({'x': 5, 'y': 0, 'z': 30, 'map': 'Map_Here', 'w': time.time()}))
    seg_path = Path(tmp) / f'seg-follow-{time.time_ns()}.toml'
    seg_path.write_text('name = "f"\nwhat = "x"\narea = "Map_Here"\nbudget_seconds = 900\nmax_decisions = 10\n[[goal]]\nname = "g"\nflag = "Final_Reached=1"\nkind = "reach"\n'
                        'targets = [{name = "friend", follow = "other", kind = "reach", radius = 2.5}]\n')

    def start(area, follow_wait, cross):
        seg = pilot.Segment(seg_path)
        live = Path(tmp) / f'live-follow-{time.time_ns()}'
        ch = pilot.Channel(live)
        ch.send(pilot.watch_lines(seg.watch))
        world = FakeWorld(live, area=area, final=(5, 30))
        world.start()
        assert ch.wait(lambda e: e['ev'] == 'gameplay', 5)
        st = ch.wait(lambda e: e['ev'] == 'state' and e['why'] == 'wait', 5)
        rd = Path(tmp) / f'run-follow-{time.time_ns()}'
        rd.mkdir()
        p = pilot.Pilot(seg, deciders.Rules(), ch, rd, rd.name, lambda: True, None, 10, follows={'other': str(path)}, follow_wait=follow_wait,
                        cross_map_wait=cross, recovery=True)
        p.plan = None
        out = {}
        th = threading.Thread(target=lambda: out.update(outcome=p.run(st)), daemon=True)
        th.start()
        return p, world, ch, th, out, rd

    # starts elsewhere, is brought to the friend's map after 1.5 s: the old code compared with the first state for ever
    p, world, ch, th, out, rd = start('Map_Elsewhere', 20, 20)
    time.sleep(1.5)
    check(th.is_alive() and not rows(rd, 'decision'), 'on another map the pilot waits (no decision yet)')
    world.area = 'Map_Here'   # (what a runner's menu script does)
    th.join(15)
    check(not th.is_alive() and out.get('outcome') == 'solved', f"once the maps agree the pilot reads its state again, goes on and walks to him ({out.get('outcome')})")
    check(not any(r.get('status') == 'never came' for r in rows(rd, 'follow')), 'it did not say the file never came')
    ch.send(['end'])
    # stays elsewhere: after the cross-map wait the pilot goes on and offers waiting, not a walk to stale coordinates
    p, world, ch, th, out, rd = start('Map_Elsewhere', 20, 1)
    th.join(15)
    decs = rows(rd, 'decision')
    check(decs and 'wait-friend' in [c['label'] for c in decs[0]['candidates']] and not any(c['label'] == 'go' for c in decs[0]['candidates']),
          'on another map after the wait: wait-friend and leaving, no go')
    check(any(r.get('status') == 'other map' for r in rows(rd, 'follow')), 'the transcript says the file was there on another map')
    ch.send(['end'])
    # a file that never comes: as before
    path.unlink()
    p, world, ch, th, out, rd = start('Map_Here', 2, 1)
    th.join(15)
    check(not th.is_alive() and out.get('outcome', '').startswith('no place of the other player') and
          any(r.get('status') == 'never came' for r in rows(rd, 'follow')), 'a file that never comes still ends the run')
    ch.send(['end'])


class Look:
    def __init__(self, hint, extra, fresh=False):
        self.hint, self.extra, self.fresh = hint, extra, fresh


class FakeEyes:
    """What vision.py hands the pilot: before_decision() gives a hint and extra candidates; at a stuck point (the pilot says so in
    mem['recover']) a picture-informed way round."""

    def __init__(self, way, fresh=False, always=None):
        self.way, self.fresh, self.always, self.calls = way, fresh, always or [], []

    def before_decision(self, st, goal=None, target=None, mem=None, tried=None, n=None):
        rc = dict((mem or {}).get('recover') or {})
        self.calls.append((n, rc))
        if rc.get('stuck') and self.way:
            return Look({'looked': 'stuck', 'blocked': True}, [self.way], self.fresh)
        return Look({'looked': 'periodic'}, list(self.always), self.fresh)


def vision_checks(tmp):
    way = ('vision-side-left', ['walk 3.00 17.00 radius 0.6 timeout 4', 'run 0.00 40.00 radius 2.5 timeout 12'], 'the picture shows the way clear to the left')
    eyes = FakeEyes(way)
    d = Counter()
    p, outcome, world, rd = play(tmp, [('t', 0, 40, 2.5)], [Post(0, 20, 1)], decider=d, eyes=eyes, area='Fake_Eyes')
    decs = rows(rd, 'decision')
    check(outcome == 'solved' and [x['choice'] for x in decs][:2] == ['go', 'vision-side-left'] and decs[1]['decider'] == 'recover' and
          decs[1].get('recover_rung') == 'vision' and not any(x['choice'] == 'recover:sidestep' for x in decs),
          f"at a stuck point the picture's way goes before the blind rungs, with no question: {[x['choice'] for x in decs]}")
    check(decs[0]['state'].get('vision') == {'looked': 'periodic'} and decs[1]['state'].get('vision') == {'looked': 'stuck', 'blocked': True},
          'the look\'s hint is in the state the decision row shows')
    check(eyes.calls[0][0] == 1 and eyes.calls[1][1].get('stuck') is True and eyes.calls[1][1].get('why') == 'blocked',
          'before_decision is called with the decision\'s number, and sees the stuck verdict in mem["recover"]')
    check([e['rung'] for e in rows(rd, 'recover') if e['status'] == 'recovered'] == ['vision'], 'the block ended recovered by the eyes\' rung')
    # a fence the picture cannot help with: the eyes' rung goes once, then the ladder's own rungs
    eyes = FakeEyes(('vision-side-left', ['walk 3.00 17.00 radius 0.6 timeout 4'], 'the way is clear (it is not)'))
    p, outcome, world, rd = play(tmp, [('t', 0, 40, 2.5)], [Wall((-30, 20), (30, 20), low=True)], eyes=eyes, area='Fake_Eyes2')
    labels = [x['choice'] for x in rows(rd, 'decision')]
    check(outcome == 'solved' and labels.count('vision-side-left') == 1 and 'recover:hop' in labels and labels.index('vision-side-left') < labels.index('recover:sidestep'),
          f"the eyes' rung once per block, the ladder after it: {labels}")
    # outside a stuck point the eyes' candidates are just candidates for the decider
    eyes = FakeEyes(None)
    p, outcome, world, rd = play(tmp, [('t', 0, 40, 2.5)], [], decider=Counter(), eyes=eyes, area='Fake_Eyes3')
    check(outcome == 'solved' and len(eyes.calls) == len(rows(rd, 'decision')), 'the eyes are consulted before every decision')
    # a fresh look and a real question: the same moment is asked once more without the picture, the answer unused
    eyes, d = FakeEyes(None, fresh=True, always=[('vision-talk', ['press A', 'wait 1'], 'the picture shows a person to talk to')]), Counter()
    p, outcome, world, rd = play(tmp, [('a', 0, 20, 2.5), ('b', 0, 40, 2.5), ('c', 0, 60, 2.5)], [], decider=d, eyes=eyes, area='Fake_Eyes4')
    main = [x for x in rows(rd, 'decision') if x['decider'] == 'counter']
    cf = rows(rd, 'counterfactual')
    check(outcome == 'solved' and main and len(cf) == len(main) and d.asked == len(main) + len(cf),
          f'counterfactual: one more question after each fresh look that asked ({len(cf)} rows, {d.asked} questions in all)')
    check(all(r['with_vision'] and r['without_vision'] and r['asked'] for r in cf) and [r['n'] for r in cf] == [x['n'] for x in main],
          'each row says what was chosen with the picture and what without it, at the decision\'s number')
    check(all('vision-talk' in labels for labels in d.seen[0::2]) and all(not any(lbl.startswith('vision-') for lbl in labels) for labels in d.seen[1::2]),
          'the first question had the eyes\' candidate, the repeated one has none')
    eyes = FakeEyes(None, fresh=False)
    p, outcome, world, rd = play(tmp, [('a', 0, 20, 2.5), ('b', 0, 40, 2.5)], [], decider=Counter(), eyes=eyes, area='Fake_Eyes5')
    check(outcome == 'solved' and not rows(rd, 'counterfactual'), 'a look that is not fresh asks nothing more')


def humanized_run_checks(tmp):
    targets = [('a', 0, 40, 2.5), ('b', 40, 40, 2.5), ('c', 40, 0, 2.5)]
    runs = []
    for _ in range(2):
        p, outcome, world, rd = play(tmp, targets, [], human=humanize.Human(3, 11))
        runs.append((p, outcome, world, rd))
    (p, outcome, world, rd), (p2, out2, w2, rd2) = runs
    check(outcome == 'solved' and out2 == 'solved', 'a humanized run (level 3) still solves the segment')
    notes = [r['humanized'] for r in rows(rd, 'result') if r.get('humanized')]
    check(notes and any('react_s' in n for n in notes), f'the shaping is in the transcript ({len(notes)} results)')
    sent = [r['lines'] for r in rows(rd, 'result')]
    sent2 = [r['lines'] for r in rows(rd2, 'result')]
    check(sent == sent2, 'the same seed plays the same lines in both runs')
    plain, _, w0, rd0 = play(tmp, targets, [], human=None)
    check(not any(r.get('humanized') for r in rows(rd0, 'result')), 'without a Human nothing is shaped')
    first_plain = [r['lines'] for r in rows(rd0, 'result')][0]
    check(all(ln.split()[0] in ('run', 'walk') and ' noise ' not in ln and ' mag ' not in ln for ln in first_plain),
          f'without shaping the lines are the candidate\'s own: {first_plain}')
    check(any(ln.startswith('wait ') for ln in sent[0]) and all(ln.split()[0] in ('wait', 'run', 'walk', 'raw', 'roll') for l in sent for ln in l),
          'shaped lines are hsap verbs: waits, moves, a look, a roll')
    check(sum(len(x) for x in sent) > sum(len(x) for x in [r['lines'] for r in rows(rd0, 'result')]), 'a humanized run sends more lines (waits, curves, looks)')


def level_checks(tmp):
    class A:
        humanize = None

    def seg_of(text):
        f = Path(tmp) / f'lvl-{time.time_ns()}.toml'
        f.write_text(text)
        return pilot.Segment(f)

    base = 'name = "x"\narea = "A"\n[[goal]]\nname = "g"\nflag = "F=1"\nkind = "reach"\ntargets = [{name = "t", at = [0, 0]}]\n'
    s = seg_of(base)
    check(pilot.humanize_level(A, s) == 2, 'the default for an exploration run is level 2')
    A.humanize = 0
    check(pilot.humanize_level(A, s) == 0, '--humanize 0 wins')
    A.humanize = None
    check(pilot.humanize_level(A, seg_of('humanize = 1\n' + base)) == 1, 'a segment\'s own `humanize` is the default of its runs')
    d = seg_of('name = "d"\narea = "A"\n[[goal]]\nname = "duel"\nkind = "duel"\ntargets = [{name = "opponent", follow = "opponent", kind = "duel", radius = 1.4}]\n')
    check(pilot.humanize_level(A, d) == 0, 'a duel is never humanized unless asked')
    A.humanize = 3
    check(pilot.humanize_level(A, d) == 3, 'asked, it is')


class Near:
    """What routelib.PrivateWorld answers (persons, doors, props near a point, the ground height ahead): a made-up world model for the sensor."""

    def __init__(self, persons=(), doors=(), props=(), ground=None):
        self.p, self.d, self.pr, self.g = list(persons), list(doors), list(props), ground

    @staticmethod
    def _near(objs, mp, x, z, r):
        return [(mp, o[0], o[1], 'Obj') for o in objs if math.hypot(o[0] - x, o[1] - z) <= r]

    def persons(self, mp, x, z, r):
        return self._near(self.p, mp, x, z, r)

    def doors(self, mp, x, z, r):
        return self._near(self.d, mp, x, z, r)

    def props(self, mp, x, z, r):
        return [o + ('sign',) for o in self._near(self.pr, mp, x, z, r)]

    def ground(self, mp, x, z, y):
        return self.g(mp, x, z, y) if self.g else y


def tactics_checks(tmp):
    """The ladder with the tactics library: the order comes from the book for the cause the sensor names, every rung is written back with its context, a
    block is one episode row, and a pilot that knows nothing behaves as the old ladder did."""
    def rung_labels(rd):
        return [d['choice'] for d in rows(rd, 'decision') if str(d['choice']).startswith('recover:') and d['choice'] not in ('recover:close-in', 'recover:replan')]

    def kit(name, world=None, mode='ranked'):
        book = tactics.Book(Path(tmp) / f'book-{name}')
        return book, {'book': book, 'sensor': tactics.Sensor(world), 'mode': mode}

    # a pilot that knows nothing: the old ladder, in its old order (an unknown cause, an empty book)
    book, kw = kit('parity')
    p, outcome, world, rd = play(tmp, [('t', 0, 40, 2.5)], [Post(0, 20, 2.2)], area='Fake_BigA', tactics=kw)
    rec = [e for e in rows(rd, 'recover') if e['status'] == 'recovered']
    check(outcome == 'solved' and rung_labels(rd) == ['recover:sidestep', 'recover:angle'] and rec[0]['rung'] == 'angle',
          f'an empty book and no world model: sidestep, then angle, as the old ladder ({rung_labels(rd)})')
    blocked = [e for e in rows(rd, 'recover') if e['status'] == 'blocked']
    check(blocked and blocked[0]['cause'] == 'unknown', 'the block row names the cause (unknown without a world model)')
    att = book.rows('attempt')
    check([(a['tactic'], a['outcome']) for a in att] == [('sidestep', 'failed'), ('angle', 'worked')] and all(a['map'] == 'Fake_BigA' and a['cause'] == 'unknown' and a['source'] == 'live' for a in att),
          f'each rung is written back with its map, cause and result ({[(a["tactic"], a["outcome"]) for a in att]})')
    check(all(a.get('at') and a.get('run') == rd.name and a.get('block') for a in att), 'with the place, the run and the block')
    blk = book.rows('block')
    check(len(blk) == 1 and blk[0]['tried'] == ['sidestep', 'angle'] and blk[0]['worked'] == 'angle' and blk[0]['how'] == 'recovered' and blk[0]['cause'] == 'unknown',
          f'and the block is one episode row ({blk})')
    dec = [d for d in rows(rd, 'decision') if d['choice'] == 'recover:sidestep'][0]
    check(dec.get('recover_cause') == 'unknown' and dec.get('recover_order') and dec['recover_order'][0]['tactic'] == 'sidestep',
          'the decision row says the cause and the order the ladder came from')
    s = p.recover_summary()
    check(s['mode'] == 'ranked' and s['causes'] == {'unknown': 1} and s['tactics'] == {'sidestep': {'tried': 1, 'worked': 0}, 'angle': {'tried': 1, 'worked': 1}},
          f"summary.json's recover block says the causes and what each tactic did ({s['causes']}, {s['tactics']})")
    # what worked there is first the next time, on another map: one rung instead of two
    p, outcome, world, rd = play(tmp, [('t', 0, 40, 2.5)], [Post(0, 20, 2.2)], area='Fake_BigB', tactics=kw)
    check(outcome == 'solved' and rung_labels(rd) == ['recover:angle'], f'the next block of the kind (another map) starts with what worked: angle first ({rung_labels(rd)})')

    # the control arm: the old order whatever the book says, but it still writes what it sees
    book2, kw2 = kit('fixed', mode='fixed')
    for i in range(6):
        book2.record('hop', 'unknown', 'worked', map='Fake_Elsewhere', source='journal', key=f'h{i}')
    p, outcome, world, rd = play(tmp, [('t', 0, 40, 2.5)], [Post(0, 20, 2.2)], area='Fake_BigC', tactics=kw2)
    check(rung_labels(rd)[:2] == ['recover:sidestep', 'recover:angle'] and len(book2.rows('attempt')) == 8, 'fixed: the old order though the book prefers hop; the attempts are still recorded')
    # a read-only library (the scoreboard's cells): ranked from what is there, nothing written, the summary's numbers still kept
    ro_book = tactics.Book(book2.dir, readonly=True)
    before = book2.path.read_bytes()
    p, outcome, world, rd = play(tmp, [('t', 0, 40, 2.5)], [Post(0, 20, 2.2)], area='Fake_BigD', tactics={'book': ro_book, 'sensor': tactics.Sensor(None), 'mode': 'ranked'})
    check(outcome == 'solved' and rung_labels(rd)[0] == 'recover:hop' and book2.path.read_bytes() == before and p.recover_summary()['tactics'].get('sidestep', {}).get('tried', 0) >= 0
          and sum(v['tried'] for v in p.recover_summary()['tactics'].values()) >= 1, f'read-only: ranked by the book (hop first), not a byte written, the run\'s own numbers kept ({rung_labels(rd)})')
    book3, kw3 = kit('ranked-hop')
    for i in range(6):
        book3.record('hop', 'unknown', 'worked', map='Fake_Elsewhere', source='journal', key=f'h{i}')
    p, outcome, world, rd = play(tmp, [('t', 0, 40, 2.5)], [Wall((-30, 20), (30, 20), low=True)], area='Fake_Fence2', tactics=kw3)
    check(outcome == 'solved' and rung_labels(rd) == ['recover:hop'], f'six wins of hop elsewhere: a low fence is cleared by the first rung ({rung_labels(rd)})')

    # the cause decides the order: a person in the way: sidestep, wait, a wider sidestep
    world_np = Near(persons=[(0.0, 18.0)])
    book4, kw4 = kit('npc', world_np)
    p, outcome, world, rd = play(tmp, [('t', 0, 40, 2.5)], [Post(0, 20, 2.2)], area='Fake_Npc', tactics=kw4)
    blocked = [e for e in rows(rd, 'recover') if e['status'] == 'blocked']
    check(blocked and blocked[0]['cause'] == 'npc-in-way' and blocked[0]['geom'].get('persons') == '1-2', f'a person at the post: npc-in-way ({blocked[0]["cause"] if blocked else None})')
    check(outcome == 'solved' and rung_labels(rd) == ['recover:sidestep', 'recover:wait', 'recover:sidestep-wide'],
          f'npc-in-way: sidestep, wait, a wider sidestep gets round ({rung_labels(rd)})')
    check(any(x == 'wait 4' for x in world.log), 'the wait was sent as the game side knows it')
    check({a['tactic'] for a in book4.rows('attempt')} == {'sidestep', 'wait', 'sidestep-wide'} and all(a['cause'] == 'npc-in-way' for a in book4.rows('attempt')),
          'attempts are filed under the cause')
    # a ledge from below: climb, jump, then the hop that clears the low fence
    world_up = Near(ground=lambda mp, x, z, y: y + 1.0)
    book5, kw5 = kit('ledge', world_up)
    p, outcome, world, rd = play(tmp, [('t', 0, 40, 2.5)], [Wall((-30, 20), (30, 20), low=True)], area='Fake_Ledge', tactics=kw5)
    check(outcome == 'solved' and rung_labels(rd) == ['recover:climb', 'recover:jump', 'recover:hop'], f'ledge-up: climb, jump, hop ({rung_labels(rd)})')
    check(any(x.startswith('climb timeout') for x in world.log) and any(x.startswith('jump ') for x in world.log), 'the climb and the jump steps were sent')
    # the ladder is capped: five tactics, then replan (the target is left and the point marked bad)
    box = [Wall((-10, 30), (10, 30)), Wall((-10, 30), (-10, 50)), Wall((10, 30), (10, 50)), Wall((-10, 50), (10, 50))]
    book6, kw6 = kit('cap')
    bad = recover.BadPoints(Path(tmp) / 'cache-cap')
    p, outcome, world, rd = play(tmp, [('boxed', 0, 40, 2.5), ('after', 40, 0, 2.5)], box, bad=bad, area='Fake_Cap', tactics=kw6)
    s = p.recover_summary()
    check(len(rung_labels(rd)) <= 5 and s['marked_bad'] == 1 and outcome == 'solved', f'five tactics at most, then replan ({rung_labels(rd)})')
    blk = book6.rows('block')
    check(blk and blk[0]['how'] == 'marked-bad' and blk[0].get('worked') is None and set(blk[0]['tried']) == {a['tactic'] for a in book6.rows('attempt')}, 'a spent ladder is a block row with nothing that worked')
    check(all(a['outcome'] == 'failed' for a in book6.rows('attempt')), 'and every rung of it a failure')
    # a segment with `straight = true` is played with no offline planner (the self-play's visits must walk into a block, not round it)
    saved_plan, pilot.world_plan = pilot.world_plan, (lambda: 'A PLANNER')
    try:
        sp = Path(tmp) / 'seg-straight.toml'
        sp.write_text(segment_text([('t', 0, 40, 2.5)], 'Fake_S', 40, 'straight = true\n'))
        plain = Path(tmp) / 'seg-plain.toml'
        plain.write_text(segment_text([('t', 0, 40, 2.5)], 'Fake_S', 40))
        mk = lambda path: pilot.Pilot(pilot.Segment(path), deciders.Rules(), pilot.Channel(Path(tmp) / f'live-{path.stem}'), Path(tmp), path.stem, lambda: True)  # noqa: E731
        check(pilot.Segment(sp).straight and not pilot.Segment(plain).straight and mk(sp).plan is None and mk(plain).plan == 'A PLANNER', 'straight = true: no offline planner; without it the planner as before')
    finally:
        pilot.world_plan = saved_plan
    p, outcome, world, rd = play(tmp, [('t', 0, 40, 2.5)], [Post(0, 20, 2.2)], area='Fake_Plain')
    blocked = [e for e in rows(rd, 'recover') if e['status'] == 'blocked']
    check(outcome == 'solved' and blocked and 'cause' not in blocked[0] and 'tactics' not in p.recover_summary(), 'without a tactics library the rows are as before')

    # the settings of a run (pilot.make_tactics): --tactics, $PILOT_TACTICS, $PILOT_LEARN
    class A:
        tactics, tactics_dir, tactics_source = None, str(Path(tmp) / 'book-args'), None

    keep = {k: os.environ.pop(k, None) for k in ('PILOT_TACTICS', 'PILOT_LEARN')}
    try:
        got = pilot.make_tactics(A, world=None)
        check(got and got['mode'] == 'ranked' and got['source'] == 'live' and str(got['book'].dir) == A.tactics_dir and got['sensor'].world is None, 'by default: ranked, filed as live, in the folder asked for')
        A.tactics, A.tactics_source = 'explore', 'selfplay'
        got = pilot.make_tactics(A, world=None)
        check(got['mode'] == 'explore' and got['source'] == 'selfplay', '--tactics explore --tactics-source selfplay (the nightly self-play)')
        A.tactics = 'off'
        check(pilot.make_tactics(A, world=None) is None, '--tactics off: the old ladder, nothing read or written')
        A.tactics = None
        os.environ['PILOT_TACTICS'] = 'fixed'
        check(pilot.make_tactics(A, world=None)['mode'] == 'fixed', '$PILOT_TACTICS=fixed: the old order, attempts still written')
        check(not pilot.make_tactics(A, world=None)['book'].readonly, 'a library is written by default')
        A.tactics_readonly = True
        check(pilot.make_tactics(A, world=None)['book'].readonly, '--tactics-readonly: the library is only read')
        A.tactics_readonly = False
        os.environ['PILOT_TACTICS_READONLY'] = '1'
        check(pilot.make_tactics(A, world=None)['book'].readonly, '$PILOT_TACTICS_READONLY=1 as well')
        del os.environ['PILOT_TACTICS_READONLY']
        os.environ['PILOT_LEARN'] = 'off'
        check(pilot.make_tactics(A, world=None) is None, '$PILOT_LEARN=off turns it off, whatever $PILOT_TACTICS says')
        A.tactics = 'ranked'
        check(pilot.make_tactics(A, world=None)['mode'] == 'ranked', 'the flag wins over the environment')
    finally:
        for k, v in keep.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v


def run():
    with tempfile.TemporaryDirectory(prefix='recover-test-') as t:
        tmp = Path(t)
        pilot.world_plan = lambda: None   # (the fake plane has no map: straight lines unless a test gives a plan)
        unit_checks(tmp)
        level_checks(tmp)
        regression_checks(tmp)
        rung_checks(tmp)
        sticky_go_checks(tmp)
        no_question_checks(tmp)
        identical_answer_checks(tmp)
        follow_checks(tmp)
        humanized_run_checks(tmp)
        vision_checks(tmp)
        tactics_checks(tmp)
    print('test_recover: all passed')


if __name__ == '__main__':
    run()
