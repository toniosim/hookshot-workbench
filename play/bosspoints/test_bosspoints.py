#!/usr/bin/env python3
"""bosspoints on a made-up table (three targets with neutral names and round numbers): the loader and its messages, the validator, the scenario
files (checked with pilot/scenario.py), the save commands (printed and run through a stand-in save tool), the hold plan (stand-in hash and planner),
the analyzer over a made-up hold folder, and the dry-run stand-in for hsap. No game, no world model, no local table.
    python3 -I -B test_bosspoints.py
"""
import contextlib
import copy
import io
import json
import os
import shlex
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'pilot'))
import analyze_hold as AH  # noqa: E402
import bosspoints_table as T  # noqa: E402
import make_saves as MS  # noqa: E402
import plan_hold as PH  # noqa: E402
import scenario as S  # noqa: E402
import write_scenarios as WS  # noqa: E402

FAILS, COUNT = [], [0]


def check(cond, what):
    COUNT[0] += 1
    if not cond:
        FAILS.append(what)
        print('FAIL', what, flush=True)


SYN = {
    'schema': 'bosspoints/1', 'game': 'game-files', 'base_save': 'base-save',
    'targets': [
        {'key': 'alpha', 'title': 'Alpha Target', 'map': 'AreaOne', 'age': 'child', 'give': ['item-a', 'item-b=5', 'item-c=7'],
         'vars': {'door': [10, 20, 30], 'through': [10, 20, 36], 'anchor': [10, 14, 60], 'crack': [12, 33]},
         'note': 'free text', 'info': {'any': ['json', 1]},
         'starts': [
             {'name': 'alpha-door', 'at': {'x': 10, 'y': 20, 'z': 27, 'facing': 0}, 'claim': 'Alpha: from outside the door to the room',
              'header': ['first header line', 'second header line'],
              'actions': [{'do': 'wait', 's': 3.0, 'tag': 'settle'},
                          {'do': 'enter', 'x': '{door[0]}', 'z': '{door[2]}', 'through_x': '{through[0]}', 'through_z': '{through[2]}', 'timeout': 55.0, 'tag': 'door'},
                          {'do': 'repeat', 'n': 2, 'actions': [{'do': 'walk', 'x': '{crack[0]}', 'z': '{crack[1]}', 'radius': 1.0}, {'do': 'press', 'button': 'A', 'ms': 150}]},
                          {'do': 'go_near', 'x': '{anchor[0]}', 'z': '{anchor[2]}', 'radius': 2.5, 'timeout': 60.0, 'tag': 'to-goal'}],
              'save': {'flags': ['FlagA=1', 'QuestA=Part2'], 'point': 'Alpha at the door', 'note': 'made up'},
              'hold': {'steps': ['# {key} on {map} ({age})', {'watch': ['flag.alpha', 'flag.alpha.two']}, 'report 1',
                                 'enter {door[0]:.2f} {door[2]:.2f} through {through[0]:.2f} {through[2]:.2f} timeout 55',
                                 {'route': {'from': 'through', 'to': 'anchor'}}, 'say {{braces}} and {title}', 'end'],
                       'note': 'route: {route}', 'expect': 'flag.alpha'}},
             {'name': 'alpha-side', 'at': {'x': 5, 'y': 20, 'z': 27, 'facing': 90}, 'save': {'name': 'alpha-side-save', 'give': ['item-a'], 'flags': ['FlagA=1']}},
         ]},
        {'key': 'beta', 'title': 'Beta Target', 'map': 'AreaTwo', 'age': 'adult', 'vars': {'p': [0, 0, 0], 'q': [3, 0, 40]},
         'starts': [
             {'name': 'beta-start', 'at': {'x': 0, 'y': 0, 'z': 0}, 'claim': 'Beta: starts at the origin', 'expect': [{'check': 'crash'}],
              'actions': [{'do': 'wait', 's': 2.0}, {'do': 'shot', 'tag': 'look'}],
              'save': {'start': 'AreaTwo/StartB', 'give': ['item-c'], 'flags': []},
              'hold': {'steps': ['# {key}', {'watch': ['flag.beta']}, {'route': {'from': 'p', 'to': 'q', 'map': 'AreaBlocked', 'radius': 2.0, 'max_steps': 3, 'timeout': 9, 'doors': 'stop'}}, 'end'],
                       'note': 'beta note'}},
             {'name': 'beta-combo', 'map': 'AreaOne', 'age': 'child', 'at': {'x': 1, 'y': 2, 'z': 3, 'facing': 180},
              'save': {'give': ['item-a', 'item-c'], 'flags': ['FlagB=2'], 'optional': 'combo'}},
         ]},
        {'key': 'gamma', 'title': 'Gamma', 'map': 'AreaNone', 'age': 'child', 'vars': {'a': [0, 0, 0], 'b': [0, 0, 9]},
         'starts': [{'name': 'gamma-start', 'at': {'x': 2, 'y': 2, 'z': 2, 'facing': 270}, 'save': {'give': [], 'flags': ['FlagG=3']},
                     'hold': {'steps': ['# {start}', {'route': {'from': 'a', 'to': 'b'}}, 'end'], 'note': 'route: {route}'}}]},
    ],
    'hold': {'runs': [
        {'lane': 'a', 'id': 'alpha', 'start': 'alpha-door', 'wall': 120},
        {'lane': 'b', 'id': 'beta', 'start': 'beta-start', 'wall': 90, 'save': 'beta-save-two', 'note': 'tried: {route}', 'expect': 'flag.beta'},
        {'lane': 'a', 'id': 'gamma', 'start': 'gamma-start', 'wall': 60},
        {'lane': 'b', 'id': 'alpha-own', 'start': 'alpha-door', 'wall': 30, 'steps': ['# own steps', 'end']},
    ]},
}


def stub_hash(name):
    return sum(ord(c) for c in name) * 7


