#!/usr/bin/env python3
"""frontier.py against made-up worlds: the attempts each stuck cause suggests (their geometry, the hsap lines they send, the ones already tried left
out), the explorer (a wall with a gap, a long wall whose gap is on the other side, a dead end, a map change, the deadline), the push (the library's
route to the frontier, the attempts at the stuck place, the one that works, the explorer after it, every attempt written into the library as it
ends), a cover push over the stuck clusters, and the live side: LiveIO and the whole game session against a FAKE hsap (a script written here that
tails steps.txt and writes out.jsonl and state.jsonl like the real one, with a walled world), the hold's plan, its refusals and its waiter command.
Made-up map names and coordinates; no game, no GPU, no network.   python3 -I -B test_frontier.py
"""
import json
import math
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import frontier  # noqa: E402
import routelib  # noqa: E402
import test_routelib as tr  # noqa: E402

FAILS, CHECKS = [], [0]


def check(cond, what):
    CHECKS[0] += 1
    if not cond:
        FAILS.append(what)
        print('FAIL', what, flush=True)


HSAP_VERBS = {'run', 'walk', 'faceat', 'roll', 'interact', 'raw', 'climb', 'wait', 'enter', 'advance', 'press', 'stick', 'camera', 'ztarget', 'end'}


def valid_line(line):
    w = line.split()
    if not w or w[0] not in HSAP_VERBS:
        return False
    if w[0] in ('run', 'walk'):
        try:
            float(w[1]), float(w[2])
        except (ValueError, IndexError):
            return False
        return 'radius' in w and 'timeout' in w
    return True


def geometry_checks():
    # stick_for is hsap's own formula: the camera's yaw minus the wanted yaw
    lx, ly = frontier.stick_for(180.0, 0.0, 1.0)
    check(abs(lx) < 1 and ly < -32000, f'a camera at 180 and a wish toward +z is the stick down ({lx}, {ly})')
    lx, ly = frontier.stick_for(180.0, 0.0, -1.0)
    check(abs(lx) < 1 and ly > 32000, f'a wish toward -z is the stick up ({lx}, {ly})')
    lx, ly = frontier.stick_for(180.0, 1.0, 0.0)
    check(abs(ly) < 1 and lx != 0, f'a wish at 90 degrees to the camera is the stick to a side ({lx}, {ly})')
    u = frontier.unit(3.0, 4.0)
    check(abs(u[0] - 0.6) < 1e-9 and abs(u[1] - 0.8) < 1e-9, 'unit')
    v = frontier.rot((0.0, 1.0), 90.0)
    check(abs(v[0] + 1) < 1e-9 and abs(v[1]) < 1e-9, f'rot 90 turns +z to -x ({v})')


def attempt_checks():
    ctx = {'at': [10.0, 100.0, 20.0], 'want': [10.0, 120.0], 'target': [10.0, 200.0], 'doors': [(12.0, 21.0, 'Door_X')], 'tried': set(), 'map': 'Testland_Child'}
    state = {'pos': [10.0, 100.0, 20.0], 'camera': 180.0, 'map': 'Testland_Child', 'event': 0}
    for cause in routelib.CAUSES + ('unknown',):
        atts = frontier.alternatives(cause, ctx)
        check(atts and len({a.label for a in atts}) == len(atts), f'{cause}: attempts with distinct labels ({[a.label for a in atts]})')
        bad = [ln for a in atts for ln in a.build(state, ctx) if not valid_line(ln)]
        check(not bad, f'{cause}: every line is an hsap step ({bad[:2]})')
    wall = frontier.alternatives('wall', ctx)
    check(wall[0].label == 'angle-L-25' and wall[1].label == 'angle-R-25', f'a wall: the gentlest change of angle first ({[a.label for a in wall[:4]]})')
    sh = next(a for a in wall if a.label == 'shift-L-6').build(state, ctx)
    p = [float(v) for v in sh[0].split()[1:3]]
    check(abs(math.dist(p, (10.0, 20.0)) - 6.0) < 0.05 and abs(p[1] - 20.0) < 0.05, f'shift-L-6 goes 6 m sideways of the heading, level with the stuck point ({p})')
    nxt = [float(v) for v in sh[1].split()[1:3]]
    check(nxt[1] > 29.0 and abs(nxt[0] - p[0]) < 0.05, f'then 10 m along the heading from there ({nxt})')
    ang = next(a for a in wall if a.label == 'angle-L-50').build(state, ctx)
    a0 = [float(v) for v in ang[0].split()[1:3]]
    check(math.dist(a0, (10, 20)) > 3.5 and abs(a0[0] - 10) > 2.0, f'angle-L-50 starts 4 m back along a line 50 degrees off the heading ({a0})')
    ja = next(a for a in wall if a.label == 'jump-a').build(state, ctx)
    raw = next(ln for ln in ja if ln.startswith('raw '))
    check('LX=' in raw and 'LY=' in raw and ':A/' in raw, f'jump-a is a stick toward the heading with A taps in the one sequence ({raw})')
    # tried ones are left out
    ctx2 = dict(ctx, tried={'angle-L-25', 'shift-L-3'})
    left = [a.label for a in frontier.alternatives('wall', ctx2)]
    check('angle-L-25' not in left and 'shift-L-3' not in left and 'angle-R-25' in left, f'attempts already made at this place are not made again ({left[:4]})')
    # causes get their own first moves
    check(frontier.alternatives('door-side', ctx)[0].label == 'door-enter', 'a door: enter it first')
    de = frontier.alternatives('door-side', ctx)[0].build(state, ctx)[0]
    check(de.startswith('enter 12.00 21.00 through '), f'the world model\'s door position is the enter point ({de})')
    check(frontier.alternatives('npc-crowd', ctx)[0].label.startswith('wait'), 'a crowd: wait first')
    check(frontier.alternatives('ledge-up', ctx)[0].label == 'climb', 'a ledge from below: climb first')
    check(frontier.alternatives('drop-not-taken', ctx)[0].label == 'drop-run', 'a drop not taken: run at the edge first')
    check(frontier.alternatives('held', ctx)[0].label == 'advance', 'held: advance the text')
    ctx3 = dict(ctx, doors=[])
    check(not any(a.label.startswith('door') for a in frontier.alternatives('door-side', ctx3)), 'no door known: no door attempts')


