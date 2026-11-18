#!/usr/bin/env python3
"""Game-free checks of hsap_actions.py (the movement, combat and shop steps of hsap.Executor) on test_hsap.py's simulated
protocol-1 bridge. ActionBridge adds invented physics (a jump, a gap, a ledge, water, a block, a ladder, a lock-on, a horse, a
shop); every name and number here is an invented fixture. No game, no GPU, no network, no wall-clock sleeps.

    python3 -I -B test_hsap_actions.py
"""
import contextlib
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_hsap as T  # noqa: E402  (its main() runs only as a script)
import hsap  # noqa: E402

check = T.check
INPUTS = ('press', 'stick', 'sequence')
CONST_FLAG = 'Fixture.DiveDepth'   # invented name for the game's depth float: a constant (3.0), on land and in water, so no proof of a dive

GAP = (-3.0, 2.0, 3.0, 2.8)                  # (x0, z0, x1, z1): he falls 6 m unless a jump carries him over
LEDGE = (-3.0, 2.4, 3.0, 8.0)                # a wall 2 m high: reached only by a jump with the stick held on (1500 ms and more)
WATER = (-5.0, -4.0, 5.0, 10.0, -0.5)        # (x0, z0, x1, z1, surface y)
LADDER = (-0.5, -0.5, 0.5, 0.5, 3.0, 0.0)    # (x0, z0, x1, z1, top y, bottom y)
BLOCK = {'x': 0.0, 'z': 1.2, 'r': 1.5}
SHOP = {'x': 0.0, 'z': 0.5, 'r': 1.0, 'prompt': 'Buy', 'text': 2, 'rupees': -20, 'buy': True}


def inside(rect, x, z):
    return rect[0] <= x <= rect[2] and rect[1] <= z <= rect[3]


class ActionBridge(T.WorldBridge):
    """WorldBridge plus invented physics, all driven by the inputs that are active in the frame (the stick, held buttons):
    X with the stick on is a jump (up 0.8 m over 42 frames, 2 m of way while the stick stays on); `gap` swallows a Link who is on
    the ground in it (y drops 6 m); `ledge` is a wall that a jump with the stick held 1500 ms or more grabs and pulls up (y +2);
    `water` slows him to 2 m/s, and A held there lowers the float `DiveDepth` 0..3 over a second and y with it; `ladder`: the stick
    up or down climbs at 1.5 m/s; `block`: A held with the stick on while he is within r of it moves both 0.5 m/s (`stuck`: neither
    moves); a long A with the stick on and nothing to grab does nothing, a short A tap with the stick on is a roll (3 m over 30
    frames); ZL with a sideways stick strafes at 2 m/s without turning (`circle`: and turns his facing 20 degrees a second toward
    the centre ahead); `horse` makes the walk 9 m/s; `hurt_at` (frames) and `hurt_after_zl` (frames after the first ZL) take a life;
    a thing with `buy` takes its rupees when its text closes (`choice`: one more A is needed)."""
    WALK, HORSE, SWIM, STRAFE, GRAB, AIR, ROLL = 4.0, 9.0, 2.0, 2.0, 0.5, 2.0 / 0.7, 6.0
    JUMP_FRAMES, ROLL_FRAMES, PULL_FRAMES, LONG_STICK, TAP = 42, 30, 30, 90, 12

    def __init__(self, *args, gap=None, ledge=None, water=None, block=None, ladder=None, horse=False, circle=False, hurt_at=(),
                 hurt_after_zl=None, rupees=0, zr_hash=False, const_flag=CONST_FLAG, **kwargs):
        self.gap, self.ledge, self.water, self.ladder = gap, ledge, water, ladder
        self.block = dict(block) if block else None
        self.horse, self.circle, self.const_flag, self.zr_hash = horse, circle, const_flag, zr_hash
        self.hurt_at, self.hurt_after_zl, self.zl_first = set(hurt_at), hurt_after_zl, None
        self.air = self.fall = self.hang = self.roll = 0
        self.floor, self.on_ledge, self.depth, self.a_prev = None, False, 0.0, False
        self.pending, self.stick_log, self.loading_override, self.dirn = None, [], False, 0
        super().__init__(*args, **kwargs)
        self.flags[self.const_flag] = 3.0
        self.rupees = rupees
        self.floor = self.pos[1]

    def game_state(self, frame=None):
        s = super().game_state(frame)
        if self.loading_override:
            s['loading'] = True
        return s

    def extra_values(self):
        values = super().extra_values()
        if self.zr_hash:
            values['0x0000cafe'] = self.zr   # (a flag hash the item button moves)
        return values

    def effect(self, t):
        if not t.get('buy'):
            return super().effect(t)
        t['used'] = t.get('once', True)
        self.text_left = t.get('text', 0) + (1 if t.get('choice') else 0)
        self.pending = t.get('rupees', 0)
        if not self.text_left:
            self.rupees, self.pending = self.rupees + self.pending, None

    def pressed(self, b):
        super().pressed(b)
        if b == 'A' and self.pending is not None and self.text_left == 0:
            self.rupees, self.pending = self.rupees + self.pending, None

    def advance(self, yaw, speed):
        """One frame along the world yaw at `speed` m/s: True moved, False a wall stopped him, 'ledge' the ledge's face did."""
        nx = self.pos[0] + speed / 60 * math.sin(math.radians(yaw))
        nz = self.pos[2] + speed / 60 * math.cos(math.radians(yaw))
        if any(inside(w, nx, nz) for w in self.walls):
            return False
        if self.ledge and not self.on_ledge and inside(self.ledge, nx, nz):
            return 'ledge'
        self.pos[0], self.pos[2] = nx, nz
        return True

    def in_water(self):
        return self.water is not None and inside(self.water, self.pos[0], self.pos[2])

    def tick(self):
        nxt = self.frame + 1
        active = [s for s in self.inputs if s['start'] <= nxt < s['end']]
        axes, held = {}, set()
        for s in active:
            axes.update(s['axes'])
            held.update(s['buttons'])
        sx, sy = axes.get('lx', 0.0), axes.get('ly', 0.0)
        mag = min(1.0, math.hypot(sx, sy))
        on = mag > 0.3
        dirn = 0 if abs(sy) <= 0.5 else 1 if sy > 0 else -1
        if dirn and dirn != self.dirn:
            self.stick_log.append((nxt, 'up' if dirn > 0 else 'down'))
        self.dirn = dirn
        heading = hsap.wrap(self.cam - self.handed * math.degrees(math.atan2(sx, sy)))
        busy = self.game_state()['event']
        a_now = 'A' in held
        edge, self.a_prev = a_now and not self.a_prev, a_now
        tap = any(s['start'] == nxt and 'A' in s['buttons'] and s['end'] - s['start'] <= self.TAP for s in self.inputs)
        jump = any(s['start'] == nxt and 'X' in s['buttons'] for s in self.inputs)
        long_stick = any((s['axes'].get('lx') or s['axes'].get('ly')) and s['end'] - s['start'] >= self.LONG_STICK for s in active)
        if 'ZL' in held and self.zl_first is None:
            self.zl_first = nxt
        if nxt in self.hurt_at or (self.hurt_after_zl is not None and self.zl_first is not None and
                                   nxt == self.zl_first + self.hurt_after_zl):
            self.life -= 1
        if self.updates and not busy:
            self.physics(heading, mag, on, held, edge and tap, jump, long_stick, sy)
        saved = [(s, s['axes']) for s in active]
        for s, a in saved:   # (the base class would walk him on the stick as well: it gets the right stick only)
            s['axes'] = {k: v for k, v in a.items() if k not in ('lx', 'ly')}
        try:
            super().tick()
        finally:
            for s, a in saved:
                s['axes'] = a

    def physics(self, heading, mag, on, held, roll_edge, jump_edge, long_stick, sy):
        grounded = self.air == 0 and self.fall == 0 and self.hang == 0
        if self.fall:   # falling into a gap: 6 m over 20 frames, then the pit's floor is his floor
            self.fall += 1
            self.pos[1] = self.floor - 6.0 * self.fall / 20
            if self.fall >= 20:
                self.floor, self.fall = self.floor - 6.0, 0
            return
        if self.hang:   # holding a ledge's edge: the stick held on pulls him up, letting go drops him
            if on:
                self.hang += 1
                if self.hang >= self.PULL_FRAMES:
                    self.pos[0] += 0.6 * math.sin(math.radians(heading))
                    self.pos[2] += 0.6 * math.cos(math.radians(heading))
                    self.floor, self.on_ledge, self.hang, self.air = 2.0, True, 0, 0
                    self.pos[1] = self.floor
            else:
                self.hang, self.air = 0, 0
                self.pos[1] = self.floor
            return
        if self.air:
            self.air += 1
            if on:
                self.face = heading
                if self.advance(heading, self.AIR * mag) == 'ledge' and long_stick:
                    self.hang = 1
                    self.pos[1] = self.floor + 1.0
                    return
            self.pos[1] = self.floor + 0.8 * math.sin(math.pi * self.air / self.JUMP_FRAMES)
            if self.air > self.JUMP_FRAMES:
                self.air = 0
                self.pos[1] = self.floor
                self.check_gap()
            return
        if self.roll:
            self.roll -= 1
            self.advance(self.face, self.ROLL)
            return
        if self.ladder and inside(self.ladder, self.pos[0], self.pos[2]) and on:
            self.pos[1] = max(self.ladder[5], min(self.ladder[4], self.pos[1] + (1.5 / 60 if sy > 0 else -1.5 / 60)))
            self.floor = self.pos[1]
            return
        if self.in_water():
            surface = self.water[4]
            self.depth = min(3.0, self.depth + 0.05) if 'A' in held else max(0.0, self.depth - 0.05)   # (y only: the depth flag is a constant)
            self.pos[1] = surface - self.depth
            self.floor = surface
            if on:
                self.face = heading
                self.advance(heading, self.SWIM * mag)
            return
        self.depth = 0.0
        if self.on_ledge and not inside(self.ledge, self.pos[0], self.pos[2]):
            self.floor, self.on_ledge = 0.0, False
        self.pos[1] = self.floor
        if not on:
            return
        block = self.block
        if 'A' in held and not roll_edge:   # a long A: a grab, or nothing at all
            if block and math.hypot(self.pos[0] - block['x'], self.pos[2] - block['z']) <= block['r'] and not block.get('stuck'):
                x0, z0 = self.pos[0], self.pos[2]
                if self.advance(heading, self.GRAB):
                    block['x'] += self.pos[0] - x0
                    block['z'] += self.pos[2] - z0
            return
        if roll_edge:
            self.roll, self.face = self.ROLL_FRAMES, heading
            return
        if jump_edge and grounded:
            self.air, self.face = 1, heading
            return
        if 'ZL' in held:
            if self.advance(heading, self.STRAFE * mag) is True and self.circle:
                side = math.sin(math.radians(heading - self.face))   # > 0: he moves to his left
                if abs(side) > 0.5:
                    self.face = hsap.wrap(self.face - math.copysign(20.0 / 60, side))
            return
        self.face = heading
        if self.follow:
            self.cam += hsap.wrap(heading - self.cam) / 60
        self.advance(heading, (self.HORSE if self.horse else self.WALK) * mag)
        self.check_gap()

    def check_gap(self):
        if self.gap and self.air == 0 and inside(self.gap, self.pos[0], self.pos[2]):
            self.fall = 1


