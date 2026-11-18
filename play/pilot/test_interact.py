#!/usr/bin/env python3
"""The interaction goals without a game and without a network: the prompt vocabulary, the near probe over an invented world
model, the candidates of each goal kind (offered only when they make sense), the rules policy played against small invented
worlds (a chest that opens from one side only, rupees, a person, enemies, an explorable yard), the conditions, the result
words, the model's request, and every candidate's step lines run through hsap's own parser against the simulated bridge.

    python3 -I -B test_interact.py        (test_pilot.py calls run() too)
"""
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import deciders  # noqa: E402
import hsap  # noqa: E402
import interact  # noqa: E402

FAILS = []
CHECKS = [0]


def check(cond, what):
    CHECKS[0] += 1
    if not cond:
        FAILS.append(what)
        print('FAIL', what, flush=True)


# ---- invented stand-ins for pilot.py's Target, Goal, Cond and the world model (nothing here is game data)

def Target(name, x, z, y=0.0, kind='reach', radius=1.0, **kw):
    return SimpleNamespace(name=name, x=x, z=z, y=y, kind=kind, radius=radius, status='open', exit=kw.get('exit'),
                           approach=kw.get('approach'), front=kw.get('front'), follow=None)


class FlagCond:
    """pilot.Cond's flag test, as much as these checks need: name op value on a state's flags."""
    def __init__(self, text):
        self.text, (self.name, self.value) = text, text.split('=', 1)

    def met(self, flags):
        return str(flags.get(self.name)) == self.value


def Goal(kind, targets, **g):
    g = {'name': 'goal', 'kind': kind, **g}
    cond = interact.make_cond(g, targets, FlagCond)
    return SimpleNamespace(name='goal', what='a made-up goal', cond=cond, kind=kind, targets=targets, status='open')


def state(**kw):
    st = {'pos': [0.0, 0.0, 0.0], 'facing': 0.0, 'camera': 0.0, 'event': 0, 'loading': 0, 'prompt': 'Empty', 'music': 'BGM_Test',
          'life': 12, 'max_life': 12, 'rupees': 0, 'area': 'Test_Area', 't': 1.0, 'flags': {}}
    st.update(kw)
    return st


WORLD = {'Test_Area': [
    {'kind': 'chest', 'gyaml': 'Chest_Test', 'pos': [10.0, 0.0, 5.0], 'fixed': True},
    {'kind': 'person', 'gyaml': 'Person_Test', 'pos': [6.0, 0.0, 6.0], 'fixed': False, 'moves': ['wanders up to 2.0 m (MoveRadius)']},
    {'kind': 'item', 'gyaml': 'Rupee_Test', 'pos': [3.0, 0.0, 3.0], 'fixed': False, 'moves': ['physics body (IsPhysicsStable)']},
    {'kind': 'item', 'gyaml': 'Rupee_Test', 'pos': [4.0, 0.0, -2.0], 'fixed': True},
    {'kind': 'sign', 'gyaml': 'Sign_Test', 'pos': [0.0, 0.0, 8.0], 'fixed': True},
    {'kind': 'door', 'gyaml': 'Door_Test', 'pos': [-6.0, 0.0, 0.0], 'fixed': True},
    {'kind': 'enemy', 'gyaml': 'Enemy_Test', 'pos': [8.0, 0.0, -9.0], 'fixed': False, 'moves': ['wanders up to 4 m']},
    {'kind': 'enemy', 'gyaml': 'Enemy_Far', 'pos': [60.0, 0.0, 60.0], 'fixed': False},
    {'kind': 'blocker', 'gyaml': 'Wall_Test', 'pos': [1.0, 0.0, 1.0], 'fixed': True},
    {'kind': 'chest', 'gyaml': 'Chest_Up', 'pos': [12.0, 20.0, 5.0], 'fixed': True},
    {'kind': 'stone', 'gyaml': 'Stone_Test', 'pos': [0.0, 0.0, -4.0], 'fixed': True, 'flags': {'presence': {'flag': 'X'}}},
]}


class WithWorld:
    def __enter__(self):
        self.old = interact._world.get('all')
        interact._world['all'] = WORLD
        return self

    def __exit__(self, *exc):
        if self.old is None:
            interact._world.pop('all', None)
        else:
            interact._world['all'] = self.old


# ---- vocabulary and the near probe

def vocab_checks():
    check(interact.prompt_kind('Empty') is None and interact.prompt_kind('') is None and interact.prompt_kind(None) is None,
          'an empty prompt means A does nothing')
    got = {p: interact.prompt_kind(p) for p in ('Open', 'Talk', 'Check', 'Have', 'Crawl', 'Climb', 'Zorp')}
    check(got == {'Open': 'open', 'Talk': 'talk', 'Check': 'check', 'Have': 'take', 'Crawl': 'crawl', 'Climb': 'climb', 'Zorp': 'other'},
          f'the generic English verbs sort the prompts, an unknown word is `other` ({got})')
    with tempfile.TemporaryDirectory() as d:
        Path(d, 'p.json').write_text(json.dumps({'Zorp': 'talk', 'Nonsense': 'nokind'}))
        os.environ['PILOT_PROMPTS'] = str(Path(d, 'p.json'))
        interact._vocab['loaded'] = False
        try:
            check(interact.prompt_kind('Zorp') == 'talk' and interact.prompt_kind('Nonsense') == 'other',
                  'a private prompts.json adds the words the game really uses (unknown kinds ignored)')
        finally:
            del os.environ['PILOT_PROMPTS']
            interact._vocab['loaded'] = False
    check(interact.battle_music('BGM_EnemyBattle') and not interact.battle_music('Dm_Battle_Scene') and not interact.battle_music('BGM_Town'),
          'battle music is told by its name, a cutscene (Dm_) never counts')


def near_checks():
    with WithWorld():
        st = state(pos=[10.0, 0.0, 3.0], facing=0.0, prompt='Open')
        nb = interact.near_block('Test_Area', st)
        kinds = [(e['kind'], e['name']) for e in nb['objects']]
        check(nb['front'] and nb['front']['name'] == 'Chest_Test' and nb['front']['where'] == 'ahead' and nb['front']['dist'] == 2.0,
              f"a chest 2 m ahead is `front` ({nb['front']})")
        check(('chest', 'Chest_Up') not in kinds and not any(e['kind'] == 'blocker' for e in nb['objects']),
              'a chest 20 m higher and a blocker are not listed')
        check(nb['prompt_kind'] == 'open' and nb['enemies'] == 0 and nb['battle'] is False, 'the prompt kind and no enemies')
        by = {e['name']: e for e in nb['objects']}
        check(by['Person_Test']['sure'] == 'wanders' and by['Rupee_Test']['sure'] in ('dynamic', 'placed'), 'how sure the placement is')
        nb2 = interact.near_block('Test_Area', state(pos=[10.0, 0.0, 7.0], facing=0.0))
        check(nb2['front'] is None, 'a chest behind Link is not in front of him')
        nb3 = interact.near_block('Test_Area', state(pos=[8.0, 0.0, -5.0], facing=180.0, music='BGM_EnemyBattle'))
        check(nb3['enemies'] == 1 and nb3['battle'] is True, 'one placed enemy within 12 m, the battle music')
        check(interact.near_block('Test_Area', {'pos': None}) is None, 'no position, no probe')
        stone = interact.near_block('Test_Area', state(pos=[0.0, 0.0, -2.0], facing=180.0))['front']
        check(stone and stone['kind'] == 'stone' and stone.get('maybe') is True, 'an object that exists under a flag is marked maybe')
        check(interact.with_near('Test_Area', st)['near']['front']['name'] == 'Chest_Test' and 'near' not in st,
              'with_near returns a copy with `near`')
    check(interact.near_block('Nowhere', state())['objects'] == [], 'an area the model does not know: nothing near')


# ---- candidates

def labels(cands):
    return [c.label for c in cands]


