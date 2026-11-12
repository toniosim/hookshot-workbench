# Hookshot nightly playtest

A local, non-posting workflow for the published `nightly` tag and rolling tests of pinned `origin/main`:
full source builds, named game-free checks, private scene definitions, preserved evidence and regression comparisons.

## Current proof and authorization

Source builds, the project game-free suite and tool tests have run; no rolling GPU cycle has run yet.
The protected-play-folder rule stopped the first real suite when that game appeared, and its resumed CPU-only
attempt completed with the named outcomes retained privately. Stand-ins and synthetic measurements are not game proof.

The user has authorized rolling GPU comparisons with the regression investigator's scenes and adapters. Ordinary
catalogue scenarios remain disabled and unrun. The optional timer stays off until explicitly requested; no rolling
watcher or timer is installed or started automatically. Live metric collection, image comparisons, Intel/windowed
nightly scenarios and automatic confirmation paths remain unvalidated by this tool.

## Rolling test of each new main

```sh
H=/home/mooki/Games/.hookshot-harness
P=$(jq -r .python "$H/nightly-local/config.json")
"$P" -I -B "$H/nightly/hs-nightly.py" rolling
"$P" -I -B "$H/nightly/hs-nightly.py" rolling --check
"$P" -I -B "$H/nightly/hs-nightly.py" rolling --watch
```

Manual `rolling` starts one cycle. `--check` starts one only when main moved and three hours have passed since the
previous cycle's start; it is not a read-only status command. `--watch` repeats that check every five minutes as a
managed foreground command for the agent's job runner, not a timer. It stops on a confirmed regression or failure.
An unchanged head writes `unchanged` and spends no build/GPU time. The same lock covers both modes.

One cycle pins a single fetch of main, uses the existing full-build path and lock, records builder/gate-inclusive
times and binary identity, then makes an owned reflink copy. It uses the shared `regress/run_case.py` and private
scenes, not a new benchmark implementation. Any identical opt-in logging aid and accepted local SDK are recorded.

GPU budget: one ordinary preparation hold, one ordinary unmeasured warm-up hold, then up to three exclusive
**non-priority** measuring holds. Every hold is at most eight minutes; compatible cached preparation and warm-ups
share one ordinary hold when they fit. Each scene is new / previous / new / previous. The supplied first reference
is read-only input to an owned, hash-checked reflink; it is never run from the original folder. The report records
actual GPU occupancy per build, including unmeasured work. Warm-up numbers are never counted as measurements.

The shared quiet rule requires other work below three cores on average, no five-second sample above six, and arm
repeats within 5%. Both paired gaps must agree outside the observed repeat spread; the shared classifier confirms
the resulting bands. Tables include frame/CPU/readback/memory statistics, loads and eligibility. Fixed reference
values keep the dates they were measured, not a fiction that they were rerun. A confirmed regression produces a
local handoff to `regress.py` and stops; no hunt, issue or message is started automatically.

The handoff uses per-copy `regress-source.txt` checks rather than one stamp shared by different builds; it requires
the source-aware shared build/run adapters. Every game/save/scene/reference path is in private `rolling.json` and
`rolling-build.json`. Nothing under `nightly-local/rolling/` is publishable. The player-folder stop rule below stays
in force. The optional nightly timer remains disabled.

```sh
"$H/hs-nocore.sh" "$P" -I -B "$H/nightly/test_rolling.py" -v
```

## Run the game-free workflow

```sh
H=/home/mooki/Games/.hookshot-harness
P=$(jq -r .python "$H/nightly-local/config.json")
"$P" -I -B "$H/nightly/hs-nightly.py" run --game-free
```

Continue an interrupted night without rebuilding a completed build or repeating a completed suite:

```sh
"$P" -I -B "$H/nightly/hs-nightly.py" run --night YYYY-MM-DD --resume --game-free
```

The lock prevents overlap. Builds use the workbench's full-build lock and build gate, eight lift workers and
`--no-prepare-shaders`; suites use `hs-idle.sh` and the configured Python with `-I -B`. Nothing bypasses the gates
when an exclusive regression hold is waiting. Completed copies use reflinks; only owned snapshots and raw data
older than the last seven nights are removed. Metrics remain in SQLite. Compiler warnings are suppressed upstream:
no logged warnings does not establish a warning-clean build.

