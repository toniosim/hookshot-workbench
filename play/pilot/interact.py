"""Interaction goals of the playthrough pilot: do things in the world, not only walk through it.

Goal kinds (a segment's `[[goal]] kind = ...`; GOAL_KINDS): open_chest, both_open_same_chest (two players press A at the
same chest at one wall-clock instant: a `rendezvous` step), collect (n rupees or items), talk_to, enter (a door or load
zone), play_song (the ocarina's notes), fight (clear the enemies near a point), explore_interact (free play that prefers
interactions not yet tried). Each has candidates (candidates(), offered only when they make sense), a deterministic policy
(pick(), used by the `rules` decider and as the fallback of the model) and a condition (make_cond()) that is met by the
state, by a flag, or by what the interaction steps reported (hsap.py: chest, talk, advance, pickup, enter, ocarina, item,
ztarget, camera, faceat, rendezvous: their result word and `changes`).

What the pilot knows about what is in front of Link, and how sure it is (with_near()):
  * `prompt`: the game's own answer to "would A do something now", from the sampled state (sure). prompt_kind() sorts its
    words into open / talk / check / take / crawl / climb; the vocabulary is generic English verbs, plus whatever a private
    prompts.json (next to this file, or PILOT_PROMPTS) adds: the words the game really uses.
  * `near`: the objects of the offline world model (world/objects.json: chests, items, people, signs, doors, exits,
    enemies, ...) around Link with distance, bearing relative to his facing, height difference and `front` (the nearest one
    within 2.4 m and 55 degrees of his facing). A placement is exact for a fixed object (`sure: placed`), only the middle of
    a wander for a person (`wanders`), and not even there for a physics body or a dynamic spawn (`dynamic`). It knows nothing
    of enemies that spawn at run time (a night field's skeletons): the battle music (`battle`) and a drop in life say those.
    prompt + front together are the probe: `Open` with a chest in front is a chest to open, sure; `Open` with a door is a door.
Nothing in this module is game data: places, flags and names come from the segment and the (private) world model.
"""
import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import hsap  # noqa: E402  (where(): one copy of the word for a bearing)

GOAL_KINDS = ('open_chest', 'both_open_same_chest', 'collect', 'talk_to', 'enter', 'play_song', 'fight', 'explore_interact')
OUTCOMES = ('done', 'none', 'refused', 'timeout', 'cut')
INTERACT_STEPS = ('interact', 'chest', 'talk', 'advance', 'pickup', 'enter', 'ztarget', 'camera', 'faceat', 'ocarina', 'item',
                  'rendezvous', 'press', 'walk', 'run', 'until', 'raw', 'swing', 'shield', 'climb')
DECIDING = ('chest', 'talk', 'interact', 'pickup', 'enter', 'ocarina', 'item', 'ztarget', 'camera', 'advance')
INTERACT_LABELS = {
    # new (this module): label -> what kind of interaction it attempts
    'open-chest': 'chest', 'open-chest-force': 'chest', 'talk': 'talk', 'talk-force': 'talk', 'advance-text': 'text',
    'pickup': 'pickup', 'pickup-nearest': 'pickup', 'pickup-2': 'pickup', 'pickup-3': 'pickup', 'pickup-dive': 'pickup', 'enter-door': 'enter',
    'ocarina-play': 'ocarina', 'ocarina-out': 'ocarina', 'ocarina-away': 'ocarina', 'item-use': 'item', 'ztarget': 'target',
    'camera-sweep': 'camera', 'try-chest': 'chest', 'try-person': 'talk', 'try-sign': 'sign', 'try-item': 'pickup',
    'try-door': 'enter', 'try-stone': 'sign', 'try-item-use': 'item', 'try-ztarget': 'target', 'try-camera': 'camera',
    'try-ocarina': 'ocarina', 'approach-enemy': 'fight',
    # the older candidates of pilot.py that act on the world
    'press-a': 'interact', 'talk-until-goal': 'talk', 'press-a-through': 'text', 'talk-through': 'text',
    'push-open': 'door', 'open-door-on-way': 'door', 'crawl-in': 'crawl', 'crawl-on-way': 'crawl', 'climb-up': 'climb',
    'climb-on-way': 'climb', 'strike': 'fight', 'swing-x3': 'fight', 'guard': 'fight',
}
SUCCESS = ('opened', 'talked', 'picked', 'entered', 'closed', 'played', 'targeted', 'used', 'turned', 'done', 'met', 'reached',
           'out', 'away')
REFUSED = ('no-prompt', 'no-ocarina', 'alone', 'no-opponent', 'no-sample')
TIMEOUT = ('timeout', 'open', 'stuck', 'held')
TUNE = {
    'front_m': 2.4, 'front_deg': 55.0, 'front_dy_m': 1.6,   # the object `front` of Link: distance, cone, height
    'near_m': 10.0, 'near_limit': 8, 'enemy_m': 12.0,        # what `near` lists; an enemy this close counts as near
    'chest_ring_m': 1.0,                                      # where Link stands to open a chest: this far from its middle
    'face_deg': 25.0,                                         # `face-*` is offered when the target is more than this off
    'talk_m': 1.7, 'pick_radius': 0.35, 'low_life_frac': 0.3, 'max_rounds': 24,
}
PROMPT_WORDS = {   # generic English verbs of an action prompt; the real words of the game go into prompts.json
    'open': ('open',), 'talk': ('talk', 'speak', 'chat'), 'check': ('check', 'read', 'look', 'examine', 'inspect'),
    'take': ('take', 'have', 'grab', 'pick', 'get', 'lift'), 'crawl': ('crawl',), 'climb': ('climb',),
}
BATTLE_WORDS = ('battle', 'fight', 'enemy')   # in the name of the music


# ---- vocabulary: what the A prompt says

_vocab = {'loaded': False, 'words': {}}


def vocab():
    if not _vocab['loaded']:
        words = {k: list(v) for k, v in PROMPT_WORDS.items()}
        path = Path(os.environ.get('PILOT_PROMPTS') or HERE / 'prompts.json')
        try:
            extra = json.loads(path.read_text())   # {"<prompt text>": "open|talk|check|take|crawl|climb"}
            for text, kind in extra.items():
                if kind in words and isinstance(text, str):
                    words[kind].append(text.lower())
        except (OSError, ValueError, AttributeError):
            pass
        _vocab.update(loaded=True, words=words)
    return _vocab['words']


def prompt_kind(prompt):
    """open / talk / check / take / crawl / climb for an A prompt, 'other' for a word not known, None when A does nothing."""
    if prompt in hsap.EMPTY_PROMPTS:
        return None
    low = str(prompt).lower()
    for kind, words in vocab().items():
        if any(w == low or low.startswith(w) for w in words):
            return kind
    return 'other'


def battle_music(music):
    low = (music or '').lower()
    return not low.startswith('dm_') and any(w in low for w in BATTLE_WORDS)


# ---- the offline world model: what stands around Link

_world = {}


def world_dir():
    return Path(os.environ.get('PILOT_WORLD') or HERE.parent / 'world')


def objects_for(area):
    """The world model's objects of one area ([] without the model: nothing then is known about what is near)."""
    if 'all' not in _world:
        try:
            _world['all'] = json.loads((world_dir() / 'objects.json').read_text())
        except (OSError, ValueError):
            _world['all'] = {}
    return _world['all'].get(area) or []


NEAR_KINDS = ('chest', 'item', 'person', 'sign', 'stone', 'door', 'exit', 'warp', 'switch', 'crawl', 'shop', 'enemy', 'owl')


def certainty(obj):
    if any('physics' in m or 'IsPhysics' in m for m in obj.get('moves') or ()):
        return 'dynamic'
    if obj.get('moves'):
        return 'wanders'
    return 'placed' if obj.get('fixed', True) else 'dynamic'


