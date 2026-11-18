"""A pilot run as an ls-input-recording/1 file, and the file's chunks for playback.

inputlog.py (taken from the bug hunter's branch) owns the format: line 1 a header, then one line per input `{"f": frames since the
start, "cmd": press | stick | sequence | live, ...}`; frames, not seconds. hsap writes `<live>/inputs.jsonl` (every input request as
it left for the game, with the present it left at). This module adds the one thing a replay needs to notice that it has left the
road: MARKS, lines `{"f", "cmd": "mark", "area": <map>, "pos": [x, y, z]}` for where Link was (the state line after each step of
the original run; the first one is the start). inputlog's converters skip `mark` lines, so a recording with marks is still an
ordinary recording.

    write_run(live_dir, out, **header)   the recording of a finished run: inputs after control began + marks
    chunks(events, marks)                the playback's units: the inputs between two marks, each with the mark it should end at

A mark's frame is the state sample's present and an input's frame is the newest present hsap had heard of when it sent the input
(samples come every six presents): an input sent in the same present as a mark counts as after it. The last input or two of a step
can therefore start the next chunk; a replay then checks its mark a few frames before the original did, which the position
tolerance (metres) absorbs.
"""
import math
from pathlib import Path

import inputlog

FORMAT = inputlog.FORMAT
FPS = inputlog.FPS
INPUT_CMDS = ('press', 'stick', 'sequence')
TOLERANCE_M = 3.0


def read_events(path):
    return inputlog.read_jsonl(path)


def marks_of(events, start):
    """A mark per `state` line the game side wrote after a step (why `wait`), frames counted from `start`."""
    out = []
    for e in events:
        if e.get('ev') == 'state' and e.get('why') == 'wait' and e.get('frame') is not None and e.get('pos') and e.get('area'):
            out.append({'f': max(0, int(e['frame']) - start), 'cmd': 'mark', 'area': e['area'],
                        'pos': [round(float(v), 2) for v in e['pos']], 'n': len(out)})
    return out


def build(rows, events, **header):
    """The recording's lines from hsap's input rows and the run's out.jsonl events (control began at the `gameplay` event: inputs
    before it are the boot's and are not part of the recording)."""
    gameplay = next((e for e in events if e.get('ev') == 'gameplay' and e.get('frame') is not None), None)
    first_state = next((e for e in events if e.get('ev') == 'state' and e.get('frame') is not None), None)
    start = int((gameplay or first_state or {}).get('frame') or 0)
    kept = [r for r in rows if int(r.get('present', 0)) >= start]
    head, *evs = inputlog.to_recording(kept, start=start, **header)
    marks = marks_of(events, start)
    head['marks'] = len(marks)
    head['tolerance_m'] = TOLERANCE_M
    merged = sorted(marks + evs, key=lambda x: (x['f'], 0 if x.get('cmd') == 'mark' else 1))   # (stable: a tie puts the mark first)
    return [head] + merged


def write_run(live_dir, out, **header):
    """Write the recording of the run whose live folder is `live_dir` (hsap's inputs.jsonl, the pilot's out.jsonl). Returns
    (path, number of input lines, number of marks), or None when the run left no input journal."""
    live = Path(live_dir)
    inputs = live / 'inputs.jsonl'
    if not inputs.is_file():
        return None
    lines = build(read_events(inputs), read_events(live / 'out.jsonl') if (live / 'out.jsonl').is_file() else [], **header)
    inputlog.write_recording(out, lines)
    marks = sum(1 for x in lines[1:] if x.get('cmd') == 'mark')
    return Path(out), len(lines) - 1 - marks, marks


def load(path):
    """(header, input events, marks) of a recording file; raises ValueError when it is not ls-input-recording/1."""
    header, lines = inputlog.read_recording(path)
    events = [x for x in lines if x.get('cmd') in INPUT_CMDS or x.get('cmd') == 'live']
    marks = [x for x in lines if x.get('cmd') == 'mark']
    return header, events, marks


def trim_overlaps(events):
    """The inputs as the game saw them: hsap sends a stick every six presents and holds each for eight, so a request is replaced by the next
    one two frames before it would end (the newest input is the one in force). A replay that sends each request for its whole length and waits
    for it (hsap's `push` and `press` do) would walk a third farther, so a press or stick that the next input overtakes is cut to the time
    until it. A sequence is left alone (its own script times it). Returns new dicts; the recording's are not changed."""
    out = [dict(e) for e in events]
    for i, e in enumerate(out[:-1]):
        if e.get('cmd') in ('press', 'stick'):
            gap = out[i + 1]['f'] - e['f']
            if 0 < gap < int(e.get('frames') or 0):
                e['frames'] = gap
    return out


def chunks(events, marks, gap_s=2.0):
    """[{events, mark}]: the inputs before each mark (a tie goes after it), each with the mark that ends it (the state the replay
    should be in once they were sent); inputs after the last mark are a last chunk with no mark. Without marks the chunks end at a
    pause of gap_s or more between inputs and there is nothing to check. Chunks with no input are dropped; their marks are not
    lost (they ride on the next chunk as `before`)."""
    out, ei, carried = [], 0, []
    if marks:
        for m in marks:
            evs = []
            while ei < len(events) and events[ei]['f'] < m['f']:
                evs.append(events[ei])
                ei += 1
            if evs:
                out.append({'events': evs, 'mark': m, 'before': carried})
                carried = []
            else:
                carried.append(m)
        if ei < len(events):
            out.append({'events': events[ei:], 'mark': None, 'before': carried})
            carried = []
    else:
        cur, last_end = [], None
        for e in events:
            if cur and last_end is not None and (e['f'] - last_end) / FPS >= gap_s:
                out.append({'events': cur, 'mark': None, 'before': []})
                cur = []
            cur.append(e)
            last_end = e['f'] + inputlog.event_frames(e)
        if cur:
            out.append({'events': cur, 'mark': None, 'before': []})
    return out, carried


def off_metres(pos, mark):
    return math.hypot(pos[0] - mark['pos'][0], pos[2] - mark['pos'][2])
