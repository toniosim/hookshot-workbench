"""Debug tools over an owned session: Debug-tab actions, flag reads and writes, and a user-folder snapshot.

Everything game-specific arrives at run time: from the bridge, from the build's operator-registered game info
(``BuildEntry.game_info``) or from the caller's arguments; none of it is built in here. Actions need a catalogue
profile with ``debug`` (and ``debug_tools`` / ``memory`` where noted). A state-changing call never replays: once its
line or write may have reached the game, any failure is ``uncertain_outcome``. Results report what was read back
from the game; a request the game merely acknowledged is ``requested``, never ``verified``.
"""
import asyncio
import json
import math
import os
from pathlib import Path
import re
import stat
import time

from src.effects.session import FIELDS, Session, number, sample_from
from src.effects.session_bridge import FLAG_NAME, Bridge
from src.effects.session_memory import PROBE_ORDER, WIDTH, FlagMemory, decode, encode, flag_hash
from src.effects.session_storage import catalogue, plain_files
from src.errors import WorkbenchError, fail
from src.effects.names import LOG_NAMES
from src.models import Job, utc_now
from src.models.session_debug import (DebugItem, DebugResult, FlagsRead, FlagWritten, GameInfo, GameItem, SaveListing,
    SnapshotResult, SnapshotState, WarpResult, WarpSample)

MAX_GAME_INFO = 4 * 1024 * 1024
SAMPLE_FIELDS = sorted(FIELDS)
LOG_BOUND = 65536            # bytes of the game's log read after a line
LOG_LINES = 8                # lines of it reported
LOG_LINE_BOUND = 200         # characters per reported line
LINE_PAUSE = 0.04            # the game polls its live input file every 30 ms and keeps only the last `!cheat`
LOG_WAIT = 2.0               # seconds to wait for the game's own words
COUNT_WAIT = 1.5             # seconds to wait for an asynchronous pickup to show in a count flag
RETURN_TOLERANCE = 1.0       # position units; the bridge's own unit
WARP_WATCH = 2.0             # seconds Link's position is read back after a warp
WARP_TOLERANCE = 0.75        # metres from the target that still count as there
FLAG_SETTLE_PRESENTS = 20
SNAPSHOT_NOTE = ("A copy of this session's disposable user folder at one moment, not a checkpoint. The game saves on its "
    "own transitions: item, flag and position edits are not on disk until its next save. To restore, call "
    "session_launch(save_id=<this id>, ...) and continue from the title.")

_NUMBER = r"(-?[0-9]+(?:\.[0-9]+)?)"
_TRIPLE = rf"{_NUMBER}[ ,]+{_NUMBER}[ ,]+{_NUMBER}"
MARKED = re.compile(rf"cheats: marked position {_TRIPLE}")
RETURNED = re.compile(rf"cheats: returned to {_TRIPLE}")
HAD_NOW = re.compile(r"\(had (-?[0-9]{1,9}), now (-?[0-9]{1,9})")
SLOT_PART = re.compile(r"slot_[0-9]{2}")


def flag_value(raw):
    """A bounded flag value (integers, finite floats, short text) or null."""
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, int):
        return raw if abs(raw) < 2**64 else None
    if isinstance(raw, float):
        return raw if math.isfinite(raw) else None
    if isinstance(raw, str):
        return raw if len(raw) <= 64 and raw.isprintable() else None
    return None


def flag_agrees(kind: str, written, observed) -> bool | None:
    """Does a flag subscription's value match what was written? Null when it could not be read."""
    if observed is None:
        return None
    if kind == "float":
        return isinstance(observed, (int, float)) and abs(observed - written) <= 0.0006  # the game prints 3 decimals
    return observed == int(written)


def log_path(session) -> Path:
    """The one place that names the running game's log file."""
    name = session.plan.get("log")
    return session.root / (name if name in LOG_NAMES else "longshot_log.txt")


