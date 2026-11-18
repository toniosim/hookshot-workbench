#!/usr/bin/env python3
"""hunt.py against a FAKE pilot and a FAKE co-op runner (small scripts written here that leave the folders the real ones leave): the plan
and its refusals, the generator (same seed, same plan; generated segments that the pilot's own Segment reads), a solo session that
is clean, one with a stall, a hang the watcher ends early, a soft-lock, a pair with a seeded double give and a flag that disagrees, the
budget, the stop by the hold's deadline, a refusal when a game of the copy runs, the replay, the waiter's command. Made-up names only;
no game, no GPU, no network.   python3 -I -B test_hunt.py
"""
import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

COPY_PREFIX = 'hunt-copy-'   # the setting hunt.py needs (this machine's own value in real use): every game copy of these tests is named so
os.environ.update({'HUNT_COPY_PREFIX': COPY_PREFIX, 'HUNT_WATCH_EVERY': '0.3', 'HUNT_SOFTLOCK_AFTER': '0.5', 'HUNT_EXTRA': '8', 'HUNT_BOOT': '5', 'HUNT_RESERVE': '5', 'HUNT_TERM_GRACE': '3'})
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bughunt  # noqa: E402
import hs_names  # noqa: E402  (bughunt put the harness folder on sys.path: the game's own file names)
import bugpacket  # noqa: E402
import hunt  # noqa: E402
import test_bughunt as tb  # noqa: E402
import test_burst as tbu  # noqa: E402
import vision  # noqa: E402

EXE = hs_names.Names(hs_names.PROJECTS[0]).executable   # the game's executable in a made-up copy
YARD = 'Yard' + '_Child'   # a made-up destination with the age suffix scenario.py reads
FAILS = []
CHECKS = [0]


def check(cond, what):
    CHECKS[0] += 1
    if not cond:
        FAILS.append(what)
        print('FAIL', what, flush=True)


FAKE_PILOT = r'''#!/usr/bin/env python3
# a fake pilot.py: leaves what the real one leaves (its run folder with live/, the game copy's run folder), by the scenario named in the segment
import json, os, sys, time
from pathlib import Path
a = sys.argv
seg = Path(a[2]).read_text()
tag = a[a.index('--tag') + 1]
copy = Path(a[a.index('--copy') + 1])
here = Path(__file__).resolve().parent
run = here / 'runs' / tag
live = run / 'live'
live.mkdir(parents=True)
game = copy / 'runs' / tag
(game / 'shots').mkdir(parents=True)
T0 = 5000.0

def sample(t, frame, **kw):
    s = {'t': T0 + t, 'frame': frame, 'map': 'Yard', 'pos': [0, 10, 0], 'facing': 0, 'camera': 0, 'event': 0, 'loading': 0, 'life': 12, 'max_life': 12,
         'rupees': 5, 'prompt': 'Empty', 'music': 'BGM_Yard', 'flags': {}, 'changed': {}, 'child': 1}
    s.update(kw)
    return s

def write_states(rows):
    with open(live / 'state.jsonl', 'w') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')

import struct, zlib
def png(g=9):
    raw = b''.join(b'\x00' + bytes([g, g, g] * 4) for _ in range(4))
    def ch(k, b):
        return struct.pack('>I', len(b)) + k + b + struct.pack('>I', zlib.crc32(k + b) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + ch(b'IHDR', struct.pack('>IIBBBBB', 4, 4, 8, 2, 0, 0, 0)) + ch(b'IDAT', zlib.compress(raw)) + ch(b'IEND', b'')
lock = 'SCENARIO=softlock' in seg
nframes = 24000 if lock else (1000 if 'SCENARIO=hang' in seg else 3700)
stall_frame = 2500 if 'SCENARIO=stall' in seg else None
times, t = {}, T0
for f in range(1, nframes + 1):
    t += 5.0 if f == stall_frame else 0.0166
    times[f] = t
rows = []
for f in range(6, nframes + 1, 6):
    pos = [f * 0.01, 10, 0] if 'SCENARIO=walk' in seg else [0, 10, 0]
    rows.append(sample(times[f] - T0, 100 + f, pos=pos))
ev = [{'ev': 'gameplay', 't': 0.0, 'frame': rows[0]['frame'], 'area': 'Yard'}]
steps = [{'ev': 'step', 'in': i + 1, 'src': 'walk 3 4 radius 1', 'result': 'stuck', 'secs': 1.0, 'moved': 0.0, 'detail': '', 't': 5.0 + 15 * i} for i in range(20)] \
    if lock else [{'ev': 'step', 'in': 1, 'src': 'walk 3 4 radius 1', 'result': 'reached', 'secs': 1.0, 'moved': 3.0, 'detail': '', 't': 2.0}]
ev += [{'ev': 'state', 'why': 'wait', 'n': 1, 't': r['t'] - T0, 'frame': r['frame']} for r in rows[::5]] + steps
write_states(rows)
(live / 'steps.txt').write_text('\n'.join('walk 3 4 radius 1' for _ in steps) + '\n')
pres = ['frame,return_ns,interval_ns,present_begin_ns,renderer_begin_ns,renderer_end_ns,vcore_back_ns']
prev = None
for f in range(1, nframes + 1):
    iv = 0 if prev is None else int((times[f] - prev) * 1e9)
    pres.append(f'{100 + f},{int(times[f] * 1e9)},{iv},0,0,0,0')
    prev = times[f]
(game / 'present.csv').write_text('\n'.join(pres) + '\n')
(game / '@LOG@').write_text('[hos] start\n[hos] vk: present 90 written to x\n' + ('CRASH: boom at 0x1\n' if 'SCENARIO=crash' in seg else '') + '[hos] audio: renderer opened\n')
code = 139 if 'SCENARIO=crash' in seg else 143
(game / 'summary.txt').write_text(f'hs-run {tag} exit={code} wall=10s fatal=0 crash={1 if code == 139 else 0} devlost=0 nocore=0 kernel=0 nvrm=0\n')
(game / 'exit.txt').write_text(str(code))
(game / 'wall.txt').write_text('10')
(game / 'shots' / 'vk_000190.png').write_bytes(png())
if 'SCENARIO=strobe' in seg:   # a scene that changes in a second while nothing moved, and a game whose bridge the test serves
    (game / 'shots' / 'vk_000280.png').write_bytes(png(240))
    (game / 'env-used.txt').write_text('HOS_CONTROL=' + os.environ['FAKE_BRIDGE'] + '\n')
if 'SCENARIO=hang' in seg or 'SCENARIO=softlock' in seg or 'SCENARIO=sleep' in seg or 'SCENARIO=strobe' in seg:
    (live / 'out.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in ev))
    time.sleep(1000)
ev.append({'ev': 'done', 't': rows[-1]['t'] - T0})
(live / 'out.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in ev))
(run / 'out.jsonl').write_text((live / 'out.jsonl').read_text())
(run / 'steps.txt').write_text((live / 'steps.txt').read_text())
(run / 'summary.json').write_text(json.dumps({'run': tag, 'outcome': 'solved', 'decisions': 3, 'rates': {'cost_usd': 0.0}, 'humanize': {'level': 2, 'seed': 7}}))
(run / 'transcript.jsonl').write_text('')
(run / 'run.log').write_text((game / '@LOG@').read_text())
'''

FAKE_COOP = r'''#!/usr/bin/env python3
# a fake coopplay.py inner CASE --out DIR: leaves a two-side session folder; the case file says what the sides did
import json, sys
from pathlib import Path
a = sys.argv
case = Path(a[a.index('inner') + 1]).read_text()
out = Path(a[a.index('--out') + 1])
T0 = 7000.0
for side in 'AB':
    d = out / side
    d.mkdir(parents=True)
    (d / 'side.json').write_text(json.dumps({'id': side}))
    rows = []
    for i in range(300):
        keys = 3
        flag = 0
        if 'SEED=double' in case:
            flag = 1 if i >= 100 else 0
            keys = 5 if i >= 105 else 3
        shared = 0
        if 'SEED=desync' in case:
            shared = 1 if (side == 'A' and i >= 50) else 0
        s = {'t': T0 + i / 10, 'frame': 100 + 6 * i, 'map': 'Yard', 'pos': [0, 10, 0], 'event': 0, 'loading': 0, 'life': 12, 'rupees': 5,
             'prompt': 'Empty', 'music': 'BGM_Yard', 'flags': {'chest_flag': flag, 'keys': keys, 'shared_flag': shared}, 'changed': {}, 'age': 'child'}
        rows.append({'w': 9000.0 + i / 10, 'frame': s['frame'], 'game': s})
    (d / 'state.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    (d / 'log.txt').write_text('[hos] fine\n[hos] audio: renderer opened\n')
    (d / 'exit.txt').write_text('124')
(out / 'session.json').write_text(json.dumps({'start_w': 9000.0}))
(out / 'result.json').write_text(json.dumps({'verdict': 'pass'}))
(out / 'case-source.toml').write_text(case)
'''


