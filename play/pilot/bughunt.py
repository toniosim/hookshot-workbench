#!/usr/bin/env python3
"""Bug hunting: detectors that read what a played session left behind (or is leaving) and say what looks wrong.

The pilot plays (free roam, a chapter, a co-op pair); the detectors watch; every finding becomes a repro packet
(bugpacket.py) with a deduplication key. This module is the detectors. Standard library only (the model questions go
through vision.py / openai_api.py when asked for); nothing here starts a game or takes a lock.

    bughunt.py analyze <session folder|run folder> [--side NAME=PATH ...] [--bounds b.json] [--baseline k.json] [--json]
    bughunt.py baseline <game log> ... --out known-log.json        the log lines a reference build says (shapes, counts)
    bughunt.py bounds <world folder> --out bounds.json             per map: the box of its walkable data (private output)

What a side is (`load_side`): the evidence of ONE game, from any of the layouts the harness leaves:
  state samples     pilot/live/state.jsonl (hsap's journal), or <side>/state.jsonl of a co-op session (`{"w", "game": {...}}`)
  the pilot's events  out.jsonl (steps with result words, `gameplay`, `done`), steps.txt (every line sent: the input log)
  the game's log    <project>_log.txt (the names hs_names.py gives) / log.txt / run.log;  hs-run's summary.txt counters;  exit.txt;  kernel.txt
  presents          present.csv (frame, return_ns, interval_ns, ...): the same monotonic clock as the samples' `t`
  pictures          shots/vk_<present>.png
A detector is `fn(side, cfg, ...) -> Result`; a Result has findings and a status: `ok` (looked, nothing), `found`, or `unknown`
(the input needed was missing or too thin to judge: never turned into a pass, as cpdetect does it).

Detectors and what they judge:
  crash     hs-run's counters (fatal, crash, devlost, nocore, kernel, nvrm), an exit code that is not 0/124/143, FATAL / CRASH: lines
  hang      no new sample (so no new frame) for hang_s while the game lives; a frame counter that stands still; a run that ended
            on its wall with the pilot never saying `done`
  stall     present gaps of stall_warn_ms and up, grouped; a gap inside a load, a scene or the first seconds is `info`, not a finding
  softlock  inputs going in (>= softlock_inputs steps) and nothing changing for softlock_s: position within softlock_move_m, map,
            life, rupees, event, prompt, music, flags; a text box (event, no cutscene music) and a cutscene are told apart
  oob       Link below a map's floor, above its ceiling, outside its box by oob_margin_m, or on a map the bounds do not know, for
            oob_samples samples in a row, outside events and loads
  visual    pictures: black while the state says play, the same picture twice while Link moved, flicker (a A B A pattern in
            consecutive pictures while nothing moved), and the model's fixed questions (missing or stretched textures, a body drawn
            wrong, Link over a void, corrupt picture)
  log       lines with a trouble word whose shape (numbers and addresses blanked) is not in the baseline of a reference build
  audio     audio error lines; the renderer never opened; (an audio-level check needs a log line the headless game does not write:
            `unknown` with the reason)
  desync    (a pair) shared flags that disagree after the grace time; a body far from its player's real place is cpdetect's jank
  give      an item counter that rises by more than the rule's per_flag when its flag flips once (the co-op shared-chest double give)
Findings carry `key`, a deduplication key: kind, subtype, map and a coarse cell of the place, or the line's shape: the same bug found
twice in two sessions has one key (bugpacket.Registry keeps the table).
"""
import argparse
import csv
import gzip
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field, asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
_H = HERE.parent.parent   # the harness folder (in a checkout of the workbench repository its root: hs_names.py sits in harness/ there), as pilot.py finds it
sys.path.insert(0, str(_H if (_H / 'hs_names.py').is_file() else _H / 'harness'))
import hs_names  # noqa: E402  (the game's log and executable file names: one copy)

LOG_NAMES = tuple(hs_names.Names(p).log for p in hs_names.PROJECTS) + ('log.txt', 'run.log')   # a side's game log: the project's own name, or what a co-op side or a plain run kept
EXE_NAMES = tuple(hs_names.Names(p).executable for p in hs_names.PROJECTS)

EXPECTED_EXIT = (0, 124, 143)   # hs-run.sh: the wall (124), our own SIGTERM (143) and a clean exit are not failures
INPUT_VERBS = {'walk', 'run', 'press', 'stick', 'push', 'raw', 'interact', 'chest', 'talk', 'advance', 'pickup', 'enter', 'faceat',
               'ztarget', 'camera', 'ocarina', 'item', 'swing', 'shield', 'roll', 'sidestep', 'face', 'approach', 'until', 'save'}
INPUT_NOT = {'wait', 'report', 'watch', 'shot', 'end', 'rendezvous'}
SEVERITIES = ('error', 'warning', 'info')
TROUBLE = re.compile(r'(?i)\b(error|errors|fail|failed|failure|fatal|crash|crashed|abort|aborted|assert|assertion|invalid|exception|'
                     r'overflow|underflow|leak|corrupt|corrupted|denied|refused|device lost|timed? ?out|unimplemented|not bound|'
                     r'no image|not ready|starved|deadlock|stopped at|segmentation|unhandled|unexpected|cannot|can\'t|bad )')
HARD = re.compile(r'FATAL|CRASH:|(?i:segmentation fault|assertion failed|abort(ed)?\b|device lost|VK_ERROR_DEVICE_LOST)')
AUDIO_BAD = re.compile(r'(?i)audio[^\n]*\b(fail|failed|error|underrun|xrun|dropped|lost|stopped|disconnect|no device|unavailable)\b')


# ====================================================================== config, findings

@dataclass
class Config:
    """Thresholds. Every one is a number a plan may override (`Config.from_dict`); the defaults are the first guesses the
    hunt's first real data is read against."""
    stall_warn_ms: float = 600.0       # a present gap this long is a hitch (a warning)
    stall_error_ms: float = 3000.0     # ... this long a stall (an error)
    stall_group_s: float = 2.0         # gaps this close are one stall
    warmup_s: float = 15.0             # seconds of game time at the start in which gaps are explained (programs being prepared)
    load_grace_s: float = 3.0          # a gap within this of a load or a scene is explained
    hang_s: float = 30.0               # no sample for this long while the game lives
    nocore_warn: int = 20              # `ran without a core` lines below this many are noise (every run says a few), above it a warning
    softlock_s: float = 180.0          # nothing changes for this long while inputs go in
    softlock_scene_factor: float = 2.0 # a cutscene is allowed this many times longer
    softlock_inputs: int = 3           # at least this many input steps in the window
    softlock_move_m: float = 0.5       # Link counts as having moved beyond this
    oob_floor_m: float = 25.0          # below the lowest walkable vertex of the map by this much
    oob_ceiling_m: float = 120.0       # above the highest by this much
    oob_margin_m: float = 40.0         # outside the box of the walkable data by this much
    oob_samples: int = 3               # samples in a row
    vision_max: int = 24               # model looks per side
    vision_p: float = 0.75             # a probability at or above is a finding
    black_luma: float = 6.0            # mean luma (0..255) of a picture below this is black
    black_pictures: int = 2            # black pictures in a row with the state saying play
    frozen_presents: int = 45          # two pictures this many presents apart ...
    frozen_move_m: float = 1.0         # ... identical, while Link moved this much, are a frozen picture
    flicker_gap: int = 6               # consecutive pictures at most this many presents apart
    flicker_diff: float = 6.0          # mean abs thumbnail difference (0..255) that counts as a change
    flicker_same: float = 2.0          # ... and as the same
    burst_n: int = 8                   # consecutive pictures in a burst (the bridge's `shot`, asked n times at once)
    burst_diff: float = 14.0           # the live check suspects a picture that differs from the periodic one before it by this much while nothing moved
    burst_max: int = 6                 # bursts per session (a suspicion or a still-moment probe each)
    burst_gap_s: float = 40.0          # at least this long between two bursts
    burst_probe_every_s: float = 75.0  # a still-moment probe (a burst with no suspicion, the data for the false-positive rate) this often ...
    burst_probe_still_s: float = 2.5   # ... once Link and the camera stood still this long, ...
    burst_probe_after_s: float = 8.0   # ... and not before this many seconds of control (the area's title card and the HUD fade in and out then)
    burst_probe_max: int = 3           # ... at most this many a session
    settle_s: float = 2.0              # pictures this soon after a load or a map change (a placement, a door, a teleport) are the fade-in: not judged
    pressure_margin_s: float = 1.0     # a stall is compared with the machine's pressure from this long before it to this long after
    pressure_cpu: float = 0.15         # the machine is short of CPU when tasks waited for it this share of that time (PSI cpu some) ...
    pressure_io_full: float = 0.10     # ... or when all non-idle tasks waited for the disk (io full) ...
    pressure_mem_full: float = 0.10    # ... or for memory (memory full)
    peer_gone_s: float = 10.0          # co-op lines about a player going away within this of the first game's end are the shutdown
    net_over_factor: float = 1.25      # a co-op send peak over the rate limit by less than this factor is the limit being touched, not exceeded
    link_delay_explains_ms: int = 100  # a link the case delays by this much or more (each way): the players' [lag] and [starved] body findings are by design
    snap_after_stall_s: float = 25.0   # a body snap within this after a stall of either game is the known snap after a stall
    desync_grace_s: float = 10.0       # shared values must agree this long after the last change
    give_settle_s: float = 6.0         # a counter is read this long after its flag flipped
    give_lookback_s: float = 30.0      # ... and compared with what it was this long before (the item is given while the message is open; the flag flips when it closes)
    log_max_shapes: int = 40           # new log shapes reported per side
    expected_exit: tuple = EXPECTED_EXIT
    shared: tuple = ()                 # flag names both sides must agree on
    give_rules: tuple = ()             # ({"name", "flag", "counter", "per_flag"}, ...)
    artefacts: tuple = ()              # regexes of finding text that are known harness artefacts (reported as `artefact`)

    @classmethod
    def from_dict(cls, d=None):
        c = cls()
        for k, v in (d or {}).items():
            if not hasattr(c, k):
                raise ValueError(f'unknown config key {k}')
            old = getattr(c, k)
            setattr(c, k, tuple(v) if isinstance(old, tuple) else type(old)(v))
        return c


@dataclass
class Finding:
    kind: str
    sub: str
    severity: str
    side: str
    text: str
    t: float = None            # the sample clock (monotonic seconds) the finding is at
    frame: int = None          # the present counter there
    game_s: float = None       # seconds of play since control began
    map: str = None
    pos: list = None
    evidence: dict = field(default_factory=dict)
    key: str = ''
    status: str = 'new'        # new | duplicate | artefact (the registry and the artefact patterns set it)

    def to_dict(self):
        return asdict(self)


