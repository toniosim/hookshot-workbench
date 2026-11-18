"""The world model's JSON files from the placements, the start list, the flag list and the nav meshes (called by
build.py, which has read the game already). Every game name and pattern comes from the tables (tables.py)."""
import collections
import json
import math
import re

from . import navgraph, plan as P


def write(g, mts, T, out_dir, acts, statics, params, objects, flags, navinfo, say):
    """Write the JSON files into out_dir (the data folder). T: the tables; acts, statics, params, objects: what
    build.py read per area; flags: build.Flags; navinfo: per area, what the nav step wrote."""
    bancs = sorted(g.folder)
    bases = sorted({T.area_base(b) for b in bancs}, key=len, reverse=True)
    areas_nav = {}
    X = T.exits

    def nav_area(b):
        if b not in areas_nav:
            p = out_dir / 'nav' / f'{b}.json.gz'
            areas_nav[b] = navgraph.Area(b, path=p) if p.is_file() else None
        return areas_nav[b]

    # ------------------------------------------------------------------------------------------------ areas.json
    areas = {}
    for b in bancs:
        A = nav_area(b)
        starts = {}
        for name, s in (g.starts.get(b) or {}).items():
            x, y, z = s['Trans']
            on = None
            if A is not None:
                c = A.candidates(x, z, y, snap=5.0, dy=4.0, limit=1)
                on = round(c[0][2], 2) if c else None
            starts[name or '(default)'] = {'pos': [round(v, 3) for v in s['Trans']], 'yaw': round(mts.yaw_of(s['Rot']), 4),
                                           'to_walkable_m': on}
        prm = params.get(b, {})
        areas[b] = {'folder': g.folder[b], 'age': mts.area_age(g, b, T)[0], 'area_index': prm.get('AreaIndex'),
                    'location': (prm.get('BaseLocation') or '').split('/')[-1].split('.')[0] or None,
                    'nav': navinfo.get(b, {}), 'starts': starts,
                    'placed_actors': len(acts[b]), 'objects': collections.Counter(o['kind'] for o in objects[b]),
                    'src': {'starts': 'Banc/BancBasedResource/StartPos.byml.zs', 'param':
                            f'Banc/GameBancParam/{b}.game__banc__GameBancParam.bgyml',
                            'nav': (navinfo.get(b) or {}).get('nav'),
                            'placements': f'Banc/{g.folder[b]}/{b}_{{Dynamic,Static}}.bcett.byml.zs'}}
        hm = prm.get('HeightMapParam') or {}
        if hm.get('BoundingBoxMin'):
            areas[b]['bbox'] = {'min': hm.get('BoundingBoxMin'), 'max': hm.get('BoundingBoxMax')}
        units = prm.get('NavMeshSceneAndConditionUnits')
        if units:
            areas[b]['nav_variants'] = units
    (out_dir / 'areas.json').write_text(json.dumps(areas, indent=1, ensure_ascii=False))
    n_starts = sum(len(a['starts']) for a in areas.values())
    say(f'areas.json: {len(areas)} areas, {n_starts} named starts')

    # ------------------------------------------------------------------------------------------------ links.json
    links = []
    for b in bancs:
        H = {x['Hash']: x for x in acts[b]}
        groups = statics[b].get('AiGroups', [])
        age = areas[b]['age']
        A = nav_area(b)
        for x in acts[b]:
            if T.kind_of(x['Gyaml']) != 'exit':
                continue
            d = x.get('Dynamic') or {}
            lk = {'id': f'{b}/{x.get("Name") or x["Hash"]}', 'from': b, 'name': x.get('Name'), 'hash': x['Hash'],
                  'actor_pos': [round(v, 3) for v in x['Translate']],
                  'to_child': d.get(X.to_child), 'to_adult': d.get(X.to_adult),
                  'to_start': d.get(X.to_start),
                  'events': {k: v for k, v in d.items() if X.event_key_part in k},
                  'evidence': [f'Banc/{g.folder[b]}/{b}_*.bcett.byml.zs: Actors[Gyaml={x["Gyaml"]}, Hash={x["Hash"]}].Dynamic']}
            if d.get(X.alt_flag):
                lk['alternative_flag'] = d[X.alt_flag]
            lk['to'] = (d.get(X.to_adult) if age == 'adult' else d.get(X.to_child)) \
                or d.get(X.to_child) or d.get(X.to_adult)
            # the trigger: a volume grouped with the exit in an AiGroup
            trig = []
            for grp in groups:
                refs = [r['Reference'] for r in grp['References']]
                if x['Hash'] not in refs:
                    continue
                for r in refs:
                    a = H.get(r)
                    if a and a['Gyaml'] == X.trigger_actor:
                        trig.append({'pos': [round(v, 3) for v in a['Translate']],
                                     'size': [round(v, 3) for v in a.get('Scale', [1, 1, 1])],
                                     'rot_y': round((a.get('Rotate') or [0, 0, 0])[1], 4),
                                     'shape': (a.get('Dynamic') or {}).get(X.trigger_shape_key, 'default'),
                                     'logic': grp['Logic'].split('/')[-1], 'hash': a['Hash']})
            lk['triggers'] = trig
            if trig:
                lk['evidence'].append(f'Banc/{g.folder[b]}/{b}_Static.bcett.byml.zs: AiGroups[Logic={trig[0]["logic"]}].References ({X.trigger_actor} + this exit)')
            for l in x.get('Links', []):
                a = H.get(l['Dst'])
                if a and a['Gyaml'] == X.anchor_actor and a.get('Name') == X.anchor_name:
                    lk['go_anchor'] = [round(v, 3) for v in a['Translate']]
            dest = lk['to']
            ds = (g.starts.get(dest) or {}).get(lk['to_start']) if dest else None
            lk['to_start_pos'] = [round(v, 3) for v in ds['Trans']] if ds else None
            lk['to_known'] = dest in g.folder if dest else False
            # where to walk to: the walkable point nearest the trigger's centre (else the exit actor), then the
            # named start of this area nearest to it
            tgt = trig[0]['pos'] if trig else lk['actor_pos']
            if A is not None:
                c = A.candidates(tgt[0], tgt[2], tgt[1], snap=12.0, dy=12.0, limit=1)
                if not c:
                    c = A.candidates(tgt[0], tgt[2], None, snap=12.0, limit=1)
                if c:
                    lk['approach'] = [round(v, 3) for v in c[0][1]]
                    lk['approach_off_m'] = round(c[0][2], 2)
            best = None
            for sname, s in areas[b]['starts'].items():
                p = s['pos']
                dd = math.dist((p[0], p[2]), (tgt[0], tgt[2]))
                if best is None or dd < best[0]:
                    best = (dd, sname)
            if best:
                lk['nearest_start'] = best[1]
                lk['nearest_start_m'] = round(best[0], 1)
            links.append(lk)
    # the way back: the exit in the destination whose next start is the area's start this exit's own start names
    by_from = collections.defaultdict(list)
    for lk in links:
        by_from[lk['from']].append(lk)
    (out_dir / 'links.json').write_text(json.dumps(links, indent=1, ensure_ascii=False))
    say(f'links.json: {len(links)} exits, {sum(1 for l in links if l["triggers"])} with a trigger volume, '
        f'{sum(1 for l in links if l["to_known"])} to a known area, {sum(1 for l in links if l.get("to_start_pos"))} with the destination start found')

    # ------------------------------------------------------------------------------------------------ objects.json
    keep = set(T.kind_names)
    obj_out = {b: [o for o in objects[b] if o['kind'] in keep] for b in bancs}
    (out_dir / 'objects.json').write_text(json.dumps(obj_out, ensure_ascii=False))
    kc = collections.Counter(o['kind'] for b in bancs for o in obj_out[b])
    with_flag = collections.Counter(o['kind'] for b in bancs for o in obj_out[b] if o.get('flags'))
    say(f'objects.json: {sum(kc.values())} objects; ' + ', '.join(f'{k} {v} ({with_flag[k]} with a flag)' for k, v in kc.most_common()))
    mobility = {}
    for k in kc:
        objs = [o for b in bancs for o in obj_out[b] if o['kind'] == k]
        mobility[k] = {'static_file': sum(o.get('placement') == 'Static' for o in objs),
                       'dynamic_file': sum(o.get('placement') == 'Dynamic' for o in objs),
                       'fixed': sum(bool(o.get('fixed')) for o in objs),
                       'wanders': sum(any('MoveRadius' in m for m in o.get('moves', [])) for o in objs),
                       'rail': sum(any('rail' in m for m in o.get('moves', [])) for o in objs),
                       'under_flag': sum(any('Presence' in m for m in o.get('moves', [])) for o in objs)}
    (out_dir / 'mobility.json').write_text(json.dumps(mobility, indent=1))
    say('mobility: ' + '; '.join(f'{k} {v["fixed"]}/{kc[k]} fixed, {v["dynamic_file"]} dynamic, {v["wanders"]} wander'
                                 for k, v in sorted(mobility.items())))

    # ------------------------------------------------------------------------------------------------ flags.json
    # offer more strings: event names as <played prefix><name>, people as <talked prefix><class>, every Dynamic string
    played, talked = T.flags.played_prefix, T.flags.talked_prefix
    for b in bancs:
        for x in acts[b]:
            if T.actors.talk_re.search(x['Gyaml']):
                flags.offer(talked + x['Gyaml'])
            for v in (x.get('Dynamic') or {}).values():
                if isinstance(v, str):
                    flags.offer(v)
                    flags.offer(played + v)
    for p in g.romfs.files:
        m = re.match(r'Event/EventFlow/(.+)\.bfevfl\.zs$', p)
        if m:
            flags.offer(played + m.group(1))
        m = T.flags.event_in_path_re.search(p)
        if m:
            flags.offer(played + m.group(1))
    # every identifier-like string of the event flows, the AI and logic graphs and the parameter files, as itself and
    # as the event/talk record of that name: a string is a flag name when its hash is in GameDataList
    ident = re.compile(rb'[A-Za-z_][A-Za-z0-9_.\-]{3,120}')
    seen_strings = set()
    for p in g.romfs.files:
        if (p.startswith('Event/EventFlow/') and p.endswith('.bfevfl.zs')) or p.endswith('.ainb') or \
                (p.startswith(('GameData', 'System/', 'Game/', 'Banc/')) and p.endswith(('.bgyml', '.byml.zs'))):
            try:
                raw = g.romfs.load(p)
            except Exception:
                continue
            seen_strings.update(m.group(0).decode() for m in ident.finditer(raw))
    for s in seen_strings:
        flags.offer(s)
        flags.offer(played + s)
        flags.offer(talked + s)
    # the quest counters are <counter prefix><quest>; the story expression flags that name a quest point at them
    for nm in list(flags.names.values()):
        m = T.quests.counter_exp_re.match(nm)
        if m:
            flags.offer(T.quests.counter_prefix + m.group(1))
    say(f'flag names: {len(seen_strings)} strings of the game offered')
    grouped = collections.defaultdict(lambda: collections.defaultdict(list))
    for h, nm in sorted(flags.names.items(), key=lambda kv: kv[1]):
        if h not in flags.types:
            continue
        area = None
        for bb in bases:
            if bb in nm:
                area = bb
                break
        if area is None:
            for tok, ar in T.areas.tokens.items():
                if tok in nm:
                    area = ar
                    break
        grouped[area or '(game-wide)'][T.flag_kind(nm)].append({'name': nm, 'hash': h, 'type': flags.types[h]})
    per_actor = collections.Counter()
    for b in bancs:
        for x in acts[b]:
            if x['Hash'] in flags.b64:
                per_actor[T.area_base(b)] += 1
    total_named = sum(len(v) for a in grouped.values() for v in a.values())
    type_counts = collections.Counter(flags.types.values())
    fl_out = {'counts': {'flags_in_list': len(flags.types), 'by_type': dict(type_counts),
                         'named': total_named, 'per_actor_bool64': len(flags.b64),
                         'per_actor_bool64_matched_to_placements': sum(per_actor.values())},
              'areas': {a: dict(k) for a, k in sorted(grouped.items())},
              'per_actor_state_flags_by_area': dict(per_actor)}
    (out_dir / 'flags.json').write_text(json.dumps(fl_out, indent=1, ensure_ascii=False))
    say(f'flags.json: {len(flags.types)} flags in GameDataList, {total_named} with a name '
        f'({total_named * 100 // max(1, len(flags.types) - len(flags.b64))} % of those without a 64-bit key), '
        f'{len(flags.b64)} per-actor states keyed by placement hash ({sum(per_actor.values())} matched to a placement)')

    # ------------------------------------------------------------------------------------------------ gates.json
    gates, questions = [], []
    # (1) walls and people that exist only under a flag, and which exits' ways pass them
    P.use(out_dir, objects=obj_out, areas={k: v for k, v in areas_nav.items() if v is not None})
    exit_paths = {}
    for lk in links:
        b = lk['from']
        if not lk.get('approach') or not P.available(b):
            continue
        s = areas[b]['starts'].get(lk.get('nearest_start')) if lk.get('nearest_start') else None
        exit_paths[lk['id']] = []
        for sname, s in areas[b]['starts'].items():
            r = P.plan(b, (s['pos'][0], s['pos'][2]), (lk['approach'][0], lk['approach'][2]), from_y=s['pos'][1],
                       to_y=lk['approach'][1], doors='through')
            if r['waypoints']:
                pts = [(s['pos'][0], s['pos'][2])] + [tuple(w) for w in r['waypoints']]
                exit_paths[lk['id']].append((sname, pts))

    def near_path(pos, pts, reach):
        for i in range(1, len(pts)):
            d = navgraph.seg_closest(pos[0], pos[2], pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1])[0]
            if d <= reach:
                return True
        return False
    for b in bancs:
        for o in obj_out[b]:
            pr = (o.get('flags') or {}).get('presence')
            if not pr or o['kind'] not in ('blocker', 'person', 'door', 'lock'):
                continue
            reach = 1.5 + (max(o.get('scale') or [1, 1, 1]) if o['kind'] == 'blocker' else 0.5)
            on_way, blocks = [], []
            for lid, paths in exit_paths.items():
                if not lid.startswith(b + '/') or not paths:
                    continue
                passing = [s for s, pts in paths if near_path(o['pos'], pts, reach)]
                if passing:
                    on_way.append({'exit': lid, 'starts_passing': len(passing), 'starts': len(paths)})
                    if 2 * len(passing) >= len(paths):
                        blocks.append(lid)
            h = mts.murmur(pr['flag'])
            exp = exp_desc(flags, h)
            gates.append({'type': f'{o["kind"]} present under a flag', 'area': b, 'object': o['gyaml'], 'pos': o['pos'],
                          'flag': pr['flag'], 'flag_type': pr.get('type'),
                          'present_when': f"{pr['flag']} is {'false' if pr['negated'] else 'true'}",
                          'flag_means': exp, 'on_way_to_exits': blocks, 'near_ways': on_way,
                          'evidence': f'Banc/{g.folder[b]}/{b}_*.bcett.byml.zs: Actors[Hash={o["hash"]}].Presence; '
                                      'the way: plan.py from every named start of the area to the exit'})
    # (2) nav mesh variants by flag
    for b in bancs:
        for u in params.get(b, {}).get('NavMeshSceneAndConditionUnits') or []:
            fl = u.get('ConditionGameDataPath')
            gates.append({'type': 'nav mesh variant', 'area': b, 'flag': fl, 'flag_means': exp_desc(flags, mts.murmur(fl or '')),
                          'unit': u, 'evidence': f'Banc/GameBancParam/{b}.game__banc__GameBancParam.bgyml: NavMeshSceneAndConditionUnits'})
    # (3) exits: the first-time event and the alternative destination flag
    for lk in links:
        ev = lk['events']
        if ev.get(X.init_flag):
            gates.append({'type': 'exit plays an event the first time', 'link': lk['id'], 'flag': ev[X.init_flag],
                          'event': ev.get(X.init_event), 'evidence': lk['evidence'][0] + f'.{X.init_flag}/{X.init_event}'})
        if lk.get('alternative_flag'):
            gates.append({'type': 'exit goes to the alternative area version under a flag', 'link': lk['id'],
                          'flag': lk['alternative_flag'], 'flag_means': exp_desc(flags, mts.murmur(lk['alternative_flag'])),
                          'evidence': lk['evidence'][0] + f'.{X.alt_flag}'})
    # (4) locked doors: their own saved state; what opens them is not in the placement
    for b in bancs:
        for o in obj_out[b]:
            if o['kind'] == 'lock':
                gates.append({'type': 'locked door', 'area': b, 'object': o['gyaml'], 'pos': o['pos'],
                              'flag': (o.get('flags') or {}).get('self'),
                              'evidence': f'Banc/{g.folder[b]}/{b}_*.bcett.byml.zs: Actors[Hash={o["hash"]}] (its Bool64bitKey state)'})
    # (5) doors whose logic module names flags
    for b in bancs:
        for o in obj_out[b]:
            lf = (o.get('flags') or {}).get('logic')
            if o['kind'] in ('door', 'lock') and lf:
                gates.append({'type': 'door named with flags by its logic module', 'area': b, 'object': o['gyaml'],
                              'pos': o['pos'], 'flags': lf, 'strength': 'mention',
                              'evidence': f'Banc/{g.folder[b]}/{b}_Static.bcett.byml.zs: AiGroups[References has '
                                          f'{o["hash"]}].Logic = {", ".join(o.get("logic", []))}; the module\'s strings '
                                          '(Logic/<name>.logic.module.ainb) that are flag names'})
    # (6) who changes the gate flags: event flows that name them, and the flags those flows name besides
    gate_flags = sorted({gt['flag'] for gt in gates if gt.get('flag') and not str(gt['flag']).startswith('Bool64')})
    named_in = flag_mentions(g, gate_flags)
    flow_names = flow_flag_names(g, flags, sorted({f for v in named_in.values() for f in v}))
    for gt in gates:
        if gt.get('flag') in named_in:
            gt['named_in_event_flows'] = named_in[gt['flag']][:12]
    for gt in gates:
        if gt['type'].endswith('present under a flag') and not gt.get('named_in_event_flows') and not gt.get('flag_means'):
            questions.append(f"what sets {gt['flag']} (gates {gt['object']} in {gt['area']}): no event flow names it")
    questions.append('which conditions the Logic modules (Logic/*.ainb, AiGroups) put on exits, doors and people: '
                     'not read (no reader for the AI node graphs yet); only the flag names they contain are listed')
    questions.append('what doors, warps and other triggers change: event flows (bfevfl) change areas '
                     'too; only flag mentions are read, not their flow')
    questions.append('which item opens a locked door: the placement '
                     'holds no key reference; the lock\'s own state is its Bool64bitKey')

    # the graph: nodes are links, objects and flags; edges carry the field they were read from
    edges = []
    for gt in gates:
        node = gt.get('link') or f"{gt.get('area')}/{gt.get('object')}@{','.join(str(round(v, 1)) for v in gt.get('pos', []))}"
        if gt.get('flag'):
            kind = {'exit plays an event the first time': 'plays-event-until',
                    'exit goes to the alternative area version under a flag': 'destination-depends-on',
                    'nav mesh variant': 'walkable-ground-depends-on', 'locked door': 'open-state'}.get(gt['type'], 'present-only-when')
            edges.append({'from': node, 'to': gt['flag'], 'kind': kind, 'strength': 'field',
                          'condition': gt.get('present_when'), 'evidence': gt['evidence']})
            for ex in gt.get('on_way_to_exits') or []:
                edges.append({'from': ex, 'to': node, 'kind': 'way-passes', 'strength': 'planned',
                              'evidence': 'plan.py: the planned way from at least half of the area\'s named starts '
                                          'to the exit passes within reach of the object'})
        for f in gt.get('flags') or []:
            edges.append({'from': node, 'to': f, 'kind': 'logic-names', 'strength': 'mention', 'evidence': gt['evidence']})
    for f, flows in named_in.items():
        for fl_ in flows[:12]:
            also = flow_names.get(fl_, [])
            edges.append({'from': f'flow:{fl_}', 'to': f, 'kind': 'flow-names', 'strength': 'mention',
                          'also_names': also[:60],
                          'evidence': f'Event/EventFlow/{fl_}.bfevfl.zs contains the name'})
            for other in also:
                if flags.types.get(mts.murmur(other)) == 'BoolExp' and other != f:
                    edges.append({'from': f'flow:{fl_}', 'to': other, 'kind': 'flow-names', 'strength': 'mention',
                                  'evidence': f'Event/EventFlow/{fl_}.bfevfl.zs contains the name'})
    exp_seen = set()
    todo = [e['to'] for e in edges if isinstance(e['to'], str)]
    while todo:
        f = todo.pop()
        if f in exp_seen:
            continue
        exp_seen.add(f)
        d = flags.describe_exp(mts.murmur(f))
        if not d:
            continue
        text, reads = d
        for r_ in reads:
            edges.append({'from': f, 'to': r_, 'kind': 'expression-reads', 'strength': 'field', 'expression': text,
                          'evidence': f'GameData/GameDataList.Product.110.byml.zs: Data.BoolExp[Hash={mts.murmur(f)}].Values'})
            todo.append(r_)
    # a gate on the way to an exit whose flag is a plain Bool: what opens it is not a field of the data; list the
    # leads (the flows that name the flag, and the expressions those flows also name, decoded) as a question
    for gt in gates:
        if not gt.get('on_way_to_exits') or flags.types.get(mts.murmur(gt.get('flag') or '')) != 'Bool':
            continue
        leads = []
        for fl_ in gt.get('named_in_event_flows') or []:
            for other in flow_names.get(fl_, []):
                d = flags.describe_exp(mts.murmur(other))
                if d and d[0]:
                    leads.append(f'{fl_}: {other} = {d[0]}')
        gt['opens_when'] = None
        gt['leads'] = leads[:12]
        questions.append(f"what opens {gt['object']} at {gt['pos']} in {gt['area']} (present while {gt['flag']} is "
                         f"true; on the way to {', '.join(gt['on_way_to_exits'])}): the flag is a plain Bool set by an "
                         f"event flow; flows naming it: {', '.join(gt.get('named_in_event_flows') or ['none'])}; "
                         f"expressions they also name: {'; '.join(leads[:6]) or 'none'}")
    ek = collections.Counter((e['kind'], e['strength']) for e in edges)
    (out_dir / 'gates.json').write_text(json.dumps({'gates': gates, 'edges': edges, 'questions': questions,
                                                    'note': 'strength field: read from a named field of the data; planned: '
                                                            'from the planner over the nav mesh; mention: the name occurs '
                                                            'in that file (a flow or logic graph not parsed): a lead, not '
                                                            'a proven condition'},
                                                   indent=1, ensure_ascii=False))
    gk = collections.Counter(gt['type'] for gt in gates)
    say(f'gates.json: {len(gates)} gates (' + ', '.join(f'{k} {v}' for k, v in gk.most_common()) + f'), '
        f'{sum(1 for gt in gates if gt.get("on_way_to_exits"))} on the way to an exit, '
        f'{sum(1 for gt in gates if gt.get("named_in_event_flows"))} named in an event flow; {len(edges)} edges ('
        + ', '.join(f'{k}/{s} {v}' for (k, s), v in ek.most_common()) + f'); {len(questions)} questions')

    # ------------------------------------------------------------------------------------------------ summary
    summ = {
        'areas': len(areas), 'areas_with_nav': sum(1 for b in areas if (areas[b]['nav'] or {}).get('faces')),
        'named_starts': n_starts,
        'starts_on_walkable_within_1m': sum(1 for a in areas.values() for s in a['starts'].values()
                                            if s['to_walkable_m'] is not None and s['to_walkable_m'] <= 1.0),
        'starts_far_or_off_mesh': sum(1 for a in areas.values() for s in a['starts'].values()
                                      if s['to_walkable_m'] is None or s['to_walkable_m'] > 1.0),
        'links': len(links), 'links_with_trigger': sum(1 for l in links if l['triggers']),
        'links_to_known_area': sum(1 for l in links if l['to_known']),
        'links_destination_start_found': sum(1 for l in links if l.get('to_start_pos')),
        'area_pairs': len({(l['from'], l['to']) for l in links}),
        'objects': dict(kc), 'objects_with_flag': dict(with_flag),
        'flags': fl_out['counts'], 'gates': dict(gk), 'gate_edges': {f'{k}/{s}': v for (k, s), v in ek.most_common()},
        'questions': questions,
    }
    (out_dir / 'summary.json').write_text(json.dumps(summ, indent=1))
    say('summary.json written')