def explorer_checks():
    # a wall across the way with a gap: the explorer goes round
    io = tr.WalledWorld([(-200, 30, 20, 32), (25, 30, 200, 32)], pos=(0.0, 100.0, 0.0))
    ex = frontier.Explorer(io, target=(0.0, 100.0), radius=3.0, deadline=time.monotonic() + 30)
    res = ex.run(max_probes=120)
    check(res['reached'] and res['stopped'] == 'reached' and res['probes'] < 80, f'a wall with a gap: found it and arrived ({res})')
    check(res['best_remaining'] <= 3.0, 'the best distance is the arrival')
    # a wall whose gap is on the other side of a long wall: it gives up the first side after a while
    io = tr.WalledWorld([(-200, 30, -60, 32), (-40, 30, 200, 32)], pos=(0.0, 100.0, 0.0))
    ex = frontier.Explorer(io, target=(0.0, 100.0), radius=3.0, deadline=time.monotonic() + 30, flip_after_m=45.0)
    res = ex.run(max_probes=300)
    check(res['reached'], f'a long wall with the gap on the far side: reached after turning back ({res["stopped"]}, {res["probes"]} probes)')
    # a dead end: no way: stops without looping for ever
    box = [(-200, 30, 200, 32), (-200, -50, 200, -48), (-200, -50, -198, 32), (198, -50, 200, 32)]
    io = tr.WalledWorld(box, pos=(0.0, 100.0, 0.0))
    ex = frontier.Explorer(io, target=(0.0, 100.0), radius=3.0, deadline=time.monotonic() + 30)
    res = ex.run(max_probes=60)
    check(not res['reached'] and res['probes'] <= 60 and res['stopped'] in ('probes', 'trapped', 'budget'), f'a closed box is not left: it stops ({res["stopped"]}, {res["probes"]})')
    check(res['best_remaining'] < 100.0 and res['best_remaining'] >= 69.0, f'the best distance is the wall ({res["best_remaining"]})')
    # a deadline in the past: no probe
    io = tr.WalledWorld([], pos=(0.0, 100.0, 0.0))
    res = frontier.Explorer(io, target=(0.0, 100.0), radius=3.0, deadline=time.monotonic() - 1).run(max_probes=10)
    check(res['stopped'] == 'deadline' and res['probes'] == 0, f'the deadline stops it before a probe ({res})')

    # a map change ends it
    class Changing(tr.WalledWorld):
        def send(self, line):
            ev = super().send(line)
            if len(self.sent) == 3:
                self.map = 'Other_Child'
            return ev
    io = Changing([], pos=(0.0, 100.0, 0.0))
    res = frontier.Explorer(io, target=(0.0, 100.0), radius=3.0, deadline=time.monotonic() + 30).run(max_probes=10)
    check(res['stopped'] == 'map-changed', f'a load ends the exploration ({res["stopped"]})')
    # probes are run lines with a radius and a timeout, and the lines go into the result for the report
    io = tr.WalledWorld([(-200, 30, 200, 32)], pos=(0.0, 100.0, 0.0))
    res = frontier.Explorer(io, target=(0.0, 100.0), radius=3.0, deadline=time.monotonic() + 30).run(max_probes=8)
    check(all(valid_line(s) for s in io.sent) and len(res['trail']) >= 2, f'every probe is an hsap run line ({io.sent[:2]})')


class HurtWorld(tr.WalledWorld):
    """WalledWorld whose Link loses `per_step` quarter hearts at every step he spends at or past z = `from_z` (a boulder), life reported in the state."""

    def __init__(self, *a, life=24, per_step=4, from_z=0.0, **k):
        super().__init__(*a, **k)
        self.life, self.per_step, self.from_z = life, per_step, from_z

    def send(self, line):
        ev = super().send(line)
        if self.pos[2] >= self.from_z:
            self.life = max(0, self.life - self.per_step)
        return ev

    def state(self):
        st = super().state()
        st['life'] = self.life
        return st


