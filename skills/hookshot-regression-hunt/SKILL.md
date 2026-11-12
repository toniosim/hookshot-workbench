---
name: hookshot-regression-hunt
description: >
  Find which merged Hookshot pull request made a build worse: frame times, hitches, start-up, memory, drawing, or a
  pass/fail check. Use for "which PR caused this", a regression against an older build, a lead that names a suspect or
  a switch, and a nightly playtest's confirmed regression. Show the difference first, test named suspects by revert or
  by switch, then bisect over groups of equal lifted inputs. Read hookshot-workbench and hookshot-perf-compare first.
---

# Finding a Hookshot regression

Read `hookshot-workbench` (building, the fast path, `hs-run.sh`, the gates) and `hookshot-perf-compare` (what a timing
needs) first, and `hookshot-pr-evidence` before anything is written for a tracker. The machine's agent brief and the
caller's word go over every example here. A worker never pushes or posts. This file is public: the method only; which
save and which input a scenario uses live in local files.

## 1. Show the difference before looking for a culprit

1. **Pin commits, not folders.** The good and the bad build by commit, binary checksums, build flags and profile.
   Fetch once and write the head down; main moves several times an hour, and a play folder or a copy called "main" can
   be replaced under you during the hunt. Check what an earlier report really compared: two settings on one build are
   not old against new.
2. **Copies of your own**, by reflink, never the player's folder or another lane's copy. Assert for every run: no
   `mods` folder and `HOS_MODS` unset, no options or environment file in the copy (a saved experiment there changes the
   run silently), the expected source stamp, device and output size in the log. Name every switch of a run.
3. **The same scene, input, size, cap, upscaler, and the same cache state.** A freshly prepared copy compiles the
   pipelines the shipped list lacks in its first run of a scene; an older copy has them. Give every copy one unmeasured
   run of each scene and mode first, then time. The shader caches' stamp covers the translator's files alone
   (`nx2/build.py`), so a variant that leaves them alone can take a prepared, warmed copy's caches by reflink (make the
   copy after the preparation and the warm-up, with no game running from the source).
4. **In turn inside one quiet hold**: A B A B, and "quiet" is judged by what everything else on the machine used
   during the run's measuring window, not by the load average: a run counts when the rest used under `quiet_cores`
   (3) on average, no 5-second sample of it was above `quiet_peak_cores` (6), and the hold's repeats of the same arm
   agree within `repeat_tolerance` (5 %) on the measure. The 1-minute load is printed beside every run as information
   only: it lags by a minute and it counts the game's own waiting threads, more on one build than on another, so a
   load limit marks the slower build more often. The hold may wait the seconds it has to spare before its first run
   (`settle_seconds`) for the rest to fall under `quiet_cores`, never more. No timing from an ordinary shared run.
