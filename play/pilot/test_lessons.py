#!/usr/bin/env python3
"""lessons.py: before a planner call, the few most similar past failures and what finally worked there, in a small token budget: the similarity order (same cause,
same map, near the place, like geometry, something worked, recent), the token budget and k, folding of the same place and outcome, the episodes where nothing worked,
determinism, the on/off switch (flag, $PILOT_LESSONS, $PILOT_LEARN), a cold library adding nothing, and the two planners' requests: byte-identical to what they were
before lessons existed when off (pinned below), and with lessons on the same plus the `lessons` data key and one sentence. A made-up library (made-up maps and
places); no game, no GPU, no network.   python3 -I -B test_lessons.py     (test_pilot.py calls run() too)"""
import hashlib
import json
import math
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import deciders  # noqa: E402
import lessons  # noqa: E402
import pilot  # noqa: E402
import sections  # noqa: E402
import tactics  # noqa: E402

FAILS, CHECKS = [], [0]
ENV = ('PILOT_LESSONS', 'PILOT_LEARN', 'PILOT_LESSONS_TOKENS', 'PILOT_LESSONS_K')

# What the two planners' requests were before lessons existed (this file's made-up segment and chapter data, built by the code as it was): the sha256 of each
# request body as json.dumps writes it, and of its developer text. A change to either planner's prompt or request is a change of these numbers, on purpose.
GOAL_BODY, GOAL_DEVELOPER = '957d49e63493a730f4de2c6d5a897f121d1888d99659739ba731d4ac4e8c1a98', '0bdb5206c034995442f119c20664b6aa2476cf67716316e156426a4c6a99265f'
CHAPTER_BODY, CHAPTER_BODY_PICTURE = '43739a293176d825a7751e92087836804d710aabadbfb3ee0bcbdc6c95f89945', 'edc83a198f9420eea4775aae25e18c91f4e8ded9abe4585cad04582940948046'
CHAPTER_DEVELOPER = '8e9b15c1bd1cf799fde7312439ddc3722917655807329de3cb6bb41a3544f22e'


def check(cond, what):
    CHECKS[0] += 1
    if not cond:
        FAILS.append(what)
        print('FAIL', what, flush=True)


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


class Env:
    """Set (or, with None, remove) environment variables for a block."""

    def __init__(self, **kw):
        self.kw, self.old = kw, {}

    def __enter__(self):
        for k, v in self.kw.items():
            self.old[k] = os.environ.get(k)
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        return self

    def __exit__(self, *exc):
        for k, v in self.old.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


# ------------------------------------------------------------------------------------------------------ the made-up library

#       map                 place (x, y, z)         cause         tried                                    worked          how           target
ROWS = [
    ('Testland_Child', [12.0, 0.0, -40.0], 'wall', ['sidestep', 'angle', 'roll'], 'roll', 'recovered', 'chest-a'),                          # 0
    ('Testland_Child', [12.4, 0.0, -40.4], 'wall', ['sidestep', 'angle', 'roll'], 'roll', 'recovered', 'chest-a'),                          # 1: the same place, cause, outcome as 0
    ('Testland_Child', [60.0, 0.0, 10.0], 'ledge-up', ['sidestep', 'hop'], None, 'marked-bad', 'chest-b'),                                  # 2: nothing worked
    ('Otherland_Child', [5.0, 0.0, 5.0], 'wall', ['sidestep'], 'sidestep', 'recovered', None),                                              # 3: another map, the same cause
    ('Testland_Adult', [12.0, 0.0, -40.0], 'wall', ['angle'], 'angle', 'recovered', None),                                                  # 4: another map (the adult's), the same cause
    ('Testland_Child', [200.0, 0.0, 200.0], 'npc-in-way', ['wait', 'talk-through'], 'talk-through', 'recovered', 'friend-far'),             # 5: far off
    ('Otherland_Child', [9.0, 0.0, 9.0], 'door-side', ['door-other'], None, 'left', None),                                                  # 6: another map and cause: nothing to do with it
    ('Testland_Child', [-30.0, 0.0, 30.0], 'held', [], None, 'recovered', None),                                                            # 7: cleared by itself: nothing to learn
    ('Testland_Child', [60.4, 1.0, 10.4], 'ledge-up', ['sidestep', 'hop', 'roll'], None, 'marked-bad', 'chest-b'),                          # 8: the same place, cause, outcome as 2
    ('Testland_Child', [40.0, 0.0, -8.0], 'wall', ['sidestep', 'angle', 'roll', 'hop'], None, 'marked-bad', 'other-chest'),                 # 9: nothing worked
]
BIG = dict(budget=100000, k=50)   # (no limit: the order alone)


