"""Synthetic game for the debug tools: guest memory with a typed flag store, oot flag subscriptions and a live-input
watcher. Every name, number and address is made up; nothing here comes from a real game."""
import asyncio
import importlib.util
import struct
import time
from pathlib import Path

from src.effects.session_memory import murmur3_32

_SPEC = importlib.util.spec_from_file_location("fake_session_bridge_base", Path(__file__).with_name("session_bridge.py"))
_BASE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BASE)
png = _BASE.png

ITEM_A = "Synthetic_Item_A"   # a possession (kind 0)
ITEM_B = "Synthetic_Item_B"   # a quantity (kind 1)
ITEM_C = "Synthetic_Item_C"   # a quantity without any flag
COUNT_FLAG = "Synthetic.Synthetic_Item_B.Stock"
HAVE_FLAG = "Synthetic.Synthetic_Item_A.Have"     # (the game's IsGet: set when an item is got, never cleared when one is taken away)
STOCK_FLAG = "Synthetic.Synthetic_Item_A.Stock"   # the pouch count of the possession: the truth about whether it is held


def synthetic_info(*, layout=True, flags=True):
    """A GameInfo document (schema 1) with made-up names and numbers."""
    info = {"schema": 1,
        "actions": {"time_base": 700, "time_hours": 24, "mark": 11, "return": 12, "item_base": 5000, "item_stride": 512,
                    "item_bias": 64, "item_toggle": 300},
        "items": [{"index": 0, "name": ITEM_A, "label": "Synthetic A", "kind": 0},
                  {"index": 1, "name": ITEM_B, "label": "Synthetic B", "kind": 1},
                  {"index": 2, "name": ITEM_C, "label": "Synthetic C", "kind": 1}],
        "names": {"life": "synthetic.life", "max_life": "synthetic.max_life", "rupees": "synthetic.rupees"}}
    if flags:
        info["item_flags"] = {"count": "Synthetic.{name}.Stock", "have": "Synthetic.{name}.Have"}
    if layout:
        info["layout"] = {"holder": 20480,
            "kinds": {"bool": {"at": 24, "stride": 32, "value": 20}, "int": {"at": 120, "stride": 48, "value": 24},
                      "uint": {"at": 216, "stride": 48, "value": 24}, "float": {"at": 312, "stride": 48, "value": 24}},
            "box": {"count": 12, "entries": 16, "table": 32, "size": 44}}
    return info


def colliding(name, slots, count=1):
    """Made-up flag names whose hash lands in the same table slot as ``name``."""
    want, found, index = murmur3_32(name.encode()) % slots, [], 0
    while len(found) < count:
        index += 1
        candidate = f"synthetic.collide.{index}"
        if murmur3_32(candidate.encode()) % slots == want:
            found.append(candidate)
    return found


