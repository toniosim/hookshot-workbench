#!/usr/bin/env python3
"""inputlog.py: the recording format, its conversions (hsap steps, the game's own script grammar), hsap's input journal (the real Game
class with an external game that is not there: every input request leaves a line), and a packet that carries the recording.
Made-up inputs only; no game, no network.   python3 -I -B test_inputlog.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import bughunt  # noqa: E402
import bugpacket  # noqa: E402
import inputlog  # noqa: E402
import test_bughunt as tb  # noqa: E402
import test_bugpacket as tp  # noqa: E402

FAILS = []
CHECKS = [0]


def check(cond, what):
    CHECKS[0] += 1
    if not cond:
        FAILS.append(what)
        print('FAIL', what, flush=True)


RAW = [
    {'id': 5, 'cmd': 'press', 'buttons': 'A', 'frames': 12, 'present': 1000, 'mono': 10.0},
    {'id': 6, 'cmd': 'stick', 'stick': 'L', 'x': 0.5, 'y': -1.0, 'frames': 30, 'present': 1090, 'mono': 11.5},
    {'id': 7, 'cmd': 'sequence', 'script': '0:LX=-3000+LY=2000/800,0.9:X/100', 'units': 'hos', 'present': 1150, 'mono': 12.5},
    {'id': 8, 'cmd': 'sequence', 'script': '0:LUP/1200,0.6:X/100', 'units': 'hos', 'present': 1400, 'mono': 16.0},
    {'cmd': 'live', 'line': '!cheat 996', 'present': 1500, 'mono': 17.5},
]


def format_checks(tmp):
    rec = inputlog.to_recording(RAW, build='abc', save='a-save')
    check(rec[0] == {'format': 'ls-input-recording/1', 'fps': 60, 'start': 1000, 'build': 'abc', 'save': 'a-save'}, f'recording: the header names the format, the frame clock and what the writer gave ({rec[0]})')
    check([e['f'] for e in rec[1:]] == [0, 90, 150, 400, 500] and all('present' not in e and 'mono' not in e and 'id' not in e for e in rec[1:]),
          'recording: events are in frames since the start, with no wall times or request ids')
    check(inputlog.to_recording(RAW, start=900)[1]['f'] == 100, 'recording: another start moves every frame')
    check(inputlog.to_recording(list(reversed(RAW)))[1:] == rec[1:], 'recording: the order is the order they were sent')
    check(inputlog.to_recording([])[0]['start'] == 0 and len(inputlog.to_recording([])) == 1, 'recording: no inputs is a header only')
    path = tmp / 'r.jsonl'
    inputlog.write_recording(path, rec)
    hdr, ev = inputlog.read_recording(path)
    check(hdr == rec[0] and ev == rec[1:], 'recording: written and read back')
    (tmp / 'bad.jsonl').write_text('{"x": 1}\n')
    try:
        inputlog.read_recording(tmp / 'bad.jsonl')
        check(False, 'recording: another file is refused')
    except ValueError:
        check(True, 'recording: another file is refused')

    steps = inputlog.to_hsap_steps(rec[1:])
    check(steps == ['press A 200', 'wait 1.30', 'push 16384 -32767 500', 'wait 0.50', 'raw 0:LX=-3000+LY=2000/800,0.9:X/100 0', 'wait 3.17',
                    'raw 0:LUP/1200,0.6:X/100 0', 'wait 0.47', '!cheat 996'], f'hsap steps: the same requests with the frame gaps as waits ({steps})')
    check(inputlog.to_hsap_steps(rec[1:2]) == ['press A 200'] and inputlog.to_hsap_steps([]) == [], 'hsap steps: one input, none')
    # every produced line is one hsap's own step parser knows
    import hsap
    for ln in steps:
        verb = ln.split()[0]
        check(verb in ('press', 'push', 'raw', 'wait') or ln.startswith('!'), f'hsap steps: {ln!r} is a verb hsap has')
    check(all(v in hsap.__doc__ for v in ('press <buttons> [ms]', 'push <lx> <ly> <ms>', 'raw <presses> <s>', 'wait <s>')), 'hsap steps: press, push, raw and wait are in hsap\'s step list')

    text, lossy = inputlog.to_hos_script(rec[1:])
    parts = text.split(',')
    check(parts[0] == '0:A/200' and lossy == 3, f'game grammar: a press is a word of it, the analog stick, the analog sequence and the debug line are lossy ({text!r}, {lossy})')
    check(any(p.startswith('6.66667:LUP/1200') for p in parts) and any(p.startswith('7.26667:X/100') for p in parts), f'game grammar: a digital sequence is moved to its start at 400 frames ({parts})')
    back = inputlog.from_hos_script('0:A/200,1.5:B/100,2:LUP/1200', source='hand')
    check(back[0]['source'] == 'hand' and [(e['f'], e['buttons'], e['frames']) for e in back[1:]] == [(0, 'A', 12), (90, 'B', 6), (120, 'LUP', 72)], 'from_hos_script: a script text as a recording')
    try:
        inputlog.from_hos_script('nonsense')
        check(False, 'from_hos_script: nonsense is refused')
    except ValueError:
        check(True, 'from_hos_script: nonsense is refused')
    check(inputlog.shift_script('0:LUP/1200,0.6:X/100', 2.0) == '2:LUP/1200,2.6:X/100', 'shift_script: every entry moves')


def hsap_hook_checks(tmp):
    import hsap
    live = tmp / 'live'
    g = hsap.Game(tmp / 'copy', 'ext', 30, live, external=hsap.ExternalGame(tmp / 'no.sock', tmp / 'live.txt', tmp / 'log.txt', os.getpid()))
    try:
        g.presents = 4321
        g.press('A+B', 100)
        g.presents = 4400
        g.stick(16384, -32767, 500)
        g.send('0:LUP/1200,0.6:X/100')
        g.send('!cheat 996')
        g.request('status')
        rows = inputlog.read_jsonl(live / 'inputs.jsonl')
        check([r['cmd'] for r in rows] == ['press', 'stick', 'sequence', 'live'], f'hsap hook: every input request is journalled, a status is not ({[r["cmd"] for r in rows]})')
        check(rows[0]['buttons'] == 'A+B' and rows[0]['frames'] == 6 and rows[0]['present'] == 4321 and 'exclusive' not in rows[0] and 'wait' not in rows[0], 'hsap hook: the press, its frames and the present it left at')
        check(rows[1]['stick'] == 'L' and abs(rows[1]['x'] - 0.5) < 1e-3 and rows[1]['y'] == -1.0 and rows[1]['present'] == 4400, 'hsap hook: the stick as the bridge takes it')
        check(rows[2]['script'] == '0:LUP/1200,0.6:X/100' and rows[2]['units'] == 'hos' and rows[3]['line'] == '!cheat 996', 'hsap hook: a sequence and a debug line')
        g.down = True
        g.press('A', 100)
        check(len(inputlog.read_jsonl(live / 'inputs.jsonl')) == 4, 'hsap hook: an input meant for a dead pad is not sent, so not journalled')
        # the journal is a recording's source
        rec = inputlog.to_recording(rows)
        check([e['f'] for e in rec[1:]] == [0, 79, 79, 79] and rec[0]['start'] == 4321, f'hsap hook: the journal makes a recording ({[e["f"] for e in rec[1:]]})')
    finally:
        g.inputs_out.close()
        g.state_out.close()


def packet_checks(tmp):
    side, session = tp.make_session(tmp, 'ip')
    rows = RAW
    (tmp / 'ip' / 'pilot' / 'live').mkdir(parents=True, exist_ok=True)
    (tmp / 'ip' / 'pilot' / 'live' / 'inputs.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    side = bughunt.load_side(tmp / 'ip')
    check(side.inputs_path is not None and len(side.inputs) == 5, 'Side: the input journal of a pilot run folder')
    f = tp.finding()
    out = bugpacket.make_packet(tmp / 'packets' / 'ip', f, {'solo': side}, session, None)
    names = sorted(p.name for p in out.iterdir())
    check('inputs.jsonl' in names and 'recording.jsonl' in names and 'inputs.hos' in names, f'packet: the raw journal, the recording and the game-grammar script ({names})')
    hdr, ev = inputlog.read_recording(out / 'recording.jsonl')
    check(hdr['key'] == f.key and hdr['save'] == 'a-library-save' and hdr['seed'] == 4242 and hdr['build'].startswith('63ddacdc9') and len(ev) == 5, f'packet: the recording\'s header names the build, save, seed and key ({hdr})')
    pk = json.loads((out / 'packet.json').read_text())
    check(pk['inputs'] == {'requests': 5, 'recording': 'recording.jsonl', 'hos_script': 'inputs.hos', 'hos_lossy': 3}, f'packet.json: says what the recording is ({pk.get("inputs")})')
    check((out / 'inputs.hos').read_text().startswith('0:A/200'), 'packet: inputs.hos is the game\'s own grammar')
    # replay from the recording: the steps file is the recording's hsap steps, an end after them
    live = tmp / 'rlive'
    pk2 = bugpacket.prepare_replay(out, live, mode='inputs')
    got = (live / 'steps.txt').read_text().splitlines()
    check(got[0] == 'press A 200' and got[-1] == 'end' and any(x.startswith('push ') for x in got), f'replay: --mode inputs sends the recorded requests ({got[:3]}...)')
    check(pk2['replay']['mode'] == 'steps', 'replay: the packet is a solo one')
    # a packet without a journal still makes no recording
    side2, session2 = tp.make_session(tmp, 'ip2')
    out2 = bugpacket.make_packet(tmp / 'packets' / 'ip2', f, {'solo': side2}, session2, None)
    check(not (out2 / 'recording.jsonl').exists() and 'inputs' not in json.loads((out2 / 'packet.json').read_text()), 'packet: no journal, no recording (and nothing claimed)')
    try:
        bugpacket.prepare_replay(out2, tmp / 'rlive2', mode='inputs')
        check(False, 'replay: --mode inputs without a recording is refused')
    except ValueError as e:
        check('no recording' in str(e), 'replay: --mode inputs without a recording is refused')


def run_in(tmp):
    format_checks(tmp)
    hsap_hook_checks(tmp)
    packet_checks(tmp)
    text = (HERE / 'inputlog.py').read_text()
    for bad in ('/home/', 'sk-', 'Bearer '):
        check(bad not in text, f'inputlog.py: no {bad!r}')


def run():
    with tempfile.TemporaryDirectory(prefix='test-inputlog-') as t:
        run_in(Path(t))


def main():
    run()
    if FAILS:
        raise SystemExit(f'test_inputlog: {len(FAILS)} of {CHECKS[0]} checks FAILED')
    print(f'test_inputlog: all {CHECKS[0]} checks passed')


if __name__ == '__main__':
    main()
