#!/usr/bin/env python3
"""Chapters: the pilot plays a whole section of the game toward a story goal (PilotSections).

A chapter (private TOML, pilot/chapters/<name>.toml) states an AIM in words ("from a new child save, get the sword and the shield, then
clear the dungeon to its boss"), the save to start from, PROGRESS MARKERS the game's own state can prove (a flag, a map, a rupee count, the share of a
region visited), and budgets (game seconds, USD, objectives, replans). A planner model (a bigger one than the step decider: the user wants good
data) breaks the aim into OBJECTIVES, a few at a time, from what it is given: the aim, the markers and which are met, Link's state, a DIGEST of the
offline world model around him (exits with their destination maps, chests, doors, people, signs, items, shops, switches, climbable things, enemies,
each with its distance and what the offline planner says about getting there), a look at the game's own picture, and the result of every step so far.
Each objective is one goal of the existing pilot (pilot.py, interact.py, actions.py: reach a place across a gap or a ledge, open a chest, talk, read, collect, enter, fight, strafe, use an item,
buy, push a block, dive, play a song that warps, ride) with a condition the state can prove; the step decider plays it as it plays any segment,
under its own time budget. When an objective fails (gave up, ran out of time or decisions, the game ended) the planner is asked again with the failure
(what each step reported, where Link stands, what the offline planner said) and may reorder, drop, or find another way. Progress is tracked on every
state line; the chapter ends when every required marker is met, or a budget runs out.

    pilot.py run <chapter.toml> ...       the ordinary run command: a file with an `aim` key is a chapter (pilot.py hands it to this module)
    sections.py check <chapter.toml>      parse it, list its markers, seeds and the flags it will watch
    sections.py digest <area> [x z]       the world digest the planner is given for that place (private world model needed)

What a run leaves in its run folder: transcript.jsonl (the decisions of every objective, as for a segment), chapter.json (the aim, markers and when each
was met, the timeline of objectives, every plan with its cost, costs by kind, anomalies), timeline.md (the same for a person), plans.jsonl (each planner
request's data and answer, no key), looks/ (the pictures the planner was shown), anomalies.jsonl.
What leaves the machine, with a key: the planner's request (aim, markers, state, digest, step results, one picture, and with lessons on (lessons.py) a few short sentences
about places where the pilot was stopped before); the step decider's requests as for any run.
Everything of the game (the chapter files, the digest, the pictures, the plans) is private; nothing of it is in this module.
"""
import base64
import json
import math
import os
import re
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import interact  # noqa: E402
import lessons as lessons_lib  # noqa: E402
import openai_api  # noqa: E402
import pilot as P  # noqa: E402  (pilot.py puts itself in sys.modules as `pilot` before it imports this module)
import recover  # noqa: E402

MODEL_KINDS = ('go_to', 'open_chest', 'talk_to', 'read_sign', 'collect', 'enter', 'fight', 'strafe', 'use_item', 'buy', 'push_block', 'dive',
               'play_song', 'warp_song', 'ride', 'explore_interact', 'wait_time')
GOAL_OF = {'go_to': 'cross'}   # an objective kind that is another goal kind of the pilot
PARAM_KEYS = ('to', 'count', 'price', 'song', 'count_flag', 'direction', 'how', 'meters', 'button', 'hold', 'range', 'fast', 'rupees', 'min_kinds',
              'quiet_s', 'sides', 'rounds', 'notes', 'drop', 'proof', 'dy')
DEFAULT_SECONDS = {'go_to': 150, 'open_chest': 90, 'talk_to': 120, 'read_sign': 80, 'collect': 120, 'enter': 100, 'fight': 120, 'strafe': 60, 'use_item': 80,
                   'buy': 120, 'push_block': 90, 'dive': 80, 'play_song': 80, 'warp_song': 100, 'ride': 100, 'explore_interact': 150, 'wait_time': 120}
def standard_watch():
    """The flags every chapter watches besides its own (private: chapters/watch.json, or the file PILOT_WATCH names; a JSON list of flag names)."""
    try:
        data = json.loads(Path(os.environ.get('PILOT_WATCH') or HERE / 'chapters' / 'watch.json').read_text())
    except (OSError, ValueError):
        return []
    return [w for w in data if isinstance(w, str)]


TIME_LUM = {'night': 0.16, 'day': 0.30}   # the sky band's brightness (0..1): at most `night` is night, at least `day` is day (read from the first pictures)


# ---- progress markers: what the game's state can prove

class Coverage:
    """The share of a region a run has been in: a grid of `cell` metre cells inside a circle of an area; a state line marks its cell."""

    def __init__(self, area, center, radius, cell=15.0):
        self.area, self.center, self.radius, self.cell = area, (float(center[0]), float(center[1])), float(radius), float(cell)
        n = int(math.ceil(self.radius / self.cell))
        self.cells = {(i, j) for i in range(-n, n + 1) for j in range(-n, n + 1)
                      if math.hypot(i * self.cell, j * self.cell) <= self.radius}
        self.seen = set()

    def key(self, x, z):
        return (round((x - self.center[0]) / self.cell), round((z - self.center[1]) / self.cell))

    def add(self, st):
        pos = st.get('pos')
        if pos and st.get('area') == self.area:
            k = self.key(pos[0], pos[2])
            if k in self.cells:
                self.seen.add(k)

    def fraction(self):
        return len(self.seen) / len(self.cells) if self.cells else 0.0

    def unvisited(self, pos, limit=4):
        """The centres of cells not visited yet, nearest first: [{x, z, dist}]."""
        out = []
        for k in self.cells - self.seen:
            x, z = self.center[0] + k[0] * self.cell, self.center[1] + k[1] * self.cell
            out.append({'x': round(x, 1), 'z': round(z, 1), 'dist': round(math.hypot(x - pos[0], z - pos[2]), 1) if pos else None})
        out.sort(key=lambda e: e['dist'] if e['dist'] is not None else 0)
        return out[:limit]


class MarkerCond:
    """What pilot.export_route and the summary read of a marker's pseudo-goal: a text, the flag name, a flag-only test."""

    def __init__(self, marker):
        self.marker = marker
        self.text, self.name, self.watch = marker.text, marker.flag_name, marker.watch

    def met(self, flags):
        return all(c.met(flags) for c in self.marker.flags) if self.marker.flags else False


