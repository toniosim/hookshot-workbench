#!/usr/bin/env python3
"""Run a local Hookshot scenario through hs-run.sh inside an existing gate.

No scenario/game data lives here. The JSON's run object supplies user, input,
env, window, warmup/window selection and optional game-free validator command.
"""
import argparse
import collections
import csv
import json
import math
import os
from pathlib import Path
import re
import statistics
import subprocess
import threading
import time


def date():
    return subprocess.check_output(['date', '-Iseconds'], text=True).strip()


def statistics_of(values):
    assert values and all(math.isfinite(x) and x > 0 for x in values)
    slow = sorted(values, reverse=True)[:max(1, len(values)//100)]
    return {'frames': len(values), 'mean_ms': statistics.mean(values),
            'median_ms': statistics.median(values), 'fps': 1000/statistics.mean(values),
            'low1_fps': 1000/statistics.mean(slow), 'over16_7': sum(x > 16.7 for x in values),
            'over20': sum(x > 20 for x in values), 'over25': sum(x > 25 for x in values),
            'max_ms': max(values)}


def analyse(run, settings):
    with (run/'frames.csv').open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 2, 'no renderer frame samples'
    frames = [int(r['frame']) for r in rows]
    seconds = [float(r['time_s']) for r in rows]
    ms = [float(r['frametime_ms']) for r in rows]
    assert all(b == a+1 for a,b in zip(frames,frames[1:])), 'missing frames'
    assert all(b >= a for a,b in zip(seconds,seconds[1:])), 'time reversed'
    assert abs(sum(ms[1:])/1000-(seconds[-1]-seconds[0])) < .02, 'frame span mismatch'
    anchor = 0.0
    if settings.get('anchor','load') == 'load':
        gaps = [t for t,d in zip(seconds,ms) if d > settings.get('load_gap_ms',300) and t < settings.get('load_before',60)]
        assert gaps, 'no save-load gap: scene not verified'
        anchor = gaps[-1]
    lo, hi = anchor+settings.get('from',15), anchor+settings.get('to',45)
    indexes = [i for i,t in enumerate(seconds) if lo <= t <= hi]
    assert len(indexes)>2 and seconds[indexes[-1]]-seconds[indexes[0]] >= .9*(hi-lo), 'short measurement window'
    selected = [ms[i] for i in indexes[1:]]
    result = statistics_of(selected)
    result.update(anchor_s=anchor, from_s=lo, to_s=hi, first_frame=frames[indexes[0]]+1,last_frame=frames[indexes[-1]]+1)
    path=run/'readbacks.csv'
    if path.exists():
        with path.open() as f:
            rb=[r for r in csv.DictReader(f) if result['first_frame'] <= int(r['frame_begin']) <= result['last_frame']]
        counts=collections.Counter(int(r['frame_begin']) for r in rb if r['kind']=='invalidate' and int(r['eligible']))
        eligible=[r for r in rb if r['kind']=='invalidate' and int(r['eligible'])]
        waits=[float(r['wait_ms']) for r in eligible]
        result.update(readback_calls=len(rb), readback_eligible=len(eligible),
                      readbacks_per_frame=len(eligible)/(result['last_frame']-result['first_frame']+1),
                      readbacks_frame_max=max(counts.values(),default=0),
                      readback_wait_mean_ms=statistics.mean(waits) if waits else 0,
                      readback_wait_median_ms=statistics.median(waits) if waits else 0,
                      readback_wait_max_ms=max(waits,default=0),
                      readback_catchup_mean_ms=statistics.mean(float(r['catchup_ms']) for r in eligible) if eligible else 0,
                      readback_fallbacks=sum(int(r['fallback']) for r in eligible),
                      read_texels_calls=sum(r['kind']=='read_texels' for r in rb))
    return result


def kernel_lines(start, end):
    text=subprocess.check_output(['journalctl','-k','--since',start,'--until',end,'--no-pager'],text=True)
    lines=[x for x in text.splitlines() if 'NVRM' in x or 'kmemsysDoCacheOp' in x]
    mem=[x for x in lines if 'memMap_IMPL: CPU mapping not supported for addressSpace: 0x1' in x]
    oom=[x for x in lines if 'NV_ERR_NO_MEMORY' in x or ('NVRM' in x and ('rmStatus @ system_mem.c' in x or 'pRmApi->Alloc' in x))]
    bad=[x for x in lines if x not in mem and x not in oom]
    return text, {'kernel_errors':len(bad),'memmap_lines':len(mem),'no_memory_lines':len(oom),'no_memory_events':sum('NV_ERR_NO_MEMORY' in x for x in oom)}


def run_case(copy, output, scenario, seconds, commit):
    assert os.environ.get('NX2NAVI_IN_GATE'), 'must be called inside GPU gate'
    settings=scenario['run']; copy=Path(copy).resolve(); output=Path(output).resolve()
    assert copy.name.startswith('.hookshot-h-') and (copy/'hookshot').is_file()
    output.mkdir(parents=True,exist_ok=True)
    assert not (output/'start.txt').exists(), 'refusing to overwrite a run'
    # The inner wrapper does not acquire a second gate. Its ordinary caller performs these same preparations.
    fields={'copy.txt':str(copy),'seconds.txt':str(seconds),'input.txt':settings.get('input',''),
            'memmax':'','env-file.txt':'# empty: scenario supplies environment\n'}
    env=dict(settings.get('env',{}))
    assert not (copy/'mods').exists() and 'HOS_MODS' not in os.environ and 'HOS_MODS' not in env, 'mods must be absent for an unmodified comparison'
    env['RX_VK_READBACK_CSV']=str(output/'readbacks.csv')
    if settings.get('prepare'):
        (output/'prepare').touch()
    if settings.get('window'):
        switch=Path(settings.get('window_switch',str(Path.home()/'Games/.hookshot-harness/window-ok')))
        assert switch.exists(), 'window authorization switch is absent'
        for p in Path('/proc').iterdir():
            if not p.name.isdigit(): continue
            try:
                exe=(p/'exe').resolve()
                assert str(Path.home()/'Games/Hookshot/') not in str(exe), 'user play folder is running'
            except (FileNotFoundError,PermissionError):
                pass
        (output/'window').touch()
    for k,v in fields.items(): (output/k).write_text(v+'\n' if k != 'input.txt' else v)
    (output/'extra-env.txt').write_text(''.join(f'{k}={v}\n' for k,v in env.items()))
    source=settings.get('user')
    if source:
        subprocess.run(['cp','-a','--reflink=always',source,str(output/'user')],check=True)
    else: (output/'user').mkdir()
    samples=[]; stop=threading.Event()
    def sample():
        while not stop.is_set():
            rss=0; pids=[]
            for p in Path('/proc').iterdir():
                if not p.name.isdigit(): continue
                try:
                    if (p/'exe').resolve() != copy/'hookshot': continue
                    pids.append(p.name)
                    m=re.search(r'^VmRSS:\s+(\d+)',(p/'status').read_text(),re.M)
                    if m: rss+=int(m.group(1))/1024
                except (FileNotFoundError,PermissionError,ProcessLookupError): pass
            vram=0.0
            try:
                data=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,used_gpu_memory','--format=csv,noheader,nounits'],text=True,timeout=3)
                for line in data.splitlines():
                    pid,mb=line.split(',')
                    if pid.strip() in pids and mb.strip().isdigit(): vram+=float(mb)
            except (subprocess.SubprocessError,ValueError): pass
            samples.append({'monotonic_ns':time.monotonic_ns(),'rss_mb':rss,'vram_mb':vram,'pids':pids,'load':os.getloadavg()[0]})
            stop.wait(1)
    sampler=threading.Thread(target=sample,daemon=True); sampler.start()
    start=date()
    start_monotonic_ns=time.monotonic_ns()
    wrapper=settings.get('wrapper',str(Path.home()/'Games/.hookshot-harness/hs-run.sh'))
    with (output/'wrapper.log').open('w') as log:
        rc=subprocess.run([wrapper,'--inner',str(output)],stdout=log,stderr=subprocess.STDOUT).returncode
    stop.set(); sampler.join(); end=date()
    (output/'samples.json').write_text(json.dumps(samples)+'\n')
    result={'commit':commit,'start':start,'end':end,'valid':False,'disturbed':False,'value':0,
            'start_monotonic_ns':start_monotonic_ns,
            'load_before':float((output/'load-before.txt').read_text().split()[0]) if (output/'load-before.txt').exists() else os.getloadavg()[0],
            'load_after':float((output/'load-after.txt').read_text().split()[0]) if (output/'load-after.txt').exists() else os.getloadavg()[0],
            'evidence':[str(output)],'wrapper_exit':rc}
    journal,kernel=kernel_lines(start,end); result.update(kernel)
    (output/'kernel.txt').write_text(journal)
    text=(output/'hookshot_log.txt').read_text(errors='replace') if (output/'hookshot_log.txt').exists() else ''
    result['mods']={'folder_absent':not (copy/'mods').exists(),'HOS_MODS_unset':'HOS_MODS' not in os.environ,
                    'log':[line for line in text.splitlines() if re.search(r'\bmods?:',line,re.I)]}
    code=int((output/'exit.txt').read_text()) if (output/'exit.txt').exists() else -1
    result.update(exit=code,fatal=len(re.findall('FATAL|CRASH:|VK_ERROR_DEVICE_LOST|device lost',text)),
                  peak_rss_mb=max((x['rss_mb'] for x in samples),default=0),
                  peak_vram_mb=max((x['vram_mb'] for x in samples),default=0),
                  load_max=max((x['load'] for x in samples),default=0))
    try:
        assert rc==0 and code==(0 if settings.get('prepare') else 124), 'run did not reach its intended end'
        assert 'NVIDIA GeForce RTX 4090' in text or settings.get('device_pattern') and re.search(settings['device_pattern'],text), 'wrong/missing device'
        assert not result['fatal'] and not kernel['kernel_errors'] and kernel['no_memory_events']<=3, 'run/kernel fault'
        if settings.get('window'):
            state=(output/'window.txt').read_text()
            result['window']=state
            assert all(t in state for t in ('window=ok','active=same','others=same','screen=on')), 'window disturbed'
        if settings.get('prepare'):
            assert '@@done shaders' in text, 'preparation incomplete'
            measures={}
        else:
            measures=analyse(output,settings)
        result['measures']=measures
        result['value']=measures.get(scenario['measure']['name'],0)
        if scenario['measure']['direction']=='pass-fail': result['value']=True
        if 'validator_command' in settings:
            command=[s.format(output=str(output),copy=str(copy)) for s in settings['validator_command']]
            with (output/'validator.log').open('w') as log:
                valid=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT).returncode==0
            if scenario['measure']['direction']=='pass-fail': result['value']=valid
            else: assert valid, 'scenario validator failed'
        result['valid']=True
    except (AssertionError,OSError,ValueError,KeyError) as exc:
        result['problem']=str(exc)
    result['disturbed']=bool(result['fatal'] or result['kernel_errors'] or (scenario.get('kind')=='timing' and result['load_max']>scenario.get('max_load',8)) or (settings.get('window') and not result.get('valid')))
    result['summary']=f"{commit[:8]} exit={code} valid={result['valid']} disturbed={result['disturbed']} load={result['load_before']}->{result['load_after']} kernel={result['kernel_errors']} {result.get('measures',{})}"
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    (output/'summary.txt').write_text(result['summary']+'\n')
    print(result['summary'],flush=True)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('copy','output','scenario','commit'): p.add_argument('--'+name,required=True)
    p.add_argument('--seconds',type=int,required=True)
    a=p.parse_args(); scenario=json.loads(Path(a.scenario).read_text())
    run_case(a.copy,a.output,scenario,a.seconds,a.commit)


if __name__=='__main__': main()