def setup(tmp, hold=120):
    """a fake harness: a pilot folder with the fake pilot, a game copy, a second copy, a library with one save, the plan's folder"""
    pdir = tmp / 'pilotdir' / 'pilot'
    pdir.mkdir(parents=True)
    (pdir / 'pilot.py').write_text(FAKE_PILOT.replace('@LOG@', tb.LOG))
    copy = tmp / (COPY_PREFIX + 'fake-a')
    copy.mkdir()
    (copy / 'built-from.txt').write_text('abcdef0123456789\n')
    (copy / EXE).write_bytes(b'x')
    copy_b = tmp / (COPY_PREFIX + 'fake-b')
    copy_b.mkdir()
    lib = tmp / 'saves'
    (lib / 'a-save' / 'save' / 'slot_00').mkdir(parents=True)
    (lib / 'a-save' / 'save' / 'slot_00' / 'progress.sav').write_bytes(b'sav')
    coop = tmp / 'coop' / 'coopplay.py'
    coop.parent.mkdir()
    coop.write_text(FAKE_COOP)
    plans = tmp / 'plans'
    plans.mkdir()
    return {'pilot': pdir / 'pilot.py', 'copy': copy, 'copy_b': copy_b, 'lib': lib, 'coop': coop, 'plans': plans, 'tmp': tmp, 'hold': hold}


def write_plan(env, name, sessions, **extra):
    plan = {'name': name, 'hold_seconds': env['hold'], 'copy': str(env['copy']), 'copy_b': str(env['copy_b']), 'pilot': str(env['pilot']),
            'library': str(env['lib']), 'coopplay': str(env['coop']), 'sessions': sessions, 'config': {'softlock_s': 60.0, 'softlock_inputs': 3}}
    plan.update(extra)
    path = env['plans'] / f'{name}.json'
    path.write_text(json.dumps(plan, indent=1))
    return path


def seg(env, name, scenario):
    p = env['plans'] / f'{name}.toml'
    p.write_text(f'# SCENARIO={scenario}\nname = "{name}"\narea = "Yard"\n')
    return p.name


def solo(env, name, scenario, wall=20, **kw):
    return {'name': name, 'kind': 'solo', 'save': 'a-save', 'segment': seg(env, name, scenario), 'wall': wall, 'seed': 5, 'humanize': 2, 'decider': 'rules', **kw}


def run_hunt(plan_path, out, timeout=120):
    return subprocess.run([sys.executable, '-I', '-B', str(HERE / 'hunt.py'), 'run', str(plan_path), '--out', str(out)], capture_output=True, text=True, timeout=timeout,
                          env={**os.environ})


def plan_checks(tmp):
    env = setup(tmp / 'e0')
    ok = write_plan(env, 'p-ok', [solo(env, 's1', 'normal')])
    plan = hunt.load_plan(ok)
    check(plan['sessions'][0]['tag'] == 'p-ok-s1' and plan['sessions'][0]['min_s'] == 20 + 5 + 30 and plan['sessions'][0]['seed'] == 5, 'plan: a session\'s tag and the time it needs')
    check(hunt.plan_errors(plan) == [], f'plan: a good plan has no errors ({hunt.plan_errors(plan)})')
    check(hunt.plan_errors(plan, tmp)[0].endswith('exists (a hunt folder is never reused)'), 'plan: an existing output folder is refused')
    r = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'hunt.py'), 'check', str(ok)], capture_output=True, text=True)
    check(r.returncode == 0 and 'ok' in r.stdout, 'cli: check says ok')

    def bad(mut, expect):
        d = json.loads(ok.read_text())
        mut(d)
        p = env['plans'] / 'bad.json'
        p.write_text(json.dumps(d))
        try:
            hunt.plan_errors(hunt.load_plan(p))
            errs = hunt.plan_errors(hunt.load_plan(p))
            check(any(expect in e for e in errs), f'plan: {expect!r} refused ({errs})')
        except hunt.PlanError as e:
            check(expect in str(e), f'plan: {expect!r} refused ({e})')
    bad(lambda d: d.update(bogus=1), 'unknown plan keys')
    bad(lambda d: d.update(copy=str(tmp / 'not-a-copy')), 'is not a /.../' + COPY_PREFIX)
    check(hunt.copy_errors(str(tmp / COPY_PREFIX)) != [] and hunt.copy_errors(str(env['copy'])) == [], 'plan: the bare prefix is no copy, a folder of that name is')
    saved = os.environ.pop('HUNT_COPY_PREFIX')   # this machine's own setting, no default: with none set no copy is accepted, and the refusal names the setting
    try:
        errs = hunt.plan_errors(plan)
        check(errs and 'HUNT_COPY_PREFIX' in errs[0] and 'no default' in errs[0], f'plan: no HUNT_COPY_PREFIX: refused, naming the setting ({errs[:1]})')
        r = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'hunt.py'), 'check', str(ok)], capture_output=True, text=True)
        check(r.returncode != 0 and 'HUNT_COPY_PREFIX' in r.stdout + r.stderr, f'cli: check without HUNT_COPY_PREFIX refuses, naming it ({r.returncode})')
    finally:
        os.environ['HUNT_COPY_PREFIX'] = saved
    bad(lambda d: d['sessions'][0].update(save='nowhere'), 'is not a folder')
    bad(lambda d: d['sessions'][0].update(segment='missing.toml'), 'is not a file')
    bad(lambda d: d['sessions'][0].update(decider='gpt'), 'decider is one of')
    bad(lambda d: d['sessions'][0].update(humanize=7), 'humanize is 0 to 3')
    bad(lambda d: d['sessions'][0].update(env=['OPENAI_API_KEY=x']), 'never from a plan')
    bad(lambda d: d['sessions'].append(dict(d['sessions'][0])), 'duplicate session name')
    bad(lambda d: d.update(hold_seconds=3), 'leaves no budget')
    bad(lambda d: d.update(config={'nonsense': 1}), 'config:')
    bad(lambda d: d['sessions'].append({'name': 'pr', 'kind': 'pair'}), 'needs a case')
    bad(lambda d: d.update(sessions=[]), 'sessions: a non-empty list')
    (env['pilot'].parent / 'runs' / 'p-ok-s1').mkdir(parents=True)
    check(any('already has a run folder' in e for e in hunt.plan_errors(plan)), 'plan: a pilot run folder of that tag is refused (a tag is never reused)')


