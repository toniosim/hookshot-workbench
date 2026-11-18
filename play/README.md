# play/: the step drivers, the pilot and its benchmark

Everything here plays a game that is already running on your machine. Nothing in it is game data, and nothing in it
needs a network except the one optional model backend (below). The game, its saves and every file made from them stay
yours and stay local.

| Path | What |
|---|---|
| `hsap.py` | The game side. Starts one game through `hs-run.sh` (the GPU gate, headless) and plays steps on it through the control bridge: walking, timed presses, waits, the interaction steps (`interact`, `chest`, `talk`, `advance`, `pickup`, `enter`, `faceat`, `ztarget`, `camera`, `ocarina`, `item`, `rendezvous`), watched flags, the sampled state (`oot` subscription). Every step ends with a result word and what changed. `python3 -I -B play/hsap.py -h` lists the steps. |
| `hsap_file.py`, `tapcheck.py` | The earlier file-tap driver, and the helper that puts a run's samples beside its pictures. |
| `pilot/pilot.py` | The pilot. Plays one *segment* (a TOML file of goals with targets) by deciding, whenever the game side has no step left, which candidate step comes next. Writes a transcript, a summary and a route file per run. |
| `pilot/deciders.py` | `rules` (a fixed policy, no model, no network), `replay` (a recorded transcript) and `openai-decisions` (a model chooses among the candidates; an optional planner call asks for route help). |
| `pilot/interact.py` | The interaction goal kinds (`open_chest`, `both_open_same_chest`, `collect`, `talk_to`, `enter`, `play_song`, `fight`, `explore_interact`): their candidates, their rules policy, their conditions. |
| `pilot/recover.py`, `pilot/humanize.py` | The stuck ladder, the per-map bad-point memory and the guard in front of the decider; seeded human-like movement (`--humanize 0..3`). |
| `pilot/vision.py` | The pilot's eyes: at chosen moments a fixed set of questions about the game's own picture goes to a vision model (`--vision on`). |
| `pilot/metrics.py` | The numbers of a run, from its own files: stuck steps per km, time to each goal, decisions per minute, cost per minute and per goal, interactions, looks. |
| `pilot/openai_api.py`, `pilot/standin.py` | The one place that talks to the API (key, caps, ledger), and a loopback stand-in server for tests. |
| `pilot/follow_feed.py` | Keeps one pilot's follow file from the other pilot's state journal (two pilots in one co-op room). |
| `pilot/tactics.py`, `pilot/tactics_seed.py`, `pilot/lessons.py` | The tactics library (ways out of a stuck place, keyed by the cause of the block, ranked by how often each worked, every attempt written back with its context), the seeding of that library from earlier runs, and the few short lessons put into a planner's request. |
| `pilot/routelib.py`, `pilot/routes.py`, `pilot/frontier.py` | The route library: what every run learned about where Link can walk, kept per map; its command line; and the frontier push that starts from the farthest walked point and tries the alternatives a stuck cause suggests. |
| `pilot/selfplay.py` | The nightly self-play hold: it puts the pilot a few metres before the open stuck places of the route library where the tactics library knows least and lets its ladder try what has been tried little there. No model, no human. |
| `hsap_items.py`, `hsdebug.py` | The item steps of the game side (`wheel-select`, `use-item`: choose the item the item button uses, and use it; they need your item table), and the game's debug tools from a command line and from Python for disposable runs (teleport, age, time of day, items, flags, a coordinate `warp`, a save snapshot), each action read back from the game. |
| `pilot/placement.py`, `pilot/hud_text.py`, `pilot/live_panel.py`, `pilot/overlay.py` | A segment's `[place]` table (Link put at a map, an age and an hour before the first decision); the pilot's decisions as a panel on the game's own screen; the same facts live in a terminal beside the game; and drawn on the game's pictures after the run (stills, a contact sheet, a video). |
| `pilot/drivers/`, `pilot/mcp_server.py`, `pilot/mcp_agent.py` | Who chooses the next step, behind one interface with fallbacks: the decisions model, OpenRouter, any OpenAI-compatible endpoint, an outside agent through MCP tools, a recorded input replay, the fixed rules. |
| `pilot/scenario.py`, `bughunt.py`, `bugpacket.py`, `burst.py`, `hunt.py`, `inputlog.py`, `score.py` | Bug hunting: a targeted test written down (`ls-scenario/1`), the detectors that read what a played session left behind, repro packets with a deduplication key, bursts of pictures for the flicker check, the input recording, the hunt that plays N sessions in one hold, and the scorecard of a round. |
| `worldmodel/` | The builders of the offline world model from your own game files (areas, exits, objects, flags, gates, event flows, the story's steps, nav meshes) and its path planner. Code only: the names and patterns it needs are in a tables file you write. |
| `bosspoints/` | Test start points just outside the places you want to test, built from one local table: saves, scenarios, a timed hold's step files and an analyzer of the finished hold. Code only. |
| `playbench/` | The capability scoreboard: a fixed set of small cells, the arms that play them, a referee that judges on the game's own state, a results store, a trend table and chart, and the nightly job. Its own `README.md` has the details. |
| `bench/` | The benchmark course and its runner: `course.py` (entries and arms), `mkcourse.py` (cuts the entries' segments from your own), `ghost.py` (a leader that walks a route for the follow entry), `run.py` (`plan`, `play`, `report`, `sheet`). |
| `test_*.py`, `pilot/test_*.py`, `bench/test_bench.py`, `playbench/test_playbench.py`, `worldmodel/test_worldmodel.py`, `bosspoints/test_bosspoints.py` | The game-free tests. |

## What you supply, and what stays private

The repository has no segment, no save, no route, no world model, no song or prompt list and no key. You make or
supply these locally; the code finds them next to itself or through the environment, and the folder's `.gitignore`
lines keep them out of a commit.

| Private input | Where the code looks | Without it |
|---|---|---|
| A built game copy (a folder named the way `harness/hs_names.py` names copies) and its save library (user folders) | `--copy` / `PILOT_COPY`; the segment's `save` (a library entry, a user folder, or `kept:<tag>`) | nothing to play |
| Segments (`pilot/segments/*.toml`) | the path you give `pilot.py run` | nothing to play |
| (the world model itself, built from the rows above) | read from `PILOT_WORLD`, else `play/world/` | no `near` objects, no planned routes: straight lines and the prompt only |
| Your tables for the world-model builders (names and patterns of the game's objects, flags, events, quests), the game's extracted files, readable flag names | `world/tables.json` or `WORLD_TABLES`; `--game` or `WORLD_GAME`; `world/flag_names.json` or `WORLD_FLAG_NAMES` | the builders refuse, naming the file and the schema (`worldmodel/tables.py`) |
| The data the builders make (`world/`: `objects.json`, `nav/`, `story.json`, ...) | `PILOT_WORLD`, else `world/` beside `worldmodel/` | see the world model row below |
| Your item table for the item steps (item names, the flags of the choice and of the stock counts, the wheel's order) | the JSON file `HSAP_ITEMS` names (schema: `hsap_items.SCHEMA`); no default | `wheel-select` and `use-item` answer `bad`, naming it |
| The game's own source, for `hsdebug.py`'s item numbers and flag layout | `hsdebug.py game-info --source <your checkout> --out <file>`, then `--info <file>` or `HSDEBUG_INFO` | the debug tools that need the lists say so |
| Bug-hunt settings: the game copies' name prefix, the main lane's two lock files, your forge page and its lock | `HUNT_COPY_PREFIX`, `HUNT_QUIET`, `HUNT_MEASURING`, `SCENARIO_FORGE` (`https://HOST/OWNER/REPO`), `SCENARIO_FORGE_LOCK`; none has a default | a plan, a queue or an issue import is refused, naming it |
| Your start-point table, your save tool and library | `bosspoints/table.local.json` or `BOSSPOINTS_TABLE`; `HS_MAKE_SAVE`; `BOSSPOINTS_SAVES` | the tools refuse, naming what is missing |
| Prompt words the game really uses | `pilot/prompts.json` or `PILOT_PROMPTS` | the generic verbs only |
| What the benchmark's six placeholder entries stand for (your segment, its goals, a save, a scripted route, a leader's route) | `bench/course-local.json`, or the file `PILOT_BENCH_LOCAL` names: `{"<entry id>": {"source": ..., "goals": {...}, "save": ..., "ghost_source": ..., "ghost_goal": ..., "tas": ...}}` | the cells are `MISSING` in `bench/run.py plan` |
| Songs (name to note buttons) | `pilot/songs.json` or `PILOT_SONGS` | a goal names its notes itself |
| The songs by pitch (1 to 5), the confirmed order of the five note buttons, the flag a warp song sets, and the name of the song that moves the time of day | `pilot/chapters/song_pitches.json` or `PILOT_SONG_PITCHES` (keys `_buttons`, `_arrive_flag`, `_time_song`; or `PILOT_NOTE_BUTTONS`, `PILOT_WARP_FLAG`, `PILOT_TIME_SONG`) | a warp-song or ride goal offers no song, and a wait for day or night only waits |
| The caps file `pilot/caps.json` | the pilot's own folder | `--decider openai-decisions` says so and the run plays on the rules |
| The main lane's lock files (for `selfplay.py` and `frontier.py` when they queue a hold) | `PILOT_QUIET_LOCK` and `PILOT_MEASURING_LOCK`; no default | the waiter is refused, naming what is missing |
| The route and tactics libraries (`routelib/`, `tactics/`, the self-play folder) | `ROUTELIB_DIR`, `PILOT_TACTICS_DIR`, `PILOT_SELFPLAY_DIR`, else beside the harness | the pilot plans with the world model alone and learns nothing |
| The scoreboard's private settings (game copies, locks, folders, key file, tracker address, cells with their saves and proofs) | `playbench-local/` (`playbench/README.md`) | the scoreboard refuses, naming what is missing |
| The key | `OPENAI_API_KEY`, or a mode-600 one-line file named by `PILOT_OPENAI_KEY_FILE` (default `$XDG_CONFIG_HOME/ls-pilot/openai.key`) | `rules` and `replay` do not need one; `--decider openai-decisions` says `no key` and the run plays on the rules |
| Run output (`pilot/runs/`, `pilot/ledger.jsonl`, `pilot/cache/`, `bench/runs/`) | made by the tools | |

Transcripts, pictures, ledgers, bad-point files and cut benchmark segments are game-derived or machine-private: keep
them out of commits and posts.

## Running the pilot

A game-free check that everything imports and the tests pass (no game, no network, no key):

```sh
cd play
for t in test_*.py */test_*.py; do python3 -I -B "$t" || break; done
```

`pilot/test_pilot.py` runs most of the others; a duel-segment check there is skipped when `pilot/segments/duel*.toml`
(private) are absent, and says so.

One segment, with the fixed policy (no model):

```sh
python3 -I -B play/pilot/pilot.py run <segment.toml> --decider rules --tag <new tag> --copy <game copy> --save <user folder> --wall 400
```

A tag is never reused (`pilot.py` refuses an existing `pilot/runs/<tag>`). The launch asks the GPU gate itself: do not
wrap it in another one, and keep a hold within the workbench's limits. `--wall` counts from the game's start; a segment's
`budget_seconds` counts from Link being in control (`gameplay_after_s` in `summary.json` says what the start-up cost).

With a model:

```sh
export PILOT_OPENAI_KEY_FILE=<a mode-600 file with the key>     # or: export OPENAI_API_KEY=...
python3 -I -B play/pilot/pilot.py run <segment.toml> --decider openai-decisions --planner --tag <new tag> --copy <game copy> --save <user folder>
```

What leaves the machine, and only with `--decider openai-decisions`: the request bodies written to the run's
`transcript.jsonl` (the state line as JSON, the goal and target names, what was tried, the candidate steps). With
`--planner` the planner's questions too; with `--vision on` the game's own frame, downscaled, with one fixed instruction
text and fixed questions: no path, log line, flag or coordinate. The key is read at the moment of each request, sent
only to the API host, scrubbed from error texts and never printed, logged, written to a transcript or put on a command
line. A stand-in server (`--api-base http://127.0.0.1:<port>/v1`, `pilot/standin.py`) never gets the real key.

### Caps and the ledger

`pilot/caps.json` (yours to write; the pilot reads it before every request and stops asking when a limit is reached):

```json
{"per_run_usd": 3.0, "per_night_usd": 50.0, "total_usd": 4000.0, "planner_share_of_night": 0.4,
 "model": null, "planner_model": null, "vision_model": null, "vision_backend": null}
```

The limits above are the ones the pilot is run with (3 USD a run, 50 USD a night, 4,000 USD in all): a run stops asking at its own
cap, a night at the night's, whoever spent the rest. They sit above what the benchmark measured (about 0.003 USD a minute
for the cheaper arms, 0.08 USD a minute for the flagship model, 1.64 USD for the dearest 13 minute run). There is no built-in
default: a tree with no `pilot/caps.json` plays on the rules.

Every request is one line of `pilot/ledger.jsonl` with the token counts the API reported and the cost computed from them
at the prices in `openai_api.py` (named `Price`s; update them when the published prices change). `pilot.py ledger [--run <id>]`
prints what a run spent. `PILOT_PLANNER_MODEL`, `PILOT_VISION_MODEL` and `PILOT_VISION_BACKEND` override the file for one run.

### Interaction goals, recovery, human-like movement, eyes

* Goal kinds, the prompt the game shows (`Open`, `Talk`, `Check`, ...) as the sure answer to "would A do something", and
  the near probe from the world model: the docstring of `pilot/interact.py`. A goal is met by the game's own evidence (a
  flag, a rupee or item count, a map change, the battle music, a message read to its end), never by a button having been
  pressed; a `play_song` goal that names a `flag` is met by that flag only.
* `recover.py`: a move that ended stuck is answered without a question by a ladder (sidestep, back up and come from an
  angle, roll, hop, next route point, local re-plan); where it happened is remembered per map and later routes bend round
  it. A guard in front of the decider takes the one valid candidate without asking, does not ask again about a state that
  did not change, and turns a long run of identical answers into recovery. `--no-recover` gives the older pilot.
* `humanize.py`: `--humanize 0..3` (default 2 for an exploration run; a segment can set its own; 0 sends every line as made),
  seeded by `--humanize-seed` or the run id.
* `vision.py`: `--vision on [--vision-every <s>] [--vision-backend decisions|responses] [--vision-model <m>]`, default off.
  The pictures sent are kept in the run's `vision/` folder with one row per look.

### Learning from earlier runs: tactics, lessons, the route library, self-play

* **Tactics** (`tactics.py`): the recovery ladder's rungs are entries of a catalogue, each applicable to some causes of a block (a ledge, a
  person's text, a crowd, a door's wrong side, a wall, ...). `recover.py` asks the library for the order to try them in; every attempt is
  written back with the map, the age, the cause and the geometry round the place. The score is `(wins + prior * K) / (attempts + K)`, each
  attempt weighted by how alike its context is, the prior being the static order's scaled by the cause's pooled success rate: an empty library ranks as the
  fixed ladder always did. `tactics_seed.py` fills the library from earlier runs (`seed`) and measures it offline (`evaluate`, leave one run out).
  `--tactics ranked|fixed|explore|off`, `--tactics-readonly`, `$PILOT_TACTICS_DIR`.
