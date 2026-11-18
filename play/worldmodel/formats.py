"""The file formats of the game, read with the standard library only (zstd comes from `compression.zstd`, Python 3.14,
imported when a compressed file is first read, so this module imports on an older Python too).

- `murmur(name)`: MurmurHash3 x86 32-bit, the game's flag hash of a flag's full name; `flag_hash(text)`: a hash given
  as 0x..., as decimal digits, or as a name.
- `sarc(bytes)`: {file name: bytes} of a SARC archive of either byte order.
- `byml(bytes)`: the value of a BYML file of either byte order (with the hash-keyed dictionaries of this engine).
- `Romfs(folder)`: a plain RomFS folder (`.raw(path)`, `.load(path)` which also unpacks `.zs` with the game's own
  dictionaries from Pack/ZsDic.pack.zs, `.files`).
- `Game(folder)`: the flag list of GameData/GameDataList (`.flags` hash -> (type name, entry)), the area start
  positions (`.starts`), the placement folder of every area (`.folder`), area parameters (`.bancparam(area)`) and
  placed actors (`.actors(area)`).
- `Sav(path, game)`: a .sav of the game, read and written in place.
- `yaw_of(rot)`: the yaw of a start position's Euler rotation.

Nothing in here names game content: the paths are the RomFS layout's, the type names those of the save format.
"""
import math
import os
import re
import struct
import sys
from pathlib import Path

GAMEDATA = 'GameData/GameDataList.Product.110.byml.zs'
REVISION = 'GameData/GameDataList.Product.110.revision.txt'
STARTPOS = 'Banc/BancBasedResource/StartPos.byml.zs'
BANCPARAM = 'Banc/GameBancParam/{}.game__banc__GameBancParam.bgyml'
ZSDICT = 'Pack/ZsDic.pack.zs'
MAGIC = 0x01020304          # a save file's first word
TAIL_HASH = 0xa3db7114      # the save's type hash: its table entry closes the table of flags
PI = math.pi


def die(msg):
    sys.exit(f'worldmodel: {msg}')


def _zstd():
    try:
        from compression import zstd
    except ImportError:
        die('reading the game\'s .zs files needs Python 3.14 or later (compression.zstd)')
    return zstd


def murmur(s, seed=0):
    """MurmurHash3 x86 32-bit: the game's flag hash (of the flag's full name)."""
    data = s.encode() if isinstance(s, str) else s
    c1, c2, h, n = 0xcc9e2d51, 0x1b873593, seed, len(data) // 4
    for (k,) in struct.iter_unpack('<I', data[:n * 4]):
        k = (k * c1) & 0xffffffff
        k = ((k << 15) | (k >> 17)) & 0xffffffff
        h ^= (k * c2) & 0xffffffff
        h = ((h << 13) | (h >> 19)) & 0xffffffff
        h = (h * 5 + 0xe6546b64) & 0xffffffff
    tail, k = data[n * 4:], 0
    for i in reversed(range(len(tail))):
        k ^= tail[i] << (8 * i)
    if tail:
        k = (k * c1) & 0xffffffff
        k = ((k << 15) | (k >> 17)) & 0xffffffff
        h ^= (k * c2) & 0xffffffff
    h ^= len(data)
    h ^= h >> 16
    h = (h * 0x85ebca6b) & 0xffffffff
    h ^= h >> 13
    h = (h * 0xc2b2ae35) & 0xffffffff
    return h ^ (h >> 16)


def flag_hash(name):
    return int(name, 16) if name.lower().startswith('0x') else int(name) if name.isdigit() else murmur(name)


def yaw_of(rot):
    """The yaw (radians about +y, 0 facing +z) of a start position's Euler rotation."""
    return rot[1] if abs(rot[0]) < 1.6 else PI - rot[1]


# ---------------------------------------------------------------------------------------------------------- archives
def sarc(data):
    e = '<' if data[6:8] == b'\xff\xfe' else '>'
    header, _, start = struct.unpack_from(e + 'HxxII', data, 4)
    count = struct.unpack_from(e + 'H', data, header + 6)[0]
    names, out = header + 12 + count * 16 + 8, {}
    for i in range(count):
        _, attr, lo, hi = struct.unpack_from(e + '4I', data, header + 12 + i * 16)
        o = names + (attr & 0xffffff) * 4
        out[data[o:data.index(0, o)].decode()] = data[start + lo:start + hi]
    return out


