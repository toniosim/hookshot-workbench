"""Read-only run sampling and fail-closed machine safety checks."""
from pathlib import Path
import json
import os
import re
import subprocess
import threading
import time
from common import HARN, text, stamp
from metrics import WARNING, ACTIVITY, VRAM


def processes():
    result = []
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            exe = os.readlink(proc / 'exe')
            cwd = os.readlink(proc / 'cwd')
            stat = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
            status = dict(re.findall(r'^(\w+):\s*(\d+)', (proc / 'status').read_text(), re.M))
            result.append({'pid': int(proc.name), 'exe': exe, 'cwd': cwd, 'comm': (proc / 'comm').read_text().strip(),
                           'cpu_s': (int(stat[11]) + int(stat[12])) / os.sysconf('SC_CLK_TCK'),
                           'rss_mib': int(status.get('VmRSS', 0)) / 1024})
        except (OSError, ValueError, IndexError):
            continue
    return result


def player_games(config, records):
    root = Path(config['play_folder'])
    return [p for p in records if Path(p['exe']).name in ('hookshot', 'hookshot.exe') and
            (Path(p['exe']).is_relative_to(root) or Path(p.get('cwd', '/')).is_relative_to(root))]


def wait_for_player_idle(config, log):
    """A continuous two-minute observation, reset whenever the protected game is seen."""
    log = Path(log)
    log.parent.mkdir(parents=True, exist_ok=True)
    quiet_since = None
    pause = threading.Event()
    with log.open('a') as output:
        while True:
            now = time.monotonic()
            players = player_games(config, processes())
            if players:
                quiet_since = None
            elif quiet_since is None:
                quiet_since = now
            output.write(json.dumps({'monotonic_s': now, 'player_pids': [p['pid'] for p in players],
                                     'quiet_for_s': now - quiet_since if quiet_since is not None else 0}) + '\n')
            output.flush()
            if quiet_since is not None and now - quiet_since >= 120:
                return
            pause.wait(1)


