#!/usr/bin/env python3
"""selfplay: the nightly self-play of the pilot's recovery ladder. No human recordings and no model: the pilot (rules decider) is put 8 to 10 m before a
place where earlier runs got stuck and walks into it, so that its ladder tries what has been tried little there (the `explore` order of the tactics
library: the same ranking plus an optimism bonus for the untried), and every attempt, every block and what finally worked is written into the Book by the
ladder itself, filed as source `selfplay`. The next night's ranking (and the lessons' source) is better by what this night found.

  plan     what to visit tonight, from the route library (open stuck clusters with a known `want`) and the Book (how little is known there), minus the places
           visited in the last nights (a small ledger): one SESSION per cluster = an approach point on the library's own track (a point runs really walked,
           9 m of path before the stuck point), a yaw toward the want, a save to make there, a generated segment (a `reach` goal at the want), the cluster's
           old tactics and ranking, the attempts to expect. Writes the plan folder (plan.json, segments, the Book's summary before). `--proven-saves NAME ...`: for
           each, one session on that saves-library entry exactly as it is (`start` null, no hs_make_save --start: that has never run in a game), the pilot's own first
           leg walking to the cluster's want; the plan says why. They come first and share --max-sessions with the --start ones.
  check    the refusals, nothing started (a missing save, a copy that is not warm or not stamped, a hold or session that is too long, spend over the caps,
           a segment that does not parse with pilot.Segment ...).
  saves    make the saves (hs_make_save.py: no game).
  run      inside the hold: the sessions one after another, each a `pilot.py run` (rules decider, no lessons, no planner) in its own process group, stopped by
           pid only; a row per session from its summary.json, transcript.jsonl and the attempts it wrote to the Book; the run imported into the route library;
           a table, result.json and the report. At most 1,100 s of wall in all, shutdown included. A session whose game never got to play is a row `no-gameplay`.
  queue    ONE waiter: the quiet lock, then the measuring lock, then `timeout` and `run`. Refuses a second waiter beside a live one. `stop` ends it by pid file.
  nightly  seed the Book from the new runs (tactics_seed), then plan, saves, check and queue in one call for the nightly job: idempotent per night id, refuses
           while a waiter of its own is queued or running or the night's spend is over its cap. It arms no timer; a scheduler (or Main) calls it.
  report   per cluster what was tried, what worked, and how the Book's ranking moved (the plan's snapshot against the Book now).

    selfplay.py plan --copy COPY [--lib L] [--tactics-dir D] [--root R] [--max-sessions 3] [--dry-run] ...
    selfplay.py check PLAN | saves PLAN | run PLAN --out DIR | queue PLAN [--dry-run] | stop PLAN | report PLAN | nightly --copy COPY ...

ROUTELIB_DIR is set for the pilot, as pilot.py wants it: it plans with the library's known way first and imports its own run into the library when it ends. A run it
could not import (stopped by pid, crashed) is imported here; the library skips a run it has. The pilot gets a bad-point memory of the hold's own: a place a run
already got past (`soft`) puts that fix first in the ladder, which would stop the untried from being tried, and the production memory should not be written by a
deliberate stress test.
Game-derived data (maps, coordinates, saves, the library) stays in the plan folder (<harness>/selfplay, outside the code and git); nothing here names a place.
Tests (a fake pilot and a made-up library): test_selfplay.py (python3 -I -B).
"""
import argparse
import collections
import datetime
import json
import math
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import recover  # noqa: E402
import routelib  # noqa: E402
import tactics  # noqa: E402

H = Path(os.environ.get('HS_HARNESS', str(HERE.parent.parent)))
SAVE_TOOL = H / 'tools' / 'hs_make_save.py'
SAVES_LIBRARY = H / 'saves'
FORMAT = 'ls-selfplay/1'
QUIET, MEASURING = os.environ.get('PILOT_QUIET_LOCK'), os.environ.get('PILOT_MEASURING_LOCK')   # the main lane's two lock files: this machine's own values, set by the environment, no default
SLOT_VARS = ('HSGATE_SLOT_DIR', 'HSGATE_INTEL_SLOT_DIR', 'HSGATE_SLOT_TEST', 'HSGATE_SLOT_NODESKTOP', 'HSGATE_IN_GATE')   # (the pilot starts the game through hs-run.sh, which applies the gate itself)
MODES = ('explore', 'ranked', 'fixed')

HOLD_MAX_S = 1100       # a hold, shutdown included: the main lane's limit
WALL_S, BUDGET_S = 270, 120   # a session: the game's wall (boot took 48 to 113 s in the pilot's runs) and the pilot's own game-time budget
TIMING = {'reserve_s': 60.0,    # the hold's sessions end this long before its timeout: the last import, the table, the report
          'tail_s': 30.0,       # the pilot's own wrap-up after the game's wall (summary, metrics)
          'soft_s': 15.0,       # then `end` into the live channel, and this long to end by itself
          'grace_s': 15.0,      # then SIGTERM to the pilot's process group, and this long before SIGKILL
          'term_soft_s': 4.0,   # the same two when the hold itself got SIGTERM (`timeout --kill-after=20`: no time for more)
          'term_grace_s': 4.0,
          'min_wall_s': 180.0}  # a session shorter than this would spend its wall on booting: not started
APPROACH_M, APPROACH_LEAST_M, APPROACH_MOST_M = 9.0, 5.0, 12.0   # the path metres before the stuck point: aimed at, least accepted, farthest looked at
APPROACH_MAX_DY = 3.5   # the approach is on the stuck point's floor (the cluster itself allows 3 m)
SAME_PLACE_M = tactics.CLUSTER_M
COOL_NIGHTS = 3
TOP_N = 8               # the rungs of the ladder that count in "how little is known"
SCARCE_N = 12.0         # a cause with this many attempts in the Book is half known
RUNS_FULL = 12          # a place that stopped this many runs has the full weight of impact
STRAIGHT_MISS_M = 1.5   # a visit runs straight at the want: the stuck point must lie within this far of the line from the approach point to the want
W_LEARN, W_IMPACT = 0.6, 0.4
DIVERSITY = 0.7         # a second cluster of the same cause on the same map tonight counts this much of its value
SEC_PER_RUNG = 8.0      # about this much game time for a rung of the ladder
NEVER_FLAG = 'PlayerStatus.MaxLife>=99999'   # the segment's flag condition: a goal needs one, and none of these visits is solved by a flag (no heart count comes near)
PROVEN_MAX_M, PROVEN_NEAR_M = 250.0, 150.0   # a proven save's cluster: within this straight-line distance of where the save starts; its value halves at the second


class PlanError(Exception):
    pass


class NothingToDo(PlanError):
    pass


def now_iso():
    return time.strftime('%Y-%m-%dT%H:%M:%S')


def default_root():
    d = os.environ.get('PILOT_SELFPLAY_DIR')
    return Path(d) if d else H / 'selfplay'   # (beside the harness's route library and tactics library: one ledger for every frozen copy of the code)


def default_lib():
    return Path(os.environ.get('ROUTELIB_DIR') or H / 'routelib')


def default_copy():
    return Path(os.environ['PILOT_COPY']) if os.environ.get('PILOT_COPY') else None   # (this machine's own folder: no default name)


def game_copy(a):
    copy = a.copy or default_copy()
    if not copy:
        raise PlanError('no game copy: --copy COPY or $PILOT_COPY (this machine\'s own folder; there is no default)')
    return str(Path(copy).resolve())


def night_id(s):
    try:
        datetime.date.fromisoformat(s)
    except (TypeError, ValueError):
        raise PlanError(f'a night id is a date, YYYY-MM-DD (got {s!r})') from None
    return s


def night_gap(a, b):
    return abs((datetime.date.fromisoformat(a) - datetime.date.fromisoformat(b)).days)


def near(a, b, r=SAME_PLACE_M):
    """Whether two [x, y, z] places are one place (as the Book's weights see it: within r metres and 3 m of height)."""
    return bool(a and b) and math.hypot(a[0] - b[0], a[2] - b[2]) <= r and abs(a[1] - b[1]) < 3.0


def jsonl(path):
    rows = []
    try:
        for ln in Path(path).read_text(errors='replace').splitlines():
            try:
                rows.append(json.loads(ln))
            except ValueError:
                pass
    except OSError:
        pass
    return rows


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None


# ------------------------------------------------------------------------------------------------------------------------ the ledger

class Ledger:
    """Which places were visited on which night, so consecutive nights spread over different clusters. One JSON line per fact: `planned` (a plan chose it; it
    counts for that night only, so a second plan of the same night picks others) and `visited` (a session played there; it counts for COOL_NIGHTS nights)."""

    def __init__(self, path):
        self.path = Path(path)
        self._rows = None

    def rows(self):
        if self._rows is None:
            self._rows = jsonl(self.path)
        return self._rows

    def add(self, **row):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, 'a') as f:
            f.write(json.dumps({'ts': now_iso(), **row}, separators=(',', ':')) + '\n')
        self._rows = None

    def cooled(self, map, at, night, cool_nights):
        """Why this place is not visited tonight, or None."""
        for r in self.rows():
            if r.get('map') != map or not near(r.get('at'), at):
                continue
            if r.get('kind') == 'visited' and night_gap(night, r['night']) < cool_nights:
                return f'visited on {r["night"]}'
            if r.get('kind') == 'planned' and r['night'] == night:
                return f'planned for tonight ({r.get("plan")})'
        return None


# ------------------------------------------------------------------------------------------------------------------------ choosing the clusters

def stuck_members(m, c):
    """The stuck records of a cluster (it keeps none: the library derives it from them)."""
    return [s for s in m.stuck if routelib.d2(s['at'], c['at']) <= 2 * routelib.CLUSTER_R and abs(s['at'][1] - c['at'][1]) <= 3.0]


def _walk_back(track, s):
    """(index of the stuck step's end on the track, [(path metres back to it, index)]) walking the track backwards, or None when the stuck point is not on it.
    The walk stops at a gap in the samples (not a walk) and where the height leaves the stuck point's floor."""
    pts, at = track['pts'], s['at']

    def off(k):
        return math.hypot(pts[k][1] - at[0], pts[k][3] - at[2])
    i = None
    if s.get('t') is not None:
        before = [k for k, p in enumerate(pts) if p[0] <= s['t'] + 0.5]
        i = before[-1] if before else None
    if i is None or off(i) > 3.0:
        i = min(range(len(pts)), key=off)
        if off(i) > 3.0:
            return None
    out, cum = [], 0.0
    for k in range(i, 0, -1):
        a, b = pts[k], pts[k - 1]
        seg = math.hypot(a[1] - b[1], a[3] - b[3])
        if seg > routelib.GAP_MAX or abs(b[2] - pts[i][2]) > APPROACH_MAX_DY:
            break
        cum += seg
        out.append((cum, k - 1))
        if cum > APPROACH_MOST_M:
            break
    return i, out


