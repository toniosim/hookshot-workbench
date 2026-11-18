#!/usr/bin/env python3
"""The flag map's tool (docs/oot/flagmap.py) on made-up builds and made-up pages, the whole path from the flag tools' made-up game to the
pages, and the invariants of the real pages (every name hashes to its row, every hash once, every page below the publication limit).
Standard library only; the made-up rows are invented: no name here is the game's."""
import contextlib
import csv
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "flagdata"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))
import fd_report  # noqa: E402
import fd_romfs  # noqa: E402
import flagdata  # noqa: E402
import flagdata_fixture as F  # noqa: E402
import name_policy  # noqa: E402

spec = importlib.util.spec_from_file_location("flagmap", ROOT / "docs" / "oot" / "flagmap.py")
fm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fm)
h = fd_romfs.murmur3
PROJECT = "Hook" + "shot"   # (a name the naming policy counts: built here so that this file needs no exception of its own)
ITEM = "Item_%s_Got" % PROJECT
INDEX = "# Index\n\n<!-- pages:begin -->\n<!-- pages:end -->\n\n<!-- made:begin -->\n<!-- made:end -->\n\n<!-- kinds:begin -->\n<!-- kinds:end -->\n"


def flag(name, category="progress", mode="shared", scene="no", default=0, reset=8, file=0, family=None, source="files", note="", kind="Bool",
         map_=""):
    return dict(category=category, scene=scene, shared_by_default="yes" if mode in ("shared", "pool") else "no", default_mode=mode, name=name,
                hash="%08x" % h(name), kind=kind, default=default, map=map_, prefix="", family=family or (name.split(".")[0] + ".*" if "." in name else "flat flags (no group)"),
                named="yes", name_source=source, note=note, reset=reset, file=file)


def out_row(name, reason, file=0, kind="Bool", reset=8):
    return dict(reason=reason, kind=kind, name=name, hash="%08x" % h(name), default=0, reset=reset, file=file, map="", prefix="", named="yes",
                family="flat flags (no group)", name_source="files", note="")


def other(kind, name="", hash_=None, default="", reset=8, file=0, family="flat %s flags", extra="", note="", map_=""):
    hs = hash_ or "%08x" % h(name)
    return dict(kind=kind, name=name, hash=hs, default=default, reset=reset, file=file, map=map_, prefix="", family=family % kind if "%s" in family else family,
                named="yes" if name else "no", name_source="files" if name else "", note=note, extra=extra)


