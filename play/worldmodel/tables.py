"""The local tables of the world model: every name, pattern and number that comes from the game, kept out of the code.

The builders and the planner publish no game content. What they need to know about the game's names (which actor
class is a door, what a flag name family looks like, which event queries test a flag ...) is read at run time from one
JSON file that you write from your own game's files and keep on your own PC: `tables.json` in the data folder, or the
file `$WORLD_TABLES` names. `load()` reads and checks it; a missing or malformed file raises `TablesMissing` /
`TablesInvalid`, whose message names the file and lists the schema (it is printed from `SCHEMA` below, the one place
that defines it).

The file is a JSON object of sections, each a JSON object of keys. Sections and key types (a regex is a string in
Python's regular expression syntax; `pairs` is a list of [text, regex] pairs; `strings` a list of strings; `map` an
object of strings):

    {
      "actors": {"kinds": [["kind_a", "^Alpha"], ["kind_b", "Beta"]], "fixed_kinds": ["kind_a"],
                 "param_flag_key_re": "Key", "talk_re": "^Gamma", "crawl_anchor": "Marker"},
      "exits": {...}, "areas": {...}, "flags": {...}, "quests": {...}, "flows": {...}, "plan": {...}
    }

Kind names are the code's own words for what an object is: the code gives roles to `climbable`, `crawl`, `person`,
`exit`, `door`, `lock`, `blocker`, `chest`, `event`, `warp`, `switch`, `sign`, `item`, `enemy` (the other kinds you
define are carried through into objects.json and used by nothing else).

The optional list of readable flag names ($WORLD_FLAG_NAMES or flag_names.json in the data folder) is a JSON object
{"<flag hash as decimal digits>": "<flag name>"}; the builders find more names themselves by hashing the strings of
the game's files.
"""
import json
import re
from pathlib import Path
from types import SimpleNamespace

from . import paths

VERSION = 1

SCHEMA = {
    'actors': {
        'kinds': ('pairs', 'ordered [kind, regex] pairs: the first regex found in an actor class name gives the actor its kind'),
        'fixed_kinds': ('strings', 'kinds whose placed position can be trusted at run time (they carry no moving field)'),
        'param_flag_key_re': ('regex', 'a placement parameter key whose string value is taken for a flag or event name'),
        'talk_re': ('regex', 'actor class names that also get the talked-to record flag offered'),
        'crawl_anchor': ('str', 'class name of the markers that stand at both ends of a crawl space'),
    },
    'exits': {
        'to_child': ('str', 'the exit actor parameter: destination area for the child age'),
        'to_adult': ('str', 'the exit actor parameter: destination area for the adult age'),
        'to_start': ('str', 'the exit actor parameter: name of the start position in the destination'),
        'alt_flag': ('str', 'the exit actor parameter: flag that switches to the alternative area version'),
        'init_flag': ('str', 'the exit actor parameter: flag of the first-time event'),
        'init_event': ('str', 'the exit actor parameter: name of the first-time event'),
        'event_key_part': ('str', 'text found in the keys of the exit actor parameters that carry events'),
        'trigger_actor': ('str', 'class name of the trigger volume grouped with an exit'),
        'trigger_shape_key': ('str', 'the trigger volume parameter that names its shape'),
        'anchor_actor': ('str', 'class name of the marker an exit points at as its go-through target'),
        'anchor_name': ('str', 'the placement name of that marker'),
    },
    'areas': {
        'strip_re': ('regex', 'matches the age suffix at the end of an area name'),
        'adult_marker': ('str', 'text inside the name of an adult-age area'),
        'child_suffix': ('str', 'ending of the name of a child-age area'),
        'child_param_key': ('str', 'the area parameter that is False when an area without a suffix defaults to the adult age'),
        'stitched_key': ('str', 'the area parameter that marks a nav mesh of stitched tiles'),
        'stitched_value': ('int', 'the value of that parameter for a stitched nav mesh'),
        'tokens': ('map', 'short words found in flag names: word -> the area name they point at'),
    },
    'flags': {
        'kinds': ('pairs', 'ordered [label, regex] pairs: the first regex found in a flag name gives its category'),
        'played_prefix': ('str', 'prefix of the flag that records an event was played (followed by the event name)'),
        'talked_prefix': ('str', 'prefix of the flag that records a person was talked to (followed by the actor class name)'),
        'event_in_path_re': ('regex1', 'an event name found inside a file path of the game (group 1)'),
    },
    'quests': {
        'counter_prefix': ('str', 'prefix of the flag that counts a quest\'s steps (followed by the quest name)'),
        'counter_exp_re': ('regex1', 'a story expression flag name that tells its quest (group 1 is the quest name)'),
        'categories': ('strings', 'the category values of the quest table'),
        'main_category': ('str', 'the category the story order is built for (one of categories)'),
        'not_ready': ('str', 'the quest counter value before the quest is ready'),
        'complete': ('str', 'the quest counter value after the last step'),
        'schedule_actor_re': ('regex2', 'an event-specific schedule name: group 2 is the actor name it is a schedule of'),
        'scene_flow_prefix': ('str', 'prefix of the names of cutscene flows'),
    },
    'flows': {
        'query_prefix': ('str', 'prefix of every event query name (dropped when a condition is shown)'),
        'bool_queries': ('strings', 'event queries whose case 0 means true and case 1 false'),
        'bool_exp_query': ('str', 'the event query that tests a stack-program flag'),
        'effects': ('map', 'event action name -> effect kind: set, add, sub, step, rollback, item, currency, area'),
        'what_keys': ('strings', 'event parameter keys, tried in order, that say what a query tests'),
        'test_keys': ('strings', 'event parameter keys, tried in order, that name the flag a query tests'),
        'flag_key': ('str', 'the event parameter key that names the flag an action sets'),
        'value_key': ('str', 'the event parameter key that holds the value an action sets'),
        'quest_key': ('str', 'the event parameter key that names the quest an action advances'),
        'step_keys': ('strings', 'event parameter keys, tried in order, that name the step an action advances to'),
        'param_keys': ('strings', 'event parameter keys kept in the output'),
        'param_key_re': ('regex', 'further event parameter keys kept in the output (scalar values only)'),
        'drop_minus_one_keys': ('strings', 'kept keys that are dropped when their value is -1'),
        'what_skip_keys': ('strings', 'event parameter keys left out of a query\'s "what" text'),
        'near_type': ('str', 'text in the type of a schedule entry that starts on the player\'s approach'),
    },
    'plan': {
        'door_flag_re': ('regex', 'flag names tied to a door by its logic that are named in the plan\'s door text'),
        'door_open_hint': ('str', 'what to set to open a door, for the plan\'s door text ("" for none)'),
    },
}


