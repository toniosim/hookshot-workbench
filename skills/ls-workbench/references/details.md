# Workbench details: donor builds, fixtures, Windows check, caches, disk and shell hazards

Reference material for `SKILL.md`; read the part the task touches.

## Donor builds: what `--dry-run` shows and the silent stops

- `nx2/build.py --dry-run` is the start-up with no lift: it lists the files the compile would read and fails on a
  missing one (`dry run: N files ..., M missing`). `lifted code ... (0 files)` there is not a broken donor.
- The new/cached split (`@@plan <new> <total>`) is printed only by the real compile, and only with
  `LONGSHOT_TIMES=<build_times.json>` (`nx2/make_game.py`'s record of earlier builds), so it cannot be read beforehand.
- `nx2/kit.py`'s `wait_for_quiet` sleeps in 60-second steps while `<worktrees>/.bench-lock` exists (build and dry run).
- `make_game.drop_stale_objects` deletes the object cache when the compiler's first version line or
  `/usr/include/stdio.h` changed since the donor was built: an unseen hours-long rebuild. Try the build on a copy first.
- A newer main base can recompile every host unit and most lifted units although the lift identity is equal (new
  compile defines, host-source changes): predict a long build, not a minutes-long one.
- The tested form of the donor recipe is `/home/tonesi/hookshot-wt/reports/tools/wincross/native-resume.py` with the
  registered lift-identity proofs in `donors.json` beside it; `reports/BuildHeads-files/preflight.py` holds the per-head
  preflight and its summaries. Mirror their `HOME`, profile path and identity checks rather than the hand recipe in
  `SKILL.md` (a donor row for a head whose `nx2/` equals a lifted one needs a **wrapped** identity proof, not the bare
  `lift-identity.py` output).
- The version the game logs is `git describe --tags --always --dirty` of the build checkout (`nx2/version.py`; also
  `LONGSHOT_VERSION` or a `VERSION` file), so an assignment's quoted tag can be one release behind. Take the expected
  text from the build's own receipt or from `python -I nx2/version.py` in that folder, never from a literal.
- Unverified here, check on the head's `nx2/build.py` before relying on either way: whether the renderer objects hit
  the donor's cache from a work folder other than `<checkout>/work/build` (the renderer's profile is unpacked into
  `<work>/longshot_vk.shipped.profdata`; a comment on the object keys in `nx2/build.py` suggests the path is kept out of
  them, but two workers rebuilt the renderer objects from another folder).
- No registered donor matched a main whose lift inputs changed (`nx2/` lift files moved in the commits since the nearest
  donor): the fast path is gone. `reports/tools/wincross/lift-identity.py <tree> <donor receipt>` against every receipt in
  `donors.json` and `lift-bases.json` says so in 30 seconds; `reports/CoopIntegrate-files/build-linux.py` is a working
  template for a plain gated `make_game.py` build with the donor's profile inputs. For a co-op-line head the quick route
  is `reports/PortInviteUpnpRun-files/hold1/build_port.py --check|--copy|--inner` (39 s; its `targets.json` is the only
  file to change). Run every path a hold will use once game-free first (`--copy`): a chain whose build path was only ever
  `--check`ed failed in its first second. The lift key of a not-yet-built checkout needs the donor's unpacked exefs given
  by hand. `--check-only` leaves a 3.8 GB reflinked `work/check-*` folder (seen once): delete it.
- Whether two trees share a lift, in seconds and from no receipt: `python3 reports/LinuxTests-files/liftsrc.py <worktree>`
  prints the hashes of the lift's input files and of the HLE set (the reader `lift-identity.py` uses); diff two outputs.
  The key alone can mislead (`skill://ls-pr-evidence`, `references/recipes.md`, "Rebases and carries"). `lift-identity.py`
  also needs a receipt that carries `lift_process_environment`; a build made without one (the 1383 build's) cannot be
  proven with it.
- A renderer or host-only probe in minutes: `reports/LinuxTests2-files/hold/build_native.py LABEL WORKTREE EXPECTED_COMMIT`
  compiles the two products natively over a donor's finished work folder (the lift inputs are checked equal by hash first;
  no lift, no game; through the build gate); `reports/LeakHunt-files/build_native.py` is the copy with `--allow-dirty`.
  For a main whose `nx2/` equals a finished build's, `make_game.py --update` over a reflinked copy of that work folder and
  copy gave a whole copy in 260 s with a 1 s lift (`reports/Work562-files/build562.py`).
