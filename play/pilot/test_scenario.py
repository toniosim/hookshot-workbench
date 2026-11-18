#!/usr/bin/env python3
"""scenario.py on made-up scenarios, maps and evidence: the format's checks, the compile to hsap steps (open_map, fight_loop, repeat, cross, enter,
go_near with and without a planner, roam, the leg to the coordinates and its omission after a warp), the importer (map, age, hour, coordinates when
the text gives them, proposed actions flagged unconfirmed, the reporter's sentences), placement at coordinates through a fake coordinate warp, and the
judging of a played run (spikes inside the windows against outside, crash, visual, distance). No game, no network.   python3 -I -B test_scenario.py"""
import json, os, stat, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bughunt, placement, scenario  # noqa: E402
import hs_names  # noqa: E402  (bughunt put the harness folder on sys.path: the game's own file names)
import test_bughunt as tb  # noqa: E402
FAILS, CHECKS = [], [0]
def check(c, w):
    CHECKS[0] += 1
    if not c:
        FAILS.append(w); print('FAIL', w, flush=True)
CHILD, ADULT = '_Child', '_Adult'   # the age suffix of a destination name, which scenario.py's importer reads
YARD, YARD_ADULT, OLD_TOWN = 'Yard' + CHILD, 'Yard' + ADULT, 'Old_Town' + CHILD   # made-up maps

BASE = {'format': 'ls-scenario/1', 'name': 'sc-a', 'purpose': 'reproduce', 'claim': 'frame spikes when an enemy dies in the Yard at night', 'players': 1,
        'at': {'map': YARD, 'age': 'child', 'hour': 23},
        'action': [{'do': 'fight_loop', 'rounds': 2, 'tag': 'fight'}], 'expect': [{'check': 'spikes', 'during': ['fight'], 'ms': 50.0}]}
def with_(**kw):
    d = json.loads(json.dumps(BASE)); d.update(kw); return d

def format_checks(tmp):
    check(scenario.problems(BASE) == [], f'a good scenario has no problems ({scenario.problems(BASE)})')
    for mut, what in ((lambda d: d.update(format='x'), 'format is'), (lambda d: d.update(purpose='fun'), 'purpose is'), (lambda d: d.pop('claim'), 'claim'),
                      (lambda d: d['at'].pop('map'), 'at.map'), (lambda d: d['at'].update(hour=24), 'at.hour'), (lambda d: d['at'].update(x=1.0), 'x and z come together'),
                      (lambda d: d['action'].append({'do': 'dance'}), 'do is one of'), (lambda d: d['action'].append({'do': 'press', 'button': 'Q'}), 'button is one of'),
                      (lambda d: d['action'].append({'do': 'press', 'button': 'A', 'zz': 1}), 'unknown keys'), (lambda d: d['action'].append({'do': 'repeat', 'n': 2, 'actions': [{'do': 'wait', 's': 'a'}]}), 'actions[0]'),
                      (lambda d: d['expect'].append({'check': 'smell'}), 'check is one of'), (lambda d: d.update(expect=[]), 'what to look for'),
                      (lambda d: d.update(name='a b'), 'name:'), (lambda d: d.update(bogus=1), 'unknown keys'), (lambda d: d.update(action=[]), 'at least one'),
                      (lambda d: d['action'].append({'do': 'cross', 'there': [1.0], 'back': [1.0, 2.0]}), 'there is')):
        d = json.loads(json.dumps(BASE)); mut(d)
        check(any(what in e for e in scenario.problems(d)), f'problems: {what!r} ({scenario.problems(d)})')
    fp = tmp / 'pair.toml'; fp.write_text(scenario.dumps(PAIR))
    check(scenario.load(fp)['save_b'] == 'b-save' and scenario.load(fp)['watch'] == ['Chest_Flag', 'Key_Count'] and scenario.load(fp)['action'][0]['who'] == 'A', 'dumps then load round-trips a pair scenario (save, watch, who)')
    f = tmp / 'ok.toml'; f.write_text(scenario.dumps(BASE))
    check(scenario.load(f)['name'] == 'sc-a' and scenario.load(f)['at']['hour'] == 23, 'dumps then load round-trips a scenario')
    (tmp / 'bad.toml').write_text('format = "ls-scenario/1"\nname = "x"\n')
    try:
        scenario.load(tmp / 'bad.toml'); check(False, 'load refuses a bad file')
    except scenario.ScenarioError as e:
        check('purpose is' in str(e), 'load refuses a bad file with every problem')
    d = with_(action=[{'do': 'open_map', 'cycles': 2, 'confirmed': False}, {'do': 'repeat', 'n': 1, 'actions': [{'do': 'wait', 'confirmed': False}]}])
    check(scenario.unconfirmed(d) == ['action[0] open_map', 'action[1].actions[0] wait'], f'unconfirmed lists proposed actions ({scenario.unconfirmed(d)})')
    check(scenario.place_spec(with_(at={'map': YARD, 'age': 'child', 'hour': 5, 'x': 1.0, 'z': 2.0})) == {'age': 'child', 'hour': 5, 'x': 1.0, 'z': 2.0, 'to': YARD}, 'place_spec: map, age, hour and the coordinates when there are some')