def byml(d):
    """BYML of either byte order, with the hash-keyed dictionaries of this engine (0x20, 0x21)."""
    e = '<' if d[:2] == b'YB' else '>'
    _, kt, st, root = struct.unpack_from(e + 'HIII', d, 2)
    U = lambda o: struct.unpack_from(e + 'I', d, o)[0]
    n24 = lambda o: U(o) >> 8 if e == '<' else U(o) & 0xffffff     # a node's count: the 3 bytes after its type byte

    def table(o):
        if not o:
            return []
        n = n24(o)
        offs = struct.unpack_from(e + '%dI' % (n + 1), d, o + 4)
        return [d[o + x:d.index(0, o + x)].decode('utf8', 'replace') for x in offs[:n]]
    keys, strs = table(kt), table(st)

    def val(t, v):
        if t == 0xa0: return strs[v]
        if t in (0xa1, 0xa2): return d[v + 4:v + 4 + U(v)]
        if t in (0x20, 0x21, 0xc0, 0xc1): return node(v)
        if t == 0xd0: return bool(v)
        if t == 0xd1: return struct.unpack(e + 'i', struct.pack(e + 'I', v))[0]
        if t == 0xd2: return struct.unpack(e + 'f', struct.pack(e + 'I', v))[0]
        if t == 0xd3: return v
        if t == 0xd4: return struct.unpack_from(e + 'q', d, v)[0]
        if t == 0xd5: return struct.unpack_from(e + 'Q', d, v)[0]
        if t == 0xd6: return struct.unpack_from(e + 'd', d, v)[0]
        if t == 0xff: return None
        raise ValueError(f'BYML value type {t:#x}')

    def node(o):
        t, n = d[o], n24(o)
        if t in (0x20, 0x21):
            w = 8 if t == 0x20 else 12
            ents = [struct.unpack_from(e + ('II' if t == 0x20 else 'QI'), d, o + 4 + w * i) for i in range(n)]
            types = o + 4 + w * n
            return {h: val(d[types + i], v) for i, (h, v) in enumerate(ents)}
        if t == 0xc0:
            types, vals = o + 4, o + 4 + ((n + 3) & ~3)
            return [val(d[types + i], U(vals + 4 * i)) for i in range(n)]
        if t == 0xc1:
            out = {}
            for i in range(n):
                p = o + 4 + 8 * i
                out[keys[U(p) & 0xffffff if e == '<' else U(p) >> 8]] = val(d[p + 3], U(p + 4))
            return out
        raise ValueError(f'BYML node type {t:#x}')
    return node(root)


# ------------------------------------------------------------------------------------------------------- game files
class PlainFiles:
    """The paths of a plain RomFS folder: membership asks the file system, iteration lists Banc/ (all a Game scans)."""
    def __init__(self, root):
        self.root = root

    def __contains__(self, path):
        return (self.root / path).is_file()

    def __iter__(self):
        for d, _, names in os.walk(self.root / 'Banc'):
            rel = Path(d).relative_to(self.root).as_posix()
            for n in names:
                yield f'{rel}/{n}'


class Romfs:
    """A plain RomFS folder, or a game copy that holds romfs/."""
    files_class = PlainFiles

    def __init__(self, game):
        g = Path(game)
        root = g if (g / 'GameData').is_dir() else g / 'romfs'
        if not (root / 'GameData').is_dir():
            die(f'{game} is not a RomFS folder (a folder that holds GameData/) and holds no romfs/ of one')
        self.root = root
        self.files = self.files_class(root)
        self._dicts = None

    def raw(self, path):
        return (self.root / path).read_bytes()

    def load(self, path):
        """The file's bytes; a `.zs` file is unpacked (with the game's own dictionary when its frame names one)."""
        data = self.raw(path)
        if not path.endswith('.zs'):
            return data
        zstd = _zstd()
        info = zstd.get_frame_info(data)
        return zstd.decompress(data, zstd_dict=self.dicts().get(info.dictionary_id) if info.dictionary_id else None)

    def dicts(self):
        """{dictionary id: ZstdDict} of the game's dictionary pack, read once."""
        if self._dicts is None:
            zstd = _zstd()
            self._dicts = {}
            for d in sarc(zstd.decompress(self.raw(ZSDICT))).values():
                z = zstd.ZstdDict(d)
                self._dicts[z.dict_id] = z
        return self._dicts


class Game:
    """What the builders read of the game: flag types and enum values, start positions, area parameters, placements."""
    romfs_class = Romfs

    def __init__(self, game):
        self.dir = Path(game)
        self.romfs = self.romfs_class(game)
        self.flags = {}                       # hash -> (type, GameDataList entry)
        for tn, entries in byml(self.romfs.load(GAMEDATA))['Data'].items():
            for ent in entries:
                self.flags[ent['Hash']] = (tn, ent)
        self.revision = int(self.romfs.raw(REVISION).strip() or 0)
        self.starts = byml(self.romfs.load(STARTPOS))
        self.folder = {}                      # area -> Banc/<folder>/ that holds its placement files
        for p in self.romfs.files:
            m = re.match(r'Banc/([^/]+)/(.+)_(Dynamic|Static)\.bcett\.byml\.zs$', p)
            if m:
                self.folder[m.group(2)] = m.group(1)
        self._param, self._actors = {}, {}

    def bancparam(self, banc):
        if banc not in self._param:
            p = BANCPARAM.format(banc)
            self._param[banc] = byml(self.romfs.raw(p)) if p in self.romfs.files else None
        return self._param[banc]

    def actors(self, banc):
        if banc not in self._actors:
            out = []
            for kind in ('Dynamic', 'Static'):
                p = f'Banc/{self.folder[banc]}/{banc}_{kind}.bcett.byml.zs'
                if p in self.romfs.files:
                    out += byml(self.romfs.load(p)).get('Actors', [])
            self._actors[banc] = out
        return self._actors[banc]

    def enum_hash(self, flag, value):
        tn, ent = self.flags[flag]
        if value not in ent.get('RawValues', ()):
            die(f'{value!r} is not a value of that enum ({" ".join(ent.get("RawValues", ())[:20])} ...)')
        return murmur(value)

    def enum_name(self, flag, value):
        ent = self.flags.get(flag, (None, {}))[1]
        return {murmur(v): v for v in ent.get('RawValues', ())}.get(value, f'{value:#x}')


