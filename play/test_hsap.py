#!/usr/bin/env python3
"""Game-free checks of hsap.py against a simulated protocol-1 bridge over a real Unix socket.
The production Game client and Executor run unchanged; only hs-run.sh is replaced. A deterministic clock advances
presents, timed inputs and Link updates, so no GPU, game files, background thread or wall-clock sleeps are needed.

    python3 -I -B test_hsap.py
    HSAP_TEST_MODULE=/path/to/hsap.py python3 -I -B test_hsap.py
"""
import contextlib
import importlib.util
import io
import json
import math
import os
import re
import signal
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hsap  # noqa: E402
if os.environ.get('HSAP_TEST_MODULE'):
    _spec = importlib.util.spec_from_file_location('hsap', os.environ['HSAP_TEST_MODULE'])
    hsap = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(hsap)

AXES = {'LUP': ('ly', 1), 'LDOWN': ('ly', -1), 'LLEFT': ('lx', -1), 'LRIGHT': ('lx', 1),
        'RUP': ('ry', 1), 'RDOWN': ('ry', -1), 'RLEFT': ('rx', -1), 'RRIGHT': ('rx', 1)}
BUTTONS = set('A B X Y L R ZL ZR PLUS MINUS LS RS LEFT UP RIGHT DOWN'.split())


class FakeRunner:
    def __init__(self):
        self.running = True

    def poll(self):
        return None if self.running else 0

    def wait(self, timeout=None):
        self.running = False
        return 0


class FakeBridge:
    """A world with y up and a following camera. All names and geometry here are invented fixtures."""
    def __init__(self, path, live, run, clock, start=(0.0, 0.0, 0.0), camera=0.0, handed=1, follow=True,
                 walls=(), boot_events=5, flags=None, prompt_at=None, ack_delay=0, listening=True, subscribe_error=None,
                 overlay='ok'):
        self.path, self.run, self.clock = path, run, clock
        self.pos, self.cam, self.handed, self.follow = list(start), camera, handed, follow
        self.walls, self.boot_events = list(walls), boot_events
        self.flags, self.prompt_at = dict(flags or {}), prompt_at
        self.ack_delay = ack_delay
        self.subscribe_error = subscribe_error
        self.overlay_mode, self.overlay_log = overlay, []   # 'ok', or the error code every overlay request is answered with
        self.panel, self.panel_until = None, None            # the text on the game's screen and when the game drops it by itself
        self.listener, self.conn = None, None
        self.rx, self.tx = bytearray(), bytearray()
        self.write_limit = None
        self.requests, self.inputs, self.waiting = [], [], []
        self.sub, self.last_sample, self.baseline = None, 0, None
        self.frame, self.latest, self.updates = 0, None, True
        self.event_override = None
        self.a_presses, self.max_waiting = 0, 0
        self.debug = hsap.Tail(live)
        self.debug_lines = []
        self.run.mkdir(parents=True)
        (self.run / 'hookshot_log.txt').write_text('vk: 0 presents, 60 fps; a frame: 15 draws\n')
        if listening:
            self.listen()

    def listen(self):
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.bind(str(self.path))
        self.listener.listen(1)
        self.listener.setblocking(False)

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
        if self.listener:
            self.listener.close()
            self.listener = None

    def queue(self, message):
        self.tx.extend((json.dumps(message, separators=(',', ':')) + '\n').encode())

    def reply(self, request, **fields):
        self.queue({'id': request['id'], 'ok': True, 'frame': self.frame, **fields})

    def fail(self, request, error, message):
        self.queue({'id': request['id'], 'ok': False, 'frame': self.frame, 'error': error, 'message': message})

    def pump(self):
        for line in self.debug.lines():
            self.debug_lines.append(line)
            if line == '!cheat 996':
                save = self.run / 'user/save/test-user/slot_00/progress.sav'
                save.parent.mkdir(parents=True, exist_ok=True)
                save.write_bytes(b'simulated save')
                os.utime(save, (self.clock.now, self.clock.now))
                with open(self.run / 'hookshot_log.txt', 'a') as out:
                    out.write('cheats: save: manager 0x1, check 1, request taken (cooldown 0)\n')
            elif line.startswith('!cheat '):
                with open(self.run / 'hookshot_log.txt', 'a') as out:
                    out.write('cheats: simulated debug action\n')
        if self.listener is not None and self.conn is None:
            try:
                self.conn, _ = self.listener.accept()
                self.conn.setblocking(False)
            except BlockingIOError:
                pass
        if self.conn is None:
            return
        while True:
            try:
                data = self.conn.recv(65536)
            except BlockingIOError:
                break
            except ConnectionResetError:
                data = b''
            if not data:
                self.conn.close()
                self.conn = None
                self.inputs.clear()   # waited inputs belong to the connection
                self.waiting.clear()
                self.sub = None
                self.panel = None   # the game clears the panel when the connection that set it closes
                return
            self.rx.extend(data)
        while b'\n' in self.rx:
            line, _, self.rx = self.rx.partition(b'\n')
            request = json.loads(line)
            assert all(r['id'] != request['id'] for r in self.requests), 'request ids must be unique'
            self.requests.append(request)
            self.dispatch(request)
        if self.tx:
            try:
                n = self.conn.send(self.tx if self.write_limit is None else self.tx[:self.write_limit])
                del self.tx[:n]
            except BlockingIOError:
                pass

    def dispatch(self, request):
        cmd = request['cmd']
        if cmd == 'subscribe':
            if self.subscribe_error:
                self.fail(request, *self.subscribe_error)
                return
            assert request['events'] == ['oot']
            assert 1 <= request['every'] <= 216000
            assert type(request['changes']) is bool
            assert len(request['flags']) <= 64 and all(hsap.valid_flag(f) for f in request['flags'])
            self.sub, self.last_sample, self.baseline = request, self.frame, None
            self.reply(request)
        elif cmd == 'status':
            self.reply(request, protocol=1, map='Last_Known_Map', game=self.latest)
        elif cmd in ('press', 'stick', 'sequence'):
            try:
                steps = self.input_steps(request)
            except ValueError as e:
                self.fail(request, 'bad_request', str(e))
                return
            assert request['exclusive'] is True and request['wait'] is True
            start = min(s['start'] for s in steps)
            end = max(s['end'] for s in steps)
            self.inputs.extend(steps)
            self.waiting.append((end + self.ack_delay, request, start, end))
            self.max_waiting = max(self.max_waiting, len(self.waiting))
        elif cmd in ('overlay', 'overlay_clear'):
            self.overlay_request(request)
        else:
            self.fail(request, 'unknown_cmd', 'no such command')

    def overlay_request(self, request):
        """The game side's contract: `overlay` text (at most 2048 bytes of valid UTF-8 once controls, DEL and C1 are dropped, at most
        16 lines, trailing blank lines ignored) and `seconds` (a number in (0, 3600], omitted: no expiry), `overlay_clear`; the panel is
        dropped by the game when `seconds` pass without a new overlay. A game that cannot says unavailable, an older one unknown_cmd."""
        self.overlay_log.append((self.clock.now, request))
        if self.overlay_mode != 'ok':
            self.fail(request, self.overlay_mode, f'overlay: {self.overlay_mode}')
            return
        if request['cmd'] == 'overlay_clear':
            self.panel = None
            self.reply(request, lines=0, bytes=0)
            return
        text, seconds = request.get('text'), request.get('seconds')
        if not isinstance(text, str):
            self.fail(request, 'bad_request', 'text must be a string')
            return
        kept = ''.join(c for c in text if c == '\n' or not (ord(c) < 0x20 or ord(c) == 0x7f or 0x80 <= ord(c) < 0xa0))
        lines = kept.split('\n')
        while lines and not lines[-1].strip():
            lines.pop()
        if len('\n'.join(lines).encode()) > 2048 or len(lines) > 16:
            self.fail(request, 'bad_request', 'text: more than 2048 bytes or 16 lines')
            return
        if seconds is not None and not (isinstance(seconds, (int, float)) and not isinstance(seconds, bool) and 0 < seconds <= 3600):
            self.fail(request, 'bad_request', 'seconds must be in (0, 3600]')
            return
        self.panel = '\n'.join(lines) or None
        self.panel_until = None if seconds is None else self.clock.now + seconds
        self.reply(request, lines=len(lines), bytes=len('\n'.join(lines).encode()))

    def shown(self):
        """What the game's screen says now: the panel unless its seconds ran out."""
        if self.panel is not None and self.panel_until is not None and self.clock.now >= self.panel_until:
            self.panel = None
        return self.panel

    def names(self, names):
        axes, buttons = {}, []
        for name in names.split('+'):
            if name in BUTTONS:
                buttons.append(name)
            elif name in AXES:
                axis, value = AXES[name]
                axes[axis] = value
            elif re.fullmatch(r'[LR][XY]=-?\d+', name):
                axes[name[:2].lower()] = max(-1.0, min(1.0, int(name[3:]) / 32767))
            else:
                raise ValueError('not a button: ' + name)
        return axes, buttons

    def input_steps(self, request):
        if request['cmd'] == 'sequence':
            assert request['units'] == 'hos'
            specs = []
            for text in request['script'].split(','):
                match = re.fullmatch(r'([\d.]+):([^/]+)(?:/([\d.]+))?', text)
                if not match:
                    raise ValueError('bad script')
                at, names, ms = match.groups()
                specs.append((math.floor(float(at) * 60 + 0.5), max(1, math.floor(float(ms or 200) * .06 + .5)), names, {}))
        else:
            axes = {}
            if request['cmd'] == 'stick':
                assert request['stick'] == 'L'
                axes = {'lx': request['x'], 'ly': request['y']}
                assert all(-1 <= value <= 1 for value in axes.values())
            specs = [(request.get('at', 0), request['frames'], request.get('buttons', ''), axes)]
        steps = []
        for at, frames, names, axes in specs:
            buttons = []
            if names:
                named_axes, buttons = self.names(names)
                axes = {**named_axes, **axes}
            assert 1 <= frames <= 216000
            self.a_presses += 'A' in buttons
            start = self.frame + 1 + at
            steps.append({'start': start, 'end': start + frames, 'axes': axes, 'buttons': buttons})
        return steps

    def game_state(self, frame=None):
        frame = self.frame if frame is None else frame
        prompt = 'Empty'
        if self.prompt_at and math.hypot(self.pos[0] - self.prompt_at[0], self.pos[2] - self.prompt_at[1]) < 1.0:
            prompt = 'Crawl'
        event = frame < self.boot_events * 6 if self.event_override is None else self.event_override
        return {'t': frame / 60, 'frame': frame, 'map': 'Test_Map', 'pos': [round(v, 2) for v in self.pos],
                'facing': 0.0, 'camera': round(self.cam, 1), 'event': event, 'loading': False, 'age': 'child',
                'life': 12, 'max_life': 12, 'rupees': 0, 'prompt': prompt, 'music': 'BGM_Test'}

    def extra_values(self):
        """More values for the change scan (a subclass's): {hash text: value}."""
        return {}

    def tick(self):
        self.frame += 1
        axes = {}
        for step in self.inputs:
            if step['start'] <= self.frame < step['end']:
                axes.update(step['axes'])
        sx, sy = axes.get('lx', 0), axes.get('ly', 0)
        if self.updates and (sx or sy) and not self.game_state()['event']:
            angle = math.degrees(math.atan2(sx, sy))
            world = math.radians(self.cam - self.handed * angle)
            speed = 4 / 60 * min(1, math.hypot(sx, sy))
            nx, nz = self.pos[0] + speed * math.sin(world), self.pos[2] + speed * math.cos(world)
            if not any(x0 <= nx <= x1 and z0 <= nz <= z1 for x0, z0, x1, z1 in self.walls):
                if self.follow:
                    self.cam += hsap.wrap(math.degrees(world) - self.cam) / 60
                self.pos[0], self.pos[2] = nx, nz
        self.inputs = [s for s in self.inputs if s['end'] > self.frame]
        if self.updates:
            self.latest = self.game_state()
            if self.sub and self.frame - self.last_sample >= self.sub['every']:
                self.last_sample = self.frame
                game = dict(self.latest)
                if self.sub['flags']:
                    game['flags'] = {name: self.flags.get(name) for name in self.sub['flags']}
                if self.sub['changes']:
                    values = {'0x00000001': self.flags.get('Test.Flag'), **self.extra_values()}
                    game['changed'] = {} if self.baseline is None else {
                        name: value for name, value in values.items() if self.baseline.get(name) != value}
                    self.baseline = values
                self.queue({'event': 'oot', 'sub': self.sub['id'], 'frame': self.frame, 'game': game})
        # Deliberately deliver completed shorter inputs before earlier, still-outstanding long inputs.
        for due, request, start, end in list(self.waiting):
            if self.frame >= due:
                self.reply(request, start=start, end=end)
                self.waiting.remove((due, request, start, end))


class Clock:
    def __init__(self):
        self.now, self.next_frame = 1000.0, 1000.0 + 1 / 60
        self.bridge = None
        self.due = []   # [(time, function)]: things the test does while simulated time passes (the pilot writing its panel file)

    def at(self, when, function):
        self.due.append((when, function))

    def run_due(self):
        for item in sorted((d for d in self.due if d[0] <= self.now + 1e-9), key=lambda d: d[0]):
            self.due.remove(item)
            item[1]()

    def time(self):
        return self.now

    def sleep(self, seconds):
        end = self.now + seconds
        while self.next_frame <= end + 1e-9:
            self.now = self.next_frame
            self.next_frame += 1 / 60
            self.run_due()
            self.bridge.pump()
            self.bridge.tick()
            self.bridge.pump()
        self.now = end
        self.bridge.pump()


class Simulation:
    def __init__(self, watch=None, hud_game=False, **options):
        self.options = options
        self.watch = list(options.get('flags', {})) if watch is None else watch
        self.executors, self.input_samples = [], []
        self.hud_game = hud_game   # hsap.Game(hud=...): the game is started with the panel's picture switch

    def __enter__(self):
        self.stack = contextlib.ExitStack()
        root = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix='hsap-test-')))
        self.live, self.copy = root / 'live', root / 'copy'
        self.clock = Clock()
        for name, value in [('time', self.clock.time), ('monotonic', self.clock.time), ('sleep', self.clock.sleep)]:
            self.stack.enter_context(mock.patch.object(hsap.time, name, value))
        self.stack.enter_context(mock.patch.object(hsap.subprocess, 'Popen', self.launch))
        self.game = hsap.Game(self.copy, 'test', 60, self.live, watch=self.watch, **({'hud': True} if self.hud_game else {}))
        self.stack.enter_context(mock.patch.object(self.game, 'game_pids', return_value=[]))
        request = self.game.request

        def tracked(cmd, **args):
            if cmd in ('press', 'stick', 'sequence'):
                self.input_samples.append((cmd, (self.game.st or {}).get('frame')))
            return request(cmd, **args)

        self.game.request = tracked
        return self

    def launch(self, cmd, **kwargs):
        self.launched, self.launch_env = list(cmd), kwargs.get('env')
        assert cmd[0] == hsap.HS_RUN and kwargs['start_new_session'] is True
        args = dict(arg.split('=', 1) for arg in cmd[4:] if '=' in arg)
        assert 'HOS_CONTROL' in args and 'HOS_INPUT_LIVE' in args
        assert not any(key.startswith('HOS_OOT_STATE_') for key in args)
        assert 'HOS_INPUT_FRAME_CLOCK' not in args and 'HOS_INPUT_EXCLUSIVE' not in args
        self.bridge = FakeBridge(Path(args['HOS_CONTROL']), Path(args['HOS_INPUT_LIVE']), self.copy / 'runs/test',
                                 self.clock, **self.options)
        self.clock.bridge = self.bridge
        return FakeRunner()

    def exchange(self):
        states = self.game.poll()
        self.bridge.pump()
        states += self.game.poll()
        return states

    def executor(self, steps=(), boot='none', hud=False):
        (self.live / 'steps.txt').write_text(''.join(s + '\n' for s in steps))
        ex = hsap.Executor(self.game, self.live, boot, **({'hud': True} if hud else {}))
        ex.analog = False   # independent of the caller's HSAP_ANALOG environment
        self.executors.append(ex)
        return ex

    def events(self):
        return [json.loads(line) for line in (self.live / 'out.jsonl').read_text().splitlines()]

    def __exit__(self, *exc):
        try:
            for ex in self.executors:
                ex.out.close()
            self.game.stop()
            self.bridge.pump()
            assert not self.bridge.inputs and not self.bridge.waiting, 'disconnect releases pending inputs'
        finally:
            self.bridge.close()
            self.stack.close()


class SendBudget:
    """Force a short write followed by EAGAIN, without replacing the actual socket transport."""
    def __init__(self, sock, budget):
        self.sock, self.budget = sock, budget

    def send(self, data):
        if self.budget == 0:
            raise BlockingIOError()
        n = self.sock.send(data if self.budget is None else data[:self.budget])
        if self.budget is not None:
            self.budget -= n
        return n

    def __getattr__(self, name):
        return getattr(self.sock, name)


def check(cond, what):
    if not cond:
        raise SystemExit('FAIL: ' + what)
    print('ok:', what)


def fails(kind, function, what):
    try:
        function()
    except kind:
        check(True, what)
    else:
        check(False, what)


