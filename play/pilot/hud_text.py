#!/usr/bin/env python3
"""hud_text: what the pilot says on the game's own screen, as plain text lines.

The pilot (pilot.py) keeps a Hud and tells it each decision and each step result; the Hud writes the panel text to
<live>/hud.txt (a temporary file renamed over it, so a reader never sees half a text) whenever the text changed. hsap.py polls
that file and sends it to the game with the control bridge's `overlay` command (see hsap.py: throttle, keep-alive, clear at
the end). Nothing here talks to the game and nothing here can end a run: a Hud that fails once says so once (on_error) and
stays quiet.

The panel is at most 14 lines of at most 56 printable ASCII characters (`->` and `...`, no unicode), well inside the game's
caps (16 lines, 2048 bytes). Rows, one a line, in this order (wording and layout from pilot/overlay.py and live_panel.py, which
draw the same facts after the fact and in a terminal):

  GOAL <goal> [open|met|failed] FOR <target>
  decision <n>/<N>  t <game seconds> s
  RUN <outcome>                        only once the run has ended (the word before the first colon)
  CANDIDATES (<decider>[, choosing])
  > <label>  82%                       the chosen one marked with `>` and the model's probability when it gave one,
    <label>  9%                        the others indented two spaces; at most five (the likeliest, the chosen one kept)
    +<k> more
  STEP choosing the next step | <label> running | <label> -> <result word>
  LAST <label> -> <result>             the step before
  MODEL <name> <latency> s sure <p>%   | <name> (asking) | rules, no model asked | recovery ladder | no question: <why>
  COST $<x> so far, <k> model calls    | none yet: no model call
  STATE moving freely | same answer <n> times running      or  STUCK <s> s, rung <n>   or  RECOVERY rung <name>
  VISION <age> s ago: <few words>      only when the run has eyes (--vision on)

When the rows do not fit 14 lines the candidates give way first. Never in a row: a path, a key, a request body, a position, a
flag, a save. Every word that came from outside is cleaned (non-ASCII to `?`, controls out, a word that looks like a path or a
key replaced by `...`) and each row is cut to 56 characters with `...`.
"""
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

WIDTH = 56       # characters a line
MAX_LINES = 14   # lines a panel (the game takes 16)
MAX_SHOWN = 5    # candidates shown
_KEY = re.compile(r'sk-[A-Za-z0-9_\-]{6,}')


def number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def clean(text):
    """One line of printable ASCII: non-ASCII becomes `?`, controls and runs of blanks one space, and a word that looks like a
    path (starts with / or ~, holds a backslash, `://` or two slashes) or a key (sk-...) is replaced by `...`."""
    s = '' if text is None else str(text)
    s = ''.join(c if 32 <= ord(c) < 127 else (' ' if ord(c) < 32 or ord(c) == 127 else '?') for c in s)
    words = []
    for w in s.split():
        core = w.lstrip('"\'([{<=,;:')
        if core.startswith(('/', '~')) or '://' in w or '\\' in w or w.count('/') >= 2 or _KEY.search(w):
            w = '...'
        words.append(w)
    return ' '.join(words)


def fit(text, width=WIDTH):
    text = str(text)
    return text if len(text) <= width else text[:max(0, width - 3)].rstrip() + '...'


def pct(p):
    return '%d%%' % round(100 * p)


def row(label, text, tail=''):
    """`LABEL text tail` in WIDTH characters: the text gives way, the label and the tail stay."""
    head = label + ' '
    return (head + fit(text, max(4, WIDTH - len(head) - len(tail))) + tail).rstrip()


# ---------------------------------------------------------------------------------------------------------- the panel

@dataclass
class Panel:
    goal: str = ''
    status: str = 'open'
    target: str = ''
    n: object = None
    total: object = None
    t: object = None
    phase: str = 'deciding'      # deciding (the candidates are offered), running (the step is done), done (its result is known)
    decider: str = ''
    cands: list = field(default_factory=list)    # [(label, probability or None)]
    chosen: str = ''
    result: object = None
    last: object = None          # (label, result) of the step before
    model: object = None
    latency_ms: object = None
    confidence: object = None
    no_request: object = None
    fallback: bool = False
    rung: object = None
    recover: dict = field(default_factory=dict)
    cost: float = 0.0
    calls: int = 0
    eyes: bool = False
    vision: object = None        # (wall time, words) of the latest look
    outcome: object = None


