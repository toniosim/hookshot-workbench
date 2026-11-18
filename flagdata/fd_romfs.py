"""Read a player's own game files: the hash the game names its flags by, zstd with the game's dictionaries, SARC and BYML.

Everything here is a reader for formats; no name, hash or table of the game is in it. Standard library only (zstd comes from
Python 3.14's `compression.zstd`, the `zstandard` package or the `zstd` program, whichever is there).
"""
import os
import re
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"
DICT_MAGIC = b"\x37\xa4\x30\xec"


def murmur3(text, seed=0):
    """MurmurHash3 x86 32-bit: the hash the game names its flags, structs and members by (seed 0, UTF-8 text)."""
    data = text.encode() if isinstance(text, str) else bytes(text)
    c1, c2, h = 0xCC9E2D51, 0x1B873593, seed & 0xFFFFFFFF
    n = len(data) // 4
    for k in struct.unpack_from("<%dI" % n, data):
        k = (k * c1) & 0xFFFFFFFF
        k = ((k << 15) | (k >> 17)) & 0xFFFFFFFF
        k = (k * c2) & 0xFFFFFFFF
        h ^= k
        h = ((h << 13) | (h >> 19)) & 0xFFFFFFFF
        h = (h * 5 + 0xE6546B64) & 0xFFFFFFFF
    tail, k = data[n * 4:], 0
    if tail:
        for i in range(len(tail) - 1, -1, -1):
            k = (k << 8) | tail[i]
        k = (k * c1) & 0xFFFFFFFF
        k = ((k << 15) | (k >> 17)) & 0xFFFFFFFF
        k = (k * c2) & 0xFFFFFFFF
        h ^= k
    h ^= len(data)
    h ^= h >> 16
    h = (h * 0x85EBCA6B) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 0xC2B2AE35) & 0xFFFFFFFF
    return h ^ (h >> 16)


# ---- zstd

def frame_dict_id(data):
    """The dictionary id a zstd frame asks for (0: none)."""
    if data[:4] != ZSTD_MAGIC:
        raise ValueError("not a zstd frame")
    descriptor = data[4]
    size = (0, 1, 2, 4)[descriptor & 3]
    at = 5 + (0 if descriptor & 0x20 else 1)   # (a single-segment frame has no window descriptor)
    return int.from_bytes(data[at:at + size], "little") if size else 0


def dict_id(blob):
    return int.from_bytes(blob[4:8], "little") if blob[:4] == DICT_MAGIC else 0


def zstd_backend():
    """'compression.zstd', 'zstandard', 'zstd' (the program) or None."""
    try:
        from compression import zstd  # noqa: F401  (Python 3.14)
        return "compression.zstd"
    except ImportError:
        pass
    try:
        import zstandard  # noqa: F401
        return "zstandard"
    except ImportError:
        pass
    return "zstd" if shutil.which("zstd") else None


def zstd_decompress(data, dictionary=None):
    backend = zstd_backend()
    if backend == "compression.zstd":
        from compression import zstd
        return zstd.decompress(data, zstd_dict=zstd.ZstdDict(dictionary) if dictionary else None)
    if backend == "zstandard":
        import zstandard
        d = zstandard.ZstdCompressionDict(dictionary) if dictionary else None
        return zstandard.ZstdDecompressor(dict_data=d).decompressobj().decompress(data)
    if backend == "zstd":
        with tempfile.TemporaryDirectory(prefix="flagdata-") as tmp:
            cmd = ["zstd", "-d", "-c", "-q"]
            if dictionary:
                path = Path(tmp) / "dict"
                path.write_bytes(dictionary)
                cmd += ["-D", str(path)]
            done = subprocess.run(cmd, input=data, capture_output=True)
            if done.returncode:
                raise ValueError("zstd failed: " + done.stderr.decode(errors="replace").strip())
            return done.stdout
    raise RuntimeError("no zstd: use Python 3.14, `pip install zstandard` in a venv, or install the zstd program")


# ---- SARC

def sarc(data):
    """{file name: bytes} of a SARC archive (either byte order)."""
    if data[:4] != b"SARC":
        raise ValueError("not a SARC")
    e = "<" if data[6:8] == b"\xff\xfe" else ">"
    header, _, start = struct.unpack_from(e + "HxxII", data, 4)
    count = struct.unpack_from(e + "H", data, header + 6)[0]
    names, out = header + 12 + count * 16 + 8, {}
    for i in range(count):
        _, attr, lo, hi = struct.unpack_from(e + "4I", data, header + 12 + i * 16)
        o = names + (attr & 0xFFFFFF) * 4
        out[data[o:data.index(0, o)].decode()] = data[start + lo:start + hi]
    return out


# ---- BYML