def near_block(area, st, radius=None, limit=None):
    """{'objects': [...nearest first...], 'front': the one in front or None, 'enemies': how many enemies are within enemy_m,
    'battle': the music says enemies are about, 'prompt_kind'} for a state line; None without a position."""
    pos = st.get('pos')
    if not pos:
        return None
    radius, limit = radius or TUNE['near_m'], limit or TUNE['near_limit']
    facing = st.get('facing')
    out, enemies = [], 0
    for o in objects_for(area):
        if o.get('kind') not in NEAR_KINDS:
            continue
        p = o['pos']
        d = math.hypot(p[0] - pos[0], p[2] - pos[2])
        if o['kind'] == 'enemy' and d <= TUNE['enemy_m'] and abs(p[1] - pos[1]) < 6.0:
            enemies += 1
        if d > radius or abs(p[1] - pos[1]) > 6.0:
            continue
        bearing = math.degrees(math.atan2(p[0] - pos[0], p[2] - pos[2]))
        rel = hsap.wrap(bearing - facing) if facing is not None else None
        e = {'kind': o['kind'], 'name': o.get('gyaml'), 'x': p[0], 'z': p[2], 'dist': round(d, 2), 'bearing': round(bearing, 1),
             'rel_deg': None if rel is None else round(rel, 1), 'where': None if rel is None else hsap.where(rel),
             'dy': round(p[1] - pos[1], 2), 'sure': certainty(o)}
        if (o.get('flags') or {}).get('presence'):
            e['maybe'] = True   # it exists only while a flag has a value
        out.append(e)
    out.sort(key=lambda e: e['dist'])
    front = next((e for e in out if e['dist'] <= TUNE['front_m'] and e['rel_deg'] is not None and abs(e['rel_deg']) <= TUNE['front_deg']
                  and abs(e['dy']) <= TUNE['front_dy_m'] and e['kind'] != 'enemy'), None)
    return {'objects': out[:limit], 'front': front, 'enemies': enemies, 'battle': battle_music(st.get('music')),
            'prompt_kind': prompt_kind(st.get('prompt'))}


def is_interaction(goal):
    """An interaction goal of this module: one of GOAL_KINDS whose condition is an InteractCond (a `fight` goal that names a
    `flag` stays the older plain goal pilot.py always had, with its own candidates and policy)."""
    return getattr(goal, 'kind', None) in GOAL_KINDS and hasattr(getattr(goal, 'cond', None), 'met_state')


def with_near(area, st):
    """The state line with `near` added (a copy), for the decider and the candidates."""
    block = near_block(st.get('area') or area, st)   # (the map Link is in now: an enter goal ends in another one)
    if block is None:
        return st
    out = dict(st)
    out['near'] = block
    return out


# ---- what a decision looks at

@dataclass
class Candidate:
    label: str
    lines: list
    text: str


def unit(dx, dz):
    d = math.hypot(dx, dz)
    return (dx / d, dz / d) if d > 1e-3 else (0.0, 1.0)


class Facts:
    """The numbers every candidate builder and the policy read: Link, the target, the prompt, the text, the enemies."""

    def __init__(self, st, target, mem):
        self.st, self.target, self.mem = st, target, mem
        self.pos, self.facing = st.get('pos'), st.get('facing')
        self.prompt = st.get('prompt')
        self.pkind = prompt_kind(self.prompt)
        self.text = st.get('event') == 1 and not (st.get('music') or '').startswith('Dm_')
        self.scene = st.get('event') == 1 and (st.get('music') or '').startswith('Dm_')
        self.loading = st.get('loading') == 1
        self.near = st.get('near') or {}
        self.front = self.near.get('front')
        self.battle = bool(self.near.get('battle')) or battle_music(st.get('music'))
        self.enemies = self.near.get('enemies') or 0
        self.life, self.max_life = st.get('life'), st.get('max_life')
        self.dist = self.rel = self.bearing = None
        if self.pos and target is not None:
            self.dist = math.hypot(target.x - self.pos[0], target.z - self.pos[2])
            self.bearing = math.degrees(math.atan2(target.x - self.pos[0], target.z - self.pos[2]))
            if self.facing is not None:
                self.rel = hsap.wrap(self.bearing - self.facing)

    def facing_target(self, tolerance=None):
        return self.rel is not None and abs(self.rel) <= (tolerance or TUNE['face_deg'])


def history(mem):
    return mem.setdefault('history', [])


def count_label(mem, label):
    return sum(1 for e in history(mem) if e[0] == label)


def last_entry(mem):
    h = history(mem)
    return h[-1] if h else None


def absorb(mem):
    """The last decision's candidate stands for an object or a spot: what was tried on it is remembered (mem['tried'])."""
    h = history(mem)
    n = mem.get('absorbed', 0)
    for e in h[n:]:
        key = (mem.get('cand_keys') or {}).get(e[0])
        if key:
            mem.setdefault('tried', {})[key] = mem.setdefault('tried', {}).get(key, 0) + 1
    mem['absorbed'] = len(h)


def nav(area, st, gx, gz, gy, radius, plan, mem):
    """(lines, why) to the ground point: the planner's waypoints when it has a way, else the reachable point nearest it,
    else straight."""
    lx, ly, lz = st['pos']
    d = math.hypot(gx - lx, gz - lz)
    t = int(max(6, d / 3 + 5))
    if plan:
        try:
            r = plan(area, (lx, lz), (gx, gz), from_y=ly, to_y=gy, radius=radius, doors=mem.get('doors', 'stop'))
        except Exception as e:   # noqa: BLE001  the planner's failure must not end the run
            r = {'ok': False, 'why': f'planner error {type(e).__name__}'}
        steps = list(r.get('steps') or [])
        ob = []
        if OBSTACLE_HOOK is not None and not r.get('ok'):   # a jump, a ledge, an ivy, a door, a crawl hole on the way: actions.py's candidates
            ob = mem['obstacles'] = OBSTACLE_HOOK(area, st, r, steps)
        if r.get('ok') and steps:
            return steps, f"along {len(steps)} planned waypoints ({r.get('length', 0):.0f} m)"
        if r.get('near'):
            nx, nz = r['near']
            return steps or [f'run {nx:.2f} {nz:.2f} radius 1 timeout {int(max(6, math.hypot(nx - lx, nz - lz) / 3 + 5))}'], \
                f"to the reachable point nearest it (planner: {r.get('why')}" + (f"; the way ends at an obstacle that only the step {ob[0].label} crosses: walking at it again just ends stuck)" if ob else ')')
    return [f'run {gx:.2f} {gz:.2f} radius {radius:g} timeout {t}'], f'straight ({d:.1f} m)'


def ring_points(target, f, mem):
    """Four places 1 m from a chest's (or a person's) middle, the first where it opens from by the segment's `front`/`approach`
    or the way Link came; the others a quarter turn on: [(x, z, yaw_to_face)]. Pushing the chest's own orientation is not
    trusted (the model's rot may be a flipped Euler): the prompt tells which side opens, and next-side tries them in turn."""
    if 'ring_base' not in mem:
        if target.front:
            base = math.degrees(math.atan2(target.front[0] - target.x, target.front[1] - target.z))
        elif target.approach is not None:
            base = target.approach + 180.0
        elif f.pos:
            base = math.degrees(math.atan2(f.pos[0] - target.x, f.pos[2] - target.z))
        else:
            base = 0.0
        mem['ring_base'] = base
    r = TUNE['chest_ring_m']
    pts = []
    for k in range(4):
        a = math.radians(mem['ring_base'] + 90.0 * k)
        pts.append((target.x + r * math.sin(a), target.z + r * math.cos(a), math.degrees(a) + 180.0))
    if target.front and f.pos is not None:
        pts[0] = (target.front[0], target.front[1], pts[0][2])
    return pts


