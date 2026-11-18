#!/usr/bin/env python3
"""Rebuild the co-op progress classification of a player's own game, and look flags up by hash.

  flagdata.py build --romfs DIR (--source oot_coop.c | --repo LS_CLONE [--rev REV]) --out DIR
                    [--names FILE ...] [--sweep DIR ...] [--compare-log LOG ...] [--state DIR] [--no-cache]
  flagdata.py hash NAME ...            the game's hash of each name (MurmurHash3, seed 0)
  flagdata.py lookup HASH ... [--cache FILE]
                                       name, family, category and default mode of flags, from the cache `build` made

`build` runs the classifier of LS's `host/oot_coop.c` over the player's own GameDataList and RomFS (the same rules, lists, struct
memberships and story-scene list the game uses), recovers the flags' names by hashing, and writes `flags.csv`, `excluded.csv`, `others.csv`
(the entries of the containers the sync never reads: structs, per-object keys, enums, strings, arrays ...) and `flags.md` to --out. It also writes the private cache the log annotator (`coop_log.py`) reads. The counts equal the game's log line
(`playing a save: N progress flags ...`); --compare-log checks that against a log and fails on any difference.

The outputs hold names read from the player's game files: they stay on the player's machine. `build` refuses to write them into the
workbench checkout. Standard library only; zstd from Python 3.14, the `zstandard` package or the `zstd` program.
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fd_cache  # noqa: E402
import fd_classify  # noqa: E402
import fd_names  # noqa: E402
import fd_report  # noqa: E402
import fd_romfs  # noqa: E402
import fd_scenes  # noqa: E402
import fd_source  # noqa: E402

CHECKOUT = Path(__file__).resolve().parents[1]
COUNT_LINE = re.compile(r": (\d+) progress flags \((\d+) of them story scenes[^)]*\), (\d+) items, (\d+) songs, (\d+) quest items, "
                        r"(\d+) key counters, (\d+) rupee counter, (\d+) ammunition counters")
SCENE_LINE = re.compile(r"story scenes: (\d+) of this game's (\d+) events .*?Made from (\d+) files .*?\(list ([0-9a-f]{8})\)")
SCENE_LINE_CACHED = re.compile(r"story scenes: (\d+) of this game's events .*?\(the list kept in .*?list ([0-9a-f]{8})\)")


def compare_log(path, counts, scenes):
    """(lines to print, ok) comparing the game's log with the numbers computed here."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    want = [counts[c] for c in ("progress",)] + [counts["scenes"], counts["items"], counts["songs"], counts["quest"], counts["keys"],
                                                 counts["rupees"], counts["ammo"]]
    lines, ok, seen = [], True, False
    for m in sorted({m.groups() for m in COUNT_LINE.finditer(text)}):
        got = [int(x) for x in m]
        seen = True
        same = got == want
        ok &= same
        lines.append("%s the log's counts %s (progress, scenes, items, songs, quest, keys, rupees, ammo) %s here %s" % (
            "OK  " if same else "FAIL", got, "=" if same else "!=", want))
    if not seen:
        ok = False
        lines.append("FAIL no `N progress flags (...)` line in %s" % path)
    for m in sorted({m.groups() for m in SCENE_LINE.finditer(text)}):
        mine = (len(scenes.kept), len(scenes.events), scenes.files, "%08x" % scenes.stamp())
        got = (int(m[0]), int(m[1]), int(m[2]), m[3])
        ok &= got == mine
        lines.append("%s the log's story-scene list (list, events, files, stamp) %s %s here %s" % ("OK  " if got == mine else "FAIL", got,
                                                                                                  "=" if got == mine else "!=", mine))
    return lines, ok


def refuse_checkout(out):
    out = Path(out).resolve()
    if out == CHECKOUT or CHECKOUT in out.parents:
        raise ValueError("--out is inside the workbench checkout (%s): the outputs hold names read from the player's game files and "
                         "must not be committed; use a folder outside it" % CHECKOUT)


