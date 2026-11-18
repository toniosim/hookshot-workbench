#!/usr/bin/env python3
"""hud_text without the game: the plain-text panel the pilot writes to <live>/hud.txt (hsap sends it to the game's own screen
with the control bridge's `overlay` command). Checks every row, the candidates (probabilities, the chosen one, at most five and
`+k more`), 56 characters a line, 14 lines, ASCII only, nothing of a path, a key or a request body, the cost, the vision row,
and the file (replaced whole, never half written, written only when the text changed, a failing disk never raises).

    python3 -I -B test_hud_text.py
"""
import os
import sys
import tempfile
import threading
import time
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hud_text  # noqa: E402


def check(cond, what):
    if not cond:
        raise SystemExit(f'FAILED: {what}')
    print(f'ok: {what}')


def goal(name='door', status='open'):
    return types.SimpleNamespace(name=name, status=status)


def target(name='porch'):
    return types.SimpleNamespace(name=name)


def lines_of(text):
    return text.split('\n')


def valid(text):
    """The contract the game side is told: at most 14 lines of at most 56 characters, printable ASCII, under 2048 bytes."""
    ls = lines_of(text)
    return (len(ls) <= 14 and all(len(x) <= 56 for x in ls) and all(32 <= ord(c) < 127 for x in ls for c in x) and
            len(text.encode()) <= 2048 and not text.endswith('\n') and all(x and x.rstrip() == x for x in ls))


def answer(**probs):
    """What a Decisions answer carries for the choice: the first answer's probabilities by candidate."""
    return {'answers': [{'type': 'choice', 'name': 'next_step', 'choice': max(probs, key=probs.get), 'confidence': 0.6,
                         'probabilities': [{'value': k, 'probability': v} for k, v in probs.items()]}]}


def hud_in(tmp, name='hud.txt', **kw):
    kw.setdefault('total', 40)
    return hud_text.Hud(tmp / name, **kw)


def read(tmp, name='hud.txt'):
    return (tmp / name).read_text().rstrip('\n')


def row_checks(tmp):
    h = hud_in(tmp, 'rows.txt', clock=lambda: 1000.0)
    h.deciding(3, goal(), target(), 12.5, 'openai-decisions', ['go', 'wait', 'side-left'], model='model-x')
    check(read(tmp, 'rows.txt') == '\n'.join([
        'GOAL door [open] FOR porch',
        'decision 3/40  t 12.5 s',
        'CANDIDATES (openai-decisions, choosing)',
        '  go',
        '  wait',
        '  side-left',
        'STEP choosing the next step',
        'MODEL model-x (asking)',
        'COST none yet: no model call',
        'STATE moving freely']), 'before the decider answers: the goal, the decision, the candidates offered, choosing, the model asked')
    info = {'request': {'model': 'model-x', 'input': 'SECRET BODY'}, 'latency_ms': 420.0, 'cost_usd': 0.0002, 'confidence': 0.6,
            **answer(go=0.7, wait=0.15, **{'side-left': 0.15})}
    h.decided('go', 'openai-decisions', ['go', 'wait', 'side-left'], info)
    check(read(tmp, 'rows.txt') == '\n'.join([
        'GOAL door [open] FOR porch',
        'decision 3/40  t 12.5 s',
        'CANDIDATES (openai-decisions)',
        '> go  70%',
        '  wait  15%',
        '  side-left  15%',
        'STEP go running',
        'MODEL model-x 0.42 s sure 60%',
        'COST $0.0002 so far, 1 model call',
        'STATE moving freely']), 'after the answer: the chosen one marked with the model\'s percentages, STEP running, model, latency, sure, cost')
    check('SECRET' not in read(tmp, 'rows.txt'), 'the request body is never in the panel')
    h.result('reached', goal(), t=14.0)
    text = read(tmp, 'rows.txt')
    check(lines_of(text)[1] == 'decision 3/40  t 14.0 s' and 'STEP go -> reached' in lines_of(text) and
          'STEP go running' not in lines_of(text), 'after the step: its result word, and the time of the new state')
    h.deciding(4, goal(), target(), 14.0, 'openai-decisions', ['go', 'wait'], model='model-x')
    text = read(tmp, 'rows.txt')
    ls = lines_of(text)
    check(ls.index('LAST go -> reached') == ls.index('STEP choosing the next step') + 1,
          'the next decision keeps the last step: LAST <label> -> <result> right under STEP')
    check(ls[ls.index('MODEL model-x (asking)') + 1] == 'COST $0.0002 so far, 1 model call', 'the cost so far carries over')
    h.decided('wait', 'openai-decisions', ['go', 'wait'], {'request': {'model': 'model-x'}, 'latency_ms': 1234.0, 'cost_usd': 0.0003})
    text = read(tmp, 'rows.txt')
    check('> wait' in lines_of(text) and '  go' in lines_of(text) and 'COST $0.0005 so far, 2 model calls' in lines_of(text) and
          'MODEL model-x 1.23 s' in lines_of(text), 'no probabilities given: no percentages; costs add up; two calls are plural')
    h.finish('solved')
    check(lines_of(read(tmp, 'rows.txt'))[2] == 'RUN solved' and valid(read(tmp, 'rows.txt')), 'the end of the run says RUN <outcome>')
    h.clear()
    check((tmp / 'rows.txt').read_text() == '', 'clear() leaves an empty file: nothing to show')