def life_checks(tmp):
    # a hazard cluster starts with a retreat and a wait
    lib = routelib.RouteLib(tmp / 'libH')
    r = tr.FakeRun(tmp / 'libH-run', 'libH-run', start=(0, 100, 0))
    r.leg('run 0 50 radius 2.5 timeout 30', [(0, 100, 49.5)], 'reached')
    r.leg('run 0 200 radius 2.5 timeout 30', [(0, 100, 50.2)], 'stuck', detail='149.80 m from the point; moved under 0.3 m in 2.5 s at 0.0 100.0 50.2', hurt=8)
    lib.import_run(r.write(), build='old')
    lib.add_target('place', 'Testland_Child', 0.0, 200.0, age='child', radius=3.0)
    w = tr.FakeWorld()
    w.plan_result = {'ok': False, 'why': 'not-connected', 'detail': 'no link', 'near': None, 'steps': [], 'waypoints': []}
    io = tr.WalledWorld([(-6, 52, 6, 54)], pos=(0.3, 100.0, 0.2))
    res = frontier.Push(lib, io, target='place', map='Testland_Child', world=w, build='new', run='push-h', deadline=time.monotonic() + 60, log=lambda *_: None, expected=(0.3, 100.0, 0.2)).run()
    check(res['attempts'] and res['attempts'][0]['label'] == 'retreat-wait', f'a place that cost hearts is approached again only after a retreat and a wait ({[a["label"] for a in res["attempts"][:3]]})')
    ra = frontier.attempt_by_label('retreat-wait', {'at': [0.0, 100.0, 50.0], 'want': [0.0, 200.0], 'target': [0.0, 200.0], 'doors': [], 'tried': set()})
    lines = ra.build({}, {'at': [0.0, 100.0, 50.0], 'want': [0.0, 200.0], 'target': [0.0, 200.0]})
    check(all(valid_line(x) for x in lines) and float(lines[0].split()[2]) < 40.0 and any(x.startswith('wait ') for x in lines), f'retreat-wait goes back 12 m, waits, comes on ({lines})')
    # the explorer stops at a heart rather than die, and says dead at none
    io = HurtWorld([], pos=(0.0, 100.0, 0.0), life=12, per_step=4, from_z=5.0)
    res = frontier.Explorer(io, target=(0.0, 100.0), radius=3.0, deadline=time.monotonic() + 30).run(max_probes=40)
    check(res['stopped'] == 'life' and io.life <= 4 and io.life > 0, f'one heart left: the explorer stops (stopped {res["stopped"]}, life {io.life})')
    io = HurtWorld([], pos=(0.0, 100.0, 0.0), life=4, per_step=4, from_z=5.0)
    res = frontier.Explorer(io, target=(0.0, 100.0), radius=3.0, deadline=time.monotonic() + 30).run(max_probes=40)
    check(res['stopped'] == 'life', f'(at a heart to begin with it does not start) ({res["stopped"]})')
    # attempts at a block are given up once hearts are being lost there
    lib2 = routelib.RouteLib(tmp / 'libH2')
    r = tr.FakeRun(tmp / 'libH2-run', 'libH2-run', start=(0, 100, 0))
    r.leg('run 0 50 radius 2.5 timeout 30', [(0, 100, 49.5)], 'reached')
    r.leg('run 0 200 radius 2.5 timeout 30', [(0, 100, 50.2)], 'stuck', detail='149.80 m from the point; moved under 0.3 m in 2.5 s at 0.0 100.0 50.2')
    lib2.import_run(r.write(), build='old')
    lib2.add_target('place', 'Testland_Child', 0.0, 200.0, age='child', radius=3.0)
    io = HurtWorld([(-300, 52, 300, 54)], pos=(0.3, 100.0, 0.2), life=40, per_step=2, from_z=45.0)
    res = frontier.Push(lib2, io, target='place', map='Testland_Child', world=w, build='new', run='push-h2', deadline=time.monotonic() + 60, log=lambda *_: None, expected=(0.3, 100.0, 0.2), max_probes=30).run()
    check(0 < len(res['attempts']) < 8, f'hearts lost at the block end its attempts early ({len(res["attempts"])} made)')


def start_checks(tmp):
    # a frontier save is not made next to a person, a door or a sign: the boot presses A until the game is calm, and A at a prompt talks
    lib = library_with_frontier(tmp, 'libS')
    w = tr.FakeWorld()
    w.people = [('Testland_Child', 0.5, 50.5)]
    copy = tmp / 'copy-s'
    (copy / 'runs').mkdir(parents=True)
    sess = frontier.make_session(lib, 'place', name='s', wall=300, budget_s=200, tag='pl-s', save_name='f-s', base_save='kid-save', copy=str(copy), world=w)
    p = sess['start']['pos']
    check(math.hypot(p[0] - 0.5, p[2] - 50.5) >= 3.0 and abs(p[2] - 50.0) < 12.0 and sess['start'].get('moved_m', 0) > 0.5, f'the save is made at the nearest library point with no person within 3 m ({p}, moved {sess["start"].get("moved_m")} m)')
    sess0 = frontier.make_session(lib, 'place', name='s', wall=300, budget_s=200, tag='pl-s', save_name='f-s', base_save='kid-save', copy=str(copy))
    check(abs(sess0['start']['pos'][2] - 50.2) < 1.0 and sess0['start'].get('moved_m', 0) == 0, 'with no world model the point is the frontier itself')
    w.people = []
    w.door_list = [('Testland_Child', 1.0, 50.0, 'Door_Y')]
    sess1 = frontier.make_session(lib, 'place', name='s', wall=300, budget_s=200, tag='pl-s', save_name='f-s', base_save='kid-save', copy=str(copy), world=w)
    check(math.hypot(sess1['start']['pos'][0] - 1.0, sess1['start']['pos'][2] - 50.0) >= 2.5, f'nor within 2.5 m of a door ({sess1["start"]["pos"]})')


def library_with_frontier(tmp, name='lib'):
    """A library that knows a walk (0,0) -> (0,50) and a stuck at (0,50) wanting (0,200)."""
    lib = routelib.RouteLib(tmp / name)
    r = tr.FakeRun(tmp / f'{name}-run', f'{name}-run', start=(0, 100, 0))
    r.leg('run 0 50 radius 2.5 timeout 30', [(0, 100, 25), (0, 100, 49.5)], 'reached')
    r.leg('run 0 200 radius 2.5 timeout 30', [(0, 100, 50.2)], 'stuck', detail='149.80 m from the point; moved under 0.3 m in 2.5 s at 0.0 100.0 50.2')
    lib.import_run(r.write(), build='old')
    lib.add_target('place', 'Testland_Child', 0.0, 200.0, age='child', radius=3.0)
    return lib


