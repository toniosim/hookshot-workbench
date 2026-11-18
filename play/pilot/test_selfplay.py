#!/usr/bin/env python3
"""selfplay.py without the game: a made-up route library (clusters with their tracks), a made-up Book, a fake `pilot.py` (a small script that writes a summary.json,
a transcript with `recover` rows, a run folder the library can import, and attempts into the Book as the real ladder does) and a fake save tool. Checks: the approach
point (a track point, 8 to 10 m of path before the stuck point, a yaw toward the want), the choice and ordering of the clusters (impact, what the Book knows, spread
over a night and over nights, `--only` with a mode), the saves' command lines, the segment files (parsed by pilot.Segment), the refusals of `check`, the hold's time
budget (a session that would not fit is not started, a stuck one is ended by pid: `end`, SIGTERM, SIGKILL), the result rows, the Book diff and the report, the
environment the pilot gets, the waiter's command (flock order, -w 43200, timeout and kill-after, setsid, the name), the second-waiter refusal, `stop`, and
`nightly` (idempotent per night, refuses beside a waiter or over the cap). No game, no GPU, no network, no model; the locks of the main lane are never touched.

    python3 -I -B test_selfplay.py
"""
import contextlib
import copy
import fcntl
import io
import json
import math
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pilot  # noqa: E402
import routelib  # noqa: E402
import selfplay  # noqa: E402
import tactics  # noqa: E402

FAILS, CHECKS = [], [0]
M, D = 'Testland_Child', 'Dungeonland'


def raises(fn, exc):
    try:
        fn()
    except exc:
        return True
    return False


def check(cond, what):
    CHECKS[0] += 1
    if not cond:
        FAILS.append(what)
        print('FAIL', what, flush=True)


def cli(argv):
    """main(argv) with its stdout: (exit code, text)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            rc = selfplay.main(argv)
        except SystemExit as e:
            rc = e.code
    return rc, buf.getvalue()


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:
        return Path(f'/proc/{pid}/stat').read_text().rpartition(')')[2].split()[0] != 'Z'
    except OSError:
        return False


def wait_for(cond, seconds, step=0.1):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(step)
    return cond()


# ---------------------------------------------------------------------------------------------------------- a made-up route library

class FakeLib:
    """Writes the library's map files directly: a cluster is runs that walked a straight line along +z to the stuck point and were stuck there."""

    def __init__(self, root):
        self.root = Path(root)
        self.maps = {}

    def _map(self, name):
        return self.maps.setdefault(name, {'format': routelib.FORMAT, 'map': name, 'tracks': [], 'stuck': [], 'attempts': [], 'anchors': []})

    def cluster(self, map, at, want, cause, runs=1, length=30.0, ts='2026-11-10T10:00:00', age='child', pts=None):
        m = self._map(map)
        for i in range(runs):
            run = f'{map}-{at[0]:.0f}-{at[2]:.0f}-r{i}'
            track = {'id': f'{run}#0', 'run': run, 'build': 'g1', 'age': age, 'origin': 'start', 'ts': ts, 'save': 'kid',
                     'pts': pts or [[float(k), at[0], at[1], round(at[2] - length + k, 2), 1] for k in range(int(length) + 1)], 'steps': [], 'len_m': length}
            m['tracks'].append(track)
            tt = track['pts'][-1][0]
            m['stuck'].append({'run': run, 'build': 'g1', 'ts': ts, 'step': 2, 'verb': 'run', 'src': 'run 0.00 0.00 radius 2.5 timeout 20', 'at': list(at), 'want': list(want) if want else None,
                               'd_want': 10.0, 'result': 'stuck', 'detail': 'made up', 'moved': 0.2, 't': tt, 'cause': cause, 'why': 'made up', 'track': track['id']})

    def walk_past(self, map, at, ts):
        """A later run that walked through the place and on: the cluster is resolved."""
        self._map(map)['tracks'].append({'id': f'late-{at[0]:.0f}#0', 'run': f'late-{at[0]:.0f}', 'build': 'g2', 'age': 'child', 'origin': 'start', 'ts': ts, 'save': 'kid',
                                         'pts': [[float(k), at[0], at[1], at[2] - 10 + k, 1] for k in range(26)], 'steps': [], 'len_m': 25.0})

    def write(self):
        (self.root / 'maps').mkdir(parents=True, exist_ok=True)
        for name, d in self.maps.items():
            (self.root / 'maps' / f'{name}.json').write_text(json.dumps(d))


FAKE_PILOT = r'''
import json, os, signal, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, %(code)r)
import routelib
import tactics
import test_routelib

a = sys.argv[1:]
opt = {a[i]: a[i + 1] for i in range(len(a) - 1) if a[i].startswith('--')}
tag = opt['--tag']
cfg = json.loads((HERE / 'fake.json').read_text()).get(tag, {})
scen = cfg.get('scen', 'worked')
run = HERE / 'runs' / tag
run.mkdir(parents=True)
(run / 'live').mkdir()
steps = run / 'live' / 'steps.txt'
steps.write_text('')
(run / 'argv.json').write_text(json.dumps(a))
(run / 'pid').write_text(str(os.getpid()))
(run / 'proc.json').write_text(json.dumps({'sid': os.getsid(0), 'pgid': os.getpgid(0), 'pid': os.getpid()}))
(run / 'env.json').write_text(json.dumps({k: os.environ.get(k) for k in ('OPENAI_API_KEY', 'ROUTELIB_DIR', 'HSGATE_SLOT_TEST', 'HSGATE_IN_GATE', 'HSGATE_SLOT_DIR')}))
area = [l.split('"')[1] for l in Path(a[1]).read_text().splitlines() if l.startswith('area')][0]
if scen not in ('noboot', 'dead-boot', 'hang-boot'):   # (hsap's `gameplay` event: the game got to play)
    (run / 'live' / 'out.jsonl').write_text(json.dumps({'ev': 'gameplay', 't': 0.0, 'frame': 1}) + '\n')


def summary(outcome, rec=None, decisions=9, routes=None):
    s = {'run': tag, 'outcome': outcome, 'decisions': decisions}
    if routes is not None:
        s['routes'] = routes
    if rec is not None:
        s['recover'] = rec
    (run / 'summary.json').write_text(json.dumps(s))


def play(attempts, how):
    cause, at = cfg.get('cause', 'wall'), cfg.get('at', [0.0, 100.0, 30.0])
    book = tactics.Book(opt['--tactics-dir'])
    src = opt['--tactics-source']
    for k, (tac, outcome, gain) in enumerate(attempts):
        book.record(tac, cause, outcome, map=area, at=at, gain_m=gain, source=src, run=tag, block=f'{tag}#0', why='made up')
    worked = next((t for t, o, g in attempts if o == 'worked'), None)
    book.add_block(map=area, at=at, cause=cause, why='made up', tried=[t for t, o, g in attempts], worked=worked, how=how, s=12.5, target='want', run=tag, source=src)
    rows = [{'kind': 'recover', 'n': 3, 'target': 'want', 'status': 'blocked', 'at': at, 'why': 'stuck', 'cause': cause}]
    rows.append({'kind': 'recover', 'n': 7, 'target': 'want', 'status': 'recovered', 'rung': worked, 'at': at, 's': 12.5} if how == 'recovered'
                else {'kind': 'recover', 'n': 7, 'target': 'want', 'status': 'marked-bad', 'at': at, 'rungs': [t for t, o, g in attempts], 's': 20.0})
    (run / 'transcript.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    r = test_routelib.FakeRun(run, tag, map=area, start=(0.0, 100.0, 21.0))
    r.leg('run 0 60 radius 2.5 timeout 20', [(0, 100, 30)], 'stuck', detail='20.00 m from the point')
    r.write()
    rec = {'on': True, 'blocks': 1, 'recovered': int(how == 'recovered'), 'marked_bad': int(how != 'recovered'), 'left': 0, 'open': 0, 'longest_s': 12.5,
           'rungs': {'recover:' + t: 1 for t, o, g in attempts}, 'episodes': [{'target': 'want', 'at': at[:2], 'cause': cause, 'rungs': [t for t, o, g in attempts], 'how': how, 's': 12.5}]}
    routes = routelib.RouteLib(os.environ['ROUTELIB_DIR']).import_run(run, label=tag) if os.environ.get('ROUTELIB_DIR') else None   # (as pilot.py does at its end)
    summary('solved' if how == 'recovered' else 'gave up: every open goal failed', rec, routes=routes)


if scen == 'worked':
    play([('sidestep', 'failed', 0.1), ('angle', 'failed', -0.2), ('roll', 'worked', 3.2)], 'recovered')
elif scen == 'nothing':
    play([('sidestep', 'failed', 0.0), ('angle', 'failed', 0.1)], 'marked-bad')
elif scen == 'noboot':
    summary('no gameplay')
elif scen == 'dead-boot':     # (the pilot dies before the game ever played: nothing written)
    sys.exit(1)
elif scen == 'hang-boot':     # (the game never gets to play and the pilot waits; it ends when asked)
    while 'end' not in steps.read_text().split():
        time.sleep(0.05)
elif scen == 'crash':
    sys.exit(3)
elif scen == 'crash-kid':     # (dies on its own with its hsap still running in a session of its own)
    import subprocess
    kid = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'], start_new_session=True)
    (run / 'kid.pid').write_text(str(kid.pid))
    time.sleep(2.5)
    sys.exit(3)
elif scen == 'crash-state':   # (dies after it walked: its files can be imported, it did not import them itself)
    r = test_routelib.FakeRun(run, tag, map=area, start=(0.0, 100.0, 21.0))
    r.leg('run 0 60 radius 2.5 timeout 20', [(0, 100, 30)], 'stuck', detail='20.00 m from the point')
    r.write()
    sys.exit(3)
elif scen.startswith('slow'):
    time.sleep(float(scen.split(':')[1]))
    play([('roll', 'worked', 2.0)], 'recovered')
elif scen in ('hang-soft', 'hang-hard'):
    if scen == 'hang-hard':   # (a pilot that ignores SIGTERM, with an hsap of its own in a session of its own, as the real one has)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        import subprocess
        kid = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'], start_new_session=True)
        (run / 'kid.pid').write_text(str(kid.pid))
    while True:
        if scen == 'hang-soft' and 'end' in steps.read_text().split():
            summary('wall')
            break
        time.sleep(0.05)
'''

