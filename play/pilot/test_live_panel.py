"""Game-free tests of live_panel.py: a fake run folder (the shapes pilot.py, hsap.py, vision.py and bughunt.py really write) in a temp dir,
rendered into a string. No TTY, no game, no network. Run: python3 -I -B test_live_panel.py  (or: python3 -I -B -m unittest test_live_panel)."""
import io
import time
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_panel as lp  # noqa: E402

W0 = time.time() - 300.0   # the wall clock of the first event


def jl(path, rows, mode='w'):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, mode) as f:
        for r in rows:
            f.write((r if isinstance(r, str) else json.dumps(r)) + '\n')


STATE = {'ev': 'state', 'why': 'wait', 'n': 35, 't': 12.5, 'frame': 5751, 'pos': [-6, 1, 5], 'facing': 108.6, 'camera': -71.4,
         'area': 'TestYardYoung', 'prompt': 'Empty', 'music': 'quiet', 'scene': False, 'event': 0, 'loading': 0, 'child': 1,
         'life': 12, 'max_life': 12, 'rupees': 7, 'last': {}, 'flags': {'A': 0}, 'changed': []}
CANDS = [{'label': 'go-near', 'lines': ['walk -4.20 3.40 radius 0.6 timeout 10'], 'text': 'walk to the front of house-door, within 0.6 m (4.4 m away)'},
         {'label': 'push-open', 'lines': ['walk -3.20 3.40 radius 0.2 timeout 4', 'press A'], 'text': 'walk into house-door, wait for the A prompt, press A'},
         {'label': 'wait-goal', 'lines': ['wait 2'], 'text': 'wait 2 s'}]
ANSWERS = [{'type': 'choice', 'name': 'next_step', 'choice': 'push-open', 'confidence': 0.61,
            'probabilities': [{'value': 'go-near', 'probability': 0.31}, {'value': 'push-open', 'probability': 0.61}, {'value': 'wait-goal', 'probability': 0.02}]},
           {'type': 'predicate', 'name': 'stuck', 'probability': 0.0}]


def decision(n, choice='push-open', wall=W0 + 10, **kw):
    row = {'kind': 'decision', 'n': n, 'state': dict(STATE, t=10.0 + n), 'goal': 'door', 'target': 'house-door', 'decider': 'openai-decisions',
           'candidates': CANDS, 'choice': choice, 'predicates': {'stuck': 0.0, 'goal_met': 0.0, 'held_by_event': 0.12}, 'plan': None, 'decide_ms': 5.0,
           'recover': {'stuck': False, 'why': None, 'stalled_obs': 0, 'stalled_s': 0.0, 'rung': 0, 'streak': 1},
           'request': {'model': 'm', 'input': [{'role': 'developer', 'content': 'x'}, {'role': 'user', 'content': [
               {'type': 'input_text', 'text': 'The game state'}, {'type': 'input_json', 'data': {
                   'state': {}, 'goal': {'name': 'door'}, 'target': {'name': 'house-door', 'kind': 'door', 'x': -4.5, 'z': 3.5, 'distance_m': 4.4}}}]}]},
           'answers': ANSWERS, 'latency_ms': 270.8, 'usage': {'input_tokens': 1858, 'output_tokens': 0, 'total_tokens': 1858}, 'cost_usd': 0.0001858,
           'confidence': 0.61, 'wall': wall}
    row.update(kw)
    return row


def result(n, word='stuck', wall=W0 + 14):
    return {'kind': 'result', 'n': n, 'lines': ['walk -5.67 2.06 radius 0.6 timeout 4'], 'result': word, 'moved': 0.95, 'wall': wall,
            'steps': [{'ev': 'step', 'in': 8, 'src': 'walk -5.67 2.06 radius 0.6 timeout 4', 'result': word, 'secs': 2.91, 'moved': 0.95,
                       'detail': '1.61 m from the point', 'pos': [-4, 1, 3], 't': 11.6}]}