def push_checks(tmp):
    lib = library_with_frontier(tmp)
    w = tr.FakeWorld()
    w.plan_result = {'ok': False, 'why': 'not-connected', 'detail': 'no link', 'near': None, 'steps': [], 'waypoints': []}
    f0 = lib.frontier('place')
    check(abs(f0['pos'][2] - 50.0) < 1.5 and 149 < f0['remaining_m'] < 151, f'the frontier before the push ({f0["pos"]}, {f0["remaining_m"]})')
    # the wall that stopped the run is 12 m wide; ten metres to the side is open
    io = tr.WalledWorld([(-6, 52, 6, 54)], pos=(0.3, 100.0, 0.2))
    push = frontier.Push(lib, io, target='place', map='Testland_Child', world=w, build='new', run='push-1', deadline=time.monotonic() + 60, log=lambda *_: None, expected=(0.3, 100.0, 0.2))
    res = push.run()
    check(res['ok'] and res['stopped'] == 'reached', f'the push reaches the place ({res["stopped"]}, {res.get("best_remaining_m")})')
    atts = res['attempts']
    check(atts and atts[0]['label'] == 'angle-L-25' and atts[0]['result'] == 'failed', f'the first alternative at the wall is the gentlest ({[a["label"] for a in atts[:3]]})')
    worked = [a for a in atts if a['result'] == 'worked']
    check(len(worked) == 1 and worked[0]['label'].startswith('shift-') and worked[0]['label'].endswith('-10'), f'the one that worked goes round the wall ({[a["label"] + ":" + a["result"] for a in atts]})')
    check(res['walker']['stopped'] in ('frontier', 'blocked') and res['start']['dist_m'] < 3.0, f'the library route was played first ({res["walker"]["stopped"]}, {res["start"]})')
    m = lib.map('Testland_Child')
    check(len(m.attempts) == len(atts) and {a['result'] for a in m.attempts} == {'failed', 'worked'}, f'every attempt is in the library as it ends ({len(m.attempts)} of {len(atts)})')
    cl = [c for c in m.clusters() if abs(c['at'][2] - 50.2) < 2.5]
    check(cl and cl[0]['resolved'] and cl[0]['worked'] and 'angle-L-25' in cl[0]['tried'], f'the stuck cluster lists what was tried and is resolved ({cl and (cl[0]["tried"], cl[0]["worked"])})')
    # a second push does not repeat the failed ones
    io2 = tr.WalledWorld([(-6, 52, 6, 54)], pos=(0.3, 100.0, 0.2))
    lib.add_target('place2', 'Testland_Child', 0.0, 200.0, age='child', radius=3.0)
    # (a cluster that an earlier attempt resolved is not attempted again: the route goes to the frontier and the explorer takes over)
    push2 = frontier.Push(lib, io2, target='place2', map='Testland_Child', world=w, build='new', run='push-2', deadline=time.monotonic() + 60, log=lambda *_: None)
    res2 = push2.run()
    check(not [a for a in res2['attempts'] if a['label'] == 'angle-L-25'], f'a second push skips the alternatives that failed there ({[a["label"] for a in res2["attempts"]][:3]})')
    check(res2['ok'], f'and still gets there ({res2["stopped"]})')

    # an unknown block: the library only knows the walk, no stuck place: the walker stops at the frontier with nothing to attempt there, the explorer
    # meets the wall, tries three alternatives at it (its cause from the stuck rule), then follows it round
    lib = routelib.RouteLib(tmp / 'libD')
    r = tr.FakeRun(tmp / 'libD-run', 'libD-run', start=(0, 100, 0))
    r.leg('run 0 50 radius 2.5 timeout 30', [(0, 100, 25), (0, 100, 49.5)], 'reached')
    lib.import_run(r.write(), build='old')
    lib.add_target('place', 'Testland_Child', 0.0, 200.0, age='child', radius=3.0)
    io = tr.WalledWorld([(-6, 80, 6, 82)], pos=(0.3, 100.0, 0.2))   # (the wall is 30 m on: what the explorer gained getting to it is not the attempts' doing)
    res = frontier.Push(lib, io, target='place', map='Testland_Child', world=w, build='new', run='push-6', deadline=time.monotonic() + 60, log=lambda *_: None, expected=(0.3, 100.0, 0.2)).run()
    check(res['ok'] and res['walker']['stopped'] == 'frontier', f'an unknown wall: the way round is found ({res["stopped"]}, walker {res["walker"]["stopped"]})')
    check(len(res['attempts']) == 3 and all(a['result'] == 'failed' and a['cause'] == 'wall' for a in res['attempts']), f'three alternatives at the new block, each with the block\'s cause ({[(a["label"], a["result"], a["cause"]) for a in res["attempts"]]})')
    check(res['explore']['reached'] and any(t['kind'] == 'follow' for t in res['explore']['trail']), 'then the explorer followed the wall round')

    # no way round at all: every alternative fails, the explorer has the rest of the time, the answer says what was tried
    lib = library_with_frontier(tmp, 'libB')
    io = tr.WalledWorld([(-300, 52, 300, 54)], pos=(0.3, 100.0, 0.2))
    push = frontier.Push(lib, io, target='place', map='Testland_Child', world=w, build='new', run='push-3', deadline=time.monotonic() + 60, max_attempts=4, max_probes=40, log=lambda *_: None)
    res = push.run()
    check(not res['ok'] and res['stopped'] in ('deadline', 'trapped', 'probes'), f'a wall with no way round: not reached, and it ends ({res["stopped"]})')
    check(len(res['attempts']) >= 4 and all(a['result'] == 'failed' for a in res['attempts']) and len([a for a in res['attempts'] if a['at'][2] > 50.0 and abs(a['at'][2] - 50.2) < 1.0]) == 4, f'at most max_attempts alternatives at one place ({len(res["attempts"])})')
    check(res['best_remaining_m'] < 150.5 and res['best_pos'], f'the best point is kept ({res["best_remaining_m"]}, {res["best_pos"]})')

    # a start away from where the save should have put Link: the walker takes the library route from where he is
    lib = library_with_frontier(tmp, 'libC')
    io = tr.WalledWorld([], pos=(0.0, 100.0, 12.0))
    res = frontier.Push(lib, io, target='place', map='Testland_Child', world=w, build='new', run='push-4', deadline=time.monotonic() + 20, log=lambda *_: None).run()
    check(res['start']['dist_m'] > 30 and res['ok'], f'a start 40 m before the frontier is walked to it ({res["start"]})')
    # a start on another map: refused, nothing sent
    io = tr.WalledWorld([], pos=(0.0, 100.0, 0.0), map='Elsewhere_Child')
    res = frontier.Push(lib, io, target='place', map='Testland_Child', world=w, build='new', run='push-5', deadline=time.monotonic() + 20, log=lambda *_: None).run()
    check(not res['ok'] and res['stopped'] == 'wrong-map' and not io.sent, f'a game on another map is refused before any step ({res["stopped"]})')