def approach_point(m, c):
    """(approach, why): a point the library's runs walked, about APPROACH_M of path before the stuck point, straight toward it, on its floor; or (None, why not).
    Never an invented point: the position is a track point as imported."""
    tracks = {t['id']: t for t in m.tracks}
    pool, why, longest = [], 'no stuck record of it has its track in the library', 0.0
    for s in stuck_members(m, c):
        t = tracks.get(s.get('track'))
        if t is None or not t.get('pts'):
            continue
        walked = _walk_back(t, s)
        if walked is None:
            why = 'its stuck point is not on the track it was recorded with'
            continue
        i, back = walked
        longest = max([longest] + [cum for cum, _k in back])
        pts = t['pts']
        for cum, k in back:
            if APPROACH_LEAST_M <= cum <= APPROACH_MOST_M:
                chord = math.hypot(pts[k][1] - pts[i][1], pts[k][3] - pts[i][3])
                straight = chord / cum
                pool.append((abs(cum - APPROACH_M) + 4.0 * (1.0 - straight), cum, straight, t, k, i))
    if not pool:
        return None, (why if longest == 0.0 and why.startswith('its') else f'the library\'s tracks give it {longest:.1f} m of walk before the stuck point (at least {APPROACH_LEAST_M:g} m wanted)')
    _score, cum, straight, t, k, i = min(pool, key=lambda p: (p[0], p[3]['id'], p[4]))
    p = t['pts'][k]
    return {'pos': [p[1], p[2], p[3]], 'approach_m': round(cum, 1), 'straight': round(straight, 2), 'run': t['run'], 'track': t['id'], 'age': t.get('age')}, None


def yaw_toward(frm, to):
    """The save tool's yaw (radians, 0 = +z, 90 degrees = +x) from a [x, y, z] to an (x, z)."""
    return math.atan2(to[0] - frm[0], to[1] - frm[2])


def place_attempts(book):
    return [(r['map'], r['at'], r['tactic']) for r in book.rows('attempt') if r['outcome'] != 'neutral' and r.get('map') and r.get('at')]


def rank_rows(book, cause, *, map=None, age=None, at=None, explore=False):
    out = []
    for r in book.rank(cause, map=map, age=age, at=at, explore=explore):
        row = {'tactic': r['tactic'], 'score': round(r['score'], 4), 'n': r['n'], 'wins': r['wins']}
        if explore:
            row['ucb'] = round(r['ucb'], 4)
        out.append(row)
    return out


def value_of(c, book, map, age, attempts):
    """How much a visit to this cluster is worth: what it would teach (the rungs of its ladder that were never tried at this place, never tried for this
    cause, how few attempts the cause has in the Book at all) and how much the place hurts (runs it stopped). Returns (value, parts)."""
    cause = c['cause']
    rank = book.rank(cause, map=map, age=age, at=c['at'], explore=True)
    top = rank[:TOP_N]
    here = collections.Counter(t for mp, at, t in attempts if mp == map and near(at, c['at']))
    n_cause = sum(v['n'] for v in book.counts(cause).values())
    untried_here = sum(1 for r in top if not here[r['tactic']]) / len(top) if top else 1.0
    untried_cause = sum(1 for r in top if not r['n']) / len(top) if top else 1.0
    scarcity = 1.0 / (1.0 + n_cause / SCARCE_N)
    learn = 0.4 * untried_here + 0.3 * untried_cause + 0.3 * scarcity
    runs = len(c['runs'])
    impact = min(1.0, math.log2(1 + runs) / math.log2(1 + RUNS_FULL))
    parts = {'learn': round(learn, 3), 'impact': round(impact, 3), 'untried_here': round(untried_here, 3), 'untried_cause': round(untried_cause, 3),
             'scarcity': round(scarcity, 3), 'runs': runs, 'stops': c['n'], 'cause_attempts': n_cause, 'attempts_here': sum(here.values())}
    return W_LEARN * learn + W_IMPACT * impact, parts


def cluster_age(m, c):
    """The age of a cluster: of the track one of its stuck records was made on, else what the map's name says."""
    tracks = {t['id']: t for t in m.tracks}
    for s in stuck_members(m, c):
        t = tracks.get(s.get('track'))
        if t and t.get('age') in ('child', 'adult'):
            return t['age']
    return tactics.age_of_map(m.name)


def candidates(lib, book, ledger, night, *, cool_nights=COOL_NIGHTS, ignore_ledger=False):
    """([{map, cluster, c, value, parts, approach, no_approach, age, cooled}], [{map, cluster, why}]): every open cluster with a want and an age, valued; and the ones that
    cannot be visited at all, with why. `approach` is None where no approach point can be made on the library's tracks (`no_approach` says why): such a cluster can be visited
    from a library save only. A cluster visited lately is kept with `cooled` (a proof run may still ask for it)."""
    out, skipped = [], []
    attempts = place_attempts(book)
    for mp in lib.maps():
        m = lib.map(mp)
        for c in m.clusters():
            def skip(why, c=c, mp=mp):
                skipped.append({'map': mp, 'cluster': c['id'], 'why': why})
            if c['resolved']:
                skip('resolved')
                continue
            if not (isinstance(c.get('want'), (list, tuple)) and len(c['want']) == 2):
                skip('no want')
                continue
            ap, why = approach_point(m, c)
            if ap:
                miss = tactics.seg_dist((c['at'][0], c['at'][2]), (ap['pos'][0], ap['pos'][2]), tuple(c['want']))[0]
                if miss > STRAIGHT_MISS_M:   # (the visit runs straight at the want: a stuck point the line misses is walked past, as hold 1's three visits did)
                    ap, why = None, f'the straight run from the approach to its want passes {miss:.1f} m from the stuck point (more than {STRAIGHT_MISS_M:g} m)'
            age = (ap or {}).get('age') or cluster_age(m, c)
            if age not in ('child', 'adult'):
                skip('age unknown')
                continue
            value, parts = value_of(c, book, mp, age, attempts)
            out.append({'map': mp, 'cluster': c['id'], 'c': c, 'value': value, 'parts': parts, 'approach': ap, 'no_approach': why, 'age': age,
                        'cooled': None if ignore_ledger else ledger.cooled(mp, c['at'], night, cool_nights)})
    return out, skipped


def pick(cands, k, forced=()):
    """The clusters of tonight, in order: the forced ones (`--only`) first, then the best by value, each further one of a (map, cause) already chosen counting
    DIVERSITY times less. Cooled clusters are not chosen on their own. Returns [(candidate, mode or None)]."""
    chosen = []
    for mp, cid, mode in forced:
        c = next((c for c in cands if c['map'] == mp and c['cluster'] == cid), None)
        if c is None:
            raise PlanError(f'--only {mp}:{cid}: not an open cluster with a want and an approach on the library\'s tracks')
        chosen.append((c, mode))
    seen = collections.Counter((c['map'], c['c']['cause']) for c, _m in chosen)
    pool = [c for c in cands if not c['cooled'] and all(c is not f for f, _m in chosen)]
    while len(chosen) < k and pool:
        best = min(pool, key=lambda c: (-c['value'] * DIVERSITY ** seen[(c['map'], c['c']['cause'])], -c['parts']['runs'], c['map'], c['cluster']))
        pool.remove(best)
        seen[(best['map'], best['c']['cause'])] += 1
        chosen.append((best, None))
    return chosen


def library_entry(library, name):
    """Where a saves-library entry starts, from its .entry.json (the newest slot that loads): {name, path, area, age, pos, proof}. The caller names the entries it
    has proven in a game; `proof` is the first proof note the library keeps for it (None: it keeps none)."""
    path = Path(library) / name
    try:
        e = json.loads((path / '.entry.json').read_text())
        slots = [s for s in e['decoded']['slots'] if s.get('status') == 'ok' and s.get('area') and s.get('pos') and s.get('age') in ('child', 'adult')]
        slot = next((s for s in slots if s['slot'] == e['decoded'].get('newest')), slots[0])
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        raise PlanError(f'--proven-saves {name}: {path} is no saves-library entry (no .entry.json with a slot that loads)') from None
    if not (path / 'save').is_dir():
        raise PlanError(f'--proven-saves {name}: {path} has no save/ folder')
    return {'name': name, 'path': str(path.resolve()), 'area': slot['area'], 'age': slot['age'], 'pos': slot['pos'], 'proof': (e.get('proven') or [None])[0]}


def pick_proven(cands, entries, taken=()):
    """One cluster for each proven save (in the order given): the best by value, discounted by the straight-line distance from where the save starts (the pilot's own
    first leg has to walk it), among the open clusters on the save's map and age within PROVEN_MAX_M of it. ([(entry, candidate, metres)], [notes of the saves that found no
    cluster])."""
    out, notes, used = [], [], list(taken)
    for e in entries:
        pool = []
        for c in cands:
            d = math.hypot(c['c']['at'][0] - e['pos'][0], c['c']['at'][2] - e['pos'][2])
            if c['map'] == e['area'] and c['age'] == e['age'] and not c['cooled'] and not any(c is u for u in used) and d <= PROVEN_MAX_M:
                pool.append((c['value'] / (1.0 + d / PROVEN_NEAR_M), d, c))
        if not pool:
            notes.append(f'proven save {e["name"]} ({e["area"]}, {e["age"]}): no open cluster within {PROVEN_MAX_M:.0f} m of where it starts')
            continue
        _v, d, c = min(pool, key=lambda p: (-p[0], p[2]['cluster']))
        used.append(c)
        out.append((e, c, d))
    return out, notes


