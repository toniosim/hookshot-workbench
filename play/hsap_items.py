"""hsap_items: the item box's steps of hsap.py's Executor (`class Executor(ActionSteps, ItemSteps)`): choosing the item the item button
(ZR) uses, and using it. The game keeps the choice in a flag of an enum type, one flag per age, so every step here ends by what that
flag says, and the count flag of an item says whether it was used: `watch` them before the game starts (a step cannot add a watch later;
without the choice's flag a step says `unverified`).

  wheel-select <item> [via <way>] [tries <n>]   selected / already / not-found / unverified / none / held / cut
  use-item <item> [hold <ms>] [fire release|y|a|zr|none] [lock]   used / aimed / none / no-item / held / cut

<item> is a word of the item table: a plain one (its `aliases`) or one of the enum's own names, in any case, with `-` or `_` or nothing
between the words.

wheel-select opens the item wheel (L held: it shows only while the button is down), moves its cursor one item toward the item, takes
the item under it and reads the flag; it goes on until the flag names the item, or the wheel has come round (not-found: the player
has not got it). The way the cursor moves and is taken is not known for sure, so there is a ladder of ways (WHEEL_VIA): the first one
that changes the flag is the way, kept for the rest of the run (`via` forces one). The step event's `changes` has `via`, the items
seen on the way and how many tries it took.

use-item chooses the item (as wheel-select does) and then holds ZR: `hold` ms (default 150, an aiming item's 1000), and `fire` says
what ends an aim: nothing (release: the ZR is let go), or a press of Y, A or ZR 0.3 s before the hold ends. `lock` holds ZL around it.
used: the item's count fell (or a flag, the rupees, the life changed); aimed: only the camera or Link turned, nothing was spent; none.

The item table. What the game calls its items (the names of the choice enum in its order, the flag of each age's choice, the flag that
holds each item's count, which items a held ZR aims, the order the wheel lists them in) is read out of the game, so none of it is in this
file: it is a JSON file kept on the machine that plays, named by $HSAP_ITEMS (`use_table(path)` names it from code and wins). There is
no default. A step that needs the table without one, or with a file that is not what SCHEMA says, is refused (a bad step: the answer
names the setting or the file and the schema), and nothing is sent to the game. The names are the game's own: a step's words and the
enum's values (the bridge reports an enum value as the MurmurHash3 of its name) are read through them.

hsap imports this module (it must, to inherit ItemSteps), so it cannot import hsap: hsap.py hands the few helpers these steps share
with its own to bind() once they are defined."""
import json
import os
import time

HELPERS = ('wrap', 'text_open', 'split_opts', 'seconds_of')
wrap = text_open = split_opts = seconds_of = None   # (bound by hsap.py)

ITEM_VERBS = ('wheel-select', 'use-item')

ITEMS_SETTING = 'HSAP_ITEMS'
KEYS = ('enum', 'aliases', 'aiming', 'stock', 'choice_flags', 'wheel_order')
SCHEMA = ('a JSON object {"enum": [every item name of the choice enum, in its order], "aliases": {plain word (lower case, - between words): '
          'item name}, "aiming": [the item names a held ZR aims], "stock": {item name: the flag that holds its count}, '
          '"choice_flags": {"adult": the flag of the adult\'s choice, "child": the flag of the child\'s choice}, '
          '"wheel_order": [item names in the order the wheel lists them]}; every item name must be in "enum"')

# The ways to move the wheel's cursor and take the item (move, confirm): the wheel shows while L is held. Tried in this order until one
# changes the flag; the first of them that did is used from then on.
WHEEL_VIA = {'stick-a': ('stick', 'a'), 'dpad-a': ('dpad', 'a'), 'stick-release': ('stick', 'release'),
             'dpad-release': ('dpad', 'release'), 'r': ('r', 'tap')}
