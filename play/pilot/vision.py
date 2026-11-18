#!/usr/bin/env python3
"""The pilot's eyes: at the points where the state line is not enough, the pilot looks at the game's own picture.

What it does. Before a decision (Vision.before_decision, called by pilot.py) the pilot may ask a vision-capable model a
FIXED set of questions about the latest frame: what is in front of Link (a choice), what kind of screen it is (a choice), and
probabilities for: a door, a chest, an enemy, a person, Link stuck on something, a text box, the way clear to his left and to
his right, a second player's body, and whether that body looks right. The answer becomes
  - a `hint` dict that the pilot puts in the state line as st['vision'] (the decider reads it),
  - EXTRA CANDIDATES (labels `vision-...`, hsap step lines) the decider may choose,
  - an ODDITY record when picture and state disagree (a text box with no event, an unexpected screen, a body that looks wrong
    or is missing, Link stuck, a snap of his place, an unexpected map).
When it looks: the first decision; when the last moves ended stuck or the recovery ladder says stuck; when the tap says an event
holds Link (a text box); when the map changed or is not the segment's; when Link's place jumped more than his last steps
explain (a snap); when a follow target is near (the other player's body); and every `every_s` seconds of wall time (default 60).
Looks are spaced (`min_gap_s`) and bounded (`max_looks`); the caps and the ledger are openai_api's (kind 'vision').

What leaves the machine: ONLY the downscaled picture (the game's own frame, without the Insert menu or FPS counter: the
control bridge's `shot`), one fixed instruction text, the fixed questions and one fixed reason word. No path, log line, flag,
coordinate or name. The picture sent is kept in <run>/vision/ (f0001.jpg ...), with vision.jsonl (one row per look: answers,
cost, latency, what it offered) and oddities.jsonl. These are game-derived files: never published.

Backends (the vision model is the user's choice, `probe` finds which models of the configured API take pictures):
  decisions  POST /v1/decisions, input_image + typed questions (choice/predicate answers with probabilities), gpt-6-luna.
  responses  POST /v1/responses, input_image + a JSON schema of the same questions plus one sentence (`says`), any model that
             takes images (gpt-6.1-terra, gpt-6.1-sol, gpt-6-astra ...).

The switch: pilot.py --vision off|on (default off), or PILOT_VISION=on. Everything fails soft: a vision error is a row in
vision.jsonl and no hint; three failures in a row, a cap or no key turn the eyes off for the run.

  vision.py probe [--models a,b] [--backends decisions,responses]   which models take pictures, and what a look costs
  vision.py look <picture.png|jpg> [--backend B] [--model M]         ask the fixed questions about one picture file
  vision.py compare <picture> ... --arms decisions:gpt-6-luna,responses:gpt-6-astra   the same pictures to several models: where they agree
"""
import argparse
import base64
import json
import math
import os
import random
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import zlib
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import openai_api  # noqa: E402

HI = 0.6                 # a probability from this up is "yes" for a candidate or a hint
ODD = 0.7                # ... and for an oddity record
DEVELOPER = (
    'You look at ONE picture from a 3D action-adventure video game that an automatic test pilot is playing, and answer '
    'fixed questions about what is visible. Link is the hero, seen from behind, in the middle of the lower half of the '
    'picture; "ahead" is straight up the picture from him. The picture is the game\'s own render: a heads-up display with '
    'hearts and buttons may be drawn over it. Answer only from what you can see; when it is not visible, say so with a low '
    'probability or the choice "other". A second player in this game is drawn like Link, usually with a small name label '
    'above the head.')
FRONT = [
    ('open_ground', 'nothing blocks the way straight ahead: open ground, a path, grass, a floor'),
    ('wall_or_obstacle', 'a wall, cliff face, fence, tree, rock, pillar, crate or other solid thing is right ahead and blocks the way'),
    ('water', 'water straight ahead (a lake, river, pond)'),
    ('drop_or_hole', 'a ledge, a drop, a gap or a hole straight ahead'),
    ('door', 'a door or a doorway straight ahead'),
    ('chest', 'a treasure chest straight ahead'),
    ('person', 'a person or other friendly character straight ahead'),
    ('enemy', 'a hostile creature straight ahead'),
    ('sign_or_switch', 'a signpost, an inscribed stone, a switch or a lever straight ahead'),
    ('ladder_or_vines', 'a ladder, vines or a climbable wall straight ahead'),
    ('other', 'none of these, or it cannot be told'),
]
SCREEN = [
    ('play', 'normal play: the hero in a 3D world with the heads-up display, nothing drawn over the picture'),
    ('text_box', 'a dialogue or message box is drawn over the picture: a dark box with a speaker\'s name or lines of text that waits '
                 'for the player to press a button (subtitles over a cinematic are not a text box)'),
    ('menu', 'a pause, map, item or settings menu fills the picture'),
    ('cutscene', 'a cinematic scene: a scripted camera, no heads-up display, maybe subtitles along the bottom'),
    ('loading', 'a black or nearly black screen, a fade, or a loading screen'),
    ('title', 'a title or file-select screen'),
    ('game_over', 'a game over screen'),
    ('other', 'something else'),
]
PREDICATES = [
    ('door', 'Is a door or a doorway visible in the picture?'),
    ('chest', 'Is a treasure chest visible in the picture?'),
    ('enemy', 'Is a hostile creature (a monster, a skeleton, a plant that attacks) visible in the picture?'),
    ('npc', 'Is a person or friendly character other than Link visible and apart from a second player?'),
    ('stuck', 'Is Link pressed against something solid (a wall, fence, rock, tree, ledge, the edge of the world) so that '
              'walking straight ahead would not move him?'),
    ('text_box', 'Is a dialogue or message box drawn over the picture: a dark box with a speaker\'s name or lines of text that waits for '
                 'the player to press a button? Subtitles over a cinematic are NOT a text box.'),
    ('clear_left', 'Is the ground to Link\'s left, a few steps away, open and walkable (no wall, water or drop)?'),
    ('clear_right', 'Is the ground to Link\'s right, a few steps away, open and walkable (no wall, water or drop)?'),
    ('other_body', 'Is a second character drawn like Link (another player), maybe with a name label, visible in the picture?'),
    ('other_body_ok', 'If a second player character is visible: does it look right (a whole character standing or moving '
                      'on the ground, normal proportions, nothing stretched, missing, doubled or floating)? If none is '
                      'visible, answer with a low probability.'),
]
REASONS = {   # the one fixed word of context (never a coordinate or a name)
    'first': 'This is the first look of the run.', 'stuck': 'The pilot\'s last moves did not get Link anywhere.',
    'text-box': 'The game says an event may be holding Link.', 'map': 'Link has just entered a different map.',
    'snap': 'Link\'s place just changed more than his walking explains.', 'body': 'The other player should be nearby.',
    'body-snap': 'The other player\'s place just jumped farther than anyone runs.',
    'periodic': 'A regular look.', 'forced': 'A requested look.'}