def decider_rows(tmp):
    h = hud_in(tmp, 'rules.txt')
    h.deciding(1, goal('g1'), target('t1'), 0.0, 'rules', ['go', 'wait'])
    h.decided('go', 'rules', ['go', 'wait'], {})
    ls = lines_of(read(tmp, 'rules.txt'))
    check(ls[ls.index('STEP go running') + 1] == 'MODEL rules, no model asked' and 'COST none yet: no model call' in ls,
          'rules: MODEL rules, no model asked, and no cost')
    check(lines_of(read(tmp, 'rules.txt'))[2] == 'CANDIDATES (rules)' and lines_of(read(tmp, 'rules.txt'))[3] == '> go' and
          lines_of(read(tmp, 'rules.txt'))[4] == '  wait', 'rules: the chosen one is marked, the other indented two spaces, no percentage')
    h = hud_in(tmp, 'gate.txt')
    h.decided('go', 'gate', ['go'], {'no_request': 'one candidate'})
    check('MODEL no question: one candidate' in lines_of(read(tmp, 'gate.txt')), 'a guard that took the only candidate: no question: one candidate')
    h = hud_in(tmp, 'rec.txt')
    h.deciding(9, goal(), target(), 50.0, 'rules', ['go'])
    h.decided('recover:sidestep', 'recover', ['recover:sidestep'],
              {'no_request': 'recover', 'recover_rung': 'sidestep', 'recover_why': 'no progress'},
              recover={'stuck': True, 'why': 'no progress', 'stalled_s': 6.0, 'rung': 1, 'streak': 0})
    ls = lines_of(read(tmp, 'rec.txt'))
    check('MODEL recovery ladder' in ls and 'RECOVERY rung sidestep' in ls and not any(x.startswith('STATE') or x.startswith('STUCK') for x in ls),
          'a recovery rung: MODEL recovery ladder and RECOVERY rung <name> in place of the state row')
    h = hud_in(tmp, 'stuck.txt')
    h.deciding(2, goal(), target(), 5.0, 'rules', ['go', 'wait'],
               recover={'stuck': True, 'why': 'no progress', 'stalled_s': 4.25, 'rung': 2, 'streak': 1})
    ls = lines_of(read(tmp, 'stuck.txt'))
    check('STUCK 4.2 s, rung 2' in ls and not any(x.startswith('STATE') for x in ls), 'stuck: STUCK <s> s, rung <n>')
    h.deciding(2, goal(), target(), 5.0, 'rules', ['go', 'wait'], recover={'stuck': False, 'streak': 3, 'rung': 0, 'stalled_s': 0.0})
    check('STATE same answer 3 times running' in lines_of(read(tmp, 'stuck.txt')), 'the same answer three times running is said')
    h.deciding(2, goal(), target(), 5.0, 'rules', ['go', 'wait'], recover={'stuck': False, 'streak': 1, 'rung': 0, 'stalled_s': 0.0})
    check('STATE moving freely' in lines_of(read(tmp, 'stuck.txt')), 'a free mover: STATE moving freely')
    h = hud_in(tmp, 'fallback.txt')   # the model was asked and failed: the rules chose; the panel must not claim the model did
    h.deciding(2, goal(), target(), 5.0, 'openai-decisions', ['go', 'wait'], model='model-x')
    h.decided('go', 'openai-decisions', ['go', 'wait'], {'request': {'model': 'model-x', 'input': 'BODY'}, 'fallback': 'ApiError: HTTP 500 /home/x'})
    ls = lines_of(read(tmp, 'fallback.txt'))
    check('MODEL model-x no answer: rules chose' in ls and 'BODY' not in read(tmp, 'fallback.txt') and 'HTTP' not in read(tmp, 'fallback.txt'),
          'a failed request: MODEL <name> no answer: rules chose (the error text stays out)')
    h.decided('go', 'openai-decisions', ['go', 'wait'], {'fallback': 'stopped: cap'})
    check('MODEL openai-decisions no answer: rules chose' in lines_of(read(tmp, 'fallback.txt')), 'a stopped model: the same, by the decider\'s name')
    h = hud_in(tmp, 'goal.txt')
    h.deciding(2, goal('door', 'met'), target(), 5.0, 'rules', ['go'])
    check(lines_of(read(tmp, 'goal.txt'))[0] == 'GOAL door [met] FOR porch', 'the goal\'s status is in its row')
    h.deciding(2, goal('door', 'failed'), target(), 5.0, 'rules', ['go'])
    check(lines_of(read(tmp, 'goal.txt'))[0] == 'GOAL door [failed] FOR porch', 'a failed goal says failed')
    h = hud_in(tmp, 'nototal.txt', total=None)
    h.deciding(2, goal(), target(), None, 'rules', ['go'])
    check(lines_of(read(tmp, 'nototal.txt'))[1] == 'decision 2', 'no total and no time known: just the decision number')