class StubPlanner:
    def __init__(self):
        self.calls = []

    def available(self, area):
        return area != 'AreaNone'

    def plan(self, area, from_xz, to_xz, *, from_y=None, to_y=None, radius=1.0, doors='stop'):
        self.calls.append((area, tuple(from_xz), tuple(to_xz), from_y, to_y, radius, doors))
        if area == 'AreaBlocked':
            return {'ok': False, 'why': 'needs-drop', 'detail': 'd' * 200, 'steps': ['run 1 2 radius 1']}
        return {'ok': True, 'steps': ['run %d %d radius 1' % (i, i + 1) for i in range(16)]}


def run_main(fn, argv, env=None):
    """(return code, stdout, stderr) of fn(argv) with an environment overlay"""
    out, err = io.StringIO(), io.StringIO()
    saved = {k: os.environ.get(k) for k in (env or {})}
    for k, v in (env or {}).items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                rc = fn(argv)
            except SystemExit as e:
                rc = e.code
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return rc, out.getvalue(), err.getvalue()


def fails_with(mutate, fragment, what):
    d = copy.deepcopy(SYN)
    mutate(d)
    try:
        T.Table(d, 'synthetic.json')
    except T.TableError as e:
        check(fragment in str(e) and 'synthetic.json' in str(e), f'validator: {what} -> {fragment!r} (got {str(e)[:150]!r})')
        return
    check(False, f'validator: {what} is refused')


