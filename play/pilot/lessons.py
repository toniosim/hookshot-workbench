#!/usr/bin/env python3
"""Lessons for the planner: before a planner call, the few most similar past failures and what finally worked there, in a small token budget.

Why: a planner (deciders.Planner for a segment's goals, sections.ChapterPlanner for a chapter's objectives) reorders targets and picks the next objectives without
knowing that the pilot has been stopped at the same place before, by what, and what finally got it past (or that nothing did). The tactics library (tactics.py) keeps
one `block` row per stuck episode: the map, the place, the cause, what was tried in order, what finally worked. Here the few that resemble this call are put in the
request as `lessons`, each one short sentence, so the planner stays off a target or a route that failed there, unless the way that worked is available.

  similarity   the same cause (when the caller knows it) > the same map > near the place (where Link is, where the last objectives failed, the targets the planner is
               about to choose between; a block that was on the way to such a target counts too) > a like age and geometry > something finally worked there (nothing-worked
               episodes surface all the same: they warn the planner off a target) > recent. The weights make each step outweigh every later one together, so the order
               is the one written here. An episode that has nothing to do with the call (not the same map, not the same cause) is never a lesson.
  folding      the same place (3 m), cause and outcome is one lesson with a count, not three.
  budget       at most `k` lessons and `budget` tokens (the code's own estimate, len(json) / 3, of the `lessons` key as it goes in the request; the fixed sentence NOTE
               that explains it to the planner is not counted). Deterministic: the same library and the same call give the same lessons in the same order.
  on and off   `make(switch, book)` returns None when switched off ('off', else $PILOT_LESSONS, else $PILOT_LEARN=off, else on): the planners then build the very request they
               built before lessons existed. A cold library (no episode that resembles the call) adds nothing either: no key, no sentence.

The `ids` of a retrieval (a short hash of each lesson's newest episode) and its size go into the planners' log rows (`record`), so the scoreboard can compare runs with
and without lessons. Game-derived (maps, places): lessons live only in the request and the private logs. Standard library only; no game, no network.
"""
import hashlib
import json
import math
import os

import tactics

NOTE = ('`lessons`, when present, are hints from earlier runs, not facts: each is a place where the pilot was stopped before, what stopped it and what finally got it past '
        '(or that nothing did); do not send the pilot to a target or along a route that failed there unless the way that worked is available.')

BUDGET_TOKENS, K = 350, 3
NEAR_M = 10.0          # nearness is 1 at the place and 1/2 this many metres away
MAX_CHARS = 200        # one lesson
W_CAUSE, W_MAP, W_NEAR, W_LIKE, W_WORKED, W_RECENT = 16.0, 8.0, 4.0, 2.0, 1.0, 0.5   # each is more than the sum of those after it
W_AT, W_FAILED, W_TARGET, W_NAME = 1.0, 1.0, 0.75, 0.5   # how much a place (or a name) of the call counts: Link's own and where objectives failed, the targets, and a block's target named alike

WORDS = {'wall': 'a wall', 'ledge-up': 'a ledge too high to climb', 'drop-not-taken': 'a drop it would not take', 'door-side': 'a door that would not open from this side',
         'npc-in-way': 'a person in the way', 'npc-crowd': 'a crowd in the way', 'held': 'a text box or a scene holding him', 'water-edge': "the water's edge",
         'other-floor': 'a target on another floor', 'slow': 'ground that slowed him to a crawl', 'unknown': 'something unknown'}
ENDS = {'marked-bad': 'the spot was marked bad', 'left': 'the target was left'}


# ------------------------------------------------------------------------------------------------------------------------ on and off

