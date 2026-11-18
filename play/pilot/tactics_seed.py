#!/usr/bin/env python3
"""Seed the tactics library from the runs that already happened, with no human recording.

Two readers, both turning what a run did at a stuck place into rows of the library (tactics.Book): attempts (what was tried, for which cause, where, with
what geometry round it, and whether Link got past), one `block` row per episode, and demonstrations.

  transcript   a pilot run's `transcript.jsonl`: the `recover` rows say where a block began and how it ended (recovered by a rung, marked bad, left); the
               decisions between them are the ladder's rungs in order, their result rows say what each did. The cause is read from the step that ended stuck
               and the world model (tactics.Sensor), the age from the state.
  journal      a run's step journal (hsap's out.jsonl + state.jsonl, read by routelib.RunData): a step that ended stuck, `held` or `timeout` short of its
               point begins an episode; the steps after it (to the next stuck step, at most 6 steps and 45 game seconds) are what was tried: their family
               (tactics.infer_family) is the tactic, and Link ending 4 m or more past the stuck point toward its want is what "got past" means. A way out
               that got past and is no family (and is not just "go again") is a demonstration: kept relative to the place and the heading, it replays
               at another block of the same cause.

A run with a transcript that has blocks is read from the transcript only (its journal shows the same steps). Every row has a key made from the run and the
episode: seeding a run again adds nothing. `evaluate` is the offline number: for each seeded block where something worked, how many attempts the old fixed
order needs to reach the tactic that worked, against the library built from every OTHER run (leave one run out) ranking the same tactics.

    python3 -I -B tactics_seed.py seed [--roots DIR ...] [--dir BOOK] [--no-world]
    python3 -I -B tactics_seed.py evaluate [--dir BOOK]
"""
import argparse
import hashlib
import json
import math
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import routelib  # noqa: E402
import tactics  # noqa: E402

WORKED_ALONG_M = 4.0      # Link ends this far past the stuck point toward its want: got past
WORKED_MIN_GAIN_M = 1.0   # a rung the pilot called recovered counts as a success only when it got Link this much nearer the point the stuck step wanted
SEG_STEPS, SEG_SECONDS = 6, 45.0
NEUTRAL = ('held', 'cut', 'bad', 'no-opponent', 'refused')
NOT_TACTICS = ('close-in', 'replan', 'vision')
SKIP_VERBS = ('watch', 'report', 'shot', 'end', 'save', 'duel')


def _jsonl(path):
    rows = []
    try:
        with open(path, errors='replace') as f:
            for ln in f:
                try:
                    rows.append(json.loads(ln))
                except ValueError:
                    continue
    except OSError:
        pass
    return rows


def _unit(dx, dz):
    n = math.hypot(dx, dz)
    return (dx / n, dz / n) if n > 1e-9 else (0.0, 1.0)


def _child(state):
    c = (state or {}).get('child')
    return 'child' if c == 1 else 'adult' if c == 0 else None


# ------------------------------------------------------------------------------------------------------------------------ the transcript

