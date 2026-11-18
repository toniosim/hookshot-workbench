# Rules for every agent working on LS or HS on this machine (tailored 2026-11-11 for toniosim's PC; merged with the author's brief of 2026-11-17 on 2026-11-18)

Adapted from the workbench author's brief (`git show upstream/main:docs/agent-brief.md` in this checkout has the original, written
for an Arch + Hyprland + RTX 4090 + 96 GB machine shared by many agents). This copy is for one user working with one
coding agent at a time.

## First: choose and use the skill

Before investigating, building, testing or drafting, read `~/.claude/skills/ls-workbench/SKILL.md`, then
the matching published skill IDs below. Use their existing tools rather than inventing another runner or parser.

| Task kind | Published skill ID | Tool to use |
|---|---|---|
| Any LS or HS work; build/run/check | `ls-workbench` | `tools/deps-local.sh`, build slot, `hs-run.sh`, `hs-idle.sh` |
| Issue survey, reproduction, reply | `ls-issue-triage` | `forge.py issue view N --comments`, `forge.py search`; read attachments and `POSTED.md` |
| PR/review/rebase/CI or tracker draft | `ls-pr-evidence` | the forge's API and `scripts/check_pr_description.py` (`references/forge.md`), `hs-win-fixture-check.sh`; Main posts with `ls_post.py` |
| FPS, frame-time, stutter comparison | `ls-perf-compare` + `ls-regression-hunt` | `regress.py` held worker and `run_case.py`; A B A B in an authorized exclusive hold |
| Regression, suspect/revert/bisect | `ls-regression-hunt` | `regress.py plan`, then authorized `hunt` |
| Controller-free play, state, saves | `ls-scripted-play` | `scripts/hookshot_ctl.py`, `playthrough/hsap.py` (capability-selected) |
| Nightly/rolling main testing | `ls-nightly-playtest` | existing `nightly/hs-nightly.py` watch; never create a second one |
| Team updates / Discord reads or named messages | `ls-discord-updates` | project's `scripts/team_chat.py` in `main-tools`; Main alone posts |
| Testing other people's PRs / request queue | `ls-pr-loop` | priority list; `scripts/test_requests.py` in `main-tools`; Main alone claims/renews/completes |
| Lifted game code, an `f_<address>` function, a game structure or subsystem | `ls-function-map` | `docs/oot/fnmap.py find` in the workbench checkout, before reading lifted C; what you work out goes back as a row in your report |
| A hold queued behind the quiet-window and measuring locks; one chain for many stages; a base that moved while waiting | `ls-hold-chain` | the chain starting points the skill names; `lslocks`; record your waiter's pid |
| Moving our own long cherry-picked branch onto a moved main | `ls-restack` | `reports/Integrate18-files/prove_carry.py`, `git range-diff`; not `ls-pr-loop`'s carry of a test result |
| Anything run, staged or captured on the remote Windows laptop (the second PC of a two-PC session) | `ls-windows-laptop` | `reports/tools/<win>/<win>-run.py`; only when the task text says so; `<win>` is the laptop's SSH alias (see "The public repository") |
| A session through the shared co-op relay on the LAN relay host; installing, updating or probing it | `ls-relay-lan` | `reports/Soak4-files/chain/<relay>-room-guard.py` before any Make; `<relay>` is the host's SSH alias (see "The public repository") |
| Two games (or the game-free player) behind simulated NATs on this PC: hole punching, STUN, relay fallback, a path-layer change before and after | `ls-nat-lab` | `reports/NatLab2-files/runner/labctl.py check` / `probe` / `report`; no sudo, no internet, no laptop |
| A skill was wrong, stale, misleading, or no skill covers a repeated procedure | `ls-skill-upkeep` | **Skill notes** in your report; the main session alone edits skills (`check_skills.py`) |

Published `ls-<suffix>` skills live in `skills/ls-<suffix>/` and use logical references such as `skill://ls-workbench`.
The host cutover is deferred: ten live sources remain `~/.claude/skills/hookshot-<suffix>/SKILL.md`; the new
`ls-function-map` and `ls-skill-upkeep` already have the same live and published name. Publication maps the sources
without renaming live folders. Keep every explicit live
command path below. This brief does not authorize or claim any sync, relocation, installation or cutover.