def exp_desc(flags, h):
    t = flags.describe_exp(h)
    return t[0] if t and t[0] else None


def flag_mentions(g, names):
    """Event flow files whose bytes contain each flag name (a cheap read of who sets or tests it)."""
    out = collections.defaultdict(list)
    want = {n.encode(): n for n in names if n}
    if not want:
        return out
    for p in sorted(g.romfs.files):
        if not (p.startswith('Event/EventFlow/') and p.endswith('.bfevfl.zs')):
            continue
        try:
            raw = g.romfs.load(p)
        except Exception:
            continue
        for b, n in want.items():
            if b in raw:
                out[n].append(p.split('/')[-1].replace('.bfevfl.zs', ''))
    return out


def flow_flag_names(g, flags, flows):
    """{flow: [flag names its bytes contain]} for the given event flows."""
    ident = re.compile(rb'[A-Za-z_][A-Za-z0-9_.\-]{3,120}')
    out = {}
    for fl in flows:
        p = f'Event/EventFlow/{fl}.bfevfl.zs'
        if p not in g.romfs.files:
            continue
        names = set()
        for m in ident.finditer(g.romfs.load(p)):
            s = m.group(0).decode()
            if flags.offer(s) is not None or flags.mts.murmur(s) in flags.types:
                names.add(s)
        out[fl] = sorted(names)
    return out