def vision_words(row_):
    """A look in a few words: what stands ahead, a screen that is not play, what it is sure of (0.5 and over, three at most), the
    oddities it flagged; a look that asked about being stuck says how stuck it thinks Link is."""
    ans = row_.get('answers') if isinstance(row_.get('answers'), dict) else {}
    p = {str(k): float(v) for k, v in (ans.get('p') or {}).items() if number(v)} if isinstance(ans.get('p'), dict) else {}
    why = [str(w) for w in (row_.get('why') or [])] if isinstance(row_.get('why'), list) else []
    odd = [str(o) for o in (row_.get('oddities') or [])] if isinstance(row_.get('oddities'), list) else []
    out = ['ODD ' + ','.join(odd) + ';'] if odd else []
    seen = []
    if ans.get('front'):
        seen.append('ahead ' + str(ans['front']))
    if ans.get('screen') and ans['screen'] != 'play':
        seen.append('screen ' + str(ans['screen']))
    strong = sorted(((k, v) for k, v in p.items() if v >= 0.5 and not k.startswith('clear_') and not k.endswith('_ok')),
                    key=lambda kv: -kv[1])[:3]
    seen += ['%s %s' % (k.replace('_', ' '), pct(v)) for k, v in strong]
    asked_stuck = 'stuck' in why or p.get('stuck', 0) >= 0.5
    if asked_stuck and 'stuck' in p and p['stuck'] < 0.5:
        seen.append('stuck %s' % pct(p['stuck']))
    if asked_stuck and 'clear_left' in p and 'clear_right' in p:
        seen.append('clear left %s right %s' % (pct(p['clear_left']), pct(p['clear_right'])))
    return ' '.join(out + [', '.join(seen) if seen else 'nothing to flag'])


def goal_row(p):
    g, t = clean(p.goal) or '?', clean(p.target) or '?'
    status = ' [%s]' % (clean(p.status) or 'open')
    room = WIDTH - len('GOAL ') - len(status) - len(' FOR ')
    if len(g) + len(t) > room:
        half = room // 2
        if len(g) <= half:
            t = fit(t, room - len(g))
        elif len(t) <= room - half:
            g = fit(g, room - len(t))
        else:
            g, t = fit(g, half), fit(t, room - half)
    return 'GOAL ' + g + status + ' FOR ' + t


def decision_row(p):
    n = '?' if p.n is None else clean(p.n)
    if p.total is not None:
        n += '/' + clean(p.total)
    return fit('decision %s%s' % (n, ('  t %.1f s' % p.t) if number(p.t) else ''))


def shown_candidates(p, k):
    """([(label, probability, chosen)], how many are left out): the likeliest k, the chosen one kept in them."""
    cands = list(p.cands)
    if p.chosen and not any(label == p.chosen for label, _ in cands):
        cands.insert(0, (p.chosen, None))
    if any(prob is not None for _, prob in cands):
        cands.sort(key=lambda c: -(c[1] if c[1] is not None else -1.0))
    shown = cands[:k]
    if p.chosen and not any(label == p.chosen for label, _ in shown):
        shown = shown[:k - 1] + [next(c for c in cands if c[0] == p.chosen)]
    return [(label, prob, label == p.chosen) for label, prob in shown], len(cands) - len(shown)


def candidate_rows(p, k):
    shown, more = shown_candidates(p, k)
    who = ', '.join(x for x in (clean(p.decider), 'choosing' if p.phase == 'deciding' else '') if x)
    rows = [row('CANDIDATES', '(%s)' % who) if who else 'CANDIDATES']
    for label, prob, chosen in shown:
        tail = ('  ' + pct(prob)) if prob is not None else ''
        rows.append(('> ' if chosen else '  ') + fit(clean(label) or '?', WIDTH - 2 - len(tail)) + tail)
    if more > 0:
        rows.append('  +%d more' % more)
    return rows


def step_row(p):
    if p.phase == 'deciding':
        return 'STEP choosing the next step'
    label = clean(p.chosen) or '?'
    if p.phase == 'running':
        return row('STEP', label, ' running')
    return row('STEP', label, ' -> ' + (fit(clean(p.result), 20) or '?'))


def model_row(p):
    if p.decider == 'recover':
        return 'MODEL recovery ladder'
    if p.decider == 'gate':
        return row('MODEL', 'no question: ' + (clean(p.no_request) or 'one valid candidate'))
    if p.model or p.latency_ms is not None:
        name = clean(p.model) or clean(p.decider) or 'model'
        if p.fallback:
            return row('MODEL', name, ' no answer: rules chose')
        bits = []
        if number(p.latency_ms):
            bits.append('%.2f s' % (p.latency_ms / 1000.0))
        if number(p.confidence):
            bits.append('sure %s' % pct(p.confidence))
        if p.phase == 'deciding':
            bits.append('(asking)')
        return row('MODEL', name, (' ' + ' '.join(bits)) if bits else '')
    if p.fallback:
        return row('MODEL', clean(p.decider) or 'model', ' no answer: rules chose')
    return row('MODEL', '%s, no model asked' % (clean(p.decider) or 'no decider'))


