---
name: ls-scripted-play
description: >
  Drive an owned, gated, windowless LS or HS run through the control bridge or the capability-selected hsap
  drivers. Choose the sampled-state or legacy file tap, wait for fresh controllable state, send inputs, capture
  pictures, inspect steps and keep a save only after proving it resumes. Use for controller-free play, test saves,
  area tours and routes that need position. Read ls-workbench first.
---

# LS scripted play

**LS / HS:** published skill IDs use `ls-*` and workbench configuration uses `LS_WB_*`; live paths stay unchanged
until a separate host cutover (see `ls-workbench`). The shared resolver selects the actual
executable, log and client; missing/mixed identities refuse. Naming proves no optional capability: the renamed main
client lacks session `show`/`log`/`stop`; those examples require the separately supported session-layer client.

**Use for:** scripted input, state samples and save-backed routes. Read `ls-workbench` and the agent brief.
On this Linux workstation game runs are windowless; a separately authorized remote Windows test does not change that.
Never use the upstream client's unwrapped `launch` to bypass the harness/gate.

Set `WT` to the selected owned LS or HS worktree before deriving the client path.

```sh
H="$HOME/Games/.hookshot-harness"
W="$HOME/hookshot-wt"
P="$W/deps/python/bin/python3"
source "$H/hs-names.sh"
hs_names checkout "$WT" || exit
CTL="$HS_CTL"  # scripts/hookshot_ctl.py or scripts/longshot_ctl.py, selected automatically
```

Set `COPY`, a new `TAG`, a new evidence directory `OUT`, and a new private `LIVE` directory outside
`$COPY/runs/$TAG`. Create `LIVE` with `mkdir -m 700 "$LIVE"` before writing its steps. `hs-run.sh` deletes a reused
run tag. Keep saves, routes, flag names, coordinates, goals and world-model facts in `$H/playthrough/NOTES.md` and
local run files, never in this public skill or a tracker.

## 1. Choose the transport, then reach controllable play

1. Pin the binary and inspect its actual capabilities. The ordinary bridge supplies input, status, options, waits,
   screenshots and quit. It does **not** imply a sampled position/camera stream. What `status.game` carries depends on the
   head: forge main's `docs/control.md` lists `frame`, `t`, `pos`, `facing`, `camera`, `event`, `loading`, `age`, `life`,
   `prompt` and `music` (one snapshot from Link's update, kept with its old `frame` when no update came for 250 ms: title,
   pause, load; no time of day: the live command `!cheat 100+h` sets the hour h, 0 to 23, and an area reload shows it), an
   older base only event/loading/age. Read the head's `docs/control.md`.
2. For steering, select `playthrough/hsap.py` only with the control-bridge `oot` sampled-state extension. It requests
   `subscribe` with `events:["oot"]`, `every:6`, selected `flags`, and `changes:true`. An unsupported subscription
   fails; there is no silent fallback. For older `HOS_OOT_STATE_FILE` builds, choose `hsap_file.py` explicitly.
   A build with neither tap supports neither driver.
3. Choose a copied save and `--boot continue`, or a fresh profile and `--boot newgame`. `--boot none` sends no boot
   presses; it still waits for fresh quiet state. Put the owned route's steps in `$LIVE/steps.txt` **before launch**;
   no steps means the driver keeps waiting. Use an `end` step to request completion.
   From a save, `--boot continue` presses A every 2 s (`newgame`: 0.75 s) from the title until Link has been calm for 3 s (a
   map, `event` 0, `loading` 0), and a press acts on whatever is in reach: a save made next to a person or a prompt starts
   the talk that holds Link (240 s lost, the game never reached play), one next to a door opens it and its event moves Link
   (43 m before the first picture), and in a place whose event never ends (a menu that stays open) the calm test never
   passes. Start such a scenario 8 to 10 m from anything that reacts, and read `state.jsonl`'s first row (the saved place),
   not the first row after control; or take the variant that presses A only until the first state with a map:
   `--boot load` in `reports/BossPoints-files/hold2/code/playthrough/hsap.py`.