PLANNER = {'kind': 'planner', 'n': 1, 'why': 'start', 'answer': {'order': ['door'], 'targets': [], 'drop': [], 'reason': 'Open the door first.'},
           'changed': False, 'before': [['door', ['house-door']]], 'after': [['door', ['house-door']]],
           'request': {'model': 'm', 'input': [{'role': 'developer', 'content': 'plan'}, {'role': 'user', 'content': json.dumps({
               'segment': {'name': 'test-door-talk', 'what': 'interaction: a door and a talk', 'area': 'TestYardYoung'},
               'goals': [{'name': 'door', 'what': 'open the door', 'met_when': 'X=1', 'state': 'open', 'kind': 'door',
                          'targets': [{'name': 'house-door', 'kind': 'door', 'x': -4.5, 'z': 3.5, 'y': 1.5, 'state': 'open'}]},
                         {'name': 'friend', 'what': 'talk', 'state': 'open', 'kind': 'talk', 'targets': []}],
               'tried': []})}]},
           'answer_text': '{}', 'latency_ms': 3928.8, 'usage': {'input_tokens': 778, 'output_tokens': 119, 'total_tokens': 897}, 'cost_usd': 0.001373,
           'wall': W0}


def make_run(root, ended=True, vision=True, finding=True, notes=True, summary=True):
    root = Path(root)
    jl(root / 'transcript.jsonl', [
        PLANNER, decision(1), result(1, 'done', W0 + 12),
        {'kind': 'goal', 'goal': 'door', 'status': 'met', 't': 30.85, 'pos': [-4, 1, 4], 'wall': W0 + 20},
        {'kind': 'recover', 'n': 2, 'target': 'house-door', 'status': 'blocked', 'at': [-4.7, 3.6], 'why': 'unchanged', 'learned': None, 'wall': W0 + 22},
        decision(2, 'push-open', wall=W0 + 24), result(2, 'stuck', W0 + 28),
        ] + ([{'kind': 'counterfactual', 'n': 2, 'with_vision': 'go-near', 'without_vision': 'go-near', 'cost_usd': 0.0002, 'asked': True, 'wall': W0 + 25}] if vision else []))
    jl(root / 'live' / 'out.jsonl', [
        {'ev': 'note', 'text': 'hs-run: /x/hs-run.sh', 'boot': 'continue', 'analog': False},
        {'ev': 'note', 'text': 'placement ok: TestTown, adult, 22:00', 'wall': W0 - 5},
        {'ev': 'gameplay', 't': 0.0, 'frame': 5700, 'area': 'TestYardYoung'},
        dict(STATE, n=36),
        {'ev': 'step', 'in': 8, 'src': 'walk -5.67 2.06 radius 0.6 timeout 4', 'result': 'stuck', 'secs': 2.91, 'moved': 0.95,
         'detail': '1.61 m from the point', 'pos': [-4, 1, 3], 't': 11.6}] + ([{'ev': 'done', 't': 116.17}] if ended else []))
    jl(root / 'live' / 'state.jsonl', [
        {'t': 602759.87, 'frame': 5546, 'map': 'TestTownGrown', 'pos': [2, 3, 4], 'facing': 10.0, 'camera': 0.0, 'event': 0, 'loading': 0,
         'life': 10, 'max_life': 12, 'rupees': 7, 'prompt': 'Empty', 'music': '', 'flags': {}, 'changed': {}, 'child': 0}])
    if vision:
        jl(root / 'vision' / 'vision.jsonl', [
            {'seq': 1, 'n': 2, 'why': ['stuck'], 'wall': W0 + 26, 't': 11.6, 'backend': 'decisions', 'model': 'm', 'frame': 'vision/f0001.jpg', 'latency_ms': 447.1,
             'usage': {'input_tokens': 2914, 'output_tokens': 0}, 'cost_usd': 0.0002914,
             'answers': {'front': 'wall_or_obstacle', 'screen': 'play', 'p': {'door': 0.43, 'stuck': 0.9}, 'says': 'Link faces a closed wooden door and pushes it.'},
             'extra': [], 'oddities': []}])
        jl(root / 'vision' / 'oddities.jsonl', [
            {'seq': 1, 'n': 2, 'wall': W0 + 26, 't': 11.6, 'area': 'TestYardYoung', 'pos': [1, 2, 3], 'frame': 'vision/f0001.jpg', 'kind': 'stuck-visible',
             'detail': 'Link is against something solid (front: wall_or_obstacle)'}])
    if finding:
        jl(root / 'findings.jsonl', [
            {'kind': 'softlock', 'sub': 'still', 'severity': 'error', 'side': 'solo', 'text': '8 input steps in 190 s and nothing changed', 't': 12.0,
             'frame': 700, 'game_s': 20.0, 'map': 'Yard', 'pos': [0, 1, 2], 'evidence': {}, 'key': 'softlock:still:x', 'status': 'new'},
            {'kind': 'stall', 'sub': 'gap', 'severity': 'info', 'side': 'solo', 'text': 'an info row is not shown', 'map': 'Yard'}])
    if notes:
        (root / 'panel-notes.txt').write_text('fallback: library save start-of-run\nplacement FAILED: hsdebug refused\n')
    if summary:
        (root / 'summary.json').write_text(json.dumps({'run': 'fake-run-1', 'segment': 'test-door-talk', 'decider': 'openai-decisions',
                                                       'outcome': 'budget: 110 s of game time', 'decisions': 2, 'goals': {'door': 'met', 'friend': 'open'}}))
    return root


