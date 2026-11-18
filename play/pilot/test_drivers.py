#!/usr/bin/env python3
"""The driver layer without the game and without a model account: fake HTTP servers (the Decisions API, OpenRouter, a local chat
server), a fake game that moves Link and keeps hsap's input journal, the made-up house of test_pilot, and the MCP server over its
stdio. Checks, in order:

  the interface and the chain (fallback, benching, plans, events); each model driver against its fake server (a good answer, a
  timeout, 429, 500, a malformed answer and its one repair, a cap reached, no key) with the failure kind, the logged reason and the
  cost in a temporary ledger; the whole pilot on the made-up house through chains (no keys: every fallback logged, scripted solves);
  scripted determinism and fixed input scripts; playback (a run's recording replayed: same steps, same result; divergence by place,
  by map and at the start); the MCP server (the protocol, every tool, an agent solving the house over stdio, a refusal, a timeout);
  the scenario's `driver` table and the command line; `pilot.py run` end to end with a fake hsap.

    python3 -I -B test_drivers.py
"""
import argparse
import base64
import io
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import deciders  # noqa: E402
import drivers  # noqa: E402
import hsap  # noqa: E402
import inputlog  # noqa: E402
import openai_api  # noqa: E402
import pilot  # noqa: E402
import test_pilot as tp  # noqa: E402  (the made-up house: FakeGame, SEGMENT)
from drivers import agents, base, chat, mcp_queue, mcp_session, playback, recording  # noqa: E402
from drivers.chain import Chain  # noqa: E402
from drivers.decisions import DecisionsDriver  # noqa: E402
from drivers.scripted import ScriptedDriver  # noqa: E402

FAILS, CHECKS = [], [0]
SECRETS = ('sk' + '-' + 'test-openai-never-logged', 'sk' + '-' + 'or-test-never-logged', 'chat-test-key-never-logged')   # (the first two built here: no key-shaped literal in the file)


def check(cond, what):
    CHECKS[0] += 1
    if not cond:
        FAILS.append(what)
        print('FAIL', what, flush=True)


def secret_free(*texts):
    return not any(s in str(t) for t in texts for s in SECRETS)


# ---- fake services

class Fake:
    """A loopback HTTP server that answers like a service. behave(n, path, body, headers) -> (status, payload or text, delay s)."""

    def __init__(self, behave):
        self.seen, self.behave = [], behave
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                raw = self.rfile.read(int(self.headers.get('Content-Length', 0)))
                try:
                    body = json.loads(raw)
                except ValueError:
                    body = None
                n = len(outer.seen)
                outer.seen.append({'path': self.path, 'headers': dict(self.headers), 'body': body})
                status, payload, delay = outer.behave(n, self.path, body, dict(self.headers))
                if delay:
                    time.sleep(delay)
                out = (payload if isinstance(payload, str) else json.dumps(payload)).encode()
                try:
                    self.send_response(status)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(out)))
                    self.end_headers()
                    self.wfile.write(out)
                except OSError:
                    pass

        self.srv = ThreadingHTTPServer(('127.0.0.1', 0), H)
        self.srv.daemon_threads = True
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = f'http://127.0.0.1:{self.srv.server_address[1]}/v1'

    def close(self):
        self.srv.shutdown()
        self.srv.server_close()


def chat_labels(body):
    return body['tools'][0]['function']['parameters']['properties']['step']['enum'] if body and body.get('tools') else None


def chat_answer(step, plan=None, cost=0.00012, model='fake/model', prompt=900, completion=30, with_cost=True, content=None):
    usage = {'prompt_tokens': prompt, 'completion_tokens': completion, 'total_tokens': prompt + completion}
    if with_cost:
        usage['cost'] = cost
    msg = {'role': 'assistant', 'content': content}
    if content is None:
        args = {'step': step, **({'plan': plan} if plan else {}), 'reason': 'test'}
        msg['tool_calls'] = [{'id': 'call_1', 'type': 'function', 'function': {'name': 'choose_step', 'arguments': json.dumps(args)}}]
    return {'id': 'gen-1', 'model': model, 'choices': [{'message': msg, 'finish_reason': 'stop'}], 'usage': usage}


def chat_good(pick=None, **kw):
    def behave(n, path, body, headers):
        labels = chat_labels(body)
        return 200, chat_answer((pick(labels) if pick else labels[0]), **kw), 0
    return behave


def decisions_answer(label):
    return {'answers': [{'type': 'choice', 'name': 'next_step', 'choice': label, 'confidence': 0.8},
                        {'type': 'predicate', 'name': 'stuck', 'probability': 0.1}],
            'usage': {'input_tokens': 1450, 'input_tokens_details': {'cached_tokens': 429, 'cache_write_tokens': 758},
                      'output_tokens': 0}}


def decisions_good(pick=None):
    def behave(n, path, body, headers):
        labels = [c['value'] for c in body['questions'][0]['choices']]
        return 200, decisions_answer(pick(labels) if pick else labels[0]), 0
    return behave


# ---- contexts and the drivers under test

def make_ctx(kind='reach', state=None):
    g = pilot.Goal('g', pilot.Cond('X=1'), kind, [pilot.Target('t', 5, 5, kind=kind)])
    st = state or {'pos': [0, 0, 0], 'facing': 0, 'area': 'Fake_Area'}
    cands = pilot.make_candidates('Fake_Area', g, g.targets[0], st, {})
    return deciders.Context(st, g, g.targets[0], cands, {}, [])


class FastClient(openai_api.Client):
    """The real Client class pointed at a fake server as if it were OpenAI (real ledger, real key file), with a short timeout."""

    def __init__(self, run_id, base, timeout=0.5):
        super().__init__(run_id, 'fake', base)
        self.real, self.timeout = True, timeout

    def post(self, path, body, **kw):
        kw['timeout'] = self.timeout
        return super().post(path, body, **kw)


def ledger_rows():
    return openai_api.ledger_rows()


def reset_ledger():
    if openai_api.LEDGER.exists():
        openai_api.LEDGER.unlink()


def set_caps(run=20.0, night=500.0, total=4000.0):
    openai_api.CAPS.write_text(json.dumps({'per_run_usd': run, 'per_night_usd': night, 'total_usd': total, 'planner_share_of_night': 0.4,
                                           'model': None}))


def write_key(path, key):
    path.write_text(key + '\n')
    path.chmod(0o600)


class Stub(base.Driver):
    """A driver that does what a script says, one entry per decision (the last repeats): a label, or a DriverFailure to raise."""
    kind = 'model'

    def __init__(self, name, script, ready=None, paid=False, gap=0.0):
        self.name, self.script, self.ready, self.paid, self.min_gap_s = name, list(script), ready, paid, gap
        self.calls, self.stop_reason = 0, None

    def available(self):
        return self.ready or base.Availability.yes()

    def decide(self, ctx):
        item = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        if isinstance(item, Exception):
            raise item
        label, plan = item if isinstance(item, tuple) else (item, ())
        return base.Decision(label, plan=plan, provenance=base.Provenance(self.name, model='m', cost_usd=0.001, latency_ms=5.0, requests=1))


# ---- 1. the interface and the chain

def chain_checks():
    ctx = make_ctx()
    labels = [c.label for c in ctx.candidates]
    a, b = labels[0], labels[1]

    ch = Chain([Stub('one', [a]), Stub('two', [b])])
    c = ch.choose(ctx)
    check(c.label == a and c.driver == 'one' and c.info['driver']['driver'] == 'one' and c.info['cost_usd'] == 0.001 and
          'fallback' not in c.info and not ch.drain_events(), 'a driver that answers: the choice, who made it, its cost; no fallback, no event')

    fail = base.DriverFailure('timeout', 'no answer in 30 s', cost_usd=0.0002, requests=1)
    ch = Chain([Stub('one', [fail]), Stub('two', [b])], bench_after=2)
    c = ch.choose(ctx)
    ev = ch.drain_events()
    check(c.label == b and c.driver == 'two' and c.info['fallbacks'] == [{'driver': 'one', 'failure': 'timeout', 'reason': 'no answer in 30 s'}] and
          c.info['fallback'].startswith('one: timeout'), 'a timeout falls back to the next driver; the decision lists what failed first')
    check(len(ev) == 1 and ev[0]['kind'] == 'driver-fallback' and ev[0]['driver'] == 'one' and ev[0]['to'] == 'two' and
          ev[0]['failure'] == 'timeout' and ev[0]['reason'] == 'no answer in 30 s' and ev[0]['benched'] is False and ev[0]['cost_usd'] == 0.0002,
          f'the fallback is an event with the reason, the next driver and the cost of the failed attempt: {ev}')
    ch.choose(ctx)
    ev2 = ch.drain_events()
    check(ev2 and ev2[0]['benched'] is True and 'one' in ch.benched, 'two timeouts in a row bench a driver')
    ch.choose(ctx)
    check(not ch.drain_events() and ch.drivers[0].calls == 2, 'a benched driver is not asked again and nothing is logged again')

    # a success in between resets the count
    one = Stub('one', [fail, a, fail, a])
    ch = Chain([one, Stub('two', [b])], bench_after=2)
    for _ in range(4):
        ch.choose(ctx)
    check('one' not in ch.benched and one.calls == 4, 'an answer resets the count of failures in a row')

    # sticky kinds bench at once; throttled counts for nothing
    for kind in ('unavailable', 'over_budget', 'diverged', 'exhausted'):
        ch = Chain([Stub('one', [base.DriverFailure(kind, 'why')]), Stub('two', [b])])
        ch.choose(ctx)
        check('one' in ch.benched and ch.benched['one'].startswith(kind), f'{kind} benches the driver at once')
    ch = Chain([Stub('one', [base.DriverFailure('throttled', 'pace')]), Stub('two', [b])], bench_after=1)
    ch.choose(ctx)
    ch.choose(ctx)
    check('one' not in ch.benched and ch.drivers[0].calls == 2, 'a throttled answer never benches a driver')
    check(all(k in base.FAILURE_KINDS for k in ('unavailable', 'timeout', 'refused', 'bad_answer', 'over_budget')),
          'the failure kinds the layer promises exist')

    # a throttled (paced) model: no other paid driver is asked in the gap either; the rules choose, and nothing counts against anyone
    paid = Stub('paid', [base.DriverFailure('throttled', '0.50 s since the last request')], paid=True)
    other = Stub('other', [b], paid=True)
    free = Stub('free', [labels[2]])
    ch = Chain([paid, other, free])
    c = ch.choose(ctx)
    check(c.driver == 'free' and other.calls == 0 and not ch.drain_events() and not ch.benched, 'a throttled model is not replaced by another paid model; the next free driver decides')
    ch = Chain([paid, other])
    c = ch.choose(ctx)
    check(c.driver == 'rules' and c.info['throttled'].startswith('0.50 s') and other.calls == 0 and not ch.stop_reason and not ch.benched,
          'throttled with only paid drivers: the rules choose (as the Decisions decider did), the run goes on')

    # an exception that is no DriverFailure is a failure of that driver (a bug must not end the run)
    ch = Chain([Stub('one', [ValueError('boom')]), Stub('two', [b])])
    c = ch.choose(ctx)
    ev = ch.drain_events()
    check(c.driver == 'two' and ev[0]['failure'] == 'error' and 'boom' in ev[0]['reason'], 'a driver\'s bug is an `error` failure and the chain goes on')

    # a plan: the later labels are taken without asking while they are offered
    one = Stub('one', [(a, (b, labels[2])), 'x'])
    ch = Chain([one, Stub('two', [labels[3]])])
    c1 = ch.choose(ctx)
    c2 = ch.choose(ctx)
    c3 = ch.choose(ctx)
    check([c1.label, c2.label, c3.label] == [a, b, labels[2]] and one.calls == 1 and c2.driver == 'one' and c2.info['driver']['note'] == 'a step of its plan',
          'a short plan is taken step by step with no new question')
    one = Stub('one', [(a, ('nope',)), b])
    ch = Chain([one, Stub('two', [labels[3]])])
    ch.choose(ctx)
    c = ch.choose(ctx)
    check(c.label == b and one.calls == 2, 'a planned label that is no longer offered drops the plan and the driver is asked again')

    # nothing left
    ch = Chain([Stub('one', [base.DriverFailure('refused', 'HTTP 403')])])
    c = ch.choose(ctx)
    check(ch.stop_reason and 'no driver could decide' in ch.stop_reason and 'one: refused: HTTP 403' in ch.stop_reason and c.driver is None,
          f'no driver left sets the stop reason the pilot ends the run with: {ch.stop_reason}')

    # availability: probed at the start, an unavailable driver is benched with its fallback written first
    ch = Chain([Stub('one', [a], ready=base.Availability.no('no key')), Stub('two', [b], ready=base.Availability.no('over the cap', 'over_budget')),
                Stub('three', [labels[2]])])
    probe = ch.probe()
    c = ch.choose(ctx)
    ev = ch.drain_events()
    check(probe == {'one': (False, 'no key'), 'two': (False, 'over the cap'), 'three': (True, '')} and c.driver == 'three' and
          [(e['driver'], e['failure'], e['reason'], e['to']) for e in ev] == [('one', 'unavailable', 'no key', 'three'), ('two', 'over_budget', 'over the cap', 'three')],
          f'availability: no key and a cap are explicit, benched before any request, each logged with its reason: {ev}')

    # min_gap_s follows the first driver that is not benched; a driver that says it must stop is benched after its answer
    ch = Chain([Stub('one', [a], gap=1.5), Stub('two', [b])])
    check(ch.min_gap_s == 1.5, 'a model at the head of the chain paces a duel')
    ch.drivers[0].stop_reason = 'a decision cost too much'
    ch.choose(ctx)
    ev = ch.drain_events()
    check(ch.min_gap_s == 0.0 and ev and ev[0]['failure'] == 'over_budget' and 'too much' in ev[0]['reason'],
          'a driver that gave an answer but says it must not be asked again is benched, with the reason')
    rep = ch.report()
    check(rep['decisions_by_driver'] == {'one': 1} and rep['benched'] and rep['chain'][0]['name'] == 'one' and rep['fallbacks'],
          'the report says who decided, who was benched and every fallback')


# ---- 2. each model driver against its fake server

def kinds_of(driver, ctx):
    try:
        driver.decide(ctx)
    except base.DriverFailure as f:
        return f
    return None


