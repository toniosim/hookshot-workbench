"""The pilot's way to OpenAI's API: the key, the caps, the ledger. Standard library and requests only.

The key is read at the moment of each request from the environment (OPENAI_API_KEY) or from a private file outside this
repository: PILOT_OPENAI_KEY_FILE, else $XDG_CONFIG_HOME/ls-pilot/openai.key (~/.config/ls-pilot/openai.key), mode 600,
one line. It is kept in a local variable for that request, sent only in the Authorization header to
https://api.openai.com, and scrubbed from every error text. It is never printed, logged, written to a transcript or put
on a command line. A stand-in server (standin.py, any base URL that is not api.openai.com) never gets the real key: it
gets the word "standin".

Caps (pilot/caps.json, edited only by the main session) are read before every request: per run, per night (01:00 to
08:00 local while that window runs, else the calendar day), in total, and the planner's share of a night. The ledger
(pilot/ledger.jsonl) holds one line per request with the token counts the API reported and the cost computed from them
at the published prices below (the API reports tokens, not dollars). Pictures (vision.py) go through the same Client, so
their tokens are counted in the same ledger under kind 'vision'.

Settings that may be overridden by the environment for one run (a benchmark arm): PILOT_PLANNER_MODEL, PILOT_VISION_MODEL,
PILOT_VISION_BACKEND (decisions or responses); caps.json may carry planner_model, vision_model, vision_backend.
"""
import datetime
import fcntl
import json
import os
import stat
import time
from collections import namedtuple
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent


def _key_file():
    explicit = os.environ.get('PILOT_OPENAI_KEY_FILE')
    if explicit:
        return Path(explicit)
    base = os.environ.get('XDG_CONFIG_HOME') or str(Path.home() / '.config')
    return Path(base) / 'ls-pilot' / 'openai.key'   # (read only; never inside a repository)


CAPS = Path(os.environ.get('PILOT_CAPS') or HERE / 'caps.json')   # (the environment may name other files: a test's subprocess must not touch the real ledger)
LEDGER = Path(os.environ.get('PILOT_LEDGER') or HERE / 'ledger.jsonl')
LEDGER_STANDIN = HERE / 'ledger-standin.jsonl'   # requests to a stand-in server: kept apart from the real ledger
OPENAI = 'https://api.openai.com/v1'
DECISION_MODEL = 'gpt-6-luna'      # "Send requests to POST /v1/decisions using gpt-6-luna, the only currently supported model."
PLANNER_MODEL = 'gpt-6.1-terra'    # the main session's choice for the planner (its message of 2026-11-10 20:05)
VISION_MODEL = 'gpt-6-luna'        # the picture questions: /v1/decisions takes input_image (see vision.py, `probe`)
VISION_BACKEND = 'decisions'
# USD per million tokens, from developers.openai.com/api/docs/pricing ("Standard pricing data", read 2026-11-10) and
# the Decisions guide ("uncached input costs $0.10 per 1M tokens ... Output tokens are not charged"):
# (input, cached input, 30-minute cache write, output)
Price = namedtuple('Price', 'inp cached write out')
PRICES = {
    ('decisions', 'gpt-6-luna'): Price(inp=0.10, cached=0.01, write=0.125, out=0.0),
    ('responses', 'gpt-6-astra'): Price(inp=10.00, cached=1.00, write=12.50, out=50.00),
    ('responses', 'gpt-6.1-sol'): Price(inp=2.00, cached=0.10, write=2.50, out=10.00),
    ('responses', 'gpt-6.1-terra'): Price(inp=1.00, cached=0.05, write=1.25, out=5.00),
    ('responses', 'gpt-6-sol'): Price(inp=2.00, cached=0.20, write=2.50, out=10.00),
    ('responses', 'gpt-6-luna'): Price(inp=0.10, cached=0.01, write=0.125, out=0.50),
}
PRICE_SOURCE = 'tokens from the response usage x published Standard prices of 2026-11-10'


class NoKey(Exception):
    pass


class CapReached(Exception):
    pass


class ApiError(Exception):
    """A request that failed. status: the HTTP status when a reply came; timeout: the request timed out (the driver layer
    sorts a failure by these two, drivers/base.py); the message is as it always was."""
    status = None
    timeout = False


