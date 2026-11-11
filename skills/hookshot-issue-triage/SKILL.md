---
name: hookshot-issue-triage
description: >
  Comb Hookshot's issues and pull requests for what this machine can reproduce, test or answer: refresh the survey,
  score a problem the way the project asks, reproduce it headless, and draft the comment. Use when asked to triage,
  survey, pick work from, or answer reports on NotRexed/Hookshot.
---

# Triage on Hookshot: what this machine can add

The project (`NotRexed/Hookshot`) merges a pull request in a median of one hour and closes issues into thirteen
`[Tracking]` issues (#993, #995 to #1006) and the collected feature requests (#1007). Labels are not used for triage;
`docs/worklist.md` is the ordered list, and claims are made in its Discord (#dev-work), so "nobody claims it on
GitHub" does not mean nobody works on it. This machine adds two things few contributors have: **Linux with an RTX 4090
on NVIDIA's driver** (Tier 1 for the project) and **an Intel UHD 770 on Mesa** (no mesh shaders: the compute fallback).
Read `skill://hookshot-workbench` for building and running, `skill://hookshot-pr-evidence` before anything is posted.

## The survey and how to refresh it

The survey of 2026-11-10 is `/home/mooki/Code/hookshot-wt/reports/HsSurvey.md`: how the project moves (numbers), every
open issue and pull request with a verdict for this machine, what exists of what we plan, which reports our earlier
findings answer, and a scored worklist of ten rows. Its data and scripts are in `reports/HsSurvey-files/`:

    cd /home/mooki/Code/hookshot-wt/reports/HsSurvey-files
    python3 fetch.py issues_open prs_open        # read-only gh calls; rewrites raw/*.json (no argument: everything)
    python3 analyse.py > analyse-out.txt         # cadence numbers
    python3 tables.py  > tables-out.md           # the two tables; the "what it is" and verdict columns live in the script

With about ten merges an hour the tables age within a day: refresh before picking work, and before any claim search
open pull requests again (`gh pr list --repo NotRexed/Hookshot --search "<words>"`), merged ones too.

## Scoring (their rule, `docs/workflow.md`)

score = severity weight x reach x confidence. Severity: S0 8 (security; crash, hang, device lost, PC freeze; lost
saves; the builder cannot build), S1 5 (cannot progress or start), S2 3 (wrong but playable; a frame-rate loss over
20 %), S3 1 (polish, features). Reach: the share of players affected (their `scripts/hardware_report.py` counts the
issue forms; Linux and SteamOS were 17 % of reports, NVIDIA 35 %). Confidence: 1.0 reproduced with a log, 0.7 two
reporters with logs, 0.4 one report or no log. Write the three parts in the claim or the comment. A new problem
becomes a row in `docs/worklist.md` through a pull request.

## One report, start to finish

1. Read the whole thread with its logs (`gh issue view <n> --repo NotRexed/Hookshot --comments`; download attached
   logs); read the tracking issue it belongs to; search open and merged pull requests for it.
2. Verdict for this machine before any run: reproducible here (Linux, NVIDIA or the Intel device, the story point
   reachable from a save in `/home/mooki/Games/.hookshot-harness/saves/`), or not (Windows only, AMD, HDR, a real pad).
3. Reproduce headless through the run wrapper at the reporter's settings (their log names version and options); ten
   runs if intermittent; pictures looked at; the log lines that show it. "Does not reproduce here in N runs at these
   settings" is a result worth posting when the reporter's hardware is ours.
4. If someone already has a pull request: build it against its base and test it here; the verdict is one of helps
   (measured), nothing to show here, breaks, cannot be tested here.
5. If nobody has: the cause before the fix; hand a fix to its own branch and pull request.
6. Draft the comment under `/home/mooki/Code/hookshot-wt/reports/drafts/`: what was run (build, settings, driver),
   what was seen, the numbers through a script, what was not tested. The main session posts it.

## What our earlier work answers

`/home/mooki/Code/hookshot-wt/reports/OURS.md` lists everything built for the other port of this game with a verdict
for Hookshot (port as a feature, fix there too, nothing to do). The two ports are unrelated code on the same game
binary: **facts about the game carry over** (its options, flags, files, what it asks of the system; addresses convert:
Hookshot = NX2navi - 0x7000000000 + 0x80020000), **code faults mostly do not**. A finding from the other port is a
lead until it is reproduced on Hookshot, and is posted as a lead (issue 1460's comment of 2026-11-10 is the model).

## Rules

- Nothing made from the game is posted or attached: no saves, no file lists, no shader dumps. Pictures and
  `hookshot_log.txt` are fine; keep asset names and local paths out of excerpts.
- Do not compete with a claimed fix: offer the reproduction and the evidence, and test their change.
- Everything posted goes into `reports/POSTED.md` with what is owed afterwards.
