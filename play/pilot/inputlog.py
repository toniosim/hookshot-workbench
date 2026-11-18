#!/usr/bin/env python3
"""The input log of a played session as a recording: what the hsap game side sent to the control bridge, frame-stamped, and converters.

hsap writes <live>/inputs.jsonl: one JSON line per input request as it left for the game (`cmd` press | stick | sequence, with its
arguments as the bridge takes them, or `cmd` live with a debug `!` line), `present` (the newest present the game had reported) and `mono`.
That is what a debug-menu "Record inputs" item would capture on the game's side (the idea of issue 1113): the same requests, the same
frame clock. This module keeps ONE recording format for both and moves between it and the places a replay needs:

    ls-input-recording/1   JSONL. Line 1: {"format", "fps": 60, "start": <present the recording is relative to>, ...the header the writer
                           gives: build, save, boot, seed, ...}. Then one line per input: {"f": frames since start, "cmd", ...arguments}.
                           Frames, not seconds: under load a second of wall time is not a second of play. A teleport or menu action of the
                           game's own debug menu would be a `cmd: "live"` line with its `!` text, or a `cmd: "menu"` line (not written yet).
    to_hsap_steps          the recording as hsap steps (`press`, `push`, `raw`, `wait`): the replay through the game side that exists today
                           (`hunt.py replay --mode inputs`); the waits between inputs are the recording's frame gaps at 60 a second.
    to_hos_script          the game's own file grammar (HOS_INPUT_SCRIPT / hs-run.sh --input: `<seconds>:<buttons>[/<ms>],...`, with
                           HOS_INPUT_FRAME_CLOCK=1 counting 60 presents a second) for the part of the recording that grammar can say: buttons and
                           the bridge's own hos sequences. An analog stick request has no word in it and is counted as `lossy`.
    from_hos_script        the other way: a script text as a recording (a hand-made one, or the game's recorder when it exists).

Standard library only; nothing here starts a game.
    inputlog.py record <inputs.jsonl> [--start N] [--header k=v ...]     print the recording
    inputlog.py script <recording.jsonl|inputs.jsonl>                    print the game-grammar script and the lossy count
"""
import argparse
import json
import re
import sys
from pathlib import Path

FORMAT = 'ls-input-recording/1'
FPS = 60.0
ANALOG = re.compile(r'\bL[XY]=')


def read_jsonl(path):
    out = []
    for ln in Path(path).read_text(errors='replace').splitlines():
        ln = ln.strip()
        if ln:
            try:
                out.append(json.loads(ln))
            except ValueError:
                pass
    return out


def to_recording(rows, start=None, **header):
    """The recording lines for hsap's raw input rows: a header and one event per input with `f` relative to `start` (default: the present of
    the first row). Rows are put in the order they were sent."""
    rows = sorted(rows, key=lambda r: (r.get('mono', 0), r.get('id', 0)))
    if start is None:
        start = rows[0].get('present', 0) if rows else 0
    out = [{'format': FORMAT, 'fps': int(FPS), 'start': start, **header}]
    for r in rows:
        e = {'f': max(0, int(r.get('present', 0)) - start)}
        e.update({k: v for k, v in r.items() if k not in ('present', 'mono', 'id')})
        out.append(e)
    return out


def write_recording(path, lines):
    Path(path).write_text(''.join(json.dumps(x, separators=(',', ':')) + '\n' for x in lines))


def read_recording(path):
    lines = read_jsonl(path)
    if not lines or lines[0].get('format') != FORMAT:
        raise ValueError(f'not an {FORMAT} file')
    return lines[0], lines[1:]


def event_frames(e):
    """How many frames an event holds the pad for (press and stick say it; a sequence ends when its last entry does)."""
    if e.get('cmd') in ('press', 'stick'):
        return int(e.get('frames') or 0)
    if e.get('cmd') == 'sequence':
        end = 0.0
        for item in str(e.get('script', '')).split(','):
            m = re.match(r'\s*([0-9.]+):[^/]*(?:/([0-9.]+))?', item)
            if m:
                end = max(end, float(m.group(1)) + (float(m.group(2)) / 1000.0 if m.group(2) else 0.2))
        return int(round(end * FPS))
    return 0