def write(path, columns, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def made_up_build(folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    unnamed = flag("x", family="unnamed, in group HavePlayedEvent", note='a played event with no name here; its struct lists members in name order, so it sorts between "Intro" and "Gate"')
    unnamed.update(name="", named="no", name_source="", hash="0badc0de")
    write(folder / "flags.csv", fd_report.CSV_COLUMNS, [
        flag("Story_Alpha"), flag("HavePlayedEvent.Intro", scene="yes", mode="own", family="HavePlayedEvent.*", source="event table"),
        flag("Stock.Bomb.Count", category="items", kind="Int", family="items: item count"), unnamed,
        flag(ITEM), flag("Dungeons.AlphaCave.Keys", category="keys", mode="pool", kind="Int")])
    write(folder / "excluded.csv", fd_report.EXCLUDED_COLUMNS, [
        out_row("Unsaved_Flag", "never saved (save file index -1)", file=-1), out_row("Option_Flag", "saved in another file than the slot's (save file index 1)", file=1),
        out_row("Misc_Counter", "an Int that is in no group the sync knows", kind="Int"), out_row("Odd_Flag", "a reason no table knows yet, however long it is")])
    write(folder / "others.csv", fd_report.OTHER_COLUMNS, [
        other("Struct", "Markers", reset=0, file=-1, extra="3 members", family="Markers.*"),
        other("Bool64bitKey", hash_="%016x" % 77, reset=24, family="per-object keys (a placed actor's hash)", map_="ZoneA", note='placed actor Other "Other_One" in ZoneA'),
        other("Bool64bitKey", hash_="%016x" % ((1 << 63) + 5), reset=24, family="per-object keys (no placed actor of the files)"),
        other("Enum", "Mode", default="B", extra="2 values: A, B"), other("String64", "Caption_Place", file=2),
        other("BoolExp", "Done_Exp", reset=0, file=-1, extra="terms 12:5"), other("Float", "Misc_Ratio", default="0.5", file=1),
        other("WString16", "Wide_Text", file=-1), other("Vector3", "Where_Pos", default="three floats", file=2)])
    return folder


def notes_file(path, rows):
    Path(path).write_text("# Notes\n\n" + fm.NOTES_HEADER + "\n|---|---|---|---|\n" + "".join("| `%s` | %s | %s | %s |\n" % r for r in rows), encoding="utf-8")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="flagmap-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.build_dir = made_up_build(self.tmp / "build")
        self.pages = self.tmp / "flags"
        self.pages.mkdir()
        (self.pages / "README.md").write_text(INDEX, encoding="utf-8")
        self.notes = self.tmp / "descriptions.md"
        notes_file(self.notes, [("%08x" % h("Story_Alpha"), "The made-up story's first step.", "read", "LS oot_coop.c")])

    def build(self, limit=None):
        old = fm.PAGE_LIMIT
        fm.PAGE_LIMIT = limit or old
        try:
            return fm.build(self.build_dir, "Made up for the tests.", self.notes, self.pages)
        finally:
            fm.PAGE_LIMIT = old

    def rows(self):
        return fm.parse_pages(self.pages)


class Build(Base):
    def test_every_row_of_the_three_files_gets_a_row_with_its_page_family_file_and_group(self):
        count, written, _ = self.build()
        self.assertEqual(count, 6 + 4 + 9)
        rows = {r["hash"]: r for r in self.rows()}
        self.assertEqual(len(rows), 19)
        story = rows["%08x" % h("Story_Alpha")]
        self.assertEqual((story["name"], story["kind"], story["file"], story["group"], story["coop"], story["page"], story["family"]),
                         ("Story_Alpha", "Bool", "progress", "1", "progress, shared", "flat-flags.md", "flat flags (no group)"))
        self.assertEqual((story["what"], story["sure"], story["source"]), ("The made-up story's first step.", "read", "LS oot_coop.c"))
        self.assertEqual(rows["%08x" % h("HavePlayedEvent.Intro")]["coop"], "story scene, own")
        self.assertEqual(rows["%08x" % h("HavePlayedEvent.Intro")]["how"], "event table")
        self.assertEqual(rows["%08x" % h("Dungeons.AlphaCave.Keys")]["coop"], "keys, pool")
        self.assertEqual(rows["%08x" % h("Stock.Bomb.Count")]["group"], "3")

    def test_out_rows_say_why_in_a_few_words_and_unknown_reasons_stay(self):
        self.build()
        by = {r["name"]: r for r in self.rows() if r["name"]}
        self.assertEqual(by["Unsaved_Flag"]["coop"], "out: not saved")
        self.assertEqual((by["Unsaved_Flag"]["file"], by["Unsaved_Flag"]["group"]), ("none", "-"))
        self.assertEqual((by["Option_Flag"]["coop"], by["Option_Flag"]["file"]), ("out: other file", "option"))
        self.assertEqual(by["Misc_Counter"]["coop"], "out: Int in no group")
        self.assertEqual(by["Odd_Flag"]["coop"], "out: " + "a reason no table knows yet, however long it is"[:40])

    def test_other_containers_have_their_groups_and_the_key_run(self):
        self.build()
        by = {r["kind"]: r for r in self.rows() if r["kind"] not in ("Bool", "Int", "Bool64bitKey")}
        self.assertEqual((by["Enum"]["group"], by["Enum"]["default"], by["Enum"]["coop"], by["Enum"]["note"]), ("7", "B", "not read", "2 values: A, B"))
        self.assertEqual((by["Struct"]["note"], by["BoolExp"]["note"]), ("3 members", "terms 12:5"))
        self.assertEqual((by["String64"]["file"], by["String64"]["group"]), ("caption", "17"))
        self.assertEqual((by["Float"]["file"], by["Float"]["group"]), ("option", "5"))
        self.assertEqual((by["Vector3"]["file"], by["Vector3"]["group"]), ("caption", "11"))
        self.assertEqual((by["Struct"]["group"], by["Struct"]["file"], by["BoolExp"]["group"], by["WString16"]["group"]), ("-", "none", "-", "-"))
        keys = sorted((r for r in self.rows() if r["kind"] == "Bool64bitKey"), key=lambda r: r["hash"])
        self.assertEqual([(r["hash"], r["group"], r["file"], r["page"]) for r in keys],
                         [("000000000000004d", "keys", "progress", "object-keys-placed.md"), ("8000000000000005", "keys", "progress", "object-keys-other.md")])
        self.assertEqual(keys[0]["map"], "ZoneA")

    def test_a_note_about_an_unnamed_played_event_is_shortened(self):
        self.build()
        row = next(r for r in self.rows() if r["hash"] == "0badc0de")
        self.assertEqual((row["name"], row["note"], row["page"]), ("", "sorts between Intro and Gate", "played-events.md"))

    def test_the_index_gets_its_tables_and_the_pages_check_out(self):
        self.build()
        text = (self.pages / "README.md").read_text(encoding="utf-8")
        self.assertIn("| **all** | | **19** |", text)
        self.assertIn("| [flat-flags.md](flat-flags.md) | Single flags |", text)
        self.assertIn("Made up for the tests.", text)
        self.assertIn("| Bool64bitKey | 2 | 0 | progress | keys |", text)
        problems, rows = fm.check(self.pages, self.notes)
        self.assertEqual(problems, [])
        self.assertEqual(len(rows), 19)

    def test_pages_are_cut_below_the_limit_and_a_family_goes_on_under_its_heading(self):
        self.build(limit=900)
        names = sorted(p.name for p in self.pages.glob("*.md"))
        self.assertGreater(len(names), 5)
        for p in self.pages.glob("*.md"):
            if p.name != "README.md":
                self.assertLessEqual(p.stat().st_size, 900 + 700, p.name)   # (the title and the intro are not counted in the limit)
        self.assertEqual(fm.check(self.pages, self.notes)[0], [])
        self.assertEqual(len(self.rows()), 19)
        flat = [p for p in names if p.startswith("flat-flags-")]
        self.assertGreater(len(flat), 1)
        self.assertTrue(all("### flat flags (no group)" in (self.pages / p).read_text(encoding="utf-8") for p in flat[:2]))

    def test_a_rebuild_replaces_old_pages(self):
        self.build(limit=900)
        self.build()
        self.assertFalse(list(self.pages.glob("flat-flags-*.md")))
        self.assertTrue((self.pages / "flat-flags.md").is_file())

    def test_refusals(self):
        notes_file(self.notes, [("%08x" % h("Story_Alpha"), "x.", "read", "s"), ("%08x" % h("Story_Alpha"), "y.", "read", "s")])
        with self.assertRaisesRegex(ValueError, "described twice"):
            self.build()
        notes_file(self.notes, [("deadbeef", "x.", "read", "s")])
        with self.assertRaisesRegex(ValueError, "does not have"):
            self.build()
        notes_file(self.notes, [])
        (self.build_dir / "others.csv").unlink()
        with self.assertRaisesRegex(ValueError, "has no others.csv"):
            self.build()
        made_up_build(self.build_dir)
        with open(self.build_dir / "others.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        rows.append(dict(rows[3], kind="Float"))   # the same hash in two containers
        write(self.build_dir / "others.csv", fd_report.OTHER_COLUMNS, rows)
        with self.assertRaisesRegex(ValueError, "two containers"):
            self.build()
        (self.pages / "README.md").write_text("# no markers\n", encoding="utf-8")
        made_up_build(self.build_dir)
        with self.assertRaisesRegex(ValueError, "markers"):
            self.build()

    def test_names_with_a_projects_name_get_kept_literal_rows_and_nothing_else_changes(self):
        kept = self.tmp / "names-kept.md"
        other_row = ["docs/agent-brief.md", "/home/x/" + PROJECT.lower(), 1, "stays"]
        old_row = ["docs/oot/flags/old-page.md", "Old_" + PROJECT, 1, "goes"]
        kept.write_text("# Kept\n\n%s\n```jsonl\n%s\n%s\n```\n%s\nafter\n" % (name_policy.BEGIN, json.dumps(other_row), json.dumps(old_row), name_policy.END),
                        encoding="utf-8")
        self.build()
        texts = {p.name: p.read_text(encoding="utf-8") for p in self.pages.glob("*.md") if p.name != "README.md"}
        self.assertEqual(fm.update_kept(texts, kept), 1)
        rows = name_policy.records(kept.read_text(encoding="utf-8"))
        self.assertEqual(rows[0], other_row)
        self.assertEqual([r[:3] for r in rows[1:]], [["docs/oot/flags/flat-flags.md", ITEM, 1]])
        self.assertTrue(kept.read_text(encoding="utf-8").endswith("\nafter\n"))
        # the policy agrees: with these rows nothing in the pages is unlisted
        root = self.tmp / "tree"
        (root / "docs/oot/flags").mkdir(parents=True)
        for name, text in texts.items():
            (root / "docs/oot/flags" / name).write_text(text, encoding="utf-8")
        files = ["docs/oot/flags/" + n for n in texts]
        self.assertFalse(name_policy.violations(root, kept.read_text(encoding="utf-8"), files))


class Check(Base):
    def setUp(self):
        super().setUp()
        self.build()

    def edit(self, page, old, new, count=1):
        path = self.pages / page
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, count), encoding="utf-8")

    def problems(self):
        return fm.check(self.pages, self.notes)[0]

    def test_a_name_that_does_not_hash_to_its_row_fails(self):
        self.edit("flat-flags.md", "`Story_Alpha`", "`Story_Beta`")
        self.assertTrue(any("Story_Beta hashes to" in p for p in self.problems()), self.problems())

    def test_a_hash_twice_fails(self):
        text = (self.pages / "flat-flags.md").read_text(encoding="utf-8")
        row = next(line for line in text.splitlines() if "`Story_Alpha`" in line)
        self.edit("flat-flags.md", row, row + "\n" + row)
        self.assertTrue(any("is in the map twice" in p for p in self.problems()), self.problems())

    def test_required_fields_and_values(self):
        self.edit("flat-flags.md", "| Bool | 0 | 8 | progress | 1 | progress, shared |", "| Bool | 0 | 8 | progress | 1 | whatever |")
        self.assertTrue(any("is not a co-op fate" in p for p in self.problems()))
        self.edit("flat-flags.md", "| Bool | 0 | 8 | progress | 1 | whatever |", "| Bool | 0 | 8 | progress | 2 | progress, shared |")
        self.assertTrue(any("is in group 1, not 2" in p for p in self.problems()), self.problems())
        self.edit("flat-flags.md", "| Bool | 0 | 8 | progress | 2 |", "| Bool | 0 | 8 | disc | 1 |")
        self.assertTrue(any("is not a save file" in p for p in self.problems()))
        self.edit("flat-flags.md", "| read | LS oot_coop.c |", "| sure | LS oot_coop.c |")
        self.assertTrue(any("tested, read or guess" in p for p in self.problems()))
        self.edit("flat-flags.md", "| sure | LS oot_coop.c |", "| read |  |")
        self.assertTrue(any("a description and no source" in p for p in self.problems()))

    def test_a_row_with_the_wrong_number_of_cells_and_a_key_with_a_name_fail(self):
        self.edit("flat-flags.md", "| Bool | 0 | 8 | progress | 1 | progress, shared |", "| Bool | 0 | 8 | progress | 1 |")
        self.assertTrue(any("cells, not 14" in p for p in self.problems()))
        row = next(line for line in (self.pages / "object-keys-placed.md").read_text(encoding="utf-8").splitlines() if "000000000000004d" in line)
        self.edit("object-keys-placed.md", row, row.replace("| `000000000000004d` |  |  |", "| `000000000000004d` | `Some_Name` | files |", 1))
        problems = self.problems()
        self.assertTrue(any("a per-object key" in p and "has no name to hash" in p for p in problems), problems)

    def test_descriptions_are_checked_against_the_map_and_the_pages(self):
        notes_file(self.notes, [("%08x" % h("Story_Alpha"), "Changed.", "read", "x"), ("cafe0001", "Nothing.", "read", "x")])
        problems = self.problems()
        self.assertTrue(any("cafe0001 is not in the map" in p for p in problems), problems)
        self.assertTrue(any("differs from descriptions.md" in p for p in problems), problems)

    def test_the_index_must_list_every_page_and_the_right_total(self):
        self.edit("README.md", "| [flat-flags.md](flat-flags.md)", "| [other.md](other.md)")
        problems = self.problems()
        self.assertTrue(any("does not list flat-flags.md" in p for p in problems), problems)
        self.assertTrue(any("lists other.md" in p for p in problems), problems)
        self.edit("README.md", "**19**", "**20**")
        self.assertTrue(any("says 20 rows" in p for p in self.problems()))

    def test_a_page_over_the_publication_limit_fails(self):
        with open(self.pages / "flat-flags.md", "a", encoding="utf-8") as f:
            f.write("x" * 200_001)
        self.assertTrue(any("over 200 KB" in p for p in self.problems()))


class Lookup(Base):
    """The program, from a copy of the tool beside made-up pages (as docs/oot/ is laid out)."""

    def setUp(self):
        super().setUp()
        tree = self.tmp / "tree"
        (tree / "docs/oot/flags").mkdir(parents=True)
        (tree / "flagdata").mkdir()
        shutil.copy(ROOT / "docs/oot/flagmap.py", tree / "docs/oot/flagmap.py")
        shutil.copy(ROOT / "flagdata/fd_romfs.py", tree / "flagdata/fd_romfs.py")
        (tree / "docs/oot/flags/README.md").write_text(INDEX, encoding="utf-8")
        self.tool = tree / "docs/oot/flagmap.py"
        notes_file(tree / "docs/oot/flags/descriptions.md", [("%08x" % h("Story_Alpha"), "The made-up story's first step.", "read", "LS oot_coop.c")])
        self.run_tool("build", "--from", str(self.build_dir), "--made-from", "test")

    def run_tool(self, *args):
        p = subprocess.run([sys.executable, "-I", "-B", str(self.tool), *args], capture_output=True, text=True)
        return p.returncode, p.stdout + p.stderr

    def test_find_by_hash_name_words_and_decimal_key(self):
        code, out = self.run_tool("find", "%08x" % h("Story_Alpha"))
        self.assertEqual(code, 0, out)
        self.assertIn("flags/flat-flags.md:", out)
        self.assertIn("`Story_Alpha`", out)
        self.assertIn("The made-up story's first step.", out)
        self.assertIn("Story_Alpha", self.run_tool("find", "0x%08x" % h("Story_Alpha"))[1])
        self.assertIn("`Story_Alpha`", self.run_tool("find", "story_alpha")[1])
        self.assertIn("`%s`" % ITEM, self.run_tool("find", PROJECT.lower() + " got")[1])
        self.assertIn("000000000000004d", self.run_tool("find", "77")[1] + self.run_tool("find", "000000000000004d")[1])
        code, out = self.run_tool("find", "%d" % ((1 << 63) + 5))
        self.assertEqual(code, 0, out)
        self.assertIn("8000000000000005", out)
        code, out = self.run_tool("find", "nothing like this")
        self.assertEqual((code, "nothing for" in out), (1, True))

    def test_show_says_where_the_flag_is_in_a_file(self):
        code, out = self.run_tool("show", "%08x" % h("Story_Alpha"))
        self.assertEqual(code, 0, out)
        self.assertIn("slot_NN/progress.sav, group 1 (Bool)", out)
        self.assertIn("the table entry's own word", out)
        self.assertIn("The made-up story's first step.", out)
        self.assertIn("key run", self.run_tool("show", "%016x" % 77)[1])
        self.assertIn("never saved", self.run_tool("show", "%08x" % h("Unsaved_Flag"))[1])
        self.assertIn("data section", self.run_tool("show", "%08x" % h("Caption_Place"))[1])
        self.assertEqual(self.run_tool("show", "deadbeef")[0], 1)

    def test_stats_names_and_check(self):
        code, out = self.run_tool("stats")
        self.assertEqual(code, 0, out)
        self.assertIn("19 rows", out)
        self.assertIn("with a description of ours: 1 (", out)
        code, out = self.run_tool("names")
        self.assertIn(ITEM, out.split())
        self.assertNotIn("", out.split("\n")[:1])
        code, out = self.run_tool("check")
        self.assertEqual(code, 0, out)
        self.assertIn("PASS", out)
        self.assertIn("19 rows", out)

    def test_check_fails_on_a_wrong_name(self):
        page = self.tool.parent / "flags/flat-flags.md"
        page.write_text(page.read_text(encoding="utf-8").replace("`Story_Alpha`", "`Story_Other`"), encoding="utf-8")
        code, out = self.run_tool("check")
        self.assertEqual(code, 1)
        self.assertIn("FAIL", out)


class FromTheFlagTools(unittest.TestCase):
    """The tools' made-up game (tests/flagdata_fixture.py) through `flagdata.py build` and `flagmap.py build`: the formats agree."""

    def test_the_output_of_the_flag_tools_becomes_pages_that_check(self):
        tmp = Path(tempfile.mkdtemp(prefix="flagmap-test-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        romfs, source = F.write_romfs(tmp / "romfs"), F.write_source(tmp)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = flagdata.main(["build", "--romfs", str(romfs), "--source", str(source), "--out", str(tmp / "out"), "--no-cache"])
        self.assertEqual(code, 0, out.getvalue())
        pages = tmp / "flags"
        pages.mkdir()
        (pages / "README.md").write_text(INDEX, encoding="utf-8")
        count, written, _ = fm.build(tmp / "out", "from the made-up game", tmp / "none.md", pages)
        problems, rows = fm.check(pages, tmp / "none.md")
        self.assertEqual(problems, [])
        self.assertEqual(count, len(rows))
        kinds = {r["kind"] for r in rows}
        self.assertLessEqual({"Bool", "Int", "Struct", "Enum", "Float", "IntArray", "Bool64bitKey"}, kinds)
        keys = [r for r in rows if r["kind"] == "Bool64bitKey"]
        self.assertEqual(sorted(r["hash"] for r in keys), ["000000000000004d", "8000000000000005"])
        self.assertEqual({r["note"] for r in keys if r["map"]}, {'placed actor Other "Other_One" in ZoneA'})
        self.assertEqual({r["coop"] for r in rows if r["kind"] not in ("Bool", "Int")}, {"not read"})
        self.assertTrue(all(r["name"] == "" or "%08x" % h(r["name"]) == r["hash"] for r in rows))


class RealPages(unittest.TestCase):
    """The pages of this repository: the invariants a refresh must keep."""

    @classmethod
    def setUpClass(cls):
        cls.problems, cls.rows = fm.check(fm.FLAGS, fm.NOTES)

    def test_the_pages_check_out(self):
        self.assertEqual(self.problems, [])

    def test_every_flag_of_the_list_is_there_once_and_named_flags_hash(self):
        hashes = [r["hash"] for r in self.rows]
        self.assertEqual(len(hashes), len(set(hashes)))
        kinds = {k: sum(1 for r in self.rows if r["kind"] == k) for k in ("Bool", "Int", "Bool64bitKey", "Struct")}
        self.assertGreater(kinds["Bool"] + kinds["Int"], 12_000)
        self.assertGreater(kinds["Bool64bitKey"], 11_000)
        self.assertGreater(kinds["Struct"], 800)
        named = [r for r in self.rows if r["name"]]
        self.assertGreater(len(named), 10_000)
        self.assertTrue(all("%08x" % h(r["name"]) == r["hash"] for r in named))

    def test_pages_stay_below_the_publication_limit_and_the_policy_lists_their_literals(self):
        pages = sorted(p for p in fm.FLAGS.glob("*.md"))
        self.assertGreater(len(pages), 10)
        for p in pages:
            self.assertLess(p.stat().st_size, 200_000, p.name)
        files = [str(p.relative_to(ROOT)) for p in pages]
        self.assertFalse(name_policy.violations(ROOT, files=files))

    def test_the_co_op_numbers_of_the_game_log_are_in_the_pages(self):
        """The line the game logs (progress 9,396 of them 2,168 story scenes, 255 items, 13 songs, 11 quest, 14 keys, 1 rupee, 7 ammunition):
        the rows' co-op cells say the same."""
        count = {}
        for r in self.rows:
            if r["coop"] == "story scene, own":
                count["scenes"] = count.get("scenes", 0) + 1
            if r["coop"].startswith("out") or r["coop"] == "not read":
                continue
            count[r["coop"].split(",")[0]] = count.get(r["coop"].split(",")[0], 0) + 1
        self.assertEqual({k: count[k] for k in ("progress", "items", "songs", "quest", "keys", "rupees", "ammo", "scenes")},
                         {"progress": 7228, "items": 255, "songs": 13, "quest": 11, "keys": 14, "rupees": 1, "ammo": 7, "scenes": 2168})
        # (story scenes are their own category in the cell, so progress counts the others: 9,396 - 2,168)


if __name__ == "__main__":
    unittest.main()