class Marker:
    """A progress marker of a chapter. Conditions (all that are given must hold): `flag` / `flags` (pilot.Cond texts), `area` (Link is in that map,
    not loading), `rupees` (at least), `rupees_gain` (more than at the start), `coverage` (the region's share visited), `near` ([x, z, r] in `area`),
    `y_below` / `y_above` (Link's height), `count_flag` with `count_gain` (a watched counter that rose by that much since it was first seen)."""

    def __init__(self, d, cover=None):
        self.name, self.what = str(d['name']), str(d.get('what', ''))
        self.required = bool(d.get('required', True))
        texts = [d['flag']] if d.get('flag') else []
        texts += list(d.get('flags') or [])
        self.flags = [P.Cond(t) for t in texts]
        self.area = d.get('area')
        self.rupees, self.gain, self.coverage = d.get('rupees'), d.get('rupees_gain'), d.get('coverage')
        self.near = d.get('near')
        self.y_below, self.y_above = d.get('y_below'), d.get('y_above')
        self.count_flag, self.count_gain = d.get('count_flag'), d.get('count_gain')
        self.by_objective = bool(d.get('by_objective', False))   # met when an objective that serves it was proved by its own condition (a dive, a ride, a night)
        self.first_count = None
        self.cover = cover
        self.start_rupees, self.met_at, self.met_area, self.met_pos = None, None, None, None
        self.flag_name = self.flags[0].name if self.flags else None
        self.watch = [c.name for c in self.flags]
        bits = [c.text for c in self.flags]
        if self.area:
            bits.append(f'the map is {self.area}')
        if self.rupees is not None:
            bits.append(f'rupees >= {self.rupees}')
        if self.gain is not None:
            bits.append(f'{self.gain} more rupees than at the start')
        if self.coverage is not None:
            bits.append(f'{float(self.coverage):.0%} of the region visited')
        if self.near:
            bits.append(f'within {self.near[2]:g} m of ({self.near[0]:g}, {self.near[1]:g})')
        if self.y_below is not None:
            bits.append(f'Link\'s height below {self.y_below:g}')
        if self.y_above is not None:
            bits.append(f'Link\'s height above {self.y_above:g}')
        if self.count_flag:
            bits.append(f'{self.count_flag} up by {self.count_gain or 1}')
            self.watch.append(self.count_flag)
        if self.by_objective:
            bits.append('an objective that serves it was met by its own proof')
        self.text = ' and '.join(bits) or 'never'


    def check(self, st):
        """Whether the marker holds at this state line; sets met_at (game time) the first time."""
        if self.met_at is not None:
            return True
        if st.get('rupees') is not None and self.start_rupees is None:
            self.start_rupees = st['rupees']
        flags = st.get('flags') or {}
        ok = bool(self.text != 'never') and not self.by_objective   # (an objective-proved marker is set by the chapter: ChapterPilot.credit)
        ok = ok and all(c.met(flags) for c in self.flags)
        if self.area:
            ok = ok and st.get('area') == self.area and st.get('loading') != 1
        if self.rupees is not None:
            ok = ok and st.get('rupees') is not None and st['rupees'] >= self.rupees
        if self.gain is not None:
            ok = ok and st.get('rupees') is not None and self.start_rupees is not None and st['rupees'] - self.start_rupees >= self.gain
        if self.coverage is not None:
            ok = ok and self.cover is not None and self.cover.fraction() >= float(self.coverage)
        if self.near:
            pos = st.get('pos')
            ok = ok and bool(pos) and math.hypot(pos[0] - self.near[0], pos[2] - self.near[1]) <= self.near[2] and \
                (not self.area or st.get('area') == self.area)
        if self.y_below is not None or self.y_above is not None:
            pos = st.get('pos')
            ok = ok and bool(pos) and (self.y_below is None or pos[1] < self.y_below) and (self.y_above is None or pos[1] > self.y_above)
        if self.count_flag:
            now = flags.get(self.count_flag)
            if isinstance(now, (int, float)) and self.first_count is None:
                self.first_count = now
            ok = ok and isinstance(now, (int, float)) and self.first_count is not None and now - self.first_count >= (self.count_gain or 1)
        if ok:
            self.met_at, self.met_area, self.met_pos = st.get('t'), st.get('area'), st.get('pos')
        return ok

    def view(self):
        return {'name': self.name, 'what': self.what, 'met': self.met_at is not None, 'met_at_t': self.met_at, 'when': self.text, 'required': self.required}


# ---- the chapter file

@dataclass
class Chapter:
    path: Path
    name: str
    aim: str
    area: str
    save: str = None
    boot: str = None
    wall: int = 900
    budget_s: float = 800.0
    budget_usd: float = 5.0
    max_objectives: int = 16
    max_replans: int = 6
    per_plan: int = 4
    humanize: int = None
    planner_model: str = None
    look: bool = True
    decisions_per_objective: int = 40
    watch: list = field(default_factory=list)
    hints: list = field(default_factory=list)
    marker_specs: list = field(default_factory=list)
    seeds: list = field(default_factory=list)
    region: dict = None
    save_after: bool = False

    def segment(self, markers):
        return ChapterSegment(self, markers)


def is_chapter_text(text):
    try:
        return 'aim' in tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return False


def load(path):
    d = tomllib.loads(Path(path).read_text())
    if 'aim' not in d:
        raise ValueError(f'{path}: no `aim`: not a chapter')
    for k in ('name', 'aim', 'area'):
        if not isinstance(d.get(k), str) or not d[k]:
            raise ValueError(f'{path}: {k} is required (a string)')
    names = set()
    for m in d.get('progress', []):
        if 'name' not in m or m['name'] in names:
            raise ValueError(f'{path}: every [[progress]] needs a unique name')
        names.add(m['name'])
    region = d.get('region')
    if region and not (region.get('area') and len(region.get('center', [])) == 2 and region.get('radius')):
        raise ValueError(f'{path}: region needs area, center = [x, z] and radius')
    ch = Chapter(path=Path(path), name=d['name'], aim=d['aim'], area=d['area'], save=d.get('save'), boot=d.get('boot'), wall=int(d.get('wall', 900)),
                 budget_s=float(d.get('budget_seconds', 800)), budget_usd=float(d.get('budget_usd', 5.0)), max_objectives=int(d.get('max_objectives', 16)),
                 max_replans=int(d.get('max_replans', 6)), per_plan=int(d.get('per_plan', 4)),
                 humanize=d.get('humanize'), planner_model=d.get('planner_model'), look=bool(d.get('look', True)),
                 decisions_per_objective=int(d.get('decisions_per_objective', 40)), watch=list(d.get('watch', [])), hints=list(d.get('hints', [])),
                 marker_specs=list(d.get('progress', [])), seeds=list(d.get('objective', [])), region=region, save_after=bool(d.get('save_after', False)))
    if not ch.marker_specs:
        raise ValueError(f'{path}: a chapter needs at least one [[progress]] marker')
    for s in ch.seeds:   # a seed is checked now, so that a typo is not found an hour into a hold
        objective_from_dict(s, ch, 'seed')
    return ch


def load_if_chapter(path):
    """The Chapter for a TOML file with an `aim`, else None (a segment)."""
    try:
        text = Path(path).read_text()
    except OSError:
        return None
    return load(path) if is_chapter_text(text) else None


class ChapterSegment:
    """pilot.Segment's face for a chapter: what cmd_run reads (name, area, save, boot, wall, budget, watch, goals = the markers as pseudo-goals)."""

    def __init__(self, ch, markers):
        self.chapter, self.path = ch, ch.path
        self.name, self.what, self.area, self.save, self.prefix, self.boot = ch.name, ch.aim, ch.area, ch.save, None, ch.boot
        self.place, self.scripted = None, False   # (no placement and no scripted play: a chapter's own save is the start, its objectives are decided)
        self.humanize, self.wall, self.budget, self.max_decisions, self.save_after = ch.humanize, ch.wall, ch.budget_s, 100000, ch.save_after
        self.goals = [P.Goal(m.name, MarkerCond(m), 'marker', [], m.what) for m in markers]
        watch = standard_watch() + list(ch.watch) + [w for m in markers for w in m.watch] + [w for s in ch.seeds for w in seed_watch(s)]
        self.watch = sorted(dict.fromkeys(watch))[:64]
        if len(set(watch)) > 64:
            print(f'chapter {ch.name}: {len(set(watch))} flags to watch, the game side takes 64: the first {len(self.watch)} (sorted) are kept', flush=True)


def seed_watch(s):
    out = [s['flag'].split('=')[0].split('<')[0].split('>')[0].split('!')[0]] if s.get('flag') else []
    if s.get('count_flag'):
        out.append(s['count_flag'])
    return out


# ---- objectives

@dataclass
class Objective:
    id: str
    kind: str
    what: str
    targets: list
    params: dict
    max_s: float
    progress: str = ''
    source: str = 'model'
    flag: str = ''
    status: str = 'open'
    result: dict = None


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', str(s).lower()).strip('-')[:24] or 'x'


