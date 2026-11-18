"""The scoreboard's private settings (playbench-local/config.json) with defaults, and the paths every part shares."""
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _harness():
    """The harness folder (the one with hs_names.py): the environment's PLAYBENCH_HARNESS, else the folder this checkout or snapshot sits in. A frozen copy of the
    tools sits deeper (under the private folder's tools/<stamp>/): the waiter and the timer set the environment for it."""
    if os.environ.get('PLAYBENCH_HARNESS'):
        return Path(os.environ['PLAYBENCH_HARNESS'])
    return HERE.parent.parent


HARNESS = _harness()


def names_dir():
    """The folder with hs_names.py: the harness folder itself or, in a checkout of the workbench repository, its harness/ folder (as hsap.py and pilot.py find it)."""
    return HARNESS if (HARNESS / 'hs_names.py').is_file() else HARNESS / 'harness'


LOCAL = Path(os.environ.get('PLAYBENCH_LOCAL') or HARNESS / 'playbench-local')
DEFAULTS = {
    'pilot_repo': str(HARNESS / 'playthrough-max'),         # the pilot's dev master: each hold plays its COMMITTED head (git archive), never a half-edited working tree
    'tools_repo': str(HARNESS / 'playthrough-playbench'),   # where playbench/ is committed; a hold runs a frozen copy of it
    'tools_root': str(LOCAL / 'tools'),                    # where the frozen copies of playbench/ are kept (a queued hold runs one, whatever is committed meanwhile)
    'python': '/usr/bin/python3',
    'copies': None,            # PRIVATE (required): the lanes, one warm game copy each (folders of the harness's game copies)
    'hold_s': 1100,            # a hold keeps the card at most this long (the rule: 1,100 s inside, shutdown included)
    'reserve_s': 120,          # the end of the hold kept for scoring, evidence and the chain (running cells are cut 20 s later than the last start allowed)
    'shots': 900,              # a picture every this many presents
    'arms': ['rules', 'cheap', 'rules-tactics', 'cheap-learned'],   # the arms played every night (names in the table in arms.py); an arm the committed pilot cannot play is skipped
    'max_holds_per_night': 6,
    'max_attempts': 2,         # a cell cut short (invalid) is tried once more in a later hold of the same night
    'allowance_usd': 5.0,      # the scoreboard's own spend a night, inside the pilot's caps (3 USD a run, 50 a night)
    'key_file': None,          # PRIVATE (required): the model key file the pilot reads (PILOT_OPENAI_KEY_FILE)
    'quiet_lock': None,        # PRIVATE (required): the shared lane's quiet-window lock file
    'measuring_lock': None,    # PRIVATE (required): the shared lane's measuring lock file
    'reports': None,           # PRIVATE (required): the folder for evidence, tables and charts (the waiter's folder: its name is the dispatcher's priority key)
    'drafts': None,            # PRIVATE (required): where the weekly draft and its picture are written
    'issue_url': None,         # PRIVATE (required): the tracker thread the weekly draft is an update for
    'timer_enabled': False,    # the nightly timer stays off until the user's word (the nightly skill's rule); `arm --user-authorized` needs it true
    'timer_time': '02:30:00',
    'game_env': {},            # extra environment for every game run of a hold (e.g. a texture budget so two games on one card fit): recorded with the hold
    'idle_s': 120,             # the player must have been away this long before a night starts
    'idle_timeout_s': 1800,
}


REQUIRED = tuple(k for k, v in DEFAULTS.items() if v is None)


def load(path=None, require=True):
    """The settings: DEFAULTS with the private file's values on top (unknown keys are errors: a typo must not silently fall back). The machine's own values
    (REQUIRED: copies, locks, folders, key file, issue URL) have no default: a file that leaves one out is an error naming it (`require=False`: tests)."""
    path = Path(path) if path else LOCAL / 'config.json'
    cfg = dict(DEFAULTS)
    if path.is_file():
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError) as e:
            raise ValueError(f'{path}: not readable JSON ({e})') from None
        bad = sorted(set(data) - set(DEFAULTS) - {'_note'})
        if bad:
            raise ValueError(f'{path}: unknown settings {bad}')
        cfg.update({k: v for k, v in data.items() if k != '_note'})
    missing = [k for k in REQUIRED if cfg.get(k) is None]
    if require and missing:
        raise ValueError(f'{path}: no value for {missing} (private settings; see README.md)')
    return cfg


def local_dir():
    return Path(os.environ.get('PLAYBENCH_LOCAL') or LOCAL)


def results_db():
    return LOCAL / 'results.sqlite'


def night_dir(cfg, night):
    return Path(cfg['reports']) / 'nights' / night
