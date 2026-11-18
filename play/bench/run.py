#!/usr/bin/env python3
"""The benchmark runner: plays the course (course.py) with the arms (rules, decisions, decisions+vision, decisions+vision-big)
and writes the metrics table.

  run.py plan   --pilot-dir D --segments-dir S [--entries a,b] [--arms x,y] [--kept-root R] [--copies A,B]
  run.py play   --out DIR --bench-id ID --copies A[,B] --pilot-dir D --segments-dir S [--entries ..] [--arms ..] [--hold-s 1000]
                [--kept-root R] [--shots 900] [--tas]
  run.py report --out DIR
  run.py sheet  --out DIR [--cells a,b]

`play` runs the cells one after another (or as many at once as there are game copies given: each game needs its own copy),
never starts a cell that cannot finish inside --hold-s, skips cells already done in DIR (so a second hold goes on where the
first ended) and stops every process of a cell by pid when it is over. It does NOT take the quiet-window or measuring locks:
the hold that runs it does (see the harness's skill). A cell is `pilot.py run <cut segment> --decider ... --tag <id>-<entry>-<arm>`
plus the arm's flags; with --tas the entry's scripted route is played through `pilot.py check-route` as the baseline row.
`report` runs metrics.py over every cell and writes results.json, table.md (one row per entry and arm, then one row per arm:
quality and cost per minute, per goal and per km) into DIR. `sheet` makes a contact sheet of each cell's pictures (ImageMagick).

Everything under DIR is game-derived and local: never published.
"""
import argparse
import json
import os
import queue
import re
import signal
import subprocess
import sys
import threading
import time
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'pilot'))
import course  # noqa: E402
import ghost  # noqa: E402
import metrics  # noqa: E402


def slug(arm):
    return arm.replace('+', '_')


def cell_id(bench_id, entry, arm):
    return f'{bench_id}-{entry.id}-{slug(arm)}'


def resolve_save(entry, kept_root):
    """The --save argument of an entry (None: the segment's own), and why it cannot be had when it cannot."""
    if not entry.save:
        return None, None
    if entry.save.startswith('kept:'):
        root = Path(kept_root) if kept_root else None
        folder = root / 'runs' / entry.save[5:] / 'user' if root else None
        if folder is None or not folder.is_dir():
            return None, f'the kept save {entry.save} is not under --kept-root'
        return str(folder), None
    return None, None   # a library entry or a path in the cut segment itself


def parse_only(text, entry_ids):
    """`entry:arm,entry:arm,...` as [(entry, arm)] in the order given (`arm` may be `tas`, the scripted baseline). ValueError names what is wrong:
    a pair without a colon, an unknown entry or arm, a pair twice, nothing at all."""
    pairs = []
    for part in text.split(','):
        entry_id, sep, arm = part.strip().partition(':')
        if not sep or entry_id not in entry_ids or (arm not in course.ARMS and arm != 'tas') or (entry_id, arm) in pairs:
            raise ValueError(f'--only wants entry:arm pairs of known entries {sorted(entry_ids)} and arms {list(course.ARMS) + ["tas"]}, each once; got {part!r}')
        pairs.append((entry_id, arm))
    return pairs


def plan(entries, arms, segments_dir, pilot_dir, kept_root=None, tas=False, only=None):
    """[{entry, arm, kind, missing}] for the course: `missing` names what is not there (segment, save, route). `only`: [(entry, arm)] keeps just those
    cells, in that order (a cell the entries/arms/tas of this call do not make is an error)."""
    cells = []
    segments_dir, pilot_dir = Path(segments_dir), Path(pilot_dir)
    for e in course.COURSE:
        if entries and e.id not in entries:
            continue
        why = []
        if not (segments_dir / f'{e.id}.toml').is_file():
            why.append(f'no cut segment {e.id}.toml (run mkcourse.py)')
        if e.follow and not (segments_dir / f'{e.id}.ghost.json').is_file():
            why.append(f'no ghost route {e.id}.ghost.json')
        _, bad = resolve_save(e, kept_root)
        if bad:
            why.append(bad)
        for arm in arms:
            cells.append({'entry': e.id, 'arm': arm, 'kind': 'play', 'missing': list(why)})
        if tas and e.tas:
            w = list(why)
            if not (pilot_dir / 'routes' / e.tas).is_file():
                w.append(f'no route {e.tas}')
            cells.append({'entry': e.id, 'arm': 'tas', 'kind': 'tas', 'missing': w})
    if only is not None:
        by = {(c['entry'], c['arm']): c for c in cells}
        absent = [p for p in only if p not in by]
        if absent:
            raise ValueError(f'--only names cells this plan does not make: {absent} (an arm outside --arms, a scripted baseline without --tas or without a route entry)')
        cells = [by[p] for p in only]
    return cells


