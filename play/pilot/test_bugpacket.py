#!/usr/bin/env python3
"""bugpacket.py against made-up sessions: the table of known findings (new, duplicate, status, two writers), the packet a finding
becomes, its triage paragraph, the replay's steps with the original's waits put back, and the verdict of a replay. Made-up names only;
no game, no network.   python3 -I -B test_bugpacket.py
"""
import gzip
import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bughunt  # noqa: E402
import bugpacket  # noqa: E402
import hs_names  # noqa: E402  (bughunt put the harness folder on sys.path: the game's own file names)
import test_bughunt as tb  # noqa: E402
import vision  # noqa: E402

FAILS = []
CHECKS = [0]


def check(cond, what):
    CHECKS[0] += 1
    if not cond:
        FAILS.append(what)
        print('FAIL', what, flush=True)


def finding(**kw):
    d = dict(kind='softlock', sub='still', severity='error', side='solo', text='8 input steps in 190 s and nothing changed', t=tb.T0 + 20.0,
             frame=100 + 6 * 200, game_s=20.0, map='Yard', pos=[3, 10, 4], evidence={'held_s': 190.0, 'inputs': 8})
    d.update(kw)
    f = bughunt.Finding(**d)
    f.key = f.key or bughunt.place_key('softlock', 'still', f.map, f.pos, 8.0)
    return f


def make_session(tmp, name='s1', with_save=True, shots=(90, 400, 700, 1000, 1300, 1600, 1900)):
    states = tb.steady(60)
    steps = [tb.step(2.0, 'walk 3 4 radius 1', 'reached', secs=1.5, **{'in': 2}), tb.step(12.0, 'chest', 'timeout', secs=4.0, **{'in': 3}),
             tb.step(14.0, 'advance timeout 25', 'closed', secs=2.0, **{'in': 4})]
    steps[0]['in'], steps[1]['in'], steps[2]['in'] = 2, 3, 4
    side = tb.make_side(tmp / name, states, events=tb.events_for(states, steps),
                        log='\n'.join(['[hos] start'] + [f'[hos host] vk: {n} presents, 60.0 fps' for n in range(120, 2400, 120)] + ['[hos] end']) + '\n',
                        summary=tb.OK_SUMMARY, exit_code=143, steps_text='watch a b\nwalk 3 4 radius 1\nchest\nadvance timeout 25\n')
    (tmp / name / 'game' / 'shots').mkdir(parents=True)
    for fr in shots:
        (tmp / name / 'game' / 'shots' / f'vk_{fr:06d}.png').write_bytes(vision.write_png(4, 4, bytes([fr % 250, 20, 30] * 16)))
    save = tmp / f'{name}-save'
    if with_save:
        (save / 'save' / 'slot_00').mkdir(parents=True)
        (save / 'save' / 'slot_00' / 'progress.sav').write_bytes(b'abc' * 100)
    copy = tmp / f'{name}-copy'
    copy.mkdir()
    (copy / 'built-from.txt').write_text('63ddacdc9a82a4ffb8675d3f8d38c21ae811704f\nmore\n')
    (copy / hs_names.Names(hs_names.PROJECTS[0]).executable).write_bytes(b'binary')
    seg = tmp / f'{name}.toml'
    seg.write_text('name = "x"\n')
    session = {'run': name, 'name': name, 'kind': 'solo', 'copy': str(copy), 'save': str(save), 'save_name': 'a-library-save', 'segment': str(seg), 'seed': 4242,
               'humanize': 2, 'decider': 'rules', 'wall': 200, 'shots': 90, 'env': ['HSAP_ANALOG=1'], 'boot': 'continue'}
    return side, session


