#!/usr/bin/env python3
"""bosspoints: the loader and validator of the local start-point table, and the helpers every tool in this folder shares.

The tools here build test start points (a library save, a scenario, a step list for a timed hold) from ONE local table. The table holds
everything that names or describes a place in the game: maps, coordinates, flag and item names, the action list of each place. You write it
for your own game files; it stays on your PC and is never committed. This folder holds code only.

    table: the file named by $BOSSPOINTS_TABLE, else table.local.json beside this file (--table FILE on every tool overrides both)
    python3 -I -B bosspoints_table.py [--table FILE]    check the table and print what it holds
    python3 -I -B bosspoints_table.py --schema          print this text

Format "bosspoints/1" (JSON). Every name below is a placeholder:

    {
      "schema": "bosspoints/1",
      "game": "/path/to/your/extracted/game/files",   passed to the save tool as --game (make_saves.py --game overrides it)
      "base_save": "base-save",                       the library save every generated save starts from
      "targets": [                                    a target = a thing to reach; it owns one or more starts
        {
          "key": "alpha", "title": "Alpha Target",    key: short id for --only; title: used in messages
          "map": "AreaOne", "age": "child",           defaults of the starts below
          "give": ["item-a", "item-b=5", "item-c=7"],  default contents of the starts' saves (--give values of the save tool)
          "vars": {"door": [10, 20, 30], "goal": [12, 40, 2.5]},   named numbers the recipes refer to (lists of numbers)
          "note": "free text", "info": {"any": "json"},   for the reader; the tools ignore them (also allowed on a start)
          "starts": [ START, ... ]
        }
      ],
      "hold": {"runs": [ RUN, ... ]}                  optional: the runs plan_hold.py plans
    }

START: one place to start a test from = one save, one scenario, one hold recipe (each part optional):

    {
      "name": "alpha-door",                           scenario name, scenario file name, default save name: letters, digits, . _ -
      "map": "AreaTwo", "age": "adult",               replace the target's
      "vars": {"gate": [1, 2, 3]},                    added to the target's
      "at": {"x": 10, "y": 20, "z": 24, "facing": 90},  where the player stands (facing in degrees, 0 = +z, 90 = +x); x and z come together
      "claim": "one sentence: what the scenario is for",   the scenario's claim (needed with "actions")
      "header": ["a comment line"],                   written as "# " lines at the top of the scenario file
      "actions": [ {"do": "wait", "s": 3.0, "tag": "settle"},
                   {"do": "go_near", "x": "{goal[0]}", "z": "{goal[1]}", "radius": "{goal[2]}"} ],   pilot/scenario.py's actions
      "expect": [ {"check": "crash"} ],               pilot/scenario.py's checks (default: crash and visual)
      "save": {
        "name": "alpha-door",                         library name (default: the start's name)
        "start": "AreaOne/StartA",                    the save tool's --start (default: "Map:x,y,z,yaw" from map and at, yaw in radians)
        "give": ["item-a"],                           --give values (default: the target's "give")
        "flags": ["FlagA=1", "FlagB=Part2"],          --flag NAME=VALUE values, in this order (default: none)
        "point": "text", "note": "text",              the library entry's --point and --note (make_saves.py --lib; defaults are generic)
        "optional": "extra"                           built only with make_saves.py --with extra (that tool only)
      },
      "hold": {
        "steps": [ "# {key} on {map}", {"watch": ["flag.one", "flag.two"]}, "report 1",
                   "enter {door[0]:.2f} {door[2]:.2f} through {gate[0]:.2f} {gate[2]:.2f} timeout 55",
                   {"route": {"from": "gate", "to": "goal"}}, "end" ],   hsap step lines, see below
        "note": "route: {route}",                     the run's note in plan.json
        "expect": "flag.one"                          the flag whose rise means the test worked (plan.json "expect")
      }
    }

RUN (hold.runs): {"lane": "a", "id": "alpha", "start": "alpha-door", "wall": 170}; "save", "steps", "note" and "expect" replace what the
start provides (the save's library name, the hold recipe's parts). The lane name groups runs that play one after the other.

Recipes. A text line or note is a Python format string over the start's key, title, map, age, start (its name) and its vars:
"{door[1]:.2f}" is the second number of the var "door" with two decimals; "{{" and "}}" are braces; in a note "{route}" is the planner's
outcome. An action value that is exactly "{door[1]}" becomes that number. {"watch": [names]} becomes `watch 0x... 0x...` (the game's flag
hashes of the names); {"route": {"from": VAR, "to": VAR}} becomes the world model planner's `walk` lines from one var (x, y, z) to
another (optional: "map", "radius" 1.5, "doors" "through", "max_steps" 14, "timeout" 20).
"""
import argparse
import importlib
import json
import math
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA = 'bosspoints/1'
ENV_TABLE = 'BOSSPOINTS_TABLE'
DEFAULT_TABLE = HERE / 'table.local.json'

NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}')
KEY = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,31}')
VAR = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')
REF = re.compile(r'\{([A-Za-z_][A-Za-z0-9_]*)\[(\d+)\]\}')
RESERVED = ('key', 'title', 'map', 'age', 'start', 'route')
AGES = ('child', 'adult')

TOP_KEYS = {'schema', 'game', 'base_save', 'targets', 'hold', 'note', 'info'}
TARGET_KEYS = {'key', 'title', 'map', 'age', 'give', 'vars', 'starts', 'note', 'info'}
START_KEYS = {'name', 'map', 'age', 'at', 'vars', 'claim', 'header', 'actions', 'expect', 'save', 'hold', 'note', 'info'}
SAVE_KEYS = {'name', 'start', 'give', 'flags', 'point', 'note', 'optional'}
HOLD_KEYS = {'steps', 'note', 'expect'}
RUN_KEYS = {'lane', 'id', 'start', 'wall', 'save', 'steps', 'note', 'expect'}
AT_KEYS = {'x', 'y', 'z', 'facing'}
ROUTE_KEYS = {'from', 'to', 'map', 'radius', 'doors', 'max_steps', 'timeout'}

MISSING = ('the table file {path} does not exist. It holds the data of your own game (maps, coordinates, flag and item names) and is not '
           'part of this repository: write it for your own game files, or point ${env} at it. Its format is "{schema}"; '
           'python3 -I -B bosspoints_table.py --schema prints the schema.')


class TableError(Exception):
    pass


def table_path(arg=None):
    """--table FILE, else $BOSSPOINTS_TABLE, else table.local.json beside this file."""
    return Path(arg or os.environ.get(ENV_TABLE) or DEFAULT_TABLE)


def yaw_rad(facing_deg):
    """Degrees (0 = +z, 90 = +x) as radians in -pi..pi: the save tool's start yaw."""
    r = math.radians(facing_deg)
    return math.atan2(math.sin(r), math.cos(r))


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def context(st):
    """The names a start's recipes can use: key, title, map, age, start, and its vars."""
    ctx = {'key': st['key'], 'title': st['title'], 'map': st['map'], 'age': st['age'], 'start': st['name']}
    ctx.update(st['vars'])
    return ctx


def render(text, ctx, **extra):
    """A recipe line or note: Python format over the context (and `route` for a note)."""
    return text.format(**ctx, **extra)


def subst(value, ctx):
    """An action with every value that is exactly "{var[i]}" replaced by that number (lists and tables are walked)."""
    if isinstance(value, str):
        m = REF.fullmatch(value)
        if m:
            return ctx[m.group(1)][int(m.group(2))]
        return value
    if isinstance(value, list):
        return [subst(v, ctx) for v in value]
    if isinstance(value, dict):
        return {k: subst(v, ctx) for k, v in value.items()}
    return value


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)


