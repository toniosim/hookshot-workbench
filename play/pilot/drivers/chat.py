"""openrouter and chat: a model through the OpenAI-compatible chat completions API.

One implementation, two drivers. `openrouter` is OpenRouter (https://openrouter.ai/api/v1, a key, a cheap default model, costs from
the response's own `usage.cost`); `chat` is any base URL that speaks the same protocol (a local llama.cpp or Ollama server needs
no key and costs nothing; a hosted one may be given a key and a price). Both ask the same question as the Decisions driver (the same
developer text and data, built by deciders.Decisions.request_for) as a forced tool call:

    choose_step(step: one of the offered labels, plan: up to two more labels (optional), reason: short (optional))

and check the answer against the offered labels. A server that ignores the tool and answers in prose is tolerated when the answer
holds the JSON object or is exactly a label. An unusable answer gets ONE repair request (the bad answer and the allowed labels sent
back); a second one fails the decision (`bad_answer`) and the chain falls back. `mode` picks the structure: `tool` (default),
`json_schema` (response_format) or `json` (JSON asked for in the prompt only; for servers with neither).

Every request is checked against the pilot's caps before it is sent and is one ledger line afterwards (openai_api's ledger, caps
and window), so the caps file's limits (a run, a night, in all) hold for every driver together. The cost comes from, in this order:
the response's `usage.cost` (OpenRouter reports it for every response), the price table below (tokens x USD per million), the
request's own estimate (counted in full, never undercounted); a loopback endpoint costs nothing. The ledger line says which in
`cost_source`.
"""
import datetime
import json
import re
import time
from urllib.parse import urlparse

import deciders
import openai_api
import requests

from .access import CHAT_KEY, OPENROUTER_KEY, caps_availability
from .base import Availability, Decision, Driver, DriverFailure, Provenance, classify_api_error

OPENROUTER_BASE = 'https://openrouter.ai/api/v1'
# The decisions model's own (gpt-6-luna) through OpenRouter, so that a comparison with the `decisions` driver is about the route and not the model: 0.10 / 0.50 USD
# per million tokens on OpenRouter's list of 2026-11-16, tools and structured outputs supported. A weaker model is not a default (gpt-4.1-nano declared victory early
# as an agent and is not used anywhere).
OPENROUTER_MODEL = 'openai/' + openai_api.DECISION_MODEL
# USD per million tokens (input, output), from the same list (read 2026-11-16): the fallback when a response has no usage.cost.
PRICES = {
    'openai/gpt-6-luna': (0.10, 0.50),
    'anthropic/claude-haiku-5.5': (0.10, 0.50),
    'deepseek/deepseek-v4-flash': (0.09, 0.18),
}
PRICE_TABLE_SOURCE = 'tokens from the response usage x the price table of 2026-11-16 (openrouter.ai/api/v1/models)'
UNKNOWN_PRICE = (1.0, 3.0)   # USD per million, for the request's estimate only: a model nobody priced is counted as dear
MAX_COST = 0.01              # USD: a decision dearer than this stops the driver for the rest of the run
TOOL = 'choose_step'
FORMAT_NOTE = (
    f'Answer by calling the function {TOOL}. `step` must be exactly one of the offered step labels. Optionally `plan`: up to two '
    'more labels you would take after it if it ends well (each is used only while it is still offered). Optionally a short '
    '`reason`. Never answer in prose.')


# ---- the question and its answer

def _builder():
    return deciders.Decisions(None, model='prompt-only')


def prompt_parts(ctx):
    """(developer text, user text, data, question, [(label, what it does)]) of this decision point: the Decisions request's own
    parts, so every model is asked the same thing."""
    body = _builder().request_for(ctx)
    dev = body['input'][0]['content']
    user = body['input'][1]['content']
    q = body['questions'][0]
    return dev, user[0]['text'], user[1]['data'], q['instructions'], [(c['value'], c['description']) for c in q['choices']]


def answer_schema(labels, strict=False):
    props = {'step': {'type': 'string', 'enum': list(labels)},
             'plan': {'type': 'array', 'items': {'type': 'string', 'enum': list(labels)}, 'maxItems': 2},
             'reason': {'type': 'string'}}
    return {'type': 'object', 'additionalProperties': False, 'required': list(props) if strict else ['step'], 'properties': props}