def transport_checks():
    missing_oot = ("this build has no oot subscription: use hsap_file.py, or a build with "
                   "HS #2292's control-bridge commits")
    for refusal in (('bad_request', 'events: present, state, log, map'),
                    ('unknown_cmd', 'no such command'), ('unavailable', 'OoT sampling is not available')):
        with Simulation(subscribe_error=refusal) as sim:
            before = sim.clock.time()
            try:
                sim.exchange()
            except hsap.ControlError as error:
                check(str(error) == missing_oot, 'unsupported oot subscription gives the explicit driver/build choice')
            else:
                check(False, 'unsupported oot subscription must fail on its first reply')
            check(sim.clock.time() == before and sim.game.n_states == 0 and not sim.bridge.debug_lines and
                  sim.game.live_in.read_text() == '', 'oot refusal neither waits for boot nor falls back to file input')
    for refusal in (('busy', 'too many requests'), ('bad_request', 'flags: invalid name')):
        with Simulation(subscribe_error=refusal) as sim:
            try:
                sim.exchange()
            except hsap.ControlError as error:
                check(str(error) != missing_oot and refusal[0] in str(error) and refusal[1] in str(error),
                      'other subscription failures keep their actual cause')
            else:
                check(False, 'other subscription errors must still fail')

    with Simulation(watch=['Test.Flag', '0x1234abcd']) as sim:
        g, bridge = sim.game, sim.bridge
        check(sim.exchange() == [] and g.st is None, 'no fabricated state before the first Link update')
        sub = bridge.requests[0]
        check(sub == {'id': g.sub, 'cmd': 'subscribe', 'events': ['oot'], 'every': 6,
                      'flags': ['Test.Flag', '0x1234abcd'], 'changes': True}, 'oot subscribes at six presents with flags and changes')
        check(not g.pending and g.sock.getblocking() is False, 'startup replies are matched and the socket is nonblocking')
        bridge.updates = False
        bridge.frame = 900
        bridge.latest = bridge.game_state(12)
        g.request('status')
        states = sim.exchange()
        check(len(states) == 1 and g.st['frame'] == 12 and g.presents == 900,
              'status keeps the snapshot frame, not the later reply present')
        check(g.st['child'] == 1 and type(g.st['child']) is int and type(g.st['event']) is int,
              'age and booleans normalize to the pilot numeric fields')
        game = bridge.game_state(12)
        game.update(flags={'Test.Flag': 7}, changed={})
        bridge.queue({'event': 'oot', 'sub': g.sub, 'frame': 901, 'game': game})
        sim.exchange()
        check(g.n_states == 1 and g.st['flags']['Test.Flag'] == 7 and g.presents == 901,
              'same-sample event enriches status despite its later delivery present, without counting it twice')
        bridge.latest = bridge.game_state(11)
        g.request('status')
        sim.exchange()
        check(g.st['frame'] == 12, 'a late older status cannot regress the current state')
        game = bridge.game_state(13)
        game.update(map=None, age=None, event=None, loading=None, changed={'0x00000001': 9}, more=4)
        bridge.queue({'event': 'oot', 'sub': g.sub, 'frame': 902, 'game': game})
        bridge.queue({'event': 'oot', 'sub': g.sub + 100, 'frame': 1000, 'game': bridge.game_state(1000)})
        bridge.queue({'event': 'present', 'sub': g.sub, 'frame': 1001})
        sim.exchange()
        check(g.st['map'] is None and g.st['child'] is None and g.st['event'] is None and g.st['loading'] is None,
              'unreadable map and unknown booleans/age remain null, without top-level map fallback')
        check(g.st['frame'] == 13 and g.presents == 902 and g.st['more'] == 4 and g.changes == {'0x00000001': 9},
              'only matching oot samples update state, changes and overflow; sample frame is not delivery frame')
        ex = sim.executor()
        check(not ex.cond(['control'])[0](g.st), 'unknown loading/event is not control')
        ex.state_event('wait')
        event = sim.events()[-1]
        check(event['area'] is None and event['child'] is None and event['frame'] == 13 and
              event['changed'] == ['0x00000001'] and not g.changes, 'downstream state events retain the pilot schema')
        bridge.latest = dict(game, frame=13)
        for _ in range(3):
            g.request('status')
            sim.exchange()
        check(g.n_states == 2, 'retained status snapshots do not create new samples during an update gap')
        game = dict(bridge.game_state(14), age='adult', flags={'Test.Flag': 9}, changed={})
        bridge.write_limit = 7
        bridge.queue({'event': 'oot', 'sub': g.sub, 'frame': 903, 'game': game})
        sim.exchange()
        check(g.st['frame'] == 13 and g.rx, 'a partial socket line does not become a partial snapshot')
        while bridge.tx:
            sim.exchange()
        check(g.st['frame'] == 14 and g.st['child'] == 0, 'fragmented events finish and normalize adult to zero')
        journal = [json.loads(line) for line in g.state_path.read_text().splitlines()]
        check([s['frame'] for s in journal] == [12, 13, 14], 'state.jsonl is a normalized output journal, not the transport')

    with Simulation(listening=False) as sim:
        check(sim.exchange() == [] and sim.game.sock is None, 'an absent startup socket does not block polling')
        sim.bridge.listen()
        sim.clock.sleep(.3)
        sim.exchange()
        check(sim.game.sock is not None and not sim.game.pending, 'the client connects when the queued game starts')

    with Simulation(boot_events=0) as sim:
        g = sim.game
        sim.exchange()
        long_id = g.press('A', 2000)
        short_id = g.press('B', 100)
        status_id = g.request('status')
        sim.exchange()
        check(long_id in g.pending and short_id in g.pending and status_id not in g.pending,
              'status is handled while input completion replies are outstanding')
        sim.clock.sleep(.2)
        sim.exchange()
        check(long_id in g.pending and short_id not in g.pending and g.n_states >= 2,
              'a later short press replies first while oot events continue')
        sim.clock.sleep(2)
        sim.exchange()
        check(not g.pending, 'all out-of-order completions are consumed by id')
        limited = SendBudget(g.sock, 5)
        g.sock = limited
        rid = g.press('X', 100)
        sim.exchange()
        check(g.tx and rid in g.pending, 'short writes and send backpressure keep the unsent request queued')
        limited.budget = None
        sim.exchange()
        sim.clock.sleep(.2)
        sim.exchange()
        check(not g.tx and rid not in g.pending and sum(r['id'] == rid for r in sim.bridge.requests) == 1,
              'the remainder is sent once when writable, without losing or duplicating the request')
        g.request('not_a_command')
        fails(hsap.ControlError, sim.exchange, 'bridge errors are surfaced instead of silently accepting failed commands')

    with Simulation() as sim:
        sim.exchange()
        sim.bridge.tx.extend(b'{broken json}\n')
        fails(hsap.ControlError, sim.exchange, 'malformed replies fail explicitly')
    with Simulation() as sim:
        sim.exchange()
        sim.bridge.conn.close()
        sim.bridge.conn = None
        fails(hsap.ControlError, sim.game.poll, 'disconnect fails explicitly instead of reusing stale steering state')

    check(hsap.Game.frames(1) == 1 and hsap.Game.frames(100) == 6 and hsap.Game.frames(140) == 8 and
          hsap.Game.frames(200) == 12, 'millisecond holds use the bridge hos-unit rounding at 60 frames per second')
    check(all(hsap.valid_flag(n) for n in ['Test.Flag', '0x1234aBcD', 'a' * 47]) and
          not any(hsap.valid_flag(n) for n in ['', '0x123', '0x1234567g', 'a' * 48, 'space name']),
          'watch names and exact eight-digit hashes match the subscription contract')
    fails(ValueError, lambda: hsap.Game('unused', 'unused', 1, 'unused', watch=['F' + str(i) for i in range(65)]),
          'more than 64 watches are rejected before launching a game')


def executor_checks():
    # Original coverage: boot, ordinary steering, event order, distance and speed, state output.
    with Simulation(boot_events=8) as sim:
        ex = sim.executor(['walk 6 8 radius 0.6 timeout 15', 'end'], boot='newgame')
        ex.run()
        ev = sim.events()
        kinds = [e['ev'] for e in ev if e['ev'] != 'note']
        check(kinds[0] == 'gameplay' and kinds[-1] == 'done', f'gameplay first, done last: {kinds}')
        gameplay = next(e for e in ev if e['ev'] == 'gameplay')
        check(gameplay['frame'] >= 8 * 6 + 29 * 6 and sim.bridge.a_presses > 0,
              'boot presses through the socket and waits for thirty calm samples')
        step = next(e for e in ev if e['ev'] == 'step' and e['src'].startswith('walk'))
        check(step['result'] == 'reached', f"a walk to a point 10 m away is reached ({step['detail']}, {step['secs']} s)")
        check(step['secs'] < 6, 'at about 4 m/s')
        check(math.hypot(sim.bridge.pos[0] - 6, sim.bridge.pos[2] - 8) <= .6, 'Link ends within the radius')
        states = [e for e in ev if e['ev'] == 'state' and e['why'] == 'wait']
        check(states and states[-1]['pos'] and 'flags' in states[-1] and states[-1]['child'] == 1,
              'a compatible wait state line follows the steps')
        check(sim.game.live_in.read_text() == '', 'ordinary boot and steering inputs never use the live file')

    # Original coverage: the mirrored world's handedness is found and corrected.
    with Simulation(boot_events=1, handed=-1, camera=0.0, follow=False) as sim:
        sim.executor(['walk 10 0 radius 0.6 timeout 20', 'end']).run()
        ev = sim.events()
        step = next(e for e in ev if e['ev'] == 'step' and e['src'].startswith('walk'))
        check(any(e['ev'] == 'note' and 'handedness flipped' in e['text'] for e in ev), 'the stick handedness is flipped')
        check(step['result'] == 'reached', f"and the walk is reached in the mirror world ({step['detail']})")

    # Original coverage: collision reports stuck, not success.
    with Simulation(boot_events=1, walls=[(-5, 2, 5, 3)]) as sim:
        sim.executor(['walk 0 8 radius 0.5 timeout 15', 'end']).run()
        step = next(e for e in sim.events() if e['ev'] == 'step' and e['src'].startswith('walk'))
        check(step['result'] == 'stuck', f"a wall in the way ends the walk stuck ({step['detail']})")

    # Original coverage: until, repeated presses, watched flag, prompt, save and invalid step.
    with Simulation(boot_events=1, flags={'Test.Flag': 0}, prompt_at=(0.0, 3.0)) as sim:
        sim.executor(['until flag Test.Flag=1 timeout 1.5 press A every 0.3', 'walk 0 3 radius 0.3 timeout 5',
                      'until prompt=Crawl timeout 2', 'save timeout 5', 'fly 1 2', 'end']).run()
        ev = sim.events()
        steps = [e for e in ev if e['ev'] == 'step']
        check(steps[0]['result'] == 'timeout' and sim.bridge.a_presses >= 4,
              f'until times out and pressed A {sim.bridge.a_presses} times')
        check(steps[2]['result'] == 'met', 'until prompt=Crawl is met at the hole')
        check(steps[3]['result'] == 'done' and 'slot_00' in steps[3]['detail'], f"save: {steps[3]['detail']}")
        check(any(e['ev'] == 'bad' and e['src'] == 'fly 1 2' for e in ev), 'an unknown step is answered bad')
        sim.bridge.flags['Test.Flag'] = 1
        sim.clock.sleep(.2)
        sim.exchange()
        ex = sim.executors[0]
        check(ex.until(['flag', 'Test.Flag=1', 'timeout', '1'])[0] == 'met' and sim.game.changes['0x00000001'] == 1,
              'watched flag updates and change deltas arrive through oot events')

    # Original analog coverage plus delayed replies: steering must not serialize on completion acknowledgements.
    with Simulation(boot_events=1, follow=False, camera=30.0, ack_delay=30) as sim:
        ex = sim.executor(['walk 7 -3 radius 0.4 timeout 15', 'end'])
        ex.analog = True
        ex.run()
        step = next(e for e in sim.events() if e['ev'] == 'step' and e['src'].startswith('walk'))
        sticks = [r for r in sim.bridge.requests if r['cmd'] == 'stick']
        check(step['result'] == 'reached' and sticks and all(r['stick'] == 'L' and r['frames'] == 8 for r in sticks),
              f"an analog walk is reached with socket stick inputs ({step['detail']}, {len(sticks)} presses)")
        check(any(0 < abs(r['x']) < .99 and 0 < abs(r['y']) < .99 for r in sticks) and
              any(math.hypot(r['x'], r['y']) < .6 for r in sticks), 'exact angles and near-target half pushes reach the wire')
        samples = [frame for cmd, frame in sim.input_samples if cmd == 'stick']
        check(len(samples) == len(set(samples)) and max(b - a for a, b in zip(samples, samples[1:])) <= 6,
              'steering sends once per fresh six-present sample, not once per input reply')
        check(sim.bridge.max_waiting >= 4, 'several outstanding input replies do not block steering')

    with Simulation(boot_events=0, ack_delay=18) as sim:
        ex = sim.executor(['press ZL+R 100', 'stick up-right 250', 'push -12345 23456 200',
                           'raw 0:LUP/200,0.1:A/100,0.3:LX=123+LY=-456/50 0.6', 'cheat 1', 'shot', 'end'])
        ex.run()
        inputs = [r for r in sim.bridge.requests if r['cmd'] in ('press', 'stick', 'sequence')]
        check([r['cmd'] for r in inputs] == ['press', 'stick', 'stick', 'sequence'],
              'press, stick, push and raw choose the bridge input commands')
        check(inputs[0]['buttons'] == 'ZL+R' and inputs[0]['frames'] == 6 and inputs[1]['x'] == inputs[1]['y'] == 1 and
              inputs[1]['frames'] == 15 and round(inputs[2]['x'] * 32767) == -12345 and
              round(inputs[2]['y'] * 32767) == 23456, 'button holds, directional sticks and exact integer pushes survive conversion')
        check(inputs[3]['units'] == 'hos' and inputs[3]['script'] == '0:LUP/200,0.1:A/100,0.3:LX=123+LY=-456/50',
              'raw sequences preserve offsets, durations and analog tokens in hos units')
        steps = [e for e in sim.events() if e['ev'] == 'step']
        check(steps[0]['secs'] >= .4 and steps[1]['secs'] >= .55,
              'discrete steps wait for their frame-completion reply while continuing to poll state')
        check(sim.game.live_in.read_text().splitlines() == ['!cheat 1', '!shots 1'],
              'only debug-only cheats and shots retain live-file delivery')

    with Simulation(boot_events=0) as sim:
        ex = sim.executor()
        check(ex.to_control(), 'control reached before update-gap steering check')
        before = sim.game.n_states
        sim.bridge.updates = False
        result, _ = ex.walk(20, 0, .5, .5)
        check(result == 'timeout' and len(sim.input_samples) <= 1 and sim.game.n_states == before,
              'an update gap cannot manufacture samples or repeatedly steer from a retained snapshot')
        sim.bridge.updates = True
        sim.bridge.event_override = True
        sim.clock.sleep(.2)
        sim.exchange()
        before = len(sim.input_samples)
        result, _ = ex.walk(20, 0, .5, 2)
        check(result == 'held' and len(sim.input_samples) == before, 'an event holds the walk without issuing new inputs')


# ---- the duel: the game's log lines, the opponent's place, the steps, a game that restarts itself

HEAD = '[hos 100.250] coop: duel: '
CANNED = {
    'terms': HEAD + 'state Read terms match 7a3f round 1 score 0-0 hearts 40/40 self 0 ready 00 reason terms read',
    'count': HEAD + 'state Countdown match 7a3f round 1 score 0-0 hearts 40/40 self 1 ready 11 reason both ready',
    'duel': HEAD + 'state Duel match 7a3f round 1 score 0-0 hearts 36/40 self 1 ready 11 reason ',
    'finish': HEAD + 'state Finishing round match 7a3f round 1 score 0-0 hearts 36/0 self 1 ready 11 reason hearts at 0',
    'round': HEAD + 'state Round ended match 7a3f round 1 score 0-1 hearts 36/0 self 1 ready 00 reason round over',
    'match': HEAD + 'state Match ended match 7a3f round 2 score 0-2 hearts 20/0 self 1 ready 00 reason match won by member 3',
    'interrupted': HEAD + 'state Interrupted match 7a3f round 2 score 0-1 hearts 20/8 self 1 ready 00 reason arena left',
    'hit': HEAD + 'swing member 2 id 5 node CutS1 frame 12 dist 1.23 bearing -4.5 dy 0.02 result hit native 4 amount 4 self_hearts 36',
    'shielded': HEAD + 'swing member 2 id 6 node CutS1 frame 11.5 dist 1.10 bearing 2.0 dy 0.00 result shielded native 4 amount 0 self_hearts 36',
    'range': HEAD + 'swing member 2 id 7 node CutS2 frame 13 dist 3.40 bearing 10.0 dy 0.10 result range native 4 amount 0 self_hearts 36',
    'refused': HEAD + 'Ready refused: native sword contact, damage, shield and arena safety are not proven; no fight started',
}


