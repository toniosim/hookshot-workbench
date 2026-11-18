---
name: ls-perf-compare
description: >
  Compare LS or HS builds or settings for frame time, fps, 1% low and stutter. Distinguish ordinary memory/log/image
  observations from authorized exclusive timing. Read ls-workbench and ls-regression-hunt; use the shared
  regression worker and registered evidence adapters, never a second timing runner.
---

# Comparing LS builds or settings

**LS / HS:** use the workbench's shared name selection; preserve live harness/gate paths. Published skill IDs use
`ls-*` and workbench configuration uses `LS_WB_*`; host cutover is separate (see `ls-workbench`).
Require the actual donor/profile/cache identity and optional instrumentation. Name compatibility
does not add a perf emitter or make GitHub request/CI tools Forgejo-aware.

**Use for:** every speed claim or “is this switch/PR faster?”. Read `ls-workbench`, `ls-regression-hunt`
and the current agent brief. All runs are windowless; swapchain, V-Sync, display latency and generated-frame output
remain untested without a new explicit grant. Reports name skills, tools, sources and actual verification.
For sampled CPU/GPU/memory or stutter context, read `ls-perf-monitor`; retain same-run perf/frame CSVs,
explicit clocks/windows, missing counters and suspicion evidence. Gauge comparisons are not causation, statistical
significance or a speed verdict; the authorized paired worker remains the timing authority.
To choose where to measure, the field (`skill://ls-field-data`: `perf --by map`, `perf --by gpu`, `perf --by version`)
shows where players lose frames. It is a lead for the scene and the cards, never a measurement or a verdict; quote its
sessions and hours (below about ten sessions it is an anecdote).

```sh
H="$HOME/Games/.hookshot-harness"
P="$HOME/hookshot-wt/deps/python/bin/python3"
```

## 1. Pin a question and plan without running a game

1. Read the whole current thread, description and posted-work record. A moved head may be parked, not a request
   for testing. A repeat of an established result is not a new finding.
2. Pin both commits, binary hashes, source stamps, release/profile identity, settings and cache state. A switch
   comparison on one build is not an old/new build comparison. Use owned copies without mods or hidden options.
3. Keep the same local save, input, scene, cap, output size and upscaler. Keep game data in local scenario files.
   A scripted real-time walk can end in different places depending on timing, which changes how many shader programs
   are first used and the frame rate: compare route-matched pairs and report every run's end position.
   `HOS_FPS_MAX` accepts 61–1000 in the selected base; 1000 is its Uncapped value, not a promise of achieved speed.
   Verify the selected build's accepted range before changing it.
4. Plan with a **new** output directory; this reads Git and writes the plan, but starts no game or build:

   ```sh
   "$P" -I -B "$H/regress/regress.py" plan --repo "$REPO" --good "$GOOD" --bad "$BAD" --output "$PLAN_OUT"
   ```

   Inspect `range.json`. `distinct_lifts` is conservative compatibility grouping, not a count of required builds.
   For several switches or scenes use the regression skill's explicit `_hold` plan, not a new runner.
5. Check the timing scenario before requesting a hold. It needs `schema_version:1`, `kind:"timing"`, explicit
   build/run argv lists and a decision measure. Quiet defaults are mean other-work **below 3 cores**, peak other-work
   **at most 6 cores** over five-second samples, and same-arm repeat spread at most 5%. Load average is context,
   not the quiet test. Set the decision bands before collecting results.

**A co-op room** whose other games are part of the experiment has no wording in the quiet rule: apply it to everything
except the room's games, write that sentence in the result and report their cores beside it (one game at the 60 fps cap
uses about 2.6 to 3.0 cores). One 24 GB card holds two real games under the runner's stock rule (a game that starts
while another runs needs 12,288 MiB free, `admit_second` in `cpsession.py`; two games leave about 9.6 GiB). A third needs
the fork key `run.late_gpu_free_mib`; the game-free headroom analysis predicts four fit only with `RX_VK_VRAM_MB=500`
each and the guard `run.gpu_guard_free_mib`: `reports/CoopScale-files/headroom/headroom.py` is the method,
`reports/CoopScale-files/coop-play4/` the fork, `reports/CoopScale.md` says whether a four-game run exists.
Two games on one card with the default texture budget stalled together for 3 to 11 s and lost a test kit; the pair holds of
the PvP nights ran with `RX_VK_VRAM_MB=5500` in both games' environment (`reports/PvpNight-files/night_queue.py` sets it
unless the caller did) and had no unplanned stall.

Game-free reader check:

```sh
"$H/hs-nocore.sh" "$P" -I -B "$H/regress/test_regress.py"
```

It tests synthetic histories, held workers and fake adapters. It does not warm a scene or establish a hardware result.

