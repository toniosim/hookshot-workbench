#!/usr/bin/env python3
"""The pilot without the game: a fake autopilot (a thread that reads steps.txt and writes out.jsonl as the live channel
does) plays a made-up house with a door, a scene and a talk; the stand-in server answers the model decider and the
planner. Checks: conditions, the candidates (at most twelve, for every kind), the rules decider solving the made-up
segment, the exported route, the replay decider, the Decisions request's shape, the key never reaching a stand-in,
the caps, the ledger's figures.

    python3 test_pilot.py
"""
import json
import math
import os
import re
import sys
import tempfile
import threading
import time
from unittest import mock
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import deciders  # noqa: E402
import follow_feed  # noqa: E402
import lessons  # noqa: E402
import hud_text  # noqa: E402
import openai_api  # noqa: E402
import pilot  # noqa: E402
import standin  # noqa: E402
import tactics  # noqa: E402
import test_actions  # noqa: E402
import test_eyes  # noqa: E402
import test_hud_text  # noqa: E402
import test_interact  # noqa: E402
import test_lessons  # noqa: E402
import test_recover  # noqa: E402
import test_sections  # noqa: E402

hsap = pilot.hsap   # the game side's parser and geometry, as the pilot uses them

SEGMENT = '''
name = "fake-house"
what = "a made-up house: the door, a scene, a talk"
area = "Fake_Area"
budget_seconds = 500
max_decisions = 40
[[goal]]
name = "door"
flag = "Door_Open=1"
kind = "door"
targets = [{name = "door", at = [0.0, 0.0], kind = "door"}]
[[goal]]
name = "scene"
flag = "Scene_Played=1"
kind = "wait"
targets = [{name = "porch", at = [2.0, 0.0], kind = "wait"}]
[[goal]]
name = "talk"
flag = "Talked=1"
kind = "talk"
targets = [{name = "friend", at = [6.0, 3.0], kind = "talk"}]
'''


class FakeGame(threading.Thread):
    """Link starts at (-4, 0) inside; the door at x = 0 is a wall until A opens it while Link pushes against it (the
    prompt reads Open there); stepping past x = 1 starts a scene whose flag is set by the next until step; the
    friend at (6, 3) answers A presses within 2 m once the scene has played. A box at (3.5, 1.5) blocks the straight
    way from the porch to the friend's front: a move that crosses x = 3.5 with z between 0.5 and 2.5 ends stuck."""

    def __init__(self, live):
        super().__init__(daemon=True)
        self.live = Path(live)
        self.pos = [-4.0, 0.0, 0.0]
        self.flags = {'Door_Open': 0, 'Scene_Played': 0, 'Talked': 0}
        self.watch, self.prompt, self.tick, self.n, self.stop = [], 'Empty', 0, 0, False
        self.scene_due = False

    def emit(self, **e):
        with open(self.live / 'out.jsonl', 'a') as f:
            f.write(json.dumps(e) + '\n')

    def state(self, last):
        self.tick += 60
        self.emit(ev='state', why='wait', n=self.tick, tick=self.tick, t=self.tick / 60, world=0, steps=self.n,
                  **{'in': self.lines}, pos=list(self.pos), facing=90.0, camera=90.0, area='Fake_Area',
                  prompt=self.prompt, music='BGM_Fake', scene=False, life=12, max_life=12, rupees=0, loading=0,
                  time='06:00', last=last, flags={k: self.flags.get(k) for k in self.watch}, changed=[])

    def blocked(self, x, z):
        x0, z0 = self.pos[0], self.pos[2]
        if not self.flags['Door_Open'] and (x0 < 0) != (x < 0) and abs(z) < 2:
            return (-0.3, z0)
        if (x0 < 3.5) != (x < 3.5) and 0.5 < (z0 + z) / 2 < 2.5:
            return (3.2 if x0 < 3.5 else 3.8, z0)
        return None

    def step(self, src):
        w = src.split()
        result, moved = 'done', 0.0
        if w[0] in ('walk', 'run'):
            x, z = float(w[1]), float(w[2])
            r = float(w[w.index('radius') + 1]) if 'radius' in w else 1.0
            stop = self.blocked(x, z)
            nx, nz = stop if stop else (x, z)
            moved = math.hypot(nx - self.pos[0], nz - self.pos[2])
            self.pos[0], self.pos[2] = nx, nz
            result = 'stuck' if stop and math.hypot(x - nx, z - nz) > r else 'reached'
            self.prompt = 'Open' if stop and stop[0] == -0.3 else 'Empty'
            if self.flags['Door_Open'] and self.pos[0] > 1 and not self.flags['Scene_Played']:
                self.scene_due = True
        elif w[0] == 'press' and self.prompt == 'Open':
            self.flags['Door_Open'], self.prompt = 1, 'Empty'
        elif w[0] == 'until':
            name, _, val = w[2].partition('=')
            if self.scene_due:
                self.flags['Scene_Played'], self.scene_due = 1, False
            if name == 'Talked' and 'press' in w and self.flags['Scene_Played'] and \
                    math.hypot(self.pos[0] - 6, self.pos[2] - 3) < 2:
                self.flags['Talked'] = 1
            if name == '0x9824206c':
                result = 'reached' if self.prompt == val else 'timeout'
            else:
                result = 'reached' if str(self.flags.get(name)) == val else 'timeout'
        self.n += 1
        return {'ev': 'step', 'n': self.n, 'in': self.lines, 'line': 0, 'src': src, 'result': result,
                'secs': 1.0, 'moved': round(moved, 2), 'pos': list(self.pos), 'detail': ''}

    def run(self):
        self.lines, off, buf = 0, 0, ''
        self.emit(ev='start', tick=0, steps=0, pos=None)
        self.emit(ev='gameplay', tick=1, steps=0, pos=list(self.pos))
        waiting = False
        while not self.stop:
            data = (self.live / 'steps.txt').read_text()[off:]
            off += len(data)
            buf += data
            *whole, buf = buf.split('\n')
            last = None
            for line in whole:
                self.lines += 1
                w = line.split()
                if not w:
                    continue
                if w[0] == 'watch':
                    self.watch += w[1:]
                elif w[0] == 'end':
                    self.emit(ev='done', tick=self.tick, steps=self.n, pos=list(self.pos))
                    return
                else:
                    e = self.step(line)
                    self.emit(**e)
                    last = {'src': e['src'], 'result': e['result'], 'secs': 1.0, 'moved': e['moved'], 'detail': ''}
                    waiting = False
            if not waiting and (last or not self.n):
                self.state(last)
                waiting = True
            time.sleep(0.01)


class RecordingHud(hud_text.Hud):
    """The panel texts a run wrote, in order (the file only ever holds the last one)."""
    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.texts = []

    def write(self, text):
        self.texts.append(text)
        super().write(text)


class FailingHud(RecordingHud):
    def write(self, text):
        raise OSError(28, 'No space left on device')


def play(decider, tmp, max_decisions=None, planner=None, hud=False):
    seg_path = tmp / 'fake.toml'
    seg_path.write_text(SEGMENT)
    seg = pilot.Segment(seg_path)
    live = tmp / f'live-{decider.name}-{time.time_ns()}'
    ch = pilot.Channel(live)
    ch.send(pilot.watch_lines(seg.watch))
    game = FakeGame(live)
    game.start()
    assert ch.wait(lambda e: e['ev'] == 'gameplay', 5)
    st = ch.wait(lambda e: e['ev'] == 'state', 5)
    run_dir = tmp / f'run-{decider.name}-{time.time_ns()}'
    run_dir.mkdir()
    panel = (RecordingHud(live / 'hud.txt') if hud is True else hud) if hud else None
    p = pilot.Pilot(seg, decider, ch, run_dir, run_dir.name, lambda: True, planner, max_decisions,
                    **({'hud': panel} if panel is not None else {}))
    p.plan = None
    outcome = p.run(st)
    ch.send(['end'])
    ch.wait(lambda e: e['ev'] == 'done', 5)
    return seg, p, outcome, ch, run_dir


FOLLOW_SEGMENT = '''
name = "fake-follow"
what = "walk to another player"
area = "Fake_Area"
budget_seconds = 500
max_decisions = 10
[[goal]]
name = "other"
flag = "Talked=1"
kind = "reach"
targets = [{name = "the-other-player", follow = "other", kind = "reach", radius = 2.0}]
'''


def follow_play(tmp, decider_cls, write_first=True, first=None):
    """A pilot on a follow target in the fake area: `other.json` is the runner's file. Returns what the decider saw."""
    seg_path = tmp / f'follow-{time.time_ns()}.toml'
    seg_path.write_text(FOLLOW_SEGMENT)
    seg = pilot.Segment(seg_path)
    live = tmp / f'live-follow-{time.time_ns()}'
    ch = pilot.Channel(live)
    ch.send(pilot.watch_lines(seg.watch))
    game = FakeGame(live)
    game.start()
    assert ch.wait(lambda e: e['ev'] == 'gameplay', 5)
    st = ch.wait(lambda e: e['ev'] == 'state', 5)
    run_dir = tmp / f'run-follow-{time.time_ns()}'
    run_dir.mkdir()
    path = tmp / f'other-{time.time_ns()}.json'
    decider = decider_cls(path)
    p = pilot.Pilot(seg, decider, ch, run_dir, run_dir.name, lambda: True, None, None, follows={'other': str(path)}, follow_wait=6.0)
    p.plan = None
    if write_first:
        decider.put(*(first or (-4.0, 9.0)))
    out = {}
    th = threading.Thread(target=lambda: out.update(outcome=p.run(st)), daemon=True)
    th.start()
    return seg, p, ch, decider, path, run_dir, th, game


class Mover:
    """Picks 'go' and moves the other player between decisions (what a runner does while the pilot walks); records what it was
    shown: the target's x, z and the labels offered."""
    name = 'mover'
    stop_reason = None

    def __init__(self, path):
        self.path, self.seen, self.route = path, [], [(-4.0, 9.0), (-4.0, -8.0), (-4.0, 4.0)]

    def put(self, x, z, map_='Fake_Area'):
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps({'x': x, 'y': 0.0, 'z': z, 'map': map_, 'w': time.time()}))
        os.replace(tmp, self.path)

    def choose(self, ctx):
        self.seen.append((ctx.target.x, ctx.target.z, [c.label for c in ctx.candidates], ctx.state.get('pos')))
        n = len(self.seen)
        if n < len(self.route):
            self.put(*self.route[n])       # he moved while Link walked
        if n == 3:
            self.put(50.0, 50.0, 'Other_Area')   # now on another map: this map's coordinates must not change
        return deciders.Choice('go' if n < 4 else 'next-target')


def follow_checks(tmp):
    # the pilot waits for the file: no decision before it exists, none of the segment's steps either
    seg, p, ch, d, path, run_dir, th, game = follow_play(tmp, Mover, write_first=False)
    time.sleep(1.2)
    check(th.is_alive() and not d.seen and not (run_dir / 'transcript.jsonl').read_text().count('"decision"'),
          'a follow target: no decision before the runner has written the other player\'s place')
    d.put(-4.0, 9.0)
    th.join(20)
    check(not th.is_alive() and d.seen, 'the pilot decides once the file is there')
    shown = [(x, z) for x, z, _, _ in d.seen]
    check(shown[:3] == [(-4.0, 9.0), (-4.0, -8.0), (-4.0, 4.0)],
          f'each decision sees the other player where he is now: {shown[:3]}')
    check(shown[3] == (-4.0, 4.0), 'a place on another map does not move the target (the fourth decision)')
    check(all('fragment' not in labels for _, _, labels, _ in d.seen), 'no replay fragment is offered for a moving target')
    tr = [json.loads(x) for x in (run_dir / 'transcript.jsonl').read_text().splitlines()]
    fl = [e for e in tr if e['kind'] == 'follow']
    check(fl and fl[-1]['same_map'] is False and all(e['age_s'] is not None and e['age_s'] < 30 for e in fl),
          f'{len(fl)} follow rows in the transcript with the file\'s age, the other map marked')
    check(any(e['kind'] == 'result' and any(line.startswith('run -4.00 -8.00') for line in e['lines']) for e in tr),
          'the step sent after the second decision runs to the second place')
    ch.send(['end'])
    # a file that never comes: the pilot says so and ends
    seg2, p2, ch2, d2, path2, run2, th2, game2 = follow_play(tmp, Mover, write_first=False)
    th2.join(15)
    check(not th2.is_alive() and not d2.seen and any('never came' in x for x in (run2 / 'transcript.jsonl').read_text().splitlines()),
          'a follow file that never comes ends the run without a decision')
    ch2.send(['end'])


def check(cond, what):
    if not cond:
        raise SystemExit(f'FAILED: {what}')
    print(f'ok: {what}')


# ---- the duel goal: candidates, the rules' policy, a whole duel against a fake game, the model path, the cost

DUEL_SEGMENT = '''
name = "fake-duel"
what = "a made-up duel in an open arena"
area = "Fake_Arena"
budget_seconds = 300
max_decisions = 200
[[goal]]
name = "duel"
what = "Fight the other player, best of three; hearts count in quarter hearts."
kind = "duel"
targets = [{name = "opponent", follow = "opponent", kind = "duel", radius = 1.4},
           {name = "opponent-b", follow = "opponent-b", kind = "duel", radius = 1.4}]
'''


def series_segment(extra='matches = 3'):
    """DUEL_SEGMENT with one more line in its goal (the goal's own `kind` line, not the targets' inline `kind`)."""
    return DUEL_SEGMENT.replace('kind = "duel"\ntargets', f'kind = "duel"\n{extra}\ntargets')


def wrap(d):
    return (d + 180.0) % 360.0 - 180.0


