"""Where the world model reads and writes its local files. Nothing here names a place on any one machine.

- the game: `--game <folder>` of a builder, else $WORLD_GAME. An extracted RomFS folder (it holds GameData/) or a game
  copy that holds romfs/. There is no default.
- the data folder, where the builders write areas.json, links.json, objects.json, flags.json, gates.json, flows.json,
  story.json, summary.json, mobility.json, navinfo.json, inventory.json/.md and nav/<area>.json.gz, and where the
  planner and the readers look: $PILOT_WORLD, else `world/` beside the `worldmodel/` folder (the tree root is the
  parent of this package). A folder named `world/` is private data in the repository, which is why the code is not
  called that.
- the tables file (tables.py): $WORLD_TABLES, else tables.json in the data folder.
- the optional list of readable flag names: $WORLD_FLAG_NAMES, else flag_names.json in the data folder.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def data_dir():
    env = os.environ.get('PILOT_WORLD')
    return Path(env) if env else ROOT / 'world'


def tables_path(data=None):
    """$WORLD_TABLES, else tables.json in `data` (default: the data folder)."""
    env = os.environ.get('WORLD_TABLES')
    return Path(env) if env else (Path(data) if data else data_dir()) / 'tables.json'


def flag_names_path(data=None):
    """$WORLD_FLAG_NAMES, else flag_names.json in `data` (default: the data folder)."""
    env = os.environ.get('WORLD_FLAG_NAMES')
    return Path(env) if env else (Path(data) if data else data_dir()) / 'flag_names.json'


def game_dir(arg=None):
    """The game folder to read: the argument, else $WORLD_GAME; exits with a message when neither is set."""
    g = arg or os.environ.get('WORLD_GAME')
    if not g:
        sys.exit('worldmodel: no game folder: give --game <folder> or set WORLD_GAME (an extracted RomFS: a folder '
                 'that holds GameData/, or a game copy that holds romfs/)')
    return g
