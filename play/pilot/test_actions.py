#!/usr/bin/env python3
"""The actions of actions.py without a game and without a network: song data and the note orders, the obstacles a plan ends at (jump, ledge, ivy,
drop, door, crawl hole), the conditions (each proved by state: a place, a count, a map, a result), the candidates of every kind, the rules played against
small invented worlds, and every candidate's step lines run through hsap's own parser against the simulated bridge. Nothing here is game data.

    python3 -I -B test_actions.py        (test_pilot.py calls run() too)
"""
import contextlib
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import actions  # noqa: E402
import deciders  # noqa: E402
import hsap  # noqa: E402
import interact  # noqa: E402
import test_interact as TI  # noqa: E402

check, state, Target, Goal, step, nums, Sim, WithWorld = TI.check, TI.state, TI.Target, TI.Goal, TI.step, TI.nums, TI.Sim, TI.WithWorld
labels = TI.labels
SONGS = {'_buttons': ['L', 'R', 'Y', 'X', 'A'], 'song-a': '2 4 1 5 3 4', 'song-b': '4 5 3 1 2 4'}   # invented songs (pitches 1..5): the pitches decide which note orders differ


@contextlib.contextmanager
def song_file(data):
    """PILOT_SONG_PITCHES points at a file of these invented songs for the length of the block."""
    with tempfile.TemporaryDirectory() as d:
        Path(d, 'sp.json').write_text(json.dumps(data))
        os.environ['PILOT_SONG_PITCHES'] = str(Path(d, 'sp.json'))
        try:
            yield
        finally:
            os.environ.pop('PILOT_SONG_PITCHES', None)


def plan_result(why, near, after, kind, needed, steps=None):
    return {'ok': False, 'why': why, 'near': near, 'after': after, 'edge': kind, 'needed': needed, 'steps': steps or [f'run {near[0]} {near[1]} radius 1'],
            'length': 10.0}


def link(kind, a, b, height=0.0, gap=None, actor=None):
    out = {'kind': kind, 'from': a, 'to': b, 'height': height, 'gap': gap, 'allowed': False}
    if actor:
        out['actor'] = actor
    return out


# ---- songs

def song_checks():
    with tempfile.TemporaryDirectory() as d:
        f = Path(d, 'sp.json')
        f.write_text(json.dumps({'_buttons': ['L', 'R', 'Y', 'X', 'A'], 'song-a': '1 3 5 2 4 1', 'bad': '1 9', 'junk': 'x y'}))
        os.environ['PILOT_SONG_PITCHES'] = str(f)
        os.environ.pop('PILOT_NOTE_BUTTONS', None)
        try:
            check(actions.song_table() == {'song-a': [1, 3, 5, 2, 4, 1]}, f'song_table keeps whole songs of pitches 1..5 ({actions.song_table()})')
            orders = actions.note_orders()
            check(orders[0] == ('L', 'R', 'Y', 'X', 'A') and ('L', 'R', 'A', 'Y', 'X') in orders and len(orders) == 2,
                  f'the confirmed order first, the other guess second, no duplicate ({orders})')
            check(actions.song_buttons('song-a', orders[0]) == ['L', 'Y', 'A', 'R', 'X', 'L'] and actions.song_buttons('song-a', orders[1]) == ['L', 'A', 'X', 'R', 'Y', 'L'],
                  'a song by two note orders: pitches 1 3 5 2 4 1 are L Y A R X L under the first, L A X R Y L under the second')
            check(actions.song_buttons('nothing', orders[0]) == [], 'an unknown song has no buttons')
            os.environ['PILOT_NOTE_BUTTONS'] = 'L R A Y X'
            check(actions.note_orders()[0] == ('L', 'R', 'A', 'Y', 'X'), 'PILOT_NOTE_BUTTONS names the order believed')
            os.environ['PILOT_NOTE_BUTTONS'] = 'L R A Y'
            check(actions.note_orders()[0] == ('L', 'R', 'Y', 'X', 'A'), 'an order that is not the five buttons is ignored')
        finally:
            os.environ.pop('PILOT_SONG_PITCHES', None)
            os.environ.pop('PILOT_NOTE_BUTTONS', None)
    os.environ['PILOT_SONG_PITCHES'] = '/nonexistent/none.json'
    try:
        check(actions.song_table() == {} and actions.note_orders()[0] == ('L', 'R', 'Y', 'X', 'A'), 'no private data: no songs, the hint-bar order first')
    finally:
        os.environ.pop('PILOT_SONG_PITCHES', None)
    # the song that moves the time of day is named by a local setting, like the arrival flag: `_time_song` of the song file, or PILOT_TIME_SONG
    with tempfile.TemporaryDirectory() as d:
        f = Path(d, 'sp.json')
        f.write_text(json.dumps({'_time_song': 'song-a', 'song-a': '1 3 5 2 4 1'}))
        os.environ['PILOT_SONG_PITCHES'] = str(f)
        os.environ.pop('PILOT_TIME_SONG', None)
        try:
            check(actions.time_song() == 'song-a', 'time_song: the name the song file gives')
            os.environ['PILOT_TIME_SONG'] = 'song-b'
            check(actions.time_song() == 'song-b', 'PILOT_TIME_SONG names it first')
            os.environ.pop('PILOT_TIME_SONG')
            f.write_text(json.dumps({'song-a': '1 3 5 2 4 1'}))
            check(actions.time_song() is None, 'a song file that names no time song: none')
            f.write_text(json.dumps({'_time_song': 7}))
            check(actions.time_song() is None, 'a name that is not a string: none')
        finally:
            os.environ.pop('PILOT_SONG_PITCHES', None)
            os.environ.pop('PILOT_TIME_SONG', None)
    os.environ['PILOT_SONG_PITCHES'] = '/nonexistent/none.json'
    try:
        check(actions.time_song() is None, 'no private data: no time song')
    finally:
        os.environ.pop('PILOT_SONG_PITCHES', None)
    # the local files agree: the table's pitches under the confirmed button order give exactly the notes of songs.json, for every song both hold (by structure only: no song is named here)
    sp, sj = HERE / 'chapters' / 'song_pitches.json', HERE / 'songs.json'
    if sp.is_file() and sj.is_file():
        book = json.loads(sj.read_text())
        order = actions.note_orders()[0]
        check(order == ('L', 'R', 'A', 'Y', 'X'), f'the button order believed first is the one the song file confirms: {order}')
        notes = {**book['inferred'], **book['proven']}
        both = [n for n in notes if actions.song_table().get(n)]
        bad = {n: (actions.song_buttons(n, order), notes[n].split()) for n in both if actions.song_buttons(n, order) != notes[n].split()}
        check(both and not bad, f'the pitches table gives the songs.json notes for every song both hold ({len(both)} songs; {bad})')