STUCK_RESULTS = ('stuck', 'timeout', 'cut')
LABELS = ('vision-fight', 'vision-talk', 'vision-side-left', 'vision-side-right', 'vision-wait-scene', 'vision-close-menu')


# ---- pictures: stdlib PNG reading and downscaling (the fallback when no `magick`), the capture from the control bridge

def read_png(data):
    """(width, height, rgb bytes) of an 8-bit non-interlaced PNG (gray, RGB, palette, gray+alpha or RGBA)."""
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('not a PNG')
    pos, ihdr, idat, plte = 8, None, [], None
    while pos + 8 <= len(data):
        n, kind = struct.unpack('>I4s', data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        pos += 12 + n
        if kind == b'IHDR':
            ihdr = struct.unpack('>IIBBBBB', body)
        elif kind == b'PLTE':
            plte = body
        elif kind == b'IDAT':
            idat.append(body)
        elif kind == b'IEND':
            break
    if ihdr is None:
        raise ValueError('no IHDR')
    w, h, depth, ctype, _, _, interlace = ihdr
    if depth != 8 or interlace != 0 or ctype not in (0, 2, 3, 4, 6):
        raise ValueError(f'unsupported PNG (depth {depth}, colour type {ctype}, interlace {interlace})')
    bpp = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    raw = zlib.decompress(b''.join(idat))
    stride = w * bpp
    if len(raw) < h * (stride + 1):
        raise ValueError('PNG data is short')
    out, prev, pos = bytearray(h * stride), bytearray(stride), 0
    for y in range(h):
        ft = raw[pos]
        row = bytearray(raw[pos + 1:pos + 1 + stride])
        pos += 1 + stride
        if ft == 1:
            for i in range(bpp, stride):
                row[i] = (row[i] + row[i - bpp]) & 255
        elif ft == 2:
            for i in range(stride):
                row[i] = (row[i] + prev[i]) & 255
        elif ft == 3:
            for i in range(stride):
                a = row[i - bpp] if i >= bpp else 0
                row[i] = (row[i] + ((a + prev[i]) >> 1)) & 255
        elif ft == 4:
            for i in range(stride):
                a = row[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                row[i] = (row[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        elif ft != 0:
            raise ValueError(f'bad PNG filter {ft}')
        out[y * stride:(y + 1) * stride] = row
        prev = row
    rgb = bytearray(w * h * 3)
    if ctype == 2:
        rgb = out
    elif ctype == 6:
        rgb[0::3], rgb[1::3], rgb[2::3] = out[0::4], out[1::4], out[2::4]
    elif ctype == 0:
        rgb[0::3] = rgb[1::3] = rgb[2::3] = out
    elif ctype == 4:
        rgb[0::3] = rgb[1::3] = rgb[2::3] = out[0::2]
    else:
        pal = plte or b''
        for c in range(3):
            table = bytes(pal[i * 3 + c] if i * 3 + c < len(pal) else 0 for i in range(256))
            rgb[c::3] = out.translate(table)
    return w, h, bytes(rgb)


def write_png(w, h, rgb):
    def chunk(kind, body):
        return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body) & 0xffffffff)
    stride = w * 3
    raw = b''.join(b'\x00' + bytes(rgb[y * stride:(y + 1) * stride]) for y in range(h))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))


def _taps(src, dst):
    """For each of dst output positions the (source index, weight) pairs of an area average over src positions."""
    scale, out = src / dst, []
    for d in range(dst):
        lo, hi = d * scale, (d + 1) * scale
        out.append([(s, (min(hi, s + 1) - max(lo, s)) / scale) for s in range(int(lo), min(src - 1, int(hi - 1e-9)) + 1)
                    if min(hi, s + 1) > max(lo, s)])
    return out


def downscale_rgb(w, h, rgb, tw, th):
    """Area-average resize of an RGB byte string to tw x th (never enlarges: tw, th are clamped to w, h)."""
    tw, th = min(tw, w), min(th, h)
    if (tw, th) == (w, h):
        return w, h, bytes(rgb)
    cols, rows = _taps(w, tw), _taps(h, th)
    mid = []   # horizontally resampled rows, as float lists of tw * 3
    for y in range(h):
        row = rgb[y * w * 3:(y + 1) * w * 3]
        line = [0.0] * (tw * 3)
        for x, taps in enumerate(cols):
            for c in range(3):
                line[x * 3 + c] = sum(row[s * 3 + c] * wt for s, wt in taps)
        mid.append(line)
    out = bytearray(tw * th * 3)
    for y, taps in enumerate(rows):
        acc = [sum(mid[s][i] * wt for s, wt in taps) for i in range(tw * 3)]
        out[y * tw * 3:(y + 1) * tw * 3] = bytes(min(255, int(v + 0.5)) for v in acc)
    return tw, th, bytes(out)


def has_magick():
    return shutil.which('magick') is not None