def pilot_args(entry, arm_name, tag, copy, segment, save, follow_file, shots, vision_every):
    """(argv after `pilot.py`, extra environment) of one cell."""
    arm = course.ARMS[arm_name]
    argv = ['run', str(segment), '--decider', arm['decider'], '--tag', tag, '--copy', str(copy), '--wall', str(entry.wall_s),
            '--max-decisions', str(entry.max_decisions)]
    if shots:
        argv += ['--shots', str(shots)]
    if arm.get('planner'):
        argv.append('--planner')
    if save:
        argv += ['--save', save]
    if follow_file:
        argv += ['--follow', f'{entry.follow}={follow_file}']
    env = dict(arm.get('env') or {})
    v = arm.get('vision')
    if v is not None:
        argv += ['--vision', 'on', '--vision-every', str(vision_every)]
        if v.get('backend'):
            argv += ['--vision-backend', v['backend']]
        if v.get('model'):
            argv += ['--vision-model', v['model']]
    return argv, env


def family(tag, own=None):
    """pids of every live process whose command line names this run tag as a whole word (the pilot's hsap, hs-run and its game)."""
    pat = re.compile(r'(?<![\w.-])' + re.escape(tag) + r'(?![\w.-])')
    own = {os.getpid(), os.getppid()} | set(own or ())
    out = []
    for p in Path('/proc').iterdir():
        if not p.name.isdigit() or int(p.name) in own:
            continue
        try:
            cmd = (p / 'cmdline').read_bytes().replace(b'\0', b' ').decode('utf-8', 'replace')
        except OSError:
            continue
        if pat.search(cmd):
            out.append(int(p.name))
    return out