`skill://<name>` knows only the skills registered when the main session started: `ls-hold-chain`, `ls-restack`,
`ls-windows-laptop`, `ls-relay-lan`, `ls-nat-lab` and `ls-pr-tagging` answer `Unknown skill` although they exist. Read
`~/.claude/skills/<name>/SKILL.md` instead (the form the first sentence above uses); every `skill://` mention of one of
them in this brief and in the skills means that file.

Every report has a **Skills and tools** section: names read (and when: before starting, or only after getting stuck)
and tools actually used. Every report ends with **Skill notes**: one line for each thing in a skill that was wrong,
missing or misleading (quote the line), and for each procedure you had to invent that no skill covers; or `Skill
notes: none`. The main session records every note in `reports/SKILL-NOTES.md` and fixes the skill, so the next agent
does not meet the same fault. A missing skill declaration means usage is unrecorded, not proof it was ignored.
Read `MORNING.md`, the last 150 lines of `LOG.md`, and `POSTED.md` before describing thread work. A result is a
**finding** only after the whole thread it belongs to has been read and compared with what is already known.

**Current desktop restriction (2026-11-12): every game run is windowless.** Yesterday's window allowance is
withdrawn, even if `window-ok` remains on disk. A swapchain-only question is untested here until the user grants it again.

## The project and who we work for

- **Longshot** (`git.magicbean.dev/MagicBeanDev/Longshot`, Forgejo, GPL-3.0-or-later; until 2026-11-12 **Hookshot**,
  `NotRexed/Hookshot` on GitHub, same history): a static recompilation of the Switch 2 remake of *The Legend of
  Zelda: Ocarina of Time* for Windows and Linux. The user (`tonesi` on git.magicbean.dev, `toniosim` on GitHub)
  contributes to it and tests it on Linux. Pull requests, comments and test requests go through the clone's
  `scripts/forge.py` and `scripts/test_requests.py` (its `AGENTS.md`, `docs/forge.md`), not `gh`.
- **This machine:** Pop!_OS 24.04 LTS, COSMIC desktop (Wayland, `cosmic-comp`), Intel Core i7-12700K (8P+4E, 20
  threads) with its Intel UHD 770 (enabled, Vulkan device 1, Mesa), NVIDIA GeForce RTX 3070 Ti 8 GB (driver 595.104.02,
  Vulkan device 0) which also drives the desktop (~0.9 GB of it in use), 16 GB DDR5 (15.7 GB usable) and 19 GB swap.
  ImageMagick 6 (`convert`, `identify`, `montage`; no `magick`), crash reports through apport (`/var/crash`), no
  `coredumpctl`.

## Read before anything else

In the clone `/home/tonesi/Hookshot`: `docs/workflow.md`, `AGENTS.md`, `CONTRIBUTING.md`, then `docs/development.md` and
`docs/design.md`. Their rules bind you as they bind everyone. The ones that matter most:

