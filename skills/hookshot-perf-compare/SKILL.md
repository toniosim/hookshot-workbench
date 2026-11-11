---
name: hookshot-perf-compare
description: >
  Compare two Hookshot builds or settings for speed on this machine (RTX 4090, NVIDIA driver, i9-13900K, Arch): fps,
  1% low, stutter frames, first-visit pipeline waits, memory over time. Use for any frame-rate claim, before posting a
  measurement on an upstream issue or PR, and for "is this switch/PR faster". Read skill://hookshot-workbench first.
  Written 2026-11-10 by PerfLinux and its successor PerfLinux2 from their own runs (reports/PerfLinux.md section 8).
---

# Comparing Hookshot builds or settings

Everything here was run by PerfLinux / PerfLinux2 on 2026-11-10 (scripts in
`/home/mooki/Code/hookshot-wt/reports/PerfLinux-files/`, called `$F` below). What was not run is marked **not run**.

## The spread: what a difference has to clear (measured, H1, report section 8.1)

Two identical runs, one quiet exclusive hold, main bdfe09c, defaults, Kokiri camera turns, 30 s window:

- uncapped (`HOS_FPS_MAX=240`): mean fps 80.14 / 80.33 (**0.2 %**), the replay's `submit` 9.04 / 9.08 ms (0.4 %),
  1% low 48.95 / 46.64 (4.7 %);
- 60 cap: mean 58.46 / 59.75 (2.2 %), `submit` 3.5 %; but **1% low 18.08 / 43.75**: one run had a 1.2-s cluster of slow
  frames (20 over 25 ms, max 89 ms), the other none.

So compare mean fps and the replay's phase times uncapped (they reproduce within ~0.5 %); 1% low and slow-frame counts
need several runs a side, and a single hitch cluster is reported as such, never as a rate.

## The scene and the save

- Save: `/home/mooki/Games/.hookshot-harness/saves/nx2navi-ocarina-20261109` (all six slots Kokiri Forest). The presses
  `5:A,8.7:A,11.7:A,15:A` go title -> Continue -> Load -> Kokiri Forest by Link's house (pictures looked at). Script time
  on the wall clock (the default): with `HOS_INPUT_FRAME_CLOCK=1` a 240-cap run's script runs 4x fast.
- Camera turns: the title presses, then from 40 s 13 right-stick turns of 4 s (`RRIGHT/4000`, `RLEFT/4000`) 4.5 s apart
  (the plans `q-h1.txt` etc. hold the full string).
- On a quiet machine the first present comes ~10 s after the start and the save's load ~22 s after the first present;
  the window 15-45 s after the load ends ~80 s after the start: **90 s runs** suffice (at load 50-60 the load came 47 s
  after the first present: runs were too short).

## Holds of runs, one waiter in the gate: pq.sh