# ---- obstacles

def obstacle_checks():
    near, after = [-9.0, 1.0], [-10.2, 1.1]
    jump = plan_result('needs-jump', near, after, 'jump', [link('jump', [-9.0, 100.1, 1.0], [-10.2, 100.0, 1.1], -0.05, 1.2)])
    got = actions.obstacle_candidates('A', state(), jump, jump['steps'])
    check(labels(got) == ['jump-on-way'] and got[0].lines[0] == 'run -9.0 1.0 radius 1' and got[0].lines[-1].startswith('jump -10.20 1.10 radius 0.6 y 100.00 hold 800')
          and 'lead' not in got[0].lines[-1], f'a 1.2 m gap: the walk to the edge, then one jump with no run-up, a landing radius of half the gap (hold 3: radius 1.2 on a 1.2 m gap called a 1.1 m hop on the near side landed) ({got[0].lines})')
    wide = plan_result('needs-jump', near, after, 'jump', [link('jump', [-9.0, 100.1, 1.0], [-10.2, 100.0, 1.1], 0.0, 2.6)])
    line = actions.obstacle_candidates('A', state(), wide, wide['steps'])[0].lines[-1]
    check('lead 3' in line and 'hold 1200' in line, f'a 2.6 m gap wants a run-up and a longer hold ({line})')
    check('radius 1.2 ' in line, f'a wide gap keeps the usual landing radius ({line})')
    ledge = plan_result('needs-climb', [-11.9, -5.6], [-12.4, -5.8], 'ledge-up', [link('ledge-up', [-11.9, 100.1, -5.6], [-12.4, 102.5, -5.8], 2.47, 0.6)])
    got = actions.obstacle_candidates('A', state(), ledge, ledge['steps'])
    check(labels(got) == ['ledge-on-way'] and 'y 102.50' in got[0].lines[-1] and 'hold 1800' in got[0].lines[-1], f'a ledge: a jump held on ({got[0].lines[-1]})')
    ivy = plan_result('needs-climb', [-45.0, 3.2], [-44.0, 6.7], 'climb-up', [link('climb-up', [-45.0, 102.5, 3.2], [-44.0, 105.0, 6.7], 2.4, 0.0, 'Ivy_Test')])
    check(labels(actions.obstacle_candidates('A', state(), ivy, ivy['steps'])) == ['climb-on-way'] and
          actions.obstacle_candidates('A', state(), ivy, ivy['steps'])[0].lines[-1] == 'climb up timeout 14', 'an ivy: climb up after the walk to its foot')
    down = plan_result('needs-climb', [1.0, 2.0], [1.0, 3.0], 'climb-down', [link('climb-down', [1.0, 100.0, 2.0], [1.0, 90.0, 3.0], -10.0, 0.0)])
    check(labels(actions.obstacle_candidates('A', state(), down, down['steps'])) == ['climb-down-on-way'], 'a climb down has its own candidate')
    drop = plan_result('needs-drop', [1.0, 2.0], [4.0, 2.0], 'drop', [link('drop', [1.0, 100.0, 2.0], [4.0, 92.0, 2.0], -8.0, 0.0)])
    check(labels(actions.obstacle_candidates('A', state(), drop, drop['steps'])) == ['drop-on-way'], 'a drop: walk off the edge')
    door = plan_result('needs-door', [1.0, 2.0], [2.0, 2.0], None, [])
    door['edge'] = None
    check(labels(actions.obstacle_candidates('A', state(), door, door['steps'])) == ['open-door-on-way'], 'a door: push, wait for Open, press A')
    crawl = plan_result('needs-crawl', [1.0, 2.0], [4.0, 2.0], 'crawl', [link('crawl', [1.0, 100.0, 2.0], [4.0, 100.0, 2.0], 0.0, 3.0, 'Hole_Test')])
    check(labels(actions.obstacle_candidates('A', state(), crawl, crawl['steps'])) == ['crawl-on-way'], 'a crawl hole: in, A at the Crawl prompt, through')
    check(actions.obstacle_candidates('A', state(), {'ok': False, 'why': 'off-mesh', 'near': [1, 2]}, []) == [] and
          actions.obstacle_candidates('A', state(), {'ok': False, 'why': 'needs-jump', 'near': None, 'after': None}, []) == [],
          'a plan that fails for another reason, or with no place, gives no obstacle candidate')
    check(actions.blocking_link({'near': [-9.0, 1.0], 'needed': [dict(link('ledge-up', [5, 100, 5], [5, 102, 5]), allowed=True), jump['needed'][0]]}) == jump['needed'][0],
          'the blocking link is the first one not allowed, at the plan\'s near point')

    # through interact.candidates and nav: the obstacle's candidate comes right after the walk there
    chest = Target('far', 5.0, 0.0, y=100.0, kind='reach', radius=1.2)
    g = Goal('cross', [chest])
    cands = interact.candidates('Test_Area', g, chest, state(pos=[0.0, 100.0, 0.0]), {}, lambda *a, **k: jump)
    check(labels(cands)[:2] == ['go', 'jump-on-way'], f'cross: the walk, then the jump the plan ends at ({labels(cands)})')
    mem = {}
    interact.candidates('Test_Area', g, chest, state(pos=[0.0, 100.0, 0.0]), mem, lambda *a, **k: {'ok': True, 'steps': ['run 5 0 radius 1'], 'length': 5.0})
    check('obstacles' not in mem, 'a plan that works leaves no obstacle behind')


