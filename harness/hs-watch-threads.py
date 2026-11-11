#!/usr/bin/env python3
"""Waits until someone other than mooki000 comments on, reviews, merges or closes one of the user's threads on
NotRexed/Hookshot (or hiKareeem/Clawshot), then prints what is new and exits. Read-only gh calls, one round every 150 s.
Threads: every open issue and pull request authored by mooki000, plus the numbers given as arguments (threads he commented on)."""
import json, subprocess, sys, time, datetime
REPO = 'NotRexed/Hookshot'
ME = 'mooki000'
extra = {int(a) for a in sys.argv[1:] if a.isdigit()}
start = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
def gh(*args):
    r = subprocess.run(['gh', *args], capture_output=True, text=True, timeout=60)
    return r.stdout if r.returncode == 0 else ''
def mine():
    out = gh('api', f'search/issues?q=repo:{REPO}+author:{ME}&per_page=50')
    try:
        return {i['number']: (i['state'], bool(i.get('pull_request')), i.get('pull_request', {}).get('merged_at')) for i in json.loads(out)['items']}
    except Exception:
        return None
base = None
while base is None:
    base = mine()
    if base is None: time.sleep(30)
while True:
    time.sleep(150)
    news = []
    try:
        for kind in ('issues/comments', 'pulls/comments'):
            out = gh('api', f'repos/{REPO}/{kind}?since={start}&per_page=100&sort=created&direction=desc')
            for c in (json.loads(out) if out else []):
                url = c.get('issue_url') or c.get('pull_request_url') or ''
                n = int(url.rstrip('/').split('/')[-1]) if url else 0
                if c['user']['login'] != ME and c['created_at'] > start and (n in base or n in extra):
                    news.append(f"#{n} {kind.split('/')[0]} comment by {c['user']['login']} at {c['created_at']}: {c['body'][:600]!r}")
        now = mine()
        if now:
            for n, (state, is_pr, merged) in now.items():
                old = base.get(n)
                if old and (old[0] != state or old[2] != merged):
                    news.append(f"#{n} is now {state}{' (merged ' + merged + ')' if merged else ''}")
            for n, (state, is_pr, merged) in now.items():
                if is_pr and state == 'open':
                    out = gh('api', f'repos/{REPO}/pulls/{n}/reviews')
                    for r in (json.loads(out) if out else []):
                        if r['user']['login'] != ME and (r.get('submitted_at') or '') > start:
                            news.append(f"#{n} review ({r['state']}) by {r['user']['login']} at {r['submitted_at']}: {(r.get('body') or '')[:500]!r}")
    except Exception as e:
        news.append(f'watcher error: {e!r}') if 'rate limit' in str(e).lower() else None
    if news:
        print(f"THREAD NEWS since {start}:")
        for x in dict.fromkeys(news): print(' -', x)
        break