class ActionSimulation(T.WorldSimulation):
    def launch(self, cmd, **kwargs):
        args = dict(arg.split('=', 1) for arg in cmd[4:] if '=' in arg)
        self.bridge = ActionBridge(Path(args['HOS_CONTROL']), Path(args['HOS_INPUT_LIVE']), self.copy / 'runs/test',
                                   self.clock, **self.options)
        self.clock.bridge = self.bridge
        return T.FakeRunner()

    def steps(self):
        return [e for e in self.events() if e['ev'] == 'step' and e['src'].split()[0] not in ('end', 'wait')]


@contextlib.contextmanager
def world(lines, tick=None, end_after_input=None, **options):
    """Run the step lines on an ActionBridge world: (simulation, the step events). `tick(bridge)` runs at every frame;
    `end_after_input` frames after the first input the game ends."""
    options.setdefault('boot_events', 0)
    options.setdefault('follow', False)
    if 'water' in options:
        options.setdefault('flags', {CONST_FLAG: 3.0})
    with ActionSimulation(**options) as sim:
        first = []

        def hook(bridge):
            if tick:
                tick(bridge)
            if end_after_input is not None:
                if not first and [r for r in bridge.requests if r['cmd'] in INPUTS]:
                    first.append(bridge.frame)
                if first and bridge.frame >= first[0] + end_after_input:
                    sim.game.runner.running = False
        sim.bridge.on_tick = hook
        sim.executor(list(lines) + ['end']).run()
        yield sim, sim.steps()


def actions_module():
    try:
        import hsap_actions
    except ImportError:
        return None
    return hsap_actions


def hsap_actions():
    module = actions_module()
    check(module is not None, 'hsap_actions.py can be imported')
    return module


def inputs(sim):
    return [r for r in sim.bridge.requests if r['cmd'] in INPUTS]


def scripts(sim):
    return [r['script'] for r in sim.bridge.requests if r['cmd'] == 'sequence']


# ---- the verbs, one group each

def near(a, b, tol=1e-9):
    return abs(a - b) <= tol