def objective_from_dict(d, ch, source, n=0):
    """An Objective from a seed table or a planner's object; raises ValueError for one that cannot be played."""
    kind = str(d.get('kind', ''))
    if kind not in MODEL_KINDS:
        raise ValueError(f'objective kind {kind!r}: one of {", ".join(MODEL_KINDS)}')
    targets = []
    for t in d.get('targets') or ([d['target']] if isinstance(d.get('target'), dict) else []):
        t = dict(t)
        if 'actor' not in t and not (isinstance(t.get('at'), (list, tuple)) and len(t['at']) == 2):
            raise ValueError(f'objective {d.get("name") or d.get("id")}: a target needs `at = [x, z]` or `actor`')
        t.setdefault('name', slug(d.get('what', kind)))
        t.setdefault('kind', {'open_chest': 'chest', 'talk_to': 'talk', 'read_sign': 'talk', 'enter': 'door', 'fight': 'reach', 'buy': 'talk'}.get(kind, 'reach'))
        t.setdefault('radius', 1.2 if kind in ('open_chest', 'talk_to', 'read_sign', 'buy') else 1.5)
        targets.append(t)
    if kind not in ('wait_time', 'explore_interact', 'warp_song', 'play_song', 'fight') and not targets:
        raise ValueError(f'objective {d.get("name") or d.get("id")} ({kind}) has no target')
    if kind in ('explore_interact', 'warp_song', 'play_song', 'fight', 'wait_time') and not targets:
        targets = [{'name': 'here', 'at': [0.0, 0.0], 'kind': 'reach', 'radius': 1000.0, 'here': True}]   # (a target that follows Link: replaced by his place when it starts)
    params = {k: d[k] for k in PARAM_KEYS if d.get(k) not in (None, '', 0, 0.0)}
    oid = str(d.get('id') or d.get('name') or f'o{n}-{slug(kind)}')
    secs = float(d.get('max_seconds') or DEFAULT_SECONDS[kind])
    return Objective(id=oid, kind=kind, what=str(d.get('what', '')), targets=targets, params=params, max_s=max(20.0, min(secs, 900.0)),
                     progress=str(d.get('progress') or ''), source=source, flag=str(d.get('flag') or ''))


def goal_table(o, pos=None):
    """The [[goal]] table of an objective, as pilot.Segment reads it. A `here` target is where Link stands now."""
    ts = []
    for t in o.targets:
        t = {k: v for k, v in t.items() if k != 'here'}
        if o.targets[0].get('here') and pos:
            t['at'] = [pos[0], pos[2]]
            t['y'] = pos[1]
        ts.append({k: v for k, v in t.items() if v is not None})
    g = {'name': o.id, 'what': o.what, 'kind': GOAL_OF.get(o.kind, o.kind), 'targets': ts}
    if o.flag:
        g['flag'] = o.flag
    g.update(o.params)
    if o.kind == 'go_to':
        g.setdefault('how', 'auto')
    return g


# ---- the world digest

_links = {}


def links_from(area):
    if 'all' not in _links:
        try:
            _links['all'] = json.loads((interact.world_dir() / 'links.json').read_text())
        except (OSError, ValueError):
            _links['all'] = []
    return {x['name']: x for x in _links['all'] if x.get('from') == area and x.get('name')}


def area_age(area):
    return 'adult' if area.endswith('_Adult') else 'child'


def chest_front(o):
    """Where Link stands to open a chest: 0.95 m in front of its lid side (the placement's yaw; Euler (pi, t, pi) is the yaw pi - t)."""
    rot = o.get('rot') or [0.0, 0.0, 0.0]
    a, b, c = rot[0], rot[1], rot[2]
    yaw = (math.pi - b) if abs(abs(a) - math.pi) < 0.1 and abs(abs(c) - math.pi) < 0.1 else b
    x, y, z = o['pos']
    return [round(x + 0.95 * math.sin(yaw), 2), round(z + 0.95 * math.cos(yaw), 2)]


DIGEST_KINDS = (('exit', 12), ('door', 6), ('chest', 8), ('person', 8), ('sign', 6), ('item', 8), ('shop', 3), ('switch', 4), ('crawl', 3),
                ('warp', 3), ('stone', 3), ('owl', 1))


DIGEST_KEYS = {'person': 'people', 'switch': 'switches', 'crawl': 'crawl_holes', 'shop': 'shop_items', 'stone': 'stones', 'owl': 'owls'}


def digest_entry(o, pos, kind, k, area):
    x, y, z = o['pos']
    e = {'ref': f'{kind}:{k}', 'name': o.get('name') or o.get('gyaml'), 'what': o.get('gyaml'), 'x': round(x, 1), 'y': round(y, 1), 'z': round(z, 1)}
    if pos:
        e['dist'] = round(math.hypot(x - pos[0], z - pos[2]), 1)
        e['dy'] = round(y - pos[1], 1)
    if kind == 'chest':
        e['front'] = chest_front(o)
        ev = ((o.get('flags') or {}).get('params') or {}).get('GetEventName')
        if ev:
            e['event'] = ev
    if kind == 'exit':
        link = links_from(area).get(o.get('name'))
        if link:
            e['to'] = link.get('to_adult') if area_age(area) == 'adult' else link.get('to_child')
    if (o.get('flags') or {}).get('presence'):
        e['only_while'] = (o['flags']['presence'] or {}).get('flag')
    return e


def world_digest(area, st, plan=None, limit_nav=36, radius=170.0):
    """What the planner is given of the world around Link: per kind the nearest objects (exits all), each with its ref, place, distance and,
    for the nearest few, what the offline planner says about the way there. `plan` is worldmodel.plan.plan (or None: no nav column)."""
    pos = st.get('pos')
    objs = interact.objects_for(area)
    seen, groups = set(), {}
    for o in objs:
        kind = o.get('kind')
        if kind not in {k for k, _ in DIGEST_KINDS}:
            continue
        key = (o.get('gyaml'), round(o['pos'][0] / 0.6), round(o['pos'][1] / 0.6), round(o['pos'][2] / 0.6))
        if key in seen:
            continue
        seen.add(key)
        d = math.hypot(o['pos'][0] - pos[0], o['pos'][2] - pos[2]) if pos else 0.0
        if kind != 'exit' and d > radius:
            continue
        groups.setdefault(kind, []).append((d, o))
    out = {'area': area, 'age': area_age(area)}
    nav_budget = limit_nav
    for kind, cap in DIGEST_KINDS:
        rows = sorted(groups.get(kind, []), key=lambda t: t[0])[:cap]
        entries = []
        for k, (d, o) in enumerate(rows, 1):
            e = digest_entry(o, pos, kind, k, area)
            if plan is not None and pos and nav_budget > 0 and kind in ('exit', 'door', 'chest', 'person', 'sign', 'item', 'shop', 'crawl', 'warp'):
                nav_budget -= 1
                gx, gz = (e.get('front') or [o['pos'][0], o['pos'][2]])
                try:
                    r = plan(area, (pos[0], pos[2]), (gx, gz), from_y=pos[1], to_y=o['pos'][1], radius=1.5, doors='through')
                    e['way'] = {'ok': bool(r.get('ok')), 'm': r.get('length'), 'why': r.get('why'),
                                'needs': [n['kind'] for n in (r.get('needed') or []) if not n.get('allowed')][:4]}
                except Exception as err:   # noqa: BLE001  the planner's failure is a fact about the digest, not an end of the run
                    e['way'] = {'ok': False, 'why': f'planner error {type(err).__name__}'}
            entries.append(e)
        if entries:
            out[DIGEST_KEYS.get(kind, kind + 's')] = entries
    climbs = sorted(((math.hypot(o['pos'][0] - pos[0], o['pos'][2] - pos[2]) if pos else 0.0, o) for o in objs if o.get('kind') == 'climbable'), key=lambda t: t[0])[:4]
    if climbs:
        out['climbables'] = [{'what': o.get('gyaml'), 'x': round(o['pos'][0], 1), 'y': round(o['pos'][1], 1), 'z': round(o['pos'][2], 1), 'dist': round(d, 1)} for d, o in climbs]
    enemies = {}
    for o in objs:
        if o.get('kind') == 'enemy' and pos and math.hypot(o['pos'][0] - pos[0], o['pos'][2] - pos[2]) <= 70.0 and abs(o['pos'][1] - pos[1]) < 15:
            enemies.setdefault(o.get('gyaml'), []).append(o)
    if enemies:
        out['enemies'] = [{'what': g, 'count': len(v), 'nearest': min(round(math.hypot(o['pos'][0] - pos[0], o['pos'][2] - pos[2]), 1) for o in v)}
                          for g, v in sorted(enemies.items(), key=lambda kv: -len(kv[1]))[:6]]
    return out


