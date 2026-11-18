"""mcp: let an outside agent drive the pilot's run loop, through a folder both sides read and write.

The pilot runs as ever (the run loop, its guard, its transcript and its recorder). Where another driver would decide, the `mcp`
driver writes the decision point to `<session>/observe.json` and waits for `<session>/act.json`. The MCP server that the agent's client
starts (`pilot/mcp_server.py --session <session>`, stdio, standard library only) turns those two files into tools: observe,
allowed_actions, act, screenshot, status. The folder is the whole protocol (every write is a rename, a reader never sees half a file):

    session.json    written once by the pilot: run, segment, pid, the briefing a model would get, the waits, the control socket
    observe.json    the current decision point: n, the state, goal, target, what was tried, the allowed actions (label and text)
    act.json        the agent's answer (the server writes it): {n, step | steps, plan?, reason?, agent?}
    rejected.json   why the last act was refused (the pilot writes it; the agent may act again for the same n)
    status.json     phase (waiting | executing | ended), n, a heartbeat, the control socket (for screenshots)
    ended.json      the outcome, when the run is over

An act names one of the allowed actions (`step`, with an optional `plan` of up to two more labels, taken while they are still
offered) or brings steps of its own (`steps`: up to 20 lines of hsap steps from SAFE_VERBS, run as the one step `mcp:steps`): the
exploratory way. Both go through the pilot's own input path, so the run is recorded and can be played back. An answer that is not
allowed is refused with its reason and may be fixed (three refusals in one decision fail it). No answer in time is a `timeout`; the
chain falls back as it does for any driver.
"""
import os
import time

from .base import Availability, Decision, Driver, DriverFailure, Provenance
from .chat import prompt_parts   # (the data the Decisions request and the chat drivers send: one source)
from .mcp_session import FILES, SAFE_VERBS, Refused, Session, check_steps