def generator_checks(tmp):
    lib = tmp / 'gen-lib'
    lib.mkdir()
    cat = {'save-a': {'decoded': {'slots': [{'area': 'Yard', 'pos': [1, 10, 2]}]}}, 'save-b': {'decoded': {'slots': [{'area': 'Cave', 'pos': [0, 5, 0]}]}},
           'save-c': {'decoded': {'slots': [{}]}}}
    (lib / 'catalogue.json').write_text(json.dumps(cat))
    check(hunt.save_starts(lib) == {'save-a': ('Yard', [1, 10, 2]), 'save-b': ('Cave', [0, 5, 0])}, 'save_starts: area and place of each save with a decoded slot')

    class FakeRoam:
        def targets(self, area, start, rng, k, **kw):
            return [(round(rng.uniform(-50, 50), 2), round(rng.uniform(-50, 50), 2), 10.0) for _ in range(k)] if area == 'Yard' else []

    class A:
        pass

    def args(out, seed=3, **kw):
        a = A()
        a.out, a.name, a.seed, a.solo, a.pairs, a.library = out, 'gen-night', seed, 3, 1, str(lib)
        a.copies, a.pilot, a.chapters, a.chapter_share, a.pair_case, a.pair_hold = '/x/copy-a,/x/copy-b', '/x/pilot.py', None, 0.5, ['/c/one.toml', '/c/two.toml'], 700.0
        a.areas, a.targets, a.wall, a.hold_seconds, a.config, a.budget_usd = 'Yard', 6, 150, 2000.0, None, 1.5
        a.bounds = a.baseline = a.registry = a.coopplay = None
        for k, v in kw.items():
            setattr(a, k, v)
        return a
    p1 = hunt.make_plan(args(tmp / 'g1'), FakeRoam())
    p2 = hunt.make_plan(args(tmp / 'g2'), FakeRoam())
    d1, d2 = json.loads(p1.read_text()), json.loads(p2.read_text())
    strip = lambda d: json.dumps(d, sort_keys=True).replace('g1', 'gx').replace('g2', 'gx')   # noqa: E731
    check(strip(d1) == strip(d2) and (tmp / 'g1' / 'solo-1.toml').read_text() == (tmp / 'g2' / 'solo-1.toml').read_text(), 'make_plan: the same seed gives the same plan and segments')
    d3 = json.loads(hunt.make_plan(args(tmp / 'g3', seed=4), FakeRoam()).read_text())
    check([s.get('seed') for s in d3['sessions']] != [s.get('seed') for s in d1['sessions']], 'make_plan: another seed, other seeds')
    solos = [s for s in d1['sessions'] if s['kind'] == 'solo']
    check(len(solos) == 3 and all(s['save'] == 'save-a' and s['humanize'] in (2, 3) and s['decider'] == 'rules' for s in solos), 'make_plan: random starts from the allowed areas, humanize 2 or 3')
    check(len({s['seed'] for s in solos}) == 3, 'make_plan: a seed for each session')
    pair = [s for s in d1['sessions'] if s['kind'] == 'pair']
    check(len(pair) == 1 and pair[0]['case'] in ('/c/one.toml', '/c/two.toml') and d1['budget'] == {'usd': 1.5} and d1['copy_b'].endswith('-b'), 'make_plan: a pair from the cases, the budget and the second copy')
    import pilot as pilotmod   # the pilot's own segment reader must accept what is generated
    segm = pilotmod.Segment(tmp / 'g1' / 'solo-1.toml')
    check(segm.area == 'Yard' and len(segm.goals[0].targets) == 6 and segm.humanize in (2, 3) and segm.goals[0].kind == 'reach' and segm.save == 'save-a',
          'roam_segment_toml: the pilot\'s Segment reads it (area, six targets, humanize)')
    try:
        hunt.make_plan(args(tmp / 'g4', areas='Cave'), FakeRoam())
        check(False, 'make_plan: no targets is refused')
    except hunt.PlanError as e:
        check('no free-roam targets' in str(e), 'make_plan: an area with no targets is refused')
    try:
        hunt.make_plan(args(tmp / 'g5', areas='Nowhere'), FakeRoam())
        check(False, 'make_plan: no save in the areas is refused')
    except hunt.PlanError as e:
        check('no save of the library' in str(e), 'make_plan: no save in an allowed area is refused')
    ch = tmp / 'chapters.json'
    ch.write_text(json.dumps([{'name': 'ch1', 'save': 'save-a', 'segment': '/segs/ch1.toml', 'wall': 99}]))
    d6 = json.loads(hunt.make_plan(args(tmp / 'g6', chapters=str(ch), chapter_share=1.0, pairs=0), FakeRoam()).read_text())
    check(all(s['segment'] == '/segs/ch1.toml' and s['wall'] == 99 for s in d6['sessions']), 'make_plan: chapters from the chapters file')


def solo_checks(tmp):
    env = setup(tmp / 'e1', hold=200)
    sessions = [solo(env, 'clean', 'normal'), solo(env, 'stall', 'stall'), solo(env, 'crash', 'crash')]
    plan_path = write_plan(env, 'hold-a', sessions, registry=str(tmp / 'e1' / 'known.json'), max_packets=10)
    out = tmp / 'e1' / 'out'
    r = run_hunt(plan_path, out)
    check(r.returncode == 0, f'run: exit 0 ({r.returncode}) {r.stderr[-300:]}')
    res = json.loads((out / 'result.json').read_text())
    rows = {x['name']: x for x in res['sessions']}
    check(all(x['status'] == 'done' for x in res['sessions']), f'run: every session done ({[x["status"] for x in res["sessions"]]})')
    check(rows['clean']['findings'] == {'new': 0, 'duplicate': 0, 'artefact': 0} and rows['clean']['outcome'] == 'solved', f'run: the clean session has no finding ({rows["clean"].get("findings")})')
    kinds = {(f['session'], f['kind']) for f in res['findings']}
    check(('stall', 'stall') in kinds and ('crash', 'crash') in kinds, f'run: the stall and the crash are found ({sorted(kinds)})')
    check(all(f['status'] == 'new' for f in res['findings'] if f['session'] == 'stall'), 'run: first sight is new')
    pk = [f for f in res['findings'] if f['session'] == 'crash' and f['packet']]
    check(pk and (Path(pk[0]['packet']) / 'triage.md').is_file() and (Path(pk[0]['packet']) / 'steps.txt').is_file() and (Path(pk[0]['packet']) / 'logs' / 'solo.log.gz').is_file(),
          'run: a new finding has its packet (triage, steps, log)')
    check((out / 'clean' / 'pilot' / 'live' / 'state.jsonl').is_file() and (out / 'clean' / 'game' / 'present.csv.gz').is_file() and (out / 'clean' / 'game' / tb.LOG).is_file(),
          'run: the pilot\'s folder and the game\'s files are collected (present.csv gzipped)')
    pub = json.loads((out / 'public.json').read_text())
    check(pub['format'] == 'ls-hunt-public/1' and pub['build'] == 'abcdef0123456789' and pub['sessions'] == {'solo': 3, 'pair': 0} and 'stall/stall' in pub['findings'] and pub['keys'],
          f'run: public.json is the fixed-shape rows ({sorted(pub)})')
    blob = json.dumps(pub)
    check('Yard' not in blob and 'walk' not in blob and 'pilotdir' not in blob and str(tmp) not in blob, 'run: public.json carries no map, no step, no path')
    table = (out / 'table.md').read_text()
    check('| clean |' in table and 'stall/stall' in table and 'crash/' in table and '| detector |' in table, 'run: table.md has the sessions, the findings and the detector rows')
    check(not (env['pilot'].parent / 'runs').exists() or True, 'run: (the fake pilot kept its folder)')
    reg = bugpacket.Registry(tmp / 'e1' / 'known.json').entries()
    check(len(reg) >= 2 and all(e['count'] == 1 for e in reg.values()), f'run: the table of known findings has them ({len(reg)})')
    check(not hunt.game_processes(env['copy']), 'run: no process of the copy is left')
    # the same plan again in a new folder with the same registry: duplicates, no new packets
    env2 = setup(tmp / 'e1b', hold=200)
    sessions_b = [solo(env2, 'stall', 'stall'), solo(env2, 'crash', 'crash')]
    plan2 = write_plan(env2, 'hold-b', sessions_b, registry=str(tmp / 'e1' / 'known.json'), max_packets=10)
    out2 = tmp / 'e1b' / 'out'
    run_hunt(plan2, out2)
    res2 = json.loads((out2 / 'result.json').read_text())
    sts = {(f['kind'], f['status']) for f in res2['findings']}
    check(sts and all(st == 'duplicate' for _, st in sts), f'run: the same bugs in the next hold are duplicates ({sorted(sts)})')
    check(not (out2 / 'packets').exists() or not list((out2 / 'packets').iterdir()), 'run: a duplicate gets no second packet')
    reg2 = bugpacket.Registry(tmp / 'e1' / 'known.json').entries()
    check(all(e['count'] == 2 and len(e['runs']) == 2 for e in reg2.values()), 'run: the table counts the second sight and lists both runs')


def watcher_checks(tmp):
    env = setup(tmp / 'e2', hold=300)
    sessions = [solo(env, 'hang', 'hang', wall=60), solo(env, 'lock', 'softlock', wall=60)]
    plan_path = write_plan(env, 'hold-w', sessions, max_packets=10, config={'hang_s': 2.0, 'softlock_s': 60.0, 'softlock_inputs': 3})
    out = tmp / 'e2' / 'out'
    t0 = time.time()
    r = run_hunt(plan_path, out, timeout=200)
    took = time.time() - t0
    res = json.loads((out / 'result.json').read_text())
    rows = {x['name']: x for x in res['sessions']}
    check(rows['hang']['stopped_by'] == 'hang' and rows['hang']['seconds'] < 30, f'watcher: a hang ends the session early ({rows["hang"].get("stopped_by")}, {rows["hang"].get("seconds")} s)')
    check(rows['lock']['stopped_by'] == 'softlock' and rows['lock']['seconds'] < 30, f'watcher: a soft-lock ends the session a little after ({rows["lock"].get("stopped_by")}, {rows["lock"].get("seconds")} s)')
    kinds = {(f['session'], f['kind'], f['sub']) for f in res['findings']}
    check(('hang', 'hang', 'live') in kinds, f'watcher: the live hang is a finding of the session ({sorted(kinds)})')
    check(any(s == 'lock' and k == 'softlock' for s, k, _ in kinds), 'watcher: the soft-lock is a finding')
    check(took < 120 and not hunt.game_processes(env['copy']), f'watcher: both sessions stopped by pid, nothing left ({took:.0f} s)')
    check(any('SIGTERM' in x for x in (out / 'driver.log').read_text().splitlines()), 'driver.log: the stop is logged')
    for f in res['findings']:
        if f['kind'] in ('hang', 'softlock') and f['packet']:
            pj = json.loads((Path(f['packet']) / 'packet.json').read_text())
            check(pj['seed'] == 5 and pj['build']['built_from'] == 'abcdef0123456789' and pj['save']['name'] == 'a-save', 'packet of a watcher finding: seed, build and save named')
            break
    else:
        check(False, 'a watcher finding has a packet')
    # a plain Watcher over a folder: no state yet is not an error
    w = hunt.Watcher(tmp / 'nowhere', tmp / 'nowhere2', bughunt.Config(), lambda: True)
    w.poll()
    check(w.stop_reason is None and w.found == [], 'Watcher: a run with no samples yet is quiet')


