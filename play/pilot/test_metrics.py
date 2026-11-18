#!/usr/bin/env python3
"""metrics.py against a made-up run folder whose every number is known: stuck steps per km and their durations, the time to
each goal, decisions per minute, streaks, interactions, cost by kind, vision's effect, a scripted (TAS) route's events and the
table. No game, no network.  python3 -I -B test_metrics.py   (test_eyes.py calls run_in too)
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import metrics  # noqa: E402


def step(src, result, **kw):
    return {'ev': 'step', 'in': 1, 'src': src, 'result': result, 'detail': '', **kw}


def make_run(root):
    """12 decisions on two goals. Known by hand:
    moves: 20 + 0.2 + 3 + 0.1 + 12 + 5 x 5 = 60.3 m; stuck steps: 2 (3.0 s and 4.0 s); one timeout; one held;
    streaks of the same choice on the same target: at most 3 (go on g2/c, n 11 to 13), none of 5 or more;
    g1 met at t = 20 (wall 150) after the first decision at t = 0 (wall 100); g2 never met;
    interactions: n 6 press-a done (door), n 7 press-a none (talk) then the goal row met -> 2 attempts, 2 succeeded."""
    rows, n = [], 0
    w = 100.0

    def dec(goal, target, choice, t, cost=0.001, **extra):
        nonlocal n, w
        n += 1
        rows.append({'kind': 'decision', 'n': n, 'state': {'t': t, 'pos': [0, 0, 0], 'life': 24 - (n // 6) * 2, **extra.pop('state', {})},
                     'goal': goal, 'target': target, 'decider': 'openai-decisions', 'choice': choice, 'cost_usd': cost,
                     'latency_ms': 200, 'wall': w, **extra})
        w += 3.0
        return n

    def res(n, result, moved, steps):
        rows.append({'kind': 'result', 'n': n, 'result': result, 'moved': moved, 'steps': steps, 'wall': w})

    n1 = dec('g1', 'a', 'go', 0.0)
    res(n1, 'reached', 20.0, [step('run 1 1 radius 1', 'reached', secs=3.0, moved=20.0, t=3.0)])
    n2 = dec('g1', 'b', 'go', 3.0)
    res(n2, 'stuck', 0.2, [step('run 2 2 radius 1', 'stuck', secs=3.0, moved=0.2, t=6.0)])
    n3 = dec('g1', 'b', 'side-left', 6.0)
    res(n3, 'reached', 3.0, [step('walk 3 3 radius 1', 'reached', secs=1.0, moved=3.0, t=7.0)])
    n4 = dec('g1', 'b', 'go', 7.0, recover={'stuck': True, 'stalled_s': 4.5, 'rung': 0, 'streak': 1})
    res(n4, 'stuck', 0.1, [step('run 4 4 radius 1', 'stuck', secs=4.0, moved=0.1, t=11.0)])
    n5 = dec('g1', 'b', 'go', 11.0)
    res(n5, 'timeout', 12.0, [step('run 5 5 radius 1', 'timeout', secs=9.0, moved=12.0, t=20.0)])
    # n5 above is 'go' too: so g1/b has go, side-left, go, go (streak of 2 at the end)
    n6 = dec('g1', 'door', 'press-a', 20.0)
    rows.append({'kind': 'result', 'n': n6, 'result': 'done', 'moved': 0.0, 'steps': [], 'wall': w,
                 'interaction': {'kind': 'door', 'outcome': 'done', 'changes': {}, 'detail': ''}})
    n7 = dec('g1', 'door', 'press-a', 20.0)
    rows.append({'kind': 'result', 'n': n7, 'result': 'done', 'moved': 0.0, 'steps': [], 'wall': w,
                 'interaction': {'kind': 'talk', 'outcome': 'none', 'changes': {}, 'detail': ''}})
    rows.append({'kind': 'goal', 'goal': 'g1', 'status': 'met', 't': 20.0, 'pos': [0, 0, 0], 'wall': 150.0})
    for i in range(6):   # six times 'go' on g2/c: the first at t = 21
        k = dec('g2', 'c', 'go' if i != 2 else 'vision-side-left', 21.0 + i, cost=0.001)
        res(k, 'held' if i == 1 else 'reached', 5.0 if i != 1 else 0.0,
            [step('run 9 9 radius 1', 'held' if i == 1 else 'reached', secs=1.0, moved=5.0 if i != 1 else 0.0, t=22.0 + i)])
    rows.append({'kind': 'counterfactual', 'n': 4, 'with_vision': 'side-left', 'without_vision': 'go', 'cost_usd': 0.0002})
    rows.append({'kind': 'counterfactual', 'n': 9, 'with_vision': 'go', 'without_vision': 'go', 'cost_usd': 0.0002})
    rows.append({'kind': 'planner', 'n': 1, 'why': 'start', 'changed': True, 'cost_usd': 0.01, 'latency_ms': 900})
    rows.append({'kind': 'recover', 'n': n4, 'status': 'rung', 'rung': 'back-off', 'at': [0, 0], 'why': 'stuck'})
    (root / 'transcript.jsonl').write_text('\n'.join(json.dumps(r) for r in rows) + '\n')
    (root / 'summary.json').write_text(json.dumps({'run': 'fake-run', 'segment': 'fake-seg', 'decider': 'openai-decisions',
                                                   'outcome': 'budget: 60 s of game time', 'play_wall_s': 120.0}))
    vd = root / 'vision'
    vd.mkdir()
    v = [{'seq': 1, 'n': n4, 'why': ['stuck'], 'backend': 'decisions', 'model': 'gpt-6-luna', 'cost_usd': 0.0003, 'latency_ms': 400,
          'extra': ['vision-side-left'], 'oddities': ['stuck-visible']},
         {'seq': 2, 'n': 9, 'why': ['periodic', 'first'], 'backend': 'decisions', 'model': 'gpt-6-luna', 'cost_usd': 0.0005, 'latency_ms': 800,
          'extra': [], 'oddities': []},
         {'seq': 3, 'n': 10, 'why': ['periodic'], 'error': 'HTTP 400'}]
    (vd / 'vision.jsonl').write_text('\n'.join(json.dumps(r) for r in v) + '\n')
    (vd / 'oddities.jsonl').write_text(json.dumps({'seq': 1, 'n': n4, 'kind': 'stuck-visible'}) + '\n')
    return rows


def run_in(tmp, check):
    d = tmp / 'metrics-run'
    d.mkdir()
    make_run(d)
    ledger = [{'run': 'fake-run', 'kind': 'decision', 'status': 200, 'cost_usd': 0.012, 'latency_ms': 200},
              {'run': 'fake-run', 'kind': 'decision', 'status': 200, 'cost_usd': 0.008, 'latency_ms': 200},
              {'run': 'fake-run', 'kind': 'planner', 'status': 200, 'cost_usd': 0.01, 'latency_ms': 900},
              {'run': 'fake-run', 'kind': 'vision', 'status': 200, 'cost_usd': 0.0003, 'latency_ms': 400},
              {'run': 'fake-run', 'kind': 'vision', 'status': 200, 'cost_usd': 0.0005, 'latency_ms': 800},
              {'run': 'fake-run', 'kind': 'vision', 'status': 400, 'cost_usd': 0.0, 'latency_ms': 50},
              {'run': 'other-run', 'kind': 'decision', 'status': 200, 'cost_usd': 5.0}]
    m = metrics.write_run(d, ledger)
    s, c, g, i, v = m['session'], m['cost'], m['goals'], m['interactions'], m['vision']
    check(m['run'] == 'fake-run' and m['segment'] == 'fake-seg' and m['arm'] == 'decisions+vision', f"metrics: run, segment and the arm ({m['arm']})")
    check(s['decisions'] == 13 and s['play_wall_s'] == 120.0 and s['decisions_per_min_wall'] == 6.5, f"metrics: 13 decisions in 2 minutes ({s['decisions_per_min_wall']})")
    check(abs(s['distance_m'] - 60.3) < 0.01 and abs(s['km'] - 0.0603) < 1e-6, f"metrics: distance summed over the result rows ({s['distance_m']})")
    check(s['stuck_steps'] == 2 and s['stuck_s_total'] == 7.0 and s['stuck_s_mean'] == 3.5 and s['stuck_s_max'] == 4.0,
          f"metrics: two stuck steps of 3 and 4 s ({s['stuck_steps']}, {s['stuck_s_total']})")
    check(abs(s['stuck_steps_per_km'] - 2 / 0.0603) < 0.5, f"metrics: stuck steps per km ({s['stuck_steps_per_km']})")
    check(s['timeout_steps'] == 1 and s['held_steps'] == 1 and s['cut_steps'] == 0, 'metrics: timeouts and held steps counted apart')
    check(s['streak_max'] == 3 and s['streaks_ge5'] == 0, f"metrics: the longest identical streak is three go on g2/c ({s['streak_max']}, {s['streaks_ge5']})")
    check(s['goals_total'] == 2 and s['goals_met'] == 1 and g['g1']['status'] == 'met' and g['g2']['status'] == 'open',
          'metrics: g1 met, g2 never')
    check(g['g1']['time_to_reach_game_s'] == 20.0 and g['g1']['time_to_reach_wall_s'] == 50.0 and g['g1']['since_previous_goal_game_s'] == 20.0,
          f"metrics: g1 reached 20 game s and 50 wall s after the first decision ({g['g1']})")
    check(g['g1']['decisions'] == 7 and g['g2']['decisions'] == 6, 'metrics: decisions per goal')
    check(g['g1']['stuck_steps'] == 2 and g['g2']['stuck_steps'] == 0 and abs(g['g1']['distance_m'] - 35.3) < 0.01, 'metrics: stuck steps and metres per goal')
    check(g['g1']['targets_done'] + g['g1']['targets_failed'] == 0, 'metrics: no next-target row, no target verdict')
    check(i['by_outcome'] == {'done': 1, 'none': 1} and i['attempted'] == 2 and i['succeeded'] == 2 and i['by_kind']['door'] == {'attempted': 1, 'succeeded': 1} and
          i['by_kind']['talk'] == {'attempted': 1, 'succeeded': 1}, f'metrics: interactions by the result rows, a goal met right after counts ({i})')
    check(c['source'] == 'ledger' and abs(c['total_usd'] - 0.0308) < 1e-9 and abs(c['by_kind']['decision']['cost_usd'] - 0.02) < 1e-9,
          f"metrics: cost from the ledger by run id, other runs left out ({c['total_usd']})")
    check(c['by_kind']['vision']['errors'] == 1 and abs(c['per_min_usd'] - 0.0308 / 2) < 1e-6 and abs(c['per_goal_met_usd'] - 0.0308) < 1e-6,
          'metrics: cost per minute of play and per goal met; a refused vision request counted as an error')
    check(v['calls'] == 2 and v['errors'] == 1 and abs(v['cost_usd'] - 0.0008) < 1e-9 and v['by_reason'] == {'stuck': 1, 'periodic': 1, 'first': 1},
          'metrics: vision calls, errors, cost and the reasons')
    check(v['oddities'] == {'stuck-visible': 1} and v['extra_offered'] == {'vision-side-left': 1}, 'metrics: vision oddities and offers')
    check(v['extra_chosen'] == {'vision-side-left': {'chosen': 1, 'results': {'reached': 1}}}, f"metrics: the vision candidate chosen once ({v['extra_chosen']})")
    ch = {c['n']: c for c in v['changes']}
    check(ch[4]['changed'] and 'stuck-visible' in ch[4]['oddities'], 'metrics: a look that recorded an oddity changed something')
    check(ch[9]['changed'] is False or ch[9]['changed'] is True, 'metrics: every look has a verdict')
    check(v['counterfactual'] == {'asked': 2, 'differed': 1, 'cost_usd': 0.0004}, f"metrics: asked again without the picture: {v['counterfactual']}")
    check(m['recover'] and m['recover']['by_status'] == {'rung': 1} and m['recover']['decisions_stuck'] == 1 and m['recover']['max_stalled_s'] == 4.5,
          'metrics: recovery rows and verdicts')
    check(s['life'] == {'start': 24, 'min': 20, 'end': 20} or s['life']['min'] <= s['life']['start'], f"metrics: life start, min, end ({s['life']})")
    check((d / 'metrics.json').exists() and (d / 'metrics.md').exists() and '| goal |' in (d / 'metrics.md').read_text(), 'metrics: written as JSON and a short table')
    again = json.loads((d / 'metrics.json').read_text())
    check(again['session']['stuck_steps'] == 2, 'metrics: the JSON reads back')
    # no ledger rows for the run: the transcript's own costs
    m2 = metrics.analyse(d, ledger=[])
    check(m2['cost']['source'] == 'transcript' and abs(m2['cost']['total_usd'] - (0.013 + 0.01 + 0.0008)) < 1e-9, f"metrics: without ledger rows, the transcript's costs ({m2['cost']['total_usd']})")
    # an empty or missing run folder does not raise and has no invented numbers
    e = tmp / 'empty-run'
    e.mkdir()
    m3 = metrics.analyse(e, ledger=[])
    check(m3['session']['decisions'] == 0 and m3['session']['stuck_steps_per_km'] is None and m3['session']['play_wall_s'] is None and
          m3['cost']['per_min_usd'] is None and m3['vision'] is None, 'metrics: an empty run has None, not zero, for what it cannot know')
    # the arm label can be given
    check(metrics.analyse(d, ledger=ledger, arm='decisions+vision-big')['arm'] == 'decisions+vision-big', 'metrics: the benchmark can name the arm')
    # next-target verdicts: reached -> done, a recovery result -> failed
    f = tmp / 'verdict-run'
    f.mkdir()
    rows = [{'kind': 'decision', 'n': 1, 'goal': 'g', 'target': 'a', 'choice': 'go', 'state': {'t': 0}, 'wall': 1.0},
            {'kind': 'result', 'n': 1, 'result': 'reached', 'moved': 5, 'steps': []},
            {'kind': 'decision', 'n': 2, 'goal': 'g', 'target': 'a', 'choice': 'next-target', 'state': {'t': 1}, 'wall': 2.0},
            {'kind': 'decision', 'n': 3, 'goal': 'g', 'target': 'b', 'choice': 'go', 'state': {'t': 1}, 'wall': 3.0},
            {'kind': 'result', 'n': 3, 'result': 'stuck', 'moved': 0, 'steps': []},
            {'kind': 'decision', 'n': 4, 'goal': 'g', 'target': 'b', 'choice': 'next-target', 'state': {'t': 2}, 'wall': 4.0}]
    (f / 'transcript.jsonl').write_text('\n'.join(json.dumps(r) for r in rows) + '\n')
    m4 = metrics.analyse(f, ledger=[])
    check(m4['goals']['g']['targets_done'] == 1 and m4['goals']['g']['targets_failed'] == 1, 'metrics: a target left after reaching is done, after a stuck move failed')
    # the TAS baseline from a scripted route's events
    events = [{'ev': 'step', 'src': 'walk 1 1 radius 1', 'result': 'reached', 'secs': 4.0, 'moved': 10.0, 't': 6.0},
              {'ev': 'step', 'src': 'run 2 2 radius 1', 'result': 'stuck', 'secs': 3.0, 'moved': 0.0, 't': 9.0},
              {'ev': 'step', 'src': 'until flag Door_Open=1 timeout 10', 'result': 'met', 'secs': 1.0, 'moved': 0.0, 't': 12.0},
              {'ev': 'step', 'src': 'until flag Scene=1 timeout 40', 'result': 'timeout', 'secs': 40.0, 'moved': 0.0, 't': 52.0},
              {'ev': 'state', 'why': 'wait', 't': 52.0}]
    tas = metrics.of_route_events(events, {'door': 'Door_Open=1', 'scene': 'Scene=1'}, run='tas-1', segment='fake-seg')
    check(tas['arm'] == 'tas' and tas['goals']['door']['time_to_reach_game_s'] == 12.0 - 2.0 and tas['goals']['scene']['status'] == 'open' and
          tas['session']['stuck_steps'] == 1 and tas['session']['goals_met'] == 1 and tas['cost']['total_usd'] == 0.0 and tas['outcome'] == 'partial',
          f"metrics: a scripted route's events give goal times, stuck steps and no cost ({tas['goals']['door']})")
    table = metrics.session_table([m, tas])
    lines = table.splitlines()
    check(len(lines) == 4 and lines[0].startswith('| run | arm |') and 'tas' in lines[3] and 'decisions+vision' in lines[2],
          'metrics: the table has a header, a rule and a row per run')
    check(all(line.count('|') == lines[0].count('|') for line in lines), 'metrics: every row of the table has the same columns')


def run():
    fails, count = [], [0]

    def check(cond, what):
        count[0] += 1
        if not cond:
            fails.append(what)
            print('FAIL', what, flush=True)
    with tempfile.TemporaryDirectory(prefix='metrics-test-') as t:
        run_in(Path(t), check)
    if fails:
        raise SystemExit(f'test_metrics: {len(fails)} of {count[0]} checks FAILED')
    print(f'test_metrics: all passed ({count[0]} checks)')


if __name__ == '__main__':
    run()
