#!/usr/bin/env python3
"""Findings become repro packets, one table of known bugs, a triage note each and a replay.

    Registry     the table of what has been found (key -> first and last seen, count, runs, packet, status, note): the same bug found
                 twice is `duplicate` the second time and gets no second packet (a count and a run id instead)
    make_packet  a folder for one finding: packet.json (build, save, seed, the plan's own words, the finding and the detector's
                 evidence), steps.txt (the full input log, as the game side received it), steps.jsonl (each step's result), trace.jsonl
                 (the state samples around it), frames/ (pictures before and after), logs/ (the game's log, both for a pair), triage.md
                 (one paragraph), replay.json and replay.sh
    replay_plan  what to run to drive the same inputs again; replay_verdict compares what the replay found with the packet's key
    classify     real? known issue? harness artefact? from the registry and the configured artefact patterns (a person confirms)

Packets hold game data (logs, pictures, saves, positions): they stay on this machine, in a folder the hunt names (never in git).
Standard library only; nothing here starts a game.

    bugpacket.py show <packet>             the triage note and the replay command
    bugpacket.py registry <known.json>     the table
    bugpacket.py set <known.json> KEY STATUS [NOTE...]
"""
import argparse
import datetime
import fcntl
import gzip
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bughunt  # noqa: E402
import inputlog  # noqa: E402

STATUSES = ('open', 'real', 'known-issue', 'artefact', 'fixed')
TRACE_BEFORE_S, TRACE_AFTER_S = 30.0, 15.0
LOG_WINDOW = 300
SAVE_COPY_MAX = 80 * 1024 * 1024     # a save folder larger than this is referenced by name and hash, not copied


def now():
    return datetime.datetime.now().isoformat(timespec='seconds')


# ====================================================================== the table of known findings

class Registry:
    """known.json: {"entries": {key: {...}}}, rewritten whole under flock and by rename (several hunts share it)."""

    def __init__(self, path):
        self.path = Path(path)
        self.lock = Path(str(path) + '.lock')

    def _read(self):
        try:
            return json.loads(self.path.read_text())['entries']
        except (OSError, ValueError, KeyError):
            return {}

    def entries(self):
        return self._read()

    def lookup(self, key):
        return self._read().get(key)

    def _update(self, fn):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.lock, 'a') as lk:
            fcntl.flock(lk, fcntl.LOCK_EX)
            entries = self._read()
            out = fn(entries)
            tmp = Path(str(self.path) + '.tmp')
            tmp.write_text(json.dumps({'entries': entries}, indent=1) + '\n')
            os.replace(tmp, self.path)
            return out

    def register(self, f, run, packet=None):
        """('new', entry) the first time a key is seen, ('duplicate', entry) after: count and last_seen move, the run is added."""
        def go(entries):
            e = entries.get(f.key)
            if e is None:
                e = entries[f.key] = {'key': f.key, 'kind': f.kind, 'sub': f.sub, 'severity': f.severity, 'text': f.text[:300], 'first_seen': now(),
                                      'last_seen': now(), 'count': 1, 'runs': [run], 'packet': str(packet) if packet else None,
                                      'status': 'artefact' if f.status == 'artefact' else 'open', 'note': ''}
                return 'new', dict(e)
            e['count'] += 1
            e['last_seen'] = now()
            if run not in e['runs']:
                e['runs'] = (e['runs'] + [run])[-20:]
            if packet and not e.get('packet'):
                e['packet'] = str(packet)
            return 'duplicate', dict(e)
        return self._update(go)

    def set_status(self, key, status, note=''):
        if status not in STATUSES:
            raise ValueError(f'status is one of {", ".join(STATUSES)}')

        def go(entries):
            if key not in entries:
                raise KeyError(key)
            entries[key]['status'] = status
            if note:
                entries[key]['note'] = note
            return dict(entries[key])
        return self._update(go)