def transcript_blocks(rows, sensor):
    """The recovery blocks of a pilot transcript (the rows as the pilot wrote them): [{map, age, at [x, y, z], cause, why, geom, attempts [{tactic, outcome,
    gain_m}], worked, how recovered | marked-bad | left, target, n}]."""
    dec = {r['n']: r for r in rows if r.get('kind') == 'decision' and 'n' in r}
    res = {r['n']: r for r in rows if r.get('kind') == 'result' and 'n' in r}
    events, cur = [], None

    def close(cur, how, end_row, eof=False):
        upper = end_row['n'] if end_row else float('inf')
        rungs = sorted((n, d) for n, d in dec.items() if cur['n'] < n <= upper and str(d.get('choice', '')).startswith('recover:') and d.get('decider') == 'recover'
                       and d['choice'][8:] not in NOT_TACTICS and not d['choice'][8:].startswith('vision'))
        rn0 = cur['n'] if cur['n'] in res else cur['n'] - 1
        r0 = res.get(rn0) or {}
        steps = [s for s in r0.get('steps') or [] if s and s.get('ev') == 'step']
        stuck = next((s for s in steps if s.get('result') in ('stuck', 'timeout') and (s.get('src') or '').split()[:1] in (['walk'], ['run'])), steps[-1] if steps else None)
        d_before, d_after = dec.get(rn0) or dec.get(cur['n']) or {}, dec.get(rn0 + 1) or dec.get(cur['n']) or {}
        st0, st1 = d_before.get('state') or {}, d_after.get('state') or {}
        area = st0.get('area') or st1.get('area')
        if not area:
            return None
        pos = (stuck or {}).get('pos') or st1.get('pos') or st0.get('pos')
        if not pos or len(pos) != 3:
            return None
        verb, want, _ = routelib.parse_want((stuck or {}).get('src'))
        sense = sensor.sense(map=area, pos=pos, want=want, result=(stuck or {}).get('result') or 'stuck', verb=verb or 'run', detail=(stuck or {}).get('detail') or '',
                             moved=(stuck or {}).get('moved'), prompt=st1.get('prompt'), event=st1.get('event') or 0)
        age = _child(st0) or sense['age']
        attempts = []
        for i, (n, d) in enumerate(rungs):
            tactic = d['choice'][8:]
            rr = res.get(n)
            if rr is None or rr.get('result') in NEUTRAL:
                continue
            last = i == len(rungs) - 1
            if how == 'recovered' and last and end_row.get('rung') == tactic:
                outcome = 'worked'
            elif eof and last:
                continue   # the run ended inside this rung: what it did is not known
            else:
                outcome = 'failed'
            end = next((s['pos'] for s in reversed(rr.get('steps') or []) if s and s.get('pos')), None)
            gain = None
            if want and end:
                gain = round(math.hypot(want[0] - pos[0], want[1] - pos[2]) - math.hypot(want[0] - end[0], want[1] - end[2]), 2)
            if outcome == 'worked' and gain is not None and gain < WORKED_MIN_GAIN_M:
                continue   # the pilot called it recovered (Link stood inside the target's radius, say) but it got him no further: no evidence for the tactic
            attempts.append({'tactic': tactic, 'outcome': outcome, 'gain_m': gain})
        return {'kind': 'block', 'map': area, 'age': age, 'at': sense['at'], 'cause': sense['cause'], 'why': sense['why'], 'geom': sense['geom'], 'attempts': attempts,
                'worked': next((a['tactic'] for a in attempts if a['outcome'] == 'worked'), None), 'how': how, 'target': cur.get('target'), 'n': cur['n']}

    for r in rows:
        if r.get('kind') != 'recover':
            continue
        status = r.get('status')
        if status == 'blocked':
            if cur is not None:
                e = close(cur, 'left', {'n': r['n']})
                if e:
                    events.append(e)
            cur = {'n': r['n'], 'target': r.get('target')}
        elif status in ('recovered', 'marked-bad') and cur is not None:
            e = close(cur, status, r)
            if e:
                events.append(e)
            cur = None
    if cur is not None:
        e = close(cur, 'left', None, eof=True)
        if e:
            events.append(e)
    return events


# ------------------------------------------------------------------------------------------------------------------------ the journal

def journal_blocks(rd, sensor):
    """The episodes of a step journal (routelib.RunData): one per step that ended stuck, `held` or timed out short of its point, with the attempt the steps after
    it make (module doc). Same shape as transcript_blocks; a demonstration carries `demo` (the relative steps) and its attempt's tactic is `demo`."""
    steps = rd.steps
    events = []
    for i, s in enumerate(steps):
        if s['result'] not in routelib.STUCK_RESULTS or s['verb'] not in routelib.STUCK_VERBS or not s.get('pos') or not s.get('want'):
            continue
        m = re.search(r'([0-9.]+) m from the point', s.get('detail') or '')
        S, W = s['pos'], s['want']
        d_want = float(m.group(1)) if m else math.hypot(W[0] - S[0], W[1] - S[2])
        if d_want < 1.5 or (s['result'] == 'timeout' and s.get('radius') is not None and d_want <= s['radius']):
            continue
        seg = []
        for t in steps[i + 1:i + 1 + SEG_STEPS]:
            if t['t0'] - s['t1'] > SEG_SECONDS or (t['result'] in routelib.STUCK_RESULTS and t['verb'] in routelib.STUCK_VERBS and t['result'] != 'held'):
                break
            if t['verb'] in SKIP_VERBS:
                continue
            seg.append(t)
        mp = routelib.map_at(rd, s['t1'])
        if not seg or not mp:
            continue
        sense = sensor.sense(map=mp, pos=S, want=W, result=s['result'], verb=s['verb'], detail=s.get('detail') or '', moved=s.get('moved'))
        row = next((r for r in rd.rows if r['t'] - rd.t0 >= s['t1'] - 0.05), None)
        age = _child(row) or sense['age']
        end = next((t['pos'] for t in reversed(seg) if t.get('pos')), None)
        ux, uz = _unit(W[0] - S[0], W[1] - S[2])
        along = (end[0] - S[0]) * ux + (end[2] - S[2]) * uz if end else 0.0
        lines = [t['src'] for t in seg]
        first = seg[0]
        if first['result'] in NEUTRAL and first['verb'] in ('walk', 'run'):
            continue   # the first step was cut or held: it says nothing about the way out
        worked = along >= WORKED_ALONG_M
        ev = {'kind': 'block', 'map': mp, 'age': age, 'at': sense['at'], 'cause': sense['cause'], 'why': sense['why'], 'geom': sense['geom'], 'attempts': [],
              'worked': None, 'how': 'recovered' if worked else 'left', 'target': None, 'n': s['in']}
        fam = tactics.infer_family(lines, (S[0], S[2]), W)
        rel = tactics.relative_steps(lines, (S[0], S[2]), W)
        outcome = 'worked' if worked else 'failed'
        if fam:
            ev['attempts'].append({'tactic': fam, 'outcome': outcome, 'gain_m': round(along, 2)})
            ev['worked'] = fam if worked else None
        elif worked and rel and len(rel) <= 5 and not _plain_go(rel) and _generic(rel):
            ev['attempts'].append({'tactic': 'demo', 'outcome': 'worked', 'gain_m': round(along, 2)})
            ev['demo'] = rel
            ev['worked'] = 'demo'
        events.append(ev)
    return events