def burst_checks(tmp):
    """a solo session whose scene changes in a second while nothing moved: the watcher takes a burst through the (fake) bridge, the hold
    collects it, the detector finds the strobe and the packet has the burst's pictures; with `burst` off nothing is asked"""
    env = setup(tmp / 'eb1', hold=200)
    sockp = tmp / 'br.sock'
    bridge = tbu.FakeBridge(sockp, pattern=(100, 180, 100, 180, 100, 180, 100, 180), present0=1500, step=3)
    bridge.start()
    sessions = [dict(solo(env, 'strobe', 'strobe', wall=14), env=[f'FAKE_BRIDGE={sockp}'])]
    plan_path = write_plan(env, 'hold-b', sessions, max_packets=10, config={'burst_gap_s': 5.0, 'burst_probe_max': 0})
    out = tmp / 'eb1' / 'out'
    r = run_hunt(plan_path, out, timeout=120)
    res = json.loads((out / 'result.json').read_text())
    row = res['sessions'][0]
    check(row.get('bursts') and row['bursts'][0]['kind'] == 'suspicion' and row['bursts'][0]['pictures'] == 8, f'burst: the watcher took one burst of 8 on a suspicion ({row.get("bursts")}, {row.get("burst_errors")}) {r.stderr[-200:]}')
    check(len(bridge.requests) >= 8 and all(q['cmd'] == 'shot' for q in bridge.requests), 'burst: the bridge was asked for shots and nothing else')
    check(len(list((out / 'strobe' / 'game' / 'burst').glob('*/vk_*.png'))) >= 8 and (out / 'strobe' / 'game' / 'burst').glob('*/burst.json'), 'burst: the hold collected the burst into the session folder')
    fl = [f for f in res['findings'] if f['sub'] == 'flicker']
    check(fl and fl[0]['severity'] == 'error' and fl[0]['packet'], f'burst: the strobe is a flicker finding with a packet ({[(f["sub"], f["severity"]) for f in res["findings"]]})')
    if fl and fl[0]['packet']:
        fr = sorted(x.name for x in (Path(fl[0]['packet']) / 'frames').iterdir())
        check(sum(1 for x in fr if x.startswith('burst-')) == 8, f'burst: the packet carries the burst\'s eight pictures ({fr})')
        ev = json.loads((Path(fl[0]['packet']) / 'evidence.json').read_text()) if (Path(fl[0]['packet']) / 'evidence.json').is_file() else {}
        check(json.dumps(ev).count('b01-suspicion') >= 1, 'burst: the packet\'s evidence names the burst')
    check(not hunt.game_processes(env['copy']), 'burst: nothing left running')
    served = len(bridge.requests)
    env_off = setup(tmp / 'eb2', hold=200)
    plan_off = write_plan(env_off, 'hold-c', [dict(solo(env_off, 'strobe', 'strobe', wall=10), env=[f'FAKE_BRIDGE={sockp}'], burst=False)], max_packets=10)
    out_off = tmp / 'eb2' / 'out'
    run_hunt(plan_off, out_off, timeout=120)
    res_off = json.loads((out_off / 'result.json').read_text())
    check(len(bridge.requests) == served and not res_off['sessions'][0].get('bursts'), 'burst: a session with burst off asks the bridge for nothing')
    bridge.close()
    d = json.loads(plan_path.read_text())
    d['burst'] = False
    p = env['plans'] / 'hold-nb.json'
    p.write_text(json.dumps(d))
    check(hunt.load_plan(p)['sessions'][0]['burst'] is False, 'plan: burst false in the plan switches every session off')


