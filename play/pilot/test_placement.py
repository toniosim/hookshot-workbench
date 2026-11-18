#!/usr/bin/env python3
"""placement.py against a FAKE hsdebug (a module file written here, loaded by path as the real one is) and a fake channel, and `pilot.py run`
end to end against test_pilot's fake game with a `[place]` table: the spec's checks, the loader, a placement that works / is refused / raises,
the state the pilot decides from (after the placement, not the stale one before it), a failed placement ending the session as such, and the
generated roam segments that carry a `[place]`. Made-up names; no game, no GPU, no network.   python3 -I -B test_placement.py
"""
import argparse
import json
import os
import random
import shutil
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hunt  # noqa: E402
import pilot  # noqa: E402
import placement  # noqa: E402
import test_pilot as tp  # noqa: E402

FAKE_HSDEBUG = r'''
import json, os
CALLS = []
ATTACHES = []
class Debug:
    def __init__(self, run, mode):
        self.run, self.mode = run, mode
    def setup(self, to=None, age=None, hour=None, **kw):
        CALLS.append({'run': self.run, 'to': to, 'age': age, 'hour': hour})
        if self.mode == 'raise':
            raise RuntimeError('the game went away')
        steps = [{'ok': True, 'action': 'teleport', 'effect': 'verified', 'map': to}]
        if self.mode == 'time-fails':
            steps += [{'ok': False, 'action': 'time', 'effect': 'unavailable', 'error': 'unavailable', 'message': 'no game info'}]
        if self.mode == 'refuse':
            steps = [{'ok': False, 'action': 'teleport', 'effect': 'not_applied', 'error': 'refused', 'message': 'destination has no map for the adult'}]
        return {'ok': all(s['ok'] for s in steps), 'effect': 'verified' if self.mode == 'ok' else 'partial', 'steps': steps,
                'state': {'map': to if self.mode in ('ok', 'time-fails') else 'Elsewhere', 'age': 'child', 'pos': [1, 2, 3], 'life': 16, 'rupees': 5, 'event': False}, 'seconds': 0.1}
    def close(self):
        CALLS.append('closed')
def attach(run=None, **kw):
    ATTACHES.append(kw)
    if os.environ.get('FAKE_MODE') == 'attach-fails':
        raise RuntimeError('no game answers on the socket')
    return Debug(run, os.environ.get('FAKE_MODE', 'ok'))
'''

FAILS = []
CHECKS = [0]


def check(cond, what):
    CHECKS[0] += 1
    if not cond:
        FAILS.append(what)
        print('FAIL', what, flush=True)


class Ch:
    """a channel that answers like hsap's: the placement's `wait` step ends, then a state line"""

    def __init__(self, with_state=True):
        self.sent, self.with_state = [], with_state
        self.script = []

    def send(self, lines):
        self.sent += lines
        return [len(self.sent)]

    def wait(self, pred, timeout, alive=lambda: True):
        for e in ({'ev': 'step', 'in': len(self.sent), 'src': 'wait 0.5', 'result': 'done'}, {'ev': 'state', 'why': 'wait', 'area': 'Dungeon_X', 'pos': [1, 2, 3]}):
            if pred(e):
                if e['ev'] == 'state' and not self.with_state:
                    return None
                return e
        return None