def jump_checks():
    with world(['jump 0 3.5'], start=(0.0, 0.0, 1.0), gap=GAP) as (sim, steps):
        a = steps[0]
        check(a['result'] == 'landed', f"jump over a gap lands on the far side ({a['result']}: {a['detail']})")
        ch = a['changes']
        check(ch['pos'][0] == [0.0, 0.0, 1.0] and 3.0 < ch['pos'][1][2] < 4.0 and abs(ch['dy']) < 0.1 and ch['moved'] > 2.0,
              f"it reports the place before and after, dy and the way moved ({ch['pos']}, dy {ch['dy']}, moved {ch['moved']})")
        check(scripts(sim) == ['0:LX=0+LY=32767/800,0.15:X/100'] and len(inputs(sim)) == 1,
              f'one raw sequence and no other input: the stick toward the point for 800 ms, X 150 ms after its start ({scripts(sim)})')
    with world(['jump 0 3.5 hold 400'], start=(0.0, 0.0, 1.0), gap=GAP) as (sim, steps):
        a = steps[0]
        check(a['result'] == 'fell' and a['changes']['dy'] < -5.0 and sim.bridge.floor < -5.0,
              f"a jump with the stick released early ends in the gap: fell ({a['result']}: {a['detail']})")
    with world(['jump 0 9 hold 400'], start=(0.0, 0.0, 1.0)) as (sim, steps):
        check(steps[0]['result'] == 'short', f"a jump that ends closer to the point but outside the radius is short ({steps[0]['detail']})")
    with world(['jump 0 9 hold 400 radius 7'], start=(0.0, 0.0, 1.0)) as (sim, steps):
        check(steps[0]['result'] == 'landed', f"the same jump with radius 7 lands ({steps[0]['result']})")
    # crossing counts: a held stick runs him past a near point (a short gap's far edge); `passed` in the detail
    with world(['jump 0 2.0'], start=(0.0, 0.0, 1.0)) as (sim, steps):
        a = steps[0]
        check(a['result'] == 'landed' and 'passed' in a['detail'] and a['changes']['pos'][1][2] > 3.0,
              f"he ended 1.5 m past a point 1 m away, outside the radius: passed the point, landed ({a['result']}: {a['detail']})")
    with world(['jump 0 2.9 radius 0.3'], start=(0.0, 0.0, 1.0), gap=GAP) as (sim, steps):
        a = steps[0]
        check(a['result'] == 'landed' and 'passed' in a['detail'] and sim.bridge.floor == 0.0,
              f"over a short gap, past the far edge by more than the radius: landed ({a['result']}: {a['detail']})")
    with world(['jump 0 3.5'], start=(0.0, 0.0, 1.0)) as (sim, steps):
        check(steps[0]['result'] == 'landed' and 'passed' not in steps[0]['detail'], 'a landing within the radius is not `passed`')
    with world(['jump 0 2.0 hold 400'], start=(0.0, 0.0, 1.0), gap=GAP) as (sim, steps):
        check(steps[0]['result'] == 'fell', f"passing the point is no landing when he fell ({steps[0]['result']})")
    with world(['jump 0 5'], start=(0.0, 0.0, 1.0), walls=[(-3.0, 1.1, 3.0, 1.3)]) as (sim, steps):
        check(steps[0]['result'] == 'none' and steps[0]['changes']['moved'] < 0.3,
              f"a jump against a wall moves under 0.3 m: none ({steps[0]['result']}: {steps[0]['detail']})")

    # a ledge: the stick held on (hold 1500 and more) grabs it and pulls up; y says where he stands
    with world(['jump 0 4 y 2 hold 800'], start=(0.0, 0.0, 0.0), ledge=LEDGE) as (sim, steps):
        a = steps[0]
        check(a['result'] == 'short' and a['changes']['dy'] < 0.1, f"hold 800 does not reach the ledge: short ({a['detail']})")
    with world(['jump 0 4 y 2 hold 1500', 'jump 0 6 y 2 hold 800'], start=(0.0, 0.0, 0.0), ledge=LEDGE) as (sim, steps):
        a, b = steps
        check(a['result'] == 'landed' and a['changes']['dy'] > 1.9 and sim.bridge.on_ledge,
              f"hold 1500 grabs the edge and pulls up: landed at y 2 ({a['result']}: {a['detail']})")
        check(b['result'] == 'landed' and abs(b['changes']['dy']) < 0.1,
              f"from the ledge's top, within the radius and the height: landed ({b['result']}: {b['detail']})")
    with world(['jump 0 4 y 0 hold 1500'], start=(0.0, 0.0, 0.0), ledge=LEDGE) as (sim, steps):
        check(steps[0]['result'] != 'landed' and steps[0]['changes']['dy'] > 1.9,
              f"a y that is not where he ends is not landed ({steps[0]['result']})")
    with world(['jump 0 4 hold 1500'], start=(0.0, 0.0, 0.0), ledge=LEDGE) as (sim, steps):
        check(steps[0]['result'] == 'landed', 'without y, a landing above the start counts')

    # facing first (face_point 15), and a lead: walk that far straight back, then the run-up and the jump
    with world(['jump 8 1 hold 800 radius 2'], start=(0.0, 0.0, 1.0)) as (sim, steps):
        check(len(scripts(sim)) == 1 and abs(hsap.wrap(sim.bridge.face - 90.0)) <= 15.0 + 1e-6 and inputs(sim)[0]['cmd'] == 'stick',
              f'the point to the side: short stick pushes turn him to it first, then the sequence ({[r["cmd"] for r in inputs(sim)]})')

    low = {'z': 9.0}

    def track(bridge):
        low['z'] = min(low['z'], bridge.pos[2])
    with world(['jump 0 9 lead 3 hold 800'], start=(0.0, 0.0, 0.0), tick=track) as (sim, steps):
        a = steps[0]
        check(low['z'] < -2.5 and a['changes']['pos'][0][2] < -2.0 and len(scripts(sim)) == 1,
              f"lead 3 walks 3 m straight back (to z {low['z']:.1f}) and jumps from there ({a['changes']['pos'][0]})")
        check(a['changes']['pos'][1][2] > a['changes']['pos'][0][2] + 2.0, 'the run-up and the jump carry him forward again')


def climb_checks():
    with world(['climb up timeout 8', 'climb down timeout 8'], start=(0.0, 0.0, 0.0), ladder=LADDER) as (sim, steps):
        a, b = steps
        check(a['result'] == 'done' and 'rose 3.0 m' in a['detail'], f"climb up keeps its meaning and words ({a['result']}: {a['detail']})")
        check(b['result'] == 'done' and abs(b['changes']['dy'] + 3.0) < 0.2 and sim.bridge.pos[1] < 0.1,
              f"climb down: done once he dropped over 1 m and stopped for a second ({b['result']}: {b['detail']})")
        check({r['y'] for r in sim.bridge.requests if r['cmd'] == 'stick'} == {1.0, -1.0}, 'climb down holds the stick down, climb up up')
    with world(['climb timeout 8'], start=(0.0, 0.0, 0.0), ladder=LADDER) as (sim, steps):
        check(steps[0]['result'] == 'done', 'a bare climb is still climb up')
    with world(['climb down timeout 8'], start=(0.0, 0.0, 0.0)) as (sim, steps):
        a = steps[0]
        check(a['result'] == 'stuck' and 'dropped' in a['detail'], f"nothing to climb down: stuck ({a['result']}: {a['detail']})")
    with world(['climb down timeout 2'], start=(0.0, 0.0, 0.0)) as (sim, steps):
        check(steps[0]['result'] == 'timeout' and 1.5 < steps[0]['secs'] < 3.0,
              f"a short timeout ends timeout ({steps[0]['result']} after {steps[0]['secs']} s)")


