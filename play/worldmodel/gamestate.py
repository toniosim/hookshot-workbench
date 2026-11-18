"""A save's flags as the game's conditions see them: plain flags read from progress.sav, BoolExp flags evaluated
from GameDataList's stack programs (codes as build.py's Flags.describe_exp infers them: push 0 Bool, 10 BoolExp,
1/12/11 an enum compared ==, >=, < with the value pushed by 2 (order: the enum's value list), 15/18/19 an Int
compared ==, <, > with the number pushed by 16; 3 AND, 4 OR, 5 NOT). [INFERENCE: the codes; an unknown code gives
None, never a guess.]

    st = State(game, mts, '<save dir or slot dir>')
    st.value('Some_Flag_Name')   # True / False / None (not in the save, not readable)
"""
from pathlib import Path


class State:
    def __init__(self, g, mts, save):
        p = Path(save)
        if p.is_dir() and not (p / 'progress.sav').is_file():
            slots = sorted(p.glob('slot_*/progress.sav'))
            p = slots[0] if slots else p / 'progress.sav'
        elif p.is_dir():
            p = p / 'progress.sav'
        self.g, self.mts = g, mts
        self.sav = mts.Sav(p, g)
        self.path = p

    def raw(self, h):
        try:
            return self.sav.get(h)
        except KeyError:
            return None

    def value(self, name_or_hash, depth=0):
        h = name_or_hash if isinstance(name_or_hash, int) else self.mts.murmur(name_or_hash)
        ent = self.g.flags.get(h)
        if ent is None:
            return None
        tn, e = ent
        if tn != 'BoolExp':
            return self.raw(h)
        if depth > 12:
            return None
        return self._eval(e.get('Values') or [], depth)

    def _eval(self, prog, depth):
        st, pending = [], None
        for item in prog:
            code = item[0]
            if len(item) == 1:
                if code == 5 and st:
                    a = st.pop()
                    st.append(None if a is None else not a)
                elif code in (3, 4) and len(st) >= 2:
                    b, a = st.pop(), st.pop()
                    if code == 3:
                        st.append(False if (a is False or b is False) else (None if None in (a, b) else True))
                    else:
                        st.append(True if (a is True or b is True) else (None if None in (a, b) else False))
                else:
                    return None
                continue
            v = item[1]
            if code in (2, 16) and pending is not None:
                h, op = pending
                pending = None
                cur = self.raw(h)
                if cur is None:
                    st.append(None)
                    continue
                if code == 2:
                    vals = (self.g.flags.get(h, (None, {}))[1] or {}).get('Values') or []
                    if cur not in vals or v not in vals:
                        st.append(None)
                        continue
                    a, b = vals.index(cur), vals.index(v)
                else:
                    a, b = cur, v
                st.append({'==': a == b, '>=': a >= b, '<': a < b, '>': a > b}[op])
                continue
            if code == 0:
                st.append(self.raw(v))
            elif code == 10:
                st.append(self.value(v, depth + 1))
            elif code in (1, 12, 11, 15, 18, 19):
                pending = (v, {1: '==', 12: '>=', 11: '<', 15: '==', 18: '<', 19: '>'}[code])
            else:
                return None
        return st[0] if len(st) == 1 else None