def stop_family(tag, wait_s=15.0):
    """SIGTERM to the family, SIGKILL to what is left after wait_s. Returns how many were found."""
    pids = family(tag)
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    end = time.time() + wait_s
    while time.time() < end and any(Path(f'/proc/{p}').exists() and 'Z' not in _state(p) for p in pids):
        time.sleep(0.5)
    for pid in pids:
        if Path(f'/proc/{pid}').exists() and 'Z' not in _state(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
    return len(pids)


def _state(pid):
    try:
        for line in Path(f'/proc/{pid}/status').read_text().splitlines():
            if line.startswith('State:'):
                return line.split(':', 1)[1].strip()
    except OSError:
        pass
    return 'Z'


class Runner:
    def __init__(self, a):
        self.a = a
        self.out = Path(a.out)
        (self.out / 'cells').mkdir(parents=True, exist_ok=True)
        self.pilot_dir = Path(a.pilot_dir)
        self.pilot_py = self.pilot_dir / 'pilot.py'
        self.segments_dir = Path(a.segments_dir)
        self.start = time.time()
        self.deadline = self.start + a.hold_s
        self.copies = queue.Queue()
        for c in a.copies.split(','):
            self.copies.put(c)
        self.lock = threading.Lock()
        self.stop = False
        self.grace_s = 150.0   # a pilot may run this long after its game's wall (its end step, the planner's answer) before it is stopped
        self.active = {}       # tag -> the cell's pilot process, while it runs

    def done(self, cid):
        return (self.out / 'cells' / f'{cid}.json').is_file()

    def run_cell(self, c, entry):
        cid = cell_id(self.a.bench_id, entry, c['arm'])
        copy = self.copies.get()
        rec = {'cell': cid, 'entry': entry.id, 'arm': c['arm'], 'kind': c['kind'], 'copy': copy, 'started': time.time()}
        proc, gh = None, None
        try:
            save, _ = resolve_save(entry, self.a.kept_root)
            env = dict(os.environ)
            for k in ('HSGATE_SLOT_DIR', 'HSGATE_INTEL_SLOT_DIR', 'HSGATE_SLOT_TEST', 'HSGATE_SLOT_NODESKTOP', 'HSGATE_IN_GATE'):
                env.pop(k, None)
            log = open(self.out / 'cells' / f'{cid}.log', 'w')
            segment = self.segments_dir / f'{entry.id}.toml'
            if c['kind'] == 'tas':
                route = self.pilot_dir / 'routes' / entry.tas
                argv = [sys.executable, '-I', '-B', str(self.pilot_py), 'check-route', str(route), '--segment', str(segment), '--runs', '1',
                        '--copy', copy, '--tag', cid, '--wall', str(entry.wall_s)]
                run_dir = self.pilot_dir / 'runs' / 'checks' / f'{cid}-1'
            else:
                follow_file = None
                if entry.follow:
                    follow_file = str(self.out / 'cells' / f'{cid}.follow.json')
                    route = json.loads((self.segments_dir / f'{entry.id}.ghost.json').read_text())
                    run_dir = self.pilot_dir / 'runs' / cid
                    ghost.write_follow(follow_file, route['points'][0][0], route['points'][0][1], route['area'])
                    gh = ghost.Ghost(follow_file, route, start_when=lambda: ghost.gameplay_started(run_dir))
                    gh.start()
                args, extra = pilot_args(entry, c['arm'], cid, copy, segment, save, follow_file, self.a.shots, course.VISION_EVERY_S)
                argv = [sys.executable, '-I', '-B', str(self.pilot_py)] + args
                env.update(extra)
                run_dir = self.pilot_dir / 'runs' / cid
            rec['argv'] = argv
            rec['run_dir'] = str(run_dir)
            proc = subprocess.Popen(argv, cwd=str(self.pilot_dir), env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                    start_new_session=True)
            self.active[cid] = proc
            try:
                rec['rc'] = proc.wait(timeout=entry.wall_s + self.grace_s)
            except subprocess.TimeoutExpired:
                rec['rc'] = 'timeout'
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except OSError:
                    pass
                try:
                    proc.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    pass
        except Exception as e:   # noqa: BLE001  one broken cell must not end the hold
            rec['error'] = f'{type(e).__name__}: {e}'
        finally:
            if gh:
                gh.stop()
            self.active.pop(cid, None)
            rec['stopped_leftovers'] = stop_family(cid)
            rec['ended'] = time.time()
            self.copies.put(copy)
        (self.out / 'cells' / f'{cid}.json').write_text(json.dumps(rec, indent=1))
        print(f"{cid}: rc {rec.get('rc')} {rec['ended'] - rec['started']:.0f} s{' ERROR ' + rec['error'] if rec.get('error') else ''}", flush=True)

    def on_signal(self, signum, frame):
        """The hold ended (timeout's SIGTERM) or the waiter was stopped: nothing of a running cell may outlive this process. Each pilot
        and its game are stopped by pid through the run tag, the cell is left unfinished (no record), and the process exits."""
        self.stop = True
        for tag, proc in list(self.active.items()):
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except OSError:
                pass
            stop_family(tag, wait_s=10)
        print(f'stopped by signal {signum}: {sorted(self.active)} were running', flush=True)
        os._exit(128 + signum)

    def play(self, cells):
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGTERM, self.on_signal)
            signal.signal(signal.SIGHUP, self.on_signal)
        by_id = {e.id: e for e in course.COURSE}
        todo = []
        for c in cells:
            e = by_id[c['entry']]
            cid = cell_id(self.a.bench_id, e, c['arm'])
            if c['missing']:
                print(f"{cid}: skipped, {'; '.join(c['missing'])}", flush=True)
            elif self.done(cid):
                print(f'{cid}: already done', flush=True)
            else:
                todo.append((c, e))
        threads, n_workers = [], self.copies.qsize()
        work = queue.Queue()
        for item in todo:
            work.put(item)
        deferred = []

        def worker():
            while True:
                try:
                    c, e = work.get_nowait()
                except queue.Empty:
                    return
                if self.stop or time.time() + e.wall_s + 40 > self.deadline:
                    deferred.append(cell_id(self.a.bench_id, e, c['arm']))
                    continue
                self.run_cell(c, e)
        for _ in range(n_workers):
            t = threading.Thread(target=worker)
            t.start()
            threads.append(t)
        for t in threads:
            t.join()
        if deferred:
            print('deferred to a later hold: ' + ', '.join(deferred), flush=True)
        return deferred


def load_goals(segment_path):
    seg = tomllib.loads(Path(segment_path).read_text())
    return {g['name']: g['flag'] for g in seg['goal'] if g.get('flag')}


def cell_metrics(rec, segments_dir):
    """The metrics dict of a finished cell record, written into its run folder; None when it left nothing to read."""
    run_dir = Path(rec['run_dir'])
    if rec['kind'] == 'tas':
        events = metrics.read_jsonl(run_dir / 'out.jsonl')
        if not events:
            return None
        goals = load_goals(Path(segments_dir) / f"{rec['entry']}.toml")
        m = metrics.of_route_events(events, goals, run=rec['cell'], segment=rec['entry'])
        (run_dir / 'metrics.json').write_text(json.dumps(m, indent=1))
        return m
    if not (run_dir / 'transcript.jsonl').is_file():
        return None
    return metrics.write_run(run_dir, arm=rec['arm'])