# ---- the conditions

def cond_checks():
    here = Target('spot', 10.0, 0.0, y=5.0, kind='reach', radius=1.0)
    g = Goal('cross', [here])
    c = g.cond
    check(not c.met_state(state(pos=[0.0, 5.0, 0.0])) and not c.met_state(state(pos=[10.0, 0.0, 0.0])) and c.met_state(state(pos=[10.2, 5.4, 0.3])),
          'cross: met by Link\'s place and height (a place under the target is not it)')
    check(not c.met_state(state(pos=[10.0, 5.0, 0.0], loading=1)), 'cross: not while a load runs')

    d = Goal('dive', [Target('pond', 0.0, 0.0)])
    d.cond.observe(state())
    d.cond.note({'kind': 'dive', 'outcome': 'done', 'result': 'dived', 'changes': {}, 'detail': ''}, state(pos=[1.0, 0.0, 1.0]))
    check(d.cond.met_state(state()), 'dive: a dived result near the spot')
    d2 = Goal('dive', [Target('pond', 0.0, 0.0)], rupees=5)
    d2.cond.observe(state(rupees=0))
    check(not d2.cond.met_state(state(rupees=3)) and d2.cond.met_state(state(rupees=5)), 'dive: or the rupees named')

    b = Goal('buy', [Target('shelf', 0.0, 0.0)], price=40)
    def seen(cond, **kw):   # (the pilot's order: observe each state line, then ask)
        cond.observe(state(**kw))
        return cond.met_state(state(**kw))
    check(not seen(b.cond, rupees=60) and not seen(b.cond, rupees=30), 'buy: not met while the rupees fell by less than the price')
    check(seen(b.cond, rupees=20) and not seen(Goal('buy', [Target('shelf', 0.0, 0.0)], price=40).cond, rupees=21), 'buy: 60 -> 20 is the price of 40')

    u = Goal('use_item', [Target('mark', 5.0, 0.0)], count_flag='Pouch.Bomb.Stock', drop=1)
    u.cond.observe(state(flags={'Pouch.Bomb.Stock': 10}))
    check(not u.cond.met_state(state(flags={'Pouch.Bomb.Stock': 10})) and u.cond.met_state(state(flags={'Pouch.Bomb.Stock': 9})) and 'Pouch.Bomb.Stock' in u.cond.watch,
          'use_item: the count flag fell by one; the flag is watched')
    u2 = Goal('use_item', [Target('mark', 5.0, 0.0)])
    u2.cond.note({'kind': 'item', 'outcome': 'done', 'result': 'used', 'changes': {}, 'detail': ''}, state())
    check(u2.cond.met_state(state()), 'use_item with no count: a used result')

    s = Goal('strafe', [Target('e', 5.0, 0.0)], count=2)
    for r in ('strafed', 'circled'):
        s.cond.note({'kind': 'strafe', 'outcome': 'done', 'result': r, 'changes': {}, 'detail': ''}, state())
    check(s.cond.met_state(state()), 'strafe: two strafes or circles')

    w = Goal('warp_song', [Target('here', 0.0, 0.0)], song='x', to='Other_Area')
    w.cond.observe(state(area='Test_Area'))
    check(not w.cond.met_state(state(area='Test_Area')) and not w.cond.met_state(state(area='Other_Area', loading=1)) and w.cond.met_state(state(area='Other_Area')),
          'warp_song: the map is the one the song warps to, once the load is over')
    with tempfile.TemporaryDirectory() as dd:
        Path(dd, 'sp.json').write_text(json.dumps({'_arrive_flag': 'Test.Arrived'}))
        os.environ['PILOT_SONG_PITCHES'] = str(Path(dd, 'sp.json'))
        try:
            w2 = Goal('warp_song', [Target('here', 0.0, 0.0)], song='x')
            check(actions.arrive_flag() == 'Test.Arrived' and 'Test.Arrived' in w2.cond.watch and w2.cond.met_state(state(flags={'Test.Arrived': 1}))
                  and not w2.cond.met_state(state(flags={'Test.Arrived': 0})), 'warp_song without a map: the arrival flag the private file names, watched')
        finally:
            del os.environ['PILOT_SONG_PITCHES']


    r = Goal('ride', [Target('far', 50.0, 0.0)])
    check(not r.cond.met_state(state()), 'ride: nothing yet')
    r.cond.note({'kind': 'ride', 'outcome': 'done', 'result': 'ridden', 'changes': {}, 'detail': ''}, state())
    check(r.cond.met_state(state()), 'ride: a ridden result')

    pb = Goal('push_block', [Target('block', 3.0, 0.0)])
    pb.cond.note({'kind': 'block', 'outcome': 'done', 'result': 'pushed', 'changes': {}, 'detail': ''}, state(pos=[2.0, 0.0, 0.0]))
    check(pb.cond.met_state(state()), 'push_block: a pushed result near the block')
    far = Goal('push_block', [Target('block', 300.0, 0.0)])
    far.cond.note({'kind': 'block', 'outcome': 'done', 'result': 'pushed', 'changes': {}, 'detail': ''}, state(pos=[2.0, 0.0, 0.0]))
    check(not far.cond.met_state(state()), 'push_block: not one far from the block')
    check(all(len(Goal(k, [Target('t', 0.0, 0.0)]).cond.text) > 20 for k in ('cross', 'dive', 'push_block', 'buy', 'use_item', 'strafe', 'warp_song', 'ride', 'read_sign')),
          'every kind states what it is met by')
    fl = Goal('cross', [here], flag='Gate_Open=1')
    check(fl.cond.met_state(state(pos=[0.0, 0.0, 0.0], flags={'Gate_Open': 1})) and 'Gate_Open' in fl.cond.watch, 'a goal that names a flag is met by it too')


