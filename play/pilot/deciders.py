"""Deciders of the playthrough pilot: given one decision point (the state line, the current goal and target, what was
tried, the candidate steps), each picks one candidate's label. All behind one interface:

    decider.choose(ctx) -> Choice(label, predicates, info)

    rules             deterministic, no model: the control every model is compared with
    replay            the choices of an earlier run's transcript, in order (rules where they no longer fit)
    openai-decisions  OpenAI's Decisions API (POST /v1/decisions, gpt-6-luna): one choice question over the candidates and
                      three predicates in one request

The planner (Planner) is no decider: called seldom, it may reorder the goals and their targets (Responses API with a
JSON schema); with lessons on (lessons.py) its request carries the few most similar past failures and what finally worked.

drivers/ (PilotDrivers) puts these and more behind one interface with fallbacks: `drivers.chain.Chain` has this interface (name,
choose(ctx) -> Choice, stop_reason, min_gap_s), so the run loop is the same for a chain of drivers as for one decider; Choice.driver
says who made the choice and Choice.candidate a step the driver brought itself (a script, a recorded chunk, an agent's own steps).

A duel goal (kind "duel", pilot.py's duel_candidates) is decided by the same deciders: the rules have a fixed policy
(Rules.pick_duel: practice swing, Ready, close in to about 1.3 m, face him, swing about once a second, guard once when a new
swing of his has just been judged and he is close); the model gets its own prompt and a single choice question
(Decisions.duel_body), at most once in DUEL_MIN_GAP_S of game time, never when there is only one candidate. A duel goal may be
a series (matches = N): after a match that ended and matches remaining, Ready is offered again.
"""
import json
from dataclasses import dataclass, field

import interact
import lessons as lessons_lib
import openai_api

RECOVERY = ('back-off', 'side-left', 'side-right')
VISION_NOTE = ('state.vision, when present, is what a second model saw in the game picture a moment ago (front: what is ahead; '
               'door/chest/enemy/npc/stuck/text_box: 0..1 probabilities; age_s); trust it over the position when the two disagree '
               'about being blocked.')
DUEL_MIN_GAP_S = 1.5   # a duel goal: the model is asked at most once in this much game time (the pilot paces it)
DUEL = {                # the numbers (metres, degrees, seconds); the game's own swing lines say what it measured
    # The game's contact test (host/coop_pvp.c, authored defaults): reach 1.5 m (a child's sword) or 1.9 m (an adult's), a cone
    # of 60 degrees about the swinger's facing, 1.0 m of height. The pilot swings inside the child's reach and well inside the cone.
    'swing_range_m': 1.45, 'swing_facing_deg': 40.0, 'approach_m': 1.3,
    'face_deg': 25.0,     # `face` is offered when he is more than this off the front ...
    'face_to_deg': 12.0,  # ... and turns until within this (hsap's own tolerance is 20: a trigger below it would loop for ever)
    'threat_s': 1.2, 'close_m': 2.2,   # a swing of his that young, and him this close: guard once
    'ready_delay_s': 1.0,   # after Round ended or Match ended, Ready only once the state has lasted this long (see duel_candidates)
    # Leaving the arena interrupts the duel, which ends the run: a move that carries Link away (a roll, a sidestep) is offered only to
    # a place within leash_m of the arena's middle (the midpoint of both spawns, read at the countdown; unknown: no such move).
    'leash_m': 3.2, 'roll_m': 2.8, 'sidestep_ms': 350, 'sidestep_m_per_s': 4.5,
}


@dataclass
class Choice:
    label: str
    predicates: dict = field(default_factory=dict)
    info: dict = field(default_factory=dict)   # what goes into the transcript: request, answer, latency, usage, cost
    driver: str = None      # the driver that made it (drivers/): None for the plain deciders, which are their own name
    candidate: tuple = None  # (label, lines, text): a step the driver brings that the pilot did not offer (a script, a recorded chunk)