class McpDriver(Driver):
    name = 'mcp'
    kind = 'agent'

    def __init__(self, session_dir, *, first_wait_s=600.0, wait_s=180.0, poll_s=0.1, max_refusals=3, clock=time.time,
                 sleep=time.sleep, on_first=None):
        self.session = Session(session_dir).make()
        self.first_wait_s, self.wait_s, self.poll_s, self.max_refusals = first_wait_s, wait_s, poll_s, max_refusals
        self.clock, self.sleep = clock, sleep
        self.n = 0
        self.info = {}
        self.sock = None            # the game's control socket (screenshots): a callable or a path, set by begin()
        self.acts = self.refusals = self.raw_steps = 0
        self.briefing = ''
        self.on_first, self.agent = on_first, None   # on_first(): starts an agent (drivers/agents.py) once the first decision point is open

    def describe(self):
        d = super().describe()
        d['session'] = str(self.session.dir)
        return d

    def available(self):
        if not self.session.dir.is_dir():
            return Availability.no(f'the session folder {self.session.dir} does not exist')
        return Availability.yes()

    def begin(self, *, run=None, segment=None, briefing='', control_sock=None, **extra):
        """Called once before the first decision: clears the folder of an earlier run and says what this one is."""
        for f in FILES:
            self.session.remove(f)
        self.briefing, self.sock = briefing, control_sock
        self.info = {'version': 1, 'run': run, 'segment': segment, 'pid': os.getpid(), 'started': self.clock(),
                     'briefing': briefing, 'first_wait_s': self.first_wait_s, 'wait_s': self.wait_s,
                     'safe_verbs': list(SAFE_VERBS), **extra}
        self.session.write('session.json', self.info)
        self.status('waiting', note='no decision point yet')

    def _sock(self):
        return str(self.sock() if callable(self.sock) else self.sock) if self.sock else None

    def status(self, phase, **extra):
        self.session.write('status.json', {'phase': phase, 'n': self.n, 'pid': os.getpid(), 'alive_ts': self.clock(),
                                           'control_sock': self._sock(), **extra})

    def decide(self, ctx):
        self.n += 1
        n = self.n
        dev, text, data, question, offered = prompt_parts(ctx)
        labels = [label for label, _ in offered]
        obs = {'n': n, 'asked_at': self.clock(), 'text': text, 'question': question, 'data': data,
               'candidates': [{'label': label, 'text': what} for label, what in offered], 'safe_verbs': list(SAFE_VERBS)}
        if n == 1:
            obs['briefing'] = dev
        self.session.remove('act.json')
        self.session.remove('rejected.json')
        self.session.write('observe.json', obs)
        self.status('waiting', note=f'decision {n}')
        if self.on_first is not None:
            start, self.on_first = self.on_first, None
            try:
                self.agent = start()
            except (OSError, ValueError) as e:
                raise DriverFailure('unavailable', f'the agent did not start: {type(e).__name__}: {e}') from None
        t0 = self.clock()
        deadline = t0 + (self.first_wait_s if n == 1 else self.wait_s)
        refusals, beat = 0, t0
        while True:
            act = self.session.read('act.json')
            if act is not None:
                self.session.remove('act.json')
                if act.get('n') == n:
                    try:
                        dec = self._accept(act, labels, n, round((self.clock() - t0) * 1000, 1))
                    except Refused as e:
                        refusals += 1
                        self.refusals += 1
                        self.session.write('rejected.json', {'n': n, 'why': str(e), 'refusals': refusals, 'at': self.clock()})
                        if refusals >= self.max_refusals:
                            raise DriverFailure('bad_answer', f'{refusals} acts refused for decision {n}; the last: {e}',
                                                info={'request': {'session': str(self.session.dir), 'observation': n}}) from None
                        continue
                    self.acts += 1
                    self.status('executing', note=f'decision {n}: {dec.label}')
                    return dec
            now = self.clock()
            if now >= deadline:
                self.status('waiting', note=f'decision {n} timed out')
                raise DriverFailure('timeout', f'no act for decision {n} in {now - t0:.0f} s',
                                    info={'request': {'session': str(self.session.dir), 'observation': n}})
            if now - beat >= 2.0:
                self.status('waiting', note=f'decision {n}')
                beat = now
            self.sleep(self.poll_s)

    def _accept(self, act, labels, n, waited_ms):
        reason = act.get('reason') if isinstance(act.get('reason'), str) else None
        plan = [p for p in (act.get('plan') or []) if isinstance(p, str) and p in labels][:2] if isinstance(act.get('plan'), list) else []
        request = {'session': str(self.session.dir), 'observation': n}
        info = {'request': request, 'answer': {k: act.get(k) for k in ('step', 'steps', 'plan', 'reason', 'agent') if k in act}}
        prov = Provenance(self.name, latency_ms=waited_ms, note=str(act.get('agent'))[:80] if act.get('agent') else None)
        if act.get('steps') is not None:
            lines = check_steps(act['steps'])
            self.raw_steps += 1
            text = f"the agent's own steps ({len(lines)} lines): {'; '.join(lines)[:120]}"
            return Decision('mcp:steps', provenance=prov, info=info, candidate=('mcp:steps', lines, text))
        step = act.get('step')
        if step not in labels:
            raise Refused(f'step {step!r} is not one of the allowed actions: {", ".join(labels)}')
        return Decision(step, plan=tuple(p for p in plan if p != step), provenance=prov, info=info)

    AGENT_GRACE_S = 10.0   # after the run ended, an agent started by the pilot gets this long to see it and write its own result

    def finish(self, outcome=None):
        self.session.write('ended.json', {'outcome': outcome, 'decisions': self.n, 'at': self.clock()})
        self.status('ended', outcome=outcome)
        if self.agent is not None:
            end = time.time() + self.AGENT_GRACE_S
            while self.agent.proc.poll() is None and time.time() < end:
                time.sleep(0.1)

    def close(self):
        if self.agent is not None:
            self.agent.stop()

    def stats(self):
        out = {'session': str(self.session.dir), 'decisions_asked': self.n, 'acts': self.acts, 'refusals': self.refusals, 'own_steps': self.raw_steps}
        if self.agent is not None:
            out['agent'] = self.agent.summary()
        return out
