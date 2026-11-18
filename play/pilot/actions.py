"""The pilot's actions beyond walking, talking and opening (PilotSections): jump a gap, climb a ledge or an ivy, swim and dive, push and
pull a block, buy in a shop, use an item on a target, lock-on strafing, play a warp song, ride, wait for a time of day. Each is a goal kind
of interact.py's registry (register_kind at the end): candidates (offered only when they make sense), a rules policy, and a condition that is
met by STATE: a position, a height, a count, a flag, a map; a result word of the game side's step says what was tried, it is not the proof
(hsap_actions.py: `landed` says Link ended within a radius at a height, `dived` that the dive depth rose, `bought` that the rupees fell, ...).

What the state shows of each action [read; the first game runs of PilotSections are in reports/PilotSections.md]:
  jump / ledge / climb   Link's position and height (pos y): a landing is a place within a radius at a height
  swim / dive            the position, and a drop in y (the game's dive depth flag is a constant: it says how deep Link may go, not how deep he is)
  block                  Link's own move along the line while he holds the block (the block's place is not in the state); a flag when a puzzle names one
  buy                    the rupees fall by the price (and the item's own flag when the goal names one)
  use an item            the item's count (a watched counter flag) falls, or a flag the target sets
  strafe / circle        Link moves sideways while locked on and his facing stays or turns by the circle
  warp song              the map changes (and the game's arrival flag, a private setting)
  ride                   Link's ground speed over a second (a horse is far faster than a run)
  time of day            the brightness of the game's own picture (sections.py), the one thing here no flag tells
The data (note sequences of songs, the buttons, the arrival flag, the name of the song that turns day to night) is private: chapters/song_pitches.json beside this
file, or PILOT_SONG_PITCHES; nothing of the game is in this module. Without it a warp-song goal offers no song.
"""
import json
import math
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import interact  # noqa: E402
import recover  # noqa: E402
from interact import (Candidate, absorb, back_off, common_tail, count_label, go_near, history, last_entry, nav,  # noqa: E402
                      side_step, unit, walk_to, went_nowhere)

try:
    import hsap_actions  # noqa: E402  (the step allowances of the new verbs)
except ImportError:   # an older hsap: the kinds are registered, their steps have no allowance table
    hsap_actions = None

TUNE = {
    'edge_m': 0.9,            # Link counts as at the edge of a jump when this close to the planner's launch point
    'gap_run_up_m': 1.8,      # a gap wider than this wants a run-up
    'land_radius': 1.2, 'land_dy': 1.2,
    'strafe_ms': 1300, 'strafes_needed': 2, 'dive_ms': 1800, 'push_m': 2.0,
    'ride_fast_mps': 6.5, 'swim_m_per_s': 1.8,
}
NOTE_ORDERS = (('L', 'R', 'Y', 'X', 'A'), ('L', 'R', 'A', 'Y', 'X'))   # the two guesses at the five note buttons, lowest note first (hint bar; the host's rows)


# ---- songs: private note data, buttons by an order that can be corrected

def song_table():
    """{song: [pitch 1..5, ...]} from the private song_pitches.json (PILOT_SONG_PITCHES), {} without it. Keys starting `_` are settings:
    `_buttons` = the five note buttons from the lowest note to the highest."""
    try:
        data = json.loads(Path(os.environ.get('PILOT_SONG_PITCHES') or HERE / 'chapters' / 'song_pitches.json').read_text())
    except (OSError, ValueError):
        return {}
    out = {}
    for k, v in data.items():
        if k.startswith('_') or not isinstance(v, str):
            continue
        try:
            seq = [int(x) for x in v.split()]
        except ValueError:
            continue
        if seq and all(1 <= n <= 5 for n in seq):
            out[k] = seq
    return out


def note_orders():
    """The note-button orders to try, the confirmed one first: PILOT_NOTE_BUTTONS ('L R Y X A') or `_buttons` of the private file,
    then the two guesses."""
    first = None
    raw = os.environ.get('PILOT_NOTE_BUTTONS')
    if not raw:
        try:
            raw = ' '.join(json.loads(Path(os.environ.get('PILOT_SONG_PITCHES') or HERE / 'chapters' / 'song_pitches.json').read_text()).get('_buttons') or [])
        except (OSError, ValueError, AttributeError):
            raw = ''
    if raw and len(raw.split()) == 5 and sorted(raw.split()) == sorted(NOTE_ORDERS[0]):
        first = tuple(raw.split())
    return ([first] if first else []) + [o for o in NOTE_ORDERS if o != first]


def arrive_flag():
    """The flag the game sets when a warp song has taken Link somewhere (private: `_arrive_flag` of the song file, or PILOT_WARP_FLAG), or None."""
    if os.environ.get('PILOT_WARP_FLAG'):
        return os.environ['PILOT_WARP_FLAG']
    try:
        flag = json.loads(Path(os.environ.get('PILOT_SONG_PITCHES') or HERE / 'chapters' / 'song_pitches.json').read_text()).get('_arrive_flag')
    except (OSError, ValueError, AttributeError):
        return None
    return flag if isinstance(flag, str) and flag else None


