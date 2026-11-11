# Rules for every agent working on Hookshot here (written 2026-11-10; the main session keeps it current)

## The project and who we work for

- **Hookshot** (`NotRexed/Hookshot`, GPL-3.0-or-later): a static recompilation of the Switch 2 remake of *The Legend of
  Zelda: Ocarina of Time* for Windows and Linux. The user (GitHub `mooki000`) contributes to it; his goal is the best
  experience for himself and other Linux players (his machine: Arch, Hyprland, i9-13900K, RTX 4090 with NVIDIA's
  driver, an Intel UHD 770 beside it, a 1920x1080 monitor at 60 Hz), and features: co-op and a randomizer first.
- Until 2026-11-10 the same work went to another port of the same game, NX2navi. The user ended that. Its repository
  (`/home/mooki/Code/NX2navi`), worktrees, reports (`/home/mooki/Code/nx2navi-wt/reports/`) and harness
  (`/home/mooki/Games/.nx2navi-harness/`) remain on disk as **reference only**: read them for ideas, facts about the
  game, and for the user's own earlier work; start nothing there, post nothing there.

## Read before anything else

In the clone `/home/mooki/Code/Hookshot`: `docs/workflow.md` (priorities, hardware tiers, the lifecycle, "For agents"),
`AGENTS.md`, `CONTRIBUTING.md`, then `docs/development.md` (commands, test switches, layout) and `docs/design.md`.
Their rules bind you as they bind everyone. The ones that matter most:

1. **No game files, keys, or anything made from them leave this PC or enter the repository, an issue or a pull
   request**: not the dump, not `work/`, not built games, saves, lifted C, shader dumps. Pictures of the game, videos and
   `hookshot_log.txt` are fine. Game-derived data we make (flag names, coordinates, routes, world models, logic read from
   the game's files) stays local under the harness or the reports' files folders; if in doubt, it is game data.
2. **Licence: only code we may license under GPL-3.0-or-later.** NX2navi's repository puts everything added after its
   base import under "all rights reserved": **never copy a line from NX2navi's repository into Hookshot**, and never
   paste decompiled game code. The user's own earlier work (files he added in his fork that contain nothing of
   NX2navi's) may be brought over only when the file is listed as wholly his in
   `/home/mooki/Code/hookshot-wt/reports/OURS.md` (the inventory; if it does not exist yet or does not list the file,
   re-implement from the idea against Hookshot's code; do not copy).
3. **One topic per pull request; a branch from current `main`; the cause before the fix; a game-free test that fails
   without the change** (many tests in `tests/` cut functions out of the source by their text: run
   `python -I -B tests/run_all.py`, all of it, and update a broken check in the same change). CI must pass.
4. **Pull request title = a Conventional Commit** (`feat(scope): ...`, `fix(scope): ...`, `perf`, `docs`, `test`, `build`,
   ...); it becomes the squash commit. The description opens with why the change is needed, in one or two plain
   sentences; then what changed, how it was tested (GPU, driver, place in the game, frame rates before and after where
   speed is claimed), what was not tested, and screenshots when the change shows on screen. Link the issue.
5. **AI assistance is recorded** with trailers, as the maintainers do: `Assisted-by: Claude Opus 5.5` and
   `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` at the end of each commit message.
6. **Claims**: the project asks for a claim in its Discord (#dev-work) and on the issue before work starts. You never
   post anywhere; say in your report what should be claimed, and the main session and the user do it.
7. Hardware tiers: a change must not break NVIDIA RTX and AMD RX on Windows and Linux, or the Steam Deck, to help
   something else. Say what you could not test (Windows, AMD, real input devices).

## This machine

- **Never touch**: `/home/mooki/Games/Ocarina`, `/home/mooki/Games/Ocarina-linux-next`, `~/.config`, `~/Downloads`
  (reading the user's dump where it lies is allowed; never copy, move or change it), global git config, system packages
  (no pacman, no sudo, no `pip install` outside a venv or a deps folder of the work area). Never restart, reconfigure or
  send input to the compositor.
- **Paths**: clone `/home/mooki/Code/Hookshot` (remotes `origin` = NotRexed, `fork` = mooki000); your own worktrees
  under `/home/mooki/Code/hookshot-wt/<name>` (`git -C /home/mooki/Code/Hookshot worktree add ...`); reports and their
  files under `/home/mooki/Code/hookshot-wt/reports/`; built games under `/home/mooki/Games/.hookshot-h-<name>`; harness
  scripts under `/home/mooki/Games/.hookshot-harness/`. The skill `hookshot-workbench` (once it exists) says how to
  build and run; until then `docs/development.md` does.
- **The GPU is shared and the user's desktop runs on it.** Every program that creates a Vulkan or GL device goes
  through a gate, window or not, headless or not: the RTX 4090 through `/home/mooki/Games/nx2navi-gpu-slot <command>`
  (add `--exclusive` only for frame-rate measurements and only with the main session's word; `--priority` only when
  the main session says so), the Intel device through `/home/mooki/Games/nx2navi-intel-slot`. Builds go through
  `/home/mooki/Games/nx2navi-build-slot`. Never set `NX2NAVI_SLOT_DIR`, `NX2NAVI_INTEL_SLOT_DIR`, `NX2NAVI_SLOT_TEST`,
  `NX2NAVI_SLOT_NODESKTOP` or `NX2NAVI_IN_GATE`; begin a command that touches a gate with `unset` of these five. Prefer
  `HOS_HEADLESS` runs (no window on his desktop) wherever a window is not what is tested. After each run on the card
  count the kernel's driver lines since its start (`journalctl -k --since "<start>" | grep -c -E
  'kmemsysDoCacheOp|NVRM: Xid'`; must be 0) and report it. A desktop crash ends the user's session and every agent.
- **One hold keeps the card for at most 8 minutes** (rule of 2026-11-11). A plan of many runs is cut into holds of
  at most 8 minutes of game time each (keep A B A B pairs inside one hold; chain the holds from a script so each asks
  the gate again and the queue gets its turn between them). One 24-run hold kept twenty waiters, the co-op lane among
  them, off the card for 35 minutes. And **no `--exclusive` without the main session's word for that one hold**: an
  exclusive run stops every new build and every run of the checks from the moment its turn comes until it has
  finished (on 2026-11-11 one stopped 13 builds and 7 runs of the checks for 17 minutes before it had even started).
  Tell the main session what needs a quiet machine and for how long; it opens a window and says when to ask. Counts
  (escapes, waits, left-out draws, memory, pictures, pass or fail) never need `--exclusive`: only frame times do.
- **Two run slots since 2026-11-11 08:05** (while the user is away; the switch is
  `/home/mooki/Games/.hookshot-harness/gpu-slots`, `2` or `1`, the main session's to change). A second game may now
  start beside yours once yours has run for a minute, if the machine has 30 GB of memory available and the card has
  room. So: **never read a frame rate, a frame time or a "smooth or not" judgement from an ordinary run as a
  measurement**: another game may be on the card. Pictures, log lines, counts, pass or fail are unaffected. A run
  whose picture is larger than the game's own 2048x1152 (`HOS_OUTPUT_RES` or `output_res=` in the copy's options
  file) takes the whole card by itself: `hs-run.sh` adds `--whole`; ask for `--whole` yourself only when a run needs
  the card's memory for another reason, and say why. After a priority run the oldest ordinary waiter goes next, so
  priority no longer starves the queue, but it is still only for single short runs the main session has named, never
  for a series. To see the state: `/tmp/nx2navi-gpu-slots/` has `queue/` and `yielded/` (the waiters), `holder.0`,
  `holder.1` (who runs), `last-kind`, `long-holds.log` (holds past 8 minutes are written there).
- **Windowed runs** (`hs-run.sh ... --window`: a real window on the user's desktop, never focused, at most two
  minutes, one at a time, the whole card): only for what needs a swapchain and the compositor (presentation, frame
  pacing, V-Sync, frame generation's output), only while the file `/home/mooki/Games/.hookshot-harness/window-ok`
  exists, and only after asking the main session for that run. The summary's `window=ok active=same others=same
  screen=on` must all hold; a run with anything else there is disturbed: tell the main session and throw its numbers
  away. Everything else stays headless.
- **Which kernel lines stop a run.** Stop every run of yours and tell the main session at any `NVRM: Xid` line, any
  `kmemsysDoCacheOp` line, or any NVRM line you do not know. Do NOT stop for `NVRM: memMap_IMPL: CPU mapping not
  supported for addressSpace: 0x1`: Hookshot's Linux path tries to hand each new block of the game's memory to the
  driver as a dma-buf, this driver refuses every one (the game falls back by itself), and the kernel prints the line
  for some of the refusals: usually once at the start, sometimes again later in a run (113 of them last night, no
  fault among them). Count them in your summaries; `hs-run.sh` prints the count as `nvrm=`.
  A second known kind since 2026-11-11 09:04: three lines in one second, `NV_ERR_NO_MEMORY ... _memdescAllocInternal
  @ mem_desc.c`, `... rmStatus @ system_mem.c` and `... pRmApi->Alloc(... ) @ nv_gpu_ops.c`: the driver was refused
  one large allocation of system memory (the machine's memory was fragmented: 50 GB available, no free block of order
  9 or 10 in `/proc/buddyinfo`) and went on; seen once before on this boot (2026-11-10 17:07), nothing after either.
  Count these per run too (they are inside `nvrm=`); they are not a stop by themselves. They become a stop when the
  run they fall into fails in any way, or when one run has more than three such events.
- **Never run with a synchronisation or safety mechanism switched off**, and never write through a mapping of video
  memory from a program of your own, without the main session's word.
- **Tests that crash on purpose must not leave core dumps.** Hookshot's checks crash fixture programs deliberately
  (`tests/test_linux_driver_fault_guard.py`, `tests/test_recorder_sync.py`'s broken variants, and any sanitizer,
  fuzz or mutation run of your own that ends in a signal). Each core dump raises a "process crashed" notification on
  the user's desktop: 107 of them in the night of 2026-11-10. Run `tests/run_all.py` only through
  `/home/mooki/Games/.hookshot-harness/hs-idle.sh <python> -I -B tests/run_all.py` (idle class, three slots, core
  dumps off), and a single test or program that may die by a signal through
  `/home/mooki/Games/.hookshot-harness/hs-nocore.sh <command>`. After your runs,
  `coredumpctl list --since '-30min' --no-pager` must show nothing of yours. Game runs keep their core dumps.
- **Full builds one at a time**: `flock /tmp/hookshot-full-build.lock` in front of the build-gate command and
  `HOOKSHOT_LIFT_JOBS=8` (the lift's workers take 4.8 GB each); the fast path (`nx2/build.py`) is not affected.
- **The session can die** (it did on 2026-11-10 at 23:20:53, with every agent): write your report after every
  result, not at the end; start anything long from a script file with `setsid nohup`, with its output in your files
  folder; before waiting for a job, check with `pgrep` that it is alive and look at what is already on disk.
- Anything that must outlive you is started from a script file with `setsid nohup ... < /dev/null &`, writes its
  output under your report's files folder, and is named in your report with what to read in it. Keep at most one
  waiter of yours in a gate at a time.
- Use `date` for every timestamp you write. Never edit a script that is running or queued (replace by rename). `/tmp`
  is a tmpfs and is lost at a reboot.

## Git

- Author `Michael Schienbein <7663497+mooki000@users.noreply.github.com>`: pass `-c user.name="Michael Schienbein" -c
  user.email="7663497+mooki000@users.noreply.github.com"` on each commit; never change git config. Before you report a
  branch: `git log --format='%ae %ce' origin/main..<branch> | grep -c -v users.noreply.github.com` must print 0 (only
  the GitHub no-reply address appears).
- **You never push, never open or comment on an issue or pull request, never post to Discord.** The main session
  does, after checking your work.

## Pull requests: the user's standard (2026-11-11)

The user wants every pull request at the level of his own earlier ones for the other port: "lots of detail and images".
`skill://hookshot-pr-evidence` has the form and the checklist; read it before you write a body. In short:

- **Collect the evidence while you work**, under `reports/<Topic>-files/`: the environment (system, GPU and driver, base
  and head commit, date, load), the test's lines on the branch and against main's source, the whole suite's totals
  with the named failures, every run's summary line, the log lines that prove the point, a table with one row per run,
  and pictures (before and after, or the feature's screen in each state). A failed check or an outlier is kept and said.
- **The body** (`reports/drafts/<Topic>-body.md`): first paragraph "**What this is for:** ... **What is measured:** ...
  **Not measured:** ..."; then Problem (the chain of causes), What changed (per file, and what is unchanged), How it
  was tested (result lines, tables, pictures with captions), Not tested, Risks, Overlaps
  (`/home/mooki/.agents/skills/hookshot-pr-evidence/scripts/pr_overlap.py --branch <name>`, hunks read), Questions.
- **Pictures**: several frames as one labelled picture with
  `/home/mooki/.agents/skills/hookshot-pr-evidence/scripts/panels.sh`; look at it; name it `hookshot-<topic>-<what>.jpg`
  and tell the main session, which uploads it.
- **An issue for every pull request**: search first; say in your hand-off which existing issue it belongs to, or give
  a draft of a new one in the form's headings (`reports/drafts/<Topic>-issue.md`) with the score and the hardware.
- Hand over the branch with its head, the title file and the body file with no placeholder left, then stop editing them.

## The public repository (since 2026-11-11)

The user shares his Hookshot tools and skills with other contributors in `mooki000/hookshot-workbench` (public, MIT;
checkout `/home/mooki/Code/hookshot-workbench`). It holds copies of the five `hookshot-*` skills, this brief, the run
wrapper and its helpers, the gates and the guard, and the step driver `hsap.py`; its `sync-from-live.sh` lists every
file. The main session copies, checks (`publish-check.sh`), commits and pushes; you never do. What that means for you:

- **A skill, this brief and every listed script are public text.** Write in them only what a stranger may read: the
  method, commands, measurements, traps. Nothing about the game's content (coordinates, flag, step and object names,
  routes, what stands where, counts from the world model): that goes into
  `/home/mooki/Games/.hookshot-harness/playthrough/NOTES.md`. Nothing about where the user's game files and saves
  came from: `/home/mooki/Games/.hookshot-harness/LOCAL-NOTES.md`. No key, no address, nothing about other people
  beyond what is on the tracker.
- The world model, the planner, the pilot, the save maker, saves, segment files, reports and drafts are **not**
  published. Do not move any of them into a skill folder or beside the listed scripts.
- When you change a skill or a listed script, say so in your final message, so the main session publishes it.

## Reporting

- Write your report to the path your task names as you go, so that a successor can continue from it at any moment;
  watch your own request budget and leave a hand-off before it ends.
- Every number comes from a log through a script (with asserts where a text will quote it); say for each which build,
  which settings, which load average. Look at every picture you cite and say what it shows. Say what is not measured
  and what is inferred.
- Log your own mistakes in `/home/mooki/Code/hookshot-wt/reports/LOG.md` as one dated line beginning with the time and
  your name in brackets.
- Your final message is read by the main session and partly by the user: the result first, in plain sentences, then
  what was checked and how, what is not proven, and what you need from the main session.
