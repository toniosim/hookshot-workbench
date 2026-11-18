"""The capability scoreboard: a fixed set of cells and the arms that play them.

A CELL is one small task for the playthrough pilot: a save-placed start and a goal that the GAME'S STATE proves (a flag, a count, a map, a place at a
height), never the pilot's own word. The eleven cells cover what a player does between two story points: open a door (from its front, and from the
wrong side), climb a ledge, take a drop, climb a ladder, cross a crowd, open a chest, pick up items (one needs a dive), play a warp song, use an item,
and one short chapter. An ARM is a way of playing (the rules player, the cheap model arm, and whatever tactics/lessons arms are added later).

This module names no place, coordinate, flag or save: the public part has the cell ids, what each cell asks, its default budget; the private file
`board-local.json` (next to the results, never published) gives each cell its segment, save, proof and start (see `load`). A cell the private file does not
define is `missing` in the plan, never silently skipped. The fixed scoreboard is the private file plus the frozen segments and saves it points at: a
cell's FINGERPRINT (segment text, save content, proof, start, budgets) is recorded with every result, and a changed fingerprint starts a new series.

Arms are public data (the table in arms.py): name -> {label, decider, planner, args, env, requires}. `requires` is a text the pilot's `run -h` must contain (a flag
a later arm needs): an arm whose requirement is not met is `unavailable` for the night, not failed.
"""
import copy
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import arms as armdata  # noqa: E402
import config  # noqa: E402

HARNESS, LOCAL = config.HARNESS, config.LOCAL

KINDS = ('segment', 'chapter')   # a segment TOML (goals: pilot.py) or a chapter TOML (an `aim` and objectives: sections.py)
PROOFS = ('flag', 'flag_drop', 'rupees_gain', 'at', 'map', 'any', 'all')
BOOT_S, GRACE_S = 90.0, 30.0     # the game's start under load (50 to 110 s seen) and the pilot's end step; a cell's wall is boot + budget + grace
ID_RE = re.compile(r'^[a-z][a-z0-9-]{1,30}$')


@dataclass(frozen=True)
class Cell:
    id: str
    title: str
    asks: str                     # what the cell asks, in words with no game facts
    kind: str = 'segment'
    budget_s: float = 80.0        # seconds of play after control
    max_decisions: int = 40
    # private (board-local.json):
    segment: str = None           # file under the local `segments/` folder (frozen copy)
    save: str = None              # folder under the local `saves/` folder (frozen copy), or None: the segment's own
    proof: dict = field(default_factory=dict)   # what the game's state must show (referee.py)
    start: dict = None            # {map, x, z, tol_m}: where the first sample must be (else the run is `invalid`, not a failure)
    enabled: bool = True
    note: str = ''
    blocker: str = None           # a KNOWN cause outside the pilot that makes the cell fail today (e.g. a game input that does nothing): a failed run is stored as `blocked`, not as a failure of the player

    @property
    def wall_s(self):
        return int(BOOT_S + self.budget_s + GRACE_S)


PUBLIC = (
    Cell('door-front', 'open a door from its front', 'walk to a door, open it at its prompt and go through', budget_s=80),
    Cell('door-wrong', 'open a door approached from the wrong side', 'the same door, but the first way in is the side that stays shut: find the side that opens',
         budget_s=90),
    Cell('ledge', 'climb up a ledge', 'get onto a ledge that is higher than a walk can reach', budget_s=60),
    Cell('drop', 'take a drop', 'go down from a high platform to the ground below', budget_s=60),
    Cell('ladder', 'climb a ladder', 'climb a ladder to the platform at its top', budget_s=70),
    Cell('crowd', 'cross a crowd', 'cross a busy town square where people stand in the way', budget_s=80),
    Cell('chest', 'open a chest', 'walk to a chest, open it from its front and read what it holds', budget_s=70),
    Cell('pickup-dive', 'pick up items, one under water', 'collect the rupees, one of them lies on the floor of a pond', budget_s=100),
    Cell('song-warp', 'play a warp song', 'play a song on the ocarina that carries Link to another place', budget_s=80),
    Cell('item-bomb', 'use an item', 'use the item on the item button (a bomb) once', budget_s=70),
    Cell('chapter-lake', 'one short chapter: the field to the lake', 'cross the open field to the lake shore (a chapter: objectives, a planner)', kind='chapter',
         budget_s=200, max_decisions=60),
)
LOCAL_FIELDS = ('segment', 'save', 'proof', 'start', 'budget_s', 'max_decisions', 'enabled', 'note', 'blocker')


class BoardError(ValueError):
    pass


def local_dir():
    return config.local_dir()


def load(path=None):
    """The cells: PUBLIC with the private file's fields applied, entry by entry (a new list). `path`: the private JSON (default board-local.json in the
    local folder); a missing file gives PUBLIC unchanged (every cell `missing`). Unknown cells or fields, a bad proof or a bad id are errors."""
    path = Path(path) if path else local_dir() / 'board-local.json'
    if not path.is_file():
        return list(PUBLIC)
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        raise BoardError(f'{path}: not readable JSON ({e})') from None
    if not isinstance(data, dict):
        raise BoardError(f'{path}: a JSON object of cell id -> fields')
    ids = {c.id for c in PUBLIC}
    unknown = sorted(set(data) - ids - {'_note'})
    if unknown:
        raise BoardError(f'{path}: unknown cells {unknown}; the board has {sorted(ids)}')
    out = []
    for c in PUBLIC:
        over = data.get(c.id)
        if over is None:
            out.append(c)
            continue
        if not isinstance(over, dict) or set(over) - set(LOCAL_FIELDS):
            raise BoardError(f'{path}: cell {c.id}: an object with only {", ".join(LOCAL_FIELDS)}')
        c = replace(c, **over)
        bad = proof_errors(c.proof) if c.proof else []
        if bad:
            raise BoardError(f'{path}: cell {c.id}: {"; ".join(bad)}')
        out.append(c)
    return out


