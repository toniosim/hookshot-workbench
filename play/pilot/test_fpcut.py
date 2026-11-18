#!/usr/bin/env python3
"""The false-positive cuts of bughunt.py, on made-up evidence whose every number is known: a stall against the machine's pressure (PSI rows the
hunt records), a stall's grouping, the pair's own rules (the other game's end, the identity line before the room is accepted, a send peak that
touches the limit, the body snap after a stall, both games stalling at once), the wall clock of a co-op side and of a log line, and the hunt's
Pressure recorder against a fake /proc. Made-up names; no game, no GPU, no network.   python3 -I -B test_fpcut.py
"""
import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bughunt  # noqa: E402
import hunt  # noqa: E402
import test_bughunt as tb  # noqa: E402

FAILS = []
CHECKS = [0]
T0 = tb.T0


def check(cond, what):
    CHECKS[0] += 1
    if not cond:
        FAILS.append(what)
        print('FAIL', what, flush=True)


def psi_rows(seconds, cpu_per_s=0.02, iof_per_s=0.0, memf_per_s=0.0, start=0):
    """cumulative counters once a second: the share of each second the kernel counted as waiting"""
    out = []
    for i in range(start, start + seconds + 1):
        out.append({'t': T0 + i, 'cpu': int(i * cpu_per_s * 1e6), 'io': 0, 'iof': int(i * iof_per_s * 1e6), 'mem': 0, 'memf': int(i * memf_per_s * 1e6), 'load1': 3.0})
    return out


def pressure_checks(tmp):
    cfg = bughunt.Config()
    st = tb.steady(60)
    gaps = {3000: 4500.0}    # a 4.5 s gap at about 50 s
    for name, rows, expect in (('quiet', psi_rows(60, 0.02), 'stall'), ('cpu', psi_rows(60, 0.60), 'explained'), ('disk', psi_rows(60, 0.02, iof_per_s=0.4), 'explained'),
                               ('memory', psi_rows(60, 0.02, memf_per_s=0.3), 'explained'), ('none', None, 'stall')):
        root = tmp / f'pr-{name}'
        side = tb.make_side(root, st, events=tb.events_for(st), present=tb.present_rows(3600, gaps=gaps))
        if rows is not None:
            tb.put(root / 'psi.jsonl', ''.join(json.dumps(r) + '\n' for r in rows))
        r = bughunt.detect_stall(side, cfg)
        f = [x for x in r.findings][0]
        check(f.sub == expect, f'pressure {name}: the 4.5 s gap is {expect} ({f.sub}: {f.text})')
        if expect == 'explained':
            check(f.severity == 'info' and 'machine was short of' in f.text and f.evidence['pressure'], f'pressure {name}: info, with the reading in the evidence ({f.text})')
        elif rows is not None:
            check(f.evidence['pressure'] and f.evidence['pressure']['cpu'] < 0.1, f'pressure {name}: the quiet reading is kept as evidence ({f.evidence["pressure"]})')
        else:
            check(f.evidence['pressure'] is None, f'pressure {name}: nothing recorded: no reading, the stall stands')
    # a recorder that was not running at the stall (rows end before it): nothing is said
    root = tmp / 'pr-late'
    side = tb.make_side(root, st, events=tb.events_for(st), present=tb.present_rows(3600, gaps=gaps))
    tb.put(root / 'psi.jsonl', ''.join(json.dumps(r) + '\n' for r in psi_rows(20, 0.9)))
    f = bughunt.detect_stall(side, cfg).findings[0]
    check(f.sub == 'stall' and f.evidence['pressure'] is None, 'pressure: rows that end before the stall explain nothing')
    # a hitch just before a long stall (1 s apart) is one stall, not two findings
    gaps2 = {2990: 900.0, 3000: 4500.0}
    side = tb.make_side(tmp / 'grp', st, events=tb.events_for(st), present=tb.present_rows(3600, gaps=gaps2))
    r = bughunt.detect_stall(side, cfg)
    check(len(r.findings) == 1 and r.findings[0].evidence['n'] == 2 and r.findings[0].evidence['max_ms'] == 4500, f'stall: a hitch right before a long stall is one group ({[f.evidence["n"] for f in r.findings]})')
    # machine_pressure on its own
    pr = bughunt.machine_pressure(psi_rows(60, 0.5), T0 + 20, T0 + 22, 1.0)
    check(pr and abs(pr['cpu'] - 0.5) < 0.01 and pr['seconds'] <= 8, f'machine_pressure: half the time ({pr})')
    check(bughunt.machine_pressure([], 0, 1) is None and bughunt.machine_pressure(psi_rows(5), T0 + 100, T0 + 101) is None, 'machine_pressure: no rows or rows elsewhere: None')
    check(bughunt.machine_short({'cpu': 0.1, 'iof': 0.0, 'memf': 0.0}, cfg) is None and 'CPU' in bughunt.machine_short({'cpu': 0.5}, cfg), 'machine_short: under the thresholds nothing, over them what')


