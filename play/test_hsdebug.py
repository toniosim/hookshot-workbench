#!/usr/bin/env python3
"""Game-free checks of hsdebug.py against a simulated game: a fake control bridge on a real Unix socket (status, teleport,
age, options, saves, shots, flag subscription, guest memory, relaunch), a live input file whose `!cheat` lines it reads and
answers in a fake log, and a fake save folder. Every name, number and layout here is made up: nothing of the game.

    python3 -I -B test_hsdebug.py
"""
import contextlib
import io
import json
import math
import os
import socket
import struct
import sys
import tempfile
import threading
import time
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hsdebug  # noqa: E402
import hs_names  # noqa: E402  (hsdebug put the harness folder on sys.path: the game's own log file names come from it)

# ---- a made-up game description: the shapes the real one has, none of its numbers or names
ACTIONS = {'time_base': 500, 'time_hours': 24, 'mark': 7, 'return': 8, 'item_base': 9000, 'item_stride': 100,
           'item_bias': 50, 'item_toggle': 90}
ITEMS = [{'index': 0, 'name': 'Synthetic_Blade', 'label': 'Synthetic Blade', 'kind': 0},
         {'index': 1, 'name': 'Synthetic_Orb', 'label': 'Synthetic Orb', 'kind': 1},
         {'index': 2, 'name': 'Synthetic_Seed', 'label': 'Synthetic Seed', 'kind': 1}]
LAYOUT = {'holder': 0x1000, 'kinds': {'bool': {'at': 0x10, 'stride': 8, 'value': 2}, 'int': {'at': 0x50, 'stride': 16, 'value': 4},
                                      'float': {'at': 0x90, 'stride': 16, 'value': 4}, 'uint': {'at': 0xd0, 'stride': 16, 'value': 4}},
          'box': {'count': 4, 'entries': 8, 'table': 16, 'size': 24}}
INFO = {'schema': 1, 'actions': ACTIONS, 'items': ITEMS, 'layout': LAYOUT,
        'item_flags': {'count': 'Synthetic.{name}.Stock', 'have': 'Synthetic.{name}.Have'},
        'names': {'life': 'synthetic.life', 'rupees': 'synthetic.rupees', 'magic': 'synthetic.magic', 'max_life': 'synthetic.max_life'}}
# Link's actor in the made-up guest memory: position (three floats) at ACTOR_POS, the rotation matrix 12 bytes after it, and a stale copy of
# the position elsewhere (a decoy: only the actor's own field moves the position the bridge reports)
ACTOR_POS, ACTOR_ROT, DECOY = 0x571c, 0x5728, 0x2800
DEST = [{'index': 0, 'child': 'SyntheticFieldYoung', 'adult': 'SyntheticFieldGrown'},
        {'index': 1, 'child': 'SyntheticHallYoung', 'adult': None},
        {'index': 2, 'child': 'SyntheticCave', 'adult': 'SyntheticCave'},
        {'index': 3, 'child': 'SyntheticFieldYoung', 'adult': 'SyntheticFieldGrown'}]   # (a second entrance of the field's maps)


def png(w, h, level):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    rows = b''.join(b'\x00' + bytes([level, level, level]) * w for _ in range(h))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


class Memory:
    """Guest memory laid out as LAYOUT says, holding made-up flags."""

    def __init__(self, flags, size=11):
        self.m = bytearray(0x6000)
        self.size = size
        box = LAYOUT['box']
        self.put(0x1000, 8, 0x2000)
        self.put(0x2000, 8, 0x3000)
        self.addr = {}
        for n, kind in enumerate(('bool', 'int', 'float', 'uint')):
            geom = LAYOUT['kinds'][kind]
            base = 0x3000 + geom['at']
            entries, table = 0x4000 + n * 0x400, 0x5000 + n * 0x100
            rows = flags.get(kind, {})
            self.put(base + box['count'], 4, len(rows))
            self.put(base + box['entries'], 8, entries)
            self.put(base + box['table'], 8, table)
            self.put(base + box['size'], 4, size)
            for i, (name, value) in enumerate(rows.items()):
                h = hsdebug.murmur3(name)
                slot = h % size
                while struct.unpack_from('<I', self.m, table + slot * 8)[0]:
                    slot = (slot + 1) % size
                struct.pack_into('<II', self.m, table + slot * 8, h, i)
                at = entries + i * geom['stride'] + geom['value']
                self.addr[name] = (kind, at)
                self.m[at:at + hsdebug.KIND_WIDTH[kind]] = hsdebug.Debug._pack(kind, value)

    def put(self, at, width, value):
        self.m[at:at + width] = value.to_bytes(width, 'little')

    def get(self, name):
        kind, at = self.addr[name]
        return hsdebug.Debug._unpack(kind, bytes(self.m[at:at + hsdebug.KIND_WIDTH[kind]]))

    def set(self, name, value):
        kind, at = self.addr[name]
        self.m[at:at + hsdebug.KIND_WIDTH[kind]] = hsdebug.Debug._pack(kind, value)