* **Lessons** (`lessons.py`): before a planner call, the few most similar past blocks and what finally worked there, as short sentences in a small token
  budget (`--lessons on|off`, `$PILOT_LESSONS`; `$PILOT_LEARN=off` switches both off, so a scoreboard arm can name its own switches). Off, or with a library that
  has seen nothing like the call, the request is exactly what it was before.
* **The route library** (`routelib.py`, `routes.py`): tracks, verified edges, stuck points with a cause, map links and the targets' frontier, kept per map
  in a private folder (`$ROUTELIB_DIR`); with it set, `pilot.py` plans with the library's known way first and imports its own run when it ends.
  `routes.py` imports finished runs, shows what is known and prints a route; `frontier.py` plans, checks and runs a push for a target
  (and queues its one waiter); both go through the game copy and the gate like any other run.
* **Self-play** (`selfplay.py`): `plan`, `check`, `saves`, `run`, `queue`, `stop`, `report` and `nightly`. A hold is at most 1,100 s, one session after another,
  each a `pilot.py run` with the rules decider; every attempt goes into the tactics library as source `selfplay`. It refuses a copy that is not warm or not
  stamped, a spend over the caps and a second waiter beside a live one.

Game-derived data (maps, places, saves, the libraries) stays in the private folders; the code names none.