# ---- candidates

def candidate_checks():
    with WithWorld():
        far = Target('far', 20.0, 0.0, y=0.0, kind='reach', radius=1.2)
        c = interact.candidates('Test_Area', Goal('cross', [far]), far, state(pos=[0.0, 0.0, 0.0]), {}, None)
        check(labels(c)[0] == 'go' and 'jump-gap' not in labels(c) and 'swim-across' not in labels(c), f'cross, far away: go, no jump yet, no swim yet ({labels(c)})')
        c = interact.candidates('Test_Area', Goal('cross', [far]), far, state(pos=[0.0, 0.0, 0.0]), {'history': [('go', 'stuck', 0.0, None)]}, None)
        check('swim-across' in labels(c), 'cross: after a walk that ended stuck, the swim is offered (water is not on the map)')
        near = Target('near', 4.0, 0.0, y=0.0, kind='reach', radius=1.2)
        c = interact.candidates('Test_Area', Goal('cross', [near]), near, state(pos=[0.0, 0.0, 0.0]), {}, None)
        check('jump-gap' in labels(c) and 'jump-run-up' in labels(c) and c[labels(c).index('jump-gap')].lines[0].startswith('jump 4.00 0.00 radius 1.2 y 0.00'),
              f'cross, four metres from the target: a jump toward it, with a run-up ({labels(c)})')
        up = Target('up', 2.0, 0.0, y=2.0, kind='reach', radius=1.2)
        c = interact.candidates('Test_Area', Goal('cross', [up]), up, state(pos=[0.0, 0.0, 0.0]), {}, None)
        check('ledge-up' in labels(c) and 'climb-here' in labels(c) and 'jump-gap' not in labels(c), f'cross, 2 m above: the ledge and the climb ({labels(c)})')
        down = Target('down', 2.0, 0.0, y=-8.0, kind='reach', radius=1.2)
        check('climb-down' in labels(interact.candidates('Test_Area', Goal('cross', [down]), down, state(pos=[0.0, 0.0, 0.0]), {}, None)), 'cross, far below: a climb down')
        swim = Goal('cross', [far], how='swim')
        check('swim-across' in labels(interact.candidates('Test_Area', swim, far, state(), {}, None)) and 'jump-gap' not in labels(interact.candidates('Test_Area', swim, near, state(), {}, None)),
              'how = swim offers the swim and no jump')

        pond = Target('pond', 10.0, 0.0, kind='reach', radius=1.0)
        c = interact.candidates('Test_Area', Goal('dive', [pond]), pond, state(), {}, None)
        check(labels(c)[0] == 'swim-to' and 'dive' in labels(c) and 'dive-long' in labels(c), f'dive: swim to the spot, then dive ({labels(c)})')
        c = interact.candidates('Test_Area', Goal('dive', [pond]), pond, state(pos=[10.0, 0.0, 0.2]), {}, None)
        check('swim-to' not in labels(c) and labels(c)[0] == 'dive', 'dive: at the spot, dive first')

        block = Target('block', 5.0, 0.0, kind='reach', radius=1.0)
        c = interact.candidates('Test_Area', Goal('push_block', [block], direction='pull'), block, state(pos=[0.0, 0.0, 0.0]), {}, None)
        check('go-near' in labels(c) and 'block-push' not in labels(c), 'push_block: go to it before grabbing')
        c = interact.candidates('Test_Area', Goal('push_block', [block], direction='pull'), block, state(pos=[4.0, 0.0, 0.0], facing=90.0), {}, None)
        check('block-pull' in labels(c) and labels(c).index('block-pull') < labels(c).index('block-push') and 'face-block' not in labels(c),
              f'push_block, direction pull: pull first ({labels(c)})')

        shelf = Target('shelf', 2.0, 0.0, kind='talk', radius=1.0)
        poor = interact.candidates('Test_Area', Goal('buy', [shelf], price=40), shelf, state(pos=[1.5, 0.0, 0.0], facing=90.0, rupees=10, prompt='Buy'), {}, None)
        check('buy' not in labels(poor) and 'buy-no-first' not in labels(poor) and 'next-target' in labels(poor), f'buy with too few rupees: no buying, the way out ({labels(poor)})')
        rich = interact.candidates('Test_Area', Goal('buy', [shelf], price=40), shelf, state(pos=[1.5, 0.0, 0.0], facing=90.0, rupees=60, prompt='Buy'), {}, None)
        check('buy' in labels(rich) and rich[labels(rich).index('buy')].lines == ['buy timeout 60'], f'buy with the rupees and a prompt: buy ({labels(rich)})')
        silent = interact.candidates('Test_Area', Goal('buy', [shelf], price=40), shelf, state(pos=[1.5, 0.0, 0.0], facing=90.0, rupees=60), {}, None)
        check('buy' not in labels(silent) and 'talk-keeper' in labels(silent) and 'step-in' in labels(silent), 'buy with no prompt: talk to the keeper, step up to the item')

        mark = Target('mark', 8.0, 0.0, kind='reach', radius=1.0)
        c = interact.candidates('Test_Area', Goal('use_item', [mark], button='ZR', hold=150), mark, state(pos=[0.0, 0.0, 0.0]), {}, None)
        check(labels(c)[:4] == ['use-item', 'use-item-lock', 'use-item-aim', 'ztarget'] and c[0].lines == ['use ZR at 8.00 0.00 hold 150'] and c[2].lines == ['use ZR at 8.00 0.00 lock hold 700'],
              f'use_item: use, lock and use, hold to aim ({[x.lines for x in c[:3]]})')
        e = Target('baba', 4.0, 0.0, kind='fight', radius=1.0)
        c = interact.candidates('Test_Area', Goal('strafe', [e]), e, state(pos=[0.0, 0.0, 0.0], facing=0.0), {}, None)
        check({'ztarget', 'strafe-left', 'strafe-right', 'guard', 'roll-away'} <= set(labels(c)) and [x.lines for x in c if x.label == 'strafe-left'] == [['strafe left 1300']], f'strafe ({labels(c)})')

        os.environ['PILOT_SONG_PITCHES'] = '/nonexistent/none.json'
        try:
            c = interact.candidates('Test_Area', Goal('warp_song', [Target('here', 0.0, 0.0, radius=1000.0)], song='song-a'), Target('here', 0.0, 0.0, radius=1000.0), state(), {}, None)
            check('song-warp' not in labels(c) and 'ocarina-out' in labels(c), 'warp_song with no song data offers no song')
        finally:
            del os.environ['PILOT_SONG_PITCHES']
        with song_file(SONGS):
            t = Target('here', 0.0, 0.0, radius=1000.0)
            c = interact.candidates('Test_Area', Goal('warp_song', [t], song='song-a'), t, state(), {}, None)
            got = {x.label: x.lines for x in c}
            check(got['song-warp'][0] == 'ocarina R X L A Y X' and got['song-warp-alt'][0] == 'ocarina R Y L X A Y' and got['song-warp'][1] == 'wait 4',
                  f'warp_song: the song by the believed order, then by the other ({got.get("song-warp")}, {got.get("song-warp-alt")})')
            c2 = interact.candidates('Test_Area', Goal('warp_song', [t], song='song-a'), t, state(), {'history': [('song-warp', 'played', 0, None)]}, None)
            check({x.label: x.lines for x in c2}['song-warp'][0] == 'ocarina R Y L X A Y', 'after one miss the other order is the first candidate')
            h = Target('horse', 40.0, 0.0, kind='reach', radius=2.0)
            c = interact.candidates('Test_Area', Goal('ride', [h], song='song-b', fast=6.5), h, state(), {}, None)
            got = {x.label: x.lines for x in c}
            check(got['call-horse'][0] == 'ocarina X A Y L R X' and got['ride-to'][0].startswith('ride 40.00 0.00 radius 2 fast 6.5 timeout') and 'mount' not in got,
                  f'ride: call her, ride to the target; mount only at a prompt ({got})')
            check('mount' in labels(interact.candidates('Test_Area', Goal('ride', [h], song='song-b'), h, state(prompt='Mount'), {}, None)), 'ride: mount at a prompt')
        sign = Target('sign', 3.0, 0.0, kind='talk', radius=1.5)
        c = interact.candidates('Test_Area', Goal('read_sign', [sign]), sign, state(pos=[2.0, 0.0, 0.0], facing=90.0, prompt='Check'), {}, None)
        check('read-sign' in labels(c) and labels(c).index('read-sign') == 0, f'read_sign at its Check prompt ({labels(c)})')

        for kind in ('cross', 'dive', 'push_block', 'buy', 'use_item', 'strafe', 'warp_song', 'ride', 'read_sign'):
            g = Goal(kind, [Target('t', 4.0, 1.0, radius=1.0)], count=2, price=10, song='x')
            sizes = []
            for st in (state(), state(pos=[3.5, 0.0, 1.0], prompt='Check', rupees=50), state(pos=[40.0, 3.0, 20.0])):
                got = interact.candidates('Test_Area', g, g.targets[0], interact.with_near('Test_Area', st), {'history': [('go', 'stuck', 0.0, None)]}, None)
                sizes.append(len(got))
                check(len(set(labels(got))) == len(got) and len(got) <= 12 and 'next-target' in labels(got) and 'give-up-goal' in labels(got), f'{kind}: distinct, at most 12, the way out')
            check(min(sizes) >= 3, f'{kind}: always a choice ({sizes})')


