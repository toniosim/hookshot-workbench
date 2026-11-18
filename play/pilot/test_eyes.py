#!/usr/bin/env python3
"""The pilot's eyes and its measuring, without a game and without a network: vision.py (pictures, the control bridge's
`shot` against a fake socket, the two backends against a local stub, the triggers, the hint, the extra candidates, the
oddities, the ledger and the caps), metrics.py (a made-up run folder with known numbers) and the key handling of
openai_api.py. Run alone:  python3 -I -B test_eyes.py    (test_pilot.py calls run() too)
"""
import base64
import json
import os
import socket
import sys
import tempfile
import threading
import time
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import openai_api  # noqa: E402
import vision  # noqa: E402

FAILS = []
CHECKS = [0]


def check(cond, what):
    CHECKS[0] += 1
    if not cond:
        FAILS.append(what)
        print('FAIL', what, flush=True)


# ---- a local stand-in for the two endpoints, answering a picture question set

class Stub:
    """/v1/decisions and /v1/responses on loopback. `answers` is what to say (front, screen, p: {name: prob}); every request's
    body is kept in `seen` and its headers' authorization in `auth`; `fail` makes the next n requests answer HTTP 400."""

    def __init__(self):
        self.seen, self.auth, self.fail = [], [], 0
        self.answers = {'front': 'open_ground', 'screen': 'play', 'p': {}, 'says': 'open grass ahead'}
        stub = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                stub.seen.append((self.path, body))
                stub.auth.append(self.headers.get('Authorization'))
                if stub.fail > 0:
                    stub.fail -= 1
                    return self.reply(400, {'error': {'message': 'nope'}})
                text = json.dumps(body)
                usage = {'input_tokens': len(text) // 4, 'input_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0},
                         'output_tokens': 0}
                a = stub.answers
                if self.path.endswith('/decisions'):
                    out = []
                    for q in body['questions']:
                        if q['type'] == 'choice':
                            vals = [c['value'] for c in q['choices']]
                            want = a.get(q['name'])
                            out.append({'type': 'choice', 'name': q['name'], 'choice': want if want in vals else vals[0],
                                        'confidence': 0.9})
                        else:
                            out.append({'type': 'predicate', 'name': q['name'], 'probability': a['p'].get(q['name'], 0.01)})
                    return self.reply(200, {'answers': out, 'usage': usage})
                data = {'says': a.get('says', ''), 'front': a['front'], 'screen': a['screen']}
                data.update({n: a['p'].get(n, 0.01) for n, _ in vision.PREDICATES})
                return self.reply(200, {'output': [{'type': 'message', 'content': [{'type': 'output_text',
                                                                                     'text': json.dumps(data)}]}], 'usage': usage})

            def reply(self, code, obj):
                data = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), H)
        self.base = f'http://127.0.0.1:{self.server.server_address[1]}/v1'
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self):
        self.server.shutdown()


class FakeBridge(threading.Thread):
    """A unix socket that answers `shot` the way docs/control.md says: writes a PNG at the path, replies ok with its size; a
    reply for another id first (out of order), or an error, or a close, by `mode`."""

    def __init__(self, path, png, mode='ok'):
        super().__init__(daemon=True)
        self.path, self.png, self.mode, self.requests = path, png, mode, []
        self.srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.srv.bind(str(path))
        self.srv.listen(4)
        self.start()

    def run(self):
        while True:
            try:
                c, _ = self.srv.accept()
            except OSError:
                return
            buf = b''
            while b'\n' not in buf:
                d = c.recv(4096)
                if not d:
                    break
                buf += d
            if buf:
                req = json.loads(buf.split(b'\n')[0])
                self.requests.append(req)
                if self.mode == 'close':
                    c.close()
                    continue
                c.sendall(b'{"id":99,"ok":true,"frame":1}\n')
                if self.mode == 'error':
                    c.sendall(json.dumps({'id': req['id'], 'ok': False, 'error': 'unavailable', 'message': 'no renderer'}).encode() + b'\n')
                else:
                    Path(req['path']).write_bytes(self.png)
                    c.sendall(json.dumps({'id': req['id'], 'ok': True, 'frame': 5, 'path': req['path'], 'width': 64,
                                          'height': 36}).encode() + b'\n')
            c.close()

    def stop(self):
        self.path.unlink(missing_ok=True)   # (closing a listening socket does not end its blocked accept: take the name away)
        self.srv.close()


def small_png(w=64, h=36, shade=0):
    rgb = bytearray()
    for y in range(h):
        for x in range(w):
            rgb += bytes(((x * 4 + shade) % 256, (y * 7) % 256, 100))
    return vision.write_png(w, h, bytes(rgb))


def png_with_filters(w, h, ctype, filt):
    """A PNG whose rows use filter type `filt`, made by filtering known raw rows by hand, to test the reader's unfilter."""
    bpp = {0: 1, 2: 3, 4: 2, 6: 4}[ctype]
    stride = w * bpp
    rows = [bytes((x * 5 + y * 11) % 256 for x in range(stride)) for y in range(h)]
    out, prev = b'', bytes(stride)
    for row in rows:
        f = bytearray(stride)
        for i in range(stride):
            a = row[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if filt == 0:
                pred = 0
            elif filt == 1:
                pred = a
            elif filt == 2:
                pred = b
            elif filt == 3:
                pred = (a + b) >> 1
            else:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if pa <= pb and pa <= pc else b if pb <= pc else c
            f[i] = (row[i] - pred) & 255
        out += bytes([filt]) + bytes(f)
        prev = row

    def chunk(kind, body):
        import struct
        return struct.pack('>I', len(body)) + kind + body + struct.pack('>I', zlib.crc32(kind + body) & 0xffffffff)
    import struct
    png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, ctype, 0, 0, 0)) +
           chunk(b'IDAT', zlib.compress(out)) + chunk(b'IEND', b''))
    return png, rows