def walk_to(x, z, radius=0.35, timeout=8):
    return f'walk {x:.2f} {z:.2f} radius {radius:g} timeout {timeout}'


def back_off(f):
    fa = f.facing if f.facing is not None else 0.0
    x, z = f.pos[0] - 2.5 * math.sin(math.radians(fa)), f.pos[2] - 2.5 * math.cos(math.radians(fa))
    return Candidate('back-off', [walk_to(x, z, 0.5, 4)], 'step 2.5 m back, away from where Link faces')


def side_step(f, target, label):
    ux, uz = unit(target.x - f.pos[0], target.z - f.pos[2])
    s = 1 if label == 'side-left' else -1
    x, z = f.pos[0] + 3 * s * -uz, f.pos[2] + 3 * s * ux
    return Candidate(label, [walk_to(x, z, 0.5, 5)], f"step 3 m to the {label[5:]} of the way to {target.name}")


STRIKE = ['raw 0:ZL/1500,0.30:Y/100,0.75:Y/100,1.20:Y/100 1.8']   # lock on (hold ZL) and slash three times, as pilot.py does


def common_tail(f, goal, target, mem, out, stuck=False):
    """The candidates every kind ends with: leaving the target, giving up, and (after a move went nowhere) a step round."""
    if stuck and f.pos and target is not None:
        out.append(side_step(f, target, 'side-left'))
        out.append(side_step(f, target, 'side-right'))
    if f.pos:
        out.append(back_off(f))
    out.append(Candidate('next-target', [], f"leave {target.name}: it is done, or it failed{' (last target)' if mem.get('last') else ''}"))
    out.append(Candidate('give-up-goal', [], f'give up the goal {goal.name}'))


def went_nowhere(mem):
    e = last_entry(mem)
    return bool(e) and e[0] in ('go-near', 'go', 'approach-enemy', 'next-side', 'pickup', 'enter-door') and e[1] in ('stuck', 'timeout', 'cut', 'blocked')


def candidates(area, goal, target, st, mem, plan=None):
    """The step lists a decision chooses between for an interaction goal (at most 12): each only when it makes sense now."""
    area = st.get('area') or area
    absorb(mem)
    if not st.get('pos'):   # a load: no Link to act with
        return [Candidate('wait', ['wait 2'], 'wait two seconds: the game is loading'),
                Candidate('next-target', [], 'leave this target')]
    f = Facts(st, target, mem)
    if f.text or f.scene or f.loading:
        # a text box holds Link (A until it closes), a scene plays (no input), a load runs: nothing else makes sense
        out = []
        if f.text:
            out.append(Candidate('advance-text', ['advance timeout 25'], 'press A every 1.2 s until the text box closes and Link is free'))
        else:
            out.append(Candidate('wait', ['wait 3'], 'a scene plays or the game loads: wait 3 s without input'))
        return out
    mem.pop('obstacles', None)
    out = BUILDERS[goal.kind](area, goal, target, f, mem, plan)
    extra = [c for c in (mem.pop('obstacles', None) or []) if c.label not in {o.label for o in out}]
    if extra:   # the plan ends at a jump, a ledge, an ivy, a door, a crawl hole: its candidate comes right after the first (the walk there)
        out = out[:1] + extra[:1] + out[1:]
    return out[:12]


# ---- candidate builders, one per goal kind

def go_near(area, f, target, mem, plan, near_r, front=None, label='go-near'):
    gx, gz = front or (target.x, target.z)
    steps, why = nav(area, f.st, gx, gz, target.y, max(near_r, 0.4), plan, mem)
    lead = steps[:-1] if len(steps) > 1 else []
    d = math.hypot(gx - f.pos[0], gz - f.pos[2])
    return Candidate(label, lead + [walk_to(gx, gz, near_r, int(max(6, d / 3 + 5)) + 4)],
                     f"walk to {target.name} until within {near_r:g} m ({d:.1f} m away, {why})")


def chest_candidates(area, goal, target, f, mem, plan):
    out, pts = [], ring_points(target, f, mem)
    sides = max(1, min(4, int(goal.cond.g.get('sides', 4))))   # `sides = 1`: only the segment's front (a chest on a ledge has air on its other sides)
    k = count_label(mem, 'next-side') % sides      # the side Link is working: go-near leads to it, next-side to the one after
    sx, sz, _ = pts[k]
    nx, nz, _ = pts[(k + 1) % sides]
    ready = f.pkind == 'open' or bool(f.pkind and f.front and f.front['kind'] == 'chest')
    near = f.dist is not None and f.dist <= 2.6
    both = goal.kind == 'both_open_same_chest'
    meet = [f'rendezvous {goal.cond.rendezvous} timeout {goal.cond.wait_s:g}'] if both else []
    if ready:
        text = 'press A at the chest (its prompt is up), advance the message, and report what changed'
        if both:
            text = (f'wait until the other player is ready too ({goal.cond.wait_s:g} s at most), then both press A at the chest at '
                    f'one instant; advance the message; report what changed')
        out.append(Candidate('open-chest', meet + ['chest'], text))
    if f.dist is not None and f.dist > max(1.5, target.radius):
        out.append(go_near(area, f, target, mem, plan, 0.45, front=(sx, sz)))
    if near and not f.facing_target(15):
        out.append(Candidate('face-chest', [f'faceat {target.x:.2f} {target.z:.2f} 12'], 'turn on the spot until Link faces the chest'))
    if near and not ready:
        if f.facing_target(40) and f.dist is not None and f.dist > 0.9:
            out.append(Candidate('step-in', [walk_to(target.x, target.z, 0.2, 4)],
                                 'walk straight into the chest: it stops Link against it, where its Open prompt shows (earlier runs stopped at 0.84 m)'))
        if f.facing_target(40):
            out.append(Candidate('open-chest-force', meet + ['chest force'],
                                 'press A at the chest although the prompt is not up (it may read something else)'))
        if sides > 1:
            out.append(Candidate('next-side', [walk_to(nx, nz, 0.35, 8), f'faceat {target.x:.2f} {target.z:.2f} 12'],
                                 f'walk to the chest\'s next side (side {(k + 1) % sides + 1} of {sides}, 1 m from it) and face it: a chest opens from one side only'))
    common_tail(f, goal, target, mem, out, went_nowhere(mem) and sides > 1)
    return out