def table_checks(tmp):
    check(T.DEFAULT_TABLE == HERE / 'table.local.json', 'the default table file is table.local.json beside the tools')
    saved = os.environ.pop(T.ENV_TABLE, None)
    check(T.table_path() == HERE / 'table.local.json', 'table_path: default is table.local.json beside the tools')
    os.environ[T.ENV_TABLE] = str(tmp / 'from-env.json')
    check(T.table_path() == tmp / 'from-env.json' and T.table_path('x.json') == Path('x.json'), 'table_path: $BOSSPOINTS_TABLE, and --table wins over it')
    if saved is None:
        os.environ.pop(T.ENV_TABLE)
    else:
        os.environ[T.ENV_TABLE] = saved
    # a missing table: the message names the file and the schema
    missing = tmp / 'no-such-table.json'
    try:
        T.load(missing)
        check(False, 'a missing table raises')
    except T.TableError as e:
        m = str(e)
        check(str(missing) in m and 'bosspoints/1' in m and T.ENV_TABLE in m and 'schema' in m, f'loader: a missing table names the file, the schema and the variable ({m[:120]!r})')
    rc, out, err = run_main(T.main, ['--table', str(missing)])
    check(rc == 2 and str(missing) in err and out == '', 'bosspoints_table.py: a missing table gives exit 2 and the message on stderr')
    bad = tmp / 'bad.json'
    bad.write_text('{"schema": ')
    try:
        T.load(bad)
        check(False, 'broken JSON raises')
    except T.TableError as e:
        check('not valid JSON' in str(e) and str(bad) in str(e), 'loader: broken JSON names the file')
    good = tmp / 'table.json'
    good.write_text(json.dumps(SYN))
    t = T.load(good)
    check(len(t.targets) == 3 and len(t.starts) == 5 and len(t.runs) == 4 and t.game == 'game-files' and t.base_save == 'base-save', 'loader: the made-up table loads (3 targets, 5 starts, 4 runs)')
    rc, out, err = run_main(T.main, ['--table', str(good)])
    check(rc == 0 and 'ok; 3 targets, 5 starts (2 scenarios, 5 saves, 3 hold recipes), 4 hold runs' in out, f'bosspoints_table.py: the summary line ({out.strip()[-90:]!r})')
    rc, out, _ = run_main(T.main, ['--schema'])
    check(rc == 0 and 'bosspoints/1' in out and '"targets"' in out, 'bosspoints_table.py --schema prints the schema')
    a, b = t.by_name['alpha-door'], t.by_name['beta-combo']
    check(a['age'] == 'child' and a['map'] == 'AreaOne' and a['vars']['door'] == [10, 20, 30] and a['save']['give'] == ['item-a', 'item-b=5', 'item-c=7'],
          'resolve: a start takes the target\'s map, age, vars and give')
    check(b['map'] == 'AreaOne' and b['age'] == 'child' and t.by_name['beta-start']['map'] == 'AreaTwo' and t.by_name['beta-start']['age'] == 'adult', 'resolve: a start\'s own map and age replace the target\'s')
    check(t.by_name['alpha-side']['save']['name'] == 'alpha-side-save' and a['save']['name'] == 'alpha-door', 'resolve: the save name defaults to the start\'s name')
    check([st['name'] for st in t.select()] == ['alpha-door', 'alpha-side', 'beta-start', 'beta-combo', 'gamma-start'], 'select: with no filter every start, in table order')
    check([st['name'] for st in t.select(None, set())] == ['alpha-door', 'alpha-side', 'beta-start', 'gamma-start'], 'select: an empty set of optional names drops the optional save')
    check([st['name'] for st in t.select({'beta'}, {'combo'})] == ['beta-start', 'beta-combo'], 'select: --only beta plus the optional save asked for')
    check([st['name'] for st in t.select({'alpha'}, {'combo'})] == ['alpha-door', 'alpha-side', 'beta-combo'], 'select: an optional save ignores --only')
    try:
        t.select({'nope'})
        check(False, 'select: an unknown target key raises')
    except T.TableError as e:
        check('nope' in str(e) and 'alpha' in str(e), 'select: an unknown target key names the keys there are')
    check(t.watch_names() == ['flag.alpha', 'flag.alpha.two', 'flag.beta'], f'watch_names: every watched flag once, in order ({t.watch_names()})')
    r = {x['id']: x for x in t.runs}
    check(r['alpha']['save'] == 'alpha-door' and r['beta']['save'] == 'beta-save-two' and r['alpha']['expect'] == 'flag.alpha' and r['gamma']['expect'] is None, 'runs: save and expect come from the start unless the run says')
    check(r['alpha-own']['steps'] == ['# own steps', 'end'] and r['alpha-own']['note'] == 'route: {route}', 'runs: own steps replace the start\'s; the note stays the start\'s')
    # the validator
    fails_with(lambda d: d.update(schema='bosspoints/2'), 'schema', 'a wrong schema')
    fails_with(lambda d: d.pop('base_save'), 'base_save', 'no base save')
    fails_with(lambda d: d.update(targets=[]), 'targets', 'no targets')
    fails_with(lambda d: d.update(extra=1), 'unknown key', 'an unknown top-level key')
    fails_with(lambda d: d['targets'][1].update(key='alpha'), 'key', 'a duplicate target key')
    fails_with(lambda d: d['targets'][0]['starts'][1].update(name='alpha-door'), 'name', 'a duplicate start name')
    fails_with(lambda d: d['targets'][0]['starts'][0].update(name='has space'), 'name', 'a start name with a space')
    fails_with(lambda d: d['targets'][0].update(age='teen'), 'age', 'a bad age')
    fails_with(lambda d: d['targets'][0].pop('map'), 'map', 'a start without a map')
    fails_with(lambda d: d['targets'][0]['starts'][0].update(gvie=['x']), 'gvie', 'a misspelt key')
    fails_with(lambda d: d['targets'][0]['vars'].update(door=['a']), 'vars', 'a var that is not numbers')
    fails_with(lambda d: d['targets'][0]['vars'].update(key=[1]), 'vars', 'a reserved var name')
    fails_with(lambda d: d['targets'][0]['starts'][0]['at'].pop('z'), 'together', 'x without z')
    fails_with(lambda d: d['targets'][0]['starts'][0].pop('claim'), 'claim', 'actions without a claim')
    fails_with(lambda d: d['targets'][0]['starts'][0]['actions'].append({'do': 'walk', 'x': '{nope[0]}', 'z': 1.0}), 'nope', 'an action naming a var that is not there')
    fails_with(lambda d: d['targets'][0]['starts'][0]['actions'].append({'do': 'walk', 'x': '{crack[5]}', 'z': 1.0}), 'crack', 'an action naming an index that is not there')
    fails_with(lambda d: d['targets'][1]['starts'][0].pop('claim'), 'claim', 'a claim missing on a second target')
    fails_with(lambda d: d['targets'][0]['starts'][0]['hold']['steps'].append('{title:'), 'steps', 'a hold line with an unfinished field')
    fails_with(lambda d: d['targets'][0]['starts'][1]['save'].update(flags=['NoEquals']), 'NAME=VALUE', 'a flag without =')
    fails_with(lambda d: d['targets'][1]['starts'][0]['save'].pop('start'), 'start', 'a save with no place (no start, no facing)')
    fails_with(lambda d: d['targets'][0]['starts'][0]['hold']['steps'].append({'jump': 1}), 'steps', 'a hold step of an unknown kind')
    fails_with(lambda d: d['targets'][0]['starts'][0]['hold']['steps'].append('{nope}'), 'steps', 'a hold line naming something that is not there')
    fails_with(lambda d: d['targets'][0]['starts'][0]['hold']['steps'].append('unbalanced {'), 'steps', 'a hold line with a stray brace')
    fails_with(lambda d: d['targets'][0]['starts'][0]['hold']['steps'].append({'route': {'from': 'crack', 'to': 'anchor'}}), 'route', 'a route from a var with two numbers')
    fails_with(lambda d: d['targets'][0]['starts'][0]['hold']['steps'].append({'route': {'from': 'door', 'to': 'anchor', 'speed': 1}}), 'route', 'a route with an unknown key')
    fails_with(lambda d: d['targets'][0]['starts'][0]['hold'].update(note='route: {nope}'), 'note', 'a note naming something that is not there')
    fails_with(lambda d: d['hold']['runs'][0].update(start='nowhere'), 'nowhere', 'a run on a start that is not there')
    fails_with(lambda d: d['hold']['runs'][1].update(id='alpha'), 'id', 'a duplicate run id')
    fails_with(lambda d: d['hold']['runs'][0].pop('wall'), 'wall', 'a run without a wall time')
    fails_with(lambda d: d['hold']['runs'].append({'lane': 'a', 'id': 'bare', 'start': 'alpha-side', 'wall': 5}), 'neither', 'a run whose start has no hold steps')
    fails_with(lambda d: d['hold']['runs'][0].update(lane=''), 'lane', 'an empty lane')
    return good, t


def render_checks():
    ctx = {'key': 'k', 'title': 'T', 'map': 'M', 'age': 'child', 'start': 's', 'door': [10, 20, 30], 'crack': [12.5, 33]}
    check(T.render('{door[0]:.2f}|{crack[0]:.1f}|{{x}}|{title}', ctx) == '10.00|12.5|{x}|T', 'render: format fields, decimals and doubled braces')
    check(T.render('n {route}', ctx, route='ok') == 'n ok', 'render: {route} in a note')
    got = T.subst({'x': '{door[0]}', 'l': ['{crack[0]}', 'plain', 3], 'd': {'z': '{door[2]}', 'text': 'a {door[0]} b'}}, ctx)
    check(got == {'x': 10, 'l': [12.5, 'plain', 3], 'd': {'z': 30, 'text': 'a {door[0]} b'}}, f'subst: only values that are exactly a reference become numbers ({got})')
    check(abs(T.yaw_rad(270) + 1.5708) < 1e-4 and abs(T.yaw_rad(90) - 1.5708) < 1e-4 and T.yaw_rad(0) == 0 and abs(abs(T.yaw_rad(180)) - 3.1416) < 1e-4, 'yaw_rad: degrees (0 = +z, 90 = +x) to radians in -pi..pi')


