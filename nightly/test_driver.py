"""Game-free orchestration tests. Stand-ins exist only in tests; no game or GPU is started."""
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import json
import tempfile
import unittest
from unittest.mock import Mock, patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import monitor
import scenario
import hunt
from common import put

spec = importlib.util.spec_from_file_location('nightly_driver_tested', Path(__file__).with_name('hs-nightly.py'))
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)


class DriverTests(unittest.TestCase):
    def test_game_free_driver_and_completed_suite_resume(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            local = root / 'local'
            out = local / 'raw/2000-01-01'
            out.mkdir(parents=True)
            commit = 'a' * 40
            build = {'commit': commit, 'started': 'fixture', 'status': 'passed', 'copy': str(root / 'copy')}
            put(out / 'build.json', build)
            config = {'worktree': str(root / 'source'), 'copy_prefix': str(root / 'copy-'),
                      'drafts': str(root / 'drafts'), 'known_test_failures': [],
                      'gpu_scenarios_enabled': False, 'timer_enabled': False}
            args = SimpleNamespace(night='2000-01-01', resume_build=True, resume=False,
                                   game_free=False, rearm=True)
            tests = {'made-up-check': {'status': 'pass', 'seconds': 1}}
            with patch.object(driver, 'LOCAL', local), patch.object(driver, 'capture', return_value=commit), \
                 patch.object(driver, 'suite', return_value=tests) as suite, \
                 patch.object(monitor, 'wait_for_player_idle'), \
                 patch.object(driver.scenario, 'run', side_effect=AssertionError('GPU must not start')), \
                 patch.object(driver, 'arm', side_effect=AssertionError('timer must not arm')):
                self.assertEqual(driver.run(config, args), 0)
                args.resume = True
                self.assertEqual(driver.run(config, args), 0)
                self.assertEqual(suite.call_count, 1)
            state = json.loads((local / 'state.json').read_text())
            self.assertEqual(state['stage'], 'complete-game-free')
            self.assertFalse(state['clean'])
            self.assertEqual(state['scenarios'], 0)
            report = (local / 'reports/2000-01-01.md').read_text()
            self.assertIn('No gameplay baseline', report)
            self.assertEqual(json.loads((local / 'baselines/latest.json').read_text())['scenarios'], {})

    def test_timer_is_off_without_explicit_local_enable(self):
        with patch.object(driver, 'capture', side_effect=AssertionError('systemd must not be called')):
            with self.assertRaisesRegex(RuntimeError, 'disabled'):
                driver.arm({})

    def test_player_executable_and_working_folder(self):
        records = [{'pid': 1, 'exe': '/player/hookshot', 'cwd': '/elsewhere'},
                   {'pid': 2, 'exe': '/test/hookshot', 'cwd': '/player'},
                   {'pid': 3, 'exe': '/test/hookshot', 'cwd': '/test'},
                   {'pid': 4, 'exe': '/bin/sh', 'cwd': '/player'}]
        self.assertEqual([p['pid'] for p in monitor.player_games({'play_folder': '/player'}, records)], [1, 2])

    def test_two_quiet_minutes_restart_when_player_appears(self):
        player = [{'pid': 1, 'exe': '/player/hookshot', 'cwd': '/player'}]
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(monitor, 'processes', side_effect=[[], player, [], [], []]), \
             patch.object(monitor.time, 'monotonic', side_effect=[0, 119, 120, 239, 240]), \
             patch.object(monitor.threading, 'Event', return_value=SimpleNamespace(wait=lambda _: None)):
            log = Path(temporary) / 'idle.jsonl'
            monitor.wait_for_player_idle({'play_folder': '/player'}, log)
            rows = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual(len(rows), 5)
            self.assertEqual(rows[-1]['quiet_for_s'], 120)
            self.assertEqual(rows[1]['player_pids'], [1])

    def test_cut_short_never_becomes_regression(self):
        current = {'id': 'made-up', 'status': 'safety-stop', 'cut_short': True}
        self.assertEqual(driver.comparisons(None, 'fixture', current, [{'status': 'passed'}]), [])
        self.assertEqual(current['comparisons'], {})

    def make_run(self, temporary, steps=(), ctl=None):
        with patch.object(scenario, 'client_module', return_value=ctl or SimpleNamespace()):
            return scenario.Run({'gpu_scenarios_enabled': False}, Path(temporary) / 'copy',
                                {'id': 'made-up', 'seconds': 90, 'steps': list(steps)},
                                Path(temporary) / 'out', 'fixture')

    def test_disabled_scenario_never_creates_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            run = self.make_run(temporary)
            with patch.object(scenario.subprocess, 'Popen', side_effect=AssertionError('must not launch')):
                with self.assertRaisesRegex(RuntimeError, 'disabled'):
                    run.execute()
            self.assertFalse(run.out.exists())

    def test_player_stop_uses_clean_separate_control_connection(self):
        commands = []
        class Bridge:
            def __init__(self, *args, **kwargs):
                pass
            def request(self, command, **kwargs):
                commands.append(command)
                return {'ok': True}
            def close(self):
                commands.append('close')
        with tempfile.TemporaryDirectory() as temporary:
            run = self.make_run(temporary, ctl=SimpleNamespace(Bridge=Bridge))
            run.proc = SimpleNamespace(poll=lambda: None, wait=lambda **kwargs: 0)
            run.control_socket = Path(temporary) / 'fake-socket'
            run.monitor.faults = ['user game running from protected play folder']
            with patch.object(scenario, 'stop_group', side_effect=AssertionError('clean quit must be attempted')):
                run.stop_for_safety()
            self.assertEqual(commands, ['quit', 'close'])
            run.monitor.faults = ['driver fault']
            with patch.object(scenario, 'stop_group') as kill:
                run.stop_for_safety()
                kill.assert_called_once_with(run.proc)

    def test_option_round_trip_restores_after_failure(self):
        changes = []
        with tempfile.TemporaryDirectory() as temporary:
            run = self.make_run(temporary, [{'op': 'options', 'values': {'made-up-row': [1, 2]}}])
            run.out.mkdir()
            def request(command, **kwargs):
                if command == 'option_get':
                    return {'option': {'value': 0}}
                if command == 'option_set':
                    changes.append(kwargs['value'])
                    if kwargs['value'] == 2:
                        raise RuntimeError('made-up unreachable value')
                    return {'option': {'value': kwargs['value']}}
                raise AssertionError(command)
            run.request, run.shot, run.delay = request, Mock(), Mock()
            with self.assertRaisesRegex(RuntimeError, 'unreachable'):
                run.steps()
            self.assertEqual(changes, [1, 2, 0])

    def test_shared_hunt_handoff_does_not_grant_exclusive_access(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            config = {key: 'fixture' for key in ('python', 'cpm', 'build_copy', 'worktree', 'romfs', 'exefs',
                                                'build_gate', 'full_build_lock', 'repo')}
            config.update(build_jobs=2, quiet_load_max=8, hunt_game_checks=False)
            result = hunt.handoff(config, {'id': 'made-up', 'seconds': 60}, {'commit': 'a'*40},
                                  {'commit': 'b'*40}, {'kind': 'passed-now-fails'}, out)
            self.assertEqual(result['state'], 'ready-not-launched')
            self.assertNotIn('--exclusive-authorized', result['command'])
            self.assertEqual(result['command'][result['command'].index('--max-steps') + 1], '8')
            self.assertEqual(result['command'][result['command'].index('--max-wall-seconds') + 1], '5400')
            manifest = json.loads((out / 'hunt-scenario.json').read_text())
            self.assertEqual(manifest['kind'], 'game-check')
            self.assertIn('build_case.py', ' '.join(manifest['build_command']))


if __name__ == '__main__':
    unittest.main()
