#!/usr/bin/env python3
"""The pilot's MCP server (stdio): a session for any MCP client to play. Python standard library only, no `mcp` package.

    python3 -I -B pilot/mcp_server.py --session <session folder>      (or PILOT_MCP_DIR)

What a client needs: to launch that command and speak MCP's JSON-RPC over its stdin and stdout (one JSON message a line; protocol
versions 2025-06-18, 2025-03-26 and 2024-11-05; tools only), and a pilot run that waits for it:

    python3 -I -B pilot/pilot.py run <segment.toml> --driver mcp --mcp-dir <session folder> [--mcp-wait <seconds>]

Client configuration (the usual shape of `mcpServers`):
    {"ls-pilot": {"command": "python3", "args": ["-I", "-B", "<this file>", "--session", "<session folder>"]}}

Tools (all take and return JSON text, the screenshot an image):
    status           the session: which run, what phase (waiting for an act, executing, ended), whether the pilot is alive, the briefing
    observe          the current decision point: the state, the goal and target, what was tried, the allowed actions. {after_n, wait_s}
                     waits up to wait_s seconds (at most 120) for a decision point newer than after_n
    allowed_actions  just the allowed actions of the current decision point (label and what it does) and the verbs for own steps
    act              answer decision `n`: {n, step: <an allowed label>, plan?: [<labels>], reason?} or {n, steps: [<hsap step lines>]} for
                     steps of your own (walk, run, press, stick, push, wait, until, face..., not cheat/save/shot/end); refused with the
                     reason when it is not allowed, and you may act again for the same n
    screenshot       the game's picture now (downscaled), through the run's control socket; {width}. The picture goes to your client.

The pilot decides nothing while it waits: each decision point stays open until an act arrives or the pilot's wait runs out (then its
chain falls back to the next driver, or the run ends, as the scenario said). Everything the agent does is in the run's transcript and
recording, so the session can be played back with `--driver playback`.
"""
import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from drivers import mcp_session  # noqa: E402

PROTOCOLS = ('2025-06-18', '2025-03-26', '2024-11-05')
SERVER = {'name': 'ls-pilot', 'version': '1'}
MAX_WAIT = 120.0
STALE_S = 30.0   # the pilot writes a heartbeat at least every two seconds while it waits

TOOLS = [
    {'name': 'status', 'description': 'The pilot session: run, segment, phase, whether the pilot is alive, and the briefing.',
     'inputSchema': {'type': 'object', 'properties': {}, 'additionalProperties': False}},
    {'name': 'observe',
     'description': 'The current decision point: state, goal, target, what was tried, the allowed actions. With after_n and wait_s '
                    'it waits (at most 120 s) for a decision point newer than after_n.',
     'inputSchema': {'type': 'object', 'properties': {'after_n': {'type': 'integer', 'minimum': 0},
                                                      'wait_s': {'type': 'number', 'minimum': 0, 'maximum': MAX_WAIT}},
                     'additionalProperties': False}},
    {'name': 'allowed_actions', 'description': 'The allowed actions of the current decision point (label and what each does).',
     'inputSchema': {'type': 'object', 'properties': {}, 'additionalProperties': False}},
    {'name': 'act',
     'description': 'Answer decision n with one allowed action (step, optionally a plan of up to two more labels) or with steps of '
                    'your own (a list of hsap step lines). Refused with the reason when not allowed; you may act again for the same n.',
     'inputSchema': {'type': 'object', 'required': ['n'],
                     'properties': {'n': {'type': 'integer'}, 'step': {'type': 'string'},
                                    'plan': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': 2},
                                    'steps': {'type': 'array', 'items': {'type': 'string'}, 'maxItems': mcp_session.MAX_LINES},
                                    'reason': {'type': 'string'}, 'agent': {'type': 'string'}},
                     'additionalProperties': False}},
    {'name': 'screenshot', 'description': 'The game\'s picture now, downscaled (an image).',
     'inputSchema': {'type': 'object', 'properties': {'width': {'type': 'integer', 'minimum': 160, 'maximum': 1920}},
                     'additionalProperties': False}},
]


class ToolError(Exception):
    pass


