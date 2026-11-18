#!/usr/bin/env python3
"""Scenarios: a targeted test written down so that any runner can play it. A scenario names a place (a map, an age, an hour, and when a bug report
gives them the player's coordinates), a list of ACTIONS and what to look for; it is the unit of a reproduction attempt ("issue N: reproduced / not on
this hardware, with what was tried") as well as of a regression check or a coverage visit. Format `ls-scenario/1` (TOML). This module reads and
checks one, compiles it to hsap steps (Linux harness), imports one from an issue's or a bug report's text,
and judges a run folder against its `expect` list. Nothing of the game is named here: map names come from the destinations list the caller passes.

    scenario.py check  F.toml                       the file's problems (unconfirmed actions are listed)
    scenario.py steps  F.toml [--world DIR]         the hsap steps it compiles to (tags in the right-hand column)
    scenario.py import (--issue N | --text FILE) --destinations D.json --out F.toml [--ref URL]   a draft for a person to confirm
    scenario.py eval   F.toml RUN [--out R.json]    the verdict of a played run (RUN: a hunt session folder)

place:  [at] map = "<destination the game lists>", age = "child"|"adult", hour = 0..23, x/y/z (metres), facing (degrees)
        placement = the debug teleport to the map (and age, hour); with x and z Link is then taken to the point: the debug tools' coordinate warp when
        the debug tools have one (the position read back), else the pilot's path-finding (a `go_near` leg) and the distance reached is reported.
action: do = wait | press | walk | go_near | repeat | open_map | fight_loop | cross | enter | roam | shot | note | rendezvous  (table below)
expect: check = crash | spikes | visual | distance, each with its own keys
"""
import json
import math
import os
import re
import sys
import tomllib
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

FORMAT = 'ls-scenario/1'
PURPOSES = ('reproduce', 'regression', 'coverage')
BUTTONS = ('A', 'B', 'X', 'Y', 'L', 'R', 'ZL', 'ZR', 'PLUS', 'MINUS', 'LEFT', 'UP', 'RIGHT', 'DOWN', 'LS', 'RS')
ACTIONS = {
    'wait': {'s': (float, 1.0)},
    'press': {'button': (str, None), 'ms': (int, 200)},
    'walk': {'x': (float, None), 'z': (float, None), 'radius': (float, 1.5), 'timeout': (float, 20.0)},
    'go_near': {'x': (float, None), 'z': (float, None), 'radius': (float, 2.5), 'timeout': (float, 40.0)},
    'repeat': {'n': (int, None), 'actions': (list, None)},
    'open_map': {'cycles': (int, 1), 'button': (str, 'MINUS'), 'close_button': (str, 'B'), 'ms': (int, 200), 'open_s': (float, 1.5), 'closed_s': (float, 1.5)},
    'fight_loop': {'rounds': (int, 10), 'swings': (int, 3), 'swing_gap_s': (float, 0.35), 'round_gap_s': (float, 1.2), 'lock_ms': (int, 800)},
    'cross': {'there': (list, None), 'back': (list, None), 'cycles': (int, 1), 'timeout': (float, 40.0)},
    'enter': {'x': (float, None), 'z': (float, None), 'through_x': (float, None), 'through_z': (float, None), 'timeout': (float, 40.0)},
    'roam': {'count': (int, 10), 'min_m': (float, 15.0), 'max_m': (float, 70.0), 'seed': (int, 1), 'radius': (float, 2.5)},
    'chest': {'timeout': (float, 0.0)},
    'interact': {'timeout': (float, 0.0)},
    'pickup': {'x': (float, None), 'z': (float, None), 'radius': (float, 1.0), 'timeout': (float, 20.0), 'press': (bool, False)},
    'stick': {'dir': (str, None), 'ms': (int, 1000)},
    'teleport': {'index': (int, None)},
    'shot': {},
    'note': {'text': (str, None)},
    'rendezvous': {'name': (str, None), 'timeout': (float, 240.0)},
}
CHECKS = {
    'crash': {},
    'spikes': {'ms': (float, 50.0), 'during': (list, None), 'factor': (float, 3.0), 'min_spikes': (int, 3), 'min_window_s': (float, 20.0)},
    'visual': {'subs': (list, ['black', 'frozen', 'flicker', 'corrupt', 'missing_textures', 'stretched_textures', 'body_wrong', 'void'])},
    'key': {'key': (str, None)},
    'counter': {'flag': (str, None), 'max': (int, 1)},
    'clean': {'ignore': (list, [])},
    'distance': {'max_m': (float, 5.0)},
    'reached': {'tags': (list, None), 'share': (float, 1.0), 'src': (str, '')},
    'visited': {'map': (str, ''), 'music': (str, ''), 'who': (str, 'both')},
}
KEYS_TOP = {'format', 'name', 'purpose', 'claim', 'source', 'players', 'runnable', 'at', 'action', 'expect', 'confirm', 'env', 'build', 'notes', 'save', 'save_b', 'watch', 'link_ms', 'hold_s'}
KEYS_AT = {'map', 'age', 'hour', 'x', 'y', 'z', 'facing', 'from'}


class ScenarioError(Exception):
    pass


ENV_FORGE, ENV_FORGE_LOCK = 'SCENARIO_FORGE', 'SCENARIO_FORGE_LOCK'   # this machine's own settings (the project's page on its forge, the lock its readers share): environment, no default


def forge_addresses():
    """(the issue API's base, the issue pages' base) from $SCENARIO_FORGE, the project's page on its forge (`https://HOST/OWNER/REPO`); the API
    is read at `https://HOST/api/v1/repos/OWNER/REPO` (the Gitea / Forgejo layout), a page at `.../OWNER/REPO/issues/N`."""
    repo = (os.environ.get(ENV_FORGE) or '').rstrip('/')
    u = urlsplit(repo)
    if u.scheme not in ('http', 'https') or not u.netloc or u.query or u.fragment or u.path.strip('/').count('/') != 1 or '//' in u.path:
        raise ScenarioError(f'set {ENV_FORGE} to the project\'s page on its forge, https://HOST/OWNER/REPO (this machine\'s own value; there is no default)')
    return f'{u.scheme}://{u.netloc}/api/v1/repos{u.path}', repo + '/issues/'


# ---- reading and checking