def build_messages(ctx, mode='tool'):
    dev, text, data, question, offered = prompt_parts(ctx)
    system = dev + '\n\n' + FORMAT_NOTE
    if mode == 'json':
        system += (' Reply with one JSON object only: {"step": <label>, "plan": [<label>, ...], "reason": <text>}.')
    steps = '\n'.join(f'- {label}: {what}' for label, what in offered)
    user = f'{text}\n{json.dumps(data, separators=(",", ":"))}\n\nSteps you may choose from (label: what it does):\n{steps}\n\n{question}'
    return [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}], [label for label, _ in offered]


def build_request(model, messages, labels, mode='tool', max_tokens=600, temperature=None, extra=None, tool_choice='required'):
    body = {'model': model, 'messages': messages, 'max_tokens': max_tokens, **(extra or {})}
    if temperature is not None:   # (not sent by default: a reasoning model does not take it, and with require_parameters the request is then a 404)
        body['temperature'] = temperature
    if mode == 'tool':
        body['tools'] = [{'type': 'function', 'function': {
            'name': TOOL, 'description': 'Choose the pilot\'s next step.', 'parameters': answer_schema(labels)}}]
        body['tool_choice'] = tool_choice   # `required`: the one tool is the only possible call. An endpoint that takes no forced tool_choice (Claude through OpenRouter: 404 "no endpoints support the provided tool_choice value") is asked again once with `auto` (ChatDriver.decide)
    elif mode == 'json_schema':
        body['response_format'] = {'type': 'json_schema', 'json_schema': {
            'name': 'step', 'strict': True, 'schema': answer_schema(labels, strict=True)}}
    elif mode != 'json':
        raise ValueError(f'mode is tool, json_schema or json, not {mode!r}')
    return body


class BadAnswer(Exception):
    pass


def _json_object(text):
    """The first JSON object in a text (a model may fence it or wrap it in a sentence), or None."""
    text = re.sub(r'^```[a-zA-Z]*\s*|\s*```$', '', (text or '').strip())
    dec = json.JSONDecoder()
    for m in re.finditer(r'\{', text):
        try:
            obj, _ = dec.raw_decode(text[m.start():])
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def parse_answer(message, labels):
    """(step, plan, reason, how) of a reply message, checked against the offered labels. Raises BadAnswer with what was wrong."""
    args, how = None, None
    for call in message.get('tool_calls') or []:
        fn = call.get('function') or {}
        raw = fn.get('arguments')
        args = raw if isinstance(raw, dict) else _json_object(raw) if isinstance(raw, str) else None
        if args is not None:
            how = 'tool call'
            break
    content = message.get('content')
    if isinstance(content, list):   # (parts, as some servers send them)
        content = ''.join(p.get('text', '') for p in content if isinstance(p, dict))
    if args is None:
        args = _json_object(content)
        how = 'JSON in the content'
    if args is None:
        bare = (content or '').strip().strip('`"\' .')
        if bare in labels:
            return bare, [], None, 'a bare label'
        raise BadAnswer('no tool call and no JSON object in the reply' if content or message.get('tool_calls') else 'an empty reply')
    step = next((args[k] for k in ('step', 'label', 'choice', 'next_step') if isinstance(args.get(k), str)), None)
    if step is None:
        raise BadAnswer(f'the answer has no `step` ({json.dumps(args)[:120]})')
    if step not in labels:
        raise BadAnswer(f'step {step!r} is not one of the offered labels')
    plan = [p for p in (args.get('plan') or []) if isinstance(p, str) and p in labels and p != step][:2] \
        if isinstance(args.get('plan'), list) else []
    reason = args.get('reason') if isinstance(args.get('reason'), str) else None
    return step, plan, reason, how


def _bad_text(message):
    calls = message.get('tool_calls') or []
    if calls:
        return json.dumps([(c.get('function') or {}) for c in calls])[:500]
    c = message.get('content')
    return (c if isinstance(c, str) else json.dumps(c))[:500] if c else ''


# ---- the requests: caps, key, ledger