def book_of(folder, rows=ROWS):
    book = tactics.Book(folder)
    for i, (m, at, cause, tried, worked, how, target) in enumerate(rows):
        book.add_block(map=m, age=tactics.age_of_map(m), at=at, cause=cause, why='made up', geom={'door': 'no'}, tried=tried, worked=worked, how=how, s=5.0, target=target,
                       run=f'run-{i}', source='live', ts=f'2026-11-01T00:00:{i:02d}')
    return book


def where(items):
    """Which rows of ROWS the lessons came from (by the map and place they name), in order; None for one that is none of them."""
    keys = [('(12, -40)', 'Testland_Child', 0), ('(60, 10)', 'Testland_Child', 8), ('(5, 5)', 'Otherland_Child', 3), ('(12, -40)', 'Testland_Adult', 4),
            ('(200, 200)', 'Testland_Child', 5), ('(9, 9)', 'Otherland_Child', 6), ('(40, -8)', 'Testland_Child', 9)]
    out = []
    for t in items:
        out.append(next((i for place, m, i in keys if t.startswith(f'{m} {place}')), None))
    return out


# ------------------------------------------------------------------------------------------------------ the retrieval

def similarity_checks(tmp):
    book = book_of(Path(tmp) / 'sim')
    less = lessons.Lessons(book, **BIG)
    # the same cause first, then the same map, then the nearest, with the lessons of a block that cleared by itself left out
    got = less.for_plan(map='Testland_Child', age='child', at=[12.0, -40.0], cause='wall')
    order = where(got['items'])
    check(order[:4] == [0, 9, 3, 4], f'the same cause: the place Link is at first, then the same map and cause, then the same cause on other maps, the child\'s before the adult\'s ({order})')
    check(all('stopped by a wall' in t for t in got['items'][:4]) and not any('stopped by a wall' in t for t in got['items'][4:]),
          'every lesson of the same cause comes before any other')
    check(len(got['items']) == 6 and None not in order and 6 not in order,
          f'six lessons, the folded places among them: not the one of another map and cause, not the block that cleared by itself ({len(got["items"])} lessons, rows {order})')
    check('(12, -40)' in got['items'][0] and 'on the way to chest-a' in got['items'][0] and 'sidestep, angle failed; roll worked' in got['items'][0]
          and 'seen 2 times' in got['items'][0], f'a lesson says where, what he was going to, what failed and what worked, how often ({got["items"][0]})')

    # no cause known: the map and the nearness say what is relevant, and another map's episodes are not
    got = less.for_plan(map='Testland_Child', age='child', at=[12.0, -40.0])
    order = where(got['items'])
    check(order[0] == 0 and set(order) == {0, 5, 9, 8} and None not in order, f'no cause known: the same map only ({order})')
    check(order == [0, 5, 9, 8], f'... nearest first; a worked one before a nothing-worked one at much the same distance ({order})')
    got = less.for_plan(map='Testland_Adult', age='adult', at=[12.0, -40.0])
    check(where(got['items']) == [4], 'another map\'s lessons are not the adult map\'s')
    check(less.for_plan(age='child', at=[12.0, -40.0])['items'] == [] and less.for_plan()['items'] == [], 'neither a map nor a cause: nothing relevant')
    got = less.for_plan(cause='door-side')
    check([t.split(':')[0] for t in got['items']] == ['Otherland_Child (9, 9)'] and 'a door that would not open from this side' in got['items'][0], 'a cause alone is enough when no map is known')

    # a target the planner is about to choose: the episode on the way to it (nothing worked there) is first
    got = less.for_plan(map='Testland_Child', age='child', targets=[{'name': 'chest-b', 'x': 60.0, 'z': 10.0}])
    check(where(got['items'])[0] == 8 and 'nothing worked' in got['items'][0] and 'on the way to chest-b' in got['items'][0] and 'seen 2 times' in got['items'][0],
          f'a place the planner is about to send Link to: what stopped him there is first, and that nothing worked ({got["items"][:1]})')
    named = less.for_plan(map='Testland_Child', targets=['other-chest'])['items']
    check(where(named)[0] == 9, f'a name alone matches the target a block was on the way to ({where(named)})')
    # how a place is given does not matter
    same = [less.for_plan(map='Testland_Child', at=p) for p in ([12.0, -40.0], [12.0, 5.0, -40.0], (12.0, -40.0), {'x': 12.0, 'z': -40.0}, {'at': [12.0, 0.0, -40.0]})]
    check(all(s == same[0] for s in same) and same[0]['items'], 'a place as [x, z], [x, y, z], a tuple or a dict: the same lessons')
    check(less.for_plan(map='Testland_Child', at='nowhere', targets=[None, 5, {'x': 'a'}, [1]])['items'] == less.for_plan(map='Testland_Child')['items'],
          'a place that is none is ignored')
    check(less.for_plan(map='Testland_Child', cause='not-a-cause')['items'] == less.for_plan(map='Testland_Child')['items'], 'a cause that is none of the library\'s is ignored')

    # a block with no place at all, and the library growing under a live run
    book.add_block(map='Testland_Child', age='child', cause='wall', tried=['angle'], worked=None, how='left', target='lost', run='run-x', source='live')
    got = less.for_plan(map='Testland_Child', targets=['lost'])
    check(got['items'][0] == 'Testland_Child on the way to lost: stopped by a wall; nothing worked (tried angle; the target was left)', f'a block with no place ({got["items"][:1]})')
    got = less.for_plan(map='Testland_Child', targets=['lost'], at=[0.0, 0.0])
    check(sum('on the way to lost' in t for t in got['items']) == 1, 'the same block is not twice')

    # a like geometry and the newest, with all else equal
    gg = tactics.Book(Path(tmp) / 'geom2')
    gg.add_block(map='Geoland', at=[1.0, 0.0, 1.0], cause='wall', tried=['sidestep'], worked='roll', how='recovered', geom={'door': 'no', 'persons': '0'}, ts='2026-11-01T00:00:00')
    gg.add_block(map='Geoland', at=[1.0, 0.0, 1.0], cause='wall', tried=['sidestep'], worked='angle', how='recovered', geom={'door': 'yes', 'persons': '0'}, ts='2026-11-01T00:00:01')
    gl = lessons.Lessons(gg, **BIG)
    one = gl.for_plan(map='Geoland', at=[1.0, 1.0], geom={'door': 'no', 'persons': '0'})['items']
    two = gl.for_plan(map='Geoland', at=[1.0, 1.0], geom={'door': 'yes', 'persons': '0'})['items']
    check('roll worked' in one[0] and 'angle worked' in two[0], f'a like geometry ranks higher ({one[0]!r}, {two[0]!r})')
    check('angle worked' in gl.for_plan(map='Geoland', at=[1.0, 1.0])['items'][0], 'all else equal the newest first')
    rec = tactics.Book(Path(tmp) / 'rec')
    rec.add_block(map='Recland', at=[1.0, 0.0, 1.0], cause='wall', tried=['sidestep'], worked='roll', how='recovered', ts='2026-11-01T00:00:00')
    rec.add_block(map='Recland', at=[1.3, 0.0, 1.0], cause='wall', tried=['sidestep'], worked='angle', how='recovered', ts='2026-11-01T00:00:01')
    check('angle worked' in lessons.Lessons(rec, **BIG).for_plan(map='Recland', at=[1.0, 1.0])['items'][0], 'a block 0.3 m nearer is no reason to put an old one before a new one')
    check(lessons.W_CAUSE > lessons.W_MAP + lessons.W_NEAR + lessons.W_LIKE + lessons.W_WORKED + lessons.W_RECENT
          and lessons.W_MAP > lessons.W_NEAR + lessons.W_LIKE + lessons.W_WORKED + lessons.W_RECENT
          and lessons.W_NEAR > lessons.W_LIKE + lessons.W_WORKED + lessons.W_RECENT and lessons.W_LIKE > lessons.W_WORKED + lessons.W_RECENT
          and lessons.W_WORKED > lessons.W_RECENT, 'the weights: each step outweighs every later one together')


