# Rules for every agent working on Hookshot on this machine (tailored 2026-11-11 for toniosim's PC)

Adapted from the workbench author's brief (`git show main:docs/agent-brief.md` in this checkout has the original, written
for an Arch + Hyprland + RTX 4090 + 96 GB machine shared by many agents). This copy is for one user working with one
coding agent at a time.

## First: choose and use the skill

Before investigating, building, testing or drafting, read `~/.agents/skills/hookshot-workbench/SKILL.md`, then
the matching skills below. Use their existing tools rather than inventing another runner or parser.

| Task kind | Skill (`~/.agents/skills/<name>/SKILL.md`) | Tool to use |
|---|---|---|
| Any Hookshot work; build/run/check | `hookshot-workbench` | `tools/deps-local.sh`, build slot, `hs-run.sh`, `hs-idle.sh` |
| Issue survey, reproduction, reply | `hookshot-issue-triage` | `gh issue view --comments`; read attachments and `POSTED.md` |
| PR/review/rebase/CI or tracker draft | `hookshot-pr-evidence` | `pr_overlap.py`, `hs-pr-ci.sh`, `hs-win-fixture-check.sh`, `hs-pr-check.sh` |
| FPS, frame-time, stutter comparison | `hookshot-perf-compare` + `hookshot-regression-hunt` | `regress.py` held worker and `run_case.py`; A B A B in an authorized exclusive hold |
| Regression, suspect/revert/bisect | `hookshot-regression-hunt` | `regress.py plan`, then authorized `hunt` |
| Controller-free play, state, saves | `hookshot-scripted-play` | `scripts/hookshot_ctl.py`, `playthrough/hsap.py` (capability-selected) |
| Nightly/rolling main testing | `hookshot-nightly-playtest` | existing `nightly/hs-nightly.py` watch; never create a second one |
| Team updates / Discord reads or named messages | `hookshot-discord-updates` | project's `scripts/team_chat.py` in `main-tools`; Main alone posts |
| Testing other people's PRs / request queue | `hookshot-pr-loop` | priority list; `scripts/test_requests.py` in `main-tools`; Main alone claims/renews/completes |

Every report has a **Skills and tools** section: names read, tools actually used, and exact file/line corrections
for missing or stale guidance. A missing skill declaration means usage is unrecorded, not proof it was ignored.
Read `MORNING.md`, the last 150 lines of `LOG.md`, and `POSTED.md` before describing thread work. A result is a
**finding** only after the whole thread it belongs to has been read and compared with what is already known.

**Current desktop restriction (2026-11-12): every game run is windowless.** Yesterday's window allowance is
withdrawn, even if `window-ok` remains on disk. A swapchain-only question is untested here until the user grants it again.

## The project and who we work for

- **Hookshot** (`NotRexed/Hookshot`, GPL-3.0-or-later): a static recompilation of the Switch 2 remake of *The Legend of
  Zelda: Ocarina of Time* for Windows and Linux. The user (GitHub `toniosim`, fork `toniosim/Hookshot`) contributes to
  it and tests it on Linux.
- **This machine:** Pop!_OS 24.04 LTS, COSMIC desktop (Wayland, `cosmic-comp`), Intel Core i7-12700K (8P+4E, 20
  threads) with its Intel UHD 770 (enabled, Vulkan device 1, Mesa), NVIDIA GeForce RTX 3070 Ti 8 GB (driver 595.104.02,
  Vulkan device 0) which also drives the desktop (~0.9 GB of it in use), 16 GB DDR5 (15.7 GB usable) and 19 GB swap.
  ImageMagick 6 (`convert`, `identify`, `montage`; no `magick`), crash reports through apport (`/var/crash`), no
  `coredumpctl`.

## Read before anything else

In the clone `/home/tonesi/Hookshot`: `docs/workflow.md`, `AGENTS.md`, `CONTRIBUTING.md`, then `docs/development.md` and
`docs/design.md`. Their rules bind you as they bind everyone. The ones that matter most:

