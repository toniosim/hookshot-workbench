---
name: ls-hold-chain
description: >
  Use before queueing a game run, build, suite or proof behind the quiet-window and measuring locks, when a hold is
  queued behind other workers, its waiter shows state T, or a base moves while you wait: one admission for many stages
  (chain.py, waiter, flock -w 43200, "admitted", hold of 480 or 1,100 seconds), the lock order and modes, the dispatcher's
  priorities (waiter name matching, never SIGCONT), the EDITING/READY markers that let a queued waiter be retargeted,
  finding your own waiter's pid, and how a session waits for a hold that may start hours later.
---

# Queued holds: one admission for many stages

The quiet-window queue held 8 to 17 waiters most of 14 to 15 November: a short run cost 22 minutes to over 3 hours
before it started, and a second hold costs a second full wait. Nineteen workers wrote their own `chain.py` for this.
Start from one of theirs, not from nothing.

## 1. Plan: one hold, code and tests first

1. Finish and commit the code and run its game-free tests **before** queueing. A stage that asserts a clean tree blocks
   all editing of the worktree while it waits; build from a detached copy of the commit if you must keep editing.
2. Put every run that does not need an earlier run's answer into **one** hold: build, warm caches, pair session, suites.
   A failed build skips what depends on it; the later independent stages still run (the hold is paid for). If each
   result chooses the next run, say so in the hand-off: several short runs are several waits.
3. Check the pieces without a lock first (`check-only.py`, `prepare.py --check` in the folders below): trees match the
   head, scripts parse, files exist. A mismatch found after admission costs the whole wait. A game copy whose build has not
   finished is refused, before you queue and again by the hold's first stage: its receipt says `done: false`, it has no
   `built-from.txt`, `build.exit` is not 0 or the build log lacks `@@done` (a rehearsal was refused for a build that was
   still queued). So is a head that moved while you prepared: the newest registered build is the one to hold
   (`reports/CoopSoak-2-files/hold/launch.py` refuses a moved head).
4. A diagnostic hold carries every candidate fix next to the question: one 100-second hold told which cause it was and
   tested the fix. You have one waiter per gate, so a second hold of yours queues only after the first is admitted or
   finished; fold both into one when you can.
5. List the game copies the hold needs in `reports/tools/diskclean/exclude.txt` (path, a tab, why) when you queue: the
   weekly cleaner judges copies by age and a reflink clone keeps its source's mtime, so a copy that waits hours looks old.

## 2. The locks (a convention; no script enforces it)

```sh
QUIET=/tmp/longshot-quiet-window.lock       # always exclusive, taken first: every hold and timing run (a build or a suite
                                            # only as a stage inside one: alone they take no quiet lock, see below)
MEASURING=/tmp/longshot-measuring.lock      # exclusive when any game runs; -s (shared) for a CPU-only job or an ordinary run
```

**The side lane (the user's decision, 17 Nov 2026):** a second lane for one single-game *feature* run at a time beside the
main lane: `setsid env --default-signal=HUP flock --verbose -w 43200 /tmp/longshot-side-lane.lock CHAIN-OR-GATE-COMMAND`
(no quiet or measuring lock; your name in the cwd or command). A feature run shows a feature works (pictures, logs, bridge
readings, a save round trip); it claims no frame time, stutter, VRAM or memory figure. Its game still asks the GPU gate
(`hs-run.sh`, one slot, never `--whole` or `--exclusive`): the gate starts it beside the main lane's game only when that game
has run a minute, the card has room, 30 GB of RAM is free and memory pressure is calm, and never beside a timing or two-game
run. Set `RX_VK_VRAM_MB=9000` for the side game so the card is never filled. **Main lane only:** timing holds, two-game or
co-op runs, soaks, memory or VRAM measurements (leak walks, cost arms), a run that must be alone (a switch with a recorded
hang), and a run driven by a timed `RX_VK_MENU_SCRIPT` (a stall beside another game breaks its timing). Say "beside another
game (side lane)" in the report; any kernel driver line in a side-lane window means the run is redone alone in the main lane.

Also in use: `/tmp/hookshot-full-build.lock` (`flock` in front of `hs-build-slot`, no `-w`, for a full build) and
`/tmp/longshot-whole-suite.lock` (the whole suite; `reports/tools/verify_heads.py`). A build on its own takes only the
full-build lock and the build gate (`flock` on the full-build lock, then `hs-build-slot ...`: how the 1383 build ran, no
quiet or measuring lock), inside `hs-idle.sh` when the task says heavy jobs go through it; a suite goes through
`hs-idle.sh`. One nested command for a hold, quiet lock outermost:

```sh
flock --verbose -w 43200 "$QUIET" flock --verbose -w 43200 [-s] "$MEASURING" CHAIN-OR-GATE-COMMAND
```

- A shared taker passes a waiting exclusive one on Linux, so a CPU job that wants the measuring lock shared takes the
  quiet lock first: `flock -w 43200 "$QUIET" true && flock -w 43200 -s "$MEASURING" CMD`.
  Do not chain shared holds: a second shared `flock` of yours is granted at once while the first is held, which keeps the
  lock without ever queueing again (such a chain kept a game hold that had waited 45 minutes waiting).
- Inside the hold each game stage asks the GPU gate itself (`hs-run.sh ... --prepare|--whole`); a pair session runs
  `hs-gpu-slot --whole timeout --signal=TERM --kill-after=25 N ...`. `--exclusive` on the gate is only for a timing hold
  Main authorised (`hs-gpu-slot --exclusive timeout --kill-after=5 475 ...`). `hs-run.sh` in wrapper mode cannot nest
  inside a gate you already hold.
- A hold is at most 480 seconds unless the task text grants more: co-op proofs 1,075 to 1,100, and on 17 Nov the ordinary
  single-game holds of a performance campaign, 1,100. A longer hold runs each stage under its own `timeout` and checks the
  time left before it starts (`regress.py`'s hold refuses more than 480; `reports/Work61-files/hold/hold61.py` runs several
  `hs-run.sh` cases one after the other inside the two locks that way). `-w 600` timed out
  silently once; the lane's wait is `-w 43200` (12 hours) with `--verbose`, which logs the wait. 4 hours (`-w 14400`)
  ran out for waiters at priority 10 behind a 3-hour hold, and `coopplay.py run` still queues itself with two nested
  `-w 14400`: on a queue that may be long, queue your own waiter.
- Cloning a game folder (hundreds of thousands of files) is heavy file-system work: do it inside the measuring lock or
  when no hold runs. Two proof holds were stalled for 14 to 38 seconds by another worker's clone; both games' present
  intervals and a process that runs no game code stalling at the same instants tell an outside stall from a game fault.
- Admission orders holds; it does not isolate the game from this PC's other work (clones, builds and tests that take no
  lock). The load average reached 130 during one 2-hour pair run and a game stalled for up to 8.8 seconds. Read the
  load average and `/proc/pressure/*` (their `total=` counters date a stall to the second) at the hold's start and end
  and read every `frames` or stall verdict against them; the co-op runner's `frames` detector cannot tell a loaded PC
  from a game fault.