def enabled(switch=None):
    """Whether lessons are on: `switch` 'on' | 'off' (the --lessons flag) wins; None: $PILOT_LESSONS ('on' | 'off'), else $PILOT_LEARN=off turns them off, else on."""
    if switch is not None:
        s = str(switch).strip().lower()
        if s not in ('on', 'off'):
            raise ValueError(f'lessons: {switch!r} is neither on nor off')
        return s == 'on'
    env = os.environ.get('PILOT_LESSONS', '').strip().lower()
    if env in ('on', 'off'):
        return env == 'on'
    return os.environ.get('PILOT_LEARN', '').strip().lower() != 'off'


def _env_int(name, default):
    try:
        v = int(os.environ[name])
    except (KeyError, ValueError):
        return default
    return v if v >= 0 else default


def make(switch, book=None, budget=None, k=None):
    """The Lessons over a tactics.Book, or None when switched off (`enabled`). `budget` (tokens) and `k` default to $PILOT_LESSONS_TOKENS and $PILOT_LESSONS_K, else
    350 and 3."""
    if not enabled(switch):
        return None
    return Lessons(book if book is not None else tactics.Book(), budget=_env_int('PILOT_LESSONS_TOKENS', BUDGET_TOKENS) if budget is None else budget,
                   k=_env_int('PILOT_LESSONS_K', K) if k is None else k)


def tokens_of(items):
    """What `items` add to a request, by the code's own estimate (len(json) / 3): the `lessons` key and its list, serialized the way the planners do."""
    return len(json.dumps({'lessons': list(items)})) / 3.0


def record(on, got=None):
    """The planners' log row for a call: {on, n, tokens_est, ids} (on false and zeros when lessons are off), `error` when the retrieval failed."""
    got = got or {}
    row = {'on': bool(on), 'n': len(got.get('items') or ()), 'tokens_est': got.get('tokens', 0), 'ids': list(got.get('ids') or ())}
    if got.get('error'):
        row['error'] = got['error']
    return row


# ------------------------------------------------------------------------------------------------------------------------ places and words

def _xz(p):
    """(x, z) of a place given as [x, z], [x, y, z] or a dict with x and z (or `at`); None when it is none of these."""
    if isinstance(p, dict):
        if 'at' in p:
            return _xz(p['at'])
        p = [p.get('x'), p.get('z')]
    try:
        if len(p) == 2:
            x, z = p
        elif len(p) >= 3:
            x, z = p[0], p[2]
        else:
            return None
        return float(x), float(z)
    except (TypeError, ValueError):
        return None


def _y(p):
    try:
        return float(p[1]) if len(p) >= 3 else None
    except (TypeError, ValueError):
        return None


def _name(t):
    return 'a recorded demonstration' if str(t).startswith('demo:') else str(t)


def _list(ts, cap=5):
    ts = list(dict.fromkeys(_name(t) for t in ts))
    return ', '.join(ts[:cap]) + (f' and {len(ts) - cap} more' if len(ts) > cap else '')


def _text(r, n):
    """One lesson: where (the map and the place in whole metres, the target he was going to), what stopped him, what was tried and what finally worked."""
    where = str(r.get('map'))
    xz = _xz(r.get('at'))
    if xz:
        where += f' ({round(xz[0])}, {round(xz[1])})'
    if isinstance(r.get('target'), str) and r['target']:
        where += f" on the way to {r['target']}"
    tried = [t for t in (r.get('tried') or []) if isinstance(t, str)]
    worked = r.get('worked') if isinstance(r.get('worked'), str) else None
    if worked:
        failed = [t for t in tried if t != worked]
        out = (f'{_list(failed)} failed; ' if failed else '') + f'{_name(worked)} worked'
    elif r.get('how') == 'recovered':
        out = f'it cleared after {_list(tried)}' if tried else 'it cleared by itself'
    else:
        bits = ([f'tried {_list(tried)}'] if tried else []) + ([ENDS[r['how']]] if r.get('how') in ENDS else [])
        out = 'nothing worked' + (f" ({'; '.join(bits)})" if bits else '')
    text = f"{where}: stopped by {WORDS.get(r.get('cause')) or str(r.get('cause')).replace('-', ' ')}; {out}" + (f' (seen {n} times)' if n > 1 else '')
    return text if len(text) <= MAX_CHARS else text[:MAX_CHARS - 1] + '…'


