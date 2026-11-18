"""Recover the names of a player's own flags by hashing.

The game's flag list has only hashes, so a name is kept only when the hash of that exact text matches a flag, a struct or a struct member
of the list. Sources, all local: the identifiers in the game's own files (read in the same pass as the story-scene list), the rows of
the EventSetting table, the decimal 64-bit ids of the placed actors (a struct's members can be named by them), names the player supplies
(`--names FILE`, `--sweep DIR` for text that quotes names), and the struct hierarchy itself: a child of a struct named S is named
"S.<member>" and checked by hash, never assumed. Nothing here carries a name or a list of the game's.
"""
import os
import re
from pathlib import Path

import fd_romfs

TOKEN = re.compile(rb"[A-Za-z_][A-Za-z0-9_]{3,}(?:\.[A-Za-z0-9_]+)*")
BANC = re.compile(r"Banc/.+/(.+?)_(Static|Dynamic)\.bcett\.byml\.zs$")
MAX_SWEEP_FILE = 8 << 20
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "runs"}
STRUCTURAL = ("struct",)


def plausible(name, strict=False):
    """Whether a name found by chance could be a flag's: a hash is 32 bits, so a few thousand flags are matched by junk text.
    Applied to the names of flags with no struct (never to a member's or a struct's name)."""
    if not re.fullmatch(r"[A-Za-z0-9_.]+", name) or len(name) < 7:
        return False
    if re.match(r"[A-Z]", name):
        return True
    return not strict and "_" in name and bool(re.match(r"[a-z]", name))


class Collector:
    """Fed every decoded file of the story-scene pass: collects identifiers and the placed actors of the Banc files."""

    def __init__(self):
        self.tokens = set()
        self.actors = {}      # 64-bit hash of a placed actor -> (map, class, instance name)

    def add_file(self, path, data):
        self.tokens.update(TOKEN.findall(data))
        m = BANC.search(path)
        if m:
            try:
                tree = fd_romfs.byml(data)
            except Exception:
                return
            for actor in tree.get("Actors", []) if isinstance(tree, dict) else []:
                h = actor.get("Hash")
                if isinstance(h, int):
                    self.actors.setdefault(h & 0xFFFFFFFFFFFFFFFF, (m.group(1), actor.get("Gyaml"), actor.get("Name")))


class Book:
    def __init__(self, targets):
        self.targets = set(targets)       # the hashes worth naming: flags, structs, members
        self.names = {}                   # hash -> (name, source)
        self.actors = {}
        self.rejected = []                # names supplied by the player that match no hash

    def add(self, name, source):
        h = fd_romfs.murmur3(name)
        if h in self.targets and h not in self.names:
            self.names[h] = (name, source)
            return True
        return False

    def flag_name(self, h):
        """(name, source) of a flag, or None: a chance match with junk text is not a name."""
        hit = self.names.get(h)
        if hit is None:
            return None
        name, source = hit
        if source not in STRUCTURAL and "." not in name and not plausible(name, strict=source == "sweep"):
            return None
        return hit


def expand(pattern):
    """A line of a names file: a name, or a name with one numbered range, `Part{000..127}` (the width of the first number is kept)."""
    m = re.search(r"\{(\d+)\.\.(\d+)\}", pattern)
    if not m:
        yield pattern
        return
    width = len(m.group(1))
    for i in range(int(m.group(1)), int(m.group(2)) + 1):
        yield pattern[:m.start()] + str(i).zfill(width) + pattern[m.end():]


def _variants(token):
    yield token
    if "." in token:
        parts = token.split(".")
        for i in range(1, len(parts)):
            yield ".".join(parts[:i])
        yield from parts


def _text_files(folder):
    for dp, dn, fn in os.walk(folder):
        dn[:] = sorted(d for d in dn if d not in SKIP_DIRS)
        for name in sorted(fn):
            path = Path(dp) / name
            try:
                if path.stat().st_size > MAX_SWEEP_FILE or not path.is_file():
                    continue
                data = path.read_bytes()
            except OSError:
                continue
            if b"\0" not in data[:2048]:
                yield data


def recover(tables, scenes, collector, prefix="HavePlayedEvent.", names_files=(), sweep_dirs=(), source_comments=None):
    """The Book of names. `tables`: fd_classify.GameTables; `scenes`: fd_scenes.Scenes; `collector`: the Collector the scene pass fed."""
    targets = {e.hash for e in tables.bools} | {e.hash for e in tables.ints} | set(tables.structs)
    for members in tables.structs.values():
        targets.update(m for m, _ in members)
    targets.update(o.hash for o in tables.others if o.kind != "Bool64bitKey" and o.hash >> 32 == 0)   # (the other containers' flags: 64-bit keys have no name to find)
    book = Book(targets)
    book.actors = dict(collector.actors)
    # The order is the order of trust: the first name that hashes to a flag keeps it.
    for path in names_files:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            fields = line.split("#", 1)[0].split()
            for name in expand(fields[0]) if fields else ():
                if not book.add(name, "names file") and fd_romfs.murmur3(name) not in book.names and "{" not in fields[0]:
                    book.rejected.append(name)
    for rid in scenes.events.values():
        book.add(prefix + rid, "event table")
    for comment in (source_comments or {}).values():
        name = re.sub(r"\s*\(.*\)$", "", comment).strip()
        if re.fullmatch(r"[A-Za-z0-9_.]+", name):
            book.add(name, "source comment")
    for token in collector.tokens:
        for v in _variants(token.decode("latin1")):
            book.add(v, "files")
    for path in sweep_dirs:
        seen = set()
        for data in _text_files(path):
            for token in TOKEN.findall(data):
                if token not in seen:
                    seen.add(token)
                    for v in _variants(token.decode("latin1")):
                        book.add(v, "sweep")
    for value in book.actors:   # decimal 64-bit ids of placed actors: struct members can be named by them
        for text in (str(value), str(value - (1 << 64)) if value >> 63 else None):
            if text:
                book.add(text, "placement")
    grow(book, tables)
    return book


def grow(book, tables):
    """Name the children of named structs: "<struct>.<member>" when the member's name is known and the hash agrees."""
    while True:
        new = 0
        for struct_hash, members in tables.structs.items():
            if struct_hash not in book.names:
                continue
            prefix = book.names[struct_hash][0] + "."
            for member, child in members:
                if member in book.names and child not in book.names and child in book.targets:
                    if fd_romfs.murmur3(prefix + book.names[member][0]) == child:
                        book.names[child] = (prefix + book.names[member][0], "struct")
                        new += 1
        if not new:
            return

