#!/usr/bin/env python3
"""Look up, check and rebuild the flag map (the pages in flags/ beside this script): one row for every flag of the game's
list (the GameDataList) that `flagdata/flagdata.py build` can enumerate, with its hash, the name recovered by hashing,
where the name came from, its kind, default, reset kind, the save file and the group it sits in, what co-op does with it,
and what we know of it.

    flagmap.py find 4d77f1cb          the row of one flag by its hash (8 hexadecimal digits; a per-object key has 16)
    flagmap.py find PlayerStatus.Life a flag by its name (the game's, as recovered), else the rows whose name has the text
    flagmap.py find "boss appear"     rows that have all the words (in the name, family, map, note or description; first 20)
    flagmap.py show 4d77f1cb          every field of a row, and where to find the flag in a save file
    flagmap.py stats                  the numbers: rows by kind, co-op fate, name, description and sureness; pages
    flagmap.py check                  the pages against themselves, and every recovered name against its hash
    flagmap.py names                  the recovered names, one a line: `flagdata.py build --names FILE` takes them for a new game version
    flagmap.py build --from DIR       rewrite the pages from the folder `flagdata.py build` wrote (flags.csv, excluded.csv,
                                      others.csv), joined with flags/descriptions.md; see flags/README.md, "Making the pages"

Standard library only. `check` and `build` hash with flagdata/fd_romfs.py (the game's MurmurHash3, seed 0).
"""
import argparse
import csv
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FLAGS = HERE / "flags"
INDEX = FLAGS / "README.md"
NOTES = FLAGS / "descriptions.md"
KEPT = ROOT / "docs" / "names-kept.md"

COLUMNS = ("Hash", "Name", "Named by", "Kind", "Default", "Reset", "File", "Group", "Co-op", "Map", "Note", "What it is", "Sure", "Source")
HEADER = "| " + " | ".join(COLUMNS) + " |"
RULE = "|" + "|".join("---" for _ in COLUMNS) + "|"
NOTES_HEADER = "| Hash | What it is | Sure | Source |"
SURE = ("tested", "read", "guess")
PAGE_LIMIT = 180_000   # bytes: the publication check refuses a file over 200 KB
KEPT_REASON = ("Flag name read by hashing from the player's own game files, quoted as an identifier the game itself uses "
               "in the flag map; not workbench branding.")

# SaveFileIndex of the GameDataList -> the file it names (the slot's files are slot_NN/progress.sav and slot_NN/caption.sav).
FILES = {0: "progress", 1: "option", 2: "caption", 3: "account", -1: "none"}
FILE_PATHS = {"progress": "slot_NN/progress.sav", "option": "option.sav", "caption": "slot_NN/caption.sav", "account": "account.sav"}
FILE_INDEX = {v: k for k, v in FILES.items()}
# The group of a type in a save file's table (docs/oot/save-format.md). Bool64bitKey flags are not in the table: they are the key
# run of progress.sav; a Struct holds no value of its own; BoolExp and the two unsaved string kinds are never saved.
GROUPS = {"Bool": 1, "BoolArray": 2, "Int": 3, "IntArray": 4, "Float": 5, "FloatArray": 6, "Enum": 7, "EnumArray": 8, "Vector3": 11,
          "String32": 15, "String64": 17, "String64Array": 18, "Binary": 19, "BinaryArray": 20, "UInt": 21, "UIntArray": 22,
          "Int64": 23, "Int64Array": 24, "UInt64": 25, "UInt64Array": 26, "WString16Array": 28}
INLINE = ("Bool", "Int", "Float", "Enum", "UInt")   # (the value is the table's own word; the other types keep it in the data section)
KINDS = tuple(sorted(set(GROUPS) | {"Bool64bitKey", "BoolExp", "Struct", "String16", "WString16"}))
CATEGORIES = ("progress", "items", "songs", "quest", "keys", "rupees", "ammo")
MODES = ("shared", "pool", "own")
HOW = ("event table", "files", "struct", "names file", "source comment", "sweep", "placement")
COOP = re.compile(r"(?:(?:%s), (?:%s)|story scene, own|out: .+|not read)\Z" % ("|".join(CATEGORIES), "|".join(MODES)))
HASH = re.compile(r"[0-9a-f]{8}(?:[0-9a-f]{8})?\Z")

