"""The chain: drivers in the order a scenario accepts them, each falling back to the next.

`Chain` has the interface of a decider (`name`, `choose(ctx) -> deciders.Choice`, `stop_reason`, `min_gap_s`), so the pilot's run
loop, its guard, its recorder and its transcript are the same whichever driver decides. Beyond that it makes the layer's
promises:

  * Every fallback is an event (`kind: driver-fallback`: the driver, the failure kind, the reason, the next driver, what the
    failed attempt cost). The pilot drains `drain_events()` after each decision and writes them to the transcript with the
    decision's number.
  * Every decision says which driver made it (`Choice.driver`; the decision row's `decider`, and `driver` with the provenance);
    one that came after a fallback also lists what failed first (`fallbacks`, `fallback`).
  * A driver that fails in a way that will not mend (no key, a cap, a recording that diverged) is benched for the rest of the run;
    one that fails otherwise is benched after `bench_after` failures in a row, so that a dead endpoint costs two timeouts, not one
    per decision. A driver that answers resets its count. A throttled answer (a duel's pace) counts for nothing.
  * When no driver is left the chain sets `stop_reason` and the pilot ends the run with it (as it did for a stopped model).
"""
from collections import Counter, defaultdict

import deciders

from .base import NOT_COUNTED, STICKY, Decision, DriverFailure, Provenance


