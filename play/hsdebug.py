#!/usr/bin/env python3
"""hsdebug: the game's debug tools from a command line and from Python, for disposable runs of the game.

What the game already offers is used as it is; nothing here changes the game:
  bridge        HOS_CONTROL's socket: status, teleport (to a destination the game lists), age, options (debug_tools,
                damage_taken, transition_autosave, ...), saves, shots, inputs, relaunch, and, only when the game was started
                with HOS_CONTROL_MEM=rw, guest memory (flag writes)
  live input    HOS_INPUT_LIVE's `!cheat <n>` lines: the Debug tab's time of day, inventory editor, mark / return
  log           the game's own `cheats:` lines say what the game did
Every action prints one JSON object read back from the game: `effect` is `verified` (the state read back is what was asked),
`requested` (the game acknowledged it in its log; there is nothing on the bridge to compare), `partial`, `not_applied`
(read back, and it differs) or `unconfirmed`. Exit status 0 done, 1 refused or not applied, 2 no game / not usable here /
not a disposable run, 3 timed out.

    hsdebug.py --run <hs-run run folder> status
    hsdebug.py --run R destinations
    hsdebug.py --run R teleport <index | map name> [--settle N] | age child|adult [--settle N] | time <hour 0-23>
    hsdebug.py --run R --info G.json give <item> [count] | take <item> [count] | toggle <item> | items
    hsdebug.py --run R --info G.json flag get NAME... | flag set NAME VALUE | health N | rupees N | magic N
    hsdebug.py --run R mark | return | option get|set NAME [VALUE] | shot [PATH] | saves | capabilities
    hsdebug.py --run R --info G.json warp X Y Z [--facing DEG] [--to MAP]   (HOS_CONTROL_MEM=rw; metres in the map's frame)
    hsdebug.py --run R boot | snapshot DIR [--wait-save S] | restore DIR [--into NEWDIR | --relaunch]
    hsdebug.py --run R --info G.json setup --age adult --to <index|map> --time 19 --toggle <upgrade> --give A=3 --rupees 99
    hsdebug.py game-info --source <game checkout> [--extra private.json] --out G.json | check-source <checkout>...

Python:  import hsdebug; d = hsdebug.attach(run='<run folder>', info='G.json'); d.setup(to='Some_Map', age='adult', hour=22)
         hsdebug.step(run, ['teleport', '3']) -> ('done', detail): one command for a driver's step (hsap's `debug <words>`)
Standard library only (and the harness's hs_names for the game's own log file names). No game data in this file: destinations come
from the bridge, item numbers and the flag layout from the game's own source (`game-info`, a private file) at run time, flag names
from the caller.
"""
import argparse
import collections
import hashlib
import json
import math
import os
import re
import socket
import stat
import struct
import sys
import tempfile
import time
import zlib

_root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))   # the harness folder (in a checkout of the workbench repository its root: hs_names.py sits in harness/ there), as hsap.py finds it
sys.path.insert(0, _root if os.path.isfile(os.path.join(_root, 'hs_names.py')) else os.path.join(_root, 'harness'))
import hs_names  # noqa: E402  (the game's log file names: one copy)

FRESH_FRAMES = 12          # a snapshot whose game.frame is this many presents behind the reply's is not current
LIVE_GAP = 0.04            # the game reads the live file every 30 ms and keeps the last `!cheat` of a poll
LINK_ROT_AFTER_POS = 12   # Link's actor holds his position (three floats) and, 12 bytes on, his rotation matrix (nine floats, row-major): host/hos_main.c +796 / +808
SETTLE = 120              # presents waited after a map change: the scene fades in from black for a while after the game says it is playing
FLAG_NAME = re.compile(r'^(0x[0-9a-fA-F]{8}|[A-Za-z0-9_.]{1,47})$')
GAME_TIMED = frozenset({'teleport', 'age', 'wait', 'shot', 'press', 'stick', 'sequence'})
LOG_NAMES = tuple(hs_names.Names(p).log for p in hs_names.PROJECTS)
EXIT = {'ok': 0, 'refused': 1, 'not_applied': 1, 'bad_request': 1, 'failed': 1, 'forbidden': 1, 'busy': 1,
        'unavailable': 2, 'not_disposable': 2, 'timeout': 3, 'uncertain': 3}


class DebugError(Exception):
    """code: bad_request, unavailable, not_disposable, refused, forbidden, busy, timeout, uncertain, failed"""

    def __init__(self, code, message, **data):
        super().__init__(message)
        self.code, self.message, self.data = code, message, data

    def as_result(self, action=None):
        return {'ok': False, 'action': action, 'error': self.code, 'message': self.message, **self.data}


# ---------------------------------------------------------------- the bridge

class Bridge:
    """The control bridge: newline-delimited JSON over a Unix socket, replies matched by id, events kept."""

    def __init__(self, path, timeout=5.0):
        self.path = str(path)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        try:
            self.sock.connect(self.path)
        except OSError as e:
            self.sock.close()
            raise DebugError('unavailable', 'no game answers on %s (%s)' % (self.path, e.strerror or e)) from None
        self.buf, self.next_id, self.events = b'', 0, collections.deque(maxlen=512)

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass

    def _line(self, deadline):
        while b'\n' not in self.buf:
            left = deadline - time.monotonic()
            if left <= 0:
                raise socket.timeout()
            self.sock.settimeout(left)
            chunk = self.sock.recv(65536)
            if not chunk:
                raise DebugError('unavailable', 'the game closed the control socket')
            self.buf += chunk
        line, _, self.buf = self.buf.partition(b'\n')
        return line

    def request(self, cmd, timeout=None, **args):
        """One request; the reply dict (ok or not). Raises DebugError('unavailable') when the socket is gone, and
        ('timeout') when no reply came."""
        self.next_id += 1
        rid = self.next_id
        body = {'id': rid, 'cmd': cmd, **args}
        if timeout is not None and cmd in GAME_TIMED:
            body['timeout'] = timeout
        wait = (timeout + 4.0) if timeout is not None else 10.0
        try:
            self.sock.settimeout(5.0)
            self.sock.sendall((json.dumps(body, separators=(',', ':')) + '\n').encode())
        except OSError as e:
            raise DebugError('unavailable', 'the control socket is gone (%s)' % (e.strerror or e)) from None
        deadline = time.monotonic() + wait
        while True:
            try:
                raw = self._line(deadline)
            except socket.timeout:
                raise DebugError('timeout', '%s: no reply in %.0f s' % (cmd, wait)) from None
            except OSError as e:
                raise DebugError('unavailable', 'the control socket is gone (%s)' % (e.strerror or e)) from None
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(msg, dict):
                continue
            if 'event' in msg and 'ok' not in msg:
                self.events.append(msg)
            elif msg.get('id') == rid:
                return msg

    def event(self, kind, timeout):
        """The next event of that kind (events already read count)."""
        deadline = time.monotonic() + timeout
        while True:
            for i, ev in enumerate(self.events):
                if ev.get('event') == kind:
                    del self.events[i]
                    return ev
            try:
                raw = self._line(deadline)
            except socket.timeout:
                return None
            except OSError:
                return None
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            if isinstance(msg, dict) and 'event' in msg and 'ok' not in msg:
                self.events.append(msg)


def must(reply, what):
    """The reply of an ok command, or the DebugError for its error."""
    if reply.get('ok'):
        return reply
    err, msg = reply.get('error'), reply.get('message', '')
    code = {'refused': 'refused', 'timeout': 'timeout', 'forbidden': 'forbidden', 'unavailable': 'unavailable',
            'not_found': 'bad_request', 'bad_request': 'bad_request', 'busy': 'busy', 'cancelled': 'busy',
            'out_of_range': 'failed', 'unknown_cmd': 'unavailable'}.get(err, 'failed')
    raise DebugError(code, '%s: %s%s' % (what, err, (': ' + msg) if msg else ''), bridge_error=err)


# ---------------------------------------------------------------- the game's own lists: game info

MURMUR_C = (0xcc9e2d51, 0x1b873593)


def murmur3(text):
    """MurmurHash3 x86 32 bit, seed 0, of the UTF-8 text: the hash the game names its flags by."""
    data = text.encode() if isinstance(text, str) else bytes(text)
    h, n = 0, len(data)
    for i in range(0, n - n % 4, 4):
        k = int.from_bytes(data[i:i + 4], 'little')
        k = (k * MURMUR_C[0]) & 0xffffffff
        k = ((k << 15) | (k >> 17)) & 0xffffffff
        k = (k * MURMUR_C[1]) & 0xffffffff
        h ^= k
        h = (((h << 13) | (h >> 19)) & 0xffffffff)
        h = (h * 5 + 0xe6546b64) & 0xffffffff
    tail, k = data[n - n % 4:], 0
    for i in range(len(tail) - 1, -1, -1):
        k ^= tail[i] << (8 * i)
    if tail:
        k = (k * MURMUR_C[0]) & 0xffffffff
        k = ((k << 15) | (k >> 17)) & 0xffffffff
        k = (k * MURMUR_C[1]) & 0xffffffff
        h ^= k
    h ^= n
    h ^= h >> 16
    h = (h * 0x85ebca6b) & 0xffffffff
    h ^= h >> 13
    h = (h * 0xc2b2ae35) & 0xffffffff
    h ^= h >> 16
    return h


ACTION_KEYS = ('time_base', 'time_hours', 'mark', 'return', 'item_base', 'item_stride', 'item_bias', 'item_toggle')
KIND_WIDTH = {'bool': 1, 'int': 4, 'uint': 4, 'float': 4}
KINDS_ORDER = ('bool', 'int', 'float', 'uint')   # the order the bridge looks a flag up in, text and enum left out


class GameInfo:
    """What the harness needs of the game's own lists, read at run time from its source (`game-info`) or from the file that
    produced: the Debug tab's action numbers, the inventory editor's items, the flag containers' layout. Private: it is
    made from the game's source and stays out of repositories."""

    def __init__(self, doc):
        if not isinstance(doc, dict) or doc.get('schema') != 1:
            raise DebugError('bad_request', 'game info: schema 1 expected')
        extra = set(doc) - {'schema', 'actions', 'items', 'layout', 'item_flags', 'names'}
        if extra:
            raise DebugError('bad_request', 'game info: unknown keys %s' % sorted(extra))
        actions = doc.get('actions') or {}
        if set(actions) != set(ACTION_KEYS) or not all(isinstance(actions[k], int) and not isinstance(actions[k], bool)
                                                       for k in ACTION_KEYS):
            raise DebugError('bad_request', 'game info: actions need exactly %s' % ', '.join(ACTION_KEYS))
        self.actions, self.doc = dict(actions), doc
        self.items = []
        for row in doc.get('items') or []:
            if not (isinstance(row, dict) and isinstance(row.get('index'), int) and isinstance(row.get('name'), str)
                    and row.get('kind') in (0, 1) and isinstance(row.get('label'), str)):
                raise DebugError('bad_request', 'game info: an item row needs index, name, label, kind 0 or 1')
            self.items.append(dict(row))
        self.layout = doc.get('layout')
        if self.layout is not None:
            kinds, box = self.layout.get('kinds'), self.layout.get('box')
            if not (isinstance(self.layout.get('holder'), int) and isinstance(kinds, dict) and isinstance(box, dict)
                    and set(box) == {'count', 'entries', 'table', 'size'} and set(kinds) <= set(KIND_WIDTH)
                    and all(isinstance(v, dict) and set(v) == {'at', 'stride', 'value'} for v in kinds.values())):
                raise DebugError('bad_request', 'game info: layout needs holder, kinds{at,stride,value}, box{count,entries,table,size}')
        self.item_flags = doc.get('item_flags') or {}
        self.names = doc.get('names') or {}

    @classmethod
    def load(cls, path):
        try:
            with open(path, 'rb') as f:
                raw = f.read(4 << 20)
            return cls(json.loads(raw))
        except (OSError, ValueError) as e:
            raise DebugError('bad_request', 'game info %s: %s' % (path, e)) from None

    def item(self, key):
        """An item by exact pouch name, label (any case) or index."""
        key = str(key)
        rows = [r for r in self.items if key == r['name']] or [r for r in self.items if key.lower() == r['label'].lower()]
        if not rows and key.isdigit():
            rows = [r for r in self.items if r['index'] == int(key)]
        if not rows:
            raise DebugError('bad_request', 'no such item %r: `items` lists the game\'s own' % key)
        return rows[0]

    def flag_name(self, name):
        return self.names.get(name, name)