## 2. Take only the authorized paired hold

1. Warm each scene/mode once without measuring, through ordinary bounded gated runs. Preserve the resulting cache
   state on both arms. Frame-clock input counts 60 game presents per script second, not wall time; verify loading,
   control and scene in fresh state and inspected pictures rather than a fixed delay.
2. Obtain the main session's authorization for the **named count of exclusive holds**. Only then:

   ```sh
   unset HSGATE_SLOT_DIR HSGATE_INTEL_SLOT_DIR HSGATE_SLOT_TEST HSGATE_SLOT_NODESKTOP HSGATE_IN_GATE HSGATE_IN_INTEL_GATE
   "$P" -I -B "$H/regress/regress.py" hunt --repo "$REPO" --good "$GOOD" --bad "$BAD" \
     --scenario "$SCENARIO" --output "$HUNT_OUT" --max-holds "$HOLDS" --exclusive-authorized
   ```

   `HUNT_OUT` must be new and distinct from `PLAN_OUT`. The scenario and budgets are operator-owned. Do not add
   `--priority-authorized` without a separate grant. Do not raise a budget to rescue an inconclusive result.
3. Keep reference/candidate/reference/candidate in one exclusive hold. The maximum is 480 seconds including the
   worker's reserve, shutdown and settling. The fit check is
   `2 * repetitions * (seconds + grace_seconds) + 10 <= max_hold_seconds`; the default grace is 25 seconds.
   Do not describe the planned duration as actual queue or occupancy time; preserve both receipts separately.
4. Keep one waiter, never withdraw/requeue to jump it, and do no analysis or other work beside your own timing hold.
   Never nest the GPU exclusive gate inside the Intel gate. A periodic desktop job is not ours to stop: a reviewed
   plan's `window` and `avoid` fields can avoid an observed disturbance without changing the desktop. The known one is
   the desktop's usage widget (`omarchy-agent-usage-update`: about 37 `rg` searches on 15 to 30 cores for 3 to 5 s,
   starting 56 to 58 s into minutes :08, :23, :38 and :53 of every hour): `{"every": 900, "at": 535, "for": 12}` in
   `avoid` covers it (`at` counts seconds into each quarter hour of the wall clock; see `avoid_delay` in `regress.py`).
5. Retain every invalid/disturbed row. Require the adapter's validity/quiet verdict and both same-arm repeats within
   tolerance. A successful input, normal wrapper exit or low load average is not timing validity.

Ordinary gated runs establish counts, pictures, start/finish and memory observations only. Label them **ordinary run,
no speed claim**; do not quote their printed frame rate even as an aside. A memory experiment does not need exclusive
GPU time. The current numeric `hunt` classifier nevertheless requires timing mode; use ordinary collection without
that classifier, not an unnecessary exclusive hold.

A long ordinary run (a soak, a co-op session) meets the same widget: one two-hour soak had nine bursts of frame stalls
up to 2.7 s. List its four bursts an hour as a known disturbance in the result and check whether stalls start at them
before blaming the game or the network. An exclusive hold does not isolate the game from this PC's other unlocked work
either (one two-hour run saw load average 130 and a stall of 8.8 s): put the load average (`pc.load` in every co-op
sampler row, `reports/Soak4-files/sampler/`) beside any frames verdict and date a machine stall from the `total=`
counters of `/proc/pressure/*` (`skill://ls-hold-chain`, "The locks").

## 3. Analyse the same clock and report the paired result

- `RX_VK_FRAME_LOG` is the three-column renderer timing CSV. Headless values are CPU intervals after the offscreen
  copy submission, without swapchain/display waits. `HOS_PRESENT_TRACE` is the game's present clock with its limiter;
  its three- and seven-column forms are not GPU completion or scan-out.
- `RX_VK_FRAMELOG` is the separate pixel stream, still swapchain-only. A still screenshot cannot establish absence
  of a continuous flash. Scan only a real retained capture with eligible consecutive frame triplets; inspect events.
  Two measured windows with the log switched off between them may carry consecutive sequence numbers (one worker read
  this in the code; not tested), and the scanner needs only consecutive numbers for a triplet: scan each window as its own
  file, or cut at a timestamp gap, so the boundary is not taken for three frames.
- `hs-run.sh` uses populated renderer CSV, labelled `headless-renderer` or `swapchain`; empty/missing renderer CSV
  falls back to three- or seven-column present traces, labelled `game`. Read the raw files for older summaries.
  `run_case.py` still requires renderer CSV for its scene window.
- Do not compare windowed and headless instruments, mismatched settings, unmatched scene windows or unlike diagnostic
  populations. The adapter's windowed frame-number alignment does not make the clocks interchangeable.
