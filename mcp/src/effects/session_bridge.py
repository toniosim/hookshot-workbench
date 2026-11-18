"""Bounded asyncio transport for the trusted control protocol, never a raw MCP tool.

Exactly one task reads each connection. Replies are matched by id (including
out-of-order replies); intervening events are retained in a bounded queue. A
lost mutation reply is uncertain, not grounds to retry or invent a quit reply.
"""
import asyncio
import json
import math
import re
import time
from collections import deque
from pathlib import Path
from src.errors import fail

# mem_read/mem_read_many/mem_write exist only when the game was started with the memory opt-in; the game answers
# `forbidden` otherwise. Reads change nothing; mem_write is a mutation and is never replayed.
COMMANDS = frozenset({"status", "press", "stick", "sequence", "release", "shot", "wait", "option_get",
                      "option_set", "teleport", "age", "saves", "quit", "subscribe", "unsubscribe",
                      "mem_read", "mem_read_many", "mem_write"})
READS = frozenset({"status", "wait", "option_get", "saves", "subscribe", "unsubscribe", "mem_read", "mem_read_many"})
MAX_REPLY = 524288
FLAG_NAME = re.compile(r"^(?:0x[0-9a-fA-F]{8}|[A-Za-z0-9_.]{1,47})$")


class Bridge:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader, self.writer = reader, writer
        self.pending: dict[int, asyncio.Future] = {}
        self.events = deque(maxlen=256)
        self.events_lost = 0
        self.changed = asyncio.Event()
        self.next_id = 0
        self.closed = False
        self._write_lock = asyncio.Lock()
        self._reader_task = asyncio.create_task(self._read())

    @classmethod
    async def connect(cls, path: Path, timeout: float = 2):
        try:
            reader, writer = await asyncio.wait_for(asyncio.open_unix_connection(str(path), limit=MAX_REPLY), timeout)
            return cls(reader, writer)
        except (OSError, TimeoutError):
            raise fail("unavailable", "session_bridge") from None

    async def _read(self):
        try:
            while line := await self.reader.readline():
                if len(line) > MAX_REPLY:
                    break
                message = json.loads(line, parse_constant=lambda _: None)
                if not isinstance(message, dict):
                    break
                if "event" in message and "ok" not in message:
                    if len(self.events) == self.events.maxlen:
                        self.events_lost += 1
                    self.events.append(message)
                    self.changed.set()
                elif isinstance(message.get("id"), int) and message["id"] in self.pending:
                    future = self.pending.pop(message["id"])
                    if not future.done():
                        future.set_result(message)
        except (OSError, ValueError, asyncio.LimitOverrunError):
            pass
        finally:
            self.closed = True
            self.changed.set()
            for future in self.pending.values():
                if not future.done():
                    future.set_result(None)
            self.pending.clear()
            self.writer.close()

    async def request(self, command: str, *, timeout: float = 5, mutation: bool | None = None, trace=None, **args) -> dict:
        if command not in COMMANDS or not math.isfinite(timeout) or not 0 < timeout <= 120:
            raise fail("invalid_argument", "session_bridge")
        operation = "session_" + command
        mutating = command not in READS if mutation is None else mutation
        if self.closed:
            raise fail("unavailable", operation)
        if len(self.pending) >= 32:
            raise fail("busy", operation)
        self.next_id += 1
        rid = self.next_id
        payload = json.dumps({"id": rid, "cmd": command, "timeout": timeout, **args}, allow_nan=False,
                             separators=(",", ":")).encode() + b"\n"
        if len(payload) > 65536:
            raise fail("invalid_argument", operation)
        future = asyncio.get_running_loop().create_future()
        self.pending[rid] = future
        sent = False
        def observe(direction, message):
            if trace is not None:
                try:
                    trace(direction, message)
                except Exception:
                    pass  # Journal failure must not turn a known reply into a replay.
        try:
            # The game's timeout reply is emitted at its deadline. Allow bounded
            # delivery time instead of expiring the socket at the same instant.
            async with asyncio.timeout(timeout + (1 if command in {"sequence", "press", "stick"} else 0)):
                async with self._write_lock:
                    sent = True
                    observe("request", json.loads(payload))
                    self.writer.write(payload)
                    await self.writer.drain()
                reply = await future
            if reply is not None:
                observe("reply", reply)
            if reply is None:
                raise fail("uncertain_outcome" if mutating else "unavailable", operation)
            if reply.get("ok") is not True:
                code = reply.get("error")
                if code == "timeout" and command in {"sequence", "press", "stick"} and reply.get("message") == "the game did not read the controller":
                    raise fail("unavailable", "session_input_not_consumed", retryable=True)
                mapped = {"unknown_cmd": "unavailable", "unavailable": "unavailable", "busy": "busy",
                          "refused": "refused_by_policy", "forbidden": "refused_by_policy", "not_found": "not_found",
                          "bad_request": "invalid_argument", "out_of_range": "backend_failed",
                          "timeout": "uncertain_outcome" if mutating else "timeout"}
                raise fail(mapped.get(code, "uncertain_outcome" if mutating else "backend_failed"), operation)
            return reply
        except (TimeoutError, OSError):
            observe("transport_timeout", {"cmd": command, "id": rid})
            raise fail("uncertain_outcome" if mutating and sent else "timeout", operation) from None
        finally:
            self.pending.pop(rid, None)
            if not future.done():
                future.cancel()

    def drain_events(self) -> list[dict]:
        events = list(self.events)
        self.events.clear()
        self.changed.clear()
        return events

    async def sample_flags(self, names: list[str], timeout: float = 5, *, max_age_ms: float = 1000,
                           operation: str = "session_flags") -> dict:
        """One-shot flag read: subscribe on this DEDICATED connection and take the first fresh ``oot`` event.

        A subscription can retain an old snapshot, so an event counts only when its game sample is recent
        (``game.t`` on this host's monotonic clock). Needs no memory opt-in. The caller owns and closes the
        connection: nothing else may share it, because every event on it is taken to be this subscription's.
        """
        if not 1 <= len(names) <= 64 or any(not isinstance(n, str) or not FLAG_NAME.fullmatch(n) for n in names) \
                or not math.isfinite(timeout) or not 0 < timeout <= 120:
            raise fail("invalid_argument", operation)
        deadline = time.monotonic() + timeout
        first = self.next_id + 1
        ack = await self.request("subscribe", timeout=min(timeout, 5), events=["oot"], every=1, flags=names, changes=False)
        sub = ack.get("sub") if isinstance(ack.get("sub"), int) and not isinstance(ack.get("sub"), bool) else first
        found = None
        while found is None:
            for event in self.drain_events():
                game = event.get("game") if event.get("event") == "oot" else None
                if not isinstance(game, dict) or not isinstance(game.get("flags"), dict):
                    continue
                frame, sampled = game.get("frame"), game.get("t")
                if isinstance(frame, int) and not isinstance(frame, bool) and isinstance(sampled, (int, float)) \
                        and not isinstance(sampled, bool) and 0 <= (time.monotonic() - sampled) * 1000 <= max_age_ms:
                    found = event
                    break
            if found is not None:
                break
            remaining = deadline - time.monotonic()
            if self.closed:
                raise fail("unavailable", operation)
            if remaining <= 0:
                raise fail("timeout", operation)
            try:
                await asyncio.wait_for(self.changed.wait(), remaining)
            except TimeoutError:
                pass
        try:
            await self.request("unsubscribe", timeout=1, sub=sub)
        except Exception:
            pass  # Best effort: closing the dedicated connection ends the subscription anyway.
        return found

    async def close(self):
        self.writer.close()
        try:
            await self.writer.wait_closed()
        except OSError:
            pass
        if not self._reader_task.done():
            self._reader_task.cancel()
        await asyncio.gather(self._reader_task, return_exceptions=True)
