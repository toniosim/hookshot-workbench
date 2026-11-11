---
name: hookshot-scripted-play
description: >
  Drive Hookshot (the Ocarina of Time Switch 2 recompilation) by script on this machine: HOS_INPUT_SCRIPT and
  HOS_INPUT_LIVE presses, the state tap (Link's area, position, facing, camera, cutscene, health, flags as JSON lines),
  getting from the title into play, the step driver hsap.py, the local world model and route planner, the segment
  pilot and how a segment keeps a save, and the traps. Use for controller-free play, test saves at story points, area
  tours, or any run that must know where Link is. Read hookshot-workbench first (building, hs-run.sh, gates).
---

# Hookshot scripted play

Read `skill://hookshot-workbench` first: building a copy, `hs-run.sh`, the GPU and build gates, pictures, saves.

**This file is public (`mooki000/hookshot-workbench`) and holds the method only.** What was read from or learned about
the game's content (places and coordinates, flag and step names, object names, routes, segment goals, counts from the
world model) is game data: it goes into `/home/mooki/Games/.hookshot-harness/playthrough/NOTES.md`, which stays on this
PC, and never into this file, git, an issue or a pull request. The world model, the saves and the segment files stay
under `/home/mooki/Games/.hookshot-harness/` for the same reason.

Written 2026-11-10 by PlayHarness-2, brought up to the first game runs by PlayHarness3 on 2026-11-11; the report
`/home/mooki/Code/hookshot-wt/reports/PlayHarness.md` has the evidence. **Marks:** [run] = run in the game (the run's
tag named); [offline] = run only without the game (tests, simulated game); [read] = read in the code only.

## Input: what main has

- `HOS_INPUT_SCRIPT='<s>:<buttons>[/<ms>],...'` (hs-run.sh `--input`): times from the first controller read. Buttons `A B
  X Y L R ZL ZR PLUS MINUS LS RS LEFT UP RIGHT DOWN`; sticks only at their edges: `LUP LDOWN LLEFT LRIGHT RUP RDOWN RLEFT
  RRIGHT`, combinable (`LUP+LRIGHT`); hold 200 ms unless `/<ms>`. Unknown names are ignored silently. [read:
  `host/nn_hid.c` `parse_presses`]
- `HOS_INPUT_LIVE=<file>`: lines appended while the game runs, read every 30 ms, each line's times from when it is read;
  a line still being written (no newline) waits. `!cheat <n>` queues a Debug-tools action taken at Link's next update
  (2/3 mark and return, 100+h time, 200+ pouch, 999 age, 1000+i teleport, 3000+ inventory; `host/hos_main.c`
  `oot_update_player_cheats`), `!shots <ms>`, `!dump`, `!synclog`. Keep the file outside `runs/<tag>` (hs-run.sh
  empties that folder). [read]
- `HOS_INPUT_FRAME_CLOCK=1`: script times in game frames at 60 a second (steadier under load). `HOS_INPUT_EXCLUSIVE=1`:
  only the script drives. [read; both set by hsap below]