ARM_COLUMNS = ['arm', 'cells', 'goals met', 'targets done', 'play min', 'decisions', 'dec/min', 'km', 'stuck/km', 'stuck s', 'streak max',
               'inter ok/att', 'vision', 'oddities', 'USD', 'USD/min', 'USD/goal', 'USD/km']


def arm_rows(ms):
    """One summary row per arm over the cells that left metrics: sums, and ratios of sums (never means of ratios)."""
    rows = []
    for arm in sorted({m['arm'] for m in ms}, key=lambda a: (a == 'tas', list(course.ARMS).index(a) if a in course.ARMS else 99)):
        g = [m for m in ms if m['arm'] == arm]
        s = lambda k: sum((m['session'].get(k) or 0) for m in g)   # noqa: E731
        minutes = s('play_wall_s') / 60.0
        km, usd = s('km'), sum(m['cost']['total_usd'] for m in g)
        met, total = s('goals_met'), s('goals_total')
        att = [m['interactions']['attempted'] for m in g if m['interactions'].get('attempted') is not None]
        ok = sum(m['interactions']['succeeded'] or 0 for m in g if m['interactions'].get('attempted') is not None)
        vcalls = sum(m['vision']['calls'] for m in g if m.get('vision'))
        odd = sum(sum(m['vision']['oddities'].values()) for m in g if m.get('vision'))
        rows.append([arm, len(g), f'{met}/{total}', s('targets_done'), metrics.fmt(round(minutes, 1)), s('decisions'),
                     metrics.fmt(round(s('decisions') / minutes, 1) if minutes else None), metrics.fmt(round(km, 3)),
                     metrics.fmt(round(s('stuck_steps') / km, 1) if km > 0.05 else None), metrics.fmt(round(s('stuck_s_total'), 1)),
                     max((m['session'].get('streak_max') or 0) for m in g), f'{ok}/{sum(att)}' if att else '-', vcalls if vcalls else '-',
                     odd if vcalls else '-', metrics.fmt(round(usd, 4)), metrics.fmt(round(usd / minutes, 4) if minutes else None),
                     metrics.fmt(round(usd / met, 4) if met else None), metrics.fmt(round(usd / km, 3) if km > 0.05 else None)])
    return rows


def cell_rows(items):
    head = ['entry', 'arm', 'outcome', 'goals met', 'targets done', 'play s', 'dec', 'dec/min', 'km', 'stuck/km', 'stuck s', 'streak max',
            'inter ok/att', 'vision', 'oddities', 'USD', 'USD/min']
    rows = []
    for rec, m in items:
        s, c, v, i = m['session'], m['cost'], m.get('vision'), m['interactions']
        rows.append([rec['entry'], m['arm'], (m.get('outcome') or '-')[:30], f"{s['goals_met']}/{s['goals_total']}", s.get('targets_done', '-'),
                     metrics.fmt(s['play_wall_s']), s['decisions'], metrics.fmt(s['decisions_per_min_wall']), metrics.fmt(s['km']),
                     metrics.fmt(s['stuck_steps_per_km']), metrics.fmt(s['stuck_s_total']), s['streak_max'],
                     '-' if i.get('attempted') is None else f"{i['succeeded']}/{i['attempted']}", v['calls'] if v else '-',
                     sum(v['oddities'].values()) if v else '-', metrics.fmt(c['total_usd'], 4), metrics.fmt(c['per_min_usd'], 4)])
    return head, rows


def md_table(head, rows):
    return '\n'.join(['| ' + ' | '.join(head) + ' |', '|' + '|'.join(['---'] * len(head)) + '|'] +
                     ['| ' + ' | '.join(str(x) for x in r) + ' |' for r in rows])