def pair_side(root, name, seconds=60, end_off=0.0, log_lines=0, log_times=None):
    """a co-op side: nested rows with `w`, a log and (optionally) log-times.jsonl, present.csv, side.json"""
    d = Path(root) / name
    rows = []
    for s in tb.steady(seconds - end_off):
        rows.append({'w': 5000.0 + s['t'] - T0, 'frame': s['frame'], 'game': {k: v for k, v in s.items() if k != 'child'} | {'age': 'child'}})
    tb.put(d / 'state.jsonl', ''.join(json.dumps(r) + '\n' for r in rows))
    lines = [f'[hos] line {i}' for i in range(log_lines)] if log_lines else ['[hos] fine']
    tb.put(d / 'log.txt', '\n'.join(lines) + '\n')
    if log_times:
        tb.put(d / 'log-times.jsonl', ''.join(json.dumps(r) + '\n' for r in log_times))
    tb.put(d / 'present.csv', tb.present_rows(3600))
    tb.put(d / 'side.json', json.dumps({'id': name}))
    return d


def F(kind, sub, side, text, sev='warning', t=None, **ev):
    return bughunt.Finding(kind, sub, sev, side, text, t=t, evidence=ev, key=bughunt.make_key(kind, sub, text))


def pair_checks(tmp):
    cfg = bughunt.Config()
    root = tmp / 'pair'
    log_lines = 100
    offs, o = [], 0
    for i in range(log_lines):
        offs.append({'w': 5000.0 + i * 0.6, 'off': o})
        o += len(f'[hos] line {i}') + 1
    pair_side(root, 'A', log_lines=log_lines, log_times=offs)
    pair_side(root, 'B', log_lines=log_lines, log_times=offs)
    tb.put(root / 'session.json', json.dumps({'start_w': 4990.0, 'anchors': {'accepted': 40.0}}))
    sides = bughunt.find_sides(root)
    a = sides['A']
    check(abs(a.end_w() - (5000.0 + a.states[-1]['t'] - T0)) < 1e-6, 'end_w: the last row\'s wall time')
    check(abs(a.wall_of(T0 + 10.0) - 5010.0) < 0.2, f'wall_of: sample-clock time to unix time ({a.wall_of(T0 + 10.0)})')
    check(a.wall_of(T0 + 1000.0) is not None and bughunt.load_side(root / 'A').wall_of(T0) is not None, 'wall_of: extends past the rows by the clock')
    w95 = a.line_wall(95)
    check(w95 is not None and abs(w95 - (5000.0 + 95 * 0.6)) < 0.7 and a.line_wall(5) < 5004, f'line_wall: log line 95 is near 5057 ({w95})')
    check(a.line_wall(None) is None and bughunt.load_side(tmp / 'nowhere').line_wall(3) is None, 'line_wall: no index or no log-times: None')
    # (1) the other player going away at the shutdown
    end_w = 5059.9
    f1 = F('log', 'coop-logs', 'B', '[bodies] puppet: member 1 is hidden (not heard) (x1; first line 9952, t=59.0s)', t=59.0, w=end_w - 1.0)
    f2 = F('log', 'coop-logs', 'B', '[bodies] puppet: member 1 is hidden (not heard) (x1; first line 10, t=20.0s)', t=20.0, w=5020.0)
    f3 = F('log', 'new-line', 'B', 'a log line new to the baseline (1x): coop: players: nobody is shown now: made 1', line='[hos] coop: players: nobody is shown now: made 1', line_index=95)
    f4 = F('log', 'new-line', 'B', 'a log line new to the baseline (1x): coop: players: nobody is shown now: made 1', line='[hos] coop: players: nobody is shown now: made 1', line_index=10)
    # (2) the identity line before and after the room was accepted
    f5 = F('log', 'coop-logs', 'A', '[identity] sync: 1 member(s) in the room are not identified (never said who they are)', t=30.0, w=5030.0)
    f6 = F('log', 'coop-logs', 'A', '[identity] sync: 1 member(s) in the room are not identified (never said who they are) x', t=50.0, w=5050.0)
    # (3) the send peak
    f7 = F('net', 'coop-net', 'A', "sent peak 33601 bytes/s is over the game's RATE_BYTES limit 32768")
    f8 = F('net', 'coop-net', 'A', "sent peak 60000 bytes/s is over the game's RATE_BYTES limit 32768")
    # (4) a body snap after a stall of A, and one with no stall before it
    stall_a = F('stall', 'stall', 'A', '1 slow present(s), the worst 5000 ms', sev='error', t=T0 + 14.0, t_end=T0 + 19.0, max_ms=5000)
    j1 = F('body', 'coop-jank', 'B', '[snap] real A drawn on B: error fell 1.7 m', w=5030.0)
    j2 = F('body', 'coop-jank', 'B', '[snap] real A drawn on B: error fell 1.7 m (again)', w=5058.0)
    src = [f1, f2, f3, f4, f5, f6, f7, f8, stall_a, j1, j2]
    out = bughunt.explain_pair(src, sides, cfg, root)
    by = {f.text[:60]: f for f in out}
    check(f1.severity == 'info' and 'ending' in f1.evidence['explained'], f'pair: the member hidden at the first game\'s end is the shutdown ({f1.evidence.get("explained")})')
    f2b = F('log', 'coop-logs', 'B', '[bodies] puppet: member 1 is hidden (not heard) (x1; first line 10, t=20.0s)', t=20.0, w=5020.0)
    bughunt.explain_pair([f2b], sides, cfg, root)
    check(f2b.severity == 'warning', 'pair: the same line mid-session with no stall near stays a finding')
    check(f3.severity == 'info' and f4.severity == 'warning', f'pair: a new log line is placed by its line number against the game\'s end ({f3.severity}, {f4.severity})')
    check(f5.severity == 'info' and 'not accepted' in f5.evidence['explained'] and f6.severity == 'warning', 'pair: the identity line before the room was accepted is explained, after it is not')
    check(f7.severity == 'info' and '1.03x' in f7.evidence['explained'] and f8.severity == 'warning', 'pair: a send peak 3 percent over the limit is touching it; 1.8x is a finding')
    check(j1.severity == 'info' and 'follows a stall' in j1.evidence['explained'] and j2.severity == 'warning', f'pair: a body snap 11 s after a stall is the known one, one 39 s after is not ({j1.severity}, {j2.severity})')
    check(stall_a.severity == 'error' and len(out) == len(src), 'pair: a lone stall of one game stays one finding; nothing is dropped')
    f9 = F('log', 'coop-logs', 'B', '[bodies] puppet: member 1 is hidden (not heard) (x1; first line 1, t=22.0s)', t=22.0, w=5022.0)
    out = bughunt.explain_pair([stall_a, f9], sides, cfg, root)
    check(f9.severity == 'info' and 'stalled just before' in f9.evidence['explained'], 'pair: not heard 3 s after a stall: the other game was stalled')
    # both games stalling at the same moment: one finding, the biggest pair first
    sa = F('stall', 'stall', 'A', '1 slow present(s), the worst 5691 ms', sev='error', t=T0 + 10.0, t_end=T0 + 15.7, max_ms=5691)
    sb = F('stall', 'stall', 'B', '1 slow present(s), the worst 6603 ms', sev='error', t=T0 + 9.5, t_end=T0 + 16.1, max_ms=6603)
    sa2 = F('stall', 'hitch', 'A', '1 slow present(s), the worst 700 ms', t=T0 + 40.0, t_end=T0 + 40.7, max_ms=700)
    sb2 = F('stall', 'hitch', 'B', '1 slow present(s), the worst 800 ms', t=T0 + 30.0, t_end=T0 + 30.8, max_ms=800)
    out = bughunt.explain_pair([sa, sb, sa2, sb2], sides, cfg, root)
    both = [f for f in out if f.sub == 'both']
    check(len(both) == 1 and both[0].side == 'pair' and both[0].severity == 'error' and 'A 5691 ms, B 6603 ms' in both[0].text, f'pair: the two overlapping stalls are one stall/both ({[f.text[:50] for f in both]})')
    check(len(out) == 3 and sum(1 for f in out if f.sub == 'hitch') == 2, 'pair: stalls that do not overlap stay as they are')
    check(both[0].key.startswith('stall:both:') and set(both[0].evidence['sides']) == {'A', 'B'}, 'pair: the merged finding has its own key and both sides\' evidence')
    sa3 = F('stall', 'stall', 'A', '1 slow present(s), the worst 5000 ms', sev='error', t=T0 + 10.0, t_end=T0 + 15.0, max_ms=5000)
    sa4 = F('stall', 'hitch', 'A', '1 slow present(s), the worst 900 ms', t=T0 + 12.0, t_end=T0 + 12.9, max_ms=900)
    out = bughunt.explain_pair([sa3, sa4], sides, cfg, root)
    check(len(out) == 2 and not any(f.sub == 'both' for f in out), 'pair: two stalls of one game are not both games')
    check(bughunt.explain_pair([sa3], {'A': a}, cfg, root) == [sa3], 'pair: a single side is left alone')
    # the runner's shutdown: after it asked the pilots to end nobody is playing: stalls and co-op lines then are the closing, not a bug
    tb.put(root / 'timeline.jsonl', json.dumps({'w': 5050.0, 't': 60.0, 'kind': 'phase', 'name': 'shutdown'}) + '\n')
    g1 = F('stall', 'stall', 'B', '3 slow present(s), the worst 7987 ms', sev='error', t=T0 + 55.0, t_end=T0 + 63.0, max_ms=7987)
    g2 = F('log', 'coop-logs', 'A', '[bodies] puppet: member 2 is hidden (this game\'s body liveness grace expired) (x1)', t=56.0, w=5056.0)
    g3 = F('body', 'coop-bodies', 'A', 'member 2 made again after "this game\'s body liveness grace expired" with no map change in between', w=5058.0)
    g4 = F('log', 'coop-logs', 'A', '[bodies] puppet: member 2 is hidden (this game\'s body liveness grace expired) (x1)', t=40.0, w=5040.0)
    g5 = F('crash', 'exit', 'A', 'the game ended with SIGSEGV', sev='error', w=5056.0)
    g6 = F('stall', 'stall', 'A', '1 slow present(s), the worst 5200 ms', sev='error', t=T0 + 20.0, t_end=T0 + 25.2, max_ms=5200)
    bughunt.explain_pair([g1, g2, g3, g4, g5, g6], sides, cfg, root)
    check(g1.severity == 'info' and 'asked the pilots to end' in g1.evidence['explained'], f'pair shutdown: a stall that begins after the runner asked the pilots to end ({g1.severity})')
    check(g2.severity == 'info' and g3.severity == 'info', 'pair shutdown: the co-op lines after it are explained')
    check(g4.severity == 'warning' and g5.severity == 'error' and g6.severity == 'error', 'pair shutdown: the same line before it, a crash after it, and a stall mid-play stay findings')
    check(bughunt.shutdown_wall(root) == 5050.0 and bughunt.shutdown_wall(tmp / 'nowhere') is None, 'shutdown_wall: the runner\'s phase, else None')
    # core dumps listed machine-wide: only those of this session's games are the session's
    txt = ('TIME                            PID  UID  GID SIG     COREFILE EXE                                      SIZE\n'
           'Mon 2026-11-16 19:01:30 CST 3521773 1000 1000 SIGABRT present  /tmp/chat-hz8birq4/core        23.7K\n'
           'Mon 2026-11-16 19:03:14 CST 3570818 1000 1000 SIGABRT present  /tmp/coop-gameplay-0hqnqvbm/fixture.exe 22.8K\n')
    copies = ['/x/copy-bughunt-a', '/x/copy-bughunt-b']
    ours, others = bughunt.split_core_dumps(txt, copies)
    check(ours == [] and len(others) == 2, f'core dumps: the header is no dump, other processes are not ours ({len(ours)}, {len(others)})')
    txt2 = txt + f'Mon 2026-11-16 19:03:50 CST 3570999 1000 1000 SIGSEGV present  /x/copy-bughunt-b/{bughunt.EXE_NAMES[0]} 1.2G\n'
    ours, others = bughunt.split_core_dumps(txt2, copies)
    check(len(ours) == 1 and 'SIGSEGV' in ours[0] and len(others) == 2, 'core dumps: a dump of a game of the case is ours')
    check(bughunt.split_core_dumps('No coredumps found.\n', []) == ([], []), 'core dumps: none found')
    # a co-op side finds its pressure file in the session folder above it
    tb.put(root / 'psi.jsonl', ''.join(json.dumps(r) + '\n' for r in psi_rows(5)))
    check(len(bughunt.find_sides(root)['A'].pressure) == 6, 'pressure: a co-op side reads psi.jsonl of its session folder')