def log_offset(path: Path) -> int | None:
    """Size of the game's log before a line (0 when it does not exist yet); null when it must not be read."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return 0
    except OSError:
        return None
    return info.st_size if stat.S_ISREG(info.st_mode) else None


def cheat_lines(path: Path, offset: int | None) -> list[str]:
    """Complete log lines written after ``offset`` that contain ``cheats:``: bounded, control characters stripped."""
    if offset is None:
        return []
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError:
        return []
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return []
        data = os.pread(fd, LOG_BOUND, offset)
    except OSError:
        return []
    finally:
        os.close(fd)
    complete = data.split(b"\n")[:-1]  # the last piece is an unfinished line (or empty)
    lines = []
    for raw in complete:
        line = raw.decode("utf-8", "replace")
        if "cheats:" in line:
            clean = "".join(" " if c == "\t" else c for c in line if c == "\t" or c.isprintable()).strip()
            lines.append(clean[:LOG_LINE_BOUND])
        if len(lines) == LOG_LINES:
            break
    return lines


def triple(pattern: re.Pattern, lines: list[str]) -> list[float] | None:
    for line in lines:
        found = pattern.search(line)
        if found:
            values = [float(part) for part in found.groups()]
            return values if all(math.isfinite(v) and abs(v) < 1e9 for v in values) else None
    return None


def had_now(lines: list[str]) -> tuple[int | None, int | None]:
    found = None
    for line in lines:
        found = HAD_NOW.search(line) or found
    return (int(found[1]), int(found[2])) if found else (None, None)


def append_line(path: Path, code: int, *, text: str | None = None, operation: str = "session_debug") -> None:
    """Append one ``!cheat`` line (or ``text``), atomically for the game's reader; never through a symlink."""
    line = (text if text is not None else f"!cheat {code}\n").encode()
    try:
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
    except OSError:
        raise fail("backend_failed", operation) from None
    try:
        try:
            written = os.write(fd, line)
        except OSError:
            raise fail("uncertain_outcome", operation) from None
        if written != len(line):
            raise fail("uncertain_outcome", operation)
    finally:
        os.close(fd)


