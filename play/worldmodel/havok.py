"""Reader of the game's physics files (Phive wrapper around a Havok tag file, sections TAG0/SDKV/DATA/TYPE/INDX).

Standard library only. Reads the type table (names, template parameters, members with offsets), the item table and the
data section, and decodes records, arrays and pointers by the type information the file carries, so no layout is
assumed here. Used for the nav meshes (hkaiNavMesh in Phive/NavMesh/*.bphnm and Phive/StitchedNavMesh/*/*.bphnm).

    t = Tagfile(raw_bytes)          # bytes of a .bphnm after zstd
    root = t.root()                 # dict of the first item (hkRootLevelContainer)
"""
import struct

KIND_VOID, KIND_OPAQUE, KIND_BOOL, KIND_STRING, KIND_INT, KIND_FLOAT, KIND_PTR, KIND_RECORD, KIND_ARRAY = range(9)


class _Packed:
    """Havok's variable-length unsigned integers of the TYPE section."""
    def __init__(self, b):
        self.b, self.p = b, 0

    def u(self):
        b, p = self.b, self.p
        x = b[p]
        if x & 0x80 == 0:
            self.p += 1
            return x
        if x & 0xC0 == 0x80:
            self.p += 2
            return ((x & 0x3F) << 8) | b[p + 1]
        if x & 0xE0 == 0xC0:
            self.p += 3
            return ((x & 0x1F) << 16) | (b[p + 1] << 8) | b[p + 2]
        if x & 0xF8 == 0xE0:
            self.p += 4
            return ((x & 0x07) << 24) | (b[p + 1] << 16) | (b[p + 2] << 8) | b[p + 3]
        if x == 0xE8:
            self.p += 6
            return int.from_bytes(b[p + 1:p + 6], 'big')
        if x == 0xE9:
            self.p += 9
            return int.from_bytes(b[p + 1:p + 9], 'big')
        raise ValueError(f'packed int prefix {x:#x}')

    def more(self):
        return self.p < len(self.b)


class Type:
    __slots__ = ('index', 'name', 'tparams', 'parent', 'format', 'subtype', 'version', 'size', 'align', 'flags',
                 'members', 'interfaces', 'attribute', 'hash')

    def __init__(self, index, name, tparams):
        self.index, self.name, self.tparams = index, name, tparams
        self.parent = self.format = self.subtype = self.version = self.size = self.align = None
        self.flags, self.members, self.interfaces, self.attribute, self.hash = 0, [], [], None, None

    def __repr__(self):
        return f'Type({self.index} {self.full_name()})'

    def full_name(self):
        if not self.tparams:
            return self.name
        return self.name + '<' + ', '.join(f'{k}={v}' for k, v in self.tparams) + '>'