def nothing_worked_checks(tmp):
    """Where nothing worked is surfaced, and not pushed out by the lessons of a place where something did."""
    book = book_of(Path(tmp) / 'nw')
    less = lessons.Lessons(book, budget=100000, k=3)
    got = less.for_plan(map='Testland_Child', age='child', at=[12.0, -40.0])
    check(any('nothing worked' in t for t in got['items']), f'a nothing-worked lesson is among the three ({got["items"]})')
    check('nothing worked (tried sidestep, angle, roll, hop; the spot was marked bad)' in ' '.join(got['items']),
          f'it says what was tried and how it ended ({[t for t in got["items"] if "nothing" in t]})')
    only = book_of(Path(tmp) / 'nw2', [r for r in ROWS if r[4] is None and r[3]])
    got = lessons.Lessons(only, **BIG).for_plan(map='Testland_Child')
    check(len(got['items']) == 2 and all('nothing worked' in t for t in got['items']), f'a library where nothing ever worked still gives its lessons ({len(got["items"])})')
    # a place where something worked and the same place where nothing did are two lessons, the worked one first
    both = book_of(Path(tmp) / 'nw3', [('Bothland_Child', [3.0, 0.0, 3.0], 'wall', ['sidestep', 'roll'], None, 'marked-bad', None),
                                       ('Bothland_Child', [3.0, 0.0, 3.0], 'wall', ['sidestep', 'roll'], 'roll', 'recovered', None)][::-1])
    got = lessons.Lessons(both, **BIG).for_plan(map='Bothland_Child', at=[3.0, 3.0])
    check(len(got['items']) == 2 and 'roll worked' in got['items'][0] and 'nothing worked' in got['items'][1], f'worked first, and both told ({got["items"]})')
    # a tried list that is long and names that are long: still one short lesson
    long = book_of(Path(tmp) / 'nw4', [('A' * 60 + '_Child', [1.0, 0.0, 1.0], 'door-side', [f'tactic-{i}' for i in range(12)], None, 'marked-bad', 'a-target-with-a-very-long-name-' + 'x' * 60)])
    t = lessons.Lessons(long, **BIG).for_plan(map='A' * 60 + '_Child')['items']
    check(len(t) == 1 and len(t[0]) <= lessons.MAX_CHARS and t[0].endswith('…'), f'a lesson is at most {lessons.MAX_CHARS} characters ({len(t[0]) if t else None})')
    many = book_of(Path(tmp) / 'nw5', [('Manyland_Child', [1.0, 0.0, 1.0], 'wall', [f't{i}' for i in range(9)], None, 'left', None)])
    t = lessons.Lessons(many, **BIG).for_plan(map='Manyland_Child')['items']
    check(t == ['Manyland_Child (1, 1): stopped by a wall; nothing worked (tried t0, t1, t2, t3, t4 and 4 more; the target was left)'], f'a long tried list is cut ({t})')
    demo = book_of(Path(tmp) / 'nw6', [('Demoland_Child', [1.0, 0.0, 1.0], 'wall', ['sidestep', 'demo:ab12cd34'], 'demo:ab12cd34', 'recovered', None)])
    t = lessons.Lessons(demo, **BIG).for_plan(map='Demoland_Child')['items']
    check(t == ['Demoland_Child (1, 1): stopped by a wall; sidestep failed; a recorded demonstration worked'], f'a demonstration is named as one ({t})')
    for c in tactics.CAUSES:
        check(c in lessons.WORDS, f'the cause {c} has words')
    odd = book_of(Path(tmp) / 'nw7', [('Oddland_Child', [1.0, 0.0, 1.0], 'wall', ['angle', 'roll'], None, 'recovered', None)])
    t = lessons.Lessons(odd, **BIG).for_plan(map='Oddland_Child')['items']
    check(t == ['Oddland_Child (1, 1): stopped by a wall; it cleared after angle, roll'], f'a block that cleared after rungs that were not credited ({t})')