The player always wins. A game whose executable **or working folder** is in the protected play folder blocks work.
A running scenario is asked to quit cleanly, with bounded termination fallback, marked cut short and never used as a
baseline or regression decision. The tool waits for two continuous player-idle minutes before beginning/resuming
its CPU-only work. It never sends input to, stops, or changes the player's game.

## Private configuration and data

Only this directory's individually listed source files and the skill are publishable. Its sibling `nightly-local/`
is private and must never enter a repository or a public sync list. Saves stay in the local library and disposable
run copies; none is copied into a public report or issue draft.

`nightly-local/config.json` supplies these machine-specific values (there are no embedded dump/repository paths):

| Keys | Meaning |
|---|---|
| `repository`, `repo`, `worktree` | Upstream GitHub repository, local clone, owned detached build worktree |
| `python`, `cpm`, `release_cache`, `release_setup` | Existing pinned workbench dependencies and release-profile inputs |
| `romfs`, `exefs` | The tester's own read-only build inputs |
| `build_copy`, `copy_prefix`, `build_jobs` | Owned stable build output, retained-copy prefix, compile worker count |
| `build_gate`, `full_build_lock`, `gate_closed` | Existing workbench gate/lock/guard paths |
| `play_folder`, `drafts`, `long_holds_log` | Protected player folder, private draft destination, existing gate log |
| `min_available_gib`, `min_swap_free_gib`, `max_memory_psi_full`, `quiet_load_max` | Watchdog/quietness policy |
| `known_test_failures` | Explicit existing machine failures; still shown by name, never silently discarded |
| `gpu_scenarios_enabled`, `hunt_game_checks`, `timer_enabled` | Off by default; the current user instruction leaves them off |
| `timer_time` | Optional authorized timer's local calendar time, not an enabled schedule |

`catalogue-template.json` supplies local catalogue-load steps. `scenarios/*.json` names private saves, settings,
steps, bounds and assertions. `raw/`, `reports/`, `baselines/` and `results.sqlite` retain private evidence. The
catalogue is read by name through `hs-save.sh`; the original save files are never played in place.

## Comparisons and evidence

Bands use 3–7 accepted matching-scenario nights: median center, and the larger of the observed maximum deviation
or three robust standard deviations (`1.4826 × MAD`) as half-width. A first game night only seeds the baseline.
Disturbed timing/memory samples do not establish or confirm numerical regressions. An outlier needs exactly one
eligible rerun. Ordinary-queue frame times are diagnostic, not benchmark claims.

Both frame traces stay distinct. Fixed-event images have a blurred-thumbnail perceptual distance with tolerance
learned from prior good images; black/blank/flash candidates require visual review. Missing traces or GPU memory
accounting remain missing. Logs keep warning/error signatures and counts; source logs remain available. No image
should be cited before a person or agent has looked at it.

The report names failures, changed tests, raw evidence, unjudged timings and available commit ranges. Tracker searches
precede local issue-form drafts; nothing is posted. The shared `regress/regress.py` owns bisection and lift grouping.
`hunt.py` supplies a held-control adapter and exact scenario/threshold handoff, capped at eight steps and 90 minutes.
Numeric hunts need separate quiet-hold authorization; the nightly cannot invent it.

Game-free tests:

```sh
"$H/hs-nocore.sh" "$P" -I -B "$H/nightly/test_compare.py" --mutations
"$H/hs-nocore.sh" "$P" -I -B "$H/nightly/test_driver.py" -v
```

## Designed, not built as full scenario families

Exhaustive destination and setting/value sweeps, save-write/load cycles, continuous 30-minute growth runs,
intentional build-load stress, empty-cache stress and simultaneous-game stress. The generic control steps do not
constitute a tested implementation of those complete families. Their bounded-run policy and optional timer command
are described in `hookshot-nightly-playtest`; the timer is disabled and has not been exercised.
