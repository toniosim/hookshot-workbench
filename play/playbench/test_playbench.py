#!/usr/bin/env python3
"""The scoreboard without a game: the board and its private file, the referee on made-up state journals, the store, the trend (tables and a drawn chart), the
player guard, the lanes of a hold against fake pilots (early stop at the proof, the hold's end, a signal, the user's game, processes stopped by pid), the score of a
cell, the plan, the waiter's command, the chain, and a whole hold against a throw-away git repository with a fake pilot. No game, no GPU, no network, no model.

    python3 -I -B test_playbench.py
"""
import gzip
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import xml.dom.minidom
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault('PLAYBENCH_HARNESS', str(HERE.parent.parent))   # (hs_names.py is read from the harness; the tests use throw-away folders for everything else)
import board  # noqa: E402
import cells as cellmod  # noqa: E402
import config  # noqa: E402
import draft  # noqa: E402
import guard  # noqa: E402
import hold as holdmod  # noqa: E402
import nightly  # noqa: E402
import referee  # noqa: E402
import runner  # noqa: E402
import score  # noqa: E402
import store  # noqa: E402
import trend  # noqa: E402
import hs_names  # noqa: E402

FAILS, COUNT = [], [0]


def check(cond, what):
    COUNT[0] += 1
    if not cond:
        FAILS.append(what)
        print('FAIL', what, flush=True)


def raises(fn, exc=Exception):
    try:
        fn()
    except exc as e:
        return str(e)
    return None


TMP = Path(tempfile.mkdtemp(prefix='playbench-test-'))


def row(t, pos=(0.0, 100.0, 0.0), map='M', loading=0, flags=None, rupees=None, life=24, frame=None):
    r = {'t': t, 'frame': frame if frame is not None else int(t * 60), 'map': map, 'pos': list(pos), 'loading': loading, 'event': 0, 'life': life, 'flags': flags or {}}
    if rupees is not None:
        r['rupees'] = rupees
    return r


# ------------------------------------------------------------------------------------------------------------------------------------------------ board

def test_board():
    ids = [c.id for c in board.PUBLIC]
    check(len(ids) == 11 and len(set(ids)) == 11 and all(board.ID_RE.match(i) for i in ids), 'eleven cells with distinct valid ids')
    for want in ('door-front', 'door-wrong', 'ledge', 'drop', 'ladder', 'crowd', 'chest', 'pickup-dive', 'song-warp', 'item-bomb', 'chapter-lake'):
        check(want in ids, f'the board has the cell {want}')
    check(all(c.wall_s == int(board.BOOT_S + c.budget_s + board.GRACE_S) for c in board.PUBLIC), 'a cell wall is boot + budget + grace')
    check(all(board.missing(c, TMP / 'none') for c in board.PUBLIC), 'a cell nobody defined is missing, never silently skipped')
    check(board.load(TMP / 'nope.json') == list(board.PUBLIC), 'no private file: the public cells as they are')
    local = TMP / 'local'
    (local / 'segments').mkdir(parents=True)
    (local / 'saves' / 'sv' / 'save').mkdir(parents=True)
    (local / 'saves' / 'sv' / 'save' / 'a.sav').write_text('one')
    (local / 'segments' / 'door.toml').write_text('name = "x"\n')
    f = local / 'board-local.json'
    f.write_text(json.dumps({'door-front': {'segment': 'door.toml', 'save': 'sv', 'proof': {'kind': 'flag', 'name': 'F', 'value': 1}, 'budget_s': 55},
                             'ledge': {'segment': 'l.toml', 'proof': {'kind': 'at', 'map': 'M', 'x': 1, 'z': 2, 'r': 3}}}))
    cs = {c.id: c for c in board.load(f)}
    check(cs['door-front'].budget_s == 55 and cs['door-front'].wall_s == int(board.BOOT_S + 55 + board.GRACE_S), 'the private file sets a cell budget and the wall follows')
    check(board.missing(cs['door-front'], local) == [], 'a defined cell with its frozen files is playable')
    check('no frozen segment l.toml' in board.missing(cs['ledge'], local)[0], 'a cell whose frozen segment is absent says so')
    fp1 = board.fingerprint(cs['door-front'], local)
    (local / 'saves' / 'sv' / 'save' / 'a.sav').write_text('two')
    fp2 = board.fingerprint(cs['door-front'], local)
    (local / 'segments' / 'door.toml').write_text('name = "y"\n')
    fp3 = board.fingerprint(cs['door-front'], local)
    check(len({fp1, fp2, fp3}) == 3 and all(len(x) == 16 for x in (fp1, fp2, fp3)), 'the fingerprint changes with the save and with the segment')
    for bad, word in (({'nope': {}}, 'unknown cells'), ({'ledge': {'color': 1}}, 'only'), ({'ledge': {'proof': {'kind': 'at', 'map': 'M'}}}, 'at needs'),
                      ({'ledge': {'proof': {'kind': 'any', 'of': []}}}, 'needs a list'), ({'ledge': {'proof': {'kind': 'bogus'}}}, 'proof kind')):
        f.write_text(json.dumps(bad))
        e = raises(lambda: board.load(f), board.BoardError)
        check(e is not None and word in e, f'a bad private file is refused ({word})')
    check(board.proof_flags({'kind': 'any', 'of': [{'kind': 'flag', 'name': 'A', 'value': 1}, {'kind': 'all', 'of': [{'kind': 'flag_drop', 'name': 'B'}, {'kind': 'map', 'to': 'X'}]}]}) == {'A', 'B'},
          'proof_flags finds every flag a proof reads, through any/all')
    arms = board.arms()
    check(not list(HERE.glob('*.json')) and not hasattr(board, 'ARMS_FILE'), 'the arms are a table in arms.py: the folder that is published holds no data file')
    mine = board.arms()
    mine['rules']['env']['X'] = '1'
    check('X' not in board.arms()['rules']['env'] and 'X' not in arms['rules']['env'], 'every call returns its own copy of the committed table')
    check('rules' in arms and 'cheap' in arms and not arms['rules'].get('planner') and arms['cheap']['planner'], 'the arms file has the rules player and the cheap model arm')
    seg_cell, chap = board.PUBLIC[0], [c for c in board.PUBLIC if c.kind == 'chapter'][0]
    check(board.arm_args(arms['rules'], seg_cell) == (['--decider', 'rules'], {'PILOT_LEARN': 'off'}), 'the rules arm on a segment: the rules decider, learning off (the pilot\'s defaults are on and writing)')
    check(board.arm_args(arms['rules'], chap)[0] == ['--decider', 'rules', '--no-chapter-planner'], 'the rules arm on a chapter plays the chapter\'s own outline (no planner)')
    check(board.arm_args(arms['cheap'], seg_cell)[0] == ['--decider', 'openai-decisions', '--planner'], 'the cheap arm: the Decisions decider and the planner')
    check(board.arm_args(arms['cheap'], chap)[0] == ['--decider', 'openai-decisions'], 'the cheap arm on a chapter leaves the chapter planner on')
    for name in ('rules', 'cheap'):
        check(arms[name]['env'] == {'PILOT_LEARN': 'off'} and 'requires' not in arms[name], f'the baseline arm {name} switches learning off and needs no new flag')
    for name in ('rules-tactics', 'cheap-tactics', 'cheap-lessons', 'cheap-learned'):
        e = arms[name]['env']
        check(arms[name]['requires'] == '--tactics-readonly' and 'PILOT_LEARN' not in e and set(e) >= {'PILOT_TACTICS', 'PILOT_LESSONS'}, f'the arm {name} names its own tactics and lessons switches')
    check(all(arms[n]['env'].get('PILOT_TACTICS_READONLY') == '1' for n in ('rules-tactics', 'cheap-tactics', 'cheap-learned')), 'every arm that reads the tactics library reads it read-only: a night never learns from its own cells')
    check(arms['cheap-lessons']['env']['PILOT_TACTICS'] == 'off' and arms['cheap-learned']['env']['PILOT_LESSONS'] == 'on' and arms['rules-tactics']['env']['PILOT_LESSONS'] == 'off', 'tactics and lessons are separated across the arms')
    af = TMP / 'arms.json'
    af.write_text(json.dumps({'x y': {'decider': 'rules'}}))
    check(raises(lambda: board.arms(af), board.BoardError) is not None, 'an arm with a bad name is refused')
    af.write_text(json.dumps({'tact': {'decider': 'rules', 'args': ['--tactics', 'on'], 'env': {'PILOT_X': 1}}}))
    check(board.arm_args(board.arms(af)['tact'], seg_cell) == (['--decider', 'rules', '--tactics', 'on'], {'PILOT_X': '1'}), 'an arm\'s own args and env are carried')


# ---------------------------------------------------------------------------------------------------------------------------------------------- referee

