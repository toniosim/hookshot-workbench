#!/usr/bin/env python3
"""What the game's event flows do and when they run, as data: which flow entry sets which flag (or story step, or
item) on which path of conditions, and which talk, approach or placement starts that entry. Game-derived output, stays
in the data folder (paths.data_dir(): $PILOT_WORLD, else world/ beside worldmodel/).

    python3 flows.py [--game <extracted RomFS folder>]     # writes flows.json and adds the 'flow' edges to gates.json

--game, else $WORLD_GAME. Needs the tables file (tables.py): which event queries test a flag, which actions set one,
and the event parameter keys.

Sources (game 1.1.1 romfs), each cited in the output:
- Event/EventFlow/<flow>.bfevfl.zs: the flows (reader: evfl.py).
- RSDB/EventSetting.Product.111.rstbl.byml.zs: event name (the played flag, the names NPC schedules and placements
  give) -> flowchart file and entry point.
- Component/AIScheduleParam/<actor>.game__component__AIScheduleParam.bgyml and the same in Pack/AIScheduleParam.pack.zs:
  per NPC, a list `ConditionalSchedule` of {ConditionFlag, IsReverseCondition, EventEntry: talk / approach (a Distance)
  -> event name}, and `DefaultSchedule`. `$parent` is followed.
- RSDB/Challenge.Product.111.rstbl.byml.zs: the quests ("challenges") and their ordered steps (story.py uses it).

Path conditions: from an entry's main event every path is followed (sub flows entered, forks taken on every branch); a
switch adds (query, its parameters, the case value taken). **For the boolean queries (the tables' flows.bool_queries)
case 0 is "true" and case 1 "false"** in this game's flows. Evidence: in the flows read, every "have talked / first
time" flag is set only on the case-1 branch of the query that tests it, and branches that test a story step have an
unreachable branch unless case 0 is true. [INFERENCE from the data; checked by test runs.] Other queries keep their
number. A sub flow that returns a value (event type 5) adds 'returned <hash>' per case.
"""
import argparse
import collections
import json
import sys
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from worldmodel import evfl, paths, tables  # noqa: E402

MAX_STEPS = 20000          # events visited per entry (all paths); flows of this game stay far below
MAX_CONDSETS = 6           # condition sets kept per effect


def load_mts():
    # the format readers with the whole RomFS folder's file list: game_files.py
    from worldmodel.game_files import load_mts as load
    return load()


def _gameparam(path):
    """'Work/Component/AIScheduleParam/X.game__component__AIScheduleParam.gyml' -> romfs name of the .bgyml."""
    return path.replace('Work/', '', 1).replace('.gyml', '.bgyml')


