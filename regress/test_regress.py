#!/usr/bin/env python3
"""Made-up histories and synthetic adapter runs; no game, device or network."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('regress',HERE/'regress.py')
r=importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
SCENARIO={'schema_version':1,'kind':'timing','seconds':60,'repetitions':2,'max_retries':1,'max_load':8,
          'measure':{'name':'ms','direction':'higher-worse','good_max':10,'bad_min':15},
          'build_command':['builder'],'run_command':['runner']}


def result(value,**kw):
    return {'value':value,'valid':True,'disturbed':False,'kernel_errors':0,'load_before':1,'load_after':2,
            'summary':'synthetic fixture','evidence':['fixture']}|kw


def arguments(output):
    return argparse.Namespace(output=str(output),repo='',scenario='',max_holds=20,max_steps=9,max_wall_seconds=100,
                              max_hold_seconds=480,exclusive_authorized=True,priority_authorized=False,suspect=[],suspects_only=False)


class Decisions(unittest.TestCase):
    def test_bands(self):
        for value,want in ((9,'good'),(10,'good'),(12,'ambiguous'),(15,'bad'),(16,'bad')):
            self.assertEqual(r.classification(result(value),SCENARIO),want)
    def test_disturbed_never_decides(self):
        for kw in ({'disturbed':True},{'valid':False},{'load_before':8.01},{'load_after':9},{'load_max':9},{'kernel_errors':1}):
            self.assertNotIn(r.classification(result(20,**kw),SCENARIO),('good','bad'))
    def test_invalid_numeric(self):
        for value in (float('nan'),float('inf'),'20',True):
            self.assertEqual(r.classification(result(value),SCENARIO),'invalid')
        self.assertEqual(r.classification({},SCENARIO),'invalid')
    def test_lower_and_pass(self):
        s=SCENARIO|{'measure':{'name':'fps','direction':'lower-worse','good_max':-90,'bad_min':-70}}
        self.assertEqual(r.classification(result(100),s),'good')
        self.assertEqual(r.classification(result(60),s),'bad')
        s=SCENARIO|{'kind':'game-check','measure':{'direction':'pass-fail'}}
        self.assertEqual(r.classification(result(True,load_before=50),s),'good')
        self.assertEqual(r.classification(result(False),s),'bad')
        self.assertEqual(r.classification(result(1),s),'invalid')
    def test_pair_requires_every_reference_and_candidate(self):
        runs=[{'role':role,'result':result(v)} for role,v in [('reference',9),('candidate',16),('reference',10),('candidate',15)]]
        self.assertEqual(r.paired_decision(runs,SCENARIO,'good'),'bad')
        runs[-1]['result']['value']=12
        self.assertEqual(r.paired_decision(runs,SCENARIO,'good'),'retry')
        runs[-1]['result']['value']=16; runs[0]['result']['value']=11
        self.assertEqual(r.paired_decision(runs,SCENARIO,'good'),'retry')
        self.assertEqual(r.paired_decision(runs[:2],SCENARIO,'good'),'retry')
    def test_budget_validation(self):
        a=arguments('unused'); r.validate(SCENARIO,a)
        a.exclusive_authorized=False
        with self.assertRaises(ValueError): r.validate(SCENARIO,a)
        a.exclusive_authorized=True; a.max_hold_seconds=481
        with self.assertRaises(ValueError): r.validate(SCENARIO,a)
        a.max_hold_seconds=300
        with self.assertRaises(ValueError): r.validate(SCENARIO,a)
        a.max_hold_seconds=480
        with self.assertRaises(ValueError): r.validate(SCENARIO|{'seconds':100},a)
        with self.assertRaises(ValueError): r.validate(SCENARIO|{'measure':{'direction':'higher-worse','good_max':10,'bad_min':10}},a)
    def test_groups_and_reusable_selection(self):
        rows=[{'commit':str(i),'lift_key':k} for i,k in enumerate('aaabbcc')]
        self.assertEqual([(g['first'],g['last']) for g in r.groups(rows)],[(0,2),(3,4),(5,6)])
        self.assertEqual(r.choose_candidate(rows,0,6,{'a'}),2)
        self.assertEqual(r.choose_candidate(rows,0,6,set()),3)
        self.assertIsNone(r.choose_candidate(rows,2,3,set()))
    def test_stop_at_supported_boundary(self):
        with tempfile.TemporaryDirectory() as td:
            rows=[{'commit':str(i),'lift_key':'same'} for i in range(8)]
            h=r.Hunt(arguments(td),SCENARIO,{'commits':rows})
            h.build=lambda i,reverts=(): {'commit':str(i),'copy':td}
            h.compare=lambda name,ref,candidate,refclass: 'good' if int(candidate['commit'])<5 else 'bad'
            with patch.object(r,'date',return_value='test'):
                answer=h.execute()
            self.assertEqual(answer['status'],'first_bad'); self.assertEqual(answer['first_bad'],'5')
            self.assertEqual(answer['remaining'],['5'])
            h=r.Hunt(arguments(td),SCENARIO,{'commits':rows}); h.args.max_steps=1
            h.build=lambda i,reverts=(): {'commit':str(i),'copy':td}
            h.compare=lambda name,ref,candidate,refclass: 'good' if int(candidate['commit'])<5 else 'bad'
            with patch.object(r,'date',return_value='test'): answer=h.execute()
            self.assertEqual(answer['status'],'inconclusive'); self.assertIsNone(answer['first_bad'])
            self.assertEqual(answer['remaining'],['4','5','6','7'])
    def test_wall_and_hold_exhaustion(self):
        with tempfile.TemporaryDirectory() as td:
            rows=[{'commit':str(i),'lift_key':'same'} for i in range(3)]
            h=r.Hunt(arguments(td),SCENARIO,{'commits':rows})
            h.holds=h.args.max_holds
            with self.assertRaisesRegex(RuntimeError,'hold budget'): h.budget()
            h.holds=0; h.args.max_wall_seconds=-1
            with self.assertRaisesRegex(RuntimeError,'wall-time'): h.budget()


class GitHistory(unittest.TestCase):
    def test_keys_and_public_plan(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); repo=root/'repo'; repo.mkdir()
            def git(*a): return subprocess.check_output(['git','-C',str(repo),*a],text=True,stderr=subprocess.DEVNULL).strip()
            git('init'); (repo/'nx2').mkdir(); (repo/'host').mkdir(); (repo/'third_party/a64-kit').mkdir(parents=True)
            (repo/'nx2/lift.py').write_text('lift one\n'); (repo/'nx2/build.py').write_text('build one\n')
            (repo/'host/one.c').write_text('HLE(one) {}\n'); (repo/'third_party/a64-kit/a').write_text('kit\n')
            def commit(subject):
                git('add','.'); git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-m',subject)
                return git('rev-parse','HEAD')
            a=commit('first (#11)'); (repo/'nx2/build.py').write_text('build two\n'); b=commit('build (#12)')
            (repo/'nx2/lift.py').write_text('lift two\n'); c=commit('lift (#13)')
            (repo/'host/one.c').write_text('HLE(two) {}\n'); d=commit('hook (#14)')
            self.assertEqual(r.lift_key(repo,a),r.lift_key(repo,b))
            self.assertNotEqual(r.lift_key(repo,b),r.lift_key(repo,c))
            self.assertNotEqual(r.lift_key(repo,c),r.lift_key(repo,d))
            history=r.history(repo,a,d)
            self.assertEqual(history['commits_in_range'],3); self.assertEqual(history['distinct_lifts'],3)
            self.assertEqual(history['commits'][2]['prs'],[13])
            out=root/'plan'
            subprocess.run([sys.executable,'-I',str(HERE/'regress.py'),'plan','--repo',str(repo),'--good',a,'--bad',d,'--output',str(out)],check=True,stdout=subprocess.DEVNULL)
            self.assertEqual(json.loads((out/'range.json').read_text())['bad'],d)


class AdapterLogic(unittest.TestCase):
    def test_all_public_scripts_parse(self):
        for path in HERE.glob('*.py'):
            compile(path.read_text(),str(path),'exec')

    def test_frame_statistics_and_window(self):
        spec=importlib.util.spec_from_file_location('run_case',HERE/'run_case.py')
        runner=importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
        self.assertEqual(runner.statistics_of([10,10,20])['over16_7'],1)
        with tempfile.TemporaryDirectory() as td:
            path=Path(td); rows=['frame,time_s,frametime_ms']
            for i in range(4001): rows.append(f'{i},{i*.01:.4f},{0 if i==0 else 10}')
            (path/'frames.csv').write_text('\n'.join(rows)+'\n')
            m=runner.analyse(path,{'anchor':'first','from':5,'to':15})
            self.assertEqual(m['mean_ms'],10); self.assertEqual(m['frames'],1000)
            with self.assertRaisesRegex(AssertionError,'save-load'):
                runner.analyse(path,{'anchor':'load'})
            with self.assertRaisesRegex(AssertionError,'short measurement'):
                runner.analyse(path,{'anchor':'first','from':30,'to':60})

    def test_missing_evidence_and_malformed_load_rejected(self):
        self.assertEqual(r.classification(result(20,evidence=[]),SCENARIO),'invalid')
        self.assertEqual(r.classification(result(20,load_max='busy'),SCENARIO),'invalid')
        self.assertEqual(r.classification(result(20,load_max=float('nan')),SCENARIO),'invalid')


if __name__=='__main__': unittest.main(verbosity=2)