4. Launch through the driver, which invokes `hs-run.sh` and its GPU gate. Use a bounded wall time with shutdown
   reserve; do not wrap it in another gate:

   ```sh
   "$P" -I -B "$H/playthrough/hsap.py" "$COPY" "$TAG" 450 --live "$LIVE" --save "$SAVE" --boot continue
   ```

   For a fresh profile omit `--save` and use `--boot newgame`. For the legacy tap replace only `hsap.py` with
   `hsap_file.py`. The boot timer begins when the game log appears, not while queued.
   `--env NAME=VALUE` (repeatable) gives the game `hsap.py` starts a switch after `hs-run.sh`'s own options (not with
   `--game-sock`).
5. Require `gameplay` and fresh `state` events in `$LIVE/out.jsonl`; require the intended map and known-false event
   and loading state. The bridge driver's `$LIVE/state.jsonl` is a client journal, not a second game-output channel.
   Read `game.frame` for sample age, not the reply envelope's current frame. Retained state through a pause/load is
   not evidence that control returned. Inspect a capture before claiming the intended scene.
6. A run's wall time counts from the game's start, boot included: 15 to 20 s on a quiet card, 50 to 113 s under load
   (the shader programs are prepared on every start; `gameplay_after_s` in `summary.json` says what it cost). A plan's
   `wall` is the boot plus the route plus 60 s; a pilot segment's `budget_seconds` is game time counted from the game's
   clock 0 (a duel goal: from its first decision), not from control, so a pilot attached to a game that has already run
   longer than its budget ends at once. A copy that never
   booted needs a preparation start first (`skill://ls-workbench`, "Cold copies and warm caches"). The solo driver's
   `wall + 60 s` for a pilot is too short beside another game (`SOLO_HOLD_EXTRA=150` worked).

The sampler's `every` counts game presents, not wall time. Its selected flags are bounded; missing/unreadable values
are null, enum values are hashes. Changes establish a new baseline on subscription. Read the extension's matching
`docs/control.md`; do not copy an extension-only command into an ordinary client's CLI. In particular, the selected
base client's `watch --help` has **no `--changes` option**. `hsap.py` sends the subscription itself.

A session-layer launch's `--ready bridge|present|play` is distinct from this driver. `play` requires a presented frame,
its play heuristic and known-false event/loading; it neither presses through the title nor guarantees sample freshness.
The upstream `--profile test` isolates its user folder and environment file but not all inherited settings/caches.
Only a configured workbench session adapter supplies the workbench's gates, isolation and wall bound.

### What the sampled state shows

- Three journal shapes exist: the bridge driver's rows, the observer's `{w, frame, game: {...}}` (`event` and `loading`
  booleans, `age` a word) and the older `HOS_OOT_STATE_FILE` rows. Read a folder's first lines before parsing it. The
  sampler's `t` and `present.csv`'s `return_ns` are one clock. A sample is a poor stall gauge (its poll is late when the
  pilot or the machine is): use the present trace.
- The tap sends **nothing while a map loads**: a load is a hole in the samples (4.5 s in one teleport) with no `loading`
  sample, and a gap of 1.5 s or more with no `step` event of yours is a map change. A flag with no name is watched as
  `0x<hash>` and shows in `game.flags` under that key. After `hsap`'s `gameplay` event comes a `state` event that is the
  state before any step: a driver that places Link reads the state after its own `wait` step.
- At the Game Over screen the bridge `state` **stays `play`**: a death is not "the state left `play`". Read the sampled
  `life` at 0 for several seconds, or the game's own log line. `relaunch` re-executes the **same process** on Linux (same
  pid, same socket) and starts a new one on Windows, which a log follower or pid watcher must follow (`docs/control.md`).
- The co-op clock (time of day) runs 120 game seconds per real second, a day in 12 real minutes, and stands in the pause
  menu and for 1 to 3 s at each map load (`docs/oot/environment.md`): a wait on the day clock is minutes, not hours.

### Conversations, events and interaction steps

- Pressing A beside a person starts a conversation each time one ends, and an open conversation or cutscene (`event`
  true) turns every later teleport, travel and chat step into a refusal and holds Link's body. A runner presses A only
  while `event` is true, stops when it is false, and checks `event` false before any step that needs control. A scene can
  last minutes (45 s for the first segment of one, over 2 minutes in all, then a conversation): timed presses cannot
  finish it reliably, and the case builder has no "press until the event clears" step.