def _read_text(root, rel):
    path = os.path.join(root, rel)
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            return f.read()
    except OSError:
        raise DebugError('bad_request', 'the game source has no %s (is %s a checkout?)' % (rel, root)) from None


def _define(text, name):
    m = re.search(r'#define\s+%s\s+(0x[0-9a-fA-F]+|\d+)' % re.escape(name), text)
    return int(m.group(1), 0) if m else None


def source_actions(root):
    """The Debug tab's action numbers as the game's source gives them, and what in the source could not be matched:
    ({key: number}, [problem]). The defined numbers are read from #defines; the others stand in literals of
    oot_update_player_cheats and the inventory editor, which are checked by their text."""
    main = _read_text(root, 'host/hos_main.c')
    items_h = _read_text(root, 'gpu/vk/oot_cheat_items.h')
    problems, out = [], {}
    base = _define(items_h, 'OOT_CHEAT_ITEM_ACTION')
    if base is None:
        problems.append('OOT_CHEAT_ITEM_ACTION is not defined in gpu/vk/oot_cheat_items.h')
    out['item_base'] = base
    for key, name in (('teleport_base', 'OOT_TELEPORT_ACTION'), ('age', 'OOT_AGE_ACTION')):
        out[key] = _define(main, name)
        if out[key] is None:
            problems.append('%s is not defined in host/hos_main.c' % name)

    def literal(label, pattern, key, group=1, convert=int):
        m = re.search(pattern, main)
        if not m:
            problems.append('host/hos_main.c: %s not found (pattern %s)' % (label, pattern))
        else:
            out[key] = convert(m.group(group))
    literal('the clock', r'action\s*>=\s*(\d+)\s*&&\s*action\s*<\s*\d+\)\s*\{\s*oot_set_time\(c,\s*action\s*-\s*\1\)', 'time_base')
    literal('the clock hours', r'action\s*>=\s*\d+\s*&&\s*action\s*<\s*(\d+)\)\s*\{\s*oot_set_time', 'time_hours')
    if out.get('time_base') is not None and out.get('time_hours') is not None:
        out['time_hours'] -= out['time_base']
    literal('the mark', r'if\s*\(action\s*==\s*(\d+)\)\s*\{\s*for\s*\(unsigned i = 0; i < 3; i\+\+\)\s*\{\s*const uint32_t bits', 'mark')
    literal('the return', r'const int returning = action == (\d+) &&', 'return')
    literal('the item stride', r'\(unsigned\)\(action - OOT_CHEAT_ITEM_ACTION\)\s*/\s*(\d+)', 'item_stride')
    literal('the item bias', r'else if \(op < 128\) delta = \(int\)op - (\d+);', 'item_bias')
    literal('the item toggle', r'if \(op == (\d+)\) delta = have > 0 \?', 'item_toggle')
    return out, problems


def source_items(root):
    """The inventory editor's items in the header's order (the index is the order). A name may be a macro of the same header;
    a row that could not be read is an error, never left out."""
    text = _read_text(root, 'gpu/vk/oot_cheat_items.h')
    text = re.sub(r'//[^\n]*', '', re.sub(r'/\*.*?\*/', '', text, flags=re.S))   # (a comment names OOT_ITEM(...) too)
    macros = dict(re.findall(r'#define\s+([A-Za-z_][A-Za-z0-9_]*)\s+"((?:[^"\\]|\\.)*)"', text))
    rows = re.findall(r'\bOOT_ITEM\(\s*"((?:[^"\\]|\\.)*)"\s*,\s*("(?:[^"\\]|\\.)*"|[A-Za-z_][A-Za-z0-9_]*)\s*,\s*(\d)\s*\)', text)
    calls = len(re.findall(r'\bOOT_ITEM\(', text))
    out = []
    for i, (label, name, kind) in enumerate(rows):
        name = name[1:-1] if name.startswith('"') else macros.get(name)
        if not name:
            raise DebugError('bad_request', 'gpu/vk/oot_cheat_items.h: item %d (%s) has a name that is not a string or a #define' % (i, label))
        out.append({'index': i, 'name': name, 'label': label.replace('\\"', '"'), 'kind': int(kind)})
    if len(rows) != calls:
        raise DebugError('bad_request', 'gpu/vk/oot_cheat_items.h: %d OOT_ITEM rows, %d read' % (calls, len(rows)))
    return out


def source_layout(root):
    """The flag containers' layout from host/oot_state_tap.c (the code that reads them for the bridge)."""
    text = _read_text(root, 'host/oot_state_tap.c')
    holder = _define(text, 'STATE_GAMEDATA_SLOT')
    enum = re.search(r'enum\s*\{\s*KIND_BOOL,\s*KIND_INT,\s*KIND_FLOAT,\s*KIND_ENUM,\s*KIND_TEXT,\s*KIND_UINT,\s*KINDS\s*\}', text)
    block = re.search(r'state_kind\[KINDS\]\s*=\s*\{(.*?)\};', text, re.S)
    entries = re.search(r'entries\s*=\s*state_u64\(box\s*\+\s*(\d+)\)\s*,\s*table\s*=\s*state_u64\(box\s*\+\s*(\d+)\)', text)
    count = re.search(r'count\s*=\s*state_u32\(box\s*\+\s*(\d+)\)\s*,\s*size\s*=\s*state_u32\(box\s*\+\s*(\d+)\)', text)
    twice = re.search(r'mgr\s*=\s*state_u64\(state_u64\(STATE_GAMEDATA_SLOT\)\)', text)
    if None in (holder, enum, block, entries, count, twice):
        raise DebugError('bad_request', 'host/oot_state_tap.c: the flag container layout could not be read as expected')
    triples = re.findall(r'\{\s*(0x[0-9a-fA-F]+|\d+)\s*,\s*(0x[0-9a-fA-F]+|\d+)\s*,\s*(0x[0-9a-fA-F]+|\d+)\s*\}', block.group(1))
    names = ['bool', 'int', 'float', 'enum', 'text', 'uint']
    if len(triples) != len(names):
        raise DebugError('bad_request', 'host/oot_state_tap.c: %d container rows, expected %d' % (len(triples), len(names)))
    kinds = {}
    for name, (at, stride, value) in zip(names, triples):
        if name in KIND_WIDTH:
            kinds[name] = {'at': int(at, 0), 'stride': int(stride, 0), 'value': int(value, 0)}
    return {'holder': holder, 'kinds': kinds,
            'box': {'count': int(count.group(1)), 'entries': int(entries.group(1)), 'table': int(entries.group(2)),
                    'size': int(count.group(2))}}


def build_game_info(root, extra=None):
    """The game-info document of a game checkout (and the problems the checkout's source showed)."""
    actions, problems = source_actions(root)
    if problems:
        raise DebugError('bad_request', 'the source does not look as the harness expects: ' + '; '.join(problems))
    doc = {'schema': 1, 'actions': {k: actions[k] for k in ACTION_KEYS}, 'items': source_items(root),
           'layout': source_layout(root)}
    if extra:
        for key in ('item_flags', 'names'):
            if key in extra:
                doc[key] = extra[key]
    GameInfo(doc)   # (validated like a consumer would)
    return doc


# ---------------------------------------------------------------- pictures

def png_luma(path, step=8):
    """The mean brightness (0-255) of a PNG's pixels, every `step`-th pixel and row; None where it is not an 8-bit
    grey, RGB, grey+alpha or RGBA non-interlaced PNG. A way to tell a lit scene from a dark one, not a colour measure."""
    try:
        with open(path, 'rb') as f:
            data = f.read(64 << 20)
        if data[:8] != b'\x89PNG\r\n\x1a\n':
            return None
        pos, header, idat = 8, None, []
        while pos + 8 <= len(data):
            n, kind = struct.unpack('>I4s', data[pos:pos + 8])
            body = data[pos + 8:pos + 8 + n]
            pos += 12 + n
            if kind == b'IHDR':
                header = struct.unpack('>IIBBBBB', body)
            elif kind == b'IDAT':
                idat.append(body)
            elif kind == b'IEND':
                break
        if not header:
            return None
        w, h, depth, ctype, _, _, interlace = header
        channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(ctype)
        if depth != 8 or channels is None or interlace or not w or not h or w * h > 64 << 20:
            return None
        raw = zlib.decompress(b''.join(idat))
        stride = w * channels
        prev, total, count, pos = bytearray(stride), 0, 0, 0
        for y in range(h):
            ft = raw[pos]
            line = bytearray(raw[pos + 1:pos + 1 + stride])
            pos += 1 + stride
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                b = prev[i]
                c = prev[i - channels] if i >= channels else 0
                if ft == 1:
                    line[i] = (line[i] + a) & 255
                elif ft == 2:
                    line[i] = (line[i] + b) & 255
                elif ft == 3:
                    line[i] = (line[i] + ((a + b) >> 1)) & 255
                elif ft == 4:
                    p = a + b - c
                    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                    line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
            prev = line
            if y % step == 0:
                for x in range(0, w, step):
                    px = line[x * channels:x * channels + channels]
                    luma = px[0] if channels <= 2 else (299 * px[0] + 587 * px[1] + 114 * px[2]) / 1000
                    total += luma
                    count += 1
        return round(total / count, 2) if count else None
    except (OSError, ValueError, zlib.error, IndexError, struct.error):
        return None


# ---------------------------------------------------------------- logs

class LogTail:
    """The game's log file: a mark now, the lines after it later."""

    def __init__(self, path):
        self.path = str(path)

    def mark(self):
        try:
            return os.path.getsize(self.path)
        except OSError:
            return 0

    def since(self, mark, limit=1 << 20):
        try:
            with open(self.path, 'rb') as f:
                f.seek(mark)
                text = f.read(limit).decode('utf-8', 'replace')
        except OSError:
            return []
        lines = text.split('\n')
        if lines and lines[-1] == '':
            lines.pop()
        elif lines:
            lines.pop()   # (a line still being written)
        return [re.sub(r'[\x00-\x1f\x7f]', '?', ln) for ln in lines]

    def wait(self, mark, pattern, seconds, nap=0.05):
        """The lines after mark once one of them matches pattern, or what there is when the time is out."""
        end = time.monotonic() + seconds
        rx = re.compile(pattern)
        while True:
            lines = self.since(mark)
            if any(rx.search(ln) for ln in lines) or time.monotonic() >= end:
                return lines
            time.sleep(nap)