- The renderer's own timing lines in the game log (`writes collected`, the capture `scan`) have two decimals, a 0.01 ms
  resolution: an A/B of a change under 0.01 ms needs the mean over many lines, not one line a run.
- At a 60 fps cap, `over16.7` includes pacing jitter. The live regression statistics emit mean/median, p99, 1% low,
  maximum and `over16.7`/`over20`/`over25`; **not `over33`**. Derive any extra threshold from the same retained window
  and label the analysis, rather than quoting a nonexistent column. Mean uncapped frame time is steadier than 1% low;
  hitches need repeated windows and their counts. The adapter judges quiet over the selected whole window, not
  automatic 30-second subsegments.
- Use the shared paired classifier. Report the gap and same-arm spread, not only averages. A non-overlapping clean
  result can support a claim; ambiguous, drifted or disturbed pairs cannot. Preserve rejected evidence and reasons.
- Conditional readback “waited” averages change population when code changes the wait classes. For per-frame cost,
  instrument all calls the same way on both builds and keep their window/present numbers.
- Short startup RSS slopes do not prove a leak. Linux `RssAnon` is not Windows private commit, and device-wide GPU
  memory is not the process's allocation. The live adapter's `rss_parts_mb` uses its final sample, possibly after
  exit; use the last **live** raw sample for composition, not as the high-water composition.
- Apply the brief's kernel signature policy, not `nvrm > 0`. Retain `kernel.txt` and the journal exit/stderr receipt.
  Failed or partial journal reads produce unknown coverage, not zero; the hunt stops instead of retrying it.
  Repeated markers inherit their preceding message; only the named same-second allocation triple is exempt.

For profiles, preserve raw stacks and matching-copy ELF symbols. `scripts/prof.py` retains argument lists but its
`waiting()` checks bare suffixes; `scripts/vkprof.py` omits `libnvidia-eglcore`. Label any corrected local classification.
`scripts/cpu_report.py` rejects Linux captures. Do not quote those readers' uncorrected wait/vendor shares as fact.

## MCP routes

Use the workbench skill's catalogue, configuration and Job-receipt rules. MCP evidence analysis consumes registered
artifacts; it does not turn an ordinary run into exclusive timing. There is **no regression hunt/held-worker MCP tool**.
After the operator setup linked in `ls-workbench`, use `uv run --project mcp ls-wb call TOOL --args JSON` from the
reviewed repository root. Read Job receipts; CLI timeout is not cancellation. `broker stop` ends owned work.

| Step | Shell route | MCP tool (group; integration) | What it saves |
|---|---|---|---|
| Read current request | The forge: `pulls/N` with its comments and reviews (`skill://ls-pr-evidence/references/forge.md`) | No forge reader exists (`github_thread_read` reads GitHub) | Read every page. |
| Pin/build arms | `regress.py plan`; approved build adapters | `build_plan(repo_id, commit, profile_id)`, `build_start(plan_id, idempotency_key)` (checks; integrated) | Pinned owned build jobs; no automatic timing authorization. |
| Observe queue | Gate files and live lock/process checks | `queue_status(device="gpu")` (status; integrated) | Structured queue/hold state without joining it. |
| Warm/collect ordinary evidence | Bounded `hs-run.sh`; control client | `session_launch(build_id, profile_id, wall_seconds, idempotency_key)`, `session_state(run_id)`, `session_stop(run_id, reason, idempotency_key)` (session; integrated) | Disposable gated lifecycle, not a performance hold. |
| Run paired timing | Authorized `regress.py hunt` or `_hold` | **None** | Keep the shared shell worker; do not substitute `session_launch`. |
| Read/analyse retained data | `run_case.py` results and raw trace/sample files | `run_logs(run_id)`, `run_faults(run_id)`, `evidence_analyze(run_id, analyzer_id, arguments, idempotency_key)` (evidence; integrated) | Bounded logs, explicit clocks, registered analyzers and rejection reasons. |
| Compare two repeats per arm | Shared `paired_decision` / `compare_paired` readers | `evidence_compare(pairing)` (evidence; integrated) | Checks exactly two explicit pairs for settings, clocks, quiet and repeat spread. |
| Scan/panel existing captures | `scripts/framelog.py`; labelled `panels.sh` | `evidence_scan_frames(capture_artifact_id, idempotency_key)`, `evidence_panels(images, label, idempotency_key)` (evidence; integrated) | Idle-gated scans/panels and artifact provenance; visual review remains. |
| Find/report previous evidence | Read registered reports and retained results | `knowledge_search(query, collection="reports")`, `workbench://reports/{id}` (knowledge; integrated); `evidence_bundle(request)` (evidence; integrated) | Revision-pinned reads and private drafts from recorded evidence, never publication. |
