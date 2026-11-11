---
name: hookshot-pr-evidence
description: >
  Take a finished Hookshot change to a pull request on NotRexed/Hookshot at the user's standard and keep it honest
  afterwards: the issue that claims it, the overlap search, the evidence to collect while working (result lines,
  per-run tables, labelled pictures), the body in the user's form (what it is for, what is measured, what is not;
  problem; what changed; how tested; risks), the checks before a push, review, and testing other people's pull
  requests. Also the rules for every comment posted as the user. Use when asked to open, update, rebase or review a
  Hookshot pull request, to collect evidence for one, or to post anything on its tracker.
---

# Hookshot pull requests and posts: evidence in, promises kept

Upstream is `NotRexed/Hookshot` (GPL-3.0-or-later); the user's fork is `mooki000/Hookshot` (remote `fork` in
`/home/mooki/Code/Hookshot`). Everything is posted as the user (mooki000) and **only by the main session**; agents
write drafts and never push or post. The project's own rules come first: `docs/workflow.md`, `AGENTS.md`,
`CONTRIBUTING.md`. Read `skill://hookshot-workbench` for building and running. Written 2026-11-10; rewritten
2026-11-11 after eighteen pull requests were opened with it and the user set the standard below.

## The standard (the user's words, 2026-11-11)

> look at the previous prs in the nx2navi repo as far as level of quality and reporting and keep that as the standard,
> i mean my prs, that had lots of detail and images etc

His models are his own pull requests on `tangerineturtle1/NX2navi` (closed now, still readable:
`gh pr view <n> --repo tangerineturtle1/NX2navi`): **#518** (co-op: 15 KB, 8 pictures, a findings table, questions),
**#382** (DLAA: before and after pictures, a four-run table), **#504** (walk key: three menu pictures, a headless test
with its counts), also #494, #496, #393, #506. What they have in common is the bar for every pull request here:

1. A reader who knows nothing learns from the first paragraph who gains what, what was measured and what was not.
2. The problem is a chain of causes down to the file and function, not a symptom.
3. Every claim has its evidence beside it: the exact result line, a table with every run (never only a mean), a
   labelled picture. What was only built says "built"; what was not run says "not run".
4. The risks and the untested parts are said plainly, in their own sections, before a reviewer has to ask.
5. A draft stays a draft while the feature is not done, but it carries its evidence all the same.

## The body, section by section

Hookshot wants a Conventional Commit title and a body that opens with why. Inside that, use this form (leave out a
section only when it would be empty; a one-line fix still has the first paragraph, what changed, how tested, not
tested):

```
**What this is for:** who gains what, in a player's or developer's words, with the issue (#N). **What is measured:**
hardware, system, base commit, and each kind of check in half a sentence, with the headline numbers. **Not measured:**
platforms, GPUs, areas, input devices, lengths that were not tried.

## Problem            (or "The cause" for a fix found in someone's logs)
- the chain of causes, each bullet one link, with file and function names; what the player sees at the end of it

## What changed
- per file or per commit: what it does now; what is deliberately unchanged (defaults, other paths); line counts when
  the size matters to a reviewer; a mermaid diagram when a protocol or a sequence is new

## How to switch it on / How to try it        (features and tools only)

## How it was tested
Environment line: system, kernel, GPU and driver, CPU, base commit and head, date, window or headless, picture size,
the load. Then one bullet per check, each with its result as the program printed it:
- the new test on the branch, and the same test against main's source (the failing case named)
- tests/run_all.py totals, with the failures that are this machine's named and explained
- game runs: what was done, the log lines quoted, a table with one row per run
- pictures, each with a caption that says what to look at
- what was rerun after a rebase and what was only rebuilt

## Not tested          (or "Not shown yet" for a draft)
## Risks               what could break and for whom; what a wrong guess here would look like
## Overlaps            other open pull requests in the same lines, from scripts/pr_overlap.py, hunks read
## Questions for you   only real decisions for the maintainers, numbered
Assisted-by: Claude Opus 5.5
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

Plain words, short sentences, no promises without a date. Numbers carry their conditions; "no difference beyond the
spread" is said as such, with the spread. Real examples of this form: #2274 (co-op draft: three two-game sessions as a
table, a failed check said plainly, a four-panel picture), #2322 (per-run frame table from a quiet machine with the
harness's own lines), #2289 (a fault proven from thirteen reporters' logs).

## Collect the evidence while you work, not afterwards

Keep it under `reports/<Topic>-files/` as you go; a body written from memory fails the review. For every change:

| What | How | Where it ends up |
|---|---|---|
| Environment | `uname -r`, `clang --version`, driver from `nvidia-smi` or the log's device line, `git rev-parse --short origin/main HEAD`, `date`, `uptime` | the environment line |
| The test both ways | on the branch: the last lines it prints; on main: `--source <main's file>` or main's worktree, the failing case | "How it was tested", verbatim |
| The whole suite | `hs-idle.sh <deps python> -I -B tests/run_all.py` (the exact command is in hookshot-workbench; the system python lacks zstandard and Tk and gives false failures) | totals and the named failures |
| Game runs | `hs-run.sh` summary lines kept whole (exit, frames, fatal, devlost, nocore, kernel, load before -> after); the log lines that prove the point, copied, not retyped | a fenced block and a table |
| Comparisons | runs in turn (A B A B), each run one row; the load at each start; only quiet-window runs for frame rates (`skill://hookshot-perf-compare`) | the table; a script with asserts makes it |
| Reporters' logs | download every attachment, count by script (`N of M logs show line X`), keep the script | a table by reporter, version, card |
| Pictures | before and after from the same place and settings; menus cropped to the rows in question; several frames as one labelled picture (`scripts/panels.sh`) | the evidence gist, linked by commit |
| Sessions of two games (co-op) | the session script's `checks.txt` (every check with its line), the relay's log, both games' logs, the stats lines | a table with one column per session |
| What failed | keep it: a failed check, a run that hitched, a flagged outlier | said in the body, never dropped |
| Overlaps | `scripts/pr_overlap.py <n>` or `--branch <name>`, then read each conflict hunk | "Overlaps" |