class Result:
    def __init__(self, name):
        self.name, self.findings, self.reason, self.looked = name, [], None, 0

    @property
    def status(self):
        if any(f.severity != 'info' for f in self.findings):
            return 'found'
        return 'unknown' if self.reason else 'ok'

    def unknown(self, reason):
        self.reason = reason
        return self

    def add(self, f):
        self.findings.append(f)
        return f

    def to_dict(self):
        return {'name': self.name, 'status': self.status, 'reason': self.reason, 'looked': self.looked,
                'findings': len([f for f in self.findings if f.severity != 'info']),
                'explained': len([f for f in self.findings if f.severity == 'info'])}


ZERO_COUNT = re.compile(r'(?i)\b0 (?:failed|failures?|starved(?: grants)?|errors?|timed? ?out|timeouts?|escapes|refused|dropped)\b')


def trouble(line):
    """Whether a log line says something is wrong: a trouble word, not counted as zero (`0 starved grants` is accounting)."""
    return bool(TROUBLE.search(ZERO_COUNT.sub('', line)) or HARD.search(line))


def shape(line, width=170):
    """A log line with what varies blanked: the thread's name, hex, numbers (also sizes like 85x40x1), long ids, paths. Two runs of one
    build say the same lines in the same shapes."""
    s = re.sub(r'^\[hos [^\]]*\]', '[hos #]', line.strip())
    s = re.sub(r'\b0x[0-9a-fA-F]+', '0x#', s)
    s = re.sub(r'\b\d+x\d+(?:x\d+)?\b', '#x#', s)
    s = re.sub(r'\b[0-9a-f]{12,}\b', '#id', s)
    s = re.sub(r'(?<![\w.])-?\d+(\.\d+)?(e[+-]?\d+)?(?![\w])', '#', s)
    s = re.sub(r'/[\w./-]{8,}', '/path', s)
    return re.sub(r'\s+', ' ', s)[:width]


def cell(v, size):
    return int(math.floor(v / size))


def make_key(kind, sub, *parts):
    """kind:sub:<8 hex of the parts>. The parts are what makes two findings one bug (a map and a coarse cell, a line's shape)."""
    h = hashlib.sha1('\x1f'.join(str(p) for p in parts).encode()).hexdigest()[:8]
    return f'{kind}:{sub}:{h}'


def place_key(kind, sub, mp, pos, size):
    c = (cell(pos[0], size), cell(pos[2], size)) if pos else ('-', '-')
    return make_key(kind, sub, mp or '-', *c)


# ====================================================================== reading a side

def read_jsonl(path):
    out = []
    try:
        opener = gzip.open if str(path).endswith('.gz') else open
        with opener(path, 'rt', errors='replace') as f:
            for ln in f:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    out.append(json.loads(ln))
                except ValueError:
                    pass
    except OSError:
        pass
    return out


def norm_state(row):
    """A flat state sample from either journal: hsap's rows are flat, a co-op session's are {"w", "frame", "game": {...}}."""
    g = row.get('game') if isinstance(row.get('game'), dict) else row
    if 't' not in g or 'frame' not in g:
        return None
    s = dict(g)
    if 'age' in s and 'child' not in s:
        s['child'] = 1 if s['age'] in ('child', 'Child', 0) else 0
    if 'w' in row:
        s['w'] = row['w']
    s['t'], s['frame'] = float(s['t']), int(s['frame'])
    s.setdefault('flags', {})
    s['flags'] = s['flags'] or {}
    if s.get('changed') is None:
        s['changed'] = {}
    return s


def first_existing(root, names):
    for n in names:
        p = Path(root) / n
        if p.is_file():
            return p
    return None


def pick_log(*folders):
    for f in folders:
        for n in LOG_NAMES:
            p = Path(f) / n
            if p.is_file():
                return p
    return None


COUNTERS_RX = re.compile(r'\b(fatal|crash|devlost|nocore|kernel|nvrm)=(\w+)')