def hold4_checks(tmp):
    """what hold 4 showed: a pair whose case delays B's link makes the other player's body late on B (by design), and a game's own load (a
    placement) is a `stopped being played` line in its co-op log, not a fault"""
    cfg = bughunt.Config()
    root = tmp / 'h4'
    log_n = 40
    offs, o = [], 0
    for i in range(log_n):
        offs.append({'w': 5000.0 + i * 1.0, 'off': o})
        o += len(f'[hos] line {i}') + 1
    for name in 'AB':
        d = pair_side(root, name, log_lines=log_n, log_times=offs)
    # side A has a load from 12 to 14 s (the placement)
    rows = []
    for s in tb.steady(40):
        rows.append({'w': 5000.0 + s['t'] - T0, 'frame': s['frame'], 'game': {k: v for k, v in s.items() if k != 'child'} | {'age': 'child', 'loading': 12 <= s['t'] - T0 <= 14}})
    tb.put(root / 'A' / 'state.jsonl', ''.join(json.dumps(r) + '\n' for r in rows))
    tb.put(root / 'session.json', json.dumps({'start_w': 4990.0, 'anchors': {'accepted': 5.0}}))
    tb.put(root / 'case.json', json.dumps({'sides': {'A': {'link': {}}, 'B': {'link': {'c2s': {'delay_ms': 150}, 's2c': {'delay_ms': 150}}}}}))
    sides = bughunt.find_sides(root)
    a = sides['A']
    check(a.t_of_wall(a.wall_of(T0 + 7.0)) is not None and abs(a.t_of_wall(a.wall_of(T0 + 7.0)) - (T0 + 7.0)) < 0.01, 't_of_wall: the inverse of wall_of')
    lag = F('body', 'coop-jank', 'B', '[lag] real A drawn on B: error over 2 m for 3 consecutive samples (max 2.8 m)')
    starved = F('body', 'coop-jank', 'B', '[starved] real A drawn on B: in 6.2% of frames the time shown was past the newest pose')
    lag_a = F('body', 'coop-jank', 'A', '[lag] real B drawn on A: error over 2 m for 3 consecutive samples (max 2.8 m)')
    snap = F('body', 'coop-jank', 'B', '[snap] real A drawn on B: error fell 2.2 m', w=5030.0)
    load_in = F('log', 'new-line', 'A', 'a log line new to the baseline (1x): coop: players: this game stopped being played: a map change or a load', line='[hos] coop: players: this game stopped being played: a map change or a load', line_index=13)
    load_out = F('log', 'new-line', 'A', 'a log line new to the baseline (1x): coop: players: this game stopped being played: a map change or a load', line='[hos] coop: players: this game stopped being played: a map change or a load', line_index=33)
    bughunt.explain_pair([lag, starved, lag_a, snap, load_in, load_out], sides, cfg, root)
    check(lag.severity == 'info' and 'delays side B' in lag.evidence['explained'] and starved.severity == 'info', f'pair: [lag] and [starved] on the side whose link the case delays are by design ({lag.severity}, {starved.severity})')
    check(lag_a.severity == 'info' and 'delays side B' in lag_a.evidence['explained'], f'pair: a delayed link delays both ways: the other player\'s body is late on the unimpaired side too ({lag_a.severity})')
    check(snap.severity == 'warning', 'pair: a snap stays a finding')
    tb.put(root / 'case.json', json.dumps({'sides': {'A': {'link': {}}, 'B': {'link': {}}}}))
    lag_n = F('body', 'coop-jank', 'A', '[lag] real B drawn on A: error over 2 m for 3 consecutive samples (max 2.8 m)')
    bughunt.explain_pair([lag_n], sides, cfg, root)
    check(lag_n.severity == 'warning', 'pair: with no link delayed anywhere a [lag] stays a finding')
    check(load_in.severity == 'info' and 'itself was loading' in load_in.evidence['explained'], 'pair: `stopped being played` during the game\'s own load is explained')
    check(load_out.severity == 'warning', 'pair: the same line 20 s from any load stays a finding')
    check(bughunt.Config(link_delay_explains_ms=200).link_delay_explains_ms == 200, 'Config: link_delay_explains_ms is a threshold')