def model_checks(tmp):
    ctx = make_ctx()
    labels = [c.label for c in ctx.candidates]
    openai_key, or_key, chat_key = tmp / 'openai.key', tmp / 'openrouter.key', tmp / 'chat.key'
    write_key(openai_key, SECRETS[0])
    write_key(or_key, SECRETS[1])
    os.environ['PILOT_OPENAI_KEY_FILE'] = str(openai_key)
    os.environ['PILOT_OPENROUTER_KEY_FILE'] = str(or_key)
    os.environ.pop('PILOT_CHAT_API_KEY', None)
    os.environ['PILOT_CHAT_KEY_FILE'] = str(tmp / 'no-chat-key')
    for k in ('OPENAI_API_KEY', 'OPENROUTER_API_KEY'):
        os.environ.pop(k, None)

    def mk_decisions(fake, run='dec', timeout=0.5):
        return DecisionsDriver(FastClient(run, fake.base, timeout))

    def mk_openrouter(fake, run='or', timeout=0.5, **kw):
        return chat.make_openrouter(run, 'fake', base=fake.base, model='fake/model', timeout=timeout, **kw)

    def mk_chat(fake, run='chat', timeout=0.5, **kw):
        return chat.make_chat(run, 'fake', base=fake.base, model='local-model', timeout=timeout, **kw)

    makers = (('decisions', mk_decisions, decisions_good, 'POST', None), ('openrouter', mk_openrouter, chat_good, 'POST', None),
              ('chat', mk_chat, chat_good, 'POST', None))
    set_caps()
    for name, mk, good, _, _ in makers:
        reset_ledger()
        # a good answer
        fake = Fake(good(lambda labs: labs[1]))
        d = mk(fake, run=f'good-{name}')
        dec = d.decide(ctx)
        row = (ledger_rows() or [None])[-1]
        check(dec.label == labels[1] and dec.provenance.driver == name and dec.provenance.requests == 1 and dec.provenance.latency_ms is not None,
              f'{name}: a good answer is the choice, with its provenance')
        check(secret_free(json.dumps(dec.info, default=str), dec.provenance.as_dict()), f'{name}: no key in the decision')
        if name == 'decisions':
            check(row and row['api'] == 'decisions' and row['base'] == 'openai' and row['cost_usd'] > 0 and dec.provenance.cost_usd == row['cost_usd'] and
                  row['run'] == 'good-decisions', 'decisions: one ledger row, costed from the response\'s tokens at the published prices')
            check(fake.seen[0]['path'] == '/v1/decisions' and fake.seen[0]['headers']['Authorization'] == 'Bearer ' + SECRETS[0],
                  'decisions: POST /decisions with the key from the key file')
        elif name == 'openrouter':
            check(row and row['api'] == 'chat' and row['base'] == 'openrouter' and abs(row['cost_usd'] - 0.00012) < 1e-12 and
                  'usage.cost' in row['cost_source'] and dec.provenance.cost_usd == 0.00012 and 'usage.cost' in dec.provenance.cost_source,
                  f"openrouter: the ledger row carries the response's own cost and says so ({row and row['cost_source']})")
            h = fake.seen[0]['headers']
            check(fake.seen[0]['path'] == '/v1/chat/completions' and h['Authorization'] == 'Bearer standin' and not any(SECRETS[1] in str(x) for x in fake.seen),
                  'openrouter: a base that is not openrouter.ai gets the word standin, never the key')
            b0 = fake.seen[0]['body']
            check(b0['model'] == 'fake/model' and b0['tool_choice'] == 'required' and b0['tools'][0]['function']['name'] == 'choose_step' and 'temperature' not in b0 and chat_labels(b0) == labels and
                  b0['messages'][0]['role'] == 'system' and labels[0] in b0['messages'][1]['content'] and 'usage' not in b0 and
                  b0['provider'] == {'require_parameters': True},
                  'openrouter: a forced tool call whose `step` enum is exactly the allowed labels, the prompt carries the labels and their texts')
        else:
            check(row and row['base'] == 'chat' and row['cost_usd'] == 0.0 and row['cost_source'] == 'local endpoint' and
                  'Authorization' not in fake.seen[0]['headers'], 'chat: a local endpoint costs nothing and is sent no key')
        fake.close()

        # a timeout
        fake = Fake(lambda n, p, b, h: (200, {}, 1.2))
        f = kinds_of(mk(fake, timeout=0.3), ctx)
        check(f and f.kind == 'timeout', f'{name}: a timeout is `timeout` ({f and f.kind}: {f and f.reason[:60]})')
        fake.close()
        # 429, 500, 403
        for status, kind in ((429, 'refused'), (500, 'error'), (403, 'refused')):
            fake = Fake(lambda n, p, b, h, s=status: (s, {'error': {'message': 'nope'}}, 0))
            f = kinds_of(mk(fake), ctx)
            check(f and f.kind == kind and f'HTTP {status}' in f.reason, f'{name}: HTTP {status} is `{kind}` ({f and f.kind}: {f and f.reason[:50]})')
            fake.close()
        # a malformed answer
        if name == 'decisions':
            fake = Fake(lambda n, p, b, h: (200, {'answers': [{'type': 'choice', 'name': 'next_step', 'choice': 'not-offered'}],
                                                   'usage': {'input_tokens': 100, 'output_tokens': 0}}, 0))
        else:
            fake = Fake(lambda n, p, b, h: (200, chat_answer('not-offered'), 0))
        reset_ledger()
        f = kinds_of(mk(fake, run=f'bad-{name}'), ctx)
        check(f and f.kind == 'bad_answer' and f.requests == (1 if name == 'decisions' else 2), f'{name}: an answer that is no allowed step is `bad_answer` ({f and f.reason[:70]})')
        if name != 'decisions':
            check(len(fake.seen) == 2 and 'not usable' in fake.seen[1]['body']['messages'][-1]['content'] and labels[0] in fake.seen[1]['body']['messages'][-1]['content'] and
                  len(ledger_rows()) == 2, f'{name}: ONE repair request (the bad answer and the allowed labels sent back), then it fails; both requests are in the ledger')
        fake.close()
        # a cap reached: no request is sent
        set_caps(run=0.0000001)
        fake = Fake(good())
        reset_ledger()
        openai_api._append({'ts': time.time(), 'run': f'cap-{name}', 'kind': 'decision', 'cost_usd': 0.001, 'status': 200, 'latency_ms': 1, 'usage': {}}, openai_api.LEDGER)
        d = mk(fake, run=f'cap-{name}')
        av = d.available()
        f = kinds_of(d, ctx) if name != 'chat' else None   # (a local endpoint is not under the caps: nothing to refuse)
        if name == 'chat':
            check(av.ok, 'chat: a local endpoint is free and is not stopped by a cap')
        else:
            check(not av.ok and av.kind == 'over_budget' and 'run cap' in av.reason, f'{name}: availability says the run cap is reached ({av.reason})')
            check(f and f.kind == 'over_budget' and 'run cap' in f.reason and not fake.seen, f'{name}: asked anyway, the cap stops it before any request ({f and f.reason[:50]})')
        fake.close()
        set_caps()

    # decisions: no key; no caps file
    os.environ['PILOT_OPENAI_KEY_FILE'] = str(tmp / 'no-such-key')
    d = DecisionsDriver(FastClient('nokey', 'http://127.0.0.1:9/v1'))
    av = d.available()
    f = kinds_of(d, ctx)
    check(not av.ok and 'no key' in av.reason and f and f.kind == 'unavailable' and 'no key' in f.reason, f'decisions: no key is `unavailable` ({av.reason})')
    os.environ['PILOT_OPENAI_KEY_FILE'] = str(openai_key)
    real_caps = openai_api.CAPS
    openai_api.CAPS = tmp / 'no-caps.json'
    d = DecisionsDriver(FastClient('nocaps', 'http://127.0.0.1:9/v1'))
    av = d.available()
    f = kinds_of(d, ctx)
    check(not av.ok and av.kind == 'over_budget' and 'caps' in av.reason and f and f.kind == 'over_budget', 'decisions: no caps file is a cap (as it always was)')
    openai_api.CAPS = real_caps

    # openrouter: no key on the real base; a key file that is not mode 600
    os.environ['PILOT_OPENROUTER_KEY_FILE'] = str(tmp / 'no-or-key')
    d = chat.make_openrouter('nokey', 'fake')
    av = d.available()
    f = kinds_of(d, ctx)
    check(d.client.base == 'https://openrouter.ai/api/v1' and d.model == chat.OPENROUTER_MODEL and not av.ok and 'no key' in av.reason and
          f and f.kind == 'unavailable' and f.requests == 0, f'openrouter: no key is `unavailable` with no request ({av.reason})')
    loose = tmp / 'loose.key'
    loose.write_text(SECRETS[1])
    loose.chmod(0o644)
    os.environ['PILOT_OPENROUTER_KEY_FILE'] = str(loose)
    check('mode 600' in chat.make_openrouter('loose', 'fake').available().reason, 'openrouter: a key file that is not mode 600 is not used')
    os.environ['PILOT_OPENROUTER_KEY_FILE'] = str(or_key)
    check(chat.make_openrouter('k', 'fake').available().ok, 'openrouter: with the key file the driver is available')

    # chat: not configured, a key when one is given, one repair that works, a content answer, 402, an error object
    d = chat.make_chat('nc', 'fake')
    av = d.available()
    check(not av.ok and 'not configured' in av.reason and 'PILOT_CHAT_BASE' in av.reason, f'chat: no base URL is `unavailable` and says what to set ({av.reason[:60]})')
    os.environ['PILOT_CHAT_API_KEY'] = SECRETS[2]
    fake = Fake(chat_good())
    chat.make_chat('keyed', 'fake', base=fake.base, timeout=0.5).decide(ctx)
    check(fake.seen[0]['headers']['Authorization'] == 'Bearer ' + SECRETS[2], 'chat: a configured key is sent')
    fake.close()
    os.environ.pop('PILOT_CHAT_API_KEY')

    state = {'n': 0}

    def flaky(n, path, body, headers):
        labs = chat_labels(body)
        return 200, (chat_answer('nope') if n == 0 else chat_answer(labs[2])), 0
    reset_ledger()
    fake = Fake(flaky)
    dec = mk_openrouter(fake, run='repair').decide(ctx)
    check(dec.label == labels[2] and dec.provenance.requests == 2 and dec.info.get('repaired') and len(ledger_rows()) == 2 and
          abs(dec.provenance.cost_usd - 0.00024) < 1e-9, f'a bad answer repaired by the one retry: both requests counted ({dec.provenance.cost_usd})')
    fake.close()
    fake = Fake(lambda n, p, b, h: (200, chat_answer(None, content='```json\n{"step": "%s", "plan": ["%s", "zzz"]}\n```' % (labels[1], labels[2])), 0))
    dec = mk_chat(fake).decide(ctx)
    check(dec.label == labels[1] and dec.plan == (labels[2],) and dec.info['answer']['how'] == 'JSON in the content',
          'a server that ignores the tool and answers JSON in prose is understood; a plan label that is not offered is dropped')
    fake.close()
    fake = Fake(lambda n, p, b, h: (200, chat_answer(None, content=labels[3]), 0))
    check(mk_chat(fake).decide(ctx).label == labels[3], 'a bare label is understood')
    fake.close()
    fake = Fake(lambda n, p, b, h: (402, {'error': {'message': 'insufficient credits'}}, 0))
    f = kinds_of(mk_openrouter(fake), ctx)
    check(f and f.kind == 'over_budget' and 'HTTP 402' in f.reason, 'openrouter: HTTP 402 (no credit) is `over_budget`')
    fake.close()
    fake = Fake(lambda n, p, b, h: (200, {'error': {'code': 429, 'message': 'upstream rate limit'}}, 0))
    f = kinds_of(mk_openrouter(fake), ctx)
    check(f and f.kind == 'refused' and 'upstream rate limit' in f.reason, 'openrouter: a 200 with an error object is sorted by its code')
    fake.close()

    # cost: the price table when the response has no cost, the estimate when it has neither
    reset_ledger()
    fake = Fake(chat_good(with_cost=False, model='anthropic/claude-haiku-5.5', prompt=1000, completion=50))
    dec = chat.make_openrouter('table', 'fake', base=fake.base, model='anthropic/claude-haiku-5.5', timeout=0.5).decide(ctx)
    row = ledger_rows()[-1]
    check(abs(row['cost_usd'] - (1000 * 0.10 + 50 * 0.50) / 1e6) < 1e-12 and 'price table' in row['cost_source'] and 'price table' in dec.provenance.cost_source,
          f"no usage.cost: the price table's figure, and the ledger says so ({row['cost_usd']}, {row['cost_source'][:40]})")
    fake.close()
    reset_ledger()
    fake = Fake(chat_good(with_cost=False, model='some/unpriced-model'))
    dec = chat.make_openrouter('estimate', 'fake', base=fake.base, model='some/unpriced-model', timeout=0.5).decide(ctx)
    row = ledger_rows()[-1]
    check(row['cost_usd'] > 0 and 'estimate' in row['cost_source'], f"neither: the request's estimate is counted, never undercounted ({row['cost_usd']:.6f})")
    fake.close()
    # a decision dearer than the limit stops the driver (its answer stands)
    fake = Fake(chat_good(cost=0.05))
    d = mk_openrouter(fake)
    dec = d.decide(ctx)
    check(dec.label and d.stop_reason and '0.05' in d.stop_reason, 'a decision dearer than the per-decision limit stops the driver for the run')
    fake.close()
    # one candidate: no request, no cost
    one = deciders.Context(ctx.state, ctx.goal, ctx.target, ctx.candidates[:1], {}, [])
    fake = Fake(chat_good())
    dec = mk_openrouter(fake).decide(one)
    check(dec.label == labels[0] and not fake.seen and dec.info['no_request'] == 'one candidate', 'one candidate: no question, no request, no cost')
    fake.close()

    # the other ways to ask for a structured answer
    b = chat.build_request('m', [{'role': 'user', 'content': 'x'}], labels, 'json_schema')
    check(b['response_format']['json_schema']['strict'] and b['response_format']['json_schema']['schema']['properties']['step']['enum'] == labels and
          b['response_format']['json_schema']['schema']['required'] == ['step', 'plan', 'reason'] and 'tools' not in b, 'json_schema mode: a strict schema whose `step` enum is the allowed labels')
    b = chat.build_request('m', [{'role': 'user', 'content': 'x'}], labels, 'json')
    check('tools' not in b and 'response_format' not in b, 'json mode: nothing but the prompt asks for JSON')
    try:
        chat.build_request('m', [], labels, 'xml')
        check(False, 'an unknown mode is refused')
    except ValueError:
        check(True, 'an unknown mode is refused')
    fake = Fake(lambda n, p, body, h: (200, chat_answer(None, content=json.dumps({'step': labels[2], 'plan': [], 'reason': 'x'})), 0))
    dec = mk_chat(fake, mode='json_schema').decide(ctx)
    check(dec.label == labels[2] and 'response_format' in fake.seen[0]['body'] and 'tools' not in fake.seen[0]['body'], 'a json_schema request is answered by JSON in the content')
    fake.close()

    # the default OpenRouter model is the decisions model's own (the comparison is about the route, not the model); no weaker model is a default anywhere
    check(chat.OPENROUTER_MODEL == 'openai/gpt-6-luna' == 'openai/' + openai_api.DECISION_MODEL and chat.make_openrouter('d', 'x').model == chat.OPENROUTER_MODEL and
          chat.make_chat('d', 'x', base='http://127.0.0.1:1/v1').model == 'local' and chat.PRICES[chat.OPENROUTER_MODEL] == (0.10, 0.50) and
          not any('nano' in k for k in chat.PRICES), 'the OpenRouter default is openai/gpt-6-luna, the decisions model\'s own (priced in the table; no nano anywhere)')

    # an endpoint that takes no forced tool_choice (Claude through OpenRouter: 404) is asked again once with `auto`, and remembered
    def no_forced(n, path, body, headers):
        if body.get('tool_choice') != 'auto':
            return 404, {'error': {'message': "No endpoints found that support the provided 'tool_choice' value.", 'code': 404}}, 0
        return 200, chat_answer(chat_labels(body)[1]), 0
    fake = Fake(no_forced)
    d = mk_openrouter(fake, run='downgrade')
    dec = d.decide(ctx)
    dec2 = d.decide(ctx)
    check(dec.label == labels[1] and dec.info.get('tool_choice', '').startswith('auto') and [s['body']['tool_choice'] for s in fake.seen] == ['required', 'auto', 'auto'] and
          dec2.label == labels[1] and dec.provenance.requests == 1 and dec.provenance.cost_usd == 0.00012,
          f"a 404 about tool_choice downgrades to `auto` once (the failed request billed nothing) and the driver remembers ({[s['body']['tool_choice'] for s in fake.seen]})")
    fake.close()

    # a chain: decisions -> openrouter -> chat -> scripted, each failing in its own way: every reason is logged and scripted decides
    reset_ledger()
    fk = [Fake(lambda n, p, b, h: (200, {}, 1.2)), Fake(lambda n, p, b, h: (429, {'error': {'message': 'slow down'}}, 0)),
          Fake(lambda n, p, b, h: (200, chat_answer('nope'), 0))]
    ch = Chain([mk_decisions(fk[0], 'chain', timeout=0.3), mk_openrouter(fk[1], 'chain'), mk_chat(fk[2], 'chain'), ScriptedDriver()], want='decisions')
    c = ch.choose(ctx)
    ev = ch.drain_events()
    check(c.driver == 'scripted' and [(e['driver'], e['failure']) for e in ev] == [('decisions', 'timeout'), ('openrouter', 'refused'), ('chat', 'bad_answer')] and
          [e['to'] for e in ev] == ['openrouter', 'chat', 'scripted'] and 'slow down' in ev[1]['reason'], f'a chain falls through every kind of failure to scripted: {[(e["driver"], e["failure"]) for e in ev]}')
    check(secret_free(json.dumps(ev, default=str), json.dumps(c.info, default=str), json.dumps(ch.report(), default=str)), 'no key in the events, the decision or the report')
    for f in fk:
        f.close()


