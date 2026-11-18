#!/usr/bin/env python3
"""fake_game.py <control socket> <live file> <run folder> <scenario.json>: a simulated game in real time (60 presents a second) behind the control bridge, for
rehearsals. The bridge is the test suite's ActionBridge (invented physics: gaps, ledges, water, blocks, shops) with the scenario's start, map, age and things.
Scenario keys: map, age, start [x, y, z], things [...], and ActionBridge's own options (gap, ledge, water, ladder, block, horse, circle, rupees, flags ...)."""
import json
import os
import signal
import sys
import time
from pathlib import Path

TREE = Path(os.environ['REHEARSE_TREE'])
sys.path.insert(0, str(TREE))
sys.path.insert(0, str(TREE / 'pilot'))
import test_hsap as T            # noqa: E402
import test_hsap_actions as A    # noqa: E402
import vision                    # noqa: E402  (write_png: the pictures the fake game's `shot` writes)


class Clock:
    @property
    def now(self):
        return time.time()


class Game(A.ActionBridge):
    def __init__(self, *args, age='child', map_name='Test_Map', **kw):
        self.age = age
        self.extra = []
        super().__init__(*args, **kw)
        self.map_name = map_name

    def game_state(self, frame=None):
        s = super().game_state(frame)
        s['age'] = self.age
        return s

    def pump(self):
        super().pump()
        # More clients than hsap (the pilot's vision and planner pictures open a connection of their own for `shot`): the real game serves many
        if self.listener is not None and self.conn is not None:
            try:
                c, _ = self.listener.accept()
                c.setblocking(False)
                self.extra.append((c, bytearray()))
            except (BlockingIOError, OSError):
                pass
        for c, buf in list(self.extra):
            try:
                data = c.recv(65536)
            except BlockingIOError:
                continue
            except OSError:
                data = b''
            if not data:
                c.close()
                self.extra.remove((c, buf))
                continue
            buf.extend(data)
            while b'\n' in buf:
                line, _, rest = bytes(buf).partition(b'\n')
                buf[:] = rest
                req = json.loads(line)
                if req.get('cmd') == 'shot':
                    Path(req['path']).write_bytes(vision.write_png(64, 36, bytes([(self.frame // 4 + 3 * i) % 256 for i in range(64 * 36 * 3)])))
                    reply = {'id': req['id'], 'ok': True, 'frame': self.frame, 'present': self.frame, 'path': req['path'], 'width': 64, 'height': 36}
                else:
                    reply = {'id': req['id'], 'ok': False, 'error': 'unknown_cmd', 'message': 'the fake game answers shot only on a second connection'}
                c.sendall((json.dumps(reply) + '\n').encode())

    def effect(self, t):
        super().effect(t)
        for k, v in (t.get('set') or {}).items():   # (a scenario thing can set watched flags: what a chest or a talk does in the game)
            self.flags[k] = v


def main():
    sock, live, run, scen = sys.argv[1:5]
    sc = json.loads(Path(scen).read_text())
    opts = {k: v for k, v in sc.items() if k not in ('map', 'age', 'start')}
    for k in ('gap', 'ledge', 'water', 'ladder'):
        if opts.get(k) is not None:
            opts[k] = tuple(opts[k])
    clock = Clock()
    g = Game(Path(sock), Path(live), Path(run), clock, start=tuple(sc.get('start', (0.0, 0.0, 0.0))), age=sc.get('age', 'child'),
             map_name=sc.get('map', 'Test_Map'), **opts)
    clock.bridge = g
    (Path(run) / 'env-used.txt').write_text(f'HOS_CONTROL={sock}\nHOS_INPUT_LIVE={live}\n')   # (vision finds the socket here, as in a real run)
    stop = []
    signal.signal(signal.SIGTERM, lambda *a: stop.append(1))
    step, nxt = 1 / 60, time.monotonic()
    while not stop:
        now = time.monotonic()
        if now < nxt:
            g.pump()
            time.sleep(min(0.004, nxt - now))
            continue
        nxt += step
        if now - nxt > 1.0:
            nxt = now
        g.pump()
        g.tick()
        g.pump()
    g.close()
    (Path(run) / 'exit.txt').write_text('143\n')
    (Path(run) / 'summary.txt').write_text('rehearsal: fake game stopped\n')


if __name__ == '__main__':
    main()