def digest_refs(digest):
    """{ref: entry} of a digest, for resolving the planner's target_ref."""
    refs = {}
    for k, v in digest.items():
        if isinstance(v, list):
            for e in v:
                if isinstance(e, dict) and e.get('ref'):
                    refs[e['ref']] = e
    return refs


# ---- the planner

PLANNER_DEVELOPER = (
    'You plan for an automatic test pilot that plays a 3D action-adventure game (a third-person game with a boy or grown hero, Link) in order to play a whole '
    'SECTION of it toward an aim, and to find bugs and gaps while it does. You are given the AIM, progress markers (some already met), Link\'s state, a digest of the '
    'offline map around him, the objectives tried so far with what each step reported, and a picture of the game\'s screen. You return the NEXT FEW objectives (at most '
    'the number asked), in order, each one a goal that the pilot\'s own step-by-step player can carry out and the game\'s state can prove. Rules: (1) Prefer the shortest '
    'sensible sequence toward the markers that are not met; do not repeat an objective that just failed unless you change what makes it fail (another side, a '
    'run-up, a different route, doing something else first such as taking an item or collecting rupees). (2) Coordinates are metres on the ground (x, z), y is '
    'height; they must come from the digest (use target_ref) or from places you were told; never invent a place. (3) A map change is an objective of kind enter with `to` '
    'the destination map; the digest\'s exits name their destinations. (4) The pilot can: walk (go_to, which also jumps gaps, climbs ledges and ivy and goes through '
    'doors and crawl holes where the offline map says it must), open_chest, talk_to, read_sign, collect (rupees, items), enter (a door or load zone), fight (clear enemies '
    'near a place), strafe (lock-on circling), use_item (the item on the item button, at a target), buy (a shelf item: needs the rupees), push_block, dive, play_song / '
    'warp_song (an ocarina song, `song` its name), ride (a horse), explore_interact (free play near here: try chests, items, people, signs, doors, lock-on, camera), wait_time (wait for '
    'day or night, `until`). (5) `flag` is the proof the state will show: only a name from the watched flags given to you (leave it empty when the objective is proved by place, '
    'map, rupees or its own step result). (6) `progress` names the marker an objective serves, or is empty. (7) Give each a max_seconds of game time that fits '
    '(walking 100 to 200, a chest 60 to 90, a fight 90 to 150) and watch the time and cost left. (8) If the digest says a way needs a jump, a ledge, a climb or a door, '
    'that is fine: the player handles it; if it says not-connected or off-mesh, choose another route or a nearer target. (9) Be brief in `reason`: why these, in what order, and what you read in the failures.')

OBJ_PROPS = {
    'id': {'type': 'string'}, 'kind': {'type': 'string', 'enum': list(MODEL_KINDS)}, 'what': {'type': 'string'}, 'target_ref': {'type': 'string'},
    'x': {'type': ['number', 'null']}, 'z': {'type': ['number', 'null']}, 'y': {'type': ['number', 'null']}, 'radius': {'type': 'number'},
    'flag': {'type': 'string'}, 'to': {'type': 'string'}, 'count': {'type': 'integer'}, 'price': {'type': 'integer'}, 'song': {'type': 'string'},
    'count_flag': {'type': 'string'}, 'direction': {'type': 'string', 'enum': ['', 'push', 'pull']},
    'how': {'type': 'string', 'enum': ['auto', 'jump', 'ledge', 'climb', 'swim']}, 'until': {'type': 'string', 'enum': ['', 'day', 'night']},
    'meters': {'type': 'number'}, 'max_seconds': {'type': 'integer'}, 'progress': {'type': 'string'},
}


def plan_schema():
    return {'type': 'object', 'additionalProperties': False, 'required': ['reason', 'objectives'],
            'properties': {'reason': {'type': 'string'},
                           'objectives': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': list(OBJ_PROPS),
                                                                      'properties': OBJ_PROPS}}}}


def parse_plan(text, ch, digest, watched, n0):
    """(objectives, rejected [(id, why)], reason) from the planner's JSON text. Objectives that cannot be played are rejected with a reason."""
    data = json.loads(text)
    refs = digest_refs(digest)
    out, rejected = [], []
    for i, d in enumerate(data.get('objectives') or []):
        oid = f'p{n0}-{i + 1}-{slug(d.get("id") or d.get("kind"))}'
        try:
            d = dict(d)
            ref = refs.get(d.get('target_ref') or '')
            t = None
            if ref:
                t = {'name': slug(ref['name'] or ref['ref']), 'at': [ref['x'], ref['z']], 'y': ref['y']}
                if ref.get('front'):
                    t['front'] = ref['front']
                if ref['ref'].startswith('exit'):
                    t['kind'] = 'door'
            elif d.get('x') is not None and d.get('z') is not None and abs(d['x']) < 3000 and abs(d['z']) < 3000:
                t = {'name': slug(d.get('what') or d['kind']), 'at': [float(d['x']), float(d['z'])]}
                if d.get('y') is not None:
                    t['y'] = float(d['y'])
            elif d.get('target_ref'):
                raise ValueError(f'target_ref {d["target_ref"]!r} is not in the digest')
            if t is not None and d.get('radius'):
                t['radius'] = float(d['radius'])
            d['targets'] = [t] if t else []
            flag = str(d.get('flag') or '').strip()
            if flag and not re.search(r'[<>=!]', flag):
                flag += '=1'   # a bare flag name asks for it to be set
            if flag and re.split(r'[<>=!]', flag)[0] not in watched:
                flag = ''   # a flag that is not watched cannot be seen: the objective is proved another way
            d['flag'] = flag
            if d.get('kind') == 'wait_time':
                d['until'] = d.get('until') or 'day'
            if d.get('kind') == 'enter' and not d.get('to') and ref and ref.get('to'):
                d['to'] = ref['to']
            o = objective_from_dict({**d, 'id': oid}, ch, 'model', n0)
            if d.get('until'):
                o.params['until'] = d['until']
            out.append(o)
        except (ValueError, KeyError, TypeError) as e:
            rejected.append((oid, str(e)[:160]))
    return out[:ch.per_plan], rejected, str(data.get('reason') or '')[:600]