def recorder_checks(tmp):
    proc = tmp / 'proc'
    (proc / 'pressure').mkdir(parents=True)
    (proc / 'pressure' / 'cpu').write_text('some avg10=1.00 avg60=1.00 avg300=1.00 total=5000000\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=0\n')
    (proc / 'pressure' / 'io').write_text('some avg10=0.00 avg60=0.00 avg300=0.00 total=700\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=300\n')
    (proc / 'pressure' / 'memory').write_text('some avg10=0.00 avg60=0.00 avg300=0.00 total=90\nfull avg10=0.00 avg60=0.00 avg300=0.00 total=40\n')
    (proc / 'loadavg').write_text(f'{3.5:.2f} {4.0:.2f} {5.0:.2f} 2/300 1234\n')
    out = tmp / 'psi.jsonl'
    p = hunt.Pressure(out, every=0.05, proc=str(proc))
    row = p.sample()
    check(row['cpu'] == 5000000 and row['io'] == 700 and row['iof'] == 300 and row['mem'] == 90 and row['memf'] == 40 and row['load1'] == 3.5, f'Pressure.sample: the five counters and the load ({row})')
    p.start()
    time.sleep(0.4)
    p.halt.set()
    p.join(timeout=3)
    rows = [json.loads(x) for x in out.read_text().splitlines()]
    check(len(rows) >= 4 and all(rows[i]['t'] < rows[i + 1]['t'] for i in range(len(rows) - 1)) and not p.is_alive(), f'Pressure: rows on a clock that rises, the thread ends ({len(rows)})')
    check(abs(rows[0]['t'] - time.monotonic()) < 60, 'Pressure: the monotonic clock the games use')
    n = hunt.slice_psi(out, rows[1]['t'], rows[2]['t'], tmp / 'slice.jsonl')
    check(n == 2 and len((tmp / 'slice.jsonl').read_text().splitlines()) == 2, 'slice_psi: the rows of a session\'s time span')
    check(hunt.slice_psi(tmp / 'nowhere.jsonl', 0, 1, tmp / 'x.jsonl') == 0, 'slice_psi: no recorder file: nothing')
    empty = hunt.Pressure(tmp / 'e.jsonl', proc=str(tmp / 'noproc')).sample()
    check(set(empty) == {'t'}, f'Pressure.sample: a kernel without the files records the time alone ({empty})')


def run_in(tmp):
    pressure_checks(tmp)
    pair_checks(tmp)
    hold4_checks(tmp)
    recorder_checks(tmp)


def run():
    with tempfile.TemporaryDirectory(prefix='test-fpcut-') as t:
        run_in(Path(t))


def main():
    run()
    if FAILS:
        raise SystemExit(f'test_fpcut: {len(FAILS)} of {CHECKS[0]} checks FAILED')
    print(f'test_fpcut: all {CHECKS[0]} checks passed')


if __name__ == '__main__':
    main()
