#!/usr/bin/env python3
"""bughunt.py against made-up run folders whose every number is known: crash, hang, stall, softlock, out of bounds, pictures, log,
audio, desync, give; the layouts a side can have; the deduplication keys. Made-up maps, flags and coordinates only; no game, no
network, no model.   python3 -I -B test_bughunt.py   (test_bugpacket.py, test_hunt.py are the other halves)
"""
import gzip
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bughunt  # noqa: E402
import vision  # noqa: E402
import hs_names  # noqa: E402  (bughunt put the harness folder on sys.path: the game's own file names)

LOG = hs_names.Names(hs_names.PROJECTS[0]).log   # the game's log in a made-up run folder

FAILS = []
CHECKS = [0]


def check(cond, what):
    CHECKS[0] += 1
    if not cond:
        FAILS.append(what)
        print('FAIL', what, flush=True)


# ---- a made-up side on disk

T0 = 1000.0   # the sample clock's start (monotonic seconds)


def sample(t, frame, pos=(0, 10, 0), **kw):
    s = {'t': T0 + t, 'frame': frame, 'map': 'Yard', 'pos': list(pos), 'facing': 0.0, 'camera': 0.0, 'event': 0, 'loading': 0, 'life': 12,
         'max_life': 12, 'rupees': 5, 'prompt': 'Empty', 'music': 'BGM_Yard', 'flags': {}, 'changed': {}, 'child': 1}
    s.update(kw)
    return s


def steady(seconds, start=0.0, frame0=100, hz=10, pos=(0, 10, 0), **kw):
    """samples every 1/hz s for `seconds`, 6 presents each, Link still"""
    n = int(seconds * hz)
    return [sample(start + i / hz, frame0 + i * 6, pos, **kw) for i in range(n)]


def walking(seconds, start=0.0, frame0=100, hz=10, x0=0.0, speed=3.0, **kw):
    n = int(seconds * hz)
    return [sample(start + i / hz, frame0 + i * 6, (x0 + speed * i / hz, 10.0, 0.0), **kw) for i in range(n)]


def step(t, src, result='reached', **kw):
    return {'ev': 'step', 'in': 1, 'src': src, 'result': result, 'secs': 1.0, 'moved': 1.0, 'detail': '', 't': t, **kw}


def present_rows(frames, gaps=None, t0=0.0):
    """present.csv text: frame, return_ns, interval_ns; gaps {frame: ms}"""
    gaps = gaps or {}
    lines = ['frame,return_ns,interval_ns,present_begin_ns,renderer_begin_ns,renderer_end_ns,vcore_back_ns']
    t = (T0 + t0) * 1e9
    for f in range(1, frames + 1):
        iv = int(gaps.get(f, 16.6) * 1e6)
        t += iv
        lines.append(f'{f},{int(t)},{0 if f == 1 else iv},0,0,0,0')
    return '\n'.join(lines) + '\n'