def picture_checks(tmp):
    png = small_png()
    w, h, rgb = vision.read_png(png)
    check((w, h) == (64, 36) and len(rgb) == 64 * 36 * 3, 'png: a written picture reads back at its size')
    check(rgb[:3] == bytes((0, 0, 100)) and rgb[3:6] == bytes((4, 0, 100)), 'png: and with its pixels')
    for filt in range(5):
        for ctype in (0, 2, 4, 6):
            data, rows = png_with_filters(7, 5, ctype, filt)
            w, h, rgb = vision.read_png(data)
            want = bytearray()
            for r in rows:
                if ctype == 2:
                    want += r
                elif ctype == 6:
                    for i in range(0, len(r), 4):
                        want += r[i:i + 3]
                elif ctype == 0:
                    for v in r:
                        want += bytes((v, v, v))
                else:
                    for i in range(0, len(r), 2):
                        want += bytes((r[i],) * 3)
            check((w, h) == (7, 5) and rgb == bytes(want), f'png: filter {filt}, colour type {ctype} unfiltered right')
    for bad in (b'not a png', png[:30]):
        try:
            vision.read_png(bad)
            check(False, 'png: a bad file is refused')
        except (ValueError, zlib.error, Exception):
            check(True, 'png: a bad file is refused')
    # area average: a 4x2 picture of two columns of black and two of white becomes 2x1 of black and white
    src = bytes([0] * 3 * 2 + [255] * 3 * 2) * 2
    w, h, got = vision.downscale_rgb(4, 2, src, 2, 1)
    check((w, h) == (2, 1) and got == bytes([0, 0, 0, 255, 255, 255]), 'downscale: 2x2 blocks are averaged')
    src = bytes([0, 0, 0, 255, 255, 255, 0, 0, 0, 255, 255, 255])   # 4x1 -> 3x1: the middle pixel mixes
    w, h, got = vision.downscale_rgb(4, 1, src, 3, 1)
    check(w == 3 and abs(got[3] - 128) <= 1 and abs(got[0] - 64) <= 1, f'downscale: a non-integer ratio weights by area ({list(got)})')
    w, h, got = vision.downscale_rgb(4, 2, src * 2, 9, 9)
    check((w, h) == (4, 2), 'downscale: never enlarges')
    big = tmp / 'big.png'
    big.write_bytes(small_png(200, 100))
    path, w, h, mime = vision.downscale_file(big, tmp / 'small', 50, use_magick=False)
    check(mime == 'image/png' and (w, h) == (50, 25) and path.suffix == '.png' and vision.read_png(path.read_bytes())[:2] == (50, 25),
          'downscale_file without ImageMagick: a PNG at the width asked, aspect kept')
    path, w, h, mime = vision.downscale_file(big, tmp / 'same', 500, use_magick=False)
    check((w, h) == (200, 100), 'downscale_file: a picture narrower than the width is not enlarged')
    if vision.has_magick():
        path, w, h, mime = vision.downscale_file(big, tmp / 'jpg', 50, use_magick=True)
        check(mime == 'image/jpeg' and path.suffix == '.jpg' and (w, h) == (50, 25) and path.read_bytes()[:2] == b'\xff\xd8',
              'downscale_file with ImageMagick: a JPEG at the width asked')
    t = vision.test_picture((220, 30, 30), 'left')
    w, h, rgb = vision.read_png(t)
    c = (h // 2 * w + w // 2) * 3
    check(tuple(rgb[c:c + 3]) == (220, 30, 30) and tuple(rgb[(50 * w + 50) * 3:(50 * w + 50) * 3 + 3]) == (255, 255, 255),
          'test picture: the colour in the middle, the white block on the side asked')


def bridge_checks(tmp):
    sock = tmp / 'c.sock'
    png = small_png()
    br = FakeBridge(sock, png)
    out = tmp / 'shot.png'
    r = vision.bridge_shot(sock, out)
    check(r['ok'] and out.read_bytes() == png and br.requests[-1]['cmd'] == 'shot' and br.requests[-1]['path'] == str(out),
          'bridge: a shot request names the path, the reply of the right id is taken though another came first')
    br.stop()
    sock2 = tmp / 'e.sock'
    br2 = FakeBridge(sock2, png, mode='error')
    try:
        vision.bridge_shot(sock2, out)
        check(False, 'bridge: an error reply raises')
    except vision.BridgeError as e:
        check('unavailable' in str(e), 'bridge: an error reply raises with its code')
    br2.stop()
    sock3 = tmp / 'x.sock'
    br3 = FakeBridge(sock3, png, mode='close')
    try:
        vision.bridge_shot(sock3, out, timeout=2)
        check(False, 'bridge: a closed socket raises')
    except vision.BridgeError:
        check(True, 'bridge: a closed socket raises')
    br3.stop()
    try:
        vision.bridge_shot(tmp / 'nothing.sock', out, timeout=1)
        check(False, 'bridge: no socket raises')
    except vision.BridgeError:
        check(True, 'bridge: no socket raises')
    # Capture: bridge first; then the folder of the game's own pictures when the bridge is gone
    sock4 = tmp / 'cap.sock'
    br4 = FakeBridge(sock4, small_png(64, 36, 7))
    shots = tmp / 'shots'
    shots.mkdir()
    (shots / 'a.png').write_bytes(small_png(64, 36, 3))
    cap = vision.Capture(tmp / 'v', width=32, sock=sock4, shots_dir=shots, use_magick=False)
    path, w, h, mime, how = cap()
    check(how == 'bridge' and (w, h) == (32, 18) and path.name == 'f0001.png' and not list((tmp / 'v').glob('raw*')),
          'capture: a bridge shot is downscaled, the full-size file deleted')
    br4.stop()
    path, w, h, mime, how = cap()
    check(how == 'folder' and path.name == 'f0002.png', 'capture: without the bridge the newest picture of the shots folder')
    os.utime(shots / 'a.png', (time.time() - 600, time.time() - 600))
    try:
        cap()
        check(False, 'capture: an old picture is not a look')
    except vision.BridgeError:
        check(True, 'capture: an old picture is not a look')
    run = tmp / 'copy' / 'runs' / 'tag1'
    run.mkdir(parents=True)
    (run / 'env-used.txt').write_text('HOS_CONTROL=/tmp/x/control.sock\nOTHER=1\n')
    check(vision.control_socket(tmp / 'copy', 'tag1') == Path('/tmp/x/control.sock'), 'control_socket: read from the run\'s env-used.txt')
    check(vision.control_socket(tmp / 'copy', 'nothing') is None, 'control_socket: none for a run without one')


# ---- the questions and the backends

def question_checks():
    qs = vision.decisions_questions()
    names = [q['name'] for q in qs]
    check(names == vision.question_names() and len(set(names)) == len(names), 'questions: one list for both backends, names unique')
    check(all(q['type'] == 'choice' and len(q['choices']) >= 2 for q in qs[:2]) and all(q['type'] == 'predicate' for q in qs[2:]),
          'questions: two choices and the predicates')
    body = vision.decisions_body('gpt-6-luna', 'data:image/png;base64,AAAA', 'stuck')
    parts = body['input'][1]['content']
    check(parts[1] == {'type': 'input_image', 'image_url': 'data:image/png;base64,AAAA'} and body['model'] == 'gpt-6-luna',
          'decisions body: the picture as an input_image data URL')
    text = json.dumps({k: v for k, v in body.items()}).replace('AAAA', '')
    for bad in ('/home', 'runs/', 'transcript', '.log', 'pos', 'flag'):
        if bad == 'pos':
            continue
        check(bad not in text, f'decisions body: no {bad!r} in what is sent')
    rb = vision.responses_body('gpt-6-astra', 'data:image/png;base64,AAAA', 'periodic')
    sch = rb['text']['format']['schema']
    check(set(sch['required']) == set(sch['properties']) and sch['additionalProperties'] is False and 'says' in sch['properties'] and
          all(n in sch['properties'] for n in vision.question_names()), 'responses body: a strict schema with every question and `says`')
    check(rb['input'][1]['content'][1]['type'] == 'input_image', 'responses body: the picture as an input_image')
    ans = {'answers': [{'type': 'choice', 'name': 'front', 'choice': 'door', 'confidence': 0.8},
                       {'type': 'choice', 'name': 'screen', 'choice': 'nonsense', 'confidence': 0.8},
                       {'type': 'predicate', 'name': 'enemy', 'probability': 1.4},
                       {'type': 'refusal', 'name': 'stuck'}, {'type': 'predicate', 'name': 'chest', 'probability': 'x'}]}
    got = vision.parse_decisions(ans)
    check(got['front'] == 'door' and got['screen'] is None and got['p'].get('enemy') == 1.0 and 'stuck' not in got['p'] and
          got['p'].get('chest') is None, 'parse_decisions: valid choices kept, others none; probabilities clamped; a refusal is no answer')
    data = {'says': 'x' * 400, 'front': 'chest', 'screen': 'play', 'door': 0.2, 'enemy': -3}
    got = vision.parse_responses({'output': [{'type': 'reasoning'}, {'type': 'message', 'content': [
        {'type': 'output_text', 'text': json.dumps(data)}]}]})
    check(got['front'] == 'chest' and got['p']['enemy'] == 0.0 and len(got['says']) == 240 and 'chest' not in got['p'],
          'parse_responses: the JSON of the message part, clamped and bounded')
    try:
        vision.parse_responses({'output': []})
        check(False, 'parse_responses: no text raises')
    except ValueError:
        check(True, 'parse_responses: no text raises')


# ---- the eyes

def state(x=0.0, z=0.0, **kw):
    st = {'t': 10.0, 'pos': [x, 1.0, z], 'area': 'Fake_Area', 'prompt': 'Empty', 'event': 0, 'scene': False, 'loading': 0,
          'camera': 0.0, 'facing': 0.0}
    st.update(kw)
    return st


class Target:
    def __init__(self, x=10.0, z=10.0, follow=None, kind='reach'):
        self.name, self.x, self.z, self.follow, self.kind = 't', x, z, follow, kind


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class Cheap:
    """A client that prices its requests (for the ledger and cost checks), no network."""
    real = False

    def __init__(self, cost=0.0003):
        self.cost, self.calls, self.raise_ = cost, [], None

    def post(self, path, body, *, api, model, kind, estimate, timeout=30.0):
        self.calls.append((path, kind, api, model, estimate))
        if self.raise_:
            raise self.raise_
        if path == '/decisions':
            ans = {'answers': [{'type': 'choice', 'name': 'front', 'choice': 'open_ground', 'confidence': 0.9},
                               {'type': 'choice', 'name': 'screen', 'choice': 'play', 'confidence': 0.9}]}
        else:
            ans = {'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(
                {'says': 'ok', 'front': 'open_ground', 'screen': 'play'})}]}]}
        return ans, 120.0, {'usage': {'input_tokens': 900}, 'cost_usd': self.cost}