class Side:
    """The evidence of one game. Everything is read lazily; a missing file is an empty list, never an error."""

    def __init__(self, root, name='solo', game=None, pilot=None):
        self.root, self.name = Path(root), name
        self.game = Path(game) if game else self.root
        self.pilot = Path(pilot) if pilot else None
        self._cache = {}

    def _memo(self, k, fn):
        if k not in self._cache:
            self._cache[k] = fn()
        return self._cache[k]

    @property
    def state_path(self):
        cands = [self.root / 'state.jsonl']
        if self.pilot:
            cands += [self.pilot / 'live' / 'state.jsonl']
        cands += [self.root / 'pilot' / 'live' / 'state.jsonl', self.root / 'live' / 'state.jsonl']
        return next((p for p in cands if p.is_file()), None)

    @property
    def states(self):
        def go():
            p = self.state_path
            rows = [norm_state(r) for r in read_jsonl(p)] if p else []
            rows = [r for r in rows if r]
            rows.sort(key=lambda r: r['t'])
            return rows
        return self._memo('states', go)

    @property
    def events(self):
        def go():
            for base in (self.pilot, self.root / 'pilot', self.root):
                if base is None:
                    continue
                for p in (base / 'out.jsonl', base / 'live' / 'out.jsonl'):
                    if p.is_file():
                        return read_jsonl(p)
            return []
        return self._memo('events', go)

    @property
    def steps(self):
        return [e for e in self.events if e.get('ev') == 'step']

    @property
    def steps_text(self):
        for base in (self.pilot, self.root / 'pilot', self.root):
            if base is None:
                continue
            for p in (base / 'steps.txt', base / 'live' / 'steps.txt'):
                if p.is_file():
                    return p.read_text(errors='replace').splitlines()
        return []

    @property
    def inputs_path(self):
        """hsap's input journal (every press, stick and sequence request as sent, with its present): pilot/live/inputs.jsonl."""
        for base in (self.pilot, self.root / 'pilot', self.root):
            if base is None:
                continue
            for p in (base / 'live' / 'inputs.jsonl', base / 'inputs.jsonl'):
                if p.is_file():
                    return p
        return None

    @property
    def inputs(self):
        return self._memo('inputs', lambda: read_jsonl(self.inputs_path) if self.inputs_path else [])

    @property
    def log_path(self):
        return pick_log(self.game, self.root, self.pilot or self.root, self.root / 'pilot')

    @property
    def log(self):
        def go():
            p = self.log_path
            if not p:
                return []
            try:
                return p.read_text(errors='replace').splitlines()
            except OSError:
                return []
        return self._memo('log', go)

    @property
    def counters(self):
        def go():
            for base in (self.game, self.root, self.pilot or self.root):
                for n in ('summary.txt', 'hs-run-summary.txt'):
                    p = Path(base) / n
                    if p.is_file():
                        text = p.read_text(errors='replace')
                        c = {k: (int(v) if v.isdigit() else v) for k, v in COUNTERS_RX.findall(text)}
                        m = re.search(r'\bexit=(\d+)', text)
                        if m:
                            c['exit'] = int(m.group(1))
                        c['_line'] = text.strip().splitlines()[0][:400] if text.strip() else ''
                        return c
            return {}
        return self._memo('counters', go)

    @property
    def exit_code(self):
        def go():
            for base in (self.game, self.root):
                p = Path(base) / 'exit.txt'
                if p.is_file():
                    t = p.read_text().strip()
                    return int(t) if t.lstrip('-').isdigit() else None
            return self.counters.get('exit')
        return self._memo('exit', go)

    @property
    def kernel_text(self):
        for base in (self.game, self.root):
            p = Path(base) / 'kernel.txt'
            if p.is_file():
                return p.read_text(errors='replace')
        return None

    @property
    def present(self):
        """[(frame, return_s, interval_ms)] from present.csv (the interval 0 of the first row left out)."""
        def go():
            p = first_existing(self.game, ('present.csv', 'present.csv.gz')) or first_existing(self.root, ('present.csv',))
            if p is None:
                return []
            rows = []
            opener = gzip.open if p.suffix == '.gz' else open
            try:
                with opener(p, 'rt', errors='replace') as f:
                    rd = csv.reader(f)
                    for r in rd:
                        if len(r) < 3 or not r[0].isdigit():
                            continue
                        iv = int(r[2])
                        if iv > 0:
                            rows.append((int(r[0]), int(r[1]) / 1e9, iv / 1e6))
            except (OSError, ValueError):
                pass
            return rows
        return self._memo('present', go)

    @property
    def shots(self):
        """[(present, path)] of the pictures, in order."""
        def go():
            out = []
            for d in (self.game / 'shots', self.root / 'auto', self.root / 'shots'):   # (a co-op side keeps the periodic ones in auto/, named ones in shots/)
                if d.is_dir():
                    for p in sorted(d.glob('vk_*.png')):
                        m = re.search(r'vk_(\d+)', p.stem)
                        if m:
                            out.append((int(m.group(1)), p))
                    if out:
                        break
            return out
        return self._memo('shots', go)

    @property
    def bursts(self):
        """[(name, why, [(present, path)])]: the runs of consecutive pictures the hunt's watcher took through the bridge
        (burst/<n>/vk_<present>.png, burst/<n>/burst.json says why), in order."""
        def go():
            out = []
            for base in (self.game, self.root):
                d = base / 'burst'
                if not d.is_dir():
                    continue
                for sub in sorted(p for p in d.iterdir() if p.is_dir()):
                    pics = sorted((int(m.group(1)), p) for p in sub.glob('vk_*.png') for m in [re.search(r'vk_(\d+)', p.stem)] if m)
                    if not pics:
                        continue
                    why = ''
                    try:
                        why = str(json.loads((sub / 'burst.json').read_text()).get('why') or '')
                    except (OSError, ValueError):
                        pass
                    out.append((sub.name, why, pics))
                if out:
                    break
            return out
        return self._memo('bursts', go)

    @property
    def pressure(self):
        """[{t, cpu, io, iof, mem, memf, load1}] the hunt's recorder left for this session (psi.jsonl in the session folder or the one above a
        co-op side's folder): the kernel's cumulative stall times in microseconds (cpu some, io some and full, memory some and full) against
        the monotonic clock the presents and samples use. Empty when nothing recorded it."""
        def go():
            for base in (self.root, self.root.parent):
                p = base / 'psi.jsonl'
                if p.is_file():
                    rows = [r for r in read_jsonl(p) if isinstance(r, dict) and 't' in r]
                    rows.sort(key=lambda r: r['t'])
                    return rows
            return []
        return self._memo('pressure', go)

    def wall_of(self, t):
        """Unix time of the sample-clock time t, from the co-op journal's rows (they carry both `w` and the game's `t`), else None."""
        st = [r for r in self.states if r.get('w') is not None]
        if not st:
            return None
        r = min(st, key=lambda r: abs(r['t'] - t))
        return r['w'] + (t - r['t'])

    def t_of_wall(self, w):
        """The sample-clock time of Unix time w (the inverse of wall_of), else None."""
        st = [r for r in self.states if r.get('w') is not None]
        if not st:
            return None
        r = min(st, key=lambda r: abs(r['w'] - w))
        return r['t'] + (w - r['w'])

    def end_w(self):
        """Unix time of the last state sample (co-op journals only), else None."""
        st = [r for r in self.states if r.get('w') is not None]
        return st[-1]['w'] if st else None

    def line_wall(self, index):
        """Unix time of log line `index` from log-times.jsonl ({w, off}: the byte offset the log had reached at that moment), else None."""
        def go():
            rows = [r for r in read_jsonl(self.root / 'log-times.jsonl') if 'w' in r and 'off' in r]
            rows.sort(key=lambda r: r['off'])
            return rows
        rows = self._memo('log-times', go)
        if not rows or index is None:
            return None
        off = sum(len(ln.encode('utf-8', 'replace')) + 1 for ln in self.log[:index])
        nxt = next((r for r in rows if r['off'] >= off), None)
        return nxt['w'] if nxt else None

    @property
    def gameplay(self):
        """(t, frame) where control began: the `gameplay` event's frame matched to a sample, else the first sample."""
        def go():
            st = self.states
            if not st:
                return None
            for e in self.events:
                if e.get('ev') == 'gameplay' and e.get('frame') is not None:
                    row = next((r for r in st if r['frame'] >= e['frame']), st[0])
                    return row['t'], row['frame']
            return st[0]['t'], st[0]['frame']
        return self._memo('gameplay', go)

    @property
    def done(self):
        return any(e.get('ev') == 'done' for e in self.events)

    def clock_offset(self):
        """The sample clock minus the pilot's own game-seconds clock (out.jsonl `t`), from state events and samples that share a present."""
        def go():
            st = self.states
            by_frame = {r['frame']: r['t'] for r in st}
            diffs = []
            for e in self.events:
                if e.get('ev') not in ('state', 'gameplay') or e.get('t') is None or e.get('frame') is None:
                    continue
                if e['frame'] in by_frame:
                    diffs.append(by_frame[e['frame']] - e['t'])
                elif st:   # a co-op runner's own subscription samples at other presents than the pilot's: the nearest sample within 6 presents
                    row = self.state_at_frame(e['frame'])
                    if abs(row['frame'] - e['frame']) <= 6:
                        diffs.append(row['t'] - e['t'] - (row['frame'] - e['frame']) / 60.0)
            if not diffs:
                return None
            diffs.sort()
            return diffs[len(diffs) // 2]
        return self._memo('offset', go)

    def end_t(self):
        """The sample-clock time of the pilot's `end` step (the game is being stopped from then on), else None."""
        for t, e in self.step_times():
            if (e.get('src') or '').split(' ', 1)[0] == 'end':
                return t
        return None

    def step_times(self):
        """[(sample-clock t at the step's end, step event)]"""
        off = self.clock_offset()
        if off is None:
            return []
        return [(e['t'] + off, e) for e in self.steps if e.get('t') is not None]

    def state_at(self, t):
        st = self.states
        if not st:
            return None
        lo, hi = 0, len(st) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if st[mid]['t'] < t:
                lo = mid + 1
            else:
                hi = mid
        if lo and abs(st[lo - 1]['t'] - t) < abs(st[lo]['t'] - t):
            lo -= 1
        return st[lo]

    def state_at_frame(self, frame):
        st = self.states
        return min(st, key=lambda r: abs(r['frame'] - frame)) if st else None

    def game_s(self, t):
        g = self.gameplay
        return round(t - g[0], 2) if g and t is not None else None

    def at(self, t, **kw):
        """Where and what at sample-clock time t (map, pos, frame, game seconds) for a finding's fields."""
        s = self.state_at(t) if t is not None else None
        d = {'t': round(t, 3) if t is not None else None, 'game_s': self.game_s(t)}
        if s:
            d.update(frame=s['frame'], map=s.get('map') or s.get('area'), pos=s.get('pos'))
        d.update(kw)
        return d


def load_side(path, name=None, game=None, pilot=None):
    """A Side from a folder. Layouts: a hunt session (<s>/pilot, <s>/game), a co-op session side (<side>/state.jsonl, log.txt,
    present.csv, pilot/), a pilot run folder (live/, run.log, hs-run-summary.txt)."""
    root = Path(path)
    if game is None and (root / 'game').is_dir():
        game = root / 'game'
    if pilot is None and (root / 'pilot').is_dir():
        pilot = root / 'pilot'
    if game is None:
        game = companion_game(root)
    return Side(root, name or root.name, game=game, pilot=pilot)


def companion_game(root):
    """The game's own run folder (present.csv, the log, shots) of a pilot run folder from another lane, when its summary.json names the copy and the
    run and that folder still exists; else None (the side then reads what the pilot's folder itself has: its copied log and hs-run summary)."""
    try:
        sm = json.loads((Path(root) / 'summary.json').read_text())
        g = Path(sm['copy']) / 'runs' / sm['run']
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return g if g.is_dir() and not (Path(root) / 'present.csv').is_file() else None


def find_sides(path):
    """{name: Side}: a co-op session folder has side folders (side.json), a hunt session or a run folder is one side `solo`."""
    root = Path(path)
    subs = sorted(p for p in root.iterdir() if p.is_dir() and (p / 'side.json').is_file()) if root.is_dir() else []
    if subs:
        return {p.name: load_side(p) for p in subs}
    return {'solo': load_side(root, 'solo')}


# ====================================================================== detectors

def detect_crash(side, cfg):
    res = Result('crash')
    c = side.counters
    code = side.exit_code
    if not c and code is None and not side.log:
        return res.unknown('no summary counters, no exit code and no log')
    res.looked = 1
    for k in ('fatal', 'crash', 'devlost'):
        if isinstance(c.get(k), int) and c[k] > 0:
            line = next((ln for ln in side.log if HARD.search(ln)), '')
            res.add(Finding('crash', k, 'error', side.name, f'{k} counter {c[k]} in the run summary' + (f': {line.strip()[:160]}' if line else ''),
                            evidence={'counter': k, 'value': c[k], 'line': line.strip()[:300], 'summary': c.get('_line')},
                            key=make_key('crash', k, shape(line) if line else k)))
    for k in ('nvrm', 'kernel'):
        if isinstance(c.get(k), int) and c[k] > 0:
            kt = side.kernel_text or ''
            res.add(Finding('crash', 'driver', 'error', side.name, f'{k} counter {c[k]}: driver or kernel lines in the journal',
                            evidence={'counter': k, 'value': c[k], 'kernel_head': kt[:600]},
                            key=make_key('crash', 'driver', k)))
    if isinstance(c.get('nocore'), int) and c['nocore'] > 0:
        line = next((ln for ln in side.log if 'ran without a core' in ln), '')
        res.add(Finding('crash', 'nocore', 'warning' if c['nocore'] >= cfg.nocore_warn else 'info', side.name, f'a vcore thread ran without a core {c["nocore"]} times',
                        evidence={'value': c['nocore'], 'line': line.strip()[:300]}, key=make_key('crash', 'nocore', 'vcores')))
    if code is not None and code not in cfg.expected_exit:
        sig = {134: 'SIGABRT', 139: 'SIGSEGV', 137: 'SIGKILL', 136: 'SIGFPE', 132: 'SIGILL', 135: 'SIGBUS'}.get(code, f'exit {code}')
        line = next((ln for ln in side.log if HARD.search(ln)), '')
        stopped = any(e.get('ev') == 'step' and str(e.get('src', '')).strip() == 'end' and e.get('result') == 'done' for e in side.steps)   # the pilot's end step was done: our stop began
        oom = bool(re.search(r'(?i)out of memory|oom-kill|killed process', side.kernel_text or ''))
        if code == 137 and stopped and not oom:   # the stop's SIGTERM did not end the game in the grace and the harness killed it: slow to stop, not a crash
            res.add(Finding('crash', 'slow-stop', 'warning', side.name, 'the game did not exit within the stop\'s grace after the pilot\'s end step and was killed (SIGKILL, exit 137)',
                            evidence={'exit': code, 'signal': sig}, key=make_key('crash', 'slow-stop', code)))
        else:
            res.add(Finding('crash', 'exit', 'error', side.name, f'the game ended with {sig} (exit {code}), not at the wall or by our stop',
                            evidence={'exit': code, 'signal': sig, 'line': line.strip()[:300]}, key=make_key('crash', 'exit', code)))
    if not any(f.sub in ('fatal', 'crash') for f in res.findings):
        hard = [ln for ln in side.log if 'FATAL' in ln or 'CRASH:' in ln]
        if hard:
            res.add(Finding('crash', 'fatal-line', 'error', side.name, f'{len(hard)} FATAL / CRASH: line(s) in the log: {hard[0].strip()[:140]}',
                            evidence={'lines': [h.strip()[:300] for h in hard[:5]]}, key=make_key('crash', 'fatal-line', shape(hard[0]))))
    return res


def detect_hang(side, cfg):
    res = Result('hang')
    st = side.states
    if len(st) < 2:
        return res.unknown('fewer than two state samples')
    res.looked = len(st)
    for a, b in zip(st, st[1:]):
        gap = b['t'] - a['t']
        if gap >= cfg.hang_s:
            res.add(Finding('hang', 'resumed', 'error', side.name, f'no state sample for {gap:.1f} s (frames {a["frame"]} to {b["frame"]}), then the game went on',
                            evidence={'gap_s': round(gap, 1), 'frame_from': a['frame'], 'frame_to': b['frame']},
                            key=place_key('hang', 'resumed', a.get('map'), a.get('pos'), 16.0), **side.at(a['t'])))
        elif gap >= cfg.hang_s / 2 and b['frame'] == a['frame']:
            res.add(Finding('hang', 'frame-frozen', 'error', side.name, f'the frame counter stood at {a["frame"]} for {gap:.1f} s while samples came',
                            evidence={'gap_s': round(gap, 1), 'frame': a['frame']},
                            key=place_key('hang', 'frame-frozen', a.get('map'), a.get('pos'), 16.0), **side.at(a['t'])))
    last = st[-1]
    pres = side.present
    if pres:
        gap = pres[-1][1] - last['t']
        if gap >= cfg.hang_s:
            res.add(Finding('hang', 'state-stream-stopped', 'error', side.name,
                            f'the presents went on {gap:.0f} s after the last state sample (frame {last["frame"]}): the sample stream died',
                            evidence={'gap_s': round(gap, 1), 'last_sample_frame': last['frame'], 'last_present': pres[-1][0]},
                            key=place_key('hang', 'state-stream-stopped', last.get('map'), last.get('pos'), 16.0), **side.at(last['t'])))
    if side.events and not side.done and side.exit_code == 124:
        # a run that reaches its wall without `done` is the budget doing its job (a chapter's wall is by design): explained, unless the game had
        # stopped presenting (the samples ended long before the last present: the `state-stream-stopped` finding above says that too)
        pres = side.present
        stopped = bool(pres) and pres[-1][1] - last['t'] > cfg.hang_s
        why = None if stopped else 'the run reached its wall (the budget), the game was still presenting and sampling at the end; input that changes nothing is the soft-lock detector\'s'
        res.add(Finding('hang', 'no-end', 'info' if why else 'warning', side.name,
                        'the run ended on its wall and the pilot never wrote `done`' + (f' (explained: {why})' if why else ' (the samples stopped long before the last present: the game stopped answering)'),
                        evidence={'exit': 124, 'last_sample_t': round(last['t'], 2), **({'explained': why} if why else {})},
                        key=place_key('hang', 'no-end', last.get('map'), last.get('pos'), 16.0), **side.at(last['t'])))
    return res


def in_scene(st, i, t0, t1, grace):
    """Whether the sample window [t0 - grace, t1 + grace] holds a load, an event or a map change."""
    for r in st[max(0, i - 80):i + 80]:
        if t0 - grace <= r['t'] <= t1 + grace and (r.get('loading') or r.get('event') or (r.get('music') or '').startswith('Dm_')):
            return True
    return False


PRESSURE_KEYS = (('cpu', 'cpu'), ('io', 'io'), ('iof', 'io (all waiting)'), ('mem', 'memory'), ('memf', 'memory (all waiting)'))


def machine_pressure(rows, t0, t1, margin=1.0):
    """The share of time (0..1) the kernel says tasks were stalled, from the sample just before t0 - margin to the one just after t1 + margin:
    {cpu, io, iof, mem, memf, 'seconds'} from the recorder's cumulative microsecond counters, or None when no two samples span the window
    (nothing recorded it, or the recorder was not running then)."""
    if not rows or len(rows) < 2:
        return None
    lo, hi = t0 - margin, t1 + margin
    before = [r for r in rows if r['t'] <= lo]
    after = [r for r in rows if r['t'] >= hi]
    a = before[-1] if before else None
    b = after[0] if after else None
    if a is None or b is None or b['t'] <= a['t'] or b['t'] - a['t'] > (hi - lo) + 4.0:
        return None
    dt = (b['t'] - a['t']) * 1e6
    out = {'seconds': round(b['t'] - a['t'], 2)}
    for k, _ in PRESSURE_KEYS:
        if k in a and k in b:
            out[k] = round(max(0.0, min(1.0, (b[k] - a[k]) / dt)), 3)
    return out


def machine_short(pr, cfg):
    """What the machine was short of in a pressure reading (text), or None: cpu some at pressure_cpu, io full at pressure_io_full, memory full at pressure_mem_full."""
    got = []
    if pr.get('cpu', 0) >= cfg.pressure_cpu:
        got.append(f'CPU (tasks waited {pr["cpu"] * 100:.0f}% of the time)')
    if pr.get('iof', 0) >= cfg.pressure_io_full:
        got.append(f'the disk (all tasks waited {pr["iof"] * 100:.0f}%)')
    if pr.get('memf', 0) >= cfg.pressure_mem_full:
        got.append(f'memory (all tasks waited {pr["memf"] * 100:.0f}%)')
    return ' and '.join(got) or None


def detect_stall(side, cfg):
    res = Result('stall')
    pres, st = side.present, side.states
    if not pres:
        # the samples' own gaps (a sample every 6 presents: 0.1 s at 60) are a thin stand-in for present.csv
        if len(st) < 2:
            return res.unknown('no present trace and fewer than two samples')
        rows = [(a['frame'], b['t'], max((b['t'] - a['t']) * 1000.0 / (b['frame'] - a['frame']), (b['t'] - a['t']) * 1000.0 - (b['frame'] - a['frame'] - 1) * 16.7))
                for a, b in zip(st, st[1:]) if b['frame'] > a['frame']]   # (the longest one present can have been, the others at 60 fps)
        basis = 'samples'
    else:
        rows, basis = pres, 'present'
    res.looked = len(rows)
    g0 = side.gameplay[0] if side.gameplay else None
    end_t = side.end_t()
    groups = []
    for fr, ts, ms in rows:
        if ms < cfg.stall_warn_ms:
            continue
        if groups and (ts - ms / 1000.0) - groups[-1]['t_end'] <= cfg.stall_group_s:   # (this gap's start against the last one's end: a short hitch just before a long stall is one stall)
            g = groups[-1]
            g['n'] += 1
            g['total'] += ms
            g['max'] = max(g['max'], ms)
            g['t_end'] = ts
        else:
            groups.append({'t': ts - ms / 1000.0, 't_end': ts, 'frame': fr, 'n': 1, 'total': ms, 'max': ms})
    for g in groups:
        s = side.state_at(g['t'])
        i = st.index(s) if s in st else 0
        explained = None
        if end_t is not None and g['t'] >= end_t - 1.0:
            explained = 'the game was being stopped (the pilot\'s end step)'
        elif g0 is not None and g['t'] < g0 + cfg.warmup_s:
            explained = 'the first seconds of play (programs being prepared)'
        elif st and in_scene(st, i, g['t'], g['t_end'], cfg.load_grace_s):
            explained = 'a load, a scene or an event'
        pr = machine_pressure(side.pressure, g['t'], g['t_end'], cfg.pressure_margin_s)
        if not explained and pr:
            why = machine_short(pr, cfg)
            if why:
                explained = f'the machine was short of {why}'
        sev = 'info' if explained else ('error' if g['max'] >= cfg.stall_error_ms else 'warning')
        text = f'{g["n"]} slow present(s), the worst {g["max"]:.0f} ms, {g["total"] / 1000:.1f} s in all' + (f' (explained: {explained})' if explained else '')
        res.add(Finding('stall', 'explained' if explained else ('stall' if sev == 'error' else 'hitch'), sev, side.name, text,
                        evidence={'basis': basis, 'n': g['n'], 'max_ms': round(g['max']), 'total_ms': round(g['total']), 'explained': explained, 'present': g['frame'],
                                  't_end': round(g['t_end'], 3), 'pressure': pr},
                        key=place_key('stall', 'stall' if sev == 'error' else 'hitch', (s or {}).get('map'), (s or {}).get('pos'), 16.0),
                        **side.at(g['t'])))
    return res


def signature(r, cfg):
    return (r.get('map') or r.get('area'), r.get('life'), r.get('rupees'), r.get('event'), r.get('loading'), r.get('prompt'), r.get('music'),
            tuple(sorted((k, v) for k, v in (r.get('flags') or {}).items())), tuple(sorted((r.get('changed') or {}))))


def moved(a, b):
    if not a or not b:
        return 0.0
    return math.hypot(a[0] - b[0], a[2] - b[2])


def detect_softlock(side, cfg):
    res = Result('softlock')
    st = side.states
    sts = side.step_times()
    if len(st) < 2:
        return res.unknown('fewer than two state samples')
    if not sts:
        return res.unknown('no step events with a clock: nothing says inputs went in')
    res.looked = len(st)
    verbs = [(t, e) for t, e in sts if (e.get('src') or '').split(' ', 1)[0] in INPUT_VERBS and (e.get('src') or '').split(' ', 1)[0] not in INPUT_NOT]
    anchor = st[0]
    anchor_sig = signature(anchor, cfg)
    t_anchor = anchor['t']
    reported = False
    for r in st[1:]:
        sig = signature(r, cfg)
        if sig != anchor_sig or moved(anchor.get('pos'), r.get('pos')) >= cfg.softlock_move_m:
            anchor, anchor_sig, t_anchor, reported = r, sig, r['t'], False
            continue
        held = r['t'] - t_anchor
        scene = (r.get('music') or '').startswith('Dm_')
        limit = cfg.softlock_s * (cfg.softlock_scene_factor if scene else 1.0)
        if held >= limit and not reported:
            n = [e for t, e in verbs if t_anchor <= t <= r['t']]
            if len(n) >= cfg.softlock_inputs:
                text_box = r.get('event') == 1 and not scene
                sub = 'scene-held' if scene else ('text-held' if text_box else 'still')
                last = n[-1].get('src', '')
                res.add(Finding('softlock', sub, 'error', side.name,
                                f'{len(n)} input steps in {held:.0f} s and nothing changed ({sub}); the last: {last[:80]}',
                                evidence={'held_s': round(held, 1), 'inputs': len(n), 'last_steps': [(e.get('src') or '')[:100] + ' -> ' + str(e.get('result')) for e in n[-4:]],
                                          'signature': {'event': r.get('event'), 'loading': r.get('loading'), 'prompt': r.get('prompt'), 'music': r.get('music')}},
                                key=place_key('softlock', sub, r.get('map'), r.get('pos'), 8.0), **side.at(r['t'])))
                reported = True
    return res


class Bounds:
    """Per map, the box of its walkable data: {"maps": {name: {"x": [lo, hi], "y": [lo, hi], "z": [lo, hi]}}}. Built from the private world
    model by `bughunt.py bounds`; the file is private, the code names no map."""

    def __init__(self, maps):
        self.maps = maps

    @classmethod
    def load(cls, path):
        return cls(json.loads(Path(path).read_text())['maps'])

    def check(self, mp, pos, cfg):
        """None, or (subtype, text) for a position on a map."""
        if not mp:
            return None
        b = self.maps.get(mp)
        if b is None:
            return 'unknown-map', f'the map {mp} is in no known area'
        x, y, z = pos
        if y < b['y'][0] - cfg.oob_floor_m:
            return 'below-floor', f'y {y:.1f} is {b["y"][0] - y:.1f} m below the lowest walkable ground of {mp} ({b["y"][0]:.1f})'
        if y > b['y'][1] + cfg.oob_ceiling_m:
            return 'above-ceiling', f'y {y:.1f} is {y - b["y"][1]:.1f} m above the highest walkable ground of {mp} ({b["y"][1]:.1f})'
        m = cfg.oob_margin_m
        if x < b['x'][0] - m or x > b['x'][1] + m or z < b['z'][0] - m or z > b['z'][1] + m:
            return 'outside-box', f'({x:.1f}, {z:.1f}) is outside the box of {mp} by more than {m:.0f} m'
        return None


def detect_oob(side, cfg, bounds=None):
    res = Result('oob')
    if bounds is None:
        return res.unknown('no bounds file (the private world model builds one: bughunt.py bounds)')
    st = side.states
    if not st:
        return res.unknown('no state samples')
    run, seen = [], set()
    for r in st:
        if r.get('loading') or r.get('event') or not r.get('pos'):
            run = []
            continue
        res.looked += 1
        bad = bounds.check(r.get('map') or r.get('area'), r['pos'], cfg)
        if not bad:
            run = []
            continue
        if run and run[-1][0] == bad[0]:
            run.append((bad[0], r, bad[1]))
        else:
            run = [(bad[0], r, bad[1])]
        if len(run) >= cfg.oob_samples and (bad[0], r.get('map')) not in seen:
            seen.add((bad[0], r.get('map')))
            first = run[0][1]
            res.add(Finding('oob', bad[0], 'error', side.name, bad[1] + f' for {len(run)} samples ({r["t"] - first["t"]:.1f} s)',
                            evidence={'samples': len(run), 'seconds': round(r['t'] - first['t'], 2), 'pos': r['pos']},
                            key=place_key('oob', bad[0], first.get('map'), first.get('pos'), 16.0), **side.at(first['t'])))
    return res


# ---- pictures

def thumb(path, w=64, h=36):
    """(w, h, rgb bytes) of a picture, small: ImageMagick when installed, else vision.py's stdlib reader."""
    path = Path(path)
    if shutil.which('magick'):
        try:
            r = subprocess.run(['magick', str(path), '-resize', f'{w}x{h}!', '-depth', '8', 'rgb:-'], capture_output=True, timeout=30, check=True)
            if len(r.stdout) == w * h * 3:
                return w, h, r.stdout
        except (OSError, subprocess.SubprocessError):
            pass
    import vision
    iw, ih, rgb = vision.read_png(path.read_bytes())
    tw, th, small = vision.downscale_rgb(iw, ih, rgb, w, h)
    return tw, th, small


def luma(rgb):
    n = len(rgb) // 3
    if not n:
        return 0.0
    return sum(0.299 * rgb[i] + 0.587 * rgb[i + 1] + 0.114 * rgb[i + 2] for i in range(0, n * 3, 3)) / n


def mean_diff(a, b):
    n = min(len(a), len(b))
    return sum(abs(a[i] - b[i]) for i in range(n)) / n if n else 0.0


def file_hash(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


ANOMALY_QUESTIONS = [
    ('blank', 'Is the picture blank: entirely one colour, entirely black or white, or an empty frame with no scene (a fade or a loading screen does not count)?'),
    ('missing_textures', 'Do surfaces look wrong for a finished game: untextured (flat white, grey or magenta), checkerboard placeholder, '
                         'missing walls or floor showing the empty background, or large holes in the world?'),
    ('stretched_textures', 'Are textures smeared or stretched in long streaks across surfaces, or polygons stretched far out of shape?'),
    ('body_wrong', 'Is a character (Link or another player) drawn wrong: stretched, twisted, missing limbs, doubled, inside the ground, '
                   'frozen in a strange pose, or floating? If no character is visible, answer low.'),
    ('void', 'Is the hero over empty space or an endless void, outside of any room or landscape (sky or black all around him, no ground)?'),
    ('corrupt', 'Does the picture show graphical corruption: noise, tearing, coloured blocks, flashing artefacts, or a broken heads-up display?'),
]
ANOMALY_DEVELOPER = ('You look at ONE picture from a 3D action-adventure video game that an automatic test pilot is playing, and answer '
                     'fixed yes/no questions about visible faults. The picture is the game\'s own render; a heads-up display with hearts and '
                     'buttons may be drawn over it. A normal, finished-looking scene is the usual case: answer a low probability unless the '
                     'fault is clearly visible.')


def anomaly_body(model, data_url):
    return {'model': model,
            'input': [{'role': 'developer', 'content': ANOMALY_DEVELOPER},
                      {'role': 'user', 'content': [{'type': 'input_text', 'text': 'The picture.'},
                                                   {'type': 'input_image', 'image_url': data_url}]}],
            'questions': [{'type': 'predicate', 'name': n, 'instructions': q} for n, q in ANOMALY_QUESTIONS],
            'prompt_cache_key': 'ls-pilot-anomaly'}


def parse_anomaly(ans):
    got = {a.get('name'): a for a in (ans or {}).get('answers', []) if isinstance(a, dict)}
    out = {}
    for n, _ in ANOMALY_QUESTIONS:
        a = got.get(n) or {}
        try:
            out[n] = max(0.0, min(1.0, float(a.get('probability'))))
        except (TypeError, ValueError):
            out[n] = None
    return out


class ModelAsker:
    """The model's fixed anomaly questions for a picture file: ask(path) -> {question: probability, ...}. client is openai_api.Client
    (so the caps and the ledger apply); kept apart so the detectors and their tests need no network."""

    def __init__(self, client, model=None, width=960):
        import openai_api
        self.client, self.width = client, width
        self.model = model or openai_api.VISION_MODEL
        self.cost = 0.0
        self.calls = 0

    def __call__(self, path):
        import base64
        import vision
        with tempfile.TemporaryDirectory(prefix='bughunt-look-') as t:
            p, w, h, mime = vision.downscale_file(Path(path), Path(t) / 'f', self.width)
            url = f'data:{mime};base64,' + base64.b64encode(p.read_bytes()).decode('ascii')
        body = anomaly_body(self.model, url)
        est = (len(json.dumps({k: v for k, v in body.items() if k != 'input'})) / 3.0 + vision.image_tokens(w, h)) * 0.10 / 1e6
        ans, ms, crow = self.client.post('/decisions', body, api='decisions', model=self.model, kind='vision', estimate=est, timeout=60.0)
        self.calls += 1
        self.cost += float((crow or {}).get('cost_usd') or 0.0)
        return parse_anomaly(ans)


def pick_looks(side, cfg, interesting=()):
    """Which pictures the model sees: the first after control began, the ones nearest `interesting` present numbers (the other
    findings), and an even spread, at most vision_max."""
    g = side.gameplay
    shots = [s for s in side.shots if not g or s[0] >= g[1]]   # (the pictures from before control began are the boot and the load: nothing to judge)
    if not shots:
        return []
    chosen = []
    if g:
        chosen.append(shots[0])
    for fr in interesting:
        chosen.append(min(shots, key=lambda s: abs(s[0] - fr)))
    n, k = len(shots), cfg.vision_max
    spread = list(shots) if n <= k else [shots[round(i * (n - 1) / max(1, k - 1))] for i in range(k)]
    seen, out = set(), []
    for s in chosen + spread:
        if s[0] not in seen and len(out) < k:
            seen.add(s[0])
            out.append(s)
    return sorted(out)


def detect_visual(side, cfg, ask=None, interesting=()):
    res = Result('visual')
    shots = side.shots
    bursts = side.bursts
    if not shots and not bursts:
        return res.unknown('no pictures')
    st = side.states
    res.looked = len(shots)
    thumbs = {}

    def th(i):
        if i not in thumbs:
            try:
                thumbs[i] = thumb(shots[i][1])
            except Exception:   # noqa: BLE001  a picture that cannot be read is a finding of its own below, never a crash
                thumbs[i] = None
        return thumbs[i]

    def state_for(present):
        if not st:
            return None
        return min(st, key=lambda r: abs(r['frame'] - present))

    black_run = []
    hashes = []
    for i, (fr, p) in enumerate(shots):
        s = state_for(fr)
        t = th(i)
        if t is None:
            res.add(Finding('visual', 'unreadable', 'warning', side.name, f'picture {p.name} cannot be read as a PNG',
                            evidence={'picture': p.name}, key=make_key('visual', 'unreadable', side.name), frame=fr))
            continue
        playing = bool(s) and not s.get('loading') and not s.get('event') and (s.get('music') or '').startswith('BGM') and not recently_changed(side, s['t'], cfg)
        lm = luma(t[2])
        if lm < cfg.black_luma and playing:
            black_run.append((fr, p, lm, s))
            if len(black_run) == cfg.black_pictures:
                s0 = black_run[0][3]
                res.add(Finding('visual', 'black', 'error', side.name, f'{len(black_run)} black pictures in a row (mean luma {lm:.1f}) while the state says play',
                                evidence={'pictures': [b[1].name for b in black_run], 'luma': round(lm, 1), 'music': s0.get('music')},
                                key=place_key('visual', 'black', s0.get('map'), s0.get('pos'), 16.0), frame=fr,
                                **{k: v for k, v in side.at(s0['t']).items() if k != 'frame'}))
        else:
            black_run = []
        hashes.append((fr, file_hash(p), s))
    for (f0, h0, s0), (f1, h1, s1) in zip(hashes, hashes[1:]):
        if h0 == h1 and f1 - f0 >= cfg.frozen_presents and s0 and s1 and moved(s0.get('pos'), s1.get('pos')) >= cfg.frozen_move_m \
                and not (s0.get('loading') or s1.get('loading')):
            res.add(Finding('visual', 'frozen', 'error', side.name,
                            f'the same picture at presents {f0} and {f1} while Link moved {moved(s0.get("pos"), s1.get("pos")):.1f} m',
                            evidence={'presents': [f0, f1], 'moved_m': round(moved(s0.get('pos'), s1.get('pos')), 2)},
                            key=place_key('visual', 'frozen', s1.get('map'), s1.get('pos'), 16.0), **side.at(s1['t'])))
    path_thumbs = {}

    def th_path(p):
        if p not in path_thumbs:
            try:
                path_thumbs[p] = thumb(p)
            except Exception:   # noqa: BLE001
                path_thumbs[p] = None
        return path_thumbs[p]

    flickers = flicker_scan(side, cfg, th_path)
    res.looked += sum(len(b[2]) for b in bursts)
    for fl in flickers:
        res.add(fl)
    if ask is not None:
        for fr, p in pick_looks(side, cfg, interesting):
            s = state_for(fr)
            if s and (s.get('loading') or abs(s['frame'] - fr) > 60):
                continue   # a load's picture, or one no sample is near: the model would call a fade blank
            try:
                lm = luma(thumb(p)[2])
            except Exception:   # noqa: BLE001
                lm = 255.0
            if lm < cfg.black_luma * 2:
                continue   # a black or all but black picture is the local check's (the model says `blank` of every fade)
            try:
                ans = ask(p)
            except Exception as e:   # noqa: BLE001  a failed look is recorded, never fatal
                res.add(Finding('visual', 'look-failed', 'info', side.name, f'the model look at {p.name} failed: {type(e).__name__}: {str(e)[:120]}',
                                evidence={'picture': p.name}, key=make_key('visual', 'look-failed', type(e).__name__), frame=fr))
                continue
            for q, v in ans.items():
                if v is not None and v >= cfg.vision_p:
                    res.add(Finding('visual', q, 'warning', side.name, f'the model says {q.replace("_", " ")} at {v:.2f} in {p.name}',
                                    evidence={'picture': p.name, 'p': ans, 'present': fr},
                                    key=place_key('visual', q, (s or {}).get('map'), (s or {}).get('pos'), 24.0),
                                    **(side.at(s['t']) if s else {'frame': fr})))
    return res


def still_span(side, f0, f1, cfg):
    """Whether Link, the camera and the scene's state stood still over the presents f0..f1 (a sample either side counts): True, False, or
    None when no sample is near (then nothing can be said and the scan does not guess)."""
    st = side.states
    if not st:
        return None
    near = [r for r in st if f0 - 6 <= r['frame'] <= f1 + 6]
    if not near:
        a = side.state_at_frame(f0)
        near = [a] if a and abs(a['frame'] - f0) <= 12 else []
    if not near:
        return None
    if recently_changed(side, near[0]['t'], cfg):
        return False
    first = near[0]
    for r in near:
        if r.get('loading') or moved(first.get('pos'), r.get('pos')) > 0.05 or r.get('camera') != first.get('camera'):
            return False
    return True


def flicker_scan(side, cfg, thumb_of):
    """A B A in consecutive pictures (each at most flicker_gap presents after the one before) while Link and the camera stood still:
    A and B differ by flicker_diff, A and the next A by under flicker_same. Needs consecutive pictures: the bursts the hunt's watcher takes
    (side.bursts; one finding a burst, a warning for one A B A and an error for two or more: a strobe) and any run of the ordinary shots that
    close (a copy started with RX_VK_SHOT_EVERY of a few presents). The every-90-presents shots are too far apart to say anything.
    thumb_of(path) is the small picture."""
    out = []
    runs = [('shots', '', side.shots)] + list(side.bursts)
    for name, why, pics in runs:
        if len(pics) < 3:
            continue
        hits = []
        for i in range(len(pics) - 2):
            (f0, p0), (f1, p1), (f2, p2) = pics[i:i + 3]
            if f1 - f0 > cfg.flicker_gap or f2 - f1 > cfg.flicker_gap:
                continue
            a, b, c = thumb_of(p0), thumb_of(p1), thumb_of(p2)
            if not (a and b and c):
                continue
            if still_span(side, f0, f2, cfg) is not True:
                continue
            d_ab, d_bc, d_ac = mean_diff(a[2], b[2]), mean_diff(b[2], c[2]), mean_diff(a[2], c[2])
            if d_ab >= cfg.flicker_diff and d_bc >= cfg.flicker_diff and d_ac <= cfg.flicker_same:
                hits.append((f0, f1, f2, d_ab, d_bc, d_ac, [p0.name, p1.name, p2.name]))
        if not hits:
            continue
        f0, f1, f2, d_ab, d_bc, d_ac, names = hits[0]
        s = side.state_at_frame(f0) or {}
        out.append(Finding('visual', 'flicker', 'error' if len(hits) >= 2 else 'warning', side.name,
                           f'{"burst " + name + ": " if name != "shots" else ""}pictures at presents {f0}, {f1}, {f2}: the middle one differs by {d_ab:.1f}/{d_bc:.1f}, '
                           f'the outer two by {d_ac:.1f} (A B A) while nothing moved' + (f'; {len(hits)} such triplets in the run' if len(hits) > 1 else ''),
                           evidence={'presents': [f0, f1, f2], 'diffs': [round(d_ab, 2), round(d_bc, 2), round(d_ac, 2)], 'triplets': len(hits),
                                     'burst': name if name != 'shots' else None, 'why': why, 'pictures': names,
                                     'run': [p.name for _, p in pics]},
                           key=place_key('visual', 'flicker', s.get('map'), s.get('pos'), 16.0), frame=f0,
                           **({k: v for k, v in side.at(s['t']).items() if k != 'frame'} if s else {})))
    return out


def recently_changed(side, t, cfg):
    """Whether a load was going on, or the map was another one, at any sample in the cfg.settle_s seconds up to sample-clock time t: the picture
    is then (or may be) the fade-in from black after a placement, a door or a teleport, and says nothing about the game."""
    st = side.states
    if t is None or not st or cfg.settle_s <= 0:
        return False
    cur = side.state_at(t)
    if not cur:
        return False
    here = cur.get('map') or cur.get('area')
    for r in st:
        if r['t'] > t:
            break
        if r['t'] >= t - cfg.settle_s and (r.get('loading') or (r.get('map') or r.get('area')) != here):
            return True
    return False


def is_playing(s):
    """A sample where the game is being played: not loading, no event or scene, the area's own music."""
    return bool(s) and not s.get('loading') and not s.get('event') and (s.get('music') or '').startswith('BGM')


def suspect_picture(side, prev, cur, cfg):
    """Why the live watcher should take a burst of consecutive pictures after the periodic picture `cur`, or None. `prev` is the periodic
    picture before it (or None); each is (present, path, small picture, file hash). The cheap parts of the visual detector, on the newest
    picture: black while the state says play, the same picture as the one before while Link moved, a large change from the one before while
    Link, the camera and the scene stood still (a flash or a flicker that the every-90-presents pictures only sample)."""
    fr, _path, small, h = cur
    s = side.state_at_frame(fr)
    if s and recently_changed(side, s['t'], cfg):
        return None
    if s and abs(s['frame'] - fr) <= 60 and is_playing(s) and small and luma(small[2]) < cfg.black_luma:
        return 'black picture while the state says play'
    if prev is None:
        return None
    f0, _p0, small0, h0 = prev
    s0 = side.state_at_frame(f0)
    if not (s and s0) or abs(s['frame'] - fr) > 60 or abs(s0['frame'] - f0) > 60 or s.get('loading') or s0.get('loading'):
        return None
    if h == h0 and fr - f0 >= cfg.frozen_presents and moved(s0.get('pos'), s.get('pos')) >= cfg.frozen_move_m:
        return f'the same picture as {fr - f0} presents before while Link moved {moved(s0.get("pos"), s.get("pos")):.1f} m'
    if small and small0 and still_span(side, f0, fr, cfg) is True and not s.get('event') and not s0.get('event'):
        d = mean_diff(small0[2], small[2])
        if d >= cfg.burst_diff:
            return f'the picture changed by {d:.1f} in {fr - f0} presents while Link, the camera and the scene stood still'
    return None


def still_now(side, cfg):
    """Whether the newest samples (cfg.burst_probe_still_s seconds of them) are play with Link and the camera standing still: a moment
    when a flicker would show against a motionless picture."""
    st = side.states
    if not st or not is_playing(st[-1]):
        return False
    last = st[-1]
    if recently_changed(side, last['t'], cfg):
        return False
    g = side.gameplay
    if g and last['t'] - g[0] < cfg.burst_probe_after_s:
        return False
    near = [r for r in st if last['t'] - r['t'] <= cfg.burst_probe_still_s]
    if len(near) < 3 or last['t'] - near[0]['t'] < cfg.burst_probe_still_s * 0.8:
        return False
    return all(is_playing(r) and moved(last.get('pos'), r.get('pos')) <= 0.05 and r.get('camera') == last.get('camera') for r in near)


# ---- the log

def build_baseline(paths):
    """{shape: count} of the trouble lines of reference logs: the lines a build says anyway."""
    known = {}
    for p in paths:
        opener = gzip.open if str(p).endswith('.gz') else open
        with opener(p, 'rt', errors='replace') as f:
            for ln in f:
                if trouble(ln):
                    k = shape(ln)
                    known[k] = known.get(k, 0) + 1
    return known


def load_baseline(path):
    if path is None:
        return None
    d = json.loads(Path(path).read_text())
    return d['shapes'] if isinstance(d, dict) and 'shapes' in d else d


def detect_log(side, cfg, baseline=None):
    res = Result('log')
    lines = side.log
    if not lines:
        return res.unknown('no game log')
    if baseline is None:
        return res.unknown('no baseline of a reference build: every trouble line would be new')
    res.looked = len(lines)
    seen = {}
    for idx, ln in enumerate(lines):
        if not trouble(ln):
            continue
        k = shape(ln)
        if k in baseline:
            continue
        if k in seen:
            seen[k][1] += 1
        else:
            seen[k] = [ln.strip(), 1, idx]
    for k, (ln, n, idx) in sorted(seen.items(), key=lambda kv: -kv[1][1])[:cfg.log_max_shapes]:
        hard = bool(HARD.search(ln))
        res.add(Finding('log', 'hard' if hard else 'new-line', 'error' if hard else 'warning', side.name,
                        f'a log line new to the baseline ({n}x): {ln[:150]}', evidence={'line': ln[:400], 'count': n, 'shape': k, 'line_index': idx},
                        key=make_key('log', 'hard' if hard else 'new-line', k)))
    if len(seen) > cfg.log_max_shapes:
        res.add(Finding('log', 'more', 'info', side.name, f'{len(seen) - cfg.log_max_shapes} more new shapes not listed', evidence={'shapes': len(seen)},
                        key=make_key('log', 'more', side.name)))
    return res


def detect_audio(side, cfg):
    res = Result('audio')
    lines = side.log
    if not lines:
        return res.unknown('no game log')
    res.looked = len(lines)
    bad = [ln for ln in lines if AUDIO_BAD.search(ln) and 'unimplemented import' not in ln]
    for ln in bad[:5]:
        res.add(Finding('audio', 'error-line', 'warning', side.name, f'an audio error line: {ln.strip()[:160]}', evidence={'line': ln.strip()[:300]},
                        key=make_key('audio', 'error-line', shape(ln))))
    if not any('audio:' in ln for ln in lines):
        return res if res.findings else res.unknown('the log has no audio lines at all; a muted headless run writes no level, so silence cannot be judged')
    played = any((r.get('music') or '').startswith(('BGM', 'Dm_')) for r in side.states)
    opened = any('audio: renderer opened' in ln for ln in lines)
    if played and not opened:
        res.add(Finding('audio', 'no-renderer', 'error', side.name, 'the state shows music but the log never says `audio: renderer opened`',
                        evidence={'music': next(r['music'] for r in side.states if (r.get('music') or '').startswith(('BGM', 'Dm_')))},
                        key=make_key('audio', 'no-renderer', side.name)))
    return res


# ---- a pair

def detect_desync(sides, cfg):
    """Shared flags (cfg.shared) that two sides disagree on for longer than the grace time after the later one's last change."""
    res = Result('desync')
    names = list(sides)
    if len(names) < 2:
        return res.unknown('fewer than two sides')
    if not cfg.shared:
        return res.unknown('no shared flag names configured')
    series = {n: [(r['t'], r.get('w'), r.get('flags') or {}) for r in s.states] for n, s in sides.items()}
    if any(not v for v in series.values()):
        return res.unknown('a side has no state samples')
    use_w = all(v[0][1] is not None for v in series.values())
    clock = (lambda r: r[1]) if use_w else (lambda r: r[0])
    pts = sorted({clock(r) for v in series.values() for r in v})
    for flag in cfg.shared:
        pos = {n: -1 for n in series}
        run_start, run_vals, run_t = None, None, None
        for t in pts:
            vals = {}
            for n, v in series.items():
                while pos[n] + 1 < len(v) and clock(v[pos[n] + 1]) <= t:
                    pos[n] += 1
                vals[n] = v[pos[n]][2].get(flag) if pos[n] >= 0 else None
            res.looked += 1
            if any(x is None for x in vals.values()) or len(set(vals.values())) == 1:
                run_start, run_vals, run_t = None, None, None
                continue
            if run_vals != vals:
                run_start, run_vals = t, dict(vals)
                run_t = series[names[0]][max(pos[names[0]], 0)][0]
            elif t - run_start >= cfg.desync_grace_s:
                at = sides[names[0]].at(run_t)
                res.add(Finding('desync', 'flag', 'error', 'pair', f'{flag} disagrees for {t - run_start:.0f} s: ' + ', '.join(f'{n}={v}' for n, v in vals.items()),
                                evidence={'flag': flag, 'values': vals, 'seconds': round(t - run_start, 1)},
                                key=make_key('desync', 'flag', flag), **{k: v for k, v in at.items() if k != 'frame'}))
                break
    return res


def detect_give(side, cfg):
    """A counter that rises by more than a rule's per_flag when its flag flips 0 -> 1 once: the shared-chest double give."""
    res = Result('give')
    if not cfg.give_rules:
        return res.unknown('no give rules configured')
    st = side.states
    if len(st) < 2:
        return res.unknown('fewer than two state samples')
    for rule in cfg.give_rules:
        flag, counter, per = rule['flag'], rule['counter'], rule.get('per_flag', 1)
        flips = [i for i in range(1, len(st)) if st[i - 1]['flags'].get(flag) in (0, None) and st[i]['flags'].get(flag) == 1
                 and st[i - 1]['flags'].get(flag) is not None]
        for i in flips:
            t_flip = st[i]['t']
            base = [r for r in st[:i] if r['t'] >= t_flip - cfg.give_lookback_s and r['flags'].get(counter) is not None]
            before = base[0]['flags'][counter] if base else st[i - 1]['flags'].get(counter)   # (the counter as it stood when the opening began)
            if before is None:
                continue
            after_row = [r for r in st[i:] if r['t'] <= t_flip + cfg.give_settle_s and r['flags'].get(counter) is not None]
            if not after_row:
                continue
            after = after_row[-1]['flags'][counter]
            res.looked += 1
            delta = after - before
            if delta > per:
                res.add(Finding('give', 'double', 'error', side.name,
                                f'{rule.get("name", flag)}: {counter} rose {before} -> {after} (+{delta}) around one flip of {flag}; one flip gives {per}',
                                evidence={'rule': rule, 'before': before, 'after': after, 'delta': delta, 'lookback_s': cfg.give_lookback_s, 'settle_s': cfg.give_settle_s},
                                key=make_key('give', 'double', rule.get('name', flag)), **side.at(t_flip)))
    if not res.looked and not res.findings:
        res.unknown('no rule\'s flag flipped with its counter read: nothing to judge')
    return res


# ---- the co-op runner's own detectors (cpdetect), when the runner is there

def coop_runner_dir():
    cands = [os.environ.get('BUGHUNT_COOPPLAY'), HERE.parent.parent / 'coop-play', HERE.parent / 'coop-play']
    for c in cands:
        if c and (Path(c) / 'cpdetect.py').is_file():
            return Path(c)
    return None


def detect_coop_runner(folder, only=('logs', 'bodies', 'net', 'divergence', 'jank', 'faults')):
    """cpdetect's findings over a co-op session folder, as Findings (errors and warnings; info is left out). unknown without the runner. Its
    `frames` detector is left out: it called the game's own shutdown (a 5.7 s and a 6.6 s present gap after the pilot's end step) a stall outside
    any declared stop and failed the hold-1 pair; this module's stall detector reads the same present trace and knows the end step."""
    res = Result('coop')
    d = coop_runner_dir()
    if d is None:
        return res.unknown('the co-op runner (cpdetect.py) is not beside this tree: set BUGHUNT_COOPPLAY')
    if not (Path(folder) / 'session.json').is_file():
        return res.unknown('not a co-op session folder (no session.json)')
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))
    try:
        import cpdetect
        results = cpdetect.run_all(str(folder), only=list(only))
    except Exception as e:   # noqa: BLE001  the runner's detectors raise on odd folders: say so, never stop the hunt
        return res.unknown(f'cpdetect failed: {type(e).__name__}: {str(e)[:160]}')
    for name, rd in results.items():
        if rd.get('status') == 'unknown':
            continue
        res.looked += 1
        for f in rd.get('findings', []):
            if f.get('severity') == 'info':
                continue
            text = f.get('text', '')
            kind = {'divergence': 'desync', 'jank': 'body', 'bodies': 'body', 'frames': 'stall', 'faults': 'crash', 'net': 'net', 'logs': 'log'}.get(name, name)
            fnd = Finding(kind, f'coop-{name}', f['severity'], f.get('side') or 'pair', text, t=f.get('t'),
                          evidence={'detector': name, 'w': f.get('w'), 'epoch': f.get('epoch')}, key=make_key(kind, f'coop-{name}', shape(text)))
            if name == 'faults' and 'core dump(s) listed' in text:   # the runner lists the machine's dumps of the window: only a dump of one of our games is ours
                try:
                    copies = [str(sd.get('build') or '') for sd in (json.loads((Path(folder) / 'case.json').read_text()).get('sides') or {}).values()]
                except (OSError, ValueError, AttributeError):
                    copies = []
                ours, others = split_core_dumps((Path(folder) / 'coredumps.txt').read_text() if (Path(folder) / 'coredumps.txt').is_file() else '', copies)
                if not ours:
                    explain(fnd, f'{len(others)} core dump(s) of other processes on this machine (' + ', '.join(sorted({ln.split()[-2] for ln in others if len(ln.split()) > 1}))[:120] + '), none of the games of this case')
                else:
                    fnd.text = f'{len(ours)} core dump(s) of this case\'s games, first: {ours[0][:160]}'
            res.add(fnd)
    return res