def duel_parse_checks():
    P = hsap.parse_duel_line
    check(P('coop: puppet: member 2 is shown as CoopPuppet_Child') is None and P('') is None and
          P('coop: duelist: state Duel') is None, 'other lines are not duel lines')
    check(P(CANNED['terms']) == {'kind': 'state', 'state': 'Read terms', 'match': '7a3f', 'round': 1, 'score': [0, 0],
                                 'hearts': [40, 40], 'self': 0, 'ready': [0, 0], 'reason': 'terms read'},
          'a state line with a two-word state, its ready flags and its reason')
    d = P(CANNED['duel'])
    check(d['state'] == 'Duel' and d['hearts'] == [36, 40] and d['self'] == 1 and d['reason'] == '' and d['ready'] == [1, 1],
          'an empty reason, hearts in quarter units, self 1')
    check([P(CANNED[k])['state'] for k in ('count', 'finish', 'round', 'match', 'interrupted')] ==
          ['Countdown', 'Finishing round', 'Round ended', 'Match ended', 'Interrupted'] and
          P(CANNED['match'])['score'] == [0, 2] and P(CANNED['interrupted'])['reason'] == 'arena left',
          'every state name, the score and a reason with spaces')
    s = P(CANNED['hit'])
    check(s == {'kind': 'swing', 'member': 2, 'id': 5, 'node': 'CutS1', 'frame': 12.0, 'dist': 1.23, 'bearing': -4.5,
                'dy': 0.02, 'result': 'hit', 'native': 4, 'amount': 4, 'self_hearts': 36}, 'a swing that hit')
    check(P(CANNED['shielded'])['result'] == 'shielded' and P(CANNED['shielded'])['amount'] == 0 and
          P(CANNED['shielded'])['frame'] == 11.5, 'a swing the shield took')
    check(P(CANNED['range'])['result'] == 'range' and P(CANNED['range'])['dist'] == 3.4, 'a swing that missed by range')
    results = ('hit', 'shielded', 'invulnerable', 'range', 'facing', 'height', 'kit', 'grace', 'replay', 'capability', 'window')
    check(all(P(CANNED['hit'].replace('result hit', 'result ' + r))['result'] == r for r in results),
          'every swing result the log names: ' + ', '.join(results))
    check(P(CANNED['refused']) == {'kind': 'refused', 'text': CANNED['refused'].split('coop: duel: ')[1]},
          'the diagnostic Ready refusal of a build without the native duel')
    check(P(HEAD + 'something new 12') == {'kind': 'note', 'text': 'something new 12'}, 'an unknown duel line is kept as a note')

    t = hsap.DuelTracker()
    check(t.snapshot(5.0) is None, 'no duel line, no duel block')
    t.feed('coop: puppet: nothing', 1.0)
    check(t.snapshot(5.0) is None, 'a line that is not about the duel changes nothing')
    for key, at in (('terms', 10.0), ('count', 11.0), ('duel', 14.2), ('hit', 15.0), ('shielded', 16.0), ('range', 17.0)):
        t.feed(CANNED[key], at)
    snap = t.snapshot(17.5)
    check(snap['state'] == 'Duel' and snap['own_hearts'] == 40 and snap['opp_hearts'] == 36 and snap['self'] == 1 and
          snap['own_ready'] == 1 and snap['opp_ready'] == 1 and snap['round'] == 1 and snap['score'] == [0, 0],
          'own hearts are the entry of this game\'s own index (self 1: the second of hearts 36/40 is its own)')
    check(snap['swings'] == {'hit': 1, 'shielded': 1, 'range': 1} and snap['last_swing']['result'] == 'range' and
          snap['last_swing']['age_s'] == 0.5 and snap['in_state_s'] == 3.3,
          'swing counts by result, the last swing with its age, the time in the state (kept over repeats of it)')
    t.feed(CANNED['duel'], 20.0)
    check(t.snapshot(21.0)['in_state_s'] == 6.8, 'a repeated state line does not restart the time in the state')
    t.feed(CANNED['refused'], 22.0)
    check(t.snapshot(22.0)['refused'].startswith('Ready refused') and t.snapshot(22.0)['refusals'] == 1,
          'a refusal is kept with its count')
    t.feed(CANNED['count'], 23.0)
    check(t.snapshot(23.0)['refused'] is None and t.snapshot(23.0)['refusals'] == 1, 'a countdown clears the refusal')
    for key in ('finish', 'round', 'match'):
        t.feed(CANNED[key], 30.0)
    snap = t.snapshot(31.0)
    check(snap['state'] == 'Match ended' and snap['own_score'] == 2 and snap['opp_score'] == 0 and snap['reason'].startswith('match won'),
          'Match ended with the score from this game\'s side')

    # a series: every match that ended is remembered by its id; a repeated line counts once; ids are the game's own (decimal)
    def S(mid, state, rnd, s0, s1, q0=40, q1=40, me=0, ready='00', reason=''):
        return f'{HEAD}state {state} match {mid} round {rnd} score {s0}-{s1} hearts {q0}/{q1} self {me} ready {ready} reason {reason}'
    t = hsap.DuelTracker()
    t.feed(S(4294967297, 'Duel', 1, 0, 0), 1.0)
    snap = t.snapshot(1.0)
    check(snap['matches_ended'] == 0 and snap['matches_won'] == 0 and snap['matches_lost'] == 0 and snap['match_results'] == [],
          'a duel in progress has ended no match')
    for at in (5.0, 5.0, 6.5):   # the same line three times (a replay)
        t.feed(S(4294967297, 'Match ended', 2, 2, 0, 12, 0, me=0, reason='match won'), at)
    snap = t.snapshot(7.0)
    check(snap['matches_ended'] == 1 and snap['matches_won'] == 1 and snap['matches_lost'] == 0 and
          snap['match_results'] == [{'id': '4294967297', 'own_score': 2, 'opp_score': 0, 'won': True}],
          'a replayed identical Match ended line counts once')
    t.feed(S(8589934593, 'Read terms', 1, 0, 0), 8.0)
    check(t.snapshot(8.0)['matches_ended'] == 1 and t.snapshot(8.0)['state'] == 'Read terms',
          'the next match begins: the count of ended matches stays')
    t.feed(S(8589934593, 'Match ended', 3, 1, 2, 0, 8, me=0), 20.0)
    snap = t.snapshot(21.0)
    check(snap['matches_ended'] == 2 and snap['matches_won'] == 1 and snap['matches_lost'] == 1 and
          [m['won'] for m in snap['match_results']] == [True, False], 'a second match that was lost is counted as lost')
    t.feed(S(4294967297, 'Match ended', 2, 2, 0, 12, 0, me=0), 22.0)
    t.feed(S(12884901889, 'Interrupted', 2, 1, 0, 12, 20, me=0, reason='arena left'), 30.0)
    check(t.snapshot(31.0)['matches_ended'] == 2 and t.snapshot(31.0)['state'] == 'Interrupted',
          'an old id again, and an interrupted match, are no new ended match')
    t2 = hsap.DuelTracker()
    t2.feed(S(77, 'Match ended', 2, 0, 2, 0, 24, me=1), 3.0)
    check(t2.snapshot(3.0)['matches_won'] == 1 and t2.snapshot(3.0)['match_results'][0]['own_score'] == 2,
          'the winner is read from this game\'s own index (self 1: its score is the second)')
    t2.feed(S(78, 'Match ended', 2, 1, 1), 4.0)
    check(t2.snapshot(4.0)['matches_ended'] == 2 and t2.snapshot(4.0)['match_results'][1]['won'] is None and
          t2.snapshot(4.0)['matches_won'] == 1 and t2.snapshot(4.0)['matches_lost'] == 0,
          'a drawn score is an ended match nobody won')
    t3 = hsap.DuelTracker()
    for _ in range(2):
        t3.feed(CANNED['refused'], 1.0)
    check(t3.snapshot(1.0)['refusals'] == 2 and t3.snapshot(1.0)['refusal_run'] == 2, 'refusals are counted, and as a run')
    t3.feed(CANNED['count'], 2.0)
    t3.feed(CANNED['refused'], 3.0)
    check(t3.snapshot(3.0)['refusals'] == 3 and t3.snapshot(3.0)['refusal_run'] == 1,
          'a Countdown ends the run of refusals (the total stays): a series is not given up on old refusals')

    check(hsap.where(0) == 'ahead' and hsap.where(40) == 'ahead-left' and hsap.where(-90) == 'right' and
          hsap.where(135) == 'behind-left' and hsap.where(-179) == 'behind' and hsap.where(None) is None, 'bearing words')
    pos = [10.0, 5.0, 20.0]
    b = hsap.opponent_block(pos, 0.0, {'x': 13.0, 'z': 24.0, 'y': 6.5, 'map': 'M', 'w': 99.5}, 100.0, 'M')
    check(b == {'x': 13.0, 'z': 24.0, 'distance_m': 5.0, 'bearing_deg': 36.9, 'rel_deg': 36.9, 'where': 'ahead-left',
                'y': 6.5, 'dy_m': 1.5, 'age_s': 0.5}, 'distance, bearing and bearing relative to Link\'s facing (positive: his left)')
    b = hsap.opponent_block(pos, 90.0, {'x': 13.0, 'z': 24.0}, None, None)
    check(b['rel_deg'] == -53.1 and b['where'] == 'ahead-right' and 'age_s' not in b and 'dy_m' not in b,
          'the same man seen by Link facing +x: to his right')
    check(hsap.opponent_block(pos, 0.0, {'x': 1.0, 'z': 2.0, 'map': 'Other'}, None, 'M') is None and
          hsap.opponent_block(pos, 0.0, {'x': 'a', 'z': 2.0}, None, None) is None and
          hsap.opponent_block(pos, 0.0, None, None, None) is None, 'another map, a bad file and no file give no opponent')
    check(hsap.opponent_block(pos, None, {'x': 13.0, 'z': 24.0}, None, None)['rel_deg'] is None, 'no facing, no relative bearing')

    with tempfile.TemporaryDirectory(prefix='hsap-tail-') as d:
        path = Path(d) / 'log.txt'
        tail = hsap.Tail(path)
        check(tail.lines() == [], 'a log that does not exist yet reads nothing')
        path.write_text('one\ntwo\npart')
        check(tail.lines() == ['one', 'two'], 'whole lines only')
        with open(path, 'a') as f:
            f.write('ial\nthree\n')
        check(tail.lines() == ['partial', 'three'], 'the rest of a partial line is joined')
        path.write_text('new run\n')   # truncated and written again (a shorter file)
        check(tail.lines() == ['new run'], 'a truncated log is read from its start')
        replacement = Path(d) / 'log.tmp'
        replacement.write_text('replaced one\nreplaced two\nreplaced three\n')
        os.replace(replacement, path)   # a new file under the old name, longer than the old read offset
        check(tail.lines() == ['replaced one', 'replaced two', 'replaced three'], 'a replaced log is read from its start')


class DuelBridge(FakeBridge):
    """FakeBridge plus: Link's facing follows his stick (he turns where he pushes), the live file's !duel lines are
    answered in the game's log, a hook runs at every frame, and the control socket can be dropped and brought back like
    a game's that restarts itself (a new process: its frame counter, subscription and listener start again)."""
    def __init__(self, *args, face=0.0, script=None, **kwargs):
        self.face, self.script, self.seen, self.on_tick = face, dict(script or {}), 0, None
        super().__init__(*args, **kwargs)

    def game_state(self, frame=None):
        state = super().game_state(frame)
        state['facing'] = round(self.face, 1)
        return state

    def tick(self):
        axes = {}
        for step in self.inputs:
            if step['start'] <= self.frame + 1 < step['end']:
                axes.update(step['axes'])
        sx, sy = axes.get('lx', 0), axes.get('ly', 0)
        if self.updates and (sx or sy) and not self.game_state()['event']:
            self.face = hsap.wrap(self.cam - self.handed * math.degrees(math.atan2(sx, sy)))
        super().tick()
        if self.on_tick:
            self.on_tick(self)

    def pump(self):
        super().pump()
        for line in self.debug_lines[self.seen:]:
            for out in self.script.get(line, []):
                with open(self.run / 'hookshot_log.txt', 'a') as f:
                    f.write(out + '\n')
        self.seen = len(self.debug_lines)

    def drop(self):
        """The game execs itself: every descriptor closes; the old socket file stays until the new process replaces it."""
        if self.conn:
            self.conn.close()
            self.conn = None
        if self.listener:
            self.listener.close()
            self.listener = None
        self.inputs.clear()
        self.waiting.clear()
        self.rx.clear()
        self.tx.clear()
        self.sub = None
        self.panel = None

    def revive(self):
        os.unlink(self.path)
        self.listen()
        self.frame = self.last_sample = 0
        self.latest = self.baseline = None

    def log(self, text):
        with open(self.run / 'hookshot_log.txt', 'a') as f:
            f.write(text + '\n')


class DuelSimulation(Simulation):
    def launch(self, cmd, **kwargs):
        self.launched, self.launch_env = list(cmd), kwargs.get('env')
        args = dict(arg.split('=', 1) for arg in cmd[4:] if '=' in arg)
        self.bridge = DuelBridge(Path(args['HOS_CONTROL']), Path(args['HOS_INPUT_LIVE']), self.copy / 'runs/test',
                                 self.clock, **self.options)
        self.clock.bridge = self.bridge
        return FakeRunner()

    @property
    def opp_path(self):
        return self.live.parent / 'opp.json'

    def opponent(self, x, z, y=None, map_='Test_Map', age=0.0):
        data = {'x': x, 'z': z, 'map': map_, 'w': self.clock.time() - age}
        if y is not None:
            data['y'] = y
        tmp = self.opp_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(data))
        os.replace(tmp, self.opp_path)

    def executor(self, steps=(), boot='none', opponent=True, hud=False):
        (self.live / 'steps.txt').write_text(''.join(s + '\n' for s in steps))
        ex = hsap.Executor(self.game, self.live, boot, opponent_path=str(self.opp_path) if opponent else None, **({'hud': True} if hud else {}))
        ex.analog = False
        self.executors.append(ex)
        return ex

    def steps(self):
        return [e for e in self.events() if e['ev'] == 'step' and e['src'] != 'end']


def duel_step_checks():
    # the plain steps, their inputs on the wire, the live file, the duel in the state line, and what is refused as bad
    script = {'!duel ready': [CANNED['count']], '!duel cancel': [CANNED['interrupted']]}
    with DuelSimulation(boot_events=0, follow=False, script=script) as sim:
        ex = sim.executor(['swing', 'shield', 'shield 1500', 'duel ready', 'duel cancel', 'end'], opponent=False)
        ex.run()
        presses = [r for r in sim.bridge.requests if r['cmd'] == 'press']
        check([(r['buttons'], r['frames']) for r in presses] == [('Y', 7), ('ZL', 42), ('ZL', 90)],
              'swing presses Y for 120 ms, shield holds ZL 700 ms by default and as long as asked')
        check(all(r['exclusive'] and r['wait'] for r in presses), 'duel inputs are exclusive and waited for, like the others')
        steps = sim.steps()
        check([s['result'] for s in steps[:3]] == ['done'] * 3 and steps[1]['detail'] == 'ZL held 700 ms',
              'swing and shield steps end done')
        check(sim.game.live_in.read_text().splitlines() == ['!duel ready', '!duel cancel'],
              'duel ready and duel cancel go to the live input file, as !cheat does')
        check(steps[3]['result'] == 'done' and steps[3]['detail'] == 'duel Countdown round 1 hearts 40/40',
              f"duel ready answers with what the log then says ({steps[3]['detail']})")
        check(steps[4]['result'] == 'done' and 'Interrupted' in steps[4]['detail'], 'duel cancel likewise')
        states = [e for e in sim.events() if e['ev'] == 'state']
        check('duel' not in states[0] and 'opponent' not in states[0],
              'before any duel line the state line has no duel block (other segments\' lines are unchanged)')
        d = states[-1]['duel']
        check(d['state'] == 'Interrupted' and d['reason'] == 'arena left' and d['own_hearts'] == 8 and d['opp_hearts'] == 20 and
              d['self'] == 1 and d['round'] == 2 and 'opponent' not in states[-1],
              'afterwards it carries the duel from the game\'s log, and no opponent without a file')

    with DuelSimulation(boot_events=0, follow=False, script={'!duel ready': [CANNED['refused']]}) as sim:
        sim.executor(['duel ready', 'end'], opponent=False).run()
        s = sim.steps()[0]
        check(s['result'] == 'refused' and s['detail'].startswith('Ready refused: native sword contact'),
              'a Ready the build refuses ends refused, with its reason')

    bad = ['swing now', 'shield abc', 'shield 10', 'shield 9000', 'shield 1 2', 'roll', 'roll sideways', 'roll up down',
           'sidestep', 'sidestep up 100', 'sidestep left', 'sidestep left x', 'sidestep left 99999', 'approach',
           'approach 0', 'approach x', 'approach 2 timeout', 'approach 2 late 5', 'face a', 'face 1 2', 'duel', 'duel go',
           'duel ready now']
    with DuelSimulation(boot_events=0, follow=False) as sim:
        sim.executor(bad + ['wait 0.1', 'end']).run()
        ev = sim.events()
        got = [e['src'] for e in ev if e['ev'] == 'bad']
        check(got == bad, f'{len(bad)} malformed duel steps are answered bad, each by its own usage text')
        check(not [r for r in sim.bridge.requests if r['cmd'] in ('press', 'stick', 'sequence')], 'and none of them sent an input')


