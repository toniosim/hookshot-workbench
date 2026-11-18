#!/usr/bin/env python3
"""Game-free checks of hsap_items.py (the item box's steps of hsap.Executor: wheel-select and use-item) on test_hsap.py's simulated
protocol-1 bridge. ItemBridge adds an invented item box: a strip of items the wheel shows while L is held, a cursor the stick, the
D-pad or R moves, a choice flag (an enum, reported as its hash), counts, and an aim; which control moves the cursor, what takes the
item, and what fires the aimed item are knobs, because the game's own answer is found by the ladder the steps carry. Every name and
number here is an invented fixture, the item table too: a JSON file the checks write into a temporary folder and name by $HSAP_ITEMS,
as a real one is named. No game, no GPU, no network, no wall-clock sleeps.

    python3 -I -B test_hsap_items.py
"""
import contextlib
import itertools
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_hsap as T  # noqa: E402  (its main() runs only as a script)
import hsap  # noqa: E402
import hsap_items  # noqa: E402

check = T.check
INPUTS = ('press', 'stick', 'sequence')
CHOICE = 'Slot.Choice.Child'     # the fake sample's age is the child's
ORBS, SEEDS = 'Pouch.Orb.Count', 'Pouch.Seed.Count'
ENUM = ('Empty', 'Twig', 'Acorn', 'Orb', 'Disc', 'Dart', 'Rope', 'Cable', 'Mallet', 'Prism', 'Mite', 'Flare', 'Gale', 'Ward', 'Sprout',
        'JarA', 'JarB', 'JarC', 'JarD', 'JarE', 'Bolt', 'Parcel', 'Hen', 'Token')
AIMING = ('Dart', 'Bolt', 'Rope', 'Cable', 'Disc')
ORDER = ('Twig', 'Dart', 'Bolt', 'Disc', 'Acorn', 'Orb', 'Mite', 'Rope', 'Cable', 'Mallet', 'Prism', 'Flare', 'Gale', 'Ward', 'Sprout',
         'JarA', 'JarB', 'JarC', 'JarD', 'JarE', 'Parcel', 'Hen', 'Token')   # (the order the wheels below list their items in)
TABLE = {'enum': list(ENUM),
         'aliases': {'orb': 'Orb', 'orbs': 'Orb', 'mite': 'Mite', 'dart': 'Dart', 'darts': 'Dart', 'bolt': 'Bolt', 'disc': 'Disc',
                     'rope': 'Rope', 'cable': 'Cable', 'mallet': 'Mallet', 'prism': 'Prism', 'flare-gun': 'Flare', 'gale': 'Gale',
                     'ward': 'Ward', 'wild-acorn': 'Acorn', 'wild-acorns': 'Acorn', 'sprout': 'Sprout', 'sprouts': 'Sprout'},
         'aiming': list(AIMING),
         'stock': {'Orb': ORBS, 'Mite': 'Pouch.Mite.Count', 'Dart': SEEDS, 'Bolt': 'Pouch.Bolt.Count', 'Acorn': 'Pouch.Acorn.Count',
                   'Twig': 'Pouch.Twig.Count', 'Sprout': 'Pouch.Sprout.Count'},
         'choice_flags': {'adult': 'Slot.Choice.Adult', 'child': CHOICE},
         'wheel_order': list(ORDER)}
STRIP = ('Acorn', 'Orb', 'Dart', 'Flare')   # (the wheel of most checks: the table's order for them is this one, set by `world`)
ADULT = ('Acorn', 'Orb', 'Rope', 'Flare', 'Gale', 'JarA', 'Parcel', 'Hen')
CHILD = ('Twig', 'Dart', 'Acorn', 'JarA', 'Token')
WORK = None        # (the temporary folder of the table files, made by main())
FILES = itertools.count()


def hashed(item):
    return '#%08x' % hsap_items.murmur3_32(item)


def table_file(order=STRIP, **changes):
    """The path of a new table file: TABLE with `order` as its wheel_order and `changes` laid over it (a changed value of None leaves the key out)"""
    data = {**TABLE, 'wheel_order': list(order), **changes}
    path = WORK / f'items-{next(FILES)}.json'
    path.write_text(json.dumps({k: v for k, v in data.items() if v is not None}))
    return path