class ChapterPlanner:
    """The model that plans: a Responses request with a JSON schema, the chapter's aim, state, digest and a picture. Errors (no key, a cap, a refusal, bad
    JSON) end in `error` on the answer; the chapter then falls back to its seeds."""
    name = 'responses'

    def __init__(self, client, model=None):
        self.client = client
        self.model = model or openai_api.caps()['planner_model']

    def body(self, data, image=None):
        content = [{'type': 'input_text', 'text': json.dumps(data, separators=(',', ':'))}]
        if image:
            content.append({'type': 'input_image', 'image_url': image, 'detail': 'auto'})
        developer = PLANNER_DEVELOPER if not data.get('lessons') else f'{PLANNER_DEVELOPER} {lessons_lib.NOTE}'   # (lessons.py: one sentence that says what the key is)
        return {'model': self.model,
                'input': [{'role': 'developer', 'content': developer}, {'role': 'user', 'content': content}],
                'text': {'format': {'type': 'json_schema', 'name': 'chapter_plan', 'schema': plan_schema(), 'strict': True}},
                'max_output_tokens': 9000}

    def ask(self, data, image=None):
        """(text, info) of the model's JSON answer; raises openai_api's errors."""
        body = self.body(data, image)
        price = openai_api.PRICES.get(('responses', self.model), openai_api.Price(inp=10.0, cached=0.0, write=0.0, out=50.0))
        est = len(json.dumps(body)) / 3.0 * price.inp / 1e6 + (700 if image else 0) * price.inp / 1e6 + 9000 * price.out / 1e6
        ans, ms, row = self.client.post('/responses', body, api='responses', model=self.model, kind='planner', estimate=est, timeout=240)
        text = ''
        for item in ans.get('output', []):
            if item.get('type') == 'message':
                for part in item.get('content', []):
                    if part.get('type') == 'output_text':
                        text += part.get('text', '')
        return text, {'model': self.model, 'latency_ms': round(ms, 1), 'usage': row['usage'], 'cost_usd': row['cost_usd']}


# ---- the time of day, the one thing no flag tells: the brightness of the game's own picture

def daylight_of(path):
    """The brightness (0..1) of the upper 40 percent of a picture (the sky band), by ImageMagick; the stdlib PNG reader without it. None when neither works."""
    p = str(path)
    try:
        out = subprocess.run(['convert', p, '-gravity', 'north', '-crop', '100%x40%+0+0', '+repage', '-colorspace', 'Gray', '-resize', '1x1!', '-format', '%[fx:mean]', 'info:'],
                             capture_output=True, text=True, timeout=20)
        if out.returncode == 0:
            return round(float(out.stdout.strip()), 3)
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    try:
        import vision
        w, h, rgb = vision.read_png(Path(p).read_bytes())
        rows = max(1, int(h * 0.4))
        total = sum(rgb[i] * 0.2126 + rgb[i + 1] * 0.7152 + rgb[i + 2] * 0.0722 for i in range(0, rows * w * 3, 3))
        return round(total / (rows * w) / 255.0, 3)
    except Exception:   # noqa: BLE001  a measurement that cannot be made is no reading
        return None


def day_class(lum):
    return None if lum is None else 'night' if lum <= TIME_LUM['night'] else 'day' if lum >= TIME_LUM['day'] else 'between'


# ---- the run

def fmt_t(t):
    return '-' if t is None else f'{t:.0f}'


