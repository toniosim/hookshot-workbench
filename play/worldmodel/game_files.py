"""The world model's reader of the game's files: formats.py's readers with the file list of the whole RomFS folder,
which the world builder walks (formats.PlainFiles lists Banc/ only).

    from worldmodel.game_files import load_mts
    mts = load_mts(); g = mts.Game('<extracted RomFS folder>')

`load_mts()` returns a module with `murmur`, `flag_hash`, `byml`, `sarc`, `Game`, `Romfs`, `Sav`, `yaw_of` and
`area_age` (the age rules of an area name come from the tables file). A file that is not in the RomFS is a KeyError.
"""
import os
import types

from . import formats, tables


class FullFiles(dict):
    """Every file of a plain RomFS folder: path ('/'-separated, sorted) -> (0, size)."""
    def __init__(self, root):
        found, todo = {}, [(str(root), '')]
        while todo:
            d, rel = todo.pop()
            with os.scandir(d) as it:
                for e in it:
                    p = f'{rel}{e.name}'
                    if e.is_dir(follow_symlinks=False):
                        todo.append((e.path, p + '/'))
                    else:
                        found[p] = (0, e.stat().st_size)
        super().__init__((p, found[p]) for p in sorted(found))


class Romfs(formats.Romfs):
    """A file not in the RomFS is a KeyError (navmesh.py tries names that way)."""
    files_class = FullFiles

    def raw(self, path):
        if path not in self.files:
            raise KeyError(path)
        return super().raw(path)


class Game(formats.Game):
    romfs_class = Romfs


def area_age(game, banc, T=None):
    """(the age the game gives the player in the area, how sure): 'only' when the area's name says it, else 'default'
    by the area parameter the tables name."""
    T = T or tables.load()
    age = T.age_of(banc)
    if age:
        return age, 'only'
    p = game.bancparam(banc) or {}
    if p.get(T.areas.child_param_key) is False:
        return 'adult', 'default'
    return 'child', 'default'


def load_mts():
    m = types.ModuleType('worldmodel.mts')
    m.__dict__.update({k: v for k, v in vars(formats).items() if not k.startswith('__')})
    m.PlainFiles, m.Romfs, m.Game, m.area_age = FullFiles, Romfs, Game, area_age
    return m