- Step timeouts count game time at the real frame rate: a chest message took about 22 s and a first conversation 42 s of
  wall time at 30 frames a second, and 30 s of wall was 12.5 s of game time at 25: a `chest` or `talk` timeout of 14 to
  20 s ends `timeout` although the thing worked. A chest's item is given while its message is open and its flag flips
  about a second after the message closes, so a give judged by the flag is late. A result word (`played`, `picked`) is
  not proof: a flag, a count or a picture is. An overlay that shows only while a button is held (the item wheel) needs
  the button held through the next inputs.
- A co-op side folder holds `auto/` (periodic pictures named by present count), `shots/` (named ones) and `state.jsonl`
  (rows with `w` and a nested `game`). The sampled state has no actors: what is in front of Link comes from the prompt and
  an offline world model. A teleport or an age change reloads the map as an event, so arrival is control in the other map,
  and the first seconds after a map change are a fade from black: look at pictures after control, not at arrival. The
  bridge teleport to Hyrule Field arrives in the tunnel at the Lost Woods exit, not in the open field: a picture of the
  open field needs a walk out of it.
- A text box can hold Link from the load (`event` 1, no hearts in the HUD; a boss door shows one for as long as nothing
  presses A): `advance` (A every 1.2 s until it closes) is the first step of such a run, `interact` ends `timeout` while a
  text is still open (`advance` after it), and a picture before any input (`shot` as the first step) is what shows it.
  `enter` presses A at the first prompt on the way, a Talk prompt included (a market gate has a person in front of it): a
  scenario that wants a load zone and no conversation walks (`walk`, or `through` points).

## 2. Send an input, observe the effect, capture and stop

For a run already started through the gate with `HOS_CONTROL` set to its private socket:

```sh
"$P" -I -B "$CTL" --json status
"$P" -I -B "$CTL" --json press A --frames 8 --exclusive
"$P" -I -B "$CTL" --json stick L 0.5 0 --frames 8 --exclusive
"$P" -I -B "$CTL" --json wait present --frames 1 --timeout 10
"$P" -I -B "$CTL" --json shot "$OUT/after.png"
```

The client defaults to `$HOS_CONTROL`; use `--sock` explicitly when selecting among owned runs. Do not send input to
an arbitrary discovered socket. An input reply means its frames completed, **not** that the scene changed or play
resumed. Record sent, accepted, observed state change and inspected picture separately. Serialize requests per socket;
keep streaming subscriptions on their own connection. Reconnect after an uncertain reply without replaying the input.
The game refuses a `HOS_CONTROL` socket whose folder is not the user's or is writable by group or others (`/tmp` itself)
and a socket path over the 107-byte `sun_path` limit: make a short `mkdir -m 700` folder, not one deep in a run folder.

- Bridge `stick` uses x/y in [-1, 1]. `sequence --hos` uses seconds and milliseconds; without it, times are frames.
  `--exclusive` covers the input, not an unlimited physical-device lock. `release` clears this client's pending input.
- File input is `HOS_INPUT_SCRIPT='<seconds>:<buttons>[/<milliseconds>],...'` or `--input` to `hs-run.sh`.
  Buttons: `A B X Y L R ZL ZR PLUS MINUS LS RS LEFT UP RIGHT DOWN`; stick edges: `LUP LDOWN LLEFT LRIGHT RUP
  RDOWN RLEFT RRIGHT`. Combine with `+`; the default hold is 200 ms. Unknown file tokens can be ignored silently.
- `HOS_INPUT_FRAME_CLOCK=1` advances file time at 60 game presents per second. `HOS_INPUT_EXCLUSIVE=1` suppresses
  physical input while the script is active and for its grace period, not forever. `HOS_INPUT_LIVE` reads complete
  lines every 30 ms and keeps only the last `!cheat` of a poll (space such commands 40 ms apart: `LIVE_GAP` in `hsdebug.py`);
  each line's times start when read. Keep that file outside the disposable run directory.
- `hsap.py` routes ordinary `press`, `stick`, `push` and `raw` through the bridge. Its `--analog`/`HSAP_ANALOG=1`
  selects exact steering angles. `hsap_file.py` needs an extra `LX=`/`LY=` file-parser extension for analog pushes;
  the bridge's analog support does not imply that extension.
  `raw` splits its argument on spaces, so a multi-word live line (a `!command a b`) is appended to `<live>/live.txt` by
  the orchestrator itself (seen once).