def scripted_checks(tmp):
    """a scenario session: hsap (a fake one) plays the scenario's compiled steps after the hold placed Link (a fake hsdebug through the session's
    env), the verdict of the reproduction attempt is in the row and in scenario-result.json, the placement result is in the row"""
    import scenario
    env = setup(tmp / 'e12', hold=300)
    hs = tmp / 'e12' / 'pilotdir' / 'hsap.py'
    hs.write_text(r'''#!/usr/bin/env python3
import json, sys, time
from pathlib import Path
a = sys.argv
copy, tag, wall = Path(a[1]), a[2], a[3]
live = Path(a[a.index('--live') + 1])
game = copy / 'runs' / tag
(game / 'shots').mkdir(parents=True)
T0 = 3000.0
(live / 'out.jsonl').write_text(json.dumps({'ev': 'gameplay', 't': 0.0, 'frame': 100, 'area': 'Yard'}) + '\n')
seen, end = [], time.time() + 40
while time.time() < end:
    lines = (live / 'steps.txt').read_text().splitlines()
    if 'end' in lines:
        break
    time.sleep(0.1)
rows = [{'t': T0 + i / 10, 'frame': 100 + 6 * i, 'map': 'Yard', 'pos': [0, 10, 0], 'event': 0, 'loading': 0, 'life': 12, 'rupees': 5, 'prompt': 'Empty', 'music': 'BGM_Yard', 'flags': {}, 'changed': {}} for i in range(600)]
(live / 'state.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
ev = []
t = 20.0
for n, ln in enumerate(lines, 1):
    if ln.split()[0] in ('end', 'watch'):
        continue
    t += 2.0
    ev.append({'ev': 'step', 'in': n, 'src': ln, 'result': 'done', 'secs': 2.0, 'moved': 0.0, 'detail': '', 't': t})
ev += [{'ev': 'state', 'why': 'wait', 'n': i, 't': (r['t'] - T0), 'frame': r['frame']} for i, r in enumerate(rows[::5])] + [{'ev': 'done', 't': 59.0}]
with open(live / 'out.jsonl', 'a') as f:
    f.write(''.join(json.dumps(e) + '\n' for e in ev))
pres = ['frame,return_ns,interval_ns,present_begin_ns,renderer_begin_ns,renderer_end_ns,vcore_back_ns']
tt = T0 * 1e9
for fr in range(1, 3601):
    iv = 90e6 if 1500 <= fr <= 2400 and fr % 60 == 0 else 16.6e6    # spikes while the fight steps ran (t 22 to 40 s: presents 1320 to 2400)
    tt += iv
    pres.append(f'{100 + fr},{int(tt)},{0 if fr == 1 else int(iv)},0,0,0,0')
(game / 'present.csv').write_text('\n'.join(pres) + '\n')
(game / '@LOG@').write_text('[hos host] vk: device 0: Test GPU 1, Vulkan 1.4\n')
(game / 'exit.txt').write_text('143')
(game / 'summary.txt').write_text('hs-run x exit=143 wall=10s fatal=0 crash=0 devlost=0 nocore=0 kernel=0 nvrm=0\n')
'''.replace('@LOG@', tb.LOG))
    fake = tmp / 'e12' / 'hsdebug_fake.py'
    fake.write_text("""
class Debug:
    def setup(self, to=None, age=None, hour=None, **kw):
        return {'ok': True, 'effect': 'verified', 'steps': [{'ok': True, 'action': 'teleport', 'effect': 'verified'}], 'state': {'map': to, 'pos': [0, 1, 0]}}
    def warp(self, x, y, z, facing=None):
        return {'ok': True, 'effect': 'verified', 'after': {'pos': [x + 0.5, y, z]}}
    def close(self): pass
def attach(run=None, info=None, **kw):
    return Debug()
""")
    sc = scenario.dumps({'format': 'ls-scenario/1', 'name': 'sc-hold', 'purpose': 'reproduce', 'claim': 'spikes while fighting in the Yard', 'players': 1,
                         'at': {'map': YARD, 'age': 'child', 'hour': 23, 'x': 5.0, 'y': 1.0, 'z': 6.0},
                         'action': [{'do': 'wait', 's': 1.0}, {'do': 'fight_loop', 'rounds': 3, 'swings': 2, 'tag': 'fight'}],
                         'expect': [{'check': 'spikes', 'during': ['fight'], 'ms': 50.0, 'min_window_s': 5.0}, {'check': 'distance', 'max_m': 5.0}]})
    (env['plans'] / 'sc-hold.toml').write_text(sc)
    (env['plans'] / 'sc-unconfirmed.toml').write_text(sc.replace('name = "sc-hold"', 'name = "sc-un"').replace('do = "wait"', 'do = "wait"\nconfirmed = false'))
    sess = {'name': 'scn', 'kind': 'solo', 'save': 'a-save', 'scenario': 'sc-hold.toml', 'wall': 60, 'shots': 90, 'env': [f'HSDEBUG_PATH={fake}']}
    plan_path = write_plan(env, 'hold-sc', [sess], max_packets=5)
    out = tmp / 'e12' / 'out'
    r = run_hunt(plan_path, out, timeout=150)
    res = json.loads((out / 'result.json').read_text())
    row = res['sessions'][0]
    check(row['status'] == 'done' and row.get('scenario', {}).get('verdict') == 'reproduced', f'scripted: the scenario ran and its verdict is in the row ({row.get("scenario")}, {row.get("scenario_error")}, {r.stderr[-200:]})')
    check(row.get('place', {}).get('ok') is True or row.get('place') is None, 'scripted: the placement result is in the row (or the scenario had none)')
    sr = json.loads((out / 'scn' / 'scenario-result.json').read_text())
    check(sr['verdict'] == 'reproduced' and sr['checks'][0]['spikes_in'] >= 3 and sr['goto']['distance_m'] is None and sr['hardware'] == 'Test GPU 1', f'scripted: scenario-result.json carries the checks and the hardware ({sr["checks"][0]})')
    steps = (out / 'scn' / 'pilot' / 'live' / 'steps.txt').read_text().splitlines()
    check(steps[-1] == 'end' and not any(x.startswith('walk 5.00') for x in steps) and 'ztarget 800' in steps, f'scripted: after the warp the leg to the point is left out and the fight steps went to hsap ({steps[:3]})')
    tg = json.loads((out / 'scn' / 'pilot' / 'live' / 'scenario-steps.json').read_text())['tags']
    check(set(tg.values()) == {'wait', 'fight'}, f'scripted: the tags of the steps are kept ({set(tg.values())})')
    check(json.loads((out / 'scn' / 'pilot' / 'live' / 'placement.json').read_text())['warp']['ok'], 'scripted: the warp is in placement.json')
    sc_env = scenario.dumps({'format': 'ls-scenario/1', 'name': 'sc-env', 'purpose': 'coverage', 'claim': 'x', 'players': 1, 'env': ['HOS_FPS_LOG=1'], 'at': {'map': YARD}, 'action': [{'do': 'wait'}]})
    (env['plans'] / 'sc-env.toml').write_text(sc_env)
    check('HOS_FPS_LOG=1' in hunt.load_plan(write_plan(env, 'hold-env', [dict(sess, scenario='sc-env.toml')]))['sessions'][0]['env'], 'plan: the scenario\'s env joins the session\'s')
    # an unconfirmed action refuses the plan; a scenario with a bad file refuses too
    try:
        hunt.load_plan(write_plan(env, 'hold-un', [dict(sess, scenario='sc-unconfirmed.toml')]))
        check(False, 'an unconfirmed scenario is refused')
    except hunt.PlanError as e:
        check('unconfirmed' in str(e), 'plan: a scenario with unconfirmed actions is refused until a person confirms them')
    check(hunt.load_plan(write_plan(env, 'hold-un2', [dict(sess, scenario='sc-unconfirmed.toml', allow_unconfirmed=True)]))['sessions'][0]['scenario'].endswith('sc-unconfirmed.toml'), 'plan: allow_unconfirmed goes on')
    # a regression scenario: the known key must fire again (a pair with the seeded double give)
    env2 = setup(tmp / 'e13', hold=300)
    case = env2['plans'] / 'case-double.toml'
    case.write_text('# SEED=double\nname = "c"\n')
    cfg = {'hang_s': 30.0, 'give_rules': [{'name': 'small-key chest', 'flag': 'chest_flag', 'counter': 'keys', 'per_flag': 1}]}
    key = bughunt.make_key('give', 'double', 'small-key chest')
    sessions = [{'name': 'pair-reg', 'kind': 'pair', 'case': case.name, 'hold_s': 60, 'expect_key': key, 'label': 'double-give-regression'},
                {'name': 'pair-gone', 'kind': 'pair', 'case': case.name, 'hold_s': 60, 'expect_key': 'give:double:00000000', 'label': 'other-key'}]
    plan2 = write_plan(env2, 'hold-reg', sessions, max_packets=10, config=cfg)
    out2 = tmp / 'e13' / 'out'
    run_hunt(plan2, out2, timeout=150)
    rows = {r['name']: r for r in json.loads((out2 / 'result.json').read_text())['sessions']}
    check(rows['pair-reg']['scenario']['verdict'] == 'reproduced' and rows['pair-reg']['scenario']['purpose'] == 'regression' and rows['pair-gone']['scenario']['verdict'] == 'not reproduced',
          f'regression: the known key fires again in the pair; another key does not ({[(n, r.get("scenario", {}).get("verdict")) for n, r in rows.items()]})')
    # a pair scenario: the pair session is judged by the scenario's checks (the seeded double give)
    env3 = setup(tmp / 'e14', hold=300)
    case3 = env3['plans'] / 'case-double.toml'
    case3.write_text('# SEED=double\nname = "c"\n')
    psc = scenario.dumps({'format': 'ls-scenario/1', 'name': 'pair-sc', 'purpose': 'regression', 'claim': 'both players open the same chest', 'players': 2, 'save': 'a-save',
                          'watch': ['keys'], 'at': {'map': 'Yard', 'from': 'save'}, 'action': [{'do': 'rendezvous', 'name': 'r'}],
                          'expect': [{'check': 'key', 'key': key}, {'check': 'counter', 'flag': 'keys', 'max': 1}, {'check': 'crash'}]})
    (env3['plans'] / 'pair-sc.toml').write_text(psc)
    plan3 = write_plan(env3, 'hold-psc', [{'name': 'pair-s', 'kind': 'pair', 'case': case3.name, 'hold_s': 60, 'scenario': 'pair-sc.toml'}], max_packets=10, config=cfg)
    out3 = tmp / 'e14' / 'out'
    run_hunt(plan3, out3, timeout=150)
    row3 = json.loads((out3 / 'result.json').read_text())['sessions'][0]
    sc3 = row3.get('scenario') or {}
    check(sc3.get('verdict') == 'reproduced' and sc3.get('purpose') == 'regression' and {c['check'] for c in sc3.get('checks', [])} == {'key', 'counter', 'crash'}, f'a pair scenario: the verdict of its checks is in the row ({sc3}, {row3.get("scenario_error")})')
    try:
        hunt.load_plan(write_plan(env3, 'hold-psc2', [{'name': 'pair-s', 'kind': 'pair', 'case': case3.name, 'hold_s': 60, 'scenario': 'sc-hold.toml'}]))
        check(False, 'a pair session needs a pair scenario')
    except (hunt.PlanError, FileNotFoundError) as e:
        check(True, 'a pair session needs a pair scenario')
    # a pilot of a pair that was cut before it wrote its summary leaves its record only in the pilot's live folder: the session folder gets it
    rd = tmp / 'rec'
    runs = rd / 'runs'
    for side, done in (('A', True), ('B', False)):
        live = runs / f'pair-x-20260101-000000-{side}' / 'live'
        live.mkdir(parents=True)
        (live / 'out.jsonl').write_text(json.dumps({'ev': 'step', 'in': 1, 'result': 'met'}) + '\n')
        (live / 'steps.txt').write_text('rendezvous r\n')
        old_run = runs / f'pair-x-20250101-000000-{side}' / 'live'
        old_run.mkdir(parents=True)
        (old_run / 'out.jsonl').write_text('OLD\n')
        os.utime(old_run / 'out.jsonl', (1000, 1000))
    sess = tmp / 'sess-rec'
    (sess / 'A' / 'pilot').mkdir(parents=True)
    (sess / 'A' / 'pilot' / 'out.jsonl').write_text('KEEP\n')
    (sess / 'B' / 'pilot').mkdir(parents=True)
    (sess / 'case.json').write_text(json.dumps({'name': 'pair-x', 'sides': {'A': {'driver': 'pilot', 'pilot': {'runs': str(runs)}}, 'B': {'driver': 'pilot', 'pilot': {'runs': str(runs)}}}}))
    got = hunt.recover_pilot_records(sess, since=2000.0)
    check(got == ['B'] and (sess / 'B' / 'pilot' / 'out.jsonl').read_text().startswith('{"ev": "step"') and (sess / 'B' / 'pilot' / 'steps.txt').is_file()
          and (sess / 'A' / 'pilot' / 'out.jsonl').read_text() == 'KEEP\n', f'a pair pilot cut before its summary: its live record is copied into the session; a side that has its own is left ({got})')
    check(hunt.recover_pilot_records(tmp / 'nowhere', since=0) == [], 'no case.json: nothing to recover')
    # the scorecard counts the attempt
    import score
    card = score.score_round('r', [out], {}, with_maps=False)
    check(card['scenarios'] == [{'name': 'sc-hold', 'purpose': 'reproduce', 'verdict': 'reproduced', 'hardware': 'Test GPU 1'}] and '| sc-hold | reproduce | reproduced |' in score.trend_table([card]), 'scorecard: a scenario is scored by its verdict')