def cover_checks(tmp):
    lib = routelib.RouteLib(tmp / 'libcov')
    r = tr.FakeRun(tmp / 'libcov-run', 'cov', start=(0, 100, 0))
    r.leg('run 0 30 radius 2.5 timeout 30', [(0, 100, 30)], 'reached')
    r.leg('run 60 30 radius 2.5 timeout 30', [(0, 100, 40)], 'stuck', detail='60.00 m from the point; moved under 0.3 m in 2.5 s at 0.0 100.0 40.0')
    r.leg('run 0 30 radius 2.5 timeout 30', [(0, 100, 30)], 'reached')
    r.leg('run 60 10 radius 2.5 timeout 30', [(10, 100, 30)], 'stuck', detail='60.00 m from the point; moved under 0.3 m in 2.5 s at 10.0 100.0 30.0')
    lib.import_run(r.write(), build='old')
    lib.add_cover('legs', 'Testland_Child', [[0, 30], [60, 30], [60, 10], [0, 40]], age='child', radius=3.0)
    cv = lib.frontier('legs')
    check(cv['reached_n'] == 2 and len(cv['unreached']) == 2, f'two legs of four were walked ({cv["reached_n"]})')
    w = tr.FakeWorld()
    # a wall at z 41..43 stops the first cluster; the second (10, 30) wants (60, 10): a wall at x 12..14
    io = tr.WalledWorld([(-5, 41, 5, 43), (12, 25, 14, 35)], pos=(0.2, 100.0, 0.1))
    res = frontier.Push(lib, io, target='legs', map='Testland_Child', world=w, build='new', run='cov-push', deadline=time.monotonic() + 60, log=lambda *_: None, max_attempts=10, max_total_attempts=40).run()
    check(res['mode'] == 'clusters' and len(res['clusters']) == 2, f'a cover target visits its open stuck clusters ({res.get("mode")}, {len(res.get("clusters", []))})')
    check(sum(1 for c in res['clusters'] if c['worked']) >= 1, f'at least one cluster gave way ({[(c["at"], c["worked"]) for c in res["clusters"]]})')
    check(all(c['attempts'] for c in res['clusters']), 'each cluster was attempted')
    legs = res.get('legs') or []
    check(legs and all(l['stopped'] in ('reached', 'frontier', 'blocked') for l in legs) and any(l['stopped'] == 'reached' and l['leg'] == [60.0, 30.0] for l in legs), f'then the legs the library had not walked are tried, nearest first, closed loop ({[(l["leg"], l["stopped"]) for l in legs]})')
    check(res['legs_reached'] >= 1 and res['legs_tried'] == len(legs), f'and counted ({res.get("legs_reached")} of {res.get("legs_tried")})')


# ------------------------------------------------------------------------------------------------------------------------ the live side