@dataclass
class Context:
    state: dict          # the last state line
    goal: object         # pilot.Goal
    target: object       # pilot.Target
    candidates: list     # [pilot.Candidate]
    memory: dict         # this target's record: 'history' [(label, result, moved)], counters
    tried: list          # the last steps of the whole run: [{label, goal, target, result, moved}]
    segment: object = None


def labels(ctx):
    return [c.label for c in ctx.candidates]


class Rules:
    """Works the current target by its kind, in a fixed order, and goes round an obstacle when a move ends stuck:
    back off, step aside left, try again, step aside right, try again; a target that failed five times is left."""
    name = 'rules'
    MAX_FAILS = 5

    def choose(self, ctx):
        return Choice(self.pick(ctx))

    def pick(self, ctx):
        if interact.is_interaction(ctx.goal):   # an interaction goal: its own policy (interact.py)
            return interact.pick(ctx)
        if getattr(ctx.goal, 'kind', None) == 'duel':
            return self.pick_duel(ctx)
        h = ctx.memory.setdefault('history', [])
        kind = ctx.target.kind
        last = h[-1] if h else None
        fails = ctx.memory.get('fails', 0)
        if fails >= self.MAX_FAILS:
            return 'next-target'
        have = set(labels(ctx))
        if ctx.state.get('scene') and 'wait-goal' in have:   # a scene plays its own music: no input until it ends
            return 'wait-goal'
        if 'talk-through' in have and not (last and last[0] == 'talk-through' and last[1] != 'met'):
            return 'talk-through'   # the tap says an event holds Link (a talk, a message): A until he is free
        for way in ('open-door-on-way', 'climb-on-way'):   # the planner found a door or a ladder on the way
            if way in have and not (last and last[0] == way):
                return way
        if last and last[0] in RECOVERY:   # after a step round the obstacle: the move again
            return 'go-near' if kind in ('door', 'talk', 'chest', 'crawl', 'fight') else 'go'
        # a move that ended short of its point; a go-near that stopped within a metre of it counts as arrived
        moved_badly = last and last[0] in ('go', 'go-near', 'push-through') and last[1] in ('stuck', 'timeout', 'cut') \
            and not (last[0] == 'go-near' and len(last) > 3 and last[3] is not None and last[3] < 1.0)
        if moved_badly and last[2] < 0.3 and len(h) >= 2 and h[-2][1] in ('stuck', 'timeout') and h[-2][2] < 0.3 and \
                'press-a-through' in have and not any(e[0] == 'press-a-through' for e in h[-4:]):
            return 'press-a-through'   # two moves in a row went nowhere: perhaps a talk or scene holds Link
        if moved_badly:
            n = ctx.memory.get('recoveries', 0)
            ctx.memory['recoveries'] = n + 1
            ctx.memory['fails'] = fails + 1
            return RECOVERY[n % 3]
        if kind == 'wait':   # a scene: at its place, wait; where it does not start, press A; then give up
            pos = ctx.state.get('pos')
            far = pos and ((pos[0] - ctx.target.x) ** 2 + (pos[2] - ctx.target.z) ** 2) ** 0.5 > ctx.target.radius
            if ctx.state.get('scene'):
                return 'wait-goal'
            if far and not any(e[0] == 'go' for e in h):
                return 'go'
            waits = sum(1 for e in h if e[0] == 'wait-goal')
            if not last or last[0] != 'wait-goal':
                return 'wait-goal'
            ctx.memory['fails'] = fails + 1
            return 'talk-until-goal' if waits < 3 else 'next-target'
        if kind in ('reach', 'item'):
            if last and last[0] == 'go' and last[1] == 'reached':
                if ctx.memory.get('last') and 'settle' in have and not any(e[0] == 'settle' for e in h):
                    return 'settle'   # the last target reached, the goal not yet: Link may still be dropping
                return 'next-target'
            if last and last[0] == 'settle':
                return 'next-target'
            return 'go'
        if kind == 'door':   # in front of it, walk into it and press A at its prompt; once open, through it
            if not last or last[0] in ('next-target',):
                return 'go-near'
            if last[0] == 'go-near':
                return 'push-open'
            if last[0] == 'push-open':
                ctx.memory['fails'] = fails + 1
                return 'push' if ctx.state.get('prompt') != 'Open' else 'press-a'
            if last[0] == 'push':
                return 'press-a' if ctx.state.get('prompt') == 'Open' else 'back-off'
            if last[0] == 'press-a':
                return 'push-through'
            if last[0] == 'push-through':
                return 'next-target'
            return 'go-near'
        if kind in ('talk', 'chest'):
            pos, prompt = ctx.state.get('pos'), ctx.state.get('prompt')
            close = pos and ((pos[0] - ctx.target.x) ** 2 + (pos[2] - ctx.target.z) ** 2) ** 0.5 <= ctx.target.radius
            offered = prompt not in (None, '', 'Empty') and not h   # the A prompt offers something already
            near = ctx.memory.get('near') or close or offered
            if not near and not (last and last[0] == 'go-near' and last[1] == 'reached'):
                return 'go-near'
            ctx.memory['near'] = True
            if not last or last[0] == 'go-near':
                return 'push' if kind == 'chest' else 'talk-until-goal'
            if last[0] == 'push':
                return 'talk-until-goal'
            if last[0] == 'talk-until-goal':
                ctx.memory['fails'] = fails + 1
                ctx.memory['near'] = False
                return 'back-off' if fails % 2 == 0 else 'next-target'
            return 'go-near'
        if kind == 'crawl':   # to the hole, in at its Crawl prompt and through; else push, A, on, as separate steps
            if not last or last[0] not in ('go-near', 'crawl-in', 'push', 'press-a', 'crawl-forward'):
                return 'go-near'
            nxt = {'go-near': 'crawl-in', 'crawl-in': 'next-target' if last[1] == 'reached' else 'push',
                   'push': 'press-a', 'press-a': 'crawl-forward', 'crawl-forward': 'next-target'}
            return nxt[last[0]]
        if kind == 'climb':
            if not last or last[0] != 'go-near':
                return 'go-near'
            return 'climb-up'
        if kind == 'fight':   # to the place, then strike and wait in turn; after eight rounds leave (no flag tells it is won)
            rounds = sum(1 for e in h if e[0] in ('strike', 'swing-x3', 'guard', 'wait-a-moment'))
            if rounds >= 8:
                return 'next-target'
            if not last:
                return 'go-near'
            return 'wait-a-moment' if last[0] == 'strike' else 'strike'
        return 'go'

    def pick_duel(self, ctx):
        """A fixed duel policy from the state line's duel and opponent blocks. Before a round (and between matches of a
        series): the practice swing once (the game reads its sword's power from it), then Ready (after a refused Ready one wait
        first; three refusals in a row: give up). Countdown: face him. Duel: guard once when a new swing of his has just been
        judged and he is close; else close in while he is out of reach, face him when he is off the front, and swing, about
        once a second. Any other state: wait."""
        have = set(labels(ctx))
        d, opp, mem = ctx.state.get('duel') or {}, ctx.state.get('opponent'), ctx.memory
        h = mem.setdefault('history', [])
        last = h[-1][0] if h else None
        state = d.get('state')
        if state in (None, 'Read terms', 'Round ended', 'Match ended'):
            if (d.get('refusal_run') or 0) >= 3 and 'give-up-goal' in have:
                return 'give-up-goal'
            if 'practice-swing' in have:
                return 'practice-swing'
            if 'ready' in have and not (last == 'ready' and d.get('refused')):
                return 'ready'
            return 'wait'
        if state == 'Countdown':
            return 'face' if 'face' in have else 'wait'
        if state != 'Duel' or opp is None or opp.get('distance_m') is None:
            return 'wait'
        swing = d.get('last_swing') or {}
        age = swing.get('age_s')
        if 'shield' in have and age is not None and age <= DUEL['threat_s'] and opp['distance_m'] <= DUEL['close_m'] and \
                swing.get('result') not in ('kit', 'capability', 'replay') and mem.get('guarded_swing') != swing.get('id'):
            mem['guarded_swing'] = swing.get('id')
            return 'shield'
        for want in ('approach', 'face', 'swing'):
            if want in have:
                return want
        return 'wait'