# ---- what a pair's findings are, read across the two games (each rule marks a finding `info` with the reason: nothing is dropped)

PEER_GONE = re.compile(r'(?i)nobody is shown now|hidden \(not heard\)|made again after "?not heard"?|member \d+ (?:is )?gone|left the room')
LOADING_LINE = re.compile(r'(?i)this game stopped being played: a map change or a load')
IDENTITY_EARLY = re.compile(r'\[identity\] sync: \d+ member\(s\)? .*not identified')
NET_PEAK = re.compile(r"sent peak (\d+) bytes/s is over the game's RATE_BYTES limit (\d+)")


def explain(f, reason):
    f.severity = 'info'
    f.text += f' (explained: {reason})'
    f.evidence = dict(f.evidence or {}, explained=reason)


def shutdown_wall(folder):
    """Unix time the co-op runner asked the pilots to end (its `shutdown` phase in timeline.jsonl), else None."""
    try:
        for line in (Path(folder) / 'timeline.jsonl').read_text().splitlines():
            e = json.loads(line)
            if e.get('kind') == 'phase' and e.get('name') == 'shutdown' and e.get('w') is not None:
                return float(e['w'])
    except (OSError, ValueError, TypeError):
        pass
    return None


def split_core_dumps(text, copies):
    """(ours, others): the lines of a `coredumpctl list` text that are dumps of a game of this case (the executable lives in one of `copies`)
    and those of other processes on the machine (the list is machine-wide: other tests dump cores too). The header and `No coredumps` are neither."""
    ours, others = [], []
    for ln in text.splitlines():
        if not ln.strip() or re.match(r'(?i)^\s*(TIME\b|no coredumps found)', ln):
            continue
        (ours if any(c and c in ln for c in copies) else others).append(ln)
    return ours, others


