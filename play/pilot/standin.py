#!/usr/bin/env python3
"""A local stand-in for the two OpenAI endpoints the pilot uses, answering in their documented shapes, on loopback only.
For tests and for runs that must not spend: pilot.py run ... --api-base http://127.0.0.1:<port>/v1

  POST /v1/decisions  (developers.openai.com/api/docs/guides/decisions and the create reference): answers in question
                      order; a choice answers {"type": "choice", "name", "choice", "probabilities": [{"value",
                      "probability"}], "confidence"}, a predicate {"type": "predicate", "name", "probability"}, a score
                      {"type": "score", "name", "score", "probabilities": [{"label", "value", "probability"}],
                      "confidence"}; "usage" {"input_tokens", "input_tokens_details": {"cached_tokens",
                      "cache_write_tokens"}, "output_tokens": 0, "output_tokens_details": {"reasoning_tokens": 0},
                      "total_tokens"}. Its choice: the value STANDIN_CHOICE names if offered, else the first.
  POST /v1/responses  a "message" output item with one "output_text" part: the first value of each enum in the
                      request's JSON schema (an object that fits it), and a usage block.

Token counts are the request's length over four: a guess, never billed. Every request's headers and body are kept in
memory; GET /seen returns them (tests check that no real key arrived).

  standin.py [--port 0]   prints "port N" when it listens
"""
import argparse
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SEEN = []


def fit(schema):
    t = schema.get('type')
    if 'enum' in schema:
        return schema['enum'][0]
    if t == 'object':
        return {k: fit(v) for k, v in schema.get('properties', {}).items()}
    if t == 'array':
        e = schema.get('items', {})
        return [fit(e)] if 'enum' in e else []
    if t == 'string':
        return 'stand-in answer'
    if t in ('number', 'integer'):
        return 0
    if t == 'boolean':
        return False
    return None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def reply(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == '/seen':
            return self.reply(200, SEEN)
        self.reply(404, {'error': 'not found'})

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        SEEN.append({'path': self.path, 'headers': dict(self.headers), 'body': raw.decode('utf-8', 'replace')})
        try:
            body = json.loads(raw)
        except ValueError:
            return self.reply(400, {'error': {'message': 'not JSON'}})
        tokens = len(raw) // 4
        usage = {'input_tokens': tokens, 'input_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0},
                 'output_tokens': 0, 'output_tokens_details': {'reasoning_tokens': 0}, 'total_tokens': tokens}
        if self.path == '/v1/decisions':
            qs = body.get('questions')
            if not body.get('model') or not isinstance(qs, list) or not 1 <= len(qs) <= 400 or 'input' not in body:
                return self.reply(400, {'error': {'message': 'model, input and 1 to 400 questions are required'}})
            answers = []
            for q in qs:
                if q.get('type') == 'choice':
                    vals = [c['value'] for c in q['choices']]
                    if not 2 <= len(vals) <= 255 or len(set(map(str, vals))) != len(vals):
                        return self.reply(400, {'error': {'message': 'between 2 and 255 unique choices'}})
                    want = os.environ.get('STANDIN_CHOICE')
                    pick = want if want in vals else vals[0]
                    rest = (1 - 0.7) / max(1, len(vals) - 1)
                    answers.append({'type': 'choice', 'name': q.get('name'), 'choice': pick, 'confidence': 0.6,
                                    'probabilities': [{'value': v, 'probability': 0.7 if v == pick else rest} for v in vals]})
                elif q.get('type') == 'predicate':
                    answers.append({'type': 'predicate', 'name': q.get('name'), 'probability': 0.1})
                elif q.get('type') == 'score':
                    lv = q['levels']
                    answers.append({'type': 'score', 'name': q.get('name'), 'score': 0.0, 'confidence': 0.5,
                                    'probabilities': [{'label': x['label'], 'value': i, 'probability': 1.0 if i == 0 else 0.0}
                                                      for i, x in enumerate(lv)]})
                else:
                    return self.reply(400, {'error': {'message': f"unknown question type {q.get('type')}"}})
            return self.reply(200, {'answers': answers, 'model': body['model'], 'usage': usage})
        if self.path == '/v1/responses':
            fmt = ((body.get('text') or {}).get('format') or {})
            out = fit(fmt.get('schema', {})) if fmt.get('type') == 'json_schema' else 'stand-in answer'
            usage['output_tokens'] = 20
            return self.reply(200, {'object': 'response', 'model': body.get('model'), 'status': 'completed', 'output': [
                {'type': 'message', 'role': 'assistant', 'content': [
                    {'type': 'output_text', 'text': out if isinstance(out, str) else json.dumps(out)}]}],
                'usage': usage})
        self.reply(404, {'error': {'message': f'no route {self.path}'}})


def serve(port=0):
    srv = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=0)
    a = ap.parse_args()
    srv = ThreadingHTTPServer(('127.0.0.1', a.port), Handler)
    print(f'port {srv.server_address[1]}', flush=True)
    srv.serve_forever()


if __name__ == '__main__':
    main()