1. **No game files, keys, or anything made from them leave this PC or enter a repository, an issue or a pull request**:
   not the dump, not `work/`, not built games, saves, lifted C, shader dumps. Pictures of the game, videos and
   `hookshot_log.txt` are fine. Game-derived data (flag names, coordinates, routes, logic read from the game's files)
   stays local.
2. **Licence: only code we may license under GPL-3.0-or-later.** Never paste decompiled game code, and never copy code
   from another port of the game.
3. **One topic per pull request; a branch from current `main`; the cause before the fix; a game-free test that fails
   without the change.** Many tests in `tests/` cut functions out of the source by their text: run the whole
   `tests/run_all.py` and update a broken check in the same change. A check is updated, never removed.
4. **Pull request title = a Conventional Commit** (`feat(scope): ...`, `fix(scope): ...`, `perf`, `docs`, `test`, ...).
   The description opens with why the change is needed in one or two plain sentences; then what changed, how it was
   tested (GPU, driver, place in the game, frame rates before and after where speed is claimed), what was not tested,
   and screenshots when the change shows on screen. Link the issue.
5. **AI assistance is recorded** with trailers naming the model that did the work, at the end of each commit message:
   `Assisted-by: Claude Opus 5.5` and `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
6. **Claims**: the project asks for a claim (Discord and/or the issue) before work starts. Agents never post anywhere
   and never push: draft the text, the user posts it.
7. Hardware tiers: a change must not break NVIDIA RTX and AMD RX on Windows and Linux, or the Steam Deck. Say what
   could not be tested here (Windows, AMD, Steam Deck, HDR: the monitor has none unless the user says otherwise).

## This machine's rules

- **Never touch**: `/home/tonesi/Games/Hookshot` (the user's play install: never run, change or write into it; reading
  its log is fine; `Hookshot/work/dump` links into it, so never write through `work/dump` either), `~/.config`,
  `~/Downloads`, global git config, system packages (no apt, no sudo, no `pip install` outside a venv). Never send input
  to or reconfigure the compositor.
- **Paths**: clone `/home/tonesi/Hookshot` (remotes `origin` = NotRexed, `fork` = toniosim); worktrees under
  `/home/tonesi/hookshot-wt/<name>`; reports under `/home/tonesi/hookshot-wt/reports/`; built game copies under
  `/home/tonesi/Games/.hookshot-h-<name>`; harness under `/home/tonesi/Games/.hookshot-harness/` (symlinks into the
  workbench checkout `/home/tonesi/hookshot-workbench`, made by its `install.sh`). The toolchain comes from the
  unpacked v2.1.0 AppImage: `source /home/tonesi/Hookshot/build-linux/dev-env.sh` before any build or test (it puts that
  Python, emsdk's clang, `RX_CPM` and the libraries on the environment).
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
- Use `date` for every timestamp. Never edit a script that is running.

## Git

- Author: commits for Hookshot use the GitHub no-reply address so the private e-mail never becomes public:
  `-c user.name=toniosim -c user.email=10343143+toniosim@users.noreply.github.com` on each commit (never change git
  config). `harness/hs-pr-check.sh <branch>` checks this (`HS_GIT_EMAIL` overrides) along with the base, the trailers,
  no game files and a Conventional Commit title.
- **Agents never push, never open or comment on an issue or pull request, never post to Discord** unless the user asks
  for that one action.

## Pull requests

`skills/hookshot-pr-evidence/SKILL.md` has the form and the checklist (it was written for the original author; its
paths are relocated, its standard applies). In short: collect the evidence while working under
`reports/<Topic>-files/` (system, GPU and driver, base and head commit, the test's lines on the branch and against main,
the whole suite's totals with named failures, every run's summary line, pictures); the body in
`reports/drafts/<Topic>-body.md`; several frames as one labelled picture with `scripts/panels.sh`; overlaps with
`scripts/pr_overlap.py --branch <name>`.

## Reporting

- Every number comes from a log through a script; say for each which build, which settings, which load average. Look
  at every picture you cite and say what it shows. Say what is not measured and what is inferred.
- The final message: the result first, in plain sentences, then what was checked and how, what is not proven, and what
  is needed from the user.
