#!/usr/bin/env python3
"""burst.py against a FAKE control bridge (a Unix socket server in this file that answers `shot` the way the game's does: a PNG at the path
asked for, `present` counting up) and made-up run folders: one burst (pictures renamed by present, the manifest, partial answers, a refused
shot, no socket, a silent game), the live Burster (a black picture, a change while nothing moved, no trigger while Link walks, the budgets,
the still-moment probes, a game that is gone). Made-up names; no game, no GPU, no network.   python3 -I -B test_burst.py
"""
import json
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bughunt  # noqa: E402
import burst  # noqa: E402
import test_bughunt as tb  # noqa: E402
import vision  # noqa: E402

FAILS = []
CHECKS = [0]


def check(cond, what):
    CHECKS[0] += 1
    if not cond:
        FAILS.append(what)
        print('FAIL', what, flush=True)


def png(grey):
    return vision.write_png(16, 9, bytes([grey, grey, grey] * 144))


class FakeBridge(threading.Thread):
    """Answers `shot` requests: pattern[k % len(pattern)] is the k-th picture's grey level, present counts up by `step` from `present0`.
    refuse: shot numbers answered with an error; stop_after: close the connection after that many answers; silent: never answer."""

    def __init__(self, path, pattern=(100, 100, 100), present0=1000, step=3, refuse=(), stop_after=None, silent=False):
        super().__init__(daemon=True)
        self.path, self.pattern, self.present, self.step = str(path), pattern, present0, step
        self.refuse, self.stop_after, self.silent = set(refuse), stop_after, silent
        self.served, self.requests = 0, []
        self.srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.srv.bind(self.path)
        self.srv.listen(4)
        self.srv.settimeout(0.2)
        self.halt = threading.Event()

    def run(self):
        while not self.halt.is_set():
            try:
                c, _ = self.srv.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            threading.Thread(target=self.serve, args=(c,), daemon=True).start()

    def serve(self, c):
        buf = b''
        c.settimeout(0.5)
        answered = 0
        while not self.halt.is_set():
            try:
                chunk = c.recv(65536)
            except socket.timeout:
                continue
            except OSError:
                return
            if not chunk:
                return
            buf += chunk
            while b'\n' in buf:
                line, _, buf = buf.partition(b'\n')
                req = json.loads(line)
                self.requests.append(req)
                if self.silent:
                    continue
                if self.stop_after is not None and answered >= self.stop_after:
                    c.close()
                    return
                k = self.served
                self.served += 1
                answered += 1
                if k in self.refuse:
                    c.sendall((json.dumps({'id': req['id'], 'ok': False, 'error': 'unavailable', 'message': 'no shot now', 'frame': 1}) + '\n').encode())
                    continue
                self.present += self.step
                Path(req['path']).write_bytes(png(self.pattern[k % len(self.pattern)]))
                c.sendall((json.dumps({'id': req['id'], 'ok': True, 'frame': self.present + 1, 'present': self.present, 'path': req['path'],
                                       'width': 16, 'height': 9}) + '\n').encode())

    def close(self):
        self.halt.set()
        self.srv.close()


