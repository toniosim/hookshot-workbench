"""Reader of the game's event flows (`Event/EventFlow/*.bfevfl.zs`, BFEVFL version 4, after zstd). Standard library only.

Layout as found in game 1.1.1's files (all offsets absolute in the file, little endian; checked on a flow whose
names come out readable at every step):

- file header: "BFEVFL\\0\\0", version u32 (0x400), BOM, ..., +0x20 number of flowcharts u16, +0x28 pointer to the
  flowchart offsets (u64 each), +0x30 their name dictionary.
- flowchart "EVFL": +0x10 counts u16 (actors, actions, queries, events, entry points), +0x20 name, +0x28 actors,
  +0x30 events, +0x38 entry point dictionary, +0x40 entry points.
- actor, 0x38 bytes: name, secondary name, argument name, action names (array of string pointers), query names,
  parameters, then u16 number of actions, number of queries, entry point index.
- event, 0x30 bytes (0x28 in the older version 3): name, type u8 (0 action, 1 switch, 2 fork, 3 join, 4 sub flow);
  action: +0x0a next, +0x0c actor, +0x0e actor's action, +0x10 parameters; switch: +0x0a number of cases, +0x0c
  actor, +0x0e actor's query, +0x10 parameters, +0x18 cases (8 bytes each: value u32, event u16); fork: +0x0a number
  of branches, +0x0c join event, +0x10 branch events (u16 each); join: +0x0a next; sub flow: +0x0a next, +0x10
  parameters, +0x18 flowchart name ('' = this flow), +0x20 entry point name. Two types new in version 4 (layout read
  from a flow where both occur): 5, a sub flow call whose returned value is switched on (+0x0a number
  of cases, +0x10 parameters, +0x18 cases as for a switch, the value a hash of the returned label, +0x20 flowchart
  name, +0x28 entry point name); 6, return a value (+0x0c the value's hash), which ends the called entry.
  0xffff is "no event".
- entry point, 0x20 bytes: +0x1c main event u16; names from the dictionary in item order.
- parameter container: type u8 (0 argument, 1 container, 2 int, 3 bool, 4 float, 5 string, 6 wide string, 7 int
  array, 8 bool array, 9 float array, 10 string array, 11 wide string array, 12 actor identifier), +2 count u16, +8 the
  dictionary of a container, +0x10 the value (or the items' pointers of a container).
- strings: u16 length, bytes, NUL; a pointer points at the length.

    f = read(raw)        # {'name', 'actors': [{'name', 'sub', 'actions', 'queries'}], 'events': [...], 'entries': {name: index}}
"""
import struct

ACTION, SWITCH, FORK, JOIN, SUBFLOW, CALL_SWITCH, RETURN = range(7)
NONE = 0xFFFF


class _R:
    def __init__(self, b):
        self.b = b

    def u8(self, o):
        return self.b[o]

    def u16(self, o):
        return struct.unpack_from('<H', self.b, o)[0]

    def i32(self, o):
        return struct.unpack_from('<i', self.b, o)[0]

    def u32(self, o):
        return struct.unpack_from('<I', self.b, o)[0]

    def f32(self, o):
        return struct.unpack_from('<f', self.b, o)[0]

    def u64(self, o):
        return struct.unpack_from('<Q', self.b, o)[0]

    def s(self, o):
        if not o:
            return None
        n = self.u16(o)
        return self.b[o + 2:o + 2 + n].decode('utf-8', 'replace')

    def sp(self, o):
        """String through the pointer stored at o."""
        return self.s(self.u64(o))

    def dic(self, o):
        """Names of a 'DIC ' dictionary in item order (entry 0 is the root)."""
        if not o or self.b[o:o + 4] != b'DIC ':
            return []
        n = self.u32(o + 4)
        return [self.sp(o + 8 + 16 * k + 8) for k in range(1, n + 1)]

    def container(self, o):
        if not o:
            return None
        t, n = self.u8(o), self.u16(o + 2)
        v = o + 0x10
        if t == 1:
            names = self.dic(self.u64(o + 8))
            return {names[k] if k < len(names) else f'#{k}': self.container(self.u64(v + 8 * k)) for k in range(n)}
        if t == 0:
            return {'$arg': self.sp(v)}
        if t == 2:
            return self.i32(v)
        if t == 3:
            return bool(self.u32(v))
        if t == 4:
            return round(self.f32(v), 4)
        if t in (5, 6):
            return self.sp(v)
        if t == 7:
            return [self.i32(v + 4 * k) for k in range(n)]
        if t == 8:
            return [bool(self.u32(v + 4 * k)) for k in range(n)]
        if t == 9:
            return [round(self.f32(v + 4 * k), 4) for k in range(n)]
        if t in (10, 11):
            return [self.sp(v + 8 * k) for k in range(n)]
        if t == 12:
            return {'$actor': self.sp(v), '$sub': self.sp(v + 8)}
        return {'$type': t}