class Table:
    """A validated table. `starts` are dicts with the target's defaults filled in: key, title, name, map, age, at, vars, claim, header,
    actions, expect, save (or None), hold (or None); `runs` are the hold runs with their start's recipe filled in."""

    def __init__(self, data, path):
        self.path = Path(path)
        self.data = data
        self.starts = []
        self.runs = []
        self._build()

    def fail(self, where, what):
        raise TableError(f'{self.path} ({SCHEMA}): {where}: {what}')

    # ---- reading

    def _keys(self, d, allowed, where):
        if not isinstance(d, dict):
            self.fail(where, 'must be an object')
        extra = sorted(set(d) - allowed)
        if extra:
            self.fail(where, 'unknown key(s) ' + ', '.join(extra) + '; allowed: ' + ', '.join(sorted(allowed)))

    def _str(self, d, key, where, required=True):
        v = d.get(key)
        if v is None and not required:
            return None
        if not isinstance(v, str) or not v:
            self.fail(f'{where}.{key}', 'must be a non-empty string')
        return v

    def _strs(self, v, where, default=None):
        if v is None:
            return list(default) if default is not None else None
        if not isinstance(v, list) or not all(isinstance(x, str) and x for x in v):
            self.fail(where, 'must be a list of non-empty strings')
        return list(v)

    def _vars(self, v, where):
        if v is None:
            return {}
        if not isinstance(v, dict):
            self.fail(where, 'must be an object of name: list of numbers')
        for k, nums in v.items():
            if not VAR.fullmatch(k) or k in RESERVED:
                self.fail(f'{where}.{k}', 'is not a usable name (letters, digits, _; not ' + ', '.join(RESERVED) + ')')
            if not isinstance(nums, list) or not nums or not all(is_num(n) for n in nums):
                self.fail(f'{where}.{k}', 'must be a non-empty list of numbers')
        return dict(v)

    def _at(self, at, where):
        if at is None:
            return None
        self._keys(at, AT_KEYS, where)
        for k, v in at.items():
            if not is_num(v):
                self.fail(f'{where}.{k}', 'must be a number')
        if ('x' in at) != ('z' in at):
            self.fail(where, 'x and z come together')
        return dict(at)

    def _build(self):
        d = self.data
        self._keys(d, TOP_KEYS, 'table')
        if d.get('schema') != SCHEMA:
            self.fail('schema', f'must be "{SCHEMA}", not {d.get("schema")!r}')
        self.game = self._str(d, 'game', 'table', required=False)
        self.base_save = self._str(d, 'base_save', 'table')
        targets = d.get('targets')
        if not isinstance(targets, list) or not targets:
            self.fail('targets', 'must be a non-empty list')
        seen_keys, seen_names = set(), set()
        for i, t in enumerate(targets):
            tw = f'targets[{i}]'
            self._keys(t, TARGET_KEYS, tw)
            key = self._str(t, 'key', tw)
            if not KEY.fullmatch(key) or key in seen_keys:
                self.fail(f'{tw}.key', f'{key!r} must be unique: letters, digits, _ and -')
            seen_keys.add(key)
            title = self._str(t, 'title', tw)
            t_vars = self._vars(t.get('vars'), f'{tw}.vars')
            t_give = self._strs(t.get('give'), f'{tw}.give')
            if t.get('age') not in (None,) + AGES:
                self.fail(f'{tw}.age', 'must be "child" or "adult"')
            starts = t.get('starts')
            if not isinstance(starts, list) or not starts:
                self.fail(f'{tw}.starts', 'must be a non-empty list')
            for j, s in enumerate(starts):
                sw = f'{tw}.starts[{j}]'
                self._keys(s, START_KEYS, sw)
                name = self._str(s, 'name', sw)
                if not NAME.fullmatch(name) or name in seen_names:
                    self.fail(f'{sw}.name', f'{name!r} must be unique: 1 to 64 letters, digits, . _ -')
                seen_names.add(name)
                st = {'key': key, 'title': title, 'name': name,
                      'map': s.get('map') or t.get('map'), 'age': s.get('age') or t.get('age'),
                      'vars': {**t_vars, **self._vars(s.get('vars'), f'{sw}.vars')},
                      'at': self._at(s.get('at'), f'{sw}.at'), 'claim': s.get('claim'), 'header': self._strs(s.get('header'), f'{sw}.header', []),
                      'actions': s.get('actions'), 'expect': s.get('expect'), 'save': None, 'hold': None}
                if not isinstance(st['map'], str) or not st['map']:
                    self.fail(f'{sw}.map', 'needs a map (here or on the target)')
                if st['age'] not in AGES:
                    self.fail(f'{sw}.age', 'needs "child" or "adult" (here or on the target)')
                self._recipe(st, s, sw, t_give)
                self.starts.append(st)
        self.by_name = {st['name']: st for st in self.starts}
        self.targets = [t['key'] for t in targets]
        self._runs(d.get('hold'))

    def _recipe(self, st, s, sw, t_give):
        if s.get('actions') is not None:
            if not isinstance(st['claim'], str) or not st['claim']:
                self.fail(f'{sw}.claim', 'is needed with "actions": what the scenario is for, in a sentence')
            acts = st['actions']
            if not isinstance(acts, list) or not acts or not all(isinstance(a, dict) for a in acts):
                self.fail(f'{sw}.actions', 'must be a non-empty list of objects')
            ctx = context(st)
            for text in _strings(acts):
                m = REF.fullmatch(text)
                if m and not (isinstance(ctx.get(m.group(1)), list) and int(m.group(2)) < len(ctx[m.group(1)])):
                    self.fail(f'{sw}.actions', f'{text!r} names a var or an index that does not exist')
            if st['expect'] is not None and not (isinstance(st['expect'], list) and all(isinstance(e, dict) for e in st['expect'])):
                self.fail(f'{sw}.expect', 'must be a list of objects')
        elif st['claim'] is not None or s.get('expect') is not None:
            self.fail(sw, '"claim" and "expect" belong to a scenario: add "actions" or drop them')
        sv = s.get('save')
        if sv is not None:
            self._keys(sv, SAVE_KEYS, f'{sw}.save')
            give = self._strs(sv.get('give'), f'{sw}.save.give', t_give)
            if give is None:
                self.fail(f'{sw}.save.give', 'needs a list (here or "give" on the target)')
            flags = self._strs(sv.get('flags'), f'{sw}.save.flags', [])
            for f in flags:
                if '=' not in f:
                    self.fail(f'{sw}.save.flags', f'{f!r} must be NAME=VALUE')
            start = sv.get('start')
            if start is None and not (st['at'] and all(k in st['at'] for k in ('x', 'y', 'z', 'facing'))):
                self.fail(f'{sw}.save', 'needs "start" or the start\'s "at" with x, y, z and facing')
            st['save'] = {'name': self._str(sv, 'name', f'{sw}.save', required=False) or st['name'], 'start': start,
                          'give': give, 'flags': flags, 'point': sv.get('point'), 'note': sv.get('note'), 'optional': sv.get('optional')}
            for k in ('start', 'point', 'note', 'optional'):
                if st['save'][k] is not None and (not isinstance(st['save'][k], str) or not st['save'][k]):
                    self.fail(f'{sw}.save.{k}', 'must be a non-empty string')
            if not NAME.fullmatch(st['save']['name']):
                self.fail(f'{sw}.save.name', 'must be 1 to 64 letters, digits, . _ -')
        hold = s.get('hold')
        if hold is not None:
            self._keys(hold, HOLD_KEYS, f'{sw}.hold')
            st['hold'] = {'steps': self._steps(hold.get('steps'), st, f'{sw}.hold.steps') if hold.get('steps') is not None else None,
                          'note': self._note(hold.get('note'), st, f'{sw}.hold.note'),
                          'expect': self._str(hold, 'expect', f'{sw}.hold', required=False)}

    def _note(self, note, st, where):
        if note is None:
            return None
        if not isinstance(note, str):
            self.fail(where, 'must be a string')
        try:
            render(note, context(st), route='ok')
        except (KeyError, IndexError, ValueError, TypeError) as e:
            self.fail(where, f'{note!r} is not a valid text over the start\'s names: {type(e).__name__} {e}')
        return note

    def _steps(self, steps, st, where):
        if not isinstance(steps, list) or not steps:
            self.fail(where, 'must be a non-empty list')
        ctx = context(st)
        for i, item in enumerate(steps):
            w = f'{where}[{i}]'
            if isinstance(item, str):
                try:
                    render(item, ctx)
                except (KeyError, IndexError, ValueError, TypeError) as e:
                    self.fail(w, f'{item!r} is not a valid line over the start\'s names: {type(e).__name__} {e}')
            elif isinstance(item, dict) and set(item) == {'watch'}:
                self._strs(item['watch'], w + '.watch')
                if not item['watch']:
                    self.fail(w + '.watch', 'must not be empty')
            elif isinstance(item, dict) and set(item) == {'route'}:
                r = item['route']
                self._keys(r, ROUTE_KEYS, w + '.route')
                for k in ('from', 'to'):
                    v = ctx.get(r.get(k))
                    if not isinstance(v, list) or len(v) < 3:
                        self.fail(f'{w}.route.{k}', 'must name a var with three numbers (x, y, z)')
                for k in ('radius', 'max_steps', 'timeout'):
                    if k in r and not is_num(r[k]):
                        self.fail(f'{w}.route.{k}', 'must be a number')
            else:
                self.fail(w, 'must be a text line, {"watch": [names]} or {"route": {...}}')
        return list(steps)

    def _runs(self, hold):
        self.runs = []
        if hold is None:
            return
        self._keys(hold, {'runs'}, 'hold')
        runs = hold.get('runs')
        if not isinstance(runs, list) or not runs:
            self.fail('hold.runs', 'must be a non-empty list')
        ids = set()
        for i, r in enumerate(runs):
            w = f'hold.runs[{i}]'
            self._keys(r, RUN_KEYS, w)
            rid = self._str(r, 'id', w)
            if not NAME.fullmatch(rid) or rid in ids:
                self.fail(f'{w}.id', f'{rid!r} must be unique: 1 to 64 letters, digits, . _ -')
            ids.add(rid)
            self._str(r, 'lane', w)
            if not is_num(r.get('wall')):
                self.fail(f'{w}.wall', 'must be a number (seconds)')
            st = self.by_name.get(r.get('start')) if isinstance(r.get('start'), str) else None
            if st is None:
                self.fail(f'{w}.start', f'{r.get("start")!r} is not the name of a start')
            hold_part = st['hold'] or {}
            steps = self._steps(r['steps'], st, f'{w}.steps') if r.get('steps') is not None else hold_part.get('steps')
            if steps is None:
                self.fail(w, f'neither the run nor the start {st["name"]!r} has hold steps')
            note = self._note(r['note'], st, f'{w}.note') if 'note' in r else hold_part.get('note')
            expect = r['expect'] if 'expect' in r else hold_part.get('expect')
            if expect is not None and not isinstance(expect, str):
                self.fail(f'{w}.expect', 'must be a flag name')
            save = r.get('save') or (st['save'] or {}).get('name') or st['name']
            self.runs.append({'lane': r['lane'], 'id': rid, 'wall': r['wall'], 'start': st, 'save': save, 'steps': steps, 'note': note, 'expect': expect})

    # ---- using

    def select(self, only=None, optional=None):
        """The starts of the targets named in `only` (None = all), in table order. With `optional` (a set of names), a start whose save is
        "optional" under some name is kept only when that name is in the set, whatever `only` says; with None no start is dropped for that."""
        if only is not None:
            unknown = sorted(set(only) - set(self.targets))
            if unknown:
                raise TableError(f'{self.path}: no target with key {", ".join(unknown)} (the keys are {", ".join(self.targets)})')
        out = []
        for st in self.starts:
            opt = (st['save'] or {}).get('optional')
            if opt is not None and optional is not None:
                if opt in optional:
                    out.append(st)
            elif only is None or st['key'] in only:
                out.append(st)
        return out

    def watch_names(self):
        """Every flag name a `watch` step names, in the order they first appear (start recipes, then the runs' own steps)."""
        seen = []
        recipes = [st['hold']['steps'] for st in self.starts if st['hold'] and st['hold']['steps']] + [r['steps'] for r in self.runs]
        for steps in recipes:
            for item in steps:
                if isinstance(item, dict) and 'watch' in item:
                    seen += [n for n in item['watch'] if n not in seen]
        return seen