@contextlib.contextmanager
def using(path):
    """$HSAP_ITEMS names `path` (nothing else names a table), as in a real run"""
    hsap_items.use_table(None)
    with mock.patch.dict(os.environ, {hsap_items.ITEMS_SETTING: str(path)}):
        yield path


@contextlib.contextmanager
def no_setting():
    hsap_items.use_table(None)
    with mock.patch.dict(os.environ):
        os.environ.pop(hsap_items.ITEMS_SETTING, None)
        yield


class ItemBridge(T.WorldBridge):
    """WorldBridge plus the item box. L held shows the wheel (its cursor starts on the choice); `move` is what moves the cursor
    (stick: the stick's edge; dpad: the D-pad's Left and Right; r: R or L pressed once, no wheel), `confirm` what takes the item under
    it (a: A while the wheel shows; release: L let go; tap: the move itself). ZR with the orb chosen spends an orb; with an aiming
    item held 12 frames it aims (the camera turns); `fire` says what spends a seed: release (ZR let go), y or a (pressed while aiming)."""
    def __init__(self, *args, strip=STRIP, choice='Orb', move='stick', confirm='a', fire='release', orbs=10, seeds=30, **kwargs):
        super().__init__(*args, **kwargs)
        self.strip, self.move, self.confirm, self.fire = list(strip), move, confirm, fire
        self.choice, self.w_open, self.cursor, self.taken = choice, False, 0, False
        self.lx_prev, self.zr_since, self.aimed, self.fired = 0.0, None, False, False
        self.flags[ORBS], self.flags[SEEDS] = orbs, seeds
        self.set_choice(choice)
        self.wheel_log = []

    def set_choice(self, item):
        self.choice = item
        self.flags[CHOICE] = hashed(item)

    def shift(self, step):
        self.cursor = max(0, min(len(self.strip) - 1, self.cursor + step))

    def pressed(self, b):
        if b == 'L':
            self.w_open, self.taken = True, False
            self.cursor = self.strip.index(self.choice) if self.choice in self.strip else 0
            self.wheel_log.append(('open', self.frame + 1))
            return
        if self.w_open:
            if b in ('RIGHT', 'LEFT') and self.move == 'dpad':
                self.shift(1 if b == 'RIGHT' else -1)
            elif b == 'A' and self.confirm == 'a' and not self.taken:
                self.set_choice(self.strip[self.cursor])
                self.taken, self.w_open = True, False
                self.wheel_log.append(('take', self.strip[self.cursor]))
            elif b == 'A':   # (A is not the way that takes it here: it backs out)
                self.taken = True
            return
        if b == 'R' and self.move == 'r' and self.choice in self.strip:
            self.cursor = self.strip.index(self.choice)
            self.shift(1)
            self.set_choice(self.strip[self.cursor])
            return
        if b == 'ZR':
            self.zr_since, self.aimed, self.fired = self.frame + 1, False, False
            if self.choice == 'Orb':
                self.flags[ORBS] -= 1
            return
        if b in ('Y', 'A') and self.aimed and not self.fired and self.fire == b.lower() and self.choice in AIMING:
            self.fired = True
            self.flags[SEEDS] -= 1
            return
        super().pressed(b)

    def tick(self):
        nxt = self.frame + 1
        active = [s for s in self.inputs if s['start'] <= nxt < s['end']]
        held = {b for s in active for b in s['buttons']}
        lx = sum(s['axes'].get('lx', 0) for s in active)
        if self.w_open and self.move == 'stick' and abs(lx) > 0.5 >= abs(self.lx_prev):
            self.shift(1 if lx > 0 else -1)
        self.lx_prev = lx
        if self.w_open and 'L' not in held and nxt > 1:
            self.w_open = False
            if self.confirm == 'release' and not self.taken:
                self.set_choice(self.strip[self.cursor])
                self.wheel_log.append(('release', self.strip[self.cursor]))
        if self.zr_since is not None:
            if 'ZR' in held:
                if self.choice in AIMING and nxt - self.zr_since >= 12:
                    self.aimed = True
                    self.cam = hsap.wrap(self.cam + 0.8)
            else:
                if self.aimed and not self.fired and self.fire == 'release':
                    self.fired = True
                    self.flags[SEEDS] -= 1
                self.zr_since = None
        super().tick()


