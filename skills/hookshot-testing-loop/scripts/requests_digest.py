"""A short digest of Longshot's open test requests, and what changed since the last look.

    python3 -I requests_digest.py [--repo DIR] [--since SNAPSHOT.json] [--save SNAPSHOT.json] [--all]

Runs `scripts/test_requests.py list --json` in a trusted checkout of Longshot's main (default ~/Hookshot; never a
pull request's checkout, whose scripts are untrusted) and prints one block per request: ID, PR, approval, the PR's
state, needs, summary, who claims or reported, and the start of the notes. With --since, only requests that are new
or newly approved since that snapshot are printed (--all prints every request, marking those); --save writes the
current list for the next --since.
"""
import argparse
import json
import os
import subprocess
import sys


def load(repo):
    out = subprocess.run([sys.executable, "-I", "scripts/test_requests.py", "list", "--json"], cwd=repo,
                         capture_output=True, text=True, encoding="utf-8")
    if out.returncode != 0:
        sys.exit("test_requests.py list failed (%d): %s" % (out.returncode, (out.stderr or out.stdout).strip()))
    return json.loads(out.stdout)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=os.path.expanduser("~/Hookshot"))
    p.add_argument("--since", help="a snapshot written by --save")
    p.add_argument("--save", help="write the current list here")
    p.add_argument("--all", action="store_true", help="with --since, print every request, not only the changes")
    a = p.parse_args()
    now = load(a.repo)
    old = None
    if a.since and os.path.isfile(a.since):
        with open(a.since, encoding="utf-8") as f:
            old = {r["id"]: r for r in json.load(f)}
    shown = 0
    for r in now:
        mark = ""
        if old is not None:
            o = old.get(r["id"])
            if o is None:
                mark = "NEW "
            elif bool(o.get("approved")) != bool(r.get("approved")):
                mark = "NOW APPROVED " if r.get("approved") else "NO LONGER APPROVED "
            elif not a.all:
                continue
        shown += 1
        pr = "PR %s" % r["pr"] if r.get("pr") else "no Longshot PR (GitHub-era: can't be marked done)"
        print("%s%s  %s  approved=%s  state=%s" % (mark, r["id"], pr, r.get("approved"), r.get("pr_state")))
        print("   needs: %s" % (r.get("needs") or "(none given: read the PR's 'Needs other testers')"))
        print("   %s" % r.get("summary", ""))
        who = sorted(r.get("claims") or {}) + ["%s=%s" % (k, v.get("result") if isinstance(v, dict) else v)
                                               for k, v in sorted((r.get("results") or {}).items())]
        if who:
            print("   on it: %s" % ", ".join(who))
        print("   notes: %s" % " | ".join((r.get("notes") or "").splitlines())[:300])
    print("%d open, %d shown%s" % (len(now), shown, " (changes since %s)" % a.since if old is not None else ""))
    if a.save:
        with open(a.save, "w", encoding="utf-8") as f:
            json.dump(now, f)


if __name__ == "__main__":
    main()
