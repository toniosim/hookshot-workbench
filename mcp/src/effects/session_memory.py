"""Typed access to the game's flag containers through the bridge's guest-memory commands.

Only what a typed flag write needs: a 32-bit name hash, a lookup of the flag's value slot through the operator's
registered layout (``GameInfo.layout``), and fixed-width value codecs. Addresses never leave this module's callers:
results carry the flag's name and hash, never a guest address. Memory commands exist only when the game was started
with the memory opt-in; otherwise the bridge answers ``forbidden``, which the transport maps to ``refused_by_policy``.
"""
import math
import re
import struct
from collections.abc import Iterable
from src.effects.session_bridge import Bridge
from src.errors import fail
from src.models.session_debug import GameLayout, KindLayout

PROBE_ORDER = ("bool", "int", "float", "uint")
WIDTH = {"bool": 1, "int": 4, "uint": 4, "float": 4}
MAX_TABLE_SLOTS = 4194304  # a larger container is not trusted
MAX_PROBES = 4096          # slots examined per container before the lookup gives up
CHUNK_SLOTS = 64           # 8-byte (key, index) pairs per read
MAX_READ = 65536
HASH_NAME = re.compile(r"^0x[0-9a-fA-F]{8}$")
MASK = 0xFFFFFFFF


def murmur3_32(data: bytes, seed: int = 0) -> int:
    """MurmurHash3, x86 32-bit variant."""
    c1, c2 = 0xCC9E2D51, 0x1B873593
    rotl = lambda value, bits: ((value << bits) | (value >> (32 - bits))) & MASK
    h = seed & MASK
    body = len(data) - len(data) % 4
    for at in range(0, body, 4):
        k = (int.from_bytes(data[at:at + 4], "little") * c1) & MASK
        k = (rotl(k, 15) * c2) & MASK
        h = (rotl(h ^ k, 13) * 5 + 0xE6546B64) & MASK
    tail = int.from_bytes(data[body:], "little")
    if len(data) % 4:
        tail = (rotl((tail * c1) & MASK, 15) * c2) & MASK
        h ^= tail
    h ^= len(data)
    h ^= h >> 16
    h = (h * 0x85EBCA6B) & MASK
    h ^= h >> 13
    h = (h * 0xC2B2AE35) & MASK
    return h ^ (h >> 16)


def flag_hash(name: str) -> int:
    """A literal ``0x`` + 8 hex digits is the hash itself; any other name is hashed as UTF-8."""
    return int(name, 16) if HASH_NAME.fullmatch(name) else murmur3_32(name.encode())


def encode(kind: str, value) -> bytes:
    """Little-endian bytes of a value in that kind's width; ValueError when it is not representable."""
    if kind == "bool":
        if isinstance(value, bool) or (isinstance(value, int) and value in (0, 1)):
            return b"\x01" if value else b"\x00"
        raise ValueError("not a boolean")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("not a finite number")
    try:
        if kind == "float":
            return struct.pack("<f", float(value))
        if isinstance(value, float):
            if not value.is_integer():
                raise ValueError("not a whole number")
            value = int(value)
        return struct.pack("<i" if kind == "int" else "<I", value)
    except (OverflowError, struct.error):
        raise ValueError("out of range") from None


def decode(kind: str, raw: bytes):
    if kind == "bool":
        return bool(raw[0]) if raw[0] in (0, 1) else raw[0]
    return struct.unpack({"int": "<i", "uint": "<I", "float": "<f"}[kind], raw)[0]


class FlagMemory:
    """Reads and writes on one session's bridge connection; every failure is a typed workbench error."""

    def __init__(self, bridge: Bridge, layout: GameLayout, operation: str, timeout: float = 5):
        self.bridge, self.layout, self.operation, self.timeout = bridge, layout, operation, timeout

    def _range(self, addr: int, size: int):
        if not 0 <= addr < 2**64 or not 1 <= size <= MAX_READ:
            raise fail("backend_failed", self.operation)

    def _bytes(self, value, size: int) -> bytes:
        try:
            raw = bytes.fromhex(value) if isinstance(value, str) else None
        except ValueError:
            raw = None
        if raw is None or len(raw) != size:
            raise fail("backend_failed", self.operation)
        return raw

    async def read(self, addr: int, size: int) -> bytes:
        self._range(addr, size)
        reply = await self.bridge.request("mem_read", timeout=self.timeout, addr=addr, size=size, format="hex")
        return self._bytes(reply.get("data"), size)

    async def read_many(self, ranges: list[tuple[int, int]]) -> list[bytes]:
        for addr, size in ranges:
            self._range(addr, size)
        reply = await self.bridge.request("mem_read_many", timeout=self.timeout,
            ranges=[{"addr": addr, "size": size} for addr, size in ranges])
        rows = reply.get("ranges")
        if not isinstance(rows, list) or len(rows) != len(ranges) or any(not isinstance(row, dict) for row in rows):
            raise fail("backend_failed", self.operation)
        return [self._bytes(row.get("data"), size) for row, (_, size) in zip(rows, ranges)]

    async def write(self, addr: int, data: bytes) -> None:
        self._range(addr, len(data))
        reply = await self.bridge.request("mem_write", timeout=self.timeout, addr=addr, hex=data.hex())
        if reply.get("wrote") != len(data):
            raise fail("uncertain_outcome", self.operation)

    async def locate(self, hashed: int, kinds: Iterable[str]) -> tuple[str, int] | None:
        """(kind, value address) of the flag in the first listed container that holds it, else None.

        ``mgr = u64(u64(holder))``; each kind's container sits at ``mgr + at``. Its hash table is probed linearly
        from ``hash % size`` with wrap: key 0 ends the probe (absent), a matching key whose index is inside the
        entry array is the flag. Probing is bounded, and an unusable container is simply not a match.
        """
        layout = self.layout
        pointer = int.from_bytes(await self.read(layout.holder, 8), "little")
        manager = int.from_bytes(await self.read(pointer, 8), "little") if pointer else 0
        if not pointer or not manager:
            raise fail("unavailable", self.operation, retryable=True)  # the game has not built its flag store yet
        box = layout.box
        for kind in kinds:
            spec = layout.kinds.get(kind)
            if spec is None:
                continue
            base = manager + spec.at
            count, entries, table, size = await self.read_many(
                [(base + box.count, 4), (base + box.entries, 8), (base + box.table, 8), (base + box.size, 4)])
            count, entries, table, size = (int.from_bytes(part, "little") for part in (count, entries, table, size))
            if not 0 < size <= MAX_TABLE_SLOTS or not table or not entries:
                continue
            address = await self._probe(hashed, spec, count, entries, table, size)
            if address is not None:
                return kind, address
        return None

    async def _probe(self, hashed: int, spec: KindLayout, count: int, entries: int, table: int, size: int) -> int | None:
        slot, probed, limit = hashed % size, 0, min(size, MAX_PROBES)
        while probed < limit:
            run = min(CHUNK_SLOTS, size - slot, limit - probed)
            chunk = await self.read(table + slot * 8, run * 8)
            for at in range(0, run * 8, 8):
                key, index = struct.unpack_from("<II", chunk, at)
                if key == 0:
                    return None
                if key == hashed and index < count:
                    return entries + index * spec.stride + spec.value
            probed += run
            slot = (slot + run) % size
        if limit < size:
            raise fail("backend_failed", self.operation)  # a bounded probe cannot prove absence
        return None