One plan line per run, written A B A B; all runs of one plan run inside ONE gate hold through `ab-hold2.sh` (header:
the line's options `--input --user --every --threads --taskset --pinafter --live --go --prepare --fresh NAME=VALUE`).
The queue runner keeps one waiter in the GPU gate and the ten minutes between holds:

    cd $F && setsid nohup ./pq.sh < /dev/null > pq.nohup 2>&1 &
    # pq.txt, one hold a line (append freely; pq.done counts the ones done):
    #   prio ./ab-hold2.sh q-h1.txt --from 15 --to 45          (nx2navi-gpu-slot --priority --exclusive: timing holds)
    #   plain ./hold-prep.sh q-fvprep.txt <copy> <copy>         (no flags: preparations, the memory run)

- `--priority` only with the main session's permission, and then (its rule of 2026-11-10) each hold at most 6 minutes of
  game time and 10 minutes between the end of one hold and asking for the next. pq.sh keeps the gap for every hold.
- **What an exclusive hold costs the others** (2026-11-11 07:06-07:24): once its turn comes, the gate marks that no build
  and no run of the checks may start, then steps aside for the card's current holder; with a 35-minute hold of another
  agent in front, 13 builds and 7 runs of the checks stood still for 17 minutes, and the main session ended the request.
  So: no queue runner that asks for `--exclusive` by itself; put all frame-time runs into ONE plan (A B A B kept within
  each question), tell the main session its length, and let it start it (`--first --exclusive`) when the card's holder
  is short. Counts (pipeline waits, left-out draws, memory) need no quiet machine: run them without `--exclusive`.
- **Never** wrap a hold as `nx2navi-intel-slot nx2navi-gpu-slot --exclusive ...`: the Intel gate holds the `quiet` lock
  shared and the GPU gate then never gets it exclusive (deadlock). An exclusive hold already waits for running Intel
  games (they hold `quiet` shared) and for builds and the checks.
- `touch $F/pq.stop` ends pq.sh before the next hold; `STOP-kernel` (ab-hold2.sh writes it) ends it too.
- Each run: `others.txt` (pl-inner2.sh): the load, the number of compiler processes and of other `hookshot` games, and
  the five busiest processes, at the start and at the wall. The 1-minute load average lags by a minute: read the
  compiler/game counts for "was it quiet", the load for the record.
- Kernel lines (the main session's rule since 2026-11-10 23:2x): stop and tell it at any `NVRM: Xid`, any
  `kmemsysDoCacheOp`, or any NVRM line other than `NVRM: memMap_IMPL: CPU mapping not supported for addressSpace: 0x1`.
  That memMap line is the game's own failed dma-buf import on NVIDIA (it tries again for every new pool): ab-hold2.sh
  counts it as `memmap=` (1 to 3 a run seen) and keeps every NVRM line with precise times in `<run>/nvrm.txt`.

Uncapped = `HOS_FPS_MAX=240` (the menu's highest cap; the code clamps at 240). The user's 4K picture:
`HOS_OUTPUT_RES=3840x2160 HOS_DYNRES=0`.

## Frame times that work headless, and the tables

`RX_VK_FRAME_LOG` writes nothing headless (no swapchain). `HOS_PRESENT_TRACE` (`present.csv`) is the game's own
present-to-present interval on CLOCK_MONOTONIC, cap included; not GPU completion or scan-out.

    python3 -I $F/fpsstat.py --from 15 --to 45 <run dir> [...]                 # one line a run
    python3 -I $F/table.py --from 15 --to 45 <runs...> --pair <a>,<b> [...]     # markdown table + the pair's differences

Window = seconds after the save's load (the last present gap over 300 ms in the first 60 s). Mean fps, 1% low (1000 /
mean of the slowest 1 %), p99, frames over 20 / 25 ms, max; the log's 120-frame means (replay `submit`, `draw`, GPU
time); samples.csv's GPU use, VRAM, RSS, power. Asserts: consecutive frames, monotonic time, the window >= 90 % covered,
frame times summing to the span. At the 60 cap half the paced intervals are 16.8-17 ms by jitter: "over 20 ms" is the
missed-frame count.

## What disturbs a run, and how to tell

- **Load.** Builds slow every phase of the replay by the same factor (`pl-load1`: 3,840 draws in 12.8-13.3 ms at load
  7, 18-24.5 ms with two builds beside it); the GPU time does not move. The frame is bound by the replay on one CPU
  thread (H1: `submit` 9-10 ms a frame, GPU 6 ms, GPU use 46-62 %).
- **Cores.** `--threads` writes threads.csv; `python3 -I $F/threads.py <run> --from 50` gives each thread's share of
  CPU time on the P-cores (0-15).
- **First visits.** `--fresh` deletes the pipeline caches (keeps translated programs). `snap.sh save|restore <copy>`
  keeps a copy's state right after `--prepare --fresh` in `<copy>/.snap-prepared` and puts it back before every play
  run (`hold-prep.sh`, `hold-play.sh`), so a second round replays the same prepared folder without preparing again.

## Memory over time

`--every 10` samples RSS (anon/file/shmem: the guest window is a memfd, so most of the game's memory is RssShmem) and
the card's memory; `python3 -I $F/memcurve.py <run> --skip 120` prints 5-minute marks and slopes, and the log's caches.
The 45-minute run (`q-mem.txt`) is queued last, not exclusive.

## Builds of a PR's renderer

`$F/build-vk.sh <worktree name>`: the Vulkan back end alone (RX_VK_ONLY=1, RX_RELEASE=1, A64_HOT_CHUNK=1) through the
build gate, 2-14 min depending on the load; log `flags f08f29989d` as the bench's. An RX_VK_ONLY build of bdfe09c is
the same size as the full build's vk.so but not byte-identical (the embedded source paths and version string differ).
A PR whose base is far behind main: merge it onto the main the game copy was built from (local probe worktrees
`perf-m<PR>`, never pushed) rather than putting an old renderer over a newer game. A vk_shader.cpp change alters the
program-cache stamp: the first start translates again.

## Not run yet here

The profilers in `q-prof.txt` (`HOS_SAMPLE_ALL` + `HOS_PROFILE=10` via `--go`, `scripts/crit.py`/`vkprof.py` with
`RX_MAPS=<copy>`, `RX_VK_PASS_TIMING=2`, `RX_VK_SLOW_LOG=25`), `fvstat.py`, `memcurve.py` on a long run: see the report
for what has run since.
