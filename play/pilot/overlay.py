#!/usr/bin/env python3
"""overlay: the pilot's decisions drawn on the game's own pictures, as stills, a contact sheet and a video.

    overlay.py RUN [--out DIR] [--layout below|side|over] [--width 1280] [--format jpg|png]
               [--from S] [--to S] [--every K] [--limit N] [--only P,P,...]
               [--sheet N] [--no-stills] [--video] [--fps 10] [--video-width W] [--looks]
               [--shots DIR] [--pilot DIR] [--state FILE] [--vision DIR] [--font F] [--font-size PX]

RUN is a pilot run folder: either a session folder with `pilot/` and `game/` below it (what solo_hold.py writes) or a pilot's own
run folder (`transcript.jsonl` at its top, pictures given with --shots). What it reads, all written by the pilot or the game:
  transcript.jsonl   one row per decision (goal, target, candidates, choice, decider, model, latency, cost, recover state), result,
                     goal, planner, counterfactual and recover rows
  out.jsonl          the game side's events; `gameplay` and `state` events carry the pilot's clock `t` and the game's picture count
  state.jsonl        the finer state stream (map, position, life, prompt) when the run kept it
  summary.json       the outcome (optional)
  vision/            vision.jsonl and the frames the vision model looked at (optional)
  game/shots/vk_<N>.png|jpg   the game's own pictures; N is the number of pictures presented so far

Alignment: the pilot's clock (game seconds since Link was in control) is mapped to the picture count N from the pairs (t, N) in the
files (piecewise linear), so a picture N belongs to the time t(N); the decision in force at t is the last one whose state was read at
or before t. A decision has three phases: `deciding` (its candidates are offered, the model has not answered), `running` (the
chosen step is being done) and `done` (the step's result word is known; the next decision's panel keeps it as `last`).

The panel (one per picture) says: goal and its target, decision number, time, picture number; the candidates with the chosen one
highlighted (and the model's probabilities when it gave them); the step and its result word; the last step's result; the model and
its latency, or that no model was asked; the cost so far; stuck or recovery state; the latest vision answer in a few words;
map, position, life, prompt. The game's own picture is never covered (`below` and `side` put the panel next to it; `over` puts a
translucent panel on the picture's right edge).

Output (in --out, default RUN/overlay): frames/ov_<N>.jpg, sheet.jpg (one annotated picture per decision, a labelled montage),
overlay.mp4 (--video: the pictures held for the real time between them, the panel changing at the moments its facts change,
sampled at --fps), looks/look-<seq>.jpg (--looks: the vision looks' own pictures with the panel as of the look) and index.json.
Needs ImageMagick (`magick`, `montage`); the video needs ffmpeg; the panel wants a monospace font (found with fc-match, or --font).
Standard library otherwise. The pictures are only as dense as the run's --shots interval: the game writes one every N presented
pictures (90 by default, about one every 1 to 3 s), so a video is held pictures with a live panel; ask the run for `--shots 20` or
less where a smoother clip matters.  Look at every picture before citing it.
"""
import argparse
import bisect
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SHOT_RE = re.compile(r'^vk_(\d+)\.(png|jpg|jpeg)$')
OK_WORDS = {'met', 'done', 'reached', 'opened', 'talked', 'picked', 'entered', 'closed', 'played', 'recovered', 'targeted', 'away',
            'out', 'turned', 'solved', 'swung', 'seen'}
BAD_WORDS = {'stuck', 'blocked', 'failed', 'died', 'lost', 'cut'}
COLORS = {'bg': '#14171d', 'band': '#222a36', 'text': '#eef1f5', 'dim': '#9aa5b5', 'accent': '#ffd34e', 'dark': '#101010',
          'ok': '#5fdc8e', 'warn': '#ffb454', 'bad': '#ff6e6e', 'info': '#78bdff'}
GLUE = '\x02'           # joins the words of one unbreakable item in wrap()
FIELD_COLS = 8           # width of a field label such as `STEP   `
LAYOUTS = ('below', 'side', 'over')


# ---------------------------------------------------------------------------------------------------------------- reading

def read_jsonl(path):
    rows = []
    try:
        text = Path(path).read_text(errors='replace')
    except OSError:
        return rows
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def read_json(path):
    try:
        v = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}
    return v if isinstance(v, dict) else {}


def number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def first_existing(paths):
    for p in paths:
        if p is not None and Path(p).exists():
            return Path(p)
    return None


class Files:
    """Where a run's files are; every one can be named explicitly."""

    def __init__(self, run, pilot=None, shots=None, state=None, vision=None):
        run = Path(run)
        self.run = run
        if pilot:
            pdir = Path(pilot)
        else:
            pdir = first_existing([run / 'pilot' if (run / 'pilot' / 'transcript.jsonl').exists() else None, run]) or run
        self.pilot = pdir
        self.transcript = pdir / 'transcript.jsonl'
        self.out = first_existing([pdir / 'out.jsonl', pdir / 'live' / 'out.jsonl'])
        self.state = Path(state) if state else first_existing([pdir / 'live' / 'state.jsonl', pdir / 'state.jsonl', run / 'live' / 'state.jsonl'])
        self.summary = first_existing([pdir / 'summary.json'])
        vdir = Path(vision) if vision else first_existing([pdir / 'vision'])
        self.vision_dir = vdir
        self.vision = first_existing([vdir / 'vision.jsonl']) if vdir else None
        self.shots = Path(shots) if shots else first_existing([run / 'game' / 'shots', run / 'shots', pdir / 'shots'])


def list_shots(folder):
    """[(picture number, path)] sorted by number."""
    found = []
    if folder and Path(folder).is_dir():
        for p in Path(folder).iterdir():
            m = SHOT_RE.match(p.name)
            if m:
                found.append((int(m.group(1)), p))
    return sorted(found)


# ---------------------------------------------------------------------------------------------------------------- clocks