# ---- the rules against small worlds

def play(goal, sim, plan=None, limit=40):
    """The pilot's loop with the rules decider; `sim.apply(cand)` answers each candidate with (result word, step events)."""
    decider = deciders.Rules()
    mem, tried, chosen = {}, [], []
    goal.status = 'open'
    ti = 0
    for _ in range(limit):
        st = sim.state()
        goal.cond.observe(st)
        if goal.cond.met_state(st):
            return 'met', chosen
        while ti < len(goal.targets) and goal.targets[ti].status != 'open':
            ti += 1
        if ti >= len(goal.targets) or goal.status == 'failed':
            return 'failed', chosen
        target = goal.targets[ti]
        mem['last'] = target is goal.targets[-1]
        st = interact.with_near('Test_Area', st)
        cands = interact.candidates('Test_Area', goal, target, st, mem, plan)
        label = decider.choose(TI.ctx_of(goal, target, st, mem, cands, tried)).label
        assert label in labels(cands), f'{label} is not offered: {labels(cands)}'
        chosen.append(label)
        h = interact.history(mem)
        if label in ('next-target', 'give-up-goal'):
            ok = bool(h) and h[-1][1] in ('reached', 'done', 'met', 'landed', 'dived', 'pushed', 'bought', 'used', 'talked', 'ridden')
            if label == 'give-up-goal':
                goal.status = 'failed'
            else:
                target.status = 'done' if ok else 'failed'
            h.append((label, 'done', 0.0, None))
            continue
        cand = next(c for c in cands if c.label == label)
        result, steps = sim.apply(cand, target)
        h.append((label, result, 0.0, None))
        tried.append({'step': label, 'result': result})
        inter = interact.interaction_of(label, steps)
        if inter:
            mem.setdefault('interactions', []).append(inter)
        goal.cond.note(inter, sim.state())
    return 'budget', chosen