FAKE_HSAP = r'''#!/usr/bin/env python3
"""A fake hsap for test_frontier: tails <live>/steps.txt and answers in hsap's own events, in a walled world (WALLS env as JSON)."""
import json, math, os, sys, time
from pathlib import Path
args = sys.argv[1:]
copy, tag, wall = args[0], args[1], int(args[2])
live = Path(args[args.index('--live') + 1])
if '--save' in args and 'badsave' in args[args.index('--save') + 1] and os.environ.get('FAKE_BAD_SAVE'):
    sys.exit(3)   # (the game could not start from a save made at a point)
live.mkdir(parents=True, exist_ok=True)
walls = json.loads(os.environ.get('FAKE_WALLS', '[]'))
pos = json.loads(os.environ.get('FAKE_START', '[0.0, 100.0, 0.0]'))
MAP = os.environ.get('FAKE_MAP', 'Testland_Child')
slow = float(os.environ.get('FAKE_SLOW', '0'))
out = open(live / 'out.jsonl', 'a')
state = open(live / 'state.jsonl', 'a')
t0 = time.time()
frame = [7000]
def emit(**e):
    out.write(json.dumps(e) + '\n'); out.flush()
def sample():
    frame[0] += 6
    row = {'t': round(1000 + time.time() - t0, 3), 'frame': frame[0], 'map': MAP, 'pos': [round(c, 2) for c in pos], 'facing': 0.0, 'camera': 180.0, 'event': 0, 'loading': 0,
           'life': 16, 'max_life': 16, 'rupees': 1, 'prompt': 'Empty', 'music': '', 'changed': {}, 'child': 1}
    state.write(json.dumps(row) + '\n'); state.flush()
    return row
def st(why):
    emit(ev='state', why=why, n=frame[0], t=round(time.time() - t0, 2), frame=frame[0], pos=[round(c, 2) for c in pos], facing=0.0, camera=180.0, area=MAP, prompt='Empty', music='', scene=False,
         event=0, loading=0, child=1, life=16, max_life=16, rupees=1, last={}, flags={}, changed=[])
def blocked(x, z):
    return any(a <= x <= c and b <= z <= d for a, b, c, d in walls)
emit(ev='note', text=f'hs-run: /h/hs-run.sh {copy} {tag} {wall} --user /h/saves/fake HOS_CONTROL=/tmp/x/control.sock', boot='continue')
sample(); sample()
emit(ev='gameplay', t=0.0, frame=frame[0], area=MAP)
sample(); st('wait')
steps = live / 'steps.txt'
n_line = 0
done = False
start = time.time()
while not done and time.time() - start < wall:
    lines = steps.read_text().splitlines() if steps.exists() else []
    if n_line >= len(lines):
        time.sleep(0.02); continue
    src = lines[n_line]; n_line += 1
    w = src.split('#', 1)[0].split()
    if not w:
        continue
    t_in = time.time()
    res, detail, moved = 'done', '', 0.0
    if w[0] in ('run', 'walk'):
        x, z = float(w[1]), float(w[2]); rad = float(w[w.index('radius') + 1]) if 'radius' in w else 1.0
        x0, z0 = pos[0], pos[2]
        n = max(1, int(math.dist((x0, z0), (x, z)) / 0.6)); res = 'reached'
        for i in range(1, n + 1):
            if math.dist((pos[0], pos[2]), (x, z)) <= rad:
                break
            px, pz = x0 + (x - x0) * i / n, z0 + (z - z0) * i / n
            if blocked(px, pz):
                res = 'stuck'; break
            pos[0], pos[2] = px, pz; sample()
            if slow: time.sleep(slow)
        moved = round(math.dist((x0, z0), (pos[0], pos[2])), 2)
        dd = math.dist((pos[0], pos[2]), (x, z))
        detail = f'{dd:.2f} m from the point' + ('; moved under 0.3 m in 2.5 s at %.1f %.1f %.1f' % tuple(pos) if res == 'stuck' else '')
    elif w[0] == 'wait':
        time.sleep(min(0.05, float(w[1]) * 0.01)); sample()
    elif w[0] == 'end':
        done = True
    sample()
    emit(ev='step', **{'in': n_line, 'src': src, 'result': res, 'secs': round(time.time() - t_in, 2), 'moved': moved, 'detail': detail, 'pos': [round(c, 2) for c in pos], 't': round(time.time() - t0, 2)})
    st('wait')
emit(ev='done', t=round(time.time() - t0, 2))
emit(ev='note', text='game stopped')
'''