def read(raw):
    r = _R(raw)
    if raw[:8] != b'BFEVFL\x00\x00':
        raise ValueError('not a BFEVFL file')
    version = r.u32(8)
    estride = 0x30 if version >= 0x400 else 0x28
    nflow = r.u16(0x20)
    if nflow == 0:
        return None
    fc = r.u64(r.u64(0x28))
    if raw[fc:fc + 4] != b'EVFL':
        raise ValueError('flowchart magic')
    na, _nact, _nq, ne, nep = (r.u16(fc + 0x10 + 2 * k) for k in range(5))
    out = {'name': r.sp(fc + 0x20), 'version': version, 'actors': [], 'events': [], 'entries': {}}
    ao = r.u64(fc + 0x28)
    for i in range(na):
        o = ao + i * 0x38
        nact, nq = r.u16(o + 48), r.u16(o + 50)
        aa, qq = r.u64(o + 24), r.u64(o + 32)
        out['actors'].append({'name': r.sp(o), 'sub': r.sp(o + 8) or '', 'arg': r.sp(o + 16) or '',
                              'actions': [r.sp(aa + 8 * k) for k in range(nact)],
                              'queries': [r.sp(qq + 8 * k) for k in range(nq)]})
    eo = r.u64(fc + 0x30)
    for i in range(ne):
        o = eo + i * estride
        t = r.u8(o + 8)
        e = {'i': i, 'name': r.sp(o), 'type': t}
        if t == ACTION:
            e.update(next=r.u16(o + 0x0a), actor=r.u16(o + 0x0c), act=r.u16(o + 0x0e), params=r.container(r.u64(o + 0x10)))
        elif t == SWITCH:
            nc, co = r.u16(o + 0x0a), r.u64(o + 0x18)
            e.update(actor=r.u16(o + 0x0c), query=r.u16(o + 0x0e), params=r.container(r.u64(o + 0x10)),
                     cases=[(r.u32(co + 8 * k), r.u16(co + 8 * k + 4)) for k in range(nc)])
        elif t == FORK:
            nf, fo = r.u16(o + 0x0a), r.u64(o + 0x10)
            e.update(join=r.u16(o + 0x0c), forks=[r.u16(fo + 2 * k) for k in range(nf)])
        elif t == JOIN:
            e.update(next=r.u16(o + 0x0a))
        elif t == SUBFLOW:
            e.update(next=r.u16(o + 0x0a), params=r.container(r.u64(o + 0x10)), flow=r.sp(o + 0x18),
                     entry=r.sp(o + 0x20))
        elif t == CALL_SWITCH:
            nc, co = r.u16(o + 0x0a), r.u64(o + 0x18)
            e.update(params=r.container(r.u64(o + 0x10)), flow=r.sp(o + 0x20), entry=r.sp(o + 0x28),
                     cases=[(r.u32(co + 8 * k), r.u16(co + 8 * k + 4)) for k in range(nc)])
        elif t == RETURN:
            e.update(value=r.u32(o + 0x0c))
        out['events'].append(e)
    names = r.dic(r.u64(fc + 0x38))
    po = r.u64(fc + 0x40)
    for k in range(nep):
        out['entries'][names[k] if k < len(names) else f'#{k}'] = r.u16(po + 0x20 * k + 0x1c)
    return out


def label(f, e):
    """'Actor.Action' or 'Actor.Query' of an action or switch event."""
    a = f['actors'][e['actor']] if e.get('actor', NONE) < len(f['actors']) else {'name': '?', 'actions': [], 'queries': []}
    if e['type'] == ACTION:
        n = a['actions'][e['act']] if e['act'] < len(a['actions']) else f'action{e["act"]}'
    else:
        n = a['queries'][e['query']] if e['query'] < len(a['queries']) else f'query{e["query"]}'
    return f"{a['name']}{'[' + a['sub'] + ']' if a.get('sub') else ''}.{n}"