SAVE_TOOL = r'''
import json, sys
from pathlib import Path
a = sys.argv[1:]
out = Path(a[a.index('--out') + 1])
(out / 'save' / 'user').mkdir(parents=True)
(out / 'argv.json').write_text(json.dumps(a))
print('made', out)
'''


class Env:
    """A private world for one group of checks: library, Book, copy, saves library, fake pilot and save tool, caps and spend ledger."""

    def __init__(self, tmp, name):
        self.dir = Path(tmp) / name
        d = self.dir
        self.lib, self.book, self.root, self.copy, self.saves_lib = d / 'lib', d / 'book', d / 'root', d / 'copy', d / 'saves-library'
        self.fake, self.tool, self.caps, self.spend = d / 'fake' / 'pilot.py', d / 'tool.py', d / 'caps.json', d / 'spend.jsonl'
        fl = FakeLib(self.lib)
        fl.cluster(M, (0.0, 100.0, 30.0), (0.0, 60.0), 'wall', runs=3)                                                  # c1: three runs, a way on 30 m ahead
        fl.cluster(M, (50.0, 100.0, 30.0), (50.3, 30.2), 'door-side', runs=1)                                           # c2: the door itself is the want
        fl.cluster(M, (100.0, 100.0, 30.0), (100.0, 60.0), 'wall', runs=1)                                              # c3: walked past since
        fl.walk_past(M, (100.0, 100.0, 30.0), '2026-11-12T10:00:00')
        fl.cluster(M, (150.0, 100.0, 30.0), None, 'wall', runs=1)                                                       # c4: no want
        fl.cluster(M, (200.0, 100.0, 3.0), (200.0, 40.0), 'wall', runs=1, length=3.0)                                   # c5: the track starts 3 m before it
        fl.cluster(M, (250.0, 100.0, 30.0), (250.0, 60.0), 'wall', runs=1,                                              # c6: a gap in the samples 4 m before it
                   pts=[[0.0, 250.0, 100.0, 5.0, 1]] + [[float(k), 250.0, 100.0, 25.0 + k, 1] for k in range(1, 6)])
        fl.cluster(M, (300.0, 100.0, 30.0), (300.0, 60.0), 'door-side', runs=1)                                         # c7: a second door-side cluster
        fl.cluster(M, (350.0, 100.0, 30.0), (351.0, 31.0), 'held', runs=1)                                              # c8: held, the want a little to the side (the straight run still meets it)
        fl.cluster(D, (20.0, 50.0, 20.0), (20.0, 40.0), 'ledge-up', runs=5, age='adult')                                # a map without an age in its name
        fl.write()
        (d / 'copy').mkdir(parents=True)
        (self.copy / 'built-from.txt').write_text('63ddacdc9a82a4ffb8675d3f8d38c21ae811704f\n')
        (self.copy / 'top_prepared.bin').write_bytes(b'prepared')
        for b in ('explore17-field-child-day', 'coop-field-adult-day'):
            (self.saves_lib / b).mkdir(parents=True)
        for name, area, age, pos in (('proven-field', M, 'child', [0.0, 100.0, 0.0]), ('proven-near5', M, 'child', [200.0, 100.0, 0.0]), ('proven-back', M, 'child', [0.0, 100.0, -150.0]),
                                     ('proven-dungeon', D, 'adult', [20.0, 50.0, 0.0]), ('proven-far', M, 'child', [1000.0, 100.0, 0.0]), ('proven-elsewhere', 'Elsewhere_Child', 'child', [0.0, 0.0, 0.0])):
            (self.saves_lib / name / 'save' / 'user').mkdir(parents=True)   # (a library entry as the harness keeps it: the user folder and its entry file)
            (self.saves_lib / name / '.entry.json').write_text(json.dumps({'decoded': {'slots': [{'slot': 'slot_00', 'status': 'ok', 'area': area, 'pos': pos, 'age': age}], 'newest': 'slot_00'},
                                                                          'proven': ['2026-11-11 06:58: run made-up loads it']}))
        self.fake.parent.mkdir(parents=True)
        self.fake.write_text(FAKE_PILOT % {'code': str(HERE)})
        (self.fake.parent / 'fake.json').write_text('{}')
        self.tool.write_text(SAVE_TOOL)
        self.caps.write_text(json.dumps({'per_run_usd': 3.0, 'per_night_usd': 50.0, 'total_usd': 4000.0}))
        self.spend.write_text('')

    def argv(self, *extra, night='2026-11-17', cmd='plan'):
        return [cmd, '--lib', str(self.lib), '--tactics-dir', str(self.book), '--root', str(self.root), '--night', night, '--copy', str(self.copy), '--pilot', str(self.fake),
                '--save-tool', str(self.tool), '--saves-library', str(self.saves_lib), '--world', '', '--caps', str(self.caps), '--spend-ledger', str(self.spend)] + list(extra)

    def plan(self, *extra, night='2026-11-17', name=None):
        rc, out = cli(self.argv(*extra, night=night) + (['--plan-name', name] if name else []))
        assert rc == 0, out
        return selfplay.load_plan(self.root / (name or f'SelfPlay-{night}'))

    def configure(self, plan, **scen):
        """What the fake pilot does for each session tag (default worked): {tag: {scen, at, cause}} with the plan's own place and cause."""
        cfg = {s['tag']: {'scen': scen.get(s['tag'], 'worked'), 'at': s['at'], 'cause': s['cause']} for s in plan['sessions']}
        (self.fake.parent / 'fake.json').write_text(json.dumps(cfg))

    def runs(self):
        return self.fake.parent / 'runs'


def patch_plan(plan, **kw):
    """The plan with some fields replaced (timing keys merge); written back so a subprocess sees it too."""
    p = copy.deepcopy(plan)
    for k, v in kw.items():
        if k == 'timing':
            p['timing'] = {**p['timing'], **v}
        else:
            p[k] = v
    return p


def save_plan(plan):
    out = {k: v for k, v in plan.items() if k != 'plan_path'}
    Path(plan['plan_path']).write_text(json.dumps(out, indent=1))


# ---------------------------------------------------------------------------------------------------------- the checks