def _generic(rel):
    """A demonstration replays at another place, so it may hold only steps that mean the same anywhere: no wait for a quest's flag or a map (`until flag <name>`,
    `until area`); the A prompt's own flag and `until control` are the engine's and stay."""
    for r in rel:
        raw = r.get('raw', '')
        if r['verb'] == 'until' and not (raw.startswith('until control') or raw.startswith('until flag 0x9824206c=')):
            return False
        if r['verb'] in ('pickup', 'approach', 'ride', 'rendezvous', 'ocarina', 'buy', 'choose', 'use', 'item'):
            return False
    return True


def _plain_go(rel):
    """The first step is just a move straight toward the want (the pilot asked again): not a way out of its own."""
    f = rel[0]
    return f.get('verb') in ('walk', 'run') and 'a' in f and f['a'] > 2.0 and abs(f['b']) < 1.5


# ------------------------------------------------------------------------------------------------------------------------ seeding

def find_transcript(folder):
    folder = Path(folder)
    for c in (folder / 'transcript.jsonl', folder / 'pilot' / 'transcript.jsonl'):
        if c.is_file():
            return c
    return None


def seed_run(book, folder, sensor=None, source='journal'):
    """One run folder into the library: {run, source transcript | journal, attempts, blocks, demos} counting the rows ADDED (a run seeded before adds none)."""
    folder = Path(folder)
    sensor = sensor or tactics.Sensor(None)
    out = {'run': str(folder), 'source': None, 'attempts': 0, 'blocks': 0, 'demos': 0}
    events, build = [], None
    if book.has_run(folder.name, 'live') or book.has_run(folder.name, 'selfplay'):
        out['skipped'] = 'recorded while it played'   # the ladder wrote this run's attempts itself: its journal would count them twice
        return out
    tp = find_transcript(folder)
    if tp is not None:
        events = transcript_blocks(_jsonl(tp), sensor)
        if events:
            out['source'] = 'transcript'
            run_key = 'tr:' + hashlib.sha1(f'{tp.resolve()}:{tp.stat().st_size}'.encode()).hexdigest()[:10]
            label = folder.name
    if not events:
        try:
            rd = routelib.RunData(folder)
        except (routelib.LibError, OSError):
            out['skipped'] = 'no journal'
            return out
        events = journal_blocks(rd, sensor)
        out['source'] = 'journal'
        run_key, label = rd.run_id, rd.run_id
        build = routelib.detect_build(rd.live, rd.out)
    demos0 = len(book.demos())
    for i, ev in enumerate(events):
        bkey = f'{run_key}:{i}'
        base = dict(map=ev['map'], age=ev['age'], at=ev['at'], geom=ev['geom'], source=source, run=label, build=build, block=bkey)
        tried, worked = [], None
        for k, a in enumerate(ev['attempts']):
            key = f"{bkey}:{k}:{a['tactic']}"
            if a['tactic'] == 'demo':
                fresh = not book.has_key(key)
                tid = book.add_demo(ev['cause'], ev['demo'], key=key, **base)['tactic']
            else:
                tid = a['tactic']
                fresh = book.record(tid, ev['cause'], a['outcome'], gain_m=a.get('gain_m'), key=key, why=ev['why'], **base) is not None
            out['attempts'] += bool(fresh)
            tried.append(tid)
            worked = worked or (tid if a['outcome'] == 'worked' else None)
        if not book.has_key(bkey + ':block') and book.add_block(map=ev['map'], age=ev['age'], at=ev['at'], cause=ev['cause'], why=ev['why'], geom=ev['geom'], tried=tried, worked=worked,
                                                                 how=ev['how'], target=ev.get('target'), run=label, source=source, key=bkey + ':block', build=build):
            out['blocks'] += 1
    out['demos'] = len(book.demos()) - demos0
    return out