def scenario_checks(tmp, table):
    out = tmp / 'scen'
    names = WS.write_all(table, out)
    check(names == ['alpha-door.toml', 'beta-start.toml'] and sorted(p.name for p in out.iterdir()) == names, f'scenarios: one file per start with actions ({names})')
    a = S.load(out / 'alpha-door.toml')
    check(S.problems(a) == [] and a['name'] == 'alpha-door' and a['save'] == 'alpha-door' and a['claim'].startswith('Alpha:') and a['players'] == 1 and a['purpose'] == 'coverage', 'scenarios: alpha passes scenario.py problems(); name, save, claim, players, purpose')
    check(a['at'] == {'map': 'AreaOne', 'age': 'child', 'x': 10, 'y': 20, 'z': 27, 'facing': 0, 'from': 'save'}, f'scenarios: [at] from the start with from = "save" ({a["at"]})')
    enter = a['action'][1]
    check(enter['x'] == 10 and enter['z'] == 30 and enter['through_x'] == 10 and enter['through_z'] == 36 and enter['timeout'] == 55.0, f'scenarios: references became the table\'s numbers ({enter})')
    check(a['action'][2]['actions'][0] == {'do': 'walk', 'x': 12, 'z': 33, 'radius': 1.0}, 'scenarios: references inside a repeat are resolved too')
    check(a['action'][3]['x'] == 10 and a['action'][3]['z'] == 60 and a['action'][3]['radius'] == 2.5, 'scenarios: a go_near to the anchor var')
    check(a['expect'] == [{'check': 'crash'}, {'check': 'visual', 'subs': ['black', 'void', 'missing_textures']}], 'scenarios: the default checks are crash and visual')
    b = S.load(out / 'beta-start.toml')
    check(b['expect'] == [{'check': 'crash'}] and b['at'] == {'map': 'AreaTwo', 'age': 'adult', 'x': 0, 'y': 0, 'z': 0, 'from': 'save'}, 'scenarios: the start\'s own checks replace the default; no facing when the table has none')
    text = (out / 'alpha-door.toml').read_text()
    check(text.startswith('# first header line\n# second header line\n') and (out / 'beta-start.toml').read_text().startswith('# written by bosspoints'), 'scenarios: the header lines come first as comments; a default notice when there are none')
    check(tomllib.loads(text)['name'] == 'alpha-door' and len(S.compile_steps(a)) >= 4, 'scenarios: the file is TOML and compiles to hsap steps')
    only = tmp / 'only'
    check(WS.write_all(table, only, {'beta'}) == ['beta-start.toml'], 'scenarios: --only picks targets')
    # a start whose scenario has problems: nothing is written
    d = copy.deepcopy(SYN)
    d['targets'][1]['starts'][0]['actions'].append({'do': 'press', 'button': 'Q'})
    t2 = T.Table(d, 'synthetic.json')
    nothing = tmp / 'nothing'
    try:
        WS.write_all(t2, nothing)
        check(False, 'a scenario with problems is refused')
    except T.TableError as e:
        check('beta-start' in str(e) and 'button' in str(e) and not nothing.exists(), 'scenarios: a scenario with problems names the start and writes nothing')
    rc, so, se = run_main(WS.main, ['--table', str(tmp / 'table.json'), '--out', str(tmp / 'main-out')])
    check(rc == 0 and so.startswith('written 2 scenarios: alpha-door.toml beta-start.toml') and (tmp / 'main-out' / 'alpha-door.toml').is_file(), 'write_scenarios main: written line and files')
    rc, so, se = run_main(WS.main, ['--table', str(tmp / 'none.json'), '--out', str(tmp / 'x')])
    check(rc == 2 and 'none.json' in se and 'bosspoints/1' in se and not (tmp / 'x').exists(), 'write_scenarios main: a missing table gives exit 2 and the message')
    d = copy.deepcopy(SYN)
    for st in d['targets'][0]['starts'] + d['targets'][1]['starts']:
        st.pop('actions', None), st.pop('claim', None), st.pop('expect', None)
    try:
        WS.write_all(T.Table(d, 'synthetic.json'), tmp / 'y')
        check(False, 'a table without actions is refused')
    except T.TableError as e:
        check('no start has "actions"' in str(e), 'scenarios: a table with no action list says so')


def stub_tool(tmp):
    """a save tool stand-in: writes its argument list beside --out, prints one line; exits with $STUB_RC"""
    p = tmp / 'stub_tool.py'
    p.write_text('import json, os, sys\n'
                 'i = sys.argv.index("--out")\n'
                 'name = os.path.basename(sys.argv[i + 1]).replace(":", "_")\n'
                 'open(os.path.join(os.environ["STUB_DIR"], name + ".args"), "w").write(json.dumps(sys.argv[1:]))\n'
                 'print("made " + sys.argv[i + 1])\n'
                 'sys.exit(int(os.environ.get("STUB_RC", "0")))\n')
    return p


