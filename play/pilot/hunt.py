#!/usr/bin/env python3
"""The hunt: N sessions of the pilot playing (free roam, a chapter, a co-op pair) inside ONE hold, with the detectors watching, a repro
packet for every new finding, a table of what was found, and replays of the new ones. Built to run as a nightly job.

    hunt.py plan   --out DIR --name NAME [--seed S] [--solo N] [--pairs M] --library DIR --copies A[,B] --pilot pilot.py [--world DIR]
                   [--chapters chapters.json] [--pair-case case.toml ...] [--areas a,b] [--hold-seconds S] [--wall S] [--config cfg.json]
    hunt.py check  PLAN                         the plan, its paths, the copies and the folder it would write: changes nothing
    hunt.py run    PLAN --out DIR               inside the hold `queue` takes (or by hand with the same care); DIR must not exist
    hunt.py queue  PLAN [--dry-run]             ONE waiter: the quiet lock, the measuring lock, `timeout`, `run` (no GPU gate: the games ask)
    hunt.py nightly TEMPLATE [--date D] [--dry-run]   tonight's plan from the date's seed (same date, same plan), checked and queued: the cron / timer entry
    hunt.py analyze FOLDER... [--out DIR] [--plan PLAN]    the detectors, the table of known findings and the packets over sessions already played
    hunt.py replay PACKET [--copy C] [--wall S] [--out DIR]   re-drive a packet's inputs in a game (inside a hold) and say what it found
    hunt.py replay-plan PACKET --plan P --out D --name N   a plan of one pair session that re-runs a pair packet's case (fresh rendezvous folder); queue it
    hunt.py verdict PACKET HUNTDIR              did the packet's key fire again in that replay hold? written to <packet>/replay/replay.json
    hunt.py table  DIR                          the findings table of a hold again
    hunt.py score  FOLDER... --name N --ledger L --registry K [--passive RUNS...] [--places P] [--md OUT]   the round's scorecard, the trend, passive coverage, the next plan

The plan (JSON; relative paths are read from the plan's folder). Machine paths, saves and segments live in the plan and in private files
beside it, never in this code:
    {"name": "hold-1", "hold_seconds": 2400, "copy": ".../<copy prefix>x-a", "copy_b": ".../<copy prefix>x-b", "pilot": ".../pilot.py",
     "library": ".../saves", "coopplay": ".../coopplay.py", "registry": "known.json", "bounds": "bounds.json", "baseline": "known-log.json",
     "config": {"softlock_s": 60}, "budget": {"usd": 3.0, "seconds": 2200}, "vision": {"enabled": true, "max": 12}, "replay_new": 2,
     "sessions": [{"name": "roam-1", "kind": "solo", "save": "<library entry>", "segment": "roam-1.toml", "wall": 200, "shots": 90,
                   "humanize": 2, "seed": 11, "decider": "rules", "env": ["HSAP_ANALOG=1"]},
                  {"name": "pair-1", "kind": "pair", "case": "pair-1.toml", "hold_s": 800}]}

A solo session is `pilot.py run` (its own hsap, its own gate request); a Watcher thread reads its live folder every few seconds and stops
the session early on a hang (the game gave no sample for hang_s) or, a little after, on a soft-lock; it also looks at the newest periodic picture
and takes a burst of consecutive pictures through the game's own control socket when one is suspicious (burst.py: the flicker check), and at a
still moment now and then (a probe). A solo session may carry a `place` ({"to", "age", "hour"}: Link is put there by hsdebug before the pilot's
first decision, placement.py; the segment says so in its [place] table); `hunt.py plan --places F --placed N` makes such roams. The hold records
the kernel's pressure counters once a second (psi.jsonl, a slice beside each session): a stall the machine's pressure explains is `info`. A pair session is `coopplay.py inner`
(its own timeout); its detectors are bughunt's plus the co-op runner's own. After each session its artefacts are copied under DIR/<name>/,
the detectors run, every finding goes through the table of known findings (a key seen before is a duplicate: a count, no packet) and every
new one gets a packet under DIR/packets/. Processes are only ever stopped by pid (SIGTERM, then SIGKILL): the pilot's family and the
processes carrying the session's tag as a whole word. The hold's budget (hold_seconds - reserve) decides whether the next session starts.
Exit: 0 finished (read result.json and table.md), 2 plan refused, 3 a game of the copy is running, 143 stopped by a signal.
This machine's own settings (environment variables, no default; what needs one is refused, naming it): HUNT_COPY_PREFIX, the name every game
copy a hold may touch starts with (a plan's copies must be absolute paths of folders so named); HUNT_QUIET and HUNT_MEASURING, the main
lane's two lock files that `queue` waits on (or `queue_command(quiet=, measuring=)`).
"""
import argparse
import datetime
import json
import math
import os
import random
import re
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bughunt  # noqa: E402
import bugpacket  # noqa: E402
import burst  # noqa: E402
import placement  # noqa: E402
import score  # noqa: E402
import scenario  # noqa: E402

ENV_COPY_PREFIX, ENV_QUIET, ENV_MEASURING = 'HUNT_COPY_PREFIX', 'HUNT_QUIET', 'HUNT_MEASURING'   # this machine's own names (a copy folder's name, the main lane's lock files): environment, no default
NAME_RE = re.compile(r'^[A-Za-z0-9._-]+$')
ENV_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*=')
DECIDERS = ('rules', 'openai-decisions')
RESERVE_S = float(os.environ.get('HUNT_RESERVE', '90'))
EXTRA_S = float(os.environ.get('HUNT_EXTRA', '90'))         # a pilot may take wall + this (start-up is not in its wall)
BOOT_S = float(os.environ.get('HUNT_BOOT', '10'))           # an allowance for the queue at the gate when a session is fitted into the hold (`wall` counts from the game's start, boot included)
TERM_GRACE = float(os.environ.get('HUNT_TERM_GRACE', '20'))
WATCH_EVERY = float(os.environ.get('HUNT_WATCH_EVERY', '3'))
SOFTLOCK_AFTER_S = float(os.environ.get('HUNT_SOFTLOCK_AFTER', '20'))
END_HOLD_S = 4
PLAN_KEYS = {'name', 'hold_seconds', 'copy', 'copy_b', 'pilot', 'library', 'coopplay', 'registry', 'bounds', 'baseline', 'config', 'budget', 'vision',
             'replay_new', 'sessions', 'max_packets', 'burst', 'world'}
SESSION_KEYS = {'name', 'kind', 'save', 'segment', 'wall', 'shots', 'env', 'decider', 'humanize', 'seed', 'boot', 'max_decisions', 'case', 'hold_s',
                'allow_usd', 'vision', 'burst', 'place', 'scenario', 'allow_unconfirmed', 'expect_key', 'label'}
GAME_FILES = ('env-used.txt', 'summary.txt', 'exit.txt', 'args.txt', 'wall.txt', 'kernel.txt', 'kernel-status.json')
CHILD_MARKS = ('hsap.py', 'hs-run.sh')


class PlanError(Exception):
    pass


class Terminated(BaseException):
    pass


# ====================================================================== the plan

def _num(d, key, default, kind=int, minimum=1):
    v = d.get(key, default)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or (kind is int and v != int(v)) or v < minimum:
        raise PlanError(f'{key}: a number of {minimum} or more{" (whole)" if kind is int else ""}, got {v!r}')
    return kind(v)


def _path(value, base):
    p = Path(str(value)).expanduser()
    return str(p if p.is_absolute() else Path(os.path.abspath(base / p)))


def load_plan(path):
    path = Path(path).resolve()
    try:
        d = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        raise PlanError(f'cannot read the plan {path}: {e}')
    if not isinstance(d, dict):
        raise PlanError('the plan is not a JSON object')
    bad = sorted(set(d) - PLAN_KEYS)
    if bad:
        raise PlanError('unknown plan keys: ' + ', '.join(bad))
    for k in ('name', 'hold_seconds', 'copy', 'pilot', 'sessions'):
        if k not in d:
            raise PlanError(f'the plan has no {k}')
    base = path.parent
    if not isinstance(d['name'], str) or not NAME_RE.match(d['name']):
        raise PlanError('name: letters, digits, . _ - only')
    plan = {'name': d['name'], 'hold_seconds': _num(d, 'hold_seconds', None, float, 1), 'copy': _path(d['copy'], base), 'pilot': _path(d['pilot'], base),
            'copy_b': _path(d['copy_b'], base) if d.get('copy_b') else None, 'library': _path(d['library'], base) if d.get('library') else None,
            'coopplay': _path(d['coopplay'], base) if d.get('coopplay') else str(HERE.parent.parent / 'coop-play' / 'coopplay.py'),
            'registry': _path(d['registry'], base) if d.get('registry') else None, 'bounds': _path(d['bounds'], base) if d.get('bounds') else None,
            'baseline': _path(d['baseline'], base) if d.get('baseline') else None, 'config': dict(d.get('config') or {}),
            'budget': dict(d.get('budget') or {}), 'vision': dict(d.get('vision') or {}), 'replay_new': int(d.get('replay_new', 0)),
            'max_packets': int(d.get('max_packets', 12)), 'burst': bool(d.get('burst', True)), 'world': _path(d['world'], base) if d.get('world') else None,
            'sessions': [], 'plan_path': str(path)}
    try:
        bughunt.Config.from_dict(plan['config'])
    except (ValueError, TypeError) as e:
        raise PlanError(f'config: {e}')
    if not isinstance(d['sessions'], list) or not d['sessions']:
        raise PlanError('sessions: a non-empty list')
    names = set()
    for i, s in enumerate(d['sessions']):
        if not isinstance(s, dict):
            raise PlanError(f'session {i} is not an object')
        bad = sorted(set(s) - SESSION_KEYS)
        if bad:
            raise PlanError(f'session {i}: unknown keys: ' + ', '.join(bad))
        if not isinstance(s.get('name'), str) or not NAME_RE.match(s['name']):
            raise PlanError(f'session {i}: name: letters, digits, . _ - only')
        if s['name'] in names:
            raise PlanError(f'duplicate session name {s["name"]}')
        names.add(s['name'])
        kind = s.get('kind', 'solo')
        if kind not in ('solo', 'pair'):
            raise PlanError(f'session {s["name"]}: kind is solo or pair')
        env = s.get('env', [])
        if not isinstance(env, list) or any(not isinstance(x, str) or not ENV_RE.match(x) for x in env):
            raise PlanError(f'session {s["name"]}: env is a list of "K=V" strings')
        if any(x.startswith('OPENAI_API_KEY=') for x in env):
            raise PlanError(f'session {s["name"]}: the key comes from the caller\'s environment, never from a plan')
        row = {'name': s['name'], 'kind': kind, 'env': list(env), 'tag': f'{plan["name"]}-{s["name"]}', 'expect_key': s.get('expect_key'), 'label': s.get('label')}
        if kind == 'solo':
            for k in ('save', 'scenario' if s.get('scenario') else 'segment'):
                if not isinstance(s.get(k), str) or not s[k]:
                    raise PlanError(f'session {s["name"]}: {k} is required (a string)')
            sc_doc = None
            if s.get('scenario'):   # a scenario session: hsap plays the scenario's compiled steps after the placement (no model, no pilot)
                try:
                    sc_doc = scenario.load(_path(s['scenario'], base))
                except scenario.ScenarioError as e:
                    raise PlanError(f'session {s["name"]}: {e}')
                for e in sc_doc.get('env') or []:   # the scenario's own env (the profile switches an issue asks for) joins the session's
                    if not isinstance(e, str) or not ENV_RE.match(e):
                        raise PlanError(f'session {s["name"]}: the scenario\'s env is a list of "K=V" strings')
                    if e not in row['env']:
                        row['env'].append(e)
                if scenario.unconfirmed(sc_doc) and not s.get('allow_unconfirmed'):
                    raise PlanError(f'session {s["name"]}: the scenario has unconfirmed actions ({", ".join(scenario.unconfirmed(sc_doc))}): a person confirms them, or allow_unconfirmed'
                                    )
            decider = s.get('decider', 'rules')
            if decider not in DECIDERS:
                raise PlanError(f'session {s["name"]}: decider is one of {", ".join(DECIDERS)}')
            h = s.get('humanize')
            if h is not None and (not isinstance(h, int) or isinstance(h, bool) or not 0 <= h <= 3):
                raise PlanError(f'session {s["name"]}: humanize is 0 to 3')
            if s.get('place') is not None:
                try:
                    placement.check_spec(s['place'])
                except ValueError as e:
                    raise PlanError(f'session {s["name"]}: {e}')
            row.update(scenario=_path(s['scenario'], base) if s.get('scenario') else None, save=s['save'],
                       segment=_path(s['segment'], base) if s.get('segment') else None, decider='scenario' if s.get('scenario') else decider, wall=_num(s, 'wall', 180), shots=_num(s, 'shots', 90),
                       humanize=h, seed=s.get('seed'), boot=s.get('boot'), max_decisions=s.get('max_decisions'), allow_usd=s.get('allow_usd'),
                       vision=s.get('vision'), burst=bool(s.get('burst', plan['burst'])), place=s.get('place') or (scenario.place_spec(sc_doc) if sc_doc else None))
            row['min_s'] = row['wall'] + BOOT_S + 30
        else:
            if not s.get('case'):
                raise PlanError(f'session {s["name"]}: a pair needs a case')
            row.update(case=_path(s['case'], base), hold_s=_num(s, 'hold_s', 800, float, 60))
            if s.get('scenario'):   # a pair scenario (scenario.py pair-files made the case): judged by its checks after the session
                try:
                    pdoc = scenario.load(_path(s['scenario'], base))
                except scenario.ScenarioError as e:
                    raise PlanError(f'session {s["name"]}: {e}')
                if pdoc.get('players') != 2:
                    raise PlanError(f'session {s["name"]}: a pair session needs a scenario with players = 2')
                if scenario.unconfirmed(pdoc) and not s.get('allow_unconfirmed'):
                    raise PlanError(f'session {s["name"]}: the scenario has unconfirmed actions ({", ".join(scenario.unconfirmed(pdoc))})')
                row['scenario'] = _path(s['scenario'], base)
            row['min_s'] = row['hold_s'] + 30
        plan['sessions'].append(row)
    return plan