class TablesError(Exception):
    pass


class TablesMissing(TablesError):
    pass


class TablesInvalid(TablesError):
    pass


def describe():
    """The schema as text: one line per key."""
    out = []
    for sec, keys in SCHEMA.items():
        for key, (typ, what) in keys.items():
            out.append(f'  {sec}.{key} ({typ}): {what}')
    return '\n'.join(out)


def _explain(path):
    return (f'The world model reads every game name and pattern from the tables file {path} ($WORLD_TABLES names another '
            'place); the code publishes none. Write that file yourself from your own game\'s files: a JSON object of '
            'sections (actors, exits, areas, flags, quests, flows, plan), each an object with the keys below, '
            f'plus "version": {VERSION}.\n' + describe())


def _problem(typ, v):
    """Why v is not of the type, or None."""
    if typ == 'str':
        return None if isinstance(v, str) else 'a string is expected'
    if typ == 'int':
        return None if isinstance(v, int) and not isinstance(v, bool) else 'an integer is expected'
    if typ.startswith('regex'):
        if not isinstance(v, str):
            return 'a regular expression string is expected'
        try:
            rx = re.compile(v)
        except re.error as e:
            return f'not a regular expression ({e})'
        need = int(typ[5:] or 0)
        return None if rx.groups >= need else f'it needs at least {need} group(s)'
    if typ == 'strings':
        return None if isinstance(v, list) and all(isinstance(x, str) for x in v) else 'a list of strings is expected'
    if typ == 'map':
        ok = isinstance(v, dict) and all(isinstance(k, str) and isinstance(x, str) for k, x in v.items())
        return None if ok else 'an object of strings is expected'
    if typ == 'pairs':
        if not (isinstance(v, list) and all(isinstance(x, list) and len(x) == 2 and all(isinstance(y, str) for y in x)
                                            for x in v)):
            return 'a list of [text, regex] pairs is expected'
        for _a, b in v:
            try:
                re.compile(b)
            except re.error as e:
                return f'{b!r} is not a regular expression ({e})'
        return None
    raise AssertionError(typ)