def duel_geometry_checks():
    # Link at the origin facing +z (yaw 0), camera yaw 0, the stick's right is the camera's right: a world in which the
    # opponent's side can be told from the numbers (+x is Link's left when he faces +z)
    with DuelSimulation(boot_events=0, follow=False, camera=0.0) as sim:
        sim.opponent(-4.0, 0.0, y=0.5)
        ex = sim.executor(['face', 'end'])
        ex.run()
        s = sim.steps()[0]
        check(s['result'] == 'done' and abs(hsap.wrap(sim.bridge.face + 90)) <= 20 and 'within' in s['detail'],
              f"face turns Link toward an opponent on his right ({s['detail']}, now facing {sim.bridge.face:.0f})")
        st = [e for e in sim.events() if e['ev'] == 'state'][-1]
        check(abs(st['opponent']['rel_deg']) <= 20 and st['opponent']['distance_m'] < 4.5 and st['opponent']['dy_m'] == 0.5 and
              st['opponent']['age_s'] >= 0, 'the state line shows him ahead after that, with his distance and age')
    with DuelSimulation(boot_events=0, follow=False, camera=0.0, face=180.0) as sim:
        sim.opponent(0.0, 5.0)
        ex = sim.executor(['face 10', 'end'])
        ex.run()
        s = sim.steps()[0]
        check(s['result'] == 'done' and abs(hsap.wrap(sim.bridge.face)) <= 10, f"face from behind him: {s['detail']}")
        st = [e for e in sim.events() if e['ev'] == 'state'][0]
        check(st['opponent']['where'] == 'behind' and st['opponent']['rel_deg'] in (180.0, -180.0) and st['facing'] == 180.0,
              'a state taken before the turn put him behind Link')

    with DuelSimulation(boot_events=0, follow=False, camera=0.0) as sim:
        sim.opponent(0.0, 10.0)
        sim.executor(['approach 1.5 timeout 10', 'end']).run()
        s = sim.steps()[0]
        dist = math.hypot(sim.bridge.pos[0], sim.bridge.pos[2] - 10.0)
        check(s['result'] == 'reached' and 1.0 <= dist <= 1.5 and 'm from the point' in s['detail'],
              f"approach walks toward a still opponent and stops within the distance ({s['detail']}, now {dist:.2f} m)")

    with DuelSimulation(boot_events=0, follow=False, camera=0.0) as sim:
        sim.opponent(6.0, 6.0)
        ex = sim.executor(['approach 1.5 timeout 15', 'end'])

        def walk_away(b):   # he walks along +z at 1 m/s and the runner's file follows him ten times a second
            if b.frame % 6 == 0:
                sim.opponent(6.0, 6.0 + b.frame / 60)
        sim.bridge.on_tick = walk_away
        ex.run()
        s = sim.steps()[0]
        end = json.loads(sim.opp_path.read_text())
        dist = math.hypot(sim.bridge.pos[0] - end['x'], sim.bridge.pos[2] - end['z'])
        check(s['result'] == 'reached' and end['z'] > 8.0 and dist <= 1.9,
              f"approach re-aims at each sample: a walking opponent is caught ({s['detail']}; he went to z {end['z']:.1f})")

    with DuelSimulation(boot_events=0, follow=False, camera=0.0) as sim:
        sim.opponent(0.0, 20.0)
        ex = sim.executor(['approach 1 timeout 10', 'end'])
        sim.bridge.on_tick = lambda b: sim.opp_path.exists() and b.frame == 90 and sim.opp_path.unlink()
        ex.run()
        check(sim.steps()[0]['result'] == 'no-opponent', 'approach ends no-opponent when his place goes away')

    with DuelSimulation(boot_events=0, follow=False, camera=0.0, walls=[(-5, 2, 5, 3)]) as sim:   # a wall between him and Link
        sim.opponent(0.0, 8.0)
        sim.executor(['approach 1.5 timeout 15', 'end']).run()
        s = sim.steps()[0]
        check(s['result'] == 'stuck' and 'moved under 0.3 m' in s['detail'], f"approach against a wall ends stuck, as walk does ({s['detail']})")
    with DuelSimulation(boot_events=0, follow=False, camera=0.0) as sim:   # already in range: nothing to do
        sim.opponent(0.0, 1.0)
        sim.executor(['approach 1.5', 'end']).run()
        s = sim.steps()[0]
        check(s['result'] == 'reached' and s['moved'] == 0.0 and not [r for r in sim.bridge.requests if r['cmd'] in ('press', 'stick')],
              'approach within the distance already: reached at once, nothing sent')

    # sidestep and roll: perpendicular to the line to him, and the A press with the stick
    with DuelSimulation(boot_events=0, follow=False, camera=0.0) as sim:
        sim.opponent(0.0, 6.0)
        sim.executor(['sidestep left 500', 'end']).run()
        x, z = sim.bridge.pos[0], sim.bridge.pos[2]
        check(sim.steps()[0]['result'] == 'done' and x > 1.5 and abs(z) < 0.3,
              f'sidestep left moves Link to his left of the line to an opponent straight ahead (x {x:.2f}, z {z:.2f})')
    with DuelSimulation(boot_events=0, follow=False, camera=0.0) as sim:
        sim.opponent(0.0, 6.0)
        sim.executor(['sidestep right 500', 'end']).run()
        x, z = sim.bridge.pos[0], sim.bridge.pos[2]
        check(x < -1.5 and abs(z) < 0.3, f'sidestep right to the other side (x {x:.2f}, z {z:.2f})')
    with DuelSimulation(boot_events=0, follow=False, camera=90.0) as sim:   # camera turned: still perpendicular to him
        sim.opponent(4.0, 0.0)   # at yaw 90 from the origin
        sim.executor(['sidestep left 500', 'end']).run()
        x, z = sim.bridge.pos[0], sim.bridge.pos[2]
        check(abs(x) < 0.3 and z < -1.5, f'the camera does not matter: left of the line to him is -z here (x {x:.2f}, z {z:.2f})')

    with DuelSimulation(boot_events=0, follow=False, camera=0.0) as sim:
        sim.opponent(0.0, 6.0)
        sim.executor(['roll away', 'roll toward', 'roll around-left', 'roll around-right', 'roll up', 'roll down-left', 'end']).run()
        seqs = [r for r in sim.bridge.requests if r['cmd'] == 'sequence']

        def axes(r):
            lx, ly = (int(v) for v in re.findall(r'L[XY]=(-?\d+)', r['script']))
            return round(lx / 32767), round(ly / 32767)
        check(len(seqs) == 6 and all(re.fullmatch(r'0:LX=-?\d+\+LY=-?\d+/240,0\.05:A/100', r['script']) for r in seqs),
              'a roll is the stick for 240 ms with A pressed 50 ms in, as one sequence')
        check([axes(r) for r in seqs] == [(0, -1), (0, 1), (-1, 0), (1, 0), (0, 1), (-1, -1)],
              'away is back from the opponent, toward is at him, around-left/right perpendicular (the stick\'s right is '
              'Link\'s right: world -x when he faces +z), named directions as for stick')
        check(sim.bridge.a_presses == 6 and [s['result'] for s in sim.steps()] == ['done'] * 6, 'six rolls, six A presses')

    with DuelSimulation(boot_events=0, follow=False, camera=0.0) as sim:   # no file, a stale map, no steps that need him
        ex = sim.executor(['face', 'approach 2', 'sidestep left 300', 'roll away', 'roll up', 'swing', 'end'])
        ex.run()
        check([s['result'] for s in sim.steps()] == ['no-opponent'] * 4 + ['done', 'done'],
              'without an opponent file the aimed steps say so and send nothing; a camera-relative roll and a swing still work')
    with DuelSimulation(boot_events=0, follow=False, camera=0.0) as sim:
        sim.opponent(5.0, 5.0, map_='Elsewhere')
        sim.executor(['face', 'end']).run()
        check(sim.steps()[0]['result'] == 'no-opponent' and 'opponent' not in [e for e in sim.events() if e['ev'] == 'state'][-1],
              'a place on another map is no opponent')

    # the duel block and the opponent block ride the pilot's state line; the log tail copes with a log that starts again
    with DuelSimulation(boot_events=0, follow=False, camera=0.0) as sim:
        ex = sim.executor()
        ex.to_control()
        sim.opponent(3.0, 4.0, y=1.5, age=0.5)
        sim.bridge.log('coop: unrelated: line')
        for key in ('terms', 'count', 'duel', 'hit'):
            sim.bridge.log(CANNED[key])
        sim.clock.sleep(0.3)
        sim.exchange()
        ex.state_event('wait')
        e = sim.events()[-1]
        check(e['opponent']['distance_m'] == 5.0 and e['opponent']['rel_deg'] == 36.9 and e['opponent']['where'] == 'ahead-left' and
              e['opponent']['dy_m'] == 1.5 and 0.4 <= e['opponent']['age_s'] < 1.5,
              f"the state line's opponent: {e['opponent']}")
        check(e['duel']['state'] == 'Duel' and e['duel']['own_hearts'] == 40 and e['duel']['opp_hearts'] == 36 and
              e['duel']['last_swing']['result'] == 'hit' and e['duel']['swings'] == {'hit': 1},
              'the state line tails the game\'s own log for the duel')
        (sim.bridge.run / 'hookshot_log.txt').write_text(CANNED['round'] + '\n')   # the log starts again, shorter
        sim.clock.sleep(0.2)
        sim.exchange()
        ex.state_event('wait')
        check(sim.events()[-1]['duel']['state'] == 'Round ended' and sim.events()[-1]['duel']['own_score'] == 1,
              'a log that was replaced by a shorter one is read from its start')


def restart_checks():
    # the game execs itself into a temporary save copy: same process, the control socket replaced at the same path
    with DuelSimulation(boot_events=0) as sim:
        g, bridge = sim.game, sim.bridge
        g.reconnect_wait = 30.0
        sim.clock.sleep(1.0)
        sim.exchange()
        first_t, first_sub = g.st['t'], g.sub
        bridge.log(CANNED['count'])
        sim.clock.sleep(0.2)
        sim.exchange()
        check(g.duel.snapshot(g.st['t'])['state'] == 'Countdown', 'a duel line of the first process is in the ledger')
        long_id = g.press('A', 5000)
        sim.exchange()
        check(g.st is not None and g.restarts == 0 and long_id in g.pending, 'state flows and a long input is outstanding')
        bridge.drop()
        sim.clock.sleep(1.0)   # the old socket file is still there with nobody listening: connection refused
        sim.exchange()
        check(g.restarts == 1 and g.down and g.st is None and long_id not in g.pending and g.duel.snapshot(0.0) is None,
              'a closed connection while the runner lives is a restart: no error, the waited input is released, no stale state, '
              'and a new duel ledger')
        lost = g.press('B', 100)
        check(lost not in g.pending and g.tx.count(b'"press"') == 0, 'an input meant for the old process is not queued for the new one')
        for _ in range(8):
            sim.clock.sleep(0.5)
            sim.exchange()
        check(g.down and g.restarts == 1, 'polling goes on quietly while the new socket is not there yet')
        bridge.revive()
        for _ in range(6):
            sim.clock.sleep(0.3)
            sim.exchange()
        subs = [r for r in bridge.requests if r['cmd'] == 'subscribe']
        check(not g.down and g.st is not None and g.st['frame'] < 120 and len(subs) == 2 and g.sub == subs[-1]['id'] != first_sub and
              subs[-1]['events'] == ['oot'] and subs[-1]['every'] == 6 and subs[-1]['changes'] is True,
              'the new socket is subscribed to again, and its samples (a frame counter from 0) are taken')
        check(first_t < g.st['t'] <= first_t + 3.0,
              f"game time goes on from where it was although the new process counts from 0 ({first_t:.2f} -> {g.st['t']:.2f})")
        check(not any(r['cmd'] == 'press' and r.get('buttons') == 'B' for r in bridge.requests), 'the input dropped in the gap never arrived')

    with DuelSimulation(boot_events=0) as sim:   # nobody comes: an end with the reason, at the end of the wait
        sim.game.reconnect_wait = 5.0
        sim.exchange()
        sim.bridge.drop()
        try:
            for _ in range(40):
                sim.clock.sleep(0.5)
                sim.exchange()
        except hsap.ControlError as e:
            check(str(e) == 'control connection closed and no new socket within 5 s', 'no new socket in time ends the run: ' + str(e))
        else:
            check(False, 'a socket that never comes back must end the run')
    with DuelSimulation(boot_events=0) as sim:   # the runner is gone: the old behaviour
        sim.game.reconnect_wait = 30.0
        sim.exchange()
        sim.game.runner.running = False
        sim.bridge.drop()
        sim.clock.sleep(0.2)
        fails(hsap.ControlError, sim.game.poll, 'a closed connection with the runner gone still ends the run')
    with DuelSimulation(boot_events=0) as sim:   # the runner ends during the wait
        sim.game.reconnect_wait = 30.0
        sim.exchange()
        sim.bridge.drop()
        sim.clock.sleep(0.5)
        sim.exchange()
        sim.game.runner.running = False
        fails(hsap.ControlError, lambda: [sim.clock.sleep(0.5), sim.exchange()], 'the runner ending while waiting for the socket ends the run')

    # a step in flight when it happens is cut, then the executor boots through the title again and goes on
    with DuelSimulation(boot_events=8) as sim:
        sim.game.reconnect_wait = 60.0
        ex = sim.executor(['walk 0 200 radius 0.5 timeout 120', 'swing', 'end'], boot='continue', opponent=False)
        phase, mark = {'n': 0}, {}

        def restart(b):
            if phase['n'] == 0 and b.frame >= 900 and sim.game.st is not None:
                b.drop()
                phase.update(n=1, at=sim.clock.time())
                mark['presses'] = b.a_presses
            elif phase['n'] == 1 and sim.clock.time() >= phase['at'] + 3.0:
                b.revive()
                b.boot_events = 8
                b.log('vk: 0 presents, 60 fps; a frame: 15 draws')   # the new process's title
                phase['n'] = 2
        sim.bridge.on_tick = restart
        ex.run()
        ev = sim.events()
        steps = sim.steps()
        check(steps[0]['result'] == 'cut' and 'restarted itself' in steps[0]['detail'], f"a walk in flight is cut: {steps[0]['detail']}")
        check(any(e['ev'] == 'note' and 'restarted itself' in e['text'] for e in ev), 'a note says the game restarted itself')
        gameplay = [e for e in ev if e['ev'] == 'gameplay']
        check(len(gameplay) == 2 and gameplay[1]['restart'] == 1, 'gameplay is reported again once Link is in control after it')
        check(sim.bridge.a_presses > mark['presses'], 'the title of the new process is pressed through again (boot continue)')
        check(steps[1]['src'] == 'swing' and steps[1]['result'] == 'done' and ev[-1]['ev'] == 'done',
              'the steps after the restart run on the new process and the run ends done')
        ts = [e['t'] for e in ev if e['ev'] in ('state', 'step')]
        check(ts == sorted(ts), 'the steps\' game time never goes back over the restart')
        presses_after = [r for r in sim.bridge.requests if r['cmd'] == 'press' and r['buttons'] == 'Y']
        check(len(presses_after) == 1, 'the swing was sent once, to the new process')


def main_wiring_checks():
    # hsap.py's command line reaches the Game and the Executor (hs-run.sh replaced by a script that exits at once)
    with tempfile.TemporaryDirectory(prefix='hsap-main-') as d:
        root = Path(d)
        script = root / 'hs-run.sh'
        script.write_text('#!/bin/sh\nexit 0\n')
        script.chmod(0o755)
        seen = []

        def record(self):
            seen.append({'opponent': self.opponent_path, 'wait': self.g.reconnect_wait, 'analog': self.analog,
                         'cmd': list(self.g.cmd)})
        for name, extra in (('options', ['--opponent', str(root / 'o.json'), '--analog', '--shots', '12', '--reconnect-wait', '7',
                                         '--env', 'HOS_CONTROL_MEM=ro', '--env', 'HSAP_TEST_EXTRA=1']),
                            ('defaults', []), ('window', [])):
            argv = ['hsap.py', str(root / 'copy'), 'tag-' + name, '60', '--live', str(root / ('live-' + name))] + extra
            window = {'HSAP_WINDOW': '1'} if name == 'window' else {}
            with mock.patch.object(hsap, 'HS_RUN', str(script)), mock.patch.object(hsap.Executor, 'run', record), \
                    mock.patch.object(sys, 'argv', argv), mock.patch.dict(os.environ, window):
                if not window:
                    os.environ.pop('HSAP_WINDOW', None)
                hsap.main()
        a, b, c = seen
        check(a['opponent'] == str(root / 'o.json') and a['wait'] == 7.0 and a['analog'] is True and 'RX_VK_SHOT_EVERY=12' in a['cmd'],
              '--opponent, --reconnect-wait, --analog and --shots reach the executor, the game and its command')
        check(b['opponent'] is None and b['wait'] == 180.0 and 'RX_VK_SHOT_EVERY=600' in b['cmd'],
              'without them: no opponent, 180 s to wait for a restarted game\'s socket, a picture every 600 presents')
        check('HOS_CONTROL_MEM=ro' in a['cmd'] and 'HSAP_TEST_EXTRA=1' in a['cmd'] and a['cmd'].index('HOS_CONTROL_MEM=ro') > a['cmd'].index('RX_VK_SHOT_EVERY=12'),
              '--env NAME=VALUE (repeatable) goes to hs-run.sh after the control switches')
        check(not any(x.startswith(('HOS_CONTROL_MEM', 'HSAP_TEST_EXTRA')) for x in b['cmd']), 'and without --env nothing of the kind is passed')
        for bad in ('HOS_CONTROL_MEM', 'hos_x=1', 'A B=1', '=1', 'X=a b'):
            argv = ['hsap.py', str(root / 'copy'), 'tag-bad', '60', '--live', str(root / 'live-bad'), '--env', bad]
            err = io.StringIO()
            with mock.patch.object(hsap, 'HS_RUN', str(script)), mock.patch.object(hsap.Executor, 'run', record), \
                    mock.patch.object(sys, 'argv', argv), contextlib.redirect_stderr(err):
                try:
                    hsap.main()
                    refused = False
                except SystemExit as e:
                    refused = e.code == 2
            check(refused and '--env' in err.getvalue(), f'--env {bad!r} is refused by the command line (exit 2) before anything starts')
        check('--window' in c['cmd'] and '--window' not in a['cmd'] + b['cmd'],
              'HSAP_WINDOW=1 adds --window to the hs-run.sh command; without it the command has none')
        # --hud on|off and HSAP_HUD=0: the panel sender and the game's picture switch
        seen.clear()

        def record_hud(self):
            seen.append({'hud': self.hud is not None, 'game_hud': 'RX_VK_SHOT_MENU=1' in self.g.cmd, 'ge': self.g.hud is self.hud})
        for name, extra, env in (('hud-default', [], {}), ('hud-on', ['--hud', 'on'], {}), ('hud-off', ['--hud', 'off'], {}),
                                 ('hud-env', [], {'HSAP_HUD': '0'}), ('hud-on-env', ['--hud', 'on'], {'HSAP_HUD': '0'})):
            argv = ['hsap.py', str(root / 'copy'), 'tag-' + name, '60', '--live', str(root / ('live-' + name))] + extra
            with mock.patch.object(hsap, 'HS_RUN', str(script)), mock.patch.object(hsap.Executor, 'run', record_hud), \
                    mock.patch.object(sys, 'argv', argv), mock.patch.dict(os.environ, env):
                if 'HSAP_HUD' not in env:
                    os.environ.pop('HSAP_HUD', None)
                hsap.main()
        check([s['hud'] for s in seen] == [True, True, False, False, False] and [s['game_hud'] for s in seen] == [True, True, False, False, False],
              'the panel is on by default and with --hud on, off with --hud off or HSAP_HUD=0 (also over --hud on); RX_VK_SHOT_MENU=1 goes '
              'to the game only when it is on')


REAL_POPEN, REAL_KILL, REAL_SLEEP, REAL_MONOTONIC = subprocess.Popen, os.kill, time.sleep, time.monotonic   # (the simulations replace them)