def collect_candidates(area, goal, target, f, mem, plan):
    out = []
    tried = mem.get('tried') or {}
    keys = {}
    spots = [(target.x, target.z, target.name, 'pickup')]
    near_items = [e for e in (f.near.get('objects') or []) if e['kind'] == 'item' and f'{e["x"]:.1f}:{e["z"]:.1f}' not in tried
                  and abs(e['x'] - target.x) + abs(e['z'] - target.z) > 0.5 and e['sure'] != 'dynamic'][:2]
    for i, e in enumerate(near_items):
        spots.append((e['x'], e['z'], f"the {e['name']} {e['dist']:.0f} m away", 'pickup-nearest' if i == 0 else 'pickup-%d' % (i + 2)))
    for x, z, name, label in spots:
        d = math.hypot(x - f.pos[0], z - f.pos[2])
        lead = []
        if d > 4.0:   # a far spot: the planner's way to it (a drop, a ramp, a bend), the last stretch by the pickup step itself
            steps, _ = nav(area, f.st, x, z, target.y if label == 'pickup' else None, 1.0, plan, mem)
            lead = steps[:-1] if len(steps) > 1 else []
        out.append(Candidate(label, lead + [f'pickup {x:.2f} {z:.2f} radius {TUNE["pick_radius"]:g} timeout {int(max(8, d / 2.5 + 8))}'],
                             f'walk onto {name} ({d:.1f} m away{", along the planned way" if lead else ""}) to pick it up, advance a message if one opens, report what changed'))
        keys[label] = f'{x:.1f}:{z:.1f}'
    mem['cand_keys'] = keys
    last = last_entry(mem)
    if last and last[0] in ('pickup', 'pickup-nearest', 'pickup-2', 'pickup-3') and last[1] == 'none' and f.dist is not None and f.dist <= 1.0:
        # (pi-solo-2b: the field's rupees lie on a pond's floor, Link swam over them at 0.17 m and nothing changed; the HUD said `Dive (Hold)` on A)
        out.append(Candidate('pickup-dive', [f'pickup {target.x:.2f} {target.z:.2f} radius {TUNE["pick_radius"]:g} timeout 12 dive 3'],
                             'the item is on the floor of the water under Link (Dive (Hold) on A): hold A over it for 3 s, report what changed'))
    if f.pkind in ('take', 'other') and f.dist is not None and f.dist < 2.5:
        out.append(Candidate('pickup-press', [f'pickup {target.x:.2f} {target.z:.2f} radius 0.6 timeout 10 press'],
                             'walk onto the spot and press A at its prompt (an item that is lifted or taken, not touched)'))
    common_tail(f, goal, target, mem, out, went_nowhere(mem))
    return out


def talk_candidates(area, goal, target, f, mem, plan):
    out = []
    near_r = max(TUNE['talk_m'], min(2.5, target.radius))
    if f.dist is not None and f.dist > near_r:
        out.append(go_near(area, f, target, mem, plan, near_r))
    close = f.dist is not None and f.dist <= 3.5
    if close and not f.facing_target():
        out.append(Candidate('face-person', [f'faceat {target.x:.2f} {target.z:.2f} 15'], 'turn on the spot until Link faces them'))
    if f.pkind in ('talk', 'check', 'other'):
        out.append(Candidate('talk', ['talk'], 'press A at the prompt, advance the text box until it closes, report what changed'))
    elif close and f.facing_target(40):
        out.append(Candidate('talk-force', ['talk force'], 'press A although the prompt is not up (the person may stand a little off)'))
    if close and f.pkind is None:
        out.append(Candidate('wait-for-person', ['wait 2'], 'wait 2 s: a person who wanders may come to Link'))
        x, z = target.x - 1.0 * math.sin(math.radians(f.bearing)), target.z - 1.0 * math.cos(math.radians(f.bearing))
        out.append(Candidate('step-in', [walk_to(x, z, 0.3, 4), f'faceat {target.x:.2f} {target.z:.2f} 15'], 'step to 1 m from them and face them'))
    common_tail(f, goal, target, mem, out, went_nowhere(mem))
    return out


def enter_candidates(area, goal, target, f, mem, plan):
    out = []
    ux, uz = unit(target.exit[0] - target.x, target.exit[1] - target.z) if target.exit else (
        math.sin(math.radians(target.approach)), math.cos(math.radians(target.approach))) if target.approach is not None else (
        unit(target.x - f.pos[0], target.z - f.pos[2]))
    gx, gz = target.front if target.front else (target.x - 2.0 * ux, target.z - 2.0 * uz)
    if f.dist is not None and f.dist > max(2.5, target.radius):
        out.append(go_near(area, f, target, mem, plan, 0.6, front=(gx, gz)))
    out.append(Candidate('enter-door', [f'enter {target.x:.2f} {target.z:.2f} through {target.x + 3 * ux:.2f} {target.z + 3 * uz:.2f} timeout 45'],
                         f'walk into {target.name}, press A at its prompt if it reads one, and go on through; ends entered when the map changed'))
    if f.pkind == 'open':
        out.append(Candidate('press-a', ['press A', 'wait 1.5'], 'press A once at the Open prompt, then wait'))
    out.append(Candidate('push', [walk_to(target.x + 1.0 * ux, target.z + 1.0 * uz, 0.2, 4)], f'walk into {target.name} (pushing against it)'))
    common_tail(f, goal, target, mem, out, went_nowhere(mem))
    return out


def song_candidates(area, goal, target, f, mem, plan):
    out = []
    notes = goal.cond.notes
    if target is not None and f.dist is not None and f.dist > max(2.0, target.radius):
        out.append(go_near(area, f, target, mem, plan, max(1.0, min(2.0, target.radius))))
    if notes:
        timing = (f' hold {goal.cond.hold_ms}' if goal.cond.hold_ms else '') + (f' gap {goal.cond.gap_ms}' if goal.cond.gap_ms else '')
        out.append(Candidate('ocarina-play', [f'ocarina {" ".join(notes)}{timing}'],
                             f'take the ocarina out (D-pad Left), play {" ".join(notes)} (the five note buttons), put it away; report what changed'))
        # (no slower retry: PadInput2 measured that the notes' timing is not what fails: 0.06 to 0.4 s notes, 0.15 to 0.8 s apart were all taken; a song the game did not take
        # (`no-song`) is tried once more unchanged by pick_song, then left: suspect the notes' order, which songs.json holds)
    out.append(Candidate('ocarina-out', ['ocarina out'], 'take the ocarina out and leave it waiting for a note'))
    out.append(Candidate('ocarina-away', ['ocarina away'], 'put the ocarina away'))
    out.append(Candidate('wait-song', ['wait 3'], 'wait 3 s for the song\'s effect'))
    common_tail(f, goal, target, mem, out, went_nowhere(mem))
    return out


def near_enemy(f):
    objs = [e for e in (f.near.get('objects') or []) if e['kind'] == 'enemy']
    return objs[0] if objs else None


def fight_candidates(area, goal, target, f, mem, plan):
    out = []
    hurt = mem.get('life_seen') is not None and f.life is not None and f.life < mem['life_seen']
    mem['life_seen'] = f.life if f.life is not None else mem.get('life_seen')
    if hurt:
        mem['hurt_at'] = len(history(mem))
    recent_hurt = mem.get('hurt_at') is not None and len(history(mem)) - mem['hurt_at'] <= 2
    if f.battle:
        mem['battle_seen'] = True
    # the placements still list a killed enemy: once the battle music has played and gone quiet, `enemies` alone no longer means a fight
    battle_over = bool(mem.get('battle_seen')) and not f.battle and not recent_hurt
    engaged = f.battle or recent_hurt or (f.enemies > 0 and not battle_over)
    low = f.life is not None and f.max_life and f.life <= max(2, TUNE['low_life_frac'] * f.max_life)
    if f.dist is not None and f.dist > max(3.0, target.radius):
        out.append(go_near(area, f, target, mem, plan, max(1.0, min(3.0, target.radius))))
    if engaged:
        out.append(Candidate('ztarget', ['ztarget 1200'], 'hold ZL for 1.2 s: lock on the nearest enemy and raise the shield'))
        out.append(Candidate('strike', STRIKE, 'lock on the nearest enemy (hold ZL for 1.5 s) and slash three times (Y)'))
        out.append(Candidate('swing-x3', ['swing', 'wait 0.4', 'swing', 'wait 0.4', 'swing', 'wait 0.5'],
                             'slash three times (Y) in the direction Link faces, 0.4 s apart'))
        out.append(Candidate('guard', ['shield 900'], 'hold the shield up (ZL) for 0.9 s'))
    e = near_enemy(f)
    if e and e['dist'] > 2.5 and not f.battle:
        out.append(Candidate('approach-enemy', [f'run {e["x"]:.2f} {e["z"]:.2f} radius 2 timeout {int(e["dist"] / 3 + 6)}'],
                             f"walk toward the {e['name']} {e['dist']:.0f} m away ({e['where']}); it is where the model placed it, and it may have moved"))
    out.append(Candidate('wait-a-moment', ['wait 2.5'], 'stand and wait 2.5 s (let the enemies come to Link)'))
    if low:
        mem['low_life'] = True
    common_tail(f, goal, target, mem, out, went_nowhere(mem))
    return out