class GapSim(Sim):
    """A gap at x = 5 (1.2 m wide, from 4.4 to 5.6) on the way to (8, 0): the plan says needs-jump until Link is across. A standing jump from the edge
    falls short the first time (`hard`: only a run-up lands)."""
    def __init__(self, hard=False, **kw):
        super().__init__(**kw)
        self.hard, self.jumps, self.across = hard, 0, False

    def state(self):
        s = super().state()
        s['pos'][1] = 0.0
        return s

    def plan(self, area, a, b, **kw):
        if self.across or a[0] > 5.6:
            return {'ok': True, 'steps': [f'run {b[0]} {b[1]} radius 1'], 'length': abs(b[0] - a[0])}
        return plan_result('needs-jump', [4.4, 0.0], [5.6, 0.0], 'jump', [link('jump', [4.4, 0.0, 0.0], [5.6, 0.0, 0.0], 0.0, 1.2)], steps=['run 4.4 0.0 radius 1'])

    def apply(self, cand, target):
        self.walks(cand)
        jumps = [l for l in cand.lines if l.startswith('jump')]
        if jumps:
            self.jumps += 1
            if self.hard and 'lead' not in jumps[0] and self.jumps < 2:
                return 'short', [step('jump', 'short')]
            self.across, self.pos = True, [5.8, 0.0]
            return 'landed', [step('jump', 'landed')]
        if cand.label in ('go', 'side-left', 'side-right', 'back-off'):
            if not self.across and cand.lines and nums(cand.lines[-1])[0] > 5.0:
                self.pos = [4.4, 0.0]
                return 'stuck', [step('run', 'stuck')]
            return 'reached', [step('walk', 'reached')]
        return 'done', [step('wait', 'done')]