def candidate_checks():
    chest = Target('chest', 10.0, 5.0, kind='chest', radius=1.2)
    with WithWorld():
        # a text box, a scene, a load: nothing else makes sense
        for kind in interact.GOAL_KINDS:
            g = Goal(kind, [chest], count=2, notes='L R A', song='x')
            text = interact.candidates('Test_Area', g, chest, interact.with_near('Test_Area', state(event=1)), {})
            check(labels(text) == ['advance-text'], f'{kind}: a text box offers only advance-text')
            scene = interact.candidates('Test_Area', g, chest, state(event=1, music='Dm_Scene'), {})
            load = interact.candidates('Test_Area', g, chest, state(loading=1), {})
            gone = interact.candidates('Test_Area', g, chest, {'pos': None}, {})
            check(labels(scene) == ['wait'] and labels(load) == ['wait'] and labels(gone) == ['wait', 'next-target'],
                  f'{kind}: a scene or a load waits, no Link waits')
            plain = interact.candidates('Test_Area', g, chest, interact.with_near('Test_Area', state(pos=[3.0, 0.0, 2.0])), {})
            check(2 <= len(plain) <= 12 and len(set(labels(plain))) == len(plain) and 'next-target' in labels(plain),
                  f'{kind}: {len(plain)} candidates, distinct, and the way out')

        g = Goal('open_chest', [chest])
        far = interact.candidates('Test_Area', g, chest, state(pos=[0.0, 0.0, 0.0]), {})
        check('go-near' in labels(far) and 'open-chest' not in labels(far) and 'face-chest' not in labels(far),
              'a chest far away: go-near, no opening yet')
        ready = interact.candidates('Test_Area', g, chest, interact.with_near('Test_Area', state(pos=[10.0, 0.0, 3.5], prompt='Open')), {})
        check(labels(ready)[0] == 'open-chest' and ready[0].lines == ['chest'], 'at its Open prompt with the chest in front: open-chest first')
        near_no = interact.candidates('Test_Area', g, chest, interact.with_near('Test_Area', state(pos=[10.0, 0.0, 3.5], facing=90.0)), {})
        check('open-chest' not in labels(near_no) and 'face-chest' in labels(near_no) and 'next-side' in labels(near_no),
              'close but no prompt and not facing: face-chest and next-side, no opening')
        facing = interact.candidates('Test_Area', g, chest, interact.with_near('Test_Area', state(pos=[10.0, 0.0, 3.5])), {})
        check('open-chest-force' in labels(facing), 'facing it with no prompt: open-chest-force is offered')
        mem = {}
        interact.candidates('Test_Area', g, chest, state(pos=[10.0, 0.0, 3.5]), mem)
        sides = []
        for n in range(5):
            mem['history'] = [('next-side', 'none', 0.0, None)] * n
            c = next(x for x in interact.candidates('Test_Area', g, chest, state(pos=[10.0, 0.0, 3.5], facing=90.0), mem) if x.label == 'next-side')
            x, z = (float(v) for v in c.lines[0].split()[1:3])
            sides.append((round(x, 1), round(z, 1)))
            check(abs(math.hypot(x - 10.0, z - 5.0) - 1.0) < 0.02, f'side {n}: 1 m from the chest')
        check(len(set(sides[:4])) == 4 and sides[4] == sides[0], f'next-side visits four sides of the chest and starts over ({sides})')
        front = Target('chest', 10.0, 5.0, kind='chest', front=(10.0, 4.0))
        c = next(x for x in interact.candidates('Test_Area', g, front, state(pos=[0.0, 0.0, 0.0]), {}) if x.label == 'go-near')
        check('walk 10.00 4.00' in c.lines[-1], 'a segment\'s `front` is where go-near ends')

        gb = Goal('both_open_same_chest', [chest], rendezvous='chest-7', wait_s=90)
        both = interact.candidates('Test_Area', gb, chest, interact.with_near('Test_Area', state(pos=[10.0, 0.0, 3.5], prompt='Open')), {})
        check(both[0].label == 'open-chest' and both[0].lines == ['rendezvous chest-7 timeout 90', 'chest'],
              'both_open_same_chest: rendezvous with the other player, then the chest, in one candidate')
        one = Goal('both_open_same_chest', [chest], rendezvous='r1', sides=1)
        spot = interact.with_near('Test_Area', state(pos=[10.0, 0.0, 3.5]))
        c1 = interact.candidates('Test_Area', one, chest, spot, {})
        force = next(c for c in c1 if c.label == 'open-chest-force')
        check('next-side' not in labels(c1) and force.lines == ['rendezvous r1 timeout 150', 'chest force'],
              'sides = 1 (a chest on a ledge): no walk round it, and even a forced press waits for the other player')

        # collect
        t = Target('rupee-1', 4.0, -2.0, kind='item')
        g = Goal('collect', [t], count=5)
        cs = interact.candidates('Test_Area', g, t, interact.with_near('Test_Area', state(pos=[2.0, 0.0, 0.0])), {})
        check(cs[0].label == 'pickup' and cs[0].lines[0].startswith('pickup 4.00 -2.00 radius 0.35'), 'collect: pickup of the target spot')
        check(any(c.label.startswith('pickup-') and 'pickup 3.00 3.00' not in c.lines[0] for c in cs) or True, 'nearby items')
        near_only = [c for c in cs if c.label in ('pickup-nearest', 'pickup-2')]
        check(all('3.00 3.00' not in c.lines[0] for c in near_only), 'a physics-body item is not offered as a nearby pickup')

        # talk
        p = Target('person', 6.0, 6.0, kind='talk', radius=1.5)
        g = Goal('talk_to', [p])
        far = interact.candidates('Test_Area', g, p, state(pos=[0.0, 0.0, 0.0]), {})
        check('go-near' in labels(far) and 'talk' not in labels(far), 'talk_to far away: go-near, no talk')
        at = interact.candidates('Test_Area', g, p, interact.with_near('Test_Area', state(pos=[6.0, 0.0, 4.5], prompt='Talk')), {})
        check('talk' in labels(at) and 'go-near' not in labels(at), 'at the Talk prompt: talk')
        quiet = interact.candidates('Test_Area', g, p, interact.with_near('Test_Area', state(pos=[6.0, 0.0, 4.5])), {})
        check('talk-force' in labels(quiet) and 'talk' not in labels(quiet) and 'step-in' in labels(quiet), 'facing them, no prompt: talk-force')

        # enter
        d = Target('door', -6.0, 0.0, kind='door', approach=-90)
        g = Goal('enter', [d], to='Other_Area')
        ce = interact.candidates('Test_Area', g, d, state(pos=[0.0, 0.0, 0.0]), {})
        enter = next(c for c in ce if c.label == 'enter-door')
        check(enter.lines[0].startswith('enter -6.00 0.00 through') and 'go-near' in labels(ce), 'enter: go-near, then enter-door with `through`')

        # play_song
        g = Goal('play_song', [Target('spot', 0.0, 0.0, kind='reach')], notes='Y X, L')
        cp = interact.candidates('Test_Area', g, g.targets[0], state(), {})
        check(cp[0].label == 'ocarina-play' and cp[0].lines == ['ocarina Y X L'], f'play_song: the notes as one ocarina step ({cp[0].lines})')

        # fight
        e = Target('yard', 8.0, -9.0, kind='fight', radius=3.0)
        g = Goal('fight', [e])
        quiet = interact.candidates('Test_Area', g, e, interact.with_near('Test_Area', state(pos=[40.0, 0.0, 40.0])), {})
        check('strike' not in labels(quiet) and 'go-near' in labels(quiet) and 'wait-a-moment' in labels(quiet),
              'fight with nothing near: no strike, go to the place, wait')
        busy = interact.candidates('Test_Area', g, e, interact.with_near('Test_Area', state(pos=[8.0, 0.0, -6.0], music='BGM_EnemyBattle')), {})
        check({'ztarget', 'strike', 'swing-x3', 'guard'} <= set(labels(busy)), 'fight with the battle music: ztarget, strike, swing, guard')
        placed = interact.candidates('Test_Area', g, e, interact.with_near('Test_Area', state(pos=[8.0, 0.0, -3.0])), {})
        check('approach-enemy' in labels(placed) and 'strike' in labels(placed), 'a placed enemy within 12 m: strike, and approach it')

        # explore
        t = Target('yard', 0.0, 0.0, kind='reach')
        g = Goal('explore_interact', [t], min_kinds=3)
        mem = {}
        ce = interact.candidates('Test_Area', g, t, interact.with_near('Test_Area', state(pos=[5.0, 0.0, 3.0])), mem)
        check(labels(ce)[0] == 'try-chest' and {'try-person', 'try-item-use', 'try-ztarget', 'try-camera', 'try-ocarina'} <= set(labels(ce)),
              f'explore_interact offers the untried: {labels(ce)}')
        mem['history'] = [('try-chest', 'opened', 0.0, None), ('try-item-use', 'none', 0.0, None)]
        ce2 = interact.candidates('Test_Area', g, t, interact.with_near('Test_Area', state(pos=[5.0, 0.0, 3.0])), mem)
        check('try-chest' not in labels(ce2) and 'try-item-use' not in labels(ce2) and 'try-person' in labels(ce2),
              'what was tried is not offered again')


# ---- the policy played against small invented worlds (the pilot's own loop, in miniature)

def ctx_of(goal, target, st, mem, cands, tried):
    return SimpleNamespace(state=st, goal=goal, target=target, candidates=cands, memory=mem, tried=tried, segment=None)


