"""Inside a hold: play the cells of a plan, one pilot and one game per lane, and leave a record per cell.

A lane is one game copy (a game needs its own); the plan's items are taken in order, so the arms of one cell run side by side on the lanes (same load, same
minute). Rules of the lane (the hold's own): never start a cell that cannot finish before the hold's cell deadline; stop every process of a cell by pid through
its run tag (the pilot, hsap, hs-run, the game) when it ends, is cut or times out; stop the hold's cells when the user's game appears (guard.py), when the
hold ends or when the waiter is signalled; and end a cell early, a few seconds after the REFEREE saw its proof in the state journal (the pilot ends itself
when its own goal is met; this covers the goals it does not recognise). The hold takes no lock: the waiter that runs it does (nightly.py).

Nothing here names a place or a flag: a cell's segment, save and proof come from the private board.
"""
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import board  # noqa: E402
import guard  # noqa: E402
import referee  # noqa: E402

SLOT_VARS = ('HSGATE_SLOT_DIR', 'HSGATE_INTEL_SLOT_DIR', 'HSGATE_SLOT_TEST', 'HSGATE_SLOT_NODESKTOP', 'HSGATE_IN_GATE', 'HSGATE_IN_INTEL_GATE')
MET_GRACE_S = 6.0       # the pilot ends itself when it saw its goal; if the referee saw the proof and it has not ended after this, it is asked to end (an `end` step)
END_WAIT_S = 8.0       # ... and stopped by pid when it still has not ended this long after that (its summary and metrics are written at its own end)
OVER_GRACE_S = 150.0    # a pilot may run this long past its game's wall (its end step, a planner answer) before it is stopped
QUEUE_WAIT_S = 480.0    # a cell waits this long for its game to show a first place (the card's gate may be busy; the pilot's own wall starts with the game, not with the wait)
POLL_S = 1.5


PILOT_FLAGS = ('--decider', '--tag', '--copy', '--wall', '--max-decisions', '--no-bad-points', '--save', '--shots', '--allowance-usd', '--allowance-since', '--planner',
               '--no-chapter-planner')   # every `pilot.py run` option cell_argv can pass: the hold's smoke check reads `run -h` for each


def tag_of(night, cell, arm, attempt):
    return f'pb{night[2:]}-{cell}-{arm}-a{attempt}'


def family(tag, own=()):
    """pids of every live process whose command line names this run tag as a whole word (the pilot, hsap, hs-run and its game)."""
    pat = re.compile(r'(?<![\w.-])' + re.escape(tag) + r'(?![\w.-])')
    skip = {os.getpid(), os.getppid()} | set(own)
    out = []
    for p in Path('/proc').iterdir():
        if not p.name.isdigit() or int(p.name) in skip:
            continue
        try:
            cmd = (p / 'cmdline').read_bytes().replace(b'\0', b' ').decode('utf-8', 'replace')
        except OSError:
            continue
        if pat.search(cmd):
            out.append(int(p.name))
    return out


def _zombie(pid):
    try:
        for line in Path(f'/proc/{pid}/status').read_text().splitlines():
            if line.startswith('State:'):
                return 'Z' in line.split(':', 1)[1]
    except OSError:
        pass
    return True


