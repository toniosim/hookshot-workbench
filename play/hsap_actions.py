"""hsap_actions: the movement, combat and shop steps of hsap.py's Executor (`class Executor(ActionSteps)`). Each one ends with a
result word that is proven by the game's own state (a place, a height, a count, a flag, the life), puts what it measured in
the step event's `changes` (the same way step_pickup and step_chest do), never sends an input it was not asked for, ends `held`
before any input while an event or a load holds Link where that makes no sense, and ends `cut` when the game ends (or
restarts) under it. hsap.py's module docstring lists the steps; this is the whole of their grammar:

  jump <x> <z> [radius <r>] [y <y>] [lead <m>] [hold <ms>] [timeout <s>]   landed / short / fell / none / held / cut
  climb up|down [timeout <s>]          up: the old `climb` (done / stuck / timeout); down: done / stuck / timeout
  swim <x> <z> [radius <r>] [timeout <s>]   swam / stuck / timeout / held / cut
  dive [ms] [timeout <s>]              dived / none / held / cut
  block push|pull [m] [timeout <s>]    pushed / pulled / none / held / cut
  strafe left|right [ms]               strafed / circled / none / held / cut
  guard [ms]                           guarded / hurt / none / held / cut
  roll to <x> <z>                      rolled / none / held / cut   (the old `roll <dir>` forms stay in hsap.py)
  use [button] [at <x> <z>] [lock] [hold <ms>]   used / none / held / cut
  buy [timeout <s>]                    bought / none / no-prompt / timeout / held / cut
  choose up|down [n]                   done / held / cut
  ride <x> <z> [radius <r>] [fast <mps>] [timeout <s>]   ridden / walked / stuck / timeout / held / cut

hsap imports this module (it must, to inherit ActionSteps), so this module cannot import hsap: hsap.py hands the few helpers
these steps share with its own (wrap, split_opts, ...) to bind() once they are defined. step_seconds(), judge_jump(),
ride_speeds() and strafe_verdict() need none of them. The measuring is in module-level functions so that it can be tested alone.
"""
import math
import time

HELPERS = ('wrap', 'yaw_of', 'text_open', 'scene_music', 'prompt_empty', 'split_opts', 'seconds_of', 'BUTTON_NAMES')
wrap = yaw_of = text_open = scene_music = prompt_empty = split_opts = seconds_of = BUTTON_NAMES = None   # (bound by hsap.py)

# the verbs hsap.py dispatches to step_<verb>; `climb` and `roll` only in their new forms (plays())
ACTION_VERBS = ('jump', 'climb', 'swim', 'dive', 'block', 'strafe', 'guard', 'roll', 'use', 'buy', 'choose', 'ride')

# the time allowance of a step that takes a timeout: this default, a few seconds on top is the step's allowance (step_seconds)
JUMP_TIMEOUT, CLIMB_TIMEOUT, SWIM_TIMEOUT, BLOCK_TIMEOUT, BUY_TIMEOUT, RIDE_TIMEOUT = 12.0, 12.0, 40.0, 10.0, 45.0, 40.0
ACTION_STICK = 32767


def bind(namespace):
    """Take hsap.py's own helpers (its module namespace, once they are defined) for the steps to use."""
    globals().update({name: namespace[name] for name in HELPERS})


def plays(w):
    """True when the split step line `w` is one of these steps': a new verb, `climb down`, `roll to`. `climb` and `climb up` (the
    old step, its words done / stuck / timeout) and `roll <dir>` (the duel's roll) stay with hsap.py."""
    if not w:
        return False
    if w[0] == 'climb':
        return w[1:2] == ['down']
    if w[0] == 'roll':
        return w[1:2] == ['to']
    return w[0] in ACTION_VERBS


# ---- time allowances (interact.py style: seconds)

def _opt(words, key, default):
    """The number after `key` in the words, else the default (a malformed line is answered bad by the step itself)."""
    try:
        return float(words[words.index(key) + 1]) if key in words[:-1] else default
    except ValueError:
        return default


def _ms(words, index, default):
    """The milliseconds at words[index] when that word is a whole number, else the default."""
    return float(words[index]) if len(words) > index and words[index].isdigit() else default


