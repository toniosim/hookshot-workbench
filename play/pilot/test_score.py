#!/usr/bin/env python3
"""score.py on made-up rounds and registries: verdicts become rules (artefact explained with its reason, known labelled, real kept, fixed is a
regression), the scorecard per detector and its false-alarm rate, the ledger and the trend, regression checks from replay verdicts, the passive
scan (new keys flagged), the next round's hints, and the hold applying the rules to what it finds. No game, no network.   python3 -I -B test_score.py"""
import json, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bughunt, bugpacket, score  # noqa: E402
import test_bughunt as tb  # noqa: E402
FAILS, CHECKS = [], [0]
def check(c, w):
    CHECKS[0] += 1
    if not c:
        FAILS.append(w); print('FAIL', w, flush=True)
def F(kind, sub, key, sev='warning', **ev):
    return bughunt.Finding(kind, sub, sev, 'solo', f'{kind} {sub}', evidence=ev, key=key)
def run_in(tmp):
    ent = {'a:1': {'status': 'artefact', 'note': 'the other game ended'}, 'k:1': {'status': 'known-issue', 'note': 'docs say so', 'packet': str(tmp / 'pk-k')},
           'r:1': {'status': 'real', 'packet': str(tmp / 'pk-r')}, 'f:1': {'status': 'fixed', 'packet': str(tmp / 'pk-f')}, 'o:1': {'status': 'open'}}
    fs = [F('log', 'x', 'a:1'), F('give', 'double', 'k:1', 'error'), F('stall', 'stall', 'r:1', 'error'), F('hang', 'live', 'f:1', 'error'), F('oob', 'x', 'o:1'), F('crash', 'x', 'n:1'), F('stall', 'both', 'a:1', 'info')]
    n = score.apply_feedback(fs, ent)
    check(n == {'explained': 1, 'known': 1, 'real': 1, 'regression': 1, 'new': 2}, f'feedback counts ({n})')
    check(fs[0].severity == 'info' and 'the other game ended' in fs[0].text and fs[0].evidence['explained'], 'artefact: info with its reason shown')
    check(fs[1].severity == 'info' and 'known issue: docs say so' in fs[1].text and fs[1].evidence['known'], 'known: labelled, not alerted')
    check(fs[2].severity == 'error' and fs[2].evidence['triaged'] == 'real', 'real: kept and labelled')
    check(fs[3].severity == 'error' and fs[3].evidence['regression'] and 'REGRESSION' in fs[3].text, 'fixed: a finding of its key is a regression')
    check(fs[4].severity == 'warning' and fs[5].severity == 'warning', 'open or unseen keys: untouched')
    # regression checks
    for name, verdict in (('pk-k', 'reproduced'), ('pk-r', 'not reproduced'), ('pk-f', 'reproduced')):
        (tmp / name / 'replay').mkdir(parents=True)
        (tmp / name / 'replay' / 'replay.json').write_text(json.dumps({'verdict': verdict}))
    rc = {r['key']: r for r in score.regression_checks(ent)}
    check(rc['k:1']['result'] == 'ok' and rc['r:1']['result'] == 'STOPPED' and rc['f:1']['result'] == 'REGRESSION' and 'a:1' not in rc and 'o:1' not in rc, f'regression: {[(k, r["result"]) for k, r in rc.items()]}')
    ent2 = dict(ent, **{'k:1': dict(ent['k:1'], packet=str(tmp / 'none'))})
    check({r['key']: r for r in score.regression_checks(ent2)}['k:1']['result'] == 'not-run', 'regression: no replay verdict yet is not-run')
    # a round on disk
    rd = tmp / 'round1'
    rd.mkdir()
    rows = [{'name': 's1', 'seconds': 120, 'detectors': {'solo': {'stall': {'explained': 2}}}, 'place': {'to': 'X'}}]
    finds = [{'session': 's1', 'key': 'a:1', 'kind': 'log', 'severity': 'warning', 'side': 'solo', 't': 1}, {'session': 's1', 'key': 'k:1', 'kind': 'give', 'severity': 'error', 'side': 'A', 't': 2},
             {'session': 's1', 'key': 'r:1', 'kind': 'stall', 'severity': 'error', 'side': 'solo', 't': 3}, {'session': 's1', 'key': 'o:1', 'kind': 'stall', 'severity': 'warning', 'side': 'solo', 't': 4}]
    (rd / 'result.json').write_text(json.dumps({'sessions': rows, 'findings': finds, 'usd_spent': 0.02}))
    card = score.score_round('round-1', [rd], ent, with_maps=False)
    d = card['detectors']
    check(d['log']['explained'] == 1 and d['give']['known'] == 1 and d['stall']['real'] == 1 and d['stall']['unreviewed'] == 1 and d['stall']['explained_by_detector'] == 2, f'scorecard per detector ({d})')
    check(card['total']['raised'] == 4 and abs(card['minutes'] - 2.0) < 1e-6 and card['usd'] == 0.02 and card['placed_sessions'] == 1, f'scorecard totals ({card["total"]}, {card["minutes"]} min)')
    check(abs(d['log']['false_alarm_rate'] - 1.0) < 1e-6 and 0 < d['stall']['false_alarm_rate'] < 1, 'false-alarm rate = explained over raised')
    led = tmp / 'ledger.jsonl'
    score.append_ledger(led, card)
    score.append_ledger(led, dict(card, round='round-2', kind='passive'))
    cards = score.read_ledger(led)
    tt = score.trend_table(cards)
    check(len(cards) == 2 and '| round-1 | hunt |' in tt and '| round-2 | passive |' in tt and '| round-1 | log |' in tt, 'ledger: appended lines, the trend table shows the rounds side by side')
    # table.json shape (an analysis folder)
    ad = tmp / 'analysis'
    ad.mkdir()
    (ad / 'table.json').write_text(json.dumps({'rows': [{'name': 's1'}], 'findings': [['s1', {'key': 'a:1', 'kind': 'log', 'severity': 'warning', 'side': 'solo'}, 'new', None]]}))
    check(score.load_round(ad)[1][0]['session'] == 's1' and score.score_round('an', [ad], ent, with_maps=False)['detectors']['log']['explained'] == 1, 'an analysis folder (table.json) is a round too')
    # passive scan over a made-up run folder: a stall finding the registry has not seen is NEW; a seen one is not
    st = tb.steady(60)
    side = tb.make_side(tmp / 'run1', st, events=tb.events_for(st), present=tb.present_rows(3600, gaps={3000: 4500.0}), log='x\n', exit_code=143)
    (tmp / 'empty').mkdir()
    rows_, allf = score.passive_scan([tmp / 'run1', tmp / 'empty'], bughunt.Config(), None, None, {})
    check(rows_[0]['flagged_new'] == 1 and any((f.evidence or {}).get('passive_new') for _, f in allf), f'passive: an unseen key is flagged NEW ({rows_})')
    check(rows_[1].get('skipped'), 'passive: a folder with nothing to read is a skipped row, not a stop')
    key = next(f.key for _, f in allf if f.kind == 'stall' and f.severity != 'info')
    rows2, allf2 = score.passive_scan([tmp / 'run1'], bughunt.Config(), None, None, {key: {'status': 'artefact', 'note': 'machine'}})
    check(rows2[0]['flagged_new'] == 0 and rows2[0]['findings'] == 0 and rows2[0]['explained'] >= 1, 'passive: a triaged key is explained, not new')
    pc = score.passive_card('p', rows_, allf, {})
    check(pc['kind'] == 'passive' and pc['total']['raised'] >= 1 and pc['flagged_new'] == 1, 'passive_card: a ledger line of the same shape')
    # a pilot run folder of another lane names its game run folder (summary.json copy + run): the present trace comes with it
    gr = tmp / 'copy' / 'runs' / 'r9'
    gr.mkdir(parents=True)
    (gr / 'present.csv').write_text(tb.present_rows(3600, gaps={3000: 4500.0}))
    pr = tmp / 'lane' / 'r9'
    tb.put(pr / 'live' / 'state.jsonl', ''.join(json.dumps(x) + '\n' for x in st))   # the flat layout of a pilot run folder (live/, summary.json), no game/ or pilot/ beside it
    tb.put(pr / 'run.log', 'x\n')
    (pr / 'summary.json').write_text(json.dumps({'copy': str(tmp / 'copy'), 'run': 'r9'}))
    check(bughunt.load_side(pr).game == gr and bughunt.load_side(pr).present, 'load_side: the game run folder a summary.json names gives the present trace')
    check(bughunt.companion_game(tmp / 'run1') is None, 'companion_game: none without a summary.json')
    # a log-only folder (a debug-tools run: log, summary, exit; no state, no present) is read, not skipped
    lg = tmp / 'dbg'
    lg.mkdir()
    (lg / tb.LOG).write_text('[hos] fine\n')
    (lg / 'summary.txt').write_text(tb.OK_SUMMARY + '\n')
    (lg / 'exit.txt').write_text('143')
    rows3, _ = score.passive_scan([lg], bughunt.Config(), None, None, {})
    check(not rows3[0].get('skipped') and rows3[0]['read'] == ['log'] and rows3[0]['sides'] == 1, f'passive: a log-and-summary folder is read ({rows3})')
    # a placed row counts in the card
    rd2 = tmp / 'round2'
    rd2.mkdir()
    (rd2 / 'result.json').write_text(json.dumps({'sessions': [{'name': 'p1', 'seconds': 60, 'place': {'to': 'X', 'ok': True}}, {'name': 'p2', 'seconds': 60, 'place': {'to': 'Y', 'ok': False}}, {'name': 'n', 'seconds': 60}], 'findings': []}))
    c3 = score.score_round('r', [rd2], {}, with_maps=False)
    check(c3['placed_sessions'] == 2 and c3['placed_ok'] == 1 and '(1/2 placed)' in score.trend_table([c3]), 'scorecard: placed sessions and how many were placed')
    # the next round
    c1 = dict(card, maps={'Yard': 2})
    c2 = dict(card, round='r2', maps={'Cave': 1}, detectors={'stall': {'raised': 5, 'real': 0, 'known': 0, 'explained': 4, 'unreviewed': 1, 'explained_by_detector': 0, 'false_alarm_rate': 0.8},
                                                                 'log': {'raised': 1, 'real': 0, 'known': 0, 'explained': 1, 'unreviewed': 0, 'explained_by_detector': 0, 'false_alarm_rate': 1.0}})
    h = score.plan_hints([c1, c2], ['Yard', 'Cave', 'Tower', 'Pond'])
    check(h['places'] == ['Tower', 'Pond'] and [r['detector'] for r in h['review']] == ['stall'] and any('stall' in t for t in h['text']), f'plan_hints: uncovered places, a noisy detector ({h})')
    check(score.plan_hints([c1], ['Yard'])['text'][0] == 'every listed destination has some coverage' and not score.plan_hints([c1], ['Yard'])['places'], 'plan_hints: no place to add when all is covered')
    # the CLI
    import subprocess
    reg = tmp / 'reg.json'
    r = bugpacket.Registry(reg)
    r.register(F('stall', 'stall', 'c:1', 'error'), 'run-x', None)
    out = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'score.py'), str(rd), '--name', 'cli', '--ledger', str(tmp / 'l2.jsonl'), '--registry', str(reg), '--md', str(tmp / 'sc.md'), '--places', str(tmp / 'pl.json')],
                         capture_output=True, text=True) if (tmp / 'pl.json').write_text('["Yard"]') else None
    check(out.returncode == 0 and (tmp / 'sc.md').is_file() and '# Scorecard' in (tmp / 'sc.md').read_text() and len(score.read_ledger(tmp / 'l2.jsonl')) == 1, f'cli: scorecard, ledger and markdown written ({out.returncode} {out.stderr[-200:]})')
if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='test-score-') as t:
        run_in(Path(t))
    if FAILS:
        raise SystemExit(f'test_score: {len(FAILS)} of {CHECKS[0]} checks FAILED')
    print(f'test_score: all {CHECKS[0]} checks passed')
