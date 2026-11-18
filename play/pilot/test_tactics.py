#!/usr/bin/env python3
"""tactics.py: the tactics library (a catalogue of ways out of a stuck place, keyed by the stuck cause, every attempt recorded with its context, ranked
across all maps by success with a prior), the sensor that names the cause and the geometry around a stuck point, the demonstrations (a way out that
worked, kept relative to the place so it replays elsewhere) and the exploration order the nightly self-play uses. Made-up maps and numbers; no game,
no GPU, no network.   python3 -I -B test_tactics.py"""
import json
import math
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import recover  # noqa: E402
import tactics  # noqa: E402

FAILS, CHECKS = [], [0]

HSAP_VERBS = {'walk', 'run', 'press', 'stick', 'push', 'raw', 'until', 'wait', 'save', 'report', 'shot', 'duel', 'swing', 'shield', 'roll', 'sidestep', 'face',
              'approach', 'interact', 'advance', 'pickup', 'enter', 'faceat', 'ztarget', 'camera', 'ocarina', 'item', 'jump', 'climb', 'swim', 'dive', 'block',
              'strafe', 'guard', 'use', 'buy', 'choose', 'ride'}


def check(cond, what):
    CHECKS[0] += 1
    if not cond:
        FAILS.append(what)
        print('FAIL', what, flush=True)


def ctx_for(**kw):
    c = {'pos': (0.0, 0.0), 'block': (0.0, 0.0), 'camera': 0, 'sign': 1.0, 'side': 1, 'target': {'x': 0.0, 'z': 30.0, 'radius': 2.5},
         'go_lines': ['run 0.00 15.00 radius 1 timeout 10', 'run 0.00 30.00 radius 2.5 timeout 14'], 'hop_ok': True, 'event': 0,
         'doors': [], 'alt_lines': [], 'plan_from': None}
    c.update(kw)
    return c


class FakeWorld:
    """What routelib.PrivateWorld answers: persons, doors, props near a point, and the walkable ground height there."""

    def __init__(self, persons=(), doors=(), props=(), ground=None, climbs=()):
        self.p, self.d, self.pr, self.g, self.cl = list(persons), list(doors), list(props), ground or (lambda m, x, z, y: y), list(climbs)

    def climbables(self, mp, x, z, r):
        return self._near(self.cl, mp, x, z, r)

    def _near(self, objs, mp, x, z, r):
        return [(mp, o[0], o[1], o[2] if len(o) > 2 else 'obj') for o in objs if math.hypot(o[0] - x, o[1] - z) <= r]

    def persons(self, mp, x, z, r):
        return self._near(self.p, mp, x, z, r)

    def doors(self, mp, x, z, r):
        return self._near(self.d, mp, x, z, r)

    def props(self, mp, x, z, r):
        return [o + ('sign',) for o in self._near(self.pr, mp, x, z, r)]

    def ground(self, mp, x, z, y):
        return self.g(mp, x, z, y)


def sense(world, **kw):
    base = dict(map='Testland_Child', pos=(10.0, 100.0, 10.0), want=(10.0, 40.0), result='stuck', verb='run', detail='20.00 m from the point', moved=0.1)
    base.update(kw)
    return tactics.Sensor(world).sense(**base)


# ------------------------------------------------------------------------------------------------------ the catalogue