def finding_wall(f, sides):
    """Unix time of a pair finding: the runner's own `w`, else the time of the log line it names."""
    ev = f.evidence or {}
    if ev.get('w') is not None:
        return ev['w']
    s = sides.get(f.side)
    if s is not None and ev.get('line_index') is not None:
        return s.line_wall(ev['line_index'])
    return None


def explain_pair(findings, sides, cfg, folder=None):
    """The pair's own false positives and the one finding two games make together. (1) co-op lines about the other player going away at the
    first game's end (the shutdown); (2) the identity line before the room was accepted; (3) a send peak that touches the rate limit
    (under net_over_factor); (4) a body snap right after a stall of either game; then both games stalling at the same moment become
    one `stall/both` finding (one cause for two games is the machine, the relay or a shared resource, not a bug of one game). Returns the
    new list; the explained ones stay in it as `info`."""
    if len(sides) < 2:
        return findings
    anchors = {}
    try:
        sj = json.loads((Path(folder) / 'session.json').read_text()) if folder else {}
        anchors = sj.get('anchors') or {}
    except (OSError, ValueError):
        pass
    delays = {}   # the case's impairment of each side's link (ms each way): the other player's body runs late on that side by design
    try:
        for sid, sd in (json.loads((Path(folder) / 'case.json').read_text()).get('sides') or {}).items():
            lk = sd.get('link') or {}
            delays[sid] = max(int((lk.get('c2s') or {}).get('delay_ms') or 0), int((lk.get('s2c') or {}).get('delay_ms') or 0))
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    ends = [w for w in (s.end_w() for s in sides.values()) if w is not None]
    stall_ends = []
    for f in findings:
        if f.kind == 'stall' and f.evidence and f.evidence.get('t_end') is not None and f.sub in ('stall', 'hitch', 'explained') \
                and not str(f.evidence.get('explained') or '').startswith(('the first seconds', 'the game was being stopped')):
            s = sides.get(f.side)
            w = s.wall_of(f.evidence['t_end']) if s else None
            if w is not None:
                stall_ends.append(w)
    sd_w = shutdown_wall(folder) if folder else None
    for f in findings:
        if f.severity == 'info':
            continue
        text = f.text
        if sd_w is not None and f.kind in ('stall', 'body', 'log'):   # after the runner asked the pilots to end nobody plays: the games' closing
            sd = sides.get(f.side)
            w = sd.wall_of(f.t) if (f.kind == 'stall' and sd is not None and f.t is not None) else finding_wall(f, sides)
            if w is not None and w >= sd_w:
                explain(f, 'the runner had asked the pilots to end: nobody was playing, the games were closing')
                continue
        slow = max(delays, key=delays.get) if delays else None
        if f.sub == 'coop-jank' and re.match(r'\[(lag|starved)\]', text) and slow is not None and delays[slow] >= cfg.link_delay_explains_ms:
            explain(f, f'the case delays side {slow}\'s link by {delays[slow]} ms each way: the players\' bodies run late on both sides by design')   # (the delay is on the path between the two games)
            continue
        if LOADING_LINE.search(text) or LOADING_LINE.search((f.evidence or {}).get('line', '')):   # the game's own load (a placement, a door): its co-op line, not a fault
            s = sides.get(f.side)
            w = finding_wall(f, sides)
            t = s.t_of_wall(w) if (s is not None and w is not None) else None
            if t is not None and any(r.get('loading') and abs(r['t'] - t) <= cfg.settle_s * 3 for r in s.states):
                explain(f, 'the game itself was loading a map (a placement or a door): its co-op line says it was not being played')
                continue
        if PEER_GONE.search(text) or PEER_GONE.search((f.evidence or {}).get('line', '')):
            w = finding_wall(f, sides)
            if w is not None and ends and w >= min(ends) - cfg.peer_gone_s:
                explain(f, 'the other game was ending: the room losing a player at the shutdown')
                continue
            if w is not None and any(0 <= w - e <= cfg.snap_after_stall_s for e in stall_ends):
                explain(f, 'a game had stalled just before: the other one was not heard for a while')
                continue
        if IDENTITY_EARLY.search(text) and anchors.get('accepted') is not None and f.t is not None and f.t < anchors['accepted']:
            explain(f, 'the room was not accepted yet: nobody is identified at its start')
            continue
        m = NET_PEAK.search(text)
        if m and int(m.group(2)) > 0 and int(m.group(1)) / int(m.group(2)) < cfg.net_over_factor:
            explain(f, f'the send rate touched its limit ({int(m.group(1)) / int(m.group(2)):.2f}x)')
            continue
        if f.sub == 'coop-jank':
            w = finding_wall(f, sides)
            if w is not None and any(0 <= w - e <= cfg.snap_after_stall_s for e in stall_ends):
                explain(f, 'the body snap that follows a stall of a game')
    stalls = sorted((f for f in findings if f.kind == 'stall' and f.sub in ('stall', 'hitch') and f.severity != 'info' and f.side in sides
                     and (f.evidence or {}).get('t_end') is not None), key=lambda f: -(f.evidence.get('max_ms') or 0))   # (the biggest pair up first)
    used, merged = set(), []
    for i, f in enumerate(stalls):
        if i in used:
            continue
        for j, g in enumerate(stalls):
            if j <= i or j in used or g.side == f.side:
                continue
            if f.t <= g.evidence['t_end'] + cfg.stall_group_s and g.t <= f.evidence['t_end'] + cfg.stall_group_s:
                used |= {i, j}
                big = f if f.evidence.get('max_ms', 0) >= g.evidence.get('max_ms', 0) else g
                p1, p2 = sorted((f, g), key=lambda x: x.side)
                merged.append(Finding('stall', 'both', 'error' if 'error' in (f.severity, g.severity) else 'warning', 'pair',
                                      f'both games stalled at the same moment: {p1.side} {p1.evidence["max_ms"]} ms, {p2.side} {p2.evidence["max_ms"]} ms '
                                      f'(one cause for two games: the machine, the relay, a shared resource; a replay says whether it comes again)',
                                      t=min(f.t, g.t), frame=big.frame, game_s=big.game_s, map=big.map, pos=big.pos,
                                      evidence={'sides': {f.side: f.evidence, g.side: g.evidence}},
                                      key=place_key('stall', 'both', big.map, big.pos, 16.0)))
                break
    if used:
        drop = {id(stalls[i]) for i in used}
        findings = [f for f in findings if id(f) not in drop] + merged
    return findings


