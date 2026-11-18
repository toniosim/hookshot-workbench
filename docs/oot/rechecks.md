# The recheck of the function map

On 17 November 2026 every row the pages had at commit `b043853` (2,996 rows on 31 pages) was read again against the lifted
code, row by row, by eight readers who took the pages between them. This page says how, what the five verdicts mean, what
came out, and what is still to do. The result for each row is in [rechecks/](rechecks/), a file for each page; `python3 docs/oot/fnmap.py
find f_833ec800` prints it under the row (`rechecked 2026-11-17: agrees (read)`, or `cannot-check yet: <reason>`, or `not
rechecked` for a row that came later).

## Method

- **What was read.** The lifted code and the image of a build of LS's main at commit
  `d3bd280503b8d5ea10111883edacf68b7f223d25`. No game was run and no save file was opened. What a row says about the port
  (a hook, a host function) was looked up in the port at forge/main as it stood that day
  (`310e7c9dfa152ecf7ff165b22a86c62bd444451f`); the ledger names both commits in its `build` and `hooks_at` columns.
- **What a verdict covers.** For each row the reader took the claims it makes (callers, calls, offsets, strings, vtable
  slots, sizes, counts) and looked for each in the code, in the function or, for a field, in the functions that use it.
  How deep that went differs: for many rows it was a check of the calls, offsets and strings the row names, and a note
  says "body only skimmed" where that was all. `agrees` is not a re-derivation of every sentence of a long row.
- **What changed in the pages.** A row the code contradicts or fills out was rewritten. A guess whose claims were all found
  was raised to read (80 rows). Nothing was lowered: a tested row stays tested for the role a patch relies on, and where
  reading contradicted part of one, the wording was corrected. The names of some rows changed with their text. Where an
  address was a thunk, a destructor or a place inside a neighbour, its row now says so and the body it described stands
  under its own address (six rows were made that way: their ledger lines have the origin `recheck-1`).
- **The pages' prose** was read only where a row depended on it. The stale places found that way are corrected: the
  culling page against the port's main, the effects page's account of bit 23, the audio page's import counts and coverage
  table, the environment object's vtables, the call and return addresses of the add-on check, and the patches a row may
  name as `Hooked by`.

## The verdicts

| Verdict | Meaning |
|---|---|
| `agrees` | The claims the row makes were found. Only the *Sure* value may have changed (guess to read). |
| `partly` | The role holds, but the row missed something or got a detail wrong (an offset, a caller, a count). The row now says what the code does. |
| `corrected` | The row said something the code does not do (a role, a name, a vtable). The row now says what it does. |
| `wrong-address` | The address is a thunk, a destructor or a neighbour, not the function the row describes. The row says what is at the address; the description is under the right address. |
| `cannot-check` | Reading the lifted code cannot settle it (save files, a very long function, a game run). The row is left as it was; the note says why. |

## The ledger

[rechecks/](rechecks/) has one tab-separated file for each page (`rechecks/actors.tsv`, …; the repository's publication check
allows no file over 200 KB, which one file for all 3,000 rows would be), with one line per checked row and the columns
`page`, `key`, `kind`, `verdict`, `sure_before`, `sure_after`, `note`, `checked`, `build`, `hooks_at` and `origin`.

- `key` is the row's address (`f_833ec800`, `0x84e98e38`). Rows without one are keyed as the pages show them: a field as
  `Structure+offset`, a catalogue row of [nvn-calls.md](nvn-calls.md) by its NVN function, the others by their first cell.
- `kind` is `function`, `data`, `field`, `place`, `catalogue` or `import`. The catalogue tables have no *Sure* column;
  their sure columns are empty.
- `hooks_at` is set where the row speaks of the port (a hook, a host function) and names the port's commit it was looked
  up in.
- `origin` is `dyst` for a row that was in the first commit of this folder as dyst wrote it, else the commit that added
  the row (`git log -S` finds the rest).

## What came out