class ShopSim(Sim):
    def __init__(self, rupees=100, **kw):
        super().__init__(**kw)
        self.rupees = rupees

    def prompt_now(self):
        return 'Buy' if math.hypot(self.pos[0] - 2.0, self.pos[1]) < 2.0 else 'Empty'

    def apply(self, cand, target):
        self.walks(cand)
        if cand.label == 'buy':
            self.rupees -= 40
            return 'bought', [step('buy', 'bought', changes={'rupees': [self.rupees + 40, self.rupees]})]
        return 'reached', [step('walk', 'reached')]


class WaterSim(Sim):
    def apply(self, cand, target):
        self.walks(cand)
        if cand.label.startswith('swim'):
            return 'swam', [step('swim', 'swam')]
        if cand.label.startswith('dive'):
            return 'dived', [step('dive', 'dived', changes={})]
        return 'reached', [step('walk', 'reached')]


class SongSim(Sim):
    """A warp song that works only with the second note order."""
    def apply(self, cand, target):
        if cand.label in ('song-warp', 'song-warp-alt'):
            if cand.lines[0].split()[1:] == ['R', 'Y', 'L', 'X', 'A', 'Y']:   # (the second note order: pitches 2 4 1 5 3 4 as R Y L X A Y)
                self.area = 'Warp_Area'
            return 'played', [step('ocarina', 'played')]
        return 'done', [step('wait', 'done')]


def policy_checks():
    with WithWorld():
        t = Target('across', 8.0, 0.0, y=0.0, kind='reach', radius=1.5)
        for hard in (False, True):
            sim = GapSim(hard=hard)
            outcome, chosen = play(Goal('cross', [t]), sim, plan=sim.plan)
            check(outcome == 'met' and 'jump-on-way' in chosen and len(chosen) <= 8, f'rules cross a gap (hard={hard}): {outcome} in {len(chosen)} decisions ({chosen})')
            if hard:
                check(sim.jumps == 2, f'a jump that fell short is tried again ({sim.jumps})')
            t = Target('across', 8.0, 0.0, y=0.0, kind='reach', radius=1.5)
        # the older kinds meet the same obstacle: a chest beyond the gap is reached by the jump the plan names (the rules, no model)
        class ChestGap(GapSim):
            def prompt_now(self):
                return 'Open' if self.across and math.hypot(self.pos[0] - 7.0, self.pos[1]) <= 1.5 and not getattr(self, 'opened', False) else 'Empty'

            def apply(self, cand, target):
                if cand.label in ('open-chest', 'open-chest-force') and self.prompt_now() == 'Open':
                    self.opened, self.rupees = True, 20
                    return 'opened', [step('chest', 'opened', changes={'rupees': [0, 20]})]
                return super().apply(cand, target)
        sim = ChestGap()
        chest = Target('chest', 7.0, 0.0, y=0.0, kind='chest', radius=1.2, front=(6.2, 0.0))
        outcome, chosen = play(Goal('open_chest', [chest]), sim, plan=sim.plan)
        check(outcome == 'met' and 'jump-on-way' in chosen and 'open-chest' in chosen and len(chosen) <= 8, f'rules open a chest beyond a gap (jump, then the chest): {outcome} ({chosen})')

        sim = ShopSim()
        shelf = Target('shelf', 2.0, 0.0, kind='talk', radius=1.2)
        outcome, chosen = play(Goal('buy', [shelf], price=40), sim)
        check(outcome == 'met' and 'buy' in chosen and sim.rupees == 60, f'rules buy an item: {outcome} ({chosen}), rupees {sim.rupees}')
        sim = ShopSim(rupees=10)
        outcome, chosen = play(Goal('buy', [Target('shelf', 2.0, 0.0, kind='talk', radius=1.2)], price=40), sim)
        check(outcome == 'failed' and 'buy' not in chosen, f'rules leave a shelf they cannot pay for: {outcome} ({chosen})')
        sim = WaterSim()
        outcome, chosen = play(Goal('dive', [Target('pond', 6.0, 0.0, kind='reach', radius=1.0)]), sim)
        check(outcome == 'met' and chosen.count('dive') + chosen.count('dive-long') == 1, f'rules swim and dive: {outcome} ({chosen})')

        class StrafeSim(Sim):
            def apply(self, cand, target):
                self.walks(cand)
                if cand.label.startswith('strafe'):
                    return 'strafed', [step('strafe', 'strafed')]
                return 'targeted' if cand.label == 'ztarget' else 'reached', [step('ztarget', 'targeted')] if cand.label == 'ztarget' else [step('walk', 'reached')]
        outcome, chosen = play(Goal('strafe', [Target('e', 4.0, 0.0, kind='fight', radius=1.0)], count=2), StrafeSim())
        check(outcome == 'met' and chosen.count('strafe-left') + chosen.count('strafe-right') == 2 and chosen.index('ztarget') < chosen.index('strafe-left'),
              f'rules lock on, then strafe twice: {outcome} ({chosen})')
        with song_file(SONGS):
            sim = SongSim()
            g = Goal('warp_song', [Target('here', 0.0, 0.0, radius=1000.0)], song='song-a', to='Warp_Area')
            outcome, chosen = play(g, sim)
            check(outcome == 'met' and chosen[0] == 'song-warp', f'rules play a warp song: {outcome} ({chosen})')
            none = SongSim()
            none.apply = lambda cand, target: ('played', [step('ocarina', 'played')]) if cand.label.startswith('song') else ('done', [step('wait', 'done')])
            outcome, chosen = play(Goal('warp_song', [Target('here', 0.0, 0.0, radius=1000.0)], song='song-a', to='Warp_Area'), none)
            check(outcome == 'failed' and sum(c.startswith('song-warp') for c in chosen) <= 4, f'a song that never warps is tried at most four times: {outcome} ({chosen})')