TRY_KIND = {'chest': ('try-chest', 'chest'), 'person': ('try-person', 'talk'), 'sign': ('try-sign', 'talk'),
            'stone': ('try-stone', 'talk'), 'item': ('try-item', None), 'door': ('try-door', None), 'exit': ('try-door', None)}


def explore_candidates(area, goal, target, f, mem, plan):
    out, keys = [], {}
    tried = mem.get('tried') or {}
    objs = [e for e in (f.near.get('objects') or []) if e['kind'] in TRY_KIND and e.get('sure') != 'dynamic'
            and f'{e["kind"]}:{e["x"]:.0f}:{e["z"]:.0f}' not in tried]
    order = {'chest': 0, 'item': 1, 'person': 2, 'sign': 3, 'stone': 4, 'door': 5, 'exit': 5}
    objs.sort(key=lambda e: (order[e['kind']], e['dist']))
    for e in objs[:4]:
        label, verb = TRY_KIND[e['kind']]
        key = f'{e["kind"]}:{e["x"]:.0f}:{e["z"]:.0f}'
        if label in keys:
            continue
        keys[label] = key
        if e['kind'] == 'item':
            lines = [f'pickup {e["x"]:.2f} {e["z"]:.2f} radius 0.35 timeout {int(e["dist"] / 2.5 + 8)}']
        elif e['kind'] in ('door', 'exit'):
            lines = [f'enter {e["x"]:.2f} {e["z"]:.2f} timeout 40']
        else:
            steps, _ = nav(area, f.st, e['x'], e['z'], None, 1.5, plan, mem)
            lead = steps[:-1] if len(steps) > 1 else []
            lines = lead + [walk_to(e['x'], e['z'], 1.2, int(e['dist'] / 2 + 8)), f'faceat {e["x"]:.2f} {e["z"]:.2f} 15',
                            'chest' if e['kind'] == 'chest' else 'talk']
        out.append(Candidate(label, lines, f"{verb or 'go to'} the {e['kind']} {e['name']} {e['dist']:.0f} m away ({e['where']}), not tried yet"))
    for label, lines, text in (('try-ztarget', ['ztarget 1200'], 'hold ZL for 1.2 s (lock on, shield)'),
                               ('try-camera', ['camera right 700', 'camera left 700'], 'turn the camera with the right stick and back'),
                               ('try-ocarina', ['ocarina out', 'wait 1', 'ocarina away'], 'take the ocarina out and put it away'),
                               ('try-item-use', ['wait 1.5', 'item'], 'use the item on the item button (ZR) once (after a 1.5 s pause: Link may still be putting the ocarina away)')):
        if label not in tried:
            keys[label] = label
            out.append(Candidate(label, lines, text))
    mem['cand_keys'] = keys
    if f.dist is not None and f.dist > max(3.0, target.radius):
        out.append(go_near(area, f, target, mem, plan, max(1.5, target.radius), label='go'))
    common_tail(f, goal, target, mem, out, went_nowhere(mem))
    return out[:12]


BUILDERS = {'open_chest': chest_candidates, 'both_open_same_chest': chest_candidates, 'collect': collect_candidates,
            'talk_to': talk_candidates, 'enter': enter_candidates, 'play_song': song_candidates, 'fight': fight_candidates,
            'explore_interact': explore_candidates}


# ---- the deterministic policy (the `rules` decider; the model's fallback)

def pick(ctx):
    """One label of ctx.candidates for the goal's kind. Never loops on a step that did nothing: each tries a bounded number
    of times and then leaves the target (the pilot marks it failed)."""
    mem, goal, have = ctx.memory, ctx.goal, {c.label for c in ctx.candidates}
    absorb(mem)
    if 'advance-text' in have:
        return 'advance-text'
    if have <= {'wait', 'next-target'}:
        return 'wait' if 'wait' in have else 'next-target'
    for label in OBSTACLE_LABELS:   # the plan ends at a gap, a ledge, an ivy, a door, a crawl hole and has a candidate for it: a few tries of that before walking at it again
        if label == 'open-door-on-way' and goal.kind == 'enter' and getattr(ctx.target, 'front', None) and count_label(mem, 'enter-door') == 0:
            continue   # (the segment names the side the door opens from; the plan's near point is on the wrong side of it: go-near the front first, this only after enter-door was tried)
        if label in have and count_label(mem, label) < 3 and goal.kind != 'cross':
            return label
    return PICKERS[goal.kind](ctx, have, mem)


def pick_chest(ctx, have, mem):
    last = last_entry(mem)
    if last and last[0] in ('open-chest', 'open-chest-force') and last[1] == 'opened':
        mem['opened'] = True
    if mem.get('opened'):
        return 'next-target'
    if count_label(mem, 'open-chest') + count_label(mem, 'open-chest-force') >= 4 or count_label(mem, 'next-side') >= 6:
        return 'give-up-goal' if 'give-up-goal' in have else 'next-target'
    if 'open-chest' in have and not (last and last[0] == 'open-chest' and last[1] in ('timeout',)):
        return 'open-chest'
    if 'go-near' in have and not (last and last[0] == 'go-near' and last[1] in ('stuck', 'timeout', 'cut') and 'side-left' in have):
        return 'go-near'
    if last and last[0] == 'go-near' and last[1] in ('stuck', 'timeout', 'cut') and 'side-left' in have:
        return 'side-left'
    if 'face-chest' in have and not (last and last[0] == 'face-chest'):
        return 'face-chest'
    if 'step-in' in have and count_label(mem, 'step-in') <= count_label(mem, 'next-side'):
        return 'step-in'
    if 'open-chest-force' in have and not (last and last[0] in ('open-chest-force',)) and count_label(mem, 'open-chest-force') <= count_label(mem, 'next-side'):
        return 'open-chest-force'
    if 'next-side' in have:
        return 'next-side'
    return 'next-target'


def pick_collect(ctx, have, mem):
    last = last_entry(mem)
    if last and last[0] == 'pickup-dive':   # (the dive is tried once; what it found does not matter: leave the spot)
        return 'next-target'
    if 'pickup-dive' in have and last and last[0].startswith('pickup') and last[1] == 'none':
        return 'pickup-dive'
    if last and last[0].startswith('pickup') and last[1] in ('picked', 'none', 'stuck', 'timeout', 'held', 'cut'):
        if last[1] == 'picked' or count_label(mem, last[0]) >= 2:
            return 'next-target'
    if 'pickup' in have:
        return 'pickup'
    if 'pickup-press' in have:
        return 'pickup-press'
    return 'next-target'


def pick_talk(ctx, have, mem):
    last = last_entry(mem)
    if last and last[0] in ('talk', 'talk-force') and last[1] == 'talked':
        return 'next-target'
    if count_label(mem, 'talk') + count_label(mem, 'talk-force') >= 4:
        return 'next-target'
    if 'go-near' in have and not (last and last[0] == 'go-near' and last[1] in ('stuck', 'timeout', 'cut')):
        return 'go-near'
    if last and last[0] == 'go-near' and last[1] in ('stuck', 'timeout', 'cut'):
        return 'side-left' if 'side-left' in have and count_label(mem, 'side-left') < 2 else 'next-target'
    if 'face-person' in have and not (last and last[0] == 'face-person'):
        return 'face-person'
    if 'talk' in have:
        return 'talk'
    if 'talk-force' in have and not (last and last[0] == 'talk-force'):
        return 'talk-force'
    if 'step-in' in have and count_label(mem, 'step-in') < 2:
        return 'step-in'
    if 'wait-for-person' in have and count_label(mem, 'wait-for-person') < 3:
        return 'wait-for-person'
    return 'next-target'