class FakeDuelGame(threading.Thread):
    """hsap without a game, for the duel goal: reads steps.txt and writes out.jsonl as the executor does. Game time moves by
    each step's length. A made-up arena in which the other player stands 8 m ahead of the spawn and swings every
    `swing_every` s at whoever is within 1.8 m (a shield held in front takes it): the duel ledger is kept in the game's own
    log lines, fed through hsap's DuelTracker, so the state lines carry exactly what hsap would make of them. Hearts: 16
    quarter units each, a hit takes 4. Ready is refused until a practice swing was made (as the native build will). A Ready
    after `Match ended` begins a new match (a new decimal id, the score 0-0). Options: lose_matches (match numbers, from 1, in which
    the opponent hits every swing through any guard and our swings do nothing: he wins them 2-0), interrupt_in ((match, s): that
    match is interrupted this long after its fight began), replay_end (the `Match ended` line is logged again, identical, twice
    after it), forget_power (the game forgets the sword's power at each match's end: Ready is refused until a swing)."""
    HEARTS, HIT = 16, 4

    def __init__(self, live, opp_path, refuse_always=False, swing_every=2.4, interrupt_at=None, opponent_swings=True,
                 no_duel=False, lose_matches=(), interrupt_in=None, replay_end=False, forget_power=False):
        super().__init__(daemon=True)
        self.live, self.opp_path = Path(live), Path(opp_path)
        self.pos, self.face, self.t = [0.0, 0.0, 0.0], 0.0, 0.0
        self.opp = [0.0, 0.0, 8.0]
        self.tracker = hsap.DuelTracker()
        self.d = None   # the ledger as the log says it: set by the first state line
        self.score, self.hearts, self.round = [0, 0], [self.HEARTS, self.HEARTS], 1
        self.match_no, self.lose_matches, self.interrupt_in = 1, set(lose_matches), interrupt_in
        self.replay_end, self.forget_power, self.replays, self.last_state = replay_end, forget_power, [], None
        self.duel_since = None
        self.practiced, self.refuse_always, self.interrupt_at = False, refuse_always, interrupt_at
        self.swing_every, self.opponent_swings = swing_every, opponent_swings
        self.countdown_end = self.finish_at = self.next_swing = None
        self.shield_until, self.winner, self.next_publish = -1.0, None, 0.0
        self.log_lines, self.requests, self.stop, self.n, self.lines = [], [], False, 0, 0
        self.swing_id, self.no_duel = 0, no_duel   # no_duel: a game without a duel (co-op off): Ready says nothing at all

    # ---- the file and the events
    def publish(self):
        tmp = self.opp_path.with_suffix('.tmp')
        tmp.write_text(json.dumps({'x': self.opp[0], 'y': 0.0, 'z': self.opp[2], 'map': 'Fake_Arena', 'w': time.time()}))
        os.replace(tmp, self.opp_path)

    def emit(self, **e):
        with open(self.live / 'out.jsonl', 'a') as f:
            f.write(json.dumps(e) + '\n')

    def state(self, last):
        self.publish()
        f = json.loads(self.opp_path.read_text())
        e = {'ev': 'state', 'why': 'wait', 'n': int(self.t * 10), 't': round(self.t, 2), 'frame': int(self.t * 60),
             'pos': [round(v, 2) for v in self.pos], 'facing': round(self.face, 1), 'camera': 0.0, 'area': 'Fake_Arena',
             'prompt': 'Empty', 'music': 'BGM_Fake', 'scene': False, 'event': 0, 'loading': 0, 'child': 0, 'life': 24,
             'max_life': 24, 'rupees': 0, 'last': last, 'flags': {}, 'changed': [], 'in': self.lines}
        duel = self.tracker.snapshot(self.t)
        if duel:
            e['duel'] = duel
        opp = hsap.opponent_block(self.pos, self.face, f, time.time(), 'Fake_Arena')
        if opp:
            e['opponent'] = opp
        self.emit(**e)

    # ---- the game's own log lines
    def line(self, text):
        line = f'[hos {self.t:.3f}] coop: duel: {text}'
        self.log_lines.append(line)
        self.tracker.feed(line, self.t)

    def match_id(self):
        return str((self.match_no << 32) | 7)   # (the game's ids are decimal numbers, a serial in the high half)

    def set_state(self, state, reason=''):
        d = self.d = {'state': state, 'ready': getattr(self, 'ready', [0, 0])}
        self.last_state = (f"state {state} match {self.match_id()} round {self.round} score {self.score[0]}-{self.score[1]} hearts "
                           f"{self.hearts[0]}/{self.hearts[1]} self 0 ready {d['ready'][0]}{d['ready'][1]} reason {reason}")
        self.line(self.last_state)

    def swing_line(self, result, dist, bearing):
        self.swing_id += 1
        self.line(f'swing member 2 id {self.swing_id} node CutS1 frame 12 dist {dist:.2f} bearing {bearing:.1f} dy 0.00 '
                  f'result {result} native 4 amount {self.HIT if result == "hit" else 0} self_hearts {self.hearts[0]}')

    # ---- geometry
    def to_opp(self):
        dx, dz = self.opp[0] - self.pos[0], self.opp[2] - self.pos[2]
        return math.hypot(dx, dz), math.degrees(math.atan2(dx, dz))

    def move(self, yaw, dist):
        self.pos[0] += dist * math.sin(math.radians(yaw))
        self.pos[2] += dist * math.cos(math.radians(yaw))
        self.face = wrap(yaw)

    # ---- the ledger over time
    def advance(self, dt):
        end = self.t + dt
        while self.t < end - 1e-9:
            self.t = min(end, self.t + 0.05)
            self.tick()

    def tick(self):
        d = self.d or {}
        run_out = (self.interrupt_in is not None and self.interrupt_in[0] == self.match_no and self.duel_since is not None and
                   self.t >= self.duel_since + self.interrupt_in[1])
        if d.get('state') == 'Duel' and ((self.interrupt_at is not None and self.t >= self.interrupt_at) or run_out):
            self.interrupt_at = self.interrupt_in = None
            self.set_state('Interrupted', 'arena left')
        elif d.get('state') == 'Countdown' and self.t >= self.countdown_end:
            self.next_swing, self.duel_since = self.t + self.swing_every, self.t
            self.set_state('Duel', 'fight')
        elif d.get('state') == 'Duel' and self.opponent_swings and self.t >= self.next_swing:
            self.next_swing = self.t + self.swing_every
            dist, bearing = self.to_opp()
            if dist > 1.8:
                self.swing_line('range', dist, bearing)
            else:
                guarded = (self.match_no not in self.lose_matches and self.t < self.shield_until and
                           abs(wrap(bearing - self.face)) <= 60)
                if not guarded:
                    self.hearts[0] = max(0, self.hearts[0] - self.HIT)
                self.swing_line('shielded' if guarded else 'hit', dist, bearing)
                if self.hearts[0] <= 0:
                    self.finish_round(1)
        elif d.get('state') == 'Finishing round' and self.t >= self.finish_at:
            self.score[self.winner] += 1
            self.ready = [0, 0]
            if self.score[self.winner] >= 2:
                self.set_state('Match ended', f'match won by participant {self.winner}')
                if self.forget_power:
                    self.practiced = False
                if self.replay_end:
                    self.replays = [self.t + 0.05, self.t + 0.1]   # (inside the 0.1 s the next Ready step takes)
            else:
                self.round += 1
                self.set_state('Round ended', f'round won by participant {self.winner}')
        elif d.get('state') == 'Match ended' and self.replays and self.t >= self.replays[0]:
            self.replays.pop(0)
            self.line(self.last_state)   # the identical line again
        if self.t >= self.next_publish:
            self.next_publish = self.t + 0.25
            self.publish()

    def finish_round(self, winner):
        self.winner, self.finish_at = winner, self.t + 0.5
        self.set_state('Finishing round', 'hearts at 0')

    # ---- the steps
    def step(self, src):
        w = src.split()
        k, result, detail, start = w[0], 'done', '', list(self.pos)
        d = self.d or {}
        if k == 'wait':
            self.advance(float(w[1]))
        elif k == 'swing':
            self.practiced = True
            self.advance(0.12)
            dist, bearing = self.to_opp()
            if (self.d or {}).get('state') == 'Duel' and dist <= 1.6 and abs(wrap(bearing - self.face)) <= 40 and \
                    self.match_no not in self.lose_matches:
                self.hearts[1] = max(0, self.hearts[1] - self.HIT)
                self.line(f'state Duel match {self.match_id()} round {self.round} score {self.score[0]}-{self.score[1]} hearts '
                          f'{self.hearts[0]}/{self.hearts[1]} self 0 ready 11 reason ')
                if self.hearts[1] <= 0:
                    self.finish_round(0)
        elif k == 'shield':
            ms = int(w[1]) if len(w) > 1 else 700
            self.shield_until = self.t + ms / 1000
            self.advance(ms / 1000)
        elif k == 'duel' and w[1] == 'ready':
            self.advance(0.1)
            if self.no_duel:
                detail = 'no duel line in the log yet'
            elif self.refuse_always or not self.practiced:
                self.line('Ready refused: swing your sword once so the game can read its native damage' if not self.refuse_always else
                          'Ready refused: native sword contact, damage, shield and arena safety are not proven; no fight started')
                result, detail = 'refused', 'Ready refused'
            elif d.get('state') in ('Countdown', 'Duel', 'Finishing round'):
                self.line('Ready refused: a duel is already running or this player is already ready')
                result, detail = 'refused', 'Ready refused'
            else:
                if d.get('state') == 'Match ended':   # a Ready after a finished match begins a new one
                    self.match_no, self.round, self.score, self.replays = self.match_no + 1, 1, [0, 0], []
                self.hearts, self.ready = [self.HEARTS, self.HEARTS], [1, 1]
                self.pos, self.face = [0.0, 0.0, 0.0], 0.0
                self.countdown_end = self.t + 3.0
                self.set_state('Countdown', 'both ready')
            self.advance(0.4)
        elif k == 'duel' and w[1] == 'cancel':
            self.set_state('Interrupted', 'cancelled')
        elif k == 'face':
            self.face = self.to_opp()[1]
            self.advance(0.4)
        elif k == 'approach':
            dist, bearing = self.to_opp()
            if dist > float(w[1]):
                self.move(bearing, dist - float(w[1]))
                self.advance((dist - float(w[1])) / 4.0)
            result, detail = 'reached', f'{self.to_opp()[0]:.2f} m from the point'
        elif k in ('run', 'walk'):
            x, z = float(w[1]), float(w[2])
            dist = math.hypot(x - self.pos[0], z - self.pos[2])
            self.move(math.degrees(math.atan2(x - self.pos[0], z - self.pos[2])), dist)
            self.advance(dist / 4.0)
            result, detail = 'reached', '0.10 m from the point'
        elif k == 'roll':
            bearing = self.to_opp()[1]
            turn = {'toward': 0.0, 'away': 180.0, 'around-left': 90.0, 'around-right': -90.0}[w[1]]
            self.move(bearing + turn, 2.0)
            self.advance(0.4)
        elif k == 'sidestep':
            self.move(self.to_opp()[1] + (90.0 if w[1] == 'left' else -90.0), 4.0 * int(w[2]) / 1000)
            self.advance(int(w[2]) / 1000)
        elif k != 'watch':
            result = 'bad'
        self.n += 1
        moved = round(math.hypot(self.pos[0] - start[0], self.pos[2] - start[2]), 2)
        return {'ev': 'step', 'n': self.n, 'in': self.lines, 'line': 0, 'src': src, 'result': result, 'secs': 1.0,
                'moved': moved, 'pos': [round(v, 2) for v in self.pos], 'detail': detail, 't': round(self.t, 2)}

    def run(self):
        off, buf = 0, ''
        self.publish()
        self.emit(ev='start', tick=0, steps=0, pos=None)
        self.emit(ev='gameplay', t=0.0, frame=0, area='Fake_Arena')
        waiting, last = False, {}
        while not self.stop:
            data = (self.live / 'steps.txt').read_text()[off:]
            off += len(data)
            buf += data
            *whole, buf = buf.split('\n')
            got = False
            for line in whole:
                self.lines += 1
                s = line.split('#', 1)[0].split()
                if not s:
                    continue
                if s[0] == 'end':
                    self.emit(ev='done', t=round(self.t, 2))
                    return
                self.requests.append(line)
                e = self.step(line)
                self.emit(**e)
                last, got, waiting = {'src': e['src'], 'result': e['result'], 'secs': 1.0, 'moved': e['moved'],
                                      'detail': e['detail']}, True, False
            if not waiting and (got or not self.n):
                self.state(last)
                waiting = True
            time.sleep(0.01)


def duel_play(decider, tmp, max_decisions=None, follows='opponent', budget=None, matches=None, **game_options):
    """A pilot with the duel segment (`matches` = N: a series of N) against a FakeDuelGame; returns (pilot, outcome, game, channel,
    run dir)."""
    seg_path = tmp / f'duel-{time.time_ns()}.toml'
    text = DUEL_SEGMENT if matches is None else series_segment(f'matches = {matches}')
    text = text if budget is None else text.replace('budget_seconds = 300', f'budget_seconds = {budget}')
    seg_path.write_text(text)
    seg = pilot.Segment(seg_path)
    live = tmp / f'live-duel-{time.time_ns()}'
    ch = pilot.Channel(live)
    ch.send(pilot.watch_lines(seg.watch))
    opp_path = tmp / f'opponent-{time.time_ns()}.json'
    game = FakeDuelGame(live, opp_path, **game_options)
    game.start()
    assert ch.wait(lambda e: e['ev'] == 'gameplay', 5)
    st = ch.wait(lambda e: e['ev'] == 'state', 5)
    run_dir = tmp / f'run-duel-{decider.name}-{time.time_ns()}'
    run_dir.mkdir()
    p = pilot.Pilot(seg, decider, ch, run_dir, run_dir.name, lambda: True, None, max_decisions,
                    follows={follows: str(opp_path)}, follow_wait=6.0)
    p.plan = None
    outcome = p.run(st)
    ch.send(['end'])
    ch.wait(lambda e: e['ev'] == 'done', 5)
    game.stop = True
    return p, outcome, game, ch, run_dir


def transcript(run_dir):
    return [json.loads(x) for x in (run_dir / 'transcript.jsonl').read_text().splitlines()]


HEAD_LINE = '[hos 100.250] coop: duel: '


SWING_FIRST = 'Ready refused: swing your sword once so the game can read its native damage'


def duel_state(state='Duel', own=16, opp=16, ready=(0, 0), refusals=0, swing=None, own_score=0, opp_score=0, earlier=0,
               refused_text='Ready refused: not yet', age=3.0):
    """A state line's duel block as hsap makes it from log lines, for the candidate and policy checks. `earlier`: matches
    that ended before this one (each won 2-0 by this game); `age`: how long ago, in game seconds, the state began."""
    t = hsap.DuelTracker()
    for i in range(earlier):
        t.feed(f'{HEAD_LINE}state Match ended match m{i + 100} round 2 score 2-0 hearts 8/0 self 0 ready 00 reason won', 2.0 + i)
    t.feed(f'{HEAD_LINE}state {state} match m1 round 1 score {own_score}-{opp_score} hearts {own}/{opp} self 0 '
           f'ready {ready[0]}{ready[1]} reason test', 10.0 - age)
    for i in range(refusals):
        t.feed(f'{HEAD_LINE}{refused_text}', 10.0)
    if swing:
        t.feed(f'{HEAD_LINE}swing member 2 id {swing[0]} node CutS1 frame 12 dist 1.2 bearing 0.0 dy 0.0 result {swing[1]} '
              f'native 4 amount 4 self_hearts {own}', 10.0 - swing[2])
    return t.snapshot(10.0)


def duel_st(duel, opp=(1.3, 0.0), facing=0.0, t=10.0):
    """The pilot's state line: Link at the origin facing `facing`, the opponent at the given (x, z) (None: no opponent)."""
    st = {'pos': [0.0, 0.0, 0.0], 'facing': facing, 'camera': 0.0, 't': t, 'area': 'Fake_Arena', 'life': 24, 'max_life': 24}
    if duel is not None:
        st['duel'] = duel
    if opp is not None:
        st['opponent'] = hsap.opponent_block(st['pos'], facing, {'x': opp[0], 'z': opp[1], 'w': time.time()}, time.time(), 'Fake_Arena')
    return st


def duel_goal(matches=1):
    return pilot.Goal('duel', pilot.DuelCond(matches), 'duel', [pilot.Target('opponent', 0, 0, kind='duel', follow='opponent')], 'fight',
                      matches=matches)


def labels_of(st, mem=None, goal=None):
    g = goal or duel_goal()
    return [c.label for c in pilot.make_candidates('Fake_Arena', g, g.targets[0], st, {} if mem is None else mem)]


STEP_FORMS = [r'wait [\d.]+', r'swing', r'shield \d+', r'duel (ready|cancel)', r'face( [\d.]+)?', r'approach [\d.]+ timeout \d+',
              r'sidestep (left|right) \d+', r'roll (toward|away|around-left|around-right)']


