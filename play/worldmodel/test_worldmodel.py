#!/usr/bin/env python3
"""The world model's code against made-up inputs: the tables loader (missing, malformed, good), MurmurHash3 against
public reference vectors, SARC and BYML round trips on bytes built here, a plain RomFS folder with zstd (and a
trained dictionary), the flag list reader and the save reader/writer on a synthetic structure, event flows on a
synthetic file, a tiny nav mesh through navgraph and plan (A*, drops, jumps, climbs, crawls, doors), and the builders
(build, model, flows, story) end to end on a synthetic RomFS folder. No game, no local data, no tables file of this
machine: the tables are written here into a temporary folder.   python3 -I -B test_worldmodel.py
"""
import contextlib
import io
import json
import os
import struct
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from worldmodel import (build, evfl, flows, formats, game_files, gamestate, navgraph, navmesh, paths, plan, story,  # noqa: E402
                        tables)

try:
    from compression import zstd
except ImportError:          # Python before 3.14: the checks that need zstd are skipped
    zstd = None

ENV = ('PILOT_WORLD', 'WORLD_TABLES', 'WORLD_GAME', 'WORLD_FLAG_NAMES')
H = formats.murmur

# a synthetic tables file: the placeholder names below mean nothing; the schema is tables.SCHEMA
TABLES = {
    'version': 1,
    'actors': {'kinds': [['exit', '^ExitAlpha$'], ['lock', '^LockBeta'], ['door', '^Door'], ['person', '^Person'],
                         ['climbable', 'Ladder'], ['crawl', 'CrawlMark'], ['chest', '^Chest'], ['blocker', '^BlockAlpha']],
               'fixed_kinds': ['door', 'lock', 'climbable', 'crawl', 'chest', 'exit'],
               'param_flag_key_re': 'FlagKey', 'talk_re': '^Person', 'crawl_anchor': 'CrawlMark'},
    'exits': {'to_child': 'DestY', 'to_adult': 'DestO', 'to_start': 'DestStart', 'alt_flag': 'AltFlag',
              'init_flag': 'InitEvtFlag', 'init_event': 'InitEvtName', 'event_key_part': 'Evt', 'trigger_actor': 'VolumeAlpha',
              'trigger_shape_key': 'ShapeKind', 'anchor_actor': 'AnchorAlpha', 'anchor_name': 'GoPoint'},
    'areas': {'strip_re': '_(Young|Old)$', 'adult_marker': '_Old', 'child_suffix': '_Young',
              'child_param_key': 'YoungDefault', 'stitched_key': 'MeshMode', 'stitched_value': 7,
              'tokens': {'TokA': 'AreaA', 'TokB': 'AreaB'}},
    'flags': {'kinds': [['played', r'^Played\.'], ['talked', r'^Talked\.'], ['switch', 'Switch|Torch']],
              'played_prefix': 'Played.', 'talked_prefix': 'Talked.', 'event_in_path_re': '(Cut_[a-z]+)'},
    'quests': {'counter_prefix': 'Count_', 'counter_exp_re': '^(.+?)_Is(After|Before)', 'categories': ['CatMain', 'CatSub'],
               'main_category': 'CatMain', 'not_ready': 'Idle', 'complete': 'Done',
               'schedule_actor_re': '^(Get|Sub)\\w*?_(Person)', 'scene_flow_prefix': 'Cut_'},
    'flows': {'query_prefix': 'Ask', 'bool_queries': ['AskIsFlag', 'AskIsExp'], 'bool_exp_query': 'AskIsExp',
              'effects': {'DoSet': 'set', 'DoStep': 'step', 'DoMoney': 'currency', 'DoAdd': 'add'},
              'what_keys': ['Flag', 'Who'], 'test_keys': ['Flag'], 'flag_key': 'Flag', 'value_key': 'Value',
              'quest_key': 'Quest', 'step_keys': ['Step', 'StepAlt'], 'param_keys': ['Flag', 'Value', 'Quest', 'Step', 'Who', 'Idx'],
              'param_key_re': 'Extra', 'drop_minus_one_keys': ['Idx'], 'what_skip_keys': ['Quiet'], 'near_type': 'Approach'},
    'plan': {'door_flag_re': 'Gate|Open', 'door_open_hint': 'set Open to 1'},
}


# ---------------------------------------------------------------------------------------------- builders of bytes
class U(int):
    """An unsigned 32-bit value of a BYML (type 0xd3): hashes."""


def byml_bytes(obj, big=False):
    e = '>' if big else '<'
    order = 'big' if big else 'little'
    keys, strs = set(), set()

    def collect(o):
        if isinstance(o, dict):
            for k, v in o.items():
                keys.add(k)
                collect(v)
        elif isinstance(o, list):
            for v in o:
                collect(v)
        elif isinstance(o, str):
            strs.add(o)
    collect(obj)
    keys, strs = sorted(keys), sorted(strs)

    def table(items):
        n = len(items)
        pos, body, offs = 4 + 4 * (n + 1), b'', []
        for s in items:
            offs.append(pos + len(body))
            body += s.encode() + b'\0'
        offs.append(pos + len(body))
        out = bytes([0xc2]) + n.to_bytes(3, order) + struct.pack(e + '%dI' % (n + 1), *offs) + body
        return out + b'\0' * (-len(out) % 4)
    kt, st = table(keys), table(strs)
    base = 16 + len(kt) + len(st)
    buf = bytearray()

    def val(o):
        if isinstance(o, bool):
            return 0xd0, int(o)
        if o is None:
            return 0xff, 0
        if isinstance(o, U):
            return 0xd3, int(o)
        if isinstance(o, int):
            return 0xd1, o & 0xffffffff
        if isinstance(o, float):
            return 0xd2, struct.unpack(e + 'I', struct.pack(e + 'f', o))[0]
        if isinstance(o, str):
            return 0xa0, strs.index(o)
        return (0xc0 if isinstance(o, list) else 0xc1), emit(o)

    def emit(o):
        if isinstance(o, list):
            vals = [val(v) for v in o]
            node = bytes([0xc0]) + len(o).to_bytes(3, order) + bytes(t for t, _ in vals)
            node += b'\0' * (-len(node) % 4) + b''.join(struct.pack(e + 'I', v) for _, v in vals)
        else:
            items = sorted(o.items(), key=lambda kv: keys.index(kv[0]))
            node = bytes([0xc1]) + len(items).to_bytes(3, order)
            for k, v in items:
                t, x = val(v)
                node += keys.index(k).to_bytes(3, order) + bytes([t]) + struct.pack(e + 'I', x)
        off = base + len(buf)
        buf.extend(node)
        return off
    _t, root = val(obj)
    return (b'BY' if big else b'YB') + struct.pack(e + 'HIII', 7, 16, 16 + len(kt), root) + kt + st + bytes(buf)