def to_hsap_steps(events, min_gap_s=0.1):
    """hsap step lines that send the same requests: press <buttons> <ms>, push <lx> <ly> <ms>, raw <script> 0, `!` lines as they are; a
    `wait <s>` for the gap between the end of one input and the start of the next when it is at least min_gap_s."""
    lines, prev_end = [], None
    for e in events:
        if prev_end is not None:
            gap = (e['f'] - prev_end) / FPS
            if gap >= min_gap_s:
                lines.append(f'wait {gap:.2f}')
        cmd = e.get('cmd')
        if cmd == 'press':
            lines.append(f'press {e["buttons"]} {max(1, round(int(e["frames"]) * 1000 / FPS))}')
        elif cmd == 'stick':
            lines.append(f'push {round(float(e["x"]) * 32767)} {round(float(e["y"]) * 32767)} {max(1, round(int(e["frames"]) * 1000 / FPS))}')
        elif cmd == 'sequence':
            lines.append(f'raw {e["script"]} 0')
        elif cmd == 'live':
            lines.append(e['line'])
        else:
            continue
        prev_end = e['f'] + event_frames(e)
    return lines


def shift_script(script, dt):
    """A hos sequence with every entry's time moved by dt seconds."""
    out = []
    for item in str(script).split(','):
        m = re.match(r'\s*([0-9.]+):(.*)$', item)
        out.append(f'{float(m.group(1)) + dt:g}:{m.group(2)}' if m else item.strip())
    return ','.join(out)


def to_hos_script(events):
    """(script text, lossy): the game's own grammar for what it can say. A press is `<s>:<buttons>/<ms>`; a hos sequence is its entries moved to
    its start; an analog stick request or a debug line is not in the grammar and is counted. Seconds are frames / 60 (HOS_INPUT_FRAME_CLOCK=1)."""
    parts, lossy = [], 0
    for e in events:
        t = e['f'] / FPS
        cmd = e.get('cmd')
        if cmd == 'press':
            parts.append(f'{t:g}:{e["buttons"]}/{round(int(e["frames"]) * 1000 / FPS)}')
        elif cmd == 'sequence' and not ANALOG.search(str(e.get('script', ''))) and e.get('units', 'hos') == 'hos':
            parts.append(shift_script(e['script'], t))
        else:
            lossy += 1
    return ','.join(parts), lossy


def from_hos_script(text, **header):
    """A game-grammar script as a recording: one `sequence` event per comma entry at its time (a hand-made recording, or the game's)."""
    lines = [{'format': FORMAT, 'fps': int(FPS), 'start': 0, **header}]
    for item in text.strip().split(','):
        m = re.match(r'\s*([0-9.]+):([^/]+)(?:/([0-9.]+))?\s*$', item)
        if not m:
            raise ValueError(f'not a script entry: {item!r}')
        t, buttons, ms = float(m.group(1)), m.group(2), float(m.group(3)) if m.group(3) else 200.0
        lines.append({'f': int(round(t * FPS)), 'cmd': 'press', 'buttons': buttons, 'frames': max(1, int(round(ms * FPS / 1000.0)))})
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    r = sub.add_parser('record')
    r.add_argument('inputs')
    r.add_argument('--start', type=int)
    r.add_argument('--header', nargs='*', default=[])
    s = sub.add_parser('script')
    s.add_argument('file')
    a = ap.parse_args()
    if a.cmd == 'record':
        hdr = dict(kv.split('=', 1) for kv in a.header)
        for ln in to_recording(read_jsonl(a.inputs), a.start, **hdr):
            print(json.dumps(ln, separators=(',', ':')))
        return 0
    lines = read_jsonl(a.file)
    ev = lines[1:] if lines and lines[0].get('format') == FORMAT else to_recording(lines)[1:]
    text, lossy = to_hos_script(ev)
    print(text)
    print(f'# lossy: {lossy} request(s) the grammar cannot say', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
