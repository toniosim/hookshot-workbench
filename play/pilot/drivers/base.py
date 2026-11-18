"""The driver interface of the playthrough pilot: who chooses the next step.

A driver is given one decision point, the observation (`deciders.Context`: the state line, the goal and target, what was tried)
and the allowed actions (`ctx.candidates`: labelled steps, each with its text), and returns one `Decision`: the label of the
step to take, optionally a short plan (labels to take after it while they are still offered), and its provenance (driver name,
model, cost, latency). Before it is asked, a driver says whether it can be (`available()`: no key, no endpoint, a cap reached);
when it is asked and cannot answer it raises `DriverFailure` with one of the failure kinds below. The chain (chain.py) turns every
failure into a logged fallback to the next driver.

    decisions    OpenAI's Decisions API (today's decider, unchanged)
    openrouter   OpenRouter's chat completions, a tool call checked against the allowed labels
    chat         any OpenAI-compatible chat endpoint (a local llama.cpp or Ollama server needs no key); the same code as openrouter
    mcp          an outside agent through MCP tools (mcp_queue.py and ../mcp_server.py)
    playback     an ls-input-recording/1 file replayed, with divergence checks at the recording's marks
    scripted     the rules policy and fixed input scripts: no model, the same inputs give the same steps

Standard library only (the chat drivers use requests, as openai_api.py does).
"""
import time
from dataclasses import dataclass, field

# What a driver can fail at, and what the chain does about it:
FAILURE_KINDS = (
    'unavailable',   # no key, no endpoint, not configured: the driver cannot be asked at all           (sticky: not asked again in the run)
    'over_budget',   # a cap is reached, a decision cost more than it may, the account has no credit     (sticky)
    'diverged',      # playback: the game is not where the recording was                                  (sticky)
    'exhausted',     # playback or a script ran out of steps, or the outside agent never answers          (sticky)
    'timeout',       # no answer in time
    'refused',       # the service said no (HTTP 4xx, 429 rate limit, an agent's refusal)
    'bad_answer',    # an answer that is not one of the allowed actions (after the one repair retry)
    'error',         # anything else that went wrong in the request (a 5xx, a dropped connection)
    'throttled',     # the driver declined to ask now (a duel's pace): this decision only, never counts against it
)
STICKY = frozenset(('unavailable', 'over_budget', 'diverged', 'exhausted'))
NOT_COUNTED = frozenset(('throttled',))


@dataclass
class Availability:
    """Whether a driver can be asked now. kind says why not: `unavailable` or `over_budget`."""
    ok: bool
    reason: str = ''
    kind: str = 'unavailable'

    @staticmethod
    def yes(note=''):
        return Availability(True, note)

    @staticmethod
    def no(reason, kind='unavailable'):
        return Availability(False, reason, kind)


@dataclass
class Provenance:
    """Who made a decision and at what price: written into the decision's transcript row and the run's summary."""
    driver: str
    model: str = None
    cost_usd: float = None      # None: not a paid driver (or a price nobody knows)
    latency_ms: float = None
    usage: dict = None
    requests: int = 0           # how many requests it took (a repair retry makes two)
    cost_source: str = None     # where the cost came from: the response's own figure, a price table, an estimate
    note: str = None

    def as_dict(self):
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class Decision:
    label: str
    plan: tuple = ()            # labels to take after `label`, each only while it is still offered
    predicates: dict = field(default_factory=dict)
    provenance: Provenance = None
    info: dict = field(default_factory=dict)   # what goes into the transcript with it: request, answer, confidence ...
    candidate: tuple = None     # (label, lines, text): a step this driver brings itself (a script, a recorded chunk, an agent's own steps)


class DriverFailure(Exception):
    """A driver asked and could not answer. kind is one of FAILURE_KINDS; cost_usd and requests say what the failed attempt
    cost anyway (it is in the ledger either way); info goes into the fallback event (the request that failed, for one)."""

    def __init__(self, kind, reason, *, info=None, cost_usd=None, requests=0, latency_ms=None):
        assert kind in FAILURE_KINDS, kind
        super().__init__(f'{kind}: {reason}')
        self.kind, self.reason, self.info = kind, str(reason), dict(info or {})
        self.cost_usd, self.requests, self.latency_ms = cost_usd, requests, latency_ms


class Driver:
    """The interface. Subclasses set `name` and implement decide(); `available()` and `close()` have working defaults."""
    name = 'driver'
    model = None
    kind = 'rules'              # rules (no model), model (a paid or local model), agent (an outside agent), recording
    paid = False
    min_gap_s = 0.0             # a duel goal: asked at most once in this much game time (the pilot waits out the rest)

    def describe(self):
        """What the summary says about this driver (no keys, no secrets)."""
        return {'name': self.name, 'kind': self.kind, 'model': self.model, 'paid': self.paid}

    def available(self):
        return Availability.yes()

    def decide(self, ctx):
        raise NotImplementedError

    def close(self):
        pass

    def stats(self):
        """Extra numbers for the run's summary (a playback's marks, a script's steps)."""
        return {}


def timed(fn, *a, **k):
    """(result, milliseconds)."""
    t0 = time.perf_counter()
    out = fn(*a, **k)
    return out, round((time.perf_counter() - t0) * 1000, 1)


def classify_api_error(e):
    """The failure kind of an openai_api.ApiError (typed by status and timeout) or of a requests exception: (kind, reason)."""
    reason = str(e)
    if getattr(e, 'timeout', False):
        return 'timeout', reason
    status = getattr(e, 'status', None)
    if status is None:
        return 'error', reason
    if status == 402:
        return 'over_budget', reason          # OpenRouter: not enough credit
    if status == 429 or 400 <= status < 500:
        return 'refused', reason
    return 'error', reason