def resources(config, executable=None):
    mem = {k: int(v) / 1048576 for k, v in re.findall(r'^(\w+):\s*(\d+)', text('/proc/meminfo'), re.M)}
    psi = re.search(r'^full avg10=([\d.]+)', text('/proc/pressure/memory'), re.M)
    procs = processes()
    games = [p for p in procs if Path(p['exe']).name in ('hookshot', 'hookshot.exe')]
    mine = [p for p in games if executable and Path(p['exe']) == Path(executable)]
    compilers = [p for p in procs if re.match(r'(?:clang|cc1|g\+\+|gcc|ld\.lld|lld-link)', p['comm'])]
    reading = {'monotonic_s': time.monotonic(), 'load': list(os.getloadavg()),
               'available_gib': mem.get('MemAvailable'), 'swap_free_gib': mem.get('SwapFree'),
               'memory_psi_full': float(psi[1]) if psi else None,
               'game_pids': [p['pid'] for p in games], 'compiler_count': len(compilers),
               'other_games': len(games) - len(mine), 'own_pids': [p['pid'] for p in mine],
               'rss_mib': sum(p['rss_mib'] for p in mine) if mine else None,
               'cpu_s': sum(p['cpu_s'] for p in mine) if mine else None,
               'hyprland': sum(p['comm'] == 'Hyprland' for p in procs),
               'play_game': bool(player_games(config, games))}
    try:
        gpu = subprocess.run(['nvidia-smi', '--query-gpu=memory.used,memory.free,utilization.gpu,driver_version',
                              '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=5)
        if gpu.returncode == 0:
            vals = gpu.stdout.splitlines()[0].split(',')
            reading.update(gpu_total_mib=float(vals[0]), gpu_free_mib=float(vals[1]),
                           gpu_util_pct=float(vals[2]), gpu_driver=vals[3].strip())
        p = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,used_gpu_memory', '--format=csv,noheader,nounits'],
                           capture_output=True, text=True, timeout=5)
        own = [float(v) for pid, v in re.findall(r'^(\d+),\s*(\d+)\s*$', p.stdout, re.M)
               if int(pid) in reading['own_pids']]
        reading['gpu_process_mib'] = sum(own) if own else None
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        reading['gpu_process_mib'] = None
    return reading


def unsafe(sample, config):
    faults = []
    for key, minimum in (('available_gib', config['min_available_gib']), ('swap_free_gib', config['min_swap_free_gib'])):
        if sample.get(key) is None or sample[key] < minimum:
            faults.append(key + ' below safety limit or unreadable')
    if sample.get('memory_psi_full') is None or sample['memory_psi_full'] > config['max_memory_psi_full']:
        faults.append('memory pressure above safety limit or unreadable')
    if not sample.get('hyprland'):
        faults.append('compositor not found')
    if sample.get('play_game'):
        faults.append('user game running from protected play folder')
    if Path(config['gate_closed']).exists():
        faults.append('GPU guard closed the gate')
    return faults


def driver_faults(lines):
    errors = []
    allocation = 0
    for line in lines:
        if re.search(r'NVRM: Xid|kmemsysDoCacheOp|(?:i915|xe ).*(?:hang|reset|error)', line, re.I):
            errors.append(line)
        elif 'NVRM' in line:
            if 'memMap_IMPL: CPU mapping not supported for addressSpace: 0x1' in line:
                continue
            if re.search(r'NV_ERR_NO_MEMORY|_memdescAllocInternal.*mem_desc.c|rmStatus.*system_mem.c|pRmApi->Alloc.*nv_gpu_ops.c', line):
                allocation += 1
            else:
                errors.append(line)
    if allocation > 9:
        errors.append('more than three allocation-refusal events in one run')
    return errors


class Monitor:
    def __init__(self, config, copy, run, out):
        self.config, self.copy, self.run, self.out = config, Path(copy), Path(run), Path(out)
        self.stop = threading.Event()
        self.started = stamp()
        self.faults, self.samples, self.kernel, self.pids = [], [], [], set()
        self.in_play = False
        self.thread = threading.Thread(target=self.work, daemon=True)
        self.watchdog = None
        self.log_offset = 0

    def start(self):
        self.out.mkdir(parents=True, exist_ok=True)
        self.wlog = (self.out / 'watchdog.log').open('w')
        self.watchdog = subprocess.Popen([HARN / 'hs-watchdog.sh', str(self.config['min_available_gib']),
                                         str(self.config['max_memory_psi_full']), str(self.config['min_swap_free_gib'])],
                                        stdout=self.wlog, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                        start_new_session=True)
        self.thread.start()

    def work(self):
        try:
            while not self.stop.is_set():
                sample = resources(self.config, self.copy / 'hookshot')
                self.samples.append(sample)
                self.pids.update(sample['own_pids'])
                with (self.out / 'samples.jsonl').open('a') as f:
                    f.write(json.dumps(sample) + '\n')
                self.faults.extend(unsafe(sample, self.config))
                journal = subprocess.run(['journalctl', '-k', '--since', self.started, '--no-pager', '-o', 'short-iso'],
                                         text=True, capture_output=True, timeout=10)
                if journal.returncode:
                    self.faults.append('kernel journal unreadable')
                self.kernel = [line for line in journal.stdout.splitlines() if re.search(r'NVRM|kmemsysDoCacheOp|i915|xe ', line)]
                (self.out / 'kernel.txt').write_text('\n'.join(self.kernel) + '\n')
                self.faults.extend(driver_faults(self.kernel))
                if self.watchdog.poll() is not None:
                    self.faults.append('shared watchdog ended: ' + text(self.out / 'watchdog.log').strip())
                logfile = self.run / 'hookshot_log.txt'
                if logfile.is_file():
                    with logfile.open(errors='replace') as f:
                        f.seek(self.log_offset)
                        fresh = f.read()
                        self.log_offset = f.tell()
                    with (self.out / 'log-events.jsonl').open('a') as f:
                        for line in fresh.splitlines():
                            if WARNING.search(line) or ACTIVITY.search(line) or VRAM.search(line):
                                f.write(json.dumps({'monotonic_s': time.monotonic(), 'in_play': self.in_play, 'line': line}) + '\n')
                if self.faults:
                    self.stop.set()
                    self.on_fault()
                    return
                self.stop.wait(2)
        except Exception as error:
            self.faults.append('safety monitor failed: ' + str(error))
            self.stop.set()
            self.on_fault()

    def finish(self):
        self.stop.set()
        self.thread.join(timeout=20)
        if self.watchdog and self.watchdog.poll() is None:
            from common import stop_group
            stop_group(self.watchdog)
        self.wlog.close()
        try:
            journal = subprocess.run(['journalctl', '-k', '--since', self.started, '--until', stamp(),
                                      '--no-pager', '-o', 'short-iso'], text=True, capture_output=True, timeout=10)
            if journal.returncode:
                self.faults.append('final kernel journal unreadable')
            self.kernel = [line for line in journal.stdout.splitlines() if re.search(r'NVRM|kmemsysDoCacheOp|i915|xe ', line)]
            (self.out / 'kernel.txt').write_text('\n'.join(self.kernel) + '\n')
            self.faults.extend(driver_faults(self.kernel))
        except (OSError, subprocess.TimeoutExpired) as error:
            self.faults.append('final kernel journal failed: ' + str(error))

    def disturbance(self):
        reasons = ['ordinary queue; no authorized exclusive timing hold']
        if any(s['compiler_count'] for s in self.samples):
            reasons.append('compilers running')
        if any(s['other_games'] for s in self.samples):
            reasons.append('other game running')
        if any(s['load'][0] > self.config['quiet_load_max'] for s in self.samples):
            reasons.append('load above configured quiet limit')
        return reasons