def pick_enter(ctx, have, mem):
    last = last_entry(mem)
    if last and last[0] == 'enter-door' and last[1] in ('entered', 'opened'):
        return 'next-target'
    if count_label(mem, 'enter-door') >= 3:
        return 'next-target'
    if 'go-near' in have and not (last and last[0] == 'go-near' and last[1] in ('stuck', 'timeout', 'cut')):
        return 'go-near'
    if last and last[0] == 'enter-door' and last[1] == 'blocked':   # a door that stays shut: reach it from another side before trying again
        for label in ('side-left', 'side-right', 'push'):
            if label in have and count_label(mem, label) < 1:
                return label
    return 'enter-door' if 'enter-door' in have else 'next-target'


def pick_song(ctx, have, mem):
    last = last_entry(mem)
    plays = count_label(mem, 'ocarina-play')
    if last and last[0] == 'ocarina-play' and last[1] == 'played':   # (the game closed its note window itself: it took the song)
        return 'wait-song' if count_label(mem, 'wait-song') < plays else 'next-target'
    if last and last[0] == 'ocarina-play' and last[1] == 'no-ocarina':
        return 'next-target'
    if last and last[0] == 'wait-song' and plays:
        return 'next-target'
    if last and last[0] == 'ocarina-play' and last[1] == 'no-song' and plays < 2 and 'ocarina-play' in have:
        return 'ocarina-play'   # once more, the same notes unchanged (what to suspect is the notes' order, not the timing)
    if plays >= 2:
        return 'next-target'
    if 'go-near' in have and not (last and last[0] == 'go-near'):
        return 'go-near'
    return 'ocarina-play' if 'ocarina-play' in have else 'ocarina-out'


def pick_fight(ctx, have, mem):
    rounds = sum(1 for e in history(mem) if e[0] in ('strike', 'swing-x3', 'guard', 'ztarget', 'wait-a-moment', 'approach-enemy'))
    if rounds >= TUNE['max_rounds'] or (mem.get('low_life') and 'back-off' in have and count_label(mem, 'back-off') < 3):
        return 'back-off' if mem.get('low_life') and 'back-off' in have and count_label(mem, 'back-off') < 3 else 'next-target'
    last = last_entry(mem)
    if 'go-near' in have and not (last and last[0] == 'go-near'):
        return 'go-near'
    if 'strike' in have:
        order = ['ztarget', 'strike', 'swing-x3', 'strike', 'guard']
        return order[sum(1 for e in history(mem) if e[0] in order) % len(order)]
    if 'approach-enemy' in have and not (last and last[0] == 'approach-enemy'):
        return 'approach-enemy'
    return 'wait-a-moment'


def pick_explore(ctx, have, mem):
    for label in ('try-chest', 'try-item', 'try-person', 'try-sign', 'try-stone', 'try-door', 'try-ztarget', 'try-camera',
                  'try-ocarina', 'try-item-use'):   # (the item last: a lit bomb in Link's hands changes what the buttons do)
        if label in have:
            return label
    if 'go' in have and count_label(mem, 'go') < 6:
        return 'go'
    return 'next-target'


OBSTACLE_LABELS = ('open-door-on-way', 'jump-on-way', 'ledge-on-way', 'climb-on-way', 'climb-down-on-way', 'drop-on-way', 'crawl-on-way')   # (cross has its own picker)
OBSTACLE_HOOK = None   # actions.py sets it: (area, state, planner result, steps to `near`) -> [Candidate] for the obstacle the plan ends at
COND_CLASSES = {}      # goal kind -> condition class (default InteractCond): the kinds actions.py registers
STEP_SECONDS_HOOKS = []   # functions line -> seconds | None, asked after the steps of this module


def register_kind(kind, builder, picker, notes, cond_class=None, labels=None, success=(), deciding=()):
    """Add a goal kind (actions.py): candidate builder, rules picker, the model's paragraph, its condition class, the labels its
    candidates stand for ({label: interaction kind}), the result words that count as success and the steps whose result decides."""
    global GOAL_KINDS, SUCCESS, DECIDING
    if kind not in GOAL_KINDS:
        GOAL_KINDS = GOAL_KINDS + (kind,)
    BUILDERS[kind], PICKERS[kind], KIND_NOTES[kind] = builder, picker, notes
    if cond_class is not None:
        COND_CLASSES[kind] = cond_class
    INTERACT_LABELS.update(labels or {})
    SUCCESS = SUCCESS + tuple(w for w in success if w not in SUCCESS)
    DECIDING = DECIDING + tuple(w for w in deciding if w not in DECIDING)


PICKERS = {'open_chest': pick_chest, 'both_open_same_chest': pick_chest, 'collect': pick_collect, 'talk_to': pick_talk,
           'enter': pick_enter, 'play_song': pick_song, 'fight': pick_fight, 'explore_interact': pick_explore}


# ---- what a result means

def interaction_of(label, results, before=None, after=None):
    """{'kind', 'outcome', 'changes', 'detail', 'result'} for the result of a candidate, or None when the label is no
    interaction. outcome: done (the state changed as that interaction means it), none (sent, nothing changed), refused
    (nothing sent: no prompt, no ocarina), timeout (ran out its time, text still open, stuck, held), cut (the game ended).
    `results` are the step events of the candidate's lines."""
    kind = INTERACT_LABELS.get(label)
    if kind is None:
        return None
    steps = [r for r in (results or []) if r and r.get('ev') == 'step']
    deciding = next((r for r in reversed(steps) if (r.get('src') or '').split()[0] in DECIDING), None) or (steps[-1] if steps else None)
    if deciding is None:
        return {'kind': kind, 'outcome': 'cut', 'changes': {}, 'detail': 'no step answered', 'result': None}
    word = deciding.get('result')
    outcome = ('done' if word in SUCCESS else 'refused' if word in REFUSED else 'timeout' if word in TIMEOUT
               else 'cut' if word == 'cut' else 'none')
    changes = dict(deciding.get('changes') or {})
    for k in ('rupees', 'life', 'map'):   # a candidate of several steps: the whole run's difference
        if before and after and before.get(k) != after.get(k) and k not in changes:
            changes[k] = [before.get(k), after.get(k)]
    if outcome == 'done' and kind in ('chest', 'pickup', 'item') and not changes.get('text') and not any(
            k in changes for k in ('rupees', 'life', 'flags', 'hashes', 'prompt', 'map')) and (deciding.get('src') or '').split()[0] in DECIDING:
        outcome = 'none'
    return {'kind': kind, 'outcome': outcome, 'changes': changes, 'detail': (deciding.get('detail') or '')[:300], 'result': word}


def step_seconds(line):
    """The time allowance of an interaction step (None: not one of this module's)."""
    w = line.split()
    if not w:
        return None
    kw = {w[i]: w[i + 1] for i in range(1, len(w) - 1) if w[i] == 'timeout'}
    t = float(kw['timeout']) if 'timeout' in kw else None
    k = w[0]
    if k == 'interact':
        return (t or 14.0) + 6
    if k == 'chest':
        return (t or 30.0) + 6
    if k == 'talk':
        return (t or 45.0) + 6
    if k == 'advance':
        return (t or 20.0) + 6
    if k == 'pickup':
        return (t or 20.0) + 22
    if k == 'enter':
        return (t or 40.0) + 30
    if k == 'faceat':
        return 4.0
    if k == 'ztarget':
        return (float(w[1]) / 1000 if len(w) > 1 else 1.2) + 2
    if k == 'camera':
        return 14.0 if len(w) > 1 and w[1] == 'to' else (float(w[2]) / 1000 if len(w) > 2 else 0.4) + 1.5
    if k == 'ocarina':
        if len(w) > 1 and w[1] not in ('out', 'away'):
            return 50.0   # a song: the window's warm-up (3 s), the notes, and for a warp song the game's question and the map change (42 s in the game)
        return 12.0 + 0.6 * max(0, len(w) - 1) + 14.0
    if k == 'item':
        return 14.0
    if k == 'rendezvous':
        return (t or 120.0) + 4
    for hook in STEP_SECONDS_HOOKS:
        s = hook(line)
        if s is not None:
            return s
    return None


