"""Rows, CSV and the markdown report of the classified flags. Local output only: it holds names read from a player's own game files.

A row is one flag: its hash, name (when one was recovered), kind, default, category, whether it is a story scene, the room's default
mode for it, and a family and map worked out from the name or from the struct it is a member of. Nothing in this module knows a name of
the game: families come from the struct names the data itself gives, maps from the Banc file names.
"""
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

import fd_classify
import fd_romfs

CSV_COLUMNS = ["category", "scene", "shared_by_default", "default_mode", "name", "hash", "kind", "default", "map", "prefix", "family",
               "named", "name_source", "note", "reset", "file"]
EXCLUDED_COLUMNS = ["reason", "kind", "name", "hash", "default", "reset", "file", "map", "prefix", "named", "family", "name_source", "note"]
OTHER_COLUMNS = ["kind", "name", "hash", "default", "reset", "file", "map", "prefix", "family", "named", "name_source", "note", "extra"]


def resolve_map(token, maps):
    """A map name for a leading word: an exact map, else the one map whose name holds the word (a word shorter than 4 letters never)."""
    if token in maps:
        return maps[token]
    if len(token) >= 4:
        hits = {v for k, v in maps.items() if token in k}
        if len(hits) == 1:
            return hits.pop()
    return ""


def map_table(actors):
    """{name as written in a file name: the base map (the age and Master Quest variants folded in)}."""
    out = {}
    for m, _, _ in actors.values():
        out[m] = re.sub(r"_(Adult|Child|MQ)$", "", m)
    for base in set(out.values()):
        out.setdefault(base, base)
    return out


class Context:
    """Everything the row builder needs, so that the report and the cache are made from the same rows."""

    def __init__(self, tables, groups, scenes, lists, book, prefix="HavePlayedEvent."):
        self.tables, self.groups, self.scenes, self.lists, self.book, self.prefix = tables, groups, scenes, lists, book, prefix
        self.maps = map_table(book.actors)
        self.parent = {}
        for sh, members in tables.structs.items():
            for m, v in members:
                self.parent.setdefault(v, (sh, m))
        self.played = tables.structs.get(fd_romfs.murmur3(prefix.rstrip(".")), [])
        self.order = {v: i for i, (_, v) in enumerate(self.played)}

    def struct_name(self, h):
        hit = self.book.names.get(h)
        return hit[0] if hit else None

    def top(self, name):
        return name.split(".")[0]

    def area(self, name, parent_name):
        """(map, prefix, note) of a flag from its name, or from its parent struct's when it has none."""
        if name is None:
            parts = (parent_name or "").split(".")
            rest = parts[1] if len(parts) > 1 else ""
            return resolve_map(rest, self.maps), parts[0] if parent_name else "", ""
        if "." in name and not name.startswith(self.prefix):
            parts = name.split(".")
            if len(parts) > 1 and re.fullmatch(r"-?\d{6,}", parts[1]):
                actor = self.book.actors.get(int(parts[1]) & 0xFFFFFFFFFFFFFFFF)
                if actor:
                    return self.maps.get(actor[0], actor[0]), parts[0], "placed actor %s \"%s\" in %s" % (actor[1], actor[2], actor[0])
                return "", parts[0], ""
            return resolve_map(parts[1], self.maps), parts[0], ""
        rest = name[len(self.prefix):] if name.startswith(self.prefix) else name
        words = rest.split("_")
        first = words[0]
        for n in (4, 3, 2, 1):
            hit = self.maps.get("_".join(words[:n]))
            if hit:
                return hit, first, ""
        if first.isdigit():
            return "", "(numeric)", ""
        if len(first) <= 2 and len(words) > 1:   # (a short kind word, then the place: `Xx_<Place>_...`)
            return resolve_map(words[1], self.maps), first, ""
        return resolve_map(first, self.maps), first, ""

    def bounds(self, h):
        """For a played event with no name: the names it sorts between (the struct lists its members in name order)."""
        i = self.order[h]
        names = [(self.book.names[v][0][len(self.prefix):] if v in self.book.names else None) for _, v in self.played]
        lo = next((names[j] for j in range(i - 1, -1, -1) if names[j]), None)
        hi = next((names[j] for j in range(i + 1, len(names)) if names[j]), None)
        return 'a played event with no name here; its struct lists members in name order, so it sorts between "%s" and "%s"' % (
            lo or "(start)", hi or "(end)")

    def family(self, r, name, parent_name):
        g, cat, h = self.groups, r.category, r.entry.hash
        if cat == "items":
            return ("items: first-get marker" if h in g.first_get else "items: item count" if h in g.pouch
                    else "items: capacity" if h in g.capacity else "items: magic meter size")
        if cat in ("songs", "quest", "keys", "rupees", "ammo"):
            return cat
        if name is not None:
            if "." in name:
                return self.top(name) + ".*"
            return "flat flags (no group)"
        if h in self.parent:
            return "unnamed, in group %s" % (self.top(parent_name) if parent_name else "(unnamed group)")
        return "unnamed, in no group"

    def note(self, r, name, parent_name, base):
        h = r.entry.hash
        if name is not None or h not in self.parent:
            return base
        sh, m = self.parent[h]
        if sh == fd_romfs.murmur3(self.prefix.rstrip(".")) and h in self.order:
            return self.bounds(h)
        member = self.book.names.get(m)
        return 'member %s of group %s' % ('"%s"' % member[0] if member else "0x%08x" % m, parent_name or "0x%08x" % sh)