# ---- 3. the whole pilot on the made-up house

def play_house(chain, tmp, max_decisions=None):
    return tp.play(chain, tmp, max_decisions)


def transcript(run_dir):
    return [json.loads(x) for x in (run_dir / 'transcript.jsonl').read_text().splitlines()]


def pilot_chain_checks(tmp):
    for k in ('OPENAI_API_KEY', 'OPENROUTER_API_KEY'):
        os.environ.pop(k, None)
    os.environ['PILOT_OPENAI_KEY_FILE'] = str(tmp / 'no-such-key')
    os.environ['PILOT_OPENROUTER_KEY_FILE'] = str(tmp / 'no-or-key')
    os.environ.pop('PILOT_CHAT_BASE', None)
    set_caps()
    reset_ledger()
    args = argparse.Namespace(driver=None, fallbacks=None)
    client = openai_api.Client('house-default', 'fake-house')   # (the real OpenAI base: no key file, so no request is ever made)
    chain = drivers.build_chain('default', None, args=args, table={}, client=client, run_id='house-default', segment='fake-house', run_dir=tmp)
    check([d.name for d in chain.drivers] == ['decisions', 'openrouter', 'scripted'] and chain.notes and 'chat: not configured' in chain.notes[0],
          f'the default chain is decisions, openrouter, chat only if configured, scripted ({[d.name for d in chain.drivers]})')
    chain.probe()
    seg, p, outcome, ch, run_dir = play_house(chain, tmp)
    tr = transcript(run_dir)
    dec = [e for e in tr if e['kind'] == 'decision']
    fb = [e for e in tr if e['kind'] == 'driver-fallback']
    check(outcome == 'solved', f'with no key anywhere the chain ends on scripted and still solves the house ({outcome}, {len(dec)} decisions)')
    check([(e['driver'], e['failure'], e['n']) for e in fb] == [('decisions', 'unavailable', 1), ('openrouter', 'unavailable', 1)] and
          'no key' in fb[0]['reason'] and 'no key' in fb[1]['reason'] and fb[1]['to'] == 'scripted',
          f'both fallbacks are in the transcript with their reasons, at decision 1: {[(e["driver"], e["reason"][:30]) for e in fb]}')
    check(all(e['decider'] == 'scripted' and e['driver']['driver'] == 'scripted' for e in dec) and set(p.who) == {'scripted'} and len(p.who) == len(dec),
          'every decision says scripted made it')
    check(not openai_api.LEDGER.exists() or not ledger_rows(), 'nothing was asked of any model: the ledger is empty')
    rep = chain.report()
    check(rep['decisions_by_driver'] == {'scripted': len(dec)} and set(rep['benched']) == {'decisions', 'openrouter'} and len(rep['fallbacks']) == 2,
          'the report: who decided, who was benched, every fallback')
    runs = pilot.who_runs(p.who)
    check(runs == [[1, len(dec), 'scripted']], f'the per-decision account is run-length coded: {runs}')

    # a model that works at first, then rate-limits: the pilot keeps going on scripted, the fallback is logged each time until benched
    reset_ledger()
    state = {'n': 0}

    def sometimes(n, path, body, headers):
        labs = chat_labels(body)
        if n < 2:
            return 200, chat_answer(labs[0]), 0
        return 429, {'error': {'message': 'rate limited'}}, 0
    fake = Fake(sometimes)
    orc = chat.make_openrouter('house-flaky', 'fake-house', base=fake.base, model='fake/model', timeout=1.0)
    chain = Chain([orc, ScriptedDriver()], want='openrouter')
    seg, p, outcome, ch, run_dir = play_house(chain, tmp, max_decisions=14)
    tr = transcript(run_dir)
    dec = [e for e in tr if e['kind'] == 'decision']
    fb = [e for e in tr if e['kind'] == 'driver-fallback']
    check([e['decider'] for e in dec[:2]] == ['openrouter', 'openrouter'] and all(e['decider'] == 'scripted' for e in dec[2:]) and
          dec[0]['cost_usd'] == 0.00012 and dec[0]['driver']['model'] == 'fake/model',
          f"two decisions by the model, the rest by scripted: {[e['decider'] for e in dec[:5]]}")
    check(len(fb) == 2 and fb[0]['failure'] == 'refused' and fb[0]['benched'] is False and fb[1]['benched'] is True and fb[0]['n'] == 3 and
          'rate limited' in fb[0]['reason'] and len(fake.seen) == 4, f'two refusals, then benched: {len(fb)} events, {len(fake.seen)} requests in all')
    check(dec[2]['fallbacks'][0]['failure'] == 'refused' and dec[2]['fallback'].startswith('openrouter: refused'), 'the decision after a fallback lists what failed')
    led = ledger_rows()
    check(len(led) == 4 and sum(r['status'] == 200 for r in led) == 2 and abs(sum(r['cost_usd'] for r in led) - 0.00024) < 1e-12 and
          {r['run'] for r in led} == {'house-flaky'}, 'the ledger: four requests, two costed, all under the run')
    fake.close()

    # a stop reason ends the run when no driver is left
    chain = Chain([Stub('only', [base.DriverFailure('refused', 'HTTP 403: no')])], want='only')
    seg, p, outcome, ch, run_dir = play_house(chain, tmp)
    tr = transcript(run_dir)
    check(outcome.startswith('stopped: no driver could decide') and any(e['kind'] == 'stop' for e in tr) and not p.decisions,
          f'a chain with no driver left ends the run with the reason ({outcome[:80]})')

    # the legacy deciders are what they were: a plain Rules and a plain Decisions have no `driver` and no fallback events
    seg, p, outcome, ch, run_dir = tp.play(deciders.Rules(), tmp)
    dec = [e for e in transcript(run_dir) if e['kind'] == 'decision']
    check(outcome == 'solved' and all(e['decider'] == 'rules' and 'driver' not in e for e in dec) and p.who == ['rules'] * len(dec),
          'the older deciders still play as before (decider = their name, no driver block)')


# ---- 4. scripted: determinism and fixed input scripts

def scripted_checks(tmp):
    runs = []
    for i in range(2):
        chain = Chain([ScriptedDriver()], want='scripted')
        seg, p, outcome, ch, run_dir = play_house(chain, tmp)
        steps = [e['src'] for e in ch.events if e['ev'] == 'step' and e.get('in')]
        dec = [{k: v for k, v in e.items() if k not in ('wall', 'decide_ms', 'state')} for e in transcript(run_dir) if e['kind'] == 'decision']
        runs.append((outcome, list(p.decisions), steps, dec, [e['state'].get('pos') for e in transcript(run_dir) if e['kind'] == 'decision']))
    check(runs[0][0] == 'solved' and runs[0][:3] == runs[1][:3] and runs[0][4] == runs[1][4], f'scripted: two runs, the same steps in the same order ({len(runs[0][2])} steps)')
    check(runs[0][3] == runs[1][3], 'scripted: the whole decision rows (candidates, choice, provenance) are the same, not only the labels')

    # the same observations in, the same labels out, from a fresh driver
    first = [e for e in transcript(run_dir) if e['kind'] == 'decision']
    check(all('latency_ms' not in e and 'cost_usd' not in e and 'request' not in e for e in first), 'scripted asks nothing, costs nothing and times nothing')

    # fixed input scripts: once, at their goal, as a step of their own
    d = ScriptedDriver([{'name': 'open', 'goal': 'door', 'lines': ['press A 200']}, {'name': 'first', 'lines': ['wait 0.1']}])
    g = pilot.Goal('door', pilot.Cond('Door_Open=1'), 'door', [pilot.Target('d', 0, 0, kind='door')])
    ctx = deciders.Context({'pos': [-4, 0, 0], 'facing': 0}, g, g.targets[0], pilot.make_candidates('A', g, g.targets[0], {'pos': [-4, 0, 0], 'facing': 0}, {}), {}, [])
    d1 = d.decide(ctx)
    other = pilot.Goal('other', pilot.Cond('X=1'), 'reach', [pilot.Target('t', 5, 5)])
    ctx2 = make_ctx()
    d2 = ScriptedDriver([{'name': 'open', 'goal': 'door', 'lines': ['press A 200']}]).decide(ctx2)
    check(d1.label == 'script:open' and d1.candidate == ('script:open', ['press A 200'], d1.candidate[2]) and d.played == ['open'],
          'a fixed input script is offered as a step of its own, once, at its goal')
    check(d2.label != 'script:open' and d2.candidate is None, 'a script that names a goal waits for it; until then the rules decide')
    check(d.decide(ctx).label == 'script:first' and d.decide(ctx).candidate is None, 'the next script follows; when all are played the rules decide again')
    try:
        ScriptedDriver([{'name': 'x'}])
        check(False, 'a script without lines is refused')
    except ValueError:
        check(True, 'a script without lines is refused')

    # a script runs through the pilot's own input path
    chain = Chain([ScriptedDriver([{'name': 'knock', 'lines': ['wait 0.1']}])], want='scripted')
    seg, p, outcome, ch, run_dir = play_house(chain, tmp, max_decisions=3)
    steps = [e['src'] for e in ch.events if e['ev'] == 'step' and e.get('in')]
    dec = [e for e in transcript(run_dir) if e['kind'] == 'decision']
    check(dec[0]['choice'] == 'script:knock' and steps[0] == 'wait 0.1' and dec[0]['candidates'][-1]['label'] == 'script:knock',
          'the script\'s lines were sent as the first step and the candidate list shows it')


# ---- 5. playback

PUSH_SEGMENT = '''
name = "push-walk"
what = "walk east then north to a spot"
area = "Push_Area"
budget_seconds = 120
max_decisions = 12
[[goal]]
name = "arrive"
flag = "Arrived=1"
kind = "reach"
targets = [{name = "spot", at = [4.0, 3.0], kind = "reach"}]
'''
PUSH_SCRIPTS = [{'name': 'knock', 'lines': ['press A 200']}, {'name': 'breathe', 'lines': ['wait 0.3']},
                {'name': 'east', 'lines': ['push 32767 0 1000']}, {'name': 'north', 'lines': ['push 0 32767 750']}]


class PushGame(threading.Thread):
    """A made-up game for replays. Link on a plane; `push lx ly ms` moves him (32767 is 4 m a second, x east and y north), `press` and
    `wait` take time; a wall at x = wall_x stops him. 60 frames a second. It keeps hsap's input journal (inputs.jsonl: every press and
    stick request with the present it left at) and writes out.jsonl as hsap does, with `frame` and `area` in each state."""

    def __init__(self, live, start=(0.0, 0.0), area='Push_Area', wall_x=None):
        super().__init__(daemon=True)
        self.live, self.pos, self.area, self.wall_x = Path(live), [start[0], 0.0, start[1]], area, wall_x
        self.frame, self.n, self.tick, self.watch, self.stop = 1000, 0, 0, [], False
        self.flags = {'Arrived': 0}
        self.inputs = open(self.live / 'inputs.jsonl', 'w')

    def emit(self, **e):
        with open(self.live / 'out.jsonl', 'a') as f:
            f.write(json.dumps(e) + '\n')

    def journal(self, **row):
        self.inputs.write(json.dumps(dict(row, present=self.frame, mono=round(time.monotonic(), 3))) + '\n')
        self.inputs.flush()

    def state(self, last):
        self.tick += 1
        self.emit(ev='state', why='wait', n=self.tick, tick=self.tick, t=self.frame / 60, world=0, steps=self.n, frame=self.frame,
                  **{'in': self.lines}, pos=list(self.pos), facing=90.0, camera=90.0, area=self.area, prompt='Empty', music='BGM_Fake',
                  scene=False, life=12, max_life=12, rupees=0, loading=0, time='06:00', last=last,
                  flags={k: self.flags.get(k) for k in self.watch}, changed=[])

    def step(self, src):
        w = src.split()
        result = 'done'
        if w[0] == 'push':
            lx, ly, ms = int(w[1]), int(w[2]), int(w[3])
            frames = round(ms * 60 / 1000)
            self.journal(cmd='stick', x=round(lx / 32767, 4), y=round(ly / 32767, 4), frames=frames)
            self.pos[0] += lx / 32767 * 4.0 * ms / 1000
            if self.wall_x is not None:
                self.pos[0] = min(self.pos[0], self.wall_x)
            self.pos[2] += ly / 32767 * 4.0 * ms / 1000
            self.frame += frames
        elif w[0] == 'press':
            ms = int(w[2]) if len(w) > 2 else 200
            frames = max(1, round(ms * 60 / 1000))
            self.journal(cmd='press', buttons=w[1], frames=frames)
            self.frame += frames
        elif w[0] == 'wait':
            self.frame += round(float(w[1]) * 60)
        elif w[0] == 'raw':   # a sequence in hos units: each entry at its own time, analog sticks as LX=/LY= tokens; then the wait
            start = self.frame
            for item in w[1].split(','):
                m = re.fullmatch(r'([\d.]+):([^/]+)(?:/([\d.]+))?', item)
                at, names, ms = int(float(m.group(1)) * 60 + 0.5), m.group(2), float(m.group(3) or 200)
                frames = max(1, int(ms * 0.06 + 0.5))
                axes = dict(tok.split('=') for tok in names.split('+') if '=' in tok)
                if axes:
                    x, y = int(axes.get('LX', 0)) / 32767, int(axes.get('LY', 0)) / 32767
                    self.frame = start + at
                    self.journal(cmd='stick', stick='L', x=round(x, 4), y=round(y, 4), frames=frames)
                    self.pos[0] += x * 4.0 * frames / 60
                    if self.wall_x is not None:
                        self.pos[0] = min(self.pos[0], self.wall_x)
                    self.pos[2] += y * 4.0 * frames / 60
                else:
                    self.frame = start + at
                    self.journal(cmd='press', buttons=names, frames=frames)
            self.frame = max(self.frame, start + int(float(w[2]) * 60 + 0.5))
        elif w[0] == 'until':
            name, _, val = w[2].partition('=')
            result = 'met' if str(self.flags.get(name)) == val else 'timeout'
        if math.hypot(self.pos[0] - 4.0, self.pos[2] - 3.0) <= 1.0:
            self.flags['Arrived'] = 1
        self.n += 1
        return {'ev': 'step', 'n': self.n, 'in': self.lines, 'line': 0, 'src': src, 'result': result, 'secs': 1.0, 'moved': 0.0,
                'pos': list(self.pos), 'detail': ''}

    def run(self):
        self.lines, off, buf = 0, 0, ''
        self.emit(ev='start', tick=0, steps=0, pos=None)
        self.emit(ev='gameplay', tick=1, steps=0, pos=list(self.pos), frame=self.frame, area=self.area)
        waiting = False
        while not self.stop:
            data = (self.live / 'steps.txt').read_text()[off:]
            off += len(data)
            buf += data
            *whole, buf = buf.split('\n')
            last = None
            for line in whole:
                self.lines += 1
                w = line.split()
                if not w:
                    continue
                if w[0] == 'watch':
                    self.watch += w[1:]
                elif w[0] == 'end':
                    self.emit(ev='done', tick=self.tick, steps=self.n, pos=list(self.pos))
                    return
                else:
                    e = self.step(line)
                    self.emit(**e)
                    last = {'src': e['src'], 'result': e['result'], 'secs': 1.0, 'moved': 0.0, 'detail': ''}
                    waiting = False
            if not waiting and (last or not self.n):
                self.state(last)
                waiting = True
            time.sleep(0.01)