WHEEL_STEP_SECONDS, USE_STEP_SECONDS = 40.0, 60.0   # (what the pilot allows these steps)
WHEEL_OPEN_MS = 900     # the wheel is drawn this long after L goes down (the game runs at 30 frames a second, a loaded PC slower)


def murmur3_32(text, seed=0):
    """MurmurHash3 x86 32-bit: the game's hash of a name (an enum's value is reported as its hash)"""
    m, data = 0xFFFFFFFF, text.encode()
    h, n = seed, len(data)
    for i in range(0, n - n % 4, 4):
        k = int.from_bytes(data[i:i + 4], 'little')
        k = (k * 0xCC9E2D51) & m
        k = ((k << 15) | (k >> 17)) & m
        h ^= (k * 0x1B873593) & m
        h = ((h << 13) | (h >> 19)) & m
        h = (h * 5 + 0xE6546B64) & m
    tail, k = data[n - n % 4:], 0
    if tail:
        for j in range(len(tail) - 1, -1, -1):
            k ^= tail[j] << (8 * j)
        k = (k * 0xCC9E2D51) & m
        k = ((k << 15) | (k >> 17)) & m
        h ^= (k * 0x1B873593) & m
    h ^= n
    h ^= h >> 16
    h = (h * 0x85EBCA6B) & m
    h ^= h >> 13
    h = (h * 0xC2B2AE35) & m
    return h ^ (h >> 16)


class ItemTableError(ValueError):
    """The item table is not named, not readable or not what SCHEMA says (a ValueError: an item step answers it as a bad step, with this text)"""


class ItemTable:
    """The item names and facts of a table file (see SCHEMA), checked on loading: `enum`, `aliases`, `aiming`, `stock`, `wheel_order`,
    `choice_flags` (the adult's flag, the child's) and `by_hash` (the enum's names by their hash)."""

    def __init__(self, data, source):
        def refuse(why):
            raise ItemTableError(f'the item table {source} {why}; it must be {SCHEMA}')

        def names(key):
            value = data[key]
            if not isinstance(value, list) or not all(isinstance(n, str) and n for n in value):
                refuse(f'has "{key}" that is not a list of names')
            if len(set(value)) != len(value):
                refuse(f'names an item twice in "{key}"')
            return tuple(value)

        def strings(key):
            value = data[key]
            if not isinstance(value, dict) or not all(isinstance(k, str) and k and isinstance(v, str) and v for k, v in value.items()):
                refuse(f'has "{key}" that is not an object of non-empty strings')
            return value

        if not isinstance(data, dict) or set(data) != set(KEYS):
            refuse('is not an object with exactly the keys ' + ', '.join(KEYS))
        self.enum = names('enum')
        if not self.enum:
            refuse('has an empty "enum"')
        self.aiming, self.wheel_order = names('aiming'), names('wheel_order')
        self.aliases, self.stock, flags = strings('aliases'), strings('stock'), strings('choice_flags')
        if set(flags) != {'adult', 'child'} or flags['adult'] == flags['child']:
            refuse('has "choice_flags" that is not two different flags, "adult" and "child"')
        self.choice_flags = (flags['adult'], flags['child'])
        self.names = set(self.enum)
        for key, used in (('aiming', self.aiming), ('wheel_order', self.wheel_order), ('aliases', self.aliases.values()), ('stock', self.stock)):
            unknown = [n for n in used if n not in self.names]
            if unknown:
                refuse(f'has {unknown[0]!r} in "{key}" that is not in "enum"')
        for word in self.aliases:
            if word != word.strip().lower().replace('_', '-'):
                refuse(f'has the alias {word!r}: a plain word is lower case with - between words')
        self.by_hash = {}
        for name in self.enum:
            other = self.by_hash.setdefault(murmur3_32(name), name)
            if other != name:
                refuse(f'has two names in "enum" that hash alike: {other!r} and {name!r}')
        self.place = {name: i for i, name in enumerate(self.wheel_order)}

    def item_name(self, word):
        """The enum name for a step's word (a plain name or the enum's own), or None"""
        w = word.strip().lower().replace('_', '-')
        if w in self.aliases:
            return self.aliases[w]
        for name in self.enum:
            if name.lower() == w.replace('-', ''):
                return name
        return None

    def enum_value(self, value):
        """The enum name a sample's value stands for: the flag's value as the bridge sends an enum (its hash: '#' and eight hex digits, a
        number, or the name itself), or None"""
        if value is None:
            return None
        if isinstance(value, str):
            text = value[1:] if value.startswith('#') else value
            if text in self.names:
                return text
            try:
                return self.by_hash.get(int(text, 16)) or ('?' + value)
            except ValueError:
                return '?' + value
        if isinstance(value, int) and not isinstance(value, bool):
            return self.by_hash.get(value & 0xFFFFFFFF) or ('?' + str(value))
        return '?' + str(value)

    def first_direction(self, now, item):
        """'left' when `item` lies before the current choice in the wheel's order, else 'right'. The wheel lists the items by type in the
        game's own order and the cursor stops at the strip's ends: only the first push uses this order, toward where the wanted item lies
        in it (the turn at an end still finds it when the guess is wrong). Items not listed count as last."""
        last = len(self.place)
        return 'left' if self.place.get(item, last) < self.place.get(now, last) else 'right'