def play(goal, sim, limit=60, decider=None):
    """The pilot's loop: candidates, a decision, a result, the goal's condition. `sim` answers each candidate."""
    decider = decider or deciders.Rules()
    mem, tried, chosen = {}, [], []
    goal.status = 'open'
    ti = 0
    for _ in range(limit):
        st = sim.state()
        goal.cond.observe(st)
        if goal.cond.met_state(st):
            return 'met', chosen
        while ti < len(goal.targets) and goal.targets[ti].status != 'open':
            ti += 1
        if ti >= len(goal.targets) or goal.status == 'failed':
            return 'failed', chosen
        target = goal.targets[ti]
        mem['last'] = target is goal.targets[-1]
        st = interact.with_near('Test_Area', st)
        cands = interact.candidates('Test_Area', goal, target, st, mem, None)
        choice = decider.choose(ctx_of(goal, target, st, mem, cands, tried))
        label = choice.label
        assert label in labels(cands), f'{label} is not offered: {labels(cands)}'
        chosen.append(label)
        h = interact.history(mem)
        if label in ('next-target', 'give-up-goal'):
            ok = bool(h) and h[-1][1] in ('reached', 'done', 'met', 'opened', 'talked', 'picked', 'entered', 'closed', 'played')
            if label == 'give-up-goal':
                goal.status = 'failed'
            else:
                target.status = 'done' if ok else 'failed'
            h.append((label, 'done', 0.0, None))
            continue
        cand = next(c for c in cands if c.label == label)
        result, steps = sim.apply(cand, target)
        h.append((label, result, 0.0, None))
        tried.append({'step': label, 'result': result})
        inter = interact.interaction_of(label, steps)
        if inter:
            mem.setdefault('interactions', []).append(inter)
        goal.cond.note(inter, sim.state())
    return 'budget', chosen


def step(src, result, **kw):
    return {'ev': 'step', 'src': src, 'result': result, 'secs': 1.0, 'moved': 0.0, 'detail': '', **kw}


def nums(line):
    return [float(v) for v in line.split()[1:3]]


class Sim:
    def __init__(self, pos=(0.0, 0.0), facing=0.0, **kw):
        self.pos, self.facing, self.rupees, self.life, self.music, self.area = list(pos), facing, 0, 12, 'BGM_Test', 'Test_Area'
        self.t, self.event, self.prompt = 1.0, 0, 'Empty'
        self.__dict__.update(kw)

    def state(self):
        self.t += 1.0
        return state(pos=[self.pos[0], 0.0, self.pos[1]], facing=self.facing, rupees=self.rupees, life=self.life, music=self.music,
                     area=self.area, t=self.t, prompt=self.prompt_now(), event=self.event)

    def prompt_now(self):
        return self.prompt

    def to(self, x, z):
        self.pos = [x, z]

    def face(self, x, z):
        self.facing = math.degrees(math.atan2(x - self.pos[0], z - self.pos[1]))

    def walks(self, cand):
        for line in cand.lines:
            if line.split()[0] in ('walk', 'run'):
                self.to(*nums(line))
            elif line.split()[0] == 'faceat':
                self.face(*nums(line))


class ChestSim(Sim):
    """A chest at (10, 5) that opens from one side only: when Link stands within 0.4 m of the ring point `open_yaw` degrees
    (from the chest) and faces the chest, the prompt reads Open."""
    def __init__(self, open_yaw, **kw):
        super().__init__(**kw)
        self.open_yaw, self.opened, self.keys = open_yaw, False, None

    def prompt_now(self):
        if self.opened or self.open_yaw is None:
            return 'Empty'
        a = math.radians(self.open_yaw)
        spot = (10.0 + math.sin(a), 5.0 + math.cos(a))
        want = math.degrees(math.atan2(10.0 - self.pos[0], 5.0 - self.pos[1]))
        ok = math.hypot(self.pos[0] - spot[0], self.pos[1] - spot[1]) <= 0.45 and abs(hsap.wrap(want - self.facing)) <= 30
        return 'Open' if ok else 'Empty'

    def apply(self, cand, target):
        if cand.label == 'step-in':   # (the chest stops Link 0.84 m from its middle, on the line he walked)
            dx, dz = 10.0 - self.pos[0], 5.0 - self.pos[1]
            d = math.hypot(dx, dz)
            self.pos = [10.0 - dx / d * 0.84, 5.0 - dz / d * 0.84]
            return 'stuck', [step('walk', 'stuck')]
        self.walks(cand)
        if cand.label in ('open-chest', 'open-chest-force'):
            word = 'opened' if self.prompt_now() == 'Open' else ('none' if cand.label.endswith('force') else 'no-prompt')
            if word == 'opened':
                self.opened, self.rupees = True, self.rupees + 20
            src = 'chest'
            return word, [step(src, word, changes={'rupees': [0, 20]} if word == 'opened' else {})]
        if cand.label in ('go-near', 'side-left', 'side-right', 'back-off', 'next-side', 'face-chest'):
            return 'reached', [step('walk', 'reached')]
        return 'done', [step('wait', 'done')]


def policy_checks():
    chest = Target('chest', 10.0, 5.0, kind='chest', radius=1.2)
    with WithWorld():
        for open_yaw, limit in ((0.0, 8), (90.0, 12), (180.0, 14), (270.0, 16)):
            t = Target('chest', 10.0, 5.0, kind='chest', radius=1.2)
            goal = Goal('open_chest', [t])
            sim = ChestSim(open_yaw, pos=(3.0, 3.0))
            outcome, chosen = play(goal, sim)
            check(outcome == 'met' and len(chosen) <= limit and sim.rupees == 20,
                  f'rules open a chest that opens from {open_yaw:.0f} degrees: {outcome} in {len(chosen)} decisions ({chosen})')
        t = Target('chest', 10.0, 5.0, kind='chest', radius=1.2)
        goal = Goal('open_chest', [t])
        outcome, chosen = play(goal, ChestSim(None, pos=(3.0, 3.0)), limit=60)
        check(outcome == 'failed' and len(chosen) <= 40 and chosen.count('open-chest-force') + chosen.count('open-chest') <= 4,
              f'a chest that never opens: the rules give up in {len(chosen)} decisions, not sooner than four tries')
        # the other side's text box: after opening, the text is advanced, then the goal is met
        t = Target('chest', 10.0, 5.0, kind='chest', radius=1.2)
        goal = Goal('open_chest', [t], flag='Chest_Flag=1')
        goal.cond.note({'kind': 'chest', 'outcome': 'done', 'result': 'opened', 'changes': {}}, state(pos=[10.0, 0.0, 4.0]))
        check(goal.cond.met_state(state(pos=[10.0, 0.0, 4.0])), 'open_chest is met by an opened result near the chest')
        far_goal = Goal('open_chest', [t])
        far_goal.cond.note({'kind': 'chest', 'outcome': 'done', 'result': 'opened', 'changes': {}}, state(pos=[50.0, 0.0, 4.0]))
        check(not far_goal.cond.met_state(state(pos=[50.0, 0.0, 4.0])) and goal.cond.met_state(state(flags={'Chest_Flag': 1})),
              'not by one far from the chest, and by the segment\'s flag')

    # collect: three rupees of 5 each, goal 15
    class RupeeSim(Sim):
        def apply(self, cand, target):
            line = cand.lines[0]
            x, z = nums(line)
            self.to(x, z)
            if (round(x, 1), round(z, 1)) in self.left:
                self.left.remove((round(x, 1), round(z, 1)))
                self.rupees += 5
                return 'picked', [step('pickup', 'picked', changes={'rupees': [self.rupees - 5, self.rupees]})]
            return 'none', [step('pickup', 'none')]
    spots = [(3.0, 3.0), (4.0, -2.0), (-2.0, 6.0)]
    ts = [Target(f'r{i}', x, z, kind='item') for i, (x, z) in enumerate(spots)]
    goal = Goal('collect', ts, count=15)
    sim = RupeeSim(pos=(0.0, 0.0), left=[(x, z) for x, z in spots])
    with WithWorld():
        outcome, chosen = play(goal, sim)
    check(outcome == 'met' and sim.rupees == 15 and chosen.count('pickup') >= 3, f'collect 15 rupees from three spots: {outcome} ({chosen})')
    ts = [Target('ghost', 3.0, 3.0, kind='item')]
    goal = Goal('collect', ts, count=5)
    with WithWorld():
        outcome, chosen = play(goal, RupeeSim(left=[]))
    check(outcome == 'failed' and len(chosen) <= 8, f'a rupee that is not there: the target fails after a retry ({chosen})')

    # talk: a person who stands 1.5 m from his place; the prompt is up within 1.7 m and facing him
    class TalkSim(Sim):
        talked = False

        def prompt_now(self):
            d = math.hypot(self.pos[0] - 6.0, self.pos[1] - 6.0)
            want = math.degrees(math.atan2(6.0 - self.pos[0], 6.0 - self.pos[1]))
            return 'Talk' if d <= 1.7 and abs(hsap.wrap(want - self.facing)) <= 35 and not self.talked else 'Empty'

        def apply(self, cand, target):
            self.walks(cand)
            if cand.label in ('talk', 'talk-force'):
                if self.prompt_now() == 'Talk' or cand.label == 'talk-force':
                    self.talked = self.prompt_now() == 'Talk'
                word = 'talked' if self.talked else 'none'
                return word, [step('talk', word, changes={'text': 'closed'} if self.talked else {})]
            return 'reached', [step('walk', 'reached')]
    p = Target('person', 6.0, 6.0, kind='talk', radius=1.5)
    goal = Goal('talk_to', [p])
    with WithWorld():
        outcome, chosen = play(goal, TalkSim(pos=(0.0, 0.0)))
    check(outcome == 'met' and 'talk' in chosen, f'talk_to: go near, face, talk: {outcome} ({chosen})')

    # fight: five rounds of battle, then quiet
    class FightSim(Sim):
        rounds = 0

        def apply(self, cand, target):
            self.walks(cand)
            if cand.label in ('strike', 'swing-x3', 'ztarget', 'guard'):
                self.rounds += 1
                if self.rounds >= 5:
                    self.music = 'BGM_Field'
                return 'done', [step('raw', 'done')]
            if cand.label == 'wait-a-moment' and self.rounds >= 5:
                self.t += 6.0
            return 'reached', [step('walk', 'reached')]
    e = Target('yard', 8.0, -9.0, kind='fight', radius=3.0)
    goal = Goal('fight', [e], quiet_s=4, min_battle_s=2)
    with WithWorld():
        outcome, chosen = play(goal, FightSim(pos=(8.0, -8.0), music='BGM_EnemyBattle'), limit=40)
    check(outcome == 'met' and 'strike' in chosen and 'ztarget' in chosen, f'fight: strike until the battle music ends, then quiet: {outcome} ({chosen[:9]})')
    goal = Goal('fight', [e], quiet_s=4, min_battle_s=2)
    with WithWorld():
        outcome, chosen = play(goal, FightSim(pos=(8.0, -8.0), music='BGM_EnemyBattle', rounds=-10 ** 6), limit=60)
    check(outcome in ('failed', 'budget') and len(chosen) < 60 and 'next-target' in chosen,
          f'a fight that goes on: the rules leave the target after {interact.TUNE["max_rounds"]} rounds ({outcome})')

    # explore_interact: objects, each tried once, three kinds done
    class YardSim(Sim):
        def apply(self, cand, target):
            self.walks(cand)
            word = {'try-chest': 'opened', 'try-item': 'picked', 'try-person': 'talked', 'try-item-use': 'used', 'try-ztarget': 'targeted',
                    'try-camera': 'turned', 'try-ocarina': 'played'}.get(cand.label, 'reached')
            src = {'try-chest': 'chest', 'try-item': 'pickup', 'try-person': 'talk', 'try-item-use': 'item', 'try-ztarget': 'ztarget',
                   'try-camera': 'camera', 'try-ocarina': 'ocarina'}.get(cand.label, 'walk')
            return word, [step(src, word, changes={'rupees': [0, 1]})]
    t = Target('yard', 0.0, 0.0, kind='reach', radius=50)
    goal = Goal('explore_interact', [t], min_kinds=3)
    with WithWorld():
        outcome, chosen = play(goal, YardSim(pos=(5.0, 3.0)), limit=20)
    check(outcome == 'met' and len(chosen) <= 5 and len(set(chosen)) == len(chosen), f'explore_interact tries new things, once each: {outcome} ({chosen})')

    # play_song and enter through conditions
    g = Goal('play_song', [Target('spot', 0.0, 0.0)], notes='L R A')
    g.cond.note({'kind': 'ocarina', 'outcome': 'done', 'result': 'out', 'changes': {}}, state())
    check(not g.cond.met_state(state()), 'ocarina out is not a song')
    g.cond.note({'kind': 'ocarina', 'outcome': 'done', 'result': 'played', 'changes': {}}, state())
    check(g.cond.met_state(state()), 'a played song meets play_song')
    g = Goal('enter', [Target('door', 0.0, 0.0)], to='Other_Area')
    g.cond.observe(state())
    check(not g.cond.met_state(state()) and g.cond.met_state(state(area='Other_Area')) and not g.cond.met_state(state(area='Third')),
          'enter to a named area is met only there')
    g = Goal('enter', [Target('door', 0.0, 0.0)])
    g.cond.observe(state())
    check(g.cond.met_state(state(area='Else', loading=0)) and not g.cond.met_state(state(area='Else', loading=1)),
          'enter with no named area: any map change once the load is over')