class Clock:
    """The pilot's clock t <-> the game's picture count, piecewise linear over monotone (t, count) points."""

    def __init__(self, points):
        pts = []
        for t, p in sorted(points):
            if pts and (p < pts[-1][1] or t == pts[-1][0]):
                continue
            pts.append((t, p))
        self.t = [t for t, _ in pts]
        self.p = [p for _, p in pts]

    def __len__(self):
        return len(self.t)

    @staticmethod
    def _map(xs, ys, x):
        i = bisect.bisect_left(xs, x)
        j = 1 if i == 0 else (len(xs) - 1 if i >= len(xs) else i)
        x0, x1, y0, y1 = xs[j - 1], xs[j], ys[j - 1], ys[j]
        return float(y0) if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)

    def presents(self, t):
        return max(0.0, self._map(self.t, self.p, t))

    def time(self, presents):
        return self._map(self.p, self.t, presents)


def build_clock(out_events, decision_states, samples):
    """From the pairs (t, picture count) of out.jsonl and the decisions' states; the state stream's absolute times are shifted by
    the offset found where both name the same picture count. None when fewer than two usable pairs exist."""
    pts = [(float(e['t']), int(e['frame'])) for e in out_events
           if e.get('ev') in ('gameplay', 'state') and number(e.get('t')) and isinstance(e.get('frame'), int)]
    pts += [(float(s['t']), int(s['frame'])) for s in decision_states if number(s.get('t')) and isinstance(s.get('frame'), int)]
    abs_pts = [(float(s['t']), int(s['frame'])) for s in samples if number(s.get('t')) and isinstance(s.get('frame'), int)]
    if abs_pts and pts:
        by_frame = {}
        for t, f in abs_pts:
            by_frame.setdefault(f, t)
        for t, f in pts:
            if f in by_frame:
                offset = by_frame[f] - t
                clock = Clock([(a - offset, f2) for a, f2 in abs_pts] + pts)
                if len(clock) >= 2:
                    return clock
                break
    clock = Clock(pts)
    return clock if len(clock) >= 2 else None


class WallMap:
    """The pilot's clock t at a wall-clock time, from the rows that carry both (a result row's wall and its last step's t)."""

    def __init__(self, pairs):
        pts = []
        for w, t in sorted(pairs):
            if pts and (t < pts[-1][1] or w == pts[-1][0]):
                continue
            pts.append((w, t))
        self.w = [w for w, _ in pts]
        self.t = [t for _, t in pts]

    def __bool__(self):
        return bool(self.w)

    def __call__(self, wall):
        if not self.w:
            return None
        i = bisect.bisect_left(self.w, wall)
        if i == 0:
            return self.t[0] - (self.w[0] - wall)
        if i >= len(self.w):
            return self.t[-1] + (wall - self.w[-1])
        w0, w1, t0, t1 = self.w[i - 1], self.w[i], self.t[i - 1], self.t[i]
        return t0 + (t1 - t0) * (wall - w0) / (w1 - w0)


# ---------------------------------------------------------------------------------------------------------------- the run

class Decision:
    def __init__(self, row):
        st = row.get('state') if isinstance(row.get('state'), dict) else {}
        req = row.get('request') if isinstance(row.get('request'), dict) else {}
        self.n = row.get('n')
        self.goal = str(row.get('goal') or '')
        self.target = str(row.get('target') or '')
        self.decider = str(row.get('decider') or '')
        self.label = str(row.get('choice') or '')
        self.model = req.get('model') if isinstance(req.get('model'), str) else None
        self.latency_ms = row.get('latency_ms') if number(row.get('latency_ms')) else None
        self.decide_ms = row.get('decide_ms') if number(row.get('decide_ms')) else 0.0
        self.confidence = row.get('confidence') if number(row.get('confidence')) else None
        self.no_request = row.get('no_request')
        self.cost = row.get('cost_usd') if number(row.get('cost_usd')) else 0.0
        self.calls = 1 if (self.model or self.cost) else 0
        self.recover = row.get('recover') if isinstance(row.get('recover'), dict) else {}
        self.rung = row.get('recover_rung')
        self.why = row.get('recover_why')
        self.wall = row.get('wall') if number(row.get('wall')) else None
        self.state = st
        self.t_dec = float(st['t']) if number(st.get('t')) else None
        self.frame = st.get('frame') if isinstance(st.get('frame'), int) else None
        self.candidates = []
        for c in row.get('candidates') or []:
            if isinstance(c, dict) and c.get('label'):
                self.candidates.append((str(c['label']), str(c.get('text') or '')))
        self.probs = {}
        for a in row.get('answers') or []:
            if isinstance(a, dict) and isinstance(a.get('probabilities'), list):
                for pr in a['probabilities']:
                    if isinstance(pr, dict) and number(pr.get('probability')):
                        self.probs[str(pr.get('value'))] = float(pr['probability'])
                break
        self.text = next((t for lab, t in self.candidates if lab == self.label), '')
        # filled from the other rows
        self.result = None
        self.t_res = None
        self.detail = ''
        self.t_choice = None
        self.looks = []


class Look:
    def __init__(self, row, files):
        ans = row.get('answers') if isinstance(row.get('answers'), dict) else {}
        self.seq = row.get('seq')
        self.n = row.get('n')
        self.t = float(row['t']) if number(row.get('t')) else None
        self.wall = row.get('wall') if number(row.get('wall')) else None
        self.why = [str(w) for w in (row.get('why') or [])]
        self.front = ans.get('front')
        self.screen = ans.get('screen')
        self.p = {str(k): float(v) for k, v in (ans.get('p') or {}).items() if number(v)}
        self.says = ans.get('says')
        self.oddities = [str(o) for o in (row.get('oddities') or [])]
        self.cost = row.get('cost_usd') if number(row.get('cost_usd')) else 0.0
        self.latency_ms = row.get('latency_ms') if number(row.get('latency_ms')) else None
        self.model = row.get('model')
        fr = row.get('frame')
        self.frame_path = None
        if isinstance(fr, str) and files.vision_dir is not None:
            for base in (files.pilot, files.vision_dir, files.vision_dir.parent):
                cand = Path(base) / fr
                if cand.exists():
                    self.frame_path = cand
                    break
            else:
                cand = files.vision_dir / Path(fr).name
                if cand.exists():
                    self.frame_path = cand
        self.t_avail = self.t       # when the answer was known, on the pilot's clock (set by Run)


