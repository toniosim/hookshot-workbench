"""Typed, windowless owned sessions. No shell, socket, environment or write-path arguments."""
from typing import Annotated, Literal
from pydantic import Field
from src.effects.session import SessionService
from src.effects.session_debug import SessionDebug
from src.models import Job
from src.models.session import (Cursor, DestinationsPage, Idempotency, InputStep, Key, Label, Limit, LocalId, OptionsChanged,
    OptionsPage, Predicate, RunId, Sample, SavesPage, ShotResult, Timeout)
from src.models.session_debug import Coordinate, DebugAction, FlagKind, FlagName, FlagsRead
from src.policy import Safety, ToolSpec

SPECS = (
    ToolSpec("session_launch", Safety.RUN, "Submit a bounded disposable windowless session through the configured wrapper and gate. The returned Job lasts until exit; use job_read.events.events[] kind=bridge_ready, then session_wait for stable menu/play before input or pictures. Bridge readiness alone is not gameplay.", shell_route="Windowless wrapper setup, gate admission and bridge readiness journal"),
    ToolSpec("session_input", Safety.WRITE_LOCAL, "Submit owned typed input. Frames are game presents; hos at is seconds and duration milliseconds, rounded half away from zero at 60 frames/s. Completion is effect_unverified.", shell_route="Typed control-client sequence or scoped release commands"),
    ToolSpec("session_state", Safety.READ, "Read bounded state with sample age and capability. Missing sampled-frame freshness remains unknown.", shell_route="Control status plus sampled-state age and freshness checks", broker=True),
    ToolSpec("session_wait", Safety.READ, "Submit a bounded observed predicate wait as a Job. Cancelling it never stops the game or resends input.", shell_route="Observed frame/state/map predicates, not guessed boot sleeps", broker=True),
    ToolSpec("session_shot", Safety.WRITE_LOCAL, "Capture to a new server-chosen run path; return artifact metadata, not image bytes. No overlay.", idempotent=False, shell_route="Control screenshot into a fresh registered output"),
    ToolSpec("session_options_get", Safety.READ, "Read bounded canonical settings with a cursor.", shell_route="Bounded canonical control option_get listing", broker=True),
    ToolSpec("session_options_set", Safety.WRITE_LOCAL, "Set owned-run canonical options, returning before/after. Device, window, microphone and resource-class changes refuse.", idempotent=False, shell_route="Scoped control option_set and conditional restoration"),
    ToolSpec("session_teleport", Safety.WRITE_LOCAL, "Submit one debug travel to a bridge-listed destination on a disposable debug profile. The result records the state before, the listed destination and the target map. No replay on uncertain acceptance.", shell_route="One listed debug teleport plus observed arrival checks"),
    ToolSpec("session_age", Safety.WRITE_LOCAL, "Submit one age change on a disposable debug profile; unavailable commands never fall back to cheats. The result records the state before and the target map.", shell_route="Optional typed bridge age command, with no cheat fallback"),
    ToolSpec("session_destinations", Safety.READ, "Read the bridge's bounded teleport destination listing: index plus child and adult map names, as the game reports them.", shell_route="Bridge teleport listing without a destination", broker=True),
    ToolSpec("session_debug", Safety.WRITE_LOCAL, "Submit one Debug-tab action (time of day, item quantity or possession, mark, return to mark) as a line in the owned live input file, on a debug profile with debug tools and the build's game info. Reads back what it can; a game-acknowledged request is not verification. No replay on uncertain outcome.", shell_route="One typed cheat line into the owned live input file, then observed log and state read-back"),
    ToolSpec("session_warp", Safety.WRITE_LOCAL, "Put Link at x, y, z (metres, in the frame of the map he is in) by the game's own return to mark: one `!place X Y Z` line in the owned live input file on a debug profile with debug tools (the game's host needs the `!place` live-input command). Reads his position back for 2 seconds: verified, partial (the game moved him) or not_applied (a build without the command says nothing). Facing is not set. No replay on uncertain outcome.", shell_route="One typed `!place` line into the owned live input file, then observed log and state read-back"),
    ToolSpec("session_flags", Safety.READ, "Read up to 16 game flags by name, hash or game-info alias through a one-shot subscription on a dedicated connection; unknown flags are null. Needs no memory opt-in.", shell_route="One-shot oot flag subscription on its own control connection", broker=True),
    ToolSpec("session_flag_set", Safety.WRITE_LOCAL, "Write one typed flag value through guest memory on a debug profile that opted into memory and has game-info layout; reads it back by memory and flag subscription. No replay on uncertain outcome.", shell_route="Typed flag lookup and write through the opt-in memory commands, then read-back"),
    ToolSpec("session_snapshot", Safety.WRITE_LOCAL, "Copy the running session's disposable user folder into a new registered clone with a hash manifest and a sampled state record. A copy, not a checkpoint; restore with session_launch(save_id=...).", shell_route="Fresh registered copy of the live disposable user folder with hashes and sampled state"),
    ToolSpec("session_saves_list", Safety.READ, "Read bounded owned-session save metadata, not contents; consistency during writes is not guaranteed.", shell_route="Control saves metadata listing, not save-file export", broker=True),
    ToolSpec("save_clone", Safety.WRITE_LOCAL, "Copy a registered save into a new owned directory with a private hash manifest. Never overwrite or modify a library.", shell_route="Fresh disposable copy of a registered seed with hashes"),
    ToolSpec("session_stop", Safety.WRITE_LOCAL, "Submit owned disposable-session stop; observe game exit before gate release. Save draining is unsupported.", destructive=True, shell_route="Owned input/game shutdown before gate release and final receipt"),
)


