#!/usr/bin/env python3
"""bosspoints: a stand-in for hsap.py in a dry run of a hold (no game): it answers the same command line and writes the files the hold's
analysis reads.

    python3 -I -B dry_fake_hsap.py COPY TAG WALL --live LIVEDIR [other hsap options, ignored]

Reads LIVEDIR/steps.txt, writes COPY/runs/TAG/summary.txt and one picture file under COPY/runs/TAG/shots/, and LIVEDIR/out.jsonl with a
`gameplay` event, two `state` events (every flag hash of the steps' `watch` lines is 0 in the first and 1 in the last), one `step` event per
step line (result "done") and a `done` event.
"""
import json
import re
import signal
import sys
import time
from pathlib import Path


def main(argv):
    copy, tag = argv[0], argv[1]
    live = Path(argv[argv.index('--live') + 1])
    signal.signal(signal.SIGTERM, lambda *a: sys.exit(1))
    steps = (live / 'steps.txt').read_text().splitlines()
    watched = [h for s in steps if s.startswith('watch ') for h in re.findall(r'0x[0-9a-f]{8}', s)]
    run = Path(copy) / 'runs' / tag
    (run / 'shots').mkdir(parents=True, exist_ok=True)
    (run / 'summary.txt').write_text('fake run %s\n' % tag)
    (run / 'shots' / 'shot_000060.png').write_bytes(b'x')
    with open(live / 'out.jsonl', 'w') as out:
        def emit(**d):
            out.write(json.dumps(d) + '\n')
            out.flush()
        emit(ev='gameplay', t=0.0, frame=10, area='AreaA')
        emit(ev='state', t=1.0, area='AreaA', music='music-a', event=0, flags={h: 0 for h in watched}, changed=[])
        for i, s in enumerate(steps, 1):
            if s.startswith('#') or not s.strip():
                continue
            time.sleep(0.05)
            emit(ev='step', **{'in': i}, src=s, result='done', secs=0.1, moved=0, detail='', t=2.0 + i)
        emit(ev='state', t=30.0, area='AreaA', music='music-b', event=1, flags={h: 1 for h in watched}, changed=[])
        emit(ev='done')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