class Flows:
    def __init__(self, g, mts, T):
        self.g, self.mts, self.T = g, mts, T
        files = g.romfs.files
        self.flows = {}
        for p in files:
            if p.startswith('Event/EventFlow/') and p.endswith('.bfevfl.zs'):
                f = evfl.read(g.romfs.load(p))
                if f:
                    self.flows[p.split('/')[-1][:-len('.bfevfl.zs')]] = f
        self.settings = {}
        for r in mts.byml(g.romfs.load('RSDB/EventSetting.Product.111.rstbl.byml.zs')):
            fc = (r.get('FlowchartFileName') or '').split('/')[-1].replace('.evfc', '')
            self.settings[r['__RowId']] = {'flow': fc, 'entry': r.get('EntryPointName') or ''}
        self.by_entry = collections.defaultdict(list)
        for ev, s in self.settings.items():
            self.by_entry[(s['flow'], s['entry'])].append(ev)
        # schedules: loose files and the pack
        self.sched_raw = {}
        for p in files:
            if p.startswith('Component/AIScheduleParam/'):
                self.sched_raw[p] = mts.byml(g.romfs.load(p))
        for k, v in mts.sarc(g.romfs.load('Pack/AIScheduleParam.pack.zs')).items():
            self.sched_raw[k] = mts.byml(v)

    # ------------------------------------------------------------------------------------------- schedules
    def schedule(self, path, depth=0):
        d = dict(self.sched_raw.get(path) or {})
        par = d.pop('$parent', None)
        if par and depth < 6:
            base = self.schedule(_gameparam(par), depth + 1)
            base.update(d)
            d = base
        return d

    def schedules(self):
        """{schedule name: {'src', 'conditional': [{'flag', 'negated', 'talk': [...], 'near': [...]}], 'default'}}"""
        out = {}
        near_type = self.T.flows.near_type
        for p in self.sched_raw:
            name = p.split('/')[-1].split('.')[0]
            d = self.schedule(p)

            def entries(lst):
                talk, near = [], []
                for e in lst or []:
                    ev = (e.get('EventName') or '').split('/')[-1].split('.')[0]
                    if not ev:
                        continue
                    t = e.get('$type', '') or e.get('$parent', '')
                    if near_type in t:
                        near.append({'event': ev, 'distance': e.get('Distance')})
                    else:
                        talk.append({'event': ev})
                return talk, near
            cond = []
            for i, c in enumerate(d.get('ConditionalSchedule') or []):
                talk, near = entries(c.get('EventEntry'))
                cond.append({'index': i, 'flag': c.get('ConditionFlag'), 'negated': bool(c.get('IsReverseCondition')),
                             'talk': talk, 'near': near})
            dt, dn = entries((d.get('DefaultSchedule') or {}).get('EventEntry'))
            if cond or dt or dn:
                out[name] = {'src': p + (': ConditionalSchedule, DefaultSchedule' if cond else ': DefaultSchedule'),
                             'conditional': cond, 'default': {'talk': dt, 'near': dn}}
        return out

    # ------------------------------------------------------------------------------------------- paths
    def cond_of(self, f, e, value):
        fl = self.T.flows
        lab = evfl.label(f, e)
        q = lab.split('.')[-1]
        p = e.get('params') or {}
        what = next((v for k in fl.what_keys if (v := p.get(k))), '')
        if q in fl.bool_queries:
            return {'q': q, 'what': what or _what(p, fl), 'is': value == 0, 'params': _small(p, fl)}
        return {'q': q, 'what': what or _what(p, fl), 'case': value, 'params': _small(p, fl)}

    def walk(self, fname, entry):
        """[(effect dict, [conditions])] for every effect reachable from the entry, per distinct condition path."""
        out = []
        steps = [0]
        fl = self.T.flows

        def go(fn, ev_i, conds, stack, seen):
            while True:
                if steps[0] > MAX_STEPS:
                    return
                steps[0] += 1
                f = self.flows.get(fn)
                if f is None or ev_i == evfl.NONE or ev_i >= len(f['events']):
                    return
                key = (fn, ev_i)
                if key in seen:
                    return
                seen = seen | {key}
                e = f['events'][ev_i]
                t = e['type']
                if t == evfl.ACTION:
                    lab = evfl.label(f, e)
                    act = lab.split('.')[-1]
                    kind = fl.effects.get(act)
                    if kind:
                        out.append(({'kind': kind, 'action': lab, 'params': _small(e.get('params') or {}, fl),
                                     'flow': fn, 'event': e['name']}, list(conds)))
                    ev_i = e['next']
                    continue
                if t == evfl.SWITCH:
                    for val, nxt in e['cases']:
                        go(fn, nxt, conds + [self.cond_of(f, e, val)], stack, seen)
                    return
                if t == evfl.FORK:
                    for b in e['forks']:
                        go(fn, b, conds, stack, seen)
                    j = f['events'][e['join']] if e['join'] < len(f['events']) else None
                    if j is None:
                        return
                    ev_i = j.get('next', evfl.NONE)
                    continue
                if t == evfl.JOIN:
                    return              # a branch of a fork ends at its join; the fork continues after it
                if t in (evfl.SUBFLOW, evfl.CALL_SWITCH):
                    sub = e.get('flow') or fn
                    if len(stack) < 6 and sub in self.flows and e.get('entry') in self.flows[sub]['entries']:
                        go(sub, self.flows[sub]['entries'][e['entry']], conds, stack + [(fn, ev_i)], frozenset())
                    if t == evfl.CALL_SWITCH:
                        for val, nxt in e.get('cases', []):
                            go(fn, nxt, conds + [{'q': 'subflow-returned', 'what': f"{sub}:{e.get('entry')}",
                                                  'case': f'0x{val:08x}'}], stack, seen)
                        return
                    ev_i = e.get('next', evfl.NONE)
                    continue
                return                  # type 6 (return a value) and anything unknown end the path

        f = self.flows.get(fname)
        if f and entry in f['entries']:
            go(fname, f['entries'][entry], [], [], frozenset())
        return out