def duel_candidate_checks():
    g = duel_goal()
    check(isinstance(g.cond, pilot.DuelCond) and not g.cond.met({'X': 1}) and g.cond.name is None, 'a duel goal has a condition no flag can meet')
    seg_path = Path(tempfile.mkdtemp(prefix='duel-seg-')) / 'd.toml'
    seg_path.write_text(DUEL_SEGMENT)
    seg = pilot.Segment(seg_path)
    check(seg.watch == [] and seg.goals[0].kind == 'duel' and seg.goals[0].cond.text == 'the game\'s log says: state Match ended' and
          seg.goals[0].matches == 1 and [t.follow for t in seg.goals[0].targets] == ['opponent', 'opponent-b'],
          'a duel segment needs no flag and watches none; one match unless it says more')
    seg_path.write_text(series_segment())
    s3 = pilot.Segment(seg_path)
    check(s3.goals[0].matches == 3 and s3.goals[0].cond.matches == 3 and 'for 3 different matches' in s3.goals[0].cond.text,
          'matches = 3 in the goal: a series of three, and the condition says so')
    for bad in ('matches = 0', 'matches = -1', 'matches = "3"', 'matches = 2.5', 'matches = true'):
        seg_path.write_text(series_segment(bad))
        try:
            pilot.Segment(seg_path)
        except ValueError:
            check(True, f'`{bad}` is refused')
        else:
            check(False, f'`{bad}` must be refused')
    seg_path.write_text(FOLLOW_SEGMENT.replace('kind = "reach"\ntargets', 'kind = "reach"\nmatches = 2\ntargets'))
    try:
        pilot.Segment(seg_path)
    except ValueError:
        check(True, '`matches` on a goal that is not a duel is refused')
    else:
        check(False, '`matches` on a goal that is not a duel must be refused')

    far, near_ahead = (0.0, 8.0), (0.0, 1.3)
    prac = {'practiced': True}
    mid = {'practiced': True, 'arena_mid': (0.0, 0.65)}   # the middle of the arena, between two players 1.3 m apart
    cases = {
        'no duel line yet': (duel_st(None, opp=far), {}, ['practice-swing']),
        'Read terms': (duel_st(duel_state('Read terms'), opp=far), {}, ['practice-swing']),
        'practised, no duel line yet': (duel_st(None, opp=far), prac, ['ready']),
        'practised, Read terms': (duel_st(duel_state('Read terms'), opp=far), prac, ['ready']),
        'already ready, waiting for him': (duel_st(duel_state('Read terms', ready=(1, 0)), opp=far), prac, ['wait']),
        'Round ended': (duel_st(duel_state('Round ended', own_score=1), opp=far), {}, ['ready']),
        'Ready refused once': (duel_st(duel_state('Read terms', refusals=1), opp=far), prac, ['ready', 'wait']),
        'Ready refused three times in a row': (duel_st(duel_state('Read terms', refusals=3), opp=far), prac,
                                               ['ready', 'wait', 'give-up-goal']),
        'Ready refused: no sword power read': (duel_st(duel_state('Read terms', refusals=1, refused_text=SWING_FIRST), opp=far), prac,
                                               ['practice-swing']),
        'Countdown, he is ahead': (duel_st(duel_state('Countdown', ready=(1, 1)), opp=far), prac, ['wait']),
        'Countdown, he is to the left': (duel_st(duel_state('Countdown', ready=(1, 1)), opp=(8.0, 0.0)), prac, ['face']),
        'Duel, far, the arena\'s middle not known': (duel_st(duel_state(), opp=far), prac, ['approach', 'shield', 'wait']),
        'Duel, far': (duel_st(duel_state(), opp=far), mid, ['approach', 'shield', 'sidestep-left', 'sidestep-right', 'roll-left',
                                                           'roll-right', 'wait']),
        'Duel, in range and in front': (duel_st(duel_state(), opp=near_ahead), mid, ['swing', 'shield', 'sidestep-left',
                                                                                     'sidestep-right', 'roll-left', 'roll-right', 'wait']),
        'Duel, in range but he is to the left': (duel_st(duel_state(), opp=(1.3, 0.0)), mid, ['face', 'shield', 'sidestep-left',
                                                                                              'sidestep-right', 'roll-away', 'roll-right',
                                                                                              'wait']),
        'Duel, far and off to the side': (duel_st(duel_state(), opp=(6.0, 0.0)), mid, ['approach', 'face', 'shield', 'sidestep-left',
                                                                                       'sidestep-right', 'roll-away', 'roll-right', 'wait']),
        'Duel, a little out of reach (1.5 m)': (duel_st(duel_state(), opp=(0.0, 1.5)), prac, ['approach', 'shield', 'wait']),
        'Duel, 1.4 m ahead': (duel_st(duel_state(), opp=(0.0, 1.4)), prac, ['swing', 'shield', 'wait']),
        'Duel, 30 degrees off the front, close': (duel_st(duel_state(), opp=(0.65, 1.13)), prac, ['face', 'swing', 'shield', 'wait']),
        'Duel, no place of him': (duel_st(duel_state(), opp=None), prac, ['shield', 'wait']),
        'Finishing round': (duel_st(duel_state('Finishing round', opp=0), opp=near_ahead), prac, ['wait']),
        'the last match ended': (duel_st(duel_state('Match ended', opp=0, own_score=2), opp=near_ahead), prac, ['wait']),
        'Interrupted': (duel_st(duel_state('Interrupted'), opp=near_ahead), prac, ['wait']),
    }
    for name, (st, mem, want) in cases.items():
        got = labels_of(st, dict(mem))
        check(got == want, f'candidates, {name}: {got}')
    g3 = duel_goal(3)
    for name, (st, want) in {
            'a match ended, two to go': (duel_st(duel_state('Match ended', opp=0, own_score=2), opp=far), ['ready']),
            'a match ended, one to go': (duel_st(duel_state('Match ended', opp=0, own_score=2, earlier=1), opp=far), ['ready']),
            'the third match ended': (duel_st(duel_state('Match ended', opp=0, own_score=2, earlier=2), opp=far), ['wait']),
            'the next match: Read terms': (duel_st(duel_state('Read terms', earlier=1), opp=far), ['ready']),
            'the next match, already ready': (duel_st(duel_state('Read terms', earlier=1, ready=(1, 0)), opp=far), ['wait']),
            'the match ended, Ready refused once': (duel_st(duel_state('Match ended', own_score=2, refusals=1), opp=far),
                                                    ['ready', 'wait']),
            'the match ended, the game wants a swing': (duel_st(duel_state('Match ended', own_score=2, refusals=1, refused_text=SWING_FIRST),
                                                                 opp=far), ['practice-swing'])}.items():
        got = labels_of(st, dict(prac), g3)
        check(got == want, f'candidates, a series of three: {name}: {got}')
    ready = next(c for c in pilot.make_candidates('Fake_Arena', g3, g3.targets[0], duel_st(duel_state('Match ended', own_score=2, earlier=1), opp=far), dict(prac)))
    check(ready.lines == ['duel ready', 'wait 0.5'] and 'next match (match 3 of 3)' in ready.text,
          f'Ready between matches says which match comes next: {ready.text}')
    # Ready for the next round or match waits until the state has lasted a second: the other game must reach it first
    far = (0.0, 8.0)
    for name, st, goal, want in (
            ('Round ended just now', duel_st(duel_state('Round ended', own_score=1, age=0.2), opp=far), None, ['wait']),
            ('Round ended 0.9 s ago', duel_st(duel_state('Round ended', own_score=1, age=0.9), opp=far), None, ['wait']),
            ('Round ended 1 s ago', duel_st(duel_state('Round ended', own_score=1, age=1.0), opp=far), None, ['ready']),
            ('Match ended just now, two to go', duel_st(duel_state('Match ended', opp=0, own_score=2, age=0.1), opp=far), g3, ['wait']),
            ('Match ended 1.5 s ago, two to go', duel_st(duel_state('Match ended', opp=0, own_score=2, age=1.5), opp=far), g3, ['ready']),
            ('Match ended just now, the last', duel_st(duel_state('Match ended', opp=0, own_score=2, age=0.1), opp=far), None, ['wait']),
            ('Read terms just now (no delay)', duel_st(duel_state('Read terms', age=0.1), opp=far), None, ['ready']),
            ('Round ended just now, the game wants a swing', duel_st(duel_state('Round ended', refusals=1, refused_text=SWING_FIRST, age=0.1),
                                                                     opp=far), None, ['practice-swing'])):
        check(labels_of(st, dict(prac), goal) == want, f'candidates, {name}: {labels_of(st, dict(prac), goal)}')
    check([c.lines for c in pilot.make_candidates('Fake_Arena', duel_goal(), duel_goal().targets[0],
                                                  duel_st(duel_state('Round ended', age=0.2), opp=far), dict(prac))] == [['wait 0.5']],
          'the wait before Ready is half a second')
    check(labels_of(duel_st(duel_state('Read terms'), opp=far), {'practiced': True}) == ['ready'],
          'after the practice swing it is not offered again')
    # a refusal that asks for a swing brings the practice swing back once, and a swing since then settles it
    asked = duel_st(duel_state('Read terms', refusals=1, refused_text=SWING_FIRST), opp=far)
    check(labels_of(asked, {'practiced': True, 'practiced_at_refusals': 1}) == ['ready', 'wait'],
          'a practice swing made after that refusal is not asked for again')
    check(labels_of({'pos': None, 'duel': duel_state()}) == ['wait'], 'while the game loads or restarts: wait')
    everything = [labels_of(st, dict(mem)) for st, mem, _ in cases.values()]
    check(all(len(x) == len(set(x)) <= 10 for x in everything), 'at most ten candidates, none twice, in every state')
    check(all(x == ['practice-swing'] or x == ['ready'] or x == ['wait'] or x == ['face'] for x in everything if len(x) == 1),
          'a state with one right move offers just that move')
    st = duel_st(duel_state(), opp=near_ahead)
    cands = pilot.make_candidates('Fake_Arena', duel_goal(), duel_goal().targets[0], st, dict(mid))
    check(all(len(c.text) <= 150 for c in cands) and all(c.text for c in cands), 'every candidate has a short text')
    every_line = [ln for st, mem, _ in cases.values() for c in pilot.make_candidates('Fake_Arena', duel_goal(), duel_goal().targets[0], st, dict(mem))
                  for ln in c.lines]
    check(every_line and all(any(re.fullmatch(form, ln) for form in STEP_FORMS) for ln in every_line),
          f'every step a candidate sends is one hsap knows: {sorted(set(every_line))[:4]} ...')
    check(not any(c.label == 'retreat' for c in cands) and next(c for c in cands if c.label == 'swing').lines == ['swing', 'wait 0.9'],
          'there is no retreat (a roll makes the distance); a swing is a swing and its wait, about a second')
    face = next(c for c in pilot.make_candidates('Fake_Arena', duel_goal(), duel_goal().targets[0],
                                                 duel_st(duel_state(), opp=(1.3, 0.0)), dict(mid)) if c.label == 'face')
    check(face.lines == ['face 12'] and deciders.DUEL['face_to_deg'] < 20 < deciders.DUEL['face_deg'],
          '`face` turns to within 12 degrees, under hsap\'s own 20 and under the 25 that offers it: no loop of no-op faces')
    approach = next(c for c in pilot.make_candidates('Fake_Arena', duel_goal(), duel_goal().targets[0], duel_st(duel_state(), opp=far),
                                                     dict(mid)) if c.label == 'approach')
    check(approach.lines == ['approach 1.3 timeout 5'], 'approach to about 1.3 m')

    # the arena's middle: read at the countdown from the two players' places; moves that carry Link away only to a place near it
    cm = {}
    labels_of(duel_st(duel_state('Countdown', ready=(1, 1)), opp=(4.0, 0.0)), cm)
    check(cm.get('arena_mid') == (2.0, 0.0), f"the countdown reads the middle of the arena (between the spawns): {cm.get('arena_mid')}")
    for name, mem2, want in (('is not known', {}, ['swing', 'shield', 'wait']),
                             ('is where Link stands to fight (a roll away would leave)', {'arena_mid': (0.0, 0.65)},
                              ['swing', 'shield', 'sidestep-left', 'sidestep-right', 'roll-left', 'roll-right', 'wait']),
                             ('lies behind Link (every move keeps him inside)', {'arena_mid': (0.0, -0.65)},
                              ['swing', 'shield', 'sidestep-left', 'sidestep-right', 'roll-away', 'roll-left', 'roll-right', 'wait']),
                             ('is 2 m ahead (only the short moves stay inside)', {'arena_mid': (0.0, 2.0)},
                              ['swing', 'shield', 'sidestep-left', 'sidestep-right', 'wait']),
                             ('is 5 m away (no move is offered)', {'arena_mid': (0.0, 5.0)}, ['swing', 'shield', 'wait'])):
        got = labels_of(duel_st(duel_state(), opp=near_ahead), dict(mem2))
        check(got == want, f'moves that carry Link away, when the arena\'s middle {name}: {got}')
    check(deciders.DUEL['leash_m'] == 3.2, 'the leash is 3.2 m about the middle of the arena (the smallest arena the session makes is 5 m '
                                           'from its middle to an edge, less 1 m of inset)')
    check(abs(pilot.step_seconds('shield 800') - 1.8) < 1e-9 and abs(pilot.step_seconds('sidestep left 350') - 1.35) < 1e-9 and
          pilot.step_seconds('approach 1.3 timeout 5') == 5 and pilot.step_seconds('face 12') == 3 and
          pilot.step_seconds('roll away') == 2 and pilot.step_seconds('swing') == 2 and pilot.step_seconds('duel ready') == 2 and
          pilot.step_seconds('shield') == 1.7, 'the pilot\'s per-step time allowance knows the duel steps')


def duel_rules_checks():
    rules = deciders.Rules()
    g = duel_goal()

    def pick(st, mem, goal=None):
        goal = goal or g
        cands = pilot.make_candidates('Fake_Arena', goal, goal.targets[0], st, mem)
        ctx = deciders.Context(st, goal, goal.targets[0], cands, mem, [])
        label = rules.choose(ctx).label
        assert label in [c.label for c in cands], (label, [c.label for c in cands])
        return label

    def did(mem, label, st=None, result='done'):
        mem.setdefault('history', []).append((label, result, 0.0, None))
        if label == 'practice-swing':   # (as Pilot.run notes it)
            mem['practiced'] = True
            mem['practiced_at_refusals'] = ((st or {}).get('duel') or {}).get('refusals') or 0

    mem, far = {}, (0.0, 8.0)
    seq = []
    for st in (duel_st(None, opp=far), duel_st(None, opp=far)):
        label = pick(st, mem)
        seq.append(label)
        did(mem, label, st)
    check(seq == ['practice-swing', 'ready'], f'before anything: the practice swing, then Ready ({seq})')
    st = duel_st(duel_state('Read terms', refusals=1), opp=far)
    check(pick(st, mem) == 'wait', 'a refused Ready is not repeated at once')
    did(mem, 'wait')
    check(pick(st, mem) == 'ready', 'but after a wait')
    check(pick(duel_st(duel_state('Read terms', refusals=3), opp=far), mem) == 'give-up-goal', 'three refusals in a row: give up')
    check(pick(duel_st(duel_state('Read terms', refusals=2), opp=far), {'practiced': True, 'history': [('wait', 'done', 0.0, None)]}) == 'ready',
          'two refusals: still trying')
    check(pick(duel_st(duel_state('Read terms', ready=(1, 0)), opp=far), {'practiced': True}) == 'wait', 'ready already, waiting for him')
    # a refusal that says the game has read no sword power: the practice swing again, once
    asked, mem4 = duel_st(duel_state('Read terms', refusals=1, refused_text=SWING_FIRST), opp=far), {'practiced': True}
    check(pick(asked, mem4) == 'practice-swing', 'a Ready refused for want of a swing: practise again')
    did(mem4, 'practice-swing', asked)
    check(pick(asked, mem4) == 'ready', 'and, that swing made, Ready (not another swing for the same refusal)')
    young = duel_st(duel_state('Round ended', own_score=1, age=0.3), opp=far)
    check(pick(young, {'practiced': True}) == 'wait' and pick(duel_st(duel_state('Round ended', own_score=1, age=1.2), opp=far), {'practiced': True}) == 'ready',
          'a round just ended: the rules wait a moment, then say Ready')
    check(pick(duel_st(duel_state('Match ended', own_score=2, age=0.2), opp=far), {'practiced': True}, duel_goal(3)) == 'wait' and
          pick(duel_st(duel_state('Match ended', own_score=2, age=2.0), opp=far), {'practiced': True}, duel_goal(3)) == 'ready',
          'a match just ended, more to play: the same wait, then Ready')

    mem = {'practiced': True}
    check(pick(duel_st(duel_state('Countdown', ready=(1, 1)), opp=(8.0, 0.0)), mem) == 'face', 'countdown: turn toward him when he is off to the side')
    check(pick(duel_st(duel_state('Countdown', ready=(1, 1)), opp=far), mem) == 'wait', 'countdown: otherwise wait')

    seq = []
    st_far = duel_st(duel_state(), opp=far)
    seq.append(pick(st_far, mem))
    st_side = duel_st(duel_state(), opp=(1.3, 0.0))
    seq.append(pick(st_side, mem))
    check(seq == ['approach', 'face'], f'in the duel: close in while he is out of reach, then face him ({seq})')
    close = duel_st(duel_state(), opp=(0.0, 1.3))
    swings = [pick(close, mem) for _ in range(6)]
    check(swings == ['swing'] * 6, f'in reach and facing: swing, swing, swing (about once a second each): {swings}')
    check(pick(duel_st(duel_state(), opp=(0.65, 1.13)), mem) == 'face', 'thirty degrees off the front: face him first')
    threat = duel_st(duel_state(swing=(7, 'hit', 0.4)), opp=(0.0, 1.3))
    mem2 = {'practiced': True}
    check(pick(threat, mem2) == 'shield', 'a new swing of his, just judged, with him close: guard')
    check(pick(threat, mem2) == 'swing', 'but once for that swing (the same swing line is not guarded twice)')
    check(pick(duel_st(duel_state(swing=(8, 'shielded', 0.5)), opp=(0.0, 1.3)), mem2) == 'shield', 'a new swing line is a new threat: guard again')
    check(pick(duel_st(duel_state(swing=(9, 'range', 0.4)), opp=(0.0, 4.0)), mem2) == 'approach',
          'a swing of his at long range, and he is still far: no threat, close in')
    check(pick(duel_st(duel_state(swing=(10, 'hit', 3.0)), opp=(0.0, 1.3)), mem2) == 'swing', 'an old swing is no threat')
    check(pick(duel_st(duel_state(swing=(11, 'range', 0.4)), opp=(0.0, 1.3)), {'practiced': True}) == 'shield',
          'a new swing of his that missed by range, and he is now close: he is swinging, guard once (was: no guard; deliberately changed)')
    check(pick(duel_st(duel_state(swing=(12, 'kit', 0.4)), opp=(0.0, 1.3)), {'practiced': True}) == 'swing',
          'a swing line that says only that his kit did not qualify is no threat')
    check(pick(duel_st(duel_state(swing=(13, 'hit', 0.4)), opp=(0.0, 2.6)), {'practiced': True}) == 'approach', 'a new swing, but he is 2.6 m off: not close')
    losing = duel_st(duel_state(own=4, opp=16), opp=(0.0, 1.3))
    check(pick(losing, {'practiced': True}) == 'swing', 'four quarter hearts against sixteen: keep fighting (a retreat gives the initiative away)')
    check(pick(duel_st(duel_state(), opp=None), {'practiced': True}) == 'wait', 'no place of him: wait')
    check(pick(duel_st(duel_state('Finishing round', opp=0), opp=(0.0, 1.3)), {'practiced': True}) == 'wait', 'a round being closed: wait')
    check(pick(duel_st(duel_state('Round ended', own_score=1), opp=far), {'practiced': True}) == 'ready', 'a round ended: Ready again (no second practice swing)')
    check(pick(duel_st(duel_state('Match ended', own_score=2), opp=far), {'practiced': True}) == 'wait', 'the match ended and no more are asked: nothing to do')
    # a series: after a match that is not the last, Ready again, no practice swing
    g3 = duel_goal(3)
    check(pick(duel_st(duel_state('Match ended', own_score=2), opp=far), {'practiced': True}, g3) == 'ready',
          'a match ended, two to go: Ready again for the next match')
    check(pick(duel_st(duel_state('Match ended', own_score=2, earlier=1), opp=far), {'practiced': True}, g3) == 'ready', 'one to go: Ready again')
    check(pick(duel_st(duel_state('Match ended', own_score=2, earlier=2), opp=far), {'practiced': True}, g3) == 'wait', 'the last of three ended: nothing to do')
    check(pick(duel_st(duel_state('Match ended', own_score=2, refusals=3), opp=far), {'practiced': True, 'history': [('wait', 'done', 0.0, None)]}, g3) ==
          'give-up-goal', 'three refusals in a row after a match: give up, as before a first match')

    # the pilot's own view of what the game's log said: canned lines -> hsap's tracker -> candidates -> rules
    t = hsap.DuelTracker()
    for line in (HEAD_LINE + 'state Duel match m1 round 1 score 0-0 hearts 16/16 self 0 ready 11 reason go',
                 HEAD_LINE + 'swing member 2 id 3 node CutS1 frame 11 dist 1.20 bearing 2.0 dy 0.00 result shielded native 4 amount 0 self_hearts 16'):
        t.feed(line, 9.7)
    snap = t.snapshot(10.0)
    check(snap['last_swing']['result'] == 'shielded' and snap['last_swing']['age_s'] == 0.3 and
          pick(duel_st(snap, opp=(0.0, 1.3)), {'practiced': True}) == 'shield',
          'a canned swing line becomes the rules\' reason to guard')

    # duel_over: matches ended by id, interrupted only before they are all ended
    over = pilot.duel_over
    check(over({}) is None and over({'duel': duel_state('Duel')}) is None and over({'duel': duel_state('Match ended', own_score=2)}) == 'met' and
          over({'duel': duel_state('Interrupted')}) == 'interrupted', 'duel_over: met, interrupted or neither, for one match')
    check(over({'duel': duel_state('Match ended', own_score=2)}, 3) is None and over({'duel': duel_state('Match ended', own_score=2, earlier=1)}, 3) is None and
          over({'duel': duel_state('Match ended', own_score=2, earlier=2)}, 3) == 'met', 'duel_over for three: met only when the third has ended')
    check(over({'duel': duel_state('Interrupted', earlier=1)}, 3) == 'interrupted' and over({'duel': duel_state('Interrupted', earlier=3)}, 3) == 'met',
          'an interrupted second match ends the run; an Interrupted after the last match ended does not undo it')

    # the gap before a request is waited out only when a request will be made (two candidates or more)
    import types
    asking = types.SimpleNamespace(decider=types.SimpleNamespace(min_gap_s=1.5), mem={}, with_opponent=lambda st, target: st)
    free = types.SimpleNamespace(decider=types.SimpleNamespace(), mem={}, with_opponent=lambda st, target: st)
    one, many = duel_st(duel_state('Countdown', ready=(1, 1)), opp=far), duel_st(duel_state(), opp=(0.0, 1.3))
    asking.mem[('duel', 'opponent')] = {'practiced': True}
    check(not pilot.Pilot.pace_due(asking, one, g, g.targets[0]) and pilot.Pilot.pace_due(asking, many, g, g.targets[0]) and
          not pilot.Pilot.pace_due(free, many, g, g.targets[0]), 'the pilot waits out the gap before a decision with a request to make, not before a single candidate, and not for a free decider')