class ChapterPilot:
    """What cmd_run runs for a chapter (pilot.py's hook): the same constructor as pilot.Pilot (plus copy, client, args as keywords), `run(first_state)` returns
    the outcome string, and the attributes cmd_run's summary reads (decisions, plans, duel_seen, skipped, frags, recover_summary())."""

    def __init__(self, seg, decider, ch, run_dir, run_id, alive, planner=None, max_decisions=None, copy=None, client=None, args=None, chapter=None, **pilot_kw):
        self.seg, self.decider, self.ch, self.dir, self.run_id, self.alive = seg, decider, ch, Path(run_dir), run_id, alive
        self.chapter = chapter or seg.chapter
        self.copy, self.client, self.args = copy, client, args
        self.pilot_kw = pilot_kw
        self.cover = Coverage(self.chapter.region['area'], self.chapter.region['center'], self.chapter.region['radius'],
                              self.chapter.region.get('cell', 15.0)) if self.chapter.region else None
        self.markers = [Marker(d, self.cover) for d in self.chapter.marker_specs]
        seg.goals = [P.Goal(m.name, MarkerCond(m), 'marker', [], m.what) for m in self.markers]
        self.watched = set(seg.watch)
        self.decisions, self.plans, self.skipped, self.frags, self.duel_seen = [], [], {}, [], None   # (plans: what pilot.cmd_run reads of a Pilot; the chapter's own are cplans)
        self.cplans = []
        self.timeline, self.anomalies, self.looks, self.rejected = [], [], [], []
        self.tried, self.pilots, self.queue = [], [], []
        self.scanned = 0
        self.planner = self.make_planner()
        self.ledger0 = openai_api.spent(run_id)['run']
        self.capture = None
        self.t0 = None
        self.n_plan = 0
        self.outcome = None
        self.last_st = {}

    # -- the planner and the picture

    def make_planner(self):
        a = self.args
        if getattr(a, 'no_chapter_planner', False) or self.client is None:
            return None
        if self.client.real and openai_api.key_state() not in ('file', 'env'):
            print(f'chapter planner: {openai_api.key_state()}; the chapter plays its seeds', flush=True)
            return None
        try:
            model = os.environ.get('PILOT_CHAPTER_MODEL') or getattr(a, 'chapter_model', None) or self.chapter.planner_model
            return ChapterPlanner(self.client, model)
        except openai_api.CapReached as e:
            print(f'chapter planner: {e}; the chapter plays its seeds', flush=True)
            return None

    def picture(self, tag):
        """A frame of the game as a data URL (kept under looks/), or None."""
        if not self.chapter.look or self.copy is None:
            return None
        try:
            import vision
            if self.capture is None:
                self.capture = vision.Capture(self.dir / 'looks', width=800, copy=self.copy, run_id=self.run_id)
            path, w, h, mime, how = self.capture()
        except Exception as e:   # noqa: BLE001  a picture is a help, never a reason to stop
            self.looks.append({'tag': tag, 'error': f'{type(e).__name__}: {e}'[:200]})
            return None
        self.looks.append({'tag': tag, 'file': f'looks/{Path(path).name}', 'how': how, 'w': w, 'h': h})
        return f'data:{mime};base64,' + base64.b64encode(Path(path).read_bytes()).decode('ascii')

    # -- state tracking: progress, coverage, anomalies

    def scan(self):
        """Every state line the game side wrote since the last scan: markers, coverage, anomalies. Returns the newest state line."""
        self.ch.unread += self.ch.poll()   # (kept for the waits of the pilot that plays next: poll alone would swallow them)
        events = self.ch.events
        newest = None
        prev = self.last_st
        for e in events[self.scanned:]:
            if e.get('ev') != 'state':
                continue
            newest = e
            if self.cover is not None:
                self.cover.add(e)
            for m in self.markers:
                if m.met_at is None and m.check(e):
                    print(f'  marker {m.name} met at {fmt_t(e.get("t"))} s: {m.what}', flush=True)
            self.detect(prev, e)
            prev = e
        self.scanned = len(events)
        if newest is not None:
            self.last_st = newest
        return newest or self.last_st

    def detect(self, a, b):
        """Anomalies a bug hunt cares about, from two consecutive state lines: a jump of place with no load, a fall out of the world, life gone."""
        pa, pb = a.get('pos'), b.get('pos')
        if pa and pb and a.get('area') == b.get('area') and not a.get('loading') and not b.get('loading') and (b.get('t') or 0) - (a.get('t') or 0) < 1.5:
            d = math.hypot(pb[0] - pa[0], pb[2] - pa[2])
            if d > 9.0 and b.get('event') != 1:
                self.note('position-jump', b, f'{d:.1f} m in {(b.get("t") or 0) - (a.get("t") or 0):.1f} s with no load or event')
            if pb[1] < pa[1] - 25.0:
                self.note('fell-out', b, f'y {pa[1]:.1f} -> {pb[1]:.1f}')
        if b.get('life') == 0 and a.get('life') != 0:
            self.note('life-zero', b, 'life reached 0')

    def note(self, kind, st, detail):
        row = {'kind': kind, 't': st.get('t'), 'area': st.get('area'), 'pos': st.get('pos'), 'detail': detail, 'objective': getattr(self, 'current_id', None)}
        self.anomalies.append(row)
        with open(self.dir / 'anomalies.jsonl', 'a') as f:
            f.write(json.dumps(row) + '\n')

    # -- planning

    def spent(self):
        return openai_api.spent(self.run_id)['run']

    def state_view(self, st):
        flags = st.get('flags') or {}
        return {'area': st.get('area'), 'age': area_age(st.get('area') or self.chapter.area), 'pos': st.get('pos'), 'facing': st.get('facing'), 'life': st.get('life'),
                'max_life': st.get('max_life'), 'rupees': st.get('rupees'), 'prompt': st.get('prompt'), 'music': st.get('music'),
                'event': st.get('event'), 'time_s': st.get('t'), 'watched_flags': {k: v for k, v in flags.items() if v is not None}}

    def plan_data(self, st, why):
        ch = self.chapter
        digest = world_digest(st.get('area') or ch.area, st, plan=P.world_plan())
        done = [o for o in self.timeline]
        data = {
            'aim': ch.aim, 'why_now': why,
            'markers': [m.view() for m in self.markers],
            'link': self.state_view(st),
            'digest': digest,
            'hints': ch.hints,
            'outline': [{'kind': s.get('kind'), 'what': s.get('what')} for s in ch.seeds],
            'watched_flags': sorted(self.watched),
            'objectives_so_far': [{'id': o['id'], 'kind': o['kind'], 'what': o['what'], 'outcome': o['outcome'], 'game_s': o['game_s'], 'where': o.get('end_pos'),
                                   'steps': o.get('steps'), 'why_it_ended': o.get('why')} for o in done[-8:]],
            'rejected_last_time': self.rejected[-6:],
            'left': {'game_seconds': round(ch.budget_s - ((st.get('t') or 0) - (self.t0 or 0)), 1), 'usd': round(ch.budget_usd - (self.spent() - self.ledger0), 3),
                     'objectives': ch.max_objectives - len(self.timeline), 'replans': ch.max_replans - max(0, self.n_plan - 1)},
            'max_objectives_now': ch.per_plan,
        }
        if self.cover is not None:
            data['region'] = {'area': self.cover.area, 'visited': round(self.cover.fraction(), 3), 'unvisited_nearest': self.cover.unvisited(st.get('pos'))}
        return data, digest

    def ask_planner(self, st, why):
        """The next objectives from the model: [Objective]; [] when it gave none (no key, an error, nothing playable): the reason goes to the log."""
        if self.planner is None:
            return []
        data, digest = self.plan_data(st, why)
        less = self.pilot_kw.get('lessons')   # (lessons.Lessons, or None: off)
        got = less.for_chapter(data['link'], self.timeline) if less is not None else None
        if got and got['items']:
            data['lessons'] = got['items']   # (last: with none to give the request is what it was)
        self.n_plan += 1
        n = self.n_plan
        image = self.picture(f'plan-{n}')
        row = {'n': n, 'why': why, 't': st.get('t'), 'model': self.planner.model, 'image': self.looks[-1].get('file') if self.looks and 'file' in self.looks[-1] else None,
               'lessons': lessons_lib.record(less is not None, got), 'data': data}
        try:
            text, info = self.planner.ask(data, image)
            objs, rejected, reason = parse_plan(text, self.chapter, digest, self.watched, n)
            row.update(info, answer=json.loads(text), reason=reason, rejected=rejected, objectives=[o.id for o in objs])
            self.rejected = [{'id': i, 'why': w} for i, w in rejected]
        except (openai_api.NoKey, openai_api.CapReached, openai_api.ApiError, ValueError) as e:
            row.update(error=f'{type(e).__name__}: {e}'[:300])
            objs = []
            print(f'  planner call {n} failed: {row["error"]}', flush=True)
        self.cplans.append({k: v for k, v in row.items() if k != 'data'})
        with open(self.dir / 'plans.jsonl', 'a') as f:
            f.write(json.dumps(row) + '\n')
        if objs:
            print(f'  plan {n} ({why}): ' + '; '.join(f'{o.kind}: {o.what[:60]}' for o in objs), flush=True)
        return objs

    def seed_objectives(self):
        out = []
        for i, s in enumerate(self.chapter.seeds):
            try:
                out.append(objective_from_dict(s, self.chapter, 'seed', i + 1))
            except ValueError as e:
                self.rejected.append({'id': s.get('name'), 'why': str(e)[:160]})
        return out

    def next_objectives(self, st, why):
        got = self.ask_planner(st, why)
        if got:
            return got
        if not self.seeded:
            self.seeded = True
            return [o for o in self.seed_objectives() if not self.satisfied(o)]
        return []

    def credit(self, o, st):
        """An objective that was met serves the marker it names: a marker that only an objective's own proof can show is met now."""
        for m in self.markers:
            if m.by_objective and m.met_at is None and m.name == o.progress:
                m.met_at, m.met_area, m.met_pos = st.get('t'), st.get('area'), st.get('pos')
                print(f'  marker {m.name} met at {fmt_t(st.get("t"))} s by objective {o.id}', flush=True)

    def satisfied(self, o):
        m = next((m for m in self.markers if m.name == o.progress), None)
        return bool(m and m.met_at is not None)

    def end_with_marker(self, goal, o):
        """A plain walk (goal kind `cross`: a go_to objective) is met as well when the marker it serves holds, whatever the goal's own condition says (a height the
        map gave within 2 m): a rehearsal against a fake game walked to the marker's place and played on to the end of the objective's time. Every other kind (a chest,
        a talk, a sign, a song, a dive) keeps its own proof: a marker tied to it that holds on the way (Link 100 m from where he began, Link near the chest) does not
        end it (a sign was once marked solved, unread, because Link had walked 100 m)."""
        if goal.kind != 'cross':
            return
        cond = goal.cond
        own = getattr(cond, 'met_state', None)
        mine = next((m for m in self.markers if m.name == o.progress and not m.by_objective), None)

        def met_state(st):
            if own(st) if own else cond.met(st.get('flags') or {}):
                return True
            if self.cover is not None:
                self.cover.add(st)
            return mine is not None and mine.check(st)
        cond.met_state = met_state

    # -- running one objective

    def run_objective(self, o, st):
        """Play one objective with a pilot.Pilot of its own; the record of what happened."""
        ch = self.chapter
        here = st.get('pos')
        spec = {'name': o.id, 'what': o.what, 'area': st.get('area') or ch.area, 'goal': [goal_table(o, here)]}
        try:
            seg = P.Segment(self.seg.path, spec=spec)
        except (ValueError, KeyError, TypeError) as e:   # an objective that cannot be built (a flag text with no comparison, a place the model made up) is a failed one
            rec = {'id': o.id, 'kind': o.kind, 'what': o.what, 'source': o.source, 'progress': o.progress, 'start_t': st.get('t'), 'start_pos': here, 'area': st.get('area'),
                   'targets': [], 'outcome': f'rejected: {type(e).__name__}: {e}'[:200], 'goal_status': 'open', 'game_s': 0.0, 'wall_s': 0.0, 'decisions': 0, 'labels': {},
                   'end_pos': here, 'end_area': st.get('area'), 'steps': [], 'why': None, 'cost_usd': 0.0, 'markers_met': []}
            o.status, o.result = 'failed', rec
            self.timeline.append(rec)
            print(f'objective {o.id} could not be built: {rec["outcome"]}', flush=True)
            return rec, st, rec['outcome']
        t_now = st.get('t') or 0.0
        left = ch.budget_s - (t_now - self.t0)
        seg.budget = t_now + max(20.0, min(o.max_s, left))
        seg.max_decisions = ch.decisions_per_objective
        seg.watch = list(self.watched)
        goal = seg.goals[0]
        self.end_with_marker(goal, o)
        rec0 = {'id': o.id, 'kind': o.kind, 'what': o.what, 'source': o.source, 'progress': o.progress, 'start_t': t_now, 'start_pos': here, 'area': st.get('area'),
                'cost0': self.spent(), 'wall0': time.time(), 'targets': [{k: t.get(k) for k in ('name', 'at', 'y', 'radius')} for t in o.targets]}
        pilot = P.Pilot(seg, self.decider, self.ch, self.dir, self.run_id, self.alive, None, ch.decisions_per_objective, **self.pilot_kw)
        pilot.tried = self.tried
        self.current_id = o.id
        print(f'objective {o.id} [{o.kind}] {o.what[:100]}', flush=True)
        outcome = pilot.run(st)
        after = self.scan()
        self.pilots.append(pilot)
        self.decisions += pilot.decisions
        for k, v in pilot.skipped.items():
            self.skipped[k] = self.skipped.get(k, 0) + v
        self.frags += pilot.frags
        self.duel_seen = pilot.duel_seen or self.duel_seen
        steps = [{'step': t['step'], 'result': t['result'], 'moved_m': t.get('moved_m')} for t in pilot.tried[-60:] if t.get('goal') == o.id][-8:]
        reasons = []
        plan_note = next((m.get('plan') for m in pilot.mem.values() if isinstance(m, dict) and m.get('plan')), None)
        if plan_note and not plan_note.get('ok'):
            reasons.append(f"the offline planner: {plan_note.get('why')} (near {plan_note.get('near')}, after {plan_note.get('after')})")
        rs = pilot.recover_summary() if pilot.rec else {}
        if rs.get('blocks'):
            reasons.append(f"{rs['blocks']} block(s), longest {rs.get('longest_s')} s, rungs {rs.get('rungs')}")
        status = goal.status
        rec = {**rec0, 'outcome': 'solved' if status == 'met' else outcome, 'goal_status': status, 'game_s': round((after.get('t') or t_now) - t_now, 1),
               'wall_s': round(time.time() - rec0['wall0'], 1), 'decisions': len(pilot.decisions), 'labels': {k: pilot.decisions.count(k) for k in sorted(set(pilot.decisions))},
               'end_pos': after.get('pos'), 'end_area': after.get('area'), 'steps': steps, 'why': '; '.join(reasons) or None,
               'cost_usd': round(self.spent() - rec0['cost0'], 5), 'markers_met': [m.name for m in self.markers if m.met_at is not None and m.met_at >= t_now]}
        for k in ('cost0', 'wall0'):
            rec.pop(k)
        o.status, o.result = ('met' if status == 'met' else 'failed'), rec
        self.timeline.append(rec)
        self.current_id = None
        print(f'  -> {rec["outcome"]} in {rec["game_s"]} game s, {rec["decisions"]} decisions, {rec["cost_usd"]} USD', flush=True)
        return rec, after, outcome

    def run_wait_time(self, o, st):
        """Wait for day or night: look at the sky band's brightness every few seconds; play the song that moves the time (adult, when the local song file names it: actions.time_song) or wait."""
        t_now = st.get('t') or 0.0
        want = str(o.params.get('until') or 'day')
        reads, solved, why = [], False, None
        rec = {'id': o.id, 'kind': o.kind, 'what': o.what, 'source': o.source, 'progress': o.progress, 'start_t': t_now, 'start_pos': st.get('pos'), 'area': st.get('area'),
               'targets': [], 'cost_usd': 0.0, 'decisions': 0, 'labels': {}}
        wall0 = time.time()
        end_t = t_now + o.max_s
        song = None
        try:
            import actions
            notes = actions.song_buttons(actions.time_song() or '', actions.note_orders()[0]) if area_age(st.get('area') or '') == 'adult' else []
            song = notes or None
        except ImportError:
            pass
        sung = 0
        while self.alive():
            cur = self.scan()
            try:
                import vision
                if self.capture is None:
                    self.capture = vision.Capture(self.dir / 'looks', width=800, copy=self.copy, run_id=self.run_id)
                path, *_ = self.capture()
                lum = daylight_of(path)
                self.looks.append({'tag': f'time-{o.id}', 'file': f'looks/{Path(path).name}', 'brightness': lum})
            except Exception as e:   # noqa: BLE001
                lum, why = None, f'no picture: {type(e).__name__}: {e}'[:160]
            reads.append({'t': cur.get('t'), 'brightness': lum, 'class': day_class(lum)})
            if day_class(lum) == want:
                solved = True
                break
            if (cur.get('t') or 0) >= end_t:
                break
            lines = ['wait 12']
            if song and sung < 2 and (cur.get('t') or 0) - t_now > 20:
                lines, sung = [f'ocarina {" ".join(song)}', 'wait 4'], sung + 1
            P.Pilot.sync(self, lines, 60 + (30 if sung else 0))   # (steps sent, then the state line after them: the pilot's own way)
        after = self.scan()
        rec.update({'outcome': 'solved' if solved else 'budget: time', 'goal_status': 'met' if solved else 'open', 'game_s': round((after.get('t') or t_now) - t_now, 1),
                    'wall_s': round(time.time() - wall0, 1), 'end_pos': after.get('pos'), 'end_area': after.get('area'),
                    'steps': [{'step': 'look', 'result': f"{r['class']} ({r['brightness']})", 'moved_m': 0} for r in reads[-6:]], 'why': why, 'markers_met': []})
        o.status, o.result = ('met' if solved else 'failed'), rec
        self.timeline.append(rec)
        return rec, after, rec['outcome']

    # -- the chapter

    def run(self, first_state):
        ch = self.chapter
        st = first_state
        self.t0 = st.get('t') or 0.0
        self.seeded = False
        outcome = None
        failures_in_a_row = 0
        self.scan()
        for m in self.markers:
            m.check(st)
        why = 'start'
        while True:
            st = self.scan() or st
            if all(m.met_at is not None for m in self.markers if m.required):
                outcome = 'solved'
                break
            if not self.alive():
                outcome = 'the game ended'
                break
            t = st.get('t') or 0.0
            if t - self.t0 > ch.budget_s:
                outcome = f'budget: {ch.budget_s:g} s of game time'
                break
            if self.spent() - self.ledger0 > ch.budget_usd:
                outcome = f'budget: {ch.budget_usd:g} USD'
                break
            if len(self.timeline) >= ch.max_objectives:
                outcome = f'budget: {ch.max_objectives} objectives'
                break
            if getattr(self.decider, 'stop_reason', None):
                outcome = f'stopped: {self.decider.stop_reason}'
                break
            if not self.queue:
                if self.n_plan and self.n_plan > ch.max_replans:
                    outcome = f'gave up: {ch.max_replans} replans'
                    break
                self.queue = self.next_objectives(st, why)
                if not self.queue:
                    failures_in_a_row += 1
                    if failures_in_a_row >= 2 or self.seeded and not self.planner:
                        outcome = 'gave up: no objective to play'
                        break
                    why = 'the last plan gave no objective that can be played'
                    continue
                failures_in_a_row = 0
            o = self.queue.pop(0)
            if self.satisfied(o):
                continue
            rec, st, o_outcome = (self.run_wait_time if o.kind == 'wait_time' else self.run_objective)(o, st)
            if o.status == 'met':
                self.credit(o, st)
                why = 'queue empty' if not self.queue else 'continue'
            else:
                self.queue = []   # the rest of the plan was made for a world this objective did not reach
                why = f'objective {o.id} failed: {rec["outcome"]}'
            if o_outcome in ('the game ended', 'the game stopped answering') or str(o_outcome).startswith('stopped:'):
                outcome = o_outcome
                break
        self.outcome = outcome
        self.last_st = st
        return outcome

    def recover_summary(self):
        rows = [p.recover_summary() for p in self.pilots]
        out = {'on': bool(rows and rows[0].get('on')), 'blocks': sum(r.get('blocks', 0) for r in rows), 'recovered': sum(r.get('recovered', 0) for r in rows),
               'marked_bad': sum(r.get('marked_bad', 0) for r in rows), 'left': sum(r.get('left', 0) for r in rows), 'open': sum(r.get('open', 0) for r in rows),
               'longest_s': max((r.get('longest_s', 0.0) for r in rows), default=0.0), 'over_10s': sum(r.get('over_10s', 0) for r in rows),
               'stuck_steps': sum(r.get('stuck_steps', 0) for r in rows), 'rungs': {}, 'planner_replans': 0, 'no_question': dict(self.skipped),
               'episodes': [e for r in rows for e in r.get('episodes', [])]}
        if any('tactics' in r for r in rows):   # the tactics library (tactics.py): the causes of the blocks and what each tactic did, over every objective's pilot
            out['mode'] = next(r['mode'] for r in rows if 'mode' in r)
            out['causes'], out['tactics'] = {}, {}
            for r in rows:
                for c, n in (r.get('causes') or {}).items():
                    out['causes'][c] = out['causes'].get(c, 0) + n
                for t, v in (r.get('tactics') or {}).items():
                    a = out['tactics'].setdefault(t, {'tried': 0, 'worked': 0})
                    a['tried'] += v['tried']
                    a['worked'] += v['worked']
        return out

    # -- what the chapter leaves

    def costs(self):
        try:
            return openai_api.summary(self.run_id, standin=bool(getattr(self.args, 'api_base', None)))
        except Exception:   # noqa: BLE001
            return {}

    def summary(self):
        ch = self.chapter
        return {'chapter': ch.name, 'aim': ch.aim, 'outcome': self.outcome, 'save': ch.save,
                'markers': [m.view() | {'area': m.met_area, 'pos': m.met_pos} for m in self.markers],
                'coverage': None if self.cover is None else round(self.cover.fraction(), 3),
                'objectives': len(self.timeline), 'objectives_met': sum(1 for o in self.timeline if o['goal_status'] == 'met'),
                'timeline': self.timeline, 'plans': [{k: p.get(k) for k in ('n', 'why', 't', 'model', 'cost_usd', 'latency_ms', 'reason', 'objectives', 'rejected', 'error', 'image')}
                                                     for p in self.cplans],
                'plan_cost_usd': round(sum(float(p.get('cost_usd') or 0) for p in self.cplans), 5), 'cost_usd': round(self.spent() - self.ledger0, 5),
                'costs_by_kind': self.costs(), 'anomalies': self.anomalies, 'looks': self.looks, 'rejected': self.rejected}

    def write(self):
        for g, m in zip(self.seg.goals, self.markers):   # (cmd_run's summary reads the pseudo-goals' statuses)
            g.status = 'met' if m.met_at is not None else 'open'
        s = self.summary()
        (self.dir / 'chapter.json').write_text(json.dumps(s, indent=1))
        (self.dir / 'timeline.md').write_text(timeline_md(s))
        return s


