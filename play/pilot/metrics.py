#!/usr/bin/env python3
"""How well did the pilot play? Numbers from a run folder, never from the game.

A run folder (pilot/runs/<tag>/) holds what the pilot wrote: transcript.jsonl (one row per decision, result, goal, planner,
recover ...), summary.json, out.jsonl (the game side's step events), vision/vision.jsonl and vision/oddities.jsonl, and the
ledger (pilot/ledger.jsonl) has every model request by run id. This module reads those and writes, per session and per goal,
  - stuck steps per km of walking, and how long each stuck step lasted (a move step that ended `stuck`; timeouts, held and
    cut ones are counted apart),
  - the time to reach each goal (game seconds and wall seconds from the first decision; since the goal before it),
  - decisions per minute (wall and game) and per goal,
  - identical-answer streaks (the same choice on the same target decision after decision; max, how many of 5 or more),
  - model cost (decision, planner, vision) from the ledger, per minute of play, per goal met and per km,
  - interactions attempted and succeeded (a candidate that is an interaction, and its result row's `interaction` outcome),
  - vision calls, their cost and latency, why they were made, what they offered, which offers were chosen, what they changed,
  - recovery rungs (recover.py), life lost, how each target ended (done / failed).
  metrics.json and metrics.md (a short table) are written into the run folder (write_run). `table` puts many runs side by
  side (one row each: the benchmark's table). `of_route_events` gives a scripted (TAS) route the same numbers from its
  out.jsonl, as the baseline row.

  metrics.py <run folder> ...        write and print each run's metrics, then the table of all of them
  metrics.py table <metrics.json> ...  the table of finished metrics files

Definitions are in the code (`analyse`); a number that cannot be known from the files is None, never zero.
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import openai_api  # noqa: E402

try:   # PilotInteract's module: which candidates are interactions and what their outcomes mean
    import interact as _interact
except ImportError:   # a checkout without it: the labels the pilot has always had
    _interact = None

MOVE_VERBS = ('walk', 'run', 'approach')
DEFAULT_INTERACTIONS = {'press-a', 'talk-until-goal', 'press-a-through', 'push-open', 'open-door-on-way', 'crawl-in',
                        'crawl-on-way', 'climb-up', 'climb-on-way', 'push', 'strike'}
OK_WORDS = {'met', 'done', 'reached', 'opened', 'talked', 'picked', 'entered', 'closed', 'played'}
RECOVERY = ('back-off', 'side-left', 'side-right')
STREAK_MIN = 5


def read_jsonl(path):
    rows = []
    try:
        for line in Path(path).read_text().splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    except OSError:
        pass
    return rows


def median(xs):
    return round(statistics.median(xs), 2) if xs else None


def rnd(v, n=3):
    return None if v is None else round(v, n)


def ratio(a, b, n=3):
    return round(a / b, n) if b else None


def interaction_labels():
    if _interact is not None and getattr(_interact, 'INTERACT_LABELS', None):
        return set(_interact.INTERACT_LABELS) | DEFAULT_INTERACTIONS
    return DEFAULT_INTERACTIONS


def interaction_of(label, row):
    """The interaction dict of a result row: its own `interaction` field (the pilot writes it), else PilotInteract's reading of the
    steps, else (an old run) the label alone with the result word. None for a label that is no interaction."""
    inter = row.get('interaction')
    if isinstance(inter, dict):
        return inter
    if _interact is not None and hasattr(_interact, 'interaction_of'):
        try:
            got = _interact.interaction_of(label, row.get('steps'))
        except Exception:   # noqa: BLE001  an analysis must not fail on a row it cannot read
            got = None
        if got:
            return got
    if label in DEFAULT_INTERACTIONS:
        return {'kind': 'attempt', 'outcome': 'done' if row.get('result') in OK_WORDS else 'none'}
    return None


def step_verb(step):
    w = (step.get('src') or '').split()
    return w[0] if w else ''


def analyse(run_dir, ledger=None, arm=None):
    """The metrics of one run folder as a dict (see the module docstring). `ledger`: the ledger rows to use (default: the pilot's)."""
    run_dir = Path(run_dir)
    rows = read_jsonl(run_dir / 'transcript.jsonl')
    try:
        summary = json.loads((run_dir / 'summary.json').read_text())
    except (OSError, ValueError):
        summary = {}
    run_id = summary.get('run') or run_dir.name
    vrows = read_jsonl(run_dir / 'vision' / 'vision.jsonl')
    orows = read_jsonl(run_dir / 'vision' / 'oddities.jsonl')
    decisions = [r for r in rows if r.get('kind') == 'decision']
    results = {r['n']: r for r in rows if r.get('kind') == 'result' and 'n' in r}
    dec_by_n = {d['n']: d for d in decisions if 'n' in d}
    goal_rows = [r for r in rows if r.get('kind') == 'goal']
    recover_rows = [r for r in rows if r.get('kind') == 'recover']
    planner_rows = [r for r in rows if r.get('kind') == 'planner']
    walls = [r['wall'] for r in rows if isinstance(r.get('wall'), (int, float))]
    ts = [d['state']['t'] for d in decisions if isinstance(d.get('state'), dict) and isinstance(d['state'].get('t'), (int, float))]
    for r in results.values():
        ts += [s['t'] for s in (r.get('steps') or []) if s and isinstance(s.get('t'), (int, float))]
    wall0 = walls[0] if walls else None
    t0 = ts[0] if ts else None
    play_wall = summary.get('play_wall_s')
    if play_wall is None and len(walls) > 1:
        play_wall = round(walls[-1] - walls[0], 1)
    game_s = round(max(ts) - min(ts), 1) if ts else None

    # steps: stuck, timeouts, held, cut, distance
    distance, stuck_secs, other = 0.0, [], {'timeout': 0, 'held': 0, 'cut': 0}
    move_steps = 0
    stuck_by_n, steps_by_goal_dist = {}, {}
    for n, r in results.items():
        distance += float(r.get('moved') or 0)
        g = (dec_by_n.get(n) or {}).get('goal')
        steps_by_goal_dist[g] = steps_by_goal_dist.get(g, 0.0) + float(r.get('moved') or 0)
        for s in r.get('steps') or []:
            if not s or s.get('ev') != 'step' or step_verb(s) not in MOVE_VERBS:
                continue
            move_steps += 1
            res = s.get('result')
            if res == 'stuck':
                stuck_secs.append(float(s.get('secs') or 0))
                stuck_by_n[n] = stuck_by_n.get(n, 0) + 1
            elif res in other:
                other[res] += 1
    km = distance / 1000.0

    # streaks: the same choice on the same target, decision after decision
    streaks, cur = [], None
    for d in decisions:
        key = (d.get('goal'), d.get('target'), d.get('choice'))
        if cur and cur['key'] == key:
            cur['len'] += 1
        else:
            cur = {'key': key, 'len': 1, 'n': d.get('n')}
            streaks.append(cur)
    longest = max(streaks, key=lambda s: s['len'], default=None)
    long_streaks = [s for s in streaks if s['len'] >= STREAK_MIN]

    # how each target ended: next-target after a reaching result is done, else failed (the pilot's own rule)
    last_result, targets = {}, {}
    for d in decisions:
        key = (d.get('goal'), d.get('target'))
        n = d.get('n')
        if d.get('choice') in ('next-target', 'give-up-goal'):
            prev = last_result.get(key)
            ok = prev is not None and prev[0] not in RECOVERY and prev[1] in ('reached', 'done', 'met')
            targets.setdefault(d.get('goal'), {})[d.get('target')] = 'done' if ok and d.get('choice') == 'next-target' else 'failed'
        elif n in results:
            last_result[key] = (d.get('choice'), results[n].get('result'))

    # goals
    final, met_rows = {}, {}
    for g in goal_rows:
        final[g.get('goal')] = g.get('status')
        if g.get('status') == 'met':
            met_rows[g.get('goal')] = g
    goals = {}
    order = []
    for d in decisions:
        if d.get('goal') not in order:
            order.append(d.get('goal'))
    for g in goal_rows:
        if g.get('goal') not in order:
            order.append(g.get('goal'))
    prev_t, prev_wall = t0, wall0
    for name in order:
        ds = [d for d in decisions if d.get('goal') == name]
        gm = met_rows.get(name)
        gt = gm.get('t') if gm else None
        gw = gm.get('wall') if gm else None
        first_t = (ds[0].get('state') or {}).get('t') if ds else None
        first_w = ds[0].get('wall') if ds else None
        last_w = ds[-1].get('wall') if ds else None
        active_wall = (gw if gw is not None else last_w) - first_w if first_w is not None and (gw is not None or last_w is not None) else None
        cost = sum(float(d.get('cost_usd') or 0) for d in ds)
        cost += sum(float(v.get('cost_usd') or 0) for v in vrows if (dec_by_n.get(v.get('n')) or {}).get('goal') == name)
        goals[name] = {
            'status': final.get(name, 'open'),
            'time_to_reach_game_s': rnd(gt - t0, 1) if gt is not None and t0 is not None else None,
            'time_to_reach_wall_s': rnd(gw - wall0, 1) if gw is not None and wall0 is not None else None,
            'since_previous_goal_game_s': rnd(gt - prev_t, 1) if gt is not None and prev_t is not None else None,
            'decisions': len(ds), 'active_wall_s': rnd(active_wall, 1),
            'decisions_per_min': ratio(len(ds) * 60.0, active_wall, 2) if active_wall else None,
            'distance_m': rnd(steps_by_goal_dist.get(name, 0.0), 1),
            'stuck_steps': sum(c for n, c in stuck_by_n.items() if (dec_by_n.get(n) or {}).get('goal') == name),
            'targets_done': sum(1 for v in targets.get(name, {}).values() if v == 'done'),
            'targets_failed': sum(1 for v in targets.get(name, {}).values() if v == 'failed'),
            'cost_usd': round(cost, 6),
        }
        if gt is not None:
            prev_t = gt
        if gw is not None:
            prev_wall = gw
    del prev_wall

    # interactions
    attempts, labels, by_kind, pending = 0, interaction_labels(), {}, None
    succeeded, by_outcome = 0, {}
    for r in rows:
        if r.get('kind') == 'result':
            label = (dec_by_n.get(r.get('n')) or {}).get('choice')
            inter = interaction_of(label, r) if label in labels or r.get('interaction') else None
            if inter:
                attempts += 1
                kind = inter.get('kind') or 'attempt'
                by_outcome[inter.get('outcome')] = by_outcome.get(inter.get('outcome'), 0) + 1
                k = by_kind.setdefault(kind, {'attempted': 0, 'succeeded': 0})
                k['attempted'] += 1
                ok = inter.get('outcome') == 'done'
                if ok:
                    succeeded += 1
                    k['succeeded'] += 1
                pending = None if ok else (kind, k)
            else:
                pending = None
        elif r.get('kind') == 'goal' and r.get('status') == 'met' and pending:   # a goal met right after an attempt that showed nothing
            succeeded += 1
            pending[1]['succeeded'] += 1
            pending = None

    # cost
    led = [x for x in (openai_api.ledger_rows() if ledger is None else ledger) if x.get('run') == run_id]
    src = 'ledger'
    if not led:
        src = 'transcript'
        led = [{'kind': 'decision', 'cost_usd': d.get('cost_usd'), 'latency_ms': d.get('latency_ms')} for d in decisions if 'cost_usd' in d]
        led += [{'kind': 'planner', 'cost_usd': p.get('cost_usd'), 'latency_ms': p.get('latency_ms')} for p in planner_rows if 'cost_usd' in p]
        led += [{'kind': 'vision', 'cost_usd': v.get('cost_usd'), 'latency_ms': v.get('latency_ms')} for v in vrows if v.get('cost_usd') is not None]
    by = {}
    for x in led:
        k = by.setdefault(x.get('kind') or '?', {'requests': 0, 'errors': 0, 'cost_usd': 0.0})
        k['requests'] += 1
        k['errors'] += 0 if x.get('status', 200) == 200 else 1
        k['cost_usd'] += float(x.get('cost_usd') or 0)
    total = sum(k['cost_usd'] for k in by.values())
    minutes = play_wall / 60.0 if play_wall else None
    met = sum(1 for v in goals.values() if v['status'] == 'met')
    cost = {'source': src, 'total_usd': round(total, 6), 'by_kind': {k: dict(v, cost_usd=round(v['cost_usd'], 6)) for k, v in sorted(by.items())},
            'per_min_usd': rnd(total / minutes, 6) if minutes else None, 'per_goal_met_usd': rnd(total / met, 6) if met else None,
            'per_km_usd': rnd(total / km, 6) if km > 0.05 else None}

    # vision: what it cost, why it looked, what it offered and what the pilot chose, what changed
    vision = None
    if vrows or summary.get('vision'):
        good = [v for v in vrows if not v.get('error')]
        reasons, odd_kinds, offered, chosen = {}, {}, {}, {}
        for v in good:
            for w in v.get('why') or []:
                reasons[w] = reasons.get(w, 0) + 1
            for e in v.get('extra') or []:
                offered[e] = offered.get(e, 0) + 1
        for o in orows or [{'kind': k} for v in good for k in v.get('oddities') or []]:
            odd_kinds[o.get('kind')] = odd_kinds.get(o.get('kind'), 0) + 1
        for d in decisions:
            if str(d.get('choice') or '').startswith('vision-'):
                c = chosen.setdefault(d['choice'], {'chosen': 0, 'results': {}})
                c['chosen'] += 1
                res = (results.get(d.get('n')) or {}).get('result')
                c['results'][res] = c['results'].get(res, 0) + 1
        changed, fresh_n = [], {v.get('n') for v in good if v.get('n') is not None}
        seq = [(d.get('n'), d.get('choice')) for d in decisions]
        for v in good:
            n = v.get('n')
            if n not in dec_by_n:
                continue
            i = next((i for i, (m, _) in enumerate(seq) if m == n), None)
            prev = seq[i - 1][1] if i else None
            run_len = 0
            for m, c in reversed(seq[:i]):
                if c == prev:
                    run_len += 1
                else:
                    break
            choice = dec_by_n[n].get('choice')
            vis_pick = str(choice).startswith('vision-')
            broke = run_len >= 3 and choice != prev
            after = [results.get(m) for m, _ in seq[i:i + 3] if results.get(m)]
            moved_after = 'stuck' in (v.get('why') or []) and any((r.get('moved') or 0) >= 1.0 and r.get('result') in ('reached', 'done') for r in after)
            changed.append({'n': n, 'why': v.get('why'), 'choice': choice, 'previous_choice': prev, 'streak_before': run_len,
                            'chose_vision_candidate': vis_pick, 'broke_streak': broke, 'oddities': v.get('oddities') or [],
                            'moved_on_after_stuck_look': moved_after,
                            'changed': bool(vis_pick or broke or v.get('oddities') or moved_after)})
        lat = sorted(v['latency_ms'] for v in good if isinstance(v.get('latency_ms'), (int, float)))
        vision = {'calls': len(good), 'errors': len(vrows) - len(good), 'cost_usd': round(sum(float(v.get('cost_usd') or 0) for v in good), 6),
                  'backend': (vrows[0].get('backend') if vrows else None), 'model': (vrows[0].get('model') if vrows else None),
                  'latency_ms_median': openai_api.percentile(lat, 50), 'latency_ms_p95': openai_api.percentile(lat, 95),
                  'by_reason': reasons, 'oddities': odd_kinds, 'extra_offered': offered, 'extra_chosen': chosen,
                  'decisions_with_hint': sum(1 for d in decisions if isinstance(d.get('state'), dict) and d['state'].get('vision')),
                  'fresh_looks_before_decisions': len(fresh_n), 'looks_that_changed': sum(1 for c in changed if c['changed']),
                  'changes': changed}
        cf = [r for r in rows if r.get('kind') == 'counterfactual']
        if cf:   # the pilot asked the decider twice at a fresh look: with the picture's hint and candidates, and without
            vision['counterfactual'] = {'asked': len(cf), 'differed': sum(1 for r in cf if r.get('with_vision') != r.get('without_vision')),
                                        'cost_usd': round(sum(float(r.get('cost_usd') or 0) for r in cf), 6)}
        try:
            vision['off_reason'] = json.loads((run_dir / 'vision' / 'summary.json').read_text()).get('off_reason')
        except (OSError, ValueError):
            vision['off_reason'] = None

    # recovery (recover.py): rungs and verdicts
    recover = None
    rec_dec = [d.get('recover') for d in decisions if isinstance(d.get('recover'), dict)]
    if recover_rows or rec_dec:
        st = {}
        for r in recover_rows:
            st[r.get('status')] = st.get(r.get('status'), 0) + 1
        recover = {'rows': len(recover_rows), 'by_status': st, 'decisions_stuck': sum(1 for r in rec_dec if r.get('stuck')),
                   'max_stalled_s': max((r.get('stalled_s') or 0 for r in rec_dec), default=None)}

    lives = [d['state']['life'] for d in decisions if isinstance(d.get('state'), dict) and isinstance(d['state'].get('life'), (int, float))]
    session = {
        'play_wall_s': play_wall, 'game_s': game_s, 'decisions': len(decisions),
        'decisions_per_min_wall': ratio(len(decisions), minutes, 2), 'decisions_per_min_game': ratio(len(decisions) * 60.0, game_s, 2) if game_s else None,
        'no_request_decisions': sum(1 for d in decisions if d.get('no_request')),
        'fallback_decisions': sum(1 for d in decisions if d.get('fallback')),
        'distance_m': round(distance, 1), 'km': round(km, 4), 'move_steps': move_steps,
        'stuck_steps': len(stuck_secs), 'stuck_steps_per_km': ratio(len(stuck_secs), km) if km > 0.05 else None,
        'stuck_s_total': round(sum(stuck_secs), 1), 'stuck_s_mean': rnd(sum(stuck_secs) / len(stuck_secs), 2) if stuck_secs else None,
        'stuck_s_median': median(stuck_secs), 'stuck_s_max': round(max(stuck_secs), 1) if stuck_secs else None,
        'timeout_steps': other['timeout'], 'held_steps': other['held'], 'cut_steps': other['cut'],
        'streak_max': longest['len'] if longest else 0, 'streaks_ge5': len(long_streaks),
        'streak_decisions': sum(s['len'] for s in long_streaks),
        'streak_longest': {'choice': longest['key'][2], 'goal': longest['key'][0], 'target': longest['key'][1], 'from_n': longest['n']} if longest else None,
        'goals_total': len(goals), 'goals_met': met, 'goals_failed': sum(1 for v in goals.values() if v['status'] == 'failed'),
        'targets_done': sum(v['targets_done'] for v in goals.values()), 'targets_failed': sum(v['targets_failed'] for v in goals.values()),
        'life': {'start': lives[0], 'min': min(lives), 'end': lives[-1]} if lives else None,
        'planner_calls': len(planner_rows), 'planner_changed': sum(1 for p in planner_rows if p.get('changed'))}
    decider = summary.get('decider') or (decisions[0].get('decider') if decisions else None)
    if arm is None:
        arm = {'openai-decisions': 'decisions'}.get(decider, decider)
        if vision and vision['calls']:
            arm = f'{arm}+vision'
    return {'run': run_id, 'segment': summary.get('segment'), 'decider': decider, 'arm': arm, 'outcome': summary.get('outcome'),
            'session': session, 'goals': goals, 'interactions': {'attempted': attempts, 'succeeded': succeeded,
                                                                'rate': ratio(succeeded, attempts, 2), 'by_kind': by_kind,
                                                                'by_outcome': by_outcome},
            'cost': cost, 'vision': vision, 'recover': recover}


def of_route_events(events, goals, run='tas', segment=None, arm='tas'):
    """The same numbers for a scripted route (a TAS) from its hsap out.jsonl events: `goals` is {goal name: 'NAME=VALUE'} (the
    segment's flag text); a goal is reached at the `until flag <text> ...` step that came out `met`. No decisions, no cost."""
    steps = [e for e in events if e.get('ev') == 'step']
    ts = [e['t'] for e in steps if isinstance(e.get('t'), (int, float))]
    t0 = ts[0] - float(steps[0].get('secs') or 0) if ts and steps else None
    moved, stuck, other = 0.0, [], {'timeout': 0, 'held': 0, 'cut': 0}
    reached = {}
    for e in steps:
        moved += float(e.get('moved') or 0)
        if step_verb(e) in MOVE_VERBS:
            if e.get('result') == 'stuck':
                stuck.append(float(e.get('secs') or 0))
            elif e.get('result') in other:
                other[e['result']] += 1
        src = e.get('src') or ''
        if src.startswith('until flag ') and e.get('result') == 'met':
            flag = src[len('until flag '):].split(' timeout')[0].split(' press')[0].strip()
            for name, text in goals.items():
                if text == flag and name not in reached:
                    reached[name] = e.get('t')
    km = moved / 1000.0
    play = round(max(ts) - t0, 1) if ts and t0 is not None else None
    g = {name: {'status': 'met' if name in reached else 'open',
                'time_to_reach_game_s': rnd(reached[name] - t0, 1) if name in reached and t0 is not None and reached[name] is not None else None,
                'time_to_reach_wall_s': None, 'decisions': 0, 'cost_usd': 0.0} for name in goals}
    session = {'play_wall_s': play, 'game_s': play, 'decisions': 0, 'decisions_per_min_wall': None, 'distance_m': round(moved, 1),
               'km': round(km, 4), 'stuck_steps': len(stuck), 'stuck_steps_per_km': ratio(len(stuck), km) if km > 0.05 else None,
               'stuck_s_total': round(sum(stuck), 1), 'stuck_s_mean': rnd(sum(stuck) / len(stuck), 2) if stuck else None,
               'stuck_s_max': round(max(stuck), 1) if stuck else None, 'timeout_steps': other['timeout'], 'held_steps': other['held'],
               'cut_steps': other['cut'], 'streak_max': 0, 'streaks_ge5': 0, 'goals_total': len(goals), 'goals_met': len(reached),
               'goals_failed': 0, 'life': None}
    return {'run': run, 'segment': segment, 'decider': 'tas', 'arm': arm, 'outcome': 'solved' if len(reached) == len(goals) else 'partial',
            'session': session, 'goals': g, 'interactions': {'attempted': None, 'succeeded': None, 'rate': None, 'by_kind': {}},
            'cost': {'source': 'none', 'total_usd': 0.0, 'by_kind': {}, 'per_min_usd': 0.0, 'per_goal_met_usd': 0.0, 'per_km_usd': 0.0},
            'vision': None, 'recover': None}


def fmt(v, nd=None):
    if v is None:
        return '-'
    if isinstance(v, float):
        return f'{v:.{nd}f}' if nd is not None else f'{v:g}'
    return str(v)


def session_table(ms, label='run'):
    """One markdown row per metrics dict: the numbers that compare arms."""
    head = [label, 'arm', 'outcome', 'goals met', 'play s', 'dec', 'dec/min', 'km', 'stuck/km', 'stuck s', 'streak max', 'inter ok/att',
            'vision', 'oddities', 'USD', 'USD/min', 'USD/goal']
    lines = ['| ' + ' | '.join(head) + ' |', '|' + '|'.join(['---'] * len(head)) + '|']
    for m in ms:
        s, c, v, i = m['session'], m['cost'], m.get('vision'), m['interactions']
        inter = '-' if i.get('attempted') is None else f"{i['succeeded']}/{i['attempted']}"
        lines.append('| ' + ' | '.join([
            fmt(m.get(label if label != 'run' else 'run')), fmt(m['arm']), fmt((m.get('outcome') or '-')[:28]),
            f"{s['goals_met']}/{s['goals_total']}", fmt(s['play_wall_s']), fmt(s['decisions']), fmt(s['decisions_per_min_wall']),
            fmt(s['km']), fmt(s['stuck_steps_per_km']), fmt(s['stuck_s_total']), fmt(s['streak_max']), inter,
            fmt(v['calls']) if v else '-', fmt(sum(v['oddities'].values())) if v else '-', fmt(c['total_usd'], 4),
            fmt(c['per_min_usd'], 4), fmt(c['per_goal_met_usd'], 4)]) + ' |')
    return '\n'.join(lines)


def goal_table(m):
    head = ['goal', 'status', 'reached (game s)', 'reached (wall s)', 'dec', 'dec/min', 'm', 'stuck', 'targets done/failed', 'USD']
    lines = ['| ' + ' | '.join(head) + ' |', '|' + '|'.join(['---'] * len(head)) + '|']
    for name, g in m['goals'].items():
        lines.append('| ' + ' | '.join([name, g['status'], fmt(g['time_to_reach_game_s']), fmt(g['time_to_reach_wall_s']), fmt(g['decisions']),
                                         fmt(g.get('decisions_per_min')), fmt(g.get('distance_m')), fmt(g.get('stuck_steps')),
                                         f"{g.get('targets_done', 0)}/{g.get('targets_failed', 0)}", fmt(g['cost_usd'], 4)]) + ' |')
    return '\n'.join(lines)


def render(m):
    out = [f"# {m['run']} ({m['segment']}, {m['arm']}): {m.get('outcome')}", '', session_table([m]), '', goal_table(m)]
    s = m['session']
    out += ['', f"Stuck: {s['stuck_steps']} move steps ended stuck ({fmt(s['stuck_s_total'])} s in all, longest {fmt(s['stuck_s_max'])} s), "
                f"{s['timeout_steps']} timed out, {s['held_steps']} held, {s['cut_steps']} cut, over {s['km']:g} km. "
                f"Longest identical streak: {s['streak_max']} ({s.get('streak_longest')}); {s['streaks_ge5']} streaks of {STREAK_MIN} or more."]
    i = m['interactions']
    if i['attempted'] is not None:
        out.append(f"Interactions: {i['succeeded']} of {i['attempted']} succeeded; by kind {json.dumps(i['by_kind'])}; outcomes {json.dumps(i.get('by_outcome'))}.")
    c = m['cost']
    out.append(f"Cost ({c['source']}): {c['total_usd']:.4f} USD {json.dumps({k: v['cost_usd'] for k, v in c['by_kind'].items()})}, "
               f"{fmt(c['per_min_usd'], 4)} USD/min of play, {fmt(c['per_goal_met_usd'], 4)} USD per goal met.")
    v = m.get('vision')
    if v:
        out.append(f"Vision ({v['backend']}, {v['model']}): {v['calls']} looks ({v['errors']} failed), {v['cost_usd']:.4f} USD, median "
                   f"{fmt(v['latency_ms_median'])} ms; reasons {json.dumps(v['by_reason'])}; oddities {json.dumps(v['oddities'])}; offered "
                   f"{json.dumps(v['extra_offered'])}; chosen {json.dumps({k: c['chosen'] for k, c in v['extra_chosen'].items()})}; "
                   f"{v['looks_that_changed']} of {v['fresh_looks_before_decisions']} looks changed a decision"
                   + (f"; asked again without the picture {v['counterfactual']['asked']} times, a different answer {v['counterfactual']['differed']} times." if v.get('counterfactual') else '.'))
    if m.get('recover'):
        out.append(f"Recovery: {json.dumps(m['recover'])}")
    return '\n'.join(out) + '\n'


def write_run(run_dir, ledger=None, arm=None):
    """Analyse a run folder and write metrics.json and metrics.md into it; returns the metrics."""
    m = analyse(run_dir, ledger, arm)
    run_dir = Path(run_dir)
    (run_dir / 'metrics.json').write_text(json.dumps(m, indent=1))
    (run_dir / 'metrics.md').write_text(render(m))
    return m


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('paths', nargs='+', help='run folders, or: table <metrics.json> ...')
    ap.add_argument('--arm')
    a = ap.parse_args()
    if a.paths[0] == 'table':
        ms = [json.loads(Path(p).read_text()) for p in a.paths[1:]]
    else:
        ms = [write_run(p, arm=a.arm) for p in a.paths]
        for m in ms:
            print(render(m))
    print(session_table(ms))
    return 0


if __name__ == '__main__':
    sys.exit(main())