def step_seconds(line):
    """The time allowance in seconds of a line of these verbs (the step's own timeout and a few seconds on top, or its own
    duration), None for any other verb. `climb` and `roll`: only the forms these steps play (`roll to`); the old `roll <dir>`
    is hsap.py's."""
    w = line.split()
    if not w or w[0] not in ACTION_VERBS:
        return None
    k = w[0]
    if k == 'jump':
        return _opt(w, 'timeout', JUMP_TIMEOUT) + _opt(w, 'hold', 800.0) / 1000 + 8.0   # (facing and the lead; the hold; the settle and the answer)
    if k == 'climb':
        return _opt(w, 'timeout', CLIMB_TIMEOUT) + 6.0
    if k == 'swim':
        return _opt(w, 'timeout', SWIM_TIMEOUT) + 6.0
    if k == 'dive':
        ms = _ms(w, 1, 1500.0)
        return _opt(w, 'timeout', ms / 1000 + 6.0) + 6.0
    if k == 'block':
        return _opt(w, 'timeout', BLOCK_TIMEOUT) + 6.0
    if k == 'strafe':
        return _ms(w, 2, 1200.0) / 1000 + 4.0
    if k == 'guard':
        return _ms(w, 1, 700.0) / 1000 + 4.0
    if k == 'roll':
        return 4.0 if w[1:2] == ['to'] else None
    if k == 'use':
        return 14.0 + _opt(w, 'hold', 150.0) / 1000 + (1.0 if 'lock' in w else 0.0) + (4.0 if 'at' in w else 0.0)   # (a text it opens is advanced)
    if k == 'buy':
        return _opt(w, 'timeout', BUY_TIMEOUT) + 6.0
    if k == 'choose':
        return 0.3 * min(6.0, max(1.0, _ms(w, 2, 1.0))) + 4.0
    return _opt(w, 'timeout', RIDE_TIMEOUT) + 6.0   # ride


# ---- what a step measured, as functions of the numbers

def jump_passed(start, end, x, z, radius):
    """True when the move from `start` to `end` ([x, y, z] each) went past the ground point (x, z) along the line from the start:
    the move projected on the direction to the point is at least the distance to it, and the sideways offset of the end from that
    line is under max(radius, 2) m (a held stick runs him on past a short gap)."""
    dx, dz = x - start[0], z - start[2]
    d0 = math.hypot(dx, dz)
    if d0 < 1e-6:
        return False
    mx, mz = end[0] - start[0], end[2] - start[2]
    return (mx * dx + mz * dz) / d0 >= d0 and abs(mx * dz - mz * dx) / d0 < max(radius, 2.0)


def judge_jump(start, end, x, z, radius, y=None):
    """landed / fell / none / short for a jump from `start` to `end` ([x, y, z] each) at the ground point (x, z). landed: within
    radius of the point in x and z, or past it (jump_passed), and the height right: with y within 1.2 m of that height, without
    not more than 1.5 m below the start; fell: more than 2.5 m below the start and not landed; none: moved under 0.3 m on the
    ground, or moved but not closer to the point; short: closer to the point than before and not landed. A start that is already
    within the radius (a short gap and a radius as long) proves nothing by standing there: such a jump is landed only when he moved
    0.6 m or more (or as far as the point, when that is nearer), unless the asked height is more than 1.2 m from the start's own
    (a ledge: the height is the proof)."""
    d0, d1 = math.hypot(x - start[0], z - start[2]), math.hypot(x - end[0], z - end[2])
    dy = end[1] - start[1]
    moved = math.hypot(end[0] - start[0], end[2] - start[2])
    height_proves = y is not None and abs(start[1] - y) > 1.2
    if d0 <= radius and not height_proves and moved < min(0.6, d0):
        return 'none' if dy >= -2.5 else 'fell'
    if (d1 <= radius or jump_passed(start, end, x, z, radius)) and (abs(end[1] - y) <= 1.2 if y is not None else dy >= -1.5):
        return 'landed'
    if dy < -2.5:
        return 'fell'
    if math.hypot(end[0] - start[0], end[2] - start[2]) < 0.3:
        return 'none'
    return 'short' if d1 < d0 else 'none'