def time_song():
    """The name of the song that moves the time of day (private: `_time_song` of the song file, or PILOT_TIME_SONG), or None: then a time wait only waits."""
    if os.environ.get('PILOT_TIME_SONG'):
        return os.environ['PILOT_TIME_SONG']
    try:
        name = json.loads(Path(os.environ.get('PILOT_SONG_PITCHES') or HERE / 'chapters' / 'song_pitches.json').read_text()).get('_time_song')
    except (OSError, ValueError, AttributeError):
        return None
    return name if isinstance(name, str) and name else None


def song_buttons(name, order):
    seq = song_table().get(name)
    return [order[n - 1] for n in seq] if seq else []


# ---- obstacles: what the planner's way ends at (interact.nav and pilot.make_candidates ask)

def blocking_link(r):
    """The link of r['needed'] the plan stopped at: the first one that is not allowed (the plan's own `near` is its start)."""
    near = r.get('near')
    for n in r.get('needed') or ():
        if n.get('allowed'):
            continue
        if near is None or math.hypot(n['from'][0] - near[0], n['from'][2] - near[1]) < 1.5:
            return n
    return next((n for n in (r.get('needed') or ()) if not n.get('allowed')), None)


def obstacle_candidates(area, st, r, steps):
    """Candidates for the obstacle the planner's way ends at: [] when it ends at none (the plan failed for another reason). The first
    steps are the walk to the obstacle's start (`steps`, the plan's waypoints to `near`), then the step that deals with it."""
    why, near, after = r.get('why'), r.get('near'), r.get('after')
    if not near or not after or why not in ('needs-jump', 'needs-climb', 'needs-drop', 'needs-door', 'needs-crawl'):
        return []
    lead = list(steps or [])
    link = blocking_link(r) or {}
    kind = r.get('edge') or link.get('kind') or ''
    ay = (link.get('to') or [0, None, 0])[1]
    yword = f' y {ay:.2f}' if ay is not None else ''
    ax, az = after
    height, gap = link.get('height') or 0.0, link.get('gap')
    where = f'({near[0]:.1f}, {near[1]:.1f}) to ({ax:.1f}, {az:.1f})'
    out = []
    if why == 'needs-jump' or kind == 'jump':
        gap = gap if gap is not None else math.hypot(ax - near[0], az - near[1])
        far = gap > TUNE['gap_run_up_m']
        radius = min(TUNE['land_radius'], max(0.4, round(gap / 2, 1)))   # (a radius as long as the gap counts a hop on the near side as landed)
        line = f'jump {ax:.2f} {az:.2f} radius {radius:g}{yword} hold {1200 if far else 800}' + (' lead 3' if far else '') + ' timeout 14'
        out.append(Candidate('jump-on-way', lead + [line],
                             f'go to the edge and jump the {gap:.1f} m gap, {where} (a jump step: X with the stick toward the far side'
                             f'{", after a 3 m run-up" if far else ""}); it ends landed when Link stands there at that height'))
    elif kind == 'ledge-up':
        out.append(Candidate('ledge-on-way', lead + [f'jump {ax:.2f} {az:.2f} radius 1.0{yword} hold 1800 timeout 14'],
                             f'go to the foot of the {abs(height):.1f} m ledge and jump onto it, {where} (X with the stick held on: the grab and pull-up); '
                             f'it ends landed when Link stands on top'))
    elif kind == 'climb-up':
        out.append(Candidate('climb-on-way', lead + ['climb up timeout 14'], f'go to the foot of the {abs(height):.1f} m ivy or ladder, {where}, and climb up'))
    elif kind == 'climb-down':
        out.append(Candidate('climb-down-on-way', lead + ['climb down timeout 14'], f'go to the top of the {abs(height):.1f} m ivy or ladder, {where}, and climb down'))
    elif why == 'needs-drop' or kind == 'drop':
        out.append(Candidate('drop-on-way', lead + [f'run {ax:.2f} {az:.2f} radius 1.5 timeout 10'],
                             f'walk off the ledge to drop {abs(height):.1f} m, {where}'))
    elif why == 'needs-door':
        out.append(Candidate('open-door-on-way', lead + [f'walk {ax:.2f} {az:.2f} radius 0.2 timeout 4', 'until flag 0x9824206c=Open timeout 6', 'press A', 'wait 1.5'],
                             'go to the door on the way, push against it and press A at its prompt'))
    elif why == 'needs-crawl':
        cx, cz = unit(ax - near[0], az - near[1])
        out.append(Candidate('crawl-on-way', lead + [f'walk {near[0] + cx:.2f} {near[1] + cz:.2f} radius 0.2 timeout 4', 'until flag 0x9824206c=Crawl timeout 3', 'press A', 'wait 1',
                                                      f'walk {ax + 1.5 * cx:.2f} {az + 1.5 * cz:.2f} radius 0.7 timeout 25'],
                             'go to the crawl hole on the way, into it, A at its Crawl prompt, and through to its far end'))
    return out