def classify(f, registry=None):
    """(class, why): `known-issue` / `artefact` when the table or the configured patterns say so, else `open`. A person confirms `real`."""
    if f.status == 'artefact':
        return 'artefact', 'matches a configured harness-artefact pattern'
    e = registry.lookup(f.key) if registry is not None else None
    if e and e['status'] in ('known-issue', 'artefact', 'fixed', 'real'):
        return e['status'], f'the table says {e["status"]}' + (f': {e["note"]}' if e.get('note') else '')
    return 'open', 'not yet triaged'


# ====================================================================== the packet

def dir_hash(path):
    """sha256 over (relative name, size, content hash) of every file of a folder: the identity of a save."""
    h = hashlib.sha256()
    for p in sorted(Path(path).rglob('*')):
        if p.is_file():
            h.update(str(p.relative_to(path)).encode() + b'\0')
            h.update(bughunt.file_hash(p).encode() + b'\0')
    return h.hexdigest()


def dir_size(path):
    return sum(p.stat().st_size for p in Path(path).rglob('*') if p.is_file())


def build_identity(copy):
    """What the build is: built-from.txt's first line (the commit), the version string line of its log if any, the sha256 of the binary."""
    out = {'copy': Path(copy).name if copy else None}
    if copy:
        bf = Path(copy) / 'built-from.txt'
        if bf.is_file():
            out['built_from'] = bf.read_text(errors='replace').strip().splitlines()[0][:80]
        exe = next((Path(copy) / n for n in bughunt.EXE_NAMES if (Path(copy) / n).is_file()), None)
        if exe:
            out['binary'] = exe.name
            out['binary_sha256'] = bughunt.file_hash(exe)
    return out


def copy_file(src, dst):
    """One file, reflinked where the filesystem can (the pictures are large)."""
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(['cp', '--reflink=auto', '-p', str(src), str(dst)], capture_output=True)
    if r.returncode != 0 or not Path(dst).exists():
        shutil.copy2(src, dst)


def gz_copy(src, dst):
    with open(src, 'rb') as a, gzip.open(dst, 'wb') as b:
        shutil.copyfileobj(a, b)


def log_window(lines, frame, width=LOG_WINDOW):
    """The lines around a present number: found by the first marker (`vk: present N written`, `vk: N presents`) at or after it."""
    if not lines:
        return []
    marker = re.compile(r'vk: present (\d+) written|vk: (\d+) presents')
    at = None
    for i, ln in enumerate(lines):
        m = marker.search(ln)
        if m and int(m.group(1) or m.group(2)) >= (frame or 0):
            at = i
            break
    if at is None:
        return lines[-2 * width:]
    return lines[max(0, at - width):at + width + 1]


def trace_window(side, t):
    if t is None:
        return []
    return [r for r in side.states if t - TRACE_BEFORE_S <= r['t'] <= t + TRACE_AFTER_S]


def frames_around(side, frame, n=2):
    shots = side.shots
    before = [s for s in shots if s[0] <= (frame or 0)][-n:]
    after = [s for s in shots if s[0] > (frame or 0)][:n]
    return before, after


def triage_text(f, side, session, cls, why, replay_cmd):
    """One paragraph: what, where, when, with which inputs, what the evidence is, what class it looks like, how to replay."""
    steps = []
    if side is not None and f.t is not None:
        for t, e in side.step_times():
            if t <= f.t:
                steps.append(e)
    last = '; '.join(f'{(e.get("src") or "")[:60]} -> {e.get("result")}' for e in steps[-3:]) or 'no step before it'
    where = f'on {f.map} near ({f.pos[0]:.0f}, {f.pos[2]:.0f})' if f.pos else (f'on {f.map}' if f.map else 'at an unknown place')
    when = f'{f.game_s:.0f} s into the play' if f.game_s is not None else 'at an unknown time'
    ev = ', '.join(f'{k}={v}' for k, v in list(f.evidence.items())[:5] if not isinstance(v, (dict, list)))
    run = (session or {}).get('run', 'this run')
    seed = (session or {}).get('seed')
    return (f'{f.kind}/{f.sub} ({f.severity}) in {run} {where}, {when}: {f.text}. The inputs before it ended with: {last}. '
            f'Evidence: {ev or "see evidence.json"}. It looks like: {cls} ({why}). '
            f'Seed {seed if seed is not None else "n/a"}, key {f.key}. To check it again: {replay_cmd}')