5. **One instrument on both builds.** An old build may lack a switch (`RX_VK_FRAME_LOG` without a window came with
   #2354, `HOS_CHAIN` with #2325): give both the same small local logging patch rather than compare unlike clocks.
   Frame intervals without a window are CPU intervals after the offscreen copy, not scan-out; when the suspected wait
   could sit in the swapchain, add one windowed pair under the window rules.
6. **Count the whole population.** A log line that averages "those that waited" changes meaning when a change alters
   what counts as waited (the readback line did, with #2125); a line that logs the first N slow cases is a sample.
   For "how many a frame and how long each" log every call the same way on both builds, with the present number.
7. **A claim about threads needs the threads**: each thread's processor time from `/proc/<pid>/task/*/stat` over the
   measurement window (the supplied adapter samples it), not the process total.
8. **Bands from clean runs.** The good and the bad build's ranges must not overlap in the measure the hunt decides by.
   Uncapped mean frame time is the steadiest; 1 % low and slow-frame counts need several runs a side. Add the
   player's own settings (his cap, his upscaler) as a separate arm: what moves uncapped may or may not cost him frames.

## 2. Suspects before a bisect

- **Read the suspect's code and its pull request first**: what it fixes, what it measured, on which hardware, and
  what its reviewers said was not measured. A wait that got longer may be the removal of a false speed-up.
- **A lead that names a switch**: read what the switch does on this platform and in both builds before spending a
  hold. A default can depend on the processor count or the system; a switch can exist in both builds with the same
  default (then it explains nothing between them, and is an A/B on the bad build only); a default that flipped inside
  the range is a real candidate even though "the code is in both". Put the switch's own log line into the run's
  expectations, so a run where it did not take effect is not counted.
- **A switch needs no build**: `--switch LABEL:NAME=VALUE` runs the bad build with it against the bad build as it is.
  **A revert** (`--suspect SHA`) is the independent check of the same story, and the only one where no switch exists.
  A switch that takes back only part of a commit is that part; say so.
- **What the suspect gives up when off**: write it down before the run, and look for exactly that in the pictures of
  the run (a stale readback shows as a one-frame brightness step, not as a slow frame).
- After the suspects: **state the remainder in numbers**: the good build against the bad one with the suspects off, in
  one hold. Only a remainder beyond the runs' own spread is hunted further.
- When someone else is already fixing the cause, the product is the measurement on this hardware (and a test of their
  branch when it exists), not a second fix.

## 3. The tool

`regress/` under the harness root holds four scripts (standard library only, nothing of a game in them):

```
python3 -I regress.py plan --repo REPO --good GOOD --bad BAD --output NEW_DIR
python3 -I regress.py hunt --repo REPO --good GOOD --bad BAD --scenario LOCAL.json --output NEW_DIR \
    --max-holds N [--max-steps 9] [--max-hold-seconds 480] [--max-wall-seconds 5400] \
    [--exclusive-authorized] [--priority-authorized] \
    [--suspect SHA[,SHA]]... [--switch LABEL:NAME=VALUE[,NAME=VALUE]]... [--suspects-only]
```

- `plan` reads git only and spends nothing: the range with each commit's subject and numbers (a subject can carry an
  issue's number beside the pull request's), the groups of commits whose lifted inputs are equal (`nx2/` without
  `build.py`, `third_party/a64-kit`, and the HLE names `host/` defines), and how many distinct lifts the range has.
  One finished lift serves a whole group through the fast path; each further group a bisect enters costs a full build.
- `hunt` confirms both ends in one hold, tests each suspect and switch on the bad commit, then bisects, choosing the
  middle of the open range among the commits a finished lift already serves. The budgets are the caller's and are
  never raised: holds (every retry is one), bisect steps, wall time, the seconds of one hold. `--exclusive-authorized`
  and `--priority-authorized` are passed only when the main session gave them for this hunt.
- A step is one hold: reference, candidate, reference, candidate. It decides only when every run is clean and both
  reference runs are in their band; anything else (a disturbed, invalid or in-between run, a reference that drifted)
  runs the whole pair again while holds remain, and otherwise the hunt ends `inconclusive` with the smallest range it
  can support. A run that is not valid ends its hold at once (the card goes back); a kernel fault line ends the hunt.
- The result: `range.json`, `steps.json`, `table.md` (one row per run, the rejected ones too), `result.json`
  (`status`: `first_bad`, `suspect_explains`, `not_reproduced`, `inconclusive`; `remaining`; `reason`; `suspects`).
  `first_bad` assumes the measure changes once in the range; `suspect_explains` says what a revert or a switch does on
  the bad commit, which is not the same as the first bad commit.

**Scenario** (local JSON, schema 1): `kind` (`timing`: an exclusive hold; `game-check`: an ordinary hold, pass/fail
only; `check`: no GPU), `seconds`, `repetitions`, `max_retries`, `quiet_cores`, `quiet_peak_cores`,
`repeat_tolerance`, `grace_seconds` (the reserve after each run, 25), `settle_seconds`, `measure` (`name`,
`direction`, and for numbers `good_max` < `bad_min` in worseness units:
negate a value where lower is worse), `build_command`, `run_command` (argv lists, never shell text), and what the
adapters read. Four runs of 90 s with a 15 s reserve fit one 480 s hold with seconds to spare for settling.

**`run_case.py`** runs one scenario through `hs-run.sh --inner` inside the hold (it never asks the gate itself). Its
`run` object: `user` (a save folder), `input`, `env`, `anchor` (`load`: the window starts at the end of the longest
present gap that begins between `load_after` and `load_before` seconds, so a later hitch is not taken for the load;
`first`), `from`, `to`, `expect_log`, `forbid_log`, `window`, `prepare`, `framelog`, `validator_command`. It writes
`result.json` with the frame statistics of the window (mean, median, 1 % low, frames over 16.7, 20 and 25 ms), the
log's 120-present lines (GPU time, replay phases, pipeline waits), start to first present, the readback counts when the
local readback log is there, memory high-water mark, per-thread processor time samples, what everything else on the
machine used, and the kernel's driver lines. Look at the run's pictures yourself: a load gap is not proof of the scene.

**`build_case.py`** builds a candidate: a finished build with the same lift key by reflink and `nx2/build.py` (release
mode, the profile at `work/build/hookshot_pieces.prof`), else a full build through the lock and the build gate. Its
`build` object names the local paths, known finished donors with their completion markers, an already accepted SDK,
and any local patch to apply to every candidate (the logging aid).

**`test_regress.py`**: game-free checks with made-up histories, synthetic logs and a stand-in adapter (grouping, the
bands in both directions, pass/fail, disturbed and in-between runs, a drifting reference, the stop conditions, the
held worker's order, limit and settling, switches, the adapter's statistics and what it hands the wrapper).

## 4. Running holds by hand

A hunt whose arms are not one good/bad pair (several switches, two scenes, the player's settings) is easier as named
plans run through the same held worker: `regress.py _hold <plan.json>` inside the gate, the plan listing its runs
(`role`, `label`, `copy`, `commit`, `output`, and a `scenario` of its own per run), `seconds`, `grace_seconds`,
`max_hold_seconds`, `settle_seconds`. Write a plan once and never run it twice: a hold's evidence is not replaced.
Before withdrawing a waiter from the gate's queue, check that its run has not started.

## 5. What counts as proof, and how a finding is written

- A cause is shown when taking it back on the bad commit moves the measure from the bad band to the good one in clean
  paired runs, or when the bisect ends on it; "contributes" when it moves part of the way beyond the spread; "ruled
  out" when its runs stay in the bad band. A list of commits that touch the code involved is a lead, not a finding.
- Every table has one row per run with the build, the switches, the scene, the load, and the state of the run.
- Say what the change fixes beside what it costs, so nobody takes back a correctness fix blindly, and what the
  pictures of the runs without it showed (and how many frames were looked at: stills do not prove a flash is gone).
- Whether anything is posted, and where, is the main session's and the user's decision.

## 6. Limits

A quiet machine and the gate's holds (a hold is at most eight minutes; exclusive holds stop every build and check on
the machine); one waiter in the gate at a time; no synchronisation or safety mechanism switched off without the main
session's word (a diagnostic revert of a wait is such a thing: it is named in the task or asked for).