interact.OBSTACLE_HOOK = obstacle_candidates

# After a block (a walk that ended stuck), recover.py's ladder acts without a question; the candidates below are what Link can DO about a gap, a ledge, an ivy
# or a drop, so the first of them goes before the ladder's blind rungs (once per block), the way the eyes' own rungs do (recover.VISION_RUNGS)
OBSTACLE_RUNGS = ('jump-on-way', 'ledge-on-way', 'climb-on-way', 'climb-down-on-way', 'drop-on-way', 'jump-gap', 'jump-run-up', 'ledge-up', 'climb-here', 'climb-down')
recover.VISION_RUNGS = tuple(recover.VISION_RUNGS) + tuple(r for r in OBSTACLE_RUNGS if r not in recover.VISION_RUNGS)
if hsap_actions is not None:
    interact.STEP_SECONDS_HOOKS.append(hsap_actions.step_seconds)


# ---- the condition of the new kinds

PROOF_WORDS = {   # the result words of the game side's steps that say the action was done (the state still has to agree where the kind needs it)
    'cross': ('landed', 'climbed', 'swam'), 'dive': ('dived',), 'push_block': ('pushed', 'pulled'), 'buy': ('bought',),
    'use_item': ('used',), 'strafe': ('strafed', 'circled'), 'warp_song': (), 'ride': ('ridden',), 'read_sign': ('talked',),
}


class ActionCond(interact.InteractCond):
    """The condition of an action goal. Met by the goal's own `flag`, and by what the kind's proof is:
      cross       Link's place: within `radius` (the target's) of the target in x/z, within `dy` (default 2.0) of its height
      dive        a `dived` result near the target (the step reads the dive depth), a rise in rupees by `rupees`, or the flag
      push_block  a `pushed`/`pulled` result near the block (Link moved along the line), or the flag
      buy         the rupees fell by `price` from the most Link had (or the flag of the item)
      use_item    the count flag `count_flag` fell by `drop` (default 1) from its first value, or the flag; `proof = "result"`: a `used` result
      strafe      `count` (default 2) strafed or circled results
      warp_song   the map is `to` (and not loading), or the arrival flag (private: arrive_flag())
      ride        a `ridden` result
      read_sign   as talk_to
    Duck-types pilot.Cond for the places that read .text, .name, .met(flags), .watch."""

    def __init__(self, kind, g, targets, flag_cond=None):
        self.price = int(g.get('price', 0))
        self.drop = int(g.get('drop', 1))
        self.count_flag = g.get('count_flag')
        self.words = set(PROOF_WORDS.get(kind, ()))
        self.proof = g.get('proof', 'state')
        self.max_rupees = None
        self.first_count = None
        self.dy = float(g.get('dy', 2.0))
        self.strafes = 0
        super().__init__(kind, g, targets, flag_cond)
        if self.count_flag and self.count_flag not in self.watch:
            self.watch.append(self.count_flag)
        self.arrive = arrive_flag() if kind == 'warp_song' else None
        if self.arrive and self.arrive not in self.watch:
            self.watch.append(self.arrive)
        self.count = int(g.get('count', 2 if kind == 'strafe' else 1))
        self.to_area = g.get('to')
        self.text = self.describe()

    def describe(self):
        g, k = self.g, self.kind
        bits = {
            'cross': 'Link stands at the target (its place, and its height within %g m)' % float(g.get('dy', 2.0)),
            'dive': 'Link dived (he sank below the surface) near the spot' + (f", or {g['rupees']} more rupees" if g.get('rupees') else ''),
            'push_block': 'Link pushed or pulled the block (he moved along the line while holding it)',
            'buy': f"the rupees fell by {g.get('price', 'the price')} (the item was bought)",
            'use_item': f"the count {g.get('count_flag')} fell by {g.get('drop', 1)}" if g.get('count_flag') else 'the item was used (a result `used` with a change)',
            'strafe': f"Link circled or strafed under a lock-on {g.get('count', 2)} times",
            'warp_song': 'the map changed to ' + str(g.get('to') or 'where the song takes Link') + ' (the song warped him)',
            'ride': 'Link rode: his speed over a second was a horse\'s',
            'read_sign': 'the sign\'s text was read to its end beside it',
        }[k]
        if self.flag is not None:
            bits += f' or flag {self.flag.text}'
        return bits

    def observe(self, st):
        super().observe(st)
        if st.get('rupees') is not None:
            self.max_rupees = max(self.max_rupees or 0, st['rupees'])
        flags = st.get('flags') or {}
        if self.count_flag and isinstance(flags.get(self.count_flag), (int, float)) and self.first_count is None:
            self.first_count = flags[self.count_flag]

    def note(self, inter, st):
        super().note(inter, st)
        if inter and inter.get('outcome') == 'done' and inter.get('result') in ('strafed', 'circled'):
            self.strafes += 1

    def at_target(self, st):
        pos = st.get('pos')
        if not pos:
            return False
        for t in self.targets:
            if math.hypot(pos[0] - t.x, pos[2] - t.z) <= max(0.5, t.radius) and (t.y is None or abs(pos[1] - t.y) <= self.dy):
                return True
        return False

    def met_state(self, st):
        flags = st.get('flags') or {}
        if self.flag is not None and self.flag.met(flags):
            return True
        k = self.kind
        if k == 'cross':
            return self.at_target(st) and st.get('loading') != 1
        if k == 'warp_song':
            area = st.get('area')
            arrived = bool(self.arrive) and flags.get(self.arrive) in (1, True)
            if self.to_area:
                return area == self.to_area and st.get('loading') != 1 and (self.start.get('area') != area)
            return arrived and st.get('loading') != 1
        if k == 'buy':
            top, now = self.max_rupees, st.get('rupees')
            return bool(self.price) and top is not None and now is not None and top - now >= self.price
        if k == 'use_item':
            if self.count_flag:
                now = flags.get(self.count_flag)
                return self.first_count is not None and isinstance(now, (int, float)) and self.first_count - now >= self.drop
            return any(d[3] == 'used' for d in self.done_near)
        if k == 'strafe':
            return self.strafes >= self.count
        if k == 'dive':
            base = self.start.get('rupees')
            if self.g.get('rupees') and base is not None and st.get('rupees') is not None:
                return st['rupees'] - base >= int(self.g['rupees'])
            return any(d[3] == 'dived' and self._near(d) for d in self.done_near)
        if k in ('push_block', 'ride'):
            return any(d[3] in self.words and (k == 'ride' or self._near(d)) for d in self.done_near)
        if k == 'read_sign':
            return any(d[3] == 'talked' and self._near(d) for d in self.done_near)
        return False