def ride_speeds(points):
    """(the best ground speed over a 1.0 s window, the mean ground speed over the whole move), metres a second, of the points
    (t, x, z) in time order: the way along the path over the time. The best is None where no window of a second fits in the move."""
    pts = [p for i, p in enumerate(points) if i == 0 or p[0] > points[i - 1][0]]
    if len(pts) < 2:
        return None, None
    path = [0.0]
    for a, b in zip(pts, pts[1:]):
        path.append(path[-1] + math.hypot(b[1] - a[1], b[2] - a[2]))
    best, j = None, 0
    for i in range(len(pts)):
        j = max(j, i + 1)
        while j < len(pts) and pts[j][0] - pts[i][0] < 1.0 - 1e-9:
            j += 1
        if j >= len(pts):
            break
        speed = (path[j] - path[i]) / (pts[j][0] - pts[i][0])
        best = speed if best is None else max(best, speed)
    return best, path[-1] / (pts[-1][0] - pts[0][0])


def strafe_verdict(perp, facing_change):
    """strafed / circled / none from the way moved sideways (metres, positive to Link's left) and how his facing changed
    (degrees, positive turning left). strafed: at least 0.5 m sideways and the facing turned under 25 degrees; circled: at least
    0.5 m and the facing turned 25 degrees or more toward the centre of the circle (the side opposite to the move)."""
    if abs(perp) < 0.5:
        return 'none'
    if abs(facing_change) < 25.0:
        return 'strafed'
    return 'circled' if facing_change * perp < 0 else 'none'


