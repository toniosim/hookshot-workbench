"""Typed flag writes through guest memory, and snapshots of the disposable user folder, against a synthetic game."""
import hashlib
import json
import struct
import time

import pytest
from src.effects import session_storage
from src.effects.session import SessionService
from src.effects.session_debug import SessionDebug
from src.effects.session_memory import murmur3_32
from src.errors import WorkbenchError
from src.models import State
from src.models.session import SessionProfile
from test_session import finished, observed, result, sandbox  # noqa: F401  (fixture)
from test_session_debug import GAME, attach_debug, code_of, submit, synthetic_info

MEMORY_PROFILE = SessionProfile(debug=True, memory="rw")


async def set_flag(client, deps, run_id, name, value, **extra):
    return await submit(client, deps, "session_flag_set", run_id=run_id, name=name, value=value, **extra)


def hashed(name):
    return f"0x{murmur3_32(name.encode()):08x}"


# ---- flag_set: lookup, kinds, read-back

async def test_each_kind_is_found_written_and_read_back_two_ways(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service, profile=MEMORY_PROFILE)
    try:
        terminal, record = await set_flag(client, deps, run_id, "synthetic.flag", True)
        assert terminal.state == State.COMPLETED
        assert record == {"name": "synthetic.flag", "hash": hashed("synthetic.flag"), "kind": "bool", "before": False,
            "written": True, "after_memory": True, "after_flag": 1, "effect": "verified", "observed_at": record["observed_at"]}
        assert fake.flag_value("synthetic.flag") == 1
        terminal, record = await set_flag(client, deps, run_id, "synthetic.delta", 12)
        assert (record["kind"], record["before"], record["written"], record["after_memory"], record["after_flag"]) == ("int", -3, 12, 12, 12)
        terminal, record = await set_flag(client, deps, run_id, "synthetic.counter", 4000000000)
        assert (record["kind"], record["before"], record["after_memory"], record["after_flag"], record["effect"]) == (
            "uint", 7, 4000000000, 4000000000, "verified")
        terminal, record = await set_flag(client, deps, run_id, "synthetic.scale", 2.25)
        assert record["kind"] == "float" and record["before"] == 1.5 and record["effect"] == "verified"
        assert {record["written"], record["after_memory"], record["after_flag"]} == {2.25}
        terminal, record = await set_flag(client, deps, run_id, "synthetic.scale", 0.1)  # not exactly representable in 32 bits
        assert record["written"] == struct.unpack("<f", struct.pack("<f", 0.1))[0] == record["after_memory"]
        assert record["after_flag"] == 0.1 and record["effect"] == "verified"
        assert "addr" not in json.dumps(record) and str(fake.flags["synthetic.scale"][1]) not in json.dumps(record)
        # bool accepts 0 and 1 as well
        terminal, record = await set_flag(client, deps, run_id, "synthetic.flag", 0)
        assert record["written"] is False and record["before"] is True and record["effect"] == "verified"
    finally:
        await fake.close()


async def test_alias_hash_and_explicit_kind(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service, profile=MEMORY_PROFILE)
    try:
        terminal, record = await set_flag(client, deps, run_id, "life", 40)
        assert record["name"] == "life" and record["hash"] == hashed("synthetic.life") and record["kind"] == "int"
        assert fake.flag_value("synthetic.life") == 40 and record["effect"] == "verified"
        terminal, record = await set_flag(client, deps, run_id, hashed("synthetic.flag"), 1)
        assert record["name"] == hashed("synthetic.flag") and record["hash"] == hashed("synthetic.flag") and record["kind"] == "bool"
        terminal, record = await set_flag(client, deps, run_id, "synthetic.counter", 9, kind="uint")
        assert record["kind"] == "uint" and record["after_memory"] == 9
        before = bytes(fake.mem)
        terminal, _ = await set_flag(client, deps, run_id, "synthetic.counter", 9, kind="int")  # it lives in the uint container
        assert terminal.error.code == "not_found" and bytes(fake.mem) == before
    finally:
        await fake.close()


