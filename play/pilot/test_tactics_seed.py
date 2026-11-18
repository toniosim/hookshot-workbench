#!/usr/bin/env python3
"""tactics_seed.py: the tactics library filled from what past runs already did, with no human recording. A pilot transcript's recovery blocks (the ladder's
rungs in order, what finally gained ground, what the spent ladder left) and a step journal's stuck steps (what the steps after one were, whether Link got
past) become attempts with their cause and geometry, one `block` row per episode, and demonstrations (a way out that is no family of the catalogue, kept
relative to the place). Seeding twice adds nothing. Made-up runs and maps; no game, no network.   python3 -I -B test_tactics_seed.py"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import tactics  # noqa: E402
import tactics_seed as seed  # noqa: E402
from test_routelib import FakeRun, FakeWorld, build_log  # noqa: E402

FAILS, CHECKS = [], [0]


def check(cond, what):
    CHECKS[0] += 1
    if not cond:
        FAILS.append(what)
        print('FAIL', what, flush=True)


def state(x, z, area='Testland_Child', y=100.0, child=1, **kw):
    return {'pos': [x, y, z], 'area': area, 'child': child, 'prompt': 'Empty', 'event': 0, 't': 10.0, **kw}


def step(src, result, pos, detail='', moved=0.0):
    return {'ev': 'step', 'in': 1, 'src': src, 'result': result, 'secs': 1.0, 'moved': moved, 'detail': detail, 'pos': pos, 't': 1.0}


def write_transcript(folder, rows):
    folder = Path(folder)
    (folder / 'pilot').mkdir(parents=True, exist_ok=True)
    (folder / 'pilot' / 'transcript.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    return folder


def ladder_rows():
    """Block 1 (a person near): sidestep fails, angle gets past. Block 2: the spent ladder (replan) with a held rung in it. Block 3: never finished (the run ended)."""
    return [
        {'kind': 'decision', 'n': 1, 'state': state(0.0, 10.0), 'choice': 'go', 'decider': 'rules', 'target': 't1'},
        {'kind': 'result', 'n': 1, 'result': 'stuck', 'moved': 5.0, 'steps': [step('run 0.00 30.00 radius 2.5 timeout 30', 'stuck', [0.0, 100.0, 10.0], '20.00 m from the point; moved under 0.3 m in 2.5 s at 0.0 100.0 10.0', 5.0)]},
        {'kind': 'recover', 'n': 1, 'target': 't1', 'status': 'blocked', 'at': [0.0, 10.0], 'why': 'blocked', 'learned': None},
        {'kind': 'decision', 'n': 2, 'state': state(0.0, 10.0), 'choice': 'recover:sidestep', 'decider': 'recover', 'target': 't1', 'recover_rung': 'sidestep'},
        {'kind': 'result', 'n': 2, 'result': 'stuck', 'moved': 3.0, 'steps': [step('run 0.00 30.00 radius 2.5', 'stuck', [2.4, 100.0, 12.0], '18 m from the point', 3.0)]},
        {'kind': 'decision', 'n': 3, 'state': state(2.4, 12.0), 'choice': 'recover:angle', 'decider': 'recover', 'target': 't1', 'recover_rung': 'angle'},
        {'kind': 'result', 'n': 3, 'result': 'reached', 'moved': 30.0, 'steps': [step('run 0.00 30.00 radius 2.5', 'reached', [0.0, 100.0, 29.0], '1 m from the point', 30.0)]},
        {'kind': 'recover', 'n': 3, 'target': 't1', 'status': 'recovered', 'rung': 'angle', 'at': [0.0, 10.0], 's': 12.0},
        {'kind': 'decision', 'n': 4, 'state': state(60.0, 60.0), 'choice': 'go', 'decider': 'rules', 'target': 't2'},
        {'kind': 'result', 'n': 4, 'result': 'stuck', 'moved': 9.0, 'steps': [step('run 60.00 90.00 radius 2.5', 'stuck', [60.0, 100.0, 70.0], '20 m from the point; moved under 0.3 m in 2.5 s', 9.0)]},
        {'kind': 'recover', 'n': 4, 'target': 't2', 'status': 'blocked', 'at': [60.0, 70.0], 'why': 'blocked', 'learned': None},
        {'kind': 'decision', 'n': 5, 'state': state(60.0, 70.0), 'choice': 'recover:sidestep', 'decider': 'recover', 'target': 't2'},
        {'kind': 'result', 'n': 5, 'result': 'stuck', 'moved': 1.0, 'steps': [step('walk 62.5 70', 'stuck', [61.0, 100.0, 70.0], '', 1.0)]},
        {'kind': 'decision', 'n': 6, 'state': state(61.0, 70.0), 'choice': 'recover:roll', 'decider': 'recover', 'target': 't2'},
        {'kind': 'result', 'n': 6, 'result': 'held', 'moved': 0.0, 'steps': [step('roll up', 'held', [61.0, 100.0, 70.0])]},
        {'kind': 'decision', 'n': 7, 'state': state(61.0, 70.0), 'choice': 'recover:hop', 'decider': 'recover', 'target': 't2'},
        {'kind': 'result', 'n': 7, 'result': 'stuck', 'moved': 0.0, 'steps': [step('raw 0:LX=0+LY=32767/800,0.15:X/100 1.2', 'stuck', [61.0, 100.0, 70.0])]},
        {'kind': 'decision', 'n': 8, 'state': state(61.0, 70.0), 'choice': 'recover:replan', 'decider': 'recover', 'target': 't2'},
        {'kind': 'recover', 'n': 8, 'target': 't2', 'status': 'marked-bad', 'at': [60.0, 70.0], 'rungs': ['sidestep', 'roll', 'hop', 'replan'], 's': 20.0},
        {'kind': 'decision', 'n': 9, 'state': state(-40.0, -40.0), 'choice': 'go', 'decider': 'rules', 'target': 't3'},
        {'kind': 'result', 'n': 9, 'result': 'stuck', 'moved': 2.0, 'steps': [step('run -40 -80 radius 2.5', 'stuck', [-40.0, 100.0, -40.0], '40 m from the point; moved under 0.3 m', 2.0)]},
        {'kind': 'recover', 'n': 9, 'target': 't3', 'status': 'blocked', 'at': [-40.0, -40.0], 'why': 'blocked', 'learned': None},
        {'kind': 'decision', 'n': 10, 'state': state(-40.0, -40.0), 'choice': 'recover:sidestep', 'decider': 'recover', 'target': 't3'},
        {'kind': 'result', 'n': 10, 'result': 'stuck', 'moved': 1.0, 'steps': [step('walk -37.5 -40', 'stuck', [-39.0, 100.0, -40.0], '', 1.0)]},
    ]


def transcript_checks(tmp):
    world = FakeWorld()
    world.people = [('Testland_Child', 0.0, 11.5, 'Npc')]
    sensor = tactics.Sensor(world)
    ev = seed.transcript_blocks(ladder_rows(), sensor)
    check(len(ev) == 3, f'three blocks in the transcript ({len(ev)})')
    b1, b2, b3 = ev
    check(b1['cause'] == 'npc-in-way' and b1['map'] == 'Testland_Child' and b1['age'] == 'child' and b1['at'] == [0.0, 100.0, 10.0], f'block 1: the cause from the stuck step and the world ({b1["cause"]}, {b1["at"]})')
    check([(a['tactic'], a['outcome']) for a in b1['attempts']] == [('sidestep', 'failed'), ('angle', 'worked')] and b1['how'] == 'recovered' and b1['worked'] == 'angle',
          f'block 1: sidestep failed, angle worked ({b1["attempts"]})')
    check(b1['attempts'][1]['gain_m'] is not None and b1['attempts'][1]['gain_m'] > 15, 'a worked rung has the ground it gained')
    check(b1['geom'].get('persons') == '1-2', 'and the geometry round the place')
    check([(a['tactic'], a['outcome']) for a in b2['attempts']] == [('sidestep', 'failed'), ('hop', 'failed')] and b2['how'] == 'marked-bad' and b2.get('worked') is None,
          f'block 2: a held rung says nothing (no attempt), replan is not a tactic, every other rung failed ({b2["attempts"]})')
    check(b2['cause'] != 'npc-in-way', f'block 2 is elsewhere: its own cause ({b2["cause"]})')
    check(b3['how'] == 'left' and [a['tactic'] for a in b3['attempts']] == [] , f'block 3: the run ended inside the ladder: the last rung is unknown, so no attempt ({b3["attempts"]}, {b3["how"]})')

    book = tactics.Book(Path(tmp) / 'book-tr')
    folder = write_transcript(Path(tmp) / 'runT', ladder_rows())
    got = seed.seed_run(book, folder, sensor)
    check(got['attempts'] == 4 and got['blocks'] == 3 and got['demos'] == 0, f'seeded: 4 attempts, 3 blocks ({got})')
    att = book.rows('attempt')
    check(all(a['source'] == 'journal' and a['key'] and a['run'] for a in att) and att[0]['block'], 'attempts are filed under the journal, with a key, the run and the block')
    again = seed.seed_run(book, folder, sensor)
    check(again['attempts'] == 0 and again['blocks'] == 0 and len(book.rows('attempt')) == 4, f'seeding the same run again adds nothing ({again})')
    check(book.counts('npc-in-way')['angle']['wins'] == 1 and book.counts('npc-in-way')['sidestep']['fails'] == 1, 'the counts are in the library')
    blk = book.rows('block')
    check(len(blk) == 3 and blk[0]['cause'] == 'npc-in-way' and blk[0]['worked'] == 'angle' and blk[0]['tried'] == ['sidestep', 'angle'], 'the block rows carry the order and what worked')


# ------------------------------------------------------------------------------------------------------ journals

def journal_run(tmp, name='runJ'):
    r = FakeRun(Path(tmp) / name, name, start=(0.0, 100.0, 0.0))
    # 1: stuck at (0, 10) wanting (0, 30); a step to the side then the go: gets past (a sidestep that worked)
    r.leg('run 0.00 30.00 radius 2.5 timeout 30', [(0, 100, 10)], 'stuck', detail='20.00 m from the point; moved under 0.3 m in 2.5 s at 0.0 100.0 10.0')
    r.leg('walk 2.50 10.00 radius 0.6 timeout 4', [(2.5, 100, 10)], 'reached')
    r.leg('run 0.00 30.00 radius 2.5 timeout 30', [(2.5, 100, 20), (0, 100, 30)], 'reached')
    # 2: stuck again at (0, 40) wanting (0, 80): a roll, a wait, the go stuck again: the roll failed
    r.leg('run 0.00 80.00 radius 2.5 timeout 30', [(0, 100, 40)], 'stuck', detail='40.00 m from the point; moved under 0.3 m in 2.5 s at 0.0 100.0 40.0')
    r.leg('roll up', [(0, 100, 42)], 'done')
    r.leg('run 0.00 80.00 radius 2.5 timeout 30', [(0, 100, 41)], 'stuck', detail='39.00 m from the point; moved under 0.3 m in 2.5 s at 0.0 100.0 41.0')
    # 3: a way out that is no family: a diagonal run past it, then the go: it got past (a demonstration)
    r.leg('run 10.00 50.00 radius 1.5 timeout 8', [(10, 100, 50)], 'reached')
    r.leg('run 0.00 80.00 radius 2.5 timeout 30', [(5, 100, 65), (0, 100, 80)], 'reached')
    return r.write(log=build_log('v3.0.0-rc.4-416-gabc1234'))


def journal_checks(tmp):
    folder = journal_run(tmp)
    sensor = tactics.Sensor(FakeWorld())
    ev = seed.journal_blocks(seed.routelib.RunData(folder), sensor)
    check(len(ev) == 3, f'three stuck steps in the journal ({len(ev)}): {[(e["at"][2], [a["tactic"] for a in e["attempts"]]) for e in ev]}')
    first = ev[0]
    check([(a['tactic'], a['outcome']) for a in first['attempts']] == [('sidestep', 'worked')] and first['how'] == 'recovered', f'a step to the side then the go that got past: a sidestep that worked ({first["attempts"]})')
    check(first['at'][2] > 9 and first['map'] == 'Testland_Child' and first['age'] == 'child', 'with the place, the map and the age')
    second = ev[1]
    check([(a['tactic'], a['outcome']) for a in second['attempts']] == [('roll', 'failed')], f'a roll then a go that stuck again: the roll failed ({second["attempts"]})')
    demo = [e for e in ev if e.get('demo')]
    check(len(demo) == 1 and demo[0]['demo'][0]['verb'] == 'run' and len(demo[0]['demo']) == 2 and demo[0]['attempts'][0]['outcome'] == 'worked',
          f'a way out that is no family and got past is a demonstration ({[e.get("demo") for e in ev]})')
    book = tactics.Book(Path(tmp) / 'book-j')
    got = seed.seed_run(book, folder, sensor)
    check(got['demos'] == 1 and got['attempts'] == 3 and got['blocks'] == 3, f'seeded from the journal: three attempts (one a demonstration), three blocks ({got})')
    # a run the ladder recorded while it played is not counted twice from its transcript
    live_folder = write_transcript(Path(tmp) / 'runLive', ladder_rows())
    book.record('sidestep', 'wall', 'failed', map='Testland_Child', run='runLive', source='live')
    check(seed.seed_run(book, live_folder, sensor).get('skipped') == 'recorded while it played' and not book.has_run('nobody'), 'a run the ladder wrote while it played is not seeded again')
    # a way out that waits for a quest's flag is no demonstration (it means nothing elsewhere); the A prompt's own flag and `until control` are fine
    check(seed._generic(tactics.relative_steps(['until flag 0x9824206c=Open timeout 3', 'press A', 'until control timeout 150 press A every 1.5'], (0, 0), (0, 10)))
          and not seed._generic(tactics.relative_steps(['until flag SomeQuest.Done=1 timeout 20 press A every 1.5'], (0, 0), (0, 10)))
          and not seed._generic(tactics.relative_steps(['pickup 3 3'], (0, 0), (0, 10))), 'demonstrations hold only steps that mean the same anywhere')
    # a rung the pilot called recovered that got Link no nearer the point the step wanted (he stood inside the target's radius): no evidence for the tactic
    rows = [{'kind': 'decision', 'n': 1, 'state': state(0.0, 28.0), 'choice': 'go', 'decider': 'rules', 'target': 't'},
            {'kind': 'result', 'n': 1, 'result': 'stuck', 'moved': 1.0, 'steps': [step('run 0.00 30.00 radius 0.6', 'stuck', [0.0, 100.0, 28.0], '2.0 m from the point; moved under 0.3 m in 2.5 s', 1.0)]},
            {'kind': 'recover', 'n': 1, 'target': 't', 'status': 'blocked', 'at': [0.0, 28.0], 'why': 'blocked'},
            {'kind': 'decision', 'n': 2, 'state': state(0.0, 28.0), 'choice': 'recover:sidestep', 'decider': 'recover', 'target': 't'},
            {'kind': 'result', 'n': 2, 'result': 'reached', 'moved': 0.2, 'steps': [step('walk 0.5 28', 'reached', [0.0, 100.0, 28.1], '', 0.2)]},
            {'kind': 'recover', 'n': 2, 'target': 't', 'status': 'recovered', 'rung': 'sidestep', 'at': [0.0, 28.0], 's': 3.0}]
    ev = seed.transcript_blocks(rows, sensor)
    check(len(ev) == 1 and ev[0]['attempts'] == [] and ev[0]['how'] == 'recovered' and ev[0].get('worked') is None, f'a recovered rung that gained under a metre is no attempt ({ev[0]["attempts"] if ev else ev})')
    check(len(book.demos()) == 1 and book.demos()[0]['cause'] in tactics.CAUSES, 'the demonstration is in the library')
    check(seed.seed_run(book, folder, sensor)['attempts'] == 0, 'a journal is seeded once')
    # a run that has a transcript with blocks is read from the transcript only: no double count
    folder2 = journal_run(tmp, 'runBoth')
    write_transcript(folder2, ladder_rows())
    book2 = tactics.Book(Path(tmp) / 'book-both')
    got = seed.seed_run(book2, folder2, sensor)
    check(got['blocks'] == 3 and got['source'] == 'transcript', f'a run with a pilot transcript is read from it, not also from the journal ({got})')
    # a journal with no stuck step adds nothing
    r = FakeRun(Path(tmp) / 'runQ', 'runQ', start=(0.0, 100.0, 0.0))
    r.leg('run 0 30 radius 2.5 timeout 30', [(0, 100, 30)], 'reached')
    got = seed.seed_run(tactics.Book(Path(tmp) / 'book-q'), r.write(), sensor)
    check(got['attempts'] == 0 and got['blocks'] == 0, 'a walk with no stuck step: nothing')
    # a held step (a text holds Link) is a block of its own cause
    r = FakeRun(Path(tmp) / 'runH', 'runH', start=(0.0, 100.0, 0.0))
    r.leg('run 0 30 radius 2.5 timeout 30', [(0, 100, 10)], 'held', detail='20.00 m from the point; an event holds Link at 0.0 100.0 10.0', event=1)
    r.wait(4.0, 'wait 4')
    r.leg('run 0 30 radius 2.5 timeout 30', [(0, 100, 30)], 'reached')
    ev = seed.journal_blocks(seed.routelib.RunData(r.write()), sensor)
    check(len(ev) == 1 and ev[0]['cause'] == 'held' and [(a['tactic'], a['outcome']) for a in ev[0]['attempts']] == [('wait', 'worked')], f'a text holds Link, a wait and the go that got past: held, wait worked ({ev})')


def discover_checks(tmp):
    root = Path(tmp) / 'tree'
    a = write_transcript(root / 'one', ladder_rows())
    b = journal_run(root, 'two')
    (root / 'empty').mkdir(parents=True)
    got = seed.discover([root])
    names = sorted(Path(p).name for p in got)
    check(Path(a) in got or str(a) in map(str, got), f'a folder with a pilot transcript is found ({names})')
    check(any(Path(p) == Path(b) for p in got) or any(str(p).startswith(str(b)) for p in got), f'a folder with a journal is found ({names})')
    check(not any(Path(p).name == 'empty' for p in got), 'an empty folder is not')
    check(len(got) == len({str(p) for p in got}), 'each run once')


def evaluate_checks(tmp):
    """Leave one run out: where the tactic that worked would have come in the old order and in the library's ranking built from the other runs."""
    book = tactics.Book(Path(tmp) / 'book-eval')
    for i in range(8):   # eight runs where the 4th legacy rung (hop) is what works at a wall
        for t, ok in (('sidestep', False), ('angle', False), ('roll', False), ('hop', True)):
            book.record(t, 'wall', 'worked' if ok else 'failed', map='M_Child', run=f'r{i}', block=f'r{i}#0', source='journal', key=f'e{i}{t}')
        book.add_block(map='M_Child', cause='wall', tried=['sidestep', 'angle', 'roll', 'hop'], worked='hop', how='recovered', run=f'r{i}', key=f'b{i}')
    out = seed.evaluate(book)
    check(out['blocks'] == 8 and out['legacy_mean_attempts'] == 4.0, f'the old order needs 4 attempts to reach the hop ({out})')
    check(out['ranked_mean_attempts'] < 2.0, f'the library, built from the other runs, puts hop first or second ({out["ranked_mean_attempts"]})')
    check(out['by_cause']['wall']['blocks'] == 8, 'per cause')
    check(seed.evaluate(tactics.Book(Path(tmp) / 'book-none'))['blocks'] == 0, 'an empty library evaluates to nothing')


def main():
    with tempfile.TemporaryDirectory(prefix='test-tactics-seed-') as t:
        transcript_checks(t)
        journal_checks(t)
        discover_checks(t)
        evaluate_checks(t)
    if FAILS:
        raise SystemExit(f'test_tactics_seed: {len(FAILS)} of {CHECKS[0]} checks FAILED')
    print(f'test_tactics_seed: all {CHECKS[0]} checks passed')


if __name__ == '__main__':
    main()