def candidate_checks(tmp):
    labels = [f'step-{i}' for i in range(9)]
    h = hud_in(tmp, 'cands.txt')
    h.deciding(1, goal(), target(), 1.0, 'openai-decisions', labels, model='m')
    probs = {lab: p / 100 for lab, p in zip(labels, (2, 50, 10, 5, 20, 3, 4, 1, 5))}   # (percent)
    h.decided('step-5', 'openai-decisions', labels, {'request': {'model': 'm'}, **answer(**probs)})
    ls = lines_of(read(tmp, 'cands.txt'))
    rows = [x for x in ls if x.startswith('> ') or x.startswith('  step-')]
    check(len(rows) == 5 and ls[3] == '  step-1  50%' and '> step-5  3%' in rows and 'step-4' in ls[4],
          f'at most five candidates, the likeliest first, the chosen one kept even when unlikely ({rows})')
    check('  +4 more' in ls and ls.index('  +4 more') == ls.index(rows[-1]) + 1, 'the ones left out are counted: +4 more')
    check(valid('\n'.join(ls)), 'and the panel is within the limits')
    h.decided('step-1', 'openai-decisions', labels, {'request': {'model': 'm'}, **answer(**probs)})
    ls = lines_of(read(tmp, 'cands.txt'))
    check(ls[3] == '> step-1  50%', 'the likeliest, when chosen, is the first row')
    few = ['a', 'b', 'c']
    h.deciding(2, goal(), target(), 2.0, 'rules', few)
    check(not any('more' in x for x in lines_of(read(tmp, 'cands.txt'))), 'no `+k more` row when all fit')