def report(a):
    out = Path(a.out)
    recs = [json.loads(p.read_text()) for p in sorted((out / 'cells').glob('*.json')) if not p.name.endswith('.ghost.json') and
            not p.name.endswith('.follow.json')]
    recs = [r for r in recs if 'cell' in r]
    order = {e.id: i for i, e in enumerate(course.COURSE)}
    arms = list(course.ARMS) + ['tas']
    recs.sort(key=lambda r: (order.get(r['entry'], 99), arms.index(r['arm']) if r['arm'] in arms else 99))
    items, missing = [], []
    for r in recs:
        m = cell_metrics(r, a.segments_dir)
        if m is None:
            missing.append(r['cell'])
        else:
            items.append((r, m))
    head, rows = cell_rows(items)
    text = ['# Benchmark ' + out.name, '', 'One row per entry and arm (metrics.py; stuck steps are move steps that ended `stuck`):', '',
            md_table(head, rows), '', 'Per arm over every cell above (sums; ratios are ratios of sums):', '',
            md_table(ARM_COLUMNS, arm_rows([m for _, m in items])), '']
    if missing:
        text += ['Cells with nothing to read (the run left no transcript): ' + ', '.join(missing), '']
    (out / 'table.md').write_text('\n'.join(text))
    (out / 'results.json').write_text(json.dumps({'cells': [{'record': r, 'metrics': m} for r, m in items], 'no_data': missing}, indent=1))
    print('\n'.join(text))
    return 0


def sheet(a):
    """A contact sheet per cell of the vision frames kept and the game's own pictures (copy/runs/<tag>/shots), with ImageMagick."""
    out = Path(a.out)
    (out / 'sheets').mkdir(exist_ok=True)
    for p in sorted((out / 'cells').glob('*.json')):
        r = json.loads(p.read_text())
        if 'cell' not in r or (a.cells and r['cell'] not in a.cells.split(',')):
            continue
        run_dir = Path(r['run_dir'])
        imgs = sorted((run_dir / 'vision').glob('f*.jp*g')) + sorted((run_dir / 'vision').glob('f*.png'))
        shots = Path(r['copy']) / 'runs' / r['cell'] / 'shots'
        imgs += sorted(shots.glob('*.png'))[:6] if shots.is_dir() else []
        if not imgs:
            continue
        dest = out / 'sheets' / f"{r['cell']}.jpg"
        subprocess.run(['magick', 'montage', '-label', '%f', *map(str, imgs[:12]), '-tile', '4x', '-geometry', '320x180+4+4', '-pointsize', '12',
                        str(dest)], check=False, timeout=120)
        print(dest, flush=True)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    for name in ('plan', 'play', 'report', 'sheet'):
        p = sub.add_parser(name)
        p.add_argument('--out', default=str(HERE / 'runs' / 'bench'))
        p.add_argument('--bench-id', default='bench')
        p.add_argument('--pilot-dir', default=str(HERE.parent / 'pilot'))
        p.add_argument('--segments-dir', default=str(HERE / 'segments'))
        p.add_argument('--entries')
        p.add_argument('--arms', default=','.join(course.DEFAULT_ARMS))
        p.add_argument('--kept-root')
        p.add_argument('--copies', default='')
        p.add_argument('--hold-s', type=float, default=1000.0)
        p.add_argument('--shots', type=int, default=900)
        p.add_argument('--tas', action='store_true')
        p.add_argument('--cells')
        p.add_argument('--only', help='entry:arm,entry:arm,... : just these cells, in this order (a scripted baseline as entry:tas); --entries, --arms and --tas follow from it')
    a = ap.parse_args()
    entries = set(a.entries.split(',')) if a.entries else None
    arms = [x for x in a.arms.split(',') if x]
    only = None
    if a.only:
        try:
            only = parse_only(a.only, {e.id for e in course.COURSE})
        except ValueError as e:
            ap.error(str(e))
        entries, arms, a.tas = {p[0] for p in only}, sorted({p[1] for p in only} - {'tas'}, key=list(course.ARMS).index), any(p[1] == 'tas' for p in only)
    bad = [x for x in arms if x not in course.ARMS]
    if bad:
        ap.error(f'unknown arm {bad}; arms: {list(course.ARMS)}')
    if a.cmd == 'report':
        return report(a)
    if a.cmd == 'sheet':
        return sheet(a)
    cells = plan(entries, arms, a.segments_dir, a.pilot_dir, a.kept_root, a.tas, only)
    if a.cmd == 'plan':
        by_id = {e.id: e for e in course.COURSE}
        for c in cells:
            e = by_id[c['entry']]
            print(f"{cell_id(a.bench_id, e, c['arm']):44s} {c['kind']:5s} wall {e.wall_s:4d} s  {'MISSING: ' + '; '.join(c['missing']) if c['missing'] else 'ready'}")
        return 0
    if not a.copies:
        ap.error('play needs --copies')
    Runner(a).play(cells)
    return 0


if __name__ == '__main__':
    sys.exit(main())