def compile_checks(tmp):
    d = with_(action=[{'do': 'open_map', 'cycles': 2, 'button': 'PLUS', 'tag': 'map'}])
    st = scenario.compile_steps(d)
    check([l for l, _ in st] == ['press PLUS 200', 'wait 1.50', 'press B 200', 'wait 1.50'] * 2 and {t for _, t in st} == {'map'}, f'open_map: press, wait, close, wait, twice ({st})')
    st = scenario.compile_steps(with_(action=[{'do': 'fight_loop', 'rounds': 2, 'swings': 2}]))
    check([l for l, _ in st][:6] == ['ztarget 800', 'swing', 'wait 0.35', 'swing', 'wait 0.35', 'wait 1.20'] and len(st) == 12 and {t for _, t in st} == {'fight_loop'}, 'fight_loop: lock on, swings, a wait, per round; the tag defaults to the action')
    st = scenario.compile_steps(with_(action=[{'do': 'repeat', 'n': 3, 'actions': [{'do': 'press', 'button': 'A', 'ms': 100}, {'do': 'wait', 's': 0.5}]}]))
    check(len(st) == 6 and st[0][0] == 'press A 100', 'repeat: the nested actions n times')
    st = scenario.compile_steps(with_(action=[{'do': 'cross', 'there': [1, 2, 3, 4], 'back': [5, 6], 'cycles': 2}, {'do': 'enter', 'x': 1.0, 'z': 2.0}]))
    check([l for l, _ in st][:2] == ['enter 1.00 2.00 through 3.00 4.00 timeout 40', 'enter 5.00 6.00 timeout 40'] and len(st) == 5, f'cross and enter: the loading-zone legs ({[l for l, _ in st]})')
    st = scenario.compile_steps(with_(action=[{'do': 'note', 'text': 'hello'}, {'do': 'shot'}, {'do': 'rendezvous', 'name': 'r1'}]))
    check([l for l, _ in st] == ['# hello', 'shot', 'rendezvous r1 timeout 240'] and st[0][1] == 'note', 'note, shot, rendezvous')
    # the leg to the coordinates
    d = with_(at={'map': YARD, 'x': 10.0, 'y': 5.0, 'z': -4.0}, action=[{'do': 'wait', 's': 1.0}])
    st = scenario.compile_steps(d)
    check(st[0] == ('walk 10.00 -4.00 radius 2.50 timeout 60', 'goto') and st[1][1] == 'wait', 'the coordinates: a go_near leg (a plain walk without a planner) before the actions, tagged goto')
    check(scenario.compile_steps(d, goto=False)[0][1] == 'wait', 'after a warp the goto leg is left out')
    calls = []
    def plan(area, a, b, from_y=0, to_y=0, radius=2.5):
        calls.append((area, a, b, from_y, to_y))
        return {'ok': True, 'steps': ['run 1.00 2.00 radius 2.5', 'run 10.00 -4.00 radius 2.5']}
    world = {'plan': plan, 'start': lambda area: [100, 7, 200], 'targets': lambda area, start, rng, k, min_m=15.0, max_m=70.0: [(1, 2, 0), (3, 4, 0)][:k]}
    st = scenario.compile_steps(d, world)
    check(st[0] == ('run 1.00 2.00 radius 2.5 timeout 60', 'goto') and calls[0][:3] == (YARD, (100.0, 200.0), (10.0, -4.0)) and calls[0][4] == 5.0, f'with a planner the leg is the planner\'s steps from the map\'s start ({st[:2]}, {calls[:1]})')
    def plan_part(area, a, b, from_y=0, to_y=0, radius=2.5):
        return {'ok': False, 'why': 'needs-door', 'detail': 'a door on the way', 'steps': ['run 1.00 1.00 radius 2.5']}
    st = scenario.compile_steps(d, dict(world, plan=plan_part))
    check([t for _, t in st][:3] == ['goto', 'note', 'goto'] and st[2][0].startswith('walk 10.00 -4.00') and 'needs-door' in st[1][0], f'a plan that stops short says so and steers straight for the rest ({st[:3]})')
    off = {'n': 0}
    def plan_off(area, a, b, from_y=0, to_y=0, radius=2.5):
        off['n'] += 1
        return {'ok': False, 'why': 'off-mesh', 'steps': []} if b == (50.0, 60.0) else {'ok': True, 'steps': ['run 7.00 8.00 radius 2.5']}
    wsnap = dict(world, plan=plan_off, snap=lambda area, x, z: (7.0, 8.0))
    st = scenario.compile_steps(with_(at={'map': YARD, 'x': 50.0, 'z': 60.0}, action=[{'do': 'wait'}]), wsnap)
    check(st[0][0].startswith('run 7.00 8.00') and off['n'] == 2, f'a goal off the mesh is snapped to the nearest walkable point and planned again ({st[:1]}, {off})')
    st = scenario.compile_steps(with_(action=[{'do': 'roam', 'count': 2, 'seed': 3}]), world)
    check(len(st) == 4 and all(t == 'roam' for _, t in st), 'roam: the planner\'s steps to each generated point')
    try:
        scenario.compile_steps(with_(action=[{'do': 'roam', 'count': 2}])); check(False, 'roam without a world is refused')
    except scenario.ScenarioError as e:
        check('world model' in str(e), 'roam without a world model is refused')

TEXT_1213 = """Reported on Discord

### What happened and steps
The reporter loaded a save in the Yard, killed several enemies, changed to night, then killed more enemies (skeletons). Each time an enemy died, repeatable frame spikes occurred.

### Where in the game
Yard, while killing enemies, including skeletons at night.

### How often
Repeatable.
"""
TEXT_809 = """### What happened
Opening the Map Menu and then closing in the Cave freezes and crashes. Position: (12.5, 3, -40.25) facing 90

### Where in the game
Opening the Map Menu and then closing in the Cave as adult Link

### How often
Every time
"""
def importer_checks(tmp):
    dests = [YARD, YARD_ADULT, 'Cave', 'InsideTheOldBarn', OLD_TOWN]
    al = scenario.aliases_of(dests)
    check(al['yard'] == [YARD, YARD_ADULT] and al['cave'] == ['Cave'] and 'old barn' in al and al['old town'] == [OLD_TOWN], f'aliases come from the destination names alone ({sorted(al)})')
    sc = scenario.import_text('Game: Repeatable frame spikes when enemies die in the Yard (GPU X, Linux)', TEXT_1213, dests, ref='https://example.test/issues/1213')
    check(sc['at'].get('map') == YARD and sc['at'].get('hour') == 23 and 'x' not in sc['at'], f'1213: the map of the where-section, night = 23, no coordinates ({sc["at"]})')
    check(any('no coordinates' in n for n in sc['notes']) and any('without an age' in n for n in sc['notes']), 'the notes say there were no coordinates and which age was assumed')
    acts = {a['do']: a for a in sc['action']}
    check('fight_loop' in acts and acts['fight_loop']['confirmed'] is False and 'open_map' not in acts, 'a fight is proposed as an action, flagged unconfirmed')
    check({e['check'] for e in sc['expect']} == {'spikes'} and sc['purpose'] == 'reproduce', 'what to look for follows the words (spikes)')
    check(len(sc['confirm']) >= 2 and any('killed several enemies' in c['text'] for c in sc['confirm']), 'the reporter\'s sentences are listed for a person')
    sc2 = scenario.import_text('Game: Crash in the Cave after opening and closing map', TEXT_809, dests)
    check(sc2['at'] == {'map': 'Cave', 'age': 'adult', 'x': 12.5, 'y': 3.0, 'z': -40.25, 'facing': 90.0}, f'809: map, age, coordinates and facing when the text gives them ({sc2["at"]})')
    check({'crash', 'distance'} <= {e['check'] for e in sc2['expect']} and sc2['action'][0]['do'] == 'open_map' and sc2['action'][0]['confirmed'] is False, '809: a crash check, a distance check, open_map proposed unconfirmed')
    sc3 = scenario.import_text('x', 'coordinates: x: 1.5, y: 2, z: -3 in old town at 22:30', dests)
    check(sc3['at'].get('x') == 1.5 and sc3['at'].get('z') == -3.0 and sc3['at']['map'] == OLD_TOWN and sc3['at']['hour'] == 22, f'labelled coordinates, a clock time, a map with an underscore ({sc3["at"]})')
    sc5 = scenario.import_text('Slowdown in the Yard and corruption in Old Square', '### Where in the game\nOld Square', dests, extra_aliases={'old square': OLD_TOWN})
    check(sc5['at'].get('map') == OLD_TOWN, f'a place players name another way maps through the alias table ({sc5["at"]})')
    sc6 = scenario.import_text('Slowdown', '### Where in the game\nYard (slowdown); Cave (corruption)', dests)
    check(sc6['at']['map'] == YARD and any('also names: cave' in n for n in sc6['notes']), f'two places in the text: one taken, the other said ({sc6["notes"]})')
    sc4 = scenario.import_text('A crash somewhere', 'no map named here', dests)
    check('map' not in sc4['at'] and any('at.map must be written' in n for n in sc4['notes']), 'no map in the text: said, never guessed')
    f = tmp / 'imp.toml'; f.write_text(scenario.dumps(sc2))
    d = scenario.load(f)
    check(d['at']['x'] == 12.5 and scenario.unconfirmed(d) == ['action[0] open_map'], 'an imported draft loads, and its unconfirmed action is listed')
    check(scenario.problems(scenario.import_text('t', 'text', dests)) != [], 'a draft with no map is not a valid scenario until a person fills it in')