def _id(r):
    return hashlib.sha1(json.dumps(r, sort_keys=True, separators=(',', ':')).encode()).hexdigest()[:8]


def _fold(rows):
    """[{row, n, idx}]: the same map, cause, outcome (what worked, or nothing) and place (3 m and 3 m of height of the first one; blocks with no place: the same target)
    are one lesson: its newest episode, how many there were. `rows` are (position in the library, row)."""
    groups, by = [], {}
    for i, r in rows:
        key = (r.get('map'), r.get('cause'), r.get('worked'))
        xz, y = _xz(r.get('at')), _y(r.get('at') or [])
        for g in by.get(key, ()):
            if xz is None or g['xz'] is None:
                same = xz is None and g['xz'] is None and r.get('target') == g['target']
            else:
                same = math.hypot(xz[0] - g['xz'][0], xz[1] - g['xz'][1]) <= tactics.CLUSTER_M and (y is None or g['y'] is None or abs(y - g['y']) < 3.0)
            if same:
                g['row'], g['n'], g['idx'] = r, g['n'] + 1, i
                break
        else:
            g = {'row': r, 'n': 1, 'idx': i, 'xz': xz, 'y': y, 'target': r.get('target')}
            groups.append(g)
            by.setdefault(key, []).append(g)
    return groups


# ------------------------------------------------------------------------------------------------------------------------ the lessons