def limit_checks(tmp):
    long = 'x' * 90
    h = hud_in(tmp, 'long.txt', total=1234567, eyes=True)
    labels = [f'candidate-{i}-' + long for i in range(12)]
    h.deciding(123456, goal(long, 'failed'), target(long), 9999.99, 'openai-decisions-with-a-long-name', labels,
               model='model-' + long, recover={'stuck': True, 'why': 'w', 'stalled_s': 999.9, 'rung': 5, 'streak': 9})
    h.look({'wall': 1000.0, 'cost_usd': 0.001, 'why': ['stuck'], 'oddities': ['odd-' + long, 'other-' + long],
            'answers': {'front': 'front-' + long, 'screen': 'play', 'p': {'door': 0.9, 'chest': 0.8, 'enemy': 0.7, 'person': 0.6}, 'says': 'said ' + long}})
    h.decided(labels[7], 'openai-decisions-with-a-long-name', labels,
              {'request': {'model': 'model-' + long}, 'latency_ms': 123456.0, 'confidence': 1.0, 'cost_usd': 1234.5,
               **answer(**{lab: 1 / 12 for lab in labels})},
              recover={'stuck': True, 'why': 'w', 'stalled_s': 999.9, 'rung': 5, 'streak': 9})
    h.result('result-' + long, goal(long, 'failed'), t=1.0)
    h.deciding(123457, goal(long), target(long), 10000.0, 'openai-decisions-with-a-long-name', labels, model='model-' + long)
    h.finish('solved: ' + long)
    text = read(tmp, 'long.txt')
    ls = lines_of(text)
    check(valid(text) and len(ls) == 14, f'the worst case fits: {len(ls)} lines, longest {max(map(len, ls))} characters, {len(text.encode())} bytes')
    check(ls[0].startswith('GOAL ') and '[open]' in ls[0] and ' FOR ' in ls[0] and '...' in ls[0],
          f'a long goal and target are cut with ... and the status and FOR stay readable ({ls[0]})')
    check(any(x.startswith('STEP ') for x in ls) and any(x.startswith('LAST ') for x in ls) and any(x.startswith('MODEL ') for x in ls) and
          any(x.startswith('COST ') for x in ls) and any(x.startswith('VISION ') for x in ls) and any(x.startswith('RUN ') for x in ls),
          'when lines are short, the candidates give way: every other row is still there')
    # a unicode label, a control character, a tab
    h = hud_in(tmp, 'uni.txt')
    h.deciding(1, goal('t\u00fcr\ttest'), target('caf\u00e9 \u2192 \u7a93'), 1.0, 'rules', ['go \u2192 left', 'wait\x07\x1b[31m'])
    text = read(tmp, 'uni.txt')
    check(valid(text) and '\u2192' not in text and '\x07' not in text and '\x1b' not in text, f'ASCII only, no control character ({lines_of(text)[0]!r})')
    # an empty candidate list and empty names still give a valid panel
    h = hud_in(tmp, 'empty.txt')
    h.deciding(1, goal(''), target(''), 0.0, '', [])
    check(valid(read(tmp, 'empty.txt')), 'empty names and no candidates: still a valid panel')


def secret_checks(tmp):
    key = 'sk' + '-' + 'test-must-never-be-sent-0123456789'   # (built here: no key-shaped literal in the file)
    path = '/home/someone/Games/save/slot_00/progress.sav'
    h = hud_in(tmp, 'secret.txt', eyes=True)
    h.deciding(1, goal(f'goal {path}'), target(f'~/x/{key}'), 1.0, 'rules', [f'go {path}', f'wait {key}', 'file:///tmp/x', 'C:\\Users\\x'],
               model=key)
    h.look({'wall': time.time(), 'why': [path], 'cost_usd': 0, 'oddities': [path],
            'answers': {'front': path, 'screen': key, 'p': {}, 'says': path}})
    h.decided(f'go {path}', 'rules', [f'go {path}'], {'request': {'model': key, 'input': path}, 'fallback': path, 'override': path})
    h.result(f'stuck {path}', goal(), t=2.0)
    h.finish(f'duel interrupted: {path}')
    text = read(tmp, 'secret.txt')
    check('/home' not in text and 'sk-' not in text and 'progress' not in text and '~/' not in text and 'file://' not in text and
          'Users' not in text and '/tmp' not in text, f'no path and no key in any row ({[x for x in lines_of(text) if "..." in x or "?" in x][:3]})')
    check('RUN duel interrupted' in lines_of(text), 'the run outcome keeps only what stands before the colon (the reason may hold a path)')
    check(valid(text), 'still a valid panel')