async def test_probing_follows_collisions_and_wraps_around(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service, profile=MEMORY_PROFILE)
    try:
        slots = fake.TABLE_SLOTS["bool"]
        names = []
        index = 0
        while len(names) < 3:  # three names hashing to the last slot: the third wraps around to the first
            index += 1
            candidate = f"synthetic.wrap.{index}"
            if murmur3_32(candidate.encode()) % slots == slots - 1:
                names.append(candidate)
        for name in names:
            fake.add_flag("bool", name, 0)
        for name in names:
            terminal, record = await set_flag(client, deps, run_id, name, True)
            assert record["effect"] == "verified" and fake.flag_value(name) == 1, name
        chain = GAME.colliding("synthetic.delta", fake.TABLE_SLOTS["int"], 4)
        for name in chain:
            fake.add_flag("int", name, 0)
        terminal, record = await set_flag(client, deps, run_id, chain[-1], 77)
        assert record["kind"] == "int" and record["after_memory"] == 77 and fake.flag_value(chain[-1]) == 77
        assert fake.flag_value("synthetic.delta") == -3
    finally:
        await fake.close()


async def test_absent_flag_changes_nothing(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service, profile=MEMORY_PROFILE)
    try:
        before = bytes(fake.mem)
        for name in ("synthetic.absent", "synthetic.text", "synthetic.enum"):  # unknown, text and enum flags are not in a typed container
            terminal, _ = await set_flag(client, deps, run_id, name, 1)
            assert terminal.error.code == "not_found", name
        assert bytes(fake.mem) == before and not [c for c in fake.commands if c["cmd"] == "mem_write"]
    finally:
        await fake.close()


async def test_a_value_the_game_changes_back_is_not_applied(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service, profile=MEMORY_PROFILE)
    try:
        fake.recompute["synthetic.flag"] = 0  # the game recomputes this every present
        terminal, record = await set_flag(client, deps, run_id, "synthetic.flag", True)
        assert terminal.state == State.COMPLETED and record["effect"] == "not_applied"
        assert record["written"] is True and record["after_memory"] is True and record["after_flag"] == 0
        fake.recompute.clear()
        fake.ignore_writes = True  # acknowledged, but nothing changed
        terminal, record = await set_flag(client, deps, run_id, "synthetic.counter", 99)
        assert record["effect"] == "not_applied" and record["after_memory"] == 7 and record["written"] == 99
        waits = [c for c in fake.commands if c["cmd"] == "wait" and c.get("frames") == 20]
        assert len(waits) == 2  # the flag read-back follows 20 presents
    finally:
        await fake.close()


@pytest.mark.parametrize("mode", ["off", "ro"])
async def test_memory_not_enabled_in_the_game_is_refused_by_policy(sandbox, mode):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service, profile=MEMORY_PROFILE, memory=mode)
    try:
        before = bytes(fake.mem)
        terminal, _ = await set_flag(client, deps, run_id, "synthetic.flag", True)
        assert terminal.error.code == "refused_by_policy" and bytes(fake.mem) == before
        if mode == "ro":
            assert [c["cmd"] for c in fake.commands if c["cmd"].startswith("mem_")][-1] == "mem_write"
    finally:
        await fake.close()


async def test_out_of_range_and_uninitialised_stores_are_typed_failures(sandbox):
    root, deps, service, client = sandbox
    far = synthetic_info()
    far["layout"]["holder"] = 70000  # beyond the synthetic guest memory
    run_id, fake, session = await attach_debug(root, deps, service, profile=MEMORY_PROFILE, info_file=json.dumps(far))
    try:
        terminal, _ = await set_flag(client, deps, run_id, "synthetic.flag", True)
        assert terminal.error.code == "backend_failed"
        assert not [c for c in fake.commands if c["cmd"] == "mem_write"]
    finally:
        await fake.close()
    run_id, fake, session = await attach_debug(root, deps, service, profile=MEMORY_PROFILE)
    try:
        struct.pack_into("<Q", fake.mem, synthetic_info()["layout"]["holder"], 0)  # the game has not built its flag store
        terminal, _ = await set_flag(client, deps, run_id, "synthetic.flag", True)
        assert terminal.error.code == "unavailable" and terminal.error.retryable is True
    finally:
        await fake.close()