def save_checks(tmp, table):
    tool = 'tool.py'
    spec = 'AreaOne:{},{},{},{}'.format('10.00', '20.00', '27.00', '0.0000')
    cmd = MS.command(table, table.by_name['alpha-door'], tool, 'game-files', 'outdir', False)
    want = [sys.executable, '-I', '-B', tool, '--game', 'game-files', '--from', 'base-save', '--start', spec, '--age', 'child', '--out', str(Path('outdir') / 'alpha-door'),
            '--give', 'item-a', '--give', 'item-b=5', '--give', 'item-c=7', '--flag', 'FlagA=1', '--flag', 'QuestA=Part2']
    check(cmd == want, f'saves: the command of a door start in order (start spec from map and place) ({cmd})')
    lib = MS.command(table, table.by_name['alpha-door'], tool, 'game-files', None, True)
    check(lib[lib.index('--out') + 1] == 'lib:alpha-door' and lib[-6:] == ['--kind', 'added', '--point', 'Alpha at the door', '--note', 'made up'], 'saves: --lib writes a library entry with the start\'s point and note')
    side = MS.command(table, table.by_name['alpha-side'], tool, 'game-files', None, True)
    check(side[side.index('--out') + 1] == 'lib:alpha-side-save' and side.count('--give') == 1 and side[-1] == MS.DEFAULT_NOTE and 'Alpha Target: child player at AreaOne:' in side[-3], f'saves: a save name, a give list of its own, and the generic point and note ({side[-4:]})')
    beta = MS.command(table, table.by_name['beta-start'], tool, 'game-files', 'o', False)
    check(beta[beta.index('--start') + 1] == 'AreaTwo/StartB' and beta[beta.index('--age') + 1] == 'adult' and '--flag' not in beta, 'saves: an explicit start is used as it is; no flags, no --flag')
    names = [n for n, _ in MS.commands(table, tool, 'game-files', 'o', False)]
    check(names == ['alpha-door', 'alpha-side-save', 'beta-start', 'gamma-start'], f'saves: the optional save is left out by default ({names})')
    names = [n for n, _ in MS.commands(table, tool, 'game-files', 'o', False, {'beta'}, {'combo'})]
    check(names == ['beta-start', 'beta-combo'], f'saves: only + with ({names})')
    combo = dict(MS.commands(table, tool, 'game-files', 'o', False, None, {'combo'}))['beta-combo']
    check(combo[combo.index('--start') + 1] == 'AreaOne:{},{},{},{}'.format('1.00', '2.00', '3.00', '3.1416'), f'saves: yaw of facing 180 in radians ({combo[combo.index("--start") + 1]})')
    # --print
    rc, so, se = run_main(MS.main, ['--table', str(tmp / 'table.json'), '--out', str(tmp / 'saves-a'), '--print'], {'HS_MAKE_SAVE': None})
    lines = so.splitlines()
    check(rc == 0 and len(lines) == 4 and not (tmp / 'saves-a').exists(), 'make_saves --print: one line per save, nothing run or created')
    check(all(shlex.split(ln)[3] == '$HS_MAKE_SAVE' for ln in lines) and '$HS_MAKE_SAVE ' in lines[0], 'make_saves --print without HS_MAKE_SAVE: the variable stays in the line')
    rc, so, se = run_main(MS.main, ['--table', str(tmp / 'table.json'), '--lib', '--print', '--with', 'combo'], {'HS_MAKE_SAVE': str(tmp / 'my tool.py')})
    lines = [shlex.split(ln) for ln in so.splitlines()]
    check(rc == 0 and len(lines) == 5 and lines[0][3] == str(tmp / 'my tool.py') and lines[0] == MS.command(table, table.by_name['alpha-door'], str(tmp / 'my tool.py'), 'game-files', None, True),
          'make_saves --print: quoted so that the lines parse back to the exact commands (with a space in the tool path)')
    # errors
    rc, so, se = run_main(MS.main, ['--table', str(tmp / 'table.json'), '--out', str(tmp / 's')], {'HS_MAKE_SAVE': None})
    check(rc == 2 and 'HS_MAKE_SAVE' in se and 'not part of this repository' in se, 'make_saves: no HS_MAKE_SAVE gives exit 2 naming the variable')
    d = copy.deepcopy(SYN)
    d.pop('game')
    nogame = tmp / 'nogame.json'
    nogame.write_text(json.dumps(d))
    rc, so, se = run_main(MS.main, ['--table', str(nogame), '--out', str(tmp / 's'), '--print'])
    check(rc == 2 and 'no game folder' in se, 'make_saves: no game folder anywhere gives exit 2')
    rc, so, se = run_main(MS.main, ['--table', str(nogame), '--out', str(tmp / 's'), '--print', '--game', 'my-game'])
    check(rc == 0 and shlex.split(so.splitlines()[0])[shlex.split(so.splitlines()[0]).index('--game') + 1] == 'my-game', 'make_saves: --game replaces/supplies the game folder')
    rc, so, se = run_main(MS.main, ['--table', str(tmp / 'table.json'), '--only', 'nope', '--lib', '--print'])
    check(rc == 2 and 'nope' in se, 'make_saves: an unknown target key gives exit 2')
    rc, so, se = run_main(MS.main, ['--table', str(tmp / 'table.json'), '--print'])
    check(rc == 2, 'make_saves: --out or --lib is required')
    rc, so, se = run_main(MS.main, ['--table', str(tmp / 'table.json'), '--out', 'a', '--lib', '--print'])
    check(rc == 2, 'make_saves: --out and --lib exclude each other')
    # run mode through a stand-in tool
    stub = stub_tool(tmp)
    out = tmp / 'saves-run'
    rc, so, se = run_main(MS.main, ['--table', str(tmp / 'table.json'), '--out', str(out), '--game', 'g'], {'HS_MAKE_SAVE': str(stub), 'STUB_RC': '0', 'STUB_DIR': str(out)})
    made = sorted(p.name for p in out.glob('*.args'))
    check(rc == 0 and made == ['alpha-door.args', 'alpha-side-save.args', 'beta-start.args', 'gamma-start.args'], f'make_saves: run mode runs the tool once per save ({made}, rc {rc})')
    args = json.loads((out / 'alpha-door.args').read_text())
    check(args[:2] == ['--game', 'g'] and '--from' in args and args[args.index('--out') + 1] == str(out / 'alpha-door'), 'make_saves: the tool gets the command\'s arguments')
    check(so.splitlines()[0] == '%-28s rc=%d  %s' % ('alpha-door', 0, 'made ' + str(out / 'alpha-door')), f'make_saves: one result line per save ({so.splitlines()[0]!r})')
    (tmp / 'stub-lib').mkdir()
    rc, so, se = run_main(MS.main, ['--table', str(tmp / 'table.json'), '--lib'], {'HS_MAKE_SAVE': str(stub), 'STUB_RC': '3', 'STUB_DIR': str(tmp / 'stub-lib')})
    check(rc == 1 and so.count('rc=3') == 4 and sorted(p.name for p in (tmp / 'stub-lib').iterdir()) == ['lib_alpha-door.args', 'lib_alpha-side-save.args', 'lib_beta-start.args', 'lib_gamma-start.args'],
          'make_saves: a failing tool run gives exit 1 and its code in the line; --lib passes lib:NAME')


