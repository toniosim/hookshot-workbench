#!/usr/bin/env python3
"""frontier: push the route library's frontier out. For a target (an issue's place, or a cover of legs) the push starts where the library's walked ground
ends nearest to it (a save made there, or the map's entrance and a closed-loop walk of the library's route), tries the alternatives the stuck cause
suggests one at a time (another angle, the other side, a roll, a jump, a climb, a door, a wait), writes every attempt into the library as it ends, and
then explores toward the target with a fan of probes; the finished run is imported, so the next push starts further on.

    frontier.py plan   --lib L --target NAME ... --out PLAN.json      a hold's plan from the library (saves to make, sessions)
    frontier.py check  PLAN                                            refusals, nothing started
    frontier.py saves  PLAN                                            make the frontier saves (hs_make_save; no game)
    frontier.py run    PLAN --out DIR                                  inside the hold: the sessions, each imported into the library
    frontier.py queue  PLAN [--dry-run]                                ONE waiter: the quiet lock, the measuring lock, `timeout`, `run`
                                                                       (the two lock files are this machine's own: $PILOT_QUIET_LOCK, $PILOT_MEASURING_LOCK; no default)

Library functions (tested game-free in test_frontier.py, with a fake hsap): Attempt/alternatives, Explorer, Push, LiveIO, run_session.
Game-derived data (coordinates, maps) stays in the library and the plan files; nothing here names a place.
"""
import argparse
import json
import math
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import routelib  # noqa: E402

H = Path(os.environ.get('HS_HARNESS', str(HERE.parent.parent)))
SAVE_TOOL = H / 'tools' / 'hs_make_save.py'
QUIET, MEASURING = os.environ.get('PILOT_QUIET_LOCK'), os.environ.get('PILOT_MEASURING_LOCK')   # the main lane's two lock files: this machine's own values, set by the environment, no default
SLOT_VARS = ('HSGATE_SLOT_DIR', 'HSGATE_INTEL_SLOT_DIR', 'HSGATE_SLOT_TEST', 'HSGATE_SLOT_NODESKTOP', 'HSGATE_IN_GATE')
RESERVE_S = 90.0       # a hold ends this long before its timeout: the last session's shutdown and import
SESSION_OVERHEAD_S = 60.0
WORKED_ALONG_M = 4.0   # an attempt worked when Link ends this far past the stuck point along the heading (or 3 m nearer the target than ever)
WORKED_NEARER_M = 3.0


# ------------------------------------------------------------------------------------------------------------------------ geometry

def unit(dx, dz):
    n = math.hypot(dx, dz)
    return (dx / n, dz / n) if n > 1e-9 else (0.0, 1.0)


