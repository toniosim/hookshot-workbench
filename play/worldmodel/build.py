#!/usr/bin/env python3
"""Build the world model of the game from a RomFS folder. Everything written here is game-derived and stays in the
data folder (paths.data_dir(): $PILOT_WORLD, else world/ beside the worldmodel/ folder), never in the repository.

    python3 build.py [--game <extracted RomFS folder>] [--only nav,model,inventory] [--areas A,B]

--game, else $WORLD_GAME. Needs the tables file (tables.py: tables.json in the data folder or $WORLD_TABLES); reads
the optional flag name list (flag_names.json in the data folder or $WORLD_FLAG_NAMES).

Writes (into the data folder):
  nav/<area>.json.gz   the area's nav mesh (navmesh.py's format) plus `xlinks` between its components
  inventory.json/.md   the kinds of files of the romfs by folder and extension, per area
  areas.json           every area: folder, age, nav mesh, named starts (place, facing, distance to walkable ground)
  links.json           every way from one area to another that the placements name (trigger volume, destination)
  objects.json         per area: doors, people, chests, switches, signs, climbables, crawl holes, blockers, items,
                       exits, starts, events; with the flags the data ties to each
  flags.json           readable flag names by area and kind
  gates.json           flag conditions on links, walls, people and nav mesh variants, each with its evidence
  summary.json/.md     the counts and what is missing
"""
import argparse
import collections
import json
import re
import sys
import time
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from worldmodel import navgraph, navmesh, paths, tables  # noqa: E402


def load_mts():
    # the format readers with the whole RomFS folder's file list: game_files.py
    from worldmodel.game_files import load_mts as load
    return load()


# ------------------------------------------------------------------------------------------------------- inventory
def inventory(g, bancs, T):
    files = g.romfs.files
    by_top = collections.Counter()
    by_ext = collections.Counter()
    by_folder_ext = collections.Counter()
    size_top = collections.Counter()
    for p, (_off, size) in files.items():
        parts = p.split('/')
        top = parts[0] if len(parts) > 1 else '(root)'
        sub = '/'.join(parts[:2]) if len(parts) > 2 else top
        name = parts[-1]
        ext = '.'.join(name.split('.')[1:]) if '.' in name else ''
        ext = re.sub(r'^.*?\.(?=[a-z_]+(\.zs)?$)', '', ext) if ext.count('.') > 2 else ext
        by_top[top] += 1
        size_top[top] += size
        by_ext[ext] += 1
        by_folder_ext[(sub, ext)] += 1
    per_area = {}
    for b in bancs:
        base = T.area_base(b)
        row = {
            'placement': [p for p in (f'Banc/{g.folder[b]}/{b}_Dynamic.bcett.byml.zs', f'Banc/{g.folder[b]}/{b}_Static.bcett.byml.zs') if p in files],
            'navmesh': [p for p in files if p.startswith(f'Phive/NavMesh/{b}.') or p.startswith(f'Phive/NavMesh/{b}_')],
            'stitched_navmesh_tiles': sum(1 for p in files if p.startswith(f'Phive/StitchedNavMesh/{b}')),
            'collision_tiles': sum(1 for p in files if p.startswith(f'Phive/StaticCompoundBody/{g.folder[b]}/{b}')
                                   or p == f'Phive/StaticCompoundBody/{g.folder[b]}/{b}.Nin_Ounce_NVN2.bphsc.zs'),
            'terrain_height_tiles': sum(1 for p in files if p.startswith(f'TerrainArc/{base}') and p.endswith('.hght')),
            'banc_param': f'Banc/GameBancParam/{b}.game__banc__GameBancParam.bgyml' in files,
            'world_param': f'WorldMgr/WorldParam/{b}.game__wm__WorldParam.bgyml' in files,
            'adjacent_rooms': f'Game/AdjacentRoomsInfo/{b}.game__AdjacentRoomsInfo.bgyml' in files,
            'dungeon_param': f'Scene/Component/DungeonParam/{b}.game__scene__DungeonParam.bgyml' in files,
            'logic_modules': sum(1 for p in files if p.startswith(f'Logic/{b}_') or p.startswith(f'Logic/{base}_Common')),
            'precomputed_culling': sum(1 for p in files if p.startswith(f'PreComputedCulling/{b}') or p.startswith(f'PreComputedCulling/{base}')),
        }
        per_area[b] = row
    return {'files': len(files), 'by_top': by_top.most_common(), 'bytes_by_top': size_top.most_common(),
            'by_ext': by_ext.most_common(), 'by_folder_ext': [[f, e, n] for (f, e), n in by_folder_ext.most_common()],
            'per_area': per_area}