def put(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def make_side(root, states, events=None, log='', summary=None, exit_code=None, present=None, steps_text=None, game_sub=True):
    """A hunt-session layout: <root>/pilot/{live/state.jsonl, out.jsonl, steps.txt}, <root>/game/{log, summary.txt, exit.txt, present.csv}"""
    root = Path(root)
    pilot = root / 'pilot'
    game = root / 'game'
    put(pilot / 'live' / 'state.jsonl', ''.join(json.dumps(s) + '\n' for s in states))
    if events is not None:
        put(pilot / 'out.jsonl', ''.join(json.dumps(e) + '\n' for e in events))
    if steps_text is not None:
        put(pilot / 'steps.txt', steps_text)
    put(game / LOG, log)
    if summary is not None:
        put(game / 'summary.txt', summary)
    if exit_code is not None:
        put(game / 'exit.txt', str(exit_code))
    if present is not None:
        put(game / 'present.csv', present)
    return bughunt.load_side(root)


def events_for(states, steps=(), done=True, t_rel0=0.0):
    """out.jsonl: a gameplay event, state events that match samples by frame, the steps, done. `t` is the pilot's clock: sample clock - T0."""
    ev = [{'ev': 'gameplay', 't': 0.0, 'frame': states[0]['frame'], 'area': 'Yard'}]
    for s in states[::5]:
        ev.append({'ev': 'state', 'why': 'wait', 'n': 1, 't': round(s['t'] - T0, 3), 'frame': s['frame']})
    ev += list(steps)
    if done:
        ev.append({'ev': 'done', 't': round(states[-1]['t'] - T0, 3)})
    return ev


OK_SUMMARY = 'hs-run x exit=143 wall=120.0s span=100s frames=6000(headless-renderer) mean=58.4 fatal=0 crash=0 devlost=0 nocore=0 kernel=0 nvrm=0 dev=0:GPU'


def tb_step_end(t):
    return {'ev': 'step', 'in': 9, 'src': 'end', 'result': 'done', 'secs': 0.0, 'moved': 0.0, 'detail': '', 't': t}


def solo_checks(tmp):
    cfg = bughunt.Config()
    # ---- keys
    a = bughunt.shape('[hos host] vk: slow present: 2770.7 ms: at 0x7fcd7cd200 pool 0x107abb0000+0x120 /tmp/some/very/long/path/x.png')
    b = bughunt.shape('[hos host] vk: slow present: 15.2 ms: at 0x11 pool 0x22+0x33 /var/other/very/long/pathname/y.png')
    check(a == b, f'shape: numbers, addresses and paths blanked ({a!r})')
    check(bughunt.shape('[hos Some Thread] vk: texture slot 0x10: no image for it; NVN target 1 format 0x8c 85x40x1 levels 1') ==
          bughunt.shape('[hos Other] vk: texture slot 0x99: no image for it; NVN target 2 format 0x1 1024x512x1 levels 4'), 'shape: the thread name and sizes are blanked')
    check(not bughunt.trouble('[hos] vcores: 5 takes, 0 starved grants, 0 escapes in 5 s') and bughunt.trouble('[hos] vcores: 5 takes, 3 starved grants')
          and not bughunt.trouble('[hos] prepared 10 programs (10 new, 0 failed)') and bughunt.trouble('[hos] prepared 10 programs (9 new, 1 failed)')
          and bughunt.trouble('FATAL: x'), 'trouble: a zero count is accounting, a non-zero one is trouble')
    check(bughunt.make_key('log', 'x', 'a') == bughunt.make_key('log', 'x', 'a') and bughunt.make_key('log', 'x', 'a') != bughunt.make_key('log', 'x', 'b'),
          'make_key is stable and tells parts apart')
    k1 = bughunt.place_key('oob', 'below-floor', 'Yard', [3.0, 0, 3.0], 16.0)
    k2 = bughunt.place_key('oob', 'below-floor', 'Yard', [10.0, 0, 12.0], 16.0)
    k3 = bughunt.place_key('oob', 'below-floor', 'Yard', [40.0, 0, 12.0], 16.0)
    check(k1 == k2 and k1 != k3 and k1.startswith('oob:below-floor:'), 'place_key: the same 16 m cell is one key, another cell another')

    # ---- config
    check(bughunt.Config.from_dict({'hang_s': 12, 'shared': ['a', 'b']}).hang_s == 12.0 and bughunt.Config.from_dict({'shared': ['a']}).shared == ('a',),
          'Config.from_dict takes numbers and lists')
    try:
        bughunt.Config.from_dict({'nonsense': 1})
        check(False, 'Config.from_dict refuses an unknown key')
    except ValueError:
        check(True, 'Config.from_dict refuses an unknown key')

    # ---- crash
    st = steady(10)
    side = make_side(tmp / 'c0', st, log='[hos] all well\n', summary=OK_SUMMARY, exit_code=143)
    r = bughunt.detect_crash(side, cfg)
    check(r.status == 'ok' and r.looked == 1, f'crash: a clean run is ok ({r.status})')
    side = make_side(tmp / 'c1', st, log='[hos host] vk: x\nCRASH: SIGSEGV in f_80123456 at 0x1234\n', exit_code=139,
                     summary=OK_SUMMARY.replace('crash=0', 'crash=1').replace('exit=143', 'exit=139'))
    r = bughunt.detect_crash(side, cfg)
    subs = sorted(f.sub for f in r.findings)
    check(r.status == 'found' and 'crash' in subs and 'exit' in subs and all(f.severity == 'error' for f in r.findings), f'crash: the counter and the exit code ({subs})')
    check(any('SIGSEGV' in f.text and f.evidence.get('exit') == 139 for f in r.findings), 'crash: the signal is named')
    a_key = [f.key for f in r.findings if f.sub == 'crash'][0]
    side2 = make_side(tmp / 'c2', st, log='CRASH: SIGSEGV in f_80123456 at 0x9999\n', exit_code=139, summary=OK_SUMMARY.replace('crash=0', 'crash=2'))
    check([f.key for f in bughunt.detect_crash(side2, cfg).findings if f.sub == 'crash'][0] == a_key, 'crash: the same line with other numbers is the same key')
    for code, expected in ((0, 'ok'), (124, 'ok'), (143, 'ok'), (134, 'found'), (137, 'found')):
        side = make_side(tmp / f'ce{code}', st, log='x\n', exit_code=code)
        check(bughunt.detect_crash(side, cfg).status == expected, f'crash: exit {code} is {expected}')
    end_step = [{'ev': 'step', 'in': 9, 'src': 'end', 'result': 'done', 't': round(st[-1]['t'] - T0, 3)}]
    side = make_side(tmp / 'cs137', st, events=events_for(st, steps=end_step), log='x\n', exit_code=137)
    r = bughunt.detect_crash(side, cfg)
    check([(f.sub, f.severity) for f in r.findings] == [('slow-stop', 'warning')], f'crash: SIGKILL after the pilot\'s end step was done is a game that did not stop on SIGTERM in time, a warning ({[(f.sub, f.severity) for f in r.findings]})')
    side = make_side(tmp / 'cs137o', st, events=events_for(st, steps=end_step), log='x\n', exit_code=137)
    put(tmp / 'cs137o' / 'game' / 'kernel.txt', 'Out of memory: Killed process 42 (game)\n')
    check([f.sub for f in bughunt.detect_crash(side, cfg).findings] == ['exit'], 'crash: with an out-of-memory line in the kernel log the SIGKILL stays a crash')
    side = make_side(tmp / 'cs137n', st, events=events_for(st), log='x\n', exit_code=137)
    check([f.sub for f in bughunt.detect_crash(side, cfg).findings] == ['exit'], 'crash: SIGKILL with no end step is still a crash')
    side = make_side(tmp / 'cn', st, log='x\n', summary=OK_SUMMARY.replace('nocore=0', 'nocore=3'), exit_code=143)
    r = bughunt.detect_crash(side, cfg)
    check([f.severity for f in r.findings] == ['info'] and r.findings[0].sub == 'nocore', 'crash: a few nocore lines are noise (info): every real run says some')
    side = make_side(tmp / 'cn2', st, log='x\n', summary=OK_SUMMARY.replace('nocore=0', 'nocore=40'), exit_code=143)
    check([f.severity for f in bughunt.detect_crash(side, cfg).findings] == ['warning'], 'crash: 40 nocore lines are a warning')
    side = make_side(tmp / 'cd', st, log='x\n', summary=OK_SUMMARY.replace('devlost=0', 'devlost=1').replace('nvrm=0', 'nvrm=2'), exit_code=143)
    check({f.sub for f in bughunt.detect_crash(side, cfg).findings} == {'devlost', 'driver'}, 'crash: device lost and an NVRM count are errors')
    side = make_side(tmp / 'cu', st, log='')
    check(bughunt.detect_crash(side, cfg).status == 'unknown', 'crash: no summary, no exit, no log: unknown, not a pass')
    side = make_side(tmp / 'cf', st, log='a\nFATAL: out of memory\n')
    check(bughunt.detect_crash(side, cfg).findings[0].sub == 'fatal-line', 'crash: a FATAL line without a summary is found')

    # ---- hang
    st = steady(5) + steady(5, start=45.0, frame0=1000)   # a 40 s hole after 5 s
    side = make_side(tmp / 'h0', st, events=events_for(st))
    r = bughunt.detect_hang(side, cfg)
    check(r.status == 'found' and r.findings[0].sub == 'resumed' and 39 < r.findings[0].evidence['gap_s'] < 41, f'hang: a 40 s hole is found ({r.status})')
    check(r.findings[0].map == 'Yard' and r.findings[0].t is not None and r.findings[0].game_s is not None, 'hang: the finding says where and when')
    st = steady(30)
    side = make_side(tmp / 'h1', st, events=events_for(st))
    check(bughunt.detect_hang(side, cfg).status == 'ok', 'hang: a steady run is ok')
    st = steady(5) + [sample(20.0, 130)]    # the frame counter stood still while a sample came 15 s later
    st = steady(5, frame0=100)
    st.append(sample(25.0, st[-1]['frame']))
    side = make_side(tmp / 'h2', st, events=events_for(st))
    r = bughunt.detect_hang(side, cfg)
    check(r.status == 'found' and r.findings[0].sub == 'frame-frozen', f'hang: a frame counter that stands still ({[f.sub for f in r.findings]})')
    st = steady(10)
    side = make_side(tmp / 'h3', st, events=events_for(st), present=present_rows(3000))   # presents run to 50 s, samples end at 10 s
    r = bughunt.detect_hang(side, cfg)
    check(any(f.sub == 'state-stream-stopped' for f in r.findings), 'hang: presents far beyond the last sample: the sample stream died')
    side = make_side(tmp / 'h4', st, events=events_for(st, done=False), exit_code=124)
    ne = [f for f in bughunt.detect_hang(side, cfg).findings if f.sub == 'no-end']
    check(len(ne) == 1 and ne[0].severity == 'info' and 'reached its wall' in ne[0].text, 'hang: a run that reached its wall without `done` is explained (the budget), not a hang')
    side = make_side(tmp / 'h4b', st, events=events_for(st, done=False), exit_code=124, present=present_rows(3000))   # presents run to 50 s, samples end at 10 s
    ne = [f for f in bughunt.detect_hang(side, cfg).findings if f.sub == 'no-end']
    check(len(ne) == 1 and ne[0].severity == 'warning' and 'stopped answering' in ne[0].text, 'hang: at the wall with the samples long over before the last present it stays a warning')
    side = make_side(tmp / 'h5', st, events=events_for(st, done=False), exit_code=143)
    check(not any(f.sub == 'no-end' for f in bughunt.detect_hang(side, cfg).findings), 'hang: a stop by us without done is not a hang')
    check(bughunt.detect_hang(make_side(tmp / 'h6', [sample(0, 1)]), cfg).status == 'unknown', 'hang: one sample: unknown')

    # ---- stall
    st = steady(60)
    pres = present_rows(3600, gaps={1500: 700.0, 1501: 800.0, 3000: 4500.0})   # frames 1500-1501: a hitch at 25 s; frame 3000: a 4.5 s stall at ~50 s
    side = make_side(tmp / 's0', st, events=events_for(st), present=pres)
    r = bughunt.detect_stall(side, cfg)
    sev = sorted(f.severity for f in r.findings)
    check(sev == ['error', 'warning'], f'stall: a hitch and a stall are two findings ({sev})')
    hitch = [f for f in r.findings if f.severity == 'warning'][0]
    check(hitch.evidence['n'] == 2 and hitch.evidence['max_ms'] == 800 and hitch.sub == 'hitch', 'stall: two adjacent slow presents are one group')
    big = [f for f in r.findings if f.severity == 'error'][0]
    check(big.sub == 'stall' and big.evidence['max_ms'] == 4500 and big.map == 'Yard', 'stall: the 4.5 s gap is an error with its place')
    check(big.key.startswith('stall:stall:') and hitch.key.startswith('stall:hitch:'), 'stall: the key says hitch or stall')
    pres = present_rows(3600, gaps={30: 5000.0})   # 0.5 s into the run: the warm-up
    side = make_side(tmp / 's1', st, events=events_for(st), present=pres)
    r = bughunt.detect_stall(side, cfg)
    check([f.severity for f in r.findings] == ['info'] and 'first seconds' in r.findings[0].text, 'stall: a gap in the first seconds is explained (info)')
    st2 = steady(60)
    for s in st2[400:420]:
        s['loading'] = 1
    side = make_side(tmp / 's2', st2, events=events_for(st2), present=present_rows(3600, gaps={2400: 6000.0}))   # ~40 s, inside the load
    r = bughunt.detect_stall(side, cfg)
    check([f.severity for f in r.findings] == ['info'] and 'load' in r.findings[0].text, 'stall: a gap inside a load is explained (info)')
    pres = present_rows(3600, gaps={3500: 6000.0})   # a 6 s gap at ~58 s, after the pilot's `end` step at 55 s: the game is being stopped
    side = make_side(tmp / 's2e', st, events=events_for(st, [tb_step_end(55.0)]), present=pres)
    r = bughunt.detect_stall(side, cfg)
    check([f.severity for f in r.findings] == ['info'] and 'being stopped' in r.findings[0].text, f'stall: a gap after the end step is explained, not a finding ({[f.severity for f in r.findings]})')
    side = make_side(tmp / 's3', st, events=events_for(st))   # no present trace: the samples' own gaps
    check(bughunt.detect_stall(side, cfg).status == 'ok', 'stall: no present trace, steady samples: ok on the samples')
    stg = steady(30) + steady(30, start=35.0, frame0=1900)     # 5 s with no sample, 6 presents apart
    side = make_side(tmp / 's4', stg, events=events_for(stg))
    r = bughunt.detect_stall(side, cfg)
    check(r.findings and r.findings[0].evidence['basis'] == 'samples' and r.findings[0].severity == 'error', 'stall: a 5 s sample gap is a stall on the samples basis')
    check(bughunt.detect_stall(make_side(tmp / 's5', [], events=[]), cfg).status == 'unknown', 'stall: nothing at all: unknown')

    # ---- softlock
    def softlock_side(name, states, steps, **kw):
        return make_side(tmp / name, states, events=events_for(states, steps), **kw)

    st = steady(240)
    steps = [step(10.0 + 20 * i, 'walk 3.0 4.0 radius 1', 'stuck') for i in range(8)]
    side = softlock_side('l0', st, steps)
    r = bughunt.detect_softlock(side, cfg)
    check(r.status == 'found' and r.findings[0].sub == 'still' and r.findings[0].evidence['inputs'] >= 8, f'softlock: inputs and nothing changing for 180 s ({r.status})')
    check(180 <= r.findings[0].evidence['held_s'] < 190, 'softlock: reported when the window is reached')
    check(len(r.findings) == 1, 'softlock: once for one stretch')
    side = softlock_side('l1', st, [])
    check(bughunt.detect_softlock(side, cfg).status == 'unknown', 'softlock: no steps with a clock: unknown')
    side = softlock_side('l2', st, [step(5.0, 'wait 5', 'done'), step(30.0, 'report 1', 'done')])
    check(bughunt.detect_softlock(side, cfg).status == 'ok', 'softlock: waits and reports are not inputs: the pilot idling is not a lock')
    side = softlock_side('l3', st, [step(10.0, 'walk 1 1', 'stuck'), step(20.0, 'walk 1 1', 'stuck')])
    check(bughunt.detect_softlock(side, cfg).status == 'ok', 'softlock: two inputs only: ok')
    st3 = steady(100) + walking(140, start=100.0, frame0=700, x0=0.0)
    side = softlock_side('l4', st3, [step(10.0 + 20 * i, 'walk 3.0 4.0', 'stuck') for i in range(12)])
    check(bughunt.detect_softlock(side, cfg).status == 'ok', 'softlock: 100 s still and then walking: under the limit, ok')
    st4 = steady(240, event=1, music='BGM_Yard')
    side = softlock_side('l5', st4, steps)
    r = bughunt.detect_softlock(side, cfg)
    check(r.findings and r.findings[0].sub == 'text-held', 'softlock: a text box that never closes is text-held')
    st5 = steady(240, event=1, music='Dm_Cs')
    side = softlock_side('l6', st5, steps)
    check(bughunt.detect_softlock(side, cfg).status == 'ok', 'softlock: a cutscene gets twice the time')
    st6 = steady(400, event=1, music='Dm_Cs')
    side = softlock_side('l7', st6, [step(10.0 + 20 * i, 'press A', 'done') for i in range(19)])
    r = bughunt.detect_softlock(side, cfg)
    check(r.findings and r.findings[0].sub == 'scene-held' and r.findings[0].evidence['held_s'] >= 360, 'softlock: a cutscene longer than twice the time is scene-held')
    st7 = [dict(s, flags={'f': 0}) for s in steady(100)] + [dict(s, flags={'f': 1}) for s in steady(140, start=100.0, frame0=700)]
    side = softlock_side('l8', st7, [step(10.0 + 20 * i, 'walk 3 4', 'stuck') for i in range(12)])
    check(bughunt.detect_softlock(side, cfg).status == 'ok', 'softlock: a flag that changes is a change')

    # ---- out of bounds
    bounds = bughunt.Bounds({'Yard': {'x': [-50.0, 50.0], 'y': [0.0, 20.0], 'z': [-50.0, 50.0]}})
    low = steady(2, start=2.0, frame0=500, pos=(0, -40, 0))
    side = make_side(tmp / 'o0', steady(2) + low + steady(2, start=5.0, frame0=900), events=events_for(steady(2)))
    r = bughunt.detect_oob(side, cfg, bounds)
    check(r.status == 'found' and r.findings[0].sub == 'below-floor' and r.findings[0].evidence['samples'] >= 3, f'oob: below the floor for several samples ({r.status})')
    side = make_side(tmp / 'o1', steady(2) + steady(0.2, start=2.0, frame0=500, pos=(0, -40, 0)) + steady(2, start=3.0, frame0=900), events=events_for(steady(2)))
    check(bughunt.detect_oob(side, cfg, bounds).status == 'ok', 'oob: one bad sample is not enough')
    side = make_side(tmp / 'o2', steady(3, pos=(200, 10, 0)), events=events_for(steady(3)))
    check(bughunt.detect_oob(side, cfg, bounds).findings[0].sub == 'outside-box', 'oob: outside the box by more than the margin')
    side = make_side(tmp / 'o3', steady(3, pos=(70, 10, 0)), events=events_for(steady(3)))
    check(bughunt.detect_oob(side, cfg, bounds).status == 'ok', 'oob: 20 m outside the box is inside the margin')
    side = make_side(tmp / 'o4', steady(3, pos=(0, 400, 0)), events=events_for(steady(3)))
    check(bughunt.detect_oob(side, cfg, bounds).findings[0].sub == 'above-ceiling', 'oob: far above the ceiling')
    side = make_side(tmp / 'o5', steady(3, map='Nowhere'), events=events_for(steady(3)))
    check(bughunt.detect_oob(side, cfg, bounds).findings[0].sub == 'unknown-map', 'oob: a map no bounds know')
    side = make_side(tmp / 'o6', steady(6, pos=(0, -90, 0), event=1), events=events_for(steady(3)))
    check(bughunt.detect_oob(side, cfg, bounds).status == 'ok', 'oob: a scene parks Link anywhere: events are skipped')
    side = make_side(tmp / 'o7', steady(6, pos=(0, -90, 0), loading=1), events=events_for(steady(3)))
    check(bughunt.detect_oob(side, cfg, bounds).status == 'ok', 'oob: loads are skipped')
    check(bughunt.detect_oob(side, cfg, None).status == 'unknown', 'oob: no bounds file: unknown')
    world = tmp / 'world'
    (world / 'nav').mkdir(parents=True)
    with gzip.open(world / 'nav' / 'Cave.json.gz', 'wt') as f:
        json.dump({'verts': [-5, 2, -7, 5, 3, 9, 0, 1, 0]}, f)
    b = bughunt.build_bounds(world)
    check(b['maps']['Cave'] == {'x': [-5.0, 5.0], 'y': [1.0, 3.0], 'z': [-7.0, 9.0]}, 'bounds: the box of a nav mesh\'s vertices')
    (tmp / 'b.json').write_text(json.dumps(b))
    check(bughunt.Bounds.load(tmp / 'b.json').maps.keys() == {'Cave'}, 'bounds: written and read back')

    # ---- log, audio
    ref = tmp / 'ref.txt'
    ref.write_text('[hos] vk: storage buffer NOT bound (reads zeros): program 1a2b3c4d5e6f7a8b stage 1 size 0x20\n[hos] fine line\n'
                   '[a64] unimplemented import _ZN2nn5audio3FooEv (lr 0x81044370)\n')
    base = bughunt.build_baseline([ref])
    check(len(base) == 2, f'baseline: only trouble lines are kept ({len(base)})')
    (tmp / 'known.json').write_text(json.dumps({'logs': 1, 'shapes': base}))
    check(bughunt.load_baseline(tmp / 'known.json') == base, 'baseline: written and read back')
    log = ('[hos] vk: storage buffer NOT bound (reads zeros): program ffffffffffffffff stage 2 size 0x40\n'
           '[hos] vk: the shadow of pool 0x1 failed to import (code -3)\n'
           '[hos] vk: the shadow of pool 0x2 failed to import (code -5)\n'
           '[hos] vk: assertion failed: x != 0\n'
           '[hos] fine\n')
    side = make_side(tmp / 'g0', steady(3), log=log)
    r = bughunt.detect_log(side, cfg, base)
    texts = sorted((f.sub, f.evidence['count']) for f in r.findings)
    check(texts == [('hard', 1), ('new-line', 2)], f'log: known shapes are quiet, new ones counted by shape ({texts})')
    check(any(f.severity == 'error' for f in r.findings if f.sub == 'hard') and all(f.severity == 'warning' for f in r.findings if f.sub == 'new-line'), 'log: a hard line is an error, a new line a warning')
    check(bughunt.detect_log(side, cfg, None).status == 'unknown', 'log: no baseline: unknown (every line would be new)')
    check(bughunt.detect_log(make_side(tmp / 'g1', steady(3), log=''), cfg, base).status == 'unknown', 'log: no log: unknown')
    side = make_side(tmp / 'a0', steady(3), log='[hos] audio: renderer opened\n[hos] audio: voice 0 ok\n')
    check(bughunt.detect_audio(side, cfg).status == 'ok', 'audio: a renderer that opened is ok')
    side = make_side(tmp / 'a1', steady(3), log='[hos] audio: renderer opened\n[hos] audio: device lost, stopped\n')
    check(bughunt.detect_audio(side, cfg).findings[0].sub == 'error-line', 'audio: an error line')
    side = make_side(tmp / 'a2', steady(3), log='[hos] audio: stereo\n')
    check(bughunt.detect_audio(side, cfg).findings[0].sub == 'no-renderer', 'audio: music in the state and no renderer line')
    side = make_side(tmp / 'a3', steady(3), log='[hos] fine\n')
    r = bughunt.detect_audio(side, cfg)
    check(r.status == 'unknown' and 'silence' in r.reason, 'audio: no audio lines at all: unknown, with the reason')

    # ---- give
    def given(per_before, after, flip_at=3.0):
        out = []
        for i in range(80):
            t = i / 10
            flags = {'chest_flag': 1 if t >= flip_at else 0, 'keys': per_before if t < flip_at + 0.5 else after}
            out.append(sample(t, 100 + 6 * i, flags=flags))
        return out
    rule = {'name': 'small-key chest', 'flag': 'chest_flag', 'counter': 'keys', 'per_flag': 1}
    gcfg = bughunt.Config(give_rules=(rule,))
    r = bughunt.detect_give(make_side(tmp / 'k0', given(3, 5)), gcfg)
    check(r.status == 'found' and r.findings[0].sub == 'double' and r.findings[0].evidence['delta'] == 2, f'give: one flip, +2: a double give ({r.status})')
    check(r.findings[0].key == bughunt.make_key('give', 'double', 'small-key chest') and 'small-key chest' in r.findings[0].text, 'give: keyed by the rule')
    check(bughunt.detect_give(make_side(tmp / 'k1', given(3, 4)), gcfg).status == 'ok', 'give: one flip, +1: fine')
    check(bughunt.detect_give(make_side(tmp / 'k2', given(3, 3)), gcfg).status == 'ok', 'give: no counter change is not an over-give')
    check(bughunt.detect_give(make_side(tmp / 'k3', given(3, 5)), bughunt.Config()).status == 'unknown', 'give: no rules: unknown')

    def given_before_flag(a, b, c):
        """the real order: the counter rises while the message is open (a -> b -> c, 0.4 s apart) and the flag flips 1 s after the last rise"""
        out = []
        for i in range(120):
            t = i / 10
            n = a if t < 5.0 else (b if t < 5.4 else c)
            out.append(sample(t, 100 + 6 * i, flags={'chest_flag': 1 if t >= 6.4 else 0, 'keys': n}))
        return out
    r = bughunt.detect_give(make_side(tmp / 'k4', given_before_flag(3, 4, 5)), gcfg)
    check(r.status == 'found' and r.findings[0].evidence['before'] == 3 and r.findings[0].evidence['after'] == 5, f'give: the counter rises while the message is open and the flag flips a second later: still +2 ({r.status})')
    check(bughunt.detect_give(make_side(tmp / 'k5', given_before_flag(3, 3, 4)), gcfg).status == 'ok', 'give: the same order with one key is fine')
    check(bughunt.detect_give(make_side(tmp / 'k6', given_before_flag(3, 3, 4)), bughunt.Config(give_rules=(rule,), give_lookback_s=0.5)).status in ('ok', 'unknown'), 'give: a short lookback sees only the end')

    # ---- the artefact patterns and the whole analysis
    st = steady(30)
    side = make_side(tmp / 'z0', st, events=events_for(st), log='x\n', summary=OK_SUMMARY, exit_code=143, present=present_rows(1800, gaps={1000: 5000.0}))
    acfg = bughunt.Config(artefacts=(r'slow present|\d+ slow',))
    rep = bughunt.analyze(tmp / 'z0', acfg, None, None)
    fnd = [f for f in rep['findings'] if f.severity != 'info']
    check(rep['sides'] == ['solo'] and any(f.kind == 'stall' for f in fnd), 'analyze: a hunt-session folder is one side `solo`')
    check(all(f.status == 'artefact' for f in fnd if f.kind == 'stall'), 'analyze: a configured artefact pattern marks the finding')
    rows = rep['detectors']['solo']
    check(rows['crash']['status'] == 'ok' and rows['oob']['status'] == 'unknown' and rows['log']['status'] == 'unknown', 'analyze: ok where looked, unknown where the input is missing')
    lines = bughunt.summarize(rep)
    check(any('stall' in ln and 'found' in ln for ln in lines) and any('<stall:stall:' in ln for ln in lines), 'summarize: a row per detector and a line per finding with its key')
    boom = bughunt.analyze_side(side, bughunt.Config(), only=('crash',))
    check(set(boom) == {'crash'}, 'analyze_side: `only` limits the detectors')
    orig = bughunt.detect_hang
    bughunt.detect_hang = lambda s, c: 1 / 0
    try:
        out = bughunt.analyze_side(side, bughunt.Config(), only=('hang', 'crash'))
    finally:
        bughunt.detect_hang = orig
    check(out['hang'].status == 'unknown' and 'ZeroDivisionError' in out['hang'].reason and out['crash'].status in ('ok', 'found'), 'analyze_side: a detector that raises is unknown, the others run')


def offset_checks(tmp):
    # a co-op runner samples every 3 presents from another phase than the pilot's own subscription (every 6): no frame in common
    st = [sample(i / 20, 101 + 3 * i) for i in range(400)]
    ev = [{'ev': 'gameplay', 't': 0.0, 'frame': 100, 'area': 'Yard'}] + [{'ev': 'state', 'why': 'wait', 'n': 1, 't': round((100 + 6 * k - 101) / 60.0, 3), 'frame': 100 + 6 * k} for k in range(1, 60)]
    side = make_side(tmp / 'off', st, events=ev + [tb_step_end(5.0)])
    off = side.clock_offset()
    check(off is not None and abs(off - (T0 + 1 / 60.0)) < 0.05, f'clock_offset: with no present in common, the nearest samples give it ({off})')
    check(side.end_t() is not None and abs(side.end_t() - (T0 + 5.0)) < 0.1, 'end_t: the sample-clock time of the end step')
    side = make_side(tmp / 'off2', st, events=ev + [{'ev': 'done', 't': 19.0}])
    check(side.end_t() is None, 'end_t: no end step: None (a `done` alone does not say how long the stop took)')


def layout_checks(tmp):
    # a co-op session side: <side>/state.jsonl with {"w", "game": {...}}, log.txt, present.csv, side.json, pilot/
    root = tmp / 'sess'
    for name, off in (('A', 0.0), ('B', 0.0)):
        d = root / name
        rows = [{'w': 5000.0 + s['t'] - T0, 'frame': s['frame'], 'game': {k: v for k, v in s.items() if k not in ('child',)} | {'age': 'child'}} for s in steady(20)]
        put(d / 'state.jsonl', ''.join(json.dumps(r) + '\n' for r in rows))
        put(d / 'log.txt', '[hos] fine\n')
        put(d / 'present.csv', present_rows(1200))
        put(d / 'side.json', json.dumps({'id': name}))
        put(d / 'exit.txt', '124')
    sides = bughunt.find_sides(root)
    check(list(sides) == ['A', 'B'], 'find_sides: side folders of a co-op session')
    s = sides['A']
    check(len(s.states) == 200 and s.states[0]['child'] == 1 and 'w' in s.states[0] and s.exit_code == 124 and s.log == ['[hos] fine'],
          'load_side: a co-op side\'s nested rows are flattened')
    check(len(s.present) == 1199 and abs(s.present[0][2] - 16.6) < 0.01, 'present: the first row\'s zero interval is left out')
    check(s.gameplay[1] == s.states[0]['frame'], 'gameplay: the first sample without a gameplay event')
    solo = bughunt.find_sides(tmp / 'z0')
    check(list(solo) == ['solo'] and solo['solo'].pilot is not None and solo['solo'].game is not None, 'find_sides: a hunt session is one side')
    check(solo['solo'].clock_offset() is not None and abs(solo['solo'].clock_offset() - T0) < 0.01, 'clock_offset: the pilot\'s clock against the samples\'')
    # the game's log is named for the project the copy was built from (hs_names); a co-op side or a plain run keeps log.txt / run.log
    for p in hs_names.PROJECTS:
        d = tmp / f'pl-{p}'
        put(d / hs_names.Names(p).log, 'x\n')
        check(bughunt.pick_log(d) == d / hs_names.Names(p).log, f'pick_log: the log of a copy built as the project {p!r}')
    for n in ('log.txt', 'run.log'):
        d = tmp / f'pl-{n}'
        put(d / n, 'x\n')
        check(bughunt.pick_log(d) == d / n, f'pick_log: {n}')
    check(bughunt.pick_log(tmp / 'pl-none') is None, 'pick_log: no log is None')
    # shots by present number
    for fr in (90, 180, 270):
        (root / 'A' / 'shots').mkdir(exist_ok=True)
        (root / 'A' / 'shots' / f'vk_{fr:06d}.png').write_bytes(vision.write_png(4, 4, bytes([10, 20, 30] * 16)))
    check([f for f, _ in bughunt.load_side(root / 'A').shots] == [90, 180, 270], 'shots: the present number from the file name')
    (root / 'B' / 'auto').mkdir()
    (root / 'B' / 'auto' / 'vk_000600.png').write_bytes(vision.write_png(4, 4, bytes([1, 2, 3] * 16)))
    (root / 'B' / 'shots').mkdir()
    (root / 'B' / 'shots' / 't0040.png').write_bytes(vision.write_png(4, 4, bytes([1, 2, 3] * 16)))
    check([f for f, _ in bughunt.load_side(root / 'B').shots] == [600], 'shots: a co-op side\'s periodic pictures are in auto/; named ones (t0040) are not presents')

    # desync: two sides, shared flag disagrees for 20 s
    cfg = bughunt.Config(shared=('shared_flag',), desync_grace_s=10.0)
    a = [sample(i / 10, 100 + 6 * i, flags={'shared_flag': 1 if i >= 50 else 0}) for i in range(300)]
    b = [sample(i / 10, 100 + 6 * i, flags={'shared_flag': 1 if i >= 250 else 0}) for i in range(300)]
    sa = make_side(tmp / 'pa', a, events=events_for(a))
    sb = make_side(tmp / 'pb', b, events=events_for(b))
    r = bughunt.detect_desync({'A': sa, 'B': sb}, cfg)
    check(r.status == 'found' and r.findings[0].evidence['seconds'] >= 10 and r.findings[0].evidence['values'] == {'A': 1, 'B': 0}, f'desync: a flag two sides disagree on for 20 s ({r.status})')
    check(r.findings[0].key == bughunt.make_key('desync', 'flag', 'shared_flag'), 'desync: keyed by the flag')
    b2 = [sample(i / 10, 100 + 6 * i, flags={'shared_flag': 1 if i >= 55 else 0}) for i in range(300)]
    sb2 = make_side(tmp / 'pb2', b2, events=events_for(b2))
    check(bughunt.detect_desync({'A': sa, 'B': sb2}, cfg).status == 'ok', 'desync: half a second of difference is under the grace time')
    check(bughunt.detect_desync({'A': sa, 'B': sb}, bughunt.Config()).status == 'unknown', 'desync: no shared names: unknown')
    check(bughunt.detect_desync({'A': sa}, cfg).status == 'unknown', 'desync: one side: unknown')
    rep = bughunt.analyze(tmp / 'sess', cfg=cfg)
    check('pair' in rep['detectors'] and rep['detectors']['pair']['coop']['status'] == 'unknown', 'analyze: a pair gets the pair detectors; the co-op runner\'s says why it cannot judge a folder without session.json')


def tb_events_gameplay(states):
    return [{'ev': 'gameplay', 't': 0.0, 'frame': states[0]['frame'], 'area': 'Yard'}]


def picture_checks(tmp):
    cfg = bughunt.Config()

    def png(w, h, rgb):
        return vision.write_png(w, h, rgb)

    def side_with_shots(name, shots, states):
        root = tmp / name
        (root / 'game' / 'shots').mkdir(parents=True)
        for fr, data in shots:
            (root / 'game' / 'shots' / f'vk_{fr:06d}.png').write_bytes(data)
        put(root / 'pilot' / 'live' / 'state.jsonl', ''.join(json.dumps(s) + '\n' for s in states))
        put(root / 'game' / LOG, 'x\n')
        return bughunt.load_side(root)

    gray = png(16, 9, bytes([120, 130, 140] * 144))
    black = png(16, 9, bytes([1, 1, 1] * 144))
    states = walking(30, frame0=100)   # 6 presents a sample; frame = 100 + 6 i
    # black pictures while the state says play
    shots = [(100, gray), (190, black), (280, black), (370, gray)]
    side = side_with_shots('p0', shots, states)
    r = bughunt.detect_visual(side, cfg)
    check(any(f.sub == 'black' for f in r.findings), f'visual: two black pictures in a row while the state says play ({[f.sub for f in r.findings]})')
    states_load = [dict(s, loading=1) for s in states]
    side = side_with_shots('p1', shots, states_load)
    check(not any(f.sub == 'black' for f in bughunt.detect_visual(side, cfg).findings), 'visual: black while the state says loading is no finding')
    one = [(100, gray), (190, black), (280, gray)]
    check(not any(f.sub == 'black' for f in bughunt.detect_visual(side_with_shots('p2', one, states), cfg).findings), 'visual: one black picture is a fade, not a finding')
    # frozen
    side = side_with_shots('p3', [(100, gray), (190, gray), (280, png(16, 9, bytes([0, 90, 0] * 144)))], states)
    r = bughunt.detect_visual(side, cfg)
    check([f.sub for f in r.findings if f.sub == 'frozen'] == ['frozen'] and r.findings[0].evidence['moved_m'] > 1, 'visual: the same picture 90 presents apart while Link walked 9 m')
    still = steady(30, frame0=100)
    side = side_with_shots('p4', [(100, gray), (190, gray)], still)
    check(not any(f.sub == 'frozen' for f in bughunt.detect_visual(side, cfg).findings), 'visual: the same picture while Link stood still is fine')
    # flicker: A B A while nothing moved, consecutive pictures
    a, b = png(16, 9, bytes([100, 100, 100] * 144)), png(16, 9, bytes([180, 170, 160] * 144))
    side = side_with_shots('p5', [(100, a), (103, b), (106, a)], still)
    r = bughunt.detect_visual(side, cfg)
    check([f.sub for f in r.findings if f.sub == 'flicker'] == ['flicker'], f'visual: A B A in pictures 3 presents apart while nothing moved ({[f.sub for f in r.findings]})')
    side = side_with_shots('p6', [(100, a), (103, b), (106, b)], still)
    check(not any(f.sub == 'flicker' for f in bughunt.detect_visual(side, cfg).findings), 'visual: A B B is a change, not a flicker')
    side = side_with_shots('p7', [(100, a), (103, b), (106, a)], states)
    check(not any(f.sub == 'flicker' for f in bughunt.detect_visual(side, cfg).findings), 'visual: A B A while Link walks is motion, not a flicker')
    side = side_with_shots('p8', [(100, a), (190, b), (280, a)], still)
    check(not any(f.sub == 'flicker' for f in bughunt.detect_visual(side, cfg).findings), 'visual: pictures 90 presents apart cannot show a flicker')
    # bursts: consecutive pictures the watcher took (burst/<n>/vk_<present>.png + burst.json)
    def side_with_burst(name, pics, states, why='a still moment (probe)', gap=3):
        root = tmp / name
        (root / 'game' / 'burst' / 'b01-probe').mkdir(parents=True)
        for i, data in enumerate(pics):
            (root / 'game' / 'burst' / 'b01-probe' / f'vk_{500 + gap * i:06d}.png').write_bytes(data)
        (root / 'game' / 'burst' / 'b01-probe' / 'burst.json').write_text(json.dumps({'why': why}))
        put(root / 'pilot' / 'live' / 'state.jsonl', ''.join(json.dumps(x) + '\n' for x in states))
        put(root / 'game' / LOG, 'x\n')
        return bughunt.load_side(root)

    still_b = steady(30, frame0=400)
    side = side_with_burst('q1', [a, b, a, b, a, b, a, b], still_b)
    r = bughunt.detect_visual(side, cfg)
    fl = [f for f in r.findings if f.sub == 'flicker']
    check(len(fl) == 1 and fl[0].severity == 'error' and fl[0].evidence['triplets'] == 6 and fl[0].evidence['burst'] == 'b01-probe', f'visual: a strobe in a burst is one error finding naming the burst ({[(f.severity, f.evidence.get("triplets")) for f in fl]})')
    check(r.looked >= 8 and r.status == 'found', 'visual: the burst pictures count as looked at')
    side = side_with_burst('q2', [a, b, a, a, a, a, a, a], still_b)
    fl = [f for f in bughunt.detect_visual(side, cfg).findings if f.sub == 'flicker']
    check(len(fl) == 1 and fl[0].severity == 'warning', 'visual: one A B A in a burst is a warning')
    mid = png(16, 9, bytes([140, 135, 130] * 144))
    side = side_with_burst('q3', [a, mid, b, b, b, b, b, b], still_b)
    check(not any(f.sub == 'flicker' for f in bughunt.detect_visual(side, cfg).findings), 'visual: a fade a, mid, b, b ... is a change, not an A B A')
    side = side_with_burst('q4', [a, b, a, b, a, b], walking(30, frame0=400))
    check(not any(f.sub == 'flicker' for f in bughunt.detect_visual(side, cfg).findings), 'visual: alternating pictures while Link walks are motion')
    side = side_with_burst('q5', [a, b, a, b, a, b], [dict(x, loading=1) for x in still_b])
    check(not any(f.sub == 'flicker' for f in bughunt.detect_visual(side, cfg).findings), 'visual: alternating pictures during a load are not a flicker')
    side = side_with_burst('q6', [a, b, a, b, a, b], still_b, gap=30)
    check(not any(f.sub == 'flicker' for f in bughunt.detect_visual(side, cfg).findings), 'visual: pictures 30 presents apart are not consecutive')
    side = side_with_burst('q7', [a, b, a], still_b[:3])
    check([f.sub for f in bughunt.detect_visual(side, cfg).findings if f.sub == 'flicker'] == [], 'visual: no sample near the burst: nothing is said')
    side = side_with_burst('q8', [a, b, a], [])
    check(not any(f.sub == 'flicker' for f in bughunt.detect_visual(side, cfg).findings), 'visual: no states at all: nothing is said')
    # a side with bursts only (no periodic pictures) is looked at, not unknown
    check(bughunt.detect_visual(side_with_burst('q9', [a, a, a], still_b), cfg).status == 'ok', 'visual: a side that has bursts and no periodic pictures is judged')
    # the live helpers
    sd = side_with_burst('q10', [a], steady(10, frame0=400))
    check(bughunt.still_now(sd, bughunt.Config(burst_probe_still_s=2.0)) is True, 'still_now: Link and the camera still for the window')
    check(bughunt.still_now(side_with_burst('q11', [a], walking(10, frame0=400)), bughunt.Config(burst_probe_still_s=2.0)) is False, 'still_now: not while Link walks')
    check(bughunt.still_now(side_with_burst('q12', [a], steady(10, frame0=400, music='')), bughunt.Config()) is False, 'still_now: not without the area music (a scene)')
    check(bughunt.still_now(side_with_burst('q14', [a], steady(6, frame0=400)), bughunt.Config(burst_probe_still_s=2.0)) is False and bughunt.still_now(side_with_burst('q15', [a], steady(10, frame0=400)), bughunt.Config(burst_probe_still_s=2.0)) is True, 'still_now: not in the first 8 s of control (the title card and the HUD fade), yes after')
    check(bughunt.still_now(side_with_burst('q13', [a], steady(1, frame0=400)), bughunt.Config(burst_probe_still_s=2.0)) is False, 'still_now: not on a second of samples')
    # the settle window: the fade-in after a map change or a load is not judged
    def with_map_change(n=60, at=30):
        rows = steady(n, frame0=100)
        for i, r in enumerate(rows):
            if i >= at:
                r['map'] = 'Other'
        return rows
    chg = with_map_change()                      # the map changes at sample 30 (t = 3.0 s, frame 280)
    shots = [(100, gray), (190, gray), (310, black), (340, black), (460, gray)]    # frames 310 and 340: 0.5 s and 1.0 s after the change
    check(not any(f.sub == 'black' for f in bughunt.detect_visual(side_with_shots('st0', shots, chg), cfg).findings), 'visual: black pictures within 2 s of a map change are the fade-in')
    late = [(100, gray), (190, gray), (520, black), (550, black), (640, gray)]      # 4 s after the change
    check(any(f.sub == 'black' for f in bughunt.detect_visual(side_with_shots('st1', late, chg), cfg).findings), 'visual: black pictures 4 s after the change are found')
    ld = steady(60, frame0=100)
    for r in ld[30:40]:
        r['loading'] = 1                         # a load from 3.0 to 4.0 s, same map
    shots = [(100, gray), (190, gray), (430, black), (450, black), (640, gray)]     # frames 430, 450: 0.8 and 1.1 s after the load ended
    check(not any(f.sub == 'black' for f in bughunt.detect_visual(side_with_shots('st2', shots, ld), cfg).findings), 'visual: black pictures right after a load ended are the fade-in')
    sd = side_with_shots('st3', [(100, gray), (310, black)], chg)
    t_after = chg[31]['t']
    check(bughunt.recently_changed(sd, t_after, cfg) and not bughunt.recently_changed(sd, chg[55]['t'], cfg) and not bughunt.recently_changed(sd, chg[10]['t'], cfg), 'recently_changed: true within settle_s of a map change, false before and long after')
    check(not bughunt.recently_changed(sd, t_after, bughunt.Config(settle_s=0)), 'recently_changed: settle_s 0 switches it off')
    prev = (100, None, (16, 9, bytes([120, 130, 140] * 144)), 'h0')
    cur_black = (310, None, (16, 9, bytes([1, 1, 1] * 144)), 'h1')
    check(bughunt.suspect_picture(sd, prev, cur_black, cfg) is None, 'suspect_picture: a black picture 0.5 s after a map change takes no burst')
    cur_late = (520, None, (16, 9, bytes([1, 1, 1] * 144)), 'h2')
    check(bughunt.suspect_picture(sd, prev, cur_late, cfg) is not None, 'suspect_picture: the same picture 4 s later does')
    chg_sd = [r for r in chg]
    check(bughunt.still_now(side_with_burst('st4', [a], chg_sd[:34]), bughunt.Config(burst_probe_still_s=0.3)) is False, 'still_now: not while the map has just changed')
    # the model
    asked = []

    def ask(path):
        asked.append(Path(path).name)
        return {'blank': 0.1, 'missing_textures': 0.9 if 'vk_000190' in str(path) else 0.1, 'stretched_textures': None, 'body_wrong': 0.8, 'void': 0.0, 'corrupt': 0.2}
    side = side_with_shots('p9', [(100, gray), (190, gray), (280, gray)], still)
    r = bughunt.detect_visual(side, cfg, ask=ask, interesting=[190])
    subs = sorted((f.sub, f.evidence['picture']) for f in r.findings if f.sub in ('missing_textures', 'body_wrong'))
    check(subs.count(('missing_textures', 'vk_000190.png')) == 1 and len([s for s in subs if s[0] == 'body_wrong']) == 3, f'visual: the model\'s answers over the threshold are findings ({subs})')
    check(len(asked) == 3 and all(f.severity == 'warning' for f in r.findings if f.sub in ('missing_textures', 'body_wrong')), 'visual: every picture asked once; a model finding is a warning')
    cfg2 = bughunt.Config(vision_max=2)
    asked.clear()
    bughunt.detect_visual(side_with_shots('p10', [(f, gray) for f in range(100, 1000, 90)], still), cfg2, ask=ask)
    check(len(asked) == 2, 'visual: the model looks at most vision_max times')
    # pictures from before control began, black ones and a load's are not asked about
    states_g = walking(30, frame0=300)
    ev_g = tb_events_gameplay(states_g)
    sg = side_with_shots('p14', [(90, gray), (180, gray), (330, gray), (420, black), (510, gray)], states_g)
    sg._cache['events'] = ev_g
    asked.clear()
    bughunt.detect_visual(sg, cfg, ask=ask)
    check(sorted(asked) == ['vk_000330.png', 'vk_000510.png'], f'visual: the model sees only pictures from after control began, and not the black one ({sorted(asked)})')
    picks = bughunt.pick_looks(side_with_shots('p11', [(f, gray) for f in range(100, 1000, 90)], still), bughunt.Config(vision_max=5), interesting=[640])
    check(any(abs(p[0] - 640) <= 45 for p in picks) and picks[0][0] == 100 and len(picks) <= 5, 'pick_looks: the first picture and the ones nearest the other findings')

    def boom(path):
        raise RuntimeError('cap reached')
    r = bughunt.detect_visual(side_with_shots('p12', [(100, gray)], still), cfg, ask=boom)
    check(any(f.sub == 'look-failed' and f.severity == 'info' for f in r.findings), 'visual: a failed look is an info row, never a crash')
    q = bughunt.anomaly_body('m', 'data:image/png;base64,AAAA')
    check(q['questions'][0]['type'] == 'predicate' and len(q['questions']) == len(bughunt.ANOMALY_QUESTIONS) and 'AAAA' in json.dumps(q), 'anomaly_body: predicates and the picture')
    parsed = bughunt.parse_anomaly({'answers': [{'name': 'blank', 'type': 'predicate', 'probability': 0.4}, {'name': 'void', 'probability': 'x'}]})
    check(parsed['blank'] == 0.4 and parsed['void'] is None and parsed['corrupt'] is None, 'parse_anomaly: a probability, or None')
    check(bughunt.detect_visual(make_side(tmp / 'p13', steady(3)), cfg).status == 'unknown', 'visual: no pictures: unknown')


def source_checks():
    for f in ('bughunt.py',):
        text = (HERE / f).read_text()
        for bad in ('/home/', 'sk-', 'Bearer ', 'OPENAI_API_KEY='):
            check(bad not in text, f'{f}: no {bad!r}')
        for p in hs_names.PROJECTS:   # the game's own names come from hs_names, never spelled in the code
            check(p not in text.lower(), f'{f}: the project name {p!r} is not spelled here')


def cli_checks(tmp):
    cmd = [sys.executable, '-I', '-B', str(HERE / 'bughunt.py'), 'analyze', str(tmp / 'z0')]
    r = subprocess.run(cmd, capture_output=True, text=True)
    check(r.returncode == 1 and 'stall' in r.stdout, f'cli: analyze prints the table and exits 1 on an error finding ({r.returncode})')
    r = subprocess.run(cmd + ['--json'], capture_output=True, text=True)
    d = json.loads(r.stdout)
    check(any(f['kind'] == 'stall' and f['key'].startswith('stall:') for f in d['findings']) and 'solo' in d['detectors'], 'cli: --json carries findings and the detector table')
    out = tmp / 'k.json'
    r = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'bughunt.py'), 'baseline', str(tmp / 'ref.txt'), '--out', str(out)], capture_output=True, text=True)
    check(r.returncode == 0 and len(json.loads(out.read_text())['shapes']) == 2, 'cli: baseline writes the shapes')


def run_in(tmp):
    solo_checks(tmp)
    offset_checks(tmp)
    layout_checks(tmp)
    picture_checks(tmp)
    cli_checks(tmp)
    source_checks()


def run():
    with tempfile.TemporaryDirectory(prefix='test-bughunt-') as t:
        run_in(Path(t))


def main():
    run()
    if FAILS:
        raise SystemExit(f'test_bughunt: {len(FAILS)} of {CHECKS[0]} checks FAILED')
    print(f'test_bughunt: all {CHECKS[0]} checks passed')


if __name__ == '__main__':
    main()