class Replay:
    """The choices of an earlier transcript, in order; where the recorded label is not among today's candidates, the
    rules choose and the divergence is noted."""
    name = 'replay'

    def __init__(self, transcript):
        self.queue = []
        for line in open(transcript):
            e = json.loads(line)
            if e.get('kind') == 'decision':
                self.queue.append(e['choice'])
        self.rules = Rules()

    def choose(self, ctx):
        if self.queue:
            want = self.queue.pop(0)
            if want in labels(ctx):
                return Choice(want, info={'replayed': True})
            c = self.rules.choose(ctx)
            c.info = {'replayed': False, 'recorded': want, 'why': 'not among the candidates'}
            return c
        c = self.rules.choose(ctx)
        c.info = {'replayed': False, 'why': 'the transcript has no more decisions'}
        return c


DEVELOPER = (
    'You choose the next step of an automatic test pilot that plays a 3D action adventure game (a third-person game '
    'with a boy hero, Link) toward a stated goal. Each step is carried out by an autopilot inside the game: it walks '
    'or runs Link in a straight line to a point and reports "reached", "stuck" (no progress for 3 seconds: something '
    'is in the way) or "timeout"; it presses buttons (A talks, opens doors, reads signs, picks up; holding A at a text '
    'box advances it); it waits until a game flag is set. Coordinates are metres on the ground plane (x, z); y is '
    'height. "facing" and "camera" are yaw angles in degrees (0 points along +z, 90 along +x). "prompt" is the action '
    'the A button would do now ("Empty" when none). "scene" is true while a cutscene plays its own music. The pilot '
    'works through an ordered list of goals; each goal has targets (places, doors, people, chests) worked in order. '
    'Commit to the current target: change only when it is reached, or when it clearly failed several times. When the '
    'last movement ended stuck, step back or aside before trying the same move again. Known behaviour: a door opens '
    'only while Link walks into it and the prompt reads "Open", then A; a talk or a tutorial scene can hold Link where '
    'he stands and goes on only with A pressed every two seconds (dozens of presses), which looks like being stuck '
    'without an obstacle; during a scene with its own music no input is needed; a target he cannot reach in a straight '
    'line may need the planned way, a crawl hole or a ladder. ' + VISION_NOTE)


