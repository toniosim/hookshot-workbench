# The hourly check's prompt

Give everything below the line to CronCreate, with `<START>` (when it was scheduled), `<CUTOFF>` (when the user
expects to be back) and `<SNAP>` (a folder in the session's scratchpad) filled in. Cron: `17 <h1>-<h2> <dom> <mon> *`,
off the :00 mark, covering only the hours until the cut-off. The job lives only in this session: it stops when the
session ends.

---

Testing-loop check (scheduled by you earlier this session while the PC is free; this is not a new user message). If the user has written anything since <START>, or it's after <CUTOFF>, do nothing. Otherwise follow the
skill hookshot-testing-loop, section "Each check":
1. `python3 -I ~/.claude/skills/hookshot-testing-loop/scripts/requests_digest.py --since <SNAP>/last.json --save <SNAP>/last.json`
2. Apply the skill's picking rules to what's new or newly approved. If one fits and you hold no claim: claim it,
   start a worker with the skill's brief.md, and renew at every check while it runs. When a worker reports back:
   the skill's "Check before posting" and "Post" sections, then `done`. If anything is unclear or unexpected,
   release the claim and leave it for the user.
3. Note (don't re-test) whether a PR tested this session has a new head.
4. Reply in one line: what came in and why it doesn't fit, or what you started or posted.
