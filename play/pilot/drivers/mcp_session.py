"""The session folder of the mcp driver and its server: the whole protocol between them (see mcp_queue.py), standard library only.
The server (../mcp_server.py) imports this module alone, so that it starts without the pilot's other modules."""
import json
import os
from pathlib import Path

# What an agent's own steps may say: movement and the buttons. Not `cheat`, `save`, `shot`, `end`, `watch`, `report`, `duel` or a debug `!` line.
SAFE_VERBS = ('walk', 'run', 'press', 'stick', 'push', 'wait', 'until', 'faceat', 'face', 'camera', 'ztarget', 'interact', 'advance',
              'pickup', 'enter', 'item', 'ocarina', 'swing', 'shield', 'roll', 'sidestep', 'approach', 'climb', 'raw')
MAX_LINES, MAX_LINE = 20, 200
FILES = ('session.json', 'observe.json', 'act.json', 'rejected.json', 'status.json', 'ended.json')


class Refused(Exception):
    pass


def check_steps(steps):
    """Validated hsap step lines of an agent's `steps`, or Refused with the reason."""
    if not isinstance(steps, list) or not steps or not all(isinstance(s, str) for s in steps):
        raise Refused('`steps` must be a list of step lines (strings)')
    if len(steps) > MAX_LINES:
        raise Refused(f'at most {MAX_LINES} step lines in one act')
    out = []
    for s in steps:
        line = s.strip()
        verb = line.split(None, 1)[0] if line else ''
        if not line or len(line) > MAX_LINE or '\n' in line or '\r' in line:
            raise Refused(f'a step line must be one line of at most {MAX_LINE} characters: {line[:40]!r}')
        if verb not in SAFE_VERBS:
            raise Refused(f'step verb {verb!r} is not allowed (allowed: {", ".join(SAFE_VERBS)})')
        out.append(line)
    return out


class Session:
    """The session folder. Every write is atomic (write a temp file, rename it over)."""

    def __init__(self, path):
        self.dir = Path(path)

    def make(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        return self

    def write(self, name, obj):
        tmp = self.dir / f'.{name}.tmp'
        tmp.write_text(json.dumps(obj, indent=1, default=str))
        os.replace(tmp, self.dir / name)

    def read(self, name):
        try:
            return json.loads((self.dir / name).read_text())
        except (OSError, ValueError):
            return None

    def remove(self, name):
        try:
            (self.dir / name).unlink()
        except OSError:
            pass


def pid_alive(pid):
    try:
        os.kill(int(pid), 0)
    except (OSError, TypeError, ValueError):
        return False
    return True