# -------------------------------------------------------------------------------------------------------- flags
class Flags:
    def __init__(self, g, mts, names=None):
        """names: {flag hash: readable name} the builder starts from (the optional flag name list)."""
        self.mts = mts
        self.types = {}
        self.ents = {}
        for h, (tn, ent) in g.flags.items():
            self.types[h] = tn
            self.ents[h] = ent
        self.names = dict(names or {})
        self.b64 = {ent['Hash'] for h, (tn, ent) in g.flags.items() if tn == 'Bool64bitKey'}
        self.tried = set()

    def offer(self, s):
        """Name a flag if the string hashes to one."""
        if not isinstance(s, str) or not s or s in self.tried:
            return None
        self.tried.add(s)
        h = self.mts.murmur(s)
        if h in self.types and h not in self.names:
            self.names[h] = s
        return h if h in self.types else None

    def name(self, h):
        return self.names.get(h)

    def describe_exp(self, h):
        """A BoolExp flag as (infix text, [flag names it reads]) or None. GameDataList stores it as a stack program:
        [code, operand] pushes, [code] combines. Codes, inferred from flags whose names say what they compute
        [INFERENCE]: push 0 a Bool flag, 10 another BoolExp, 1/12/11 an enum flag compared (==, >=, <) with the enum
        value pushed next by 2, 15/18/19 an Int flag compared (==, <, >) with the number pushed next by 16; combine
        3 AND, 4 OR, 5 NOT. Examples: [[0, A], [0, B], [3]] is (A AND B); [[18, C], [16, 1], [5]] is NOT C < 1."""
        ent = self.ents.get(h)
        if not ent or self.types.get(h) != 'BoolExp' or 'Values' not in ent:
            return None
        stack, reads, pending = [], [], None
        for item in ent['Values']:
            code = item[0]
            if len(item) == 1:
                if code == 5 and stack:
                    stack.append(f'NOT {stack.pop()}')
                elif code in (3, 4) and len(stack) >= 2:
                    b, a = stack.pop(), stack.pop()
                    stack.append(f'({a} {"AND" if code == 3 else "OR"} {b})')
                else:
                    stack.append(f'?op{code}')
                continue
            v = item[1]
            if code in (2, 16) and pending is not None:
                name, ent2, cmp_ = pending
                if code == 2:
                    raw = (ent2 or {}).get('RawValues', [])
                    val = {self.mts.murmur(x): x for x in raw}.get(v, f'0x{v:08x}')
                else:
                    val = str(v)
                stack.append(f'{name} {cmp_} {val}')
                pending = None
                continue
            name = self.names.get(v, f'0x{v:08x}')
            if v in self.ents:
                reads.append(name)
            if code in (0, 10):
                stack.append(name)
            else:
                pending = (name, self.ents.get(v), CMP.get(code, f'?{code}'))
        # more than one value left on the stack: the program does not say how they combine; shown apart with ' ; '
        return (' ; '.join(stack) if stack else None), reads


CMP = {1: '==', 12: '>=', 11: '<', 15: '==', 18: '<', 19: '>'}