- Read `option get` before `option set`; setters use the real menu and persist. Restore only your owned copy's
  intended settings. Debug travel/age operations need observed binary support and an authorized disposable profile.
  Never enable `HOS_CONTROL_MEM=rw` or use memory writes as an input substitute. The exception is a task that names a
  debug tool (the pilot repository's `hsdebug`, or the MCP's `session_flag_set` where registered): it runs on a
  disposable profile that opted in to `memory: rw`, and its edit reaches a save only after the game's own autosave (a
  few seconds after a map change, "Saving..." in the picture): wait for that before copying a save.
  Named settings are not action-row selection. A head whose `vk_menu.cpp` has the `ROW:<internal name>` token selects a
  visible row in the current tab by it, not a translated label or another tab: the co-op line's heads have it, forge
  main's has none (`git grep -n 'ROW:' gpu/vk/vk_menu.cpp` on your head); elsewhere the script is keys only. Verify the actual menu before confirming.
  The token list is in the game repository's `docs/development.md` (`INS UP DOWN LEFT RIGHT ESC ENTER TABL TABR`, the
  pad's face buttons `PADS PADE PADW PADN`, `TYPE:<text>`, and while a field has the keyboard `HOME END BACK DEL`):
  there is no D-pad token (`TABL`/`TABR` are the tab keys). The script is a fixed timetable of one token a frame with no
  feedback. Its seconds start at the menu's first tick, the game's first presented frame (log line `vk: present: WxH`),
  not process/bridge uptime: 5 to 29 seconds after launch in six sessions (the co-op runner assumes 6; a loaded PC or a
  second game is later), so wait for the log line you need and do not assert a fixed uptime, and remember the
  run's wall limit counts from the game's start: a script needs its last mark plus that lag and the kill reserve. A
  `ROW:<name>` that is not shown selects nothing and the next `ENTER` presses whatever is selected (it is also skipped
  while a field has the keyboard): script an accept or a leave only where the row is certain. `ESC` both opens a closed
  menu and closes an open one. The menu keeps its tab between opens, so `TABL` reaches the Co-op tab only on a
  process's first open and a restarted game starts on the first tab again. A field edited again keeps its text: empty it
  with `BACK` repeated.
  Turning **Debug tools** on from a scripted menu meets a modal "Enable Debug Tools?" whose answer starts on Cancel: the
  script sends Right, Right, Enter (seen once; the keys are timed, so a script that skips the question never reaches the tools).
- Use bridge `shot` for Vulkan captures. The drivers' legacy `shot` step writes `!shots` to live input; in the selected
  base that command targets the WebGPU renderer, not Vulkan. Do not treat its step completion as a captured PNG.
  The renderer queues bridge shots (one worker had 16 waiting, each `after` a game frame): n requests at once give n
  consecutive pictures, so a flicker watch can run from a watcher on its own socket. A shot costs a frame in the frame
  log: take pictures outside measured windows.
  Bridge shots omit Insert-menu and co-op labels/chat; the automatic menu-overlay stream (`RX_VK_SHOT_MENU=1`) is
  offscreen-only and does show them, so a windowless proof of a label or chat line uses that stream.
  An explicitly authorized real-window presentation/overlay test needs an OS capture of the exact game window.
  A chat line leaves no log line; only a picture shows it (a stream of one picture every 180 presents caught the
  typing field, the sent line and the received line). A Windows run has no such stream (`shot_menu && dev.offscreen`):
  capture the owned window. The stream never scrolls a list: see `ls-workbench`, "Pictures and logs".
  Inspect the actual pose/chat pixels; a timed input or capture filename is not proof of a stride or delivery.
  A periodic overlay picture is the only picture that shows a chat line or a name label, and a line stays on screen
  about 8 s: the default of one picture every 900 presents (about 15 s) misses it, so a case that must show a line sets
  `shot_every = 120`.

For a periodic observer, record sample timestamps and check actual gaps, including input/capture phases; a sleep after
observation is not a fixed cadence. Sequential captures of two games are not simultaneous evidence.

### Owned session logs and shutdown

A control-session `RUN` is a directory with `manifest.json` and `log.txt`. It is **not** an hs-run directory with
`hookshot_log.txt` or `longshot_log.txt` (the shared reader uses `log_path`). Use `--run` only for a manifest made
by the session layer. With that supported client, `show` and `log` also work after exit.

