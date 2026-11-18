# The game's flags

A map of the flags of Ocarina of Time (the Switch 2 remake): one row for every entry of the game's list of values (the
`GameDataList`, [game-data.md](../game-data.md)) that `flagdata/flagdata.py build` can enumerate, with the flag's hash, the
name recovered from it by hashing (and how), its kind, default, reset kind, the save file and the group it sits in, what LS's co-op
does with it, and, where we know it, what it is. It stands beside the function map ([README.md](../README.md)) and works the same
way: look a flag up before you work it out, and add what you learn.

**This is game data, kept here on purpose.** The names are the game's own identifiers, found by hashing the identifiers of the
player's own game files (the method: [flag-names.md](../flag-names.md)). The owner of this repository decided that this
repository, and only this one, may hold them: the flag map and the function map. They never go into LS's repository, an issue or a pull
request. No game file, save or lifted code is here: only each flag's hash, its name, and facts and words of ours. A row says nothing
that is not in the game's list or in our own work (below, "Sure"). **LS code:** `host/oot_coop.c`, `host/coop_scenes.c`; in this
repository `flagdata/`.

**See also:** [save-format.md](../save-format.md) (where a flag sits in a save file), [flag-names.md](../flag-names.md) (the method),
[game-data.md](../game-data.md), [flagdata/README.md](../../../flagdata/README.md) (the tools that make the data)

## Finding a flag

```sh
python3 docs/oot/flagmap.py find 4d77f1cb              # a flag by its hash (8 hexadecimal digits; a per-object key has 16)
python3 docs/oot/flagmap.py find PlayerStatus.Life      # by the game's name (else the rows whose name holds the text)
python3 docs/oot/flagmap.py find "boss appear"          # by words: every word must be in the row (first 20 rows)
python3 docs/oot/flagmap.py show 4d77f1cb               # one row in full, and where the flag sits in a save file
python3 docs/oot/flagmap.py stats                       # the numbers
python3 docs/oot/flagmap.py check                       # the pages against themselves; every name against its hash
```