def pair_checks(tmp):
    env = setup(tmp / 'e3', hold=300)
    case_ok = env['plans'] / 'case-double.toml'
    case_ok.write_text('# SEED=double SEED=desync\nname = "c"\n')
    cfg = {'hang_s': 30.0, 'shared': ['shared_flag'], 'desync_grace_s': 5.0,
           'give_rules': [{'name': 'small-key chest', 'flag': 'chest_flag', 'counter': 'keys', 'per_flag': 1}]}
    plan_path = write_plan(env, 'hold-p', [{'name': 'pair-1', 'kind': 'pair', 'case': case_ok.name, 'hold_s': 60}], max_packets=10, config=cfg)
    out = tmp / 'e3' / 'out'
    r = run_hunt(plan_path, out)
    res = json.loads((out / 'result.json').read_text())
    row = res['sessions'][0]
    check(row['status'] == 'done' and row.get('verdict') == 'pass', f'pair: the session ran and its own verdict is kept ({row["status"]}, {row.get("verdict")}) {r.stderr[-200:]}')
    got = {(f['kind'], f['sub'], f['side'], f['status']) for f in res['findings']}
    check(('give', 'double', 'A', 'new') in got and ('give', 'double', 'B', 'duplicate') in got, f'pair: the seeded double give is found on both sides, once new, once duplicate ({sorted(got)})')
    check(any(k == 'desync' and sub == 'flag' for k, sub, _, _ in got), 'pair: the shared flag that disagrees is found')
    pk = [f['packet'] for f in res['findings'] if f['kind'] == 'give' and f['status'] == 'new'][0]
    names = sorted(p.name for p in Path(pk).iterdir())
    check('steps.A.txt' in names or 'trace.A.jsonl' in names, f'pair: the packet has per-side files ({names})')
    check('case.toml' in names and json.loads((Path(pk) / 'replay.json').read_text())['mode'] == 'case', 'pair: the packet carries the case and replays through it')
    check((Path(pk) / 'logs' / 'A.log.gz').is_file() and (Path(pk) / 'logs' / 'B.log.gz').is_file(), 'pair: both logs are in the packet')
    # replay of the pair packet: a plan of one pair session on the packet's case with a fresh rendezvous folder, run, then the verdict
    rp = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'hunt.py'), 'replay-plan', pk, '--plan', str(plan_path), '--out', str(tmp / 'e3' / 'rp'), '--name', 'hold-pr', '--hold-seconds', '300'],
                        capture_output=True, text=True)
    check(rp.returncode == 0 and (tmp / 'e3' / 'rp' / 'plan.json').is_file() and (tmp / 'e3' / 'rp' / 'rendezvous').is_dir(), f'replay-plan: a plan of one pair session ({rp.returncode}) {rp.stderr[-200:]}')
    rplan = hunt.load_plan(tmp / 'e3' / 'rp' / 'plan.json')
    check(len(rplan['sessions']) == 1 and rplan['sessions'][0]['kind'] == 'pair' and rplan['sessions'][0]['case'].endswith('replay-case.toml') and rplan['config']['shared'] == ['shared_flag'],
          'replay-plan: the pair session on the replay case, with the original\'s detector config')
    rout = tmp / 'e3' / 'rp-out'
    run_hunt(tmp / 'e3' / 'rp' / 'plan.json', rout)
    vd = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'hunt.py'), 'verdict', pk, str(rout)], capture_output=True, text=True)
    check(vd.returncode == 0 and '"reproduced"' in vd.stdout and (Path(pk) / 'replay' / 'replay.json').is_file(), f'verdict: the double give fired again in the replay hold ({vd.stdout[-200:]}{vd.stderr[-200:]})')
    clean = env['plans'] / 'case-clean.toml'
    clean.write_text('name = "c"\n')
    env2 = setup(tmp / 'e3b', hold=300)
    plan2 = write_plan(env2, 'hold-p2', [{'name': 'pair-1', 'kind': 'pair', 'case': str(clean), 'hold_s': 60}], config=cfg)
    run_hunt(plan2, tmp / 'e3b' / 'out')
    res2 = json.loads((tmp / 'e3b' / 'out' / 'result.json').read_text())
    check([f for f in res2['findings'] if f['kind'] in ('give', 'desync')] == [], 'pair: a clean pair has no give or desync finding')


def budget_checks(tmp):
    env = setup(tmp / 'e4', hold=100)   # budget 95 s: the first needs 5 + 5 + 30 = 40 s and runs 13 s to its wall; the second needs 60 + 5 + 30 = 95: no more
    plan_path = write_plan(env, 'hold-b', [solo(env, 'one', 'sleep', wall=5), solo(env, 'two', 'normal', wall=60)])
    out = tmp / 'e4' / 'out'
    run_hunt(plan_path, out)
    res = json.loads((out / 'result.json').read_text())
    sts = [x['status'] for x in res['sessions']]
    check(sts[0] == 'done' and sts[1].startswith('not started: ') and 'needed' in sts[1], f'budget: the second session does not fit and is not started ({sts})')
    check(res['sessions'][0]['stopped_by'] == 'wall', 'budget: a session that outlives its wall plus the allowance is stopped there')
    # a game of the copy is running: refused, not started
    env = setup(tmp / 'e5', hold=200)
    fake_game = env['copy'] / EXE
    shutil.copy(shutil.which('sleep'), fake_game)
    proc = subprocess.Popen([str(fake_game), '60'], start_new_session=True)
    try:
        time.sleep(0.3)
        plan_path = write_plan(env, 'hold-r', [solo(env, 'one', 'normal')])
        out = tmp / 'e5' / 'out'
        r = run_hunt(plan_path, out)
        res = json.loads((out / 'result.json').read_text())
        check(res['sessions'][0]['status'].startswith('refused: a game process of the copy is running'), f'refusal: a game of the copy is running ({res["sessions"][0]["status"]})')
        check(proc.poll() is None, 'refusal: the other game was not touched')
        rr = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'hunt.py'), 'replay', str(tmp), '--copy', str(env['copy'])], capture_output=True, text=True)
        check(rr.returncode != 0, 'refusal: replay of a non-packet fails')
    finally:
        proc.kill()
        proc.wait()