def catalogue_checks():
    check(set(tactics.LEGACY) <= set(tactics.TACTICS), 'the six rungs of the old ladder are tactics')
    check(tactics.LEGACY == recover.LADDER, 'the old ladder is the legacy order')
    check(all(c in tactics.ORDER for c in tactics.CAUSES), 'every cause has a static order')
    for c, order in tactics.ORDER.items():
        check(all(t in tactics.TACTICS for t in order) and len(set(order)) == len(order), f'order of {c}: known tactics, once each')
        check(order[-1] == 'replan' or 'replan' not in order, f'{c}: replan, when listed, is last')
    check(list(tactics.ORDER['unknown'])[:5] == ['sidestep', 'angle', 'roll', 'hop', 'next-point'],
          'an unknown cause starts with the old ladder in its old order: a pilot that knows nothing behaves as before')
    # every tactic builds hsap lines that the game side knows, finite numbers, the go tail last
    ctx = ctx_for(doors=[(3.0, 5.0, 'door')], alt_lines=['run 4.00 4.00 radius 1 timeout 8', 'climb up timeout 12'],
                  plan_from=lambda x, z: [f'run {x + 1:.2f} {z + 1:.2f} radius 1 timeout 9'])
    for tid in tactics.TACTICS:
        if tid in ('replan',):
            continue
        lines = tactics.build(tid, ctx)
        check(lines and all(isinstance(x, str) and x.split()[0] in HSAP_VERBS for x in lines), f'{tid}: builds hsap lines ({lines[:2]})')
        check(all('nan' not in x and 'inf' not in x for x in lines), f'{tid}: finite numbers')
    check(tactics.build('replan', ctx) == [], 'replan has no lines: the pilot plans')
    legacy = recover.Recovery(None)
    rs = legacy.new_state()
    rs.blocked = {'pos': (0, 0), 'lines': ctx['go_lines'], 'idx': 0}
    for tid in ('sidestep', 'angle', 'roll', 'hop', 'next-point'):
        rs = legacy.new_state()
        rs.blocked = {'pos': (0, 0), 'lines': ctx['go_lines'], 'idx': 0}
        rs.tried = [t for t in recover.LADDER if t != tid and t != 'replan']
        act = legacy.action(rs, {k: v for k, v in ctx.items() if k in ('pos', 'camera', 'sign', 'target', 'go_lines', 'hop_ok')})
        check(act.rung == tid and tactics.build(tid, ctx) == act.lines, f'{tid}: the catalogue builds what the old ladder built ({act.lines[:1]})')
    # geometry
    def mv(line):
        m = recover.parse_move(line)
        return m[1], m[2]
    x, z = mv(tactics.build('sidestep-wide', ctx)[0])
    check(abs(x - 6.0) < 0.01 and abs(z) < 0.01, f'sidestep-wide: 6 m to the left of a heading along +z ({x}, {z})')
    x, z = mv(tactics.build('sidestep-wide', ctx_for(side=-1))[0])
    check(abs(x + 6.0) < 0.01, 'sidestep-wide: the right side when the side says so')
    b, v = (mv(l) for l in tactics.build('angle-steep', ctx)[:2])
    check(abs(b[0]) < 0.01 and b[1] < -1.9 and v[0] < -3 and v[1] > b[1], f'angle-steep: back 2 m, then out 70 degrees to the other side ({b}, {v})')
    ang = math.degrees(math.atan2(v[0] - b[0], v[1] - b[1]))
    check(abs(abs(ang) - 70) < 0.5, f'angle-steep comes at 70 degrees ({ang:.1f})')
    lines = tactics.build('run-up', ctx)
    check(mv(lines[0])[1] <= -4.9 and lines[1].startswith('faceat 0.00 30.00') and lines[2].startswith('run 0.00 6.00') and 'mag 1' in lines[2], f'run-up: back 5 m, face, full push ({lines})')
    check(tactics.build('jump', ctx)[0].startswith('jump 0.00 2.50 radius 1.5 lead 3'), 'jump: the hsap jump step 2.5 m ahead with a run-up')
    ja = tactics.build('jump-a', ctx)
    check(ja[0].startswith('faceat') and ja[1].startswith('raw 0:LX=0+LY=32767/1400,0.35:A/100,0.7:A/100') and 'X/' not in ja[1], 'jump-a: the stick toward it, A twice, never X')
    check(tactics.build('climb', ctx)[:2] == ['faceat 0.00 30.00 20', 'climb timeout 10'], 'climb: face it and hold up')
    check(tactics.build('climb', dict(ctx, climb_at=(1.0, 2.0)))[:2] == ['faceat 1.00 2.00 20', 'climb timeout 10'], 'climb: face the climbable surface the world model knows, not the target')
    check(tactics.build('wait', ctx)[0] == 'wait 4' and tactics.build('wait-long', ctx)[0] == 'wait 10', 'wait 4 s, wait 10 s')
    check(tactics.build('talk-through', ctx)[0] == 'advance timeout 20', 'talk-through: advance the text')
    check(tactics.build('press-a', ctx)[:2] == ['faceat 0.00 30.00 20', 'interact force timeout 4'], 'press-a: face it, A at whatever prompt there is')
    ar = tactics.build('around', ctx)
    check(mv(ar[0])[0] > 5.5 and ar[1].startswith('run 7.00 1.00'), f'around: out to the side, then the planner\'s way from there ({ar})')
    check(tactics.build('around', ctx_for())[1:] == ctx_for()['go_lines'], 'around without a planner: out to the side, then the plan from the block')
    check(len(tactics.build('ring', ctx)) == 4 + len(ctx['go_lines']), 'ring: four points round the place')
    de = tactics.build('door-enter', ctx)
    check(de[0] == 'enter 3.00 5.00 through 3.00 8.00 timeout 25', f'door-enter: the nearest door, through to the heading\'s side ({de})')
    do = tactics.build('door-other', ctx)
    check(do[0].startswith('run 3.00 2.00') and do[1] == de[0], f'door-other: the far side first ({do})')
    check(tactics.build('swim', ctx)[0].startswith('swim 0.00 30.00 radius 2.5'), 'swim: the swim step toward the target')
    check(tactics.build('alt-edge', ctx) == ctx['alt_lines'], 'alt-edge: the world model\'s alternative edge as given')
    check(tactics.build('continue', ctx) == ctx['go_lines'], 'continue: carry on along the plan')
    # applicability
    ap = lambda tid, cause, **kw: tactics.applicable(tid, cause, ctx_for(**kw))  # noqa: E731
    check(not ap('door-enter', 'door-side') and ap('door-enter', 'door-side', doors=[(3, 5, 'd')]), 'door tactics need a door the world model knows')
    check(not ap('alt-edge', 'wall') and ap('alt-edge', 'wall', alt_lines=['run 1 1']), 'alt-edge needs an alternative edge')
    check(not ap('hop', 'wall', hop_ok=False) and not ap('hop', 'wall', camera=None) and ap('hop', 'wall'), 'hop needs hop_ok and a camera (as the old ladder)')
    check(not ap('roll', 'wall', camera=None), 'roll needs a camera')
    check(not ap('climb', 'npc-crowd') and ap('climb', 'ledge-up') and ap('talk-through', 'held') and not ap('talk-through', 'ledge-up'), 'a tactic belongs to its causes')
    check(not ap('next-point', 'wall', go_lines=['run 0.00 30.00 radius 1 timeout 10']) and ap('next-point', 'wall') and ap('next-point', 'wall', go_lines=['run 1 1'], block_lines=ctx['go_lines'], block_idx=0),
          'next-point needs a route point after the one that stopped')