| Page | Rows | agrees | partly | corrected | wrong-address | cannot-check |
|---|---|---|---|---|---|---|
| [actors.md](actors.md) | 193 | 177 | 13 | 2 | 0 | 1 |
| [ai.md](ai.md) | 138 | 128 | 8 | 2 | 0 | 0 |
| [animation.md](animation.md) | 88 | 83 | 0 | 3 | 0 | 2 |
| [audio.md](audio.md) | 117 | 99 | 13 | 4 | 0 | 1 |
| [camera.md](camera.md) | 15 | 12 | 1 | 2 | 0 | 0 |
| [culling.md](culling.md) | 47 | 40 | 4 | 3 | 0 | 0 |
| [drawing.md](drawing.md) | 60 | 59 | 1 | 0 | 0 | 0 |
| [effects.md](effects.md) | 103 | 89 | 6 | 7 | 0 | 1 |
| [environment.md](environment.md) | 126 | 106 | 16 | 3 | 0 | 1 |
| [events.md](events.md) | 74 | 70 | 1 | 0 | 0 | 3 |
| [frame-time.md](frame-time.md) | 43 | 29 | 3 | 1 | 0 | 10 |
| [game-data.md](game-data.md) | 78 | 74 | 2 | 2 | 0 | 0 |
| [graphics.md](graphics.md) | 29 | 20 | 8 | 0 | 0 | 1 |
| [input.md](input.md) | 113 | 97 | 3 | 0 | 0 | 13 |
| [jobs.md](jobs.md) | 107 | 85 | 11 | 2 | 0 | 9 |
| [layout.md](layout.md) | 61 | 48 | 12 | 0 | 0 | 1 |
| [maps.md](maps.md) | 120 | 109 | 11 | 0 | 0 | 0 |
| [master-quest.md](master-quest.md) | 55 | 51 | 1 | 2 | 0 | 1 |
| [menus.md](menus.md) | 74 | 70 | 3 | 0 | 1 | 0 |
| [navigation.md](navigation.md) | 70 | 62 | 4 | 1 | 0 | 3 |
| [nvn-calls.md](nvn-calls.md) | 340 | 326 | 14 | 0 | 0 | 0 |
| [physics.md](physics.md) | 208 | 193 | 10 | 5 | 0 | 0 |
| [player.md](player.md) | 64 | 51 | 7 | 1 | 0 | 5 |
| [rendering.md](rendering.md) | 47 | 44 | 2 | 0 | 1 | 0 |
| [resources.md](resources.md) | 140 | 139 | 0 | 0 | 1 | 0 |
| [save-data.md](save-data.md) | 38 | 21 | 9 | 3 | 0 | 5 |
| [save-format.md](save-format.md) | 119 | 68 | 0 | 0 | 0 | 51 |
| [save-list.md](save-list.md) | 66 | 54 | 4 | 6 | 1 | 1 |
| [sequences.md](sequences.md) | 154 | 132 | 11 | 3 | 0 | 8 |
| [shaders.md](shaders.md) | 77 | 73 | 3 | 0 | 1 | 0 |
| [textures.md](textures.md) | 32 | 24 | 6 | 0 | 2 | 0 |
| **All** | **2,996** | **2,633** | **187** | **52** | **7** | **117** |

[nvn-calls.md](nvn-calls.md) counts its 285 catalogue rows (273 agrees, 12 partly: 47 of the site counts were inconclusive
by a rougher second count) with its 55 other rows. The pages `hot-path.md`, `nvn-driver.md` and `flag-names.md` have no
rows of the first pass.

## Not rechecked

- **Rows added after `b043853`.** The commit `b597a8a` added 282 rows (the whole of [nvn-driver.md](nvn-driver.md), new
  rows of [graphics.md](graphics.md), [jobs.md](jobs.md), [drawing.md](drawing.md), [frame-time.md](frame-time.md),
  [nvn-calls.md](nvn-calls.md), [shaders.md](shaders.md) and [textures.md](textures.md)) and merged 20 into rows that
  existed. `find` says `not rechecked` for the new ones. The merged ones carry the verdict of the row as it stood before
  the merge: what the merge added was not read.
- **Whatever a later commit adds.** A row is rechecked when it is in the ledger; the `origin` column shows how old it was.

## The second pass

The 117 `cannot-check` rows wait for it, with the rows added since:

- **Save files** (51 rows of [save-format.md](save-format.md)): the layouts there were tested on real save files and the
  game's data list, which a reading of the lifted code does not have.
- **Deep reads**: long functions and fields whose users were not all followed ([frame-time.md](frame-time.md), 10;
  [jobs.md](jobs.md), 9; [events.md](events.md); [navigation.md](navigation.md); [player.md](player.md);
  [save-data.md](save-data.md)), and the [input.md](input.md) rows that were not reached.
- **A game run**: values and roles that only show at run time (the actor database's role, the clock's day-night windows).
- **Counts** of [sequences.md](sequences.md)'s catalogue, which a second counting only reproduced to within a few percent.

It reads the deep ones, runs the game for those that need it, takes the save-format rows to save files, and rechecks the
rows added since. Until a row is done, `find` says `cannot-check yet` and why.