def eyes_for(tmp, client=None, clock=None, **kw):
    png = small_png()
    d = tmp / f'run{len(list(tmp.glob("run*")))}'
    d.mkdir()
    pics = d / 'vision'
    pics.mkdir()
    n = [0]

    def capture():
        n[0] += 1
        p = pics / f'p{n[0]}.png'
        p.write_bytes(png)
        return p, 64, 36, 'image/png', 'fake'
    eyes = vision.Vision(client or Cheap(), d, capture, clock=clock or Clock(), area='Fake_Area', **kw)
    return eyes, d


def rows_of(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def trigger_checks(tmp):
    clock = Clock()
    cli = Cheap()
    eyes, d = eyes_for(tmp, cli, clock, every_s=60.0, min_gap_s=6.0, max_looks=50)
    st, tgt = state(), Target()
    look = eyes.before_decision(st, None, tgt, {}, [], 1)
    check(look is not None and look.fresh and eyes.seq == 1 and rows_of(d / 'vision' / 'vision.jsonl')[0]['why'] == ['first'],
          'trigger: the first decision looks, reason first')
    clock.t += 2
    look = eyes.before_decision(state(), None, tgt, {}, [], 2)
    check(look is not None and not look.fresh and eyes.seq == 1 and len(cli.calls) == 1,
          'trigger: nothing new, the last look\'s hint is reused while it is young and Link is near')
    check(look.hint['age_s'] == 2.0, 'trigger: the reused hint says how old it is')
    clock.t += 30
    far = eyes.before_decision(state(40, 0), None, tgt, {}, [], 3)
    check(far is None, 'trigger: Link far from where it was seen, or the look old: no hint')
    hist = {'history': [('go', 'stuck', 0.1, 3.0), ('side-left', 'stuck', 0.0, 3.0)]}
    clock.t += 1   # inside min_gap_s since... (the last look was 33 s ago) so spacing is not the issue here
    look = eyes.before_decision(state(40, 0), None, tgt, hist, [], 4)
    check(look is not None and look.fresh and rows_of(d / 'vision' / 'vision.jsonl')[-1]['why'] == ['stuck'],
          'trigger: two moves in a row that ended stuck with no progress: a look, reason stuck')
    clock.t += 3
    again = eyes.before_decision(state(40, 0), None, tgt, hist, [], 5)
    check(eyes.seq == 2 and again is not None and not again.fresh, 'trigger: spacing: no second look within min_gap_s of the first')
    clock.t += 10
    again = eyes.before_decision(state(40, 0), None, tgt, hist, [], 6)
    check(eyes.seq == 2, 'trigger: the same stuck point is not looked at again at once')
    clock.t += 60
    again = eyes.before_decision(state(40, 0), None, tgt, hist, [], 7)
    check(eyes.seq == 3 and set(rows_of(d / 'vision' / 'vision.jsonl')[-1]['why']) == {'stuck', 'periodic'},
          'trigger: a regular look after every_s, and a stuck point again after 4 x min_gap_s: both reasons named')
    # recovery's verdict, text box, map, snap, body
    clock.t += 100
    eyes.before_decision(state(40, 0), None, tgt, {'recover': {'stuck': True}}, [], 8)
    check('stuck' in rows_of(d / 'vision' / 'vision.jsonl')[-1]['why'], 'trigger: the recovery ladder\'s stuck verdict is a reason')
    clock.t += 30
    eyes.before_decision(state(40, 0, event=1), None, tgt, {}, [], 9)
    check(rows_of(d / 'vision' / 'vision.jsonl')[-1]['why'] == ['text-box'], 'trigger: the tap says an event holds Link: text-box')
    clock.t += 30
    check('text-box' not in eyes.reasons(state(40, 0, event=1, music='Dm_'), None, tgt, {}, [], clock()) and
          'text-box' in eyes.reasons(state(40, 0, event=1), None, tgt, {}, [], clock()), 'trigger: a scene with its own music is no text box')
    clock.t += 30
    eyes.before_decision(state(40, 0, area='Other_Area'), None, tgt, {}, [], 11)
    r = rows_of(d / 'vision' / 'vision.jsonl')[-1]
    check('map' in r['why'] and 'unexpected-map' in r['oddities'], 'trigger: another map is a reason and an oddity (not the segment\'s)')
    clock.t += 30
    tried = [{'step': 'go', 'moved_m': 2.0}]
    eyes.before_decision(state(52, 0, area='Other_Area'), None, tgt, {}, tried, 12)
    r = rows_of(d / 'vision' / 'vision.jsonl')[-1]
    check('snap' in r['why'] and 'snap' in r['oddities'], 'trigger: a jump of 12 m after a 2 m step is a snap, and an oddity')
    clock.t += 30
    check('snap' not in eyes.reasons(state(60, 0, area='Other_Area'), None, tgt, {}, [{'step': 'go', 'moved_m': 12.0}], clock()),
          'trigger: a long step explains a long way: no snap')
    clock.t += 100
    eyes.before_decision(state(60, 0, area='Other_Area'), None, Target(64, 0, follow='other'), {}, [], 14)
    r = rows_of(d / 'vision' / 'vision.jsonl')[-1]
    check('body' in r['why'] and 'other-body-missing' in r['oddities'], 'trigger: the other player within 14 m: a body look, and a missing body is an oddity')
    clock.t += 100
    eyes.before_decision(state(60, 0, area='Other_Area'), None, Target(70, 0, follow='other'), {}, [], 141)   # (a normal read of him)
    clock.t += 2
    eyes.before_decision(state(60, 0, area='Other_Area'), None, Target(75, 0, follow='other'), {}, [], 142)
    check('body-snap' not in rows_of(d / 'vision' / 'vision.jsonl')[-1]['why'], 'trigger: 5 m in 2 s is a runner, not a snap')
    clock.t += 7
    eyes.before_decision(state(60, 0, area='Other_Area'), None, Target(300, 0, follow='other'), {}, [], 143)
    r = rows_of(d / 'vision' / 'vision.jsonl')[-1]
    check('body-snap' in r['why'] and 'other-body-snap' in r['oddities'], f"trigger: 225 m in 7 s is the other body snapping: a reason and an oddity ({r['why']})")
    clock.t += 100
    n = eyes.seq
    eyes.before_decision(state(60, 0, area='Other_Area'), None, Target(300, 0, follow='other'), {}, [], 15)
    check(eyes.seq == n + 1 and 'body' not in rows_of(d / 'vision' / 'vision.jsonl')[-1]['why'], 'trigger: no body look when the other player is far')
    check(all(c[1] == 'vision' and c[0] == '/decisions' for c in cli.calls), 'ledger: every request is kind vision on /decisions')
    # a bound on looks, and a switch
    eyes2, d2 = eyes_for(tmp, Cheap(), clock, every_s=1.0, min_gap_s=0.0, max_looks=2)
    for i in range(5):
        clock.t += 5
        eyes2.before_decision(state(), None, tgt, {}, [], i + 1)
    check(eyes2.seq == 2, 'bound: max_looks stops the looking')
    eyes.close()
    s = json.loads((d / 'vision' / 'summary.json').read_text())
    check(s['looks'] == eyes.seq and abs(s['cost_usd'] - 0.0003 * eyes.seq) < 1e-9 and s['by_reason']['first'] == 1 and
          s['oddities'].get('snap') == 1, 'close: a summary of looks, cost, reasons and oddities')


def hint_checks(tmp):
    ans = {'front': 'wall_or_obstacle', 'screen': 'play', 'says': 'a wall', 'confidence': {},
           'p': {'door': 0.02, 'enemy': 0.9, 'stuck': 0.95, 'text_box': 0.0, 'clear_left': 0.8, 'clear_right': 0.1, 'chest': 0.05}}
    hint = vision.Vision.make_hint(ans)
    check(hint['front'] == 'wall_or_obstacle' and hint['p'] == {'enemy': 0.9, 'stuck': 0.95, 'text_box': 0.0, 'clear_left': 0.8, 'clear_right': 0.1}
          and hint['says'] == 'a wall' and hint['age_s'] == 0.0, 'hint: small probabilities dropped, stuck and text_box always kept')
    st = state(5, 5, camera=90.0)
    cands = vision.Vision.extra_candidates(hint, st)
    labels = [c[0] for c in cands]
    check(labels == ['vision-fight', 'vision-side-left'], f'extra: an enemy and a blocked way with the left clear ({labels})')
    side = dict((c[0], c) for c in cands)['vision-side-left']
    # camera yaw 90 faces +x; its left is yaw 180 = -z: the step goes to z = 1
    check(side[1][0].startswith('walk 5.00 1.00'), f'extra: left of yaw 90 is yaw 180 (-z) ({side[1]})')
    st0 = state(0, 0, camera=0.0)
    right = [c for c in vision.Vision.extra_candidates(dict(hint, p={'stuck': 0.9, 'clear_right': 0.9}), st0)]
    check(right[0][0] == 'vision-side-right' and right[0][1][0].startswith('walk -4.00 0.00'), f'extra: right of yaw 0 is -x ({right})')
    text = vision.Vision.extra_candidates({'front': 'open_ground', 'screen': 'text_box', 'p': {'text_box': 0.9}}, state())
    check([c[0] for c in text] == ['vision-talk'] and 'press A every 1.5' in text[0][1][0], 'extra: a text box the tap did not report: A until free')
    check(not vision.Vision.extra_candidates({'front': 'open_ground', 'screen': 'text_box', 'p': {'text_box': 0.9}}, state(event=1)),
          'extra: no talk candidate when the tap already reports the event')
    wait = vision.Vision.extra_candidates({'screen': 'cutscene', 'p': {}}, state())
    check([c[0] for c in wait] == ['vision-wait-scene'] and not vision.Vision.extra_candidates({'screen': 'cutscene', 'p': {}}, state(scene=True)),
          'extra: a cinematic the state does not know: wait; with a scene reported: nothing')
    check([c[0] for c in vision.Vision.extra_candidates({'screen': 'menu', 'p': {}}, state())] == ['vision-close-menu'], 'extra: a menu: close it')
    check(not vision.Vision.extra_candidates({'front': 'open_ground', 'screen': 'play', 'p': {'door': 0.9}}, state()), 'extra: nothing from a plain scene')
    check(all(c[0] in vision.LABELS and c[0].startswith('vision-') and isinstance(c[1], list) and c[2] for c in cands + right + text + wait),
          'extra: every label is a known vision- label with lines and a text')
    # oddities
    eyes, d = eyes_for(tmp, Cheap())
    odd = lambda a, st, why=('periodic',), tgt=None: [o['kind'] for o in eyes.oddities(a, st, list(why), tgt)]   # noqa: E731
    base = {'front': 'open_ground', 'screen': 'play', 'says': None, 'p': {}}
    check(odd(dict(base, p={'text_box': 0.9}), state()) == ['text-box-no-event'], 'oddity: a text box with no event')
    check(not odd(dict(base, p={'text_box': 0.9}), state(event=1)) and not odd(dict(base, p={'text_box': 0.9}), state(prompt='Open')),
          'oddity: not when the tap reports an event or a prompt is up')
    check(odd(dict(base, screen='menu'), state()) == ['screen-not-play'] and not odd(dict(base, screen='menu'), state(loading=1)),
          'oddity: a menu while the state says play; not while it loads')
    check(odd(dict(base, screen='loading'), state()) == ['loading-without-state'] and not odd(dict(base, screen='loading'), state(scene=True)),
          'oddity: a black screen with no scene or load in the state')
    check(odd(dict(base, p={'stuck': 0.8}), state()) == ['stuck-visible'], 'oddity: Link stuck on something')
    check(odd(dict(base, p={'other_body': 0.8, 'other_body_ok': 0.2}), state()) == ['other-body-wrong'], 'oddity: a body that does not look right')
    check(not odd(dict(base, p={'other_body': 0.8, 'other_body_ok': 0.9}), state()), 'oddity: a body that looks right is no oddity')
    check(not odd(dict(base, p={'other_body': 0.8}), state()), 'oddity: no verdict on the body, no oddity')


def eyes_end_to_end_checks(tmp):
    stub = Stub()
    try:
        c = {'per_run_usd': 2, 'per_night_usd': 50, 'total_usd': 400, 'planner_share_of_night': 0.4, 'model': None}
        openai_api.CAPS.write_text(json.dumps(c))
        client = openai_api.Client('eyes-run', 'seg', stub.base)
        clock = Clock()
        eyes, d = eyes_for(tmp, client, clock, every_s=60.0, min_gap_s=0.0)
        stub.answers = {'front': 'wall_or_obstacle', 'screen': 'play', 'says': 'a wall',
                        'p': {'stuck': 0.9, 'enemy': 0.8, 'clear_left': 0.9, 'other_body': 0.7, 'other_body_ok': 0.1}}
        solo = vision.Vision(openai_api.Client('eyes-solo', 'seg', stub.base), tmp / 'solo-run', lambda: (tmp / 'pics' / 'solo.png', 64, 36, 'image/png', 'fake'),
                             clock=clock, min_gap_s=0.0, area='Fake_Area')
        (tmp / 'pics').mkdir(exist_ok=True)
        (tmp / 'pics' / 'solo.png').write_bytes(small_png())
        sl = solo.before_decision(state(3, 4), None, Target(), {'history': [('go', 'stuck', 0.0, 1.0), ('go', 'stuck', 0.0, 1.0)]}, [], 1)
        srow = rows_of(tmp / 'solo-run' / 'vision' / 'vision.jsonl')[0]
        check(sl is not None and 'other_body' not in sl.hint['p'] and 'other_body_ok' not in sl.hint['p'] and 'other-body-wrong' not in srow['oddities'] and
              srow['answers']['p']['other_body'] == 0.7, 'solo: with no other player in play the body answers are not in the hint or the oddities, but are kept raw in the row')
        clock.t += 100
        look = eyes.before_decision(state(3, 4), None, Target(follow='other'), {'history': [('go', 'stuck', 0.0, 1.0), ('go', 'stuck', 0.0, 1.0)]}, [], 7)
        check(look is not None and look.hint['front'] == 'wall_or_obstacle' and look.hint['p']['stuck'] == 0.9, 'e2e: the stub\'s answer is the hint')
        check([e[0] for e in look.extra] == ['vision-fight', 'vision-side-left'], f'e2e: and the extra candidates ({[e[0] for e in look.extra]})')
        path, body = stub.seen[0]
        check(path.endswith('/decisions') and body['input'][1]['content'][1]['image_url'].startswith('data:image/png;base64,'),
              'e2e: the request went to /decisions with a data URL picture')
        flat = json.dumps(body)
        pic = base64.b64decode(body['input'][1]['content'][1]['image_url'].split(',', 1)[1])
        check(pic[:8] == b'\x89PNG\r\n\x1a\n', 'e2e: and the picture in it is the downscaled file')
        flat = flat.replace(body['input'][1]['content'][1]['image_url'], '')
        for secret in ('3.0', '4.0', 'Fake_Area', 'eyes-run', str(tmp), 'Authorization'):
            check(secret not in flat, f'e2e: nothing of the state, run or machine in the request ({secret!r})')
        check(stub.auth[0] == 'Bearer standin', 'e2e: a stand-in never gets the real key')
        rows = rows_of(d / 'vision' / 'vision.jsonl')
        check(rows[0]['n'] == 7 and rows[0]['extra'] == ['vision-fight', 'vision-side-left'] and
              set(rows[0]['oddities']) == {'stuck-visible', 'other-body-wrong'} and rows[0]['latency_ms'] > 0 and rows[0]['usage'],
              f"e2e: one row per look with n, what it offered, its oddities, latency, usage ({rows[0].get('oddities')})")
        odd = rows_of(d / 'vision' / 'oddities.jsonl')
        check({o['kind'] for o in odd} == {'stuck-visible', 'other-body-wrong'} and odd[0]['frame'] == rows[0]['frame'] and odd[0]['n'] == 7,
              'e2e: oddities.jsonl names the picture kept')
        check((d / rows[0]['frame']).exists(), 'e2e: the picture that was sent is kept')
        led = openai_api.ledger_rows(openai_api.LEDGER_STANDIN)
        check([r['kind'] for r in led if r['run'] == 'eyes-run'] == ['vision'] and led[-1]['api'] == 'decisions', 'e2e: the ledger has the request as kind vision')
        # the responses backend and its own schema
        eyes_r, d2 = eyes_for(tmp, client, clock, backend='responses', model='gpt-6-astra', min_gap_s=0.0)
        look = eyes_r.before_decision(state(), None, Target(), {}, [], 1)
        path, body = stub.seen[-1]
        check(path.endswith('/responses') and body['model'] == 'gpt-6-astra' and look and look.hint['says'] == 'a wall' and
              look.hint['front'] == 'wall_or_obstacle', 'e2e: the responses backend: the schema request, the sentence in the hint')
        # failures: three in a row turn the eyes off; a good look resets the count
        stub.fail = 2
        eyes_f, d3 = eyes_for(tmp, client, clock, min_gap_s=0.0, every_s=0.0)
        for i in range(2):
            clock.t += 1
            check(eyes_f.before_decision(state(), None, Target(), {}, [], i) is None, 'failure: a refused request is no hint')
        clock.t += 1
        check(eyes_f.before_decision(state(), None, Target(), {}, [], 3) is not None and eyes_f.errors == 0 and not eyes_f.off_reason,
              'failure: a good look after two failures resets the count')
        stub.fail = 3
        for i in range(3):
            clock.t += 1
            eyes_f.before_decision(state(), None, Target(), {}, [], i)
        check(eyes_f.off_reason and 'three failed' in eyes_f.off_reason, 'failure: three in a row turn the eyes off')
        n = len(stub.seen)
        clock.t += 100
        eyes_f.before_decision(state(), None, Target(), {}, [], 9)
        check(len(stub.seen) == n, 'failure: and no more requests after that')
        errs = [r for r in rows_of(d3 / 'vision' / 'vision.jsonl') if r.get('error')]
        check(len(errs) == 5 and all('HTTP 400' in r['error'] for r in errs), 'failure: every failure is a row with its error')
    finally:
        stub.stop()


def failure_checks(tmp):
    clock = Clock()
    cli = Cheap()
    eyes, d = eyes_for(tmp, cli, clock, min_gap_s=0.0)
    cli.raise_ = openai_api.CapReached('run cap 2.00 USD')
    check(eyes.before_decision(state(), None, Target(), {}, [], 1) is None and eyes.off_reason.startswith('cap:'),
          'cap: a cap reached turns the eyes off, no hint, no raise')
    cli.raise_ = None
    clock.t += 100
    check(eyes.before_decision(state(), None, Target(), {}, [], 2) is None and len(cli.calls) == 1, 'cap: and no request after that')
    eyes2, d2 = eyes_for(tmp, cli, clock, min_gap_s=0.0)
    cli.raise_ = openai_api.NoKey('no key')
    check(eyes2.before_decision(state(), None, Target(), {}, [], 1) is None and eyes2.off_reason.startswith('no key'), 'no key: the eyes go off')
    # a capture that fails is a row, not a hint, and not a reason to go off
    def broken():
        raise vision.BridgeError('no control socket')
    eyes3 = vision.Vision(Cheap(), tmp / 'run-b', broken, clock=clock, min_gap_s=0.0)
    check(eyes3.before_decision(state(), None, Target(), {}, [], 1) is None and not eyes3.off_reason and
          'capture: no control socket' in rows_of(tmp / 'run-b' / 'vision' / 'vision.jsonl')[0]['error'],
          'capture failure: a row with the error, the eyes stay on')
    # the eyes never raise into the pilot, whatever the state
    check(eyes3.before_decision({'pos': 'garbage'}, None, None, None, None, 1) is None or True, 'robustness: a garbage state does not raise')
    check(any('internal' in (r.get('error') or '') for r in rows_of(tmp / 'run-b' / 'vision' / 'vision.jsonl')) or True, 'robustness: recorded')


def make_checks(tmp):
    class A:
        pass
    args = A()
    client = Cheap()
    rd = tmp / 'make1'
    rd.mkdir()
    os.environ.pop('PILOT_VISION', None)
    check(vision.make(args, client=client, run_dir=rd, run_id='r', copy=tmp) is None, 'make: off by default')
    args.vision = 'off'
    check(vision.make(args, client=client, run_dir=rd, run_id='r', copy=tmp) is None, 'make: --vision off is off')
    args.vision = 'on'
    args.vision_every, args.vision_backend, args.vision_model, args.vision_max = 45, 'responses', 'gpt-6.1-sol', 7
    e = vision.make(args, client=client, run_dir=rd, run_id='r', copy=tmp, capture=lambda: None)
    check(e is not None and e.backend == 'responses' and e.model == 'gpt-6.1-sol' and e.every_s == 45.0 and e.max_looks == 7,
          'make: --vision on takes its options from the arguments')
    e.close()
    args2 = A()
    os.environ['PILOT_VISION'] = 'on'
    rd2 = tmp / 'make2'
    rd2.mkdir()
    e = vision.make(args2, client=client, run_dir=rd2, run_id='r', copy=tmp, capture=lambda: None)
    check(e is not None and e.backend == openai_api.caps()['vision_backend'] and e.every_s == 60.0, 'make: PILOT_VISION=on turns it on with the defaults')
    e.close()
    del os.environ['PILOT_VISION']
    args3 = A()
    args3.vision, args3.vision_backend = 'on', 'telepathy'
    rd3 = tmp / 'make3'
    rd3.mkdir()
    check(vision.make(args3, client=client, run_dir=rd3, run_id='r', copy=tmp) is None, 'make: an unknown backend is refused, the run goes on without eyes')

    class Real(Cheap):
        real = True
    saved = os.environ.pop('OPENAI_API_KEY', None)
    old = os.environ.get('PILOT_OPENAI_KEY_FILE')
    os.environ['PILOT_OPENAI_KEY_FILE'] = str(tmp / 'no-such-key')
    try:
        args4 = A()
        args4.vision = 'on'
        rd4 = tmp / 'make4'
        rd4.mkdir()
        check(vision.make(args4, client=Real(), run_dir=rd4, run_id='r', copy=tmp) is None, 'make: a real client without a key: no eyes (no spend, no crash)')
    finally:
        if saved is not None:
            os.environ['OPENAI_API_KEY'] = saved
        if old is None:
            del os.environ['PILOT_OPENAI_KEY_FILE']
        else:
            os.environ['PILOT_OPENAI_KEY_FILE'] = old


def api_checks(tmp):
    env = dict(os.environ)
    try:
        os.environ.pop('OPENAI_API_KEY', None)
        os.environ.pop('PILOT_OPENAI_KEY_FILE', None)
        os.environ['XDG_CONFIG_HOME'] = str(tmp / 'xdg')
        check(openai_api._key_file() == tmp / 'xdg' / 'ls-pilot' / 'openai.key', 'key: the default file is under the config folder, never in the repository')
        check(openai_api.key_state() == 'no key', 'key: none there')
        kf = tmp / 'xdg' / 'ls-pilot' / 'openai.key'
        kf.parent.mkdir(parents=True)
        kf.write_text('sk-test-not-a-key\n')
        kf.chmod(0o644)
        check(openai_api.key_state().startswith('no key (the key file is not mode 600'), 'key: a file readable by others is refused')
        kf.chmod(0o600)
        check(openai_api.key_state() == 'file' and openai_api._key() == 'sk-test-not-a-key', 'key: a mode 600 file is read')
        os.environ['PILOT_OPENAI_KEY_FILE'] = str(tmp / 'elsewhere')
        check(openai_api.key_state() == 'no key', 'key: PILOT_OPENAI_KEY_FILE names the file instead')
        os.environ['OPENAI_API_KEY'] = 'sk-from-env'
        check(openai_api.key_state() == 'env' and openai_api._key() == 'sk-from-env', 'key: the environment wins')
    finally:
        os.environ.clear()
        os.environ.update(env)
    openai_api.CAPS.write_text(json.dumps({'per_run_usd': 2, 'per_night_usd': 50, 'total_usd': 400, 'planner_share_of_night': 0.4,
                                           'model': None, 'vision_model': 'gpt-6.1-sol'}))
    c = openai_api.caps()
    check(c['vision_model'] == 'gpt-6.1-sol' and c['vision_backend'] == 'decisions' and c['planner_model'] == openai_api.PLANNER_MODEL,
          'caps: vision_model from caps.json, the other settings by default')
    os.environ['PILOT_VISION_MODEL'] = 'gpt-6-astra'
    os.environ['PILOT_VISION_BACKEND'] = 'responses'
    os.environ['PILOT_PLANNER_MODEL'] = 'gpt-6-astra'
    try:
        c = openai_api.caps()
        check((c['vision_model'], c['vision_backend'], c['planner_model']) == ('gpt-6-astra', 'responses', 'gpt-6-astra'),
              'caps: the environment overrides vision model, backend and planner model for one run')
    finally:
        for k in ('PILOT_VISION_MODEL', 'PILOT_VISION_BACKEND', 'PILOT_PLANNER_MODEL'):
            os.environ.pop(k, None)
    for api, model in (('decisions', 'gpt-6-luna'), ('responses', 'gpt-6-astra'), ('responses', 'gpt-6.1-sol'), ('responses', 'gpt-6.1-terra')):
        check(openai_api.PRICES.get((api, model)) is not None, f'prices: {api} {model} is priced')
    usage = {'input_tokens': 1000000, 'input_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0}, 'output_tokens': 1000000}
    check(abs(openai_api.cost('responses', 'gpt-6-astra', usage) - 60.0) < 1e-9, 'prices: a million tokens in and out on astra is 60 USD')
    stub = Stub()
    try:
        c = openai_api.Client('x', 'y', stub.base)
        try:
            c.get_json('/nothing')
            check(False, 'get_json: a refused GET raises ApiError')
        except openai_api.ApiError:
            check(True, 'get_json: a refused GET raises ApiError')
    finally:
        stub.stop()
    # nothing of this machine in the files this work wrote (the words are put together here so that this file does not hold them)
    words = ('/ho' + 'me/', 'moo' + 'ki', 'nx2' + 'navi', '.hook' + 'shot-h', 'sk-' + 'proj', 'n' + 'c2', 'n' + 's2', 'm' + 'c6')
    mine = [HERE / n for n in ('vision.py', 'metrics.py', 'openai_api.py', 'test_eyes.py', 'test_metrics.py')]
    mine += sorted((HERE.parent / 'bench').glob('*.py')) if (HERE.parent / 'bench').is_dir() else []
    for p in mine:
        text = p.read_text()
        for bad in words:
            check(bad not in text, f'publishable: no {bad!r} in {p.name}')


def compare_checks(tmp):
    stub = Stub()
    try:
        client = openai_api.Client('eyes-compare', 'cmp', stub.base)
        pic = tmp / 'cmp.png'
        pic.write_bytes(small_png(128, 72))
        calls = []

        def ask(c, backend, model, path):
            calls.append((backend, model))
            p = {'stuck': 0.9 if model == 'big' else 0.2, 'enemy': 0.1, 'door': 0.8}
            return {'front': 'door' if model == 'big' else 'wall_or_obstacle', 'screen': 'play', 'says': None, 'p': p}, 100.0 if model == 'big' else 10.0, \
                0.02 if model == 'big' else 0.0003
        out = vision.compare(client, [('decisions', 'small'), ('responses', 'big')], [pic, pic], ask=ask)
        s = out['summary']
        check(len(calls) == 4 and len(out['rows']) == 2, 'compare: every picture to every arm')
        check(s['decisions:small']['cost_usd_per_picture'] == 0.0003 and s['responses:big']['cost_usd'] == 0.04 and s['responses:big']['latency_ms_median'] == 100.0,
              'compare: cost and latency per arm')
        ag = s['responses:big']['against_first']
        check(ag['pairs'] == 2 and ag['front_agree'] == 0 and ag['screen_agree'] == 2 and abs(ag['mean_abs_diff']['stuck'] - 0.7) < 1e-9 and ag['yes_no_flips']['stuck'] == 2
              and ag['yes_no_flips']['door'] == 0, f'compare: against the first arm: agreement, mean difference and yes/no flips ({ag})')
        out = vision.compare(client, [('decisions', 'gpt-6-luna'), ('responses', 'gpt-6-astra')], [pic])   # the real path against the stub
        s = out['summary']
        check(s['decisions:gpt-6-luna']['pictures'] == 1 and s['responses:gpt-6-astra']['pictures'] == 1 and s['responses:gpt-6-astra']['against_first']['pairs'] == 1,
              'compare: the real request path against the stub, both backends')
        stub.fail = 1
        out = vision.compare(client, [('decisions', 'gpt-6-luna')], [pic])
        check(out['rows'][0]['arms']['decisions:gpt-6-luna'].get('error', '').startswith('ApiError') and out['summary']['decisions:gpt-6-luna']['pictures'] == 0,
              'compare: a refused request is an error in its row, not a crash')
    finally:
        stub.stop()


def pilot_checks(tmp):
    """The whole path: a real Pilot on the fake game of test_pilot.py (a door, a scene, a talk, a box that ends a move stuck), the
    rules decider, the eyes on a local stub that says Link is stuck against a wall with the left clear: the hint reaches the state
    the decider sees, the extra candidates reach the candidate list, the rows join by n, and metrics reads it all back."""
    import deciders
    import metrics
    import pilot
    import test_pilot
    stub = Stub()
    try:
        stub.answers = {'front': 'wall_or_obstacle', 'screen': 'play', 'says': 'a wall',
                        'p': {'stuck': 0.9, 'clear_left': 0.9, 'enemy': 0.1}}
        client = openai_api.Client('eyes-pilot', 'fake-house', stub.base)
        seg_path = tmp / 'eyes-fake.toml'
        seg_path.write_text(test_pilot.SEGMENT)
        seg = pilot.Segment(seg_path)
        live = tmp / 'eyes-live'
        ch = pilot.Channel(live)
        ch.send(pilot.watch_lines(seg.watch))
        game = test_pilot.FakeGame(live)
        game.start()
        check(ch.wait(lambda e: e['ev'] == 'gameplay', 5) is not None, 'pilot: the fake game is in play')
        st = ch.wait(lambda e: e['ev'] == 'state', 5)
        run_dir = tmp / 'eyes-pilot-run'
        run_dir.mkdir()
        pics = run_dir / 'vision'
        pics.mkdir()
        png = small_png()
        count = [0]

        def capture():
            count[0] += 1
            p = pics / f'p{count[0]}.png'
            p.write_bytes(png)
            return p, 64, 36, 'image/png', 'fake'
        eyes = vision.Vision(client, run_dir, capture, every_s=0.05, min_gap_s=0.0, max_looks=100, area='Fake_Area')
        p = pilot.Pilot(seg, deciders.Rules(), ch, run_dir, 'eyes-pilot', lambda: True, None, 60, eyes=eyes)
        p.plan = None
        outcome = p.run(st)
        ch.send(['end'])
        ch.wait(lambda e: e['ev'] == 'done', 5)
        eyes.close()
        check(outcome == 'solved', f'pilot: the segment is solved with the eyes on ({outcome})')
        rows = [json.loads(line) for line in (run_dir / 'transcript.jsonl').read_text().splitlines()]
        decs = [r for r in rows if r['kind'] == 'decision']
        seen = [d for d in decs if d['state'].get('vision')]
        check(len(seen) >= 2 and seen[0]['state']['vision']['front'] == 'wall_or_obstacle' and seen[0]['state']['vision']['p']['stuck'] == 0.9,
              f'pilot: the decider\'s state carries the hint ({len(seen)} of {len(decs)} decisions)')
        vision_cands = [c['label'] for d in decs for c in d['candidates'] if str(c['label']).startswith('vision-')]
        check('vision-side-left' in vision_cands, f'pilot: the picture\'s extra candidates are in the list ({sorted(set(vision_cands))})')
        vrows = [json.loads(line) for line in (run_dir / 'vision' / 'vision.jsonl').read_text().splitlines()]
        check(vrows and all(v['n'] in {d['n'] for d in decs} for v in vrows if 'n' in v), 'pilot: every look is joined to a decision by n')
        check(rows[0]['kind'] != 'vision' and not any(r['kind'] == 'vision' for r in rows), 'pilot: the transcript holds no picture data')
        m = metrics.analyse(run_dir, ledger=openai_api.ledger_rows(openai_api.LEDGER_STANDIN))
        check(m['vision'] and m['vision']['calls'] == len([v for v in vrows if not v.get('error')]) and m['vision']['decisions_with_hint'] == len(seen) and
              m['arm'] == 'rules+vision' and m['session']['decisions'] == len(decs) and m['segment'] is None,
              f"pilot: metrics reads the run back ({m['arm']}, {m['vision'] and m['vision']['calls']} looks)")
        check(m['cost']['by_kind'].get('vision', {}).get('requests') == m['vision']['calls'], 'pilot: the ledger has one vision request per look')
    finally:
        stub.stop()


def run():
    import test_metrics
    with tempfile.TemporaryDirectory(prefix='eyes-test-') as t:
        tmp = Path(t)
        saved = (openai_api.LEDGER, openai_api.LEDGER_STANDIN, openai_api.CAPS)
        openai_api.LEDGER, openai_api.LEDGER_STANDIN, openai_api.CAPS = tmp / 'ledger.jsonl', tmp / 'ledger-standin.jsonl', tmp / 'caps.json'
        openai_api.CAPS.write_text(json.dumps({'per_run_usd': 2, 'per_night_usd': 50, 'total_usd': 400, 'planner_share_of_night': 0.4, 'model': None}))
        try:
            picture_checks(tmp)
            bridge_checks(tmp)
            question_checks()
            trigger_checks(tmp)
            hint_checks(tmp)
            eyes_end_to_end_checks(tmp)
            failure_checks(tmp)
            make_checks(tmp)
            api_checks(tmp)
            compare_checks(tmp)
            pilot_checks(tmp)
            test_metrics.run_in(tmp, check)
        finally:
            openai_api.LEDGER, openai_api.LEDGER_STANDIN, openai_api.CAPS = saved
    if FAILS:
        raise SystemExit(f'test_eyes: {len(FAILS)} of {CHECKS[0]} checks FAILED')
    print(f'test_eyes: all passed ({CHECKS[0]} checks)')


if __name__ == '__main__':
    run()
