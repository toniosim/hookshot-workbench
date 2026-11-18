"""Human-like movement for the pilot: what a person does that a route walker does not. Switchable (level 0 to 3) and
seeded, so a run can be played again move for move.

    level 0   off: every candidate's lines go out exactly as made (proofs that need determinism, duels)
    level 1   a reaction delay before a move, a little noise on the stick
    level 2   (the default of an exploration run) and: small curves in long legs, now and then a look around with the
              camera stick, a pause, a leg walked instead of run
    level 3   and: bigger curves, more looks and pauses, a roll along the way

The shaping works on the step lines a candidate would send (`walk|run <x> <z> radius <r> timeout <t>`, `wait`, `raw`,
`roll`), never on the decision itself, and it only adds: the last waypoint of every leg keeps its point and radius, so
what a goal needs (a door's front, a target's radius) is untouched. The extra words on a move line (`mag <0..1>`,
`noise <degrees>`, `seed <n>`) are read by the game side's walk step; a game side that does not know them ignores them.

Everything random is drawn from `random.Random(f"{seed}:{n}:{salt}")`, n being the decision's number, so the same seed
and the same decision always shape the same way, whatever else was drawn before.
"""
import math
import random
from dataclasses import dataclass, field

LEVELS = (0, 1, 2, 3)
KNOBS = {
    1: dict(react=0.7, pause_p=0.0, pause_s=(0.0, 0.0), look_p=0.0, curve=0.0, curve_cap=0.0, walk_p=0.0, roll_p=0.0,
            noise_deg=2.0),
    2: dict(react=1.0, pause_p=0.06, pause_s=(0.6, 1.8), look_p=0.10, curve=0.05, curve_cap=1.4, walk_p=0.12, roll_p=0.0,
            noise_deg=3.0),
    3: dict(react=1.25, pause_p=0.12, pause_s=(0.8, 2.6), look_p=0.22, curve=0.08, curve_cap=2.2, walk_p=0.22, roll_p=0.08,
            noise_deg=5.0),
}
REACTION_MEDIAN_S, REACTION_SIGMA = 0.28, 0.40      # a person's reaction to "now go": log-normal, about 0.2 to 0.5 s
REACTION_CLIP_S = (0.12, 1.5)
CURVE_MIN_LEG_M = 8.0        # shorter legs stay straight
CURVE_LONG_LEG_M = 18.0      # from this length two waypoints
LOOK_MIN_LEG_M = 8.0
ROLL_MIN_LEG_M = 12.0
WALK_MAX_LEG_M = 14.0        # a leg longer than this is always run
WAYPOINT_RADIUS = 1.5        # an intermediate waypoint is passed, not arrived at

# the candidates a person starts voluntarily (a reaction delay goes before them); everything else is a continuation, a
# wait, a fight move or a recovery and goes out as made
TRAVEL = ('go', 'go-near')
VOLUNTARY = TRAVEL + ('push', 'push-open', 'push-through', 'press-a', 'crawl-in', 'crawl-forward', 'climb-up',
                      'back-off', 'side-left', 'side-right')
DIRS = [(0, 'up'), (45, 'up-right'), (90, 'right'), (135, 'down-right'), (180, 'down'), (-135, 'down-left'),
        (-90, 'left'), (-45, 'up-left')]   # as hsap's roll names the left stick's directions (camera relative)


def wrap(d):
    return (d + 180.0) % 360.0 - 180.0


def parse_move(line):
    """('walk'|'run', x, z, [rest words]) of a move line, else None."""
    w = line.split()
    if len(w) < 3 or w[0] not in ('walk', 'run'):
        return None
    try:
        return w[0], float(w[1]), float(w[2]), w[3:]
    except ValueError:
        return None


def timeout_for(metres):
    return int(max(6, metres / 3 + 5))


def dir_name(yaw, camera, sign=1.0):
    """The camera-relative direction word (`roll up`, `roll down-left`, ...) that moves Link toward the world yaw."""
    want = wrap(camera - yaw) * sign
    return min(DIRS, key=lambda d: abs(wrap(d[0] - want)))[1]


@dataclass
class Shaped:
    lines: list
    notes: dict = field(default_factory=dict)