# The classifier's reasons (fd_classify.py) in a few words; a reason this table does not know is kept as it is.
REASONS = (("never saved", "not saved"), ("saved in another file", "other file"), ("temporary", "temporary"),
           ("not reset by a new game", "no new-game reset"), ("heart reward", "heart reward"), ("unshared list", "unshared list"),
           ("a boss fight's own flag", "boss fight's own"), ("an Int that is in no group", "Int in no group"),
           ("a count that stays with each player", "own count"))

KIND_NOTES = {
    "Bool": "A flag: true or false", "Int": "A signed 32-bit number", "UInt": "An unsigned 32-bit number", "Float": "A 32-bit float",
    "Enum": "One of a list of named values; the saved value is the hash of the value's name (the values are listed in the row's note)",
    "EnumArray": "An array of an enum's values", "BoolArray": "An array of flags", "IntArray": "An array of Ints",
    "UIntArray": "An array of UInts", "FloatArray": "An array of floats", "Int64": "A signed 64-bit number",
    "UInt64": "An unsigned 64-bit number", "Int64Array": "An array of Int64s", "UInt64Array": "An array of UInt64s",
    "Vector3": "Three floats", "String16": "A text of up to 15 bytes", "String32": "A text of up to 31 bytes",
    "String64": "A text of up to 63 bytes", "String64Array": "An array of String64s", "WString16": "A wide text (16-bit characters)",
    "WString16Array": "An array of wide texts", "Binary": "A block of bytes (the caption's picture is one)",
    "BinaryArray": "An array of blocks of bytes",
    "Struct": "A group of flags: it lists its members (the hash of each member's own name and the flag that holds it; their number is in the row's note) and holds no value itself",
    "Bool64bitKey": "A per-object flag keyed by a 64-bit hash (a placed object's): only the true keys are saved, as the key run of progress.sav",
    "BoolExp": "A logic expression over other values (its terms are in the row's note); computed, never saved",
}

# Which page a row goes to: the first pattern its family matches. Each page is a group of families that read alike.
PAGES = (
    ("items", "Items, songs, quest items, counters", r"^(items|songs|quest|keys|rupees|ammo)\b|^(PouchData|IsGet|Pouch)\b",
     "The flags of what Link carries and has learned: each item's first-pickup marker and count, the capacities, the songs, the quest items, "
     "the small-key counters, the rupee counter and the ammunition counters."),
    ("played-events", "Played events", r"^(HavePlayedEvent\b|unnamed, in group HavePlayedEvent\b)",
     "One Bool for every event the game plays (a scene, a talk, a chest opening): the members of the struct of played events, "
     "named by the event table where it has a row."),
    ("hints-and-talks", "Hints, talks and tutorials",
     r"^(HavePlayedNaviBalloonMessage|HaveTalked|ActionGuide|HavePlayedGetEvent|unnamed, in group (HaveTalked|ActionGuide|HavePlayedNavi|HavePlayedGetEvent))",
     "Navi's hint balloons, the talks with each person, the action-guide tutorials and the scenes of getting an item."),
    ("dungeons", "Dungeons: rooms, maps, logic nodes", r"^(DungeonRoomStep|DungeonInfo|AutogenGameDataLogicNode|unnamed, in group (DungeonRoomStep|DungeonInfo|AutogenGameDataLogicNode))",
     "The per-room state of every dungeon and its Master Quest twin, each dungeon's map, compass and boss key flags and key counter, and "
     "the logic nodes the game names only by an id."),
    ("flat-flags", "Single flags", r"^(flat flags|flat \w+ flags|unnamed, in no group)",
     "Flags that are not members of a struct: room, gimmick, boss, person and minigame flags named in full, and the ones with no name."),
    ("object-keys-placed", "Per-object keys of placed actors", r"^per-object keys \(a placed actor's hash\)",
     "One key for every placed thing the game keeps a flag for (a chest, a pot, a grass patch, a rock, a Gold Skulltula ...), "
     "matched to the placed actor of the game's map files that has the same 64-bit hash."),
    ("object-keys-other", "Per-object keys with no placed actor found", r"^per-object keys \(no placed actor",
     "The per-object keys whose hash no placed actor of the files the tools read has. They are saved in the key run of progress.sav."),
    ("expressions", "Expressions", r"^__expression__",
     "The game's logic expressions (BoolExp): a flag computed from other values, never saved."),
    ("structs", "Structs", r"^__struct__",
     "The structs of the list: each groups flags under a shared name and gives their members' hashes."),
    ("other-values", "Other values", r"^__other__",
     "The values of every other kind: enums, floats, strings, arrays, vectors, 64-bit numbers, binary data."),
    ("other-groups", "Other groups of flags", r".",
     "Every other struct of flags: per-object Bools and counters named by a placed actor's id, enemy counts, shop counts, minigame values and the like."),
)
# the pages' own order in the index
PAGE_KEYS = [p[0] for p in PAGES]