class FakeGame:
    """A control bridge on a Unix socket in a run folder, and the game behind it."""

    def __init__(self, run, mem_level='rw', live=True, hold=()):
        self.run = Path(run)
        self.run.mkdir(parents=True, exist_ok=True)
        self.sock_path = str(Path(tempfile.mkdtemp(prefix='hsd-')) / 'control.sock')
        self.log_path = self.run / hs_names.Names(hs_names.PROJECTS[-1]).log
        self.live_path = self.run / 'live.txt'
        if live:
            self.live_path.write_text('')
        self.log_path.write_text('[hos host] started\n')
        self.save = self.run / 'user' / 'save' / '5a3c0000000000000000000000000001'
        (self.save / 'slot_00').mkdir(parents=True)
        (self.save / 'account.sav').write_bytes(b'account')
        (self.save / 'slot_00' / 'progress.sav').write_bytes(b'map=SyntheticFieldYoung age=child')
        (self.save / 'slot_00' / 'caption.sav').write_bytes(b'x')
        os.utime(self.save / 'slot_00' / 'progress.sav', (time.time() - 5, time.time() - 5))
        (self.run / 'env-used.txt').write_text('HOS_CONTROL=%s\nHOS_INPUT_LIVE=%s\nHOS_HEADLESS=1\n' %
                                               (self.sock_path, self.live_path if live else ''))
        if not live:
            (self.run / 'env-used.txt').write_text('HOS_CONTROL=%s\n' % self.sock_path)
        self.frame, self.t0 = 100, time.monotonic()
        self.map, self.age = 'SyntheticFieldYoung', 'child'
        self.place_supported = True             # the build has the `!place` live command
        self.place_lag, self.stale_pos, self.stale_left = 0, None, 0
        self.pull_to, self.pull_delay, self.pull_armed = None, 0, 0   # the game puts Link back at pull_to once pull_delay status requests have seen him where he was put (a wall, a floor check)
        self.life, self.max_life, self.rupees = 12, 12, 7
        self.event, self.loading = False, 0     # loading: presents left
        self.mem_level, self.state = mem_level, 'play'
        self.last_tp = -99.0
        self.busy_replies = 0                   # refuse the next N map changes: "an event is playing"
        self.hour, self.marked = 12, None
        self.sticky = set()                     # flags the game writes back itself
        self.reload_flags = {}                  # flag -> value the game has again after a restart (what its save holds; a memory edit is not in it)
        self.fade = 0                           # presents the picture stays black after a map change (the scene fades in)
        self.fade_frames = 60
        self.autosave_after = None              # presents after a map change at which the game writes its slot (None: it does not)
        self.autosave_due = None
        self.flags = {'bool': {'synthetic.flag': 0, 'Synthetic.Synthetic_Blade.Have': 0},
                      'int': {'synthetic.life': 12, 'synthetic.max_life': 12, 'synthetic.rupees': 7, 'synthetic.magic': 0,
                              'Synthetic.Synthetic_Orb.Stock': 2, 'Synthetic.Synthetic_Seed.Stock': 5, 'Synthetic.Synthetic_Blade.Stock': 0},
                      'float': {'synthetic.ratio': 1.5}, 'uint': {'synthetic.big': 4000000000}}
        self.mem = Memory(self.flags)
        struct.pack_into('<9f', self.mem.m, ACTOR_ROT, 1, 0, 0, 0, 1, 0, 0, 0, 1)
        struct.pack_into('<3f', self.mem.m, DECOY, 1, 2, 3)
        self.pos = [1, 2, 3]
        self.pending_items = []                 # (frame due, flag, delta): the pickup is an event
        self.commands, self.cheats, self.lock = [], [], threading.RLock()
        self.cap = {'Synthetic_Orb': 10, 'Synthetic_Seed': 99}
        self.stop = False
        self.server = None
        self.relaunched = 0
        self.serve()
        self.watch = threading.Thread(target=self.watch_live, daemon=True)
        self.watch.start()

    # -- the socket
    def serve(self):
        try:
            os.unlink(self.sock_path)
        except OSError:
            pass
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(self.sock_path)
        self.server.listen(8)
        threading.Thread(target=self.accept, args=(self.server,), daemon=True).start()

    def accept(self, server):
        while not self.stop:
            try:
                conn, _ = server.accept()
            except OSError:
                return
            threading.Thread(target=self.client, args=(conn,), daemon=True).start()

    def client(self, conn):
        buf = b''
        sub = None
        try:
            while not self.stop:
                chunk = conn.recv(65536)
                if not chunk:
                    return
                buf += chunk
                while b'\n' in buf:
                    line, _, buf = buf.partition(b'\n')
                    req = json.loads(line)
                    with self.lock:
                        self.commands.append(req)
                        reply, extra = self.handle(req, conn)
                    if reply is not None:
                        conn.sendall((json.dumps(reply) + '\n').encode())
                    for ev in extra:
                        conn.sendall((json.dumps(ev) + '\n').encode())
        except (OSError, ValueError):
            pass
        finally:
            conn.close()

    def log(self, line):
        with open(self.log_path, 'a') as f:
            f.write('[hos host] ' + line + '\n')

    @property
    def pos(self):
        return [round(v, 2) for v in struct.unpack_from('<3f', self.mem.m, ACTOR_POS)]

    @pos.setter
    def pos(self, value):
        struct.pack_into('<3f', self.mem.m, ACTOR_POS, *value)

    @property
    def facing(self):
        m = struct.unpack_from('<9f', self.mem.m, ACTOR_ROT)
        return round(math.degrees(math.atan2(m[2], m[8])) % 360, 1)

    def tick(self, n=1):
        self.frame += n
        if self.loading:
            self.loading = max(0, self.loading - n)
            if not self.loading:
                self.fade = self.fade_frames
                if self.autosave_after is not None:
                    self.autosave_due = self.frame + self.autosave_after
        elif self.fade:
            self.fade = max(0, self.fade - n)
        if self.autosave_due is not None and self.frame >= self.autosave_due and not self.loading:
            self.autosave_due = None
            (self.save / 'slot_00' / 'progress.sav').write_bytes(('map=%s age=%s' % (self.map, self.age)).encode())
        for item in list(self.pending_items):
            if self.frame >= item[0]:
                name, delta = item[1], item[2]
                self.pending_items.remove(item)
                self.mem.set(name, max(0, self.mem.get(name) + delta))
        for name in self.sticky:
            if name == 'synthetic.life':
                self.mem.set(name, self.life)

    def lagged_pos(self):
        if self.stale_left > 0:
            self.stale_left -= 1
            return self.stale_pos
        return self.pos

    def game(self):
        updating = self.state == 'play' and not self.loading
        g = {'frame': self.frame if updating else self.frame - 50, 't': time.monotonic(), 'map': self.map, 'pos': self.lagged_pos(),
             'facing': self.facing, 'camera': 0, 'event': self.event, 'loading': bool(self.loading), 'age': self.age,
             'life': self.mem.get('synthetic.life'), 'max_life': self.mem.get('synthetic.max_life'),
             'rupees': self.mem.get('synthetic.rupees'), 'prompt': 'Empty', 'music': 'x'}
        return g

    def status(self, rid):
        if self.pull_to is not None and self.state == 'play':
            if self.pull_armed > 0:
                self.pull_armed -= 1
            elif self.pos != self.pull_to:
                self.pos = self.pull_to
        return {'id': rid, 'ok': True, 'frame': self.frame, 'protocol': 1, 'state': self.state if not self.loading else 'loading',
                'map': self.map, 'game': self.game(), 'draws': 200.0, 'uptime': time.monotonic() - self.t0,
                'version': 'fake', 'renderer': 'Fake'}

    def err(self, rid, error, message=''):
        return {'id': rid, 'ok': False, 'frame': self.frame, 'error': error, 'message': message}

    def target_map(self, row):
        return row['child'] if self.age == 'child' else row['adult']

    def dest_for(self, to):
        if isinstance(to, int):
            return next((r for r in DEST if r['index'] == to), None)
        return next((r for r in DEST if to.lower() in ((r['child'] or '').lower(), (r['adult'] or '').lower())), None)

    def handle(self, req, conn):
        rid, cmd = req.get('id'), req.get('cmd')
        self.tick(1)
        if cmd == 'status':
            return self.status(rid), []
        if cmd == 'wait':
            ev = req.get('event')
            if ev == 'present':
                self.tick(int(req.get('frames', 1)))
            elif ev in ('map', 'loading_end'):
                self.tick(max(self.loading, 1))
            return {'id': rid, 'ok': True, 'frame': self.frame, 'waited': 1, 'map': self.map}, []
        if cmd == 'teleport':
            if 'to' not in req:
                return {'id': rid, 'ok': True, 'frame': self.frame, 'destinations': DEST}, []
            row = self.dest_for(req['to'])
            if not row:
                return self.err(rid, 'not_found', 'to: a destination'), []
            if not self.target_map(row):
                return self.err(rid, 'refused', 'the game refused the teleport: this destination has no map for the %s' % self.age), []
            if self.busy_replies:
                self.busy_replies -= 1
                return self.err(rid, 'refused', 'the game refused the teleport: an event is playing (a cutscene, a map change\'s)'), []
            if time.monotonic() - self.last_tp < 0.2:
                return self.err(rid, 'refused', 'the game refused the teleport: another teleport is still in progress (one every 8 s)'), []
            self.last_tp = time.monotonic()
            self.map, self.loading = self.target_map(row), 20
            self.log('cheats: teleport %s to %s' % (self.age, self.map))
            return {'id': rid, 'ok': True, 'frame': self.frame, 'teleport': row['index'], 'child': row['child'], 'adult': row['adult'],
                    'sent': True, 'map': self.map, 'accepted': True}, []
        if cmd == 'age':
            if req.get('to') not in ('child', 'adult'):
                return self.err(rid, 'bad_request', 'to: child or adult'), []
            if req['to'] == self.age:
                return {'id': rid, 'ok': True, 'frame': self.frame, 'age': self.age, 'sent': False}, []
            self.age = req['to']
            row = next((r for r in DEST if self.map in (r['child'], r['adult'])), DEST[0])
            self.map, self.loading = (self.target_map(row) or self.map), 20
            return {'id': rid, 'ok': True, 'frame': self.frame, 'age': self.age, 'sent': True, 'map': self.map, 'accepted': True}, []
        if cmd == 'option_get':
            name = req.get('name')
            opts = {'debug_tools': 0, 'damage_taken': 1}
            if name and name not in opts:
                return self.err(rid, 'not_found', 'no such setting'), []
            row = lambda k: {'key': k, 'name': k, 'tab': 'debug', 'value': opts[k], 'min': 0, 'max': 3, 'step': 1, 'restart': False,
                             'fixed': False, 'text': str(opts[k])}
            if name:
                return {'id': rid, 'ok': True, 'frame': self.frame, 'option': row(name)}, []
            return {'id': rid, 'ok': True, 'frame': self.frame, 'options': [row(k) for k in opts]}, []
        if cmd == 'option_set':
            if req.get('name') not in ('debug_tools', 'damage_taken'):
                return self.err(rid, 'not_found', 'no such setting'), []
            v = max(0, min(3, int(req['value'])))
            return {'id': rid, 'ok': True, 'frame': self.frame, 'was': 0,
                    'option': {'key': req['name'], 'value': v, 'min': 0, 'max': 3, 'step': 1, 'fixed': False}}, []
        if cmd == 'saves':
            return {'id': rid, 'ok': True, 'frame': self.frame, 'path': str(self.save), 'account': True, 'option': False,
                    'slots': [{'slot': '00', 'mtime': int(os.stat(self.save / 'slot_00' / 'progress.sav').st_mtime), 'newest': True,
                               'files': [{'name': 'progress.sav', 'size': 3, 'mtime': 1}],
                               'caption': {'scene': 's', 'map': 'SyntheticArea/' + self.age_map_for_caption()}}]}, []
        if cmd == 'shot':
            level = 0 if self.fade else 200 if 6 <= self.hour < 19 else 30
            path = req.get('path') or str(self.run / 'shot.png')
            Path(path).write_bytes(png(16, 16, level))
            return {'id': rid, 'ok': True, 'frame': self.frame, 'present': self.frame, 'path': path, 'width': 16, 'height': 16}, []
        if cmd in ('press', 'stick', 'sequence'):
            if cmd == 'press' and req.get('buttons') == 'A' and self.state == 'menu':
                self.state_presses += 1
                if self.state_presses >= 2:
                    self.boot_from_save()
            return {'id': rid, 'ok': True, 'frame': self.frame, 'start': self.frame, 'end': self.frame + int(req.get('frames', 8))}, []
        if cmd == 'release':
            return {'id': rid, 'ok': True, 'frame': self.frame, 'released': 0, 'all': False}, []
        if cmd == 'subscribe':
            flags = req.get('flags') or []
            ack = {'id': rid, 'ok': True, 'frame': self.frame, 'events': req.get('events'), 'every': req.get('every')}
            conn.sendall((json.dumps(ack) + '\n').encode())
            game = self.game()
            game['flags'] = {n: self.flag_by_name(n) for n in flags}
            return None, [{'event': 'oot', 'sub': rid, 'frame': self.frame, 'game': game}]
        if cmd == 'unsubscribe':
            return {'id': rid, 'ok': True, 'frame': self.frame}, []
        if cmd in ('mem_read', 'mem_read_many', 'mem_write'):
            return self.memory(rid, cmd, req), []
        if cmd == 'relaunch':
            threading.Thread(target=self.restart, daemon=True).start()
            return {'id': rid, 'ok': True, 'frame': self.frame, 'relaunching': True}, []
        if cmd == 'coop_save':
            return self.err(rid, 'unknown_cmd', 'no command coop_save'), []
        return self.err(rid, 'unknown_cmd', 'no command %s' % cmd), []

    state_presses = 0

    def age_map_for_caption(self):
        return (self.save / 'slot_00' / 'progress.sav').read_bytes().decode().split()[0].split('=')[1]

    def flag_by_name(self, name):
        if name.startswith('0x'):
            for n in self.mem.addr:
                if '0x%08x' % hsdebug.murmur3(n) == name.lower():
                    return self.mem.get(n)
            return None
        return self.mem.get(name) if name in self.mem.addr else None

    def memory(self, rid, cmd, req):
        if self.mem_level == 'off':
            return self.err(rid, 'forbidden', 'guest memory is off (HOS_CONTROL_MEM)')
        if cmd == 'mem_write' and self.mem_level != 'rw':
            return self.err(rid, 'forbidden', 'writes are off (HOS_CONTROL_MEM=ro)')

        def span(addr, size):
            if isinstance(addr, str):
                addr = int(addr, 0)
            if addr < 0 or addr + size > len(self.mem.m):
                return None
            return addr
        if cmd == 'mem_read':
            a = span(req.get('addr', 0), req.get('size', 0))
            if a is None:
                return self.err(rid, 'out_of_range', 'outside mapped guest memory')
            return {'id': rid, 'ok': True, 'frame': self.frame, 'data': bytes(self.mem.m[a:a + req['size']]).hex()}
        if cmd == 'mem_write':
            a = span(req.get('addr', 0), len(req.get('hex', '')) // 2)
            if a is None or not req.get('hex'):
                return self.err(rid, 'out_of_range' if a is None else 'bad_request', 'bad write')
            data = bytes.fromhex(req['hex'])
            self.mem.m[a:a + len(data)] = data
            if a == ACTOR_POS:
                self.pull_armed = self.pull_delay
            for name in self.sticky:   # (the game writes it back at once)
                if name in self.mem.addr and self.mem.addr[name][1] <= a < self.mem.addr[name][1] + 4:
                    self.mem.set(name, self.life)
            return {'id': rid, 'ok': True, 'frame': self.frame, 'wrote': len(data), 'addr': a}
        return self.err(rid, 'bad_request', 'unsupported here')

    # -- the Debug tab through the live input file
    def watch_live(self):
        offset = 0
        while not self.stop:
            time.sleep(0.01)
            try:
                with open(self.live_path, 'rb') as f:
                    f.seek(offset)
                    data = f.read()
            except OSError:
                continue
            while b'\n' in data:
                line, _, data = data.partition(b'\n')
                offset += len(line) + 1
                if line.startswith(b'!cheat '):
                    with self.lock:
                        self.cheat(int(line[7:]))
                elif line.startswith(b'!place ') and self.place_supported:
                    with self.lock:
                        self.place([float(v) for v in line[7:].split()])

    def place(self, xyz):
        """The host's `!place X Y Z` (a command only a patched build has): the return-to-mark path with the asked position as the mark."""
        if not (self.state == 'play' and not self.loading) or len(xyz) != 3:
            return
        if self.place_lag:   # (the bridge's status is the last snapshot, taken at Link's previous update: it still shows where he was)
            self.stale_pos, self.stale_left = list(self.pos), self.place_lag
        self.pos = xyz
        self.pull_armed = self.pull_delay
        self.log('cheats: returned to %.2f %.2f %.2f' % tuple(xyz))

    def cheat(self, n):
        self.cheats.append(n)
        if not (self.state == 'play' and not self.loading):
            return
        a = ACTIONS
        if a['time_base'] <= n < a['time_base'] + a['time_hours']:
            self.hour = n - a['time_base']
            self.log('cheats: requested %02d:00' % self.hour)
        elif n == a['mark']:
            self.marked = list(self.pos)
            self.log('cheats: marked position %.2f %.2f %.2f' % tuple(self.pos))
        elif n == a['return']:
            if self.marked is None:
                self.log('cheats: no mark for this player controller')
            else:
                self.pos = list(self.marked)
                self.log('cheats: returned to %.2f %.2f %.2f' % tuple(self.marked))
        elif n >= a['item_base']:
            index, op = divmod(n - a['item_base'], a['item_stride'])
            if index >= len(ITEMS):
                return
            item = ITEMS[index]
            if op == a['item_toggle']:
                # a pouch item: its count is the truth; the IsGet flag is set when it is got and the game never clears it again
                stock = 'Synthetic.%s.Stock' % item['name']
                have = self.mem.get(stock)
                self.pending_items.append((self.frame + 3, stock, 1 if not have else -have))
                if not have:
                    self.mem.set('Synthetic.%s.Have' % item['name'], 1)
                self.log('cheats: inventory %s %+d (had %d, now %d, event status 2)' % (item['name'], 1 if not have else -have, have, have))
                return
            delta = op - a['item_bias']
            name = 'Synthetic.%s.Stock' % item['name']
            have = self.mem.get(name)
            room = self.cap.get(item['name'], 99) - have
            real = max(min(delta, room), -have)
            self.pending_items.append((self.frame + 3, name, real))
            self.log('cheats: inventory %s %+d (had %d, now %d, event status 2)' % (item['name'], delta, have, have))

    # -- the game started again
    def restart(self):
        time.sleep(0.1)
        self.server.close()
        self.state, self.state_presses, self.map = 'menu', 0, None
        self.t0 = time.monotonic()
        time.sleep(0.2)
        self.relaunched += 1
        for name, value in self.reload_flags.items():
            self.mem.set(name, value)
        self.serve()

    def boot_from_save(self):
        text = (self.save / 'slot_00' / 'progress.sav').read_bytes().decode()
        kv = dict(p.split('=') for p in text.split())
        self.state, self.map, self.age, self.loading = 'play', kv['map'], kv['age'], 10

    def close(self):
        self.stop = True
        try:
            self.server.close()
        except OSError:
            pass


@contextlib.contextmanager
def game(**kw):
    with tempfile.TemporaryDirectory(prefix='hsdebug-test-') as tmp:
        g = FakeGame(Path(tmp) / 'run', **kw)
        try:
            yield g, Path(tmp)
        finally:
            g.close()


def attach(g, info=True, **kw):
    return hsdebug.attach(run=str(g.run), info=hsdebug.GameInfo(INFO) if info else None, ready_timeout=5, **kw)


def raises(code, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except hsdebug.DebugError as e:
        assert e.code == code, (e.code, e.message)
        return e
    raise AssertionError('expected DebugError %s' % code)


# ---------------------------------------------------------------- checks

def murmur_checks():
    assert hsdebug.murmur3('') == 0
    assert hsdebug.murmur3('test') == 0xba6bd213
    assert hsdebug.murmur3('Hello, world!') == 0xc0363e43
    assert hsdebug.murmur3(b'The quick brown fox jumps over the lazy dog') == 0x2e4ff723


def info_checks():
    info = hsdebug.GameInfo(INFO)
    assert info.item('Synthetic_Orb')['index'] == 1 and info.item('synthetic blade')['kind'] == 0 and info.item('2')['name'] == 'Synthetic_Seed'
    raises('bad_request', info.item, 'Nothing')
    for bad in ({'schema': 2}, dict(INFO, extra=1), dict(INFO, actions={'time_base': 1}),
                dict(INFO, items=[{'index': 0, 'name': 'x', 'label': 'x', 'kind': 5}]),
                dict(INFO, layout={'holder': 1, 'kinds': {'bogus': {}}, 'box': {}})):
        raises('bad_request', hsdebug.GameInfo, bad)
    assert info.flag_name('life') == 'synthetic.life' and info.flag_name('other.flag') == 'other.flag'


def status_checks():
    with game(live=True) as (g, _):
        d = attach(g)
        st = d.status()
        assert st['map'] == 'SyntheticFieldYoung' and st['age'] == 'child' and st['fresh'] and hsdebug.ready(st)
        assert st['pos'] == [1, 2, 3] and st['life'] == 12 and st['rupees'] == 7
        g.loading = 50
        assert not hsdebug.ready(d.status())
        g.loading = 0
        g.state = 'menu'
        stale = d.status()
        assert stale['state'] == 'menu' and not hsdebug.ready(stale)
        d.close()


def teleport_checks():
    with game() as (g, _):
        d = attach(g)
        assert [r['index'] for r in d.destinations()] == [0, 1, 2, 3]
        r = d.teleport('SyntheticHallYoung')
        assert r['ok'] and r['effect'] == 'verified' and r['after']['map'] == 'SyntheticHallYoung' and r['before']['map'] == 'SyntheticFieldYoung'
        assert r['destination']['index'] == 1 and r['sent'] is True
        # by index, to the child's map of a destination; the cool-down refusal is waited out
        r = d.teleport(2)
        assert r['ok'] and r['after']['map'] == 'SyntheticCave'
        # a map that is the one Link stands in is a reload
        time.sleep(0.25)
        r = d.teleport('SyntheticCave')
        assert r['ok'] and r['reload'] is True
        # busy: an event playing is asked again
        time.sleep(0.25)
        g.busy_replies = 2
        r = d.teleport(0)
        assert r['ok'] and r['after']['map'] == 'SyntheticFieldYoung' and r['same_map_destinations'] == [3] and r['moved_m'] == 0.0
        assert sum(1 for c in g.commands if c['cmd'] == 'teleport' and 'to' in c) >= 6
        # no map for this age: refused before asking the game, naming the ages that have one
        d.age('adult')
        e = raises('refused', d.teleport, 'SyntheticHallYoung')
        assert 'has no map for the adult' in e.message and e.data['destination']['index'] == 1
        raises('bad_request', d.teleport, 'Nowhere')
        raises('bad_request', d.teleport, 99)
        d.close()


def age_checks():
    with game() as (g, _):
        d = attach(g)
        r = d.age('adult')
        assert r['ok'] and r['effect'] == 'verified' and r['after']['age'] == 'adult' and r['after']['map'] == 'SyntheticFieldGrown'
        r = d.age('adult')
        assert r['ok'] and r['sent'] is False and 'already' in r['note']
        raises('bad_request', d.age, 'elder')
        d.close()


def guard_checks():
    with game() as (g, tmp):
        # a socket alone, no scratch: nothing that changes the game
        d = hsdebug.Debug(g.sock_path, live=g.live_path, log=g.log_path, info=hsdebug.GameInfo(INFO))
        for fn, args in ((d.teleport, (0,)), (d.age, ('adult',)), (d.time, (3,)), (d.give, ('Synthetic_Orb', 1)),
                         (d.flag_set, ('synthetic.flag', 1)), (d.option_set, ('debug_tools', 1))):
            e = raises('not_disposable', fn, *args)
            assert 'throw-away' in e.message
        assert not any(c['cmd'] in ('teleport', 'age', 'option_set', 'mem_write') and (c['cmd'] != 'teleport' or 'to' in c) for c in g.commands)
        assert not g.cheats
        # a scratch root that is not the game's folder
        d2 = hsdebug.Debug(g.sock_path, live=g.live_path, log=g.log_path, scratch=[str(tmp / 'elsewhere')])
        e = raises('not_disposable', d2.time, 3)
        assert 'is not inside' in e.message
        # the game's folder inside the scratch root: allowed
        d3 = hsdebug.Debug(g.sock_path, live=g.live_path, log=g.log_path, scratch=[str(tmp)], info=hsdebug.GameInfo(INFO))
        assert d3.time(4)['ok']
        # a symlink that points the run folder somewhere else does not prove anything
        d4 = hsdebug.Debug(g.sock_path, live=g.live_path, log=g.log_path, root=str(tmp / 'run' / 'user'))
        assert d4.disposable()['verified']
        d4b = hsdebug.Debug(g.sock_path, live=g.live_path, log=g.log_path, root=str(tmp / 'run' / 'user' / 'save' / 'other'))
        assert not d4b.disposable()['verified']
        for x in (d, d2, d3, d4, d4b):
            x.close()
    # saves not opened yet: unknown, and refused with that said
    with game() as (g, _):
        d = attach(g)
        orig = g.handle

        def no_saves(req, conn):
            if req.get('cmd') == 'saves':
                return g.err(req['id'], 'unavailable', 'the game has not opened its saves'), []
            return orig(req, conn)
        g.handle = no_saves
        e = raises('not_disposable', d.time, 3)
        assert 'not opened its saves' in e.message
        d.close()


def time_checks():
    with game() as (g, tmp):
        d = attach(g)
        r = d.time(22)
        assert r['ok'] and r['effect'] == 'requested' and g.hour == 22 and r['game_said'] == ['[hos host] cheats: requested 22:00']
        assert g.cheats == [ACTIONS['time_base'] + 22]
        d.time(12)
        r = d.time(3, look=True)
        assert r['effect'] == 'requested' and r['luma'][0] > r['luma'][1], r   # (noon, then night: darker)
        raises('bad_request', d.time, 24)
        raises('bad_request', d.time, -1)
        raises('bad_request', d.time, True)
        assert g.cheats == [ACTIONS['time_base'] + 22, ACTIONS['time_base'] + 12, ACTIONS['time_base'] + 3]
        # not in control: the line is not written at all
        g.loading = 10 ** 9
        raises('unavailable', hsdebug.attach(run=str(g.run), info=hsdebug.GameInfo(INFO), ready_timeout=0.3).time, 5)
        assert len(g.cheats) == 3
        g.loading = 0
        d.close()
    # no live file in the run
    with game(live=False) as (g, _):
        d = attach(g)
        e = raises('unavailable', d.time, 5)
        assert 'HOS_INPUT_LIVE' in e.message
        d.close()
    # a line the game never answers
    with game() as (g, _):
        d = attach(g)
        g.log = lambda line: None
        r = d.time(5)
        assert r['effect'] == 'unconfirmed' and not r['ok'] and 'keeps the line' in r['note']
        d.close()


def item_checks():
    with game() as (g, _):
        d = attach(g)
        r = d.give('Synthetic Orb', 3)
        assert r['ok'] and r['effect'] == 'verified' and r['count_before'] == 2 and r['count_after'] == 5, r
        assert r['had'] == 2 and 'inventory Synthetic_Orb +3' in r['game_said'][0]
        assert g.cheats[-1] == 9000 + 1 * 100 + 50 + 3
        r = d.give('Synthetic_Orb', -4)
        assert r['effect'] == 'partial' or r['effect'] == 'verified'
        assert r['count_after'] == 1 and r['effect'] == 'verified', r
        # capacity: more than the pouch holds is partial
        r = d.give('Synthetic_Orb', 20)
        assert r['effect'] == 'partial' and r['ok'] and r['count_after'] == 10, r
        # at the capacity already: nothing moves, and the result says why that may be
        r = d.give('Synthetic_Orb', 1)
        assert r['effect'] == 'not_applied' and not r['ok'] and 'capacity' in r['note'] and 'upgrade' in r['note'] and 'fills its pouch' in r['note'], r
        # removing what is not there changes nothing
        r = d.give('Synthetic_Seed', -50)
        assert r['effect'] == 'partial' and r['count_after'] == 0, r
        r = d.give('Synthetic_Seed', -1)
        assert r['effect'] == 'not_applied' and not r['ok'], r
        # a have/lack item
        r = d.toggle('Synthetic_Blade')
        assert r['ok'] and r['effect'] == 'verified' and r['have_before'] == 0 and r['have_after'] == 1, r
        assert g.cheats[-1] == 9000 + 0 * 100 + 90
        r = d.toggle('Synthetic_Blade')
        assert r['ok'] and r['have_after'] == 0
        # kinds and ranges
        raises('bad_request', d.give, 'Synthetic_Blade', 1)
        raises('bad_request', d.give, 'Synthetic_Orb', 0)
        raises('bad_request', d.give, 'Synthetic_Orb', 78)
        raises('bad_request', d.give, 'Synthetic_Orb', -51)
        raises('bad_request', d.give, 'Nothing', 1)
        n = len(g.cheats)
        raises('bad_request', d.give, 'Synthetic_Orb', 100)
        assert len(g.cheats) == n
        # without a game info: unavailable
        d2 = attach(g, info=False)
        raises('unavailable', d2.give, 'Synthetic_Orb', 1)
        d.close(), d2.close()
    # no count flag configured: the game's own line is all there is
    with game() as (g, _):
        bare = dict(INFO)
        del bare['item_flags']
        d = hsdebug.attach(run=str(g.run), info=hsdebug.GameInfo(bare), ready_timeout=5)
        r = d.give('Synthetic_Orb', 2)
        assert r['effect'] == 'requested' and r['ok'] and r['had'] == 2 and 'no count flag' in r['note'], r
        d.close()


def mark_checks():
    with game() as (g, _):
        d = attach(g)
        r = raises('unavailable', lambda: None) if False else None
        r = d.return_to_mark()
        assert not r['ok'] and r['effect'] == 'not_applied' and 'no mark' in ' '.join(r['game_said'])
        r = d.mark()
        assert r['ok'] and r['marked'] == [1, 2, 3] and r['effect'] == 'requested'
        g.pos = [40, 2, -9]
        r = d.return_to_mark()
        assert r['ok'] and r['effect'] == 'verified' and r['distance'] == 0.0 and r['after']['pos'] == [1, 2, 3]
        d.close()


def flag_checks():
    with game() as (g, _):
        d = attach(g)
        r = d.flag_get('synthetic.flag', 'synthetic.life', 'unknown.flag', '0x%08x' % hsdebug.murmur3('synthetic.ratio'))
        assert r['flags'] == {'synthetic.flag': 0, 'synthetic.life': 12, 'unknown.flag': None, '0x%08x' % hsdebug.murmur3('synthetic.ratio'): 1.5}, r
        assert d.flag_get('life')['flags'] == {'synthetic.life': 12}   # (an alias)
        raises('bad_request', d.flag_get, 'bad name!')
        raises('bad_request', d.flag_get)
        # every kind written and read back
        for name, kind, value in (('synthetic.flag', 'bool', 1), ('synthetic.rupees', 'int', 99), ('synthetic.ratio', 'float', 2.5),
                                  ('synthetic.big', 'uint', 123456789)):
            r = d.flag_set(name, value)
            assert r['ok'] and r['effect'] == 'verified' and r['kind'] == kind and r['written'] == value and r['after_flag'] == value, r
            assert r['hash'] == '0x%08x' % hsdebug.murmur3(name)
        assert g.mem.get('synthetic.rupees') == 99 and g.mem.get('synthetic.big') == 123456789
        r = d.flag_set('synthetic.rupees', -3, kind='int')
        assert r['after_flag'] == -3 and r['before'] == 99
        # by hash, by alias
        r = d.flag_set('0x%08x' % hsdebug.murmur3('synthetic.flag'), 0)
        assert r['ok'] and g.mem.get('synthetic.flag') == 0
        r = d.set_state(rupees=5)[0]
        assert r['ok'] and r['state']['rupees'] == 5 and g.mem.get('synthetic.rupees') == 5
        # absent, wrong kind, no alias
        e = raises('bad_request', d.flag_set, 'absent.flag', 1)
        assert 'no flag absent.flag' in e.message
        raises('bad_request', d.flag_set, 'synthetic.rupees', 1, kind='bool')
        e = raises('bad_request', d.flag_set, 'synthetic.rupees', 2 ** 40)
        assert 'does not fit a int flag' in e.message and g.mem.get('synthetic.rupees') == 5
        raises('bad_request', d.set_state, nothing=1)
        # a value the game writes back is not applied, and says so
        g.sticky.add('synthetic.life')
        g.life = 12
        r = d.flag_set('synthetic.life', 3)
        assert not r['ok'] and r['effect'] == 'not_applied' and r['after_flag'] == 12 and 'game writes it itself' in r['note'], r
        d.close()
    # memory off: forbidden, with what to do
    with game(mem_level='off') as (g, _):
        d = attach(g)
        e = raises('forbidden', d.flag_set, 'synthetic.flag', 1)
        assert 'HOS_CONTROL_MEM=rw' in e.message
        assert d.flag_get('synthetic.flag')['flags'] == {'synthetic.flag': 0}    # (reads need no memory opt-in)
        d.close()
    with game(mem_level='ro') as (g, _):
        d = attach(g)
        e = raises('forbidden', d.flag_set, 'synthetic.flag', 1)
        assert 'mem_write' in e.message
        assert g.mem.get('synthetic.flag') == 0
        d.close()
    # a table that cannot be right is not walked
    with game() as (g, _):
        d = attach(g)
        g.mem.put(0x3000 + LAYOUT['kinds']['bool']['at'] + LAYOUT['box']['size'], 4, 1 << 23)
        e = raises('bad_request', d.flag_set, 'synthetic.flag', 1, kind='bool')
        d.close()


def option_checks():
    with game() as (g, _):
        d = attach(g)
        r = d.option_get('debug_tools')
        assert r['option']['value'] == 0
        r = d.option_set('debug_tools', 'true')
        assert r['ok'] and r['effect'] == 'verified' and r['option']['value'] == 1, r
        r = d.option_set('damage_taken', '9')
        assert not r['ok'] and r['effect'] == 'not_applied' and r['option']['value'] == 3   # (cut to the row's range)
        raises('bad_request', d.option_set, 'nothing', 1)
        d.close()


def shot_and_input_checks():
    with game() as (g, tmp):
        d = attach(g)
        r = d.shot(str(tmp / 'a.png'))
        assert r['ok'] and r['width'] == 16 and r['luma'] == 200.0, r
        assert hsdebug.png_luma(str(tmp / 'a.png')) == 200.0
        (tmp / 'bad.png').write_bytes(b'not a png')
        assert hsdebug.png_luma(str(tmp / 'bad.png')) is None and hsdebug.png_luma(str(tmp / 'missing.png')) is None
        assert d.press('A', 4)['effect'] == 'requested'
        assert d.stick(0, 1, 4)['ok']
        assert d.release()['released'] == 0
        d.close()


def capabilities_checks():
    with game() as (g, _):
        d = attach(g)
        r = d.capabilities()
        assert r['ok'] and r['bridge']['memory'] == 'rw' and r['bridge']['teleport'] and r['bridge']['age'] and r['bridge']['saves']
        assert r['bridge']['coop_save'] is False and r['debug_tools_option'] == 0
        assert r['live_input']['present'] and r['game_info'] == {'loaded': True, 'items': 3, 'layout': True,
                                                                 'aliases': ['life', 'magic', 'max_life', 'rupees']}
        assert r['disposable']['verified']
        d.close()
    for level in ('ro', 'off'):
        with game(mem_level=level) as (g, _):
            d = attach(g)
            assert d.capabilities()['bridge']['memory'] == level
            d.close()


def snapshot_checks():
    with game() as (g, tmp):
        d = attach(g)
        out = tmp / 'snap'
        r = d.snapshot(str(out))
        assert r['ok'] and r['effect'] == 'verified' and r['files'] == 3 and r['caption_matches_map'] is True and r['state']['map'] == 'SyntheticFieldYoung', r
        doc = json.loads((out / 'snapshot.json').read_text())
        assert doc['user_id'] == '5a3c0000000000000000000000000001' and len(doc['files']) == 3
        assert (out / 'save' / doc['user_id'] / 'slot_00' / 'progress.sav').read_bytes() == b'map=SyntheticFieldYoung age=child'
        # a caption that names another map than Link is in is said
        g.map = 'SyntheticCave'
        r = d.snapshot(str(tmp / 'snap2'))
        assert r['caption_matches_map'] is False and r['effect'] == 'partial' and r['ok'] and 'not saved' in r['note'], r
        # never into something that is there
        raises('refused', d.snapshot, str(out))
        # a link in the save folder is not followed
        os.symlink('/etc/hostname', g.save / 'slot_00' / 'evil.sav')
        raises('refused', d.snapshot, str(tmp / 'snap3'))
        os.unlink(g.save / 'slot_00' / 'evil.sav')
        # restore into a scratch folder: files equal their hashes
        r = hsdebug.restore(str(out), into=str(tmp / 'scratch'))
        assert r['ok'] and r['effect'] == 'verified' and r['files'] == 3
        assert (tmp / 'scratch' / 'save' / doc['user_id'] / 'account.sav').read_bytes() == b'account'
        raises('refused', hsdebug.restore, str(out), into=str(tmp / 'scratch'))
        raises('bad_request', hsdebug.restore, str(out))
        raises('bad_request', hsdebug.restore, str(tmp / 'nothing'), into=str(tmp / 's2'))
        # a damaged snapshot is not restored
        (out / 'save' / doc['user_id'] / 'account.sav').write_bytes(b'tampered')
        e = raises('failed', hsdebug.restore, str(out), into=str(tmp / 's3'))
        assert 'damaged' in e.message and not (tmp / 's3').exists()
        d.close()


def restore_relaunch_checks():
    with game() as (g, tmp):
        d = attach(g)
        out = tmp / 'snap'
        d.snapshot(str(out))
        d.teleport('SyntheticCave')            # (the game is somewhere else, and saved there: the slot says so)
        (g.save / 'slot_00' / 'progress.sav').write_bytes(b'map=SyntheticCave age=child')
        g.t0 -= 100   # (a game that has run a while, as a real one has)
        r = d.restore(str(out), relaunch=True)
        assert r['ok'] and r['effect'] == 'verified' and r['relaunched'] and r['after']['map'] == 'SyntheticFieldYoung', r
        assert g.relaunched == 1
        assert (g.save / 'slot_00' / 'progress.sav').read_bytes() == b'map=SyntheticFieldYoung age=child'
        d.close()
    # an attached game that is not a throw-away one: not touched
    with game() as (g, tmp):
        d = attach(g)
        d.snapshot(str(tmp / 'snap'))
        loose = hsdebug.Debug(g.sock_path, live=g.live_path, log=g.log_path)
        before = (g.save / 'slot_00' / 'progress.sav').read_bytes()
        raises('not_disposable', hsdebug.restore, str(tmp / 'snap'), debug=loose)
        assert (g.save / 'slot_00' / 'progress.sav').read_bytes() == before and g.relaunched == 0
        d.close(), loose.close()


def setup_checks():
    with game() as (g, _):
        d = attach(g)
        r = d.setup(to='SyntheticFieldGrown', hour=22, give={'Synthetic_Orb': 3}, toggle=['Synthetic_Blade'],
                    flags={'synthetic.flag': 1}, life=9, rupees=50)
        assert r['ok'], r
        names = [s['action'] for s in r['steps']]
        assert names == ['age', 'teleport', 'time', 'toggle', 'give', 'flag_set', 'flag_set', 'flag_set'], names   # (an upgrade first: a pouch has room only once Link has it)
        assert r['state']['age'] == 'adult' and r['state']['map'] == 'SyntheticFieldGrown' and g.hour == 22
        assert g.mem.get('synthetic.rupees') == 50 and g.mem.get('synthetic.life') == 9 and g.mem.get('synthetic.flag') == 1
        # stops at the first step that fails
        g.busy_replies = 0
        r = d.setup(to='SyntheticHallYoung', age='adult', hour=5)
        assert not r['ok'] and r['steps'][-1]['error'] == 'refused' and g.hour == 22
        assert [s['action'] for s in r['steps']] == ['age', 'teleport']
        # keep going past it
        r = d.setup(to='SyntheticHallYoung', age='adult', hour=5, keep_going=True)
        assert g.hour == 5 and not r['ok']
        d.close()


def source_checks():
    """game-info from a made-up checkout laid out as the game's source is."""
    with tempfile.TemporaryDirectory(prefix='hsdebug-src-') as tmp:
        root = Path(tmp)
        (root / 'host').mkdir()
        (root / 'gpu' / 'vk').mkdir(parents=True)
        header = ('#ifndef OOT_CHEAT_ITEMS\n#define SYNTH_BLADE "Synthetic_Blade"\n'
                  '#define OOT_CHEAT_ITEMS(OOT_SECTION, OOT_ITEM) \\\n    OOT_SECTION("A") \\\n'
                  '    OOT_ITEM("Synthetic Blade", SYNTH_BLADE, 0) \\\n    OOT_ITEM("Synthetic \\"Orb\\"", "Synthetic_Orb", 1)\n#endif\n'
                  '#define OOT_CHEAT_ITEM_ACTION 9000 /* + item * 256 */\n')
        (root / 'gpu/vk/oot_cheat_items.h').write_text(header)
        main = '''#define OOT_AGE_ACTION 998
#define OOT_TELEPORT_ACTION 1111
static void oot_inventory_edit(Ctx *c, int action) {
    const unsigned item = (unsigned)(action - OOT_CHEAT_ITEM_ACTION) / 100, op = (unsigned)(action - OOT_CHEAT_ITEM_ACTION) % 100;
    if (op == 90) delta = have > 0 ? -have : 1;   /* unlock / relock */
    else if (op < 128) delta = (int)op - 50;
}
static void oot_update_player_cheats(void) {
    } else if (action >= 500 && action < 524) {
        oot_set_time(c, action - 500);
    }
    if (action == 7) {
        for (unsigned i = 0; i < 3; i++) {
            const uint32_t bits = recomp_load32(c, actor + 796 + i * 4);
        }
    }
    const int returning = action == 8 && marked_controller == controller;
}
'''
        (root / 'host/hos_main.c').write_text(main)
        (root / 'host/oot_state_tap.c').write_text('''#define STATE_GAMEDATA_SLOT 0x1000ULL   /* x */
enum { KIND_BOOL, KIND_INT, KIND_FLOAT, KIND_ENUM, KIND_TEXT, KIND_UINT, KINDS };
static const struct { uint32_t at, stride, value; } state_kind[KINDS] = {
    {0x010, 0x8, 0x2}, {0x050, 0x10, 0x4}, {0x090, 0x10, 0x4}, {0x0d0, 0x20, 0x4}, {0x110, 0x100, 0x60}, {0x150, 0x10, 0x4}};
    const uint64_t box = mgr + state_kind[kind].at, entries = state_u64(box + 8), table = state_u64(box + 16);
    const uint32_t count = state_u32(box + 4), size = state_u32(box + 24);
    const uint64_t mgr = state_u64(state_u64(STATE_GAMEDATA_SLOT));
''')
        actions, problems = hsdebug.source_actions(str(root))
        assert not problems, problems
        assert actions == {'item_base': 9000, 'teleport_base': 1111, 'age': 998, 'time_base': 500, 'time_hours': 24, 'mark': 7,
                           'return': 8, 'item_stride': 100, 'item_bias': 50, 'item_toggle': 90}, actions
        doc = hsdebug.build_game_info(str(root), {'names': {'life': 'synthetic.life'}})
        assert [i['name'] for i in doc['items']] == ['Synthetic_Blade', 'Synthetic_Orb'] and doc['items'][1]['label'] == 'Synthetic "Orb"'
        assert doc['layout']['holder'] == 0x1000 and doc['layout']['kinds']['uint'] == {'at': 0x150, 'stride': 0x10, 'value': 4}
        assert doc['layout']['box'] == {'count': 4, 'entries': 8, 'table': 16, 'size': 24}
        assert set(doc['layout']['kinds']) == {'bool', 'int', 'float', 'uint'} and doc['names'] == {'life': 'synthetic.life'}
        info = hsdebug.GameInfo(doc)
        assert info.item('Synthetic "Orb"')['index'] == 1
        # a source that does not look as expected is said, not guessed at
        (root / 'host/hos_main.c').write_text(main.replace('const int returning = action == 8 &&', 'const int returning = flag == 8 &&'))
        actions, problems = hsdebug.source_actions(str(root))
        assert any('the return' in p for p in problems) and 'return' not in actions
        raises('bad_request', hsdebug.build_game_info, str(root))
        (root / 'host/hos_main.c').write_text(main)
        # an item whose name is neither a string nor a #define of the header is an error, never a missing row
        (root / 'gpu/vk/oot_cheat_items.h').write_text(header.replace('SYNTH_BLADE, 0', 'UNKNOWN_NAME, 0'))
        e = raises('bad_request', hsdebug.source_items, str(root))
        assert 'not a string or a #define' in e.message
        (root / 'gpu/vk/oot_cheat_items.h').write_text(header.replace('"Synthetic_Orb", 1)', '"Synthetic_Orb", one)'))
        e = raises('bad_request', hsdebug.source_items, str(root))
        assert '2 OOT_ITEM rows, 1 read' in e.message
        (root / 'gpu/vk/oot_cheat_items.h').write_text(header)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = hsdebug.main(['check-source', str(root)])
        res = json.loads(out.getvalue())
        assert code == 0 and res['ok'] and res['sources'][0]['items'] == 2 and res['sources'][0]['layout']
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = hsdebug.main(['game-info', '--source', str(root), '--out', str(root / 'g.json')])
        assert code == 0 and (os.stat(root / 'g.json').st_mode & 0o777) == 0o600 and json.loads(out.getvalue())['private'] is True
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = hsdebug.main(['check-source', str(tmp) + '/nowhere'])
        assert code == 1 and json.loads(out.getvalue())['error'] == 'bad_request'


def cli_checks():
    with game() as (g, tmp):
        info = tmp / 'info.json'
        info.write_text(json.dumps(INFO))

        def cli(*argv):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = hsdebug.main(['--run', str(g.run), '--info', str(info), '--ready-timeout', '5', *argv])
            return code, json.loads(out.getvalue())
        code, r = cli('status')
        assert code == 0 and r['state']['map'] == 'SyntheticFieldYoung'
        code, r = cli('destinations')
        assert code == 0 and len(r['destinations']) == 4
        code, r = cli('teleport', 'SyntheticCave')
        assert code == 0 and r['effect'] == 'verified'
        code, r = cli('age', 'adult', '--settle', '5')
        assert code == 0 and r['after']['age'] == 'adult' and r['settle'] == 5
        code, r = cli('time', '4')
        assert code == 0 and r['hour'] == 4 and r['effect'] == 'requested'
        code, r = cli('give', 'Synthetic_Orb', '2')
        assert code == 0 and r['effect'] == 'verified'
        code, r = cli('take', 'Synthetic_Orb', '1')
        assert code == 0 and r['count_after'] == r['count_before'] - 1
        code, r = cli('toggle', 'Synthetic_Blade')
        assert code == 0
        code, r = cli('items')
        assert code == 0 and len(r['items']) == 3
        code, r = cli('flag', 'set', 'synthetic.flag', '1')
        assert code == 0 and r['after_flag'] == 1
        code, r = cli('flag', 'get', 'synthetic.flag', 'synthetic.life')
        assert code == 0 and r['flags']['synthetic.flag'] == 1
        code, r = cli('health', '8')
        assert code == 0 and r['state']['life'] == 8
        code, r = cli('rupees', '77')
        assert code == 0 and g.mem.get('synthetic.rupees') == 77
        code, r = cli('warp', '2', '2', '2', '--watch', '0.3')
        assert code == 0 and r['effect'] == 'verified' and r['after']['pos'] == [2, 2, 2], r
        code, r = cli('mark')
        assert code == 0
        code, r = cli('return')
        assert code == 0 and r['effect'] == 'verified'
        code, r = cli('option', 'set', 'debug_tools', '1')
        assert code == 0
        code, r = cli('option', 'get')
        assert code == 0 and len(r['options']) == 2
        code, r = cli('shot', str(tmp / 'cli.png'))
        assert code == 0 and (tmp / 'cli.png').exists()
        code, r = cli('saves')
        assert code == 0 and r['disposable']['verified']
        code, r = cli('capabilities')
        assert code == 0 and r['bridge']['memory'] == 'rw'
        code, r = cli('snapshot', str(tmp / 'cli-snap'), '--wait-save', '0.4')
        assert code == 0 and r['files'] == 3 and r['effect'] == 'partial'
        code, r = cli('restore', str(tmp / 'cli-snap'), '--into', str(tmp / 'cli-scratch'))
        assert code == 0 and r['effect'] == 'verified'
        code, r = cli('setup', '--time', '9', '--give', 'Synthetic_Seed=2', '--flag', 'synthetic.flag=0')
        assert code == 0 and [s['action'] for s in r['steps']] == ['time', 'give', 'flag_set']
        # errors: exit codes and the JSON
        code, r = cli('teleport', 'Nowhere')
        assert code == 1 and r['ok'] is False and r['error'] == 'bad_request'
        code, r = cli('give', 'Synthetic_Blade')
        assert code == 1 and r['error'] == 'bad_request'
        code, r = cli('flag', 'set', 'synthetic.life', '1', '--kind', 'bool')
        assert code == 1
        g.sticky.add('synthetic.life')
        code, r = cli('health', '1')
        assert code == 1 and r['effect'] == 'not_applied'
        code, r = cli('setup', '--to', 'Nowhere')
        assert code == 1 or code == 0
    # no game: exit 2
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = hsdebug.main(['--sock', '/nonexistent/control.sock', 'status'])
    assert code == 2 and json.loads(out.getvalue())['error'] == 'unavailable'
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = hsdebug.main(['status'])
    assert code == 1 and json.loads(out.getvalue())['error'] == 'bad_request'
    # timeout: exit 3
    with game() as (g, tmp):
        orig = g.handle
        g.handle = lambda req, conn: (None, []) if req.get('cmd') == 'status' else orig(req, conn)
        d = attach(g)
        d.bridge.request = (lambda f: lambda cmd, timeout=None, **a: f(cmd, timeout=0.3 if cmd == 'status' else timeout, **a))(d.bridge.request)
        e = raises('timeout', d.status)
        assert hsdebug.EXIT[e.code] == 3
        d.bridge.close()


def attach_checks():
    with game() as (g, tmp):
        d = attach(g)
        assert d.sock_path == g.sock_path and d.live == str(g.live_path) and d.log.path == str(g.log_path) and d.root == str(g.run.resolve())
        d.close()
        # a workbench session's folder: control.sock and extra-env.txt
        s = tmp / 'session'
        s.mkdir()
        (s / 'extra-env.txt').write_text('HOS_CONTROL=%s\nHOS_INPUT_LIVE=%s\nHOS_OOT_CHEATS=1\n' % (g.sock_path, g.live_path))
        d = hsdebug.attach(run=str(s))
        assert d.sock_path == g.sock_path and d.env['HOS_OOT_CHEATS'] == '1'
        d.close()
        raises('bad_request', hsdebug.attach, run=str(tmp / 'nothing'))
        raises('bad_request', hsdebug.attach)
        raises('unavailable', hsdebug.attach, sock=str(tmp / 'no.sock'))


def boot_checks():
    with game() as (g, _):
        g.state, g.state_presses, g.map = 'menu', 0, None
        d = attach(g)
        st = d.wait_play(timeout=20)
        assert st['map'] == 'SyntheticFieldYoung' and hsdebug.ready(st)
        assert sum(1 for c in g.commands if c['cmd'] == 'press') >= 2
        d.close()

def step_checks():
    """The step a driver (hsap's `debug <words>`) runs: words in, (result, detail) out; HSDEBUG_INFO names the game info."""
    with game() as (g, tmp):
        info = tmp / 'info.json'
        info.write_text(json.dumps(INFO))
        r, detail = hsdebug.step(g.run, ['teleport', 'SyntheticCave'], info=info)
        assert r == 'done' and json.loads(detail)['effect'] == 'verified' and g.map == 'SyntheticCave', (r, detail)
        os.environ['HSDEBUG_INFO'] = str(info)
        try:
            r, detail = hsdebug.step(g.run, ['give', 'Synthetic_Orb', '2'])
            assert r == 'done' and json.loads(detail)['count_after'] == 4, (r, detail)
            r, detail = hsdebug.step(g.run, ['give', 'Synthetic_Blade'])
            assert r == 'bad_request' or 'error' in json.loads(detail), (r, detail)
            g.sticky.add('synthetic.life')
            r, detail = hsdebug.step(g.run, ['health', '1'])
            assert r == 'not_applied', (r, detail)
        finally:
            del os.environ['HSDEBUG_INFO']
        r, detail = hsdebug.step(g.run, ['nonsense'])
        assert r == 'bad_request' and 'not a command' in detail
        r, detail = hsdebug.step(tmp / 'no-run', ['status'])
        assert r == 'bad_request' and 'no run folder' in detail
        r, detail = hsdebug.step(g.run, ['time', '30'], info=info)
        assert r == 'bad_request'
        assert len(detail) <= 400



def toggle_checks():
    """A pouch item's count is the truth about whether Link has it: the item's `have` flag is set when it is got and the game never
    clears it when one is taken away (seen in the real game with a sword taken away: the flag still read 1)."""
    with game() as (g, _):
        d = attach(g)
        r = d.toggle('Synthetic_Blade')
        assert r['ok'] and r['effect'] == 'verified' and r['have_before'] == 0 and r['have_after'] == 1, r
        assert r['read_from'] == 'Synthetic.Synthetic_Blade.Stock', r
        r = d.toggle('Synthetic_Blade')    # taken away: the count says so, the have flag does not
        assert r['ok'] and r['effect'] == 'verified' and r['have_before'] == 1 and r['have_after'] == 0, r
        assert g.mem.get('Synthetic.Synthetic_Blade.Have') == 1
        d.close()
    with game() as (g, _):    # the game has no count flag for it: the have flag proves a got item, not a taken one
        info = json.loads(json.dumps(INFO))
        info['item_flags']['count'] = 'Synthetic.{name}.Absent'
        d = hsdebug.attach(run=str(g.run), info=hsdebug.GameInfo(info), ready_timeout=5)
        r = d.toggle('Synthetic_Blade')
        assert r['ok'] and r['effect'] == 'verified' and r['read_from'] == 'Synthetic.Synthetic_Blade.Have', r
        r = d.toggle('Synthetic_Blade')
        assert r['ok'] and r['effect'] == 'requested' and 'not cleared' in r['note'] and r['have_after'] == 1, r
        d.close()


def settle_checks():
    """After a map change the scene fades in: a picture taken at the arrival is black. The tools wait the fade out."""
    with game() as (g, tmp):
        d = attach(g)
        r = d.teleport('SyntheticHallYoung', settle=0)
        assert r['ok'] and r['settle'] == 0
        assert d.shot(str(tmp / 'a.png'))['luma'] < 5          # (the fake game is still fading in)
        time.sleep(0.25)
        r = d.teleport(2)
        assert r['ok'] and r['settle'] == hsdebug.SETTLE >= 60, r
        assert d.shot(str(tmp / 'b.png'))['luma'] > 20
        r = d.age('adult')
        assert r['ok'] and r['settle'] == hsdebug.SETTLE
        assert d.shot(str(tmp / 'c.png'))['luma'] > 20
        d.close()


def snapshot_save_checks():
    """The game saves at its own transitions: a snapshot says whether its newest slot holds the place Link is in, can wait for the
    save, and a restore says which of the two it put back."""
    with game() as (g, tmp):
        d = attach(g)
        d.teleport('SyntheticCave')                            # (the fake game does not save there)
        r = d.snapshot(str(tmp / 's1'))
        assert r['ok'] and r['effect'] == 'partial' and r['caption_matches_map'] is False and 'not saved' in r['note'], r
        assert json.loads((tmp / 's1' / 'snapshot.json').read_text())['slot_map'] == 'SyntheticFieldYoung'
        time.sleep(0.25)
        d.teleport(0)
        g.t0 -= 100
        r = d.restore(str(tmp / 's1'), relaunch=True)          # the files came back: the game stands where THEY say
        assert r['ok'] and r['effect'] == 'partial' and r['after']['map'] == 'SyntheticFieldYoung' and 'not saved' in r['note'], r
        assert r['state_at_snapshot']['map'] == 'SyntheticCave' and r['slot_map'] == 'SyntheticFieldYoung', r
        d.close()
    with game() as (g, tmp):
        g.autosave_after = 400
        d = attach(g)
        d.teleport('SyntheticCave', settle=0)
        r = d.snapshot(str(tmp / 's2'), wait_save=20)          # (the game writes its slot 400 presents after the arrival)
        assert r['effect'] == 'verified' and r['caption_matches_map'] is True and r['waited_s'] >= 0, r
        time.sleep(0.25)
        g.autosave_after = None
        d.teleport(0)
        t0 = time.monotonic()
        r = d.snapshot(str(tmp / 's3'), wait_save=1.0)         # it never comes: the wait ends and the result says so
        assert r['effect'] == 'partial' and 1.0 <= time.monotonic() - t0 < 6, (r, time.monotonic() - t0)
        g.t0 -= 100
        d.close()


def restore_edits_checks():
    """The save holds what the game saved, not a value written into its memory: an in-place restore says what differs."""
    with game() as (g, tmp):
        g.reload_flags = {'synthetic.rupees': 7}
        d = attach(g)
        d.set_state(rupees=50)
        d.snapshot(str(tmp / 'snap'))
        g.t0 -= 100
        r = d.restore(str(tmp / 'snap'), relaunch=True)
        assert r['ok'] and r['effect'] == 'partial' and r['after']['rupees'] == 7 and r['state_at_snapshot']['rupees'] == 50, r
        assert r['not_in_save'] == {'rupees': [50, 7]} and 'memory' in r['note'], r
        d.close()


def place_checks():
    """warp through the game's own return-to-mark path: the live file's `!place X Y Z` (no memory write, no opt-in)."""
    with game(mem_level='off') as (g, tmp):
        d = attach(g)
        r = d.warp(11, 2, -5.5, watch=0.4)
        assert r['ok'] and r['effect'] == 'verified' and r['after']['pos'] == [11, 2, -5.5] and r['method'] == 'place', r
        assert 'returned to %.2f %.2f %.2f' % (11, 2, -5.5) in ' '.join(r['game_said']), r
        assert [c for c in g.commands if c['cmd'] == 'mem_write'] == []          # nothing was written into memory
        r = d.warp(5, 2, 5, to='SyntheticCave', facing=45, watch=0.3)
        assert r['effect'] == 'verified' and r['teleport']['after']['map'] == 'SyntheticCave' and 'facing' in r['note'], r
        g.pull_to, g.pull_delay = [1, 2, 3], 1
        r = d.warp(30, 2, 30, watch=1.0)
        assert r['effect'] == 'partial' and 'put him back' in r['note'], r
        g.pull_to = None
        # the first reading is still the old snapshot (a few metres away, then the target for good): that is not a failure
        g.place_lag = 1
        r = d.warp(8, 2, 8, watch=0.6)
        assert r['effect'] == 'verified' and r['samples'][0]['dist'] > 5 and r['samples'][0]['stale'] and not r['samples'][-1].get('stale'), r
        assert r.get('note') is None, r
        g.place_lag = 0
        g.place_supported = False                    # a build without the command: the game says nothing
        r = d.warp(40, 2, 40, watch=0.4)
        assert not r['ok'] and r['effect'] == 'not_applied' and '!place' in r['note'], r
        d.close()
    with game() as (g, tmp):
        loose = hsdebug.Debug(g.sock_path, live=g.live_path, log=g.log_path, info=hsdebug.GameInfo(INFO))
        raises('not_disposable', loose.warp, 1, 2, 3)
        assert 'place' not in ' '.join(open(g.live_path).read().split())
        loose.close()


def warp_checks():
    """A coordinate warp: Link's position written into guest memory at the field the bridge's position is read from (found by effect, not by
    address), then read back for a while. The game may pull him back; the result says what was seen."""
    with game() as (g, tmp):
        d = attach(g)
        r = d.warp(11, 2, -5.5, facing=90, watch=0.6, method='memory')
        assert r['ok'] and r['effect'] == 'verified' and r['after']['pos'] == [11, 2, -5.5], r
        assert abs(r['after']['facing'] - 90) < 0.5 and r['candidates'] == 2 and r['samples'], r
        assert struct.unpack_from('<3f', g.mem.m, DECOY) == (1, 2, 3)      # the decoy was put back
        r = d.warp(12, 2, -5.5, watch=0.3, method='memory')                                   # the address is known now: no scan
        assert r['effect'] == 'verified' and r['candidates'] == 0, r
        # the game puts Link back after a moment: partial, with what was seen
        g.pull_to, g.pull_delay = [1, 2, 3], 1
        r = d.warp(30, 2, 30, watch=1.0, method='memory')
        assert r['ok'] and r['effect'] == 'partial' and r['samples'][0]['dist'] < 0.6 and r['samples'][-1]['dist'] > 5, r
        assert 'put him back' in r['note'], r
        # he is put back at once: not applied
        g.pull_delay = 0
        r = d.warp(40, 2, 40, watch=0.5, method='memory')
        assert not r['ok'] and r['effect'] == 'not_applied', r
        g.pull_to = None
        # a warp after a teleport to a map
        r = d.warp(5, 2, 5, to='SyntheticCave', watch=0.3, method='memory')
        assert r['effect'] == 'verified' and r['teleport']['after']['map'] == 'SyntheticCave', r
        raises('bad_request', d.warp, float('nan'), 0, 0)
        raises('bad_request', d.warp, 1e9, 0, 0)
        raises('bad_request', d.warp, 1, 2, 3, facing='north')
        n = len([c for c in g.commands if c['cmd'] == 'mem_write'])
        raises('bad_request', d.warp, 1, 2, None)
        assert len([c for c in g.commands if c['cmd'] == 'mem_write']) == n
        d.close()
    with game(mem_level='off') as (g, _):
        d = attach(g)
        raises('forbidden', lambda: d.warp(1, 2, 3, method='memory'))
        d.close()
    with game() as (g, tmp):    # not a throw-away run: nothing is written
        loose = hsdebug.Debug(g.sock_path, live=g.live_path, log=g.log_path, info=hsdebug.GameInfo(INFO))
        raises('not_disposable', loose.warp, 1, 2, 3)
        assert not [c for c in g.commands if c['cmd'] == 'mem_write']
        loose.close()


CHECKS = [murmur_checks, info_checks, status_checks, teleport_checks, age_checks, guard_checks, time_checks, item_checks, mark_checks,
          flag_checks, option_checks, shot_and_input_checks, capabilities_checks, snapshot_checks, restore_relaunch_checks,
          setup_checks, source_checks, cli_checks, attach_checks, boot_checks, step_checks, toggle_checks, settle_checks,
          snapshot_save_checks, restore_edits_checks, warp_checks, place_checks]


def main():
    failed = 0
    for check in CHECKS:
        t0 = time.monotonic()
        try:
            check()
            print('pass  %-28s %.1f s' % (check.__name__, time.monotonic() - t0))
        except Exception as e:   # noqa: BLE001
            import traceback
            traceback.print_exc()
            print('FAIL  %-28s %s: %s' % (check.__name__, type(e).__name__, e))
            failed += 1
    print('test_hsdebug: %s' % ('%d failed' % failed if failed else 'all passed'))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
