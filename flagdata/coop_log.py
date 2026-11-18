#!/usr/bin/env python3
"""Annotate an LS game log's co-op progress lines with the flags' names, families, categories and default modes.

  coop_log.py [--cache FILE | --state DIR] [--summary] [--names N] [--only VERB,...] [--all] LOG ...    (LOG: `-` is stdin)

The co-op sync lines name a flag by its hash: `sent progress 1a2b3c4d = 1 to all`, `received ...`, `applied ...`, `held ...` (a boss's end
set), `the game shows ...`, `pool keys ...` (HOS_COOP_TRACE=1 makes the game log the sent, received, applied, held and shows lines), the `test:` and `flag ... reads`
lines and `refused from member`. Each such line is printed as it is, followed by `-> name  [family]  category, default mode`, from the
table `flagdata.py build` made from the player's own game files (a private cache under the user's state folder; without one, this tool
says how to make it). By default only the annotated lines are printed; --all prints every line.

--summary prints, for each verb, the flags grouped by category and family: lines, distinct flags and a few names (--names N, default 3).
A story scene is shown as its own group: the default room keeps those each player's own. Standard library only.
"""
import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fd_cache  # noqa: E402

H = r"([0-9a-f]{8})"
CAT = r"(progress|items|songs|quest|keys|rupees|ammo)"
PATTERNS = [   # (regex, verb or group number of the verb, group of the category (0: none), group of the hash, group of the kind (0: none))
    (re.compile(r"\b(sent|received|applied|held)\s+%s\s+%s\b" % (CAT, H)), 1, 2, 3, 0),
    (re.compile(r"\bthe game shows\s+%s\s+%s\b" % (CAT, H)), "shows", 1, 2, 0),
    (re.compile(r"\bpool\s+%s\s+%s\b" % (CAT, H)), "pool", 1, 2, 0),
    (re.compile(r"\btest: set (Bool|Int)\s+%s\b" % H), "test set", 0, 2, 1),
    (re.compile(r"\btest: (Bool|Int)\s+%s reads\b" % H), "test read", 0, 2, 1),
    (re.compile(r"\btest: no Bool or Int flag\s+%s\b" % H), "test read", 0, 1, 0),
    (re.compile(r"\bflag\s+%s reads\b" % H), "check", 0, 1, 0),
    (re.compile(r"\brefused from member \d+: .*?\b%s\b \(" % H), "refused", 0, 1, 0),
    (re.compile(r"\b%s of its end set\b" % H), "boss skipped", 0, 1, 0),
]
VERB_ORDER = ["applied", "held", "received", "sent", "shows", "pool", "test set", "test read", "check", "refused", "boss skipped"]


def references(line):
    """[(verb, category from the line or '', hash text, kind from the line or '')] of the flags a log line names."""
    out = []
    for rx, verb, cat, h, kind in PATTERNS:
        for m in rx.finditer(line):
            out.append((m.group(verb) if isinstance(verb, int) else verb, m.group(cat) if cat else "", m.group(h), m.group(kind) if kind else ""))
    return out


class Table:
    def __init__(self, doc):
        self.flags = doc["flags"]

    def find(self, h, kind="", category=""):
        entries = self.flags.get(h)
        if not entries:
            return None
        for e in entries:
            if (not kind or e["k"] == kind) and (not category or e["c"] == category):
                return e
        for e in entries:
            if not kind or e["k"] == kind:
                return e
        return entries[0]


def describe(e):
    """(group label, text) of a cache record."""
    if e is None:
        return "(not in the table)", "not a Bool or Int flag of the cached table"
    name = e["n"] or "(no name)"
    if not e["c"]:
        return "left out", "%s  [%s]  left out: %s" % (name, e["f"] or "-", e["r"])
    group = "progress (story scene)" if e["s"] else e["c"]
    return group, "%s  [%s]  %s, %s" % (name, e["f"], group, e["m"])


def annotate(table, line, only=None):
    """The line with `  -> ...` appended for each flag it names, or None when it names none (or none of the verbs wanted)."""
    notes, seen = [], []
    for verb, category, h, kind in references(line):
        if only and verb not in only:
            continue
        e = table.find(h, kind, category)
        label, text = describe(e)
        notes.append(text)
        seen.append((verb, label, e, h))
    if not notes:
        return None, []
    return "%s  -> %s" % (line.rstrip("\n"), "; ".join(notes)), seen


def summary(events, names):
    """Text of the summary: {verb: {group: {family: [lines, {hash: name}]}}}."""
    by = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: [0, {}])))
    for verb, label, e, h in events:
        fam = e["f"] if e and e["f"] else "-" if e is None else "(left out)"
        cell = by[verb][label][fam]
        cell[0] += 1
        cell[1].setdefault(h, (e["n"] if e and e["n"] else "(no name) " + h))
    out = []
    for verb in sorted(by, key=lambda v: VERB_ORDER.index(v) if v in VERB_ORDER else 99):
        total = sum(c[0] for g in by[verb].values() for c in g.values())
        distinct = len({h for g in by[verb].values() for c in g.values() for h in c[1]})
        out.append("%s: %d lines, %d distinct flags" % (verb, total, distinct))
        for label in sorted(by[verb]):
            out.append("  %s" % label)
            for fam, (n, flags) in sorted(by[verb][label].items(), key=lambda x: (-x[1][0], x[0])):
                shown = ", ".join(sorted(flags.values())[:names])
                out.append("    %-44s %5d lines %4d flags%s" % (fam, n, len(flags), ("   e.g. " + shown) if names and shown else ""))
        out.append("")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--cache", help="the table `flagdata.py build` wrote (default: the latest under the state folder)")
    ap.add_argument("--state", help="the private state folder (default: see fd_cache.py)")
    ap.add_argument("--summary", action="store_true", help="group what the log shows by verb, category and family instead of printing lines")
    ap.add_argument("--names", type=int, default=3, help="names shown per group in the summary (0: none)")
    ap.add_argument("--only", help="only these verbs, comma separated (applied, held, received, sent, shows, pool, test set, ...)")
    ap.add_argument("--all", action="store_true", help="print the lines that name no flag too")
    a = ap.parse_args(argv)
    try:
        table = Table(fd_cache.load(fd_cache.find(a.state, a.cache)))
    except (OSError, ValueError) as error:
        print("coop_log: %s" % error, file=sys.stderr)
        return 2
    only = {v.strip() for v in a.only.split(",")} if a.only else None
    events, lines, unknown = [], 0, Counter()
    for path in a.logs:
        stream = sys.stdin if path == "-" else open(path, encoding="utf-8", errors="replace")
        if len(a.logs) > 1 and not a.summary:
            print("==> %s <==" % path)
        with stream:
            for line in stream:
                text, seen = annotate(table, line, only)
                events.extend(seen)
                lines += text is not None
                for _, _, e, h in seen:
                    if e is None:
                        unknown[h] += 1
                if not a.summary and (text or a.all):
                    print(text if text else line.rstrip("\n"))
    if a.summary:
        print(summary(events, a.names))
    print("%d annotated lines, %d flag references, %d distinct hashes not in the table" % (lines, len(events), len(unknown)), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