# ---- candidates and policies

def tgt_y(target):
    return target.y if target.y is not None else None


def yarg(target):
    return f' y {target.y:.2f}' if target.y is not None else ''


def cross_candidates(area, goal, target, f, mem, plan):
    """Get to a place that may lie across a gap, up a ledge or an ivy, or over water."""
    out = []
    how = str(goal.cond.g.get('how', 'auto'))
    d = f.dist if f.dist is not None else 0.0
    dy = (target.y - f.pos[1]) if target.y is not None else 0.0
    out.append(go_near(area, f, target, mem, plan, max(0.8, min(target.radius, 2.0)), label='go'))
    if how in ('auto', 'jump') and 0.8 < d <= 9.0 and abs(dy) < 1.5:
        far = d > TUNE['gap_run_up_m'] + 0.5
        out.append(Candidate('jump-gap', [f'jump {target.x:.2f} {target.z:.2f} radius {TUNE["land_radius"]:g}{yarg(target)} hold {1200 if far else 800} timeout 14'],
                             f'jump straight toward {target.name} ({d:.1f} m away, X with the stick toward it); ends landed when Link stands there'))
        if far:
            out.append(Candidate('jump-run-up', [f'jump {target.x:.2f} {target.z:.2f} radius {TUNE["land_radius"]:g}{yarg(target)} hold 1200 lead 3 timeout 16'],
                                 'back off 3 m, run up and jump toward the target'))
    if how in ('auto', 'ledge', 'jump') and 0.4 <= dy <= 3.2 and d <= 6.0:
        out.append(Candidate('ledge-up', [f'jump {target.x:.2f} {target.z:.2f} radius 1.0{yarg(target)} hold 1800 timeout 14'],
                             f'jump up onto the ledge {dy:.1f} m above (X with the stick held on: grab and pull up); ends landed on top'))
    if how in ('auto', 'climb') and (f.pkind == 'climb' or dy > 1.0):
        out.append(Candidate('climb-here', ['climb up timeout 14'], 'hold up on the stick against an ivy or ladder while Link climbs'))
    if how in ('auto', 'climb') and dy < -1.5:
        out.append(Candidate('climb-down', ['climb down timeout 14'], 'hold down on the stick at the top of an ivy or ladder while Link climbs down'))
    stuck_here = bool(history(mem)) and history(mem)[-1][0] in ('go', 'go-near') and history(mem)[-1][1] in ('stuck', 'timeout')
    if how == 'swim' or (how == 'auto' and stuck_here):
        out.append(Candidate('swim-across', [f'swim {target.x:.2f} {target.z:.2f} radius {max(0.8, target.radius):g} timeout {int(d / TUNE["swim_m_per_s"] + 12)}'],
                             f'swim straight to {target.name} ({d:.1f} m): water is not on the map, so the planner cannot route it'))
    common_tail(f, goal, target, mem, out, went_nowhere(mem))
    return out