def _small(p, fl):
    """Parameters without the presentation noise (camera, animation, message layout): the keys the tables name."""
    keep = {}
    for k, v in p.items():
        if isinstance(v, dict) and '$arg' in v:
            v = f"<argument {v['$arg']}>"      # filled in by the caller of the sub flow
        if k in fl.param_keys:
            if k in fl.drop_minus_one_keys and v == -1:
                continue
            keep[k] = v
        elif fl.param_key_re.search(k) and isinstance(v, (str, int, bool)):
            keep[k] = v
    return keep


def _cond_text(c, fl):
    if c['q'] == 'subflow-returned':
        return f"sub flow {c['what']} returned {c['case']}"
    if 'is' in c:
        nm = c['what'] or c['q']
        return f"{'' if c['is'] else 'NOT '}{c['q'].replace(fl.query_prefix, '')}({nm})"
    return f"{c['q'].replace(fl.query_prefix, '')}({c['what']}) == {c['case']}"


def _what(p, fl):
    """A query's scalar parameters as 'key=value, ...' (for queries that name no flag, e.g. an equipment slot)."""
    return ', '.join(f'{k}={v}' for k, v in p.items() if isinstance(v, (str, int, float, bool)) and v not in ('', -1)
                     and k not in fl.what_skip_keys)


def analyse(F):
    """The index written to flows.json."""
    fl = F.T.flows
    sched = F.schedules()
    # who starts an event: NPC schedules (talk / approach under a condition)
    starters = collections.defaultdict(list)
    for sname, s in sched.items():
        for c in s['conditional']:
            for kind in ('talk', 'near'):
                for e in c[kind]:
                    starters[e['event']].append({'by': 'schedule', 'schedule': sname, 'how': kind,
                                                 'distance': e.get('distance'), 'index': c['index'],
                                                 'when': c['flag'], 'negated': c['negated'],
                                                 'src': s['src'] + f"[{c['index']}]"})
        for kind in ('talk', 'near'):
            for e in s['default'][kind]:
                starters[e['event']].append({'by': 'schedule', 'schedule': sname, 'how': kind, 'index': 'default',
                                             'when': None, 'src': s['src'] + '.DefaultSchedule'})
    setters = collections.defaultdict(list)
    steps = collections.defaultdict(lambda: collections.defaultdict(list))
    items, areas = [], []
    tests = collections.defaultdict(set)
    n_entries = 0
    for fn, f in sorted(F.flows.items()):
        for e in f['events']:
            if e['type'] == evfl.SWITCH:
                p = e.get('params') or {}
                nm = next((v for k in fl.test_keys if (v := p.get(k))), None)
                if nm and isinstance(nm, str):
                    tests[nm].add(fn)
        for entry in f['entries']:
            n_entries += 1
            evs = F.by_entry.get((fn, entry), [])
            res = F.walk(fn, entry)
            grouped = collections.OrderedDict()
            for eff, conds in res:
                k = (eff['flow'], eff['event'], json.dumps(eff['params'], sort_keys=True))
                grouped.setdefault(k, (eff, []))
                cs = list(dict.fromkeys(_cond_text(c, fl) for c in conds))
                if cs not in grouped[k][1] and len(grouped[k][1]) < MAX_CONDSETS:
                    grouped[k][1].append(cs)
            for (_fl, _ev, _p), (eff, condsets) in grouped.items():
                rec = {'flow': fn, 'entry': entry, 'events': evs, 'at': f"{eff['flow']}:{eff['event']}",
                       'action': eff['action'], 'params': eff['params'], 'when': condsets,
                       'src': f"Event/EventFlow/{eff['flow']}.bfevfl.zs: event {eff['event']} (entry {fn}:{entry})"}
                if eff['kind'] in ('set', 'add', 'sub'):
                    nm = eff['params'].get(fl.flag_key)
                    if nm:
                        rec['value'] = eff['params'].get(fl.value_key)
                        rec['op'] = eff['kind']
                        setters[nm].append(rec)
                elif eff['kind'] in ('step', 'rollback'):
                    ch = eff['params'].get(fl.quest_key)
                    st = next((v for k in fl.step_keys if (v := eff['params'].get(k))), None)
                    if ch and st:
                        rec['op'] = eff['kind']
                        steps[ch][st].append(rec)
                elif eff['kind'] in ('item', 'currency'):
                    items.append(rec)
                elif eff['kind'] == 'area':
                    areas.append(rec)
    return {
        'note': 'Game-derived. setters: flag -> every flow entry that sets it, with the conditions on the way '
                '(when: alternatives, each a list that must all hold) and the events that start the entry (events: '
                'EventSetting names; starters: who starts each event). steps: quest -> step -> the flow events that '
                'advance it. Sources in each record.',
        'counts': {'flows': len(F.flows), 'entries': n_entries, 'event_settings': len(F.settings),
                   'schedules': len(sched), 'flags_set': len(setters),
                   'step_setters': sum(len(v) for s in steps.values() for v in s.values()),
                   'item_effects': len(items), 'area_changes': len(areas)},
        'event_settings': F.settings,
        'schedules': sched,
        'starters': starters,
        'setters': setters,
        'steps': {k: dict(v) for k, v in steps.items()},
        'items': items,
        'area_changes': areas,
        'tested_in': {k: sorted(v) for k, v in tests.items()},
    }