def make_rows(results, ctx):
    """(rows of the classified flags, rows of the ones left out), sorted."""
    rows, left = [], []
    for r in results:
        h, e = r.entry.hash, r.entry
        hit = ctx.book.flag_name(h)
        name, source = hit if hit else (None, "")
        parent = ctx.parent.get(h)
        parent_name = ctx.struct_name(parent[0]) if parent else None
        mp, prefix, note = ctx.area(name, parent_name)
        if r.category is None:
            left.append(dict(reason=r.reason, kind=e.kind, name=name or "", hash="%08x" % h, default=e.default, reset=e.reset, file=e.file,
                             map=mp, prefix=prefix, named="yes" if name else "no", family=ctx.family(r, name, parent_name),
                             name_source=source, note=ctx.note(r, name, parent_name, note), _hash=h))
            continue
        rows.append(dict(category=r.category, scene="yes" if r.scene else "no", shared_by_default="yes" if r.shared_by_default else "no",
                         default_mode=r.mode if not r.scene else "own (story scenes: each player)", name=name or "", hash="%08x" % h,
                         kind=e.kind, default=e.default, map=mp, prefix=prefix, family=ctx.family(r, name, parent_name),
                         named="yes" if name else "no", name_source=source, note=ctx.note(r, name, parent_name, note), reset=e.reset,
                         file=e.file, _hash=h))
    order = {c: i for i, c in enumerate(fd_classify.CATEGORIES)}
    rows.sort(key=lambda x: (order[x["category"]], x["scene"] == "yes", x["family"], x["name"] or "\uffff", x["hash"]))
    left.sort(key=lambda x: (x["reason"], x["name"] or "\uffff", x["hash"]))
    return rows, left


def make_other_rows(ctx):
    """Rows of the entries of every container but Bool and Int (structs, per-object keys, enums, strings, arrays ...), sorted. A name is
    looked for the same way (a 32-bit hash); a per-object key is matched against the placed actors of the Banc files."""
    rows = []
    for o in ctx.tables.others:
        wide = o.kind == "Bool64bitKey" or o.hash >> 32 != 0   # (a key is always 16 digits)
        hit = ctx.book.names.get(o.hash) if o.kind == "Struct" else None if wide else ctx.book.flag_name(o.hash)   # (a struct's name is its group's)
        name, source = hit if hit else (None, "")
        parent = ctx.parent.get(o.hash)
        parent_name = ctx.struct_name(parent[0]) if parent else None
        note, mp, prefix = "", "", ""
        if o.kind == "Bool64bitKey":
            actor = ctx.book.actors.get(o.hash)
            if actor:
                mp, prefix = ctx.maps.get(actor[0], actor[0]), actor[1] or ""
                note = "placed actor %s \"%s\" in %s" % (actor[1], actor[2], actor[0])
            family = "per-object keys (a placed actor's hash)" if actor else "per-object keys (no placed actor of the files)"
        else:
            mp, prefix, note = ctx.area(name, parent_name)
            if name is not None:
                family = ctx.top(name) + ".*" if "." in name else "flat %s flags" % o.kind
            elif o.hash in ctx.parent:
                family = "unnamed, in group %s" % (ctx.top(parent_name) if parent_name else "(unnamed group)")
            else:
                family = "unnamed, in no group"
            if name is None and o.hash in ctx.parent:
                member = ctx.book.names.get(ctx.parent[o.hash][1])
                note = 'member %s of group %s' % ('"%s"' % member[0] if member else "0x%08x" % ctx.parent[o.hash][1], parent_name or "0x%08x" % ctx.parent[o.hash][0])
        rows.append(dict(kind=o.kind, name=name or "", hash=("%016x" if wide else "%08x") % o.hash, default=o.default,
                         reset="" if o.reset is None else o.reset, file="" if o.file is None else o.file, map=mp, prefix=prefix,
                         family=family, named="yes" if name else "no", name_source=source, note=note, extra=o.extra))
    rows.sort(key=lambda x: (x["kind"], x["family"], x["name"] or "\uffff", x["hash"]))
    return rows