def swim_checks():
    with world(['swim 0 8 radius 1.5 timeout 30'], start=(0.0, 0.0, -8.0), water=WATER) as (sim, steps):
        a = steps[0]
        check(a['result'] == 'swam' and 'y 0.00' in a['detail'] and '-0.50' in a['detail'],
              f"swim to a point in the water ends swam, the detail has the y at start and end ({a['result']}: {a['detail']})")
        check(a['changes']['dy'] == -0.5 and 5.0 < a['secs'] < 9.0, f"in the water he swims at 2 m/s ({a['secs']} s)")
    with world(['swim 0 20 timeout 12'], start=(0.0, 0.0, 0.0), water=WATER, walls=[(-5.0, 5.0, 5.0, 5.2)]) as (sim, steps):
        check(steps[0]['result'] == 'stuck', f"a wall in the water: the walk's stuck ({steps[0]['result']})")
    with world(['swim 0 40 timeout 3'], start=(0.0, 0.0, 0.0), water=WATER) as (sim, steps):
        check(steps[0]['result'] == 'timeout', 'and the walk\'s timeout')


def dive_checks():
    with world(['dive', 'wait 3', 'dive 400'], start=(0.0, 0.0, 0.0), water=WATER) as (sim, steps):
        a, b = steps
        check(a['result'] == 'dived' and a['changes']['dy'] < -2.0 and a['changes']['min_y'] < -2.5 and 'dive_depth' not in a['changes'],
              f"dive holds A: y fell, dy and min_y say how far, the constant depth flag is no proof ({a['result']}: {a['detail']})")
        presses = [r for r in sim.bridge.requests if r['cmd'] == 'press']
        check([(r['buttons'], r['frames']) for r in presses] == [('A', 90), ('A', 24)] and not scripts(sim) and
              not [r for r in sim.bridge.requests if r['cmd'] == 'stick'],
              'A for 1500 ms (default) and for 400 ms, the stick never touched')
        check(b['result'] == 'dived' and -1.5 < b['changes']['dy'] <= -0.4, f"a short dive: {b['changes']}")
    # on dry ground the flag still reads 3.0 (watched): that is no dive, y never falls
    with world(['dive 800'], start=(0.0, 0.0, 0.0), flags={CONST_FLAG: 3.0}) as (sim, steps):
        a = steps[0]
        check(a['result'] == 'none' and a['changes']['dy'] == 0.0 and sim.game.st['flags'][CONST_FLAG] == 3.0,
              f"a constant 3.0 flag on dry ground: none ({a['detail']})")
    with world(['dive 1000'], start=(0.0, 0.0, 0.0), water=WATER, flags={}) as (sim, steps):
        a = steps[0]
        check(a['result'] == 'dived' and a['changes']['dy'] <= -0.4, f"with no flag watched at all: dived ({a['detail']})")
    with world(['dive 800'], start=(0.0, 0.0, 0.0)) as (sim, steps):
        check(steps[0]['result'] == 'none', 'on dry ground: y never fell: none')


def block_checks():
    with world(['block push 2', 'block pull 1.5'], start=(0.0, 0.0, 0.0), block=BLOCK) as (sim, steps):
        a, b = steps
        check(a['result'] == 'pushed' and 2.0 <= a['changes']['along'] < 2.4 and abs(a['changes']['facing_drift']) < 1.0,
              f"block push moves him about 2 m along his facing, facing unchanged ({a['result']}: {a['detail']})")
        check(b['result'] == 'pulled' and 1.5 <= b['changes']['along'] < 1.9 and abs(b['changes']['facing_drift']) < 1.0,
              f"block pull moves him backward along the line ({b['result']}: {b['detail']})")
        check(near(sim.bridge.block['z'] - sim.bridge.pos[2], 1.2, 0.02), 'the block moved with him')
        check(a['changes']['facing'][0] == a['changes']['facing'][1], 'facing is listed before and after')
        seq = [r['script'] for r in sim.bridge.requests if r['cmd'] == 'sequence']
        pushing = [s for s in seq if s == '0:A+LX=0+LY=32767/300']
        pulling = [s for s in seq if s == '0:A+LX=0+LY=-32767/300']
        check(len(pushing) + len(pulling) == len(seq) and len(pushing) >= 5 and len(pulling) >= 4 and seq[0] in pushing,
              f'A is held through the move: renewed 300 ms holds with the stick along the line ({len(pushing)} and {len(pulling)})')
        check(a['secs'] > 3.5, f"the block moves at 0.5 m/s ({a['secs']} s)")
    with world(['block push 2 timeout 3'], start=(0.0, 0.0, 0.0), block={**BLOCK, 'stuck': True}) as (sim, steps):
        a = steps[0]
        check(a['result'] == 'none' and a['changes']['along'] < 0.5 and 2.5 < a['secs'] < 4.5,
              f"a block that does not move: none at the timeout ({a['result']}: {a['detail']})")
    with world(['block pull 1 timeout 3'], start=(0.0, 0.0, 0.0)) as (sim, steps):
        check(steps[0]['result'] == 'none', 'nothing to grab: none')
    with world(['block push 0.3', 'block push 10 timeout 2'], start=(0.0, 0.0, 0.0), block=BLOCK) as (sim, steps):
        a, b = steps
        check(a['result'] == 'pushed' and 0.3 <= a['changes']['along'] < 0.6,
              f"m 0.3: the move asked for is done, pushed ({a['result']}: {a['changes']['along']} m)")
        check(b['result'] == 'pushed' and 0.5 <= b['changes']['along'] < 1.4 and b['secs'] < 4.0,
              f"m 10: the timeout ends the push where it stands ({b['changes']['along']} m in {b['secs']} s)")
    # facing that turned: not a push
    with world(['block push 3 timeout 3'], start=(0.0, 0.0, 0.0), block=BLOCK,
               tick=lambda b: setattr(b, 'face', hsap.wrap(b.face + 0.8)) if b.block['z'] > 1.3 else None) as (sim, steps):
        a = steps[0]
        check(a['result'] == 'none' and abs(a['changes']['facing_drift']) >= 25.0,
              f"he moved but his facing turned over 25 degrees: not pushed ({a['result']}: {a['detail']})")


def strafe_checks():
    with world(['strafe left', 'strafe right 600'], start=(0.0, 0.0, 0.0)) as (sim, steps):
        a, b = steps
        check(a['result'] == 'strafed' and 2.0 < a['changes']['perp_m'] < 3.0 and abs(a['changes']['facing_change']) < 1.0,
              f"strafe left holds ZL and moves him to his left ({a['result']}: {a['detail']})")
        check(b['result'] == 'strafed' and -1.5 < b['changes']['perp_m'] < -0.9, f"right is the other way, 600 ms ({b['changes']})")
        check(scripts(sim) == ['0:ZL+LX=-32767+LY=0/1200', '0:ZL+LX=32767+LY=0/600'],
              f'ZL held with the stick sideways, camera relative ({scripts(sim)})')
    with world(['strafe left 2000', 'strafe right 2000'], start=(0.0, 0.0, 0.0), circle=True) as (sim, steps):
        a, b = steps
        check(a['result'] == 'circled' and a['changes']['facing_change'] < -25.0 and a['changes']['perp_m'] > 2.0,
              f"locked on, his facing turns as he circles: circled ({a['result']}: {a['detail']})")
        check(b['result'] == 'circled' and b['changes']['facing_change'] > 25.0, f"the other way round ({b['changes']})")
    with world(['strafe left 500'], start=(0.0, 0.0, 0.0), walls=[(-3.0, -1.0, 3.0, 1.0)]) as (sim, steps):
        check(steps[0]['result'] == 'none' and abs(steps[0]['changes']['perp_m']) < 0.5, 'a wall: none')
    # the facing turned toward the side he moved: neither a strafe nor a circle
    with world(['strafe left 2000'], start=(0.0, 0.0, 0.0),
               tick=lambda b: setattr(b, 'face', hsap.wrap(b.face + 0.4)) if b.zl_first else None) as (sim, steps):
        check(steps[0]['result'] == 'none', f"facing turned toward the move: none ({steps[0]['detail']})")


