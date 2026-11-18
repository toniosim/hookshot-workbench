"""Operator catalogue additions, game info schema, hashing and codecs, bridge memory/flag helpers, publication hygiene."""
import asyncio
import json
from pathlib import Path
import re
import struct

import pytest
from pydantic import ValidationError
from src.effects.session_bridge import COMMANDS, READS, Bridge
from src.effects.session_memory import decode, encode, flag_hash, murmur3_32
from src.errors import WorkbenchError
from src.models.session import BuildEntry, SessionCatalogue, SessionProfile
from src.models.session_debug import GameInfo
from src.tools import session as tools
from test_session_debug import GAME, ITEM_A, ITEM_B, ITEM_C, synthetic_info

FakeDebugGame = GAME.FakeDebugGame


# ---- catalogue additions

def test_profile_defaults_change_nothing():
    profile = SessionProfile()
    assert (profile.debug, profile.debug_tools, profile.memory, profile.protect_hearts) == (False, False, "off", False)
    assert SessionProfile(debug=True).memory == "off"


@pytest.mark.parametrize("field", [{"debug_tools": True}, {"memory": "rw"}, {"protect_hearts": True},
                                   {"debug_tools": True, "memory": "rw", "protect_hearts": True}])
def test_each_debug_switch_requires_a_debug_profile(field):
    with pytest.raises(ValidationError):
        SessionProfile(**field)
    with pytest.raises(ValidationError):
        SessionCatalogue.model_validate({"clone_root": "/x", "profiles": {"p": field}})
    assert SessionProfile(debug=True, **field)


@pytest.mark.parametrize("field", [{"memory": "ro"}, {"memory": True}, {"debug_tools": "maybe"}, {"unknown": 1}])
def test_debug_switch_values_are_closed(field):
    with pytest.raises(ValidationError):
        SessionProfile(debug=True, **field)


def test_build_game_info_is_an_optional_path():
    assert BuildEntry(path="/x", reviewed=True, owned=True).game_info is None
    entry = BuildEntry(path="/x", reviewed=True, owned=True, game_info="/y/info.json")
    assert entry.game_info == Path("/y/info.json")


# ---- game info schema 1

def with_change(path, value):
    info = synthetic_info()
    target = info
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return info


def test_game_info_accepts_the_documented_shape():
    info = GameInfo.model_validate(synthetic_info())
    assert info.actions.return_to_mark == 12 and info.actions.time_hours == 24
    assert [(i.name, i.kind) for i in info.items] == [(ITEM_A, 0), (ITEM_B, 1), (ITEM_C, 1)]
    assert info.layout.kinds["uint"].stride == 48 and info.layout.box.size == 44
    assert info.names["life"] == "synthetic.life" and info.item_flags.count == "Synthetic.{name}.Stock"
    minimal = GameInfo.model_validate({"schema": 1, "actions": synthetic_info()["actions"]})
    assert minimal.items == [] and minimal.layout is None and minimal.item_flags is None and minimal.names == {}