def load(path=None):
    p = table_path(path)
    try:
        text = p.read_text(encoding='utf-8')
    except FileNotFoundError:
        raise TableError(MISSING.format(path=p, env=ENV_TABLE, schema=SCHEMA)) from None
    except OSError as e:
        raise TableError(f'cannot read the table file {p}: {e}') from None
    try:
        data = json.loads(text)
    except ValueError as e:
        raise TableError(f'the table file {p} is not valid JSON ({e}); its format is "{SCHEMA}"') from None
    return Table(data, p)


def _world_module(name):
    sys.path.insert(0, str(HERE.parent))
    try:
        return importlib.import_module('worldmodel.' + name)
    except Exception as e:  # noqa: BLE001  (any failure to reach the world model is reported the same way)
        raise TableError(f'this needs the world model (the worldmodel folder beside this one): {type(e).__name__}: {e}') from None


def flag_hash_function():
    """The game's flag-name hash, from the world model's format module (worldmodel.game_files.load_mts().flag_hash).
    Raises TableError with the reason when the world model is not there."""
    try:
        return _world_module('game_files').load_mts().flag_hash
    except TableError:
        raise
    except Exception as e:  # noqa: BLE001
        raise TableError(f'the flag hash needs the world model\'s format module: {type(e).__name__}: {e}') from None


def planner_module():
    """The world model's path planner (worldmodel.plan: available(area), plan(area, from_xz, to_xz, ...))."""
    return _world_module('plan')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--table', help=f'the table file (default: ${ENV_TABLE}, else table.local.json beside this tool)')
    ap.add_argument('--schema', action='store_true', help='print the format of the table and exit')
    a = ap.parse_args(argv)
    if a.schema:
        print(__doc__)
        return 0
    path = a.table
    try:
        t = load(path)
    except TableError as e:
        print('bosspoints: ' + str(e), file=sys.stderr)
        return 2
    scen = sum(1 for s in t.starts if s['actions'])
    saves = sum(1 for s in t.starts if s['save'])
    holds = sum(1 for s in t.starts if s['hold'])
    print(f'{t.path}: ok; {len(t.targets)} targets, {len(t.starts)} starts ({scen} scenarios, {saves} saves, {holds} hold recipes), {len(t.runs)} hold runs')
    return 0


if __name__ == '__main__':
    sys.exit(main())