def spec_checks(tmp):
    ok = placement.check_spec({'to': 'Dungeon_X', 'age': 'child', 'hour': 22})
    check(ok['hour'] == 22 and placement.check_spec({'to': 3}) == {'to': 3} and placement.check_spec({'to': 'A'})['to'] == 'A', 'check_spec: a name or an index, age and hour optional')
    for bad, why in (({'to': ''}, 'to'), ({}, 'to'), ({'to': 'A', 'age': 'old'}, 'age'), ({'to': 'A', 'hour': 24}, 'hour'), ({'to': 'A', 'hour': True}, 'hour'),
                     ({'to': 'A', 'q': 1}, 'unknown keys'), ({'to': 'A', 'x': 1}, 'come together'), ('A', 'table'), ({'to': True}, 'to')):
        try:
            placement.check_spec(bad)
            check(False, f'check_spec refuses {bad!r}')
        except ValueError as e:
            check(why in str(e), f'check_spec refuses {bad!r} ({e})')
    # a segment with a place table
    seg = tmp / 'place-seg.toml'
    seg.write_text(tp.SEGMENT + '\n[place]\nto = "Dungeon_X"\nage = "adult"\nhour = 23\n')
    s = pilot.Segment(seg)
    check(s.place == {'to': 'Dungeon_X', 'age': 'adult', 'hour': 23}, f'Segment: the [place] table is read ({s.place})')
    seg2 = tmp / 'place-seg2.toml'
    seg2.write_text('name = "x"\narea = "A"\nplace = { to = "A", bogus = 1 }\n[[goal]]\nname = "g"\nflag = "F=1"\nkind = "reach"\ntargets = [{name = "t", at = [0.0, 0.0]}]\n')
    try:
        pilot.Segment(seg2)
        check(False, 'Segment refuses an unknown place key')
    except ValueError as e:
        check('unknown keys' in str(e), 'Segment refuses an unknown place key')
    plain = tmp / 'plain.toml'
    plain.write_text(tp.SEGMENT)
    check(pilot.Segment(plain).place is None, 'Segment: no [place], none')