@pytest.mark.parametrize("info", [
    {**synthetic_info(), "extra": 1}, {**synthetic_info(), "schema": 2}, {k: v for k, v in synthetic_info().items() if k != "schema"},
    {k: v for k, v in synthetic_info().items() if k != "actions"},
    with_change(["actions", "extra"], 1), with_change(["actions", "mark"], -1), with_change(["actions", "time_hours"], 25),
    with_change(["actions", "time_hours"], 0), with_change(["actions", "item_stride"], 0), with_change(["actions", "mark"], "x"),
    with_change(["items", 0, "kind"], 2), with_change(["items", 0, "extra"], 1), with_change(["items", 0, "name"], ""),
    with_change(["items", 0, "name"], "bad\nname"), with_change(["items", 1, "name"], ITEM_A), with_change(["items", 1, "index"], 0),
    with_change(["items"], [{"index": n, "name": f"n{n}", "label": "", "kind": 0} for n in range(1025)]),
    with_change(["item_flags", "count"], "no.placeholder"), with_change(["item_flags", "have"], "{name}.{name}"),
    with_change(["item_flags", "count"], "bad space.{name}"), with_change(["item_flags", "extra"], "x"),
    with_change(["layout", "kinds"], {}), with_change(["layout", "kinds", "text"], {"at": 1, "stride": 1, "value": 1}),
    with_change(["layout", "kinds", "bool", "stride"], 0), with_change(["layout", "holder"], -1),
    with_change(["layout", "holder"], 2**63), with_change(["layout", "box", "extra"], 1), with_change(["layout", "extra"], 1),
    with_change(["names"], {"bad name": "synthetic.life"}), with_change(["names"], {"ok": "bad name"}),
    with_change(["names"], {f"n{n}": "synthetic.life" for n in range(65)}),
])
def test_game_info_refuses_anything_else(info):
    with pytest.raises(ValidationError):
        GameInfo.model_validate(info)


def test_game_info_names_accept_any_alias_under_the_bound():
    info = with_change(["names"], {"synthetic.alias_1": "0x00ab12cd", "Another.Alias": "synthetic.flag"})
    assert set(GameInfo.model_validate(info).names) == {"synthetic.alias_1", "Another.Alias"}
    assert GameInfo.model_validate(with_change(["item_flags"], {"count": "{name}"})).item_flags.count == "{name}"


# ---- hashing and codecs

@pytest.mark.parametrize("data,expected", [(b"", 0), (b"test", 0xBA6BD213), (b"Hello, world!", 0xC0363E43)])
def test_murmur3_published_vectors(data, expected):
    assert murmur3_32(data, 0) == expected


def test_murmur3_is_seeded_and_covers_every_tail_length():
    assert murmur3_32(b"", 1) == 0x514E28B7
    assert len({murmur3_32(b"abcdefgh"[:n]) for n in range(9)}) == 9
    assert murmur3_32(b"a" * 1000) == murmur3_32(b"a" * 1000) < 2**32


def test_flag_hash_takes_a_literal_hash_as_is():
    assert flag_hash("0x0000abcd") == 0xABCD and flag_hash("0xDEADBEEF") == 0xDEADBEEF
    assert flag_hash("synthetic.flag") == murmur3_32(b"synthetic.flag")
    assert flag_hash("0xZZZZZZZZ") == murmur3_32(b"0xZZZZZZZZ") and flag_hash("0x123") == murmur3_32(b"0x123")


@pytest.mark.parametrize("kind,value,raw", [("bool", True, b"\x01"), ("bool", False, b"\x00"), ("bool", 1, b"\x01"), ("bool", 0, b"\x00"),
    ("int", -2, struct.pack("<i", -2)), ("int", 2**31 - 1, struct.pack("<i", 2**31 - 1)), ("int", 5.0, struct.pack("<i", 5)),
    ("uint", 2**32 - 1, b"\xff\xff\xff\xff"), ("uint", 0, b"\0\0\0\0"), ("float", 1.5, struct.pack("<f", 1.5)),
    ("float", 3, struct.pack("<f", 3.0)), ("float", -0.25, struct.pack("<f", -0.25))])
def test_values_encode_little_endian_in_the_kinds_width(kind, value, raw):
    assert encode(kind, value) == raw
    assert decode(kind, raw) == (bool(value) if kind == "bool" else value)


@pytest.mark.parametrize("kind,value", [("bool", 2), ("bool", -1), ("bool", 0.5), ("bool", "1"), ("int", 2**31), ("int", -2**31 - 1),
    ("int", 1.5), ("int", True), ("uint", -1), ("uint", 2**32), ("uint", False), ("float", True), ("float", float("nan")),
    ("float", float("inf")), ("float", 3.5e38), ("float", "1"), ("int", None)])
def test_unrepresentable_values_are_refused(kind, value):
    with pytest.raises(ValueError):
        encode(kind, value)