class ExternalSimulation(DuelSimulation):
    """hsap's external mode: the game is somebody else's. The fake bridge listens on a socket the test chose, the live file
    and the log are the game's own (outside hsap's live folder), Popen, os.kill and os.killpg are traps (an external game is
    never started, signalled or killed), game_pids must not be asked, and the pid is real: the test process itself unless a
    test passes another."""
    def __init__(self, wall=600.0, pid=None, reconnect_wait=0.0, old_live='', old_log=(), **options):
        super().__init__(**options)
        self.wall, self.pid, self.reconnect_wait = wall, pid or os.getpid(), reconnect_wait
        self.old_live, self.old_log = old_live, list(old_log)
        self.kills, self.spawned = [], []

    def __enter__(self):
        self.stack = contextlib.ExitStack()
        root = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix='hsap-ext-')))
        self.live, self.copy = root / 'live', root / 'copy'
        game_dir = root / 'game'
        game_dir.mkdir()
        self.sock, self.live_file = game_dir / 'control.sock', game_dir / 'live.txt'
        self.live_file.write_text(self.old_live)
        self.clock = Clock()
        for name, value in [('time', self.clock.time), ('monotonic', self.clock.time), ('sleep', self.clock.sleep)]:
            self.stack.enter_context(mock.patch.object(hsap.time, name, value))

        def no_popen(*args, **kwargs):
            self.spawned.append(args)
            raise AssertionError('hsap must not start a process for an external game')
        self.stack.enter_context(mock.patch.object(hsap.subprocess, 'Popen', no_popen))
        self.stack.enter_context(mock.patch.object(hsap.os, 'kill', lambda pid, sig: self.kills.append((pid, sig))))
        self.stack.enter_context(mock.patch.object(hsap.os, 'killpg', lambda pid, sig: self.kills.append((-pid, sig))))
        self.bridge = DuelBridge(self.sock, self.live_file, game_dir / 'run', self.clock, **self.options)
        self.bridge.debug.off = len(self.old_live.encode())   # (the game has read what was in its live file already)
        self.clock.bridge = self.bridge
        self.log = game_dir / 'run' / 'hookshot_log.txt'
        for line in self.old_log:
            self.bridge.log(line)
        self.game = hsap.Game(self.copy, 'ext', self.wall, self.live, reconnect_wait=self.reconnect_wait,
                              external=hsap.ExternalGame(self.sock, self.live_file, self.log, self.pid), **({'hud': True} if self.hud_game else {}))
        self.stack.enter_context(mock.patch.object(self.game, 'game_pids',
                                                   side_effect=AssertionError('an external game has no game_pids')))
        return self

    def __exit__(self, *exc):
        try:
            for ex in self.executors:
                ex.out.close()
            self.game.stop()
            self.bridge.pump()
            if exc[0] is None:
                assert not self.bridge.inputs and not self.bridge.waiting, 'disconnect releases pending inputs'
                assert not self.kills and not self.spawned, f'an external game is never signalled or started: {self.kills}'
        finally:
            self.bridge.close()
            self.stack.close()


def wait_gone(pid, limit=5.0):
    """Real time: until the process is a zombie or gone (a SIGKILL takes a moment to land)."""
    end = REAL_MONOTONIC() + limit
    while REAL_MONOTONIC() < end:
        try:
            state = Path(f'/proc/{pid}/stat').read_bytes().rsplit(b')', 1)[-1].split()[0]
        except OSError:
            return True
        if state in (b'Z', b'X'):
            return True
        REAL_SLEEP(0.005)
    return False


def external_wiring_checks():
    # the four flags reach the Game as an ExternalGame, no process is started, nothing is signalled, the game's live file is untouched
    with tempfile.TemporaryDirectory(prefix='hsap-extmain-') as d:
        root = Path(d)
        sock, live_file, log = root / 'game.sock', root / 'game-live.txt', root / 'game.log'
        live_file.write_text('!an old line\n')
        log.write_text('earlier\n')
        spawned, kills, seen = [], [], []

        def record(self):
            g = self.g
            seen.append({'external': g.external, 'cmd': list(g.cmd), 'boot': self.boot, 'opponent': self.opponent_path,
                         'analog': self.analog, 'wait': g.reconnect_wait, 'sock': g.control_path, 'live': g.live_in,
                         'tail': g.log_tail.path, 'runner': type(g.runner).__name__, 'pid': g.runner.pid, 'alive': g.alive(),
                         'control_dir': g.control_dir, 'left': g.deadline - REAL_MONOTONIC()})

        def no_popen(*args, **kwargs):
            spawned.append(args)
            raise AssertionError('no process for an external game')
        flags = ['--game-sock', str(sock), '--game-live', str(live_file), '--game-log', str(log), '--game-pid', str(os.getpid())]

        def argv(wall='90', extra=(), live='live'):
            return ['hsap.py', str(root / 'copy'), 'ext', wall, '--live', str(root / live)] + list(extra)

        def run_main(args):
            with mock.patch.object(hsap.time, 'sleep', lambda s: None), mock.patch.object(hsap.subprocess, 'Popen', no_popen), \
                    mock.patch.object(hsap.os, 'kill', lambda *a: kills.append(a)), \
                    mock.patch.object(hsap.os, 'killpg', lambda *a: kills.append(a)), \
                    mock.patch.object(hsap.Executor, 'run', record), mock.patch.object(sys, 'argv', args):
                return hsap.main()
        check(run_main(argv(extra=flags + ['--opponent', str(root / 'o.json'), '--analog'])) == 0, 'hsap with an external game ends exit 0')
        s = seen[0]
        check(s['external'] is not None and s['cmd'][0] == 'external-game' and s['sock'] == sock and s['live'] == live_file and
              s['tail'] == log and s['runner'] == 'PidRunner' and s['pid'] == os.getpid() and s['alive'] is True and
              s['control_dir'] is None, 'the four flags reach the Game: its socket, live file, log and pid; no private control folder')
        check(s['boot'] == 'none' and s['opponent'] == str(root / 'o.json') and s['analog'] is True and s['wait'] == 180.0,
              '--boot defaults to none for an external game; --opponent, --analog and the 180 s reconnect wait are as for any game')
        check(88 < s['left'] <= 90, f"the wall time bounds hsap's own life ({s['left']:.1f} s left)")
        check(not spawned and not kills, 'no hs-run.sh start (nothing spawned), nothing signalled when hsap ends')
        check(live_file.read_text() == '!an old line\n' and log.read_text() == 'earlier\n',
              "the game's live file and log are untouched by hsap's start and end")
        check(not (root / 'live' / 'hs-run.out').exists() and not (root / 'live' / 'live.txt').exists(),
              'no hs-run.out and no live.txt of its own in hsap\'s folder')
        notes = [json.loads(x)['text'] for x in (root / 'live' / 'out.jsonl').read_text().splitlines() if json.loads(x)['ev'] == 'note']
        check(notes[0].startswith('external game') and notes[-1] == f'hsap ended; the game (pid {os.getpid()}) was left running',
              f'the events say it was an external game and that it was left running: {notes}')

        def usage(args):
            err = io.StringIO()
            try:
                with contextlib.redirect_stderr(err):
                    run_main(args)
            except SystemExit as e:
                return e.code, err.getvalue()
            return None, ''
        for name, args in (('only the socket', argv(extra=flags[:2])), ('no pid', argv(extra=flags[:6])),
                           ('no log', argv(extra=flags[:4] + flags[6:])), ('--save', argv(extra=flags + ['--save', str(root)])),
                           ('--shots', argv(extra=flags + ['--shots', '5'])), ('a wall of 0', argv('0', flags)),
                           ('pid 0', argv(extra=flags[:6] + ['--game-pid', '0'])), ('pid -4', argv(extra=flags[:6] + ['--game-pid', '-4']))):
            code, text = usage(args)
            check(code == 2 and text, f'{name}: refused with a usage error ({text.strip().splitlines()[-1][-90:]})')
        check(len(seen) == 1 and not spawned and not kills, 'and none of them started anything')


def external_run_checks():
    old_live = '!an old line the game has read\n'
    chatter = 'coop: puppet: member 2 is shown as CoopPuppet_Adult'
    with ExternalSimulation(boot_events=0, follow=False, script={'!duel ready': [CANNED['count']]}, old_live=old_live,
                            old_log=[CANNED['terms'], chatter]) as sim:
        g, bridge = sim.game, sim.bridge
        sim.exchange()
        check(g.sock is not None and g.duel.snapshot(0.0)['state'] == 'Read terms' and chatter in g.log_lines,
              'hsap connects to the socket the test serves and reads the game\'s log from its start (the duel history is the ledger)')
        ex = sim.executor(['duel ready', 'swing', 'end'], opponent=False)
        ex.run()
        steps = sim.steps()
        check([s['result'] for s in steps] == ['done', 'done'] and steps[0]['detail'] == 'duel Countdown round 1 hearts 40/40',
              f"`duel ready` ends done with what the game's log then says: {steps[0]['detail']}")
        check(sim.live_file.read_text() == old_live + '!duel ready\n' and bridge.debug_lines == ['!duel ready'],
              "the `duel ready` line is appended to the game's own live file, what was there stays")
        subs = [r for r in bridge.requests if r['cmd'] == 'subscribe']
        check(len(subs) == 1 and subs[0]['events'] == ['oot'] and subs[0]['every'] == 6 and subs[0]['changes'] is True,
              'it subscribed to the game\'s oot samples as an ordinary client')
        check([(r['buttons'], r['frames']) for r in bridge.requests if r['cmd'] == 'press'] == [('Y', 7)],
              'a swing is a press through the bridge, as for any game')
        check(not (sim.live / 'hs-run.out').exists() and not (sim.live / 'live.txt').exists() and sim.game.control_dir is None,
              'it wrote no hs-run.out, no live.txt and made no private control folder')
        ev = sim.events()
        check(ev[-1]['ev'] == 'done' and not [e for e in ev if e['ev'] == 'bad'] and
              [e['ev'] for e in ev].count('gameplay') == 1, '`end` ends the run with done')
        check(not sim.kills and not sim.spawned and g.runner.poll() is None,
              'nothing was started or signalled, and the game process is still there when hsap is done')

    # alive follows the pid
    child = REAL_POPEN(['sleep', '300'])
    try:
        with ExternalSimulation(boot_events=0, pid=child.pid) as sim:
            g = sim.game
            sim.exchange()
            check(g.alive() and g.end_reason() == 'the game ended', 'alive while its pid exists')
            REAL_KILL(child.pid, signal.SIGKILL)
            check(wait_gone(child.pid), 'the test killed the game')
            check(not g.alive(), 'a zombie (killed, its parent has not reaped it) is gone')
            child.wait()
            check(not g.alive() and g.runner.wait(1) == 0, 'and a reaped process is gone')
    finally:
        child.kill()
        child.wait()
    with ExternalSimulation(boot_events=0, pid=child.pid, wall=600.0) as sim:   # the pid is not a process any more
        check(not sim.game.alive(), 'a pid nobody has is not alive')

    # the game exits during a step: hsap ends itself, exit 0 (no error), the game's end is not ours to handle
    child = REAL_POPEN(['sleep', '300'])
    try:
        with ExternalSimulation(boot_events=0, pid=child.pid, reconnect_wait=30.0) as sim:
            ex = sim.executor(['wait 60', 'swing', 'end'], opponent=False)
            phase = {}

            def die(b):
                if 'at' not in phase and b.frame >= 600 and sim.game.st is not None:
                    REAL_KILL(child.pid, signal.SIGKILL)
                    wait_gone(child.pid)
                    phase['at'] = sim.clock.time()
            sim.bridge.on_tick = die
            ex.run()
            ev = sim.events()
            check(ev[-1]['ev'] == 'done' and ev[-2]['ev'] == 'note' and ev[-2]['text'] == 'the game ended', f"the game's exit ends the run: {ev[-2]}")
            check([e['src'] for e in ev if e['ev'] == 'step'] == ['wait 60'] and not sim.bridge.debug_lines and
                  not [r for r in sim.bridge.requests if r['cmd'] == 'press'],
                  'the wait in flight ended with the game, and the swing after it was never tried')
            check(sim.clock.time() - phase['at'] < 1.0, 'it ended at once, not at its wall time')
    finally:
        child.kill()
        child.wait()

    # `end` and the wall time end hsap and nothing else
    with ExternalSimulation(boot_events=0) as sim:
        sim.executor(['end'], opponent=False).run()
        check(sim.events()[-1]['ev'] == 'done' and not [r for r in sim.bridge.requests if r['cmd'] in ('press', 'stick', 'sequence')] and
              not sim.bridge.debug_lines, '`end` is a step like the others: done, no input, no debug line')
    with ExternalSimulation(boot_events=0, wall=12.0) as sim:
        start = sim.clock.time()
        sim.executor(['wait 600', 'swing'], opponent=False).run()
        ev = sim.events()
        used = sim.clock.time() - start
        check(11.9 < used < 13.0 and ev[-1]['ev'] == 'done', f'the wall time ends hsap ({used:.1f} s of 12) and writes done')
        check(ev[-2]['ev'] == 'note' and ev[-2]['text'] == 'hsap wall time (12 s) is over; the game was not touched',
              f"with the reason: {ev[-2].get('text')}")
        check([e['src'] for e in ev if e['ev'] == 'step'] == ['wait 600'] and
              not [r for r in sim.bridge.requests if r['cmd'] in ('press', 'stick', 'sequence')],
              'the wait in flight ended at the wall time, and the swing after it sent nothing')
        check(sim.game.runner.poll() is None and not sim.kills, 'the game process is alive and unsignalled')
    with ExternalSimulation(boot_events=0, wall=3.0) as sim:   # no sample ever: the wall time ends the wait for control
        sim.bridge.updates = False
        sim.executor(['swing'], opponent=False).run()
        notes = [e['text'] for e in sim.events() if e['ev'] == 'note']
        check(notes and notes[-1] == 'no control: hsap wall time (3 s) is over; the game was not touched',
              f'a wall time that runs out before there is control says so: {notes}')

    # a game that restarts itself (its control socket replaced) is survived, with nothing pressed at its title
    with ExternalSimulation(boot_events=8, reconnect_wait=60.0, follow=False) as sim:
        ex = sim.executor(['walk 0 200 radius 0.5 timeout 120', 'swing', 'end'], boot='none', opponent=False)
        phase, mark = {'n': 0}, {}

        def restart(b):
            if phase['n'] == 0 and b.frame >= 900 and sim.game.st is not None:
                b.drop()
                phase.update(n=1, at=sim.clock.time())
            elif phase['n'] == 1 and sim.clock.time() >= phase['at'] + 3.0:
                b.revive()
                b.boot_events = 8
                b.log('vk: 0 presents, 60 fps; a frame: 15 draws')
                phase['n'] = 2
        sim.bridge.on_tick = restart
        ex.run()
        ev, steps = sim.events(), sim.steps()
        subs = [r for r in sim.bridge.requests if r['cmd'] == 'subscribe']
        check(sim.game.restarts == 1 and len(subs) == 2 and steps[0]['result'] == 'cut' and 'restarted itself' in steps[0]['detail'],
              f"the replaced socket is reconnected to and subscribed again; the walk in flight is cut ({steps[0]['detail']})")
        check(steps[1]['src'] == 'swing' and steps[1]['result'] == 'done' and ev[-1]['ev'] == 'done' and
              [e['ev'] for e in ev].count('gameplay') == 2, 'control is found again and the steps after the restart run on the new process')
        check(sim.bridge.a_presses == 0, '--boot none: no title press, before or after the restart')
        check(sim.game.alive() and not sim.kills, 'the same pid lives on, unsignalled')

    # the game's log: not there yet, appended to, truncated, replaced
    with ExternalSimulation(boot_events=0, follow=False) as sim:
        g = sim.game
        os.unlink(sim.log)
        sim.exchange()
        check(g.duel.snapshot(0.0) is None and g.log_lines == [], 'a log that is not there yet reads nothing')
        sim.log.write_text(CANNED['terms'] + '\n' + CANNED['count'] + '\n')
        sim.exchange()
        check(g.duel.snapshot(0.0)['state'] == 'Countdown' and len(g.log_lines) == 2, 'it appears and is read from its start')
        with open(sim.log, 'a') as f:
            f.write(CANNED['duel'] + '\n' + CANNED['hit'] + '\n')
        sim.exchange()
        d = g.duel.snapshot(0.0)
        check(d['state'] == 'Duel' and d['swings'] == {'hit': 1} and len(g.log_lines) == 4, 'appended lines are read once')
        sim.log.write_text(CANNED['round'] + '\n')   # truncated and written again (shorter)
        sim.exchange()
        d = g.duel.snapshot(0.0)
        check(d['state'] == 'Round ended' and len(g.log_lines) == 5 and d['swings'] == {'hit': 1},
              'a truncated log is read from its start (the game started it again)')
        tmp = sim.log.with_name('hookshot_log.tmp')
        tmp.write_text(CANNED['terms'] + '\n' + CANNED['finish'] + '\n' + CANNED['round'] + '\n' + CANNED['match'] + '\n')
        os.replace(tmp, sim.log)   # a new file under the old name, longer than the old read offset
        sim.exchange()
        d = g.duel.snapshot(0.0)
        check(d['state'] == 'Match ended' and d['matches_ended'] == 1 and len(g.log_lines) == 9,
              'a replaced log is read from its start')

    try:
        hsap.ExternalGame('/x/sock', '/x/live', '/x/log', 0)
    except ValueError:
        check(True, 'a pid of 0 is refused')
    else:
        check(False, 'a pid of 0 must be refused')


def external_checks():
    external_wiring_checks()
    external_run_checks()


def duel_checks():
    duel_parse_checks()
    duel_step_checks()
    duel_geometry_checks()
    restart_checks()
    main_wiring_checks()


# ---- interactions: A at a prompt, text, pickups, doors, the camera, the ocarina, items (invented scene)