DUEL_DEVELOPER = (
    'You choose the next move of an automatic test pilot that fights a sword duel against another player in a 3D action '
    'adventure game (a third-person game with a hero, Link, who has a sword and a shield). The goal text states the duel\'s '
    'rules: read it. Each move is a short action of one or two seconds and you are asked at most once in 1.5 seconds of game '
    'time; the game goes on while you decide. The data holds: "goal"; "link" (t is game seconds, pos x y z in metres, facing '
    'in degrees; 0 is along +z, 90 along +x); "duel", the game\'s own ledger (state: Read terms, Countdown, Duel, Finishing '
    'round, Round ended, Match ended; round; own_hearts and opp_hearts and own_score and opp_score, hearts in quarter-heart '
    'units; own_ready and opp_ready; "last_swing", the last swing of HIS that the game judged against you, with its result '
    '(hit, shielded, invulnerable, grace, range, facing, height, window) and its age in seconds; "swings", counts by result; '
    'matches_ended, matches_won, matches_lost); and "opponent" (distance_m on the ground, rel_deg his direction relative to '
    'where Link faces, positive when he is on Link\'s left, where, dy_m height difference, age_s how old that place is). '
    'Only hits win rounds, and nobody flinches when hit. Say Ready as soon as it is offered (after the one practice swing). In '
    'the duel: swing, about once a second, whenever he is in reach and in front of you; close in when he is out of reach; face '
    'him when he is off to the side; guard (shield) only right after a new swing of his, and briefly: it blocks nothing from '
    'behind and you cannot swing while it is up; roll or sidestep only to get out of his reach; waiting while he is in reach '
    'never wins. Commit to attacking.')