def fold_checks(tmp):
    rows = [('Foldland_Child', [10.0, 0.0, 10.0], 'wall', ['angle'], 'angle', 'recovered', None),
            ('Foldland_Child', [11.0, 0.0, 11.0], 'wall', ['angle'], 'angle', 'recovered', None),          # 1.4 m: the same place
            ('Foldland_Child', [10.0, 0.0, 10.0], 'wall', ['angle', 'roll'], 'roll', 'recovered', None),    # another outcome: not folded
            ('Foldland_Child', [10.0, 0.0, 10.0], 'ledge-up', ['angle'], 'angle', 'recovered', None),       # another cause
            ('Foldland_Child', [10.0, 0.0, 14.0], 'wall', ['angle'], 'angle', 'recovered', None),          # 4 m away: another place
            ('Foldland_Child', [10.0, 6.0, 10.0], 'wall', ['angle'], 'angle', 'recovered', None),          # 6 m above: another floor
            ('Foldland_Child', [10.4, 0.0, 10.3], 'wall', ['angle'], 'angle', 'recovered', None)]          # the same place again
    less = lessons.Lessons(book_of(Path(tmp) / 'fold', rows), **BIG)
    items = less.for_plan(map='Foldland_Child', at=[10.0, 10.0])['items']
    check(len(items) == 5 and sum('seen 3 times' in t for t in items) == 1 and sum('seen' in t for t in items) == 1, f'the same place, cause and outcome is one lesson with a count ({items})')
    check(len(set(items)) == len(items), 'no duplicates')
    ids = less.for_plan(map='Foldland_Child', at=[10.0, 10.0])['ids']
    check(len(ids) == len(items) == len(set(ids)) and all(len(i) == 8 for i in ids), 'one id per lesson, none twice')


