#!/usr/bin/env python3
"""A small agent of our own as an MCP client: an OpenRouter tool-calling model plays the pilot's session through the pilot's stdio MCP server.

    python3 -I -B pilot/mcp_agent.py --session <session folder> [--run-id R] [--segment S] [--model M] [--max-steps N] [--wall SECONDS]
                                     [--usd D] [--out agent.json]

It starts `mcp_server.py --session <folder>` as a child (stdio, JSON-RPC), lists the server's tools, gives them to the model as functions and
lets it call them (observe, allowed_actions, act, screenshot, status) until the run has ended or a budget is spent: model calls (--max-steps,
default $PILOT_AGENT_STEPS or 60), wall time (--wall, 280 s), dollars (--usd, 0.05). Every model request goes through the pilot's caps and
ledger (kind `agent`, under --run-id, so the run's own cap counts it); the cost is the response's usage.cost. The key is read from
$PILOT_OPENROUTER_KEY_FILE (default ~/.config/ls-pilot/openrouter.key, mode 600) at each request and is never printed or written. A picture
from the screenshot tool is handed to the model as an image. pilot.py run --driver mcp --mcp-agent loop starts this at the first decision.
Output: --out JSON (the tool calls, the model's steps, the money, why it stopped); exit 0 when the run ended, 1 when a budget stopped it, 2 when
it could not start (no key, no server).
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import openai_api  # noqa: E402
from drivers import chat as chat_mod  # noqa: E402
from drivers.access import OPENROUTER_KEY  # noqa: E402

SYSTEM = ('You are the player of an automatic test pilot for a 3D action adventure game, connected through MCP tools. The pilot asks for '
          'a decision again and again; each decision point has a number n. Loop: call observe with after_n set to the number of the last '
          'decision you answered (0 at first) and wait_s 60; read the goal, the state and the allowed actions in what it returns; call act '
          'with n and step set to exactly one of the allowed labels (the one that gets the goal done, by what the data says); then call '
          'observe again with after_n = n. Stop calling tools when observe says the run has ended. screenshot is optional: use it when the '
          'state does not explain why a step failed. Keep your own words to a minimum.')
TASK = 'Play the session now. Start with observe.'
# gpt-6-luna: 0.10 / 0.50 USD per million tokens on OpenRouter, takes tools and the routing flag; on the made-up house it solved the session in 8 decisions for 0.005 USD where
# openai/gpt-4.1-nano (fine for one choice among labels) declared victory early and failed the goal.
AGENT_MODEL = 'openai/gpt-6-luna'
KEEP_FULL = 6        # the last this many tool results are kept whole; older ones are shortened (the history is sent again at every step)
SHORT = 400


class McpClient:
    """A minimal MCP client over a child's stdio: one JSON-RPC message a line."""

    def __init__(self, session):
        self.p = subprocess.Popen([sys.executable, '-I', '-B', str(HERE / 'mcp_server.py'), '--session', str(session)], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        self.n = 0

    def send(self, obj):
        self.p.stdin.write(json.dumps(obj) + '\n')
        self.p.stdin.flush()

    def rpc(self, method, params=None):
        self.n += 1
        self.send({'jsonrpc': '2.0', 'id': self.n, 'method': method, 'params': params or {}})
        line = self.p.stdout.readline()
        if not line:
            raise RuntimeError('the MCP server closed: ' + self.p.stderr.read()[-300:])
        r = json.loads(line)
        if 'error' in r:
            raise RuntimeError(f"MCP error {r['error'].get('code')}: {r['error'].get('message')}")
        return r['result']

    def start(self):
        self.rpc('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 'ls-pilot-agent-loop', 'version': '1'}})
        self.send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        return self.rpc('tools/list')['tools']

    def call(self, name, args):
        return self.rpc('tools/call', {'name': name, 'arguments': args})

    def close(self):
        try:
            self.p.stdin.close()
            self.p.wait(timeout=10)
        except Exception:   # noqa: BLE001
            self.p.kill()


def flatten(result):
    """(text, image) of a tool result: the text parts joined, and (mime, base64) of the first image part."""
    text, image = [], None
    for part in result.get('content') or []:
        if part.get('type') == 'text':
            text.append(part.get('text', ''))
        elif part.get('type') == 'image' and image is None:
            image = (part.get('mimeType') or 'image/png', part.get('data') or '')
            text.append('(a picture; it follows)')
    return '\n'.join(text), image


def trimmed(messages):
    """The history to send: tool results older than the last KEEP_FULL shortened."""
    idx = [i for i, m in enumerate(messages) if m['role'] == 'tool']
    old = set(idx[:-KEEP_FULL])
    out = []
    for i, m in enumerate(messages):
        if i in old and len(m['content']) > SHORT:
            m = dict(m, content=m['content'][:SHORT] + ' ...(an older result, shortened)')
        out.append(m)
    return out


def run_agent(session, client, *, model, run_id=None, max_steps=60, wall_s=280.0, usd=0.05, mcp=None, log=print):
    """Play until the run ends or a budget is spent. Returns the result dict. `client` is a drivers.chat.ChatClient."""
    mc = mcp or McpClient(session)
    t0, spent, requests, calls_log, stop, ended, nudges, last_n = time.time(), 0.0, 0, [], None, False, 0, 0
    final_text = None
    try:
        tools = mc.start()
        oa_tools = [{'type': 'function', 'function': {'name': t['name'], 'description': t.get('description', ''), 'parameters': t['inputSchema']}} for t in tools]
        messages = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': TASK}]
        for step in range(1, max_steps + 1):
            left = wall_s - (time.time() - t0)
            if left <= 0:
                stop = 'wall time'
                break
            if spent >= usd:
                stop = 'dollar budget'
                break
            body = {'model': model, 'messages': trimmed(messages), 'tools': oa_tools, 'tool_choice': 'auto',
                    'max_tokens': 600, 'provider': {'require_parameters': True}}
            try:
                ans, ms, row = client.post(body, model=model, kind='agent', timeout=min(60.0, max(5.0, left)))
            except (openai_api.NoKey, openai_api.CapReached, openai_api.ApiError) as e:
                stop = f'{type(e).__name__}: {e}'[:300]
                break
            requests += 1
            spent += float(row.get('cost_usd') or 0)
            choice = (ans.get('choices') or [{}])[0]
            msg = choice.get('message') or {}
            calls = msg.get('tool_calls') or []
            final_text = msg.get('content') or final_text
            if not calls:
                messages.append({'role': 'assistant', 'content': msg.get('content') or ''})
                nudges += 1
                if nudges > 2:
                    stop = 'the model stopped calling tools'
                    break
                messages.append({'role': 'user', 'content': f'The run has not ended: observe has not said so. Call observe now with after_n = {last_n} and wait_s 60.'})
                continue
            nudges = 0   # (it is calling tools again)
            messages.append({'role': 'assistant', 'content': msg.get('content'), 'tool_calls': calls})
            for c in calls:
                fn = c.get('function') or {}
                name = fn.get('name')
                try:
                    args = json.loads(fn.get('arguments') or '{}')
                except ValueError:
                    args = None
                if not isinstance(args, dict):
                    text, image, ok = 'the arguments were not a JSON object', None, False
                else:
                    if name == 'observe':   # (the server waits for the pilot: never longer than 60 s or than the time left)
                        args['wait_s'] = min(float(args.get('wait_s') or 30), 60.0, max(1.0, wall_s - (time.time() - t0)))
                    res = mc.call(name, args)
                    text, image = flatten(res)
                    ok = not res.get('isError')
                calls_log.append({'step': step, 'tool': name, 'args': args if name != 'screenshot' else args, 'ok': ok, 'result': text[:300]})
                messages.append({'role': 'tool', 'tool_call_id': c.get('id'), 'content': text})
                if image:
                    messages.append({'role': 'user', 'content': [{'type': 'text', 'text': 'The picture from the screenshot tool:'},
                                                                 {'type': 'image_url', 'image_url': {'url': f'data:{image[0]};base64,{image[1]}'}}]})
                if name == 'act' and ok:
                    try:
                        last_n = int(json.loads(text).get('n') or last_n)
                    except (ValueError, TypeError, AttributeError):
                        pass
                if name == 'observe' and ok:
                    try:
                        if 'ended' in json.loads(text):
                            ended = True
                    except ValueError:
                        pass
            if ended:
                stop = 'the run ended'
                break
        else:
            stop = 'step budget'
        if stop is None:
            stop = 'step budget'
    finally:
        if mcp is None:
            mc.close()
    return {'model': model, 'run': run_id, 'steps_used': requests, 'max_steps': max_steps, 'tool_calls': len(calls_log), 'spent_usd': round(spent, 8),
            'usd_cap': usd, 'wall_s': round(time.time() - t0, 1), 'wall_cap_s': wall_s, 'stop': stop, 'ended': ended, 'final_text': (final_text or '')[:300],
            'calls': calls_log}


def make_client(run_id, segment, base=None):
    base = base or os.environ.get('PILOT_OPENROUTER_BASE') or chat_mod.OPENROUTER_BASE
    real = base.rstrip('/').startswith('https://openrouter.ai/')
    return chat_mod.ChatClient(run_id, segment, base, 'openrouter', OPENROUTER_KEY, key_required=True, send_key=real), real


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--session', required=True)
    ap.add_argument('--run-id', default=os.environ.get('PILOT_RUN_ID') or f'agent-{time.strftime("%Y%m%d-%H%M%S")}')
    ap.add_argument('--segment', default='agent')
    ap.add_argument('--model', default=os.environ.get('PILOT_AGENT_MODEL') or AGENT_MODEL)
    ap.add_argument('--max-steps', type=int, default=int(os.environ.get('PILOT_AGENT_STEPS') or 60))
    ap.add_argument('--wall', type=float, default=float(os.environ.get('PILOT_AGENT_WALL') or 280))
    ap.add_argument('--usd', type=float, default=float(os.environ.get('PILOT_AGENT_USD') or 0.05))
    ap.add_argument('--out')
    a = ap.parse_args(argv)
    client, real = make_client(a.run_id, a.segment)
    if real and OPENROUTER_KEY.state() not in ('file', 'env'):
        result = {'model': a.model, 'run': a.run_id, 'stop': f'OpenRouter: {OPENROUTER_KEY.state()}', 'ended': False, 'steps_used': 0, 'spent_usd': 0.0}
        code = 2
    else:
        try:
            result = run_agent(a.session, client, model=a.model, run_id=a.run_id, max_steps=a.max_steps, wall_s=a.wall, usd=a.usd)
            code = 0 if result['ended'] else 1
        except (RuntimeError, OSError) as e:
            result = {'model': a.model, 'run': a.run_id, 'stop': f'{type(e).__name__}: {e}'[:300], 'ended': False, 'steps_used': 0, 'spent_usd': 0.0}
            code = 2
    if a.out:
        Path(a.out).write_text(json.dumps(result, indent=1))
    print(json.dumps({k: result.get(k) for k in ('model', 'steps_used', 'tool_calls', 'spent_usd', 'wall_s', 'stop', 'ended')}), flush=True)
    return code


if __name__ == '__main__':
    sys.exit(main())