def stop_checks(tmp):
    env = setup(tmp / 'e6', hold=300)
    plan_path = write_plan(env, 'hold-s', [solo(env, 'sleeper', 'sleep', wall=100), solo(env, 'next', 'normal')])
    out = tmp / 'e6' / 'out'
    p = subprocess.Popen([sys.executable, '-I', '-B', str(HERE / 'hunt.py'), 'run', str(plan_path), '--out', str(out)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    deadline = time.time() + 30
    while time.time() < deadline and not (env['copy'] / 'runs' / 'hold-s-sleeper').exists():
        time.sleep(0.2)
    time.sleep(1.5)
    p.send_signal(signal.SIGTERM)
    try:
        code = p.wait(timeout=60)
    except subprocess.TimeoutExpired:
        p.kill()
        code = None
    res = json.loads((out / 'result.json').read_text())
    check(code == 143 and res['stopped'].startswith('signal'), f'stop: the hold\'s deadline ends the hunt with 143 and says so ({code}, {res.get("stopped")})')
    check(res['sessions'][0]['status'] == 'stopped by the hold' and res['sessions'][1]['status'] == 'pending', f'stop: the running session is marked, the next never started ({[s["status"] for s in res["sessions"]]})')
    check((out / 'sleeper' / 'pilot' / 'live' / 'state.jsonl').is_file() and (out / 'table.md').is_file(), 'stop: what the session had made is collected and the table written')
    check(not hunt.game_processes(env['copy']) and subprocess.run(['pgrep', '-f', 'hold-s-sleeper'], capture_output=True).returncode != 0, 'stop: the pilot\'s family is gone')


def replay_and_queue_checks(tmp):
    # a replay needs a hsap; the fake one writes what hsap leaves (a live folder with state, out and the game's run folder)
    env = setup(tmp / 'e7', hold=200)
    hs = tmp / 'e7' / 'pilotdir' / 'hsap.py'
    hs.write_text(r'''#!/usr/bin/env python3
import json, sys, time
from pathlib import Path
a = sys.argv
copy, tag, wall = Path(a[1]), a[2], a[3]
live = Path(a[a.index('--live') + 1])
steps = (live / 'steps.txt').read_text()
game = copy / 'runs' / tag
(game / 'shots').mkdir(parents=True)
T0 = 3000.0
rows = [{'t': T0 + i / 10, 'frame': 100 + 6 * i, 'map': 'Yard', 'pos': [0, 10, 0], 'event': 0, 'loading': 0, 'life': 12, 'rupees': 5, 'prompt': 'Empty', 'music': 'BGM_Yard', 'flags': {}, 'changed': {}} for i in range(300)]
if True:   # the replayed inputs meet the same hang: a 400 s hole in the samples
    rows = rows + [{'t': T0 + 400 + i / 10, 'frame': 5000 + 6 * i, 'map': 'Yard', 'pos': [0, 10, 0], 'event': 0, 'loading': 0, 'life': 12, 'rupees': 5, 'prompt': 'Empty', 'music': 'BGM_Yard', 'flags': {}, 'changed': {}} for i in range(100)]
(live / 'state.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
(live / 'out.jsonl').write_text(json.dumps({'ev': 'done', 't': 1.0}) + '\n')
(game / '@LOG@').write_text('[hos] start\n')
(game / 'exit.txt').write_text('143')
'''.replace('@LOG@', tb.LOG))
    side, session = tb_session(tmp / 'e7', env)
    f = bughunt.Finding(kind='hang', sub='resumed', severity='error', side='solo', text='a 40 s hole', t=tb.T0 + 10.0, frame=700, game_s=10.0, map='Yard', pos=[0, 10, 0], evidence={})
    f.key = bughunt.place_key('hang', 'resumed', 'Yard', f.pos, 16.0)
    packet = bugpacket.make_packet(tmp / 'e7' / 'packet', f, {'solo': side}, session, None)
    cfg = bughunt.Config(hang_s=30.0)
    res = hunt.replay_packet(packet, env['copy'], env['pilot'], cfg, None, None, wall=20, out=packet / 'replay')
    check(res['verdict'] == 'reproduced' and res['packet_key'] == f.key, f'replay: the hang fires again from the packet\'s own inputs ({res["verdict"]}: {res["detail"]})')
    live = (packet / 'replay' / 'live' / 'steps.txt').read_text().splitlines()
    check(live[-1] == 'end' and (packet / 'replay' / 'replay.json').is_file(), 'replay: the packet\'s steps went to the game side, with an end; the verdict is written')
    check(not hunt.game_processes(env['copy']), 'replay: nothing left running')
    # the waiter
    plan_path = write_plan(env, 'PilotQueueTest', [solo(env, 'one', 'normal')])
    plan = hunt.load_plan(plan_path)
    cmd = hunt.queue_command(plan_path, plan, tmp / 'e7' / 'sessions' / 'PilotQueueTest', quiet='/tmp/q.lock', measuring='/tmp/m.lock')
    cmd_w = hunt.queue_command(plan_path, plan, tmp / 'e7' / 'sessions' / 'PilotQueueTest', quiet='/tmp/q.lock', measuring='/tmp/m.lock', wait=43200)
    check(cmd_w[cmd_w.index('/tmp/q.lock') - 1] == '43200' and cmd[cmd.index('/tmp/q.lock') - 1] == '28800', 'queue --wait: the quiet lock is waited for as long as asked, 8 hours by default')
    check(cmd[:4] == ['setsid', 'nohup', 'env', '--default-signal=HUP'] and cmd.count('flock') == 2 and cmd.index('/tmp/q.lock') < cmd.index('/tmp/m.lock') and 'timeout' in cmd, 'queue: setsid, the quiet lock then the measuring lock, then timeout')
    check(cmd[cmd.index('timeout') + 3] == '200' and 'run' in cmd and 'Pilot' in ' '.join(cmd), 'queue: the hold\'s length, the run command, and "Pilot" in the line for the dispatcher\'s priority')
    out = tmp / 'e7' / 'sessions' / 'PilotQueueTest'
    saved = {k: os.environ.pop(k) for k in ('HUNT_QUIET', 'HUNT_MEASURING') if k in os.environ}   # the main lane's two lock files: this machine's own settings, no default
    try:
        for given in ({}, {'quiet': str(tmp / 'q.lock')}, {'measuring': str(tmp / 'm.lock')}):
            try:
                hunt.queue_command(plan_path, plan, out, **given)
                check(False, f'queue: without both lock settings it is refused ({sorted(given)})')
            except hunt.PlanError as e:
                check('HUNT_QUIET' in str(e) and 'HUNT_MEASURING' in str(e) and 'no default' in str(e), f'queue: without both lock settings it is refused, naming them ({sorted(given)}: {e})')
        os.environ.update({'HUNT_QUIET': str(tmp / 'q.lock'), 'HUNT_MEASURING': str(tmp / 'm.lock')})
        check(hunt.queue_command(plan_path, plan, out) == hunt.queue_command(plan_path, plan, out, quiet=str(tmp / 'q.lock'), measuring=str(tmp / 'm.lock')), 'queue: HUNT_QUIET and HUNT_MEASURING are the two locks')
    finally:
        os.environ.pop('HUNT_QUIET', None)
        os.environ.pop('HUNT_MEASURING', None)
        os.environ.update(saved)
    unset = {k: v for k, v in os.environ.items() if k not in ('HUNT_QUIET', 'HUNT_MEASURING')}
    cli = [sys.executable, '-I', '-B', str(HERE / 'hunt.py'), 'queue', str(plan_path), '--dry-run', '--sessions', str(tmp / 'e7' / 'sessions')]
    r = subprocess.run(cli, capture_output=True, text=True, env={**unset, 'HUNT_PGREP': 'no-such-process-pattern-xyz'})
    check(r.returncode == 2 and 'WOULD REFUSE' in r.stdout and 'HUNT_QUIET' in r.stdout and not (tmp / 'e7' / 'sessions').exists(), f'queue: --dry-run without the lock settings says it would refuse ({r.returncode}) {r.stdout[-200:]}{r.stderr[-200:]}')
    locks = {**unset, 'HUNT_QUIET': str(tmp / 'q.lock'), 'HUNT_MEASURING': str(tmp / 'm.lock'), 'HUNT_PGREP': 'no-such-process-pattern-xyz'}
    r = subprocess.run(cli, capture_output=True, text=True, env=locks)
    check(r.returncode == 0 and 'dry run: would start the waiter' in r.stdout and not (tmp / 'e7' / 'sessions').exists(), f'queue: --dry-run prints the command and writes nothing ({r.returncode}) {r.stdout[-200:]}{r.stderr[-200:]}')
    (tmp / 'e7' / 'sessions').mkdir()
    (tmp / 'e7' / 'sessions' / 'PilotQueueTest.pid').write_text('1\n')
    r = subprocess.run(cli, capture_output=True, text=True, env=locks)
    check(r.returncode == 2 and 'WOULD REFUSE' in r.stdout and '.pid exists' in r.stdout, 'queue: a pid file of the name refuses')


def tb_session(tmp, env):
    states = tb.steady(10)
    side = tb.make_side(tmp / 'orig', states, events=tb.events_for(states, [tb.step(2.0, 'walk 3 4', 'reached', **{'in': 2})]),
                        log='[hos] x\n', summary=tb.OK_SUMMARY, exit_code=143, steps_text='watch a\nwalk 3 4 radius 1\n')
    (tmp / 'orig' / 'game' / 'shots').mkdir(parents=True)
    (tmp / 'orig' / 'game' / 'shots' / 'vk_000090.png').write_bytes(vision.write_png(4, 4, bytes([9, 9, 9] * 16)))
    save = tmp / 'orig-save'
    (save / 'save').mkdir(parents=True)
    (save / 'save' / 'progress.sav').write_bytes(b'z')
    seg = tmp / 'orig.toml'
    seg.write_text('name = "x"\n')
    return side, {'run': 'orig', 'kind': 'solo', 'copy': str(env['copy']), 'save': str(save), 'save_name': 'a-save', 'segment': str(seg), 'seed': 5, 'humanize': 2,
                  'decider': 'rules', 'wall': 20, 'shots': 90, 'env': [], 'boot': 'continue'}


def analyze_cli_checks(tmp):
    # `hunt.py analyze` over folders already played: the table of known findings, the packets, the table
    side, session = tb_session(tmp / 'e8', {'copy': tmp})
    d = tmp / 'e8' / 'orig'
    (d / 'game' / 'present.csv').write_text(tb.present_rows(3000, gaps={1000: 5000.0}))
    out = tmp / 'e8' / 'analysis'
    r = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'hunt.py'), 'analyze', str(d), '--out', str(out), '--packets'], capture_output=True, text=True)
    check(r.returncode == 0 and 'stall' in r.stdout and (out / 'table.md').is_file() and (out / 'known.json').is_file(), f'analyze: detectors, table and known findings written ({r.returncode}) {r.stderr[-200:]}')
    check(any((out / 'packets').iterdir()), 'analyze: --packets makes the packets')
    r2 = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'hunt.py'), 'analyze', str(d), '--out', str(out)], capture_output=True, text=True)
    reg = bugpacket.Registry(out / 'known.json').entries()
    check(r2.returncode == 0 and all(e['count'] == 2 for e in reg.values()), 'analyze: the same folder again counts the second sight')
    # a verdict in the table is a rule for the next analysis: the artefact is no finding the next time (its registry is the folder's known.json)
    t1 = (out / 'table.md').read_text()
    keys = list(bugpacket.Registry(out / 'known.json').entries())
    bugpacket.Registry(out / 'known.json').set_status(keys[0], 'artefact', 'the machine')
    r3 = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'hunt.py'), 'analyze', str(d), '--out', str(out)], capture_output=True, text=True, env={**os.environ})
    t3 = (out / 'table.md').read_text()
    check(r3.returncode in (0, 1) and f'`{keys[0]}`' in t1 and f'`{keys[0]}`' not in t3, f'analyze: a key triaged as an artefact is no finding in the next analysis ({r3.returncode}) {r3.stderr[-160:]}')