def play_push(chain, tmp, max_decisions=None, **game_kw):
    seg_path = tmp / f'push-{time.time_ns()}.toml'
    seg_path.write_text(PUSH_SEGMENT)
    seg = pilot.Segment(seg_path)
    live = tmp / f'live-push-{time.time_ns()}'
    ch = pilot.Channel(live)
    ch.send(pilot.watch_lines(seg.watch))
    game = PushGame(live, **game_kw)
    game.start()
    assert ch.wait(lambda e: e['ev'] == 'gameplay', 5)
    st = ch.wait(lambda e: e['ev'] == 'state', 5)
    run_dir = tmp / f'run-push-{time.time_ns()}'
    run_dir.mkdir()
    p = pilot.Pilot(seg, chain, ch, run_dir, run_dir.name, lambda: True, None, max_decisions)
    p.plan = None
    outcome = p.run(st)
    ch.send(['end'])
    ch.wait(lambda e: e['ev'] == 'done', 5)
    return seg, p, outcome, ch, run_dir, live


def playback_checks(tmp):
    # the recording of a run: a scripted run of four decisions on the fake game, with hsap's journal
    chain = Chain([ScriptedDriver(PUSH_SCRIPTS)], want='scripted')
    seg, p, outcome, ch, run_dir, live = play_push(chain, tmp)
    check(outcome == 'solved' and p.decisions == ['script:knock', 'script:breathe', 'script:east', 'script:north'], f'the recorded run: {outcome}, {p.decisions}')
    rec_path = tmp / 'push.recording.jsonl'
    made = recording.write_run(live, rec_path, segment='push-walk', area='Push_Area', save='lib-save', boot='continue', tag='rec-1')
    header, lines = inputlog.read_recording(rec_path)
    marks = [x for x in lines if x['cmd'] == 'mark']
    inputs = [x for x in lines if x['cmd'] != 'mark']
    check(made == (rec_path, 3, 5) and header['format'] == inputlog.FORMAT and header['marks'] == 5 and header['save'] == 'lib-save' and
          [x['cmd'] for x in inputs] == ['press', 'stick', 'stick'] and header['start'] == 1000,
          f'the recording: ls-input-recording/1, three inputs, five marks (the start and one per step), the setup in its header ({made and made[1:]})')
    check(marks[0]['f'] == 0 and marks[0]['pos'] == [0, 0, 0] and marks[-1]['pos'] == [4, 0, 3] and marks[-1]['area'] == 'Push_Area' and
          [x['f'] for x in inputs] == [0, 30, 90], f'marks carry map and place; inputs are frames since control began ({[x["f"] for x in inputs]})')
    check(inputlog.to_hsap_steps(lines[1:])[0] == 'press A 200' and any(s.startswith('push 32767 0') for s in inputlog.to_hsap_steps(lines[1:])),
          'inputlog\'s converters read the file with its marks in (marks are skipped)')
    check(recording.write_run(tmp / 'no-journal-here', tmp / 'x.jsonl') is None, 'a run with no input journal makes no recording')

    # playback on a fresh game: the same steps, the same result, no model, no recovery
    def replay(**kw):
        d = playback.PlaybackDriver(rec_path)
        chain = Chain([d], want='playback')
        res = play_push(chain, tmp, **kw)
        return d, chain, res
    d1, c1, (seg1, p1, out1, ch1, run1, live1) = replay()
    steps1 = [e['src'] for e in ch1.events if e['ev'] == 'step' and e.get('in')]
    dec1 = [e for e in transcript(run1) if e['kind'] == 'decision']
    check(out1 == 'solved' and p1.decisions == ['playback:0', 'playback:1', 'playback:2'] and set(p1.who) == {'playback'} and
          d1.stats()['diverged'] is None and len(d1.stats()['offsets']) == d1.stats()['marks_checked'] and d1.stats()['marks_checked'] >= 3 and d1.stats()['max_off_m'] < 0.5,
          f'playback solves the same segment: {out1}, {p1.decisions}, checked {d1.stats()["marks_checked"]} marks, off by at most {d1.stats()["max_off_m"]} m')
    check(steps1 == ['raw 0.0017:A/201 0.20', 'wait 0.30', 'raw 0.0017:LX=32767+LY=0/1001 1.00', 'raw 0.0017:LX=0+LY=32767/751 0.75'],
          f'the replay sends the recorded requests as raw sequences in the game\'s own clock, with the recorded pauses ({steps1})')
    dp = playback.PlaybackDriver(rec_path, mode='push')
    seg_p, pp, out_p, ch_p, run_p, _ = play_push(Chain([dp], want='playback'), tmp)
    steps_p = [e['src'] for e in ch_p.events if e['ev'] == 'step' and e.get('in')]
    check(out_p == 'solved' and steps_p == ['press A 200', 'wait 0.30', 'push 32767 0 1000', 'push 0 32767 750'] and dp.stats()['mode'] == 'push',
          f'mode push: one hsap step per recorded request ({steps_p})')
    try:
        playback.PlaybackDriver(rec_path, mode='fast')
        check(False, 'an unknown playback mode is refused')
    except ValueError:
        check(True, 'an unknown playback mode is refused')
    d2, c2, (seg2, p2, out2, ch2, run2, live2) = replay()
    steps2 = [e['src'] for e in ch2.events if e['ev'] == 'step' and e.get('in')]
    check(out2 == 'solved' and steps2 == steps1 and p2.decisions == p1.decisions, 'playback is deterministic: a second replay sends exactly the same steps')
    check(dec1[0]['driver']['driver'] == 'playback' and dec1[0]['playback']['chunk'] == 0 and dec1[0]['playback']['of'] == 3 and 'cost_usd' not in dec1[0],
          'each decision row says which chunk of the recording it played')
    # the replay is itself recorded: a recording of a recording says the same
    again = recording.write_run(live1, tmp / 'replayed.jsonl', segment='push-walk')
    h2, l2 = inputlog.read_recording(tmp / 'replayed.jsonl')
    check(again and again[1] == 3 and [x['cmd'] for x in l2 if x['cmd'] != 'mark'] == ['press', 'stick', 'stick'], 'the same run loop records a replay too')

    # divergence by place: a wall at x = 2 stops Link; the replay says so before it goes on
    d3 = playback.PlaybackDriver(rec_path)
    chain = Chain([d3], want='playback')
    seg3, p3, out3, ch3, run3, live3 = play_push(chain, tmp, wall_x=0.5)
    tr3 = transcript(run3)
    fb3 = [e for e in tr3 if e['kind'] == 'driver-fallback']
    check(out3.startswith('stopped: no driver could decide (playback: diverged') and len(fb3) == 1 and fb3[0]['failure'] == 'diverged' and
          'm from where the recording had him' in fb3[0]['reason'] and fb3[0]['to'] is None and p3.decisions == ['playback:0', 'playback:1'] and
          d3.stats()['diverged']['at_chunk'] == 2, f'a replay that left the road stops and says where: {out3[:120]}')
    check('[0.5, 0.0, 0.0]' in fb3[0]['reason'] and '[4.0, 0.0, 0.0]' in fb3[0]['reason'] and '3.5 m' in fb3[0]['reason'], 'the reason holds the place it is in, the place the recording was at and how far apart')
    # the goal's flag flips a moment AFTER the last recorded input (the first hold: raw replay exhausted 0.1 s before it): one settle wait first
    class LateFlag(PushGame):
        def step(self, src):
            out = super().step(src)
            if src.startswith('wait 3'):   # (the flag comes a moment after the last input, whatever Link did)
                self.flags['Arrived'] = 1
            return out
    short_goal = tmp / 'late.jsonl'
    lines_late = [header] + [x for x in lines[1:] if x['f'] < 80]   # (the recording stops before the last push: Link is not at the spot)
    inputlog.write_recording(short_goal, lines_late)
    seg_path = tmp / f'late-{time.time_ns()}.toml'
    seg_path.write_text(PUSH_SEGMENT)
    dl = playback.PlaybackDriver(short_goal)
    seg_l = pilot.Segment(seg_path)
    live_l = tmp / f'live-late-{time.time_ns()}'
    ch_l = pilot.Channel(live_l)
    ch_l.send(pilot.watch_lines(seg_l.watch))
    game_l = LateFlag(live_l)
    game_l.start()
    assert ch_l.wait(lambda e: e['ev'] == 'gameplay', 5)
    st_l = ch_l.wait(lambda e: e['ev'] == 'state', 5)
    run_l = tmp / f'run-late-{time.time_ns()}'
    run_l.mkdir()
    p_l = pilot.Pilot(seg_l, Chain([dl], want='playback'), ch_l, run_l, run_l.name, lambda: True, None, 12)
    p_l.plan = None
    out_l = p_l.run(st_l)
    ch_l.send(['end'])
    ch_l.wait(lambda e: e['ev'] == 'done', 5)
    check(out_l == 'solved' and p_l.decisions[-1] == 'playback:settle' and dl.stats()['settled'] and
          [e['src'] for e in ch_l.events if e['ev'] == 'step' and e.get('in')][-1] == 'wait 3',
          f'when the goal shows only after the last recorded input, one settle wait lets it show before the replay is called exhausted ({out_l}, {p_l.decisions[-2:]})')
    # by map and at the start
    d4 = playback.PlaybackDriver(rec_path)
    seg4, p4, out4, ch4, run4, _ = play_push(Chain([d4], want='playback'), tmp, area='Other_Area')
    fb4 = [e for e in transcript(run4) if e['kind'] == 'driver-fallback']
    check(out4.startswith('stopped:') and fb4 and "the map is 'Other_Area'" in fb4[0]['reason'] and not p4.decisions, f'a different map is a divergence at the start, before any input ({fb4 and fb4[0]["reason"][:90]})')
    d5 = playback.PlaybackDriver(rec_path)
    seg5, p5, out5, ch5, run5, _ = play_push(Chain([d5], want='playback'), tmp, start=(10.0, 0.0))
    fb5 = [e for e in transcript(run5) if e['kind'] == 'driver-fallback']
    check(out5.startswith('stopped:') and fb5 and 'at the start' in fb5[0]['reason'] and not p5.decisions, 'a start somewhere else is a divergence before the first input')
    # divergence with a fallback the scenario accepts: scripted takes over and the run goes on
    d6 = playback.PlaybackDriver(rec_path)
    seg6, p6, out6, ch6, run6, _ = play_push(Chain([d6, ScriptedDriver()], want='playback'), tmp, wall_x=0.5, max_decisions=6)
    fb6 = [e for e in transcript(run6) if e['kind'] == 'driver-fallback']
    check(fb6 and fb6[0]['to'] == 'scripted' and p6.who[:2] == ['playback', 'playback'] and set(p6.who[2:]) == {'scripted'}, 'with scripted accepted as a fallback the run goes on after the divergence')
    # exhausted: the recording ends and the goal is not met (a goal the recording does not reach)
    short = tmp / 'short.jsonl'
    inputlog.write_recording(short, [lines_ for lines_ in [header] + [x for x in lines[1:] if x['f'] < 70]])
    d7 = playback.PlaybackDriver(short)
    seg7, p7, out7, ch7, run7, _ = play_push(Chain([d7], want='playback'), tmp)
    fb7 = [e for e in transcript(run7) if e['kind'] == 'driver-fallback']
    check(out7.startswith('stopped:') and fb7 and fb7[0]['failure'] == 'exhausted' and 'recording ended' in fb7[0]['reason'], 'a recording that ends before the goal is `exhausted`, not a silent stop')
    # a tolerance
    d8 = playback.PlaybackDriver(rec_path, tolerance_m=50.0)
    seg8, p8, out8, ch8, run8, _ = play_push(Chain([d8], want='playback'), tmp, wall_x=0.5)
    check(d8.tolerance == 50.0 and d8.stats()['diverged'] is None, 'the tolerance is the scenario\'s to set')
    # setup
    d9 = playback.PlaybackDriver(rec_path, setup={'boot': 'newgame', 'steps': ['wait 1']})
    check(d9.setup() == {'save': 'lib-save', 'boot': 'newgame', 'steps': ['wait 1']}, 'the start setup: the recording\'s header, over-ridden by the scenario\'s own table')
    try:
        playback.PlaybackDriver(tmp / 'does-not-exist.jsonl')
        check(False, 'a missing recording is refused')
    except ValueError as e:
        check('recording' in str(e), 'a missing recording is refused with its name')
    bad = tmp / 'not-a-recording.jsonl'
    bad.write_text('{"x": 1}\n')
    try:
        playback.PlaybackDriver(bad)
        check(False, 'a file that is no recording is refused')
    except ValueError as e:
        check('ls-input-recording' in str(e), 'a file that is no ls-input-recording/1 is refused')

    # raw mode on a long stretch of steering (a stick every 6 presents held for 6): runs of at most RAW_ENTRIES, each sent when the spacing
    # since the last run's first input has passed less the typical overshoot of hsap's wait; a pause becomes a wall wait; a press is in the script
    walk = [{'f': 6 * i, 'cmd': 'stick', 'stick': 'L', 'x': 0.5, 'y': -0.25, 'frames': 6} for i in range(60)]
    walk.append({'f': 6 * 60 + 5, 'cmd': 'press', 'buttons': 'ZL+R', 'frames': 12})
    walk.append({'f': 400, 'cmd': 'press', 'buttons': 'A', 'frames': 12})
    walk.append({'f': 1400, 'cmd': 'sequence', 'script': '0:LUP/200', 'units': 'hos'})
    dr = playback.PlaybackDriver(rec_path)
    out = dr.raw_lines(walk)
    runs = [ln for ln in out if ln.startswith('raw ')]
    sizes = [len(ln.split()[1].split(',')) for ln in runs]
    check(sizes == [24, 24, 14, 1] and out[0].startswith('raw 0.0017:LX=16384+LY=-8192/101,0.1017:LX=16384+LY=-8192/101') and
          out[0].endswith(' 2.38') and out[1].endswith(' 2.38') and out[2].endswith(' 2.07'),
          f'raw mode: sixty sticks and two presses become runs of 24, 24 and 14 entries, 2.4 s apart less the overshoot, then a recorded sequence ({sizes}, {[ln.split()[-1] for ln in out]})')
    check(out[3] == 'wait 16.47' and out[4] == 'raw 0:LUP/200 0.20' and dr.trimmed_s == 0 and 'ZL+R/201,1.8683:A/201' in out[2],
          f'a pause between runs is a wall wait, a press is an entry of the run it falls in with its own frame count, a recorded sequence is carried over ({out[3:]})')
    check(playback.PlaybackDriver.entry({'cmd': 'stick', 'stick': 'R', 'x': -1.0, 'y': 0.0, 'frames': 3}, 0.5) == '0.5017:RX=-32767+RY=0/51' and
          playback.PlaybackDriver.entry({'cmd': 'mark'}, 0) is None, 'a right stick is RX/RY; what has no word in the grammar is dropped')
    seq = playback.PlaybackDriver.timed('raw 0:LUP/1200,0.6:X/100 0')
    check(seq == 'raw 0:LUP/1200,0.6:X/100 1.20' and playback.PlaybackDriver.timed('push 1 2 3') == 'push 1 2 3' and
          playback.PlaybackDriver.timed('raw 0:A 5') == 'raw 0:A 5', 'a recorded sequence is replayed with its own length as the wait, so the next step does not overlap it')

    # chunks without marks split at pauses; hsap's journal hook writes a row with the present it was sent at
    evs = [{'f': 0, 'cmd': 'press', 'buttons': 'A', 'frames': 10}, {'f': 20, 'cmd': 'press', 'buttons': 'B', 'frames': 10},
           {'f': 400, 'cmd': 'press', 'buttons': 'X', 'frames': 10}]
    chunks, tail = recording.chunks(evs, [], gap_s=2.0)
    check([len(c['events']) for c in chunks] == [2, 1] and all(c['mark'] is None for c in chunks), 'a recording without marks is cut at pauses (nothing to check)')
    g = hsap.Game.__new__(hsap.Game)
    g.inputs_out, g.presents = io.StringIO(), 77
    g.record_input({'cmd': 'press', 'buttons': 'A', 'frames': 8})
    row = json.loads(g.inputs_out.getvalue())
    check(row['present'] == 77 and row['cmd'] == 'press' and 'mono' in row, 'hsap\'s journal hook writes the request with the present it left at')