def label_checks():
    res = [interact.interaction_of('jump-on-way', [step('walk', 'reached'), step('jump', 'landed')]),
           interact.interaction_of('buy', [step('buy', 'bought', changes={'rupees': [60, 20]})]),
           interact.interaction_of('dive', [step('dive', 'none')]),
           interact.interaction_of('block-push', [step('block', 'pushed', changes={'along': 1.2})]),
           interact.interaction_of('strafe-left', [step('strafe', 'circled')])]
    check([r['outcome'] for r in res] == ['done', 'done', 'none', 'done', 'done'] and res[0]['kind'] == 'cross' and res[3]['kind'] == 'block',
          f"the result words of the new steps are read ({[(r['kind'], r['outcome'], r['result']) for r in res]})")
    check(interact.interaction_of('climb-up', [step('climb', 'done')])['kind'] == 'climb', 'the old climb-up label keeps its kind')
    check(set(interact.KIND_NOTES) == set(interact.GOAL_KINDS) and len(interact.GOAL_KINDS) == 17, f'every kind has its paragraph ({len(interact.GOAL_KINDS)} kinds)')


# ---- every candidate line is a step hsap understands

def grammar_checks():
    import test_hsap
    lines = set()
    with WithWorld(), song_file(SONGS):
        mark = Target('m', 6.0, 2.0, y=0.0, kind='reach', radius=1.2)
        for kind, kw in (('cross', {}), ('cross', {'how': 'swim'}), ('dive', {}), ('push_block', {'direction': 'pull'}), ('buy', {'price': 20}), ('use_item', {'button': 'ZR', 'hold': 150}),
                         ('strafe', {}), ('ride', {'song': 'song-b', 'fast': 6.5}), ('read_sign', {}), ('warp_song', {'song': 'song-a'})):
            g = Goal(kind, [mark], **kw)
            for st in (state(pos=[1.0, 0.0, 1.0]), state(pos=[5.0, 0.0, 2.0], prompt='Check', rupees=50, facing=90.0), state(pos=[5.5, 1.0, 2.0], prompt='Mount')):
                for c in interact.candidates('Test_Area', g, mark, interact.with_near('Test_Area', st), {}, None):
                    lines.update(c.lines)
        for r in (plan_result('needs-jump', [4.4, 0.0], [5.6, 0.0], 'jump', [link('jump', [4.4, 0.0, 0.0], [5.6, 0.0, 0.0], 0.0, 2.6)]),
                  plan_result('needs-climb', [4.4, 0.0], [5.6, 0.0], 'ledge-up', [link('ledge-up', [4.4, 0.0, 0.0], [5.6, 2.0, 0.0], 2.0)]),
                  plan_result('needs-climb', [4.4, 0.0], [5.6, 0.0], 'climb-down', [link('climb-down', [4.4, 0.0, 0.0], [5.6, -9.0, 0.0], -9.0)]),
                  plan_result('needs-drop', [4.4, 0.0], [5.6, 0.0], 'drop', [link('drop', [4.4, 0.0, 0.0], [5.6, -6.0, 0.0], -6.0)])):
            for c in actions.obstacle_candidates('Test_Area', state(), r, r['steps']):
                lines.update(c.lines)
    bounded = []
    for l in sorted(lines):
        w = l.split()
        if 'timeout' in w:
            w[w.index('timeout') + 1] = '3'
        bounded.append(' '.join(w))
    with test_hsap.WorldSimulation(boot_events=0, follow=False, things=[test_hsap.CHEST]) as sim:
        sim.executor(sorted(set(bounded)) + ['end']).run()
        bad = [e['src'] + ': ' + e['why'] for e in sim.events() if e['ev'] == 'bad']
        check(not bad, f'all {len(set(bounded))} distinct candidate lines of the new kinds are steps hsap understands ({bad[:4]})')


def run():
    song_checks()
    obstacle_checks()
    cond_checks()
    candidate_checks()
    label_checks()
    policy_checks()
    grammar_checks()
    print(f'test_actions: {TI.CHECKS[0]} checks (shared with test_interact), {len(TI.FAILS)} failed')
    return not TI.FAILS


def main():
    ok = run()
    print('test_actions: all passed' if ok else 'test_actions: FAILED')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
