"""Debug tools over a synthetic game: state fields, destinations, travel records, launch switches, debug actions, flags."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import time

import pytest
from src.effects.session import Session, SessionService, sample_from
from src.effects.session_debug import SessionDebug
from src.effects.session_memory import murmur3_32
from src.errors import WorkbenchError
from src.models import State
from src.models.session import SessionProfile
from src.models.session_debug import TimeAction
from test_session import attach, finished, observed, result, sandbox  # noqa: F401  (fixture)

SPEC = importlib.util.spec_from_file_location("fake_session_debug_game", Path(__file__).parent / "fakes/session_debug_game.py")
GAME = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GAME)
synthetic_info, FakeDebugGame = GAME.synthetic_info, GAME.FakeDebugGame
ITEM_A, ITEM_B, ITEM_C = GAME.ITEM_A, GAME.ITEM_B, GAME.ITEM_C
HAVE_FLAG, STOCK_FLAG = GAME.HAVE_FLAG, GAME.STOCK_FLAG

DEBUG_PROFILE = SessionProfile(debug=True, debug_tools=True, memory="rw")


async def attach_debug(root, deps, service, *, info=None, profile=DEBUG_PROFILE, game_info=True, info_file=None,
                       live=True, memory="rw", populate=True):
    """A running synthetic session: fake game, live-input file, game log and (optionally) registered game info."""
    info = synthetic_info() if info is None else info
    run = deps.registry.create_run(state=State.RUNNING)
    job = deps.registry.create_job("session_fixture")
    directory = root / run.run_id
    directory.mkdir()
    live_path = directory / "debug-live.txt"
    live_path.write_text("")
    log = directory / "longshot_log.txt"
    log.write_text("synthetic boot line\n")
    from src.effects import session_runtime
    socket = session_runtime.allocate(deps, run.run_id)
    (directory / "control-socket.json").write_text(json.dumps({"run_id": run.run_id, "socket": str(socket)}))
    fake = FakeDebugGame(socket, info, log=log, live=live_path if live else None, memory=memory)
    if populate:
        fake.populate()
    await fake.start()
    info_path = directory / "game-info.json"
    info_path.write_text(json.dumps(info) if info_file is None else info_file)
    session = Session(run.run_id, job.job_id, directory, socket, profile, {"socket": str(socket), "log": "longshot_log.txt"},
        live_path=live_path if live else None, game_info_path=info_path if game_info else None)
    service.sessions[run.run_id] = session
    return run.run_id, fake, session


def code_of(response):
    return json.loads(response.content[0].text)["code"]


async def submit(client, deps, tool, **arguments):
    """Call a Job-returning tool and wait for it; (terminal Job, result record or None)."""
    arguments.setdefault("idempotency_key", f"key-{time.monotonic_ns()}")
    job = (await client.call_tool(tool, arguments)).data
    terminal = await finished(deps, job)
    return terminal, result(deps, job) if terminal.state == State.COMPLETED else None


async def debug(client, deps, run_id, action, **extra):
    return await submit(client, deps, "session_debug", run_id=run_id, action=action, **extra)


# ---- session_state fields, destinations, travel records

async def test_state_fields_extend_without_changing_the_default(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        default = (await client.call_tool("session_state", {"run_id": run_id})).data
        assert sorted(default.unknown_fields) == []
        assert default.game.pos is None and default.game.life is None and default.game.rupees is None
        wide = (await client.call_tool("session_state", {"run_id": run_id,
            "fields": ["map", "pos", "life", "max_life", "rupees"]})).data
        assert wide.game.pos == [10, 0, -20] and wide.game.life == 48 and wide.game.max_life == 48 and wide.game.rupees == 100
        assert wide.game.event is None and wide.unknown_fields == []
        fake.nulls = {"pos", "life", "rupees"}
        gone = (await client.call_tool("session_state", {"run_id": run_id,
            "fields": ["pos", "life", "max_life", "rupees"]})).data
        assert gone.game.pos is None and gone.game.life is None and gone.game.max_life == 48
        assert gone.unknown_fields == ["life", "pos", "rupees"]
        reply = await client.call_tool("session_state", {"run_id": run_id, "fields": ["memory"]}, raise_on_error=False)
        assert code_of(reply) == "invalid_argument"
    finally:
        await fake.close()


@pytest.mark.parametrize("raw", [{"pos": [1, 2]}, {"pos": [1, 2, "x"]}, {"pos": [1, 2, float("inf")]}, {"pos": [True, 1, 2]},
    {"pos": "1 2 3"}, {"life": -1}, {"life": 1.5}, {"life": True}, {"rupees": "7"}, {"max_life": 2**40}])
def test_malformed_sample_fields_are_null(raw):
    sample = sample_from({"frame": 1, "game": {"frame": 1, "t": time.monotonic(), **raw}}, max_age_ms=500,
        selected=["pos", "life", "max_life", "rupees"])
    key = next(iter(raw))
    assert getattr(sample.game, key) is None and key in sample.unknown_fields


async def test_destinations_listing_is_typed_and_bounded(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        page = (await client.call_tool("session_destinations", {"run_id": run_id})).data
        assert [(d.index, d.child, d.adult) for d in page.destinations] == [
            (0, "SyntheticZone", "SyntheticZone"), (1, "SyntheticAnnex", "SyntheticAnnex")]
        assert page.observed_at
        fake.destination_rows = [{"index": 3, "child": None, "adult": "SyntheticAnnex"}]
        page = (await client.call_tool("session_destinations", {"run_id": run_id})).data
        assert page.destinations[0].child is None and page.destinations[0].adult == "SyntheticAnnex"
        fake.destination_rows = [{"index": n, "child": f"SyntheticRow{n}", "adult": None} for n in range(256)]
        assert len((await client.call_tool("session_destinations", {"run_id": run_id})).data.destinations) == 256
        bad = [[{"index": n, "child": None, "adult": None} for n in range(257)],
               [{"index": 256, "child": None, "adult": None}], [{"index": -1}], [{"index": "0"}], [{"index": True}],
               [{"index": 0, "child": "x" * 81}], [{"index": 0, "child": ""}], [{"index": 0, "adult": 7}],
               [{"index": 0, "child": "Synthetic\nZone"}], ["SyntheticZone"], "SyntheticZone"]
        for rows in bad:
            fake.destination_rows = rows
            reply = await client.call_tool("session_destinations", {"run_id": run_id}, raise_on_error=False)
            assert code_of(reply) == "backend_failed", rows
        assert str(root) not in json.dumps((await client.call_tool("session_destinations", {"run_id": run_id},
            raise_on_error=False)).content[0].text)
    finally:
        await fake.close()


async def test_travel_results_record_before_destination_and_map(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        terminal, record = await submit(client, deps, "session_teleport", run_id=run_id, destination_id=1)
        assert terminal.state == State.COMPLETED and record["arrived"] is True and record["sent"] is True
        assert record["before"] == {"map": "SyntheticZone", "event": None, "loading": None, "age": "child",
            "pos": [10, 0, -20], "life": None, "max_life": None, "rupees": None}
        assert record["destination"] == {"index": 1, "child": "SyntheticAnnex", "adult": "SyntheticAnnex"}
        assert record["map"] == "SyntheticAnnex" and record["state"]["game"]["map"] == "SyntheticAnnex"
        terminal, record = await submit(client, deps, "session_age", run_id=run_id, age="adult")
        assert record["arrived"] is True and record["destination"] is None and record["map"] == "SyntheticAnnex"
        assert record["before"]["age"] == "child" and record["before"]["map"] == "SyntheticAnnex"
        fake.destination_rows = [{"index": 0, "child": "SyntheticZone", "adult": None}]
        terminal, _ = await submit(client, deps, "session_teleport", run_id=run_id, destination_id=1)
        assert terminal.error.code == "invalid_argument"
        fake.destination_rows = "not a list"
        terminal, _ = await submit(client, deps, "session_teleport", run_id=run_id, destination_id=0)
        assert terminal.error.code == "unavailable"
        assert not [c for c in fake.commands if c["cmd"] == "teleport" and "to" in c and c["to"] == 0]
    finally:
        await fake.close()


async def test_age_arrives_when_the_other_ages_map_has_loaded_and_link_is_in_control(sandbox):
    # The real game flips Link's age at once and reloads the scene as an event: a result taken at the flip said arrived with
    # the old map, an event playing and no control (the first real session showed it).
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        fake.age_map, fake.reload_delay = "SyntheticAdultZone", 0.6
        terminal, record = await submit(client, deps, "session_age", run_id=run_id, age="adult")
        assert terminal.state == State.COMPLETED and record["arrived"] is True and record["map"] == "SyntheticAdultZone"
        assert record["controllable"] is True and record["state"]["controllable"] is True
        assert record["state"]["game"]["map"] == "SyntheticAdultZone" and record["state"]["game"]["age"] == "adult"
        assert record["state"]["game"]["event"] is False
    finally:
        await fake.close()


def test_a_sample_stamped_a_hair_ahead_of_the_reader_is_fresh():
    # The game's clock is printed to the millisecond: a status read within a millisecond of its sample can carry a stamp that is
    # a fraction of a millisecond ahead of the reader's. A real session lost a teleport's arrival to it (fresh None, "unsupported").
    now = time.monotonic()
    sample = sample_from({"frame": 1, "game": {"frame": 1, "t": now + 0.0005, "event": False, "loading": False, "map": "SyntheticZone"}},
        max_age_ms=500)
    assert sample.fresh is True and sample.age_ms == 0 and sample.controllable is True
    far = sample_from({"frame": 1, "game": {"frame": 1, "t": now + 5, "event": False, "loading": False, "map": "SyntheticZone"}}, max_age_ms=500)
    assert far.fresh is None and far.capabilities["freshness"] is True


async def test_a_wait_does_not_give_up_on_a_sample_that_is_briefly_unusable(sandbox):
    # Freshness IS supported by this game (the samples carry a frame and a time); a stamp that cannot be aged is not "unsupported".
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        fake.future = 5
        terminal, record = await submit(client, deps, "session_teleport", run_id=run_id, destination_id=1)
        assert terminal.state == State.COMPLETED and record["arrived"] is True and record["controllable"] is True
        assert record["state"]["game"]["map"] == "SyntheticAnnex"
    finally:
        await fake.close()


# ---- launch switches

async def test_launch_env_lines_follow_the_profile(sandbox):
    root, deps, service, client = sandbox
    (root / "game-info.json").write_text(json.dumps(synthetic_info()))
    path = root / "catalogue.json"
    cat = json.loads(path.read_text())
    cat["builds"]["synthetic"]["game_info"] = str(root / "game-info.json")
    cat["profiles"] = {"plain": {"debug": True}, "tools": {"debug": True, "debug_tools": True},
        "memory": {"debug": True, "memory": "rw"}, "hearts": {"debug": True, "protect_hearts": True},
        "all": {"debug": True, "debug_tools": True, "memory": "rw", "protect_hearts": True}, "ordinary": {}}
    path.write_text(json.dumps(cat))
    base = {"HOS_CONTROL", "HOS_HEADLESS", "HOS_OUTPUT_RES", "HOS_INPUT_EXCLUSIVE", "RX_VK_SHOT_EVERY", "RX_VK_SHOT_MENU"}
    for name, extra in (("ordinary", set()), ("plain", set()), ("tools", {"HOS_OOT_CHEATS", "HOS_INPUT_LIVE"}),
                        ("memory", {"HOS_CONTROL_MEM"}), ("hearts", {"HOS_OOT_PROTECT_HEARTS"}),
                        ("all", {"HOS_OOT_CHEATS", "HOS_INPUT_LIVE", "HOS_CONTROL_MEM", "HOS_OOT_PROTECT_HEARTS"})):
        for stale in ("pids.json", "game-env.json"):
            (root / stale).unlink(missing_ok=True)
        launch = await service.launch_impl("synthetic", None, name, 30, "none", f"env-{name}")
        await observed(lambda: (root / "pids.json").exists())
        run_id = deps.registry.get_job(launch.job_id).run_ids[0]
        session = service.sessions[run_id]
        env = json.loads((root / "game-env.json").read_text())
        assert set(env) == base | extra, name
        lines = (session.root / "extra-env.txt").read_text().splitlines()
        assert [line.split("=")[0] for line in lines if line.split("=")[0] not in base] == [
            key for key in ("HOS_OOT_CHEATS", "HOS_INPUT_LIVE", "HOS_CONTROL_MEM", "HOS_OOT_PROTECT_HEARTS") if key in extra]
        if "HOS_OOT_CHEATS" in extra:
            assert env["HOS_OOT_CHEATS"] == "1" and env["HOS_INPUT_LIVE"] == str(session.live_path)
            assert session.live_path == session.root / "debug-live.txt" and session.live_path.read_bytes() == b""
            assert oct(session.live_path.stat().st_mode & 0o777) == "0o600"
        else:
            assert session.live_path is None and not (session.root / "debug-live.txt").exists()
        assert env.get("HOS_CONTROL_MEM") == ("rw" if "HOS_CONTROL_MEM" in extra else None)
        assert env.get("HOS_OOT_PROTECT_HEARTS") == ("1" if "HOS_OOT_PROTECT_HEARTS" in extra else None)
        assert session.game_info_path == root / "game-info.json"
        await deps.supervisor.cancel(launch.job_id)
        await finished(deps, launch)


# ---- debug actions

async def test_time_action_is_requested_never_verified(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        terminal, record = await debug(client, deps, run_id, {"kind": "time", "hour": 3})
        assert terminal.state == State.COMPLETED
        assert (record["kind"], record["line_sent"], record["action_number"]) == ("time", True, 703)
        assert record["game_said"] == ["cheats: requested 03:00"] and record["effect"] == "requested"
        assert record["item"] is None and record["observed_at"]
        assert record["before"]["pos"] == [10, 0, -20] and record["after"]["life"] == 48 and record["after"]["event"] is False
        assert fake.polls == [[703]] and fake.live.read_bytes() == b"!cheat 703\n"
        fake.clock = False
        terminal, record = await debug(client, deps, run_id, {"kind": "time", "hour": 23})
        assert record["effect"] == "not_applied" and record["game_said"] == ["cheats: world clock unavailable"]
        assert record["action_number"] == 723 and fake.polls == [[703], [723]]  # one line per poll
    finally:
        await fake.close()


async def test_item_quantity_is_verified_through_the_count_flag(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        terminal, record = await debug(client, deps, run_id, {"kind": "item", "name": ITEM_B, "change": 3})
        assert record["action_number"] == 5000 + 512 + 64 + 3 and record["effect"] == "verified"
        assert record["item"] == {"name": ITEM_B, "index": 1, "count_before": 5, "count_after": 8, "had": 5, "now": 8}
        assert record["game_said"] == ["cheats: inventory Synthetic B +3 (had 5, now 8, event status 0)"]
        terminal, record = await debug(client, deps, run_id, {"kind": "item", "name": ITEM_B, "change": -2})
        assert record["action_number"] == 5000 + 512 + 64 - 2 and record["effect"] == "verified"
        assert (record["item"]["count_before"], record["item"]["count_after"]) == (8, 6)
        # The game's own cap: what is read back differs from what was asked.
        fake.item_cap = 7
        terminal, record = await debug(client, deps, run_id, {"kind": "item", "name": ITEM_B, "change": 63})
        assert record["effect"] == "not_applied" and record["item"]["count_after"] == 7
        assert record["action_number"] == 5000 + 512 + 64 + 63
        assert fake.polls == [[5579], [5574], [5639]]
    finally:
        await fake.close()


async def test_asynchronous_pickup_is_waited_for_but_the_games_words_stay_unverified(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        fake.pickup_delay = 0.4
        terminal, record = await debug(client, deps, run_id, {"kind": "item", "name": ITEM_B, "change": 4})
        assert record["item"]["had"] == 5 and record["item"]["now"] == 5  # what the game said right after the line
        assert record["item"]["count_after"] == 9 and record["effect"] == "verified"  # what the flag showed later
    finally:
        await fake.close()


async def test_item_toggle_reads_the_pouch_count_and_item_kinds_are_enforced(sandbox):
    # The game's have flag (IsGet) is set when an item is got and never cleared when one is taken away: a removal read from it
    # looks not applied (the first real game showed it with a Kokiri Sword), so the pouch count is read when the game has one.
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        terminal, record = await debug(client, deps, run_id, {"kind": "item_toggle", "name": ITEM_A})
        assert record["action_number"] == 5000 + 300 and record["effect"] == "verified"
        assert (record["item"]["count_before"], record["item"]["count_after"]) == (0, 1)
        terminal, record = await debug(client, deps, run_id, {"kind": "item_toggle", "name": ITEM_A})
        assert (record["item"]["count_before"], record["item"]["count_after"]) == (1, 0) and record["effect"] == "verified"
        assert fake.flag_value(HAVE_FLAG) == 1
        assert fake.flag_value(STOCK_FLAG) == 0
        for action in ({"kind": "item", "name": ITEM_A, "change": 1}, {"kind": "item_toggle", "name": ITEM_B},
                       {"kind": "item", "name": "Synthetic_Item_Z", "change": 1}, {"kind": "item", "name": ITEM_B.lower(), "change": 1},
                       {"kind": "item_toggle", "name": ""}):
            reply = await client.call_tool("session_debug", {"run_id": run_id, "action": action, "idempotency_key": "kinds"},
                raise_on_error=False)
            assert reply.is_error and code_of(reply) == "invalid_argument", action
        assert fake.polls == [[5300], [5300]]
    finally:
        await fake.close()


async def test_a_toggle_with_only_the_have_flag_cannot_prove_a_removal(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        del fake.flags[STOCK_FLAG]    # the game has no count flag for this item
        terminal, record = await debug(client, deps, run_id, {"kind": "item_toggle", "name": ITEM_A})
        assert record["effect"] == "verified" and (record["item"]["count_before"], record["item"]["count_after"]) == (0, 1)
        terminal, record = await debug(client, deps, run_id, {"kind": "item_toggle", "name": ITEM_A})
        assert record["effect"] == "requested" and (record["item"]["count_before"], record["item"]["count_after"]) == (1, 1)
    finally:
        await fake.close()


async def test_without_configured_flags_or_values_an_item_is_only_requested(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service, info=synthetic_info(flags=False))
    try:
        terminal, record = await debug(client, deps, run_id, {"kind": "item", "name": ITEM_B, "change": 2})
        assert record["effect"] == "requested"
        assert record["item"] == {"name": ITEM_B, "index": 1, "count_before": None, "count_after": None, "had": 0, "now": 0}
    finally:
        await fake.close()
    # Flags are configured but the game does not know this item's flag (a null subscription value).
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        terminal, record = await debug(client, deps, run_id, {"kind": "item", "name": ITEM_C, "change": 2})
        assert record["effect"] == "requested" and record["item"]["count_before"] is None
    finally:
        await fake.close()


async def test_mark_and_return_are_verified_by_position(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        terminal, record = await debug(client, deps, run_id, {"kind": "return_to_mark"})
        assert record["effect"] == "not_applied" and record["game_said"] == ["cheats: no mark for this player controller"]
        assert record["action_number"] == 12
        terminal, record = await debug(client, deps, run_id, {"kind": "mark"})
        assert record["action_number"] == 11 and record["effect"] == "requested"
        assert record["game_said"] == ["cheats: marked position " + " ".join(f"{v:.1f}" for v in (10, 0, -20))]
        assert session.marked == [10, 0, -20]
        fake.pos = [300, 4, 5]
        terminal, record = await debug(client, deps, run_id, {"kind": "return_to_mark"})
        assert record["effect"] == "verified" and record["before"]["pos"] == [300, 4, 5] and record["after"]["pos"] == [10, 0, -20]
        fake.pos, fake.stuck = [300, 4, 5], True  # acknowledged, but Link did not move
        terminal, record = await debug(client, deps, run_id, {"kind": "return_to_mark"})
        assert record["effect"] == "not_applied" and record["after"]["pos"] == [300, 4, 5]
        fake.stuck = False
        fake.nulls = {"pos"}
        terminal, record = await debug(client, deps, run_id, {"kind": "return_to_mark"})
        assert record["effect"] == "requested" and record["after"]["pos"] is None
    finally:
        await fake.close()


async def test_return_to_a_mark_made_outside_this_server_uses_the_games_own_line(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        fake.mark, fake.pos = [7, 8, 9], [100, 100, 100]
        terminal, record = await debug(client, deps, run_id, {"kind": "return_to_mark"})
        assert session.marked is None and record["effect"] == "verified"
        assert record["after"]["pos"] == [7, 8, 9]
    finally:
        await fake.close()


async def test_log_excerpt_is_bounded_sanitized_and_starts_after_the_line(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        with fake.log.open("a") as stream:
            stream.write("cheats: an older line\nunrelated line\n")
        fake.noise = ["cheats: " + "x" * 500, "cheats: \x1b[31mcolor\x1b[0m\there\rcarriage", "unrelated line",
                      *[f"cheats: noise {n}" for n in range(12)]]
        terminal, record = await debug(client, deps, run_id, {"kind": "time", "hour": 1})
        said = record["game_said"]
        assert len(said) == 8 and all(len(line) <= 200 for line in said)
        assert said[0] == "cheats: " + "x" * 192
        assert said[1] == "cheats: [31mcolor[0m herecarriage"
        assert said[2:] == [f"cheats: noise {n}" for n in range(6)]
        assert not any(ord(c) < 32 for line in said for c in line)
        assert "older" not in json.dumps(record) and "unrelated" not in json.dumps(record)
    finally:
        await fake.close()


async def test_silent_game_leaves_the_request_unverified(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        fake.silent = True
        began = time.monotonic()
        terminal, record = await debug(client, deps, run_id, {"kind": "mark"})
        assert 1.5 <= time.monotonic() - began < 6  # waits about two seconds for the game's words
        assert record["game_said"] == [] and record["effect"] == "requested" and record["line_sent"] is True
    finally:
        await fake.close()


@pytest.mark.parametrize("attribute,value", [("event", True), ("loading", True), ("stale", True), ("sampled", False)])
async def test_no_line_is_queued_behind_a_busy_or_unknown_game(sandbox, attribute, value):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        setattr(fake, attribute, value)
        terminal, _ = await debug(client, deps, run_id, {"kind": "mark"})
        assert terminal.state == State.FAILED and terminal.error.code == "unavailable" and terminal.error.retryable is True
        assert fake.live.read_bytes() == b"" and fake.polls == []
        setattr(fake, attribute, not value if attribute != "sampled" else True)
        terminal, record = await debug(client, deps, run_id, {"kind": "mark"})
        assert terminal.state == State.COMPLETED and record["line_sent"] is True and fake.polls == [[11]]
    finally:
        await fake.close()


async def test_one_debug_action_at_a_time_per_session(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        async with session.debug_lock:
            terminal, _ = await debug(client, deps, run_id, {"kind": "mark"})
            assert terminal.error.code == "busy" and fake.polls == []
            terminal, _ = await submit(client, deps, "session_flag_set", run_id=run_id, name="synthetic.flag", value=True)
            assert terminal.error.code == "busy"
        terminal, record = await debug(client, deps, run_id, {"kind": "mark"})
        assert terminal.state == State.COMPLETED
    finally:
        await fake.close()


async def test_uncertain_outcome_is_never_replayed(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        fake.stall_wait = True  # the line is written, then the game stops answering
        arguments = {"run_id": run_id, "action": {"kind": "time", "hour": 5}, "idempotency_key": "stalled", "timeout_seconds": 0.5}
        job = (await client.call_tool("session_debug", arguments)).data
        terminal = await finished(deps, job)
        assert terminal.state == State.FAILED and terminal.error.code == "uncertain_outcome"
        assert fake.polls == [[705]]
        again = (await client.call_tool("session_debug", arguments)).data
        assert again.job_id == job.job_id
        changed = await client.call_tool("session_debug", {**arguments, "action": {"kind": "time", "hour": 6}}, raise_on_error=False)
        assert code_of(changed) == "invalid_argument"
        await asyncio.sleep(0.2)
        assert fake.polls == [[705]] and fake.live.read_bytes() == b"!cheat 705\n"
    finally:
        await fake.close()


async def test_a_bridge_failure_after_the_line_is_uncertain_not_unavailable(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        fake.hangup_wait = True  # the connection drops right after the line was written
        terminal, _ = await debug(client, deps, run_id, {"kind": "time", "hour": 9}, idempotency_key="hangup")
        assert terminal.state == State.FAILED and terminal.error.code == "uncertain_outcome" and not terminal.error.retryable
        assert fake.polls == [[709]] and fake.live.read_bytes() == b"!cheat 709\n"
    finally:
        await fake.close()


async def test_a_timeout_before_the_line_is_a_plain_timeout(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        service_debug = SessionDebug(service)
        original = fake.custom

        async def slow_status(writer, cmd, command, response):
            if cmd == "status":
                await asyncio.sleep(30)
            return await original(writer, cmd, command, response)
        fake.custom = slow_status
        job = await service_debug.debug_impl(run_id, TimeAction(kind="time", hour=2), 0.4, "slow")
        terminal = await finished(deps, job)
        assert terminal.error.code == "timeout" and fake.polls == [] and fake.live.read_bytes() == b""
    finally:
        await fake.close()


async def test_duplicate_submission_returns_the_first_job_and_one_line(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        arguments = {"run_id": run_id, "action": {"kind": "mark"}, "idempotency_key": "once"}
        first = (await client.call_tool("session_debug", arguments)).data
        second = (await client.call_tool("session_debug", arguments)).data
        assert first.job_id == second.job_id
        await finished(deps, first)
        assert (await client.call_tool("session_debug", arguments)).data.job_id == first.job_id
        assert fake.polls == [[11]]
    finally:
        await fake.close()


@pytest.mark.parametrize("action", [{"kind": "time", "hour": 24}, {"kind": "time", "hour": -1}, {"kind": "time"},
    {"kind": "item", "name": ITEM_B, "change": 0}, {"kind": "item", "name": ITEM_B, "change": 64},
    {"kind": "item", "name": ITEM_B, "change": -65}, {"kind": "item", "name": ITEM_B}, {"kind": "item_toggle"},
    {"kind": "mark", "hour": 1}, {"kind": "teleport"}, {"hour": 1}, "mark"])
async def test_action_schema_is_a_closed_discriminated_union(sandbox, action):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        reply = await client.call_tool("session_debug", {"run_id": run_id, "action": action, "idempotency_key": "schema"},
            raise_on_error=False)
        assert reply.is_error and code_of(reply) == "invalid_argument"
        assert fake.live.read_bytes() == b""
    finally:
        await fake.close()


def test_debug_action_edges():
    from src.models.session_debug import ItemAction, TimeAction
    assert ItemAction(kind="item", name="x", change=-64).change == -64 and ItemAction(kind="item", name="x", change=63).change == 63
    assert TimeAction(kind="time", hour=0).hour == 0 and TimeAction(kind="time", hour=23).hour == 23


async def test_every_precondition_failure_writes_no_line(sandbox):
    root, deps, service, client = sandbox
    action = {"kind": "item", "name": ITEM_B, "change": 1}
    cases = []

    def add(label, code, **kwargs):
        cases.append((label, code, kwargs))
    add("no debug", "refused_by_policy", profile=SessionProfile())
    add("no debug tools", "refused_by_policy", profile=SessionProfile(debug=True))
    add("no live file", "unavailable", live=False)
    add("no game info", "unavailable", game_info=False)
    add("invalid json", "backend_failed", info_file="{not json")
    add("wrong schema", "backend_failed", info_file=json.dumps({**synthetic_info(), "schema": 2}))
    add("extra field", "backend_failed", info_file=json.dumps({**synthetic_info(), "extra": 1}))
    add("oversize", "backend_failed", info_file=" " * (4 * 1024 * 1024 + 1))
    for label, code, kwargs in cases:
        run_id, fake, session = await attach_debug(root, deps, service, **kwargs)
        try:
            reply = await client.call_tool("session_debug", {"run_id": run_id, "action": action, "idempotency_key": "pre"},
                raise_on_error=False)
            assert reply.is_error and code_of(reply) == code, label
            assert (session.root / "debug-live.txt").read_bytes() == b"" and fake.polls == [], label
            assert session.game_info is None, label
        finally:
            await fake.close()
    # A live file replaced by a link, and game info outside the registered roots or behind a link, are refused too.
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        session.live_path.unlink()
        session.live_path.symlink_to(root / "protected")
        assert code_of(await client.call_tool("session_debug", {"run_id": run_id, "action": action, "idempotency_key": "l"},
            raise_on_error=False)) == "unavailable"
        session.live_path.unlink()
        session.live_path.write_text("")
        outside = root / "protected" / "info.json"
        outside.write_text(json.dumps(synthetic_info()))
        session.game_info_path = outside
        assert code_of(await client.call_tool("session_debug", {"run_id": run_id, "action": action, "idempotency_key": "o"},
            raise_on_error=False)) == "refused_by_policy"
        link = session.root / "link.json"
        link.symlink_to(session.root / "game-info.json")
        session.game_info_path = link
        assert code_of(await client.call_tool("session_debug", {"run_id": run_id, "action": action, "idempotency_key": "s"},
            raise_on_error=False)) == "refused_by_policy"
        session.game_info_path = session.root / "missing.json"
        assert code_of(await client.call_tool("session_debug", {"run_id": run_id, "action": action, "idempotency_key": "m"},
            raise_on_error=False)) == "unavailable"
        assert fake.live.read_bytes() == b"" and fake.polls == []
        # An hour beyond the build's own clock length is refused before any line.
        session.game_info_path = session.root / "game-info.json"
        info = synthetic_info()
        info["actions"]["time_hours"] = 12
        (session.root / "game-info.json").write_text(json.dumps(info))
        assert code_of(await client.call_tool("session_debug", {"run_id": run_id, "action": {"kind": "time", "hour": 12},
            "idempotency_key": "h"}, raise_on_error=False)) == "invalid_argument"
        assert fake.live.read_bytes() == b""
        # Not owned, and not active.
        foreign = deps.registry.create_run(state=State.RUNNING)
        assert code_of(await client.call_tool("session_debug", {"run_id": foreign.run_id, "action": action,
            "idempotency_key": "f"}, raise_on_error=False)) == "refused_by_policy"
        deps.registry.update_run(run_id, state=State.COMPLETED)
        assert code_of(await client.call_tool("session_debug", {"run_id": run_id, "action": action, "idempotency_key": "d"},
            raise_on_error=False)) == "unavailable"
        assert fake.live.read_bytes() == b""
    finally:
        await fake.close()


async def test_game_info_is_loaded_once_and_cached_on_the_session(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        await debug(client, deps, run_id, {"kind": "mark"})
        loaded = session.game_info
        assert loaded is not None and loaded.actions.return_to_mark == 12
        session.game_info_path.write_text("{")  # a later damaged file does not matter: the validated copy is cached
        terminal, record = await debug(client, deps, run_id, {"kind": "return_to_mark"})
        assert terminal.state == State.COMPLETED and session.game_info is loaded
    finally:
        await fake.close()


# ---- flags (one-shot subscription on a dedicated connection)

async def test_flags_by_name_hash_and_alias_with_unknown_as_null(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        await client.call_tool("session_state", {"run_id": run_id})  # the session's own connection
        before = fake.connections
        hashed = f"0x{murmur3_32(b'synthetic.flag'):08x}"
        reply = await client.call_tool("session_flags", {"run_id": run_id, "names": [
            "synthetic.counter", hashed, "life", "synthetic.scale", "synthetic.absent", "synthetic.text", "synthetic.enum",
            "synthetic.long", "0x00000000"]})
        page = reply.data
        assert page.flags == {"synthetic.counter": 7, hashed: 0, "life": 48, "synthetic.scale": 1.5, "synthetic.absent": None,
            "synthetic.text": "hello", "synthetic.enum": "#0000002a", "synthetic.long": None, "0x00000000": None}
        assert page.frame is not None and page.sample_frame is not None and page.observed_at
        assert fake.connections == before + 1  # a dedicated connection, closed again
        sent = [c for c in fake.commands if c["cmd"] in {"subscribe", "unsubscribe"}]
        assert [c["cmd"] for c in sent] == ["subscribe", "unsubscribe"]
        assert sent[0]["events"] == ["oot"] and sent[0]["changes"] is False and sent[0]["every"] == 1
        assert sorted(sent[0]["flags"]) == sorted({"synthetic.counter", hashed, "synthetic.life", "synthetic.scale",
            "synthetic.absent", "synthetic.text", "synthetic.enum", "synthetic.long", "0x00000000"})
        assert reply.structured_content["flags"]["life"] == 48
        assert not [c for c in fake.commands if c["cmd"] in {"mem_read", "mem_write"}]  # no memory opt-in needed
    finally:
        await fake.close()


async def test_flags_skip_old_snapshots_and_work_without_game_info(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service, game_info=False, memory="off")
    try:
        fake.stale_first = True
        page = (await client.call_tool("session_flags", {"run_id": run_id, "names": ["synthetic.counter", "life"]})).data
        assert page.flags == {"synthetic.counter": 7, "life": None}  # no game info: "life" is just a name
        fake.memory = "off"
        assert (await client.call_tool("session_flags", {"run_id": run_id, "names": ["synthetic.flag"]})).data.flags == {"synthetic.flag": 0}
    finally:
        await fake.close()


async def test_flags_arguments_and_ownership(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        for names in ([], [f"synthetic.n{n}" for n in range(17)], ["bad name"], ["x" * 48], [""], ["a/b"], [5]):
            reply = await client.call_tool("session_flags", {"run_id": run_id, "names": names}, raise_on_error=False)
            assert reply.is_error and code_of(reply) == "invalid_argument", names
        assert not [c for c in fake.commands if c["cmd"] == "subscribe"]
        assert (await client.call_tool("session_flags", {"run_id": run_id, "names": ["x" * 47, "0x1234abcd"]})).data.flags == {
            "x" * 47: None, "0x1234abcd": None}
        foreign = deps.registry.create_run(state=State.RUNNING)
        assert code_of(await client.call_tool("session_flags", {"run_id": foreign.run_id, "names": ["a"]},
            raise_on_error=False)) == "refused_by_policy"
        deps.registry.update_run(run_id, state=State.COMPLETED)
        assert code_of(await client.call_tool("session_flags", {"run_id": run_id, "names": ["a"]}, raise_on_error=False)) == "unavailable"
    finally:
        await fake.close()