- **What input cannot do yet:** in main, no analog stick values (eight directions at full push only); branch
  `input-script-analog` (a draft pull request) adds `LX= LY= RX= RY=<-32767..32767>` tokens, the same as #926's control
  socket; the harness copy `.hookshot-h-play2` has them (hsap `push`, `--analog`). No text or menu helpers (the pause
  menu, shops and the ocarina are button sequences you must write; PR #2048 has pause-menu sequences); no save command
  in main (the harness build's `!cheat 996` works [run newgame-2, house-2]).

## The state tap (pull request #2292, branch `play-harness`; not in main yet)

Branch `play-harness` (worktree `/home/mooki/Code/hookshot-wt/play`, commit d7a29e88 on origin/main 49f75dc8) adds
`host/oot_state_tap.c`. `HOS_OOT_STATE_FILE=<file>` writes one JSON line every `HOS_OOT_STATE_EVERY` presents (6) from the
update of Link, so only while he is updated (none on the title, the load list and the first part of the opening; two
gaps of 18 and 67 presents inside one scene) [run newgame-2, house-2]:

    {"t":..,"frame":..,"map":"<map name>","pos":[x,y,z],"facing":deg,"camera":deg,"event":0|1,"loading":0|1,
     "child":0|1,"life":quarter hearts,"max_life":..,"rupees":..,"prompt":"Empty|Open|Crawl|...","music":"BGM_..."}

`frame` is the present count, the same number as a picture's name `vk_<present>.png`: `playthrough/tapcheck.py
<state.jsonl> <shots>` prints the line nearest each picture, the runs of map/event/music and the values per field.
`facing`/`camera`: degrees, 0 toward +z, 90 toward +x. `event`: 1 through cutscenes and talks, 0 in control [run
newgame-2, house-2, yard-1]. `HOS_OOT_STATE_FLAGS=Name,0xHASH,...` adds `"flags":{...}` (an Enum value reads as
`"#<murmur3 of the value's name>"`); `HOS_OOT_STATE_CHANGES=1` adds `"changed":{"0x<hash>":value}` for every
Bool/Int/Enum/UInt flag that changed: the way to find which flag an action sets. Checked in the game, field by field,
in the report ("The tap's fields against the pictures"): right are map, pos (= the save's place at each save), facing
(in play; -180 in a cutscene), camera (by steering), event, child, life, prompt (`Open` at a door), music, flags; at 0
only: rupees; not exercised: loading. **During a scene `pos` is where the scene parks the Player**, not where Link is
drawn. Check offline: `python -I -B tests/test_oot_state_tap.py --cc gcc` [offline, passes with gcc and clang].

Harness builds (fast path of the workbench, `RX_RELEASE=1`, `RX_PGO`; `object keys: ... flags f08f29989d, hot flags
fc9905f579`): `/home/mooki/Games/.hookshot-h-play` = branch `play-harness-local` cea9ba2f (worktree
`/home/mooki/Code/hookshot-wt/play-local`: play-harness + PR #2048 merged + a local-only `!cheat 996` that asks the game
for its own autosave) [run]; `/home/mooki/Games/.hookshot-h-play2` = `play-harness-local2` b9eff490 (the same +
input-script-analog) [built 2026-11-11 07:19]. PR #2048 adds `!cheat 998` (a `cheats: state:` log line) and
`!teleport <map> <start> [<event>]`. Build [run]:

    cd /home/mooki/Code/hookshot-wt/play-local      # work/build is a reflink copy of bench/work/build
    /home/mooki/Games/nx2navi-build-slot env RX_CPM=/home/mooki/Code/hookshot-wt/deps/cpm OOT_WORK=$PWD/work/build \
        RX_RELEASE=1 RX_PGO=$PWD/work/build/hookshot_pieces.prof \
        /home/mooki/Code/hookshot-wt/deps/python/bin/python3 -I -u nx2/build.py --standalone --jobs 16
    cp work/build/sa/build/hookshot work/build/sa/build/hookshot_vk.so /home/mooki/Games/.hookshot-h-play2/

(compiled in 8-11 s; 48 s with the gate.) Keep one binary per copy while a chain runs on it: build into a new copy
(`PlayHarness-files/build-fast2.sh` makes one by reflink without the `runs/`).

## From the title into play

- New game: A every ~0.75 s from the title (the log's `a frame: N draws` reaches 15) until the state lines show Link in
  a map with `event` 0 and `loading` 0 for three seconds (PR #2048's `new_game` method; hsap `--boot newgame`) [run
  newgame-2: control at present 23622, about 400 s after the start at 60 fps; the opening's text advances with A].
- A save: copy it as `--user` (hs-run.sh copies, never in place) and A every 2 s from the title (hsap `--boot continue`)
  [run house-2, yard-1: in play about 30 s after the title]; the workbench's `5:A,8.7:A,11.7:A,15:A` with the frame
  clock also works [run by HsWorkbench].
- hsap's boot limit (900 s) counts from the game's start (its log appearing), not from hsap's: the GPU gate may hold a
  run for hours (newgame-1 timed out in the queue before this was fixed; newgame-2 waited 2 h 21 min).

## The step driver: hsap.py (public)

`playthrough/hsap.py <copy> <tag> <wall s> --live <dir> [--save <user folder>] [--boot newgame|continue|none]`: runs
one game through hs-run.sh (headless, gate) with the live file, the tap, the frame clock and exclusive input, and plays
steps from `<dir>/steps.txt`, answering in `<dir>/out.jsonl` (`gameplay`, `step` with result, `state`, `bad`, `done`).
Steps: `walk|run x z [radius r] [timeout s]` (closed loop on the tap's position and camera; reached / stuck / timeout /
**held** (an event held Link 0.6 s); the stick's handedness is checked and flipped while walking; `--analog` or
`HSAP_ANALOG=1`: exact angles with `LX=`/`LY=`, a build that has them), `press B [ms]`, `stick up|down|.. ms`, `push lx
ly ms`, `raw <live line> <wait s>` (e.g. `0:LUP/1400,0.5:X/120`), `cheat <n>` (a debug-tools action, answers the
log's `cheats:` line), `until flag N=V|area A|prompt=P|control [timeout s] [press A every s]`, `wait s`, `climb
[timeout s]`, `save [timeout s]` (`!cheat 996`, done when a `progress.sav` changes [run]), `report s`, `shot`, `end`.
`python3 -I test_hsap.py` [offline: all passed, against a simulated game; `HSAP_TEST_MODULE=<file>` tests a copy].

## The world model, the planner and the pilot (local: they carry game data)

These stay on this PC until their code is separated from what they read out of the game; the commands, the model's
contents and every game fact they showed are in `playthrough/NOTES.md`.

- **World model and planner** (`playthrough/world/`): built from your own dump (areas, nav meshes, exits, objects,
  event flows, the story's steps). `plan(area, from, to)` gives a walkable route as `run x z` steps, or why there is
  none (`needs-door`, `needs-climb`, `needs-crawl`, `needs-jump`, `off-mesh`, `not-connected`).
- **`playthrough/probe.py <script> --tag <tag> [--save <lib name>] [--copy <copy>]`**: a scripted segment without
  decisions: hsap steps one at a time, plus `plan x z [y Y] [radius R]` (the planner from where Link is; a door on the
  way: into it, A at `Open`, plan on through doors), `unless <flag>=<v> <step>`, `stop-if life<=N`; the rule **an
  event holds Link -> A every 1.5 s until control** after any step. Output `playthrough/runs/<tag>/probe.log`.
- **`playthrough/pilot/pilot.py run segments/<seg>.toml --tag <tag> [--save <user folder>]`**: the decision loop (a
  rules decider by default; a model decider only after a segment works with rules, with spending caps and a ledger;
  the key is read from the user's file and never printed). Its run goes to `pilot/runs/<tag>/` (`transcript.jsonl`,
  `summary.json`, `live/`), the game's to `<copy>/runs/<tag>/`. `python3 -I pilot/test_pilot.py` [offline: all
  passed]. A segment file (TOML) has `save` (`kept:<tag>`, a library name, or a path), `boot`, `save_after`, `watch`
  and its goals.
- **Keeping a save:** `save` (or `save_after = true`) asks the game for its own autosave; hs-run.sh keeps
  `<copy>/runs/<tag>/user/save`; the newest slot is what Continue loads. Put it into the local save library with
  `tools/hs_make_save.py --lib-add <copy>/runs/<tag>/user --name <area-what> ...`, then `--lib-proven <name> "<what
  the picture shows>" --presses '...'` after a run continued from it [run, twice].

## Traps met

- A `set -e` in the shared persistent shell stays on and cuts later commands short ("exit 1, no output"): use `set +e`.
- The world builder's packed-index reader returned `KeyError` for a missing file and `navmesh.py` relies on it; a plain
  folder reader must too (`world/game_files.py`).
- The fast build path needs `RX_RELEASE=1` and `RX_PGO` at `<worktree>/work/build/hookshot_pieces.prof`; check the
  `object keys:` line with `--dry-run` first.
- The GPU gate queue on 2026-11-10 evening held 8 to 10 runs, 20 on 2026-11-11 morning: a segment may wait hours before
  the game starts; the pilot waits up to 6 h for `gameplay`, so start it from a script with `setsid nohup`.
- **One hold keeps the card for at most 8 minutes of game time** (Main, 2026-11-11): give a probe or segment `--wall 470`
  or less and cut longer plans into pieces chained from one script, each its own hs-run (its own gate turn), each
  continuing from the user folder the last one left (`<copy>/runs/<tag>/user`; example `PlayHarness-files/run-chain3.sh`).
  No `--exclusive` without Main's word for that hold.
- The full game-free checks go through the test gate: `/home/mooki/Games/.hookshot-harness/hs-idle.sh <python> -I -B
  tests/run_all.py` (idle class, core dumps off); a single test that may die by a signal through `hs-nocore.sh`.
- `test_recorder_sync.py` and `test_display_pointer.py` are timing-dependent under load (one failed on origin/main
  alone at load 98, the other in a loaded full run): compare at a quiet hour before blaming a branch.
- A probe that walks into a talk or scene without a rule stops dead (yard-1): every script needs the held rule.