def is_loopback(base):
    host = urlparse(base).hostname or ''
    return host in ('localhost', '::1') or host.startswith('127.')


class ChatClient:
    """One run's requests to a chat completions endpoint. label: `openrouter` or `chat` (the ledger's `base`). key_source: where a
    key may come from; send_key says whether one is sent to this base (OpenRouter's key goes to https://openrouter.ai only: any
    other base, a stand-in, gets the word `standin`)."""

    def __init__(self, run_id, segment, base, label, key_source, *, key_required=True, send_key=True, price=None, http=None,
                 local_free=False):
        self.run_id, self.segment, self.label = run_id, segment, label
        self.local_free = local_free            # a loopback endpoint costs nothing (the generic chat driver; never OpenRouter's)
        self.base = base.rstrip('/')
        self.key_source, self.key_required, self.send_key = key_source, key_required, send_key
        self.price = price                      # (input, output) USD per million, when the caller knows it
        self.caps = openai_api.Client(run_id, segment, self.base)   # (only for check_caps)
        self.http = http or requests.Session()
        self.requests = 0

    def local(self):
        return self.local_free and is_loopback(self.base)

    def prices(self, model):
        return self.price or PRICES.get(model)

    def estimate(self, body, model):
        if self.local():
            return 0.0
        p = self.prices(model) or UNKNOWN_PRICE
        return len(json.dumps(body)) / 3.0 * p[0] / 1e6 + int(body.get('max_tokens') or 0) * p[1] / 1e6

    def cost(self, status, model, usage, estimate):
        """(USD, where it came from)."""
        if status != 200:
            return 0.0, f'no tokens billed (HTTP {status})'
        if self.local():
            return 0.0, 'local endpoint'
        if isinstance(usage, dict) and isinstance(usage.get('cost'), (int, float)):
            return float(usage['cost']), f'{self.label} usage.cost (the response)'
        p = self.prices(model)
        if p and isinstance(usage, dict) and usage.get('prompt_tokens') is not None:
            return ((int(usage.get('prompt_tokens') or 0) * p[0] + int(usage.get('completion_tokens') or 0) * p[1]) / 1e6,
                    PRICE_TABLE_SOURCE)
        return estimate, 'estimate (no usage.cost in the response and no price for the model: the request estimate is counted)'

    def post(self, body, *, model, kind='decision', timeout=30.0):
        """POST /chat/completions; returns (answer JSON, latency ms, ledger row). Raises openai_api.NoKey, CapReached, ApiError
        (typed: .status, .timeout)."""
        est = self.estimate(body, model)
        self.caps.check_caps(kind, est)
        key = None
        if self.send_key:
            try:
                key = self.key_source.get()
            except openai_api.NoKey:
                if self.key_required:
                    raise
        headers = {'Content-Type': 'application/json', 'X-Title': 'ls-pilot'}
        if key:
            headers['Authorization'] = 'Bearer ' + key
        elif self.key_required:
            headers['Authorization'] = 'Bearer standin'   # (a stand-in or a proxy that wants a word: never the real key)
        t0 = time.perf_counter()
        try:
            r = self.http.post(self.base + '/chat/completions', json=body, timeout=timeout, headers=headers)
            ms = (time.perf_counter() - t0) * 1000
            text = r.text
        except requests.RequestException as e:
            msg = f'{type(e).__name__}: {e}'
            if key:
                msg = msg.replace(key, '<key>')
            err = openai_api.ApiError(msg)
            err.timeout = isinstance(e, requests.Timeout)
            raise err from None
        finally:
            del key
        self.requests += 1
        try:
            answer = json.loads(text)
        except ValueError:
            answer = None
        usage = answer.get('usage') if isinstance(answer, dict) else None
        if isinstance(answer, dict) and answer.get('error') and not answer.get('choices'):   # (a 200 that says an upstream failed: no tokens)
            usd, source = 0.0, 'no tokens billed (an error object in the reply)'
        else:
            usd, source = self.cost(r.status_code, model, usage, est)
        row = {'ts': time.time(), 'when': datetime.datetime.now().isoformat(timespec='seconds'), 'run': self.run_id,
               'segment': self.segment, 'kind': kind, 'api': 'chat', 'model': model, 'base': self.label,
               'status': r.status_code, 'latency_ms': round(ms, 1), 'usage': usage, 'cost_usd': usd, 'cost_source': source}
        openai_api._append(row, openai_api.LEDGER)
        if r.status_code != 200 or not isinstance(answer, dict):
            err = openai_api.ApiError(f'HTTP {r.status_code}: {text[:400]}')
            err.status = r.status_code
            raise err
        return answer, ms, row