def pick_cross(ctx, have, mem):
    last = last_entry(mem)
    special = next((l for l in ('jump-on-way', 'ledge-on-way', 'climb-on-way', 'climb-down-on-way', 'drop-on-way', 'open-door-on-way', 'crawl-on-way') if l in have), None)
    tries = lambda l: count_label(mem, l)   # noqa: E731
    stuck = last and last[0] in ('go', 'go-near') and last[1] in ('stuck', 'timeout', 'cut', 'blocked')
    if special and tries(special) < 3 and not (last and last[0] == special and last[1] in ('short', 'fell', 'none')):
        return special
    if special and tries(special) == 1 and last and last[0] == special and last[1] in ('short', 'none') and 'jump-run-up' in have:
        return 'jump-run-up'
    if 'go' in have and not stuck and tries('go') < 6:
        return 'go'
    for label in ('jump-gap', 'ledge-up', 'climb-here', 'climb-down', 'swim-across', 'jump-run-up'):
        if label in have and tries(label) < 2:
            return label
    if stuck and 'side-left' in have and count_label(mem, 'side-left') < 2:
        return 'side-left'
    return 'next-target'


def dive_candidates(area, goal, target, f, mem, plan):
    out = []
    d = f.dist if f.dist is not None else 0.0
    if d > max(1.0, target.radius):
        out.append(Candidate('swim-to', [f'swim {target.x:.2f} {target.z:.2f} radius {max(0.8, target.radius):g} timeout {int(d / TUNE["swim_m_per_s"] + 14)}'],
                             f'swim to {target.name} ({d:.1f} m away; water is not on the map, so this is a straight swim)'))
        out.append(go_near(area, f, target, mem, plan, max(1.5, target.radius), label='go'))
    out.append(Candidate('dive', [f'dive {TUNE["dive_ms"]} timeout 12'], 'hold the dive button for 1.8 s while Link swims; ends dived when his height fell below the surface'))
    out.append(Candidate('dive-long', ['dive 3500 timeout 16'], 'hold the dive button 3.5 s (a deeper or longer dive)'))
    common_tail(f, goal, target, mem, out, went_nowhere(mem))
    return out


def pick_dive(ctx, have, mem):
    last = last_entry(mem)
    far = 'swim-to' in have and count_label(mem, 'swim-to') < 3 and not (last and last[0] == 'swim-to' and last[1] in ('stuck', 'timeout'))
    if far:
        return 'swim-to'
    n = count_label(mem, 'dive') + count_label(mem, 'dive-long')
    if n >= 4:
        return 'next-target'
    return 'dive' if count_label(mem, 'dive') <= count_label(mem, 'dive-long') else 'dive-long'


def block_candidates(area, goal, target, f, mem, plan):
    """Push or pull a block: stand at its front (the segment's `front`, or the side Link comes from), face it, hold A and push."""
    out = []
    m = float(goal.cond.g.get('meters', TUNE['push_m']))
    way = str(goal.cond.g.get('direction', 'push'))
    if f.dist is not None and f.dist > max(1.8, target.radius):
        out.append(go_near(area, f, target, mem, plan, 1.3, front=target.front))
    near = f.dist is not None and f.dist <= 3.0
    if near and not f.facing_target(20):
        out.append(Candidate('face-block', [f'faceat {target.x:.2f} {target.z:.2f} 12'], 'turn on the spot until Link faces the block'))
    if near:
        out.append(Candidate('block-push', [f'block push {m:g} timeout 12'], f'hold A to grab the block and push it {m:g} m (the stick toward it); ends pushed when Link moved along the line'))
        out.append(Candidate('block-pull', [f'block pull {m:g} timeout 12'], f'hold A to grab the block and pull it {m:g} m (the stick away from it); ends pulled when Link moved back'))
    common_tail(f, goal, target, mem, out, went_nowhere(mem))
    first = 'block-pull' if way == 'pull' else 'block-push'
    out.sort(key=lambda c: 0 if c.label == first else 1 if c.label.startswith('block') else 2)
    return out


def pick_block(ctx, have, mem):
    last = last_entry(mem)
    way = str(ctx.goal.cond.g.get('direction', 'push'))
    first, second = ('block-pull', 'block-push') if way == 'pull' else ('block-push', 'block-pull')
    if count_label(mem, 'block-push') + count_label(mem, 'block-pull') >= 4:
        return 'next-target'
    if 'go-near' in have and not (last and last[0] == 'go-near' and last[1] in ('stuck', 'timeout', 'cut')):
        return 'go-near'
    if 'face-block' in have and not (last and last[0] == 'face-block'):
        return 'face-block'
    if first in have and count_label(mem, first) < 2:
        return first
    if second in have and count_label(mem, second) < 1:
        return second
    return 'next-target'