class ItemSimulation(T.WorldSimulation):
    def launch(self, cmd, **kwargs):
        args = dict(arg.split('=', 1) for arg in cmd[4:] if '=' in arg)
        self.bridge = ItemBridge(Path(args['HOS_CONTROL']), Path(args['HOS_INPUT_LIVE']), self.copy / 'runs/test',
                                 self.clock, **self.options)
        self.clock.bridge = self.bridge
        return T.FakeRunner()

    def steps(self):
        return [e for e in self.events() if e['ev'] == 'step' and e['src'].split()[0] not in ('end', 'wait')]


@contextlib.contextmanager
def world(lines, watched=True, order=STRIP, **options):
    """Run the step lines on an ItemBridge world whose table lists the items in `order`: (simulation, the step events). The choice and
    the counts are watched unless not `watched`."""
    options.setdefault('boot_events', 0)
    options.setdefault('follow', False)
    choice = options.get('choice', 'Orb')
    options['flags'] = {CHOICE: hashed(choice), ORBS: options.get('orbs', 10), SEEDS: options.get('seeds', 30)} if watched else {}
    with using(table_file(order)), ItemSimulation(**options) as sim:
        sim.executor(list(lines) + ['end']).run()
        yield sim, sim.steps()


def inputs(sim):
    return [r for r in sim.bridge.requests if r['cmd'] in INPUTS]


def scripts(sim):
    return [r['script'] for r in sim.bridge.requests if r['cmd'] == 'sequence']


def refusal(call, *hints):
    """The text of the ItemTableError `call` raises (None when it raises none), and whether it holds every hint"""
    try:
        call()
    except hsap_items.ItemTableError as e:
        return str(e), all(h in str(e) for h in hints)
    return None, False


def pure_checks():
    # the published values of MurmurHash3 x86 32 (seed 0, and abc with the seed of the reference test)
    check(hsap_items.murmur3_32('') == 0 and hsap_items.murmur3_32('a') == 0x3C2569B2 and hsap_items.murmur3_32('abc') == 0xB3DD93FA and
          hsap_items.murmur3_32('Hello, world!') == 0xC0363E43 and
          hsap_items.murmur3_32('The quick brown fox jumps over the lazy dog') == 0x2E4FF723 and
          hsap_items.murmur3_32('abc', 0x9747B28C) == 0xC84A62DD, 'murmur3_32 gives the published values of MurmurHash3 x86 32')
    with using(table_file()):
        t = hsap_items.table()
        check(t.enum == ENUM and len(t.by_hash) == len(ENUM) and t.choice_flags == ('Slot.Choice.Adult', CHOICE) and set(t.aiming) == set(AIMING),
              'the table file is read as written: the enum, a hash for every name, the two choice flags (adult first), the aiming items')
        check([hsap_items.item_name(x) for x in ('orb', 'Orb', 'Dart', 'dart', 'flare-gun', 'Flare', 'wild_acorn', 'hen', 'jar-a', 'nothing')] ==
              ['Orb', 'Orb', 'Dart', 'Dart', 'Flare', 'Flare', 'Acorn', 'Hen', 'JarA', None],
              'item names: a plain word of the table, the enum\'s own in any case, with - or _ or nothing between the words')
        check([hsap_items.enum_value(v) for v in (hashed('Rope'), hsap_items.murmur3_32('Bolt'), 'Orb', '#12345678', None)] ==
              ['Rope', 'Bolt', 'Orb', '?#12345678', None], 'an enum value as a hash, a number or a name; an unknown one stays visible')
        check(hsap_items.first_direction('Orb', 'Acorn') == 'left' and hsap_items.first_direction('Acorn', 'Orb') == 'right' and
              hsap_items.first_direction('Dart', 'Orb') == 'left' and hsap_items.first_direction('Orb', 'Empty') == 'right' and
              hsap_items.first_direction('Empty', 'Acorn') == 'left',
              'the first push goes toward where the item lies in the table\'s wheel order; one not listed counts as last')
    check(hsap_items.wheel_script('stick-a', 'right') == ('0:L/1950,0.9:LRIGHT/150,1.5:A/150', 2.1) and
          hsap_items.wheel_script('dpad-release', 'left')[0] == '0:L/1500,0.9:LEFT/150' and
          hsap_items.wheel_script('r', 'right')[0] == '0:R/80' and hsap_items.wheel_script('r', 'left')[0] == '0:L/80',
          'the ways\' sequences: L held through the move and the A, or released; R or L pressed once')
    check(set(hsap_items.ITEM_VERBS) <= set(hsap.INTERACT_VERBS), 'the verbs are in hsap\'s dispatch table')