class Chain:
    def __init__(self, drivers, want=None, bench_after=2, notes=()):
        assert drivers, 'a chain needs a driver'
        self.drivers = list(drivers)
        self.by_name = {d.name: d for d in self.drivers}
        assert len(self.by_name) == len(self.drivers), 'a driver twice in a chain'
        self.want = want or self.drivers[0].name
        self.name = self.drivers[0].name          # what the summary's `decider` says: the driver the scenario wanted
        self.bench_after = bench_after
        self.notes = list(notes)
        self.benched, self.consecutive, self.availability = {}, Counter(), {}
        self.pending, self.fallbacks = [], []     # events not yet drained; every fallback of the run
        self.decided, self.requests, self.cost = Counter(), Counter(), defaultdict(float)
        self.stop_reason = None
        self.plan = None                          # (driver name, [labels still to take])

    # ---- the interface the pilot knows
    @property
    def min_gap_s(self):
        for d in self.drivers:
            if d.name not in self.benched:
                return d.min_gap_s
        return 0.0

    def probe(self):
        """Ask every driver whether it can be asked (no request, no cost). One that cannot is benched now and its fallback is
        written with the first decision, naming the next driver that can. Returns {driver: (ok, reason)}."""
        for d in self.drivers:
            av = d.available()
            self.availability[d.name] = {'ok': av.ok, 'reason': av.reason, 'kind': av.kind}
            if not av.ok:
                self.benched[d.name] = f'{av.kind}: {av.reason}'[:300]
        for d in self.drivers:
            av = self.availability[d.name]
            if not av['ok']:
                self._event('driver-fallback', d.name, av['kind'], av['reason'], benched=True)
        return {k: (v['ok'], v['reason']) for k, v in self.availability.items()}

    def active(self):
        return [d.name for d in self.drivers if d.name not in self.benched]

    def bench(self, name, reason, kind, event=False, **extra):
        if name in self.benched:
            return
        self.benched[name] = f'{kind}: {reason}'[:300]
        if event:
            self._event('driver-fallback', name, kind, reason, benched=True, **extra)

    def choose(self, ctx):
        tried = []
        if self.plan:
            name, rest = self.plan
            offered = {c.label for c in ctx.candidates}
            if name not in self.benched and rest and rest[0] in offered:
                label = rest.pop(0)
                self.plan = (name, rest) if rest else None
                d = self.by_name[name]
                return self._made(d, Decision(label, provenance=Provenance(
                    d.name, model=d.model, cost_usd=0.0 if d.paid else None, note='a step of its plan')), tried)
            self.plan = None
        throttled = None
        for d in self.drivers:
            if d.name in self.benched or (throttled and d.paid):   # (a duel's pace: no other model is asked in the gap either)
                continue
            try:
                dec = d.decide(ctx)
            except DriverFailure as f:
                if f.kind == 'throttled':
                    throttled = f
                else:
                    self._failed(d, f, tried)
                continue
            except Exception as e:   # noqa: BLE001  a driver's bug is a failure of that driver, never the end of a run
                self._failed(d, DriverFailure('error', f'{type(e).__name__}: {e}'), tried)
                continue
            self.consecutive[d.name] = 0
            return self._made(d, dec, tried)
        if throttled is not None:   # every driver that could answer is paced or failed: the rules choose, as Decisions always did
            c = deciders.Rules().choose(ctx)
            c.info, c.driver = {'throttled': throttled.reason}, 'rules'
            return c
        parts = [f"{t['driver']}: {t['failure']}: {t['reason']}" for t in tried]
        parts += [f'{n}: {r}' for n, r in self.benched.items() if n not in {t['driver'] for t in tried}]
        self.stop_reason = f"no driver could decide ({'; '.join(parts) or 'none was asked'})"[:400]
        first = ctx.candidates[0].label
        return deciders.Choice(first, info={'fallback': self.stop_reason}, driver=None)

    def drain_events(self):
        out, self.pending = self.pending, []
        return out

    def finish(self, outcome):
        """The run is over: a driver that keeps a session (mcp) says how it ended."""
        for d in self.drivers:
            if hasattr(d, 'finish'):
                try:
                    d.finish(outcome)
                except Exception:   # noqa: BLE001
                    pass

    def close(self):
        for d in self.drivers:
            try:
                d.close()
            except Exception:   # noqa: BLE001
                pass

    # ---- bookkeeping
    def _next_after(self, d):
        seen = False
        for x in self.drivers:
            if x is d:
                seen = True
            elif seen and x.name not in self.benched:
                return x.name
        return None

    def _event(self, kind, name, failure, reason, **extra):
        ev = {'kind': kind, 'driver': name, 'failure': failure, 'reason': str(reason)[:400],
              'to': self._next_after(self.by_name[name]), **{k: v for k, v in extra.items() if v is not None}}
        self.pending.append(ev)
        self.fallbacks.append({k: ev[k] for k in ('driver', 'failure', 'reason', 'to')})
        return ev

    def _failed(self, d, f, tried):
        if f.kind not in NOT_COUNTED:
            self.consecutive[d.name] += 1
        benched = f.kind in STICKY or self.consecutive[d.name] >= self.bench_after
        if benched:
            self.benched[d.name] = f'{f.kind}: {f.reason}'[:300]
        if f.cost_usd:
            self.cost[d.name] += f.cost_usd
        self.requests[d.name] += f.requests
        self._event('driver-fallback', d.name, f.kind, f.reason, benched=benched, cost_usd=f.cost_usd,
                    requests=f.requests or None, latency_ms=f.latency_ms, **{k: v for k, v in f.info.items() if k == 'request'})
        tried.append({'driver': d.name, 'failure': f.kind, 'reason': f.reason[:200]})

    def _made(self, d, dec, tried):
        prov = dec.provenance
        info = dict(dec.info)
        info['driver'] = prov.as_dict()
        if prov.model:
            info.setdefault('model', prov.model)
        if prov.latency_ms is not None:
            info.setdefault('latency_ms', prov.latency_ms)
        if prov.usage is not None:
            info.setdefault('usage', prov.usage)
        if prov.cost_usd is not None:
            info.setdefault('cost_usd', prov.cost_usd)
        if dec.plan:
            info['driver_plan'] = list(dec.plan)
            self.plan = (d.name, list(dec.plan))
        if tried:
            info['fallbacks'] = tried
            info['fallback'] = '; '.join(f"{t['driver']}: {t['failure']}: {t['reason']}" for t in tried)[:400]
        self.decided[d.name] += 1
        self.requests[d.name] += prov.requests
        self.cost[d.name] += prov.cost_usd or 0.0
        stop = getattr(d, 'stop_reason', None)
        if stop:   # the driver gave this answer and says it must not be asked again (a decision dearer than it may be)
            self.bench(d.name, stop, 'over_budget', event=True)
        return deciders.Choice(dec.label, dec.predicates, info, driver=d.name, candidate=dec.candidate)

    def report(self):
        return {'want': self.want, 'chain': [d.describe() for d in self.drivers], 'availability': self.availability,
                'benched': dict(self.benched), 'decisions_by_driver': dict(self.decided), 'fallbacks': list(self.fallbacks),
                'requests_by_driver': {k: v for k, v in self.requests.items() if v},
                'cost_usd_by_driver': {k: round(v, 6) for k, v in self.cost.items() if v},
                'notes': list(self.notes), 'stats': {d.name: d.stats() for d in self.drivers if d.stats()}}

