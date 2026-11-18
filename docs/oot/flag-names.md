# Flag names, and how co-op sorts the flags

How the game's flags get their names (they have none on disk), how a player can recover most of them from their own game files,
what stays unnamed and why, and how LS's co-op progress sync sorts the flags it shares. Worked out while reproducing, offline, the
line each game logs when a save is played: `playing a save: N progress flags (M of them story scenes ...), N items, N songs, ...`
(November 2026). The tools are in `flagdata/`; this page is the method. The list itself, every flag with the name recovered for it, is
the flag map ([flags/README.md](flags/README.md), made from the tools' output by `flagmap.py`): the owner of this repository decided
that the names may be published here, in this repository only, never in LS's repository, an issue or a pull request. The tools'
own output (`flags.csv` and the rest) stays on the player's machine; only the map's pages are published.

**LS code:** `host/oot_coop.c` (`classify`, `build_table` and the lists above them), `host/coop_scenes.c`, `docs/coop.md` ("What is shared",
"Story scenes"); in this repository `flagdata/`, `docs/oot/flagmap.py` and `tests/test_flagdata.py`, `tests/test_flagmap.py`
**See also:** [game-data.md](game-data.md), [save-data.md](save-data.md), [save-format.md](save-format.md) (where a flag sits in a save
file), [flags/README.md](flags/README.md) (the flag map)

## In short

- The game's list of values (`GameDataList`) holds, for each flag, a hash, a default, a reset kind and a save file index, and for each
  struct the hashes of its members. **No name is stored.** [game-data.md](game-data.md) says how the hash is made. **tested**
- A name can be **recovered by hashing**: take every identifier the game's own files spell out and keep the ones whose hash is in the
  list. About two thirds of the flags co-op looks at are named from the game's files alone, and over 70 per cent with a few names found by search; the rest are not, and no file of the game holds their names.
- The co-op layer reads only the **Bool** and **Int** containers (about 12,500 flags) and keeps about **9,700** of them: the numbers the
  game logs. `flagdata.py build` reproduces them from the player's files and the LS source, and `--compare-log` fails when a log's
  numbers differ. **tested** (every figure of the log line, and the story-scene list's stamp, matched on the build the first run used)
- The list holds **26,654 entries of 26 kinds** (11,292 Bool, 11,657 per-object keys, 1,259 Int, 884 BoolExp, 874 Struct and the rest). The
  tools enumerate every one and the flag map has a row for each; 11,168 have a recovered name. **tested** (`flagmap.py check` hashes every name)

## How a flag is named in the data

A flag's hash is MurmurHash3 (x86, 32 bit, seed 0) of its name. There are two shapes of name:

- **Flat**: the whole name is one identifier, hashed as it is. Many of these start with the map or dungeon the flag belongs to, as in
  `InsideTheDekuTree_Heart_Container_Obtained` (a name LS's source quotes).
- **Struct member**: the list also declares **structs**, each a list of `(member hash, child hash)`. The child is a flag or another
  struct, and its hash is the hash of `<struct name>.<member name>`; a nested child is `A.B.C`. `PouchData.Item_Ocarina_Fairy.StockNum`
  and `PlayerStatus.EquipOcarina` (quoted in LS's source) are of this shape. The code reads a member by the plain hash of the member's
  name through a struct handle (`f_805a1170`, [game-data.md](game-data.md)), which is why a scan for the flat hash alone misses it.

So one name is enough to open a branch: when a struct's name is known and the member names are, every child's name follows, and
**each is checked by hashing** (`murmur(parent + "." + member) == child`), never assumed.

## Recovering names

`fd_names.py` takes the sources in this order, and the first text whose hash is in the list keeps it:

1. names the player supplies (`--names FILE`, one a line, `Part{000..127}` for numbered members) and the comments beside the hashes in
   LS's `host/oot_coop.c`;
2. the **EventSetting table**: each row id, with the played prefix in front, is a flag (the same table the story-scene list is made from);
3. every **identifier in the game's own files** (flows, logic graphs, placements, tables; read in the same pass as the scene list),
   whole and, for a dotted one, its prefixes and parts;
4. text the player points at (`--sweep DIR`: notes, the LS source) with a stricter filter;
5. the **decimal 64-bit ids of placed actors** (the Banc placement files): some structs name their members by such an id, one struct per
   kind of placed thing; the map of the placement file then says where the flag is;
6. the struct hierarchy itself, repeated until nothing new is named.

A hash is 32 bits, so with a few hundred thousand identifiers and ten thousand flags a handful match by chance: a stray word of a log, a
file name. Two defences. Flags with no struct must look like a flag's name (`plausible`: long enough, starting in a capital, or
`lower_case` with an underscore); and **when you search patterns yourself, accept a hit only when a second hash confirms it** (a second
member of the same struct, or a hierarchy of children that all agree). The numbers: `candidates x targets / 2^32` false hits, so ten
billion candidates against two target hashes give about five; two targets that agree are not chance.

Patterns that found names which no file spells: a struct name made of a few words (a prefix and a CamelCase word list), a member family
numbered `<Word>NNN` (a word and a three-digit index; `--names` expands `Word{000..127}`), and a struct name seen only as the first half of a member ("a hit for the
first member of a struct, then for a second"). The tools do not search by themselves; `flagdata.py hash NAME` prints a name's hash and
`--names` takes what a search finds.

## What the families look like

The data's own structs give the families (`flagdata.py build` writes them as the `family` column and a count table). The shapes, and
roughly how many of the flags the co-op layer keeps (this build; order of magnitude only):

| Family shape | What it is | Flags kept |
|---|---|---|
| Played events, `HavePlayedEvent.<row id>` | One Bool per event the game plays (a scene, a talk, a chest opening); the struct lists its members in name order | about 3,600, of which the table names about 2,400 |
| Flat flags, `<Map>_<what>` | Room, gimmick and boss flags named in full | about 1,800 |
| Per-room structs, `<Struct>.<map>.<Name>NNN.<flag>` | Three Bools and a step counter for every room of every dungeon and its Master Quest twin | about 1,700 Bools |
| Per-object structs, `<Struct>.<decimal id>` | One Bool per placed chest, chain door, counter, hole and the like, named by the placed actor's 64-bit id | a few hundred |
| Markers and hints | A Bool per NPC, per hint balloon, per tutorial hint | about 1,500 |
| Logic nodes, `AutogenGameDataLogicNode.<id>` | Room-graph nodes the game names only by a 64-bit id (LS's source quotes the struct) | about 180 |
| Dungeon structs | The HUD's map, compass and boss key flags and the small-key counter, one struct per dungeon | about 40 Bools and 14 counters |
| Item markers, `<Struct>.<item>`; item counts, `PouchData.<item>.StockNum`; capacities | The items category | 255 |

The counts per category are the ones in the game's log line (9,396 progress flags, of them 2,168 story scenes; 255 items; 13 songs; 11
quest items; 14 key counters; 1 rupee counter; 7 ammunition counters).

## What stays unnamed, and why

Of the flags co-op keeps, a quarter to a third have no name from the game's files. What is left, in order of size:

- **Played events with no row in the table.** The struct holds more members than the table has rows; the rest are named in no file. The
  struct lists members in name order, so each sits between two named neighbours (`flags.csv` says which); that bounds the name, it does
  not give it.
- **Two of the three Bools of the per-room struct.** The struct, the dungeon and the room are known; the Bool names appear in no file and
  no pattern tried so far hits them.
- **Logic-node ids.** Computed by the game from its graphs; only a few occur in any file.
- **Members of a struct whose own name is in no file**, and a few flat flags in no struct.

The numbers move with the sources: a names file from a successful search, or a sweep of notes that quote names, names more.

## How co-op sorts them

`classify()` in `host/oot_coop.c` (verified against `29b087a83`; `fd_source.RULES_VERIFIED`, and `build` warns when the source's
`classify()` has lost a fragment the mirror depends on). For a **Bool**, in this order, the first test that fails leaves it out:

1. not saved in the slot's progress file (save file index other than 0);
2. reset by the game itself (a scene change, a new day, a load: the temporary reset kinds);
3. not reset by a new game;
4. in a short list of **heart rewards**, of **unshared** flags (where one player stands, failed tries, refills, Link's age), or one of a
   boss fight's own flags or an end set's members (`boss_sets`).

What is left is a **song** if it is in `song_flags`, an **item** if it is a member of the markers struct, else **progress**. Progress is a
**story scene** when it is a row of the EventSetting table that no other file of the game names, is not in `code_read_scenes` (the game's
code reads it) and is not a boss's proof flag. An **Int** is kept only when it is the rupee counter (`rupees`), a dungeon's small-key
counter (`keys`), an item count of the pouch structs (items, less `own_counts`, with `quest_counts` as quest items and the `ammo` pairs as
ammunition), a capacity or the magic meter's size (items).

The story-scene list is the table's events less every `<played prefix><name>` that any file of the scanned folders spells (something
reads those, so a door or a person depends on them). It is made at run time from the player's files; its stamp is logged
(`list <8 hex digits>`), and `fd_scenes.py` makes the same hashes: the stamp of the first build checked was the game's. **tested**

The room's default rules (`coop_rules_default`): progress, items, songs and quest items **shared**; small keys **pooled**; rupees and
ammunition **each player's own**; story scenes each player's own ("Story scenes: Per player"). `flags.csv` has `default_mode` and
`shared_by_default` for every flag.

## The tools

```sh
python3 flagdata/flagdata.py build --romfs <RomFS> --repo <LS clone> [--rev REV] --out <folder outside this repository> \
    [--names FILE] [--sweep DIR] [--compare-log game.log]
python3 flagdata/flagdata.py lookup <hash> ...            # name, family, category, default mode
python3 flagdata/coop_log.py game.log [--summary]         # a co-op log, each flag line with its flag
```

`build` writes `flags.csv` (the flags co-op keeps), `excluded.csv` (the Bool and Int flags it leaves out, with the reason),
`others.csv` (every entry of the other containers: structs, per-object keys, enums, strings, arrays, expressions), `flags.md` and a
**private cache** under the user's state folder (`$XDG_STATE_HOME/ls-workbench/flagdata`, mode 0600) that the log annotator reads. The
files hold names read from the player's files: they are never written under this checkout, and never committed, posted or sent.
What is published is the flag map, made from them:

```sh
python3 docs/oot/flagmap.py build --from <the folder build wrote> --made-from "<game build, list revision, LS revision>"
python3 docs/oot/flagmap.py check        # every name against its hash, every hash once
python3 docs/oot/flagmap.py find 4d77f1cb
```

`flagdata/README.md` has the tools' details, `flags/README.md` the map's columns and how to refresh it.

## Open questions

- The remaining per-room Bool names, and a way to name the played events that have no row.
- Whether the logic-node ids can be computed from the graphs (they occur as plain integers in no file tried: the files were scanned for
  every aligned 64-bit value whose decimal text hashes to a member).
- Windows: the tools have only run on Linux, from a Python with a zstd (3.14's `compression.zstd`, the `zstandard` package or the `zstd`
  program).