def live_checks(tmp):
    fake = tmp / 'fake_hsap.py'
    fake.write_text(FAKE_HSAP)
    # LiveIO against the fake
    live = tmp / 'live1'
    env = dict(os.environ, FAKE_WALLS=json.dumps([[-6, 52, 6, 54]]))
    proc = frontier.spawn([sys.executable, '-I', '-B', str(fake), '/g/.copy', 'tag-live', '60', '--live', str(live)], env=env, log=tmp / 'fake1.out')
    try:
        io = frontier.LiveIO(live, alive=lambda: proc.poll() is None)
        st = io.wait_gameplay(20)
        check(st and st['map'] == 'Testland_Child' and st['pos'][2] == 0.0, f'LiveIO waits for gameplay and reads the first state ({st})')
        ev = io.send('run 0 20 radius 2 timeout 10')
        check(ev['result'] == 'reached' and abs(io.state()['pos'][2] - 18.0) < 2.5, f'send returns the step event and state() the position after it ({ev["result"]}, {io.state()["pos"]})')
        ev = io.send('run 0 80 radius 2 timeout 10')
        check(ev['result'] == 'stuck' and abs(ev['pos'][2] - 51.7) < 1.0 and 'm from the point' in ev['detail'], f'a stuck step carries its position and detail ({ev["result"]}, {ev["pos"]})')
        ev = io.send('end')
        check(ev['result'] == 'done', 'end is a step too')
        for _ in range(100):
            if proc.poll() is not None:
                break
            time.sleep(0.05)
        check(proc.poll() is not None, 'the fake game ended with end')
    finally:
        frontier.stop_pid(proc.pid)
    # the whole game session: library, fake game, push, import
    lib = library_with_frontier(tmp, 'liblive')
    copy = tmp / 'copy-a'
    (copy / 'runs').mkdir(parents=True)
    (copy / 'built-from.txt').write_text('17c44b80f69a7088e38ce93757fa5749330a997e\n')
    save = tmp / 'save-x'
    save.mkdir()
    w = tr.FakeWorld()
    w.plan_result = {'ok': False, 'why': 'not-connected', 'detail': 'no link', 'near': None, 'steps': [], 'waypoints': []}
    sess = {'name': 'dm', 'target': 'place', 'map': 'Testland_Child', 'save': str(save), 'wall': 60, 'budget_s': 40, 'tag': 'pl-test-dm', 'shots': 0, 'age': 'child'}
    env = dict(os.environ, FAKE_WALLS=json.dumps([[-6, 52, 6, 54]]), FAKE_START='[0.3, 100.0, 0.2]')
    out = tmp / 'hold-out'
    row = frontier.run_session(sess, lib, copy=copy, hsap=fake, out=out, world=w, env=env, deadline=time.monotonic() + 60, log=lambda *_: None, boot_s=20)
    check(row['status'] == 'done' and row['push']['ok'], f'a session against the fake game reaches the place ({row.get("status")}, {row.get("push", {}).get("stopped")})')
    check((out / 'dm' / 'pilot' / 'live' / 'state.jsonl').is_file() and (out / 'dm' / 'pilot' / 'live' / 'out.jsonl').is_file(), 'the session keeps the run\'s journals')
    imp = row['import']
    check(imp['build'] == '17c44b80f' and imp['metres'] > 50 and 'place' in imp['frontier_gain'] and imp['frontier_gain']['place'] > 100, f'the run is imported into the library with its frontier gain ({imp.get("build")}, {imp.get("metres")}, {imp.get("frontier_gain")})')
    f = lib.frontier('place')
    check(f['reached'] and f['remaining_m'] <= 3.0, f'the library\'s frontier is now the place itself ({f["remaining_m"]})')
    check(any(a['result'] == 'worked' for a in lib.map('Testland_Child').attempts), 'the worked attempt is in the library')
    # a warp where the build has one: the placer is asked for the frontier point after gameplay, its answer is in the row, and the push goes on from where Link is
    calls = []

    def placer(spec, game_run, env=None):
        calls.append((dict(spec), str(game_run)))
        return {'ok': True, 'warp': {'ok': True}, 'steps': [['teleport', 'verified']]}
    lib_w = library_with_frontier(tmp, 'libwarp')
    sess_w = dict(sess, name='warped', tag='pl-test-warp', warp=True, start={'pos': [0.0, 100.0, 49.0], 'yaw': 0.0}, expected=[0.3, 100.0, 0.2])
    row_w = frontier.run_session(sess_w, lib_w, copy=copy, hsap=fake, out=out, world=w, env=env, deadline=time.monotonic() + 60, log=lambda *_: None, boot_s=20, placer=placer)
    check(len(calls) == 1 and calls[0][0]['to'] == 'Testland_Child' and calls[0][0]['x'] == 0.0 and calls[0][0]['z'] == 49.0 and calls[0][0]['y'] == 100.0 and calls[0][0]['age'] == 'child' and calls[0][1].endswith('runs/pl-test-warp'),
          f'a warp session asks the placer for the frontier point on the game\'s run folder ({calls})')
    check(row_w['status'] == 'done' and row_w['warp'] == {'ok': True, 'warped': True, 'error': None}, f'the row says the warp worked ({row_w.get("warp")})')
    row_x = frontier.run_session(dict(sess_w, name='nowarp', tag='pl-test-nowarp'), lib_w, copy=copy, hsap=fake, out=out, world=w, env=env, deadline=time.monotonic() + 60, log=lambda *_: None, boot_s=20,
                                 placer=lambda *a, **k: {'ok': False, 'error': 'no !place in this build'})
    check(row_x['status'] == 'done' and row_x['warp']['warped'] is False and 'no !place' in row_x['warp']['error'], f'a build with no warp: the row says so and the walk goes on ({row_x.get("warp")})')
    # the save did not put Link on the map: the harness's own placement at the map's entrance is asked for (no coordinates), the walk follows; the answer is in the row
    calls.clear()
    lib_m = library_with_frontier(tmp, 'libwrong')
    env_m = dict(env, FAKE_MAP='Wrongland_Child')
    row_m = frontier.run_session(dict(sess, name='wrongmap', tag='pl-test-wrong'), lib_m, copy=copy, hsap=fake, out=out, world=w, env=env_m, deadline=time.monotonic() + 60, log=lambda *_: None, boot_s=20, placer=placer)
    check(len(calls) == 1 and 'x' not in calls[0][0] and calls[0][0]['to'] == 'Testland_Child' and calls[0][0]['age'] == 'child' and row_m['place']['ok'], f'a game on the wrong map is placed at the entrance, not warped ({calls}, {row_m.get("place")})')
    check(row_m['push']['stopped'] == 'wrong-map' and row_m['status'] == 'done', f'(the fake game cannot move: the push says wrong-map, nothing was sent) ({row_m["push"]["stopped"]})')
    # a game that cannot start from the save made at the point is tried again from the base save, placed at the entrance
    plan_r = {'name': 'hold-r', 'lib': str(lib.root), 'copy': str(copy), 'hsap': str(fake), 'hold_seconds': 700, 'world': None,
              'sessions': [dict(sess, name='boots', tag='pl-test-boots', save=str(tmp / 'badsave-x'), retry_save=str(save), wall=120, budget_s=20, shots=0)]}
    old_env = {k: os.environ.get(k) for k in ('FAKE_WALLS', 'FAKE_START', 'FAKE_BAD_SAVE')}
    os.environ.update(FAKE_WALLS='[]', FAKE_START='[0.0, 100.0, 0.0]', FAKE_BAD_SAVE='1')
    try:
        rc = frontier.run_hold(plan_r, tmp / 'out-r', log=lambda *_: None)
    finally:
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    rows_r = json.loads((tmp / 'out-r' / 'result.json').read_text())['rows']
    check(rc == 0 and [r['status'] for r in rows_r] == ['no-gameplay', 'done'] and rows_r[1]['name'] == 'boots-retry', f'a boot that fails is retried once from the base save ({[(r["name"], r["status"]) for r in rows_r]})')
    # a game that never starts: the session says so, imports nothing
    broken = tmp / 'broken_hsap.py'
    broken.write_text('import sys; sys.exit(3)\n')
    row = frontier.run_session(dict(sess, name='dead', tag='pl-test-dead'), lib, copy=copy, hsap=broken, out=out, world=w, env=env, deadline=time.monotonic() + 30, log=lambda *_: None, boot_s=3)
    check(row['status'] == 'no-gameplay' and 'import' not in row, f'a game that never reaches play: no push, no import ({row["status"]})')