def table_checks():
    """Where the table comes from: a setting with no default, a file that must be what the schema says, and each refusal says so."""
    with no_setting():
        text, ok = refusal(hsap_items.table, 'HSAP_ITEMS', '"enum"', '"wheel_order"')
        check(ok, f'no setting: the refusal names $HSAP_ITEMS and the schema ({text})')
        with mock.patch.dict(os.environ, {hsap_items.ITEMS_SETTING: ''}):
            check(refusal(hsap_items.table, 'HSAP_ITEMS')[1], 'an empty setting is no setting')
        # the steps: a bad step each, with that text, and nothing sent to the game
        with ItemSimulation(boot_events=0, follow=False, flags={CHOICE: hashed('Orb')}) as sim:
            sim.executor(['wheel-select orb', 'use-item orb', 'wait 0.1', 'end']).run()
            bad = [e for e in sim.events() if e['ev'] == 'bad']
            check([e['src'] for e in bad] == ['wheel-select orb', 'use-item orb'] and all('HSAP_ITEMS' in e['why'] and '"enum"' in e['why'] for e in bad),
                  'without a table both item steps are bad steps whose text names the setting and the schema')
            check(not inputs(sim), 'and neither sent an input')
    # use_table names a file from code and wins over the setting; None gives the setting back
    first, second = table_file(), table_file(order=('Orb', 'Acorn'))
    with using(first):
        hsap_items.use_table(second)
        check(hsap_items.table().wheel_order == ('Orb', 'Acorn'), 'use_table(path) names the file, over $HSAP_ITEMS')
        hsap_items.use_table(None)
        check(hsap_items.table().wheel_order == STRIP, 'use_table(None): the setting again')
    # a file that changed is read again
    path = table_file()
    with using(path):
        check(hsap_items.table().wheel_order == STRIP, 'a table file is read')
        path.write_text(json.dumps({**TABLE, 'wheel_order': ['Orb', 'Dart', 'Acorn']}))
        check(hsap_items.table().wheel_order == ('Orb', 'Dart', 'Acorn'), 'and read again when the file changed')
    # every refusal names the file and the schema and says what is wrong with it
    cases = [('is not JSON', 'this is not json', 'is not JSON'),
             ('is not an object', json.dumps(['enum']), 'exactly the keys'),
             ('is missing a key', {k: v for k, v in TABLE.items() if k != 'stock'}, 'exactly the keys'),
             ('has a key too many', {**TABLE, 'more': []}, 'exactly the keys'),
             ('has an enum that is not a list', {**TABLE, 'enum': 'Orb'}, '"enum" that is not a list of names'),
             ('has an empty enum', {**TABLE, 'enum': [], 'aliases': {}, 'aiming': [], 'stock': {}, 'wheel_order': []}, 'empty "enum"'),
             ('has an item twice', {**TABLE, 'enum': list(ENUM) + ['Orb']}, 'names an item twice in "enum"'),
             ('has a name that is not text', {**TABLE, 'aiming': [3]}, '"aiming" that is not a list of names'),
             ('has an alias of no item', {**TABLE, 'aliases': {**TABLE['aliases'], 'axe': 'Axe'}}, "'Axe' in \"aliases\""),
             ('has an alias that is not a plain word', {**TABLE, 'aliases': {'Flare Gun': 'Flare'}}, "alias 'Flare Gun'"),
             ('has an alias with _', {**TABLE, 'aliases': {'flare_gun': 'Flare'}}, "alias 'flare_gun'"),
             ('has aliases that are not text', {**TABLE, 'aliases': {'orb': 3}}, '"aliases" that is not an object of non-empty strings'),
             ('has an aiming item of no item', {**TABLE, 'aiming': ['Axe']}, "'Axe' in \"aiming\""),
             ('has a stock of no item', {**TABLE, 'stock': {'Axe': 'Pouch.Axe.Count'}}, "'Axe' in \"stock\""),
             ('has an empty count flag', {**TABLE, 'stock': {'Orb': ''}}, '"stock" that is not an object of non-empty strings'),
             ('has a wheel order of no item', {**TABLE, 'wheel_order': ['Orb', 'Axe']}, "'Axe' in \"wheel_order\""),
             ('lists a wheel item twice', {**TABLE, 'wheel_order': ['Orb', 'Orb']}, 'names an item twice in "wheel_order"'),
             ('has one choice flag', {**TABLE, 'choice_flags': {'adult': 'Slot.Choice.Adult'}}, '"adult" and "child"'),
             ('has the same flag for both ages', {**TABLE, 'choice_flags': {'adult': CHOICE, 'child': CHOICE}}, '"adult" and "child"')]
    for what, content, hint in cases:
        path = WORK / f'bad-{next(FILES)}.json'
        path.write_text(content if isinstance(content, str) else json.dumps(content))
        with using(path):
            text, ok = refusal(hsap_items.table, str(path), 'a JSON object', hint)
            check(ok, f'a table that {what} is refused, naming the file, the schema and the fault ({text})')
    with using(WORK / 'nothing-here.json'):
        text, ok = refusal(hsap_items.table, str(WORK / 'nothing-here.json'), 'cannot be read', '"enum"')
        check(ok, f'a file that is not there is refused, naming it and the schema ({text})')
    path = WORK / f'bad-{next(FILES)}.json'
    path.write_bytes(b'\xff\xfe{')
    with using(path):
        check(refusal(hsap_items.table, str(path), 'is not JSON', '"enum"')[1], 'a file that is not text is refused the same way')
    # two names that hash alike cannot both be read back from a hash
    with using(table_file()), mock.patch.object(hsap_items, 'murmur3_32', lambda text, seed=0: 7):
        text, ok = refusal(hsap_items.table, 'hash alike', "'Empty' and 'Twig'")
        check(ok, f'two enum names with one hash are refused ({text})')