def build(args):
    refuse_checkout(args.out)
    if not args.no_cache:
        refuse_checkout(fd_cache.state_dir(args.state))
    text = fd_source.read_source(args.source, args.repo, args.rev)
    lists = fd_source.parse(text)
    warnings = list(lists.warnings) + fd_source.rule_warnings(text)
    scene_cfg = None
    try:
        other = (Path(args.source).with_name("coop_scenes.c") if args.source
                 else None)
        scene_text = (other.read_text(encoding="utf-8") if other and other.is_file()
                      else fd_source.read_source(None, args.repo, args.rev, fd_source.SCENES_SOURCE) if args.repo else None)
        scene_cfg = fd_source.scan_settings(scene_text) if scene_text else None
    except ValueError as error:
        warnings.append("coop_scenes.c not read (%s): the scanned folders are the built-in defaults" % error)
    if scene_cfg is None:
        warnings.append("scanned folders and table name are the built-in defaults, not read from the source")
    romfs = fd_romfs.Romfs(args.romfs)
    tables = fd_classify.load_tables(romfs)
    collector = fd_names.Collector()
    scenes = fd_scenes.scan(romfs, scene_cfg, collector.add_file)
    classifier = fd_classify.Classifier(tables, lists, scenes)
    results = classifier.all()
    counts = fd_classify.counts(results)
    prefix = fd_scenes.settings(scene_cfg)["prefix"]
    book = fd_names.recover(tables, scenes, collector, prefix, args.names, args.sweep, lists.comments)
    ctx = fd_report.Context(tables, classifier.groups, scenes, lists, book, prefix)
    rows, left = fd_report.make_rows(results, ctx)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    lines = ["classifier: `%s`%s; rules mirrored as of `%s`" % (args.source or fd_source.SOURCE, "" if args.source else " at `%s`" % args.rev,
                                                                  fd_source.RULES_VERIFIED),
             "lists read from it: " + ", ".join("%s %d" % (k, len(v)) for k, v in sorted(lists.lists.items())) +
             ", ammunition %d, boss sets %d" % (len(lists.ammo), len(lists.boss_sets)),
             "the game's own data: %s Bool, %s Int, %s structs; struct groups: markers %d, item counts %d, small keys %d, capacities %d, "
             "map flags %d" % (fd_report.n(len(tables.bools)), fd_report.n(len(tables.ints)), fd_report.n(len(tables.structs)),
                               len(classifier.groups.first_get), len(classifier.groups.pouch), len(classifier.groups.keys),
                               len(classifier.groups.capacity), len(classifier.groups.hud)),
             "story-scene list: %s files read (%d skipped), %s events, %s named by other data (stay shared), %s in the list, stamp `%08x`" % (
                 fd_report.n(scenes.files), len(scenes.skipped), fd_report.n(len(scenes.events)), fd_report.n(len(scenes.gated)),
                 fd_report.n(len(scenes.kept)), scenes.stamp()),
             "counts: " + ", ".join("%s %s" % (k, fd_report.n(v)) for k, v in counts.items()),
             "zstd: %s" % fd_romfs.zstd_backend()]
    ok = True
    for log in args.compare_log:
        got, same = compare_log(log, counts, scenes)
        ok &= same
        lines += ["compared with `%s`: %s" % (Path(log).name, "equal" if same else "DIFFERENT")] + ["  " + g for g in got]
        for g in got:
            print(g)
    if book.rejected:
        warnings.append("names supplied that match no hash: " + ", ".join(book.rejected[:10]))
    lines += ["warning: " + w for w in warnings]
    fd_report.write_csv(out / "flags.csv", fd_report.CSV_COLUMNS, rows)
    fd_report.write_csv(out / "excluded.csv", fd_report.EXCLUDED_COLUMNS, left)
    other = fd_report.make_other_rows(ctx)
    fd_report.write_csv(out / "others.csv", fd_report.OTHER_COLUMNS, other)
    fd_report.write_md(out / "flags.md", ctx, results, rows, left, dict(lines=lines))
    for w in warnings:
        print("warning: " + w, file=sys.stderr)
    print("counts: " + ", ".join("%s %d" % (k, v) for k, v in counts.items()))
    print("named %d of %d classified flags; wrote flags.csv, excluded.csv, others.csv (%d entries of the other containers) and flags.md to %s" % (
        sum(1 for r in rows if r["named"] == "yes"), len(rows), len(other), out))
    if not args.no_cache:
        key = fd_cache.make_key(romfs.raw(romfs.glob_one(fd_classify.GAMEDATA_FOLDER, fd_classify.GAMEDATA_NAME)), text.encode())
        meta = dict(counts=counts, stamp="%08x" % scenes.stamp(), source=args.source or fd_source.SOURCE, rev=None if args.source else args.rev)
        path = fd_cache.write(fd_cache.state_dir(args.state), key, rows, left, meta)
        print("cache for the log annotator: %s" % path)
    return 0 if ok else 1


def lookup(args):
    doc = fd_cache.load(fd_cache.find(args.state, args.cache))
    for text in args.hash:
        key = "%08x" % int(text, 16)
        for e in doc["flags"].get(key, []):
            print("%s  %s  %s  %s  default %s  %s" % (key, e["n"] or "(no name)", e["k"], e["c"] or "left out: " + e["r"], e["d"],
                                                       e["f"] + (", " + e["m"] if e["m"] else "")))
        if key not in doc["flags"]:
            print("%s  not a Bool or Int flag of this game's list" % key)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="classify, name and write the reports and the cache")
    b.add_argument("--romfs", required=True, help="the player's own RomFS folder")
    b.add_argument("--source", help="host/oot_coop.c as a file")
    b.add_argument("--repo", help="an LS clone: the source is read with `git show REV:host/oot_coop.c`")
    b.add_argument("--rev", default="HEAD")
    b.add_argument("--out", required=True, help="where flags.csv, excluded.csv and flags.md go (outside the workbench checkout)")
    b.add_argument("--names", action="append", default=[], help="a file of names to try, one a line (# comments); each is checked by hash")
    b.add_argument("--sweep", action="append", default=[], help="a folder of text that quotes names (the LS source, your notes)")
    b.add_argument("--compare-log", action="append", default=[], help="a game log: its counts and story-scene list must equal the result")
    b.add_argument("--state", help="the private folder for the cache (default: see fd_cache.py)")
    b.add_argument("--no-cache", action="store_true")
    h = sub.add_parser("hash", help="the game's hash of names")
    h.add_argument("name", nargs="+")
    k = sub.add_parser("lookup", help="flags by hash, from the cache")
    k.add_argument("hash", nargs="+")
    k.add_argument("--cache")
    k.add_argument("--state")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "hash":
            for name in a.name:
                print("%08x  %s" % (fd_romfs.murmur3(name), name))
            return 0
        return build(a) if a.cmd == "build" else lookup(a)
    except (ValueError, OSError, RuntimeError) as error:
        print("flagdata: %s" % error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