def byml(data):
    """The value of a BYML file (either byte order; also the engine's hash-keyed dictionaries, nodes 0x20 and 0x21).
    Dictionaries are dicts, arrays lists; 64-bit integers are plain ints, binary data is bytes."""
    e = "<" if data[:2] == b"YB" else ">" if data[:2] == b"BY" else None
    if e is None:
        raise ValueError("not a BYML")
    _, key_table, string_table, root = struct.unpack_from(e + "HIII", data, 2)

    def u32(at):
        return struct.unpack_from(e + "I", data, at)[0]

    def count(at):
        return u32(at) >> 8 if e == "<" else u32(at) & 0xFFFFFF

    def table(at):
        if not at:
            return []
        n = count(at)
        offsets = struct.unpack_from(e + "%dI" % (n + 1), data, at + 4)
        return [data[at + o:data.index(0, at + o)].decode("utf-8", "replace") for o in offsets[:n]]

    keys, strings = table(key_table), table(string_table)

    def value(kind, word, at):
        if kind == 0xA0:
            return strings[word]
        if kind in (0xA1, 0xA2):
            return data[word + 4:word + 4 + u32(word)]
        if kind in (0x20, 0x21, 0xC0, 0xC1):
            return node(word)
        if kind == 0xD0:
            return bool(word)
        if kind == 0xD1:
            return struct.unpack(e + "i", struct.pack(e + "I", word))[0]
        if kind == 0xD2:
            return struct.unpack(e + "f", struct.pack(e + "I", word))[0]
        if kind == 0xD3:
            return word
        if kind == 0xD4:
            return struct.unpack_from(e + "q", data, word)[0]
        if kind == 0xD5:
            return struct.unpack_from(e + "Q", data, word)[0]
        if kind == 0xD6:
            return struct.unpack_from(e + "d", data, word)[0]
        if kind == 0xFF:
            return None
        raise ValueError("BYML value type %#x at %#x" % (kind, at))

    def node(at):
        kind, n = data[at], count(at)
        if kind in (0x20, 0x21):
            width = 8 if kind == 0x20 else 12
            fmt = e + ("II" if kind == 0x20 else "QI")
            types = at + 4 + width * n
            return {k: value(data[types + i], v, at) for i, (k, v) in
                    enumerate(struct.unpack_from(fmt, data, at + 4 + width * i) for i in range(n))}
        if kind == 0xC0:
            types, values = at + 4, at + 4 + ((n + 3) & ~3)
            return [value(data[types + i], u32(values + 4 * i), at) for i in range(n)]
        if kind == 0xC1:
            out = {}
            for i in range(n):
                p = at + 4 + 8 * i
                out[keys[(u32(p) & 0xFFFFFF) if e == "<" else (u32(p) >> 8)]] = value(data[p + 3], u32(p + 4), at)
            return out
        raise ValueError("BYML node type %#x at %#x" % (kind, at))

    return node(root)


# ---- the RomFS folder

class Romfs:
    """A player's RomFS folder (the one the game's own files were put in). `read` returns a file's bytes, decoded when it is a
    zstd file: the frame's own header says so, so the file's name does not matter."""

    DICT_PACK = "Pack/ZsDic.pack.zs"

    def __init__(self, root):
        self.root = Path(root)
        if not self.root.is_dir():
            raise ValueError("no such RomFS folder: %s" % root)
        self._dicts = None

    def raw(self, rel):
        return (self.root / rel).read_bytes()

    def dicts(self):
        if self._dicts is None:
            self._dicts = {}
            path = self.root / self.DICT_PACK
            if path.is_file():
                for blob in sarc(zstd_decompress(path.read_bytes())).values():
                    self._dicts[dict_id(blob)] = blob
        return self._dicts

    def read(self, rel):
        data = self.raw(rel)
        if data[:4] != ZSTD_MAGIC:
            return data
        wanted = frame_dict_id(data)
        if wanted and wanted not in self.dicts():
            raise ValueError("%s needs zstd dictionary %d, which %s does not hold" % (rel, wanted, self.DICT_PACK))
        return zstd_decompress(data, self.dicts().get(wanted) if wanted else None)

    def is_dir(self, rel):
        return (self.root / rel).is_dir()

    def walk(self, rel, max_depth=12):
        """(path relative to the RomFS, size) of every file under `rel`, sorted by path; raises when the tree is deeper than
        max_depth. A missing folder gives nothing (the caller decides whether that is an error)."""
        out = []

        def visit(folder, depth):
            base = self.root / folder
            if not base.is_dir():
                return
            for entry in sorted(os.scandir(base), key=lambda x: x.name):
                path = folder + "/" + entry.name if folder else entry.name
                if entry.is_dir():
                    if depth >= max_depth:
                        raise ValueError("folder tree deeper than %d: %s" % (max_depth, path))
                    visit(path, depth + 1)
                else:
                    out.append((path, entry.stat().st_size))

        visit(rel, 0)
        return sorted(out)

    def glob_one(self, folder, pattern):
        """The one file of `folder` that matches the regular expression (its version number is part of its name)."""
        names = [p.name for p in (self.root / folder).iterdir() if re.fullmatch(pattern, p.name)] if self.is_dir(folder) else []
        if len(names) != 1:
            raise ValueError("expected one file like %r in %s, found %d" % (pattern, folder, len(names)))
        return folder + "/" + names[0]