def downscale_file(src, dst_base, width, use_magick=None):
    """Write the picture `src` (PNG) downscaled to `width` pixels across (aspect kept, never enlarged) next to dst_base: a JPEG
    through ImageMagick when it is installed, else a PNG made here. Returns (path, w, h, mime)."""
    src, dst_base = Path(src), Path(dst_base)
    use_magick = has_magick() if use_magick is None else use_magick
    w, h, rgb = None, None, None
    if use_magick:
        try:
            size = subprocess.run(['magick', 'identify', '-format', '%w %h', str(src)], capture_output=True, text=True,
                                  timeout=20, check=True).stdout.split()
            w, h = int(size[0]), int(size[1])
            tw = min(width, w)
            th = max(1, round(h * tw / w))
            dst = dst_base.with_suffix('.jpg')
            subprocess.run(['magick', str(src), '-resize', f'{tw}x{th}!', '-strip', '-quality', '88', str(dst)],
                           capture_output=True, timeout=30, check=True)
            return dst, tw, th, 'image/jpeg'
        except (OSError, subprocess.SubprocessError, ValueError, IndexError):
            pass   # fall through to the stdlib path
    w, h, rgb = read_png(src.read_bytes())
    tw = min(width, w)
    tw, th, small = downscale_rgb(w, h, rgb, tw, max(1, round(h * tw / w)))
    dst = dst_base.with_suffix('.png')
    dst.write_bytes(write_png(tw, th, small))
    return dst, tw, th, 'image/png'


def control_socket(copy, run_id):
    """The control bridge's socket of a run hs-run.sh started (HOS_CONTROL in its env-used.txt), or None."""
    try:
        for line in (Path(copy) / 'runs' / run_id / 'env-used.txt').read_text().splitlines():
            if line.startswith('HOS_CONTROL='):
                return Path(line.split('=', 1)[1].strip())
    except OSError:
        pass
    return None


class BridgeError(Exception):
    pass