# ---------------------------------------------------------------------------------------------------------------- the rows

def short_reason(reason):
    for start, short in REASONS:
        if reason.startswith(start):
            return short
    return reason[:40]


def coop_cell(row, source):
    if source == "excluded":
        return "out: " + short_reason(row["reason"])
    if source == "others":
        return "not read"
    if row["scene"] == "yes":
        return "story scene, own"
    return "%s, %s" % (row["category"], row["default_mode"])


def note_cell(note):
    m = re.fullmatch(r'a played event with no name here; its struct lists members in name order, so it sorts between "(.*)" and "(.*)"', note)
    return "sorts between %s and %s" % (m.group(1), m.group(2)) if m else note


def group_cell(kind, file):
    if kind == "Bool64bitKey":
        return "keys"
    if file == "none" or kind not in GROUPS:
        return "-"
    return str(GROUPS[kind])


def clean(text):
    """A cell: one line, no bar (it would end the cell)."""
    return re.sub(r"\s+", " ", str(text).replace("|", "/")).strip()


def page_key(r):
    kind, family = r["kind"], r["family"]
    if kind == "Struct":
        return "structs"
    if kind == "BoolExp":
        return "expressions"
    if kind not in ("Bool", "Int", "Bool64bitKey"):
        return "other-values"
    for key, _, pattern, _ in PAGES:
        if re.search(pattern, family):
            return key
    return "other-groups"


def rows_from_build(folder):
    """The rows of a `flagdata.py build` output folder (flags.csv, excluded.csv, others.csv), as dicts with the map's fields."""
    out = []
    for name, source in (("flags.csv", "flags"), ("excluded.csv", "excluded"), ("others.csv", "others")):
        path = Path(folder) / name
        if not path.is_file():
            raise ValueError("%s has no %s: run `flagdata.py build` and give its --out folder" % (folder, name))
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                file = FILES.get(int(row["file"]), "file %s" % row["file"]) if str(row["file"]).lstrip("-").isdigit() else "none"
                kind = row["kind"]
                out.append(dict(hash=row["hash"].lower(), name=row["name"], how=row.get("name_source", "") if row["name"] else "", kind=kind,
                                default=row["default"], reset=row["reset"] if row["reset"] != "" else "0", file=file,
                                group=group_cell(kind, file), coop=coop_cell(row, source), map=row.get("map", ""),
                                note="; ".join(x for x in (note_cell(row.get("note", "")), row.get("extra", "")) if x), what="", sure="read",
                                source="", family=row.get("family", ""),
                                reason=row.get("reason", "")))
    return out