@pytest.mark.parametrize("name,value,kind", [("synthetic.flag", 1.5, None), ("synthetic.flag", 2, None), ("synthetic.delta", 2**31, None),
    ("synthetic.delta", 1.5, None), ("synthetic.counter", -1, None), ("synthetic.counter", 2**32, None), ("synthetic.scale", True, None),
    ("synthetic.scale", 3.5e38, None), ("synthetic.delta", True, None)])
async def test_values_the_kind_cannot_hold_write_nothing(sandbox, name, value, kind):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service, profile=MEMORY_PROFILE)
    try:
        before = bytes(fake.mem)
        terminal, _ = await set_flag(client, deps, run_id, name, value)
        assert terminal.error.code == "invalid_argument" and bytes(fake.mem) == before
        assert not [c for c in fake.commands if c["cmd"] == "mem_write"]
    finally:
        await fake.close()


async def test_flag_set_arguments_and_preconditions_write_nothing(sandbox):
    root, deps, service, client = sandbox
    cases = [("debug profile without memory", "refused_by_policy", dict(profile=SessionProfile(debug=True))),
             ("no debug", "refused_by_policy", dict(profile=SessionProfile())),
             ("no game info", "unavailable", dict(profile=MEMORY_PROFILE, game_info=False)),
             ("no layout", "unavailable", dict(profile=MEMORY_PROFILE, info=synthetic_info(layout=False), populate=False))]
    for label, code, kwargs in cases:
        run_id, fake, session = await attach_debug(root, deps, service, **kwargs)
        try:
            reply = await client.call_tool("session_flag_set", {"run_id": run_id, "name": "synthetic.flag", "value": True,
                "idempotency_key": "pre"}, raise_on_error=False)
            assert reply.is_error and code_of(reply) == code, label
            assert not [c for c in fake.commands if c["cmd"].startswith("mem_")], label
        finally:
            await fake.close()
    run_id, fake, session = await attach_debug(root, deps, service, profile=MEMORY_PROFILE)
    try:
        for arguments in ({"name": "bad name", "value": 1}, {"name": "synthetic.flag", "value": "1"}, {"name": "synthetic.flag", "value": None},
                          {"name": "synthetic.flag", "value": 1, "kind": "text"}, {"name": "synthetic.flag", "value": 5, "kind": "bool"},
                          {"name": "synthetic.scale", "value": 1.5, "kind": "int"}, {"name": "x" * 48, "value": 1}):
            reply = await client.call_tool("session_flag_set", {"run_id": run_id, "idempotency_key": "args", **arguments}, raise_on_error=False)
            assert reply.is_error and code_of(reply) == "invalid_argument", arguments
        with pytest.raises(WorkbenchError) as failure:
            await SessionDebug(service).flag_set_impl(run_id, "synthetic.scale", float("inf"), None, 5, "inf")
        assert failure.value.envelope.code == "invalid_argument"
        assert not [c for c in fake.commands if c["cmd"].startswith("mem_")]
        foreign = deps.registry.create_run(state=State.RUNNING)
        reply = await client.call_tool("session_flag_set", {"run_id": foreign.run_id, "name": "synthetic.flag", "value": True,
            "idempotency_key": "foreign"}, raise_on_error=False)
        assert code_of(reply) == "refused_by_policy"
    finally:
        await fake.close()


@pytest.mark.parametrize("knob", ["drop_write", "stall_wait", "hangup_wait"])
async def test_uncertain_flag_write_is_never_replayed(sandbox, knob):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service, profile=MEMORY_PROFILE)
    try:
        setattr(fake, knob, True)  # the write's reply never comes / the read-back never comes
        arguments = {"run_id": run_id, "name": "synthetic.flag", "value": True, "idempotency_key": "uncertain", "timeout_seconds": 0.6}
        job = (await client.call_tool("session_flag_set", arguments)).data
        terminal = await finished(deps, job)
        assert terminal.state == State.FAILED and terminal.error.code == "uncertain_outcome"
        assert (await client.call_tool("session_flag_set", arguments)).data.job_id == job.job_id
        assert len([c for c in fake.commands if c["cmd"] == "mem_write"]) == 1
        assert fake.flag_value("synthetic.flag") == 1
    finally:
        await fake.close()