def make_packet(out_dir, f, sides, session=None, registry=None, replay_cmd=None):
    """The folder of one finding. `sides` {name: Side} (one for a solo session, two for a pair); the finding's own side is `f.side`
    (a pair finding with side `pair` takes every side's log). Returns the folder."""
    session = session or {}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    own = sides.get(f.side) or next(iter(sides.values()))
    cls, why = classify(f, registry)
    # the input log and the steps with their results
    for name, s in sides.items():
        suffix = '' if len(sides) == 1 else f'.{name}'
        lines = s.steps_text
        if lines:
            (out / f'steps{suffix}.txt').write_text('\n'.join(lines) + '\n')
        if s.steps:
            (out / f'steps{suffix}.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in s.steps))
        if s.state_path and f.t is not None:
            tr = trace_window(s, f.t)
            (out / f'trace{suffix}.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in tr))
    # the input log at the bridge: hsap's journal, the recording made from it, and what the game's own script grammar can say of it
    inputs_info = None
    own_inputs = own.inputs
    if own_inputs:
        shutil.copy2(own.inputs_path, out / 'inputs.jsonl')
        hdr = {'key': f.key, 'build': build_identity(session.get('copy')).get('built_from'), 'save': session.get('save_name'), 'seed': session.get('seed'),
               'boot': session.get('boot') or 'continue'}
        gp = own.gameplay
        rec = inputlog.to_recording(own_inputs, start=own_inputs[0].get('present', 0), **{k: v for k, v in hdr.items() if v is not None})
        inputlog.write_recording(out / 'recording.jsonl', rec)
        hos, lossy = inputlog.to_hos_script(rec[1:])
        (out / 'inputs.hos').write_text(hos + '\n')
        inputs_info = {'requests': len(own_inputs), 'recording': 'recording.jsonl', 'hos_script': 'inputs.hos', 'hos_lossy': lossy}
        del gp
    # pictures
    frames = []
    before, after = frames_around(own, f.frame)
    for tag, group in (('before', before), ('after', after)):
        for k, (fr, p) in enumerate(group):
            dst = out / 'frames' / f'{tag}-{k + 1}-{p.name}'
            copy_file(p, dst)
            frames.append(dst.name)
    burst_name = (f.evidence or {}).get('burst')
    if burst_name:   # a flicker finding: every picture of its burst, in order (the three that made the pattern are named in evidence.json)
        for name, _why, pics in own.bursts:
            if name == burst_name:
                for k, (fr, p) in enumerate(pics):
                    dst = out / 'frames' / f'burst-{k + 1:02d}-{p.name}'
                    copy_file(p, dst)
                    frames.append(dst.name)
    # logs
    logs = {}
    for name, s in sides.items():
        if s.log_path:   # (a pair's packet has both games' logs: the other game's log is half the evidence of a co-op finding)
            (out / 'logs').mkdir(exist_ok=True)
            gz_copy(s.log_path, out / 'logs' / f'{name}.log.gz')
            w = log_window(s.log, f.frame if name == own.name or f.side != 'pair' else None)
            (out / 'logs' / f'{name}-window.txt').write_text('\n'.join(w) + '\n')
            logs[name] = f'logs/{name}.log.gz'
    # save and build
    save = session.get('save')
    save_info = None
    if save and Path(save).is_dir():
        save_info = {'name': session.get('save_name') or Path(save).name, 'sha256': dir_hash(save), 'bytes': dir_size(save)}
        if save_info['bytes'] <= SAVE_COPY_MAX:
            shutil.copytree(save, out / 'save', dirs_exist_ok=True, copy_function=shutil.copy2)
            save_info['copied'] = True
        else:
            save_info['copied'] = False
    segment = session.get('segment')
    if segment and Path(segment).is_file():
        shutil.copy2(segment, out / 'segment.toml')
    case = session.get('case')
    if case and Path(case).is_file():
        shutil.copy2(case, out / 'case.toml')
    rp = replay_plan(session, out, f)
    if replay_cmd is None:
        replay_cmd = rp.get('command_text') or 'see replay.json'
    packet = {'key': f.key, 'made': now(), 'finding': f.to_dict(), 'class': cls, 'class_why': why, 'run': session.get('run'), 'kind': session.get('kind'),
              'build': build_identity(session.get('copy')), 'save': save_info, 'segment': Path(segment).name if segment else None,
              'seed': session.get('seed'), 'humanize': session.get('humanize'), 'decider': session.get('decider'),
              'plan': {k: v for k, v in session.items() if k in ('name', 'kind', 'wall', 'shots', 'env', 'humanize', 'seed', 'decider', 'boot', 'place')},
              'frames': frames, 'logs': logs, 'sides': list(sides), 'replay': rp}
    if inputs_info:
        packet['inputs'] = inputs_info
    (out / 'packet.json').write_text(json.dumps(packet, indent=1) + '\n')
    (out / 'evidence.json').write_text(json.dumps(f.evidence, indent=1) + '\n')
    (out / 'triage.md').write_text(triage_text(f, own, session, cls, why, replay_cmd) + '\n')
    (out / 'replay.json').write_text(json.dumps(rp, indent=1) + '\n')
    (out / 'replay.sh').write_text('#!/bin/bash\n# Re-drives this packet\'s inputs. Inside a hold only: ' + (rp.get('command_text') or '') + '\n'
                                   + f'python3 -I -B {shlex.quote(str(HERE / "hunt.py"))} replay {shlex.quote(str(out))} "$@"\n')
    os.chmod(out / 'replay.sh', 0o755)
    return out


# ====================================================================== replay

GAP_MIN_S = 0.75


def steps_with_gaps(side, lines=None):
    """The input log with the waits the original had between steps put back: the pilot thinks between decisions while the game goes on;
    a step's `t` is the sample-clock-free game seconds at its end and `secs` its length, so the gap before step n+1 is its start minus
    the end of step n. Lines whose events are not found are sent as they were."""
    lines = list(lines if lines is not None else side.steps_text)
    evs = {e.get('in'): e for e in side.steps if e.get('in')}
    out, prev_end = [], None
    for i, ln in enumerate(lines, 1):
        e = evs.get(i)
        if e and e.get('t') is not None and prev_end is not None:
            start = e['t'] - (e.get('secs') or 0.0)
            gap = start - prev_end
            if gap >= GAP_MIN_S:
                out.append(f'wait {gap:.1f}')
        out.append(ln)
        if e and e.get('t') is not None:
            prev_end = e['t']
    return out


def replay_plan(session, packet_dir, f=None):
    """What re-drives this packet. solo: hsap with the saved steps (waits put back) on the saved start; pair: the case file again with
    the same segments and seeds (the pilots are rules deciders: the same game states give the same decisions). Nothing runs here."""
    kind = session.get('kind') or 'solo'
    plan = {'mode': 'steps' if kind == 'solo' else 'case', 'key': f.key if f else None}
    if kind == 'solo':
        plan.update({'steps': 'steps.txt', 'save': 'save' if (Path(packet_dir) / 'save').is_dir() else None, 'boot': session.get('boot') or 'continue',
                     'wall': int(session.get('wall') or 180), 'shots': session.get('shots') or 90, 'env': session.get('env') or [],
                     'segment': 'segment.toml' if session.get('segment') else None, 'place': session.get('place')})
        plan['command_text'] = f'hunt.py replay {packet_dir} --copy <a game copy of the same build> (inside a hold)'
    else:
        plan.update({'case': 'case.toml' if session.get('case') else None, 'command_text': f'coopplay.py run {packet_dir}/case.toml --out <new folder> (a queued hold)'})
    return plan


def prepare_replay(packet_dir, live_dir, with_gaps=True, mode='steps'):
    """Writes <live_dir>/steps.txt from the packet (an `end` after the last line) and returns the packet. For a solo packet. mode `steps`: the
    pilot's own steps (the walks are closed loops that steer from the game's state: the same decisions, not the same stick values);
    mode `inputs`: the recording's requests, exact stick values and frame gaps (needs the packet's recording.jsonl)."""
    packet_dir, live_dir = Path(packet_dir), Path(live_dir)
    pk = json.loads((packet_dir / 'packet.json').read_text())
    if pk['replay']['mode'] != 'steps':
        raise ValueError('a pair packet replays through its case file, not a steps file')
    if mode == 'inputs':
        if not (packet_dir / 'recording.jsonl').is_file():
            raise ValueError('no recording in this packet (the session had no input journal): replay it in steps mode')
        _, events = inputlog.read_recording(packet_dir / 'recording.jsonl')
        lines = inputlog.to_hsap_steps(events)
    else:
        lines = (packet_dir / 'steps.txt').read_text().splitlines()
        if with_gaps:
            side = bughunt.Side(packet_dir)
            side._cache['events'] = [json.loads(ln) for ln in (packet_dir / 'steps.jsonl').read_text().splitlines()] if (packet_dir / 'steps.jsonl').exists() else []
            lines = steps_with_gaps(side, lines)
    lines = [ln for ln in lines if ln.strip() != 'end'] + ['end']
    live_dir.mkdir(parents=True, exist_ok=True)
    (live_dir / 'steps.txt').write_text('\n'.join(lines) + '\n')
    return pk


def fresh_rendezvous(case_text, folder):
    """The case's text with every rendezvous folder (HSAP_RENDEZVOUS=<dir> in a side's env) replaced by `folder`, made empty: a replay must
    not meet the files of the run it replays (a stale name there would release a side at once)."""
    folder = Path(folder)
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    return re.sub(r'HSAP_RENDEZVOUS=[^"\']*', f'HSAP_RENDEZVOUS={folder}', case_text)


def replay_verdict(packet_key, findings):
    """('reproduced' | 'similar' | 'not reproduced', detail): the same key among the replay's findings; the same kind and subtype elsewhere;
    nothing of that kind."""
    errs = [f for f in findings if f.severity != 'info']
    if any(f.key == packet_key for f in errs):
        return 'reproduced', 'the same key fired again'
    kind, sub = packet_key.split(':')[:2]
    sim = [f for f in errs if f.kind == kind and f.sub == sub]
    if sim:
        return 'similar', f'{kind}/{sub} fired at another place: {sim[0].key}'
    return 'not reproduced', f'no {kind} finding in the replay' + (f' ({len(errs)} other finding(s))' if errs else '')


# ====================================================================== CLI

def cmd_show(a):
    p = Path(a.packet)
    print((p / 'triage.md').read_text())
    print(json.dumps(json.loads((p / 'replay.json').read_text()), indent=1))
    return 0


def cmd_registry(a):
    for k, e in sorted(Registry(a.path).entries().items(), key=lambda kv: kv[1]['first_seen']):
        print(f'{e["status"]:11} x{e["count"]:<3} {k}  {e["text"][:100]}')
    return 0


def cmd_set(a):
    e = Registry(a.path).set_status(a.key, a.status, ' '.join(a.note))
    print(json.dumps(e, indent=1))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('show')
    s.add_argument('packet')
    r = sub.add_parser('registry')
    r.add_argument('path')
    t = sub.add_parser('set')
    t.add_argument('path')
    t.add_argument('key')
    t.add_argument('status', choices=STATUSES)
    t.add_argument('note', nargs='*')
    a = ap.parse_args()
    return {'show': cmd_show, 'registry': cmd_registry, 'set': cmd_set}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