def load(path):
    try:
        d = tomllib.loads(Path(path).read_text())
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise ScenarioError(f'cannot read {path}: {e}')
    errs = problems(d)
    if errs:
        raise ScenarioError(f'{path}: ' + '; '.join(errs))
    return d


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_action(a, where, errs):
    if not isinstance(a, dict) or a.get('do') not in ACTIONS:
        errs.append(f'{where}: do is one of {", ".join(ACTIONS)}')
        return
    spec = ACTIONS[a['do']]
    if a.get('who') not in (None, 'A', 'B', 'both'):
        errs.append(f'{where}: who is A, B or both')
    extra = sorted(set(a) - set(spec) - {'do', 'tag', 'confirmed', 'source', 'why', 'who'})
    if extra:
        errs.append(f'{where}: unknown keys {", ".join(extra)}')
    for k, (kind, default) in spec.items():
        v = a.get(k, default)
        if v is None:
            if a['do'] == 'enter' and k in ('through_x', 'through_z'):
                continue
            errs.append(f'{where}: {k} is required')
        elif kind is bool and not isinstance(v, bool) or kind is float and not _num(v) or kind is int and (not isinstance(v, int) or isinstance(v, bool)) or kind is str and not isinstance(v, str) or kind is list and not isinstance(v, list):
            errs.append(f'{where}: {k} is a {kind.__name__}')
    if a['do'] == 'press' and a.get('button') not in BUTTONS:
        errs.append(f'{where}: button is one of {", ".join(BUTTONS)}')
    if a['do'] == 'stick' and a.get('dir') not in ('up', 'down', 'left', 'right', 'up-left', 'up-right', 'down-left', 'down-right'):
        errs.append(f'{where}: dir is up, down, left, right or a diagonal')
    if a['do'] == 'open_map':
        for k in ('button', 'close_button'):
            if a.get(k, ACTIONS['open_map'][k][1]) not in BUTTONS:
                errs.append(f'{where}: {k} is one of the buttons')
    if a['do'] == 'repeat':
        for i, sub in enumerate(a.get('actions') or []):
            check_action(sub, f'{where}.actions[{i}]', errs)
    if a['do'] == 'cross':
        for k in ('there', 'back'):
            v = a.get(k)
            if isinstance(v, list) and (len(v) not in (2, 4) or not all(_num(x) for x in v)):
                errs.append(f'{where}: {k} is [x, z] or [x, z, through_x, through_z]')


def problems(d):
    errs = []
    if d.get('format') != FORMAT:
        errs.append(f'format is "{FORMAT}"')
    bad = sorted(set(d) - KEYS_TOP)
    if bad:
        errs.append('unknown keys ' + ', '.join(bad))
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', str(d.get('name') or '')):
        errs.append('name: 1 to 64 letters, digits, . _ -')
    if d.get('purpose') not in PURPOSES:
        errs.append('purpose is one of ' + ', '.join(PURPOSES))
    if not d.get('claim'):
        errs.append('claim: what this scenario is for, in a sentence')
    if d.get('players', 1) not in (1, 2):
        errs.append('players is 1 or 2')
    at = d.get('at')
    if not isinstance(at, dict) or not at.get('map'):
        errs.append('at.map is required (a destination the game lists)')
    else:
        bad = sorted(set(at) - KEYS_AT)
        if bad:
            errs.append('at: unknown keys ' + ', '.join(bad))
        if at.get('age') not in (None, 'child', 'adult'):
            errs.append('at.age is child or adult')
        h = at.get('hour')
        if h is not None and (isinstance(h, bool) or not isinstance(h, int) or not 0 <= h <= 23):
            errs.append('at.hour is a whole hour 0 to 23')
        for k in ('x', 'y', 'z', 'facing'):
            if k in at and not _num(at[k]):
                errs.append(f'at.{k} is a number')
        if at.get('from') not in (None, 'save'):
            errs.append('at.from is "save" (start where the save puts Link: no placement) or absent')
        if ('x' in at) != ('z' in at):
            errs.append('at: x and z come together (y is optional)')
    if d.get('players', 1) == 1 and any(isinstance(a, dict) and a.get('who') in ('A', 'B') for a in (d.get('action') or [])):
        errs.append('who A/B is for players = 2')
    if d.get('players', 1) == 2 and not d.get('save'):
        errs.append('a pair names the save both players start from (save = "<library entry>")')
    acts = d.get('action') or []
    if not isinstance(acts, list) or not acts and not (isinstance(at, dict) and 'x' in at):
        errs.append('action: at least one [[action]] (or coordinates to go to)')
    for i, a in enumerate(acts if isinstance(acts, list) else []):
        check_action(a, f'action[{i}]', errs)
    for i, e in enumerate(d.get('expect') or []):
        if not isinstance(e, dict) or e.get('check') not in CHECKS:
            errs.append(f'expect[{i}]: check is one of {", ".join(CHECKS)}')
            continue
        extra = sorted(set(e) - set(CHECKS[e['check']]) - {'check', 'why'})
        if extra:
            errs.append(f'expect[{i}]: unknown keys {", ".join(extra)}')
        for k, (kind_, default) in CHECKS[e['check']].items():
            if default is None and k not in e:
                errs.append(f'expect[{i}]: {k} is required')
        if e['check'] == 'visited' and not (e.get('map') or e.get('music')):
            errs.append(f'expect[{i}]: visited needs a map or a music')
    if d.get('purpose') == 'reproduce' and not d.get('expect'):
        errs.append('a reproduce scenario says what to look for (expect)')
    return errs


def unconfirmed(d):
    """The actions an importer proposed that a person has not confirmed (`confirmed = false`): a runner refuses these unless told to go on."""
    out = []

    def walk(acts, path):
        for i, a in enumerate(acts or []):
            if isinstance(a, dict) and a.get('confirmed') is False:
                out.append(f'{path}[{i}] {a.get("do")}')
            if isinstance(a, dict) and a.get('do') == 'repeat':
                walk(a.get('actions'), f'{path}[{i}].actions')
    walk(d.get('action'), 'action')
    return out


def place_spec(d):
    """The `[place]` table for placement.py: the debug teleport to the map with age and hour, and the coordinates when there are some (placement.py warps
    there when the debug tools can; the run's own leg to the point is the fallback)."""
    at = d['at']
    if at.get('from') == 'save':
        return None
    return {k: at[k] for k in ('age', 'hour', 'x', 'y', 'z', 'facing') if at.get(k) is not None} | {'to': at['map']}


def goto_of(d):
    at = d['at']
    return (float(at['x']), float(at['z'])) if 'x' in at and 'z' in at else None


# ---- compiling to hsap steps

def _fmt(v):
    return f'{v:.2f}' if isinstance(v, float) else str(v)