class FakeDebug:
    def __init__(self, warp_pos=None, has_warp=True):
        self.calls, self.warp_pos = [], warp_pos
        if not has_warp:
            self.warp = None
    def setup(self, to=None, age=None, hour=None, **kw):
        self.calls.append(('setup', to, age, hour))
        return {'ok': True, 'effect': 'verified', 'steps': [{'ok': True, 'action': 'teleport', 'effect': 'verified'}], 'state': {'map': to, 'pos': [0, 1, 0]}}
    def warp(self, x, y, z, facing=None, to=None, watch=2.0):
        self.calls.append(('warp', x, y, z, facing))
        return {'ok': True, 'action': 'warp', 'effect': 'verified', 'after': {'pos': self.warp_pos or [x, y, z], 'facing': facing}}
    def close(self):
        self.calls.append('closed')
class FakeMod:
    def __init__(self, dbg):
        self.dbg = dbg
    def attach(self, run=None, info=None, **kw):
        return self.dbg

def placement_checks(tmp):
    spec = {'to': YARD, 'age': 'child', 'hour': 5, 'x': 10.0, 'y': 2.0, 'z': -4.0, 'facing': 90.0}
    check(placement.check_spec(spec) == spec, 'check_spec takes coordinates')
    dbg = FakeDebug(warp_pos=[10.5, 2, -4.5])
    r = placement.apply(spec, tmp / 'run', hsdebug=FakeMod(dbg))
    check(r['ok'] and r['warp']['ok'] and r['warp']['pos'] == [10.5, 2, -4.5] and abs(r['warp']['distance_m'] - 0.71) < 0.01 and ('warp', 10, 2, -4, 90.0) in dbg.calls, f'a coordinate warp after the teleport, the position read back and its distance ({r.get("warp")})')
    r = placement.apply(spec, tmp / 'run', hsdebug=FakeMod(FakeDebug(has_warp=False)))
    check(r['ok'] and 'warp' not in r and r['x'] == 10.0, 'without a warp in the debug tools: placed at the map, no warp result (the leg to the point is the runner\'s)')
    class Bad(FakeDebug):
        def warp(self, x, y, z, facing=None, to=None, watch=2.0):
            raise RuntimeError('the position field could not be found')
    r = placement.apply(spec, tmp / 'run', hsdebug=FakeMod(Bad()))
    check(r['ok'] and r['warp']['ok'] is False and 'could not be found' in r['warp']['error'], 'a warp that raises is a failed warp, not a failed placement (the run walks to the point)')
    class NoFacing(FakeDebug):
        def warp(self, x, y, z, to=None, watch=2.0):   # the debug tools' warp today: no facing argument
            return {'ok': True, 'effect': 'verified', 'after': {'pos': [x, y, z]}}
    r = placement.apply(spec, tmp / 'run', hsdebug=FakeMod(NoFacing()))
    check(r['warp']['ok'] and r['warp']['distance_m'] == 0.0, 'a warp without a facing argument is called without one')
    class NotApplied(FakeDebug):
        def warp(self, x, y, z, to=None, watch=2.0):
            return {'ok': False, 'effect': 'not_applied', 'note': 'no `!place` command in this build'}
    r = placement.apply(spec, tmp / 'run', hsdebug=FakeMod(NotApplied()))
    check(r['ok'] and r['warp']['ok'] is False, 'a build without the place command: not applied, the run walks to the point')
    class Part(FakeDebug):
        def warp(self, x, y, z, facing=None, to=None, watch=2.0):
            return {'ok': True, 'effect': 'partial', 'after': {'pos': [x + 3.0, y, z]}}
    r = placement.apply(spec, tmp / 'run', hsdebug=FakeMod(Part()))
    check(r['ok'] and r['warp']['ok'] is False and r['warp']['effect'] == 'partial', 'a partial warp (the game moved him) is not counted as having put him there')
    r = placement.apply({'to': YARD}, tmp / 'run', hsdebug=FakeMod(FakeDebug()))
    check('warp' not in r, 'no coordinates, no warp')
    dbg2 = FakeDebug()
    r = placement.apply({'to': YARD, 'x': 10.0, 'z': -4.0}, tmp / 'run', hsdebug=FakeMod(dbg2))
    check('warp' not in r and not any(c[0] == 'warp' for c in dbg2.calls if isinstance(c, tuple)), 'coordinates without a height: no warp (the run walks to the point)')

def tags_for(d, goto=True):
    return {i + 1: t for i, (_, t) in enumerate(scenario.compile_steps(d, goto=goto))}

def run_folder(tmp, name, gaps, steps, exit_code=143, log='[hos host] vk: device 0: Test GPU 9000, Vulkan 1.4\n'):
    st = tb.steady(60)
    ev = tb.events_for(st, steps=steps)
    return tb.make_side(tmp / name, st, events=ev, log=log, summary=tb.OK_SUMMARY, exit_code=exit_code, present=tb.present_rows(3600, gaps=gaps)), tmp / name