def load_table(path):
    """The ItemTable of a JSON file; ItemTableError (naming the file and the schema) when it cannot be read or is not what SCHEMA says"""
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except OSError as e:
        raise ItemTableError(f'the item table {path} cannot be read ({e.strerror or e}); it must be {SCHEMA}') from None
    except ValueError as e:   # (not UTF-8, or not JSON)
        raise ItemTableError(f'the item table {path} is not JSON ({e}); it must be {SCHEMA}') from None
    return ItemTable(data, path)


_table_path = None   # (the file use_table named)
_loaded = None       # (the file's identity, the table read from it)


def use_table(path):
    """Name the item table's file from code; it wins over $HSAP_ITEMS. None: the setting again."""
    global _table_path
    _table_path = os.fspath(path) if path else None


def table():
    """The item table of the named file (read again when the file changes); ItemTableError when none is named or it cannot be used"""
    global _loaded
    path = _table_path or os.environ.get(ITEMS_SETTING)
    if not path:
        raise ItemTableError(f'no item table: set ${ITEMS_SETTING} to the JSON file with the game\'s item names; it must be {SCHEMA}')
    try:
        st = os.stat(path)
        ident = (path, st.st_mtime_ns, st.st_size)
    except OSError:
        ident = None   # (load_table says what is wrong)
    if ident is None or _loaded is None or _loaded[0] != ident:
        _loaded = (ident, load_table(path))
    return _loaded[1]


def bind(namespace):
    """Take hsap.py's own helpers (its module namespace, once they are defined) for the steps to use."""
    globals().update({name: namespace[name] for name in HELPERS})


def item_name(word):
    """The enum name for a step's word (a plain name or the enum's own), or None"""
    return table().item_name(word)


def enum_value(value):
    """The enum name a sample's value stands for (see ItemTable.enum_value), or None"""
    return table().enum_value(value)


def first_direction(now, item):
    """'left' when `item` lies before the current choice in the wheel's order, else 'right'"""
    return table().first_direction(now, item)


def wheel_script(via, direction, delay_ms=WHEEL_OPEN_MS):
    """(the `sequence` line in the bridge's hos units, seconds it lasts) that opens the wheel, moves the cursor one item to `direction`
    ('right' or 'left') and takes the item, the way `via` says"""
    move, confirm = WHEEL_VIA[via]
    d = delay_ms / 1000.0
    if move == 'r':   # the quick select: R (L) pressed once is one item on, without the wheel
        return ('0:' + ('R' if direction == 'right' else 'L') + '/80', 0.2)
    key = ('LRIGHT' if direction == 'right' else 'LLEFT') if move == 'stick' else ('RIGHT' if direction == 'right' else 'LEFT')
    if confirm == 'a':
        press = f'{d + 0.6:g}'
        hold = int((d + 0.6 + 0.45) * 1000)
        return (f'0:L/{hold},{d:g}:{key}/150,{press}:A/150', d + 1.2)
    hold = int((d + 0.6) * 1000)
    return (f'0:L/{hold},{d:g}:{key}/150', d + 0.9)