# ====================================================================== running them all

DETECTORS = ('crash', 'hang', 'stall', 'softlock', 'oob', 'log', 'audio', 'visual')


def analyze_side(side, cfg=None, bounds=None, baseline=None, ask=None, only=None):
    """{name: Result} of every detector over one side (those in `only` if given). Findings carry the side's name."""
    cfg = cfg or Config()
    run = {
        'crash': lambda: detect_crash(side, cfg),
        'hang': lambda: detect_hang(side, cfg),
        'stall': lambda: detect_stall(side, cfg),
        'softlock': lambda: detect_softlock(side, cfg),
        'oob': lambda: detect_oob(side, cfg, bounds),
        'log': lambda: detect_log(side, cfg, baseline),
        'audio': lambda: detect_audio(side, cfg),
        'give': lambda: detect_give(side, cfg),
    }
    out = {}
    for name in [n for n in (only or DETECTORS) if n in run]:
        try:
            out[name] = run[name]()
        except Exception as e:   # noqa: BLE001  a detector that raises is `unknown`, the others still run
            out[name] = Result(name).unknown(f'{type(e).__name__}: {str(e)[:160]}')
    if only is None or 'visual' in only:
        try:
            interesting = [f.frame for r in out.values() for f in r.findings if f.severity != 'info' and f.frame]
            out['visual'] = detect_visual(side, cfg, ask, interesting)
        except Exception as e:   # noqa: BLE001
            out['visual'] = Result('visual').unknown(f'{type(e).__name__}: {str(e)[:160]}')
    if cfg.give_rules and (only is None or 'give' in only) and 'give' not in out:
        out['give'] = detect_give(side, cfg)
    return out