def apply_checks(tmp):
    mod_path = tmp / 'hsdebug_fake.py'
    mod_path.write_text(FAKE_HSDEBUG)
    mod = placement.load_hsdebug(mod_path)
    check(hasattr(mod, 'attach'), 'load_hsdebug: by path')
    os.environ['FAKE_MODE'] = 'ok'
    r = placement.apply({'to': 'Dungeon_X', 'age': None, 'hour': 22}, tmp / 'run', hsdebug=mod)
    check(r['ok'] and r['map'] == 'Dungeon_X' and r['steps'] == [['teleport', 'verified']] and r['state']['map'] == 'Dungeon_X', f'apply: a placement that worked ({r})')
    check(mod.CALLS[-2]['to'] == 'Dungeon_X' and mod.CALLS[-2]['hour'] == 22 and mod.CALLS[-1] == 'closed', 'apply: setup got to and hour, the attachment was closed')
    os.environ['FAKE_MODE'] = 'time-fails'
    r = placement.apply({'to': 'Dungeon_X', 'hour': 22}, tmp / 'run', hsdebug=mod)
    check(r['ok'] and r['partial'] == ['time'] and 'hour was not set' in r['note'] and 'error' not in r, f'apply: placed but the hour not set is a partial placement, the roam goes on ({r})')
    info_file = tmp / 'game-info.json'
    info_file.write_text('{}')
    os.environ['HSDEBUG_INFO'] = str(info_file)
    placement.apply({'to': 'Dungeon_X', 'hour': 22}, tmp / 'run', hsdebug=mod)
    check(mod.ATTACHES[-1].get('info') == str(info_file), 'apply: the game-info file of $HSDEBUG_INFO goes to hsdebug (the hour needs it)')
    os.environ['HSDEBUG_INFO'] = str(tmp / 'missing-info.json')
    placement.apply({'to': 'Dungeon_X'}, tmp / 'run', hsdebug=mod)
    check(mod.ATTACHES[-1].get('info') is None, 'apply: a game-info path that is not a file is not passed')
    del os.environ['HSDEBUG_INFO']
    os.environ['FAKE_MODE'] = 'refuse'
    r = placement.apply({'to': 'Dungeon_X', 'age': 'adult'}, tmp / 'run', hsdebug=mod)
    check(not r['ok'] and 'no map for the adult' in r['error'], f'apply: a refused teleport is a result with the game\'s words ({r.get("error")})')
    os.environ['FAKE_MODE'] = 'raise'
    r = placement.apply({'to': 'Dungeon_X'}, tmp / 'run', hsdebug=mod)
    check(not r['ok'] and 'RuntimeError' in r['error'] and mod.CALLS[-1] == 'closed', 'apply: an exception is a result, and the attachment is still closed')
    os.environ['FAKE_MODE'] = 'attach-fails'
    r = placement.apply({'to': 'Dungeon_X'}, tmp / 'run', hsdebug=mod)
    check(not r['ok'] and 'no game answers' in r['error'], 'apply: no game on the socket is a result')
    os.environ['HSDEBUG_PATH'] = str(tmp / 'nowhere.py')
    saved_paths, placement.HSDEBUG_PATHS = placement.HSDEBUG_PATHS, ()   # (a tree that has the real hsdebug.py beside hsap.py still finds none here)
    try:
        placement.load_hsdebug(tmp / 'also-nowhere.py')
        check(False, 'load_hsdebug without a file raises')
    except placement.PlacementError as e:
        check('hsdebug.py not found' in str(e), 'load_hsdebug: no file: PlacementError naming the places looked at')
    finally:
        placement.HSDEBUG_PATHS = saved_paths
    os.environ['HSDEBUG_PATH'] = str(mod_path)
    check(hasattr(placement.load_hsdebug(), 'attach'), 'load_hsdebug: $HSDEBUG_PATH')
    del os.environ['HSDEBUG_PATH']
    os.environ.pop('FAKE_MODE', None)
    # start_placed
    ch = Ch()
    st, placed = placement.start_placed({'to': 'Dungeon_X'}, ch, tmp / 'run', lambda: True, apply_fn=lambda spec, run: {'ok': True, 'map': 'Dungeon_X', 'seconds': 1.0})
    check(st and st['area'] == 'Dungeon_X' and placed['ok'] and placed['area_after'] == 'Dungeon_X' and 'note' not in placed and ch.sent == ['wait 0.5'],
          f'start_placed: a state from after the placement, forced by a wait step ({st}, {placed})')
    st, placed = placement.start_placed({'to': 'Dungeon_X'}, Ch(), tmp / 'run', lambda: True, apply_fn=lambda spec, run: {'ok': True, 'map': 'Elsewhere'})
    check(st and 'note' in placed and 'Elsewhere' in placed['note'], 'start_placed: a state that does not show the placement\'s map is noted, not hidden')
    ch = Ch()
    st, placed = placement.start_placed({'to': 'Dungeon_X'}, ch, tmp / 'run', lambda: True, apply_fn=lambda spec, run: {'ok': False, 'error': 'refused'})
    check(st is None and not placed['ok'] and ch.sent == [], 'start_placed: a failed placement sends nothing and gives no state')
    st, placed = placement.start_placed({'to': 'Dungeon_X'}, Ch(with_state=False), tmp / 'run', lambda: True, apply_fn=lambda spec, run: {'ok': True, 'map': 'Dungeon_X'})
    check(st is None and not placed['ok'] and 'no state line' in placed['error'], 'start_placed: no state after it is a failure')