1. **No game files, keys, or anything made from them leave this PC or enter the repository, an issue or a pull
   request**: not the dump, not `work/`, not built games, saves, lifted C, shader dumps. Pictures of the game, videos and
   `hookshot_log.txt` are fine. Game-derived data we make (flag names, coordinates, routes, world models, logic read from
   the game's files) stays local under the harness or the reports' files folders; if in doubt, it is game data.
   **The one exception is the workbench repository's two maps** (the workbench author's repository, published at
   https://github.com/mooki000/ls-workbench; this checkout is a fork of it): the function map and the flag map, both in `docs/oot/`. They may hold the
   game's own identifiers and what we know of them, and nothing else from the game: no file, no lifted code, no value
   from a save, no position. The flag map has a row for every flag of the game's list (about 26,700: its hash, its name where
   one was recovered by hashing, kind, save file and group, what co-op does with it, and what it is). **The two maps never
   leave the workbench repository**: the flag names, their rows and anything copied from them still never enter the LS or
   HS repository, an issue, a pull request, a comment or a post (say the hash and the family there).
   **A map of the game's lifted functions exists** (about 2,000 rows: what each `f_<address>` we have looked at does,
   its data and structures, and how sure each row is), in the workbench repository:
   `/home/tonesi/hookshot-workbench/docs/oot/` (published at https://github.com/mooki000/ls-workbench). Before
   reading lifted code, look the address up: `python3 /home/tonesi/hookshot-workbench/docs/oot/fnmap.py find
   f_803edf70` (or words); before working out a flag, look its hash, name or words up the same way with `flagmap.py`
   beside it (`find 4d77f1cb`, `show`), and a flag's place in a save file is in `docs/oot/save-format.md`. When you work out
   what a function or a flag is, write the row for it (conventions: `docs/oot/README.md`, "What may go here": an address or
   hash, a name of ours, a description in our own words, never lifted code or anything copied from the game's files) and hand
   the row to the main session in your report (a flag's as a row of `docs/oot/flags/descriptions.md`); do not commit or push
   in the workbench repository yourself.
2. **Licence: only code we may license under GPL-3.0-or-later.** The other port's repository puts everything added after its
   base import under "all rights reserved": **never copy a line from the other port's repository into LS or HS**, and never
   paste decompiled game code. There is no inventory of earlier work on this machine: re-implement from the idea against LS or HS's code; do not copy.
3. **One topic per pull request; a branch from current `main`; the cause before the fix; a game-free test that fails
   without the change** (many tests in `tests/` cut functions out of the source by their text: run
   `python -I -B tests/run_all.py`, all of it, and update a broken check in the same change). Forgejo runs no CI yet: run `tests/run_all.py` yourself and say so.
4. **Pull request title = a Conventional Commit** (`feat(scope): ...`, `fix(scope): ...`, `perf`, `docs`, `test`, `build`,
   ...); it becomes the squash commit. The description opens with why the change is needed, in one or two plain
   sentences; then what changed, how it was tested (GPU, driver, place in the game, frame rates before and after where
   speed is claimed), what was not tested, and screenshots when the change shows on screen. Link the issue.
4b. **A regression** (worked in an earlier build, broken in a newer one) gets the label `regression` with
   `priority/critical`, above every other bug (the user's word, 2026-11-14). Its pull request and its issue start with one
   line before everything else, so the Discord post shows it: `**Regression:** <what breaks> since <first bad build>,
   caused by <full link to the change>. <last good build> was fine.` plus the workaround if there is one.
5. **AI assistance is recorded** with trailers, as the maintainers do, naming the model that did the work. End
   each new commit message with the two attribution lines your session's own instructions give (for Claude Sonnet 5.5:
   `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`, and `Assisted-by: Claude Sonnet 5.5` where the project
   asks for it); keep the trailers of commits you replay. If your task text
   names other trailers than the model you are, use the ones for the model you are and say so in your report. A
   replayed commit keeps its own message. At most 16 sub-agents run at once.
   **A check is updated, never removed**: when main or a review changes what a test covers, bring its checks to the
   new code; do not delete one to make a rebase pass (a reviewer sent two of our pull requests back for that on
   2026-11-11).
6. **Coordination (user decision, 2026-11-12):** team updates use the project's `python -I scripts/team_chat.py`
   from `/home/tonesi/hookshot-wt/main-tools`. Main alone posts; read before claiming, at most one post/hour,
   in the source `.claude/skills/team-updates/SKILL.md` form: summary then applicable ordered labelled bullets
   (Done, Found, Claimed, PR, Working on, Blocked, Wanted), with full links. The user is already signed in;
   agents never read/copy the session under `~/.config/hookshot/` or `~/.config/longshot/`. Workers hand Main unposted drafts.
   Discord's browser is for reading and messages the user requests by name, not routine team updates.
   Test requests use `scripts/test_requests.py` and `docs/test-requests.md`; this PC may take fitting work by
   `ls-pr-loop`'s priority list, but only Main claims, renews and marks done. Results on others' PRs go out
   after Main's own numbers/pictures/thread check; opinions, disagreements and design questions go to the user first.
7. Hardware tiers: a change must not break NVIDIA RTX and AMD RX on Windows and Linux, or the Steam Deck, to help
   something else. Say what you could not test (Windows, AMD, real input devices).

## This machine's rules

- **Never touch**: `/home/tonesi/Games/Hookshot` (the user's play install: never run, change or write into it; reading
  its log is fine; `Hookshot/work/dump` links into it, so never write through `work/dump` either), `~/.config`,
  `~/Downloads`, global git config, system packages (no apt, no sudo, no `pip install` outside a venv). Never send input
  to or reconfigure the compositor.
- **Paths**: clone `/home/tonesi/Hookshot` (remotes `forge` = Longshot, fetch only, `main` tracks it; `forge-fork` =
  `tonesi/Longshot` once made, push here; legacy `origin` = NotRexed, `fork` = toniosim); worktrees under
  `/home/tonesi/hookshot-wt/<name>`; reports under `/home/tonesi/hookshot-wt/reports/`; built game copies under
  `/home/tonesi/Games/.hookshot-h-<name>`; harness under `/home/tonesi/Games/.hookshot-harness/` (symlinks into the
  workbench checkout `/home/tonesi/hookshot-workbench`, made by its `install.sh`). The toolchain comes from the
  unpacked v2.1.0 AppImage: `source /home/tonesi/Hookshot/build-linux/dev-env.sh` before any build or test (it puts that
  Python, emsdk's clang, `RX_CPM` and the libraries on the environment, under both `HOOKSHOT_*` and `LONGSHOT_*`
  names); `~/hookshot-wt/deps/python` and `deps/cpm` link to the same toolchain.
- **Memory is the tight resource.** 16 GB: one game reserves ~9.8 GB, a full build's lift ~4.8 GB per worker. So
  **one thing heavy at a time**: one game (the GPU gate never lets in a second, and waits for 6 GB available before a
  game starts), one build (`hs-build-slot` has one slot, two lift workers by default), one run of the checks
  (`hs-idle.sh`, one slot; pass `--jobs 8` to `run_all.py`). Don't start a build while a game runs, or the reverse,
  unless the user says so.
- **The GPU is the user's desktop.** Every program that creates a Vulkan device goes through a gate, headless or not:
  the RTX 3070 Ti through `/home/tonesi/Games/hs-gpu-slot <command>` (`hs-run.sh` does this itself), the Intel
  device through `/home/tonesi/Games/hs-intel-slot`. Builds through `/home/tonesi/Games/hs-build-slot`.
  Begin a command that touches a gate with `unset HSGATE_SLOT_DIR HSGATE_INTEL_SLOT_DIR HSGATE_SLOT_TEST
  HSGATE_SLOT_NODESKTOP HSGATE_IN_GATE`. Prefer headless runs (`HOS_HEADLESS`, the default of `hs-run.sh`).
- **Pictures larger than the game's 2048x1152** (`HOS_OUTPUT_RES`, `output_res=`) need more than this 8 GB card has
  beside the desktop (3840x2160 took 9.8-11.6 GB on the original machine): don't, unless testing exactly that.
- **Kernel lines.** After each run on the card count the driver lines since its start (`hs-run.sh` prints `kernel=`
  and `nvrm=`). Stop and tell the user at any `NVRM: Xid` line, any `kmemsysDoCacheOp` line, or any NVRM line you do
  not know. `NVRM: memMap_IMPL: CPU mapping not supported for addressSpace: 0x1` is expected (the game's dma-buf
  import is refused and it falls back); count it, don't stop for it. The GPU guard (`gpu-guard.sh`, started by the
  gate) kills harness programs on the card at a fault line and closes the card until
  `/home/tonesi/Games/.hookshot-harness/gpu-guard.sh --reopen`.
- **Windowed runs** (`hs-run.sh ... --window`): COSMIC has no window-rule interface, so the game opens an ordinary
  window that may take the focus and nothing watches it (`window=unmanaged`). Only while
  `/home/tonesi/Games/.hookshot-harness/window-ok` exists, and only when the user has asked for that run.
- **Never run with a synchronisation or safety mechanism switched off** without the user's word.
- **Tests that crash on purpose must not leave crash reports.** Run `tests/run_all.py` only through
  `/home/tonesi/Games/.hookshot-harness/hs-idle.sh python3 -I -B tests/run_all.py --jobs 8` and a single program that
  may die by a signal through `/home/tonesi/Games/.hookshot-harness/hs-nocore.sh <command>` (core limit 1 byte: the
  kernel then does not hand the crash to apport). Afterwards `ls -lt /var/crash | head` shows nothing new of yours.
  Game runs keep their crash reports.
- **Long jobs** (a full build is ~10 min on 32 threads elsewhere, probably 20-30 here) start from a script file with
  `setsid nohup ... < /dev/null &`, write their output under the report's files folder, and are named in the report.
- **One hold keeps the card for at most 8 minutes** (the gate's rule, from the author's 2026-11-11). A plan of many runs is cut
  into holds of at most 8 minutes of game time each (keep A B A B pairs inside one hold; chain the holds from a script so each
  asks the gate again). Never `--exclusive` without the user's word for that one hold: an exclusive run stops every new build
  and every run of the checks until it has finished. Counts (escapes, waits, left-out draws, memory, pictures, pass or fail)
  never need `--exclusive`: only frame times do. A longer hold exists only when your task text grants it, and each stage in it
  checks the time left before it starts. `skill://ls-hold-chain` (read it by path, `~/.claude/skills/ls-hold-chain/SKILL.md`)
  chains holds. Only one game runs at a time here, so the author's two-slot and two-games-in-one-hold rules do not apply:
  never read a frame rate from an ordinary run as a measurement anyway; pictures, log lines, counts, pass or fail are fine.
- A second known kind of NVRM line (the author's 2026-11-11): three lines in one second, `NV_ERR_NO_MEMORY ...
  _memdescAllocInternal`, `... rmStatus @ system_mem.c`, `... pRmApi->Alloc(...) @ nv_gpu_ops.c`: the driver was refused one
  large allocation of system memory and went on. Counted in `nvrm=`; a stop only when the run fails in any way or has more than
  three such events.
- **Long commands:** start from a saved script with `setsid --wait nohup`, output in your report's files folder. `setsid`
  without `--wait` can return success while its child is still queued: require the child's own completion receipt and
  exit code; never repeat a build or check because only its launcher ended. `nohup` leaves SIGHUP ignored in every child,
  which makes a test that sends SIGHUP (`tests/test_crash_record.py`) time out: start such a script as
  `setsid --wait nohup env --default-signal=HUP bash script`, or without `nohup`. In the tool shell a backgrounded
  `( ... "$t" ... ) &` inside a `for` loop expands `$t` late: use a script that takes the argument.
- Keep at most one waiter of yours in a gate. Record owned process identities at launch; a `pgrep -f` name match, `kill -0`
  on a zombie, or a gap between holds is not proof a chain ended. **Never `pkill` or `killall` anything**, by name or pattern:
  kill only pids you recorded when you started them (`kill <pid>`, or the job's own stop). End owned games before releasing
  the gate; `timeout` may put the game in a different process group from its shell wrapper.
- Never edit a running or queued script in place: stage, test, then replace atomically when no active process depends on it.
  `/tmp` is a tmpfs lost at reboot, and a different filesystem from `/home`: an atomic rename between them fails.
- Use `date` for every timestamp.

## Git

- Author: commits for Longshot are `tonesi <tonesi@noreply.git.magicbean.dev>`, the git.magicbean.dev no-reply address, so they link to
  the user's account there and the private e-mail never becomes public. It is set in the clone's own git config
  (`/home/tonesi/Hookshot/.git/config`, shared by its worktrees; the global config is untouched): nothing to pass per
  commit. Legacy GitHub commits used `toniosim <10343143+toniosim@users.noreply.github.com>`. Check a branch's authors with
  `git log --format='%h %ae %ce' forge/main..<branch>`; `forge.py pr create` and `pr ready` run the project's own description and
  game-files checks (the author's `hs-pr-check.sh` is gone upstream, the forge route replaced it).
- **Agents never push, never open or comment on an issue or pull request, never post to Discord** unless the user asks
  for that one action.

## Pull requests

`skill://ls-pr-evidence` has the form and the checklist; read it before you write a body. Pull requests ask for
lots of detail and images. In short:

- **When you edit an existing description, the forge's template forms stay exactly as they are** (read the checkout's
  `.forgejo/pull_request_template.md` and `scripts/check_pr_description.py`; the forms named here were the template's of
  2026-11-13, check them against the file): the lines
  `main: <hash> (<date>)` and `this PR: <branch> @ <hash>`, table column heads `main @ <hash>` and `this PR @ <hash>`,
  the labels `**Tested:**`, `**Not tested:**`, `**Needs other testers:**`, the checklist boxes' own text, and the
  origin line under the last `---` (`Moved from NotRexed/Hookshot#N.` or `New on this forge; not opened on
  GitHub.`). "No at-signs" means no user mentions; it never means rewriting these. The description check reads them
  literally: three bodies failed it on 2026-11-13 because a worker reworded them. Put what you want to add after
  the label, not into it.

- **Collect the evidence while you work**, under `reports/<Topic>-files/`: the environment (system, GPU and driver, base
  and head commit, date, load), the test's lines on the branch and against main's source, the whole suite's totals
  with the named failures, every run's summary line, the log lines that prove the point, a table with one row per run,
  and pictures (before and after, or the feature's screen in each state). A failed check or an outlier is kept and said.
- New or changed C/C++ fixtures, including Python-generated ones: run the Windows-target check from the pr-evidence
  skill's scripts folder (`/home/tonesi/.claude/skills/ls-pr-evidence/scripts/hs-win-fixture-check.sh <worktree>
  <base-revision> --sysroot <llvm-mingw-sysroot>`; the copy in `$H` has no checker beside it)
  through `hs-idle.sh` with the pinned Python. Keep each compiler command, errors and explicit unjudged coverage.
  A syntax pass is not a Windows execution: **Not tested** names the remaining Windows run of the new fixtures.
  Read the head's statuses on the forge and the failed job/test names, not just a green/red count (`ls-pr-evidence`,
  `references/forge.md`); inherited failures and the known
  release-script race remain visible. Never remove or weaken a check to get a green rebase.
- Current main `AGENTS.md` (#2712) requires game evidence before a runtime/performance PR is opened ready for review;
  if the game could not be run, disclose it and keep the PR a draft until someone has. Passing source checks alone
  is not runtime proof. The current windowless restriction is not permission to claim swapchain coverage.
- **The body** (`reports/drafts/<Topic>-body.md`): first paragraph "**What this is for:** ... **What is measured:** ...
  **Not measured:** ..."; then Problem (the chain of causes), What changed (per file, and what is unchanged), How it
  was tested (result lines, tables, pictures with captions), Not tested, Risks, Overlaps
  (the forge route in `ls-pr-evidence`'s `references/forge.md`, hunks read), Questions.
- **Pictures**: several frames as one labelled picture with
  `/home/tonesi/.claude/skills/ls-pr-evidence/scripts/panels.sh`; look at it; name it `ls-<topic>-<what>.jpg`
  and tell the main session, which uploads it.
- **A claim issue only while there is no pull request yet** (the user's word of 2026-11-11, after the maintainer
  closed four of ours as duplicates of their pull requests): search first; say in your hand-off which existing issue
  the work belongs to. If there is none and the pull request can be opened at once, no issue. If the work takes
  longer or needs a decision first, give a draft of one in the form's headings (`reports/drafts/<Topic>-issue.md`)
  with the score and the hardware.
- Hand over the branch with its head, the title file and the body file with no placeholder left, then stop editing them.

## The public repository

This checkout is the user's fork (`toniosim/hookshot-workbench`, public) of the author's `mooki000/ls-workbench`. It holds the
published `ls-*` skills, this brief, the run wrapper and helpers, gates, play drivers, regression and nightly tools, with this
machine's changes on branch `tonesi-machine`. `install.sh` links them into place; the author's `publish.py`, `sync-from-live.sh`,
`relocate.sh` and `cutover.py` are for the author's own live layout and are **not run here** (see the README's "This branch").
The MCP identity is `ls-workbench`, its CLI is `ls-wb`, and workbench configuration uses `LS_WB_*` and `LS_DISCORD_CONFIG`.
External game switches, runtime/source filenames and repository URLs stay unchanged. Only the main session commits and pushes.

- **A skill, this brief and every listed script are public text.** Write in them only what a stranger may read: the
  method, commands, measurements, traps. Nothing about the game's content (coordinates, flag, step and object names,
  routes, what stands where, counts from the world model): that goes into
  `/home/tonesi/Games/.hookshot-harness/playthrough/NOTES.md`. Nothing about where the user's game files and saves
  came from, and no machine name or SSH alias of the user's other PCs: that goes into
  `/home/tonesi/Games/.hookshot-harness/LOCAL-NOTES.md`, whose section "Hosts" gives `<win>` (the Windows laptop) and
  `<relay>` (the LAN relay host) as the skills write them; look there, not in a skill. No key, no address, nothing about
  other people beyond what is on the tracker.
- The world model, the planner, the pilot, the save maker, saves, segment files, reports and drafts are **not**
  published. Do not move any of them into a skill folder or beside the listed scripts.
- When you change a skill or a listed script, say so in your final message, so the main session commits it.

## Reporting

- Every number comes from a log through a script; say for each which build, which settings, which load average. Look
  at every picture you cite and say what it shows. Say what is not measured and what is inferred.
- The final message: the result first, in plain sentences, then what was checked and how, what is not proven, and what
  is needed from the user.