def analyze(path, cfg=None, bounds=None, baseline=None, ask=None, only=None, sides=None):
    """Everything over a folder: a hunt session, a pilot run folder or a co-op session. Returns
    {'findings': [Finding], 'detectors': {side: {name: {...}}, 'pair': {...}}, 'sides': [...]}; each finding keyed and tagged by side."""
    cfg = cfg or Config()
    sides = sides or find_sides(path)
    findings, table = [], {}
    for name, side in sides.items():
        rs = analyze_side(side, cfg, bounds, baseline, ask, only)
        table[name] = {k: v.to_dict() for k, v in rs.items()}
        for v in rs.values():
            findings += v.findings
    if len(sides) >= 2:
        pair = {'desync': detect_desync(sides, cfg), 'coop': detect_coop_runner(path)}
        table['pair'] = {k: v.to_dict() for k, v in pair.items()}
        for v in pair.values():
            findings += v.findings
        findings = explain_pair(findings, sides, cfg, path)
    for f in findings:
        if any(re.search(p, f.text) for p in cfg.artefacts):
            f.status = 'artefact'
    return {'findings': findings, 'detectors': table, 'sides': list(sides)}


def summarize(report):
    lines = []
    for side, rows in report['detectors'].items():
        for name, r in rows.items():
            lines.append(f'{side:5} {name:9} {r["status"]:8} looked {r["looked"]:>7}  findings {r["findings"]:>3}  explained {r["explained"]:>3}' +
                         (f'  ({r["reason"]})' if r['reason'] else ''))
    for f in report['findings']:
        if f.severity != 'info':
            lines.append(f'  [{f.severity}] {f.side} {f.kind}/{f.sub} t={f.t} frame={f.frame} {f.map} {f.text[:150]}  <{f.key}>')
    return lines