def plan_checks(tmp, table):
    planner = StubPlanner()
    hold = tmp / 'hold'
    runs = PH.plan(table, hold, str(tmp / 'saves'), PH.World(flag_hash=stub_hash, planner=planner))
    check(sorted(p.name for p in (hold / 'steps').iterdir()) == ['alpha-own.txt', 'alpha.txt', 'beta.txt', 'gamma.txt'] and (hold / 'plan.json').is_file(), 'hold: plan.json and one steps file per run')
    plan = json.loads((hold / 'plan.json').read_text())
    check(plan == {'runs': json.loads(json.dumps(runs))} and [r['id'] for r in plan['runs']] == ['alpha', 'beta', 'gamma', 'alpha-own'], 'hold: plan.json is the run list in table order')
    r = plan['runs'][0]
    check(r == {'lane': 'a', 'id': 'alpha', 'save': str(tmp / 'saves' / 'alpha-door'), 'steps': 'steps/alpha.txt', 'wall': 120, 'note': 'route: ok', 'expect': 'flag.alpha', 'save_name': 'alpha-door'}, f'hold: a run record ({r})')
    check(list(r) == ['lane', 'id', 'save', 'steps', 'wall', 'note', 'expect', 'save_name'], 'hold: the run record\'s keys are in the runner\'s order')
    lines = (hold / 'steps' / 'alpha.txt').read_text().splitlines()
    check(lines[0] == '# alpha on AreaOne (child)' and lines[1] == 'watch 0x%08x 0x%08x' % (stub_hash('flag.alpha'), stub_hash('flag.alpha.two')) and lines[2] == 'report 1', f'hold: a rendered comment and a watch line of hashes ({lines[:3]})')
    check(lines[3] == 'enter 10.00 30.00 through 10.00 36.00 timeout 55', f'hold: an enter line from the vars ({lines[3]!r})')
    route = lines[4:-2]
    check(len(route) == 14 and route[0] == 'run 0 1 radius 1 timeout 20' and route[-1] == 'run 13 14 radius 1 timeout 20', f'hold: the planner\'s steps, 14 of 16, each with its timeout ({len(route)})')
    check(lines[-2] == 'say {braces} and Alpha Target' and lines[-1] == 'end', 'hold: doubled braces and {title}')
    check(planner.calls[0] == ('AreaOne', (10, 36), (10, 60), 20, 14, 1.5, 'through'), f'hold: the planner is asked x and z with the y of both ends, radius 1.5, doors through ({planner.calls[0]})')
    beta = (hold / 'steps' / 'beta.txt').read_text().splitlines()
    check(beta == ['# beta', 'watch 0x%08x' % stub_hash('flag.beta'), 'run 1 2 radius 1 timeout 9', 'end'], f'hold: route options (map, max_steps, timeout) ({beta})')
    check(planner.calls[1] == ('AreaBlocked', (0, 0), (3, 40), 0, 0, 2.0, 'stop'), 'hold: route options reach the planner (map, radius, doors)')
    check(plan['runs'][1]['note'] == 'tried: needs-drop: ' + 'd' * 120 and plan['runs'][1]['save'].endswith('beta-save-two') and plan['runs'][1]['save_name'] == 'beta-save-two', 'hold: a failed plan: why and the detail cut to 120 characters in the note; the run\'s own save')
    check(plan['runs'][2]['note'] == 'route: no plan' and (hold / 'steps' / 'gamma.txt').read_text() == '# gamma-start\nend\n', 'hold: no nav data for the map: no route lines, note "no plan"')
    check(plan['runs'][2]['expect'] is None and '"expect": null' in (hold / 'plan.json').read_text(), 'hold: no expect is null')
    check((hold / 'steps' / 'alpha-own.txt').read_text() == '# own steps\nend\n' and plan['runs'][3]['note'] == 'route: ', 'hold: a run\'s own steps; {route} is empty with no route item')
    # the world model is loaded only when a recipe needs it
    d = copy.deepcopy(SYN)
    for t in d['targets']:
        for st in t['starts']:
            if st.get('hold'):
                st['hold']['steps'] = [s for s in st['hold']['steps'] if isinstance(s, str)]
    plain = T.Table(d, 'synthetic.json')
    PH.plan(plain, tmp / 'hold-plain', 'saves', PH.World())
    check((tmp / 'hold-plain' / 'plan.json').is_file(), 'hold: text-only recipes need neither the hash nor the planner')
    # main
    good = str(tmp / 'table.json')
    rc, so, se = run_main(PH.main, [str(tmp / 'h1'), '--table', good], {'BOSSPOINTS_SAVES': None})
    check(rc == 2 and 'BOSSPOINTS_SAVES' in se and '--saves' in se and not (tmp / 'h1').exists(), 'plan_hold: no save library folder gives exit 2 naming both ways')
    rc, so, se = run_main(PH.main, [str(tmp / 'h2'), '--table', str(tmp / 'none.json'), '--saves', 's'])
    check(rc == 2 and 'none.json' in se and 'bosspoints/1' in se, 'plan_hold: a missing table gives the message')
    real_hash, real_planner = T.flag_hash_function, T.planner_module
    try:
        def no_world():
            raise T.TableError('this needs the world model: stand-in refusal')
        T.flag_hash_function = no_world
        rc, so, se = run_main(PH.main, [str(tmp / 'h3'), '--table', good, '--saves', 's'])
        check(rc == 2 and 'world model' in se, 'plan_hold: a missing world model gives exit 2 and its reason')
        T.flag_hash_function, T.planner_module = (lambda: stub_hash), (lambda: StubPlanner())
        rc, so, se = run_main(PH.main, [str(tmp / 'h4'), '--table', good, '--saves', 'lib-dir'], {'BOSSPOINTS_SAVES': 'ignored'})
        check(rc == 0 and so.splitlines()[0] == 'a alpha alpha-door route: ok' and so.splitlines()[1] == 'b beta beta-save-two tried: needs-drop: ' + 'd' * 81 and json.loads((tmp / 'h4' / 'plan.json').read_text())['runs'][0]['save'] == 'lib-dir/alpha-door',
              f'plan_hold main: runs listed, --saves wins over the variable ({so.splitlines()[:2]})')
    finally:
        T.flag_hash_function, T.planner_module = real_hash, real_planner