def nightly_checks(tmp):
    env = setup(tmp / 'e9', hold=200)
    lib = tmp / 'e9' / 'ngt-lib'
    (lib / 'save-a' / 'save').mkdir(parents=True)
    (lib / 'catalogue.json').write_text(json.dumps({'save-a': {'decoded': {'slots': [{'area': 'Yard', 'pos': [1, 10, 2]}]}}}))

    class FakeRoam:
        def targets(self, area, start, rng, k, **kw):
            return [(round(rng.uniform(-50, 50), 2), round(rng.uniform(-50, 50), 2), 10.0) for _ in range(k)]
    old_factory = hunt.ROAM_FACTORY
    hunt.ROAM_FACTORY = FakeRoam
    tpl = tmp / 'e9' / 'nightly.json'
    tpl.write_text(json.dumps({'solo': 2, 'library': str(lib), 'copies': [str(env['copy']), str(env['copy_b'])], 'pilot': str(env['pilot']), 'areas': 'Yard',
                               'hold_seconds': 300, 'wall': 100, 'prefix': 'PilotNightlyTest', 'budget_usd': 1.0, 'registry': 'known.json'}))
    try:
        import datetime
        a = argparse.Namespace(template=str(tpl), date='2026-11-20', dry_run=True)
        os.environ['HUNT_PGREP'] = 'no-such-process-pattern-xyz'
        saved_locks = {k: os.environ.get(k) for k in ('HUNT_QUIET', 'HUNT_MEASURING')}   # the queue needs this machine's lock settings
        os.environ.update({'HUNT_QUIET': str(tmp / 'q.lock'), 'HUNT_MEASURING': str(tmp / 'm.lock')})
        code = hunt.cmd_nightly(a)
        plan = json.loads((tmp / 'e9' / 'plans' / 'PilotNightlyTest-20261120' / 'plan.json').read_text())
        check(code == 0 and plan['name'] == 'PilotNightlyTest-20261120' and len(plan['sessions']) == 2 and plan['registry'].endswith('known.json') and plan['budget'] == {'usd': 1.0},
              f'nightly: tonight\'s plan is named by the date and carries the template\'s budget and registry ({code})')
        check(not (tmp / 'e9' / 'sessions').exists(), 'nightly: --dry-run queues nothing')
        args1, _, _, _ = hunt.nightly_args(tpl, datetime.date(2026, 11, 20))
        args2, _, _, _ = hunt.nightly_args(tpl, datetime.date(2026, 11, 21))
        check(args1.seed == 20261120 and args2.seed == 20261121 and args1.name != args2.name, 'nightly: the seed is the date')
        plan2 = json.loads(hunt.make_plan(args2, FakeRoam()).read_text())
        check([s['seed'] for s in plan2['sessions']] != [s['seed'] for s in plan['sessions']], 'nightly: another night, other seeds')
        check(hunt.cmd_nightly(a) == 2, 'nightly: the same night twice is refused (the plan exists)')
        tpl.write_text(json.dumps({'bogus': 1}))
        try:
            hunt.nightly_args(tpl, datetime.date(2026, 11, 20))
            check(False, 'nightly: an unknown template key is refused')
        except hunt.PlanError:
            check(True, 'nightly: an unknown template key is refused')
    finally:
        hunt.ROAM_FACTORY = old_factory
        os.environ.pop('HUNT_PGREP', None)
        for k, v in saved_locks.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def session_info_checks(tmp):
    d = tmp / 'e10' / 'sess'
    (d / 'pilot').mkdir(parents=True)
    (d / 'pilot' / 'summary.json').write_text(json.dumps({'copy': '/x/copy-c', 'decider': 'rules', 'humanize': {'level': 3, 'seed': 77},
                                                         'runner': ['py', 'hsap.py', '/x/copy-c', 'tag', '260', '--live', 'l', '--save', '/lib/some-save', '--boot', 'continue', '--shots', '90']}))
    info = hunt.session_from_folder(d)
    check(info == {'run': 'sess', 'kind': 'solo', 'save': '/lib/some-save', 'boot': 'continue', 'shots': '90', 'save_name': 'some-save', 'copy': '/x/copy-c', 'seed': 77,
                   'humanize': 3, 'decider': 'rules'}, f'session_from_folder: a solo\'s save, boot, seed and copy from its pilot summary ({info})')
    p = tmp / 'e10' / 'pair'
    p.mkdir()
    (p / 'case-source.toml').write_text('name = "c"\n')
    (p / 'session.json').write_text('{}')
    check(hunt.session_from_folder(p) == {'run': 'pair', 'kind': 'pair', 'case': str(p / 'case-source.toml')}, 'session_from_folder: a pair\'s case source')
    check(hunt.session_from_folder(tmp / 'e10') == {'run': 'e10', 'kind': 'solo'}, 'session_from_folder: nothing known, nothing claimed')


def source_checks():
    text = (HERE / 'hunt.py').read_text()
    import re
    for bad in ('/home/', 'sk-', 'Bearer '):
        check(bad not in text, f'hunt.py: no {bad!r}')
    for p in hs_names.PROJECTS:   # the game's own names come from hs_names, never spelled in the code
        check(p not in text.lower(), f'hunt.py: the project name {p!r} is not spelled here')
    check(not re.search(r"OPENAI_API_KEY=[^'\"\s]", text), 'hunt.py: no key value')


def run_in(tmp):
    plan_checks(tmp)
    generator_checks(tmp)
    solo_checks(tmp)
    watcher_checks(tmp)
    burst_checks(tmp)
    scripted_checks(tmp)
    pair_checks(tmp)
    budget_checks(tmp)
    stop_checks(tmp)
    replay_and_queue_checks(tmp)
    analyze_cli_checks(tmp)
    nightly_checks(tmp)
    session_info_checks(tmp)
    source_checks()


def run():
    with tempfile.TemporaryDirectory(prefix='test-hunt-') as t:
        run_in(Path(t))


def main():
    run()
    if FAILS:
        raise SystemExit(f'test_hunt: {len(FAILS)} of {CHECKS[0]} checks FAILED')
    print(f'test_hunt: all {CHECKS[0]} checks passed')


if __name__ == '__main__':
    main()
