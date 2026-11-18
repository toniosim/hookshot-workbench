#!/usr/bin/env python3
"""A ghost leader for a follow benchmark: a thread that keeps a pilot's follow file with a place that moves along a route, the
way a runner keeps another player's place (pilot.py --follow NAME=<file>: JSON {x, z, y, map, w}, replaced whole by rename).

It stands at the route's first point until the pilot's game is in play (the pilot's run folder gets a `gameplay` event in
live/out.jsonl) and then runs along the points at `speed` metres a second, standing a second at each, round and round.
Only a place is written: no body, no game, no network. The other player is as exact as a recording and as predictable
as a loop, which is what a benchmark needs.
"""
import json
import math
import os
import threading
import time
from pathlib import Path

PAUSE_S = 1.0


def position_at(points, t, speed, pause=PAUSE_S, loop=True):
    """(x, z, index of the leg being run or the point stood at) after t seconds of moving from points[0]. Legs are straight lines
    at `speed`; the pilot stands `pause` seconds at each point reached; the route repeats when `loop` (last back to first)."""
    if len(points) < 2 or speed <= 0:
        return float(points[0][0]), float(points[0][1]), 0
    legs = [(points[i], points[(i + 1) % len(points)]) for i in range(len(points) if loop else len(points) - 1)]
    cycle = sum(math.hypot(b[0] - a[0], b[1] - a[1]) / speed + pause for a, b in legs)
    if loop:
        t %= cycle
    for i, (a, b) in enumerate(legs):
        run = math.hypot(b[0] - a[0], b[1] - a[1]) / speed
        if t < run:
            f = t / run if run else 1.0
            return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, i
        t -= run
        if t < pause:
            return float(b[0]), float(b[1]), (i + 1) % len(points)
        t -= pause
    last = points[-1]
    return float(last[0]), float(last[1]), len(points) - 1


def write_follow(path, x, z, area, y=None, now=None):
    """The follow file as the runner writes it: whole, by rename."""
    path = Path(path)
    body = {'x': round(x, 2), 'z': round(z, 2), 'map': area, 'w': time.time() if now is None else now}
    if y is not None:
        body['y'] = y
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(body))
    os.replace(tmp, path)


class Ghost(threading.Thread):
    """Keeps `path` at `hz` times a second. `start_when()` (default: at once) says when the leader starts to move; before that
    it stands at the first point. `stop()` ends the thread. `moved_s` is how long it has moved."""

    def __init__(self, path, route, start_when=None, hz=5.0, clock=time.monotonic):
        super().__init__(daemon=True)
        self.path, self.route, self.hz, self.clock = Path(path), route, hz, clock
        self.start_when = start_when or (lambda: True)
        self._stop_flag = threading.Event()
        self.t_start = None
        self.last = None   # (x, z) as last written

    def moved_s(self):
        return 0.0 if self.t_start is None else self.clock() - self.t_start

    def place(self):
        pts = self.route['points']
        if self.t_start is None:
            return float(pts[0][0]), float(pts[0][1]), 0
        return position_at(pts, self.moved_s(), self.route.get('speed', 4.5))

    def tick(self):
        if self.t_start is None and self.start_when():
            self.t_start = self.clock()
        x, z, i = self.place()
        ys = self.route.get('y') or []
        write_follow(self.path, x, z, self.route.get('area'), ys[i] if i < len(ys) else None)
        self.last = (x, z)

    def run(self):
        while not self._stop_flag.is_set():
            try:
                self.tick()
            except OSError:
                pass
            self._stop_flag.wait(1.0 / self.hz)

    def stop(self):
        self._stop_flag.set()
        self.join(timeout=5)


def gameplay_started(run_dir):
    """True once the pilot's live/out.jsonl has the `gameplay` event (the game is in play): the ghost starts then."""
    try:
        return '"gameplay"' in (Path(run_dir) / 'live' / 'out.jsonl').read_text()
    except OSError:
        return False