def vision_checks(tmp):
    now = [2000.0]
    h = hud_in(tmp, 'eyes.txt', eyes=True, clock=lambda: now[0])
    h.deciding(1, goal(), target(), 1.0, 'rules', ['go'])
    check('VISION no look yet' in lines_of(read(tmp, 'eyes.txt')), 'eyes on, no look yet: VISION no look yet')
    row = {'wall': 1988.0, 'why': ['first'], 'cost_usd': 0.0004, 'oddities': [],
           'answers': {'front': 'door', 'screen': 'play', 'p': {'text_box': 0.91, 'stuck': 0.2, 'chest': 0.1, 'clear_left': 0.9}, 'says': 'x'}}
    h.look(row)
    ls = lines_of(read(tmp, 'eyes.txt'))
    check('VISION 12 s ago: ahead door, text box 91%' in ls, f'the look in a few words: what is ahead and what it is sure of ({[x for x in ls if x.startswith("VISION")]})')
    check('COST $0.0004 so far, 1 model call' in ls, 'a look is a model call and costs money')
    now[0] = 2030.0
    h.deciding(2, goal(), target(), 31.0, 'rules', ['go'])
    check('VISION 42 s ago: ahead door, text box 91%' in lines_of(read(tmp, 'eyes.txt')), 'the age is as of the moment the panel was made')
    h.look({'wall': 2030.0, 'why': ['stuck'], 'cost_usd': None, 'oddities': ['screen-not-play'],
            'answers': {'front': None, 'screen': 'menu', 'p': {}, 'says': None}})
    check('VISION 0 s ago: ODD screen-not-play; screen menu' in lines_of(read(tmp, 'eyes.txt')),
          'oddities and a screen that is not play are said')
    h = hud_in(tmp, 'noeyes.txt', eyes=False)
    h.deciding(1, goal(), target(), 1.0, 'rules', ['go'])
    check(not any(x.startswith('VISION') for x in lines_of(read(tmp, 'noeyes.txt'))), 'eyes off: no VISION row at all')
    h.spend(0.0005)
    check('COST $0.0005 so far, 1 model call' in lines_of(read(tmp, 'noeyes.txt')), 'a planner or counterfactual request is spent with spend()')