def compile_steps(d, world=None, goto=True, side=None):
    """[(hsap step line, tag)] for the scenario (no `watch`, no `end`). tag = the action's `tag` or its name (`goto` for the leg to the coordinates:
    left out with goto=False when the debug tools warped Link there). `world` = {'plan': fn, 'start': fn} (a private world model) lets `go_near`
    and `roam` become the planner's own steps; without it `go_near` is one `walk` and `roam` is refused."""
    out = []
    at = d['at']
    start = None
    if world and world.get('start'):
        start = world['start'](at['map'])

    def emit(line, tag):
        out.append((line, tag))

    def go_near(x, z, radius, timeout, tag):
        if world and start:
            r = world['plan'](at['map'], (start[0], start[2]), (x, z), from_y=start[1], to_y=at.get('y', start[1]), radius=radius)
            if not r.get('ok') and r.get('why') == 'off-mesh' and world.get('snap'):   # a point off the walkable mesh (a load zone's trigger, a spot over a ledge): go to the nearest walkable point
                snapped = world['snap'](at['map'], x, z)   # (x, z) or (x, z, y): the planner wants the height of the level it is to reach
                sx, sz = snapped[0], snapped[1]
                r = world['plan'](at['map'], (start[0], start[2]), (sx, sz), from_y=start[1], to_y=snapped[2] if len(snapped) > 2 else at.get('y', start[1]), radius=radius)
            steps = r.get('steps') or []
            if steps:
                for s in steps:
                    emit(s if 'timeout' in s else f'{s} timeout {int(timeout)}', tag)
                if not r.get('ok'):   # the planner got part of the way (a door, a gate, a ledge it cannot pass): say so, then steer straight at the point for the rest
                    emit(f'# the planner stopped short ({r.get("why")}): {str(r.get("detail") or "")[:120]}', 'note')
                    emit(f'walk {_fmt(x)} {_fmt(z)} radius {_fmt(radius)} timeout {int(timeout)}', tag)
                return
        emit(f'walk {_fmt(x)} {_fmt(z)} radius {_fmt(radius)} timeout {int(timeout)}', tag)

    def run(acts, tagpath=''):
        for i, a in enumerate(acts or []):
            do = a['do']
            tag = a.get('tag') or do
            if side is not None and a.get('who', 'both') not in ('both', side):   # a pair: this player's own steps
                continue
            if do == 'wait':
                emit(f'wait {_fmt(a.get("s", 1.0))}', tag)
            elif do == 'press':
                emit(f'press {a["button"]} {a.get("ms", 200)}', tag)
            elif do == 'walk':
                emit(f'walk {_fmt(a["x"])} {_fmt(a["z"])} radius {_fmt(a.get("radius", 1.5))} timeout {int(a.get("timeout", 20))}', tag)
            elif do == 'go_near':
                go_near(float(a['x']), float(a['z']), float(a.get('radius', 2.5)), float(a.get('timeout', 40)), tag)
            elif do == 'repeat':
                for _ in range(int(a['n'])):
                    run(a['actions'], tagpath)
            elif do == 'open_map':
                for _ in range(int(a.get('cycles', 1))):
                    emit(f'press {a.get("button", "MINUS")} {a.get("ms", 200)}', tag)
                    emit(f'wait {_fmt(float(a.get("open_s", 1.5)))}', tag)
                    emit(f'press {a.get("close_button", "B")} {a.get("ms", 200)}', tag)
                    emit(f'wait {_fmt(float(a.get("closed_s", 1.5)))}', tag)
            elif do == 'fight_loop':
                for _ in range(int(a.get('rounds', 10))):
                    emit(f'ztarget {a.get("lock_ms", 800)}', tag)
                    for k in range(int(a.get('swings', 3))):
                        emit('swing', tag)
                        emit(f'wait {_fmt(float(a.get("swing_gap_s", 0.35)))}', tag)
                    emit(f'wait {_fmt(float(a.get("round_gap_s", 1.2)))}', tag)
            elif do == 'enter':
                line = f'enter {_fmt(float(a["x"]))} {_fmt(float(a["z"]))}'
                if a.get('through_x') is not None:
                    line += f' through {_fmt(float(a["through_x"]))} {_fmt(float(a["through_z"]))}'
                emit(f'{line} timeout {int(a.get("timeout", 40))}', tag)
            elif do == 'cross':
                for _ in range(int(a.get('cycles', 1))):
                    for leg in (a['there'], a['back']):
                        line = f'enter {_fmt(float(leg[0]))} {_fmt(float(leg[1]))}'
                        if len(leg) == 4:
                            line += f' through {_fmt(float(leg[2]))} {_fmt(float(leg[3]))}'
                        emit(f'{line} timeout {int(a.get("timeout", 40))}', tag)
            elif do == 'roam':
                if not (world and world.get('targets') and start):
                    raise ScenarioError('roam needs the world model (a private folder): pass world=')
                import random
                pts = world['targets'](at['map'], start, random.Random(int(a.get('seed', 1))), int(a.get('count', 10)), min_m=float(a.get('min_m', 15.0)), max_m=float(a.get('max_m', 70.0)))
                cx, cz = start[0], start[2]
                for (x, z, y) in pts:
                    go_near(x, z, float(a.get('radius', 2.5)), 30.0, tag)
            elif do in ('chest', 'interact'):
                emit(do + (f' timeout {int(a["timeout"])}' if a.get('timeout') else ''), tag)
            elif do == 'pickup':
                emit(f'pickup {_fmt(float(a["x"]))} {_fmt(float(a["z"]))} radius {_fmt(float(a.get("radius", 1.0)))} timeout {int(a.get("timeout", 20))}' + (' press' if a.get('press') else ''), tag)
            elif do == 'stick':
                emit(f'stick {a["dir"]} {int(a.get("ms", 1000))}', tag)
            elif do == 'teleport':   # the Debug tab's teleport by its list index (`!cheat 1000 + index`)
                emit(f'cheat {1000 + int(a["index"])}', tag)
            elif do == 'shot':
                emit('shot', tag)
            elif do == 'note':
                emit('# ' + str(a['text']).replace('\n', ' ')[:200], 'note')
            elif do == 'rendezvous':
                emit(f'rendezvous {a["name"]} timeout {int(a.get("timeout", 240))}', tag)
    g = goto_of(d)
    if g and goto and side in (None, 'A', 'B'):
        go_near(g[0], g[1], 2.5, 60.0, 'goto')
    run(d.get('action'))
    return out


# ---- the importer (a draft for a person to confirm: nothing is guessed silently)

SECTION = re.compile(r'^#{2,4}\s*(.+?)\s*$', re.M)
NUM = r'(-?\d+(?:\.\d+)?)'
COORD_LABELLED = re.compile(r'(?is)\bx\s*[:=]\s*' + NUM + r'[\s,;/|]+y\s*[:=]\s*' + NUM + r'[\s,;/|]+z\s*[:=]\s*' + NUM)
COORD_TUPLE = re.compile(r'(?is)\b(?:pos(?:ition)?|coords?|coordinates|location)\b[^\d\-\n]{0,12}\(?\[?\s*' + NUM + r'\s*[,;]\s*' + NUM + r'\s*[,;]\s*' + NUM)
FACING = re.compile(r'(?i)\b(?:facing|yaw|heading)\b\s*[:=]?\s*' + NUM)
HOURS = (('midnight', 0), ('dawn', 6), ('sunrise', 6), ('noon', 12), ('midday', 12), ('dusk', 18), ('sunset', 18), ('night', 23), ('daytime', 12), ('day time', 12))
HOUR_CLOCK = re.compile(r'(?i)\b(?:time|clock|at)\b[^\d\n]{0,12}\b([01]?\d|2[0-3]):([0-5]\d)\b')


