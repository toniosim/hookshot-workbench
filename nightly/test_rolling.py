"""Game-free rolling decisions, cadence, unchanged skipping, budgets and hunt handoffs.

Only made-up measurements and temporary files. --shared-dir can select the shared
regression revision under test; production rolling mode always uses its configured live tool.
"""
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace
import argparse
import copy
import json
import os
import tempfile
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import rolling
from common import HARN, put, env_clean
from compare import compare_paired

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('--shared-dir', type=Path, default=HARN / 'regress')
known, remaining = parser.parse_known_args()
sys.argv = [sys.argv[0], *remaining]


def case():
    return {'schema_version': 1, 'kind': 'timing', 'repetitions': 2,
            'quiet_cores': 3, 'quiet_peak_cores': 6, 'repeat_tolerance': .05,
            'name': 'made-up', 'seconds': 90, 'max_retries': 1, 'max_load': 8, 'grace_seconds': 15,
            'measure': {'name': 'mean_ms', 'direction': 'higher-worse'}}


def rows(values):
    roles = ('candidate', 'reference', 'candidate', 'reference')
    return [{'role': role, 'result': {'valid': True, 'disturbed': False, 'kernel_errors': 0,
             'load_before': 200.0, 'load_after': 150.0, 'others_cores_window': 1.5,
             'others_cores_peak': 2.0, 'value': value, 'summary': 'made-up run', 'evidence': ['fixture']}}
            for role, value in zip(roles, values)]


class PairedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = rolling.load_module('rolling_test_rules', known.shared_dir / 'regress.py')
        assert callable(getattr(cls.shared, 'repeats_agree', None)), 'new quiet/repeat-rule API required'

    def test_confirmed_regression_uses_observed_bands(self):
        decision = compare_paired(rows([12, 10, 12.1, 10.1]), case(), self.shared)
        self.assertEqual(decision['state'], 'regression')
        self.assertEqual(decision['measure']['good_max'], 10.1)
        self.assertEqual(decision['measure']['bad_min'], 12)
        self.assertAlmostEqual(decision['combined_repeat_spread'], .2)

    def test_both_pairs_must_agree_outside_repeat_spread(self):
        self.assertEqual(compare_paired(rows([10.1, 10, 10.3, 10.2]), case(), self.shared)['state'], 'within-repeat-spread')
        self.assertEqual(compare_paired(rows([10.1, 10, 10, 10.1]), case(), self.shared)['state'], 'within-repeat-spread')
        self.assertEqual(compare_paired(rows([9, 10, 9.01, 10.01]), case(), self.shared)['state'], 'improvement')

    def test_quiet_rule_not_lagging_load_average(self):
        data = rows([12, 10, 12.1, 10.1])
        self.assertEqual(compare_paired(data, case(), self.shared)['state'], 'regression')
        data[1]['result']['others_cores_window'] = 3
        self.assertEqual(compare_paired(data, case(), self.shared)['state'], 'not-judged')
        data[1]['result']['others_cores_window'] = 2
        data[2]['result']['others_cores_peak'] = 6.01
        self.assertEqual(compare_paired(data, case(), self.shared)['state'], 'not-judged')

    def test_each_arm_repeats_within_five_percent(self):
        self.assertEqual(compare_paired(rows([12, 10, 13, 10.1]), case(), self.shared)['state'], 'not-judged')
        self.assertEqual(compare_paired(rows([12, 10, 12.1, 11]), case(), self.shared)['state'], 'not-judged')

    def test_lower_worse_and_bad_inputs(self):
        scenario = case()
        scenario['measure']['direction'] = 'lower-worse'
        decision = compare_paired(rows([80, 100, 79.9, 100.1]), scenario, self.shared)
        self.assertEqual(decision['state'], 'regression')
        self.assertEqual(decision['measure']['good_max'], -100)
        self.assertEqual(decision['measure']['bad_min'], -80)
        for value in (None, float('nan'), True):
            data = rows([12, 10, 12.1, 10.1])
            data[0]['result']['value'] = value
            self.assertEqual(compare_paired(data, case(), self.shared)['state'], 'not-judged')
        data = rows([12, 10, 12.1, 10.1])
        data[0]['result']['valid'] = False
        self.assertEqual(compare_paired(data, case(), self.shared)['state'], 'not-judged')

    def test_exact_new_previous_order_and_no_partial_pair(self):
        data = rows([12, 10, 12.1, 10.1])
        self.assertEqual(compare_paired(data[:3], case(), self.shared)['state'], 'not-judged')
        data[0], data[1] = data[1], data[0]
        self.assertEqual(compare_paired(data, case(), self.shared)['state'], 'not-judged')