# ---- 6. MCP

class Client:
    """An MCP client over the server's stdio: one JSON message a line."""

    def __init__(self, session, extra=()):
        self.p = subprocess.Popen([sys.executable, '-I', '-B', str(HERE / 'mcp_server.py'), '--session', str(session), *extra],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.n = 0

    def send(self, obj):
        self.p.stdin.write(json.dumps(obj) + '\n')
        self.p.stdin.flush()

    def rpc(self, method, params=None):
        self.n += 1
        self.send({'jsonrpc': '2.0', 'id': self.n, 'method': method, 'params': params or {}})
        line = self.p.stdout.readline()
        return json.loads(line)

    def tool(self, name, **args):
        r = self.rpc('tools/call', {'name': name, 'arguments': args})
        res = r['result']
        content = res['content'][0]
        out = json.loads(content['text']) if content['type'] == 'text' and not res.get('isError') and content['text'].startswith(('{', '[')) else content
        return out, res.get('isError', False)

    def close(self):
        try:
            self.p.stdin.close()
            self.p.wait(timeout=10)
        except Exception:   # noqa: BLE001
            self.p.kill()
        return self.p.stderr.read()


def hsap_pipeline_checks(tmp):
    """The real hsap (its Game, its Executor, its input journal) on test_hsap's simulated bridge: a run is journalled, made a recording,
    replayed by the playback driver's lines on a second simulated game, and ends where the first one did."""
    import test_hsap
    steps = ['walk 6 8 radius 0.6 timeout 15', 'press A 200', 'wait 0.5', 'walk 0 8 radius 0.6 timeout 15', 'end']
    rec_path = tmp / 'sim.recording.jsonl'
    with test_hsap.Simulation(boot_events=1, follow=False, camera=0.0) as sim:
        ex = sim.executor(steps)
        ex.analog = True
        ex.run()
        final1 = list(sim.bridge.pos)
        made = recording.write_run(sim.live, rec_path, segment='sim')
        gameplay = next(e for e in sim.events() if e['ev'] == 'gameplay')
    header, lines = inputlog.read_recording(rec_path)
    inputs = [x for x in lines if x['cmd'] != 'mark']
    press = [x for x in inputs if x['cmd'] == 'press']
    check(made and header['start'] == gameplay['frame'] and len([x for x in inputs if x['cmd'] == 'stick']) > 30 and
          len(press) == 1 and press[0]['buttons'] == 'A' and press[0]['frames'] == 12 and inputs[0]['f'] < 12,
          f"hsap's own journal becomes the recording: control began at present {header['start']}, {len(inputs)} requests from frame 0, the A press in it")
    d = playback.PlaybackDriver(rec_path)
    flat = [ln for chunk in d.chunks for ln in d.lines_of(chunk)]
    entries = [item for ln in flat if ln.startswith('raw ') for item in ln.split()[1].split(',')]
    check(len(flat) >= 2 and all(ln.split()[0] in ('raw', 'wait') for ln in flat) and any(e.endswith(':A/201') for e in entries) and
          sum('LX=' in e for e in entries) > 30 and len(entries) == len([x for x in inputs]),
          f'its steps (raw mode): {len(flat)} raw sequences holding the {len(entries)} recorded requests, the A press among them')
    check(recording.trim_overlaps([{'f': 0, 'cmd': 'stick', 'frames': 8}, {'f': 6, 'cmd': 'stick', 'frames': 8}, {'f': 40, 'cmd': 'press', 'frames': 12}]) ==
          [{'f': 0, 'cmd': 'stick', 'frames': 6}, {'f': 6, 'cmd': 'stick', 'frames': 8}, {'f': 40, 'cmd': 'press', 'frames': 12}],
          'a stick that the next one overtakes is cut to the time until it (hsap holds each for 8 presents and sends one every 6)')
    with test_hsap.Simulation(boot_events=1, follow=False, camera=0.0) as sim2:
        ex2 = sim2.executor(flat + ['end'])
        ex2.analog = True
        ex2.run()
        final2 = list(sim2.bridge.pos)
    off = math.hypot(final1[0] - final2[0], final1[2] - final2[2])
    check(off < 0.5 and math.hypot(final1[0], final1[2]) > 5, f'the replay on a second game ends {off:.2f} m from where the recorded run ended ({[round(v, 1) for v in final1]})')
    dpush = playback.PlaybackDriver(rec_path, mode='push')
    flat_push = [ln for chunk in dpush.chunks for ln in dpush.lines_of(chunk)]
    with test_hsap.Simulation(boot_events=1, follow=False, camera=0.0) as sim3:
        ex3 = sim3.executor(flat_push + ['end'])
        ex3.analog = True
        ex3.run()
        final3 = list(sim3.bridge.pos)
    print(f'   (push mode on the simulated bridge ends {math.hypot(final1[0] - final3[0], final1[2] - final3[2]):.2f} m from the recorded run)')


def mcp_protocol_checks(tmp):
    s = mcp_session.Session(tmp / 'mcp-proto').make()
    srv = __import__('mcp_server').Server(tmp / 'mcp-proto', capture=lambda w: (str(tmp / 'pic.png'), 'image/png'))
    r = srv.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2024-11-05', 'clientInfo': {'name': 'test-client', 'version': '9'}}})
    check(r['result']['protocolVersion'] == '2024-11-05' and 'tools' in r['result']['capabilities'] and r['result']['serverInfo']['name'] == 'ls-pilot',
          'initialize: the client\'s protocol version when it is one we speak')
    r = srv.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'initialize', 'params': {'protocolVersion': '2099-01-01'}})
    check(r['result']['protocolVersion'] == '2025-06-18', 'initialize: an unknown version is answered with ours')
    check(srv.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'}) is None, 'a notification gets no answer')
    listed = srv.handle({'jsonrpc': '2.0', 'id': 3, 'method': 'tools/list'})['result']['tools']
    check([t['name'] for t in listed] == ['status', 'observe', 'allowed_actions', 'act', 'screenshot'] and all(t['inputSchema']['type'] == 'object' for t in listed),
          'tools/list: observe, allowed actions, act, screenshot and status, each with an input schema')
    r = srv.handle({'jsonrpc': '2.0', 'id': 5, 'method': 'nope'})
    check(r['error']['code'] == -32601, 'an unknown method is a JSON-RPC error')
    r = srv.handle({'jsonrpc': '2.0', 'id': 6, 'method': 'tools/call', 'params': {'name': 'observe', 'arguments': {}}})
    check(r['result']['isError'] and 'no decision point' in r['result']['content'][0]['text'], 'observe before the pilot has asked: a tool error that says so')
    r = srv.handle({'jsonrpc': '2.0', 'id': 7, 'method': 'tools/call', 'params': {'name': 'nope', 'arguments': {}}})
    check(r['result']['isError'], 'an unknown tool is a tool error')
    st = json.loads(srv.handle({'jsonrpc': '2.0', 'id': 8, 'method': 'tools/call', 'params': {'name': 'status', 'arguments': {}}})['result']['content'][0]['text'])
    check('no pilot has made this session' in st['pilot'], 'status without a pilot says how to start one')
    # a pilot's observation on disk
    s.write('session.json', {'run': 'r1', 'segment': 'seg', 'briefing': 'You play.', 'safe_verbs': list(mcp_session.SAFE_VERBS)})
    s.write('status.json', {'phase': 'waiting', 'n': 4, 'pid': os.getpid(), 'alive_ts': time.time(), 'control_sock': None})
    s.write('observe.json', {'n': 4, 'candidates': [{'label': 'go', 'text': 'walk'}, {'label': 'wait', 'text': 'wait'}], 'data': {}, 'safe_verbs': ['walk']})

    def call(name, **args):
        r = srv.handle({'jsonrpc': '2.0', 'id': 9, 'method': 'tools/call', 'params': {'name': name, 'arguments': args}})['result']
        return r, (json.loads(r['content'][0]['text']) if r['content'][0]['type'] == 'text' and r['content'][0]['text'].startswith('{') else r['content'][0])
    r, st = call('status')
    check(st['pilot_alive'] and st['phase'] == 'waiting' and st['n'] == 4 and st['briefing'] == 'You play.', 'status: the phase, the decision, the pilot alive, the briefing')
    s.write('status.json', {'phase': 'waiting', 'n': 4, 'pid': os.getpid(), 'alive_ts': time.time() - 500})
    check(call('status')[1]['pilot_alive'] is False, 'status: a pilot whose heartbeat is old is not alive')
    r, obs = call('observe')
    check(obs['n'] == 4 and len(obs['candidates']) == 2, 'observe: the open decision point')
    t0 = time.time()
    r, obs = call('observe', after_n=4, wait_s=0.3)
    check(time.time() - t0 >= 0.25 and obs.get('note') == 'no newer decision point yet', 'observe with after_n waits for a newer decision and says when there is none')
    r, al = call('allowed_actions')
    check([a['label'] for a in al['actions']] == ['go', 'wait'] and 'walk' in al['own_steps']['verbs'], 'allowed_actions: the labels and the verbs for own steps')
    for args, why in (({'n': 3, 'step': 'go'}, 'a decision that is not the open one'), ({'n': 4, 'step': 'dance'}, 'a label that is not allowed'),
                      ({'n': 4}, 'neither step nor steps'), ({'n': 4, 'step': 'go', 'steps': ['walk 1 1']}, 'both'),
                      ({'n': 4, 'steps': ['cheat 3000']}, 'a verb that is not allowed'), ({'n': 4, 'steps': ['!shots 1']}, 'a debug line'),
                      ({'n': 4, 'steps': ['walk 1 1\npress A']}, 'two lines in one'), ({'n': 4, 'steps': ['walk 1 1'] * 21}, 'too many lines'),
                      ({'step': 'go'}, 'no n')):
        r, out = call('act', **args)
        check(r.get('isError') and not (s.dir / 'act.json').exists(), f'act refused: {why}')
    r, out = call('act', n=4, step='go', plan=['wait', 'zzz'], reason='because', agent='me')
    act = s.read('act.json')
    check(out['accepted'] and act == {'n': 4, 'step': 'go', 'plan': ['wait', 'zzz'], 'reason': 'because', 'agent': 'me'}, 'act: an allowed step is written for the pilot with its plan, reason and who')
    s.remove('act.json')
    r, out = call('act', n=4, steps=['walk 3 4 1', 'press A 200'])
    check(out['accepted'] and s.read('act.json')['steps'] == ['walk 3 4 1', 'press A 200'] and s.read('act.json')['agent'] == 'test-client 9',
          'act: steps of the agent\'s own, with the client\'s name when it gave none')
    (tmp / 'pic.png').write_bytes(b'\x89PNG fake picture bytes')
    r, img = call('screenshot')
    check(img['type'] == 'image' and base64.b64decode(img['data']) == b'\x89PNG fake picture bytes' and img['mimeType'] == 'image/png', 'screenshot: an image content with the picture')
    srv2 = __import__('mcp_server').Server(tmp / 'mcp-proto')
    r = srv2.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': 'screenshot', 'arguments': {}}})['result']
    check(r['isError'] and 'no picture source' in r['content'][0]['text'], 'screenshot with no control socket says why')

    # over stdio, as a client starts it
    c = Client(tmp / 'mcp-stdio')
    init = c.rpc('initialize', {'protocolVersion': '2025-06-18', 'clientInfo': {'name': 'stdio-test', 'version': '1'}, 'capabilities': {}})
    c.send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
    tools = c.rpc('tools/list')
    out, err = c.tool('status')
    c.send([{'jsonrpc': '2.0', 'id': 90, 'method': 'ping'}, {'jsonrpc': '2.0', 'id': 91, 'method': 'tools/list'}])
    batch = json.loads(c.p.stdout.readline())
    c.p.stdin.write('this is not json\n')
    c.p.stdin.flush()
    bad = json.loads(c.p.stdout.readline())
    stderr = c.close()
    check(init['result']['serverInfo']['name'] == 'ls-pilot' and len(tools['result']['tools']) == 5 and not err and 'no pilot' in out['pilot'], 'over stdio: initialize, tools/list and a tool call')
    check(isinstance(batch, list) and [x['id'] for x in batch] == [90, 91] and bad['error']['code'] == -32700 and stderr == '', 'over stdio: a batch is answered, bad JSON is a parse error, nothing on stderr')
    check(json.loads((tmp / 'mcp-stdio' / 'client.json').read_text())['client']['name'] == 'stdio-test', 'the session folder learns which client connected')


def mcp_session_checks(tmp):
    # the driver alone: observe is written, an act comes back, a refusal is written and can be mended
    d = mcp_queue.McpDriver(tmp / 'mcp-driver', first_wait_s=5, wait_s=5, poll_s=0.02)
    d.begin(run='r', segment='s', briefing='briefing text', control_sock=None)
    ctx = make_ctx()
    labels = [c.label for c in ctx.candidates]
    out = {}

    def ask():
        try:
            out['dec'] = d.decide(ctx)
        except base.DriverFailure as e:
            out['fail'] = e
    th = threading.Thread(target=ask)
    th.start()
    for _ in range(100):
        obs = d.session.read('observe.json')
        if obs:
            break
        time.sleep(0.02)
    check(obs['n'] == 1 and [c['label'] for c in obs['candidates']] == labels and obs['briefing'] and 'data' in obs and d.session.read('status.json')['phase'] == 'waiting',
          'the driver writes the decision point with the allowed actions and the briefing, and the phase waiting')
    d.session.write('act.json', {'n': 1, 'step': 'not-offered'})
    for _ in range(100):
        rej = d.session.read('rejected.json')
        if rej:
            break
        time.sleep(0.02)
    check(rej and rej['n'] == 1 and 'not one of the allowed actions' in rej['why'] and th.is_alive(), 'an act that is not allowed is refused with its reason and the decision stays open')
    d.session.write('act.json', {'n': 7, 'step': labels[0]})   # (another decision's: ignored)
    time.sleep(0.2)
    check(th.is_alive(), 'an act for another decision is ignored')
    d.session.write('act.json', {'n': 1, 'step': labels[1], 'plan': [labels[2]], 'agent': 'x'})
    th.join(5)
    dec = out.get('dec')
    check(dec and dec.label == labels[1] and dec.plan == (labels[2],) and dec.provenance.driver == 'mcp' and dec.provenance.note == 'x' and
          d.session.read('status.json')['phase'] == 'executing', 'a good act is the decision')
    # three refusals fail the decision; a timeout is a timeout
    d2 = mcp_queue.McpDriver(tmp / 'mcp-driver2', first_wait_s=5, wait_s=5, poll_s=0.02, max_refusals=2)
    d2.begin(run='r', segment='s')
    out2 = {}

    def ask2():
        try:
            d2.decide(ctx)
        except base.DriverFailure as e:
            out2['fail'] = e
    th = threading.Thread(target=ask2)
    th.start()
    for i in range(2):
        for _ in range(100):
            if d2.session.read('observe.json'):
                break
            time.sleep(0.02)
        d2.session.write('act.json', {'n': 1, 'step': 'bad'})
        time.sleep(0.3)
    th.join(5)
    check(out2.get('fail') and out2['fail'].kind == 'bad_answer' and 'refused' in out2['fail'].reason, 'refused acts in a row fail the decision as a bad answer')
    d3 = mcp_queue.McpDriver(tmp / 'mcp-driver3', first_wait_s=0.3, wait_s=0.3, poll_s=0.02)
    d3.begin(run='r', segment='s')
    try:
        d3.decide(ctx)
        check(False, 'no agent: a timeout')
    except base.DriverFailure as e:
        check(e.kind == 'timeout' and 'no act for decision 1' in e.reason, f'no agent answers: `timeout` ({e.reason})')
    d3.finish('stopped')
    check(d3.session.read('ended.json')['outcome'] == 'stopped' and d3.session.read('status.json')['phase'] == 'ended', 'finish writes ended.json')
    steps = mcp_session.check_steps(['walk 1 2', ' press A 200 '])
    check(steps == ['walk 1 2', 'press A 200'], 'steps are checked and trimmed')


def mcp_shot_checks(tmp):
    """The screenshot tool end to end over stdio: the server asks the run's control socket for a `shot` (a fake bridge answers as the
    game's does: it writes the PNG at the path asked and replies), downscales it and returns it as an image."""
    import socket
    import vision
    sock_path = tmp / 'bridge.sock'
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(sock_path))
    srv.listen(2)
    asked = []

    def serve():
        for _ in range(2):
            try:
                conn, _ = srv.accept()
            except OSError:
                return
            req = json.loads(conn.recv(65536).split(b'\n')[0])
            asked.append(req)
            Path(req['path']).write_bytes(vision.write_png(64, 36, bytes([200, 30, 30]) * (64 * 36)))
            conn.sendall(json.dumps({'id': req['id'], 'ok': True, 'frame': 1, 'present': 1, 'path': req['path'], 'width': 64, 'height': 36}).encode() + b'\n')
            conn.close()
    threading.Thread(target=serve, daemon=True).start()
    session = mcp_session.Session(tmp / 'mcp-shot').make()
    session.write('status.json', {'phase': 'waiting', 'n': 1, 'pid': os.getpid(), 'alive_ts': time.time(), 'control_sock': str(sock_path)})
    c = Client(session.dir)
    c.rpc('initialize', {'protocolVersion': '2025-06-18', 'clientInfo': {'name': 'shot-test', 'version': '1'}, 'capabilities': {}})
    r = c.rpc('tools/call', {'name': 'screenshot', 'arguments': {'width': 320}})
    content = r['result']['content'][0]
    data = base64.b64decode(content.get('data', ''))
    c.close()
    srv.close()
    check(content['type'] == 'image' and content['mimeType'] in ('image/png', 'image/jpeg') and (data[:4] == b'\x89PNG' or data[:2] == b'\xff\xd8') and
          len(asked) == 1 and asked[0]['cmd'] == 'shot' and 'isError' not in r['result'],
          f'screenshot over stdio: a `shot` asked of the control socket, the picture returned as an image ({content.get("mimeType")}, {len(data)} bytes)')