Things that were asked for in review every time they were missing: the base commit, the load, whether the run had a
window, what the default is and who sets it, and what happens on Windows.

## Before work starts: the claim, the issue and the overlap search

The work is claimed before it starts (`docs/workflow.md`: on the issue and in Discord, with what, why and the hardware
it can be tested on; the score is severity weight S0 8, S1 5, S2 3, S3 1, times reach, times confidence 1.0, 0.7 or
0.4). **A claim issue is opened only while there is no pull request yet.** On 2026-11-11 the maintainer closed four
claim issues of ours the same day as duplicates of their pull requests ("closing the issue so the work is tracked in
one place there"), so an issue next to a pull request that already exists is noise.

1. Search first; add to an existing issue instead of opening a duplicate:

       gh search issues --repo NotRexed/Hookshot --match title,body "<two or three words>" --json number,title,state
       gh pr list --repo NotRexed/Hookshot --state all --search "<words>" --json number,title,state
       /home/mooki/.agents/skills/hookshot-pr-evidence/scripts/pr_overlap.py --branch <name>

2. An existing issue: comment the claim there (what, why, hardware, the branch or pull request); the pull request
   says `Fixes #N` (or `Refs #N` when it is one part) and names the tracking issue.
3. No issue, and the pull request can be opened the same day (a fix that is already proven, a reviewer's follow-up):
   no issue. The pull request is the record; its first paragraph and its Problem section carry what the issue would
   have said, and it names the review or pull request it follows.
4. No issue, and the work takes longer or needs a decision before it starts (a feature, a change of behaviour):
   open one. Blank issues are switched off, so write the body with the form's own headings
   (`.github/ISSUE_TEMPLATE/1-game-problem.yml`, `2-build-problem.yml`, `3-idea.yml`) and end it with the claim.
   Small fixes of one kind share one issue. The maintainer may close it once the pull request exists.

       gh issue create --repo NotRexed/Hookshot --title "<plain sentence>" --body-file <file>

5. The claim and the pull request are announced in the Discord's #dev-agents by the main session (skill
   `hookshot-discord-updates`: `Claiming …`, then `PR up …`). Rows go into `reports/POSTED.md` and
   `reports/PR-INDEX.md`.

A claim is dropped out loud when the work stops.

## Before any push (all must pass)

1. **Nothing made from the game** in the branch: no dump, no `work/`, no built game, saves, lifted C, shader dumps,
   logic or lists read out of the game's files. `git status` clean of build output; no `.gitignore` bypass.
2. **Licence**: only code that can be GPL-3.0-or-later. Nothing from NX2navi's repository (its additions are "all
   rights reserved"); the user's own earlier files only as `/home/mooki/Code/hookshot-wt/reports/OURS.md` allows.
   Third-party code keeps its notice.
3. **One topic**, on a branch from current `main`; rebased before review is asked again.
4. **Checks**: a game-free test that fails without the change, and the whole of `tests/run_all.py` (many tests cut
   functions out of the source by their text: a renamed function breaks one; fix it in the same change).
5. **In the game**, on this machine: what was done and what was seen, and a row for `docs/tested-configurations.md`
   for each measured run.
6. **Commits**: author `Michael Schienbein <7663497+mooki000@users.noreply.github.com>`; each message ends with
   `Assisted-by: Claude Opus 5.5` and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
7. **The main session** reads every commit's diff, runs the test both ways itself, runs the gate script, and only
   then pushes:

       /home/mooki/Games/.hookshot-harness/hs-pr-check.sh <branch> <title file>      # must print PASS
       git -C /home/mooki/Code/Hookshot push --force-with-lease fork <branch>          # never to origin
       gh pr create --repo NotRexed/Hookshot --head mooki000:<branch> --base main --title "$(cat <title file>)" --body-file <body file>

   An agent hands over three things: the branch with its head, `reports/drafts/<Topic>-title.txt`, and
   `reports/drafts/<Topic>-body.md` with no placeholder left; then it stops editing them.

## The title

A Conventional Commit, checked by CI and used as the squash commit and the changelog line: `feat(scope): ...`,
`fix(scope): ...`, `perf`, `refactor`, `docs`, `test`, `ci`, `build`, `chore`, `revert`; scopes as the project uses
them (`vk`, `linux`, `menu`, `runtime`, `builder`, `video`, `vcores`, `coop`). `feat` makes a minor release, `fix` and
`perf` a patch: choose the type by what the change is. After the colon, say what is true after the change in the
player's words (`Linux Play leaves the game its hookshot_log.txt again`).

## Pictures

Pictures and videos of the game are allowed (the rule is about game files). They go in the user's evidence gist
`b86bd3f35969803fb032f71f035844f8`, linked by commit so an old post cannot change:

    git clone https://gist.github.com/b86bd3f35969803fb032f71f035844f8.git /tmp/gist-evidence    # once per boot
    scripts/panels.sh /tmp/hookshot-<topic>-<what>.jpg 2 <frame1> "1. <what to look at>" <frame2> "2. ..."
    cp /tmp/hookshot-<topic>-<what>.jpg /tmp/gist-evidence/ && git -C /tmp/gist-evidence add -A
    git -C /tmp/gist-evidence -c user.name="Michael Schienbein" -c user.email=7663497+mooki000@users.noreply.github.com commit -m "<topic>: <what the pictures show>" && git -C /tmp/gist-evidence push
    sha=$(git -C /tmp/gist-evidence rev-parse HEAD)
    # ![<the panels in one sentence>](https://gist.githubusercontent.com/mooki000/b86bd3f35969803fb032f71f035844f8/raw/$sha/hookshot-<topic>-<what>.jpg)

- A fix shows before and after from the same place; a feature shows its screen in each state; a menu change shows the
  rows, cropped (`PANEL_CROP`); a co-op change shows both games.
- Number the panels and say in each caption what to look at. **Look at every picture before citing it**, and fetch it
  once through its raw link after the push (the bytes must match).
- Nothing unpublished and nothing private in it: other tabs of a menu under work, paths with the home folder, a room
  secret that is still in use.
- Frames come from `hs-run.sh`'s `shots/` folder; a contact sheet finds the right ones quickly:
  `magick montage -label '%t' <every nth frame> -tile 6x -geometry 426x240+2+2 sheet.jpg`.
- The Intel GPU's picture on main has false colours for a known reason: use the RTX 4090's game for pictures.

## Every post as the user (twelve corrections on 2026-11-10 made these rules)

1. **Read the thread's newest comments in one command; post in a later command** that first checks the last comment
   is still the one read (author and time, and for a pull request its head), and does not post if it changed.
2. **Every sentence against its source** before posting: the log line, the test, the picture, the file and line. What
   is inferred is said as inferred; what was not run on Hookshot is said so.
3. **Numbers go through a script with asserts**, never by hand; say the build, the settings and the load.
4. **Before calling anything "the default"**, grep the whole tree for who sets it.
5. **A mistake is corrected in place with a dated note**, never silently.
6. **Overlaps** are described only after reading the conflict hunk.
7. Short, plain, only what helps the reader act. What is owed goes into `POSTED.md`'s last column and is kept.
8. **Read a draft whole** before posting it (never through `fold` or `cut`), and when two writers touched it, post
   from your own copy.
9. Keep every posted text in `reports/posted/`, a row in `reports/POSTED.md`, pull requests in `reports/PR-INDEX.md`.

## After opening

- **Comments and reviews**: `hs-watch-threads.py <numbers>` runs in the background and reports new ones; once a day,
  and whenever the user asks, read all of them in one sweep (a loop of `gh pr view <n> --json comments,reviews` over
  `gh pr list --author mooki000`, and `gh api notifications`). Answer each the same day: a tester gets thanks and what
  his result settles and leaves open; a finding is fixed with a test that fails without the fix.
- When `main` moves: rebase, rebuild, rerun what the change touches, push with lease, say what was rerun and what was
  only built.
- When new evidence arrives (an owed run, a picture), add it to the body with a dated line.
- When it merges: move the row in `docs/worklist.md` to "Fixed, waiting for a release", and after the release ask the
  reporter to retest.

## Other people's pull requests

1. `git -C /home/mooki/Code/Hookshot fetch origin pull/<n>/head:refs/remotes/pr/<n>`; read the whole diff and thread;
   note what the author measured and on what.
2. Build it and its base as two game copies; measure what it claims against the base in turn in one hold, with the
   load noted; pictures or the flash check when it touches drawing.
3. Verdict, one of: **helps** (measured), **nothing to show here**, **breaks** (what, with evidence), **cannot be
   tested here** (why). Post only measured things, short: the build, the scene, the numbers, a fault with its fix
   offered. Linux with NVIDIA's driver is Tier 1 for the project and is what this machine adds; an Intel device on
   Mesa is the second thing it can test.