def timeline_md(s):
    lines = [f"# Chapter {s['chapter']}: {s['outcome']}", '', f"Aim: {s['aim']}", '', '## Progress', '']
    for m in s['markers']:
        lines.append(f"* {'met' if m['met'] else 'NOT met'} `{m['name']}`: {m['what']} ({m['when']})" + (f" at {fmt_t(m['met_at_t'])} s in {m['area']}" if m['met'] else ''))
    if s.get('coverage') is not None:
        lines.append(f"* region visited: {s['coverage']:.0%}")
    lines += ['', '## Timeline', '', '| # | objective | kind | game s | outcome | decisions | USD | where it ended |', '|---|---|---|---|---|---|---|---|']
    for i, o in enumerate(s['timeline'], 1):
        end = o.get('end_pos')
        lines.append(f"| {i} | {o['id']}: {o['what'][:70]} | {o['kind']} | {o['game_s']} | {o['outcome']} | {o['decisions']} | {o['cost_usd']} | "
                     f"{o.get('end_area')} {[round(v, 1) for v in end] if end else ''} |")
    stuck = [o for o in s['timeline'] if o['goal_status'] != 'met']
    if stuck:
        lines += ['', '## Where it got stuck and why', '']
        for o in stuck:
            tail = ', '.join(f"{t['step']}:{t['result']}" for t in (o.get('steps') or [])[-6:])
            lines.append(f"* `{o['id']}` ({o['kind']}): {o['outcome']}; last steps: {tail or 'none'}" + (f"; {o['why']}" if o.get('why') else ''))
    lines += ['', '## Plans', '']
    for p in s['plans']:
        lines.append(f"* plan {p['n']} ({p['why']}) {p.get('model')}: {p.get('cost_usd')} USD, {p.get('latency_ms')} ms; {p.get('reason') or p.get('error')}")
    lines += ['', f"Cost: {s['cost_usd']} USD in all, {s['plan_cost_usd']} USD for the plans.", '']
    if s['anomalies']:
        lines += ['## Anomalies', ''] + [f"* {a['kind']} at {fmt_t(a['t'])} s in {a['area']} {a.get('pos')}: {a['detail']} (objective {a.get('objective')})" for a in s['anomalies']] + ['']
    return '\n'.join(lines)


