"""The co-op story-scene list, rebuilt offline from a player's own RomFS (the same list `host/coop_scenes.c` makes at run time).

The events of the EventSetting table, each as the hash of "<played prefix><row id>", less every played-flag name that any file of the
scanned folders spells out (something reads those, so they stay shared). The folders, the table's file name and the prefix are read
from the LS source (`scan_settings`), with the values below as the fallback. The module can hand every decoded file to a callback,
so that the name search reads the files in the same pass.
"""
import re
import struct
from dataclasses import dataclass, field

import fd_romfs

DEFAULTS = dict(folders=["AI", "AISchedule", "ActorSystem", "AoC1", "BSA", "Banc", "Chemical", "Component", "Env", "Event/EventFlow",
                         "Event/ResidentEventList", "Game", "GameData", "GameParameter", "Layout2Shader", "Lib", "Life", "Logic", "Pack",
                         "Perception", "RSDB", "Reaction", "Scene", "Sequence", "System", "VolumeStats", "WorldMgr"],
                table_folder="RSDB", table_start="EventSetting.Product.", table_end=".rstbl.byml.zs",
                prefix="HavePlayedEvent.", name_max=255)
NAME = re.compile(r"[A-Za-z0-9_]+")


@dataclass
class Scenes:
    events: dict = field(default_factory=dict)    # hash of the played flag -> the event's row id
    gated: set = field(default_factory=set)       # of them, named by other data of the game
    kept: set = field(default_factory=set)        # the list: each player's own unless the room shares scenes
    files: int = 0
    skipped: list = field(default_factory=list)   # files that could not be read or decoded

    def stamp(self, version=1):
        """The list's stamp the game logs ("list 42165167"): FNV-1a over the version and the sorted hashes."""
        if not self.kept:
            return 0
        h = 2166136261
        for byte in struct.pack("<I", version) + b"".join(struct.pack("<I", x) for x in sorted(self.kept)):
            h = ((h ^ byte) * 16777619) & 0xFFFFFFFF
        return h or 1


def settings(source_settings=None):
    out = dict(DEFAULTS)
    out.update({k: v for k, v in (source_settings or {}).items() if v})
    return out


def scan(romfs, source_settings=None, on_file=None):
    """Make the list. `on_file(path, data)` is called for each file that was read."""
    cfg = settings(source_settings)
    prefix = cfg["prefix"].encode()
    found = re.compile(re.escape(prefix) + rb"[A-Za-z0-9_]*")
    files = []
    for folder in cfg["folders"]:
        files.extend(romfs.walk(folder))
    files.sort()
    table = next((p for p, _ in files if p.startswith(cfg["table_folder"] + "/") and "/" not in p[len(cfg["table_folder"]) + 1:]
                  and p.split("/", 1)[1].startswith(cfg["table_start"]) and p.endswith(cfg["table_end"])), None)
    if table is None:
        raise ValueError("the EventSetting table (%s/%s*%s) is not in the RomFS" % (cfg["table_folder"], cfg["table_start"], cfg["table_end"]))
    scenes, spelled, rows = Scenes(), set(), None
    for path, _ in files:
        try:
            data = romfs.read(path)
        except Exception as error:   # (counted, never guessed from: the game does the same)
            scenes.skipped.append("%s: %s" % (path, error))
            continue
        scenes.files += 1
        for m in found.finditer(data):
            if 1 <= len(m.group(0)) - len(prefix) <= cfg["name_max"]:
                spelled.add(fd_romfs.murmur3(m.group(0)))
        if path == table:
            rows = fd_romfs.byml(data)
        if on_file:
            on_file(path, data)
    if not isinstance(rows, list):
        raise ValueError("the EventSetting table cannot be read as a list of rows")
    for row in rows:
        rid = row.get("__RowId") if isinstance(row, dict) else None
        if isinstance(rid, str) and 1 <= len(rid) <= cfg["name_max"] and NAME.fullmatch(rid) and rid.isascii():
            scenes.events[fd_romfs.murmur3(cfg["prefix"] + rid)] = rid
    scenes.gated = {h for h in scenes.events if h in spelled}
    scenes.kept = set(scenes.events) - scenes.gated
    if not scenes.events:
        raise ValueError("the EventSetting table names no event")
    return scenes