def take_checks(tmp):
    sockp = tmp / 's1.sock'
    b = FakeBridge(sockp, pattern=(100, 180, 100, 180), present0=1000, step=3)
    b.start()
    m = burst.take(sockp, tmp / 'b1', n=6, why='by test')
    check(len(m['pictures']) == 6 and m['errors'] == [], f'take: six pictures, no errors ({m["pictures"]} {m["errors"]})')
    check([p for p, _ in m['pictures']] == [1003, 1006, 1009, 1012, 1015, 1018], 'take: the presents come from the replies, in order')
    check(sorted(x.name for x in (tmp / 'b1').glob('vk_*.png')) == [f'vk_{p:06d}.png' for p in (1003, 1006, 1009, 1012, 1015, 1018)], 'take: the files are renamed vk_<present>.png, none left as b0N.png')
    check(not list((tmp / 'b1').glob('b0*.png')), 'take: no temporary names left')
    man = json.loads((tmp / 'b1' / 'burst.json').read_text())
    check(man['why'] == 'by test' and man['n'] == 6 and len(man['pictures']) == 6, 'take: burst.json is the manifest')
    check(all(r['cmd'] == 'shot' and Path(r['path']).is_absolute() for r in b.requests) and len(b.requests) == 6, 'take: n shot requests with absolute paths, sent on one connection')
    m = burst.take(sockp, tmp / 'b-big', n=99)
    check(m['n'] == burst.MAX_ASK, 'take: n is capped at what the renderer queues')
    b.close()
    # one shot refused, one answered in between
    sockp = tmp / 's2.sock'
    b = FakeBridge(sockp, refuse=(1,))
    b.start()
    m = burst.take(sockp, tmp / 'b2', n=4)
    check(len(m['pictures']) == 3 and len(m['errors']) == 1 and 'unavailable' in m['errors'][0], f'take: a refused shot is an error, the others are kept ({m["errors"]})')
    b.close()
    # the game closes the connection after two answers
    sockp = tmp / 's3.sock'
    b = FakeBridge(sockp, stop_after=2)
    b.start()
    m = burst.take(sockp, tmp / 'b3', n=5)
    check(len(m['pictures']) == 2 and any('closed' in e or 'not answered' in e for e in m['errors']), f'take: a game that goes away mid-burst leaves what it gave ({m["errors"]})')
    b.close()
    # silent game
    sockp = tmp / 's4.sock'
    b = FakeBridge(sockp, silent=True)
    b.start()
    t0 = time.time()
    m = burst.take(sockp, tmp / 'b4', n=3, timeout=0.5, grace=0.5)
    check(not m['pictures'] and 'not answered' in ' '.join(m['errors']) and time.time() - t0 < 5, f'take: a silent game ends at the deadline ({m["errors"]}, {time.time() - t0:.1f} s)')
    b.close()
    m = burst.take(tmp / 'nobody.sock', tmp / 'b5', n=3)
    check(not m['pictures'] and 'no game answers' in m['errors'][0] and (tmp / 'b5' / 'burst.json').is_file(), 'take: no socket is an error in the manifest, not an exception')
    (tmp / 'run').mkdir()
    (tmp / 'run' / 'env-used.txt').write_text('HOS_AUDIO=0\nHOS_CONTROL=/tmp/x/control.sock\nRX_VK_SHOTS=/y\n')
    check(burst.control_socket(tmp / 'run') == '/tmp/x/control.sock', 'control_socket: HOS_CONTROL of env-used.txt')
    check(burst.control_socket(tmp / 'nowhere') is None, 'control_socket: none without env-used.txt')