def make_pilot(chapter_seg, decider, ch, run_dir, run_id, alive, planner=None, max_decisions=None, **kw):
    """pilot.cmd_run's factory for a chapter (copy, client and args come as keywords)."""
    extra = {k: kw.pop(k) for k in ('copy', 'client', 'args') if k in kw}
    return ChapterPilot(chapter_seg, decider, ch, run_dir, run_id, alive, planner, max_decisions, **extra, **kw)


def segment_for(chapter):
    return ChapterSegment(chapter, [Marker(d) for d in chapter.marker_specs])


# ---- command line

def cmd_check(args):
    ch = load(args.chapter)
    seg = segment_for(ch)
    print(f'chapter {ch.name}: {ch.aim}')
    print(f'  save {ch.save}, boot {ch.boot}, area {ch.area}, wall {ch.wall} s, {ch.budget_s:g} game s, {ch.budget_usd:g} USD, {ch.max_objectives} objectives, {ch.max_replans} replans')
    for m in ch.marker_specs:
        print(f"  marker {m['name']}: {Marker(m).text}{'' if m.get('required', True) else ' (optional)'}")
    for s in ch.seeds:
        o = objective_from_dict(s, ch, 'seed')
        print(f'  seed {o.id} [{o.kind}] {o.what[:80]} ({o.max_s:g} s)')
    print(f'  watches {len(seg.watch)} flags: {", ".join(seg.watch)}')
    return 0


def cmd_digest(args):
    st = {'pos': [args.x, args.y, args.z] if args.x is not None else None, 'area': args.area}
    print(json.dumps(world_digest(args.area, st, plan=P.world_plan()), indent=1))
    return 0


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('check')
    c.add_argument('chapter')
    d = sub.add_parser('digest')
    d.add_argument('area')
    d.add_argument('x', nargs='?', type=float)
    d.add_argument('z', nargs='?', type=float)
    d.add_argument('--y', type=float, default=0.0)
    a = ap.parse_args()
    if a.cmd == 'digest' and a.x is not None and a.z is None:
        ap.error('digest <area> [x z]')
    return {'check': cmd_check, 'digest': cmd_digest}[a.cmd](a)


if __name__ == '__main__':
    sys.modules.setdefault('pilot', __import__('pilot'))
    sys.exit(main())