# ------------------------------------------------------------------------------------------------------ the book: ranking

def new_book(tmp, name):
    return tactics.Book(Path(tmp) / name)


def add(book, tactic, cause, n, wins, **kw):
    kw.setdefault('map', 'Testland_Child')
    kw.setdefault('age', 'child')
    for i in range(n):
        book.record(tactic, cause, 'worked' if i < wins else 'failed', source='journal', **kw)


def book_checks(tmp):
    b = new_book(tmp, 'empty')
    for c in tactics.CAUSES:
        got = [r['tactic'] for r in b.rank(c)]
        want = [t for t in tactics.ORDER[c] if tactics.applicable(t, c, ctx_for(doors=[(1, 1, 'd')], alt_lines=['run 1 1'], plan_from=lambda x, z: ['run 1 1']))]
        check(got[:len(want)] == [t for t in want] or set(want) <= set(got), f'{c}: an empty book ranks as the static order ({got[:4]})')
    check([r['tactic'] for r in b.rank('unknown')][:5] == ['sidestep', 'angle', 'roll', 'hop', 'next-point'], 'empty: unknown = the old ladder')
    check(abs(tactics.prior('wall', 'sidestep') - 0.5) < 1e-9 and tactics.prior('wall', 'sidestep') > tactics.prior('wall', 'angle') > tactics.prior('wall', 'roll'),
          'the prior falls with the static rank')
    # evidence moves the order; one win does not
    b = new_book(tmp, 'evidence')
    add(b, 'hop', 'wall', 1, 1, map='Other_Child')
    check([r['tactic'] for r in b.rank('wall')][0] == 'sidestep', 'one win elsewhere does not overturn the prior')
    add(b, 'hop', 'wall', 3, 3, map='Other_Child')
    top = b.rank('wall')
    check(top[0]['tactic'] == 'hop' and top[0]['n'] == 4 and top[0]['wins'] == 4, f'four wins of four on another map put hop first ({[(r["tactic"], round(r["score"], 2)) for r in top[:3]]})')
    add(b, 'sidestep', 'wall', 4, 0, map='Another_Child')
    r = {x['tactic']: x for x in b.rank('wall')}
    check(r['sidestep']['score'] < r['angle']['score'], 'four failures drop a tactic below the next one')
    check({x['tactic']: x['n'] for x in b.rank('door-side')}.get('hop') is None or b.rank('door-side') != [], 'the evidence is per cause: wall wins say nothing of a door')
    check(b.rank('ledge-up')[0]['tactic'] == tactics.ORDER['ledge-up'][0], 'wall evidence leaves ledge-up\'s order alone')
    # across maps: wins recorded on map A rank on map B; a place's own history counts more
    b = new_book(tmp, 'across')
    add(b, 'wait', 'npc-crowd', 6, 6, map='Map_A', at=[0, 100, 0])
    check(b.rank('npc-crowd', map='Map_B', age='child')[0]['tactic'] == 'wait', 'ranked across all maps: six wins on map A rank first on map B')
    add(b, 'ring', 'npc-crowd', 1, 1, map='Map_B', at=[50.0, 100.0, 50.0])
    add(b, 'wait', 'npc-crowd', 2, 0, map='Map_B', at=[50.0, 100.0, 50.0])
    here = b.rank('npc-crowd', map='Map_B', age='child', at=[51.0, 100.0, 50.0])
    check(here[0]['tactic'] == 'ring' and [x['tactic'] for x in here].index('wait') > 1, f'at the place where wait failed twice and ring worked, ring is first ({[x["tactic"] for x in here[:3]]})')
    far = b.rank('npc-crowd', map='Map_B', age='child', at=[300.0, 100.0, 300.0])
    check(far[0]['tactic'] == 'wait', 'a place 250 m away does not weigh the local history')
    # geometry similarity weighs in
    check(tactics.geom_similarity({'ahead': 'up', 'persons': '0'}, {'ahead': 'up', 'persons': '0'}) == 1.0 and
          tactics.geom_similarity({'ahead': 'up', 'persons': '0'}, {'ahead': 'drop', 'persons': '0'}) == 0.5 and
          tactics.geom_similarity({}, {'ahead': 'up'}) == 0.0, 'geometry similarity: the share of the shared keys that agree, none shared: 0')
    # candidates restricts, neutral is not counted
    b = new_book(tmp, 'cand')
    b.record('sidestep', 'wall', 'neutral', map='M')
    check(b.counts('wall').get('sidestep', {}).get('n', 0) == 0, 'a neutral result is not an attempt')
    got = [r['tactic'] for r in b.rank('wall', candidates=['roll', 'hop'])]
    check(got == ['roll', 'hop'], f'candidates restrict the ranking ({got})')
    # a demonstration is a tactic of its own
    b = new_book(tmp, 'demo')
    S, u = (10.0, 20.0), (0.0, 1.0)
    d = b.add_demo('wall', [{'verb': 'walk', 'a': 0.0, 'b': 3.0, 'tail': 'radius 0.6 timeout 4'}, {'verb': 'run', 'a': 12.0, 'b': 3.0, 'tail': 'radius 1.5 timeout 8'}],
                   map='Testland_Child', age='child', at=[10.0, 100.0, 20.0], run='r1', source='demo')
    check(d and d['tactic'].startswith('demo:') and any(r['tactic'] == d['tactic'] for r in b.rank('wall')), 'a demonstration is ranked with the tactics')
    check(next(r for r in b.rank('wall') if r['tactic'] == d['tactic'])['n'] == 1, 'a demonstration counts as the one win it was seen to make')
    lines = tactics.build(d['tactic'], ctx_for(block=(50.0, 60.0), pos=(50.0, 60.0), target={'x': 50.0, 'z': 90.0, 'radius': 2.5}), book=b)
    check(lines[0] == 'walk 53.00 60.00 radius 0.6 timeout 4', f'a demonstration replays relative to the new place ({lines})')
    ctx_e = ctx_for(block=(0.0, 0.0), pos=(0.0, 0.0), target={'x': 30.0, 'z': 0.0, 'radius': 2.5})   # heading along +x
    lines = tactics.build(d['tactic'], ctx_e, book=b)
    x, z = (recover.parse_move(lines[1])[1], recover.parse_move(lines[1])[2])
    check(abs(x - 12.0) < 0.01 and abs(abs(z) - 3.0) < 0.01, f'a demonstration turns with the heading ({lines[1]})')
    check(not tactics.applicable(d['tactic'], 'ledge-up', ctx_for(), book=b) and tactics.applicable(d['tactic'], 'wall', ctx_for(), book=b), 'a demonstration applies to the cause it worked for')
    # exploration (the nightly self-play): the untried come before the proven-bad
    b = new_book(tmp, 'explore')
    add(b, 'sidestep', 'wall', 6, 0)
    add(b, 'angle', 'wall', 6, 1)
    exp = [r['tactic'] for r in b.rank('wall', explore=True)]
    greedy = [r['tactic'] for r in b.rank('wall')]
    check(exp.index('sidestep') > exp.index('jump') and exp.index('sidestep') > exp.index('jump-a') and greedy.index('sidestep') > greedy.index('roll') - 99,
          f'exploring: untried tactics go before a tactic that failed six times ({exp})')
    check(exp == [r['tactic'] for r in b.rank('wall', explore=True)] and greedy[0] != 'sidestep', 'exploring is deterministic; greedy leaves the failed one')
    # persistence: a second Book on the same folder reads the same rows; a key is added once
    b2 = tactics.Book(Path(tmp) / 'explore')
    check(len(b2.rows()) == len(b.rows()) == 12 and [r['tactic'] for r in b2.rank('wall')] == greedy, 'rows persist across Book objects')
    check(b.record('hop', 'wall', 'worked', map='M', key='k1') is not None and b.record('hop', 'wall', 'worked', map='M', key='k1') is None and len(b.rows()) == 13,
          'a row with a key already on file is not added twice')
    (Path(tmp) / 'explore' / 'book.jsonl').open('a').write('not json\n{"kind": "attempt"}\n')
    check(len(tactics.Book(Path(tmp) / 'explore').rows()) == 13, 'a torn or incomplete line is skipped')
    s = b.summary()
    check(s['attempts'] == 13 and s['causes']['wall']['sidestep'] == {'n': 6, 'wins': 0} and s['demos'] == 0, f'summary: attempts and wins by cause and tactic ({s["attempts"]})')
    # a read-only book is read and never written (the scoreboard's cells must not learn from their own test)
    src = new_book(tmp, 'ro-src')
    add(src, 'hop', 'wall', 4, 4, map='Other_Child')
    size = src.path.stat().st_size
    ro = tactics.Book(src.dir, readonly=True)
    check(ro.rank('wall')[0]['tactic'] == 'hop' and ro.record('hop', 'wall', 'worked', map='M') is None and ro.add_block(map='M', cause='wall') is None
          and ro.add_demo('wall', [{'verb': 'wait', 'raw': 'wait 4'}], map='M') is None and src.path.stat().st_size == size, 'a read-only book ranks from what is there and adds nothing')
    gone = tactics.Book(Path(tmp) / 'ro-empty', readonly=True)
    gone.record('hop', 'wall', 'worked', map='M')
    check(not (Path(tmp) / 'ro-empty').exists(), 'and does not even make its folder')
    check(tactics.default_dir().name == 'tactics' and tactics.default_dir().parent == HERE.parent.parent, 'the library lives beside the harness\'s route library')
    # an untried tactic starts at what the cause's tactics do, not above one measured at 28 percent (the seeded library's walls: sidestep 11 of 39, the rest nearly none)
    pooled = new_book(tmp, 'pooled')
    add(pooled, 'sidestep', 'wall', 39, 11)
    add(pooled, 'angle', 'wall', 16, 1)
    add(pooled, 'roll', 'wall', 15, 1)
    add(pooled, 'hop', 'wall', 8, 0)
    top = [r['tactic'] for r in pooled.rank('wall')]
    check(top[0] == 'sidestep' and top.index('sidestep-wide') < top.index('angle') and top.index('sidestep-wide') < top.index('roll'),
          f'a measured 28 percent stays first, an untried tactic comes before the ones measured near zero ({top[:5]})')

