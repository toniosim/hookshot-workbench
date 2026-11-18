"""A made-up game for the flagdata tests: a RomFS folder, a GameDataList, an EventSetting table, placements and a source file.

Nothing here is the game's: the names are invented, the hashes are computed from them, and every file is written into a temporary
folder when a test asks for it (no data file is kept in the repository). The BYML and SARC writers exist only for the tests.
"""
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLAGDATA = ROOT / "flagdata"


def h(name):
    import fd_romfs
    return fd_romfs.murmur3(name)


# ---- writers (tests only)

def byml_dump(root, little=True):
    e = "<" if little else ">"
    keys, strings = set(), set()

    def collect(o):
        if isinstance(o, dict):
            for k, v in o.items():
                keys.add(k)
                collect(v)
        elif isinstance(o, list):
            for v in o:
                collect(v)
        elif isinstance(o, str):
            strings.add(o)

    collect(root)
    keys, strings = sorted(keys), sorted(strings)
    out = bytearray(16)

    def align(n=4):
        while len(out) % n:
            out.append(0)

    def head(kind, count):
        return bytes([kind]) + (count.to_bytes(3, "little" if little else "big"))

    def table(items):
        align()
        at = len(out)
        body = [s.encode() + b"\0" for s in items]
        first = 4 + 4 * (len(items) + 1)
        offsets, pos = [], first
        for b in body:
            offsets.append(pos)
            pos += len(b)
        offsets.append(pos)
        out.extend(head(0xC2, len(items)) + struct.pack(e + "%dI" % len(offsets), *offsets) + b"".join(body))
        return at

    kt = table(keys)
    st = table(strings)

    def value(v):
        """(type, word) of a value, writing what it needs first."""
        if v is None:
            return 0xFF, 0
        if isinstance(v, bool):
            return 0xD0, int(v)
        if isinstance(v, str):
            return 0xA0, strings.index(v)
        if isinstance(v, float):
            return 0xD2, struct.unpack(e + "I", struct.pack(e + "f", v))[0]
        if isinstance(v, int):
            if 0 <= v < 1 << 32:
                return 0xD3, v
            if -(1 << 31) <= v < 0:
                return 0xD1, struct.unpack(e + "I", struct.pack(e + "i", v))[0]
            align(8)
            at = len(out)
            out.extend(struct.pack(e + ("Q" if v >= 0 else "q"), v))
            return (0xD5 if v >= 0 else 0xD4), at
        if isinstance(v, bytes):
            align()
            at = len(out)
            out.extend(struct.pack(e + "I", len(v)) + v)
            return 0xA1, at
        return (0xC1 if isinstance(v, dict) else 0xC0), node(v)

    def node(o):
        if isinstance(o, dict):
            items = [(keys.index(k), value(v)) for k, v in o.items()]
            items.sort()
            align()
            at = len(out)
            out.extend(head(0xC1, len(items)))
            for idx, (kind, word) in items:
                out.extend(idx.to_bytes(3, "little" if little else "big") + bytes([kind]) + struct.pack(e + "I", word))
            return at
        vals = [value(v) for v in o]
        align()
        at = len(out)
        out.extend(head(0xC0, len(vals)) + bytes(kind for kind, _ in vals))
        align()
        out.extend(struct.pack(e + "%dI" % len(vals), *[w for _, w in vals]))
        return at

    r = node(root)
    out[0:16] = (b"YB" if little else b"BY") + struct.pack(e + "HIII", 7, kt, st, r)
    return bytes(out)