def cost_row(p):
    if not p.calls:
        return 'COST none yet: no model call'
    return 'COST $%.4f so far, %d model call%s' % (p.cost, p.calls, '' if p.calls == 1 else 's')


def state_row(p):
    rc = p.recover if isinstance(p.recover, dict) else {}
    if p.decider == 'recover' and p.phase != 'deciding':
        return row('RECOVERY', 'rung ' + (clean(p.rung or rc.get('rung')) or '?'))
    if rc.get('stuck'):
        stalled = rc.get('stalled_s')
        return 'STUCK %.1f s, rung %s' % (stalled if number(stalled) else 0.0, clean(rc.get('rung', 0)))
    streak = rc.get('streak')
    if isinstance(streak, int) and streak >= 3:
        return 'STATE same answer %d times running' % streak
    return 'STATE moving freely'


def vision_row(p, now):
    if not p.eyes:
        return None
    if not p.vision:
        return 'VISION no look yet'
    wall, words = p.vision
    return row('VISION', clean('%d s ago: %s' % (max(0, round(now - wall)), words)))


def render(p, now=None):
    """The panel text: lines joined by newlines, no trailing newline. At most MAX_LINES lines of WIDTH characters."""
    now = time.time() if now is None else now
    head = [goal_row(p), decision_row(p)]
    if p.outcome:
        word = clean(str(p.outcome).split(':', 1)[0])
        if word:
            head.append(row('RUN', word))
    tail = [step_row(p)]
    if p.last:
        tail.append(row('LAST', clean(p.last[0]) or '?', ' -> ' + (fit(clean(p.last[1]), 20) or '?')))
    tail += [model_row(p), cost_row(p), state_row(p)]
    vis = vision_row(p, now)
    if vis:
        tail.append(vis)
    cands = []
    for k in range(min(MAX_SHOWN, len(p.cands) or 1), 0, -1):
        cands = candidate_rows(p, k) if (p.cands or p.chosen) else []
        if len(head) + len(cands) + len(tail) <= MAX_LINES:
            break
    rows = [fit(r.rstrip()) for r in head + cands + tail]
    return '\n'.join(rows[:MAX_LINES])


# ---------------------------------------------------------------------------------------------------------- the pilot's Hud