def save_path(plan, name):
    s = Path(name)
    if s.is_absolute():
        return s
    if not plan['library']:
        raise PlanError(f'save {name!r} is a library name and the plan has no library')
    return Path(plan['library']) / s


def copy_prefix():
    """The name every game copy of a hold starts with: this machine's setting, or None."""
    return os.environ.get(ENV_COPY_PREFIX) or None


def copy_errors(copy):
    prefix = copy_prefix()
    if not prefix:
        return [f'set {ENV_COPY_PREFIX} to the name every game copy a hold may use starts with (this machine\'s own value; there is no default)']
    p = Path(copy)
    if not p.is_absolute() or not p.name.startswith(prefix) or p.name == prefix:
        return [f'the copy {copy} is not a /.../{prefix}* folder']
    if not p.is_dir():
        return [f'the copy {copy} is not a folder']
    if not Path(os.path.realpath(p)).name.startswith(prefix):
        return [f'the copy {copy} resolves to {os.path.realpath(p)}, not a {prefix}* folder']
    return []


def plan_errors(plan, out=None):
    errs = copy_errors(plan['copy'])
    pilot = Path(plan['pilot'])
    if not pilot.is_file():
        errs.append(f'pilot {pilot} is not a file')
    if any(s['kind'] == 'pair' for s in plan['sessions']):
        if not plan['copy_b']:
            errs.append('a pair session needs copy_b')
        else:
            errs += copy_errors(plan['copy_b'])
        if not Path(plan['coopplay']).is_file():
            errs.append(f'coopplay {plan["coopplay"]} is not a file')
    if plan['hold_seconds'] <= RESERVE_S:
        errs.append(f'hold_seconds {plan["hold_seconds"]} leaves no budget after the {RESERVE_S:.0f} s reserve')
    for k in ('bounds', 'baseline'):
        if plan[k] and not Path(plan[k]).is_file():
            errs.append(f'{k} {plan[k]} is not a file')
    for s in plan['sessions']:
        if s['kind'] == 'solo':
            try:
                if not save_path(plan, s['save']).is_dir():
                    errs.append(f'session {s["name"]}: save {save_path(plan, s["save"])} is not a folder')
            except PlanError as e:
                errs.append(str(e))
            if s.get('segment') and not Path(s['segment']).is_file():
                errs.append(f'session {s["name"]}: segment {s["segment"]} is not a file')
            if (pilot.resolve().parent / 'runs' / s['tag']).exists():
                errs.append(f'session {s["name"]}: the pilot already has a run folder {s["tag"]}')
        elif not Path(s['case']).is_file():
            errs.append(f'session {s["name"]}: case {s["case"]} is not a file')
    if out is not None and Path(out).exists():
        errs.append(f'{out} exists (a hunt folder is never reused)')
    return errs


# ====================================================================== the plan's generator: random starts, seeds, free-roam segments

