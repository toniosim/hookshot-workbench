#!/usr/bin/env python3
"""The tactics library: ways out of a stuck place, keyed by the stuck cause, every attempt recorded with its context, ranked across all maps.

Why: the recovery ladder (recover.py) used to be six rungs in one fixed order for every kind of block. A ledge from below, a person's text, a crowd,
a door's wrong side and a wall are different blocks; what gets Link past them differs, and what worked on one map says something about the next.
Here the ways out are a catalogue (`TACTICS`), each applicable to some causes (`APPLIES`) with a static order per cause (`ORDER`, the prior). The
ladder asks `Book.rank(cause, ...)` for the order to try them in; every attempt it makes is written back (`Book.record`) with the map, the age, the
cause, the place and the geometry around it, so the ranking learns:

  score = (wins + prior * K) / (attempts + K)         every attempt weighted by how alike its context is (same place > same map > anywhere);
              the prior is the static order's, scaled by the cause's pooled success rate (a tactic nobody tried starts where the cause's tactics are)

The prior is the static order's rank, so a library that has seen nothing ranks as the static order and one lucky attempt does not overturn it. The old ladder
(sidestep, angle, roll, hop, next-point, replan) is the start of the order for an unknown cause: a pilot that knows nothing behaves as before.

  Sensor      the cause and the geometry round a stuck point (routelib's cause rules over the world model, refined: one person or a crowd, the water's edge,
              another floor); bucketed, so contexts compare.
  Book        one JSONL file (`book.jsonl`): attempts, demonstrations (a way out that worked, kept relative to the place and the heading so it replays
              elsewhere), and block episodes (what stopped Link, what was tried, what finally worked: the lessons' source).
  explore     the order the nightly self-play uses: the same score plus an optimism bonus for what has been tried little.

Game-derived (places, maps): the library lives beside the route library in the harness (`tactics/`, or $PILOT_TACTICS_DIR), out of git and out of the publication. Standard
library only; no game, no network.

    python3 -I -B tactics.py report [--dir D]      the library as a table        python3 -I -B tactics.py rank CAUSE [--dir D]
"""
import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
FORMAT = 'ls-tactics/1'

STRENGTH = 5.0                  # K: the prior counts as this many attempts of weight 1
PRIOR_TOP, PRIOR_STEP, PRIOR_FLOOR, PRIOR_DEMO = 0.5, 0.035, 0.15, 0.45
PRIOR_POOL = 50.0              # the cause's pooled success rate counts as this many attempts against the static priors' mean: a tactic nobody has tried starts at what the cause's tactics do, not above a measured one
W_BASE, W_AGE, W_GEOM, W_MAP, W_CLUSTER = 0.6, 0.2, 0.2, 0.4, 2.0   # an attempt's weight: anywhere 0.6 (up to 1.0 with the same age and geometry), same map +0.4, same place +2.0
CLUSTER_M = 3.0                 # "the same place": within this many metres on the same map (and 3 m of height)
UCB_C = 0.5                     # the exploration bonus of the nightly self-play
CLIMB_NEAR_M = 2.5              # a climbable surface (ivy, a vine, a ladder) this near the stuck point is what the stuck step walked into

CAUSES = ('wall', 'ledge-up', 'drop-not-taken', 'door-side', 'npc-in-way', 'npc-crowd', 'held', 'water-edge', 'other-floor', 'slow', 'unknown')
LEGACY = ('sidestep', 'angle', 'roll', 'hop', 'next-point', 'replan')   # recover.LADDER
OUTCOMES = ('worked', 'failed', 'neutral')
SOURCES = ('live', 'journal', 'demo', 'frontier', 'selfplay')


# ------------------------------------------------------------------------------------------------------------------------ geometry
# (the moves' primitives live here; recover.py imports them)

DIRS = [(0, 'up'), (45, 'up-right'), (90, 'right'), (135, 'down-right'), (180, 'down'), (-135, 'down-left'),
        (-90, 'left'), (-45, 'up-left')]


def wrap(d):
    return (d + 180.0) % 360.0 - 180.0


def yaw_to(dx, dz):
    return math.degrees(math.atan2(dx, dz))


def heading(yaw):
    """(dx, dz) of a unit step along the yaw (0 along +z, 90 along +x)."""
    r = math.radians(yaw)
    return math.sin(r), math.cos(r)


def parse_move(line):
    w = line.split()
    if len(w) < 3 or w[0] not in ('walk', 'run'):
        return None
    try:
        return w[0], float(w[1]), float(w[2]), w[3:]
    except ValueError:
        return None


def move_line(verb, x, z, radius, timeout):
    return f'{verb} {x:.2f} {z:.2f} radius {radius:g} timeout {int(timeout)}'


def run_timeout(metres):
    return int(max(6, metres / 3 + 5))


def seg_dist(p, a, b):
    """(distance, t) of point p to the segment a-b, t in 0..1 along it."""
    dx, dz = b[0] - a[0], b[1] - a[1]
    ll = dx * dx + dz * dz
    t = 0.0 if ll < 1e-9 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dz) / ll))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dz)), t


def stick_for(yaw, camera, sign=1.0, mag=1.0):
    """(lx, ly) in -32767..32767 that moves Link toward the world yaw: the stick's angle is the camera's yaw minus the wanted
    yaw, right positive (the game side's walk steers the same way; `sign` is its learned handedness)."""
    want = math.radians(wrap(camera - yaw) * sign)
    return round(mag * 32767 * math.sin(want)), round(mag * 32767 * math.cos(want))


