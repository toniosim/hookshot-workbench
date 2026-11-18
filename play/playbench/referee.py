"""The referee: did the GAME's state show the goal? Judged on the run's state journal (live/state.jsonl: one row per sampled present), not on the pilot's own
word (the pilot has marked a goal solved that the game never showed). A proof is a small tree (board.PROOFS):

  flag         a watched flag compares true (`op` = < > <= >= != =, `value`); a flag the segment does not watch is never in the journal: board.proof_flags
  flag_drop    a watched count fell by `drop` (default 1) from its first value: the bomb that was thrown
  rupees_gain  the rupee count rose by `gain` from its first value
  at           Link stands within `r` metres (x/z) of (x, z) on `map`, between `y_min` and `y_max` when given: a ledge top, a ladder top, the bottom of a drop,
               the lake shore. `forbid`: a list of zones {x, z, r, y_min, y_max} on the same map: a run that was in one BEFORE the proof was met did not take the way
               the task asks for (a drop that went down by the ladder beside it) and can no longer meet it: the result says `tainted`
  map          Link is on map `to` (not loading) after starting on another: a warp song, a door that loads
  any / all    a list of proofs (`all`: each met at some sample; `any`: the first one)

Only samples that show control of a place count: not loading, with a map and a position. The time to goal is game seconds from the first such sample (or the
caller's t_ref, the pilot's first decision) to the first sample that met the proof. `progress` (for position proofs only) is how much of the first distance
to the target the best sample closed (1.0 when met): a failing cell still shows movement. `start_ok` is false when the first sample is not where the cell
says it starts (the save did not put Link there): such a run is `invalid`, not a failure of the pilot.
"""
import json
import math
from pathlib import Path

OPS = {'=': lambda a, b: a == b, '!=': lambda a, b: a != b, '<': lambda a, b: a < b, '>': lambda a, b: a > b, '<=': lambda a, b: a <= b, '>=': lambda a, b: a >= b}


def number(v):
    """float of a state value (true/false and numeric text included), None when it is no number."""
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = {'true': '1', 'false': '0'}.get(v.strip().lower(), v.strip())
        try:
            return float(s)
        except ValueError:
            return None
    return None


def valid(row):
    """A sample that shows control of a place: not loading, a map and a position."""
    return bool(row) and not row.get('loading') and (row.get('map') or row.get('area')) and isinstance(row.get('pos'), (list, tuple)) and len(row['pos']) >= 3


def map_of(row):
    return row.get('map') or row.get('area')


class Node:
    """One proof (or one proof of an any/all list): `met_t` is the game time of the first sample that met it, or None."""

    def __init__(self, spec):
        self.spec = spec
        self.kind = spec['kind']
        self.met_t = None
        self.base = None            # flag_drop, rupees_gain: the first value
        self.best = None            # at: the smallest x/z distance seen (while the map was right and the y fit or not)
        self.first = None           # at: the distance at the first valid sample
        self.tainted = False        # at: a forbidden zone was entered before the proof was met
        self.children = [Node(s) for s in spec.get('of', ())]

    def feed(self, row):
        if self.met_t is not None and self.kind not in ('any', 'all'):
            return
        t = row.get('t')
        k, s = self.kind, self.spec
        if k in ('any', 'all'):
            for c in self.children:
                c.feed(row)
            times = [c.met_t for c in self.children]
            if k == 'any' and any(x is not None for x in times):
                self.met_t = min(x for x in times if x is not None)
            elif k == 'all' and all(x is not None for x in times):
                self.met_t = max(times)
            return
        if k == 'flag':
            v = (row.get('flags') or {}).get(s['name'])
            a, b = number(v), number(s['value'])
            if a is not None and b is not None:
                hit = OPS[s.get('op', '=')](a, b)
            else:   # text values (an enum's name or hash): equality only
                hit = v is not None and ((str(v) == str(s['value'])) if s.get('op', '=') == '=' else (str(v) != str(s['value'])) if s.get('op') == '!=' else False)
            if hit:
                self.met_t = t
        elif k == 'flag_drop':
            v = number((row.get('flags') or {}).get(s['name']))
            if v is None:
                return
            if self.base is None:
                self.base = v
            elif self.base - v >= s.get('drop', 1):
                self.met_t = t
        elif k == 'rupees_gain':
            v = number(row.get('rupees'))
            if v is None:
                return
            if self.base is None:
                self.base = v
            elif v - self.base >= s['gain']:
                self.met_t = t
        elif k == 'at':
            if s['map'] != map_of(row):
                return
            pos = row['pos']
            d = math.hypot(pos[0] - s['x'], pos[2] - s['z'])
            if self.first is None:
                self.first = d
            self.best = d if self.best is None else min(self.best, d)
            for z in s.get('forbid') or ():
                if math.hypot(pos[0] - z['x'], pos[2] - z['z']) <= z['r'] and (z.get('y_min') is None or pos[1] >= z['y_min']) and (z.get('y_max') is None or pos[1] <= z['y_max']):
                    self.tainted = True
            if self.tainted:
                return
            if d <= s['r'] and (s.get('y_min') is None or pos[1] >= s['y_min']) and (s.get('y_max') is None or pos[1] <= s['y_max']):
                self.met_t = t
        elif k == 'map':
            if self.base is None:
                self.base = map_of(row)
            if map_of(row) == s['to'] and self.base != s['to']:
                self.met_t = t

    def is_tainted(self):
        return self.tainted or any(c.is_tainted() for c in self.children)

    def progress(self):
        """For position proofs: the share of the first distance closed (1.0 when met), the best over an any/all list; None for the others."""
        if self.kind in ('any', 'all'):
            ps = [p for p in (c.progress() for c in self.children) if p is not None]
            return (max(ps) if self.kind == 'any' else min(ps)) if ps else None
        if self.kind != 'at':
            return None
        if self.met_t is not None:
            return 1.0
        if not self.first or self.best is None:
            return None
        return round(max(0.0, min(1.0, 1.0 - self.best / self.first)), 3)


