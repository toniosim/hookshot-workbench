"""decisions: today's OpenAI Decisions API path (deciders.Decisions through openai_api.Client), unchanged in what it asks and
what it answers. This module only sorts how it can fail, so that the chain knows what to do:

  no key                              -> unavailable (before any request)
  a cap reached, no caps file         -> over_budget (before any request)
  a request that timed out            -> timeout
  HTTP 4xx (429 included)             -> refused
  HTTP 5xx, a dropped connection      -> error
  an answer that is no offered step   -> bad_answer
  a decision dearer than max_cost     -> its answer stands; the driver then says it must not be asked again (over_budget)

The legacy `--decider openai-decisions` still builds deciders.Decisions directly and behaves exactly as before.
"""
import deciders
import openai_api

from .access import caps_availability
from .base import Availability, Decision, Driver, DriverFailure, Provenance, classify_api_error


class DecisionsDriver(Driver):
    name = 'decisions'
    kind = 'model'
    paid = True
    min_gap_s = deciders.DUEL_MIN_GAP_S

    def __init__(self, client, model=None, max_cost=None):
        self.client, self._model, self._max_cost = client, model, max_cost
        self.inner = None

    # the model name without needing the caps file (describe() is called before anything is asked)
    @property
    def model(self):
        if self.inner is not None:
            return self.inner.model
        return self._model or openai_api.DECISION_MODEL

    @property
    def stop_reason(self):
        return self.inner.stop_reason if self.inner is not None else None

    def describe(self):
        d = super().describe()
        d['base'] = 'openai' if self.client.real else 'stand-in'
        return d

    def available(self):
        if self.client.real:
            state = openai_api.key_state()
            if state not in ('file', 'env'):
                return Availability.no(f'OpenAI Decisions: {state}')
        return caps_availability(self.client.run_id)

    def _inner(self):
        if self.inner is None:
            kw = {} if self._max_cost is None else {'max_cost': self._max_cost}
            self.inner = deciders.Decisions(self.client, self._model, **kw)
        return self.inner

    def decide(self, ctx):
        try:
            inner = self._inner()
        except openai_api.CapReached as e:   # (no caps file: a fresh tree)
            raise DriverFailure('over_budget', str(e)) from None
        inner.last_error = None
        c = inner.choose(ctx)
        info = c.info
        if 'throttled' in info:
            raise DriverFailure('throttled', info['throttled'])
        if 'fallback' in info:
            raise self._failure(inner, info)
        asked = 'latency_ms' in info
        prov = Provenance(self.name, model=inner.model, cost_usd=info.get('cost_usd'), latency_ms=info.get('latency_ms'),
                          usage=info.get('usage'), requests=1 if asked else 0,
                          cost_source=openai_api.PRICE_SOURCE if asked and info.get('cost_usd') is not None else None)
        return Decision(c.label, predicates=c.predicates, provenance=prov, info=info)

    @staticmethod
    def _failure(inner, info):
        text = info['fallback']
        keep = {'info': {'request': info['request']} if 'request' in info else None,
                'cost_usd': info.get('cost_usd'), 'latency_ms': info.get('latency_ms'),
                'requests': 1 if 'latency_ms' in info else 0}
        e = inner.last_error
        if isinstance(e, openai_api.NoKey):
            return DriverFailure('unavailable', str(e), **keep)
        if isinstance(e, openai_api.CapReached):
            return DriverFailure('over_budget', str(e), **keep)
        if isinstance(e, openai_api.ApiError):
            kind, reason = classify_api_error(e)
            return DriverFailure(kind, reason, **keep)
        if text.startswith('stopped:'):   # no request after the model was stopped: its own reason says cap, cost or refusals
            why = text[len('stopped:'):].strip()
            return DriverFailure('refused' if 'refused' in why else 'over_budget', why, **keep)
        return DriverFailure('bad_answer', text, **keep)