def registry_checks(tmp):
    reg = bugpacket.Registry(tmp / 'k' / 'known.json')
    f = finding()
    st, e = reg.register(f, 'run-1', packet=tmp / 'p1')
    check(st == 'new' and e['count'] == 1 and e['status'] == 'open' and e['runs'] == ['run-1'] and e['packet'].endswith('p1'), 'registry: the first sight is new, open, with its packet')
    st, e = reg.register(f, 'run-2')
    check(st == 'duplicate' and e['count'] == 2 and e['runs'] == ['run-1', 'run-2'] and e['packet'].endswith('p1'), 'registry: the second sight is a duplicate: count and run, the first packet kept')
    reg.register(f, 'run-2')
    check(reg.lookup(f.key)['runs'] == ['run-1', 'run-2'] and reg.lookup(f.key)['count'] == 3, 'registry: a run is listed once')
    check(reg.set_status(f.key, 'known-issue', 'seen before PR 68')['status'] == 'known-issue' and reg.lookup(f.key)['note'] == 'seen before PR 68', 'registry: set_status keeps the note')
    try:
        reg.set_status(f.key, 'bogus')
        check(False, 'registry: a bad status is refused')
    except ValueError:
        check(True, 'registry: a bad status is refused')
    try:
        reg.set_status('nope', 'real')
        check(False, 'registry: an unknown key is refused')
    except KeyError:
        check(True, 'registry: an unknown key is refused')
    art = finding(key='x:y:1', status='artefact')
    check(reg.register(art, 'r')[1]['status'] == 'artefact', 'registry: an artefact-pattern finding starts as artefact')
    # two writers at once
    reg2 = bugpacket.Registry(tmp / 'k2' / 'known.json')
    ths = [threading.Thread(target=lambda i=i: reg2.register(finding(key=f'k:{i % 5}:0'), f'r{i}')) for i in range(20)]
    [t.start() for t in ths]
    [t.join() for t in ths]
    e = reg2.entries()
    check(len(e) == 5 and sum(v['count'] for v in e.values()) == 20, f'registry: twenty concurrent writers lose nothing ({len(e)} keys, {sum(v["count"] for v in e.values())} counts)')
    cls, why = bugpacket.classify(f, reg)
    check(cls == 'known-issue' and 'seen before' in why, 'classify: the table\'s status')
    check(bugpacket.classify(finding(key='fresh:key:0'), reg)[0] == 'open', 'classify: an unseen key is open')
    check(bugpacket.classify(art, reg)[0] == 'artefact', 'classify: an artefact pattern')