- A rebuild was killed by the system once (`lift.py`, signal 9, memory) while other agents were busy: `free -g` before
  `build.py`, then retry.

## Fixtures: text-cutting tests, build lists, fuzzing

- Many fixtures cut functions or tables out of source files by their text (`host/oot_coop.c` pieces by marker,
  `host/nn_fs.c`, `host/posix/win32_posix.c`, the language counts in `gpu/vk/menu_i18n.h`). After a rebase, a replay or a
  change inside such text, run them on the new head **before** any queued hold; `git grep -l '<changed file>' tests`
  lists the drivers that read it. A suite run on an older base is not the suite of the integrated head.
- A host `.c` file that another one uses must be added to every driver that compiles the other
  (`git grep -l coop_portmap.c tests` found eleven build lists). `gcc -MM -I host ... tests/<fixture>.c` lists a
  fixture's include closure without compiling. The suite shows a missing file only as a link error.
- The fuzz test (`tests/test_coop_fuzz.py`; its docstring lists the smoke, `--campaign` and `--replay`) stops each
  harness at its first crash, so a campaign that ends early found something.
- `python3 -I` leaves the script's own folder out of `sys.path`: a module placed beside a script must be imported after
  `sys.path.insert(0, HERE)`.
- A header that gains an include breaks every fixture that stands in for the included one, and a new function called
  from a host file that a fixture compiles needs a stand-in in that fixture (a host input file compiled by the
  background-input fixture): the feature's own tests show neither, the whole suite does.
- A diagnostic counter put inside a function that a fixture cuts out of the source by its text (`texture_frame`,
  `destroy_later`) breaks that fixture (`test_readback_timeout_reuse`: `rt_retired` undeclared): a diagnostic commit is not
  a pull request. No game-free test links all the host sources together: a duplicate global between two host files passed
  every fixture and failed only in the real link, so build the head (an incremental build through the gate) before handing
  it over.
- A branch's version gate keeps a two-session fixture from delivering anything until its test gate is switched off (the
  pattern is in `tests/coop_events_test.c`). A text-cutting fixture needs a marker per new function; a missing marker
  fails only at the fixture's compile.
- A fixture build that tries a sanitizer first falls back to a plain build without a word and prints only `compiled`:
  `compiled` without `with -fsanitize` means the sanitizer build failed (seen for `tests/test_oot_coop.py`: a
  `-Werror=format-truncation` under ASan inlining). Run it by hand with that warning off when ASan matters.
- A driver with both `--cc` and `--cxx` (`tests/test_menu_coop_tab.py`) compiles its C fixture with `--cc`: `--cc g++`
  fails on missing field initializers and looks like a regression. Edit nothing in a worktree while a mutation driver
  runs: its stages read the files and report a false "unbroken test fails".
- `tests/run_all.py` fills its tool placeholders (`{vulkan_headers}`, `{spirv_val}`) in `find_tools()`, which reads
  `RX_CPM`: a focused runner imports it instead of guessing paths.
- `hs-nocore.sh` sets exactly one byte as the core limit; a fixture that lowers its children's soft limit to 0 undoes it
  (the kernel then calls systemd-coredump: a journal entry and a notification). End a deliberate abort with `_exit(1)`
  or `prctl(PR_SET_DUMPABLE, 0)`, or `setrlimit` to 1, never 0 (`tests/test_coop_fuzz.py` does).

## Main's suite and the failing names

Whole strict runs of main showed 37 to 41 failing names on this PC on 17 Nov (compile errors in old fixtures,
`test_import_reach`, `test_linux_update`, ...). The count moves with the head, the load, the runner and where the tree
sits; the "7 inherited failures" an older assignment quotes were the subset that reads one renderer file. Quote no count
and compare none:

- Run main's commit **and your head** through the same runner in the same layout: `reports/tools/verify_heads.py OUT.json
  main=<sha> head=<sha>` (the test gate, a global suite lock, `--jobs 6`, its worktrees under `/tmp`). `LSV_PY=<python with
  FastMCP>` for a head whose tests import the MCP adapter: `--strict` fails a missing package.
- Compare the failing **names**. A name only the head fails is yours; a name both fail is inherited and is said by name.
- The layout changes the names. A worktree in the work area has the `Tooling` clone beside it; a `/tmp` worktree or a bare
  `git archive` copy has not, and `test_docs`, `test_bug_report*`, `test_cpu_report`, `test_crash_groups` and
  `test_hardware_report` then fail or pass differently (3 to 5 more names; a bare copy also needs `git init && git add -A`
  for `git ls-files`). Say which runner and layout each list came from.

At load 50 to 90 the idle gate alone held a whole-suite run for 8 minutes: for one change or a diagnostic use `--changed` or
`--exact`, and keep the whole suite for the head you hand over.

## The Windows-target syntax check

`BASE` is a git revision (the checker runs `git diff BASE -- tests`), not a worktree path. Exit 0: every captured compile
passed; 1: a failure; **2 (`INCOMPLETE`) is normal** whenever a changed driver skips Windows (`RUN_ALL_SKIP`), runs a
Python script or never reaches a compile call: those are listed as `UNJUDGED`. The checker answers success to every
captured compiler call, so it cannot judge a driver whose assertions need a compile to fail (a driver such as
`tests/test_option_ids.py` shows a failing unit for its deliberate negative case): judge that one with a real mingw
compile and say so. It finds drivers by the source files they read, so an unchanged driver of main's that reads a file
the branch changes joins the run; a failure main has too is inherited: run the checker on a worktree of the base
(`--test tests/<name>.py`) and keep both rows.

The checker's `-Werror` turns the mingw runtime's POSIX and CRT deprecations (`strdup`, `getenv`, `tmpfile`, `memcpy`,
`memmove`) into failures: a driver that compiles a cross-platform host file defines `_CRT_SECURE_NO_WARNINGS` and
`_CRT_NONSTDC_NO_DEPRECATE` for the Windows target, and a changed **old** fixture without them fails the check for its
old lines too (inherited: keep both rows). `--output` takes an absolute, new folder: a relative one is written inside
the checkout, leaves an untracked folder and fails a hold's clean-tree assertion. It compiles only what a driver that
runs on Windows includes: a new host file with only a Linux fixture is `UNJUDGED`; run a by-hand syntax check with the
llvm-mingw compiler and say so.

A fixture that includes the project's environment header after `<stdlib.h>` still needs `_CRT_SECURE_NO_WARNINGS` before its
**first** include: the header defines it only for its own include. The checker stops at the first command of a driver that
is not a compile (the run of its first fixture: `NOT TESTED: ... stopped before`), so a second fixture that the driver
compiles after running the first is never reached; its `COVERAGE:` line says so. Compile such a one by hand with the
llvm-mingw compiler and say so.

## Cold copies and warm caches

- A copy made by `nx2/make_game.py` has no `cache/` and no `.nv-cache/`: its first start prepares every shipped
  pipeline (about 38,800 `vk: start-up: N of M` lines, about 6 a second under a load average of 70, 4 to 7 minutes on
  a quiet card) before the game can be played. A pair hold on a fresh clone loses its first sessions to it; a pilot hold
  needs `RX_VK_PRECOMPILE=1` (a test build does not precompile otherwise) and `anchor_timeout_s = 600`; a preparation
  run shorter than that is incomplete. Registered builds in the state folder carry empty driver caches; the `-title`
  copies carry warmed ones.
- Reflink a warm copy's `cache/` and `.nv-cache/` into the new copy (`cp -a --reflink=always`: seconds, where a copy of
  the same tree takes minutes), **only when the shader translator is the same**. The renderer is built with a translator
  stamp (`nx2/translator_files.py`, `stamp('gpu/vk')`, folded with the GPU data into `cache/*_vk_pipelines.stamp`) and
  the game drops its caches whole when it differs. Same stamp means no change between the warm copy's head and the new
  head under `gpu/vk/eden`, `gpu/vk/sirit`, `gpu/vk/compat`, `gpu/vk/vk_shader.cpp`, `gpu/vk/vk_bank.cpp` and
  `gpu/vk/vk_state.h`: `git diff --stat <warm head> <new head> -- <those paths>` is empty (or the two checkouts print the
  same `stamp`). Settle it before choosing the base commit: every warm copy built before a translator change prepares
  cold. A copy rebuilt from new sources over an old cache keeps the old stamp, so it is not a warm base.
  A warm copy is valid when it was built from the same translator sources **and** its `cache/*_vk_pipelines.stamp` is newer
  than the last commit that touched them (`git log -1 -- gpu/vk/eden gpu/vk/sirit gpu/vk/compat gpu/vk/vk_shader.cpp
  gpu/vk/vk_bank.cpp gpu/vk/vk_state.h` against the stamp file's mtime): on 17 Nov every copy built before the latest such
  commit prepared cold, so a new copy always did (4 to 7 minutes).
- Check a clone is warm before queueing: the stamp, the `.built` marker and the prepared-list files `cmp`-equal to the
  warm copy's, the same names and sizes in `cache/`. A game that starts from a copied save is playable in about 30
  seconds from a warm copy, not the 80 a pilot's frame counter suggests.
- A cache also fills per area: a clone warmed in one dungeon compiled a second dungeon's pipelines at its first visit
  (the `vk: start-up` counter again; seen once): a scenario in a new area budgets that.

## Clones, disk and the end of a topic

- Plain `du` is wrong here: reflinked clones make `~/Games` read 19 TB on a 1.9 TB disk. `btrfs filesystem du -s --raw
  <path>`: its "Exclusive" column is what deleting that path frees; take `df` before and after. `/home` is its own
  subvolume (snapper covers `/` only and needs root).
- When your topic's report is written, delete what you made, by exact path: your game copies (`rm -rf` of the clone is
  the clean-up; `hs-run.sh` has none), the `work/` and build folders of your worktree unless a registered donor needs
  them, and the `shots/`, `auto/` and frame folders you do not cite. `ls -a` shows the dot-folders of owned copies:
  check the deletion is complete. In eleven days the harness made about 350 game copies and 86,000 frames and filled the
  disk to 98 percent.
- The weekly cleaner (`reports/tools/diskclean`, run by Main) keeps what an active topic folder, `exclude.txt`,
  `sessions.json`, a queued hold or a citation names. A citation of a whole `runs/`, `shots/` or `auto/` folder pins
  every frame below it: cite single files (copy the one picture into the topic's `-files` folder). Raw nightly runs and
  regression-hunt `framelog.bin` files (about 1 GiB each) are disposable once the cited `result.json` and pictures stay.
- The registry (`sessions.json`) has no unregister, and a build is not listed the moment its hold ends (the folder's name
  and its `receipt.json` are the authority): deleting a registered build's folder needs its entry removed first
  (`reports/tools/diskclean/regbuilds.py` does both for Main).
- `cp -a --reflink=always` across filesystems fails per file with one line each (`/tmp` is tmpfs): keep dry-run copies
  on the same disk and pipe such a command to `| tail`. `cp -al` of read-only assets (an unpacked romfs, 186,000 files)
  took 2 seconds where the reflink copy took 4 to 8 minutes under load; a 45 GB reflink clone took 40 to 60 seconds.
- A hold's pictures are most of its disk: three holds of 100 to 200 s wrote 6.7 GB of 1280x720 PNGs with `--shots 120`
  (`hsap.py --shots <presents>`: one picture every N presents, default 600); 240 is enough for a panel. Make the panels
  (the analyzer's `--panels` needs the shots) before pruning, then delete the rest.

## Tool-shell hazards

- A persistent shell keeps `set -e` from an earlier command, and a later loop then stops at its first `grep` miss: `set +e`.
- Parallel tool calls race on what they share: two that run `git add` or `git commit` in one worktree meet `index.lock`
  (the `&&` chain then skips the rest silently; run one worktree's git one call at a time); a `read` of a picture issued
  in the same turn as the command that makes it fails with "not found".
- Calls that background themselves (`sleep`, deleting a 57,000-file game folder, `( cmd & )`) return before the work is
  done: check the result before the next step. `setsid nohup script > log 2>&1 &` is what survives the call.
- Not installed on this PC: `bc` and `/usr/bin/time`; use Python arithmetic, the shell's `time` or two `date +%s`.
- A branch worktree has no `reports/` folder: it is `$W/reports`, the parent of all worktrees.
- A Python process that has run a hold keeps the hold's SIGTERM handler, so a test process that called `Hold.play()` no
  longer stops on a plain `kill`: stop it by pid with SIGKILL.

## Attaching gdb to a running game (seen once)

`ptrace_scope` is 1 here, so gdb attaches only to a game that allows it: a one-line diagnostic patch calling
`prctl(PR_SET_PTRACER, PR_SET_PTRACER_ANY)`. The game's binary loads in 0.5 s and carries the `f_<address>` symbols
(about 82,000), so `watch -l`, `break *f_...` and backtraces by function name work. A failing breakpoint `commands`
block aborts a batch script and detaches gdb without telling the game: use a Python `condition N $fn(...)` function
that returns 0, and a `continue` loop.