```sh
"$P" -I -B "$CTL" --json --run "$RUN" show
"$P" -I -B "$CTL" --json --run "$RUN" log --lines 40
"$P" -I -B "$CTL" --json --run "$RUN" log --since "$CURSOR" --expect "$TEXT" --timeout 10
"$P" -I -B "$CTL" --json --run "$RUN" stop --timeout 10
```

Take the log's byte cursor **before** the action whose new line matters. `--expect` requires `--since`; `more` means
continue from the returned cursor. A cursor past EOF refuses. MCP log cursors are opaque and are not these byte offsets.
There is no workbench MCP log-line wait tool yet; `run_logs` is a bounded read, not an `expect_log` replacement.

A successful stop requires observed game/owner/wrapper exit. If graceful quit times out, the owned game remains running;
only an authorized disposable run may use `stop --terminate`. Save draining is unsupported: never call it a clean save.
For `hsap`, let its owned runner stop the game before ending the gate. A summary game exit 143 can mean its deliberate
SIGTERM; shell exit 0 or an `end` event alone does not prove the route's assertions passed. A solo run's exit 137 is not
always a crash: it is also the wrapper's SIGKILL after its grace for a game whose `end` step was not done first; read the
driver's `end` event and `kernel.txt` (an out-of-memory line) before calling it one.

## 3. Run a local route and prove a saved checkpoint

Read `$H/playthrough/NOTES.md` for the local world model, planner, segment schema and save library. Never send their
contents to a remote model service. Use the local rules decider. The public drivers stay standard-library-only;
the **local** pilot/probe import `requests`, which the pinned build Python lacks. The local save utility also imports
Python 3.14's `compression.zstd`. Use the installed system Python for these local tools; do not install into shared
Python or system packages.

```sh
python3 -I -B "$H/playthrough/probe.py" "$ROUTE" --tag "$TAG" --copy "$COPY" --save "$SAVE" --wall 450
python3 -I -B "$H/playthrough/pilot/pilot.py" run "$SEGMENT" --decider rules --tag "$TAG" --copy "$COPY" --save "$SAVE" --wall 450
```

Choose **one** of those launchers for a new tag. Their defaults can exceed the hold limit; pass `--wall` explicitly.
The probe invokes `hsap.py`, so it needs the socket sampler too. An older file-tap build is not a compatible fallback.
Use `setsid --wait nohup` for a saved managed launcher and retain its child receipt (not for children that test
signals: see `ls-workbench`); one chain queues at a time.

The pilot's package, goals and benchmark are described in `play/README.md` (live: `$H/playthrough/`), and so is its learning
side (the tactics and lessons libraries, the route library, `selfplay.py`, `--tactics`, `--lessons`). A tag is never
reused (`pilot.py` refuses an existing `pilot/runs/<tag>`), the launch asks the GPU gate itself (a hold must not hold
it), and a pilot hold's folder name needs `Pilot` for the dispatcher (`skill://ls-hold-chain`). A pilot can take pictures
through a second short connection to the control socket (`shot` with an absolute path; the socket path is in the run's
`env-used.txt`, which the run writes after its gate admission: a chain that polls for it waits for a file newer than its own
launch, or uses a new tag, since a reused tag can show the previous run's dead socket path until the wrapper has cleared
the folder), with the run's `--shots` folder as the fallback. Run every script a hold starts once under `python3 -I`
and keep the hold's frozen code beside `hs_names.py` (`skill://ls-hold-chain`).
A pilot's vision questions go only after control began and never on a black picture: the model answers `blank`, `void`,
`missing textures` and `corrupt` yes on every load screen and fade (25 of 25 looks), and "a text box" gets cinematic
subtitles unless the question says they are not one.

1. Inspect every `step.result`, `bad` event and goal check. `walk`/`run` can be reached, stuck, timed out or held.
   A later step after a stuck one proves nothing about its intended target. Use the local planner instead of a
   straight walk across obstacles. An event-held action needs an explicit rule to resume and fresh control evidence.
2. The debug `save` step requires its build's save extension. Require the reply plus a newly written `progress.sav`,
   not an old slot. A short delay is not a save-drain barrier. Keep the run's disposable `user/save/` after exit.
3. Continue from that copied user folder in a new bounded run and inspect the scene and state. Only then mark the
   checkpoint proven in the local library. The save tool is `$H/tools/hs_make_save.py` (not under `playthrough/`):
   `--help` lists `--case` and `--time` (a named test-save case and the time of day) besides `--lib-add` (needs a new
   `--name`) and `--lib-proven` (records the observed result and optional `--presses`). Do not rewrite library entries
   merely to make a route pass.