class Decisions:
    """OpenAI's Decisions API. One request per decision point: the choice among the candidates and four predicates.
    A decision that costs more than max_cost (USD) stops the model for the rest of the run (stop_reason says why; the
    pilot ends the run on it): at 0.10 USD a million input tokens a decision of this size costs about 0.0002."""
    name = 'openai-decisions'
    MAX_COST = 0.002

    def __init__(self, client, model=None, max_cost=MAX_COST):
        self.client = client
        self.model = model or openai_api.caps()['model']
        self.rules = Rules()
        self.max_cost = max_cost
        self.stop_reason, self.errors = None, 0
        self.last_error = None   # the exception of the last request that failed (the driver layer sorts failures by its type)
        self.min_gap_s, self.last_request_t = DUEL_MIN_GAP_S, None   # for a duel goal (the pilot waits it out)

    def body(self, ctx):
        st = dict(ctx.state)
        for k in ('ev', 'n', 'tick', 'in', 'world'):
            st.pop(k, None)
        t = ctx.target
        link = st.get('pos')
        data = {
            'state': st,
            'goal': {'name': ctx.goal.name, 'what': ctx.goal.what, 'met_when': ctx.goal.cond.text, 'kind': ctx.goal.kind},
            'target': {'name': t.name, 'kind': t.kind, 'x': round(t.x, 2), 'z': round(t.z, 2),
                       'distance_m': round(((link[0] - t.x) ** 2 + (link[2] - t.z) ** 2) ** 0.5, 2) if link else None},
            'tried_on_this_target': [{'step': e[0], 'result': e[1], 'moved_m': e[2]} for e in
                                     ctx.memory.get('history', [])[-8:]],
            'recent_steps': ctx.tried[-6:],
        }
        return {
            'model': self.model,
            'input': [
                {'role': 'developer', 'content': DEVELOPER},
                {'role': 'user', 'content': [
                    {'type': 'input_text', 'text': 'The game state at this decision point, the goal and what was tried:'},
                    {'type': 'input_json', 'data': data}]}],
            'questions': [
                {'type': 'choice', 'name': 'next_step',
                 'instructions': 'Which of these steps should the pilot take next to reach the current target and goal?',
                 'choices': [{'value': c.label, 'description': c.text} for c in ctx.candidates]},
                {'type': 'predicate', 'name': 'stuck',
                 'instructions': 'Is Link stuck against an obstacle: did the last movement end "stuck" or "timeout" '
                                 'having moved less than one metre?'},
                {'type': 'predicate', 'name': 'goal_met',
                 'instructions': 'Is the current goal already met according to the state?'},
                {'type': 'predicate', 'name': 'held_by_event',
                 'instructions': 'Is a talk, a text box or a scene holding Link where he stands (he did not move '
                                 'although the last steps asked him to, and nothing in the way is expected there)?'},
                {'type': 'predicate', 'name': 'give_up_target',
                 'instructions': 'Has the pilot tried the current target so often without progress that it should move '
                                 'on to the next target?'}],
            'prompt_cache_key': 'ls-pilot',
        }

    DUEL_LEDGER_KEYS = ('state', 'round', 'own_hearts', 'opp_hearts', 'own_score', 'opp_score', 'own_ready', 'opp_ready',
                        'in_state_s', 'last_swing', 'swings', 'refused', 'reason', 'matches_ended', 'matches_won', 'matches_lost')
    SWING_MODEL_KEYS = ('id', 'result', 'dist', 'amount', 'age_s')   # (his swing's other fields describe the game's measuring)

    def duel_body(self, ctx):
        """The duel goal's request: the goal's text (which states the rules; for a series a line says which match this is and
        how many were won and lost), Link, the duel ledger (the keys a decision needs, not the duplicates of them) and the
        opponent as the pilot's state line has them, the last moves, and one choice question over the candidates."""
        st = ctx.state
        duel = st.get('duel')
        what, n = ctx.goal.what, getattr(ctx.goal, 'matches', 1)
        if n > 1:
            d = duel or {}
            ended = d.get('matches_ended') or 0
            what += (f"\nmatch {min(ended + 1, n)} of {n}, matches won {d.get('matches_won') or 0} / "
                     f"lost {d.get('matches_lost') or 0} so far")
        shown = {k: duel.get(k) for k in self.DUEL_LEDGER_KEYS if k in duel} if duel else None
        if shown and isinstance(shown.get('last_swing'), dict):
            shown['last_swing'] = {k: shown['last_swing'].get(k) for k in self.SWING_MODEL_KEYS}
        data = {
            'goal': {'name': ctx.goal.name, 'what': what, 'met_when': ctx.goal.cond.text},
            'link': {k: st.get(k) for k in ('t', 'pos', 'facing')},
            'duel': shown,
            'opponent': st.get('opponent'),
            'recent_moves': [{'move': e[0], 'result': e[1]} for e in ctx.memory.get('history', [])[-6:]],
        }
        return {
            'model': self.model,
            'input': [
                {'role': 'developer', 'content': DUEL_DEVELOPER},
                {'role': 'user', 'content': [
                    {'type': 'input_text', 'text': 'The duel now, the opponent, the goal text with the rules, and the last moves:'},
                    {'type': 'input_json', 'data': data}]}],
            'questions': [
                {'type': 'choice', 'name': 'next_step',
                 'instructions': 'Which move should Link make next to win the duel?',
                 'choices': [{'value': c.label, 'description': c.text} for c in ctx.candidates]}],
            'prompt_cache_key': 'ls-pilot-duel',
        }

    def interact_body(self, ctx):
        """The request for an interaction goal (open a chest, talk, pick up, enter, play a song, fight, explore): the walking
        prompt's choice question and predicates, a developer text about the interaction steps, and richer data (the whole
        state with `near`, the last results with their changes, what was tried where, how the goal has gone)."""
        return {
            'model': self.model,
            'input': [
                {'role': 'developer', 'content': interact.INTERACT_DEVELOPER + ' ' + VISION_NOTE},
                {'role': 'user', 'content': [
                    {'type': 'input_text', 'text': 'The game state at this decision point, the goal, the target and what was tried:'},
                    {'type': 'input_json', 'data': interact.model_data(ctx)}]}],
            'questions': [
                {'type': 'choice', 'name': 'next_step',
                 'instructions': 'Which of these steps should the pilot take next to reach the current goal?',
                 'choices': [{'value': c.label, 'description': c.text} for c in ctx.candidates]},
                {'type': 'predicate', 'name': 'stuck',
                 'instructions': 'Is Link stuck against an obstacle: did the last movement end "stuck" or "timeout" '
                                 'having moved less than one metre?'},
                {'type': 'predicate', 'name': 'goal_met',
                 'instructions': 'Is the current goal already met according to the state?'},
                {'type': 'predicate', 'name': 'interaction_worked',
                 'instructions': 'Did the last interaction step change what the goal needs (a chest or text opened, a count rose, '
                                 'a map changed), judging by its result word and changes?'},
                {'type': 'predicate', 'name': 'held_by_event',
                 'instructions': 'Is a text box or a scene holding Link where he stands?'},
                {'type': 'predicate', 'name': 'give_up_target',
                 'instructions': 'Has the pilot tried the current target so often without progress that it should move '
                                 'on to the next target?'}],
            'prompt_cache_key': 'pilot-interact',
        }

    def request_for(self, ctx):
        """The request body of this decision point's kind: a duel goal's, an interaction goal's, or the walking prompt's."""
        duel = getattr(ctx.goal, 'kind', None) == 'duel'
        return self.duel_body(ctx) if duel else self.interact_body(ctx) if interact.is_interaction(ctx.goal) else self.body(ctx)

    def choose(self, ctx):
        duel = getattr(ctx.goal, 'kind', None) == 'duel'
        body = self.request_for(ctx)
        if self.stop_reason:   # no request after the model was stopped
            c = self.rules.choose(ctx)
            c.info = {'fallback': f'stopped: {self.stop_reason}'}
            return c
        if len(ctx.candidates) < 2:   # nothing to choose between (the API wants two choices at least): no request, no cost
            return Choice(ctx.candidates[0].label, info={'no_request': 'one candidate'})
        t = ctx.state.get('t')
        if duel and t is not None and self.last_request_t is not None and t - self.last_request_t < self.min_gap_s - 0.05:
            c = self.rules.choose(ctx)   # (the pilot paces a duel by min_gap_s: this is the guarantee behind that)
            c.info = {'throttled': f'{t - self.last_request_t:.2f} s of game time since the last request '
                                   f'(at most one in {self.min_gap_s:g} s)'}
            return c
        if duel:
            self.last_request_t = t
        est = len(json.dumps(body)) / 3.0 * 0.10 / 1e6
        try:
            ans, ms, row = self.client.post('/decisions', body, api='decisions', model=self.model, kind='decision',
                                            estimate=est)
        except (openai_api.NoKey, openai_api.CapReached, openai_api.ApiError) as e:
            self.errors += 1
            self.last_error = e
            if isinstance(e, openai_api.ApiError) and str(e).startswith('HTTP 4') and not str(e).startswith('HTTP 429') \
                    and self.errors >= 2:
                self.stop_reason = f'two requests in a row refused: {e}'[:300]
            if isinstance(e, openai_api.CapReached):
                self.stop_reason = f'cap: {e}'
            c = self.rules.choose(ctx)
            c.info = {'fallback': f'{type(e).__name__}: {e}', 'request': body}
            return c
        self.errors = 0
        got = {a.get('name'): a for a in ans.get('answers', [])}
        info = {'request': body, 'answers': ans.get('answers'), 'latency_ms': round(ms, 1), 'usage': row['usage'],
                'cost_usd': row['cost_usd']}
        if row['cost_usd'] is None or row['cost_usd'] > self.max_cost:
            self.stop_reason = (f"a decision cost {row['cost_usd']} USD, more than {self.max_cost} (usage "
                                f"{json.dumps(row['usage'])})")
        pick = got.get('next_step') or {}
        preds = {k: got[k].get('probability') for k in ('stuck', 'goal_met', 'held_by_event', 'give_up_target', 'interaction_worked')
                 if k in got and got[k].get('type') == 'predicate'}
        if pick.get('type') != 'choice' or pick.get('choice') not in labels(ctx):
            c = self.rules.choose(ctx)
            info['fallback'] = f"no usable choice ({pick.get('type')})"
            c.info, c.predicates = info, preds
            return c
        label = pick['choice']
        info['confidence'] = pick.get('confidence')
        if (preds.get('give_up_target') or 0) > 0.8 and label != 'next-target' and 'next-target' in labels(ctx) and \
                len(ctx.memory.get('history', [])) >= 4:
            info['override'] = f"give_up_target {preds['give_up_target']:.2f}: next-target instead of {label}"
            label = 'next-target'
        return Choice(label, preds, info)