def hold_checks(tmp):
    lib = library_with_frontier(tmp, 'libhold')
    lib.add_target('place', 'Testland_Child', 0.0, 200.0, age='child', radius=3.0)
    copy = tmp / 'copy-h'
    (copy / 'runs').mkdir(parents=True)
    plan = {'name': 'hold-x', 'lib': str(lib.root), 'copy': str(copy), 'hsap': str(HERE.parent / 'hsap.py'), 'hold_seconds': 1100, 'world': None,
            'sessions': [{'name': 'a', 'target': 'place', 'map': 'Testland_Child', 'save': str(tmp), 'wall': 300, 'budget_s': 250, 'tag': 'pl-hold-a', 'age': 'child'},
                         {'name': 'b', 'target': 'place', 'map': 'Testland_Child', 'save': str(tmp), 'wall': 300, 'budget_s': 250, 'tag': 'pl-hold-b', 'age': 'child'}]}
    pp = tmp / 'PathLib-plan.json'
    pp.write_text(json.dumps(plan))
    p = frontier.load_plan(pp)
    check(p['name'] == 'hold-x' and len(p['sessions']) == 2, 'the plan loads')
    check(not frontier.plan_errors(p), f'a good plan has no errors ({frontier.plan_errors(p)})')
    bad = json.loads(pp.read_text())
    bad['sessions'][1]['tag'] = 'pl-hold-a'
    bad['sessions'][0]['target'] = 'nowhere'
    (tmp / 'bad.json').write_text(json.dumps(bad))
    errs = frontier.plan_errors(frontier.load_plan(tmp / 'bad.json'))
    check(any('duplicate' in e for e in errs) and any('nowhere' in e for e in errs), f'a duplicate tag and an unknown target are refused ({errs})')
    bad['sessions'] = [dict(bad['sessions'][0], target='place', tag='t', wall=900), dict(bad['sessions'][1], tag='u', wall=900)]
    (tmp / 'bad2.json').write_text(json.dumps(bad))
    check(any('hold' in e for e in frontier.plan_errors(frontier.load_plan(tmp / 'bad2.json'))), 'sessions that cannot fit the hold are refused')
    q, m = str(tmp / 'quiet.lock'), str(tmp / 'measuring.lock')
    cmd = frontier.queue_command(pp, p, tmp / 'out-h', quiet=q, measuring=m)
    check(cmd[:4] == ['setsid', 'env', '--default-signal=HUP', 'flock'] and q in cmd and m in cmd and cmd.index(q) < cmd.index(m) and 'timeout' in cmd and '1100' in cmd and '-x' in cmd, f'the waiter command takes both locks and a timeout ({cmd[:14]})')
    saved_locks = frontier.QUIET, frontier.MEASURING
    frontier.QUIET = frontier.MEASURING = None   # (the lock files are this machine's own values, set by the environment: with none the waiter is refused, nothing is guessed)
    try:
        refused = []
        for kw in ({}, {'quiet': q}, {'measuring': m}):
            try:
                frontier.queue_command(pp, p, tmp / 'out-h', **kw)
            except ValueError as e:
                refused.append(str(e))
        check(len(refused) == 3 and all('PILOT_QUIET_LOCK' in e and 'PILOT_MEASURING_LOCK' in e for e in refused), f'a waiter with no quiet lock or no measuring lock is refused, naming the settings ({refused})')
    finally:
        frontier.QUIET, frontier.MEASURING = saved_locks
    for env_, want in (({'PILOT_QUIET_LOCK': q, 'PILOT_MEASURING_LOCK': m}, [q, m]), ({}, ['None', 'None'])):
        r = subprocess.run([sys.executable, '-I', '-B', '-c', f'import sys; sys.path.insert(0, {str(HERE)!r}); import frontier; print(frontier.QUIET, frontier.MEASURING)'],
                           env={**{k: v for k, v in os.environ.items() if not k.startswith('PILOT_')}, **env_}, capture_output=True, text=True)
        check(r.stdout.split() == want, f'the lock files are $PILOT_QUIET_LOCK and $PILOT_MEASURING_LOCK, no default ({r.stdout!r} {r.stderr[-100:]!r})')
    check(any('PathLib' in c for c in cmd), 'the command names PathLib so the lane can recognise it')
    check(str(tmp / 'out-h') in cmd, 'it carries the output folder')
    # the plan from the library: sessions from the targets, saves named
    sess = frontier.make_session(lib, 'place', name='x', wall=300, budget_s=250, tag='pl-x', save_name='frontier-place', base_save='kid-save', copy=str(copy))
    check(sess['map'] == 'Testland_Child' and sess['target'] == 'place' and sess['start']['pos'][2] > 49 and sess['start']['yaw'] is not None, f'a session starts at the frontier point with a yaw toward the stuck point\'s want ({sess["start"]})')
    cmd = frontier.save_command(sess, tmp / 'saves', game=str(copy))
    check(cmd[1].endswith('hs_make_save.py') and '--start' in cmd and cmd[cmd.index('--start') + 1].startswith('Testland_Child:') and '--from' in cmd and '--out' in cmd, f'the save command is hs_make_save with the start at the frontier ({cmd})')
    check(cmd[cmd.index('--age') + 1] == 'child', 'with the age')
    lib.add_cover('legs2', 'Testland_Child', [[0, 50], [0, 150]], age='child', radius=3.0)
    sc = frontier.make_session(lib, 'legs2', name='c', wall=300, budget_s=200, tag='pl-c', save_name='frontier-legs2', base_save='kid-save', copy=str(copy))
    check(abs(sc['start']['pos'][2] - 50.2) < 1.0, f'a cover session starts at the open stuck place that stopped most runs ({sc["start"]["pos"]})')


def run():
    with tempfile.TemporaryDirectory(prefix='test-frontier-') as t:
        tmp = Path(t)
        geometry_checks()
        attempt_checks()
        explorer_checks()
        push_checks(tmp)
        cover_checks(tmp)
        life_checks(tmp)
        start_checks(tmp)
        live_checks(tmp)
        hold_checks(tmp)


def main():
    run()
    if FAILS:
        raise SystemExit(f'test_frontier: {len(FAILS)} of {CHECKS[0]} checks FAILED')
    print(f'test_frontier: all {CHECKS[0]} checks passed')


if __name__ == '__main__':
    main()