# ------------------------------------------------------------------------------------------------------ the sensor

def sensor_checks():
    s = sense(FakeWorld(), result='held', detail='')
    check(s['cause'] == 'held', 'an event holds Link: held')
    s = sense(None)
    check(s['cause'] == 'unknown' and s['map'] == 'Testland_Child' and s['age'] == 'child' and s['at'] == [10.0, 100.0, 10.0], f'no world model: unknown, the map and the age still known ({s["cause"]})')
    s = sense(FakeWorld(doors=[(10.0, 11.5, 'Door_A')]))
    check(s['cause'] == 'door-side' and s['geom'].get('door') == 'yes', f'a door on the way: door-side ({s["why"]})')
    s = sense(FakeWorld(persons=[(10.0, 11.5, 'Npc_A')]))
    check(s['cause'] == 'npc-in-way' and s['geom']['persons'] == '1-2', f'one person close by: npc-in-way ({s["cause"]})')
    s = sense(FakeWorld(persons=[(10.0, 11.5), (12.0, 12.0), (8.0, 9.0)]))
    check(s['cause'] == 'npc-crowd' and s['geom']['persons'] == '3+', 'three people: a crowd')
    s = sense(FakeWorld(props=[(10.5, 10.5, 'Sign')]))
    check(s['cause'] == 'wall' and s['geom']['prop'] == 'yes', 'a placed object by the point: wall')
    s = sense(FakeWorld(ground=lambda m, x, z, y: y + 1.2))
    check(s['cause'] == 'ledge-up' and s['geom']['ahead'] == 'up', 'ground 1.2 m higher ahead: ledge-up')
    s = sense(FakeWorld(ground=lambda m, x, z, y: y - 3.0))
    check(s['cause'] == 'drop-not-taken' and s['geom']['ahead'] == 'drop', 'ground 3 m lower ahead: drop-not-taken')
    s = sense(FakeWorld(ground=lambda m, x, z, y: None))
    check(s['cause'] == 'wall' and s['geom']['ahead'] == 'none', 'no ground ahead: wall at the mesh edge')
    s = sense(FakeWorld(ground=lambda m, x, z, y: None), prompt='Dive (Hold)')
    check(s['cause'] == 'water-edge', f'the mesh ends and the prompt offers a dive: the water\'s edge ({s["cause"]})')
    s = sense(FakeWorld(ground=lambda m, x, z, y: y + 1.0), target_y=106.5)
    check(s['cause'] == 'other-floor', f'the target is 6.5 m above Link and a ledge is in the way: another floor ({s["cause"]})')
    s = sense(FakeWorld(), result='timeout', moved=5.0, detail='12.0 m from the point')
    check(s['cause'] == 'slow', 'a timeout that kept moving: slow')
    check(sense(FakeWorld(), event=1)['cause'] == 'held', 'the tap\'s event flag alone is a held Link')
    check(sense(FakeWorld())['geom'].get('far') == 'far', 'the distance to the target is in the geometry (bucketed)')
    check(tactics.Sensor(FakeWorld()).sense(map='Plain_Adult', pos=(0.0, 0.0, 0.0), want=None, result='stuck', verb='walk', detail='')['age'] == 'adult', 'the age comes from the map name')
    boom = type('Boom', (), {'persons': lambda *a: 1 / 0, 'doors': lambda *a: [], 'props': lambda *a: [], 'ground': lambda *a: None})()
    s = sense(boom)
    check(s['cause'] in tactics.CAUSES, 'a world model that raises is no reason to stop: the sensor falls back')
    # a climbable surface (ivy, a vine, a ladder) by a wall: a ledge from below, and climb is ranked first (the Deku Tree wall that five other tactics did not pass in the game)
    s = sense(FakeWorld(climbs=[(10.5, 11.4, 'Vine')]))
    check(s['cause'] == 'ledge-up' and s['geom'].get('climb') == 'yes' and 'climbable' in s['why'], f'a climbable surface 1.4 m from the stuck point: ledge-up, climb in the geometry ({s["cause"]}: {s["why"]})')
    check(tactics.Book(Path(tempfile.gettempdir()) / 'tactics-no-such-book', readonly=True).rank(s['cause'], geom=s['geom'])[0]['tactic'] == 'climb', 'and the library ranks climb first for it')
    far = sense(FakeWorld(climbs=[(10.0, 15.0, 'Vine')]))
    check(far['cause'] == 'wall' and far['geom'].get('climb') == 'no', f'a climbable 5 m away is not what stops him ({far["cause"]})')
    check(sense(FakeWorld(doors=[(10.0, 11.5, 'Door_A')], climbs=[(10.5, 11.4, 'Vine')]))['cause'] == 'door-side' and sense(FakeWorld(), event=1)['cause'] == 'held', 'a door or a held text is not turned into a ledge by a vine')