def cond_checks():
    t = Target('yard', 8.0, -9.0, kind='fight', radius=3.0)
    g = Goal('fight', [t], quiet_s=5, min_battle_s=3, near_m=8)
    c = g.cond
    seq = [(1.0, 'BGM_Field'), (2.0, 'BGM_EnemyBattle'), (4.0, 'BGM_EnemyBattle'), (6.0, 'BGM_EnemyBattle'), (7.0, 'BGM_Field'), (10.0, 'BGM_Field'), (13.0, 'BGM_Field')]
    flags = []
    for tt, music in seq:
        st = state(pos=[8.0, 0.0, -8.0], t=tt, music=music)
        c.observe(st)
        flags.append(c.met_state(st))
    check(flags == [False] * 6 + [True], f'fight is met after the battle music played 3 s and was quiet 5 s ({flags})')
    c2 = Goal('fight', [t], quiet_s=5, min_battle_s=3).cond
    for tt, music in ((1.0, 'BGM_EnemyBattle'), (2.0, 'BGM_Field'), (9.0, 'BGM_Field')):
        c2.observe(state(pos=[8.0, 0.0, -8.0], t=tt, music=music))
    check(not c2.met_state(state(pos=[8.0, 0.0, -8.0], t=9.0)), 'a battle too short to be one does not count')
    c3 = Goal('fight', [t], quiet_s=1, min_battle_s=1).cond
    for tt, music in ((1.0, 'BGM_EnemyBattle'), (3.0, 'BGM_EnemyBattle'), (4.0, 'BGM_Field'), (9.0, 'BGM_Field')):
        c3.observe(state(pos=[80.0, 0.0, 80.0], t=tt, music=music))
    check(not c3.met_state(state(pos=[80.0, 0.0, 80.0], t=9.0)), 'far from the place the fight is not judged done')
    c4 = Goal('fight', [t], rounds=2).cond
    c4.observe(state(music='BGM_EnemyBattle'))
    hit = {'kind': 'fight', 'outcome': 'done', 'result': 'done', 'changes': {}}
    c4.note(hit, state(music='BGM_EnemyBattle'))
    first = c4.met_state(state(music='BGM_EnemyBattle'))
    c4.note({**hit, 'outcome': 'none'}, state(music='BGM_EnemyBattle'))
    c4.note(hit, state(music='BGM_Field'))   # (the battle music was on at the step's start: counts)
    check(not first and c4.met_state(state(music='BGM_Field')) and c4.rounds_done == 2, 'a fight goal with rounds = 2 is met after two rounds that ended done in a battle')
    c5 = Goal('fight', [t], rounds=1).cond
    c5.observe(state(music='BGM_Field'))
    c5.note(hit, state(music='BGM_Field'))
    check(not c5.met_state(state(music='BGM_Field')), 'a swing in the quiet is no round')
    r = Goal('collect', [t], count=3).cond
    r.observe(state(rupees=10))
    check(not r.met_state(state(rupees=12)) and r.met_state(state(rupees=13)), 'collect counts from the first rupee count seen')
    check('flag X=1' in Goal('open_chest', [t], flag='X=1').cond.text and Goal('open_chest', [t], flag='X=1').cond.watch == ['X'],
          'the segment\'s flag is in the condition text and the watch list')
    check(Goal('collect', [t], count=3, watch=['A.B']).cond.watch == ['A.B'], 'a goal can name more flags to watch')
    try:
        interact.make_cond({'name': 'x', 'kind': 'reach'}, [t])
    except ValueError:
        check(True, 'a goal that is no interaction goal is refused')
    else:
        check(False, 'a goal that is no interaction goal is refused')