# ---- the goal conditions

class InteractCond:
    """A goal's condition (kind-specific): met by the state, a `flag` of the segment (optional), or what the interaction steps
    reported. Duck-types pilot.Cond for the places that read `.text`, `.name`, `.met(flags)`, adds `.watch` (flags to
    subscribe), `.observe(st)` (every new state), `.note(inter, st)` (after each candidate's result) and `.met_state(st)`."""

    def __init__(self, kind, g, targets, flag_cond=None):
        self.kind, self.g, self.targets, self.flag = kind, g, list(targets), flag_cond
        self.name, self.op, self.value = None, '=', None
        self.watch = [flag_cond.name] if flag_cond is not None and getattr(flag_cond, 'name', None) else []
        self.watch += [str(x) for x in g.get('watch', [])]
        self.start = {}                       # first values seen: rupees, map
        self.kinds_done = set()               # explore_interact: kinds of interaction that ended done
        self.done_near, self.last_inter = [], None
        self.battle_t0 = self.quiet_t0 = None
        self.fought = 0.0
        self.count = int(g.get('count', 1))
        self.min_kinds = int(g.get('min_kinds', 3))
        self.to_area = g.get('to')
        self.notes = [n for n in str(g.get('notes', '')).replace(',', ' ').split() if n] or self.song_notes(g.get('song'))
        self.hold_ms = int(g['hold_ms']) if g.get('hold_ms') else None   # the ocarina's note timing (hsap's own when not named)
        self.gap_ms = int(g['gap_ms']) if g.get('gap_ms') else None
        self.rendezvous = str(g.get('rendezvous', 'chest-1'))
        self.wait_s = float(g.get('wait_s', 150.0))
        self.quiet_s, self.min_battle_s = float(g.get('quiet_s', 8.0)), float(g.get('min_battle_s', 3.0))
        self.rounds = int(g['rounds']) if g.get('rounds') else None   # fight: met after this many fight rounds that ended done in a battle
        self.rounds_done = 0
        self.radius = float(g.get('radius', 30.0))
        self.near_m = float(g.get('near_m', 6.0))
        self.last_state = {}
        self.text = self.describe()

    @staticmethod
    def _songbook():
        try:
            return json.loads((Path(os.environ.get('PILOT_SONGS') or HERE / 'songs.json')).read_text())   # {"proven": {"<song>": "L R A ..."}, "inferred": {...}} (or flat)
        except (OSError, ValueError):
            return {}

    @staticmethod
    def song_notes(name):
        if not name:
            return []
        data = InteractCond._songbook()
        for table in (data.get('proven'), data.get('inferred'), data):
            if isinstance(table, dict) and isinstance(table.get(name), str):
                return table[name].split()
        return []

    @staticmethod
    def song_status(name):
        """'proven' (played in the game and taken), 'inferred' (from the pitches, not played), None (not in the songbook, or a flat file that says nothing of proof)."""
        data = InteractCond._songbook()
        for key in ('proven', 'inferred'):
            if isinstance(data.get(key), dict) and name in data[key]:
                return key
        return None

    def describe(self):
        bits = {'open_chest': 'the chest was opened (its flag, a rupee or item count that rose, or its message read to the end)',
                'both_open_same_chest': 'this player opened the shared chest',
                'collect': f'{self.count} more rupees or items than at the start',
                'talk_to': 'the person was talked to (their talked flag, or a message read to its end beside them)',
                'enter': 'the map changed' + (f' to {self.to_area}' if self.to_area else ''),
                'play_song': 'the song was played on the ocarina',
                'fight': f'the enemies near the place are done: the battle music has played for {self.min_battle_s:g} s and been quiet for {self.quiet_s:g} s',
                'explore_interact': f'{self.min_kinds} different kinds of interaction ended done'}[self.kind]
        if self.kind == 'play_song' and self.flag is not None:   # (the notes pressed prove nothing: only the game's own answer does)
            return f'the game heard the song: flag {self.flag.text}'
        return bits + (f" or flag {self.flag.text}" if self.flag is not None else '')

    def met(self, flags):
        return self.flag.met(flags) if self.flag is not None else False

    def observe(self, st):
        """Every new state: the baselines, and the battle clock of a fight goal."""
        self.last_state = st
        if st.get('rupees') is not None and 'rupees' not in self.start:
            self.start['rupees'] = st['rupees']
        if st.get('area') is not None and 'area' not in self.start:
            self.start['area'] = st['area']
        t = st.get('t')
        if self.kind == 'fight' and t is not None:
            if battle_music(st.get('music')):
                self.battle_t0 = self.battle_t0 if self.battle_t0 is not None else t
                self.quiet_t0 = None
                self.fought = max(self.fought, t - self.battle_t0)
            elif self.battle_t0 is not None and self.quiet_t0 is None:
                self.quiet_t0 = t

    def note(self, inter, st):
        """After a candidate's result: what the interaction steps reported (an `interaction` dict or None)."""
        prev = self.last_state
        self.observe(st)
        if not inter:
            return
        before = self.last_inter   # the interaction before this one
        self.last_inter = inter
        if inter['outcome'] == 'done':
            self.kinds_done.add(inter['kind'])
            pos = st.get('pos')
            if pos:
                self.done_near.append((inter['kind'], pos[0], pos[2], inter.get('result')))
                # A chest or a person whose own step ran out of time with the message still open (the game's texts take 20 to 40 s
                # at 30 frames a second) is finished by the advance-text that closes the message: that counts as opened / talked.
                if (inter['kind'] == 'text' and inter.get('result') == 'closed' and before and before['outcome'] == 'timeout'
                        and before['kind'] in ('chest', 'talk') and (before.get('changes') or {}).get('text') == 'open'):
                    self.kinds_done.add(before['kind'])
                    self.done_near.append((before['kind'], pos[0], pos[2], 'opened' if before['kind'] == 'chest' else 'talked'))
            if inter['kind'] == 'fight' and (battle_music(prev.get('music')) or battle_music(st.get('music'))):
                self.rounds_done += 1

    def near_target(self, st, kinds=None):
        pos = st.get('pos')
        return any(pos and math.hypot(pos[0] - t.x, pos[2] - t.z) <= max(self.near_m, t.radius) for t in self.targets)

    def met_state(self, st):
        flags = st.get('flags') or {}
        if self.flag is not None and self.flag.met(flags):
            return True
        k = self.kind
        if k in ('open_chest', 'both_open_same_chest'):
            return any(d[3] == 'opened' and self._near(d) for d in self.done_near)
        if k == 'collect':
            base = self.start.get('rupees')
            return base is not None and st.get('rupees') is not None and st['rupees'] - base >= self.count
        if k == 'talk_to':
            return any(d[3] == 'talked' and self._near(d) for d in self.done_near)
        if k == 'enter':
            area = st.get('area')
            if self.to_area:
                return area == self.to_area
            return self.start.get('area') is not None and area is not None and area != self.start['area'] and st.get('loading') == 0
        if k == 'play_song':   # (notes pressed prove nothing: with a flag named the game's own answer is the only proof)
            return self.flag is None and any(d[3] == 'played' for d in self.done_near)
        if k == 'fight':
            if self.rounds is not None and self.rounds_done >= self.rounds:
                return True
            t = st.get('t')
            return (self.quiet_t0 is not None and t is not None and self.fought >= self.min_battle_s and t - self.quiet_t0 >= self.quiet_s
                    and self.near_target(st))
        if k == 'explore_interact':
            return len(self.kinds_done) >= self.min_kinds
        return False

    def _near(self, d):
        return any(math.hypot(d[1] - t.x, d[2] - t.z) <= max(self.near_m, t.radius) for t in self.targets)


