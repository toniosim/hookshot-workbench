#!/usr/bin/env python3
"""A live panel for a pilot run: what the pilot decides, as it happens, in a narrow terminal beside the game window.

    python3 live_panel.py <run folder> [--once] [--interval 0.5] [--width N] [--height N] [--wait SECONDS] [--no-color]

<run folder> is the pilot's run folder (pilot/runs/<tag>). It may not exist yet (the game is queued behind other runs): the panel waits
(default 3 hours) until transcript.jsonl or live/out.jsonl appears. Read-only: nothing is ever written into the run folder, no file is held
open between two reads, only complete lines are parsed, a bad line is skipped. Standard library only, no network, no secret read.

What each section reads (all of it is what the pilot and hsap really write):
  header     transcript.jsonl `planner` rows (the segment's name, goals, targets), `goal` rows (met / failed), `follow` rows; the pilot's own
             command line (/proc/<pid>/cmdline of the process that holds transcript.jsonl open) gives the segment .toml (name, what, goals,
             target places, [place], max_decisions) and --max-decisions / --vision / --decider; summary.json at the end (segment, goals, place)
  placement  `note` events (out.jsonl / transcript.jsonl) whose text starts with placement / fallback, <run>/panel-notes.txt, live/placement.json,
             summary.json `place`; else the segment's [place] table (requested) and whether a first decision followed it
  NOW        the latest transcript `decision` row (candidates, choice, answers[].probabilities, confidence, predicates, recover, fallback
             info), its `result` row, live/out.jsonl `step` events (src, result word, secs, moved), `recover` rows, `stop` rows
  WORLD      live/state.jsonl (the newest line: map, pos, facing, life / max_life, rupees, prompt, music, child, event, loading), its file
             age; live/out.jsonl `state` events when state.jsonl is absent
  EYES       vision/vision.jsonl (the newest look: screen, front, p, says, latency, cost)
  BUGS       vision/oddities.jsonl (what the eyes flag), findings.jsonl (run folder or live/; bughunt.Finding rows), transcript / out
             events of kind finding / bug
  NOTES      <run>/panel-notes.txt, hsap `note` / `bad` events
  footer     cost: cost_usd + usage of the transcript's decision / planner / counterfactual rows and vision.jsonl rows; decisions per
             minute from the decisions' wall stamps; the end: out.jsonl `done`, summary.json, or the writer process gone and no growth
"""
import argparse
import collections
import json
import math
import os
import re
import shutil
import signal
import sys
import textwrap
import time
import unicodedata
from pathlib import Path

try:
    import tomllib
except ImportError:   # (Python before 3.11: the segment file is then not read; everything else works)
    tomllib = None

STALE_STATE_S = 5.0     # a state line older than this is shown red
END_STALL_S = 20.0      # no growth for this long, the writer process gone: the run has ended
DONE_GRACE_S = 4.0      # after `done`, wait this long for summary.json (its outcome) before the final frame
MAX_CHUNK = 8 << 20     # bytes read from one file in one poll
MAX_PARTIAL = 16 << 20  # a partial last line longer than this is dropped
DEFAULT_WAIT_S = 3 * 3600
PLACE_WORDS = ('placement', 'fallback', '[place]')
SPIN = '⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'


# ---- tailing

class Tail:
    """One file read incrementally by byte offset. Only complete lines are returned; the partial last line waits for its newline. The
    file is opened for each read and closed again. `tail_bytes`: a file that grew by more than this since the last read is read from its
    last `tail_bytes` only (for a journal of which only the newest line matters)."""

    def __init__(self, path, tail_bytes=None):
        self.path, self.tail_bytes = Path(path), tail_bytes
        self.off, self.buf, self.size, self.mtime = 0, b'', 0, None

    def poll(self):
        try:
            st = os.stat(self.path)
        except OSError:
            return []
        self.mtime = st.st_mtime
        if st.st_size < self.off:   # replaced or truncated: from the start again
            self.off, self.buf = 0, b''
        self.size = st.st_size
        start, skip = self.off, False
        if self.tail_bytes and st.st_size - start > self.tail_bytes:
            start, skip = st.st_size - self.tail_bytes, True
        want = min(st.st_size - start, MAX_CHUNK)
        if want <= 0:
            return []
        try:
            with open(self.path, 'rb') as f:
                f.seek(start)
                data = f.read(want)
        except OSError:
            return []
        self.off = start + len(data)
        if skip:   # (it starts inside a line)
            self.buf = b''
            data = data.split(b'\n', 1)[1] if b'\n' in data else b''
        parts = (self.buf + data).split(b'\n')
        self.buf = parts.pop()
        if len(self.buf) > MAX_PARTIAL:
            self.buf = b''
        return parts

    @property
    def exists(self):
        return self.mtime is not None


def parse_rows(lines):
    """The JSON objects among complete lines; a blank or bad line is skipped (and counted by the caller through the shortfall)."""
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw.decode('utf-8', 'replace'))
        except ValueError:
            continue
        if isinstance(row, dict):
            yield row


def find_holders(paths):
    """pids (not ours) that hold any of `paths` open, from /proc; None where /proc cannot be read."""
    want = set()
    for p in paths:
        want.add(str(p))
        try:
            want.add(os.path.realpath(p))
        except OSError:
            pass
    try:
        pids = [p for p in os.listdir('/proc') if p.isdigit()]
    except OSError:
        return None
    me, found = str(os.getpid()), []
    for pid in pids:
        if pid == me:
            continue
        try:
            fds = os.listdir(f'/proc/{pid}/fd')
        except OSError:
            continue
        for fd in fds:
            try:
                if os.readlink(f'/proc/{pid}/fd/{fd}') in want:
                    found.append(int(pid))
                    break
            except OSError:
                continue
    return found