def proof_errors(p, top=True):
    """What is wrong with a proof spec (a list of words; [] when it is a proof the referee can judge)."""
    if not isinstance(p, dict) or p.get('kind') not in PROOFS:
        return [f'proof kind must be one of {PROOFS}']
    k, bad = p['kind'], []
    if k == 'flag':
        if not p.get('name') or p.get('op', '=') not in ('=', '!=', '<', '>', '<=', '>=') or 'value' not in p:
            bad.append('flag needs name, value and optionally op')
    elif k == 'flag_drop':
        if not p.get('name'):
            bad.append('flag_drop needs name (and optionally drop, default 1)')
    elif k == 'rupees_gain':
        if not isinstance(p.get('gain'), int) or p['gain'] < 1:
            bad.append('rupees_gain needs a whole gain of 1 or more')
    elif k == 'at':
        if not all(isinstance(p.get(f), (int, float)) for f in ('x', 'z', 'r')) or not p.get('map'):
            bad.append('at needs map, x, z, r (and optionally y_min, y_max, forbid)')
        for z in p.get('forbid') or ():
            if not isinstance(z, dict) or not all(isinstance(z.get(f), (int, float)) for f in ('x', 'z', 'r')):
                bad.append('a forbid zone needs x, z, r (and optionally y_min, y_max)')
    elif k == 'map':
        if not p.get('to'):
            bad.append('map needs `to`')
    else:
        sub = p.get('of')
        if not isinstance(sub, list) or not sub:
            bad.append(f'{k} needs a list `of` of proofs')
        else:
            for s in sub:
                bad += proof_errors(s, False)
    return bad


def proof_flags(p):
    """The flag names a proof reads (the segment's `watch` must list each: the state tap carries watched flags only)."""
    if not p:
        return set()
    if p['kind'] in ('flag', 'flag_drop'):
        return {p['name']}
    if p['kind'] in ('any', 'all'):
        return set().union(*(proof_flags(s) for s in p['of']))
    return set()


def arms(path=None):
    """{name: arm dict} (an arm needs `decider` in rules|openai-decisions): the committed table (arms.py, a copy), or a JSON file's (a plan's own `arms_file`)."""
    if path:
        path = Path(path)
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError) as e:
            raise BoardError(f'{path}: not readable JSON ({e})') from None
    else:
        path, data = Path(armdata.__file__), copy.deepcopy(armdata.ARMS)
    out = {}
    for name, a in data.items():
        if name.startswith('_'):
            continue
        if not ID_RE.match(name) or not isinstance(a, dict) or a.get('decider') not in ('rules', 'openai-decisions'):
            raise BoardError(f'{path}: arm {name!r}: an id and an object with decider rules or openai-decisions')
        out[name] = a
    return out


def arm_args(arm, cell):
    """(argv after `pilot.py run <segment>`, extra environment) of one arm on one cell: the decider, the planner or the chapter planner, the arm's own args."""
    argv = ['--decider', arm['decider']]
    if cell.kind == 'chapter':
        if not arm.get('planner'):
            argv.append('--no-chapter-planner')   # the rules player plays the chapter's own outline: no model
    elif arm.get('planner'):
        argv.append('--planner')
    argv += [str(x) for x in arm.get('args') or ()]
    return argv, {str(k): str(v) for k, v in (arm.get('env') or {}).items()}


def tree_hash(path):
    """sha256 over the relative names and contents of every file under path (a file: its content), '' when it is not there."""
    p = Path(path)
    h = hashlib.sha256()
    if p.is_file():
        h.update(p.read_bytes())
        return h.hexdigest()
    if not p.is_dir():
        return ''
    for f in sorted(x for x in p.rglob('*') if x.is_file()):
        h.update(str(f.relative_to(p)).encode() + b'\0')
        h.update(f.read_bytes() + b'\0')
    return h.hexdigest()


def fingerprint(cell, local=None):
    """What makes a cell the same cell on two nights: the frozen segment, the frozen save, the proof, the start and the budgets (16 hex digits)."""
    local = Path(local) if local else local_dir()
    h = hashlib.sha256()
    h.update(tree_hash(local / 'segments' / cell.segment).encode() if cell.segment else b'')
    h.update(tree_hash(local / 'saves' / cell.save).encode() if cell.save else b'')
    h.update(json.dumps([cell.proof, cell.start, cell.budget_s, cell.max_decisions, cell.kind], sort_keys=True).encode())
    return h.hexdigest()[:16]


def missing(cell, local=None):
    """Why a cell cannot be played ([] when it can): the private file has not defined it, or its frozen files are not there."""
    local = Path(local) if local else local_dir()
    why = []
    if not cell.enabled:
        why.append('disabled')
    if not cell.segment or not cell.proof:
        why.append('not defined in board-local.json')
        return why
    if not (local / 'segments' / cell.segment).is_file():
        why.append(f'no frozen segment {cell.segment}')
    if cell.save and not (local / 'saves' / cell.save).is_dir():
        why.append(f'no frozen save {cell.save}')
    return why