def hold_folder(tmp, table):
    """a made-up finished hold: two runs (one with pictures), a skipped one and an errored one"""
    out = tmp / 'hold-out'
    shots = tmp / 'runs-a' / 'shots'
    shots.mkdir(parents=True)
    for n in (60, 120, 180, 240, 300):
        (shots / ('shot_%06d.png' % n)).write_bytes(b'x')
    names = {n: '0x%08x' % stub_hash(n) for n in ('flag.alpha', 'flag.alpha.two')}
    live = out / 'live' / 'alpha'
    live.mkdir(parents=True)
    rows = []
    t0 = 1000.0
    for i in range(80):
        moving = 5 <= i < 20
        rows.append({'t': t0 + i * 0.1, 'frame': 10 + i * 6, 'map': 'AreaOne', 'pos': [10, 20, 27 + (i - 4 if moving else (15 if i >= 20 else 0))], 'facing': 0.0,
                     'event': 1 if i < 25 else 0, 'loading': 0, 'life': 80 if i < 40 else 78, 'music': '' if i < 30 else 'music-x', 'flags': {names['flag.alpha']: 0}, 'child': 1})
    (live / 'state.jsonl').write_text('\n'.join(json.dumps(r) for r in rows) + '\n')
    events = [{'ev': 'gameplay', 't': 3.0, 'frame': 100, 'area': 'AreaOne'}]
    events += [{'ev': 'state', 't': 1.0 * k, 'frame': 60 * k, 'flags': {names['flag.alpha']: 1 if k >= 4 else 0}} for k in range(1, 6)]
    events += [{'ev': 'step', 'src': 'enter 10 30 through 10 36 timeout 55', 'result': 'done', 't': 2.5, 'detail': ''}, 'not json']
    (live / 'out.jsonl').write_text('\n'.join(e if isinstance(e, str) else json.dumps(e) for e in events) + '\n')
    result = {'started_at': 'S', 'finished_at': 'F', 'elapsed_s': 12.5, 'kernel': {'kernel_driver_lines': 0},
              'runs': [{'id': 'alpha', 'lane': 'a', 'save': 'alpha-door', 'started': 0.0, 'ended': 10.4, 'returncode': 0, 'shots': 5, 'run_folder': str(tmp / 'runs-a'), 'summary': 'sum',
                        'journal': {'gameplay': {'t': 3.0, 'frame': 100, 'area': 'AreaOne'}, 'areas': [['AreaOne', 1.0]], 'events': 4, 'music': [['music-x', 3.0]],
                                    'flags_seen': {names['flag.alpha']: [[0, 1.0], [1, 4.0]], '0x0000beef': [[1, 2.0]]},
                                    'steps': [{'src': 'enter 10 30 through 10 36 timeout 55', 'result': 'done', 'detail': 'x' * 100}, {'src': 'shot', 'result': 'done'}], 'last_state': {'t': 5.0}}},
                       {'id': 'beta', 'lane': 'b', 'skipped': 'out of time'}, {'id': 'gamma', 'lane': 'b', 'error': 'boom'}]}
    (out / 'result.json').write_text(json.dumps(result))
    return out, names


