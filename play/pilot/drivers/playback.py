"""playback: replay an ls-input-recording/1 file through the pilot's own input path, no model.

Each decision point plays the next chunk of the recording (the inputs between two marks, recording.chunks) as one step of its own,
`playback:<k>`, through the same guard-free path as every other step, so the run loop, the transcript and the recorder (a replay of a
replay) are the same. Two ways to turn a chunk into hsap lines (`mode`):

  raw   (default) the inputs are scheduled inside the game's own frame clock: runs of inputs become `raw` sequences (hos units, analog
        sticks as LX=/LY= tokens, each entry at its frame offset and for its frame count), so a replay moves Link as far as the original
        did however the PC is loaded. A sequence covers at most RAW_SPAN_S seconds and RAW_ENTRIES inputs; between sequences the wall wait
        is the recording's spacing less the typical overshoot of hsap's 50 ms wait loop.
  push  the recorded requests one after another as hsap `press` / `push` steps (inputlog.to_hsap_steps: the converter the bug hunter's
        replay uses). Each step waits for its input to end, and the next is sent a frame or more after, so a long stretch of steering
        comes out shorter than it was; kept for comparison and for a bridge that does not take analog tokens in a sequence.

Divergence is reported, never skipped over: before each chunk the state the pilot has is compared with the mark the recording had
there (the map by name, the position within `tolerance_m` metres on the ground). A replay that left the road raises `diverged`
with where and by how much; the chain then falls back only if the scenario says so, else the run ends with the reason. A recording
that is played to its end without the scenario's goals met raises `exhausted`.

The start setup: `setup()` says what the recording was made from (its header's save and boot) unless the scenario's own `setup`
table overrides it (`save`, `boot`, `steps`: hsap steps sent before the first chunk).
"""
import math
from pathlib import Path

import inputlog

from . import recording
from .base import Availability, Decision, Driver, DriverFailure, Provenance

MAX_WAIT_S = 60.0   # a pause in the recording longer than this is cut to it (a scene's or a model's wait is the original's time: replayed as it was)
MODES = ('raw', 'push')
RAW_SPAN_S = 4.0    # one raw sequence covers at most this much of the recording ...
RAW_ENTRIES = 24    # ... and this many inputs (a line stays under a kilobyte)
RAW_SPLIT_S = 1.0   # a pause of this much between two inputs ends a sequence (the pause is then a wall wait)
SETTLE_S = 3.0      # after the last recorded input the replay waits this long once for the goals to show (a flag flips a moment after the input that earned it)
RAW_OVERSHOOT_S = 0.025   # hsap's wait loop sleeps 50 ms at a time: a wait ends 0 to 50 ms late, 25 on average