def live_run(tmp, name, shots, states, gameplay=True, sock=None):
    """a pilot run folder and a game run folder as the watcher sees them: shots = [(present, grey)]"""
    pilot, game = tmp / name / 'pilot', tmp / name / 'game'
    (game / 'shots').mkdir(parents=True)
    for fr, g in shots:
        (game / 'shots' / f'vk_{fr:06d}.png').write_bytes(png(g))
    (pilot / 'live').mkdir(parents=True)
    (pilot / 'live' / 'state.jsonl').write_text(''.join(json.dumps(s) + '\n' for s in states))
    ev = [{'ev': 'gameplay', 't': 0.0, 'frame': states[0]['frame'], 'area': 'Yard'}] if gameplay else []
    (pilot / 'live' / 'out.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in ev))
    if sock:
        (game / 'env-used.txt').write_text(f'HOS_CONTROL={sock}\n')
    return pilot, game


class Taker:
    def __init__(self):
        self.calls = []

    def __call__(self, sock, dest, n, why):
        self.calls.append((str(sock), Path(dest).name, n, why))
        return {'why': why, 'n': n, 'pictures': [[1000 + i, f'vk_{1000 + i}.png'] for i in range(n)], 'errors': [], 'seconds': 0.1}


def burster_checks(tmp):
    cfg = bughunt.Config(burst_gap_s=30.0, burst_max=3, burst_probe_every_s=60.0, burst_probe_still_s=2.0, burst_probe_max=2)
    now = [time.time() + 100.0]

    def clock():
        return now[0]

    def make(name, shots, states, **kw):
        pilot, game = live_run(tmp, name, shots, states, sock='/tmp/fake/control.sock', **kw)
        tk = Taker()
        b = burst.Burster(game, cfg, taker=tk, clock=clock)
        side = lambda: bughunt.Side(pilot, game=game, pilot=pilot)   # noqa: E731  (the watcher builds a new one each poll)
        return b, tk, side, game

    walking = tb.walking(40, frame0=100)       # frames 100.., 6 a sample
    still = tb.steady(40, frame0=100)
    # a picture that was black while the state says play
    b, tk, side, game = make('black', [(100, 120), (190, 1), (280, 1)], still)
    m = b.poll(side())
    check(m is not None and m['kind'] == 'suspicion' and tk.calls and tk.calls[0][2] == cfg.burst_n and 'black' in tk.calls[0][3], f'burster: a black picture while the state says play takes a burst ({tk.calls})')
    check(tk.calls[0][0] == '/tmp/fake/control.sock' and tk.calls[0][1] == 'b01-suspicion', 'burster: the run\'s own socket, burst/b01-suspicion')
    # a large change in the picture while Link and the camera stood still
    b, tk, side, game = make('change', [(100, 100), (190, 160)], still)
    m = b.poll(side())
    check(m is not None and 'changed by' in m['why'], f'burster: a picture that changed by 60 while nothing moved takes a burst ({m and m["why"]})')
    # the same two pictures while Link walks: motion, not a suspicion; and not a still moment either (no probe)
    b, tk, side, game = make('walk', [(100, 100), (190, 160)], walking)
    check(b.poll(side()) is None and not tk.calls, 'burster: the same change while Link walked is motion (no burst, no probe)')
    # a small change while still is the scene's own life
    b, tk, side, game = make('small', [(100, 100), (190, 108)], still)
    m = b.poll(side())
    check(m is None or m['kind'] == 'probe', 'burster: a change of 8 while still is under burst_diff (no suspicion; a still moment may take a probe)')
    # the same picture twice while Link walked 9 m: frozen
    b, tk, side, game = make('frozen', [(100, 100), (190, 100)], walking)
    m = b.poll(side())
    check(m is not None and 'same picture' in m['why'], f'burster: the same picture while Link walked takes a burst ({m and m["why"]})')
    # before control began nothing is looked at
    b, tk, side, game = make('early', [(100, 1), (190, 1)], still, gameplay=False)
    check(b.poll(side()) is None and not tk.calls, 'burster: no burst before control began')
    # a picture that was seen is not looked at again
    b, tk, side, game = make('twice', [(100, 100), (190, 160)], still)
    b.poll(side())
    n = len(tk.calls)
    now[0] += 100
    b.poll(side())
    check(len(tk.calls) == n or tk.calls[-1][3].startswith('a still moment'), 'burster: the same periodic pictures give no second suspicion')
    # a picture younger than a second may be half written
    pilot, game = live_run(tmp, 'fresh', [(100, 100), (190, 160)], still, sock='/tmp/fake/control.sock')
    tk = Taker()
    b = burst.Burster(game, cfg, taker=tk, clock=time.time)
    m = b.poll(bughunt.Side(pilot, game=game, pilot=pilot))
    check(b.shots() == [] and (m is None or m['kind'] == 'probe'), 'burster: a periodic picture written this second is left for the next poll')
    # the budget: burst_max and burst_gap_s
    b, tk, side, game = make('budget', [(100, 100), (190, 160)], still)
    b.taken = []
    b.last_at = None
    b.poll(side())
    check(len(tk.calls) == 1, 'burster: first suspicion takes a burst')
    for fr, g in ((280, 100), (370, 170)):
        (game / 'shots' / f'vk_{fr:06d}.png').write_bytes(png(g))
    now[0] += 5
    b.last_probe_at = now[0]
    b.poll(side())
    check(len(tk.calls) == 1, 'burster: a second suspicion within burst_gap_s waits')
    now[0] += 40
    for fr, g in ((460, 100), (550, 170)):
        (game / 'shots' / f'vk_{fr:06d}.png').write_bytes(png(g))
    b.poll(side())
    check(len(tk.calls) == 2, 'burster: after burst_gap_s the next suspicion takes one')
    b.taken += [{}] * 5
    now[0] += 100
    for fr, g in ((640, 100), (730, 170)):
        (game / 'shots' / f'vk_{fr:06d}.png').write_bytes(png(g))
    b.poll(side())
    check(len(tk.calls) == 2, 'burster: burst_max bursts a session, no more')
    # a probe at a still moment, and the probe budget
    b, tk, side, game = make('probe', [(100, 100), (190, 102)], still)
    m = b.poll(side())
    check(m is not None and m['kind'] == 'probe' and 'still moment' in m['why'], f'burster: a still moment with nothing suspicious takes a probe ({m and m["why"]})')
    # a probe whose fresh reading shows Link moving takes nothing (the poll's own reading was seconds old)
    b3, tk3, side3, game3 = make('probe-stale', [(100, 100), (190, 102)], still)
    walking_now = lambda: bughunt.Side(game3.parent / 'pilot', game=game3, pilot=game3.parent / 'pilot')   # noqa: E731
    (game3.parent / 'pilot' / 'live' / 'state.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in tb.walking(40, frame0=100)))
    check(b3.poll(side3(), refresh=walking_now) is None and not tk3.calls, 'burster: a probe is not taken when the fresh reading shows Link moving')
    b4, tk4, side4, game4 = make('probe-fresh', [(100, 100), (190, 102)], still)
    m4 = b4.poll(side4(), refresh=side4)
    check(m4 is not None and m4['kind'] == 'probe', 'burster: a probe is taken when the fresh reading is still too')
    now[0] += 31
    check(b.poll(side()) is None, 'burster: the next probe waits burst_probe_every_s')
    now[0] += 61
    m2 = b.poll(side())
    check(m2 is not None and m2['kind'] == 'probe', 'burster: after burst_probe_every_s the second probe')
    now[0] += 200
    check(b.poll(side()) is None, 'burster: burst_probe_max probes a session')
    # a game with no socket in env-used.txt: no more attempts
    pilot, game = live_run(tmp, 'nosock', [(100, 1), (190, 1)], still)
    tk = Taker()
    b = burst.Burster(game, cfg, taker=tk, clock=clock)
    check(b.poll(bughunt.Side(pilot, game=game, pilot=pilot)) is None and b.dead and not tk.calls, 'burster: no socket in env-used.txt: it stops trying')
    # a game that went away: the manifest says so and the burster stops
    pilot, game = live_run(tmp, 'gone', [(100, 1), (190, 1)], still, sock=str(tmp / 'gone.sock'))
    b = burst.Burster(game, cfg, clock=clock)
    m = b.poll(bughunt.Side(pilot, game=game, pilot=pilot))
    check(m is not None and not m['pictures'] and b.dead, 'burster: a burst through a socket nobody serves leaves an error manifest and ends the bursts')


def end_to_end(tmp):
    """the real take() against the fake bridge, then the detector over what it left: A B A B flicker found, a steady scene not"""
    for name, pattern, found in (('strobe', (100, 180, 100, 180, 100, 180, 100, 180), 'error'), ('steady', (100, 100, 100, 100), None), ('once', (100, 180, 100, 100, 100, 100, 100, 100), 'warning')):
        sockp = tmp / f'e-{name}.sock'
        b = FakeBridge(sockp, pattern=pattern, present0=1000, step=3)
        b.start()
        pilot, game = live_run(tmp, f'e-{name}', [(100, 100)], tb.steady(60, frame0=900), sock=sockp)
        m = burst.take(sockp, game / 'burst' / 'b01-probe', n=8, why='a still moment (probe)')
        b.close()
        side = bughunt.Side(pilot, game=game, pilot=pilot)
        check(len(side.bursts) == 1 and len(side.bursts[0][2]) == 8 and side.bursts[0][1] == 'a still moment (probe)', f'end to end {name}: the side reads the burst and why it was taken')
        r = bughunt.detect_visual(side, bughunt.Config())
        fl = [f for f in r.findings if f.sub == 'flicker']
        check((fl[0].severity if fl else None) == found, f'end to end {name}: flicker finding {found} (got {[f.severity for f in fl]})')
        if fl:
            check(fl[0].evidence['burst'] == 'b01-probe' and len(fl[0].evidence['pictures']) == 3 and fl[0].evidence['why'].startswith('a still moment'), f'end to end {name}: the finding names its burst, the three pictures and why it was taken')
        check(r.looked >= 8, f'end to end {name}: the detector counts the burst pictures it looked at ({r.looked})')


def run_in(tmp):
    take_checks(tmp)
    burster_checks(tmp)
    end_to_end(tmp)


def run():
    with tempfile.TemporaryDirectory(prefix='test-burst-') as t:
        run_in(Path(t))


def main():
    run()
    if FAILS:
        raise SystemExit(f'test_burst: {len(FAILS)} of {CHECKS[0]} checks FAILED')
    print(f'test_burst: all {CHECKS[0]} checks passed')


if __name__ == '__main__':
    main()