# ------------------------------------------------------------------------------------------------------ demonstrations and inference

def demo_checks():
    S, W = (10.0, 20.0), (10.0, 50.0)   # heading +z
    steps = ['walk 13.00 20.00 radius 0.6 timeout 4', 'run 13.00 32.00 radius 1.5 timeout 8']
    rel = tactics.relative_steps(steps, S, W)
    check(rel and rel[0] == {'verb': 'walk', 'a': 0.0, 'b': 3.0, 'tail': 'radius 0.6 timeout 4'}, f'steps made relative to the place and the heading ({rel[0]})')
    back = tactics.absolute_steps(rel, (0.0, 0.0), (30.0, 0.0))
    check(back[0].startswith('walk ') and back[1].split()[0] == 'run', 'and back to absolute lines elsewhere')
    check(tactics.relative_steps(['wait 2', 'roll up'], S, W) == [{'verb': 'wait', 'raw': 'wait 2'}, {'verb': 'roll', 'raw': 'roll up'}], 'a step with no place is kept as it is')
    check(tactics.relative_steps(['watch Foo', 'end'], S, W) is None, 'steps that are not play (watch, end, save, shot, report) make no demonstration')
    # inferring the family of a recovery from its steps
    inf = lambda steps, S=(0.0, 0.0), W=(0.0, 30.0): tactics.infer_family(steps, S, W)  # noqa: E731
    check(inf(['roll up']) == 'roll' and inf(['roll to 0 30']) == 'roll', 'roll')
    check(inf(['raw 0:LX=0+LY=32767/800,0.15:X/100 1.2']) == 'hop', 'a stick and X: hop')
    check(inf(['jump 0.00 3.00 radius 1.5 lead 3']) == 'jump', 'the jump step: jump')
    check(inf(['walk 2.50 0.00 radius 0.6 timeout 4', 'run 0.00 30.00 radius 2']) == 'sidestep', 'a short step to the side then on: sidestep')
    check(inf(['walk 6.00 0.00 radius 0.8 timeout 6']) == 'sidestep-wide', 'a long step to the side: sidestep-wide')
    check(inf(['walk 0.00 -2.00 radius 0.4 timeout 4', 'walk -6.43 5.66 radius 1.5 timeout 6']) == 'angle', 'back up and out at an angle: angle')
    check(inf(['walk 0.00 -2.00 radius 0.4 timeout 4', 'walk -9.00 2.00 radius 1.5 timeout 6']) == 'angle-steep', 'back up and out steeply: angle-steep')
    check(inf(['walk 0.00 -5.00 radius 0.6 timeout 5', 'run 0.00 8.00 radius 1.5 timeout 6 mag 1.0']) == 'run-up', 'back up and run straight at it: run-up')
    check(inf(['wait 4']) == 'wait' and inf(['wait 10']) == 'wait-long' and inf(['advance timeout 20']) == 'talk-through', 'wait, wait-long, advance')
    check(inf(['until control timeout 150 press A every 1.5']) == 'talk-through' and inf(['interact force timeout 4']) == 'press-a', 'a text pressed through; A at a prompt')
    check(inf(['climb up timeout 12']) == 'climb' and inf(['swim 0 30 radius 2']) == 'swim', 'climb, swim')
    check(inf(['enter 3.00 5.00 through 3.00 8.00 timeout 25']) == 'door-enter', 'enter: door-enter')
    check(inf(['run 20.00 20.00 radius 1', 'run -5 3 radius 1', 'wait 0.1']) is None, 'a sequence that is no family stays a demonstration')
    check(tactics.FRONTIER_LABELS['angle-L-25'] == 'angle' and tactics.FRONTIER_LABELS['angle-R-80'] == 'angle-steep' and tactics.FRONTIER_LABELS['shift-L-3'] == 'sidestep'
          and tactics.FRONTIER_LABELS['shift-R-10'] == 'sidestep-wide' and tactics.FRONTIER_LABELS['roll-at'] == 'roll' and tactics.FRONTIER_LABELS['drop-run'] == 'run-up'
          and tactics.FRONTIER_LABELS['wait-4'] == 'wait' and tactics.FRONTIER_LABELS['wait-10'] == 'wait-long' and tactics.FRONTIER_LABELS['advance'] == 'talk-through'
          and tactics.FRONTIER_LABELS['ring-4'] == 'ring' and all(v in tactics.TACTICS for v in tactics.FRONTIER_LABELS.values()),
          'the frontier push\'s labels map onto tactics')


def main():
    catalogue_checks()
    with tempfile.TemporaryDirectory(prefix='test-tactics-') as t:
        book_checks(t)
    sensor_checks()
    demo_checks()
    if FAILS:
        raise SystemExit(f'test_tactics: {len(FAILS)} of {CHECKS[0]} checks FAILED')
    print(f'test_tactics: all {CHECKS[0]} checks passed')


if __name__ == '__main__':
    main()