def guard_checks():
    with world(['wait 1', 'guard', 'wait 3', 'guard 300'], start=(0.0, 0.0, 0.0), hurt_after_zl=200) as (sim, steps):
        a, b = steps
        check(a['result'] == 'guarded' and a['changes']['life'] == [12, 12], f"nothing hurt him in 700 ms and 0.6 s after: guarded ({a['detail']})")
        check(sim.bridge.life == 11 and b['result'] == 'guarded' and b['changes']['life'] == [11, 11],
              'a hit long after it is not the guard\'s')
        check([(r['buttons'], r['frames']) for r in sim.bridge.requests if r['cmd'] == 'press'] == [('ZL', 42), ('ZL', 18)],
              'ZL held 700 ms (default)')
    with world(['wait 1', 'guard 700'], start=(0.0, 0.0, 0.0), hurt_after_zl=20) as (sim, steps):
        a = steps[0]
        check(a['result'] == 'hurt' and a['changes']['life'] == [12, 11], f"life dropped during the guard: hurt ({a['detail']})")
    with world(['wait 1', 'guard 400'], start=(0.0, 0.0, 0.0), hurt_after_zl=45) as (sim, steps):
        check(steps[0]['result'] == 'hurt', 'a hit within 0.6 s after the release counts')
    with world(['wait 1', 'guard 400'], start=(0.0, 0.0, 0.0), hurt_after_zl=24 + 60) as (sim, steps):
        check(steps[0]['result'] == 'guarded', 'and one after that does not')
    with world(['wait 1', 'shield 300'], start=(0.0, 0.0, 0.0)) as (sim, steps):
        check(steps[0]['result'] == 'done', 'shield stays as it was')


def roll_checks():
    with world(['roll to 0 8', 'roll up'], start=(0.0, 0.0, 0.0)) as (sim, steps):
        a, c = steps
        check(a['result'] == 'rolled' and a['changes']['moved'] > 1.0, f"roll to a point ahead: rolled ({a['result']}: {a['detail']})")
        check(scripts(sim)[0] == '0:LX=0+LY=32767/240,0.05:A/100', f'the stick toward the point, A 50 ms later ({scripts(sim)[0]})')
        check(c['result'] == 'done' and scripts(sim)[1] == '0:LX=0+LY=32767/240,0.05:A/100', 'the old camera-relative roll is unchanged')
    with world(['roll to 8 0'], start=(0.0, 0.0, 0.0)) as (sim, steps):
        check(steps[0]['result'] == 'rolled' and scripts(sim)[0] == '0:LX=-32767+LY=0/240,0.05:A/100' and sim.bridge.pos[0] > 1.0,
              f"toward a point to the east the stick goes by the camera ({scripts(sim)[0]})")
    with world(['roll to 0 8'], start=(0.0, 0.0, 0.0), walls=[(-3.0, 0.5, 3.0, 1.0)]) as (sim, steps):
        check(steps[0]['result'] == 'none', f"a wall in the way: none ({steps[0]['detail']})")
    with world(['roll to 0 -8'], start=(0.0, 0.0, 0.0)) as (sim, steps):
        a = steps[0]
        check(a['result'] == 'rolled' and sim.bridge.pos[2] < -1.0, f"a roll away from where he faces still goes toward the point ({a['result']})")


def use_checks():
    watch = {'Item.Count': 10}
    with world(['use', 'use Y hold 600', 'use ZR lock hold 300'], start=(0.0, 0.0, 0.0), flags=watch, lock_turn=40.0) as (sim, steps):
        a, b, c = steps
        check(a['result'] == 'used' and a['changes']['flags'] == {'Item.Count': [10, 9]} and a['changes']['aimed'] == 0.0,
              f"use presses ZR 150 ms and reports the flag that changed ({a['result']}: {a['detail']})")
        press = [(r['buttons'], r['frames']) for r in sim.bridge.requests if r['cmd'] == 'press']
        check(press == [('ZR', 9), ('Y', 36)], f'the button and the hold: {press}')
        check(b['result'] == 'none', f"a press that changed nothing: none ({b['detail']})")
        check(c['result'] == 'used' and c['changes']['aimed'] >= 39.0 and 'facing' in c['changes'],
              f"with lock ZL is held and the lock-on turn counts as an aim ({c['result']}: {c['detail']})")
        check(scripts(sim)[-1] == '0:ZL/1300,0.4:ZR/300', f'ZL from 0.4 s before the item press to 0.6 s after it ({scripts(sim)[-1]})')
        zl_frame = [f for f, b in sim.bridge.pressed_log if b == 'ZL'][0]
        zr_frame = [f for f, b in sim.bridge.pressed_log if b == 'ZR'][-1]
        check(zr_frame - zl_frame == 24, f'0.4 s (24 frames) between the lock and the item press ({zr_frame - zl_frame})')
    with world(['use X at 6 0'], start=(0.0, 0.0, 0.0), zr_effect=False) as (sim, steps):
        a = steps[0]
        check(abs(hsap.wrap(sim.bridge.face - 90.0)) <= 12.0 and a['result'] == 'none' and a['changes']['aimed'] == 0.0,
              f"at <x> <z> faces the point first within 12 degrees, and that turn is no aim ({sim.bridge.face:.0f}: {a['detail']})")
    with world(['use ZR hold 800'], start=(0.0, 0.0, 0.0), zr_effect=False) as (sim, steps):
        check(steps[0]['result'] == 'none' and sim.bridge.zr == 1, 'one press, nothing changed: none')
    with world(['use'], start=(0.0, 0.0, 0.0), zr_effect=False, zr_hash=True) as (sim, steps):
        a = steps[0]
        check(a['result'] == 'used' and '0x0000cafe' in a['changes']['hashes'] and '0x00000002' not in a['changes']['hashes'],
              f"a changed hash counts, the clock counter does not ({a['changes']})")
    # rupees and the prompt count; a text that opens is advanced
    gift = {'x': 0.0, 'z': 0.0, 'r': 1.0, 'prompt': 'Open', 'text': 1, 'rupees': 5}
    with world(['use A'], start=(0.0, 0.0, 0.0), things=[gift], zr_effect=False) as (sim, steps):
        a = steps[0]
        check(a['result'] == 'used' and a['changes']['rupees'] == [0, 5] and a['changes']['prompt'][0] == 'Open' and sim.game.st['event'] == 0,
              f"rupees, the prompt and a text closed again: used ({a['result']}: {a['detail']})")
    with world(['use Y', 'use'], start=(0.0, 0.0, 0.0), zr_effect=False) as (sim, steps):
        check([s['result'] for s in steps] == ['none', 'none'], 'the clock counter alone is no use')