def wheel_checks():
    # the first way of the ladder works: one try, L held through the move and the A (the wheel shows only while L is down)
    with world(['wheel-select dart'], move='stick', confirm='a') as (sim, steps):
        a = steps[0]
        sc = scripts(sim)
        check(a['result'] == 'selected' and a['changes']['item']['via'] == 'stick-a' and a['changes']['item']['tries'] == 1,
              f"wheel-select: the stick moves the cursor, A takes the item: selected in one try ({a['detail']})")
        check(len(sc) == 1 and sc[0].startswith('0:L/') and 'LRIGHT/150' in sc[0] and ',1.5:A/150' in sc[0],
              f'one sequence: L down at once, the stick at 0.9 s, A at 1.5 s, L let go after it ({sc})')
        check(sim.bridge.choice == 'Dart' and a['changes']['item']['seen'] == ['Orb', 'Dart'], 'the game\'s choice is the item; the items seen are named')
        check(hsap.Executor.wheel_via is None and sim.executors[-1].wheel_via == 'stick-a', 'the way that worked is kept in the executor, not in the class')

    # the ladder finds the way: the D-pad moves, L let go takes. Three ways do nothing first; then the way is kept
    with world(['wheel-select dart', 'wheel-select flare-gun'], move='dpad', confirm='release') as (sim, (a, b)):
        sc = scripts(sim)
        check(a['result'] == 'selected' and a['changes']['item']['via'] == 'dpad-release' and a['changes']['item']['tries'] == 4,
              f"the ladder: stick+A, dpad+A, stick+release do nothing, dpad+release works ({a['detail']})")
        check(len(sc) == 5 and sc[3] == hsap_items.wheel_script('dpad-release', 'right')[0] and sc[4] == sc[3],
              'the next wheel-select goes straight to the way that worked (one sequence, no ladder)')
        check(b['result'] == 'selected' and b['changes']['item']['tries'] == 1 and sim.bridge.choice == 'Flare', 'and it chooses the next item')

    # R pressed once moves the choice without a wheel
    with world(['wheel-select dart'], move='r', confirm='tap') as (sim, (a,)):
        check(a['result'] == 'selected' and a['changes']['item']['via'] == 'r' and sim.bridge.choice == 'Dart',
              f"the quick select: R once chooses the next item ({a['detail']}; {scripts(sim)})")

    # via forces one way; a way that does nothing is none
    with world(['wheel-select dart via dpad-a'], move='stick', confirm='a') as (sim, (a,)):
        check(a['result'] == 'none' and len(scripts(sim)) <= 2 and sim.bridge.choice == 'Orb',
              f"via dpad-a with the stick the game's way: nothing changes, none and the ladder is not walked ({a['result']}, {len(scripts(sim))} sequences)")

    # already chosen: nothing is sent
    with world(['wheel-select orb'], choice='Orb') as (sim, (a,)):
        check(a['result'] == 'already' and not inputs(sim), 'the item is the choice already: nothing sent')

    # the item is not in the wheel: the cursor goes to the end, turns round, meets what it saw
    with world(['wheel-select rope'], move='stick', confirm='a') as (sim, (a,)):
        check(a['result'] == 'not-found' and 'Orb' in a['changes']['item']['seen'] and a['changes']['item']['tries'] <= 8,
              f"an item the wheel does not hold: not-found with what was seen ({a['detail']})")

    # a wheel of eight items in the table's order; the first push goes the way the item lies in that order
    with world(['wheel-select wild-acorn', 'wheel-select hen', 'wheel-select orb'], order=ORDER, strip=ADULT, choice='Orb', move='stick', confirm='a') as (sim, (a, b, c)):
        check(a['result'] == 'selected' and a['changes']['item']['tries'] == 1 and sim.bridge.wheel_log[0][0] == 'open',
              f"the acorn lies before the orb: one push to the left, one try ({a['result']}, {a['changes']['item']['tries']} tries; {a['detail']})")
        check(b['result'] == 'selected' and b['changes']['item']['tries'] == 7, f"from the first item to the last: seven pushes to the right ({b['result']}, {b['changes']['item']['tries']} tries)")
        check(c['result'] == 'selected' and c['changes']['item']['tries'] <= 8 and sim.bridge.choice == 'Orb',
              f"and back to the orb from the last item: to the left, not the way it was told first ({c['result']}, {c['changes']['item']['tries']} tries)")
    # an item the wheel does not hold, placed before its first: the cursor goes left to the end, turns round and walks the whole strip back; meeting an item
    # it saw on the way back is no wrap (the wheel has none: it stops at its ends)
    with world(['wheel-select twig tries 20'], order=ORDER, strip=ADULT, choice='Orb', move='stick', confirm='a') as (sim, (a,)):
        seen = a['changes']['item']['seen']
        check(a['result'] == 'not-found' and 'Hen' in seen and a['changes']['item']['tries'] >= 10,
              f"not-found only after both ends were met ({a['result']}; {a['changes']['item']['tries']} tries; seen {seen})")
    # a wheel of five: the dart comes before the acorn here
    with world(['wheel-select wild-acorn', 'wheel-select dart', 'wheel-select token'], order=ORDER, strip=CHILD, choice='Dart', move='stick', confirm='a') as (sim, (a, b, c)):
        check(a['result'] == 'selected' and a['changes']['item']['tries'] == 1, f"the acorn after the dart: one push to the right ({a['result']}, {a['changes']['item']['tries']} tries; {a['detail']})")
        check(b['result'] == 'selected' and b['changes']['item']['tries'] == 1, f"and back: one push to the left ({b['result']}, {b['changes']['item']['tries']} tries)")
        check(c['result'] == 'selected' and c['changes']['item']['tries'] == 3, f"the last item of the strip: three pushes to the right ({c['result']}, {c['changes']['item']['tries']} tries)")

    # the choice is not watched: one try, unverified
    with world(['wheel-select dart'], watched=False, move='stick', confirm='a') as (sim, (a,)):
        check(a['result'] == 'unverified' and len(scripts(sim)) == 1 and 'watch' in a['detail'] and CHOICE in a['detail'],
              f"no choice flag watched: unverified, one try, the flags to watch named ({a['detail']})")