A hash from a game log or a save file is the usual start (`coop_log.py` in `flagdata/` prints the flag of every co-op log line from
your own build's table; this map is the same list, published). A flag with no name still has its row: its hash, kind, file and group,
the family it belongs to, and what co-op does with it.

## The pages

<!-- pages:begin -->
| Page | What | Rows |
|---|---|---|
| [items.md](items.md) | Items, songs, quest items, counters | 331 |
| [played-events-1.md](played-events-1.md) | Played events (1 of 4) | 1,116 |
| [played-events-2.md](played-events-2.md) | Played events (2 of 4) | 1,198 |
| [played-events-3.md](played-events-3.md) | Played events (3 of 4) | 1,097 |
| [played-events-4.md](played-events-4.md) | Played events (4 of 4) | 235 |
| [hints-and-talks-1.md](hints-and-talks-1.md) | Hints, talks and tutorials (1 of 2) | 1,289 |
| [hints-and-talks-2.md](hints-and-talks-2.md) | Hints, talks and tutorials (2 of 2) | 251 |
| [dungeons-1.md](dungeons-1.md) | Dungeons: rooms, maps, logic nodes (1 of 3) | 1,089 |
| [dungeons-2.md](dungeons-2.md) | Dungeons: rooms, maps, logic nodes (2 of 3) | 1,092 |
| [dungeons-3.md](dungeons-3.md) | Dungeons: rooms, maps, logic nodes (3 of 3) | 394 |
| [flat-flags-1.md](flat-flags-1.md) | Single flags (1 of 3) | 1,217 |
| [flat-flags-2.md](flat-flags-2.md) | Single flags (2 of 3) | 1,308 |
| [flat-flags-3.md](flat-flags-3.md) | Single flags (3 of 3) | 761 |
| [object-keys-placed-1.md](object-keys-placed-1.md) | Per-object keys of placed actors (1 of 4) | 1,044 |
| [object-keys-placed-2.md](object-keys-placed-2.md) | Per-object keys of placed actors (2 of 4) | 1,043 |
| [object-keys-placed-3.md](object-keys-placed-3.md) | Per-object keys of placed actors (3 of 4) | 1,043 |
| [object-keys-placed-4.md](object-keys-placed-4.md) | Per-object keys of placed actors (4 of 4) | 556 |
| [object-keys-other-1.md](object-keys-other-1.md) | Per-object keys with no placed actor found (1 of 5) | 1,795 |
| [object-keys-other-2.md](object-keys-other-2.md) | Per-object keys with no placed actor found (2 of 5) | 1,795 |
| [object-keys-other-3.md](object-keys-other-3.md) | Per-object keys with no placed actor found (3 of 5) | 1,795 |
| [object-keys-other-4.md](object-keys-other-4.md) | Per-object keys with no placed actor found (4 of 5) | 1,795 |
| [object-keys-other-5.md](object-keys-other-5.md) | Per-object keys with no placed actor found (5 of 5) | 791 |
| [expressions.md](expressions.md) | Expressions | 884 |
| [structs.md](structs.md) | Structs | 874 |
| [other-values.md](other-values.md) | Other values | 688 |
| [other-groups-1.md](other-groups-1.md) | Other groups of flags (1 of 2) | 977 |
| [other-groups-2.md](other-groups-2.md) | Other groups of flags (2 of 2) | 196 |
| **all** | | **26,654** |
<!-- pages:end -->

<!-- made:begin -->
Made from the player's own game (flag list revision 2982123, game version 1.1.1, build e0f3ccfa) by `flagdata.py build` with LS's rules as of `29b087a83` (the co-op classifier of `host/oot_coop.c`); its counts (9,396 progress flags, 2,168 of them story scenes, 255 items, 13 songs, 11 quest items, 14 key counters, 1 rupee counter, 7 ammunition counters) and the story-scene list's stamp equal the game's own log line. 7,029 of the 9,697 flags co-op keeps and 11,168 of the list's 26,654 entries have a recovered name.
<!-- made:end -->

## A row

| Column | What it holds |
|---|---|
| Hash | The 32-bit MurmurHash3 (seed 0) of the flag's name: how the game and its save files know the flag. A per-object key has 64 bits (16 digits) |
| Name | The game's own name, when one is known: the text whose hash is the flag's. Every name on these pages is checked by `flagmap.py check`. Empty: no name is known |
| Named by | Where the name came from: `event table` (a row of the game's EventSetting table with the played prefix), `files` (an identifier of the game's own files), `struct` (the struct's name and a member's name, checked by the child's hash), `names file` (a name found by searching and supplied to the tool), `source comment` (a name written beside a hash in LS's source) |
| Kind | The container of the game's list the flag is in: Bool, Int, Float, Enum, String64, Struct, Bool64bitKey, BoolExp ... ([the kinds](#what-the-list-holds)) |
| Default | The value a new game starts with, as the list gives it (a Bool is 0 or 1; an Enum's is the name of its default value; empty for a kind with none) |
| Reset | The list's reset kind, a set of bits: 1, 2, 4 and 256 are reset by the game itself while it runs (a scene change, a new day, a load: which bit is which was not worked out); 8, 16 and 32 are reset by a new game. Most saved flags are 8 |
| File | The save file the flag is in: `progress` (`slot_NN/progress.sav`, the list's save file index 0), `option` (`option.sav`, 1), `caption` (`slot_NN/caption.sav`, 2), `account` (`account.sav`, 3) or `none` (-1: never saved) |
| Group | The group of the flag's type in that file's table, numbered as [save-format.md](../save-format.md) numbers them (group k is the entries before the table's marker `{0, k}`; the game's loader counts the same blocks from 0, so group k is its type k-1): a number from 1 to 32, `keys` for a per-object key (the key run at the end of `progress.sav`, not the table), `-` for a flag with no place in a file. Bool is group 1, Int 3, Enum 7, String64 17 |
| Co-op | What LS's progress sync does with the flag: `<category>, <mode>` (`progress`, `items`, `songs`, `quest`, `keys`, `rupees`, `ammo`; `shared`, `pool` or `own`: the room's default rules), `story scene, own`, `out: <reason>` (left out on purpose) or `not read` (in a container the sync never looks at). [How it sorts](../flag-names.md#how-co-op-sorts-them) |
| Map | The map the name, the struct path or the placed actor implies (the age and Master Quest variants folded in) |
| Note | What the data says besides: for an unnamed flag its group, or the names a played event sorts between; the placed actor of a per-object key; a struct's number of members, an enum's values, an array's sizes, a `BoolExp`'s terms |
| What it is | Our description, in our own words, where we know what the flag means. Most rows have none: the flag's name is then all there is, and a flag with no name has only the data |
| Sure | How sure the row is: see below |
| Source | Where the description comes from: a file of LS's source, the world model or the boss start points of the test player, a page of the function map, a report of the co-op or test work |

The headings above each table name the **family**: the struct a flag is a member of (`HavePlayedEvent.*`), or `flat flags` (no
struct), or `unnamed, in group X` (a member of the struct X whose own name was not found).

### Out: why a flag is left out

| Reason | Meaning |
|---|---|
| `not saved` | The flag's save file index is -1: it is never written to a save |
| `other file` | Saved, but in `option.sav`, `caption.sav` or `account.sav`: not part of a save's progress |
| `temporary` | The game resets it itself (a scene change, a new day, a load) |
| `no new-game reset` | A new game does not reset it |
| `heart reward` | One of the heart rewards: a shared count would pay twice, so each game finds its own |
| `unshared list` | On LS's list of flags that are one player's own (where he stands, a failed try, a refill, his age) |
| `boss fight's own` | A flag only a boss fight and its warp set (the end set's members) |
| `Int in no group` | An Int that is not the rupee counter, a small-key counter, an item count, a capacity or the magic meter |
| `own count` | An item count that stays with each player |

### Sure

| Value | Meaning |
|---|---|
| **tested** | The description was seen to be true in a running game or against the game's own log: a boss fight starting when the flag rises, a co-op run |
| **read** | Worked out from the game's list and files, from LS's source, or from the test player's world model, without a run. This is also what a row with no description of ours says: its hash, kind, default, reset, file and group are read from the list, its name is checked by hash, and its co-op fate is the classifier's, which reproduces the game's own log line |
| **guess** | Inferred from the words of a name, a constant or the data around it |

## Families

What the data's own structs say a family is, read from the names (so **guess**; a row's description, where it has one, is firmer).

| Family | What it is | Flags |
|---|---|---|
| `HavePlayedEvent.<row id>` | One Bool for every event the game plays: a scene, a talk, a chest opening, a gimmick's demonstration. Named by the EventSetting table where it has a row; the struct lists its members in name order | about 3,650 |
| `HavePlayedNaviBalloonMessage.*`, `HaveTalked.*`, `HaveTalked_Special.*`, `ActionGuide_IsEnd.*`, `ActionGuide_IsNew.*` | A Navi hint balloon was shown; a person was talked to (once, or a special line); an action-guide tutorial was finished or is new | about 1,250 |
| `HavePlayedGetEvent.*` | The scene of getting an item or a pickup was played | 199 |
| `IsTreasureBoxOpen.<id>`, `IsChainLockDoorOpen.<id>`, `IsGoBackHome.<id>`, `IsDoorKeepOpen.<id>` | One Bool for a placed chest, a chain-locked door, an animal or person that went home, a door that stays open; the name carries the placed actor's 64-bit id | a few hundred |
| `DungeonRoomStep.<dungeon>.DungeonRoomNNN.<flag>` | Three Bools for every room of every dungeon and its Master Quest twin: a cleared marker and two more | about 2,300 (1,725 kept by co-op) |
| `DungeonInfo.<dungeon>.*` | A dungeon's map, compass and boss key flags and its small-key counter | about 85 |
| `AutogenGameDataLogicNode.<id>` | Room-graph nodes the game names only by a 64-bit id | 191 |
| `IsGet.<item>`, `PouchData.<item>.StockNum` | An item's first-pickup marker; its count | 186 / 92 |
| `DefeatedEnemyNum.*`, `Shop_SoldNum.*`, `IsAttacked_ScrubBusiness.*`, `HaveTalked_ScrubBusiness.*`, `IsNPC_ScrubBusiness.*` | Enemy defeat counts, sale counts and the Deku scrub shops' per-person state | about 400 |
| `<Map>_<what>` (flat flags) | Room, gimmick, boss, person and minigame flags named in full | about 3,000 |
| `per-object keys` | One 64-bit key for each placed object the game keeps a flag for (a chest's lid, a pot, a grass patch, a Gold Skulltula, a piece of heart); true keys are the key run of `progress.sav` | 11,657 |

## What the list holds

The tools read one list, the `GameDataList` of the player's own game (one file, `GameData/GameDataList.Product.<n>.byml.zs`). Every
entry of it is a row. The co-op layer reads only the Bool and Int containers; the others are listed here too (the sync's `Co-op`
cell says `not read`).

<!-- kinds:begin -->
| Kind | Rows | Named | Save file | Group | What it is |
|---|---|---|---|---|---|
| Bool64bitKey | 11,657 | 0 | progress | keys | A per-object flag keyed by a 64-bit hash (a placed object's): only the true keys are saved, as the key run of progress.sav |
| Bool | 11,292 | 8,453 | progress, option, caption, account | 1 | A flag: true or false |
| Int | 1,259 | 1,105 | progress, option, caption | 3 | A signed 32-bit number |
| BoolExp | 884 | 526 | never saved | - | A logic expression over other values (its terms are in the row's note); computed, never saved |
| Struct | 874 | 831 | never saved | - | A group of flags: it lists its members (the hash of each member's own name and the flag that holds it; their number is in the row's note) and holds no value itself |
| IntArray | 156 | 44 | progress, option | 4 | An array of Ints |
| Enum | 130 | 62 | progress, option | 7 | One of a list of named values; the saved value is the hash of the value's name (the values are listed in the row's note) |
| UInt | 97 | 5 | progress, caption | 21 | An unsigned 32-bit number |
| Float | 89 | 77 | progress, caption | 5 | A 32-bit float |
| String64 | 54 | 34 | progress, caption | 17 | A text of up to 63 bytes |
| Int64 | 33 | 0 | progress, option | 23 | A signed 64-bit number |
| UIntArray | 33 | 0 | progress | 22 | An array of UInts |
| Vector3 | 26 | 20 | progress, caption | 11 | Three floats |
| EnumArray | 14 | 0 | progress | 8 | An array of an enum's values |
| BoolArray | 13 | 7 | progress | 2 | An array of flags |
| Binary | 11 | 1 | progress, option, caption | 19 | A block of bytes (the caption's picture is one) |
| UInt64 | 6 | 1 | progress | 25 | An unsigned 64-bit number |
| String64Array | 5 | 0 | progress, caption | 18 | An array of String64s |
| FloatArray | 4 | 0 | progress | 6 | An array of floats |
| Int64Array | 4 | 0 | option | 24 | An array of Int64s |
| UInt64Array | 4 | 0 | progress | 26 | An array of UInt64s |
| BinaryArray | 2 | 0 | progress | 20 | An array of blocks of bytes |
| String32 | 2 | 1 | progress | 15 | A text of up to 31 bytes |
| WString16 | 2 | 0 | never saved | - | A wide text (16-bit characters) |
| WString16Array | 2 | 0 | progress | 28 | An array of wide texts |
| String16 | 1 | 1 | never saved | - | A text of up to 15 bytes |
| **all** | **26,654** | **11,168** | | | |
<!-- kinds:end -->

What is **not** here, and why:

- **Flags the game does not keep in the list.** The list is the game's table of saved and temporary values. A value a
  graph or an actor computes at run time without a list entry, and the tables of flag hashes the game's code holds (a story-progress
  table of 235 hashes in rodata, [game-data.md](../game-data.md)), are not enumerated: the tools cannot see them.
- **The terms of a `BoolExp`.** The expression's terms are listed as the list gives them (`kind:value` pairs); what each kind
  means was not worked out, so they are not decoded.
- **Names of the per-object keys.** A key carries no name: it is the 64-bit hash of a placed object. Where a placed actor of the
  game's map files has that hash the row says which; for the rest (about two thirds) the data says nothing more.
- **Unnamed flags.** About a quarter of the Bool and Int flags have no recoverable name ([flag-names.md](../flag-names.md), "What stays
  unnamed"); their rows hold what the data says.

## Making the pages

The pages are made, not typed: by hand only `flags/descriptions.md` (the descriptions, one row for each flag we can describe, with how
sure and where from) and this index's text are written. To refresh them, for a new game version or after learning names:

```sh
# 1. the data: your own RomFS and an LS clone (flagdata/README.md); --names takes names to try, e.g. the ones this map holds
python3 docs/oot/flagmap.py names > /tmp/known-names.txt
python3 -I -B flagdata/flagdata.py build --romfs <your RomFS> --repo <LS clone> --rev <commit> --names /tmp/known-names.txt \
    --out <a folder outside this repository> --compare-log <a game log with the `playing a save:` line>
# 2. the pages, from that folder (this rewrites flags/*.md, the tables of this index and the flag pages' rows of docs/names-kept.md)
python3 docs/oot/flagmap.py build --from <that folder> --made-from "<one line: game build, list revision, LS revision>"
# 3. the checks
python3 docs/oot/flagmap.py check && python3 tests/test_flagmap.py && bash publish-check.sh
```

`build` refuses a build folder without `flags.csv`, `excluded.csv` and `others.csv`, a hash in two containers, and a description for a
flag the build does not have. The flag names are the game's identifiers, and a few of them are also the names of
projects (two items of the game): the publication policy counts such literals per file, so `build` rewrites those rows of
`docs/names-kept.md` too.

## Adding to it

- **Search first.** `find` by hash or name: if the flag has a description, extend it.
- **Write a description** as a row of `flags/descriptions.md` (hash, what it is in one sentence of our own, tested/read/guess, source), then
  run `flagmap.py build` again; never edit the generated pages by hand, `check` fails when a page disagrees with the descriptions.
- **Say what you saw.** A row is a claim about the game. Never the lifted code, never a position or coordinate, never a value from a
  save.