def caps():
    try:
        c = json.loads(CAPS.read_text())
        float(c['per_run_usd']), float(c['per_night_usd']), float(c['total_usd'])
    except (OSError, ValueError, KeyError, TypeError):
        raise CapReached('no readable caps file (pilot/caps.json with per_run_usd, per_night_usd, total_usd): write one before a model is asked') from None
    env = os.environ.get
    return {'per_run_usd': float(c['per_run_usd']), 'per_night_usd': float(c['per_night_usd']),
            'total_usd': float(c['total_usd']), 'planner_share_of_night': float(c.get('planner_share_of_night', 0)),
            'model': c.get('model') or DECISION_MODEL,
            'planner_model': env('PILOT_PLANNER_MODEL') or c.get('planner_model') or PLANNER_MODEL,
            'vision_model': env('PILOT_VISION_MODEL') or c.get('vision_model') or VISION_MODEL,
            'vision_backend': env('PILOT_VISION_BACKEND') or c.get('vision_backend') or VISION_BACKEND}


def key_state():
    """'file', 'env' or 'no key' (without reading more than the file's mode)."""
    if os.environ.get('OPENAI_API_KEY'):
        return 'env'
    try:
        mode = stat.S_IMODE(_key_file().stat().st_mode)
    except OSError:
        return 'no key'
    return 'file' if mode == 0o600 else 'no key (the key file is not mode 600)'


def _key():
    k = os.environ.get('OPENAI_API_KEY')
    if k:
        return k.strip()
    path = _key_file()
    try:
        if stat.S_IMODE(path.stat().st_mode) != 0o600:
            raise NoKey('the key file is not mode 600')
        k = path.read_text().strip()
    except OSError:
        raise NoKey('no key') from None
    if not k:
        raise NoKey('the key file is empty')
    return k


def window_start(now):
    """The start of the night the caps count: 01:00 while 01:00 to 08:00 runs, else the calendar day's midnight."""
    if 1 <= now.hour < 8:
        return now.replace(hour=1, minute=0, second=0, microsecond=0)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def ledger_rows(path=None):
    path = path or LEDGER
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            pass
    return rows


def spent(run_id=None):
    """Dollars so far: in this run, in this night (or day), the planner's in this night, in total."""
    now = datetime.datetime.now()
    start = window_start(now).timestamp()
    run = night = planner = total = 0.0
    for r in ledger_rows():
        c = float(r.get('cost_usd') or 0)
        total += c
        if r.get('ts', 0) >= start:
            night += c
            if r.get('kind') == 'planner':
                planner += c
        if run_id and r.get('run') == run_id:
            run += c
    return {'run': run, 'night': night, 'planner_night': planner, 'total': total}


def cost(api, model, usage):
    p = PRICES.get((api, model))
    if not p or not usage:
        return None
    inp = int(usage.get('input_tokens') or 0)
    det = usage.get('input_tokens_details') or {}
    cached, write = int(det.get('cached_tokens') or 0), int(det.get('cache_write_tokens') or 0)
    out = int(usage.get('output_tokens') or 0)
    # "Both counts are included in usage.input_tokens; don't add them to that total." (Decisions guide)
    return ((inp - cached - write) * p[0] + cached * p[1] + write * p[2] + out * p[3]) / 1e6