## 3. Build the chain

Starting points (read first: they carry their own run's names; the third is the simplest for timeboxed plans):

- `reports/Replay18-files/hold/` (`chain.py`, `build-linux.py`, `title-linux.py`, `tests.py`, `check-only.py`) with
  `reports/Integrate18-files/make-hold.py HEAD MAIN BASE`: build, title run, suites; six stages ran in about 1,955 s.
- `reports/PortUpnp-files/hold-src/` (`chain.py`, `warm.py`, `pair.py`, `tests.py`, `prepare.py`): build, warm, pair
  session, suites with `@HEAD@` templates; its last chain was never admitted, so treat it as untried end to end.
- `reports/SaveSettingsOnly-files/hold/` (`queue_hold.py`, `hold_chain.py`, `make_plan.py`, `inner.sh`, `refresh.sh`):
  a plan of tracks with `min_left`, `timeout --kill-after=25` capped at 1,400 s.
- `reports/Work61-files/hold/hold61.py`: several game cases of one hold, each its own `hs-run.sh` with its wall and a
  time-left check, inside the quiet and measuring locks (an ordinary hold of up to 1,100 seconds).

For a pair of games alone, `$H/coop-play/coopplay.py run CASE` is the whole hold (see `ls-scripted-play`).

Keep from them: receipts written at each step (`chain-requested.json` makes a second launch refuse, `chain-waiter.json`
holds the waiter's pid, `stage-K-running.json`, `stage-K-exit.json`, one log per stage opened exclusive-create,
`chain-admitted.json` with the queue wait, `chain-result.json`); never replay a stage; a clean environment (drop
`HOS_*`, `RX_*` and the game's name-prefixed variables); the head's hash and every name in **one small constants file** that each stage
reads when it starts; each stage checks the time left before it starts and runs under its own `timeout`.

Freeze what the hold runs. The plan and case files are read again at admission; a tools folder is not. Copy it (with
every file the pilot loads by path) into a new folder, queue from the copy, and replace single files atomically only if
you must: `multihold.py queue` resolves its own path when queued, so swapping a symlink later does nothing. The copy
must sit beside the harness's `hs_names.py` (the drivers find it from their own location; a folder under `reports/`
fails at import), and each script the hold starts must run once under `python3 -I`, which leaves the script's own folder
out of `sys.path`: a sibling import that passes the unit tests dies at start. A stage that starts the next waiter closes
inherited descriptors (`close_fds=True`), or the successor waits for a lock its own leaked descriptor holds.

## 4. Retarget a queued waiter instead of requeueing

Stage scripts are read when their stage starts and `chain.py` only at admission, so stage scripts and the constants file
can be edited while the waiter is queued; a moved base was handled this way once and saved a 2 hour wait.

- `hold/EDITING` (empty file): after admission the chain polls it every second and waits while it exists. Create it
  before you edit `chain.py` itself or swap folders (`swap-dirs.py`), remove it when the files are whole. While it exists
  the hold keeps both locks and idles the machine (about 12 minutes in one case): be quick.
- `hold-N/READY`: `inner.sh` waits up to 120 s holding the locks for it, then exits 3 and gives the hold back. Write the
  plan and chain script to a temporary file and `os.replace` them, so a stub that only checks `READY` can queue first and
  the real plan arrives later. Rerun `make_plan.py` after every rebase: it asserts the trees match the head.
- A rebase that changes the head still needs the checks of section 1 before the stages run.
- The waiter's own `timeout` (the hold's length) is fixed when it is queued; a rewritten plan cannot lengthen the hold.
  A hold maker's "one waiter at a time" guard that counts processes with `pgrep` sees every agent's waiter: give it a
  pattern with your own folder name only (`QUEUE_HOLD_PGREP` in the pilot hold makers).

