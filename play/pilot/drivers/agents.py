"""Real agents for the mcp driver, started by the pilot when the first decision point is open (`--mcp-agent loop|omp`, scenario `mcp_agent`).

  loop   our own small agent (../mcp_agent.py): an OpenRouter tool-calling model as an MCP client of ../mcp_server.py. Its requests are in the
         pilot's ledger (kind `agent`, under the run) and under its caps; it stops at its step, wall-time and dollar budgets.
  omp    the omp coding agent (the harness this project is worked in), non-interactive: `omp -p --no-session --mode json` in a scratch folder
         of the run (`omp-agent/`) whose `.omp/mcp.json` names the pilot's stdio server; omp's own sign-in and settings are used and nothing of
         them is changed. omp's model use is on the user's plan, not in the ledger: its token and cost lines are read from its JSON output.

Both run as a child process group of the pilot (so a hold's stop reaches them), write their output into the run folder, and are stopped when
the run ends. No key is ever put on a command line.
"""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

PILOT = Path(__file__).resolve().parent.parent
KINDS = ('loop', 'omp')
OMP_MODEL = 'anthropic/claude-haiku-4-5'
OMP_WALL_S, OMP_MAX_COST_USD = 330, 0.30
OMP_TASK = ('You are connected to an automatic test pilot for a 3D action adventure game through the MCP server `pilot`. Play its session: '
            'loop: call observe with after_n = the number of the last decision you answered (0 at first) and wait_s 60; read the goal, the state '
            'and the allowed actions; call act with n and step = exactly one of the allowed labels (the one that gets the goal done by what the '
            'data says); then observe again with after_n = n. Stop when observe says the run has ended. At most 60 tool calls in all. Use only '
            'the pilot tools: no files, no shell. Be brief.')


class Agent:
    def __init__(self, kind, proc, out, extra=None):
        self.kind, self.proc, self.out, self.extra = kind, proc, Path(out), dict(extra or {})
        self.started = time.time()

    def stop(self, grace=5.0):
        if self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
            try:
                self.proc.wait(timeout=grace)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(self.proc.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
        self.proc.poll()

    def summary(self):
        out = {'kind': self.kind, 'exit': self.proc.poll(), 'wall_s': round(time.time() - self.started, 1), **self.extra}
        try:
            if self.kind == 'loop':
                j = json.loads(self.out.read_text())
                out.update({k: j.get(k) for k in ('model', 'steps_used', 'tool_calls', 'spent_usd', 'stop', 'ended')})
            else:
                out.update(omp_usage(self.out))
        except (OSError, ValueError):
            pass
        return out


def omp_usage(path):
    """Best effort from omp's `--mode json` lines: the events seen, tool calls, and any usage / cost figures (sums of numeric `cost`/`total` fields
    that a usage object carries)."""
    events, tool_calls, cost, tokens = {}, 0, 0.0, 0
    for ln in Path(path).read_text(errors='replace').splitlines():
        try:
            e = json.loads(ln)
        except ValueError:
            continue
        t = e.get('type') if isinstance(e, dict) else None
        events[t] = events.get(t, 0) + 1
        if t and 'tool' in str(t) and 'start' in str(t):
            tool_calls += 1
        stack = [e]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                u = x.get('usage')
                if isinstance(u, dict) and t == 'message_end' and (e.get('message') or {}).get('role') == 'assistant' and x is e['message']:   # (once per model answer)
                    c = u.get('cost')
                    cost += float(c.get('total') or 0) if isinstance(c, dict) else float(c or 0) if isinstance(c, (int, float)) else 0.0
                    tokens += int(u.get('totalTokens') or u.get('total_tokens') or 0)
                stack.extend(v for v in x.values() if isinstance(v, (dict, list)))
            elif isinstance(x, list):
                stack.extend(v for v in x if isinstance(v, (dict, list)))
    return {'omp_events': events, 'omp_tool_calls': tool_calls, 'omp_cost_usd': round(cost, 6) if cost else None, 'omp_tokens': tokens or None}



def launcher(kind, *, session_dir, run_dir, run_id, segment, model=None, env=None):
    """A callable that starts the agent and returns its Agent."""
    if kind not in KINDS:
        raise ValueError(f'mcp agent is one of {", ".join(KINDS)}, not {kind!r}')
    run_dir = Path(run_dir)

    def start():
        penv = dict(os.environ if env is None else env)
        if kind == 'loop':
            out = run_dir / 'agent.json'
            cmd = [sys.executable, '-I', '-B', str(PILOT / 'mcp_agent.py'), '--session', str(session_dir), '--run-id', run_id, '--segment', segment,
                   '--out', str(out)] + (['--model', model] if model else [])
            penv['PILOT_RUN_ID'] = run_id
            log, extra = run_dir / 'agent.out', {'model': model}
        else:
            work = run_dir / 'omp-agent'
            (work / '.omp').mkdir(parents=True, exist_ok=True)
            (work / '.omp' / 'mcp.json').write_text(json.dumps({'mcpServers': {'pilot': {
                'type': 'stdio', 'command': 'python3', 'args': ['-I', '-B', str(PILOT / 'mcp_server.py'), '--session', str(session_dir)],
                'timeout': 150000}}}, indent=1))
            out = run_dir / 'omp-agent.jsonl'
            use = model or OMP_MODEL
            cmd = ['timeout', '--signal=TERM', '--kill-after=10', str(OMP_WALL_S), 'omp', '-p', '--no-session', '--cwd', str(work), '--mode', 'json',
                   '--model', use, '--thinking', 'minimal', '--max-cost', str(OMP_MAX_COST_USD), '--no-skills', '--no-rules', OMP_TASK]
            penv.setdefault('OMP_MCP_TIMEOUT_MS', '60000')
            log, extra = run_dir / 'omp-agent.err', {'model': use, 'cwd': str(work)}
        with open(out if kind == 'omp' else log, 'w') as stdout, open(log, 'a') as stderr:
            proc = subprocess.Popen(cmd, stdout=stdout, stderr=subprocess.STDOUT if kind == 'loop' else stderr, stdin=subprocess.DEVNULL, env=penv,
                                    cwd=str(run_dir), start_new_session=True)
        return Agent(kind, proc, out, extra)
    return start