class SessionDebug:
    def __init__(self, service):
        self.service = service
        self.deps = service.deps

    # ---- operator-registered game info

    def game_info(self, session: Session, operation: str, *, required: bool = True) -> GameInfo | None:
        """The build's game info, validated and cached on the session; never echoed to callers."""
        if session.game_info is not None:
            return session.game_info
        path = session.game_info_path
        if path is None:
            if required:
                raise self.deps.error("unavailable", operation)
            return None
        try:
            resolved = self.deps.paths.read(path)
        except WorkbenchError as exc:
            if exc.envelope.code == "not_found":
                raise self.deps.error("unavailable", operation) from None
            raise
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise self.deps.error("refused_by_policy", operation)
        try:
            with resolved.open("rb") as stream:
                raw = stream.read(MAX_GAME_INFO + 1)
            if len(raw) > MAX_GAME_INFO:
                raise ValueError
            session.game_info = GameInfo.model_validate_json(raw)
        except (OSError, ValueError):
            raise self.deps.error("backend_failed", operation) from None
        return session.game_info

    # ---- flag reads (a dedicated connection and a one-shot subscription; no memory opt-in)

    async def read_flags(self, session: Session, names: list[str], operation: str, timeout: float = 5) -> dict:
        await self.service.connection(session)  # the runtime-socket pointer checks of every other bridge use; sets session.socket
        if not session.socket.exists():
            raise self.deps.error("unavailable", operation)
        bridge = await Bridge.connect(session.socket)
        try:
            return await bridge.sample_flags(names, timeout, operation=operation)
        finally:
            await bridge.close()

    async def flags_impl(self, run_id: str, names: list[str]) -> FlagsRead:
        session = self.service.owned(run_id)
        if not 1 <= len(names) <= 16 or any(not isinstance(n, str) or not FLAG_NAME.fullmatch(n) for n in names):
            raise self.deps.error("invalid_argument", "session_flags")
        info = self.game_info(session, "session_flags", required=False)
        aliases = info.names if info else {}
        resolved = {name: aliases.get(name, name) for name in names}
        event = await self.read_flags(session, sorted(set(resolved.values())), "session_flags")
        values = event["game"]["flags"]
        return FlagsRead(flags={name: flag_value(values.get(flag, values.get(flag.lower()))) for name, flag in resolved.items()},
            frame=number(event.get("frame"), integer=True), sample_frame=number(event["game"].get("frame"), integer=True),
            observed_at=utc_now())

    # ---- Debug-tab actions (appended `!cheat <n>` lines)

    def _plan(self, info: GameInfo, action) -> tuple[int, GameItem | None]:
        actions, item = info.actions, None
        if action.kind == "time":
            if action.hour >= actions.time_hours:
                raise self.deps.error("invalid_argument", "session_debug")
            code = actions.time_base + action.hour
        elif action.kind in {"item", "item_toggle"}:
            item = next((row for row in info.items if row.name == action.name), None)
            if item is None or item.kind != (1 if action.kind == "item" else 0):
                raise self.deps.error("invalid_argument", "session_debug")
            base = actions.item_base + item.index * actions.item_stride
            code = base + actions.item_bias + action.change if action.kind == "item" else base + actions.item_toggle
        else:
            code = actions.mark if action.kind == "mark" else actions.return_to_mark
        if not 0 <= code < 2**31:
            raise self.deps.error("invalid_argument", "session_debug")
        return code, item

    @staticmethod
    def _item_flags(info: GameInfo, action, item: GameItem | None) -> list[str]:
        """The flags an item's quantity or possession is read from, best first. A quantity: its count flag. A possession: its count
        flag when the game has one (the pouch's count is the truth), then the have flag. The have flag (the game's IsGet) is set when
        an item is got and never cleared when one is taken away, so on its own it can show a got item but not a taken one."""
        if item is None or info.item_flags is None:
            return []
        templates = [info.item_flags.count] if action.kind == "item" else [info.item_flags.count, info.item_flags.have]
        names = [template.replace("{name}", item.name) for template in templates if template]
        return [name for name in names if FLAG_NAME.fullmatch(name)]

    async def debug_impl(self, run_id: str, action, timeout_seconds: float, idempotency_key: str) -> Job:
        request = dict(run_id=run_id, action=action.model_dump(), timeout_seconds=timeout_seconds)
        previous = self.deps.registry.find_job("session_debug", idempotency_key, request)
        if previous is not None:
            return previous
        session = self.service.owned(run_id)
        if not (session.profile.debug and session.profile.debug_tools):
            raise self.deps.error("refused_by_policy", "session_debug")
        if session.live_path is None or session.live_path.is_symlink() or not session.live_path.is_file():
            raise self.deps.error("unavailable", "session_debug")
        info = self.game_info(session, "session_debug")
        code, item = self._plan(info, action)

        async def run(job_id):
            if session.debug_lock.locked():
                raise self.deps.error("busy", "session_debug")
            async with session.debug_lock:
                written = []
                try:
                    async with asyncio.timeout(timeout_seconds):
                        return await self._debug(session, info, action, code, item, written)
                except TimeoutError:
                    raise self.deps.error("uncertain_outcome" if written else "timeout", "session_debug") from None
        return await self.service._submit("session_debug", request, idempotency_key, run, run_id=run_id)

    async def _count(self, session: Session, flag: str) -> int | None:
        event = await self.read_flags(session, [flag], "session_debug")
        flags = event["game"]["flags"]
        value = flag_value(flags.get(flag, flags.get(flag.lower())))
        return value if isinstance(value, int) else None

    async def _debug(self, session: Session, info: GameInfo, action, code: int, item: GameItem | None, written: list):
        deps, bridge = self.deps, await self.service.connection(session)
        before = sample_from(await bridge.request("status", timeout=2), max_age_ms=500, selected=SAMPLE_FIELDS)
        if before.controllable is not True:
            # Never queue a line behind a load, a cutscene or a stale sample: the game would hold and fire it later.
            raise deps.error("unavailable", "session_debug", retryable=True)
        flag, count_before, have_only = None, None, False
        for position, candidate in enumerate(self._item_flags(info, action, item)):
            flag = flag or candidate
            value = await self._count(session, candidate)
            if value is not None:
                flag, count_before, have_only = candidate, value, action.kind == "item_toggle" and position > 0
                break
        log = log_path(session)
        offset = log_offset(log)
        deps.paths.read(session.live_path)
        append_line(session.live_path, code)
        written.append(code)
        try:
            await asyncio.sleep(LINE_PAUSE)
            await bridge.request("wait", timeout=5, event="present", frames=3)
            said, deadline = [], time.monotonic() + LOG_WAIT
            while not (said := cheat_lines(log, offset)) and time.monotonic() < deadline:
                await bridge.request("wait", timeout=1, event="present", frames=1)
            expected = None
            if count_before is not None and not (have_only and count_before):   # (a removal the have flag cannot show is not waited for)
                expected = count_before + action.change if action.kind == "item" else 0 if count_before else 1
            count_after, settle = None, time.monotonic() + COUNT_WAIT
            while flag:
                count_after = await self._count(session, flag)
                if expected is None or count_after == expected or time.monotonic() >= settle:
                    break
                await bridge.request("wait", timeout=1, event="present", frames=3)
            after = sample_from(await bridge.request("status", timeout=2), max_age_ms=500, selected=SAMPLE_FIELDS)
            said = cheat_lines(log, offset) or said
        except WorkbenchError as exc:
            if exc.envelope.code == "uncertain_outcome":
                raise
            raise deps.error("uncertain_outcome", "session_debug") from None
        marked = triple(MARKED, said)
        if action.kind == "mark" and marked is not None:
            session.marked = marked
        had, now = had_now(said)
        detail = None if item is None else DebugItem(name=item.name, index=item.index, count_before=count_before,
            count_after=count_after, had=had, now=now)
        return DebugResult(kind=action.kind, action_number=code, game_said=said,
            effect=self._effect(session, action, said, after, count_before, count_after, have_only),
            before=before.game, after=after.game, item=detail, observed_at=utc_now())

    @staticmethod
    def _effect(session: Session, action, said: list[str], after, count_before, count_after, have_only=False) -> str:
        """Only a read-back from the game earns ``verified``; the game's own log lines never do."""
        if action.kind == "time":
            # The clock is not on the bridge, so a request the game acknowledged is the best claim there is.
            return "not_applied" if any("world clock unavailable" in line for line in said) else "requested"
        if action.kind == "mark":
            return "requested"
        if action.kind == "return_to_mark":
            if any("no mark for this player controller" in line for line in said):
                return "not_applied"
            target = session.marked or triple(RETURNED, said)
            if target is None or after.fresh is not True or after.game.pos is None:
                return "requested"
            return "verified" if math.dist(target, after.game.pos) <= RETURN_TOLERANCE else "not_applied"
        if count_before is None or count_after is None:
            return "requested"
        if action.kind == "item":
            return "verified" if count_after == count_before + action.change else "not_applied"
        if bool(count_after) != bool(count_before):
            return "verified"
        # Read from the have flag alone, a removal cannot be seen: it stays set. The game's log line is all there is.
        return "requested" if have_only and count_before else "not_applied"

    # ---- a coordinate warp: the game's own return to mark, with the asked position as the mark (the live input's `!place X Y Z`)

    async def warp_impl(self, run_id: str, x: float, y: float, z: float, timeout_seconds: float, idempotency_key: str) -> Job:
        target = [float(x), float(y), float(z)]
        request = dict(run_id=run_id, target=target, timeout_seconds=timeout_seconds)
        previous = self.deps.registry.find_job("session_warp", idempotency_key, request)
        if previous is not None:
            return previous
        session = self.service.owned(run_id)
        if not (session.profile.debug and session.profile.debug_tools):
            raise self.deps.error("refused_by_policy", "session_warp")
        if session.live_path is None or session.live_path.is_symlink() or not session.live_path.is_file():
            raise self.deps.error("unavailable", "session_warp")
        if not all(math.isfinite(v) and abs(v) <= 100000 for v in target):
            raise self.deps.error("invalid_argument", "session_warp")

        async def run(job_id):
            if session.debug_lock.locked():
                raise self.deps.error("busy", "session_warp")
            async with session.debug_lock:
                written = []
                try:
                    async with asyncio.timeout(timeout_seconds):
                        return await self._warp(session, target, written)
                except TimeoutError:
                    raise self.deps.error("uncertain_outcome" if written else "timeout", "session_warp") from None
        return await self.service._submit("session_warp", request, idempotency_key, run, run_id=run_id)

    async def _warp(self, session: Session, target: list[float], written: list) -> WarpResult:
        deps, bridge = self.deps, await self.service.connection(session)
        before = sample_from(await bridge.request("status", timeout=2), max_age_ms=500, selected=SAMPLE_FIELDS)
        if before.controllable is not True:
            raise deps.error("unavailable", "session_warp", retryable=True)   # never queue a line behind a load or a cutscene
        log = log_path(session)
        offset = log_offset(log)
        deps.paths.read(session.live_path)
        append_line(session.live_path, 0, text="!place %.4f %.4f %.4f\n" % tuple(target), operation="session_warp")
        written.append(1)
        samples, said = [], []
        try:
            await asyncio.sleep(LINE_PAUSE)
            await bridge.request("wait", timeout=5, event="present", frames=3)
            deadline = time.monotonic() + LOG_WAIT
            while not (said := [line for line in cheat_lines(log, offset) if "returned to" in line]) and time.monotonic() < deadline:
                await bridge.request("wait", timeout=1, event="present", frames=1)
            started = time.monotonic()
            while said:
                sample = sample_from(await bridge.request("status", timeout=2), max_age_ms=500, selected=SAMPLE_FIELDS)
                pos = sample.game.pos
                samples.append(WarpSample(t=round(time.monotonic() - started, 2), pos=pos,
                                          dist=round(math.dist(pos, target), 2) if pos else None))
                if time.monotonic() - started >= WARP_WATCH or len(samples) >= 64:
                    break
                await bridge.request("wait", timeout=2, event="present", frames=6)
            after = sample_from(await bridge.request("status", timeout=2), max_age_ms=500, selected=SAMPLE_FIELDS)
            said = cheat_lines(log, offset) or said
        except WorkbenchError as exc:
            if exc.envelope.code == "uncertain_outcome":
                raise
            raise deps.error("uncertain_outcome", "session_warp") from None
        effect, note = "not_applied", ("the game gave no \"returned to\" line: this build has no `!place` command (the host lacks the live-input command), "
                                      "or Link was not being updated")
        near = [s for s in samples if s.dist is not None and s.dist <= WARP_TOLERANCE]
        if near:
            first = samples.index(near[0])
            for s in samples[:first]:
                s.stale = True    # (the state sample is the previous update's: the old place, not a failure)
            kept = samples[first:]
            last = samples[-1]
            if all(s.dist is not None and s.dist <= WARP_TOLERANCE for s in kept):
                effect, note = "verified", None
            else:
                effect, note = "partial", (f"Link was at the target for {len(near)} of {len(kept)} samples and then {last.dist} m away: "
                                           "the game put him back or moved him (a wall, the floor, a drop)")
        elif said:
            note = "the game said it returned him, but his position never read back within 0.75 m of the target"
        return WarpResult(target=target, game_said=said[:8], effect=effect, samples=samples[:64], before=before.game, after=after.game,
                          note=note, observed_at=utc_now())

    # ---- typed flag writes (memory opt-in)

    async def flag_set_impl(self, run_id: str, name: str, value, kind: str | None, timeout_seconds: float,
                            idempotency_key: str) -> Job:
        if not FLAG_NAME.fullmatch(name) or isinstance(value, str) or not isinstance(value, (bool, int, float)) \
                or (isinstance(value, float) and not math.isfinite(value)) or kind not in {None, *PROBE_ORDER}:
            raise self.deps.error("invalid_argument", "session_flag_set")
        request = dict(run_id=run_id, name=name, value=value, kind=kind, timeout_seconds=timeout_seconds)
        previous = self.deps.registry.find_job("session_flag_set", idempotency_key, request)
        if previous is not None:
            return previous
        session = self.service.owned(run_id)
        if not (session.profile.debug and session.profile.memory == "rw"):
            raise self.deps.error("refused_by_policy", "session_flag_set")
        info = self.game_info(session, "session_flag_set")
        if info.layout is None:
            raise self.deps.error("unavailable", "session_flag_set")
        if kind is not None:
            try:
                encode(kind, value)
            except ValueError:
                raise self.deps.error("invalid_argument", "session_flag_set") from None
        layout, target = info.layout, info.names.get(name, name)

        async def run(job_id):
            if session.debug_lock.locked():
                raise self.deps.error("busy", "session_flag_set")
            async with session.debug_lock:
                phase = ["lookup"]
                try:
                    async with asyncio.timeout(timeout_seconds):
                        return await self._flag_set(session, layout, name, target, value, kind, phase)
                except TimeoutError:
                    raise self.deps.error("timeout" if phase[0] == "lookup" else "uncertain_outcome", "session_flag_set") from None
                except WorkbenchError as exc:
                    if phase[0] == "after" and exc.envelope.code != "uncertain_outcome":
                        raise self.deps.error("uncertain_outcome", "session_flag_set") from None
                    raise
        return await self.service._submit("session_flag_set", request, idempotency_key, run, run_id=run_id)

    async def _flag_set(self, session: Session, layout, name: str, target: str, value, kind: str | None, phase: list):
        deps, bridge = self.deps, await self.service.connection(session)
        memory = FlagMemory(bridge, layout, "session_flag_set")
        hashed = flag_hash(target)
        found = await memory.locate(hashed, (kind,) if kind else PROBE_ORDER)
        if found is None:
            raise deps.error("not_found", "session_flag_set")
        found_kind, address = found
        try:
            payload = encode(found_kind, value)
        except ValueError:
            raise deps.error("invalid_argument", "session_flag_set") from None
        width = WIDTH[found_kind]
        before = decode(found_kind, await memory.read(address, width))
        written = decode(found_kind, payload)
        if any(isinstance(v, float) and not math.isfinite(v) for v in (before, written)):
            raise deps.error("backend_failed", "session_flag_set")
        phase[0] = "write"
        await memory.write(address, payload)
        phase[0] = "after"
        after_memory = decode(found_kind, await memory.read(address, width))
        if isinstance(after_memory, float) and not math.isfinite(after_memory):
            after_memory = None
        await bridge.request("wait", timeout=5, event="present", frames=FLAG_SETTLE_PRESENTS)
        event = await self.read_flags(session, [target], "session_flag_set")
        flags = event["game"]["flags"]
        after_flag = flag_value(flags.get(target, flags.get(target.lower())))
        # A flag the subscription cannot read (null) neither confirms nor contradicts the memory read-back.
        verified = after_memory is not None and after_memory == written and flag_agrees(found_kind, written, after_flag) is not False
        return FlagWritten(name=name, hash=f"0x{hashed:08x}", kind=found_kind, before=before, written=written,
            after_memory=after_memory, after_flag=after_flag, effect="verified" if verified else "not_applied",
            observed_at=utc_now())

    # ---- snapshot of the disposable user folder

    async def snapshot_impl(self, run_id: str, idempotency_key: str) -> Job:
        deps, service = self.deps, self.service
        session = service.owned(run_id)
        cat = catalogue(deps)
        user = session.root / "user"
        deps.paths.read(cat.clone_root)
        plain_files(deps, user, None, "session_snapshot")
        if cat.clone_root.resolve().is_relative_to(user.resolve()):
            raise deps.error("refused_by_policy", "session_snapshot")

        async def run(job_id):
            state = await self._state(session, run_id)
            files = plain_files(deps, user, None, "session_snapshot")
            newest = max((info.st_mtime for path, info in files
                          if any(SLOT_PART.fullmatch(part) for part in path.relative_to(user).parts)), default=None)
            clone_id, manifest, artifact = await service._copy_clone(job_id, cat, user, run_id, None, "session_snapshot",
                {"state.json": json.dumps(state.model_dump(), separators=(",", ":"))})
            return SnapshotResult(save_id=clone_id, file_count=len(manifest), copy_hash_manifest=artifact, state=state,
                slot_age_seconds=None if newest is None else max(0.0, time.time() - newest), note=SNAPSHOT_NOTE)
        return await service._submit("session_snapshot", dict(run_id=run_id), idempotency_key, run, run_id=run_id)

    async def _state(self, session: Session, run_id: str) -> SnapshotState:
        """What the game reports now; parts the bridge cannot give stay null."""
        sample = listing = None
        try:
            bridge = await self.service.connection(session)
            sample = sample_from(await bridge.request("status", timeout=2), max_age_ms=1000, selected=SAMPLE_FIELDS)
        except WorkbenchError:
            pass
        try:
            page = await self.service.saves_list_impl(run_id, 0, 100)
            listing = [SaveListing(slot=row.slot, mtime=row.mtime) for row in page.slots]
        except WorkbenchError:
            pass
        game = sample.game if sample else None
        return SnapshotState(map=game and game.map, age=game and game.age, pos=game and game.pos,
            life=game and game.life, max_life=game and game.max_life, rupees=game and game.rupees,
            frame=sample.sample_frame if sample else None, fresh=sample.fresh if sample else None,
            observed_at=sample.observed_at if sample else utc_now(), saves_listing=listing)