def run_checks(tmp):
    """pilot.py run (attach mode, the game side is test_pilot's fake) with a [place] table: the placement is made after `gameplay`, before the
    first decision; the summary carries it; a failed placement ends the run as `placement failed` and still ends the game side"""
    calls = []
    saved = placement.apply

    def good(spec, run):
        calls.append((dict(spec), str(run)))
        return {'ok': True, 'map': 'Fake_Area', 'seconds': 0.1, 'steps': [['teleport', 'verified']]}

    def bad(spec, run):
        calls.append((dict(spec), str(run)))
        return {'ok': False, 'error': 'refused: destination has no map for the adult', 'seconds': 0.1}
    for name, fn, outcome in (('good', good, 'played'), ('bad', bad, 'placement failed'), ('fallback', bad, 'played')):
        seg = tmp / f'run-{name}.toml'
        seg.write_text(tp.SEGMENT + '\n[place]\nto = "Dungeon_X"\nhour = 5\n')
        tag = f'place-run-{name}-{time.time_ns()}'
        live = tmp / f'live-{name}'
        pilot.Channel(live)
        game = tp.FakeGame(live)
        game.start()
        placement.apply = fn
        if name == 'fallback':
            os.environ['PILOT_PLACE_FALLBACK'] = 'the library save stands in the place already'
        try:
            args = argparse.Namespace(segment=str(seg), decider='rules', replay=None, planner=False, copy=str(tmp / 'copy'), tag=tag, attach=str(live),
                                      save=None, wall=60, max_decisions=None, follow=[], end_hold=0.0, shots=0, api_base=None, allowance_usd=None,
                                      allowance_since='2026-01-01', matches=None)
            code = pilot.cmd_run(args)
        finally:
            placement.apply = saved
            os.environ.pop('PILOT_PLACE_FALLBACK', None)
        run_dir = pilot.HERE / 'runs' / tag
        summary = json.loads((run_dir / 'summary.json').read_text())
        steps = (run_dir / 'steps.txt').read_text().splitlines()
        events = [json.loads(x) for x in (live / 'out.jsonl').read_text().splitlines()]
        check(summary['place']['ok'] == (name == 'good') and (summary['outcome'] == outcome or (name != 'bad' and summary['decisions'])), f'pilot run {name}: outcome {summary["outcome"]}, place {summary.get("place")}')
        check(calls[-1][0] == {'to': 'Dungeon_X', 'hour': 5} and calls[-1][1].endswith(f'copy/runs/{tag}'), f'pilot run {name}: apply got the spec and the game\'s run folder ({calls[-1]})')
        check(events[-1]['ev'] == 'done', f'pilot run {name}: the game side was ended either way')
        notes = (run_dir / 'panel-notes.txt').read_text()
        check(('placement ok' in notes) == (name == 'good') and ('placement FAILED: refused' in notes) == (name != 'good') and ('fallback: the library save' in notes) == (name == 'fallback'),
              f'pilot run {name}: panel-notes.txt says what happened ({notes!r})')
        if name != 'bad':
            check(steps[0].startswith('watch') or steps[0] == 'wait 0.5', f'pilot run {name}: the wait step that forces a fresh state comes before the pilot\'s steps')
            check('wait 0.5' in steps and steps.index('wait 0.5') < max(i for i, x in enumerate(steps) if x.split()[0] in ('walk', 'run', 'press')), f'pilot run {name}: the pilot\'s own steps come after it')
        else:
            check('wait 0.5' not in steps and not any(x.split()[0] in ('walk', 'run', 'press') for x in steps), 'pilot run bad: no step was sent after a failed placement')
        check(name != 'bad' or code != 0, f'pilot run {name}: exit code {code} (a failed placement without a fallback is not a pass)')
        shutil.rmtree(run_dir, ignore_errors=True)


def roam_checks(tmp):
    """the generator: a roam segment that carries its [place]; the pilot's Segment reads what is generated"""
    toml = hunt.roam_segment_toml('gen', 'Dungeon_X', 'a-save', [(1, 2, 3)], 150, 2, place={'to': 'Dungeon_X', 'age': 'child', 'hour': 22})
    p = tmp / 'gen-place.toml'
    p.write_text(toml)
    s = pilot.Segment(p)
    check(s.place == {'to': 'Dungeon_X', 'age': 'child', 'hour': 22} and s.area == 'Dungeon_X' and len(s.goals[0].targets) == 1, f'roam_segment_toml: a placed roam reads back ({s.place})')
    p2 = tmp / 'gen-plain.toml'
    p2.write_text(hunt.roam_segment_toml('gen', 'Dungeon_X', 'a-save', [(1, 2, 3)], 150, 2))
    check(pilot.Segment(p2).place is None, 'roam_segment_toml: no place, none')


