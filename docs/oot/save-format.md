# The save files' byte layout

The bytes of the four kinds of save file: `slot_NN/progress.sav`, `slot_NN/caption.sav`, `option.sav` and `account.sav`. Each is a
header, a table of 8-byte entries in 32 groups (a flag's hash and either its value or the place its value is kept), a data section
for the values that do not fit a word and, in `progress.sav` only, a run of 64-bit keys. The page says what each part holds, how
to find any flag of the game's list in a file ([flags/README.md](flags/README.md): its *File* and *Group* columns are the first two
steps of that), and what the game checks when it loads one. It was worked out from the two tools that read and write these files
without the game (LS #1401, LS #1403), from the game's lifted loader and writer, and checked on 144 distinct files (39 of them
real players' saves) with the game's own value list (`GameDataList`) read from the player's RomFS (November 2026). **No byte,
hash, position or value of any save is quoted**: the example is made up. Every number in a file is little-endian. Here **tested**
means checked on real files or in the running game (the numbers are under [What was tested](#what-was-tested)), **read** means
worked out from code (the lifted functions below, or LS's tools), **guess** means likely.

**LS code:** `scripts/oot_savefile.py` (LS #1401) and `scripts/oot_save_text.py` (LS #1403), which read and write these files; `host/nn_fs.c` (the `save:` mount)
**See also:** [save-data.md](save-data.md) (where the files are, the slots, the caption manager), [game-data.md](game-data.md) (the list that declares the values and the manager that holds them), [flag-names.md](flag-names.md) (how a hash gets a name), [master-quest.md](master-quest.md) (its slots), [flags/README.md](flags/README.md) (the flag map)

## In short

- A flag lives in **one file**, named by its `SaveFileIndex`, and in that file in **one group**, named by its type. The file holds
  *every* flag of the list that has its file index, once each, in a fixed order, found by hash; a flag that nothing has changed is
  in the file with its default value (most words equal the list's default). **tested**
- A flag of five types (Bool, Int, UInt, Float, Enum) keeps its value in the entry's second word. A flag of the other sixteen types
  keeps in that word the file offset of its bytes in the data section. A `Bool64bitKey` flag has no entry: it is true when its
  64-bit key is in the sorted key run at the end of `progress.sav`. **tested**
- Structs, `BoolExp` flags, and every flag whose `SaveFileIndex` is -1 are in no file (2,978 flags of the list's 26,654 have -1). **tested**
- As far as the code was read, the game checks the first word (`0x01020304`) and the shape of the table, nothing else: no
  checksum, no size field, no check of the revision word. **read**; edited files load in the game (**tested**).

## The files

| File | `SaveFileIndex` | One per | Entries in the table | Table ends at (the word at offset 8) | Largest size (`SaveDataSize`) | Sizes seen | Last table entry's hash (its name) | Sure |
|---|---|---|---|---|---|---|---|---|
| `slot_NN/progress.sav` | 0 | slot | 11,925 | 95,704 | 703,884 | 120,572 to 167,784 | `a3db7114` (`Game`) | tested |
| `option.sav` | 1 | profile | 46 | 672 | 44,660 | 42,100 (all 14 seen) | `a60ba395` (`Option`) | tested |
| `slot_NN/caption.sav` | 2 | slot | 46 | 672 | 42,356 | 34,845 to 42,300 | `26f3523b` (`Caption`) | tested |
| `account.sav` | 3 | profile | 2 | 320 | 320 | 320 | `be9f04bd` (`Account`) | tested |

The file's place is the list's `SaveDirectory` entry of its index (`%02d` is the slot number). A profile folder holds `account.sav`,
`option.sav` and one `slot_NN` folder for each used slot (see [save-data.md](save-data.md) for where LS keeps it). The last entry's
hash is the MurmurHash3 of the name in brackets (all four checked), and equals the list's `SaveTypeHash` for the file's index.

### What the list's `MetaData` says

| Member | Value | What it is | Sure |
|---|---|---|---|
| `SaveDirectory` | `slot_%02d/progress.sav`, `option.sav`, `slot_%02d/caption.sav`, `account.sav` | The file names, in `SaveFileIndex` order | tested |
| `SaveTypeHash` | the four hashes above, as decimal numbers | The last table entry of each file kind | tested |
| `SaveDataOffsetPos` | 95,704, 672, 672, 320 | Where the table ends and the data section begins, per kind: equal to the word at offset 8 of every file | tested |
| `SaveDataSize` | 703,884, 44,660, 42,356, 320 | The biggest a file of the kind can be (not its size: see below) | tested |
| `AllDataSaveOffset`, `AllDataSaveSize` | 106,216 and 842,876 | The same two numbers for one table holding *every* value that has a layout, the unsaved ones too (13,239 entries) | read |
| `FormatVersion` | 1 | Not seen in any file; what uses it is not known | guess |

Both numbers per kind come out of the list's own entries, to the byte, so they say nothing a reader needs to store: the table's
end is `0x28 + 8 × (n + 33)` for `n` flags in the file (the 32 group markers and the tail entry make the 33), and the largest size
is that plus every value at its largest (an array at its total length, a Binary at its declared size, a BinaryArray at its array
size times 4 plus its declared size, a String32 32 bytes, a String64 64, a Vector3 12, a 64-bit number 8) plus, for `progress.sav`,
8 × (11,657 + 1) for a key run with every key set and its end. **tested** (all four kinds; and the two `AllData` numbers fit when
every unsaved flag is added, with a String16 of 16 bytes and a WString16 of 32 bytes: that is evidence for those two sizes,
**guess**). Real files are well under their largest size (a played `progress.sav` is between a sixth and a quarter of it).

## Functions

The loader and the writer are not in any other page. Both are known from the lifted code; neither was run under a debugger here.

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_80bc26c0` | `GameDataMgr_LoadFile(mgr, buffer)` | Takes one file's bytes into the manager's values. It is given the manager and the file's address, no length. It compares the word at offset 0 with `0x01020304` (the answer only becomes the function's result), stores the word at 4 (the revision) at `mgr+3252` and compares it with nothing, takes the word at 8 as the end of the table (a value below 33 ends the load at once), then walks the table from file offset 32: a block opens with an entry whose hash is 0 and whose second word is the type number `t`, and holds the entries up to the next such marker; where a marker belongs, an entry whose hash is not 0 ends the load with result 0. For `t` 0 to 31 it looks each entry's hash up in the type's table in the manager (container `t` at `mgr+0x08+0x60*t`, its hash table at `+0x18`) and writes the live and the saved copy of the value; a hash the table lacks is skipped. `t` = 32 hands the tail entry to `f_80bc5a70`. The only direct caller found is the applier `f_80bb9980`; the result goes to a byte of the file record (the 128-byte records at `mgr+0xcc8`, indexed by file index), which `SaveFile_Read` (`f_83051c60`) turns into its success or its failure state | read |
| `f_80bc5a70` | `GameDataMgr_LoadKeyRun(keys, cursor, buffer, end, kinds)` | The loader's block 32: reads the tail entry (file kind hash, key run offset), finds the hash among the manager's list of file kind hashes (`mgr+3280`) to get the file index, and loads no keys when it is not there. It then walks the manager's sorted 16-byte key records (`mgr+0xc60`) against the file's sorted keys until the key 0: a record whose key is in the run becomes true, one of this file's records that is not becomes false, a key the manager does not know is skipped. `end` is never read, so the run's 0 is the only thing that stops it; an offset of 0 is an empty run (every key of the file's kind comes out false) | read |
| `f_80bc8100` | `GameDataMgr_WriteFile(mgr, request)` | Builds a file's bytes in the file record's buffer (the low byte of `request` is the kind of job, its high half the file index). The pass read: at offset 0 the magic, at 4 the manager's own revision (`mgr+3248`), at 8 the record's table size (`record+84`, which every file shows to be the list's `SaveDataOffsetPos` for the kind), 8 zero bytes at offset 32, then the Bool entries of the file index as `{hash, saved byte}`, taken from the Bool hash table's slots in slot order (the order the file shows, see Notes). The other passes (the other types, the key run) were not read | read |

## The header

| Offset | Field | What | Sure |
|---|---|---|---|
| `0x00` | Magic, u32 | `0x01020304` (the bytes 04 03 02 01). The one header word the loader compares | tested |
| `0x04` | Revision, u32 | 2,982,123 (`0x002d80eb`), the number in `GameDataList.Product.110.revision.txt` beside the list. The game writes its own copy (a manager field) and, on load, stores the file's without comparing it | tested |
| `0x08` | Data offset, u32 | Where the table ends and the data section begins: the list's `SaveDataOffsetPos` for the file kind. It is **not the file's size**: it equals the size only in `account.sav`, which has no data section | tested |
| `0x0c` to `0x27` | Zeros | 28 bytes, zero in every file | tested |

## The table

Entries are 8 bytes each from `0x28`, `{u32 first word, u32 second word}`, and a table is read by walking them in order.

| Offset | Entry | What | Sure |
|---|---|---|---|
| `0x28` on | A flag: `{hash, value}` | The hash of the flag's name and its value word (inline types) or the file offset of its bytes (the sixteen others). A hash is never 0 (none of the list's 14,997 32-bit hashes is) | tested |
| after each group | A group marker: `{0, k}` | A first word of 0 closes group `k`, for `k` = 1 to 32 in order. A group with no flags is just its marker | tested |
| the last 8 bytes before the data offset | The tail: `{file kind hash, key run offset}` | The kind's hash (table above). The second word is the key run's file offset in `progress.sav` and 0 in the three other kinds | tested |

**Groups in this page and in the game.** The numbering here is the one LS's tools use and the flag map uses: group `k` is the
entries *before* the marker `{0, k}`, so group 1 starts at `0x28`. The game's loader reads the same bytes the other way round: a
marker `{0, t}` *opens* block `t` (t from 0 to 32), and the first one is the 8 zero bytes at offset `0x20`, inside the header's
zero padding. Block `t` is the manager's container `t` ([game-data.md](game-data.md): Bool 0, BoolArray 1, Int 2, …, UInt 20), so
**group `k` is the game's type `k - 1`**, and block 32 holds the one tail entry. **read** (the loader's jump table, container by
container), **tested** for the bytes.

Inside a group the entries are in one fixed order, the same in every file of a kind (one sequence per kind over all 144 files),
**not** the list's order and **not** by hash. It follows the slot order of the game's own hash table for the type (see Notes).
**tested**

### The 32 groups

| Group | Game's type `k - 1` | Type | In which files | Sure |
|---|---|---|---|---|
| 1 | 0 | Bool | all four | tested |
| 2 | 1 | BoolArray | `progress.sav` | tested |
| 3 | 2 | Int | `progress.sav`, `option.sav`, `caption.sav` | tested |
| 4 | 3 | IntArray | `progress.sav`, `option.sav` | tested |
| 5 | 4 | Float | `progress.sav`, `caption.sav` | tested |
| 6 | 5 | FloatArray | `progress.sav` | tested |
| 7 | 6 | Enum | `progress.sav`, `option.sav` | tested |
| 8 | 7 | EnumArray | `progress.sav` | tested |
| 9, 10 | 8, 9 | none known | no file seen; no type of the list has them | tested (empty), guess (what they would hold) |
| 11 | 10 | Vector3 | `progress.sav`, `caption.sav` | tested |
| 12, 13, 14 | 11, 12, 13 | none known | no file seen | tested (empty) |
| 15 | 14 | String32 | `progress.sav` | tested |
| 16 | 15 | none known | no file seen | tested (empty) |
| 17 | 16 | String64 | `progress.sav`, `caption.sav` | tested |
| 18 | 17 | String64Array | `progress.sav`, `caption.sav` | tested |
| 19 | 18 | Binary | `progress.sav`, `option.sav`, `caption.sav` | tested |
| 20 | 19 | BinaryArray | `progress.sav` | tested |
| 21 | 20 | UInt | `progress.sav`, `caption.sav` | tested |
| 22 | 21 | UIntArray | `progress.sav` | tested |
| 23 | 22 | Int64 | `progress.sav`, `option.sav` | tested |
| 24 | 23 | Int64Array | `option.sav` | tested |
| 25 | 24 | UInt64 | `progress.sav` | tested |
| 26 | 25 | UInt64Array | `progress.sav` | tested |
| 27 | 26 | none known (guess: WString16, the list's never-saved type, next to its array form, group 28) | no file seen | tested (empty), guess |
| 28 | 27 | WString16Array | `progress.sav` | tested |
| 29 to 32 | 28 to 31 | none known | no file seen | tested (empty) |

The loader has a branch for every one of the 32 types, so the empty groups exist in the game; the list names no type for them.
Groups used per file kind: `progress.sav` 20 (1 to 8, 11, 15, 17 to 23, 25, 26, 28), `option.sav` 7 (1, 3, 4, 7, 19, 23, 24),
`caption.sav` 8 (1, 3, 5, 11, 17, 18, 19, 21), `account.sav` 1 (group 1). **tested**

### The list's types and their groups

All 26 types of the list (26,654 flags). The counts are the list's entries of the type by `SaveFileIndex`; a type's flags can be in
several files. **tested** (the group column from the real files, the counts from the list)

| Type | In the list | `progress.sav` (0) | `option.sav` (1) | `caption.sav` (2) | `account.sav` (3) | Not saved (-1) | Group |
|---|---|---|---|---|---|---|---|
| Bool | 11,292 | 10,212 | 14 | 27 | 2 | 1,037 | 1 |
| BoolArray | 13 | 6 | | | | 7 | 2 |
| Int | 1,259 | 1,144 | 8 | 12 | | 95 | 3 |
| IntArray | 156 | 155 | 1 | | | | 4 |
| Float | 89 | 76 | | 1 | | 12 | 5 |
| FloatArray | 4 | 3 | | | | 1 | 6 |
| Enum | 130 | 101 | 8 | | | 21 | 7 |
| EnumArray | 14 | 14 | | | | | 8 |
| Vector3 | 26 | 16 | | 1 | | 9 | 11 |
| String32 | 2 | 1 | | | | 1 | 15 |
| String64 | 54 | 30 | | 2 | | 22 | 17 |
| String64Array | 5 | 3 | | 1 | | 1 | 18 |
| Binary | 11 | 3 | 6 | 1 | | 1 | 19 |
| BinaryArray | 2 | 2 | | | | | 20 |
| UInt | 97 | 87 | | 1 | | 9 | 21 |
| UIntArray | 33 | 33 | | | | | 22 |
| Int64 | 33 | 28 | 5 | | | | 23 |
| Int64Array | 4 | | 4 | | | | 24 |
| UInt64 | 6 | 5 | | | | 1 | 25 |
| UInt64Array | 4 | 4 | | | | | 26 |
| WString16Array | 2 | 2 | | | | | 28 |
| Bool64bitKey | 11,657 | 11,657 | | | | | none: the key run |
| BoolExp | 884 | | | | | 884 | none: computed, never saved |
| Struct | 874 | | | | | 874 | none: never saved (its members are flat flags of other types) |
| String16 | 1 | | | | | 1 | none: never saved |
| WString16 | 2 | | | | | 2 | none: never saved |

The 11,657 `Bool64bitKey` flags are all file 0, but they are not in the table (see The key run). The table of `progress.sav` holds
the other 11,925. A type's flags with -1 appear in no file, whatever the type.

## The data section

From the table's end (the word at offset 8) to the key run (`progress.sav`) or the end of the file. The values come one after
another in **table order** (group by group, entry by entry), with no gap and no padding, and each starts where the table entry's
second word says. Sixteen types keep their value here; each layout below was used to walk every data section of the 144 files
and the values tiled the section exactly, to the key run's offset or the end of the file (19,764 values).

| Type (group) | Layout | Seen in real files | Sure |
|---|---|---|---|
| BoolArray (2) | u32 count `n`, then ⌈n/32⌉ u32 words; element `i` is bit `i mod 32` of word `i / 32` | every one is a single word (`n` 5 to 10), the bits above `n` zero (378 of 378); a count of more than 32 only in LS's tools' own tests | tested up to 32, read above |
| IntArray (4) | u32 `n`, then `n` × i32 | 9,779 | tested |
| FloatArray (6) | u32 `n`, then `n` × f32 | 189 | tested |
| EnumArray (8) | u32 `n`, then `n` × u32, each the hash of one of the entry's value names | 882, every element one of its entry's names | tested |
| Vector3 (11) | 3 × f32 (x, y, z); no count; 12 bytes | 1,073 | tested |
| String32 (15) | A 32-byte buffer: UTF-8 text, a 0, then anything | 63 | tested |
| String64 (17) | The same in 64 bytes | 2,020 | tested |
| String64Array (18) | u32 `n`, then `n` × 64-byte buffers | 254 (2,097 buffers) | tested |
| Binary (19) | u32 byte length `L`, then `L` bytes | 338; the length varies from file to file in `progress.sav` (three) and `caption.sav` (the picture), not in `option.sav` | tested |
| BinaryArray (20) | u32 `n`, then `n` × (u32 length, bytes) | 126, every one with the list's array size (10) of elements and every element empty: a filled one has not been seen, so the element layout is LS's tools' | tested for empty, read for filled |
| UIntArray (22) | u32 `n`, then `n` × u32 | 2,079 | tested |
| Int64 (23) | One i64, 8 bytes | 1,834 | tested |
| Int64Array (24) | u32 `n`, then `n` × i64 | 56 | tested |
| UInt64 (25) | One u64, 8 bytes | 315 | tested |
| UInt64Array (26) | u32 `n`, then `n` × u64 | 252 | tested |
| WString16Array (28) | u32 `n`, then `n` × 32-byte buffers of UTF-16LE text (16 code units, a 0 ends it) | 126, with the list's 10 elements each, every one empty: the text coding is LS's tools' | tested for size, read for text |

The count of an array in a file is **always the list's total length** for that entry (14,121 of 14,121 arrays; for a BinaryArray its
array size): a file does not hold a shorter array. A Binary's declared size in the list is what the largest file size counts for
it (the caption picture's is 40,960 bytes; the longest real picture was 40,904); the length in the file is what it holds. **tested**

In `caption.sav` the one Binary is the Load screen's picture: the length, then a JPEG (all 65 begin with FF D8 and end with FF D9,
33,449 to 40,904 bytes). **tested**

### Values kept in the table's word

| Type (group) | The second word | Sure |
|---|---|---|
| Bool (1) | 0 or 1: every Bool word of every file | tested |
| Int (3) | A signed 32-bit number (two's complement): the list's negative defaults appear as such wherever the word is unchanged | tested |
| UInt (21) | An unsigned 32-bit number | read |
| Float (5) | The bits of an IEEE-754 binary32 float: the list's default floats match bit for bit | tested |
| Enum (7) | The hash of the chosen value's name, one of the entry's value names in every file (6,475 words) | tested |

A flag is stored with its default from the list until something changes it: in the 63 `progress.sav` files 91.5% of the Bool words
(588,519 of 643,356), 91.3% of the Int and 94.7% of the Float words equal the list's default. **tested**

### Strings and the old bytes after their end

A string's text ends at the first 0 byte; none of 4,180 buffers (63 String32, 2,020 String64, 2,097 String64Array elements)
lacked one. The game does not clear a buffer when it stores a shorter text, so **bytes of an older, longer text can stay after the
end**: 64 of the 4,180 buffers have non-zero bytes after the first 0 (63 start right after it, 62 are one run, all printable
ASCII), none of the 63 String32 and none of the WString16Array elements (all empty). **tested**. The cause is **guess**: the
string setter copies the new text and its end into a buffer and the file takes the whole buffer
(`GameDataMgr_PushString64`, [game-data.md](game-data.md)). A reader stops at the first 0 and ignores the rest; a writer that wants
the file byte for byte as the game wrote it keeps the old bytes. 1,150 of the 2,020 String64 buffers are all zero (empty strings).

## The key run

The `Bool64bitKey` flags (11,657 in the list) are mostly one flag per placed object that can be taken or broken (a Gold Skulltula,
a heart piece or container, a silver rupee, a breakable) and have **no table entry**. They are kept in `progress.sav` after the
data section:

| Part | What | Sure |
|---|---|---|
| Offset | The second word of the tail entry (the table's last 8 bytes). Equal to where the data section ends in all 63 files | tested |
| The keys | 64-bit unsigned numbers, **strictly ascending** (compared as unsigned), one for every key that is **true**; a key that is not there is false | tested |
| The end | One more 0, as the file's last 8 bytes. No count: the number of true keys is `(size - offset) / 8 - 1`. A key is never 0 | tested |

The 63 files hold 0 to 739 keys; every key is a `Bool64bitKey` hash of the list; every file's size is the offset plus
8 × (keys + 1). A key is **not** a 32-bit hash: 3,686 of the 11,657 are the 64-bit `Hash` of a placed object in the game's
placement files (`Banc/`: 128,296 distinct `Hash` values were read from the player's RomFS and 3,686 of them are in the list); the other
7,971 are not placement hashes, and how they are made is not known. **tested** (the 3,686), **guess** (that the rest are derived
from names). The list has an extra byte for 2,424 of the keys (all of reset kind 88) that no file holds.

The loader reads the run until its 0 with no other bound (`f_80bc5a70`), so a run without its 0 would read past the buffer.
**read**. The key run is not the only part that changes size: the three Binary values of `progress.sav` change length too (17
distinct sizes in 63 files).

## Hashes: how a flag is named

- A flag's hash is the MurmurHash3 (x86, 32 bit, seed 0) of its name's UTF-8 bytes ([game-data.md](game-data.md),
  [flag-names.md](flag-names.md)). The table holds that hash and no name. **tested** (the names of six of
  [game-data.md](game-data.md)'s known values recompute to the hashes it lists; a flat flag's hash is in the list, a struct
  member's plain-name hash is not: the list holds the `Struct.member` one).
- A struct's member is a flat flag named `Struct.member`; its hash is of that whole text. The struct itself is never saved.
  **tested**
- An enum's value in a file is the hash of the value's name: a reader gets the name by hashing the entry's value names
  (`RawValues`) and comparing. **tested**
- **The file kind hashes are of the plain words** `Game` (`progress.sav`), `Option`, `Caption` and `Account`. **tested**
- 64-bit keys: see The key run.
- The list holds 14,997 flags with a 32-bit hash and no hash is in it twice (not even across types). **tested**

## Slots, files and Master Quest

- `progress.sav` and `caption.sav` of slot `N` are `slot_NN/progress.sav` and `slot_NN/caption.sav` (two digits); `option.sav`
  and `account.sav` are one per profile. A game uses slots 0 to 5; the real saves seen have slots 00 to 05 only. **tested**
- **Master Quest slot `i` is the folder `slot_{i+6}`**: the load, the caption request and the save slot add 6 to the slot number
  in Master Quest mode (`f_832e1db0`, `f_80cdc350`, `f_811f4910`, [save-data.md](save-data.md), [master-quest.md](master-quest.md)),
  so Master Quest uses `slot_06` to `slot_11` with the same two files. **read**
- **Not tested:** no file in a slot above 05 was found among the 800 files on this PC, so the layout of a Master Quest slot's files
  is not checked. They are written by the same code as the others; the expectation is the same layout with the same group
  contents (**guess**).
- `account.sav`: group 1 only, two Bool flags, no data section; its table is 35 entries (the two flags, the 32 markers and the tail), 320 bytes with the header.

## What the game checks on load

The checks are in `f_80bc26c0`, `f_80bc5a70` and `SaveFile_Read` (`f_83051c60`), above. **Not tested in the game**: no file with a
wrong magic word, a wrong offset, a wrong revision or a cut table was loaded; the rows say what the code does.

| Part of the file | What the game does | Sure |
|---|---|---|
| Magic word | Compared with `0x01020304`. A mismatch gives the load result 0, which `SaveFile_Read` turns into its failure state; the loader **still walks the table and applies it** | read |
| Revision (the word at 4) | Stored at `mgr+3252`, compared with nothing in the loader. No other reader of that field was found (the search was not exhaustive); the game writes its own number from another field. So, as far as is read, a file of another flag-list revision loads: its flags are matched by hash and an unknown hash is skipped | read |
| Data offset (the word at 8) | The end of the walk of the table; below 33 the load stops at once. Never compared with a file size | read |
| Table shape | A block must open with an entry whose first word is 0, else the load ends with result 0. A marker's second word picks the type; 32 is the tail | read |
| An entry's hash | Looked up in the type's table. A hash that is not there is **skipped** without a message (read for Bool; the other types' branches have the same shape). Whether the entry's own `SaveFileIndex` agrees with the file is not checked | read |
| A data offset | Used as the entry says, with no bound: the loader is given no file length | read |
| A Binary's length | Copied as the file says; only a length with the top bit set is refused; no comparison with the declared size was seen | read |
| The key run | Read to its 0 with no bound; keys are loaded only when the tail's hash is one of the file kinds' hashes; unknown keys are skipped | read |
| Checksum, size field, compression, encryption | None seen in the loader (not every line of it was read). **No file has one**: 20 library saves made by changing values of real files in place, with nothing recomputed, were loaded and played in the game, and a `caption.sav` whose picture and date were replaced (so its size changed) loaded as the original did | tested |
| Missing flag | The loader only visits the entries present, so a flag the file lacks would keep what the manager already holds. No real file lacks one | read |
| The tools' rule | LS's editor refuses a file whose revision is not the game's list. That is the tool's rule, not the game's | read |

## Finding a flag of the flag map in a file

1. **File.** The flag's `SaveFileIndex`: 0 is `slot_NN/progress.sav`, 1 `option.sav`, 2 `slot_NN/caption.sav`, 3 `account.sav`,
   -1 no file. For a slot's file take the slot's folder, for the other two the profile's. A `Bool64bitKey` flag is always 0 (step 5).
   Structs, `BoolExp` flags and all the other -1 flags have no place in any file (the list: 2,978 flags, 884 of them `BoolExp`, 874
   structs).
2. **Group.** From the flag's type, by [the types table](#the-lists-types-and-their-groups): Bool 1, BoolArray 2, Int 3,
   IntArray 4, Float 5, FloatArray 6, Enum 7, EnumArray 8, Vector3 11, String32 15, String64 17, String64Array 18, Binary 19,
   BinaryArray 20, UInt 21, UIntArray 22, Int64 23, Int64Array 24, UInt64 25, UInt64Array 26, WString16Array 28.
3. **Entry.** Check the header (the magic, and the word at 4 equal to the list's revision for this game build), then read 8-byte entries from
   `0x28`. The group's entries are those after the marker `{0, group - 1}` (from `0x28` for group 1) and before `{0, group}`. The
   entry whose first word is the flag's hash is the flag. It is always there: a missing hash means the wrong file or the wrong
   revision.
4. **Value.** For Bool, Int, UInt, Float and Enum the entry's second word is the value. For the other sixteen types it is the
   file offset of the bytes: read them by [the layouts](#the-data-section).
5. **Key flag.** Take the tail entry's second word as the offset and look the flag's 64-bit key up in the sorted run to the end of
   the file: found is true, not found false.
6. A struct's member is looked up as the flat flag `Struct.member` (its own hash, type, file and group); a struct and a `BoolExp`
   have no value of their own.

For the flag map's *File* column the value is the list's `SaveFileIndex` and for its *Group* column the number in step 2; both
are **tested** against the real files (every flag of the list that has an index is in the file of that index, once, in the group
of its type: 144 of 144 files).

## A made-up file

Nine invented flags and three invented keys, in a table that keeps the real layout: 32 group markers and a tail, and the offsets
below are this file's own. The hashes, the values and the keys are made up (the revision and the kind hash are the game's
constants). The real tables hold the whole list (11,925 entries in `progress.sav`), so a real file is far longer.

```
offset  word 0    word 1    what
0x000   01020304  002d80eb  magic (bytes 04 03 02 01); revision
0x008   00000178  00000000  data offset: the table ends at 0x178; first of the zeros
0x010   00000000  00000000  zeros
0x018   00000000  00000000  zeros
0x020   00000000  00000000  zeros (the game reads these 8 bytes as the marker {0, 0})
0x028   1a2b0001  00000001  group 1, Bool: true
0x030   1a2b0002  00000000  group 1, Bool: false
0x038   00000000  00000001  marker: group 1 ends
0x040   00000000  00000002  marker: group 2 (BoolArray) is empty
0x048   2c3d0001  fffffffd  group 3, Int: -3
0x050   00000000  00000003  marker: group 3 ends
0x058   00000000  00000004  marker: group 4 (IntArray) is empty
0x060   3e4f0001  3fc00000  group 5, Float: 1.5
0x068   00000000  00000005  marker: group 5 ends
0x070   00000000  00000006  marker: group 6 (FloatArray) is empty
0x078   4a5b0001  5c6d7e8f  group 7, Enum: the hash of a made-up value name
0x080   00000000  00000007  marker: group 7 ends
0x088   ..        ..        3 rows 0x088-0x098: markers 8, 9, 10, all empty
0x0a0   5b6c0001  00000178  group 11, Vector3: its 12 bytes are at offset 0x178
0x0a8   ..        ..        6 rows 0x0a8-0x0d0: markers 11 to 16, all empty
0x0d8   6c7d0001  00000184  group 17, String64: its 64 bytes are at offset 0x184
0x0e0   ..        ..        5 rows 0x0e0-0x100: markers 17 to 21, all empty
0x108   7d8e0001  000001c4  group 22, UIntArray: its bytes are at offset 0x1c4
0x110   00000000  00000016  marker: group 22 ends (0x16 = 22)
0x118   8e9f0001  000001d4  group 23, Int64: its 8 bytes are at offset 0x1d4
0x120   ..        ..        10 rows 0x120-0x168: markers 23 to 32, all empty
0x170   a3db7114  000001dc  tail: the file kind (progress), and the key run is at 0x1dc

0x178   3f800000  40000000  data, group 11: 1.0, 2.0,
0x180   40400000            3.0
0x184   48 69 00 6c 00 ..   data, group 17: "Hi", its end, an 'l' left from an older "Hill", zeros to 0x1c4
0x1c4   00000003            data, group 22: three elements
0x1c8   00000007  00000008  7, 8,
0x1d0   00000009            9
0x1d4   fffffffb  ffffffff  data, group 23: -5 (low word first)

0x1dc   0000000000000007    key run: three keys, ascending...
0x1e4   1234567890abcdef
0x1ec   fedcba9876543210
0x1f4   0000000000000000    ...and the end; the file is 0x1fc = 508 bytes long
```

(A `..` row stands for the run of empty-group markers it names, one 8-byte `{0, k}` entry each.) Reading it: the Int flag `2c3d0001` is type Int, so group 3; its entry is between marker 2 (`0x40`) and
marker 3 (`0x50`), at `0x48`, with value `fffffffd`, which is -3. The Vector3 flag `5b6c0001` is group 11, between markers 10
and 11, at `0x0a0`; its second word `0x178` is where its 12 bytes are. The key `1234567890abcdef` is in the run: true; the
key `1234567890abcdee` is not: false. The string flag's text is "Hi": reading stops at the first 0 and the `l` after it is old.

## What was tested

Everything was read from the files and the list **read-only**. The 800 files on this PC (a library of 58 save folders and the
player's finished 100% save) are 144 distinct files: 63 `progress.sav`, 65 `caption.sav`, 14 `option.sav`, 2 `account.sav`. 39 of
them (15 + 16 + 6 + 2) are recorded as real saves, written by the game for a player; the other 105 are test fixtures made by
tools that change values in place, or by playing from a real save. Every check passed in all 144 files, and in the 39 real ones.

| What | Result |
|---|---|
| Header | The magic is `0x01020304`; the word at 4 is the list's revision (2,982,123); the word at 8 is `SaveDataOffsetPos` of the kind and where the table ends; bytes `0x0c` to `0x27` are zero; the last table entry's hash is the kind's `SaveTypeHash` (144 of 144) |
| Table | Markers 1 to 32 in order; no hash twice; every hash is in the list; the table holds exactly the list's flags of the file's `SaveFileIndex` (no key flag, no struct, no `BoolExp`, no -1 flag): every index lands in the file `SaveDirectory` names. The tail's second word is 0 in the 81 files that are not `progress.sav` |
| Types and groups | The list's type of every entry is its group's type; 21 types in 21 groups; groups 9, 10, 12, 13, 14, 16, 27 and 29 to 32 are empty in every file. One order of entries per kind over all files |
| Data section | 19,764 values walked by the 16 layouts, each starting where the last ended; array counts equal the list's total length (14,121 arrays); BoolArray bits above the count zero (378); Enum words and EnumArray elements are hashes of the entry's value names (6,475 and 882) |
| Strings | 4,180 buffers all have an end; 64 hold old bytes after it; 65 of 65 pictures are JPEGs of 33,449 to 40,904 bytes (capacity 40,960) |
| Key run | 63 `progress.sav`: offset equals the data end, a multiple of 8 long, ends in 0, strictly ascending, every key in the list, size equal to offset + 8 × (keys + 1); 0 to 739 keys |
| Sizes | Every file is at most `SaveDataSize` of its kind. `progress.sav` 17 distinct sizes (120,572 to 167,784), `caption.sav` 21 (34,845 to 42,300), `option.sav` 42,100, `account.sav` 320 |
| The list | `SaveDataOffsetPos`, `SaveDataSize`, `AllDataSaveOffset`, `AllDataSaveSize` all recomputed from the list's entries (see above) |
| Hashes | The four file kind hashes are the MurmurHash3 of `Game`, `Option`, `Caption`, `Account`; six of the known flag names of [game-data.md](game-data.md) recompute to their hashes |
| Placed objects | 3,686 of 11,657 keys equal a placement `Hash` of the player's `Banc/` files |
| The game | 20 library saves made by editing real files in place were loaded and played; a `caption.sav` with another picture, date and size loaded. Not run for this page |
| Not tested | A Master Quest slot (none on this PC); a file with a wrong magic, revision, offset or length; a BoolArray of more than 32 bits, a filled BinaryArray, a filled WString16Array (the real files have none) |

## Notes

- **The order of a group.** In every file the entries of a type are in the order of the slots of the game's own hash table for
  that type: ascending by the hash modulo the number of that type's entries in the list (the table seems to be as big as the
  list's count for the type: 1,259 for Int, 11,292 for Bool, 97 for UInt, 130 for Enum, 54 for String64: the best fit), with entries that collide moved to a
  nearby slot, and then only the entries of the file's index kept. For Int in a `progress.sav` the home slots are in order except
  at 94 of 1,143 steps. The exact placement of colliding entries was not reproduced; the writer reads the table in slot order
  (`f_80bc8100`, Bool pass). A reader should not depend on the order: find a flag by its hash. **tested** (the home-slot order),
  **read** (the writer)
- **No size field, one fixed table.** The table is always complete, so its length and the data offset are constants of the kind;
  the only things that grow are the three Binary values and the key run of `progress.sav` and the picture of `caption.sav`.
- **LS's tools:** `oot_savefile.py` keeps a file byte for byte when nothing is set and rebuilds only the key run;
  `oot_save_text.py` rebuilds a whole file from JSON and keeps a string's old bytes as a `residue`. Both agree with the layouts
  here; `oot_save_text.py` names the groups with no entries `Group09`, … and keeps their bytes raw.

## Open questions

- A Master Quest slot's files (`slot_06` to `slot_11`): save once in Master Quest and run the same checks; expected, the same layout.
- Whether the game really ignores the revision word, and what a wrong magic word does on screen: copy a save, change the word,
  load it from Continue; expected, the first loads and the second shows the slot as broken. The one other hash the key loader
  treats specially (`0x0179ec2d`, which it accepts without a file index) is not understood.
- What the groups 9, 10, 12, 13, 14, 16, 27 and 29 to 32 would hold, and where the list's String16 and WString16 would sit; a
  file with an entry there would show it.
- The exact slot placement of colliding entries (the order of a group): reproduce it by building the table from the list in some
  order and probing; the right order would match every file.
- What a filled BinaryArray, a filled WString16Array and a BoolArray of more than 32 elements look like in a real file; the layouts
  here are LS's tools'.
- How the 7,971 non-placement keys are made, and what the list's extra byte on 2,424 keys is for.
- What `FormatVersion` (1) and the `AllData…` numbers are used for.