PLANNER_DEVELOPER = (
    'You plan for an automatic test pilot that plays a 3D action adventure game. The pilot works through an ordered '
    'list of goals; each goal is proved by a game flag and has candidate targets (places, doors, people, chests, with '
    'ground coordinates x, z in metres) that the pilot visits in order, walking in straight lines, pressing A to talk, '
    'open or pick up. You get the segment, the goals with their state, and what the pilot tried and how each step '
    'ended. Return the goal order and the target order per goal that is most likely to succeed now, and the targets '
    'to drop as hopeless. Keep goals that are already met out of the order. Be brief in the reason.')


class Planner:
    """A stronger model through the Responses API with a JSON schema; its answer reorders goals and targets. `lessons` (a lessons.Lessons, set by pilot.cmd_run; None: off)
    puts the few most similar past failures and what finally worked into the request, with one more sentence in the developer text; off, and with no lesson to give, the
    request is the one it always was."""
    lessons = None

    def __init__(self, client, model=None):
        self.client = client
        self.model = model or openai_api.caps()['planner_model']

    def body(self, seg, goals, tried, lessons=None):
        gnames = [g.name for g in goals]
        tnames = sorted({t.name for g in goals for t in g.targets})
        schema = {
            'type': 'object', 'additionalProperties': False, 'required': ['order', 'targets', 'drop', 'reason'],
            'properties': {
                'order': {'type': 'array', 'items': {'type': 'string', 'enum': gnames}},
                'targets': {'type': 'array', 'items': {
                    'type': 'object', 'additionalProperties': False, 'required': ['goal', 'order'],
                    'properties': {'goal': {'type': 'string', 'enum': gnames},
                                   'order': {'type': 'array', 'items': {'type': 'string', 'enum': tnames}}}}},
                'drop': {'type': 'array', 'items': {'type': 'string', 'enum': tnames}},
                'reason': {'type': 'string'}}}
        data = {
            'segment': {'name': seg.name, 'what': seg.what, 'area': seg.area},
            'goals': [{'name': g.name, 'what': g.what, 'met_when': g.cond.text, 'state': g.status, 'kind': g.kind,
                       'targets': [{'name': t.name, 'kind': t.kind, 'x': round(t.x, 1), 'z': round(t.z, 1),
                                    'y': None if t.y is None else round(t.y, 1), 'state': t.status} for t in g.targets]}
                      for g in goals],
            'tried': tried[-60:],
        }
        developer = PLANNER_DEVELOPER
        if lessons:
            data['lessons'] = lessons
            developer = f'{PLANNER_DEVELOPER} {lessons_lib.NOTE}'
        return {
            'model': self.model,
            'input': [{'role': 'developer', 'content': developer},
                      {'role': 'user', 'content': json.dumps(data)}],
            'text': {'format': {'type': 'json_schema', 'name': 'plan', 'schema': schema, 'strict': True}},
            'max_output_tokens': 6000,
        }

    def plan(self, seg, goals, tried):
        got = self.lessons.for_goals(seg, goals, tried) if self.lessons is not None else None
        body = self.body(seg, goals, tried, got['items'] if got else None)
        est = len(json.dumps(body)) / 3.0 * 1.0 / 1e6 + 6000 * 5.0 / 1e6
        ans, ms, row = self.client.post('/responses', body, api='responses', model=self.model, kind='planner',
                                        estimate=est, timeout=120)
        text = ''
        for item in ans.get('output', []):
            if item.get('type') == 'message':
                for part in item.get('content', []):
                    if part.get('type') == 'output_text':
                        text += part.get('text', '')
        return json.loads(text), {'request': body, 'answer_text': text, 'latency_ms': round(ms, 1),
                                  'usage': row['usage'], 'cost_usd': row['cost_usd'],
                                  'lessons': lessons_lib.record(self.lessons is not None, got)}
