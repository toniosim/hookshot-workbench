#!/usr/bin/env python3
"""The story's steps as the game counts them, from its data: story.json in the data folder (paths.data_dir():
$PILOT_WORLD, else world/ beside worldmodel/). Game-derived, stays there.

    python3 story.py [--game <extracted RomFS folder>]    # needs flows.json (flows.py) and objects.json, gates.json,
                                                          # links.json (build.py) in the data folder

--game, else $WORLD_GAME. Needs the tables file (tables.py): the quest counter prefix, the quest categories and the
event query that tests a stack-program flag.

Sources, cited per entry:
- RSDB/Challenge.Product.111.rstbl.byml.zs: the quests ("challenges"): Category, the ordered Steps with
  IsBossBattle, IsMiniGame, Participants (an NPC and the AIScheduleParam it follows in that step),
  ForceProgressGameData (a flag whose setting moves the quest on), and per quest DependFlagName, RequestLocation,
  RequestActor.
- GameData/GameDataList.Product.110.byml.zs: the quest counter (the tables' quests.counter_prefix + the quest name;
  Enum; RawValues = not ready, ready, the steps, complete): the counter the game keeps per quest; the BoolExp flags
  of the story expressions that the flows, schedules and placements test.
- flows.json: which flow event advances which quest to which step (the actions of effect kind step), on which path of
  conditions, started by whom (an NPC's talk or approach under a schedule condition, a placed event or chest, an
  exit's first-time event).
- objects.json / links.json: where the starters stand (area, place), which placements name an event.
- gates.json: walls and people present under a flag, to say which gate a step opens.

Order: within a quest by its counter; between the main quests by what the data says one needs of another (a step
setter's path condition or its starter's schedule condition on another quest's counter, DependFlagName,
ForceProgressGameData, a flow that advances two quests at once); quests the data leaves unordered keep the table's
order and are marked so.
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from worldmodel import paths, tables  # noqa: E402


def load_mts():
    # the format readers with the whole RomFS folder's file list: game_files.py
    from worldmodel.game_files import load_mts as load
    return load()


class Exp:
    """Story conditions inside BoolExp flags: [(quest, op, step)] for the parts that compare a quest counter."""
    def __init__(self, g, mts, quests, T):
        self.g, self.mts = g, mts
        self.step_of = {mts.murmur(T.quests.counter_prefix + q): q for q in quests}
        self.cache = {}

    def parts(self, name, depth=0):
        if name in self.cache:
            return self.cache[name]
        h = self.mts.murmur(name) if isinstance(name, str) else name
        ent = self.g.flags.get(h)
        out = []
        if ent and ent[0] == 'BoolExp' and depth < 8:
            pend = None
            for item in ent[1].get('Values') or []:
                if len(item) == 1:
                    continue
                c, v = item
                if c in (1, 12, 11):
                    pend = (v, {1: '==', 12: '>=', 11: '<'}[c])
                elif c == 2 and pend:
                    q = self.step_of.get(pend[0])
                    if q:
                        raw = (self.g.flags.get(pend[0], (None, {}))[1] or {}).get('RawValues') or []
                        val = {self.mts.murmur(x): x for x in raw}.get(v)
                        out.append((q, pend[1], val))
                    pend = None
                elif c == 10:
                    out += self.parts(v, depth + 1)
        if isinstance(name, str):
            self.cache[name] = out
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--game', default=None, help='the extracted RomFS folder (else $WORLD_GAME)')
    a = ap.parse_args()
    game = paths.game_dir(a.game)
    try:
        T = tables.load()
    except tables.TablesError as e:
        sys.exit(f'worldmodel: {e}')
    Q, FL = T.quests, T.flows
    out_dir = paths.data_dir()
    missing = [n for n in ('flows.json', 'objects.json', 'gates.json', 'links.json') if not (out_dir / n).is_file()]
    if missing:
        sys.exit(f'worldmodel: story.py needs {", ".join(missing)} in {out_dir}: run build.py, then flows.py, first')
    mts = load_mts()
    g = mts.Game(game)
    table = mts.byml(g.romfs.load('RSDB/Challenge.Product.111.rstbl.byml.zs'))
    CAT = {mts.murmur(c): c for c in Q.categories}
    quests = {}
    for r in table:
        q = r['__RowId'].split('/')[-1].split('.')[0]
        quests[q] = r
    idx = json.loads((out_dir / 'flows.json').read_text())
    objects = json.loads((out_dir / 'objects.json').read_text())
    gates = json.loads((out_dir / 'gates.json').read_text())
    links = json.loads((out_dir / 'links.json').read_text())
    E = Exp(g, mts, quests, T)
    # the flow query that tests a stack-program flag, as its condition text names it: 'Query(flag)'
    bool_exp = FL.bool_exp_query.replace(FL.query_prefix, '')
    cond_re = re.compile(r'(NOT )?' + re.escape(bool_exp) + r'\((\S+)\)$')

    # where an actor stands and which placements name an event
    actor_at = collections.defaultdict(list)
    event_at = collections.defaultdict(list)
    for area, lst in objects.items():
        for o in lst:
            actor_at[o['gyaml']].append((area, o['pos']))
            for k, v in (o.get('params') or {}).items():
                if isinstance(v, str) and v:
                    event_at[v].append({'area': area, 'object': o['gyaml'], 'kind': o['kind'], 'pos': o['pos'], 'field': k,
                                        'src': o.get('src')})
            for k, v in ((o.get('flags') or {}).get('params') or {}).items():
                if isinstance(v, str) and v and not any(e['object'] == o['gyaml'] and e['field'] == k for e in event_at[v]):
                    event_at[v].append({'area': area, 'object': o['gyaml'], 'kind': o['kind'], 'pos': o['pos'], 'field': k,
                                        'src': o.get('src')})
    for lk in links:
        for k, v in (lk.get('events') or {}).items():
            if isinstance(v, str) and v:
                event_at[v.replace(T.flags.played_prefix, '')].append(
                    {'area': lk['from'], 'object': f"exit {lk['name']}", 'kind': 'exit', 'pos': lk.get('actor_pos'),
                     'field': k, 'src': (lk.get('evidence') or [''])[0]})

    def conds_story(texts):
        """Story requirements inside a list of condition texts: [(quest, op, step, negated, flag)]."""
        out = []
        for t in texts:
            m = cond_re.match(t)
            if m:
                for q, op, val in E.parts(m.group(2)):
                    out.append({'quest': q, 'op': op, 'step': val, 'negated': bool(m.group(1)), 'flag': m.group(2)})
        return out

    def starter_text(s):
        who = s['schedule']
        place = actor_at.get(who) or actor_at.get(Q.schedule_actor_re.sub(r'\2', who)) or []
        return {'how': s['how'], 'actor': who, 'distance': s.get('distance'),
                'when': (('NOT ' if s.get('negated') else '') + s['when']) if s.get('when') else None,
                'areas': sorted({p[0] for p in place})[:4], 'src': s['src']}

    def action_of(rec, starters, places, step_row):
        """What a machine must do, as far as the data says."""
        acts, unknown = [], []
        for s in starters:
            if s['how'] == 'talk':
                acts.append({'do': 'talk', 'to': s['actor'], 'areas': s['areas'], 'when': s['when']})
            else:
                acts.append({'do': 'go near', 'to': s['actor'], 'distance': s['distance'], 'areas': s['areas'],
                             'when': s['when']})
        for p in places:
            k = p['kind']
            if k == 'chest':
                acts.append({'do': 'open a chest', 'object': p['object'], 'area': p['area'], 'pos': p['pos']})
            elif k == 'exit':
                acts.append({'do': 'go through an exit', 'object': p['object'], 'area': p['area'], 'pos': p['pos'],
                             'field': p['field']})
            elif k in ('event', 'warp', 'switch', 'sign', 'person', 'item', 'enemy', 'door'):
                acts.append({'do': {'event': 'enter the place of an event trigger', 'warp': 'step onto a warp',
                                    'switch': 'work a switch', 'sign': 'read a sign', 'person': 'meet a person',
                                    'item': 'pick up an item', 'enemy': 'defeat an enemy', 'door': 'open a door'}[k],
                             'object': p['object'], 'area': p['area'], 'pos': p['pos'], 'field': p['field']})
            else:
                acts.append({'do': f'({k})', 'object': p['object'], 'area': p['area'], 'pos': p['pos'], 'field': p['field']})
        flow = rec['flow']
        if flow.startswith(Q.scene_flow_prefix) and not acts:
            acts.append({'do': 'watch a scene', 'scene': flow})
        if not acts:
            unknown.append(f"what starts {rec['flow']}:{rec['entry']} (events {', '.join(rec['events']) or 'none named'}; no "
                           'schedule, placement or exit in the data names them; a caller flow or a logic graph may)')
        if step_row:
            if step_row.get('IsBossBattle'):
                acts.append({'do': 'win a fight', 'boss': True})
            if step_row.get('IsMiniGame'):
                acts.append({'do': 'a timed or scored part (IsMiniGame)'})
        return acts, unknown

    out_quests = []
    order_edges = collections.defaultdict(set)     # quest -> quests it needs
    edge_src = collections.defaultdict(list)
    for q, r in quests.items():
        cat = CAT.get(r.get('Category'))
        counter = Q.counter_prefix + q
        steps_tbl = r.get('Steps') or []
        enum = (g.flags.get(mts.murmur(counter), (None, {}))[1] or {}).get('RawValues') or []
        setters = (idx.get('steps') or {}).get(q, {})
        steps = []
        for i, val in enumerate(enum):
            row = next((s for s in steps_tbl if s.get('Name') == val), None)
            recs = [x for x in setters.get(val, []) if x.get('op') == 'step']
            # one record per setting event, the entries something starts first
            seen, chosen = set(), []
            for x in sorted(recs, key=lambda x: (not x['events'], len(x['when'][0]) if x['when'] else 0)):
                if x['at'] in seen:
                    continue
                seen.add(x['at'])
                chosen.append(x)
            set_by = []
            reqs = []
            acts_all, unk_all = [], []
            for x in chosen[:6]:
                st = [starter_text(s) for ev in x['events'] for s in (idx.get('starters') or {}).get(ev, [])]
                places = [p for ev in x['events'] for p in event_at.get(ev, [])][:6]
                if not places and x['entry'] in event_at:
                    places = event_at[x['entry']][:6]
                if not places and not st:
                    places = event_at.get(x['flow'], [])[:6]
                acts, unk = action_of(x, st, places, row)
                acts_all += acts
                unk_all += unk
                cs = conds_story(x['when'][0] if x['when'] else [])
                for s in st:
                    if s['when']:
                        cs += conds_story([('NOT ' if s['when'].startswith('NOT ') else '') + bool_exp + '('
                                           + s['when'].replace('NOT ', '') + ')'])
                reqs += cs
                set_by.append({'flow': x['flow'], 'entry': x['entry'], 'event': x['at'], 'events': x['events'],
                               'conditions': x['when'][:2], 'started_by': st, 'placed': places, 'src': x['src']})
            for c in reqs:
                if c['quest'] != q and not c['negated']:
                    order_edges[q].add(c['quest'])
                    edge_src[(q, c['quest'])].append(f"{q}.{val} needs {c['flag']} ({c['quest']} {c['op']} {c['step']})")
            areas = sorted({a_ for act in acts_all for a_ in ([act['area']] if act.get('area') else act.get('areas') or [])})
            entry = {'index': i, 'value': val, 'flag': counter, 'set_by': set_by,
                     'requires': [c for c in reqs if not (c['quest'] == q)][:8],
                     'requires_own': [c for c in reqs if c['quest'] == q][:4],
                     'areas': areas, 'actions': acts_all[:8],
                     'boss': bool(row and row.get('IsBossBattle')), 'minigame': bool(row and row.get('IsMiniGame')),
                     'participants': [p.get('ActorName', '').split('/')[-1].split('.')[0] for p in (row or {}).get('Participants') or []],
                     'force_flag': (row or {}).get('ForceProgressGameData') or None,
                     'unknown': sorted(set(unk_all)) if set_by else (
                         [] if val in (Q.not_ready,) else [f'no flow event advances {q} to {val} (the game may set it '
                                                           'in code, or a step is skipped)']),
                     'evidence': ['RSDB/Challenge.Product.111.rstbl.byml.zs: ' + r['__RowId'] + f'.Steps[Name={val}]' if row else
                                  f'GameDataList: {counter}.RawValues[{i}]'] + [s['src'] for s in set_by]}
            if entry['force_flag']:
                entry['actions'].append({'do': 'make the game set a flag', 'flag': entry['force_flag'],
                                         'note': 'ForceProgressGameData: the step follows when this flag is set'})
            known = [a_ for a_ in entry['actions'] if a_.get('do')]
            entry['machine'] = 'known' if known and not entry['unknown'] else ('partly known' if known else 'unknown')
            steps.append(entry)
        dep = r.get('DependFlagName')
        if dep:
            for qq, op, val in E.parts(dep):
                if qq != q:
                    order_edges[q].add(qq)
                    edge_src[(q, qq)].append(f'{q}.DependFlagName = {dep} ({qq} {op} {val})')
        out_quests.append({'quest': q, 'category': cat or 'none (minigames and other)', 'complete_target': r.get('IsCompleteTarget'),
                           'depends_on_flag': dep, 'request_location': (r.get('RequestLocation') or '').split('/')[-1].split('.')[0] or None,
                           'request_actor': (r.get('RequestActor') or '').split('/')[-1].split('.')[0] or None,
                           'counter': counter, 'values': enum, 'steps': steps,
                           'src': 'RSDB/Challenge.Product.111.rstbl.byml.zs: ' + r['__RowId']})
    # one flow entry that finishes a quest (or moves it on) and starts another: the second follows the first
    by_entry = collections.defaultdict(set)
    for qq, sts in (idx.get('steps') or {}).items():
        for val, recs in sts.items():
            for x in recs:
                if x.get('op') == 'step':
                    by_entry[(x['flow'], x['entry'])].add((qq, val))
    first_of = {}
    for xq in out_quests:
        vals = [v for v in xq['values'] if v not in (Q.not_ready,)]
        first_of[xq['quest']] = set(vals[:2])          # ready and the first step after it
    for (fl, en), pairs in by_entry.items():
        done = [qq for qq, v in pairs if v == Q.complete]
        for qq, v in pairs:
            for dq in done:
                if dq != qq and v in first_of.get(qq, ()):
                    order_edges[qq].add(dq)
                    edge_src[(qq, dq)].append(f'{fl}:{en} sets {dq} {Q.complete} and {qq} {v} (Event/EventFlow/{fl}.bfevfl.zs)')
    # order of the main quests: a quest after every quest it needs (topological; ties in the table's order); quests
    # that the data relates to no other main quest are listed apart, unordered
    main = [x['quest'] for x in out_quests if x['category'] == Q.main_category]
    related = {q for q in main for d in order_edges[q] if d in main} | {d for q in main for d in order_edges[q] if d in main}
    order, placed = [], set()
    pending = [q for q in main if q in related]
    while pending:
        ready = [q for q in pending if all(d in placed or d not in main for d in order_edges[q])]
        if not ready:
            ready = [pending[0]]                     # a cycle in what the data says: keep the table's order
        q = ready[0]
        order.append({'quest': q, 'needs': sorted(d for d in order_edges[q] if d in main),
                      'why': sorted({s for d in order_edges[q] for s in edge_src[(q, d)]})[:6],
                      'ordered_by_data': True})
        placed.add(q)
        pending.remove(q)
    for q in main:
        if q not in related:
            order.append({'quest': q, 'needs': [], 'why': ['no data read here relates it to another main quest'],
                          'ordered_by_data': False})
    # gates a step opens: presence flags that are story expressions, satisfied from this step on
    opens = collections.defaultdict(list)
    for gt in gates.get('gates', []):
        fl = gt.get('flag')
        if not fl:
            continue
        for qq, op, val in E.parts(fl):
            opens[(qq, val, op)].append({'object': gt.get('object'), 'area': gt.get('area'), 'flag': fl,
                                         'present_when': gt.get('present_when'), 'type': gt.get('type')})
    for xq in out_quests:
        for st in xq['steps']:
            st['gates'] = []
            for (qq, val, op), lst in opens.items():
                if qq == xq['quest'] and val == st['value']:
                    for gte in lst:
                        st['gates'].append(dict(gte, test=f"{qq} {op} {val}"))
            st['gates'] = st['gates'][:12]
    # flow-set gate flags whose setter (or its starter) needs a step: the bridge kind
    for flag, recs in (idx.get('setters') or {}).items():
        gl = [gt for gt in gates.get('gates', []) if gt.get('flag') == flag]
        if not gl:
            continue
        for x in recs:
            st_ = [s for ev in x['events'] for s in (idx.get('starters') or {}).get(ev, [])]
            cs = conds_story(x['when'][0] if x['when'] else [])
            for s in st_:
                if s.get('when'):
                    cs += conds_story([bool_exp + '(' + s['when'] + ')'])
            for c in cs:
                if c['negated']:
                    continue
                for xq in out_quests:
                    if xq['quest'] != c['quest']:
                        continue
                    for st in xq['steps']:
                        if st['value'] == c['step']:
                            for gt in gl:
                                item = {'object': gt.get('object'), 'area': gt.get('area'), 'flag': flag,
                                        'present_when': gt.get('present_when'),
                                        'test': f"{c['quest']} {c['op']} {c['step']}",
                                        'how': f"{x['flow']}:{x['entry']} {x['at']} sets {flag} {x.get('value')}"}
                                if item not in st['gates']:
                                    st['gates'].append(item)
    n_steps = sum(len([s for s in x['steps'] if s['value'] != Q.not_ready]) for x in out_quests if x['category'] == Q.main_category)
    n_known = sum(1 for x in out_quests if x['category'] == Q.main_category for s in x['steps']
                  if s['value'] != Q.not_ready and s['machine'] != 'unknown')
    res = {'note': 'Game-derived. The story as the game counts it: quests (RSDB Challenge table) with their counters '
                   f'{Q.counter_prefix}<quest>, every step with the flow events that set it, who starts them, where, what a machine '
                   'must do there as far as the data says (actions; machine = known / partly known / unknown), the '
                   'other quests it needs (requires), the gates it opens, and the evidence. main_order: the main '
                   'quests ordered by what the data says each needs; ordered_by_data false = no data orders it.',
           'counts': {'quests': len(out_quests), 'main_quests': len(main), 'main_steps': n_steps,
                      'main_steps_with_machine_action': n_known},
           'main_order': order, 'quests': out_quests}
    (out_dir / 'story.json').write_text(json.dumps(res, indent=1, default=str))
    print('story:', json.dumps(res['counts']))
    for o in order:
        print(' ', o['quest'], '<-', ', '.join(o['needs']) or '-', '' if o['ordered_by_data'] else '(table order)')


if __name__ == '__main__':
    main()