def use_checks():
    # the orb: chosen already; ZR 150 ms; the count falls
    with world(['use-item orb'], choice='Orb') as (sim, (a,)):
        check(a['result'] == 'used' and a['changes']['item']['count'] == [10, 9] and scripts(sim) == ['0:ZR/150'],
              f"use-item orb: ZR for 150 ms, the orbs 10 -> 9: used ({a['detail']}; {scripts(sim)})")
    # the dart is chosen first (the wheel), then ZR is held to aim and let go
    with world(['use-item dart'], choice='Orb', move='stick', confirm='a', fire='release') as (sim, (a,)):
        sc = scripts(sim)
        check(a['result'] == 'used' and a['changes']['item']['count'] == [30, 29] and a['changes']['aimed'] >= 4 and sc[-1] == '0:ZR/1000',
              f"use-item dart: the wheel first, then ZR held 1000 ms, the seeds 30 -> 29 and the camera turned ({a['detail']})")
        check(len(sc) == 2 and sc[0].startswith('0:L/'), 'one sequence for the wheel and one for the item')
    # the game fires with Y: the default (release) only aims; `fire y` presses Y 0.3 s before the ZR is let go
    with world(['use-item dart', 'use-item dart fire y'], choice='Dart', fire='y') as (sim, (a, b)):
        check(a['result'] == 'aimed' and a['changes']['item']['count'] == [30, 30] and not [s for s in scripts(sim) if s.startswith('0:L/')],
              f"the dart is the choice: no wheel; aimed (the camera turned), no seed spent ({a['detail']})")
        check(b['result'] == 'used' and b['changes']['item']['count'] == [30, 29] and scripts(sim)[-1] == '0:ZR/1000,0.7:Y/120',
              f"fire y: Y pressed 0.3 s before the end of the hold: used ({b['detail']}; {scripts(sim)[-1]})")
    # lock: ZL around it
    with world(['use-item dart fire a lock hold 800'], choice='Dart', fire='a') as (sim, (a,)):
        check(scripts(sim) == ['0:ZL/1900,0.4:ZR/800,0.9:A/120'] and a['result'] == 'used', f"lock holds ZL from before to after: {scripts(sim)} {a['result']}")
    # the item is not in the wheel: no ZR is sent
    with world(['use-item rope'], choice='Orb', move='stick', confirm='a') as (sim, (a,)):
        check(a['result'] == 'no-item' and not [s for s in scripts(sim) if 'ZR' in s] and sim.bridge.flags[ORBS] == 10,
              f"an item that cannot be chosen: no-item, ZR never pressed ({a['detail']})")
    # unverified choice: the ZR is pressed anyway, the count says
    with world(['use-item orb'], watched=False) as (sim, (a,)):
        check(len(scripts(sim)) == 2 and scripts(sim)[-1] == '0:ZR/150' and a['result'] in ('used', 'none'), 'the choice not watched and the item named: one wheel try, then ZR all the same')