def stop_family(tag, wait_s=15.0, own=()):
    """SIGTERM to the family (by pid, never by name), SIGKILL to what is left after wait_s. Returns how many were found."""
    pids = family(tag, own)
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    end = time.time() + wait_s
    while time.time() < end and any(Path(f'/proc/{p}').exists() and not _zombie(p) for p in pids):
        time.sleep(0.4)
    for pid in pids:
        if Path(f'/proc/{pid}').exists() and not _zombie(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
    return len(pids)


def cell_argv(plan, cell, arm_name, arm, tag, copy):
    """(argv, env) of one pilot run: `pilot.py run <frozen segment> <arm's decider/planner/args> --tag ... --copy ... --wall ... --no-bad-points`.
    No bad-point memory and no route library: every night's cell starts from the same pilot knowledge, whatever earlier nights learned."""
    local = Path(plan['local'])
    prefix = plan.get('pilot_cmd') or [plan.get('python', sys.executable), '-I', '-B', str(Path(plan['pilot_dir']) / 'pilot.py')]
    arg_arm, env_arm = board.arm_args(arm, cell)
    argv = [*prefix, 'run', str(local / 'segments' / cell.segment), *arg_arm, '--tag', tag, '--copy', str(copy), '--wall', str(cell.wall_s),
            '--max-decisions', str(cell.max_decisions), '--no-bad-points']
    if plan.get('shots'):
        argv += ['--shots', str(plan['shots'])]
    if cell.save:
        argv += ['--save', str(local / 'saves' / cell.save)]
    if plan.get('allowance_usd') is not None:
        argv += ['--allowance-usd', str(plan['allowance_usd']), '--allowance-since', str(plan['allowance_since'])]
    env = dict(os.environ)
    for k in (*SLOT_VARS, 'ROUTELIB_DIR', 'PILOT_CACHE'):
        env.pop(k, None)
    env.update({str(k): str(v) for k, v in (plan.get('env') or {}).items()})
    env.update(env_arm)
    return argv, env


class Hold:
    def __init__(self, plan, clock=time.time, sleep=time.sleep, player_probe=None):
        self.plan = plan
        self.clock, self.sleep = clock, sleep
        self.out = Path(plan['out'])
        (self.out / 'cells').mkdir(parents=True, exist_ok=True)
        self.t0 = clock()
        self.cells_deadline = self.t0 + plan['hold_s'] - plan.get('reserve_s', 110)
        self.hard_deadline = self.t0 + plan['hold_s'] - max(40.0, plan.get('reserve_s', 110) - 20)   # (what is left after it is for scoring: the waiter's `timeout` kills 25 s after the hold's end)
        self.cells = {c.id: c for c in board.load(Path(plan['local']) / 'board-local.json')}
        self.arms = board.arms(plan.get('arms_file'))
        self.lock = threading.Lock()
        self.stopping = None          # why the hold stops its cells early: 'signal' | 'player' | 'hold'
        self.active = {}              # tag -> Popen
        self.todo = list(plan['items'])
        self.deferred, self.done = [], []
        self.player_probe = player_probe or guard.player_games
        self.player_seen = []
        self.reached, self.never = 0, 0   # cells that showed a place / that ended without one: two of the second kind and none of the first stop the hold ('no-play')

    # ---- stopping
    def stop(self, why):
        with self.lock:
            self.stopping = self.stopping or why
        for tag, proc in list(self.active.items()):
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except OSError:
                pass
            stop_family(tag, wait_s=8)

    def on_signal(self, signum, frame):
        self.stop('signal')

    def _guard_loop(self):
        while self.stopping is None and not self._finished:
            try:
                seen = self.player_probe()
            except Exception:   # noqa: BLE001  an unreadable /proc is not a reason to stop
                seen = []
            if seen:
                self.player_seen = [p.get('pid') for p in seen]
                self.stop('player')
                return
            self.sleep(5.0)

    # ---- one cell
    def key(self, item):
        return item['cell'], item['arm'], item['attempt']

    def run_one(self, copy, item):
        cell, arm_name = self.cells[item['cell']], item['arm']
        arm = self.arms[arm_name]
        tag = tag_of(self.plan['night'], cell.id, arm_name, item['attempt'])
        argv, env = cell_argv(self.plan, cell, arm_name, arm, tag, copy)
        run_dir = Path(self.plan['pilot_dir']) / 'runs' / tag
        rec = {'cell': cell.id, 'arm': arm_name, 'attempt': item['attempt'], 'tag': tag, 'copy': str(copy), 'hold': self.plan['hold'], 'argv': argv,
               'run_dir': str(run_dir), 'started': self.clock(), 'wall_s': cell.wall_s}
        live = referee.Referee(cell.proof, cell.start)
        proc, off, met_at, cut, end_sent = None, 0, None, None, False
        try:
            log = open(self.out / 'cells' / f'{tag}.log', 'w')
            proc = subprocess.Popen(argv, cwd=str(Path(self.plan['pilot_dir'])), env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                    start_new_session=True)
            with self.lock:
                self.active[tag] = proc
            started = self.clock()
            first_row_at = None
            while True:
                rc = proc.poll()
                rows, off = referee.read_rows(run_dir / 'live' / 'state.jsonl', off)
                if rows and first_row_at is None:
                    first_row_at = self.clock()
                for r in rows:
                    if live.feed(r) and met_at is None:
                        met_at = self.clock()
                limit = (first_row_at + cell.wall_s + OVER_GRACE_S) if first_row_at is not None else started + QUEUE_WAIT_S
                if rc is not None:
                    rec['rc'] = rc
                    break
                now = self.clock()
                if self.stopping:
                    cut = self.stopping
                    break
                if met_at is not None and now - met_at >= MET_GRACE_S and not end_sent:
                    end_sent = True
                    try:
                        with open(run_dir / 'live' / 'steps.txt', 'a') as f:
                            f.write('end\n')   # what the pilot sends itself at its end: the game stops, the pilot writes its summary and metrics
                    except OSError:
                        pass
                if met_at is not None and now - met_at >= MET_GRACE_S + END_WAIT_S:
                    rec['stopped_after_proof'] = True
                    break
                if now >= self.hard_deadline:
                    cut = 'hold'
                    break
                if now >= limit:
                    rec['rc'] = 'timeout'
                    break
                self.sleep(POLL_S)
        except Exception as e:   # noqa: BLE001  one broken cell must not end the hold
            rec['error'] = f'{type(e).__name__}: {e}'
        finally:
            with self.lock:
                self.active.pop(tag, None)
            if proc is not None and proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except OSError:
                    pass
                try:
                    proc.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    pass
            if proc is not None:
                rec.setdefault('rc', proc.poll())
            rec['stopped_leftovers'] = stop_family(tag)
            rec['ended'] = self.clock()
        if cut is None and self.stopping and isinstance(rec.get('rc'), int) and rec['rc'] < 0 and not live.met:
            cut = self.stopping   # (the hold's own stop killed it before the loop looked: the cell did not end by itself)
        rec['cut'] = cut
        rec['proof_met_live'] = live.met
        rows, _ = referee.read_rows(run_dir / 'live' / 'state.jsonl', 0)
        rec['valid_samples'] = sum(1 for r in rows if referee.valid(r))
        with self.lock:
            if rec['valid_samples']:
                self.reached += 1
            elif not cut:
                self.never += 1
        if self.never >= 2 and not self.reached:
            self.stop('no-play')   # (the game or the save is broken for every cell: the rest of the hold would be lane time for nothing)
        (self.out / 'cells' / f'{tag}.json').write_text(json.dumps(rec, indent=1))
        print(f"{tag}: rc {rec.get('rc')} {rec['ended'] - rec['started']:.0f} s proof {'MET' if live.met else 'not met'}"
              f"{' CUT ' + cut if cut else ''}{' ERROR ' + rec['error'] if rec.get('error') else ''}", flush=True)
        return rec

    # ---- the lanes
    def _next(self):
        """The next item that fits in the time left, or None; items that do not fit are deferred (kept for the next hold)."""
        with self.lock:
            while self.todo:
                item = self.todo.pop(0)
                cell = self.cells[item['cell']]
                if self.stopping is None and self.clock() + cell.wall_s + 15 <= self.cells_deadline:
                    return item
                self.deferred.append(item)
            return None

    def _lane(self, copy):
        while self.stopping is None:
            item = self._next()
            if item is None:
                return
            rec = self.run_one(copy, item)
            with self.lock:
                self.done.append(rec)

    def play(self):
        self._finished = False
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGTERM, self.on_signal)
            signal.signal(signal.SIGHUP, self.on_signal)
        g = threading.Thread(target=self._guard_loop, daemon=True)
        g.start()
        lanes = [threading.Thread(target=self._lane, args=(c,)) for c in self.plan['copies']]
        for t in lanes:
            t.start()
        for t in lanes:
            t.join()
        self._finished = True
        with self.lock:
            self.deferred += self.todo
            self.todo = []
        summary = {'done': [r['tag'] for r in self.done], 'deferred': [(i['cell'], i['arm'], i['attempt']) for i in self.deferred], 'stopping': self.stopping,
                   'player_pids': self.player_seen, 'seconds': round(self.clock() - self.t0, 1)}
        (self.out / 'hold.json').write_text(json.dumps(summary, indent=1))
        return summary