def budget_checks(tmp):
    book = book_of(Path(tmp) / 'budget')
    for budget in (0, 10, 40, 60, 100, 150, 200, 350, 1000):
        for k in (0, 1, 2, 3, 5, 10):
            got = lessons.Lessons(book, budget=budget, k=k).for_plan(map='Testland_Child', age='child', at=[12.0, -40.0], cause='wall')
            est = lessons.tokens_of(got['items']) if got['items'] else 0
            check(len(got['items']) <= k and est <= budget and got['tokens'] == math.ceil(est) and len(got['ids']) == len(got['items']),
                  f'budget {budget} tokens, k {k}: {len(got["items"])} lessons, {est:.1f} tokens estimated, {got["tokens"]} given')
    one = lessons.Lessons(book, budget=100000, k=1).for_plan(map='Testland_Child', at=[12.0, -40.0])
    three = lessons.Lessons(book, budget=100000, k=3).for_plan(map='Testland_Child', at=[12.0, -40.0])
    check(len(one['items']) == 1 and one['items'][0] == three['items'][0] and len(three['items']) == 3, 'k is how many: the best first, the same best')
    default = lessons.Lessons(book)
    check((default.budget, default.k) == (350, 3) == (lessons.BUDGET_TOKENS, lessons.K), 'the defaults: 350 tokens, 3 lessons')
    got = default.for_plan(map='Testland_Child', at=[12.0, -40.0], cause='wall')
    check(len(got['items']) == 3 and 0 < got['tokens'] <= 350, f'the defaults give three lessons in 350 tokens ({got["tokens"]})')
    # a lesson too long for what is left of the budget is skipped, and a shorter one after it still goes in
    skip = book_of(Path(tmp) / 'skip', [('Skipland_Child', [1.0, 0.0, 1.0], 'wall', ['sidestep', 'angle', 'roll'], 'roll', 'recovered', 'a-target-with-a-long-name-' + 'x' * 40),
                                        ('Skipland_Child', [1.0, 0.0, 2.0], 'wall', [], None, 'left', None)])
    both = lessons.Lessons(skip, **BIG).for_plan(map='Skipland_Child', at=[1.0, 1.0])['items']
    fit = lessons.Lessons(skip, budget=lessons.tokens_of(both[1:]), k=3).for_plan(map='Skipland_Child', at=[1.0, 1.0])
    check(len(both) == 2 and 'roll worked' in both[0] and fit['items'] == both[1:], f'the best lesson does not fit the budget: it is left out and the next one is given ({fit["items"]})')


def determinism_checks(tmp):
    book = book_of(Path(tmp) / 'det')
    q = dict(map='Testland_Child', age='child', at=[12.0, -40.0], targets=[{'name': 'chest-b', 'x': 60.0, 'z': 10.0}], failed=['other-chest'])
    a = lessons.Lessons(book).for_plan(**q)
    b = lessons.Lessons(book).for_plan(**q)
    c = lessons.Lessons(tactics.Book(Path(tmp) / 'det')).for_plan(**q)   # (read afresh from the file)
    check(a == b == c and a['items'], 'the same library and call: the same lessons, in the same order, with the same ids')
    check(json.dumps(a) == json.dumps(c), 'byte for byte')
    book.add_block(map='Testland_Child', age='child', at=[12.0, 0.0, -40.0], cause='wall', tried=['hop'], worked='hop', how='recovered', run='run-new', source='live')
    d = lessons.Lessons(book).for_plan(**q)
    check(d != a and any('hop worked' in t for t in d['items']), 'a block written meanwhile (the run\'s own) is a lesson at the next call')


def cold_checks(tmp):
    empty = lessons.Lessons(tactics.Book(Path(tmp) / 'cold'))
    check(empty.for_plan(map='Testland_Child', at=[1.0, 1.0], cause='wall') == {'items': [], 'tokens': 0, 'ids': []}, 'a library with no file: nothing, no error')
    book = tactics.Book(Path(tmp) / 'attempts')
    book.record('roll', 'wall', 'worked', map='Testland_Child', at=[1.0, 0.0, 1.0])
    book.record('sidestep', 'wall', 'failed', map='Testland_Child', at=[1.0, 0.0, 1.0])
    check(lessons.Lessons(book).for_plan(map='Testland_Child', at=[1.0, 1.0], cause='wall')['items'] == [], 'attempts are no episodes: nothing')
    warm = lessons.Lessons(book_of(Path(tmp) / 'warm'))
    check(warm.for_plan(map='Nowhere_Child', at=[1.0, 1.0])['items'] == [] and 'error' not in warm.for_plan(map='Nowhere_Child'), 'nothing that resembles the call: nothing')
    check(lessons.Lessons(book_of(Path(tmp) / 'warm0'), k=0).for_plan(map='Testland_Child')['items'] == [] and lessons.Lessons(book_of(Path(tmp) / 'warm1'), budget=0).for_plan(
        map='Testland_Child')['items'] == [], 'k or the budget at 0: nothing')

    class Broken:
        def rows(self, kind=None):
            raise OSError('the library is gone')
    got = lessons.Lessons(Broken()).for_plan(map='Testland_Child')
    check(got['items'] == [] and got['error'] == 'OSError: the library is gone', f'a library that cannot be read is no lessons, with the reason ({got})')
    check(lessons.Lessons(Broken()).for_goals(None, [], []).get('error', '').startswith('OSError'), 'the adapters answer a library that cannot be read as the retrieval does')
    check(lessons.Lessons(book_of(Path(tmp) / 'bad')).for_goals(object(), [object()], [])['items'] == [] and lessons.Lessons(book_of(Path(tmp) / 'bad')).for_chapter(None)['items'] == [],
          'the adapters never raise on what they do not understand')


# ------------------------------------------------------------------------------------------------------ the switch

