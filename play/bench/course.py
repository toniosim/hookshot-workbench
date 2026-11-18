"""The benchmark course: a fixed set of short segments (made from segments that already exist, on saves that already exist)
and the arms (deciders) that play it.

The course names no place, coordinate or game fact: each entry names a SOURCE segment file of pilot/segments/ (a local,
unpublished folder) and how to cut it (which goals, how many of their targets), by a placeholder; the real names are in the
private course-local.json (see `load`). mkcourse.py makes the cut segments into bench/segments/ (also local); a source that
is missing makes its entry `missing` in the plan, never a silent skip.

Entries cover: walking (open ground), a hard route (the targets a pilot has been stuck at; they come from a local
hard-points file when one is given), interactions (a chest; a door, a scene and a talk), a follow (a ghost leader the runner
moves, ghost.py) and a fight (a ring of spots where enemies come). `tas` names a scripted route of the same segment
(pilot/routes/) where one exists: its run is the baseline row.

Arms: rules (the control: no model), decisions (the Decisions API decider and the planner), decisions+vision (the same
with the pilot's eyes, vision.py, on the cheap Decisions backend), decisions+vision-big (the same with the flagship model
for the pictures and for the planner, through the Responses API).
"""
import json
import os
from dataclasses import dataclass, field, replace
from pathlib import Path

HERE = Path(__file__).resolve().parent

# What an arm changes in the pilot's command line (run.py turns it into arguments and environment).
ARMS = {
    'rules': {'decider': 'rules'},
    'decisions': {'decider': 'openai-decisions', 'planner': True},
    'decisions+vision': {'decider': 'openai-decisions', 'planner': True, 'vision': {'backend': 'decisions'}},
    'decisions+vision-big': {'decider': 'openai-decisions', 'planner': True,
                             'vision': {'backend': 'responses', 'model': 'gpt-6-astra'},
                             'env': {'PILOT_PLANNER_MODEL': 'gpt-6-astra'}},
}
DEFAULT_ARMS = ('rules', 'decisions', 'decisions+vision')
VISION_EVERY_S = 30   # the cells are short (a minute or two of play): a regular look twice a minute, besides stuck points and oddities


@dataclass
class Entry:
    id: str
    kind: str                       # what it covers
    source: str                     # segment file (without .toml) of pilot/segments/ it is cut from
    goals: dict = field(default_factory=dict)   # goal name -> how many of its first targets (None: all, 'hard': the hard points)
    budget_s: float = 60.0          # game seconds of play, from the first decision
    boot_s: float = 70.0            # the game's start (the pilot's `gameplay_after_s` is about 50) and its end
    max_decisions: int = 60
    save: str = None                # overrides the source segment's save (a library entry, an absolute folder, kept:<tag>)
    follow: str = None              # 'other': a ghost leader along the route of the goal `ghost` of segment `ghost_source`
    ghost_source: str = None
    ghost_goal: str = None
    ghost_speed: float = 4.5        # metres a second while it runs, and it stands a second at each point
    tas: str = None                 # a route file of pilot/routes/: the scripted baseline of this entry
    note: str = ''

    @property
    def wall_s(self):
        return int(self.boot_s + self.budget_s + 30)


# The published course: six entries with PLACEHOLDER sources, goal names and routes. What they stand for in a real game (which segment of
# your own, which of its goals, which save, which scripted route, which leader's route) is private: course-local.json beside this file (or
# the file PILOT_BENCH_LOCAL names), `{"<entry id>": {"source": ..., "goals": {...}, "save": ..., "ghost_source": ..., "ghost_goal": ...,
# "tas": ...}}`, overrides those fields entry by entry (`load`). An entry whose source is still a placeholder is `missing` in the plan.
PUBLIC = [
    Entry('walk', 'walking: open ground, a few long legs', 'walk-source', {'goal-1': 6}, budget_s=50, max_decisions=40),
    Entry('door-talk', 'interaction: a door, a scene, a talk', 'door-talk-source', {}, budget_s=110, max_decisions=60,
          tas='door-talk-route.txt'),
    Entry('follow', 'follow a moving player (a ghost leader)', 'follow-source', {'goal-1': 6}, budget_s=60,
          max_decisions=60, follow='other', ghost_source='follow-leader-source', ghost_goal='goal-1'),
    Entry('hard', 'a hard route: targets a pilot got stuck at', 'walk-source', {'goal-1': 'hard'}, budget_s=75, max_decisions=50),
    Entry('chest', 'interaction: open a chest', 'chest-source', {'goal-1': None, 'goal-2': None}, budget_s=60,
          max_decisions=40),
    Entry('fight', 'a fight: a ring of spots where enemies come', 'fight-source', {'goal-1': None, 'goal-2': 3},
          budget_s=60, max_decisions=40),
]
LOCAL_FIELDS = ('source', 'goals', 'save', 'ghost_source', 'ghost_goal', 'tas')


def load(path=None):
    """PUBLIC with the private file's overrides applied (a new list; PUBLIC is not changed). A missing file: PUBLIC as it is."""
    path = Path(path) if path else Path(os.environ.get('PILOT_BENCH_LOCAL') or HERE / 'course-local.json')
    if not path.is_file():
        return list(PUBLIC)
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        raise ValueError(f'{path}: not readable JSON ({e})') from None
    if not isinstance(data, dict):
        raise ValueError(f'{path}: a JSON object of entry id -> fields')
    ids = {e.id for e in PUBLIC}
    out = []
    for e in PUBLIC:
        over = data.get(e.id)
        if over is None:
            out.append(e)
            continue
        if not isinstance(over, dict) or set(over) - set(LOCAL_FIELDS):
            raise ValueError(f'{path}: entry {e.id}: an object with only {", ".join(LOCAL_FIELDS)}')
        out.append(replace(e, **over))
    unknown = sorted(set(data) - ids)
    if unknown:
        raise ValueError(f'{path}: unknown entries {unknown}; the course has {sorted(ids)}')
    return out


COURSE = load()


def entry(entry_id):
    for e in COURSE:
        if e.id == entry_id:
            return e
    raise KeyError(entry_id)