class Run:
    """A run folder read into decisions, results, goals, looks and the clocks."""

    def __init__(self, files, tail=6.0):
        self.files = files
        rows = read_jsonl(files.transcript)
        if not rows:
            raise SystemExit('overlay: no transcript rows in %s' % files.transcript)
        out = read_jsonl(files.out) if files.out else []
        samples = read_jsonl(files.state) if files.state else []
        self.summary = read_json(files.summary) if files.summary else {}
        by_n, self.decisions = {}, []
        planner, counter, results, goal_rows, recover_rows = {}, {}, {}, [], {}
        for r in rows:
            k = r.get('kind')
            if k == 'decision':
                d = Decision(r)
                by_n[d.n] = d
                self.decisions.append(d)
            elif k == 'result':
                results[r.get('n')] = r
            elif k == 'goal':
                goal_rows.append(r)
            elif k == 'planner':
                planner.setdefault(r.get('n'), []).append(r)
            elif k == 'counterfactual':
                counter.setdefault(r.get('n'), []).append(r)
            elif k == 'recover':
                recover_rows.setdefault(r.get('n'), []).append(r)
        self.decisions = [d for d in self.decisions if d.t_dec is not None]
        if not self.decisions:
            raise SystemExit('overlay: no decision row with a state time in %s' % files.transcript)
        self.decisions.sort(key=lambda d: d.t_dec)
        self.clock = build_clock(out, [d.state for d in self.decisions], samples)
        self.state_points = self._state_points(samples, out)
        anchors = []
        for n, r in results.items():
            steps = [s for s in r.get('steps') or [] if isinstance(s, dict) and number(s.get('t'))]
            if steps and number(r.get('wall')):
                anchors.append((float(r['wall']), float(steps[-1]['t'])))
        for g in goal_rows:
            if number(g.get('wall')) and number(g.get('t')):
                anchors.append((float(g['wall']), float(g['t'])))
        self.wallmap = WallMap(anchors)
        for i, d in enumerate(self.decisions):
            r = results.get(d.n)
            if r is not None:
                steps = [s for s in r.get('steps') or [] if isinstance(s, dict)]
                d.result = str(r.get('result') or '')
                timed = [s for s in steps if number(s.get('t'))]
                d.t_res = float(timed[-1]['t']) if timed else None
                inter = r.get('interaction') if isinstance(r.get('interaction'), dict) else {}
                d.detail = str(inter.get('detail') or (steps[-1].get('detail') if steps else '') or '')
            nxt = self.decisions[i + 1].t_dec if i + 1 < len(self.decisions) else None
            if d.t_res is None and d.result is not None:
                d.t_res = nxt if nxt is not None else d.t_dec
            for x in planner.get(d.n, []) + counter.get(d.n, []):
                if number(x.get('cost_usd')):
                    d.cost += float(x['cost_usd'])
                d.calls += 1
            d.recover_rows = recover_rows.get(d.n, [])
            tc = self.wallmap(d.wall) if (self.wallmap and d.wall is not None) else None
            if tc is None:
                tc = d.t_dec + d.decide_ms / 1000.0
            hi = d.t_res if d.t_res is not None else (nxt if nxt is not None else tc)
            d.t_choice = min(max(tc, d.t_dec), max(hi, d.t_dec))
        self.goals = sorted(((float(g['t']), str(g.get('goal')), str(g.get('status'))) for g in goal_rows if number(g.get('t'))))
        self.looks = []
        if files.vision:
            for r in read_jsonl(files.vision):
                lk = Look(r, files)
                if lk.t is not None:
                    if lk.wall is not None and self.wallmap:
                        lk.t_avail = max(lk.t, self.wallmap(lk.wall))
                    self.looks.append(lk)
            self.looks.sort(key=lambda lk: lk.t_avail)
            for lk in self.looks:
                d = next((d for d in self.decisions if d.n == lk.n), None)
                if d is not None:
                    d.cost += lk.cost
                    d.calls += 1
        self.final = {g: s for g, s in (self.summary.get('goals') or {}).items()} if isinstance(self.summary.get('goals'), dict) else {}
        ends = [d.t_res for d in self.decisions if d.t_res is not None] + [t for t, _, _ in self.goals]
        self.t_start = self.decisions[0].t_dec
        self.t_end = (max(ends) if ends else self.decisions[-1].t_dec) + tail
        self.total = len(self.decisions)

    @staticmethod
    def _state_points(samples, out):
        pts = []
        for s in samples:
            if isinstance(s.get('frame'), int):
                pts.append((s['frame'], s))
        if not pts:
            for e in out:
                if e.get('ev') == 'state' and isinstance(e.get('frame'), int):
                    pts.append((e['frame'], e))
        pts.sort(key=lambda x: x[0])
        return pts

    # -- queries
    def time_of(self, presents):
        return self.clock.time(presents) if self.clock else None

    def decision_at(self, t):
        i = bisect.bisect_right([d.t_dec for d in self.decisions], t) - 1
        return (self.decisions[i], self.decisions[i - 1] if i > 0 else None, i) if i >= 0 else (None, None, -1)

    def state_at(self, t, decision):
        """The nearest state sample (by picture count) or the decision's own state."""
        if self.state_points and self.clock:
            p = self.clock.presents(t)
            frames = [f for f, _ in self.state_points]
            i = bisect.bisect_left(frames, p)
            cands = [self.state_points[j][1] for j in (i - 1, i) if 0 <= j < len(self.state_points)]
            if cands:
                return min(cands, key=lambda s: abs(s['frame'] - p))
        return decision.state if decision is not None else {}

    def look_at(self, t):
        i = bisect.bisect_right([lk.t_avail for lk in self.looks], t) - 1
        return self.looks[i] if i >= 0 else None

    def goal_status(self, goal, t, finished):
        if any(g == goal and st == 'met' and gt <= t for gt, g, st in self.goals):
            return 'met'
        if finished and self.final.get(goal) == 'failed':
            return 'failed'
        return 'open'

    def key_times(self, t0, t1):
        """The moments the panel's facts change (and the window's ends), for the video."""
        ts = {t0, t1}
        for d in self.decisions:
            ts.update(x for x in (d.t_dec, d.t_choice, d.t_res) if x is not None)
        ts.update(lk.t_avail for lk in self.looks)
        ts.update(t for t, _, _ in self.goals)
        return sorted(t for t in ts if t0 <= t <= t1)