def switch_checks(tmp):
    book = book_of(Path(tmp) / 'switch')
    with Env(**{k: None for k in ENV}):
        check(lessons.make('on', book) is not None and lessons.make('off', book) is None, 'the flag: on gives lessons, off gives None')
        check(lessons.make(None, book) is not None, 'nothing said: on')
        check(isinstance(lessons.make('on', book), lessons.Lessons) and lessons.make('ON ', book) is not None and lessons.make('Off', book) is None, 'the flag is not fussy about case')
        try:
            lessons.make('maybe', book)
            check(False, 'a flag that is neither on nor off is refused')
        except ValueError as e:
            check('maybe' in str(e), 'a flag that is neither on nor off is refused')
    with Env(PILOT_LESSONS='off', PILOT_LEARN=None):
        check(lessons.make(None, book) is None and lessons.make('on', book) is not None, '$PILOT_LESSONS=off: off, unless the flag says on')
    with Env(PILOT_LESSONS='on', PILOT_LEARN='off'):
        check(lessons.make(None, book) is not None and lessons.make('off', book) is None, '$PILOT_LESSONS=on beats $PILOT_LEARN=off; the flag beats both')
    with Env(PILOT_LESSONS=None, PILOT_LEARN='off'):
        check(lessons.make(None, book) is None and lessons.make('on', book) is not None, '$PILOT_LEARN=off: off, unless the flag says on')
    with Env(PILOT_LESSONS=None, PILOT_LEARN='on'):
        check(lessons.make(None, book) is not None, '$PILOT_LEARN=on: on')
    with Env(PILOT_LESSONS='nonsense', PILOT_LEARN=None):
        check(lessons.make(None, book) is not None, 'a $PILOT_LESSONS that is neither on nor off is no word at all: on')
    with Env(PILOT_LESSONS='nonsense', PILOT_LEARN='off'):
        check(lessons.make(None, book) is None, '... and then $PILOT_LEARN=off decides')
    with Env(**{k: None for k in ENV}):
        less = lessons.make('on', book)
        check(less.book is book and (less.budget, less.k) == (350, 3), 'make keeps the library and the defaults')
        less = lessons.make('on', book, budget=120, k=2)
        check((less.budget, less.k) == (120, 2), 'the budget and k are configurable')
    with Env(PILOT_LESSONS_TOKENS='90', PILOT_LESSONS_K='1', PILOT_LEARN=None, PILOT_LESSONS=None):
        less = lessons.make(None, book)
        check((less.budget, less.k) == (90, 1) and lessons.make('on', book, budget=500, k=4).budget == 500, 'and by $PILOT_LESSONS_TOKENS and $PILOT_LESSONS_K')
    with Env(PILOT_LESSONS_TOKENS='lots', PILOT_LESSONS_K='-3', PILOT_LEARN=None, PILOT_LESSONS=None):
        less = lessons.make(None, book)
        check((less.budget, less.k) == (350, 3), 'a count that is none or negative is the default')
    check(lessons.record(False) == {'on': False, 'n': 0, 'tokens_est': 0, 'ids': []}, 'the log row when off')
    got = lessons.Lessons(book).for_plan(map='Testland_Child', at=[12.0, -40.0])
    row = lessons.record(True, got)
    check(row == {'on': True, 'n': len(got['items']), 'tokens_est': got['tokens'], 'ids': got['ids']} and row['n'] == 3, 'the log row when on: {on, n, tokens_est, ids}')
    check(lessons.record(True, {'items': [], 'tokens': 0, 'ids': [], 'error': 'E: x'}) == {'on': True, 'n': 0, 'tokens_est': 0, 'ids': [], 'error': 'E: x'}, 'a failed retrieval says so')


# ------------------------------------------------------------------------------------------------------ the planners

def goal_segment():
    spec = {'name': 'made-up', 'what': 'a made-up errand', 'area': 'Testland_Child', 'goal': [
        {'name': 'chest', 'flag': 'Chest_Open=1', 'kind': 'chest', 'what': 'open the chest',
         'targets': [{'name': 'chest', 'at': [10.0, 5.0], 'y': 0.0, 'kind': 'chest'}, {'name': 'other-chest', 'at': [40.2, -7.46], 'kind': 'chest'}]},
        {'name': 'friend', 'flag': 'Talked=1', 'kind': 'talk', 'what': 'talk to the friend', 'targets': [{'name': 'friend', 'at': [6.0, 3.0], 'kind': 'talk'}]}]}
    seg = pilot.Segment(Path('made-up.toml'), spec=spec)
    seg.goals[0].targets[1].status = 'failed'   # the second chest was left as failed
    tried = [{'step': 'go', 'goal': 'chest', 'target': 'chest', 'result': 'stuck', 'moved_m': 0.4},
             {'step': 'recover:replan', 'goal': 'chest', 'target': 'other-chest', 'result': 'marked-bad', 'moved_m': 0.0, 'at': [41.0, -8.0]}]
    return seg, tried