def buy_candidates(area, goal, target, f, mem, plan):
    """A shelf item: walk to it, face it, buy; talk to the shopkeeper first when the shelf says nothing."""
    out = []
    price = int(goal.cond.g.get('price', 0))
    rupees = f.st.get('rupees')
    if f.dist is not None and f.dist > max(1.6, target.radius):
        out.append(go_near(area, f, target, mem, plan, max(1.0, min(1.6, target.radius))))
    close = f.dist is not None and f.dist <= 3.0
    if close and not f.facing_target(25):
        out.append(Candidate('face-item', [f'faceat {target.x:.2f} {target.z:.2f} 15'], 'turn on the spot until Link faces the item on the shelf'))
    poor = bool(price and rupees is not None and rupees < price)   # (too few rupees: nothing to buy with, so no buying is offered; the way out is)
    if f.pkind is not None and not poor:
        out.append(Candidate('buy', ['buy timeout 60'], 'press A at the item\'s prompt, read the message, answer the question with its first choice (yes), and report the rupees'))
        out.append(Candidate('buy-no-first', ['buy timeout 8', 'choose down', 'advance timeout 20'], 'buy, but move the cursor down to the second answer before confirming'))
    if close and f.pkind is None:
        out.append(Candidate('talk-keeper', ['talk timeout 60'], 'press A at whoever stands here (the shopkeeper) and read the text to its end'))
        out.append(Candidate('step-in', [walk_to(target.x, target.z, 0.5, 6), f'faceat {target.x:.2f} {target.z:.2f} 15'], 'step up to the item and face it'))
    common_tail(f, goal, target, mem, out, went_nowhere(mem))
    return out


def pick_buy(ctx, have, mem):
    last = last_entry(mem)
    if count_label(mem, 'buy') + count_label(mem, 'buy-no-first') >= 3:
        return 'next-target'
    price, rupees = ctx.goal.cond.price, ctx.state.get('rupees')
    if price and rupees is not None and rupees < price:
        return 'next-target'   # (too few rupees to buy with: leave the shelf, the rupees come first)
    if 'go-near' in have and not (last and last[0] == 'go-near' and last[1] in ('stuck', 'timeout', 'cut')):
        return 'go-near'
    if 'face-item' in have and not (last and last[0] == 'face-item'):
        return 'face-item'
    if 'buy' in have and count_label(mem, 'buy') < 2:
        return 'buy'
    if 'buy-no-first' in have and count_label(mem, 'buy-no-first') < 1:
        return 'buy-no-first'
    if 'talk-keeper' in have and count_label(mem, 'talk-keeper') < 2:
        return 'talk-keeper'
    if 'step-in' in have and count_label(mem, 'step-in') < 2:
        return 'step-in'
    return 'next-target'


def item_candidates(area, goal, target, f, mem, plan):
    """Use the item on the item button at a target: face it, lock on (ZL), press ZR, held for a bow or slingshot."""
    out = []
    g = goal.cond.g
    button = str(g.get('button', 'ZR'))
    hold = int(g.get('hold', 150))
    d = f.dist if f.dist is not None else 0.0
    if d > float(g.get('range', 12.0)):
        out.append(go_near(area, f, target, mem, plan, max(3.0, float(g.get('range', 12.0)) - 3.0)))
    at = f'at {target.x:.2f} {target.z:.2f}'
    out.append(Candidate('use-item', [f'use {button} {at} hold {hold}'], f'face the target and press the item button ({button}) once, {hold} ms'))
    out.append(Candidate('use-item-lock', [f'use {button} {at} lock hold {hold}'], 'face the target, lock on with ZL, and press the item button'))
    out.append(Candidate('use-item-aim', [f'use {button} {at} lock hold 700'], 'face the target, lock on, and hold the item button 0.7 s (aims a bow or a slingshot) before releasing'))
    if d > 2.0:
        out.append(Candidate('ztarget', ['ztarget 1200'], 'hold ZL 1.2 s: lock on the nearest target'))
    common_tail(f, goal, target, mem, out, went_nowhere(mem))
    return out


def pick_item(ctx, have, mem):
    last = last_entry(mem)
    n = sum(count_label(mem, l) for l in ('use-item', 'use-item-lock', 'use-item-aim'))
    if n >= 6:
        return 'next-target'
    if 'go-near' in have and not (last and last[0] == 'go-near') and count_label(mem, 'go-near') < 2:
        return 'go-near'
    for label in ('use-item', 'use-item-lock', 'use-item-aim'):
        if count_label(mem, label) < 2 and label in have:
            return label
    return 'next-target'


def strafe_candidates(area, goal, target, f, mem, plan):
    """Lock on and move sideways round a target (an enemy), guard, roll away."""
    out = []
    if f.dist is not None and f.dist > max(4.0, target.radius):
        out.append(go_near(area, f, target, mem, plan, max(2.5, min(4.0, target.radius))))
    out.append(Candidate('ztarget', ['ztarget 1200'], 'hold ZL for 1.2 s: lock on the nearest enemy and raise the shield'))
    ms = TUNE['strafe_ms']
    out.append(Candidate('strafe-left', [f'strafe left {ms}'], f'hold ZL and push the stick left for {ms} ms: Link moves round the locked target'))
    out.append(Candidate('strafe-right', [f'strafe right {ms}'], f'hold ZL and push the stick right for {ms} ms'))
    out.append(Candidate('guard', ['guard 900'], 'hold the shield up (ZL) for 0.9 s; ends guarded when his life did not drop'))
    if f.pos and f.facing is not None:
        out.append(Candidate('roll-away', [f'roll to {f.pos[0] - 4 * math.sin(math.radians(f.facing)):.2f} {f.pos[2] - 4 * math.cos(math.radians(f.facing)):.2f}'],
                             'roll backwards, away from where Link faces'))
    common_tail(f, goal, target, mem, out, went_nowhere(mem))
    return out