# ---------------------------------------------------------------------------------------------------------------- the panel

class Panel:
    """What the panel says at one moment: plain data, drawn by `rows`."""

    def __init__(self):
        self.goal = self.target = ''
        self.goal_status = 'open'
        self.n = None
        self.total = 0
        self.t = 0.0
        self.present = None
        self.phase = 'deciding'
        self.decider = ''
        self.candidates = []      # (label, probability or None, chosen)
        self.more = 0
        self.chosen_text = ''
        self.step_label = ''
        self.result = None
        self.detail = ''
        self.last = None          # (label, result, detail)
        self.model_line = ''
        self.cost = 0.0
        self.calls = 0
        self.state_line = ('moving', 'ok')
        self.vision = None        # [(text, colour)]
        self.where = []
        self.run_outcome = None


def result_color(word):
    w = (word or '').lower()
    if w in OK_WORDS:
        return 'ok'
    if w in BAD_WORDS:
        return 'bad'
    return 'warn'


def pct(p):
    return '%d%%' % round(100 * p)


def vision_words(lk, age):
    """The latest look in a few words: what it saw, the probabilities worth reading, what it flagged."""
    if lk is None:
        return None
    out = []
    head = 'look %.0f s ago (why: %s):' % (max(0.0, age), ','.join(lk.why) or 'asked')
    out.append((head, 'dim'))
    if lk.oddities:
        out.append(('ODD ' + ','.join(lk.oddities) + ';', 'bad'))
    seen = []
    if lk.front:
        seen.append('ahead ' + str(lk.front))
    if lk.screen and lk.screen != 'play':
        seen.append('screen ' + str(lk.screen))
    strong = sorted(((k, v) for k, v in lk.p.items() if v >= 0.5 and not k.startswith('clear_') and not k.endswith('_ok')),
                    key=lambda kv: -kv[1])[:3]
    seen += ['%s %s' % (k.replace('_', ' '), pct(v)) for k, v in strong]
    asked_stuck = 'stuck' in lk.why or lk.p.get('stuck', 0) >= 0.5
    if asked_stuck and 'stuck' in lk.p and lk.p['stuck'] < 0.5:
        seen.append('stuck %s' % pct(lk.p['stuck']))       # a look asked about being stuck says how stuck it thinks Link is
    if asked_stuck and 'clear_left' in lk.p and 'clear_right' in lk.p:
        seen.append('clear left %s right %s' % (pct(lk.p['clear_left']), pct(lk.p['clear_right'])))
    out.append((', '.join(seen) if seen else 'nothing to flag', 'info'))
    if lk.says:
        out.append(('"%s"' % lk.says, 'text'))
    return out


def model_text(d, phase):
    if d.model:
        bits = [d.model]
        if d.latency_ms is not None:
            bits.append('%.2f s' % (d.latency_ms / 1000.0))
        if d.confidence is not None:
            bits.append('sure %s' % pct(d.confidence))
        return '  '.join(bits) + ('  (asking)' if phase == 'deciding' else '')
    if d.decider == 'recover':
        return 'recovery ladder, no model'
    if d.decider == 'gate':
        return 'no question: ' + str(d.no_request or 'one valid candidate')
    return '%s, no model asked' % (d.decider or 'no decider')


def state_text(d, prev, phase):
    rc = d.recover or {}
    if d.decider == 'recover':
        return ('RECOVERY rung %s (%s)' % (d.rung or rc.get('rung') or '?', d.why or 'stuck'), 'warn')
    if rc.get('stuck'):
        return ('STUCK %.1f s (%s), ladder rung %s' % (float(rc.get('stalled_s') or 0), rc.get('why') or 'no progress', rc.get('rung', 0)), 'bad')
    if prev is not None:
        for r in getattr(prev, 'recover_rows', []):
            if r.get('status') == 'recovered':
                return ('recovered by %s after %.0f s' % (r.get('rung'), float(r.get('s') or 0)), 'ok')
    streak = rc.get('streak')
    if isinstance(streak, int) and streak >= 3:
        return ('same answer %d times running' % streak, 'warn')
    return ('moving freely', 'ok')


def where_bits(st):
    bits = []
    area = st.get('map') or st.get('area')
    if area:
        bits.append(str(area))
    pos = st.get('pos')
    if isinstance(pos, (list, tuple)) and len(pos) >= 3 and all(number(v) for v in pos[:3]):
        bits.append('x %.1f y %.1f z %.1f' % tuple(round(v, 1) + 0.0 for v in pos[:3]))
    if st.get('child') in (0, 1):
        bits.append('child' if st['child'] else 'adult')
    if number(st.get('life')) and number(st.get('max_life')):
        bits.append('life %d/%d' % (st['life'], st['max_life']))
    if number(st.get('rupees')):
        bits.append('rupees %d' % st['rupees'])
    if st.get('prompt') and st.get('prompt') != 'Empty':
        bits.append('prompt ' + str(st['prompt']))
    return bits


def panel_at(run, t, present=None, max_candidates=7):
    """The Panel for the pilot's time t, or None before the first decision."""
    d, prev, i = run.decision_at(t)
    if d is None:
        return None
    p = Panel()
    p.goal, p.target, p.n, p.total, p.t, p.present = d.goal, d.target, d.n, run.total, t, present
    finished = i == len(run.decisions) - 1 and d.t_res is not None and t >= d.t_res
    p.goal_status = run.goal_status(d.goal, t, finished)
    p.decider = d.decider
    if t < d.t_choice:
        p.phase = 'deciding'
    elif d.t_res is not None and t >= d.t_res:
        p.phase = 'done'
    else:
        p.phase = 'running'
    chosen = d.label if p.phase != 'deciding' else None
    cands = list(d.candidates)
    if d.label and not any(lab == d.label for lab, _ in cands):
        cands.insert(0, (d.label, d.text))
    if d.probs:
        cands.sort(key=lambda c: -d.probs.get(c[0], -1.0))
    shown = cands[:max_candidates]
    if chosen and not any(lab == chosen for lab, _ in shown):
        shown = shown[:max_candidates - 1] + [next(c for c in cands if c[0] == chosen)]
    p.candidates = [(lab, d.probs.get(lab), lab == chosen) for lab, _ in shown]
    p.more = len(cands) - len(shown)
    p.chosen_text = d.text if chosen else ''
    p.step_label = d.label
    p.result = d.result if p.phase == 'done' else None
    p.detail = d.detail if p.phase == 'done' else ''
    if prev is not None and prev.result is not None:
        p.last = (prev.label, prev.result, prev.detail)
    p.model_line = model_text(d, p.phase)
    for x in run.decisions[:i + 1]:
        if x is d and p.phase == 'deciding':
            continue
        p.cost += x.cost
        p.calls += x.calls
    p.state_line = state_text(d, prev, p.phase)
    lk = run.look_at(t)
    p.vision = vision_words(lk, t - lk.t_avail) if lk is not None else None
    p.where = where_bits(run.state_at(t, d))
    if finished and run.summary.get('outcome'):
        p.run_outcome = str(run.summary['outcome'])
    return p