def sarc_dump(files, little=True):
    e = "<" if little else ">"
    names = b""
    nodes = []
    for name, data in sorted(files.items()):
        nodes.append((len(names) // 4, name, data))
        names += name.encode() + b"\0"
        names += b"\0" * (-len(names) % 4)
    sfat = b"SFAT" + struct.pack(e + "HHI", 12, len(nodes), 0x65)
    data_off, blobs = 0, b""
    for i, (off, name, data) in enumerate(nodes):
        sfat += struct.pack(e + "4I", h(name) & 0, 0x01000000 | off, data_off, data_off + len(data))
        blobs += data + b"\0" * (-len(data) % 4)
        data_off += len(data) + (-len(data) % 4)
    sfnt = b"SFNT" + struct.pack(e + "HH", 8, 0) + names
    start = 0x14 + len(sfat) + len(sfnt)
    start += -start % 4
    total = start + len(blobs)
    return (b"SARC" + struct.pack(e + "H", 0x14) + (b"\xff\xfe" if little else b"\xfe\xff") + struct.pack(e + "II", total, start)
            + struct.pack(e + "I", 0x100) + sfat + sfnt + b"\0" * (start - 0x14 - len(sfat) - len(sfnt)) + blobs)


# ---- the made-up game

BOOLS = {   # name: (default, reset, file)
    "Markers.Sword": (0, 8, 0), "Markers.Song1": (0, 8, 0), "Markers.Song2": (0, 8, 0),
    "Story_Alpha": (0, 8, 0), "Story_StartsTrue": (1, 8, 0),
    "HavePlayedEvent.Intro": (0, 8, 0), "HavePlayedEvent.Gate_Alpha": (0, 8, 0), "HavePlayedEvent.CodeRead": (0, 8, 0),
    "HavePlayedEvent.BossDeath": (0, 8, 0), "HavePlayedEvent.BossIn": (0, 8, 0),
    "Dungeons.AlphaCave.HasMap": (0, 8, 0),
    "Temp_Flag": (0, 1, 0), "Unsaved_Flag": (0, 8, -1), "Option_Flag": (0, 8, 1), "NoReset_Flag": (0, 0, 0),
    "Heart_Flag": (0, 8, 0), "Standing_Flag": (0, 8, 0), "Fight_Flag": (0, 8, 0),
    "ZoneA_RoomA_Cleared": (0, 8, 0),
}
INTS = {
    "Player.Rupees": 0, "Player.MagicSize": 0, "Dungeons.AlphaCave.Keys": 0, "Stock.Bomb.Count": 0, "Stock.Medal.Count": 0,
    "Stock.Cloak.Count": 0, "Stock.Boots.Count": 0, "Caps.Wallet": 0, "Misc_Counter": 5,
}
EVENT_ROWS = ["Intro", "Gate_Alpha", "CodeRead", "BossDeath", "BossIn", "Unlisted_Row"]
ACTOR_ID = 12786193094758345086   # a 64-bit placement hash (as a decimal it names a struct member)
STRUCTS = {   # struct name -> [member name -> child name]
    "Markers": ["Sword", "Song1", "Song2"],
    "Stock": ["Bomb", "Medal", "Cloak", "Boots"],
    "Dungeons": ["AlphaCave"],
    "Caps": ["Wallet"],
    "ChestOpen": [str(ACTOR_ID)],
}
BOOLS["ChestOpen.%d" % ACTOR_ID] = (0, 8, 0)


def game_data():
    entries = {"Bool": [], "Int": [], "Struct": [],
               "Enum": [dict(Hash=h("Mode"), DefaultValue=h("B"), RawValues=["A", "B"], ResetTypeValue=8, SaveFileIndex=0)],
               "Bool64bitKey": [dict(Hash=77, ResetTypeValue=24, SaveFileIndex=0), dict(Hash=(1 << 63) + 5, ResetTypeValue=24, SaveFileIndex=0)],
               "Float": [dict(Hash=h("Misc_Ratio"), DefaultValue=0.5, ResetTypeValue=0, SaveFileIndex=2)],
               "IntArray": [dict(Hash=h("Misc_Counts"), DefaultValue=-1, OriginalSize=2, TotalSize=4, ResetTypeValue=8, SaveFileIndex=0)]}
    for name, (default, reset, file) in BOOLS.items():
        entries["Bool"].append(dict(Hash=h(name), DefaultValue=bool(default), ResetTypeValue=reset, SaveFileIndex=file))
    for name, default in INTS.items():
        entries["Int"].append(dict(Hash=h(name), DefaultValue=default, ResetTypeValue=8, SaveFileIndex=0))

    def struct(name, members):
        entries["Struct"].append(dict(Hash=h(name), DefaultValue=[dict(Hash=h(m), Value=h(v)) for m, v in members]))

    for top, kids in STRUCTS.items():
        struct(top, [(k, top + "." + k) for k in kids])
    for stock in ("Bomb", "Medal", "Cloak", "Boots"):
        struct("Stock." + stock, [("Count", "Stock.%s.Count" % stock)])
    struct("Dungeons.AlphaCave", [("Keys", "Dungeons.AlphaCave.Keys"), ("HasMap", "Dungeons.AlphaCave.HasMap")])
    return {"Data": entries, "MetaData": {}}


def source_text(song=None, own=None, extra_rule=True):
    """A host/oot_coop.c shaped like the real one for what the tool reads."""
    def hx(names):
        return ", ".join("0x%08x" % h(n) for n in names)

    classify = ("static Class classify(int is_int, uint32_t h, uint32_t reset, int32_t file, int default_true, const Sets *s) {\n"
                "    if (file != 0 || reset & RESET_TEMPORARY || !(reset & RESET_NEW_GAME) || COOP_FLAG_IN(heart_reward_flags, h) ||\n"
                "        COOP_FLAG_IN(unshared_flags, h) || boss_own(h)) return k;\n"
                "    k.cat = COOP_FLAG_IN(song_flags, h) ? 1 : hset_has(&s->first_get, h) ? 2 : 0;\n"
                "    k.scene = coop_scenes_has(s->scenes, h) && !COOP_FLAG_IN(code_read_scenes, h) && boss_proof_of(h, &proof_bit) < 0;\n"
                "    if (h == F_RUPEES) {} else if (hset_has(&s->keys, h)) {} else if (hset_has(&s->pouch, h)) {\n"
                "        if (COOP_FLAG_IN(own_counts, h)) return k; k.cat = COOP_FLAG_IN(quest_counts, h);\n"
                "        for (i = 0; i < n; i++) if (ammo[i].count == h) k.cat = 6;\n"
                "    } else if (hset_has(&s->capacity, h) || h == F_MAGIC_SIZE) {}\n}\n")
    if not extra_rule:
        classify = classify.replace("boss_proof_of(h, &proof_bit) < 0", "1")
    return """/* made-up source for the tests */
#define S_POUCH 0x%08xu      /* item counts */
#define M_STOCK 0x%08xu
#define S_FIRST_GET 0x%08xu
#define S_DUNGEON 0x%08xu
#define M_SMALL_KEYS 0x%08xu
#define M_GET_MAP 0x%08xu
#define M_GET_COMPASS 0x%08xu
#define M_GET_BOSS_KEY 0x%08xu
#define S_CAPACITY 0x%08xu
#define F_RUPEES 0x%08xu
#define F_MAGIC_SIZE 0x%08xu
enum { RESET_NEW_GAME = 8 | 16 | 32, RESET_TEMPORARY = 1 | 2 | 4 | 256, INT_MAX_ITEM = 999, KEY_MAX = 15 };
static const uint32_t song_flags[] = {%s};
static const uint32_t heart_reward_flags[] = {%s};
/* where one player stands */
static const uint32_t unshared_flags[] = {
    0x%08x,   /* Standing_Flag */
    0x00000001,   /* a flag that is in no list of the game */
};
static const BossSet boss_sets[BOSS_N] = {
    {"Gohma", "AlphaCave", 0x%08x, 0x%08x, 3,
     {0x%08x, 0x%08x},
     {{0x%08x, 1},   /* HavePlayedEvent.BossDeath */
      {0x00000000, 0}},
     {{0x%08x, 1}},   /* HavePlayedEvent.BossIn */
     {0x%08x}},   /* Fight_Flag */
};
static const uint32_t code_read_scenes[] = {%s};
static const uint32_t quest_counts[] = {%s};
static const uint32_t own_counts[] = {%s};
static const struct { uint32_t count, cap_member; } ammo[] = {
    {0x%08x, 0x%08x},
};
%s
""" % (h("Stock"), h("Count"), h("Markers"), h("Dungeons"), h("Keys"), h("HasMap"), h("HasCompass"), h("HasBossKey"), h("Caps"),
       h("Player.Rupees"), h("Player.MagicSize"), hx(song or ["Markers.Song1", "Markers.Song2"]), hx(["Heart_Flag"]), h("Standing_Flag"),
       h("Quest"), h("Step"), h("A"), h("B"), h("HavePlayedEvent.BossDeath"), h("HavePlayedEvent.BossIn"), h("Fight_Flag"),
       hx(["HavePlayedEvent.CodeRead"]), hx(["Stock.Medal.Count"]), hx(own or ["Stock.Cloak.Count"]), h("Stock.Bomb.Count"), h("Cap"), classify)


SCENES_SOURCE = """#define PLAYED_PREFIX "HavePlayedEvent."
static const char *const scan_roots[] = { "Event", "Banc", "GameData", "RSDB" };
#define TABLE_FOLDER "RSDB"
#define TABLE_START "EventSetting.Product."
#define TABLE_END ".rstbl.byml.zs"
"""


# identifiers the made-up flow files spell out (the rest of the flags stay unnamed until a test names them)
FLOW_NAMES = ["Markers", "Stock", "Dungeons", "Caps", "ChestOpen", "Sword", "Song1", "Song2", "Bomb", "Medal", "Cloak", "Boots", "AlphaCave",
              "Wallet", "Count", "Keys", "HasMap", "Story_Alpha", "Story_StartsTrue", "Player.Rupees", "Player.MagicSize", "Misc_Counter",
              "Temp_Flag", "Unsaved_Flag", "Option_Flag", "NoReset_Flag", "Heart_Flag", "Standing_Flag", "Fight_Flag", "Misc_Ratio"]


def romfs_files(little=True):
    """{relative path: bytes} of the made-up RomFS (raw BYML under the game's .zs names: the reader goes by the frame, not the name)."""
    actors = [dict(Hash=ACTOR_ID, Gyaml="Chest_Small", Name="Chest_One"), dict(Hash=77, Gyaml="Other", Name="Other_One")]
    return {
        "GameData/GameDataList.Product.100.byml.zs": byml_dump(game_data(), little),
        "RSDB/EventSetting.Product.100.rstbl.byml.zs": byml_dump([dict(__RowId=r) for r in EVENT_ROWS] + [dict(__RowId="bad name!")], little),
        "Event/Flow.txt": ("flow names a played flag: HavePlayedEvent.Gate_Alpha and a long identifier ZoneA_RoomA_Cleared_Extra\n" +
                           " ".join(FLOW_NAMES) + "\n").encode(),
        "Banc/Zone/ZoneA_Static.bcett.byml.zs": byml_dump(dict(Actors=actors), little),
        "Pack/readme.txt": b"nothing here\n",
    }


def write_romfs(root, little=True, drop=()):
    root = Path(root)
    for rel, data in romfs_files(little).items():
        if rel in drop:
            continue
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return root


def write_source(folder, **kw):
    folder = Path(folder)
    (folder / "oot_coop.c").write_text(source_text(**kw), encoding="utf-8")
    (folder / "coop_scenes.c").write_text(SCENES_SOURCE, encoding="utf-8")
    return folder / "oot_coop.c"