def file_checks(tmp):
    writes = []

    class Counting(hud_text.Hud):
        def write(self, text):
            writes.append(text)
            return super().write(text)
    path = tmp / 'file.txt'
    h = Counting(path, total=5)
    h.deciding(1, goal(), target(), 1.0, 'rules', ['go'])
    h.deciding(1, goal(), target(), 1.0, 'rules', ['go'])
    check(len(writes) == 1, 'the same text is not written twice')
    check(not list(tmp.glob('file.txt.*')) and not list(tmp.glob('.file.txt*')) and path.read_text().endswith('\n') and
          path.read_text().rstrip('\n') == writes[0], 'one whole file, no temporary left behind')
    ino = path.stat().st_ino
    h.deciding(2, goal(), target(), 2.0, 'rules', ['go'])
    check(path.stat().st_ino != ino, 'a new text replaces the file (a new inode): a reader holds either whole text, never half')

    # a reader racing a writer sees only whole panels
    race = tmp / 'race.txt'
    w = hud_text.Hud(race, total=900)
    made, stop, bad = set(), threading.Event(), []

    def reader():
        while not stop.is_set():
            try:
                text = race.read_text()
            except OSError:
                continue
            if text and text.rstrip('\n') not in made:
                time.sleep(0.01)   # the writer records a text a moment after it was written
                if text.rstrip('\n') not in made:
                    bad.append(text)
    th = threading.Thread(target=reader, daemon=True)
    th.start()
    for n in range(1, 400):
        w.deciding(n, goal('g' * (n % 40)), target('t' * (n % 30)), n / 3, 'rules', ['go', 'wait', 'a' * (n % 50)])
        made.add(race.read_text().rstrip('\n'))
    stop.set()
    th.join(2)
    check(not bad, f'400 panels written while a reader polls: no torn read ({len(bad)} bad)')

    # no path: an off panel writes nothing and never raises
    off = hud_text.Hud(None)
    off.deciding(1, goal(), target(), 1.0, 'rules', ['go'])
    off.decided('go', 'rules', ['go'], {})
    off.result('done', goal())
    off.look({})
    off.spend(1.0)
    off.finish('solved')
    off.clear()
    check(True, 'a Hud without a path does nothing and raises nothing')

    # a disk that fails: one note, no raise, no more tries
    errors = []
    bad_dir = tmp / 'no-such-folder' / 'hud.txt'
    h = hud_text.Hud(bad_dir, total=5, on_error=errors.append)
    h.deciding(1, goal(), target(), 1.0, 'rules', ['go'])
    h.decided('go', 'rules', ['go'], {})
    h.result('done', goal())
    check(len(errors) == 1 and 'no-such-folder' not in errors[0], f'a failing write is reported once, without its path ({errors})')
    # bad data in must not end a run either
    errors2 = []
    h = hud_text.Hud(tmp / 'bad.txt', total=5, on_error=errors2.append)
    h.deciding(1, goal(), target(), 1.0, 'rules', 7)   # not a list of labels
    h.decided('go', 'rules', ['go'], {'answers': 'nonsense', 'request': 5, 'latency_ms': 'x', 'cost_usd': 'y'})
    h.result('done', goal(), t='soon')
    h.look({'wall': 'now', 'answers': 3})
    h.spend('lots')
    h.finish(None)
    check(len(errors2) <= 1, f'bad data never raises into the pilot (at most one note: {errors2})')


def start_checks(tmp):
    h = hud_text.Hud(tmp / 'start.txt')
    h.configure(total=12, eyes=True)
    h.spend(0.0004)
    h.look({'wall': time.time(), 'cost_usd': 0.0004, 'why': ['first'], 'oddities': [],
            'answers': {'front': 'door', 'screen': 'play', 'p': {}, 'says': None}})
    check(not (tmp / 'start.txt').exists(), 'money spent and a look made before the first decision show nothing: no panel without a decision')
    h.deciding(1, goal(), target(), 0.0, 'rules', ['go'])
    ls = lines_of(read(tmp, 'start.txt'))
    check(ls[1] == 'decision 1/12  t 0.0 s' and 'COST $0.0008 so far, 2 model calls' in ls and any(x.startswith('VISION 0 s ago: ahead door') for x in ls),
          'the first decision shows the total and the eyes row configure() set, and what was spent before it')
    mine, theirs = [], []
    h = hud_text.Hud(tmp / 'nope-dir' / 'x.txt', on_error=mine.append)
    h.configure(on_error=theirs.append)
    h.deciding(1, goal(), target(), 0.0, 'rules', ['go'])
    check(len(mine) == 1 and not theirs, 'configure() sets on_error only where the Hud has none')
    h = hud_text.Hud(tmp / 'nope-dir' / 'x.txt')
    h.configure(on_error=theirs.append)
    h.deciding(1, goal(), target(), 0.0, 'rules', ['go'])
    check(len(theirs) == 1, 'and where it has none, the one configure() gives is called once')



def run():
    with tempfile.TemporaryDirectory(prefix='hud-text-') as t:
        tmp = Path(t)
        row_checks(tmp)
        decider_rows(tmp)
        candidate_checks(tmp)
        limit_checks(tmp)
        secret_checks(tmp)
        vision_checks(tmp)
        file_checks(tmp)
        start_checks(tmp)
    print('test_hud_text: all passed')


if __name__ == '__main__':
    run()