def discover(roots):
    """Run folders under the roots: a folder with a pilot transcript (`transcript.jsonl`, or `pilot/transcript.jsonl`) or a step journal (out.jsonl and state.jsonl,
    in the folder, its pilot/live or live). Each run once."""
    found = {}
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for dp, dns, fns in os.walk(root):
            p = Path(dp)
            if 'transcript.jsonl' in fns:
                found[(p.parent if p.name == 'pilot' else p).resolve()] = p.parent if p.name == 'pilot' else p
            if 'out.jsonl' in fns and 'state.jsonl' in fns:
                top = p.parent.parent if (p.name == 'live' and p.parent.name == 'pilot') else p.parent if p.name == 'live' else p
                found[top.resolve()] = top
    return sorted(found.values())


def seed(book, roots, sensor=None, source='journal', log=lambda *_: None):
    totals = {'runs': 0, 'transcript': 0, 'journal': 0, 'attempts': 0, 'blocks': 0, 'demos': 0, 'skipped': 0}
    for folder in discover(roots):
        try:
            r = seed_run(book, folder, sensor, source)
        except Exception as e:   # noqa: BLE001  one unreadable run is no reason to stop the rest
            log(f'{folder}: {type(e).__name__}: {e}')
            totals['skipped'] += 1
            continue
        if r.get('skipped'):
            totals['skipped'] += 1
            continue
        totals['runs'] += 1
        totals[r['source']] += 1
        for k in ('attempts', 'blocks', 'demos'):
            totals[k] += r[k]
    return totals


# ------------------------------------------------------------------------------------------------------------------------ the offline number

def evaluate(book):
    """Leave one run out: for every block where a tactic worked, attempts the old fixed order needs to reach it (its place in the order they were tried) against
    the place the library, built from every other run, gives it among the same tactics."""
    blocks = [b for b in book.rows('block') if b.get('worked') and b.get('tried') and b['worked'] in b['tried']]
    attempts = book.rows('attempt')
    out = {'blocks': 0, 'unsolved': sum(1 for b in book.rows('block') if not b.get('worked')), 'legacy_mean_attempts': None, 'ranked_mean_attempts': None, 'by_cause': {}}
    legacy, ranked = [], []
    for b in blocks:
        others = tactics.Book.from_rows([r for r in book.rows() if r.get('run') != b.get('run')], book.strength)
        tried = list(dict.fromkeys(b['tried']))
        rank = [r['tactic'] for r in others.rank(b['cause'], map=b.get('map'), age=b.get('age'), at=b.get('at'), geom=b.get('geom'), candidates=tried)]
        lg, rk = tried.index(b['worked']) + 1, rank.index(b['worked']) + 1
        legacy.append(lg)
        ranked.append(rk)
        c = out['by_cause'].setdefault(b['cause'], {'blocks': 0, 'legacy': [], 'ranked': []})
        c['blocks'] += 1
        c['legacy'].append(lg)
        c['ranked'].append(rk)
    out['blocks'] = len(legacy)
    if legacy:
        out['legacy_mean_attempts'] = round(sum(legacy) / len(legacy), 2)
        out['ranked_mean_attempts'] = round(sum(ranked) / len(ranked), 2)
    for c in out['by_cause'].values():
        c['legacy'], c['ranked'] = round(sum(c['legacy']) / len(c['legacy']), 2), round(sum(c['ranked']) / len(c['ranked']), 2)
    return out


def default_roots():
    roots = [HERE / 'runs']
    lib = Path(os.environ.get('ROUTELIB_DIR') or HERE.parent.parent / 'routelib')
    try:
        roots += [Path(r['folder']) for r in json.loads((lib / 'runs.json').read_text()).get('runs', []) if r.get('folder')]
    except (OSError, ValueError):
        pass
    return roots


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('seed')
    s.add_argument('--roots', nargs='*', default=None, help='folders to search for runs (default: pilot/runs and the route library\'s imported runs)')
    s.add_argument('--dir')
    s.add_argument('--no-world', action='store_true', help='no world model: causes are only what the steps say')
    e = sub.add_parser('evaluate')
    e.add_argument('--dir')
    a = ap.parse_args(argv)
    book = tactics.Book(a.dir)
    if a.cmd == 'seed':
        world = None
        if not a.no_world:
            try:
                world = routelib.PrivateWorld(HERE.parent / 'world')
            except Exception as ex:   # noqa: BLE001
                print(f'no world model ({type(ex).__name__}): causes from the steps only', flush=True)
        t0 = time.time()
        totals = seed(book, a.roots if a.roots is not None else default_roots(), tactics.Sensor(world), log=lambda m: print(m, flush=True))
        print(json.dumps({**totals, 'seconds': round(time.time() - t0, 1), 'library': book.summary()['attempts']}))
    else:
        print(json.dumps(evaluate(book), indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