def mcp_pilot_checks(tmp):
    """An agent (this test, over the server's stdio) plays the made-up house: one allowed step, then steps of its own; a pilot-side
    refusal in the middle; the same run loop, transcript and chain report as for any driver."""
    session = tmp / 'mcp-house'
    drv = mcp_queue.McpDriver(session, first_wait_s=20, wait_s=20, poll_s=0.02)
    chain = Chain([drv], want='mcp')
    drv.begin(run='house-mcp', segment='fake-house', briefing='play')
    seg_path = tmp / 'mcp-fake.toml'
    seg_path.write_text(tp.SEGMENT)
    seg = pilot.Segment(seg_path)
    live = tmp / 'live-mcp'
    ch = pilot.Channel(live)
    ch.send(pilot.watch_lines(seg.watch))
    game = tp.FakeGame(live)
    game.start()
    assert ch.wait(lambda e: e['ev'] == 'gameplay', 5)
    st = ch.wait(lambda e: e['ev'] == 'state', 5)
    run_dir = tmp / 'run-mcp'
    run_dir.mkdir()
    p = pilot.Pilot(seg, chain, ch, run_dir, run_dir.name, lambda: True, None, 20)
    p.plan = None
    result = {}
    def play():
        result['outcome'] = p.run(st)
        chain.finish(result['outcome'])   # (as cmd_run does: the agent's observe then learns the run has ended)
    th = threading.Thread(target=play, daemon=True)
    th.start()

    c = Client(session)
    c.rpc('initialize', {'protocolVersion': '2025-06-18', 'clientInfo': {'name': 'house-agent', 'version': '1'}, 'capabilities': {}})
    c.send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
    own = {2: ['walk 0 0 1'], 3: ['press A 200'], 4: ['walk 2 0 0.5'], 5: ['until flag Scene_Played=1 timeout 5'], 6: ['walk 5 0 0.5'],
           7: ['walk 6 3 1'], 8: ['until flag Talked=1 timeout 10 press A every 2']}
    seen, last_n, refused_once = [], 0, False
    for _ in range(40):
        obs, err = c.tool('observe', after_n=last_n, wait_s=20)
        if isinstance(obs, dict) and 'ended' in obs:
            break
        if err:
            seen.append(('error', obs))
            break
        n = obs['n']
        seen.append(n)
        last_n = n
        if n == 1:
            check(obs.get('briefing', '').startswith('You choose the next step'), 'the first observation carries the same briefing a model is given')
            out, err = c.tool('allowed_actions')
            check([a['label'] for a in out['actions']] == [x['label'] for x in obs['candidates']] and not err, 'allowed_actions matches the observation')
            out, err = c.tool('act', n=1, step=obs['candidates'][0]['label'], reason='first allowed step', agent='house-agent')
            check(out['accepted'], 'act: the first allowed step')
        elif n == 3 and not refused_once:
            refused_once = True
            (session / 'act.json').write_text(json.dumps({'n': 3, 'step': 'not-a-step'}))   # (bypassing the server: the pilot refuses it itself)
            obs2, err = c.tool('observe', after_n=2, wait_s=5)
            for _ in range(60):
                time.sleep(0.05)
                obs2, err = c.tool('observe', after_n=2, wait_s=0.2)
                if obs2.get('last_refusal'):
                    break
            check(obs2.get('last_refusal') and 'not one of the allowed actions' in obs2['last_refusal']['why'], 'observe shows the pilot\'s refusal of an act, and the decision stays open')
            out, err = c.tool('act', n=3, steps=own[n])
        else:
            out, err = c.tool('act', n=n, steps=own[n])
        if err:
            seen.append(('act error', out))
            break
    th.join(30)
    err_text = c.close()
    tr = transcript(run_dir)
    dec = [e for e in tr if e['kind'] == 'decision']
    check(result.get('outcome') == 'solved' and not th.is_alive(), f'an agent over MCP solved the house: {result.get("outcome")}, {len(dec)} decisions, saw {seen[:12]}')
    check(set(p.who) == {'mcp'} and dec[0]['decider'] == 'mcp' and dec[1]['choice'] == 'mcp:steps' and dec[1]['answer']['steps'] == ['walk 0 0 1'] and
          dec[1]['driver']['note'] == 'house-agent 1', 'every decision is the agent\'s; its own steps are the step `mcp:steps` and are in the transcript')
    sent = [e['src'] for e in ch.events if e['ev'] == 'step' and e.get('in')]
    check('walk 0 0 1' in sent and 'press A 200' in sent, 'the agent\'s steps went through the pilot\'s input path')
    ended = mcp_session.Session(session).read('ended.json')
    check(ended and ended['outcome'] == 'solved' and chain.report()['decisions_by_driver'] == {'mcp': len(dec)} and chain.report()['stats']['mcp']['refusals'] == 1,
          'the session ends with the outcome; the report counts the agent\'s decisions and the refusal')
    check(err_text == '' and secret_free(json.dumps(tr)), 'the server wrote nothing on stderr')

    # no agent: the chain falls back to scripted after the timeouts and the run is solved all the same
    drv2 = mcp_queue.McpDriver(tmp / 'mcp-nobody', first_wait_s=0.2, wait_s=0.2, poll_s=0.02)
    chain2 = Chain([drv2, ScriptedDriver()], want='mcp')
    seg2, p2, outcome2, ch2, run2 = play_house(chain2, tmp)
    fb = [e for e in transcript(run2) if e['kind'] == 'driver-fallback']
    check(outcome2 == 'solved' and [e['failure'] for e in fb] == ['timeout', 'timeout'] and fb[1]['benched'] and fb[0]['to'] == 'scripted' and set(p2.who) == {'scripted'},
          'no agent: two timeouts bench mcp, scripted plays the house, both logged')


# ---- 7. the scenario's table and the command line

def scenario_checks(tmp):
    text = tp.SEGMENT.replace('[[goal]]', '[driver]\nwant = "openrouter"\nfallbacks = ["scripted"]\nopenrouter_model = "some/model"\n'
                              'script = [{name = "a", goal = "door", lines = ["press A 200"]}]\n[[goal]]', 1)
    path = tmp / 'with-driver.toml'
    path.write_text(text)
    seg = pilot.Segment(path)
    check(seg.driver['want'] == 'openrouter' and seg.driver['fallbacks'] == ['scripted'] and seg.driver['openrouter_model'] == 'some/model' and seg.driver['script'][0]['lines'] == ['press A 200'],
          'a scenario\'s driver table is read: want, fallbacks, options, scripts')
    check(pilot.Segment(tmp / 'fake.toml').driver is None if (tmp / 'fake.toml').exists() else True, 'a scenario with no table has none')
    for bad, why in (('want = "gpt"', 'an unknown driver'), ('want = "decisions"\nfallbacks = ["decisions"]', 'the wanted driver as its own fallback'),
                     ('want = "decisions"\nfallbacks = ["scripted", "scripted"]', 'a fallback twice'), ('want = "decisions"\nspeed = 3', 'an unknown key'),
                     ('want = "scripted"\nscript = [{name = "x"}]', 'a script with no steps')):
        p = tmp / 'bad-driver.toml'
        p.write_text(tp.SEGMENT.replace('[[goal]]', f'[driver]\n{bad}\n[[goal]]', 1))
        try:
            pilot.Segment(p)
            check(False, f'refused: {why}')
        except ValueError as e:
            check(True, f'refused: {why} ({str(e)[:50]})')
    check(drivers.chain_names('decisions', None, False) == (['decisions', 'openrouter', 'scripted'], ['chat: not configured (PILOT_CHAT_BASE / --chat-base), left out of the default chain']),
          'decisions with no fallbacks named: the rest of the default chain, chat left out when it is not configured')
    check(drivers.chain_names('decisions', None, True)[0] == ['decisions', 'openrouter', 'chat', 'scripted'], 'chat is in the default chain when a base URL is configured')
    check(drivers.chain_names('default', None, True)[0] == ['decisions', 'openrouter', 'chat', 'scripted'] and drivers.chain_names('openrouter', None, False)[0] == ['openrouter', 'scripted'],
          'default is the whole chain; openrouter starts the tail at itself')
    check(drivers.chain_names('playback', None, True)[0] == ['playback'] and drivers.chain_names('scripted', None, True)[0] == ['scripted'] and
          drivers.chain_names('mcp', None, True)[0] == ['mcp', 'scripted'], 'playback and scripted never fall back to a model on their own; mcp falls back to scripted')
    check(drivers.chain_names('playback', ['scripted'], False)[0] == ['playback', 'scripted'] and drivers.chain_names('decisions', [], False)[0] == ['decisions'],
          'fallbacks named are exactly the fallbacks; an empty list is none')
    try:
        drivers.chain_names('default', ['decisions', 'scripted'], False)
        check(False, 'the default chain with a fallback that repeats its head is refused')
    except ValueError:
        check(True, 'the default chain with a fallback that repeats its head is refused')
    check(drivers.chain_names('chat', None, False)[0] == ['chat', 'scripted'], 'chat wanted explicitly stays in even when it is not configured (it will say so)')
    ns = lambda **k: argparse.Namespace(**{'driver': None, 'fallbacks': None, **k})   # noqa: E731
    check(drivers.resolve(ns(), None, {})[0] is None, 'no driver named anywhere: none (the run plays on the rules as always)')
    check(drivers.resolve(ns(), seg, {})[:2] == ('openrouter', ['scripted']), 'the scenario names it')
    check(drivers.resolve(ns(driver='decisions,openrouter'), seg, {})[:2] == ('decisions', ['openrouter']), 'the command line over the scenario')
    check(drivers.resolve(ns(driver='decisions', fallbacks='none'), seg, {})[:2] == ('decisions', []) and drivers.resolve(ns(fallbacks='scripted'), seg, {})[:2] == ('openrouter', ['scripted']),
          '--fallbacks none and --fallbacks a,b')
    check(drivers.resolve(ns(), None, {'PILOT_DRIVER': 'chat,scripted'})[:2] == ('chat', ['scripted']), 'PILOT_DRIVER is the shell\'s default')
    for bad in ('nonsense', 'decisions,nonsense'):
        try:
            drivers.resolve(ns(driver=bad), None, {})
            check(False, f'--driver {bad} is refused')
        except ValueError:
            check(True, f'--driver {bad} is refused')
    try:
        drivers.resolve(ns(driver='decisions', fallbacks='x'), None, {})
        check(False, '--fallbacks x is refused')
    except ValueError:
        check(True, '--fallbacks x is refused')
    check(drivers.run_settings(Chain([ScriptedDriver()])) == {'recovery': True, 'humanize': 0} and
          drivers.run_settings(Chain([Stub('playback', ['x'])])) == {'recovery': False, 'humanize': 0} and
          drivers.run_settings(Chain([Stub('openrouter', ['x'])])) == {'recovery': True, 'humanize': None},
          'a replay and an agent run with no guard; a scripted run with no seeded delays; a model as before')
    saved_env = dict(os.environ)
    os.environ.update({'OPENAI_API_KEY': SECRETS[0], 'OPENROUTER_API_KEY': SECRETS[1], 'PILOT_CHAT_API_KEY': SECRETS[2]})
    try:
        env = pilot.runner_env()
    finally:
        os.environ.clear()
        os.environ.update(saved_env)
    check(not any(k in env for k in ('OPENAI_API_KEY', 'OPENROUTER_API_KEY', 'PILOT_CHAT_API_KEY')), 'the game and its runner never see a key in their environment')
    try:
        drivers.build_chain('playback', None, args=ns(), table={}, client=None, run_id='x', segment='s', run_dir=tmp)
        check(False, 'playback without a recording is refused')
    except ValueError as e:
        check('recording' in str(e), 'playback without a recording is refused when the chain is built')