class Hud:
    """The pilot's side. Methods are told what the pilot knows at each moment and write the panel when it changed:

        deciding(n, goal, target, t, decider, labels, model=None, recover=None)   the candidates are offered, nobody has answered
        decided(label, decider, labels, info=None, recover=None)                   the decider's answer (Choice.info: request's
                                                                                   model, answers' probabilities, latency_ms,
                                                                                   confidence, cost_usd, no_request, recover_rung)
        result(result, goal=None, t=None, recover=None, label=None)               the step's result word (or a target left)
        spend(usd) / look(row)                                                     money for a planner or counterfactual request /
                                                                                   a vision look (vision.py's row)
        finish(outcome) / clear()                                                  the run's end / nothing to show
        configure(total=None, eyes=None, on_error=None)                            what the pilot knows after the Hud was made

    Hud(None) does nothing. goal and target are anything with .name (goal also .status). total is the decision budget, eyes
    whether the run looks at pictures (the VISION row), on_error(text) is called once if the panel can no longer be made or
    written (after which the Hud is silent: a panel never ends a run). Nothing is written before the first decision (money spent
    on a plan or a look before it shows on that decision's panel)."""

    def __init__(self, path=None, total=None, eyes=False, clock=time.time, on_error=None):
        self.path = Path(path) if path is not None else None
        self.clock, self.on_error = clock, on_error
        self.p = Panel(total=total, eyes=bool(eyes))
        self.text, self.dead, self.started = None, False, False

    def configure(self, total=None, eyes=None, on_error=None):
        """The decision budget and whether there are eyes, once the pilot knows them; on_error only where the Hud has none."""
        if total is not None:
            self.p.total = total
        if eyes is not None:
            self.p.eyes = bool(eyes)
        if on_error is not None and self.on_error is None:
            self.on_error = on_error

    # -- what the pilot says
    def deciding(self, n, goal, target, t, decider, labels, model=None, recover=None):
        self._do(self._deciding, n, goal, target, t, decider, labels, model, recover)

    def decided(self, label, decider, labels, info=None, recover=None):
        self._do(self._decided, label, decider, labels, info, recover)

    def result(self, result, goal=None, t=None, recover=None, label=None):
        self._do(self._result, result, goal, t, recover, label)

    def spend(self, usd, calls=1):
        self._do(self._spend, usd, calls)

    def look(self, row_):
        self._do(self._look, row_)

    def finish(self, outcome):
        self._do(self._finish, outcome)

    def clear(self):
        if self.path is None or self.dead or not self.started:   # (nothing was ever shown: nothing to clear)
            return
        try:
            self._put('')
        except Exception as e:   # noqa: BLE001  a panel never ends a run
            self._fail(e)

    # -- the pieces
    def _deciding(self, n, goal, target, t, decider, labels, model, recover):
        p, self.started = self.p, True
        if p.phase == 'done' and p.chosen:
            p.last = (p.chosen, p.result if p.result is not None else '?')
        p.n, p.goal, p.status, p.target = n, getattr(goal, 'name', ''), getattr(goal, 'status', 'open'), getattr(target, 'name', '')
        p.t, p.decider, p.phase = t, decider, 'deciding'
        p.cands = [(str(label), None) for label in labels]
        p.chosen, p.result, p.model, p.latency_ms, p.confidence = '', None, model, None, None
        p.no_request, p.fallback, p.rung = None, False, None
        if isinstance(recover, dict):
            p.recover = recover

    def _decided(self, label, decider, labels, info, recover):
        p, info, self.started = self.p, info if isinstance(info, dict) else {}, True
        probs = probabilities(info)
        req = info.get('request')
        model = req.get('model') if isinstance(req, dict) and isinstance(req.get('model'), str) else None
        cost = info.get('cost_usd')
        p.decider, p.phase, p.chosen, p.result = decider, 'running', str(label), None
        p.cands = [(str(x), probs.get(str(x))) for x in labels]
        p.model = model
        p.latency_ms = info.get('latency_ms') if number(info.get('latency_ms')) else None
        p.confidence = info.get('confidence') if number(info.get('confidence')) else None
        p.no_request, p.rung = info.get('no_request'), info.get('recover_rung')
        p.fallback = bool(info.get('fallback') or info.get('throttled'))
        if isinstance(recover, dict):
            p.recover = recover
        if number(cost):
            p.cost += float(cost)
        if model or number(cost):
            p.calls += 1

    def _result(self, result, goal, t, recover, label):
        p = self.p
        p.phase, p.result = 'done', str(result)
        if label is not None:
            p.chosen = str(label)
        if goal is not None:
            p.status = getattr(goal, 'status', p.status)
        if t is not None:
            p.t = t
        if isinstance(recover, dict):
            p.recover = recover

    def _spend(self, usd, calls):
        if number(usd):
            self.p.cost += float(usd)
        self.p.calls += calls

    def _look(self, row_):
        wall = row_.get('wall')
        self.p.vision = (float(wall) if number(wall) else self.clock(), vision_words(row_))
        self._spend(row_.get('cost_usd'), 1)

    def _finish(self, outcome):
        self.p.outcome = '' if outcome is None else str(outcome)

    # -- the file
    def _do(self, fn, *args):
        if self.path is None or self.dead:
            return
        try:
            fn(*args)
            if self.started:
                self._put(render(self.p, self.clock()))
        except Exception as e:   # noqa: BLE001  a panel never ends a run
            self._fail(e)

    def _put(self, text):
        if text != self.text:
            self.write(text)
            self.text = text

    def write(self, text):
        """The text as the whole new content of the file (a temporary file renamed over it); '' leaves an empty file."""
        tmp = self.path.with_name(self.path.name + '.tmp')
        try:
            with open(tmp, 'w', encoding='ascii') as f:
                f.write(text + '\n' if text else '')
            os.replace(tmp, self.path)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _fail(self, e):
        self.dead = True
        if self.on_error is not None:
            try:
                self.on_error(f'{type(e).__name__}: {e.strerror}' if isinstance(e, OSError) and e.strerror else
                              f'{type(e).__name__}: {e}'[:120])
            except Exception:   # noqa: BLE001
                pass


def probabilities(info):
    """{label: probability} from a Decisions answer: the `next_step` choice's (else the first choice's) probabilities."""
    answers = info.get('answers')
    if not isinstance(answers, list):
        return {}
    pick = None
    for a in answers:
        if isinstance(a, dict) and isinstance(a.get('probabilities'), list):
            if a.get('name') == 'next_step':
                pick = a
                break
            pick = pick or a
    out = {}
    for pr in (pick or {}).get('probabilities') or []:
        if isinstance(pr, dict) and number(pr.get('probability')):
            out[str(pr.get('value'))] = float(pr['probability'])
    return out
