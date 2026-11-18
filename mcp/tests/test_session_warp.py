"""session_warp: Link put at coordinates by the game's own return-to-mark path (the live file's `!place X Y Z`), read back from the state sample."""
import json

from src.models import State
from src.models.session import SessionProfile
from test_session import sandbox  # noqa: F401  (fixture)
from test_session_debug import attach_debug, code_of, submit


async def warp(client, deps, run_id, x, y, z, **extra):
    return await submit(client, deps, "session_warp", run_id=run_id, x=x, y=y, z=z, **extra)


async def test_a_warp_is_verified_by_the_position_read_back(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        terminal, record = await warp(client, deps, run_id, 11.0, 2.0, -5.5)
        assert terminal.state == State.COMPLETED and record["effect"] == "verified", record
        assert record["target"] == [11.0, 2.0, -5.5] and record["after"]["pos"] == [11.0, 2.0, -5.5]
        assert record["before"]["pos"] == [10, 0, -20] and any("returned to 11.0 2.0 -5.5" in line for line in record["game_said"])
        assert record["samples"] and all(s["dist"] <= 0.75 for s in record["samples"] if not s.get("stale"))
        assert fake.placed == [[11.0, 2.0, -5.5]]
        assert "!place 11.0000 2.0000 -5.5000" in (root / run_id / "debug-live.txt").read_text()
    finally:
        await fake.close()


async def test_a_game_that_puts_him_back_is_partial_and_says_what_was_seen(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        fake.pull_after = 0.7
        terminal, record = await warp(client, deps, run_id, 30.0, 2.0, 30.0)
        assert record["effect"] == "partial" and "put him back" in record["note"], record
        assert record["samples"][-1]["dist"] > 5 and record["after"]["pos"] == [10, 0, -20]
    finally:
        await fake.close()


async def test_a_build_without_the_command_says_nothing_and_is_not_applied(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        fake.place_supported = False
        terminal, record = await warp(client, deps, run_id, 40.0, 2.0, 40.0)
        assert record["effect"] == "not_applied" and "!place" in record["note"] and record["game_said"] == [], record
        assert record["after"]["pos"] == [10, 0, -20]
    finally:
        await fake.close()


async def test_preconditions_fail_before_a_line_is_written(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    live = root / run_id / "debug-live.txt"
    try:
        for bad in ({"x": float("nan"), "y": 0, "z": 0}, {"x": 1e9, "y": 0, "z": 0}, {"x": 1, "y": 0}):
            reply = await client.call_tool("session_warp", {"run_id": run_id, "idempotency_key": "bad", **bad}, raise_on_error=False)
            assert reply.is_error, bad
        fake.event = True    # a cutscene: the game would hold the line and fire it later
        reply = await client.call_tool("session_warp", {"run_id": run_id, "x": 1, "y": 2, "z": 3, "idempotency_key": "evt"}, raise_on_error=False)
        terminal = None
        if not reply.is_error:
            from test_session import finished
            terminal = await finished(deps, reply.data)
            assert terminal.state != State.COMPLETED and terminal.error.code == "unavailable" and terminal.error.retryable
        assert "!place" not in live.read_text()
    finally:
        await fake.close()
    other_id, other, _ = await attach_debug(root, deps, service, profile=SessionProfile(debug=True, debug_tools=False, memory="off"))
    try:
        reply = await client.call_tool("session_warp", {"run_id": other_id, "x": 1, "y": 2, "z": 3, "idempotency_key": "nodebug"}, raise_on_error=False)
        assert reply.is_error and code_of(reply) == "refused_by_policy"
        assert "!place" not in (root / other_id / "debug-live.txt").read_text()
    finally:
        await other.close()