def pick_strafe(ctx, have, mem):
    last = last_entry(mem)
    n = sum(count_label(mem, l) for l in ('strafe-left', 'strafe-right'))
    if n >= 10:
        return 'next-target'
    if 'go-near' in have and not (last and last[0] == 'go-near' and last[1] in ('stuck', 'timeout', 'cut')) and count_label(mem, 'go-near') < 3:
        return 'go-near'
    if count_label(mem, 'ztarget') == 0 or (last and last[0] in ('strafe-left', 'strafe-right') and last[1] == 'none' and count_label(mem, 'ztarget') < 3):
        return 'ztarget'
    return 'strafe-left' if count_label(mem, 'strafe-left') <= count_label(mem, 'strafe-right') else 'strafe-right'


def warp_candidates(area, goal, target, f, mem, plan):
    """A song that warps: the ocarina out, the song's five-button sequence by the note order believed, put away; the other order after a miss."""
    out = []
    song = str(goal.cond.g.get('song', ''))
    orders = note_orders()
    tries = count_label(mem, 'song-warp') + count_label(mem, 'song-warp-alt')
    for label, order in (('song-warp', orders[tries % len(orders)]), ('song-warp-alt', orders[(tries + 1) % len(orders)])):
        notes = song_buttons(song, order)
        if notes:
            out.append(Candidate(label, [f'ocarina {" ".join(notes)}', 'wait 4'],
                                 f'take the ocarina out and play {song} as {" ".join(notes)} (note buttons lowest to highest {" ".join(order)}), put it away, and wait for the warp'))
    out.append(Candidate('ocarina-out', ['ocarina out'], 'take the ocarina out and leave it waiting for a note'))
    out.append(Candidate('ocarina-away', ['ocarina away'], 'put the ocarina away'))
    out.append(Candidate('wait-song', ['wait 4'], 'wait 4 s for the warp'))
    common_tail(f, goal, target, mem, out, went_nowhere(mem))
    return out


def pick_warp(ctx, have, mem):
    last = last_entry(mem)
    n = count_label(mem, 'song-warp') + count_label(mem, 'song-warp-alt')
    if last and last[0] in ('song-warp', 'song-warp-alt') and last[1] in ('no-ocarina',):
        return 'next-target'
    if n >= 4:
        return 'next-target'
    if last and last[0] in ('song-warp', 'song-warp-alt') and last[1] == 'played' and count_label(mem, 'wait-song') < n:
        return 'wait-song'
    if 'song-warp' in have:
        return 'song-warp'   # (its note order rotates by itself after each miss: warp_candidates)
    return 'next-target'


def ride_candidates(area, goal, target, f, mem, plan):
    """Call the horse with her song, get on her (A at her prompt), and ride to a place."""
    out = []
    g = goal.cond.g
    song = str(g.get('song', ''))
    notes = song_buttons(song, note_orders()[0]) if song else []
    fast = float(g.get('fast', TUNE['ride_fast_mps']))
    d = f.dist if f.dist is not None else 0.0
    if notes and count_label(mem, 'call-horse') < 2:
        out.append(Candidate('call-horse', [f'ocarina {" ".join(notes)}', 'wait 5'], f'play {song} ({" ".join(notes)}) to call the horse, and wait for her to come'))
    if f.pkind is not None:
        out.append(Candidate('mount', ['interact timeout 10', 'wait 1.5'], 'press A at the prompt to get on the horse'))
    out.append(Candidate('ride-to', [f'ride {target.x:.2f} {target.z:.2f} radius {max(2.0, target.radius):g} fast {fast:g} timeout {int(d / 4 + 14)}'],
                         f'run to {target.name} ({d:.1f} m): on a horse this is far faster than Link\'s own run; ends ridden when the speed shows it'))
    out.append(Candidate('wait-horse', ['wait 3'], 'wait 3 s for the horse'))
    common_tail(f, goal, target, mem, out, went_nowhere(mem))
    return out


def pick_ride(ctx, have, mem):
    last = last_entry(mem)
    if count_label(mem, 'ride-to') >= 4:
        return 'next-target'
    if 'call-horse' in have and count_label(mem, 'call-horse') == 0:
        return 'call-horse'
    if 'mount' in have and count_label(mem, 'mount') < 2 and not (last and last[0] == 'mount'):
        return 'mount'
    return 'ride-to' if not (last and last[0] == 'ride-to' and last[1] in ('stuck', 'timeout')) else 'next-target'