def packet_checks(tmp):
    side, session = make_session(tmp)
    f = finding()
    reg = bugpacket.Registry(tmp / 'kk.json')
    out = bugpacket.make_packet(tmp / 'packets' / '001', f, {'solo': side}, session, reg)
    names = sorted(p.name for p in out.iterdir())
    for want in ('packet.json', 'steps.txt', 'steps.jsonl', 'trace.jsonl', 'frames', 'logs', 'triage.md', 'replay.json', 'replay.sh', 'evidence.json', 'save', 'segment.toml'):
        check(want in names, f'packet: has {want} ({names})')
    pk = json.loads((out / 'packet.json').read_text())
    check(pk['key'] == f.key and pk['seed'] == 4242 and pk['run'] == 's1' and pk['class'] == 'open', 'packet: key, seed, run, class')
    check(pk['build']['built_from'].startswith('63ddacdc9') and len(pk['build']['binary_sha256']) == 64, 'packet: the build commit and binary hash')
    check(pk['build']['binary'] == hs_names.Names(hs_names.PROJECTS[0]).executable, 'packet: the binary is the executable hs_names names')
    check(pk['save']['name'] == 'a-library-save' and len(pk['save']['sha256']) == 64 and pk['save']['copied'], 'packet: the save by name and hash, copied')
    check((out / 'steps.txt').read_text() == 'watch a b\nwalk 3 4 radius 1\nchest\nadvance timeout 25\n', 'packet: the full input log as the game side got it')
    check(len((out / 'steps.jsonl').read_text().splitlines()) == 3, 'packet: the steps with their results')
    tr = [json.loads(x) for x in (out / 'trace.jsonl').read_text().splitlines()]
    check(tr and min(r['t'] for r in tr) >= f.t - 30.0 - 1e-6 and max(r['t'] for r in tr) <= f.t + 15.0 + 1e-6, f'packet: the trace is the window around the finding ({len(tr)} rows)')
    frames = sorted(p.name for p in (out / 'frames').iterdir())
    check(len(frames) == 4 and frames[0].startswith('after-1') and any(n.startswith('before-2') for n in frames), f'packet: two pictures before and two after ({frames})')
    check(any('vk_001300' in n for n in frames if n.startswith('before')), 'packet: the pictures nearest the finding (present 1300)')
    log = gzip.open(out / 'logs' / 'solo.log.gz', 'rt').read()
    check('[hos] start' in log and (out / 'logs' / 'solo-window.txt').exists(), 'packet: the whole log gzipped and a window of it')
    triage = (out / 'triage.md').read_text()
    check(triage.count('\n') == 1 and 'softlock/still' in triage and 'Yard' in triage and f.key in triage and 'chest' in triage and 'Seed 4242' in triage,
          f'triage: one paragraph with the what, where, inputs, seed and key')
    rp = json.loads((out / 'replay.json').read_text())
    check(rp['mode'] == 'steps' and rp['boot'] == 'continue' and rp['wall'] == 200 and rp['save'] == 'save' and rp['env'] == ['HSAP_ANALOG=1'], 'replay.json: steps mode, the same save, boot, wall and environment')
    r = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'bugpacket.py'), 'show', str(out)], capture_output=True, text=True)
    check(r.returncode == 0 and 'softlock/still' in r.stdout and '"mode": "steps"' in r.stdout, 'cli: show prints the note and the replay')
    sh = (out / 'replay.sh').read_text()
    check(sh.startswith('#!/bin/bash') and 'hunt.py' in sh and 'replay' in sh and str(out) in sh, 'replay.sh calls the hunt\'s replay on the packet')
    # a big save is referenced, not copied
    old = bugpacket.SAVE_COPY_MAX
    bugpacket.SAVE_COPY_MAX = 10
    try:
        out2 = bugpacket.make_packet(tmp / 'packets' / '002', f, {'solo': side}, session, reg)
    finally:
        bugpacket.SAVE_COPY_MAX = old
    pk2 = json.loads((out2 / 'packet.json').read_text())
    check(not (out2 / 'save').exists() and pk2['save']['copied'] is False and pk2['replay']['save'] is None, 'packet: a save over the limit is named by hash, not copied')
    # a pair
    a, sa = make_session(tmp, 'pa')
    b, sb = make_session(tmp, 'pb')
    pair_session = {'run': 'pair-1', 'kind': 'pair', 'case': str(tmp / 'case.toml'), 'seed': 7, 'copy': sa['copy']}
    (tmp / 'case.toml').write_text('name = "c"\n')
    fp = finding(kind='give', sub='double', side='pair', text='keys +2', key='give:double:abc')
    out3 = bugpacket.make_packet(tmp / 'packets' / '003', fp, {'A': a, 'B': b}, pair_session, reg)
    n3 = sorted(p.name for p in out3.iterdir())
    check('steps.A.txt' in n3 and 'steps.B.txt' in n3 and 'case.toml' in n3 and (out3 / 'logs' / 'A.log.gz').exists() and (out3 / 'logs' / 'B.log.gz').exists(),
          f'packet: a pair has both sides\' inputs, both logs and the case ({n3})')
    rp3 = json.loads((out3 / 'replay.json').read_text())
    check(rp3['mode'] == 'case' and rp3['case'] == 'case.toml', 'replay.json: a pair replays through its case')
    return out


def replay_checks(tmp, packet):
    # steps with the original's waits put back: step 2 ended at t 2.0 after 1.5 s, step 3 ended at 12.0 after 4.0 s (it began at 8.0: 6 s of think time)
    side = bughunt.Side(packet)
    side._cache['events'] = [json.loads(x) for x in (packet / 'steps.jsonl').read_text().splitlines()]
    lines = bugpacket.steps_with_gaps(side, (packet / 'steps.txt').read_text().splitlines())
    check(lines == ['watch a b', 'walk 3 4 radius 1', 'wait 6.0', 'chest', 'advance timeout 25'], f'replay: the 6 s of thinking before the chest is a wait ({lines})')
    live = tmp / 'live'
    pk = bugpacket.prepare_replay(packet, live)
    got = (live / 'steps.txt').read_text().splitlines()
    check(got[-1] == 'end' and got.count('end') == 1 and 'wait 6.0' in got and got[0] == 'watch a b', f'prepare_replay: the steps with waits and one end ({got})')
    check(pk['key'] and pk['replay']['mode'] == 'steps', 'prepare_replay: returns the packet')
    live2 = tmp / 'live2'
    bugpacket.prepare_replay(packet, live2, with_gaps=False)
    check('wait 6.0' not in (live2 / 'steps.txt').read_text(), 'prepare_replay: without gaps, as sent')
    (packet / 'steps.txt').write_text('walk 1 1\nend\n')
    bugpacket.prepare_replay(packet, tmp / 'live3', with_gaps=False)
    check((tmp / 'live3' / 'steps.txt').read_text().splitlines() == ['walk 1 1', 'end'], 'prepare_replay: an end already there is not doubled')
    pair_dir = tmp / 'packets' / '003'
    try:
        bugpacket.prepare_replay(pair_dir, tmp / 'live4')
        check(False, 'prepare_replay: a pair packet is refused')
    except ValueError:
        check(True, 'prepare_replay: a pair packet is refused')
    # verdicts
    f1 = finding()
    key = f1.key
    check(bugpacket.replay_verdict(key, [f1])[0] == 'reproduced', 'verdict: the same key is reproduced')
    near = finding(pos=[300, 10, 300])
    near.key = bughunt.place_key('softlock', 'still', 'Yard', near.pos, 8.0)
    check(bugpacket.replay_verdict(key, [near])[0] == 'similar', 'verdict: the same kind elsewhere is similar')
    other = finding(kind='stall', sub='stall', key='stall:stall:1')
    v = bugpacket.replay_verdict(key, [other, finding(severity='info', key=key)])
    check(v[0] == 'not reproduced' and '1 other' in v[1], f'verdict: another kind, or only an info row, is not reproduced ({v})')
    check(bugpacket.replay_verdict(key, [])[0] == 'not reproduced', 'verdict: nothing is not reproduced')