def said(lines, limit=8):
    return [ln[:240] for ln in lines if 'cheats:' in ln][-limit:]


# ---------------------------------------------------------------- the tools

def snap(reply):
    """The part of a status reply the tools compare: the game's snapshot, or the bridge's own map before one exists."""
    g = reply.get('game') if isinstance(reply.get('game'), dict) else {}
    gf, rf = g.get('frame'), reply.get('frame')
    fresh = isinstance(gf, int) and isinstance(rf, int) and 0 <= rf - gf <= FRESH_FRAMES
    pos = g.get('pos') if isinstance(g.get('pos'), list) and len(g['pos']) == 3 else None
    return {'map': g.get('map') if gf is not None else reply.get('map'), 'age': g.get('age'), 'pos': pos,
            'life': g.get('life'), 'max_life': g.get('max_life'), 'rupees': g.get('rupees'),
            'event': g.get('event'), 'loading': g.get('loading'), 'state': reply.get('state'), 'fresh': fresh,
            'frame': rf, 'sample_frame': gf, 'prompt': g.get('prompt'), 'music': g.get('music'), 'facing': g.get('facing')}


def short(st):
    """The comparison fields of a snapshot, for a result's before and after."""
    keep = ('map', 'age', 'pos', 'life', 'max_life', 'rupees', 'event', 'loading', 'state', 'fresh', 'frame', 'facing')
    return {k: st.get(k) for k in keep}


def ready(st):
    """Link in control: a fresh snapshot (the game takes its Debug actions at his update), no event, nothing loading. The
    bridge's draw-count `state` guess is not used: a quiet scene can look like a menu."""
    return bool(st.get('fresh') and st.get('event') is False and st.get('loading') is False and st.get('map'))


def dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