def test_decode_keeps_odd_bool_bytes_visible():
    assert decode("bool", b"\x02") == 2 and decode("bool", b"\x00") is False


# ---- bridge: memory commands and the one-shot flag sample

async def connected(tmp_path, **kwargs):
    fake = await FakeDebugGame(tmp_path / "b.sock", synthetic_info(), **kwargs).start()
    fake.populate()
    return fake, await Bridge.connect(fake.path)


def test_memory_reads_are_reads_and_the_write_is_a_mutation():
    assert {"mem_read", "mem_read_many", "mem_write"} <= COMMANDS
    assert {"mem_read", "mem_read_many"} <= READS and "mem_write" not in READS


async def test_memory_commands_and_their_error_mapping(tmp_path):
    fake, bridge = await connected(tmp_path)
    try:
        address = fake.flags["synthetic.counter"][1]
        assert (await bridge.request("mem_read", addr=address, size=4, format="hex"))["data"] == struct.pack("<I", 7).hex()
        rows = (await bridge.request("mem_read_many", ranges=[{"addr": address, "size": 4}, {"addr": 0, "size": 2}]))["ranges"]
        assert [(r["addr"], r["size"], len(r["data"])) for r in rows] == [(address, 4, 8), (0, 2, 4)]
        assert (await bridge.request("mem_write", addr=address, hex="09000000"))["wrote"] == 4
        assert fake.flag_value("synthetic.counter") == 9
        for command, args, code in (("mem_read", {"addr": 70000, "size": 4, "format": "hex"}, "backend_failed"),
                                    ("mem_write", {"addr": 70000, "hex": "00"}, "backend_failed")):
            with pytest.raises(WorkbenchError) as failure:
                await bridge.request(command, **args)
            assert failure.value.envelope.code == code, command  # out_of_range: nothing was written, so not uncertain
        fake.memory = "ro"
        await bridge.request("mem_read", addr=address, size=4, format="hex")
        with pytest.raises(WorkbenchError) as failure:
            await bridge.request("mem_write", addr=address, hex="00000000")
        assert failure.value.envelope.code == "refused_by_policy"
        fake.memory = "off"
        for command, args in (("mem_read", {"addr": address, "size": 4, "format": "hex"}),
                              ("mem_read_many", {"ranges": [{"addr": address, "size": 4}]})):
            with pytest.raises(WorkbenchError) as failure:
                await bridge.request(command, **args)
            assert failure.value.envelope.code == "refused_by_policy"
        assert fake.flag_value("synthetic.counter") == 9
    finally:
        await bridge.close()
        await fake.close()


async def test_a_lost_memory_write_reply_is_uncertain_and_a_lost_read_is_not(tmp_path):
    fake, bridge = await connected(tmp_path)
    try:
        address = fake.flags["synthetic.counter"][1]
        fake.drop_write = True
        with pytest.raises(WorkbenchError) as failure:
            await bridge.request("mem_write", timeout=0.1, addr=address, hex="05000000")
        assert failure.value.envelope.code == "uncertain_outcome"
        fake.drop_write = False
        fake.stall_wait = True
        with pytest.raises(WorkbenchError) as failure:
            await bridge.request("wait", timeout=0.1, event="present", frames=1)
        assert failure.value.envelope.code == "timeout"
    finally:
        await bridge.close()
        await fake.close()


async def test_sample_flags_takes_the_first_fresh_event_and_unsubscribes(tmp_path):
    fake, bridge = await connected(tmp_path)
    try:
        fake.stale_first = True
        event = await bridge.sample_flags(["synthetic.counter", "synthetic.absent", "synthetic.scale"], timeout=2)
        assert event["event"] == "oot" and event["game"]["flags"] == {"synthetic.counter": 7, "synthetic.absent": None, "synthetic.scale": 1.5}
        assert isinstance(event["game"]["frame"], int)
        commands = [c for c in fake.commands if c["cmd"] in {"subscribe", "unsubscribe"}]
        assert [c["cmd"] for c in commands] == ["subscribe", "unsubscribe"]
        assert commands[1]["sub"] == commands[0]["id"]
        assert commands[0]["flags"] == ["synthetic.counter", "synthetic.absent", "synthetic.scale"]
        assert len(fake.streams) == 0 or all(task.done() for task in fake.streams.values())
    finally:
        await bridge.close()
        await fake.close()