class CycleTests(unittest.TestCase):
    def test_three_hours_and_moved_head_are_both_required(self):
        started = '2000-01-01T00:00:00+00:00'
        epoch = datetime.fromisoformat(started).timestamp()
        previous = {'commit': 'a' * 40}
        self.assertEqual(rolling.target_decision('b'*40, previous, started, epoch+10799, True), 'not-due')
        self.assertEqual(rolling.target_decision('b'*40, previous, started, epoch+10800, True), 'run')
        self.assertEqual(rolling.target_decision('a'*40, previous, started, epoch+10800, True), 'unchanged')
        self.assertEqual(rolling.target_decision('b'*40, previous, started, epoch+1, False), 'run')

    def test_unchanged_fetches_once_and_never_builds_or_runs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / 'rolling/state.json'
            put(state, {'last_completed': {'commit': 'a'*40}, 'last_started': '2000-01-01T00:00:00+00:00'})
            with patch.object(rolling, 'ROOT', root / 'rolling'), patch.object(rolling, 'LOCAL', root), \
                 patch.object(rolling, 'capture', side_effect=['fetched\n', 'a'*40]) as git, \
                 patch.object(rolling.builder, 'run', side_effect=AssertionError('must not build')), \
                 patch.object(rolling, 'run_hold', side_effect=AssertionError('must not request GPU')):
                result = rolling.cycle({'enabled': True, 'repo': 'fixture'})
                self.assertEqual(result['status'], 'unchanged')
                self.assertEqual(git.call_count, 2)  # one fetch, one immutable rev-parse
                self.assertEqual(git.call_args_list[0].args[0][-3:], ['fetch', 'origin', 'main'])
            self.assertFalse((root / 'rolling/raw').exists())

    def test_automatic_check_does_not_fetch_before_due(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            put(root / 'rolling/state.json', {'last_started': '2000-01-01T00:00:00+00:00'})
            epoch = datetime.fromisoformat('2000-01-01T00:00:00+00:00').timestamp()
            with patch.object(rolling, 'ROOT', root / 'rolling'), patch.object(rolling, 'LOCAL', root), \
                 patch.object(rolling.time, 'time', return_value=epoch+100), \
                 patch.object(rolling, 'capture', side_effect=AssertionError('must not fetch')):
                self.assertEqual(rolling.cycle({'enabled': True}, automatic=True)['status'], 'not-due')

    def test_plan_fits_eight_minutes(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            config = {'python': 'python', 'regress_dir': '/fixture'}
            entries = [{'scenario': '/fixture/scenario'}] * 4
            scenarios = [{'seconds': 90, 'grace_seconds': 15, 'settle_seconds': 100}] * 4
            path = rolling.make_plan(config, out, 'fits', entries, scenarios, True)
            plan = json.loads(path.read_text())
            self.assertEqual(plan['settle_seconds'], 50)
            self.assertLessEqual(plan['settle_seconds'] + 10 + 4 * (90+15), 480)
            with self.assertRaisesRegex(ValueError, 'eight minutes'):
                rolling.make_plan(config, out, 'too-long', entries * 2, scenarios * 2, True)

    def test_cycle_never_spends_a_fourth_exclusive_hold(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            for i in range(3):
                put(folder / (str(i) + '.asked.json'), {'flags': ['--exclusive']})
            with patch.object(rolling, 'command', side_effect=AssertionError('must not launch')):
                with self.assertRaisesRegex(RuntimeError, 'budget'):
                    rolling.run_hold({}, {}, folder / 'fourth.json', True)

    def test_inherited_game_switches_cannot_change_scene(self):
        with patch.dict(os.environ, {'HOS_FPS_MAX': '999', 'RX_VK_FAKE': '1', 'HOOKSHOT_FAKE': '1'}):
            cleaned = env_clean(game=True)
            self.assertNotIn('HOS_FPS_MAX', cleaned)
            self.assertNotIn('RX_VK_FAKE', cleaned)
            self.assertNotIn('HOOKSHOT_FAKE', cleaned)

    def test_handoff_is_real_schema_and_never_starts_hunt(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            config = {'python': 'python', 'regress_dir': '/fixture/regress', 'repo': '/fixture/repo'}
            build_config = {key: '/fixture' for key in ('cpm', 'worktree', 'romfs', 'exefs', 'build_gate', 'full_build_lock')}
            build_config['build_jobs'] = 2
            (out / 'old').mkdir()
            (out / 'new').mkdir()
            before = {'commit': 'a'*40, 'copy': str(out / 'old'), 'binary_sha256': {'hookshot': '1'*64}, 'source_stamp': '11111111'}
            after = {'commit': 'b'*40, 'source_commit': 'c'*40, 'copy': str(out / 'new'),
                     'binary_sha256': {'hookshot': '2'*64}, 'source_stamp': '22222222'}
            scene = {'id': 'made-up', 'scenario': {**case(), 'run': {'expect_log': ['source 22222222', 'fixture device']}},
                     'runs': [{'output': '/fixture/run'}]}
            decision = {'state': 'regression', 'measure': {'name': 'mean_ms', 'direction': 'higher-worse',
                                                           'good_max': 10.1, 'bad_min': 12}}
            with patch.object(rolling, 'capture', side_effect=['fixture diagnostic patch', 'b Fix (#7)']), \
                 patch.object(rolling, 'command', side_effect=AssertionError('must not start hunt')):
                path = rolling.handoff(config, build_config, out, scene, decision, before, after)
            handoff = json.loads(Path(path).read_text())
            self.assertFalse(handoff['automatic_hunt_started'])
            self.assertEqual((handoff['good'], handoff['bad']), ('a'*40, 'b'*40))
            target = json.loads(Path(handoff['scenario']).read_text())
            self.assertEqual(target['measure'], decision['measure'])
            self.assertTrue(target['requires_regress_source_marker'])
            self.assertEqual(target['run']['expect_log'], ['fixture device'])
            self.assertEqual((out / 'old/regress-source.txt').read_text().strip(), '11111111')
            self.assertEqual((out / 'new/regress-source.txt').read_text().strip(), '22222222')
            self.assertEqual(set(target['build']['prebuilt']), {'a'*40, 'b'*40})
            self.assertIn('build_case.py', ' '.join(target['build_command']))
            self.assertIn('run_case.py', ' '.join(target['run_command']))


if __name__ == '__main__':
    print('Shared regression rules under test:', known.shared_dir, flush=True)
    unittest.main()