class Debug:
    """One game behind its control socket. `live` is the file HOS_INPUT_LIVE names (for time, items, mark), `log` the game's
    log, `info` a GameInfo (items, flag layout), `root` the run folder or `scratch` the folders in which the game's
    saves may be: the tools that change the game refuse unless its save folder is proved to be inside one of them."""

    def __init__(self, sock, live=None, log=None, info=None, root=None, scratch=(), ready_timeout=30.0):
        self.sock_path = str(sock)
        self.bridge = Bridge(sock)
        self.live = str(live) if live else None
        self.log = LogTail(log) if log else None
        self.info = info if isinstance(info, GameInfo) or info is None else GameInfo.load(info)
        self.root = os.path.realpath(root) if root else None
        self.scratch = [os.path.realpath(s) for s in ([self.root] if self.root else []) + list(scratch or ())]
        self.ready_timeout = ready_timeout
        self._last_live = 0.0
        self._disposable = None
        self._link = None          # the guest address of the field the bridge's position is read from (found by `warp`)

    # -- plumbing
    def close(self):
        self.bridge.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def ask(self, cmd, timeout=None, **args):
        return self.bridge.request(cmd, timeout=timeout, **args)

    def status(self):
        return snap(must(self.ask('status'), 'status'))

    def _presents(self, n, timeout=10):
        r = self.ask('wait', timeout=timeout, event='present', frames=n)
        if not r.get('ok') and r.get('error') != 'timeout':
            must(r, 'wait present')

    def wait_ready(self, timeout=None, calm=2):
        """Link in control (a fresh snapshot with no event playing and nothing loading), `calm` times in a row; the state."""
        end = time.monotonic() + (self.ready_timeout if timeout is None else timeout)
        run, st = 0, None
        while True:
            st = self.status()
            run = run + 1 if ready(st) else 0
            if run >= calm:
                return st
            if time.monotonic() >= end:
                raise DebugError('unavailable', 'Link is not in control (map %s, event %s, loading %s, fresh %s, state %s): '
                                 'the game takes these actions at his next update, in play' %
                                 (st.get('map'), st.get('event'), st.get('loading'), st.get('fresh'), st.get('state')),
                                 state=short(st))
            self._presents(6)

    def wait_play(self, timeout=300.0, press_every=2.0, calm_presents=30):
        """From the title: A until Link is in control (the way a boot to a loaded save goes), then the state."""
        end, last, calm = time.monotonic() + timeout, 0.0, 0
        while time.monotonic() < end:
            st = self.status()
            calm = calm + 6 if ready(st) else 0
            if calm >= calm_presents:
                return st
            if not ready(st) and (st.get('state') in ('menu', 'intro', 'play')) and time.monotonic() - last >= press_every:
                self.ask('press', buttons='A', frames=6, wait=False)
                last = time.monotonic()
            self._presents(6, timeout=30)
        raise DebugError('timeout', 'no control after %.0f s' % timeout)

    # -- the disposable guard
    def saves(self):
        r = self.ask('saves')
        if not r.get('ok'):
            return {'available': False, 'error': r.get('error'), 'message': r.get('message')}
        return {'available': True, 'path': r.get('path'), 'slots': r.get('slots') or [], 'account': r.get('account')}

    def disposable(self):
        """Is the game's save folder inside a folder that is throw-away (the run's own, or a scratch root given)?
        {verified, save_path, inside}; positive answers are kept."""
        if self._disposable and self._disposable['verified']:
            return self._disposable
        s = self.saves()
        path = os.path.realpath(s['path']) if s.get('available') and s.get('path') else None
        inside = next((r for r in self.scratch if path and (path == r or path.startswith(r + os.sep))), None)
        self._disposable = {'verified': bool(inside), 'save_path': path, 'inside': inside}
        return self._disposable

    def _guard(self, what):
        d = self.disposable()
        if d['verified']:
            return d
        if not self.scratch:
            raise DebugError('not_disposable', '%s: no run folder or scratch root was given, so the game\'s save folder cannot '
                             'be shown to be throw-away (--run <run folder>, or --scratch <folder the game\'s user folder is in>)' % what)
        if d['save_path'] is None:
            raise DebugError('not_disposable', '%s: the game has not opened its saves yet; wait for play and ask again' % what)
        raise DebugError('not_disposable', '%s: the game\'s save folder %s is not inside %s' %
                         (what, d['save_path'], ' or '.join(self.scratch)))

    # -- the live input file and the log
    def _need_live(self):
        if not self.live:
            raise DebugError('unavailable', 'this run has no live input file: start the game with HOS_INPUT_LIVE=<file> '
                             '(the Debug tab\'s time, items and mark are `!cheat` lines in it)')
        return self.live

    def _send_line(self, line):
        gap = LIVE_GAP - (time.monotonic() - self._last_live)
        if gap > 0:
            time.sleep(gap)
        with open(self._need_live(), 'a', encoding='utf-8') as f:
            f.write(line + '\n')
            f.flush()
        self._last_live = time.monotonic()

    def _cheat(self, what, number, expect, settle=3, seconds=3.0):
        """`!cheat <number>` once Link is in control; (state before, the game's `cheats:` lines)."""
        self._guard(what)
        self._need_live()
        before = self.wait_ready()
        mark = self.log.mark() if self.log else None
        self._send_line('!cheat %d' % number)
        self._presents(settle)
        lines = self.log.wait(mark, expect, seconds) if self.log else []
        return before, lines

    # -- teleport and age
    def destinations(self):
        r = must(self.ask('teleport'), 'teleport list')
        return [{'index': d.get('index'), 'child': d.get('child'), 'adult': d.get('adult')} for d in r.get('destinations') or []]

    def resolve_destination(self, to, age=None):
        """(index, row, which ages name it): a destination by index or by one of its maps' names (any case)."""
        rows = self.destinations()
        if isinstance(to, int) or (isinstance(to, str) and to.isdigit()):
            row = next((r for r in rows if r['index'] == int(to)), None)
            if row:
                return row['index'], row, [a for a in ('child', 'adult') if row[a]]
        else:
            want = str(to).lower().replace('-', '_')
            hit = [(r, [a for a in ('child', 'adult') if r[a] and r[a].lower() == want]) for r in rows]
            hit = [(r, ages) for r, ages in hit if ages]
            if hit:
                return hit[0][0]['index'], hit[0][0], hit[0][1]
        raise DebugError('bad_request', 'no destination %r: `destinations` lists the game\'s own (index or a map name)' % (to,))

    def _arrive(self, wait_cmd, want, limit):
        """After a sent map change: the wait the bridge offers, then a calm in-control state that satisfies want(st)."""
        r = self.ask('wait', timeout=limit, **wait_cmd)
        end = time.monotonic() + limit
        st = None
        while time.monotonic() < end:
            st = self.status()
            if want(st) and ready(st):
                return st, r.get('ok', False)
            self._presents(6)
        return st, r.get('ok', False)

    def teleport(self, to, arrive=60.0, retry=40.0, settle=None):
        """The Debug tab's teleport: Link, in his current age, to a destination the game lists (index or a map's name).
        Asked again while the game is busy (an event playing, a map loading, another teleport within 8 s). `settle` presents
        (default SETTLE) are waited after the arrival, so a picture is not the black of the fade-in."""
        self._guard('teleport')
        index, row, ages = self.resolve_destination(to)
        before = self.wait_ready()
        age = before.get('age')
        if age not in ages and age in ('child', 'adult'):
            raise DebugError('refused', 'destination %s has no map for the %s (it has %s): `age` first' %
                             (index, age, '/'.join(ages)), destination=row)
        end, reply = time.monotonic() + retry, None
        while True:
            reply = self.ask('teleport', timeout=10, to=index)
            if reply.get('ok'):
                break
            msg = reply.get('message', '')
            if reply.get('error') == 'refused' and any(p in msg for p in ('no map', 'no such destination', 'could not be')):
                raise DebugError('refused', 'teleport: refused: ' + msg, destination=row)
            if reply.get('error') in ('refused', 'timeout', 'cancelled', 'busy') and time.monotonic() < end:
                self._presents(60 if 'another teleport' in msg else 20)
                continue
            must(reply, 'teleport')
        target = reply.get('map')
        reload_ = bool(before.get('map')) and before.get('map') == target
        wait = {'event': 'loading_end'} if reload_ else {'event': 'map', 'map': target}
        after, waited = self._arrive(wait, lambda st: (st.get('map') or '').lower() == (target or '').lower(), arrive)
        same_map = bool(after and ready(after) and (after.get('map') or '').lower() == (target or '').lower())
        ok = same_map and (waited or not reload_)   # (a reload is a map change only when the load was seen)
        moved = round(dist(before['pos'], after['pos']), 2) if before.get('pos') and after and after.get('pos') else None
        also = [r['index'] for r in self.destinations() if r['index'] != index and any(r[a] and r[a] == row[a] for a in ('child', 'adult'))]
        settle = SETTLE if settle is None else settle
        if ok and settle:
            self._presents(settle)
            after = self.status()
        out = {'ok': ok, 'action': 'teleport', 'effect': 'verified' if ok else 'not_applied', 'destination': row,
               'sent': reply.get('sent'), 'accepted': reply.get('accepted'), 'map': target, 'reload': reload_, 'moved_m': moved,
               'settle': settle, 'before': short(before), 'after': short(after or {})}
        if also:
            out['same_map_destinations'] = also   # (other entrances of this map: the game lists them as destinations of their own)
        return out

    def age(self, to, arrive=60.0, retry=40.0, settle=None):
        """The Debug tab's Switch age: Link flipped and the current map reloaded in the other age (`settle`: as `teleport`)."""
        if to not in ('child', 'adult'):
            raise DebugError('bad_request', 'age: child or adult')
        self._guard('age')
        before = self.wait_ready()
        if before.get('age') == to:
            return {'ok': True, 'action': 'age', 'effect': 'verified', 'sent': False, 'note': 'Link is that age already',
                    'before': short(before), 'after': short(before)}
        end = time.monotonic() + retry
        while True:
            reply = self.ask('age', timeout=10, to=to)
            if reply.get('ok'):
                break
            msg = reply.get('message', '')
            if reply.get('error') == 'refused' and any(p in msg for p in ('not in the game', 'could not be')):
                raise DebugError('refused', 'age: refused: ' + msg)
            if reply.get('error') in ('refused', 'timeout', 'cancelled', 'busy') and time.monotonic() < end:
                self._presents(60 if 'another teleport' in msg else 20)
                continue
            must(reply, 'age')
        if reply.get('sent') is False:
            after = self.status()
        else:
            after, _ = self._arrive({'event': 'loading_end'}, lambda st: st.get('age') == to, arrive)
        ok = bool(after and ready(after) and after.get('age') == to)
        settle = SETTLE if settle is None else settle
        if ok and settle and reply.get('sent') is not False:
            self._presents(settle)
            after = self.status()
        return {'ok': ok, 'action': 'age', 'effect': 'verified' if ok else 'not_applied', 'sent': reply.get('sent'),
                'accepted': reply.get('accepted'), 'map': reply.get('map'), 'settle': settle, 'before': short(before), 'after': short(after or {})}

    # -- the Debug tab through the live input file
    def _number(self, key, offset=0):
        if not self.info:
            raise DebugError('unavailable', 'no game info: `game-info --source <game checkout>` makes the file (--info)')
        return self.info.actions[key] + offset

    def shot(self, path=None, timeout=30):
        args = {'path': os.path.abspath(path)} if path else {}
        r = must(self.ask('shot', timeout=timeout, **args), 'shot')
        p = r.get('path')
        return {'ok': True, 'action': 'shot', 'effect': 'verified', 'path': p, 'width': r.get('width'), 'height': r.get('height'),
                'luma': png_luma(p) if p and os.path.isfile(p) else None, 'frame': r.get('frame')}

    def time(self, hour, look=False):
        """The world clock to hour:00. The game logs the request; the clock itself is not on the bridge, so the effect is
        `requested`. With look, a picture before and after and their mean brightness (a night is darker than a noon)."""
        if not isinstance(hour, int) or isinstance(hour, bool):
            raise DebugError('bad_request', 'time: an hour, 0 to 23')
        self._guard('time')
        hours = self.info.actions['time_hours'] if self.info else 24
        if not 0 <= hour < hours:
            raise DebugError('bad_request', 'time: an hour, 0 to %d' % (hours - 1))
        shots = []
        if look:
            tmp = tempfile.mkdtemp(prefix='hsdebug-')
            shots.append(self.shot(os.path.join(tmp, 'before.png')))
        before, lines = self._cheat('time', self._number('time_base', hour), r'cheats: (requested|world clock)')
        if look:
            self._presents(30)
            shots.append(self.shot(os.path.join(tmp, 'after.png')))
        text = ' '.join(lines)
        if 'requested %02d:00' % hour in text:
            effect = 'requested'
        elif 'world clock unavailable' in text:
            effect = 'not_applied'
        else:
            effect = 'unconfirmed'
        out = {'ok': effect == 'requested', 'action': 'time', 'effect': effect, 'hour': hour, 'game_said': said(lines),
               'before': short(before)}
        if look:
            out['shots'] = shots
            out['luma'] = [s['luma'] for s in shots]
        if effect == 'unconfirmed':
            out['note'] = 'no `cheats:` line in time; the game keeps the line and acts on it at Link\'s next update'
        return out

    def _flag_value(self, name):
        got = self.flag_get(name)
        return got['flags'].get(name)

    def _item_flag(self, item, which):
        tpl = self.info.item_flags.get(which) if self.info else None
        if not tpl:
            return None
        return self._flag_value(tpl.format(name=item['name']))

    def give(self, item, change=1):
        """Add (change > 0) or remove a quantity item of the Debug tab's editor; the amount comes back from the item's count
        flag when game info has `item_flags`, else from the game's own `had/now` line (`requested`)."""
        if not self.info:
            raise DebugError('unavailable', 'no game info: the editor\'s item list is in the game\'s source (`game-info`)')
        row = self.info.item(item)
        if row['kind'] != 1:
            raise DebugError('bad_request', '%s is an item Link has or has not: `toggle`' % row['name'])
        bias = self.info.actions['item_bias']
        if not isinstance(change, int) or isinstance(change, bool) or change == 0 or not -bias <= change < 128 - bias:
            raise DebugError('bad_request', 'change: a whole number from %d to %d, not 0' % (-bias, 127 - bias))
        number = (self.info.actions['item_base'] + row['index'] * self.info.actions['item_stride'] + bias + change)
        return self._item_action('give', row, number, change)

    def toggle(self, item):
        """Unlock an item Link lacks, or take away one he has (the editor's Enter on an equipment, song or quest card)."""
        if not self.info:
            raise DebugError('unavailable', 'no game info: the editor\'s item list is in the game\'s source (`game-info`)')
        row = self.info.item(item)
        number = self.info.actions['item_base'] + row['index'] * self.info.actions['item_stride'] + self.info.actions['item_toggle']
        return self._item_action('toggle', row, number, None)

    def _item_flag_name(self, row, quantity):
        """(which, flag name) the item's possession or count is read from. A quantity: the count flag. A have/lack item: the count flag
        too when the game has one (a pouch's count is the truth), else the have flag (set when an item is got, and the game never
        clears it when one is taken away, so it proves a got item and not a taken one)."""
        flags = self.info.item_flags
        count = flags.get('count').format(name=row['name']) if flags.get('count') else None
        have = flags.get('have').format(name=row['name']) if flags.get('have') else None
        if quantity:
            return 'count', count
        if count and self._flag_value(count) is not None:
            return 'count', count
        return ('have', have) if have else ('count', count)

    def _item_action(self, action, row, number, change):
        self._guard(action)
        quantity = change is not None
        which, flag = self._item_flag_name(row, quantity)
        count_before = self._flag_value(flag) if flag else None
        before, lines = self._cheat(action, number, r'cheats: (inventory|song|pouch)[^\n]*\((had|event)')
        text = ' '.join(lines)
        m = re.search(r'\(had (-?\d+), now (-?\d+)', text)
        out = {'action': action, 'item': {'name': row['name'], 'label': row['label'], 'index': row['index']},
               'game_said': said(lines), 'had': int(m.group(1)) if m else None, 'now_when_said': int(m.group(2)) if m else None,
               'before': short(before)}
        if not lines:
            out.update(ok=False, effect='unconfirmed', note='no `cheats:` line: the game keeps the line and acts at Link\'s next update')
            return out
        if flag is None:
            out.update(ok=True, effect='requested',
                       note='the game asked for the change (its log); no %s flag is configured to read it back' % which)
        else:
            self._presents(30)   # (the pickup is an event: its count lands a few frames after the game says it asked)
            count_after = self._flag_value(flag)
            key = 'count' if quantity else 'have'
            out[key + '_before'], out[key + '_after'], out['read_from'] = count_before, count_after, flag
            if count_after is None or count_before is None:
                out.update(ok=False, effect='unconfirmed', note='the %s flag could not be read' % which)
            elif quantity and count_after == count_before + change:
                out.update(ok=True, effect='verified')
            elif quantity and (count_after - count_before) * change > 0:
                out.update(ok=True, effect='partial', note='the amount moved less than asked (the pouch\'s capacity)')
            elif not quantity and bool(count_after) != bool(count_before):
                out.update(ok=True, effect='verified')
            elif not quantity and which == 'have' and count_before:
                out.update(ok=True, effect='requested',
                           note='the have flag is not cleared when the game takes an item away: the game\'s log line is all there is')
            elif quantity and change > 0:
                out.update(ok=False, effect='not_applied',
                           note='the count did not move: the pouch is at its capacity, or Link has no pouch for it yet (an upgrade '
                                'item, such as a bag, a quiver or a wallet, comes first: `toggle` it; unlocking it fills its pouch '
                                'to the capacity, so take some away to set an exact count)')
            else:
                out.update(ok=False, effect='not_applied')
        out['after'] = short(self.status())
        return out

    def mark(self):
        before, lines = self._cheat('mark', self._number('mark'), r'cheats: (marked position|no mark)')
        m = re.search(r'marked position (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)', ' '.join(lines))
        marked = [float(x) for x in m.groups()] if m else None
        return {'ok': bool(marked), 'action': 'mark', 'effect': 'requested' if marked else 'unconfirmed', 'marked': marked,
                'game_said': said(lines), 'before': short(before)}

    def return_to_mark(self, tolerance=1.5):
        before, lines = self._cheat('return', self._number('return'), r'cheats: (returned to|no mark)', seconds=4.0)
        text = ' '.join(lines)
        m = re.search(r'returned to (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)', text)
        if not m:
            return {'ok': False, 'action': 'return', 'effect': 'not_applied' if 'no mark' in text else 'unconfirmed',
                    'game_said': said(lines), 'before': short(before)}
        target = [float(x) for x in m.groups()]
        self._presents(20)
        after = self.status()
        near = bool(after.get('pos')) and dist(after['pos'], target) <= tolerance
        return {'ok': near, 'action': 'return', 'effect': 'verified' if near else 'not_applied', 'target': target,
                'distance': round(dist(after['pos'], target), 2) if after.get('pos') else None, 'game_said': said(lines),
                'before': short(before), 'after': short(after)}

    # -- flags: read by the bridge's subscription, written in guest memory (the second opt-in)
    def flag_get(self, *names):
        """Flag values by name or `0x` + 8 hex digits (or an alias of the game info): one subscription of its own, the first
        sample taken at Link's next update. No memory opt-in. Raises 'unavailable' when Link is not being updated."""
        names = [self.info.flag_name(n) if self.info else n for n in names]
        if not 1 <= len(names) <= 64 or any(not FLAG_NAME.match(n) for n in names):
            raise DebugError('bad_request', 'flag names: 1 to 64 of 1-47 letters, digits, _ or . (or 0x and 8 hex digits)')
        sub = Bridge(self.sock_path)
        try:
            r = must(sub.request('subscribe', events=['oot'], every=1, flags=names, changes=False), 'subscribe')
            ev = sub.event('oot', 8.0)
            try:
                sub.request('unsubscribe')
            except DebugError:
                pass
        finally:
            sub.close()
        if not ev:
            raise DebugError('unavailable', 'no sample in 8 s: Link is not being updated (title, pause or a load)')
        game = ev.get('game') or {}
        return {'ok': True, 'action': 'flag_get', 'effect': 'verified', 'flags': game.get('flags') or {},
                'frame': ev.get('frame'), 'sample_frame': game.get('frame'), 'subscribed': r.get('events')}

    def _mem(self, cmd, **args):
        r = self.ask(cmd, **args)
        if not r.get('ok') and r.get('error') == 'forbidden':
            raise DebugError('forbidden', '%s: guest memory is off: start the game with HOS_CONTROL_MEM=rw (a throw-away save)' % cmd)
        return must(r, cmd)

    def _mem_read(self, addr, size):
        data = bytes.fromhex(self._mem('mem_read', addr=addr, size=size, format='hex')['data'])
        if len(data) != size:
            raise DebugError('failed', 'mem_read returned %d of %d bytes' % (len(data), size))
        return data

    def _u(self, addr, width):
        return int.from_bytes(self._mem_read(addr, width), 'little')

    def locate(self, name, kind=None):
        """(kind, value address) of a flag in the game's containers; the lookup the game's own debug tools use."""
        if not self.info or not self.info.layout:
            raise DebugError('unavailable', 'no flag container layout: `game-info --source <game checkout>` has it')
        lay = self.info.layout
        h = int(name, 16) if re.fullmatch(r'0x[0-9a-fA-F]{8}', name) else murmur3(name)
        mgr = self._u(self._u(lay['holder'], 8), 8)
        if not mgr:
            raise DebugError('unavailable', 'the game\'s data manager is not there yet')
        box = lay['box']
        for k in ([kind] if kind else [k for k in KINDS_ORDER if k in lay['kinds']]):
            geom = lay['kinds'][k]
            base = mgr + geom['at']
            count, entries = self._u(base + box['count'], 4), self._u(base + box['entries'], 8)
            table, size = self._u(base + box['table'], 8), self._u(base + box['size'], 4)
            if not entries or not table or not 0 < size <= 1 << 22:
                continue
            slot = h % size
            for _ in range(size):
                key, index = struct.unpack('<II', self._mem_read(table + slot * 8, 8))
                if key == 0:
                    break
                if key == h:
                    if index < count:
                        return k, entries + index * geom['stride'] + geom['value'], h
                    break
                slot = 0 if slot + 1 == size else slot + 1
        raise DebugError('bad_request', 'no flag %s in the game\'s %s containers' % (name, kind or '/'.join(KINDS_ORDER)))

    @staticmethod
    def _pack(kind, value):
        if kind == 'bool':
            return bytes([1 if value else 0])
        if kind == 'int':
            return struct.pack('<i', int(value))
        if kind == 'uint':
            return struct.pack('<I', int(value))
        return struct.pack('<f', float(value))

    @staticmethod
    def _unpack(kind, data):
        return {'bool': lambda d: d[0], 'int': lambda d: struct.unpack('<i', d)[0], 'uint': lambda d: struct.unpack('<I', d)[0],
                'float': lambda d: round(struct.unpack('<f', d)[0], 3)}[kind](data)

    def flag_set(self, name, value, kind=None, settle=20):
        """Write a flag's live value in guest memory (HOS_CONTROL_MEM=rw; the way the game's own debug tools set a Bool flag),
        then read it back from memory and from the bridge's flag subscription. `not_applied` when the game gave it back."""
        self._guard('flag set')
        real = self.info.flag_name(name) if self.info else name
        if not FLAG_NAME.match(real):
            raise DebugError('bad_request', 'flag name: 1-47 letters, digits, _ or . (or 0x and 8 hex digits)')
        k, addr, h = self.locate(real, kind)
        width = KIND_WIDTH[k]
        before = self._unpack(k, self._mem_read(addr, width))
        try:
            data = self._pack(k, value)
        except (struct.error, ValueError, OverflowError, TypeError):
            raise DebugError('bad_request', 'flag set: %r does not fit a %s flag' % (value, k)) from None
        r = self._mem('mem_write', addr=addr, hex=data.hex())
        after_mem = self._unpack(k, self._mem_read(addr, width))
        self._presents(settle)
        try:
            after_flag = self.flag_get(real)['flags'].get(real)
        except DebugError:
            after_flag = None
        want = self._unpack(k, data)
        ok = after_flag == want if after_flag is not None else after_mem == want
        return {'ok': ok, 'action': 'flag_set', 'effect': 'verified' if ok else 'not_applied', 'name': name, 'hash': '0x%08x' % h,
                'kind': k, 'before': before, 'written': want, 'wrote': r.get('wrote'), 'after_memory': after_mem,
                'after_flag': after_flag,
                'note': None if ok else 'the value did not stay: the game writes it itself (it is recomputed or queued every frame)'}

    def set_state(self, **values):
        """life, max_life, rupees, magic ...: the game info's aliases of the flags behind them, through flag_set."""
        out = []
        for key, value in values.items():
            if not self.info or key not in self.info.names:
                raise DebugError('bad_request', '%s: no alias in the game info\'s names (the flag behind it is private)' % key)
            res = self.flag_set(key, value)
            st = self.status()
            res['state'] = {k: st.get(k) for k in ('life', 'max_life', 'rupees')}
            out.append(res)
        return out

    # -- a coordinate warp: Link's position written into guest memory
    @staticmethod
    def _find_triples(buf, want, tol):
        """Offsets (4-byte aligned) in buf where three little-endian floats are each within tol of want."""
        n = len(buf) // 4
        vals = struct.unpack_from('<%df' % n, buf)
        return [i * 4 for i in range(n - 2) if abs(vals[i] - want[0]) <= tol and abs(vals[i + 1] - want[1]) <= tol and abs(vals[i + 2] - want[2]) <= tol]

    def _probe_field(self, addr, cur, seen=None):
        """Is the float triple at addr the one the bridge's position comes from? Moved by 0.25 m, the position read back must follow it (read
        after 3 presents and again after 15); the triple is put back as it was either way (a copy somewhere else is not followed).
        `seen`, a list, gets what was read back."""
        orig = self._mem_read(addr, 12)
        self._mem('mem_write', addr=addr, hex=struct.pack('<3f', cur[0] + 0.25, cur[1], cur[2]).hex())
        reads = []
        for n in (3, 12):
            self._presents(n)
            reads.append(self.status().get('pos'))
        self._mem('mem_write', addr=addr, hex=orig.hex())
        if seen is not None:
            seen.append(reads)
        return any(m and abs(m[0] - (cur[0] + 0.25)) < 0.1 and abs(m[1] - cur[1]) < 0.1 and abs(m[2] - cur[2]) < 0.1 for m in reads)

    def _link_field(self, pos, scan_mb, scan_seconds, chunk):
        """(address, candidates probed, MB scanned) of Link's position field. Remembered: a later call only checks it still holds his position.
        Found by scanning the guest memory around the flag containers (the game's heap) for his reported position, outward, and probing each
        match by effect. Nothing here knows an address of the game."""
        if self._link is not None:
            try:
                cur = struct.unpack('<3f', self._mem_read(self._link, 12))
                if dist(cur, pos) <= 0.05:
                    return self._link, 0, 0.0
            except DebugError as e:
                if e.code in ('forbidden', 'unavailable'):
                    raise
            self._link = None
        if not self.info or not self.info.layout or 'life' not in self.info.names:
            raise DebugError('unavailable', 'warp: game info with the flag layout and the `life` alias is needed (the scan starts at the flag containers)')
        anchor = self.locate(self.info.flag_name('life'))[1]
        base0 = anchor & ~(chunk - 1)
        end, probed, scanned, tried = time.monotonic() + scan_seconds, 0, 0, []
        for k in range(2 * int(scan_mb * 1048576 // chunk) + 1):
            base = base0 + ((k + 1) // 2) * chunk * (1 if k % 2 else -1)
            if base < 0:
                continue
            if time.monotonic() > end:
                break
            parts = [(base, chunk)]
            try:
                bufs = [(base, self._mem_read(base, chunk))]
            except DebugError as e:
                if e.code in ('forbidden', 'unavailable', 'timeout'):
                    raise
                bufs = []    # (a hole in the mapping: its pieces that are there are read)
                for sub in range(base, base + chunk, 0x1000):
                    try:
                        bufs.append((sub, self._mem_read(sub, 0x1000)))
                    except DebugError as e2:
                        if e2.code in ('forbidden', 'unavailable', 'timeout'):
                            raise
            scanned += sum(len(b) for _, b in bufs)
            for at, buf in bufs:
                for off in self._find_triples(buf, pos, 0.03):
                    if probed >= 16:
                        break
                    probed += 1
                    seen = []
                    if self._probe_field(at + off, pos, seen):
                        self._link = at + off
                        return self._link, probed, round(scanned / 1048576, 1)
                    tried.append({'at': '%+#x' % (at + off - anchor), 'read_back': seen[-1]})
        raise DebugError('failed', 'warp: no field that moves his reported position was found in %.1f MB around the flag containers (%d matches probed)' %
                         (scanned / 1048576, probed), candidates=probed, tried=tried)

    def _watch_target(self, target, watch):
        """Link's reported position read for `watch` seconds against a target: (samples, effect, note)."""
        samples, t_w = [], time.monotonic()
        while True:
            st = self.status()
            p = st.get('pos')
            samples.append({'t': round(time.monotonic() - t_w, 2), 'pos': p, 'dist': round(dist(p, target), 2) if p else None, 'facing': st.get('facing')})
            if time.monotonic() - t_w >= watch:
                break
            self._presents(6)
            time.sleep(0.1)
        near = [x_ for x_ in samples if x_['dist'] is not None and x_['dist'] <= 0.75]
        last = samples[-1]
        if near:
            # (the bridge reports the snapshot of Link's previous update: the readings before the first one at the target are the old place, not a failure)
            first = samples.index(near[0])
            for x_ in samples[:first]:
                x_['stale'] = True
            kept = samples[first:]
            if all(x_['dist'] is not None and x_['dist'] <= 0.75 for x_ in kept):
                return samples, 'verified', None
            return samples, 'partial', ('Link was at the target for %d of %d samples and then at %s (%.1f m away): the game put him back or moved him '
                                        '(a wall, the floor, a drop)' % (len(near), len(kept), last['pos'], last['dist'] if last['dist'] is not None else -1))
        return samples, 'not_applied', 'his position never read back within 0.75 m of the target (first sample %s): the game put him back at once' % (samples[0]['pos'],)

    def _warp_place(self, target, facing, watch, before, tp):
        """warp by the game's own return-to-mark path: `!place X Y Z` in the live file (a command only a patched build has), then the log's "returned to" line."""
        self._need_live()
        mark = self.log.mark() if self.log else None
        self._send_line('!place %.4f %.4f %.4f' % tuple(target))
        self._presents(3)
        lines = self.log.wait(mark, r'cheats: returned to', 3.0) if self.log else []
        out = {'action': 'warp', 'method': 'place', 'target': target, 'facing_asked': facing, 'game_said': said(lines), 'before': short(before)}
        if tp:
            out['teleport'] = {k: tp.get(k) for k in ('effect', 'map', 'destination', 'after')}
        if not lines:
            out.update(ok=False, effect='not_applied', samples=[], after=short(self.status()),
                       note='the game gave no "returned to" line: this build has no `!place` command (the patch that adds it is not in it) or Link was not '
                            'being updated')
            return out
        samples, effect, note = self._watch_target(target, watch)
        notes = [n for n in (note, 'facing was not set: the game\'s return-to-mark does not turn Link' if facing is not None else None) if n]
        out.update(ok=effect != 'not_applied', effect=effect, samples=samples, facing_seen=samples[-1].get('facing'), after=short(self.status()))
        if notes:
            out['note'] = '; '.join(notes)
        return out

    def warp(self, x, y, z, facing=None, to=None, watch=2.0, method='place', scan_mb=64, scan_seconds=60.0, chunk=0x40000):
        """Put Link at x, y, z (metres, the frame of the map he is in), after a teleport to `to` (a destination index or a map name).
        method 'place' (default): the live file's `!place X Y Z`, which the game answers by its own return-to-mark path (needs a build with
        that command; a build without it says nothing and the result is `not_applied`); it does not turn Link. method 'memory' (experimental, did not work in the first real game): his position and rotation
        written into guest memory (HOS_CONTROL_MEM=rw), `facing` degrees (0 toward +z, 90 toward +x). Then his position is read back for `watch` seconds: `verified` when it stayed at the target, `partial` when it was there and
        the game moved him (a wall, the floor, a drop), `not_applied` when it never was. The facing is reported, not judged."""
        vals = [x, y, z]
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or abs(v) > 1e5 for v in vals):
            raise DebugError('bad_request', 'warp: x, y, z are finite numbers of metres, at most 100000 either way')
        if facing is not None and (isinstance(facing, bool) or not isinstance(facing, (int, float)) or not math.isfinite(facing)):
            raise DebugError('bad_request', 'warp: facing is a number of degrees (0 toward +z, 90 toward +x)')
        if method not in ('place', 'memory'):
            raise DebugError('bad_request', "warp: method is 'place' (the game's return-to-mark) or 'memory'")
        target = [float(v) for v in vals]
        self._guard('warp')
        tp = None
        if to is not None:
            tp = self.teleport(to)
            if not tp['ok']:
                return {'ok': False, 'action': 'warp', 'effect': 'not_applied', 'note': 'the teleport to %s did not arrive: nothing was written' % to, 'teleport': tp}
        before = self.wait_ready()
        if not before.get('pos'):
            raise DebugError('unavailable', 'warp: the game gives no position for Link (he is not being updated)')
        if method == 'place':
            return self._warp_place(target, facing, watch, before, tp)
        t0 = time.monotonic()
        addr, candidates, scanned = self._link_field(before['pos'], scan_mb, scan_seconds, chunk)
        found_in = round(time.monotonic() - t0, 1)
        self._mem('mem_write', addr=addr, hex=struct.pack('<3f', *target).hex())
        if facing is not None:
            yaw = math.radians(facing)
            c, s_ = math.cos(yaw), math.sin(yaw)
            self._mem('mem_write', addr=addr + LINK_ROT_AFTER_POS, hex=struct.pack('<9f', c, 0, s_, 0, 1, 0, -s_, 0, c).hex())
        samples, effect, note = self._watch_target(target, watch)
        last = samples[-1]
        out = {'ok': effect != 'not_applied', 'action': 'warp', 'effect': effect, 'target': target, 'facing_asked': facing, 'facing_seen': last.get('facing'),
               'address': hex(addr), 'candidates': candidates, 'scanned_mb': scanned, 'found_in_s': found_in, 'samples': samples,
               'before': short(before), 'after': short(self.status())}
        if tp:
            out['teleport'] = {k: tp.get(k) for k in ('effect', 'map', 'destination', 'after')}
        if note:
            out['note'] = note
        return out

    # -- options
    def option_get(self, name=None):
        r = must(self.ask('option_get', **({'name': name} if name else {})), 'option_get')
        return {'ok': True, 'action': 'option_get', 'effect': 'verified', 'option': r.get('option'), 'options': r.get('options')}

    def option_set(self, name, value):
        """A settings row through the menu's own setter (debug_tools, damage_taken, transition_autosave, ...)."""
        self._guard('option set')
        if isinstance(value, str):
            value = {'true': True, 'false': False}.get(value.lower(), value)
            if isinstance(value, str):
                try:
                    value = int(value)
                except ValueError:
                    value = float(value)
        r = must(self.ask('option_set', name=name, value=value), 'option_set')
        now = (r.get('option') or {}).get('value')
        want = int(value) if isinstance(value, bool) else value
        ok = now == want
        return {'ok': ok, 'action': 'option_set', 'effect': 'verified' if ok else 'not_applied', 'name': name, 'was': r.get('was'),
                'asked': value, 'option': r.get('option')}

    # -- input (thin)
    def press(self, buttons, frames=8):
        r = must(self.ask('press', timeout=30, buttons=buttons, frames=frames, exclusive=True), 'press')
        return {'ok': True, 'action': 'press', 'effect': 'requested', 'start': r.get('start'), 'end': r.get('end')}

    def stick(self, x, y, frames=8, which='L'):
        r = must(self.ask('stick', timeout=30, stick=which, x=x, y=y, frames=frames, exclusive=True), 'stick')
        return {'ok': True, 'action': 'stick', 'effect': 'requested', 'start': r.get('start'), 'end': r.get('end')}

    def release(self):
        r = must(self.ask('release'), 'release')
        return {'ok': True, 'action': 'release', 'effect': 'verified', 'released': r.get('released')}

    # -- what is there
    def capabilities(self):
        """What this game and this run can do, found by asking: bridge commands, the memory level, the live file, the
        Debug tools switch, the game info loaded, whether the game's saves are throw-away."""
        try:
            r = must(self.ask('status'), 'status')
        except DebugError as e:
            return e.as_result('capabilities')
        cmds = {'teleport': self.ask('teleport'), 'option_get': self.ask('option_get'), 'saves': self.ask('saves'),
                'age': self.ask('age', to='nonsense'), 'coop_save': self.ask('coop_save', action='status')}
        caps = {'version': r.get('version'), 'renderer': r.get('renderer'), 'protocol': r.get('protocol'),
                **{k: v.get('error') != 'unknown_cmd' for k, v in cmds.items()}}
        # (the write check comes before its arguments are read: `forbidden` below rw, `bad_request` at rw)
        read, write = self.ask('mem_read', addr=0x80000000, size=8), self.ask('mem_write', addr=0, hex='')
        if read.get('error') == 'forbidden':
            caps['memory'] = 'off'
        elif read.get('error') == 'unavailable' and write.get('error') == 'unavailable':
            caps['memory'] = 'unavailable'
        else:
            caps['memory'] = 'ro' if write.get('error') == 'forbidden' else 'rw'
        option = self.ask('option_get', name='debug_tools')
        return {'ok': True, 'action': 'capabilities', 'effect': 'verified', 'bridge': caps, 'state': short(snap(r)),
                'debug_tools_option': (option.get('option') or {}).get('value') if option.get('ok') else None,
                'live_input': {'path': self.live, 'present': bool(self.live and os.path.exists(self.live))},
                'log': self.log.path if self.log else None,
                'game_info': {'loaded': bool(self.info), 'items': len(self.info.items) if self.info else 0,
                              'layout': bool(self.info and self.info.layout), 'aliases': sorted(self.info.names) if self.info else []},
                'disposable': self.disposable()}

    # -- snapshot and restore: a copy of the game's save slots (the game has no state snapshot)
    def snapshot(self, dest, wait_save=0):
        return snapshot(self, dest, wait_save=wait_save)

    def restore(self, snapshot_dir, relaunch=True, into=None):
        return restore(snapshot_dir, into=into, debug=self if relaunch else None)

    # -- one call for a scene: age, place, time, items, flags
    def setup(self, to=None, age=None, hour=None, give=None, toggle=(), flags=None, life=None, rupees=None, keep_going=False):
        """Put Link at a place, an age and a time with given items, in a few seconds: each step's result, then the final state.
        Order: age, place, time, toggles, items, flags, life, rupees (an upgrade first: a pouch has room only once Link has it,
        a bomb bag before bombs). `give` is {item: change}. Stops at the first step that is not
        ok unless keep_going."""
        t0, steps = time.monotonic(), []

        def run(fn, *a, **kw):
            try:
                res = fn(*a, **kw)
            except DebugError as e:
                res = e.as_result(fn.__name__)
            steps.append(res)
            return res.get('ok', True) or keep_going
        go = True
        if to is not None and age is None:
            _, _, ages = self.resolve_destination(to)
            cur = self.wait_ready().get('age')
            if cur not in ages and ages:
                age = ages[0]
        if age and go:
            go = run(self.age, age)
        if to is not None and go:
            go = run(self.teleport, to)
        if hour is not None and go:
            go = run(self.time, hour)
        for name in toggle:
            if go:
                go = run(self.toggle, name)
        for name, change in (give or {}).items():
            if go:
                go = run(self.give, name, change)
        for name, value in (flags or {}).items():
            if go:
                go = run(self.flag_set, name, value)
        if life is not None and go:
            go = run(lambda: self.set_state(life=life)[0])
        if rupees is not None and go:
            go = run(lambda: self.set_state(rupees=rupees)[0])
        final = None
        try:
            final = short(self.status())
        except DebugError:
            pass
        return {'ok': all(s.get('ok', True) for s in steps), 'action': 'setup', 'effect': 'verified' if all(
            s.get('effect') in ('verified', 'requested') for s in steps) else 'partial', 'steps': steps, 'state': final,
            'seconds': round(time.monotonic() - t0, 1)}


# ---------------------------------------------------------------- snapshot / restore

SLOT = re.compile(r'^slot_[0-9]{2}$')


def _plain_tree(root):
    """(relative path, absolute path) of the plain files of a save folder; refuses links and other kinds."""
    out = []
    for top, dirs, files in os.walk(root, followlinks=False):
        for name in sorted(dirs + files):
            p = os.path.join(top, name)
            st = os.lstat(p)
            if stat.S_ISDIR(st.st_mode):
                continue
            if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
                raise DebugError('refused', 'a save folder with a link or a special file is not copied: %s' % p)
            out.append((os.path.relpath(p, root), p))
    return out


def _sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _copy_stable(src, dst, tries=3):
    """Copy one file; if it changes while it is read (the game writes it), again; (bytes, sha256)."""
    for _ in range(tries):
        before = os.stat(src)
        h = hashlib.sha256()
        os.makedirs(os.path.dirname(dst), mode=0o700, exist_ok=True)
        tmp = dst + '.part'
        with open(src, 'rb') as a, open(tmp, 'wb') as b:
            for chunk in iter(lambda: a.read(1 << 20), b''):
                h.update(chunk)
                b.write(chunk)
            b.flush()
            os.fsync(b.fileno())
        after = os.stat(src)
        if (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns):
            os.replace(tmp, dst)
            return after.st_size, h.hexdigest()
        os.unlink(tmp)
        time.sleep(0.3)
    raise DebugError('busy', 'a save file kept changing while it was copied (the game is writing): ask again: %s' % src)


def _slot_view(debug):
    """(saves reply, state, the newest slot's map as its caption names it, whether that is the map Link is in: True / False / None)."""
    s = debug.saves()
    if not s.get('available') or not s.get('path'):
        raise DebugError('unavailable', 'snapshot: the game has not opened its saves (%s)' % (s.get('message') or s.get('error')))
    state = debug.status()
    slots = s.get('slots') or []
    newest = next((x for x in slots if x.get('newest')), slots[0] if slots else None)
    caption = ((newest or {}).get('caption') or {}).get('map')
    slot_map = caption.split('/')[-1] if caption else None
    in_map = state.get('map') or ''
    matches = (slot_map.lower() == in_map.lower()) if slot_map and in_map else None
    return s, state, slot_map, matches


def snapshot(debug, dest, wait_save=0):
    """Copy the game's save folder (account, option and slot files; plain files only) into a new folder `dest` laid out as
    a game user folder (`dest/save/<user id>/...`, what `hs-run.sh --user` takes) with `snapshot.json`: the game's state
    now, each file's hash, the map the newest slot's caption names and whether that is the map Link is in. The game has no
    state snapshot: this is the slots as they are on disk; the game writes them at its own transitions, so a place, item or flag
    changed since is not in them. `effect` is `verified` only when the newest slot names the map Link is in, else `partial`.
    `wait_save` seconds are waited for the game to write a slot that does (a debug teleport may never make it save)."""
    if os.path.lexists(dest) and (not os.path.isdir(dest) or os.listdir(dest)):
        raise DebugError('refused', 'snapshot: %s exists and is not an empty folder' % dest)
    waited, t0 = None, time.monotonic()
    s, state, slot_map, matches = _slot_view(debug)
    while wait_save and matches is not True and time.monotonic() - t0 < wait_save:
        debug._presents(20)
        time.sleep(0.2)
        s, state, slot_map, matches = _slot_view(debug)
    if wait_save:
        waited = round(time.monotonic() - t0, 1)
    src = s['path']
    user_id = os.path.basename(src.rstrip('/'))
    files, root = [], os.path.join(dest, 'save', user_id)
    for rel, p in _plain_tree(src):
        if '/' in rel and not SLOT.match(rel.split('/')[0]):
            continue
        size, digest = _copy_stable(p, os.path.join(root, rel))
        files.append({'file': rel, 'bytes': size, 'sha256': digest})
    if not files:
        raise DebugError('failed', 'snapshot: no save files in %s' % src)
    slots = s.get('slots') or []
    newest_mtime = max((x.get('mtime') or 0 for x in slots), default=0)
    note = ('the slots as on disk: the newest names the map Link is in' if matches else
            'the newest slot does not name the map Link is in: the game had not saved here (it saves at its own transitions), so '
            'this place, and any item or flag changed since, is not saved in these files'
            if matches is False else 'the slots as on disk; whether the newest names the map Link is in could not be told')
    doc = {'schema': 1, 'taken_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'user_id': user_id,
           'state': short(state), 'files': files, 'slots': [{'slot': x.get('slot'), 'mtime': x.get('mtime'), 'newest': x.get('newest')} for x in slots],
           'newest_slot_age_s': round(time.time() - newest_mtime, 1) if newest_mtime else None, 'caption_matches_map': matches,
           'slot_map': slot_map, 'note': note}
    with open(os.path.join(dest, 'snapshot.json'), 'w', encoding='utf-8') as f:
        json.dump(doc, f, indent=1)
    for item in files:   # read back: the copy is what was hashed
        if _sha(os.path.join(root, item['file'])) != item['sha256']:
            raise DebugError('failed', 'snapshot: the copy of %s differs from what was read' % item['file'])
    out = {'ok': True, 'action': 'snapshot', 'effect': 'verified' if matches else 'partial', 'path': dest, 'user_dir': dest, 'files': len(files),
           'state': doc['state'], 'caption_matches_map': matches, 'slot_map': slot_map, 'newest_slot_age_s': doc['newest_slot_age_s'], 'note': note}
    if waited is not None:
        out['waited_s'] = waited
    return out


def restore(snapshot_dir, into=None, debug=None, boot_timeout=300.0):
    """Make a snapshot a running state again. into=NEWDIR: a new scratch user folder (the files, checked against their
    hashes), to start a game with `--user`. With `debug` (an attached game whose save folder is a throw-away one): its own
    save slots are replaced, the game started again (`relaunch`, the same process and socket), booted to play, and the map and age
    compared with the snapshot's."""
    try:
        with open(os.path.join(snapshot_dir, 'snapshot.json'), encoding='utf-8') as f:
            doc = json.load(f)
    except (OSError, ValueError) as e:
        raise DebugError('bad_request', 'restore: %s is not a snapshot (%s)' % (snapshot_dir, e)) from None
    src_root = os.path.join(snapshot_dir, 'save', doc['user_id'])
    for item in doc['files']:
        p = os.path.join(src_root, item['file'])
        if not os.path.isfile(p) or _sha(p) != item['sha256']:
            raise DebugError('failed', 'restore: %s does not match its hash: the snapshot is damaged' % item['file'])
    if debug is None:
        if not into:
            raise DebugError('bad_request', 'restore: --into NEWDIR (a new scratch user folder) or an attached game with --relaunch')
        if os.path.lexists(into) and (not os.path.isdir(into) or os.listdir(into)):
            raise DebugError('refused', 'restore: %s exists and is not an empty folder' % into)
        root = os.path.join(into, 'save', doc['user_id'])
        for item in doc['files']:
            _copy_stable(os.path.join(src_root, item['file']), os.path.join(root, item['file']))
        bad = [i['file'] for i in doc['files'] if _sha(os.path.join(root, i['file'])) != i['sha256']]
        return {'ok': not bad, 'action': 'restore', 'effect': 'verified' if not bad else 'not_applied', 'user_dir': into,
                'files': len(doc['files']), 'state_at_snapshot': doc['state'], 'bad': bad,
                'launch': 'hs-run.sh <copy> <tag> <seconds> --user %s' % into}
    d = debug._guard('restore')
    live_root = d['save_path']
    if os.path.basename(live_root.rstrip('/')) != doc['user_id']:
        raise DebugError('refused', 'restore: the game\'s save folder is for another user id than the snapshot\'s')
    for item in doc['files']:
        _copy_stable(os.path.join(src_root, item['file']), os.path.join(live_root, item['file']))
    up0 = debug.ask('status').get('uptime')
    r = debug.ask('relaunch')
    if not r.get('ok'):
        must(r, 'relaunch')
    debug.bridge.close()
    sent_at = time.monotonic()
    deadline = sent_at + 120
    while True:   # (the same process serves the same socket again once it is up. The old game answers for a moment before it
        # lets go of the socket, so: the new one is a status, a second after the ask or later, whose uptime is less than the old
        # game's would be by now (its uptime then plus the time since) and no longer than the time since)
        try:
            debug.bridge = Bridge(debug.sock_path)
            rr = debug.bridge.request('status')
            up, since = rr.get('uptime'), time.monotonic() - sent_at
            if (rr.get('ok') and isinstance(up, (int, float)) and since >= 1.0 and up <= since + 0.5
                    and (up0 is None or up < up0 + since - 0.5)):
                break
            debug.bridge.close()
        except DebugError:
            pass
        if time.monotonic() > deadline:
            raise DebugError('timeout', 'restore: the game did not answer again in 120 s')
        time.sleep(0.2)
    debug._disposable = None
    after = debug.wait_play(timeout=boot_timeout)
    want = doc['state']
    slot_map = doc.get('slot_map')
    ok = (after.get('map') or '').lower() == (want.get('map') or '').lower() and after.get('age') == want.get('age')
    out = {'ok': ok, 'action': 'restore', 'effect': 'verified' if ok else 'not_applied', 'relaunched': True,
           'state_at_snapshot': want, 'slot_map': slot_map, 'after': short(after), 'files': len(doc['files'])}
    differs = {k: [want.get(k), after.get(k)] for k in ('life', 'max_life', 'rupees')
               if want.get(k) is not None and after.get(k) is not None and want.get(k) != after.get(k)}
    if ok and differs:
        # (a value written into the game's memory is live only: the game's save holds what it saved, so a restart brings back the old one)
        out.update(effect='partial', not_in_save=differs, note='map and age are back, but %s differ from the snapshot\'s state: a value written '
                   'into the game\'s memory is not in its save (the save holds what the game saved)' % ', '.join(sorted(differs)))
    if not ok and doc.get('caption_matches_map') is not True and slot_map and (after.get('map') or '').lower() == slot_map.lower():
        # the files came back exactly; they were never saved at the place the snapshot's state names, so the game stands where they say
        out.update(ok=True, effect='partial', note='the snapshot\'s slots were not saved at the place Link was in when it was taken '
                   '(the game had not saved there): the files are back, and the game stands where they say, not at the snapshot\'s state')
    return out


# ---------------------------------------------------------------- finding the game

def read_env(path):
    out = {}
    try:
        with open(path, encoding='utf-8') as f:
            for line in f:
                k, eq, v = line.rstrip('\n').partition('=')
                if eq and re.fullmatch(r'[A-Z][A-Z0-9_]*', k):
                    out[k] = v
    except OSError:
        pass
    return out


def attach(run=None, sock=None, live=None, log=None, info=None, scratch=(), ready_timeout=30.0):
    """A Debug on a running game. run: the run folder (hs-run.sh's `<copy>/runs/<tag>`, or a workbench session's: its
    env-used.txt / extra-env.txt name the socket and the live file, its log is the game's); the game's save folder must be inside
    it for the tools that change the game. Or sock (+ live, log) and scratch."""
    env = {}
    if run:
        run = os.path.abspath(run)
        if not os.path.isdir(run):
            raise DebugError('bad_request', 'no run folder %s' % run)
        env = read_env(os.path.join(run, 'extra-env.txt'))
        env.update(read_env(os.path.join(run, 'env-used.txt')))
        sock = sock or env.get('HOS_CONTROL') or (os.path.join(run, 'control.sock') if os.path.exists(os.path.join(run, 'control.sock')) else None)
        live = live or env.get('HOS_INPUT_LIVE')
        log = log or next((os.path.join(run, n) for n in LOG_NAMES if os.path.isfile(os.path.join(run, n))), None)
    if not sock:
        raise DebugError('bad_request', 'which game? --run <run folder> or --sock <control socket>')
    d = Debug(sock, live=live, log=log, info=info, root=run, scratch=scratch, ready_timeout=ready_timeout)
    d.env = env
    return d


# ---------------------------------------------------------------- command line

def kv(items, cast=int):
    out = {}
    for it in items or ():
        k, eq, v = it.rpartition('=')
        if not eq or not k:
            raise DebugError('bad_request', '%r: NAME=VALUE expected' % it)
        try:
            out[k] = cast(v)
        except ValueError:
            raise DebugError('bad_request', '%r: a number after = expected' % it) from None
    return out


def flag_value(text):
    if text.lower() in ('true', 'false'):
        return text.lower() == 'true'
    try:
        return int(text, 0)
    except ValueError:
        return float(text)


def parser():
    ap = argparse.ArgumentParser(prog='hsdebug', description=__doc__.split('\n\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--run', help='the run folder of a game started by hs-run.sh (or a workbench session)')
    ap.add_argument('--sock', help='the control socket (HOS_CONTROL) instead of --run')
    ap.add_argument('--live', help='HOS_INPUT_LIVE file (default: from the run)')
    ap.add_argument('--log', help='the game log (default: from the run)')
    ap.add_argument('--info', help='game info file (`game-info` made it): items, flag layout, aliases')
    ap.add_argument('--scratch', action='append', default=[], help='a throw-away folder the game\'s user folder is in (with --sock)')
    ap.add_argument('--ready-timeout', type=float, default=30.0, help='seconds to wait for Link to be in control')
    ap.add_argument('--pretty', action='store_true', help='indent the JSON')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('boot', help='from the title: A until Link is in control'); p.add_argument('--timeout', type=float, default=300.0)
    for name in ('status', 'destinations', 'items', 'mark', 'return', 'saves', 'capabilities', 'release'):
        sub.add_parser(name)
    p = sub.add_parser('teleport'); p.add_argument('to'); p.add_argument('--arrive', type=float, default=60.0)
    p.add_argument('--settle', type=int, default=None, help='presents waited after the arrival (default %d: the scene fades in)' % SETTLE)
    p = sub.add_parser('age'); p.add_argument('to', choices=('child', 'adult')); p.add_argument('--arrive', type=float, default=60.0)
    p.add_argument('--settle', type=int, default=None, help='presents waited after the reload (default %d)' % SETTLE)
    p = sub.add_parser('time'); p.add_argument('hour', type=int); p.add_argument('--look', action='store_true', help='pictures before and after, their brightness')
    p = sub.add_parser('give'); p.add_argument('item'); p.add_argument('count', nargs='?', type=int, default=1)
    p = sub.add_parser('take'); p.add_argument('item'); p.add_argument('count', nargs='?', type=int, default=1)
    p = sub.add_parser('toggle'); p.add_argument('item')
    p = sub.add_parser('flag'); fs = p.add_subparsers(dest='what', required=True)
    q = fs.add_parser('get'); q.add_argument('names', nargs='+')
    q = fs.add_parser('set'); q.add_argument('name'); q.add_argument('value'); q.add_argument('--kind', choices=sorted(KIND_WIDTH))
    for name in ('health', 'rupees', 'magic'):
        q = sub.add_parser(name); q.add_argument('value', type=int)
    p = sub.add_parser('option'); os_ = p.add_subparsers(dest='what', required=True)
    q = os_.add_parser('get'); q.add_argument('name', nargs='?')
    q = os_.add_parser('set'); q.add_argument('name'); q.add_argument('value')
    p = sub.add_parser('shot'); p.add_argument('path', nargs='?')
    p = sub.add_parser('press'); p.add_argument('buttons'); p.add_argument('--frames', type=int, default=8)
    p = sub.add_parser('stick'); p.add_argument('x', type=float); p.add_argument('y', type=float); p.add_argument('--frames', type=int, default=8)
    p = sub.add_parser('warp', help='put Link at x y z (metres, the map\'s frame) by writing his position into memory')
    for axis in 'xyz':
        p.add_argument(axis, type=float)
    p.add_argument('--facing', type=float, help='degrees: 0 toward +z, 90 toward +x'); p.add_argument('--to', help='teleport to this destination (index or map name) first')
    p.add_argument('--watch', type=float, default=2.0, help='seconds his position is read back'); p.add_argument('--scan-mb', type=int, default=64)
    p.add_argument('--method', choices=('place', 'memory'), default='place', help="'place': the game's return-to-mark (needs the host patch); 'memory': experimental")
    p = sub.add_parser('snapshot'); p.add_argument('dir')
    p.add_argument('--wait-save', type=float, default=0.0, help='seconds to wait for the game to save the place Link is in')
    p = sub.add_parser('restore'); p.add_argument('dir'); p.add_argument('--into'); p.add_argument('--relaunch', action='store_true')
    p = sub.add_parser('setup', help='age, place, time, items, flags in one call')
    p.add_argument('--age', choices=('child', 'adult')); p.add_argument('--to'); p.add_argument('--time', type=int, dest='hour')
    p.add_argument('--give', action='append', metavar='ITEM=N'); p.add_argument('--toggle', action='append', metavar='ITEM')
    p.add_argument('--flag', action='append', metavar='NAME=VALUE'); p.add_argument('--life', type=int); p.add_argument('--rupees', type=int)
    p.add_argument('--keep-going', action='store_true')
    p = sub.add_parser('game-info', help='read the game\'s source and write the private game info file')
    p.add_argument('--source', required=True); p.add_argument('--extra', help='JSON with item_flags / names (private)'); p.add_argument('--out')
    p = sub.add_parser('check-source', help='are the Debug tab\'s action numbers as this tool has them, in these game checkouts')
    p.add_argument('roots', nargs='+')
    return ap


def run_source_commands(a):
    if a.cmd == 'check-source':
        res = []
        for root in a.roots:
            actions, problems = source_actions(root)
            try:
                layout, n_items = source_layout(root), len(source_items(root))
            except DebugError as e:
                layout, n_items = None, 0
                problems.append(e.message)
            res.append({'root': root, 'actions': actions, 'items': n_items, 'layout': bool(layout), 'problems': problems})
        return {'ok': all(not r['problems'] for r in res), 'action': 'check-source', 'effect': 'verified', 'sources': res}
    extra = None
    if a.extra:
        try:
            with open(a.extra, encoding='utf-8') as f:
                extra = json.load(f)
        except (OSError, ValueError) as e:
            raise DebugError('bad_request', '--extra %s: %s' % (a.extra, e)) from None
    doc = build_game_info(a.source, extra)
    if a.out:
        fd = os.open(a.out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(doc, f, indent=1)
    return {'ok': True, 'action': 'game-info', 'effect': 'verified', 'out': a.out, 'items': len(doc['items']),
            'layout': True, 'actions': doc['actions'], 'names': sorted(doc.get('names') or {}), 'private': True}


def run_command(a):
    if a.cmd in ('game-info', 'check-source'):
        return run_source_commands(a)
    if a.cmd == 'restore' and not a.relaunch:
        return restore(a.dir, into=a.into)
    info_path = a.info or os.environ.get('HSDEBUG_INFO')
    info = GameInfo.load(info_path) if info_path else None
    d = attach(run=a.run, sock=a.sock, live=a.live, log=a.log, info=info, scratch=a.scratch, ready_timeout=a.ready_timeout)
    try:
        if a.cmd == 'boot':
            st = d.wait_play(timeout=a.timeout)
            return {'ok': True, 'action': 'boot', 'effect': 'verified', 'state': short(st)}
        if a.cmd == 'status':
            return {'ok': True, 'action': 'status', 'effect': 'verified', 'state': d.status()}
        if a.cmd == 'destinations':
            return {'ok': True, 'action': 'destinations', 'effect': 'verified', 'destinations': d.destinations()}
        if a.cmd == 'items':
            if not info:
                raise DebugError('unavailable', 'no game info: --info FILE (`game-info` makes it)')
            return {'ok': True, 'action': 'items', 'effect': 'verified', 'items': info.items}
        if a.cmd == 'teleport':
            return d.teleport(a.to, arrive=a.arrive, settle=a.settle)
        if a.cmd == 'age':
            return d.age(a.to, arrive=a.arrive, settle=a.settle)
        if a.cmd == 'time':
            return d.time(a.hour, look=a.look)
        if a.cmd == 'give':
            return d.give(a.item, a.count)
        if a.cmd == 'take':
            return d.give(a.item, -a.count)
        if a.cmd == 'toggle':
            return d.toggle(a.item)
        if a.cmd == 'mark':
            return d.mark()
        if a.cmd == 'return':
            return d.return_to_mark()
        if a.cmd == 'flag':
            if a.what == 'get':
                return d.flag_get(*a.names)
            return d.flag_set(a.name, flag_value(a.value), kind=a.kind)
        if a.cmd in ('health', 'rupees', 'magic'):
            alias = {'health': 'life'}.get(a.cmd, a.cmd)
            return d.set_state(**{alias: a.value})[0]
        if a.cmd == 'option':
            return d.option_get(a.name) if a.what == 'get' else d.option_set(a.name, a.value)
        if a.cmd == 'shot':
            return d.shot(a.path)
        if a.cmd == 'press':
            return d.press(a.buttons, a.frames)
        if a.cmd == 'stick':
            return d.stick(a.x, a.y, a.frames)
        if a.cmd == 'release':
            return d.release()
        if a.cmd == 'saves':
            return {'ok': True, 'action': 'saves', 'effect': 'verified', 'saves': d.saves(), 'disposable': d.disposable()}
        if a.cmd == 'capabilities':
            return d.capabilities()
        if a.cmd == 'warp':
            return d.warp(a.x, a.y, a.z, facing=a.facing, to=a.to, watch=a.watch, method=a.method, scan_mb=a.scan_mb)
        if a.cmd == 'snapshot':
            return d.snapshot(a.dir, wait_save=a.wait_save)
        if a.cmd == 'restore':
            return d.restore(a.dir, relaunch=True)
        if a.cmd == 'setup':
            return d.setup(to=a.to, age=a.age, hour=a.hour, give=kv(a.give), toggle=a.toggle or (),
                           flags=kv(a.flag, flag_value), life=a.life, rupees=a.rupees, keep_going=a.keep_going)
        raise DebugError('bad_request', 'unknown command %s' % a.cmd)
    finally:
        d.close()


def main(argv=None):
    a = parser().parse_args(argv)
    try:
        res = run_command(a)
        code = 0 if res.get('ok') else EXIT.get(res.get('effect') if res.get('effect') in EXIT else 'not_applied')
    except DebugError as e:
        res, code = e.as_result(a.cmd), EXIT.get(e.code, 1)
    print(json.dumps(res, indent=1 if a.pretty else None, separators=None if a.pretty else (',', ':'), default=str))
    return code


def brief(res):
    """A result for one line of a driver's journal: the bulky parts (states, options, listings) reduced to what tells it."""
    out = {k: v for k, v in res.items() if k not in ('before', 'after', 'state', 'shots', 'options', 'items', 'destinations', 'steps',
                                                    'saves', 'bridge', 'disposable', 'game_info', 'live_input')}
    if isinstance(res.get('after'), dict):
        out['after'] = {k: res['after'].get(k) for k in ('map', 'age', 'pos', 'life', 'rupees')}
    if isinstance(res.get('state'), dict):
        out['state'] = {k: res['state'].get(k) for k in ('map', 'age', 'pos', 'life', 'rupees')}
    if isinstance(res.get('steps'), list):
        out['steps'] = [[s.get('action'), s.get('effect') or s.get('error')] for s in res['steps']]
    return out


def step(run, words, info=None):
    """For a driver with steps of words (hsap's `debug <command...>`): hsdebug's command line `words` run on the game of the run
    folder, as (result, detail): result `done` when the action is ok, else its effect or error (`not_applied`, `refused`,
    `unavailable`, ...); detail the result's `brief` as compact JSON, cut at 400 characters. Never raises."""
    try:
        a = parser().parse_args(['--run', str(run)] + (['--info', str(info)] if info else []) + [str(w) for w in words])
    except SystemExit:
        return 'bad_request', 'hsdebug: the words are not a command: ' + ' '.join(map(str, words))
    try:
        res = run_command(a)
    except DebugError as e:
        res = e.as_result(a.cmd)
    text = json.dumps(brief(res), separators=(',', ':'), default=str)
    return ('done' if res.get('ok') else res.get('effect') or res.get('error') or 'failed'), (text if len(text) <= 400 else text[:397] + '...')


if __name__ == '__main__':
    sys.exit(main())