class WorldBridge(DuelBridge):
    """DuelBridge plus an invented scene. `things` are dicts {x, z, r, prompt, text, scene, rupees, flag, to, touch, once}:
    A at its prompt (or walking within r when it `touch`es) runs its effect: `text` more A presses close the text it opens,
    `scene` frames of a cutscene (event 1, a Dm_ music), rupees, a flag (a hash text, reported by the change scan), a map
    change. The D-pad's Left takes the ocarina out (the log says the note wait is on; B puts it away), the note buttons
    are kept in `notes`; the right stick turns the camera 2 degrees a frame; ZL turns Link `lock_turn` degrees; ZR counts."""
    def __init__(self, *args, things=(), ocarina=True, lock_turn=0.0, zr_effect=True, oc_event=False, song=(), song_gap=30, song_busy=360,
                 oc_busy=0, warm=0, **kwargs):
        self.oc_event = oc_event   # the real game holds Link (event 1) while the ocarina waits for a note
        self.things = [dict(t) for t in things]
        self.map_name, self.rupees, self.life, self.music = 'Test_Map', 0, 12, 'BGM_Test'
        self.text_left, self.scene_left, self.set_flags = 0, 0, {}
        self.notes, self.zr, self.a_log, self.oc_on, self.ocarina = [], 0, [], False, ocarina
        self.lock_turn, self.zr_effect, self.pressed_log = lock_turn, zr_effect, []
        self.note_log, self.held_s = [], 0.0
        self.song, self.song_gap, self.song_busy, self.busy_left = list(song), song_gap, song_busy, oc_busy
        self.song_at, self.songs_taken, self.lost = 0, 0, []
        self.warm, self.oc_open, self.dropped, self.fresh_first = warm, 0, [], False   # (the first note in the first `warm` frames of a window is ignored: the game does this)
        super().__init__(*args, **kwargs)

    def near_thing(self):
        for t in self.things:
            if not t.get('used') and 'prompt' in t and math.hypot(self.pos[0] - t['x'], self.pos[2] - t['z']) <= t['r']:
                return t
        return None

    def game_state(self, frame=None):
        s = super().game_state(frame)
        thing = self.near_thing()
        busy = self.text_left > 0 or self.scene_left > 0 or (self.oc_event and self.oc_on) or self.busy_left > 0
        s.update(map=self.map_name, rupees=self.rupees, life=self.life,
                 prompt=thing['prompt'] if thing and not busy else 'Empty',
                 music='Dm_Test_Scene' if self.scene_left > 0 else self.music)
        s['event'] = bool(s['event']) or busy
        return s

    def extra_values(self):
        return {'0x00000002': self.frame // 6, **self.set_flags}   # (a counter that moves in every sample: the play clock)

    def effect(self, t):
        t['used'] = t.get('once', True)
        self.text_left = t.get('text', 0)
        self.scene_left = t.get('scene', 0)
        self.rupees += t.get('rupees', 0)
        if 'flag' in t:
            self.set_flags[t['flag']] = 1
        if 'to' in t:
            self.map_name = t['to']

    def pressed(self, b):
        self.pressed_log.append((self.frame + 1, b))
        if self.busy_left > 0:   # (the song plays back: Link is held, a button is lost)
            self.lost.append((self.frame + 1, b))
            return
        if self.oc_on:
            if b == 'B':
                self.oc_on = False
                self.log("[hos X] oc: the note wait turned off (the action's kind 1)")
            elif b in ('L', 'R', 'A', 'Y', 'X'):
                if self.fresh_first and self.frame + 1 - self.oc_open < self.warm:   # (the first note of a window opened a moment ago is not recorded)
                    self.dropped.append(b)
                    self.fresh_first = False
                    return
                self.fresh_first = False
                self.notes.append(b)
                self.note_log.append((b, self.frame + 1, round(self.held_s, 3)))
                n = len(self.song)
                if n and self.notes[-n:] == self.song:   # (taken when the last n notes are the song and each started within song_gap frames of the one before)
                    starts = [f for _, f, _ in self.note_log[-n:]]
                    if all(y - x <= self.song_gap for x, y in zip(starts, starts[1:])):
                        self.song_at = self.frame + 1 + 12
            return
        if b == 'A':
            self.a_log.append(self.frame + 1)
            if self.scene_left > 0:
                return
            if self.text_left > 0:
                self.text_left -= 1
            elif self.near_thing():
                self.effect(self.near_thing())
        elif b == 'LEFT' and self.ocarina:
            self.oc_on, self.oc_open, self.fresh_first = True, self.frame + 1, True
            self.log("[hos X] oc: the note wait turned on (buttons) (the action's kind 1)")
        elif b == 'ZR':
            self.zr += 1
            if self.zr_effect:
                self.flags['Item.Count'] = 10 - self.zr
        elif b == 'ZL':
            self.face = hsap.wrap(self.face + self.lock_turn)

    def tick(self):
        nxt = self.frame + 1
        if self.song_at and nxt >= self.song_at:   # (the game takes the song by itself: it closes the note wait and plays it back)
            self.song_at, self.oc_on, self.busy_left = 0, False, self.song_busy
            self.log("[hos X] oc: the note wait turned off (the action's kind 1)")
            self.songs_taken += 1
        if self.busy_left > 0:
            self.busy_left -= 1
        for s in list(self.inputs):
            if s['start'] == nxt:
                self.held_s = (s['end'] - s['start']) / 60.0
                for b in s['buttons']:
                    self.pressed(b)
                    if b == 'A':   # a thing under water: taken by an A held long enough (the dive) while Link is over it
                        for t in self.things:
                            if t.get('dive') and not t.get('used') and self.held_s >= t['dive'] and \
                                    math.hypot(self.pos[0] - t['x'], self.pos[2] - t['z']) <= t['r']:
                                self.effect(t)
            if s['start'] <= nxt < s['end'] and s['axes'].get('rx'):
                self.cam = hsap.wrap(self.cam + 2.0 * s['axes']['rx'])
        for t in self.things:
            if t.get('touch') and not t.get('used') and math.hypot(self.pos[0] - t['x'], self.pos[2] - t['z']) <= t['r']:
                self.effect(t)
        if self.scene_left > 0:
            self.scene_left -= 1
        super().tick()


class WorldSimulation(DuelSimulation):
    def launch(self, cmd, **kwargs):
        args = dict(arg.split('=', 1) for arg in cmd[4:] if '=' in arg)
        self.bridge = WorldBridge(Path(args['HOS_CONTROL']), Path(args['HOS_INPUT_LIVE']), self.copy / 'runs/test',
                                  self.clock, **self.options)
        self.clock.bridge = self.bridge
        return FakeRunner()

    def steps(self):
        return [e for e in self.events() if e['ev'] == 'step' and e['src'] not in ('end', 'wait 2')]


CHEST = {'x': 0.0, 'z': 0.5, 'r': 1.0, 'prompt': 'Open', 'text': 2, 'rupees': 20, 'flag': '0x0000beef'}


def interact_step_checks():
    # a chest: A at its prompt, the text advanced until Link is free, and what changed
    with WorldSimulation(boot_events=0, follow=False, things=[CHEST]) as sim:
        sim.executor(['wait 2', 'chest', 'chest', 'chest force', 'end']).run()
        a, b, c = sim.steps()
        check(a['result'] == 'opened', f"chest at an Open prompt ends opened ({a['result']}: {a['detail']})")
        ch = a['changes']
        check(ch['rupees'] == [0, 20] and ch['prompt'] == ['Open', 'Empty'] and ch['text'] == 'closed',
              'it names the rupees, the prompt and the text (opened, then closed)')
        check('0x0000beef' in ch['hashes'] and '0x00000002' not in ch['hashes'],
              'the changed flag hash is listed and the play clock counter (it rose in every sample) is left out')
        check('rupees 0 -> 20' in a['detail'] and 'text closed' in a['detail'], 'the detail says it in words')
        first = sim.bridge.a_log[:3]
        check(len(sim.bridge.a_log) == 4 and all(f2 - f1 >= 48 for f1, f2 in zip(first, first[1:])),
              'A once to open it, then one every 1.2 s of the text (3 presses, each at least 0.8 s after the one before)')
        check(b['result'] == 'no-prompt' and 'Empty' in b['detail'] and 'changes' not in b,
              'a second chest step with the prompt gone sends nothing and ends no-prompt')
        check(c['result'] == 'none' and len(sim.bridge.a_log) == 4,
              'force presses A anyway; with nothing changing the step ends none')
        check(sim.bridge.rupees == 20, 'the rupees were taken once')

    # a chest whose text closes while the step's time runs out (hold A2: the deadline fell inside the 0.6 s Link must be free before the text counts
    # as closed, the step said `timeout` with `text closed` and the chest flag set): whenever the text is closed when the step ends, the result is opened
    swept, late = 0, 0
    for tenths in range(20, 36):
        with WorldSimulation(boot_events=0, follow=False, things=[{**CHEST, 'text': 2}]) as sim:
            sim.executor([f'chest timeout {tenths / 10:g}', 'end']).run()
            a = sim.steps()[0]
            swept += 1
            if sim.bridge.text_left == 0 and not sim.game.st.get('event'):
                late += a['result'] != 'opened'
    check(swept == 16 and late == 0, f'a chest whose text closed by the time the step ended is never `timeout` ({late} of {swept} timeouts 2.0 to 3.5 s ended so)')

    # a person: talked when the text opened and closed; open when it never closes in time
    people = [{'x': 0.0, 'z': 0.4, 'r': 1.0, 'prompt': 'Talk', 'text': 3}]
    with WorldSimulation(boot_events=0, follow=False, things=people) as sim:
        sim.executor(['talk', 'end']).run()
        s = sim.steps()[0]
        check(s['result'] == 'talked' and s['changes']['text'] == 'closed' and 'rupees' not in s['changes'],
              f"talk ends talked once the text closed ({s['detail']})")
        check(len(sim.bridge.a_log) == 4, 'one A to start and three to close the text')
    with WorldSimulation(boot_events=0, follow=False, things=[{**people[0], 'text': 99}]) as sim:
        sim.executor(['talk timeout 5', 'advance timeout 3', 'end']).run()
        a, b = sim.steps()
        check(a['result'] == 'open' and a['changes']['text'] == 'open', f"a text still open at the timeout ends open ({a['detail']})")
        check(b['result'] == 'timeout' and 5.0 < a['secs'] < 7.0, 'advance with a text that never closes ends timeout')
        check(sim.game.st['event'] == 1 and sim.bridge.text_left > 0, 'the text is still open')

    # advance: nothing open: nothing sent; open: A until closed
    with WorldSimulation(boot_events=0, follow=False, things=[{**people[0], 'text': 2}]) as sim:
        sim.executor(['advance', 'press A', 'report 0.2', 'wait 0.5', 'report 0', 'advance', 'end']).run()
        a, p, c = [s for s in sim.steps() if s['src'].split()[0] in ('advance', 'press')]
        check(a['result'] == 'none' and p['result'] == 'done', 'advance with no text open ends none')
        check(c['result'] == 'closed' and c['changes']['text'] == 'closed' and len(sim.bridge.a_log) == 3,
              'advance with the text open presses A until it closed')
        states = [e for e in sim.events() if e['ev'] == 'state']
        reports = [e for e in states if e['why'] == 'report']
        check(reports and all(e.get('text') is True for e in reports) and 'text' not in states[0] and 'text' not in states[-1],
              'the state line carries text: true while a text box holds Link, and nothing otherwise')

    # a scene (a cutscene music): no A is pressed inside it
    with WorldSimulation(boot_events=0, follow=False, things=[{**people[0], 'scene': 150, 'text': 0}]) as sim:
        sim.executor(['talk', 'end']).run()
        s = sim.steps()[0]
        check(s['result'] == 'talked' and s['changes'].get('scene') is True and len(sim.bridge.a_log) == 1,
              f"a scene is waited out without A (one press in all): {s['result']}, {s['detail']}")

    # interact: A at any prompt; done when something changed
    with WorldSimulation(boot_events=0, follow=False, things=[{**people[0], 'prompt': 'Check', 'text': 1}]) as sim:
        sim.executor(['interact', 'interact', 'end']).run()
        a, b = sim.steps()
        check(a['result'] == 'done' and b['result'] == 'no-prompt', 'interact: done after a change, no-prompt without one')


def interact_move_checks():
    rupee = {'x': 0.0, 'z': 3.0, 'r': 0.5, 'touch': True, 'rupees': 5}
    with WorldSimulation(boot_events=0, follow=False, things=[rupee]) as sim:
        sim.executor(['pickup 0 3 radius 0.3 timeout 10', 'pickup 0 8 timeout 10', 'end']).run()
        a, b = sim.steps()
        check(a['result'] == 'picked' and a['changes']['rupees'] == [0, 5] and 'rupees 0 -> 5' in a['detail'],
              f"pickup walks onto the rupee and reports the count ({a['result']}: {a['detail']})")
        check(b['result'] == 'none', f"pickup at an empty place ends none ({b['result']}: {b['detail']})")
    # a walk that ended short of the spot is no pickup when only the change scan's hashes moved (a camera cut, a prompt on the way)
    passing = {'x': 0.0, 'z': 1.0, 'r': 0.8, 'touch': True, 'flag': '0x0000f00d'}
    with WorldSimulation(boot_events=0, follow=False, things=[passing], walls=[(-3, 2.0, 3, 2.6)]) as sim:
        sim.executor(['pickup 0 8 timeout 8', 'end']).run()
        a = sim.steps()[0]
        check(a['result'] != 'picked' and sim.bridge.rupees == 0 and sim.bridge.pos[2] < 2.2,
              f"a pickup whose walk was stopped short, with only a hash changed, is not a pickup ({a['result']}: {a['detail']})")
    # a rupee on a pond's floor (pi-solo-2b: Link swam over it at 0.17 m and nothing changed; the HUD said `Dive (Hold)` on A): only with `dive <s>`
    pond = {'x': 0.0, 'z': 3.0, 'r': 0.5, 'dive': 2.0, 'rupees': 5}
    with WorldSimulation(boot_events=0, follow=False, things=[pond]) as sim:
        sim.executor(['pickup 0 3 radius 0.3 timeout 10', 'pickup 0 3 radius 0.3 timeout 10 dive 2.5', 'end']).run()
        a, b = sim.steps()
        holds = [(r['buttons'], r['frames']) for r in sim.bridge.requests if r['cmd'] == 'press' and r['buttons'] == 'A']
        check(a['result'] == 'none' and holds == [('A', 150)] and b['result'] == 'picked' and b['changes']['rupees'] == [0, 5],
              f"pickup without dive leaves a rupee under water; with `dive 2.5` it holds A 2.5 s there and takes it ({a['result']}, {b['result']}: {b['detail']}; holds {holds})")
    with WorldSimulation(boot_events=0, follow=False, things=[{**pond, 'z': 8.0}], walls=[(-3, 2.0, 3, 2.6)]) as sim:
        sim.executor(['pickup 0 8 timeout 6 dive 2', 'end']).run()
        a = sim.steps()[0]
        check(not [r for r in sim.bridge.requests if r['cmd'] == 'press' and r['buttons'] == 'A'],
              f"dive is only tried where the walk reached the spot: no A was held after a walk that ended short ({a['result']}: {a['detail']})")
    on_spot = {'x': 0.0, 'z': 3.0, 'r': 0.5, 'touch': True, 'flag': '0x0000f00e'}
    with WorldSimulation(boot_events=0, follow=False, things=[on_spot]) as sim:
        sim.executor(['pickup 0 3 radius 0.3 timeout 10', 'end']).run()
        a = sim.steps()[0]
        check(a['result'] == 'picked' and '0x0000f00e' in a['changes']['hashes'],
              f"but a walk that reached the spot and changed a flag is one ({a['result']}: {a['detail']})")
    first = {'x': 0.0, 'z': 3.0, 'r': 0.5, 'touch': True, 'rupees': 20, 'text': 1}
    with WorldSimulation(boot_events=0, follow=False, things=[first]) as sim:
        sim.executor(['pickup 0 3 timeout 10', 'end']).run()
        a = sim.steps()[0]
        check(a['result'] == 'picked' and a['changes']['text'] == 'closed' and sim.game.st['event'] == 0,
              f"a first-time pickup's text is advanced to its end ({a['result']}: {a['detail']})")
    with WorldSimulation(boot_events=0, follow=False, things=[{'x': 0.0, 'z': 3.0, 'r': 1.0, 'prompt': 'Have', 'text': 1, 'rupees': 1}]) as sim:
        sim.executor(['pickup 0 3 radius 0.3 timeout 10 press', 'end']).run()
        a = sim.steps()[0]
        check(a['result'] == 'picked' and sim.bridge.rupees == 1 and len(sim.bridge.a_log) == 2,
              f"pickup with press takes what the A prompt offers at the spot ({a['result']})")

    # enter: a load zone by walking into it; a door by A at its prompt; a wall that stays shut
    zone = {'x': 0.0, 'z': 6.0, 'r': 0.8, 'touch': True, 'to': 'Other_Map'}
    with WorldSimulation(boot_events=0, follow=False, things=[zone]) as sim:
        sim.executor(['enter 0 6 timeout 15', 'end']).run()
        a = sim.steps()[0]
        check(a['result'] == 'entered' and a['changes']['map'] == ['Test_Map', 'Other_Map'] and 'Test_Map -> Other_Map' in a['detail'],
              f"enter through a load zone ends entered with both maps ({a['result']}: {a['detail']})")
    door = {'x': 0.0, 'z': 3.0, 'r': 1.2, 'prompt': 'Open', 'flag': '0x0000d00d', 'once': True}
    with WorldSimulation(boot_events=0, follow=False, things=[door]) as sim:
        sim.executor(['enter 0 3 through 0 7 timeout 20', 'end']).run()
        a = sim.steps()[0]
        check(a['result'] == 'opened' and len(sim.bridge.a_log) == 1 and '0x0000d00d' in a['changes']['hashes'],
              f"enter at a door presses A at its Open prompt: opened ({a['result']}: {a['detail']})")
        check(sim.bridge.pos[2] > 5.5, 'and goes on through it')
    # a door whose Open prompt shows only on its near side, a step away from the point the walk aims at (a door frame the walk cannot reach):
    # the walk stops where the prompt reads Open and A goes in then, not 2.5 s later at a place where the prompt is gone
    side_door = {'x': 0.0, 'z': 1.5, 'r': 0.6, 'prompt': 'Open', 'flag': '0x0000d00e', 'once': True}
    with WorldSimulation(boot_events=0, follow=False, things=[side_door], walls=[(-0.3, 2.6, 0.3, 3.4)]) as sim:
        sim.executor(['enter 0 3 through 2 7 timeout 25', 'end']).run()
        a = sim.steps()[0]
        check(a['result'] == 'opened' and len(sim.bridge.a_log) == 1 and '0x0000d00e' in a['changes']['hashes'] and sim.bridge.pos[2] > 5.5,
              f"enter stops its walk where the prompt reads Open and presses A there, then goes through ({a['result']}: {a['detail']})")
    with WorldSimulation(boot_events=0, follow=False, walls=[(-3, 2.0, 3, 2.6)]) as sim:
        sim.executor(['enter 0 6 timeout 10', 'end']).run()
        a = sim.steps()[0]
        check(a['result'] == 'blocked' and not sim.bridge.a_log, f"a wall with no prompt ends blocked ({a['result']}: {a['detail']})")


def interact_view_checks():
    with WorldSimulation(boot_events=0, follow=False, lock_turn=40.0) as sim:
        sim.executor(['ztarget 600', 'end']).run()
        a = sim.steps()[0]
        zl = [r for r in sim.bridge.requests if r['cmd'] == 'press']
        check(a['result'] == 'targeted' and [(r['buttons'], r['frames']) for r in zl] == [('ZL', 36)],
              f"ztarget holds ZL and reports Link turned ({a['result']}: {a['detail']})")
    with WorldSimulation(boot_events=0, follow=False) as sim:
        sim.executor(['ztarget', 'end']).run()
        a = sim.steps()[0]
        check(a['result'] == 'none' and sim.bridge.pressed_log[0][1] == 'ZL', 'ztarget with nothing to turn to ends none')

    with WorldSimulation(boot_events=0, follow=False, camera=10.0) as sim:
        sim.executor(['camera right 300', 'camera left 150', 'camera to 90', 'camera to 90', 'end']).run()
        a, b, c, d = sim.steps()
        check(a['result'] == 'turned' and abs(a['changes']['camera'][1] - a['changes']['camera'][0] - 36.0) < 1.5,
              f"camera right 300 ms turns the camera by the right stick ({a['detail']})")
        check(b['result'] == 'turned' and b['changes']['camera'][1] < b['changes']['camera'][0], 'camera left turns it back')
        check(c['result'] == 'turned' and abs(hsap.wrap(sim.bridge.cam - 90.0)) <= 8.0,
              f"camera to 90 turns it to within 8 degrees by closed loop ({sim.bridge.cam:.1f})")
        check(d['result'] == 'none' and 'already' in d['detail'], 'and when it already is, nothing is sent')

    # faceat: Link turned toward a point
    with WorldSimulation(boot_events=0, follow=False) as sim:
        sim.executor(['faceat 6 0', 'faceat 6 0', 'end']).run()
        a, b = sim.steps()
        check(a['result'] == 'done' and abs(hsap.wrap(sim.bridge.face - 90.0)) <= 20.0, f"faceat turns Link toward the point ({sim.bridge.face:.0f})")
        check(b['result'] == 'done' and 'facing' in b['detail'], 'and says so when he already does')


def interact_gear_checks():
    with WorldSimulation(boot_events=0, follow=False) as sim:
        sim.executor(['ocarina Y X L', 'end']).run()
        a = sim.steps()[0]
        wire = [b for _, b in sim.bridge.pressed_log]
        check(a['result'] == 'no-song' and wire == ['LEFT', 'Y', 'X', 'L', 'B'] and sim.bridge.notes == ['Y', 'X', 'L'],
              f"ocarina takes it out (D-pad Left), plays the notes in order, and when the game takes no song puts it away with B: no-song ({a['result']}; {wire})")
        check('note wait turned on' in a['detail'] and 'note wait turned off' in a['detail'] and 'Y X L' in a['detail'],
              f"the detail has the notes and the game's oc lines ({a['detail']})")
        check(not sim.bridge.oc_on, 'the ocarina is away afterwards')
        check([h for _, _, h in sim.bridge.note_log] == [0.1] * 3 and [b[1] - a_[1] for a_, b in zip(sim.bridge.note_log, sim.bridge.note_log[1:])] == [15, 15],
              f'notes are held 100 ms and start 0.25 s apart by default: the timing the game took a song at in every run of hold pi2-h1 ({sim.bridge.note_log})')
        seqs = [r for r in sim.bridge.requests if r['cmd'] == 'sequence' and 'L/' in r.get('script', '')]
        check(len(seqs) == 1 and seqs[0]['units'] == 'hos' and seqs[0]['script'] == '0:Y/100,0.25:X/100,0.5:L/100',
              f"the notes go out as ONE timed sequence, not one request each ({[r.get('script') for r in seqs]})")
    # hold and gap: the notes' length and the pause after each (a song taken at 100/150 ms)
    with WorldSimulation(boot_events=0, follow=False) as sim:
        sim.executor(['ocarina Y X L hold 400 gap 600', 'end']).run()
        a = sim.steps()[0]
        log = sim.bridge.note_log
        check(a['result'] == 'no-song' and sim.bridge.notes == ['Y', 'X', 'L'] and [h for _, _, h in log] == [0.4] * 3 and
              [b[1] - a_[1] for a_, b in zip(log, log[1:])] == [60, 60],
              f"ocarina ... hold 400 gap 600: each note held 0.4 s, the next started 1.0 s after the one before ({log}; {a['detail']})")
    # a window just opened ignores the notes pressed in its first 3 s (holds pi2-h1..h3: 21 of 22 tries in a fresh window gave no song, 6 of 6 in one that had been
    # open 3 s or more did; with the poller on, the first note was missing and the game had five notes): the step lets the window warm up before the notes, unless it has been open that long
    tune = ['A', 'Y', 'L', 'X', 'R', 'A']   # an invented song: the simulated game takes these six notes, in this order, and nothing else
    play = 'ocarina ' + ' '.join(tune)
    with WorldSimulation(boot_events=0, follow=False, song=tune, warm=180) as sim:
        sim.executor([play, 'end']).run()
        a = sim.steps()[0]
        first = sim.bridge.note_log[0][1] if sim.bridge.note_log else None
        left = [f for f, x in sim.bridge.pressed_log if x == 'LEFT'][0]
        check(a['result'] == 'played' and not sim.bridge.dropped and first is not None and first - left >= 175,
              f"the step waits for the window: no note was lost, the first came {None if first is None else first - left} frames after the D-pad Left ({a['result']}; dropped {sim.bridge.dropped})")
    with WorldSimulation(boot_events=0, follow=False, song=tune, warm=180) as sim:
        sim.executor([play + ' ready 0', 'end']).run()
        a = sim.steps()[0]
        check(a['result'] == 'no-song' and sim.bridge.dropped == tune[:1],
              f"ready 0 plays at once: the first note is lost and there is no song ({a['result']}; dropped {sim.bridge.dropped})")
    with WorldSimulation(boot_events=0, follow=False, song=tune, warm=180) as sim:
        sim.executor(['ocarina out', 'wait 3.5', play, 'end']).run()
        a, b = [s for s in sim.steps() if s['src'].split()[0] == 'ocarina']
        first = sim.bridge.note_log[0][1]
        left = [f for f, x in sim.bridge.pressed_log if x == 'LEFT'][0]
        check(b['result'] == 'played' and first - left < 300 and not sim.bridge.dropped,
              f"a window that has been open 3.5 s needs no further wait: the notes start {first - left} frames after the D-pad Left ({b['result']}, {b['secs']} s)")
    # a song the game takes: it closes the note wait by itself (no B from us), plays it back and holds Link; the step waits for control and says played
    with WorldSimulation(boot_events=0, follow=False, song=tune) as sim:
        sim.executor([play, 'end']).run()
        a = sim.steps()[0]
        wire = [b for _, b in sim.bridge.pressed_log]
        check(a['result'] == 'played' and wire == ['LEFT'] + tune and sim.bridge.songs_taken == 1 and 'B' not in wire,
              f"a song the game takes ends played and nobody presses B ({a['result']}; {wire}; {a['detail']})")
        check(sim.game.st['event'] == 0 and sim.bridge.busy_left == 0 and a['secs'] >= 5.0,
              f"the step waited until the song's playback let Link go ({a['secs']} s, event {sim.game.st['event']})")
    # the same notes too slowly (0.6 s apart: invented rule, the game's own is not known beyond 0.25 s): not taken, put away
    with WorldSimulation(boot_events=0, follow=False, song=tune) as sim:
        sim.executor([play + ' gap 450', 'end']).run()
        a = sim.steps()[0]
        check(a['result'] == 'no-song' and sim.bridge.songs_taken == 0 and [b for _, b in sim.bridge.pressed_log][-1] == 'B',
              f"notes the game does not take end no-song and the ocarina is put away ({a['result']})")
    # after a song the playback holds Link and a D-pad Left sent into it is lost: the step after the song finds him free; and an `ocarina out`
    # asked while a scene or a playback holds Link waits for control before the D-pad Left
    with WorldSimulation(boot_events=0, follow=False, song=tune) as sim:
        sim.executor([play, 'ocarina out', 'ocarina away', 'end']).run()
        a, b, c = sim.steps()
        check(a['result'] == 'played' and b['result'] == 'out' and c['result'] == 'away' and not sim.bridge.lost,
              f"ocarina out right after a taken song works and no button was lost ({a['result']}, {b['result']}, {c['result']}; lost {sim.bridge.lost})")
    with WorldSimulation(boot_events=0, follow=False, oc_busy=420) as sim:
        sim.executor(['ocarina out', 'ocarina away', 'end']).run()
        a, b = sim.steps()
        left = [f for f, x in sim.bridge.pressed_log if x == 'LEFT']
        check(a['result'] == 'out' and not sim.bridge.lost and len(left) == 1 and left[0] > 420 - 5,
              f"ocarina out while Link is held (7 s of playback) waits and sends the D-pad Left once he is free ({a['result']}; LEFT at {left}; lost {sim.bridge.lost})")
    with WorldSimulation(boot_events=0, follow=False, ocarina=False) as sim:
        sim.executor(['ocarina A', 'end']).run()
        a = sim.steps()[0]
        check(a['result'] == 'no-ocarina' and [b for _, b in sim.bridge.pressed_log] == ['LEFT'] and 3.0 <= a['secs'] <= 5.0,
              f"no note wait after D-pad Left: no-ocarina, no notes ({a['secs']} s)")
    with WorldSimulation(boot_events=0, follow=False) as sim:
        sim.executor(['ocarina out', 'report 0.2', 'wait 0.6', 'ocarina away', 'wait 0.6', 'end']).run()
        a, c = [s for s in sim.steps() if s['src'].split()[0] == 'ocarina']
        check(a['result'] == 'out' and c['result'] == 'away' and [b for _, b in sim.bridge.pressed_log] == ['LEFT', 'B'],
              'ocarina out and ocarina away')
        states = [e for e in sim.events() if e['ev'] == 'state']
        seen = [e.get('ocarina') for e in states if e['why'] == 'report']
        check('ocarina' not in states[0] and seen[0] == 'on' and seen[-1] == 'off' and states[-1].get('ocarina') == 'off',
              'the state line shows the ocarina once the game has said anything about it')

    # while the ocarina waits for a note the game holds Link (event 1) like a text box would: A there is a note, not a way out. advance must send nothing
    # (first real warp run: 36 A presses in 50 s, two timeouts, a whole objective)
    with WorldSimulation(boot_events=0, follow=False, oc_event=True) as sim:
        sim.executor(['ocarina out', 'wait 0.5', 'advance timeout 4', 'ocarina away', 'wait 0.6', 'end']).run()
        out, adv, away = [s for s in sim.steps() if s['src'].split()[0] in ('ocarina', 'advance')]
        check(out['result'] == 'out' and adv['result'] == 'none' and adv['secs'] < 2.0 and 'ocarina' in adv['detail'] and sim.bridge.notes == [],
              f"advance while the ocarina waits for a note sends nothing and says so ({adv['result']}: {adv['detail']}, {adv['secs']} s, notes {sim.bridge.notes})")
        check(away['result'] == 'away' and not sim.bridge.oc_on, 'and ocarina away still puts it back')

    watch = ['Item.Count']
    with WorldSimulation(boot_events=0, follow=False, flags={'Item.Count': 10}, watch=watch) as sim:
        sim.executor(['item', 'item Y 100', 'end']).run()
        a, b = sim.steps()
        zr = [r for r in sim.bridge.requests if r['cmd'] == 'press']
        check(a['result'] == 'used' and a['changes']['flags'] == {'Item.Count': [10, 9]} and zr[0]['buttons'] == 'ZR' and zr[0]['frames'] == 9,
              f"item presses ZR (the item button) 150 ms and reports the count ({a['detail']})")
        check(zr[1]['buttons'] == 'Y' and zr[1]['frames'] == 6 and b['result'] == 'none', 'item takes another button and a time; nothing changed: none')

    # rendezvous: two players meet at a wall-clock instant
    with tempfile.TemporaryDirectory(prefix='hsap-rv-') as d, mock.patch.dict(os.environ, {'HSAP_RENDEZVOUS': d, 'HSAP_SIDE': 'A'}):
        with WorldSimulation(boot_events=0, follow=False) as sim:
            Path(d, 'go.B').write_text(json.dumps({'t': sim.clock.time() - 0.5}))
            sim.executor(['rendezvous go timeout 5', 'rendezvous other timeout 2', 'end']).run()
            a, b = sim.steps()
            check(a['result'] == 'met' and 1.4 <= a['secs'] <= 1.8 and Path(d, 'go.A').exists(),
                  f"rendezvous: the other side's file is there: both leave 1.5 s after the later one wrote ({a['secs']} s)")
            check(b['result'] == 'timeout' and 1.9 <= b['secs'] <= 2.4, f"nobody came: timeout ({b['secs']} s)")
    with WorldSimulation(boot_events=0, follow=False) as sim:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('HSAP_RENDEZVOUS', None)
            sim.executor(['rendezvous go', 'end']).run()
        check(sim.steps()[0]['result'] == 'alone', 'without HSAP_RENDEZVOUS the step ends alone at once')


def interact_walk_checks():
    def sticks(sim):
        return [(r['x'], r['y']) for r in sim.bridge.requests if r['cmd'] == 'stick']

    def walk(line, analog=True, seed_line=None):
        with WorldSimulation(boot_events=0, follow=False) as sim:
            ex = sim.executor([line, 'end'])
            ex.analog = analog
            ex.run()
            return sim.steps()[0], sticks(sim)
    plain, plain_sticks = walk('walk 0 12 radius 0.5 timeout 20')
    capped, capped_sticks = walk('walk 0 12 radius 0.5 timeout 20 mag 0.4')
    check(plain['result'] == 'reached' and capped['result'] == 'reached' and max(math.hypot(*s) for s in plain_sticks) > 0.95,
          'an ordinary walk is unchanged: full stick far from the point')
    check(max(math.hypot(*s) for s in capped_sticks) <= 0.4 + 1e-3, 'mag 0.4 caps the stick at 0.4 the whole way')
    n1, n1s = walk('walk 0 12 radius 0.5 timeout 25 noise 8 seed 3')
    n2, n2s = walk('walk 0 12 radius 0.5 timeout 25 noise 8 seed 3')
    n3, n3s = walk('walk 0 12 radius 0.5 timeout 25 noise 8 seed 4')
    check(n1['result'] == 'reached' and n1s == n2s and n1s != n3s and n1s != plain_sticks,
          'noise D with seed S wanders the angle: the same seed the same hand, another seed another, none = unchanged')
    angles = [math.degrees(math.atan2(x, y)) for x, y in n1s]
    far = n1s[:len(n1s) // 2]   # (the first half of the way: far from the point, at the full push)
    check(max(abs(a) for a in angles) > 1.0 and max(abs(a) for a in angles) < 40.0 and
          min(math.hypot(*s) for s in far) > 0.9 and max(math.hypot(*s) for s in n1s) <= 1.0 + 1e-3,
          'the noise is degrees, not a swerve, and the magnitude stays within 5 percent below full')
    digital, _ = walk('walk 0 12 radius 0.5 timeout 25 noise 8 seed 3', analog=False)
    check(digital['result'] == 'reached', 'noise also steers the eight-direction walk')
    for bad in ('walk 0 12 mag 0', 'walk 0 12 mag 1.5', 'walk 0 12 mag x', 'walk 0 12 noise -1', 'walk 0 12 seed x'):
        with WorldSimulation(boot_events=0, follow=False) as sim:
            sim.executor([bad, 'end']).run()
            check([e['src'] for e in sim.events() if e['ev'] == 'bad'] == [bad] and not sticks(sim),
                  f'{bad!r} is a bad step and sends nothing')


def interact_bad_checks():
    bad = ['chest now', 'chest timeout', 'chest timeout x', 'talk quick', 'advance x', 'advance timeout', 'interact timeout',
           'pickup', 'pickup 1', 'pickup a b', 'pickup 1 2 radius', 'pickup 1 2 radius 0', 'pickup 1 2 dive', 'pickup 1 2 dive 0.1', 'pickup 1 2 dive 99', 'enter', 'enter 1', 'enter 1 2 through 3',
           'enter 1 2 through a b', 'ztarget x', 'ztarget 5', 'ztarget 99999', 'camera', 'camera sideways', 'camera left x',
           'camera left 5', 'camera to', 'camera to x', 'faceat', 'faceat 1', 'faceat 1 2 3 4', 'ocarina Q', 'ocarina out L', 'ocarina L hold', 'ocarina L hold 10', 'ocarina L hold 9000', 'ocarina L gap x', 'ocarina hold 300', 'ocarina out hold 300',
           'ocarina away R', 'item Q', 'item A x', 'item A 5', 'rendezvous', 'rendezvous a b c', 'rendezvous x timeout']
    with WorldSimulation(boot_events=0, follow=False) as sim:
        sim.executor(bad + ['wait 0.1', 'end']).run()
        got = [e['src'] for e in sim.events() if e['ev'] == 'bad']
        check(got == bad, f'{len(bad)} malformed interaction steps are answered bad, each by its own usage text')
        check(not [r for r in sim.bridge.requests if r['cmd'] in ('press', 'stick', 'sequence')], 'and none of them sent an input')


def interact_checks():
    interact_step_checks()
    interact_move_checks()
    interact_view_checks()
    interact_gear_checks()
    interact_walk_checks()
    interact_bad_checks()


# ---- the panel: the pilot's decisions on the game's own screen (the control bridge's `overlay` command)

OVERLAY = ('overlay', 'overlay_clear')
PANEL = 'GOAL door [open] FOR porch\ndecision 1/40  t 0.0 s\nSTEP go running'
PANEL2 = 'GOAL door [open] FOR porch\ndecision 2/40  t 9.5 s\nSTEP go -> reached'


def write_hud(sim, text):
    """What the pilot does: a temporary file renamed over <live>/hud.txt (an empty text: an empty file)."""
    tmp = sim.live / 'hud.txt.tmp'
    tmp.write_text(text + '\n' if text else '')
    os.replace(tmp, sim.live / 'hud.txt')


def sets_of(sim):
    return [(t, r) for t, r in sim.bridge.overlay_log if r['cmd'] == 'overlay']


def others_of(sim):
    """Every request that is not the panel's, without its id (the panel's requests take ids too)."""
    return [{k: v for k, v in r.items() if k != 'id'} for r in sim.bridge.requests if r['cmd'] not in OVERLAY]


def hud_wire_checks():
    with Simulation(boot_events=0) as sim:
        ex = sim.executor(hud=True)
        check(sim.game.hud is ex.hud and ex.hud is not None, 'the executor makes the panel sender and the game routes its replies to it')
        sim.exchange()
        for _ in range(10):
            ex.tick(0.05)
        check(not sim.bridge.overlay_log, 'no panel file: nothing is sent, not even a clear')
        write_hud(sim, PANEL)
        for _ in range(10):
            ex.tick(0.05)
        ov = sim.bridge.overlay_log
        check(len(ov) == 1 and set(ov[0][1]) == {'id', 'cmd', 'text', 'seconds'} and ov[0][1]['cmd'] == 'overlay' and
              ov[0][1]['text'] == PANEL and ov[0][1]['seconds'] == 60,
              'the panel is one `overlay` request on the open connection: {id, cmd, text with its newlines, seconds: 60}')
        check(sim.bridge.shown() == PANEL and not [c for c in sim.game.pending.values() if c in OVERLAY],
              'the game shows it, and its ok reply was consumed like any other (nothing left pending)')
        for _ in range(10):
            ex.tick(0.05)
        write_hud(sim, PANEL)   # (the pilot wrote the same text again: a new file, the same words)
        for _ in range(20):
            ex.tick(0.05)
        check(len(sets_of(sim)) == 1, 'the same text again is not sent again')
        write_hud(sim, PANEL2 + '\n\n')
        for _ in range(10):
            ex.tick(0.05)
        check(len(sets_of(sim)) == 2 and sets_of(sim)[1][1]['text'] == PANEL2 and sim.bridge.shown() == PANEL2,
              'a new text is sent at once, trailing newlines left out')
        big = '\n'.join('x' * 56 for _ in range(14))
        write_hud(sim, big)
        for _ in range(10):
            ex.tick(0.05)
        check(sim.bridge.shown() == big, 'a full panel (14 lines of 56 characters) is accepted by a game that enforces the caps')
        ids = [r['id'] for _, r in sim.bridge.overlay_log]
        check(len(set(ids)) == len(ids) and not set(ids) & {r['id'] for r in sim.bridge.requests if r['cmd'] not in OVERLAY},
              'the requests use ids of their own, like any other command')


def hud_throttle_checks():
    # the pilot writes a new text every 50 ms for three seconds: at most four requests a second, the latest text wins, no backlog
    with Simulation(boot_events=0) as sim:
        ex = sim.executor(['wait 6', 'end'], hud=True)
        t0 = sim.clock.time()
        texts = [f'GOAL g [open] FOR t\ndecision {i}/99  t {i}.0 s' for i in range(1, 61)]
        for i, text in enumerate(texts):
            sim.clock.at(t0 + 1.0 + i * 0.05, lambda text=text: write_hud(sim, text))
        last_write = t0 + 1.0 + 59 * 0.05
        ex.run()
        sim.clock.sleep(0.1)   # (the fake game reads what hsap sent last)
        sets = [(t, r['text']) for t, r in sets_of(sim)]
        times = [t for t, _ in sets]
        check(len(sets) >= 8 and all(b - a >= 0.25 for a, b in zip(times, times[1:])) and
              all(times[i + 4] - times[i] >= 1.0 for i in range(len(times) - 4)),
              f'at most four requests in any second ({len(sets)} requests in {times[-1] - times[0]:.1f} s)')
        check(len(sets) < len(texts) // 2 and all(text in texts for _, text in sets), f'texts that were overwritten before their turn are never sent ({len(sets)} of {len(texts)})')
        check(sets[-1][1] == texts[-1] and sets[-1][0] <= last_write + 0.4, 'the latest text wins, and it goes out at the next turn: no backlog to work off')
        check(sim.bridge.overlay_log[-1][1]['cmd'] == 'overlay_clear' and all(b[0] - a[0] >= 0.25 for a, b in zip(sim.bridge.overlay_log, sim.bridge.overlay_log[1:])),
              'the clear at the end keeps the spacing too')
    # a socket that does not take writes: one request waits at most, never a pile
    with Simulation(boot_events=0) as sim:
        ex = sim.executor(hud=True)
        sim.exchange()
        limited = SendBudget(sim.game.sock, 0)
        sim.game.sock = limited
        for i in range(12):
            write_hud(sim, f'text {i}')
            ex.tick(0.3)
        check(bytes(sim.game.tx).count(b'"cmd":"overlay"') <= 1, 'a blocked socket holds at most one panel request, not one per change')
        limited.budget = None
        for _ in range(20):
            ex.tick(0.3)
        check(sim.bridge.shown() == 'text 11', 'when it frees up the latest text is what the game shows')


def hud_keepalive_checks():
    with Simulation(boot_events=0) as sim:
        write_hud(sim, PANEL)
        ex = sim.executor(['wait 100', 'end'], hud=True)
        t0 = sim.clock.time()
        samples = []
        for k in range(5, 100):
            sim.clock.at(t0 + k, lambda: samples.append(sim.bridge.shown()))
        ex.run()
        sets = sets_of(sim)
        gaps = [b[0] - a[0] for a, b in zip(sets, sets[1:])]
        check(len(sets) >= 4 and all(25.0 <= g <= 25.5 for g in gaps) and all(r['text'] == PANEL and r['seconds'] == 60 for _, r in sets),
              f'nothing changed for 100 s: the same text again every 25 s, seconds 60 each time ({len(sets)} requests, gaps {[round(g, 2) for g in gaps]})')
        check(len(samples) == 95 and all(s == PANEL for s in samples),
              'the game (which drops a panel 60 s after its last request) showed it every second of the run')
    with Simulation(boot_events=0) as sim:   # a change restarts the 25 s
        ex = sim.executor(['wait 70', 'end'], hud=True)
        t0 = sim.clock.time()
        write_hud(sim, PANEL)
        sim.clock.at(t0 + 20, lambda: write_hud(sim, PANEL2))
        ex.run()
        sets = sets_of(sim)
        check([r['text'] for _, r in sets][:2] == [PANEL, PANEL2] and 24.5 <= sets[2][0] - sets[1][0] <= 25.5,
              'a new text is sent at once and its own 25 s run from there')


def hud_clear_checks():
    with Simulation(boot_events=0) as sim:
        write_hud(sim, PANEL)
        ex = sim.executor(['wait 5', 'end'], hud=True)
        ex.run()
        sim.clock.sleep(0.1)
        ov = sim.bridge.overlay_log
        check([r['cmd'] for _, r in ov] == ['overlay', 'overlay_clear'] and set(ov[-1][1]) == {'id', 'cmd'} and sim.bridge.shown() is None,
              'at the end of a run (the end step) the panel is cleared with overlay_clear, before the connection closes')
        check(sim.bridge.conn is not None, 'while the connection is still open (the game need not drop it itself)')
    with Simulation(boot_events=0) as sim:
        ex = sim.executor(['wait 3', 'end'], hud=True)
        ex.run()
        check(not sim.bridge.overlay_log, 'a run that never had a panel sends nothing at all at its end')
    with Simulation(boot_events=0) as sim:   # an emptied or removed file clears the panel, once; a new text shows it again
        ex = sim.executor(hud=True)
        sim.exchange()
        write_hud(sim, PANEL)
        for _ in range(20):
            ex.tick(0.05)
        write_hud(sim, '')
        for _ in range(20):
            ex.tick(0.05)
        check([r['cmd'] for _, r in sim.bridge.overlay_log] == ['overlay', 'overlay_clear'] and sim.bridge.shown() is None,
              'the pilot empties the file: overlay_clear')
        for _ in range(700):
            ex.tick(0.05)
        check(len(sim.bridge.overlay_log) == 2, 'nothing more while there is nothing to show (no keep-alive of an empty panel)')
        write_hud(sim, PANEL2)
        for _ in range(20):
            ex.tick(0.05)
        check(sim.bridge.shown() == PANEL2, 'a new text shows it again')
        os.unlink(sim.live / 'hud.txt')
        for _ in range(20):
            ex.tick(0.05)
        check(sim.bridge.shown() is None and [r['cmd'] for _, r in sim.bridge.overlay_log] == ['overlay', 'overlay_clear', 'overlay', 'overlay_clear'],
              'a removed file clears it too')
    with Simulation(boot_events=0) as sim:   # the run ends in an error: the clear is tried and never raises
        write_hud(sim, PANEL)
        ex = sim.executor(hud=True)
        sim.exchange()
        for _ in range(10):
            ex.tick(0.05)
        sim.bridge.conn.close()
        sim.bridge.conn = None
        ex.hud.close()
        check(True, 'closing the panel after the connection is gone raises nothing')


def hud_run_case(mode, hud, flip=None):
    """One run of the same steps, the pilot's panel file changing during it: what hsap did (steps, every other request), what the
    panel did (its requests, the notes it left, what the game shows at the end)."""
    with Simulation(boot_events=1, overlay=mode) as sim:
        t0 = sim.clock.time()
        sim.clock.at(t0 + 1.0, lambda: write_hud(sim, PANEL))
        sim.clock.at(t0 + 12.0, lambda: write_hud(sim, PANEL2))
        sim.clock.at(t0 + 20.0, lambda: write_hud(sim, PANEL))
        if flip:
            sim.clock.at(t0 + flip[0], lambda: setattr(sim.bridge, 'overlay_mode', flip[1]))
        ex = sim.executor(['walk 6 8 radius 0.6 timeout 15', 'press A 100', 'wait 40', 'end'], hud=hud)
        ex.run()
        sim.clock.sleep(0.1)
        ev = sim.events()
        return {'steps': [e for e in ev if e['ev'] in ('step', 'bad', 'gameplay')], 'others': others_of(sim),
                'sets': [r['text'] for _, r in sets_of(sim)], 'all': [r['cmd'] for _, r in sim.bridge.overlay_log],
                'notes': [e['text'] for e in ev if e['ev'] == 'note' and 'overlay' in e['text']], 'shown': sim.bridge.shown(),
                'done': [e for e in ev if e['ev'] == 'done']}


def hud_error_checks():
    off = hud_run_case('ok', hud=False)
    check(off['all'] == [] and off['shown'] is None and len(off['steps']) == 5, 'the baseline: the same run with the panel off sends nothing')
    ok = hud_run_case('ok', hud=True)
    check(len(ok['sets']) >= 4 and ok['all'][-1] == 'overlay_clear' and ok['shown'] is None and not ok['notes'],
          f"a game that does it: the panel follows the file, keep-alives in the long wait, cleared at the end ({ok['all']})")
    check(ok['steps'] == off['steps'] and ok['others'] == off['others'] and len(ok['done']) == 1,
          'steps, their results, times and every other request are exactly those of the run with the panel off')
    for mode in ('unavailable', 'unknown_cmd'):
        run = hud_run_case(mode, hud=True)
        check(run['all'] == ['overlay'] and run['shown'] is None,
              f'{mode}: one request, and not another for the rest of the run (no new text, no keep-alive, no clear): {run["all"]}')
        check(len(run['notes']) == 1 and mode in run['notes'][0] and 'overlay' in run['notes'][0],
              f'{mode}: noted once in the run\'s own event file ({run["notes"]})')
        check(run['steps'] == off['steps'] and run['others'] == off['others'] and len(run['done']) == 1,
              f'{mode}: nothing else about the run changed: the same steps, results, times and requests as with the panel off')
    for mode in ('bad_request', 'busy'):
        run = hud_run_case(mode, hud=True, flip=(8.0, 'ok'))
        check(run['sets'][:2] == [PANEL, PANEL2] and len(run['notes']) == 1,
              f'{mode}: noted once; the refused text is not sent again as a keep-alive; the next text is tried ({run["sets"][:3]})')
        check(run['notes'] and mode in run['notes'][0], f'{mode}: the note names the code ({run["notes"]})')
        check(run['shown'] is None and run['all'][-1] == 'overlay_clear', f'{mode}: not stopped for good: once the game takes it, it is cleared at the end too')
        check(run['steps'] == off['steps'] and run['others'] == off['others'], f'{mode}: the run itself is unchanged')
    # the refusal comes while a step is waiting: no ControlError, whatever the code
    run = hud_run_case('something_new', hud=True)
    check(len(run['notes']) == 1 and 'something_new' in run['notes'][0] and run['steps'] == off['steps'],
          'any other refusal code is noted once and never ends the run')


def hud_off_checks():
    with Simulation(boot_events=0) as sim:
        write_hud(sim, PANEL)
        ex = sim.executor(['wait 40', 'end'], hud=False)
        ex.run()
        check(ex.hud is None and sim.game.hud is None and not sim.bridge.overlay_log, 'panel off: nothing is sent, however the file changes')
    before = dict(os.environ)
    for hud, want in ((False, False), (True, True)):
        with Simulation(boot_events=0, hud_game=hud) as sim:
            menu = [a for a in sim.launched if 'RX_VK_SHOT_MENU' in a]
            check(menu == (['RX_VK_SHOT_MENU=1'] if want else []),
                  f'a game hsap starts: RX_VK_SHOT_MENU=1 {"is" if want else "is not"} in its command with the panel {"on" if want else "off"}')
            check('RX_VK_SHOT_MENU' not in sim.launch_env and sim.launch_env == {k: v for k, v in os.environ.items() if k not in hsap.SLOT_VARS and k != 'OPENAI_API_KEY'},
                  'and the environment hsap gives the runner is the same either way')
    check(dict(os.environ) == before, 'hsap never changes its own environment')
    with ExternalSimulation(boot_events=0, hud_game=True, follow=False) as sim:
        ex = sim.executor(['wait 2', 'end'], hud=True, opponent=False)
        write_hud(sim, PANEL)
        ex.run()
        sim.clock.sleep(0.1)
        check(not sim.spawned and not any('RX_VK_SHOT_MENU' in str(a) for a in sim.game.cmd) and
              [r['cmd'] for _, r in sim.bridge.overlay_log] == ['overlay', 'overlay_clear'],
              'an external game is never started or changed (no RX_VK_SHOT_MENU), and still gets the panel over the control socket, cleared at the end')
    ask = hsap.hud_wanted
    check(ask(None, {}) and ask('on', {}) and not ask('off', {}) and not ask(None, {'HSAP_HUD': '0'}) and not ask('on', {'HSAP_HUD': '0'}) and
          ask('on', {'HSAP_HUD': '1'}) and ask(None, {'HSAP_HUD': ''}), '--hud off or HSAP_HUD=0 turn the panel off; otherwise it is on')


def hud_restart_checks():
    # the game execs itself: its panel went with the old connection, so the same text is shown again on the new one at once
    with DuelSimulation(boot_events=0) as sim:
        sim.game.reconnect_wait = 30.0
        ex = sim.executor(hud=True, opponent=False)
        sim.exchange()
        write_hud(sim, PANEL)
        for _ in range(20):
            ex.tick(0.05)
        check(sim.bridge.shown() == PANEL, 'before the restart the panel is shown')
        sim.bridge.drop()
        for _ in range(40):
            ex.tick(0.05)
        write_hud(sim, PANEL2)
        for _ in range(40):
            ex.tick(0.05)
        check(sim.game.down and b'overlay' not in bytes(sim.game.tx) and not [c for c in sim.game.pending.values() if c in OVERLAY],
              'while the socket is gone nothing is queued for the new process')
        sent_before = len(sim.bridge.overlay_log)
        sim.bridge.revive()
        for _ in range(100):
            ex.tick(0.05)
        check(not sim.game.down and len(sim.bridge.overlay_log) == sent_before + 1 and sim.bridge.shown() == PANEL2,
              'the new process gets the latest text within seconds, not after a keep-alive')
        sim.bridge.drop()
        for _ in range(40):
            ex.tick(0.05)
        sim.bridge.revive()
        for _ in range(100):
            ex.tick(0.05)
        check(sim.bridge.shown() == PANEL2, 'and again after a second restart with no new text: the same text is shown again')


def hud_checks():
    hud_wire_checks()
    hud_throttle_checks()
    hud_keepalive_checks()
    hud_clear_checks()
    hud_error_checks()
    hud_off_checks()
    hud_restart_checks()


def main():
    transport_checks()
    executor_checks()
    duel_checks()
    external_checks()
    interact_checks()
    hud_checks()
    print('test_hsap: all passed')

if __name__ == '__main__':
    main()
