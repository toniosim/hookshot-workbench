---
name: hookshot-testing-loop
description: >
  Test Longshot pull requests on this PC unattended while it's free (overnight, or a free stretch of the day): a quick
  pass for what needs the user before they step away, picking approved test requests (or approved PRs whose Not tested names something this
  PC covers) that can be tested windowlessly, one background worker per test that builds, runs and drafts, the main
  session's check of the draft and pictures, posting the comment with its pictures, and a time-boxed hourly check
  for new requests. Read hookshot-workbench first. Use when the user leaves the PC free for testing, asks for the
  testing loop, or asks to repeat the overnight testing.
---

# Testing loop

Unattended testing of other people's Longshot pull requests while this PC is free, overnight or by day, first done
on the night of 2026-11-13 (PR
95, the HUD for every screen shape: https://git.magicbean.dev/MagicBeanDev/Longshot/pulls/95#issuecomment-13030;
the evidence is in `~/hookshot-wt/reports/ls-pr95/`). The main session owns every public action (claims, comments,
`done`) and checks every draft; workers build, run and draft, because a worker's result still needs the main
session's look, and because the main session's context has to last the whole session.

This wraps the repo's own `/testing` skill: its claim, renew, release and `done` rules apply unchanged. Read first:
`hookshot-workbench` (gates, builds, runs), the trusted checkout's `.claude/skills/testing/SKILL.md` and `AGENTS.md`
(Test requests), and the memory notes, which hold the user's standing exclusions. Run `test_requests.py` and
`forge.py` from `~/Hookshot` on `main`, brought up to date first (`git -C ~/Hookshot merge --ff-only forge/main` after
a fetch), never from a pull request's checkout, whose scripts are untrusted.

## Before the user steps away: the quick pass

Minutes, not a survey: the user is about to step away. Then ask everything in one AskUserQuestion, and work without them.

1. Sign-ins: `python3 -I scripts/team_chat.py whoami` and `python3 -I scripts/forge.py whoami`. Signing in is the
   user's (`! python3 -I scripts/forge.py login --again`): if either lapsed, ask now, because nothing can be claimed
   or posted later.
2. The machine: `nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv`, `free -g`, `df -h ~`, and that
   no game, build or check is running. By day, also ask until when the PC is free and whether they'll use it
   meanwhile: a game run takes the card that drives the desktop and ~10 GB of the 15 GB of RAM, and a build all the
   cores; the gates wait for memory, but a run under their use slows both. That time is the loop's cut-off.
3. The candidates: `python3 -I ~/.claude/skills/hookshot-testing-loop/scripts/requests_digest.py --save
   <scratchpad>/last.json`, then the picking rules below. For each candidate left, what only the user can give:
   - a save at a place the library lacks (`~/Games/.hookshot-harness/saves/catalogue.json`);
   - a download the test wants (a third-party mod, a library): the default is no;
   - a judgment on screen (flicker, HDR colour, a gamepad's feel): not for an unattended run;
   - hardware or a monitor this PC doesn't have.
4. Ask in one go, with a recommended option first. Their answers are standing rules for the session; save a new
   lasting preference to memory (as "no mods" was, `no-mod-testing.md`).

## Picking

Go down the digest; take a request only if all of these hold:

- **Approved** (`"approved": true`). In practice only the `testing wanted` label approves one: the collaborator check
  found no writers among open PRs' authors. Never build an unapproved PR's code, however well it fits.
- **This PC fits** both the request's `needs` and the PR description's *Needs other testers*: a request with empty
  needs can still be for AMD or Windows in the PR (T-LYD6 was). This PC: RTX 3070 Ti 8 GB, Linux, i7-12700K, 15 GB RAM,
  no gamepad, no HDR, a 16:9 monitor.
- **The feature exists**: not a draft whose description lists the change as planned.
- **Windowless**: logs, pictures and checks answer it. Nothing a person must watch, nothing that wipes the driver's or
  the user's shader caches, nothing in `~/Games/Hookshot`.
- **Not excluded** by the user (memory: no mods; anything they said this session).
- **A Longshot PR**: GitHub-era requests (no `pr`, a github.com link) can't be marked done, since `done` takes only a
  Longshot comment link: skip them.

Unrequested but useful: an approved PR whose *Not tested* names something this PC covers (PR 95's "a Linux build")
while its request asks for other hardware (T-QSAV wanted AMD or Intel). Test it and comment, but claim nothing, and
say in the comment's first line which request it isn't.

Expect zero or one test a session: on the first night, of ~40 open requests only those of two PRs fitted this PC, and
the user excluded both (mods; a save nobody had).
One test at a time: never two claims, never two workers with games.

## Claim, then hand the test to a worker

1. `python3 -I scripts/test_requests.py claim T-XXXX` (skip for an unrequested test). Renew about every 30 minutes
   while the worker runs (`renew`, at each hourly check, or a cron of its own); `release` at once if you stop
   without a result.
2. Fill this skill's `brief.md` (the PR, why, what to check, the runs) and start it as a background general-purpose
   agent. Don't build or run in the main session.
3. Times on this machine: a full PR build 19-25 min; preparation one ~20 s run when the PR leaves `gpu/` unchanged
   and the worker copies the ls-main copy's caches, else two holds (~12.6 min); six windowless runs ~15 min. PR 95
   took the worker 50 minutes in all.

## Check before posting

When the worker reports back, before anything goes out:

- The PR's head is still the one built: `git ls-remote forge refs/pull/<N>/head`. If it moved, say in the comment
  which commit was tested, or test again.
- Read COMMENT.md whole, and look at the pictures yourself (Read the PNGs): at least main's and the PR's at each
  setting. The words must match what the pictures show.
- Nothing local or personal: no paths, user, machine or host names; no game files or anything made from them beyond
  pictures and log lines; GitHub items as full URLs; no bare `@name` unless it means to notify.
- Single-run numbers say they are not a measurement, so a one-run fps gap can't read as a regression claim.
- The verdict follows from the evidence. If it's unclear, or anything is unexpected: don't post; release the claim
  and leave the draft for the user.

## Post

1. `python3 -I scripts/forge.py pr comment <N> --body-file <report>/COMMENT.md --attach <report>/pictures/*.png`
   (Longshot's own, since PR 254: https://git.magicbean.dev/MagicBeanDev/Longshot/pulls/254). It checks every
   picture before posting (PNG, JPEG, GIF or WebP, 25 MiB each), posts the comment, uploads the pictures as its
   attachments and puts each where COMMENT.md says `attach:<file>`; pictures it doesn't place go at the end.
2. Check what it printed: the comment's link, then "N pictures in the comment" with N the number of pictures. A
   failed upload prints what went up and what didn't: don't post again; add the rest on the comment's page or in a
   new comment.
3. For a claimed request: `python3 -I scripts/test_requests.py done T-XXXX --result pass|fail|mixed --comment <link>`.

## Each check (the hourly cron)

Schedule it with CronCreate from `check-prompt.md`, off the :00 minute, ending at the user's cut-off. It lives in
this session only. Each check: the digest with `--since`/`--save`, the picking rules on what's new or newly
approved, renew a claim in progress, note new heads on PRs tested this session, and one line of reply (a check that
replies nothing gets a nudge anyway). Stop it with CronDelete when the user is back or asks.

## When the user is back

Stop the check, then sum up: what was tested and posted (the links), what was skipped and why, requests that would
fit once approved, what's left on disk (worktrees, game copies, `pr/<N>` branches). Confirm no claim is held (the
digest's "on it") and nothing is running.