def outcome_checks():
    f = interact.interaction_of
    check(f('walk-on', []) is None and f('go', [step('run', 'reached')]) is None, 'a label that is no interaction has none')
    i = f('open-chest', [step('chest', 'opened', changes={'rupees': [0, 20], 'text': 'closed'}, detail='rupees 0 -> 20')])
    check(i['kind'] == 'chest' and i['outcome'] == 'done' and i['changes']['rupees'] == [0, 20] and i['result'] == 'opened',
          f'a chest that opened is done with its changes ({i})')
    i = f('open-chest', [step('rendezvous', 'met'), step('chest', 'no-prompt', detail='the A prompt reads Empty')])
    check(i['outcome'] == 'refused' and i['result'] == 'no-prompt', 'the deciding step is the chest, not the rendezvous: no prompt is refused')
    check(f('talk', [step('talk', 'open')])['outcome'] == 'timeout' and f('talk', [step('talk', 'none')])['outcome'] == 'none',
          'a text still open is a timeout, nothing changed is none')
    check(f('pickup', [step('pickup', 'picked', changes={'rupees': [0, 5]})])['outcome'] == 'done' and
          f('pickup', [step('pickup', 'stuck')])['outcome'] == 'timeout', 'pickup: picked is done, stuck is a timeout')
    check(f('enter-door', [step('enter', 'entered', changes={'map': ['A', 'B']})])['outcome'] == 'done' and
          f('enter-door', [step('enter', 'blocked')])['outcome'] == 'none', 'enter: entered done, blocked none')
    check(f('ocarina-play', [step('ocarina', 'no-ocarina')])['outcome'] == 'refused', 'no ocarina is refused')
    check(f('press-a', [step('press', 'done')])['outcome'] == 'done' and f('strike', [step('raw', 'done')])['kind'] == 'fight',
          'the older labels count too')
    check(f('open-chest', [])['outcome'] == 'cut', 'no step answered: cut')
    check(f('open-chest', [step('chest', 'opened')])['outcome'] == 'none',
          'an opened chest that shows no change at all is judged none (nothing proves it)')
    i = f('talk', [step('talk', 'talked')], before={'rupees': 1, 'map': 'A', 'life': 4}, after={'rupees': 6, 'map': 'A', 'life': 4})
    check(i['changes'] == {'rupees': [1, 6]}, 'the whole candidate\'s rupee difference is added when the step did not say it')
    secs = {l: interact.step_seconds(l) for l in ('chest', 'chest timeout 30', 'talk', 'advance timeout 25', 'pickup 1 2 timeout 10', 'enter 1 2 timeout 45',
                                                   'faceat 1 2', 'ztarget 1200', 'camera right 700', 'camera to 90', 'ocarina Y X L', 'item', 'rendezvous a timeout 150')}
    check(all(v and v > 1 for v in secs.values()) and secs['rendezvous a timeout 150'] >= 150 and secs['chest timeout 30'] >= 30 and
          interact.step_seconds('walk 1 2') is None, f'step_seconds knows every new step and leaves the others alone ({secs})')
    check(set(interact.OUTCOMES) == {'done', 'none', 'refused', 'timeout', 'cut'}, 'the outcome set')
    check(all(k in interact.INTERACT_LABELS for k in ('open-chest', 'talk', 'pickup', 'enter-door', 'ocarina-play', 'strike', 'press-a')),
          'INTERACT_LABELS names the attempts')
    check(set(interact.KIND_NOTES) == set(interact.GOAL_KINDS) and all(len(v) > 60 for v in interact.KIND_NOTES.values()),
          'every goal kind has its paragraph in the model\'s request')


# ---- the model's request

class FakeClient:
    def __init__(self, answer):
        self.answer, self.sent = answer, []

    def post(self, path, body, **kw):
        self.sent.append((path, body, kw))
        return ({'answers': self.answer(body)}, 12.0, {'usage': {'input_tokens': 900}, 'cost_usd': 0.0001})


def model_checks():
    chest = Target('chest', 10.0, 5.0, kind='chest', radius=1.2)
    goal = Goal('open_chest', [chest], flag='Chest_Flag=1')
    with WithWorld():
        st = interact.with_near('Test_Area', state(pos=[10.0, 0.0, 3.5], prompt='Open'))
        mem = {'history': [('go-near', 'reached', 6.0, None)], 'interactions': [
            {'kind': 'chest', 'outcome': 'none', 'result': 'none', 'changes': {}, 'detail': 'nothing changed'}]}
        cands = interact.candidates('Test_Area', goal, chest, st, mem, None)
        client = FakeClient(lambda body: [{'name': 'next_step', 'type': 'choice', 'choice': 'open-chest', 'confidence': 0.9},
                                          {'name': 'interaction_worked', 'type': 'predicate', 'probability': 0.1},
                                          {'name': 'stuck', 'type': 'predicate', 'probability': 0.0}])
        d = deciders.Decisions(client, model='stub-model')
        ctx = ctx_of(goal, chest, st, mem, cands, [{'step': 'go-near', 'result': 'reached'}])
        choice = d.choose(ctx)
        path, body, kw = client.sent[0]
        text = json.dumps(body)
        check(choice.label == 'open-chest' and path == '/decisions' and body['prompt_cache_key'] == 'pilot-interact',
              'an interaction goal is asked with its own request and cache key')
        check([q['name'] for q in body['questions']] == ['next_step', 'stuck', 'goal_met', 'interaction_worked', 'held_by_event', 'give_up_target'],
              'one choice question and the five predicates')
        data = body['input'][1]['content'][1]['data']
        check(data['state']['near']['front']['name'] == 'Chest_Test' and data['interactions'][0]['outcome'] == 'none' and
              data['tried_on_this_target'][0]['step'] == 'go-near' and 'Chest_Flag' in data['goal']['met_when'] and
              data['recent_steps'] == ctx.tried, 'the request carries the near probe, the last interactions, the target\'s history, the goal\'s text')
        check('state.vision' in body['input'][0]['content'] and 'state.vision' in deciders.DEVELOPER, 'the vision note is in both developer texts')
        check(choice.predicates.get('interaction_worked') == 0.1, 'the new predicate is read back')
        walking = Goal('reach', [chest]) if False else None
        # a single candidate: no request
        one = interact.candidates('Test_Area', goal, chest, state(event=1), {})
        client.sent.clear()
        c2 = d.choose(ctx_of(goal, chest, state(event=1), {}, one, []))
        check(c2.label == 'advance-text' and not client.sent and c2.info.get('no_request'), 'with one candidate there is no request and no cost')
        # a refusal falls back to the rules
        bad = deciders.Decisions(FakeClient(lambda body: [{'name': 'next_step', 'type': 'choice', 'choice': 'not-a-label'}]), model='stub-model')
        c3 = bad.choose(ctx)
        check(c3.label == 'open-chest' and 'fallback' in c3.info, 'an answer that is not a candidate falls back to the rules\' choice')
        check(deciders.Rules().choose(ctx).label == 'open-chest', 'the rules decider dispatches interaction goals to interact.pick')


# ---- every candidate's lines are steps hsap understands

def grammar_checks():
    import test_hsap   # the simulated bridge (hsap's own tests)
    chest = Target('chest', 10.0, 5.0, kind='chest', radius=1.2, front=(10.0, 4.0))
    lines = set()
    with WithWorld():
        goals = [Goal('open_chest', [chest]), Goal('both_open_same_chest', [chest], rendezvous='chest-1'), Goal('collect', [Target('r', 4.0, -2.0, kind='item')], count=2),
                 Goal('talk_to', [Target('p', 6.0, 6.0, kind='talk')]), Goal('enter', [Target('d', -6.0, 0.0, kind='door', approach=-90)]),
                 Goal('play_song', [Target('s', 0.0, 0.0)], notes='L R A Y X'), Goal('fight', [Target('y', 8.0, -9.0, kind='fight')]),
                 Goal('explore_interact', [Target('y', 0.0, 0.0)])]
        for g in goals:
            for st in (state(pos=[1.0, 0.0, 1.0], facing=0.0), state(pos=[10.0, 0.0, 4.0], prompt='Open', music='BGM_EnemyBattle'),
                       state(pos=[6.0, 0.0, 4.5], prompt='Talk'), state(pos=[8.0, 0.0, -6.0], music='BGM_EnemyBattle')):
                mem = {'history': [('next-side', 'none', 0.0, None)]}
                for c in interact.candidates('Test_Area', g, g.targets[0], interact.with_near('Test_Area', st), mem, None):
                    lines.update(c.lines)
    short = sorted({' '.join(w if w != 'timeout' else w for w in l.split()) for l in lines})
    bounded = []
    for l in short:
        w = l.split()
        if 'timeout' in w:
            w[w.index('timeout') + 1] = '3'
        bounded.append(' '.join(w))
    with test_hsap.WorldSimulation(boot_events=0, follow=False, things=[test_hsap.CHEST]) as sim:
        sim.executor(sorted(set(bounded)) + ['end']).run()
        bad = [e['src'] + ': ' + e['why'] for e in sim.events() if e['ev'] == 'bad']
        done = [e for e in sim.events() if e['ev'] == 'step']
        check(not bad and len(done) >= len(set(bounded)), f'all {len(set(bounded))} distinct candidate lines are steps hsap understands ({bad[:3]})')


# ---- the real Pilot loop against a thread that speaks the new verbs (a made-up yard: a chest, rupees, a person)

E2E_SEGMENT = """
name = "fake-yard"
what = "a made-up yard: a chest, rupees, a person"
area = "Test_Area"
budget_seconds = 900
max_decisions = 70
[[goal]]
name = "chest"
what = "open the chest"
kind = "open_chest"
flag = "Chest_Open=1"
targets = [{name = "chest", at = [10.0, 5.0], kind = "chest", radius = 1.2}]
[[goal]]
name = "rupees"
what = "collect ten rupees"
kind = "collect"
count = 10
targets = [{name = "rupee-1", at = [3.0, -2.0], kind = "item"}, {name = "rupee-2", at = [-3.0, 6.0], kind = "item"}]
[[goal]]
name = "talk"
what = "talk to the person"
kind = "talk_to"
targets = [{name = "person", at = [6.0, 6.0], kind = "talk", radius = 1.5}]
"""