class Client:
    """One run's requests. base: the API root (OpenAI, or a stand-in on loopback)."""

    def __init__(self, run_id, segment, base=None, allowance=None):
        self.run_id, self.segment = run_id, segment
        self.base = (base or OPENAI).rstrip('/')
        self.real = self.base.startswith('https://api.openai.com/')
        self.requests = 0
        self.allowance = allowance   # (since unix time, USD): a lane's own limit below the caps, e.g. one night's trials
        self.http = requests.Session()   # one connection kept open: no new TLS handshake per decision

    def check_caps(self, kind, estimate):
        c, s = caps(), spent(self.run_id)
        if s['run'] + estimate > c['per_run_usd']:
            raise CapReached(f"run cap {c['per_run_usd']:.2f} USD ({s['run']:.4f} spent)")
        if s['night'] + estimate > c['per_night_usd']:
            raise CapReached(f"night cap {c['per_night_usd']:.2f} USD ({s['night']:.4f} spent)")
        if s['total'] + estimate > c['total_usd']:
            raise CapReached(f"total cap {c['total_usd']:.2f} USD ({s['total']:.4f} spent)")
        if kind == 'planner' and s['planner_night'] + estimate > c['planner_share_of_night'] * c['per_night_usd']:
            raise CapReached(f"planner share {c['planner_share_of_night']:.2f} of the night's cap")
        if self.allowance:
            since, usd = self.allowance
            used = sum(float(r.get('cost_usd') or 0) for r in ledger_rows() if r.get('ts', 0) >= since)
            if used + estimate > usd:
                raise CapReached(f'allowance {usd:.2f} USD since {datetime.datetime.fromtimestamp(since):%F %H:%M} '
                                 f'({used:.4f} spent)')
        return c

    def post(self, path, body, *, api, model, kind, estimate, timeout=30.0):
        """POST; returns (answer JSON, latency ms, ledger row). Raises NoKey, CapReached, ApiError."""
        self.check_caps(kind, estimate)
        key = _key() if self.real else 'standin'
        t0 = time.perf_counter()
        try:
            r = self.http.post(self.base + path, json=body, timeout=timeout,
                              headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
            ms = (time.perf_counter() - t0) * 1000
            text = r.text
        except requests.RequestException as e:
            msg = f'{type(e).__name__}: {e}'.replace(key, '<key>')
            del key
            err = ApiError(msg)
            err.timeout = isinstance(e, requests.Timeout)
            raise err from None
        del key
        self.requests += 1
        try:
            answer = json.loads(text)
        except ValueError:
            answer = None
        usage = (answer or {}).get('usage') if isinstance(answer, dict) else None
        row = {'ts': time.time(), 'when': datetime.datetime.now().isoformat(timespec='seconds'), 'run': self.run_id,
               'segment': self.segment, 'kind': kind, 'api': api, 'model': model, 'base': 'openai' if self.real else
               'standin', 'status': r.status_code, 'latency_ms': round(ms, 1), 'usage': usage,
               'cost_usd': cost(api, model, usage) if r.status_code == 200 else 0.0, 'cost_source': PRICE_SOURCE}
        if not self.real:
            row['cost_usd'] = 0.0   # a stand-in costs nothing; its token counts are its own guess
        _append(row, LEDGER if self.real else LEDGER_STANDIN)
        if r.status_code != 200 or answer is None:
            err = ApiError(f'HTTP {r.status_code}: {text[:400]}')
            err.status = r.status_code
            raise err
        return answer, ms, row

    def get_json(self, path, timeout=30.0):
        """GET (no tokens, so no ledger row and no cap check, e.g. /models); returns the answer JSON. Raises NoKey, ApiError."""
        key = _key() if self.real else 'standin'
        try:
            r = self.http.get(self.base + path, timeout=timeout, headers={'Authorization': 'Bearer ' + key})
            text = r.text
        except requests.RequestException as e:
            msg = f'{type(e).__name__}: {e}'.replace(key, '<key>')
            del key
            raise ApiError(msg) from None
        del key
        try:
            answer = json.loads(text)
        except ValueError:
            answer = None
        if r.status_code != 200 or answer is None:
            raise ApiError(f'HTTP {r.status_code}: {text[:400]}')
        return answer


def _append(row, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(row) + '\n')
        f.flush()
        fcntl.flock(f, fcntl.LOCK_UN)


def summary(run_id=None, since=None, standin=False):
    """Requests, tokens, dollars and latency (median, 95th percentile) of the ledger's rows (one run, or since a time)."""
    rows = [r for r in ledger_rows(LEDGER_STANDIN if standin else LEDGER) if (run_id is None or r.get('run') == run_id) and (since is None or r['ts'] >= since)]
    out = {}
    for kind in sorted({r['kind'] for r in rows}):
        rs = [r for r in rows if r['kind'] == kind]
        lat = sorted(r['latency_ms'] for r in rs)
        inp = sum(int((r.get('usage') or {}).get('input_tokens') or 0) for r in rs)
        cached = sum(int(((r.get('usage') or {}).get('input_tokens_details') or {}).get('cached_tokens') or 0) for r in rs)
        outp = sum(int((r.get('usage') or {}).get('output_tokens') or 0) for r in rs)
        out[kind] = {'requests': len(rs), 'errors': sum(r['status'] != 200 for r in rs), 'input_tokens': inp,
                     'cached_tokens': cached, 'output_tokens': outp,
                     'cost_usd': round(sum(float(r.get('cost_usd') or 0) for r in rs), 6),
                     'latency_ms_median': percentile(lat, 50), 'latency_ms_p95': percentile(lat, 95),
                     'base': sorted({r.get('base') for r in rs})}
    return out


def percentile(xs, q):
    if not xs:
        return None
    k = (len(xs) - 1) * q / 100
    i = int(k)
    j = min(i + 1, len(xs) - 1)
    return round(xs[i] + (xs[j] - xs[i]) * (k - i), 1)