def plan_checks(tmp):
    """the generator makes placed sessions from a places file and a world model's start; a plan with a place is validated; the packet and the
    replay carry the placement"""
    import test_hunt as th

    lib = tmp / 'pl-lib'
    lib.mkdir()
    (lib / 'catalogue.json').write_text(json.dumps({'save-a': {'decoded': {'slots': [{'area': 'Yard', 'pos': [1, 10, 2]}]}}}))
    places = tmp / 'places.json'
    places.write_text(json.dumps([{'to': 'Dungeon_X', 'age': 'child', 'hour': 22, 'area': 'Dungeon_X'}, {'to': 'Town_Y', 'age': 'adult', 'save': 'save-a'}]))

    class FakeRoam:
        def start(self, area):
            return [5, 10, 6] if area in ('Dungeon_X', 'Town_Y') else None

        def targets(self, area, start, rng, k, **kw):
            assert start == [5, 10, 6]
            return [(round(rng.uniform(-50, 50), 2), round(rng.uniform(-50, 50), 2), 10.0) for _ in range(k)]

    class A:
        pass

    def args(out, **kw):
        a = A()
        a.out, a.name, a.seed, a.solo, a.pairs, a.library = out, 'pl-night', 3, 1, 0, str(lib)
        a.copies, a.pilot, a.chapters, a.chapter_share, a.pair_case, a.pair_hold = '/x/copy-a,/x/copy-b', '/x/pilot.py', None, 0.5, [], 700.0
        a.areas, a.targets, a.wall, a.hold_seconds, a.config, a.budget_usd = 'Yard', 5, 150, 2000.0, None, 1.5
        a.bounds = a.baseline = a.registry = a.coopplay = None
        a.places, a.placed = str(places), 3
        for k, v in kw.items():
            setattr(a, k, v)
        return a

    class Y(FakeRoam):
        def targets(self, area, start, rng, k, **kw):
            return super().targets(area, start, rng, k) if area != 'Yard' else [(1, 1, 1)] * k
    path = hunt.make_plan(args(tmp / 'pl1'), Y())
    d = json.loads(path.read_text())
    placed = [x for x in d['sessions'] if x['name'].startswith('placed-')]
    check(len(placed) == 3 and all(x['place']['to'] in ('Dungeon_X', 'Town_Y') for x in placed) and len(d['sessions']) == 4, f'make_plan: three placed roams besides the ordinary ({[x["name"] for x in d["sessions"]]})')
    seg = pilot.Segment(tmp / 'pl1' / placed[0]['segment'])
    check(seg.place == placed[0]['place'] and seg.area == placed[0]['place']['to'], 'make_plan: the placed roam\'s segment carries the same [place] and its area')
    check(all(x['save'] in ('save-a',) for x in placed), 'make_plan: a places entry\'s save, else the first save of the allowed areas')
    d5 = json.loads(hunt.make_plan(args(tmp / 'pl5', placed=2), Y()).read_text())
    check(sorted(x['place']['to'] for x in d5['sessions'] if x['name'].startswith('placed-')) == ['Dungeon_X', 'Town_Y'], 'make_plan: two placed roams from two places are the two places (no draw twice before every one was used)')
    d6 = json.loads(hunt.make_plan(args(tmp / 'pl6', session_env=['HSDEBUG_INFO=/x/info.json']), Y()).read_text())
    check(all('HSDEBUG_INFO=/x/info.json' in x['env'] for x in d6['sessions'] if x['name'].startswith('placed-')), 'make_plan: --session-env is in the env of every placed session')
    d2 = json.loads(hunt.make_plan(args(tmp / 'pl2'), Y()).read_text())
    check(json.dumps(d).replace('pl1', 'x') == json.dumps(d2).replace('pl2', 'x'), 'make_plan: the same seed gives the same placed plan')
    plan = hunt.load_plan(path)
    check(all(s_['place'] == x['place'] for s_, x in zip(plan['sessions'][1:], placed)), 'load_plan: the place of a session is kept')
    for bad, what in ((lambda dd: dd['sessions'][1].update(place={'to': 'X', 'hour': 99}), 'hour'), (lambda dd: dd['sessions'][1].update(place={'to': 'X', 'zzz': 1}), 'unknown keys')):
        dd = json.loads(path.read_text())
        bad(dd)
        pp = tmp / 'pl1' / 'bad.json'
        pp.write_text(json.dumps(dd))
        try:
            hunt.load_plan(pp)
            check(False, f'load_plan refuses a bad place ({what})')
        except hunt.PlanError as e:
            check(what in str(e), f'load_plan refuses a bad place ({e})')
    for kw, what in (({'places': None}, '--placed needs --places'),):
        try:
            hunt.make_plan(args(tmp / 'pl3', **kw), Y())
            check(False, what)
        except hunt.PlanError as e:
            check(what in str(e), f'make_plan: {what}')

    class NoStart(Y):
        def start(self, area):
            return None
    try:
        hunt.make_plan(args(tmp / 'pl4'), NoStart())
        check(False, 'make_plan: no start in the world model is refused')
    except hunt.PlanError as e:
        check('no free-roam targets for the placed area' in str(e), 'make_plan: an area the world model has no start for is refused')
    # WorldRoam.start reads areas.json
    wd = tmp / 'world'
    wd.mkdir()
    (wd / 'areas.json').write_text(json.dumps({'Dungeon_X': {'starts': {'(default)': {'pos': [1, 2, 3]}, 'EntrancePos': {'pos': [4, 5, 6]}}},
                                               'Town_Y': {'starts': {'EntrancePos': {'pos': [4, 5, 6]}, 'Other': {'pos': [7, 8, 9]}}}, 'Odd': {'starts': {'Z': {'pos': [9, 9, 9]}}}, 'Bare': {}}))
    wr = hunt.WorldRoam.__new__(hunt.WorldRoam)
    wr.dir = wd
    check(wr.start('Dungeon_X') == [1, 2, 3] and wr.start('Town_Y') == [4, 5, 6] and wr.start('Odd') == [9, 9, 9] and wr.start('Bare') is None and wr.start('Nowhere') is None,
          'WorldRoam.start: the default, else the entrance, else the first named start; none for an area without')

    # WorldRoam.targets: the attempts are a parameter (a big area needs more than 400 to find 60 checkpoints)
    class StubPlan:
        calls = 0

        @staticmethod
        def plan(area, a, b, from_y=0, to_y=0, radius=2.5):
            StubPlan.calls += 1
            return {'ok': StubPlan.calls % 3 == 0, 'length': 30.0}
    wr2 = hunt.WorldRoam.__new__(hunt.WorldRoam)
    wr2.plan = StubPlan
    wr2.centroids = lambda area: [(float(i % 20) * 4, 10.0, float(i // 20) * 4) for i in range(400)]
    got = wr2.targets('A', [10, 10, 10], random.Random(1), 60)
    check(len(got) == 60, f'WorldRoam.targets: 60 checkpoints when a third of the tries succeed ({len(got)})')
    StubPlan.calls = 0
    check(len(wr2.targets('A', [10, 10, 10], random.Random(1), 60, max_tries=30)) < 60, 'WorldRoam.targets: max_tries bounds the search')
    # a dead end does not end the search: it goes on from an earlier checkpoint
    class IslandPlan:
        @staticmethod
        def plan(area, a, b, from_y=0, to_y=0, radius=2.5):
            return {'ok': True, 'length': 30.0}
    wr3 = hunt.WorldRoam.__new__(hunt.WorldRoam)
    wr3.plan = IslandPlan
    wr3.centroids = lambda area: [(i * 30, 10, 0) for i in range(8)] + [(1000, 10, 1000)]   # a line of eight points 30 m apart and one far island
    got3 = wr3.targets('A', [0, 10, 0], random.Random(2), 40, max_tries=400)
    check(len(got3) == 40, f'WorldRoam.targets: a chain that reaches a dead end goes on from an earlier checkpoint ({len(got3)})')
    # a start far from every mesh point (a start named for a cutscene, off the mesh) begins at the nearest mesh point
    wr4 = hunt.WorldRoam.__new__(hunt.WorldRoam)
    wr4.plan = IslandPlan
    wr4.centroids = lambda area: [(i * 30, 10, 0) for i in range(8)]
    got4 = wr4.targets('A', [500, 10, 500], random.Random(3), 10, max_tries=300)
    check(len(got4) == 10, f'WorldRoam.targets: a start off the mesh begins at the nearest mesh point ({len(got4)})')
    class OffMeshPlan:
        @staticmethod
        def plan(area, a, b, from_y=0, to_y=0, radius=2.5):
            return {'ok': a in [(float(i) * 30.0, 0.0) for i in range(8)], 'length': 30.0}   # refuses any start that is not exactly a mesh point
    wr4.plan = OffMeshPlan
    check(len(wr4.targets('A', [31, 10, 2], random.Random(3), 10, max_tries=400)) == 10, 'WorldRoam.targets: a start the planner would call off-mesh is snapped to a mesh point first')
    # the packet and the replay
    env = th.setup(tmp / 'plr', hold=200)
    (tmp / 'plr' / 'pilotdir' / 'hsap.py').write_text(r'''#!/usr/bin/env python3
import json, sys, time
from pathlib import Path
a = sys.argv
copy, tag, wall = Path(a[1]), a[2], a[3]
live = Path(a[a.index('--live') + 1])
game = copy / 'runs' / tag
(game / 'shots').mkdir(parents=True)
T0 = 3000.0
(live / 'out.jsonl').write_text(json.dumps({'ev': 'gameplay', 't': 0.0, 'frame': 100, 'area': 'Yard'}) + '\\n')
seen = []
end = time.time() + 20
while time.time() < end:
    lines = (live / 'steps.txt').read_text().splitlines()
    seen.append((time.time(), len(lines)))
    if 'end' in lines:
        break
    time.sleep(0.05)
rows = [{'t': T0 + i / 10, 'frame': 100 + 6 * i, 'map': 'Yard', 'pos': [0, 10, 0], 'event': 0, 'loading': 0, 'life': 12, 'rupees': 5, 'prompt': 'Empty', 'music': 'BGM_Yard', 'flags': {}, 'changed': {}} for i in range(100)]
(live / 'state.jsonl').write_text(''.join(json.dumps(r) + '\\n' for r in rows))
with open(live / 'out.jsonl', 'a') as f:
    f.write(json.dumps({'ev': 'done', 't': 1.0}) + '\\n')
(live / 'seen.json').write_text(json.dumps(seen))
(game / '@LOG@').write_text('[hos] start\\n')
(game / 'exit.txt').write_text('143')
'''.replace('@LOG@', th.tb.LOG))
    side, session = th.tb_session(tmp / 'plr', env)
    session['place'] = {'to': 'Dungeon_X', 'hour': 22}
    f = hunt.bughunt.Finding(kind='hang', sub='resumed', severity='error', side='solo', text='a 40 s hole', t=th.tb.T0 + 10.0, frame=700, game_s=10.0, map='Yard', pos=[0, 10, 0], evidence={})
    f.key = hunt.bughunt.place_key('hang', 'resumed', 'Yard', f.pos, 16.0)
    packet = hunt.bugpacket.make_packet(tmp / 'plr' / 'packet', f, {'solo': side}, session, None)
    pk = json.loads((packet / 'packet.json').read_text())
    check(pk['replay']['place'] == {'to': 'Dungeon_X', 'hour': 22} and pk['plan']['place'] == {'to': 'Dungeon_X', 'hour': 22}, 'packet: the placement is in the plan and in the replay plan')
    check(hunt.session_from_folder(tmp / 'plr' / 'nowhere').get('place') is None, 'session_from_folder: no summary, no place')
    sf = tmp / 'plr' / 'folder'
    (sf / 'pilot').mkdir(parents=True)
    (sf / 'pilot' / 'summary.json').write_text(json.dumps({'runner': ['x', '--save', '/s/a-save', '--boot', 'continue'], 'humanize': {'seed': 4, 'level': 2},
                                                           'place': {'ok': True, 'to': 'Dungeon_X', 'age': None, 'hour': 22, 'steps': []}}))
    check(hunt.session_from_folder(sf).get('place') == {'to': 'Dungeon_X', 'hour': 22}, 'session_from_folder: the placement of a placed run\'s summary')
    calls = []
    saved = placement.apply

    def fake_apply(spec, run, env=None):
        calls.append((dict(spec), str(run), (live_dir / 'steps.txt').read_text().splitlines()))
        return {'ok': True, 'seconds': 0.1, 'map': 'Dungeon_X'}
    live_dir = packet / 'replay' / 'live'
    placement.apply = fake_apply
    try:
        res = hunt.replay_packet(packet, env['copy'], env['pilot'], hunt.bughunt.Config(hang_s=30.0), None, None, wall=20, out=packet / 'replay')
    finally:
        placement.apply = saved
    steps = (live_dir / 'steps.txt').read_text().splitlines()
    check(len(calls) == 1 and calls[0][0] == {'to': 'Dungeon_X', 'hour': 22} and '/runs/replay-' in calls[0][1], f'replay: placed once, with the packet\'s spec on the replay\'s game run ({calls and calls[0][:2]})')
    check(calls[0][2] == ['watch a'] or all(x.startswith('watch') for x in calls[0][2]), f'replay: at the moment of the placement the live steps held only the watch lines ({calls[0][2]})')
    check(steps[-1] == 'end' and any(x.startswith('walk') for x in steps) and json.loads((live_dir / 'placement.json').read_text())['ok'], f'replay: after it the steps and the end went to the game side ({steps})')
    check(res['verdict'] in ('reproduced', 'not reproduced', 'similar') and res['mode'] == 'steps', 'replay: a verdict from the same detectors')
    # a failed placement releases only the end
    packet2 = hunt.bugpacket.make_packet(tmp / 'plr' / 'packet2', f, {'solo': side}, dict(session, place={'to': 'Nowhere'}), None)
    placement.apply = lambda spec, run, env=None: {'ok': False, 'error': 'refused', 'seconds': 0.1}
    try:
        hunt.replay_packet(packet2, env['copy'], env['pilot'], hunt.bughunt.Config(hang_s=30.0), None, None, wall=20, out=packet2 / 'replay')
    finally:
        placement.apply = saved
    steps2 = (packet2 / 'replay' / 'live' / 'steps.txt').read_text().splitlines()
    check(not any(x.startswith('walk') for x in steps2) and steps2[-1] == 'end', f'replay: a failed placement lets no step through ({steps2})')


def run_in(tmp):
    spec_checks(tmp)
    apply_checks(tmp)
    os.environ['PILOT_TACTICS_DIR'] = str(tmp / 'tactics')   # (pilot.py run writes what it learns there: never into the real library beside the harness)
    try:
        run_checks(tmp)
    finally:
        os.environ.pop('PILOT_TACTICS_DIR', None)
    check((tmp / 'tactics' / 'book.jsonl').is_file(), 'the runs wrote what they learned into the test\'s own tactics folder, not into the harness\'s')
    roam_checks(tmp)
    plan_checks(tmp)


def run():
    with tempfile.TemporaryDirectory(prefix='test-placement-') as t:
        run_in(Path(t))


def main():
    run()
    if FAILS:
        raise SystemExit(f'test_placement: {len(FAILS)} of {CHECKS[0]} checks FAILED')
    print(f'test_placement: all {CHECKS[0]} checks passed')


if __name__ == '__main__':
    main()