def buy_checks():
    with world(['buy', 'buy'], start=(0.0, 0.0, 0.0), things=[SHOP], rupees=50) as (sim, steps):
        a, b = steps
        check(a['result'] == 'bought' and a['changes']['rupees'] == [50, 30] and sim.bridge.rupees == 30,
              f"buy: A at the prompt, the text advanced, the rupees fell: bought ({a['result']}: {a['detail']})")
        check(len(sim.bridge.a_log) == 3 and sim.game.st['event'] == 0, f'one A at the prompt and two for the text ({len(sim.bridge.a_log)})')
        check(b['result'] == 'no-prompt' and 'changes' not in b and len(sim.bridge.a_log) == 3,
              'the prompt reads Empty again: nothing sent, no-prompt')
    with world(['buy'], start=(0.0, 0.0, 0.0), things=[{**SHOP, 'choice': True}], rupees=50) as (sim, steps):
        a = steps[0]
        check(a['result'] == 'bought' and a['changes']['rupees'] == [50, 30] and len(sim.bridge.a_log) == 4,
              f"a choice question takes one more A (the cursor's default): bought ({a['detail']}; {len(sim.bridge.a_log)} presses)")
    with world(['buy'], start=(0.0, 0.0, 0.0), things=[{**SHOP, 'rupees': 0}], rupees=50) as (sim, steps):
        check(steps[0]['result'] == 'none', f"the text closed with nothing changed: none ({steps[0]['detail']})")
    with world(['buy timeout 6'], start=(0.0, 0.0, 0.0), things=[{**SHOP, 'text': 99}], rupees=50) as (sim, steps):
        a = steps[0]
        check(a['result'] == 'timeout' and 5.5 < a['secs'] < 8.0 and sim.game.st['event'] == 1, f"a text that never ends: timeout ({a['secs']} s)")
    with world(['buy'], start=(0.0, 0.0, 5.0), things=[SHOP]) as (sim, steps):
        check(steps[0]['result'] == 'no-prompt' and not inputs(sim), 'away from the shop: nothing sent')
    # a text that is already open is only advanced: no A at the prompt
    with world(['press A 100', 'buy'], start=(0.0, 0.0, 0.0), things=[SHOP], rupees=50) as (sim, steps):
        a = steps[1]
        check(a['result'] == 'bought' and len(sim.bridge.a_log) == 3,
              f"a text already open is advanced, no A at the prompt: two presses of its own ({len(sim.bridge.a_log) - 1})")


def choose_checks():
    with world(['choose down 2', 'choose up'], start=(0.0, 0.0, 0.0)) as (sim, steps):
        a, b = steps
        check(a['result'] == 'done' and 'down' in a['detail'] and '2' in a['detail'], f"choose down 2: done, the detail names the presses ({a['detail']})")
        check(scripts(sim) == ['0:LDOWN/120,0.3:LDOWN/120,0.6:A/100', '0:LUP/120,0.3:A/100'],
              f'stick presses 120 ms, 0.3 s apart, then A ({scripts(sim)})')
        frames = [f for f, _ in sim.bridge.stick_log]
        check([d for _, d in sim.bridge.stick_log] == ['down', 'down', 'up'] and frames[1] - frames[0] == 18,
              f'on the wire: down, down 0.3 s later, then up for the second step ({sim.bridge.stick_log})')
        check(b['result'] == 'done', 'default n is 1')
    with world(['choose up 6'], start=(0.0, 0.0, 0.0)) as (sim, steps):
        check(steps[0]['result'] == 'done' and scripts(sim)[0].count('LUP') == 6, 'the most: 6')


def ride_checks():
    with world(['ride 0 40 radius 2', 'ride 0 100 radius 2 fast 12'], start=(0.0, 0.0, 0.0), horse=True) as (sim, steps):
        a, b = steps
        check(a['result'] == 'ridden' and 8.0 < a['changes']['speed_max'] < 10.0 and a['changes']['speed_mean'] > 7.0,
              f"on a horse the ground speed over a second is over 6.5 m/s: ridden ({a['result']}: {a['detail']})")
        check(b['result'] == 'walked' and b['changes']['speed_max'] < 12.0, f"not as fast as fast 12: the walk's reached becomes walked ({b['detail']})")
    with world(['ride 0 20 radius 2'], start=(0.0, 0.0, 0.0)) as (sim, steps):
        a = steps[0]
        check(a['result'] == 'walked' and 3.5 < a['changes']['speed_max'] < 4.5, f"on foot: walked ({a['detail']})")
    with world(['ride 0 40 timeout 20'], start=(0.0, 0.0, 0.0), horse=True, walls=[(-3.0, 10.0, 3.0, 10.5)]) as (sim, steps):
        a = steps[0]
        check(a['result'] == 'stuck' and a['changes']['speed_max'] > 8.0,
              f"fast but stopped short at a wall: the walk's stuck, the speed still reported ({a['result']}: {a['detail']})")
    with world(['ride 0 80 timeout 2'], start=(0.0, 0.0, 0.0), horse=True) as (sim, steps):
        check(steps[0]['result'] == 'timeout', 'the walk\'s timeout')


# ---- refusals, the end of the game, grammar

HOLD_LINES = ('jump 0 5', 'climb down', 'swim 0 5 timeout 10', 'dive 400', 'block push 1', 'strafe left 400', 'guard 200',
              'roll to 0 5', 'use', 'use ZR lock', 'ride 0 5 timeout 10')


def held_checks():
    def held(b):
        if b.frame >= 300:
            b.event_override = True
    with world(['wait 4'] + list(HOLD_LINES), start=(0.0, 0.0, 0.0), tick=held, water=WATER, block=BLOCK) as (sim, steps):
        got = [(s['src'], s['result']) for s in steps]
        check(got == [(line, 'held') for line in HOLD_LINES], f'an event holds Link: every movement and combat step ends held ({got})')
        check(not inputs(sim), 'and sent nothing')

    def loading(b):
        if b.frame >= 300:
            b.loading_override = True
    with world(['wait 4', 'buy', 'choose up', 'jump 0 5'], start=(0.0, 0.0, 0.0), tick=loading, things=[SHOP]) as (sim, steps):
        check([s['result'] for s in steps] == ['held'] * 3 and not inputs(sim), 'a load holds buy and choose too: held, nothing sent')

    def scene(b):
        if b.frame >= 300:
            b.music, b.event_override = 'Dm_Test_Scene', True
    with world(['wait 4', 'buy'], start=(0.0, 0.0, 0.0), tick=scene, things=[SHOP]) as (sim, steps):
        check(steps[0]['result'] == 'held' and not inputs(sim), 'a scene holds buy: held, nothing sent')

    def text(b):   # choose is for the question a text holds: an event is no refusal for it
        if b.frame >= 300:
            b.event_override = True
    with world(['wait 4', 'choose down'], start=(0.0, 0.0, 0.0), tick=text) as (sim, steps):
        check(steps[0]['result'] == 'done', 'choose answers while a text holds Link')


