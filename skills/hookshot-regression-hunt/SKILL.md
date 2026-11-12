---
name: hookshot-regression-hunt
description: >
  Find which merged Hookshot pull request made a build worse: frame times, hitches, startup,
  memory, drawing or a game-free pass/fail check. Use for "which PR caused this", a regression
  against an older build, and a nightly playtest's confirmed regression. Show the difference
  first, test named suspects by revert, then bisect using compatible lifted-input groups.
---

# Finding a Hookshot regression

Read `hookshot-workbench` first, then `hookshot-perf-compare` for timings and
`hookshot-pr-evidence` before drafting a tracker comment. The machine's current agent brief
and the caller's permission override old examples in any skill. Never push or post as a worker.

## Prove the difference before looking for a culprit

1. Pin the actual good and bad **commits**, binary checksums, build flags and release profile.
   Fetch and record the bad head once. A folder called main need not contain today's main.
   Read earlier lane reports: two settings on one build are not an old/new comparison.
2. Use an owned reflink copy, never the player's live game or another lane's mutable copy.
   Record options and the complete environment. Assert that `mods/` is absent and `HOS_MODS`
   unset for an unmodified comparison; record any mods log line. Empty environment files
   prevent a saved experiment or a randomizer seed silently changing the test.
3. Keep scene, input, output size, cap, upscaler and caches equal. Save/route details belong
   in **local scenario files**, not this public skill or its scripts. Prepared and first-visit
   caches answer different questions; preserve and label their states.
4. Compare in turn, A B A B, inside one authorized quiet GPU hold. Record every run, load
   before/after and during it, device, kernel counts and any interference. Reject disturbed
   runs; never rescue one by selecting a favorable part of it. Start/load timing and memory
   need a controlled comparison too. No speed claim from an ordinary shared-card run.
5. Use the same instrument. Older builds may lack headless `RX_VK_FRAME_LOG`; #2354 added it.
   A small identical local logging patch is preferable to comparing unlike clocks. Headless
   frame intervals are CPU intervals after the offscreen copy, **not scanout**. Use an authorized
   windowed pair when the suspected wait could depend on a swapchain. Follow the window switch,
   focus and desktop-disturbance rules; do not operate the compositor yourself.
6. Count the population, not just slow examples. `RX_VK_LOG_READBACK_WAITS` logs a limited
   subset of waited calls. The aggregate `readbacks of GPU results` denominator and what
   "waited" means changed with #2125. For readbacks/frame and per-call duration, record all
   eligible calls the same way on both builds, with frame IDs and separate catch-up/wait time.
   `RX_VK_LOG_READ_TEXELS` describes texture reads, not every buffer readback. `HOS_CHAIN`
   explains the CPU critical path but was not present in all older builds.
7. Set the decision bands from repeated clean endpoint runs. Their ranges must not overlap.
   Pick the clearest measure; a single 1%-low outlier is not a stable predicate. For a
   lower-is-worse measure, negate it before choosing good/bad bands. An ambiguous result
   needs a complete paired rerun, not a guess.

## Tool and stable nightly interface

Public scripts live in `~/.hookshot-harness/regress` beneath the local game's harness root
(on this workbench: `~/Games/.hookshot-harness/regress/`). They contain no saves, routes,
addresses or data derived from the game. Python uses only its standard library.

```
python3 -I regress.py plan --repo REPO --good GOOD --bad BAD --output NEW_DIR
python3 -I regress.py hunt --repo REPO --good GOOD --bad BAD \
  --scenario LOCAL_JSON --output NEW_DIR --max-steps 8 --max-wall-seconds 5400 \
  --max-holds AUTHORIZED_COUNT --max-hold-seconds 480 --exclusive-authorized \
  --suspect SHA --suspect OTHER_SHA --suspect SHA,OTHER_SHA
```

`--priority-authorized` additionally uses priority only when the caller actually authorized
it. Never pass either authorization automatically from nightly. `plan` reads Git only.
`hunt` confirms endpoints, tests each named revert (comma-separated = combined revert), then
bisects. `--suspects-only` ends after the revert comparisons. The first-parent range must
contain good. A first-bad result assumes a monotonic predicate: reversions and multiple
regressions can require separate ranges.

The caller supplies finite hold/step/wall limits. One hold is at most 480 seconds, including
termination/evidence reserve, not only the requested game seconds. The tool will not launch
a paired plan that does not fit. Its gate requests are serial; it never changes gate state
or grants itself another hold. The shared gate's ordinary-turn fairness remains in force.
Timing uses an exclusive hold, `game-check` an ordinary GPU hold, `check` no GPU at all.
Do not call the gate again from a held run adapter. Do not use `check` for a GPU program.

### Local scenario schema, version 1

- `schema_version: 1`, `name`, `kind: timing|game-check|check`, `seconds`,
  `repetitions` (at least 2), `max_retries` (default 1), `max_load` (default 8),
  `grace_seconds` (default 25). Four 90-second runs fit an eight-minute hold.
- `measure: {name, direction: higher-worse|lower-worse, good_max, bad_min}` with
  `good_max < bad_min` in worseness units (negate lower-worse raw values), or
  `{name, direction: pass-fail}` where `value=true` means pass. Numeric decisions require
  `kind=timing`. Bands come from evidence, not the example's desired answer.