async def test_lookup_timeout_is_a_plain_timeout(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service, profile=MEMORY_PROFILE)
    try:
        original = fake.custom

        async def slow(writer, cmd, command, response):
            if cmd.startswith("mem_read"):
                import asyncio
                await asyncio.sleep(30)
            return await original(writer, cmd, command, response)
        fake.custom = slow
        job = await SessionDebug(service).flag_set_impl(run_id, "synthetic.flag", True, None, 0.4, "slow-lookup")
        terminal = await finished(deps, job)
        assert terminal.error.code == "timeout" and not [c for c in fake.commands if c["cmd"] == "mem_write"]
    finally:
        await fake.close()


# ---- snapshot

def seed_user(session, files=None):
    user = session.root / "user"
    (user / "slot_00").mkdir(parents=True)
    for name, data in (files or {"slot_00/progress.sav": b"synthetic progress", "account.sav": b"synthetic account"}).items():
        (user / name).write_bytes(data)
    return user


async def snapshot(client, deps, run_id, key=None):
    return await submit(client, deps, "session_snapshot", run_id=run_id, **({"idempotency_key": key} if key else {}))


async def test_snapshot_copies_the_user_folder_with_manifest_and_state(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        user = seed_user(session)
        before = {p.relative_to(user).as_posix(): p.read_bytes() for p in user.rglob("*") if p.is_file()}
        terminal, record = await snapshot(client, deps, run_id)
        assert terminal.state == State.COMPLETED
        assert record["file_count"] == 2 and record["matches_state"] is None
        assert record["validation_status"] == "copy_only_not_a_checkpoint"
        for phrase in ("not a checkpoint", "next save", "session_launch(save_id=", "title"):
            assert phrase in record["note"]
        assert 0 <= record["slot_age_seconds"] < 60
        clone = root / "clones" / record["save_id"]
        assert record["save_id"].startswith("save_") and len(record["save_id"]) == 37
        assert {p.relative_to(clone / "user").as_posix(): p.read_bytes() for p in (clone / "user").rglob("*") if p.is_file()} == before
        manifest = json.loads((clone / "copy-manifest.json").read_text())
        assert manifest["owner"] == deps.registry.owner and manifest["source_id"] == run_id and manifest["save_id"] == record["save_id"]
        assert {row["file"]: row["sha256"] for row in manifest["files"]} == {
            name: hashlib.sha256(data).hexdigest() for name, data in before.items()}
        assert json.loads((clone / "clone-identity.json").read_text()) == {"save_id": record["save_id"], "owner": deps.registry.owner}
        state = json.loads((clone / "state.json").read_text())
        assert state == record["state"]
        assert (state["map"], state["age"], state["pos"], state["life"], state["max_life"], state["rupees"]) == (
            "SyntheticZone", "child", [10, 0, -20], 48, 48, 100)
        assert state["frame"] is not None and state["fresh"] is True and state["observed_at"]
        assert state["saves_listing"] == [{"slot": "00", "mtime": 100}, {"slot": "01", "mtime": 101}, {"slot": "02", "mtime": 102}]
        artifact = deps.registry.artifact_path(record["copy_hash_manifest"]["id"], deps.paths)
        assert artifact == (clone / "copy-manifest.json").resolve() and record["copy_hash_manifest"]["complete"] is True
        assert str(root) not in json.dumps(record)
        assert {p.relative_to(user).as_posix(): p.read_bytes() for p in user.rglob("*") if p.is_file()} == before
    finally:
        await fake.close()


async def test_snapshot_state_stays_honest_when_the_bridge_cannot_say(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        seed_user(session, {"account.sav": b"synthetic account"})  # no slot file: no slot age
        fake.sampled = False
        fake.nulls = {"pos", "life"}
        terminal, record = await snapshot(client, deps, run_id)
        assert record["slot_age_seconds"] is None
        assert record["state"]["frame"] is None and record["state"]["fresh"] is None
        assert record["state"]["life"] is None and record["state"]["pos"] is None
    finally:
        await fake.close()


async def test_snapshot_refusals_and_deduplication(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        reply = await client.call_tool("session_snapshot", {"run_id": run_id, "idempotency_key": "empty"}, raise_on_error=False)
        assert code_of(reply) == "not_found"  # no user folder yet
        user = seed_user(session)
        (user / "link").symlink_to(root / "protected")
        reply = await client.call_tool("session_snapshot", {"run_id": run_id, "idempotency_key": "link"}, raise_on_error=False)
        assert code_of(reply) == "refused_by_policy"
        assert json.loads(reply.content[0].text)["operation"] == "session_snapshot"
        (user / "link").unlink()
        (user / "slot_00" / "again.sav").hardlink_to(user / "account.sav")
        reply = await client.call_tool("session_snapshot", {"run_id": run_id, "idempotency_key": "hard"}, raise_on_error=False)
        assert code_of(reply) == "refused_by_policy"
        (user / "slot_00" / "again.sav").unlink()
        assert not list((root / "clones").iterdir())  # nothing was copied by a refusal
        first = (await client.call_tool("session_snapshot", {"run_id": run_id, "idempotency_key": "same"})).data
        second = (await client.call_tool("session_snapshot", {"run_id": run_id, "idempotency_key": "same"})).data
        assert first.job_id == second.job_id
        await finished(deps, first)
        assert len(list((root / "clones").iterdir())) == 1
        foreign = deps.registry.create_run(state=State.RUNNING)
        reply = await client.call_tool("session_snapshot", {"run_id": foreign.run_id, "idempotency_key": "f"}, raise_on_error=False)
        assert code_of(reply) == "refused_by_policy"
        session.stopping = True
        reply = await client.call_tool("session_snapshot", {"run_id": run_id, "idempotency_key": "stopping"}, raise_on_error=False)
        assert code_of(reply) == "unavailable"
        session.stopping = False
        deps.registry.update_run(run_id, state=State.COMPLETED)
        reply = await client.call_tool("session_snapshot", {"run_id": run_id, "idempotency_key": "done"}, raise_on_error=False)
        assert code_of(reply) == "unavailable"
        assert len(list((root / "clones").iterdir())) == 1
    finally:
        await fake.close()


async def test_a_file_changing_mid_copy_is_busy(sandbox, monkeypatch):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        user = seed_user(session)
        listed = session_storage.plain_files

        def changing(deps_, source, slot=None, operation="save_clone"):
            files = listed(deps_, source, slot, operation)
            (user / "account.sav").write_bytes(b"the game saved while we were copying")
            return files
        monkeypatch.setattr(session_storage, "plain_files", changing)
        terminal, _ = await snapshot(client, deps, run_id, "busy")
        assert terminal.state == State.FAILED and terminal.error.code == "busy"
        assert terminal.error.operation == "session_snapshot"
    finally:
        await fake.close()


async def test_a_snapshot_id_restores_through_session_launch(sandbox):
    root, deps, service, client = sandbox
    run_id, fake, session = await attach_debug(root, deps, service)
    try:
        user = seed_user(session)
        terminal, record = await snapshot(client, deps, run_id)
        snapshot_id = record["save_id"]
        before = {p.relative_to(user).as_posix(): p.read_bytes() for p in user.rglob("*") if p.is_file()}
    finally:
        await fake.close()
    deps.registry.update_run(run_id, state=State.COMPLETED)  # the snapshotted session is over; a launch needs the lane
    launch = await service.launch_impl("synthetic", snapshot_id, "ordinary", 30, "none", "restore")
    await observed(lambda: (root / "pids.json").exists())
    new_run = deps.registry.get_job(launch.job_id).run_ids[0]
    restored = service.sessions[new_run].root / "user"
    assert {p.relative_to(restored).as_posix(): p.read_bytes() for p in restored.rglob("*") if p.is_file()} == before
    await deps.supervisor.cancel(launch.job_id)
    await finished(deps, launch)
    # A foreign, unregistered or damaged snapshot id is not accepted.
    with pytest.raises(WorkbenchError) as failure:
        await service.launch_impl("synthetic", "save_" + "0" * 32, "ordinary", 30, "none", "unknown-snapshot")
    assert failure.value.envelope.code in {"not_found", "refused_by_policy"}
    marker = root / "clones" / snapshot_id / "clone-identity.json"
    marker.write_text(json.dumps({"save_id": snapshot_id, "owner": "someone-else"}))
    with pytest.raises(WorkbenchError) as failure:
        await service.launch_impl("synthetic", snapshot_id, "ordinary", 30, "none", "foreign-snapshot")
    assert failure.value.envelope.code == "refused_by_policy"