# ---------------------------------------------------------------------------------------------------------------- text rows

def clean(text):
    """Text safe for magick -annotate / -label: printable ASCII on one line, no escapes, no `@file`."""
    s = ''.join(ch if 32 <= ord(ch) < 127 else ('?' if ord(ch) > 126 else ' ') for ch in str(text))
    s = re.sub(r'\s+', ' ', s.replace('\\', ' ')).strip(' ')
    s = s.replace('%', '%%')
    return (' ' + s) if s.startswith('@') else s


def fit(text, width):
    text = str(text)
    return text if len(text) <= width else text[:max(0, width - 3)] + '...'


def wrap(pieces, width, max_lines):
    """Greedy word wrap of [(text, colour)] into at most max_lines lines of [(text, colour)] runs; the last line ends in `...`."""
    words = []
    for text, color in pieces:
        for w in str(text).split():
            while len(w) > width:
                words.append((w[:width], color))
                w = w[width:]
            words.append((w, color))
    lines, cur, used = [], [], 0
    for w, color in words:
        need = len(w) + (1 if cur else 0)
        if cur and used + need > width:
            lines.append(cur)
            cur, used, need = [], 0, len(w)
        cur.append((w, color))
        used += need
    if cur:
        lines.append(cur)
    cut = len(lines) > max_lines
    lines = lines[:max_lines]
    if cut and lines:
        last = lines[-1]
        text = ' '.join(w for w, _ in last)
        while text and len(text) + 4 > width:
            last.pop()
            text = ' '.join(w for w, _ in last)
        last.append(('...', 'dim'))
    runs = []
    for ln in lines:
        segs, col = [], 0
        for k, (w, color) in enumerate(ln):
            if k:
                col += 1
            if segs and segs[-1][2] == color and segs[-1][0] + len(segs[-1][1]) == col - 1:
                segs[-1] = (segs[-1][0], segs[-1][1] + ' ' + w, color)
            else:
                segs.append((col, w, color))
            col += len(w)
        runs.append([(c, t.replace(GLUE, ' '), co) for c, t, co in segs])
    return runs


class Row:
    def __init__(self, segs, bar=None):
        self.segs = segs      # [(column, text, colour name)]
        self.bar = bar        # colour name of a background bar, or None

    def key(self):
        return (tuple(self.segs), self.bar)


def field(label, pieces, cols, max_lines=2):
    """Rows of `LABEL value...` with the value wrapped under itself."""
    body = max(8, cols - FIELD_COLS)
    rows = []
    for k, segs in enumerate(wrap(pieces, body, max_lines)):
        first = [(0, label, 'dim')] if k == 0 else []
        rows.append(Row(first + [(FIELD_COLS + c, t, col) for c, t, col in segs]))
    return rows


def header_rows(p, cols, wide):
    st = {'met': 'ok', 'failed': 'bad'}.get(p.goal_status, 'warn')
    right = 'decision %s/%s  t %.1f s%s' % (p.n, p.total, p.t, ('  p%d' % p.present) if p.present is not None else '')
    tag = '[%s]' % p.goal_status
    if wide:
        left_w = cols - len(right) - 2
        goal = fit(p.goal, max(6, left_w - 6 - len(tag) - 1 - 4 - len(p.target) - 1))
        segs = [(0, 'GOAL', 'dim'), (5, goal, 'text'), (6 + len(goal), tag, st)]
        col = 6 + len(goal) + len(tag) + 2
        tgt = fit(p.target, max(0, left_w - col - 4))
        segs += [(col, 'FOR', 'dim'), (col + 4, tgt, 'text'), (cols - len(right), right, 'dim')]
        return [Row(segs)]
    return [Row([(0, 'GOAL', 'dim'), (5, fit(p.goal, cols - 6 - len(tag)), 'text'), (cols - len(tag), tag, st)]),
            Row([(0, 'FOR', 'dim'), (5, fit(p.target, cols - 5), 'text')]),
            Row([(0, right, 'dim')])]


def candidate_rows(p, cols):
    who = ', '.join(x for x in (p.decider, 'choosing' if p.phase == 'deciding' else '') if x)
    rows = [Row([(0, 'CANDIDATES', 'dim')] + ([(11, fit('(%s)' % who, max(8, cols - 11)), 'dim')] if who else []))]
    for label, prob, chosen in p.candidates:
        pcol = ('%3d%%' % round(100 * prob)) if prob is not None else ''
        name = fit(label, cols - 3 - (5 if pcol else 0))
        segs = [(0, '>' if chosen else ' ', 'dark' if chosen else 'dim'), (2, name, 'dark' if chosen else 'text')]
        if pcol:
            segs.append((cols - 4, pcol, 'dark' if chosen else 'dim'))
        rows.append(Row(segs, bar='accent' if chosen else None))
    if p.more > 0:
        rows.append(Row([(2, '+%d more' % p.more, 'dim')]))
    return rows


