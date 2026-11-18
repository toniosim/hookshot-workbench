#!/usr/bin/env python3
"""The flag tools (flagdata/) on a made-up game: formats, the classifier's lists, the story-scene list, name recovery, the reports and
the cache. No game, no game file and no data file of the game's is used or kept: everything is written to a temporary folder here."""
import contextlib
import io
import os
import stat
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "flagdata"))
sys.path.insert(0, str(ROOT / "tests"))
import fd_cache  # noqa: E402
import fd_classify  # noqa: E402
import fd_names  # noqa: E402
import fd_report  # noqa: E402
import fd_romfs  # noqa: E402
import fd_scenes  # noqa: E402
import fd_source  # noqa: E402
import flagdata  # noqa: E402
import flagdata_fixture as F  # noqa: E402

h = fd_romfs.murmur3


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = flagdata.main(argv)
    return code, out.getvalue(), err.getvalue()


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="flagdata-test-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.romfs = F.write_romfs(self.tmp / "romfs")
        self.source = F.write_source(self.tmp)

    def pipeline(self, names=(), sweep=(), source=None):
        lists = fd_source.parse((source or self.source).read_text())
        romfs = fd_romfs.Romfs(self.romfs)
        tables = fd_classify.load_tables(romfs)
        collector = fd_names.Collector()
        scenes = fd_scenes.scan(romfs, fd_source.scan_settings(F.SCENES_SOURCE), collector.add_file)
        classifier = fd_classify.Classifier(tables, lists, scenes)
        results = classifier.all()
        book = fd_names.recover(tables, scenes, collector, "HavePlayedEvent.", names, sweep, lists.comments)
        ctx = fd_report.Context(tables, classifier.groups, scenes, lists, book)
        return dict(lists=lists, tables=tables, scenes=scenes, classifier=classifier, results=results, book=book, ctx=ctx)

    def build(self, *extra):
        return run(["build", "--romfs", str(self.romfs), "--source", str(self.source), "--out", str(self.tmp / "out"),
                    "--state", str(self.tmp / "state"), *extra])


