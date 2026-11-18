#!/usr/bin/env python3
"""Bursts: consecutive pictures of a running game, asked through its own control bridge, for the flicker check.

A flicker (the picture alternating A B A while nothing moves) cannot be seen in the every-90-presents pictures a run takes: they are a
second and a half apart. The bridge's `shot` is a PNG of the first present after the request; the renderer takes one shot at a time but keeps a
queue (16), so n requests sent at once come back as n pictures of presents a few apart, the gap `bughunt.Config.flicker_gap` is made for.

    burst.py take SOCKET DEST [--n 8] [--why TEXT]     one burst by hand (a game this user started, through its own socket)

`Burster` is what the hunt's watcher runs on each poll of a solo session: it looks at the newest periodic picture with the cheap checks of the
visual detector (`bughunt.suspect_picture`) and takes a burst when one is suspicious; and, at a quiet moment (Link and the camera still), a
probe burst now and then, so the false-positive rate of the flicker check is read from bursts that nobody suspected. Bursts are budgeted
(`burst_max`, `burst_gap_s`, `burst_probe_*`). The socket is the run's own: HOS_CONTROL in the game run's env-used.txt. Nothing here sends an
input, changes a setting or touches the game but through `shot`. Standard library only (the detector side uses bughunt's small pictures).
"""
import json
import os
import re
import socket
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bughunt  # noqa: E402

MAX_ASK = 12            # the renderer queues 16 shots; the bridge answers 'busy' past its own limit
FRESH_S = 1.0           # a periodic picture younger than this may still be being written


def control_socket(game_run):
    """The control socket path of a game run folder (env-used.txt's HOS_CONTROL), or None."""
    try:
        text = (Path(game_run) / 'env-used.txt').read_text(errors='replace')
    except OSError:
        return None
    m = re.search(r'^HOS_CONTROL=(.+)$', text, re.M)
    return m.group(1).strip() if m else None


def take(sock_path, dest, n=8, timeout=12.0, why='', clock=time.monotonic, grace=4.0):
    """n `shot` requests at once on one connection of their own, the pictures renamed vk_<present>.png in dest, a burst.json beside them.
    Returns the manifest {why, n, pictures: [[present, name]], errors: [...], seconds, taken_at}; `pictures` may be fewer than n."""
    n = max(1, min(int(n), MAX_ASK))
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    manifest = {'why': why, 'n': n, 'pictures': [], 'errors': [], 'taken_at': time.strftime('%F %T')}
    t0 = clock()
    paths = {}
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.settimeout(5.0)
        try:
            s.connect(str(sock_path))
        except OSError as e:
            manifest['errors'].append(f'no game answers on the socket ({e.strerror or e})')
            return finish(dest, manifest, t0, clock)
        wire = b''
        for k in range(n):
            rid = k + 1
            paths[rid] = dest / f'b{k:02d}.png'
            wire += (json.dumps({'id': rid, 'cmd': 'shot', 'path': str(paths[rid]), 'timeout': int(timeout)}, separators=(',', ':')) + '\n').encode()
        try:
            s.sendall(wire)
        except OSError as e:
            manifest['errors'].append(f'the socket is gone ({e.strerror or e})')
            return finish(dest, manifest, t0, clock)
        got, buf = {}, b''
        deadline = clock() + timeout + grace
        while len(got) < n:
            left = deadline - clock()
            if left <= 0:
                manifest['errors'].append(f'{n - len(got)} of {n} pictures not answered in {timeout + grace:.0f} s')
                break
            s.settimeout(left)
            try:
                chunk = s.recv(65536)
            except socket.timeout:
                continue
            except OSError as e:
                manifest['errors'].append(f'the socket is gone ({e.strerror or e})')
                break
            if not chunk:
                manifest['errors'].append('the game closed the socket')
                break
            buf += chunk
            while b'\n' in buf:
                line, _, buf = buf.partition(b'\n')
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                if isinstance(msg, dict) and msg.get('id') in paths and 'ok' in msg:
                    got[msg['id']] = msg
    finally:
        s.close()
    for rid, p in paths.items():
        r = got.get(rid)
        if r is None:
            continue
        if not r.get('ok'):
            manifest['errors'].append(f'shot {rid}: {r.get("error")}: {str(r.get("message") or "")[:100]}')
            continue
        present = r.get('present')
        if not isinstance(present, int) or not p.is_file():
            manifest['errors'].append(f'shot {rid}: no present number or no file')
            continue
        final = dest / f'vk_{present:06d}.png'
        if final.exists():
            p.unlink()
            continue
        os.replace(p, final)
        manifest['pictures'].append([present, final.name])
    manifest['pictures'].sort()
    return finish(dest, manifest, t0, clock)


