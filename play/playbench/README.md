# The pilot's capability scoreboard (`playbench/`)

A fixed set of small tasks ("cells") that the playthrough pilot plays every night, with each arm (a way of playing), scored from the **game's own state**, stored,
and drawn as a trend. It answers one question over time: *is the pilot getting better at playing in general, and by how much, on tasks that never change?*

## The cells

Eleven cells, each a save-placed start plus a goal the game's state proves:

| cell | what it asks | what proves it (private: `board-local.json`) |
|---|---|---|
| `door-front` | open a door from its front and go through | a door flag |
| `door-wrong` | the same door approached from the side that stays shut | the same flag |
| `ledge` | get up onto a ledge a walk cannot climb | Link at the top, at its height |
| `drop` | go down from a high platform | Link at the bottom, at its height |
| `ladder` | climb a ladder to the platform at its top | Link at the top, at its height |
| `crowd` | cross a busy town square | Link at the far side |
| `chest` | open a chest | the chest's flag |
| `pickup-dive` | collect rupees, one lies on a pond floor | the rupee count rose by 6 |
| `song-warp` | play a warp song | the map changed to the song's place |
| `item-bomb` | use the item on the item button (a bomb) | the bomb count fell |
| `chapter-lake` | a short chapter: the open field to the lake | Link at the lake shore |

The public code (`board.py`) holds the ids, what each asks and its default budget. **Places, flags, saves and proofs are game data and stay private**:
`playbench-local/board-local.json`, `segments/` and `saves/` (frozen copies; a cell's *fingerprint* hashes them, so changing one on purpose starts a new series).

## The referee

`referee.py` reads the run's state journal (`live/state.jsonl`) and judges the proof: `flag`, `flag_drop`, `rupees_gain`, `at` (a place within a radius, between two
heights), `map`, `any`/`all`. Only samples that show control of a place count (not loading, a map and a position). The pilot's own "solved" is recorded but never
used. Per cell and arm: `success`, `time_to_goal_s` (game seconds from the pilot's first decision), `progress` (position proofs: how much of the first distance the
best sample closed, so a failing cell still shows movement), `stuck_s` and `decisions` (the pilot's `metrics.py`), `cost_usd` (the pilot's ledger), the game build
and the pilot commit. A run is `invalid` (kept, shown, not counted as a pass or a fail) when the save did not put Link at the cell's start, when no sample showed a
place, or when the hold or the user's game cut it short before the proof.

## A night

* `playbench.py nightly` (the timer, or by hand) waits for two quiet minutes (the user's game wins), writes `nights/<night>/plan.json` (cells x arms, in pair order),
  freezes the tools, and queues **hold 1**: one waiter, `flock` on the quiet-window lock then the measuring lock (each `-w 43200`), `timeout 1100`.
* The hold (`playbench.py hold`) takes the pilot's **committed head** as a snapshot (`git archive`), smoke-checks it (falls back to the last commit that played),
  plays the pending items on its lanes (one warm game copy each; windowless; the arms of a cell side by side), ends a cell a few seconds after the referee saw its
  proof, scores every cell, stores it, copies the evidence out, merges the cost ledger into the dev copy's (the caps see it), counts the kernel's driver lines,
  draws the trend, and **queues the next hold if cells remain** (at most 4 a night; a cell that did not count gets a second attempt).
* No bad-point memory and no route library are read or written by a scoreboard run: every night starts from the same pilot knowledge.

## Arms

`arms.py` (the `ARMS` table): `name -> {label, decider, planner, args, env, requires}`. Add an arm and the next night plays it on every cell. `requires` is a text the pilot's committed
`pilot.py` must contain (a flag a later arm needs): an arm whose requirement is not met is *unavailable* for the night, not failed. A changed arm starts a new series
(its hash is stored with each result).

## Reading it

`reports/PlayBench-files/trend/` holds `trend.md` (the trend table, a grid per arm, the last night, what flipped since the night before), `chart.svg` and `chart.png`.
`playbench.py draft` writes the weekly section for issue 1198 (nothing is posted).

## Private settings

`playbench-local/config.json` holds the machine's own values, which have **no default** (a file without them is an error naming them): `copies` (the lanes' warm game
copies), `quiet_lock` and `measuring_lock` (the shared lane's lock files), `reports` (evidence, tables, charts; its name is the dispatcher's priority key), `drafts`,
`key_file` (the model key file the pilot reads) and `issue_url` (the tracker thread the weekly draft is an update for). Everything else has a default in `config.py`
(`arms` played every night, `hold_s` 1100, `allowance_usd` 5, `max_holds_per_night` 6, `timer_enabled` false, `timer_time` 02:30). A frozen copy of the tools runs with
`PLAYBENCH_HARNESS` and `PLAYBENCH_LOCAL` set (the waiter and the timer set them).

## Commands

`check`, `plan`, `queue`, `nightly [--rearm]`, `hold`, `score`, `trend`, `draft`, `status`, `copies`, `arm --user-authorized` (see `playbench.py --help`).
Tests: `python3 -I -B test_playbench.py` (game-free). `rehearsal/rehearse.py` plays a cell against a fake game (no GPU).
