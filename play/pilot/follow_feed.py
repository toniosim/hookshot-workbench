#!/usr/bin/env python3
"""follow_feed: keeps one pilot's follow file (the OTHER player's place) from the other pilot's own state journal.

The decisions pilot (pilot.py run ... --follow <name>=<file>) reads a JSON file {"x", "z", "y"?, "map", "w"} before every decision
and hands it to hsap (--opponent) for the duel steps; a runner or session driver keeps that file. hsap writes every sample of its
game to <pilot run folder>/live/state.jsonl (pos, map, frame, t, ten a second), so the place of pilot B's Link, for pilot A, is the
last line of B's journal: this tool copies it, as often as asked, atomically (os.replace), with `w` = when the journal was last
written (the sample's receipt time, not the time of this copy), and stops writing while the journal is older than --max-age (the
file's age then grows in the pilot's opponent block, instead of a stale place looking fresh).

    follow_feed.py --src <B pilot run folder>/live/state.jsonl --dest <dir>/follow-opponent.json [--gate-file <file>] [--hz 5]

Nothing is written until --gate-file exists (the runner's premise: both games in the temporary copy, accepted, the kit verified);
until then the pilot waits for the file, so it makes no decision (and presses no Ready) before the gate. As a library: Feeder(src,
dest, gate=<callable or None>, hz, max_age).start() / .stop(). Standard library only.
"""
import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path


class Feeder(threading.Thread):
    def __init__(self, src, dest, gate=None, hz=5.0, max_age=1.5, clock=time.time):
        super().__init__(name='follow-feed-' + Path(dest).stem, daemon=True)
        self.src, self.dest, self.gate, self.period, self.max_age, self.clock = Path(src), Path(dest), gate, 1.0 / hz, max_age, clock
        self.stop_event = threading.Event()
        self.seq, self.written, self.skipped = 0, 0, {'gate': 0, 'no sample': 0, 'stale': 0}

    def stop(self):
        self.stop_event.set()

    def last_sample(self):
        """(sample, file mtime) of the journal's last whole line, or None."""
        try:
            with open(self.src, 'rb') as f:
                size = os.fstat(f.fileno()).st_size
                f.seek(max(0, size - 8192))
                lines = f.read().split(b'\n')
                mtime = os.fstat(f.fileno()).st_mtime
        except OSError:
            return None
        for line in reversed(lines[1:] if size > 8192 else lines):   # (the first line of a tail read may be cut)
            try:
                s = json.loads(line)
            except ValueError:
                continue
            if isinstance(s, dict) and isinstance(s.get('pos'), list) and len(s['pos']) == 3:
                return s, mtime
        return None

    def once(self):
        """One copy: True when the file was written, else False (and why is counted in `skipped`)."""
        if self.gate is not None and not (self.gate() if callable(self.gate) else Path(self.gate).exists()):
            self.skipped['gate'] += 1
            return False
        got = self.last_sample()
        if got is None:
            self.skipped['no sample'] += 1
            return False
        sample, mtime = got
        if self.clock() - mtime > self.max_age:
            self.skipped['stale'] += 1
            return False
        x, y, z = sample['pos']
        self.seq += 1
        tmp = self.dest.with_suffix('.tmp')
        tmp.write_text(json.dumps({'x': x, 'y': y, 'z': z, 'map': sample.get('map'), 'w': mtime, 'of': str(self.src), 'seq': self.seq}))
        os.replace(tmp, self.dest)
        self.written += 1
        return True

    def run(self):
        while not self.stop_event.is_set():
            self.once()
            self.stop_event.wait(self.period)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--src', required=True, help="the other pilot's <run folder>/live/state.jsonl")
    ap.add_argument('--dest', required=True, help="the follow file this pilot reads (--follow <name>=<this file>)")
    ap.add_argument('--gate-file', help='write nothing until this file exists')
    ap.add_argument('--hz', type=float, default=5.0)
    ap.add_argument('--max-age', type=float, default=1.5)
    a = ap.parse_args()
    f = Feeder(a.src, a.dest, gate=a.gate_file, hz=a.hz, max_age=a.max_age)
    try:
        f.run()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