# ====================================================================== bounds from the private world model

def build_bounds(world_dir):
    """{maps: {name: {x, y, z}}} from <world>/nav/*.json.gz: the min and max of every nav mesh's vertices. Reads data, names nothing."""
    maps = {}
    for p in sorted(Path(world_dir, 'nav').glob('*.json.gz')):
        d = json.load(gzip.open(p, 'rt'))
        v = d.get('verts') or []
        if len(v) < 3:
            continue
        xs, ys, zs = v[0::3], v[1::3], v[2::3]
        maps[p.name[:-len('.json.gz')]] = {'x': [min(xs), max(xs)], 'y': [min(ys), max(ys)], 'z': [min(zs), max(zs)]}
    return {'maps': maps}


# ====================================================================== CLI

def cmd_analyze(a):
    cfg = Config.from_dict(json.loads(Path(a.config).read_text()) if a.config else None)
    sides = None
    if a.side:
        sides = {}
        for item in a.side:
            n, p = item.split('=', 1)
            sides[n] = load_side(p, n)
    bounds = Bounds.load(a.bounds) if a.bounds else None
    report = analyze(a.folder, cfg, bounds, load_baseline(a.baseline), None, None, sides)
    if a.json:
        print(json.dumps({'findings': [f.to_dict() for f in report['findings']], 'detectors': report['detectors']}, indent=1))
    else:
        print('\n'.join(summarize(report)))
    return 1 if any(f.severity == 'error' for f in report['findings']) else 0


def cmd_baseline(a):
    shapes = build_baseline(a.logs)
    Path(a.out).write_text(json.dumps({'logs': len(a.logs), 'shapes': shapes}, indent=0))
    print(f'{len(shapes)} shapes from {len(a.logs)} logs -> {a.out}')
    return 0


def cmd_bounds(a):
    b = build_bounds(a.world)
    Path(a.out).write_text(json.dumps(b))
    print(f'{len(b["maps"])} maps -> {a.out}')
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('analyze')
    s.add_argument('folder')
    s.add_argument('--side', action='append', metavar='NAME=PATH')
    s.add_argument('--config')
    s.add_argument('--bounds')
    s.add_argument('--baseline')
    s.add_argument('--json', action='store_true')
    b = sub.add_parser('baseline')
    b.add_argument('logs', nargs='+')
    b.add_argument('--out', required=True)
    d = sub.add_parser('bounds')
    d.add_argument('world')
    d.add_argument('--out', required=True)
    a = ap.parse_args()
    return {'analyze': cmd_analyze, 'baseline': cmd_baseline, 'bounds': cmd_bounds}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