def sarc_bytes(files, big=False):
    e = '>' if big else '<'
    names, nodes, data = b'', [], b''
    for name, content in files.items():
        data += b'\0' * (-len(data) % 4)
        nodes.append((H(name), 0x01000000 | len(names) // 4, len(data), len(data) + len(content)))
        data += content
        names += name.encode() + b'\0'
        names += b'\0' * (-len(names) % 4)
    sfat = b'SFAT' + struct.pack(e + 'HHI', 12, len(nodes), 0x65) + b''.join(struct.pack(e + '4I', *n) for n in nodes)
    sfnt = b'SFNT' + struct.pack(e + 'HH', 8, 0) + names
    start = 0x14 + len(sfat) + len(sfnt)
    start += -start % 4
    total = start + len(data)
    head = b'SARC' + struct.pack(e + 'H', 0x14) + (b'\xfe\xff' if big else b'\xff\xfe') + struct.pack(e + 'IIHH', total, start, 0x100, 0)
    return head + sfat + sfnt + b'\0' * (start - 0x14 - len(sfat) - len(sfnt)) + data


def evfl_bytes():
    """A BFEVFL file of one flowchart: actor A (action DoSet, DoStep; query AskIsFlag); entry 'Main': event 0 sets a
    flag, event 1 switches on a flag (case 0 -> event 2, case 1 -> end), event 2 advances a quest."""
    b = bytearray(0x48)

    def put(fmt, off, *v):
        struct.pack_into('<' + fmt, b, off, *v)

    def alloc(n, align=8):
        b.extend(b'\0' * (-len(b) % align))
        off = len(b)
        b.extend(b'\0' * n)
        return off

    def string(text):
        raw = text.encode()
        off = alloc(2 + len(raw) + 1, 2)
        put('H', off, len(raw))
        b[off + 2:off + 2 + len(raw)] = raw
        return off

    def container(value):
        if isinstance(value, dict):
            names = list(value)
            items = [container(value[k]) for k in names]
            dic = alloc(8 + 16 * (len(names) + 1))
            b[dic:dic + 4] = b'DIC '
            put('I', dic + 4, len(names))
            for k, n in enumerate(names, 1):
                put('Q', dic + 8 + 16 * k + 8, string(n))
            o = alloc(0x10 + 8 * len(names))
            put('B', o, 1)
            put('H', o + 2, len(names))
            put('Q', o + 8, dic)
            for k, it in enumerate(items):
                put('Q', o + 0x10 + 8 * k, it)
            return o
        o = alloc(0x18)
        if isinstance(value, bool):
            put('B', o, 3)
            put('I', o + 0x10, int(value))
        elif isinstance(value, int):
            put('B', o, 2)
            put('i', o + 0x10, value)
        else:
            put('B', o, 5)
            put('Q', o + 0x10, string(value))
        return o
    sname, aname = string('SynFlow'), string('ActorA')
    actions = alloc(16)
    put('Q', actions, string('DoSet'))
    put('Q', actions + 8, string('DoStep'))
    queries = alloc(8)
    put('Q', queries, string('AskIsFlag'))
    actor = alloc(0x38)
    put('Q', actor, aname)
    put('Q', actor + 24, actions)
    put('Q', actor + 32, queries)
    put('HH', actor + 48, 2, 1)
    events = alloc(0x30 * 3)
    for i, nm in enumerate(('EvSet', 'EvAsk', 'EvStep')):
        put('Q', events + 0x30 * i, string(nm))
    put('B', events + 8, 0)                                  # action: sets Flag_One to 1
    put('HHH', events + 0x0a, 1, 0, 0)
    put('Q', events + 0x10, container({'Flag': 'Flag_One', 'Value': 1}))
    put('B', events + 0x30 + 8, 1)                           # switch on the query: case 0 -> event 2, case 1 -> end
    cases = alloc(16)
    put('IH', cases, 0, 2)
    put('IH', cases + 8, 1, 0xffff)
    put('H', events + 0x30 + 0x0a, 2)
    put('HH', events + 0x30 + 0x0c, 0, 0)
    put('Q', events + 0x30 + 0x10, container({'Flag': 'Flag_Two'}))
    put('Q', events + 0x30 + 0x18, cases)
    put('B', events + 0x60 + 8, 0)                           # action: advances a quest
    put('HHH', events + 0x60 + 0x0a, 0xffff, 0, 1)
    put('Q', events + 0x60 + 0x10, container({'Quest': 'Quest_One', 'Step': 'S2'}))
    entry_dic = alloc(8 + 32)
    b[entry_dic:entry_dic + 4] = b'DIC '
    put('I', entry_dic + 4, 1)
    put('Q', entry_dic + 8 + 16 + 8, string('Main'))
    entries = alloc(0x20)
    put('H', entries + 0x1c, 0)
    fc = alloc(0x48)
    b[fc:fc + 4] = b'EVFL'
    put('HHHHH', fc + 0x10, 1, 2, 1, 3, 1)
    put('Q', fc + 0x20, sname)
    put('Q', fc + 0x28, actor)
    put('Q', fc + 0x30, events)
    put('Q', fc + 0x38, entry_dic)
    put('Q', fc + 0x40, entries)
    ptrs = alloc(8)
    put('Q', ptrs, fc)
    b[0:8] = b'BFEVFL\0\0'
    put('I', 8, 0x400)
    put('H', 0x20, 1)
    put('Q', 0x28, ptrs)
    return bytes(b)


def save_bytes(entries, data=b''):
    """A .sav: header, the table of (hash, word), the closing entry, then the data section."""
    start = 0x28 + 8 * (len(entries) + 1)
    out = bytearray(struct.pack('<III', formats.MAGIC, 1, start)) + bytearray(0x28 - 12)
    for h, w in entries:
        out += struct.pack('<II', h, w)
    out += struct.pack('<II', formats.TAIL_HASH, 0)
    return bytes(out) + data


def grid_nav(w, h, y=0.0, holes=(), x0=0, z0=0, level=None):
    """A nav mesh of unit squares: cell (i, j) spans x from x0 + i, z from z0 + j; `holes` are cells left out;
    `level(i, j)` gives a cell's height (default y)."""
    verts, vid, faces, cell_face = [], {}, [], {}

    def vert(i, j, yy):
        if (i, j, yy) not in vid:
            vid[(i, j, yy)] = len(verts)
            verts.append((x0 + i, yy, z0 + j))
        return vid[(i, j, yy)]
    for j in range(h):
        for i in range(w):
            if (i, j) in holes:
                continue
            yy = level(i, j) if level else y
            cell_face[(i, j)] = len(faces)
            faces.append([vert(i, j, yy), vert(i + 1, j, yy), vert(i + 1, j + 1, yy), vert(i, j + 1, yy)])
    cells = {f: c for c, f in cell_face.items()}
    adj = []
    for f in range(len(faces)):
        i, j = cells[f]
        adj.append([cell_face.get(n, -1) for n in ((i, j - 1), (i + 1, j), (i, j + 1), (i - 1, j))])
    return {'verts': [c for v in verts for c in v], 'faces': faces, 'adj': adj, 'fdata': [], 'erosion': 0.4,
            'portals': [], 'source': ['synthetic']}


# ------------------------------------------------------------------------------------------------------- the checks
class Checks:
    def __init__(self):
        self.fails, self.count = [], 0

    def __call__(self, cond, what):
        self.count += 1
        if not cond:
            self.fails.append(what)
            print('FAIL', what, flush=True)


@contextlib.contextmanager
def environment(**values):
    saved = {k: os.environ.pop(k, None) for k in ENV}
    os.environ.update({k: str(v) for k, v in values.items()})
    try:
        yield
    finally:
        for k in ENV:
            os.environ.pop(k, None)
        os.environ.update({k: v for k, v in saved.items() if v is not None})


def raises(exc, fn, *a, **kw):
    try:
        fn(*a, **kw)
    except exc as e:
        return e
    return None


def test_tables(check, tmp):
    p = tmp / 'tables-test.json'
    e = raises(tables.TablesMissing, tables.load, p)
    check(e is not None and str(p) in str(e) and 'actors.kinds' in str(e) and 'your own game' in str(e),
          'tables: a missing file raises TablesMissing naming the file and the schema and saying to write it from the game')
    p.write_text('{not json')
    check(raises(tables.TablesInvalid, tables.load, p) is not None, 'tables: a file that is no JSON raises TablesInvalid')
    bad = json.loads(json.dumps(TABLES))
    del bad['flows']
    bad['actors']['kinds'] = [['kind_a', '(unclosed']]
    bad['areas']['stitched_value'] = 'seven'
    bad['quests']['counter_exp_re'] = 'no group'
    bad['actors']['extra'] = 1
    p.write_text(json.dumps(bad))
    e = raises(tables.TablesInvalid, tables.load, p)
    text = str(e)
    check(e is not None and 'section "flows"' in text and 'actors.kinds' in text and 'areas.stitched_value' in text
          and 'quests.counter_exp_re' in text and 'actors.extra' in text and str(p) in text,
          'tables: a malformed file names every problem with its key')
    bad = json.loads(json.dumps(TABLES))
    bad['actors']['fixed_kinds'] = ['kind_unknown']
    p.write_text(json.dumps(bad))
    check('fixed_kinds' in str(raises(tables.TablesInvalid, tables.load, p)), 'tables: fixed_kinds must be kinds')
    bad = json.loads(json.dumps(TABLES))
    bad['flows']['effects']['DoSet'] = 'explode'
    p.write_text(json.dumps(bad))
    check('effect kind' in str(raises(tables.TablesInvalid, tables.load, p)), 'tables: an unknown effect kind is refused')
    p.write_text(json.dumps(TABLES))
    T = tables.load(p)
    check(T.path == p and tables.load(p) is T, 'tables: a good file loads, and is kept while the file is unchanged')
    check(T.kind_of('ExitAlpha') == 'exit' and T.kind_of('ExitAlphaX') is None and T.kind_of('DoorFrameLadder') == 'door'
          and T.kind_of('LadderOne') == 'climbable', 'tables: kind_of gives the first pattern that matches, else None')
    check(T.kind_names == ['exit', 'lock', 'door', 'person', 'climbable', 'crawl', 'chest', 'blocker'],
          'tables: kind_names keep the order')
    check(T.flag_kind('Played.X') == 'played' and T.flag_kind('Some_Switch') == 'switch' and T.flag_kind('zzz') == 'other',
          'tables: flag_kind by the first pattern, else other')
    check(T.area_base('AreaA_Young') == 'AreaA' and T.area_base('AreaA') == 'AreaA' and T.age_of('AreaA_Old') == 'adult'
          and T.age_of('AreaA_Young') == 'child' and T.age_of('AreaA') is None, 'tables: area_base and age_of')
    check(list(T.areas.tokens) == ['TokA', 'TokB'] and T.flows.near_type == 'Approach' and T.plan.door_flag_re.search('xGate'),
          'tables: maps keep their order, regular expressions are compiled')
    p.write_text(json.dumps(dict(TABLES, plan={'door_flag_re': 'Other', 'door_open_hint': ''})))
    check(tables.load(p).plan.door_flag_re.pattern == 'Other', 'tables: a changed file is read again')
    # where the files are looked for
    with environment():
        check(paths.data_dir() == paths.ROOT / 'world' and paths.tables_path() == paths.ROOT / 'world' / 'tables.json',
              'paths: the data folder is world/ beside the package when nothing is set')
    with environment(PILOT_WORLD=tmp / 'data', WORLD_TABLES=p):
        check(paths.data_dir() == tmp / 'data' and paths.tables_path() == p and paths.flag_names_path() == tmp / 'data' / 'flag_names.json',
              'paths: $PILOT_WORLD and $WORLD_TABLES are honoured')
        check(paths.tables_path(tmp / 'other') == p, 'paths: $WORLD_TABLES wins over a data folder argument')
    with environment():
        check(paths.tables_path(tmp / 'other') == tmp / 'other' / 'tables.json', 'paths: a data folder argument names the tables beside it')
        e = raises(SystemExit, paths.game_dir, None)
        check(e is not None and 'WORLD_GAME' in str(e) and paths.game_dir('x') == 'x', 'paths: no game folder is a clear refusal')
    with environment(WORLD_GAME='from-env'):
        check(paths.game_dir(None) == 'from-env', 'paths: $WORLD_GAME names the game')
    return T


def test_hash_and_archives(check):
    vectors = [(b'', 0, 0x0), (b'', 1, 0x514E28B7), (b'', 0xffffffff, 0x81F16F39), (b'\xff\xff\xff\xff', 0, 0x76293B50),
               (b'\x21\x43\x65\x87', 0, 0xF55B516B), (b'\x21\x43\x65\x87', 0x5082EDEE, 0x2362F9DE),
               (b'\x21\x43\x65', 0, 0x7E4A8634), (b'\x21\x43', 0, 0xA0F7B07A), (b'\x21', 0, 0x72661CF4),
               (b'\0\0\0\0', 0, 0x2362F9DE), (b'\0\0\0', 0, 0x85F0B427), (b'\0\0', 0, 0x30F4C306), (b'\0', 0, 0x514E28B7),
               (b'Hello, world!', 0x9747b28c, 0x24884CBA), (b'abcd', 0x9747b28c, 0xF0478627), (b'abc', 0x9747b28c, 0xC84A62DD),
               (b'ab', 0x9747b28c, 0x74875592), (b'a', 0x9747b28c, 0x7FA09EA6), (b'test', 0, 0xba6bd213),
               (b'The quick brown fox jumps over the lazy dog', 0x9747b28c, 0x2FA826CD)]
    check(all(formats.murmur(d, s) == want for d, s, want in vectors), f'murmur: {len(vectors)} public MurmurHash3 x86 32 vectors')
    check(formats.murmur('Hello, world!', 0) == 0xc0363e43 and formats.murmur(b'test') == formats.murmur('test'),
          'murmur: text and bytes hash alike')
    check(formats.flag_hash('0x10') == 16 and formats.flag_hash('42') == 42 and formats.flag_hash('test') == 0xba6bd213,
          'flag_hash: hex, decimal and a name')
    check(abs(formats.yaw_of([0, 0.5, 0]) - 0.5) < 1e-9 and abs(formats.yaw_of([3.0, 0.5, 0]) - (formats.PI - 0.5)) < 1e-9,
          'yaw_of: both branches')
    files = {'dir/one.bin': b'12345', 'two.txt': b'x' * 9, 'three': b''}
    for big in (False, True):
        got = formats.sarc(sarc_bytes(files, big))
        check(got == files, f'sarc: round trip of a {"big" if big else "little"} endian archive')
    doc = {'Name': 'x', 'List': [1, -2, 3.5, True, None, 'str'], 'Nested': {'A': [], 'B': {'C': 'D'}}, 'Hash': U(0xdeadbeef)}
    for big in (False, True):
        got = formats.byml(byml_bytes(doc, big))
        check(got == doc and got['Hash'] == 0xdeadbeef, f'byml: round trip of a {"big" if big else "little"} endian file')
    check(formats.byml(byml_bytes([{'A': 1}, {'A': 2}])) == [{'A': 1}, {'A': 2}], 'byml: a list root')


def test_romfs(check, tmp):
    root = tmp / 'rom'
    (root / 'GameData').mkdir(parents=True)
    (root / 'Banc' / 'F').mkdir(parents=True)
    (root / 'Other').mkdir()
    (root / 'Pack').mkdir()
    (root / 'GameData' / 'plain.bin').write_bytes(b'plain')
    (root / 'Banc' / 'F' / 'x.bin').write_bytes(b'xx')
    (root / 'Other' / 'y.bin').write_bytes(b'yyy')
    R = formats.Romfs(root)
    check(R.raw('GameData/plain.bin') == b'plain' and R.load('GameData/plain.bin') == b'plain', 'romfs: a plain file')
    check('Banc/F/x.bin' in R.files and 'Banc/F/nothing' not in R.files and sorted(R.files) == ['Banc/F/x.bin'],
          'romfs: PlainFiles asks the file system for membership and lists Banc/ only')
    (tmp / 'copy' / 'romfs' / 'GameData').mkdir(parents=True)
    check(formats.Romfs(tmp / 'copy').root == tmp / 'copy' / 'romfs', 'romfs: a game copy that holds romfs/')
    e = raises(SystemExit, formats.Romfs, tmp / 'nowhere')
    check(e is not None and 'not a RomFS folder' in str(e), 'romfs: a folder without GameData/ is refused with a message')
    F = game_files.Romfs(root)
    check(sorted(F.files) == ['Banc/F/x.bin', 'GameData/plain.bin', 'Other/y.bin'] and F.files['Other/y.bin'] == (0, 3),
          'game_files: FullFiles lists every file with its size')
    check(isinstance(raises(KeyError, F.raw, 'Other/missing'), KeyError), 'game_files: a file not in the RomFS is a KeyError')
    if zstd is None:
        print('test_worldmodel: no compression.zstd here: the .zs checks are skipped')
        return
    (root / 'GameData' / 'packed.bin.zs').write_bytes(zstd.compress(b'packed bytes' * 20))
    check(R.load('GameData/packed.bin.zs') == b'packed bytes' * 20, 'romfs: a .zs file is unpacked')
    samples = [(' '.join(f'w{(i * 7 + k * 13) % 29}' for k in range(60))).encode() for i in range(300)]
    zd = zstd.train_dict(samples, 2048)
    payload = samples[5]
    (root / 'Pack' / 'ZsDic.pack.zs').write_bytes(zstd.compress(sarc_bytes({'a.dict': zd.dict_content})))
    (root / 'GameData' / 'dict.bin.zs').write_bytes(zstd.compress(payload, zstd_dict=zd))
    R = formats.Romfs(root)
    check(list(R.dicts()) == [zd.dict_id] and R.load('GameData/dict.bin.zs') == payload,
          'romfs: a file compressed with a dictionary from Pack/ZsDic.pack.zs is unpacked with it')


def make_game_folder(root, with_flows=False):
    """A synthetic RomFS folder: two areas, flags of every kind the builders read, one event flow."""
    def zs(path, data):
        p = root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(zstd.compress(data) if path.endswith('.zs') else data)
    flags = {'Bool': [{'Hash': U(H(n))} for n in ('Flag_One', 'Flag_Two', 'Played.EvOne', 'AreaA_Switch_X', 'Other_TokB_Y')],
             'Bool64bitKey': [{'Hash': U(777)}],
             'Enum': [{'Hash': U(H('Mode_Enum')), 'RawValues': ['Low', 'High'], 'Values': [U(H('Low')), U(H('High'))]},
                      {'Hash': U(H('Count_Quest_One')), 'RawValues': ['Idle', 'S1', 'S2', 'Done']}],
             'BoolExp': [{'Hash': U(H('Area_IsAfter_Exp')), 'Values': [[1, U(H('Count_Quest_One'))], [2, U(H('S2'))]]},
                         {'Hash': U(H('Flag_Three')), 'Values': [[0, U(H('Flag_One'))], [0, U(H('Flag_Two'))], [3]]}]}
    zs('GameData/GameDataList.Product.110.byml.zs', byml_bytes({'Data': flags}))
    zs('GameData/GameDataList.Product.110.revision.txt', b'1\n')
    start = {'Trans': [1, 0, 1], 'Rot': [0, 0, 0]}
    zs('Banc/BancBasedResource/StartPos.byml.zs', byml_bytes({'AreaA_Young': {'': start, 'StartX': {'Trans': [2, 0, 1], 'Rot': [0, 1, 0]}},
                                                              'AreaB': {'': start, 'StartX': {'Trans': [4, 0, 1], 'Rot': [0, 0, 0]}}}))
    exit_d = {'DestY': 'AreaB', 'DestO': 'AreaB_Old', 'DestStart': 'StartX', 'AltFlag': 'Flag_Two', 'InitEvtFlag': 'Flag_One',
              'InitEvtName': 'EvOne', 'ShapeKind': 'Box'}
    static = {'Actors': [{'Gyaml': 'ExitAlpha', 'Hash': U(101), 'Name': 'GoOne', 'Translate': [5, 0, 1], 'Dynamic': exit_d,
                          'Links': [{'Name': 'link', 'Dst': U(103)}]},
                         {'Gyaml': 'VolumeAlpha', 'Hash': U(102), 'Translate': [5, 0, 1], 'Scale': [2, 2, 2], 'Rotate': [0, 0, 0]},
                         {'Gyaml': 'AnchorAlpha', 'Hash': U(103), 'Name': 'GoPoint', 'Translate': [6, 0, 1]},
                         {'Gyaml': 'DoorAlpha', 'Hash': U(104), 'Translate': [3, 0, 1], 'Presence': {'FlagName': 'Flag_Two', 'IsNegation': False},
                          'Dynamic': {'FlagKey': 'Flag_One', 'Other': 3}},
                         {'Gyaml': 'LadderOne', 'Hash': U(105), 'Translate': [3, 2, 1]},
                         {'Gyaml': 'PersonOne', 'Hash': U(106), 'Translate': [2, 0, 1], 'MoveRadius': 2}],
              'AiGroups': [{'Logic': 'x/LogicOne.logic.module.ain', 'References': [{'Reference': U(101)}, {'Reference': U(102)}]},
                           {'Logic': 'x/LogicTwo.logic.module.ain', 'References': [{'Reference': U(104)}]}]}
    zs('Banc/Fold/AreaA_Young_Static.bcett.byml.zs', byml_bytes(static))
    zs('Banc/Fold/AreaA_Young_Dynamic.bcett.byml.zs', byml_bytes({'Actors': [{'Gyaml': 'ChestOne', 'Hash': U(107), 'Translate': [1, 0, 1]}]}))
    zs('Banc/Fold/AreaB_Static.bcett.byml.zs', byml_bytes({'Actors': [{'Gyaml': 'LockBetaX', 'Hash': U(201), 'Translate': [0, 0, 0]}]}))
    zs('Banc/GameBancParam/AreaA_Young.game__banc__GameBancParam.bgyml', byml_bytes({'AreaIndex': 3, 'BaseLocation': 'a/b.c'}))
    zs('Banc/GameBancParam/AreaB.game__banc__GameBancParam.bgyml', byml_bytes({'YoungDefault': False}))
    zs('Logic/LogicTwo.logic.module.ainb', b'\0header Flag_Three \0 other AreaA_Switch_X Other_TokB_Y\0')
    if with_flows:
        zs('Event/EventFlow/SynFlow.bfevfl.zs', evfl_bytes())
        zs('RSDB/EventSetting.Product.111.rstbl.byml.zs', byml_bytes([
            {'__RowId': 'EvOne', 'FlowchartFileName': 'x/SynFlow.evfc', 'EntryPointName': 'Main'}]))
        member = 'Component/AIScheduleParam/PersonOne.game__component__AIScheduleParam.bgyml'
        sched = {'ConditionalSchedule': [{'ConditionFlag': 'Flag_Two', 'IsReverseCondition': True, 'EventEntry': [
            {'$type': 'TalkX', 'EventName': 'a/EvOne.x'}, {'$type': 'ApproachX', 'EventName': 'a/EvTwo.x', 'Distance': 3}]}],
            'DefaultSchedule': {'EventEntry': [{'EventName': 'a/EvOne.x'}]}}
        zs('Pack/AIScheduleParam.pack.zs', sarc_bytes({member: byml_bytes(sched)}))
        zs('RSDB/Challenge.Product.111.rstbl.byml.zs', byml_bytes([
            {'__RowId': 'Quest/Quest_One.row', 'Category': U(H('CatMain')), 'Steps': [{'Name': 'S1'}, {'Name': 'S2', 'IsBossBattle': True}],
             'DependFlagName': 'Area_IsAfter_Exp'},
            {'__RowId': 'Quest/Quest_Two.row', 'Category': U(H('CatOther')), 'Steps': []}]))
    return root


def test_game_and_save(check, tmp, T):
    if zstd is None:
        return
    root = make_game_folder(tmp / 'game')
    g = game_files.Game(root)
    check(g.revision == 1 and H('Flag_One') in g.flags and g.flags[H('Flag_One')][0] == 'Bool'
          and g.flags[H('Mode_Enum')][1]['RawValues'] == ['Low', 'High'], 'game: the flag list is read by hash with its type and entry')
    check(sorted(g.folder) == ['AreaA_Young', 'AreaB'] and g.folder['AreaB'] == 'Fold', 'game: the placement folder of every area')
    check(g.starts['AreaA_Young']['StartX']['Trans'] == [2, 0, 1] and g.bancparam('AreaB') == {'YoungDefault': False}
          and g.bancparam('Nowhere') is None, 'game: start positions and area parameters')
    check([a['Gyaml'] for a in g.actors('AreaA_Young')][0] == 'ChestOne' and len(g.actors('AreaA_Young')) == 7,
          'game: the placed actors of both files of an area, Dynamic first')
    plain = formats.Game(root)
    check(sorted(plain.folder) == ['AreaA_Young', 'AreaB'], 'game: the plain file list finds the areas too')
    check(g.enum_name(H('Mode_Enum'), H('High')) == 'High' and g.enum_name(H('Mode_Enum'), 5) == '0x5'
          and g.enum_hash(H('Mode_Enum'), 'Low') == H('Low') and raises(SystemExit, g.enum_hash, H('Mode_Enum'), 'Zzz') is not None,
          'game: enum names and hashes')
    mts = game_files.load_mts()
    check(mts.murmur is formats.murmur and mts.Sav is formats.Sav and mts.byml is formats.byml and mts.sarc is formats.sarc
          and mts.flag_hash('7') == 7 and mts.yaw_of is formats.yaw_of and mts.Game is game_files.Game
          and mts.PlainFiles is game_files.FullFiles, 'load_mts: the readers a builder uses')
    check(mts.area_age(g, 'AreaA_Young', T) == ('child', 'only') and mts.area_age(g, 'AreaX_Old', T) == ('adult', 'only')
          and mts.area_age(g, 'AreaB', T) == ('adult', 'default') and mts.area_age(g, 'Nowhere', T) == ('child', 'default'),
          'load_mts: area_age by the name, else by the area parameter the tables name')
    # a save
    vec = (1, -2, 4)
    data = struct.pack('<3f', *vec) + b'text\0'.ljust(16, b'\0')
    flags = {H('Int_One'): ('Int', {}), H('Float_One'): ('Float', {}), H('Vec_One'): ('Vector3', {}), H('Str_One'): ('String16', {})}
    ents = [(H('Flag_One'), 1), (H('Flag_Two'), 0), (H('Mode_Enum'), H('High')), (H('Flag_Three'), 0),
            (H('Int_One'), (-5) & 0xffffffff), (H('Float_One'), struct.unpack('<I', struct.pack('<f', 0.5))[0]),
            (H('Vec_One'), 0), (H('Str_One'), 0)]
    sav = tmp / 'progress.sav'
    start = 0x28 + 8 * (len(ents) + 1)                 # the data section follows the table
    at = {H('Vec_One'): start, H('Str_One'): start + 12}
    sav.write_bytes(save_bytes([(h, at.get(h, w)) for h, w in ents], data))
    gg = type('G', (), {'flags': {**g.flags, **flags}})()
    S = formats.Sav(sav, gg)
    check(S.get(H('Flag_One')) is True and S.get(H('Flag_Two')) is False and S.get(H('Int_One')) == -5
          and S.get(H('Float_One')) == 0.5 and S.get(H('Mode_Enum')) == H('High') and S.get(H('Vec_One')) == tuple(map(float, vec))
          and S.get(H('Str_One')) == 'text' and S.get(12345, 'dflt') == 'dflt' and S.has(H('Flag_One')) and not S.has(1),
          'sav: bool, int, float, enum, vector and string flags are read')
    S.set(H('Flag_Two'), True)
    S.set(H('Int_One'), 9)
    S.set(H('Float_One'), 2.5)
    S.set(H('Vec_One'), (3, 4, 5))
    S.set(H('Str_One'), 'new')
    out = tmp / 'copy.sav'
    S.save(out)
    S2 = formats.Sav(out, gg)
    check(S2.get(H('Flag_Two')) is True and S2.get(H('Int_One')) == 9 and S2.get(H('Float_One')) == 2.5
          and S2.get(H('Vec_One')) == tuple(map(float, (3, 4, 5))) and S2.get(H('Str_One')) == 'new' and S2.get(H('Flag_One')) is True,
          'sav: values changed in place survive a save, the others are kept')
    check(len(S2.b) == len(S.b) and raises(SystemExit, S.set, H('Str_One'), 'x' * 20) is not None
          and raises(SystemExit, S.set, 99, 1) is not None, 'sav: a value too long or a flag not in the save is refused')
    bad = tmp / 'bad.sav'
    bad.write_bytes(b'\0' * 0x40)
    check(raises(ValueError, formats.Sav, bad, gg) is not None, 'sav: a file without the header is refused')
    # the conditions of the game as a save sees them
    sav2 = tmp / 'slots' / 'slot_00' / 'progress.sav'
    sav2.parent.mkdir(parents=True)
    sav2.write_bytes(sav.read_bytes())
    st = gamestate.State(g, mts, sav2.parent.parent)
    check(st.value('Flag_One') is True and st.value('Flag_Two') is False and st.value('Flag_Three') is False
          and st.value('Unknown_Flag') is None, 'gamestate: plain flags, and a stack-program flag (AND) from the save')
    g.flags[H('Flag_Or')] = ('BoolExp', {'Values': [[0, H('Flag_One')], [0, H('Flag_Two')], [4], [5]]})
    check(st.value('Flag_Or') is False, 'gamestate: OR and NOT')
    g.flags[H('Flag_Cmp')] = ('BoolExp', {'Values': [[15, H('Int_One')], [16, -5]]})
    g.flags[H('Int_One')] = ('Int', {})
    check(gamestate.State(g, mts, sav).value('Flag_Cmp') is True, 'gamestate: an Int flag compared with a number')


def test_evfl(check, tmp, T):
    f = evfl.read(evfl_bytes())
    check(f['name'] == 'SynFlow' and f['entries'] == {'Main': 0} and len(f['events']) == 3 and f['actors'][0]['name'] == 'ActorA'
          and f['actors'][0]['actions'] == ['DoSet', 'DoStep'] and f['actors'][0]['queries'] == ['AskIsFlag'],
          'evfl: the flowchart, its actor and entry points')
    e0, e1, e2 = f['events']
    check(e0['type'] == evfl.ACTION and e0['params'] == {'Flag': 'Flag_One', 'Value': 1} and e0['next'] == 1
          and e1['type'] == evfl.SWITCH and e1['cases'] == [(0, 2), (1, 0xffff)] and e2['params'] == {'Quest': 'Quest_One', 'Step': 'S2'}
          and e2['next'] == evfl.NONE, 'evfl: actions, a switch with its cases, and parameter containers')
    check(evfl.label(f, e0) == 'ActorA.DoSet' and evfl.label(f, e1) == 'ActorA.AskIsFlag' and evfl.label(f, e2) == 'ActorA.DoStep',
          'evfl: labels of actions and queries')
    check(raises(ValueError, evfl.read, b'not a flow file at all') is not None, 'evfl: a file that is no BFEVFL is refused')
    # the flow index with these tables
    F = flows.Flows.__new__(flows.Flows)
    F.T, F.g, F.mts = T, None, None
    F.flows = {'SynFlow': f}
    F.settings = {'EvOne': {'flow': 'SynFlow', 'entry': 'Main'}}
    F.by_entry = {('SynFlow', 'Main'): ['EvOne']}
    F.sched_raw = {'Component/AIScheduleParam/PersonOne.x.bgyml': {
        'ConditionalSchedule': [{'ConditionFlag': 'Flag_Two', 'IsReverseCondition': True, 'EventEntry': [
            {'$type': 'TalkX', 'EventName': 'a/EvOne.x'}, {'$type': 'ApproachX', 'EventName': 'a/EvTwo.x', 'Distance': 3}]}],
        'DefaultSchedule': {'EventEntry': [{'EventName': 'a/EvOne.x'}]}}}
    idx = flows.analyse(F)
    check(set(idx['setters']) == {'Flag_One'} and idx['setters']['Flag_One'][0]['value'] == 1
          and idx['setters']['Flag_One'][0]['when'] == [[]] and idx['setters']['Flag_One'][0]['events'] == ['EvOne'],
          'flows: an effect the tables call set is indexed by its flag, with the value and the event that starts it')
    st = idx['steps']['Quest_One']['S2'][0]
    check(st['when'] == [['IsFlag(Flag_Two)']] and st['op'] == 'step' and st['at'] == 'SynFlow:EvStep',
          'flows: a step effect behind a bool query is indexed by quest and step with its condition text (query prefix dropped)')
    check(idx['tested_in'] == {'Flag_Two': ['SynFlow']} and idx['counts']['entries'] == 1 and idx['counts']['step_setters'] == 1,
          'flows: tested_in and counts')
    sch = idx['schedules']['PersonOne']
    check(sch['conditional'][0]['negated'] is True and sch['conditional'][0]['talk'] == [{'event': 'EvOne'}]
          and sch['conditional'][0]['near'] == [{'event': 'EvTwo', 'distance': 3}] and sch['default']['talk'] == [{'event': 'EvOne'}],
          'flows: a schedule entry whose type holds near_type starts on approach, the others on talk')
    check(idx['starters']['EvOne'][0]['how'] == 'talk' and idx['starters']['EvTwo'][0]['distance'] == 3, 'flows: who starts an event')
    check(flows._small({'Flag': 'x', 'Idx': -1, 'Extra1': 5, 'Noise': 1, 'Extra2': [1], 'Value': {'$arg': 'a'}}, T.flows)
          == {'Flag': 'x', 'Extra1': 5, 'Value': '<argument a>'}, 'flows: only the parameter keys of the tables are kept')
    check(flows._what({'A': 'x', 'Quiet': 1, 'B': 2, 'C': ''}, T.flows) == 'A=x, B=2', 'flows: the text of a query that names no flag')
    edges = flows.gate_edges(idx, {'gates': [{'flag': 'Flag_One'}, {'flag': 'Flag_One'}, {'flag': 'Flag_X(1)'}]})
    check(len(edges) == 1 and edges[0]['to'] == 'Flag_One' and edges[0]['value'] == 1 and 'PersonOne' in edges[0]['started_by'],
          'flows: an edge per gate flag a flow sets')


def make_data(tmp, T_dict=TABLES):
    data = tmp / 'data'
    (data / 'nav').mkdir(parents=True, exist_ok=True)
    (data / 'tables.json').write_text(json.dumps(T_dict))
    return data


def test_nav_and_plan(check, tmp, T):
    data = make_data(tmp / 'plan')
    nav = grid_nav(4, 1)
    A = navgraph.Area('S', nav=nav)
    check(len(A.F) == 4 and A.comp_size == [4] and A.faces_at(1.5, 0.5) == [1] and A.faces_at(9, 9) == []
          and abs(A.height(1, 1.5, 0.5)) < 1e-9, 'navgraph: faces, components, point location and height of a strip')
    check(A.locate(1.5, 0.5)[0] == 1 and A.locate(9, 0.5, snap=1.0) is None and A.locate(4.5, 0.5, snap=1.0)[2] == 0.5,
          'navgraph: locate inside, off the mesh, and snapped')
    check(navgraph.seg_closest(1, 1, 0, 0, 2, 0)[:3] == (1, 1, 0), 'navgraph: the closest point of a segment')
    navmesh.save(nav, data / 'nav' / 'AreaA.json.gz')
    check(navmesh.load(data / 'nav' / 'AreaA.json.gz')['faces'] == nav['faces'], 'navmesh: save and load round trip')
    two = grid_nav(3, 3, holes={(1, 1)})
    navmesh.save(two, data / 'nav' / 'Ring.json.gz')
    plan.use(data)
    check(plan.available('AreaA') and not plan.available('Nowhere'), 'plan: available asks the data folder')
    r = plan.plan('AreaA', (0.5, 0.5), (3.5, 0.5), from_y=0, to_y=0)
    check(r['ok'] and r['waypoints'][-1] == [3.5, 0.5] and abs(r['length'] - 3.0) < 0.1 and r['source'] == 'navmesh'
          and r['steps'][-1].startswith('run 3.50 0.50'), 'plan: a straight way over a strip of faces, as route steps')
    r = plan.plan('Ring', (0.5, 0.5), (2.5, 2.5))
    check(r['ok'] and 3.1 <= r['length'] <= 3.3 and any(abs(x - 2) < 0.01 and abs(z - 1) < 0.01 or abs(x - 1) < 0.01 and abs(z - 2) < 0.01
                                                         for x, z in r['waypoints']),
          'plan: A* goes round a hole and the funnel keeps to its corner')
    r = plan.plan('Ring', (20, 20), (2.5, 2.5))
    check(not r['ok'] and r['why'] == 'off-mesh' and r['near'] is not None, 'plan: a start off the mesh says off-mesh and where the mesh is')
    r = plan.plan('Nowhere', (0, 0), (1, 1))
    check(not r['ok'] and r['why'] == 'no-data' and r['source'] == 'straight', 'plan: an area without data says no-data')
    check((data / 'nav' / 'AreaA.pickle').is_file(), 'plan: the loaded area is kept as a pickle beside its mesh')
    plan.use(data)
    check(plan.plan('AreaA', (0.5, 0.5), (3.5, 0.5))['ok'], 'plan: use() forgets what was loaded; the pickle serves the next load')
    (data / 'nav' / 'AreaA.pickle').write_bytes(b'garbage')
    os.utime(data / 'nav' / 'AreaA.pickle', (4e9, 4e9))
    plan.use(data)
    check(plan.plan('AreaA', (0.5, 0.5), (3.5, 0.5))['ok'], 'plan: an unreadable pickle is ignored and replaced')
    # components apart: a gap (jump), a lower piece (drop, and a ledge back up), climbables and crawl markers
    gap = grid_nav(5, 1, holes={(2, 0)})
    A = navgraph.Area('G', nav=gap)
    gap['xlinks'] = navgraph.compute_xlinks(A)
    check(len(A.comp_size) == 2 and {l['kind'] for l in gap['xlinks']} == {'jump'}, 'navgraph: a gap of 1 m between two pieces is a jump link')
    navmesh.save(gap, data / 'nav' / 'Gap.json.gz')
    low = grid_nav(5, 1, holes={(2, 0)}, level=lambda i, j: 0 if i < 2 else -3)
    A = navgraph.Area('L', nav=low)
    low['xlinks'] = navgraph.compute_xlinks(A)
    kinds = {l['kind'] for l in low['xlinks']}
    check(kinds == {'drop', 'ledge-up'}, 'navgraph: a lower piece is reached by a drop and left by a ledge-up')
    navmesh.save(low, data / 'nav' / 'Low.json.gz')
    plan.use(data)
    r = plan.plan('Gap', (0.5, 0.5), (4.5, 0.5))
    check(not r['ok'] and r['why'] == 'needs-jump' and r['edge'] == 'jump' and r['near'] is not None and r['needed'][0]['allowed'] is False
          and 'no pilot step' in r['detail'], 'plan: a jump is named, with the place to jump from, when jumps are not allowed')
    r = plan.plan('Gap', (0.5, 0.5), (4.5, 0.5), allow=('walk', 'drop', 'jump'))
    check(r['ok'] and r['edges'].count('jump') == 1 and r['needed'][0]['allowed'], 'plan: with jumps allowed the way crosses the gap')
    r = plan.plan('Low', (0.5, 0.5), (4.5, 0.5), from_y=0, to_y=-3)
    check(r['ok'] and 'drop' in r['edges'] and r['needed'][0]['height'] == -3.0, 'plan: a drop within max_drop is part of the way')
    r = plan.plan('Low', (0.5, 0.5), (4.5, 0.5), from_y=0, to_y=-3, max_drop=2)
    check(not r['ok'] and r['why'] == 'needs-drop', 'plan: a drop higher than max_drop is named')
    r = plan.plan('Low', (4.5, 0.5), (0.5, 0.5), from_y=-3, to_y=0)
    check(not r['ok'] and r['why'] == 'needs-climb' and 'ledge-up' in r['edges'], 'plan: the way back up a ledge needs a climb')
    high = grid_nav(5, 1, holes={(2, 0)}, level=lambda i, j: 0 if i < 2 else 5)
    A = navgraph.Area('H', nav=high)
    obj = {'gyaml': 'LadderOne', 'hash': 7, 'pos': [2, 2, 0.5], 'kind': 'climbable'}
    high['xlinks'] = navgraph.compute_xlinks(A, [obj])
    check({l['kind'] for l in high['xlinks'] if 'actor' in l} == {'climb-up', 'climb-down'}
          and all(l['actor'] == 'LadderOne' for l in high['xlinks'] if 'actor' in l) and 'drop' in {l['kind'] for l in high['xlinks']},
          'navgraph: a placed climbable joins the lowest piece near it to each higher one')
    navmesh.save(high, data / 'nav' / 'High.json.gz')
    plan.use(data)
    r = plan.plan('High', (0.5, 0.5), (4.5, 0.5), from_y=0, to_y=5)
    check(not r['ok'] and r['why'] == 'needs-climb' and 'LadderOne' in r['detail'] and 'the pilot has `climb up`' in r['detail'],
          'plan: a climb names the placed object it needs')
    r = plan.plan('High', (0.5, 0.5), (4.5, 0.5), from_y=0, to_y=5, allow=('walk', 'drop', 'climb-up'))
    check(r['ok'] and r['needed'][0]['actor'] == 'LadderOne', 'plan: with climbing allowed the way uses the climbable')
    crawl = grid_nav(5, 1, holes={(2, 0)}, level=lambda i, j: 0)
    A = navgraph.Area('C', nav=crawl)
    marks = [{'gyaml': 'CrawlMark', 'hash': 1, 'pos': [1.5, 0, 0.5]}, {'gyaml': 'CrawlMark', 'hash': 2, 'pos': [3.5, 0, 0.5]},
             {'gyaml': 'Other', 'hash': 3, 'pos': [3.5, 0, 0.5]}]
    cl = navgraph.compute_xlinks(A, (), marks, anchor=T.actors.crawl_anchor)
    check({l['kind'] for l in cl} >= {'crawl'} and sum(l['kind'] == 'crawl' for l in cl) == 2
          and all(l['actor'] == 'CrawlMark' for l in cl if l['kind'] == 'crawl'), 'navgraph: two crawl markers join their pieces both ways')
    check(raises(ValueError, navgraph.compute_xlinks, A, (), marks) is not None, 'navgraph: crawl objects without the marker class are refused')
    # doors and flag-gated people on the way
    door = {'kind': 'door', 'gyaml': 'DoorAlpha', 'pos': [2, 0, 0.5], 'flags': {'self': 'Bool64bitKey 1', 'logic': ['Gate_Open', 'Other']}}
    guard = {'kind': 'blocker', 'gyaml': 'BlockAlpha', 'pos': [3, 0, 0.5], 'scale': [1, 1, 1],
             'flags': {'presence': {'flag': 'Flag_Two', 'negated': True}}}
    (data / 'objects.json').write_text(json.dumps({'AreaA': [door, guard]}))
    plan.use(data)
    r = plan.plan('AreaA', (0.2, 0.5), (3.5, 0.5))
    check(not r['ok'] and r['why'] == 'needs-door' and r['door']['gyaml'] == 'DoorAlpha' and r['door']['flags'] == ['Bool64bitKey 1', 'Gate_Open']
          and 'set Open to 1' in r['detail'] and 'Other' not in r['detail'], 'plan: a door stops the way; the tables say which of its flags are named and what opens it')
    check([g['object'] for g in r['gates']] == ['BlockAlpha'] and r['gates'][0]['present_when'] == 'Flag_Two is false',
          'plan: flag-gated people on the way are reported')
    r = plan.plan('AreaA', (0.2, 0.5), (3.5, 0.5), doors='through')
    check(r['ok'], 'plan: doors=through passes the door')
    os.remove(data / 'tables.json')
    plan.use(data)
    r = plan.plan('AreaA', (0.2, 0.5), (3.5, 0.5))
    check(r['why'] == 'needs-door' and r['door']['flags'] == ['Bool64bitKey 1'] and 'set Open' not in r['detail'],
          'plan: without a tables file the door text still works, naming the door\'s own flag only')
    plan.use(data, objects={'AreaA': []}, areas={'AreaA': navgraph.Area('AreaA', nav=grid_nav(4, 1))})
    check(plan.plan('AreaA', (0.2, 0.5), (3.5, 0.5))['ok'], 'plan: use() takes the objects and meshes a builder holds')
    plan.use(None)


def test_build_classes(check, tmp, T):
    class Rom:
        files = {'Banc/Fold/A_Static.bcett.byml.zs': (0, 10), 'Banc/Fold/A_Dynamic.bcett.byml.zs': (0, 20),
                 'Phive/NavMesh/A.Nin_Ounce_NVN2.bphnm.zs': (0, 5), 'Logic/A_Common.logic.module.ainb': (0, 1), 'x.txt': (0, 3)}
    G = type('G', (), {'romfs': Rom, 'folder': {'A_Young': 'Fold', 'A': 'Fold'}})
    inv = build.inventory(G, ['A'], T)
    row = inv['per_area']['A']
    check(inv['files'] == 5 and row['placement'] == ['Banc/Fold/A_Dynamic.bcett.byml.zs', 'Banc/Fold/A_Static.bcett.byml.zs']
          and row['navmesh'] == ['Phive/NavMesh/A.Nin_Ounce_NVN2.bphnm.zs'] and row['logic_modules'] == 1 and row['banc_param'] is False
          and dict(inv['by_top'])['Banc'] == 2 and dict(inv['bytes_by_top'])['(root)'] == 3, 'build: the inventory counts files per area and folder')
    check(build.inventory(G, ['A_Young'], T)['per_area']['A_Young']['logic_modules'] == 1,
          'build: the inventory finds the files of the base area name of an age version')
    mts = game_files.load_mts()
    names = {H('Flag_One'): 'Flag_One'}
    gdl = {H(n): ('Bool', {'Hash': H(n)}) for n in ('Flag_One', 'Flag_Two')}
    gdl[777] = ('Bool64bitKey', {'Hash': 777})
    exp = {'Values': [[0, H('Flag_One')], [0, H('Flag_Two')], [3], [5], [18, H('Flag_Two')], [16, 1], [5], [4]]}
    gdl[H('Exp')] = ('BoolExp', exp)
    gdl[H('Mode')] = ('Enum', {'Hash': H('Mode'), 'RawValues': ['Low', 'High']})
    gdl[H('Exp2')] = ('BoolExp', {'Values': [[1, H('Mode')], [2, H('High')]]})
    g = type('G', (), {'flags': gdl})()
    F = build.Flags(g, mts, names)
    check(F.offer('Flag_Two') == H('Flag_Two') and F.names[H('Flag_Two')] == 'Flag_Two' and F.offer('Flag_Two') is None
          and F.offer('nothing') is None and F.offer(5) is None and F.offer('') is None and F.b64 == {777} and F.name(H('Flag_One')) == 'Flag_One',
          'build: Flags names a flag when a string hashes to one, once')
    text, reads = F.describe_exp(H('Exp'))
    check(text == '(NOT (Flag_One AND Flag_Two) OR NOT Flag_Two < 1)' and reads == ['Flag_One', 'Flag_Two', 'Flag_Two'],
          'build: a stack program is shown as text, with the flags it reads')
    check(F.describe_exp(H('Exp2'))[0] == '0x%08x == High' % H('Mode') and F.describe_exp(H('Flag_One')) is None
          and F.describe_exp(1) is None, 'build: an enum comparison names the value; a plain flag or an unknown one has no text')
    from worldmodel import model
    check(model.exp_desc(F, H('Exp2')) == F.describe_exp(H('Exp2'))[0] and model.exp_desc(F, 5) is None, 'model: exp_desc')
    f = story.Exp.__new__(story.Exp)
    gq = type('G', (), {'flags': {H('Count_Quest_One'): ('Enum', {'RawValues': ['Idle', 'S1', 'S2']}),
                                  H('Area_IsAfter_Exp'): ('BoolExp', {'Values': [[1, H('Count_Quest_One')], [2, H('S2')]]}),
                                  H('Outer'): ('BoolExp', {'Values': [[10, H('Area_IsAfter_Exp')]]})}})()
    f.g, f.mts, f.step_of, f.cache = gq, mts, {H('Count_Quest_One'): 'Quest_One'}, {}
    check(f.parts('Area_IsAfter_Exp') == [('Quest_One', '==', 'S2')] and f.parts('Outer') == [('Quest_One', '==', 'S2')]
          and f.parts('Nothing') == [], 'story: the quest counter comparisons inside a stack-program flag')
    check(story.Exp(gq, mts, {'Quest_One': {}}, T).step_of == {H('Count_Quest_One'): 'Quest_One'},
          'story: the counters of the quests are named by the tables\' prefix')


def run_main(module, argv, **env):
    out = io.StringIO()
    old = sys.argv
    sys.argv = [module.__file__] + argv
    try:
        with environment(**env), contextlib.redirect_stdout(out):
            module.main()
    finally:
        sys.argv = old
    return out.getvalue()


def test_pipeline(check, tmp, T):
    if zstd is None:
        return
    root = make_game_folder(tmp / 'pipe-game', with_flows=True)
    data = make_data(tmp / 'pipe')
    names = {H('Flag_Two'): 'Flag_Two'}
    (data / 'flag_names.json').write_text(json.dumps({str(k): v for k, v in names.items()}))
    nav = grid_nav(7, 3)
    navmesh.save(nav, data / 'nav' / 'AreaA_Young.json.gz')
    env = {'PILOT_WORLD': data}
    out = run_main(build, ['--game', str(root), '--only', 'inventory,model'], **env)
    check('areas.json: 2 areas, 4 named starts' in out and 'summary.json written' in out and 'flag names: no list' not in out,
          'build: the model step runs on a synthetic RomFS folder and reads the flag name list beside the tables')
    areas = json.loads((data / 'areas.json').read_text())
    a = areas['AreaA_Young']
    check(a['age'] == 'child' and areas['AreaB']['age'] == 'adult' and a['area_index'] == 3 and a['location'] == 'b'
          and a['starts']['(default)']['to_walkable_m'] == 0.0 and a['starts']['StartX']['yaw'] == 1.0,
          'model: areas.json holds the age by the tables, the area parameters and the starts on the mesh')
    check(a['objects'] == {'exit': 1, 'door': 1, 'climbable': 1, 'person': 1, 'chest': 1}, 'model: the objects of an area are counted by kind')
    links = json.loads((data / 'links.json').read_text())
    lk = links[0]
    check(len(links) == 1 and lk['id'] == 'AreaA_Young/GoOne' and lk['to'] == 'AreaB' and lk['to_adult'] == 'AreaB_Old' and lk['to_known'] and lk['to_start'] == 'StartX'
          and lk['to_start_pos'] == [4, 0, 1] and lk['triggers'][0]['logic'] == 'LogicOne.logic.module.ain'
          and lk['triggers'][0]['shape'] == 'default' and lk['go_anchor'] == [6, 0, 1] and lk['events'] == {'InitEvtFlag': 'Flag_One', 'InitEvtName': 'EvOne'}
          and lk['alternative_flag'] == 'Flag_Two' and lk['nearest_start'] == 'StartX' and lk['approach'] is not None,
          'model: an exit with its destination, trigger volume, go-through marker, events and approach, named by the tables')
    objs = json.loads((data / 'objects.json').read_text())['AreaA_Young']
    byk = {o['gyaml']: o for o in objs}
    check(set(byk) == {'ExitAlpha', 'DoorAlpha', 'LadderOne', 'PersonOne', 'ChestOne'} and byk['PersonOne']['fixed'] is False
          and byk['DoorAlpha']['fixed'] is False and byk['DoorAlpha']['moves'] == ['exists only under a flag (Presence)']
          and byk['ChestOne']['fixed'] is True and byk['DoorAlpha']['placement'] == 'Static' and byk['ChestOne']['placement'] == 'Dynamic'
          and byk['PersonOne']['moves'] == ['wanders up to 2 m (MoveRadius)'], 'build: objects get their kind from the tables, fixed by fixed_kinds')
    check(byk['DoorAlpha']['flags']['presence']['flag'] == 'Flag_Two' and byk['DoorAlpha']['flags']['presence']['negated'] is False
          and byk['DoorAlpha']['flags']['params'] == {'FlagKey': 'Flag_One'} and byk['DoorAlpha']['logic'] == ['LogicTwo']
          and byk['DoorAlpha']['flags']['logic'] == ['AreaA_Switch_X', 'Flag_Three', 'Other_TokB_Y'] and byk['ExitAlpha']['params']['InitEvtName'] == 'EvOne',
          'build: flags of an object: presence, parameter keys from the tables, names in its logic module')
    fl = json.loads((data / 'flags.json').read_text())
    named = {x['name'] for k in fl['areas'].values() for v in k.values() for x in v}
    check({'Flag_One', 'Flag_Two', 'Flag_Three'} <= named and fl['counts']['per_actor_bool64'] == 1
          and 'Played.EvOne' in named, 'model: flags.json names the flags whose strings the game files hold, and the played flag of an event')
    wide, area_a, area_b = fl['areas']['(game-wide)'], fl['areas']['AreaA'], fl['areas']['AreaB']
    check([x['name'] for x in wide['played']] == ['Played.EvOne'] and sorted(x['name'] for x in wide['other']) == ['Flag_One', 'Flag_Three', 'Flag_Two']
          and [x['name'] for x in area_a['switch']] == ['AreaA_Switch_X'] and [x['name'] for x in area_b['other']] == ['Other_TokB_Y'],
          'model: flags.json groups the flags by area (an area name in the flag, else a token of the tables) and by category of the tables')
    gates = json.loads((data / 'gates.json').read_text())
    gt = next(x for x in gates['gates'] if x['type'] == 'door present under a flag')
    check(gt['flag'] == 'Flag_Two' and gt['on_way_to_exits'] == ['AreaA_Young/GoOne'] and gt['present_when'] == 'Flag_Two is true'
          and any(x['type'] == 'exit plays an event the first time' and x['flag'] == 'Flag_One' for x in gates['gates'])
          and any(x['type'] == 'exit goes to the alternative area version under a flag' for x in gates['gates'])
          and any(x['type'] == 'door named with flags by its logic module' and 'Flag_Three' in x['flags'] for x in gates['gates']),
          'model: gates: a door under a flag on the planned way to an exit, the exit\'s event and alternative flag, a logic module\'s flags')
    summ = json.loads((data / 'summary.json').read_text())
    check(summ['areas'] == 2 and summ['links'] == 1 and (data / 'mobility.json').is_file() and 'inventory.json' not in out
          and (data / 'inventory.json').is_file(), 'build: summary, mobility and inventory are written')
    # the next steps read the files of this one
    out = run_main(flows, ['--game', str(root)], **env)
    idx = json.loads((data / 'flows.json').read_text())
    check('flows: {"flows": 1, "entries": 1' in out and 'flow edges for 1 gate flags' in out and list(idx['setters']) == ['Flag_One']
          and idx['event_settings'] == {'EvOne': {'flow': 'SynFlow', 'entry': 'Main'}} and 'PersonOne' in idx['schedules'],
          'flows: the whole step runs on the synthetic RomFS folder and adds its edges to gates.json')
    gates = json.loads((data / 'gates.json').read_text())
    check(any(e['strength'] == 'flow' and e['to'] == 'Flag_One' for e in gates['edges']), 'flows: gates.json got the flow edges')
    out = run_main(story, ['--game', str(root)], **env)
    sj = json.loads((data / 'story.json').read_text())
    q = next(x for x in sj['quests'] if x['quest'] == 'Quest_One')
    s2 = q['steps'][2]
    check(sj['counts']['quests'] == 2 and sj['counts']['main_quests'] == 1 and q['category'] == 'CatMain' and q['counter'] == 'Count_Quest_One'
          and q['values'] == ['Idle', 'S1', 'S2', 'Done'] and s2['value'] == 'S2' and s2['boss'] is True and s2['set_by'][0]['flow'] == 'SynFlow'
          and s2['set_by'][0]['conditions'] == [['IsFlag(Flag_Two)']] and q['steps'][0]['unknown'] == [] and 'no flow event advances' in q['steps'][1]['unknown'][0]
          and sj['main_order'][0]['quest'] == 'Quest_One' and 'Count_<quest>' in sj['note'] and next(x for x in sj['quests'] if x['quest'] == 'Quest_Two')['category'].startswith('none'),
          'story: quests, their counters and steps, who sets a step and on which condition, from the tables\' names')
    check('Quest_One <-' in out, 'story: the main order is printed')


def test_refusals(check, tmp):
    data = tmp / 'refuse-data'
    data.mkdir()
    for module, argv in ((build, []), (flows, []), (story, [])):
        with environment(PILOT_WORLD=data):
            e = raises(SystemExit, run_main, module, argv, PILOT_WORLD=data)
        check(e is not None and 'WORLD_GAME' in str(e), f'{module.__name__.split(".")[-1]}: no game folder is refused with the way to give it')
    for module in (build, flows, story):
        e = raises(SystemExit, run_main, module, ['--game', str(tmp / 'nowhere')], PILOT_WORLD=data)
        check(e is not None and 'does not exist' in str(e) and 'actors.kinds' in str(e),
              f'{module.__name__.split(".")[-1]}: no tables file is refused with its name and schema')
    ready = make_data(tmp / 'refuse-story')
    e = raises(SystemExit, run_main, story, ['--game', str(tmp / 'nowhere')], PILOT_WORLD=ready)
    check(e is not None and 'flows.json' in str(e) and 'links.json' in str(e) and 'build.py' in str(e),
          'story: without the files of the earlier steps it says which are missing and what to run first')


def test_script_files(check):
    sh = HERE / 'rebuild.sh'
    text = sh.read_text()
    check(text.startswith('#!/bin/bash') and 'WORLD_GAME' in text and os.access(sh, os.X_OK),
          'rebuild.sh: an executable script that needs WORLD_GAME')
    import subprocess
    check(subprocess.run(['bash', '-n', str(sh)]).returncode == 0, 'rebuild.sh: bash accepts the syntax')
    r = subprocess.run(['bash', str(sh)], capture_output=True, text=True, env={'PATH': os.environ.get('PATH', '')})
    check(r.returncode != 0 and 'WORLD_GAME' in r.stderr, 'rebuild.sh: without WORLD_GAME it stops and says so')


def run():
    check = Checks()
    with tempfile.TemporaryDirectory(prefix='worldmodel-test-') as t, environment():
        tmp = Path(t)
        T = test_tables(check, tmp)
        test_hash_and_archives(check)
        test_romfs(check, tmp)
        test_game_and_save(check, tmp, T)
        test_evfl(check, tmp, T)
        test_nav_and_plan(check, tmp, T)
        test_build_classes(check, tmp, T)
        test_pipeline(check, tmp, T)
        test_refusals(check, tmp)
        test_script_files(check)
    if check.fails:
        print(f'test_worldmodel: {len(check.fails)} of {check.count} checks FAILED')
        sys.exit(1)
    print(f'test_worldmodel: all {check.count} checks passed')


if __name__ == '__main__':
    run()