## 5. See the queue, find your own waiter, cancel

```sh
lslocks -o PID,COMMAND,MODE,M,PATH | grep -E 'quiet-window|measuring'   # WRITE* = waiting, the holder has no star
ps -eo pid,ppid,stat,etime,cmd | grep 'flock.*quiet-window'            # T = paused by the dispatcher
tail /home/tonesi/hookshot-wt/reports/tools/gpu_priority.log
```

- Main's dispatcher (`reports/tools/gpu_priority.py`) ranks every waiter of the quiet lock by priority, then by when it
  was queued (its start time; pids wrap, so a pid is no order), lets the first run and SIGSTOPs the rest. State `T` is
  normal. The priority is the first entry of its `ORDER` list whose text occurs in the waiter's **working directory or
  command line** (lower runs first; `LinuxTests2` matches `LinuxTests`; a name with no entry gets 10, which waits behind
  everything real). So start your waiter from a folder named for your topic (the waiter script must `cd` there; the log
  names a waiter by that folder), ask Main for an entry before queueing a new topic name (the list is read once: Main
  restarts the dispatcher), and name a pilot proof's hold folder with `Pilot`. `reports/tools/gpu_priority.log` shows the
  live ranking; the file's `ORDER` can differ from the running copy.
- A stopped flock keeps its own `-w` timer: a waiter paused for the whole of its wait exits 1 unadmitted (one did,
  after 16,150 s); requeue it in a **new** folder. A stopped flock is not shown by `lslocks`. Never signal the
  dispatcher, and never SIGCONT a waiter: only the dispatcher continues one, and a waiter you continue runs out of order.
  A waiter that takes the lock in the instant before the dispatcher stops it is continued as a **holder** within a few
  seconds (fixed 17 Nov 11:43; before that the soak held the lane for 80 minutes after its run ended): a waiter in state
  `T` is normal, a holder in `T` is not: tell Main.
- Record the pid of your own waiter when you start it (`chain-waiter.json`). The `$!` of `setsid ... &` inside a subshell
  is a wrapper that exits at once; find the real waiter with `ps --ppid`. Never use `pgrep -f` or `pkill -f` on a lock
  command line: it matches itself and everybody's.
- Cancel before admission with `kill -KILL <pid of your own flock>`: a stopped flock acts on SIGKILL at once but keeps
  SIGTERM pending until it is continued. After admission, killing the outer flock only ends the launcher: stop the
  stage's own process (for a regression hold, `regress.py _hold`) and wait for its game to end. A withdrawn waiter
  gives up its place: requeue in a new folder and expect the wait again.

## 6. Start it, and wait for it from a session

- Start the chain as a managed background job (an async `bash` call with `timeout: 0`) or a launcher started with
  `setsid --wait nohup env --default-signal=HUP`. A plain foreground `cmd &` died with its tool call; a
  `setsid nohup bash -c "flock ..." &` launcher vanished without a receipt within minutes, and a `( cmd & )` inside one
  call is gone when the call returns. When the launcher already runs in its own session (a tool or script that started
  it with `start_new_session`), `setsid` forks and the recorded pid is a dead parent: start `env ... flock ...` directly.
- A foreground `bash` call is moved to a background job after about 60 seconds, so keep a `sleep` inside one under 50
  seconds; `wait` returns after 5 to 10 seconds and never sits out a queue. What blocks until the hold ends: a `bash`
  call with `pty: true` (the tool says the terminal is unavailable and runs without one; four workers' calls stayed in
  the foreground for the whole wait, 1,425 s to 3,500 s, up to the call's `timeout`), or one `eval` (Python) cell with
  `timeout` up to 3600 that loops on the receipt file or on inotify (39 minutes in one run; an incoming message
  interrupts the cell, so restart it). A managed background job that ends when the receipt exists (`while [ ! -e
  exit.json ]`) wakes the session when it finishes; a detached `setsid` waiter cannot. A reply without a tool call ends the run.
- A hold likely to be admitted hours later, past your request budget: hand Main the queued waiter, its pid and the
  steps for reading the results (`chain-admitted.json`, `chain-result.json`, each `stage-K-exit.json`), and stop.
- `hs-nocore.sh` queued behind someone's exclusive measuring lock prints nothing for minutes; that is the wait, not a
  hang. The same holds for `hs-idle.sh`, which queues silently behind an exclusive hold (waits of 5 to 6 minutes seen)
  and sits on one of its three test slots while it waits.

Report the admission wait separately from the child's time, with the receipts.