def rot(u, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (u[0] * c - u[1] * s, u[0] * s + u[1] * c)


def wrap(d):
    return (d + 180.0) % 360.0 - 180.0


def stick_for(camera, dx, dz, mag=1.0, sign=1.0):
    """The left stick (lx, ly) that moves Link toward (dx, dz) as hsap's walk steers: the camera's yaw minus the wanted yaw, right positive."""
    want = wrap(camera - math.degrees(math.atan2(dx, dz))) * sign
    return round(mag * 32767 * math.sin(math.radians(want))), round(mag * 32767 * math.cos(math.radians(want)))


def _p(p):
    return f'{p[0]:.2f} {p[1]:.2f}'


def run_line(p, radius=1.5, timeout=8, extra=''):
    return f'run {_p(p)} radius {radius:g} timeout {timeout}' + (' ' + extra if extra else '')


# ------------------------------------------------------------------------------------------------------------------------ the alternatives

class Attempt:
    """One alternative at a stuck place: a label (stable: the library remembers it), why, and `build(state, ctx)` -> the hsap lines to send."""

    def __init__(self, label, why, builder):
        self.label, self.why, self.builder = label, why, builder

    def build(self, state, ctx):
        return self.builder(state or {}, ctx)


def _geo(ctx):
    at = ctx['at']
    S = (at[0], at[2])
    want = ctx.get('want') or ctx.get('target')
    u = unit(want[0] - S[0], want[1] - S[1])
    perp = (-u[1], u[0])
    return S, want, u, perp


def _shift(side, d):
    def build(state, ctx):
        S, _w, u, perp = _geo(ctx)
        sgn = 1.0 if side == 'L' else -1.0
        P = (S[0] + sgn * d * perp[0], S[1] + sgn * d * perp[1])
        return [run_line(P, 1.5, 8), run_line((P[0] + 10 * u[0], P[1] + 10 * u[1]), 2.0, 10)]
    return Attempt(f'shift-{side}-{d}', f'{d} m to the {"left" if side == "L" else "right"} of the heading, then 10 m along it', build)


def _angle(side, deg):
    def build(state, ctx):
        S, _w, u, _p_ = _geo(ctx)
        v = rot(u, deg if side == 'L' else -deg)
        return [run_line((S[0] - 4 * v[0], S[1] - 4 * v[1]), 1.5, 8), run_line((S[0] + 8 * v[0], S[1] + 8 * v[1]), 2.0, 8)]
    return Attempt(f'angle-{side}-{deg}', f'come at it from {deg} degrees to the {"left" if side == "L" else "right"}', build)


def _roll(state, ctx):
    S, w, u, _p_ = _geo(ctx)
    return [f'faceat {w[0]:.2f} {w[1]:.2f} 20', 'roll up', 'roll up', run_line((S[0] + 6 * u[0], S[1] + 6 * u[1]), 2.0, 8)]


def _press_a(state, ctx):
    S, w, u, _p_ = _geo(ctx)
    return [f'faceat {w[0]:.2f} {w[1]:.2f} 20', 'interact force timeout 4', run_line((S[0] + 6 * u[0], S[1] + 6 * u[1]), 2.0, 8)]


def _jump(state, ctx):
    S, w, u, _p_ = _geo(ctx)
    cam = state.get('camera')
    lx, ly = stick_for(180.0 if cam is None else cam, u[0], u[1])
    return [f'faceat {w[0]:.2f} {w[1]:.2f} 20', f'raw 0:LX={lx}+LY={ly}/1400,0.35:A/100,0.7:A/100 1.6', run_line((S[0] + 6 * u[0], S[1] + 6 * u[1]), 2.0, 8)]


def _climb(state, ctx):
    S, w, u, _p_ = _geo(ctx)
    return [f'faceat {w[0]:.2f} {w[1]:.2f} 20', 'climb timeout 10', run_line((S[0] + 6 * u[0], S[1] + 6 * u[1]), 2.0, 8)]


def _drop_run(state, ctx):
    S, _w, u, _p_ = _geo(ctx)
    return [run_line((S[0] - 4 * u[0], S[1] - 4 * u[1]), 1.5, 6), run_line((S[0] + 6 * u[0], S[1] + 6 * u[1]), 1.5, 6, 'mag 1.0')]


def _wait(s):
    def build(state, ctx):
        S, _w, u, _p_ = _geo(ctx)
        return [f'wait {s}', run_line((S[0] + 8 * u[0], S[1] + 8 * u[1]), 2.5, 10)]
    return Attempt(f'wait-{s}', f'wait {s} s (people move, a scene ends) and go on', build)


def _ring(state, ctx):
    S, _w, u, _p_ = _geo(ctx)
    pts = [(S[0] + 4 * math.cos(a), S[1] + 4 * math.sin(a)) for a in (0.0, math.pi / 2, math.pi, 3 * math.pi / 2)]
    return [run_line(q, 1.5, 6) for q in pts] + [run_line((S[0] + 6 * u[0], S[1] + 6 * u[1]), 2.0, 8)]


def _retreat_wait(state, ctx):
    S, _w, u, _p_ = _geo(ctx)
    return [run_line((S[0] - 12 * u[0], S[1] - 12 * u[1]), 2.0, 10), 'wait 15', run_line((S[0] + 8 * u[0], S[1] + 8 * u[1]), 2.5, 12)]


def _advance(state, ctx):
    S, _w, u, _p_ = _geo(ctx)
    return ['advance timeout 20', run_line((S[0] + 8 * u[0], S[1] + 8 * u[1]), 2.5, 10)]


def _continue(state, ctx):
    w = ctx.get('want') or ctx['target']
    return [run_line(w, 2.5, 25)]


def _door_enter(state, ctx):
    S, _w, u, _p_ = _geo(ctx)
    d = min(ctx['doors'], key=lambda d: math.hypot(d[0] - S[0], d[1] - S[1]))
    return [f'enter {d[0]:.2f} {d[1]:.2f} through {d[0] + 3 * u[0]:.2f} {d[1] + 3 * u[1]:.2f} timeout 25']


def _door_other(state, ctx):
    S, _w, u, _p_ = _geo(ctx)
    d = min(ctx['doors'], key=lambda d: math.hypot(d[0] - S[0], d[1] - S[1]))
    return [run_line((d[0] - 3 * u[0], d[1] - 3 * u[1]), 1.5, 10), f'enter {d[0]:.2f} {d[1]:.2f} through {d[0] + 3 * u[0]:.2f} {d[1] + 3 * u[1]:.2f} timeout 25']


def _simple(label, why, fn):
    return Attempt(label, why, fn)


def _catalogue(ctx):
    """Every attempt that can be made at this place, by label."""
    cat = {}
    for a in [_angle(s, d) for d in (25, 50, 80, 45) for s in 'LR'] + [_shift(s, d) for d in (3, 6, 8, 10) for s in 'LR'] + [_wait(4), _wait(6), _wait(10)]:
        cat[a.label] = a
    for a in (_simple('roll-at', 'face it and roll into it', _roll), _simple('press-a', 'face it and press A at whatever prompt there is', _press_a),
              _simple('jump-a', 'run at it with A tapped (a jump, a grab)', _jump), _simple('climb', 'face it and hold up (a ladder, ivy, a ledge)', _climb),
              _simple('drop-run', 'run at the edge from 4 m back at full push', _drop_run), _simple('ring-4', 'walk a ring of 4 m round the place (a crowd moves)', _ring),
              _simple('retreat-wait', 'go back 12 m, wait 15 s (a boulder, a moving hazard), come on', _retreat_wait), _simple('advance', 'advance the text that holds Link', _advance), _simple('continue', 'carry on to the point (the step only ran out of time)', _continue)):
        cat[a.label] = a
    if ctx.get('doors'):
        cat['door-enter'] = _simple('door-enter', 'enter the nearest door the world model knows, and go through', _door_enter)
        cat['door-other'] = _simple('door-other', 'go to the far side of the door and enter it from there', _door_other)
    return cat


ORDER = {
    'wall': ['angle-L-25', 'angle-R-25', 'shift-L-3', 'shift-R-3', 'shift-L-6', 'shift-R-6', 'shift-L-10', 'shift-R-10', 'angle-L-50', 'angle-R-50', 'jump-a', 'roll-at', 'angle-L-80', 'angle-R-80'],
    'ledge-up': ['climb', 'jump-a', 'press-a', 'roll-at', 'shift-L-3', 'shift-R-3', 'shift-L-8', 'shift-R-8', 'angle-L-25', 'angle-R-25'],
    'drop-not-taken': ['drop-run', 'angle-L-45', 'angle-R-45', 'jump-a', 'roll-at', 'shift-L-3', 'shift-R-3', 'shift-L-8', 'shift-R-8'],
    'door-side': ['door-enter', 'door-other', 'wait-4', 'shift-L-3', 'shift-R-3', 'shift-L-8', 'shift-R-8', 'press-a'],
    'npc-crowd': ['wait-6', 'shift-L-3', 'shift-R-3', 'ring-4', 'wait-10', 'shift-L-6', 'shift-R-6', 'angle-L-25', 'angle-R-25'],
    'held': ['advance', 'wait-6', 'press-a'],
    'slow': ['continue', 'angle-L-25', 'angle-R-25'],
}
ORDER['unknown'] = ORDER['wall']
HURT_QUARTERS = 4      # a heart (4 quarter hearts) lost at a place makes it a hazard; a heart left is a stop


def alternatives(cause, ctx):
    """The attempts for a stuck cause, in order, minus those in ctx['tried'] (labels already made at this place)."""
    cat = _catalogue(ctx)
    tried = set(ctx.get('tried') or ())
    return [cat[l] for l in ORDER.get(cause, ORDER['unknown']) if l in cat and l not in tried]


def attempt_by_label(label, ctx):
    return _catalogue(ctx).get(label)


# ------------------------------------------------------------------------------------------------------------------------ the explorer

FOLLOW_OFFSETS = (90, 120, 60, 150, 30, 180)   # a wall followed: sideways first (along it), then leaning away, then leaning in


class Explorer:
    """Bug-style exploration toward the target from where Link is. GO: probes straight at the target (6 m runs, longer while they go). When one does not
    move Link (under 1.5 m) it FOLLOWs the obstacle: sideways probes along it (90, then 120, 60, 150, 30 degrees off the bearing, on one side), a try
    at the target after each; the side is given up for the other after `flip_after_m` metres with no progress (and the allowance doubles each time, so
    a long wall is not paced back and forth). Ends reached, deadline, probes, trapped (nothing moves Link, either way, and there is nowhere to go
    back to), map-changed, held or cut."""

    def __init__(self, io, *, target, radius=3.0, step_len=6.0, deadline=None, clock=time.monotonic, visited=(), log=None, flip_after_m=45.0, probe_timeout=6, on_block=None):
        self.io, self.target, self.radius, self.step, self.deadline, self.clock = io, (float(target[0]), float(target[1])), radius, step_len, deadline, clock
        self.on_block = on_block   # called with (position, step event) when a straight probe does not move Link: True when something there worked
        self.log = log or (lambda *_: None)
        self.flip_after_m, self.probe_timeout = flip_after_m, probe_timeout

    def _rem(self, x, z):
        return math.hypot(self.target[0] - x, self.target[1] - z)

    def run(self, max_probes=200):
        st = self.io.state() or {}
        map0, pos = st.get('map'), st.get('pos')
        res = {'reached': False, 'stopped': None, 'probes': 0, 'best_remaining': None, 'best_pos': None, 'trail': []}
        if not pos:
            res['stopped'] = 'no-state'
            return res
        best = [self._rem(pos[0], pos[2]), list(pos)]
        history = [list(pos)]
        mode, side, allowance, lateral, block_rem, fails = 'go', 1, self.flip_after_m, 0.0, None, 0
        step = self.step

        def done(why, reached=False):
            res.update(stopped=why, reached=reached, best_remaining=round(best[0], 1), best_pos=best[1])
            return res

        def probe(heading, length, kind):
            nonlocal pos
            dest = (pos[0] + length * heading[0], pos[2] + length * heading[1])
            line = run_line(dest, 1.5, self.probe_timeout)
            ev = self.io.send(line)
            res['probes'] += 1
            p2 = ev.get('pos') or pos
            moved = math.hypot(p2[0] - pos[0], p2[2] - pos[2])
            res['trail'].append({'line': line, 'result': ev.get('result'), 'moved': round(moved, 1), 'pos': p2, 'kind': kind})
            return ev, p2, moved
        while True:
            if self.deadline is not None and self.clock() >= self.deadline:
                return done('deadline')
            if res['probes'] >= max_probes:
                return done('probes')
            st = self.io.state() or {}
            pos = st.get('pos')
            if st.get('map') not in (None, map0):
                return done('map-changed')
            if not pos:
                return done('no-state')
            life = st.get('life')
            if life is not None and life <= HURT_QUARTERS:   # (a heart left: the run is worth more alive; no life at all is a game over)
                return done('dead' if life == 0 else 'life')
            rem = self._rem(pos[0], pos[2])
            if rem < best[0]:
                best = [rem, list(pos)]
            if rem <= self.radius:
                return done('reached', True)
            bearing = unit(self.target[0] - pos[0], self.target[1] - pos[2])
            if mode == 'go':
                ev, p2, moved = probe(bearing, min(step, max(2.0, rem)), 'go')
                if ev.get('result') in ('cut', 'lost', 'held'):
                    return done(ev['result'])
                if moved >= 1.5:
                    history.append(list(p2))
                    step = min(12.0, step + 2.0) if moved >= step - 1.5 else self.step
                    continue
                step = self.step
                if self.on_block is not None and self.on_block(list(p2 or pos), ev):
                    continue
                mode, lateral, block_rem, fails = 'follow', 0.0, rem, 0
                continue
            # follow: along the obstacle on this side, then a try at the target
            moved_any = False
            for off in FOLLOW_OFFSETS:
                if self.deadline is not None and self.clock() >= self.deadline:
                    return done('deadline')
                ev, p2, moved = probe(rot(bearing, off * side), 8.0, 'follow')
                if ev.get('result') in ('cut', 'lost', 'held'):
                    return done(ev['result'])
                if moved >= 3.0:
                    moved_any = True
                    history.append(list(p2))
                    lateral += moved
                    break
                if res['probes'] >= max_probes:
                    return done('probes')
            if not moved_any:
                fails += 1
                side, lateral = -side, 0.0
                if fails >= 2:
                    if len(history) < 3:
                        return done('trapped')
                    back = history[-3]
                    del history[-2:]
                    probe(unit(back[0] - pos[0], back[2] - pos[2]), min(12.0, math.hypot(back[0] - pos[0], back[2] - pos[2])), 'back')
                    mode, fails = 'go', 0
                continue
            fails = 0
            st = self.io.state() or {}
            pos = st.get('pos') or pos
            rem = self._rem(pos[0], pos[2])
            if rem < best[0]:
                best = [rem, list(pos)]
            if block_rem is not None and rem < block_rem - 4.0:
                mode = 'go'
                continue
            if lateral > allowance:
                side, lateral, allowance = -side, 0.0, allowance * 2.0
            if res['probes'] >= max_probes:
                return done('probes')
            bearing = unit(self.target[0] - pos[0], self.target[1] - pos[2])
            ev, p2, moved = probe(bearing, min(5.0, max(2.0, rem)), 'try')
            if ev.get('result') in ('cut', 'lost', 'held'):
                return done(ev['result'])
            if moved >= 3.0:
                history.append(list(p2))
                mode = 'go'


# ------------------------------------------------------------------------------------------------------------------------ the push

class Push:
    """One session's play: the library's route to the frontier (closed loop), the alternatives at the place it stops, then the explorer. For a cover
    target it visits the open stuck clusters instead. Every attempt is written into the library as it ends."""

    def __init__(self, lib, io, *, target, map, world=None, build=None, run=None, deadline=None, log=None, max_attempts=8, expected=None, clock=time.monotonic, max_probes=400, block_attempts=3, cluster_attempts=4,
                 max_total_attempts=16):
        self.lib, self.io, self.name, self.map, self.world, self.build, self.run_id = lib, io, target, map, world, build, run
        self.deadline, self.log, self.max_attempts, self.expected, self.clock, self.max_probes = deadline, log or print, max_attempts, expected, clock, max_probes
        self.block_attempts, self.cluster_attempts, self.max_total_attempts = block_attempts, cluster_attempts, max_total_attempts
        self.blocks_done = set()
        self.attempts, self.recs = [], []
        self.best = None

    def left(self):
        return float('inf') if self.deadline is None else self.deadline - self.clock()

    def _note_best(self, goal):
        st = self.io.state() or {}
        if st.get('pos'):
            r = math.hypot(goal[0] - st['pos'][0], goal[1] - st['pos'][2])
            if self.best is None or r < self.best[0]:
                self.best = (r, list(st['pos']))

    def _walker(self, t, beyond):
        return routelib.Walker(self.lib, self.io, map=self.map, age=t.get('age'), world=self.world, beyond=beyond, build=self.build, run=self.run_id, record=self.recs.append, log=self.log)

    def _ctx(self, cluster, goal):
        at = cluster['at']
        doors = self.world.doors(self.map, at[0], at[2], 12.0) if self.world is not None and hasattr(self.world, 'doors') else []
        return {'at': at, 'want': cluster.get('want') or list(goal), 'target': list(goal), 'doors': [(d[1], d[2], d[3] if len(d) > 3 else 'door') for d in doors],
                'tried': set(cluster.get('tried') or ()), 'map': self.map}

    def _cluster_for(self, pos, goal):
        if pos:
            best = None
            for c in self.lib.map(self.map).clusters():
                d = math.hypot(c['at'][0] - pos[0], c['at'][2] - pos[2])
                if d <= 4.0 and (best is None or d < best[0]):
                    best = (d, c)
            if best:
                return best[1]
        rec = self.recs[-1] if self.recs and pos and math.hypot(self.recs[-1]['at'][0] - pos[0], self.recs[-1]['at'][2] - pos[2]) <= 4.0 else None
        return {'at': list(pos) if pos else [0, 0, 0], 'want': (rec or {}).get('want') or list(goal), 'cause': (rec or {}).get('cause', 'unknown'), 'why': (rec or {}).get('why'), 'tried': [], 'worked': [], 'n': 0,
                'pseudo': True, 'seen_stuck': rec is not None}

    def _return_to(self, at):
        st = self.io.state() or {}
        pos = st.get('pos')
        if pos and math.hypot(pos[0] - at[0], pos[2] - at[2]) > 3.0:
            self.io.send(run_line((at[0], at[2]), 2.0, 12))

    def _attempts(self, cluster, goal, limit=None):
        """Attempts at a place until one works, the list is out or `limit` (else max_attempts) are made; [{label, result, progress_m ...}]."""
        ctx = self._ctx(cluster, goal)
        at = cluster['at']
        S = (at[0], at[2])
        u = unit(ctx['want'][0] - S[0], ctx['want'][1] - S[1])
        order = []
        cat = _catalogue(ctx)
        for lab in cluster.get('worked') or []:     # a way past that worked before is tried first
            if lab in cat and lab not in order:
                order.append(lab)
        order += [a.label for a in alternatives(cluster.get('cause') or 'unknown', ctx) if a.label not in order]
        if cluster.get('hazard') and 'retreat-wait' not in (cluster.get('tried') or ()):   # (hearts were lost here before: back off and wait before coming at it again)
            order.insert(0, 'retreat-wait')
        life0 = (self.io.state() or {}).get('life')
        out = []
        for lab in order[:limit or self.max_attempts]:
            if self.left() < 25.0 or len(self.attempts) >= self.max_total_attempts:
                self.log(f'push: out of time before {lab}')
                break
            self._return_to(at)
            self._note_best(goal)   # (what the walk or the explorer gained getting here is not credited to the attempt)
            st = self.io.state() or {}
            lines = cat[lab].build(st, ctx)
            ev = {}
            for ln in lines:
                ev = self.io.send(ln)
                if ev.get('result') in ('cut', 'lost'):
                    break
            st = self.io.state() or {}
            pos = st.get('pos') or at
            along = (pos[0] - S[0]) * u[0] + (pos[2] - S[1]) * u[1]
            nearer = self.best is not None and math.hypot(goal[0] - pos[0], goal[1] - pos[2]) <= self.best[0] - WORKED_NEARER_M
            worked = along >= WORKED_ALONG_M or nearer
            self._note_best(goal)
            result = 'worked' if worked else 'failed'
            self.lib.record_attempt(self.map, at, lab, result, max(0.0, along), self.build, self.run_id)
            rec = {'at': list(at), 'label': lab, 'result': result, 'progress_m': round(max(0.0, along), 1), 'cause': cluster.get('cause'), 'pos': list(pos)}
            self.attempts.append(rec)
            out.append(rec)
            self.log(f'push: attempt {lab} at {at}: {result} ({along:.1f} m along the heading)')
            if ev.get('result') in ('cut', 'lost') or (st.get('map') not in (None, self.map)):
                break
            if worked:
                break
            life = st.get('life')
            if life is not None and life0 is not None and (life0 - life >= HURT_QUARTERS or life <= HURT_QUARTERS):
                self.log(f'push: hearts are being lost at {at} (life {life0} -> {life}): no more attempts there')
                break
        return out

    def run(self):
        t = self.lib.targets().get(self.name)
        if t is None:
            raise routelib.LibError(f'no target {self.name!r}')
        st = self.io.state() or {}
        res = {'ok': False, 'stopped': None, 'mode': 'clusters' if t['kind'] == 'cover' else 'target', 'target': self.name, 'map': self.map, 'attempts': self.attempts, 'walker': None,
               'explore': None, 'clusters': [], 'best_remaining_m': None, 'best_pos': None, 'start': None}
        if st.get('map') not in (None, self.map):
            res['stopped'] = 'wrong-map'
            res['start'] = {'live_map': st.get('map'), 'expected_map': self.map}
            return res
        f = self.lib.frontier(self.name)
        expected = self.expected if self.expected is not None else (f.get('pos') if f.get('known') else None)
        pos = st.get('pos')
        res['start'] = {'expected': expected, 'live': pos, 'dist_m': round(math.hypot(expected[0] - pos[0], expected[2] - pos[2]), 1) if expected and pos else None}
        if t['kind'] == 'point' and f.get('known'):   # (a point is only nearer when it beats the library's own frontier, not where Link happens to stand)
            self.best = (f['remaining_m'], list(f['pos']))
        try:
            if t['kind'] == 'cover':
                return self._clusters(t, res)
            return self._target(t, res)
        finally:
            if self.best:
                res['best_remaining_m'], res['best_pos'] = round(self.best[0], 1), self.best[1]

    def _target(self, t, res):
        goal = (t['x'], t['z'])
        self._note_best(goal)
        r = self._walker(t, True).go(goal, t.get('y'), goal_radius=t['radius'])
        res['walker'] = {k: r.get(k) for k in ('stopped', 'replans', 'drifts', 'sent', 'pos', 'blocked_at')}
        self._note_best(goal)
        if r['stopped'] == 'reached':
            res.update(ok=True, stopped='reached')
            return res
        if r['stopped'] in ('map-changed', 'cut', 'no-state', 'held'):
            res['stopped'] = r['stopped']
            return res
        cluster = self._cluster_for(r.get('blocked_at') or r.get('pos'), goal)
        res['cluster'] = {k: cluster.get(k) for k in ('at', 'cause', 'why', 'n', 'tried', 'worked')}
        if self.left() >= 25.0 and not (cluster.get('pseudo') and not cluster.get('seen_stuck')):   # (the end of the known route is no stuck place: the explorer meets the blocks)
            self._attempts(cluster, goal)
        if self.left() < 10.0:
            res['stopped'] = 'deadline'
            return res
        g = self.lib.map(self.map).graph()
        ex = Explorer(self.io, target=goal, radius=t['radius'], deadline=self.deadline, clock=self.clock, visited=[(n.x, n.z) for n in g.nodes], log=self.log,
                      on_block=lambda pos, ev: self._block_hook(pos, ev, goal))
        er = ex.run(max_probes=self.max_probes)
        res['explore'] = {k: er[k] for k in ('reached', 'stopped', 'probes', 'best_remaining', 'best_pos')}
        res['explore']['trail'] = er['trail'][-60:]
        self._note_best(goal)
        if er['best_remaining'] is not None and (self.best is None or er['best_remaining'] < self.best[0]):
            self.best = (er['best_remaining'], er['best_pos'])
        res.update(ok=bool(er['reached']), stopped='reached' if er['reached'] else er['stopped'])
        return res

    def _block_hook(self, pos, ev, goal):
        """The explorer's straight probe did not move Link: classify the block as a stuck step is, try a few of the alternatives its cause suggests (once per 4 m cell)."""
        key = (round(pos[0] / 4.0), round(pos[2] / 4.0))
        if key in self.blocks_done or self.left() < 25.0 or len(self.attempts) >= self.max_total_attempts:
            return False
        self.blocks_done.add(key)
        rec = routelib.stuck_from_event(dict(ev, pos=pos, result=ev.get('result') or 'stuck'), self.map, self.build, self.run_id, self.world)
        rec['want'] = list(goal)
        self.recs.append(rec)
        out = self._attempts({'at': list(pos), 'want': list(goal), 'cause': rec['cause'], 'why': rec['why'], 'tried': [], 'worked': [], 'n': 0}, goal, limit=self.block_attempts)
        return any(a['result'] == 'worked' for a in out)

    def _clusters(self, t, res):
        clusters = sorted((c for c in self.lib.map(self.map).clusters() if not c['resolved']), key=lambda c: -c['n'])   # (the places that stopped most runs first)
        goal = (t['points'][0][0], t['points'][0][1]) if t['points'] else (0.0, 0.0)
        for c in clusters:
            if self.left() < 40.0:
                res['stopped'] = 'deadline'
                break
            r = self._walker(t, False).go((c['at'][0], c['at'][2]), goal_radius=3.0)
            row = {'at': c['at'], 'cause': c['cause'], 'n': c['n'], 'walker': r['stopped'], 'attempts': [], 'worked': []}
            res['clusters'].append(row)
            if r['stopped'] in ('map-changed', 'cut', 'no-state'):
                res['stopped'] = r['stopped']
                break
            if r['stopped'] not in ('reached', 'frontier'):
                continue
            want = c.get('want') or list(goal)
            out = self._attempts(dict(c, want=want), (want[0], want[1]), limit=self.cluster_attempts)
            row['attempts'] = out
            row['worked'] = [a['label'] for a in out if a['result'] == 'worked']
            self._return_to(c['at'])
        res['ok'] = any(c['worked'] for c in res['clusters'])
        self._legs(t, res)
        res['stopped'] = res['stopped'] or ('done' if res['clusters'] else 'no-open-clusters')
        return res

    def _legs(self, t, res):
        """The legs the library had not walked, nearest first from where Link is: the library's way and the world model's plan, closed loop; each leg's end is recorded."""
        res['legs'], res['legs_tried'], res['legs_reached'] = [], 0, 0
        left = [list(p) for p in (self.lib.frontier(self.name).get('unreached') or [])]
        while left and self.left() >= 30.0 and res['stopped'] in (None, 'done'):
            pos = (self.io.state() or {}).get('pos')
            if not pos:
                break
            leg = min(left, key=lambda p: math.hypot(p[0] - pos[0], p[1] - pos[2]))
            left.remove(leg)
            r = self._walker(t, True).go((leg[0], leg[1]), goal_radius=t['radius'])
            tried = []
            if r['stopped'] == 'blocked' and self.left() >= 30.0:   # (a new block on the way to a leg: the alternatives its cause suggests, then the leg again)
                tried = self._attempts(self._cluster_for(r.get('blocked_at') or r.get('pos'), leg), (leg[0], leg[1]), limit=self.max_attempts)
                if any(a['result'] == 'worked' for a in tried):
                    r = self._walker(t, True).go((leg[0], leg[1]), goal_radius=t['radius'])
            res['legs'].append({'leg': leg, 'stopped': r['stopped'], 'pos': r.get('pos'), 'attempts': tried})
            res['legs_tried'] += 1
            res['legs_reached'] += r['stopped'] == 'reached'
            if r['stopped'] in ('map-changed', 'cut', 'no-state'):
                res['stopped'] = r['stopped']
            life = (self.io.state() or {}).get('life')
            if life is not None and life <= HURT_QUARTERS:
                res['stopped'] = 'dead' if life == 0 else 'life'


# ------------------------------------------------------------------------------------------------------------------------ the live side

def spawn(cmd, env=None, log=None):
    out = open(log, 'w') if log else subprocess.DEVNULL
    return subprocess.Popen([str(c) for c in cmd], stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env, start_new_session=True)


def stop_pid(pid, grace=15.0):
    """SIGTERM the process group of pid, then SIGKILL after the grace (by pid only: never by name)."""
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    end = time.time() + grace
    while time.time() < end:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        try:
            done, _ = os.waitpid(pid, os.WNOHANG)
            if done:
                return
        except ChildProcessError:
            pass
        time.sleep(0.1)
    try:
        os.killpg(os.getpgid(pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


class LiveIO:
    """The pilot's channel to a running hsap: steps appended to <live>/steps.txt, events read from <live>/out.jsonl. `send(line)` returns the step event
    (and reads the state event that follows it); `state()` is the newest state (position, map, camera, event, loading, prompt...)."""

    def __init__(self, live, alive=lambda: True, poll=0.03):
        self.live, self.alive, self.poll = Path(live), alive, poll
        self.live.mkdir(parents=True, exist_ok=True)
        self.steps, self.out = self.live / 'steps.txt', self.live / 'out.jsonl'
        self.steps.touch()
        self.n_lines = len(self.steps.read_text().splitlines())
        self.off, self.buf, self.st, self.events = 0, b'', {}, []

    def _read(self):
        if not self.out.exists():
            return []
        with open(self.out, 'rb') as f:
            f.seek(self.off)
            data = f.read()
        self.off += len(data)
        self.buf += data
        *whole, self.buf = self.buf.split(b'\n')
        new = []
        for line in whole:
            try:
                e = json.loads(line.decode('utf-8', 'replace'))
            except ValueError:
                continue
            new.append(e)
            if e.get('ev') == 'state':
                self.st = {'map': e.get('area'), 'pos': e.get('pos'), 'camera': e.get('camera'), 'facing': e.get('facing'), 'event': e.get('event'), 'loading': e.get('loading'),
                           'prompt': e.get('prompt'), 'life': e.get('life'), 'child': e.get('child'), 't': e.get('t')}
        self.events = (self.events + new)[-400:]
        return new

    def state(self):
        self._read()
        return dict(self.st)

    def wait_gameplay(self, timeout):
        end = time.time() + timeout
        seen = False
        while time.time() < end:
            for e in self._read():
                seen = seen or e.get('ev') == 'gameplay'
                if seen and e.get('ev') == 'state' and e.get('why') == 'wait':
                    return dict(self.st)
            if not self.alive():
                for e in self._read():
                    seen = seen or e.get('ev') == 'gameplay'
                return dict(self.st) if (seen and self.st) else None
            time.sleep(self.poll)
        return None

    def send(self, line, timeout=None):
        with open(self.steps, 'a') as f:
            f.write(line + '\n')
        self.n_lines += 1
        n = self.n_lines
        w = line.split()
        if timeout is None:
            if 'timeout' in w:
                timeout = float(w[w.index('timeout') + 1]) + 40.0
            elif w[0] == 'wait' and len(w) > 1:
                timeout = float(w[1]) + 30.0
            else:
                timeout = 60.0
        end = time.time() + timeout
        got = None
        while time.time() < end:
            for e in self._read():
                if e.get('ev') == 'step' and e.get('in') == n:
                    got = e
                elif e.get('ev') == 'bad' and e.get('in') == n:
                    got = {'ev': 'step', 'in': n, 'src': line, 'result': 'bad', 'detail': e.get('why') or e.get('text') or '', 'pos': (self.st or {}).get('pos')}
                elif got is not None and e.get('ev') == 'state' and e.get('why') == 'wait':
                    return got
            if got is not None and not self.alive():
                return got
            if not self.alive():
                self._read()
                break
            time.sleep(self.poll)
        if got is not None:
            return got
        return {'ev': 'step', 'in': n, 'src': line, 'result': 'lost', 'detail': 'no answer from the game side', 'pos': (self.st or {}).get('pos')}


def _env_for_game(env=None):
    e = dict(env if env is not None else os.environ)
    for k in SLOT_VARS:
        e.pop(k, None)
    e.pop('OPENAI_API_KEY', None)
    return e


def warp_to(sess, game_run, env, placer=None, entrance=False):
    """The warp to the session's start point through the placer ({ok, warp: {ok}, error}); with entrance=True only the harness's own placement at the map's
    entrance (the age, the hour), no coordinates. Never raises: {ok, warped, error}."""
    spec = {'to': sess['map'], 'age': sess.get('age'), **({'hour': sess['hour']} if sess.get('hour') is not None else {})}
    if not entrance:
        p = sess['start']['pos']
        spec.update(x=p[0], y=p[1], z=p[2])
    try:
        if placer is None:
            import placement
            placer = placement.apply
        res = placer(spec, str(game_run), env=env) or {}
    except Exception as e:   # noqa: BLE001  (no hsdebug, no !place, a game that did not answer: the walk follows)
        return {'ok': False, 'warped': False, 'error': f'{type(e).__name__}: {e}'[:200]}
    return {'ok': bool(res.get('ok')), 'warped': bool((res.get('warp') or {}).get('ok')), 'error': res.get('error')}


def run_session(sess, lib, *, copy, hsap, out, world=None, env=None, deadline=None, log=print, boot_s=240.0, clock=time.monotonic, placer=None):
    """One game: hsap through the gate from a save, the push, end, the run's journals kept under out/<name>/, the run imported into the library.
    With `warp` in the session the frontier point is asked of the placer (placement.apply: hsdebug's warp) after gameplay; a build without the warp is no
    failure, the push walks from where Link is. Returns the row {name, tag, status, warp, push, import, seconds}. status: done | no-gameplay | refused."""
    t0 = time.time()
    name, tag = sess['name'], sess['tag']
    copy = Path(copy)
    row = {'name': name, 'tag': tag, 'target': sess['target'], 'map': sess['map'], 'status': 'pending', 'started': time.strftime('%F %T')}
    live = Path(out) / name / 'pilot' / 'live'
    if live.exists():
        row['status'] = 'refused: the output folder already has this session'
        return row
    game_run = copy / 'runs' / tag
    if game_run.is_symlink():
        game_run.unlink()
    elif game_run.exists():
        shutil.rmtree(game_run)
    live.mkdir(parents=True)
    wall = int(sess['wall'])
    cmd = [sys.executable, '-I', '-B', hsap, str(copy), tag, str(wall), '--live', str(live), '--boot', 'continue', '--shots', str(sess.get('shots', 120)), '--analog']
    if sess.get('save'):
        cmd += ['--save', str(sess['save'])]
    t_spawn = clock()
    log(f'session {name}: {" ".join(shlex.quote(str(c)) for c in cmd)}')
    proc = spawn(cmd, env=_env_for_game(env), log=Path(out) / name / 'hsap.out')
    io = LiveIO(live, alive=lambda: proc.poll() is None)
    push = res = None
    try:
        st = io.wait_gameplay(boot_s)
        if not st:
            row['status'] = 'no-gameplay'
            log(f'session {name}: no gameplay ({"hsap ended" if proc.poll() is not None else "boot timeout"})')
            return row
        row['gameplay'] = {'map': st.get('map'), 'pos': st.get('pos')}
        if sess.get('warp'):
            row['warp'] = warp_to(sess, game_run, env, placer)
            io.send('wait 0.5', timeout=30)   # (a state line that came after the warp)
            log(f'session {name}: warp {row["warp"]}')
        elif sess.get('place') or st.get('map') != sess['map']:   # (the save did not put Link on the map: the harness's own placement at its entrance; the walk follows)
            row['place'] = warp_to(sess, game_run, env, placer, entrance=True)
            io.send('wait 0.5', timeout=30)
            log(f'session {name}: placed at the map\'s entrance {row["place"]}')
        d = min(clock() + float(sess.get('budget_s', wall - 100)), t_spawn + wall - 25.0)   # (hsap ends the game at its wall, boot included)
        if deadline is not None:
            d = min(d, deadline)
        push = Push(lib, io, target=sess['target'], map=sess['map'], world=world, build=None, run=f'{tag}', deadline=d, log=log, max_attempts=int(sess.get('max_attempts', 8)),
                    expected=sess.get('expected'), clock=clock, block_attempts=int(sess.get('block_attempts', 3)), cluster_attempts=int(sess.get('cluster_attempts', 4)),
                    max_total_attempts=int(sess.get('max_total_attempts', 16)))
        res = push.run()
        row['push'] = res
        row['status'] = 'done'
    finally:
        if proc.poll() is None:
            try:
                io.send('end', timeout=25)
            except Exception:   # noqa: BLE001  (the game may already be gone: stop it below)
                pass
            end = time.time() + 40
            while proc.poll() is None and time.time() < end:
                time.sleep(0.2)
            if proc.poll() is None:
                log(f'session {name}: stopping hsap pid {proc.pid}')
                stop_pid(proc.pid)
        gdst = Path(out) / name / 'game'
        gdst.mkdir(parents=True, exist_ok=True)
        if game_run.is_dir():
            for fn in ('summary.txt', 'exit.txt', 'wall.txt', 'args.txt', 'env-used.txt', 'kernel.txt', 'kernel-status.json') + routelib.LOG_NAMES:
                if (game_run / fn).is_file():
                    shutil.copy2(game_run / fn, gdst / fn)
            if (game_run / 'shots').is_dir():
                shutil.copytree(game_run / 'shots', gdst / 'shots', dirs_exist_ok=True)
        row['seconds'] = round(time.time() - t0, 1)
        if row['status'] == 'done':
            try:
                row['import'] = lib.import_run(Path(out) / name, label=f'{Path(out).name}-{name}', world=world)
            except routelib.LibError as e:
                row['import_error'] = str(e)
    return row


# ------------------------------------------------------------------------------------------------------------------------ the plan and the hold

def calm_start(lib, map, pos, world, within=12.0):
    """The library point nearest `pos` (reachable from an anchor, within `within` m) with no person within 3 m, no door or placed object within 2.5 m: the boot presses A every 2 s
    until the game is calm, and A at a prompt starts a talk that holds Link (the Castle Town save made beside a person never reached play in 240 s)."""
    m = lib.map(map)
    g, _srcs, reach = lib._anchored_nodes(m)

    def calm(n):
        if world.persons(map, n.x, n.z, 3.0) or world.doors(map, n.x, n.z, 2.5):
            return False
        return not (hasattr(world, 'props') and world.props(map, n.x, n.z, 1.5))
    cands = sorted((math.hypot(g.nodes[i].x - pos[0], g.nodes[i].z - pos[2]), i) for i in reach if abs(g.nodes[i].y - pos[1]) <= 2.0)
    for d, i in cands:
        if d > within:
            break
        if calm(g.nodes[i]):
            return g.nodes[i].pos
    return list(pos)


def make_session(lib, target, *, name, wall, budget_s, tag, save_name, base_save, copy, shots=120, max_attempts=8, time_of_day='day', world=None):
    """A session dict that starts at the library's frontier for the target: the point, a yaw toward what the nearest stuck place wanted, the save to make."""
    t = lib.targets()[target]
    f = lib.frontier(target)
    if not f.get('known'):
        raise routelib.LibError(f'target {target}: the library has no anchored track on {t["map"]} yet: nothing to start from')
    pos = f['pos']
    m = lib.map(t['map'])
    first_pos = list(pos)
    cl = min(((math.hypot(c['at'][0] - pos[0], c['at'][2] - pos[2]), c) for c in m.clusters() if not c['resolved']), key=lambda x: x[0], default=(None, None))[1]
    if t['kind'] == 'cover':
        cl = max((c for c in m.clusters() if not c['resolved']), key=lambda c: c['n'], default=cl)   # (the place that stopped most runs: the push visits it first)
        if cl:
            pos = cl['at']
            first_pos = list(pos)
    if world is not None:
        pos = calm_start(lib, t['map'], pos, world)
    want = (cl.get('want') if cl and cl.get('want') else None) or ([t['x'], t['z']] if t['kind'] == 'point' else f.get('nearest_leg') or [pos[0], pos[2] + 1])
    yaw = math.atan2(want[0] - pos[0], want[1] - pos[2])
    return {'name': name, 'target': target, 'map': t['map'], 'age': t.get('age') or routelib.age_of_map(t['map']) or 'child', 'wall': wall, 'budget_s': budget_s, 'tag': tag, 'shots': shots,
            'max_attempts': max_attempts, 'save_name': save_name, 'base_save': base_save, 'retry_save': str(H / 'saves' / base_save), 'hour': 12, 'copy': str(copy), 'time': time_of_day,
            'expected': [round(c, 2) for c in pos],
            'start': {'pos': [round(c, 2) for c in pos], 'yaw': round(yaw, 3), 'want': want, 'moved_m': round(math.hypot(pos[0] - first_pos[0], pos[2] - first_pos[2]), 2)}}


def save_command(sess, saves_dir, game):
    """The hs_make_save command that makes the session's save: the base save moved to the frontier point (map:x,y,z,yaw), the age, the time of day."""
    p = sess['start']['pos']
    return [sys.executable, str(SAVE_TOOL), '--from', sess['base_save'], '--out', str(Path(saves_dir) / sess['save_name']), '--start', f'{sess["map"]}:{p[0]:.2f},{p[1]:.2f},{p[2]:.2f},{sess["start"]["yaw"]:.3f}',
            '--age', sess['age'], '--time', sess.get('time', 'day'), '--game', str(game)]


class PlanError(Exception):
    pass


def load_plan(path):
    path = Path(path)
    try:
        p = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        raise PlanError(f'{path}: {e}')
    p['plan_path'] = str(path)
    p.setdefault('hold_seconds', 1100)
    p.setdefault('world', None)
    p.setdefault('sessions', [])
    return p


def plan_errors(plan, out=None):
    errs = []
    try:
        lib = routelib.RouteLib(plan['lib'])
        targets = lib.targets()
    except (KeyError, routelib.LibError) as e:
        return [f'library: {e}']
    names, tags = set(), set()
    total = 0.0
    for s in plan['sessions']:
        for k in ('name', 'target', 'map', 'wall', 'tag'):
            if k not in s:
                errs.append(f'session {s.get("name")}: {k} is missing')
        if s.get('name') in names:
            errs.append(f'duplicate session name {s.get("name")}')
        if s.get('tag') in tags:
            errs.append(f'duplicate session tag {s.get("tag")}')
        names.add(s.get('name'))
        tags.add(s.get('tag'))
        if s.get('target') not in targets:
            errs.append(f'session {s.get("name")}: target {s.get("target")!r} is not in the library')
        elif targets[s['target']]['map'] != s.get('map'):
            errs.append(f'session {s.get("name")}: target is on {targets[s["target"]]["map"]}, not {s.get("map")}')
        if s.get('save') and not Path(s['save']).is_dir():
            errs.append(f'session {s.get("name")}: save {s["save"]} is not a folder (frontier.py saves makes it)')
        total += float(s.get('wall', 0)) + SESSION_OVERHEAD_S
    if total > plan['hold_seconds'] - RESERVE_S:
        errs.append(f'the sessions need {total:.0f} s with their overhead; the hold has {plan["hold_seconds"] - RESERVE_S:.0f} s: they do not fit the hold')
    if not Path(plan.get('copy', '')).is_dir():
        errs.append(f'copy {plan.get("copy")} is not a folder')
    if not Path(plan.get('hsap', '')).is_file():
        errs.append(f'hsap {plan.get("hsap")} is not a file')
    if out is not None and Path(out).exists():
        errs.append(f'{out} exists (a hold writes a new folder)')
    return errs


def queue_command(plan_path, plan, out, quiet=None, measuring=None):
    quiet, measuring = quiet or QUIET, measuring or MEASURING
    if not (quiet and measuring):
        raise ValueError('the waiter needs the main lane\'s lock files: set PILOT_QUIET_LOCK and PILOT_MEASURING_LOCK (this machine\'s own values; there is no default)')
    return ['setsid', 'env', '--default-signal=HUP', 'flock', '-w', '43200', quiet, 'flock', '-x', measuring, 'timeout', '--signal=TERM', '--kill-after=20', str(int(plan['hold_seconds'])),
            sys.executable, '-I', '-B', str(HERE / 'frontier.py'), 'run', str(plan_path), '--out', str(out)]


class Terminated(BaseException):
    pass


def run_hold(plan, out, log=print):
    out = Path(out)
    out.mkdir(parents=True)
    lib = routelib.RouteLib(plan['lib'])
    world = routelib.PrivateWorld(plan['world']) if plan.get('world') else None
    t0 = time.monotonic()
    hold_end = t0 + plan['hold_seconds'] - RESERVE_S
    rows = []

    def on_term(signum, frame):
        raise Terminated(signum)
    signal.signal(signal.SIGTERM, on_term)
    signal.signal(signal.SIGHUP, on_term)

    def flush():
        (out / 'result.json').write_text(json.dumps({'name': plan['name'], 'started': time.strftime('%F %T'), 'rows': rows}, indent=1, default=str))
    try:
        for s in plan['sessions']:
            left = hold_end - time.monotonic()
            if left < 150:
                rows.append({'name': s['name'], 'status': f'not started: {left:.0f} s left of the hold'})
                flush()
                continue
            s = dict(s, wall=min(float(s['wall']), left - 40))
            s['budget_s'] = min(float(s.get('budget_s', s['wall'] - 100)), s['wall'] - 100)
            row = run_session(s, lib, copy=plan['copy'], hsap=plan['hsap'], out=out, world=world, deadline=hold_end, log=log, boot_s=float(plan.get('boot_s', 240)))
            rows.append(row)
            flush()
            left = hold_end - time.monotonic()
            if row['status'] == 'no-gameplay' and s.get('retry_save') and left >= 240:   # (a game that cannot start from a save made at a point: the base save, placed at the entrance)
                r2 = dict(s, name=s['name'] + '-retry', tag=s['tag'] + 'r', save=s['retry_save'], place=True, warp=False, retry_save=None, wall=min(float(s['wall']), left - 40))
                r2['budget_s'] = min(float(s.get('budget_s', r2['wall'] - 100)), r2['wall'] - 100)
                rows.append(run_session(r2, lib, copy=plan['copy'], hsap=plan['hsap'], out=out, world=world, deadline=hold_end, log=log, boot_s=float(plan.get('boot_s', 240))))
                flush()
    except Terminated:
        rows.append({'name': 'hold', 'status': 'stopped by a signal'})
        flush()
        return 143
    flush()
    return 0


def write_table(out, plan, rows):
    lines = [f'# {plan["name"]}', '', '| session | target | status | stopped | attempts (worked) | best remaining m | imported | frontier gain m |', '|---|---|---|---|---|---|---|---|']
    for r in rows:
        p = r.get('push') or {}
        a = p.get('attempts') or []
        imp = r.get('import') or {}
        lines.append(f'| {r.get("name")} | {r.get("target")} | {r.get("status")} | {p.get("stopped")} | {len(a)} ({sum(1 for x in a if x["result"] == "worked")}) | {p.get("best_remaining_m")} | '
                     f'{imp.get("metres")} m, {imp.get("new_edges")} new edges | {imp.get("frontier_gain")} |')
    (Path(out) / 'table.md').write_text('\n'.join(lines) + '\n')


# ------------------------------------------------------------------------------------------------------------------------ the command line

def cmd_check(a):
    plan = load_plan(a.plan)
    errs = plan_errors(plan, a.out)
    for e in errs:
        print('refused:', e)
    print(f'{plan["name"]}: {len(plan["sessions"])} sessions, hold {plan["hold_seconds"]} s' + ('' if errs else ': ok'))
    return 2 if errs else 0


def cmd_saves(a):
    plan = load_plan(a.plan)
    saves = Path(plan['saves_dir'])
    lib = routelib.RouteLib(plan['lib'])
    for s in plan['sessions']:
        if not s.get('save_name'):
            continue
        dest = saves / s['save_name']
        if dest.exists():
            print(f'{s["name"]}: {dest} exists, kept')
            continue
        cmd = save_command(s, saves, plan['copy'])
        print(' '.join(shlex.quote(c) for c in cmd))
        r = subprocess.run(cmd, capture_output=True, text=True)
        print(r.stdout[-600:], r.stderr[-600:])
        if r.returncode:
            print(f'{s["name"]}: hs_make_save failed ({r.returncode})')
            return r.returncode
        lib.add_anchor(s['map'], s['start']['pos'], kind='save', name=s['save_name'])
    return 0


def cmd_run(a):
    plan = load_plan(a.plan)
    errs = plan_errors(plan, a.out)
    if errs:
        for e in errs:
            print('refused:', e, file=sys.stderr)
        return 2
    rc = run_hold(plan, a.out)
    try:
        rows = json.loads((Path(a.out) / 'result.json').read_text())['rows']
        write_table(a.out, plan, rows)
    except (OSError, ValueError):
        pass
    return rc


def cmd_queue(a):
    plan = load_plan(a.plan)
    out = Path(a.out) if a.out else Path(plan['plan_path']).parent / 'sessions' / plan['name']
    errs = plan_errors(plan, out)
    try:
        cmd = queue_command(plan['plan_path'], plan, out)
        print('command: ' + ' '.join(shlex.quote(c) for c in cmd))
    except ValueError as e:
        cmd = None
        errs.append(str(e))
    others = subprocess.run(['pgrep', '-u', str(os.getuid()), '-f', r'PathLib.*frontier\.py run '], capture_output=True, text=True).stdout.split()
    others = [p for p in others if int(p) not in (os.getpid(), os.getppid())]
    if errs or others:
        for e in errs:
            print('refusing:', e)
        if others:
            print(f'refusing: a waiter of mine is queued (pid {" ".join(others)}): one at a time')
        return 2
    if a.dry_run:
        print('dry run: nothing started')
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    log = open(out.parent / (plan['name'] + '.launcher.log'), 'w')
    p = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, cwd=str(Path(plan['plan_path']).parent))
    (out.parent / (plan['name'] + '.pid')).write_text(f'{p.pid}\n')
    print(f'launcher pid {p.pid}')
    return 0


def cmd_plan(a):
    lib = routelib.RouteLib(a.lib)
    sessions = []
    for i, spec in enumerate(a.session):
        target, base, wall = spec.split(',')[:3]
        s = make_session(lib, target, name=f'{target}', wall=int(wall), budget_s=int(wall) - 100, tag=f'PathLib-{a.name}-{i + 1}', save_name=f'pathlib-{a.name}-{target}', base_save=base, copy=a.copy)
        if a.warp:
            s['warp'] = True
        sessions.append(s)
    plan = {'name': a.name, 'lib': str(a.lib), 'copy': a.copy, 'hsap': a.hsap, 'hold_seconds': a.hold_seconds, 'world': a.world, 'saves_dir': a.saves_dir, 'boot_s': 240, 'sessions': sessions}
    for s in sessions:
        s['save'] = str(Path(a.saves_dir) / s['save_name'])
    Path(a.out).write_text(json.dumps(plan, indent=1))
    print(f'plan {a.out}: {len(sessions)} sessions')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('plan')
    p.add_argument('--lib', required=True)
    p.add_argument('--name', required=True)
    p.add_argument('--session', action='append', required=True, metavar='TARGET,BASE_SAVE,WALL')
    p.add_argument('--copy', required=True)
    p.add_argument('--hsap', required=True)
    p.add_argument('--world')
    p.add_argument('--warp', action='store_true', help='ask the placer (hsdebug warp: a build with !place) for the frontier point after boot; the walk is the fallback')
    p.add_argument('--saves-dir', dest='saves_dir', required=True)
    p.add_argument('--hold-seconds', dest='hold_seconds', type=int, default=1100)
    p.add_argument('--out', required=True)
    p.set_defaults(fn=cmd_plan)
    p = sub.add_parser('check')
    p.add_argument('plan')
    p.add_argument('--out')
    p.set_defaults(fn=cmd_check)
    p = sub.add_parser('saves')
    p.add_argument('plan')
    p.set_defaults(fn=cmd_saves)
    p = sub.add_parser('run')
    p.add_argument('plan')
    p.add_argument('--out', required=True)
    p.set_defaults(fn=cmd_run)
    p = sub.add_parser('queue')
    p.add_argument('plan')
    p.add_argument('--out')
    p.add_argument('--dry-run', action='store_true')
    p.set_defaults(fn=cmd_queue)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == '__main__':
    raise SystemExit(main())