def sign_candidates(area, goal, target, f, mem, plan):
    """Read a sign or guide post: the Check prompt, the text read to its end."""
    out = []
    if f.dist is not None and f.dist > 1.7:
        out.append(go_near(area, f, target, mem, plan, 1.5, front=target.front))
    close = f.dist is not None and f.dist <= 3.5
    if close and not f.facing_target():
        out.append(Candidate('face-sign', [f'faceat {target.x:.2f} {target.z:.2f} 15'], 'turn on the spot until Link faces the sign'))
    if f.pkind in ('check', 'talk', 'other'):
        out.append(Candidate('read-sign', ['talk'], 'press A at its Check prompt and advance the text until the box closes'))
    elif close and f.facing_target(40):
        out.append(Candidate('read-sign-force', ['talk force'], 'press A although no prompt is up (the sign may stand a little off)'))
    common_tail(f, goal, target, mem, out, went_nowhere(mem))
    return out


def pick_sign(ctx, have, mem):
    last = last_entry(mem)
    if last and last[0] in ('read-sign', 'read-sign-force') and last[1] == 'talked':
        return 'next-target'
    if count_label(mem, 'read-sign') + count_label(mem, 'read-sign-force') >= 3:
        return 'next-target'
    if 'go-near' in have and not (last and last[0] == 'go-near' and last[1] in ('stuck', 'timeout', 'cut')):
        return 'go-near'
    if 'face-sign' in have and not (last and last[0] == 'face-sign'):
        return 'face-sign'
    if 'read-sign' in have:
        return 'read-sign'
    if 'read-sign-force' in have and not (last and last[0] == 'read-sign-force'):
        return 'read-sign-force'
    return 'next-target'


NOTES = {
    'cross': 'reach a place across an obstacle: the planner\'s way ends at a jump, a ledge, an ivy or a drop and its own candidate (jump-on-way, ledge-on-way, '
             'climb-on-way, drop-on-way) follows the first; swim-across for water. A jump ends landed only when Link stands at the place at its height; '
             'short or fell means try again from the edge, with a run-up. Met when Link stands at the target.',
    'dive': 'swim to the spot, then dive (hold the dive button): dive, dive-long. Met when Link sank below the surface near the spot, or the rupees rose by the count named.',
    'push_block': 'stand at the block\'s front, face it, hold A and push or pull it (block-push, block-pull). Met when Link moved along the line holding it (or a named flag).',
    'buy': 'walk to the shelf item, face it, buy: the message asks a question, answered with its first choice by buy; talk-keeper when the shelf is silent. Met when the rupees fell by the price. Not enough rupees: leave.',
    'use_item': 'face the target and press the item button (use-item; use-item-lock locks on first; use-item-aim holds the button to aim a bow or a slingshot). Met when the item\'s count fell or a named flag rose.',
    'strafe': 'lock on (ztarget) and move sideways round the target (strafe-left, strafe-right), guard, roll away when hurt. Met after the number of strafes named.',
    'warp_song': 'play the warp song: song-warp plays it by the note order believed, song-warp-alt by the other; put the ocarina away, wait. Met when the map changed to the place the song warps to.',
    'ride': 'call the horse with her song, mount at her prompt, ride to the target: ride-to ends ridden when Link\'s speed over a second was a horse\'s. Met on that.',
    'read_sign': 'go near the sign, face it, read-sign at its Check prompt; the text box is advanced until it closes. Met when the text was read to its end beside it.',
}

LABELS = {
    'jump-on-way': 'cross', 'ledge-on-way': 'cross', 'climb-down-on-way': 'cross', 'drop-on-way': 'cross', 'jump-gap': 'cross', 'jump-run-up': 'cross',
    'ledge-up': 'cross', 'climb-here': 'cross', 'climb-down': 'cross', 'swim-across': 'cross', 'swim-to': 'cross', 'dive': 'dive', 'dive-long': 'dive',
    'block-push': 'block', 'block-pull': 'block', 'buy': 'buy', 'buy-no-first': 'buy', 'talk-keeper': 'talk', 'use-item': 'item', 'use-item-lock': 'item',
    'use-item-aim': 'item', 'strafe-left': 'strafe', 'strafe-right': 'strafe', 'roll-away': 'roll', 'song-warp': 'ocarina', 'song-warp-alt': 'ocarina',
    'call-horse': 'ocarina', 'mount': 'interact', 'ride-to': 'ride', 'read-sign': 'talk', 'read-sign-force': 'talk',
}
RESULTS = ('landed', 'climbed', 'swam', 'dived', 'pushed', 'pulled', 'strafed', 'circled', 'guarded', 'rolled', 'bought', 'ridden')
STEPS = ('jump', 'swim', 'dive', 'block', 'strafe', 'guard', 'roll', 'use', 'buy', 'choose', 'ride')

for _kind, _build, _pick in (('cross', cross_candidates, pick_cross), ('dive', dive_candidates, pick_dive), ('push_block', block_candidates, pick_block),
                             ('buy', buy_candidates, pick_buy), ('use_item', item_candidates, pick_item), ('strafe', strafe_candidates, pick_strafe),
                             ('warp_song', warp_candidates, pick_warp), ('ride', ride_candidates, pick_ride), ('read_sign', sign_candidates, pick_sign)):
    interact.register_kind(_kind, _build, _pick, NOTES[_kind], cond_class=ActionCond, labels=LABELS, success=RESULTS, deciding=STEPS)