def finish(dest, manifest, t0, clock):
    manifest['seconds'] = round(clock() - t0, 2)
    tmp = Path(dest) / 'burst.json.tmp'
    tmp.write_text(json.dumps(manifest, indent=1) + '\n')
    os.replace(tmp, Path(dest) / 'burst.json')
    return manifest


class Burster:
    """The live side: `poll(side)` after the watcher read the session's live folders; returns the manifest of a burst taken now, or None.
    `taker(sock, dest, n, why)` is `take` (the tests give a fake). `clock` is wall seconds."""

    def __init__(self, game_run, cfg, taker=take, clock=time.time, log=None):
        self.game_run, self.cfg, self.taker, self.clock = Path(game_run), cfg, taker, clock
        self.log = log or (lambda m: None)
        self.seen = -1          # the newest periodic present looked at
        self.prev = None        # (present, path, small, hash) of the one before the newest
        self.taken = []         # manifests
        self.last_at = None     # clock of the last burst
        self.probes = 0
        self.last_probe_at = None
        self.dead = False       # no socket or the game refused: stop trying

    def shots(self):
        d = self.game_run / 'shots'
        if not d.is_dir():
            return []
        out = []
        for p in sorted(d.glob('vk_*.png')):
            m = re.search(r'vk_(\d+)', p.stem)
            if m and int(m.group(1)) > self.seen:
                try:
                    if self.clock() - p.stat().st_mtime < FRESH_S:
                        break
                except OSError:
                    break
                out.append((int(m.group(1)), p))
        return out

    def room(self):
        c = self.cfg
        if self.dead or len(self.taken) >= c.burst_max:
            return False
        return self.last_at is None or self.clock() - self.last_at >= c.burst_gap_s

    def poll(self, side, refresh=None):
        if self.dead:
            return None
        playing = any(e.get('ev') == 'gameplay' for e in side.events)
        if not playing:
            return None
        reason = None
        for fr, p in self.shots()[-3:]:      # (a few at a time: a slow poll catches up without a thumbnail of every picture)
            try:
                small = bughunt.thumb(p)
                cur = (fr, p, small, bughunt.file_hash(p))
            except Exception:   # noqa: BLE001  an unreadable picture is the detector's finding later; here it is just not judged
                self.seen = fr
                continue
            self.seen = fr
            why = bughunt.suspect_picture(side, self.prev, cur, self.cfg)
            self.prev = cur
            reason = reason or why
        if reason and self.room():
            return self.take(reason, 'suspicion')
        if not reason and self.room() and self.probes < self.cfg.burst_probe_max and bughunt.still_now(side, self.cfg) \
                and (self.last_probe_at is None or self.clock() - self.last_probe_at >= self.cfg.burst_probe_every_s) \
                and (refresh is None or bughunt.still_now(refresh(), self.cfg)):   # (the poll's reading is seconds old: Link may have set off since; hold 4's two probes caught him walking, 0 of 12 triplets still)
            self.probes += 1
            self.last_probe_at = self.clock()
            return self.take('a still moment (probe)', 'probe')
        return None

    def take(self, why, kind):
        sock = control_socket(self.game_run)
        if not sock:
            self.dead = True
            self.log('burst: no control socket in env-used.txt: no more bursts')
            return None
        dest = self.game_run / 'burst' / f'b{len(self.taken) + 1:02d}-{kind}'
        m = self.taker(sock, dest, self.cfg.burst_n, why=why)
        m['kind'] = kind
        self.last_at = self.clock()
        self.taken.append(m)
        self.log(f'burst {dest.name}: {len(m["pictures"])} of {m["n"]} pictures in {m["seconds"]} s ({why})' + (f' errors: {m["errors"][:2]}' if m['errors'] else ''))
        if not m['pictures'] and any('no game answers' in e or 'closed' in e or 'gone' in e for e in m['errors']):
            self.dead = True
        return m


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    t = sub.add_parser('take', help='one burst through a game\'s control socket')
    t.add_argument('socket')
    t.add_argument('dest')
    t.add_argument('--n', type=int, default=8)
    t.add_argument('--why', default='by hand')
    a = ap.parse_args(argv)
    m = take(a.socket, a.dest, a.n, why=a.why)
    print(json.dumps(m))
    return 0 if m['pictures'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