def detail_rows(p, cols):
    rows = []
    if p.phase == 'deciding':
        step = [('choosing the next step', 'warn')]
    elif p.phase == 'running':
        step = [(p.step_label, 'accent'), ('running', 'warn')]
    else:
        step = [(p.step_label, 'accent'), ('->', 'dim'), (p.result or '?', result_color(p.result))]
    rows += field('STEP', step, cols)
    extra = p.detail if p.phase == 'done' and p.detail else p.chosen_text
    if extra:
        rows += [Row([(FIELD_COLS + c, t, col) for c, t, col in segs]) for segs in wrap([(extra, 'dim')], cols - FIELD_COLS, 2)]
    if p.last:
        label, result, detail = p.last
        rows += field('LAST', [(label, 'text'), ('->', 'dim'), (result, result_color(result))] + ([(detail, 'dim')] if detail else []), cols, 2)
    rows += field('MODEL', [(p.model_line, 'text')], cols, 1)
    cost = '$%.4f so far, %d model call%s' % (p.cost, p.calls, '' if p.calls == 1 else 's') if p.calls else 'none yet: no model call'
    rows += field('COST', [(cost, 'text')], cols, 1)
    rows += field('STATE', [(p.state_line[0], p.state_line[1])], cols, 1)
    rows += field('VISION', p.vision or [('no look yet', 'dim')], cols, 4)
    if p.where:
        glued = []
        for k, bit in enumerate(p.where):
            glued += ([('|', 'dim')] if k else []) + [(bit.replace(' ', GLUE), 'text')]
        rows += field('AT', glued, cols, 3)
    if p.run_outcome:
        rows += field('RUN', [(p.run_outcome, 'ok' if p.run_outcome.startswith('solved') else 'bad')], cols, 1)
    return rows


# ---------------------------------------------------------------------------------------------------------------- drawing

def find_font(name=None):
    if name:
        return name
    try:
        r = subprocess.run(['fc-match', '-f', '%{file}', 'Liberation Mono'], capture_output=True, text=True, timeout=10)
        if r.returncode == 0 and r.stdout.strip().endswith(('.ttf', '.otf')):
            return r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


class Style:
    def __init__(self, layout, width, font=None, fs=None):
        self.layout = layout
        self.width = width
        scale = width / 1280.0
        self.fs = fs or max(11, round({'below': 20, 'side': 17, 'over': 16}[layout] * scale))
        self.font = find_font(font)
        self.cw = self.fs * 0.6              # monospace advance (Liberation Mono, JetBrains Mono: 0.6 em)
        self.lh = round(self.fs * 1.42)
        self.pad = round(self.fs * 0.8)
        self.panel_w = {'below': width, 'side': round(560 * scale), 'over': round(480 * scale)}[layout]
        self.cols = max(20, int((self.panel_w - 2 * self.pad) / self.cw))