class FakeDebugGame(_BASE.FakeBridge):
    TABLE_SLOTS = {"bool": 8, "int": 16, "uint": 8, "float": 8}

    def __init__(self, path, info, *, log=None, live=None, memory="rw"):
        super().__init__(path)
        self.info = info
        self.log, self.live = log, live
        self.memory = memory                      # "off": every memory command is forbidden; "ro"; "rw"
        self.mem = bytearray(65536)
        self.brk = 32768
        self.kinds, self.flags, self.hashes = {}, {}, {}
        self.constant_flags = {"synthetic.text": "hello", "synthetic.enum": "#0000002a", "synthetic.long": "x" * 70}
        self.pos, self.life, self.max_life, self.rupees = [10, 0, -20], 48, 48, 100
        self.nulls = set()                        # status.game fields the game does not give
        self.mark = None
        self.clock = True
        self.recompute = {}                       # flag name -> value the game puts back on every present
        self.ignore_writes = False                # a write is acknowledged but changes nothing
        self.pickup_delay = 0.0                   # seconds before a quantity edit shows (asynchronous pickup)
        self.item_cap = None
        self.noise = []                           # extra log lines written before the game's own line
        self.silent = False                       # the game says nothing in its log
        self.stale_first = False                  # a subscription first delivers an old retained sample
        self.always_stale = False                 # ... and then never a fresh one
        self.stall_wait = False                   # `wait` never answers
        self.hangup_wait = False                  # `wait` closes the connection instead of answering
        self.drop_write = False                   # a memory write lands but its reply never comes
        self.stuck = False                        # a return is acknowledged but Link does not move
        self.destination_rows = None              # replaces the teleport listing
        self.connections = 0
        self.streams = {}
        self.polls = []                           # every poll's `!cheat` numbers, in order
        self.place_supported = True               # the build has the `!place X Y Z` live command (a host command)
        self.pending_place = None
        self.placed = []                          # every `!place` position the game applied
        self.pull_after = None                    # seconds after a place at which the game puts Link back where he was
        self.applied = []
        self.watcher = None
        if info.get("layout"):
            self.build_memory(info["layout"])

    # -- guest memory

    def alloc(self, size):
        address = self.brk
        self.brk += (size + 15) // 16 * 16
        return address

    def build_memory(self, layout):
        holder, pointer, manager = layout["holder"], self.alloc(16), self.alloc(512)
        struct.pack_into("<Q", self.mem, holder, pointer)
        struct.pack_into("<Q", self.mem, pointer, manager)
        box = layout["box"]
        for kind, spec in layout["kinds"].items():
            slots, capacity = self.TABLE_SLOTS[kind], 12
            entries, table = self.alloc(spec["stride"] * capacity), self.alloc(slots * 8)
            base = manager + spec["at"]
            struct.pack_into("<Q", self.mem, base + box["entries"], entries)
            struct.pack_into("<Q", self.mem, base + box["table"], table)
            struct.pack_into("<I", self.mem, base + box["size"], slots)
            self.kinds[kind] = dict(spec, base=base, box=box, entries=entries, table=table, slots=slots, count=0)

    def add_flag(self, kind, name, value):
        box = self.kinds[kind]
        hashed, index = murmur3_32(name.encode()), box["count"]
        box["count"] += 1
        struct.pack_into("<I", self.mem, box["base"] + box["box"]["count"], box["count"])
        slot = hashed % box["slots"]
        while struct.unpack_from("<II", self.mem, box["table"] + slot * 8)[0]:
            slot = (slot + 1) % box["slots"]
        struct.pack_into("<II", self.mem, box["table"] + slot * 8, hashed, index)
        address = box["entries"] + index * box["stride"] + box["value"]
        self.flags[name] = self.hashes[hashed] = (kind, address)
        self.store(kind, address, value)
        return address

    def store(self, kind, address, value):
        self.mem[address:address + {"bool": 1}.get(kind, 4)] = {"bool": lambda v: bytes([int(bool(v))]),
            "int": lambda v: struct.pack("<i", v), "uint": lambda v: struct.pack("<I", v),
            "float": lambda v: struct.pack("<f", v)}[kind](value)

    def load(self, kind, address):
        if kind == "bool":
            return self.mem[address]
        return struct.unpack_from({"int": "<i", "uint": "<I", "float": "<f"}[kind], self.mem, address)[0]

    def flag_value(self, name):
        if name in self.constant_flags:
            return self.constant_flags[name]
        if name.startswith("0x") and len(name) == 10:
            found = self.hashes.get(int(name, 16))
        else:
            found = self.flags.get(name)
        if found is None:
            return None
        value = self.load(*found)
        return round(value, 3) if found[0] == "float" else value

    def populate(self):
        """The flags a typical test needs; collisions and wrap-around come from ``colliding``."""
        self.add_flag("int", "synthetic.life", self.life)
        self.add_flag("int", "synthetic.max_life", self.max_life)
        self.add_flag("int", "synthetic.rupees", self.rupees)
        self.add_flag("int", "synthetic.delta", -3)
        self.add_flag("int", COUNT_FLAG, 5)
        self.add_flag("int", STOCK_FLAG, 0)
        self.add_flag("bool", HAVE_FLAG, 0)
        self.add_flag("bool", "synthetic.flag", 0)
        self.add_flag("uint", "synthetic.counter", 7)
        self.add_flag("float", "synthetic.scale", 1.5)

    # -- bridge surface

    def game_fields(self, game):
        for key, value in (("pos", list(self.pos)), ("life", self.life), ("max_life", self.max_life), ("rupees", self.rupees)):
            if key not in self.nulls:
                game[key] = value

    def tick(self):
        for name, value in self.recompute.items():
            kind, address = self.flags[name]
            self.store(kind, address, value)

    def oot_event(self, sub, names, *, stale=False):
        game = {"map": self.map, "age": self.age, "loading": self.loading, "event": self.event,
                "frame": self.frame, "t": time.monotonic() - (10 if stale or self.always_stale else 0)}
        self.game_fields(game)
        game["flags"] = {name: self.flag_value(name) for name in names}
        return {"event": "oot", "sub": sub, "frame": self.frame, "game": game}

    async def client(self, reader, writer):
        self.connections += 1
        await super().client(reader, writer)

    async def custom(self, writer, cmd, command, response):
        if cmd == "wait":
            self.tick()
            if self.stall_wait:
                await asyncio.sleep(60)
            if self.hangup_wait:
                writer.close()
                await asyncio.sleep(60)
            return False
        if cmd == "teleport" and "to" not in command and self.destination_rows is not None:
            response["destinations"] = self.destination_rows
            return True
        if cmd in {"mem_read", "mem_read_many", "mem_write"}:
            if self.memory == "off" or (cmd == "mem_write" and self.memory != "rw"):
                response.update(ok=False, error="forbidden", message="memory access is not enabled")
                return True
            try:
                if cmd == "mem_read":
                    response["data"] = self.read(command["addr"], command["size"])
                elif cmd == "mem_read_many":
                    response["ranges"] = [{"addr": r["addr"], "size": r["size"], "data": self.read(r["addr"], r["size"])}
                                          for r in command["ranges"]]
                else:
                    data = bytes.fromhex(command["hex"])
                    if command["addr"] + len(data) > len(self.mem):
                        raise IndexError
                    if not self.ignore_writes:
                        self.mem[command["addr"]:command["addr"] + len(data)] = data
                    response["wrote"] = len(data)
                    if self.drop_write:
                        await asyncio.sleep(60)
            except IndexError:
                response.update(ok=False, error="out_of_range", message="outside guest memory")
            return True
        if cmd == "subscribe":
            response["sub"] = command["id"]
            task = asyncio.create_task(self.stream(writer, command["id"], command.get("flags", [])))
            self.streams[(writer, command["id"])] = task
            self.pending.add(task)
            task.add_done_callback(self.pending.discard)
            return True
        if cmd == "unsubscribe":
            task = self.streams.pop((writer, command.get("sub")), None)
            if task:
                task.cancel()
            response["unsubscribed"] = task is not None
            return True
        return False

    def read(self, address, size):
        if address < 0 or size < 1 or address + size > len(self.mem):
            raise IndexError
        return bytes(self.mem[address:address + size]).hex()

    async def stream(self, writer, sub, names):
        try:
            if self.stale_first:
                await self.emit(writer, self.oot_event(sub, names, stale=True))
            while not writer.is_closing():
                await asyncio.sleep(0.01)
                self.frame += 1
                self.tick()
                await self.emit(writer, self.oot_event(sub, names))
        except (OSError, asyncio.CancelledError):
            pass

    # -- the Debug tab, reached through lines appended to the live input file

    async def start(self):
        await super().start()
        if self.live is not None:
            self.watcher = asyncio.create_task(self.watch())
        return self

    async def close(self):
        if self.watcher:
            self.watcher.cancel()
            await asyncio.gather(self.watcher, return_exceptions=True)
        await super().close()

    async def watch(self):
        offset, held = 0, None
        while True:
            await asyncio.sleep(0.03)  # the game polls the live file about every 30 ms
            data = self.live.read_bytes()
            end = data.rfind(b"\n") + 1
            text = data[offset:end].decode().split("\n")
            lines = [line for line in text if line.startswith("!cheat ")]
            places = [line for line in text if line.startswith("!place ")]
            if places and self.place_supported:
                self.pending_place = [float(v) for v in places[-1].split()[1:4]]
            offset = max(offset, end)
            if self.pending_place is not None and not self.event and not self.loading:
                xyz, self.pending_place, old = self.pending_place, None, list(self.pos)
                self.pos = xyz
                self.placed.append(xyz)
                self.say("cheats: returned to " + self.triple(xyz))
                if self.pull_after is not None:
                    asyncio.get_running_loop().call_later(self.pull_after, lambda: setattr(self, "pos", old))
            if lines:
                self.polls.append([int(line.split()[1]) for line in lines])
                held = self.polls[-1][-1]  # only the LAST line of a poll is kept
            if held is not None and not self.event and not self.loading:  # held until Link is being updated
                number, held = held, None
                self.applied.append(number)
                await self.apply(number)

    def say(self, line):
        if self.silent or self.log is None:
            return
        with self.log.open("a") as stream:
            for extra in self.noise:
                stream.write(extra + "\n")
            self.noise = []
            stream.write(line + "\n")

    @staticmethod
    def triple(values):
        return " ".join(f"{v:.1f}" for v in values)

    async def apply(self, number):
        a = self.info["actions"]
        if number == a["mark"]:
            self.mark = list(self.pos)
            self.say("cheats: marked position " + self.triple(self.pos))
        elif number == a["return"]:
            if self.mark is None:
                self.say("cheats: no mark for this player controller")
            else:
                self.pos = list(self.mark) if not self.stuck else self.pos
                self.say("cheats: returned to " + self.triple(self.pos))
        elif a["time_base"] <= number < a["time_base"] + a["time_hours"]:
            hour = number - a["time_base"]
            self.say(f"cheats: requested {hour:02d}:00" if self.clock else "cheats: world clock unavailable")
        elif number >= a["item_base"]:
            index, rest = divmod(number - a["item_base"], a["item_stride"])
            item = next((row for row in self.info["items"] if row["index"] == index), None)
            if item is None:
                return
            templates = self.info.get("item_flags") or {}
            if rest == a["item_toggle"]:
                have_name = (templates.get("have") or "").replace("{name}", item["name"])
                stock_name = (templates.get("count") or "").replace("{name}", item["name"])
                have, stock = self.flags.get(have_name), self.flags.get(stock_name)
                held = self.load(*stock) if stock else self.load(*have) if have else 0
                if stock:
                    self.store(stock[0], stock[1], 0 if held else 1)
                if have and not held:
                    self.store(have[0], have[1], 1)   # (a removal leaves it set)
                self.say(f"cheats: inventory {item['label']} toggled (had {held}, now {held}, event status 0)")
            else:
                delta = rest - a["item_bias"]
                flag = (templates.get("count") or "").replace("{name}", item["name"])
                kind_address = self.flags.get(flag)
                had = self.load(*kind_address) if kind_address else 0
                target = had + delta
                if self.item_cap is not None:
                    target = min(target, self.item_cap)
                if kind_address and self.pickup_delay:
                    self.say(f"cheats: inventory {item['label']} {delta:+d} (had {had}, now {had}, event status 1)")
                    asyncio.get_running_loop().call_later(self.pickup_delay, self.store, kind_address[0], kind_address[1], target)
                else:
                    if kind_address:
                        self.store(kind_address[0], kind_address[1], target)
                    self.say(f"cheats: inventory {item['label']} {delta:+d} (had {had}, now {target if kind_address else had}, event status 0)")
