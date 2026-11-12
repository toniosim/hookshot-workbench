#!/usr/bin/env python3
"""Evidence-first regression hunting. Scenario/build adapters are local JSON argv, never shell text."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

SCHEMA=1
GATE_VARS=('NX2NAVI_SLOT_DIR','NX2NAVI_INTEL_SLOT_DIR','NX2NAVI_SLOT_TEST','NX2NAVI_SLOT_NODESKTOP','NX2NAVI_IN_GATE')


def clean_env():
    return {k:v for k,v in os.environ.items() if k not in GATE_VARS}


def date():
    return subprocess.check_output(['date','-Iseconds'],text=True).strip()


def save(path,data):
    path=Path(path); temporary=path.with_name(path.name+'.tmp')
    temporary.write_text(json.dumps(data,indent=2)+'\n'); temporary.replace(path)


def git(repo,*args):
    return subprocess.check_output(['git','-C',str(repo),*args],text=True).strip()


def lift_key(repo,commit):
    tree=git(repo,'ls-tree','-r',commit,'--','nx2','third_party/a64-kit').splitlines()
    tree=[x for x in tree if not x.endswith('\tnx2/build.py')]
    # The lift hooks the HLE names, not the other host code. Never reuse a lift when the set changes.
    names=set()
    for f in git(repo,'ls-tree','--name-only',commit+':host').splitlines():
        if not f.endswith('.c'): continue
        source=git(repo,'show',commit+':host/'+f)
        names.update(re.findall(r'^void (imp_\w+)\(Ctx',source,re.M))
        names.update('imp_'+n for n in re.findall(r'^HLE\((\w+)\)',source,re.M))
    content='\n'.join(tree)+'\nHLE\n'+'\n'.join(sorted(names))
    return hashlib.sha256(content.encode()).hexdigest()


def groups(rows):
    out=[]
    for i,row in enumerate(rows):
        if not out or out[-1]['lift_key']!=row['lift_key']:
            out.append({'lift_key':row['lift_key'],'first':i,'last':i,'commits':[]})
        out[-1]['last']=i; out[-1]['commits'].append(row['commit'])
    return out


def history(repo,good,bad):
    good=git(repo,'rev-parse',good+'^{commit}'); bad=git(repo,'rev-parse',bad+'^{commit}')
    subprocess.run(['git','-C',str(repo),'merge-base','--is-ancestor',good,bad],check=True)
    ancestors=git(repo,'rev-list','--first-parent',bad).splitlines()
    if good not in ancestors: raise ValueError('good must be on bad\'s first-parent history')
    commits=[good]+git(repo,'rev-list','--first-parent','--reverse',good+'..'+bad).splitlines()
    rows=[]; keys={}
    for commit in commits:
        subject=git(repo,'show','-s','--format=%s',commit)
        # Most adjacent revisions share these subtree hashes. HLE changes remain part of each key.
        key=lift_key(repo,commit)
        rows.append({'commit':commit,'subject':subject,'prs':[int(n) for n in re.findall(r'#(\d+)',subject)],'lift_key':key})
        keys[key]=True
    return {'schema_version':SCHEMA,'good':good,'bad':bad,'commits':rows,'groups':groups(rows),
            'distinct_lifts':len(keys),'commits_in_range':len(rows)-1,'created':date()}


def classification(result,scenario):
    for key in ('valid','disturbed','kernel_errors','load_before','load_after','value','summary','evidence'):
        if key not in result: return 'invalid'
    if result['valid'] is not True or result['disturbed'] is not False or result['kernel_errors']!=0: return 'invalid'
    if not isinstance(result['summary'],str) or not isinstance(result['evidence'],list) or not result['evidence']: return 'invalid'
    loads=[result['load_before'],result['load_after'],result.get('load_max',0)]
    if any(isinstance(x,bool) or not isinstance(x,(float,int)) or not math.isfinite(x) for x in loads): return 'invalid'
    if scenario['kind']=='timing' and max(loads)>scenario.get('max_load',8): return 'disturbed'
    measure=scenario['measure']; value=result['value']
    if measure['direction']=='pass-fail': return ('good' if value else 'bad') if isinstance(value,bool) else 'invalid'
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value): return 'invalid'
    worse=value if measure['direction']=='higher-worse' else -value
    if worse<=measure['good_max']: return 'good'
    if worse>=measure['bad_min']: return 'bad'
    return 'ambiguous'


def paired_decision(runs,scenario,reference):
    n=scenario.get('repetitions',2)
    if len(runs)!=2*n: return 'retry'
    a=[classification(x['result'],scenario) for x in runs if x['role']=='reference']
    b=[classification(x['result'],scenario) for x in runs if x['role']=='candidate']
    if len(a)!=n or len(b)!=n or any(x!=reference for x in a): return 'retry'
    if all(x=='good' for x in b): return 'good'
    if all(x=='bad' for x in b): return 'bad'
    return 'retry'


def choose_candidate(rows,lo,hi,available):
    candidates=list(range(lo+1,hi))
    if not candidates: return None
    # Exhaust a reusable endpoint lift first; within that slice choose its midpoint.
    cached=[i for i in candidates if rows[i]['lift_key'] in available]
    pool=cached or candidates
    middle=(lo+hi)/2
    return min(pool,key=lambda i:(abs(i-middle),i))


def run_command(argv,log,timeout=None,env=None,cwd=None):
    with Path(log).open('w') as f:
        process=subprocess.Popen(argv,stdout=f,stderr=subprocess.STDOUT,env=env,cwd=cwd,start_new_session=True)
        try:
            code=process.wait(timeout=timeout)
        except (subprocess.TimeoutExpired,KeyboardInterrupt,InterruptedError):
            os.killpg(process.pid,signal.SIGTERM)
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL); process.wait()
            raise
        if code: raise RuntimeError(f'command exited {code}; see {log}')


def hold(plan_path):
    plan=json.loads(Path(plan_path).read_text()); gpu=plan['kind']!='check'
    if not 10<plan['max_hold_seconds']<=480 or plan['seconds']<=0 or plan['grace_seconds']<5:
        raise ValueError('invalid held-worker duration/reserve')
    if len(plan['entries'])*(plan['seconds']+plan['grace_seconds'])+10>plan['max_hold_seconds']:
        raise ValueError('run plan does not fit its hard hold limit')
    def interrupted(signum, frame):
        raise InterruptedError("held worker terminated; stopping its active process group")
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGALRM, interrupted)
    signal.setitimer(signal.ITIMER_REAL,plan['max_hold_seconds']-10)
    if gpu and not os.environ.get('NX2NAVI_IN_GATE'): raise ValueError('held worker is outside GPU gate')
    begin=time.monotonic(); runs=[]
    for entry in plan['entries']:
        # Hard wall reserve includes wrapper termination and evidence collection; no fifth run can spill the hold.
        left=plan['max_hold_seconds']-(time.monotonic()-begin)
        if left<plan['seconds']+plan['grace_seconds']: break
        out=Path(entry['output']); out.mkdir(parents=True)
        subst=entry|{'seconds':str(plan['seconds']),'scenario':plan['scenario']}
        argv=[part.format_map(subst) for part in plan['run_command']]
        try:
            run_command(argv,out/'adapter.log',timeout=min(left-2,plan['seconds']+plan['grace_seconds']),env=os.environ.copy())
            result=json.loads((out/'result.json').read_text())
        except InterruptedError:
            save(Path(plan_path).with_suffix('.runs.json'),runs)
            raise
        except (RuntimeError,subprocess.TimeoutExpired,OSError,ValueError) as exc:
            result={'valid':False,'disturbed':True,'kernel_errors':0,'load_before':os.getloadavg()[0],
                    'load_after':os.getloadavg()[0],'value':0,'summary':str(exc),'evidence':[str(out)]}
            save(out/'result.json',result)
        runs.append({'role':entry['role'],'commit':entry['commit'],'output':str(out),'result':result})
        save(Path(plan_path).with_suffix('.runs.json'),runs)
        if result.get('kernel_errors',0) or result.get('fatal',0): break
    save(Path(plan_path).with_suffix('.runs.json'),runs)
    signal.setitimer(signal.ITIMER_REAL,0)


class Hunt:
    def __init__(self,args,scenario,range_):
        self.args=args; self.scenario=scenario; self.range=range_; self.rows=range_['commits']; self.output=Path(args.output)
        self.steps=[]; self.built={}; self.donors={}; self.holds=0; self.used_steps=0; self.suspects=[]
        self.lo=0; self.hi=len(self.rows)-1; self.started=getattr(args,'started',time.monotonic())

    def remaining_time(self):
        return self.args.max_wall_seconds-(time.monotonic()-self.started)

    def budget(self):
        if self.remaining_time()<=0: raise RuntimeError('caller wall-time budget exhausted')
        if self.holds>=self.args.max_holds: raise RuntimeError('caller hold budget exhausted')

    def persist(self):
        save(self.output/'steps.json',self.steps)
        lines=['| Step | Role | Build | Value | Decision | Load before → after | Summary |','|---|---|---|---:|---|---|---|']
        for step in self.steps:
            for run in step['runs']:
                r=run['result']; summary=str(r.get('summary','')).replace('|','/').replace('\n',' ')
                lines.append(f"| {step['name']} | {run['role']} | {run['commit'][:12]} | {r.get('value')} | {classification(r,self.scenario)} | {r.get('load_before')} → {r.get('load_after')} | {summary} |")
        (self.output/'table.md').write_text('\n'.join(lines)+'\n')
        self.result('inconclusive','hunt in progress')

    def result(self,status,reason,first=None):
        data={'schema_version':SCHEMA,'status':status,'first_bad':first,'good':self.rows[self.lo]['commit'],
              'bad':self.rows[self.hi]['commit'],'remaining':[r['commit'] for r in self.rows[self.lo+1:self.hi+1]],
              'reason':reason,'holds_used':self.holds,'steps_used':self.used_steps,'suspects':self.suspects,
              'evidence':[str(self.output/x) for x in ('range.json','steps.json','table.md')],'updated':date()}
        save(self.output/'result.json',data); return data

    def build(self,index,reverts=()):
        row=self.rows[index]; key=(row['commit'],tuple(reverts))
        if key in self.built: return self.built[key]
        if self.remaining_time()<=0: raise RuntimeError('caller wall-time budget exhausted before build')
        label=row['commit'][:12]+('rev'+hashlib.sha256(','.join(reverts).encode()).hexdigest()[:8] if reverts else '')
        out=self.output/'builds'/label; out.mkdir(parents=True)
        root=Path(self.scenario.get('worktree_root',str(self.output/'worktrees'))).resolve(); root.mkdir(parents=True,exist_ok=True)
        work=root/(self.output.name+'-'+label)
        run_command(['git','-C',self.args.repo,'worktree','add','--detach',str(work),row['commit']],out/'worktree.log',timeout=self.remaining_time(),env=clean_env())
        for rev in reverts:
            run_command(['git','revert','--no-commit',rev],out/('revert-'+rev[:12]+'.log'),timeout=self.remaining_time(),env=clean_env(),cwd=work)
        # A revert outside the lift inputs can share the bad build. Otherwise force a full build.
        actual_key=row['lift_key']
        if reverts and git(work,'diff','HEAD','--','nx2',':(exclude)nx2/build.py','third_party/a64-kit','host'):
            actual_key+='-revert-'+hashlib.sha256(','.join(reverts).encode()).hexdigest()[:12]
        donor=self.donors.get(actual_key,'')
        substitutions={'commit':row['commit'],'worktree':str(work),'output':str(out),'lift_key':actual_key,
                       'donor_worktree':donor,'build_kind':'fast' if donor else 'full','reverts':','.join(reverts)}
        argv=[x.format_map(substitutions) for x in self.scenario['build_command']]
        save(out/'request.json',substitutions)
        run_command(argv,out/'adapter.log',timeout=self.remaining_time(),env=clean_env(),cwd=work)
        build=json.loads((out/'build.json').read_text())
        if build.get('commit')!=row['commit'] or build.get('lift_key')!=actual_key or not Path(build.get('copy','')).is_dir():
            raise ValueError('build adapter returned mismatched identity')
        build.update(worktree=str(work)); self.built[key]=build; self.donors[actual_key]=str(work)
        return build

    def compare(self,name,reference,candidate,reference_class):
        for retry in range(self.scenario.get('max_retries',1)+1):
            self.budget(); self.holds+=1
            entries=[]
            for repetition in range(self.scenario.get('repetitions',2)):
                for role,b in (('reference',reference),('candidate',candidate)):
                    entries.append({'role':role,'copy':b['copy'],'commit':b['commit'],
                                    'output':str(self.output/f'hold-{self.holds:02d}'/f'{repetition+1}-{role}')})
            plan={'kind':self.scenario['kind'],'entries':entries,'run_command':self.scenario['run_command'],
                  'scenario':str(Path(self.args.scenario).resolve()),'seconds':self.scenario['seconds'],
                  'max_hold_seconds':self.args.max_hold_seconds,'grace_seconds':self.scenario.get('grace_seconds',25)}
            plan_path=self.output/f'hold-{self.holds:02d}.json'; save(plan_path,plan)
            argv=[sys.executable,'-I',str(Path(__file__).resolve()),'_hold',str(plan_path)]
            if self.scenario['kind']!='check':
                gate=self.scenario.get('gpu_gate',str(Path.home()/'Games/nx2navi-gpu-slot'))
                flags=['--exclusive'] if self.scenario['kind']=='timing' else []
                if self.args.priority_authorized: flags=['--priority']+flags
                argv=[gate,*flags,'timeout','--signal=TERM','--kill-after=5',str(self.args.max_hold_seconds-5),*argv]
            try:
                run_command(argv,self.output/f'hold-{self.holds:02d}.log',timeout=self.remaining_time(),env=clean_env())
            finally:
                result_path=plan_path.with_suffix('.runs.json')
                runs=json.loads(result_path.read_text()) if result_path.exists() else []
                decision=paired_decision(runs,self.scenario,reference_class)
                self.steps.append({'name':name,'retry':retry,'hold':self.holds,'runs':runs,'decision':decision}); self.persist()
            if any(r['result'].get('kernel_errors',0) or r['result'].get('fatal',0) for r in runs): raise RuntimeError('GPU/game safety fault; no more runs')
            if decision!='retry': return decision
        raise RuntimeError(name+': disturbed, invalid, ambiguous or reference-drift pairs exhausted retries')

    def execute(self):
        if self.hi==0: return self.result('not_reproduced','endpoints are the same commit')
        try:
            good=self.build(0); bad=self.build(self.hi)
            outcome=self.compare('endpoints',good,bad,'good')
            if outcome!='bad': return self.result('not_reproduced','paired endpoints did not establish the requested regression')
            for suspect in self.args.suspect:
                commits=[git(self.args.repo,'rev-parse',s+'^{commit}') for s in suspect.split(',')]
                if any(c not in [r['commit'] for r in self.rows[1:]] for c in commits): raise ValueError('suspect outside good..bad')
                variant=self.build(self.hi,commits)
                outcome=self.compare('revert '+','.join(c[:8] for c in commits),bad,variant,'bad')
                self.suspects.append({'reverts':commits,'decision':outcome}); self.persist()
            # Reverts show interaction on the bad endpoint, not the first historical regression. Continue if requested.
            if self.args.suspects_only:
                return self.result('suspect_explains' if any(s['decision']=='good' for s in self.suspects) else 'inconclusive','named revert comparisons complete; historical first bad not bisected')
            while self.hi-self.lo>1:
                if self.used_steps>=self.args.max_steps: return self.result('inconclusive','bisection step allowance exhausted')
                self.budget()
                index=choose_candidate(self.rows,self.lo,self.hi,self.donors)
                candidate=self.build(index); self.used_steps+=1
                outcome=self.compare('bisect '+str(self.used_steps),good,candidate,'good')
                if outcome=='good': self.lo=index
                else: self.hi=index
                self.persist()
            return self.result('first_bad','adjacent tested good/bad boundary; assumes the tested predicate is monotonic in this range',self.rows[self.hi]['commit'])
        except (RuntimeError,ValueError,OSError,subprocess.SubprocessError,KeyboardInterrupt) as exc:
            return self.result('inconclusive',str(exc))


def validate(s,args):
    if s.get('schema_version')!=SCHEMA: raise ValueError('unsupported scenario schema')
    if s['kind'] not in ('timing','game-check','check'): raise ValueError('unknown scenario kind')
    if s['kind']=='timing' and not args.exclusive_authorized: raise ValueError('timing requires explicit --exclusive-authorized')
    if s['kind']!='timing' and s['measure']['direction']!='pass-fail': raise ValueError('numeric decisions require timing holds')
    if s['measure']['direction'] not in ('higher-worse','lower-worse','pass-fail'): raise ValueError('unknown measure direction')
    if s['measure']['direction']!='pass-fail':
        a,b=s['measure']['good_max'],s['measure']['bad_min']
        if not all(isinstance(x,(int,float)) and math.isfinite(x) for x in (a,b)) or not a<b: raise ValueError('good/bad bands must be finite and non-overlapping')
    if not 0<args.max_hold_seconds<=480: raise ValueError('hold must be within 480 seconds')
    if min(args.max_holds,args.max_steps,args.max_wall_seconds)<=0: raise ValueError('budgets must be positive')
    if s.get('repetitions',2)<2 or s.get('max_retries',1)<0: raise ValueError('at least two repetitions, nonnegative retry count')
    if s['seconds']<=0 or 2*s.get('repetitions',2)*(s['seconds']+s.get('grace_seconds',25))+5>args.max_hold_seconds:
        raise ValueError('paired runs and termination/evidence reserve do not fit the allowed hold')
    for key in ('build_command','run_command'):
        if not isinstance(s[key],list) or not s[key] or not all(isinstance(x,str) for x in s[key]): raise ValueError(key+' must be an argv list')


def main():
    if len(sys.argv)>1 and sys.argv[1]=='_hold': hold(sys.argv[2]); return
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('command',choices=['plan','hunt'])
    for key in ('repo','good','bad','output'): p.add_argument('--'+key,required=True)
    p.add_argument('--scenario'); p.add_argument('--max-steps',type=int,default=9)
    p.add_argument('--max-holds',type=int,default=1); p.add_argument('--max-hold-seconds',type=int,default=480)
    p.add_argument('--max-wall-seconds',type=int,default=5400)
    p.add_argument('--exclusive-authorized',action='store_true'); p.add_argument('--priority-authorized',action='store_true')
    p.add_argument('--suspect',action='append',default=[]); p.add_argument('--suspects-only',action='store_true')
    a=p.parse_args(); a.repo=str(Path(a.repo).resolve()); a.output=str(Path(a.output).resolve())
    a.started=time.monotonic()
    s=None
    if a.command=='hunt':
        if not a.scenario: p.error('hunt needs --scenario')
        s=json.loads(Path(a.scenario).read_text()); validate(s,a)
    Path(a.output).mkdir(parents=True,exist_ok=False)
    r=history(a.repo,a.good,a.bad); save(Path(a.output)/'range.json',r)
    if a.command=='plan': print(json.dumps(r,indent=2)); return
    save(Path(a.output)/'scenario.json',s)
    h=Hunt(a,s,r); print(json.dumps(h.execute(),indent=2))


if __name__=='__main__': main()