def bad_checks():
    bad = ['wheel-select', 'wheel-select a b', 'wheel-select nothing', 'wheel-select orb via', 'wheel-select orb via x', 'wheel-select orb tries 0',
           'wheel-select orb tries 99', 'wheel-select orb tries x', 'use-item', 'use-item nothing', 'use-item orb hold 10', 'use-item orb hold 9000',
           'use-item orb hold x', 'use-item orb fire x', 'use-item orb fire', 'use-item orb dart']
    with using(table_file()), ItemSimulation(boot_events=0, follow=False, flags={CHOICE: hashed('Orb')}) as sim:
        sim.executor(bad + ['wait 0.1', 'end']).run()
        got = [e['src'] for e in sim.events() if e['ev'] == 'bad']
        check(got == bad, f'{len(bad)} malformed item steps are answered bad, each by its own usage text')
        check(not inputs(sim), 'and none of them sent an input')
        words = [e['why'] for e in sim.events() if e['ev'] == 'bad' and e['src'] == 'wheel-select nothing']
        check(words and 'wild-acorn' in words[0] and 'flare-gun' in words[0], 'an unknown item is answered with the table\'s words')


def main():
    global WORK
    with tempfile.TemporaryDirectory(prefix='hsap-items-') as tmp:
        WORK = Path(tmp)
        pure_checks()
        table_checks()
        wheel_checks()
        use_checks()
        bad_checks()
    print('test_hsap_items: all passed')


if __name__ == '__main__':
    main()