def check(raw):
    """The problems of a parsed tables file as a list of text lines (empty: it is well formed)."""
    if not isinstance(raw, dict):
        return ['the file must hold a JSON object']
    out = []
    if raw.get('version') != VERSION:
        out.append(f'"version" must be {VERSION}')
    for sec, keys in SCHEMA.items():
        got = raw.get(sec)
        if not isinstance(got, dict):
            out.append(f'section "{sec}" is missing or not an object')
            continue
        for key, (typ, _what) in keys.items():
            if key not in got:
                out.append(f'{sec}.{key} is missing')
                continue
            why = _problem(typ, got[key])
            if why:
                out.append(f'{sec}.{key}: {why}')
        for key in got:
            if key not in keys:
                out.append(f'{sec}.{key} is not a key of the schema')
    for sec in raw:
        if sec != 'version' and sec not in SCHEMA:
            out.append(f'"{sec}" is not a section of the schema')
    if not out:
        kinds = {k for k, _ in raw['actors']['kinds']}
        for k in raw['actors']['fixed_kinds']:
            if k not in kinds:
                out.append(f'actors.fixed_kinds: {k!r} is not a kind of actors.kinds')
        if raw['quests']['main_category'] not in raw['quests']['categories']:
            out.append('quests.main_category is not one of quests.categories')
        for k in raw['flows']['effects'].values():
            if k not in ('set', 'add', 'sub', 'step', 'rollback', 'item', 'currency', 'area'):
                out.append(f'flows.effects: {k!r} is not an effect kind')
    return out


class Tables:
    """The checked tables: sections as attributes (`T.flows.effects`); regular expressions are compiled (a key that
    ends in _re, the `pairs` of `kinds`)."""
    def __init__(self, raw, path):
        self.raw, self.path = raw, path
        for sec, keys in SCHEMA.items():
            ns = SimpleNamespace()
            for key, (typ, _what) in keys.items():
                v = raw[sec][key]
                if typ.startswith('regex'):
                    v = re.compile(v)
                elif typ == 'pairs':
                    v = [(a, re.compile(b)) for a, b in v]
                elif typ == 'strings':
                    v = list(v)
                setattr(ns, key, v)
            setattr(self, sec, ns)
        self.kind_names = list(dict.fromkeys(k for k, _ in self.actors.kinds))
        self.fixed_kinds = frozenset(self.actors.fixed_kinds)
        self._kind_cache = {}

    def kind_of(self, gyaml):
        """The kind of an actor class name, or None."""
        if gyaml not in self._kind_cache:
            self._kind_cache[gyaml] = next((k for k, r in self.actors.kinds if r.search(gyaml)), None)
        return self._kind_cache[gyaml]

    def flag_kind(self, name):
        """The category of a flag name ('other' when no pattern of flags.kinds finds it)."""
        return next((k for k, r in self.flags.kinds if r.search(name)), 'other')

    def area_base(self, banc):
        """An area name without its age suffix."""
        return self.areas.strip_re.sub('', banc)

    def age_of(self, banc):
        """'adult' or 'child' by the area's name, else None."""
        a = self.areas
        return 'adult' if a.adult_marker in banc else 'child' if banc.endswith(a.child_suffix) else None


_cache = {}


def load(path=None):
    """The checked tables of `path` (default: paths.tables_path()). Raises TablesMissing / TablesInvalid."""
    p = Path(path) if path else paths.tables_path()
    try:
        st = p.stat()
    except OSError:
        raise TablesMissing(f'the tables file {p} does not exist. ' + _explain(p)) from None
    key = (str(p), st.st_mtime_ns, st.st_size)
    if key in _cache:
        return _cache[key]
    try:
        raw = json.loads(p.read_text())
    except (OSError, ValueError) as e:
        raise TablesInvalid(f'the tables file {p} cannot be read as JSON ({e}). ' + _explain(p)) from None
    bad = check(raw)
    if bad:
        raise TablesInvalid(f'the tables file {p} does not match the schema:\n  ' + '\n  '.join(bad[:20])
                            + ('\n  ...' if len(bad) > 20 else '') + '\n' + _explain(p))
    _cache.clear()
    _cache[key] = Tables(raw, p)
    return _cache[key]