def cut_checks():
    lines = ['jump 0 5 hold 1000', 'climb down timeout 20', 'swim 0 30 timeout 30', 'dive 3000', 'block push 5', 'strafe left 3000',
             'guard 3000', 'roll to 0 9', 'use ZR lock hold 1000', 'buy', 'choose up 5', 'ride 0 90 timeout 40']
    for line in lines:
        with world([line], start=(0.0, 0.0, 0.0), end_after_input=12, water=WATER, block=BLOCK, things=[{**SHOP, 'text': 99}],
                   rupees=50) as (sim, steps):
            check([(s['src'], s['result']) for s in steps] == [(line, 'cut')],
                  f'{line}: the game ends during the step: cut ({[s["result"] for s in steps]})')


BAD = {
    'jump': ['jump', 'jump 1', 'jump a b', 'jump 1 2 3', 'jump 1 2 radius', 'jump 1 2 radius 0', 'jump 1 2 radius x', 'jump 1 2 y', 'jump 1 2 y x',
             'jump 1 2 lead -1', 'jump 1 2 lead 21', 'jump 1 2 hold 399', 'jump 1 2 hold 3001', 'jump 1 2 hold x', 'jump 1 2 timeout 0',
             'jump 1 2 sideways', 'jump nan 2', 'jump 1 inf'],
    'climb': ['climb down x', 'climb down timeout', 'climb down timeout x', 'climb down timeout 0', 'climb down 5'],
    'swim': ['swim', 'swim 1', 'swim a b', 'swim 1 2 3', 'swim 1 2 radius 0', 'swim 1 2 timeout', 'swim 1 2 hold 3'],
    'dive': ['dive x', 'dive 199', 'dive 8001', 'dive 500 600', 'dive timeout', 'dive 500 timeout x', 'dive 500 timeout 0'],
    'block': ['block', 'block sideways', 'block push x', 'block push 0.1', 'block push 11', 'block pull 1 2', 'block push timeout',
              'block 2'],
    'strafe': ['strafe', 'strafe up', 'strafe left x', 'strafe left 299', 'strafe left 5001', 'strafe left 500 600'],
    'guard': ['guard x', 'guard 49', 'guard 5001', 'guard 100 200'],
    'roll': ['roll to', 'roll to 1', 'roll to a b', 'roll to 1 2 3'],
    'use': ['use Q', 'use A B', 'use at', 'use at 1', 'use at a b', 'use hold', 'use hold 49', 'use hold 3001', 'use hold x', 'use lock now',
            'use at 1 2 3'],
    'buy': ['buy now', 'buy timeout', 'buy timeout 0', 'buy 5'],
    'choose': ['choose', 'choose sideways', 'choose up 0', 'choose up 7', 'choose up x', 'choose up 1 2', 'choose 2'],
    'ride': ['ride', 'ride 1', 'ride a b', 'ride 1 2 3', 'ride 1 2 fast 0', 'ride 1 2 fast x', 'ride 1 2 radius 0', 'ride 1 2 timeout'],
}


def bad_checks():
    lines = [line for group in BAD.values() for line in group]
    with world(lines + ['wait 0.1'], start=(0.0, 0.0, 0.0), water=WATER) as (sim, steps):
        bad = [e for e in sim.events() if e['ev'] == 'bad']
        check([e['src'] for e in bad] == lines, f'{len(lines)} malformed steps are answered bad ({[e["src"] for e in bad][:3]} ...)')
        wrong = [e['src'] for e in bad if not e['why'].startswith(e['src'].split()[0] + ': ')]
        check(not wrong, f'each with its verb\'s usage text ({wrong[:3]})')
        check(not inputs(sim), 'and none of them sent an input')


def ledger_checks():
    """step_seconds knows the lines of every verb and nothing else; hsap's own verb list and Executor have them."""
    actions = hsap_actions()
    lines = ['jump 0 5', 'jump 0 5 hold 3000 timeout 20', 'climb up', 'climb down timeout 9', 'swim 1 2', 'swim 1 2 timeout 20', 'dive',
             'dive 4000', 'dive 4000 timeout 10', 'block push', 'block pull 3 timeout 20', 'strafe left', 'strafe right 5000', 'guard',
             'guard 3000', 'roll to 1 2', 'use', 'use ZL lock hold 1000', 'use Y at 1 2', 'buy', 'buy timeout 30', 'choose up', 'choose down 4',
             'ride 1 2', 'ride 1 2 timeout 50']
    secs = {line: actions.step_seconds(line) for line in lines}
    check(all(isinstance(v, float) and v > 0 for v in secs.values()), f'step_seconds covers every verb ({secs})')
    want = {'jump 0 5': 20.8, 'jump 0 5 hold 3000 timeout 20': 31.0, 'climb up': 18.0, 'climb down timeout 9': 15.0, 'swim 1 2': 46.0,
            'swim 1 2 timeout 20': 26.0, 'ride 1 2': 46.0, 'ride 1 2 timeout 50': 56.0, 'dive': 13.5, 'dive 4000': 16.0,
            'dive 4000 timeout 10': 16.0, 'block push': 16.0, 'block pull 3 timeout 20': 26.0, 'strafe left': 5.2, 'strafe right 5000': 9.0,
            'guard': 4.7, 'guard 3000': 7.0, 'roll to 1 2': 4.0, 'use': 14.15, 'use ZL lock hold 1000': 16.0, 'use Y at 1 2': 18.15,
            'buy': 51.0, 'buy timeout 30': 36.0, 'choose up': 4.3, 'choose down 4': 5.2}
    check(set(want) == set(lines) and all(near(secs[k], v, 1e-6) for k, v in want.items()),
          f'the allowances: timeout (jump 12 s, climb 12, swim 40, dive hold + 6, block 10, buy 45, ride 40) + 6 s, the holds + 4 s, '
          f'jump + its hold + 8 s, use 14 s + hold ({[k for k, v in want.items() if not near(secs[k], v, 1e-6)]})')
    for other in ('walk 1 2', 'run 1 2', 'wait 2', 'shield 700', 'roll up', 'roll toward', 'press A', 'chest', 'item', 'raw 0:A/100 1', 'end', '', '   '):
        check(actions.step_seconds(other) is None, f'step_seconds leaves {other!r} alone')
    check(all(actions.step_seconds(bad) > 0 for bad in ('jump x', 'dive x', 'jump 1 2 hold', 'swim 1 2 timeout', 'use hold', 'choose up x', 'block')),
          'a malformed line of these verbs still gets an allowance (the step itself answers bad)')
    for verb in ('jump', 'climb', 'swim', 'dive', 'block', 'strafe', 'guard', 'roll', 'use', 'buy', 'choose', 'ride'):
        check(verb in hsap.INTERACT_VERBS and hasattr(hsap.Executor, 'step_' + verb), f'{verb} is in hsap.INTERACT_VERBS with its step_{verb}')
    for line in ('walk 0 1', 'shield', 'roll toward', 'roll up', 'swing', 'wait 1', 'climb', 'climb up timeout 4', 'climb timeout 4'):
        check(actions.plays(line.split()) is False, f'{line!r} stays with hsap\'s own steps')
    for line in ('jump 1 2', 'climb down', 'roll to 1 2', 'use', 'ride 1 2', 'buy', 'choose up'):
        check(actions.plays(line.split()) is True, f'{line!r} is a step of hsap_actions')
    check(actions.plays([]) is False, 'an empty line is nobody\'s')