def analyzer_checks(tmp, table):
    out, names = hold_folder(tmp, table)
    live = out / 'live' / 'alpha'
    first = AH.first_state_rows(live)
    check(first['pos'] == [10, 20, 27] and first['map'] == 'AreaOne', 'analyzer: the journal\'s first row is where the save put the player')
    check(AH.first_state_rows(out / 'live' / 'beta') is None and AH.journal(out / 'live' / 'beta') == [], 'analyzer: no journal gives None / no rows')
    pc = AH.pre_control(live)
    check(pc['map'] == 'AreaOne' and pc['pos'] == [10, 20, 27] and pc['child'] == 1 and pc['moved'] == 15.0 and pc['life'] == (80, 78) and pc['music'] == ['music-x'], f'analyzer: pre_control: place, how far the player moved, life and music ({pc})')
    check(pc['events'] == [(0.0, 1), (2.5, 0)] and pc['seconds'] == 5.4, f'analyzer: pre_control: events by time and the seconds to three calm seconds ({pc["events"]}, {pc["seconds"]})')
    states, steps = AH.read_states(live)
    check(len(states) == 5 and len(steps) == 1 and AH.read_states(out / 'live' / 'beta') == ([], []), 'analyzer: read_states skips lines that are not JSON')
    shots = sorted((tmp / 'runs-a' / 'shots').glob('*.png'))
    check(AH.nearest_shot(shots, 130).name == 'shot_000120.png' and AH.nearest_shot(shots, 1000).name == 'shot_000300.png' and AH.nearest_shot([], 5) is None, 'analyzer: the picture nearest to a present')
    check(AH.frame_at(states, 3.2) == 180 and AH.frame_at([], 1.0) is None, 'analyzer: the present of the state nearest in time')
    h = lambda n: '0x%08x' % stub_hash(n)
    check(AH.names_of(table, stub_hash) == {h('flag.alpha'): 'flag.alpha', h('flag.alpha.two'): 'flag.alpha.two', h('flag.beta'): 'flag.beta'}, 'analyzer: flag names from the table\'s watch items')
    lines = []
    AH.report(out, AH.names_of(table, stub_hash), None, emit=lambda *a: lines.append(' '.join(str(x) for x in a)))
    text = '\n'.join(lines)
    check(lines[0] == "hold: started S finished F elapsed 12.5 s; kernel {'kernel_driver_lines': 0}", f'analyzer: the first line ({lines[0]!r})')
    check('== alpha (lane a, save alpha-door): rc 0, 10 s, 5 pictures' in text and "watched flags: {'flag.alpha': [[0, 1.0], [1, 4.0]], '0x0000beef': [[1, 2.0]]}" in text, 'analyzer: the run block names the watched flags it knows and keeps the hashes it does not')
    check('== beta (lane b): out of time' in text and '== gamma (lane b): boom' in text, 'analyzer: skipped and errored runs are listed')
    check("steps: [('enter', 'done', '" + 'x' * 60 + "')]" in text and 'before control (the journal, from the load): {' in text, 'analyzer: movement steps with a 60 character detail; the pre-control line')
    # panels through a stand-in script
    script = tmp / 'panels.sh'
    script.write_text('#!/bin/bash\nprintf "%s\\n" "$@" > "$(dirname "$1")/panel-args.txt"\necho made "$PANEL_W"\n')
    lines = []
    AH.report(out, {}, str(script), emit=lambda *a: lines.append(' '.join(str(x) for x in a)))
    parts = (out / 'panel-args.txt').read_text().splitlines()
    check(parts[0] == str(out / 'panel-alpha.jpg') and parts[1] == '2' and parts[2].endswith('shot_000300.png') and parts[3].startswith('1. standing there') and parts[-1].startswith('4. last state'),
          f'analyzer --panels: the script gets the panel path, 2 columns and picture/caption pairs ({parts[:2]}, {len(parts)} args)')
    check(any(ln.startswith('   panel:') and 'made 640' in ln for ln in lines), 'analyzer --panels: the script\'s answer is printed')
    # main
    rc, so, se = run_main(AH.main, [str(out), '--table', str(tmp / 'none.json')])
    check(rc == 0 and 'flags are not named' in se and 'none.json' in se and "'" + h('flag.alpha') + "'" in so, 'analyzer main: without a table the hashes are printed and stderr says why')
    rc, so, se = run_main(AH.main, [str(out), '--panels'], {'BOSSPOINTS_PANELS': None})
    check(rc == 2 and 'BOSSPOINTS_PANELS' in se and so == '', 'analyzer main: --panels without the variable gives exit 2 naming it')
    rc, so, se = run_main(AH.main, [str(tmp / 'not-a-hold'), '--table', str(tmp / 'none.json')])
    check(rc == 2 and 'result.json' in se, 'analyzer main: a folder that is no hold gives exit 2')
    real_hash = T.flag_hash_function
    try:
        T.flag_hash_function = lambda: stub_hash
        rc, so, se = run_main(AH.main, [str(out), '--table', str(tmp / 'table.json')])
        check(rc == 0 and se == '' and "'flag.alpha': [[0, 1.0], [1, 4.0]]" in so, 'analyzer main: with the table and a hash the flags are named')
    finally:
        T.flag_hash_function = real_hash


def dry_checks(tmp):
    live = tmp / 'dry-live'
    live.mkdir()
    (live / 'steps.txt').write_text('# comment\nwatch 0x0000000a 0x0000000b\nreport 1\n\nshot\nend\n')
    r = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'dry_fake_hsap.py'), str(tmp / 'dry-copy'), 'tag1', '60', '--live', str(live), '--save', 'x', '--boot', 'load'], capture_output=True, text=True, timeout=60)
    ev = [json.loads(ln) for ln in (live / 'out.jsonl').read_text().splitlines()]
    steps = [e['src'] for e in ev if e['ev'] == 'step']
    check(r.returncode == 0 and [e['ev'] for e in ev] == ['gameplay', 'state', 'step', 'step', 'step', 'step', 'state', 'done'], f'dry fake: the events it writes ({[e["ev"] for e in ev]}, rc {r.returncode})')
    check(ev[1]['flags'] == {'0x0000000a': 0, '0x0000000b': 0} and ev[6]['flags'] == {'0x0000000a': 1, '0x0000000b': 1}, 'dry fake: the watched hashes go from 0 to 1')
    check(steps == ['watch 0x0000000a 0x0000000b', 'report 1', 'shot', 'end'], f'dry fake: one step event per step line, comments and blanks skipped ({steps})')
    run = tmp / 'dry-copy' / 'runs' / 'tag1'
    check((run / 'summary.txt').read_text() == 'fake run tag1\n' and (run / 'shots' / 'shot_000060.png').is_file(), 'dry fake: summary and one picture under COPY/runs/TAG')


def main():
    with tempfile.TemporaryDirectory(prefix='bosspoints-test-') as t:
        tmp = Path(t)
        good, table = table_checks(tmp)
        render_checks()
        scenario_checks(tmp, table)
        save_checks(tmp, table)
        plan_checks(tmp, table)
        analyzer_checks(tmp, table)
        dry_checks(tmp)
    if FAILS:
        raise SystemExit(f'test_bosspoints: {len(FAILS)} of {COUNT[0]} checks FAILED')
    print(f'test_bosspoints: all {COUNT[0]} checks passed')


if __name__ == '__main__':
    main()
