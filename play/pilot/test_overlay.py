#!/usr/bin/env python3
"""overlay.py against a made-up run folder whose every time, cost and word is known: reading both folder shapes, the clock,
the three phases of a decision, the candidates and their probabilities, the cost so far, the latest vision answer and its age,
stuck and recovery state, the text rules (nothing of the machine, no escapes, no row wider than its column), picture selection,
key frames, and (when ImageMagick / ffmpeg are installed) the pictures themselves: sizes of the three layouts, the game's own
pixels untouched, the contact sheet and the video's length. No game, no network.  python3 -I -B test_overlay.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import overlay  # noqa: E402
import vision  # noqa: E402  (write_png / read_png only)

W0 = 1000.0     # the made-up wall clock starts here; the state stream's absolute clock is 500000 + t
FPS = 60        # made-up pictures per second: picture N is at t = (N - 100) / 60


def jl(rows):
    return ''.join(json.dumps(r) + '\n' for r in rows)


def state(t, **kw):
    return {'t': t, 'frame': 100 + round(t * FPS), 'pos': [round(t, 1), 10.0, -0.0], 'area': 'MadeUpMap', 'prompt': 'Empty',
            'life': 12, 'max_life': 12, 'rupees': 3, 'child': 1, **kw}


def make_run(root, shape='session'):
    """Four decisions on two goals (known by hand):
      n1 t 0.0   rules, go on `a`, a planner call before it (0.002 USD); result reached, its step ends at t 4.0
      n2 t 4.0   model `test-model`: answers at t 4.45 (decide 500 ms, 0.001 USD), `press-a` 60 %, `go` 30 %; a look before it
                 (0.0003 USD, its answer known at 4.25); result stuck at t 10.0
      n3 t 10.0  the recovery ladder, rung sidestep after a stall of 6 s; result reached at t 13.0, recovered
      n4 t 13.0  rules, press-a; result done at t 15.0, goal g2 met at 15.0; the run ends 6 s later, at t 21
    The pictures: one every second from picture 100 (t 0) to 1360 (t 21), plain colours, 64 x 36."""
    pilot = root / 'pilot' if shape == 'session' else root
    (pilot / 'live').mkdir(parents=True)
    (pilot / 'vision').mkdir()
    shots = root / 'game' / 'shots' if shape == 'session' else root / 'shots'
    shots.mkdir(parents=True)

    def dec(n, t, goal, target, decider, choice, cands, wall, **kw):
        return {'kind': 'decision', 'n': n, 'state': state(t), 'goal': goal, 'target': target, 'decider': decider,
                'candidates': [{'label': c, 'lines': ['x'], 'text': 'does %s' % c} for c in cands], 'choice': choice,
                'predicates': {}, 'plan': None, 'decide_ms': 0.0, 'recover': {'stuck': False, 'why': None, 'rung': 0, 'streak': 1},
                'wall': wall, **kw}

    def res(n, result, t, secs, wall, detail='', interaction=None):
        return {'kind': 'result', 'n': n, 'lines': ['x'], 'result': result, 'moved': 1.0, 'interaction': interaction,
                'steps': [{'ev': 'step', 'in': n, 'src': 'walk 1 1', 'result': result, 'secs': secs, 'moved': 1.0, 'detail': detail,
                           't': t}], 'wall': wall}

    rows = [
        {'kind': 'planner', 'n': 1, 'why': 'start', 'cost_usd': 0.002, 'latency_ms': 900.0, 'wall': W0 - 1.0,
         'request': {'model': 'test-planner'}},
        dec(1, 0.0, 'g1', 'a', 'rules', 'go', ['go', 'press-a', 'next-target'], W0 + 0.0),
        res(1, 'reached', 4.0, 4.0, W0 + 4.05, '0.39 m from the point'),
        dec(2, 4.0, 'g1', 'b', 'test-decider', 'press-a', ['go', 'press-a', 'side-left', 'side-right', 'back-off', 'wait', 'next-target', 'give-up'],
            W0 + 4.5, decide_ms=500.0, latency_ms=480.0, cost_usd=0.001, confidence=0.6, request={'model': 'test-model', 'input': 'not shown'},
            answers=[{'type': 'choice', 'choice': 'press-a', 'probabilities': [{'value': 'go', 'probability': 0.3},
                                                                              {'value': 'press-a', 'probability': 0.6},
                                                                              {'value': 'wait', 'probability': 0.1}]}]),
        res(2, 'stuck', 10.0, 6.0, W0 + 10.05, 'moved under 0.3 m'),
        dec(3, 10.0, 'g1', 'b', 'recover', 'recover:sidestep', ['recover:sidestep'], W0 + 10.1, recover_rung='sidestep', recover_why='blocked',
            recover={'stuck': True, 'why': 'blocked', 'stalled_s': 6.0, 'rung': 1, 'streak': 1}, no_request='recover'),
        res(3, 'reached', 13.0, 3.0, W0 + 13.05),
        {'kind': 'recover', 'n': 3, 'target': 'b', 'status': 'recovered', 'rung': 'sidestep', 's': 9.0, 'wall': W0 + 13.06},
        dec(4, 13.0, 'g2', 'c', 'rules', 'press-a', ['press-a', 'next-target'], W0 + 13.1),
        res(4, 'done', 15.0, 2.0, W0 + 15.05, interaction={'kind': 'door', 'outcome': 'done', 'detail': 'door opened', 'result': 'done'}),
        {'kind': 'goal', 'goal': 'g2', 'status': 'met', 't': 15.0, 'pos': [15, 10, 0], 'wall': W0 + 15.06},
    ]
    (pilot / 'transcript.jsonl').write_text(jl(rows))
    (pilot / 'out.jsonl').write_text(jl([{'ev': 'gameplay', 't': 0.0, 'frame': 100, 'area': 'MadeUpMap'},
                                         {'ev': 'state', 'why': 'wait', 't': 4.0, 'frame': 340, 'pos': [4, 10, 0]}]))
    samples = []
    for k in range(0, 106):
        t = k * 0.2
        s = state(t, prompt='Open' if 8.0 <= t <= 9.0 else 'Empty')
        s['map'] = s.pop('area')
        s['t'] = 500000.0 + t
        samples.append(s)
    (pilot / 'live' / 'state.jsonl').write_text(jl(samples))
    (pilot / 'summary.json').write_text(json.dumps({'run': 'made-up', 'outcome': 'solved', 'copy': '/srv/somewhere/game-copy',
                                                    'runner': ['/usr/bin/python3', '/srv/somewhere/x.py'], 'goals': {'g1': 'failed', 'g2': 'met'}}))
    look = {'seq': 1, 'n': 2, 'why': ['stuck'], 'wall': W0 + 4.3, 't': 4.0, 'model': 'test-eyes', 'frame': 'vision/f0001.png',
            'cost_usd': 0.0003, 'latency_ms': 300.0,
            'answers': {'front': 'wall_or_obstacle', 'screen': 'play', 'says': None,
                        'p': {'door': 0.8, 'chest': 0.0, 'stuck': 0.9, 'clear_left': 0.2, 'clear_right': 0.7, 'other_body_ok': 0.96}},
            'oddities': ['stuck-visible']}
    (pilot / 'vision' / 'vision.jsonl').write_text(jl([look]))
    (pilot / 'vision' / 'f0001.png').write_bytes(vision.write_png(96, 54, bytes([200, 40, 40]) * (96 * 54)))
    for k in range(0, 22):
        color = bytes([(k * 11) % 256, 90, 200 - k * 5])
        (shots / ('vk_%06d.png' % (100 + k * FPS))).write_bytes(vision.write_png(64, 36, color * (64 * 36)))
    return pilot, shots


def look_row_for_test():
    return {'seq': 9, 'n': 2, 'why': ['stuck'], 't': 4.0, 'wall': W0 + 4.3}


def rows_text(rows):
    return ' '.join(t for r in rows for _, t, _ in r.segs)


def fits(rows, cols):
    return all(c + len(t) <= cols for r in rows for c, t, _ in r.segs)


def logic_checks(tmp, check):
    root = tmp / 'session'
    make_run(root)
    files = overlay.Files(root)
    check(files.transcript == root / 'pilot' / 'transcript.jsonl' and files.shots == root / 'game' / 'shots' and files.state is not None
          and files.vision is not None and files.out is not None and files.summary is not None,
          'files: a session folder is found (pilot/ and game/ below it)')
    flat = tmp / 'flat'
    make_run(flat, shape='flat')
    ff = overlay.Files(flat)
    check(ff.transcript == flat / 'transcript.jsonl' and ff.shots == flat / 'shots' and ff.state == flat / 'live' / 'state.jsonl',
          "files: a pilot's own run folder is found (transcript.jsonl at its top, shots/ beside it)")
    run = overlay.Run(files)
    check(run.total == 4 and [d.n for d in run.decisions] == [1, 2, 3, 4], 'run: four decisions in time order')
    check(run.clock is not None and abs(run.time_of(340) - 4.0) < 1e-6 and abs(run.time_of(100)) < 1e-6 and abs(run.time_of(1360) - 21.0) < 0.05,
          'clock: a picture count maps to the pilot clock (60 pictures a second)')
    check(abs(run.clock.presents(10.0) - 700) < 1e-6, 'clock: and back')
    d1, d2, d3, d4 = run.decisions
    check(d1.result == 'reached' and d1.t_res == 4.0 and d2.result == 'stuck' and d2.t_res == 10.0 and d4.detail == 'door opened',
          'run: results, their end times and the interaction detail')
    check(abs(d2.t_choice - 4.45) < 0.02 and d1.t_choice == 0.0,
          f'run: the model answered at t 4.45 by the wall clock, a rules decision at once ({d2.t_choice}, {d1.t_choice})')
    check(abs(d1.cost - 0.002) < 1e-9 and d1.calls == 1 and abs(d2.cost - 0.0013) < 1e-9 and d2.calls == 2,
          'run: the planner row adds to decision 1; the look adds to decision 2 (its cost and a call)')
    check(abs(run.looks[0].t_avail - 4.25) < 0.02, f'run: the look is known at 4.25 ({run.looks[0].t_avail})')
    check(abs(run.t_end - 21.0) < 1e-6 and run.t_start == 0.0, 'run: it ends 6 s after the last result')

    check(overlay.panel_at(run, -1.0) is None, 'panel: nothing before the first decision')
    p = overlay.panel_at(run, 2.0, present=220)
    check(p.n == 1 and p.phase == 'running' and p.goal == 'g1' and p.target == 'a' and p.present == 220,
          'panel: t 2.0 is decision 1, its step running')
    check([c[0] for c in p.candidates] == ['go', 'press-a', 'next-target'] and [c[2] for c in p.candidates] == [True, False, False],
          'panel: candidates in offered order, the chosen one flagged')
    check(p.model_line == 'rules, no model asked' and p.last is None and p.vision is None and p.state_line[0] == 'moving freely',
          'panel: a rules decision names no model; no last step before the first; no look yet')
    check(abs(p.cost - 0.002) < 1e-9 and p.calls == 1, 'panel: cost so far is the planner call')
    p = overlay.panel_at(run, 4.2)
    check(p.n == 2 and p.phase == 'deciding' and not any(c[2] for c in p.candidates) and p.last == ('go', 'reached', '0.39 m from the point'),
          'panel: 4.2 is decision 2 still being decided: nothing chosen, decision 1 shown as last with its word')
    check(p.vision is None and '(asking)' in p.model_line and abs(p.cost - 0.002) < 1e-9,
          'panel: at 4.2 no look is known yet (4.25), the model is marked asking and its cost is not counted yet')
    p = overlay.panel_at(run, 4.3)
    check(p.phase == 'deciding' and p.vision is not None, 'panel: at 4.3 the look is known while the model is still being asked')
    p = overlay.panel_at(run, 4.1)
    check(p.vision is None, 'panel: no look before its answer is known')
    p = overlay.panel_at(run, 5.0)
    check(p.phase == 'running' and [c[0] for c in p.candidates][:3] == ['press-a', 'go', 'wait'] and p.candidates[0][1] == 0.6 and p.candidates[0][2],
          'panel: a model decision lists candidates by its probabilities, the chosen one flagged with its 60 %')
    check(p.model_line == 'test-model  0.48 s  sure 60%' and abs(p.cost - 0.0033) < 1e-9 and p.calls == 3,
          f'panel: model, latency and confidence; cost counts planner + decision + look ({p.model_line} {p.cost} {p.calls})')
    flat_text = ' '.join(t for t, _ in p.vision)
    check('wall_or_obstacle' in flat_text and 'door 80%' in flat_text and 'stuck 90%' in flat_text and 'clear left 20% right 70%' in flat_text
          and 'other body' not in flat_text and 'why: stuck' in flat_text and '1 s ago' in flat_text and ('ODD stuck-visible;', 'bad') in p.vision and p.vision[1][0].startswith('ODD'),
          f'panel: the look in a few words with its age and its oddity, no _ok probability ({flat_text})')
    low = overlay.Look(dict(look_row_for_test(), answers={'front': 'open_ground', 'p': {'stuck': 0.03, 'clear_left': 0.9, 'clear_right': 0.8}}),
                       overlay.Files(root))
    check(' '.join(t for t, _ in overlay.vision_words(low, 2.0)).count('stuck 3%') == 1,
          'panel: a look asked because of a stall says how stuck it thinks Link is even when that is low')
    small = overlay.panel_at(run, 5.0, max_candidates=3)
    check(len(small.candidates) == 3 and small.more == 5 and any(c[2] for c in small.candidates), 'panel: a long list is cut, the chosen one kept, the rest counted')
    p = overlay.panel_at(run, 10.5)
    check(p.n == 3 and p.state_line[0].startswith('RECOVERY rung sidestep (blocked)') and p.state_line[1] == 'warn' and p.last[1] == 'stuck',
          'panel: a recovery decision says so; the last step is the stuck one')
    check(p.model_line == 'recovery ladder, no model', 'panel: the ladder asks no model')
    p = overlay.panel_at(run, 13.5)
    check(p.state_line[0].startswith('recovered by sidestep after 9 s'), 'panel: the step after a recovery says it recovered')
    p = overlay.panel_at(run, 15.5)
    check(p.phase == 'done' and p.result == 'done' and p.detail == 'door opened' and p.goal_status == 'met' and p.run_outcome == 'solved',
          'panel: the end shows the result word, the goal met and the run outcome')
    check(overlay.panel_at(run, 12.0).goal_status == 'open', 'panel: a goal not met yet is open')
    p = overlay.panel_at(run, 8.5)
    check(any('prompt Open' in b for b in p.where) and any('MadeUpMap' in b for b in p.where) and any(b.startswith('x ') for b in p.where),
          'panel: map, position and the prompt come from the nearest state sample')
    check(not any('-0.0' in b for b in p.where), 'panel: no negative zero in a position')

    # text rules
    for t in (0.0, 2.0, 4.2, 5.0, 10.5, 13.5, 15.5):
        pp = overlay.panel_at(run, t, present=300)
        left, right, head = overlay.candidate_rows(pp, 40), overlay.detail_rows(pp, 48), overlay.header_rows(pp, 88, True)
        text = rows_text(left + right + head)
        check('/srv' not in text and 'somewhere' not in text and 'game-copy' not in text and 'not shown' not in text,
              f'text: nothing of the summary paths or the request bodies is drawn (t {t})')
        check(fits(left, 40) and fits(right, 48) and fits(head, 88), f'text: every row fits its column (t {t})')
        check(fits(overlay.detail_rows(pp, 36), 36) and fits(overlay.header_rows(pp, 44, False), 44), f'text: narrow columns too (t {t})')
    check(overlay.clean('50% @x \\n\u00e9') == '50%% @x n?', f"text: clean escapes % and drops backslashes and non-ASCII ({overlay.clean('50% @x \\n' + chr(233))!r})")
    check(overlay.clean('@file').startswith(' @') and overlay.clean('a\n b\t c') == 'a b c',
          'text: a leading @ cannot read a file; whitespace is one space')
    check(overlay.fit('abcdefghij', 6) == 'abc...' and overlay.fit('abc', 6) == 'abc', 'text: fit cuts with an ellipsis')
    runs = overlay.wrap([('alpha beta', 'text'), ('gamma delta epsilon zeta', 'dim')], 12, 2)
    widths = [max(c + len(t) for c, t, _ in ln) for ln in runs]
    check(len(runs) == 2 and max(widths) <= 12 and runs[-1][-1][1].endswith('...'), f'text: wrap fits the width and ends a cut text in an ellipsis ({runs})')
    glued = overlay.wrap([('aa bb'.replace(' ', overlay.GLUE), 'text'), ('cc', 'text')], 6, 3)
    check(glued[0][0][1] == 'aa bb' and len(glued) == 2, f'text: a glued item is one word and shows its spaces ({glued})')
    check(overlay.result_color('reached') == 'ok' and overlay.result_color('stuck') == 'bad' and overlay.result_color('timeout') == 'warn',
          'colours: reached is good, stuck is bad, timeout is a warning')

    # selecting pictures and key frames
    shots = overlay.list_shots(files.shots)
    check(len(shots) == 22 and shots[0][0] == 100 and shots[-1][0] == 1360, 'shots: 22 pictures found, in order')

    class A:
        t_from = t_to = only = None
        every = 1
        limit = 0
    check(len(overlay.select_shots(run, shots, A)) == 22, 'select: all pictures of the run window')
    A.t_from, A.t_to = 3.9, 6.1
    check([n for n, _, _ in overlay.select_shots(run, shots, A)] == [340, 400, 460], 'select: --from/--to keep the window')
    A.t_from = A.t_to = None
    A.every = 5
    check(len(overlay.select_shots(run, shots, A)) == 5, 'select: --every thins')
    A.every, A.limit = 1, 4
    check(len(overlay.select_shots(run, shots, A)) == 4, 'select: --limit spreads evenly')
    A.limit, A.only = 0, '160, 700,1360'
    check([n for n, _, _ in overlay.select_shots(run, shots, A)] == [160, 700, 1360], 'select: --only takes the listed pictures')
    timed = [(n, run.time_of(n), p) for n, p in shots]
    keys = overlay.keyframes(run, timed, 0.0, 21.0)
    check(abs(sum(k[3] for k in keys) - 21.0) < 1e-6 and keys[0][0] == 0.0, f'keyframes: the durations add up to the window ({sum(k[3] for k in keys)})')
    times = [round(k[0], 2) for k in keys]
    check(all(any(abs(t - x) < 0.03 for x in times) for t in (0.0, 4.0, 4.25, 4.45, 10.0, 15.0)) and times == sorted(times),
          f'keyframes: a key frame where a fact changes (decision, look, answer, result) ({times})')
    check(all(a[0] < b[0] for a, b in zip(keys, keys[1:])), 'keyframes: strictly increasing times')
    for d in run.decisions[1:]:       # at its key frame a decision's phase has already changed
        key = next(k[0] for k in keys if abs(k[0] - d.t_choice) < 0.03)
        check(overlay.panel_at(run, key).phase != 'deciding' or d.t_choice == d.t_dec,
              f'keyframes: the key frame of decision {d.n} choosing is not still in its deciding phase ({key} vs {d.t_choice})')
    short = overlay.keyframes(run, timed, 6.0, 8.0)
    check(abs(sum(k[3] for k in short) - 2.0) < 1e-6 and short[0][0] == 6.0, 'keyframes: a window inside the run')
    # the decisions' own states are enough to align, and give the position
    lonely = tmp / 'lonely'
    make_run(lonely)
    (lonely / 'pilot' / 'live' / 'state.jsonl').unlink()
    (lonely / 'pilot' / 'out.jsonl').unlink()
    r2 = overlay.Run(overlay.Files(lonely))
    check(r2.clock is not None and abs(r2.time_of(700) - 10.0) < 1e-6, 'clock: the decisions alone are enough to align')
    check(any(b.startswith('x ') for b in overlay.panel_at(r2, 5.0).where), 'panel: without a state stream the decision state gives the position')
    # one picture per decision for the sheet
    entries = [{'decision': k, 'present': 100 + i, 't': float(i), 'step': 's', 'result': None, 'step_span': [float(i), float(i) + 1]}
               for i, k in enumerate([1, 1, 2, 2, 3, 3, 4, 4])]
    check([e['decision'] for e in overlay.sheet_picks(run, entries, 0)] == [1, 2, 3, 4], 'sheet: one picture per decision')
    check(len(overlay.sheet_picks(run, entries, 2)) == 2, 'sheet: thinned to the asked number')


def px(path, x, y):
    w, h, rgb = vision.read_png(Path(path).read_bytes())
    i = (y * w + x) * 3
    return tuple(rgb[i:i + 3]), w, h


def picture_checks(tmp, check):
    if shutil.which('magick') is None:
        print('test_overlay: ImageMagick not installed: picture checks skipped')
        return
    root = tmp / 'pics'
    make_run(root)
    shot = root / 'game' / 'shots' / 'vk_000400.png'    # t = 5.0
    color = px(shot, 3, 3)[0]
    run = overlay.Run(overlay.Files(root))
    sizes = {}
    for layout in overlay.LAYOUTS:
        st = overlay.Style(layout, 640)
        out = tmp / ('one-%s.png' % layout)
        overlay.render(shot, overlay.panel_at(run, 5.0, present=400), st, out, 640, 360)
        c, w, h = px(out, 4, 4)
        sizes[layout] = (w, h)
        if layout == 'over':
            check(c == color, f'render over: the picture away from the panel is untouched ({c} vs {color})')
            check(px(out, 640 - 30, 30)[0] != color, 'render over: the panel covers the picture near its upper right')
        else:
            check(c == color, f'render {layout}: the game picture is untouched at its corner ({c} vs {color})')
        if layout == 'below':
            check(px(out, 4, 360 + 4)[0] != color and px(out, 320, 359)[0] == color, 'render below: the panel is under the picture, which ends at its last row')
        if layout == 'side':
            check(px(out, 640 + 4, 4)[0] != color and px(out, 639, 359)[0] == color, 'render side: the panel is right of the picture')
    check(sizes['below'][0] == 640 and sizes['below'][1] > 360 and sizes['below'][1] % 2 == 0, f"render below: width kept, taller than the picture ({sizes['below']})")
    check(sizes['side'][1] >= 360 and sizes['side'][0] > 640, f"render side: wider than the picture ({sizes['side']})")
    check(sizes['over'] == (640, 360), f"render over: the picture's own size ({sizes['over']})")
    out = tmp / 'wide.png'
    overlay.render(root / 'pilot' / 'vision' / 'f0001.png', overlay.panel_at(run, 5.0), overlay.Style('below', 640), out, 640, 360)
    check(px(out, 4, 4)[1] == 640, 'render: a 96 x 54 picture is scaled to the width')

    # the whole thing through the command line
    out_dir = tmp / 'out'
    code = overlay.main([str(root), '--out', str(out_dir), '--width', '640', '--sheet', '4', '--looks', '--format', 'jpg'])
    idx = json.loads((out_dir / 'index.json').read_text())
    check(code == 0 and len(idx['frames']) == 22 and all((out_dir / f['file']).exists() for f in idx['frames']), 'cli: a frame for every picture of the run')
    check(idx['sheet'] == 'sheet.jpg' and (out_dir / 'sheet.jpg').stat().st_size > 1000 and len(idx['sheet_frames']) == 4, 'cli: a contact sheet of 4 pictures')
    check(len(idx['looks']) == 1 and (out_dir / idx['looks'][0]['file']).exists(), "cli: --looks annotates the look's own picture")
    first = idx['frames'][0]
    check(first['present'] == 100 and first['decision'] == 1 and first['phase'] == 'running' and first['t'] == 0.0, f'cli: index names picture, decision and phase ({first})')
    mid = next(f for f in idx['frames'] if f['present'] == 400)
    check(mid['decision'] == 2 and mid['step'] == 'press-a', 'cli: picture 400 (t 5.0) belongs to decision 2, press-a')
    out2 = tmp / 'out2'
    code = overlay.main([str(root), '--out', str(out2), '--width', '640', '--layout', 'side', '--only', '400,700', '--sheet', '0', '--format', 'png'])
    i2 = json.loads((out2 / 'index.json').read_text())
    check(code == 0 and [f['present'] for f in i2['frames']] == [400, 700] and 'sheet' not in i2 and (out2 / 'frames' / 'ov_000400.png').exists(),
          'cli: --only, --layout side, --format png, no sheet')
    empty = tmp / 'empty'
    make_run(empty)
    for p in (empty / 'game' / 'shots').iterdir():
        p.unlink()
    try:
        overlay.main([str(empty), '--out', str(tmp / 'out4')])
        check(False, 'cli: no pictures is an error')
    except SystemExit as e:
        check('no pictures' in str(e), 'cli: no pictures is an error that says so')

    if shutil.which('ffmpeg') is None or shutil.which('ffprobe') is None:
        print('test_overlay: ffmpeg not installed: video checks skipped')
        return

    def probe(path):
        r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=width,height,codec_name', '-of', 'json', str(path)],
                           capture_output=True, text=True)
        info = json.loads(r.stdout)
        return float(info['format']['duration']), info['streams'][0]

    out5 = tmp / 'out5'
    code = overlay.main([str(root), '--out', str(out5), '--width', '320', '--video', '--fps', '5', '--every', '30', '--sheet', '0'])
    i5 = json.loads((out5 / 'index.json').read_text())
    dur, s0 = probe(out5 / 'overlay.mp4')
    check(code == 0 and i5['video'] == 'overlay.mp4' and abs(dur - 21.0) < 0.4, f'video: as long as the run (21 s, got {dur})')
    check(s0['codec_name'] == 'h264' and s0['width'] % 2 == 0 and s0['height'] % 2 == 0 and s0['width'] == 320, f'video: h264, even size, the asked width ({s0})')
    out6 = tmp / 'out6'
    overlay.main([str(root), '--out', str(out6), '--width', '320', '--video', '--from', '5', '--to', '15', '--sheet', '0', '--fps', '5'])
    d6, _ = probe(out6 / 'overlay.mp4')
    check(abs(d6 - 10.0) < 0.4, f'video: --from 5 --to 15 is a ten second clip ({d6})')


def publishable_checks(check):
    # nothing of a machine, a game or a key in the files of this tool (the words are put together here so that this file does not hold them)
    words = ('/ho' + 'me/', 'moo' + 'ki', 'nx2' + 'navi', '.hook' + 'shot-h', 'sk-' + 'proj', 'n' + 'c2', 'n' + 's2', 'm' + 'c6')
    for name in ('overlay.py', 'test_overlay.py'):
        text = (HERE / name).read_text()
        for bad in words:
            check(bad not in text, f'publishable: no {bad!r} in {name}')


def run():
    fails, count = [], [0]

    def check(cond, what):
        count[0] += 1
        if not cond:
            fails.append(what)
            print('FAIL', what, flush=True)
    with tempfile.TemporaryDirectory(prefix='overlay-test-') as t:
        logic_checks(Path(t), check)
        picture_checks(Path(t), check)
    publishable_checks(check)
    if fails:
        raise SystemExit(f'test_overlay: {len(fails)} of {count[0]} checks FAILED')
    print(f'test_overlay: all passed ({count[0]} checks)')


if __name__ == '__main__':
    run()