def register(mcp, deps):
    service = SessionService(deps)
    debug = SessionDebug(service)

    @deps.tool(mcp, "session_launch")
    async def session_launch(build_id: LocalId, profile_id: LocalId, wall_seconds: Annotated[int, Field(ge=1, le=450)],
                             idempotency_key: Idempotency, save_id: LocalId | None = None,
                             capture: Literal["standard", "dense", "none"] = "standard") -> Job:
        return await service.launch_impl(build_id, save_id, profile_id, wall_seconds, capture, idempotency_key)

    @deps.tool(mcp, "session_input")
    async def session_input(run_id: RunId, steps: Annotated[list[InputStep], Field(min_length=1, max_length=64)],
                            units: Literal["frames", "hos"], idempotency_key: Idempotency,
                            timeout_seconds: Timeout = 30) -> Job:
        return await service.input_impl(run_id, steps, units, timeout_seconds, idempotency_key)

    @deps.tool(mcp, "session_state")
    async def session_state(run_id: RunId, max_age_ms: Annotated[int, Field(ge=1, le=10000)] = 500,
                            expected_map: Annotated[str, Field(min_length=1, max_length=80)] | None = None,
                            fields: Annotated[list[Literal["map", "event", "loading", "age", "pos", "life", "max_life", "rupees"]], Field(max_length=8)] | None = None) -> Sample:
        return await service.state_impl(run_id, max_age_ms, expected_map, fields)

    @deps.tool(mcp, "session_wait")
    async def session_wait(run_id: RunId, predicate: Predicate, idempotency_key: Idempotency,
                           timeout_seconds: Timeout = 30, max_age_ms: Annotated[int, Field(ge=1, le=10000)] = 500,
                           stable_frames: Annotated[int, Field(ge=0, le=600)] = 0) -> Job:
        return await service.wait_impl(run_id, predicate, timeout_seconds, max_age_ms, stable_frames, idempotency_key)

    @deps.tool(mcp, "session_shot")
    async def session_shot(run_id: RunId, after_frame: Annotated[int, Field(ge=0)] | None = None, label: Label = "shot") -> ShotResult:
        return await service.shot_impl(run_id, after_frame, label)

    @deps.tool(mcp, "session_options_get")
    async def session_options_get(run_id: RunId, key: Key | None = None, cursor: Cursor = 0, limit: Limit = 25) -> OptionsPage:
        return await service.options_get_impl(run_id, key, cursor, limit)

    @deps.tool(mcp, "session_options_set")
    async def session_options_set(run_id: RunId,
            values: Annotated[dict[Key, int | float | bool], Field(min_length=1, max_length=8)],
            restore_on_finish: bool = False) -> OptionsChanged:
        return await service.options_set_impl(run_id, values, restore_on_finish)

    @deps.tool(mcp, "session_teleport")
    async def session_teleport(run_id: RunId, destination_id: Annotated[int, Field(ge=0, le=255)],
                               idempotency_key: Idempotency, timeout_seconds: Timeout = 30) -> Job:
        return await service.travel_impl(run_id, "teleport", destination_id, timeout_seconds, idempotency_key)

    @deps.tool(mcp, "session_age")
    async def session_age(run_id: RunId, age: Literal["child", "adult"], idempotency_key: Idempotency,
                          timeout_seconds: Timeout = 30) -> Job:
        return await service.travel_impl(run_id, "age", age, timeout_seconds, idempotency_key)

    @deps.tool(mcp, "session_destinations")
    async def session_destinations(run_id: RunId) -> DestinationsPage:
        return await service.destinations_impl(run_id)

    @deps.tool(mcp, "session_debug")
    async def session_debug(run_id: RunId, action: DebugAction, idempotency_key: Idempotency,
                            timeout_seconds: Timeout = 30) -> Job:
        return await debug.debug_impl(run_id, action, timeout_seconds, idempotency_key)

    @deps.tool(mcp, "session_warp")
    async def session_warp(run_id: RunId, x: Coordinate, y: Coordinate, z: Coordinate, idempotency_key: Idempotency,
                           timeout_seconds: Timeout = 30) -> Job:
        return await debug.warp_impl(run_id, x, y, z, timeout_seconds, idempotency_key)

    @deps.tool(mcp, "session_flags")
    async def session_flags(run_id: RunId, names: Annotated[list[FlagName], Field(min_length=1, max_length=16)]) -> FlagsRead:
        return await debug.flags_impl(run_id, names)

    @deps.tool(mcp, "session_flag_set")
    async def session_flag_set(run_id: RunId, name: FlagName, value: bool | int | float, idempotency_key: Idempotency,
                               kind: FlagKind | None = None, timeout_seconds: Timeout = 30) -> Job:
        return await debug.flag_set_impl(run_id, name, value, kind, timeout_seconds, idempotency_key)

    @deps.tool(mcp, "session_snapshot")
    async def session_snapshot(run_id: RunId, idempotency_key: Idempotency) -> Job:
        return await debug.snapshot_impl(run_id, idempotency_key)

    @deps.tool(mcp, "session_saves_list")
    async def session_saves_list(run_id: RunId, cursor: Cursor = 0, limit: Limit = 25) -> SavesPage:
        return await service.saves_list_impl(run_id, cursor, limit)

    @deps.tool(mcp, "save_clone")
    async def save_clone(save_id: LocalId, idempotency_key: Idempotency, slot: Annotated[int, Field(ge=0, le=99)] | None = None) -> Job:
        return await service.clone_impl(save_id, slot, idempotency_key)

    @deps.tool(mcp, "session_stop")
    async def session_stop(run_id: RunId, reason: Annotated[str, Field(min_length=1, max_length=160)],
                           idempotency_key: Idempotency) -> Job:
        return await service.stop_impl(run_id, reason, idempotency_key)