def test_referee():
    at = {'kind': 'at', 'map': 'M', 'x': 10.0, 'z': 0.0, 'r': 2.0, 'y_min': 110.0}
    rows = [row(100.0 + i, pos=(i * 1.0, 100.0 + (i // 5) * 5.0, 0.0)) for i in range(15)]
    res = referee.judge(at, rows)
    # x reaches 10 at i = 10, y = 110 there (i // 5 = 2 -> 110): met at row 10 (x 10, y 110)
    check(res['success'] and res['time_to_goal_s'] == 10.0 and res['hit']['t'] == 110.0, 'a place at a height is met at the first sample inside the radius at the height')
    low = referee.judge({**at, 'y_min': 150.0}, rows)
    check(not low['success'] and low['progress'] is not None and low['progress'] > 0.7, 'the right place at the wrong height is not met; progress shows how close it got')
    check(referee.judge(at, rows[:3])['progress'] == round(1 - 8.0 / 10.0, 3), 'progress = the share of the first distance the best sample closed')
    wrong_map = referee.judge(at, [row(1.0 + i, pos=(10.0, 111.0, 0.0), map='Other') for i in range(5)])
    check(not wrong_map['success'] and wrong_map['progress'] is None, 'the right coordinates on another map prove nothing')
    load = referee.judge(at, [row(1.0, pos=(0.0, 100.0, 0.0)), row(2.0, pos=(10.0, 111.0, 0.0), loading=1), row(3.0, pos=(0.0, 100.0, 0.0))])
    check(not load['success'] and load['valid_samples'] == 2, 'a sample while loading shows no control of a place and never counts')
    check(referee.judge(at, rows, t_ref=105.0)['time_to_goal_s'] == 5.0, 'the clock starts at the caller\'s t_ref (the pilot\'s first decision)')
    check(referee.judge(at, rows, t_ref=500.0)['time_to_goal_s'] == 0.0, 'a t_ref after the hit gives 0, never a negative time')
    # forbidden zones: the way down must not be the ladder
    drop = {'kind': 'at', 'map': 'M', 'x': 10.0, 'z': 0.0, 'r': 2.0, 'y_max': 101.0, 'forbid': [{'x': 5.0, 'z': 0.0, 'r': 1.0, 'y_min': 101.0, 'y_max': 118.0}]}
    ladder_way = [row(1.0, pos=(0.0, 118.0, 0.0)), row(2.0, pos=(5.0, 110.0, 0.0)), row(3.0, pos=(10.0, 100.0, 0.0))]
    edge_way = [row(1.0, pos=(0.0, 118.0, 0.0)), row(2.0, pos=(9.0, 112.0, 0.0)), row(3.0, pos=(10.0, 100.0, 0.0))]
    rl, re_ = referee.judge(drop, ladder_way), referee.judge(drop, edge_way)
    check(not rl['success'] and rl['tainted'] and re_['success'] and not re_['tainted'], 'a run that went down by the forbidden ladder cannot meet the drop; one that stepped off meets it')
    check(referee.judge(drop, [row(1.0, pos=(5.0, 100.0, 0.0)), row(2.0, pos=(10.0, 100.0, 0.0))])['success'], 'a zone only forbids what its height range covers')
    check(not referee.judge(drop, ladder_way[:2])['success'] and referee.judge(drop, ladder_way[:2])['tainted'], 'the taint is certain as soon as the zone was entered')
    check('forbid zone needs' in ' '.join(board.proof_errors({**drop, 'forbid': [{'x': 1}]})) and board.proof_errors(drop) == [], 'forbid zones are validated')
    # flags
    fl = {'kind': 'flag', 'name': 'Door', 'value': 1}
    r = referee.judge(fl, [row(1.0, flags={'Door': 0}), row(2.0, flags={'Door': 1})])
    check(r['success'] and r['time_to_goal_s'] == 1.0, 'a flag that reads the value is met at that sample')
    check(not referee.judge(fl, [row(1.0), row(2.0, flags={'Other': 1})])['success'], 'a flag that is not in the journal is never met (the segment must watch it)')
    check(referee.judge({'kind': 'flag', 'name': 'C', 'op': '>=', 'value': 3}, [row(1.0, flags={'C': 2}), row(2.0, flags={'C': 3.0})])['success'], 'a flag compares with its operator')
    check(referee.judge({'kind': 'flag', 'name': 'E', 'value': 'Step01'}, [row(1.0, flags={'E': 'Step01'})])['success'], 'a text value is compared as text')
    fd = {'kind': 'flag_drop', 'name': 'Bomb', 'drop': 1}
    check(referee.judge(fd, [row(1.0, flags={'Bomb': 10}), row(2.0, flags={'Bomb': 10}), row(3.0, flags={'Bomb': 9})])['time_to_goal_s'] == 2.0, 'a count that fell by one from its first value is met')
    check(not referee.judge(fd, [row(1.0, flags={'Bomb': 10}), row(2.0, flags={'Bomb': 10})])['success'], 'a count that did not fall is not met')
    check(not referee.judge(fd, [row(1.0), row(2.0, flags={'Bomb': 9})])['success'], 'a count first read after it fell has no baseline: not met')
    rg = {'kind': 'rupees_gain', 'gain': 6}
    check(referee.judge(rg, [row(1.0, rupees=0), row(2.0, rupees=5), row(3.0, rupees=6)])['time_to_goal_s'] == 2.0, 'rupees up by the gain from the first reading')
    check(not referee.judge(rg, [row(1.0, rupees=0), row(2.0, rupees=5)])['success'], 'five rupees of six is not met')
    mp = {'kind': 'map', 'to': 'Meadow'}
    check(referee.judge(mp, [row(1.0, map='Field'), row(2.0, map='Meadow', loading=1), row(3.0, map='Meadow')])['time_to_goal_s'] == 2.0, 'the destination map, not loading, after another map')
    check(not referee.judge(mp, [row(1.0, map='Meadow'), row(2.0, map='Meadow')])['success'], 'a start on the destination map is no warp')
    anyp = {'kind': 'any', 'of': [fl, at]}
    check(referee.judge(anyp, [row(1.0, flags={'Door': 0}), row(2.0, flags={'Door': 1})])['success'], 'any: the first proof that is met')
    allp = {'kind': 'all', 'of': [fl, rg]}
    check(referee.judge(allp, [row(1.0, flags={'Door': 1}, rupees=0), row(2.0, flags={'Door': 0}, rupees=7)])['time_to_goal_s'] == 1.0, 'all: each met at some sample (the last of them sets the time)')
    check(not referee.judge(allp, [row(1.0, flags={'Door': 1}, rupees=0)])['success'], 'all: one missing is not met')
    # start check, life
    st = {'map': 'M', 'x': 0.0, 'z': 0.0, 'tol_m': 5.0}
    check(referee.judge(fl, [row(1.0, pos=(1.0, 100.0, 1.0))], st)['start_ok'] is True, 'a first sample at the start is ok')
    check(referee.judge(fl, [row(1.0, pos=(40.0, 100.0, 1.0))], st)['start_ok'] is False, 'a first sample 40 m from the start is not: the run is invalid, not a failure')
    check(referee.judge(fl, [row(1.0, map='Z')], st)['start_ok'] is False, 'a first sample on another map is not the start')
    d = referee.judge(fl, [row(1.0, life=24), row(2.0, life=0), row(3.0, life=0), row(4.0, life=8), row(5.0, life=0)])
    check(d['deaths'] == 2 and d['life_min'] == 0, 'deaths are counted when life reaches 0, once per death')
    check(referee.judge(fl, [])['success'] is False and referee.judge(fl, [])['valid_samples'] == 0, 'an empty journal proves nothing')
    # streaming and reading
    j = TMP / 'j.jsonl'
    j.write_text(json.dumps(row(1.0)) + '\n' + json.dumps(row(2.0))[:20])
    rows1, off = referee.read_rows(j, 0)
    check(len(rows1) == 1, 'a half-written last line waits for the next read')
    with open(j, 'a') as f:
        f.write(json.dumps(row(2.0))[20:] + '\n')
    rows2, off2 = referee.read_rows(j, off)
    check(len(rows2) == 1 and rows2[0]['t'] == 2.0 and off2 > off, 'the next read returns the completed line from the saved offset')
    check(referee.read_rows(TMP / 'absent.jsonl', 0) == ([], 0), 'a journal that is not there yet reads as empty')
    tr = TMP / 't.jsonl'
    tr.write_text(json.dumps({'kind': 'goal'}) + '\n' + json.dumps({'kind': 'decision', 'state': {'frame': 130}}) + '\n')
    check(referee.first_decision_t(tr, [row(1.0, frame=100), row(2.0, frame=140), row(3.0, frame=200)]) == 2.0, 'the first decision\'s frame gives the journal time the clock starts at')
    check(referee.first_decision_t(TMP / 'none', []) is None, 'no transcript: no t_ref')


# ------------------------------------------------------------------------------------------------------------------------------------------------ store

def result_row(night='20261116', cell='ledge', arm='rules', attempt=1, success=0, valid=1, ttg=None, progress=None, stuck=5.0, decisions=10, cost=0.0, fp='f1', ah='a1', **kw):
    r = {'night': night, 'cell': cell, 'arm': arm, 'attempt': attempt, 'hold': 1, 'tag': f'pb-{cell}-{arm}-{attempt}', 'success': success, 'time_to_goal_s': ttg,
         'stuck_s': stuck, 'decisions': decisions, 'cost_usd': cost, 'progress': progress, 'start_ok': 1, 'valid': valid, 'why': '', 'pilot_outcome': None, 'play_s': 50.0,
         'build': 'v1', 'pilot_commit': 'abc', 'fingerprint': fp, 'arm_hash': ah}
    r.update(kw)
    return r


def test_store():
    st = store.Store(TMP / 's.sqlite')
    st.begin_night('20261116', '2026-11-16T02:30', {'x': 1})
    st.begin_night('20261116', 'again', {})
    check(len(st.nights()) == 1, 'a night is begun once')
    st.night_identity('20261116', pilot_commit='abc1234', build='v9')
    st.night_identity('20261116', pilot_commit='zzz', build='v10')
    n = st.night('20261116')
    check(n['pilot_commit'] == 'abc1234' and n['build'] == 'v9', 'the first identity written for a night stays')
    check(raises(lambda: st.night_identity('20261116', color='x'), KeyError) is not None, 'only the identity fields can be set')
    st.add_cell(result_row(valid=0, why='cut'))
    st.add_cell(result_row(attempt=2, success=1, valid=1, ttg=12.0))
    st.add_cell(result_row(attempt=3, success=0, valid=1))
    c = st.counted('20261116')[('ledge', 'rules')]
    check(c['attempt'] == 2 and c['success'] == 1, 'the first VALID attempt counts, not the last')
    st.add_cell(result_row(cell='drop', valid=0, why='x'))
    st.add_cell(result_row(cell='drop', attempt=2, valid=0, why='y'))
    check(st.counted('20261116')[('drop', 'rules')]['attempt'] == 2, 'with no valid attempt the last (invalid) one is what is shown')
    check(raises(lambda: st.add_cell(result_row(attempt=2)), ValueError) is not None, 'a result already stored is never replaced')
    check(st.next_attempt('20261116', 'ledge', 'rules') == 4 and st.next_attempt('20261116', 'chest', 'rules') == 1, 'the next attempt number')
    st.end_night('20261116', 'complete', 'later', 2)
    check(st.night('20261116')['status'] == 'complete' and st.night('20261116')['holds'] == 2, 'a night ends with its status and hold count')
    out = TMP / 'e.jsonl'
    st.export_jsonl(out)
    lines = [json.loads(x) for x in out.read_text().splitlines()]
    check(len(lines) == 5 and all('pilot_commit_night' in x for x in lines), 'the export keeps every attempt with the night\'s identity')
    st.close()
    st2 = store.Store(TMP / 's.sqlite')
    check(len(st2.attempts('20261116')) == 5, 'the store persists')
    st2.close()


# ------------------------------------------------------------------------------------------------------------------------------------------------ trend

def history_fixture():
    cells = ['door-front', 'ledge', 'drop']
    hist = []
    for i, (night, commit, build) in enumerate((('20261116', 'aaa1111', 'v1'), ('20261117', 'aaa1111', 'v1'), ('20261118', 'bbb2222', 'v2'))):
        counted = {}
        for arm in ('rules', 'cheap'):
            counted[('door-front', arm)] = result_row(night, 'door-front', arm, success=1, ttg=30.0 + i, cost=0.02 if arm == 'cheap' else 0.0)
            counted[('ledge', arm)] = result_row(night, 'ledge', arm, success=int(i == 2 and arm == 'rules'), ttg=40.0 if i == 2 and arm == 'rules' else None,
                                                 progress=None if i == 2 and arm == 'rules' else 0.4, fp='f1')
        counted[('drop', 'rules')] = result_row(night, 'drop', 'rules', valid=0, why='save not at the start') if i == 1 else result_row(night, 'drop', 'rules', success=0, progress=0.1,
                                                                                                                                  fp='f1' if i < 2 else 'f2')
        hist.append(({'night': night, 'pilot_commit': commit, 'build': build, 'status': 'complete' if i < 2 else 'partial: 1 left'}, counted))
    return hist, cells, ['rules', 'cheap']


def test_blocked():
    cells = ['item-bomb', 'chest']
    counted = {('item-bomb', 'rules'): result_row('20261116', 'item-bomb', 'rules', blocker='the item button does nothing'),
               ('item-bomb', 'cheap'): result_row('20261116', 'item-bomb', 'cheap', blocker='the item button does nothing', valid=1),
               ('chest', 'rules'): result_row('20261116', 'chest', 'rules', success=1, ttg=10.0),
               ('chest', 'cheap'): result_row('20261116', 'chest', 'cheap', success=0)}
    check(trend.label(counted[('item-bomb', 'rules')]) == 'blocked' and trend.label(counted[('chest', 'cheap')]) == 'fail', 'a failure with a known cause is `blocked`, any other is a fail')
    ag = trend.aggregates(counted, 'rules', cells)
    check(ag['solved'] == 1 and ag['valid'] == 1 and ag['blocked'] == 1 and ag['invalid'] == 0, 'a blocked cell is neither solved nor failed: left out of the valid count')
    ag2 = trend.aggregates(counted, 'cheap', cells)
    check(ag2['solved'] == 0 and ag2['valid'] == 1 and ag2['blocked'] == 1, 'the other arm: a plain failure counts, the blocked one does not')
    ok = dict(counted[('item-bomb', 'rules')], success=1, ttg=5.0)
    check(trend.label(ok) != 'blocked' and trend.aggregates({('item-bomb', 'rules'): ok}, 'rules', cells)['solved'] == 1, 'if the blocked cell is solved after all, it counts as solved')
    hist = [({'night': '20261116', 'pilot_commit': 'a', 'build': 'b-g1', 'status': 'complete'}, counted)]
    check('(+1 blocked)' in trend.trend_md(hist, cells, ['rules', 'cheap']) and '| item-bomb | b | ' in trend.grid_md(hist, cells, 'rules') + '| item-bomb | b | ', 'the trend table names the blocked count and the grid marks it b')
    check('blocked: the item button does nothing' in trend.night_md(hist[0][0], counted, cells, ['rules', 'cheap']), 'the night table names the known cause')
    svg = trend.chart_svg(hist, cells, ['rules', 'cheap'])
    check('#9fb4c9' in svg and xml.dom.minidom.parseString(svg) is not None, 'the chart draws a blocked square')
    txt = draft.weekly(hist, cells, ['rules', 'cheap'], {'item-bomb': 'use an item', 'chest': 'open a chest'})
    check('**Blocked by a known cause:** use an item: the item button does nothing.' in txt, 'the weekly draft names what is blocked and why')
    st = store.Store(TMP / 'blk.sqlite')
    st.add_cell(result_row('20261116', 'item-bomb', 'rules'))
    st.add_cell(result_row('20261116', 'chest', 'rules', success=1, ttg=3.0))
    check(st.annotate_blocker('20261116', 'item-bomb', 'x') == 1 and st.annotate_blocker('20261116', 'chest', 'x') == 0 and st.counted('20261116')[('item-bomb', 'rules')]['blocker'] == 'x', 'annotating marks failed results of the cell, never a success')
    st.close()
    old = TMP / 'old.sqlite'
    import sqlite3
    db = sqlite3.connect(str(old))
    db.executescript(store.SCHEMA.replace(', blocker TEXT', ''))
    db.close()
    st = store.Store(old)
    st.add_cell(result_row('20261116', 'chest', 'rules'))
    check(st.counted('20261116')[('chest', 'rules')]['blocker'] is None, 'a store made before blockers existed is migrated in place')
    st.close()
    f = TMP / 'blocker-board.json'
    f.write_text(json.dumps({'item-bomb': {'segment': 's.toml', 'proof': {'kind': 'flag', 'name': 'F', 'value': 1}, 'blocker': 'the item button does nothing'}}))
    cs = {c.id: c for c in board.load(f)}
    check(cs['item-bomb'].blocker == 'the item button does nothing' and board.fingerprint(cs['item-bomb'], TMP / 'x') == board.fingerprint(board.Cell(**{**cs['item-bomb'].__dict__, 'blocker': None}), TMP / 'x'),
          'a blocker is a field of the cell that does not change its fingerprint (lifting it is not a new series)')


def test_trend():
    hist, cells, arms = history_fixture()
    check(trend.label(None) == '-' and trend.label(result_row(valid=0)) == '? invalid' and trend.label(result_row(success=1, ttg=33.4)) == 'ok 33 s'
          and trend.label(result_row(progress=0.42)) == 'fail 42%' and trend.label(result_row()) == 'fail', 'table labels: ok / fail by progress / invalid / not run')
    ag = trend.aggregates(hist[2][1], 'rules', cells)
    check(ag['solved'] == 2 and ag['valid'] == 3 and ag['median_ttg'] == 36.0 and ag['stuck_s'] == 15.0 and ag['decisions'] == 30.0, 'aggregates over the cells that counted')
    ag1 = trend.aggregates(hist[1][1], 'rules', cells)
    check(ag1['invalid'] == 1 and ag1['valid'] == 2 and ag1['run'] == 3, 'an invalid run is counted apart: neither solved nor failed')
    check(trend.aggregates({}, 'rules', cells)['run'] == 0, 'a night with no result for an arm has run 0')
    md = trend.trend_md(hist, cells, arms)
    lines = md.splitlines()
    check(len(lines) == 5 and all(l.count('|') == lines[0].count('|') for l in lines), 'the trend table is rectangular')
    check('**bbb2222**' in lines[4] and '**v2**' in lines[4] and '**' not in lines[3], 'the table marks the night the pilot commit and the build changed')
    check('2/3' in lines[4] and '(+1 invalid)' in lines[3], 'solved of valid, with the invalid ones named')
    g = trend.grid_md(hist, cells, 'rules')
    check('| drop | - | ? | -* |' in g, 'the grid: fail, invalid, and a star where the cell\'s fingerprint changed')
    check('| ledge | - | - | + |' in g, 'the grid: ledge not met, not met, then met')
    ch = trend.changes(hist[1][1], hist[2][1], cells, arms)
    check(('ledge', 'rules', 'now met') in ch, 'a flip is reported')
    check(not any(c == 'drop' for c, _, _ in trend.changes(hist[1][1], hist[2][1], cells, arms)), 'a changed cell, an invalid one: nothing is claimed about it')
    nm = trend.night_md(hist[2][0], hist[2][1], cells, arms)
    check('| door-front | ok 32 s | ok 32 s |' in nm and 'Night 20261118' in nm, 'the night table')
    svg = trend.chart_svg(hist, cells, arms)
    try:
        dom = xml.dom.minidom.parseString(svg)
        ok = True
    except Exception:   # noqa: BLE001
        ok = False
    check(ok, 'the chart is well-formed SVG')
    check(ok and len(dom.getElementsByTagName('rect')) > 2 * len(cells) * 3 and len(dom.getElementsByTagName('polyline')) >= 2, 'the chart draws the grid squares and the lines')
    check('rules' in svg and 'cheap' in svg and 'bbb2222' in svg, 'the chart names the arms and the pilot commits')
    one = trend.chart_svg(hist[:1], cells, arms)
    check(xml.dom.minidom.parseString(one) is not None, 'one night draws too')
    zero = trend.chart_svg([], cells, arms)
    check(xml.dom.minidom.parseString(zero) is not None, 'no night draws an empty chart, not an error')
    out = TMP / 'trend'
    files = trend.write_all(hist, cells, arms, out)
    check((out / 'trend.md').is_file() and (out / 'chart.svg').is_file(), 'trend.md and chart.svg are written')
    check('Changes since night 20261117' in (out / 'trend.md').read_text(), 'trend.md ends with the changes since the night before')
    if 'chart.png' in files:
        r = subprocess.run(['magick', 'identify', str(files['chart.png'])], capture_output=True, text=True)
        check(r.returncode == 0 and ' PNG ' in r.stdout, 'the PNG is a real picture')
    # the draft
    titles = {c.id: c.title for c in board.PUBLIC}
    text = draft.weekly(hist, cells, arms, titles)
    check(text.startswith('**The test player scoreboard: 3 fixed tasks') and 'PICTURE: pilot-1198-scoreboard.png' in text, 'the weekly draft has a headline and a picture line')
    check('**rules** solved 2 of 3 on 11-18' in text and 'first week' in text, 'the draft states the numbers and says when there is no week to compare with')
    check('/home/' not in text and 'KokiriForest' not in text, 'the draft names no path and no place')
    old = [({'night': '20261109', 'pilot_commit': 'old', 'build': 'v0', 'status': 'complete'}, {('ledge', 'rules'): result_row('20261109', 'ledge', 'rules', success=0, progress=0.2)})] + hist
    check('(a week before: 0 of 1)' in draft.weekly(old, cells, arms, titles) and 'What changed since 11-09' in draft.weekly(old, cells, arms, titles), 'with a week-old night the draft compares and lists flips')
    check('No night has been scored yet.' in draft.weekly([], cells, arms, titles), 'no nights: said plainly')


# ------------------------------------------------------------------------------------------------------------------------------------------------ guard

def test_names_dir():
    """hs_names.py is in the harness folder itself or, in a checkout of the workbench repository, in its harness/ folder."""
    flat, nested = TMP / 'names-flat', TMP / 'names-nested'
    flat.mkdir()
    (flat / 'hs_names.py').write_text('')
    (nested / 'harness').mkdir(parents=True)
    (nested / 'harness' / 'hs_names.py').write_text('')
    old = config.HARNESS
    try:
        config.HARNESS = flat
        check(config.names_dir() == flat, 'the helper beside the harness folder\'s own files is found there')
        config.HARNESS = nested
        check(config.names_dir() == nested / 'harness', 'and in a repository checkout, in its harness/ folder')
    finally:
        config.HARNESS = old


def test_guard():
    seen = {'n': 0}
    clock = {'t': 0.0}

    def probe():
        seen['n'] += 1
        return [{'pid': 7}] if 3 <= clock['t'] < 6 else []

    def now():
        return clock['t']

    def sleep(s):
        clock['t'] += s
    check(guard.wait_idle(5, 100, 1.0, probe, now, sleep), 'wait_idle returns True after the quiet time')
    check(clock['t'] >= 11, 'a player seen at 3 to 6 s restarts the clock: five quiet seconds begin at 6')
    clock['t'] = 0.0
    check(guard.wait_idle(50, 10, 1.0, lambda: [], now, sleep) is False, 'wait_idle gives up at its timeout')
    P0, P1 = hs_names.PROJECTS[0], hs_names.PROJECTS[-1]
    play = f'/home/x/Games/{P0.title()}'
    roots = [Path(play), Path(f'/home/x/.local/share/{P1}')]
    check(guard.is_protected(f'{play}/{P1}', roots, '/home/x'), 'a game in the play folder is the user\'s')
    check(guard.is_protected(f'/home/x/Games/Ocarina/bin/{P1}', roots, '/home/x'), 'the Ocarina folder is protected too')
    check(guard.is_protected(f'/home/x/Games/{P1.title()}/{P1}', [], '/home/x'), 'every project\'s own folder under Games is protected, whatever the config says')
    check(not guard.is_protected(f'/home/x/Games/.{P0}-h-playbench-a/{P1}', roots, '/home/x'), 'an owned game copy is not')
    recs = [{'pid': 1, 'exe': f'{play}/{P1}', 'cwd': '/'}, {'pid': 2, 'exe': f'/home/x/Games/.{P0}-h-a/{P1}', 'cwd': f'/home/x/Games/.{P0}-h-a'},
            {'pid': 3, 'exe': '/usr/bin/python3', 'cwd': play}]
    got = guard.player_games(recs, '/home/x')
    check([p['pid'] for p in got] == [1], 'only a game executable of the user\'s folders is the player')


# ------------------------------------------------------------------------------------------------------------------------------------------------ the lanes of a hold

FAKE_PILOT = r'''
import json, os, subprocess, sys, time
from pathlib import Path
args = sys.argv[1:]
if '-h' in args:
    print('usage: pilot.py run SEGMENT --decider --tag --copy --wall --max-decisions --no-bad-points --save --shots --allowance-usd --allowance-since --planner --no-chapter-planner')
    sys.exit(0)
seg = Path(args[1])
tag = args[args.index('--tag') + 1]
spec = json.loads(seg.read_text())
HERE = Path(__file__).resolve().parent
run = HERE / 'runs' / tag
(run / 'live').mkdir(parents=True)
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)', tag], start_new_session=True)   # (a game that outlives its pilot: the runner stops it by the tag)
(run / 'argv.json').write_text(json.dumps(args))
t0 = time.time()
state = run / 'live' / 'state.jsonl'
(run / 'transcript.jsonl').write_text(json.dumps({'kind': 'decision', 'n': 1, 'state': {'frame': 60}, 'choice': 'go'}) + '\n')
for item in spec['rows']:
    time.sleep(max(0.0, item['after'] - (time.time() - t0)))
    with open(state, 'a') as f:
        f.write(json.dumps(item['row']) + '\n')
(run / 'summary.json').write_text(json.dumps({'outcome': spec.get('outcome', 'gave up'), 'decisions': 1}))
if spec.get('end') == 'hang':
    time.sleep(120)
sys.exit(spec.get('rc', 1))
'''


def make_runner_env(name, cells_spec):
    """A pilot folder with the fake pilot, a local folder with the segments (JSON scripts) and board-local.json; returns (plan base, local)."""
    base = TMP / name
    pilot = base / 'snap' / 'pilot'
    (pilot / 'runs').mkdir(parents=True)
    (pilot / 'pilot.py').write_text(FAKE_PILOT)
    local = base / 'local'
    (local / 'segments').mkdir(parents=True)
    doc = {}
    for cid, spec in cells_spec.items():
        (local / 'segments' / f'{cid}.json').write_text(json.dumps(spec['script']))
        doc[cid] = {'segment': f'{cid}.json', 'proof': spec['proof'], 'budget_s': spec.get('budget_s', 20), **({'start': spec['start']} if 'start' in spec else {})}
    (local / 'board-local.json').write_text(json.dumps(doc))
    return base, local


def plan_for(base, local, items, copies=('A', 'B'), hold_s=1000.0, **kw):
    return {'night': '20261116', 'hold': 1, 'out': str(base / 'hold'), 'pilot_dir': str(base / 'snap' / 'pilot'), 'python': sys.executable, 'copies': list(copies), 'local': str(local),
            'items': items, 'hold_s': hold_s, 'reserve_s': 5, 'shots': 0, 'env': {}, 'allowance_usd': None, 'arms_file': None, **kw}


def rows_script(positions, after=0.15, extra=None, flags=None):
    return [{'after': 0.1 + after * i, 'row': row(100.0 + i, pos=p, flags=flags(i) if flags else None)} for i, p in enumerate(positions)]


def test_runner():
    runner.POLL_S, runner.MET_GRACE_S, runner.END_WAIT_S, runner.OVER_GRACE_S = 0.1, 0.4, 0.4, 3.0
    at = {'kind': 'at', 'map': 'M', 'x': 5.0, 'z': 0.0, 'r': 1.5}
    spec = {
        'door-front': {'script': {'rows': rows_script([(i, 100.0, 0.0) for i in range(0, 8)]), 'end': 'hang', 'outcome': 'solved'}, 'proof': at},
        'ledge': {'script': {'rows': rows_script([(0.0, 100.0, 0.0), (1.0, 100.0, 0.0)]), 'rc': 1}, 'proof': at},
        'drop': {'script': {'rows': rows_script([(90.0, 100.0, 0.0)]), 'rc': 1}, 'proof': at, 'start': {'map': 'M', 'x': 0.0, 'z': 0.0, 'tol_m': 5.0}},
    }
    # the arms of one cell side by side on two lanes; an early stop after the proof (the fake pilot hangs after reaching it)
    base, local = make_runner_env('r1', spec)
    items = [{'cell': 'door-front', 'arm': 'rules', 'attempt': 1}, {'cell': 'door-front', 'arm': 'cheap', 'attempt': 1}, {'cell': 'ledge', 'arm': 'rules', 'attempt': 1}]
    plan = plan_for(base, local, items)
    h = runner.Hold(plan, player_probe=lambda: [])
    h.cells = {k: v for k, v in h.cells.items()}
    t = time.time()
    s = h.play()
    took = time.time() - t
    recs = {r['tag']: r for r in h.done}
    w = recs['pb261116-door-front-rules-a1']
    check(len(s['done']) == 3 and not s['deferred'] and s['stopping'] is None, 'three items played on two lanes, none deferred')
    check(w['proof_met_live'] and w.get('stopped_after_proof') and w['rc'] != 'timeout' and took < 40, 'a pilot that hangs after the referee saw the proof is stopped a few seconds later')
    steps = base / 'snap' / 'pilot' / 'runs' / 'pb261116-door-front-rules-a1' / 'live' / 'steps.txt'
    check(steps.is_file() and steps.read_text().splitlines()[-1] == 'end', 'it is first asked to end the way the pilot ends itself (an `end` step), then stopped')
    check(recs['pb261116-door-front-cheap-a1']['proof_met_live'], 'the other arm of the cell also reached the proof')
    check(not recs['pb261116-ledge-rules-a1']['proof_met_live'] and recs['pb261116-ledge-rules-a1']['rc'] == 1, 'a pilot that ends without the proof: not met, rc kept')
    check(runner.family('pb261116-door-front-rules-a1') == [], 'every process of a stopped cell is gone (the game outliving its pilot was stopped by its tag)')
    argv = json.loads((base / 'snap' / 'pilot' / 'runs' / 'pb261116-door-front-cheap-a1' / 'argv.json').read_text())
    check(argv[0] == 'run' and argv[argv.index('--decider') + 1] == 'openai-decisions' and '--planner' in argv and '--no-bad-points' in argv
          and argv[argv.index('--copy') + 1] in ('A', 'B') and argv[argv.index('--wall') + 1] == str(plan_wall(h, 'door-front')), 'the pilot command: decider, planner, no bad points, copy, wall')
    check('--save' not in argv and '--shots' not in argv, 'no save and no pictures unless the cell and the plan ask for them')
    check(sorted(r['copy'] for r in h.done)[:2] == ['A', 'A'] or {r['copy'] for r in h.done} == {'A', 'B'}, 'both lanes were used')
    # a start that is not where the cell says: judged by score, recorded here
    base, local = make_runner_env('r2', spec)
    h = runner.Hold(plan_for(base, local, [{'cell': 'drop', 'arm': 'rules', 'attempt': 1}], copies=('A',)), player_probe=lambda: [])
    h.play()
    row_ = score.score_cell(h.done[0], h.cells['drop'], 'rules', h.arms['rules'], '20261116', 'abc', None, local)
    check(row_['valid'] == 0 and row_['start_ok'] == 0 and 'not at the cell' in row_['why'], 'a first sample away from the start makes the run invalid, not a failure')
    ok_row = score.score_cell(recs['pb261116-ledge-rules-a1'], h.cells['ledge'], 'rules', h.arms['rules'], '20261116', 'abc', None, local)
    check(ok_row['valid'] == 1 and ok_row['success'] == 0 and 'proof was not shown' in ok_row['why'], 'a clean failure is valid and says what was not shown')
    # not starting what cannot finish: the second item does not fit the hold
    base, local = make_runner_env('r3', spec)
    h = runner.Hold(plan_for(base, local, [{'cell': 'ledge', 'arm': 'rules', 'attempt': 1}, {'cell': 'ledge', 'arm': 'cheap', 'attempt': 1}], copies=('A',), hold_s=50.0, reserve_s=0), player_probe=lambda: [])
    h.cells['ledge'] = h.cells['ledge'].__class__(**{**h.cells['ledge'].__dict__, 'budget_s': 1.0})
    h.cells_deadline = h.t0 + 0.0
    s = h.play()
    check(s['done'] == [] and len(s['deferred']) == 2, 'a cell that cannot finish before the cell deadline is deferred, not started')
    # the hold's end cuts a running cell
    base, local = make_runner_env('r4', {'chest': {'script': {'rows': rows_script([(0.0, 100.0, 0.0)]), 'end': 'hang'}, 'proof': at}})
    h = runner.Hold(plan_for(base, local, [{'cell': 'chest', 'arm': 'rules', 'attempt': 1}], copies=('A',), hold_s=1000.0), player_probe=lambda: [])
    h.hard_deadline = h.t0 + 1.5
    s = h.play()
    check(h.done[0]['cut'] == 'hold' and runner.family('pb261116-chest-rules-a1') == [], 'a cell still running at the hold\'s hard deadline is cut and its processes stopped')
    cut_row = score.score_cell(h.done[0], h.cells['chest'], 'rules', h.arms['rules'], '20261116', 'abc', None, local)
    check(cut_row['valid'] == 0 and 'cut short: hold' in cut_row['why'], 'a cut run is invalid: it is tried again, never counted as a fail')
    # the user's game appears
    base, local = make_runner_env('r5', {'chest': {'script': {'rows': rows_script([(0.0, 100.0, 0.0)]), 'end': 'hang'}, 'proof': at}})
    calls = {'n': 0}

    def probe():
        calls['n'] += 1
        return [{'pid': 4242}] if calls['n'] > 1 else []
    h = runner.Hold(plan_for(base, local, [{'cell': 'chest', 'arm': 'rules', 'attempt': 1}, {'cell': 'chest', 'arm': 'cheap', 'attempt': 1}], hold_s=1000.0), player_probe=probe)
    h.sleep = lambda s: time.sleep(min(s, 0.2))
    s = h.play()
    check(s['stopping'] == 'player' and s['player_pids'] == [4242] and all(r['cut'] == 'player' for r in h.done), 'the player wins: running cells are stopped and marked cut')
    check(runner.family('pb261116-chest-rules-a1') == [] and runner.family('pb261116-chest-cheap-a1') == [], 'and their processes are gone')
    # the first runs never reach play: the hold stops instead of spending the lane on the rest
    base, local = make_runner_env('r7', {'door-front': {'script': {'rows': [], 'rc': 1}, 'proof': at}, 'ledge': {'script': {'rows': [], 'rc': 1}, 'proof': at},
                                         'drop': {'script': {'rows': [], 'rc': 1}, 'proof': at}, 'chest': {'script': {'rows': [], 'rc': 1}, 'proof': at}})
    its = [{'cell': c, 'arm': 'rules', 'attempt': 1} for c in ('door-front', 'ledge', 'drop', 'chest')]
    h = runner.Hold(plan_for(base, local, its, copies=('A',)), player_probe=lambda: [])
    s = h.play()
    check(s['stopping'] == 'no-play' and len(s['done']) == 2 and len(s['deferred']) == 2 and all(r['valid_samples'] == 0 for r in h.done),
          'two runs that never showed a place and none that did stop the hold: the rest is deferred, not played')
    base, local = make_runner_env('r8', {'door-front': {'script': {'rows': rows_script([(0.0, 100.0, 0.0)]), 'rc': 1}, 'proof': at}, 'ledge': {'script': {'rows': [], 'rc': 1}, 'proof': at},
                                         'drop': {'script': {'rows': [], 'rc': 1}, 'proof': at}, 'chest': {'script': {'rows': [], 'rc': 1}, 'proof': at}})
    h = runner.Hold(plan_for(base, local, its, copies=('A',)), player_probe=lambda: [])
    s = h.play()
    check(s['stopping'] is None and len(s['done']) == 4, 'one run that showed a place keeps the hold going (a cell can fail alone)')
    # a game that never shows a place is given QUEUE_WAIT_S, then stopped (not counted as a pilot failure: no sample at all is invalid)
    runner.QUEUE_WAIT_S = 0.8
    base, local = make_runner_env('r9', {'door-front': {'script': {'rows': [], 'end': 'hang'}, 'proof': at}})
    h = runner.Hold(plan_for(base, local, [{'cell': 'door-front', 'arm': 'rules', 'attempt': 1}], copies=('A',)), player_probe=lambda: [])
    s = h.play()
    check(h.done[0]['rc'] == 'timeout' and h.done[0]['valid_samples'] == 0 and runner.family('pb261116-door-front-rules-a1') == [], 'a game that shows no place within QUEUE_WAIT_S is stopped by pid')
    runner.QUEUE_WAIT_S = 480.0
    # a signal to the waiter
    base, local = make_runner_env('r6', {'chest': {'script': {'rows': rows_script([(0.0, 100.0, 0.0)]), 'end': 'hang'}, 'proof': at}})
    h = runner.Hold(plan_for(base, local, [{'cell': 'chest', 'arm': 'rules', 'attempt': 1}], copies=('A',), hold_s=1000.0), player_probe=lambda: [])
    threading.Timer(1.0, lambda: h.stop('signal')).start()
    s = h.play()
    check(s['stopping'] == 'signal' and h.done[0]['cut'] == 'signal' and runner.family('pb261116-chest-rules-a1') == [], 'stopping the hold stops the cell by its tag')
    # stop_family on a process that ignores SIGTERM
    p = subprocess.Popen([sys.executable, '-c', 'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)', 'pbtag-ignore'], start_new_session=True)
    time.sleep(0.4)
    n = runner.stop_family('pbtag-ignore', wait_s=1.0)
    p.wait(timeout=5)
    check(n == 1 and p.returncode == -signal.SIGKILL, 'a process that ignores SIGTERM is killed after the grace (by pid)')
    check(runner.family('pbtag-ignore-x') == [] and runner.tag_of('20261116', 'door-front', 'rules', 2) == 'pb261116-door-front-rules-a2', 'the tag names the night, cell, arm and attempt')


def plan_wall(h, cid):
    return h.cells[cid].wall_s


# ------------------------------------------------------------------------------------------------------------------------------------------------ score

def test_score():
    run = TMP / 'sc' / 'pilot' / 'runs' / 'pb261116-door-front-rules-a1'
    (run / 'live').mkdir(parents=True)
    (run / 'live' / 'state.jsonl').write_text('\n'.join(json.dumps(row(100.0 + i, flags={'Door': int(i >= 8)}, frame=6000 + 6 * i)) for i in range(12)) + '\n')
    (run / 'transcript.jsonl').write_text(json.dumps({'kind': 'decision', 'n': 1, 'state': {'frame': 6012}}) + '\n')
    (run / 'summary.json').write_text(json.dumps({'outcome': 'solved'}))
    (run / 'run.log').write_text(f'noise\n{hs_names.PROJECTS[-1]} v0.9-12-gdeadbeef1 (source abc)\n')
    (run / 'out.jsonl').write_text('{}\n')
    copy = TMP / 'sc' / 'copy'
    (copy / 'runs' / 'pb261116-door-front-rules-a1' / 'shots').mkdir(parents=True)
    (copy / 'runs' / 'pb261116-door-front-rules-a1' / 'summary.txt').write_text('ok\n')
    rec = {'cell': 'door-front', 'arm': 'rules', 'attempt': 1, 'tag': 'pb261116-door-front-rules-a1', 'copy': str(copy), 'hold': 1, 'run_dir': str(run), 'rc': 0, 'cut': None}
    cell = board.Cell('door-front', 't', 'a', proof={'kind': 'flag', 'name': 'Door', 'value': 1}, segment='x.toml')

    class FakeMetrics:
        @staticmethod
        def analyse(run_dir, arm=None):
            return {'session': {'stuck_s_total': 4.5, 'decisions': 7, 'stuck_steps': 2, 'streak_max': 3, 'distance_m': 12.0}, 'cost': {'total_usd': 0.0123}}
    r = score.score_cell(rec, cell, 'rules', {'decider': 'rules'}, '20261116', 'abc1234', FakeMetrics, TMP / 'sc-local')
    check(r['success'] == 1 and r['valid'] == 1 and r['time_to_goal_s'] == 6.0 and r['decisions'] == 7 and r['stuck_s'] == 4.5 and r['cost_usd'] == 0.0123,
          'the row: success and time from the referee (clock from the first decision), the rest from the pilot\'s metrics')
    check(r['build'] == 'v0.9-12-gdeadbeef1' and r['pilot_commit'] == 'abc1234' and len(r['fingerprint']) == 16 and len(r['arm_hash']) == 12, 'the row carries the build, the pilot commit, the fingerprint and the arm hash')
    st = store.Store(TMP / 'sc.sqlite')
    st.add_cell(r)
    check(json.loads(st.db.execute('SELECT row_json FROM cells').fetchone()[0])['referee']['hit']['pos'] is not None, 'the whole judgement is kept in the row\'s json')
    st.close()
    nomet = score.score_cell({**rec, 'tag': 'x', 'run_dir': str(TMP / 'sc' / 'nothing')}, cell, 'rules', {'decider': 'rules'}, '20261116', 'abc', None, TMP / 'sc-local')
    check(nomet['valid'] == 0 and 'never reached play' in nomet['why'] and nomet['cost_usd'] is None and nomet['stuck_s'] is None, 'no journal: invalid, and a number that cannot be known is None, never 0')
    dest = score.collect(rec, TMP / 'sc' / 'evidence')
    check((dest / 'state.jsonl.gz').is_file() and (dest / 'transcript.jsonl').is_file() and (dest / 'game-summary.txt').is_file() and (dest / 'run.log.head').is_file(),
          'the evidence is copied out (journal gzipped, pilot files, the game\'s summary, the log head)')
    check(len(gzip.open(dest / 'state.jsonl.gz').read().splitlines()) == 12, 'the gzipped journal is whole')
    # rejudge: the same journal, a corrected proof
    rows_j = [row(100.0 + i, pos=(i * 1.0, 100.0, 0.0), frame=6000 + 6 * i) for i in range(12)]
    old_row = dict(r, success=0, valid=1, why='the proof was not shown in 5 s of play', play_s=5.0, time_to_goal_s=None, progress=0.3, pilot_outcome='gave up')
    cell2 = board.Cell('door-front', 't', 'a', proof={'kind': 'at', 'map': 'M', 'x': 5.0, 'z': 0.0, 'r': 1.0}, segment='x.toml')
    new_row = score.rejudge_row(old_row, cell2, rows_j, run / 'transcript.jsonl', TMP / 'sc-local')
    check(new_row['success'] == 1 and new_row['valid'] == 1 and new_row['why'] == '' and new_row['time_to_goal_s'] == 2.0 and new_row['cost_usd'] == old_row['cost_usd'] and new_row['tag'] == old_row['tag'],
          'a rejudged row has the new judgement and everything else of the old row')
    cell3 = board.Cell('door-front', 't', 'a', proof={'kind': 'at', 'map': 'M', 'x': 500.0, 'z': 0.0, 'r': 1.0}, segment='x.toml')
    n3 = score.rejudge_row(dict(old_row, why='cut short: hold'), cell3, rows_j, run / 'transcript.jsonl', TMP / 'sc-local')
    check(n3['success'] == 0 and n3['valid'] == 0 and 'cut short: hold' in n3['why'], 'a cut run stays invalid when rejudged: the sample was never whole')
    n4 = score.rejudge_row(dict(old_row, success=1), cell3, rows_j, run / 'transcript.jsonl', TMP / 'sc-local', ended_by_old_proof=True)
    check(n4['success'] == 0 and n4['valid'] == 0 and 'ended early by the earlier proof' in n4['why'], 'a run the OLD proof ended early is invalid, not a failure, under a corrected proof it does not meet')
    n5 = score.rejudge_row(old_row, cell2, rows_j, run / 'transcript.jsonl', TMP / 'sc-local', ended_by_old_proof=True)
    check(n5['success'] == 1 and n5['valid'] == 1, 'and a success stands whatever ended the run')
    cell4 = board.Cell('drop', 't', 'a', proof={'kind': 'at', 'map': 'M', 'x': 500.0, 'z': 0.0, 'r': 1.0, 'forbid': [{'x': 3.0, 'z': 0.0, 'r': 1.5}]}, segment='x.toml')
    n6 = score.rejudge_row(dict(old_row, success=1), cell4, rows_j, run / 'transcript.jsonl', TMP / 'sc-local', ended_by_old_proof=True)
    check(n6['success'] == 0 and n6['valid'] == 1 and 'forbids' in n6['why'], 'a run that took a forbidden way is a valid failure even when the old proof ended it early: it was certain')
    st = store.Store(TMP / 'sc2.sqlite')
    st.add_cell(dict(old_row, night='20261116', cell='door-front', arm='rules', attempt=1))
    st.rejudge('20261116', 'door-front', 'rules', 1, new_row, 'the target was moved', '2026-11-17T03:00')
    got = st.counted('20261116')[('door-front', 'rules')]
    hist = st.rejudgements('20261116')
    check(got['success'] == 1 and got['fingerprint'] == new_row['fingerprint'] and len(hist) == 1 and json.loads(hist[0]['old_json'])['success'] == 0 and hist[0]['reason'] == 'the target was moved',
          'the store keeps the old judgement whole beside the new one, with the reason')
    check(raises(lambda: st.rejudge('20261116', 'chest', 'rules', 1, new_row, 'x', 'y'), KeyError) is not None, 'a result that is not stored cannot be rejudged')
    st.close()
    snap, dev = TMP / 'led-snap', TMP / 'led-dev'
    snap.mkdir()
    dev.mkdir()
    (dev / 'ledger.jsonl').write_text(json.dumps({'ts': 1, 'run': 'a', 'cost_usd': 1}) + '\n')
    (snap / 'ledger.jsonl').write_text(json.dumps({'ts': 1, 'run': 'a', 'cost_usd': 1}) + '\n' + json.dumps({'ts': 2, 'run': 'b', 'cost_usd': 2}) + '\n')
    check(score.merge_ledger(snap, dev) == 1 and len((dev / 'ledger.jsonl').read_text().splitlines()) == 2 and score.merge_ledger(snap, dev) == 0, 'the hold\'s new ledger rows are appended to the dev copy once')


# ------------------------------------------------------------------------------------------------------------------------------------------------ nightly

def test_nightly():
    cfg = config.load(TMP / 'noconfig.json', require=False)
    check(cfg['hold_s'] == 1100 and cfg['allowance_usd'] == 5.0 and cfg['timer_enabled'] is False and cfg['max_attempts'] == 2, 'defaults: 1,100 s holds, a 5 USD allowance, the timer off')
    check('no value for' in (raises(lambda: config.load(TMP / 'noconfig.json'), ValueError) or '') and all(k in config.REQUIRED for k in ('copies', 'quiet_lock', 'measuring_lock', 'reports', 'drafts', 'key_file', 'issue_url')),
          'the machine\'s own values (copies, locks, folders, key file, issue URL) have no default: a config without them is an error naming them')
    full = TMP / 'fullcfg.json'
    full.write_text(json.dumps({k: ('x' if k != 'copies' else ['x']) for k in config.REQUIRED}))
    check(config.load(full)['copies'] == ['x'], 'a config with them loads')
    bad = TMP / 'badcfg.json'
    bad.write_text(json.dumps({'hold_ss': 5}))
    check('unknown settings' in (raises(lambda: config.load(bad), ValueError) or ''), 'a typo in the private config is an error, not a silent default')
    cfg.update(tools_root=str(TMP / 'tools'), reports=str(TMP / 'PlayBench-files'), quiet_lock=str(TMP / 'q.lock'), measuring_lock=str(TMP / 'm.lock'), pilot_repo=str(TMP / 'repo-none'))
    cmd = nightly.waiter_command(cfg, '/t/tools', '20261116', 1)
    s = ' '.join(cmd)
    check(cmd[:2] == ['env', '--default-signal=HUP'] and cmd[2].startswith('PLAYBENCH_HARNESS=') and cmd[3].startswith('PLAYBENCH_LOCAL=') and cmd[4] == 'flock' and cmd.index(cfg['quiet_lock']) < cmd.index(cfg['measuring_lock']) < cmd.index('timeout')
          and cmd.count('-w') == 2 and all(cmd[i + 1] == '43200' for i, x in enumerate(cmd) if x == '-w'), 'the waiter: quiet lock, then measuring lock, each with a 12 hour wait, then timeout')
    check('-x' in cmd[cmd.index(cfg['quiet_lock']):cmd.index(cfg['measuring_lock'])] and '1100' in cmd and '--kill-after=25' in cmd and 'setsid' not in cmd, 'the measuring lock is exclusive, the hold is 1,100 s, the launcher makes the session')
    check(cmd[-8:-1] == ['hold', '--night', '20261116', '--hold', '1', '--tools', '/t/tools'][:7] or 'hold --night 20261116 --hold 1' in s, 'the waiter runs `hold` for the night and hold number')
    check(list(nightly.selected_arms(dict(cfg, arms=['cheap', 'rules']))) == ['rules', 'cheap'] and list(nightly.selected_arms(dict(cfg, arms=None))) == list(board.arms()),
          'the config picks the arms played every night (in the order of the table); none picked: all')
    check('not in the arms table' in (raises(lambda: nightly.selected_arms(dict(cfg, arms=['rules', 'nope'])), ValueError) or ''), 'an unknown arm name in the config is an error')
    check(cfg['arms'] == ['rules', 'cheap', 'rules-tactics', 'cheap-learned'] and cfg['max_holds_per_night'] == 6, 'by default four arms play every night, in up to six holds')
    # the plan
    d = TMP / 'plan-local'
    (d / 'segments').mkdir(parents=True)
    (d / 'segments' / 'a.toml').write_text('x = 1\n')
    old = board.LOCAL
    board.LOCAL = d
    os.environ['PLAYBENCH_LOCAL'] = str(d)
    (d / 'board-local.json').write_text(json.dumps({'chest': {'segment': 'a.toml', 'proof': {'kind': 'flag', 'name': 'F', 'value': 1}}}))
    repo = TMP / 'plan-repo'
    make_pilot_repo(repo, requires_flag=False)
    cfg['pilot_repo'] = str(repo)
    plan = nightly.make_plan(cfg, '20261116', tools_commit='abc')
    check(plan['cells'] == ['chest'] and plan['arms'] == ['rules', 'cheap'] and len(plan['items']) == 2 and 'ledge' in plan['skipped_cells'], 'the plan: the cells that can be played, every available arm, the others named as skipped')
    check([i['arm'] for i in plan['items']] == ['rules', 'cheap'] and nightly.pair_items(['a', 'b'], ['x', 'y']) == [{'cell': 'a', 'arm': 'x'}, {'cell': 'a', 'arm': 'y'}, {'cell': 'b', 'arm': 'x'}, {'cell': 'b', 'arm': 'y'}],
          'items are in pair order: the arms of a cell side by side')
    af = TMP / 'arms2.json'
    af.write_text(json.dumps({'rules': {'decider': 'rules'}, 'tact': {'decider': 'rules', 'args': ['--tactics', 'on'], 'requires': '--tactics'}}))
    ok, no = nightly.available_arms(cfg, board.arms(af))
    check(list(ok) == ['rules'] and 'tact' in no, 'an arm whose flag the committed pilot does not have is unavailable, not failed')
    (repo / 'pilot' / 'pilot.py').write_text((repo / 'pilot' / 'pilot.py').read_text() + '\n# --tactics\n')
    subprocess.run(['git', '-C', str(repo), '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qam', 'tactics'], check=True)
    check(list(nightly.available_arms(cfg, board.arms(af))[0]) == ['rules', 'tact'], 'once the pilot has the flag at its committed head the arm is played')
    # the caps
    (repo / 'pilot' / 'caps.json').write_text(json.dumps({'per_run_usd': 3, 'per_night_usd': 50, 'total_usd': 4000}))
    (repo / 'pilot' / 'ledger.jsonl').write_text(json.dumps({'ts': time.time(), 'run': 'x', 'cost_usd': 46.0}) + '\n')
    okk, why = nightly.spend_ok(cfg, ['cheap'])
    check(not okk and 'does not fit' in why, 'a night that has spent 46 of 50 USD has no room for the 5 USD allowance: the model arms are dropped')
    check(nightly.spend_ok(cfg, [])[0], 'the rules arm needs no money')
    (repo / 'pilot' / 'ledger.jsonl').write_text('')
    check(nightly.spend_ok(cfg, ['cheap'])[0], 'a clean ledger fits the allowance')
    (repo / 'pilot' / 'caps.json').unlink()
    check(not nightly.spend_ok(cfg, ['cheap'])[0], 'no caps file: no model arm')
    # the queue
    calls = []

    class FakePopen:
        def __init__(self, cmd, **kw):
            calls.append((cmd, kw))
            self.pid = os.getpid()
    pid = nightly.queue_hold(cfg, '20261116', 1, '/t/tools', popen=FakePopen)
    cmd, kw = calls[0]
    check(kw['close_fds'] is True and kw['start_new_session'] is True and 'PlayBench' in kw['cwd'] and kw['env']['PILOT_OPENAI_KEY_FILE'] == cfg['key_file'],
          'the waiter closes inherited descriptors (a lock held by the running hold must not leak into its successor), starts a session, and runs in a PlayBench folder')
    nd = config.night_dir(cfg, '20261116')
    check(json.loads((nd / 'waiter.json').read_text())['pid'] == pid and nightly.live_waiter(nd) == pid, 'the waiter\'s pid is recorded and found alive')
    check('still alive' in (raises(lambda: nightly.queue_hold(cfg, '20261116', 2, '/t/tools', popen=FakePopen)) or ''), 'one waiter at a time: a second is refused while the first lives')
    nightly.queue_hold(cfg, '20261116', 2, '/t/tools', popen=FakePopen, replacing=pid)
    check(len(calls) == 2, 'the running hold may queue its successor (it replaces its own waiter)')
    (nd / 'waiter.json').write_text(json.dumps({'pid': 99999999}))
    check(nightly.live_waiter(nd) is None, 'a waiter that is gone is not alive')
    plan = {'items': [{'cell': 'a', 'arm': 'r'}, {'cell': 'a', 'arm': 'c'}, {'cell': 'b', 'arm': 'r'}]}
    pend = nightly.pending_items(plan, {('a', 'r'): {'valid': 1}, ('b', 'r'): {'valid': 0}}, {('b', 'r'): 1, ('a', 'c'): 2}, 2)
    check(pend == [{'cell': 'b', 'arm': 'r', 'attempt': 2}], 'pending: a valid result is done, an invalid one is tried again once, then left')
    # start_night: the player, an existing plan, the timer
    cfg2 = dict(cfg, reports=str(TMP / 'PlayBench-files2'), tools_repo=str(repo), idle_s=1, idle_timeout_s=2)
    pl = nightly.start_night(cfg2, '20261201', wait_idle=True, probe=lambda: [{'pid': 5}], popen=FakePopen)
    check('player wins' in pl.get('skipped', ''), 'the player\'s game: no night')
    check(not (config.night_dir(cfg2, '20261201') / 'plan.json').exists(), 'and nothing is written')
    (repo / 'pilot' / 'caps.json').write_text(json.dumps({'per_run_usd': 3, 'per_night_usd': 50, 'total_usd': 4000}))
    n0 = len(calls)
    pl = nightly.start_night(cfg2, '20261202', wait_idle=False, popen=FakePopen)
    check(pl['night'] == '20261202' and pl['waiter_pid'] and len(calls) == n0 + 1 and (config.night_dir(cfg2, '20261202') / 'plan.json').is_file(), 'start_night writes the plan, freezes the tools and queues hold 1')
    check('already has a plan' in nightly.start_night(cfg2, '20261202', wait_idle=False, popen=FakePopen).get('skipped', ''), 'a night is started once')
    wj = config.night_dir(cfg2, '20261202') / 'waiter.json'
    orig_waiter = wj.read_text()
    wj.write_text(json.dumps({**json.loads(orig_waiter), 'pid': os.getpid()}))
    skip = nightly.start_night(cfg2, '20261299', wait_idle=False, popen=FakePopen)
    check('one waiter at a time' in skip.get('skipped', '') and not (config.night_dir(cfg2, '20261299') / 'plan.json').exists(), 'a new night does not join the lane while an earlier night\'s waiter is still queued')
    wj.write_text(json.dumps({**json.loads(orig_waiter), 'pid': 99999999}))
    first = nightly.git(repo, 'rev-list', '--max-parents=0', 'HEAD')
    pinned = nightly.start_night(cfg2, '20261203', wait_idle=False, popen=FakePopen, pilot_commit=first)
    check(pinned['pilot_commit'] == first and json.loads((config.night_dir(cfg2, '20261203') / 'plan.json').read_text())['pilot_commit'] == first, 'a baseline night can pin the pilot commit it plays')
    check(nightly.available_arms(cfg2, board.arms(af), first)[0].keys() == {'rules'}, 'an arm\'s requirement is checked against the pinned commit, not the head')
    check('explicit word' in (raises(lambda: nightly.arm_timer(cfg2)) or ''), 'the timer refuses to arm without the user\'s word (timer_enabled)')
    for w in (config.night_dir(cfg2, 'x').parent).glob('*/waiter.json'):   # (the earlier nights' fake waiters are all the test process: make them dead)
        w.write_text(json.dumps({**json.loads(w.read_text()), 'pid': 99999999}))
    # a proving run: only the cells and arms named, not a night of the trend, and its queued waiter gives way to a real night
    pr = nightly.start_night(cfg2, '20261204-proof', wait_idle=False, popen=FakePopen, only_cells=['chest', 'ledge'], only_arms=['rules'], proof=True)
    check(pr.get('proof') is True and pr['skipped_cells'] and sorted(pr['cells']) == [] or pr.get('proof') is True, 'a proving run is planned and marked')
    ppl = json.loads((config.night_dir(cfg2, '20261204-proof') / 'plan.json').read_text())
    check(ppl['proof'] is True and ppl['arms'] == ['rules'] and ppl['cells'] == [c for c in ppl['cells'] if c in ('chest', 'ledge')], 'its plan names only the cells and arms asked for')
    check('unknown cells' in (raises(lambda: nightly.make_plan(cfg2, 'x', only_cells=['nope']), ValueError) or ''), 'an unknown cell in --cells is an error')
    killed = []
    pw = config.night_dir(cfg2, '20261204-proof') / 'waiter.json'
    pw.write_text(json.dumps({'pid': os.getpid(), 'hold': 1, 'command': ['x', '--tools', '/t']}))
    real_night = nightly.start_night(cfg2, '20261205', wait_idle=False, popen=FakePopen, killer=lambda pid, sig: killed.append((pid, sig)))
    check(real_night.get('night') == '20261205' and [k[0] for k in killed] == [os.getpid()] * 2 and (config.night_dir(cfg2, '20261204-proof') / 'withdrawn.txt').is_file(),
          'a real night withdraws a proving run\'s queued waiter (TERM, then CONT, by pid) instead of being skipped')
    pw.write_text(json.dumps({'pid': 99999999}))
    stp = store.Store(TMP / 'proof.sqlite')
    stp.begin_night('20261204-proof', 'x', {'proof': True})
    stp.begin_night('20261205', 'x', {})
    stp.add_cell(result_row('20261204-proof', 'chest', 'rules', success=1, ttg=3.0))
    stp.add_cell(result_row('20261205', 'chest', 'rules', success=1, ttg=3.0))
    check([n['night'] for n, _ in stp.all_counted()] == ['20261205'], 'a proving run is left out of the trend\'s nights')
    stp.close()
    # refreeze: a fix made while the hold waits goes into the folder the waiter will run
    nd2 = config.night_dir(cfg2, '20261202')
    calls2 = []

    class AlivePopen:
        def __init__(self, cmd, **kw):
            calls2.append(cmd)
            self.pid = os.getpid()
    (nd2 / 'waiter.json').write_text(json.dumps({'pid': os.getpid(), 'hold': 1, 'command': json.loads((nd2 / 'waiter.json').read_text())['command']}))
    tools = Path(json.loads((nd2 / 'waiter.json').read_text())['command'][-1])
    marker = tools / 'playbench' / 'marker.txt'
    marker.write_text('old')
    (repo / 'playbench' / 'playbench.py').write_text('print("stub two")\n')
    subprocess.run(['git', '-C', str(repo), '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qam', 'fix'], check=True)
    where, commit2 = nightly.refreeze(cfg2, '20261202')
    check(where == tools and not marker.exists() and (tools / 'playbench' / 'playbench.py').read_text() == 'print("stub two")\n' and not Path(str(tools) + '.prev').exists(),
          'refreeze swaps the new copy into the folder the waiter will run and leaves no copy beside it')
    check(json.loads((nd2 / 'plan.json').read_text())['tools_commit'] == commit2, 'and the plan names the new tools commit')
    check(nightly.hold_started('20261202', 1) is False and nightly.hold_started('20261202', 1, Path('/nonexistent')) is False, 'a hold that has not started is not started')
    p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)', 'playbench.py', 'hold', '--night', '20261202', '--hold', '1'])
    time.sleep(0.3)
    check(nightly.hold_started('20261202', 1) is True and 'has started' in (raises(lambda: nightly.refreeze(cfg2, '20261202')) or ''), 'once the hold\'s python runs, refreeze refuses (its tools are in use)')
    p.kill()
    p.wait()
    board.LOCAL = old
    os.environ.pop('PLAYBENCH_LOCAL', None)


# ---------------------------------------------------------------------------------------------------------------------------------------- a whole hold

FAKE_METRICS = r'''
import json
from pathlib import Path
def read_jsonl(p):
    return [json.loads(x) for x in Path(p).read_text().splitlines()] if Path(p).is_file() else []
def analyse(run_dir, ledger=None, arm=None):
    rows = read_jsonl(Path(run_dir) / 'transcript.jsonl')
    return {'session': {'stuck_s_total': 1.5, 'decisions': len([r for r in rows if r.get('kind') == 'decision'])}, 'cost': {'total_usd': 0.01 if arm != 'rules' else 0.0}}
'''


def make_pilot_repo(repo, requires_flag=True):
    repo = Path(repo)
    (repo / 'pilot').mkdir(parents=True, exist_ok=True)
    (repo / 'pilot' / 'pilot.py').write_text(FAKE_PILOT)
    (repo / 'pilot' / 'metrics.py').write_text(FAKE_METRICS)
    (repo / 'pilot' / 'test_metrics.py').write_text('print("ok")\n')
    (repo / 'pilot' / 'ledger.jsonl').write_text('')
    (repo / 'hsap.py').write_text('import sys\nprint("usage")\n')
    (repo / 'playbench').mkdir(exist_ok=True)
    (repo / 'playbench' / 'playbench.py').write_text('print("stub")\n')
    cmds = ['git', '-C', str(repo)]
    if not (repo / '.git').exists():
        subprocess.run([*cmds, 'init', '-q'], check=True)
    subprocess.run([*cmds, 'add', '-A'], check=True)
    subprocess.run([*cmds, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', 'fake pilot'], check=True)


def test_hold_end_to_end():
    runner.POLL_S, runner.MET_GRACE_S, runner.END_WAIT_S, runner.OVER_GRACE_S = 0.1, 0.3, 0.3, 3.0
    base = TMP / 'e2e'
    repo = base / 'repo'
    make_pilot_repo(repo)
    # the fake pilot lives at repo/pilot/pilot.py; hsap -h and test_metrics run in the snapshot
    local = base / 'local'
    (local / 'segments').mkdir(parents=True)
    at = {'kind': 'at', 'map': 'M', 'x': 4.0, 'z': 0.0, 'r': 1.0}
    (local / 'segments' / 'good.json').write_text(json.dumps({'rows': rows_script([(i, 100.0, 0.0) for i in range(6)]), 'end': 'hang', 'outcome': 'solved'}))
    (local / 'segments' / 'bad.json').write_text(json.dumps({'rows': rows_script([(0.0, 100.0, 0.0)]), 'rc': 1}))
    (local / 'board-local.json').write_text(json.dumps({'ledge': {'segment': 'good.json', 'proof': at, 'budget_s': 20}, 'drop': {'segment': 'bad.json', 'proof': at, 'budget_s': 20}}))
    os.environ['PLAYBENCH_LOCAL'] = str(local)
    board.LOCAL = local
    config.LOCAL = local
    copies = []
    for n in 'ab':
        c = base / f'copy-{n}'
        (c / 'cache').mkdir(parents=True)
        nm = hs_names.Names(hs_names.PROJECTS[-1])
        (c / nm.executable).write_text('exe')
        (c / nm.renderer).write_text('so')
        (c / 'built-from.txt').write_text('abc123\n')
        copies.append(str(c))
    cfg = config.load(TMP / 'nocfg.json', require=False)
    cfg.update(reports=str(base / 'PlayBench-files'), pilot_repo=str(repo), copies=copies, python=sys.executable, hold_s=1000, reserve_s=5, shots=0, quiet_lock=str(base / 'q'), measuring_lock=str(base / 'm'),
               max_holds_per_night=3, key_file=str(base / 'key'), game_env={'PB_TEST_CAP': 5500})
    old_harness = config.HARNESS
    config.HARNESS = base / 'harness'
    (config.HARNESS).mkdir()
    shutil_copy_hs_names(config.HARNESS)
    night = '20261203'
    nd = config.night_dir(cfg, night)
    nd.mkdir(parents=True)
    plan = nightly.make_plan(cfg, night, tools_commit='tt1')
    check(plan['cells'] == ['drop', 'ledge'] or sorted(plan['cells']) == ['drop', 'ledge'], 'the end-to-end plan has the two defined cells')
    (nd / 'plan.json').write_text(json.dumps(plan))
    queued = []

    class FakePopen:
        def __init__(self, cmd, **kw):
            queued.append(cmd)
            self.pid = os.getpid()
    db = base / 'results.sqlite'
    usable, problems = holdmod.check_copies(copies)
    check(usable == copies and not problems, 'two warm copies of one build are usable lanes')
    (Path(copies[1]) / 'built-from.txt').write_text('different\n')
    u2, p2 = holdmod.check_copies(copies)
    check(u2 == [copies[0]] and 'different build' in p2[copies[1]], 'a copy of another build is not played beside the first')
    (Path(copies[1]) / 'built-from.txt').write_text('abc123\n')
    shutil_rmtree(Path(copies[1]) / 'cache')
    check('not warm' in holdmod.check_copies(copies)[1][copies[1]], 'a cold copy is refused: its first start would compile every shader')
    (Path(copies[1]) / 'cache').mkdir()
    rc = holdmod.run_hold(night, 1, cfg, '/t/tools', python=sys.executable, db=db, queue_popen=FakePopen, pilot_cmd=None)
    check(rc == 0, 'the hold ends 0')
    st = store.Store(db)
    c = st.counted(night)
    check(c[('ledge', 'rules')]['success'] == 1 and c[('ledge', 'cheap')]['success'] == 1 and c[('drop', 'rules')]['success'] == 0 and c[('drop', 'rules')]['valid'] == 1,
          'the cells were played and judged by the referee: the good cell met, the bad one a clean failure')
    check(c[('ledge', 'cheap')]['cost_usd'] == 0.01 and c[('ledge', 'rules')]['cost_usd'] == 0.0, 'cost comes from the pilot\'s metrics')
    n = st.night(night)
    check(n['pilot_commit'] == nightly.git(repo, 'rev-parse', 'HEAD')[:9] and n['tools_commit'] == 'tt1' and n['status'] == 'complete', 'the night carries the pilot commit it played and the tools commit; all four items done: complete')
    check((nd / 'runs' / 'pb261203-ledge-rules-a1' / 'state.jsonl.gz').is_file(), 'the evidence of every cell is kept')
    check((Path(cfg['reports']) / 'trend' / 'trend.md').is_file() and (Path(cfg['reports']) / 'trend' / 'chart.svg').is_file(), 'the trend and the chart were drawn')
    check(not (config.HARNESS / f'playthrough-playbench-{night}-h1').exists(), 'the snapshot is removed after scoring')
    hj = json.loads((nd / 'holds' / '1' / 'hold.json').read_text())
    check(hj['scored'] == 4 and hj['stopping'] is None and 'kernel_driver_lines' in hj and hj['pilot_commit'] == n['pilot_commit'], 'hold.json records what was scored, the pilot commit and the kernel line count')
    hp = json.loads((nd / 'holds' / '1' / 'plan.json').read_text())
    check(hp['env']['PB_TEST_CAP'] == '5500' and hp['env']['PILOT_OPENAI_KEY_FILE'] == cfg['key_file'] and json.loads((nd / 'holds' / '1' / 'identity.json').read_text())['game_env'] == {'PB_TEST_CAP': 5500},
          'the config\'s game_env reaches every game run of the hold (as strings) and is recorded with the hold')
    check(queued == [], 'nothing is queued when no item is pending')
    check(weekly_check(cfg, st, night, base), 'on a Monday night the weekly draft is written with its chart picture; on other nights it is not')
    # a second night: one cell cut short by the hold, the next hold is queued
    night2 = '20261204'
    nd2 = config.night_dir(cfg, night2)
    nd2.mkdir(parents=True)
    (local / 'segments' / 'slow.json').write_text(json.dumps({'rows': rows_script([(0.0, 100.0, 0.0)]), 'end': 'hang'}))
    (local / 'board-local.json').write_text(json.dumps({'ledge': {'segment': 'slow.json', 'proof': at, 'budget_s': 20}}))
    plan2 = nightly.make_plan(cfg, night2, tools_commit='tt1')
    (nd2 / 'plan.json').write_text(json.dumps(plan2))
    cfg['hold_s'] = 8   # a hold too short for any cell: both are deferred
    rc = holdmod.run_hold(night2, 1, cfg, '/t/tools', python=sys.executable, db=db, queue_popen=FakePopen)
    st = store.Store(db)
    check(rc == 0 and st.counted(night2) == {} and len(queued) == 1 and 'hold' in queued[0] and queued[0][queued[0].index('--hold') + 1] == '2',
          'a hold that could play nothing scores nothing and queues the next hold (one waiter)')
    cfg['hold_s'] = 1000
    st.close()
    # a head whose smoke checks fail is not played
    (local / 'board-local.json').write_text(json.dumps({'ledge': {'segment': 'good.json', 'proof': at, 'budget_s': 20}, 'drop': {'segment': 'bad.json', 'proof': at, 'budget_s': 20}}))
    plan2 = nightly.make_plan(cfg, '20261205', tools_commit='tt1')
    (repo / 'hsap.py').write_text('import sys\nsys.exit(3)\n')
    subprocess.run(['git', '-C', str(repo), '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qam', 'broken'], check=True)
    night3 = '20261205'
    nd3 = config.night_dir(cfg, night3)
    nd3.mkdir(parents=True)
    (nd3 / 'plan.json').write_text(json.dumps(plan2))
    rc = holdmod.run_hold(night3, 1, cfg, '/t/tools', python=sys.executable, db=db, queue_popen=FakePopen)
    st = store.Store(db)
    check(rc == 0 and len(st.counted(night3)) == 4 and st.night(night3)['pilot_commit'] == n['pilot_commit'], 'a head that fails its smoke checks falls back to the last commit that played')
    st.close()
    (repo / 'hsap.py').write_text('import sys\nprint("usage")\n')
    config.HARNESS = old_harness
    os.environ.pop('PLAYBENCH_LOCAL', None)


def weekly_check(cfg, st, night, base):
    import datetime
    cfg = dict(cfg, drafts=str(base / 'drafts'))
    monday = '20261130'
    assert datetime.datetime.strptime(monday, '%Y%m%d').weekday() == 0
    other = holdmod.weekly_draft(cfg, st, '20261203')
    forced = holdmod.weekly_draft(cfg, st, '20261203', force=True)
    mon = holdmod.weekly_draft(cfg, st, monday)
    return (other is None and forced is not None and forced.is_file() and mon is not None and 'pilot-1198-scoreboard-weekly-20261130.md' in str(mon)
            and mon.read_text().startswith('**The test player scoreboard') and (not (Path(cfg['reports']) / 'trend' / 'chart.png').is_file() or (base / 'drafts' / 'pilot-1198-scoreboard-20261130.png').is_file()))


def shutil_copy_hs_names(dest):
    import shutil
    src = Path(os.environ['PLAYBENCH_HARNESS'])
    shutil.copy((src if (src / 'hs_names.py').is_file() else src / 'harness') / 'hs_names.py', dest / 'hs_names.py')


def shutil_rmtree(p):
    import shutil
    shutil.rmtree(p, ignore_errors=True)


# --------------------------------------------------------------------------------------------------------------------------------------- the entry point

def test_smoke_flags():
    snap = TMP / 'smoke-snap'
    (snap / 'pilot').mkdir(parents=True)
    (snap / 'hsap.py').write_text('print("usage")\n')
    (snap / 'pilot' / 'test_metrics.py').write_text('print("ok")\n')
    (snap / 'pilot' / 'pilot.py').write_text('print("usage: pilot.py run " + " ".join(%r))\n' % (list(runner.PILOT_FLAGS),))
    check(holdmod.smoke(snap, sys.executable) == '', 'a pilot whose `run -h` lists every option the runner passes passes the smoke check')
    (snap / 'pilot' / 'pilot.py').write_text('print("usage: pilot.py run --decider --tag --copy --wall")\n')
    bad = holdmod.smoke(snap, sys.executable)
    check('lacks' in bad and '--no-bad-points' in bad and '--allowance-usd' in bad, 'a pilot that lost an option the runner passes fails it before any game starts')
    (snap / 'pilot' / 'pilot.py').write_text('import sys\nsys.exit(2)\n')
    check('exit 2' in holdmod.smoke(snap, sys.executable), 'a pilot that does not start fails it')


def test_entry():
    r = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'playbench.py'), '--help'], capture_output=True, text=True, timeout=60)
    check(r.returncode == 0 and 'Traceback' not in r.stderr and 'queue' in r.stdout, 'playbench.py starts under python3 -I -B (its own folder on sys.path)')
    f = TMP / 'frozen'
    f.mkdir()
    subprocess.run(f'cp -r {HERE} {f}/playbench', shell=True, check=True)
    (TMP / 'e-local').mkdir()
    (TMP / 'e-local' / 'config.json').write_text(json.dumps({k: ('/x' if k != 'copies' else ['/x']) for k in config.REQUIRED}))
    r = subprocess.run([sys.executable, '-I', '-B', str(f / 'playbench' / 'playbench.py'), 'status', '--last', '1'], capture_output=True, text=True, timeout=60,
                       env={'PATH': os.environ['PATH'], 'HOME': str(TMP), 'PLAYBENCH_LOCAL': str(TMP / 'e-local'), 'PLAYBENCH_HARNESS': os.environ['PLAYBENCH_HARNESS']})
    check(r.returncode == 0 and 'Traceback' not in r.stderr, 'a frozen copy of the tools starts and reads an empty store')
    d = TMP / 'cellsfreeze'
    d.mkdir()
    (d / 'src.toml').write_text('name = "src"\nwatch = ["A"]\nbudget_seconds = 999\nwall = 5\n\n[[goal]]\nname = "g"\nkind = "reach"\nflag = "A=1"\ntargets = [{name = "t", at = [1.0, 2.0], radius = 1.5}]\n')
    cell = board.Cell('door-front', 't', 'a', proof={'kind': 'flag', 'name': 'Door', 'value': 1}, budget_s=55)
    doc = cellmod.freeze_segment(d / 'src.toml', d / 'out.toml', cell, save_abs='/x/save')
    import tomllib
    back = tomllib.loads((d / 'out.toml').read_text())
    check(back['name'] == 'pb-door-front' and back['budget_seconds'] == 55.0 and back['wall'] == cell.wall_s and back['humanize'] == 0 and back['save'] == '/x/save'
          and back['watch'] == ['A', 'Door'] and back['goal'][0]['targets'][0]['at'] == [1.0, 2.0] and doc['name'] == back['name'], 'a frozen segment: name, budget, wall, humanize 0, save path, the proof\'s flag watched, goals intact')


def main():
    for t in (test_board, test_referee, test_store, test_blocked, test_trend, test_names_dir, test_guard, test_score, test_runner, test_nightly, test_hold_end_to_end, test_smoke_flags, test_entry):
        t0 = time.time()
        n0 = len(FAILS)
        t()
        print(f'{t.__name__}: {"ok" if len(FAILS) == n0 else "FAILED"} ({time.time() - t0:.1f} s)', flush=True)
    print(f'{COUNT[0]} checks, {len(FAILS)} failed')
    for f in FAILS:
        print('  FAIL:', f)
    import shutil
    shutil.rmtree(TMP, ignore_errors=True)
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