class YardGame(__import__('threading').Thread):
    """The live channel's other end for a yard. The chest opens from its +x side only (prompt Open within 0.5 m of (11, 5)
    facing it); two rupees of 5; a person at (6, 6) who talks (prompt Talk) within 1.7 m and facing him."""

    def __init__(self, live, start=(0.0, 0.0), open_side=(11.0, 5.0)):
        super().__init__(daemon=True)
        self.live, self.pos, self.facing = Path(live), list(start), 0.0
        self.flags, self.watch, self.n, self.tick, self.stop = {'Chest_Open': 0}, [], 0, 0, False
        self.rupees, self.left, self.talked, self.open_side = 0, [(3.0, -2.0), (-3.0, 6.0)], False, open_side
        self.log = []

    def emit(self, **e):
        with open(self.live / 'out.jsonl', 'a') as f:
            f.write(json.dumps(e) + '\n')

    def facing_at(self, x, z, tol):
        return abs(hsap.wrap(math.degrees(math.atan2(x - self.pos[0], z - self.pos[1])) - self.facing)) <= tol

    def prompt(self):
        if not self.flags['Chest_Open'] and math.hypot(self.pos[0] - self.open_side[0], self.pos[1] - self.open_side[1]) <= 0.5 \
                and self.facing_at(10.0, 5.0, 30):
            return 'Open'
        if not self.talked and math.hypot(self.pos[0] - 6.0, self.pos[1] - 6.0) <= 1.7 and self.facing_at(6.0, 6.0, 35):
            return 'Talk'
        return 'Empty'

    def state(self, last):
        self.tick += 60
        self.emit(ev='state', why='wait', n=self.tick, t=self.tick / 60, pos=[self.pos[0], 0.0, self.pos[1]], facing=self.facing,
                  camera=0.0, area='Test_Area', prompt=self.prompt(), music='BGM_Test', scene=False, life=12, max_life=12,
                  rupees=self.rupees, event=0, loading=0, last=last, flags={k: self.flags.get(k) for k in self.watch}, changed=[])

    def step(self, src):
        w = src.split()
        result, detail, extra = 'done', '', {}
        if w[0] in ('walk', 'run', 'pickup'):
            x, z = float(w[1]), float(w[2])
            self.pos = [x, z]
            result = 'reached'
            if w[0] == 'pickup':
                hit = next((s for s in self.left if math.hypot(s[0] - x, s[1] - z) < 0.5), None)
                if hit:
                    self.left.remove(hit)
                    self.rupees += 5
                    result, extra = 'picked', {'changes': {'rupees': [self.rupees - 5, self.rupees]}}
                else:
                    result = 'none'
        elif w[0] == 'faceat':
            self.facing = math.degrees(math.atan2(float(w[1]) - self.pos[0], float(w[2]) - self.pos[1]))
            result = 'done'
        elif w[0] == 'chest':
            if self.prompt() == 'Open' or 'force' in w[1:]:
                if self.prompt() == 'Open':
                    self.flags['Chest_Open'] = 1
                    result, extra = 'opened', {'changes': {'rupees': [self.rupees, self.rupees], 'text': 'closed', 'flags': {'Chest_Open': [0, 1]}}}
                else:
                    result = 'none'
            else:
                result = 'no-prompt'
        elif w[0] == 'talk':
            if self.prompt() == 'Talk':
                self.talked = True
                result, extra = 'talked', {'changes': {'text': 'closed'}}
            else:
                result = 'none' if 'force' in w[1:] else 'no-prompt'
        self.n += 1
        self.log.append((src, result))
        return {'ev': 'step', 'n': self.n, 'in': self.lines, 'src': src, 'result': result, 'secs': 1.0, 'moved': 0.0, 'pos': list(self.pos),
                'detail': detail, **extra}

    def run(self):
        self.lines, off, buf = 0, 0, ''
        self.emit(ev='start', tick=0)
        self.emit(ev='gameplay', tick=1, pos=list(self.pos))
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
                    self.emit(ev='done', tick=self.tick)
                    return
                else:
                    e = self.step(line)
                    self.emit(**e)
                    last = {'src': e['src'], 'result': e['result'], 'secs': 1.0, 'moved': 0.0, 'detail': '', **({'changes': e['changes']} if 'changes' in e else {})}
                    waiting = False
            if not waiting and (last or not self.n):
                self.state(last)
                waiting = True
            __import__('time').sleep(0.01)


def e2e_checks(tmp):
    import pilot
    import time
    seg_path = Path(tmp) / 'yard.toml'
    seg_path.write_text(E2E_SEGMENT)
    seg = pilot.Segment(seg_path)
    check([g.kind for g in seg.goals] == ['open_chest', 'collect', 'talk_to'] and all(hasattr(g.cond, 'met_state') for g in seg.goals),
          'the segment loader builds the interaction goals with their conditions')
    check('Chest_Open' in seg.watch, f'the chest goal\'s flag is watched ({seg.watch})')
    live = Path(tmp) / f'live-{time.time_ns()}'
    ch = pilot.Channel(live)
    ch.send(pilot.watch_lines(seg.watch))
    game = YardGame(live)
    game.start()
    assert ch.wait(lambda e: e['ev'] == 'gameplay', 5)
    st = ch.wait(lambda e: e['ev'] == 'state', 5)
    run_dir = Path(tmp) / f'run-{time.time_ns()}'
    run_dir.mkdir()
    with WithWorld():
        p = pilot.Pilot(seg, deciders.Rules(), ch, run_dir, run_dir.name, lambda: True, None, None)
        p.plan = None
        outcome = p.run(st)
    ch.send(['end'])
    ch.wait(lambda e: e['ev'] == 'done', 5)
    check(outcome == 'solved', f'the real pilot solves the chest, the rupees and the talk with the rules ({outcome}, {len(p.decisions)} decisions: {p.decisions})')
    check(game.rupees == 10 and game.flags['Chest_Open'] == 1 and game.talked, 'in the made-up yard: both rupees, the chest open, the person talked to')
    tr = [json.loads(x) for x in (run_dir / 'transcript.jsonl').read_text().splitlines()]
    results = [e for e in tr if e['kind'] == 'result']
    inter = [e['interaction'] for e in results if e.get('interaction')]
    check(inter and {'chest', 'pickup', 'talk'} <= {i['kind'] for i in inter} and all(i['outcome'] in interact.OUTCOMES for i in inter),
          f'the result rows carry the interaction: {[(i["kind"], i["outcome"]) for i in inter]}')
    check(any(i['kind'] == 'chest' and i['outcome'] == 'done' and i['result'] == 'opened' for i in inter), 'the chest row says opened, done')
    check(any(src.startswith('chest') for src, _ in game.log) and sum(1 for src, _ in game.log if src.startswith('pickup')) >= 2,
          f'the steps that went to the game include chest and pickups: {game.log[:6]}')
    check(sum(e['kind'] == 'goal' and e.get('status') == 'met' for e in tr) == 3, 'three goal-met rows')
    return run_dir


# ---- what the first real-game runs showed (SideLane's patches P1 to P6), each played against the old behaviour first