class Human:
    def __init__(self, level=0, seed=0):
        if level not in LEVELS:
            raise ValueError(f'humanize level must be one of {LEVELS}')
        self.level, self.seed = level, seed
        self.k = KNOBS.get(level)

    @property
    def on(self):
        return self.level > 0

    def rng(self, n, salt=''):
        return random.Random(f'{self.seed}:{n}:{salt}')

    def reaction_s(self, n):
        """A reaction delay in seconds for decision n (0 at level 0)."""
        if not self.on:
            return 0.0
        d = self.rng(n, 'react').lognormvariate(math.log(REACTION_MEDIAN_S), REACTION_SIGMA) * self.k['react']
        lo, hi = REACTION_CLIP_S
        return round(min(hi * self.k['react'], max(lo * self.k['react'], d)), 2)

    def shape(self, label, lines, st, target=None, n=0, sign=1.0, validate=None, curves_ok=True):
        """The lines to send for a candidate chosen at decision n, and what was added (notes, for the transcript).
        `st` is the state line (pos, camera), `validate(a_xz, b_xz) -> bool` says whether a shaped waypoint can be walked to
        from the point before it (the planner's verdict where there is one); a waypoint it refuses is dropped.
        `curves_ok` False (a block was seen near here, a bad point is close) keeps the legs straight."""
        if not self.on or label not in VOLUNTARY:
            return Shaped(list(lines))
        r, k, notes = self.rng(n), self.k, {}
        out = []
        d = self.reaction_s(n)
        if d >= 0.05:
            out.append(f'wait {d:.2f}')
            notes['react_s'] = d
        if k['pause_p'] and r.random() < k['pause_p']:
            p = round(r.uniform(*k['pause_s']), 2)
            out.append(f'wait {p:.2f}')
            notes['pause_s'] = p
        pos = (st or {}).get('pos')
        cam = (st or {}).get('camera')
        prev = (pos[0], pos[2]) if pos else None
        first_leg = None
        shaped_moves, walked = [], 0
        for line in lines:
            m = parse_move(line)
            if not m or prev is None:
                shaped_moves.append(line)
                continue
            verb, x, z, rest = m
            leg = math.hypot(x - prev[0], z - prev[1])
            first_leg = leg if first_leg is None else first_leg
            wps = []
            if curves_ok and label in TRAVEL and k['curve'] and leg >= CURVE_MIN_LEG_M and not (target and (target.kind == 'door' or target.front)):
                wps = self.waypoints(r, prev, (x, z), leg, validate)
            for wx, wz in wps:
                shaped_moves.append(f'{verb} {wx:.2f} {wz:.2f} radius {WAYPOINT_RADIUS:g} timeout {timeout_for(leg)}'
                                    + self.stick(r, False))
                prev = (wx, wz)
            walking = leg <= WALK_MAX_LEG_M and k['walk_p'] and r.random() < k['walk_p'] and label in TRAVEL
            walked += bool(walking)
            shaped_moves.append(line + self.stick(r, walking))
            if wps:
                notes['curve_waypoints'] = notes.get('curve_waypoints', 0) + len(wps)
            prev = (x, z)
        if walked:
            notes['walked_legs'] = walked
        if label in TRAVEL and first_leg is not None and cam is not None:
            if k['look_p'] and first_leg >= LOOK_MIN_LEG_M and r.random() < k['look_p']:
                out.append(self.look(r, notes))
            if k['roll_p'] and first_leg >= ROLL_MIN_LEG_M and pos and r.random() < k['roll_p']:
                first = next((parse_move(line) for line in lines if parse_move(line)), None)
                if first:
                    yaw = math.degrees(math.atan2(first[1] - pos[0], first[2] - pos[2]))
                    name = dir_name(yaw, cam, sign)
                    out += [f'roll {name}', 'wait 0.5']
                    notes['roll'] = name
        return Shaped(out + shaped_moves, notes)

    def stick(self, r, walking):
        """The extra words of a move line: the stick's noise and, for a walked leg, its magnitude."""
        words = ''
        if walking:
            words += ' mag 0.5'
        if self.k['noise_deg']:
            words += f" noise {self.k['noise_deg']:g} seed {r.randrange(1, 2 ** 31)}"
        return words

    def waypoints(self, r, a, b, leg, validate):
        """One or two points beside the straight line a -> b, offset by a smooth bump, each reachable from the one before."""
        n = 2 if leg >= CURVE_LONG_LEG_M else 1
        amp = min(self.k['curve'] * leg, self.k['curve_cap']) * r.uniform(0.35, 1.0)
        ux, uz = (b[0] - a[0]) / leg, (b[1] - a[1]) / leg
        side = r.choice((-1.0, 1.0))
        out, prev = [], a
        for i in range(1, n + 1):
            f = i / (n + 1)
            off = side * amp * math.sin(math.pi * f)
            if n == 2 and self.level >= 3 and i == 2:
                off = -off   # an S
            p = (a[0] + ux * leg * f - uz * off, a[1] + uz * leg * f + ux * off)
            if validate is not None and not validate(prev, p):
                continue
            out.append(p)
            prev = p
        if out and validate is not None and not validate(out[-1], b):
            return []
        return out

    def look(self, r, notes):
        """A camera look with the right stick: a turn of 140 to 420 ms, mostly followed by a turn back."""
        name = r.choice(('RLEFT', 'RRIGHT'))
        back = 'RRIGHT' if name == 'RLEFT' else 'RLEFT'
        ms = r.randrange(140, 421, 10)
        seq, end = f'0:{name}/{ms}', ms / 1000
        if r.random() < 0.55:
            ms2, at = r.randrange(120, 361, 10), end + r.uniform(0.2, 0.5)
            seq += f',{at:.2f}:{back}/{ms2}'
            end = at + ms2 / 1000
        notes['look'] = seq
        return f'raw {seq} {end + 0.25:.2f}'