def expected_attempts(cause, mode, book, budget_s):
    """The rungs a visit should get through: the ladder's length for the mode, the cause's tactics, and the game time (a rung takes about SEC_PER_RUNG s)."""
    cfg = recover.Config()
    if mode == 'fixed':
        names = [n for n in recover.LADDER if n != 'replan']
    else:
        names = list(tactics.ORDER.get(cause, tactics.ORDER['unknown'])) + [d['id'] for d in book.demos(cause)]
    cap = cfg.explore_rungs if mode == 'explore' else cfg.rungs_max
    return max(1, min(len(set(names)), cap, int((budget_s - 20) // SEC_PER_RUNG)))


# ------------------------------------------------------------------------------------------------------------------------ segments and sessions

def segment_text(name, night, area, want, save, wall, budget_s, max_decisions=40, radius=2.0):
    """The pilot segment of a visit: a `reach` goal at the cluster's want, humanize 0, from the generated save. A reach goal needs a flag; this one never
    comes true, so the visit ends by its target (reached or failed) or its budget."""
    return '\n'.join([
        f'# generated by selfplay.py for night {night}: a visit to a known stuck place (private: game data)',
        f'name = {json.dumps(name)}',
        'what = "walk to a place that earlier runs could not reach, so that the recovery ladder tries what has been tried little there"',
        f'area = {json.dumps(area)}',
        f'save = {json.dumps(str(save))}',
        'boot = "continue"',
        'humanize = 0',
        'straight = true',   # no offline planner: the visit runs straight at the want, as the runs that were stopped there did (the first hold's plans routed round every block: 0 blocks in 3 visits)
        f'wall = {int(wall)}',
        f'budget_seconds = {int(budget_s)}',
        f'max_decisions = {int(max_decisions)}',
        'watch = []',
        '',
        '[[goal]]',
        'name = "reach-want"',
        'what = "You are Link. Walk to the point ahead; when the way is shut, step back or aside, and try again."',
        f'flag = "{NEVER_FLAG}"',
        'kind = "reach"',
        f'targets = [{{name = "want", at = [{want[0]:.2f}, {want[1]:.2f}], kind = "reach", radius = {radius:g}}}]',
        ''])


def book_before(book, plan_sessions):
    """The Book as planned: its summary, and the production ranking of every cause (the report diffs against it)."""
    causes = sorted({s['cause'] for s in plan_sessions} | set(tactics.CAUSES))
    return {'format': FORMAT, 'taken': now_iso(), 'dir': str(book.dir), 'rows': {k: len(book.rows(k)) for k in ('attempt', 'block', 'demo')},
            'summary': book.summary(), 'ranks': {c: rank_rows(book, c) for c in causes}}


def build_plan(a):
    """(plan, notes, segments {path: text}): the whole plan from the library, the Book and the ledger; reads only."""
    night = night_id(a.night or time.strftime('%Y-%m-%d'))
    lib = routelib.RouteLib(Path(a.lib or default_lib()).resolve())
    if not lib.maps():
        raise PlanError(f'the route library {lib.root} has no maps')
    book = tactics.Book(Path(a.tactics_dir).resolve() if a.tactics_dir else tactics.default_dir().resolve(), readonly=True)
    root = Path(a.root or default_root()).resolve()
    ledger = Ledger(Path(a.ledger).resolve() if a.ledger else root / 'ledger.jsonl')
    name = a.plan_name or f'SelfPlay-{night}'
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', name):
        raise PlanError(f'a plan name is letters, digits and _.- (got {name!r})')
    folder = root / name
    t = dict(TIMING)
    overhead = t['tail_s'] + t['soft_s'] + t['grace_s'] + 10.0
    hold = int(a.hold_seconds)
    wall, budget = int(a.wall), int(a.budget_s)
    if hold > HOLD_MAX_S:
        raise PlanError(f'a hold is at most {HOLD_MAX_S} s, shutdown included (asked for {hold})')
    fit = int((hold - t['reserve_s']) // (wall + overhead))
    forced = []
    for spec in a.only or []:
        ref, _, mode = spec.partition('=')
        mp, _, cid = ref.rpartition(':')
        if not mp or not cid or (mode and mode not in MODES):
            raise PlanError(f'--only MAP:CLUSTER[=MODE] (mode one of {", ".join(MODES)}), got {spec!r}')
        forced.append((mp, cid, mode or None))
    if wall < t['min_wall_s']:
        raise PlanError(f'a session wall of {wall} s is under the {t["min_wall_s"]:.0f} s a boot (48 to 113 s in the pilot\'s runs) and a visit need')
    if fit < 1:
        raise PlanError(f'a hold of {hold} s has no room for one session of {wall} s (+{overhead:.0f} s to end it, {t["reserve_s"]:.0f} s reserve)')
    if len(forced) > fit:
        raise PlanError(f'{len(forced)} sessions of {wall} s (+{overhead:.0f} s each to end them) do not fit a hold of {hold} s ({fit} do)')
    saves_library = Path(a.saves_library or SAVES_LIBRARY)
    entries = [library_entry(saves_library, n) for n in a.proven_saves or []]
    total = max(len(forced), min(int(a.max_sessions), fit))
    cands, skipped = candidates(lib, book, ledger, night, cool_nights=int(a.cool_nights), ignore_ledger=bool(a.ignore_ledger))
    startable = [c for c in cands if c['approach']]
    n_clusters = len(cands) + len(skipped)
    skipped += [{'map': c['map'], 'cluster': c['cluster'], 'why': f'no approach: {c["no_approach"]}'} for c in cands if not c['approach']]
    proven, proven_notes = pick_proven(cands, entries, taken=[c for c in cands if any(c['map'] == mp and c['cluster'] == cid for mp, cid, _m in forced)])
    proven_notes += [f'proven save {e["name"]}: the library keeps no proof note for it (named as proven by the caller)' for e in entries if not e['proof']]
    proven = proven[:max(0, min(total, fit - len(forced)))]   # (the proven saves' sessions come first; --only ones are never pushed out)
    chosen = [{'c': c, 'mode': a.mode, 'entry': e, 'metres': d} for e, c, d in proven]
    left = [c for c in startable if not any(c is x['c'] for x in chosen)]
    chosen += [{'c': c, 'mode': m or a.mode, 'entry': None, 'metres': None} for c, m in pick(left, max(len(forced), total - len(chosen)), forced)]
    if not chosen:
        raise NothingToDo(f'nothing to visit: {len(skipped)} clusters cannot be visited ({", ".join(f"{n} {w}" for w, n in collections.Counter(s["why"].split(":")[0] for s in skipped).most_common())})'
                          + (f'; {sum(1 for c in cands if c["cooled"])} were visited lately' if cands else '') + ''.join(f'; {n}' for n in proven_notes))
    code = Path(a.code or HERE.parent).resolve()
    pilot = Path(a.pilot).resolve() if a.pilot else code / 'pilot' / 'pilot.py'
    saves_dir = Path(a.saves_dir or folder / 'saves').resolve()
    world = default_world(a)
    base = {'child': a.base_child, 'adult': a.base_adult}
    sessions, segments, attempts = [], {}, place_attempts(book)
    for i, item in enumerate(chosen, 1):
        c, mode, entry = item['c'], item['mode'], item['entry']
        cl, ap = c['c'], c['approach']
        want = [float(cl['want'][0]), float(cl['want'][1])]
        radius = round(max(0.5, min(2.0, 0.6 * math.hypot(want[0] - cl['at'][0], want[1] - cl['at'][2]))), 2)   # (smaller than the gap the runs were stopped short by: a visit must not end "reached" at the stuck point)
        tag = f'{name}-{i}'
        seg_path = folder / 'segments' / f'{tag}.toml'
        if entry:   # a proven library save as it is: no --start, the pilot's own first leg walks to the want, which may be far: more game time for it
            save, base_save, sbudget = Path(entry['path']), None, int(max(budget, min(item['metres'] / 3.0 + 80.0, wall - 120)))
            start = None
            why = (f'the library save {entry["name"]} is used as it is, with no --start: hs_make_save --start has not been run in a game yet, and this save has been; '
                   f'the pilot\'s own first leg walks the {item["metres"]:.0f} m from where it starts to the want')
            proof = {'save': entry['name'], 'area': entry['area'], 'age': entry['age'], 'pos': entry['pos'], 'metres': round(item['metres'], 1), 'proof': entry['proof']}
        else:
            save, base_save, sbudget, why, proof = saves_dir / tag, base[c['age']], budget, None, None
            yaw = yaw_toward(ap['pos'], want)
            start = {'pos': ap['pos'], 'yaw': round(yaw, 3), 'yaw_deg': round(math.degrees(yaw), 1), 'approach_m': ap['approach_m'], 'straight': ap['straight'], 'from_run': ap['run'], 'track': ap['track']}
        segments[str(seg_path)] = segment_text(tag, night, c['map'], want, save, wall, sbudget, radius=radius)
        rank = rank_rows(book, cl['cause'], map=c['map'], age=c['age'], at=cl['at'], explore=True)
        here = collections.Counter(t_ for mp, at, t_ in attempts if mp == c['map'] and near(at, cl['at']))
        sessions.append({
            'name': tag, 'tag': tag, 'cluster': cl['id'], 'map': c['map'], 'age': c['age'], 'cause': cl['cause'], 'mode': mode,
            'value': {'score': round(c['value'], 4), **c['parts']},
            'old': {'library_tried': list(cl['tried']), 'library_worked': list(cl['worked']), 'library_causes': dict(cl['causes']), 'attempts_here': dict(here),
                    'ranking': rank[:TOP_N], 'production': rank_rows(book, cl['cause'], map=c['map'], age=c['age'], at=cl['at']),
                    'untried_here': [r['tactic'] for r in rank[:TOP_N] if not here[r['tactic']]]},
            'expected_attempts': expected_attempts(cl['cause'], mode, book, sbudget),
            'at': [round(v, 2) for v in cl['at']],
            'target': {'want': want, 'radius': radius}, 'start': start, 'start_why': why, 'proven': proof,
            'save_name': save.name, 'save': str(save), 'base_save': base_save, 'time': 'day',
            'segment': str(seg_path), 'wall': wall, 'budget_s': sbudget})
    plan = {'format': FORMAT, 'name': name, 'night': night, 'created': now_iso(), 'dir': str(folder), 'root': str(root), 'ledger': str(ledger.path),
            'lib': str(lib.root), 'tactics_dir': str(book.dir), 'world': world, 'copy': game_copy(a),
            'code': str(code), 'pilot': str(pilot), 'save_tool': str(a.save_tool or SAVE_TOOL), 'saves_library': str(saves_library),
            'saves_dir': str(saves_dir), 'bad_points': str(folder / 'bad-points'), 'base_saves': base, 'proven_saves': list(a.proven_saves or []), 'proven_notes': proven_notes,
            'hold_seconds': hold, 'timing': {**t, 'overhead_s': overhead},
            'model': None, 'spend': {'caps': a.caps, 'ledger': a.spend_ledger} if a.caps or a.spend_ledger else None, 'book_before': str(folder / 'book-before.json'),
            'considered': {'clusters': n_clusters, 'eligible': len(startable), 'cooled': sum(1 for c in startable if c['cooled']),
                           'skipped': dict(collections.Counter(s['why'].split(':')[0] for s in skipped))},
            'sessions': sessions}
    notes = {'skipped': skipped, 'ranked': sorted(startable, key=lambda c: -c['value']), 'fit': fit}
    return plan, notes, segments


def write_plan(plan, segments, book):
    """The plan folder: plan.json, the segments, the Book as it is, and a `planned` ledger row per session."""
    folder = Path(plan['dir'])
    if (folder / 'plan.json').exists():
        raise PlanError(f'{folder / "plan.json"} exists: a plan is written once (the same night id makes the same plan folder)')
    (folder / 'segments').mkdir(parents=True, exist_ok=True)
    for path, text in segments.items():
        Path(path).write_text(text)
    Path(plan['book_before']).write_text(json.dumps(book_before(book, plan['sessions']), indent=1))
    (folder / 'plan.json').write_text(json.dumps(plan, indent=1))
    led = Ledger(plan['ledger'])   # (after the plan: a plan that was not written must not use up a cluster)
    for s in plan['sessions']:
        led.add(kind='planned', night=plan['night'], plan=plan['name'], map=s['map'], cluster=s['cluster'], at=s['at'], cause=s['cause'], tag=s['tag'])


def print_plan(plan, notes):
    print(f'plan {plan["name"]}: night {plan["night"]}, {len(plan["sessions"])} sessions, hold {plan["hold_seconds"]} s (room for {notes["fit"]} of {plan["sessions"][0]["wall"]} s)')
    c = plan['considered']
    print(f'  {c["clusters"]} clusters: {c["eligible"]} can be visited ({c["cooled"]} visited lately), cannot: {c["skipped"] or "none"}')
    for s in plan['sessions']:
        v, o, st = s['value'], s['old'], s['start']
        how = f'approach {st["approach_m"]} m of path at yaw {st["yaw_deg"]} deg' if st else f'proven save {s["proven"]["save"]}, {s["proven"]["metres"]:.0f} m from the want, no --start'
        print(f'  {s["name"]}: {s["map"]} {s["cluster"]} ({s["cause"]}) mode {s["mode"]}, value {v["score"]:.3f} (learn {v["learn"]:.2f}, impact {v["impact"]:.2f}; {v["runs"]} runs, '
              f'{v["stops"]} stops, {v["cause_attempts"]} attempts of the cause in the Book, {v["attempts_here"]} here), {how}, '
              f'{s["age"]}, expects {s["expected_attempts"]} attempts')
        print(f'      the library tried {o["library_tried"] or "nothing"}; the explore order starts {[r["tactic"] for r in o["ranking"][:5]]}; untried here {o["untried_here"]}')
    for n in plan['proven_notes']:
        print('  ' + n)
    left = [c for c in notes['ranked'] if not any(c['map'] == s['map'] and c['cluster'] == s['cluster'] for s in plan['sessions'])]
    if left:
        print('  next in line: ' + ', '.join(f'{c["map"]} {c["cluster"]} ({c["c"]["cause"]}, {c["value"]:.3f}{", " + c["cooled"] if c["cooled"] else ""})' for c in left[:5]))


# ------------------------------------------------------------------------------------------------------------------------ the plan file and its refusals

def load_plan(path):
    path = Path(path)
    if path.is_dir():
        path = path / 'plan.json'
    try:
        p = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        raise PlanError(f'{path}: {e}') from None
    p['plan_path'] = str(path)
    p.setdefault('sessions', [])
    p.setdefault('hold_seconds', HOLD_MAX_S)
    p['timing'] = {**TIMING, 'overhead_s': TIMING['tail_s'] + TIMING['soft_s'] + TIMING['grace_s'] + 10.0, **p.get('timing', {})}
    return p


def copy_errors(copy):
    """A copy that has not been prepared (its shader caches built: `*_prepared.bin` in the copy or in its `cache/` folder, where the game writes it) would spend a session's
    wall on shaders; one without a source stamp (built-from.txt, or regress-source.txt) cannot be told from another build in the library."""
    copy = Path(copy)
    if not copy.is_dir():
        return [f'copy {copy} is not a folder']
    errs = []
    stamps = [copy / n for n in ('built-from.txt', 'regress-source.txt') if (copy / n).is_file()]
    first = stamps[0].read_text().split() if stamps else []
    if not first or not re.fullmatch(r'[0-9a-fA-F]{7,64}', first[0]):
        errs.append(f'copy {copy} is not stamped: no built-from.txt (or regress-source.txt) that starts with the commit it was built from')
    if not any(p.stat().st_size > 0 for p in list(copy.glob('*_prepared.bin')) + list((copy / 'cache').glob('*_prepared.bin'))):
        errs.append(f'copy {copy} is not warm: no *_prepared.bin (run hs-run.sh --prepare on it once: a session would spend its wall on shaders)')
    return errs


def spend_errors(spend=None):
    """The night's ledger against the caps: refuse when the night (or the total) is already at its cap. The visits spend nothing; a night already over its cap
    should not start a hold in it. `spend` {caps, ledger}: the files to read (default: the pilot's caps.json and ledger.jsonl, as openai_api.spent() counts them)."""
    try:
        import openai_api
    except ImportError as e:
        return [f'the spend ledger cannot be read (openai_api: {e})']
    spend = spend or {}
    caps, ledger = Path(spend.get('caps') or openai_api.CAPS), Path(spend.get('ledger') or openai_api.LEDGER)
    try:
        c = json.loads(caps.read_text())
        per_night, total_cap = float(c['per_night_usd']), float(c['total_usd'])
    except (OSError, ValueError, KeyError, TypeError):
        return [f'no readable caps file {caps} (per_night_usd and total_usd): no hold is started without one']
    start = openai_api.window_start(datetime.datetime.now()).timestamp()
    rows = openai_api.ledger_rows(ledger)
    night = sum(float(r.get('cost_usd') or 0) for r in rows if r.get('ts', 0) >= start)
    total = sum(float(r.get('cost_usd') or 0) for r in rows)
    errs = []
    if night >= per_night:
        errs.append(f'the night\'s spend ({night:.2f} USD) is at its cap ({per_night:.2f} USD)')
    if total >= total_cap:
        errs.append(f'the total spend ({total:.2f} USD) is at its cap ({total_cap:.2f} USD)')
    return errs


def segment_errors(plan, s):
    try:
        import pilot
    except Exception as e:   # noqa: BLE001  (an import that fails for any reason is a refusal, not a crash)
        return [f'pilot.py cannot be imported to parse the segments ({type(e).__name__}: {e})']
    try:
        seg = pilot.Segment(s['segment'])
    except Exception as e:   # noqa: BLE001
        return [f'session {s.get("name")}: the segment {s["segment"]} does not parse with pilot.Segment ({type(e).__name__}: {e})']
    errs = []
    if seg.area != s['map']:
        errs.append(f'session {s["name"]}: the segment is on {seg.area}, the session on {s["map"]}')
    if seg.humanize != 0:
        errs.append(f'session {s["name"]}: the segment is not humanize 0')
    if len(seg.goals) != 1 or len(seg.goals[0].targets) != 1 or seg.goals[0].kind != 'reach':
        errs.append(f'session {s["name"]}: the segment is not one reach goal with one target')
    elif max(abs(seg.goals[0].targets[0].x - s['target']['want'][0]), abs(seg.goals[0].targets[0].z - s['target']['want'][1])) > 0.006:
        errs.append(f'session {s["name"]}: the segment\'s target is not the cluster\'s want')
    elif abs(seg.goals[0].targets[0].radius - s['target']['radius']) > 0.006:
        errs.append(f'session {s["name"]}: the segment\'s target radius is not the session\'s')
    if seg.save != s['save']:
        errs.append(f'session {s["name"]}: the segment\'s save is not the session\'s')
    return errs


def plan_errors(plan, out=None):
    """The refusals of `check` (and of `run`, `queue`): everything that would waste the hold, found before anything starts."""
    errs = []
    t = plan['timing']
    hold = plan['hold_seconds']
    if hold > HOLD_MAX_S:
        errs.append(f'the hold is {hold} s: at most {HOLD_MAX_S} s, shutdown included')
    if not plan['sessions']:
        errs.append('the plan has no sessions')
    if plan.get('model') is not None:
        errs.append('the plan names a model: self-play spends nothing (rules decider)')
    room = hold - t['reserve_s']
    total = 0.0
    names, tags = set(), set()
    for s in plan['sessions']:
        for k in ('name', 'tag', 'cluster', 'map', 'cause', 'mode', 'save', 'segment', 'wall', 'target', 'start', 'age'):
            if k not in s:
                errs.append(f'session {s.get("name")}: {k} is missing')
        if s.get('mode') not in MODES:
            errs.append(f'session {s.get("name")}: mode {s.get("mode")!r} is none of {", ".join(MODES)}')
        if s.get('name') in names or s.get('tag') in tags:
            errs.append(f'duplicate session name or tag {s.get("name")}')
        names.add(s.get('name'))
        tags.add(s.get('tag'))
        wall = float(s.get('wall', 0))
        if wall < t['min_wall_s']:
            errs.append(f'session {s.get("name")}: a wall of {wall:.0f} s is under the {t["min_wall_s"]:.0f} s a boot and a visit need')
        if wall + t['overhead_s'] > room:
            errs.append(f'session {s.get("name")}: a wall of {wall:.0f} s (+{t["overhead_s"]:.0f} s to end it) is longer than the hold has ({room:.0f} s)')
        total += wall + t['overhead_s']
        if s.get('save') and not (Path(s['save']) / 'save').is_dir():
            errs.append(f'session {s.get("name")}: save {s["save"]} is not a game user folder (save/<user id>/ inside it)' + ('' if s.get('start') is None else ': selfplay.py saves makes it'))
        if s.get('start') is not None and not (Path(plan.get('saves_library', SAVES_LIBRARY)) / str(s.get('base_save'))).is_dir():
            errs.append(f'session {s.get("name")}: the base save {s.get("base_save")} is not in the saves library')
        if s.get('segment') and not Path(s['segment']).is_file():
            errs.append(f'session {s.get("name")}: segment {s["segment"]} is missing')
        elif s.get('segment') and 'target' in s:
            errs += segment_errors(plan, s)
        run_dir = Path(plan['pilot']).parent / 'runs' / str(s.get('tag'))
        if run_dir.exists():
            errs.append(f'session {s.get("name")}: the pilot already has a run folder {run_dir} (a tag is used once)')
    if total > room:
        errs.append(f'the sessions need {total:.0f} s with the time to end them; the hold has {room:.0f} s after its {t["reserve_s"]:.0f} s reserve: they do not fit')
    errs += copy_errors(plan['copy'])
    for k in ('pilot', 'save_tool'):
        if not Path(plan.get(k, '')).is_file():
            errs.append(f'{k} {plan.get(k)} is not a file')
    try:
        lib = routelib.RouteLib(plan['lib'])
        if not lib.maps():
            errs.append(f'the route library {plan["lib"]} has no maps')
    except (KeyError, routelib.LibError) as e:
        errs.append(f'library: {e}')
    if not Path(plan.get('book_before', '')).is_file():
        errs.append('the Book snapshot of the plan is missing (book-before.json): the report would have nothing to diff against')
    errs += spend_errors(plan.get('spend'))
    if out is not None and Path(out).exists():
        errs.append(f'{out} exists (a hold writes a new folder)')
    return errs


# ------------------------------------------------------------------------------------------------------------------------ the saves

def save_command(plan, s):
    """The hs_make_save command of a session that starts at an approach point: the base save moved there (map:x,y,z,yaw radians), the age, the time of day. None for a session
    on a proven library save as it is."""
    if s['start'] is None:
        return None
    p = s['start']['pos']
    return [sys.executable, str(plan.get('save_tool') or SAVE_TOOL), '--from', s['base_save'], '--out', str(s['save']),
            '--start', f'{s["map"]}:{p[0]:.2f},{p[1]:.2f},{p[2]:.2f},{s["start"]["yaw"]:.3f}', '--age', s['age'], '--time', s.get('time', 'day'), '--game', str(plan['copy'])]


def make_saves(plan, log=print):
    for s in plan['sessions']:
        if s['start'] is None:
            log(f'{s["name"]}: the proven library save {s["save"]} is used as it is: nothing to make')
            continue
        if Path(s['save']).exists():
            log(f'{s["name"]}: {s["save"]} exists, kept')
            continue
        cmd = save_command(plan, s)
        log(' '.join(shlex.quote(c) for c in cmd))
        Path(s['save']).parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        log((r.stdout[-600:] + r.stderr[-600:]).strip())
        if r.returncode:
            log(f'{s["name"]}: hs_make_save failed ({r.returncode})')
            return r.returncode
    return 0


# ------------------------------------------------------------------------------------------------------------------------ one session

def pilot_command(plan, s, wall):
    """The pilot's run of a session: the rules decider (no model), no lessons, the tactics library in the session's mode filed as selfplay, a bad-point memory of the
    hold's own. No planner, no vision: nothing here can spend."""
    return [sys.executable, '-I', '-B', plan['pilot'], 'run', s['segment'], '--decider', 'rules', '--tag', s['tag'], '--copy', plan['copy'], '--save', s['save'],
            '--wall', str(int(wall)), '--humanize', '0', '--tactics', s['mode'], '--tactics-source', 'selfplay', '--tactics-dir', plan['tactics_dir'], '--lessons', 'off',
            '--bad-points', plan['bad_points']]


def child_env(env=None, lib=None):
    """The pilot's environment: the gate's slot variables and every test or bypass of it unset (hs-run.sh applies the gate), no key (nothing can be asked of a model),
    ROUTELIB_DIR the plan's library (the pilot imports its own run at its end)."""
    e = dict(os.environ if env is None else env)
    for k in SLOT_VARS + ('OPENAI_API_KEY', 'ROUTELIB_DIR'):
        e.pop(k, None)
    if lib:
        e['ROUTELIB_DIR'] = str(lib)
    return e


def _wait(proc, seconds):
    end = time.monotonic() + seconds
    while proc.poll() is None:
        left = end - time.monotonic()
        if left <= 0:
            return False
        try:
            proc.wait(timeout=min(0.2, left))
        except subprocess.TimeoutExpired:
            pass
    return True


def _signal_group(proc, sig):
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, sig)   # (the pilot is its own session: its group is its pid)
        except (ProcessLookupError, PermissionError):
            pass


def _stat_fields(pid):
    """(ppid, start time) of a process from /proc/<pid>/stat, or None when it is gone. The start time tells a process from a later one with the same number."""
    try:
        f = Path(f'/proc/{pid}/stat').read_text().rpartition(')')[2].split()
        return int(f[1]), int(f[19])
    except (OSError, ValueError, IndexError):
        return None


def descendants(pid):
    """[(pid, start time)] of everything below a process (the ppid links of /proc). The pilot starts hsap in a session of its own, and hs-run.sh and the game hang below
    that: a pilot that is killed leaves them running until the game's wall, so they are listed before anything is sent."""
    kids, started = collections.defaultdict(list), {}
    for p in Path('/proc').iterdir():
        st = _stat_fields(int(p.name)) if p.name.isdigit() else None
        if st:
            kids[st[0]].append(int(p.name))
            started[int(p.name)] = st[1]
    out, todo = [], [pid]
    while todo:
        for c in kids.get(todo.pop(), []):
            out.append((c, started[c]))
            todo.append(c)
    return out


def stop_leftovers(left, grace_s):
    """SIGTERM, then SIGKILL after grace_s, to the processes of a descendants() snapshot that are still alive (by pid and start time, never by name). The number
    of them that had to be stopped."""
    def live():
        return [p for p, born in left if (_stat_fields(p) or (0, None))[1] == born and not _zombie(p)]
    n = len(live())
    for sig, wait in ((signal.SIGTERM, grace_s), (signal.SIGKILL, 2.0)):
        pids = live()
        if not pids:
            break
        for p in pids:
            try:
                os.kill(p, sig)
            except (ProcessLookupError, PermissionError):
                pass
        end = time.monotonic() + wait
        while live() and time.monotonic() < end:
            time.sleep(0.1)
    return n


def stop_proc(proc, live, soft_s, grace_s, known=()):
    """End a session's pilot by pid only: `end` into its live channel (the game ends, the pilot writes its summary), after soft_s SIGTERM to its process group, after
    grace_s more SIGKILL; then whatever of its tree (`known` from earlier looks, and what is below it now) is still alive. ('ended' | 'terminated' | 'killed', how many
    descendants had to be stopped)."""
    tree = sorted(set(known) | set(descendants(proc.pid)))
    how = 'ended'
    if proc.poll() is None:
        if soft_s > 0:
            try:
                with open(Path(live) / 'steps.txt', 'a') as f:
                    f.write('end\n')
            except OSError:
                pass
            _wait(proc, soft_s)
        if proc.poll() is None:
            _signal_group(proc, signal.SIGTERM)
            how = 'terminated'
            if not _wait(proc, grace_s):
                _signal_group(proc, signal.SIGKILL)
                _wait(proc, 5.0)
                how = 'killed'
    return how, stop_leftovers(tree, grace_s)


def reached_play(run_dir):
    """Whether the game got to gameplay in a run: hsap's `gameplay` event in its out.jsonl (the live channel's, or the copy the pilot keeps)."""
    run_dir = Path(run_dir)
    return any(r.get('ev') == 'gameplay' for sub in ('live', '', 'pilot/live') for r in jsonl(run_dir / sub / 'out.jsonl'))


def read_run(run_dir, tag, book):
    """What a finished (or stopped) session did, from the pilot's own files and the Book: summary.json (the ladder's counts and episodes), the transcript's
    `recover` rows (which rung got Link past), and the attempts and blocks the ladder wrote to the Book under this run."""
    run_dir = Path(run_dir)
    summary = read_json(run_dir / 'summary.json')
    rec = (summary or {}).get('recover') or {}
    trows = [r for r in jsonl(run_dir / 'transcript.jsonl') if r.get('kind') == 'recover']
    by = {k: [r for r in trows if r.get('status') == k] for k in ('blocked', 'recovered', 'marked-bad')}
    attempts = [{'tactic': r['tactic'], 'cause': r['cause'], 'outcome': r['outcome'], 'gain_m': r.get('gain_m')} for r in book.rows('attempt') if r.get('run') == tag]
    blocks = [{'cause': r.get('cause'), 'tried': r.get('tried'), 'worked': r.get('worked'), 'how': r.get('how'), 's': r.get('s')} for r in book.rows('block') if r.get('run') == tag]
    return {'summary': summary is not None, 'outcome': (summary or {}).get('outcome'), 'decisions': (summary or {}).get('decisions'),
            'blocks': rec.get('blocks', len(by['blocked'])), 'recovered': rec.get('recovered', len(by['recovered'])), 'marked_bad': rec.get('marked_bad', len(by['marked-bad'])),
            'left': rec.get('left', 0), 'open': rec.get('open', 0), 'recovered_by': [r.get('rung') for r in by['recovered']],
            'rungs': {k.split(':', 1)[-1]: v for k, v in (rec.get('rungs') or {}).items()}, 'episodes': (rec.get('episodes') or [])[:12],
            'attempts': attempts, 'tried': [x['tactic'] for x in attempts], 'worked': [x['tactic'] for x in attempts if x['outcome'] == 'worked'],
            'block_rows': blocks, 'causes_seen': sorted({x['cause'] for x in attempts} | {b['cause'] for b in blocks if b['cause']}), 'routes': (summary or {}).get('routes')}


def run_session(plan, s, *, wall, out, importer, stop, clock=time.monotonic, log=print, env=None):
    """One visit: the pilot's run in its own process group, waited for until its game wall plus its tail, then ended (see stop_proc); the row of what it did;
    its summary and transcript kept under out/<name>/; the run imported into the library."""
    t = plan['timing']
    name, tag = s['name'], s['tag']
    row = {'name': name, 'tag': tag, 'cluster': s['cluster'], 'map': s['map'], 'cause': s['cause'], 'mode': s['mode'], 'status': 'pending', 'started': time.strftime('%F %T'),
           'wall': int(wall), 'expected_attempts': s.get('expected_attempts')}
    sdir = Path(out) / name
    sdir.mkdir(parents=True, exist_ok=True)
    run_dir = Path(plan['pilot']).parent / 'runs' / tag
    if run_dir.exists():
        row['status'] = f'refused: the pilot has a run folder {run_dir} already'
        return row
    live = run_dir / 'live'
    cmd = pilot_command(plan, s, wall)
    log(f'session {name}: {" ".join(shlex.quote(str(c)) for c in cmd)}')
    t0 = clock()
    with open(sdir / 'pilot.out', 'wb') as lg:
        proc = subprocess.Popen([str(c) for c in cmd], stdout=lg, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=child_env(env, plan['lib']), start_new_session=True)
    row['pid'] = proc.pid
    limit = t0 + wall + t['tail_s']
    how, tree, last_scan = None, [], t0
    try:
        while proc.poll() is None:
            if clock() - last_scan >= 1.0:   # (what hangs below the pilot is listed as it goes: a pilot that dies on its own leaves its hsap and game running)
                tree, last_scan = sorted(set(tree) | set(descendants(proc.pid))), clock()
            if stop.on:
                (how, row['descendants_stopped']), row['stopped_by'] = stop_proc(proc, live, t['term_soft_s'], t['term_grace_s'], tree), 'signal'
                break
            if clock() >= limit:
                (how, row['descendants_stopped']), row['stopped_by'] = stop_proc(proc, live, t['soft_s'], t['grace_s'], tree), 'deadline'
                break
            try:
                proc.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                pass
    finally:
        if proc.poll() is None:   # (an error in the loop: nothing is left running)
            stop_proc(proc, live, 0, t['grace_s'], tree)
    if how is None:
        row['descendants_stopped'] = stop_leftovers(tree, t['grace_s'])
    row['exit'] = proc.returncode
    row['ended_by'] = how
    row['seconds'] = round(clock() - t0, 1)
    got = read_run(run_dir, tag, tactics.Book(plan['tactics_dir'], readonly=True))
    row.update(got)
    row['gameplay'] = bool(got['decisions'] or got['blocks'] or got['attempts'] or reached_play(run_dir))
    if not row['gameplay'] or got['outcome'] in ('no gameplay', 'no first state line'):   # (a game that never got to play, stopped or not: no crash, no visit)
        row['status'] = 'no-gameplay'
    elif how is not None:
        row['status'] = 'stopped'
    elif not got['summary']:
        row['status'] = 'no-summary'
    else:
        row['status'] = 'done'
    for fn in ('summary.json', 'transcript.jsonl'):
        if (run_dir / fn).is_file():
            shutil.copy2(run_dir / fn, sdir / fn)
    if got['routes']:   # (the pilot imported its own run)
        row['import'] = got['routes']
    elif row['status'] in ('done', 'stopped', 'no-summary') and (run_dir / 'live').is_dir():
        try:
            row['import'] = importer(run_dir, tag)
        except Exception as e:   # noqa: BLE001  (the library is a record: a run that cannot be imported is told, never a reason to stop the hold)
            row['import_error'] = f'{type(e).__name__}: {e}'[:200]
    row['played'] = bool(got['decisions'] or got['blocks'] or got['attempts'])
    return row


class Stop:
    """The hold's own SIGTERM/SIGHUP as a flag: the loops look at it, so nothing is torn down in the middle of a write."""

    def __init__(self):
        self.signum = None

    def __call__(self, signum, frame):
        self.signum = signum

    @property
    def on(self):
        return self.signum is not None


def library_importer(plan):
    """The import of a run the pilot could not import itself, with the world model for the stuck points' causes where there is one (loaded when first needed)."""
    lib = routelib.RouteLib(plan['lib'])
    state = {}

    def importer(run_dir, tag):
        if 'world' not in state:
            try:
                state['world'] = routelib.PrivateWorld(plan['world']) if plan.get('world') else None
            except Exception:   # noqa: BLE001  (no world model: the causes of the stuck points are told by the rules that need none)
                state['world'] = None
        return lib.import_run(run_dir, label=tag, world=state['world'])
    return importer


def run_hold(plan, out, log=print, importer=None, stop=None, clock=time.monotonic, name=None):
    """The hold: the sessions one after another inside hold_seconds minus the reserve. A session starts only if its wall (shortened to what is left, never under
    min_wall_s) and the time to end it still fit; the rows and the Book's before and after go to result.json after every session."""
    out = Path(out)
    out.mkdir(parents=True)
    t = plan['timing']
    importer = importer or library_importer(plan)
    stop = stop or Stop()
    book = tactics.Book(plan['tactics_dir'], readonly=True)
    before = (read_json(plan['book_before']) or {}).get('summary') or book.summary()
    led = Ledger(plan['ledger'])
    t0, started = clock(), time.strftime('%F %T')
    hold_end = t0 + plan['hold_seconds'] - t['reserve_s']
    rows = []
    state = {'rc': 0}

    def flush():
        after = tactics.Book(plan['tactics_dir'], readonly=True).summary()
        (out / 'result.json').write_text(json.dumps({'format': FORMAT, 'name': plan['name'], 'night': plan['night'], 'waiter': name, 'started': started,
                                                      'seconds': round(clock() - t0, 1), 'hold_seconds': plan['hold_seconds'], 'rc': state['rc'], 'rows': rows,
                                                      'book': {'before': before, 'after': after, 'diff': book_diff(before, after)}}, indent=1, default=str))
    flush()
    for s in plan['sessions']:
        if stop.on:
            rows.append({'name': s['name'], 'status': 'not started: the hold was stopped by a signal'})
            continue
        left = hold_end - clock()
        wall = min(float(s['wall']), left - t['overhead_s'])
        if wall < t['min_wall_s']:
            rows.append({'name': s['name'], 'tag': s['tag'], 'cluster': s['cluster'], 'map': s['map'], 'cause': s['cause'], 'mode': s['mode'],
                         'status': f'not started: {left:.0f} s left of the hold, a session needs {t["min_wall_s"] + t["overhead_s"]:.0f}'})
            flush()
            continue
        row = run_session(plan, s, wall=wall, out=out, importer=importer, stop=stop, clock=clock, log=log)
        rows.append(row)
        led.add(kind='visited' if row['status'] in ('done', 'stopped') and row.get('played') else 'failed', night=plan['night'], plan=plan['name'], map=s['map'], cluster=s['cluster'],
                at=s['at'], cause=s['cause'], tag=s['tag'], status=row['status'], worked=row.get('worked'))
        flush()
    if stop.on:
        state['rc'] = 143
        rows.append({'name': 'hold', 'status': 'stopped by a signal'})
    flush()
    return state['rc']


# ------------------------------------------------------------------------------------------------------------------------ the report

def book_diff(before, after):
    """What changed between two Book.summary() dicts: the totals, the sources, and per cause and tactic the attempts and wins gained."""
    d = {'attempts': after['attempts'] - before['attempts'], 'blocks': after['blocks'] - before['blocks'], 'demos': after['demos'] - before['demos'],
         'sources': {k: after['sources'].get(k, 0) - before['sources'].get(k, 0) for k in sorted(set(after['sources']) | set(before['sources']))}, 'causes': {}}
    d['sources'] = {k: v for k, v in d['sources'].items() if v}
    for cause in sorted(set(after['causes']) | set(before['causes'])):
        rows = {}
        for tac in sorted(set(after['causes'].get(cause, {})) | set(before['causes'].get(cause, {}))):
            b = before['causes'].get(cause, {}).get(tac, {'n': 0, 'wins': 0})
            a = after['causes'].get(cause, {}).get(tac, {'n': 0, 'wins': 0})
            if a != b:
                rows[tac] = {'n': a['n'] - b['n'], 'wins': a['wins'] - b['wins'], 'now': {'n': a['n'], 'wins': a['wins']}}
        if rows:
            d['causes'][cause] = rows
    return d


def rank_change(before, after, eps=0.005):
    """The tactics whose place in a ranking, score or attempts moved: [{tactic, from, to (1-based places), score_from, score_to, n_from, n_to, wins_from,
    wins_to}], those that moved up first."""
    pb = {r['tactic']: (i + 1, r) for i, r in enumerate(before)}
    pa = {r['tactic']: (i + 1, r) for i, r in enumerate(after)}
    out = []
    for tac in dict.fromkeys([r['tactic'] for r in after] + [r['tactic'] for r in before]):
        b, a = pb.get(tac), pa.get(tac)
        if b and a and b[0] == a[0] and abs(b[1]['score'] - a[1]['score']) < eps and b[1]['n'] == a[1]['n']:
            continue
        out.append({'tactic': tac, 'from': b[0] if b else None, 'to': a[0] if a else None, 'score_from': b[1]['score'] if b else None, 'score_to': a[1]['score'] if a else None,
                    'n_from': b[1]['n'] if b else 0, 'n_to': a[1]['n'] if a else 0, 'wins_from': b[1]['wins'] if b else 0, 'wins_to': a[1]['wins'] if a else 0})
    out.sort(key=lambda r: ((r['to'] or 99) - (r['from'] or 99), r['to'] or 99))
    return out


def report_data(plan, result, book):
    """Per cluster: what was tried, what worked, the ranking before (the plan's) and now; and the Book's diff."""
    rows = {r.get('name'): r for r in result['rows']}
    before = read_json(plan['book_before']) or {}
    sessions = []
    for s in plan['sessions']:
        r = rows.get(s['name'], {'status': 'not run'})
        causes = [s['cause']] + [c for c in r.get('causes_seen', []) if c != s['cause']]
        entry = {'name': s['name'], 'cluster': s['cluster'], 'map': s['map'], 'cause': s['cause'], 'mode': s['mode'], 'status': r.get('status'), 'expected_attempts': s['expected_attempts'],
                 'attempts': len(r.get('attempts', [])), 'tried': r.get('tried', []), 'worked': r.get('worked', []), 'outcomes': [f'{a["tactic"]} {a["outcome"]}' for a in r.get('attempts', [])],
                 'blocks': r.get('blocks'), 'recovered_by': r.get('recovered_by', []), 'marked_bad': r.get('marked_bad'), 'causes_seen': r.get('causes_seen', []),
                 'library_tried': s['old']['library_tried'], 'ranking': {}}
        entry['ranking'][s['cause']] = {'context': rank_change(s['old']['production'], rank_rows(book, s['cause'], map=s['map'], age=s['age'], at=s['at']))}
        for c in causes[1:]:
            entry['ranking'][c] = {'plain': rank_change((before.get('ranks') or {}).get(c, []), rank_rows(book, c))}
        sessions.append(entry)
    after = book.summary()
    return {'name': plan['name'], 'night': plan['night'], 'sessions': sessions,
            'book': {'before': before.get('summary'), 'after': after, 'diff': book_diff(before['summary'], after) if before.get('summary') else None}}


def report_text(rep, result):
    out = [f'# {rep["name"]} (night {rep["night"]})', '']
    d = (rep['book'] or {}).get('diff')
    started = [r for r in result['rows'] if r.get('pid')]
    out.append(f'hold: {result.get("seconds")} s of {result.get("hold_seconds")}, {len(started)} of {len(rep["sessions"])} sessions started, exit {result.get("rc")}')
    if d:
        out.append(f'Book: {d["attempts"]:+d} attempts, {d["blocks"]:+d} blocks, {d["demos"]:+d} demonstrations; sources {d["sources"] or "no change"}')
    for s in rep['sessions']:
        out += ['', f'## {s["name"]}: {s["map"]} {s["cluster"]} ({s["cause"]}), mode {s["mode"]}: {s["status"]}']
        out.append(f'- the library had tried: {", ".join(s["library_tried"]) or "nothing"}')
        out.append(f'- visit: {s["blocks"]} blocks, got past by {", ".join(map(str, s["recovered_by"])) or "nothing"}, marked bad {s["marked_bad"]}; '
                   f'{s["attempts"]} attempts ({len(s["worked"])} worked; {s["expected_attempts"]} expected): {", ".join(s["outcomes"]) or "none"}')
        for cause, ch in s['ranking'].items():
            kind, rows = next(iter(ch.items()))
            if not rows:
                out.append(f'- ranking for {cause} ({kind}): unchanged')
                continue
            out.append(f'- ranking for {cause} ({"this place" if kind == "context" else "anywhere"}) changed:')
            tried = [r for r in rows if r['n_from'] != r['n_to'] or abs((r['score_to'] or 0) - (r['score_from'] or 0)) >= 0.005]
            for r in tried[:8]:
                out.append(f'  - {r["tactic"]}: place {r["from"] or "-"} -> {r["to"] or "-"}, score {r["score_from"] if r["score_from"] is not None else "-"} -> {r["score_to"] if r["score_to"] is not None else "-"}, '
                           f'attempts {r["wins_from"]}/{r["n_from"]} -> {r["wins_to"]}/{r["n_to"]}')
            if len(rows) > len(tried):
                out.append(f'  - {len(rows) - len(tried)} more only changed their place')
    if d and d['causes']:
        out += ['', '## the Book, per cause: attempts (wins) gained', '']
        for cause, rows in d['causes'].items():
            out.append(f'- {cause}: ' + ', '.join(f'{t} {v["n"]:+d} ({v["wins"]:+d})' for t, v in rows.items()))
    return '\n'.join(out) + '\n'


def write_table(out, plan, rows):
    lines = [f'# {plan["name"]}', '', '| session | map | cluster | cause | mode | status | blocks | got past by | attempts (worked) | tried in order | imported |', '|---|---|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        imp = r.get('import') or {}
        lines.append(f'| {r.get("name")} | {r.get("map", "")} | {r.get("cluster", "")} | {r.get("cause", "")} | {r.get("mode", "")} | {r.get("status")} | {r.get("blocks", "")} | '
                     f'{", ".join(map(str, r.get("recovered_by") or [])) or "-"} | {len(r.get("attempts") or [])} ({len(r.get("worked") or [])}) | {", ".join(r.get("tried") or []) or "-"} | '
                     f'{(str(imp.get("metres")) + " m, " + str(imp.get("new_edges")) + " new edges") if imp else r.get("import_error", "-")} |')
    (Path(out) / 'table.md').write_text('\n'.join(lines) + '\n')


def write_report(plan, out):
    result = read_json(Path(out) / 'result.json')
    if result is None:
        raise PlanError(f'{out}/result.json: no result (the hold has not run)')
    rep = report_data(plan, result, tactics.Book(plan['tactics_dir'], readonly=True))
    (Path(out) / 'report.json').write_text(json.dumps(rep, indent=1))
    text = report_text(rep, result)
    (Path(out) / 'report.md').write_text(text)
    return text


# ------------------------------------------------------------------------------------------------------------------------ the waiter

def _cmdline(pid):
    try:
        return [a.decode('utf-8', 'replace') for a in Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0') if a]
    except OSError:
        return []


def _session_of(pid):
    try:
        raw = Path(f'/proc/{pid}/stat').read_text()
        return int(raw.rpartition(')')[2].split()[3])
    except (OSError, ValueError, IndexError):
        return None


def waiter_args(args, name):
    """(plan path) when a command line is a self-play hold or its waiter for this name (`... selfplay.py run PLAN ... --name NAME`), else None."""
    for i, a in enumerate(args):
        if a.endswith('selfplay.py') and i + 2 < len(args) and args[i + 1] == 'run':
            rest = args[i + 2:]
            if any(x == '--name' and j + 1 < len(rest) and rest[j + 1] == name for j, x in enumerate(rest)) or f'--name={name}' in rest:
                return args[i + 2]
    return None


def waiters(name):
    """[{pid, plan}] of the live processes of waiters and holds of this name (the exec chain has several: flock, timeout, python)."""
    out = []
    for p in Path('/proc').iterdir():
        if p.name.isdigit() and int(p.name) != os.getpid():
            plan = waiter_args(_cmdline(int(p.name)), name)
            if plan is not None:
                out.append({'pid': int(p.name), 'plan': plan})
    return out


def queue_command(plan, out, name='PilotLearn', code=None, quiet=None, measuring=None):
    """The one waiter the main lane requires: the quiet-window lock, then the measuring lock, then `timeout` (TERM, KILL 20 s later) around the hold. The name is
    in the command so the lane can tell whose it is."""
    quiet, measuring = quiet or QUIET, measuring or MEASURING
    if not (quiet and measuring):
        raise PlanError('the waiter needs the main lane\'s lock files: set PILOT_QUIET_LOCK and PILOT_MEASURING_LOCK (this machine\'s own values; there is no default)')
    script = Path(code or plan['code']) / 'pilot' / 'selfplay.py'
    return ['setsid', 'env', '--default-signal=HUP', 'flock', '-w', '43200', quiet, 'flock', '-x', measuring, 'timeout', '--signal=TERM', '--kill-after=20', str(int(plan['hold_seconds'])),
            sys.executable, '-I', '-B', str(script), 'run', str(plan['plan_path']), '--out', str(out), '--name', name]


def pid_file(plan):
    return Path(plan['dir']) / 'waiter.pid'


def do_queue(plan, out, name, code=None, dry_run=False, log=print):
    """0 queued (or, with dry_run, would be), 2 refused."""
    errs = plan_errors(plan, out)
    try:
        cmd = queue_command(plan, out, name, code)
        log('command: ' + ' '.join(shlex.quote(c) for c in cmd))
    except PlanError as e:
        errs.append(str(e))
    others = waiters(name)
    pf = pid_file(plan)
    if others:
        errs.append(f'a waiter or hold named {name} is queued or running (pid {" ".join(str(w["pid"]) for w in others)}): one at a time')
    for e in errs:
        log('refusing: ' + e)
    if errs:
        return 2
    if dry_run:
        log('dry run: nothing started')
        return 0
    log_file = open(Path(plan['dir']) / 'waiter.log', 'w')
    p = subprocess.Popen(cmd, stdout=log_file, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, cwd=plan['dir'])   # (setsid is the first word: the waiter is its own session)
    log_file.close()
    pf.write_text(f'{p.pid}\n')
    time.sleep(0.2)
    if p.poll() is not None:
        log(f'refusing: the waiter ended at once (exit {p.returncode}): see {Path(plan["dir"]) / "waiter.log"}')
        pf.unlink(missing_ok=True)
        return 2
    log(f'waiter pid {p.pid} (pid file {pf})')
    return 0


def do_stop(plan, name, grace=30.0, log=print):
    """Kill a queued or running waiter of the plan by its pid file: every process of its session (flock, timeout, the hold) gets SIGTERM, whatever is left after the
    grace SIGKILL. Never SIGCONT. The pid must still look like a waiter (a recycled pid is not killed)."""
    pf = pid_file(plan)
    try:
        pid = int(pf.read_text().split()[0])
    except (OSError, ValueError, IndexError):
        log(f'no waiter pid file {pf}')
        return 1
    if waiter_args(_cmdline(pid), name) is None:
        log(f'pid {pid} is not a waiter of {name} (gone, or its number was reused): nothing killed, pid file removed')
        pf.unlink(missing_ok=True)
        return 1
    group = [p for p in (int(x.name) for x in Path('/proc').iterdir() if x.name.isdigit()) if p == pid or _session_of(p) == pid]
    log(f'stopping the waiter: pids {group}')
    for p in group:
        try:
            os.kill(p, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    end = time.monotonic() + grace
    while time.monotonic() < end and any(Path(f'/proc/{p}').exists() and not _zombie(p) for p in group):
        time.sleep(0.1)
    for p in group:
        if Path(f'/proc/{p}').exists() and not _zombie(p):
            try:
                os.kill(p, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
    pf.unlink(missing_ok=True)
    return 0


def _zombie(pid):
    try:
        return Path(f'/proc/{pid}/stat').read_text().rpartition(')')[2].split()[0] == 'Z'
    except (OSError, IndexError):
        return True


# ------------------------------------------------------------------------------------------------------------------------ the command line

def cmd_plan(a):
    try:
        plan, notes, segments = build_plan(a)
    except NothingToDo as e:
        print(e)
        return 3
    except PlanError as e:
        print('refused:', e)
        return 2
    print_plan(plan, notes)
    if a.dry_run:
        print('dry run: nothing written')
        return 0
    try:
        write_plan(plan, segments, tactics.Book(plan['tactics_dir'], readonly=True))
    except PlanError as e:
        print('refused:', e)
        return 2
    print(f'written: {plan["dir"]}/plan.json')
    return 0


def cmd_check(a):
    plan = load_plan(a.plan)
    errs = plan_errors(plan, a.out)
    for e in errs:
        print('refused:', e)
    print(f'{plan["name"]}: {len(plan["sessions"])} sessions, hold {plan["hold_seconds"]} s' + ('' if errs else ': ok'))
    return 2 if errs else 0


def cmd_saves(a):
    return make_saves(load_plan(a.plan))


def cmd_run(a):
    plan = load_plan(a.plan)
    errs = plan_errors(plan, a.out)
    if errs:
        for e in errs:
            print('refused:', e, file=sys.stderr)
        return 2
    stop = Stop()
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGHUP, stop)
    rc = run_hold(plan, a.out, name=a.name, stop=stop)
    try:
        result = read_json(Path(a.out) / 'result.json')
        write_table(a.out, plan, result['rows'])
        write_report(plan, a.out)
    except (OSError, ValueError, KeyError, PlanError) as e:
        print(f'report: {type(e).__name__}: {e}', file=sys.stderr)
    return rc


def cmd_queue(a):
    plan = load_plan(a.plan)
    out = Path(a.out) if a.out else Path(plan['dir']) / 'hold'
    return do_queue(plan, out, a.name, a.code, a.dry_run)


def cmd_stop(a):
    return do_stop(load_plan(a.plan), a.name)


def cmd_report(a):
    plan = load_plan(a.plan)
    out = Path(a.out) if a.out else Path(plan['dir']) / 'hold'
    try:
        print(write_report(plan, out), end='')
    except PlanError as e:
        print('refused:', e)
        return 2
    return 0


def default_world(a):
    """The world model folder of a plan: --world (empty: none), else the dev folder's world/ where there is one."""
    if a.world is not None:
        return a.world or None
    return str(HERE.parent / 'world') if (HERE.parent / 'world').is_dir() else None


def seed_book(a, log=print):
    """The Book learns from the runs since it last looked, before tonight's plan values the clusters by what the Book knows: tactics_seed over the pilot's runs folder and
    the folders of the runs the route library imported (idempotent: a run seeded before adds nothing). A failure is told and the night goes on."""
    try:
        import tactics_seed
        lib = routelib.RouteLib(Path(a.lib or default_lib()).resolve())
        pilot_dir = Path(a.pilot).resolve().parent if a.pilot else Path(a.code or HERE.parent).resolve() / 'pilot'
        roots = [pilot_dir / 'runs'] + [Path(r['folder']) for r in lib.runs().get('runs', []) if r.get('folder')]
        book = tactics.Book(Path(a.tactics_dir).resolve() if a.tactics_dir else tactics.default_dir().resolve())
        world = None
        if default_world(a):
            try:
                world = routelib.PrivateWorld(default_world(a))
            except Exception as e:   # noqa: BLE001  (no world model: the causes come from the steps only, as tactics_seed's own --no-world)
                log(f'seeding without a world model ({type(e).__name__}: {e})')
        t0 = time.time()
        totals = tactics_seed.seed(book, roots, tactics.Sensor(world), log=log)
        log(f'the Book was seeded from {totals["runs"]} new runs in {time.time() - t0:.1f} s: +{totals["attempts"]} attempts, +{totals["blocks"]} blocks, +{totals["demos"]} demonstrations ({totals["skipped"]} skipped)')
        return totals
    except Exception as e:   # noqa: BLE001  (a Book that cannot be seeded is a night planned on what it has)
        log(f'the Book was not seeded ({type(e).__name__}: {e})')
        return None


# ---- the nightly timer: a transient user timer (systemd-run --user --on-calendar, no unit file written), each firing re-arms the next night, like PlayBench's

TIMER_PREFIX = 'pilot-selfplay-'


def next_calendar(at, now=None):
    """'YYYY-MM-DD HH:MM:SS': the next time of day `at` (HH:MM) strictly after `now`."""
    now = now or datetime.datetime.now()
    hh, mm = (int(x) for x in at.split(':'))
    t = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if t <= now:
        t += datetime.timedelta(days=1)
    return t.strftime('%Y-%m-%d %H:%M:%S')


def timer_unit(cal):
    return TIMER_PREFIX + cal.replace(' ', '-').replace(':', '')


def timer_argv(a, cal, quiet=None, measuring=None, python=None):
    """systemd-run's command line: the unit, the calendar, the two lane locks as the service's environment, and the frozen code's `timer fire` (which re-arms)."""
    argv = ['systemd-run', '--user', f'--unit={timer_unit(cal)}', f'--on-calendar={cal}', '--timer-property=AccuracySec=60s', '--collect',
            f'--setenv=PILOT_QUIET_LOCK={quiet or QUIET}', f'--setenv=PILOT_MEASURING_LOCK={measuring or MEASURING}',
            python or sys.executable, '-I', '-B', str(Path(a.code) / 'pilot' / 'selfplay.py'), 'timer', 'fire', '--copy', str(a.copy), '--code', str(a.code),
            '--max-sessions', str(a.max_sessions), '--name', a.name, '--at', a.at, '--user-authorized', '--authority', a.authority or '']
    if a.refreeze:
        argv += ['--refreeze', str(a.refreeze)]
    if a.root:
        argv += ['--root', str(a.root)]
    return argv


def arm_timer(a, now=None, run=subprocess.run, quiet=None, measuring=None):
    """Arm the next night's transient timer and record it (<root>/timer.json: the unit, the calendar, the command and the authority). Refused without the user's word
    (--user-authorized, --authority: what the user said) and without the lane's lock files in the environment."""
    if not getattr(a, 'user_authorized', False):
        raise PlanError('arming the nightly timer needs the user\'s word: pass --user-authorized and --authority "<what the user said>"')
    quiet, measuring = quiet or QUIET, measuring or MEASURING
    if not quiet or not measuring:
        raise PlanError('the timer needs the main lane\'s lock files: set PILOT_QUIET_LOCK and PILOT_MEASURING_LOCK')
    cal = next_calendar(a.at, now)
    argv = timer_argv(a, cal, quiet, measuring)
    r = run(argv, capture_output=True, text=True)
    root = Path(a.root or default_root())
    root.mkdir(parents=True, exist_ok=True)
    info = {'at': now_iso(), 'calendar': cal, 'unit': timer_unit(cal), 'command': argv, 'result': (r.stdout + r.stderr).strip(), 'rc': r.returncode, 'authority': a.authority}
    (root / 'timer.json').write_text(json.dumps(info, indent=1))
    if r.returncode:
        raise PlanError(f'systemd-run failed: {info["result"]}')
    return info


def fire_timer(a, arm=None, run=subprocess.run, nightly=None):
    """What the timer runs: arm the next night FIRST (a failure below must not end the chain), replace the frozen code (a hold of it that is running keeps its code), then
    one `nightly`. A night skipped (a waiter of its own still queued, a ran-already night, a refusal) prints why and is no failure. Always returns 0."""
    arm = arm or arm_timer
    nightly = nightly or (lambda b: b.fn(b))
    try:
        info = arm(a)
        print(f'timer: next night armed: {info["unit"]}', flush=True)
    except Exception as e:   # noqa: BLE001
        print(f'timer: the next night could not be armed: {e}', flush=True)
    if a.refreeze:
        r = run(['bash', str(a.refreeze), str(a.code)], capture_output=True, text=True)
        if r.returncode == 3:
            print('timer: a hold of the frozen code is running: the code is left as it is', flush=True)
        elif r.returncode:
            print(f'timer: night skipped: the code could not be frozen ({(r.stderr or r.stdout).strip()[-200:]})', flush=True)
            return 0
        else:
            print('timer: ' + r.stdout.strip(), flush=True)
    args = ['nightly', '--copy', str(a.copy), '--code', str(a.code), '--max-sessions', str(a.max_sessions), '--name', a.name] + (['--root', str(a.root)] if a.root else [])
    rc = nightly(make_parser().parse_args(args))
    print(f'timer: nightly returned {rc}' + (' (skipped or refused: the reason is printed above)' if rc else ''), flush=True)
    return 0


def cmd_timer(a):
    if a.action == 'arm':
        try:
            info = arm_timer(a)
        except PlanError as e:
            print('refused:', e)
            return 2
        print(f'armed: {info["unit"]} at {info["calendar"]}')
        return 0
    if a.action == 'fire':
        return fire_timer(a)
    root = Path(a.root or default_root())
    try:
        info = json.loads((root / 'timer.json').read_text())
    except (OSError, ValueError):
        print('no timer recorded')
        return 0
    if a.action == 'status':
        print(json.dumps({k: info[k] for k in ('unit', 'calendar', 'at', 'authority')}))
        print(subprocess.run(['systemctl', '--user', 'list-timers', '--all', '--no-pager'], capture_output=True, text=True).stdout)
        return 0
    r = subprocess.run(['systemctl', '--user', 'stop', info['unit'] + '.timer'], capture_output=True, text=True)
    print(f'disarmed {info["unit"]}' if r.returncode == 0 else f'could not stop {info["unit"]}: {r.stderr.strip()}')
    return r.returncode


def cmd_nightly(a):
    """plan, saves, check, queue for one night; running it again for the same night changes nothing, and it never queues beside another waiter of its own."""
    try:
        night = night_id(a.night or time.strftime('%Y-%m-%d'))
    except PlanError as e:
        print('refused:', e)
        return 2
    root = Path(a.root or default_root()).resolve()
    folder = root / (a.plan_name or f'SelfPlay-{night}')
    hold = folder / 'hold'
    errs = spend_errors({'caps': a.caps, 'ledger': a.spend_ledger} if a.caps or a.spend_ledger else None)
    if errs:
        for e in errs:
            print('refused:', e)
        return 2
    mine = waiters(a.name)
    if mine:
        if any(Path(w['plan']).resolve().parent == folder for w in mine):
            print(f'night {night}: already queued or running (pid {" ".join(str(w["pid"]) for w in mine)}): nothing to do')
            return 0
        print(f'refusing: a waiter named {a.name} is queued or running for another plan ({mine[0]["plan"]}, pid {mine[0]["pid"]}): one at a time')
        return 2
    if (hold / 'result.json').is_file():
        print(f'night {night}: the hold ran already ({hold / "result.json"}): nothing to do')
        return 0
    if hold.exists():
        print(f'refusing: {hold} exists without a result: the hold of night {night} started and did not finish; look at it, do not run it twice')
        return 2
    a.night, a.plan_name = night, folder.name
    if not (folder / 'plan.json').is_file():
        if a.dry_run:
            print('dry run: the Book would be seeded from the new runs first')
        elif not a.no_seed:
            seed_book(a)
        try:
            plan, notes, segments = build_plan(a)
        except NothingToDo as e:
            print(f'night {night}: {e}')
            return 0
        except PlanError as e:
            print('refused:', e)
            return 2
        print_plan(plan, notes)
        if a.dry_run:
            plan['plan_path'] = str(folder / 'plan.json')
            try:
                print('command: ' + ' '.join(shlex.quote(c) for c in queue_command(plan, hold, a.name, a.code)))
            except PlanError as e:
                print('refused:', e)
                return 2
            print('dry run: nothing written, nothing started')
            return 0
        write_plan(plan, segments, tactics.Book(plan['tactics_dir'], readonly=True))
    plan = load_plan(folder / 'plan.json')
    if a.dry_run:
        return do_queue(plan, hold, a.name, a.code, dry_run=True)
    rc = make_saves(plan)
    if rc:
        return rc
    return do_queue(plan, hold, a.name, a.code)


def add_plan_args(p):
    p.add_argument('--lib', help='the route library (default $ROUTELIB_DIR, else the harness\'s routelib)')
    p.add_argument('--tactics-dir', dest='tactics_dir', help='the tactics Book\'s folder (default tactics.default_dir())')
    p.add_argument('--root', help=f'where plans and the ledger live (default $PILOT_SELFPLAY_DIR, else {default_root()})')
    p.add_argument('--plan-name', dest='plan_name', help='the plan folder and tag prefix (default SelfPlay-<night>)')
    p.add_argument('--night', help='the night id, YYYY-MM-DD (default today)')
    p.add_argument('--ledger', help='the visits ledger (default <root>/ledger.jsonl)')
    p.add_argument('--copy', help='the game copy the sessions run in (default $PILOT_COPY; no other default)')
    p.add_argument('--max-sessions', dest='max_sessions', type=int, default=3)
    p.add_argument('--hold-seconds', dest='hold_seconds', type=int, default=HOLD_MAX_S)
    p.add_argument('--wall', type=int, default=WALL_S, help='a session\'s wall: the game\'s, boot included')
    p.add_argument('--budget-s', dest='budget_s', type=int, default=BUDGET_S, help='a session\'s game-time budget in the segment')
    p.add_argument('--mode', choices=MODES, default='explore')
    p.add_argument('--only', action='append', metavar='MAP:CLUSTER[=MODE]', help='visit exactly this cluster (repeatable, first); a proof run of the production ladder is =ranked')
    p.add_argument('--cool-nights', dest='cool_nights', type=int, default=COOL_NIGHTS, help='a place visited in the last this many nights (tonight included) is left alone')
    p.add_argument('--ignore-ledger', dest='ignore_ledger', action='store_true')
    p.add_argument('--base-child', dest='base_child', default='explore17-field-child-day', help='the saves-library entry a child session\'s save is made from')
    p.add_argument('--base-adult', dest='base_adult', default='coop-field-adult-day', help='the saves-library entry an adult session\'s save is made from')
    p.add_argument('--proven-saves', dest='proven_saves', nargs='+', metavar='NAME', help='saves-library entries proven in a game: each gets one session that uses the save exactly as it is '
                   '(no --start: hs_make_save --start has not been run in a game yet), the pilot\'s own first leg walking to the cluster\'s want. They come first and share max-sessions with the --start ones')
    p.add_argument('--saves-dir', dest='saves_dir', help='where the saves are made (default <plan folder>/saves)')
    p.add_argument('--saves-library', dest='saves_library', help='the harness\'s saves library (default <harness>/saves)')
    p.add_argument('--save-tool', dest='save_tool', help='hs_make_save.py (default <harness>/tools/hs_make_save.py)')
    p.add_argument('--world', help='the world model folder for the import (default: the dev folder\'s world/, where there is one)')
    p.add_argument('--code', help='the (frozen) code folder holding pilot/ (default: this one)')
    p.add_argument('--pilot', help='the pilot.py to run (default <code>/pilot/pilot.py)')
    p.add_argument('--caps', help='the caps file the spend check reads (default pilot/caps.json)')
    p.add_argument('--spend-ledger', dest='spend_ledger', help='the ledger the spend check reads (default pilot/ledger.jsonl)')
    p.add_argument('--dry-run', dest='dry_run', action='store_true')


def make_parser():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('plan')
    add_plan_args(p)
    p.set_defaults(fn=cmd_plan)
    p = sub.add_parser('check')
    p.add_argument('plan')
    p.add_argument('--out')
    p.set_defaults(fn=cmd_check)
    p = sub.add_parser('saves')
    p.add_argument('plan')
    p.set_defaults(fn=cmd_saves)
    p = sub.add_parser('run')
    p.add_argument('plan')
    p.add_argument('--out', required=True)
    p.add_argument('--name', default='PilotLearn', help='whose hold this is (the lane finds waiters by it)')
    p.set_defaults(fn=cmd_run)
    p = sub.add_parser('queue')
    p.add_argument('plan')
    p.add_argument('--out')
    p.add_argument('--name', default='PilotLearn')
    p.add_argument('--code')
    p.add_argument('--dry-run', dest='dry_run', action='store_true')
    p.set_defaults(fn=cmd_queue)
    p = sub.add_parser('stop')
    p.add_argument('plan')
    p.add_argument('--name', default='PilotLearn')
    p.set_defaults(fn=cmd_stop)
    p = sub.add_parser('report')
    p.add_argument('plan')
    p.add_argument('--out')
    p.set_defaults(fn=cmd_report)
    p = sub.add_parser('timer')
    p.add_argument('action', choices=('arm', 'fire', 'status', 'disarm'))
    p.add_argument('--at', default='03:30', help='the time of day (HH:MM)')
    p.add_argument('--copy')
    p.add_argument('--code', help='the frozen code folder')
    p.add_argument('--max-sessions', dest='max_sessions', type=int, default=3)
    p.add_argument('--name', default='PilotLearn')
    p.add_argument('--refreeze', help='a script that replaces the frozen code (called with the code folder; exit 3: a hold of it is running)')
    p.add_argument('--root')
    p.add_argument('--user-authorized', dest='user_authorized', action='store_true')
    p.add_argument('--authority', default='', help='what the user said (recorded in timer.json)')
    p.set_defaults(fn=cmd_timer)
    p = sub.add_parser('nightly')
    add_plan_args(p)
    p.add_argument('--name', default='PilotLearn')
    p.add_argument('--no-seed', dest='no_seed', action='store_true', help='plan on the Book as it is: do not seed it from the new runs first')
    p.set_defaults(fn=cmd_nightly)
    return ap


def main(argv=None):
    a = make_parser().parse_args(argv)
    return a.fn(a)


if __name__ == '__main__':
    raise SystemExit(main())