def write_csv(path, columns, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(columns)
        for r in rows:
            w.writerow([r[c] for c in columns])


def n(x):
    return "{:,}".format(x)


class Doc:
    def __init__(self):
        self.out = []

    def w(self, s=""):
        self.out.append(s)

    def table(self, head, body, align=None):
        align = align or ["l"] * len(head)
        self.w("| " + " | ".join(head) + " |")
        self.w("|" + "|".join("---:" if a == "r" else ":---" for a in align) + "|")
        for r in body:
            self.w("| " + " | ".join(str(x) for x in r) + " |")
        self.w()

    def text(self):
        return "\n".join(self.out) + "\n"


def listing(rows, fallback="(no name found)"):
    return [[("`%s`" % r["name"]) if r["name"] else ("(%s; %s)" % (fallback.strip("()"), r["note"]) if r["note"] else fallback),
             r["hash"], r["kind"], r["default"]] for r in rows]


def hp_prefix(name, prefix):
    rest = name[len(prefix):]
    first = rest.split("_")[0]
    return "(numeric)" if first.isdigit() else first


def write_md(path, ctx, results, rows, left, info):
    """`info`: what the report says about how it was made (revision, paths, the log comparison)."""
    d = Doc()
    cat = {c: [r for r in rows if r["category"] == c] for c in fd_classify.CATEGORIES}
    prog = cat["progress"]
    scenes = [r for r in prog if r["scene"] == "yes"]
    shared = sum(1 for r in rows if r["shared_by_default"] == "yes")
    named = sum(1 for r in rows if r["named"] == "yes")
    t = ctx.tables
    d.w("# Flags classified by co-op progress sync")
    d.w()
    d.w("Made from a player's own game files and an LS checkout by `flagdata.py build`. It holds names read from those files: local, never "
        "to be committed, posted or sent.")
    d.w()
    d.w("## Summary")
    d.w()
    d.w("Of %s Bool and %s Int flags in the game's list, co-op looks at **%s**; the other %s are left out on purpose." % (
        n(len(t.bools)), n(len(t.ints)), n(len(rows)), n(len(left))))
    d.w()
    modes = dict(progress="shared", items="shared", songs="shared", quest="shared", keys="pooled", rupees="each player's own",
                 ammo="each player's own")
    body = [["progress (not a story scene)", n(len(prog) - len(scenes)), "shared"],
            ["story scenes", n(len(scenes)), "each player's own (rule Story scenes: Per player)"]]
    body += [[c, n(len(cat[c])), modes[c]] for c in fd_classify.CATEGORIES[1:]]
    body.append(["**total**", "**%s**" % n(len(rows)), "**%s shared or pooled, %s each player's own**" % (n(shared), n(len(rows) - shared))])
    d.table(["Category", "Flags", "Default room"], body, ["l", "r", "l"])
    d.w("%s of %s classified flags have a name that matches their hash; the others are listed by hash and by their group." % (
        n(named), n(len(rows))))
    d.w()
    d.w("## How this was made")
    d.w()
    for line in info.get("lines", []):
        d.w("- " + line)
    d.w()

    # ---- progress
    d.w("## Progress: %s flags (%s story scenes + %s shared)" % (n(len(prog)), n(len(scenes)), n(len(prog) - len(scenes))))
    d.w()
    d.w("Saved Bools that a new game resets, that are not temporary and not in the lists of flags left out, and not a song or an item's "
        "marker. %s of them start true." % n(sum(1 for r in prog if r["default"] == 1)))
    d.w()
    d.w("### By family (the struct a flag is a member of, or its own name)")
    d.w()
    fam = defaultdict(lambda: [0, 0, 0])
    for r in prog:
        f = fam[r["family"]]
        f[0] += 1
        f[1] += r["scene"] == "yes"
        f[2] += r["named"] == "yes"
    d.table(["Family", "Flags", "story scenes", "named"], [[k, n(a), n(s), n(m)] for k, (a, s, m) in sorted(fam.items(), key=lambda x: -x[1][0])],
            ["l", "r", "r", "r"])
    played = [r for r in prog if r["name"].startswith(ctx.prefix)]
    if played:
        d.w("### Played events by the first word of the name")
        d.w()
        c = defaultdict(lambda: [0, 0])
        for r in played:
            p = hp_prefix(r["name"], ctx.prefix)
            c[p][0] += 1
            c[p][1] += r["scene"] == "yes"
        top = sorted(c.items(), key=lambda x: -x[1][0])
        body = [[p, n(a), n(s), n(a - s)] for p, (a, s) in top[:30]]
        if len(top) > 30:
            rest = top[30:]
            body.append(["(%d other words)" % len(rest), n(sum(a for _, (a, s) in rest)), n(sum(s for _, (a, s) in rest)),
                         n(sum(a - s for _, (a, s) in rest))])
        d.table(["First word", "Flags", "story scenes (own)", "shared"], body, ["l", "r", "r", "r"])
    d.w("### By map or area")
    d.w()
    d.w("The map the name, the struct path or the placed actor implies (age and Master Quest variants folded in); the last row has none.")
    d.w()
    mp = defaultdict(Counter)
    for r in prog:
        m = r["map"] or "(no map implied)"
        mp[m]["all"] += 1
        mp[m]["scene"] += r["scene"] == "yes"
        mp[m]["named"] += r["named"] == "yes"
    d.table(["Map / area", "Progress flags", "story scenes", "named"],
            [[m, n(c["all"]), n(c["scene"]), n(c["named"])] for m, c in sorted(mp.items(), key=lambda x: (x[0].startswith("("), -x[1]["all"]))],
            ["l", "r", "r", "r"])

    # ---- the small categories, in full
    d.w("## Items: %s flags" % n(len(cat["items"])))
    d.w()
    d.w("The markers of a first pickup (members of the marker struct), the item counts (the pouch structs' counts, less the counts that stay "
        "with each player and the quest items and ammunition counts), the capacities and the magic meter's size.")
    d.w()
    fc = Counter(r["family"] for r in cat["items"])
    d.table(["Source", "Flags"], [[k, n(v)] for k, v in fc.most_common()], ["l", "r"])
    for fname in [k for k, _ in fc.most_common()]:
        rs = sorted([r for r in cat["items"] if r["family"] == fname], key=lambda r: (r["name"] or "\uffff", r["hash"]))
        d.w("### %s (%d)" % (fname, len(rs)))
        d.w()
        d.table(["Name", "Hash", "Kind", "Default"], listing(rs), ["l", "l", "l", "r"])
    for c, title in (("songs", "Songs"), ("quest", "Quest items"), ("keys", "Key counters"), ("rupees", "Rupee counter"),
                     ("ammo", "Ammunition counters")):
        rs = sorted(cat[c], key=lambda r: (r["name"] or "\uffff", r["hash"]))
        d.w("## %s: %d" % (title, len(rs)))
        d.w()
        d.table(["Name", "Hash", "Kind", "Default"], listing(rs), ["l", "l", "l", "r"])

    # ---- left out
    d.w("## What is left out")
    d.w()
    d.w("A Bool is tested in the source's order and the first test that fails leaves it out; an Int is kept only when it is the rupee counter, a "
        "small-key counter, an item count, a capacity or the magic meter's size. Each flag is counted once, under its first reason. All of "
        "them are in `excluded.csv`.")
    d.w()
    why = Counter(r["reason"] for r in left)
    body = [[k, v and n(v)] for k, v in why.most_common()]
    body.append(["**all left out**", "**%s**" % n(len(left))])
    d.table(["Reason", "Flags"], body, ["l", "r"])
    d.w("Check: %s Bool + %s Int = %s; classified %s + left out %s = %s." % (
        n(len(t.bools)), n(len(t.ints)), n(len(t.bools) + len(t.ints)), n(len(rows)), n(len(left)), n(len(rows) + len(left))))
    d.w()
    by_hash = {r["_hash"]: r for r in left + rows}
    L = ctx.lists

    def named_list(title, hashes, text):
        d.w("### %s (%d)" % (title, len(hashes)))
        d.w()
        d.w(text)
        d.w()
        body = []
        for h in sorted(hashes, key=lambda h: ((by_hash[h]["name"] if h in by_hash and by_hash[h]["name"] else "~") .lower(), h)):
            r = by_hash.get(h)
            nm = r["name"] if r and r["name"] else None
            comment = re.sub(r"\s*\(.*\)$", "", L.comments.get(h, "")).strip()
            if not nm and comment and fd_romfs.murmur3(comment) == h:
                nm = comment
            fate = ("left out: " + r["reason"].split(" (")[0]) if r and "reason" in r else ("classified: " + r["category"]) if r else "not in the list"
            body.append([("`%s`" % nm) if nm else '(no name found%s)' % ('; the source says "%s"' % L.comments[h] if h in L.comments else ""),
                         "%08x" % h, r["kind"] if r else "", r["default"] if r else "", fate])
        d.table(["Name", "Hash", "Kind", "Default", "Fate"], body, ["l", "l", "l", "r", "l"])

    named_list("Heart rewards", L.lists["heart_reward_flags"], "Left out so that each game finds and takes its own.")
    named_list("Unshared list", L.lists["unshared_flags"], "One player's own flags (`unshared_flags` in the source): where he stands, failed or "
               "reset tries, refills, Link's age and flags the game's own logic sets and clears.")
    bosses = sorted({h for b in L.boss_sets for h in b["fight"]} | {h for b in L.boss_sets for h, _ in b["members"]})
    named_list("Bosses' own fight flags and end-set members", bosses,
               "What only the fights and warps set, and the end sets' members; the proof flags are in the table and are shared.")
    named_list("Own counts", L.lists["own_counts"], "Item counts that stay with each player.")
    d.w("### Data the classifier never looks at")
    d.w()
    d.w("The sync reads only the manager's Bool and Int containers. The list also holds: " + ", ".join(
        "%s %s" % (k, n(v)) for k, v in t.kinds.most_common() if k not in ("Bool", "Int")) + ".")
    d.w()

    # ---- names
    d.w("## Names")
    d.w()
    d.w("A name is given only when the hash of that exact text matches: identifiers in the game's own files, event table rows, struct "
        "children (checked by hash), placed-actor ids, and names the player supplied.")
    d.w()
    srcs = Counter(r["name_source"] for r in rows if r["named"] == "yes")
    d.table(["Where the name comes from", "Flags"], [[k, n(v)] for k, v in srcs.most_common()] + [["**named**", "**%s**" % n(sum(srcs.values()))]],
            ["l", "r"])
    un = Counter(r["family"] for r in rows if r["named"] == "no")
    d.table(["Unnamed flags", "Count"], [[k, n(v)] for k, v in un.most_common()] + [["**all unnamed**", "**%s**" % n(sum(un.values()))]], ["l", "r"])
    d.w("## Columns of `flags.csv`")
    d.w()
    d.table(["Column", "Meaning"], [
        ["category, scene", "the log's category words; yes for a story scene (progress only)"],
        ["shared_by_default, default_mode", "under the room's default rules: shared, pool (keys) or own"],
        ["name, hash", "the name when its hash matched, and the 32-bit MurmurHash3 hash"],
        ["kind, default", "Bool or Int, and the default in the game's list"],
        ["map, prefix", "the map the name implies, and its first word or struct"],
        ["family, named, name_source, note", "the group, whether a name was found, where from, and a hint for an unnamed flag"],
        ["reset, file", "ResetTypeValue and SaveFileIndex of the list"]], ["l", "l"])
    Path(path).write_text(d.text(), encoding="utf-8")