class PlaybackDriver(Driver):
    name = 'playback'
    kind = 'recording'

    def __init__(self, path, *, tolerance_m=None, include_live=False, setup=None, max_wait_s=MAX_WAIT_S, mode='raw', settle_s=SETTLE_S):
        if mode not in MODES:
            raise ValueError(f'playback mode is one of {", ".join(MODES)}, not {mode!r}')
        self.mode, self.settle_s, self.settled = mode, float(settle_s), False
        self.path = Path(path)
        try:
            self.header, events, marks = recording.load(self.path)
        except (OSError, ValueError) as e:
            raise ValueError(f'recording {path}: {e}') from None
        self.tolerance = float(tolerance_m or self.header.get('tolerance_m') or recording.TOLERANCE_M)
        self.include_live, self.max_wait = include_live, max_wait_s
        if not include_live:   # debug `!` lines (pictures, cheats) are not the player's inputs
            events = [e for e in events if e.get('cmd') != 'live']
        self.events = recording.trim_overlaps(events)
        self.chunks, self.trailing = recording.chunks(self.events, marks)
        self.n_marks = len(marks)
        self._setup = dict(setup or {})
        self.cursor, self.expect, self.expect_why = 0, None, 'the start'
        self.prev_end = 0                      # the frame the last chunk's last input ended at
        self.checked = self.unchecked = 0
        self.max_off = 0.0
        self.offsets = []                      # [frame of the mark, metres off] for every mark checked: how far a replay is from the road, mark by mark
        self.trimmed_s = 0.0
        self.diverged = None

    def describe(self):
        d = super().describe()
        d.update(recording=str(self.path), mode=self.mode, events=len(self.events), chunks=len(self.chunks), marks=self.n_marks)
        return d

    def setup(self):
        """{save, boot, steps} the replay starts from: the scenario's own table over the recording's header."""
        out = {k: self.header.get(k) for k in ('save', 'boot') if self.header.get(k)}
        out.update({k: v for k, v in self._setup.items() if v})
        return out

    def available(self):
        if not self.events:
            return Availability.no('the recording has no inputs')
        return super().available()

    def stats(self):
        return {'recording': self.path.name, 'mode': self.mode, 'chunks': len(self.chunks), 'played': self.cursor, 'marks': self.n_marks,
                'marks_checked': self.checked, 'marks_unchecked': self.unchecked, 'max_off_m': round(self.max_off, 2),
                'tolerance_m': self.tolerance, 'trimmed_s': round(self.trimmed_s, 1), 'settled': self.settled, 'offsets': self.offsets, 'diverged': self.diverged}

    def check(self, st):
        """Compare the state with the mark expected now; raises `diverged` (kept in stats) when the game is elsewhere."""
        m = self.expect
        if m is None:
            return
        area, pos = st.get('area'), st.get('pos')
        if area is not None and area != m['area']:
            self._diverge(f"{self.expect_why}: the map is {area!r}, the recording was on {m['area']!r} at frame {m['f']}", m, st)
        if not pos:
            self.unchecked += 1
            return
        off = recording.off_metres(pos, m)
        self.checked += 1
        self.max_off = max(self.max_off, off)
        self.offsets.append([m['f'], round(off, 2)])
        if off > self.tolerance:
            self._diverge(f"{self.expect_why}: Link is {off:.1f} m from where the recording had him at frame {m['f']} "
                          f"(tolerance {self.tolerance:g} m; now {[round(v, 1) for v in pos]}, then {m['pos']})", m, st)

    def _diverge(self, why, mark, st):
        self.diverged = {'at_chunk': self.cursor, 'frame': mark['f'], 'why': why}
        raise DriverFailure('diverged', why, info={'expected': mark, 'seen': {k: st.get(k) for k in ('area', 'pos', 't')}})

    @staticmethod
    def timed(line):
        """A recorded `sequence` comes back as `raw <script> 0` (inputlog's converter): the sequence takes its own time on the game's side and
        raw does not wait for it, so the next step would overlap it. The wait it was given is the sequence's length."""
        w = line.split()
        if len(w) == 3 and w[0] == 'raw' and w[2] == '0':
            secs = inputlog.event_frames({'cmd': 'sequence', 'script': w[1]}) / recording.FPS
            return f'raw {w[1]} {secs:.2f}'
        return line

    @staticmethod
    def entry(e, t):
        """The raw-sequence text of one recorded input starting t seconds into its script, or None for one that has no word in the grammar.
        The bridge turns a time in seconds and a hold in milliseconds into whole frames (docs/control.md: 60 a second) and may floor, so both
        are written a little over the frame (a tenth of a frame on the start, a third of a frame on the hold, whole milliseconds) and land on
        the frame the recording had, not one before."""
        cmd = e.get('cmd')
        ms = math.ceil(max(1, int(e.get('frames') or 0)) * 1000.0 / recording.FPS + 0.3)
        at = t + 0.1 / recording.FPS
        if cmd == 'press':
            return f'{at:.4f}:{e["buttons"]}/{ms}'
        if cmd == 'stick':
            pad = 'R' if e.get('stick') == 'R' else 'L'
            return f'{at:.4f}:{pad}X={round(float(e["x"]) * 32767)}+{pad}Y={round(float(e["y"]) * 32767)}/{ms}'
        if cmd == 'sequence':   # (hos units: the script's own times, moved to t)
            return inputlog.shift_script(e['script'], t)
        return None

    def raw_lines(self, evs):
        """hsap lines for a chunk's inputs in `raw` mode: runs of inputs as one `raw <script> <wait>` each (every entry at its own frame
        offset), a `wait` for a pause of RAW_SPLIT_S or more between runs, the first run's lead-in from the end of the last chunk."""
        groups = []   # [[events], start frame, end frame]
        for e in evs:
            end = e['f'] + inputlog.event_frames(e)
            g = groups[-1] if groups else None
            if g and (e['f'] - g[2]) / recording.FPS < RAW_SPLIT_S and len(g[0]) < RAW_ENTRIES and (e['f'] - g[1]) / recording.FPS < RAW_SPAN_S:
                g[0].append(e)
                g[2] = max(g[2], end)
            else:
                groups.append([[e], e['f'], end])
        lines, prev_end = [], self.prev_end
        for i, (items, start, end) in enumerate(groups):
            gap = (start - prev_end) / recording.FPS
            if gap >= 0.1 and (i == 0 or gap >= RAW_SPLIT_S):   # (a pause: a wall wait; a small gap inside a run is already in the script)
                lines.append(f'wait {min(gap, self.max_wait):.2f}')
                self.trimmed_s += max(0.0, gap - self.max_wait)
            parts = [x for x in (self.entry(e, (e['f'] - start) / recording.FPS) for e in items) if x]
            if not parts:
                prev_end = end
                continue
            if i + 1 < len(groups):   # the next run is sent when this run's first input has been in for the spacing between them
                nxt = groups[i + 1][1]
                wait = (nxt - start) / recording.FPS
                wait = wait - RAW_OVERSHOOT_S if (nxt - end) / recording.FPS < RAW_SPLIT_S else (end - start) / recording.FPS
            else:
                wait = (end - start) / recording.FPS
            lines.append(f'raw {",".join(parts)} {max(wait, 0.0):.2f}')
            prev_end = end
        self.prev_end = prev_end
        return lines

    def lines_of(self, chunk):
        evs = chunk['events']
        if self.mode == 'raw':
            return self.raw_lines(evs)
        lines = [self.timed(ln) for ln in inputlog.to_hsap_steps(evs)]
        lead = (evs[0]['f'] - self.prev_end) / recording.FPS
        if lead >= 0.1:
            lines.insert(0, f'wait {min(lead, self.max_wait):.2f}')
            self.trimmed_s += max(0.0, lead - self.max_wait)
        self.prev_end = evs[-1]['f'] + inputlog.event_frames(evs[-1])
        return lines

    def decide(self, ctx):
        while True:
            nxt = self.chunks[self.cursor] if self.cursor < len(self.chunks) else None
            before = nxt['before'] if nxt else self.trailing
            if before:                       # states the original had between its last input and this one: the newest is the check
                self.expect, self.expect_why = before[-1], ('at the start' if self.cursor == 0 else f'before chunk {self.cursor}')
            self.check(ctx.state)
            if nxt is None and self.settle_s > 0 and not self.settled:   # the first hold: the last A press came, the flag flipped 0.1 s later, the replay had already given up
                self.settled = True
                label, text = 'playback:settle', f'the recording is played: waiting {self.settle_s:g} s for the goals to show'
                return Decision(label, provenance=Provenance(self.name, note=text), info={'playback': {'settle_s': self.settle_s}},
                                candidate=(label, [f'wait {self.settle_s:g}'], text))
            if nxt is None:
                raise DriverFailure('exhausted', f'the recording ended after {len(self.chunks)} chunks '
                                                 f'({len(self.events)} inputs) and the goals are not met')
            self.cursor += 1
            lines = self.lines_of(nxt)
            if not lines:                    # (nothing the player did: only debug lines)
                self.expect, self.expect_why = nxt['mark'] or self.expect, f'after chunk {self.cursor - 1}'
                continue
            k = self.cursor - 1
            evs = nxt['events']
            label = f'playback:{k}'
            text = f"recorded inputs {k + 1} of {len(self.chunks)}: frames {evs[0]['f']} to {evs[-1]['f']}, {len(evs)} requests"
            self.expect, self.expect_why = nxt['mark'], f'after chunk {k}'
            return Decision(label, provenance=Provenance(self.name, note=text),
                            info={'playback': {'chunk': k, 'of': len(self.chunks), 'frames': [evs[0]['f'], evs[-1]['f']],
                                               'requests': len(evs), 'expects': nxt['mark']}},
                            candidate=(label, lines, text))