def read_notes(path):
    """{hash: (what, sure, source)} of the descriptions table."""
    notes = {}
    if not Path(path).is_file():
        return notes
    seen = False
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if line.strip() == NOTES_HEADER:
            seen = True
            continue
        if not seen or not line.startswith("| `"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 4:
            raise ValueError("%s:%d: a description row has four cells (hash, what, sure, source)" % (path, number))
        h = cells[0].strip("`")
        if h in notes:
            raise ValueError("%s:%d: %s is described twice" % (path, number, h))
        notes[h] = (cells[1], cells[2], cells[3])
    return notes


def parse_pages(folder=FLAGS):
    """[row dict] of every page in the folder: each row with its page file, line number and family (the heading above its table)."""
    rows = []
    for page in sorted(Path(folder).glob("*.md")):
        if page.name in ("README.md", "descriptions.md"):
            continue
        family, in_table = "", False
        for number, line in enumerate(page.read_text(encoding="utf-8").splitlines(), 1):
            if line.startswith("### "):
                family, in_table = line[4:].strip(), False
            elif line.strip() == HEADER:
                in_table = True
            elif in_table and line.startswith("| `"):
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                row = dict(zip(("hash", "name", "how", "kind", "default", "reset", "file", "group", "coop", "map", "note", "what", "sure",
                                "source"), cells))
                row["hash"], row["name"] = row["hash"].strip("`"), row["name"].strip("`")
                row.update(family=family, page=page.name, line=number, cells=len(cells))
                rows.append(row)
            elif not line.startswith("|"):
                in_table = False
    return rows


# ---------------------------------------------------------------------------------------------------------------- reading

def sort_key(r):
    return (r["family"].lower(), 0 if r["name"] else 1, r["name"].lower(), r["hash"])


def render_row(r):
    cells = ["`%s`" % r["hash"], "`%s`" % clean(r["name"]) if r["name"] else "", r["how"], r["kind"], r["default"], r["reset"], r["file"],
             r["group"], r["coop"], r["map"], r["note"], r["what"], r["sure"], r["source"]]
    return "| " + " | ".join(clean(c) if i not in (0, 1) else c for i, c in enumerate(cells)) + " |"


def plan_pages(rows):
    """{page key: [[(family, [rows]) of one page] ...]}: the rows of each page group in order, cut into files below PAGE_LIMIT bytes
    (a family that does not fit goes on with the same heading on the next page)."""
    by_page = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by_page[r["page_key"]][r["family"]].append(r)
    plan = {}
    for key in PAGE_KEYS:
        if key not in by_page:
            continue
        pages, state = [], dict(current=[], size=0)

        def flush():
            if state["current"]:
                pages.append(state["current"])
            state.update(current=[], size=0)

        for family in sorted(by_page[key], key=str.lower):
            head = len(family.encode("utf-8")) + len(HEADER) + len(RULE) + 12
            section = None
            for r in sorted(by_page[key][family], key=sort_key):
                cost = len(render_row(r).encode("utf-8")) + 1
                if section is None or state["size"] + cost > PAGE_LIMIT:
                    if state["size"] + head + cost > PAGE_LIMIT:
                        flush()
                    section = (family, [])
                    state["current"].append(section)
                    state["size"] += head
                section[1].append(r)
                state["size"] += cost
        flush()
        plan[key] = pages
    return plan


def page_name(key, index, count):
    return "%s.md" % key if count == 1 else "%s-%d.md" % (key, index + 1)


def render_page(key, index, count, sections):
    title, intro = next((p[1], p[3]) for p in PAGES if p[0] == key)
    total = sum(len(rows) for _, rows in sections)
    out = ["# Flag map: %s%s" % (title, "" if count == 1 else " (%d of %d)" % (index + 1, count)), "",
           "%s %d rows on this page. Columns, values and how sure a row is: [README.md](README.md)." % (intro, total), ""]
    for family, rows in sections:
        out += ["### " + family, "", HEADER, RULE]
        out += [render_row(r) for r in rows]
        out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------------------------------------------- build

def merge_notes(rows, notes):
    unknown = sorted(set(notes) - {r["hash"] for r in rows})
    if unknown:
        raise ValueError("flags/descriptions.md describes flags the build does not have: %s" % ", ".join(unknown[:10]))
    for r in rows:
        if r["hash"] in notes:
            r["what"], r["sure"], r["source"] = notes[r["hash"]]


def kinds_block(rows):
    """The index's table of the list's containers: rows, names, and where each kind sits in a save file."""
    out = ["| Kind | Rows | Named | Save file | Group | What it is |", "|---|---|---|---|---|---|"]
    kinds = Counter(r["kind"] for r in rows)
    for kind, count in sorted(kinds.items(), key=lambda kv: (-kv[1], kv[0])):
        mine = [r for r in rows if r["kind"] == kind]
        files = sorted({r["file"] for r in mine if r["file"] != "none"}, key=lambda f: FILE_INDEX[f])
        out.append("| %s | %s | %s | %s | %s | %s |" % (kind, "{:,}".format(count), "{:,}".format(sum(1 for r in mine if r["name"])),
                                                      ", ".join(files) or "never saved", group_cell(kind, files[0] if files else "none"),
                                                      KIND_NOTES.get(kind, "")))
    out.append("| **all** | **{:,}** | **{:,}** | | | |".format(len(rows), sum(1 for r in rows if r["name"])))
    return out


def write_index_block(index, marker, lines):
    text = index.read_text(encoding="utf-8") if index.is_file() else ""
    begin, end = "<!-- %s:begin -->" % marker, "<!-- %s:end -->" % marker
    if begin not in text or end not in text:
        raise ValueError("%s has no %s ... %s markers to write into" % (index, begin, end))
    head, rest = text.split(begin, 1)
    _, tail = rest.split(end, 1)
    index.write_text(head + begin + "\n" + "\n".join(lines) + "\n" + end + tail, encoding="utf-8")


def update_kept(pages_text, kept=KEPT):
    """Rewrite the flag pages' rows of docs/names-kept.md: a flag name such as the item that shares a name with a project is the
    game's identifier, kept by file and count like the function map's other literals. Returns the number of rows written."""
    sys.path.insert(0, str(ROOT))
    import json
    import name_policy
    counts = Counter()
    for page, text in pages_text.items():
        for literal in name_policy.literals(text):
            counts[(page, literal)] += 1
    text = kept.read_text(encoding="utf-8")
    before, rest = text.split(name_policy.BEGIN, 1)
    body, after = rest.split(name_policy.END, 1)
    lines = [line for line in body.split("\n") if not line.startswith('["docs/oot/flags/')]
    fresh = [json.dumps(["docs/oot/flags/" + page, literal, n, KEPT_REASON], ensure_ascii=False) for (page, literal), n in sorted(counts.items())]
    # (the other rows keep their order and their lines: the new ones go in front of the first row of a later file)
    last = next((i for i, line in enumerate(lines) if line.startswith("[") and json.loads(line)[0] > "docs/oot/flags/\uffff"), None)
    if last is None:
        last = max((i for i, line in enumerate(lines) if line.startswith("[")), default=-1) + 1
    kept.write_text(before + name_policy.BEGIN + "\n".join(lines[:last] + fresh + lines[last:]) + name_policy.END + after, encoding="utf-8")
    return len(counts)


def build(source, made_from, notes_path=NOTES, folder=FLAGS):
    rows = rows_from_build(source)
    for r in rows:
        r["page_key"] = page_key(r)
    merge_notes(rows, read_notes(notes_path))
    hashes = Counter(r["hash"] for r in rows)
    clash = sorted(h for h, n in hashes.items() if n > 1)
    if clash:
        raise ValueError("a hash is in two containers of the list: %s" % ", ".join(clash[:10]))
    plan = plan_pages(rows)
    Path(folder).mkdir(parents=True, exist_ok=True)
    for old in Path(folder).glob("*.md"):
        if old.name not in ("README.md", "descriptions.md"):
            old.unlink()
    written, texts, table = [], {}, []
    for key, pages in plan.items():
        for index, sections in enumerate(pages):
            name = page_name(key, index, len(pages))
            text = render_page(key, index, len(pages), sections)
            (Path(folder) / name).write_text(text, encoding="utf-8")
            written.append(name)
            texts[name] = text
            title = next(p[1] for p in PAGES if p[0] == key)
            table.append("| [%s](%s) | %s%s | %s |" % (name, name, title, "" if len(pages) == 1 else " (%d of %d)" % (index + 1, len(pages)),
                                                  "{:,}".format(sum(len(rs) for _, rs in sections))))
    index = Path(folder) / "README.md"
    lines = ["| Page | What | Rows |", "|---|---|---|"] + table + ["| **all** | | **{:,}** |".format(len(rows))]
    write_index_block(index, "pages", lines)
    write_index_block(index, "made", [made_from])
    write_index_block(index, "kinds", kinds_block(rows))
    kept = update_kept(texts) if Path(folder).resolve() == FLAGS.resolve() and KEPT.is_file() else 0
    return len(rows), written, kept


# ---------------------------------------------------------------------------------------------------------------- lookup

def load():
    rows = parse_pages()
    if not rows:
        raise ValueError("no flag pages in %s" % FLAGS)
    return rows


def search_text(r):
    return " ".join([r["name"], r["family"], r["map"], r["note"], r["what"], r["kind"], r["coop"], r["hash"], r["how"]]).lower()


def find_rows(rows, query):
    q = query.strip().strip("`")
    low = q.lower()
    if re.fullmatch(r"(0x)?[0-9a-f]{8}([0-9a-f]{8})?", low):
        h = low[2:] if low.startswith("0x") else low
        return [r for r in rows if r["hash"] == h]
    if re.fullmatch(r"\d{9,20}", q):   # (a per-object key in decimal, as a save editor or a name shows it)
        h = "%016x" % int(q) if int(q) < 1 << 64 else ""
        hit = [r for r in rows if r["hash"] == h]
        return hit or [r for r in rows if q in r["name"]]
    exact = [r for r in rows if r["name"].lower() == low]
    if exact:
        return exact
    words = low.split()
    hits = [r for r in rows if all(w in search_text(r) for w in words)]
    return sorted(hits, key=lambda r: not all(w in r["name"].lower() for w in words))   # (rows whose name has every word first)


def show_row(r):
    where = FILE_PATHS.get(r["file"], "no file: the flag is never saved")
    print("%s  %s" % (r["hash"], r["name"] or "(no name)"))
    for label, key in (("page", None), ("family", "family"), ("named by", "how"), ("kind", "kind"), ("default", "default"),
                       ("reset kind", "reset"), ("save file", "file"), ("group", "group"), ("co-op", "coop"), ("map", "map"),
                       ("note", "note"), ("what it is", "what"), ("sure", "sure"), ("source", "source")):
        value = "flags/%s:%d" % (r["page"], r["line"]) if key is None else r[key]
        if value != "":
            print("  %-10s %s" % (label, value))
    print("  in a file: " + where_in_file(r, where))


def where_in_file(r, where):
    if r["file"] == "none":
        return "%s." % where
    if r["kind"] == "Bool64bitKey":
        return "%s: the key run at the end of the file (a sorted list of the true keys), not the table." % where
    if r["kind"] not in GROUPS:
        return "%s: the kind %s has no group (see docs/oot/save-format.md)." % (where, r["kind"])
    how = ("the table entry's own word" if r["kind"] in INLINE else "an offset into the data section, where the value's bytes are")
    return ("%s, group %s (%s): the entry {hash, value} among that group's entries; the value is %s. "
            "docs/oot/save-format.md has the layout." % (where, r["group"], r["kind"], how))


def cmd_find(query):
    rows = load()
    hits = find_rows(rows, query)
    for r in hits[:20]:
        print("flags/%s:%d  [%s]" % (r["page"], r["line"], r["family"]))
        print("  " + render_row(r))
    if len(hits) > 20:
        print("(%d rows; the first 20 shown)" % len(hits))
    if not hits:
        print("nothing for %r" % query)
    return 0 if hits else 1


def cmd_show(query):
    hits = find_rows(load(), query)
    if len(hits) != 1:
        print("%s: %s" % (query, "no row" if not hits else "%d rows; give the hash" % len(hits)))
        return 1
    show_row(hits[0])
    return 0


def cmd_stats():
    rows = load()
    n = len(rows)
    pct = lambda k: "%d (%.1f%%)" % (k, 100.0 * k / n) if n else "0"
    print("%d rows on %d pages" % (n, len({r["page"] for r in rows})))
    for title, key in (("kind", "kind"), ("save file", "file"), ("co-op", lambda r: r["coop"].split(",")[0] if not r["coop"].startswith("out") else r["coop"]),
                       ("named by", lambda r: r["how"] or "(no name)"), ("sure", "sure")):
        get = key if callable(key) else (lambda r, k=key: r[k])
        print("%s:" % title)
        for value, k in Counter(get(r) for r in rows).most_common():
            print("  %-34s %s" % (value, pct(k)))
    named = sum(1 for r in rows if r["name"])
    print("named: %s; unnamed: %s; with a description of ours: %s" % (pct(named), pct(n - named), pct(sum(1 for r in rows if r["what"]))))
    for kind in ("Bool", "Int"):
        k = [r for r in rows if r["kind"] == kind]
        print("%s: %d, of them named %d, co-op reads %d" % (kind, len(k), sum(1 for r in k if r["name"]), sum(1 for r in k if not r["coop"].startswith("out"))))
    return 0


def cmd_names():
    for name in sorted({r["name"] for r in load() if r["name"]}):
        print(name)
    return 0


# ---------------------------------------------------------------------------------------------------------------- check

def murmur3():
    sys.path.insert(0, str(ROOT / "flagdata"))
    import fd_romfs
    return fd_romfs.murmur3


def check(folder=FLAGS, notes_path=NOTES, hash_of=None):
    """(problems, notes) of the pages in `folder`."""
    hash_of = hash_of or murmur3()
    problems = []
    rows = parse_pages(folder)
    seen = {}
    for r in rows:
        where = "%s:%d" % (r["page"], r["line"])
        if r["cells"] != len(COLUMNS):
            problems.append("%s: a row has %d cells, not %d" % (where, r["cells"], len(COLUMNS)))
            continue
        if not HASH.match(r["hash"]):
            problems.append("%s: %r is not a hash (8 hexadecimal digits; 16 for a per-object key)" % (where, r["hash"]))
            continue
        if r["hash"] in seen:
            problems.append("%s: %s is in the map twice (first: %s)" % (where, r["hash"], seen[r["hash"]]))
        seen.setdefault(r["hash"], where)
        for key in ("kind", "reset", "file", "group", "coop", "sure"):
            if r[key] == "":
                problems.append("%s: %s has no %s" % (where, r["hash"], key))
        if r["kind"] not in KINDS:
            problems.append("%s: %s: %r is not a kind of the list" % (where, r["hash"], r["kind"]))
        if r["kind"] in ("Bool", "Int") and r["default"] == "":
            problems.append("%s: %s: a %s has a default" % (where, r["hash"], r["kind"]))
        if r["file"] not in FILE_INDEX:
            problems.append("%s: %s: %r is not a save file (%s)" % (where, r["hash"], r["file"], ", ".join(FILE_INDEX)))
        elif r["group"] != group_cell(r["kind"], r["file"]) and r["kind"] in KINDS:
            problems.append("%s: %s: a %s in the file %s is in group %s, not %s" % (where, r["hash"], r["kind"], r["file"],
                                                                                 group_cell(r["kind"], r["file"]), r["group"]))
        if r["coop"] and not COOP.match(r["coop"]):
            problems.append("%s: %s: %r is not a co-op fate" % (where, r["hash"], r["coop"]))
        if r["sure"] and r["sure"] not in SURE:
            problems.append("%s: %s: how sure is tested, read or guess, not %r" % (where, r["hash"], r["sure"]))
        if r["what"] and not r["source"]:
            problems.append("%s: %s has a description and no source" % (where, r["hash"]))
        if r["name"] and not r["how"]:
            problems.append("%s: %s has a name and no 'named by'" % (where, r["hash"]))
        if r["name"] and len(r["hash"]) == 8 and "%08x" % hash_of(r["name"]) != r["hash"]:
            problems.append("%s: the name %s hashes to %08x, not %s" % (where, r["name"], hash_of(r["name"]), r["hash"]))
        if r["name"] and len(r["hash"]) == 16:
            problems.append("%s: a per-object key (%s) has no name to hash" % (where, r["hash"]))
        if r["kind"] == "Bool64bitKey" and len(r["hash"]) != 16:
            problems.append("%s: a per-object key has 16 digits" % where)
        if r["kind"] != "Bool64bitKey" and len(r["hash"]) != 8:
            problems.append("%s: only a per-object key has 16 digits" % where)
    try:
        notes = read_notes(notes_path)
    except ValueError as error:
        problems.append(str(error))
        notes = {}
    for h, (what, sure, source) in sorted(notes.items()):
        if h not in seen:
            problems.append("descriptions.md: %s is not in the map" % h)
        if not what or sure not in SURE or not source:
            problems.append("descriptions.md: %s needs a description, tested/read/guess and a source" % h)
    for r in rows:
        if r["hash"] in notes and notes[r["hash"]] != (r["what"], r["sure"], r["source"]):
            problems.append("%s:%d: %s differs from descriptions.md: rebuild the pages" % (r["page"], r["line"], r["hash"]))
    index = Path(folder) / "README.md"
    text = index.read_text(encoding="utf-8") if index.is_file() else ""
    names = sorted({r["page"] for r in rows})
    for name in names:
        if "(%s)" % name not in text:
            problems.append("README.md: the page table does not list %s" % name)
        size = (Path(folder) / name).stat().st_size
        if size > 200_000:
            problems.append("%s is %d bytes: a file over 200 KB is refused by the publication check" % (name, size))
    for name in re.findall(r"\]\(([a-z0-9-]+\.md)\)", text.split("<!-- pages:begin -->")[-1].split("<!-- pages:end -->")[0]):
        if not (Path(folder) / name).is_file():
            problems.append("README.md lists %s, which is not here" % name)
    m = re.search(r"\| \*\*all\*\* \| \| \*\*([\d,]+)\*\*", text)
    if m and int(m.group(1).replace(",", "")) != len(rows):
        problems.append("README.md says %s rows, the pages have %d" % (m.group(1), len(rows)))
    return problems, rows


def cmd_check():
    problems, rows = check()
    named = sum(1 for r in rows if r["name"])
    print("%d rows on %d pages; %d named (every name hashes to its row), %d with a description of ours" % (
        len(rows), len({r["page"] for r in rows}), named, sum(1 for r in rows if r["what"])))
    for p in problems[:200]:
        print("FAIL: " + p)
    print("PASS" if not problems else "FAIL: %d problems" % len(problems))
    return 1 if problems else 0


def cmd_build(args):
    count, written, kept = build(args.source, args.made_from, Path(args.descriptions))
    print("%d rows on %d pages in %s; %d kept-literal rows in docs/names-kept.md" % (count, len(written), FLAGS, kept))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("find").add_argument("query")
    sub.add_parser("show").add_argument("hash")
    sub.add_parser("stats")
    sub.add_parser("check")
    sub.add_parser("names")
    b = sub.add_parser("build")
    b.add_argument("--from", dest="source", required=True, help="the folder `flagdata.py build` wrote (flags.csv, excluded.csv, others.csv)")
    b.add_argument("--made-from", default="Made by `flagmap.py build` from a `flagdata.py build` output.",
                   help="one line for the index: the game build, the list's revision, the LS revision the rules were read at")
    b.add_argument("--descriptions", default=str(NOTES))
    a = ap.parse_args(argv)
    try:
        if a.cmd == "find":
            return cmd_find(a.query)
        if a.cmd == "show":
            return cmd_show(a.hash)
        if a.cmd == "stats":
            return cmd_stats()
        if a.cmd == "check":
            return cmd_check()
        if a.cmd == "names":
            return cmd_names()
        return cmd_build(a)
    except (ValueError, OSError) as error:
        print("flagmap: %s" % error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