4. Split a longer route into separate bounded holds, each continuing from the preceding run's copied user folder.
   Never hold the card while waiting for a model, another lane or manual decisions.

### Saves for a start place: `hs_make_save.py`

- `--start <Area>:x,y,z,yaw` (yaw in radians), `--case` and `--time` make a save for a place and a time of day. `--from`
  takes a library entry, not a folder, whatever its `--help` says; `--out lib:NAME` of an existing name makes `NAME-2`
  and never replaces (remove the folder first). A `--give` of a meter item sets a stand-in maximum and leaves the current
  value, where a real pickup writes far more: set the maximum and the value with `--flag` after it and read the state
  back. The options file's enum values are set the same way (`--from <save> --flag OptionData.<name>=<value>`).
- A save is a place to start from, not a position at the thing: the scenario needs an **approach** leg to the target and a
  gate that shows it was reached before the interaction (a fight scenario without one swung at nothing for the whole
  run), and the game's own load can put Link at the room's start rather than at the door the save names. Stand 1 to 2.5
  m before the target on the side its prompt shows from, facing it; for a place a run got stuck at, 8 to 10 m of the
  library's own track before it. A map name need not change between a corridor and its boss room: gate on the music or
  a position.
- A save made with `--start` for a new place is untried until a game has booted from it: an entry's README does not say
  (`selfplay.py` warns for a proven save without a proof note). Prove it (`--lib-proven`) before building a route on it.
- A generated save is only as good as its flags. Before a hold, check it game-free: (1) the lock flags of the door the
  scenario needs, (2) any person or enemy placed within 10 m whose presence flag your quest step does not clear, (3) the
  equipment (`--give` does not equip: set the equip flag with `--flag`), (4) the order of the quest steps that arrival
  events set themselves, read from the event flows. Each of the four failed a save once; a scan of the placements near the
  start point takes seconds (`reports/BossPoints-files/load.py`). A door that still does not react is read from the flow
  that opens it: start the player on the side the story arrives from.

## Co-op pairs: the runner

Two games, or a pilot beside a TAS game, run through `$H/coop-play/coopplay.py`; its `--help` and the docstring of
`cpcase.py` document the case file. `plan CASE` validates it and prints the schedule without a game or a lock; `run
CASE --out DIR` queues one waiter behind the quiet-window lock, then the measuring lock (shared unless the case says
`measuring = "exclusive"`), then one whole-card gate command both games are children of; `check DIR` re-runs the
detectors; `DIR/waiter.json` holds the waiter's pid and command. `run` copies the runner's own source and the case
into `DIR/runner-src` **when it queues**: an edit made while it waits does not run, and a half-edited module at that
moment does. The longest hold is 1,100 seconds and a case that needs more than 480 says `run.hold_seconds`. A case's
menu steps (`chat`, `accept`, `leave`, `rules`, `menu`) are built from the tokens in `cpcase.py`'s `menu_tokens`.
`[run] pose_trace = true` writes the dense pose trace that the jank detector and `cppose.analyse_pair` read (Linux sides
only). `hsap.py --env NAME=VALUE` (repeatable) gives its own game a switch; in a co-op case a game's setting goes in the
case's `[room.settings]` or `[sides.X.settings]`. The runner's own tests are plain `python3 -I -B test_*.py` files in
`$H/coop-play`, not part of `tests/run_all.py`.
A menu step is compiled into the game's start-up script and can only use `from = "start"` (a game's menu clock runs
from its own start). The game refuses every `HOS_COOP*` variable that comes from `HOS_ENV_FILE`: they must be in the
process environment, which matters to any harness that restarts the game: a restart keeps the first exec's environment, so a
per-exec `RX_VK_MENU_SCRIPT` goes into the run's `env-file.txt`, which `hs-run.sh` overwrites with a placeholder just before
the gate. Such a harness builds the run folder by hand and calls `hs-run.sh --inner` inside the gate
(`reports/Carry68f-files/hold/fold68-tooling/duel/duel_session.py` does). The runner's `--help` also describes the
`<win>-install` and `<win>-probe` commands for a Windows side (`skill://ls-windows-laptop`).

Case facts read from `cpcase.py`, `cpexpect.py`, `cpdetect.py` and `cpsession.py`:

- `run.hold_seconds` is both the gate command's `timeout` and the runner's abort deadline: the session faults 45 s before
  it, so set it about 100 s above the planned end.
- `check = "log"` takes its `pattern` as a **regex** (a literal `(` is an unterminated group; `count` is exact, `min` and
  `max` bound it). `check = "state"` cannot read a flag (the keys hold dots). `saves_unchanged` compares the run copy after
  the run with the library save before it, so it fails whenever the game autosaves (an area title, a scene). Chat
  expectations need `win_slack_s` of 8 or more where a side's log reaches this PC by a poll (up to 6 s late). An anchor
  named by an expectation that is never reached ends the session as a fault, not a failed row.
- `coredumps.txt` is `coredumpctl list` for the **whole machine** over the session, so another worker's crashing test
  raises `crash`, and the deadline kill (SIGKILL, exit 137) of a game that never booted looks like a crash: ask "did
  any game reach control" before "did a game crash". A failing `frames` detector fails the verdict even when every
  expectation passed: list the startup windows you accept in `[detectors] tolerate`.
- A menu step (chat, leave) runs on its own side's menu clock, which starts at that side's first presented frame: a
  side launched second (a 62 s gap plus its start-up) ran its chats and its leave 7 to 9 s after the planned second, so
  anchor no pause or body step to a menu step. Read a step's `t_planned`, not the time recorded after its span. A chat
  typed while the other player is dropped is lost by design. `consent = "auto"` puts the bodies at about 106 to 110 s
  where the two-press menu consent takes about 250 s: use it when a case needs the path layer, not the consent screen.
  `HOS_COOP_TEST_SET` takes at most 8 items (a ninth is dropped with a `config` warning).
