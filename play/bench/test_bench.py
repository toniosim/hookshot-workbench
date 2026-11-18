#!/usr/bin/env python3
"""The benchmark without a game: the cut of a segment, the TOML written back, the ghost leader's path, the plan, each arm's
command line, stopping a cell's processes by pid, a whole play of fake pilots (sequential, as a pair, resumed, over the hold's
time, timed out) and the report's table. No game, no network.   python3 -I -B test_bench.py
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import tomllib
from argparse import Namespace
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'pilot'))
import course  # noqa: E402
import ghost  # noqa: E402
import mkcourse  # noqa: E402
import run  # noqa: E402

FAILS, COUNT = [], [0]


def check(cond, what):
    COUNT[0] += 1
    if not cond:
        FAILS.append(what)
        print('FAIL', what, flush=True)


SOURCE = '''
# a made-up source segment
name = "src"
what = "made up: \\"quotes\\", a line\\nbreak and \u00e9"
area = "Fake_Area"
save = "fake-save"
boot = "continue"
wall = 1000
budget_seconds = 1000
max_decisions = 900
save_after = true
watch = ["B_Flag", "A_Flag"]

[[goal]]
name = "loop"
what = "walk a loop"
flag = "A_Flag=1"
kind = "reach"
targets = [{name = "p0", at = [0.0, 0.0], y = 1.5, kind = "reach", radius = 2},
           {name = "p1", at = [10.0, 0.0], kind = "reach", radius = 2},
           {name = "p2", at = [20.0, 0.0], kind = "reach", radius = 2},
           {name = "p3", at = [30.0, 0.0], kind = "reach", radius = 2},
           {name = "p4", at = [40.0, 0.0], kind = "reach", radius = 2},
           {name = "p5", at = [50.0, 0.0], kind = "reach", radius = 2},
           {name = "p6", at = [60.0, 0.0], kind = "reach", radius = 2},
           {name = "p7", at = [70.0, 0.0], kind = "reach", radius = 2}]

[[goal]]
name = "chest"
what = "open it"
flag = "B_Flag=1"
kind = "chest"
targets = [{name = "c", at = [5.0, 5.0], kind = "chest", radius = 0.6, approach = -90, front = [4.0, 5.0]}]
'''


def toml_checks(tmp):
    seg = tomllib.loads(SOURCE)
    again = tomllib.loads(mkcourse.dumps_segment(seg, 'a header\nsecond line'))
    check(again == seg, 'toml: a segment written back reads back equal (strings with quotes, newlines, accents; inline targets)')
    check(mkcourse.toml_value(True) == 'true' and mkcourse.toml_value([1, 'a']) == '[1, "a"]' and mkcourse.toml_value({'a': 1}) == '{a = 1}',
          'toml: values')
    try:
        mkcourse.toml_value(object())
        check(False, 'toml: an unknown type raises')
    except TypeError:
        check(True, 'toml: an unknown type raises')


def cut_checks(tmp):
    segs = tmp / 'segments'
    segs.mkdir()
    (segs / 'src.toml').write_text(SOURCE)
    e = course.Entry('t1', 'a test entry', 'src', {'loop': 3}, budget_s=40, max_decisions=25, save='other-save')
    s = mkcourse.cut(e, segs, None, 'bX')
    check(s['name'] == 'bX-t1' and s['budget_seconds'] == 40 and s['max_decisions'] == 25 and s['wall'] == e.wall_s and s['save'] == 'other-save'
          and s['save_after'] is False and s['area'] == 'Fake_Area' and s['boot'] == 'continue', 'cut: name, budget, wall, save, area, no save_after')
    check([g['name'] for g in s['goal']] == ['loop'] and [t['name'] for t in s['goal'][0]['targets']] == ['p0', 'p1', 'p2'], 'cut: the first 3 targets of one goal')
    check(s['watch'] == ['A_Flag', 'B_Flag'], 'cut: watch flags sorted')
    s = mkcourse.cut(course.Entry('t2', 'x', 'src', {'chest': None, 'loop': 2}), segs)
    check([g['name'] for g in s['goal']] == ['chest', 'loop'] and len(s['goal'][0]['targets']) == 1 and s['goal'][0]['targets'][0]['front'] == [4.0, 5.0],
          'cut: goals in the order the entry names them, all targets of one, keys like front kept')
    s = mkcourse.cut(course.Entry('t3', 'x', 'src', {}), segs)
    check([g['name'] for g in s['goal']] == ['loop', 'chest'], 'cut: no goals named: all of them')
    s = mkcourse.cut(course.Entry('t4', 'x', 'src', {'loop': 'hard'}), segs, [[41.0, 1.0], [69.0, -1.0], [500.0, 500.0]])
    check([t['name'] for t in s['goal'][0]['targets']] == ['p4', 'p7'], 'cut: hard: the targets nearest to the points, in route order, far points left out')
    s = mkcourse.cut(course.Entry('t5', 'x', 'src', {'loop': 'hard'}), segs, None)
    check([t['name'] for t in s['goal'][0]['targets']] == ['p6', 'p7'], 'cut: hard without points: the fallback slice')
    try:
        mkcourse.cut(course.Entry('t6', 'x', 'src', {'nope': 1}), segs)
        check(False, 'cut: an unknown goal raises')
    except KeyError:
        check(True, 'cut: an unknown goal raises')
    out = tmp / 'cut'
    saved = course.COURSE
    course.COURSE = [e, course.Entry('gone', 'x', 'no-such-source', {}),
                     course.Entry('fol', 'x', 'src', {'loop': 2}, follow='other', ghost_source='src', ghost_goal='loop', ghost_speed=3.0)]
    try:
        got = mkcourse.make(segs, out, None, 'bX')
    finally:
        course.COURSE = saved
    check(got['t1'].endswith('t1.toml') and got['gone'].startswith('missing:') and (out / 'fol.ghost.json').is_file(),
          'make: a path for a cut entry, `missing:` for a source that is not there, a ghost route for a follow entry')
    route = json.loads((out / 'fol.ghost.json').read_text())
    check(route['area'] == 'Fake_Area' and len(route['points']) == 8 and route['speed'] == 3.0 and route['y'][0] == 1.5, 'make: the ghost route is the goal\'s points')
    check(tomllib.loads((out / 't1.toml').read_text())['name'] == 'bX-t1', 'make: the file written is a valid segment')


def ghost_checks(tmp):
    pts = [[0, 0], [10, 0], [10, 10]]
    check(ghost.position_at(pts, 0, 5) == (0, 0, 0), 'ghost: at t = 0 at the first point')
    x, z, i = ghost.position_at(pts, 1, 5)
    check(abs(x - 5) < 1e-9 and z == 0 and i == 0, 'ghost: 1 s at 5 m/s is 5 m along the first leg')
    check(ghost.position_at(pts, 2.4, 5)[:2] == (10.0, 0.0) and ghost.position_at(pts, 2.4, 5)[2] == 1, 'ghost: it stands a second at the point reached')
    x, z, i = ghost.position_at(pts, 3.5, 5)
    check(abs(x - 10) < 1e-9 and abs(z - 2.5) < 1e-9 and i == 1, 'ghost: then runs the second leg')
    cycle = 2 + 1 + 2 + 1 + (200 ** 0.5) / 5 + 1
    check(ghost.position_at(pts, cycle + 1, 5)[:2] == ghost.position_at(pts, 1, 5)[:2], 'ghost: the route repeats, last point back to the first')
    check(ghost.position_at(pts, 1000, 5, loop=False)[:2] == (10.0, 10.0), 'ghost: without looping it stops at the last point')
    check(ghost.position_at([[3, 4]], 7, 5) == (3.0, 4.0, 0), 'ghost: a one-point route stands still')
    f = tmp / 'follow.json'
    ghost.write_follow(f, 1.234, 5.678, 'Fake_Area', y=2.0, now=100.0)
    check(json.loads(f.read_text()) == {'x': 1.23, 'z': 5.68, 'map': 'Fake_Area', 'w': 100.0, 'y': 2.0} and not (tmp / 'follow.json.tmp').exists(),
          'ghost: the follow file is whole JSON with x, z, map, w, y, no temporary left')

    class Clock:
        t = 0.0

        def __call__(self):
            return self.t
    clock, started = Clock(), [False]
    g = ghost.Ghost(f, {'points': pts, 'area': 'Fake_Area', 'speed': 5.0, 'y': [None, 3.0, None]}, start_when=lambda: started[0], clock=clock)
    g.tick()
    check(g.last == (0.0, 0.0) and json.loads(f.read_text())['x'] == 0.0, 'ghost: stands at the first point until the game is in play')
    clock.t = 50.0
    g.tick()
    check(g.last == (0.0, 0.0), 'ghost: time passing before the start moves nothing')
    started[0] = True
    g.tick()
    clock.t = 51.0
    g.tick()
    check(abs(g.last[0] - 5.0) < 1e-9, f'ghost: it moves from the moment the game is in play ({g.last})')
    clock.t = 52.4
    g.tick()
    check(json.loads(f.read_text())['y'] == 3.0 and g.last == (10.0, 0.0), 'ghost: the height of the point it stands at is written')
    rd = tmp / 'prun'
    (rd / 'live').mkdir(parents=True)
    check(not ghost.gameplay_started(rd), 'ghost: no gameplay event yet')
    (rd / 'live' / 'out.jsonl').write_text('{"ev": "note"}\n{"ev": "gameplay", "n": 3}\n')
    check(ghost.gameplay_started(rd), 'ghost: the gameplay event starts it')
    t = ghost.Ghost(f, {'points': pts, 'area': 'A', 'speed': 5.0}, hz=50)
    t.start()
    time.sleep(0.15)
    t.stop()
    check(not t.is_alive() and t.last is not None, 'ghost: the thread writes and stops')


def plan_checks(tmp):
    segs, pdir = tmp / 'psegs', tmp / 'pilotdir'
    segs.mkdir()
    (pdir / 'routes').mkdir(parents=True)
    ents = [course.Entry('a', 'x', 's', {}), course.Entry('b', 'x', 's', {}, save='kept:run1', tas='r.txt'),
            course.Entry('c', 'x', 's', {}, follow='other')]
    saved = course.COURSE
    course.COURSE = ents
    try:
        (segs / 'a.toml').write_text('x')
        (segs / 'b.toml').write_text('x')
        (segs / 'c.toml').write_text('x')
        cells = run.plan(None, ['rules', 'decisions'], segs, pdir, None, tas=True)
        by = {(c['entry'], c['arm']): c for c in cells}
        check(len(cells) == 7 and not by[('a', 'rules')]['missing'], 'plan: a cell per entry and arm, plus a tas cell where an entry has a route')
        check(any('kept save' in w for w in by[('b', 'rules')]['missing']) and any('no route r.txt' in w for w in by[('b', 'tas')]['missing']),
              'plan: a kept save without --kept-root and a missing route are named')
        check(any('ghost' in w for w in by[('c', 'rules')]['missing']), 'plan: a follow entry without its ghost route is missing')
        (segs / 'c.ghost.json').write_text('{}')
        (pdir / 'routes' / 'r.txt').write_text('x')
        kept = tmp / 'kept'
        (kept / 'runs' / 'run1' / 'user').mkdir(parents=True)
        cells = run.plan({'b', 'c'}, ['rules'], segs, pdir, kept, tas=True)
        check(all(not c['missing'] for c in cells) and {c['entry'] for c in cells} == {'b', 'c'} and len(cells) == 3, 'plan: all there: nothing missing; --entries narrows it')
        check(run.resolve_save(ents[1], kept) == (str(kept / 'runs' / 'run1' / 'user'), None), 'resolve_save: kept:<tag> under --kept-root')
        check(run.resolve_save(ents[0], None) == (None, None), 'resolve_save: no save, none asked')
        only = run.parse_only('c:rules,b:tas,a:decisions', {'a', 'b', 'c'})
        check(only == [('c', 'rules'), ('b', 'tas'), ('a', 'decisions')], 'parse_only: entry:arm pairs, in the order given')
        cells = run.plan(None, ['rules', 'decisions'], segs, pdir, kept, tas=True, only=only)
        check([(c['entry'], c['arm']) for c in cells] == only and all(not c['missing'] for c in cells),
              'plan: --only picks single cells (the scripted baseline as `entry:tas`), in the order given')
        for bad in ('a', 'a:nosucharm', 'zz:rules', 'a:rules,a:rules', ''):
            try:
                run.parse_only(bad, {'a', 'b', 'c'})
                check(False, f'parse_only refuses {bad!r}')
            except ValueError:
                check(True, f'parse_only refuses {bad!r}')
    finally:
        course.COURSE = saved


def args_checks():
    e = course.entry('follow')
    seg = Path('/x/follow.toml')
    a, env = run.pilot_args(e, 'rules', 'T', '/c', seg, None, '/f.json', 900, 60)
    check(a[:2] == ['run', str(seg)] and a[a.index('--decider') + 1] == 'rules' and '--planner' not in a and '--vision' not in a and not env,
          'args: rules: no planner, no vision')
    check(a[a.index('--tag') + 1] == 'T' and a[a.index('--copy') + 1] == '/c' and a[a.index('--wall') + 1] == str(e.wall_s) and
          a[a.index('--max-decisions') + 1] == str(e.max_decisions) and a[a.index('--shots') + 1] == '900' and a[a.index('--follow') + 1] == 'other=/f.json',
          'args: tag, copy, wall, decision limit, shots, the ghost\'s follow file')
    a, env = run.pilot_args(course.entry('walk'), 'decisions', 'T', '/c', seg, '/save/dir', None, 0, 60)
    check(a[a.index('--decider') + 1] == 'openai-decisions' and '--planner' in a and '--vision' not in a and a[a.index('--save') + 1] == '/save/dir' and
          '--shots' not in a and '--follow' not in a, 'args: decisions: the model and the planner, a save, no shots when 0')
    a, env = run.pilot_args(course.entry('walk'), 'decisions+vision', 'T', '/c', seg, None, None, 900, 45)
    check(a[a.index('--vision') + 1] == 'on' and a[a.index('--vision-every') + 1] == '45' and a[a.index('--vision-backend') + 1] == 'decisions' and
          '--vision-model' not in a and not env, 'args: decisions+vision: the eyes on the cheap backend')
    a, env = run.pilot_args(course.entry('walk'), 'decisions+vision-big', 'T', '/c', seg, None, None, 900, 60)
    check(a[a.index('--vision-backend') + 1] == 'responses' and a[a.index('--vision-model') + 1] == 'gpt-6-astra' and env == {'PILOT_PLANNER_MODEL': 'gpt-6-astra'},
          'args: the big arm: the flagship for pictures (responses) and, by environment, for the planner')
    check(all(a in course.ARMS for a in course.DEFAULT_ARMS) and course.entry('door-talk').tas and course.entry('follow').follow == 'other',
          'course: the default arms exist, the door entry has a scripted baseline, the follow entry a ghost')
    check({e.kind.split(':')[0].split(' ')[0] for e in course.COURSE} >= {'walking', 'interaction', 'follow', 'a'}, 'course: walking, interactions, a follow and a fight/hard route are in it')
    check(all(e.wall_s >= e.boot_s + e.budget_s for e in course.COURSE), 'course: every wall limit covers the boot and the budget')


def family_checks():
    tag = f'bench-test-tag-{os.getpid()}'
    p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)', '--tag', tag], start_new_session=True)
    q = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)', '--tag', tag + '2'], start_new_session=True)
    time.sleep(0.3)
    check(p.pid in run.family(tag) and q.pid not in run.family(tag), 'family: the processes that name the tag as a whole word, not a longer tag')
    n = run.stop_family(tag, wait_s=3)
    p.wait(timeout=10)
    check(n == 1 and p.returncode is not None and q.poll() is None, 'family: stopped by pid, the other left alone')
    q.terminate()
    q.wait(timeout=10)
    stubborn = subprocess.Popen([sys.executable, '-c', 'import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)', '--tag', tag + '3'],
                                start_new_session=True)
    time.sleep(0.4)
    run.stop_family(tag + '3', wait_s=1)
    stubborn.wait(timeout=10)
    check(stubborn.returncode == -9, 'family: a process that ignores SIGTERM gets SIGKILL')


FAKE_PILOT = r'''
import json, os, sys, time
from pathlib import Path
here = Path(__file__).resolve().parent
a = sys.argv[1:]
def opt(name, default=None):
    return a[a.index(name) + 1] if name in a else default
if a[0] == 'check-route':
    tag = opt('--tag') + '-1'
    d = here / 'runs' / 'checks' / tag
    d.mkdir(parents=True)
    ev = [{'ev': 'step', 'src': 'run 1 1 radius 1', 'result': 'reached', 'secs': 5.0, 'moved': 30.0, 't': 6.0},
          {'ev': 'step', 'src': 'until flag Door_Open=1 timeout 10', 'result': 'met', 'secs': 1.0, 'moved': 0.0, 't': 8.0}]
    (d / 'out.jsonl').write_text('\n'.join(json.dumps(e) for e in ev) + '\n')
    sys.exit(0)
tag = opt('--tag')
if os.environ.get('FAKE_HANG'):
    time.sleep(600)
d = here / 'runs' / tag
d.mkdir(parents=True)
(d / 'argv.json').write_text(json.dumps({'argv': a, 'env': {k: v for k, v in os.environ.items() if k.startswith('PILOT_')}}))
time.sleep(float(os.environ.get('FAKE_SECS', '0.3')))
rows = []
cost = 0.0 if opt('--decider') == 'rules' else 0.002
for n in range(1, 4):
    rows.append({'kind': 'decision', 'n': n, 'state': {'t': n * 5.0, 'life': 24}, 'goal': 'g', 'target': 't', 'decider': opt('--decider'),
                 'choice': 'go', 'cost_usd': cost, 'wall': 100.0 + n * 3})
    rows.append({'kind': 'result', 'n': n, 'result': 'reached', 'moved': 10.0, 'steps': [{'ev': 'step', 'src': 'run 1 1', 'result': 'reached',
                 'secs': 2.0, 'moved': 10.0, 't': n * 5.0 + 2}], 'wall': 101.0 + n * 3})
rows.append({'kind': 'goal', 'goal': 'g', 'status': 'met', 't': 15.0, 'wall': 112.0})
(d / 'transcript.jsonl').write_text('\n'.join(json.dumps(r) for r in rows) + '\n')
(d / 'summary.json').write_text(json.dumps({'run': tag, 'segment': 's', 'decider': opt('--decider'), 'outcome': 'solved', 'play_wall_s': 30.0}))
if opt('--vision') == 'on':
    (d / 'vision').mkdir()
    (d / 'vision' / 'vision.jsonl').write_text(json.dumps({'seq': 1, 'n': 1, 'why': ['first'], 'backend': 'decisions', 'model': 'm', 'cost_usd': 0.0003,
                                                          'latency_ms': 300, 'extra': [], 'oddities': []}) + '\n')
'''


def play_checks(tmp):
    pdir = tmp / 'fakepilot'
    (pdir / 'routes').mkdir(parents=True)
    (pdir / 'pilot.py').write_text(FAKE_PILOT)
    (pdir / 'routes' / 'r.txt').write_text('x')
    segs = tmp / 'play-segs'
    segs.mkdir()
    ents = [course.Entry('e1', 'x', 's', {}, budget_s=1, boot_s=0, tas='r.txt'), course.Entry('e2', 'x', 's', {}, budget_s=1, boot_s=0),
            course.Entry('e3', 'x', 's', {}, budget_s=1, boot_s=0, follow='other')]
    for e in ents:
        (segs / f'{e.id}.toml').write_text('name = "s"\narea = "A"\n[[goal]]\nname = "g"\nflag = "Door_Open=1"\nkind = "reach"\ntargets = []\n')
    (segs / 'e3.ghost.json').write_text(json.dumps({'area': 'A', 'points': [[0, 0], [10, 0]], 'speed': 5.0}))
    saved = course.COURSE
    course.COURSE = ents
    try:
        out = tmp / 'out'
        a = Namespace(out=str(out), bench_id='bt', pilot_dir=str(pdir), segments_dir=str(segs), copies='/copyA,/copyB', hold_s=600.0, kept_root=None,
                      shots=900, entries=None, arms='rules,decisions+vision-big')
        cells = run.plan(None, ['rules', 'decisions+vision-big'], segs, pdir, None, tas=True)
        r = run.Runner(a)
        deferred = r.play(cells)
        recs = {p.stem: json.loads(p.read_text()) for p in (out / 'cells').glob('bt-*.json') if '.follow' not in p.name}
        check(len(recs) == 7 and not deferred and all(v.get('rc') == 0 for v in recs.values()), f'play: seven cells (6 plays and 1 tas), all exit 0 ({sorted(recs)})')
        check({v['copy'] for v in recs.values()} <= {'/copyA', '/copyB'} and len({v['copy'] for v in recs.values()}) == 2, 'play: two copies, both used (a pair)')
        argv = json.loads((pdir / 'runs' / 'bt-e1-decisions_vision-big' / 'argv.json').read_text())
        check(argv['env'].get('PILOT_PLANNER_MODEL') == 'gpt-6-astra' and '--vision' in argv['argv'] and '--planner' in argv['argv'],
              'play: the big arm\'s flags and environment reached the pilot')
        rules_argv = json.loads((pdir / 'runs' / 'bt-e1-rules' / 'argv.json').read_text())
        check('--planner' not in rules_argv['argv'] and 'PILOT_PLANNER_MODEL' not in rules_argv['env'], 'play: the rules arm got neither planner nor vision')
        e3 = json.loads((pdir / 'runs' / 'bt-e3-rules' / 'argv.json').read_text())['argv']
        check(e3[e3.index('--follow') + 1].startswith('other=') and e3[e3.index('--follow') + 1].endswith('bt-e3-rules.follow.json'), 'play: a follow entry gets its ghost\'s file')
        follow = json.loads((out / 'cells' / 'bt-e3-rules.follow.json').read_text())
        check(follow['map'] == 'A' and 'x' in follow, 'play: the ghost wrote its follow file')
        # a second play resumes: nothing runs again
        n_before = {p.name: p.stat().st_mtime for p in (out / 'cells').glob('bt-*.json')}
        r2 = run.Runner(a)
        r2.play(cells)
        check({p.name: p.stat().st_mtime for p in (out / 'cells').glob('bt-*.json')} == n_before, 'play: cells already done are not run again')
        # the report
        a_rep = Namespace(out=str(out), segments_dir=str(segs))
        run.report(a_rep)
        table = (out / 'table.md').read_text()
        res = json.loads((out / 'results.json').read_text())
        check(len(res['cells']) == 7 and not res['no_data'], 'report: metrics for all seven cells')
        check('| e1 | rules |' in table and '| e1 | tas |' in table and '| rules | 3 |' in table and '| tas | 1 |' in table, f'report: a row per entry and arm, a row per arm\n{table}')
        arms = {m['arm'] for m in (c['metrics'] for c in res['cells'])}
        check(arms == {'rules', 'decisions+vision-big', 'tas'}, f'report: the arms named by the benchmark ({arms})')
        rules = [c['metrics'] for c in res['cells'] if c['metrics']['arm'] == 'rules']
        check(all(m['cost']['total_usd'] == 0.0 and m['session']['goals_met'] == 1 for m in rules), 'report: rules cost nothing and met their goal')
        big = [c['metrics'] for c in res['cells'] if c['metrics']['arm'] == 'decisions+vision-big']
        check(all(abs(m["cost"]["total_usd"] - 0.0063) < 1e-9 and m['vision']['calls'] == 1 for m in big), 'report: the big arm\'s cost includes decisions and the look')
        tas = [c['metrics'] for c in res['cells'] if c['metrics']['arm'] == 'tas']
        check(tas and tas[0]['goals']['g']['status'] == 'met' and tas[0]['session']['distance_m'] == 30.0, 'report: the scripted baseline from its events')
        # the hold's time: a cell that cannot finish inside it is deferred, not started
        out2 = tmp / 'out2'
        a2 = Namespace(**dict(vars(a), out=str(out2), hold_s=5.0, bench_id='bu'))
        deferred = run.Runner(a2).play(run.plan(None, ['rules'], segs, pdir, None))
        check(len(deferred) == 3 and not list((out2 / 'cells').glob('bu-*.json')), f'play: nothing starts when the hold is too short ({deferred})')
        # a pilot that hangs is stopped at its wall plus the grace, by pid, and the cell says so
        out3 = tmp / 'out3'
        a3 = Namespace(**dict(vars(a), out=str(out3), bench_id='bv', copies='/copyA'))
        os.environ['FAKE_HANG'] = '1'
        course.COURSE = [course.Entry('hang', 'x', 's', {}, budget_s=1, boot_s=0)]
        (segs / 'hang.toml').write_text((segs / 'e1.toml').read_text())
        try:
            rr = run.Runner(a3)
            rr.grace_s = 2 - course.COURSE[0].wall_s
            t0 = time.time()
            rr.play(run.plan(None, ['rules'], segs, pdir, None))
            rec = json.loads((out3 / 'cells' / 'bv-hang-rules.json').read_text())
            check(rec['rc'] == 'timeout' and time.time() - t0 < 30, f"play: a pilot that hangs is stopped at its limit and the cell says so ({rec.get('rc')})")
            check(not run.family('bv-hang-rules'), 'play: nothing of the cell is left running')
        finally:
            os.environ.pop('FAKE_HANG', None)
        # the hold ends (SIGTERM to the runner): the running cell's pilot and its family are stopped, the cell leaves no record
        out4 = tmp / 'out4'
        env = dict(os.environ, FAKE_HANG='1')
        course.COURSE = [course.Entry('sig', 'x', 's', {}, budget_s=1, boot_s=0)]
        (segs / 'sig.toml').write_text((segs / 'e1.toml').read_text())
        driver = tmp / 'drive.py'
        driver.write_text(f"import sys\nsys.path.insert(0, {str(HERE)!r})\nimport course, run\nfrom argparse import Namespace\n"
                          f"course.COURSE = [course.Entry('sig', 'x', 's', {{}}, budget_s=1, boot_s=0)]\n"
                          f"a = Namespace(out={str(out4)!r}, bench_id='bw', pilot_dir={str(pdir)!r}, segments_dir={str(segs)!r}, copies='/copyA', hold_s=600.0,\n"
                          f"              kept_root=None, shots=0)\nr = run.Runner(a)\nr.play(run.plan(None, ['rules'], a.segments_dir, a.pilot_dir, None))\n")
        p = subprocess.Popen([sys.executable, '-I', '-B', str(driver)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for _ in range(100):
            if run.family('bw-sig-rules'):
                break
            time.sleep(0.1)
        check(bool(run.family('bw-sig-rules')), 'signal: the cell\'s pilot is running')
        p.terminate()
        out, _ = p.communicate(timeout=60)
        check(p.returncode == 128 + 15 and not run.family('bw-sig-rules') and not (out4 / 'cells' / 'bw-sig-rules.json').exists(),
              f'signal: SIGTERM to the runner stops the cell\'s processes by pid and leaves no record ({p.returncode}, {out.strip()[-80:]})')
    finally:
        course.COURSE = saved


def local_checks(tmp):
    """The course in the published tree names no segment, save, goal or route of anyone's game: generic placeholders; the real names come from a
    private file (course-local.json, or PILOT_BENCH_LOCAL) that overrides fields entry by entry."""
    pub = course.PUBLIC
    check([e.id for e in pub] == ['walk', 'door-talk', 'follow', 'hard', 'chest', 'fight'] and all(e.source.endswith('-source') for e in pub),
          'local: the public course has the six entries and placeholder sources')
    text = repr([vars(e) for e in pub]).lower()
    check(not any(w in text for w in ('kokiri', 'hyrule', 'forest', 'ex17', 'house', 'deku', 'field')), 'local: no place, save or segment name of a real game in the public course')
    check(course.load(tmp / 'absent.json') == pub, 'local: no private file: the public course')
    f = tmp / 'course-local.json'
    f.write_text(json.dumps({'walk': {'source': 'mine', 'goals': {'g': 6}, 'save': 'my-save'}, 'follow': {'ghost_source': 'other', 'ghost_goal': 'r1'},
                             'door-talk': {'tas': 'r.txt'}}))
    got = {e.id: e for e in course.load(f)}
    check((got['walk'].source, got['walk'].goals, got['walk'].save) == ('mine', {'g': 6}, 'my-save') and got['walk'].budget_s == 50 and got['follow'].ghost_source == 'other'
          and got['follow'].ghost_goal == 'r1' and got['door-talk'].tas == 'r.txt' and got['chest'] == [e for e in pub if e.id == 'chest'][0],
          'local: the private file overrides source, goals, save, ghost and route per entry and nothing else')
    check(course.PUBLIC[0].source.endswith('-source'), 'local: loading does not change the public course')
    for bad in ({'nope': {'source': 'x'}}, {'walk': {'budget_s': 1}}, {'walk': 'x'}, [1]):
        f.write_text(json.dumps(bad))
        try:
            course.load(f)
            check(False, f'local: {bad} is refused')
        except ValueError:
            check(True, f'local: {bad} is refused')
    f.write_text('{not json')
    try:
        course.load(f)
        check(False, 'local: a file that is no JSON is refused')
    except ValueError:
        check(True, 'local: a file that is no JSON is refused')


def main():
    with tempfile.TemporaryDirectory(prefix='bench-test-') as t:
        tmp = Path(t)
        local_checks(tmp)
        toml_checks(tmp)
        cut_checks(tmp)
        ghost_checks(tmp)
        plan_checks(tmp)
        args_checks()
        family_checks()
        play_checks(tmp)
    if FAILS:
        raise SystemExit(f'test_bench: {len(FAILS)} of {COUNT[0]} checks FAILED')
    print(f'test_bench: all passed ({COUNT[0]} checks)')


if __name__ == '__main__':
    main()