class Stub:
    """The model's side of a Responses request: keeps the bodies, answers with an empty plan."""
    real = False

    def __init__(self):
        self.bodies = []

    def post(self, path, body, *, api, model, kind, estimate, timeout=30.0):
        self.bodies.append(body)
        text = json.dumps({'order': [], 'targets': [], 'drop': [], 'reason': 'made up'})
        return {'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': text}]}]}, 5.0, {'usage': None, 'cost_usd': 0.0}


def goal_planner_checks(tmp):
    seg, tried = goal_segment()
    planner = deciders.Planner(Stub(), 'gpt-6-astra')
    check(planner.lessons is None, 'a planner has no lessons until it is given some')
    off = planner.body(seg, seg.goals, tried)
    check(sha(json.dumps(off)) == GOAL_BODY and sha(off['input'][0]['content']) == GOAL_DEVELOPER and deciders.PLANNER_DEVELOPER == off['input'][0]['content'],
          'lessons off: the goal-level planner\'s request is byte for byte the one it was before lessons')
    check(planner.body(seg, seg.goals, tried, None) == off and planner.body(seg, seg.goals, tried, []) == off, 'no lessons given, or none: the same request')
    items = ['Testland_Child (40, -8) on the way to other-chest: stopped by a wall; nothing worked (tried angle)']
    on = planner.body(seg, seg.goals, tried, items)
    d_off, d_on = json.loads(off['input'][1]['content']), json.loads(on['input'][1]['content'])
    check(list(d_on) == list(d_off) + ['lessons'] and d_on.pop('lessons') == items and d_on == d_off and json.dumps(d_on) == off['input'][1]['content'],
          'lessons on: the data is the same and one key more, last')
    check(on['input'][0]['content'] == off['input'][0]['content'] + ' ' + lessons.NOTE and on['input'][0]['role'] == 'developer',
          'and the developer text is the same and one sentence more')
    check({k: v for k, v in on.items() if k != 'input'} == {k: v for k, v in off.items() if k != 'input'} and on['input'][1]['role'] == off['input'][1]['role'],
          'nothing else of the request differs')
    check(lessons.NOTE.count('. ') == 0 and lessons.NOTE.endswith('.') and 'hints' in lessons.NOTE and 'not facts' in lessons.NOTE and 'worked' in lessons.NOTE
          and 'failed' in lessons.NOTE, 'the sentence is one sentence: hints, not facts, what worked, what failed')

    # plan(): the request it sends and the log row it returns
    book = book_of(Path(tmp) / 'planner')
    client = Stub()
    p = deciders.Planner(client, 'gpt-6-astra')
    out, info = p.plan(seg, seg.goals, tried)
    check(json.dumps(client.bodies[-1]) == json.dumps(off) and info['request'] == off and info['lessons'] == {'on': False, 'n': 0, 'tokens_est': 0, 'ids': []} and out['reason'] == 'made up',
          'off: plan() sends that request and says lessons are off')
    p.lessons = lessons.Lessons(book)
    want = p.lessons.for_goals(seg, seg.goals, tried)
    out, info = p.plan(seg, seg.goals, tried)
    sent = json.loads(client.bodies[-1]['input'][1]['content'])
    check(want['items'] and sent['lessons'] == want['items'] and info['lessons'] == {'on': True, 'n': len(want['items']), 'tokens_est': want['tokens'], 'ids': want['ids']},
          f'on: plan() sends the lessons and logs {{on, n, tokens_est, ids}} ({info["lessons"]["n"]} lessons, {info["lessons"]["tokens_est"]} tokens)')
    check('other-chest' in want['items'][0] and 'nothing worked' in want['items'][0], f'the point marked bad and the target left as failed come first ({want["items"][0]})')
    check(client.bodies[-1]['input'][0]['content'].endswith(lessons.NOTE) and info['lessons']['tokens_est'] <= 350 and info['request'] == client.bodies[-1],
          'the sentence is in, and the request is the logged one')
    cold = deciders.Planner(client, 'gpt-6-astra')
    cold.lessons = lessons.Lessons(tactics.Book(Path(tmp) / 'cold-planner'))
    out, info = cold.plan(seg, seg.goals, tried)
    check(json.dumps(client.bodies[-1]) == json.dumps(off) and info['lessons'] == {'on': True, 'n': 0, 'tokens_est': 0, 'ids': []},
          'on with a cold library: the very request that off sends (no key, no sentence), and the log says on with none')
    # the adapter: finished goals, dropped and moving targets are no place to ask about
    seg2, tried2 = goal_segment()
    seg2.goals[1].status = 'met'
    seg2.goals[0].targets[0].follow = 'someone'
    seg2.goals[0].targets[1].status = 'dropped'
    check(p.lessons.for_goals(seg2, seg2.goals, [])['items'] == p.lessons.for_plan(map='Testland_Child', age='child')['items'], 'only open and failed targets with a place count')