class Tagfile:
    def __init__(self, data):
        if data[:5] == b'Phive':
            off = struct.unpack_from('<I', data, 12)[0]
        else:
            off = 0
        self.raw = data
        self.sec = {}
        self._walk(off, off + (struct.unpack_from('>I', data, off)[0] & 0x3FFFFFFF), '')
        if 'TAG0' not in self.sec:
            raise ValueError('not a Havok tag file')
        self.sdk = self.body('TAG0/SDKV').decode('latin1')
        self.data_off = self.sec['TAG0/DATA'][0]
        self._types()
        self._items()

    def _walk(self, off, end, prefix):
        while off < end:
            w = struct.unpack_from('>I', self.raw, off)[0]
            flags, size = w >> 30, w & 0x3FFFFFFF
            tag = self.raw[off + 4:off + 8].decode('latin1')
            path = prefix + tag
            self.sec[path] = (off + 8, off + size)
            if flags == 0:
                self._walk(off + 8, off + size, path + '/')
            off += size

    def body(self, path):
        a, b = self.sec[path]
        return self.raw[a:b]

    def _strings(self, *paths):
        for p in paths:
            if p in self.sec:
                return [s.decode('latin1') for s in self.body(p).split(b'\0')]
        return []

    def _types(self):
        tst = self._strings('TAG0/TYPE/TST1', 'TAG0/TYPE/TSTR')
        fst = self._strings('TAG0/TYPE/FST1', 'TAG0/TYPE/FSTR')
        r = _Packed(self.body('TAG0/TYPE/TNA1' if 'TAG0/TYPE/TNA1' in self.sec else 'TAG0/TYPE/TNAM'))
        n = r.u()
        self.types = [None]
        raw_tp = [None]
        for i in range(1, n):
            name = tst[r.u()]
            tp = []
            for _ in range(r.u()):
                k = tst[r.u()]
                tp.append((k, r.u()))
            raw_tp.append(tp)
            self.types.append(Type(i, name, tp))
        # template parameters: 't...' name a type index, 'v...' a value
        for t in self.types[1:]:
            t.tparams = [(k[1:], self.types[v] if k.startswith('t') and 0 < v < len(self.types) else v) for k, v in t.tparams]
        r = _Packed(self.body('TAG0/TYPE/TBDY' if 'TAG0/TYPE/TBDY' in self.sec else 'TAG0/TYPE/TBOD'))
        while r.more():
            ti = r.u()
            if ti == 0:
                continue
            t = self.types[ti]
            t.parent = self.types[r.u()] or None
            opt = r.u()
            if opt & 0x01:
                t.format = r.u()
            if opt & 0x02:
                t.subtype = self.types[r.u()] or None
            if opt & 0x04:
                t.version = r.u()
            if opt & 0x08:
                t.size = r.u()
                t.align = r.u()
            if opt & 0x10:
                t.flags = r.u()
            if opt & 0x20:
                for _ in range(r.u()):
                    name, flags, offset, mt = fst[r.u()], r.u(), r.u(), r.u()
                    t.members.append((name, flags, offset, self.types[mt]))
            if opt & 0x40:
                for _ in range(r.u()):
                    t.interfaces.append((self.types[r.u()], r.u()))
            if opt & 0x80:
                t.attribute = tst[r.u()] if False else r.u()
        if 'TAG0/TYPE/THSH' in self.sec:
            r = _Packed(self.body('TAG0/TYPE/THSH'))
            for _ in range(r.u()):
                ti = r.u()
                h = struct.unpack_from('<I', r.b, r.p)[0]
                r.p += 4
                if 0 < ti < len(self.types):
                    self.types[ti].hash = h
        self.by_name = {}
        for t in self.types[1:]:
            self.by_name.setdefault(t.name, t)

    def _items(self):
        b = self.body('TAG0/INDX/ITEM')
        self.items = []
        for i in range(0, len(b), 12):
            tf, off, cnt = struct.unpack_from('<III', b, i)
            self.items.append((self.types[tf & 0xFFFFFF] if tf & 0xFFFFFF else None, tf >> 24, off, cnt))

    # ------------------------------------------------------------------------------------------------- type helpers
    def fmt(self, t):
        while t is not None and t.format is None:
            t = t.parent
        return t.format if t else 0

    def kind(self, t):
        return self.fmt(t) & 0xF

    def size(self, t):
        s = t
        while s is not None and s.size is None:
            s = s.parent
        return s.size if s else 0

    def all_members(self, t):
        chain = []
        while t is not None:
            chain.append(t)
            t = t.parent
        out = []
        for c in reversed(chain):
            out += c.members
        return out

    def subtype(self, t):
        while t is not None and t.subtype is None:
            t = t.parent
        return t.subtype if t else None

    # ------------------------------------------------------------------------------------------------------ decoding
    def read(self, t, off, depth=0):
        """Decode one value of type t at offset off of the DATA section's start."""
        f = self.fmt(t)
        k = f & 0xF
        a = self.data_off + off
        if k == KIND_BOOL:
            n = self.size(t) or 1
            return bool(int.from_bytes(self.raw[a:a + n], 'little'))
        if k == KIND_INT:
            n = self.size(t) or (f >> 10) // 8 or 4
            return int.from_bytes(self.raw[a:a + n], 'little', signed=bool(f & 0x200))
        if k == KIND_FLOAT:
            n = self.size(t) or 4
            if n == 4:
                return struct.unpack_from('<f', self.raw, a)[0]
            if n == 2:
                return struct.unpack_from('<e', self.raw, a)[0]
            return struct.unpack_from('<d', self.raw, a)[0]
        if k == KIND_STRING:
            idx = struct.unpack_from('<Q', self.raw, a)[0]
            return self.item_string(idx)
        if k == KIND_PTR:
            idx = struct.unpack_from('<Q', self.raw, a)[0]
            return ('ptr', idx)
        if k == KIND_ARRAY:
            if f & 0x20:          # fixed size, inline
                n = f >> 8
                st = self.subtype(t)
                es = self.size(st)
                return [self.read(st, off + i * es, depth + 1) for i in range(n)]
            idx, cnt = struct.unpack_from('<QI', self.raw, a)
            return ('array', idx, cnt)
        if k == KIND_RECORD:
            out = {}
            for name, _flags, moff, mt in self.all_members(t):
                out[name] = self.read(mt, off + moff, depth + 1)
            return out
        if k == KIND_OPAQUE or k == KIND_VOID:
            return None
        return None

    def item_string(self, idx):
        if not idx or idx >= len(self.items):
            return None
        t, fl, off, cnt = self.items[idx]
        a = self.data_off + off
        return self.raw[a:a + cnt].split(b'\0')[0].decode('latin1')

    def item(self, idx):
        """The values of item idx: a list (array items) or a single decoded record."""
        t, fl, off, cnt = self.items[idx]
        es = self.size(t)
        vals = [self.read(t, off + i * es) for i in range(cnt)]
        return vals

    def item_raw(self, idx):
        t, fl, off, cnt = self.items[idx]
        a = self.data_off + off
        return t, self.raw[a:a + cnt * self.size(t)], cnt

    def root(self):
        for i, it in enumerate(self.items):
            if it[0] is not None:
                return self.item(i)[0]
        return None