def bridge_shot(sock_path, out_path, timeout=12.0):
    """One `shot` over its own short connection to the control bridge (docs/control.md): the game's PNG of the first present
    after the request, written whole at out_path. Returns the reply (frame, present, path, width, height)."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout + 2)
    try:
        s.connect(str(sock_path))
        s.sendall(json.dumps({'id': 1, 'cmd': 'shot', 'path': str(out_path), 'timeout': timeout}).encode() + b'\n')
        buf = b''
        end = time.time() + timeout + 2
        while time.time() < end:
            data = s.recv(65536)
            if not data:
                raise BridgeError('the control socket closed')
            buf += data
            *lines, buf = buf.split(b'\n')
            for line in lines:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict) and r.get('id') == 1 and 'ok' in r:
                    if not r['ok']:
                        raise BridgeError(f"shot: {r.get('error')}: {r.get('message')}")
                    return r
        raise BridgeError('no reply to shot')
    except (OSError, socket.timeout) as e:
        raise BridgeError(f'{type(e).__name__}: {e}') from None
    finally:
        s.close()


class Capture:
    """The latest frame, downscaled, written under <vision dir>: from the control bridge (a fresh `shot`), else the newest
    picture the game wrote itself (<copy>/runs/<tag>/shots, at most max_age_s old). The full-size shot is deleted once the
    downscaled copy exists (the disk is small); the downscaled copy is the file that is sent and kept."""

    def __init__(self, vdir, width=960, sock=None, shots_dir=None, max_age_s=45.0, copy=None, run_id=None, use_magick=None):
        self.vdir, self.width, self.sock, self.shots_dir = Path(vdir), width, sock, shots_dir
        self.max_age_s, self.copy, self.run_id, self.use_magick = max_age_s, copy, run_id, use_magick
        self.seq = 0

    def _sock(self):
        if self.sock:
            return Path(self.sock)
        return control_socket(self.copy, self.run_id) if self.copy and self.run_id else None

    def _shots(self):
        if self.shots_dir:
            return Path(self.shots_dir)
        return Path(self.copy) / 'runs' / self.run_id / 'shots' if self.copy and self.run_id else None

    def __call__(self):
        """(path, w, h, mime, how) of the new downscaled copy. Raises BridgeError."""
        self.vdir.mkdir(parents=True, exist_ok=True)
        self.seq += 1
        raw = self.vdir / f'raw{self.seq:04d}.png'
        sock, how, err = self._sock(), None, None
        if sock is not None:
            try:
                bridge_shot(sock, raw)
                how = 'bridge'
            except BridgeError as e:
                err = str(e)
        if how is None:
            folder = self._shots()
            newest = max(folder.glob('*.png'), key=lambda p: p.stat().st_mtime, default=None) if folder and folder.is_dir() else None
            if newest is None or time.time() - newest.stat().st_mtime > self.max_age_s:
                raise BridgeError(err or 'no control socket and no recent picture in the run\'s shots folder')
            shutil.copyfile(newest, raw)
            how = 'folder'
        try:
            path, w, h, mime = downscale_file(raw, self.vdir / f'f{self.seq:04d}', self.width, self.use_magick)
        except (OSError, ValueError, zlib.error) as e:
            raise BridgeError(f'downscale: {type(e).__name__}: {e}') from None
        finally:
            raw.unlink(missing_ok=True)
        return path, w, h, mime, how


# ---- the questions: one source for both backends

def question_names():
    return ['front', 'screen'] + [n for n, _ in PREDICATES]


def decisions_questions():
    qs = [{'type': 'choice', 'name': 'front', 'instructions': 'What is straight ahead of Link, within a few steps?',
           'choices': [{'value': v, 'description': d} for v, d in FRONT]},
          {'type': 'choice', 'name': 'screen', 'instructions': 'What kind of screen is this?',
           'choices': [{'value': v, 'description': d} for v, d in SCREEN]}]
    qs += [{'type': 'predicate', 'name': n, 'instructions': q} for n, q in PREDICATES]
    return qs


def decisions_body(model, data_url, reason):
    return {'model': model,
            'input': [{'role': 'developer', 'content': DEVELOPER},
                      {'role': 'user', 'content': [
                          {'type': 'input_text', 'text': 'The picture. ' + REASONS.get(reason, REASONS['forced'])},
                          {'type': 'input_image', 'image_url': data_url}]}],
            'questions': decisions_questions(),
            'prompt_cache_key': 'ls-pilot-vision'}


def responses_schema():
    props = {'says': {'type': 'string'},
             'front': {'type': 'string', 'enum': [v for v, _ in FRONT]},
             'screen': {'type': 'string', 'enum': [v for v, _ in SCREEN]}}
    props.update({n: {'type': 'number'} for n, _ in PREDICATES})
    return {'type': 'object', 'additionalProperties': False, 'required': list(props), 'properties': props}


def responses_body(model, data_url, reason):
    ask = ('Answer with the JSON object of the schema. `says`: one short sentence of what is in front of Link. `front`: ' +
           '; '.join(f'{v} = {d}' for v, d in FRONT) + '. `screen`: ' + '; '.join(f'{v} = {d}' for v, d in SCREEN) +
           '. Each other field is the probability from 0 to 1 that the answer to its question is yes: ' +
           ' '.join(f'{n}: {q}' for n, q in PREDICATES))
    return {'model': model,
            'input': [{'role': 'developer', 'content': DEVELOPER},
                      {'role': 'user', 'content': [
                          {'type': 'input_text', 'text': REASONS.get(reason, REASONS['forced']) + ' ' + ask},
                          {'type': 'input_image', 'image_url': data_url, 'detail': 'auto'}]}],
            'text': {'format': {'type': 'json_schema', 'name': 'look', 'schema': responses_schema(), 'strict': True}},
            'max_output_tokens': 4000}


def _clamp(v):
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return None


def parse_decisions(ans):
    """The normalized look from a /v1/decisions answer: {front, screen, p: {name: probability}, says, confidence}. A refused or
    missing answer is None for that field."""
    got = {a.get('name'): a for a in (ans or {}).get('answers', []) if isinstance(a, dict)}
    out = {'front': None, 'screen': None, 'p': {}, 'says': None, 'confidence': {}}
    for name, valid in (('front', [v for v, _ in FRONT]), ('screen', [v for v, _ in SCREEN])):
        a = got.get(name) or {}
        if a.get('type') == 'choice' and a.get('choice') in valid:
            out[name] = a['choice']
            out['confidence'][name] = _clamp(a.get('confidence'))
    for name, _ in PREDICATES:
        a = got.get(name) or {}
        if a.get('type') == 'predicate':
            out['p'][name] = _clamp(a.get('probability'))
    return out


def parse_responses(ans):
    text = ''
    for item in (ans or {}).get('output', []):
        if isinstance(item, dict) and item.get('type') == 'message':
            for part in item.get('content', []):
                if isinstance(part, dict) and part.get('type') == 'output_text':
                    text += part.get('text', '')
    data = json.loads(text)
    out = {'front': data.get('front') if data.get('front') in [v for v, _ in FRONT] else None,
           'screen': data.get('screen') if data.get('screen') in [v for v, _ in SCREEN] else None,
           'p': {n: _clamp(data.get(n)) for n, _ in PREDICATES if n in data}, 'says': str(data.get('says') or '')[:240] or None,
           'confidence': {}}
    return out


def image_tokens(w, h, multiplier=1.2):
    """The documented patch-count estimate for an image input (32 px patches, 1.2x): used only for the cap estimate."""
    return int(-(-w // 32) * -(-h // 32) * multiplier) + 1


# ---- the eyes

@dataclass
class Look:
    hint: dict
    extra: list = field(default_factory=list)   # [(label, lines, text)] for pilot.Candidate(*e)
    fresh: bool = True
    row: dict = None


class Vision:
    """See the module docstring. `capture()` returns (path, w, h, mime, how) and may raise BridgeError."""
    TEST_REASON = None

    def __init__(self, client, run_dir, capture, backend=None, model=None, every_s=60.0, min_gap_s=6.0, max_looks=200,
                 hint_ttl_s=25.0, area=None, clock=time.time, timeout=60.0):
        c = openai_api.caps()
        self.client, self.capture, self.clock, self.timeout = client, capture, clock, timeout
        self.backend = backend or c['vision_backend']
        self.model = model or c['vision_model']
        if self.backend not in ('decisions', 'responses'):
            raise ValueError(f'vision backend {self.backend!r}: decisions or responses')
        self.every_s, self.min_gap_s, self.max_looks, self.hint_ttl_s = every_s, min_gap_s, max_looks, hint_ttl_s
        self.area = area                      # the segment's own map: another one is unexpected
        self.dir = Path(run_dir) / 'vision'
        self.dir.mkdir(parents=True, exist_ok=True)
        self.rows = open(self.dir / 'vision.jsonl', 'a')
        self.odd = open(self.dir / 'oddities.jsonl', 'a')
        self.seq, self.errors, self.off_reason = 0, 0, None
        self.last_wall = self.last_stuck_wall = self.last_text_wall = self.last_body_wall = None
        self.last_stuck_pos = self.last_area = self.last_state = self.last_follow = None
        self.last = None                      # (wall, pos, Look) of the last fresh look: the hint is reused a while
        self.tally = {'looks': 0, 'errors': 0, 'cost_usd': 0.0, 'by_reason': {}, 'oddities': {}, 'extra_offered': {}}
        self.latencies = []

    # -- when to look

    def reasons(self, st, goal, target, mem, tried, now):
        r = []
        pos = st.get('pos')
        if self.seq == 0:
            r.append('first')
        h = (mem or {}).get('history') or []
        rec = (mem or {}).get('recover') or {}
        two = len(h) >= 2 and all(e[1] in STUCK_RESULTS and e[2] < 0.5 for e in h[-2:])
        if rec.get('stuck') or two:
            moved_away = self.last_stuck_pos is None or (pos and flat_dist(pos, self.last_stuck_pos) > 3.0)
            if self.last_stuck_wall is None or moved_away or now - self.last_stuck_wall >= 4 * self.min_gap_s:
                r.append('stuck')
        if st.get('event') == 1 and not (st.get('music') or '').startswith('Dm_') and not st.get('scene'):
            if self.last_text_wall is None or now - self.last_text_wall >= 20.0:
                r.append('text-box')
        area = st.get('area')
        if area and ((self.last_area is not None and area != self.last_area) or (self.area and area != self.area and self.seq == 0)):
            r.append('map')
        if pos and self.last_state and self.last_state.get('pos') and tried and not st.get('loading') and \
                st.get('area') == self.last_state.get('area'):
            jump = flat_dist(pos, self.last_state['pos'])
            if jump > (tried[-1].get('moved_m') or 0) + 3.0:
                r.append('snap')
        if target is not None and getattr(target, 'follow', None):
            prev, self.last_follow = self.last_follow, (target.x, target.z, now)
            if prev and 0 < now - prev[2] <= 30.0 and (target.x, target.z) != prev[:2]:   # the other player's body jumped: faster than anyone runs
                d = math.hypot(target.x - prev[0], target.z - prev[1])
                if d >= 3.0 and d / (now - prev[2]) > 20.0:
                    r.append('body-snap')
            if pos and (self.last_body_wall is None or now - self.last_body_wall >= 90.0) and flat_dist(pos, (target.x, 0, target.z)) <= 14.0:
                r.append('body')
        if self.last_wall is None or now - self.last_wall >= self.every_s:
            if 'first' not in r:
                r.append('periodic')
        return r

    def before_decision(self, st, goal=None, target=None, mem=None, tried=None, n=None):
        """None, or a Look (fresh, or the last one reused while it is young and Link has not moved far). Never raises."""
        try:
            return self._before(st, goal, target, mem, tried or [], n)
        except Exception as e:   # noqa: BLE001  the eyes must not end a run
            self._row({'seq': self.seq, 'n': n, 'error': f'internal: {type(e).__name__}: {e}'})
            return None

    def _before(self, st, goal, target, mem, tried, n):
        now = self.clock()
        why = [] if self.off_reason or self.seq >= self.max_looks else self.reasons(st, goal, target, mem, tried, now)
        spaced = self.last_wall is None or now - self.last_wall >= self.min_gap_s
        if why and (spaced or why == ['first']):
            look = self.look(st, why, n, now, target)
            self.last_state = st
            if look:
                return look
        else:
            self.last_state = st
        if self.last and now - self.last[0] <= self.hint_ttl_s and st.get('pos') and self.last[1] and \
                flat_dist(st['pos'], self.last[1]) <= 4.0 and self.last[2].hint:
            old = self.last[2]
            hint = dict(old.hint, age_s=round(now - self.last[0], 1))
            return Look(hint, self.extra_candidates(hint, st), fresh=False, row=old.row)
        return None

    # -- one look

    def look(self, st, why, n=None, now=None, target=None):
        """Capture, ask, record. The Look, or None when the capture or the request failed (a row says why)."""
        now = self.clock() if now is None else now
        why = [why] if isinstance(why, str) else list(why)
        self.seq += 1
        row = {'seq': self.seq, 'n': n, 'why': why, 'wall': round(time.time(), 2), 't': st.get('t'), 'backend': self.backend,
               'model': self.model}
        self.last_wall = now
        for w in why:
            self.tally['by_reason'][w] = self.tally['by_reason'].get(w, 0) + 1
        if 'stuck' in why:
            self.last_stuck_wall, self.last_stuck_pos = now, st.get('pos')
        if 'text-box' in why:
            self.last_text_wall = now
        if 'body' in why or 'body-snap' in why:
            self.last_body_wall = now
        if st.get('area'):
            self.last_area = st['area']
        t0 = time.perf_counter()
        try:
            path, w, h, mime, how = self.capture()
        except BridgeError as e:
            return self._fail(row, f'capture: {e}', soft=True)
        row.update({'frame': f'vision/{Path(path).name}', 'w': w, 'h': h, 'capture': how,
                    'capture_ms': round((time.perf_counter() - t0) * 1000, 1)})
        data_url = f'data:{mime};base64,' + base64.b64encode(Path(path).read_bytes()).decode('ascii')
        reason = why[0]
        try:
            ans, ms, crow = self._ask(data_url, reason, w, h)
        except openai_api.CapReached as e:
            self.off_reason = f'cap: {e}'
            return self._fail(row, f'cap: {e}')
        except openai_api.NoKey as e:
            self.off_reason = f'no key: {e}'
            return self._fail(row, f'no key: {e}')
        except (openai_api.ApiError, ValueError) as e:
            self.errors += 1
            if self.errors >= 3:
                self.off_reason = f'three failed looks in a row: {e}'[:300]
            return self._fail(row, f'{type(e).__name__}: {e}'[:400])
        self.errors = 0
        row.update({'latency_ms': round(ms, 1), 'usage': crow.get('usage'), 'cost_usd': crow.get('cost_usd')})
        self.latencies.append(ms)
        self.tally['cost_usd'] += float(crow.get('cost_usd') or 0)
        self.tally['looks'] += 1
        raw_p = dict(ans['p'])
        if not (target is not None and getattr(target, 'follow', None)):   # no other player in play: a second body is a villager, a fairy, a statue
            ans = dict(ans, p={k: v for k, v in ans['p'].items() if k not in ('other_body', 'other_body_ok')})
        hint = self.make_hint(ans)
        extra = self.extra_candidates(hint, st)
        odd = self.oddities(ans, st, why, target)
        row.update({'answers': {'front': ans['front'], 'screen': ans['screen'], 'p': raw_p, 'says': ans['says']}, 'hint': hint,
                    'extra': [e[0] for e in extra], 'oddities': [o['kind'] for o in odd]})
        for e in extra:
            self.tally['extra_offered'][e[0]] = self.tally['extra_offered'].get(e[0], 0) + 1
        for o in odd:
            self.tally['oddities'][o['kind']] = self.tally['oddities'].get(o['kind'], 0) + 1
            self.odd.write(json.dumps({'seq': self.seq, 'n': n, 'wall': row['wall'], 't': st.get('t'), 'area': st.get('area'),
                                       'pos': st.get('pos'), 'frame': row['frame'], **o}) + '\n')
        self.odd.flush()
        self._row(row)
        look = Look(hint, extra, True, row)
        self.last = (now, st.get('pos'), look)
        return look

    def _ask(self, data_url, reason, w, h):
        if self.backend == 'decisions':
            body = decisions_body(self.model, data_url, reason)
            est = (len(json.dumps({k: v for k, v in body.items() if k != 'input'})) / 3.0 + len(DEVELOPER) / 3.0 +
                   image_tokens(w, h)) * 0.10 / 1e6
            ans, ms, crow = self.client.post('/decisions', body, api='decisions', model=self.model, kind='vision',
                                             estimate=est, timeout=self.timeout)
            return parse_decisions(ans), ms, crow
        body = responses_body(self.model, data_url, reason)
        price = openai_api.PRICES.get(('responses', self.model), openai_api.Price(inp=10.0, cached=0.0, write=0.0, out=50.0))
        est = (len(json.dumps({k: v for k, v in body.items() if k != 'input'})) / 3.0 + image_tokens(w, h)) * price.inp / 1e6 \
            + 600 * price.out / 1e6
        ans, ms, crow = self.client.post('/responses', body, api='responses', model=self.model, kind='vision', estimate=est,
                                         timeout=max(self.timeout, 120.0))
        return parse_responses(ans), ms, crow

    def _fail(self, row, error, soft=False):
        row['error'] = error
        self.tally['errors'] += 1
        self._row(row)
        return None

    def _row(self, row):
        self.rows.write(json.dumps(row) + '\n')
        self.rows.flush()

    # -- what a look means

    @staticmethod
    def make_hint(ans):
        p = {k: round(v, 2) for k, v in ans['p'].items() if v is not None and (v >= 0.1 or k in ('stuck', 'text_box'))}
        hint = {'front': ans['front'], 'screen': ans['screen'], 'p': p, 'age_s': 0.0}
        if ans.get('says'):
            hint['says'] = ans['says']
        return hint

    @staticmethod
    def extra_candidates(hint, st):
        """[(label, hsap step lines, text)] the picture makes worth offering. Never offered for a duel (the pilot does not ask)."""
        p, out = hint.get('p') or {}, []
        screen, front = hint.get('screen'), hint.get('front')
        event = st.get('event') == 1
        if (p.get('enemy', 0) >= HI or front == 'enemy') and screen in (None, 'play'):
            out.append(('vision-fight', ['raw 0:ZL/1500,0.30:Y/100,0.75:Y/100,1.20:Y/100 1.8', 'wait 0.5'],
                        'the picture shows an enemy: lock on (hold ZL) and slash three times (Y)'))
        if (p.get('text_box', 0) >= HI or screen == 'text_box') and not event:
            out.append(('vision-talk', ['until control timeout 60 press A every 1.5'],
                        'the picture shows a text box the game did not report as an event: A every 1.5 s until Link is free, at most 60 s'))
        if screen in ('cutscene', 'loading') and not st.get('scene') and not st.get('loading'):
            out.append(('vision-wait-scene', ['wait 3'], f'the picture shows a {screen} screen: wait 3 s without input'))
        if screen == 'menu':
            out.append(('vision-close-menu', ['press B 150', 'wait 1'], 'the picture shows a menu: press B to close it'))
        pos, yaw = st.get('pos'), st.get('camera')
        if yaw is None:
            yaw = st.get('facing')
        blocked = (p.get('stuck', 0) >= HI) or front in ('wall_or_obstacle', 'water', 'drop_or_hole')
        if blocked and pos and yaw is not None:
            for side, turn, key in (('left', 90.0, 'clear_left'), ('right', -90.0, 'clear_right')):
                if p.get(key, 0) >= HI:
                    a = math.radians(yaw + turn)
                    x, z = pos[0] + 4.0 * math.sin(a), pos[2] + 4.0 * math.cos(a)
                    out.append((f'vision-side-{side}', [f'walk {x:.2f} {z:.2f} radius 0.6 timeout 6'],
                                f'the picture shows the way blocked ahead and the ground clear to Link\'s {side}: step 4 m {side}'))
        return out

    def oddities(self, ans, st, why, target):
        p, out = ans['p'], []
        screen, event = ans.get('screen'), st.get('event') == 1
        playing = not st.get('scene') and not st.get('loading')
        if ((p.get('text_box') or 0) >= ODD or screen == 'text_box') and not event and st.get('prompt') in (None, '', 'Empty'):
            out.append({'kind': 'text-box-no-event', 'detail': 'a text box is in the picture, the tap reports no event'})
        if screen in ('menu', 'title', 'game_over', 'other') and playing:
            out.append({'kind': 'screen-not-play', 'detail': f'the picture is a {screen} screen while the state says play'})
        if screen in ('cutscene', 'loading') and playing and event is False:
            out.append({'kind': f'{screen}-without-state', 'detail': f'the picture is a {screen} screen, the state reports neither a scene nor loading'})
        if (p.get('stuck') or 0) >= ODD:
            out.append({'kind': 'stuck-visible', 'detail': f"Link is against something solid (front: {ans.get('front')})"})
        if (p.get('other_body') or 0) >= 0.5 and p.get('other_body_ok') is not None and p['other_body_ok'] <= 0.4:
            out.append({'kind': 'other-body-wrong', 'detail': 'a second player body is visible and does not look right',
                        'says': ans.get('says')})
        if 'body-snap' in why:
            out.append({'kind': 'other-body-snap', 'detail': 'the other player\'s place jumped farther than anyone runs between two decisions',
                        'says': ans.get('says')})
        if 'body' in why and (p.get('other_body') or 0) <= 0.15:
            out.append({'kind': 'other-body-missing', 'detail': 'the other player is within 14 m on this map and no second body is in the picture (it may be behind the camera)', 'weak': True})
        if 'snap' in why:
            out.append({'kind': 'snap', 'detail': 'Link\'s place jumped more than his steps explain'})
        if 'map' in why and self.area and st.get('area') != self.area:
            out.append({'kind': 'unexpected-map', 'detail': f"the map is not the segment's ({st.get('area')} instead of {self.area})"})
        return out

    # -- the end

    def summary(self):
        lat = sorted(self.latencies)
        out = dict(self.tally, backend=self.backend, model=self.model, off_reason=self.off_reason,
                   latency_ms_median=openai_api.percentile(lat, 50), latency_ms_p95=openai_api.percentile(lat, 95))
        out['cost_usd'] = round(out['cost_usd'], 6)
        return out

    def close(self):
        try:
            (self.dir / 'summary.json').write_text(json.dumps(self.summary(), indent=1))
        finally:
            self.rows.close()
            self.odd.close()


def flat_dist(a, b):
    return math.hypot(a[0] - b[0], a[2] - b[2])


def make(args, *, client, run_dir, run_id, copy=None, segment=None, clock=time.time, capture=None):
    """The pilot's eyes for a run, or None. pilot.py's args may carry vision (off|on), vision_every, vision_model,
    vision_backend, vision_sock, vision_max, vision_width; PILOT_VISION=on turns it on too. Prints why it stays off."""
    mode = str(getattr(args, 'vision', None) or os.environ.get('PILOT_VISION') or 'off').lower()
    if mode not in ('on', '1', 'yes', 'true'):
        return None
    if client.real and openai_api.key_state() not in ('file', 'env'):
        print(f'vision: {openai_api.key_state()}; the run goes without eyes', flush=True)
        return None
    vdir = Path(run_dir) / 'vision'
    cap = capture or Capture(vdir, width=int(getattr(args, 'vision_width', None) or 960), sock=getattr(args, 'vision_sock', None),
                             copy=copy, run_id=run_id)
    try:
        eyes = Vision(client, run_dir, cap, backend=getattr(args, 'vision_backend', None), model=getattr(args, 'vision_model', None),
                      every_s=float(getattr(args, 'vision_every', None) or 60.0),
                      max_looks=int(getattr(args, 'vision_max', None) or 200), area=getattr(segment, 'area', None), clock=clock)
    except ValueError as e:
        print(f'vision: {e}; the run goes without eyes', flush=True)
        return None
    print(f'vision: on ({eyes.backend}, {eyes.model}, a look every {eyes.every_s:g} s and at oddities)', flush=True)
    return eyes


# ---- command line: probe and look

def test_picture(color, side, w=640, h=360):
    """A made-up picture: a grey field, a big square of `color` in the middle, a small white block on the `side`."""
    rgb = bytearray([90, 90, 90] * (w * h))
    def fill(x0, y0, x1, y1, c):
        for y in range(y0, y1):
            rgb[(y * w + x0) * 3:(y * w + x1) * 3] = bytes(c) * (x1 - x0)
    fill(w // 2 - 80, h // 2 - 80, w // 2 + 80, h // 2 + 80, color)
    bx = 40 if side == 'left' else w - 80
    fill(bx, 40, bx + 40, 80, (255, 255, 255))
    return write_png(w, h, bytes(rgb))


COLORS = {'red': (220, 30, 30), 'green': (30, 180, 60), 'blue': (40, 70, 230), 'yellow': (240, 220, 40)}


def probe_one(client, backend, model):
    """Ask one model about a made-up picture. Returns a row: status, right (it read the picture), latency, tokens, cost."""
    color, side = random.choice(list(COLORS)), random.choice(['left', 'right'])
    png = test_picture(COLORS[color], side)
    url = 'data:image/png;base64,' + base64.b64encode(png).decode('ascii')
    qs = [{'type': 'choice', 'name': 'square_color', 'instructions': 'What colour is the big square in the middle?',
           'choices': [{'value': c} for c in COLORS]},
          {'type': 'choice', 'name': 'white_block_side', 'instructions': 'On which side of the picture is the small white block?',
           'choices': [{'value': 'left'}, {'value': 'right'}]}]
    row = {'backend': backend, 'model': model, 'expected': {'square_color': color, 'white_block_side': side}}
    try:
        if backend == 'decisions':
            body = {'model': model, 'input': [{'role': 'user', 'content': [
                {'type': 'input_text', 'text': 'A made-up test picture.'}, {'type': 'input_image', 'image_url': url}]}], 'questions': qs}
            ans, ms, crow = client.post('/decisions', body, api='decisions', model=model, kind='vision', estimate=0.001, timeout=60)
            got = {a.get('name'): a.get('choice') for a in ans.get('answers', [])}
        else:
            schema = {'type': 'object', 'additionalProperties': False, 'required': ['square_color', 'white_block_side'],
                      'properties': {'square_color': {'type': 'string', 'enum': list(COLORS)},
                                     'white_block_side': {'type': 'string', 'enum': ['left', 'right']}}}
            body = {'model': model, 'input': [{'role': 'user', 'content': [
                {'type': 'input_text', 'text': 'A made-up test picture. What colour is the big square in the middle, and on which '
                                               'side of the picture is the small white block?'},
                {'type': 'input_image', 'image_url': url, 'detail': 'auto'}]}],
                'text': {'format': {'type': 'json_schema', 'name': 'probe', 'schema': schema, 'strict': True}},
                'max_output_tokens': 2000}
            ans, ms, crow = client.post('/responses', body, api='responses', model=model, kind='vision', estimate=0.01, timeout=120)
            text = ''.join(part.get('text', '') for it in ans.get('output', []) if it.get('type') == 'message'
                           for part in it.get('content', []) if part.get('type') == 'output_text')
            got = json.loads(text)
        row.update({'status': 200, 'got': got, 'right': got == row['expected'], 'latency_ms': round(ms, 1),
                    'usage': crow.get('usage'), 'cost_usd': crow.get('cost_usd')})
    except (openai_api.ApiError, openai_api.CapReached, openai_api.NoKey, ValueError) as e:
        row.update({'status': 'error', 'error': f'{type(e).__name__}: {e}'[:300], 'right': False})
    return row


def cmd_probe(args):
    client = openai_api.Client('vision-probe', 'probe', args.api_base)
    models = [m for m in (args.models or '').split(',') if m] or ['gpt-6-luna', 'gpt-6.1-terra', 'gpt-6.1-sol', 'gpt-6-sol', 'gpt-6-astra']
    rows = []
    for backend in [b for b in args.backends.split(',') if b]:
        for model in models:
            if backend == 'decisions' and model != openai_api.DECISION_MODEL:
                continue   # /v1/decisions takes gpt-6-luna only
            for _ in range(args.repeat):
                rows.append(probe_one(client, backend, model))
    print(f"{'backend':10s} {'model':15s} {'status':>6s} {'read it':>8s} {'ms':>7s} {'in tok':>7s} {'USD':>10s}")
    for r in rows:
        u = r.get('usage') or {}
        print(f"{r['backend']:10s} {r['model']:15s} {str(r['status']):>6s} {str(r['right']):>8s} {r.get('latency_ms', ''):>7} "
              f"{u.get('input_tokens', ''):>7} {r.get('cost_usd') if r.get('cost_usd') is not None else '':>10}")
        if r.get('error'):
            print('   ', r['error'])
    if args.out:
        Path(args.out).write_text(json.dumps(rows, indent=1))
    return 0


def cmd_look(args):
    client = openai_api.Client('vision-look', 'look', args.api_base)
    src = Path(args.picture)
    with tempfile.TemporaryDirectory(prefix='vision-look-') as t:
        if src.suffix.lower() == '.png':
            path, w, h, mime = downscale_file(src, Path(t) / 'f', args.width)
        else:
            path, w, h, mime = src, 0, 0, 'image/jpeg'
        url = f'data:{mime};base64,' + base64.b64encode(Path(path).read_bytes()).decode('ascii')
        v = Vision.__new__(Vision)
        v.client, v.backend, v.model, v.timeout = client, args.backend or openai_api.caps()['vision_backend'], \
            args.model or openai_api.caps()['vision_model'], 90.0
        ans, ms, crow = v._ask(url, 'forced', w or 960, h or 540)
    print(json.dumps({'answers': ans, 'hint': Vision.make_hint(ans), 'latency_ms': round(ms, 1), 'cost_usd': crow.get('cost_usd')}, indent=1))
    return 0


def ask_picture(client, backend, model, path, reason='forced', width=960):
    """The normalized look of one picture file by one backend and model: (answers, latency ms, cost USD)."""
    path = Path(path)
    with tempfile.TemporaryDirectory(prefix='vision-ask-') as t:
        if path.suffix.lower() == '.png':
            path, w, h, mime = downscale_file(path, Path(t) / 'f', width)
        else:
            w, h, mime = 960, 540, 'image/jpeg' if path.suffix.lower() in ('.jpg', '.jpeg') else 'image/png'
        url = f'data:{mime};base64,' + base64.b64encode(path.read_bytes()).decode('ascii')
        v = Vision.__new__(Vision)
        v.client, v.backend, v.model, v.timeout = client, backend, model, 120.0
        ans, ms, crow = v._ask(url, reason, w, h)
    return ans, ms, crow.get('cost_usd')


def compare(client, arms, pictures, ask=ask_picture):
    """Ask every picture of every (backend, model) in arms; returns {'rows': [...], 'summary': {...}}: per arm its cost and latency, and
    against the first arm: how often the front and screen choices agree, the mean absolute difference of each probability, and how
    often the two sides of 0.5 differ (a yes against a no)."""
    rows = []
    for pic in pictures:
        row = {'picture': str(pic), 'arms': {}}
        for backend, model in arms:
            try:
                ans, ms, cost = ask(client, backend, model, pic)
                row['arms'][f'{backend}:{model}'] = {'answers': {k: ans[k] for k in ('front', 'screen', 'p', 'says')}, 'latency_ms': round(ms, 1),
                                                     'cost_usd': cost}
            except (openai_api.ApiError, openai_api.CapReached, openai_api.NoKey, ValueError) as e:
                row['arms'][f'{backend}:{model}'] = {'error': f'{type(e).__name__}: {e}'[:200]}
        rows.append(row)
    names = [f'{b}:{m}' for b, m in arms]
    summary = {}
    for name in names:
        got = [r['arms'][name] for r in rows if 'answers' in r['arms'].get(name, {})]
        lat = sorted(g['latency_ms'] for g in got)
        s = {'pictures': len(got), 'cost_usd': round(sum(float(g.get('cost_usd') or 0) for g in got), 6),
             'cost_usd_per_picture': round(sum(float(g.get('cost_usd') or 0) for g in got) / len(got), 6) if got else None,
             'latency_ms_median': openai_api.percentile(lat, 50)}
        if name != names[0]:
            pairs = [(r['arms'][names[0]]['answers'], r['arms'][name]['answers']) for r in rows
                     if 'answers' in r['arms'].get(names[0], {}) and 'answers' in r['arms'].get(name, {})]
            diffs = {q: [abs(a['p'][q] - b['p'][q]) for a, b in pairs if a['p'].get(q) is not None and b['p'].get(q) is not None] for q, _ in PREDICATES}
            flips = {q: sum((a['p'][q] >= 0.5) != (b['p'][q] >= 0.5) for a, b in pairs if a['p'].get(q) is not None and b['p'].get(q) is not None)
                     for q, _ in PREDICATES}
            s['against_first'] = {'pairs': len(pairs), 'front_agree': sum(a['front'] == b['front'] for a, b in pairs),
                                  'screen_agree': sum(a['screen'] == b['screen'] for a, b in pairs),
                                  'mean_abs_diff': {q: round(sum(d) / len(d), 3) for q, d in diffs.items() if d}, 'yes_no_flips': flips}
        summary[name] = s
    return {'rows': rows, 'summary': summary}


def cmd_compare(args):
    client = openai_api.Client('vision-compare', 'compare', args.api_base)
    arms = [tuple(a.split(':', 1)) for a in args.arms.split(',') if a]
    pics = []
    for p in args.pictures:
        p = Path(p)
        pics += sorted(list(p.glob('*.jpg')) + list(p.glob('*.png'))) if p.is_dir() else [p]
    out = compare(client, arms, pics[:args.limit])
    print(json.dumps(out['summary'], indent=1))
    if args.out:
        Path(args.out).write_text(json.dumps(out, indent=1))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('probe')
    p.add_argument('--models')
    p.add_argument('--backends', default='decisions,responses')
    p.add_argument('--repeat', type=int, default=1)
    p.add_argument('--api-base')
    p.add_argument('--out')
    lk = sub.add_parser('look')
    lk.add_argument('picture')
    lk.add_argument('--backend', choices=['decisions', 'responses'])
    lk.add_argument('--model')
    lk.add_argument('--width', type=int, default=960)
    lk.add_argument('--api-base')
    cp = sub.add_parser('compare')
    cp.add_argument('pictures', nargs='+', help='picture files or folders of them')
    cp.add_argument('--arms', default='decisions:gpt-6-luna,responses:gpt-6-astra', help='backend:model, comma separated; the first is the reference')
    cp.add_argument('--limit', type=int, default=40)
    cp.add_argument('--api-base')
    cp.add_argument('--out')
    a = ap.parse_args()
    return {'probe': cmd_probe, 'look': cmd_look, 'compare': cmd_compare}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