class ItemSteps:
    wheel_via = None       # the way of WHEEL_VIA that last changed the choice (kept for the run)

    # ---- what the game says about the choice and the counts
    def item_choice(self):
        """(enum name or None, the raw value): the item button's choice from the watched flag of Link's age"""
        st = self.g.st or {}
        flags = st.get('flags') or {}
        flag_names = table().choice_flags
        names = flag_names[::-1] if st.get('child') else flag_names      # (child 1: the child's flag first)
        for name in names:
            if flags.get(name) is not None:
                return enum_value(flags[name]), flags[name]
        return None, None

    def item_count(self, item):
        flag = table().stock.get(item)
        return None if flag is None else ((self.g.st or {}).get('flags') or {}).get(flag)

    def choice_watched(self):
        flags = (self.g.st or {}).get('flags') or {}
        return any(n in flags for n in table().choice_flags)

    # ---- the wheel
    def wheel_once(self, via, direction):
        """One try: the inputs of `via`, then the choice as the game says it afterwards"""
        script, seconds = wheel_script(via, direction)
        self.wait_input(self.g.send(script))
        self.wait(seconds if via == 'r' else 0.8)
        self.fresh()
        return self.item_choice()[0]

    def select_item(self, item, tries=8, via=None):
        """(result, detail, info): the item button's choice made `item`. already / selected / not-found / unverified / none"""
        now, raw = self.item_choice()
        info = {'item': item}
        if now == item:
            return 'already', f'{item} is the item button\'s choice already', info
        ladder = [via] if via else ([self.wheel_via] if self.wheel_via else list(WHEEL_VIA))
        if now is None:   # (the flag is not watched: one try with the first way, nothing to read)
            self.wheel_once(ladder[0], 'right')
            return 'unverified', f'the choice flag is not watched (watch {" ".join(table().choice_flags)}): one try, {ladder[0]}', info
        seen, direction, flips, idle, way, moved = [now], first_direction(now, item), 0, 0, 0, False
        used = 0
        while used < tries and self.g.alive():
            used += 1
            current = ladder[way]
            after = self.wheel_once(current, direction)
            if after is None or after == now:
                # no change: a way that has moved the cursor before has reached the strip's end (turn round once), one that has not
                # did nothing (the next way of the ladder)
                if moved or via or len(ladder) == 1 and self.wheel_via:
                    idle += 1
                    if flips == 0:
                        direction, flips, idle = ('left' if direction == 'right' else 'right'), 1, 0
                    elif idle >= 1:
                        break
                elif way + 1 < len(ladder):
                    way += 1
                else:
                    break
                continue
            moved, idle = True, 0
            if not via:
                self.wheel_via = current
            now = after
            if now == item:
                info.update(via=current, tries=used, seen=seen + [now])
                return 'selected', f'{item} chosen with {current} after {used} tr' + ('y' if used == 1 else 'ies'), info
            if now in seen and flips == 0:   # (round the strip in one direction: the item is not in it; after a turn, seen items are expected)
                seen.append(now)
                break
            seen.append(now)
        info.update(via=self.wheel_via if not via else via, tries=used, seen=seen)
        if moved:
            return 'not-found', f'{item} is not in the wheel (the choices seen: {", ".join(seen)}; {used} tries)', info
        return 'none', f'no way of the ladder changed the choice (still {seen[0]}; {used} tries)', info

    def step_wheel_select(self, args):
        usage = 'wheel-select <item> [via <way>] [tries <n>]'
        pos, kv, _ = split_opts(args, keys=('via', 'tries'))
        if len(pos) != 1:
            raise ValueError(usage)
        item = item_name(pos[0])
        if item is None:
            raise ValueError(usage + '; items: ' + ' '.join(sorted(table().aliases)))
        via = kv.get('via')
        if via is not None and via not in WHEEL_VIA:
            raise ValueError(usage + '; ways: ' + ' '.join(WHEEL_VIA))
        tries = int(seconds_of(kv, 8.0, 'tries'))
        if not 1 <= tries <= 20:
            raise ValueError(usage + '; tries 1 to 20')
        restarts = self.g.restarts
        refusal = self._refuse(self.fresh())
        if refusal:
            return refusal
        result, said, info = self.select_item(item, tries, via)
        gone = self._gone(restarts)
        if gone:
            return gone
        ch = {'item': info}
        return self.outcome(result, ch, said)

    # ---- use
    def step_use_item(self, args):
        usage = 'use-item <item> [hold <ms>] [fire release|y|a|zr|none] [lock]'
        pos, kv, fl = split_opts(args, flags=('lock',), keys=('hold', 'fire'))
        if len(pos) != 1:
            raise ValueError(usage)
        item = item_name(pos[0])
        if item is None:
            raise ValueError(usage + '; items: ' + ' '.join(sorted(table().aliases)))
        fire = (kv.get('fire') or 'release').lower()
        if fire not in ('release', 'none', 'y', 'a', 'zr'):
            raise ValueError(usage)
        hold = int(seconds_of(kv, 1000.0 if item in table().aiming else 150.0, 'hold'))
        if not 50 <= hold <= 3000:
            raise ValueError(usage + '; hold 50 to 3000')
        restarts = self.g.restarts
        refusal = self._refuse(self.fresh())
        if refusal:
            return refusal
        result, said, info = self.select_item(item)
        if result not in ('already', 'selected', 'unverified'):
            gone = self._gone(restarts)
            return gone if gone else self.outcome('no-item', {'item': info}, said)
        self.fresh()
        before, mark = self.snap(), self.g.n_states
        count0 = self.item_count(item)
        tail = {'y': 'Y', 'a': 'A', 'zr': 'ZR'}.get(fire)
        parts = []
        if 'lock' in fl:
            parts.append(f'0:ZL/{400 + hold + 700}')
            parts.append(f'0.4:ZR/{hold}')
            if tail:
                parts.append(f'{0.4 + max(0.1, (hold - 300) / 1000.0):g}:{tail}/120')
        else:
            parts.append(f'0:ZR/{hold}')
            if tail:
                parts.append(f'{max(0.1, (hold - 300) / 1000.0):g}:{tail}/120')
        self.wait_input(self.g.send(','.join(parts)))
        self._wait_game(1.2)
        if text_open(self.g.st or {}):
            self.advance_text(time.time() + 10.0)
        after = self.snap()
        turns = [abs(wrap(s[k] - before[k])) for s in self.g.window(mark) + [self.g.st or {}] for k in ('camera', 'facing')
                 if s.get(k) is not None and before.get(k) is not None]
        aimed = max(turns, default=0.0)
        ch = self.changes(before, after, mark)
        count1 = self.item_count(item)
        spent = None not in (count0, count1) and count1 < count0
        ch['aimed'] = round(aimed, 1)
        ch['item'] = {**info, 'count': [count0, count1]}
        used = spent or any(k in ch for k in ('rupees', 'life', 'prompt', 'hashes')) and not (
            set(ch['flags']) <= set(table().choice_flags) if 'flags' in ch else False) and aimed < 4.0 and count0 is None
        gone = self._gone(restarts)
        if gone:
            return gone
        word = 'used' if spent or used else 'aimed' if aimed >= 4.0 else 'none'
        return self.outcome(word, ch, f'{item}: ZR held {hold} ms' + (f', then {fire}' if tail else '') + (' with ZL held' if 'lock' in fl else ''))