def dir_name(yaw, camera, sign=1.0):
    want = wrap(camera - yaw) * sign
    return min(DIRS, key=lambda d: abs(wrap(d[0] - want)))[1]


def age_of_map(name):
    name = str(name or '')
    if name.endswith('_Adult') or '_Adult_' in name:
        return 'adult'
    if name.endswith('_Child') or '_Child_' in name:
        return 'child'
    return None


def _unit(dx, dz):
    n = math.hypot(dx, dz)
    return (dx / n, dz / n) if n > 1e-9 else (0.0, 1.0)


# ------------------------------------------------------------------------------------------------------------------------ the catalogue

_ALL = frozenset(CAUSES)
_ANY = _ALL - {'held'}

APPLIES = {
    'sidestep': _ANY, 'sidestep-wide': _ANY, 'angle': _ANY, 'roll': _ANY, 'next-point': _ANY,
    'angle-steep': frozenset({'wall', 'door-side', 'npc-in-way', 'other-floor', 'unknown'}),
    'hop': frozenset({'wall', 'ledge-up', 'drop-not-taken', 'other-floor', 'slow', 'unknown'}),
    'jump': frozenset({'ledge-up', 'wall', 'drop-not-taken', 'water-edge', 'other-floor', 'unknown'}),
    'jump-a': frozenset({'ledge-up', 'wall', 'drop-not-taken', 'other-floor', 'unknown'}),
    'run-up': frozenset({'drop-not-taken', 'ledge-up', 'slow', 'wall'}),
    'climb': frozenset({'ledge-up', 'other-floor', 'wall', 'unknown'}),
    'press-a': frozenset({'door-side', 'npc-in-way', 'ledge-up', 'held', 'wall'}),
    'talk-through': frozenset({'held', 'npc-in-way', 'npc-crowd'}),
    'wait': frozenset({'held', 'npc-in-way', 'npc-crowd', 'door-side', 'slow', 'unknown'}),
    'wait-long': frozenset({'held', 'npc-in-way', 'npc-crowd'}),
    'around': frozenset({'wall', 'other-floor', 'npc-crowd', 'npc-in-way', 'door-side', 'water-edge', 'unknown', 'slow'}),
    'ring': frozenset({'npc-crowd', 'npc-in-way'}),
    'door-enter': frozenset({'door-side'}), 'door-other': frozenset({'door-side'}),
    'swim': frozenset({'water-edge'}),
    'alt-edge': frozenset({'other-floor', 'ledge-up', 'drop-not-taken', 'wall', 'door-side', 'unknown'}),
    'continue': frozenset({'slow'}),
    'replan': _ALL,
}
TACTICS = {t: {'causes': c} for t, c in APPLIES.items()}

# the static order per cause: the prior. (`replan`, the end of every ladder, is not listed: the ladder appends it.)
ORDER = {
    'wall': ['sidestep', 'angle', 'roll', 'hop', 'next-point', 'sidestep-wide', 'angle-steep', 'around', 'jump', 'jump-a', 'climb', 'alt-edge', 'press-a'],
    'unknown': ['sidestep', 'angle', 'roll', 'hop', 'next-point', 'sidestep-wide', 'around', 'jump', 'angle-steep', 'wait', 'climb', 'alt-edge'],
    'ledge-up': ['climb', 'jump', 'hop', 'jump-a', 'press-a', 'alt-edge', 'roll', 'sidestep-wide', 'sidestep', 'angle', 'run-up', 'next-point'],
    'drop-not-taken': ['run-up', 'alt-edge', 'angle', 'jump-a', 'roll', 'hop', 'jump', 'sidestep', 'sidestep-wide', 'next-point'],
    'door-side': ['door-enter', 'door-other', 'wait', 'sidestep', 'press-a', 'sidestep-wide', 'alt-edge', 'angle', 'around', 'next-point'],
    'npc-in-way': ['sidestep', 'wait', 'sidestep-wide', 'around', 'angle', 'ring', 'talk-through', 'press-a', 'roll', 'wait-long', 'angle-steep', 'next-point'],
    'npc-crowd': ['wait', 'sidestep', 'ring', 'wait-long', 'sidestep-wide', 'around', 'angle', 'talk-through', 'roll', 'next-point'],
    'held': ['talk-through', 'wait', 'press-a', 'wait-long'],
    'slow': ['continue', 'angle', 'sidestep', 'run-up', 'around', 'wait', 'next-point', 'roll', 'hop'],
    'other-floor': ['alt-edge', 'around', 'climb', 'next-point', 'jump', 'angle', 'sidestep-wide', 'sidestep', 'roll', 'hop', 'jump-a'],
    'water-edge': ['swim', 'sidestep-wide', 'around', 'jump', 'angle', 'sidestep', 'next-point', 'roll'],
}

# the frontier push's labels (PathLib: reports/PathLib.md 1.7) as tactics, so its attempts feed the same library
FRONTIER_LABELS = {'roll-at': 'roll', 'press-a': 'press-a', 'jump-a': 'jump-a', 'climb': 'climb', 'drop-run': 'run-up', 'ring-4': 'ring', 'advance': 'talk-through',
                   'continue': 'continue', 'door-enter': 'door-enter', 'door-other': 'door-other', 'wait-4': 'wait', 'wait-6': 'wait', 'wait-10': 'wait-long'}