### Debug tools, placement and the panel

* **`hsdebug.py`** (the game's debug tools, for a disposable run only): a command line and a Python module that teleport to a destination the game lists,
  switch age, set the clock, give, take or toggle an item, read and set flags, health, rupees and magic, mark and return, write a coordinate `warp`,
  and snapshot or restore a run's save. Every action prints one JSON object read back from the game, and `effect` says whether it was `verified`
  (the state read back is what was asked), `requested`, `partial`, `not_applied` or `unconfirmed`. It refuses a game that is not a throw-away run
  (`--run <run folder>`). Writing memory needs the game started with `HOS_CONTROL_MEM=rw`. The item numbers and the flag layout are not in the file:
  `hsdebug.py game-info --source <your game source checkout> --out <file>` reads them from your own source and writes a private file that you pass with
  `--info` (or `HSDEBUG_INFO`). `hsdebug.py` needs `hs_names.py` (the harness folder, or `harness/` in this repository), as `hsap.py` does.
* **`placement.py`**: a segment's `[place]` table (`to`, `age`, `hour`) puts Link at a map, an age and a time of day through `hsdebug.py` before the
  pilot's first decision, with the effects read back from the game. `hsdebug.py` is found beside `hsap.py`, or at `$HSDEBUG_PATH`.
* **The panel** (`hud_text.py`, `--hud on|off`, `HSAP_HUD=0`): the pilot writes its decisions as at most 14 short ASCII lines to `<live>/hud.txt` and
  `hsap.py` sends them to the game's own screen with the bridge's `overlay` command (at most four a second, cleared at the end). A game that cannot
  draw it is noted once and the run goes on exactly as without; the decisions, steps, timing and pictures are the same with it off.
* **`live_panel.py`** shows the same facts as they happen in a narrow terminal beside the game window (`python3 -I -B play/pilot/live_panel.py <run folder>`;
  read-only, standard library only), and **`overlay.py`** draws them on the game's own pictures after the run: stills, a contact sheet and a video
  (`python3 -I -B play/pilot/overlay.py <run folder> [--video]`; needs ImageMagick, and ffmpeg for the video). Ask the run for a denser `--shots` where a smoother
  clip matters.
* **The item steps** (`hsap_items.py`): `wheel-select <item>` and `use-item <item>` choose the item the item button uses and use it, and end by what the
  game's own flags say. The item table (the game's item names, the flags of the choice and of the stock counts, the wheel's order) is **yours**:
  a JSON file named by `HSAP_ITEMS` (no default; the schema is `hsap_items.SCHEMA`); without it these two steps answer `bad` and name it.

### Drivers: who chooses the next step

`pilot/drivers/` puts every way of choosing a step behind one interface, each falling back to the next (`--driver decisions,openrouter,scripted`,
`--fallbacks none`, or a segment's `[driver]` table): `decisions` (the model of `--decider openai-decisions`), `openrouter` and `chat` (a model through the
OpenAI-compatible chat API: OpenRouter, or any base URL such as a local llama.cpp or Ollama server, which needs no key), `mcp` (an outside agent
through the MCP tools of `pilot/mcp_server.py`, stdio, standard library only; `pilot/mcp_agent.py` is a small agent of ours that plays through it),
`playback` (an `ls-input-recording/1` file replayed through the same input path, with the map and place checked at the recording's marks) and `scripted`
(the rules, or fixed input scripts: no model, the same inputs give the same steps). A driver that cannot be asked (no key, no endpoint, a cap reached) is
benched before any request; one that fails falls back, and every fallback is a row of the transcript. Every paid request, whichever driver, goes through the
same caps and the same ledger. Every run writes `recording.jsonl` (the input journal with a mark after each step); `inputlog.py` converts it to the game's
own input script grammar. `pilot.py drivers [--ask NAME]` says which drivers can be asked now and why not. Keys: OpenAI as above, OpenRouter in
`PILOT_OPENROUTER_KEY_FILE` (default `$XDG_CONFIG_HOME/ls-pilot/openrouter.key`, mode 600), a chat endpoint in `PILOT_CHAT_KEY_FILE` or `PILOT_CHAT_API_KEY`
(optional), its base URL in `PILOT_CHAT_BASE`.

### Bug hunting: scenarios, detectors, the hunt

The pilot plays; detectors read what a played session left behind and say what looks wrong; every finding becomes a repro packet with a deduplication key.

* **`scenario.py`**: a targeted test written down so that any runner can play it (`ls-scenario/1`, TOML): a place (map, age, hour, coordinates), a list of
  actions and what to look for. `check`, `steps` (what it compiles to for `hsap.py`), `import` (a draft from an issue's or a bug report's text, for a person to
  confirm; `--issue` reads your forge through `SCENARIO_FORGE`, the project page as `https://HOST/OWNER/REPO`, under the lock `SCENARIO_FORGE_LOCK`) and `eval`
  (the verdict of a played run). Map names come from the destinations list you pass; none is named in the code.
* **`bughunt.py`**: the detectors (crash, hang, stall, softlock, out of bounds, visual, log, audio, desync of a pair, ...), each returning `ok`, `found` or
  `unknown` (the input it needed was missing: never turned into a pass). `bughunt.py analyze <session folder>`.
* **`bugpacket.py`**, **`burst.py`**, **`inputlog.py`**, **`score.py`**: the repro packet and the table of known findings; bursts of consecutive pictures for the
  flicker check; the input recording; the scorecard of a round and the triage that feeds back into the next one.
* **`hunt.py`**: N sessions of the pilot (free roam, a chapter, a co-op pair) inside one hold with the detectors watching: `plan`, `check`, `run`, `queue`
  (one waiter behind the main lane's two locks), `nightly`, `analyze`, `replay`, `verdict`, `table`, `score`. Machine paths, saves and segments live in the plan and in
  private files beside it. Settings, none with a default: `HUNT_COPY_PREFIX` (the name every game copy a hold may touch starts with), `HUNT_QUIET` and
  `HUNT_MEASURING` (the two lock files); a plan or a queue without them is refused, naming them. A hold is long and starts games: read `hunt.py`'s docstring first.

## The offline world model (`worldmodel/`)

The world model is what lets the pilot plan a route, know where doors, chests and people are, and say why a walk cannot continue. `worldmodel/` BUILDS it from
the game's own files on your PC: areas, start positions, exits, placed objects, flags, gates, event flows and the story's steps, plus a nav mesh per area and a
path planner on those meshes (`plan.py`). **The code holds no game data.** Everything the builders need to know about the game's names (which actor class is a
door, what a flag name family looks like, which event queries test a flag, which parameter keys carry what) is read from one JSON file that you write from your own
game's files and keep on your own PC. What it makes is game-derived and stays in the data folder, never in a commit.

What you need first, in this order:

1. **The game's files, extracted from your own copy**: a RomFS folder (it holds `GameData/`), or a game copy that holds `romfs/`. `--game <folder>` or `WORLD_GAME`;
   there is no default. Python 3.14 (`compression.zstd`) reads them; the zstd dictionaries come from the game's own files.
2. **Your tables file**, `world/tables.json` (or the file `WORLD_TABLES` names): sections `actors`, `exits`, `areas`, `flags`, `quests`, `flows` and `plan`, each key
   documented in `worldmodel/tables.py` (the one place that defines the schema; the error you get when the file is missing or wrong names the file and prints it).
   Write it from what the game's files show. It is yours and stays local (`world/` is ignored by `.gitignore`).
3. Optionally a list of readable flag names, `world/flag_names.json` (or `WORLD_FLAG_NAMES`): `{"<flag hash>": "<name>"}`. The builders also find names themselves
   by hashing the strings of the game's files.

Then build it:

```sh
WORLD_GAME=<your extracted RomFS folder> play/worldmodel/rebuild.sh     # build.py, then flows.py, then story.py
```

or the three scripts one by one (`python3 -I -B play/worldmodel/build.py --game <folder> [--only nav,model,inventory] [--areas A,B]`, then `flows.py`, then
`story.py`, which needs the files the first two wrote). They write, into the data folder (`PILOT_WORLD`, else `play/world/`): `nav/<area>.json.gz`, `areas.json`,
`links.json`, `objects.json`, `flags.json`, `gates.json`, `mobility.json`, `navinfo.json`, `inventory.json`/`.md`, `flows.json`, `story.json`, `summary.json`/`.md` and
the logs of the three steps. The pilot finds them there (`PILOT_WORLD`), and a planned route is one call:

```python
import sys; sys.path.insert(0, 'play')
from worldmodel import plan as wplan          # wplan.use('<data folder>') to point it elsewhere
print(wplan.plan('<an area your model has>', (x0, z0), (x1, z1), from_y=y0))   # ok + steps, or why not and what to do first
```

`worldmodel/test_worldmodel.py` (synthetic fixtures only: no game, no tables file of yours) tests the tables loader, the file-format readers, the nav graph and
the planner, and the builders' classification.

## Start points for a test (`bosspoints/`)

`bosspoints/` builds test start points just outside the places you want to test (a room's door, say) from ONE table that you write for your own game.
`make_saves.py` writes a library save per start (it builds the save tool's command lines; the save tool itself is yours: `HS_MAKE_SAVE`, no default;
`--print` shows the commands without running it), `write_scenarios.py` writes a pilot scenario (`ls-scenario/1`) per start, `plan_hold.py` plans a timed
hold of `hsap.py` runs (step files and a `plan.json`), and `analyze_hold.py` summarises a finished hold folder. The tools hold no game data: every map,
actor, flag and quest name, every coordinate and every action list is in the table, which is `table.local.json` beside the tools or the file named by
`BOSSPOINTS_TABLE` (`--table` on every tool). `python3 -I -B play/bosspoints/bosspoints_table.py --schema` prints the format, and without a flag it checks
your file. The outputs hold game names and coordinates too: write them outside the repository.

What you need first: the world model (above; flag hashes need only its `worldmodel/` package, the planner needs the built nav meshes, and only when a recipe has
a `route` item), your save tool, your save library (`--saves` or `BOSSPOINTS_SAVES`, for `plan_hold.py`) and, for `analyze_hold.py --panels`, a panel script
(`BOSSPOINTS_PANELS`).

## The benchmark

`bench/course.py` names six entries (walk, hard route, door-talk, follow, chest, fight) as cuts of segments *you* have (placeholders until `course-local.json` says which),
and four arms: `rules`, `decisions`, `decisions+vision`, `decisions+vision-big`. `bench/mkcourse.py` makes the cut segments
into `bench/segments/` from your local `pilot/segments/`; `bench/run.py` plays the cells (one game copy per cell at a
time, two copies for two at once), writes `results.json` and `table.md` (quality and cost per minute, per goal met and per
km for each entry and arm) and contact sheets, and never starts a cell that cannot finish inside `--hold-s`. It does not
take the quiet-window or measuring locks: the hold that runs it does. Wall-clock cells are functional runs, not frame-time
measurements.

```sh
python3 -I -B play/bench/mkcourse.py --segments <your pilot/segments> --out play/bench/segments --bench-id b1
python3 -I -B play/bench/run.py play --out <new folder> --bench-id b1 --copies <copy-a>,<copy-b> \
    --pilot-dir play/pilot --segments-dir play/bench/segments --arms rules,decisions --hold-s 1500 [--tas]
python3 -I -B play/bench/run.py report --out <that folder> --segments-dir play/bench/segments
```