def sections(text):
    """{lowercased heading: text} of an issue form's `### heading` blocks (the text before the first heading is `_`)."""
    out, last, pos = {}, '_', 0
    for m in SECTION.finditer(text):
        out[last] = out.get(last, '') + text[pos:m.start()]
        last, pos = m.group(1).strip().lower(), m.end()
    out[last] = out.get(last, '') + text[pos:]
    return out


def aliases_of(destinations):
    """{alias: [destination, ...]} from the game's destination names alone: the age suffix (child or adult) dropped, CamelCase split into lower-case words, a leading 'inside the' dropped as a second alias."""
    out = {}
    for name in destinations:
        base = re.sub(r'_(Child|Adult)$', '', name)
        words = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', base.replace('_', ' ')).lower()
        out.setdefault(words, []).append(name)
        no_the = re.sub(r'^(inside the|inside) ', '', words)
        if no_the != words:
            out.setdefault(no_the, []).append(name)
    return out


def find_map(text, aliases):
    """(destination alias words, the destinations it names) for the earliest-longest alias in `text`, or (None, [])."""
    low = text.lower()
    best = None
    for alias in sorted(aliases, key=len, reverse=True):
        m = re.search(r'(?<![a-z])' + re.escape(alias).replace(r'\ ', r'[\s\-_]*') + r"(?:'s)?(?![a-z])", low)
        if m and (best is None or m.start() < best[0] or (m.start() == best[0] and len(alias) > len(best[1]))):
            best = (m.start(), alias)
    return (best[1], aliases[best[1]]) if best else (None, [])


def pick_destination(cands, age):
    if age:
        for c in cands:
            if c.endswith('_' + age.capitalize()):
                return c
    for c in cands:
        if c.endswith('_Child'):
            return c
    return cands[0] if cands else None


def import_text(title, body, destinations, ref='', name=None, aliases=None, extra_aliases=None):
    """A scenario draft (a dict that `dumps` writes) from an issue's or a bug report's text. The map is the earliest destination name in the
    `where` section, else the title, else the body; the coordinates, the facing, the age and the hour only when the text says them; every sentence
    of the reporter's description is listed as `confirm`; actions are proposed from a few words and marked `confirmed = false`."""
    aliases = aliases or aliases_of(destinations)
    for k, v in (extra_aliases or {}).items():   # what players call a place that is not the destination's own name (`town square`): a person's table
        aliases.setdefault(k.lower(), []).append(v)
    secs = sections(body)
    where = ' '.join(v for k, v in secs.items() if k.startswith('where'))
    what = ' '.join(v for k, v in secs.items() if k.startswith(('what happened', 'steps')))
    full = f'{title}\n{body}'
    alias, cands = (None, [])
    for src in (where, title, what, full):
        alias, cands = find_map(src, aliases)
        if cands:
            break
    others = sorted(a for a in aliases if a != alias and find_map(where or full, {a: aliases[a]})[1])
    age = None
    m = re.search(r'(?i)\b(adult|child|young)\s+link\b|\bas (?:an? )?(adult|child)\b', full)
    if m:
        age = 'adult' if 'adult' in m.group(0).lower() else 'child'
    at = {}
    notes = []
    dest = pick_destination(cands, age)
    if dest:
        at['map'] = dest
        if len(cands) > 1 and not age:
            notes.append(f'the text names "{alias}" without an age: the {dest.rsplit("_", 1)[-1].lower()} map was taken (the other is {", ".join(c for c in cands if c != dest)})')
        if age:
            at['age'] = age
    else:
        notes.append('no map of the destinations list is named in the text: at.map must be written by a person')
    if others and dest:
        notes.append('the text also names: ' + ', '.join(others[:6]) + ' (one map was taken: a person picks the one the fault is in)')
    c = COORD_LABELLED.search(full) or COORD_TUPLE.search(full)
    if c and dest:
        at['x'], at['y'], at['z'] = (float(c.group(i)) for i in (1, 2, 3))
        f = FACING.search(full)
        if f:
            at['facing'] = float(f.group(1))
    elif dest:
        notes.append('no coordinates in the text: the scenario goes to the map (its entrance) only')
    hour = None
    hc = HOUR_CLOCK.search(full)
    if hc:
        hour = int(hc.group(1))
    else:
        for word, h in HOURS:
            if re.search(r'(?i)\b' + word + r'\b', full):
                hour = h
                break
    if hour is not None and dest:
        at['hour'] = hour
    low = full.lower()
    expect = []
    if re.search(r'crash|freeze|froze|black screen|device lost|driver (?:fail|timeout)|closed unexpectedly', low):
        expect.append({'check': 'crash', 'why': 'the text says the game crashes or freezes'})
    if re.search(r'frame spike|spikes|stutter|hitch|lag|slowdown|slow down|fps', low):
        expect.append({'check': 'spikes', 'why': 'the text reports spikes, stutter or a slowdown'})
    if re.search(r'corrupt|glitch|texture|flicker|artifact|artefact', low):
        expect.append({'check': 'visual', 'why': 'the text reports a rendering fault'})
    if 'x' in at:
        expect.append({'check': 'distance', 'max_m': 5.0, 'why': 'the text gives coordinates: report how near the run got'})
    actions = []
    if re.search(r'\bmap\b', low) and re.search(r'\bopen(?:ing|ed)?\b', low) and re.search(r'\bclos(?:e|ing|ed)\b', low):
        actions.append({'do': 'open_map', 'cycles': 10, 'confirmed': False, 'source': 'the text opens and closes the map', 'tag': 'map'})
    if re.search(r'\b(?:kill(?:ed|ing)?|enem(?:y|ies)|fight|skeletons?)\b', low) and re.search(r'\b(?:kill|die|dies|died|dead|defeat)', low):
        actions.append({'do': 'fight_loop', 'rounds': 12, 'confirmed': False, 'source': 'the text kills enemies', 'tag': 'fight'})
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', (what or where or title)) if len(s.strip()) > 12][:12]
    return {'format': FORMAT, 'name': name or re.sub(r'[^A-Za-z0-9._-]+', '-', f'import-{ref.rsplit("/", 1)[-1] or title[:30]}').strip('-')[:64] or 'import',
            'purpose': 'reproduce', 'claim': title.strip()[:300], 'source': {'ref': ref, 'imported': True}, 'players': 1, 'at': at, 'action': actions,
            'expect': expect, 'confirm': [{'text': s} for s in sentences], 'notes': notes}