def how_set(idx, flag, value=None):
    """Plain records of how a flag gets a value: [(record, [starters of its events])]."""
    out = []
    for rec in idx['setters'].get(flag, []):
        if value is not None and rec.get('value') != value:
            continue
        st = [s for ev in rec['events'] for s in idx['starters'].get(ev, [])]
        out.append((rec, st))
    return out


def gate_edges(idx, gates):
    """Edges 'flag F gets value V by flow X when ...', for every gate flag that a flow sets."""
    edges = []
    done = set()
    for gt in gates.get('gates', []):
        flag = gt.get('flag')
        if not flag or flag in done or '(' in flag:
            continue
        done.add(flag)
        per_at = collections.Counter()
        # an effect reached from many entries through a shared sub flow: the entries that something starts first,
        # at most four per setting event
        for rec, st in sorted(how_set(idx, flag), key=lambda rs: (not rs[1], not rs[0]['events'])):
            per_at[(rec['at'], str(rec.get('value')))] += 1
            if per_at[(rec['at'], str(rec.get('value')))] > 4:
                continue
            started = '; '.join(
                f"{s['how']} {s['schedule']}" + (f" ({s['distance']} m)" if s.get('distance') else '')
                + (f" while {'NOT ' if s.get('negated') else ''}{s['when']}" if s.get('when') else ' (default schedule)')
                for s in st) or ('event ' + ', '.join(rec['events']) if rec['events'] else 'entry not named by any EventSetting')
            edges.append({'from': f"{rec['flow']}:{rec['entry']}", 'to': flag, 'kind': 'sets',
                          'value': rec.get('value'), 'op': rec.get('op'), 'strength': 'flow',
                          'condition': ' OR '.join('(' + ' AND '.join(c) + ')' if c else '(always)' for c in rec['when']),
                          'started_by': started, 'events': rec['events'],
                          'evidence': rec['src'] + '; RSDB/EventSetting.Product.111.rstbl.byml.zs (event -> entry)'
                          + ('; ' + '; '.join(sorted({s['src'] for s in st})) if st else '')})
    return edges


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--game', default=None, help='the extracted RomFS folder (else $WORLD_GAME)')
    a = ap.parse_args()
    game = paths.game_dir(a.game)
    try:
        T = tables.load()
    except tables.TablesError as e:
        sys.exit(f'worldmodel: {e}')
    out_dir = paths.data_dir()
    mts = load_mts()
    g = mts.Game(game)
    F = Flows(g, mts, T)
    idx = analyse(F)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'flows.json').write_text(json.dumps(idx, indent=1, default=str))
    gp = out_dir / 'gates.json'
    if gp.is_file():
        gates = json.loads(gp.read_text())
        gates['edges'] = [e for e in gates['edges'] if e.get('strength') != 'flow']
        fe = gate_edges(idx, gates)
        gates['edges'] += fe
        flagged = {e['to'] for e in fe}
        for gt in gates['gates']:
            if gt.get('flag') in flagged:
                gt['set_by_flow'] = [f"{e['from']} -> {e['value']}" for e in fe if e['to'] == gt['flag']]
        gp.write_text(json.dumps(gates, indent=1))
        print(f'flows: {len(fe)} flow edges for {len(flagged)} gate flags -> gates.json')
    print('flows:', json.dumps(idx['counts']))


if __name__ == '__main__':
    main()