async def test_sample_flags_never_accepts_an_old_snapshot_and_validates_names(tmp_path):
    fake, bridge = await connected(tmp_path)
    try:
        fake.always_stale = True
        with pytest.raises(WorkbenchError) as failure:
            await bridge.sample_flags(["synthetic.counter"], timeout=0.3)
        assert failure.value.envelope.code == "timeout"
        for names in ([], ["bad name"], [""], ["a" * 48], [5], ["x"] * 65):
            with pytest.raises(WorkbenchError) as failure:
                await bridge.sample_flags(names, timeout=0.3)
            assert failure.value.envelope.code == "invalid_argument", names
        with pytest.raises(WorkbenchError):
            await bridge.sample_flags(["a"], timeout=0)
    finally:
        await bridge.close()
        await fake.close()


async def test_sample_flags_on_a_lost_connection_is_unavailable(tmp_path):
    fake, bridge = await connected(tmp_path)
    try:
        fake.always_stale = True
        waiting = asyncio.create_task(bridge.sample_flags(["synthetic.counter"], timeout=5))
        await asyncio.sleep(0.1)
        await fake.close()
        with pytest.raises(WorkbenchError) as failure:
            await asyncio.wait_for(waiting, 3)
        assert failure.value.envelope.code == "unavailable"
    finally:
        await bridge.close()


# ---- registration and publication hygiene

def test_new_tools_are_declared_with_their_safety_and_routes():
    specs = {spec.name: spec for spec in tools.SPECS}
    for name in ("session_destinations", "session_flags"):
        assert specs[name].safety.value == "READ" and specs[name].requires_broker and specs[name].shell_route
    for name in ("session_debug", "session_flag_set", "session_snapshot"):
        assert specs[name].safety.value == "WRITE_LOCAL" and specs[name].requires_broker and not specs[name].destructive
        assert specs[name].idempotent and "\n" not in specs[name].shell_route
    assert not {"session_memory", "memory_write", "raw_bridge"} & set(specs)


SOURCES = ("src/effects/session_debug.py", "src/effects/session_debug_env.py", "src/effects/session_memory.py",
           "src/models/session_debug.py", "src/models/session.py", "src/effects/session.py", "src/effects/session_bridge.py",
           "src/tools/session.py")


def test_no_fixture_or_game_literals_leak_into_the_sources():
    root = Path(__file__).resolve().parents[1]
    made_up = [ITEM_A, ITEM_B, ITEM_C, "Synthetic", "synthetic.", "SyntheticZone", "SyntheticAnnex"]
    for relative in SOURCES:
        text = (root / relative).read_text()
        for literal in made_up:
            assert literal not in text, (relative, literal)
        # No action numbers, addresses or layout offsets are written in code: a numeric literal is a bound or a width.
        assert not re.search(r"0x[0-9a-fA-F]{5,}", text.replace("0xCC9E2D51", "").replace("0x1B873593", "").replace("0xE6546B64", "")
                             .replace("0x85EBCA6B", "").replace("0xC2B2AE35", "").replace("0xFFFFFFFF", "")), relative


def test_fixture_names_in_tests_are_all_made_up():
    here = Path(__file__).parent
    for path in (*here.glob("test_session_debug*.py"), here / "test_session_flagset.py", here / "fakes/session_debug_game.py"):
        for token in re.findall(r"\b(?:[A-Za-z]+_)?Item_[A-Za-z0-9_]+", path.read_text()):
            assert token.startswith("Synthetic_Item_"), (path.name, token)