def rendezvous_checks(tmp):
    text = 'env = ["HSAP_ANALOG=1", "HSAP_RENDEZVOUS=/old/rv", "HSAP_SIDE=A"]\nenv = ["HSAP_RENDEZVOUS=/old/rv", "HSAP_SIDE=B"]\n'
    (tmp / 'rv-new').mkdir()
    (tmp / 'rv-new' / 'stale.A').write_text('1')
    got = bugpacket.fresh_rendezvous(text, tmp / 'rv-new')
    check(got.count(f'HSAP_RENDEZVOUS={tmp / "rv-new"}') == 2 and '/old/rv' not in got and 'HSAP_SIDE=B' in got, 'fresh_rendezvous: every rendezvous folder of the case is the new one')
    check(list((tmp / 'rv-new').iterdir()) == [], 'fresh_rendezvous: the folder is made empty (a stale name would release a side at once)')


def identity_checks(tmp):
    for p in hs_names.PROJECTS:   # the binary of a copy is found under the name of whichever project it was built as
        copy = tmp / f'id-{p}'
        copy.mkdir()
        (copy / hs_names.Names(p).executable).write_bytes(b'x')
        got = bugpacket.build_identity(copy)
        check(got['binary'] == hs_names.Names(p).executable and len(got['binary_sha256']) == 64, f'build_identity: the executable of a copy built as {p!r}')
    empty = tmp / 'id-none'
    empty.mkdir()
    check('binary' not in bugpacket.build_identity(empty), 'build_identity: a copy with no executable has no binary')


def log_checks():
    lines = ['a', 'vk: 100 presents x', 'b', 'vk: present 190 written to x', 'c', 'vk: 300 presents y'] + ['z'] * 5
    w = bugpacket.log_window(lines, 150, width=1)
    check(w == ['b', 'vk: present 190 written to x', 'c'], f'log_window: around the first marker at or after the present ({w})')
    check(bugpacket.log_window(lines, 5000, width=2) == lines[-4:], 'log_window: no marker that late: the tail')
    check(bugpacket.log_window([], 1) == [], 'log_window: nothing')
    text = (HERE / 'bugpacket.py').read_text()
    for bad in ('/home/', 'sk-', 'Bearer '):
        check(bad not in text, f'bugpacket.py: no {bad!r}')
    for p in hs_names.PROJECTS:   # the game's own names come from hs_names, never spelled in the code
        check(p not in text.lower(), f'bugpacket.py: the project name {p!r} is not spelled here')


def run_in(tmp):
    registry_checks(tmp)
    packet = packet_checks(tmp)
    replay_checks(tmp, packet)
    rendezvous_checks(tmp)
    identity_checks(tmp)
    log_checks()


def run():
    with tempfile.TemporaryDirectory(prefix='test-bugpacket-') as t:
        run_in(Path(t))


def main():
    run()
    if FAILS:
        raise SystemExit(f'test_bugpacket: {len(FAILS)} of {CHECKS[0]} checks FAILED')
    print(f'test_bugpacket: all {CHECKS[0]} checks passed')


if __name__ == '__main__':
    main()