def cmd_run_checks(tmp):
    """`pilot.py run` end to end, a fake hsap behind its command line (the made-up house, and the push game)."""
    fake = tmp / 'fake_hsap.py'
    fake.write_text(
        "import sys\nfrom pathlib import Path\n"
        f"sys.path.insert(0, {str(HERE)!r})\nimport test_pilot, test_drivers\n"
        "a = sys.argv[1:]\nlive = Path(a[a.index('--live') + 1])\nlive.mkdir(parents=True, exist_ok=True)\n"
        "(live / 'argv.json').write_text(__import__('json').dumps(a))\n"
        "(test_drivers.PushGame if 'push' in a[1] else test_pilot.FakeGame)(live).run()\n")
    seg_path = tmp / 'house-cmd.toml'
    seg_path.write_text(tp.SEGMENT)
    os.environ['PILOT_OPENAI_KEY_FILE'] = str(tmp / 'no-such-key')
    os.environ['PILOT_OPENROUTER_KEY_FILE'] = str(tmp / 'no-or-key')
    saved = pilot.HSAP
    pilot.HSAP = fake

    def ns(seg, tag, **k):
        d = dict(segment=str(seg), decider=None, driver=None, fallbacks=None, recording=None, openrouter_model=None, chat_base=None, chat_model=None,
                 chat_mode=None, mcp_dir=None, mcp_wait_s=None, replay=None, planner=False, copy=str(tmp / 'copy'), tag=tag, attach=None, save=None,
                 wall=60, max_decisions=None, follow=[], end_hold=0.0, shots=0, api_base=None, allowance_usd=None, allowance_since='2026-01-01',
                 matches=None, humanize=None, humanize_seed=None, recover=False, bad_points=str(tmp / 'bad'), no_bad_points=True, vision=None)
        d.update(k)
        return argparse.Namespace(**d)

    def summary(tag):
        return json.loads((pilot.HERE / 'runs' / tag / 'summary.json').read_text())
    try:
        code = pilot.cmd_run(ns(seg_path, 'cmd-scripted', driver='scripted'))
        s = summary('cmd-scripted')
        check(code == 0 and s['outcome'] == 'solved' and s['decider'] == 'scripted' and s['drivers']['spec']['chain'] == ['scripted'] and
              s['humanize']['level'] == 0 and s['drivers']['per_decision'][0][2] == 'scripted' and s['drivers']['decisions_by_driver'] == {'scripted': s['decisions']},
              f"--driver scripted: solved, no seeded delays, the summary says scripted made all {s['decisions']} decisions")
        check(s['recording'] is None, 'a game side with no input journal leaves no recording (and says so)')

        code = pilot.cmd_run(ns(seg_path, 'cmd-default', driver='decisions,openrouter,scripted'))
        s = summary('cmd-default')
        check(code == 0 and s['decider'] == 'decisions' and s['drivers']['spec'] == {'want': 'decisions', 'fallbacks': ['openrouter', 'scripted'], 'chain': ['decisions', 'openrouter', 'scripted']} and
              [(f['driver'], f['failure']) for f in s['drivers']['fallbacks']] == [('decisions', 'unavailable'), ('openrouter', 'unavailable')] and
              set(s['drivers']['benched']) == {'decisions', 'openrouter'} and s['drivers']['availability']['scripted']['ok'] and s['ledger'] == {},
              f"--driver decisions,openrouter,scripted with no keys: both fallbacks in the summary, scripted decided, nothing spent ({s['drivers']['fallbacks']})")
        tr = [json.loads(x) for x in (pilot.HERE / 'runs' / 'cmd-default' / 'transcript.jsonl').read_text().splitlines()]
        check(sum(e['kind'] == 'driver-fallback' for e in tr) == 2, 'and the transcript has the two fallback events')

        code = pilot.cmd_run(ns(seg_path, 'cmd-legacy', decider='rules'))
        s = summary('cmd-legacy')
        check(code == 0 and s['decider'] == 'rules' and 'drivers' not in s, '--decider rules is the older way, unchanged: no driver block')
        code = pilot.cmd_run(ns(seg_path, 'cmd-none'))
        s = summary('cmd-none')
        check(code == 0 and s['decider'] == 'rules' and 'drivers' not in s, 'naming nothing plays on the rules as it always did')
        err = io.StringIO()
        saved_err = sys.stderr
        sys.stderr = err
        try:
            code = pilot.cmd_run(ns(seg_path, 'cmd-both', decider='rules', driver='scripted'))
            code2 = pilot.cmd_run(ns(seg_path, 'cmd-bad', driver='nonsense'))
            code3 = pilot.cmd_run(ns(seg_path, 'cmd-norec', driver='playback'))
        finally:
            sys.stderr = saved_err
        check(code == 2 and code2 == 2 and code3 == 2 and 'both say who decides' in err.getvalue() and 'no driver' in err.getvalue() and 'needs a recording' in err.getvalue() and
              not (pilot.HERE / 'runs' / 'cmd-norec').exists(), 'two ways at once, an unknown driver and a playback with no recording are refused (exit 2, no run folder left)')
        # --driver mcp with nobody attached: the session is opened and told, the agent never comes, scripted plays, the session says how it ended
        os.environ['PILOT_MCP_FIRST_WAIT_S'] = '0.2'
        out = io.StringIO()
        saved_out, sys.stdout = sys.stdout, out
        try:
            code = pilot.cmd_run(ns(seg_path, 'cmd-mcp', driver='mcp', mcp_wait_s=0.2, mcp_dir=str(tmp / 'mcp-cmd')))
        finally:
            sys.stdout = saved_out
            os.environ.pop('PILOT_MCP_FIRST_WAIT_S')
        s = summary('cmd-mcp')
        ended = mcp_session.Session(tmp / 'mcp-cmd').read('ended.json')
        check(code == 0 and s['outcome'] == 'solved' and s['recovery'] is False and s['humanize']['level'] == 0 and s['drivers']['spec']['chain'] == ['mcp', 'scripted'] and
              [f['failure'] for f in s['drivers']['fallbacks']] == ['timeout', 'timeout'] and ended and ended['outcome'] == 'solved' and
              'mcp_server.py --session ' + str(tmp / 'mcp-cmd') in out.getvalue(),
              f"--driver mcp: the pilot says how to attach an agent, no agent comes, two timeouts, scripted plays, the session ends with the outcome ({s['outcome']})")
        sc = tmp / 'scn.toml'
        sc.write_text(tp.SEGMENT.replace('[[goal]]', '[driver]\nwant = "scripted"\n[[goal]]', 1))
        code = pilot.cmd_run(ns(sc, 'cmd-scenario'))
        s = summary('cmd-scenario')
        check(code == 0 and s['drivers']['spec']['want'] == 'scripted', 'the scenario\'s own driver table is what runs')

        # record + playback through pilot.py: the push game's run is recorded by cmd_run (the fake game keeps hsap's journal), then replayed
        pushgame_seg = tmp / 'push-cmd-scripts.toml'
        text = PUSH_SEGMENT.replace('[[goal]]', '[driver]\nwant = "scripted"\nscript = [' + ', '.join(
            '{name = "%s", lines = %s}' % (x['name'], json.dumps(x['lines'])) for x in PUSH_SCRIPTS) + ']\n[[goal]]', 1)
        pushgame_seg.write_text(text)
        code = pilot.cmd_run(ns(pushgame_seg, 'cmd-push-rec'))
        s = summary('cmd-push-rec')
        rec_file = pilot.HERE / 'runs' / 'cmd-push-rec' / 'recording.jsonl'
        check(code == 0 and s['outcome'] == 'solved' and s['recording'] and s['recording']['inputs'] == 3 and s['recording']['marks'] == 5 and rec_file.exists() and
              s['labels'] == {k: 1 for k in sorted(f"script:{x['name']}" for x in PUSH_SCRIPTS)}, f"a run's recording is written next to its summary ({s['recording']})")
        pb = tmp / 'push-playback.toml'
        pb.write_text(PUSH_SEGMENT)
        code = pilot.cmd_run(ns(pb, 'cmd-push-play', driver='playback', recording=str(rec_file)))
        s = summary('cmd-push-play')
        check(code == 0 and s['outcome'] == 'solved' and s['decider'] == 'playback' and s['recovery'] is False and s['humanize']['level'] == 0 and
              s['drivers']['stats']['playback']['marks_checked'] >= 3 and s['drivers']['decisions_by_driver'] == {'playback': 3},
              f"--driver playback --recording: solved, no guard, no delays, marks checked ({s['drivers']['stats']['playback']})")
        argv = json.loads((pilot.HERE / 'runs' / 'cmd-push-play' / 'live' / 'argv.json').read_text())
        check('--save' not in argv and '--boot' not in argv, 'hsap is started without a save or boot when neither the scenario nor the recording names one')
        # the recording's header names its save: the replay starts from it
        h, lines = inputlog.read_recording(rec_file)
        h['save'], h['boot'] = 'lib-entry', 'continue'
        rec2 = tmp / 'with-setup.jsonl'
        inputlog.write_recording(rec2, [h] + lines)
        code = pilot.cmd_run(ns(pb, 'cmd-push-setup', driver='playback', recording=str(rec2)))
        argv = json.loads((pilot.HERE / 'runs' / 'cmd-push-setup' / 'live' / 'argv.json').read_text())
        check(argv[argv.index('--boot') + 1] == 'continue' and argv[argv.index('--save') + 1].endswith('lib-entry'), 'the playback starts the game from the recording\'s own save and boot')
    finally:
        pilot.HSAP = saved


def drivers_cmd_checks(tmp):
    """`pilot.py drivers`: availability without a request, and `--ask` as the one tiny live request (here against a fake OpenRouter)."""
    import contextlib
    or_key = tmp / 'smoke-or.key'
    write_key(or_key, SECRETS[1])
    os.environ['PILOT_OPENROUTER_KEY_FILE'] = str(tmp / 'smoke-no-key')
    os.environ['PILOT_OPENAI_KEY_FILE'] = str(tmp / 'smoke-no-openai-key')
    os.environ.pop('PILOT_OPENROUTER_BASE', None)
    reset_ledger()
    set_caps()

    def run(**kw):
        a = argparse.Namespace(**{'ask': None, 'api_base': None, 'openrouter_model': None, 'chat_base': None, 'chat_model': None,
                                  'chat_mode': None, **kw})
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = pilot.cmd_drivers(a)
        return code, json.loads(buf.getvalue())
    code, out = run()
    d = out['drivers']
    check(code == 0 and not d['decisions']['available'] and 'no key' in d['decisions']['why_not'] and not d['openrouter']['available'] and
          'no key' in d['openrouter']['why_not'] and d['openrouter']['model'] == 'openai/gpt-6-luna' and not d['chat']['available'] and
          'not configured' in d['chat']['why_not'] and d['scripted']['available'] and not ledger_rows(),
          'pilot.py drivers: each driver, whether it can be asked and why not, no request made')
    code, out = run(ask='openrouter')
    check(code == 1 and out['ask']['failed'] == 'unavailable' and 'no key' in out['ask']['reason'], '--ask with no key says so (exit 1)')
    fake = Fake(chat_good())
    os.environ['PILOT_OPENROUTER_BASE'] = fake.base
    os.environ['PILOT_OPENROUTER_KEY_FILE'] = str(or_key)
    code, out = run(ask='openrouter')
    row = ledger_rows()[-1]
    check(code == 0 and out['ask']['step'] in out['ask']['offered'] and out['ask']['provenance']['cost_usd'] == 0.00012 and
          out['ledger']['decision']['requests'] == 1 and row['run'].startswith('drivers-smoke-') and row['cost_usd'] == 0.00012 and
          secret_free(json.dumps(out), json.dumps(row)) and len(fake.seen) == 1, '--ask openrouter: one request, its cost in the ledger, no key anywhere in the output')
    fake.close()
    os.environ.pop('PILOT_OPENROUTER_BASE')
    err = io.StringIO()
    saved_err, sys.stderr = sys.stderr, err
    try:
        code = pilot.cmd_drivers(argparse.Namespace(ask='scripted', api_base=None, openrouter_model=None, chat_base=None, chat_model=None, chat_mode=None))
    finally:
        sys.stderr = saved_err
    check(code == 2 and '--ask: one of decisions, openrouter, chat' in err.getvalue(), '--ask names a driver that costs: scripted is refused')


# ---- 8. real agents: our OpenRouter agent loop and the omp launcher

OWN_STEPS = {2: ['walk 0 0 1'], 3: ['press A 200'], 4: ['walk 2 0 0.5'], 5: ['until flag Scene_Played=1 timeout 5'], 6: ['walk 5 0 0.5'],
             7: ['walk 6 3 1'], 8: ['until flag Talked=1 timeout 10 press A every 2']}


def own_policy(obs):
    """The act arguments a made-up player gives for an observation of the made-up house (the first decision: its first allowed step)."""
    n = obs['n']
    return {'n': n, 'step': obs['candidates'][0]['label']} if n == 1 else {'n': n, 'steps': OWN_STEPS.get(n, ['wait 1'])}


def model_reply(body, message, cost=0.00005):
    usage = {'prompt_tokens': 800, 'completion_tokens': 20, 'total_tokens': 820, 'cost': cost}
    return 200, {'id': 'gen-agent', 'model': body['model'], 'choices': [{'message': message, 'finish_reason': 'stop'}], 'usage': usage}, 0


def tool_call(n, name, args):
    return {'role': 'assistant', 'content': None, 'tool_calls': [{'id': f'call_{n}', 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}]}


def agent_model(n, path, body, headers):
    """A made-up tool-calling model that plays the house through the pilot's tools: observe, act as own_policy says, observe again."""
    tools = [m for m in body['messages'] if m['role'] == 'tool']
    if not tools:
        return model_reply(body, tool_call(n, 'observe', {'after_n': 0, 'wait_s': 20}))
    try:
        j = json.loads(tools[-1]['content'])
    except ValueError:
        j = {}
    if 'ended' in j:
        return model_reply(body, {'role': 'assistant', 'content': 'The run ended.'})
    if 'candidates' in j and 'n' in j:
        return model_reply(body, tool_call(n, 'act', own_policy(j)))
    if j.get('accepted'):
        return model_reply(body, tool_call(n, 'observe', {'after_n': j['n'], 'wait_s': 20}))
    return model_reply(body, tool_call(n, 'observe', {'after_n': 0, 'wait_s': 20}))


def house_pilot(tmp, tag, session, chain, live_name=None):
    """A Pilot on the made-up house with the given chain, run in a thread; returns (pilot, thread, result dict, channel)."""
    seg_path = tmp / f'{tag}.toml'
    seg_path.write_text(tp.SEGMENT)
    seg = pilot.Segment(seg_path)
    live = tmp / f'live-{tag}'
    ch = pilot.Channel(live)
    ch.send(pilot.watch_lines(seg.watch))
    game = tp.FakeGame(live)
    game.start()
    assert ch.wait(lambda e: e['ev'] == 'gameplay', 5)
    st = ch.wait(lambda e: e['ev'] == 'state', 5)
    run_dir = tmp / f'run-{tag}'
    run_dir.mkdir()
    p = pilot.Pilot(seg, chain, ch, run_dir, tag, lambda: True, None, 40)
    p.plan = None
    result = {}

    def play():
        result['outcome'] = p.run(st)
        chain.finish(result['outcome'])
    th = threading.Thread(target=play, daemon=True)
    th.start()
    return p, th, result, ch, run_dir