- `kind = "solo"` with the co-op switches in `sides.A.env` (appended after the runner's `HOS_COOP=0`) is a one-game
  co-op-on run. A read-only driver beside the runner finds the sockets in `tempfile.mkdtemp(prefix='coopplay-')`: set the
  runner's `TMPDIR` to a short private folder and glob it. The runner ends when its last planned step plus the tail has
  passed (a `mark` step keeps it alive) and its menu scripts own the menus until the room is accepted: press nothing
  before both logs say `room accepted`.
- `cppose.analyse_pair` and `cppose.replay` compare two sessions on the same messages, which removes the noise between
  sessions; `[run] pose_trace` feeds them.
- A deliberate stall of one game is `SIGSTOP`, then `SIGCONT` of its own game pid for a few seconds (6 s in the hold that
  used it): it reproduces the log signature of the two-game stall (`reports/PvpNight-files/src/night_session.py`,
  `run_stall_stage`).
- To test a co-op path-layer change (STUN, hole punching, relay fallback, a LAN relay behind a router forward) without the
  internet, the Windows laptop or the LAN relay, use the NAT lab: `skill://ls-nat-lab`.

## Game-free reader checks

These use fakes, not a game or a GPU. Run each named test through the core-dump wrapper; keep the real output.
On the public workbench the driver folder is `play/`; in the live harness it is `playthrough/`.

```sh
"$H/hs-nocore.sh" "$P" -I -B "$H/playthrough/test_hsap.py"
"$H/hs-nocore.sh" "$P" -I -B "$H/playthrough/test_hsap_file.py"
"$H/hs-nocore.sh" python3 -I -B "$H/playthrough/pilot/test_pilot.py"
```

`HSAP_TEST_MODULE=<file>` selects a staged driver for its matching test. Never replace a driver used by a queued or
live run; stage it, test it, then replace only when no process depends on it. A fake-driver pass is not a game route,
a tap-compatible binary, a real save barrier or a visual proof.

## MCP routes

Use the workbench skill's **MCP routes** for operator setup and the canonical `uv run --project mcp ls-wb`
entry. From that repository root, `call TOOL --args JSON` invokes a table tool; authorized mutations need
`--profile operate`. Keep the same state root: separate CLI processes share the owning broker.
A launch Job ends only when the session ends. Read `.events.events[]` / `.kind` for `bridge_ready`, then observe
`menu` or `play` for 30 further frames using a state predicate with `stable_frames:30` before first input/capture.
Boot input is refused. The opening cutscene reports `loading`; menu/play waits can time out during a drawn cutscene,
and input may be refused. Inspect advancing frames/captures; do not mislabel that as a frozen bridge or replay input.
Missing sampled-state freshness remains unknown. `broker stop` ends owned sessions, not only a client wait.

| Step | Shell route | MCP tool (group; integration) | What it saves |
|---|---|---|---|
| Start/stop | Gated `hs-run.sh`/driver; owned runner stop | `session_launch(build_id, profile_id, wall_seconds, idempotency_key)`, `session_stop(run_id, reason, idempotency_key)` (session; integrated) | Owns disposable run, gate and stop receipt; no clean-save claim. |
| Queue/receipt | Gate tickets, process identity and child receipt | `queue_status(device="gpu", job_id=job_id)`, `job_read(job_id)` (status; integrated) | Joins the job to its live gate request without PID guessing. |
| State/readiness | `"$CTL" status` (shared-selected LS/HS client); driver samples | `session_state(run_id)`, `session_wait(run_id, predicate={"kind":"state","state":"menu"}, stable_frames=30, idempotency_key=key)` (session; integrated) | Separates drawable-state readiness from fresh control; use `controllable` only with sampled-state support. |
| Input then observe | `press`/`stick`/`sequence`, then status/wait | `session_input(run_id, steps, units="frames", idempotency_key=key)`, then `session_state(run_id)` (session; integrated) | Typed units, deduplicated submission and separate effect evidence. Not a route planner. |
| Capture/settings | `shot`, `option get/set` | `session_shot(run_id)`, `session_options_get(run_id)`, `session_options_set(run_id, values)` (session; integrated) | New capture paths and bounded settings; unsafe setting classes refuse. |
| Read/wait for log | Session `log --lines`; `log --since --expect` | `run_logs(run_id, last_lines=40)` (evidence; integrated); **no log-wait tool** | Bounded retained reads. Keep the shell cursor wait for a new line. |
| Copy/inspect save | Disposable save copy; `slots` | `save_clone(save_id, idempotency_key)`, `session_saves_list(run_id)` (session; integrated) | Registered-source copy and metadata only. No autosave or resume proof. |
| Inspect route evidence | Run log, captures and labelled panels | `run_faults(run_id)`, `evidence_panels(images, label, idempotency_key)` (evidence; integrated) | Signature classification and private panel artifacts; inspect them yourself. |
| Find previous proof | Read local notes/registered reports | `knowledge_search(query, collection="reports")`, `workbench://reports/{id}` (knowledge; integrated) | Bounded revision-pinned report access. The URI is a resource; private game data stays private. |

## Traps seen on this machine (the user's PC; kept from the 2026-11-10/11 notes)

- A `set -e` in the shared persistent shell stays on and cuts later commands short ("exit 1, no output"): use `set +e`.
- The world builder's packed-index reader returned `KeyError` for a missing file and `navmesh.py` relies on it; a plain
  folder reader must too (`world/game_files.py`).
- The fast build path needs `RX_RELEASE=1` and `RX_PGO` at the play profile the checkout names (`work/build/` holds
  `longshot_pieces.prof` or `hookshot_pieces.prof`, see `hs_names`); check the `object keys:` line with `--dry-run` first.
- The GPU gate's queue can hold many runs (8 to 20 on a busy day of the author's): a segment may wait hours before the
  game starts, and the pilot waits up to 6 h for `gameplay`, so start it from a script with `setsid nohup`.
- **One hold keeps the card for at most 8 minutes of game time:** give a probe or segment `--wall 470` or less and chain
  longer plans from one script, each piece its own `hs-run` (its own gate turn) continuing from the user folder the last
  one left (`<copy>/runs/<tag>/user`); `skill://ls-hold-chain`. No `--exclusive` without the user's word for that hold.
- The full game-free checks go through the test gate: `/home/tonesi/Games/.hookshot-harness/hs-idle.sh <python> -I -B
  tests/run_all.py --jobs 8` (idle class, core dumps off); a single test that may die by a signal through `hs-nocore.sh`.
- Keep game PIDs: `timeout` can move children into a different process group; stopping only the shell can strand games
  outside the gate.
- Scope includes the whole acceptance checker, not only process exit: some old co-op scripts returned 0 with failed
  assertions. Record sent, accepted, state change and inspected picture separately; do not weaken an assertion to rescue
  an earlier run.
- `test_recorder_sync.py` and `test_display_pointer.py` are timing-dependent under load: compare at a quiet hour before
  blaming a branch.