class Referee:
    def __init__(self, proof, start=None):
        self.root = Node(proof)
        self.start = start
        self.first = None            # the first valid row
        self.last = None
        self.start_ok = None         # None until the first valid row
        self.samples = self.valid_samples = 0
        self.maps = []
        self.life_min = None
        self.deaths = 0
        self._alive = True
        self.hit_row = None

    @property
    def met(self):
        return self.root.met_t is not None

    def feed(self, row):
        """One state row; True when this row is the one that met the proof."""
        self.samples += 1
        if not valid(row):
            return False
        self.valid_samples += 1
        self.last = row
        m = map_of(row)
        if not self.maps or self.maps[-1] != m:
            self.maps.append(m)
        life = row.get('life')
        if isinstance(life, (int, float)):
            self.life_min = life if self.life_min is None else min(self.life_min, life)
            if life <= 0 and self._alive:
                self.deaths += 1
            self._alive = life > 0
        if self.first is None:
            self.first = row
            if self.start:
                pos = row['pos']
                self.start_ok = (m == self.start.get('map')) and (self.start.get('x') is None or math.hypot(pos[0] - self.start['x'], pos[2] - self.start['z']) <= self.start.get('tol_m', 8.0))
            else:
                self.start_ok = True
        was = self.met
        self.root.feed(row)
        if self.met and not was:
            self.hit_row = row
            return True
        return False

    def result(self, t_ref=None):
        """The judgement so far: {success, time_to_goal_s, progress, start_ok, ...}. t_ref: the game time the clock starts at (default the first valid sample)."""
        t0 = t_ref if t_ref is not None else (self.first or {}).get('t')
        hit = self.root.met_t
        ttg = round(hit - t0, 1) if hit is not None and t0 is not None else None
        if ttg is not None and ttg < 0:
            ttg = 0.0
        return {'success': self.met, 'time_to_goal_s': ttg, 'progress': 1.0 if self.met and self.root.progress() is not None else self.root.progress(),
                'start_ok': self.start_ok, 'samples': self.samples, 'valid_samples': self.valid_samples,
                'tainted': self.root.is_tainted() and not self.met, 'first_t': (self.first or {}).get('t'), 'last_t': (self.last or {}).get('t'), 'maps': self.maps[:6], 'life_min': self.life_min, 'deaths': self.deaths,
                'start': (self.first or {}).get('pos'), 'end': (self.last or {}).get('pos'),
                'hit': {'t': hit, 'pos': self.hit_row.get('pos'), 'map': map_of(self.hit_row)} if self.hit_row else None}


def read_rows(path, offset=0):
    """(rows, new offset) of the complete JSON lines of a journal from a byte offset (a half-written last line waits for the next call)."""
    try:
        with open(path, 'rb') as f:
            f.seek(offset)
            data = f.read()
    except OSError:
        return [], offset
    end = data.rfind(b'\n')
    if end < 0:
        return [], offset
    rows = []
    for line in data[:end].splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            pass
    return rows, offset + end + 1


def judge(proof, rows, start=None, t_ref=None):
    """The referee's result for a whole journal (a list of rows)."""
    r = Referee(proof, start)
    for row in rows:
        r.feed(row)
    return r.result(t_ref)


def first_decision_t(transcript, rows):
    """The game time (the journal's `t`) of the pilot's first decision: the transcript's first decision carries the state's `frame`, the journal row with that
    frame (or the next one) the `t`. None when either is missing."""
    frame = None
    try:
        for line in Path(transcript).read_text().splitlines():
            d = json.loads(line)
            if d.get('kind') == 'decision':
                frame = (d.get('state') or {}).get('frame')
                break
    except (OSError, ValueError):
        return None
    if frame is None:
        return None
    for row in rows:
        if isinstance(row.get('frame'), (int, float)) and row['frame'] >= frame and isinstance(row.get('t'), (int, float)):
            return row['t']
    return None