for _s in 'LR':
    for _d in (25, 45):
        FRONTIER_LABELS[f'angle-{_s}-{_d}'] = 'angle'
    for _d in (50, 80):
        FRONTIER_LABELS[f'angle-{_s}-{_d}'] = 'angle-steep'
    for _d in (3,):
        FRONTIER_LABELS[f'shift-{_s}-{_d}'] = 'sidestep'
    for _d in (6, 8, 10):
        FRONTIER_LABELS[f'shift-{_s}-{_d}'] = 'sidestep-wide'


class Params:
    """The metres and degrees of the moves (recover.Config's side_m, back_m and angle_deg override the first three)."""
    side_m, back_m, angle_deg = 2.5, 2.0, 40.0
    wide_m, steep_deg, runup_m, around_m, ring_m, jump_m = 6.0, 70.0, 5.0, 6.0, 4.0, 2.5


def _p(cfg, name):
    return getattr(cfg, name, getattr(Params, name))


class Frame:
    """Where Link is, where the block was, where he is going (a ctx of the ladder: pos, block, target, go_lines ...)."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.px, self.pz = ctx['pos']
        t = ctx['target']
        self.tx, self.tz, self.radius = t['x'], t['z'], t.get('radius', 1.0)
        self.d = math.hypot(self.tx - self.px, self.tz - self.pz)
        self.theta = yaw_to(self.tx - self.px, self.tz - self.pz) if self.d > 1e-3 else 0.0
        self.rx, self.rz = ctx.get('block') or (self.px, self.pz)   # the sidestep and the angle are measured from where the block was
        self.dref = math.hypot(self.tx - self.rx, self.tz - self.rz)
        self.tref = yaw_to(self.tx - self.rx, self.tz - self.rz) if self.dref > 1e-3 else self.theta
        self.go = list(ctx.get('go_lines') or [move_line('run', self.tx, self.tz, self.radius, run_timeout(self.d))])
        self.side = ctx.get('side', 1)
        self.climb_at = ctx.get('climb_at') or (self.tx, self.tz)   # the climbable surface the world model knows near the block, else the target
        self.camera, self.sign = ctx.get('camera'), ctx.get('sign', 1.0)

    def along(self, a, b=0.0, yaw=None):
        """The point a metres along the heading from the block and b metres to its left (the ladder's left: yaw + 90)."""
        yaw = self.tref if yaw is None else yaw
        ux, uz = heading(yaw)
        lx, lz = heading(yaw + 90.0)
        return self.rx + a * ux + b * lx, self.rz + a * uz + b * lz


def next_lines(ctx):
    """The route points after the one that ended stuck: of the lines that were blocked, else of the plan from here."""
    lines, idx = ctx.get('block_lines') or [], ctx.get('block_idx')
    if idx is not None and idx + 1 < len(lines) and all(parse_move(x) for x in lines[idx + 1:]):
        return list(lines[idx + 1:])
    go = ctx.get('go_lines') or []
    if len(go) >= 2 and all(parse_move(x) for x in go):
        return list(go[1:])
    return []


def _angle_lines(f, cfg, deg, back_m):
    bx, bz = heading(f.tref + 180.0)
    back = (f.rx + back_m * bx, f.rz + back_m * bz)
    length = max(4.0, min(10.0, f.dref * 0.5))
    hx, hz = heading(f.tref - f.side * deg)   # the other side from the sidestep
    via = (back[0] + length * hx, back[1] + length * hz)
    return [move_line('walk', back[0], back[1], 0.4, 4), move_line('walk', via[0], via[1], 1.5, 6)] + f.go


def _door(f, ctx):
    doors = ctx.get('doors') or []
    d = min(doors, key=lambda d: math.hypot(d[0] - f.rx, d[1] - f.rz))
    ux, uz = heading(f.tref)
    return d, (d[0] + 3 * ux, d[1] + 3 * uz), (ux, uz)


def make(tid, ctx, cfg=None, book=None):
    """(lines, text) of a tactic at this place; ctx as the ladder gives it (module doc). `replan` has no lines. A demonstration (`demo:<id>`) is replayed
    relative to the block and the heading."""
    f = Frame(ctx)
    side = f.side
    side_m, back_m, angle_deg = _p(cfg, 'side_m'), _p(cfg, 'back_m'), _p(cfg, 'angle_deg')
    left = 'left' if side > 0 else 'right'
    ux, uz = heading(f.tref)
    if tid == 'sidestep':
        hx, hz = heading(f.tref + 90.0 * side)
        return ([move_line('walk', f.rx + side_m * hx, f.rz + side_m * hz, 0.6, 4)] + f.go,
                f'step {side_m:g} m to the {left} of the way to the target, then on to it')
    if tid == 'angle':
        return (_angle_lines(f, cfg, angle_deg, back_m),
                f"back up {back_m:g} m from the block and come at it {angle_deg:g} degrees to the {'right' if side > 0 else 'left'}, then on to the target")
    if tid == 'roll':
        return [f'roll {dir_name(f.theta, f.camera, f.sign)}', 'wait 0.4'] + f.go, 'roll toward the target, then on to it'
    if tid == 'hop':
        lx, ly = stick_for(f.theta, f.camera, f.sign)
        return [f'raw 0:LX={lx}+LY={ly}/800,0.15:X/100 1.2', 'wait 0.3'] + f.go, 'jump (X, no sword) toward the target, then on to it'
    if tid == 'next-point':
        return next_lines(ctx), 'skip the route point that ended stuck and go to the next'
    if tid == 'replan':
        return [], 'plan again from here, mark the point bad, leave the target'
    if tid == 'sidestep-wide':
        w = _p(cfg, 'wide_m')
        hx, hz = heading(f.tref + 90.0 * side)
        return ([move_line('walk', f.rx + w * hx, f.rz + w * hz, 0.8, 6)] + f.go, f'step {w:g} m to the {left} of the way (past a wider obstacle), then on to the target')
    if tid == 'angle-steep':
        deg = _p(cfg, 'steep_deg')
        return _angle_lines(f, cfg, deg, back_m), f"back up {back_m:g} m and come at it {deg:g} degrees to the {'right' if side > 0 else 'left'}, then on to the target"
    if tid == 'run-up':
        m = _p(cfg, 'runup_m')
        bx, bz = f.along(-m)
        fx, fz = f.along(6.0)
        return ([move_line('walk', bx, bz, 0.6, 5), f'faceat {f.tx:.2f} {f.tz:.2f} 15', move_line('run', fx, fz, 1.5, 6) + ' mag 1.0'] + f.go,
                f'back up {m:g} m, face the target and run at the block at full push (a drop is taken, a ledge cleared with a run-up)')
    if tid == 'jump':
        x, z = f.along(_p(cfg, 'jump_m'))
        return [f'jump {x:.2f} {z:.2f} radius 1.5 lead 3 hold 800 timeout 8'] + f.go, 'run up and jump (X) at the point 2.5 m ahead, then on to the target'
    if tid == 'jump-a':
        lx, ly = stick_for(f.theta, f.camera if f.camera is not None else 180.0, f.sign)
        return ([f'faceat {f.tx:.2f} {f.tz:.2f} 20', f'raw 0:LX={lx}+LY={ly}/1400,0.35:A/100,0.7:A/100 1.6'] + f.go,
                'face the target and run at it with A tapped twice (a jump, a grab), then on to it')
    if tid == 'climb':
        return ([f'faceat {f.climb_at[0]:.2f} {f.climb_at[1]:.2f} 20', 'climb timeout 10'] + f.go,
                'face the climbable surface (a ladder, ivy, a vine, a ledge) and hold up, then on to the target')
    if tid in ('wait', 'wait-long'):
        s = 4 if tid == 'wait' else 10
        return [f'wait {s}'] + f.go, f'wait {s} s (a person moves, a scene ends), then on to the target'
    if tid == 'talk-through':
        return ['advance timeout 20'] + f.go, 'advance the text that holds Link (A every 1.2 s), then on to the target'
    if tid == 'press-a':
        return [f'faceat {f.tx:.2f} {f.tz:.2f} 20', 'interact force timeout 4'] + f.go, 'face the target and press A at whatever prompt there is, then on to it'
    if tid == 'around':
        wx, wz = f.along(0.0, _p(cfg, 'around_m') * side)
        plan = ctx.get('plan_from')
        lines = None
        if callable(plan):
            try:
                lines = list(plan(wx, wz) or [])
            except Exception:   # noqa: BLE001  a planner that fails is no reason to stop: the plan from the block is the fallback
                lines = None
        return [move_line('walk', wx, wz, 1.0, 6)] + (lines or f.go), 'go round: out to the side, then the planner\'s way to the target from there'
    if tid == 'ring':
        r = _p(cfg, 'ring_m')
        pts = [(f.rx + r * math.cos(a), f.rz + r * math.sin(a)) for a in (0.0, math.pi / 2, math.pi, 3 * math.pi / 2)]
        return [move_line('run', x, z, 1.5, 6) for x, z in pts] + f.go, f'walk a ring of {r:g} m round the place (a crowd moves), then on to the target'
    if tid == 'door-enter':
        d, through, _u = _door(f, ctx)
        return [f'enter {d[0]:.2f} {d[1]:.2f} through {through[0]:.2f} {through[1]:.2f} timeout 25'], 'enter the nearest door the world model knows and go through'
    if tid == 'door-other':
        d, through, (dux, duz) = _door(f, ctx)
        return ([move_line('run', d[0] - 3 * dux, d[1] - 3 * duz, 1.5, 10), f'enter {d[0]:.2f} {d[1]:.2f} through {through[0]:.2f} {through[1]:.2f} timeout 25'],
                'go to the other side of the nearest door and enter it from there')
    if tid == 'swim':
        return [f'swim {f.tx:.2f} {f.tz:.2f} radius {f.radius:g} timeout 25'], 'swim toward the target'
    if tid == 'alt-edge':
        return list(ctx.get('alt_lines') or []), 'the world model\'s alternative edge round the block'
    if tid == 'continue':
        return list(f.go), 'carry on along the plan (the step only ran out of time)'
    if tid.startswith('demo:') and book is not None:
        d = book.demo(tid)
        if d:
            return absolute_steps(d['steps'], (f.rx, f.rz), (f.tx, f.tz)), f'replay a way out that worked at a block like this ({len(d["steps"])} steps)'
    raise KeyError(tid)


def build(tid, ctx, cfg=None, book=None):
    return make(tid, ctx, cfg, book)[0]


def applicable(tid, cause, ctx, book=None):
    """Whether the tactic can be tried for this cause with what ctx offers (a camera, a door, a way round, a hop that is allowed)."""
    if tid.startswith('demo:'):
        d = book.demo(tid) if book is not None else None
        return bool(d and d.get('cause') == cause)
    if tid not in APPLIES or cause not in APPLIES[tid]:
        return False
    cam = ctx.get('camera')
    if tid in ('roll', 'jump-a') and cam is None:
        return False
    if tid == 'hop' and (cam is None or not ctx.get('hop_ok', True)):
        return False
    if tid in ('jump', 'jump-a') and not ctx.get('hop_ok', True):
        return False
    if tid in ('door-enter', 'door-other') and not ctx.get('doors'):
        return False
    if tid == 'alt-edge' and not ctx.get('alt_lines'):
        return False
    if tid == 'next-point' and not next_lines(ctx):
        return False
    return True


# ------------------------------------------------------------------------------------------------------------------------ demonstrations

NOT_PLAY = ('watch', 'end', 'save', 'shot', 'report', 'duel')
COORD = ('walk', 'run', 'jump', 'swim', 'faceat')


def _frame_of(S, W):
    ux, uz = _unit(W[0] - S[0], W[1] - S[1])
    return ux, uz, uz, -ux   # along, then the left (the ladder's left of +z is +x)


def relative_steps(lines, S, W):
    """The steps as offsets from the place S along the heading toward W (a metres along, b metres to the left), or None when one of them is no play (watch, end,
    save, shot ...) or there are none. Steps with no place (wait, roll, raw, advance ...) are kept as they are."""
    ux, uz, lx, lz = _frame_of(S, W)
    rel = lambda x, z: (round((x - S[0]) * ux + (z - S[1]) * uz, 2), round((x - S[0]) * lx + (z - S[1]) * lz, 2))  # noqa: E731
    out = []
    for line in lines:
        w = line.split('#', 1)[0].split()
        if not w:
            continue
        verb = w[0]
        if verb in NOT_PLAY:
            return None
        try:
            if verb in COORD and len(w) >= 3:
                a, b = rel(float(w[1]), float(w[2]))
                out.append({'verb': verb, 'a': a, 'b': b, 'tail': ' '.join(w[3:])})
            elif verb == 'enter' and len(w) >= 3:
                a, b = rel(float(w[1]), float(w[2]))
                e = {'verb': 'enter', 'a': a, 'b': b}
                if 'through' in w and len(w) > w.index('through') + 2:
                    i = w.index('through')
                    e['through'] = list(rel(float(w[i + 1]), float(w[i + 2])))
                    e['tail'] = ' '.join(w[i + 3:])
                else:
                    e['tail'] = ' '.join(w[3:])
                out.append(e)
            else:
                out.append({'verb': verb, 'raw': ' '.join(w)})
        except ValueError:
            out.append({'verb': verb, 'raw': ' '.join(w)})
    return out or None


def absolute_steps(rel, S, W):
    """relative_steps' inverse at another place: S the block, W the target."""
    ux, uz, lx, lz = _frame_of(S, W)
    pt = lambda a, b: (S[0] + a * ux + b * lx, S[1] + a * uz + b * lz)  # noqa: E731
    out = []
    for r in rel:
        if 'raw' in r:
            out.append(r['raw'])
        elif r['verb'] == 'enter':
            x, z = pt(r['a'], r['b'])
            s = f'enter {x:.2f} {z:.2f}'
            if r.get('through'):
                tx, tz = pt(*r['through'])
                s += f' through {tx:.2f} {tz:.2f}'
            out.append((s + ' ' + (r.get('tail') or '')).strip())
        else:
            x, z = pt(r['a'], r['b'])
            out.append((f"{r['verb']} {x:.2f} {z:.2f} " + (r.get('tail') or '')).strip())
    return out


def infer_family(lines, S, W):
    """The tactic a sequence of steps is (the family of a recovery that a journal shows), or None when it is no family: it stays a demonstration."""
    rel = relative_steps(lines, S, W)
    if not rel:
        return None
    first = rel[0]
    v = first['verb']
    raw = first.get('raw', '')
    if v == 'roll':
        return 'roll'
    if v == 'raw':
        if ':X/' in raw and ':A/' not in raw:
            return 'hop'
        if ':A/' in raw and ':X/' not in raw:
            return 'jump-a'
        return None
    if v == 'jump':
        return 'jump'
    if v == 'advance':
        return 'talk-through'
    if v == 'until':
        return 'talk-through' if 'control' in raw and 'press A' in raw else None
    if v == 'interact':
        return 'press-a'
    if v == 'climb':
        return 'climb'
    if v == 'swim':
        return 'swim'
    if v == 'enter':
        return 'door-enter'
    if v == 'wait':
        try:
            n = float(raw.split()[1])
        except (IndexError, ValueError):
            return None
        return 'wait-long' if n >= 8 else 'wait' if n >= 2 else None
    if v in ('walk', 'run') and 'a' in first:
        a, b = first['a'], first['b']
        second = next((r for r in rel[1:] if r['verb'] in ('walk', 'run') and 'a' in r), None)
        if abs(b) <= 1.0 and a <= -1.5 and second is not None:
            if a <= -3.5 and abs(second['b']) <= 1.5 and second['a'] > a:
                return 'run-up'
            da, db = second['a'] - a, second['b'] - b
            if da > 0:
                ang = math.degrees(math.atan2(abs(db), da))
                return 'angle' if 20 <= ang < 55 else 'angle-steep' if ang >= 55 else None
            return None
        if abs(a) <= 2.0 and 1.5 <= abs(b) < 4.5:
            return 'sidestep'
        if abs(a) <= 2.0 and 4.5 <= abs(b) <= 12.0:
            return 'sidestep-wide'
    return None


# ------------------------------------------------------------------------------------------------------------------------ the sensor

class Sensor:
    """The cause of a stuck point and the geometry round it. `world` is what routelib.PrivateWorld answers (persons, doors, props, ground); None: the cause is
    only what the step itself says (held, slow) and the rest is `unknown`. Never raises: a world model that fails is no reason to stop."""

    def __init__(self, world=None):
        self.world = world

    @staticmethod
    def _bucket_persons(n):
        return '0' if n == 0 else '1-2' if n <= 2 else '3+'

    def sense(self, *, map, pos, want=None, result='stuck', verb='run', detail='', moved=None, prompt=None, event=0, target_y=None):
        at = [round(float(c), 2) for c in pos]
        w = self.world
        x, y, z = at
        geom = {}
        if want:
            d = math.hypot(want[0] - x, want[1] - z)
            geom['far'] = 'near' if d < 5.0 else 'mid' if d <= 20.0 else 'far'
        if event:
            geom['event'] = 'yes'
        n5 = None
        if w is not None and map:
            for key, fn in (('persons', lambda: self._bucket_persons(len(w.persons(map, x, z, 5.0)))),
                            ('door', lambda: 'yes' if w.doors(map, x, z, 2.6) else 'no'),
                            ('prop', lambda: 'yes' if w.props(map, x, z, 1.8) else 'no'),
                            ('ahead', lambda: self._ahead(w, map, at, want)),
                            ('climb', lambda: 'yes' if w.climbables(map, x, z, CLIMB_NEAR_M) else 'no')):
                try:
                    val = fn()
                except Exception:   # noqa: BLE001
                    continue
                if val is not None:
                    geom[key] = val
            try:
                n5 = len(w.persons(map, x, z, 5.0))
            except Exception:   # noqa: BLE001
                n5 = None
        cause, why = self._cause(map, at, want, result, verb, detail, moved, event)
        if cause == 'npc-crowd' and n5 is not None and n5 < 3:
            cause = 'npc-in-way'
        if cause in ('wall', 'ledge-up', 'drop-not-taken') and target_y is not None and abs(float(target_y) - y) >= 2.5:
            cause, why = 'other-floor', f'the target is {abs(float(target_y) - y):.1f} m {"above" if target_y > y else "below"} Link: a way to another floor is needed ({why})'
        if cause == 'wall' and 'mesh ends' in why and prompt and re.search(r'dive|swim|water', str(prompt), re.I):
            cause, why = 'water-edge', f'the mesh ends and the prompt reads {prompt!r}: the edge of the water'
        if cause in ('wall', 'ledge-up', 'other-floor') and geom.get('climb') == 'yes':
            near = min(w.climbables(map, x, z, CLIMB_NEAR_M), key=lambda o: math.hypot(o[1] - x, o[2] - z))
            cause, why = 'ledge-up', f'a climbable surface lies {math.hypot(near[1] - x, near[2] - z):.1f} m from the stuck point: climb it ({why})'
        return {'cause': cause, 'why': why, 'geom': geom, 'map': map, 'age': age_of_map(map), 'at': at}

    @staticmethod
    def _ahead(w, map, at, want):
        if not want or not hasattr(w, 'ground'):
            return None
        n = math.hypot(want[0] - at[0], want[1] - at[2])
        if n < 1e-3:
            return None
        g = w.ground(map, at[0] + 1.5 * (want[0] - at[0]) / n, at[2] + 1.5 * (want[1] - at[2]) / n, at[1])
        if g is None:
            return 'none'
        dy = g - at[1]
        return 'up' if dy >= 0.6 else 'drop' if dy <= -1.5 else 'flat'

    def _cause(self, map, at, want, result, verb, detail, moved, event):
        if result == 'held' or event:
            return 'held', 'an event holds Link (a text box or a scene)'
        if self.world is None:
            if result == 'timeout' and (moved or 0) >= 3.0:
                return 'slow', f'the step ran out of time still moving ({moved} m)'
            return 'unknown', 'no world model: the step stopped and nothing more is known'
        try:
            routelib = _routelib()
            return routelib.classify_stuck({'verb': verb, 'result': result, 'detail': detail, 'at': at, 'want': list(want) if want else None, 'moved': moved, 'map': map},
                                           self.world)
        except Exception as e:   # noqa: BLE001
            return 'unknown', f'the cause rules failed ({type(e).__name__})'


def _routelib():
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import routelib
    return routelib


# ------------------------------------------------------------------------------------------------------------------------ the book

def default_dir():
    """The library's folder: $PILOT_TACTICS_DIR, else `tactics/` beside the harness's route library (one library for the dev master and every frozen copy of the code,
    outside git)."""
    d = os.environ.get('PILOT_TACTICS_DIR')
    return Path(d) if d else HERE.parent.parent / 'tactics'


def now_iso():
    return time.strftime('%Y-%m-%dT%H:%M:%S')


def geom_similarity(a, b):
    """The share of the keys both have on which they agree (0 when none is shared)."""
    keys = [k for k in a if k in b and a[k] is not None and b[k] is not None]
    return sum(a[k] == b[k] for k in keys) / len(keys) if keys else 0.0


def _valid(r):
    if not isinstance(r, dict):
        return False
    kind = r.get('kind', 'attempt')
    if kind == 'attempt':
        return bool(r.get('tactic')) and r.get('cause') in CAUSES and r.get('outcome') in OUTCOMES
    if kind == 'demo':
        return bool(r.get('id')) and r.get('cause') in CAUSES and isinstance(r.get('steps'), list) and bool(r['steps'])
    if kind == 'block':
        return r.get('cause') in CAUSES and bool(r.get('map'))
    return False


class Book:
    """The library's file (module doc). Appends are atomic under a lock; reads are cached by the file's stamp, so several processes (the pilot's runs, the
    nightly self-play) can share a folder."""

    def __init__(self, folder=None, strength=STRENGTH, readonly=False):
        """readonly: the library is read (ranking, lessons) and nothing is written to it: the scoreboard's cells must not learn from their own test."""
        self.dir = Path(folder) if folder else default_dir()
        self.path = self.dir / 'book.jsonl'
        self.strength = strength
        self.readonly = readonly
        self._seen = None   # (stamp, rows, keys)
        self._fixed = None  # rows held in memory (from_rows)

    @classmethod
    def from_rows(cls, rows, strength=STRENGTH):
        """A read-only book over rows in memory (the offline evaluation builds one from every run but the one it leaves out)."""
        b = cls(Path(os.devnull), strength)
        b._fixed = [r for r in rows if _valid(r)]
        return b

    # -- the file
    def _stamp(self):
        try:
            st = self.path.stat()
        except OSError:
            return None
        return (st.st_mtime_ns, st.st_size)

    def _load(self):
        if self._fixed is not None:
            return (None, self._fixed, set())
        stamp = self._stamp()
        if self._seen is not None and self._seen[0] == stamp:
            return self._seen
        rows, keys = [], set()
        if stamp is not None:
            try:
                text = self.path.read_text(errors='replace')
            except OSError:
                text = ''
            for ln in text.splitlines():
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if _valid(r):
                    rows.append(r)
                    if r.get('key'):
                        keys.add(r['key'])
        self._seen = (stamp, rows, keys)
        return self._seen

    def rows(self, kind=None):
        rows = self._load()[1]
        return list(rows) if kind is None else [r for r in rows if r.get('kind', 'attempt') == kind]

    def has_key(self, key):
        return key in self._load()[2]

    def has_run(self, run, source=None):
        """Whether the library holds rows of this run (filed under `source`, when given): a run the ladder wrote while it played is not seeded again from its journal."""
        return any(r.get('run') == run and (source is None or r.get('source') == source) for r in self._load()[1])

    def add(self, row):
        """Append a row; False when its key is on file already (a seeding is idempotent) or the book is read-only, ValueError for a row that is no valid row."""
        if self._fixed is not None:
            raise ValueError('a book made from rows in memory is read-only')
        if not _valid(row):
            raise ValueError(f'not a valid row: {str(row)[:120]}')
        if self.readonly:
            return False
        self.dir.mkdir(parents=True, exist_ok=True)
        with open(self.dir / 'book.lock', 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                if row.get('key') and row['key'] in self._load_fresh()[2]:
                    return False
                with open(self.path, 'a') as f:
                    f.write(json.dumps(row, separators=(',', ':')) + '\n')
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
        self._seen = None
        return True

    def _load_fresh(self):
        self._seen = None
        return self._load()

    # -- writing
    def record(self, tactic, cause, outcome, *, map=None, age=None, at=None, geom=None, gain_m=None, source='live', run=None, build=None, block=None, why=None,
               side=None, key=None, ts=None):
        """One attempt: what was tried at a block of this cause, where, and how it came out (worked | failed | neutral: a step that says nothing about ground). The
        row, or None when its key is on file."""
        row = {'v': 1, 'kind': 'attempt', 'ts': ts or now_iso(), 'tactic': tactic, 'cause': cause, 'outcome': outcome, 'map': map, 'age': age or age_of_map(map),
               'at': [round(float(c), 2) for c in at] if at else None, 'geom': dict(geom) if geom else None,
               'gain_m': None if gain_m is None else round(float(gain_m), 2), 'source': source, 'run': run, 'build': build, 'block': block, 'why': why, 'side': side,
               'key': key}
        row = {k: v for k, v in row.items() if v is not None}
        return row if self.add(row) else None

    def add_demo(self, cause, steps, *, map=None, age=None, at=None, run=None, source='demo', key=None, geom=None, build=None, block=None):
        """A way out that worked, kept relative to the place and the heading (`relative_steps`): a tactic of its own (`demo:<hash>`) that replays at another block
        of the same cause. The same steps seen again are the same demonstration (one more win). The demo row."""
        did = 'demo:' + hashlib.sha1((cause + json.dumps(steps, sort_keys=True)).encode()).hexdigest()[:8]
        existing = self.demo(did)
        if existing is None:
            row = {'v': 1, 'kind': 'demo', 'ts': now_iso(), 'id': did, 'cause': cause, 'steps': steps, 'map': map, 'age': age or age_of_map(map),
                   'at': [round(float(c), 2) for c in at] if at else None, 'run': run, 'source': source, 'build': build, 'key': f'{key}:demo' if key else None}
            row = {k: v for k, v in row.items() if v is not None}
            if not self.add(row):
                return self.demo(did)
            existing = row
        self.record(did, cause, 'worked', map=map, age=age, at=at, geom=geom, source=source, run=run, build=build, key=key, block=block)
        return {**existing, 'tactic': did}

    def add_block(self, **fields):
        """A block episode: what stopped Link (cause, place, geometry), what was tried in what order, what finally worked (None: nothing), how it ended."""
        row = {'v': 1, 'kind': 'block', 'ts': fields.pop('ts', None) or now_iso(), **fields}
        row = {k: v for k, v in row.items() if v is not None}
        return row if self.add(row) else None

    # -- reading
    def demos(self, cause=None):
        seen, out = set(), []
        for r in self.rows('demo'):
            if r['id'] in seen or (cause is not None and r['cause'] != cause):
                continue
            seen.add(r['id'])
            out.append(r)
        return out

    def demo(self, did):
        return next((r for r in self.rows('demo') if r['id'] == did), None)

    def counts(self, cause=None):
        """{tactic: {n, wins, fails}} over worked and failed attempts (neutral ones say nothing), for one cause or all."""
        out = {}
        for r in self.rows('attempt'):
            if r['outcome'] == 'neutral' or (cause is not None and r['cause'] != cause):
                continue
            c = out.setdefault(r['tactic'], {'n': 0, 'wins': 0, 'fails': 0})
            c['n'] += 1
            c['wins' if r['outcome'] == 'worked' else 'fails'] += 1
        return out

    @staticmethod
    def weight(row, map=None, age=None, at=None, geom=None):
        """How much an attempt counts for a query: anywhere 0.6, up to 1.0 with the same age and a like geometry, +0.4 on the same map, +2.0 at the same place."""
        w = W_BASE
        if age and row.get('age') == age:
            w += W_AGE
        if geom and row.get('geom'):
            w += W_GEOM * geom_similarity(geom, row['geom'])
        if map and row.get('map') == map:
            w += W_MAP
            ra = row.get('at')
            if at and ra and math.hypot(at[0] - ra[0], at[2] - ra[2]) <= CLUSTER_M and abs(at[1] - ra[1]) < 3.0:
                w += W_CLUSTER
        return w

    @staticmethod
    def prior(cause, tactic):
        return prior(cause, tactic)

    def rank(self, cause, *, map=None, age=None, at=None, geom=None, candidates=None, explore=False):
        """The tactics for a cause, best first: [{tactic, score, prior, n, wins}] (+ `ucb` when exploring). `candidates` restricts to tactics the ladder can try
        here; without them every tactic of the cause's static order, the demonstrations of the cause and any tactic with evidence is ranked."""
        order = ORDER.get(cause, ORDER['unknown'])
        attempts = [r for r in self.rows('attempt') if r['cause'] == cause and r['outcome'] != 'neutral']
        if candidates is None:
            cand = list(order) + [d['id'] for d in self.demos(cause)] + sorted({r['tactic'] for r in attempts})
        else:
            cand = list(candidates)
        cand = list(dict.fromkeys(cand))
        by = {}
        for r in attempts:
            by.setdefault(r['tactic'], []).append(r)
        total = len(attempts)
        K = self.strength
        s_bar = sum(prior(cause, t) for t in order) / len(order)
        scale = ((sum(r['outcome'] == 'worked' for r in attempts) + PRIOR_POOL * s_bar) / (total + PRIOR_POOL)) / s_bar   # 1 with no attempts of this cause: the static order as written
        out = []
        for t in cand:
            p = min(0.9, max(0.03, prior(cause, t) * scale))
            w = nw = 0.0
            n = wins = 0
            for r in by.get(t, ()):
                wt = self.weight(r, map, age, at, geom)
                nw += wt
                n += 1
                if r['outcome'] == 'worked':
                    w += wt
                    wins += 1
            score = (w + p * K) / (nw + K)
            row = {'tactic': t, 'score': score, 'prior': p, 'n': n, 'wins': wins}
            if explore:
                row['ucb'] = score + UCB_C * math.sqrt(math.log(total + 1) / (n + 1))
            out.append(row)
        pos = {t: i for i, t in enumerate(order)}
        out.sort(key=lambda r: (-(r['ucb'] if explore else r['score']), pos.get(r['tactic'], 99), r['tactic']))
        return out

    def summary(self):
        att = self.rows('attempt')
        causes = {}
        for r in att:
            if r['outcome'] == 'neutral':
                continue
            c = causes.setdefault(r['cause'], {}).setdefault(r['tactic'], {'n': 0, 'wins': 0})
            c['n'] += 1
            c['wins'] += r['outcome'] == 'worked'
        sources = {}
        for r in att:
            sources[r.get('source', 'live')] = sources.get(r.get('source', 'live'), 0) + 1
        return {'attempts': len(att), 'blocks': len(self.rows('block')), 'demos': len(self.demos()), 'causes': causes, 'sources': sources}

    def report(self):
        """The library as plain text: per cause the tactics ranked, with their attempts, wins and score."""
        s = self.summary()
        out = [f"tactics library {self.path}: {s['attempts']} attempts, {s['blocks']} blocks, {s['demos']} demonstrations; sources {s['sources']}"]
        for c in CAUSES:
            rank = self.rank(c)
            seen = [r for r in rank if r['n']]
            if not seen:
                continue
            out += ['', f'## {c}', '', '| tactic | attempts | wins | rate | score | prior |', '|---|---|---|---|---|---|']
            for r in rank:
                if r['n']:
                    out.append(f"| {r['tactic']} | {r['n']} | {r['wins']} | {r['wins'] / r['n']:.2f} | {r['score']:.3f} | {r['prior']:.3f} |")
            out.append(f"untried: {', '.join(r['tactic'] for r in rank if not r['n'])}")
        return '\n'.join(out)


def prior(cause, tactic):
    order = ORDER.get(cause, ORDER['unknown'])
    if tactic.startswith('demo:'):
        return PRIOR_DEMO
    if tactic in order:
        return max(PRIOR_FLOOR, PRIOR_TOP - PRIOR_STEP * order.index(tactic))
    return PRIOR_FLOOR


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('report')
    r.add_argument('--dir')
    k = sub.add_parser('rank')
    k.add_argument('cause', choices=CAUSES)
    k.add_argument('--dir')
    a = ap.parse_args(argv)
    book = Book(a.dir)
    if a.cmd == 'report':
        print(book.report())
    else:
        for row in book.rank(a.cause):
            print(f"{row['tactic']:15s} score {row['score']:.3f} prior {row['prior']:.3f} attempts {row['n']} wins {row['wins']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