class WorldRoam:
    """Free-roam targets from the private world model: random walkable points of an area that its planner can reach from the one before,
    15 to 70 m apart. world_dir is the data folder of the world model (`world/`; the planner's code is `worldmodel/`). Reads data; names no place."""

    def __init__(self, world_dir):
        self.dir = Path(world_dir)
        sys.path.insert(0, str(HERE.parent))
        from worldmodel import plan as wplan   # noqa: E402  (the code; world_dir is the data it reads)
        wplan.use(self.dir)
        self.plan = wplan

    def centroids(self, area):
        import gzip
        p = self.dir / 'nav' / f'{area}.json.gz'
        if not p.is_file():
            return []
        d = json.load(gzip.open(p, 'rt'))
        v, out = d['verts'], []
        for face in d['faces']:
            idx = face[:-1] if len(face) > 3 and isinstance(face[-1], int) and face[-1] >= len(v) // 3 else face
            idx = [i for i in idx if 0 <= i < len(v) // 3]
            if idx:
                out.append((sum(v[i * 3] for i in idx) / len(idx), sum(v[i * 3 + 1] for i in idx) / len(idx), sum(v[i * 3 + 2] for i in idx) / len(idx)))
        return out

    def nearest(self, area, x, z):
        """(x, z, y) of the walkable point (a nav-mesh face centre) nearest to (x, z): the planner needs the level's height too."""
        pts = self.centroids(area)
        q = min(pts, key=lambda p: math.hypot(p[0] - x, p[2] - z))
        return (q[0], q[2], q[1])

    def start(self, area):
        """[x, y, z] where a placement in `area` puts Link: the area's default start (else its entrance, else the first one named) from areas.json."""
        try:
            starts = json.loads((self.dir / 'areas.json').read_text())[area]['starts']
        except (OSError, ValueError, KeyError, TypeError):
            return None
        for name in ('(default)', 'EntrancePos', area):
            if name in starts and starts[name].get('pos'):
                return list(starts[name]['pos'])
        first = next((v['pos'] for v in starts.values() if isinstance(v, dict) and v.get('pos')), None)
        return list(first) if first else None

    def targets(self, area, start, rng, k, min_m=15.0, max_m=70.0, max_tries=6000):
        pts = self.centroids(area)
        if not pts:
            return []
        out, cur, tries, fails = [], (start[0], start[2], start[1]), 0, 0
        near_pt = min(pts, key=lambda q: math.hypot(q[0] - cur[0], q[2] - cur[1]))   # begin at the mesh point nearest to the start: the planner refuses a start it
        cur = (near_pt[0], near_pt[2], near_pt[1])                                    # finds off the mesh (a start on another level, in a corner)
        origin = cur
        while len(out) < k and tries < max_tries:
            near = [q for q in pts if min_m * 0.6 <= math.hypot(q[0] - cur[0], q[2] - cur[1]) <= max_m]   # (the way is never shorter than the line)
            if not near or fails >= 60:   # a dead end (nothing reachable 15 to 70 m on, or sixty tries that failed): go on from an earlier checkpoint, or the start
                cur = rng.choice([(x, z, y) for x, z, y in out] + [origin]) if out else origin
                fails = 0
                if not near and tries >= max_tries - 1:
                    break
                if not [q for q in pts if min_m * 0.6 <= math.hypot(q[0] - cur[0], q[2] - cur[1]) <= max_m]:
                    tries += 1
                    continue
                continue
            tries += 1
            x, y, z = rng.choice(near)
            r = self.plan.plan(area, (cur[0], cur[1]), (x, z), from_y=cur[2], to_y=y, radius=2.5)
            if r.get('ok') and min_m <= r.get('length', 0.0) <= max_m:
                out.append((round(x, 2), round(z, 2), round(y, 2)))
                cur = (x, z, y)
                fails = 0
            else:
                fails += 1
        return out


def place_toml(place):
    """the segment's `[place]` table (placement.py)"""
    placement.check_spec(place)
    return '\n[place]\n' + ''.join(f'{k} = {json.dumps(place[k])}\n' for k in ('to', 'age', 'hour') if place.get(k) is not None)


def roam_segment_toml(name, area, save, targets, wall, humanize, watch=(), place=None):
    """The text of a free-roam segment: one reach goal over the targets (it never meets its flag: the run ends when the targets are done or
    the budget is)."""
    ts = ',\n           '.join(f'{{name = "r{i + 1}", at = [{x:.2f}, {z:.2f}], y = {y:.2f}, kind = "reach", radius = 2.5}}' for i, (x, z, y) in enumerate(targets))
    w = ', '.join(json.dumps(x) for x in watch)
    return (f'# a generated free-roam segment (hunt.py plan): private, never published\nname = "{name}"\n'
            f'what = "free roam over random walkable points of {area}"\narea = "{area}"\nsave = "{save}"\nboot = "continue"\nwall = {wall}\n'
            f'budget_seconds = {max(30, wall - 110)}\nmax_decisions = {max(40, wall * 2)}\nhumanize = {humanize}\n' + (f'watch = [{w}]\n' if watch else '') +
            (place_toml(place) if place else '') +
            f'\n[[goal]]\nname = "roam"\nwhat = "You are Link, free roaming. Walk the checkpoints in order and stop within about 2 m of each; when a walk ends reached, choose next-target; a stuck walk is solved by stepping back or aside."\n'
            f'flag = "HuntRoam_Done=1"\nkind = "reach"\ntargets = [{ts}]\n')


def save_starts(library):
    """{save name: (area, [x, y, z])} from the library's catalogue.json: where each save puts Link."""
    cat = json.loads((Path(library) / 'catalogue.json').read_text())
    out = {}
    for name, e in cat.items():
        sl = ((e.get('decoded') or {}).get('slots') or [{}])[0]
        if sl.get('area') and sl.get('pos'):
            out[name] = (sl['area'], sl['pos'])
    return out


def make_plan(args, roam=None):
    """A plan and its generated segments, from a seed: solo sessions (a chapter from the chapters file, else free roam from a random save
    of the allowed areas) and pairs (a random case of --pair-case). Same seed, same plan."""
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(f'{args.name}:{args.seed}')
    starts = save_starts(args.library)
    areas = set(args.areas.split(',')) if args.areas else None
    pool = sorted(n for n, (a, _) in starts.items() if areas is None or a in areas)
    chapters = json.loads(Path(args.chapters).read_text()) if args.chapters else []
    copies = args.copies.split(',')
    sessions = []
    for i in range(args.solo):
        name = f'solo-{i + 1}'
        seed = rng.randrange(1, 2 ** 31)
        humanize = rng.choice((2, 3))
        if chapters and rng.random() < args.chapter_share:
            ch = rng.choice(chapters)
            sessions.append({'name': name, 'kind': 'solo', 'save': ch['save'], 'segment': ch['segment'], 'wall': ch.get('wall', args.wall), 'shots': 90,
                             'humanize': humanize, 'seed': seed, 'decider': 'rules', 'env': ['HSAP_ANALOG=1'], 'chapter': ch.get('name')})
            continue
        if not pool:
            raise PlanError('no save of the library starts in an allowed area')
        save = rng.choice(pool)
        area, pos = starts[save]
        tg = roam.targets(area, pos, random.Random(seed), args.targets) if roam else []
        if not tg:
            raise PlanError(f'no free-roam targets for {area} (a save in an area without nav data?)')
        seg = out / f'{name}.toml'
        seg.write_text(roam_segment_toml(f'{args.name}-{name}', area, save, tg, args.wall, humanize))
        sessions.append({'name': name, 'kind': 'solo', 'save': save, 'segment': seg.name, 'wall': args.wall, 'shots': 90, 'humanize': humanize,
                         'seed': seed, 'decider': 'rules', 'env': ['HSAP_ANALOG=1']})
    places = json.loads(Path(args.places).read_text()) if getattr(args, 'places', None) else []
    order = []
    for i in range(getattr(args, 'placed', 0) or 0):   # roams that start where hsdebug puts Link: any destination the game lists, an age, an hour
        if not places:
            raise PlanError('--placed needs --places (a JSON list of {"to", "age", "hour", "area", "save"} entries)')
        if not order:   # (each entry once, in a seeded order, before any is used again: a hold covers as many places as it can)
            order = list(places)
            rng.shuffle(order)
        pl = order.pop()
        name = f'placed-{i + 1}'
        seed = rng.randrange(1, 2 ** 31)
        humanize = rng.choice((2, 3))
        spec = {k: pl[k] for k in ('to', 'age', 'hour') if pl.get(k) is not None}
        area = pl.get('area') or spec.get('to')
        spec.setdefault('to', area)
        try:
            placement.check_spec(spec)
        except ValueError as e:
            raise PlanError(f'places: {e}')
        save = pl.get('save') or (pool[0] if pool else None)
        if not save:
            raise PlanError(f'placed session {name}: no save to boot from (the entry names none and no save of the library is in an allowed area)')
        pos = roam.start(area) if roam else None
        tg = roam.targets(area, pos, random.Random(seed), args.targets) if roam and pos else []
        if not tg:
            raise PlanError(f'no free-roam targets for the placed area {area} (no start in the world model, or no nav data)')
        seg = out / f'{name}.toml'
        seg.write_text(roam_segment_toml(f'{args.name}-{name}', area, save, tg, args.wall, humanize, place=spec))
        sessions.append({'name': name, 'kind': 'solo', 'save': save, 'segment': seg.name, 'wall': args.wall, 'shots': 90, 'humanize': humanize,
                         'seed': seed, 'decider': 'rules', 'env': ['HSAP_ANALOG=1'] + list(getattr(args, 'session_env', None) or []), 'place': spec})
    cases = list(args.pair_case or [])
    for j in range(args.pairs):
        if not cases:
            raise PlanError('--pairs needs --pair-case')
        sessions.append({'name': f'pair-{j + 1}', 'kind': 'pair', 'case': rng.choice(cases), 'hold_s': args.pair_hold})
    plan = {'name': args.name, 'hold_seconds': args.hold_seconds, 'copy': copies[0], 'pilot': args.pilot, 'library': args.library, 'sessions': sessions}
    if len(copies) > 1:
        plan['copy_b'] = copies[1]
    if args.config:
        plan['config'] = json.loads(Path(args.config).read_text())
    for k in ('bounds', 'baseline', 'registry', 'coopplay'):
        if getattr(args, k, None):
            plan[k] = getattr(args, k)
    if args.budget_usd is not None:
        plan['budget'] = {'usd': args.budget_usd}
    (out / 'plan.json').write_text(json.dumps(plan, indent=1) + '\n')
    return out / 'plan.json'


# ====================================================================== processes: only ever by pid

class Proc:
    __slots__ = ('pid', 'ppid', 'state', 'start', 'cmd', 'exe', 'text')

    def key(self):
        return (self.pid, self.start)


def proc_info(pid):
    try:
        raw = Path(f'/proc/{pid}/stat').read_bytes().decode('utf-8', 'replace')
        rest = raw[raw.rindex(')') + 2:].split()
        p = Proc()
        p.pid, p.state, p.ppid, p.start = pid, rest[0], int(rest[1]), int(rest[19])
        if os.stat(f'/proc/{pid}').st_uid != os.getuid():
            return None
        p.cmd = [a.decode('utf-8', 'replace') for a in Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0') if a]
        try:
            p.exe = os.readlink(f'/proc/{pid}/exe')
        except OSError:
            p.exe = ''
        p.text = ' '.join(p.cmd)
        return p
    except (OSError, ValueError, IndexError):
        return None


def snapshot():
    out = []
    for n in os.listdir('/proc'):
        if n.isdigit():
            p = proc_info(int(n))
            if p is not None and p.state not in ('Z', 'X'):
                out.append(p)
    return out


def tag_regex(tag):
    return re.compile(r'(?<![A-Za-z0-9._-])' + re.escape(tag) + r'(?![A-Za-z0-9._-])')


def descendants(procs, root):
    kids = {}
    for p in procs:
        kids.setdefault(p.ppid, []).append(p.pid)
    seen, todo = set(), [root]
    while todo:
        for k in kids.get(todo.pop(), ()):
            if k not in seen:
                seen.add(k)
                todo.append(k)
    return seen


def ancestors(pid):
    seen = set()
    while pid > 1 and pid not in seen:
        seen.add(pid)
        p = proc_info(pid)
        if p is None:
            break
        pid = p.ppid
    return seen


def under(path, folders):
    return any(path == f or path.startswith(f + '/') for f in folders)


def game_processes(copy, exclude=()):
    """Processes of this user running the game of the copy or a wrapper that names a path inside it."""
    spell = tuple(dict.fromkeys((str(copy), os.path.realpath(str(copy)))))
    out = []
    for p in snapshot():
        if p.pid in exclude:
            continue
        wrapper = bool(p.cmd) and os.path.basename(p.cmd[0]) == 'timeout'
        mark = wrapper or any(m in p.text for m in CHILD_MARKS + ('pilot.py',))
        if under(p.exe, spell) or (mark and any(under(a, spell) for a in p.cmd)):
            out.append(p)
    return out


class Family:
    """The processes of one session: the root (the pilot or coopplay), everything below it, and whatever carries the session's tag as a whole
    word and is hsap, hs-run.sh, pilot, coopplay, the timeout wrapper or the game itself. Signalled only as seen (same pid and start time)."""

    def __init__(self, tag, copies, log=print):
        self.tag, self.copies, self.log = tag, [str(c) for c in copies], log
        self.me = ancestors(os.getpid())
        self.tracked = {}

    def spell(self):
        return tuple(dict.fromkeys(x for c in self.copies for x in (c, os.path.realpath(c))))

    def members(self, root_pid):
        procs = snapshot()
        desc = descendants(procs, root_pid) if root_pid else set()
        rx = tag_regex(self.tag)
        sp = self.spell()
        out = []
        for p in procs:
            if p.pid in self.me:
                continue
            tagged = bool(rx.search(p.text))
            mark = any(m in p.text for m in CHILD_MARKS)
            below = p.pid in desc or p.key() in self.tracked
            if root_pid and p.pid == root_pid:
                why = 'root'
            elif below and (tagged or mark):
                why = 'below the root'
            elif tagged and (mark or 'pilot.py' in p.text or 'coopplay.py' in p.text or under(p.exe, sp) or (p.cmd and os.path.basename(p.cmd[0]) == 'timeout')):
                why = 'tagged'
            else:
                continue
            out.append((p, why))
        return out

    def track(self, root_pid):
        for p, _ in self.members(root_pid):
            self.tracked[p.key()] = p.text[:160]

    def signal(self, p, sig):
        cur = proc_info(p.pid)
        if cur is None or cur.start != p.start or cur.state in ('Z', 'X'):
            return False
        try:
            os.kill(p.pid, sig)
        except (ProcessLookupError, PermissionError):
            return False
        self.log(f'  {signal.Signals(sig).name} pid {p.pid}: {p.text[:120]}')
        return True

    def stop(self, proc, grace=TERM_GRACE):
        """SIGTERM every member (and new ones as they appear), SIGKILL what is left after `grace`; by pid only."""
        sent, killed, deadline = set(), False, time.monotonic() + grace
        while True:
            proc.poll()
            members = self.members(proc.pid if proc.returncode is None else None)
            if not members:
                break
            for p, _ in members:
                if (p.key(), 15) not in sent and self.signal(p, signal.SIGTERM):
                    sent.add((p.key(), 15))
            if time.monotonic() >= deadline:
                if killed:
                    self.log('  still alive after SIGKILL: ' + ', '.join(str(p.pid) for p, _ in members))
                    break
                for p, _ in members:
                    if (p.key(), 9) not in sent and self.signal(p, signal.SIGKILL):
                        sent.add((p.key(), 9))
                killed, deadline = True, time.monotonic() + 3
            time.sleep(0.2)
        proc.poll()
        return bool(sent)


# ====================================================================== the watcher

class Watcher(threading.Thread):
    """Reads a running solo session's live files every few seconds with the cheap detectors (hang, soft-lock). `stop_reason` is set when
    the session should end early: the game gave no sample for hang_s (live: the journal's mtime), or a soft-lock was seen SOFTLOCK_AFTER_S ago.
    It stops nothing itself: the runner reads it."""

    def __init__(self, pilot_run, game_run, cfg, alive, every=WATCH_EVERY, clock=time.time, burster=None):
        super().__init__(daemon=True)
        self.pilot_run, self.game_run, self.cfg, self.alive, self.every, self.clock = Path(pilot_run), Path(game_run), cfg, alive, every, clock
        self.stop_reason, self.found, self.seen, self.halt = None, [], set(), threading.Event()
        self.soft_at = None
        self.polls = 0
        self.burster = burster
        self.burst_errors = []

    def poll(self):
        self.polls += 1
        side = bughunt.Side(self.pilot_run, game=self.game_run, pilot=self.pilot_run)
        sp = side.state_path
        if sp is None:
            return
        playing = any(e.get('ev') == 'gameplay' for e in side.events)   # (the boot and the first map's programs may be silent a long time)
        if playing and self.alive() and self.clock() - sp.stat().st_mtime >= self.cfg.hang_s and side.states:
            last = side.states[-1]
            f = bughunt.Finding('hang', 'live', 'error', side.name, f'no state sample for {self.clock() - sp.stat().st_mtime:.0f} s while the game lives (frame {last["frame"]})',
                                evidence={'last_frame': last['frame'], 'journal_age_s': round(self.clock() - sp.stat().st_mtime, 1)},
                                key=bughunt.place_key('hang', 'live', last.get('map'), last.get('pos'), 16.0), **side.at(last['t']))
            self.note(f)
            self.stop_reason = self.stop_reason or 'hang'
        rs = bughunt.analyze_side(side, self.cfg, only=('hang', 'softlock'))
        for name, r in rs.items():
            for f in r.findings:
                if f.severity == 'info':
                    continue
                self.note(f)
                if name == 'softlock' and self.soft_at is None:
                    self.soft_at = self.clock()
        if self.soft_at is not None and self.clock() - self.soft_at >= SOFTLOCK_AFTER_S:
            self.stop_reason = self.stop_reason or 'softlock'
        if self.burster is not None and self.alive():
            try:
                self.burster.poll(side, refresh=lambda: bughunt.Side(self.pilot_run, game=self.game_run, pilot=self.pilot_run))
            except Exception as e:   # noqa: BLE001  a burst that fails is recorded; the cheap detectors go on
                if len(self.burst_errors) < 5:
                    self.burst_errors.append(f'{type(e).__name__}: {str(e)[:160]}')

    def note(self, f):
        k = (f.key, round(f.t or 0))
        if k not in self.seen:
            self.seen.add(k)
            self.found.append(f)

    def run(self):
        while not self.halt.is_set():
            try:
                self.poll()
            except Exception:   # noqa: BLE001  a half-written line is read again next time
                pass
            self.halt.wait(self.every)


PSI_EVERY = float(os.environ.get('HUNT_PSI_EVERY', '1'))
PSI_FILES = (('cpu', 'cpu', 'some'), ('io', 'io', 'some'), ('iof', 'io', 'full'), ('mem', 'memory', 'some'), ('memf', 'memory', 'full'))


class Pressure(threading.Thread):
    """Records the kernel's pressure counters (pressure stall information: the microseconds tasks have waited for the CPU, the disk or memory,
    cumulative) with the load average once a second into one JSONL file, on the monotonic clock the presents and the samples use. A stall
    the detectors find is compared with the counters around it (`bughunt.machine_pressure`): the machine being short of something is told
    from the game stalling by itself. Reads /proc only; a kernel without the files records the load average alone."""

    def __init__(self, path, every=PSI_EVERY, proc='/proc', clock=time.monotonic):
        super().__init__(daemon=True)
        self.path, self.every, self.proc, self.clock = Path(path), every, proc, clock
        self.halt = threading.Event()
        self.rows = 0

    def sample(self):
        row = {'t': round(self.clock(), 3)}
        for key, name, which in PSI_FILES:
            try:
                with open(f'{self.proc}/pressure/{name}') as f:
                    for ln in f:
                        if ln.startswith(which + ' '):
                            row[key] = int(re.search(r'total=(\d+)', ln).group(1))
            except (OSError, AttributeError, ValueError):
                pass
        try:
            with open(f'{self.proc}/loadavg') as f:
                row['load1'] = float(f.read().split()[0])
        except (OSError, ValueError, IndexError):
            pass
        return row

    def run(self):
        with open(self.path, 'a', buffering=1) as f:
            while True:
                try:
                    f.write(json.dumps(self.sample()) + '\n')
                    self.rows += 1
                except OSError:
                    pass
                if self.halt.wait(self.every):
                    return


def slice_psi(src, t0, t1, dst):
    """The recorder's rows from t0 to t1 (monotonic seconds) as a file beside one session's evidence."""
    rows = []
    try:
        for ln in Path(src).read_text().splitlines():
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if isinstance(r, dict) and t0 <= r.get('t', -1) <= t1:
                rows.append(ln)
    except OSError:
        return 0
    Path(dst).write_text('\n'.join(rows) + ('\n' if rows else ''))
    return len(rows)


# ====================================================================== the hunt

def dump_json(path, obj):
    tmp = Path(str(path) + '.tmp')
    tmp.write_text(json.dumps(obj, indent=1) + '\n')
    os.replace(tmp, path)


def read_text(path):
    try:
        return Path(path).read_text(errors='replace').strip()
    except OSError:
        return None


def reflink_copy(sources, dest_dir):
    sources = [str(s) for s in sources]
    dest_dir.mkdir(parents=True, exist_ok=True)
    for i in range(0, len(sources), 100):
        batch = sources[i:i + 100]
        r = subprocess.run(['cp', '--reflink=auto', '-p', '-t', str(dest_dir)] + batch, capture_output=True)
        if r.returncode != 0:
            for s in batch:
                shutil.copy2(s, dest_dir / os.path.basename(s))


def gzip_file(src, dst):
    import gzip
    with open(src, 'rb') as a, gzip.open(dst, 'wb') as b:
        shutil.copyfileobj(a, b)


def session_from_folder(folder):
    """What a session folder says of how it was played, for a packet made after the fact (`hunt.py analyze --packets`): a pair has its case
    source beside the sides; a solo has the pilot's summary.json (the save and boot of its hsap command line, the seed, the copy)."""
    folder = Path(folder)
    info = {'run': folder.name}
    if (folder / 'case-source.toml').is_file() and (folder / 'session.json').is_file():
        info.update(kind='pair', case=str(folder / 'case-source.toml'))
        return info
    info['kind'] = 'solo'
    try:
        summary = json.loads((folder / 'pilot' / 'summary.json').read_text())
    except (OSError, ValueError):
        return info
    cmd = summary.get('runner') or []
    for flag, key in (('--save', 'save'), ('--boot', 'boot'), ('--shots', 'shots')):
        if flag in cmd and cmd.index(flag) + 1 < len(cmd):
            info[key] = cmd[cmd.index(flag) + 1]
    if info.get('save'):
        info['save_name'] = Path(info['save']).name
    hz = summary.get('humanize') or {}
    pl = summary.get('place') or {}
    info.update(copy=summary.get('copy'), seed=hz.get('seed'), humanize=hz.get('level'), decider=summary.get('decider'),
                place={k: pl[k] for k in ('to', 'age', 'hour') if pl.get(k) is not None} or None)
    return {k: v for k, v in info.items() if v is not None}


def handle_finding(registry, f, run, sides, session, packets_dir, counter, max_packets):
    """One finding through the table of known findings: a key seen before is a duplicate (a count and a run, no new packet); a new one gets a
    packet before it is entered, so the table keeps the packet's place. Returns (status, packet or None); `counter` is a one-item list."""
    known = registry.lookup(f.key)
    packet = None
    if known is None and f.status != 'artefact' and counter[0] < max_packets:
        counter[0] += 1
        packet = bugpacket.make_packet(Path(packets_dir) / f'{counter[0]:03d}-{f.key.replace(":", "_")}', f, sides, session, registry)
    st, entry = registry.register(f, run, packet)
    f.status = 'artefact' if f.status == 'artefact' else ('duplicate' if st == 'duplicate' else 'new')
    return f.status, packet or (Path(entry['packet']) if entry.get('packet') else None)


def recover_pilot_records(rdir, since=0.0):
    """A pair's pilot that the runner cut before the pilot wrote its summary leaves its record (out.jsonl, steps.txt) only in the pilot's live folder, which the
    runner does not copy: the verdict's `reached` gate then reads no steps for that side. Copies the newest live record (newer than `since`, a unix time) of each
    pilot side that has none in the session folder `rdir`. Returns the sides it filled."""
    rdir = Path(rdir)
    try:
        case = json.loads((rdir / 'case.json').read_text())
    except (OSError, ValueError):
        return []
    filled = []
    for side, sd in sorted((case.get('sides') or {}).items()):
        pl = sd.get('pilot') or {}
        dest = rdir / side / 'pilot'
        if sd.get('driver') != 'pilot' or not pl.get('runs') or (dest / 'out.jsonl').is_file():
            continue
        live = [p for p in Path(pl['runs']).glob(f'{case.get("name", "")}-*-{side}/live') if (p / 'out.jsonl').is_file() and (p / 'out.jsonl').stat().st_mtime >= since]
        if not live:
            continue
        best = max(live, key=lambda p: (p / 'out.jsonl').stat().st_mtime)
        dest.mkdir(parents=True, exist_ok=True)
        for name in ('out.jsonl', 'steps.txt'):
            if (best / name).is_file():
                shutil.copy2(best / name, dest / name)
        filled.append(side)
    return filled


class Hunt:
    def __init__(self, plan, out, log=print):
        self.plan, self.out = plan, Path(out)
        self.log_fn = log
        self.t0 = time.monotonic()
        self.started = time.strftime('%F %T')
        self.budget_s = plan['budget'].get('seconds') or (plan['hold_seconds'] - RESERVE_S)
        self.budget_s = min(self.budget_s, plan['hold_seconds'] - RESERVE_S)
        self.usd, self.spent = plan['budget'].get('usd'), 0.0
        self.cfg = bughunt.Config.from_dict(plan['config'])
        self.bounds = bughunt.Bounds.load(plan['bounds']) if plan['bounds'] else None
        self.baseline = bughunt.load_baseline(plan['baseline'])
        self.registry = bugpacket.Registry(plan['registry'] or self.out / 'known.json')
        self.pilot = Path(plan['pilot'])
        self.pilot_dir = self.pilot.resolve().parent
        self.rows = [{'name': s['name'], 'kind': s['kind'], 'tag': s['tag'], 'status': 'pending'} for s in plan['sessions']]
        self.findings = []        # (row name, finding, status, packet or None)
        self.packets = 0
        self.stopped = None
        self.term_signal = None
        self.defer = False
        self.logf = None
        self.ask = None

    # -- bookkeeping
    def log(self, msg):
        line = f'{time.strftime("%F %T")} {msg}'
        if self.logf:
            self.logf.write(line + '\n')
        self.log_fn(line)

    def elapsed(self):
        return time.monotonic() - self.t0

    def remaining(self):
        return self.budget_s - self.elapsed()

    def write(self):
        dump_json(self.out / 'result.json', {'name': self.plan['name'], 'hold_seconds': self.plan['hold_seconds'], 'started_at': self.started,
                                             'elapsed_s': round(self.elapsed(), 1), 'budget_s': self.budget_s, 'usd_spent': round(self.spent, 5),
                                             'stopped': self.stopped, 'sessions': self.rows,
                                             'findings': [{'session': n, 'key': f.key, 'kind': f.kind, 'sub': f.sub, 'severity': f.severity, 'side': f.side,
                                                           'status': st, 'text': f.text, 'packet': str(p) if p else None, 'map': f.map, 't': f.t, 'game_s': f.game_s}
                                                          for n, f, st, p in self.findings]})

    def on_term(self, signum, _frame):
        self.term_signal = self.term_signal or signum
        if self.defer:
            return
        self.defer = True
        raise Terminated(signum)

    # -- the model's eyes, when the plan wants them and the key is there
    def eyes(self):
        v = self.plan['vision']
        if not v.get('enabled'):
            return None
        if self.ask is None:
            try:
                import openai_api
                if openai_api.key_state() not in ('file', 'env'):
                    self.log('vision: no key, the model looks are off')
                    self.ask = False
                else:
                    allowance = (time.time() - 3600, self.usd) if self.usd else None
                    client = openai_api.Client(f'{self.plan["name"]}-look', 'bughunt', None, allowance)
                    self.ask = bughunt.ModelAsker(client, v.get('model'))
                    self.cfg.vision_max = int(v.get('max', self.cfg.vision_max))
            except Exception as e:   # noqa: BLE001
                self.log(f'vision: off ({type(e).__name__}: {e})')
                self.ask = False
        return self.ask or None

    # -- collecting
    def collect_solo(self, rdir, pilot_run, game_run, row):
        missing = []
        if pilot_run.is_dir():
            shutil.copytree(pilot_run, rdir / 'pilot', copy_function=shutil.copy2, dirs_exist_ok=True)
        else:
            missing.append('pilot run folder')
        gdir = rdir / 'game'
        if game_run.is_dir():
            gdir.mkdir(exist_ok=True)
            logs = sorted(game_run.glob('*_log.txt'))
            if not logs:
                missing.append('game log')
            for f in logs + [game_run / n for n in GAME_FILES]:
                if f.is_file():
                    shutil.copy2(f, gdir / f.name)
            pres = game_run / 'present.csv'
            if pres.is_file():
                gzip_file(pres, gdir / 'present.csv.gz')
            else:
                missing.append('game/present.csv')
            shots = sorted((game_run / 'shots').glob('*.png')) if (game_run / 'shots').is_dir() else []
            if shots:
                reflink_copy(shots, gdir / 'shots')
            row['shots'] = len(shots)
            bursts = sorted(p for p in (game_run / 'burst').glob('*/*') if p.suffix in ('.png', '.json')) if (game_run / 'burst').is_dir() else []
            for sub in sorted({p.parent for p in bursts}):
                reflink_copy([p for p in bursts if p.parent == sub], gdir / 'burst' / sub.name)
        else:
            missing.append('game run folder')
        row['missing'] = missing
        summary = None
        try:
            summary = json.loads((pilot_run / 'summary.json').read_text())
        except (OSError, ValueError):
            pass
        if isinstance(summary, dict):
            row['outcome'] = summary.get('outcome')
            row['pilot_summary'] = {k: summary.get(k) for k in ('segment', 'decider', 'decisions', 'goals', 'play_wall_s', 'gameplay_after_s', 'humanize', 'rates', 'recover')}
            c = (summary.get('rates') or {}).get('cost_usd')
            if isinstance(c, (int, float)):
                row['usd'] = c
                self.spent += c

    # -- one solo session
    def run_solo(self, s, row, rdir):
        tag = s['tag']
        scripted = bool(s.get('scenario'))
        pilot_run = (self.out / 'scripted' / tag) if scripted else (self.pilot_dir / 'runs' / tag)
        game_run = Path(self.plan['copy']) / 'runs' / tag
        save = save_path(self.plan, s['save'])
        row.update(started_at=time.strftime('%F %T'), save=s['save'], segment=Path(s['segment']).name if s.get('segment') else None, decider=s['decider'], humanize=s['humanize'], seed=s['seed'])
        if scripted:
            row['scenario'] = {'name': Path(s['scenario']).stem, 'file': Path(s['scenario']).name}
        err = copy_errors(self.plan['copy'])
        others = game_processes(self.plan['copy'], ancestors(os.getpid()))
        if not err and others:
            err = [f'a game process of the copy is running (pid {others[0].pid}): {others[0].text[:100]}']
        if not err and pilot_run.exists():
            err = [f'the pilot already has a run folder {tag}']
        if not err and not save.is_dir():
            err = [f'save {save} is not a folder']
        if err:
            row['status'] = 'refused: ' + err[0]
            self.log(f'session {s["name"]} refused: {err[0]}')
            return None
        if game_run.is_symlink():
            game_run.unlink()
        elif game_run.exists():
            self.log(f'session {s["name"]}: deleting the copy\'s old {game_run}')
            shutil.rmtree(game_run)
        wall = s['wall']
        if scripted:   # hsap plays the scenario's steps once Link is placed: no pilot, no model
            sc = scenario.load(s['scenario'])
            world = None
            if self.plan.get('world'):
                wr = WorldRoam(self.plan['world'])
                world = {'plan': wr.plan.plan, 'start': wr.start, 'targets': wr.targets, 'snap': wr.nearest}
            live = pilot_run / 'live'
            live.mkdir(parents=True, exist_ok=True)
            (live / 'steps.txt').write_text('')
            cmd = [sys.executable, '-I', '-B', str(self.pilot.resolve().parent.parent / 'hsap.py'), str(self.plan['copy']), tag, str(wall), '--live', str(live), '--boot', 'continue',
                   '--save', str(save), '--shots', str(s['shots']), '--analog']
        else:
            cmd = [sys.executable, '-I', '-B', str(self.pilot), 'run', s['segment'], '--decider', s['decider'], '--tag', tag, '--copy', self.plan['copy'],
                   '--save', str(save), '--wall', str(wall), '--shots', str(s['shots']), '--end-hold', str(END_HOLD_S)]
        if not scripted:
            if s['humanize'] is not None:
                cmd += ['--humanize', str(s['humanize'])]
            if s['seed'] is not None:
                cmd += ['--humanize-seed', str(s['seed'])]
            if s.get('max_decisions'):
                cmd += ['--max-decisions', str(s['max_decisions'])]
            if s.get('vision'):
                cmd += ['--vision', 'on']
            allow = s.get('allow_usd') or (max(0.0, self.usd - self.spent) if self.usd else None)
            if allow is not None and s['decider'] != 'rules':
                cmd += ['--allowance-usd', f'{allow:.3f}', '--allowance-since', datetime.date.today().isoformat()]
        env = dict(os.environ)
        for k in ('HSGATE_SLOT_DIR', 'HSGATE_INTEL_SLOT_DIR', 'HSGATE_SLOT_TEST', 'HSGATE_SLOT_NODESKTOP', 'HSGATE_IN_GATE'):
            env.pop(k, None)
        if s['decider'] in ('rules', 'scenario') and not s.get('vision'):
            env.pop('OPENAI_API_KEY', None)
        for kv in s['env']:
            k, v = kv.split('=', 1)
            env[k] = v
        fam = Family(tag, [self.plan['copy']], self.log)
        rdir.mkdir(parents=True, exist_ok=True)
        pout = open(rdir / 'pilot.out', 'w')
        proc = subprocess.Popen(cmd, stdout=pout, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env, start_new_session=True)
        pout.close()
        row['pilot_pid'] = proc.pid
        self.log(f'session {s["name"]}: ' + (f'scenario {row["scenario"]["name"]}: hsap' if scripted else 'pilot') + f' pid {proc.pid}, wall {wall} s, seed {s["seed"]}')
        if scripted:
            spec = scenario.place_spec(sc)
            def release(res, sc=sc, world=world):   # (what the scenario sends once Link is placed: the leg to the coordinates only when no warp put him there)
                warped = bool((res.get('warp') or {}).get('ok'))
                st = scenario.compile_steps(sc, world, goto=not warped)
                lines = [l for l, _ in st] + ['end']
                return lines, {i + 1: t for i, (_, t) in enumerate(st)}
            threading.Thread(target=release_after_placement, args=(live, game_run, spec, [], self.log, wall, lambda: proc.poll() is not None), kwargs={'release': release, 'env': env}, daemon=True).start()
        burster = burst.Burster(game_run, self.cfg, log=self.log) if s.get('burst') else None
        watcher = Watcher(pilot_run, game_run, self.cfg, lambda: proc.poll() is None, burster=burster)
        watcher.start()
        t_start = time.monotonic()
        deadline = t_start + wall + EXTRA_S
        reason, terminated = None, None
        try:
            while proc.poll() is None:
                fam.track(proc.pid)
                if self.term_signal:
                    raise Terminated(self.term_signal)
                if time.monotonic() >= deadline:
                    reason = 'wall'
                    break
                if watcher.stop_reason:
                    reason = watcher.stop_reason
                    break
                time.sleep(0.5)
        except Terminated as e:
            terminated, reason = e, 'the hold\'s deadline'
        finally:
            watcher.halt.set()
            watcher.join(timeout=10)
            self.defer = True
            if proc.poll() is None or fam.members(None):
                self.log(f'session {s["name"]}: stopping the family ({reason or "ended"})')
                fam.stop(proc)
        row.update(seconds=round(time.monotonic() - t_start, 1), pilot_exit=proc.returncode, stopped_by=reason, watcher_findings=len(watcher.found))
        if burster is not None:
            row['bursts'] = [{'kind': m.get('kind'), 'why': m.get('why'), 'pictures': len(m.get('pictures') or []), 'errors': m.get('errors')[:2]} for m in burster.taken]
            if watcher.burst_errors:
                row['burst_errors'] = watcher.burst_errors
        self.collect_solo(rdir, pilot_run, game_run, row)
        if s.get('place'):   # what was asked and what the game did: the ledger counts placed sessions from this
            try:
                got = json.loads((pilot_run / ('live/placement.json' if scripted else 'summary.json')).read_text())
                got = got if scripted else (got.get('place') or {})
            except (OSError, ValueError):
                got = {}
            row['place'] = {**{k: s['place'][k] for k in ('to', 'age', 'hour') if s['place'].get(k) is not None}, 'ok': bool(got.get('ok')), 'partial': got.get('partial'),
                            'error': got.get('error'), 'seconds': got.get('seconds')}
        if terminated:
            raise terminated
        return watcher

    # -- one pair session
    def run_pair(self, s, row, rdir):
        env = {k: v for k, v in os.environ.items() if not k.startswith(('HSGATE_', 'HOS_', 'RX_'))}
        for kv in s['env']:
            k, v = kv.split('=', 1)
            env[k] = v
        row.update(started_at=time.strftime('%F %T'), case=Path(s['case']).name)
        Path(rdir).mkdir(parents=True, exist_ok=True)
        case_copy = Path(rdir) / 'case-source.toml'
        shutil.copy2(s['case'], case_copy)
        try:   # what `coopplay.py run` leaves before it hands over to `inner`: the normalized case beside the source
            sys.path.insert(0, str(Path(self.plan['coopplay']).resolve().parent))
            import cpcase
            import cpio
            cpio.dump_json(Path(rdir) / 'case.json', cpcase.load_case(str(case_copy)))
        except Exception as e:   # noqa: BLE001  the fake runner of the tests has no cpcase: inner reads the source itself
            self.log(f'session {s["name"]}: no case.json ({type(e).__name__}: {str(e)[:80]})')
        cmd = ['timeout', '--signal=TERM', '--kill-after=25', str(int(s['hold_s'])), sys.executable, '-I', '-B', self.plan['coopplay'], 'inner', str(case_copy),
               '--out', str(rdir)]
        err = copy_errors(self.plan['copy']) + copy_errors(self.plan['copy_b'] or '')
        for c in (self.plan['copy'], self.plan['copy_b']):
            others = game_processes(c, ancestors(os.getpid())) if c else []
            if others:
                err.append(f'a game process of {c} is running (pid {others[0].pid})')
        if err:
            row['status'] = 'refused: ' + err[0]
            self.log(f'session {s["name"]} refused: {err[0]}')
            return
        fam = Family(s['tag'], [self.plan['copy'], self.plan['copy_b']], self.log)
        t_start = time.monotonic()
        pout = open(self.out / f'{s["name"]}.pair.out', 'w')
        proc = subprocess.Popen(cmd, stdout=pout, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env, start_new_session=True)
        pout.close()
        self.log(f'session {s["name"]}: coopplay pid {proc.pid}, hold {s["hold_s"]} s')
        try:
            while proc.poll() is None:
                fam.track(proc.pid)
                if self.term_signal:
                    raise Terminated(self.term_signal)
                if time.monotonic() > t_start + s['hold_s'] + 60:
                    break
                time.sleep(0.5)
        finally:
            self.defer = True
            if proc.poll() is None or fam.members(None):
                fam.stop(proc)
        row.update(seconds=round(time.monotonic() - t_start, 1), pilot_exit=proc.returncode)
        res = read_text(Path(rdir) / 'result.json')
        if res:
            try:
                r = json.loads(res)
                row['verdict'] = r.get('verdict')
            except ValueError:
                pass

    # -- the detectors over what a session left, then the table and the packets
    def judge(self, s, row, rdir, extra=()):
        if s['kind'] == 'pair':
            recover_pilot_records(rdir, since=time.time() - float(row.get('seconds') or 0) - 120)
        try:
            sides = bughunt.find_sides(rdir)
            report = bughunt.analyze(rdir, self.cfg, self.bounds, self.baseline, self.eyes(), None, sides)
            have = {f.key for f in report['findings']}
            report['findings'] += [f for f in extra if f.key not in have]   # (what the watcher saw live: a hang that never resumed leaves no gap to read)
        except Exception as e:   # noqa: BLE001  the evidence is kept: `hunt.py analyze` can run again
            row['analysis_error'] = f'{type(e).__name__}: {str(e)[:200]}'
            self.log(f'session {s["name"]}: the analysis failed: {row["analysis_error"]}')
            return []
        row['detectors'] = report['detectors']
        row['feedback'] = score.apply_feedback(report['findings'], self.registry.entries())   # (the registry's verdicts of earlier rounds are rules now)
        if s.get('scenario'):   # the verdict of the reproduction attempt: what was looked for, what was tried, on which hardware
            try:
                sc = scenario.load(s['scenario'])
                if s['kind'] == 'pair':
                    res = scenario.evaluate_pair(sc, report['findings'], sides)
                else:
                    res = scenario.evaluate(sc, rdir, visual_findings=[f for f in report['findings'] if f.kind == 'visual'])
                dump_json(rdir / 'scenario-result.json', res)
                row['scenario'] = {'name': sc['name'], 'purpose': sc['purpose'], 'claim': sc['claim'], 'verdict': res['verdict'], 'hardware': res.get('hardware'), 'why': res.get('why'),
                                   'checks': [{k: v for k, v in c.items() if k in ('check', 'verdict', 'spikes_in', 'spikes_out', 'spikes_machine', 'found', 'distance_m', 'pictures', 'why', 'share', 'rises', 'sides', 'what', 'per_side')} for c in res['checks']],
                                   'goto': res.get('goto'), 'steps_done': res.get('steps_done')}
                self.log(f'scenario {sc["name"]}: {res["verdict"]}')
            except Exception as e:   # noqa: BLE001  the evidence is kept: `scenario.py eval` can run again
                row['scenario_error'] = f'{type(e).__name__}: {str(e)[:200]}'
        if s.get('expect_key'):   # a regression scenario: does the known key still fire (a real or known bug must), and a fixed one must not
            fired = any(f.key == s['expect_key'] and f.severity != 'info' or (f.key == s['expect_key'] and (f.evidence or {}).get('known')) for f in report['findings'])
            row['scenario'] = {'name': s.get('label') or s['name'], 'purpose': 'regression', 'claim': f'the key {s["expect_key"]} fires again', 'verdict': 'reproduced' if fired else 'not reproduced',
                               'hardware': None, 'checks': [{'check': 'key', 'verdict': 'reproduced' if fired else 'not reproduced'}]}
            self.log(f'regression {s["expect_key"]}: {row["scenario"]["verdict"]}')
        out = []
        base_session = self.session_info(s, rdir)
        counter = [self.packets]
        for f in report['findings']:
            if f.severity == 'info':
                continue
            st, packet = handle_finding(self.registry, f, s['tag'], sides, base_session, self.out / 'packets', counter, self.plan['max_packets'])
            out.append((s['name'], f, st, packet))
        self.packets = counter[0]
        self.findings += out
        row['findings'] = {k: sum(1 for _, _f, st, _p in out if st == k) for k in ('new', 'duplicate', 'artefact')}
        return out

    def session_info(self, s, rdir):
        info = {'run': s['tag'], 'name': s['name'], 'kind': s['kind'], 'copy': self.plan['copy'], 'env': s['env']}
        if s['kind'] == 'solo':
            info.update(save=str(save_path(self.plan, s['save'])), save_name=s['save'], segment=s.get('segment'), seed=s['seed'], humanize=s['humanize'],
                        decider=s['decider'], wall=s['wall'], shots=s['shots'], boot=s.get('boot') or 'continue')
            if s.get('place'):
                info['place'] = s['place']
            if s.get('scenario'):
                info['scenario'] = s['scenario']
        else:
            info.update(case=str(Path(rdir) / 'case-source.toml') if (Path(rdir) / 'case-source.toml').is_file() else s['case'])
        return info

    # -- the whole hold
    def run(self):
        self.out.mkdir(parents=True)
        self.logf = open(self.out / 'driver.log', 'a', buffering=1)
        self.psi = Pressure(self.out / 'psi.jsonl')
        self.psi.start()
        shutil.copy2(self.plan['plan_path'], self.out / 'plan-at-admission.json')
        signal.signal(signal.SIGTERM, self.on_term)
        self.write()
        try:
            for s, row in zip(self.plan['sessions'], self.rows):
                self.defer = False
                if self.term_signal:
                    raise Terminated(self.term_signal)
                if self.remaining() < s['min_s']:
                    row['status'] = f'not started: {self.remaining():.0f} s of budget left, {s["min_s"]:.0f} s needed'
                    self.log(f'session {s["name"]}: {row["status"]}')
                    continue
                if self.usd is not None and self.spent >= self.usd:
                    row['status'] = f'not started: the {self.usd} USD budget is spent'
                    continue
                row['status'] = 'running'
                self.write()
                rdir = self.out / s['name']
                t_mono0 = time.monotonic()
                watcher = None
                try:
                    if s['kind'] == 'solo':
                        watcher = self.run_solo(s, row, rdir)
                    else:
                        self.run_pair(s, row, rdir)
                except Terminated:
                    self.stopped = f'signal {self.term_signal}'
                    row['status'] = 'stopped by the hold'
                    raise
                finally:
                    self.defer = True
                if (self.out / 'psi.jsonl').is_file() and rdir.is_dir():
                    slice_psi(self.out / 'psi.jsonl', t_mono0 - 5.0, time.monotonic() + 5.0, rdir / 'psi.jsonl')
                if not str(row['status']).startswith('refused'):
                    self.judge(s, row, rdir, watcher.found if watcher else ())
                    row['status'] = 'done'
                self.write()
                self.defer = False
            self.replays()
        except Terminated:
            self.log('stopped by the hold\'s deadline')
            self.stopped = self.stopped or f'signal {self.term_signal}'
            self.defer = True
            for s, row in zip(self.plan['sessions'], self.rows):
                if row['status'] == 'stopped by the hold' and 'detectors' not in row and (self.out / s['name']).is_dir():
                    try:
                        self.judge(s, row, self.out / s['name'])
                    except Exception as e:   # noqa: BLE001
                        self.log(f'judge after the stop failed: {e}')
        finally:
            self.defer = True
            self.psi.halt.set()
            try:
                write_table(self.out, self.plan, self.rows, self.findings, self.registry)
            except Exception as e:   # noqa: BLE001
                self.log(f'table failed: {e}')
            self.write()
        return 0 if not self.stopped else 143

    # -- replays of the new findings, budget permitting
    def replays(self):
        n = self.plan['replay_new']
        if not n:
            return
        kinds = {r['name']: r['kind'] for r in self.rows}   # (a pair's packet replays through its case: `replay-plan`)
        todo = [(name, f, p) for name, f, st, p in self.findings if st == 'new' and p and f.severity == 'error' and kinds.get(name) == 'solo'][:n]
        for name, f, packet in todo:
            if self.remaining() < 240:
                self.log('replays: out of budget')
                break
            self.defer = False
            try:
                v = replay_packet(packet, self.plan['copy'], self.pilot, self.cfg, self.bounds, self.baseline, wall=min(int(self.remaining()) - 120, 240),
                                  out=packet / 'replay', log=self.log, term=lambda: self.term_signal)
                self.log(f'replay of {f.key}: {v["verdict"]}')
            except Terminated:
                raise
            except Exception as e:   # noqa: BLE001
                self.log(f'replay of {f.key} failed: {type(e).__name__}: {e}')
            self.defer = True


def write_table(out, plan, rows, findings, registry):
    """table.md and table.json: a row per session, then every finding with its key, status and packet."""
    lines = [f'# Hunt {plan["name"]}', '', '| session | kind | save / case | seed | humanize | outcome | seconds | findings new/dup/artefact | USD |', '|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        fi = r.get('findings') or {}
        lines.append(f'| {r["name"]} | {r["kind"]} | {r.get("save") or r.get("case") or ""} | {r.get("seed", "")} | {r.get("humanize", "")} | '
                     f'{r.get("outcome") or r.get("verdict") or r["status"]} | {r.get("seconds", "")} | {fi.get("new", 0)}/{fi.get("duplicate", 0)}/{fi.get("artefact", 0)} | {r.get("usd", "")} |')
    lines += ['', '| session | severity | kind/sub | where | game s | status | key | text | packet |', '|---|---|---|---|---|---|---|---|---|']
    for name, f, st, p in findings:
        lines.append(f'| {name} | {f.severity} | {f.kind}/{f.sub} | {f.map or ""} | {f.game_s if f.game_s is not None else ""} | {st} | `{f.key}` | {f.text[:110].replace("|", "/")} | {Path(p).name if p else ""} |')
    det = {}
    for r in rows:
        for side, d in (r.get('detectors') or {}).items():
            for name, v in d.items():
                row = det.setdefault(name, {'ok': 0, 'found': 0, 'unknown': 0})
                row[v['status']] = row.get(v['status'], 0) + 1
    lines += ['', '| detector | ok | found | unknown (sides) |', '|---|---|---|---|'] + [f'| {n} | {v["ok"]} | {v["found"]} | {v["unknown"]} |' for n, v in sorted(det.items())]
    (Path(out) / 'table.md').write_text('\n'.join(lines) + '\n')
    dump_json(Path(out) / 'public.json', public_rows(plan, rows, findings, bugpacket.build_identity(plan.get('copy')).get('built_from') if plan.get('copy') else None))
    dump_json(Path(out) / 'table.json', {'sessions': rows, 'findings': [{'session': n, 'key': f.key, 'status': st, 'finding': f.to_dict(), 'packet': str(p) if p else None}
                                                                         for n, f, st, p in findings], 'detectors': det})


def public_rows(plan, rows, findings, built_from=None):
    """What may leave this machine of a hold, in a fixed shape (issue 43: no raw output, only reviewed configuration rows): counts by detector
    and kind, the keys (hashes of a bug's identity: no text, no map, no place), the build's commit, how many sessions of which kind. Nothing from
    a log, a picture, a save or a position."""
    kinds = {}
    for _, f, st, _ in findings:
        k = kinds.setdefault(f'{f.kind}/{f.sub}', {'severity': f.severity, 'new': 0, 'duplicate': 0, 'artefact': 0})
        k[st] = k.get(st, 0) + 1
    det = {}
    for r in rows:
        for _side, d in (r.get('detectors') or {}).items():
            for name, v in d.items():
                row = det.setdefault(name, {'ok': 0, 'found': 0, 'unknown': 0})
                row[v['status']] = row.get(v['status'], 0) + 1
    return {'format': 'ls-hunt-public/1', 'hunt': plan['name'], 'build': built_from, 'sessions': {k: sum(1 for r in rows if r['kind'] == k) for k in ('solo', 'pair')},
            'done': sum(1 for r in rows if r['status'] == 'done'), 'findings': kinds, 'keys': sorted({f.key for _, f, st, _ in findings if st != 'artefact'}), 'detectors': det}


# ====================================================================== replay

def release_after_placement(live, game_run, spec, held, log, wait_s, gone=lambda: False, release=None, env=None):
    """A placed replay's steps: wait for `gameplay` in the live folder's events, place Link (placement.apply, the result kept as
    placement.json), then append the held steps; a failed placement releases only the `end` (a replay from the wrong place is no replay)."""
    end = time.time() + wait_s
    while time.time() < end and not gone():
        try:
            if '"gameplay"' in (live / 'out.jsonl').read_text():
                break
        except OSError:
            pass
        time.sleep(0.3)
    else:
        log('replay: no gameplay: the steps are not released')
        return
    res = placement.apply(spec, game_run, env=env)
    log(f'replay: placement {"ok" if res.get("ok") else "FAILED"} in {res.get("seconds")} s' + (f' ({res.get("error")})' if res.get('error') else ''))
    dump_json(live / 'placement.json', res)
    lines = held
    if release is not None and res.get('ok'):   # a scenario: its steps are compiled now that the placement (and a warp) is known; the tags say which step belongs to which action
        lines, tags = release(res)
        dump_json(live / 'scenario-steps.json', {'tags': tags})
    with open(live / 'steps.txt', 'a') as f:
        for ln in (lines if res.get('ok') else ['end']):
            f.write(ln + '\n')


def replay_packet(packet, copy, pilot, cfg, bounds, baseline, wall=None, out=None, log=print, term=lambda: None, mode='steps'):
    """Re-drives a solo packet's inputs in a game of `copy` and judges what happens with the same detectors. Inside a hold only: it starts a
    game (hsap, which asks the gate itself). Returns {verdict, detail, findings, ...}, also written to <out>/replay.json."""
    packet = Path(packet)
    out = Path(out or packet / 'replay')
    out.mkdir(parents=True, exist_ok=True)
    pk = json.loads((packet / 'packet.json').read_text())
    if pk['replay']['mode'] != 'steps':
        raise ValueError('a pair packet replays through its case (coopplay.py run <packet>/case.toml)')
    rp = pk['replay']
    tag = f'replay-{pk["key"].split(":")[-1]}-{int(time.time()) % 100000}'
    live = out / 'live'
    bugpacket.prepare_replay(packet, live, mode=mode)
    game_run = Path(copy) / 'runs' / tag
    if game_run.exists():
        shutil.rmtree(game_run)
    held = []
    if rp.get('place'):   # a placed session replays placed: the steps wait until hsdebug has put Link where the session began
        lines = (live / 'steps.txt').read_text().splitlines()
        (live / 'steps.txt').write_text(''.join(ln + '\n' for ln in lines if ln.split()[:1] == ['watch']))
        held = [ln for ln in lines if ln.split()[:1] != ['watch']]
    wall = int(wall or rp['wall'])
    cmd = [sys.executable, '-I', '-B', str(Path(pilot).resolve().parent.parent / 'hsap.py'), str(copy), tag, str(wall), '--live', str(live), '--boot', rp['boot'], '--shots', str(rp['shots'])]
    if rp.get('save'):
        cmd += ['--save', str(packet / rp['save'])]
    env = dict(os.environ)
    env.pop('OPENAI_API_KEY', None)
    for k in ('HSGATE_SLOT_DIR', 'HSGATE_INTEL_SLOT_DIR', 'HSGATE_SLOT_TEST', 'HSGATE_SLOT_NODESKTOP', 'HSGATE_IN_GATE'):
        env.pop(k, None)
    for kv in rp.get('env') or []:
        k, v = kv.split('=', 1)
        env[k] = v
    fam = Family(tag, [copy], log)
    pout = open(out / 'hsap.out', 'w')
    proc = subprocess.Popen(cmd, stdout=pout, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env, start_new_session=True)
    pout.close()
    t0 = time.monotonic()
    if rp.get('place'):
        threading.Thread(target=release_after_placement, args=(live, game_run, rp['place'], held, log, wall, lambda: proc.poll() is not None), kwargs={'env': env}, daemon=True).start()
    try:
        while proc.poll() is None and time.monotonic() < t0 + wall + EXTRA_S:
            fam.track(proc.pid)
            if term():
                raise Terminated(term())
            time.sleep(0.5)
    finally:
        if proc.poll() is None or fam.members(None):
            fam.stop(proc)
    side_dir = out / 'run'
    shutil.copytree(live, side_dir / 'pilot' / 'live', dirs_exist_ok=True)
    (side_dir / 'pilot').mkdir(exist_ok=True)
    for n in ('out.jsonl', 'steps.txt'):
        if (live / n).is_file():
            shutil.copy2(live / n, side_dir / 'pilot' / n)
    gdir = side_dir / 'game'
    gdir.mkdir(exist_ok=True)
    if game_run.is_dir():
        for f in sorted(game_run.glob('*_log.txt')) + [game_run / n for n in GAME_FILES]:
            if f.is_file():
                shutil.copy2(f, gdir / f.name)
        if (game_run / 'present.csv').is_file():
            gzip_file(game_run / 'present.csv', gdir / 'present.csv.gz')
        shots = sorted((game_run / 'shots').glob('*.png')) if (game_run / 'shots').is_dir() else []
        reflink_copy(shots, gdir / 'shots')
    report = bughunt.analyze(side_dir, cfg, bounds, baseline, None, None)
    verdict, detail = bugpacket.replay_verdict(pk['key'], report['findings'])
    res = {'verdict': verdict, 'detail': detail, 'mode': mode, 'tag': tag, 'seconds': round(time.monotonic() - t0, 1), 'packet_key': pk['key'],
           'findings': [{'key': f.key, 'kind': f.kind, 'sub': f.sub, 'severity': f.severity, 'text': f.text} for f in report['findings'] if f.severity != 'info'],
           'detectors': report['detectors']}
    dump_json(out / 'replay.json', res)
    return res


# ====================================================================== the waiter

def queue_command(plan_path, plan, out, quiet=None, measuring=None, wait=28800):
    quiet, measuring = quiet or os.environ.get(ENV_QUIET), measuring or os.environ.get(ENV_MEASURING)
    if not (quiet and measuring):
        raise PlanError(f'the waiter needs the main lane\'s lock files: set {ENV_QUIET} and {ENV_MEASURING} (this machine\'s own values; there is no default)')
    return ['setsid', 'nohup', 'env', '--default-signal=HUP', 'flock', '--verbose', '-w', str(int(wait)), quiet, 'flock', '--verbose', '-w', '14400', measuring,
            'timeout', '--signal=TERM', '--kill-after=20', str(int(plan['hold_seconds'])), sys.executable, '-I', '-B', str(HERE / 'hunt.py'), 'run',
            str(plan_path), '--out', str(out)]


def cmd_queue(a):
    plan = load_plan(a.plan)
    sessions = Path(a.sessions) if a.sessions else Path(plan['plan_path']).parent / 'sessions'
    out = sessions / plan['name']
    errs = plan_errors(plan, out)
    try:
        cmd = queue_command(Path(plan['plan_path']), plan, out, wait=getattr(a, 'wait', 28800))
    except PlanError as e:   # (no lock settings: a dry run says so as it says every other refusal)
        cmd = None
        errs.append(str(e))
    pattern = os.environ.get('HUNT_PGREP', r'hunt\.py (run|queue) ')   # (my own waiters: the machine's other lanes are the dispatcher's business)
    others = []
    me = {os.getpid(), os.getppid()}
    r = subprocess.run(['pgrep', '-u', str(os.getuid()), '-f', pattern], capture_output=True, text=True)
    for p in r.stdout.split():
        if int(p) not in me:
            others.append(p)
    print(f'hunt {plan["name"]}: {plan["hold_seconds"]:.0f} s, plan {plan["plan_path"]}')
    if cmd:
        print('command: ' + ' '.join(shlex.quote(c) for c in cmd) + f' > {sessions / (plan["name"] + ".launcher.log")} 2>&1 < /dev/null &')
    refuse = None
    if errs:
        refuse = errs[0]
    elif (sessions / (plan['name'] + '.pid')).exists():
        refuse = f'{plan["name"]}.pid exists (a waiter was queued for this name)'
    elif others:
        refuse = f'another hold waiter or hold is running (pid {" ".join(others)}): one waiter at a time'
    if refuse:
        print(('dry run: WOULD REFUSE: ' if a.dry_run else 'refusing: ') + refuse, file=sys.stderr if not a.dry_run else sys.stdout)
        return 2 if errs or not others else 3
    if a.dry_run:
        print('dry run: would start the waiter; nothing was started')
        return 0
    sessions.mkdir(parents=True, exist_ok=True)
    shutil.copy2(plan['plan_path'], sessions / f'{plan["name"]}.plan-at-queue.json')
    log = open(sessions / f'{plan["name"]}.launcher.log', 'w')
    p = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, start_new_session=False)
    (sessions / f'{plan["name"]}.pid').write_text(f'{p.pid}\n')
    print(f'launcher pid {p.pid}')
    return 0


# ====================================================================== CLI

def cmd_plan(a):
    roam = WorldRoam(a.world) if a.world else None
    path = make_plan(a, roam)
    plan = load_plan(path)
    print(f'{path}: {len(plan["sessions"])} sessions, {sum(s["min_s"] for s in plan["sessions"]):.0f} s of play and start-up')
    for s in plan['sessions']:
        print(f'  {s["name"]:8} {s["kind"]:5} ' + (f'{s["save"]} {Path(s["segment"]).name} seed {s["seed"]} humanize {s["humanize"]}' if s['kind'] == 'solo' else Path(s['case']).name))
    return 0


NIGHTLY_KEYS = {'solo', 'pairs', 'library', 'copies', 'pilot', 'world', 'chapters', 'chapter_share', 'pair_case', 'pair_hold', 'areas', 'targets', 'wall', 'hold_seconds',
                'config', 'bounds', 'baseline', 'registry', 'coopplay', 'budget_usd', 'prefix', 'sessions_dir', 'places', 'placed', 'session_env'}
ROAM_FACTORY = None   # the tests put a fake roam source here


def nightly_args(template, day):
    """The make_plan arguments of one night: the template (a JSON file of the plan generator's own options) with the date's seed. The same date,
    the same plan; a new date, new starts and seeds."""
    class A:
        pass
    t = json.loads(Path(template).read_text())
    bad = sorted(set(t) - NIGHTLY_KEYS)
    if bad:
        raise PlanError('unknown nightly keys: ' + ', '.join(bad))
    base = Path(template).resolve().parent
    a = A()
    stamp = day.strftime('%Y%m%d')
    name = f'{t.get("prefix", "PilotNightly")}-{stamp}'
    sessions = Path(_path(t['sessions_dir'], base)) if t.get('sessions_dir') else base / 'sessions'
    a.name, a.seed, a.out = name, int(stamp), str(base / 'plans' / name)
    a.solo, a.pairs, a.targets, a.wall = int(t.get('solo', 3)), int(t.get('pairs', 0)), int(t.get('targets', 8)), int(t.get('wall', 260))
    a.library, a.copies, a.pilot = _path(t['library'], base), ','.join(_path(c, base) for c in t['copies']), _path(t['pilot'], base)
    a.chapters = _path(t['chapters'], base) if t.get('chapters') else None
    a.chapter_share, a.pair_hold, a.areas, a.hold_seconds = float(t.get('chapter_share', 0.3)), float(t.get('pair_hold', 800)), t.get('areas'), float(t.get('hold_seconds', 2400))
    a.pair_case = [_path(c, base) for c in t.get('pair_case', [])]
    a.config = _path(t['config'], base) if t.get('config') else None
    for k in ('bounds', 'baseline', 'registry', 'coopplay'):
        setattr(a, k, _path(t[k], base) if t.get(k) else None)
    a.budget_usd = t.get('budget_usd')
    a.places, a.placed = (_path(t['places'], base) if t.get('places') else None), int(t.get('placed', 0))
    a.session_env = [str(x) for x in t.get('session_env', [])]
    return a, t.get('world'), sessions, base


def cmd_nightly(a):
    """One night: the plan from the date's seed, checked, and queued as the one waiter (`--dry-run`: printed, nothing written beyond the plan)."""
    day = datetime.date.fromisoformat(a.date) if a.date else datetime.date.today()
    args, world, sessions, base = nightly_args(a.template, day)
    roam = ROAM_FACTORY() if ROAM_FACTORY else (WorldRoam(_path(world, base)) if world else None)
    if Path(args.out).exists():
        print(f'refusing: {args.out} exists (tonight\'s plan was made already)', file=sys.stderr)
        return 2
    path = make_plan(args, roam)
    print(f'nightly {args.name}: plan {path}')
    q = argparse.Namespace(plan=str(path), dry_run=a.dry_run, sessions=str(sessions))
    return cmd_queue(q)


def cmd_check(a):
    plan = load_plan(a.plan)
    errs = plan_errors(plan)
    for e in errs:
        print('REFUSED:', e)
    print(f'{plan["name"]}: {len(plan["sessions"])} sessions, hold {plan["hold_seconds"]:.0f} s, budget {plan["hold_seconds"] - RESERVE_S:.0f} s; ' + ('refused' if errs else 'ok'))
    return 2 if errs else 0


def cmd_run(a):
    plan = load_plan(a.plan)
    errs = plan_errors(plan, a.out)
    if errs:
        for e in errs:
            print('refusing:', e, file=sys.stderr)
        return 2
    os.umask(0o077)
    return Hunt(plan, a.out).run()


def cmd_analyze(a):
    plan = load_plan(a.plan) if a.plan else None
    cfg = bughunt.Config.from_dict(plan['config'] if plan else None)
    bounds = bughunt.Bounds.load(plan['bounds']) if plan and plan['bounds'] else (bughunt.Bounds.load(a.bounds) if a.bounds else None)
    base = bughunt.load_baseline(plan['baseline'] if plan and plan['baseline'] else a.baseline)
    out = Path(a.out or '.')
    reg = bugpacket.Registry(plan['registry'] if plan and plan['registry'] else out / 'known.json')
    rows, findings, counter = [], [], [0]
    for folder in a.folders:
        sides = bughunt.find_sides(folder)
        report = bughunt.analyze(folder, cfg, bounds, base, None, None, sides)
        row = {'name': Path(folder).name, 'kind': 'pair' if len(sides) > 1 else 'solo', 'status': 'analyzed', 'detectors': report['detectors']}
        row['feedback'] = score.apply_feedback(report['findings'], reg.entries())   # (the registry's verdicts are rules here too)
        mine = []
        for f in report['findings']:
            if f.severity == 'info':
                continue
            if a.packets:
                st, packet = handle_finding(reg, f, Path(folder).name, sides, session_from_folder(folder), out / 'packets', counter, 10 ** 6)
            else:
                st, entry = reg.register(f, Path(folder).name)
                f.status = 'artefact' if f.status == 'artefact' else ('duplicate' if st == 'duplicate' else 'new')
                st, packet = f.status, (Path(entry['packet']) if entry.get('packet') else None)
            mine.append((row['name'], f, st, packet))
        row['findings'] = {k: sum(1 for _, _f, st, _p in mine if st == k) for k in ('new', 'duplicate', 'artefact')}
        findings += mine
        rows.append(row)
        print('\n'.join(bughunt.summarize(report)))
    if a.out:
        out.mkdir(parents=True, exist_ok=True)
        write_table(out, {'name': 'analyze'}, rows, findings, reg)
    return 0


def cmd_replay(a):
    copy = a.copy or None
    if not copy:
        print('replay needs --copy <a game copy of the same build>', file=sys.stderr)
        return 2
    errs = copy_errors(copy)
    if errs:
        print('refusing:', errs[0], file=sys.stderr)
        return 2
    others = game_processes(copy, ancestors(os.getpid()))
    if others:
        print(f'refusing: a game process of the copy is running (pid {others[0].pid})', file=sys.stderr)
        return 3
    cfg = bughunt.Config.from_dict(json.loads(Path(a.config).read_text()) if a.config else None)
    res = replay_packet(a.packet, copy, a.pilot or HERE / 'pilot.py', cfg, bughunt.Bounds.load(a.bounds) if a.bounds else None, bughunt.load_baseline(a.baseline),
                        wall=a.wall, out=a.out, mode=a.mode)
    print(json.dumps({k: res[k] for k in ('verdict', 'detail', 'tag', 'seconds', 'packet_key')}, indent=1))
    return 0


def cmd_replay_plan(a):
    """A plan of ONE pair session that re-runs a pair packet's case (with a fresh rendezvous folder): queue it like any plan. Copies, pilot,
    config and the rest come from the plan the packet was found under (--plan)."""
    packet = Path(a.packet)
    pk = json.loads((packet / 'packet.json').read_text())
    if pk['replay']['mode'] != 'case':
        print('refusing: a solo packet replays with `hunt.py replay` (steps or inputs)', file=sys.stderr)
        return 2
    base = json.loads(Path(a.plan).read_text())
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    case = out / 'replay-case.toml'
    case.write_text(bugpacket.fresh_rendezvous((packet / 'case.toml').read_text(), out / 'rendezvous'))
    plan = {k: v for k, v in base.items() if k not in ('sessions', 'name', 'replay_new', 'budget', 'vision')}
    for k in ('copy', 'copy_b', 'pilot', 'library', 'coopplay', 'registry', 'bounds', 'baseline'):
        if plan.get(k):
            plan[k] = _path(plan[k], Path(a.plan).resolve().parent)
    plan.update(name=a.name, hold_seconds=float(a.hold_seconds), replay_new=0, budget={}, sessions=[{'name': 'replay', 'kind': 'pair', 'case': str(case), 'hold_s': float(a.hold_seconds) - 100}])
    path = out / 'plan.json'
    path.write_text(json.dumps(plan, indent=1) + '\n')
    print(f'{path}: one pair session replaying {pk["key"]}')
    return 0


def cmd_verdict(a):
    """The verdict of a replay hold over a packet: did the packet's key fire again among the replay session's findings? Written to <packet>/replay/replay.json."""
    packet = Path(a.packet)
    pk = json.loads((packet / 'packet.json').read_text())
    res = json.loads((Path(a.hunt) / 'result.json').read_text())
    found = []
    for f in res['findings']:
        x = bughunt.Finding(f['kind'], f['sub'], f['severity'], f['side'], f['text'], map=f.get('map'))
        x.key = f['key']
        found.append(x)
    verdict, detail = bugpacket.replay_verdict(pk['key'], found)
    out = packet / 'replay'
    out.mkdir(exist_ok=True)
    row = {'verdict': verdict, 'detail': detail, 'mode': 'case', 'packet_key': pk['key'], 'hunt': str(a.hunt), 'findings': [{k: f[k] for k in ('key', 'kind', 'sub', 'severity', 'text')} for f in res['findings']]}
    dump_json(out / 'replay.json', row)
    print(json.dumps({k: row[k] for k in ('verdict', 'detail', 'packet_key')}, indent=1))
    return 0


def cmd_score(a):
    return score.main(a.rest)


def cmd_table(a):
    print((Path(a.dir) / 'table.md').read_text())
    return 0


def main():
    if sys.argv[1:2] == ['score']:   # (score.py has its own options: passed whole, whatever order they come in)
        return score.main(sys.argv[2:])
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('plan')
    p.add_argument('--out', required=True)
    p.add_argument('--name', required=True)
    p.add_argument('--seed', type=int, default=1)
    p.add_argument('--solo', type=int, default=3)
    p.add_argument('--pairs', type=int, default=0)
    p.add_argument('--library', required=True)
    p.add_argument('--copies', required=True)
    p.add_argument('--pilot', required=True)
    p.add_argument('--world')
    p.add_argument('--chapters')
    p.add_argument('--chapter-share', type=float, default=0.5)
    p.add_argument('--pair-case', action='append')
    p.add_argument('--pair-hold', type=float, default=800.0)
    p.add_argument('--areas')
    p.add_argument('--targets', type=int, default=8)
    p.add_argument('--wall', type=int, default=180)
    p.add_argument('--hold-seconds', type=float, default=2400.0)
    p.add_argument('--config')
    p.add_argument('--bounds')
    p.add_argument('--baseline')
    p.add_argument('--registry')
    p.add_argument('--coopplay')
    p.add_argument('--budget-usd', type=float)
    p.add_argument('--places', help='a JSON list of placements ({"to", "age", "hour", "area", "save"}) the --placed roams start at')
    p.add_argument('--session-env', action='append', default=[], dest='session_env', help='NAME=VALUE for the env of every placed session (HSDEBUG_INFO=<the game-info file>)')
    p.add_argument('--placed', type=int, default=0, help='roams that start where hsdebug puts Link (needs --places and --world)')
    sc = sub.add_parser('score', help='the scorecard, the ledger, passive coverage, the next round (score.py --help)')
    sc.add_argument('rest', nargs=argparse.REMAINDER)
    ni = sub.add_parser('nightly')
    ni.add_argument('template')
    ni.add_argument('--date')
    ni.add_argument('--dry-run', action='store_true')
    c = sub.add_parser('check')
    c.add_argument('plan')
    r = sub.add_parser('run')
    r.add_argument('plan')
    r.add_argument('--out', required=True)
    q = sub.add_parser('queue')
    q.add_argument('plan')
    q.add_argument('--dry-run', action='store_true')
    q.add_argument('--sessions')
    q.add_argument('--wait', type=int, default=28800, help='seconds to wait for the quiet-window lock (default 8 hours)')
    n = sub.add_parser('analyze')
    n.add_argument('folders', nargs='+')
    n.add_argument('--out')
    n.add_argument('--plan')
    n.add_argument('--bounds')
    n.add_argument('--baseline')
    n.add_argument('--packets', action='store_true')
    rp = sub.add_parser('replay')
    rp.add_argument('packet')
    rp.add_argument('--copy')
    rp.add_argument('--pilot')
    rp.add_argument('--wall', type=int)
    rp.add_argument('--mode', choices=('steps', 'inputs'), default='steps', help='steps: the pilot\'s own steps; inputs: the recorded requests (exact stick values, frame gaps)')
    rp.add_argument('--out')
    rp.add_argument('--config')
    rp.add_argument('--bounds')
    rp.add_argument('--baseline')
    rpl = sub.add_parser('replay-plan')
    rpl.add_argument('packet')
    rpl.add_argument('--plan', required=True)
    rpl.add_argument('--out', required=True)
    rpl.add_argument('--name', required=True)
    rpl.add_argument('--hold-seconds', type=float, default=500.0)
    vd = sub.add_parser('verdict')
    vd.add_argument('packet')
    vd.add_argument('hunt')
    t = sub.add_parser('table')
    t.add_argument('dir')
    a = ap.parse_args()
    try:
        return {'plan': cmd_plan, 'check': cmd_check, 'run': cmd_run, 'queue': cmd_queue, 'nightly': cmd_nightly, 'analyze': cmd_analyze, 'replay': cmd_replay, 'replay-plan': cmd_replay_plan, 'verdict': cmd_verdict, 'table': cmd_table, 'score': cmd_score}[a.cmd](a)
    except PlanError as e:
        print('refused:', e, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