def geometry_checks(env):
    lib = routelib.RouteLib(env.lib)
    m = lib.map(M)
    cl = {c['id']: c for c in m.clusters()}
    # a visit runs straight at the want: a stuck point the straight line from the approach misses by more than 1.5 m cannot be visited (hold 1 walked round every block)
    lib2 = routelib.RouteLib(env.lib)
    for s in lib2.map(M).stuck:
        if s['at'][0] == 350.0 and s['at'][2] == 30.0:
            s['want'] = [370.0, 30.0]
    lib2.map(M).touch()
    got = {(c['map'], c['cluster']): c for c in selfplay.candidates(lib2, tactics.Book(env.dir / 'nobook', readonly=True), selfplay.Ledger(env.dir / 'l.jsonl'), '2026-12-21')[0]}
    check(got[(M, 'c8')]['approach'] is None and 'passes' in got[(M, 'c8')]['no_approach'] and got[(M, 'c1')]['approach'] is not None,
          f'a want to the side that the straight run misses: no visit ({got[(M, "c8")]["no_approach"]})')
    check(sorted(cl) == ['c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'c7', 'c8'], f'the made-up library has its eight clusters ({sorted(cl)})')
    check(cl['c3']['resolved'] and not cl['c1']['resolved'] and cl['c4']['want'] is None, 'one is resolved, one has no want')
    ap, why = selfplay.approach_point(m, cl['c1'])
    pts = {tuple(p[1:4]) for t in m.tracks for p in t['pts']}
    check(ap is not None and tuple(ap['pos']) in pts, f'the approach is a point a run walked ({ap})')
    check(abs(ap['pos'][2] - 21.0) < 1e-6 and ap['approach_m'] == 9.0 and ap['straight'] == 1.0 and ap['age'] == 'child', f'9 m of path before the stuck point on a straight track ({ap})')
    ap5, why5 = selfplay.approach_point(m, cl['c5'])
    check(ap5 is None and '3.0 m' in why5, f'a track that starts 3 m before the stuck point gives no approach ({why5})')
    ap6, why6 = selfplay.approach_point(m, cl['c6'])
    check(ap6 is None and '4.0 m' in why6, f'a gap in the samples ends the walk back: only 4 m are walked ({why6})')
    apd, _ = selfplay.approach_point(lib.map(D), lib.map(D).clusters()[0])
    check(apd['age'] == 'adult' and apd['pos'] == [20.0, 50.0, 11.0], f'a dungeon map takes its age from the track ({apd})')
    check(selfplay.yaw_toward([0, 100, 21], (0, 60)) == 0.0 and abs(selfplay.yaw_toward([0, 100, 21], (10, 21)) - math.pi / 2) < 1e-9, 'the yaw is the save tool\'s: radians, 0 along +z, 90 degrees along +x')
    # a track that winds (a long way round for a short chord) is the worse approach: the straight one of another run wins
    fl = FakeLib(env.dir / 'lib-wind')
    wind = [[float(k), 0.0 + (3.0 if k % 2 else -3.0) * (1 if k < 40 else 0), 100.0, 0.0 + k * 0.25, 1] for k in range(41)]
    fl.cluster(M, (0.0, 100.0, 10.0), (0.0, 50.0), 'wall', runs=1, pts=wind)
    fl.cluster(M, (0.0, 100.0, 10.0), (0.0, 50.0), 'wall', runs=1, length=20.0, ts='2026-11-11T10:00:00')
    fl.write()
    mm = routelib.RouteLib(env.dir / 'lib-wind').map(M)
    c = mm.clusters()[0]
    wap, _ = selfplay.approach_point(mm, c)
    check(wap is not None and wap['straight'] > 0.95, f'the straight approach is chosen over a winding one ({wap})')


def plan_checks(env):
    # a dry run reads and prints, writes nothing
    rc, out = cli(env.argv('--dry-run'))
    check(rc == 0 and 'dry run: nothing written' in out and 'SelfPlay-2026-11-17-1' in out and not env.root.exists(), f'a dry run prints the plan and writes nothing ({rc}, {out[-120:]!r})')
    plan = env.plan()
    names = [(s['map'], s['cluster']) for s in plan['sessions']]
    check(names == [(D, 'c1'), (M, 'c1'), (M, 'c2')], f'the most hurting open clusters come first: 5 runs, 3 runs, then the first of those that stopped one ({names})')
    check(plan['considered']['clusters'] == 9 and plan['considered']['eligible'] == 5 and plan['considered']['skipped'] == {'resolved': 1, 'no want': 1, 'no approach': 2},
          f'the clusters that cannot be visited are counted by reason ({plan["considered"]})')
    s0, s1, s2 = plan['sessions']
    check(s0['cause'] == 'ledge-up' and s0['age'] == 'adult' and s0['base_save'] == 'coop-field-adult-day' and s1['base_save'] == 'explore17-field-child-day', 'the age picks the base save')
    check(all(s['mode'] == 'explore' for s in plan['sessions']) and plan['model'] is None, 'the default mode is explore; no model')
    check(8.0 <= s1['start']['approach_m'] <= 10.0 and s1['start']['pos'] == [0.0, 100.0, 21.0] and s1['start']['yaw'] == 0.0 and s1['target']['want'] == [0.0, 60.0], f'a session starts on the track 9 m before the stuck point, facing the want ({s1["start"]})')
    check(s2['start']['yaw'] == 0.033 and s2['target']['want'] == [50.3, 30.2], f'a want 0.4 m from the stuck point is aimed at from 9 m: 0.033 rad off the heading ({s2["start"]})')
    check(s1['target']['radius'] == 2.0 and s2['target']['radius'] == 0.5, f'the target\'s radius is under the gap that stopped the runs, between 0.5 and 2 m ({s1["target"]["radius"]}, {s2["target"]["radius"]})')
    check(s1['proven'] is None and s1['start_why'] is None and s1['base_save'] == 'explore17-field-child-day', 'a session that starts at an approach point is no proven-save session')
    o = s1['old']
    check(o['library_tried'] == [] and [r['tactic'] for r in o['ranking'][:3]] == ['sidestep', 'angle', 'roll'] and len(o['production']) >= 10 and o['untried_here'][:3] == ['sidestep', 'angle', 'roll'],
          f'the plan records the cluster\'s old tactics and ranking ({o["ranking"][:3]})')
    check(s1['expected_attempts'] == 12 and s2['expected_attempts'] == 10 and s1['value']['runs'] == 3 and s1['value']['stops'] == 3, f'the attempts to expect: the ladder, the cause\'s tactics and the budget ({s1["expected_attempts"]}, {s2["expected_attempts"]}, {s1["value"]})')
    folder = Path(plan['dir'])
    check((folder / 'plan.json').is_file() and (folder / 'book-before.json').is_file() and len(list((folder / 'segments').glob('*.toml'))) == 3, 'the plan folder holds plan.json, the Book snapshot and a segment per session')
    snap = json.loads((folder / 'book-before.json').read_text())
    check(snap['summary']['attempts'] == 0 and 'wall' in snap['ranks'] and snap['ranks']['wall'][0]['tactic'] == 'sidestep', 'the Book\'s summary and every cause\'s ranking are kept as they were')
    led = [json.loads(ln) for ln in (env.root / 'ledger.jsonl').read_text().splitlines()]
    check(len(led) == 3 and all(r['kind'] == 'planned' and r['night'] == '2026-11-17' for r in led), 'a planned row per session goes to the ledger')
    rc, out = cli(env.argv())
    check(rc == 2 and 'exists' in out, f'a plan is written once ({rc}, {out[-100:]!r})')
    # the Book changes the order: a cause that has been tried everywhere at M c1's place is worth less than an unknown one
    book = tactics.Book(env.book)
    for tac in tactics.ORDER['wall']:
        for _ in range(3):
            book.record(tac, 'wall', 'failed', map=M, at=[0.0, 100.0, 30.0], source='live')
    p2 = env.plan(night='2026-11-20', name='knowing')
    names = [(s['map'], s['cluster']) for s in p2['sessions']]
    check(names == [(D, 'c1'), (M, 'c2'), (M, 'c8')], f'what the Book knows lowers a cluster: M c1 (39 attempts there) falls behind the unknown door cluster, and a second door-side one counts less ({names})')
    check(p2['considered']['eligible'] == 5, 'every eligible cluster is still valued')
    # a cluster in the book with a mode asked for: the production ladder at a known stuck place
    p3 = env.plan('--only', f'{M}:c1=ranked', '--only', f'{D}:c1', night='2026-11-21', name='proof')
    check([(s['map'], s['cluster'], s['mode']) for s in p3['sessions']] == [(M, 'c1', 'ranked'), (D, 'c1', 'explore'), (M, 'c2', 'explore')],
          f'--only puts the asked clusters first with their own mode ({[(s["cluster"], s["mode"]) for s in p3["sessions"]]})')
    check(p3['sessions'][0]['expected_attempts'] == 5, f'a ranked visit expects the ladder\'s five rungs ({p3["sessions"][0]["expected_attempts"]})')
    rc, out = cli(env.argv('--only', 'Nowhere:c9', night='2026-11-22', cmd='plan') + ['--plan-name', 'bad'])
    check(rc == 2 and 'not an open cluster' in out, f'an --only that is not a visitable cluster is refused ({rc}, {out[-120:]!r})')
    rc, out = cli(env.argv('--only', f'{M}:c1=fast', night='2026-11-22') + ['--plan-name', 'bad'])
    check(rc == 2 and 'mode one of' in out, 'an unknown mode is refused')
    no_copy = env.argv(night='2026-11-23') + ['--plan-name', 'nocopy']
    del no_copy[no_copy.index('--copy'):no_copy.index('--copy') + 2]
    kept = os.environ.pop('PILOT_COPY', None)
    try:
        check(selfplay.default_copy() is None, 'with no --copy and no $PILOT_COPY there is no game copy (the folder is this machine\'s own value: no default)')
        rc, out = cli(no_copy)
        check(rc == 2 and 'no game copy' in out and not (env.root / 'nocopy').exists(), f'a plan with no game copy is refused ({rc}, {out[-120:]!r})')
        os.environ['PILOT_COPY'] = str(env.copy)
        check(selfplay.default_copy() == Path(env.copy), '$PILOT_COPY is the default copy')
    finally:
        os.environ.pop('PILOT_COPY', None)
        if kept is not None:
            os.environ['PILOT_COPY'] = kept
    rc, out = cli(env.argv('--hold-seconds', '1200', night='2026-11-22') + ['--plan-name', 'bad'])
    check(rc == 2 and 'at most 1100' in out, 'a hold over 1,100 s is refused at planning')
    rc, out = cli(env.argv('--hold-seconds', '300', night='2026-11-22') + ['--plan-name', 'bad'])
    check(rc == 2 and 'no room for one session' in out, f'a hold with no room for a session is refused ({out[-120:]!r})')
    p4 = env.plan('--hold-seconds', '700', night='2026-11-23', name='small')
    check(len(p4['sessions']) == 1, f'sessions are sized to fit the hold: 700 s hold takes one 270 s session with its 70 s to end ({len(p4["sessions"])})')
    p5 = env.plan('--max-sessions', '1', night='2026-11-24', name='one')
    check(len(p5['sessions']) == 1 and p5['sessions'][0]['cluster'] == 'c1', 'at most N sessions')
    return plan


def diversity_and_nights_checks(env):
    # the same (map, cause) twice tonight counts less: after the door-side c2 the held c8 comes before the second door-side c7
    p = env.plan('--max-sessions', '4', '--hold-seconds', '1100', '--wall', '180', night='2026-12-01', name='wide')
    order = [(s['map'], s['cluster']) for s in p['sessions']]
    check(order == [(D, 'c1'), (M, 'c1'), (M, 'c2'), (M, 'c8')], f'a second cluster of one cause on one map counts less: the held c8 comes before the second door-side c7 ({order})')
    # the same night, a second plan: what the first chose is left alone
    p2 = env.plan('--max-sessions', '2', night='2026-12-01', name='again')
    check([(s['map'], s['cluster']) for s in p2['sessions']] == [(M, 'c7')], f'a second plan of the same night takes what the first left ({[(s["map"], s["cluster"]) for s in p2["sessions"]]})')
    led = selfplay.Ledger(env.root / 'ledger.jsonl')
    check(all(led.cooled(M, at, '2026-12-01', 3) for at in ([0.0, 100.0, 30.0], [50.0, 100.0, 30.0])), 'a cluster planned tonight is cooled tonight')
    check(led.cooled(M, [0.0, 100.0, 30.0], '2026-12-02', 3) is None, 'a plan that never ran does not use up a cluster for the next night')
    # a visit counts for three nights, then the place is open again
    led.add(kind='visited', night='2026-12-05', plan='x', map=M, cluster='c1', at=[0.0, 100.0, 30.0], status='done')
    check(led.cooled(M, [0.5, 100.0, 30.5], '2026-12-05', 3) and led.cooled(M, [0.0, 100.0, 30.0], '2026-12-07', 3), 'visited tonight and two nights ago: left alone (a place is one place within 3 m)')
    check(led.cooled(M, [0.0, 100.0, 30.0], '2026-12-08', 3) is None and led.cooled(D, [0.0, 100.0, 30.0], '2026-12-05', 3) is None, 'three nights later it is open again; another map is another place')
    led.add(kind='visited', night='2026-12-10', plan='x', map=D, cluster='c1', at=[20.0, 50.0, 20.0], status='done')
    p3 = env.plan('--max-sessions', '1', night='2026-12-11', name='spread')
    check((p3['sessions'][0]['map'], p3['sessions'][0]['cluster']) == (M, 'c1'), f'tomorrow the cluster visited today is skipped: the next night takes another ({p3["sessions"][0]["map"]} {p3["sessions"][0]["cluster"]})')
    p4 = env.plan('--max-sessions', '1', '--ignore-ledger', night='2026-12-11', name='ignoring')
    check((p4['sessions'][0]['map'], p4['sessions'][0]['cluster']) == (D, 'c1'), '--ignore-ledger plans as if none had been visited')
    p5 = env.plan('--max-sessions', '1', '--only', f'{D}:c1', night='2026-12-11', name='forced')
    check((p5['sessions'][0]['map'], p5['sessions'][0]['cluster']) == (D, 'c1'), '--only may ask for a cluster that was visited lately (a proof run)')


def segment_checks(env, plan):
    for s in plan['sessions']:
        seg = pilot.Segment(s['segment'])
        t = seg.goals[0].targets[0]
        check(seg.name == s['tag'] and seg.area == s['map'] and seg.humanize == 0 and seg.save == s['save'] and seg.boot == 'continue', f'{s["name"]}: the segment parses: area, humanize 0, the save ({seg.area}, {seg.humanize})')
        check(seg.straight is True, f'{s["name"]}: the visit runs straight at the want (no offline planner routes round the block)')
        check(len(seg.goals) == 1 and seg.goals[0].kind == 'reach' and [t.x, t.z] == s['target']['want'] and t.kind == 'reach' and t.radius == s['target']['radius'], f'{s["name"]}: one reach goal at the cluster\'s want')
        check(seg.wall == s['wall'] and seg.budget == s['budget_s'] and not seg.goals[0].cond.met({'PlayerStatus.MaxLife': 20}) and not seg.goals[0].cond.met({}) and seg.watch == ['PlayerStatus.MaxLife'], 'a small budget; the flag condition never comes true')
    text = Path(plan['sessions'][0]['segment']).read_text()
    check('Testland' not in Path(selfplay.__file__).read_text() and 'Dungeonland' not in Path(selfplay.__file__).read_text(), 'no map name in the code')
    check(text.startswith('# generated by selfplay.py'), 'the segment says where it came from')


def saves_checks(env, plan):
    cmd = selfplay.save_command(plan, plan['sessions'][0])
    want = [sys.executable, plan['save_tool'], '--from', 'coop-field-adult-day', '--out', plan['sessions'][0]['save'], '--start', f'{D}:20.00,50.00,11.00,0.000', '--age', 'adult', '--time', 'day', '--game', plan['copy']]
    check(cmd == want, f'the save command: base save, out, start map:x,y,z,yaw, age, time, game ({cmd})')
    p8 = env.plan('--only', f'{M}:c8', '--max-sessions', '1', night='2026-12-20', name='sideways')
    c8 = selfplay.save_command(p8, p8['sessions'][0])
    check(c8[c8.index('--start') + 1] == f'{M}:350.00,100.00,21.00,0.100', f'a want a little to the side gives its yaw in radians ({c8[c8.index("--start") + 1]})')
    check(all(not Path(x['save']).exists() for x in plan['sessions']), 'nothing is made before `saves`')
    rc, out = cli(['saves', str(Path(plan['dir']) / 'plan.json')])
    check(rc == 0 and all(Path(x['save']).is_dir() for x in plan['sessions']), f'`saves` makes every save ({rc})')
    made = json.loads((Path(plan['sessions'][1]['save']) / 'argv.json').read_text())
    check(made == selfplay.save_command(plan, plan['sessions'][1])[2:], 'the tool was called with the planned arguments')
    rc, out = cli(['saves', str(Path(plan['dir']) / 'plan.json')])
    check(rc == 0 and out.count('exists, kept') == 3, 'a save that exists is kept')


def refusal_checks(env, plan):
    plan = selfplay.load_plan(Path(plan['dir']) / 'plan.json')
    errs = selfplay.plan_errors(plan)
    check(errs == [], f'a good plan has no refusals ({errs})')
    rc, out = cli(['check', plan['plan_path']])
    check(rc == 0 and 'ok' in out, 'check says ok')

    def refused(p, what, text, out=None):
        e = selfplay.plan_errors(p, out)
        check(any(text in x for x in e), f'refused: {what} ({e[:2]})')
        return e
    p = copy.deepcopy(plan)
    p['sessions'][1]['save'] = str(env.dir / 'no-such-save')
    refused(p, 'a missing save', 'is not a game user folder')
    cf = Path(plan['copy'])
    (cf / 'built-from.txt').rename(cf / 'built-from.off')
    refused(plan, 'a copy that is not stamped', 'is not stamped')
    (cf / 'built-from.off').rename(cf / 'built-from.txt')
    (cf / 'top_prepared.bin').rename(cf / 'top_prepared.off')
    refused(plan, 'a copy that is not warm', 'is not warm')
    (cf / 'top_prepared.off').rename(cf / 'top_prepared.bin')
    (cf / 'top_prepared.bin').rename(cf / 'top_prepared.off')
    (cf / 'cache').mkdir(exist_ok=True)
    (cf / 'cache' / 'game_prepared.bin').write_bytes(b'prepared')   # (the game writes the marker into its cache folder)
    check(not selfplay.copy_errors(cf), 'a copy warmed in its cache folder is warm')
    (cf / 'cache' / 'game_prepared.bin').unlink()
    (cf / 'cache').rmdir()
    (cf / 'top_prepared.off').rename(cf / 'top_prepared.bin')
    check(selfplay.copy_errors(env.dir / 'nowhere') and not selfplay.copy_errors(cf), 'a copy that is no folder is refused')
    refused(patch_plan(plan, hold_seconds=1200), 'a hold over 1,100 s', 'at most 1100')
    long_wall = copy.deepcopy(plan)
    long_wall['sessions'][0]['wall'] = 1000
    e = refused(long_wall, 'a session whose wall is longer than the hold', 'is longer than the hold has')
    check(any('do not fit' in x for x in e), 'and sessions that together do not fit')
    short_wall = copy.deepcopy(plan)
    short_wall['sessions'][0]['wall'] = 100
    refused(short_wall, 'a session shorter than a boot', 'under the')
    # spend
    env.spend.write_text(json.dumps({'ts': time.time(), 'cost_usd': 60.0, 'kind': 'decision'}) + '\n')
    refused(plan, 'a night already over its cap', 'night\'s spend')
    env.spend.write_text(json.dumps({'ts': time.time() - 30 * 86400, 'cost_usd': 60.0}) + '\n')
    check(not any('spend' in x for x in selfplay.plan_errors(plan)), 'spend of another night does not count')
    env.spend.write_text(json.dumps({'ts': time.time() - 30 * 86400, 'cost_usd': 4100.0}) + '\n')
    refused(plan, 'the total at its cap', 'total spend')
    env.spend.write_text('')
    env.caps.rename(env.caps.with_suffix('.off'))
    refused(plan, 'no caps file', 'no readable caps file')
    env.caps.with_suffix('.off').rename(env.caps)
    # segments
    seg = Path(plan['sessions'][0]['segment'])
    good = seg.read_text()
    seg.write_text(good.replace('kind = "reach"', 'kind = "reach"\nnot toml at all ='))
    refused(plan, 'a segment that does not parse', 'does not parse with pilot.Segment')
    seg.write_text(good.replace('area = "Dungeonland"', 'area = "Elsewhere"'))
    refused(plan, 'a segment on another map', 'the segment is on')
    seg.write_text(good.replace('humanize = 0', 'humanize = 2'))
    refused(plan, 'a segment that humanizes', 'humanize 0')
    seg.write_text(good)
    check(not selfplay.plan_errors(plan), 'the segment restored: no refusals')
    # the rest
    dup = copy.deepcopy(plan)
    dup['sessions'][1]['tag'] = dup['sessions'][0]['tag']
    refused(dup, 'a duplicate tag', 'duplicate')
    refused(patch_plan(plan, model='some-model'), 'a plan that names a model', 'names a model')
    badmode = copy.deepcopy(plan)
    badmode['sessions'][0]['mode'] = 'fast'
    refused(badmode, 'an unknown mode', 'is none of')
    (env.runs() / plan['sessions'][0]['tag']).mkdir(parents=True)
    refused(plan, 'a tag the pilot already has a run folder for', 'run folder')
    (env.runs() / plan['sessions'][0]['tag']).rmdir()
    refused(plan, 'an output folder that exists', 'exists (a hold writes a new folder)', out=env.dir)
    no_pilot = patch_plan(plan, pilot=str(env.dir / 'nothing.py'))
    refused(no_pilot, 'no pilot.py', 'pilot ')
    gone = patch_plan(plan, book_before=str(env.dir / 'none.json'))
    refused(gone, 'no Book snapshot', 'Book snapshot')
    check(len(plan['sessions']) == 3, 'the plan under test was not changed by the refusal checks')


def command_checks(env, plan):
    s = plan['sessions'][1]
    cmd = selfplay.pilot_command(plan, s, 250)
    check(cmd[:4] == [sys.executable, '-I', '-B', plan['pilot']] and cmd[4:6] == ['run', s['segment']], 'the pilot is run isolated: python -I -B pilot.py run <segment>')
    opt = {cmd[i]: cmd[i + 1] for i in range(6, len(cmd) - 1) if cmd[i].startswith('--')}
    check(opt['--decider'] == 'rules' and opt['--lessons'] == 'off' and opt['--tactics'] == 'explore' and opt['--tactics-source'] == 'selfplay' and opt['--humanize'] == '0', f'rules decider, no lessons, explore, filed as selfplay, humanize 0 ({opt})')
    check(opt['--tag'] == s['tag'] and opt['--copy'] == plan['copy'] and opt['--save'] == s['save'] and opt['--wall'] == '250' and opt['--tactics-dir'] == plan['tactics_dir'] and opt['--bad-points'] == plan['bad_points'], 'tag, copy, save, wall, the Book\'s folder and a bad-point memory of the hold\'s own')
    check(not any(x in cmd for x in ('--planner', '--vision', '--api-base', 'openai-decisions')), 'nothing in it can spend: no planner, no vision, no model decider')
    env_ = selfplay.child_env({'OPENAI_API_KEY': 'k', 'ROUTELIB_DIR': '/x', 'HSGATE_SLOT_DIR': '/s', 'HSGATE_INTEL_SLOT_DIR': '/s', 'HSGATE_SLOT_TEST': '1', 'HSGATE_SLOT_NODESKTOP': '1', 'HSGATE_IN_GATE': '1', 'KEEP': 'yes'})
    check(env_ == {'KEEP': 'yes'} and selfplay.child_env({'OPENAI_API_KEY': 'k', 'ROUTELIB_DIR': '/x', 'KEEP': 'yes'}, '/the/lib') == {'KEEP': 'yes', 'ROUTELIB_DIR': '/the/lib'},
          f'the slot variables and the key are unset, ROUTELIB_DIR is the plan\'s library, the rest stays ({env_})')
    # the waiter's command
    q, m = '/tmp/quiet-x.lock', '/tmp/meas-x.lock'
    qc = selfplay.queue_command(plan, plan['dir'] + '/hold', name='PilotLearn', code='/frozen/code', quiet=q, measuring=m)
    want = ['setsid', 'env', '--default-signal=HUP', 'flock', '-w', '43200', q, 'flock', '-x', m, 'timeout', '--signal=TERM', '--kill-after=20', '1100', sys.executable, '-I', '-B',
            '/frozen/code/pilot/selfplay.py', 'run', plan['plan_path'], '--out', plan['dir'] + '/hold', '--name', 'PilotLearn']
    check(qc == want, f'the waiter: setsid env --default-signal=HUP flock -w 43200 QUIET flock -x MEASURING timeout --signal=TERM --kill-after=20 1100 python -I -B <frozen>/pilot/selfplay.py run ... ({qc})')
    check(qc.index(q) < qc.index(m) and qc[0] == 'setsid' and 'PilotLearn' in qc, 'quiet before measuring, setsid first, the name in the command')
    check(selfplay.queue_command(patch_plan(plan, hold_seconds=900), 'x', name='N', quiet=q, measuring=m)[13] == '900', 'the timeout is the plan\'s hold')
    saved_locks = selfplay.QUIET, selfplay.MEASURING
    selfplay.QUIET = selfplay.MEASURING = None   # (the lock files are this machine's own values, set by the environment: with none the waiter is refused, nothing is guessed)
    try:
        check(raises(lambda: selfplay.queue_command(plan, 'x', name='N'), selfplay.PlanError) and raises(lambda: selfplay.queue_command(plan, 'x', name='N', quiet=q), selfplay.PlanError),
              'a waiter with no quiet lock or no measuring lock is refused')
        lines = []
        rc = selfplay.do_queue(plan, plan['dir'] + '/hold', 'N', '/frozen/code', dry_run=True, log=lines.append)
        check(rc == 2 and any('PILOT_QUIET_LOCK' in x and 'PILOT_MEASURING_LOCK' in x for x in lines) and not any(x.startswith('command:') for x in lines), f'queue says which settings are missing and starts nothing ({rc}, {lines[-1:]})')
    finally:
        selfplay.QUIET, selfplay.MEASURING = saved_locks
    r = subprocess.run([sys.executable, '-I', '-B', '-c', f'import sys; sys.path.insert(0, {str(HERE)!r}); import selfplay; print(selfplay.QUIET, selfplay.MEASURING)'],
                       env={**os.environ, 'PILOT_QUIET_LOCK': q, 'PILOT_MEASURING_LOCK': m}, capture_output=True, text=True)
    check(r.stdout.split() == [q, m], f'the settings are $PILOT_QUIET_LOCK and $PILOT_MEASURING_LOCK ({r.stdout!r} {r.stderr[-100:]!r})')
    r = subprocess.run([sys.executable, '-I', '-B', '-c', f'import sys; sys.path.insert(0, {str(HERE)!r}); import selfplay; print(selfplay.QUIET, selfplay.MEASURING)'],
                       env={k: v for k, v in os.environ.items() if k not in ('PILOT_QUIET_LOCK', 'PILOT_MEASURING_LOCK')}, capture_output=True, text=True)
    check(r.stdout.split() == ['None', 'None'], f'and with neither set there is no default ({r.stdout!r})')
    check(selfplay.waiter_args(want, 'PilotLearn') == plan['plan_path'] and selfplay.waiter_args(want, 'Other') is None and selfplay.waiter_args(['python3', 'selfplay.py', 'nightly', '--name', 'PilotLearn'], 'PilotLearn') is None,
          'a command line is recognised as a waiter by its name and its `run`')


def proven_checks(env):
    """A session on a proven library save exactly as it is: no --start, the pilot's own first leg walks to the want; mixed with --start ones; the plan says why."""
    p = env.plan('--proven-saves', 'proven-field', 'proven-dungeon', '--max-sessions', '3', night='2027-04-01', name='proven')
    check([(s['map'], s['cluster'], s['start'] is None) for s in p['sessions']] == [(M, 'c1', True), (D, 'c1', True), (M, 'c2', False)],
          f'a proven-save session each, first, then the --start ones ({[(s["map"], s["cluster"], s["start"] is None) for s in p["sessions"]]})')
    s0, s1, s2 = p['sessions']
    entry = str((env.saves_lib / 'proven-field').resolve())
    check(s0['save'] == entry and s0['base_save'] is None and s0['start'] is None and 'with no --start' in s0['start_why'] and 'proven-field' in s0['start_why'] and 'first leg' in s0['start_why'], f'no --start: the library save as it is, and why ({s0["start_why"]})')
    check(s0['proven']['save'] == 'proven-field' and s0['proven']['proof'].startswith('2026-11-11') and 29 < s0['proven']['metres'] < 31 and s0['target']['want'] == [0.0, 60.0], f'the plan records the proof, the walk and the want ({s0["proven"]})')
    check(s2['proven'] is None and s2['start'] is not None and s1['age'] == 'adult', 'the --start session beside them is unchanged')
    check(pilot.Segment(s0['segment']).save == entry and pilot.Segment(s0['segment']).goals[0].targets[0].z == 60.0 and s0['budget_s'] == 120, 'its segment starts from the library entry')
    check(selfplay.save_command(p, s0) is None and selfplay.save_command(p, s2) is not None, 'no hs_make_save command for a proven save')
    rc, out = cli(['saves', p['plan_path']])
    check(rc == 0 and out.count('used as it is: nothing to make') == 2 and Path(s2['save']).is_dir() and not (env.saves_lib / 'proven-field' / 'argv.json').exists(), f'`saves` makes only the --start save and never touches the library ({rc})')
    check(selfplay.plan_errors(selfplay.load_plan(p['plan_path'])) == [], f'check accepts the mix ({selfplay.plan_errors(selfplay.load_plan(p["plan_path"]))})')
    # they share max-sessions, and come first
    p2 = env.plan('--proven-saves', 'proven-field', 'proven-dungeon', '--max-sessions', '1', night='2027-04-02', name='proven-one')
    check([(s['map'], s['cluster'], s['start'] is None) for s in p2['sessions']] == [(M, 'c1', True)], 'proven-save sessions share the sessions of the plan')
    # a cluster no approach can be made to is fine for a proven save: it only needs to be walked to
    p3 = env.plan('--proven-saves', 'proven-near5', '--max-sessions', '1', night='2027-04-03', name='proven-near')
    check([(s['map'], s['cluster'], s['start']) for s in p3['sessions']] == [(M, 'c5', None)] and p3['considered']['skipped'].get('no approach') == 2, f'a cluster without an approach is visited from a proven save ({p3["sessions"][0]["cluster"]})')
    # a far one gets more game time for the walk
    p4 = env.plan('--proven-saves', 'proven-back', '--max-sessions', '1', night='2027-04-04', name='proven-back')
    check(p4['sessions'][0]['proven']['metres'] > 170 and p4['sessions'][0]['budget_s'] == 140, f'a farther cluster gets more game time ({p4["sessions"][0]["budget_s"]} s for {p4["sessions"][0]["proven"]["metres"]} m)')
    # no cluster within reach of the save: told in the plan, the rest of the plan stands
    p5 = env.plan('--proven-saves', 'proven-far', 'proven-elsewhere', '--max-sessions', '2', night='2027-04-05', name='proven-none')
    check(len(p5['proven_notes']) == 2 and 'no open cluster within 250 m' in p5['proven_notes'][0] and all(s['start'] is not None for s in p5['sessions']) and len(p5['sessions']) == 2, f'a proven save with nothing in reach is told, not an error ({p5["proven_notes"]})')
    rc, out = cli(env.argv('--proven-saves', 'proven-far', '--dry-run', night='2027-04-05', cmd='plan'))
    check(rc == 0 and 'proven save proven-far' in out, 'and printed')
    rc, out = cli(env.argv('--proven-saves', 'no-such-entry', night='2027-04-06') + ['--plan-name', 'bad'])
    check(rc == 2 and 'no saves-library entry' in out, f'an entry that is not in the library is refused ({rc}; {out[-120:]!r})')
    # --only keeps its cluster: the proven save takes the next best
    p6 = env.plan('--only', f'{M}:c1=ranked', '--proven-saves', 'proven-field', '--max-sessions', '2', night='2027-04-07', name='proven-only')
    check([(s['map'], s['cluster'], s['start'] is None, s['mode']) for s in p6['sessions']] == [(M, 'c2', True, 'explore'), (M, 'c1', False, 'ranked')], f'--only is not pushed out by a proven save ({[(s["cluster"], s["mode"]) for s in p6["sessions"]]})')
    check(selfplay.make_parser().parse_args(['nightly', '--no-seed', '--proven-saves', 'a', 'b']).proven_saves == ['a', 'b'], 'nightly takes --proven-saves NAME ... and --no-seed')


def hold_budget_checks(env):
    """The hold with a fake pilot: the time budget, shutdown by pid, the environment the pilot gets."""
    plan = env.plan('--max-sessions', '3', night='2026-12-30', name='hold-a')
    cli(['saves', plan['plan_path']])
    small = {'reserve_s': 2.0, 'tail_s': 1.0, 'soft_s': 1.0, 'grace_s': 1.0, 'term_soft_s': 1.0, 'term_grace_s': 1.0, 'min_wall_s': 6.0, 'overhead_s': 3.0}
    # (A) the budget: a quick session, one that never ends (ignores SIGTERM), and a third that would not fit
    pa = patch_plan(plan, hold_seconds=20, timing=small)
    for s in pa['sessions']:
        s['wall'] = 6
    env.configure(pa, **{pa['sessions'][1]['tag']: 'hang-hard'})
    os.environ.update({'OPENAI_API_KEY': 'sk-test', 'ROUTELIB_DIR': '/nonexistent', 'HSGATE_SLOT_TEST': '1', 'HSGATE_IN_GATE': '1', 'HSGATE_SLOT_DIR': '/s'})
    t0 = time.monotonic()
    try:
        rc = selfplay.run_hold(pa, env.dir / 'out-a', log=lambda *_: None, importer=selfplay.library_importer(pa), name='TestWaiter')
    finally:
        for k in ('OPENAI_API_KEY', 'ROUTELIB_DIR', 'HSGATE_SLOT_TEST', 'HSGATE_IN_GATE', 'HSGATE_SLOT_DIR'):
            os.environ.pop(k, None)
    took = time.monotonic() - t0
    res = json.loads((env.dir / 'out-a' / 'result.json').read_text())
    rows = {r['name']: r for r in res['rows']}
    r1, r2, r3 = (rows[s['name']] for s in pa['sessions'])
    check(rc == 0 and r1['status'] == 'done' and r2['status'] == 'stopped' and r3['status'].startswith('not started: '), f'quick session done, the stuck one stopped, the third not started ({r1["status"]}, {r2["status"]}, {r3["status"]})')
    check(took < 20 - 2 + 1, f'the hold ends inside its hold seconds ({took:.1f} s of 20)')
    check(r2['ended_by'] == 'killed' and r2['stopped_by'] == 'deadline' and not alive(int((env.runs() / r2['tag'] / 'pid').read_text())), f'a pilot that ignores SIGTERM is killed by pid and gone ({r2["ended_by"]})')
    kid = int((env.runs() / r2['tag'] / 'kid.pid').read_text())
    check(r2['descendants_stopped'] == 1 and not alive(kid), f'what hung below the killed pilot (its hsap, in a session of its own) is stopped too ({r2["descendants_stopped"]}, alive {alive(kid)})')
    check('end' in (env.runs() / r2['tag'] / 'live' / 'steps.txt').read_text().split(), 'it was asked to end first, through the live channel')
    check(6 + 1 + 1 + 1 <= r2['seconds'] <= 6 + 1 + 1 + 1 + 4, f'ended at its wall plus the tail, the soft end and the grace ({r2["seconds"]} s)')
    check(not (env.runs() / r3['tag']).exists(), 'the session that would not fit was never started')
    proc = json.loads((env.runs() / r1['tag'] / 'proc.json').read_text())
    check(proc['sid'] == proc['pid'] == proc['pgid'] and proc['sid'] != os.getsid(0), 'the pilot runs in its own session and process group')
    envs = json.loads((env.runs() / r1['tag'] / 'env.json').read_text())
    check(envs.pop('ROUTELIB_DIR') == pa['lib'] and all(v is None for v in envs.values()), f'the key and the slot variables never reach the pilot, ROUTELIB_DIR is the plan\'s library ({envs})')
    argv = json.loads((env.runs() / r1['tag'] / 'argv.json').read_text())
    check(argv[argv.index('--wall') + 1] == '6' and argv[argv.index('--tactics-source') + 1] == 'selfplay' and argv[argv.index('--lessons') + 1] == 'off', 'the fake pilot got the real command')
    led = [json.loads(ln) for ln in (env.root / 'ledger.jsonl').read_text().splitlines()]
    check(any(r['kind'] == 'visited' and r['tag'] == r1['tag'] for r in led) and any(r['kind'] == 'failed' and r['tag'] == r2['tag'] for r in led), 'a session that played is a visit in the ledger; one that was killed before it wrote anything is not')

    # (B) the wall is shortened to what is left
    plan_b = env.plan('--max-sessions', '2', night='2026-12-31', name='hold-b')
    cli(['saves', plan_b['plan_path']])
    pb = patch_plan(plan_b, hold_seconds=16, timing=small)
    for s in pb['sessions']:
        s['wall'] = 9
    env.configure(pb, **{pb['sessions'][0]['tag']: 'slow:2'})
    selfplay.run_hold(pb, env.dir / 'out-b', log=lambda *_: None, importer=lambda *a: {}, name='TestWaiter')
    walls = [int(json.loads((env.runs() / s['tag'] / 'argv.json').read_text())[json.loads((env.runs() / s['tag'] / 'argv.json').read_text()).index('--wall') + 1]) for s in pb['sessions']]
    check(walls[0] == 9 and 6 <= walls[1] < 9, f'a session\'s wall is shortened to what the hold has left, never below the minimum ({walls})')

    # (D) a game that never reaches play: a row no-gameplay (not a stop, not a crash), and no visit
    plan_d = env.plan('--max-sessions', '1', night='2027-01-05', name='hold-d')
    cli(['saves', plan_d['plan_path']])
    pd = patch_plan(plan_d, hold_seconds=20, timing={**small, 'min_wall_s': 3.0})
    pd['sessions'][0]['wall'] = 3
    env.configure(pd, **{pd['sessions'][0]['tag']: 'hang-boot'})
    selfplay.run_hold(pd, env.dir / 'out-d', log=lambda *_: None, importer=lambda *a: {}, name='TestWaiter')
    rd = json.loads((env.dir / 'out-d' / 'result.json').read_text())['rows'][0]
    led = [json.loads(ln) for ln in (env.root / 'ledger.jsonl').read_text().splitlines()]
    check(rd['status'] == 'no-gameplay' and rd['gameplay'] is False and rd['stopped_by'] == 'deadline' and rd['ended_by'] == 'ended' and 'import' not in rd, f'a game that never played, ended at the deadline, is a no-gameplay row ({rd["status"]}, {rd.get("ended_by")})')
    check(any(r['kind'] == 'failed' and r['tag'] == rd['tag'] for r in led), 'and no visit')


def hold_result_checks(env):
    """The rows of a hold, the Book diff, the report and the import of the runs into the library."""
    small = {'reserve_s': 2.0, 'tail_s': 1.0, 'soft_s': 1.0, 'grace_s': 1.0, 'term_soft_s': 1.0, 'term_grace_s': 1.0, 'min_wall_s': 6.0, 'overhead_s': 3.0}
    plan_c = env.plan('--only', f'{M}:c1', '--max-sessions', '3', night='2027-01-02', name='hold-c')
    cli(['saves', plan_c['plan_path']])
    pc = patch_plan(plan_c, hold_seconds=60, timing=small)
    for s in pc['sessions']:
        s['wall'] = 6
    extra = copy.deepcopy(pc['sessions'][0])
    extra.update(name='hold-c-4', tag='hold-c-4')
    pc['sessions'].append(extra)
    extra5 = copy.deepcopy(pc['sessions'][0])
    extra5.update(name='hold-c-5', tag='hold-c-5')
    pc['sessions'].append(extra5)
    extra6 = copy.deepcopy(pc['sessions'][0])
    extra6.update(name='hold-c-6', tag='hold-c-6')
    pc['sessions'].append(extra6)
    extra7 = copy.deepcopy(pc['sessions'][0])
    extra7.update(name='hold-c-7', tag='hold-c-7')
    pc['sessions'].append(extra7)
    env.configure(pc, **{pc['sessions'][1]['tag']: 'nothing', pc['sessions'][2]['tag']: 'noboot', 'hold-c-4': 'crash', 'hold-c-5': 'crash-state', 'hold-c-6': 'crash-kid', 'hold-c-7': 'dead-boot'})
    snap_runs = len(routelib.RouteLib(env.lib).runs()['runs'])
    attempts_before = tactics.Book(env.book).summary()['attempts']
    out = env.dir / 'out-c'
    rc = selfplay.run_hold(pc, out, log=lambda *_: None, importer=selfplay.library_importer(pc), name='TestWaiter')
    res = json.loads((out / 'result.json').read_text())
    rows = res['rows']
    check(rc == 0 and [r['status'] for r in rows] == ['done', 'done', 'no-gameplay', 'no-summary', 'no-summary', 'no-summary', 'no-gameplay'], f'a row per session: done, done, no gameplay, no summary x3, no gameplay ({[r["status"] for r in rows]})')
    w = rows[0]
    check(w['tried'] == ['sidestep', 'angle', 'roll'] and w['worked'] == ['roll'] and w['recovered_by'] == ['roll'] and w['blocks'] == 1 and w['recovered'] == 1 and w['marked_bad'] == 0, f'the row says what was tried, what worked and which rung got past ({w["tried"]}, {w["worked"]}, {w["recovered_by"]})')
    check(w['rungs'] == {'sidestep': 1, 'angle': 1, 'roll': 1} and w['causes_seen'] == ['wall'] and w['block_rows'][0]['worked'] == 'roll' and w['attempts'][2]['gain_m'] == 3.2, 'from the summary, the transcript and the Book: rungs, causes, block rows, gains')
    n = rows[1]
    check(n['tried'] == ['sidestep', 'angle'] and n['worked'] == [] and n['recovered_by'] == [] and n['marked_bad'] == 1 and n['outcome'].startswith('gave up'), f'a visit that found nothing says so ({n["tried"]}, {n["marked_bad"]})')
    check(rows[2]['attempts'] == [] and rows[3]['exit'] == 3 and rows[3]['status'] == 'no-summary' and rows[3]['gameplay'] is True, 'no gameplay and a crash leave empty rows with the exit code')
    check(rows[6]['status'] == 'no-gameplay' and rows[6]['exit'] == 1 and rows[6]['gameplay'] is False and 'import' not in rows[6], 'a pilot that died before the game played is no-gameplay, not a crash')
    check(w['import']['tag'] == w['tag'] and w['import']['metres'] > 0 and 'import' not in rows[2] and 'import' not in rows[3] and 'import_error' in rows[3], f'the pilot\'s own import is the row\'s; no gameplay and a crash with nothing to import have none ({w.get("import")})')
    check(rows[4]['import']['tag'] == 'hold-c-5' and rows[4]['import']['metres'] > 0, f'a run that died before it imported itself is imported by the hold ({rows[4].get("import")}, {rows[4].get("import_error")})')
    kid = int((env.runs() / 'hold-c-6' / 'kid.pid').read_text())
    check(rows[5]['descendants_stopped'] == 1 and not alive(kid) and rows[3]['descendants_stopped'] == 0, f'a pilot that died on its own leaves nothing of its tree running ({rows[5]["descendants_stopped"]}, alive {alive(kid)})')
    lib = routelib.RouteLib(env.lib)
    check(len(lib.runs()['runs']) == snap_runs + 3 and any(r['run'].startswith(w['tag']) for r in lib.runs()['runs']), 'the library knows the new runs, each once')
    check((out / w['name'] / 'summary.json').is_file() and (out / w['name'] / 'transcript.jsonl').is_file() and (out / w['name'] / 'pilot.out').is_file(), 'the summary and the transcript are kept with the hold')
    diff = res['book']['diff']
    check(diff['attempts'] == 5 and diff['blocks'] == 2 and diff['sources'] == {'selfplay': 5}, f'the Book\'s diff: 5 attempts and 2 blocks, all selfplay ({diff["attempts"]}, {diff["blocks"]}, {diff["sources"]})')
    check(diff['causes']['wall']['roll'] == {'n': 1, 'wins': 1, 'now': {'n': 1, 'wins': 1}} and diff['causes']['wall']['sidestep']['n'] == 1 and diff['causes']['wall']['angle']['wins'] == 0
          and diff['causes']['ledge-up']['sidestep']['n'] == 1 and 'roll' not in diff['causes']['ledge-up'], f'per cause and tactic: attempts and wins gained ({diff["causes"]})')
    check(tactics.Book(env.book).summary()['attempts'] == attempts_before + 5, 'the Book on disk gained them')
    selfplay.write_table(out, pc, rows)
    table = (out / 'table.md').read_text()
    check('| done |' in table and 'sidestep, angle, roll' in table and 'no-gameplay' in table, 'the table lists the sessions')
    text = selfplay.write_report(pc, out)
    rep = json.loads((out / 'report.json').read_text())
    s0 = rep['sessions'][0]
    change = {r['tactic']: r for r in s0['ranking'][s0['cause']]['context']}
    check(s0['tried'] == ['sidestep', 'angle', 'roll'] and s0['worked'] == ['roll'] and s0['expected_attempts'] == pc['sessions'][0]['expected_attempts'], 'the report: tried, worked, expected')
    check(change['roll']['from'] == 3 and change['roll']['to'] == 1 and change['roll']['n_from'] == 0 and change['roll']['n_to'] == 1 and change['roll']['wins_to'] == 1 and change['roll']['score_to'] > change['roll']['score_from'],
          f'the report shows the ranking at that place moving: roll third to first ({change.get("roll")})')
    check(change['sidestep']['to'] > change['sidestep']['from'], 'and the failed ones down')
    check('## ' + pc['sessions'][0]['name'] in text and 'got past by roll' in text and 'roll: place 3 -> 1' in text and 'Book: +5 attempts' in text, 'the text report names the cluster, what worked and the Book\'s change')
    check(selfplay.book_diff(res['book']['before'], res['book']['before']) == {'attempts': 0, 'blocks': 0, 'demos': 0, 'sources': {}, 'causes': {}}, 'no change is an empty diff')
    rows_move = selfplay.rank_change([{'tactic': 'a', 'score': .5, 'n': 0, 'wins': 0}, {'tactic': 'b', 'score': .4, 'n': 0, 'wins': 0}], [{'tactic': 'b', 'score': .6, 'n': 1, 'wins': 1}, {'tactic': 'a', 'score': .5, 'n': 0, 'wins': 0}])
    check([r['tactic'] for r in rows_move] == ['b', 'a'] and rows_move[0]['from'] == 2 and rows_move[0]['to'] == 1, 'rank_change: what moved up first')
    # a plan that fails its refusals starts nothing
    rc, _out = cli(['run', plan_c['plan_path'], '--out', str(env.dir / 'out-never'), '--name', 'x'])
    check(rc == 2 and not (env.dir / 'out-never').exists(), 'run refuses a plan whose tags the pilot has used already, and creates nothing')


def term_checks(env):
    """The hold itself gets SIGTERM (the lane's timeout): the running pilot is ended by pid, the rows and the result are written, exit 143."""
    plan = env.plan('--max-sessions', '2', night='2027-02-01', name='term')
    cli(['saves', plan['plan_path']])
    small = {'reserve_s': 5.0, 'tail_s': 2.0, 'soft_s': 1.0, 'grace_s': 1.0, 'term_soft_s': 1.0, 'term_grace_s': 1.0, 'min_wall_s': 6.0, 'overhead_s': 4.0}
    pt = patch_plan(plan, hold_seconds=60, timing=small)
    for s in pt['sessions']:
        s['wall'] = 20
    save_plan(pt)
    env.configure(pt, **{pt['sessions'][0]['tag']: 'hang-hard'})
    out = env.dir / 'out-term'
    p = subprocess.Popen([sys.executable, '-I', '-B', str(HERE / 'selfplay.py'), 'run', pt['plan_path'], '--out', str(out), '--name', 'TermTest'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    pidf = env.runs() / pt['sessions'][0]['tag'] / 'pid'
    check(wait_for(pidf.exists, 30), 'the hold started its first pilot')
    time.sleep(0.5)
    pid = int(pidf.read_text())
    p.send_signal(signal.SIGTERM)
    try:
        rc = p.wait(timeout=20)
    except subprocess.TimeoutExpired:
        p.kill()
        rc = None
    output = p.stdout.read()
    check(rc == 143, f'the hold exits 143 on SIGTERM ({rc}; {output[-200:]!r})')
    check(not alive(pid), 'the pilot that was running is gone: ended by pid')
    res = json.loads((out / 'result.json').read_text())
    check(res['rc'] == 143 and res['rows'][0]['status'] == 'stopped' and res['rows'][0]['stopped_by'] == 'signal' and res['rows'][1]['status'].startswith('not started')
          and res['rows'][-1]['status'] == 'stopped by a signal', f'the rows say stopped, not started, stopped by a signal ({[r["status"] for r in res["rows"]]})')
    check((out / 'table.md').is_file() and (out / 'report.md').is_file(), 'the table and the report are written after the stop')
    check(not (env.runs() / pt['sessions'][1]['tag']).exists(), 'no further session was started')


def waiter_checks(env, tmp):
    """The real chain (setsid, env, flock, flock, timeout, python) on test locks: a queued waiter is found by its name and stops by pid file; nightly is idempotent."""
    name = f'SelfplayTest{os.getpid()}'
    import tactics_seed
    real_seed = tactics_seed.seed
    quiet_before = selfplay.QUIET, selfplay.MEASURING
    selfplay.QUIET, selfplay.MEASURING = str(tmp / 'quiet.lock'), str(tmp / 'measuring.lock')
    code = tmp / 'code'
    code.mkdir()
    (code / 'pilot').symlink_to(HERE)
    held = os.open(selfplay.QUIET, os.O_CREAT | os.O_RDWR)
    fcntl.flock(held, fcntl.LOCK_EX)    # (the main lane holds the window: the waiter has to queue)
    night_a, night_b = '2027-03-01', '2027-03-02'
    base = ['--name', name, '--code', str(code)]
    folder_a = env.root / f'SelfPlay-{night_a}'
    try:
        # the second-waiter refusal and the pid file, with a fake waiter that only looks like one
        fake = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)', 'selfplay.py', 'run', 'PLAN', '--out', 'X', '--name', name], start_new_session=True)
        time.sleep(0.2)
        pl = env.plan('--max-sessions', '1', night='2027-02-20', name='fakewait')
        cli(['saves', pl['plan_path']])
        lines = []
        rc = selfplay.do_queue(pl, env.dir / 'out-q', name, str(code), dry_run=True, log=lines.append)
        check(rc == 2 and any('one at a time' in x and str(fake.pid) in x for x in lines), f'a second waiter beside a live one is refused ({rc}, {lines[-1:]})')
        rc = selfplay.do_queue(pl, env.dir / 'out-q', name + 'Other', str(code), dry_run=True, log=lines.append)
        check(rc == 0 and any(x.startswith('command: setsid env --default-signal=HUP flock -w 43200') for x in lines), 'another name is no waiter of mine; --dry-run prints the command and starts nothing')
        fake.kill()
        fake.wait()
        check(not selfplay.waiters(name), 'a killed waiter is no waiter')
        # nightly: plan, saves, check, queue; the waiter is queued behind the held lock
        seeded = []
        (env.lib / 'runs.json').write_text(json.dumps({'format': routelib.FORMAT, 'runs': [{'run': 'old', 'folder': str(tmp / 'old-run-folder')}], 'builds': {}}))

        def fake_seed(book, roots, sensor=None, source='journal', log=lambda *_: None):
            seeded.append({'dir': book.dir, 'roots': [str(r) for r in roots], 'sensor': type(sensor).__name__})
            book.record('sidestep', 'wall', 'failed', map=M, at=[0.0, 100.0, 30.0], source='journal', key='seedstub')
            return {'runs': 1, 'attempts': 1, 'blocks': 0, 'demos': 0, 'skipped': 0}
        tactics_seed.seed = fake_seed
        rc, out = cli(env.argv('--max-sessions', '3', *base, night=night_a, cmd='nightly'))
        check(len(seeded) == 1 and seeded[0]['dir'] == Path(env.book).resolve() and seeded[0]['sensor'] == 'Sensor' and seeded[0]['roots'] == [str(env.fake.parent / 'runs'), str(tmp / 'old-run-folder')]
              and 'the Book was seeded from 1 new runs' in out, f'nightly seeds the Book from the pilot\'s runs and the library\'s run folders first ({seeded}, {out[:200]!r})')
        check(json.loads((folder_a / 'book-before.json').read_text())['summary']['attempts'] == 1, 'and plans on the seeded Book: the plan\'s snapshot has what the seeding added')
        pidf = folder_a / 'waiter.pid'
        check(rc == 0 and pidf.is_file() and (folder_a / 'plan.json').is_file() and 'waiter pid' in out, f'nightly plans, makes the saves, checks and queues ({rc}; {out[-200:]!r})')
        plan = selfplay.load_plan(folder_a)
        check(all(Path(s['save']).is_dir() for s in plan['sessions']) and len(plan['sessions']) == 3, 'the saves were made by nightly')
        w = selfplay.waiters(name)
        check(w and all(Path(x['plan']) == folder_a / 'plan.json' for x in w), f'the queued waiter is found by its name ({w})')
        text_before = (folder_a / 'plan.json').read_text()
        ledger_before = (env.root / 'ledger.jsonl').read_text()
        pids_before = sorted(x['pid'] for x in w)
        rc, out = cli(env.argv('--max-sessions', '3', *base, night=night_a, cmd='nightly'))
        check(len(seeded) == 1, 'a night that has its plan is not seeded again')
        check(rc == 0 and 'already queued or running' in out and (folder_a / 'plan.json').read_text() == text_before and (env.root / 'ledger.jsonl').read_text() == ledger_before
              and sorted(x['pid'] for x in selfplay.waiters(name)) == pids_before, f'nightly again for the same night changes nothing and queues nothing ({rc}; {out[-120:]!r})')
        rc, out = cli(env.argv('--max-sessions', '3', *base, night=night_b, cmd='nightly'))
        check(rc == 2 and 'one at a time' in out and not (env.root / f'SelfPlay-{night_b}').exists(), f'a night beside a waiter of its own is refused and plans nothing ({rc}; {out[-120:]!r})')
        # stop by pid file
        rc, out = cli(['stop', plan['plan_path'], '--name', name])
        check(rc == 0 and not pidf.exists() and wait_for(lambda: not selfplay.waiters(name), 5) and 'stopping the waiter' in out, f'stop ends the queued waiter and its chain by pid file ({rc}; {out[-160:]!r})')
        rc, out = cli(['stop', plan['plan_path'], '--name', name])
        check(rc == 1 and 'no waiter pid file' in out, 'stop with no pid file says so')
        # a stale pid file (a recycled number) is not killed
        pidf.write_text(f'{os.getpid()}\n')
        rc, out = cli(['stop', plan['plan_path'], '--name', name])
        check(rc == 1 and 'not a waiter' in out and alive(os.getpid()) and not pidf.exists(), 'a pid that is no waiter is not killed')
        # over the cap: nightly refuses before anything is written
        env.spend.write_text(json.dumps({'ts': time.time(), 'cost_usd': 55.0}) + '\n')
        rc, out = cli(env.argv('--max-sessions', '3', *base, night=night_b, cmd='nightly'))
        check(rc == 2 and 'at its cap' in out and not (env.root / f'SelfPlay-{night_b}').exists(), f'nightly refuses when the night\'s spend is over its cap ({rc}; {out[-120:]!r})')
        env.spend.write_text('')
        # queue again for the same night (the hold folder does not exist: stopped before it started), then release the lock: the hold runs
        rc, out = cli(env.argv('--max-sessions', '3', *base, night=night_a, cmd='nightly'))
        check(rc == 0 and pidf.is_file(), f'after a stop the night can be queued again ({rc})')
        fcntl.flock(held, fcntl.LOCK_UN)
        hold = folder_a / 'hold'
        check(wait_for(lambda: (hold / 'report.md').is_file(), 90, 0.25), 'the lock was released: the waiter ran the hold and wrote its report')
        res = json.loads((hold / 'result.json').read_text())
        check(res['rc'] == 0 and res['waiter'] == name and [r['status'] for r in res['rows']] == ['done', 'done', 'done'], f'the hold ran its three sessions through the chain ({[r.get("status") for r in res["rows"]]})')
        check(wait_for(lambda: not selfplay.waiters(name), 10), 'the waiter is gone when the hold is over')
        rc, out = cli(env.argv('--max-sessions', '3', *base, night=night_a, cmd='nightly'))
        check(rc == 0 and 'ran already' in out, f'nightly after the hold: nothing to do ({rc}; {out[-100:]!r})')
        led = [json.loads(ln) for ln in (env.root / 'ledger.jsonl').read_text().splitlines()]
        check(sum(1 for r in led if r['kind'] == 'visited' and r['night'] == night_a) == 3, 'the visits are in the ledger')
        rc, out = cli(['report', str(folder_a)])
        check(rc == 0 and 'Book: +9 attempts' in out, f'`report` prints the report after the hold ({out[:200]!r})')
        # a hold folder without a result is not run twice
        night_c = '2027-03-05'
        (env.root / f'SelfPlay-{night_c}' / 'hold').mkdir(parents=True)
        rc, out = cli(env.argv(*base, night=night_c, cmd='nightly'))
        check(rc == 2 and 'did not finish' in out, 'a hold folder with no result is not run twice')
        # a dry run writes nothing and starts nothing
        night_d = '2027-03-06'
        rc, out = cli(env.argv(*base, '--dry-run', night=night_d, cmd='nightly'))
        check(rc == 0 and 'command: setsid' in out and not (env.root / f'SelfPlay-{night_d}').exists() and not selfplay.waiters(name), 'nightly --dry-run prints the plan and the command and writes nothing')
        # a hold that is running: stop ends every process of the waiter's session, the hold ends its pilot by pid and writes its result
        night_e = '2027-03-08'
        fcntl.flock(held, fcntl.LOCK_EX)
        tactics_seed.seed = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('made up'))
        rc, out = cli(env.argv('--max-sessions', '2', *base, night=night_e, cmd='nightly'))
        check('the Book was not seeded (RuntimeError: made up)' in out and (env.root / f'SelfPlay-{night_e}' / 'plan.json').is_file(), 'a seeding that fails is told and the night is planned on the Book as it is')
        plan_e = selfplay.load_plan(env.root / f'SelfPlay-{night_e}')
        env.configure(plan_e, **{plan_e['sessions'][0]['tag']: 'hang-soft'})
        fcntl.flock(held, fcntl.LOCK_UN)
        pidfile = env.runs() / plan_e['sessions'][0]['tag'] / 'pid'
        check(rc == 0 and wait_for(pidfile.exists, 60, 0.25), 'the hold runs its first pilot')
        pilot_pid = int(pidfile.read_text())
        rc, out = cli(['stop', plan_e['plan_path'], '--name', name])
        check(rc == 0 and wait_for(lambda: not selfplay.waiters(name), 30) and not alive(pilot_pid), f'stop on a running hold: the chain ends and so does the pilot ({rc}; {out[-120:]!r})')
        res = json.loads((env.root / f'SelfPlay-{night_e}' / 'hold' / 'result.json').read_text())
        check(res['rc'] == 143 and res['rows'][0]['status'] == 'stopped' and res['rows'][0]['stopped_by'] == 'signal', f'the hold wrote its result before it went ({res["rc"]}, {res["rows"][0]["status"]})')
    finally:
        for pf in env.root.glob('*/waiter.pid'):
            try:
                selfplay.do_stop(selfplay.load_plan(pf.parent), name, grace=5, log=lambda *_: None)
            except Exception:   # noqa: BLE001  (cleanup only)
                pass
        try:
            fcntl.flock(held, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(held)
        selfplay.QUIET, selfplay.MEASURING = quiet_before
        tactics_seed.seed = real_seed


def timer_checks(tmp):
    """The nightly user timer: a transient systemd-run unit at 03:30 that fires `timer fire`, which re-arms the next night first, replaces the frozen code, and runs one
    `nightly`; a night whose earlier waiter is still queued is skipped with the reason printed. Nothing is armed without the user's word."""
    import datetime
    from types import SimpleNamespace as NS
    check(selfplay.next_calendar('03:30', datetime.datetime(2026, 11, 17, 4, 0)) == '2026-11-18 03:30:00' and selfplay.next_calendar('03:30', datetime.datetime(2026, 11, 17, 2, 0)) == '2026-11-17 03:30:00'
          and selfplay.next_calendar('03:30', datetime.datetime(2026, 11, 17, 3, 30)) == '2026-11-18 03:30:00', 'the next 03:30 strictly after now')
    a = NS(at='03:30', copy='/c/copy', code='/c/code', max_sessions=3, name='PilotLearn', refreeze='/c/refreeze.sh', root=str(tmp / 'root'), user_authorized=True, authority='the user\'s word, relayed by Main')
    argv = selfplay.timer_argv(a, '2026-11-18 03:30:00', quiet='/l/q', measuring='/l/m', python='/usr/bin/python3')
    check(argv[:7] == ['systemd-run', '--user', '--unit=pilot-selfplay-2026-11-18-033000', '--on-calendar=2026-11-18 03:30:00', '--timer-property=AccuracySec=60s', '--collect', '--setenv=PILOT_QUIET_LOCK=/l/q']
          and '--setenv=PILOT_MEASURING_LOCK=/l/m' in argv and argv[argv.index('/usr/bin/python3') + 1:argv.index('/usr/bin/python3') + 4] == ['-I', '-B', '/c/code/pilot/selfplay.py'] and 'timer' in argv and 'fire' in argv
          and '--refreeze' in argv and '--max-sessions' in argv and '--name' in argv, f'the transient unit: calendar, the two locks, the frozen code\'s timer fire ({argv})')
    ran = []
    fake = lambda cmd, **k: (ran.append(cmd), NS(returncode=0, stdout='Running timer as unit: x.timer\n', stderr=''))[1]  # noqa: E731
    refused = lambda **kw: selfplay.arm_timer(NS(**{**vars(a), **kw}), now=datetime.datetime(2026, 11, 17, 4, 0), run=fake, quiet='/l/q', measuring='/l/m')
    try:
        refused(user_authorized=False)
        check(False, 'arming needs the user\'s word')
    except selfplay.PlanError as e:
        check('user' in str(e) and not ran, f'arming without the user\'s word is refused ({e})')
    info = refused()
    saved = json.loads((tmp / 'root' / 'timer.json').read_text())
    check(info['unit'] == 'pilot-selfplay-2026-11-18-033000' and saved['unit'] == info['unit'] and saved['authority'] == a.authority and saved['calendar'] == '2026-11-18 03:30:00' and len(ran) == 1,
          f'armed once, the unit and the authority recorded ({saved["unit"]})')
    # fire: re-arm first, then the frozen code, then one nightly; a skipped night is no failure and still leaves the next night armed
    order = []
    arm = lambda args, **k: (order.append('arm'), {'unit': 'next'})[1]  # noqa: E731
    run_ok = lambda cmd, **k: (order.append('refreeze' if 'bash' in cmd[0] else cmd[0]), NS(returncode=0, stdout='frozen: x', stderr=''))[1]  # noqa: E731
    rc = selfplay.fire_timer(a, arm=arm, run=run_ok, nightly=lambda b: (order.append('nightly'), 2)[1])
    check(rc == 0 and order == ['arm', 'refreeze', 'nightly'], f'fire: the next night armed first, the code replaced, then the night ({order})')
    order.clear()
    busy = lambda cmd, **k: (order.append('refreeze'), NS(returncode=3, stdout='', stderr='a hold is running: not replacing its code'))[1]  # noqa: E731
    rc = selfplay.fire_timer(a, arm=arm, run=busy, nightly=lambda b: (order.append('nightly'), 0)[1])
    check(rc == 0 and order == ['arm', 'refreeze', 'nightly'], 'a hold of the old code is running: the code is left, the night goes on')
    order.clear()
    broke = lambda cmd, **k: (order.append('refreeze'), NS(returncode=1, stdout='', stderr='git failed'))[1]  # noqa: E731
    rc = selfplay.fire_timer(a, arm=arm, run=broke, nightly=lambda b: (order.append('nightly'), 0)[1])
    check(rc == 0 and order == ['arm', 'refreeze'], 'the code could not be frozen: no night on stale code, the next one is armed')


def main():
    with tempfile.TemporaryDirectory(prefix='test-selfplay-') as t:
        tmp = Path(t)
        env = Env(tmp, 'a')
        geometry_checks(env)
        timer_checks(tmp / 'timer')
        plan = plan_checks(env)
        segment_checks(env, plan)
        saves_checks(env, plan)
        refusal_checks(env, plan)
        command_checks(env, plan)
        env_n = Env(tmp, 'n')
        diversity_and_nights_checks(env_n)
        proven_checks(Env(tmp, 'p'))
        hold_budget_checks(Env(tmp, 'h'))
        hold_result_checks(Env(tmp, 'r'))
        env_t = Env(tmp, 't')
        term_checks(env_t)
        env_w = Env(tmp, 'w')
        waiter_checks(env_w, tmp)
    if FAILS:
        raise SystemExit(f'test_selfplay: {len(FAILS)} of {CHECKS[0]} checks FAILED')
    print(f'test_selfplay: all {CHECKS[0]} checks passed')


if __name__ == '__main__':
    main()