class Lessons:
    """The retrieval (module doc) over a tactics.Book's `block` rows. Never raises: a library that cannot be read is no lessons, and the call says why in `error`."""

    def __init__(self, book, budget=BUDGET_TOKENS, k=K):
        self.book, self.budget, self.k = book, budget, k

    def for_plan(self, *, map=None, age=None, at=None, targets=(), failed=(), cause=None, geom=None):
        """{items, tokens, ids}: the lessons for a planner call, best first.
        map      the map the planner plans on (the segment's, or Link's); without it only the cause can make an episode relevant
        age      'child' | 'adult' (a like age ranks higher)
        at       where Link is: [x, z], [x, y, z]
        targets  the places the planner is about to choose between: dicts with name, x and z (or `at`), or [x, z] pairs
        failed   what already failed in this run: names (a block's target is matched to them), places like the targets, or the places objectives ended stuck
        cause    one of tactics.CAUSES when the caller knows what stops Link
        geom     tactics.Sensor's bucketed geometry, when the caller has sensed one
        items are strings of at most 200 characters; tokens (rounded up) and ids (a short hash of each lesson's newest episode, aligned with items) are for the log."""
        try:
            return self._retrieve(map, age, at, targets, failed, cause, geom)
        except Exception as e:   # noqa: BLE001  lessons are an aid: a planner call goes on without them
            return self._none(e)

    def for_goals(self, seg, goals, tried=()):
        """What the goal-level planner knows (deciders.Planner.plan): the segment's map, its goals' open targets (the failed ones as what failed) and, in the steps tried, the
        points the recovery marked bad (the newest first). It is not told where Link is."""
        try:
            targets, failed = [], []
            for g in goals:
                if g.status == 'met':
                    continue
                for t in g.targets:
                    if t.status in ('done', 'dropped') or getattr(t, 'follow', None):   # (a target that moves has no place of its own)
                        continue
                    (failed if t.status == 'failed' else targets).append({'name': t.name, 'x': t.x, 'z': t.z})
            marked = [{'name': e.get('target'), 'at': e['at']} for e in reversed(list(tried)) if isinstance(e, dict) and e.get('result') == 'marked-bad' and e.get('at')]
            area = getattr(seg, 'area', None)
            return self._retrieve(area, tactics.age_of_map(area), None, targets, marked + failed, None, None)
        except Exception as e:   # noqa: BLE001
            return self._none(e)

    def for_chapter(self, link, timeline=()):
        """What the chapter planner knows (sections.ChapterPilot.ask_planner): `link`, its view of Link (area, age, pos), and the objectives so far (their records: the
        targets they went to and where they ended; the ones that were not met count as what failed)."""
        try:
            area, failed = link.get('area'), []
            for rec in list(timeline)[-8:]:
                if rec.get('goal_status') == 'met':
                    continue
                if rec.get('area') == area:
                    failed += [{'name': t.get('name'), 'at': t.get('at')} for t in rec.get('targets') or [] if isinstance(t, dict)]
                if rec.get('end_area') == area and rec.get('end_pos'):
                    failed.append({'at': rec['end_pos']})
            return self._retrieve(area, link.get('age'), link.get('pos'), (), failed, None, None)
        except Exception as e:   # noqa: BLE001
            return self._none(e)

    @staticmethod
    def _none(error=None):
        out = {'items': [], 'tokens': 0, 'ids': []}
        if error is not None:
            out['error'] = f'{type(error).__name__}: {error}'[:120]
        return out

    def _retrieve(self, map, age, at, targets, failed, cause, geom):
        rows = self.book.rows('block')
        if self.k <= 0 or self.budget <= 0 or not rows:
            return self._none()
        cause = cause if cause in tactics.CAUSES else None
        points, names = [], {}
        here = _xz(at) if at is not None else None
        if here:
            points.append((here[0], here[1], W_AT))
        for items, w in ((failed, W_FAILED), (targets, W_TARGET)):
            for p in items or ():
                if isinstance(p, str):
                    names[p] = max(names.get(p, 0.0), W_NAME * w)
                    continue
                xz = _xz(p)
                if xz:
                    points.append((xz[0], xz[1], w))
                if isinstance(p, dict) and isinstance(p.get('name'), str) and p['name']:
                    names[p['name']] = max(names.get(p['name'], 0.0), W_NAME * w)
        relevant = []
        for i, r in enumerate(rows):
            if not ((map and r.get('map') == map) or (cause and r.get('cause') == cause)):
                continue   # not this map, not this cause: no lesson however recent
            if not r.get('tried') and not r.get('worked') and r.get('how') == 'recovered':
                continue   # it cleared by itself: nothing to learn
            relevant.append((i, r))
        ranked = []
        for g in _fold(relevant):
            r = g['row']
            same_map = bool(map) and r.get('map') == map
            near = 0.0
            if same_map:
                if isinstance(r.get('target'), str):
                    near = names.get(r['target'], 0.0)
                xz = _xz(r.get('at'))
                if xz:
                    near = max([near] + [w / (1.0 + math.hypot(xz[0] - px, xz[1] - pz) / NEAR_M) for px, pz, w in points])
            like = ((1.0 if age and r.get('age') == age else 0.0) + (tactics.geom_similarity(geom, r['geom']) if geom and r.get('geom') else 0.0)) / 2.0
            score = (W_CAUSE * bool(cause and r.get('cause') == cause) + W_MAP * same_map + W_NEAR * near + W_LIKE * like + W_WORKED * bool(r.get('worked'))
                     + W_RECENT * (g['idx'] + 1) / len(rows))
            ranked.append((-score, -g['idx'], g))
        ranked.sort(key=lambda s: s[:2])   # (the library's position is unique: a total order)
        items, ids = [], []
        for _, _, g in ranked:
            if len(items) >= self.k:
                break
            text = _text(g['row'], g['n'])
            if tokens_of(items + [text]) <= self.budget:   # (one that does not fit: a shorter one after it still may)
                items.append(text)
                ids.append(_id(g['row']))
        return {'items': items, 'tokens': math.ceil(tokens_of(items)) if items else 0, 'ids': ids}
