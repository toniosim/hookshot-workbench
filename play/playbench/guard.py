"""The player wins. A game whose executable or working folder is the user's own (the play folders, the projects' user storage) means the user is playing: no
scoreboard run starts, and one that runs is stopped and marked cut short (excluded from the trend). The same rule as the nightly's monitor.py, restated here
because that module imports a `metrics` of its own that clashes with the pilot's. Never touches or stops the player's process: it only reports it."""
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import config  # noqa: E402

HARNESS = config.HARNESS
if str(config.names_dir()) not in sys.path:
    sys.path.insert(0, str(config.names_dir()))


def _config():
    try:
        return json.loads((HARNESS / 'nightly-local' / 'config.json').read_text())
    except (OSError, ValueError):
        return {}


def protected_roots(home=None):
    from hs_names import protected_user_paths
    home = Path(home or Path.home())
    cfg = _config()
    roots = [*protected_user_paths(home)]
    if cfg.get('play_folder'):
        roots.append(Path(cfg['play_folder']))
    roots += [Path(p) for p in cfg.get('play_folders', [])]
    return roots


def is_protected(path, roots, home=None):
    p = Path(path)
    home = Path(home or Path.home())
    if any(p.is_relative_to(r) for r in roots):
        return True
    games = home / 'Games'
    from hs_names import PROJECTS
    return p.is_relative_to(games) and p.relative_to(games).parts[0].startswith(('Ocarina', *(x.title() for x in PROJECTS))) and not p.relative_to(games).parts[0].startswith('.')


def processes(proc=Path('/proc')):
    out = []
    for d in proc.iterdir():
        if not d.name.isdigit():
            continue
        try:
            out.append({'pid': int(d.name), 'exe': os.readlink(d / 'exe'), 'cwd': os.readlink(d / 'cwd')})
        except OSError:
            continue
    return out


def player_games(records=None, home=None):
    """The running processes that are the user's own game: [{pid, exe, cwd}]."""
    from hs_names import GAME_EXECUTABLES
    roots = protected_roots(home)
    records = processes() if records is None else records
    return [p for p in records if Path(p['exe']).name in GAME_EXECUTABLES and (is_protected(p['exe'], roots, home) or is_protected(p.get('cwd', '/'), roots, home))]


def wait_idle(seconds=120.0, timeout=None, poll=1.0, probe=player_games, now=time.monotonic, sleep=time.sleep, log=None):
    """True after `seconds` of continuous observation with no player game (the clock restarts whenever one is seen); False when `timeout` passes first."""
    start, quiet = now(), None
    while True:
        t = now()
        seen = probe()
        if seen:
            quiet = None
        elif quiet is None:
            quiet = t
        if log:
            log({'player_pids': [p['pid'] for p in seen], 'quiet_for_s': 0 if quiet is None else round(t - quiet, 1)})
        if quiet is not None and t - quiet >= seconds:
            return True
        if timeout is not None and t - start >= timeout:
            return False
        sleep(poll)