def poll_and_render(root, width=72, height=50, **kw):
    run = lp.Run(root, holders=lambda paths: None, **kw)
    run.poll(grace_s=0)
    return run, lp.render(run.snapshot(), width, height)


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'runs' / 'fake-run-1'
        self.addCleanup(self.tmp.cleanup)

    def test_full_frame(self):
        make_run(self.root)
        run, frame = poll_and_render(self.root)
        # header: run, segment, goals met/unmet, target place
        self.assertIn('fake-run-1', frame)
        self.assertIn('segment test-door-talk', frame)
        self.assertIn('✓door', frame)
        self.assertIn('·friend', frame)
        self.assertIn('target house-door', frame)
        self.assertIn('-4.5 3.5', frame)
        self.assertIn('placement FAILED: hsdebug refused', frame)
        # NOW: the chosen mark, the others, the probability, the result word, the recover state
        self.assertIn('▶ push-open', frame)
        self.assertIn('· go-near', frame)
        self.assertIn(' 61%', frame)
        self.assertIn('decision 2', frame)
        self.assertIn('stuck', frame)
        self.assertIn('recover@2: blocked house-door', frame)
        # WORLD from state.jsonl
        self.assertIn('TestTownGrown', frame)
        self.assertIn('life 10/12', frame)
        self.assertIn('rupees 7', frame)
        self.assertIn('state ', frame)
        # EYES
        self.assertIn('Link faces a closed wooden door', frame)
        # BUGS: the finding, the eyes' oddity; an info row is not a finding
        self.assertIn('softlock/still', frame)
        self.assertIn('8 input steps in 190 s', frame)
        self.assertIn('stuck-visible', frame)
        self.assertNotIn('an info row is not shown', frame)
        # NOTES
        self.assertIn('fallback: library save', frame)
        # footer: cost summed over decisions, planner, counterfactual, vision rows; end state
        usd = 0.0001858 * 2 + 0.001373 + 0.0002 + 0.0002914
        self.assertIn(f'cost ${usd:.4f}', frame)
        self.assertIn('RUN ENDED: budget: 110 s of game time', frame)
        self.assertEqual(run.n_dec, 2)

    def test_placement_note_and_fallback_from_events(self):
        make_run(self.root, notes=False)
        _, frame = poll_and_render(self.root)
        self.assertIn('placement ok: TestTown, adult, 22:00', frame)
        jl(self.root / 'live' / 'out.jsonl', [{'ev': 'note', 'text': 'fallback to a saved position: library save x'}], 'a')
        _, frame = poll_and_render(self.root)
        self.assertIn('fallback to a saved position: library save x', frame)

    def test_placement_from_summary(self):
        make_run(self.root, notes=False)
        out = self.root / 'live' / 'out.jsonl'
        out.write_text(''.join(ln for ln in out.read_text().splitlines(True) if 'placement' not in ln))
        s = json.loads((self.root / 'summary.json').read_text())
        s['place'] = {'ok': True, 'to': 'TestTown', 'age': 'adult', 'hour': 22, 'map': 'TestTownGrown', 'seconds': 3.2}
        (self.root / 'summary.json').write_text(json.dumps(s))
        _, frame = poll_and_render(self.root)
        self.assertIn('placed: TestTownGrown, adult, 22:00', frame)

    def test_vision_off_and_no_finding(self):
        make_run(self.root, vision=False, finding=False, notes=False, summary=False, ended=False)
        _, frame = poll_and_render(self.root)
        self.assertIn('vision: off', frame)
        self.assertIn('BUGS off', frame)
        self.assertNotIn('RUN ENDED', frame)
        # the hunter is on (the eyes run) and has found nothing
        (self.root / 'vision').mkdir()
        jl(self.root / 'vision' / 'vision.jsonl', [{'seq': 1, 'n': 1, 'wall': W0, 'answers': {'front': 'x', 'screen': 'play', 'p': {}, 'says': None}, 'cost_usd': 0.0001}])
        _, frame = poll_and_render(self.root)
        self.assertIn('no finding yet (bug hunter on)', frame)
        self.assertNotIn('vision: off', frame)

    def test_cost_na(self):
        jl(self.root / 'live' / 'out.jsonl', [{'ev': 'gameplay', 't': 0.0}])
        _, frame = poll_and_render(self.root)
        self.assertIn('cost: n/a', frame)
        self.assertIn('no decision yet', frame)

    def test_rules_decider_costs_nothing(self):
        jl(self.root / 'transcript.jsonl', [decision(1, decider='rules', answers=None, cost_usd=None, request=None, usage=None)])
        run, frame = poll_and_render(self.root)
        self.assertIn('no model calls', frame)

    def test_truncation_to_width(self):
        make_run(self.root)
        for width in (30, 40, 60, 100):
            _, frame = poll_and_render(self.root, width=width)
            for ln in frame.split('\n'):
                self.assertLessEqual(lp.vlen(ln), width, ln)
        run = lp.Run(self.root, holders=lambda p: None)
        run.poll(grace_s=0)
        coloured = lp.render(run.snapshot(), 40, 50, color=True)
        self.assertIn('\x1b[', coloured)
        for ln in coloured.split('\n'):
            self.assertLessEqual(lp.vlen(ln), 40, ln)

    def test_height_drops_oldest_history_first(self):
        make_run(self.root)
        rows = [{'kind': 'x', 'sub': str(i), 'severity': 'error', 'side': 's', 'text': f'finding number {i}', 'game_s': float(i)} for i in range(30)]
        jl(self.root / 'findings.jsonl', rows)
        _, tall = poll_and_render(self.root, height=100)
        _, short = poll_and_render(self.root, height=36)
        self.assertLessEqual(len(short.split('\n')), 36)
        self.assertIn('finding number 29', short)
        self.assertNotIn('finding number 0', short)
        self.assertIn('finding number 0', tall)
        for needle in ('▶ push-open', 'RUN ENDED', 'segment test-door-talk', 'WORLD'):   # the headline sections stay
            self.assertIn(needle, short)

    def test_many_candidates_shed_least_likely_first(self):
        make_run(self.root)
        cands = [{'label': f'cand-{i}', 'lines': ['wait 1'], 'text': f'candidate number {i}'} for i in range(12)]
        probs = [{'value': f'cand-{i}', 'probability': round(0.02 + i * 0.01, 2)} for i in range(12)]
        probs[5]['probability'] = 0.5
        answers = [{'type': 'choice', 'name': 'next_step', 'choice': 'cand-5', 'confidence': 0.5, 'probabilities': probs}]
        jl(self.root / 'transcript.jsonl', [decision(9, 'cand-5', candidates=cands, answers=answers)], 'a')
        _, tall = poll_and_render(self.root, height=60)
        _, short = poll_and_render(self.root, height=30)
        for i in range(12):
            self.assertIn(f'candidate number {i}', tall)
        self.assertLessEqual(len(short.split('\n')), 30)
        self.assertIn('▶ cand-5', short)
        self.assertIn('candidate number 11', short)      # the likelier ones stay
        self.assertNotIn('candidate number 0', short)    # the least likely go first
        for needle in ('WORLD', 'BUGS', 'RUN ENDED'):
            self.assertIn(needle, short)

    def test_section_error_is_contained(self):
        make_run(self.root)
        run = lp.Run(self.root, holders=lambda p: None)
        run.poll(grace_s=0)
        snap = run.snapshot()
        snap['state'] = 5   # an odd field: WORLD cannot draw it
        frame = lp.render(snap, 72, 50)
        self.assertIn('world: ? (', frame)
        self.assertIn('▶ push-open', frame)
        self.assertIn('RUN ENDED', frame)

    def test_stale_state_is_red(self):
        make_run(self.root, ended=False, summary=False)
        run = lp.Run(self.root, holders=lambda p: None)
        run.poll(grace_s=0)
        old = run.sta.mtime - 30.0
        os.utime(run.sta.path, (old, old))
        run.poll()
        snap = run.snapshot(now=run.sta.mtime + 30.0)
        self.assertGreater(snap['state_age'], lp.STALE_STATE_S)
        self.assertIn('\x1b[1;31mstate 30.0 s ago', lp.render(snap, 72, 50, color=True))
        fresh = run.snapshot(now=run.sta.mtime + 0.4)
        self.assertNotIn('\x1b[1;31mstate', lp.render(fresh, 72, 50, color=True))
        self.assertIn('state 0.4 s ago', lp.render(fresh, 72, 50))


class TailTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'run'
        self.addCleanup(self.tmp.cleanup)

    def test_partial_last_line_waits(self):
        self.root.mkdir()
        t = self.root / 'transcript.jsonl'
        line = json.dumps(decision(3))
        t.write_text(json.dumps(decision(1)) + '\n' + 'not json at all\n' + line[:50])
        run = lp.Run(self.root, holders=lambda p: None)
        run.poll()
        self.assertEqual([d['n'] for d in run.decisions], [1])   # the bad line is skipped, the partial one waits
        with open(t, 'a') as f:
            f.write(line[50:] + '\n')
        run.poll()
        self.assertEqual([d['n'] for d in run.decisions], [1, 3])
        self.assertEqual(run.n_dec, 2)

    def test_missing_files_and_late_appearance(self):
        run = lp.Run(self.root, holders=lambda p: None)
        run.poll()
        self.assertFalse(run.started)
        (self.root / 'live').mkdir(parents=True)
        jl(self.root / 'live' / 'out.jsonl', [{'ev': 'gameplay', 't': 0.0}])
        run.poll()
        self.assertTrue(run.started)

    def test_never_writes_into_the_run_folder(self):
        make_run(self.root)
        before = sorted((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in self.root.rglob('*'))
        run = lp.Run(self.root, holders=lambda p: None)
        for _ in range(3):
            run.poll()
            lp.render(run.snapshot(), 72, 50)
        after = sorted((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in self.root.rglob('*'))
        self.assertEqual(before, after)

    def test_bounded_memory(self):
        self.root.mkdir()
        jl(self.root / 'transcript.jsonl', [decision(i) for i in range(1, 400)])
        run = lp.Run(self.root, holders=lambda p: None)
        run.poll()
        self.assertEqual(run.n_dec, 399)
        self.assertLessEqual(len(run.decisions), 60)
        self.assertEqual(run.decisions[-1]['n'], 399)

    def test_big_state_journal_reads_only_the_tail(self):
        (self.root / 'live').mkdir(parents=True)
        rows = [{'t': float(i), 'map': 'M', 'pos': [i, 0, 0], 'life': 4, 'max_life': 12, 'frame': i} for i in range(5000)]
        jl(self.root / 'live' / 'state.jsonl', rows)
        run = lp.Run(self.root, holders=lambda p: None)
        run.poll()
        self.assertEqual(run.state['frame'], 4999)
        self.assertLess(run.sta.off, 10_000_000)


class EndTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'run'
        self.addCleanup(self.tmp.cleanup)

    def test_done_event_ends_after_grace_only(self):
        make_run(self.root, summary=False)
        clock = [100.0]
        run = lp.Run(self.root, mono=lambda: clock[0], holders=lambda p: ['alive'])
        run.poll(grace_s=4.0)
        self.assertIsNone(run.ended)
        clock[0] += 5.0
        run.poll(grace_s=4.0)
        self.assertIn('game done', run.ended)

    def test_summary_json_ends_with_its_outcome(self):
        make_run(self.root, ended=False)
        run, frame = poll_and_render(self.root)
        self.assertEqual(run.ended, 'budget: 110 s of game time')
        self.assertIn('RUN ENDED: budget: 110 s of game time', frame)

    def test_writer_gone_and_no_growth_ends(self):
        make_run(self.root, ended=False, summary=False)
        clock = [100.0]
        holders = [['pid']]
        run = lp.Run(self.root, mono=lambda: clock[0], holders=lambda p: holders[0])
        run.poll()
        clock[0] += 60.0
        run.poll()
        self.assertIsNone(run.ended, 'a live writer keeps the run going however still it is')
        holders[0] = []
        clock[0] += 3.0   # (the holders answer is cached for 2 s)
        run.poll()
        self.assertIn('writer process is gone', run.ended)

    def test_writer_gone_but_recent_growth_does_not_end_yet(self):
        make_run(self.root, ended=False, summary=False)
        clock = [100.0]
        run = lp.Run(self.root, mono=lambda: clock[0], holders=lambda p: [])
        run.poll()
        clock[0] += 10.0
        run.poll()
        self.assertIsNone(run.ended, 'no growth for only 10 s')
        clock[0] += 11.0
        run.poll()
        self.assertIn('writer process is gone', run.ended)

    def test_unreadable_proc_never_ends_a_run(self):
        make_run(self.root, ended=False, summary=False)
        clock = [100.0]
        run = lp.Run(self.root, mono=lambda: clock[0], holders=lambda p: None)
        run.poll()
        clock[0] += 500.0
        run.poll()
        self.assertIsNone(run.ended)

    def test_growth_resets_the_stall(self):
        make_run(self.root, ended=False, summary=False)
        clock = [100.0]
        run = lp.Run(self.root, mono=lambda: clock[0], holders=lambda p: [])
        run.poll()
        clock[0] += 15.0
        jl(self.root / 'transcript.jsonl', [result(3, 'done')], 'a')
        run.poll()
        clock[0] += 15.0
        run.poll()
        self.assertIsNone(run.ended)


class CommandTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_waiting_for_a_folder_that_does_not_exist(self):
        out = io.StringIO()
        code = lp.main([str(Path(self.tmp.name) / 'later' / 'run-1'), '--once', '--width', '60'], out)
        text = out.getvalue()
        self.assertEqual(code, 0)
        self.assertIn('waiting for', text)
        self.assertIn('run-1', text)
        self.assertIn('(the game is queued behind other runs)', text)
        self.assertIn('elapsed', text)
        for ln in text.split('\n'):
            self.assertLessEqual(lp.vlen(ln), 60)

    def test_waiting_frame_function(self):
        frame = lp.render_waiting('/x/run', 125, 80, 50)
        self.assertIn('waiting for /x/run (the game is queued behind other runs)', frame)
        self.assertIn('elapsed 02:05', frame)

    def test_once_prints_one_frame(self):
        root = make_run(Path(self.tmp.name) / 'run')
        out = io.StringIO()
        code = lp.main([str(root), '--once', '--width', '72'], out)
        self.assertEqual(code, 0)
        self.assertIn('RUN ENDED', out.getvalue())
        self.assertNotIn('\x1b', out.getvalue())   # not a TTY: no escape sequences

    def test_live_mode_ends_cleanly_and_restores_the_cursor(self):
        root = make_run(Path(self.tmp.name) / 'run')

        class Tty(io.StringIO):
            def isatty(self):
                return True
        out = Tty()
        code = lp.main([str(root), '--interval', '0.05', '--width', '72', '--height', '45'], out)
        text = out.getvalue()
        self.assertEqual(code, 0)
        self.assertTrue(text.startswith(lp.HIDE))
        self.assertIn(lp.HOME, text)
        self.assertTrue(text.rstrip('\n').endswith(lp.SHOW))
        self.assertIn('RUN ENDED', text)

    def test_wait_gives_up(self):
        class Tty(io.StringIO):
            def isatty(self):
                return True
        out = Tty()
        code = lp.main([str(Path(self.tmp.name) / 'never'), '--interval', '0.05', '--wait', '0.2'], out)
        self.assertEqual(code, 1)
        self.assertIn('gave up waiting', out.getvalue())
        self.assertTrue(out.getvalue().rstrip('\n').endswith(lp.SHOW))


class ParseTest(unittest.TestCase):
    def test_pilot_command_line(self):
        argv = ['/usr/bin/python3', '-I', '/p/pilot/pilot.py', 'run', 'segments/x.toml', '--decider', 'openai-decisions', '--max-decisions', '40', '--vision', 'on', '--planner']
        a = lp.parse_pilot_args(argv, '/p/pilot')
        self.assertEqual((a['decider'], a['max-decisions'], a['vision'], a['planner']), ('openai-decisions', '40', 'on', True))
        self.assertTrue(a['segment'].endswith('segments/x.toml'))
        self.assertEqual(lp.parse_pilot_args(['/bin/sleep', '1'], '/'), {})

    def test_segment_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 's.toml'
            p.write_text('name = "s"\nwhat = "w"\narea = "A"\nmax_decisions = 30\n[place]\nto = "TestTown"\nage = "adult"\nhour = 22\n'
                         '[[goal]]\nname = "g1"\nwhat = "go"\nflag = "X=1"\ntargets = [{name = "t1", at = [1.5, 2.5], kind = "reach"}]\n')
            seg = lp.load_segment(p)
            self.assertEqual((seg['name'], seg['max_decisions'], seg['goals'][0]['name']), ('s', 30, 'g1'))
            self.assertEqual(seg['targets']['t1']['x'], 1.5)
            self.assertEqual(seg['place']['hour'], 22)

    def test_max_decisions_from_the_command_line(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_run(Path(d) / 'run', summary=False, ended=False)
            run = lp.Run(root, holders=lambda p: None)
            run.cmd = {'max-decisions': '40'}
            run.poll()
            frame = lp.render(run.snapshot(), 72, 50)
            self.assertIn('decision 2/40', frame)


if __name__ == '__main__':
    unittest.main()