def pure_checks():
    """The measuring functions on their own."""
    actions = hsap_actions()
    J = actions.judge_jump
    start = [0.0, 5.0, 0.0]
    check(J(start, [0.0, 5.0, 5.0], 0.0, 5.0, 1.2, None) == 'landed', 'judge_jump: within the radius, no y: landed')
    check(J(start, [0.0, 3.6, 5.0], 0.0, 5.0, 1.2, None) == 'landed', '... 1.4 m below the start is still landed')
    check(J(start, [0.0, 3.4, 5.0], 0.0, 5.0, 1.2, None) != 'landed', '... 1.6 m below is not (not more than 1.5 m)')
    check(J(start, [0.0, 3.4, 5.0], 0.0, 5.0, 1.2, 3.0) == 'landed', '... but a y asks only for 1.2 m of height')
    check(J(start, [0.0, 3.4, 5.0], 0.0, 5.0, 1.2, 5.0) != 'landed', '... and away from the asked height it is not landed')
    check(J(start, [0.0, 2.0, 5.0], 0.0, 5.0, 1.2, None) == 'fell' and J(start, [0.0, 2.4, 1.0], 0.0, 9.0, 1.2, None) == 'fell',
          'more than 2.5 m below the start and not landed: fell')
    check(J(start, [0.0, 5.0, 0.1], 0.0, 9.0, 1.2, None) == 'none' and J(start, [0.0, 5.0, 3.0], 0.0, 9.0, 1.2, None) == 'short',
          'under 0.3 m: none; closer: short')
    check(J(start, [0.0, 5.0, -2.0], 0.0, 9.0, 1.2, None) == 'none', 'moved but not closer: none')
    check(J(start, [0.0, 5.0, 5.0], 0.0, 2.0, 1.2, None) == 'landed' and J(start, [0.0, 5.0, 5.0], 0.0, 2.0, 1.2, 5.0) == 'landed',
          'judge_jump: past the point along the line, outside the radius: landed (the height rule as before)')
    check(J(start, [1.5, 5.0, 5.0], 0.0, 2.0, 1.2, None) == 'landed' and J(start, [3.0, 5.0, 5.0], 0.0, 2.0, 1.2, None) == 'none' and
          J(start, [3.0, 5.0, 5.0], 0.0, 2.0, 4.0, None) == 'landed',
          '... with the sideways offset under max(radius, 2) m: 1.5 m off lands, 3 m off does not (unless the radius is 4)')
    check(J(start, [0.0, 3.4, 5.0], 0.0, 2.0, 1.2, None) != 'landed' and J(start, [0.0, 2.0, 5.0], 0.0, 2.0, 1.2, None) == 'fell' and
          J(start, [0.0, 3.4, 5.0], 0.0, 2.0, 1.2, 3.0) == 'landed' and J(start, [0.0, 3.4, 5.0], 0.0, 2.0, 1.2, 5.0) != 'landed',
          '... and the height rule: 1.6 m below is not landed, 3 m below fell, a y asks for 1.2 m')
    check(J(start, [0.0, 5.0, 1.9], 0.0, 2.0, 0.05, None) == 'short' and J(start, [0.0, 5.0, 2.0], 0.0, 2.0, 0.05, None) == 'landed',
          '... not yet at the point: short; at it: landed')
    # a start already inside the landing radius (a 1.2 m gap and a radius of 1.2): standing there proves nothing, a jump must have moved him (first real run: the
    # jump ended where it began, 0.2 m, with a Deku Baba on him, and was called landed)
    inside = [0.0, 5.0, 0.9]
    check(J(inside, [0.0, 5.0, 1.1], 0.0, 2.0, 1.2, None) == 'none' and J(inside, [0.0, 5.0, 1.1], 0.0, 2.0, 1.2, 5.0) == 'none',
          'judge_jump: the start inside the radius and 0.2 m moved: none, not landed')
    check(J(inside, [0.0, 5.0, 2.0], 0.0, 2.0, 1.2, None) == 'landed' and J(inside, [0.0, 5.0, 5.0], 0.0, 2.0, 1.2, None) == 'landed',
          '... moved 1.1 m onto the point, or past it: landed')
    check(J([0.0, 5.0, 1.9], [0.0, 5.0, 2.0], 0.0, 2.0, 0.05, None) == 'landed',
          '... a start outside the radius is judged as before (0.1 m onto a 0.05 m radius: landed)')
    check(J([0.0, 5.0, 0.5], [0.0, 7.0, 0.6], 0.0, 1.0, 1.0, 7.0) == 'landed' and J([0.0, 5.0, 0.5], [0.0, 5.0, 0.6], 0.0, 1.0, 1.0, 7.0) != 'landed',
          '... a ledge (the asked height 2 m above the start) is proved by the height, however short the move')
    S = actions.ride_speeds
    pts = [(i / 10, 0.0, i * 0.9) for i in range(0, 31)]
    mx, mean = S(pts)
    check(near(mx, 9.0, 1e-6) and near(mean, 9.0, 1e-6), f'ride_speeds: a steady 9 m/s ({mx}, {mean})')
    pts = [(i / 10, 0.0, 0.0) for i in range(8)] + [(0.8 + i / 10, 0.0, i * 1.2) for i in range(1, 12)]
    mx, mean = S(pts)
    check(near(mx, 12.0, 1e-6) and 6.0 < mean < 12.0, f'it is the best 1 s window, the mean is over the whole move ({mx}, {mean})')
    check(S([(0.0, 0.0, 0.0), (0.5, 0.0, 6.0)])[0] is None and S([(0.0, 0.0, 0.0)]) == (None, None), 'under 1 s of move: no window')
    V = actions.strafe_verdict
    check(V(1.0, 3.0) == 'strafed' and V(1.0, -40.0) == 'circled' and V(-1.0, 40.0) == 'circled' and V(1.0, 40.0) == 'none' and
          V(0.4, 0.0) == 'none' and V(-0.6, 24.9) == 'strafed',
          'strafe_verdict: strafed, circled (facing turned toward the centre), none')


GROUPS = (jump_checks, climb_checks, swim_checks, dive_checks, block_checks, strafe_checks, guard_checks, roll_checks, use_checks,
          buy_checks, choose_checks, ride_checks, held_checks, cut_checks, bad_checks, ledger_checks, pure_checks)


def main():
    for group in GROUPS:
        group()
    print('test_hsap_actions: all passed')


if __name__ == '__main__':
    main()