def agent_loop_checks(tmp):
    import mcp_agent
    set_caps()
    reset_ledger()
    session = tmp / 'agent-session'
    drv = mcp_queue.McpDriver(session, first_wait_s=60, wait_s=60, poll_s=0.02)
    chain = Chain([drv], want='mcp')
    drv.begin(run='agent-test', segment='fake-house', briefing='play')
    p, th, result, ch, run_dir = house_pilot(tmp, 'agent-test', session, chain)
    fake = Fake(agent_model)
    client = chat.ChatClient('agent-test', 'fake-house', fake.base, 'openrouter', chat.OPENROUTER_KEY, key_required=True, send_key=False)
    res = mcp_agent.run_agent(session, client, model='fake/agent', run_id='agent-test', max_steps=40, wall_s=90, usd=1.0)
    th.join(30)
    rows = [r for r in ledger_rows() if r.get('run') == 'agent-test']
    check(result.get('outcome') == 'solved' and res['ended'] and res['stop'] == 'the run ended' and set(p.who) == {'mcp'},
          f"a tool-calling model as an MCP client plays the house to the end through the real stdio server ({result.get('outcome')}, {res['steps_used']} model calls, {res['tool_calls']} tool calls)")
    check(len(rows) == res['steps_used'] == len(fake.seen) and all(r['kind'] == 'agent' and r['base'] == 'openrouter' for r in rows) and
          abs(res['spent_usd'] - 0.00005 * len(rows)) < 1e-9 and abs(sum(r['cost_usd'] for r in rows) - res['spent_usd']) < 1e-9,
          f"every model request is a ledger row of kind `agent` under the run, costed from the response ({len(rows)} rows, {res['spent_usd']} USD)")
    b0 = fake.seen[0]['body']
    names = {t['function']['name'] for t in b0['tools']}
    check(names == {'status', 'observe', 'allowed_actions', 'act', 'screenshot'} and b0['tool_choice'] == 'auto' and 'parallel_tool_calls' not in b0 and
          b0['provider'] == {'require_parameters': True} and b0['messages'][0]['role'] == 'system' and all('inputSchema' not in t['function'] for t in b0['tools']) and
          all(t['function']['parameters']['type'] == 'object' for t in b0['tools']),
          "the server's tools, listed over MCP, are the functions given to the model (schemas as parameters)")
    last = fake.seen[-1]['body']['messages']
    tool_texts = [m['content'] for m in last if m['role'] == 'tool']
    check(len(tool_texts) > mcp_agent.KEEP_FULL and all(len(t) <= mcp_agent.SHORT + 40 for t in tool_texts[:-mcp_agent.KEEP_FULL]) and
          any(len(t) > mcp_agent.SHORT + 40 for t in tool_texts[-mcp_agent.KEEP_FULL:]),
          'older tool results are shortened in the history that is sent again; the latest are whole')
    check(secret_free(json.dumps(res), json.dumps(fake.seen)) and all('Authorization' in s['headers'] and s['headers']['Authorization'] == 'Bearer standin' for s in fake.seen), 'no key in the agent\'s output or requests')
    fake.close()

    # budgets and the other ways to stop
    mcp_session.Session(tmp / 'idle-session').make()

    def status_model(cost, delay=0.0):
        return lambda n, path, body, headers: (model_reply(body, tool_call(n, 'status', {}), cost)[0], model_reply(body, tool_call(n, 'status', {}), cost)[1], delay)

    def play(model, **kw):
        fk = Fake(model)
        c = chat.ChatClient('agent-budget', 'x', fk.base, 'openrouter', chat.OPENROUTER_KEY, key_required=True, send_key=False)
        try:
            return mcp_agent.run_agent(tmp / 'idle-session', c, model='fake/agent', run_id='agent-budget', **kw), fk
        finally:
            fk.close()
    r, _ = play(status_model(0.00001), max_steps=3, wall_s=60, usd=1.0)
    check(r['stop'] == 'step budget' and r['steps_used'] == 3 and r['tool_calls'] == 3 and not r['ended'], 'the step budget stops the agent')
    r, _ = play(status_model(0.01), max_steps=50, wall_s=60, usd=0.015)
    check(r['stop'] == 'dollar budget' and r['steps_used'] == 2 and abs(r['spent_usd'] - 0.02) < 1e-9, f"the dollar budget stops it once it is spent ({r['steps_used']} calls, {r['spent_usd']} USD)")
    r, _ = play(status_model(0.00001, delay=0.5), max_steps=50, wall_s=0.3, usd=1.0)
    check(r['stop'] == 'wall time' and r['steps_used'] == 1, 'the wall-time budget stops it')
    r, _ = play(lambda n, p, b, h: model_reply(b, {'role': 'assistant', 'content': 'I will think.'}), max_steps=20, wall_s=60, usd=1.0)
    check(r['stop'] == 'the model stopped calling tools' and r['steps_used'] == 3 and r['tool_calls'] == 0, 'a model that only talks is nudged twice, then stopped')
    seen_prose = []

    def chatty(n, path, body, headers):   # prose, a tool call, prose, a tool call, ...: never two prose answers in a row
        seen_prose.append(body['messages'][-1])
        if n % 2 == 0:
            return model_reply(body, {'role': 'assistant', 'content': 'The mission is accomplished.'})
        return model_reply(body, tool_call(n, 'status', {}))
    r, _ = play(chatty, max_steps=6, wall_s=60, usd=1.0)
    check(r['stop'] == 'step budget' and r['tool_calls'] == 3 and 'The run has not ended' in seen_prose[1]['content'] and 'after_n = 0' in seen_prose[1]['content'],
          'a model that declares victory early is told the run has not ended; a nudge does not count against it once it calls tools again')
    os.environ['PILOT_OPENROUTER_KEY_FILE'] = str(tmp / 'no-agent-key')
    real = chat.ChatClient('agent-nokey', 'x', chat.OPENROUTER_BASE, 'openrouter', chat.OPENROUTER_KEY, key_required=True, send_key=True)
    r = mcp_agent.run_agent(tmp / 'idle-session', real, model='fake/agent', run_id='agent-nokey', max_steps=5, wall_s=30, usd=1.0)
    check(r['stop'].startswith('NoKey') and r['steps_used'] == 0 and 'no key' in r['stop'], f"no key: the agent stops before any request ({r['stop']})")

    class FakeMcp:
        def start(self):
            return [{'name': 'screenshot', 'description': 'a picture', 'inputSchema': {'type': 'object', 'properties': {}}}]

        def call(self, name, args):
            return {'content': [{'type': 'image', 'data': 'QUJD', 'mimeType': 'image/png'}]}

        def close(self):
            pass

    def pic_model(n, path, body, headers):
        if not any(m['role'] == 'tool' for m in body['messages']):
            return model_reply(body, tool_call(n, 'screenshot', {}))
        return model_reply(body, {'role': 'assistant', 'content': 'I see it.'})
    fk = Fake(pic_model)
    c = chat.ChatClient('agent-pic', 'x', fk.base, 'openrouter', chat.OPENROUTER_KEY, key_required=True, send_key=False)
    mcp_agent.run_agent(None, c, model='fake/agent', run_id='agent-pic', max_steps=2, wall_s=30, usd=1.0, mcp=FakeMcp())
    second = fk.seen[1]['body']['messages']
    img = [part for m in second if m['role'] == 'user' and isinstance(m['content'], list) for part in m['content'] if part.get('type') == 'image_url']
    fk.close()
    check(img and img[0]['image_url']['url'] == 'data:image/png;base64,QUJD' and any(m['role'] == 'tool' and 'picture' in m['content'] for m in second),
          'a screenshot result reaches the model as an image')


def agent_cmd_run_checks(tmp):
    """`pilot.py run --driver mcp --mcp-agent loop|omp` end to end with a fake hsap (the made-up house): the pilot starts the agent when the first
    decision point is open, the agent plays, the summary and the ledger say so. The model is a fake OpenRouter; `omp` is a fake executable that
    follows omp's command line and its .omp/mcp.json."""
    fake_hsap = tmp / 'fake_hsap2.py'
    fake_hsap.write_text(
        "import sys\nfrom pathlib import Path\n"
        f"sys.path.insert(0, {str(HERE)!r})\nimport test_pilot\n"
        "a = sys.argv[1:]\nlive = Path(a[a.index('--live') + 1])\nlive.mkdir(parents=True, exist_ok=True)\n"
        "test_pilot.FakeGame(live).run()\n")
    seg_path = tmp / 'house-agent.toml'
    seg_path.write_text(tp.SEGMENT)
    fake = Fake(agent_model)
    saved_env = dict(os.environ)
    os.environ.update({'PILOT_OPENROUTER_BASE': fake.base, 'PILOT_LEDGER': str(openai_api.LEDGER), 'PILOT_CAPS': str(openai_api.CAPS), 'PILOT_AGENT_WALL': '120',
                       'PILOT_MCP_FIRST_WAIT_S': '60'})
    # a fake `omp`: reads its project's .omp/mcp.json, starts the server named there, plays the house through it, prints json lines with a usage
    bindir = tmp / 'fakebin'
    bindir.mkdir()
    (bindir / 'omp').write_text(
        "#!/usr/bin/env python3\nimport json, subprocess, sys\nfrom pathlib import Path\n"
        "argv = sys.argv[1:]\ncwd = Path(argv[argv.index('--cwd') + 1])\n"
        "cfg = json.loads((cwd / '.omp' / 'mcp.json').read_text())['mcpServers']['pilot']\n"
        "Path(cwd / 'argv.json').write_text(json.dumps(argv))\n"
        "p = subprocess.Popen([cfg['command']] + cfg['args'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)\n"
        "n = [0]\n"
        "def rpc(m, params=None):\n    n[0] += 1\n    p.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': n[0], 'method': m, 'params': params or {}}) + '\\n'); p.stdin.flush()\n    return json.loads(p.stdout.readline())['result']\n"
        "def emit(**e):\n    print(json.dumps(e), flush=True)\n"
        "emit(type='agent_start')\nrpc('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 'omp', 'version': 'fake'}})\n"
        f"OWN = {OWN_STEPS!r}\nlast = 0\n"
        "for _ in range(40):\n"
        "    emit(type='tool_execution_start', toolName='mcp_pilot_observe')\n"
        "    r = rpc('tools/call', {'name': 'observe', 'arguments': {'after_n': last, 'wait_s': 20}})\n"
        "    j = json.loads(r['content'][0]['text'])\n"
        "    if 'ended' in j: break\n"
        "    last = j['n']\n"
        "    args = {'n': last, 'step': j['candidates'][0]['label']} if last == 1 else {'n': last, 'steps': OWN.get(last, ['wait 1'])}\n"
        "    emit(type='tool_execution_start', toolName='mcp_pilot_act')\n"
        "    rpc('tools/call', {'name': 'act', 'arguments': args})\n"
        "emit(type='message_end', message={'role': 'assistant', 'usage': {'totalTokens': 123, 'cost': {'total': 0.001}}})\nemit(type='turn_end', message={'role': 'assistant', 'usage': {'totalTokens': 123, 'cost': {'total': 0.001}}})\nemit(type='agent_end')\n")
    (bindir / 'omp').chmod(0o755)
    os.environ['PATH'] = str(bindir) + os.pathsep + os.environ['PATH']
    saved_hsap, pilot.HSAP = pilot.HSAP, fake_hsap
    try:
        def ns(tag, **k):
            d = dict(segment=str(seg_path), decider=None, driver='mcp', fallbacks='scripted', recording=None, openrouter_model=None, chat_base=None, chat_model=None,
                     chat_mode=None, mcp_dir=None, mcp_wait_s=60.0, mcp_agent=None, mcp_agent_model=None, replay=None, planner=False, copy=str(tmp / 'copy'), tag=tag,
                     attach=None, save=None, wall=60, max_decisions=None, follow=[], end_hold=0.0, shots=0, api_base=None, allowance_usd=None,
                     allowance_since='2026-01-01', matches=None, humanize=None, humanize_seed=None, recover=False, bad_points=str(tmp / 'bad'),
                     no_bad_points=True, vision=None)
            d.update(k)
            return argparse.Namespace(**d)
        out = io.StringIO()
        saved_out, sys.stdout = sys.stdout, out
        try:
            code = pilot.cmd_run(ns('agent-loop-run', mcp_agent='loop'))
        finally:
            sys.stdout = saved_out
        s = json.loads((pilot.HERE / 'runs' / 'agent-loop-run' / 'summary.json').read_text())
        agent = s['drivers']['stats']['mcp']['agent']
        check(code == 0 and s['outcome'] == 'solved' and s['drivers']['decisions_by_driver'] == {'mcp': s['decisions']} and agent['kind'] == 'loop' and agent['ended'] is True and
              agent['exit'] == 0 and agent['spent_usd'] > 0 and s['ledger']['agent']['requests'] == agent['steps_used'] and s['ledger']['agent']['cost_usd'] > 0,
              f"--driver mcp --mcp-agent loop: the pilot started our agent at the first decision, it played the house, its model requests are in the run's ledger ({agent.get('steps_used')} calls, {agent.get('spent_usd')} USD)")
        check((pilot.HERE / 'runs' / 'agent-loop-run' / 'agent.json').exists() and 'mcp_server.py --session' in out.getvalue(), 'its result is kept in the run folder')
        code = pilot.cmd_run(ns('agent-omp-run', mcp_agent='omp'))
        s = json.loads((pilot.HERE / 'runs' / 'agent-omp-run' / 'summary.json').read_text())
        agent = s['drivers']['stats']['mcp']['agent']
        rd = pilot.HERE / 'runs' / 'agent-omp-run'
        argv = json.loads((rd / 'omp-agent' / 'argv.json').read_text())
        cfg = json.loads((rd / 'omp-agent' / '.omp' / 'mcp.json').read_text())
        check(code == 0 and s['outcome'] == 'solved' and s['drivers']['decisions_by_driver'] == {'mcp': s['decisions']} and agent['kind'] == 'omp' and agent['exit'] == 0 and
              agent['omp_cost_usd'] == 0.001 and agent['omp_tokens'] == 123 and agent['omp_tool_calls'] >= 8,
              f"--mcp-agent omp: omp is started with its own project config, plays through the stdio server, and its usage line is read ({agent})")
        check(argv[:1] == ['-p'] and '--no-session' in argv and argv[argv.index('--mode') + 1] == 'json' and argv[argv.index('--model') + 1] == 'anthropic/claude-haiku-4-5' and
              '--max-cost' in argv and '--profile' not in argv and cfg['mcpServers']['pilot']['type'] == 'stdio' and
              cfg['mcpServers']['pilot']['args'][-2:] == ['--session', str(pilot.HERE / 'runs' / 'agent-omp-run' / 'mcp')] and secret_free(json.dumps(argv), json.dumps(cfg)),
              'omp runs non-interactively, ephemeral, in json mode with a small model and a cost cap, no profile, no key anywhere on its command line or in its config')
        try:
            agents.launcher('claude', session_dir=tmp, run_dir=tmp, run_id='x', segment='s')
            check(False, 'an unknown agent is refused')
        except ValueError:
            check(True, 'an unknown agent is refused')
    finally:
        pilot.HSAP = saved_hsap
        os.environ.clear()
        os.environ.update(saved_env)
        fake.close()


# ---- run

def main():
    t0 = time.time()
    with tempfile.TemporaryDirectory(prefix='drivers-test-') as t:
        tmp = Path(t)
        openai_api.LEDGER = tmp / 'ledger.jsonl'
        openai_api.LEDGER_STANDIN = tmp / 'ledger-standin.jsonl'
        openai_api.CAPS = tmp / 'caps.json'
        os.environ['PILOT_LEDGER'], os.environ['PILOT_CAPS'] = str(openai_api.LEDGER), str(openai_api.CAPS)   # (a test's subprocess must not touch the real ledger)
        set_caps()
        pilot.FRAGMENTS = tmp / 'fragments.jsonl'
        pilot.PLANNER_LOG = tmp / 'planner.jsonl'
        pilot.HERE = tmp
        pilot.world_plan = lambda: None
        for k in ('OPENAI_API_KEY', 'OPENROUTER_API_KEY', 'PILOT_CHAT_API_KEY', 'PILOT_DRIVER', 'PILOT_CHAT_BASE', 'PILOT_OPENROUTER_BASE',
                  'PILOT_MCP_DIR', 'PILOT_OPENROUTER_MODEL', 'PILOT_CHAT_MODEL', 'PILOT_CHAT_MODE'):
            os.environ.pop(k, None)
        for name, fn in (('chain', lambda: chain_checks()), ('model drivers', lambda: model_checks(tmp)), ('pilot on the house', lambda: pilot_chain_checks(tmp)),
                         ('scripted', lambda: scripted_checks(tmp)), ('playback', lambda: playback_checks(tmp)),
                         ('hsap pipeline', lambda: hsap_pipeline_checks(tmp)), ('mcp protocol', lambda: mcp_protocol_checks(tmp)), ('mcp driver', lambda: mcp_session_checks(tmp)),
                         ('mcp screenshot', lambda: mcp_shot_checks(tmp)), ('mcp pilot', lambda: mcp_pilot_checks(tmp)), ('scenario', lambda: scenario_checks(tmp)), ('pilot.py run', lambda: cmd_run_checks(tmp)),
                         ('pilot.py drivers', lambda: drivers_cmd_checks(tmp)),
                         ('agent loop', lambda: agent_loop_checks(tmp)), ('agents by pilot.py', lambda: agent_cmd_run_checks(tmp))):
            n0, f0 = CHECKS[0], len(FAILS)
            try:
                fn()
            except Exception as e:   # noqa: BLE001
                import traceback
                traceback.print_exc()
                FAILS.append(f'{name}: {type(e).__name__}: {e}')
            print(f'-- {name}: {CHECKS[0] - n0} checks, {len(FAILS) - f0} failed', flush=True)
    print(f'test_drivers: {CHECKS[0]} checks, {len(FAILS)} failed, {time.time() - t0:.0f} s')
    for f in FAILS:
        print('  FAILED:', f)
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