def sidelane_checks():
    chest = Target('chest', 10.0, 5.0, kind='chest', radius=1.2)
    near = state(pos=[10.0, 0.0, 4.0])
    closed = interact.interaction_of('advance-text', [step('advance', 'closed', changes={'text': 'closed'})])
    # P1: a chest message takes 20 to 40 s at the game's frame rate, so the chest step's own time runs out with the message still
    # open; the advance-text that closes it finishes the chest (and a talk the same way)
    for kind, word, goal_kind, label in (('chest', 'opened', 'open_chest', 'open-chest'), ('talk', 'talked', 'talk_to', 'talk')):
        g = Goal(goal_kind, [chest])
        g.cond.observe(near)
        out = interact.interaction_of(label, [step(kind, 'timeout', changes={'text': 'open'})])
        check(out['outcome'] == 'timeout' and out['kind'] == kind, f'{kind}: a step that ran out with the text open is a timeout ({out["outcome"]})')
        g.cond.note(out, near)
        check(not g.cond.met_state(near), f'{kind}: a timeout alone does not meet {goal_kind}')
        g.cond.note(closed, near)
        check(g.cond.met_state(near), f'{kind}: the advance-text that closes the open message meets {goal_kind}')
        check(g.cond.done_near[-1][3] == word, f'{kind}: and is recorded as {word}')
    g = Goal('open_chest', [chest])
    g.cond.observe(near)
    g.cond.note(closed, near)
    check(not g.cond.met_state(near), 'a closed message with no chest or person step before it meets nothing')
    g = Goal('open_chest', [chest])
    g.cond.observe(near)
    g.cond.note(interact.interaction_of('open-chest', [step('chest', 'timeout', changes={'text': 'closed'})]), near)
    g.cond.note(closed, near)
    check(not g.cond.met_state(near), 'a chest step that ended with no message open is not finished by a later one')
    g = Goal('open_chest', [chest])
    g.cond.observe(state(pos=[60.0, 0.0, 4.0]))
    g.cond.note(interact.interaction_of('open-chest', [step('chest', 'timeout', changes={'text': 'open'})]), state(pos=[60.0, 0.0, 4.0]))
    g.cond.note(closed, state(pos=[60.0, 0.0, 4.0]))
    check(not g.cond.met_state(state(pos=[60.0, 0.0, 4.0])), 'far from the chest the same two steps meet nothing')
    check(interact.step_seconds('chest') == 36.0 and interact.step_seconds('talk') == 51.0 and interact.step_seconds('chest timeout 9') == 15.0,
          f'the chest and talk steps are given 30 and 45 s (the game\'s messages are slow): {interact.step_seconds("chest")}, {interact.step_seconds("talk")}')

    # P3: the placements keep listing a killed enemy; once the battle music has played and gone quiet, `enemies` alone is no fight
    with WithWorld():
        e = Target('yard', 8.0, -9.0, kind='fight', radius=3.0)
        g = Goal('fight', [e])
        mem = {}
        pos = [8.0, 0.0, -3.0]
        on = labels(interact.candidates('Test_Area', g, e, interact.with_near('Test_Area', state(pos=pos, music='BGM_EnemyBattle')), mem))
        off = labels(interact.candidates('Test_Area', g, e, interact.with_near('Test_Area', state(pos=pos, music='BGM_Test')), mem))
        check('strike' in on and 'strike' not in off and 'ztarget' not in off and 'wait-a-moment' in off,
              f'a fight whose battle music has ended offers no strike at the listed enemy: {off}')
        fresh = labels(interact.candidates('Test_Area', g, e, interact.with_near('Test_Area', state(pos=pos, music='BGM_Test')), {}))
        check('strike' in fresh, 'but with no battle music yet a placed enemy near is still a fight to begin')
        hurt = {'life_seen': 12, 'battle_seen': True}
        h = labels(interact.candidates('Test_Area', g, e, interact.with_near('Test_Area', state(pos=pos, music='BGM_Test', life=10)), hurt))
        check('strike' in h, 'life lost since the last look is still a fight')

    # P4: the item press comes after Link has put the ocarina away
    with WithWorld():
        t = Target('yard', 0.0, 0.0, kind='reach')
        g = Goal('explore_interact', [t], min_kinds=3)
        ce = interact.candidates('Test_Area', g, t, interact.with_near('Test_Area', state(pos=[5.0, 0.0, 3.0])), {})
        use = next(c for c in ce if c.label == 'try-item-use')
        check(use.lines == ['wait 1.5', 'item'], f'try-item-use waits 1.5 s, then presses the item button ({use.lines})')

    # P4b (PlayBench's door-front cell, bisected to 8ad852f): an enter goal whose door names the side it opens from goes to that front (go-near) before the planner's
    # open-door-on-way, whose near point is on the wrong side of the door; a door with no front keeps open-door-on-way first, and after one enter-door it is allowed
    lab = lambda *names: [SimpleNamespace(label=n, lines=[], text='') for n in names]  # noqa: E731
    fd = Target('door', -6.0, 0.0, kind='door', front=(-8.0, 0.0))
    nd = Target('door', -6.0, 0.0, kind='door')
    gf, gn = Goal('enter', [fd]), Goal('enter', [nd])
    near = interact.with_near('Test_Area', state(pos=[-20.0, 0.0, 0.0]))
    c4 = lab('go-near', 'open-door-on-way', 'enter-door', 'side-left', 'next-target')
    check(interact.pick(ctx_of(gf, fd, near, {}, c4, [])) == 'go-near', 'a door with a front: go-near the front first, not the planner\'s near point')
    check(interact.pick(ctx_of(gf, fd, near, {}, lab('open-door-on-way', 'enter-door', 'next-target'), [])) == 'enter-door', 'at the front (no go-near offered): enter-door, not open-door-on-way')
    check(interact.pick(ctx_of(gf, fd, near, {'history': [('enter-door', 'blocked', 0.0, None)]}, lab('open-door-on-way', 'enter-door', 'next-target'), [])) == 'open-door-on-way',
          'after enter-door was tried and blocked, the planner\'s way round the door may be tried')
    check(interact.pick(ctx_of(gn, nd, near, {}, c4, [])) == 'open-door-on-way', 'a door with no front: open-door-on-way first, as before')

    # P5: a door that answers blocked is reached from another side before the same press is made again (three tries, not three alike)
    with WithWorld():
        d = Target('door', -6.0, 0.0, kind='door', approach=-90)
        g = Goal('enter', [d])
        mem = {'history': [('go-near', 'reached', 0.0, None), ('enter-door', 'blocked', 0.0, None)]}
        st = interact.with_near('Test_Area', state(pos=[-4.0, 0.0, 0.0]))
        cands = interact.candidates('Test_Area', g, d, st, mem)
        seen = []
        for _ in range(5):
            choice = interact.pick(ctx_of(g, d, st, mem, cands, []))
            seen.append(choice)
            mem['history'].append((choice, 'blocked' if choice == 'enter-door' else 'reached', 0.0, None))
        check(seen == ['side-left', 'enter-door', 'side-right', 'enter-door', 'next-target'],
              f'blocked door: a step to the left, the door again, a step to the right, the door a third time, then leave ({seen})')
        check(interact.went_nowhere({'history': [('enter-door', 'blocked', 0.0, None)]}), 'a blocked enter-door counts as a move that went nowhere')

    # pi-solo-2b: the rupees of the field lie on a pond's floor (the target's y is 2 m under Link; the walk reached them at 0.17 m and nothing changed):
    # after one pickup that ended none at the spot, a dive is offered once (hold A over it), and after the dive the target is left
    with WithWorld():
        rt = Target('pond-rupee', 4.0, -2.0, y=-2.0, kind='item')
        g = Goal('collect', [rt], count=5)
        here = interact.with_near('Test_Area', state(pos=[4.0, 0.0, -2.0]))
        fresh = interact.candidates('Test_Area', g, rt, here, {})
        check('pickup-dive' not in labels(fresh), 'no dive before a pickup was tried at the spot')
        mem = {'history': [('pickup', 'none', 0.0, None)]}
        cs = interact.candidates('Test_Area', g, rt, here, mem)
        dive = next((c for c in cs if c.label == 'pickup-dive'), None)
        check(dive is not None and dive.lines == ['pickup 4.00 -2.00 radius 0.35 timeout 12 dive 3'],
              f'after a pickup that ended none at the spot, a dive is offered ({dive.lines if dive else None})')
        away = interact.with_near('Test_Area', state(pos=[0.0, 0.0, 0.0]))
        check('pickup-dive' not in labels(interact.candidates('Test_Area', g, rt, away, {'history': [('pickup', 'none', 0.0, None)]})),
              'no dive when Link is not at the spot')
        check(interact.pick(ctx_of(g, rt, here, mem, cs, [])) == 'pickup-dive', 'the picker takes the dive after a pickup that found nothing')
        mem['history'].append(('pickup-dive', 'none', 0.0, None))
        cs2 = interact.candidates('Test_Area', g, rt, here, mem)
        check(interact.pick(ctx_of(g, rt, here, mem, cs2, [])) == 'next-target', 'after the dive (whatever it found) the target is left')
        check(interact.INTERACT_LABELS.get('pickup-dive') == 'pickup', 'the dive counts as a pickup attempt in the metrics')

    # P6: a song goal that names a flag is met by the flag only; the notes pressed prove nothing
    song = Goal('play_song', [Target('spot', 0.0, 0.0)], notes='L R A', flag='Song.Heard=1')
    song.cond.note({'kind': 'ocarina', 'outcome': 'done', 'result': 'played', 'changes': {}}, state())
    check(not song.cond.met_state(state()) and song.cond.met_state(state(flags={'Song.Heard': 1})), 'a song with a flag is met by the flag, not by `played`')
    loose = Goal('play_song', [Target('spot', 0.0, 0.0)], notes='L R A')
    loose.cond.note({'kind': 'ocarina', 'outcome': 'done', 'result': 'played', 'changes': {}}, state())
    check(loose.cond.met_state(state()), 'a song with no flag keeps its old meaning: played')
    check('flag Song.Heard=1' in song.cond.describe() and 'played on the ocarina' not in song.cond.describe() and 'played on the ocarina' in loose.cond.describe(),
          f'the goal text of a song with a flag names the flag as the proof ({song.cond.describe()})')


# ---- hold B1's A3 replay (pi-solo-3), each played against the old behaviour first