class Server:
    def __init__(self, session_dir, clock=time.time, sleep=time.sleep, capture=None):
        self.session = mcp_session.Session(session_dir)
        self.clock, self.sleep = clock, sleep
        self.capture = capture      # (width) -> (path, mime): tests give a fake; None means the pilot's vision.Capture
        self.shots = 0
        self.agent = None

    # ---- JSON-RPC
    def handle(self, msg):
        """The response to one JSON-RPC message (a dict), or None for a notification."""
        if not isinstance(msg, dict) or msg.get('jsonrpc') != '2.0':
            return self.error(msg.get('id') if isinstance(msg, dict) else None, -32600, 'not a JSON-RPC 2.0 message')
        method, mid, params = msg.get('method'), msg.get('id'), msg.get('params') or {}
        if method is None:   # a response to us: nothing to do
            return None
        if mid is None:      # a notification (notifications/initialized, notifications/cancelled): no answer
            return None
        try:
            if method == 'initialize':
                want = params.get('protocolVersion')
                info = params.get('clientInfo') or {}
                if info.get('name'):
                    self.agent = f"{info['name']} {info.get('version', '')}".strip()
                self.session.make()
                self.session.write('client.json', {'client': info, 'protocol': want, 'at': self.clock()})
                return self.result(mid, {'protocolVersion': want if want in PROTOCOLS else PROTOCOLS[0],
                                         'capabilities': {'tools': {'listChanged': False}}, 'serverInfo': SERVER,
                                         'instructions': 'Play the pilot\'s run: observe, then act for the decision n you saw; '
                                                         'screenshot when you need to see.'})
            if method == 'ping':
                return self.result(mid, {})
            if method == 'tools/list':
                return self.result(mid, {'tools': TOOLS})
            if method == 'tools/call':
                return self.result(mid, self.call(params.get('name'), params.get('arguments') or {}))
        except ToolError as e:
            return self.result(mid, {'content': [{'type': 'text', 'text': str(e)}], 'isError': True})
        return self.error(mid, -32601, f'method not found: {method}')

    @staticmethod
    def result(mid, result):
        return {'jsonrpc': '2.0', 'id': mid, 'result': result}

    @staticmethod
    def error(mid, code, message):
        return {'jsonrpc': '2.0', 'id': mid, 'error': {'code': code, 'message': message}}

    # ---- tools
    def call(self, name, args):
        fn = {'status': self.t_status, 'observe': self.t_observe, 'allowed_actions': self.t_allowed, 'act': self.t_act,
              'screenshot': self.t_screenshot}.get(name)
        if fn is None:
            raise ToolError(f'no tool {name!r}')
        if not isinstance(args, dict):
            raise ToolError('the arguments must be an object')
        out = fn(args)
        if isinstance(out, dict) and out.get('type') == 'image':
            return {'content': [out]}
        return {'content': [{'type': 'text', 'text': json.dumps(out, indent=1, default=str)}]}

    def state(self):
        st = self.session.read('status.json')
        alive = bool(st) and mcp_session.pid_alive(st.get('pid')) and self.clock() - float(st.get('alive_ts') or 0) < STALE_S
        return st, alive

    def t_status(self, args):
        info = self.session.read('session.json')
        st, alive = self.state()
        if not info:
            return {'session': str(self.session.dir), 'pilot': 'no pilot has made this session: start `pilot.py run ... --driver mcp '
                                                              f'--mcp-dir {self.session.dir}`'}
        ended = self.session.read('ended.json')
        return {'session': str(self.session.dir), 'run': info.get('run'), 'segment': info.get('segment'),
                'phase': (st or {}).get('phase'), 'n': (st or {}).get('n'), 'note': (st or {}).get('note'),
                'pilot_alive': alive, 'ended': ended, 'safe_verbs': info.get('safe_verbs'), 'briefing': info.get('briefing')}

    def current(self):
        obs = self.session.read('observe.json')
        if obs is None:
            raise ToolError('no decision point yet: the pilot has not asked (is it running? see status)')
        return obs

    def t_observe(self, args):
        after = args.get('after_n')
        wait = min(max(float(args.get('wait_s') or 0), 0.0), MAX_WAIT)
        end = self.clock() + wait
        while True:
            obs = self.session.read('observe.json')
            if obs is not None and (after is None or obs.get('n', 0) > after):
                break
            ended = self.session.read('ended.json')
            if ended is not None:
                return {'ended': ended, 'last_n': (obs or {}).get('n')}
            if self.clock() >= end:
                if obs is None:
                    raise ToolError('no decision point yet: the pilot has not asked (is it running? see status)')
                return dict(obs, waiting_for_newer_than=after, note='no newer decision point yet')
            self.sleep(0.1)
        rej = self.session.read('rejected.json')
        st, alive = self.state()
        return dict(obs, pilot_alive=alive, phase=(st or {}).get('phase'),
                    last_refusal=rej if rej and rej.get('n') == obs.get('n') else None)

    def t_allowed(self, args):
        obs = self.current()
        return {'n': obs['n'], 'actions': obs['candidates'], 'own_steps': {'verbs': obs.get('safe_verbs'),
                                                                            'example': ['walk 3 4', 'press A 200', 'wait 1']}}

    def t_act(self, args):
        n = args.get('n')
        obs = self.current()
        if not isinstance(n, int) or isinstance(n, bool):
            raise ToolError('act needs n, the number of the decision point you observed')
        if n != obs.get('n'):
            raise ToolError(f'decision {n} is not the open one: the pilot is at decision {obs.get("n")} (observe again)')
        if self.session.read('ended.json') is not None:
            raise ToolError('the run has ended')
        if ('step' in args) == ('steps' in args):
            raise ToolError('act with exactly one of `step` (an allowed label) or `steps` (your own step lines)')
        labels = [c['label'] for c in obs['candidates']]
        if 'step' in args and args['step'] not in labels:   # (the pilot checks too; refusing here is quicker)
            raise ToolError(f'step {args["step"]!r} is not one of the allowed actions: {", ".join(labels)}')
        if 'steps' in args:
            try:
                mcp_session.check_steps(args['steps'])
            except mcp_session.Refused as e:
                raise ToolError(str(e)) from None
        act = {k: args[k] for k in ('n', 'step', 'steps', 'plan', 'reason') if k in args}
        act['agent'] = args.get('agent') or self.agent
        self.session.write('act.json', act)
        return {'accepted': True, 'n': n, 'next': f'observe with after_n={n} and wait_s to see the result and the next decision point'}

    def t_screenshot(self, args):
        width = int(args.get('width') or 960)
        if self.capture is not None:
            path, mime = self.capture(width)
        else:
            path, mime = self.take(width)
        return {'type': 'image', 'data': base64.b64encode(Path(path).read_bytes()).decode(), 'mimeType': mime}

    def take(self, width):
        import vision   # the pilot's own capture: the control bridge's `shot`, downscaled (ImageMagick or the standard library)
        st = self.session.read('status.json') or {}
        sock = st.get('control_sock')
        if not sock:
            raise ToolError('no picture source: the game\'s control socket is not known (the pilot has not started its game, or the run '
                            'was attached without --vision-sock)')
        self.shots += 1
        vdir = self.session.dir / 'shots'
        try:
            path, _, _, mime, _ = vision.Capture(vdir, width=width, sock=sock, shots_dir=vdir)()
        except (vision.BridgeError, OSError) as e:
            raise ToolError(f'screenshot failed: {e}') from None
        for old in sorted(vdir.glob('f*.*'))[:-12]:   # (a few kept; the disk is small)
            old.unlink(missing_ok=True)
        return path, mime


def serve(server, fin, fout):
    for line in fin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            out = server.error(None, -32700, 'parse error')
        else:
            if isinstance(msg, list):
                out = [r for r in (server.handle(m) for m in msg) if r is not None] or None
            else:
                out = server.handle(msg)
        if out is not None:
            fout.write(json.dumps(out) + '\n')
            fout.flush()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--session', default=os.environ.get('PILOT_MCP_DIR'), help='the session folder the pilot run waits on (or $PILOT_MCP_DIR)')
    a = ap.parse_args(argv)
    if not a.session:
        ap.error('--session (or PILOT_MCP_DIR) is required')
    serve(Server(a.session), sys.stdin, sys.stdout)
    return 0


if __name__ == '__main__':
    sys.exit(main())