def read_cmdline(pid):
    """(argv, cwd) of a process, or (None, None)."""
    try:
        argv = [a.decode('utf-8', 'replace') for a in Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0') if a]
        return argv, os.readlink(f'/proc/{pid}/cwd')
    except OSError:
        return None, None


def parse_pilot_args(argv, cwd):
    """What the pilot's command line says: the segment file, --max-decisions, --vision, --decider, --planner, --tag. {} when it is no pilot."""
    out = {}
    if not argv or not any(a.endswith('pilot.py') for a in argv[:3]) or 'run' not in argv:
        return out
    rest = argv[argv.index('run') + 1:]
    takes = {'--decider', '--replay', '--copy', '--tag', '--attach', '--save', '--wall', '--max-decisions', '--follow', '--end-hold', '--shots',
             '--matches', '--humanize', '--humanize-seed', '--bad-points', '--vision', '--vision-every', '--vision-model', '--vision-backend',
             '--vision-sock', '--api-base', '--allowance-usd', '--allowance-since'}
    i = 0
    while i < len(rest):
        a = rest[i]
        if a.startswith('--'):
            key, eq, val = a.partition('=')
            if key in takes and not eq and i + 1 < len(rest):
                val, i = rest[i + 1], i + 1
            elif key not in takes:
                val = True
            out[key[2:]] = val
        elif 'segment' not in out:
            seg = Path(a)
            if not seg.is_absolute():
                script = Path(next((x for x in argv[:3] if x.endswith('pilot.py')), 'pilot.py'))
                for base in (Path(cwd or '.'), (Path(cwd or '.') / script).parent):
                    if (base / seg).is_file():
                        seg = base / seg
                        break
            out['segment'] = str(seg)
        i += 1
    return out


def load_segment(path):
    """The segment .toml as the panel needs it: name, what, area, max_decisions, place, goals [{name, what, kind}], targets {name: {...}}."""
    if tomllib is None or not path:
        return None
    d = tomllib.loads(Path(path).read_text())
    goals, targets = [], {}
    for g in d.get('goal') or []:
        goals.append({'name': g.get('name'), 'what': g.get('what'), 'kind': g.get('kind', 'reach')})
        for t in g.get('targets') or []:
            at = t.get('at')
            e = {'kind': t.get('kind', g.get('kind', 'reach')), 'goal': g.get('name'), 'y': t.get('y')}
            if isinstance(at, (list, tuple)) and len(at) == 2:
                e.update(x=at[0], z=at[1])
            targets[t.get('name')] = e
    return {'name': d.get('name'), 'what': d.get('what'), 'area': d.get('area'), 'max_decisions': d.get('max_decisions', 80),
            'budget_seconds': d.get('budget_seconds', 400), 'place': d.get('place'), 'goals': goals, 'targets': targets}


def request_data(req):
    """The JSON a request body carried to the model (the planner's user message, or a decision's input_json part), or {}."""
    for m in (req or {}).get('input') or []:
        if not isinstance(m, dict):
            continue
        c = m.get('content')
        cands = []
        if isinstance(c, str):
            try:
                cands.append(json.loads(c))
            except ValueError:
                pass
        elif isinstance(c, list):
            cands += [p.get('data') for p in c if isinstance(p, dict) and p.get('type') == 'input_json']
        for d in cands:
            if isinstance(d, dict) and ('goal' in d or 'segment' in d or 'goals' in d):
                return d
    return {}


def fmt_place(res):
    """The placement result dict (placement.apply / summary.json `place`) as one line."""
    if not isinstance(res, dict):
        return None
    if res.get('ok'):
        hour = res.get('hour')
        st = res.get('state') or {}
        bits = [res.get('map') or st.get('map') or res.get('to'), res.get('age') or st.get('age'), None if hour is None else f'{int(hour):02d}:00']
        sec = f' ({res.get("seconds")} s)' if res.get('seconds') is not None else ''
        return 'placed: ' + ', '.join(str(b) for b in bits if b is not None) + sec
    return f'placement FAILED: {res.get("error") or res.get("effect") or "not applied"}'


# ---- the run, accumulated from its files

class Run:
    def __init__(self, folder, clock=time.time, mono=time.monotonic, holders=find_holders):
        self.folder = Path(folder)
        self.clock, self.mono, self.holders = clock, mono, holders
        live = self.folder / 'live'
        self.tr = Tail(self.folder / 'transcript.jsonl')
        self.out = Tail(live / 'out.jsonl')
        self.out_end = Tail(self.folder / 'out.jsonl')   # (the copy made when the run ends: used only when the live one is not there)
        self.sta = Tail(live / 'state.jsonl', tail_bytes=64 * 1024)
        self.vis = Tail(self.folder / 'vision' / 'vision.jsonl')
        self.odd = Tail(self.folder / 'vision' / 'oddities.jsonl')
        self.fnd = [Tail(self.folder / 'findings.jsonl'), Tail(live / 'findings.jsonl')]
        self.tails = [self.tr, self.out, self.out_end, self.sta, self.vis, self.odd] + self.fnd
        self.notes_path, self.place_path, self.summary_path = self.folder / 'panel-notes.txt', live / 'placement.json', self.folder / 'summary.json'
        self.panel_notes, self._notes_sig = [], None
        self.place_json, self._place_sig = None, None
        # accumulated
        self.events = 0
        self.first_wall = self.last_wall = None
        self.first_seen = None
        self.decisions = collections.deque(maxlen=60)
        self.n_dec, self.n_max, self.dec_walls = 0, 0, collections.deque(maxlen=400)
        self.first_dec_wall = None
        self.deciders = set()
        self.goal_order, self.goal_status, self.goal_what = [], {}, {}
        self.targets = {}
        self.seg = None
        self.cmd = {}
        self.pilot_pid, self._probe_at, self._gone_at, self._gone = None, -1e9, -1e9, None
        self.plan_reason = None
        self.last_step, self.steps_seen, self.last_result = None, 0, None
        self.recovers = collections.deque(maxlen=6)
        self.stop = None
        self.out_state, self.state = None, None
        self.gameplay = None
        self.vision_on, self.vision_last, self.vision_n, self.vision_err = False, None, 0, None
        self.bugs = collections.deque(maxlen=40)
        self.bug_sources = set()
        self.notes = collections.deque(maxlen=30)       # hsap notes and the like
        self.place_notes = collections.deque(maxlen=20)  # (text, from)
        self.cost = {'usd': 0.0, 'calls': 0, 'tin': 0, 'tout': 0}
        self.counterfactuals = 0
        self.done, self.done_t, self.done_at = False, None, None
        self.summary, self._summary_sig = None, None
        self.last_growth, self._sig = None, None
        self.ended, self.end_ref = None, None
        self.row_errors, self.last_error = 0, None

    # -- bookkeeping of what the rows say
    def see_wall(self, wall):
        if isinstance(wall, (int, float)) and not isinstance(wall, bool) and wall > 1e9:
            self.first_wall = wall if self.first_wall is None else min(self.first_wall, wall)
            self.last_wall = wall if self.last_wall is None else max(self.last_wall, wall)

    def cost_add(self, usd, usage=None):
        if isinstance(usd, (int, float)) and not isinstance(usd, bool):
            self.cost['usd'] += usd
            self.cost['calls'] += 1
        if isinstance(usage, dict):
            self.cost['tin'] += int(usage.get('input_tokens') or 0)
            self.cost['tout'] += int(usage.get('output_tokens') or 0)

    def goal_seen(self, name, what=None):
        if name and name not in self.goal_order:
            self.goal_order.append(name)
        if name and what:
            self.goal_what[name] = what

    def note_place(self, text, src):
        t = ' '.join(str(text).split())
        if t.lower().startswith(PLACE_WORDS):
            self.place_notes.append((t, src))

    def add_bug(self, kind, text, wall=None, t=None, where=None, src=''):
        self.bugs.append({'kind': kind, 'text': text, 'wall': wall, 'game_t': t, 'where': where, 'src': src})
        self.bug_sources.add(src)

    # -- row handlers
    def on_transcript(self, r):
        self.events += 1
        self.see_wall(r.get('wall'))
        kind = r.get('kind') or r.get('ev')
        if kind == 'decision':
            self.on_decision(r)
        elif kind == 'result':
            self.on_result(r)
        elif kind == 'goal':
            self.goal_seen(r.get('goal'))
            if r.get('status') in ('met', 'failed'):
                self.goal_status[r.get('goal')] = r['status']
        elif kind == 'planner':
            self.on_planner(r)
        elif kind == 'counterfactual':
            self.vision_on = True
            if r.get('asked'):
                self.cost_add(r.get('cost_usd'))
        elif kind == 'recover':
            self.recovers.append({k: r.get(k) for k in ('n', 'target', 'status', 'rung', 'rungs', 'why', 'at', 's')})
        elif kind == 'stop':
            self.stop = str(r.get('why') or 'stopped')
        elif kind == 'follow':
            name = r.get('target')
            if name and r.get('x') is not None:
                self.targets.setdefault(name, {}).update(x=r.get('x'), z=r.get('z'), y=r.get('y'), area=r.get('map'), kind='follow')
        elif kind == 'note':
            self.note_place(r.get('text') or '', 'transcript')
        elif kind in ('finding', 'bug'):
            self.add_bug(r.get('type') or r.get('sub') or kind, str(r.get('text') or r.get('detail') or r.get('why') or ''), r.get('wall'),
                         r.get('game_s') or r.get('t'), r.get('map'), 'transcript')

    def on_planner(self, r):
        self.cost_add(r.get('cost_usd'), r.get('usage'))
        ans = r.get('answer')
        if isinstance(ans, dict) and ans.get('reason'):
            self.plan_reason = str(ans['reason'])
        d = request_data(r.get('request'))
        seg = d.get('segment')
        if isinstance(seg, dict) and not self.seg:
            self.seg = {'name': seg.get('name'), 'what': seg.get('what'), 'area': seg.get('area')}
        for g in d.get('goals') or []:
            if isinstance(g, dict):
                self.goal_seen(g.get('name'), g.get('what'))
                for t in g.get('targets') or []:
                    if isinstance(t, dict) and t.get('name') and t.get('x') is not None:
                        self.targets.setdefault(t['name'], {}).update(x=t.get('x'), z=t.get('z'), y=t.get('y'), kind=t.get('kind'), goal=g.get('name'))
        for pair in r.get('before') or []:
            if isinstance(pair, (list, tuple)) and pair:
                self.goal_seen(pair[0])

    def on_decision(self, r):
        n = r.get('n') if isinstance(r.get('n'), int) else self.n_dec + 1
        cands = [{'label': c.get('label'), 'text': c.get('text'), 'lines': c.get('lines')} for c in r.get('candidates') or [] if isinstance(c, dict)]
        probs, conf = {}, r.get('confidence')
        for a in r.get('answers') or []:
            if isinstance(a, dict) and a.get('type') == 'choice':
                probs = {p.get('value'): p.get('probability') for p in a.get('probabilities') or [] if isinstance(p, dict)}
                if conf is None:
                    conf = a.get('confidence')
        info = {k: r[k] for k in ('fallback', 'throttled', 'override', 'replayed', 'no_request', 'recover_rung', 'recover_why', 'recorded') if r.get(k) is not None}
        st = r.get('state') if isinstance(r.get('state'), dict) else {}
        d = request_data(r.get('request'))
        t = d.get('target') if isinstance(d.get('target'), dict) else None
        if t and t.get('name') and t.get('x') is not None:
            self.targets.setdefault(t['name'], {}).update(x=t.get('x'), z=t.get('z'), kind=t.get('kind'))
        self.goal_seen(r.get('goal'))
        self.cost_add(r.get('cost_usd'), r.get('usage'))
        rec = {'n': n, 'goal': r.get('goal'), 'target': r.get('target'), 'decider': r.get('decider'), 'choice': r.get('choice'), 'cands': cands,
               'probs': probs, 'conf': conf, 'preds': r.get('predicates') or {}, 'recover': r.get('recover'), 'info': info,
               'latency_ms': r.get('latency_ms'), 'wall': r.get('wall'), 't': st.get('t'), 'area': st.get('area'), 'pos': st.get('pos'),
               'plan': r.get('plan') if isinstance(r.get('plan'), (str, dict)) else None, 'result': None}
        self.decisions.append(rec)
        self.n_dec += 1
        self.n_max = max(self.n_max, n)
        if r.get('decider'):
            self.deciders.add(r['decider'])
        if isinstance(r.get('wall'), (int, float)):
            self.dec_walls.append(r['wall'])
            self.first_dec_wall = r['wall'] if self.first_dec_wall is None else self.first_dec_wall

    def on_result(self, r):
        steps = [s for s in r.get('steps') or [] if isinstance(s, dict)]
        word = r.get('result') or (steps[-1].get('result') if steps else None) or ('lost' if r.get('lost') else None)
        res = {'n': r.get('n'), 'word': word, 'moved': r.get('moved'), 'lost': r.get('lost'), 'interaction': r.get('interaction'),
               'steps': [{k: s.get(k) for k in ('src', 'result', 'secs', 'moved', 'detail')} for s in steps[-3:]]}
        self.last_result = res
        for d in reversed(self.decisions):
            if d['n'] == r.get('n'):
                d['result'] = res
                break

    def on_out(self, r):
        self.events += 1
        self.see_wall(r.get('wall'))
        ev = r.get('ev')
        if ev == 'state':
            self.out_state = {'t': r.get('t'), 'frame': r.get('frame'), 'map': r.get('area'), 'pos': r.get('pos'), 'facing': r.get('facing'),
                              'life': r.get('life'), 'max_life': r.get('max_life'), 'rupees': r.get('rupees'), 'prompt': r.get('prompt'),
                              'music': r.get('music'), 'child': r.get('child'), 'event': r.get('event'), 'loading': r.get('loading'),
                              'text': r.get('text')}
        elif ev == 'step':
            self.steps_seen += 1
            self.last_step = {k: r.get(k) for k in ('in', 'src', 'result', 'secs', 'moved', 'detail', 't')}
        elif ev == 'gameplay':
            self.gameplay = {'t': r.get('t'), 'area': r.get('area')}
        elif ev == 'done':
            if not self.done:
                self.done, self.done_t, self.done_at = True, r.get('t'), self.mono()
        elif ev == 'note':
            text = str(r.get('text') or '')
            self.note_place(text, 'out')
            if text and not text.startswith(('hs-run:', 'external game')):
                self.notes.append(text)
        elif ev == 'bad':
            self.notes.append(f'bad step: {r.get("src")} ({r.get("why")})')
        elif ev in ('finding', 'bug'):
            self.add_bug(r.get('type') or r.get('sub') or ev, str(r.get('text') or r.get('detail') or ''), r.get('wall'), r.get('t'), r.get('map'), 'out')

    def on_state(self, r):
        if isinstance(r.get('game'), dict):   # (a co-op session side writes {"w", "game": {...}})
            r = dict(r['game'], w=r.get('w'))
        self.state = {k: r.get(k) for k in ('t', 'frame', 'map', 'pos', 'facing', 'life', 'max_life', 'rupees', 'prompt', 'music', 'child',
                                            'event', 'loading')}

    def on_vision(self, r):
        self.vision_on = True
        self.see_wall(r.get('wall'))
        self.vision_n += 1
        self.cost_add(r.get('cost_usd'), r.get('usage'))
        if r.get('error'):
            self.vision_err = {'error': str(r['error']), 'wall': r.get('wall')}
        else:
            ans = r.get('answers') if isinstance(r.get('answers'), dict) else {}
            self.vision_last = {'seq': r.get('seq'), 'n': r.get('n'), 'wall': r.get('wall'), 't': r.get('t'), 'why': r.get('why'), 'answers': ans,
                                'latency_ms': r.get('latency_ms'), 'cost_usd': r.get('cost_usd'), 'model': r.get('model')}

    def on_oddity(self, r):
        self.vision_on = True
        self.add_bug(str(r.get('kind') or 'oddity'), str(r.get('detail') or ''), r.get('wall'), r.get('t'), r.get('area'), 'eyes')

    def on_finding(self, r):
        if r.get('severity') == 'info':
            return
        label = '/'.join(str(x) for x in (r.get('kind'), r.get('sub')) if x) or 'finding'
        self.add_bug(label, str(r.get('text') or ''), r.get('wall'), r.get('game_s') if r.get('game_s') is not None else r.get('t'), r.get('map'), 'findings')

    # -- one poll
    def feed(self, tail, fn):
        for row in parse_rows(tail.poll()):
            try:
                fn(row)
            except Exception as e:   # noqa: BLE001  an odd row is skipped, never a crash
                self.row_errors += 1
                self.last_error = f'{type(e).__name__}: {e}'

    def poll(self, grace_s=DONE_GRACE_S):
        now, mono = self.clock(), self.mono()
        self.feed(self.tr, self.on_transcript)
        self.feed(self.out, self.on_out)
        if not self.out.exists:
            self.feed(self.out_end, self.on_out)
        self.feed(self.sta, self.on_state)
        self.feed(self.vis, self.on_vision)
        self.feed(self.odd, self.on_oddity)
        for t in self.fnd:
            self.feed(t, self.on_finding)
            if t.exists:
                self.bug_sources.add('findings')
        self.read_small_files()
        sig = tuple((t.size, t.mtime) for t in self.tails) + ((self.summary or {}).get('_sig'),)
        if sig != self._sig:
            self._sig = sig
            self.last_growth = mono
        if self.started and self.first_seen is None:
            self.first_seen = now
        if self.ended is None and self.started and not self.pilot_pid and mono - self._probe_at >= 3.0:
            self._probe_at = mono
            self.probe_pilot()
        if self.ended is None:
            self.check_end(now, mono, grace_s)
        return self

    def read_small_files(self):
        try:   # panel-notes.txt: small, replaced or appended by the runner: re-read whole when it changes
            st = os.stat(self.notes_path)
            if (st.st_size, st.st_mtime) != self._notes_sig:
                self._notes_sig = (st.st_size, st.st_mtime)
                data = self.notes_path.read_bytes()[-65536:].decode('utf-8', 'replace')
                self.panel_notes = [' '.join(x.split()) for x in data.splitlines() if x.strip()][-40:]
        except OSError:
            pass
        try:
            st = os.stat(self.place_path)
            if (st.st_size, st.st_mtime) != self._place_sig:
                self._place_sig = (st.st_size, st.st_mtime)
                self.place_json = json.loads(self.place_path.read_text())
        except (OSError, ValueError):
            pass
        try:
            st = os.stat(self.summary_path)
            sig = (st.st_size, st.st_mtime)
            if sig != self._summary_sig:
                self._summary_sig = sig
                s = json.loads(self.summary_path.read_text())
                if isinstance(s, dict):
                    s['_sig'] = sig
                    self.summary = s
        except (OSError, ValueError):
            pass

    @property
    def started(self):
        return self.tr.exists or self.out.exists or self.out_end.exists

    def probe_pilot(self):
        """Find the process that holds transcript.jsonl open (the pilot) and what its command line says: the segment file and options."""
        if not self.tr.exists:
            return
        pids = self.holders([self.tr.path])
        if not pids:
            return
        self.pilot_pid = pids[0]
        argv, cwd = read_cmdline(self.pilot_pid)
        self.cmd = parse_pilot_args(argv, cwd)
        try:
            self.seg = dict(self.seg or {}, **(load_segment(self.cmd.get('segment')) or {}))
        except Exception as e:   # noqa: BLE001  a segment file the panel cannot read is not the run's problem
            self.last_error = f'segment: {type(e).__name__}: {e}'
        for g in (self.seg or {}).get('goals') or []:
            self.goal_seen(g['name'], g.get('what'))
        for name, t in ((self.seg or {}).get('targets') or {}).items():
            self.targets.setdefault(name, {}).update({k: v for k, v in t.items() if v is not None})
        if self.cmd.get('vision') == 'on':
            self.vision_on = True

    def writer_gone(self, mono):
        """True when no process holds any of the run's live files open (None: cannot tell). Cached for 2 s."""
        if mono - self._gone_at < 2.0:
            return self._gone
        self._gone_at = mono
        paths = [t.path for t in (self.tr, self.out, self.sta) if t.exists]
        h = self.holders(paths) if paths else None
        self._gone = None if h is None else not h
        return self._gone

    def check_end(self, now, mono, grace_s):
        why = None
        if self.summary is not None and (self.summary.get('outcome') is not None or self.summary.get('decisions') is not None
                                         or self.summary.get('done') is not None):
            why = 'summary'
        elif self.done and (grace_s <= 0 or mono - (self.done_at or mono) >= grace_s):
            why = 'done'
        elif self.events and self.last_growth is not None and mono - self.last_growth >= END_STALL_S and self.writer_gone(mono):
            why = 'gone'
        if why is None:
            return
        walls = [t.mtime for t in self.tails if t.mtime] + ([self.last_wall] if self.last_wall else [])
        self.end_ref = max(walls) if walls else now
        stall = mono - (self.last_growth or mono)
        s = self.summary or {}
        if s.get('outcome'):
            self.ended = str(s['outcome'])
        elif self.stop:
            self.ended = f'stopped: {self.stop}'
        elif self.done:
            self.ended = f'game done at t={self.done_t} s' if self.done_t is not None else 'game done'
        else:
            self.ended = f'no activity for {stall:.0f} s and the writer process is gone'

    # -- the derived view
    def snapshot(self, now=None):
        now = self.clock() if now is None else now
        ref = self.end_ref if self.ended is not None and self.end_ref else now
        s, seg = self.summary or {}, dict(self.seg or {})
        if s.get('segment') and not seg.get('name'):
            seg['name'] = s['segment']
        names = list(self.goal_order)
        for k in (s.get('goals') or {}):
            if k not in names:
                names.append(k)
        status = dict(self.goal_status)
        for k, v in (s.get('goals') or {}).items():
            status.setdefault(k, v if v in ('met', 'failed') else 'open')
        last = self.decisions[-1] if self.decisions else None
        cur_goal = last['goal'] if last else None
        tname = last['target'] if last else None
        target = None
        if tname:
            target = dict(self.targets.get(tname) or {}, name=tname)
            pos = (self.state or self.out_state or {}).get('pos') or (last or {}).get('pos')
            if target.get('x') is not None and isinstance(pos, (list, tuple)) and len(pos) >= 3:
                try:
                    target['dist'] = math.hypot(pos[0] - target['x'], pos[2] - target['z'])
                except (TypeError, ValueError):
                    pass
            target.setdefault('area', seg.get('area') or (last or {}).get('area'))
        st = self.state or self.out_state
        st_mtime = (self.sta.mtime if self.state else self.out.mtime or self.out_end.mtime)
        max_n = self.cmd.get('max-decisions') or seg.get('max_decisions')
        try:
            max_n = int(max_n) if max_n else None
        except (TypeError, ValueError):
            max_n = None
        first = self.first_wall or self.first_seen
        # decisions per minute: all decisions over the time since the first
        dpm = None
        if self.first_dec_wall and self.dec_walls:
            span = (self.dec_walls[-1] if self.ended is not None else max(ref, self.dec_walls[-1])) - self.first_dec_wall
            if span >= 5.0:
                dpm = self.n_dec * 60.0 / span
        place = self.placement_lines(seg, last, s)
        vision_on = self.vision_on or bool(s.get('vision')) or self.vis.exists
        bug_on = bool(self.bug_sources) or vision_on
        model = any(not (d or '').startswith(('rules', 'replay')) for d in self.deciders)
        return {
            'folder': str(self.folder), 'run_id': s.get('run') or self.folder.name, 'seg': seg, 'goals': [(g, status.get(g, 'open')) for g in names],
            'goal_what': dict(self.goal_what), 'cur_goal': cur_goal, 'target': target, 'place': place,
            'wall_s': max(0.0, ref - first) if first else None, 'game_t': (self.out_state or {}).get('t') if self.out_state else (last or {}).get('t'),
            'n': last['n'] if last else None, 'max_n': max_n, 'n_dec': self.n_dec, 'decision': last, 'plan_reason': self.plan_reason,
            'step': self.last_step, 'result': self.last_result, 'recover': (last or {}).get('recover'), 'recovers': list(self.recovers),
            'stop': self.stop, 'steps_seen': self.steps_seen, 'gameplay': self.gameplay, 'last_note': self.notes[-1] if self.notes else None,
            'state': st, 'state_age': (ref - st_mtime) if st_mtime else None, 'state_src': 'state.jsonl' if self.state else 'out.jsonl',
            'vision_on': vision_on, 'vision': self.vision_last, 'vision_n': self.vision_n, 'vision_err': self.vision_err,
            'vision_age': (ref - self.vision_last['wall']) if self.vision_last and self.vision_last.get('wall') else None,
            'bugs': list(self.bugs), 'bug_on': bug_on, 'bug_sources': sorted(self.bug_sources),
            'notes': [('panel', x) for x in self.panel_notes[-8:]] + [('game', x) for x in list(self.notes)[-4:]],
            'cost': dict(self.cost), 'cost_known': self.cost['calls'] > 0, 'model': model, 'dpm': dpm,
            'clock': time.strftime('%H:%M:%S', time.localtime(now)), 'ended': self.ended, 'summary': {k: s.get(k) for k in ('decisions', 'outcome')},
            'errors': self.row_errors, 'now': ref,
        }

    def placement_lines(self, seg, last, summary):
        out = []
        for text, _src in list(self.place_notes)[-6:]:
            out.append(text)
        for t in self.panel_notes:
            if t.lower().startswith(PLACE_WORDS):
                out.append(t)
        # newest placement line and newest fallback line only
        pick = []
        for word in ('placement', 'placed', 'fallback'):
            hit = [x for x in out if x.lower().startswith(word)]
            if hit:
                pick.append(hit[-1])
        if pick:
            return pick
        line = fmt_place(self.place_json) or fmt_place(summary.get('place'))
        if line:
            return [line]
        spec = seg.get('place') if seg else None
        if isinstance(spec, dict):
            bits = [spec.get('to'), spec.get('age'), None if spec.get('hour') is None else f'{int(spec["hour"]):02d}:00']
            req = ', '.join(str(b) for b in bits if b is not None)
            return [f'placement requested: {req}; ' + ('the first decision followed it (so it applied)' if last else 'no decision yet')]
        return []


# ---- drawing

ANSI = re.compile(r'\x1b\[[0-9;?]*[A-Za-z]')


def cwidth(ch):
    if unicodedata.combining(ch):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in 'WF' else 1


def vlen(s):
    return sum(cwidth(c) for c in ANSI.sub('', s))


def clip(s, width):
    """The line cut to `width` columns (ANSI sequences cost nothing); a cut line ends in an ellipsis."""
    if vlen(s) <= width:
        return s
    out, vis, i = [], 0, 0
    limit = max(1, width - 1)
    while i < len(s):
        m = ANSI.match(s, i)
        if m:
            out.append(m.group())
            i = m.end()
            continue
        w = cwidth(s[i])
        if vis + w > limit:
            break
        out.append(s[i])
        vis += w
        i += 1
    res = ''.join(out) + '…'
    return res + '\x1b[0m' if '\x1b[' in res else res


def clean(v):
    """One printable line of text from anything: whitespace collapsed, control characters (escape sequences too) removed."""
    return ''.join(ch for ch in ' '.join(str(v).split()) if ch.isprintable())


def clean_keep(v):
    """clean(), but the colour sequences this module made itself stay."""
    out, i, s = [], 0, str(v)
    for m in ANSI.finditer(s):
        out.append(clean(s[i:m.start()]) if s[i:m.start()].strip() else s[i:m.start()])
        out.append(m.group())
        i = m.end()
    out.append(clean(s[i:]) if s[i:].strip() else s[i:])
    return ''.join(out)


class Paint:
    def __init__(self, on):
        self.on = on

    def _p(self, code, s):
        return f'\x1b[{code}m{s}\x1b[0m' if self.on and s else s

    def bold(self, s):
        return self._p('1', s)

    def dim(self, s):
        return self._p('2', s)

    def red(self, s):
        return self._p('1;31', s)

    def green(self, s):
        return self._p('32', s)

    def gbold(self, s):
        return self._p('1;32', s)

    def yellow(self, s):
        return self._p('33', s)

    def cyan(self, s):
        return self._p('1;36', s)


class Sec:
    """A section: lines that stay (`fixed`, the title first), history lines (`hist`, oldest first) dropped from the oldest when short of rows,
    and `soft` lines (members of `fixed`, in drop order) dropped after the history."""

    def __init__(self, name, fixed=None, hist=None, soft=None):
        self.name, self.fixed, self.hist, self.soft = name, list(fixed or []), list(hist or []), list(soft or [])


def wrapped(text, width, first='', rest=None, limit=None):
    rest = first if rest is None else rest
    lines = textwrap.wrap(clean(text), width=max(10, width - vlen(first)), break_long_words=True, break_on_hyphens=False) or ['']
    if limit and len(lines) > limit:
        lines = lines[:limit]
        lines[-1] = lines[-1][:-1] + '…' if lines[-1] else '…'
    return [(first if i == 0 else rest) + ln for i, ln in enumerate(lines)]


def title(c, width, name, extra=''):
    head = f'─ {name} '
    body = c.cyan(head) + (clean_keep(extra) + ' ' if extra else '')
    return body + c.dim('─' * max(0, width - vlen(body)))


def hms(sec):
    if sec is None:
        return '?'
    sec = int(max(0, sec))
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return f'{h}:{m:02d}:{s:02d}' if h else f'{m:02d}:{s:02d}'


def ago(sec):
    if sec is None:
        return '?'
    sec = max(0.0, sec)
    if sec < 100:
        return f'{sec:.1f} s'
    return f'{int(sec // 60)} min {int(sec % 60):02d} s'


def fnum(x, nd=1):
    try:
        return f'{float(x):.{nd}f}'
    except (TypeError, ValueError):
        return '?'


def fpos(p):
    try:
        return ' '.join(fnum(v) for v in p[:3])
    except (TypeError, ValueError):
        return '?'


def clock_of(wall):
    try:
        return time.strftime('%H:%M:%S', time.localtime(wall))
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def word_color(c, word):
    w = str(word or '')
    if w in ('reached', 'done', 'met', 'arrived', 'ok'):
        return c.green(w)
    if w in ('stuck', 'blocked', 'timeout', 'lost', 'failed', 'refused', 'cut'):
        return c.red(w)
    return c.yellow(w) if w else '?'


def sec_header(s, width, c):
    seg = s['seg'] or {}
    wall = f'wall {hms(s["wall_s"])}' if s['wall_s'] is not None else 'wall ?'
    game = f' · game {fnum(s["game_t"], 0)} s' if s.get('game_t') is not None else ''
    lines = [c.cyan('═ PILOT ') + clip(f'{clean(s["run_id"])} · {wall}{game}', max(10, width - 9))]
    if seg.get('name'):
        what = f' — {seg["what"]}' if seg.get('what') else ''
        lines += wrapped(f'segment {seg["name"]}{what}', width, '', limit=2)
    if s['goals']:
        marks = []
        for g, st in s['goals']:
            if st == 'met':
                marks.append(c.green('✓' + clean(g)))
            elif st == 'failed':
                marks.append(c.red('✗' + clean(g)))
            elif g == s['cur_goal']:
                marks.append(c.bold('▸' + clean(g)))
            else:
                marks.append(c.dim('·' + clean(g)))
        lines += wrapped_marks('goals ', marks, width)
    elif s['cur_goal']:
        lines.append(f'goal {clean(s["cur_goal"])}')
    t = s['target']
    if t:
        bits = [f'target {clean(t["name"])}']
        if t.get('kind'):
            bits.append(f'({clean(t["kind"])})')
        if t.get('x') is not None:
            bits.append(f'at {fnum(t.get("x"))} {fnum(t.get("z"))}')
        if t.get('area'):
            bits.append(f'in {clean(t["area"])}')
        if t.get('dist') is not None:
            bits.append(f'· {fnum(t["dist"])} m away')
        lines += wrapped(' '.join(bits), width, '', limit=2)
    for p in s['place']:
        lines += wrapped(p, width, '', limit=2) if 'FAILED' not in p else [c.red(clean(p))]
    return Sec('header', lines)


def wrapped_marks(prefix, marks, width):
    """Coloured words flowed into lines (the prefix on the first)."""
    lines, cur = [], prefix
    for m in marks:
        if cur.strip() and vlen(cur) + 1 + vlen(m) > width:
            lines.append(cur.rstrip())
            cur = '      '
        cur += m + ' '
    lines.append(cur.rstrip())
    return lines[:4]


def sec_now(s, width, c):
    d = s['decision']
    if d is None:
        bits = ['no decision yet']
        if s['gameplay']:
            bits.append('the game is in play, waiting for the first state/decision')
        elif s['last_note']:
            bits.append(f'game: {s["last_note"]}')
        lines = [title(c, width, 'NOW', ' · '.join(bits))]
        if s['step']:
            lines += step_lines(s, width, c, None)
        return Sec('NOW', lines)
    n = f'decision {d["n"]}' + (f'/{s["max_n"]}' if s['max_n'] else '')
    res = d.get('result')
    state = 'executing' if res is None else None
    bits = [n, (d.get('decider') or '?') + (f' · goal {clean(d["goal"])}' if d.get('goal') else '')]
    lines = [title(c, width, 'NOW', ' · '.join(bits))]
    cands = d['cands'] or []
    labels = [x['label'] for x in cands]
    if d['choice'] not in labels:
        cands = cands + [{'label': d['choice'], 'text': 'the chosen step (not among the listed candidates)', 'lines': None}]
    lw = min(18, max([len(str(x['label'])) for x in cands] + [4]))
    probs = d['probs'] or {}
    chosen_text = None
    soft = []
    for x in cands:
        pick = x['label'] == d['choice']
        p = probs.get(x['label'])
        ptxt = f'{int(round(float(p) * 100)):>3}%' if isinstance(p, (int, float)) and not isinstance(p, bool) else '    '
        text = clean(x['text'] or '')
        if pick:
            chosen_text = text
            lines.append(c.gbold(f'▶ {clean(x["label"])[:lw]:<{lw}} {ptxt}  ') + c.bold(text))
        else:
            lines.append(c.dim(f'· {clean(x["label"])[:lw]:<{lw}} {ptxt}  {text}'))
            soft.append((float(p) if isinstance(p, (int, float)) and not isinstance(p, bool) else 0.0, -len(lines), lines[-1]))
    why = chosen_text or ''
    extra = []
    if isinstance(d.get('conf'), (int, float)):
        extra.append(f'confidence {fnum(d["conf"], 2)}')
    preds = [f'{k} {fnum(v, 2)}' for k, v in (d['preds'] or {}).items() if isinstance(v, (int, float)) and v >= 0.05]
    if preds:
        extra.append('preds ' + ', '.join(preds))
    if d.get('latency_ms'):
        extra.append(f'{fnum(d["latency_ms"], 0)} ms')
    if why:
        lines += wrapped(why, width, '  does: ', '        ', limit=2)
    if extra:
        lines.append(clean(' · '.join(extra)))
    info = dict(d['info'] or {})
    if info.pop('no_request', None) is not None:
        rung = info.pop('recover_rung', None)
        why_r = info.pop('recover_why', None)
        lines.append(c.yellow(clip('  no model call: ' + ('recover rung ' + clean(rung) if rung else 'one candidate') + (f' ({clean(why_r)})' if why_r else ''), width)))
    for k, v in info.items():
        lines += [c.yellow(x) for x in wrapped(f'{k}: {clean(v)}', width, '  ! ', '    ', limit=2)]
    extra_soft = []
    if s['plan_reason']:
        planned = [c.dim(x) for x in wrapped(f'plan: {s["plan_reason"]}', width, '', limit=1)]
        lines += planned
        extra_soft += planned
    lines += step_lines(s, width, c, state)
    rec = s['recover'] or {}
    if rec.get('stuck'):
        lines.append(c.red(clip(clean(f'STUCK: {rec.get("why")} (stalled {fnum(rec.get("stalled_s"))} s / {rec.get("stalled_obs")} obs, rung {rec.get("rung")}, streak {rec.get("streak")})'), width)))
    elif rec:
        lines.append(f'recover: ok (rung {rec.get("rung")}, streak {rec.get("streak")})')
    for e in s['recovers'][-2:]:
        bits = [clean(e.get('status') or '?')]
        if e.get('target'):
            bits.append(clean(e['target']))
        if e.get('rung'):
            bits.append(f'rung {clean(e["rung"])}')
        if e.get('rungs'):
            bits.append('tried ' + '/'.join(clean(x) for x in e['rungs']))
        if e.get('why'):
            bits.append(f'({clean(e["why"])})')
        if e.get('s') is not None:
            bits.append(f'{fnum(e["s"])} s')
        bad = e.get('status') in ('blocked', 'marked-bad')
        txt = f'  recover@{e.get("n")}: ' + ' '.join(bits)
        lines.append(c.red(txt) if bad else c.dim(txt))
        extra_soft.append(lines[-1])
    if s['stop']:
        lines.append(c.red(f'STOPPED: {clean(s["stop"])}'))
    order = [x[2] for x in sorted(soft, key=lambda t: (t[0], t[1]))] + extra_soft
    return Sec('NOW', lines, soft=order)


def step_lines(s, width, c, state):
    d = s['decision']
    out = []
    chosen = next((x for x in (d or {}).get('cands') or [] if x['label'] == d['choice']), None) if d else None
    if state == 'executing' and chosen and chosen.get('lines'):
        out += wrapped('doing: ' + ' ; '.join(str(x) for x in chosen['lines']), width, '  ', '  ', limit=2)
    st = s['step'] or ((s['result'] or {}).get('steps') or [None])[-1]
    if st:
        det = f' — {clean(st["detail"])}' if st.get('detail') else ''
        mv = f', moved {fnum(st.get("moved"), 2)} m' if st.get('moved') is not None else ''
        sec = f' ({fnum(st.get("secs"), 1)} s{mv})' if st.get('secs') is not None else ''
        head = f'  step: {clean(st.get("src"))} → '
        room = max(10, width - vlen(head) - len(str(st.get('result') or '?')))
        out.append(head + word_color(c, st.get('result')) + clip(sec + det, room))
    r = s['result']
    if r and d and r.get('n') == d['n'] and r.get('word') and (not st or r['word'] != st.get('result')):
        out.append(f'  result of {d["n"]}: ' + word_color(c, r['word']) + (f' (moved {fnum(r["moved"], 2)} m)' if r.get('moved') is not None else ''))
    return out


def sec_world(s, width, c):
    st = s['state']
    age = s['state_age']
    if st is None:
        return Sec('WORLD', [title(c, width, 'WORLD', 'no state yet')])
    stale = age is not None and age > STALE_STATE_S and s['ended'] is None
    agetxt = f'state {ago(age)} ago' if age is not None else 'state age ?'
    lines = [title(c, width, 'WORLD', c.red(agetxt) if stale else agetxt)]
    life = st.get('life')
    hearts = f' ({fnum(life / 4.0, 2).rstrip("0").rstrip(".")} hearts)' if isinstance(life, (int, float)) and not isinstance(life, bool) else ''
    form = {1: 'child', 0: 'adult'}.get(st.get('child'))
    lines.append(clip(f'map {clean(st.get("map"))}{" · " + form if form else ""} · pos {fpos(st.get("pos"))} · facing {fnum(st.get("facing"), 0)}°', width))
    lines.append(clip(f'life {life}/{st.get("max_life")}{hearts} · rupees {st.get("rupees")} · prompt {clean(st.get("prompt"))} · music {clean(st.get("music") or "-")}', width))
    flags = []
    if st.get('event'):
        flags.append('event')
    if st.get('loading'):
        flags.append('loading')
    if st.get('text'):
        flags.append('text box')
    lines.append(clip(f'frame {st.get("frame")}' + (' · ' + ', '.join(flags) if flags else ''), width))
    return Sec('WORLD', lines)


def sec_eyes(s, width, c):
    if not s['vision_on']:
        return Sec('EYES', [title(c, width, 'EYES', 'vision: off')])
    v = s['vision']
    if v is None:
        extra = f'vision: on, no look yet' + (f' (last error: {clean(s["vision_err"]["error"])[:60]})' if s['vision_err'] else '')
        return Sec('EYES', [title(c, width, 'EYES', extra)])
    a = v['answers'] or {}
    bits = [f'look {v.get("seq")}', f'for decision {v.get("n")}', f'{ago(s["vision_age"])} ago' if s['vision_age'] is not None else '']
    if v.get('latency_ms'):
        bits.append(f'{fnum(v["latency_ms"], 0)} ms')
    lines = [title(c, width, 'EYES', ' · '.join(b for b in bits if b))]
    head = f'screen {clean(a.get("screen"))} · front {clean(a.get("front"))}'
    p = a.get('p') if isinstance(a.get('p'), dict) else {}
    top = sorted(((k, x) for k, x in p.items() if isinstance(x, (int, float))), key=lambda kv: -kv[1])[:4]
    lines += wrapped(head + (' · ' + ' '.join(f'{k} {x:.2f}' for k, x in top) if top else ''), width, '', '  ', limit=2)
    if a.get('says'):
        lines += wrapped('says: ' + clean(a['says']), width, '', '      ', limit=3)
    if s['vision_err']:
        lines.append(c.yellow(clip('last look failed: ' + clean(s['vision_err']['error']), width)))
    return Sec('EYES', lines[:6])


def sec_bugs(s, width, c):
    bugs = s['bugs']
    if not s['bug_on'] and not bugs:
        return Sec('BUGS', [title(c, width, 'BUGS', 'off: no findings file or vision in this run folder')])
    ttl = f'({len(bugs)})' if bugs else '(none yet)'
    src = ','.join(s['bug_sources']) or 'hunter on'
    fixed = [title(c, width, 'BUGS', f'{ttl} [{src}]')]
    if not bugs:
        fixed = [title(c, width, 'BUGS', 'no finding yet (bug hunter on)')]
    hist = []
    for b in bugs:
        when = clock_of(b['wall']) if b.get('wall') else (f't+{fnum(b["game_t"], 0)}s' if b.get('game_t') is not None else '--:--:--')
        where = f' @{clean(b["where"])}' if b.get('where') else ''
        hist.append(c.red(clip(f'{when} {clean(b["kind"])}', 40)) + clip(f'{where} {clean(b["text"])}', max(10, width - 12 - len(clean(b['kind'])))))
    return Sec('BUGS', fixed, hist)


def sec_notes(s, width, c):
    if not s['notes']:
        return Sec('NOTES', [])
    hist = [(c.dim('game: ') if src == 'game' else '') + clean(x) for src, x in s['notes']]
    return Sec('NOTES', [title(c, width, 'NOTES')], hist)


def sec_footer(s, width, c, mono=None):
    cost = s['cost']
    if s['cost_known']:
        txt = f'cost ${cost["usd"]:.4f} · {cost["calls"]} calls · {cost["tin"] / 1000:.1f}k tok in, {cost["tout"] / 1000:.1f}k out'
    elif s['n_dec'] and not s['model']:
        txt = 'cost $0 (no model calls: a rules decider)'
    else:
        txt = 'cost: n/a (nothing priced in the run folder yet)'
    dpm = f'{s["dpm"]:.1f} decisions/min' if s['dpm'] is not None else f'{s["n_dec"]} decisions'
    lines = [c.dim('─' * width), clip(f'{txt} · {dpm}', width)]
    tick = f' {SPIN[int(((mono if mono is not None else time.monotonic()) * 8)) % len(SPIN)]}' if s['ended'] is None else ''
    lines.append(clip(f'refreshed {s["clock"]}' + (f' · {s["errors"]} odd row(s) skipped' if s['errors'] else '') + (' · final frame' if s['ended'] is not None else tick), width))
    if s['ended'] is not None:
        extra = f' · {s["summary"]["decisions"]} decisions' if s['summary'].get('decisions') is not None else ''
        met = [g for g, st in s['goals'] if st == 'met']
        extra += f' · goals met {len(met)}/{len(s["goals"])}' if s['goals'] else ''
        lines.append(c.red(clip(f'RUN ENDED: {clean(s["ended"])}{extra}', width)) if not str(s['ended']).startswith(('solved',)) else c.green(clip(f'RUN ENDED: {clean(s["ended"])}{extra}', width)))
    return Sec('footer', lines)


SECTIONS = (sec_header, sec_now, sec_world, sec_eyes, sec_bugs, sec_notes, sec_footer)


def build_sections(snap, width, color):
    c = Paint(color)
    out = []
    for fn in SECTIONS:
        name = fn.__name__[4:].upper()
        try:
            out.append(fn(snap, width, c))
        except Exception as e:   # noqa: BLE001  a section that cannot be drawn says so; the others are still drawn
            out.append(Sec(name, [c.red(f'{name.lower()}: ? ({type(e).__name__}: {clean(e)})')]))
    return out


def fit(secs, height):
    """The lines for `height` rows: the oldest history lines go first (the longest history first); then the `soft` lines (the least likely
    candidates); then, as a last resort, the end of the middle sections. The header and the footer stay."""
    def total():
        return sum(len(x.fixed) + len(x.hist) for x in secs)
    while total() > height:
        having = [x for x in secs if x.hist]
        if not having:
            break
        max(having, key=lambda x: len(x.hist)).hist.pop(0)
    while total() > height:
        having = [x for x in secs if x.soft]
        if not having:
            break
        x = having[0]
        gone = x.soft.pop(0)
        if gone in x.fixed:
            x.fixed.remove(gone)
    lines = [ln for x in secs for ln in x.fixed + x.hist]
    if len(lines) > height:
        foot = secs[-1].fixed
        lines = lines[:max(0, height - len(foot))] + foot
        lines = lines[-height:]
    return lines


def render(snap, width=72, height=50, color=False):
    """The whole frame as one string (no trailing newline): `snap` is Run.snapshot()."""
    width = max(30, int(width))
    secs = build_sections(snap, width, color)
    return '\n'.join(clip(ln, width) for ln in fit(secs, max(5, int(height))))


def render_waiting(folder, elapsed_s, width=72, height=50, color=False, mono=None):
    c = Paint(color)
    tick = SPIN[int((mono if mono is not None else time.monotonic()) * 8) % len(SPIN)]
    queued = '(the game is queued behind other runs)'
    one = f'waiting for {clean(folder)} {queued}'
    if len(one) <= width:
        head = [one]
    else:
        f = clean(folder)
        room = max(8, width - len('waiting for '))
        head = ['waiting for ' + (f if len(f) <= room else '…' + f[-(room - 1):]), queued]
    lines = [c.cyan('═ LIVE PILOT ') + 'waiting'] + head + [
        f'elapsed {hms(elapsed_s)} {tick}',
        c.dim('transcript.jsonl or live/out.jsonl appears when the run starts; Ctrl-C quits'),
        f'refreshed {time.strftime("%H:%M:%S")}']
    out = []
    for ln in lines:
        out += wrapped(ln, width, '', '  ') if vlen(ln) > width and '\x1b' not in ln else [ln]
    return '\n'.join(clip(x, width) for x in out[:max(5, height)])


# ---- the command

HIDE, SHOW, HOME, EOL, EOS = '\x1b[?25l', '\x1b[?25h', '\x1b[H', '\x1b[K', '\x1b[J'


def term_size(args):
    ts = shutil.get_terminal_size((80, 50))
    return max(30, min(args.width or ts.columns, 160)), max(8, args.height or ts.lines)


def parse_args(argv):
    p = argparse.ArgumentParser(description='A live panel for a pilot run: what the pilot decides, as it happens.')
    p.add_argument('folder', help="the pilot's run folder (it may not exist yet)")
    p.add_argument('--once', action='store_true', help='print one frame and exit')
    p.add_argument('--interval', type=float, default=0.5, help='seconds between redraws (default 0.5)')
    p.add_argument('--width', type=int, default=0, help='columns (default: the terminal, re-read each frame)')
    p.add_argument('--height', type=int, default=0, help='rows (default: the terminal, 50 when there is none)')
    p.add_argument('--wait', type=float, default=DEFAULT_WAIT_S, help='seconds to wait for the run folder to appear (default 3 hours)')
    p.add_argument('--no-color', action='store_true')
    return p.parse_args(argv)


def main(argv=None, out=None):
    args = parse_args(argv)
    out = out or sys.stdout
    tty = out.isatty()
    live = tty and not args.once
    color = tty and not args.no_color and 'NO_COLOR' not in os.environ
    run = Run(args.folder)
    t0 = time.monotonic()
    code = 0

    def stop(*_):
        raise KeyboardInterrupt

    if live:
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGHUP, stop)
        out.write(HIDE)
    try:
        while True:
            run.poll(grace_s=DONE_GRACE_S if live else 0.0)
            w, h = term_size(args)
            if run.started:
                frame = render(run.snapshot(), w, h, color)
            else:
                frame = render_waiting(args.folder, time.monotonic() - t0, w, h, color)
            if live:
                out.write(HOME + (EOL + '\n').join(frame.split('\n')) + EOL + EOS)
            else:
                out.write(frame + '\n')
            out.flush()
            if run.ended is not None or not live:
                break
            if not run.started and time.monotonic() - t0 > args.wait:
                out.write(f'\ngave up waiting for {args.folder} after {hms(args.wait)}\n')
                code = 1
                break
            time.sleep(max(0.05, args.interval))
    except KeyboardInterrupt:
        code = 0
    except BrokenPipeError:
        code = 0
    finally:
        if live:
            try:
                out.write('\n' + SHOW)
                out.flush()
            except OSError:
                pass
    return code


if __name__ == '__main__':
    sys.exit(main())