def eval_checks(tmp):
    d = with_(action=[{'do': 'wait', 's': 1.0}, {'do': 'fight_loop', 'rounds': 1, 'swings': 1, 'tag': 'fight'}], expect=[{'check': 'spikes', 'during': ['fight'], 'ms': 50.0, 'min_window_s': 10.0}])
    tg = tags_for(d)
    fight_in = [i for i, t in tg.items() if t == 'fight']
    steps = [tb.step(30.0, 'ztarget 800', 'done', **{'in': fight_in[0]}) | {'secs': 20.0}]
    inwin = {f: 80.0 for f in (1000, 1060, 1120, 1180, 1240)}
    _, run = run_folder(tmp, 'e1', {**inwin, 2400: 90.0}, steps)
    (run / 'pilot' / 'live').mkdir(parents=True, exist_ok=True)
    r = scenario.evaluate(d, run, tags={fight_in[0]: 'fight'})
    c = r['checks'][0]
    check(r['verdict'] == 'reproduced' and c['spikes_in'] == 5 and c['spikes_out'] == 1 and c['per_min_in'] > 10 and r['hardware'] == 'Test GPU 9000', f'spikes: five inside the fight window against one outside is reproduced ({c})')
    even = {f: 80.0 for f in range(300, 3500, 200)}
    _, run = run_folder(tmp, 'e2', even, steps)
    r = scenario.evaluate(d, run, tags={fight_in[0]: 'fight'})
    check(r['verdict'] == 'not reproduced' and r['checks'][0]['spikes_in'] >= 3, f'spikes: the same rate everywhere is not the scenario\'s ({r["checks"][0].get("verdict")}, in {r["checks"][0].get("spikes_in")} out {r["checks"][0].get("spikes_out")})')
    _, run = run_folder(tmp, 'e3', {}, steps)
    r = scenario.evaluate(d, run, tags={fight_in[0]: 'fight'})
    check(r['verdict'] == 'not reproduced' and r['checks'][0]['spikes_in'] == 0 and r['tried_steps_by_tag'] == {'fight': 1}, f'spikes: no spike while it fought: not reproduced, with what was tried ({r["tried_steps_by_tag"]})')
    short = [tb.step(12.0, 'ztarget 800', 'done', **{'in': fight_in[0]}) | {'secs': 3.0}]
    _, run = run_folder(tmp, 'e4', {}, short)
    check(scenario.evaluate(d, run, tags={fight_in[0]: 'fight'})['verdict'] == 'inconclusive', 'spikes: three seconds of fighting say nothing: inconclusive')
    _, run = run_folder(tmp, 'e5', {}, [])
    check(scenario.evaluate(d, run, tags={})['checks'][0]['verdict'] == 'inconclusive', 'spikes: no step of the tag ran: inconclusive')
    dc = with_(action=[{'do': 'wait', 's': 1.0}], expect=[{'check': 'crash'}])
    end_done = [tb.step(58.0, 'end', 'done', **{'in': 2})]
    _, run = run_folder(tmp, 'e6', {}, end_done, exit_code=137)
    r = scenario.evaluate(dc, run, tags={})
    check(r['verdict'] == 'not reproduced' and r['checks'][0]['found'] == 0, f'crash: SIGKILL after the end step was done (the game was slow to stop) is no crash ({r["verdict"]}, {r["checks"][0]})')
    _, run = run_folder(tmp, 'e7', {}, [], exit_code=137)
    check(scenario.evaluate(dc, run, tags={})['verdict'] == 'reproduced', 'crash: SIGKILL with no end step is a crash')
    # the machine's own slow frames are not the scenario's: a pressure record that says the CPU was short while they happened
    root = tmp / 'e1'
    rows = [{'t': tb.T0 + i, 'cpu': int(i * 0.6e6), 'io': 0, 'iof': 0, 'mem': 0, 'memf': 0, 'load1': 30.0} for i in range(0, 61)]
    (root / 'psi.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    r = scenario.evaluate(d, root, tags={fight_in[0]: 'fight'})
    check(r['checks'][0]['spikes_in'] == 0 and r['checks'][0]['spikes_machine'] >= 5 and r['verdict'] == 'not reproduced', f'spikes: slow frames while the machine was short of CPU are counted as the machine\'s ({r["checks"][0]})')
    (root / 'psi.jsonl').unlink()
    # a gate: the steps of its tags must have got where they were meant to
    dgate = with_(action=[{'do': 'go_near', 'x': 1.0, 'z': 1.0, 'tag': 'approach'}, {'do': 'wait'}], expect=[{'check': 'crash'}, {'check': 'reached', 'tags': ['approach']}])
    tgg = tags_for(dgate)
    appr = [i for i, t in tgg.items() if t == 'approach'][0]
    _, run = run_folder(tmp, 'e10', {}, [tb.step(5.0, 'walk 1.00 1.00 radius 2.50 timeout 40', 'stuck', **{'in': appr})])
    r = scenario.evaluate(dgate, run, tags=tgg)
    gg = [c for c in r['checks'] if c['check'] == 'reached'][0]
    check(r['verdict'] == 'inconclusive' and gg['verdict'] == 'not reached' and gg['results'] == ['stuck'], f'a gate that was not reached makes a clean run inconclusive, not "not reproduced" ({r["verdict"]}, {gg})')
    _, run = run_folder(tmp, 'e11', {}, [tb.step(5.0, 'walk 1.00 1.00 radius 2.50 timeout 40', 'reached', **{'in': appr})])
    r = scenario.evaluate(dgate, run, tags=tgg)
    check(r['verdict'] == 'not reproduced' and [c for c in r['checks'] if c['check'] == 'reached'][0]['verdict'] == 'reached', 'a gate that was reached leaves the verdict to the checks')
    _, run = run_folder(tmp, 'e12', {}, [])
    check(scenario.evaluate(dgate, run, tags=tgg)['verdict'] == 'inconclusive', 'a gate whose steps never ran: inconclusive')
    # a gate on one kind of step and one kind of result: the lock-ons of a fight that found something to lock onto (hold 9: 1 of 30 did)
    dfight = with_(action=[{'do': 'fight_loop', 'rounds': 2, 'swings': 1, 'tag': 'fight'}], expect=[{'check': 'crash'}, {'check': 'reached', 'tags': ['fight'], 'src': 'ztarget', 'share': 0.3}])
    tgf = tags_for(dfight)
    fi = sorted(tgf)
    zs = [i for i in fi if True]
    def fight_steps(results):
        return [tb.step(5.0 + k, 'ztarget 800', r, **{'in': fi[0]}) for k, r in enumerate(results)] + [tb.step(20.0, 'swing', 'done', **{'in': fi[0]}) for _ in range(6)]
    _, run = run_folder(tmp, 'e13', {}, fight_steps(['targeted', 'none', 'none', 'none']))
    r = scenario.evaluate(dfight, run, tags=tgf)
    gf = [c for c in r['checks'] if c['check'] == 'reached'][0]
    check(gf['verdict'] == 'not reached' and gf['steps'] == 4 and gf['ok'] == 1 and r['verdict'] == 'inconclusive', f'a fight whose lock-ons mostly found nothing: the gate fails, the run is inconclusive ({gf}, {r["verdict"]})')
    _, run = run_folder(tmp, 'e14', {}, fight_steps(['targeted', 'targeted', 'none', 'none']))
    r = scenario.evaluate(dfight, run, tags=tgf)
    check([c for c in r['checks'] if c['check'] == 'reached'][0]['verdict'] == 'reached' and r['verdict'] == 'not reproduced', 'half the lock-ons found a target: the gate holds and the checks decide')
    check(any('reached' in e for e in scenario.problems(with_(expect=[{'check': 'reached', 'zz': 1}]))) or scenario.problems(with_(expect=[{'check': 'reached', 'zz': 1}])) != [], 'a gate takes only its own keys')
    dc = with_(expect=[{'check': 'crash'}])
    _, run = run_folder(tmp, 'e6', {}, steps, exit_code=143)
    check(scenario.evaluate(dc, run, tags={})['verdict'] == 'not reproduced', 'crash: a clean run is not reproduced')
    side = tb.make_side(tmp / 'e7', tb.steady(20), events=tb.events_for(tb.steady(20)), log='CRASH: boom at 0x1\n', exit_code=139, summary=tb.OK_SUMMARY.replace('crash=0', 'crash=1').replace('exit=143', 'exit=139'))
    check(scenario.evaluate(dc, tmp / 'e7', tags={})['verdict'] == 'reproduced', 'crash: a crash in the run is reproduced')
    # the leg to the coordinates: distance reached
    dg = with_(at={'map': YARD, 'x': 10.0, 'z': -4.0}, action=[{'do': 'wait'}], expect=[{'check': 'distance', 'max_m': 5.0}, {'check': 'crash'}])
    tg = tags_for(dg)
    goto_in = [i for i, t in tg.items() if t == 'goto'][0]
    gstep = [tb.step(5.0, 'walk 10.00 -4.00 radius 2.50 timeout 60', 'reached', **{'in': goto_in}) | {'detail': '1.41 m from the point'}]
    _, run = run_folder(tmp, 'e8', {}, gstep)
    r = scenario.evaluate(dg, run, tags=tg)
    dd = [c for c in r['checks'] if c['check'] == 'distance'][0]
    check(dd['distance_m'] == 1.41 and dd['verdict'] == 'reproduced' and r['goto'] == {'distance_m': 1.41, 'result': 'reached'} and r['verdict'] == 'not reproduced', f'distance: 1.41 m from the reported point; the distance check does not decide the verdict ({r["goto"]}, {r["verdict"]})')
    # visual: no pictures is inconclusive; a black pair is found
    dv = with_(expect=[{'check': 'visual'}])
    _, run = run_folder(tmp, 'e9', {}, [])
    check(scenario.evaluate(dv, run, tags={})['verdict'] == 'inconclusive', 'visual: no pictures: inconclusive')
    class VF:
        kind, sub, severity, text = 'visual', 'corrupt', 'warning', 'the model says corrupt at 0.9 in vk_000100.png'
    (run / 'game' / 'shots').mkdir(parents=True, exist_ok=True)
    (run / 'game' / 'shots' / 'vk_000100.png').write_bytes(tb.vision.write_png(4, 4, bytes([9, 9, 9] * 16)))
    r = scenario.evaluate(dv, run, tags={}, visual_findings=[VF()])
    check(r['verdict'] == 'reproduced' and r['checks'][0]['found'] == 1, 'visual: a corrupt finding of the model is reproduced')
    r = scenario.evaluate(dv, run, tags={}, visual_findings=[])
    check(r['verdict'] == 'not reproduced' and r['checks'][0]['pictures'] == 1, 'visual: pictures looked at and nothing found: not reproduced, with the count')

PAIR = {'format': 'ls-scenario/1', 'name': 'pair-t', 'purpose': 'regression', 'claim': 'both players take the same chest at once', 'players': 2, 'save': 'a-save', 'save_b': 'b-save',
        'watch': ['Chest_Flag', 'Key_Count'], 'link_ms': 150, 'hold_s': 300, 'at': {'map': 'Dungeon_X', 'from': 'save'},
        'action': [{'do': 'walk', 'x': 1.0, 'z': 2.0, 'who': 'A', 'tag': 'approach'}, {'do': 'walk', 'x': 3.0, 'z': 4.0, 'who': 'B', 'tag': 'approach'},
                   {'do': 'rendezvous', 'name': 'chest-1'}, {'do': 'press', 'button': 'A', 'who': 'A', 'tag': 'chest'}, {'do': 'wait', 's': 1.5, 'who': 'B'},
                   {'do': 'teleport', 'index': 3, 'who': 'B', 'tag': 'warp'}, {'do': 'stick', 'dir': 'up', 'ms': 500}],
        'expect': [{'check': 'key', 'key': 'give:double:abc'}, {'check': 'counter', 'flag': 'Key_Count', 'max': 1}, {'check': 'clean', 'ignore': ['stall']},
                   {'check': 'reached', 'tags': ['approach']}, {'check': 'crash'}]}

def pair_checks(tmp):
    check(scenario.problems(PAIR) == [], f'a good pair scenario ({scenario.problems(PAIR)})')
    for mut, what in ((lambda d: d.pop('save'), 'names the save'), (lambda d: d['action'].append({'do': 'wait', 'who': 'C'}), 'who is A, B or both'),
                      (lambda d: d['at'].update({'from': 'elsewhere'}), 'at.from'), (lambda d: d['action'].append({'do': 'stick', 'dir': 'sideways'}), 'dir is'),
                      (lambda d: d['expect'].append({'check': 'key'}), 'key is required')):
        d = json.loads(json.dumps(PAIR)); mut(d)
        check(any(what in e for e in scenario.problems(d)), f'pair problems: {what!r} ({scenario.problems(d)})')
    solo = with_(action=[{'do': 'wait', 'who': 'A'}])
    check(any('players = 2' in e for e in scenario.problems(solo)), 'who A/B is for a pair')
    a = [l for l, _ in scenario.compile_steps(PAIR, side='A')]
    b = [l for l, _ in scenario.compile_steps(PAIR, side='B')]
    check(a == ['walk 1.00 2.00 radius 1.50 timeout 20', 'rendezvous chest-1 timeout 240', 'press A 200', 'stick up 500'], f'player A\'s own steps ({a})')
    check(b == ['walk 3.00 4.00 radius 1.50 timeout 20', 'rendezvous chest-1 timeout 240', 'wait 1.50', 'cheat 1003', 'stick up 500'], f'player B\'s own steps: the debug teleport by list index ({b})')
    st = [l for l, _ in scenario.compile_steps(with_(action=[{'do': 'chest'}, {'do': 'chest', 'timeout': 30.0}, {'do': 'interact'}, {'do': 'pickup', 'x': 1.5, 'z': 2.5, 'radius': 0.8, 'press': True}, {'do': 'pickup', 'x': 1.5, 'z': 2.5}]))]
    check(st == ['chest', 'chest timeout 30', 'interact', 'pickup 1.50 2.50 radius 0.80 timeout 20 press', 'pickup 1.50 2.50 radius 1.00 timeout 20'], f'chest, interact and pickup compile to hsap\'s own verbs ({st})')
    check(len(scenario.compile_steps(PAIR)) == 7 and scenario.place_spec(PAIR) is None, 'without a side every step; a scenario that starts from the save has no placement')
    # the files for the co-op runner
    out = tmp / 'pairout'
    r = scenario.pair_files(PAIR, out, tmp / 'frozen', '/x/copy-a', '/x/copy-b', tmp / 'rv', info='/x/info.json', wall=280)
    check(Path(r['case']).is_file() and (out / 'pair-t-A.txt').read_text().splitlines() == a and (out / 'pair-t-B.txt').read_text().splitlines() == b and (tmp / 'rv').is_dir(), 'pair_files: a case, a segment and a route for each player, the rendezvous folder')
    import pilot
    sg = pilot.Segment(out / 'pair-t-B.toml')
    check(sg.scripted and sg.prefix == 'pair-t-B.txt' and sg.save == 'b-save' and sg.place is None and sg.watch == ['Chest_Flag', 'Key_Count'] and sg.goals == [], 'the segment is scripted: the route, the player\'s own save, the watch flags, no goals')
    text = Path(r['case']).read_text()
    check('delay_ms = 150' in text and 'HSAP_SIDE=B' in text and f'HSAP_RENDEZVOUS={tmp / "rv"}' in text and 'HSDEBUG_INFO=/x/info.json' in text and 'coop_keys = 2' in text and 'hold_seconds = 300' in text, 'the case: B\'s link delay, the rendezvous env, the info file, the room rules, the hold')
    check(text.count('RX_VK_VRAM_MB=5500') == 2, 'the case: each game\'s texture budget is 5500 MB (two games with the default 11 GB each fill the card and freeze together)')
    r_nv = scenario.pair_files(PAIR, tmp / 'pairout3', tmp / 'frozen', '/x/a', '/x/b', tmp / 'rv4', vram_mb=0)
    check('RX_VK_VRAM_MB' not in Path(r_nv['case']).read_text(), 'vram_mb = 0 leaves the budget to the game')
    cp = HERE.parent.parent / 'coop-play'
    if (cp / 'cpcase.py').is_file():
        sys.path.insert(0, str(cp))
        import cpcase
        c = cpcase.load_case(r['case'])
        check(sorted(c['sides']) == ['A', 'B'] and c['sides']['A']['driver'] == 'pilot' and c['sides']['B']['link']['c2s']['delay_ms'] == 150, 'the case loads in the co-op runner (two pilot sides, the link delay)')
    placed = dict(PAIR, at={'map': 'Dungeon_X', 'age': 'adult', 'hour': 5})
    r2 = scenario.pair_files(placed, tmp / 'pairout2', tmp / 'frozen', '/x/a', '/x/b', tmp / 'rv2')
    sg2 = pilot.Segment(tmp / 'pairout2' / 'pair-t-A.toml')
    check(sg2.place == {'to': 'Dungeon_X', 'age': 'adult', 'hour': 5}, 'a scenario with a placement gives each segment its [place]')
    try:
        scenario.pair_files(BASE, tmp / 'x', tmp, 'a', 'b', tmp / 'rv3'); check(False, 'pair_files refuses a solo scenario')
    except scenario.ScenarioError:
        check(True, 'pair_files refuses a solo scenario')

class FS:
    def __init__(self, key, sev='error', known=False, side='A', kind='give', sub='double'):
        self.key, self.severity, self.side, self.kind, self.sub, self.text = key, sev, side, kind, sub, 'x'
        self.evidence = {'known': 'docs'} if known else {}

def pair_sides(tmp, rise_a=2, steps_ok=True):
    out = {}
    for name in 'AB':
        st = tb.steady(20)
        for i, r in enumerate(st):
            r['flags'] = {'Key_Count': 3 + (rise_a if (name == 'A' and i > 10) else 1 if i > 12 else 0)}
        comp = scenario.compile_steps(PAIR, side=name)
        evs = [tb.step(2.0 + i, l, 'reached' if steps_ok else 'stuck', **{'in': i + 2}) for i, (l, _) in enumerate([c for c in comp if not c[0].startswith('#')])]   # (the watch line is step 1)
        out[name] = tb.make_side(tmp / f'ps-{name}-{rise_a}-{steps_ok}', st, events=tb.events_for(st, steps=evs), log='[hos host] vk: device 0: Test GPU 2, Vulkan 1.4\n', summary=tb.OK_SUMMARY, exit_code=143)
    return out

def pair_eval_checks(tmp):
    sides = pair_sides(tmp)
    tg = scenario.align_tags(sides['A'].steps, scenario.compile_steps(PAIR, side='A'))
    check(tg == {2: 'approach', 3: 'rendezvous', 4: 'chest', 5: 'stick'}, f'align_tags matches the compiled lines to the played steps, the watch line before them ({tg})')
    r = scenario.evaluate_pair(PAIR, [FS('give:double:abc')], sides)
    c = {x['check']: x for x in r['checks']}
    check(r['verdict'] == 'reproduced' and c['key']['verdict'] == 'reproduced' and c['counter']['verdict'] == 'reproduced' and c['counter']['rises']['A'] == 2 and c['clean']['verdict'] == 'reproduced'
          and c['reached']['verdict'] == 'reached' and r['hardware'] == 'Test GPU 2' and r['players'] == 2, f'pair: the key, the counter (+2 on A) and the finding are reproduced ({r["verdict"]}, {c})')
    check(scenario.evaluate_pair(PAIR, [FS('give:double:abc', 'info', known=True)], sides)['checks'][0]['verdict'] == 'reproduced', 'pair: a known key (triaged info with the note) still counts as having fired')
    check(scenario.evaluate_pair(PAIR, [FS('give:double:abc', 'info')], sides)['checks'][0]['verdict'] == 'not reproduced', 'pair: an explained key does not')
    sides1 = pair_sides(tmp, rise_a=1)
    r = scenario.evaluate_pair(PAIR, [], sides1)
    check(r['verdict'] == 'not reproduced' and all(x['verdict'] in ('not reproduced', 'reached') for x in r['checks']), f'pair: nothing found, the counter rose once: not reproduced ({r["verdict"]})')
    r = scenario.evaluate_pair(PAIR, [FS('stall:both:1', kind='stall', sub='both')], sides1)
    check([x for x in r['checks'] if x['check'] == 'clean'][0]['verdict'] == 'not reproduced', 'pair: clean ignores the kinds it is told to')
    r = scenario.evaluate_pair(PAIR, [FS('crash:x:1', kind='crash', sub='crash', side='B')], sides1)
    check([x for x in r['checks'] if x['check'] == 'crash'][0]['verdict'] == 'reproduced' and r['verdict'] == 'reproduced', 'pair: a crash on either side')
    dv = dict(PAIR, expect=[{'check': 'crash'}, {'check': 'visited', 'map': 'Yard'}])
    r = scenario.evaluate_pair(dv, [], sides1)
    check(r['verdict'] == 'not reproduced' and [x for x in r['checks'] if x['check'] == 'visited'][0]['verdict'] == 'reached', 'pair: both players were in the map the gate names')
    dv2 = dict(PAIR, expect=[{'check': 'crash'}, {'check': 'visited', 'map': 'Boss_Room'}])
    r = scenario.evaluate_pair(dv2, [], sides1)
    check(r['verdict'] == 'inconclusive' and [x for x in r['checks'] if x['check'] == 'visited'][0]['per_side'] == {'A': False, 'B': False}, 'pair: players that never reached the map the gate names: inconclusive')
    dv3 = dict(PAIR, expect=[{'check': 'crash'}, {'check': 'visited', 'map': 'Yard', 'who': 'B'}])
    check(scenario.evaluate_pair(dv3, [], sides1)['checks'][1]['per_side'] == {'B': True}, 'pair: a visited gate for one player only')
    dm = dict(PAIR, expect=[{'check': 'crash'}, {'check': 'visited', 'music': 'BGM_BossRoom'}])
    check(scenario.problems(dm) == [] and scenario.problems(dict(PAIR, expect=[{'check': 'visited'}])) != [], 'visited needs a map or a music')
    for sd in sides1.values():
        for r in sd.states:
            r['music'] = 'BGM_BossRoom'
    check(scenario.evaluate_pair(dm, [], sides1)['checks'][1]['verdict'] == 'reached', 'pair: a visited gate by the music of the state')
    # a session whose games never reached control: the runner's own kill is no crash, the run is inconclusive
    nobody = {n: tb.make_side(tmp / f'np-{n}', [], events=[], log='[hos host] boot\n', summary=tb.OK_SUMMARY, exit_code=137) for n in 'AB'}
    kill = FS('crash:exit:x', kind='crash', sub='exit', side='A'); kill.text = 'the game ended with SIGKILL (exit 137), not at the wall or by our stop'
    kill2 = FS('crash:coop-faults:x', kind='crash', sub='coop-faults', side='B'); kill2.text = 'exit code 137'
    r = scenario.evaluate_pair(PAIR, [kill, kill2], nobody)
    check(r['verdict'] == 'inconclusive' and 'control' in r['why'] and all(c['verdict'] == 'inconclusive' for c in r['checks']), f'pair: no game reached control and the runner killed them: inconclusive ({r["verdict"]})')
    # one game booted, the other never reached control (hold 7: B was still compiling its pipelines at the deadline): nothing about two players is shown
    half = {'A': sides1['A'], 'B': nobody['B']}
    r = scenario.evaluate_pair(PAIR, [], half)
    check(r['verdict'] == 'inconclusive' and 'B' in r['why'] and 'never reached control' in r['why'], f'pair: one player never reached control: inconclusive, not "not reproduced" ({r["verdict"]}, {r.get("why")})')
    r = scenario.evaluate_pair(PAIR, [FS('give:double:abc')], half)
    check(r['verdict'] == 'reproduced', 'pair: a key that fired is a result whoever else failed to boot')
    # a game that played, was still in a rendezvous when the runner asked the pilots to end, and was killed by the runner: the runner's kill; an OOM kill is a crash
    half.update(A=sides1['A'])
    sess = Path(sides1['A'].root).parent
    (sess / 'timeline.jsonl').write_text(json.dumps({'w': 5050.0, 't': 195.0, 'kind': 'phase', 'name': 'shutdown'}) + '\n')
    (sess / 'kernel.txt').write_text('nothing of note\n')
    killA = FS('crash:exit:z', kind='crash', sub='exit', side='A'); killA.text = 'the game ended with SIGKILL (exit 137), not at the wall or by our stop'
    r = scenario.evaluate_pair(PAIR, [killA], half)
    check(r['verdict'] == 'inconclusive' and [c for c in r['checks'] if c['check'] == 'crash'][0]['verdict'] == 'not reproduced', f'pair: SIGKILL of a game after the runner\'s shutdown began is the runner\'s ({r["verdict"]})')
    (sess / 'kernel.txt').write_text('Out of memory: Killed process 123 (game)\n')
    check(scenario.evaluate_pair(PAIR, [killA], half)['verdict'] == 'reproduced', 'pair: with an out-of-memory line in the kernel log the SIGKILL is a crash')
    (sess / 'kernel.txt').write_text('nothing of note\n')
    (sess / 'timeline.jsonl').unlink()
    check(scenario.evaluate_pair(PAIR, [killA], half)['verdict'] == 'reproduced', 'pair: a SIGKILL with no shutdown phase on record is a crash')
    segv = FS('crash:exit:y', kind='crash', sub='exit', side='B'); segv.text = 'the game ended with SIGSEGV'
    check(scenario.evaluate_pair(PAIR, [segv], nobody)['verdict'] == 'reproduced', 'pair: a crash while booting is still a crash')
    stuck = pair_sides(tmp, rise_a=1, steps_ok=False)
    r = scenario.evaluate_pair(PAIR, [], stuck)
    check(r['verdict'] == 'inconclusive' and [x for x in r['checks'] if x['check'] == 'reached'][0]['verdict'] == 'not reached', 'pair: players that never got where they were meant to: inconclusive, not "not reproduced"')

def pilot_scripted_checks(tmp):
    """pilot.py run on a scripted segment (a fake game side): the prefix is the whole play, after the placement when there is one, then `end`"""
    import argparse, shutil, time
    import pilot
    import placement
    import test_pilot as tp
    for name, place in (('plain', ''), ('placed', '\n[place]\nto = "Fake_Area"\nage = "child"\n')):
        seg = tmp / f'scr-{name}.toml'
        seg.write_text(f'name = "scr-{name}"\narea = "Fake_Area"\nscripted = true\nprefix = "scr-{name}.txt"\nwall = 30\nwatch = ["Door_Open"]\n' + place)
        (tmp / f'scr-{name}.txt').write_text('# a comment\npress A 100\nwait 0.2\nstick up 300\n')
        live = tmp / f'live-scr-{name}'
        pilot.Channel(live)
        game = tp.FakeGame(live)
        game.start()
        saved = placement.apply
        order = []
        placement.apply = lambda spec, run, env=None: (order.append(('placed', (live / 'steps.txt').read_text().splitlines())), {'ok': True, 'map': 'Fake_Area', 'seconds': 0.1})[1]
        tag = f'scr-run-{name}-{time.time_ns()}'
        try:
            args = argparse.Namespace(segment=str(seg), decider='rules', replay=None, planner=False, copy=str(tmp / 'copy'), tag=tag, attach=str(live), save=None, wall=30, max_decisions=None,
                                      follow=[], end_hold=0.0, shots=0, api_base=None, allowance_usd=None, allowance_since='2026-01-01', matches=None)
            code = pilot.cmd_run(args)
        finally:
            placement.apply = saved
        run_dir = pilot.HERE / 'runs' / tag
        summary = json.loads((run_dir / 'summary.json').read_text())
        steps = (run_dir / 'steps.txt').read_text().splitlines()
        shutil.rmtree(run_dir, ignore_errors=True)
        check(summary['outcome'] == 'scripted' and code == 0 and steps[-1] == 'end' and steps[-4:-1] == ['press A 100', 'wait 0.2', 'stick up 300'], f'scripted {name}: the prefix then `end` ({summary["outcome"]}, {steps})')
        if place:
            check(order and order[0][1] == ['watch Door_Open'], f'scripted placed: at the moment of the placement only the watch line had been sent ({order})')
    bad = tmp / 'scr-bad.toml'
    bad.write_text('name = "x"\narea = "A"\nscripted = true\n')
    try:
        pilot.Segment(bad); check(False, 'a scripted segment without a prefix is refused')
    except ValueError as e:
        check('prefix' in str(e), 'a scripted segment without a prefix is refused')
    bad.write_text('name = "x"\narea = "A"\n')
    try:
        pilot.Segment(bad); check(False, 'a segment with neither goals nor scripted is refused')
    except ValueError as e:
        check('goals' in str(e), 'a segment with neither goals nor scripted is refused')


def forge_checks(tmp):
    """the forge's address and the lock its readers share are this machine's settings: none has a default, a missing one is refused naming it;
    the issue is fetched under the lock (a fake flock and a fake curl stand in for the real ones)"""
    names = (scenario.ENV_FORGE, scenario.ENV_FORGE_LOCK, 'PATH')
    saved = {k: os.environ.get(k) for k in names}
    try:
        for k in names[:2]:
            os.environ.pop(k, None)
        for bad in (None, 'forge.test/o/r', 'ftp://forge.test/o/r', 'https://forge.test/o', 'https://forge.test/o/r/x', 'https://forge.test/o/r?x=1'):
            if bad is None:
                os.environ.pop(scenario.ENV_FORGE, None)
            else:
                os.environ[scenario.ENV_FORGE] = bad
            try:
                scenario.forge_addresses()
                check(False, f'forge_addresses: {bad!r} is refused')
            except scenario.ScenarioError as e:
                check(scenario.ENV_FORGE in str(e) and 'no default' in str(e), f'forge_addresses: {bad!r} is refused, naming the setting ({e})')
        os.environ[scenario.ENV_FORGE] = 'https://forge.test/o/r/'
        api, pages = scenario.forge_addresses()
        check(api == 'https://forge.test/api/v1/repos/o/r' and pages == 'https://forge.test/o/r/issues/', f'forge_addresses: the API and the page base from the project page ({api}, {pages})')
        try:
            scenario.fetch_issue(7)
            check(False, 'fetch_issue: without the lock setting it is refused')
        except scenario.ScenarioError as e:
            check(scenario.ENV_FORGE_LOCK in str(e) and 'no default' in str(e), f'fetch_issue: without the lock setting it is refused, naming it ({e})')
        bindir, record = tmp / 'forge-bin', tmp / 'forge-calls.txt'
        bindir.mkdir()
        for name, body in (('flock', f'#!/bin/sh\necho "flock $1" >> {record}\nshift\nexec "$@"\n'),
                           ('curl', f'#!/bin/sh\necho "curl $*" >> {record}\necho \'{{"title": "T", "body": "B"}}\'\n')):
            (bindir / name).write_text(body)
            (bindir / name).chmod(stat.S_IRWXU)
        os.environ['PATH'] = f'{bindir}{os.pathsep}{os.environ["PATH"]}'
        os.environ[scenario.ENV_FORGE_LOCK] = str(tmp / 'forge.lock')
        check(scenario.fetch_issue(7) == ('T', 'B'), 'fetch_issue: the title and the body of the answer')
        calls = record.read_text().splitlines()
        check(calls[0] == f'flock {tmp / "forge.lock"}' and calls[1].endswith('https://forge.test/api/v1/repos/o/r/issues/7'), f'fetch_issue: curl runs under the setting\'s lock, at the setting\'s API ({calls})')
        dests = tmp / 'forge-dests.json'
        dests.write_text(json.dumps([YARD, 'Cave']))
        out = tmp / 'forge-issue.toml'
        check(scenario.main(['import', '--issue', '7', '--destinations', str(dests), '--out', str(out)]) == 0 and 'https://forge.test/o/r/issues/7' in out.read_text(), 'import --issue: the reference is the issue\'s page on the setting\'s forge')
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    text = (HERE / 'scenario.py').read_text()
    for p in hs_names.PROJECTS:   # the game's own names come from hs_names, never spelled in the code
        check(p not in text.lower(), f'scenario.py: the project name {p!r} is not spelled here')

def run_in(tmp):
    format_checks(tmp); compile_checks(tmp); importer_checks(tmp); placement_checks(tmp); eval_checks(tmp); pair_checks(tmp); pair_eval_checks(tmp); pilot_scripted_checks(tmp); forge_checks(tmp)
if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='test-scenario-') as t:
        run_in(Path(t))
    if FAILS:
        raise SystemExit(f'test_scenario: {len(FAILS)} of {CHECKS[0]} checks FAILED')
    print(f'test_scenario: all {CHECKS[0]} checks passed')