# ------------------------------------------------------------------------------------------------------------ the save
class Sav:
    """A .sav of the game: header (magic, GameDataList revision, data offset), a table of {hash, value} grouped by
    type with a {0, k} marker after group k, values of the larger types at offsets in the data section after it.
    There is no checksum or size field: values are changed in place and every other byte is kept."""
    def __init__(self, path, game):
        self.path, self.game = Path(path), game
        self.b = bytearray(self.path.read_bytes())
        if len(self.b) < 0x30:
            raise ValueError(f'{self.path.name} is {len(self.b)} bytes')
        magic, self.revision, start = struct.unpack_from('<III', self.b, 0)
        if magic != MAGIC:
            raise ValueError(f'{self.path.name} has no save header ({magic:#x})')
        if not 0x28 < start <= len(self.b):
            raise ValueError(f'{self.path.name}: data offset {start} outside the file')
        self.at = {}                          # hash -> table offset of its {hash, value}
        o = 0x28
        while o < start:
            h, _ = struct.unpack_from('<II', self.b, o)
            if h:
                self.at[h] = o
            o += 8
            if h == TAIL_HASH:
                break

    def has(self, h):
        return h in self.at and h in self.game.flags

    def type(self, h):
        return self.game.flags[h][0]

    def _word(self, h):
        return struct.unpack_from('<I', self.b, self.at[h] + 4)[0]

    def get(self, h, default=None):
        if not self.has(h):
            return default
        tn, w = self.type(h), self._word(h)
        if tn == 'Bool': return bool(w)
        if tn == 'Int': return struct.unpack('<i', struct.pack('<I', w))[0]
        if tn in ('UInt', 'Enum'): return w
        if tn == 'Float': return struct.unpack('<f', struct.pack('<I', w))[0]
        if tn == 'Vector3': return struct.unpack_from('<3f', self.b, w)
        if tn in ('UInt64', 'Int64'): return struct.unpack_from('<Q' if tn == 'UInt64' else '<q', self.b, w)[0]
        if tn.startswith('String') and not tn.endswith('Array'):
            n = int(tn[6:])
            return bytes(self.b[w:w + n]).split(b'\0')[0].decode('utf8', 'replace')
        if tn in ('IntArray', 'UIntArray', 'EnumArray'):
            n = struct.unpack_from('<I', self.b, w)[0]
            return list(struct.unpack_from('<%d%s' % (n, 'i' if tn == 'IntArray' else 'I'), self.b, w + 4))
        raise KeyError(f'{h:#010x}: type {tn} is not read here')

    def set(self, h, value):
        if not self.has(h):
            die(f'flag {h:#010x} is not in {self.path.parent.name}/{self.path.name}')
        tn, o, w = self.type(h), self.at[h] + 4, self._word(h)
        if tn == 'Bool':
            struct.pack_into('<I', self.b, o, 1 if value else 0)
        elif tn == 'Int':
            struct.pack_into('<i', self.b, o, int(value))
        elif tn == 'UInt':
            struct.pack_into('<I', self.b, o, int(value) & 0xffffffff)
        elif tn == 'Enum':
            struct.pack_into('<I', self.b, o, value if isinstance(value, int) else self.game.enum_hash(h, value))
        elif tn == 'Float':
            struct.pack_into('<f', self.b, o, float(value))
        elif tn in ('UInt64', 'Int64'):
            struct.pack_into('<Q' if tn == 'UInt64' else '<q', self.b, w, int(value))
        elif tn == 'Vector3':
            struct.pack_into('<3f', self.b, w, *map(float, value))
        elif tn.startswith('String') and not tn.endswith('Array'):
            n, raw = int(tn[6:]), str(value).encode()
            if len(raw) >= n:
                die(f'{value!r} is longer than a {tn} holds')
            self.b[w:w + n] = raw + bytes(n - len(raw))
        elif tn in ('IntArray', 'UIntArray', 'EnumArray'):
            idx, v = value                      # one element: (index, value)
            n = struct.unpack_from('<I', self.b, w)[0]
            if not 0 <= idx < n:
                die(f'index {idx} is outside the {n} elements of {h:#010x}')
            if tn == 'EnumArray' and not isinstance(v, int):
                v = self.game.enum_hash(h, v)
            struct.pack_into('<i' if tn == 'IntArray' else '<I', self.b, w + 4 + 4 * idx, v)
        else:
            die(f'flag {h:#010x} is a {tn}; this reader does not write that type')

    def save(self, path):
        Path(path).write_bytes(self.b)
