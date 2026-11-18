"""scripted: the rules policy plus fixed input scripts. No model, no network, no clock, no randomness: the same decision
points in give the same steps out, which is what a hard-coded test needs.

The policy is deciders.Rules (the control every model is compared with). A fixed input script is a named list of hsap steps
(`press A 200`, `walk 3 4`, `wait 1`, ...) that a scenario wants played verbatim, once, at a goal (or at the first decision when
it names none); it is offered to the pilot as a step of its own, `script:<name>`, and goes through the same input path, guard and
recorder as every other step. A scenario writes them in its `driver` table:

    [driver]
    want = "scripted"
    script = [{name = "open-door", goal = "door", lines = ["walk 1 2 0.5", "press A 200"]},
              {name = "warm-up", file = "warm-up.txt"}]
"""
import deciders

from .base import Decision, Driver, Provenance


class ScriptedDriver(Driver):
    name = 'scripted'
    kind = 'rules'

    def __init__(self, scripts=()):
        self.rules = deciders.Rules()
        self.scripts = [dict(s) for s in scripts]
        for s in self.scripts:
            if not s.get('name') or not s.get('lines'):
                raise ValueError(f'a script needs a name and lines: {s!r}')
        self.played = []

    def describe(self):
        d = super().describe()
        d['scripts'] = [s['name'] for s in self.scripts]
        return d

    def due(self, ctx):
        for s in self.scripts:
            if s['name'] not in self.played and (not s.get('goal') or s['goal'] == getattr(ctx.goal, 'name', None)):
                return s
        return None

    def decide(self, ctx):
        s = self.due(ctx)
        if s is not None:
            self.played.append(s['name'])
            label = f"script:{s['name']}"
            text = f"the fixed input script {s['name']} ({len(s['lines'])} steps)"
            return Decision(label, provenance=Provenance(self.name, note='fixed input script'),
                            candidate=(label, list(s['lines']), text))
        return Decision(self.rules.pick(ctx), provenance=Provenance(self.name))

    def stats(self):
        return {'scripts_played': list(self.played)} if self.scripts else {}