def _number(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValueError(f'{text!r} is not a finite number')
    return value


def _whole(text, low, high, what):
    try:
        value = int(text)
    except ValueError:
        raise ValueError(f'{what} must be a whole number: {text!r}') from None
    if not low <= value <= high:
        raise ValueError(f'{what}: {low} to {high}')
    return value


def _round(pos):
    return [round(v, 2) for v in pos]


class ActionSteps:
    """step_jump ... step_ride: mixed into hsap.Executor, which supplies self.g, fresh(), snap(), changes(), outcome(), walk(),
    wait(), wait_input(), tick(), stick_at(), face_point(), advance_text(), no_prompt(), climb()."""

    # ---- the parts the steps share
    def _clock(self):
        """The game's own clock (the newest sample's t), else wall time: one clock for the waits and windows below."""
        t = (self.g.st or {}).get('t')
        return t if isinstance(t, (int, float)) else time.time()

    def _wait_game(self, seconds):
        """Tick until the game clock has run `seconds` (the wall time as a bound: three times that and a second)."""
        end, cap = self._clock() + seconds, time.time() + 3 * seconds + 1.0
        while self.g.alive() and self._clock() < end and time.time() < cap:
            self.tick(0.03)

    def _follow(self, seconds, rid=None):
        """Tick until the game clock has run `seconds` and the request `rid` (if any) is over: [(clock, pos)] of each new sample."""
        end, cap, out = self._clock() + seconds, time.time() + 3 * seconds + 1.0, []
        while self.g.alive() and time.time() < cap and (self._clock() < end or (rid is not None and rid in self.g.pending)):
            n = self.g.n_states
            self.tick(0.03)
            pos = (self.g.st or {}).get('pos')
            if self.g.n_states != n and pos:
                out.append((self._clock(), list(pos)))
        return out

    def _settle(self, limit=3.0, span=0.4, eps=0.05):
        """Tick until Link's y changed under eps metres over `span` seconds, at most `limit` seconds (the game clock)."""
        end, cap, seen = self._clock() + limit, time.time() + 3 * limit + 1.0, []
        while self.g.alive() and time.time() < cap:
            pos, now = (self.g.st or {}).get('pos'), self._clock()
            if pos and (not seen or seen[-1][0] != now):
                seen.append((now, pos[1]))
            if seen and now - seen[0][0] >= span - 1e-6:
                recent = [y for t, y in seen if now - t <= span + 1e-6]
                if max(recent) - min(recent) < eps:
                    return True
            if now >= end:
                return False
            self.tick(0.03)
        return False

    def _gone(self, restarts):
        if self.g.restarts != restarts:
            return 'cut', 'the game restarted itself during the step'
        if not self.g.alive():
            return 'cut', 'the game ended'
        return None

    def _refuse(self, st, camera=True):
        """None when Link can act now; else the step's (result, detail): held while an event or a load holds him, none without a
        place (and a camera, for a stick that steers)."""
        if st.get('event') == 1 or st.get('loading') == 1:
            return 'held', f"{'a load' if st.get('loading') == 1 else 'an event'} holds Link: nothing was sent"
        if not st.get('pos') or (camera and st.get('camera') is None):
            return 'none', 'no sample of Link yet (no place or camera): nothing was sent'
        return None

    def _close(self, restarts, result, before, mark, extra, said=''):
        """The step's (result, detail): cut when the game ended or restarted, else the result with what changed (the
        state's own changes, then what this step measured)."""
        gone = self._gone(restarts)
        if gone:
            return gone
        ch = self.changes(before, self.snap(), mark)
        ch.update(extra)
        return self.outcome(result, ch, said)

    # ---- jump
    def step_jump(self, args):
        usage = 'jump <x> <z> [radius <r>] [y <y>] [lead <m>] [hold <ms>] [timeout <s>]'
        pos, kv, _ = split_opts(args, keys=('radius', 'y', 'lead', 'hold', 'timeout'))
        if len(pos) != 2:
            raise ValueError(usage)
        x, z = _number(pos[0]), _number(pos[1])
        radius = _number(kv.get('radius', 1.2))
        if radius <= 0:
            raise ValueError('radius must be above 0')
        y = _number(kv['y']) if 'y' in kv else None
        lead = _number(kv.get('lead', 0.0))
        if not 0.0 <= lead <= 20.0:
            raise ValueError('lead: 0 to 20 metres')
        hold = _whole(kv.get('hold', 800), 400, 3000, 'hold')
        timeout = seconds_of(kv, JUMP_TIMEOUT)
        restarts = self.g.restarts
        refusal = self._refuse(self.fresh())
        if refusal:
            return refusal
        before, mark = self.snap(), self.g.n_states
        notes = []
        turned, why = self.face_point(x, z, 15.0)
        if turned != 'done':
            notes.append(f'facing the point: {why}')
        p = (self.g.st or {}).get('pos') or before['pos']
        d = math.hypot(x - p[0], z - p[2])
        if lead > 0 and d > 0.05:   # straight back from the point, then the run-up is the jump's own stick
            result, detail = self.walk(p[0] - lead * (x - p[0]) / d, p[2] - lead * (z - p[2]) / d, 0.4, timeout)
            if result in ('held', 'cut'):
                return result, detail
            notes.append(f'lead {lead:g} m: walk {result}')
            self.face_point(x, z, 15.0)
        st = self.fresh()
        start = list(st.get('pos') or before['pos'])
        lx, ly = self.stick_at(yaw_of(x - start[0], z - start[2]))
        self.wait_input(self.g.send(f'0:LX={lx}+LY={ly}/{hold},0.15:X/100'))   # the stick; X 150 ms after its start (a jump)
        self._settle()
        end = list((self.g.st or {}).get('pos') or start)
        result = judge_jump(start, end, x, z, radius, y)
        d0, d1 = math.hypot(x - start[0], z - start[2]), math.hypot(x - end[0], z - end[2])
        moved = math.hypot(end[0] - start[0], end[2] - start[2])
        if result == 'landed' and d1 > radius:
            notes.append('passed the point (an overshoot)')
        said = '; '.join(notes + [f'{d0:.1f} m from the point at the start, {d1:.1f} m at the end, y {start[1]:.2f} -> {end[1]:.2f}'])
        return self._close(restarts, result, before, mark,
                           {'pos': [_round(start), _round(end)], 'dy': round(end[1] - start[1], 2), 'moved': round(moved, 2)}, said)

    # ---- climb
    def step_climb(self, args):
        usage = 'climb up|down [timeout <s>]'
        pos, kv, _ = split_opts(args, keys=('timeout',))
        if len(pos) != 1 or pos[0] not in ('up', 'down'):
            raise ValueError(usage)
        timeout = seconds_of(kv, CLIMB_TIMEOUT)
        if pos[0] == 'up':
            return self.climb(timeout)
        restarts = self.g.restarts
        refusal = self._refuse(self.fresh(), camera=False)
        if refusal:
            return refusal
        before, mark = self.snap(), self.g.n_states
        y0 = bottom = before['pos'][1]
        start = bottom_at = time.time()
        result = 'timeout'
        while time.time() - start < timeout and self.g.alive():   # (the old climb's loop, the stick down)
            self.g.stick(0, -ACTION_STICK, 250)
            self.wait(0.2)
            y = ((self.g.st or {}).get('pos') or [0, y0, 0])[1]
            if y < bottom - 0.05:
                bottom, bottom_at = y, time.time()
            if y0 - bottom > 1.0 and time.time() - bottom_at > 1.0:
                result = 'done'
                break
            if y0 - bottom < 0.2 and time.time() - start > 3.0:
                result = 'stuck'
                break
        dropped = y0 - ((self.g.st or {}).get('pos') or [0, y0, 0])[1]
        said = {'done': f'dropped {dropped:.1f} m', 'stuck': f'dropped {dropped:.2f} m in 3 s',
                'timeout': f'dropped {dropped:.1f} m in {timeout:g} s'}[result]
        return self._close(restarts, result, before, mark, {'dy': round(-dropped, 2)}, said)

    # ---- swim
    def step_swim(self, args):
        usage = 'swim <x> <z> [radius <r>] [timeout <s>]'
        pos, kv, _ = split_opts(args, keys=('radius', 'timeout'))
        if len(pos) != 2:
            raise ValueError(usage)
        x, z = _number(pos[0]), _number(pos[1])
        radius = _number(kv.get('radius', 1.5))
        if radius <= 0:
            raise ValueError('radius must be above 0')
        timeout = seconds_of(kv, SWIM_TIMEOUT)
        restarts = self.g.restarts
        st = self.fresh()
        if not st.get('pos'):
            return 'none', 'no sample of Link yet: nothing was sent'
        before, mark = self.snap(), self.g.n_states
        y0 = st['pos'][1]
        result, detail = self.walk(x, z, radius, timeout)   # (water has no wall: the stick swims him)
        end = (self.g.st or {}).get('pos') or st['pos']
        extra = {'pos': [_round(before['pos']), _round(end)], 'dy': round(end[1] - y0, 2)}
        if result == 'reached':
            return self._close(restarts, 'swam', before, mark, extra, f'y {y0:.2f} -> {end[1]:.2f}; {detail}')
        if result == 'cut':
            return result, detail
        return self._close(restarts, result, before, mark, extra, detail)

    # ---- dive
    def step_dive(self, args):
        usage = 'dive [ms] [timeout <s>]'
        pos, kv, _ = split_opts(args, keys=('timeout',))
        if len(pos) > 1:
            raise ValueError(usage)
        ms = _whole(pos[0], 200, 8000, 'ms') if pos else 1500
        timeout = seconds_of(kv, ms / 1000 + 6.0)
        restarts = self.g.restarts
        st = self.fresh()
        refusal = self._refuse(st, camera=False)
        if refusal:
            return refusal
        before, mark = self.snap(), self.g.n_states
        y0 = before['pos'][1]
        rid, end = self.g.press('A', ms), time.time() + timeout   # A is the dive button in the water: held, the stick still
        while rid in self.g.pending and self.g.alive() and time.time() < end:
            self.tick(0.03)
        over = rid in self.g.pending
        held = [s for n, s in self.g.history if mark < n <= self.g.n_states]   # (the samples of the hold)
        low = min([y0] + [s['pos'][1] for s in held if s.get('pos')])
        said = f'A held {ms} ms' + (f'; the hold had not ended after {timeout:g} s' if over else '') + \
               f'; lowest y {low:.2f} (start {y0:.2f})'
        self._wait_game(0.3)   # (the game's own depth flag is a constant, on land and in water: only y proves a dive)
        return self._close(restarts, 'dived' if y0 - low >= 0.4 else 'none', before, mark,
                           {'dy': round(low - y0, 2), 'min_y': round(low, 2)}, said)

    # ---- block
    def step_block(self, args):
        usage = 'block push|pull [m] [timeout <s>]'
        pos, kv, _ = split_opts(args, keys=('timeout',))
        if not 1 <= len(pos) <= 2 or pos[0] not in ('push', 'pull'):
            raise ValueError(usage)
        mode = pos[0]
        m = _number(pos[1]) if len(pos) == 2 else 2.0
        if not 0.3 <= m <= 10.0:
            raise ValueError('m: 0.3 to 10 metres')
        timeout = seconds_of(kv, BLOCK_TIMEOUT)
        restarts = self.g.restarts
        st = self.fresh()
        refusal = self._refuse(st)
        if refusal:
            return refusal
        if st.get('facing') is None:
            return 'none', 'no facing in the sample of Link: nothing was sent'
        before, mark = self.snap(), self.g.n_states
        f0, p0 = st['facing'], list(st['pos'])
        yaw = f0 if mode == 'push' else f0 + 180.0   # the line he moves along, from his facing
        ux, uz = math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
        along = lambda p: (p[0] - p0[0]) * ux + (p[2] - p0[2]) * uz   # noqa: E731
        start = time.time()
        hold_until = 0.0
        while self.g.alive() and time.time() - start < timeout:
            cur = self.g.st or {}
            if cur.get('pos') and along(cur['pos']) >= m:
                break
            if time.time() >= hold_until - 0.12 and cur.get('camera') is not None:   # A held the whole way: renewed short holds
                lx, ly = self.stick_at(yaw)
                self.g.send(f'0:A+LX={lx}+LY={ly}/300')
                hold_until = time.time() + 0.3
            self.tick(0.03)
        self._wait_game(0.4)   # (the last hold runs out and he stops)
        end = self.snap()
        moved = along(end['pos']) if end['pos'] else 0.0
        drift = wrap(end['facing'] - f0) if end['facing'] is not None else 0.0
        word = 'pushed' if mode == 'push' else 'pulled'
        result = word if moved >= min(0.5, m) and abs(drift) <= 25.0 else 'none'
        said = f'{moved:.2f} m along the line (asked {m:g}), facing {drift:+.0f} degrees'
        if result == 'none' and moved >= min(0.5, m):
            said += ': his facing turned, so it was no grab'
        return self._close(restarts, result, before, mark,
                           {'along': round(moved, 2), 'facing': [f0, end['facing']], 'facing_drift': round(drift, 1)}, said)

    # ---- strafe
    def step_strafe(self, args):
        usage = 'strafe left|right [ms]'
        if not 1 <= len(args) <= 2 or args[0] not in ('left', 'right'):
            raise ValueError(usage)
        ms = _whole(args[1], 300, 5000, 'ms') if len(args) == 2 else 1200
        restarts = self.g.restarts
        st = self.fresh()
        refusal = self._refuse(st)
        if refusal:
            return refusal
        if st.get('facing') is None:
            return 'none', 'no facing in the sample of Link: nothing was sent'
        before, mark = self.snap(), self.g.n_states
        f0, p0 = st['facing'], list(st['pos'])
        side = -ACTION_STICK if args[0] == 'left' else ACTION_STICK   # camera relative: the stick sideways, ZL (the lock) held
        self.wait_input(self.g.send(f'0:ZL+LX={side}+LY=0/{ms}'))
        self._wait_game(0.3)
        end = self.snap()
        if not end['pos'] or end['facing'] is None:
            return 'none', 'no sample of Link after the move'
        left = f0 + 90.0   # (his left is 90 degrees from his facing, positive toward +x when he faces +z)
        perp = (end['pos'][0] - p0[0]) * math.sin(math.radians(left)) + (end['pos'][2] - p0[2]) * math.cos(math.radians(left))
        change = wrap(end['facing'] - f0)
        result = strafe_verdict(perp, change)
        said = f'ZL held {ms} ms, stick {args[0]}: {perp:+.2f} m to his left, facing {change:+.0f} degrees'
        return self._close(restarts, result, before, mark,
                           {'perp_m': round(perp, 2), 'facing_change': round(change, 1), 'facing': [f0, end['facing']]}, said)

    # ---- guard
    def step_guard(self, args):
        usage = 'guard [ms]'
        if len(args) > 1:
            raise ValueError(usage)
        ms = _whole(args[0], 50, 5000, 'ms') if args else 700
        restarts = self.g.restarts
        st = self.fresh()
        refusal = self._refuse(st, camera=False)
        if refusal:
            return refusal
        life0 = st.get('life')
        if not isinstance(life0, (int, float)):
            return 'none', 'no life in the sample of Link: nothing was sent'
        before, mark = self.snap(), self.g.n_states
        self.wait_input(self.g.press('ZL', ms))
        self._wait_game(0.6)   # (a hit that lands just after the guard drops counts as well)
        lives = [s['life'] for s in self.g.window(mark) if isinstance(s.get('life'), (int, float))]
        low = min([life0] + lives)
        last = lives[-1] if lives else life0
        result = 'hurt' if low < life0 else 'guarded'
        return self._close(restarts, result, before, mark, {'life': [life0, last]},
                           f'ZL held {ms} ms; life {life0} -> {last} (lowest {low})')

    # ---- roll
    def step_roll(self, args):
        usage = 'roll to <x> <z>'
        if len(args) != 3 or args[0] != 'to':
            raise ValueError(usage)
        x, z = _number(args[1]), _number(args[2])
        restarts = self.g.restarts
        st = self.fresh()
        refusal = self._refuse(st)
        if refusal:
            return refusal
        before, mark = self.snap(), self.g.n_states
        p0 = list(st['pos'])
        bearing = yaw_of(x - p0[0], z - p0[2])
        lx, ly = self.stick_at(bearing)
        t0 = self._clock()
        rid = self.g.send(f'0:LX={lx}+LY={ly}/240,0.05:A/100')   # the duel's roll: the stick, then A a moment later
        track = [(t0, p0)] + self._follow(0.9, rid)
        p1 = next((p for t, p in track if t >= t0 + 0.8), track[-1][1])
        moved = math.hypot(p1[0] - p0[0], p1[2] - p0[2])
        off = abs(wrap(yaw_of(p1[0] - p0[0], p1[2] - p0[2]) - bearing)) if moved > 1e-6 else 180.0
        result = 'rolled' if moved >= 1.0 and off <= 60.0 else 'none'
        return self._close(restarts, result, before, mark, {'pos': [_round(p0), _round(p1)], 'moved': round(moved, 2)},
                           f'{moved:.2f} m in the first 0.8 s, {off:.0f} degrees off the bearing to the point')

    # ---- use
    def step_use(self, args):
        usage = 'use [button] [at <x> <z>] [lock] [hold <ms>]'
        words, at = list(args), None
        if 'at' in words:
            i = words.index('at')
            if len(words) < i + 3:
                raise ValueError(usage)
            at = (_number(words[i + 1]), _number(words[i + 2]))
            del words[i:i + 3]
        pos, kv, fl = split_opts(words, flags=('lock',), keys=('hold',))
        if len(pos) > 1 or (pos and pos[0] not in BUTTON_NAMES):
            raise ValueError(usage + '; buttons: ' + ' '.join(BUTTON_NAMES))
        button = pos[0] if pos else 'ZR'
        hold = _whole(kv.get('hold', 150), 50, 3000, 'hold')
        restarts = self.g.restarts
        refusal = self._refuse(self.fresh(), camera=at is not None)
        if refusal:
            return refusal
        if at is not None:
            self.face_point(at[0], at[1], 12.0)
        self.fresh()
        before, mark = self.snap(), self.g.n_states
        if 'lock' in fl:   # a lock-on aim: ZL from 0.4 s before the item press to 0.6 s after it
            rid = self.g.send(f'0:ZL/{400 + hold + 600},0.4:{button}/{hold}')
        else:
            rid = self.g.press(button, hold)
        self.wait_input(rid)
        self._wait_game(1.0)
        if text_open(self.g.st or {}):
            self.advance_text(time.time() + 10.0)
        after = self.snap()
        turns = [abs(wrap(s[k] - before[k])) for s in self.g.window(mark) + [self.g.st or {}] for k in ('camera', 'facing')
                 if s.get(k) is not None and before.get(k) is not None]
        aimed = max(turns, default=0.0)
        ch = self.changes(before, after, mark)
        for k in ('camera', 'facing'):
            if None not in (before[k], after[k]) and abs(wrap(after[k] - before[k])) >= 4.0:
                ch[k] = [before[k], after[k]]
        ch['aimed'] = round(aimed, 1)
        used = any(k in ch for k in ('rupees', 'life', 'flags', 'hashes', 'prompt')) or aimed >= 4.0
        gone = self._gone(restarts)
        if gone:
            return gone
        return self.outcome('used' if used else 'none', ch, f'{button} held {hold} ms' + (' with ZL held' if 'lock' in fl else ''))

    # ---- buy, choose
    def _answer_text(self, deadline, rupees):
        """A every 1.2 s while the text is open, as advance_text does; a text that stays open 3 s with the rupees as they were is
        a question: A on the cursor's default at once (not waiting for the next 1.2 s). (closed, presses, answers)."""
        presses = answers = 0
        calm, next_press, since, seen = None, time.time() + 0.8, None, rupees
        while self.g.alive():
            st, now = self.g.st or {}, time.time()
            if now >= deadline:
                return False, presses, answers
            if st.get('rupees') != seen:
                seen, since = st.get('rupees'), None   # (the count moved: the question, if it was one, has been answered)
            if text_open(st):
                calm, since = None, since or now
                if now >= next_press:
                    self.wait_input(self.g.press('A', 100))
                    presses, next_press = presses + 1, time.time() + 1.2
                elif now - since >= 3.0 and st.get('rupees') == rupees:
                    self.wait_input(self.g.press('A', 100))
                    answers, since = answers + 1, time.time()
            elif st.get('event') == 1 or st.get('loading') == 1:   # a scene, a load: waited out
                calm, since = None, None
            else:
                calm, since = calm or now, None
                if now - calm >= 0.6:
                    return True, presses, answers
            self.tick(0.05)
        return False, presses, answers

    def step_buy(self, args):
        usage = 'buy [timeout <s>]'
        pos, kv, _ = split_opts(args, keys=('timeout',))
        if pos:
            raise ValueError(usage)
        timeout = seconds_of(kv, BUY_TIMEOUT)
        restarts = self.g.restarts
        st = self.fresh()
        if st.get('loading') == 1 or (st.get('event') == 1 and scene_music(st)):
            return 'held', f"{'a load' if st.get('loading') == 1 else 'a scene'} holds Link: nothing was sent"
        before, mark = self.snap(), self.g.n_states
        deadline = time.time() + timeout
        if not text_open(st):   # (a text already open is only advanced)
            if prompt_empty(st.get('prompt')):
                return self.no_prompt(st.get('prompt'))
            self.wait_input(self.g.press('A', 100))
            react = time.time() + 2.5
            while time.time() < react and self.g.alive() and not (self.g.st or {}).get('event'):
                self.tick(0.05)
        closed, presses, answers = self._answer_text(deadline, before['rupees'])
        self._wait_game(0.6)
        after = self.snap()
        r0, r1 = before['rupees'], after['rupees']
        fell = isinstance(r0, (int, float)) and isinstance(r1, (int, float)) and r1 < r0
        result = 'bought' if fell else 'none' if closed else 'timeout'
        return self._close(restarts, result, before, mark, {},
                           f'{presses} A presses' + (f', {answers} to a question' if answers else ''))

    def step_choose(self, args):
        usage = 'choose up|down [n]'
        if not 1 <= len(args) <= 2 or args[0] not in ('up', 'down'):
            raise ValueError(usage)
        n = _whole(args[1], 1, 6, 'n') if len(args) == 2 else 1
        restarts = self.g.restarts
        st = self.fresh()
        if st.get('loading') == 1:
            return 'held', 'a load holds Link: nothing was sent'
        before, mark = self.snap(), self.g.n_states
        name = 'LUP' if args[0] == 'up' else 'LDOWN'
        script = ','.join([f'{i * 0.3:g}:{name}/120' for i in range(n)] + [f'{n * 0.3:g}:A/100'])   # the presses 0.3 s apart, then A
        self.wait_input(self.g.send(script))
        self._wait_game(0.5)
        return self._close(restarts, 'done', before, mark, {}, f'stick {args[0]} x{n}, then A')

    # ---- ride
    def step_ride(self, args):
        usage = 'ride <x> <z> [radius <r>] [fast <mps>] [timeout <s>]'
        pos, kv, _ = split_opts(args, keys=('radius', 'fast', 'timeout'))
        if len(pos) != 2:
            raise ValueError(usage)
        x, z = _number(pos[0]), _number(pos[1])
        radius, fast = _number(kv.get('radius', 2.0)), _number(kv.get('fast', 6.5))
        if radius <= 0 or fast <= 0:
            raise ValueError('radius and fast must be above 0')
        timeout = seconds_of(kv, RIDE_TIMEOUT)
        restarts = self.g.restarts
        st = self.fresh()
        if not st.get('pos'):
            return 'none', 'no sample of Link yet: nothing was sent'
        before, mark = self.snap(), self.g.n_states
        result, detail = self.walk(x, z, radius, timeout)
        if result == 'cut':
            return result, detail
        points = [(s['t'], s['pos'][0], s['pos'][2]) for s in [st] + self.g.window(mark)
                  if isinstance(s.get('t'), (int, float)) and s.get('pos')]
        best, mean = ride_speeds(points)
        extra = {}
        if best is not None:
            extra['speed_max'] = round(best, 2)
        if mean is not None:
            extra['speed_mean'] = round(mean, 2)
        speed = f"best 1 s window {best:.1f} m/s, mean {mean:.1f}" if best is not None else 'no 1 s window in the move'
        if result == 'reached':
            result = 'ridden' if best is not None and best >= fast else 'walked'
        return self._close(restarts, result, before, mark, extra, f'{speed} (ridden from {fast:g}); {detail}')