CHAPTER_DATA = {'aim': 'x', 'why_now': 'start', 'link': {'area': 'Fake_A', 'pos': [1.0, 2.0, 3.0]}}


def chapter_planner_checks(tmp):
    planner = sections.ChapterPlanner(Stub(), 'gpt-6-astra')
    off = planner.body(CHAPTER_DATA)
    pic = planner.body(CHAPTER_DATA, image='data:image/jpeg;base64,AAAA')
    check(sha(json.dumps(off)) == CHAPTER_BODY and sha(json.dumps(pic)) == CHAPTER_BODY_PICTURE and sha(off['input'][0]['content']) == CHAPTER_DEVELOPER
          and off['input'][0]['content'] == sections.PLANNER_DEVELOPER, 'no lessons: the chapter planner\'s request is byte for byte the one it was before lessons')
    items = ['Testland_Child (12, -40): stopped by a wall; sidestep, angle failed; roll worked']
    on = planner.body({**CHAPTER_DATA, 'lessons': items}, image='data:image/jpeg;base64,AAAA')
    text_off, text_on = pic['input'][1]['content'][0]['text'], on['input'][1]['content'][0]['text']
    d_on = json.loads(text_on)
    check(list(d_on) == list(CHAPTER_DATA) + ['lessons'] and d_on.pop('lessons') == items and json.dumps(d_on, separators=(',', ':')) == text_off, 'lessons on: the data is the same and one key more, last')
    check(text_on == text_off[:-1] + ',"lessons":' + json.dumps(items, separators=(',', ':')) + '}', 'byte for byte: the same text with the key before the closing brace')
    check(on['input'][0]['content'] == pic['input'][0]['content'] + ' ' + lessons.NOTE and on['input'][1]['content'][1] == pic['input'][1]['content'][1]
          and {k: v for k, v in on.items() if k != 'input'} == {k: v for k, v in pic.items() if k != 'input'}, 'and the developer text one sentence more, the picture and the rest as they were')
    check(on['input'][0]['content'].startswith(sections.PLANNER_DEVELOPER) and on['input'][0]['content'] != sections.PLANNER_DEVELOPER, 'the prompt is the chapter\'s own, then the sentence')

    book = book_of(Path(tmp) / 'chapter')
    less = lessons.Lessons(book)
    link = {'area': 'Testland_Child', 'age': 'child', 'pos': [12.0, 0.0, -40.0]}
    timeline = [{'id': 'o1', 'goal_status': 'open', 'area': 'Testland_Child', 'end_area': 'Testland_Child', 'targets': [{'name': 'other-chest', 'at': [40.2, -7.46], 'y': 0.0}],
                 'end_pos': [39.0, 0.0, -7.0]},
                {'id': 'o2', 'goal_status': 'met', 'area': 'Testland_Child', 'end_area': 'Testland_Child', 'targets': [{'name': 'chest-b', 'at': [60.0, 10.0]}], 'end_pos': [60.0, 0.0, 10.0]},
                {'id': 'o3', 'goal_status': 'open', 'area': 'Otherland_Child', 'end_area': 'Otherland_Child', 'targets': [{'name': 'friend-far', 'at': [200.0, 200.0]}], 'end_pos': [200.0, 0.0, 200.0]}]
    got = less.for_chapter(link, timeline)
    want = less.for_plan(map='Testland_Child', age='child', at=[12.0, 0.0, -40.0], failed=[{'name': 'other-chest', 'at': [40.2, -7.46]}, {'at': [39.0, 0.0, -7.0]}])
    check(got == want and len(got['items']) == 3, 'the chapter planner\'s call: Link\'s place and map, and what the objectives that were not met went to and where they ended; not the met, not another map\'s')
    check(where(got['items'])[:2] == [0, 9], f'Link\'s own place first, then where the last objective was stopped ({where(got["items"])})')
    check(less.for_chapter(link, [])['items'] == less.for_plan(map='Testland_Child', age='child', at=[12.0, 0.0, -40.0])['items'], 'with no objectives so far, Link\'s place alone')
    check(less.for_chapter({'area': 'Nowhere_Child', 'age': 'child', 'pos': [0.0, 0.0, 0.0]}, timeline)['items'] == [], 'a map the library has not seen: nothing')


def run():
    with Env(**{k: None for k in ENV}), tempfile.TemporaryDirectory(prefix='test-lessons-') as tmp:
        similarity_checks(tmp)
        nothing_worked_checks(tmp)
        fold_checks(tmp)
        budget_checks(tmp)
        determinism_checks(tmp)
        cold_checks(tmp)
        switch_checks(tmp)
        goal_planner_checks(tmp)
        chapter_planner_checks(tmp)
    print(f'test_lessons: {CHECKS[0]} checks, {len(FAILS)} failed')
    return not FAILS


def main():
    ok = run()
    print('test_lessons: all passed' if ok else 'test_lessons: FAILED')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