def make_cond(g, targets, flag_cond_class=None):
    """The condition of an interaction goal from its TOML table g (`flag` optional: parsed with pilot.Cond, passed in as
    flag_cond_class) and its Target list."""
    kind = g.get('kind')
    if kind not in GOAL_KINDS:
        raise ValueError(f'goal {g.get("name")}: kind {kind!r} is no interaction goal')
    flag = flag_cond_class(g['flag']) if g.get('flag') and flag_cond_class is not None else None
    return COND_CLASSES.get(kind, InteractCond)(kind, g, targets, flag)


KIND_NOTES = {   # one paragraph per goal kind in the model's request: the way through, in the candidates' own words
    'open_chest': 'go-near to the chest\'s front, make sure the Open prompt is up (face-chest; next-side when it is not), then open-chest; advance-text '
                  'when a message opens. Met when the chest is open.',
    'both_open_same_chest': 'as open_chest, but open-chest first waits for the other player and then presses A at the same moment as they do: never '
                            'open the chest by any other step before that. Met when this player opened it.',
    'collect': 'pick up the rupees or items one after the other: pickup walks onto the spot (the planner\'s way when it is far); a spot that gave nothing '
               'twice is left (next-target). Met when the count has risen enough.',
    'talk_to': 'go-near the person or sign, face them, talk at the Talk or Check prompt, advance-text until the box closes; a person who wanders '
               'may need wait-for-person or step-in when the prompt does not come. Met when the talk was read to its end beside them.',
    'enter': 'go-near the door\'s front, then enter-door: it presses A at an Open prompt and walks on through. Met when the map changes (or the '
             'door\'s flag is set).',
    'play_song': 'ocarina-play takes the ocarina out, plays the notes and puts it away; wait-song gives the song\'s effect a moment; no ocarina: leave '
                 'the target. Met when the song was played.',
    'fight': 'only when enemies are near (the battle music, or an enemy in near): ztarget (lock on), strike, swing-x3, guard when hurt; back-off when '
             'life is low. Met when the battle music has stopped for a few seconds near the place.',
    'explore_interact': 'try an interaction of a kind not tried yet (the try-* candidates, each once): chests, items, people, signs, doors first, then '
                        'lock-on, camera, ocarina, the item. Met when enough different kinds ended done.',
}


# ---- what the model is told (deciders.Decisions.interact_body builds the request from these)

INTERACT_DEVELOPER = (
    'You choose the next step of an automatic test pilot that plays a 3D action adventure game (a third-person game with a boy '
    'hero, Link) and is asked to DO things in the world: open a chest, pick up rupees, talk to a person, go through a door, play '
    'the ocarina, use an item, fight. Each step is a short list of inputs carried out in the game; it ends with a result word and '
    'what changed in the game state. Coordinates are metres on the ground (x, z); y is height; yaw angles are degrees (0 along '
    '+z, 90 along +x); rel_deg is where something is relative to the way Link faces, positive on his left. The state has: '
    '"prompt", what the A button would do right now as the game names it ("Empty" when nothing; Open, Talk, Check, Crawl and '
    'similar words are an action in front of Link: it is the game\'s own answer and certain); "text": true while a text box '
    'holds Link (only A, pressed every second or so, gets him out); "event"/"loading"; rupees, life (quarter hearts); '
    '"music" (a name starting Dm_ is a cutscene: give it no input; a name with Battle means enemies are about); '
    '"near": the objects of an offline map around Link (kind, name, dist, rel_deg, dy, sure: placed is exact, wanders means a '
    'person may be a few metres off, dynamic means unknown) and "front", the one directly ahead within 2.4 m. Where '
    'the prompt and front agree (prompt Open with a chest in front) that thing can be acted on now; offer the matching step. '
    'Rules of thumb that held in play: a chest opens only from its front, facing it, at its Open prompt: if A did nothing, step '
    'to another side of it and face it; a person talks only when the Talk prompt is up; a text box must be advanced to its end '
    'before anything else; a rupee is taken by walking onto it; a door opens at the Open prompt, then walk through; walking '
    'into a load zone or through a door changes the map; with an enemy near, lock on (ZL) and slash (Y), and step back when '
    'life is low; do not repeat an interaction that already ended done on the same thing. When the way to a place ends at an obstacle (a gap, a ledge, an ivy, a drop, a door, '
    'a crawl hole) the candidate named like jump-on-way, ledge-on-way, climb-on-way, drop-on-way, open-door-on-way or crawl-on-way is the step that crosses it (it walks to the '
    'edge itself): choose it rather than go-near again, which only ends stuck at the obstacle; after a jump that fell short try again with a run-up. "recent" lists the last steps with '
    'their result words and changes; "tried" counts what was tried on which object. Commit to the goal: choose the step that '
    'moves it forward, advance text first, and choose next-target only when the target is done or has failed several times.')


def model_data(ctx):
    """The data part of the model's request for an interaction goal: richer than the walking prompt's (the user wants the data
    over savings): the whole state with `near`, the goal with its condition and parameters, the target, the last results with
    their changes, what was tried where, how the goal has gone."""
    st, mem, goal, t = dict(ctx.state), ctx.memory, ctx.goal, ctx.target
    for k in ('ev', 'n', 'tick', 'in', 'world'):
        st.pop(k, None)
    link = st.get('pos')
    cond = goal.cond
    params = {k: v for k, v in getattr(cond, 'g', {}).items() if k in ('count', 'to', 'notes', 'song', 'min_kinds', 'quiet_s', 'sides',
                                                                         'rounds', 'rendezvous', 'radius', 'how', 'price', 'count_flag', 'direction', 'meters',
                                                                         'button', 'hold', 'fast', 'drop', 'rupees', 'dy')}
    return {
        'state': st,
        'goal': {'name': goal.name, 'what': goal.what, 'kind': goal.kind, 'how': KIND_NOTES.get(goal.kind), 'met_when': cond.text, 'parameters': params,
                 'progress': {'kinds_done': sorted(getattr(cond, 'kinds_done', ())), 'rupees_gained': (
                     (st.get('rupees') - cond.start['rupees']) if st.get('rupees') is not None and 'rupees' in getattr(cond, 'start', {}) else None)}},
        'target': {'name': t.name, 'kind': t.kind, 'x': round(t.x, 2), 'z': round(t.z, 2), 'radius': t.radius,
                   'distance_m': round(math.hypot(link[0] - t.x, link[2] - t.z), 2) if link else None},
        'tried_on_this_target': [{'step': e[0], 'result': e[1], 'moved_m': e[2]} for e in history(mem)[-10:]],
        'interactions': [{'kind': i['kind'], 'outcome': i['outcome'], 'result': i.get('result'), 'changes': i['changes'],
                          'detail': i['detail'][:160]} for i in (mem.get('interactions') or [])[-6:]],
        'tried': mem.get('tried') or {},
        'recent_steps': ctx.tried[-8:],
    }


import actions  # noqa: E402,F401  (registers the movement, shop, item, song and time goal kinds: actions.py)