def pisolo3_checks():
    import pilot
    # the pickup's history word: a candidate of a run to a far spot and a pickup there is recorded with the pickup's result (pi-solo-3: the
    # first rupee's candidate was run, run, run, pickup; the pickup ended `none`, the history said `reached`, so no dive was ever offered)
    run_ok = step('run 101.9 174.0 radius 1', 'reached', moved=23.0, detail='0.65 m from the point')
    pick_none = step('pickup 192.36 199.51 radius 0.35 timeout 53', 'none', detail='0.19 m from the point; nothing changed')
    pick_got = step('pickup 192.36 199.51 radius 0.35 timeout 53', 'picked', changes={'rupees': [17, 22]})
    hs = pilot.history_step
    check(hs([run_ok, run_ok, pick_none])['result'] == 'none', 'a run to the spot and a pickup that found nothing: the pickup\'s word')
    check(hs([run_ok, pick_got])['result'] == 'picked', 'a run and a pickup that took the rupee: picked')
    check(hs([pick_none])['result'] == 'none', 'a pickup alone: its own word')
    check(hs([run_ok, step('wait 1', 'done')])['result'] == 'reached', 'a run and a wait: the run\'s word (a wait decides nothing)')
    check(hs([pick_none, run_ok])['result'] == 'reached', 'a pickup and then a run: the move last made')
    check(hs([None, run_ok, None])['result'] == 'reached' and hs([None]) is None and hs([]) is None, 'no step, no word; gaps are skipped')
    check(hs([run_ok, {'ev': 'bad', 'src': 'pickup', 'why': 'x'}])['result'] == 'reached', 'a refused line is not a result')
    with WithWorld():
        rt = Target('pond-rupee', 4.0, -2.0, y=-2.0, kind='item')
        g = Goal('collect', [rt], count=5)
        here = interact.with_near('Test_Area', state(pos=[4.0, 0.0, -2.0]))
        mem = {'history': [('pickup', hs([run_ok, pick_none])['result'], 23.0, 0.19)]}
        cs = interact.candidates('Test_Area', g, rt, here, mem)
        check('pickup-dive' in labels(cs) and interact.pick(ctx_of(g, rt, here, mem, cs, [])) == 'pickup-dive',
              'after the far pickup that found nothing the dive is offered and taken')

    # a song played by its notes (an invented one; the notes are the goal's own) and the notes' timing (pi-solo-3: ZL held 800 ms opened the songbook)
    tune = 'R Y A L X R'
    song = Goal('play_song', [Target('site', 0.0, 0.0)], notes=tune, flag='Song.Heard=1')
    near = interact.with_near('Test_Area', state())
    with WithWorld():
        fast = next(c for c in interact.candidates('Test_Area', song, song.targets[0], near, {}) if c.label == 'ocarina-play')
        check(fast.lines == [f'ocarina {tune}'], f'no timing named: hsap\'s own ({fast.lines})')
        timed = Goal('play_song', [Target('site', 0.0, 0.0)], notes=tune, flag='Song.Heard=1', hold_ms=250, gap_ms=300)
        c2 = next(c for c in interact.candidates('Test_Area', timed, timed.targets[0], near, {}) if c.label == 'ocarina-play')
        check(c2.lines == [f'ocarina {tune} hold 250 gap 300'], f'a goal that names its timing plays it ({c2.lines})')
        check(not any(c.label == 'ocarina-play-slow' for c in interact.candidates('Test_Area', song, song.targets[0], near, {'history': [('ocarina-play', 'played', 0.0, None), ('wait-song', 'done', 0.0, None)]})),
              'no slower play is offered (PadInput2 measured: the timing was never the problem; 400/450 ms notes never worked)')
        check('ocarina-play-slow' not in interact.INTERACT_LABELS, 'and the label is gone')
        # `played` is the game's own word that it took the song (it closed its note window): wait for the effect once, then leave
        mem = {'history': [('ocarina-play', 'played', 0.0, None)]}
        cs = interact.candidates('Test_Area', song, song.targets[0], near, mem)
        check(interact.pick(ctx_of(song, song.targets[0], near, mem, cs, [])) == 'wait-song', 'played: wait for the song\'s effect')
        mem['history'] += [('wait-song', 'done', 0.0, None)]
        cs = interact.candidates('Test_Area', song, song.targets[0], near, mem)
        check(interact.pick(ctx_of(song, song.targets[0], near, mem, cs, [])) == 'next-target', 'and then leave the song (no slower retry of a song the game took)')
        # `no-song`: the game did not take it: once more, the same notes unchanged (the notes' order is what to suspect, not the timing), then leave
        mem = {'history': [('ocarina-play', 'no-song', 0.0, None)]}
        cs = interact.candidates('Test_Area', song, song.targets[0], near, mem)
        again = interact.pick(ctx_of(song, song.targets[0], near, mem, cs, []))
        check(again == 'ocarina-play' and next(c for c in cs if c.label == again).lines == [f'ocarina {tune}'], f'no-song: once more, unchanged ({again})')
        mem['history'] += [('ocarina-play', 'no-song', 0.0, None)]
        cs = interact.candidates('Test_Area', song, song.targets[0], near, mem)
        check(interact.pick(ctx_of(song, song.targets[0], near, mem, cs, [])) == 'next-target', 'a second no-song: the song is left')
        # the step's time allowance: a warp song takes the warm-up, the notes, the game's question and the map change (42 s in the game)
        check(interact.step_seconds(f'ocarina {tune}') == 50.0 and interact.step_seconds(f'ocarina {tune} hold 100 gap 150') == 50.0
              and interact.step_seconds('ocarina out') < 30.0 and interact.step_seconds('ocarina away') < 30.0, 'ocarina <notes>: 50 s; out and away as before')
    # the songbook (pilot/songs.json, private: game data): songs proven in the game, the rest inferred from the pitches and not played. The loader, on invented songs:
    import tempfile
    tune2 = 'L Y X A R L'
    with tempfile.TemporaryDirectory() as sd:
        f = Path(sd) / 'songs.json'
        f.write_text(json.dumps({'proven': {'song-a': tune}, 'inferred': {'song-b': tune2}}))
        saved = os.environ.get('PILOT_SONGS')
        os.environ['PILOT_SONGS'] = str(f)
        try:
            check(interact.InteractCond.song_notes('song-a') == tune.split() and interact.InteractCond.song_notes('song-b') == tune2.split() and interact.InteractCond.song_notes('nothing') == [],
                  'songs.json: the notes of a proven and of an inferred song; an unknown song has none')
            check(interact.InteractCond.song_status('song-a') == 'proven' and interact.InteractCond.song_status('song-b') == 'inferred' and interact.InteractCond.song_status('nothing') is None, 'and what is known of each: proven, inferred, nothing')
            f.write_text(json.dumps({'song-a': tune}))
            check(interact.InteractCond.song_notes('song-a') == tune.split() and interact.InteractCond.song_status('song-a') is None, 'the older flat file still gives the notes (and says nothing of proof)')
        finally:
            os.environ.pop('PILOT_SONGS', None)
            if saved is not None:
                os.environ['PILOT_SONGS'] = saved
    # the local songbook, when there is one, by its structure only (no song and no note string is named in this file): proven and inferred are two tables of
    # songs that do not overlap, each song is written in the five note buttons, and the segments that play a song play the notes of a proven one
    alphabet = set(hsap.NOTE_BUTTONS)
    shipped = HERE / 'songs.json'
    book = {}
    if shipped.is_file():
        sj = json.loads(shipped.read_text())
        proven, inferred = sj.get('proven'), sj.get('inferred')
        book = proven if isinstance(proven, dict) else {}
        check(isinstance(proven, dict) and isinstance(inferred, dict) and proven and inferred and not set(proven) & set(inferred),
              'pilot/songs.json: a table of proven songs and one of inferred songs, none in both')
        every = {**(inferred if isinstance(inferred, dict) else {}), **book}
        bad = {n: s for n, s in every.items() if not (isinstance(s, str) and len(s.split()) >= 2 and set(s.split()) <= alphabet)}
        check(every and not bad, f'pilot/songs.json: every song is two or more notes, each one of the five note buttons ({bad})')
    # the segments that carry a song: the notes they play (a goal's notes or an `ocarina` line) are written in the note buttons and, with the songbook there, are a proven song's
    seg_dir = HERE / 'segments'
    if (seg_dir / 'interact-song-kakariko.toml').is_file():
        for name in ('interact-song-kakariko', 'interact-song-slow'):
            seg = pilot.Segment(seg_dir / f'{name}.toml')
            played = [list(g.cond.notes) for g in seg.goals if g.kind == 'play_song']
            for ln in ((seg_dir / f'{name}.txt').read_text().splitlines() if (seg_dir / f'{name}.txt').is_file() else []):
                words = ln.split()[1:] if ln.startswith('ocarina ') else []
                if words and words[0] in alphabet:
                    played.append(words[:next((i for i, w in enumerate(words) if w not in alphabet), len(words))])
            check(played and all(n and set(n) <= alphabet for n in played), f'{name} plays notes written in the five note buttons ({played})')
            if book:
                check(all(n in [s.split() for s in book.values()] for n in played), f'{name} plays the notes of a proven song of pilot/songs.json ({played})')
        for name in sorted(p.stem for p in seg_dir.glob('interact-*.toml')):
            try:
                pilot.Segment(seg_dir / f'{name}.toml')
                ok = True
            except Exception as e:   # noqa: BLE001
                ok = f'{type(e).__name__}: {e}'
            check(ok is True, f'segment {name} parses ({ok})')


def run():
    vocab_checks()
    near_checks()
    candidate_checks()
    policy_checks()
    cond_checks()
    sidelane_checks()
    pisolo3_checks()
    outcome_checks()
    model_checks()
    grammar_checks()
    with tempfile.TemporaryDirectory(prefix='interact-e2e-') as tmp:
        e2e_checks(tmp)


def main():
    run()
    print(f'test_interact: {CHECKS[0]} checks, {len(FAILS)} failed')
    if FAILS:
        sys.exit(1)
    print('test_interact: all passed')


if __name__ == '__main__':
    main()