class Formats(unittest.TestCase):
    def test_the_hash_is_murmur3_seed_0(self):
        self.assertEqual(h(""), 0)
        self.assertEqual(h("test"), 0xBA6BD213)            # a published MurmurHash3_x86_32 value
        self.assertEqual(h("SelectedCaptionIndex"), 0x1A49C4F6)   # the name docs/oot/game-data.md checks the hash with
        self.assertEqual(h(b"abc"), h("abc"))

    def test_zstd_frame_header_names_its_dictionary(self):
        magic = b"\x28\xb5\x2f\xfd"
        self.assertEqual(fd_romfs.frame_dict_id(magic + bytes([0x03, 0x58]) + (1234).to_bytes(4, "little")), 1234)
        self.assertEqual(fd_romfs.frame_dict_id(magic + bytes([0x21]) + (7).to_bytes(1, "little")), 7)   # single segment: no window byte
        self.assertEqual(fd_romfs.frame_dict_id(magic + bytes([0x20, 0x01])), 0)
        with self.assertRaises(ValueError):
            fd_romfs.frame_dict_id(b"not zstd")
        self.assertEqual(fd_romfs.dict_id(b"\x37\xa4\x30\xec" + (99).to_bytes(4, "little")), 99)

    def test_byml_round_trip_in_both_byte_orders(self):
        tree = dict(Name="x", List=[1, -2, True, None, 0.5, "s", dict(A=1)], Big=2 ** 40, Neg=-(2 ** 40), Bytes=b"\x01\x02\x03", Nested=dict(K=[[], {}]))
        for little in (True, False):
            self.assertEqual(fd_romfs.byml(F.byml_dump(tree, little)), tree)
        with self.assertRaises(ValueError):
            fd_romfs.byml(b"nope" * 8)

    def test_byml_hash_keyed_dictionary(self):
        node = bytes([0x20, 1, 0, 0]) + struct.pack("<II", 0xDEADBEEF, 7) + bytes([0xD3, 0, 0, 0])
        data = b"YB" + struct.pack("<HIII", 7, 0, 0, 16) + node
        self.assertEqual(fd_romfs.byml(data), {0xDEADBEEF: 7})

    def test_sarc_both_byte_orders(self):
        files = {"a.bin": b"hello", "dir/b.bin": b"x" * 9}
        for little in (True, False):
            self.assertEqual(fd_romfs.sarc(F.sarc_dump(files, little)), files)

    def test_romfs_walk_glob_and_read(self):
        root = F.write_romfs(Path(tempfile.mkdtemp(prefix="flagdata-test-")))
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        r = fd_romfs.Romfs(root)
        self.assertEqual([p for p, _ in r.walk("Event")], ["Event/Flow.txt"])
        self.assertEqual(r.walk("NoSuchFolder"), [])
        self.assertEqual(r.glob_one("GameData", r"GameDataList\.Product\.[0-9]+\.byml\.zs"), "GameData/GameDataList.Product.100.byml.zs")
        with self.assertRaises(ValueError):
            r.glob_one("Event", r"nothing.*")
        self.assertEqual(r.read("Pack/readme.txt"), b"nothing here\n")
        with self.assertRaises(ValueError):
            fd_romfs.Romfs(root / "missing")
        deep = root / "d"
        for i in range(14):
            deep = deep / "x"
        deep.mkdir(parents=True)
        (deep / "f").write_bytes(b"1")
        with self.assertRaises(ValueError):
            r.walk("d")

    @unittest.skipUnless(fd_romfs.zstd_backend() == "compression.zstd", "needs Python 3.14's compression.zstd to make a dictionary")
    def test_zstd_files_are_decoded_with_the_dictionary_of_their_frame(self):
        from compression import zstd
        samples = [("sample %d: %s" % (i, "abcdefghij" * (i % 7 + 3))).encode() * 2 for i in range(400)]
        try:
            dictionary = zstd.train_dict(samples, 2048)
        except Exception as error:   # (a made-up corpus too small for this zstd build)
            self.skipTest("cannot train a dictionary here: %s" % error)
        blob = dictionary.dict_content
        root = Path(tempfile.mkdtemp(prefix="flagdata-test-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        (root / "Pack").mkdir()
        (root / "Pack/ZsDic.pack.zs").write_bytes(zstd.compress(F.sarc_dump({"one.zsdic": blob})))
        payload = b"sample 5: abcdefghij" * 5
        (root / "f.bin.zs").write_bytes(zstd.compress(payload, zstd_dict=zstd.ZstdDict(blob)))
        (root / "plain.zs").write_bytes(zstd.compress(payload))
        r = fd_romfs.Romfs(root)
        self.assertEqual(r.read("f.bin.zs"), payload)
        self.assertEqual(r.read("plain.zs"), payload)
        self.assertIn(fd_romfs.dict_id(blob), r.dicts())
        (root / "other.zs").write_bytes(zstd.compress(payload, zstd_dict=zstd.ZstdDict(zstd.train_dict(samples[:200], 1024).dict_content)))
        with self.assertRaises(ValueError):
            fd_romfs.Romfs(root).read("other.zs")


class Source(unittest.TestCase):
    def test_lists_constants_and_comments_are_read_from_the_source(self):
        lists = fd_source.parse(F.source_text())
        self.assertEqual(lists.constants["S_POUCH"], h("Stock"))
        self.assertEqual((lists.reset_new_game, lists.reset_temporary, lists.key_max, lists.int_max_item), (56, 263, 15, 999))
        self.assertEqual(lists.lists["song_flags"], [h("Markers.Song1"), h("Markers.Song2")])
        self.assertEqual(lists.lists["unshared_flags"], [h("Standing_Flag"), 1])
        self.assertEqual(lists.ammo, [(h("Stock.Bomb.Count"), h("Cap"))])
        boss = lists.boss_sets[0]
        self.assertEqual((boss["name"], boss["scene"], boss["proof"], boss["members"], boss["fight"]),
                         ("Gohma", "AlphaCave", [(h("HavePlayedEvent.BossDeath"), 1)], [(h("HavePlayedEvent.BossIn"), 1)], [h("Fight_Flag")]))
        self.assertEqual(lists.comments[h("Standing_Flag")], "Standing_Flag")
        self.assertEqual(lists.comments[h("HavePlayedEvent.BossDeath")], "HavePlayedEvent.BossDeath")
        self.assertEqual(lists.warnings, [])
        self.assertEqual(fd_source.rule_warnings(F.source_text()), [])

    def test_a_list_or_constant_that_is_missing_is_named(self):
        text = F.source_text()
        with self.assertRaises(ValueError) as e:
            fd_source.parse(text.replace("song_flags", "other_flags"))
        self.assertIn("song_flags", str(e.exception))
        with self.assertRaises(ValueError) as e:
            fd_source.parse(text.replace("#define F_RUPEES", "#define F_MONEY"))
        self.assertIn("F_RUPEES", str(e.exception))
        older = fd_source.parse(text.replace("code_read_scenes", "renamed_list"))
        self.assertEqual(older.lists["code_read_scenes"], [])
        self.assertIn("code_read_scenes", older.warnings[0])

    def test_changed_rules_are_reported(self):
        warnings = fd_source.rule_warnings(F.source_text(extra_rule=False))
        self.assertEqual(len(warnings), 1)
        self.assertIn("boss_proof_of", warnings[0])
        self.assertEqual(fd_source.rule_warnings("int main(void) { return 0; }"), ["no classify() in the source: the rules cannot be checked"])

    def test_scene_scan_settings(self):
        cfg = fd_source.scan_settings(F.SCENES_SOURCE)
        self.assertEqual((cfg["folders"], cfg["table_folder"], cfg["prefix"]), (["Event", "Banc", "GameData", "RSDB"], "RSDB", "HavePlayedEvent."))
        self.assertIsNone(fd_source.scan_settings("no roots here"))

    def test_the_source_is_read_from_a_clone_at_a_revision(self):
        import subprocess
        tmp = Path(tempfile.mkdtemp(prefix="flagdata-test-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        (tmp / "host").mkdir()
        (tmp / "host/oot_coop.c").write_text("first\n")
        git = ["git", "-C", str(tmp), "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]
        subprocess.run(git + ["init", "-q"], check=True)
        subprocess.run(git + ["add", "."], check=True)
        subprocess.run(git + ["commit", "-q", "-m", "one"], check=True)
        (tmp / "host/oot_coop.c").write_text("second\n")
        self.assertEqual(fd_source.read_source(repo=tmp, rev="HEAD"), "first\n")
        self.assertEqual(fd_source.read_source(path=tmp / "host/oot_coop.c"), "second\n")
        with self.assertRaises(ValueError):
            fd_source.read_source(repo=tmp, rev="nosuchrev")
        with self.assertRaises(ValueError):
            fd_source.read_source()


class StoryScenes(Fixture):
    def test_the_list_is_the_events_less_the_names_other_files_spell(self):
        s = self.pipeline()["scenes"]
        self.assertEqual((len(s.events), len(s.gated), len(s.kept), s.files, s.skipped), (6, 1, 5, 4, []))   # (the folder Pack is not scanned)
        self.assertEqual(s.gated, {h("HavePlayedEvent.Gate_Alpha")})
        self.assertNotIn(h("HavePlayedEvent.bad name!"), s.events)
        self.assertIn(h("HavePlayedEvent.Unlisted_Row"), s.kept)

    def test_the_stamp_is_fnv_over_the_sorted_hashes(self):
        s = self.pipeline()["scenes"]
        v = 2166136261
        for b in struct.pack("<I", 1) + b"".join(struct.pack("<I", x) for x in sorted(s.kept)):
            v = ((v ^ b) * 16777619) & 0xFFFFFFFF
        self.assertEqual(s.stamp(), v)
        self.assertEqual(fd_scenes.Scenes().stamp(), 0)

    def test_files_that_cannot_be_read_are_counted_not_guessed_from(self):
        (self.romfs / "Event" / "Bad.zs").write_bytes(b"\x28\xb5\x2f\xfd" + bytes([0x03, 0x58]) + (5).to_bytes(4, "little") + b"junk")
        s = self.pipeline()["scenes"]
        self.assertEqual((s.files, len(s.skipped)), (4, 1))
        self.assertIn("Bad.zs", s.skipped[0])

    def test_a_missing_table_is_an_error(self):
        os_remove = (self.romfs / "RSDB/EventSetting.Product.100.rstbl.byml.zs")
        os_remove.unlink()
        with self.assertRaises(ValueError):
            fd_scenes.scan(fd_romfs.Romfs(self.romfs), fd_source.scan_settings(F.SCENES_SOURCE))

    def test_big_endian_files_read_the_same(self):
        for rel, data in F.romfs_files(little=False).items():
            (self.romfs / rel).write_bytes(data)
        p = self.pipeline()
        self.assertEqual(len(p["scenes"].kept), 5)
        self.assertEqual(fd_classify.counts(p["results"])["progress"], 9)


class Classification(Fixture):
    def test_counts_equal_what_the_game_would_log(self):
        p = self.pipeline()
        self.assertEqual(fd_classify.counts(p["results"]),
                         dict(progress=9, items=4, songs=2, quest=1, keys=1, rupees=1, ammo=1, scenes=1))

    def test_each_flag_lands_where_the_rules_put_it(self):
        by = {r.entry.hash: r for r in self.pipeline()["results"]}

        def at(name):
            return by[h(name)]
        self.assertEqual((at("HavePlayedEvent.Intro").category, at("HavePlayedEvent.Intro").scene), ("progress", True))
        for name in ("HavePlayedEvent.Gate_Alpha", "HavePlayedEvent.CodeRead", "HavePlayedEvent.BossDeath"):
            self.assertEqual((at(name).category, at(name).scene), ("progress", False), name)   # named by data, read by code, a proof
        self.assertEqual(at("Markers.Song1").category, "songs")
        self.assertEqual(at("Markers.Sword").category, "items")
        self.assertEqual(at("Dungeons.AlphaCave.HasMap").category, "progress")
        for name, cat in (("Player.Rupees", "rupees"), ("Dungeons.AlphaCave.Keys", "keys"), ("Stock.Bomb.Count", "ammo"),
                          ("Stock.Medal.Count", "quest"), ("Stock.Boots.Count", "items"), ("Caps.Wallet", "items"), ("Player.MagicSize", "items")):
            self.assertEqual(at(name).category, cat, name)
        reasons = {name: at(name).reason for name in ("Temp_Flag", "Unsaved_Flag", "Option_Flag", "NoReset_Flag", "Heart_Flag", "Standing_Flag",
                                                      "Fight_Flag", "HavePlayedEvent.BossIn", "Stock.Cloak.Count", "Misc_Counter")}
        self.assertTrue(all(reasons.values()), reasons)
        self.assertTrue(reasons["Temp_Flag"].startswith("temporary"))
        self.assertTrue(reasons["Unsaved_Flag"].startswith("never saved"))
        self.assertIn("save file index 1", reasons["Option_Flag"])
        self.assertEqual(reasons["NoReset_Flag"], "not reset by a new game")
        self.assertTrue(reasons["Heart_Flag"].startswith("heart reward"))
        self.assertTrue(reasons["Standing_Flag"].startswith("unshared list"))
        self.assertTrue(reasons["Fight_Flag"].startswith("a boss fight's own flag"))
        self.assertTrue(reasons["HavePlayedEvent.BossIn"].startswith("a boss fight's own flag"))
        self.assertTrue(reasons["Stock.Cloak.Count"].startswith("a count that stays"))
        self.assertTrue(reasons["Misc_Counter"].startswith("an Int that is in no group"))

    def test_default_modes_follow_the_rooms_defaults(self):
        by = {r.entry.hash: r for r in self.pipeline()["results"]}
        expect = {"HavePlayedEvent.Intro": ("own", False), "Story_Alpha": ("shared", True), "Markers.Song1": ("shared", True),
                  "Stock.Medal.Count": ("shared", True), "Dungeons.AlphaCave.Keys": ("pool", True), "Player.Rupees": ("own", False),
                  "Stock.Bomb.Count": ("own", False)}
        for name, (mode, shared) in expect.items():
            self.assertEqual((by[h(name)].mode, by[h(name)].shared_by_default), (mode, shared), name)

    def test_struct_groups_are_read_the_way_the_game_builds_them(self):
        g = self.pipeline()["classifier"].groups
        self.assertEqual(g.first_get, {h("Markers.Sword"), h("Markers.Song1"), h("Markers.Song2")})
        self.assertEqual(g.pouch, {h("Stock.%s.Count" % x) for x in ("Bomb", "Medal", "Cloak", "Boots")})
        self.assertEqual((g.keys, g.capacity, g.hud), ({h("Dungeons.AlphaCave.Keys")}, {h("Caps.Wallet")}, {h("Dungeons.AlphaCave.HasMap")}))

    def test_a_list_the_data_does_not_hold_changes_the_counts(self):
        self.source.write_text(F.source_text(song=["Markers.Song1"]))
        c = fd_classify.counts(self.pipeline()["results"])
        self.assertEqual((c["songs"], c["items"], c["progress"]), (1, 5, 9))   # the second song falls back to an item marker
        self.source.write_text(F.source_text(own=["Stock.Boots.Count"]))
        by = {r.entry.hash: r for r in self.pipeline()["results"]}
        self.assertEqual(by[h("Stock.Cloak.Count")].category, "items")      # Cloak is now an item, Boots stays with its player
        self.assertIsNone(by[h("Stock.Boots.Count")].category)


class Names(Fixture):
    def test_names_come_from_files_the_event_table_structs_and_placements(self):
        book = self.pipeline()["book"]
        source = lambda name: book.names[h(name)][1]
        self.assertEqual(source("Story_Alpha"), "files")
        self.assertEqual(source("HavePlayedEvent.Intro"), "event table")
        self.assertEqual(source("Stock.Bomb.Count"), "struct")
        self.assertEqual(book.names[h("Stock.Bomb")][0], "Stock.Bomb")
        self.assertEqual(source("ChestOpen.%d" % F.ACTOR_ID), "struct")
        self.assertEqual(book.names[h(str(F.ACTOR_ID))][1], "placement")
        self.assertEqual(book.actors[F.ACTOR_ID], ("ZoneA", "Chest_Small", "Chest_One"))
        self.assertNotIn(h("ZoneA_RoomA_Cleared"), book.names)    # only a longer identifier is spelled out in the files

    def test_the_names_file_supplies_names_with_ranges_and_reports_misses(self):
        names = self.tmp / "names.txt"
        names.write_text("# a comment\nZoneA_RoomA_Cleared   # trailing\nRoom{08..11}\nNotAFlagAtAll\n")
        book = self.pipeline(names=[names])["book"]
        self.assertEqual(book.names[h("ZoneA_RoomA_Cleared")], ("ZoneA_RoomA_Cleared", "names file"))
        self.assertEqual(book.rejected, ["NotAFlagAtAll"])
        self.assertEqual(list(fd_names.expand("Room{08..11}")), ["Room08", "Room09", "Room10", "Room11"])
        self.assertEqual(list(fd_names.expand("Plain")), ["Plain"])

    def test_a_sweep_of_text_names_flags_it_quotes(self):
        notes = self.tmp / "notes"
        notes.mkdir()
        (notes / "a.md").write_text("The flag `ZoneA_RoomA_Cleared` is set when the room is done.\n")
        (notes / "blob.bin").write_bytes(b"\0ZoneA_RoomA_Cleared")
        book = self.pipeline(sweep=[notes])["book"]
        self.assertEqual(book.names[h("ZoneA_RoomA_Cleared")][1], "sweep")

    def test_the_first_name_to_match_keeps_the_flag(self):
        book = fd_names.Book({h("Alpha_Beta")})
        self.assertTrue(book.add("Alpha_Beta", "names file"))
        self.assertFalse(book.add("Alpha_Beta", "files"))
        self.assertEqual(book.names[h("Alpha_Beta")][1], "names file")
        self.assertFalse(book.add("Gamma_Delta", "files"))

    def test_chance_matches_with_junk_text_are_not_names(self):
        book = fd_names.Book(set())
        for name, source in (("f3xXn", "files"), ("mooona", "files"), ("self.abi_resolve", "files"), ("ab", "files")):
            book.names[h(name)] = (name, source)
        for name in ("f3xXn", "mooona", "ab"):
            self.assertIsNone(book.flag_name(h(name)), name)
        book.names[h("Zone_Flag")] = ("Zone_Flag", "files")
        book.names[h("lower_case_flag")] = ("lower_case_flag", "files")
        book.names[h("lower_case_note")] = ("lower_case_note", "sweep")
        self.assertIsNotNone(book.flag_name(h("Zone_Flag")))
        self.assertIsNotNone(book.flag_name(h("lower_case_flag")))
        self.assertIsNone(book.flag_name(h("lower_case_note")))       # text swept from notes: stricter
        self.assertTrue(fd_names.plausible("IsAlreadyDone") and not fd_names.plausible("Short"))

    def test_a_member_is_named_only_when_the_hash_agrees(self):
        p = self.pipeline()
        tables, book = p["tables"], p["book"]
        member = h("Wallet")
        book.names.pop(h("Caps.Wallet"), None)
        tables.structs[h("Caps")] = [(member, h("Caps.Wallet") ^ 1)]     # a child hash that is not murmur(parent.member)
        fd_names.grow(book, tables)
        self.assertNotIn(h("Caps.Wallet"), book.names)
        self.assertNotIn(h("Caps.Wallet") ^ 1, book.names)


class Reports(Fixture):
    def rows(self, **kw):
        p = self.pipeline(**kw)
        return p, *fd_report.make_rows(p["results"], p["ctx"])

    def test_rows_carry_family_map_and_default_mode(self):
        _, rows, left = self.rows()
        by = {r["name"] or r["hash"]: r for r in rows}
        chest = by["ChestOpen.%d" % F.ACTOR_ID]
        self.assertEqual((chest["family"], chest["map"], chest["prefix"]), ("ChestOpen.*", "ZoneA", "ChestOpen"))
        self.assertIn("Chest_Small", chest["note"])
        scene = by["HavePlayedEvent.Intro"]
        self.assertEqual((scene["scene"], scene["shared_by_default"], scene["default_mode"], scene["family"]),
                         ("yes", "no", "own (story scenes: each player)", "HavePlayedEvent.*"))
        self.assertEqual(by["Dungeons.AlphaCave.Keys"]["default_mode"], "pool")
        self.assertEqual(by["Stock.Boots.Count"]["family"], "items: item count")
        self.assertEqual(by["Player.MagicSize"]["family"], "items: magic meter size")
        unnamed = by["%08x" % h("ZoneA_RoomA_Cleared")]
        self.assertEqual((unnamed["named"], unnamed["family"]), ("no", "unnamed, in no group"))
        self.assertEqual(len(left), 10)
        self.assertEqual(len({r["reason"] for r in left}), 9)

    def test_maps_resolve_exactly_or_by_one_unique_containing_name(self):
        older = "TowerKeep_" + "Adult"     # (the variant suffixes are folded into the base map)
        maps = {"ZoneA": "ZoneA", older: "TowerKeep", "TowerKeep": "TowerKeep", "TowerMarket": "TowerMarket"}
        self.assertEqual(fd_report.resolve_map("ZoneA", maps), "ZoneA")
        self.assertEqual(fd_report.resolve_map("Keep", maps), "TowerKeep")
        self.assertEqual(fd_report.resolve_map("Tower", maps), "")       # two maps hold it
        self.assertEqual(fd_report.resolve_map("Ke", maps), "")          # too short to mean anything
        self.assertEqual(fd_report.map_table({1: (older, "x", "y")})["TowerKeep"], "TowerKeep")

    def test_the_other_containers_are_listed_with_names_defaults_and_placed_actors(self):
        p = self.pipeline()
        by_kind = {}
        for r in fd_report.make_other_rows(p["ctx"]):
            by_kind.setdefault(r["kind"], []).append(r)
        self.assertEqual({k: len(v) for k, v in by_kind.items()},
                         {"Bool64bitKey": 2, "Enum": 1, "Float": 1, "IntArray": 1, "Struct": 10})
        enum, = by_kind["Enum"]
        self.assertEqual((enum["default"], enum["extra"], enum["named"]), ("B", "2 values: A, B", "no"))
        ratio, = by_kind["Float"]
        self.assertEqual((ratio["name"], ratio["default"], ratio["file"], ratio["name_source"]), ("Misc_Ratio", "0.5", 2, "files"))
        counts, = by_kind["IntArray"]
        self.assertEqual((counts["default"], counts["extra"]), ("-1", "OriginalSize 2; TotalSize 4"))
        placed, wide = sorted(by_kind["Bool64bitKey"], key=lambda r: r["hash"])
        self.assertEqual((placed["hash"], placed["map"], placed["prefix"], placed["note"]),
                         ("000000000000004d", "ZoneA", "Other", 'placed actor Other "Other_One" in ZoneA'))
        self.assertEqual((wide["hash"], wide["map"], wide["note"]), ("8000000000000005", "", ""))   # (a key no placed actor has: 16 digits)
        self.assertLessEqual({"Markers", "Stock", "Dungeons", "Caps", "ChestOpen", "Dungeons.AlphaCave"}, {r["name"] for r in by_kind["Struct"]})
        self.assertTrue(all(r["extra"].endswith("members") for r in by_kind["Struct"]))

    def test_describe_other_covers_the_kinds_the_list_has(self):
        d = fd_classify.describe_other
        self.assertEqual(d("Vector3", dict(DefaultValue=dict(x=1.0, y=2.0, z=0.0))), (" ".join(["1.0", "2.0", "0.0"]), ""))
        self.assertEqual(d("BoolExp", dict(Values=[[12, 5], [2, 7, 9]])), ("", "terms 12:5 2:7:9"))
        self.assertEqual(d("String64", dict(DefaultValue="x")), ("x", ""))
        self.assertEqual(d("Binary", dict(DefaultValue=40960)), ("40960", ""))
        self.assertEqual(d("BoolArray", dict(DefaultValue=False, OriginalSize=80, TotalSize=80)), ("0", "OriginalSize 80; TotalSize 80"))
        self.assertEqual(d("Enum", dict(DefaultValue=12345, RawValues=["A"])), ("0x00003039", "1 values: A"))
        self.assertEqual(d("Bool64bitKey", dict(Hash=1)), ("", ""))

    def test_a_short_kind_word_before_the_place_is_skipped(self):
        p = self.pipeline()
        ctx = p["ctx"]
        ctx.maps = {"AlphaCave": "AlphaCave"}
        self.assertEqual(ctx.area("HavePlayedEvent.Xx_Alpha_Scene", None)[0], "AlphaCave")
        self.assertEqual(ctx.area("HavePlayedEvent.Long_Alpha_Scene", None)[0], "")
        self.assertEqual(ctx.area("HavePlayedEvent.12345_6_7", None)[1], "(numeric)")

    def test_csv_and_markdown_are_written_with_the_numbers(self):
        code, out, err = self.build()
        self.assertEqual((code, err), (0, ""))
        self.assertIn("counts: progress 9, items 4, songs 2, quest 1, keys 1, rupees 1, ammo 1, scenes 1", out)
        import csv
        with open(self.tmp / "out/flags.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(list(rows[0]), fd_report.CSV_COLUMNS)
        self.assertEqual(len(rows), 19)
        self.assertEqual(sum(r["scene"] == "yes" for r in rows), 1)
        with open(self.tmp / "out/excluded.csv", encoding="utf-8") as f:
            left = list(csv.DictReader(f))
        self.assertEqual((list(left[0]), len(left)), (fd_report.EXCLUDED_COLUMNS, 10))
        self.assertTrue(all(r["family"] for r in left))
        with open(self.tmp / "out/others.csv", encoding="utf-8") as f:
            other = list(csv.DictReader(f))
        self.assertEqual(list(other[0]), fd_report.OTHER_COLUMNS)
        md = (self.tmp / "out/flags.md").read_text(encoding="utf-8")
        self.assertIn("co-op looks at **19**", md)
        self.assertIn("| story scenes | 1 | each player's own", md)
        self.assertIn("classified 19 + left out 10 = 29", md)
        self.assertIn("| ChestOpen.* | 1 | 0 | 1 |", md)
        self.assertIn("`Markers.Song1`", md)
        self.assertIn("never to be committed", md)


class Build(Fixture):
    def log(self, counts="9 progress flags (1 of them story scenes: each player's own unless the room shares scenes), 4 items, 2 songs, "
                         "1 quest items, 1 key counters, 1 rupee counter, 1 ammunition counters"):
        path = self.tmp / "game.log"
        stamp = "%08x" % self.pipeline()["scenes"].stamp()
        path.write_text("[hos host] coop: sync: story scenes: 5 of this game's 6 events are each player's own unless the room shares scenes; "
                        "the other 1 are named by other data. Made from 4 files of this game in 0.1 s (list %s)\n"
                        "[hos Presentation Thread] coop: sync: playing a save: %s; the room's rules decide which are shared\n" % (stamp, counts))
        return path

    def test_a_log_with_the_same_counts_passes(self):
        code, out, err = self.build("--compare-log", str(self.log()))
        self.assertEqual(code, 0, out + err)
        self.assertIn("OK   the log's counts [9, 1, 4, 2, 1, 1, 1, 1]", out)
        self.assertIn("OK   the log's story-scene list", out)
        self.assertIn("compared with `game.log`: equal", (self.tmp / "out/flags.md").read_text())

    def test_a_log_with_other_counts_fails_the_build(self):
        code, out, _ = self.build("--compare-log", str(self.log(counts=self.log().read_text().split("playing a save: ")[1].split(";")[0].replace("9 progress", "10 progress"))))
        self.assertEqual(code, 1)
        self.assertIn("FAIL the log's counts", out)
        self.assertIn("DIFFERENT", (self.tmp / "out/flags.md").read_text())

    def test_a_log_without_the_line_fails(self):
        empty = self.tmp / "empty.log"
        empty.write_text("nothing\n")
        code, out, _ = self.build("--compare-log", str(empty))
        self.assertEqual(code, 1)
        self.assertIn("no `N progress flags", out)

    def test_outputs_and_cache_are_refused_inside_the_workbench_checkout(self):
        for argv in (["--out", str(ROOT / "flagdata" / "out-should-not-exist"), "--state", str(self.tmp / "s")],
                     ["--out", str(self.tmp / "o"), "--state", str(ROOT / "state-should-not-exist")]):
            code, _, err = run(["build", "--romfs", str(self.romfs), "--source", str(self.source), *argv])
            self.assertEqual(code, 2)
            self.assertIn("workbench checkout", err)
        self.assertFalse((ROOT / "flagdata" / "out-should-not-exist").exists())
        self.assertFalse((ROOT / "state-should-not-exist").exists())

    def test_the_cache_is_private_and_lookup_reads_it(self):
        self.assertEqual(self.build()[0], 0)
        state = self.tmp / "state"
        self.assertEqual(stat.S_IMODE(state.stat().st_mode), 0o700)
        files = sorted(state.iterdir())
        self.assertEqual(sorted(p.name[:6] for p in files), ["LATEST", "table-"])
        for p in files:
            self.assertEqual(stat.S_IMODE(p.stat().st_mode), 0o600, p.name)
        code, out, err = run(["lookup", "%08x" % h("Dungeons.AlphaCave.Keys"), "%08x" % h("Heart_Flag"), "deadbeef", "--state", str(state)])
        self.assertEqual((code, err), (0, ""))
        self.assertIn("Dungeons.AlphaCave.Keys  Int  keys  default 0  keys, pool", out)
        self.assertIn("Heart_Flag  Bool  left out: heart reward", out)
        self.assertIn("deadbeef  not a Bool or Int flag", out)
        code, _, err = run(["lookup", "00000001", "--state", str(self.tmp / "nothing")])
        self.assertEqual(code, 2)
        self.assertIn("flagdata.py build", err)

    def test_no_cache_writes_none(self):
        self.assertEqual(self.build("--no-cache")[0], 0)
        self.assertFalse((self.tmp / "state").exists())

    def test_rule_and_source_warnings_are_shown_and_kept_in_the_report(self):
        self.source.write_text(F.source_text(extra_rule=False))
        code, _, err = self.build()
        self.assertEqual(code, 0)
        self.assertIn("boss_proof_of", err)
        self.assertIn("warning: classify() no longer contains", (self.tmp / "out/flags.md").read_text())

    def test_a_missing_game_file_is_an_error_not_a_traceback(self):
        os.unlink(self.romfs / "GameData/GameDataList.Product.100.byml.zs")
        code, _, err = self.build()
        self.assertEqual(code, 2)
        self.assertIn("flagdata:", err)

    def test_hash_command(self):
        code, out, _ = run(["hash", "test"])
        self.assertEqual((code, out), (0, "ba6bd213  test\n"))

    def test_scan_settings_come_from_the_source_next_to_oot_coop(self):
        (self.tmp / "coop_scenes.c").write_text(F.SCENES_SOURCE.replace('"Event", ', ""))
        self.assertEqual(self.build()[0], 0)
        md = (self.tmp / "out/flags.md").read_text()
        self.assertIn("story-scene list: 3 files read", md)     # (the folder Event is no longer scanned)


class Cache(unittest.TestCase):
    def test_state_folder_precedence(self):
        keep = {k: os.environ.get(k) for k in ("LS_FLAGDATA_STATE", "XDG_STATE_HOME")}
        self.addCleanup(lambda: [os.environ.__setitem__(k, v) if v is not None else os.environ.pop(k, None) for k, v in keep.items()])
        os.environ.pop("LS_FLAGDATA_STATE", None)
        os.environ["XDG_STATE_HOME"] = "/xdg"
        self.assertEqual(fd_cache.state_dir(), Path("/xdg/ls-workbench/flagdata"))
        os.environ["LS_FLAGDATA_STATE"] = "/own"
        self.assertEqual(fd_cache.state_dir(), Path("/own"))
        self.assertEqual(fd_cache.state_dir("/explicit"), Path("/explicit"))

    def test_a_cache_of_another_version_is_refused(self):
        tmp = Path(tempfile.mkdtemp(prefix="flagdata-test-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        (tmp / "t.json").write_text('{"version": 0, "flags": {}}')
        with self.assertRaises(ValueError):
            fd_cache.load(tmp / "t.json")


class Publication(unittest.TestCase):
    def test_no_data_file_and_no_game_name_list_is_kept_with_the_tools(self):
        banned = {".json", ".csv", ".pkl", ".pickle", ".zs", ".byml", ".bin", ".sav", ".log", ".txt"}
        for folder in (ROOT / "flagdata",):
            for path in folder.rglob("*"):
                if "__pycache__" in path.parts or not path.is_file():
                    continue
                self.assertNotIn(path.suffix, banned, str(path))
                text = path.read_text(encoding="utf-8")
                self.assertLess(len(text), 60_000, str(path))
                run_of_hashes = __import__("re").findall(r"(?:0x[0-9a-fA-F]{8}[, ]+){3}", text)
                self.assertEqual(run_of_hashes, [], str(path))


if __name__ == "__main__":
    unittest.main()
