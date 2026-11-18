#!/usr/bin/env python3
"""The co-op log annotator (flagdata/coop_log.py) on a made-up game and a made-up log. The table it reads is built by flagdata.py from the
made-up game files of tests/flagdata_fixture.py, into a temporary state folder."""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "flagdata"))
sys.path.insert(0, str(ROOT / "tests"))
import coop_log  # noqa: E402
import flagdata  # noqa: E402
import flagdata_fixture as F  # noqa: E402

h = F.h


def run(module, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = module.main(argv)
    return code, out.getvalue(), err.getvalue()


def x(name):
    return "%08x" % h(name)


class Annotator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="coop-log-test-"))
        F.write_romfs(cls.tmp / "romfs")
        source = F.write_source(cls.tmp)
        code, _, err = run(flagdata, ["build", "--romfs", str(cls.tmp / "romfs"), "--source", str(source), "--out", str(cls.tmp / "out"),
                                      "--state", str(cls.tmp / "state")])
        assert code == 0, err
        cls.state = str(cls.tmp / "state")
        cls.log = cls.tmp / "game.log"
        cls.log.write_text("\n".join([
            "[hos host] coop: sync: caught up with the room",
            "[hos host] coop: sync: sent progress %s = 1 to all" % x("Story_Alpha"),
            "[hos host] coop: sync: received progress %s = 1 from member 2" % x("HavePlayedEvent.Intro"),
            "[hos Presentation Thread] coop: sync: applied progress %s = 1" % x("Story_Alpha"),
            "[hos Presentation Thread] coop: sync: applied items %s = 1" % x("Markers.Sword"),
            "[hos Presentation Thread] coop: sync: held progress %s for its boss's end set" % x("HavePlayedEvent.BossDeath"),
            "[hos host] coop: sync: sent keys %s of member 1: base 0 gain 1 spend 0 to all" % x("Dungeons.AlphaCave.Keys"),
            "[hos host] coop: sync: pool keys %s joined at 2, the pool holds 3" % x("Dungeons.AlphaCave.Keys"),
            "[hos host] coop: sync: the game shows ammo %s = 5 (its getter agrees)" % x("Stock.Bomb.Count"),
            "[hos host] coop: test: set Bool %s = 1 at frame 40" % x("Standing_Flag"),
            "[hos host] coop: test: Int %s reads 5 in the table" % x("Misc_Counter"),
            "[hos host] coop: sync: flag %s reads 0 in the table (entry 0x1) and 0 (found 1) by the game's getter" % x("Heart_Flag"),
            "[hos host] coop: sync: refused from member 2: not a flag of this table %s (3 so far)" % "deadbeef",
            "[hos host] coop: boss: Gohma was beaten in the room, but %s of its end set is not in this game's data" % x("HavePlayedEvent.BossIn"),
            "[hos host] coop: relay: room %s created" % x("Story_Alpha"),    # (a room id that looks like a hash: not a flag)
            "[hos host] coop: sync: applied progress %s = 1" % x("ZoneA_RoomA_Cleared"),
            "",
        ]), encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        __import__("shutil").rmtree(cls.tmp, ignore_errors=True)

    def annotate(self, *extra):
        return run(coop_log, ["--state", self.state, *extra, str(self.log)])

    def test_each_flag_line_gets_name_family_category_and_mode(self):
        code, out, err = self.annotate()
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertEqual(len(lines), 14)    # the lines that name no flag, the room id included, are not printed
        self.assertIn("sent progress %s = 1 to all  -> Story_Alpha  [flat flags (no group)]  progress, shared" % x("Story_Alpha"), out)
        self.assertIn("-> HavePlayedEvent.Intro  [HavePlayedEvent.*]  progress (story scene), own (story scenes: each player)", out)
        self.assertIn("applied items %s = 1  -> Markers.Sword  [items: first-get marker]  items, shared" % x("Markers.Sword"), out)
        self.assertIn("-> Dungeons.AlphaCave.Keys  [keys]  keys, pool", out)
        self.assertIn("the game shows ammo %s = 5 (its getter agrees)  -> Stock.Bomb.Count  [ammo]  ammo, own" % x("Stock.Bomb.Count"), out)
        self.assertIn("-> Standing_Flag  [-]  left out: unshared list", out)
        self.assertIn("-> Misc_Counter  [-]  left out: an Int that is in no group", out)
        self.assertIn("-> Heart_Flag  [-]  left out: heart reward", out)
        self.assertIn("-> HavePlayedEvent.BossIn  [-]  left out: a boss fight's own flag", out)
        self.assertIn("refused from member 2: not a flag of this table deadbeef (3 so far)  -> not a Bool or Int flag of the cached table", out)
        self.assertIn("applied progress %s = 1  -> (no name)  [unnamed, in no group]  progress, shared" % x("ZoneA_RoomA_Cleared"), out)
        self.assertNotIn("caught up", out)
        self.assertNotIn("relay: room", out)
        self.assertIn("14 annotated lines, 14 flag references, 1 distinct hashes not in the table", err)

    def test_all_prints_the_other_lines_unchanged(self):
        _, out, _ = self.annotate("--all")
        self.assertIn("[hos host] coop: sync: caught up with the room\n", out)
        self.assertIn("relay: room %s created\n" % x("Story_Alpha"), out)

    def test_only_selects_verbs(self):
        _, out, err = self.annotate("--only", "applied,held")
        self.assertEqual(len(out.splitlines()), 4)
        self.assertIn("4 annotated lines", err)
        self.assertNotIn("sent progress", out)

    def test_summary_groups_each_verb_by_category_and_family(self):
        code, out, _ = self.annotate("--summary", "--names", "2")
        self.assertEqual(code, 0)
        self.assertIn("applied: 3 lines, 3 distinct flags", out)
        self.assertIn("held: 1 lines, 1 distinct flags", out)
        self.assertIn("    unnamed, in no group", out)
        self.assertIn("flat flags (no group)", out)
        self.assertIn("  items\n    items: first-get marker", out)
        self.assertIn("e.g. Markers.Sword", out)
        self.assertIn("received: 1 lines", out)
        self.assertIn("  progress (story scene)\n    HavePlayedEvent.*", out)       # a story scene is a group of its own
        self.assertIn("  left out\n", out)
        self.assertLess(out.index("applied:"), out.index("held:"))
        self.assertLess(out.index("held:"), out.index("received:"))
        _, none, _ = self.annotate("--summary", "--names", "0")
        self.assertNotIn("e.g.", none)

    def test_a_missing_table_says_how_to_make_it(self):
        code, _, err = run(coop_log, ["--state", str(self.tmp / "no-state"), str(self.log)])
        self.assertEqual(code, 2)
        self.assertIn("flagdata.py build", err)

    def test_the_cache_can_be_named_and_logs_can_be_piped(self):
        cache = next(Path(self.state).glob("table-*.json"))
        code, out, _ = run(coop_log, ["--cache", str(cache), str(self.log)])
        self.assertEqual(code, 0)
        self.assertIn("Story_Alpha", out)
        stdin = sys.stdin
        try:
            sys.stdin = io.StringIO("[hos host] coop: sync: applied progress %s = 1\n" % x("Story_Alpha"))
            code, out, _ = run(coop_log, ["--state", self.state, "-"])
        finally:
            sys.stdin = stdin
        self.assertIn("-> Story_Alpha", out)

    def test_references_by_pattern(self):
        r = coop_log.references
        a = x("Story_Alpha")
        self.assertEqual(r("coop: sync: sent progress %s = 1 to member 2" % a), [("sent", "progress", a, "")])
        self.assertEqual(r("coop: sync: received songs %s = 1 from member 2" % a), [("received", "songs", a, "")])
        self.assertEqual(r("coop: sync: the game shows items %s = 1" % a), [("shows", "items", a, "")])
        self.assertEqual(r("coop: test: set Int %s = 3 at frame 2" % a), [("test set", "", a, "Int")])
        self.assertEqual(r("coop: test: Bool %s reads 1 in the table and 1 (found 1) by the game's getter" % a), [("test read", "", a, "Bool")])
        self.assertEqual(r("coop: test: no Bool or Int flag %s" % a), [("test read", "", a, "")])
        self.assertEqual(r("coop: sync: held progress %s for its boss's end set" % a), [("held", "progress", a, "")])
        self.assertEqual(r("coop: relay: room %s created" % a), [])
        self.assertEqual(r("coop: sync: sent progress xyz = 1"), [])


if __name__ == "__main__":
    unittest.main()