- `build_command`: an argv list, not a shell command. Substitutions: `{commit}`,
  `{worktree}`, `{output}`, `{lift_key}`, `{donor_worktree}`, `{build_kind}`, `{reverts}`.
  The engine creates the candidate worktree and applies the requested diagnostic reverts;
  the adapter builds it and writes `output/build.json` with `copy`, `commit`, `lift_key`.
- `run_command`: argv with `{copy}`, `{commit}`, `{output}`, `{seconds}`, `{scenario}`.
  It must write `output/result.json`: `value`, `valid` (boolean), `disturbed` (boolean),
  `kernel_errors` (number), `load_before`, `load_after`, `summary`, `evidence` (paths).
  Extra fields survive in the per-step evidence. A missed scene is `valid=false`, not
  a pass. A game failure that is the predicate must be identified by the local validator,
  not confused with a broken harness or driver fault.

Nightly may carry its initial confirmation evidence as extra metadata. The hunt still
confirms both pinned endpoints in one hold. If authorization or clean bands are absent,
nightly writes the scenario and invokes `plan`, then reports the missing prerequisite.

### Supplied adapters

`run_case.py --copy ... --commit ... --output ... --scenario ... --seconds ...` prepares
an isolated user directory, calls the shared `hs-run.sh --inner` **inside the existing gate**,
samples RSS/VRAM/load, records kernel lines and writes the result. Its local `run` object
supplies `user`, `input`, `env`, optional `window`, and measurement `anchor: load|first`,
`from`, `to`, `load_before`, `load_gap_ms`. Optional `validator_command` checks that the
expected scene/state really occurred. Inspect matching screenshots as well; a long present
gap alone is not proof that the intended save loaded. `device_pattern`, `wrapper` and
`window_switch` are configurable. Its frame metrics include mean/median ms, mean/1%-low
fps and frames over 16.7/20/25 ms. Readback fields appear when the local CSV instrument
is present. Sampled memory peaks are not exact process high-water marks.

`build_case.py` accepts the build substitutions above as `--worktree`, `--commit`,
`--output`, `--lift-key`, `--donor-worktree`, `--build-kind`, `--reverts`, plus `--scenario`.
Its local `build` configuration supplies `python`, `cpm`, `game_root`, `profile_dir`,
`romfs`, `exefs`, optional already-accepted `ngx_sdk`, `jobs`, `lift_jobs`, gates/lock,
`donors` (worktree, copy, completion_file, completion_marker), and optional explicit local
`patches`/`extra_files`. Donors are used only after their completion marker and exact lift
key match. `prebuilt` maps an endpoint SHA to a checksum-bearing local build manifest.
It never downloads/accepts an SDK licence or publishes a binary.

Lift keys cover `nx2/` except `build.py`, `third_party/a64-kit`, and the HLE name set:
a host change can change what the lift hooks even when those two directories are equal.
The plan prints the number of distinct lifts **before** building. Fast builds preserve
`RX_RELEASE=1` and the profile at `work/build/hookshot_pieces.prof`, use `nx2/build.py`,
and rebuild host/renderer from the candidate checkout. A different key requires a full
build through the full-build lock and build gate. Unfinished or dirty-input donors are
not reusable. Patch conflicts and build failures stop with a supported range, not a verdict.

## Reading and posting the evidence

- `range.json`: every commit, subject, referenced PR/issue numbers, lift keys and groups.
  Subject numbers can include an issue as well as the squashed PR; check the tracker before
  calling every number a PR.
- `steps.json` and `table.md`: every run in order, including rejected runs, loads and decision.
  An entire pair is retried if a reference drifts or any result is invalid/ambiguous.
- `result.json`: `first_bad`, `inconclusive`, `not_reproduced` or `suspect_explains`, the
  smallest supported remaining range, reasons/budgets and evidence paths. A successful
  revert on bad proves a contribution/interdependence there, not necessarily a unique
  first historical culprit. No rejected run narrows the range.

Read the suspect's diff and latest discussion. A longer correct wait may remove a false
speedup that let the CPU overwrite data while the GPU still used it. Show its cost **and**
what it fixes; never recommend blindly reverting a correctness fix. Inspect pictures at
matching moments, and state how many frames/areas were inspected. Still screenshots do
not prove an intermittent flash is gone. Attribute a warning/memory/startup difference
only after a targeted reversal or narrowed history; a touched-file list is a lead.

Draft a short measured comment on the merged PR or the issue it fixed: hardware/driver,
commits, settings, scene, per-run table and load, exact cost, correctness trade-off, what
was not tested. If the code suggests waiting only for the recording that writes the read
range, cite the relevant lines and mark that as a proposal until it has a game-free test,
a controlled measurement and picture evidence. Public drafts contain no game-derived
files, save data, routes or private paths. The main session checks and posts them.

## Game-free checks

`python3 -I -B test_regress.py` uses made-up histories and temporary Git repositories:
keys/grouping, negative direction, pass/fail, disturbed/ambiguous/reference-drift decisions,
endpoint confirmation and step/hold/wall stop conditions. Use the workbench's no-core/test
gates. These checks do not replace a live comparison or validate a local scenario's route.