class ModelStub(BaseHTTPRequestHandler):
    """The Decisions API as a model that is not the rules: swing when it can, else practice, Ready, approach, face, wait."""
    SEEN = []
    ORDER = ('practice-swing', 'ready', 'swing', 'approach', 'face', 'wait')

    def log_message(self, *a):
        pass

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        body = json.loads(raw)
        self.SEEN.append({'path': self.path, 'headers': dict(self.headers), 'body': body})
        labels = [c['value'] for c in body['questions'][0]['choices']]
        pick = next((w for w in self.ORDER if w in labels), labels[0])
        tokens = len(raw) // 4
        out = json.dumps({'answers': [{'type': 'choice', 'name': 'next_step', 'choice': pick, 'confidence': 0.7}],
                          'model': body['model'], 'usage': {'input_tokens': tokens, 'output_tokens': 0,
                                                           'input_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0}}}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(out)))
        self.end_headers()
        self.wfile.write(out)


class PricedClient:
    """Stands in for openai_api.Client with the model's own price: the real cap checks, the same answers as ModelStub, and a
    ledger row costed from the tokens (openai_api.cost), so that cost accounting can be checked without a paid call."""
    def __init__(self, run_id, fail_after=None):
        self.run_id, self.requests = run_id, 0
        self.caps = openai_api.Client(run_id, 'fake-duel', 'http://127.0.0.1:9/v1')

    def post(self, path, body, *, api, model, kind, estimate, timeout=30.0):
        self.caps.check_caps(kind, estimate)
        labels = [c['value'] for c in body['questions'][0]['choices']]
        pick = next((w for w in ModelStub.ORDER if w in labels), labels[0])
        usage = {'input_tokens': len(json.dumps(body)) // 4, 'output_tokens': 0,
                 'input_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0}}
        row = {'ts': time.time(), 'run': self.run_id, 'segment': 'fake-duel', 'kind': kind, 'api': api, 'model': model, 'status': 200,
               'latency_ms': 5.0, 'usage': usage, 'cost_usd': openai_api.cost(api, model, usage)}
        openai_api._append(row, openai_api.LEDGER)
        self.requests += 1
        return {'answers': [{'type': 'choice', 'name': 'next_step', 'choice': pick, 'confidence': 0.7}]}, 5.0, row


def duel_play_checks(tmp):
    # the rules decider plays a whole duel against the fake game
    rules = deciders.Rules()
    p, outcome, game, ch, run_dir = duel_play(rules, tmp)
    tr = transcript(run_dir)
    dec = [e for e in tr if e['kind'] == 'decision']
    check(outcome == 'solved' and p.seg.goals[0].status == 'met', f'the rules win a made-up duel end to end ({outcome}, {len(dec)} decisions)')
    d = p.duel_seen
    check(d['state'] == 'Match ended' and d['own_score'] == 2 and d['opp_score'] == 0 and d['refusals'] == 0,
          f"the game's log ended it: {d['state']} {d['own_score']}-{d['opp_score']}, no refusal")
    check([e['choice'] for e in dec[:2]] == ['practice-swing', 'ready'], 'the practice swing came before the first Ready')
    check(p.decisions.count('ready') == 2 and p.decisions.count('practice-swing') == 1,
          f"Ready once per round, one practice swing: {sorted(set(p.decisions))}")
    check({'approach', 'swing', 'shield'} <= set(p.decisions), 'it closed in, swung and guarded')
    check(all('duel' in e['state'] for e in dec[2:]) and all('opponent' in e['state'] for e in dec),
          'every decision after the first Ready saw the duel block, and every one the opponent\'s place')
    check(all(e['state']['opponent']['age_s'] < 5 for e in dec), 'the opponent block is made from the follow file as it is at the decision')
    steps = [e for e in ch.events if e['ev'] == 'step' and e.get('in')]
    check(not [e for e in ch.events if e['ev'] == 'bad'] and not [s for s in steps if s['result'] == 'bad'], 'the fake game knew every step sent')
    check(sum(1 for s in steps if s['src'] == 'duel ready') == 2 and not any('Ready refused' in x for x in game.log_lines),
          'two Readys, none refused')
    check(p.duel_seen['swings'].get('hit', 0) >= 1 and p.duel_seen['swings'].get('hit', 0) <= 6,
          'his swings landed on us at times (a hit was counted) and the match was still won')

    # a follow name this side was not given: the other target is dropped; a duel with the second name works the same
    p2, outcome2, _, _, _ = duel_play(deciders.Rules(), tmp, follows='opponent-b')
    check(outcome2 == 'solved' and [t.name for t in p2.seg.goals[0].targets] == ['opponent-b'],
          'a pilot given only `opponent-b` keeps that target and plays the same duel')

    # a build that refuses Ready (r16: HOS_COOP_HITS_TRACE): three tries, then the goal is given up, with the reason kept
    p3, outcome3, game3, _, run3 = duel_play(deciders.Rules(), tmp, refuse_always=True)
    d3 = p3.duel_seen
    check(outcome3 == 'gave up: every open goal failed' and d3['refusals'] == 3 and 'no fight started' in d3['refused'] and
          p3.decisions.count('ready') == 3 and p3.decisions[0] == 'practice-swing',
          f'a refused Ready is tried three times, then given up ({outcome3}, {d3["refusals"]} refusals)')

    # the match is interrupted
    p4, outcome4, _, _, run4 = duel_play(deciders.Rules(), tmp, interrupt_at=6.0)
    check(outcome4 == 'duel interrupted: arena left' and p4.seg.goals[0].status == 'failed',
          f'an Interrupted ends the run with the reason ({outcome4})')
    check(any(e['kind'] == 'goal' and e['status'] == 'failed' and 'arena left' in e['why'] for e in transcript(run4)),
          'and the transcript says why')

    # budgets: decisions and game time
    p5, outcome5, _, _, _ = duel_play(deciders.Rules(), tmp, max_decisions=7)
    check(outcome5 == 'budget: 7 decisions' and len(p5.decisions) == 7, f'the decision budget ends a duel ({outcome5})')
    p6, outcome6, _, _, _ = duel_play(deciders.Rules(), tmp, budget=12)
    check(outcome6 == 'budget: 12 s of game time', f'the game-time budget ends a duel ({outcome6})')


def duel_series_checks(tmp):
    # a series against the fake game, with the rules: every match that ended is counted by its id
    rules = deciders.Rules()
    first, second, third = (str((n << 32) | 7) for n in (1, 2, 3))
    p, outcome, game, ch, run_dir = duel_play(rules, tmp, matches=2)
    d, tr = p.duel_seen, transcript(run_dir)
    dec = [e for e in tr if e['kind'] == 'decision']
    check(outcome == 'solved' and p.seg.goals[0].status == 'met' and d['matches_ended'] == 2 and d['matches_won'] == 2 and d['matches_lost'] == 0,
          f"a series of two: both matches won, the goal met only when the second ended ({outcome}, {len(dec)} decisions)")
    check([m['id'] for m in d['match_results']] == [first, second] and all(m['won'] and m['own_score'] == 2 for m in d['match_results']),
          'the two matches are told apart by the ids of their `Match ended` lines')
    check(p.decisions.count('practice-swing') == 1 and p.decisions.count('ready') == 4 and game.requests.count('duel ready') == 4 and
          not any('Ready refused' in x for x in game.log_lines),
          'one practice swing, then Ready for every round of both matches: four, none refused (a Ready after Match ended is the next match)')
    between = [i for i, e in enumerate(dec) if (e['state'].get('duel') or {}).get('state') == 'Match ended' and
               e['state']['duel']['matches_ended'] == 1]
    check(between and [dec[i]['choice'] for i in between][-1] == 'ready' and dec[between[0]]['choice'] == 'wait' and
          dec[between[0]]['state']['duel']['match'] == first,
          'after the first match ended the pilot waited a moment, then said Ready again: '
          f"{[dec[i]['choice'] for i in between]}")
    ready_rows = [e for e in dec if e['choice'] == 'ready' and (e['state'].get('duel') or {}).get('state') in ('Round ended', 'Match ended')]
    check(len(ready_rows) == 3 and all(e['state']['duel']['in_state_s'] >= 1.0 for e in ready_rows),
          'Ready after a round or a match came only once that state had lasted a second (three: after each of round 1 of both matches and match 1)')
    met = [i for i, e in enumerate(tr) if e['kind'] == 'goal' and e['status'] == 'met']
    check(len(met) == 1 and met[0] > tr.index(dec[between[0]]),
          'the goal row (met) is written once, long after the first match ended')
    check(outcome == 'solved' and p.mem[('duel', 'opponent')].get('arena_mid') is not None,
          'the arena\'s middle was read at a countdown and kept for the whole series')

    # three matches, the second lost: 2 won, 1 lost, solved when the third ended
    p, outcome, game, ch, run_dir = duel_play(rules, tmp, matches=3, lose_matches=(2,))
    d = p.duel_seen
    check(outcome == 'solved' and d['matches_ended'] == 3 and d['matches_won'] == 2 and d['matches_lost'] == 1 and
          [m['won'] for m in d['match_results']] == [True, False, True] and [m['own_score'] for m in d['match_results']] == [2, 0, 2],
          f"three matches, the second lost: won {d['matches_won']}, lost {d['matches_lost']} ({outcome})")
    check(game.requests.count('duel ready') == 6, f"Ready per round, 2 + 2 + 2 over the three matches: {game.requests.count('duel ready')}")

    # a match interrupted: the run ends there, with what ended before it
    p, outcome, game, ch, run_dir = duel_play(rules, tmp, matches=3, interrupt_in=(2, 4.0))
    d = p.duel_seen
    check(outcome == 'duel interrupted: arena left' and p.seg.goals[0].status == 'failed' and d['matches_ended'] == 1 and d['state'] == 'Interrupted' and
          d['match'] == second, f"the second match interrupted ends the run; the first is kept ({outcome}, {d['matches_ended']} ended)")
    check(any(e['kind'] == 'goal' and e['status'] == 'failed' and 'arena left' in e['why'] for e in transcript(run_dir)),
          'and the transcript says why')
    # the first match interrupted
    p, outcome, game, ch, run_dir = duel_play(rules, tmp, matches=2, interrupt_in=(1, 3.0))
    check(outcome == 'duel interrupted: arena left' and p.duel_seen['matches_ended'] == 0, 'the first match interrupted: nothing ended')

    # the game logs the last line again, identical (a replay): still one match
    p, outcome, game, ch, run_dir = duel_play(rules, tmp, matches=2, replay_end=True)
    d = p.duel_seen
    ended_lines = [x for x in game.log_lines if 'state Match ended' in x]
    check(len(ended_lines) >= 4 and outcome == 'solved' and d['matches_ended'] == 2 and [m['id'] for m in d['match_results']] == [first, second],
          f"{len(ended_lines)} `Match ended` lines for two matches (the first one repeated): two matches counted, the series went on to the second")
    check(game.requests.count('duel ready') == 4, 'the replayed lines made no extra Ready and did not end the run after the first match')

    # the game forgets the sword's power between matches: a refused Ready asks for a swing, the pilot practises again, once
    p, outcome, game, ch, run_dir = duel_play(rules, tmp, matches=2, forget_power=True)
    d = p.duel_seen
    check(outcome == 'solved' and d['matches_ended'] == 2 and p.decisions.count('practice-swing') == 2 and d['refusals'] == 1 and
          sum('swing your sword' in x for x in game.log_lines) == 1,
          f"a Ready refused for want of a swing brings back the practice swing ({p.decisions.count('practice-swing')} in all, "
          f"{d['refusals']} refusal)")
    check(d['refusal_run'] == 0, 'and the next Countdown ended the run of refusals')

    # refusals do not add up across matches: one refusal in each of three matches is not three in a row
    p, outcome, game, ch, run_dir = duel_play(rules, tmp, matches=3, forget_power=True)
    d = p.duel_seen
    check(outcome == 'solved' and d['matches_ended'] == 3 and d['refusals'] == 2 and p.decisions.count('practice-swing') == 3,
          f"two refusals (one a match) and three practice swings over three matches: no give-up ({outcome})")

    # a series budget scales: --matches on a segment, and a segment's own
    seg_path = tmp / 'budget-series.toml'
    seg_path.write_text(DUEL_SEGMENT.replace('budget_seconds = 300', 'budget_seconds = 300\nwall = 900'))
    one = pilot.Segment(seg_path)
    check(one.goals[0].matches == 1 and one.budget == 300 and one.max_decisions == 200, 'a single-match segment: its own budgets')
    one.set_matches(5)
    check(one.goals[0].matches == 5 and one.goals[0].cond.matches == 5 and one.budget == 1500 and one.max_decisions == 1000 and
          'for 5 different matches' in one.goals[0].cond.text, '--matches 5 on it: five matches asked for, the budgets times five')
    seg_path.write_text(series_segment('matches = 3'))
    three = pilot.Segment(seg_path)
    three.set_matches(6)
    check(three.budget == 600 and three.max_decisions == 400 and three.goals[0].matches == 6,
          'a segment written for three, asked for six: the budgets double')
    three.set_matches(6)
    check(three.budget == 600, 'the same N again changes nothing')
    for bad in (0, -2):
        try:
            pilot.Segment(seg_path).set_matches(bad)
        except ValueError:
            check(True, f'--matches {bad} is refused')
        else:
            check(False, f'--matches {bad} must be refused')
    seg_path.write_text(FOLLOW_SEGMENT)
    try:
        pilot.Segment(seg_path).set_matches(2)
    except ValueError:
        check(True, '--matches on a segment with no duel goal is refused')
    else:
        check(False, '--matches on a segment with no duel goal must be refused')


def duel_series_model_checks(tmp):
    # the model's request for a series says which match it is and how the series stands; a single match's request is unchanged
    run_id = 'duel-series-cost'
    client = PricedClient(run_id)
    p, outcome, game, ch, run_dir = duel_play(deciders.Decisions(client), tmp, matches=3, lose_matches=(2,))
    tr = transcript(run_dir)
    asked = [e for e in tr if e['kind'] == 'decision' and 'request' in e]
    whats = [e['request']['input'][1]['content'][1]['data']['goal']['what'] for e in asked]
    lines = [w.rsplit('\n', 1)[1] if '\n' in w else None for w in whats]
    check(outcome == 'solved' and p.duel_seen['matches_ended'] == 3 and len(asked) >= 20, f'the model plays three matches ({outcome}, {len(asked)} requests)')
    check(all(lines) and all(w.startswith(DUEL_SEGMENT.split('what = "')[2].split('"')[0] + '\n') for w in whats),
          'every request\'s goal text is the segment\'s text with one more line')
    want = []
    for e in asked:
        d = e['state'].get('duel') or {}
        want.append(f"match {min((d.get('matches_ended') or 0) + 1, 3)} of 3, matches won {d.get('matches_won') or 0} / lost {d.get('matches_lost') or 0} so far")
    check(lines == want, f'the line says which match this is and the score so far ({sorted(set(lines))})')
    check({'match 1 of 3, matches won 0 / lost 0 so far', 'match 2 of 3, matches won 1 / lost 0 so far', 'match 3 of 3, matches won 1 / lost 1 so far'} <=
          set(lines), 'all three matches appear, with 1-0 and 1-1 after the first and second')
    check(all('match_results' not in json.dumps(e['request']) and 'seq' not in e['request']['input'][1]['content'][1]['data']['duel'] and
              'hearts' not in e['request']['input'][1]['content'][1]['data']['duel'] for e in asked if e['request']['input'][1]['content'][1]['data']['duel']),
          'the ledger shown to the model has no duplicates of own/opp hearts, scores and ready flags, and no list of past match ids')
    check(all(set(e['request']['input'][1]['content'][1]['data']['link']) == {'t', 'pos', 'facing'} for e in asked),
          'Link\'s real life is not shown (the duel\'s hearts are separate)')
    swings = [e['request']['input'][1]['content'][1]['data']['duel']['last_swing'] for e in asked
              if (e['request']['input'][1]['content'][1]['data']['duel'] or {}).get('last_swing')]
    check(swings and all(set(s) == {'id', 'result', 'dist', 'amount', 'age_s'} for s in swings), 'his last swing is shown by id, result, distance, amount and age')
    ts = [e['state']['t'] for e in asked]
    check(all(b - a >= 1.45 for a, b in zip(ts, ts[1:])), f'over three matches the requests stay 1.5 s of game time apart (smallest gap {min(b - a for a, b in zip(ts, ts[1:])):.2f} s)')
    rows = [r for r in openai_api.ledger_rows() if r.get('run') == run_id]
    check(len(rows) == len(asked) == client.requests and sum(r['cost_usd'] for r in rows) < 0.01,
          f"every request is in the ledger and the series cost {sum(r['cost_usd'] for r in rows):.6f} USD")
    one_candidate = [e for e in tr if e['kind'] == 'decision' and len(e['candidates']) == 1]
    check(one_candidate and all(e.get('no_request') for e in one_candidate) and all('request' not in e for e in one_candidate) and
          {e['choice'] for e in one_candidate} >= {'practice-swing', 'ready', 'wait'},
          'the practice swing, Ready and the waits (one candidate each) cost no request in a whole series')
    p1, outcome1, _, _, run1 = duel_play(deciders.Decisions(PricedClient('duel-single-cost')), tmp)
    asked1 = [e for e in transcript(run1) if e['kind'] == 'decision' and 'request' in e]
    check(outcome1 == 'solved' and asked1 and all('\nmatch ' not in e['request']['input'][1]['content'][1]['data']['goal']['what'] and
                                                  e['request']['input'][1]['content'][1]['data']['goal']['met_when'] == "the game's log says: state Match ended"
                                                  for e in asked1), 'a single match\'s request has no match line and its old condition text')


def duel_model_checks(tmp):
    srv = ThreadingHTTPServer(('127.0.0.1', 0), ModelStub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{srv.server_address[1]}/v1'
    os.environ['OPENAI_API_KEY'] = 'sk-test-must-never-be-sent'
    try:
        client = openai_api.Client('duel-model', 'fake-duel', base)
        decider = deciders.Decisions(client)
        p, outcome, game, ch, run_dir = duel_play(decider, tmp)
        series = duel_play(deciders.Decisions(openai_api.Client('duel-model-series', 'fake-duel', base)), tmp, matches=2)
    finally:
        del os.environ['OPENAI_API_KEY']
        srv.shutdown()
    ps, outcome_s, _, _, run_s = series
    tr_s = transcript(run_s)
    asked_s = [e for e in tr_s if e['kind'] == 'decision' and 'request' in e]
    lines_s = {e['request']['input'][1]['content'][1]['data']['goal']['what'].rsplit('\n', 1)[-1] for e in asked_s}
    check(outcome_s == 'solved' and ps.duel_seen['matches_ended'] == 2 and 'match 1 of 2, matches won 0 / lost 0 so far' in lines_s and
          'match 2 of 2, matches won 1 / lost 0 so far' in lines_s and not [e for e in tr_s if e['kind'] == 'decision' and 'fallback' in e],
          f'a series of two through the real client and the stub: solved, the request says which match it is ({sorted(lines_s)})')
    tr = transcript(run_dir)
    dec = [e for e in tr if e['kind'] == 'decision']
    asked = [e for e in dec if 'request' in e]
    check(outcome == 'solved', f'a model that is not the rules wins the made-up duel through the real client and a stub ({outcome}, '
                               f'{len(dec)} decisions, {len(asked)} requests)')
    body = asked[0]['request']
    check(body['model'] == 'gpt-6-luna' and [q['type'] for q in body['questions']] == ['choice'] and
          body['input'][0]['content'] == deciders.DUEL_DEVELOPER and
          [x['value'] for x in body['questions'][0]['choices']] == [x['label'] for x in asked[0]['candidates']],
          'the duel request: the duel prompt, one choice question over the candidates')
    data = body['input'][1]['content'][1]['data']
    check(set(data) == {'link', 'duel', 'opponent', 'goal', 'recent_moves'} and 'quarter hearts' in data['goal']['what'] and
          data['goal']['met_when'] == 'the game\'s log says: state Match ended' and 'flags' not in data['link'],
          'its data: Link, the duel ledger, the opponent, the goal text, the last moves (no flags)')
    check(len(json.dumps(body)) < 6000, f'a request is small ({len(json.dumps(body))} characters)')
    check(all(s['headers'].get('Authorization') == 'Bearer standin' for s in ModelStub.SEEN) and
          not any('sk-test' in json.dumps(s['body']) for s in ModelStub.SEEN), 'the key is not in any request body or header')
    check(all('fallback' not in e for e in dec), 'no decision fell back to the rules')
    check([e for e in dec if e.get('no_request')] and all('request' not in e for e in dec if e.get('no_request')),
          'a state with one candidate (countdown, a round being closed) makes no request')
    # at most one request per 1.5 s of game time
    ts = [e['state']['t'] for e in asked]
    check(len(ts) >= 5 and all(b - a >= 1.45 for a, b in zip(ts, ts[1:])),
          f'requests are at least 1.5 s of game time apart (smallest gap {min(b - a for a, b in zip(ts, ts[1:])):.2f} s over {len(ts)})')
    check([e for e in tr if e['kind'] == 'pace'], 'the pilot waited out the rest of the gap when a move ended early')
    check((ts[-1] - ts[0]) / (len(ts) - 1) >= 1.45, f'so over the duel one request in {(ts[-1] - ts[0]) / (len(ts) - 1):.2f} s of game time')
    led = openai_api.summary('duel-model', standin=True)
    check(led['decision']['requests'] == len(asked) and led['decision']['errors'] == 0, 'every request is in the (stand-in) ledger')

    # a second request inside the gap is refused by the decider itself (the guarantee behind the pacing)
    class Never:
        def post(self, *a, **k):
            raise AssertionError('no request inside the gap')
    d2 = deciders.Decisions(Never(), model='gpt-6-luna')
    d2.last_request_t = 10.0
    g = duel_goal()
    st = duel_st(duel_state(), opp=(0.0, 1.3), t=10.8)
    cands = pilot.make_candidates('Fake_Arena', g, g.targets[0], st, {'practiced': True})
    ch2 = d2.choose(deciders.Context(st, g, g.targets[0], cands, {'practiced': True}, []))
    check('throttled' in ch2.info and ch2.label in [c.label for c in cands] and 'request' not in ch2.info,
          f"0.8 s after a request the decider makes none: {ch2.info['throttled']}")


def duel_cost_checks(tmp):
    # cost accounting: every request in the ledger, with the cost from the tokens, the same sums in the transcript, the caps respected
    run_id = 'duel-cost'
    client = PricedClient(run_id)
    p, outcome, _, _, run_dir = duel_play(deciders.Decisions(client), tmp)
    dec = [e for e in transcript(run_dir) if e['kind'] == 'decision' and 'cost_usd' in e]
    rows = [r for r in openai_api.ledger_rows() if r.get('run') == run_id]
    check(outcome == 'solved' and len(dec) == len(rows) == client.requests and len(rows) >= 5,
          f'{len(rows)} requests: each decision that asked the model has its ledger row ({outcome})')
    spent = openai_api.spent(run_id)['run']
    check(abs(spent - sum(e['cost_usd'] for e in dec)) < 1e-12 and spent > 0,
          f"the ledger's {spent:.6f} USD for the run is the sum of the decisions' costs in the transcript")
    check(all(0 < r['cost_usd'] <= deciders.Decisions.MAX_COST for r in rows) and
          all(abs(r['cost_usd'] - openai_api.cost('decisions', 'gpt-6-luna', r['usage'])) < 1e-12 for r in rows),
          'each cost is its tokens at the published price, under 0.002 USD a decision')
    check(max(r['cost_usd'] for r in rows) < 0.0005, f"a decision costs about {sum(r['cost_usd'] for r in rows) / len(rows):.6f} USD")
    # a run cap stops the model mid-duel: the pilot ends 'stopped', the last request's cost still counted
    caps = openai_api.CAPS.read_text()
    first = rows[0]['cost_usd']
    openai_api.CAPS.write_text(json.dumps({'per_run_usd': first * 3.5, 'per_night_usd': 50, 'total_usd': 400,
                                           'planner_share_of_night': 0.4, 'model': None}))
    try:
        run2 = 'duel-cost-capped'
        client2 = PricedClient(run2)
        p2, outcome2, _, _, _ = duel_play(deciders.Decisions(client2), tmp)
    finally:
        openai_api.CAPS.write_text(caps)
    check(outcome2.startswith('stopped: cap: run cap') and 1 <= client2.requests <= 3 and
          openai_api.spent(run2)['run'] <= first * 3.5 + 1e-9,
          f'the per-run cap stops the model after {client2.requests} requests ({outcome2})')


def duel_segment_checks():
    segs = HERE / 'segments'
    if not (segs / 'duel.toml').is_file() or not (segs / 'duel-series.toml').is_file() or not (segs / 'duel-child.toml').is_file():
        print('skip: the duel segments are game data kept out of the published tree (pilot/segments/duel*.toml): their checks run where the folder is')
        return
    for name in ('duel.toml', 'duel-child.toml'):
        seg = pilot.Segment(segs / name)
        save, area = seg.save, seg.area
        g = seg.goals[0]
        check(bool(save) and bool(area) and g.kind == 'duel' and seg.watch == [] and
              [t.follow for t in g.targets] == ['opponent', 'opponent-b'] and seg.boot == 'continue',
              f'{name}: a save, an area, a duel goal with two follow names and no flag')
        check((pilot.LIBRARY / save / 'save').is_dir(), f'{name}: the library save {save} exists')
        text = g.what
        check(all(w in text for w in ('quarter-heart', 'shield', 'hearts reach 0', 'best of three', 'practice swing', 'Ready', 'swing (Y)',
                                      'roll', 'invulnerable')) and len(text) < 2500,
              f'{name}: the goal text carries the rules (what hits, the shield, hearts, the round end) in {len(text)} characters')
        check(seg.max_decisions >= 300 and seg.budget >= 300, f'{name}: budgets for a best-of-three at one decision a second or two')
    one, many = pilot.Segment(segs / 'duel.toml'), pilot.Segment(segs / 'duel-series.toml')
    g1, g3 = one.goals[0], many.goals[0]
    check(g1.matches == 1 and g3.matches == 3 and g3.cond.matches == 3 and g3.cond.text == 'the game\'s log says: state Match ended for 3 different matches',
          'duel.toml asks for one match (its default), duel-series.toml for three')
    check((many.area, many.save, many.boot, many.wall) == (one.area, one.save, one.boot, one.wall) and g3.what == g1.what and
          g3.kind == g1.kind and [(t.name, t.follow, t.kind, t.radius) for t in g3.targets] == [(t.name, t.follow, t.kind, t.radius) for t in g1.targets] and
          many.watch == one.watch and many.name == 'duel-series',
          'duel-series.toml is duel.toml: the same area, save, boot, wall, goal text and follow targets')
    check(many.budget == 3 * one.budget and many.max_decisions == 3 * one.max_decisions and many.budget == 1200 and many.max_decisions == 1200,
          'and its budgets are three times duel.toml\'s (1200 s of game time from the first decision, 1200 decisions)')
    check(pilot.Segment(segs / 'duel-child.toml').goals[0].what == g1.what, 'the child segment\'s goal text is the same text')


def duel_cmd_run_checks(tmp):
    """`pilot.py run` end to end for a duel segment, with a fake hsap process (FakeDuelGame behind hsap's command line): the
    arguments the pilot gives hsap, the summary, the ledger, and that no route is exported for a fight."""
    import argparse
    fake = tmp / 'fake_hsap.py'
    fake.write_text(
        "import json, sys\nfrom pathlib import Path\n"
        f"sys.path.insert(0, {str(HERE)!r})\nimport test_pilot\n"
        "a = sys.argv[1:]\nlive = Path(a[a.index('--live') + 1])\nlive.mkdir(parents=True, exist_ok=True)\n"
        "(live / 'argv.json').write_text(json.dumps(a))\n"
        "test_pilot.FakeDuelGame(live, Path(a[a.index('--opponent') + 1])).run()\n")
    seg_path = tmp / 'duel-cmd.toml'
    seg_path.write_text(DUEL_SEGMENT)
    opp = tmp / 'cmd-opponent.json'
    saved = pilot.HSAP
    pilot.HSAP = fake
    try:
        args = argparse.Namespace(segment=str(seg_path), decider='rules', replay=None, planner=False, copy=str(tmp / 'copy'),
                                  tag='duel-cmd-run', attach=None, save=None, wall=60, max_decisions=None,
                                  follow=[f'opponent-b={opp}'], end_hold=0.0, shots=12, api_base=None, allowance_usd=None,
                                  allowance_since='2026-01-01', matches=None)
        code = pilot.cmd_run(args)
        args2 = argparse.Namespace(**{**vars(args), 'tag': 'duel-cmd-run-series', 'matches': 2})   # --matches 2: a series of two
        code2 = pilot.cmd_run(args2)
    finally:
        pilot.HSAP = saved
    run_dir = pilot.HERE / 'runs' / 'duel-cmd-run'
    summary = json.loads((run_dir / 'summary.json').read_text())
    argv = json.loads((run_dir / 'live' / 'argv.json').read_text())
    check(code == 0 and summary['outcome'] == 'solved' and summary['goals'] == {'duel': 'met'}, f"pilot.py run on a duel segment: {summary['outcome']}")
    check(argv[argv.index('--opponent') + 1] == str(opp) and '--analog' in argv and argv[argv.index('--shots') + 1] == '12',
          'hsap is started with --opponent <the follow file the pilot was given>, exact stick angles and the picture cadence')
    check(summary['duel']['state'] == 'Match ended' and summary['duel']['own_score'] == 2 and summary['labels']['ready'] == 2,
          'the summary keeps the last duel block and the labels chosen')
    check(summary['ledger'] == {} and 'route' not in summary and not list(pilot.HERE.glob('routes/*duel*')),
          'the rules cost nothing, and a duel is not exported as a route')
    check((run_dir / 'transcript.jsonl').exists() and (run_dir / 'out.jsonl').exists(), 'the transcript and the events are kept with the run')
    check(summary['matches'] == {'wanted': 1, 'ended': 1, 'won': 1, 'lost': 0,
                                 'results': [{'id': str((1 << 32) | 7), 'own_score': 2, 'opp_score': 0, 'won': True}]},
          'the summary says how many matches were wanted and how many ended, won and lost, by id')
    run2 = pilot.HERE / 'runs' / 'duel-cmd-run-series'
    summary2 = json.loads((run2 / 'summary.json').read_text())
    check(code2 == 0 and summary2['outcome'] == 'solved' and summary2['goals'] == {'duel': 'met'} and
          summary2['matches']['wanted'] == 2 and summary2['matches']['ended'] == 2 and summary2['matches']['won'] == 2 and
          [m['id'] for m in summary2['matches']['results']] == [str((1 << 32) | 7), str((2 << 32) | 7)] and summary2['labels']['ready'] == 4,
          f"`pilot.py run --matches 2` on a one-match segment plays two matches: {summary2['outcome']}, {summary2['matches']['ended']} ended")
    # attach mode, as the duel session uses it (an hsap it started itself): no hsap is started, a series of two is played, and the pilot's
    # `end` is what ends the game side
    live = tmp / 'attach-live'
    attach_opp = tmp / 'attach-opponent.json'
    pilot.Channel(live)   # (the folder and steps.txt, as hsap makes them)
    attached = FakeDuelGame(live, attach_opp)
    attached.start()
    pilot.HSAP = tmp / 'there-is-no-hsap-to-start.py'
    try:
        args3 = argparse.Namespace(**{**vars(args), 'tag': 'duel-cmd-run-attach', 'attach': str(live), 'follow': [f'opponent={attach_opp}'],
                                      'matches': 2, 'shots': 0})
        code3 = pilot.cmd_run(args3)
    finally:
        pilot.HSAP = saved
    summary3 = json.loads((pilot.HERE / 'runs' / 'duel-cmd-run-attach' / 'summary.json').read_text())
    events3 = [json.loads(x) for x in (live / 'out.jsonl').read_text().splitlines()]
    check(code3 == 0 and summary3['outcome'] == 'solved' and 'runner' not in summary3 and summary3['live'] == str(live) and
          summary3['matches']['ended'] == 2 and summary3['matches']['wanted'] == 2 and events3[-1]['ev'] == 'done',
          f"attached to a game side it did not start: two matches played, hsap not started, the pilot's end ended the game side ({summary3['outcome']})")


def duel_feed_checks(tmp):
    """follow_feed: the other pilot's state journal becomes this pilot's follow file: gated, atomic, fresh or nothing."""
    import types
    src, dest, gate = tmp / 'feed-state.jsonl', tmp / 'feed-follow.json', tmp / 'feed-gate'

    def sample(i, x=6.5, z=15.7):
        return json.dumps({'t': 100.0 + i / 10, 'frame': 6 * i, 'map': 'Fake_Arena', 'pos': [x, 55.52, z], 'facing': 0.0})
    src.write_text(''.join(sample(i, z=15.7 + i) + '\n' for i in range(5)))
    f = follow_feed.Feeder(src, dest, gate=str(gate), hz=50)
    check(f.once() is False and not dest.exists() and f.skipped['gate'] == 1, 'nothing is written before the gate file exists')
    gate.write_text('')
    check(f.once() is True, 'after the gate the last sample of the journal is copied')
    got = json.loads(dest.read_text())
    check(got['x'] == 6.5 and got['z'] == 19.7 and got['y'] == 55.52 and got['map'] == 'Fake_Arena' and got['seq'] == 1 and
          abs(got['w'] - src.stat().st_mtime) < 1e-6 and not dest.with_suffix('.tmp').exists(),
          'x, y, z, map, w = when the journal was last written, written whole (no temporary file left)')
    with open(src, 'a') as fh:
        fh.write('{"t": 101.0, "pos": [1.0,')   # a line being written
    check(f.once() is True and json.loads(dest.read_text())['z'] == 19.7, 'a half-written last line is passed over')
    os.utime(src, (time.time() - 10, time.time() - 10))
    before = dest.read_text()
    check(f.once() is False and f.skipped['stale'] == 1 and dest.read_text() == before,
          'a journal older than 1.5 s is not copied again: the file ages instead of looking fresh')
    big = tmp / 'feed-big.jsonl'
    big.write_text(''.join(sample(i, z=100.0 + i) + '\n' for i in range(400)))   # over 8 KB: the tail read starts mid-line
    f2 = follow_feed.Feeder(big, tmp / 'feed-big.json')
    check(f2.once() is True and json.loads((tmp / 'feed-big.json').read_text())['z'] == 499.0, 'a long journal is read from its end')
    check(follow_feed.Feeder(tmp / 'nothing.jsonl', tmp / 'x.json').once() is False, 'no journal yet: nothing written')
    # what the pilot makes of the file
    target = pilot.Target('opponent', 0, 0, kind='duel', follow='opponent')
    placed = pilot.Pilot.read_follow(types.SimpleNamespace(follows={'opponent': str(dest)}), target)
    block = hsap.opponent_block([6.5, 55.52, 10.0], 0.0, placed, placed['w'] + 0.3, 'Fake_Arena')
    check(block['distance_m'] == 9.7 and block['where'] == 'ahead' and block['age_s'] == 0.3, f'the pilot and hsap read it as an opponent: {block}')
    # as a thread, following a journal that grows
    live = tmp / 'feed-live.jsonl'
    live.write_text(sample(0) + '\n')
    out = tmp / 'feed-live.json'
    th = follow_feed.Feeder(live, out, hz=50)
    th.start()
    seen = set()
    end = time.time() + 5
    while time.time() < end and len(seen) < 3:
        with open(live, 'a') as fh:
            fh.write(sample(len(seen) + 1, z=200.0 + len(seen)) + '\n')
        time.sleep(0.05)
        if out.exists():
            seen.add(json.loads(out.read_text())['z'])
    th.stop()
    th.join(2)
    check(len(seen) >= 3 and th.written >= 3 and not th.is_alive(), f'as a thread it follows the journal ({len(seen)} places seen, {th.written} writes)')


def duel_smoke_checks(tmp):
    """The solo smoke's segment (a prefix of steps, two follow files of which the second is the gate) behind a fake hsap whose game
    has no duel at all (co-op off): the prefix runs first, the pilot's first decision waits for the gate, the log tail stays quiet."""
    if not (HERE / 'segments' / 'duel-solo-smoke.toml').is_file() or not (HERE / 'segments' / 'duel-solo-smoke.txt').is_file():
        print('skip: the solo smoke segment is game data kept out of the published tree (pilot/segments/duel-solo-smoke.*)')
        return
    import argparse
    fake = tmp / 'fake_hsap_solo.py'
    fake.write_text(
        "import json, sys\nfrom pathlib import Path\n"
        f"sys.path.insert(0, {str(HERE)!r})\nimport test_pilot\n"
        "a = sys.argv[1:]\nlive = Path(a[a.index('--live') + 1])\nlive.mkdir(parents=True, exist_ok=True)\n"
        "test_pilot.FakeDuelGame(live, Path(a[a.index('--opponent') + 1]), no_duel=True).run()\n")
    opp, gate = tmp / 'smoke-opponent.json', tmp / 'smoke-gate.json'
    prefix = [ln for ln in (HERE / 'segments' / 'duel-solo-smoke.txt').read_text().splitlines() if ln.split('#', 1)[0].strip()]
    live = pilot.HERE / 'runs' / 'duel-smoke-run' / 'live' / 'out.jsonl'
    opened = []

    def open_gate():   # what duel_solo_smoke.py does: the gate opens when the last prefix step has ended
        end = time.time() + 60
        while time.time() < end:
            if live.exists() and any('"in": %d,' % len(prefix) in x and '"ev": "step"' in x for x in live.read_text().splitlines()):
                opened.append(len([x for x in live.read_text().splitlines() if '"ev": "step"' in x]))
                gate.write_text(json.dumps({'x': 0.0, 'z': 8.0, 'map': 'Fake_Arena', 'w': time.time()}))
                return
            time.sleep(0.02)
    threading.Thread(target=open_gate, daemon=True).start()
    saved = pilot.HSAP
    pilot.HSAP = fake
    try:
        args = argparse.Namespace(segment=str(HERE / 'segments' / 'duel-solo-smoke.toml'), decider='rules', replay=None, planner=False,
                                  copy=str(tmp / 'copy'), tag='duel-smoke-run', attach=None, save=None, wall=60, max_decisions=None,
                                  follow=[f'opponent={opp}', f'gate={gate}'], end_hold=0.0, shots=12, api_base=None,
                                  allowance_usd=None, allowance_since='2026-01-01')
        code = pilot.cmd_run(args)
    finally:
        pilot.HSAP = saved
    run_dir = pilot.HERE / 'runs' / 'duel-smoke-run'
    summary = json.loads((run_dir / 'summary.json').read_text())
    steps = [e for e in (json.loads(x) for x in (run_dir / 'out.jsonl').read_text().splitlines()) if e['ev'] == 'step']
    srcs = [e['src'] for e in steps if e['src'] != 'end']
    check(code == 1 and summary['outcome'] == 'budget: 8 decisions' and opened == [len(prefix)],
          f"the smoke segment ends on its eight decisions after the gate ({summary['outcome']}), the gate opened after {opened} steps")
    check(srcs[:len(prefix)] == [ln.split('#', 1)[0].strip() for ln in prefix] and srcs[len(prefix):len(prefix) + 2] == ['wait 0.2', 'swing'],
          f'the prefix runs first ({len(prefix)} steps), then the pilot\'s own: the fresh-state wait after the gate, the practice swing')
    check(summary['labels'] == {'practice-swing': 1, 'ready': 7} and summary['duel'] is None,
          f"with no duel line ever, the rules practise once and say Ready, and the duel block never appears ({summary['labels']})")
    check(summary['ledger'] == {}, 'no model request')


def duel_checks(tmp):
    duel_candidate_checks()
    duel_rules_checks()
    duel_segment_checks()
    duel_play_checks(tmp)
    duel_series_checks(tmp)
    duel_model_checks(tmp)
    duel_series_model_checks(tmp)
    duel_cost_checks(tmp)
    duel_cmd_run_checks(tmp)
    duel_smoke_checks(tmp)
    duel_feed_checks(tmp)


def fight_checks():
    """The fight target kind (PlayExplore17, 2026-11-15): hold a place and fight what comes. It has candidates made of hsap steps
    that exist, a time allowance for its `raw` step, and a `rules` policy (go there, strike and wait in turn, leave after 8 rounds)."""
    g = pilot.Goal('hold', pilot.Cond('Test.Step=Step01'), 'fight',
                   [pilot.Target('spot', 6.49, 15.69, y=55.5, kind='fight', radius=3.0)], what='fight what comes')
    st = {'pos': [0.0, 55.5, 10.0], 'facing': 0.0, 'event': 0}
    cands = pilot.make_candidates('Fake_Arena', g, g.targets[0], st, {}, None)
    names = [c.label for c in cands]
    check(names == ['strike', 'swing-x3', 'guard', 'wait-a-moment', 'go-near', 'back-off', 'side-left', 'side-right', 'next-target'],
          f'fight candidates: {names}')
    by = {c.label: c.lines for c in cands}
    check(by['strike'] == ['raw 0:ZL/1500,0.30:Y/100,0.75:Y/100,1.20:Y/100 1.8'], 'strike is one raw sequence: ZL held 1.5 s, three Y presses')
    check(by['swing-x3'] == ['swing', 'wait 0.4', 'swing', 'wait 0.4', 'swing', 'wait 0.5'], 'swing-x3 is three swings 0.4 s apart')
    check(by['guard'] == ['shield 900'] and by['wait-a-moment'] == ['wait 2.5'], 'guard and wait-a-moment')
    check(by['go-near'][-1].startswith('walk 6.49 15.69 radius 1.2'), f"go-near walks to the point: {by['go-near'][-1]}")
    check(all(ln.split()[0] in ('raw', 'swing', 'wait', 'shield', 'walk', 'run') for c in cands for ln in c.lines), 'every line is a hsap verb')
    check(abs(pilot.step_seconds(by['strike'][0]) - 3.8) < 1e-9, f"a raw step is allowed its wait plus 2 s: {pilot.step_seconds(by['strike'][0])}")
    check(pilot.step_seconds('raw 0:A/100 0.5') == 2.5 and pilot.step_seconds('swing') == 2 and pilot.step_seconds('wait 2.5') == 2.5,
          'raw takes its last word as the wait; swing and wait are unchanged')
    check(pilot.make_candidates('Fake_Arena', g, g.targets[0], dict(st, event=1), {}, None)[0].label == 'talk-through',
          'an event holding Link still offers talk-through first')
    rules = deciders.Rules()
    mem, seq = {}, []
    for _ in range(10):
        cands = pilot.make_candidates('Fake_Arena', g, g.targets[0], st, mem, None)
        label = rules.choose(deciders.Context(st, g, g.targets[0], cands, mem, [])).label
        assert label in [c.label for c in cands], (label, seq)
        seq.append(label)
        mem.setdefault('history', []).append((label, 'done', 0.0, None))
    check(seq == ['go-near'] + ['strike', 'wait-a-moment'] * 4 + ['next-target'],
          f'rules: go there, strike and wait in turn for eight rounds, then leave ({seq})')
    mem = {'history': [('go-near', 'stuck', 0.1, 4.0)]}
    cands = pilot.make_candidates('Fake_Arena', g, g.targets[0], st, mem, None)
    check(rules.choose(deciders.Context(st, g, g.targets[0], cands, mem, [])).label in ('back-off', 'side-left', 'side-right'),
          'rules: a go-near that ended stuck is answered by a step round, not by a label the kind lacks')
    mem['history'].append(('back-off', 'reached', 3.0, None))
    cands = pilot.make_candidates('Fake_Arena', g, g.targets[0], st, mem, None)
    check(rules.choose(deciders.Context(st, g, g.targets[0], cands, mem, [])).label == 'go-near',
          'rules: after the step round, go-near again')


def lessons_checks(tmp):
    """Lessons (lessons.py) in the goal-level planner, through the pilot's own planner call (maybe_plan) on the fake game: off, the planner's row in the transcript says lessons off and
    its request holds no `lessons` and the developer text it always had; on, the request holds the library's lesson for the door the pilot goes to, one more sentence, and the row says
    {on, n, tokens_est, ids}; on with nothing to say, the request is the one off sends."""
    book = tactics.Book(tmp / 'lessons-book')
    book.add_block(map='Fake_Area', at=[0.6, 0.0, 0.2], cause='door-side', tried=['sidestep', 'door-enter'], worked='door-enter', how='recovered', target='door', run='r1', source='live')

    def first_plan(less):
        planner = deciders.Planner(test_lessons.Stub(), 'gpt-6-astra')
        planner.lessons = less
        _, p, _, _, run_dir = play(deciders.Rules(), tmp, max_decisions=4, planner=planner)
        row = next(e for e in transcript(run_dir) if e['kind'] == 'planner')
        check('error' not in row and all(row[k] == p.plans[0][k] for k in ('n', 'why', 'lessons')), 'the planner row of the transcript is the pilot\'s own plan entry')
        return row, json.loads(row['request']['input'][1]['content'])

    off, off_data = first_plan(None)
    check(off['lessons'] == {'on': False, 'n': 0, 'tokens_est': 0, 'ids': []} and 'lessons' not in off_data and off['request']['input'][0]['content'] == deciders.PLANNER_DEVELOPER,
          f"lessons off: the planner's row says so and its request is the old one ({off['lessons']})")
    on, on_data = first_plan(lessons.Lessons(book))
    check(on['lessons']['on'] and on['lessons']['n'] == 1 and on['lessons']['tokens_est'] > 0 and len(on['lessons']['ids']) == 1, f"lessons on: the planner's row says {{on, n, tokens_est, ids}} ({on['lessons']})")
    check(len(on_data['lessons']) == 1 and on_data['lessons'][0].startswith('Fake_Area') and 'on the way to door' in on_data['lessons'][0] and 'door-enter worked' in on_data['lessons'][0],
          f"lessons on: the request has the lesson for the door ({on_data.get('lessons')})")
    check(on['request']['input'][0]['content'] == deciders.PLANNER_DEVELOPER + ' ' + lessons.NOTE and {k: v for k, v in on_data.items() if k != 'lessons'} == off_data,
          'lessons on: the same request, with the sentence and the key')
    cold, cold_data = first_plan(lessons.Lessons(tactics.Book(tmp / 'lessons-cold')))
    check(cold['request'] == off['request'] and cold['lessons'] == {'on': True, 'n': 0, 'tokens_est': 0, 'ids': []},
          'lessons on with a cold library: the request off sends, and the row says on with none')


# ---- the panel: what the pilot says on the game's own screen (hud_text.py; hsap.py sends <live>/hud.txt)

def hud_rows(text):
    return text.split('\n')


def hud_during(texts, n, total):
    """The texts written while decision n was the one on the panel."""
    return [t for t in texts if hud_rows(t)[1].startswith(f'decision {n}/{total}')]


def hud_checks(tmp):
    seg, p, outcome, ch, run_dir = play(deciders.Rules(), tmp, hud=True)
    texts, total = p.hud.texts, seg.max_decisions
    tr = transcript(run_dir)
    decs = [e for e in tr if e['kind'] == 'decision']
    results = {e['n']: e for e in tr if e['kind'] == 'result'}
    check(outcome == 'solved' and len(decs) == len(p.decisions) > 3, f'rules solve the made-up house with the panel on ({outcome}, {len(decs)} decisions)')
    check(texts and all(test_hud_text.valid(t) for t in texts), f'{len(texts)} panel texts, each within 14 lines of 56 ASCII characters')
    check(all(a != b for a, b in zip(texts, texts[1:])), 'a text is written only when it changed')
    rows = lambda n: [r for t in hud_during(texts, n, total) for r in hud_rows(t)]   # noqa: E731
    missing = [d['n'] for d in decs if 'STEP choosing the next step' not in rows(d['n'])]
    check(not missing, f'every decision shows its candidates before the decider answers ({missing})')
    missing = [d['n'] for d in decs if f"STEP {d['choice']} running" not in rows(d['n']) or f"> {d['choice']}" not in rows(d['n'])]
    check(not missing, f'and then the chosen candidate marked > and the step running ({missing})')
    missing = [d['n'] for d in decs if (f"STEP {d['choice']} -> {results[d['n']]['result']}" if d['n'] in results else None) not in rows(d['n'])
               and (d['n'] in results or not any(r.startswith(f"STEP {d['choice']} -> ") for r in rows(d['n'])))]
    check(not missing, f'and its result word when the step ended (a target left without a step: done or failed) ({missing})')
    missing = [d['n'] for d in decs[1:] if not any(r.startswith('LAST ') for r in rows(d['n']))]
    check(not missing, f'from the second decision on the step before is there as LAST ({missing})')
    last = hud_rows(texts[-1])
    check(last[0] == 'GOAL talk [met] FOR friend' and last[2] == 'RUN solved' and (ch.live / 'hud.txt').read_text().rstrip('\n') == texts[-1],
          f'at the end: the last goal met, RUN solved, and that text is what the file holds ({last[:3]})')
    check(any(r.startswith('MODEL rules, no model asked') for r in rows(1)) and 'COST none yet: no model call' in rows(1) and 'STATE moving freely' in rows(1),
          'rules: no model asked, no cost, moving freely')
    # the same run without a panel: every decision, every step line, the same
    _, p0, outcome0, ch0, run0 = play(deciders.Rules(), tmp)
    check(not (ch0.live / 'hud.txt').exists(), 'a pilot without a Hud writes no file')
    key = lambda tr_: [(e['n'], e['choice'], e['goal'], e['target']) for e in tr_ if e['kind'] == 'decision']   # noqa: E731
    check(outcome0 == outcome and p0.decisions == p.decisions and ch0.steps.read_text() == ch.steps.read_text() and key(transcript(run0)) == key(tr),
          'with the panel on or off the pilot decides and sends exactly the same: the same decisions, goals, targets and step lines')
    # a panel that cannot be written ends nothing: noted once in the transcript, the run is the same
    broken = FailingHud(tmp / 'never-written-hud.txt')
    _, pb, outcomeb, chb, runb = play(deciders.Rules(), tmp, hud=broken)
    notes = [e for e in transcript(runb) if e['kind'] == 'hud']
    check(outcomeb == 'solved' and pb.decisions == p.decisions and len(notes) == 1 and notes[0]['error'] == 'OSError: No space left on device',
          f'a Hud that cannot write: one `hud` row in the transcript ({notes}), the same decisions, still solved')


def hud_recover_checks(tmp):
    made = []

    def factory(live):
        made.append(RecordingHud(Path(live) / 'hud.txt'))
        return made[-1]
    posts = [test_recover.Post(0, 20)]
    p, outcome, world, rd = test_recover.play(tmp, [('t', 0, 40, 2.5)], posts, area='Fake_Post', hud=factory)
    texts = made[0].texts
    check(outcome == 'solved' and p.recover_summary()['blocks'] == 1, f'a post in the way: blocked once, solved ({outcome})')
    allrows = [r for t in texts for r in hud_rows(t)]
    check('RECOVERY rung sidestep' in allrows and 'MODEL recovery ladder' in allrows and any(r.startswith('> recover:sidestep') for r in allrows),
          'a recovery rung is a panel of its own: RECOVERY rung sidestep, MODEL recovery ladder, the rung as the chosen candidate')
    check(any(r.startswith('STUCK ') and ', rung ' in r for r in allrows), 'and the decision after the stuck move shows STUCK <s> s, rung <n>')
    check(all(test_hud_text.valid(t) for t in texts), 'every one within the limits')
    p0, outcome0, world0, rd0 = test_recover.play(tmp, [('t', 0, 40, 2.5)], posts, area='Fake_Post')
    check(outcome0 == outcome and p0.decisions == p.decisions and world0.log == world.log,
          'and the run is the same without the panel: the same decisions, the same lines sent to the game')


def hud_eyes_checks(tmp):
    import vision   # noqa: E402

    class EyesFirst:
        """The first decision looks: a fresh look with the row vision.py would have written."""
        def __init__(self):
            self.asked = 0

        def before_decision(self, st, goal=None, target=None, mem=None, tried=None, n=None):
            self.asked += 1
            if self.asked > 1:
                return None
            row = {'wall': time.time(), 'why': ['first'], 'cost_usd': 0.0004, 'oddities': [],
                   'answers': {'front': 'door', 'screen': 'play', 'p': {'text_box': 0.9, 'stuck': 0.1}, 'says': 'free text that stays off the panel'}}
            return vision.Look({'front': 'door', 'p': {}, 'age_s': 0.0}, [], True, row)
    made = []

    def factory(live):
        made.append(RecordingHud(Path(live) / 'hud.txt'))
        return made[-1]
    p, outcome, world, rd = test_recover.play(tmp, [('t', 0, 40, 2.5)], [], eyes=EyesFirst(), hud=factory)
    texts = made[0].texts
    first = hud_rows(texts[0])
    check(outcome == 'solved' and first[1].startswith('decision 1/') and any(r.startswith('VISION ') and r.endswith(' s ago: ahead door, text box 90%') for r in first) and
          'COST $0.0004 so far, 1 model call' in first, f'a look made before the first decision is on its panel: VISION, and its cost ({first[-3:]})')
    check(not any('free text' in t for t in texts), 'what the look said in words never goes on the panel')


def hud_model_checks(tmp, client_base):
    """The stand-in model decider and planner: what the panel says of the model, its percentages and its cost."""
    client = openai_api.Client('hud-run', 'fake-house', client_base)
    _, p4, outcome4, ch4, run4 = play(deciders.Decisions(client), tmp, max_decisions=6, planner=deciders.Planner(client), hud=True)
    texts = p4.hud.texts
    allrows = [r for t in texts for r in hud_rows(t)]
    import re as _re
    check(any(_re.fullmatch(r'MODEL gpt-6-luna \d+\.\d\d s sure 60%', r) for r in allrows) and 'MODEL gpt-6-luna (asking)' in allrows,
          'the model: asking while the request is out, then its name, latency and how sure it was')
    check(any(_re.fullmatch(r'> \S+  70%', r) for r in allrows) and any(_re.fullmatch(r'  \S+  \d+%', r) for r in allrows),
          'the candidates carry the model\'s percentages, the chosen one marked')
    led = openai_api.summary('hud-run', standin=True)
    calls, cost = sum(v['requests'] for v in led.values()), sum(v['cost_usd'] for v in led.values())
    m = _re.fullmatch(r'COST \$([0-9.]+) so far, (\d+) model calls', next(r for r in hud_rows(texts[-1]) if r.startswith('COST ')))
    check(m and int(m.group(2)) == calls and abs(float(m.group(1)) - cost) < 2e-4 and 'planner' in led,
          f'the cost row is the ledger\'s: decisions and the planner ({m and m.group(0)} against {calls} requests, ${cost:.6f})')
    check(not any(w in t for t in texts for w in ('sk-test', '/tmp', '127.0.0.1', 'input_json', '"pos"', 'request')),
          'no key, path, address, request body or position anywhere in the panel')
    check(all(test_hud_text.valid(t) for t in texts), 'every text within the limits')
    # a model that costs real money (the ledger priced from tokens): the panel's cost row is the ledger's, to the fourth decimal
    _, p5, outcome5, _, _ = play(deciders.Decisions(PricedClient('hud-cost')), tmp, max_decisions=6, hud=True)
    led = openai_api.summary('hud-cost')
    calls, cost = sum(v['requests'] for v in led.values()), sum(v['cost_usd'] for v in led.values())
    m = _re.fullmatch(r'COST \$([0-9.]+) so far, (\d+) model calls', next(r for r in hud_rows(p5.hud.texts[-1]) if r.startswith('COST ')))
    check(m and cost > 0.0002 and int(m.group(2)) == calls and abs(float(m.group(1)) - cost) <= 5.1e-5 and
          any('sure 70%' in r for t in p5.hud.texts for r in hud_rows(t)),
          f'the cost row is the ledger\'s to the fourth decimal ({m and m.group(0)} against {calls} requests, ${cost:.6f}), and how sure the model was')


def hud_wire_checks(tmp):
    """The two halves together: the pilot's Hud writing <live>/hud.txt, hsap's sender reading it and sending it to a fake game that
    enforces the game side's caps (test_hsap.FakeBridge): what the game shows is exactly what the Hud wrote."""
    import types
    import test_hsap
    with test_hsap.Simulation(boot_events=0) as sim:
        ex = sim.executor(hud=True)
        sim.exchange()
        hud = hud_text.Hud(sim.live / 'hud.txt', total=40, eyes=True)
        g, t = types.SimpleNamespace(name='door', status='open'), types.SimpleNamespace(name='porch')
        labels = ['go', 'wait', 'side-left', 'side-right', 'roll', 'hop', 'back-off']

        def settle():
            for _ in range(20):
                ex.tick(0.05)
        hud.deciding(1, g, t, 3.0, 'openai-decisions', labels, model='model-x')
        settle()
        check(sim.bridge.shown() == hud.text and hud.text.startswith('GOAL door [open] FOR porch\ndecision 1/40  t 3.0 s'),
              'the game shows the panel the Hud wrote (the candidates offered, before the decider answers)')
        hud.decided('go', 'openai-decisions', labels, {'request': {'model': 'model-x'}, 'latency_ms': 420.0, 'confidence': 0.82, 'cost_usd': 0.0002,
                                                       'answers': [{'name': 'next_step', 'probabilities': [{'value': 'go', 'probability': 0.82}, {'value': 'wait', 'probability': 0.09}]}]})
        settle()
        shown = sim.bridge.shown()
        check(shown == hud.text and '> go  82%' in shown.split('\n') and 'MODEL model-x 0.42 s sure 82%' in shown.split('\n'),
              'and the chosen one with the model\'s percentage, its latency and how sure it was')
        hud.result('reached', g, t=4.5)
        settle()
        check(sim.bridge.shown() == hud.text and 'STEP go -> reached' in sim.bridge.shown().split('\n'), 'and the step\'s result')
        hud.finish('solved')
        settle()
        check(sim.bridge.shown().split('\n')[2] == 'RUN solved', 'and the end of the run')
        hud.clear()
        settle()
        check(sim.bridge.shown() is None and [r['cmd'] for _, r in sim.bridge.overlay_log][-1] == 'overlay_clear',
              'and the pilot\'s clear takes it off the screen')
        check(all(r['cmd'] != 'overlay' or len(r['text'].split('\n')) <= 14 for _, r in sim.bridge.overlay_log) and
              len([1 for _, r in sim.bridge.overlay_log if r['cmd'] == 'overlay']) == 4, 'four texts sent for four panel changes, none refused')


def hud_cmd_checks(tmp):
    """`pilot.py run` hands the switch to hsap and writes <live>/hud.txt; a fake hsap process (the made-up house behind hsap's command line)."""
    import argparse
    import contextlib
    import io
    fake = tmp / 'fake_hsap_hud.py'
    fake.write_text(
        "import json, sys\nfrom pathlib import Path\n"
        f"sys.path.insert(0, {str(HERE)!r})\nimport test_pilot\n"
        "a = sys.argv[1:]\nlive = Path(a[a.index('--live') + 1])\nlive.mkdir(parents=True, exist_ok=True)\n"
        "(live / 'argv.json').write_text(json.dumps(a))\ntest_pilot.FakeGame(live).run()\n")
    seg_path = tmp / 'hud-cmd.toml'
    seg_path.write_text(SEGMENT)
    written = []
    real_write = hud_text.Hud.write

    def spy(self, text):
        written.append((str(self.path), text))
        real_write(self, text)

    def run(tag, env=None, attach=None, **extra):
        args = argparse.Namespace(segment=str(seg_path), decider='rules', replay=None, planner=False, copy=str(tmp / 'copy'), tag=tag,
                                  attach=attach, save=None, wall=60, max_decisions=None, follow=[], end_hold=0.0, shots=0, api_base=None,
                                  allowance_usd=None, allowance_since='2026-01-01', matches=None, humanize=0, no_bad_points=True, **extra)
        written.clear()
        saved = pilot.HSAP
        pilot.HSAP = fake
        try:
            with mock.patch.dict(os.environ, env or {}), mock.patch.object(hud_text.Hud, 'write', spy), \
                    contextlib.redirect_stdout(io.StringIO()):
                code = pilot.cmd_run(args)
        finally:
            pilot.HSAP = saved
        run_dir = pilot.HERE / 'runs' / tag
        return code, run_dir, json.loads((run_dir / 'live' / 'argv.json').read_text()) if (run_dir / 'live' / 'argv.json').exists() else None

    with mock.patch.dict(os.environ):
        os.environ.pop('HSAP_HUD', None)
        code, run_dir, argv = run('hud-run-default')
    texts = [t for _, t in written if t]
    check(argv[argv.index('--hud') + 1] == 'on' and (run_dir / 'live' / 'hud.txt').exists(),
          'by default hsap is started with --hud on and the pilot writes <live>/hud.txt')
    check(texts and all(test_hud_text.valid(t) for t in texts) and written[-1][1] == '' and (run_dir / 'live' / 'hud.txt').read_text() == '' and
          any(hud_rows(t)[2].startswith('RUN ') for t in texts),
          f'{len(texts)} texts, RUN <outcome> at the end, and the panel cleared (an empty file) before the end step ends the game side')
    check(all(path == str(run_dir / 'live' / 'hud.txt') for path, _ in written), 'only ever that one file')
    code, run_dir, argv = run('hud-run-off', hud='off')
    check(argv[argv.index('--hud') + 1] == 'off' and not written and not (run_dir / 'live' / 'hud.txt').exists(),
          '--hud off: hsap is told off, and nothing is written, not even an empty file')
    code, run_dir, argv = run('hud-run-env', env={'HSAP_HUD': '0'})
    check(argv[argv.index('--hud') + 1] == 'off' and not written and not (run_dir / 'live' / 'hud.txt').exists(), 'HSAP_HUD=0: the same')
    code, run_dir, argv = run('hud-run-env-on', env={'HSAP_HUD': '0'}, hud='on')
    check(argv[argv.index('--hud') + 1] == 'off' and not written, 'HSAP_HUD=0 wins over --hud on')
    # attached to a game side somebody else started: the panel goes into that live folder, no hsap is started
    live = tmp / 'hud-attach-live'
    pilot.Channel(live)
    attached = FakeGame(live)
    attached.start()
    with mock.patch.dict(os.environ):
        os.environ.pop('HSAP_HUD', None)
        code, run_dir, argv = run('hud-run-attach', attach=str(live))
    summary = json.loads((run_dir / 'summary.json').read_text())
    check(argv is None and 'runner' not in summary and (live / 'hud.txt').exists() and any(t for _, t in written) and
          all(path == str(live / 'hud.txt') for path, _ in written), '--attach: the panel text goes into the attached live folder')
    # check-route (no decisions: nothing to show) tells hsap --hud off
    fake2 = tmp / 'fake_hsap_check.py'
    fake2.write_text("import json, sys\nfrom pathlib import Path\na = sys.argv[1:]\nlive = Path(a[a.index('--live') + 1])\n"
                     "(live / 'argv.json').write_text(json.dumps(a))\n")
    route = tmp / 'hud-route.txt'
    route.write_text('wait 1\n')
    saved = pilot.HSAP
    pilot.HSAP = fake2
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            pilot.cmd_check_route(argparse.Namespace(route=str(route), segment=str(seg_path), runs=1, copy=str(tmp / 'copy'), tag='hud-check', wall=10))
    finally:
        pilot.HSAP = saved
    argv = json.loads((pilot.HERE / 'runs' / 'checks' / 'hud-check-1' / 'argv.json').read_text())
    check(argv[argv.index('--hud') + 1] == 'off', 'check-route: hsap is started with --hud off (a route has no decisions to show)')


def main():
    with tempfile.TemporaryDirectory(prefix='pilot-test-') as t:
        tmp = Path(t)
        openai_api.LEDGER = tmp / 'ledger.jsonl'
        openai_api.LEDGER_STANDIN = tmp / 'ledger-standin.jsonl'
        openai_api.CAPS = tmp / 'caps.json'
        openai_api.CAPS.write_text(json.dumps({'per_run_usd': 2, 'per_night_usd': 50, 'total_usd': 400,
                                               'planner_share_of_night': 0.4, 'model': None}))
        pilot.FRAGMENTS = tmp / 'fragments.jsonl'
        pilot.HERE = tmp   # exported routes into the temporary folder
        os.environ['PILOT_TACTICS_DIR'] = str(tmp / 'tactics')   # (a run's tactics library: never the real one)
        pilot.world_plan = lambda: None   # straight lines in the made-up area

        # `pilot.py story` needs story.py and the private world model, which a published tree does not have: it says so and returns 2
        import contextlib
        import io
        import types
        saved_story = sys.modules.get('story')
        sys.modules['story'] = None   # (an import that fails, whether or not the module is on disk)
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                code = pilot.cmd_story(types.SimpleNamespace(quest='q', after='a', area='x', save='s', name='n', out=None))
        finally:
            if saved_story is None:
                sys.modules.pop('story', None)
            else:
                sys.modules['story'] = saved_story
        check(code == 2 and 'story.py' in buf.getvalue() and 'private' in buf.getvalue(), f'`story` without its private module says so and returns 2 ({code}: {buf.getvalue().strip()[:80]})')

        # a tree with no caps file (a fresh clone: caps.json is private): the model deciders say so and the run plays on the rules
        import types as _types
        real_caps = openai_api.CAPS
        openai_api.CAPS = tmp / 'no-such-caps.json'
        try:
            try:
                openai_api.caps()
                got = None
            except openai_api.CapReached as e:
                got = str(e)
            check(got is not None and 'caps' in got, f'no caps file: caps() says so as a cap, not a crash ({got})')
            a = _types.SimpleNamespace(decider='openai-decisions', replay=None, api_base='http://127.0.0.1:9/v1')
            d, note = pilot.make_decider(a, openai_api.Client('nocaps', 'seg', 'http://127.0.0.1:9/v1'))
            check(d.name == 'rules' and note == 'no caps', f'no caps file: the run uses the rules ({d.name}, {note})')
            check(pilot.make_planner(openai_api.Client('nocaps', 'seg', 'http://127.0.0.1:9/v1'), _types.SimpleNamespace(planner=True, api_base='http://127.0.0.1:9/v1')) is None,
                  'no caps file: no planner')
        finally:
            openai_api.CAPS = real_caps

        c = pilot.Cond('Test.Step=Step01')
        check(c.met({'Test.Step': f"#{pilot.murmur('Step01'):08x}"}) and not c.met({'Test.Step': None}),
              'an Enum condition by the hash of its value name')
        check(pilot.murmur('') == 0 and pilot.murmur('test') == 0xba6bd213 and pilot.murmur('The quick brown fox jumps over the lazy dog') == 0x2e4ff723,
              'murmur is MurmurHash3 (x86, 32 bit, seed 0: the published test vectors), as the game hashes its flag names')
        check(pilot.Cond('Test.Life>=8').met({'Test.Life': 12}) and
              pilot.Cond('0x9824206c=Open').met({'0x9824206c': 'Open'}), 'number and text conditions')

        st = {'pos': [0, 0, 0], 'facing': 0}
        for kind in ('reach', 'item', 'wait', 'door', 'talk', 'chest', 'crawl', 'climb', 'fight'):
            g = pilot.Goal('g', pilot.Cond('X=1'), kind, [pilot.Target('t', 5, 5, kind=kind)])
            cands = pilot.make_candidates('A', g, g.targets[0], st, {})
            check(2 <= len(cands) <= 12 and len({x.label for x in cands}) == len(cands), f'{len(cands)} candidates for {kind}')
        fight_checks()

        seg, p, outcome, ch, run_dir = play(deciders.Rules(), tmp)
        check(outcome == 'solved', f'rules solve the made-up segment ({outcome}, {len(p.decisions)} decisions)')
        check('back-off' in p.decisions or 'side-left' in p.decisions, 'rules went round the box after a stuck move')
        route, kept = pilot.export_route(seg, run_dir, run_dir.name, 'rules', ch.events)
        text = route.read_text()
        check(all(f'expect flag {g.cond.text}' in text for g in seg.goals) and 'until flag Talked=1' in text and
              '# left out:' not in text.split('expect area')[0], f'exported route with {kept} steps and an expect per goal')
        tr = [json.loads(x) for x in (run_dir / 'transcript.jsonl').read_text().splitlines()]
        check(sum(e['kind'] == 'decision' for e in tr) == len(p.decisions), 'every decision in the transcript')

        _, p2, outcome2, _, _ = play(deciders.Replay(run_dir / 'transcript.jsonl'), tmp)
        check(outcome2 == 'solved' and p2.decisions == p.decisions, 'the replay decider repeats the recorded choices')

        srv = standin.serve(0)
        base = f'http://127.0.0.1:{srv.server_address[1]}/v1'
        os.environ['OPENAI_API_KEY'] = 'sk-test-must-never-be-sent'
        client = openai_api.Client('test-run', 'fake-house', base)
        _, p3, outcome3, _, run3 = play(deciders.Decisions(client), tmp, max_decisions=6,
                                        planner=deciders.Planner(client))
        tr3 = [json.loads(x) for x in (run3 / 'transcript.jsonl').read_text().splitlines()]
        dec = [e for e in tr3 if e['kind'] == 'decision']
        body = dec[0]['request']
        check(body['model'] == 'gpt-6-luna' and body['input'][1]['content'][1]['type'] == 'input_json' and
              [q['type'] for q in body['questions']] == ['choice', 'predicate', 'predicate', 'predicate', 'predicate'] and
              [x['value'] for x in body['questions'][0]['choices']] == [x['label'] for x in dec[0]['candidates']],
              'the Decisions request: model, JSON input, one choice over the candidates and four predicates')
        check(all('fallback' not in e for e in dec) and all(e.get('latency_ms') is not None for e in dec),
              f'{len(dec)} decisions answered by the stand-in, none fell back to rules')
        seen = standin.SEEN
        check(seen and all(s['headers'].get('Authorization') == 'Bearer standin' for s in seen) and
              not any('sk-test' in json.dumps(s) for s in seen), 'the real key never reached the stand-in')
        check('sk-test' not in (run3 / 'transcript.jsonl').read_text(), 'the key is not in the transcript')
        plans = [e for e in tr3 if e['kind'] == 'planner']
        check(plans and plans[0]['answer']['order'] and 'reason' in plans[0]['answer'], 'the planner answered and was applied')
        led = openai_api.summary('test-run', standin=True)
        check(led['decision']['requests'] == len(dec) and led['planner']['requests'] == len(plans) and
              not openai_api.LEDGER.exists(), 'stand-in requests in the stand-in ledger only')
        hud_model_checks(tmp, base)
        del os.environ['OPENAI_API_KEY']

        openai_api.CAPS.write_text(json.dumps({'per_run_usd': 0.001, 'per_night_usd': 50, 'total_usd': 400,
                                               'planner_share_of_night': 0.4, 'model': None}))
        openai_api._append({'ts': time.time(), 'run': 'r1', 'kind': 'decision', 'cost_usd': 0.0009, 'status': 200,
                            'latency_ms': 200, 'usage': {'input_tokens': 9000}}, openai_api.LEDGER)
        try:
            openai_api.Client('r1', 's').check_caps('decision', 0.0002)
            check(False, 'the run cap stops a request')
        except openai_api.CapReached as e:
            check('run cap' in str(e), f'the run cap stops a request ({e})')
        # the shipped limits (the user's decision of 2026-11-16: 3 USD a run, 50 USD a night, 4,000 USD in all): a run stops at its cap, a night at its own
        real = HERE / 'caps.json'
        if real.is_file():   # (the caps file is private: a published tree has none and its model deciders play on the rules)
            shipped = json.loads(real.read_text())
            check((shipped['per_run_usd'], shipped['per_night_usd'], shipped['total_usd']) == (3.0, 50.0, 4000.0),
                  f'pilot/caps.json holds 3 USD a run, 50 a night, 4000 in all ({shipped})')
        keep_ledger = openai_api.LEDGER
        openai_api.LEDGER = tmp / 'cap-ledger.jsonl'   # (its own ledger: the checks after this block count their own rows)
        openai_api.CAPS.write_text(json.dumps({'per_run_usd': 3.0, 'per_night_usd': 50.0, 'total_usd': 4000.0,
                                               'planner_share_of_night': 0.4, 'model': None}))

        def spend(run, usd):
            openai_api._append({'ts': time.time(), 'run': run, 'kind': 'decision', 'cost_usd': usd, 'status': 200,
                                'latency_ms': 200, 'usage': {'input_tokens': 9000}}, openai_api.LEDGER)

        spend('cap-run', 2.99)
        try:
            openai_api.Client('cap-run', 's').check_caps('decision', 0.005)
            check(True, '2.995 USD of 3.00 in a run still passes')
        except openai_api.CapReached as e:
            check(False, f'2.995 USD of 3.00 in a run still passes ({e})')
        try:
            openai_api.Client('cap-run', 's').check_caps('decision', 0.02)
            check(False, 'a run stops at 3.00 USD')
        except openai_api.CapReached as e:
            check('run cap 3.00' in str(e), f'a run stops at its 3.00 USD cap ({e})')
        for i in range(17):   # (other runs, each under its own cap, fill the night to 49.99 USD)
            spend(f'cap-night-{i}', 2.9)
        spend('cap-night-last', 0.69)
        night = openai_api.spent('cap-night-new')['night']
        check(abs(night - 49.99 - 2.99) < 1e-6, f'the night holds 52.98 USD with the first run ({night:.3f})')
        try:
            openai_api.Client('cap-night-new', 's').check_caps('decision', 0.02)
            check(False, 'a night stops at 50 USD')
        except openai_api.CapReached as e:
            check('night cap 50.00' in str(e), f'a new run (0 USD of its own 3.00) stops at the night\'s 50.00 USD cap ({e})')
        openai_api.LEDGER = tmp / 'cap-ledger-2.jsonl'
        for i in range(17):
            spend(f'cap-night-{i}', 2.9)
        spend('cap-night-last', 0.69)
        try:
            openai_api.Client('cap-night-new', 's').check_caps('decision', 0.005)
            check(True, '49.995 USD of 50.00 in a night still passes')
        except openai_api.CapReached as e:
            check(False, f'49.995 USD of 50.00 in a night still passes ({e})')
        openai_api.LEDGER = keep_ledger
        openai_api.CAPS.write_text(json.dumps({'per_run_usd': 2, 'per_night_usd': 50, 'total_usd': 400,
                                               'planner_share_of_night': 0.00001, 'model': None}))
        try:
            openai_api.Client('r2', 's').check_caps('planner', 0.01)
            check(False, 'the planner share stops a planner request')
        except openai_api.CapReached as e:
            check('planner share' in str(e), 'the planner share stops a planner request')
        u = {'input_tokens': 1000, 'input_tokens_details': {'cached_tokens': 200, 'cache_write_tokens': 100},
             'output_tokens': 50}
        check(abs(openai_api.cost('decisions', 'gpt-6-luna', u) - (700 * 0.10 + 200 * 0.01 + 100 * 0.125) / 1e6) < 1e-12,
              'cost from usage: cached and written tokens priced apart, output free on Decisions')
        check(openai_api.percentile([100, 200, 300, 400], 50) == 250 and openai_api.percentile([5], 95) == 5,
              'median and 95th percentile')
        names = [f'Some.Flag_Name_{i:03d}_LongEnoughToMatter' for i in range(20)]
        wl = pilot.watch_lines(names)
        check(len(wl) > 1 and all(len(x) <= 255 for x in wl) and
              [n for x in wl for n in x.split()[1:]] == names, f'{len(names)} flags in {len(wl)} watch lines under 255')
        openai_api.CAPS.write_text(json.dumps({'per_run_usd': 2, 'per_night_usd': 50, 'total_usd': 400,
                                               'planner_share_of_night': 0.4, 'model': None}))
        try:
            openai_api.Client('r3', 's', allowance=(time.time() - 60, 0.0005)).check_caps('decision', 0.0002)
            check(False, 'the allowance stops a request')
        except openai_api.CapReached as e:
            check('allowance' in str(e), f'the allowance stops a request ({e})')

        class Dear:   # a client whose answer costs more than a decision may
            def post(self, *a, **k):
                return ({'answers': [{'name': 'next_step', 'type': 'choice', 'choice': 'go'}]}, 100.0,
                        {'usage': {'input_tokens': 30000}, 'cost_usd': 0.003})
        d = deciders.Decisions(Dear(), model='gpt-6-luna')
        g = pilot.Goal('g', pilot.Cond('X=1'), 'reach', [pilot.Target('t', 5, 5)])
        ctx = deciders.Context({'pos': [0, 0, 0]}, g, g.targets[0], pilot.make_candidates('A', g, g.targets[0],
                                                                                         {'pos': [0, 0, 0]}, {}), {}, [])
        d.choose(ctx)
        check(d.stop_reason and '0.003' in d.stop_reason, 'a decision dearer than 0.002 USD stops the model')
        again = d.choose(ctx)
        check(again.info.get('fallback', '').startswith('stopped'), 'no request after the stop')
        follow_checks(tmp)
        duel_checks(tmp)
        hud_checks(tmp)
        hud_recover_checks(tmp)
        hud_eyes_checks(tmp)
        hud_cmd_checks(tmp)
        hud_wire_checks(tmp)
        lessons_checks(tmp)
        os.environ.pop('PILOT_TACTICS_DIR', None)
    test_recover.run()
    test_hud_text.run()
    test_interact.run()
    if test_interact.FAILS:
        raise SystemExit(f'FAILED: test_interact: {len(test_interact.FAILS)} checks failed')
    test_eyes.run()
    if not test_actions.run():
        raise SystemExit('FAILED: test_actions')
    if not test_sections.run():
        raise SystemExit('FAILED: test_sections')
    if not test_lessons.run():
        raise SystemExit('FAILED: test_lessons')
    print('test_pilot: all passed')


if __name__ == '__main__':
    main()