def _error_body(answer):
    """OpenRouter sometimes answers 200 with {"error": {code, message}} (an upstream provider failed): (kind, reason) or None."""
    err = answer.get('error') if isinstance(answer, dict) else None
    if not err or answer.get('choices'):
        return None
    code = err.get('code') if isinstance(err, dict) else None
    msg = (err.get('message') if isinstance(err, dict) else str(err)) or 'an error object'
    status = int(code) if isinstance(code, (int, str)) and str(code).isdigit() else None
    e = openai_api.ApiError(f'error object {code}: {msg}'[:400])
    e.status = status
    e.timeout = status == 408
    return classify_api_error(e)


# ---- the drivers

class ChatDriver(Driver):
    kind = 'model'
    paid = True
    min_gap_s = deciders.DUEL_MIN_GAP_S

    def __init__(self, name, client, model, *, mode='tool', max_tokens=600, timeout=30.0, max_cost=MAX_COST, temperature=None,
                 repair=True, key_ready=None, not_ready='', extra=None):
        self.name, self.client, self.model = name, client, model
        self.extra = dict(extra or {})          # fields added to every request body (OpenRouter's provider routing)
        self.mode, self.max_tokens, self.timeout, self.max_cost = mode, max_tokens, timeout, max_cost
        self.temperature, self.repair = temperature, repair
        self.key_ready, self.not_ready = key_ready, not_ready   # callables/text for the availability check
        self.stop_reason = None
        self.repairs = 0
        self.tool_choice = 'required'

    def describe(self):
        d = super().describe()
        d.update(base=self.client.base, mode=self.mode, local=self.client.local())
        return d

    def available(self):
        if self.not_ready:
            return Availability.no(self.not_ready)
        if self.key_ready is not None:
            ok, why = self.key_ready()
            if not ok:
                return Availability.no(why)
        if self.client.local():
            return Availability.yes('local endpoint')
        return caps_availability(self.client.run_id)

    def stats(self):
        return {'repairs': self.repairs, 'requests': self.client.requests}

    def _ask(self, body):
        """One request: (message, usage, usd, source, ms, raw answer). Failures raise DriverFailure."""
        try:
            ans, ms, row = self.client.post(body, model=self.model, timeout=self.timeout)
        except openai_api.NoKey as e:
            raise DriverFailure('unavailable', str(e)) from None
        except openai_api.CapReached as e:
            raise DriverFailure('over_budget', str(e)) from None
        except openai_api.ApiError as e:
            kind, reason = classify_api_error(e)
            raise DriverFailure(kind, reason, info={'request': body}, requests=1, latency_ms=None) from None
        problem = _error_body(ans)
        if problem:
            raise DriverFailure(problem[0], problem[1], info={'request': body}, requests=1, cost_usd=row['cost_usd'])
        choices = ans.get('choices')
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict) or \
                not isinstance(choices[0].get('message'), dict):
            raise DriverFailure('bad_answer', 'the reply has no choices[0].message', info={'request': body}, requests=1,
                                cost_usd=row['cost_usd'], latency_ms=round(ms, 1))
        return choices[0]['message'], ans.get('usage'), row['cost_usd'], row['cost_source'], ms, ans

    def decide(self, ctx):
        labels = [c.label for c in ctx.candidates]
        if len(labels) < 2:   # nothing to choose between: no request, no cost
            return Decision(labels[0], provenance=Provenance(self.name, model=self.model, requests=0),
                            info={'no_request': 'one candidate'})
        messages, offered = build_messages(ctx, self.mode)
        body = build_request(self.model, messages, offered, self.mode, self.max_tokens, self.temperature, self.extra, self.tool_choice)
        spent, ms_total, requests, sources = 0.0, 0.0, 0, []
        info = {'request': body}
        usage = None
        attempt, downgraded = 0, False
        while True:
            attempt += 1
            try:
                msg, usage, usd, source, ms, raw = self._ask(body)
            except DriverFailure as f:
                if f.kind == 'refused' and 'tool_choice' in f.reason and self.tool_choice != 'auto' and not downgraded and self.mode == 'tool':
                    downgraded, self.tool_choice = True, 'auto'   # (the failed request billed nothing)
                    body = dict(body, tool_choice='auto')
                    info['tool_choice'] = 'auto: the endpoint takes no forced tool_choice'
                    attempt -= 1
                    continue
                f.cost_usd = round((f.cost_usd or 0.0) + spent, 8) or None   # (what the first request of a repair pair cost counts)
                f.requests += requests
                f.info.setdefault('request', body)
                raise
            spent += usd or 0.0
            ms_total += ms
            requests += 1
            sources.append(source)
            try:
                step, plan, reason, how = parse_answer(msg, offered)
                break
            except BadAnswer as e:
                why = str(e)
                info.setdefault('bad_answers', []).append({'why': why, 'answer': _bad_text(msg)})
                if attempt == 2 or not self.repair:
                    raise DriverFailure(
                        'bad_answer', why + ('; the repair request failed too' if attempt == 2 else ''), info=info,
                        cost_usd=spent, requests=requests, latency_ms=round(ms_total, 1)) from None
                self.repairs += 1
                repair = (f'That answer was not usable: {why}. Answer again by calling {TOOL} with `step` set to exactly one of: '
                          + ', '.join(offered) + '.')
                body = build_request(self.model, messages + [{'role': 'assistant', 'content': _bad_text(msg) or '(empty)'},
                                                             {'role': 'user', 'content': repair}],
                                     offered, self.mode, self.max_tokens, self.temperature, self.extra, self.tool_choice)
                info['repair_request'] = body
        info.update(answer={'step': step, 'plan': plan, 'reason': reason, 'how': how}, repaired=requests > 1 or None)
        info = {k: v for k, v in info.items() if v is not None}
        if spent > self.max_cost:
            self.stop_reason = f'a decision cost {spent:.5f} USD, more than {self.max_cost} (the limit for one decision)'
        prov = Provenance(self.name, model=self.model, cost_usd=round(spent, 8), latency_ms=round(ms_total, 1), usage=usage,
                          requests=requests, cost_source='; '.join(dict.fromkeys(s for s in sources if s)) or None)
        return Decision(step, plan=tuple(plan), provenance=prov, info=info)