def _tv(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        return '[' + ', '.join(_tv(x) for x in v) + ']'
    if isinstance(v, dict):
        return '{' + ', '.join(f'{k} = {_tv(x)}' for k, x in v.items()) + '}'
    raise TypeError(type(v))


def dumps(d):
    """TOML text of a scenario dict (this format only: scalars, lists of scalars and inline tables, [at], [source], [[action]] ...)."""
    out = [f'# {FORMAT}: a targeted scenario']
    for k in ('format', 'name', 'purpose', 'claim', 'players', 'runnable', 'save', 'save_b', 'watch', 'link_ms', 'hold_s'):
        if k in d:
            out.append(f'{k} = {_tv(d[k])}')
    if d.get('notes'):
        out.append(f'notes = {_tv(d["notes"])}')
    if d.get('env'):
        out.append(f'env = {_tv(d["env"])}')
    if d.get('source'):
        out += ['', '[source]'] + [f'{k} = {_tv(v)}' for k, v in d['source'].items()]
    out += ['', '[at]'] + [f'{k} = {_tv(v)}' for k, v in d.get('at', {}).items()]
    for a in d.get('action') or []:
        out += ['', '[[action]]'] + [f'{k} = {_tv(v)}' for k, v in a.items()]
    for e in d.get('expect') or []:
        out += ['', '[[expect]]'] + [f'{k} = {_tv(v)}' for k, v in e.items()]
    for c in d.get('confirm') or []:
        out += ['', '[[confirm]]'] + [f'{k} = {_tv(v)}' for k, v in c.items()]
    return '\n'.join(out) + '\n'


def fetch_issue(number, api=None, lock=None):
    """(title, body) of a forge issue by number: a GET, under the forge-auth lock the harness's other readers share ($SCENARIO_FORGE_LOCK)."""
    import subprocess
    api = api or forge_addresses()[0]
    lock = lock or os.environ.get(ENV_FORGE_LOCK)
    if not lock:
        raise ScenarioError(f'set {ENV_FORGE_LOCK} to the forge-auth lock file the harness\'s other readers share (this machine\'s own value; there is no default)')
    r = subprocess.run(['flock', lock, 'curl', '-s', '-m', '30', f'{api}/issues/{int(number)}'], capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
        return d['title'], d.get('body') or ''
    except (ValueError, KeyError):
        raise ScenarioError(f'issue {number}: no readable answer from the forge')


# ---- judging a played run

def distance_reached(steps_events, tag_by_in):
    """metres from the point, from the detail of the last `goto` step ('1.41 m from the point'), else None."""
    last = None
    for e in steps_events:
        if tag_by_in.get(e.get('in')) == 'goto':
            last = e
    if not last:
        return None, None
    m = re.search(r'([\d.]+) m from the point', last.get('detail') or '')
    return (float(m.group(1)) if m else (0.0 if last.get('result') == 'reached' else None)), last.get('result')


def hardware_of(log_lines):
    for ln in log_lines:
        m = re.search(r'device \d+: (.+?), Vulkan', ln)
        if m:
            return m.group(1)
    return None


def evaluate(d, run, tags=None, bughunt_mod=None, cfg=None, visual_findings=None):
    """The verdict of a played run of scenario `d`: {verdict, checks: [...], hardware, at, tried}. `run` is a hunt session folder (pilot/, game/).
    verdict: `reproduced` (a check found it), `not reproduced` (every check looked and found nothing: say so with what was tried) or
    `inconclusive` (a check could not look). `tags` = {step number: tag} (scenario-steps.json); `visual_findings` = the detectors' visual findings."""
    bh = bughunt_mod
    if bh is None:
        import bughunt as bh   # noqa: E402
    cfg = cfg or bh.Config()
    side = bh.load_side(run)
    tags = {int(k): v for k, v in (tags or _read_tags(run)).items()}
    steps = [e for e in side.steps]
    results = []
    for ex in d.get('expect') or []:
        kind = ex['check']
        res = {'check': kind}
        if kind == 'crash':
            found = [f for r in (bh.detect_crash(side, cfg), bh.detect_hang(side, cfg)) for f in r.findings if f.severity != 'info' and f.sub not in ('no-end', 'slow-stop')]   # (a slow stop is a finding of its own, no crash)
            res.update(found=len(found), what=[f'{f.kind}/{f.sub}: {f.text[:100]}' for f in found[:3]])
            res['verdict'] = 'reproduced' if found else ('not reproduced' if side.states or side.present else 'inconclusive')
        elif kind == 'spikes':
            res.update(spike_check(side, steps, tags, ex, cfg, bh))
        elif kind == 'visual':
            subs = set(ex.get('subs') or CHECKS['visual']['subs'][1])
            vf = visual_findings if visual_findings is not None else [f for f in bh.detect_visual(side, cfg).findings]
            hit = [f for f in vf if f.kind == 'visual' and f.sub in subs and f.severity != 'info']
            looked = len(side.shots) + sum(len(b[2]) for b in side.bursts)
            res.update(pictures=looked, found=len(hit), what=[f'{f.sub}: {f.text[:100]}' for f in hit[:3]])
            res['verdict'] = 'reproduced' if hit else ('not reproduced' if looked else 'inconclusive')
        elif kind == 'reached':   # a gate, not a bug check: did the run get where the scenario meant to be? (steps of these tags that ended reached/done/entered/opened)
            want = set(ex.get('tags') or [])
            mine = [e for e in steps if tags.get(e.get('in')) in want and str(e.get('src', '')).startswith(ex.get('src') or '')]
            ok = [e for e in mine if e.get('result') in ('reached', 'done', 'entered', 'opened', 'picked', 'talked', 'met', 'targeted')]
            share = len(ok) / len(mine) if mine else 0.0
            res.update(tags=sorted(want), steps=len(mine), ok=len(ok), share=round(share, 2), need=ex.get('share', 1.0), results=sorted({str(e.get('result')) for e in mine}))
            res['verdict'] = 'reached' if mine and share >= ex.get('share', 1.0) else 'not reached'
        elif kind == 'visited':   # a gate: the player's state was in this map at some sample
            seen = any(_state_at(r, ex) for r in side.states)
            res.update(map=ex.get('map'), music=ex.get('music'), seen=seen)
            res['verdict'] = 'reached' if seen else 'not reached'
        elif kind == 'distance':
            dist, how = distance_reached(steps, tags)
            res.update(distance_m=dist, last_step=how, max_m=ex.get('max_m', 5.0))
            res['verdict'] = 'inconclusive' if dist is None else ('reproduced' if dist <= ex.get('max_m', 5.0) else 'not reproduced')
            res['note'] = 'how near the run got to the reported coordinates (a place, not a bug)'
        else:
            res['verdict'] = 'inconclusive'
            res['why'] = f'{kind} does not apply to a single player'
        results.append(res)
    judged = [r for r in results if r['check'] not in ('distance', 'reached', 'visited')]
    gate_failed = [r for r in results if r['check'] in ('reached', 'visited') and r['verdict'] != 'reached']
    if any(r['verdict'] == 'reproduced' for r in judged):
        verdict = 'reproduced'
    elif gate_failed:   # it never got where it was meant to look: nothing was tried that counts
        verdict = 'inconclusive'
    elif judged and all(r['verdict'] == 'not reproduced' for r in judged):
        verdict = 'not reproduced'
    else:
        verdict = 'inconclusive'
    tried = {t: sum(1 for e in steps if tags.get(e.get('in')) == t) for t in sorted(set(tags.values()) - {'note'})}
    dist, how = distance_reached(steps, tags)
    return {'scenario': d.get('name'), 'purpose': d.get('purpose'), 'claim': d.get('claim'), 'verdict': verdict, 'checks': results, 'hardware': hardware_of(side.log),
            'tried_steps_by_tag': tried, 'at': {k: d['at'].get(k) for k in ('map', 'age', 'hour', 'x', 'z')}, 'goto': {'distance_m': dist, 'result': how} if goto_of(d) else None,
            'steps_done': len(steps)}


# ---- a pair: two games, each with its own steps (`who`), a rendezvous to meet, a co-op case for the runner

ROOM_SETTINGS = {'coop_presence_permissions': 3, 'coop_progress': 1, 'coop_items': 1, 'coop_songs': 1, 'coop_quest': 1, 'coop_keys': 2}


def segment_text(d, side, route_name, wall):
    """The pilot segment of one player of a pair: scripted (no goals, no decider): the route is the whole play. The place is a `[place]` table
    unless the scenario starts from the save's own place (`at.from = "save"`)."""
    at = d['at']
    lines = [f'# a scripted segment made by scenario.py from {d["name"]} (player {side}); private, never published',
             f'name = {_tv(d["name"] + "-" + side)}', f'what = {_tv(d["claim"][:200])}', f'area = {_tv(at["map"])}',
             f'save = {_tv(d.get("save_b") if side == "B" and d.get("save_b") else d["save"])}', 'boot = "continue"', 'scripted = true',
             f'prefix = {_tv(route_name)}', f'wall = {int(wall)}', f'budget_seconds = {int(wall)}', 'max_decisions = 1', 'humanize = 0']
    if d.get('watch'):
        lines.append(f'watch = {_tv(list(d["watch"]))}')
    spec = place_spec(d)
    if spec:
        lines += ['', '[place]'] + [f'{k} = {_tv(v)}' for k, v in spec.items() if k in ('to', 'age', 'hour')]
    return '\n'.join(lines) + '\n'


def pair_files(d, out, frozen, copy_a, copy_b, rendezvous, info=None, wall=420, world=None, vram_mb=5500):
    """Writes what the co-op runner needs to play a two-player scenario into `out`: a scripted segment and a route per player, and the case
    (two pilot sides, a local relay, progress shared, B's link delayed by `link_ms` each way when the scenario says so). `frozen` = the folder of the
    frozen code (pilot/pilot.py, pilot/runs); `rendezvous` = a new, empty folder both sides' `rendezvous` steps meet in. Returns {'case': path, ...}."""
    if d.get('players', 1) != 2:
        raise ScenarioError('pair_files: players = 2')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    Path(rendezvous).mkdir(parents=True, exist_ok=True)
    segs = {}
    for side in 'AB':
        steps = compile_steps(d, world, side=side)
        route = out / f'{d["name"]}-{side}.txt'
        route.write_text('\n'.join(l for l, _ in steps) + '\n')
        seg = out / f'{d["name"]}-{side}.toml'
        seg.write_text(segment_text(d, side, route.name, wall))
        segs[side] = seg
    env_extra = [f'HSDEBUG_INFO={info}'] if info else []
    hold = int(d.get('hold_s') or 420)
    text = [f'# {FORMAT} pair scenario {d["name"]}: two scripted pilots (scenario.py), progress shared, keys pooled; the room is that of the shared-chest proof',
            f'name = {_tv(d["name"])}', f'description = {_tv(d["claim"][:200])}', '', 'steps = [', '  {id = "c0010", from = "bodies", at = 10, sides = ["A", "B"], do = "shot", name = "c0010"},',
            '  {id = "c0040", from = "bodies", at = 40, sides = ["A", "B"], do = "shot", name = "c0040"},', ']', '',
            'expect = [', '  {name = "room reached: bodies shown on both sides", check = "anchor", anchor = "bodies", by = 330},',
            '  {name = "both games exit cleanly", check = "exit"},', '  {name = "no faults", check = "detector", detector = "faults", status_max = "warn"},', ']', '']
    if d.get('watch'):
        text += [f'shared_flags = {_tv(list(d["watch"]))}', '']
    text += ['[build]', f'A = {_tv(str(copy_a))}', f'B = {_tv(str(copy_b))}', '', '[topology]', 'kind = "local-relay"', 'maker = "A"', '',
             '[room]', 'consent = "auto"', '[room.settings]'] + [f'{k} = {v}' for k, v in ROOM_SETTINGS.items()]
    for side in 'AB':
        env = ['HSAP_ANALOG=1', 'RX_VK_PRECOMPILE=1', f'HSAP_RENDEZVOUS={rendezvous}', f'HSAP_SIDE={side}'] + ([f'RX_VK_VRAM_MB={int(vram_mb)}'] if vram_mb else []) + env_extra + [e for e in (d.get('env') or [])]
        text += ['', f'[sides.{side}]', f'name = "Scn{side}"', f'save = {_tv(d.get("save_b") if side == "B" and d.get("save_b") else d["save"])}', 'driver = "pilot"', f'env = {_tv(env)}',
                 f'[sides.{side}.pilot]', f'pilot = {_tv(str(Path(frozen) / "pilot" / "pilot.py"))}', f'runs = {_tv(str(Path(frozen) / "pilot" / "runs"))}',
                 f'segment = {_tv(str(segs[side]))}', 'decider = "rules"', 'end_hold_s = 15', 'planner = false']
    if d.get('link_ms'):
        text += ['', '[sides.B.link]', 'seed = 7', 'trace = true', '[sides.B.link.c2s]', f'delay_ms = {int(d["link_ms"])}', '[sides.B.link.s2c]', f'delay_ms = {int(d["link_ms"])}']
    text += ['', '[run]', f'hold_seconds = {hold}', 'launch_gap_seconds = 62', 'launch_mode = "wrapper"', 'gate = "none"', 'anchor_timeout_s = 600', 'tail_s = 10', 'shot_every = 240',
             'state_every = 3', 'pose_trace = true', 'measuring = "exclusive"'] + ([f'watch = {_tv(list(d["watch"]))}'] if d.get('watch') else []) + \
            ['', '[detectors]', 'run = ["logs", "bodies", "net", "divergence", "jank", "frames", "cpu", "faults"]']
    case = out / f'{d["name"]}.toml'
    case.write_text('\n'.join(text) + '\n')
    return {'case': str(case), 'segments': {k: str(v) for k, v in segs.items()}, 'hold_s': hold, 'rendezvous': str(rendezvous)}


def align_tags(step_events, compiled):
    """{step number: tag} for a played side: the compiled lines (comments left out) matched in order to the step events' `src`; the numbers are the
    events' own (hsap numbers every line of the steps file, the watch lines included)."""
    lines = [(l, t) for l, t in compiled if not l.startswith('#')]
    out, k = {}, 0
    for e in step_events:
        if k < len(lines) and (e.get('src') or '').strip() == lines[k][0].strip():
            out[e.get('in')] = lines[k][1]
            k += 1
    return out


def _state_at(row, ex):
    """a state sample is in the place a `visited` gate names: its map and/or its music"""
    return (not ex.get('map') or (row.get('map') or row.get('area')) == ex['map']) and (not ex.get('music') or row.get('music') == ex['music'])


RUNNER_KILL = re.compile(r'SIGKILL|exit(?: code)? 137')


def evaluate_pair(d, findings, sides, bughunt_mod=None):
    """The verdict of a played pair: `key` (a registry key fired: a double give), `counter` (a count that rose by more than `max` on one side),
    `clean` (no finding but the ignored kinds: `desync`, `body/coop-jank` ...), `crash`, `reached` (each player's steps of the tags got where they were meant to).
    `findings` = the detectors' findings (after the triage rules), `sides` = {name: bughunt.Side}."""
    bh = bughunt_mod
    if bh is None:
        import bughunt as bh   # noqa: E402
    played = {n: bool(sd.states) for n, sd in sides.items()}
    folder = next((Path(sd.root).parent for sd in sides.values()), None)
    asked = bh.shutdown_wall(folder) is not None if folder else False   # the runner's `shutdown` phase: it asked the pilots to end, and kills a game that does not
    try:
        oom = bool(re.search(r'(?i)out of memory|oom-kill|killed process', (folder / 'kernel.txt').read_text())) if folder else False
    except OSError:
        oom = False
    findings = [f for f in findings if not (f.side in played and RUNNER_KILL.search(f.text or '') and not oom and (not played[f.side] or asked))]   # the runner's own SIGKILL (a game that never reached control, or one still waiting when it asked the pilots to end): no crash
    if not any(played.values()) and not [f for f in findings if f.kind == 'crash' and f.severity != 'info']:
        why = 'no game reached control: the session proves nothing about the scenario'
        hw = {n: hardware_of(sd.log) for n, sd in sides.items()}
        return {'scenario': d.get('name'), 'purpose': d.get('purpose'), 'claim': d.get('claim'), 'verdict': 'inconclusive', 'why': why,
                'checks': [{'check': ex['check'], 'verdict': 'inconclusive', 'why': why} for ex in d.get('expect') or []],
                'hardware': next((h for h in hw.values() if h), None), 'players': 2, 'steps_done': {n: len(sd.steps) for n, sd in sides.items()}}
    results = []
    for ex in d.get('expect') or []:
        kind = ex['check']
        res = {'check': kind}
        if kind == 'key':
            hit = [f for f in findings if f.key == ex['key'] and (f.severity != 'info' or (f.evidence or {}).get('known'))]
            res.update(found=len(hit), sides=sorted({f.side for f in hit}))
            res['verdict'] = 'reproduced' if hit else 'not reproduced'
        elif kind == 'counter':
            rises, usable = {}, 0
            for name, side in sides.items():
                vals = [(r.get('flags') or {}).get(ex['flag']) for r in side.states]
                vals = [v for v in vals if isinstance(v, (int, float))]
                if vals:
                    usable += 1
                    rises[name] = max(vals) - vals[0]
            res.update(rises=rises, max=ex.get('max', 1))
            res['verdict'] = 'inconclusive' if not usable else ('reproduced' if any(v > ex.get('max', 1) for v in rises.values()) else 'not reproduced')
        elif kind == 'crash':
            hit = [f for f in findings if f.kind in ('crash', 'hang') and f.severity != 'info' and f.sub not in ('no-end', 'slow-stop')]
            res.update(found=len(hit), what=[f'{f.side}: {f.kind}/{f.sub}: {f.text[:100]}' for f in hit[:3]])
            res['verdict'] = 'reproduced' if hit else ('not reproduced' if any(s.states or s.present for s in sides.values()) else 'inconclusive')
        elif kind == 'clean':
            ignore = tuple(ex.get('ignore') or ())
            hit = [f for f in findings if f.severity != 'info' and not f'{f.kind}/{f.sub}'.startswith(ignore)]
            res.update(found=len(hit), what=[f'{f.side}: {f.kind}/{f.sub}: {f.text[:100]}' for f in hit[:4]])
            res['verdict'] = 'reproduced' if hit else 'not reproduced'
        elif kind == 'reached':
            want = set(ex.get('tags') or [])
            per = {}
            for name, side in sides.items():
                tg = align_tags(side.steps, compile_steps(d, side=name if name in ('A', 'B') else None))
                mine = [e for e in side.steps if tg.get(e.get('in')) in want and str(e.get('src', '')).startswith(ex.get('src') or '')]
                ok = [e for e in mine if e.get('result') in ('reached', 'done', 'entered', 'opened', 'picked', 'talked', 'met', 'targeted')]
                per[name] = {'steps': len(mine), 'ok': len(ok), 'results': sorted({str(e.get('result')) for e in mine})}
            share = min((v['ok'] / v['steps'] if v['steps'] else 0.0) for v in per.values()) if per else 0.0
            res.update(tags=sorted(want), per_side=per, share=round(share, 2), need=ex.get('share', 1.0))
            res['verdict'] = 'reached' if per and share >= ex.get('share', 1.0) else 'not reached'
        elif kind == 'visited':   # a gate for each player: both states were in this map at some sample
            per = {n: any(_state_at(r, ex) for r in sd.states) for n, sd in sides.items() if ex.get('who', 'both') in ('both', n)}
            res.update(map=ex.get('map'), music=ex.get('music'), per_side=per)
            res['verdict'] = 'reached' if per and all(per.values()) else 'not reached'
        else:
            res['verdict'] = 'inconclusive'
            res['why'] = f'{kind} does not apply to a pair'
        results.append(res)
    judged = [r for r in results if r['check'] not in ('reached', 'visited')]
    gate_failed = [r for r in results if r['check'] in ('reached', 'visited') and r['verdict'] != 'reached']
    if any(r['verdict'] == 'reproduced' for r in judged):
        verdict = 'reproduced'
    elif gate_failed:
        verdict = 'inconclusive'
    elif judged and all(r['verdict'] == 'not reproduced' for r in judged):
        verdict = 'not reproduced'
    else:
        verdict = 'inconclusive'
    why = None
    missing = sorted(n for n, ok in played.items() if not ok)
    if missing and verdict != 'reproduced':   # a pair needs both players: a clean read of one game says nothing about two
        verdict = 'inconclusive'
        why = f'player {", ".join(missing)} never reached control (the session shows one game only)'
    hw = {n: hardware_of(sd.log) for n, sd in sides.items()}
    return {'scenario': d.get('name'), 'purpose': d.get('purpose'), 'claim': d.get('claim'), 'verdict': verdict, 'checks': results, 'why': why,
            'hardware': next((h for h in hw.values() if h), None), 'players': 2, 'steps_done': {n: len(sd.steps) for n, sd in sides.items()}}


def _read_tags(run):
    for p in (Path(run) / 'pilot' / 'live' / 'scenario-steps.json', Path(run) / 'live' / 'scenario-steps.json'):
        try:
            return json.loads(p.read_text())['tags']
        except (OSError, ValueError, KeyError):
            pass
    return {}


def spike_check(side, steps, tags, ex, cfg, bh):
    """Present intervals of `ms` or more inside the windows of the `during` tags against outside them (after the warm-up): reproduced when the
    windows have `min_spikes` or more spikes at `factor` times the rate outside; `inconclusive` with less than `min_window_s` seconds inside."""
    pres = side.present
    during = set(ex.get('during') or [])
    wins = []
    for t_end, e in side.step_times():
        tag = tags.get(e.get('in'))
        if tag in during:
            wins.append((t_end - float(e.get('secs') or 0.0), t_end))
    out = {'ms': ex.get('ms', 50.0), 'during': sorted(during), 'windows': len(wins)}
    if not pres or not wins:
        out['verdict'] = 'inconclusive'
        out['why'] = 'no present trace' if not pres else 'no step of the `during` tags ran'
        return out
    merged = []
    for a, b in sorted(wins):
        if merged and a <= merged[-1][1] + 0.5:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    g0 = side.gameplay[0] if side.gameplay else pres[0][1]
    ms = ex.get('ms', 50.0)
    in_s = sum(b - a for a, b in merged)
    in_n = out_n = machine = 0
    prs = side.pressure
    t_first, t_last = pres[0][1], pres[-1][1]
    out_s = max(0.0, (t_last - max(g0 + cfg.warmup_s, t_first)) - in_s)
    for fr, ts, iv in pres:
        if ts < g0 + cfg.warmup_s:
            continue
        if iv >= ms:
            if prs:   # a frame that was slow while the machine was short of CPU, disk or memory is the machine's (the pressure counters around it)
                pr_ = bh.machine_pressure(prs, ts - 1.0, ts, 0.0)
                if pr_ and bh.machine_short(pr_, cfg):
                    machine += 1
                    continue
            if any(a <= ts <= b for a, b in merged):
                in_n += 1
            else:
                out_n += 1
    rate_in, rate_out = in_n / max(in_s, 1e-6) * 60.0, out_n / max(out_s, 1e-6) * 60.0 if out_s > 1.0 else None
    out.update(window_s=round(in_s, 1), spikes_in=in_n, spikes_out=out_n, spikes_machine=machine, outside_s=round(out_s, 1), per_min_in=round(rate_in, 2), per_min_out=None if rate_out is None else round(rate_out, 2))
    if in_s < ex.get('min_window_s', 20.0):
        out['verdict'], out['why'] = 'inconclusive', f'only {in_s:.0f} s inside the windows'
    elif in_n >= ex.get('min_spikes', 3) and (rate_out is None or rate_in >= ex.get('factor', 3.0) * max(rate_out, 1.0)):
        out['verdict'] = 'reproduced'
    else:
        out['verdict'] = 'not reproduced'
    return out


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('check')
    c.add_argument('file')
    s = sub.add_parser('steps')
    s.add_argument('file')
    s.add_argument('--world')
    i = sub.add_parser('import')
    g = i.add_mutually_exclusive_group(required=True)
    g.add_argument('--issue', type=int)
    g.add_argument('--text')
    i.add_argument('--title', default='')
    i.add_argument('--destinations', required=True)
    i.add_argument('--out', required=True)
    i.add_argument('--ref', default='')
    i.add_argument('--name')
    i.add_argument('--alias', action='append', default=[], help='"what players say=Destination" (e.g. "town square=SomeDestination"): a place named another way')
    pp = sub.add_parser('pair-files')
    pp.add_argument('file')
    pp.add_argument('--out', required=True)
    pp.add_argument('--frozen', required=True)
    pp.add_argument('--copy-a', required=True)
    pp.add_argument('--copy-b', required=True)
    pp.add_argument('--rendezvous', required=True)
    pp.add_argument('--info')
    pp.add_argument('--wall', type=int, default=420)
    e = sub.add_parser('eval')
    e.add_argument('file')
    e.add_argument('run')
    e.add_argument('--out')
    a = ap.parse_args(argv)
    if a.cmd == 'check':
        d = load(a.file)
        for u in unconfirmed(d):
            print('UNCONFIRMED', u)
        print(f'{d["name"]}: ok ({len(d.get("action") or [])} actions, {len(d.get("expect") or [])} checks)')
        return 0
    if a.cmd == 'steps':
        d = load(a.file)
        world = None
        if a.world:
            import hunt
            r = hunt.WorldRoam(a.world)
            world = {'plan': r.plan.plan, 'start': r.start, 'targets': r.targets, 'snap': r.nearest}
        for line, tag in compile_steps(d, world):
            print(f'{line:60} {tag}')
        return 0
    if a.cmd == 'import':
        dests = json.loads(Path(a.destinations).read_text())
        if a.issue:
            title, body = fetch_issue(a.issue)
            ref = a.ref or f'{forge_addresses()[1]}{a.issue}'
        else:
            title, body, ref = a.title, Path(a.text).read_text(), a.ref
        sc = import_text(title, body, dests, ref=ref, name=a.name, extra_aliases=dict(x.split('=', 1) for x in a.alias))
        Path(a.out).write_text(dumps(sc))
        print(f'{a.out}: map {sc["at"].get("map")}, coordinates {"yes" if "x" in sc["at"] else "no"}, {len(sc["action"])} proposed action(s) to confirm, {len(sc["confirm"])} sentence(s)')
        for n in sc['notes']:
            print('  note:', n)
        return 0
    if a.cmd == 'pair-files':
        d = load(a.file)
        print(json.dumps(pair_files(d, a.out, a.frozen, a.copy_a, a.copy_b, a.rendezvous, info=a.info, wall=a.wall)))
        return 0
    d = load(a.file)
    res = evaluate(d, a.run)
    text = json.dumps(res, indent=1)
    if a.out:
        Path(a.out).write_text(text + '\n')
    print(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