# ----------------------------------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--game', default=None, help='the extracted RomFS folder (else $WORLD_GAME)')
    ap.add_argument('--only', default='inventory,nav,model')
    ap.add_argument('--areas', default='')
    a = ap.parse_args()
    game = paths.game_dir(a.game)
    try:
        T = tables.load()
    except tables.TablesError as e:
        sys.exit(f'worldmodel: {e}')
    out_dir = paths.data_dir()
    only = set(a.only.split(','))
    t0 = time.time()
    log = []

    def say(s):
        print(s, flush=True)
        log.append(s)

    names = {}
    np = paths.flag_names_path()
    if np.is_file():
        names = {int(k): v for k, v in json.loads(np.read_text()).items()}
    else:
        say(f'flag names: no list at {np} (optional): only names found by hashing the game\'s strings are used')
    mts = load_mts()
    g = mts.Game(game)
    bancs = sorted(g.folder)
    if a.areas:
        bancs = [b for b in bancs if b in a.areas.split(',')]
    (out_dir / 'nav').mkdir(parents=True, exist_ok=True)

    if 'inventory' in only:
        inv = inventory(g, sorted(g.folder), T)
        (out_dir / 'inventory.json').write_text(json.dumps(inv, indent=1))
        say(f'inventory: {inv["files"]} files ({time.time() - t0:.0f} s)')

    # each actor with the placement file it came from: <area>_Static (the static world) or <area>_Dynamic (actors that
    # the game instantiates as live actors: they may move, be picked up or vanish)
    acts, src_of = {}, {}
    for b in sorted(g.folder):
        acts[b] = []
        for kind in ('Dynamic', 'Static'):
            p = f'Banc/{g.folder[b]}/{b}_{kind}.bcett.byml.zs'
            if p in g.romfs.files:
                for x in mts.byml(g.romfs.load(p)).get('Actors', []):
                    acts[b].append(x)
                    src_of[(b, x['Hash'])] = (kind, p)
    statics = {}
    for b in sorted(g.folder):
        p = f'Banc/{g.folder[b]}/{b}_Static.bcett.byml.zs'
        statics[b] = mts.byml(g.romfs.load(p)) if p in g.romfs.files else {}
    params = {b: g.bancparam(b) or {} for b in sorted(g.folder)}
    flags = Flags(g, mts, names)

    # objects first (the nav links need the climbables)
    objects = {}
    ident = re.compile(rb'[A-Za-z_][A-Za-z0-9_.\-]{3,120}')
    lf_cache = {}

    def logic_flags(name):
        """Flag names that the logic module (an AI node graph the placement's AiGroups point the object at) contains:
        its strings whose hash is a flag of GameDataList."""
        if name not in lf_cache:
            found = []
            for suffix in ('.logic.module.ainb', '.logic.root.ainb'):
                p = f'Logic/{name}{suffix}'
                if p in g.romfs.files:
                    for m in ident.finditer(g.romfs.load(p)):
                        s = m.group(0).decode()
                        if flags.offer(s) is not None or mts.murmur(s) in flags.types:
                            found.append(s)
            lf_cache[name] = sorted(set(found))
        return lf_cache[name]

    for b in sorted(g.folder):
        H = {x['Hash']: x for x in acts[b]}
        logic_of = collections.defaultdict(list)
        for grp in statics[b].get('AiGroups', []):
            lg = grp['Logic'].split('/')[-1].replace('.logic.module.ain', '').replace('.logic.root.ain', '')
            for r in grp['References']:
                logic_of[r['Reference']].append(lg)
        out = []
        for x in acts[b]:
            k = T.kind_of(x['Gyaml'])
            if k is None:
                continue
            sk, sp = src_of.get((b, x['Hash']), (None, None))
            o = {'kind': k, 'gyaml': x['Gyaml'], 'hash': x['Hash'], 'name': x.get('Name'),
                 'pos': [round(v, 3) for v in x.get('Translate', [0, 0, 0])],
                 'placement': sk, 'src': f'{sp}: Actors[Hash={x["Hash"]}]'}
            # can the file's coordinate be trusted at run time: a Static placement does not move; a Dynamic one is
            # a live actor (MoveRadius: it wanders that far; on a rail: it follows the rail; Presence: it exists only
            # under a flag; a pickup or a breakable leaves when used)
            mob = []
            if x.get('MoveRadius'):
                mob.append(f'wanders up to {round(x["MoveRadius"], 1)} m (MoveRadius)')
            if x.get('Rails'):
                mob.append('follows a rail (Rails)')
            if x.get('Presence'):
                mob.append('exists only under a flag (Presence)')
            if x.get('IsPhysicsStable') is not None:
                mob.append('physics body (IsPhysicsStable)')
            # the Static/Dynamic file split is not a mobility mark (most enemies are in the Static file): fixed is by
            # kind (the tables' fixed_kinds), for structural objects that carry no moving field
            o['fixed'] = not mob and k in T.fixed_kinds
            if mob:
                o['moves'] = mob
            if x.get('Rotate'):
                o['rot'] = [round(v, 4) for v in x['Rotate']]
            if x.get('Scale'):
                o['scale'] = [round(v, 3) for v in x['Scale']]
            fl = {}
            if x['Hash'] in flags.b64:
                fl['self'] = f'Bool64bitKey {x["Hash"]}'
            if x.get('Presence'):
                pr = x['Presence']
                h = flags.offer(pr.get('FlagName'))
                fl['presence'] = {'flag': pr.get('FlagName'), 'negated': pr.get('IsNegation'),
                                  'type': flags.types.get(h) if h else None}
            dyn = x.get('Dynamic') or {}
            params_f = {}
            for dk, dv in dyn.items():
                if isinstance(dv, str) and dv:
                    h = flags.offer(dv)
                    for pre in (T.flags.played_prefix, T.flags.talked_prefix):
                        flags.offer(pre + dv)
                    if T.actors.param_flag_key_re.search(dk) or h:
                        params_f[dk] = dv
            if params_f:
                fl['params'] = params_f
            if k == 'person':
                pre = T.flags.talked_prefix
                if flags.offer(pre + x['Gyaml']) or (pre + x['Gyaml']) in flags.names.values():
                    fl['talked'] = pre + x['Gyaml']
            if fl:
                o['flags'] = fl
            if x.get('Links'):
                o['links'] = [{'name': l.get('Name'), 'to': H[l['Dst']]['Gyaml'] if l['Dst'] in H else None,
                               'to_hash': l['Dst']} for l in x['Links']]
            if logic_of.get(x['Hash']):
                o['logic'] = sorted(set(logic_of[x['Hash']]))
                lf = sorted({f for lg in o['logic'] for f in logic_flags(lg)})
                if lf:
                    o.setdefault('flags', {})['logic'] = lf
            if dyn and k in ('exit', 'chest', 'switch', 'door', 'lock', 'warp', 'event', 'sign'):
                o['params'] = {dk: dv for dk, dv in dyn.items() if isinstance(dv, (str, int, float, bool))}
            out.append(o)
        objects[b] = out

    # ------------------------------------------------------------------------------------------------- nav
    navinfo = {}
    if 'nav' in only:
        for b in bancs:
            t1 = time.time()
            prm = params.get(b, {})
            try:
                if prm.get(T.areas.stitched_key) == T.areas.stitched_value or any(
                        p.startswith(f'Phive/StitchedNavMesh/{b}/') for p in g.romfs.files):
                    nav = navmesh.stitched(g.romfs.load, g.romfs.files, b)
                else:
                    nav = navmesh.single(g.romfs.load, b)
            except KeyError:
                navinfo[b] = {'nav': None}
                say(f'nav {b}: no nav mesh')
                continue
            A = navgraph.Area(b, nav=nav)
            climb = [o for o in objects.get(b, []) if o['kind'] == 'climbable']
            crawl = [o for o in objects.get(b, []) if o['kind'] == 'crawl']
            nav['xlinks'] = navgraph.compute_xlinks(A, climb, crawl, anchor=T.actors.crawl_anchor)
            nav['components'] = len(A.comp_size)
            navmesh.save(nav, out_dir / 'nav' / f'{b}.json.gz')
            kinds = collections.Counter(l['kind'] for l in nav['xlinks'])
            navinfo[b] = {'nav': nav['source'][0] if len(nav['source']) == 1 else f'{len(nav["source"])} stitched tiles',
                          'faces': len(nav['faces']), 'components': len(A.comp_size),
                          'largest_component': max(A.comp_size) if A.comp_size else 0,
                          'erosion': round(nav['erosion'], 3), 'xlinks': dict(kinds)}
            say(f'nav {b}: {len(nav["faces"])} faces, {len(A.comp_size)} components, links {dict(kinds)} '
                f'({time.time() - t1:.1f} s)')
        (out_dir / 'navinfo.json').write_text(json.dumps(navinfo, indent=1))
    elif (out_dir / 'navinfo.json').is_file():
        navinfo = json.loads((out_dir / 'navinfo.json').read_text())

    if 'model' not in only:
        return
    from worldmodel import model
    model.write(g, mts, T, out_dir, acts, statics, params, objects, flags, navinfo, say)
    say(f'build: done in {time.time() - t0:.0f} s')


if __name__ == '__main__':
    main()
