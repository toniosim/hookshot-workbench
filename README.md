# LS workbench

The tools, test harness and agent skills I use to build, run, test and measure
[HS](https://github.com/NotRexed/Hookshot) and its continuation
[LS](https://git.magicbean.dev/MagicBeanDev/Longshot) on Linux. I'm sharing them so other contributors can
check and reuse the methods. This workbench is separate from both projects and is not endorsed by their maintainers.

**No game files are here:** no dump, no saves, no built game, no assets and no code from the game. The one thing here
that is about the game itself is `docs/oot/`, a map of what its functions do: addresses, working names and
descriptions written by people who studied it; it quotes names the game itself uses (a class, a thread, a file) as
identifiers (see `docs/oot/README.md`, "What may go here"). You need your own legally obtained game and your own LS or
HS build.

I work with coding agents (Claude, and GPT-6 Astra). The `skills/` are the instructions those agents follow on my machine, and most of
the scripts were written by them under those rules, then run and checked here. The commits say so in their trailers.

## What is here

| Folder | What | Start with |
|---|---|---|
| `skills/ls-workbench` | Owned builds, windowless runs, name selection, checks and registered MCP routes | `SKILL.md` |
| `skills/ls-pr-evidence` | The standard for a pull request and for anything posted on the forge: the claim, the overlap search, the evidence to collect while working, the body's form | `SKILL.md`, `references/forge.md`, `scripts/panels.sh` |
| `skills/ls-perf-compare` | Comparing two builds or settings honestly: runs in turn, a quiet machine, per-run tables, what counts as a difference | `SKILL.md` |
| `skills/ls-perf-monitor` | Read sampled CPU/GPU/memory context and `perf.csv`; suspicions and gauge comparisons are not speed verdicts | `SKILL.md` |
| `skills/ls-scripted-play` | Playing without a controller: inputs and state samples through the control bridge, the file driver for older builds, saves at story points | `SKILL.md` |
| `skills/ls-issue-triage` | Reading an issue or someone else's pull request and reproducing it on this hardware | `SKILL.md` |
| `skills/ls-discord-updates` | Guarded coordination reads and checked drafts; the main session posts through the project tool, not routine browser automation | `SKILL.md`, `scripts/discord_tab.mjs` |
| `skills/ls-regression-hunt` | Finding which merged pull request made a build worse: show the difference first with the same measuring code in both builds, test named suspects by revert, then bisect | `SKILL.md` |
| `skills/ls-nightly-playtest` | Building the project's nightly tag from source each night, running its checks, and comparing the result with the nights before; what a first night can and cannot say | `SKILL.md` |
| `skills/ls-pr-loop` | The existing GitHub-backed request queue, ownership, replies and verified evidence carry | `SKILL.md` |
| `skills/ls-function-map` | Look a game function, structure or subsystem up in `docs/oot/` before reading lifted code; how far to trust a row; how to hand back a row for what was worked out | `SKILL.md` |
| `skills/ls-skill-upkeep` | Keeping the skills true: how an agent reports a skill that was wrong, missing or misleading, the mechanical check, when a new skill is worth it, testing a change with a blank worker | `SKILL.md`, `check_skills.py` |
| `skills/ls-field-data` | What players' games sent in: crash reports and performance summaries through the team's Grafana MCP server; how to read them and how to use them in triage, test choice and evidence | `SKILL.md`, `scripts/ls_field.py`, `docs/field-data.md` |
| `skills/ls-hold-chain` | Queued game holds: the quiet-window and measuring locks, one admission for many stages, retargeting a queued waiter, finding your own waiter, waiting from a session | `SKILL.md` |
| `skills/ls-restack` | Moving our own long cherry-picked branch onto a moved main: replay, byte proofs, conflict resolvers, tests before the hold | `SKILL.md` |
| `skills/ls-windows-laptop` | Staging, running, capturing and restoring on the remote Windows laptop: tools, limits, who may use it | `SKILL.md` |
| `skills/ls-relay-lan` | The shared co-op relay on the LAN relay host: room limits, probes, the log, install and update | `SKILL.md` |
| `skills/ls-nat-lab` | Two games or the game-free player behind simulated NATs on this PC with no sudo: the lab's levels, the case table, counters, the before/after of a path-layer change | `SKILL.md`, `references/evidence.md` |
| `harness/` | Run/check helpers, shared runtime-name selection and local commit porting | `hs-run.sh`, `hs_names.py`, `ls-port.py` |
| `gates/` | Queues that let many test runs share one GPU and one CPU without hurting each other or the desktop | `hs-gpu-slot` |
| `play/` | Step drivers that play on a running game (one for the control bridge's state samples, one for older builds with the state file; the driver is chosen explicitly), the pilot that plays a segment of goals with them (a fixed policy or a model; interactions, stuck recovery, human-like movement, eyes, metrics) a benchmark of its arms, a route library and a tactics library the pilot learns from, the nightly self-play and a capability scoreboard (`playbench/`), the game's debug tools from a command line (`hsdebug.py`), a panel and a video of what the pilot decides, interchangeable decision makers (a model, an outside agent over MCP, a recorded replay), bug hunting (scenarios, detectors, repro packets, the hunt), the builders of the offline world model from your own game files (`worldmodel/`) and start points for a test (`bosspoints/`), with their game-free tests | `README.md`, `hsap.py`, `pilot/pilot.py`, `bench/run.py`, `playbench/README.md`, `worldmodel/build.py`, `bosspoints/bosspoints_table.py` |
| `regress/` | The regression hunt's engine and its two adapters (build a candidate, run a scenario), with their game-free tests | `regress.py` |
| `nightly/` | Catalogue/rolling drivers, retained reports and game-free checks; each report names its actual runtime coverage | `hs-nightly.py`, `rolling.py`, `README.md` |
| `perf/` | Optional telemetry CSV reader and game-free contract tests | `hs_perf.py` |
| `mcp/` | Registered tools, CLI and private broker; operator setup is required | `README.md`, `CATALOGUE.md` |
| `docs/agent-brief.md` | The rules every agent on my machine reads first | |
| `docs/oot/` | A map of the game's lifted functions: what each `f_<address>` looked at so far does, its data and structures, and how sure each row is (about 2,000 rows, by dyst, with later additions); beside it a map of the game's flags (every flag of its list by hash, with the recovered name, kind, save file and group, what co-op does with it and what it is) and of the save files' byte layout. Search them before reading lifted code or working out a flag; add what you learn | `README.md`, `fnmap.py`, `flagmap.py`, `flags/README.md`, `save-format.md` |
| `flagdata/` | For your own copy of the game: rebuild the co-op progress classification and the flags' names from your files (reports and a private cache), and annotate a co-op log with them. The tools hold no game data; their published result is the flag map in `docs/oot/flags/` | `README.md`, `flagdata.py`, `coop_log.py`, `docs/oot/flag-names.md` |

### The harness

- **`harness/hs-run.sh <game copy> <tag> <seconds> [options] [NAME=VALUE ...]`**: one unattended run, headless by
  default, through the GPU gate. It leaves everything in `<copy>/runs/<tag>/`: the log, pictures every N presents, the
  frame log, and one summary line (exit, frames, mean and 1% low, slow frames, fatal and device-lost lines, kernel
  driver lines, the load before and after). `--intel` selects the integrated GPU, `--input` plays a press script,
  `--user` copies a disposable save, and `--perf` requests optional sampled context. A new explicit grant is needed
  for the existing `--window` mechanism; a leftover switch file is not permission.
  The wrapper returns 0 once reporting succeeds, even when the game failed: read `exit.txt` or `exit=` in the
  summary for the game's status (124 means the wall-time limit). Summary generation or final-write failures
  return nonzero instead. A failed final `tee` preserves its status and skips `runs.log`; a failed log append
  keeps the written summary and game receipt.
- **`harness/hs-idle.sh <command>`**: runs the game-free checks (`tests/run_all.py`) in the idle scheduling class, three
  at a time, never beside a timing run, and with core dumps switched off.
- **`harness/hs-nocore.sh <command>`**: runs one command with core dumps off. HS's checks crash three fixture
  programs on purpose; on a desktop with a crash notifier each one raised a notification.
- **`skills/ls-pr-evidence/scripts/panels.sh <out.jpg> <per row> <frame> "<caption>" ...`**: several frames as
  one labelled picture for a pull request.
- **`harness/hs-watch-threads.py [numbers]`**: waits until someone comments on, reviews, merges or closes one of your
  threads, then prints what is new.
- **`harness/hs-window.py`**: the compositor's side of a windowed run on Hyprland (a window that never takes focus).
- **`harness/hs-save.sh <name> <folder>`**: copies a save from a local library into a throwaway user folder for one
  run. The library is not here: saves are game data.
- **`harness/deps-local.sh <worktree>`**: fetches what a source build needs on Arch into one folder, from the pins of
  HS's own `scripts/linux/deps.sh`, without touching the system.
- **`harness/hs-names.sh` / `hs_names.py`**: select executable, log, profile and source-verified build variables from
  a checkout/copy, refusing missing or mixed identity. External runtime names and existing harness paths stay unchanged.
  Runtime naming does not port GitHub release/CI/request backends to Forgejo or migrate credentials.

### The gates

One GPU that is also the desktop, thirty-two threads, and many test runs at once: without a queue, two games ran the
card out of memory and took the desktop down. The gates are small shell scripts around lock files:

- **`gates/hs-gpu-slot <command>`**: one or two games on the card at a time, served in the order they asked;
  `--priority` for a single short run, `--exclusive` for a frame-rate measurement that needs the machine quiet. It
  checks free card memory and system memory before it lets a second game in.
- **`gates/hs-intel-slot <command>`**: one run at a time on the integrated GPU.
- **`gates/hs-build-slot <command>`**: four builds at a time in the idle scheduling class.
- **`gates/gpu-guard.sh`**: watches the kernel log; at a driver fault line it ends every test run and closes the gate.
  It also ends anything of the harness that uses the card outside the gate. The gates start it with each run, and it
  ends by itself after 15 minutes with no slot held.


### Playing without a controller

`play/hsap.py` runs one game through `hs-run.sh` and plays steps on it through the control bridge (`HOS_CONTROL`):
inputs as the bridge's own commands, and Link's place, facing and state from the state samples that
[HS #2292](https://github.com/NotRexed/Hookshot/pull/2292) adds to it (`status.game`, and `subscribe` with
`events:["oot"]`; `game.frame` dates a sample). `walk <x> <z>` steers to a point and says whether it arrived, got
stuck or was held by a scene. Main's control bridge alone is not enough: the build must have that subscription, and
the driver says so in one sentence when it does not.

Older builds with the state file (`HOS_OOT_STATE_FILE`) need `play/hsap_file.py`, the earlier driver kept as it was.
There is no silent fallback from one to the other. `play/tapcheck.py` puts a run's samples beside its pictures;
`play/test_hsap.py` and `play/test_hsap_file.py` test the two drivers without a game.

On top of `hsap.py` sits the pilot, `play/pilot/pilot.py`: it plays one segment (goals with targets, written by you from your own
game) by choosing, whenever the driver has no step left, among candidate steps: with a fixed policy (`rules`, no model, no
network) or with a model that picks among them (`openai-decisions`, key and spending caps yours). It opens chests, picks up
items, talks, goes through doors, plays the ocarina and fights, proves each only by the game's own evidence (a flag, a count, a map
change), recovers from being stuck, moves with seeded human-like variation, and can look at the game's own picture; `play/bench/`
plays a fixed course of short cells with each arm and tabulates cost and quality. What earlier runs learned (where Link can walk, what got
him out of a stuck place) is kept in private libraries (`routelib.py`, `tactics.py`) and reaches the next run as a better route, a better order of
the ladder and a few lessons in a planner's request; `selfplay.py` and the scoreboard in `play/playbench/` run that against a fixed set of cells.
`play/README.md` says how to run it, what it
sends where, and what you must supply and keep private (segments, saves, routes, the tables the world-model builders read, the world model they make, run output, the key).
The offline world model is built from your own game files by `play/worldmodel/` (code only: the names it needs come from a tables file you write); build it first, then the pilot
plans with it.

### Finding a regression

`regress/regress.py plan` reads a commit range and lists it with the pull request numbers and the groups of commits
that can share one long build step. `regress.py hunt` confirms the good and the bad end in one quiet hold (old, new,
old, new), tests named suspects by reverting them, then bisects. It stops at the number of holds, steps and minutes it
was given, and what it then reports is the smallest range the clean runs support, not a guess. The scene, the save and
the bands that count as good and bad come from a scenario file that stays on the machine: none is here.
`regress/build_case.py` and `regress/run_case.py` are the adapters for this workbench's build and run wrappers;
`regress/test_regress.py` tests the engine on made-up histories without a game. First published as written, before a
whole hunt had run through it on the game.

### A nightly build and its checks

`nightly/hs-nightly.py run --game-free` builds the project's `nightly` tag from source, runs its game-free checks and
compares the named results with the night before. The comparison's rules (a band from the last three to seven good
nights, a disturbed run never feeding a timing baseline, one confirming rerun before anything is called a regression)
are tested on made-up numbers by `nightly/test_compare.py`. The part that plays scenarios on the game, collects frame
times, memory, log lines and pictures, and hands a confirmed regression to `regress/` is written and tested against
stand-ins only: it has never run on the game. It stops, and counts nothing, whenever a game is started from the
player's own folder. Saves, scenarios and results stay on the machine.

### A rolling test of each new main

`nightly/hs-nightly.py rolling` pins a head, builds it, warms the configured scenes, then measures
new / previous / new / previous with the shared regression worker and quiet rule. It writes a handoff and stops
on a confirmed regression; it starts no hunt or timer and posts nothing. Automatic checks require a moved head
and three hours, or the six-hour fresh-build deadline even on an unchanged head. The player's-folder rule governs
the whole cycle. Read the retained cycle report for what actually ran; offline checks are not gameplay or timing proof.

## What is not here, and why

- **Anything made from the game**: saves, the world model my planner builds from my own dump (areas, links, event
  flows), the tables of the game's names and coordinates that the builders and the start-point tools read, and scripts that carry
  lists read out of the game's files. The builders, the planner and the pilot are here as code (`play/worldmodel/`, `play/pilot/`);
  what they make, and the tables that tell them what the game calls things, are yours to make from your own copy. The save maker
  follows once I have separated its code from the item and story lists it carries.
- **My working notes**: the reports, drafts and logs the skills mention under `reports/`. The skills name those paths
  because that is where an agent on my machine writes; you would use your own.

## Using it on another machine

### This branch (`tonesi-machine`): Pop!_OS 24.04, COSMIC, RTX 3070 Ti 8 GB, i7-12700K, 16 GB

Tailored on 2026-11-11 from the author's `main`. What changed, and why:

| Where | Change | Why |
|---|---|---|
| everywhere | `/home/mooki` -> `/home/tonesi`; clone `~/Hookshot`, worktrees and reports `~/hookshot-wt/`; skills at `~/.claude/skills/ls-*` (not `~/.agents/skills/hookshot-*`); Tooling at `~/Tooling` | this machine's layout. The author's `relocate.sh` only swaps the home, so it is not used: it would leave `Code/` and `.agents/` in |
| `gates/hs-gpu-slot` | one game at a time whatever `gpu-slots` says; a game starts only with 6 GB available and calm memory pressure; "drained" below 2 GB, not 5 | 8 GB card that also drives the desktop; 16 GB of RAM, of which a game reserves ~9.8 GB |
| `gates/*-slot` | desktop check accepts `cosmic-comp` (Hyprland's safe-mode check kept) | COSMIC, not Hyprland |
| `gates/hs-build-slot`, `harness/hs-idle.sh` | one build slot (was four), `HOOKSHOT_LIFT_JOBS=2` by default; one run of the checks (was three) | 16 GB of RAM |
| `harness/hs-run.sh` | expects the RTX 3070 Ti; ImageMagick 6 fallback; `--window` on COSMIC opens an unmanaged window (no rules, no watcher); `--intel` gets `--mem-max 9G` unless given | no Hyprland rules interface; Intel's driver used 23-28 GB preparing shaders |
| skills, `hs-watch-threads.py`, `nightly/report.py` | identity: `tonesi <tonesi@noreply.git.magicbean.dev>` on the forge, toniosim's GitHub no-reply address for legacy | the author's identity. `hs-pr-check.sh` and `pr_overlap.py` are gone upstream (the forge route replaced them) |
| `regress/`, `nightly/build.py` | device 3070 Ti, lift workers 2, jobs 12 | as above |
| `skills/ls-pr-evidence/scripts/panels.sh`, `references/recipes.md` | works without `magick` | ImageMagick 6 |
| `docs/agent-brief.md`, `skills/ls-workbench/SKILL.md` | rewritten / annotated for this machine and the AppImage toolchain (`~/Hookshot/build-linux/dev-env.sh`) | |
| `skills/ls-pr-loop/` | its paths, GitHub login, hardware profile (RTX 3070 Ti 8 GiB, i7-12700K, Mesa 26.1.6) and the tests' hardware cases | this machine; it needs a read-only `~/hookshot-wt/main-tools` worktree of current main (`git -C ~/Hookshot worktree add --detach ~/hookshot-wt/main-tools origin/main`) |
| `tools/magick6`, `tools/names_keep_local.py` (new) | `magick` for ImageMagick 6 (linked to `~/.local/bin/magick` by `install.sh` while no real one exists); the author's counted names policy lists this branch's own HS/LS literals instead of failing (`python3 -I -B tools/names_keep_local.py` after a merge) | the author's `play/` and `regress/` call `magick`; the policy keeps the published repository free of old names, this branch writes them on purpose |
| `install.sh` (new) | symlinks the harness, gates, guard and skills (all but the Discord one) into place; `--check`; removes links to the pre-rename `hookshot-*` skills and to files upstream dropped | |
| 2026-11-12: Longshot | rebased onto the author's name-table `main` (backup branch `backup-tonesi-machine-2`); `hs-pr-check.sh` compares with remote `forge` (Longshot; `HS_UPSTREAM=origin` for legacy Hookshot); `longshot-port.py` commits as toniosim; skills say where PRs live now (`scripts/forge.py` on git.magicbean.dev) and use `~/hookshot-wt/deps/{python,cpm}`, which link to the AppImage toolchain; tests expect lift workers 2 and the 3070 Ti; `install.sh` links `perf/` | development moved to git.magicbean.dev/MagicBeanDev/Longshot; `main-tools` now follows `forge/main` |
| 2026-11-13: `skills/ls-testing-loop/` (new; was `hookshot-testing-loop` until upstream's rename) | unattended testing of approved Longshot test requests while the PC is free (overnight or by day): the quick pass before they leave, picking, the worker brief, the check before posting, posting with pictures (`forge.py pr comment --attach`, Longshot PR 254), an hourly check (`check-prompt.md`, `scripts/requests_digest.py`) | the first night (PR 95) worked; this makes it repeatable |

| 2026-11-18: merge of the author's `main` (04ecad3, 18 Nov) | merged, not rebased (the author's `hookshot-*` -> `ls-*` skill rename touched every file this branch had edited). Taken as is: the new skills (`ls-field-data`, `ls-function-map`, `ls-hold-chain`, `ls-restack`, `ls-nat-lab`, `ls-pr-tagging`, `ls-relay-lan`, `ls-windows-laptop`, `ls-skill-upkeep`), the MCP debug tools, `docs/oot/` maps, nightly/harness fixes, `play/` and `pilot/`. Kept from this branch: gates, the 3070 Ti / 16 GB changes, COSMIC, identity, the AppImage toolchain block in `ls-workbench`, a rewritten brief, `ls-testing-loop`. Not used here: `publish.py`, `sync-from-live.sh`, `relocate.sh`, `cutover.py` (the author's own live-layout tools; the harness stays at `~/Games/.hookshot-harness`, which `cutover.py` would move to `.ls-harness`). | stay current with the author without losing this machine's changes |

The author's numbers quoted in the skills (build times, loads, memory) are from their machine: measure here.

### The original notes

Everything was written for one machine: Arch Linux, Hyprland, an RTX 4090 on NVIDIA's driver with an Intel UHD 770
beside it, and these places:

| Path | What |
|---|---|
| `/home/mooki/Code/Hookshot` | the clone (`origin` = NotRexed, `fork` = mine) |
| `/home/mooki/Code/hookshot-wt/<name>` | worktrees, one per branch |
| `/home/mooki/Code/hookshot-wt/deps` | Python and headers from `deps-local.sh` |
| `/home/mooki/Games/.hookshot-h-<name>` | built game copies for test runs |
| `/home/mooki/Games/.hookshot-harness/` | `harness/` lives here |
| `/home/mooki/Games/` | `gates/hs-*-slot` live here |
| `/home/mooki/.agents/skills/` | existing live `hookshot-*` folders; publication maps to `skills/ls-*` |
| `/tmp/hs-gpu-slots/` | the GPU gate's queue and state |

`./relocate.sh /home/you` rewrites the example home in checkout text and its name exceptions, not live files,
private/cache directories, linked files or the publication entry scripts. Paths containing spaces or `&` are literal.
The GPU gate's numbers (how much card and system memory a game needs) are for a 24 GB card and 96 GB of RAM: read the top of `gates/hs-gpu-slot`
before you rely on them. `hs-window.py` speaks to Hyprland only.

The skills are plain Markdown with a short header. Agent tools that read `~/.agents/skills/<name>/SKILL.md` (or
Claude Code's `~/.claude/skills/`) pick them up as they are; a person can read them as the manual.

Starting on a Mac: [docs/handoff-macos.md](docs/handoff-macos.md) is the hand-over for an agent there (what LS needs
for macOS, which parts of this workbench carry over, and what to ask me for).

### Published identity and deferred host cutover

The published workbench identity is `ls-workbench` (LS in prose); its MCP CLI is `ls-wb` and its configuration
variables use `LS_WB_*`. The Discord helper's override is `LS_DISCORD_CONFIG`; the fixture compiler override is
`LS_MINGW`. These are workbench names, not game switches. The published skills above use `ls-<suffix>` in
their directory and frontmatter `name`, with logical references such as `skill://ls-workbench`.

Publication maps ten existing live `~/.agents/skills/hookshot-<suffix>/` folders to `skills/ls-<suffix>/`;
`ls-function-map`, `ls-skill-upkeep`, `ls-field-data`, `ls-pr-tagging`, `ls-hold-chain`, `ls-restack`, `ls-windows-laptop`, `ls-relay-lan` and `ls-nat-lab` are identity entries: their live and published names are already the same.
The live folders have **not** been renamed: absolute and home-relative `.agents/skills/hookshot-*` command paths
remain intentional until a separately authorized host cutover. This repository change does not run publication,
sync, relocation or cutover, install the renamed MCP entry point, or change live configuration.
The main session owns those later operations.

Keep existing repository URLs, clone/worktree paths, `.hookshot-harness` paths, gates and `hs-*` helper filenames.
Game executables, libraries, logs, profiles, source filenames, build variables and protocol/telemetry names retain
the exact selected runtime's spelling. `harness/ls-port.py` and `harness/test_ls_port.py` are workbench filenames;
`nightly/test_runtime_names.py` and `regress/test_runtime_names.py` cover runtime selection, whose shared module
remains `hs_names.py`.

### Publication and the later host move

`sync-from-live.sh` uses the explicit source/destination tables and tested `skill_references()` function in
`publish.py`. It reads the current installed folders, preserves runtime names and physical live skill paths,
and rewrites logical skill names on the way into `skills/ls-*`. Identity entries are copied and checked like the
other skills, but never removed as legacy folders or scheduled for a same-path host rename.
Source comments/docstrings use LS/HS while runtime string values remain literal. The local compiler-input helper and its renamed test reuse their reviewed LS
definitions so publication and host cutover select the same new override. Only allowlisted tools and source/document
skill extensions are copied; unreviewed file types and links refuse. It never touches MCP files, live sources,
saves or game data. `--check` compares without writing. `LS_WB_SOURCE_ROOT` selects an isolated source tree
(`harness/`, `skills/`, `gates/`, `docs/agent-brief.md`); the harness subtree has the installed subfolder layout.
Individual source overrides are `LS_WB_HARNESS`, `LS_WB_SKILLS`, `LS_WB_GATES`, `LS_WB_GUARD` and `LS_WB_BRIEF`.
The proposed tree is staged and its [counted name policy](docs/names-kept.md) checked **before any checkout file is
replaced or removed**; a names-check failure leaves existing files unchanged. The existing publication guard still runs afterwards.
Review the diff and run the game-free suites before committing. A newly introduced external literal needs a
reviewed, file-scoped entry, never a blanket exception.

`python3 -I -B cutover.py --dry-run` prints every planned rename, rewritten file and `git worktree repair`.
It writes nothing, including locks. `--apply` is a separate, later operator action: first integrate this
publication into the main checkout and stop every worker. It renames the ten live skill folders, the harness
and the workbench checkout, updates the selected source files and path constants (including sync's installed
layout), then repairs Git worktrees. Both existing admission locks must have **no holders or waiters**; apply
takes them nonblockingly and conservatively treats matching lock inodes on any device as busy. Missing sources, existing destinations, links and stale
plans refuse; failure during mutation rolls the changes back. It never moves the port clone, worktree parent,
player folders, coordination locks or private MCP state; credentials and services are neither migrated nor
restarted. Reconcile private registrations and restart the renamed MCP entry points separately. The script
does not grant permission to run it on a busy workstation.


## How the results I post are made

When I post a number on an LS or HS issue or pull request, it comes from here: a run through `hs-run.sh`, its summary
line and log, a script that makes the table, and a picture I looked at. `skills/ls-pr-evidence/SKILL.md` is the
standard I hold those posts to: what was measured, on what, what was not, and what failed.

## Licence

MIT, see `LICENSE`. HS itself is GPL-3.0-or-later and lives in its own repository.