def make_openrouter(run_id, segment, *, base=None, model=None, **kw):
    base = base or OPENROUTER_BASE
    real = base.rstrip('/').startswith('https://openrouter.ai/')
    client = ChatClient(run_id, segment, base, 'openrouter', OPENROUTER_KEY, key_required=True, send_key=real,
                        price=kw.pop('price', None))
    ready = None
    if real:
        def ready():
            state = OPENROUTER_KEY.state()
            return (state in ('file', 'env'), f'OpenRouter: {state}')
    # require_parameters: only providers that support every parameter of the request (tool_choice above all) may serve it
    return ChatDriver('openrouter', client, model or OPENROUTER_MODEL, key_ready=ready, extra={'provider': {'require_parameters': True}}, **kw)


def make_chat(run_id, segment, *, base=None, model=None, **kw):
    """The generic endpoint: `base` None means not configured (the driver is unavailable and says what to set)."""
    if not base:
        client = ChatClient(run_id, segment, 'http://not-configured.invalid/v1', 'chat', CHAT_KEY, key_required=False)
        return ChatDriver('chat', client, model or 'local', not_ready='not configured: set PILOT_CHAT_BASE (or --chat-base) to an '
                          'OpenAI-compatible base URL, e.g. http://127.0.0.1:8080/v1', **kw)
    client = ChatClient(run_id, segment, base, 'chat', CHAT_KEY, key_required=False, price=kw.pop('price', None), local_free=True)
    return ChatDriver('chat', client, model or 'local', **kw)