def panel_layout(p, st):
    """-> (header rows, left rows, right rows, columns of left, columns of right, wide)"""
    wide = st.layout == 'below'
    if wide:
        lcols = min(46, max(30, st.cols * 4 // 9))
        rcols = st.cols - lcols - 2
        return header_rows(p, st.cols, True), candidate_rows(p, lcols), detail_rows(p, rcols), lcols, rcols, True
    return header_rows(p, st.cols, False), candidate_rows(p, st.cols), detail_rows(p, st.cols), st.cols, st.cols, False


def panel_ops(p, st, min_height=0):
    """The magick arguments that draw the panel as its own image; returns (args, height, signature)."""
    hdr, left, right, lcols, rcols, wide = panel_layout(p, st)
    pad, lh, cw = st.pad, st.lh, st.cw
    base = (lh - st.fs) // 2 + round(st.fs * 0.82)      # the text's baseline below a row's top (no gravity: -annotate sets the baseline)
    if wide:
        body = max(len(left), len(right))
        blocks = [(left, pad), (right, pad + (lcols + 2) * cw)]
        hdr_h = lh * len(hdr) + pad
        height = hdr_h + pad // 2 + body * lh + pad
    else:
        stack = left + [Row([])] + right
        blocks = [(stack, pad)]
        hdr_h = lh * len(hdr) + pad
        height = hdr_h + pad // 2 + len(stack) * lh + pad
    height = max(height, min_height)
    height += height % 2
    ops = ['-size', '%dx%d' % (st.panel_w, height), 'xc:' + (COLORS['bg'] if st.layout != 'over' else COLORS['bg'] + 'd2')]
    if st.font:
        ops += ['-font', st.font]
    ops += ['-pointsize', str(st.fs)]
    ops += ['-fill', COLORS['band'], '-draw', 'rectangle 0,0 %d,%d' % (st.panel_w, hdr_h)]

    def draw(rows, x0, y0):
        for k, row in enumerate(rows):
            y = y0 + k * lh
            if row.bar:
                ops.extend(['-fill', COLORS[row.bar], '-draw', 'rectangle %d,%d %d,%d' % (
                    x0 - pad // 2, y, x0 + (lcols if wide else st.cols) * cw + pad // 2, y + lh - 2)])
            for col, text, color in row.segs:
                ops.extend(['-fill', COLORS[color], '-annotate', '+%d+%d' % (round(x0 + col * cw), y + base), clean(text)])

    draw(hdr, pad, pad // 2)
    for rows, x0 in blocks:
        draw(rows, x0, hdr_h + pad // 2)
    sig = hashlib.sha1(repr((p.n, p.phase, [r.key() for r in hdr + left + right], st.layout, st.width)).encode()).hexdigest()[:12]
    return ops, height, sig


def have(tool):
    return shutil.which(tool) is not None


def run_magick(args):
    r = subprocess.run(['magick'] + args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError('magick failed: %s' % (r.stderr.strip()[:300] or r.returncode))


def image_size(path):
    r = subprocess.run(['magick', 'identify', '-format', '%w %h', '%s[0]' % path], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError('cannot read %s: %s' % (Path(path).name, r.stderr.strip()[:200]))
    w, h = r.stdout.split()
    return int(w), int(h)


def render(frame, p, st, out, fw, fh, quality=90):
    """Frame + panel -> out. `fw`,`fh` are the size the game's picture is scaled to (all frames of a run share it)."""
    ops, ph, _ = panel_ops(p, st, min_height=fh if st.layout == 'side' else 0)
    q = ['-quality', str(quality)] if str(out).lower().endswith(('.jpg', '.jpeg')) else ['-depth', '8', '-define', 'png:compression-level=6']
    base = [str(frame), '-resize', '%dx%d!' % (fw, fh)]
    if st.layout == 'below':
        args = base + ['('] + ops + [')', '-append']
    elif st.layout == 'side':
        args = base + ['-background', COLORS['bg'], '('] + ops + [')', '+append']
    else:
        args = base + ['('] + ops + [')', '-gravity', 'NorthEast', '-geometry', '+%d+%d' % (st.pad, st.pad), '-composite']
    run_magick(args + q + [str(out)])


# ---------------------------------------------------------------------------------------------------------------- building

def parse_only(text):
    return [int(x) for x in re.split(r'[,\s]+', text.strip()) if x]


def select_shots(run, shots, args):
    """[(picture number, time, path)] in the window, thinned."""
    out = []
    lo = args.t_from if args.t_from is not None else run.t_start - 0.25
    hi = args.t_to if args.t_to is not None else run.t_end
    only = set(parse_only(args.only)) if args.only else None
    for n, path in shots:
        if only is not None and n not in only:
            continue
        t = run.time_of(n)
        if t is None or (only is None and not lo <= t <= hi):
            continue
        out.append((n, t, path))
    if args.every and args.every > 1:
        out = out[::args.every]
    if args.limit and len(out) > args.limit:
        step = len(out) / float(args.limit)
        out = [out[int(i * step)] for i in range(args.limit)]
    return out


def build_frames(run, picks, st, out_dir, fmt, fw, fh, jobs):
    frames_dir = out_dir / 'frames'
    frames_dir.mkdir(parents=True, exist_ok=True)
    entries = []

    def one(item):
        n, t, path = item
        p = panel_at(run, t, present=n, max_candidates=7 if st.layout == 'below' else 6)
        if p is None:
            return None
        dest = frames_dir / ('ov_%06d.%s' % (n, fmt))
        render(path, p, st, dest, fw, fh)
        d = run.decision_at(t)[0]
        return {'file': 'frames/' + dest.name, 'present': n, 't': round(t, 2), 'decision': p.n, 'goal': p.goal, 'step': p.step_label,
                'phase': p.phase, 'result': p.result, 'cost_usd': round(p.cost, 6), 'src': Path(path).name,
                'step_span': [round(d.t_choice, 2), None if d.t_res is None else round(d.t_res, 2)]}

    with ThreadPoolExecutor(max_workers=jobs) as ex:
        for e in ex.map(one, picks):
            if e:
                entries.append(e)
    return entries


def build_looks(run, st, out_dir, fmt, fw, fh, jobs):
    entries = []
    looks = [lk for lk in run.looks if lk.frame_path is not None]
    if not looks:
        return entries
    (out_dir / 'looks').mkdir(parents=True, exist_ok=True)

    def one(lk):
        p = panel_at(run, lk.t_avail, present=None, max_candidates=7 if st.layout == 'below' else 6)
        if p is None:
            return None
        dest = out_dir / 'looks' / ('look-%s.%s' % (lk.seq, fmt))
        render(lk.frame_path, p, st, dest, fw, fh)
        return {'file': 'looks/' + dest.name, 'seq': lk.seq, 't': round(lk.t_avail, 2), 'why': lk.why, 'oddities': lk.oddities}

    with ThreadPoolExecutor(max_workers=jobs) as ex:
        entries = [e for e in ex.map(one, looks) if e]
    return entries


def sheet_picks(run, entries, n):
    """One entry per decision (the picture nearest the middle of its running phase), thinned evenly to n."""
    best = {}
    for e in entries:
        lo, hi = e['step_span']
        mid = (lo + (hi if hi is not None else lo)) / 2.0
        k = e['decision']
        if k not in best or abs(e['t'] - mid) < abs(best[k]['t'] - best[k]['_mid']):
            best[k] = dict(e, _mid=mid)
    picks = sorted(best.values(), key=lambda e: e['t'])
    if n and len(picks) > n:
        step = len(picks) / float(n)
        picks = [picks[int(i * step)] for i in range(n)]
    return picks


def build_sheet(entries, out_dir, st, tile=3, thumb=520):
    if not entries or not have('montage'):
        return None
    cmd = ['montage', '-background', COLORS['bg'], '-fill', 'white', '-pointsize', '15']
    if st.font:
        cmd += ['-font', st.font]
    for e in entries:
        label = clean('d%s p%s %s %s' % (e['decision'], e['present'], e['step'], ('-> ' + e['result']) if e['result'] else ''))
        cmd += ['-label', label, str(out_dir / e['file'])]
    dest = out_dir / 'sheet.jpg'
    cmd += ['-tile', '%dx' % tile, '-geometry', '%dx+4+4' % thumb, '-quality', '88', str(dest)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError('montage failed: ' + r.stderr.strip()[:300])
    return dest


def keyframes(run, shots, t0, t1):
    """[(time, picture path, picture number, duration)] covering [t0, t1]: a new one where a picture arrives or a fact changes."""
    times = list(run.key_times(t0, t1))
    for n, t, _ in shots:
        if t0 <= t <= t1:
            times.append(t)
    times = sorted(set(math.ceil(x * 1000) / 1000.0 for x in times))      # up to a millisecond: a key frame is never just before its event
    merged = []
    for t in times:
        if not merged or t - merged[-1] >= 0.05:
            merged.append(t)
    shot_times = [t for _, t, _ in shots]
    keys = []
    for i, t in enumerate(merged):
        j = bisect.bisect_right(shot_times, t + 1e-6) - 1
        n, _, path = shots[max(j, 0)]
        end = merged[i + 1] if i + 1 < len(merged) else t1
        if end - t > 1e-3:
            keys.append((t, path, n, end - t))
    return keys


def build_video(run, shots_all, st, out_dir, fw, fh, jobs, fps, video_width, t0, t1):
    if not have('ffmpeg'):
        return None, 'ffmpeg is not installed'
    shots = [(n, run.time_of(n), p) for n, p in shots_all if run.time_of(n) is not None]
    if not shots:
        return None, 'no pictures'
    keys = keyframes(run, shots, t0, t1)
    if not keys:
        return None, 'no key frames in the window'
    tmp = Path(tempfile.mkdtemp(prefix='overlay-video-'))
    try:
        by_sig, jobs_list, images = {}, [], []
        for t, path, n, dur in keys:
            p = panel_at(run, t, present=n, max_candidates=7 if st.layout == 'below' else 6)
            if p is None:
                images.append(None)
                continue
            sig = (str(path), panel_ops(p, st)[2])
            if sig not in by_sig:
                by_sig[sig] = tmp / ('k%04d.jpg' % len(by_sig))
                jobs_list.append((path, p, by_sig[sig]))
            images.append(by_sig[sig])

        def one(item):
            path, p, dest = item
            render(path, p, st, dest, fw, fh, quality=88)

        with ThreadPoolExecutor(max_workers=jobs) as ex:
            list(ex.map(one, jobs_list))
        # a constant-rate image sequence: output frame i is the key frame in force at t0 + i / fps (real speed)
        seq = tmp / 'seq'
        seq.mkdir()
        starts = [k[0] for k in keys]
        valid = [im for im in images if im is not None]
        if not valid:
            return None, 'no frame had a decision yet'
        count = max(1, round((t1 - t0) * fps))
        for i in range(count):
            j = max(0, bisect.bisect_right(starts, t0 + i / float(fps) + 1e-9) - 1)
            src = images[j] or next((im for im in images[j:] if im is not None), valid[-1])
            try:
                os.link(src, seq / ('%06d.jpg' % i))
            except OSError:
                shutil.copyfile(src, seq / ('%06d.jpg' % i))
        dest = out_dir / 'overlay.mp4'
        vf = ('scale=%d:-2:flags=lanczos,format=yuv420p' % video_width) if video_width else 'scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p'
        r = subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(fps), '-i', str(seq / '%06d.jpg'), '-vf', vf,
                            '-c:v', 'libx264', '-crf', '26', '-preset', 'veryfast', '-movflags', '+faststart', '-an', str(dest)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            return None, 'ffmpeg failed: ' + r.stderr.strip()[:300]
        return dest, None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def build(args):
    if not have('magick'):
        raise SystemExit('overlay: ImageMagick (`magick`) is not installed')
    files = Files(args.run, pilot=args.pilot, shots=args.shots, state=args.state, vision=args.vision)
    run = Run(files)
    shots = list_shots(files.shots)
    if not shots:
        raise SystemExit('overlay: no pictures vk_<N>.png in %s (use --shots)' % (files.shots or 'the run folder'))
    if run.clock is None:
        raise SystemExit('overlay: the run has no (time, picture count) pairs to align the pictures with')
    out_dir = Path(args.out) if args.out else Path(args.run) / 'overlay'
    out_dir.mkdir(parents=True, exist_ok=True)
    fw0, fh0 = image_size(shots[0][1])
    fw = args.width
    fh = round(fw * fh0 / fw0 / 2) * 2
    st = Style(args.layout, fw, font=args.font, fs=args.font_size)
    jobs = args.jobs or min(8, os.cpu_count() or 2)
    picks = [] if args.no_stills else select_shots(run, shots, args)
    entries = build_frames(run, picks, st, out_dir, args.format, fw, fh, jobs) if picks else []
    index = {'run': files.run.name, 'layout': args.layout, 'width': fw, 'decisions': run.total, 'frames': entries,
             'outcome': run.summary.get('outcome')}
    if args.sheet and entries:
        picked = sheet_picks(run, entries, args.sheet)
        if build_sheet(picked, out_dir, st):
            index['sheet'] = 'sheet.jpg'
            index['sheet_frames'] = [e['present'] for e in picked]
    if args.looks:
        index['looks'] = build_looks(run, st, out_dir, args.format, fw, fh, jobs)
    if args.video:
        t0 = args.t_from if args.t_from is not None else run.t_start
        t1 = args.t_to if args.t_to is not None else run.t_end
        dest, why = build_video(run, shots, st, out_dir, fw, fh, jobs, args.fps, args.video_width, t0, t1)
        index['video'] = dest.name if dest else None
        index['video_seconds'] = round(t1 - t0, 2) if dest else None
        if why:
            index['video_error'] = why
            print('overlay: no video: ' + why, file=sys.stderr)
    (out_dir / 'index.json').write_text(json.dumps(index, indent=1) + '\n')
    print('overlay: %d frames in %s%s%s%s' % (len(entries), out_dir,
                                              ', sheet.jpg' if index.get('sheet') else '',
                                              ', %d looks' % len(index['looks']) if index.get('looks') else '',
                                              ', overlay.mp4' if index.get('video') else ''))
    return 0 if (entries or args.no_stills) else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('run')
    ap.add_argument('--out')
    ap.add_argument('--layout', choices=LAYOUTS, default='below')
    ap.add_argument('--width', type=int, default=1280, help='width the game picture is scaled to (default 1280)')
    ap.add_argument('--format', choices=('jpg', 'png'), default='jpg')
    ap.add_argument('--from', dest='t_from', type=float, help='first moment, pilot seconds (game seconds since Link was in control)')
    ap.add_argument('--to', dest='t_to', type=float, help='last moment, pilot seconds')
    ap.add_argument('--every', type=int, default=1, help='keep every Kth picture')
    ap.add_argument('--limit', type=int, default=0, help='at most N pictures, spread evenly')
    ap.add_argument('--only', help='only these picture numbers, comma separated (any time)')
    ap.add_argument('--no-stills', action='store_true', help='write no frames (and no sheet): only --looks and --video')
    ap.add_argument('--sheet', type=int, default=12, help='pictures on the contact sheet (0: none)')
    ap.add_argument('--video', action='store_true', help='write overlay.mp4 (needs ffmpeg)')
    ap.add_argument('--fps', type=int, default=10)
    ap.add_argument('--video-width', type=int, default=0, help='scale the video to this width (default: as the pictures)')
    ap.add_argument('--looks', action='store_true', help="also annotate the vision looks' own pictures")
    ap.add_argument('--shots')
    ap.add_argument('--pilot')
    ap.add_argument('--state')
    ap.add_argument('--vision')
    ap.add_argument('--font')
    ap.add_argument('--font-size', type=int)
    ap.add_argument('--jobs', type=int, default=0)
    return build(ap.parse_args(argv))


if __name__ == '__main__':
    sys.exit(main())
