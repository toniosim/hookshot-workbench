# Game data and the save files

How the game keeps its flags and values ("game data"), how code reads them, and what the save files hold. Looked at while
looking for a way to try Master Quest (November 2026), and for the debug tools' flag reads and writes.

**LS code:** `host/hos_main.c` (`oot_gamedata_bool`, `oot_gamedata_set_bool`)
**See also:** [save-data.md](save-data.md), [save-format.md](save-format.md) (the save files' bytes), [master-quest.md](master-quest.md), [flag-names.md](flag-names.md)

## How the game declares its values

The game's values are declared in `GameData/GameDataList.Product.110.byml.zs` in the RomFS: a zstd-compressed BYML, using the
dictionary in `Pack/ZsDic.pack.zs`. **tested**

- **`Data`** holds one table per type. Each entry has a `Hash`, a `DefaultValue`, a `ResetTypeValue` and a `SaveFileIndex`.

  | Type | Entries |
  |---|---|
  | Bool | 11292 |
  | Bool64bitKey | 11657 |
  | BoolExp | 884 |
  | Enum | 130 |
  | Float | 89 |
  | Int | 1259 |
  | Int64 | 33 |
  | Struct | 874 |
  | UInt | 97 |
  | Vector3 | 26 |
  | String / WString | a few |

  There are also array forms of most types.

- **`SaveFileIndex`** says which file a value is saved in:

  | Index | File |
  |---|---|
  | 0 | `slot_NN/progress.sav` |
  | 1 | `option.sav` |
  | 2 | `slot_NN/caption.sav` |
  | 3 | `account.sav` |

- **`MetaData`** holds `SaveDirectory`, the file names (`slot_%02d/progress.sav`, `option.sav`, `slot_%02d/caption.sav`,
  `account.sav`), `SaveTypeHash` (each file's last table entry), `SaveDataOffsetPos` (95704, 672, 672, 320: where each kind of
  file's table ends and its data section begins, the third word of its header), `SaveDataSize` (703884, 44660, 42356, 320 bytes:
  the largest each kind can be), two `AllData…` numbers and a `FormatVersion`. The numbers come out of the list's own entries,
  see [save-format.md](save-format.md).
- **Flag names are not in the game.** A flag is known only by the murmur3 (x86, 32-bit, seed 0) hash of its name; the hash
  function was checked against a known name, `SelectedCaptionIndex` → `0x1a49c4f6`. Hashing every identifier in the
  executable (163,375 strings) matched neither account flag below, so the names live in data, if anywhere: in the game's other files, as
  identifiers a flow, a graph or a table spells out. How most of them are recovered, and what stays unnamed: [flag-names.md](flag-names.md). **tested**
- **The code reads values by hash**, through the game-data manager, with the hash built in registers. Look for MOVZ/MOVK
  pairs such as `0x5097` / `0xa299` (that is, 0xa2995097). A flag can also be read as a member of a struct, by the plain
  hash of the member's name rather than the flat hash of `Struct.member`; the played flags are read both ways, so a scan
  for the flat hash alone misses the struct reads (`f_805a1170`, under *Reading values*). **read**

## Functions

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_80cbf5e0` | `GameDataMgr_ReadFileList` | Reads the list's MetaData (FormatVersion, SaveDirectory, SaveDataSize, SaveTypeHash, SaveDataOffsetPos) into the game-data manager (`[0x84ea42a8]`), its file records included; called by `f_80e1f010` | read |
| `f_8022d9c0` | `GameDataMgr_GetBool` | A bool by its name's hash: the `(hash, index)` table at `mgr+32` (its size at `+44`), then the bools' 24-byte entries at `mgr+24` (their count at `+16`), the value at `+22` of an entry. The live value only: the pending ring is not looked at; a hash in the BoolArray container returns the first element of its array, after the element's own virtual call (vtable `+0x20`) has answered 1 or more | tested |
| `f_80cd0ea0` | `GameDataMgr_GetString64` | A String64 by its name's hash | tested |
| `f_809d3eb0` | `GameDataMgr_FindStruct(mgr, handle*, structHash)` | Finds a game-data struct by its name's hash (table at `mgr+3104`, size `+3116`, 32-byte entries at `+3096`) and fills the handle: `+0` the struct's descriptor, `+8` 0, `+12` set when the entry's kind (`entry+24`) is 2 or more. `f_809d39e0` and `f_805b60b0` take that handle to reach a member by hash (the save list's CaptionData pick, [save-list.md](save-list.md)) | read |
| `f_809d39e0` | `GameDataMgr_SetStructField(mgr, value, handle, memberHash)` | Writes one member of a game-data struct: resolves the member through the struct's descriptor (`handle+0`: its table at `+8`, its size at `+20`) to the member's flat hash, checks that hash is in the Int table and queues `{value, flat hash}` on the Int ring (assign), like `f_80183b70`. The pouch code writes `PlayerStatus` members this way; the save list's CaptionData pick uses it with `f_809d3eb0` | read |
| `f_805b60b0` | `GameDataMgr_GetStructField(mgr, out, handle, memberHash)` | Reads one member of a game-data struct: resolves the member to its flat hash through the descriptor, first asks a virtual method of the Int container (vtable slot 4 of the object at manager `+200`), else reads the entry's live value (`entry+28`); returns whether it was found. `f_8112d570` reads `PlayerStatus.MPMax` with it | read |
| `f_809d32b0` | `PlayerStatus_CopyMembers` | Reads and rewrites a group of `PlayerStatus` members (MP and MPMax among them) between two struct handles; called while a save is loaded or filled (`f_806a3810`, `f_833ed200`) | read |
| `f_806a2b20` | `GameDataMgr_SetBool(mgr, value, hash)` | Sets a Bool: enqueues `{u8 value & 1, u32 hash}` (an 8-byte slot) on the Bool ring (container at `+0x08`: capacity `+0x30`, slots `+0x38`, ring word `+0x40`); a full ring or a round change aborts the game (`f_8351c280`). A hash that is not in the Bool table but in the BoolArray container's (table `+0x80`, 0x40-byte elements at `+0x78`) makes the element's own virtual call (vtable `+0x20`) and, when that returns 1 or more, `f_8378a0b0` queues the write as an 8-byte slot `{hash, a word whose bit 31 is the value}` on the BoolArray's ring (capacity `+0x90`, slots `+0x98`, word `+0xa0`; the same protocol and abort). Nothing is written to the entry until the applier runs (see Notes). `SeqOneShotSetMQMode` clears `IsLastSelectedMQMode` with it ([master-quest.md](master-quest.md)) | read |
| `f_83051aa0` | `GameClear_SetFlags` | At the game's end: sets `IsGameClear`, `IsGameClearAtLeastOnce`, CaptionData's `IsClear` and the `DefeatedEnemyNum` fields for Ganon and Ganondorf. Called by `f_832962b0` (a script node class's method) | read |
| `f_80857070` | `GameDataMgr_GetInt` | Reads an int by hash (the save list's last picked index, 0xa2995097) | read |

### Setting values: the rings

Every setter queues a write on its container's ring and the applier (below) does the writing. See *How a set reaches a value* in Notes. `K` is a container's base, `mgr+0x008 + 0x60*type` (the table under *Structures*).

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_80183b70` | `GameDataMgr_SetInt(mgr, value, hash)` | Sets an Int flag: `x0` the GameDataMgr (`[[0x84c9e180]]`, = `[0x84ea42a8]`), `x1` the 32-bit value, `x2` the murmur3 hash; hash 0 returns at once. A hash in the Int container's table (container at manager `+0xc8`) queues `{value, hash}` (a 12-byte slot; the setter does not write the slot's third word, which the applier reads as the mode and finds 0, assign, because it clears slots) on that container's ring (ring capacity at manager `+0xf0`, slots at `+0xf8`, counter at `+0x100`: low 20 bits taken, bits 20 to 27 finished, bits 28 to 31 the round); a full ring or a round that changed while the slot was filled ends in the abort `f_8351c280`; nothing is written to the entry here (the per-frame applier `f_80bb9980` does it). A hash not in that table is looked up in the IntArray container at manager `+0x128` (0x40-byte elements): the element's own virtual call (vtable `+0x20`) is made with the value and the hash and, when it returns 1 or more, `f_8378a590` queues the write as a 16-byte slot `{value, 0, hash}` on that container's own ring (capacity `+0x150`, slots `+0x158`, word `+0x160`, the same protocol and abort); a hash in neither table returns without a word (no error is logged). Not a message-argument setter: `SaveCard_FillFromRecord` (`f_833ec8f0`) writes a save slot's date numbers through it into the same GameDataMgr. Hooked by nothing; `host/oot_coop.c` calls it (from the present thread: see Notes, *How a set reaches a value*) | read |
| `f_80fe42d0` | `GameDataMgr_AddInt(mgr, delta, hash)` | The Int setter with mode 1 (add): the same ring protocol as `f_80183b70`, with the slot's third word set to 1; the applier adds and only guards overflow, it does not clamp to any maximum. Called by `f_8112d570` and the event one-shots. An add on `PlayerStatus.MPEconomy` changes nothing: the game assigns it 0 behind the add in the same pass (Notes) | read |
| `f_80400980` | `GameDataMgr_SetEnum(mgr, value, hash)` | Enqueues {u32 value, u32 hash} (8-byte slot) into the Enum ring (K=0x248: cap +0x270, slots +0x278, word +0x280); never writes the entry; full ring or round change aborts. The value the co-op kit passes is the hash of an enumerator's name; it is not checked against the declared ones, and a flag hash found in neither table is ignored | read |
| `f_80bc6f80` | `GameDataMgr_SetFloat(mgr, hash, v0)` | Enqueues {f32 value, hash, mode 0} (12-byte slot) into the Float ring (K=0x188: cap +0x1b0, slots +0x1b8, word +0x1c0); hash is x1, the value v0 | read |
| `f_8059af30` | `GameDataMgr_AddUInt(mgr, delta, hash)` | Enqueues {value, hash, mode 1} into the UInt ring (K=0x788: cap +0x7b0, slots +0x7b8, word +0x7c0); the applier ADDS the value (overflow dropped). A caller that takes this for a "set UInt" (another project's `0x57af30` is this function) adds instead of assigning | read |
| `f_8059bcc0` | `GameDataMgr_SetUInt(mgr, value, hash)` | Same ring, mode 0: the applier assigns (skipped when unchanged). The real UInt set | read |
| `f_8378b9b0` | `GameDataMgr_PushString64(container, entry*)` | The String64 setter's push: `x0` the String64 container (manager `+0x608`), `x1` points to `{char *text, u32 hash at +8}`. Takes a ring slot by compare-and-swap on the word at container `+0x38` (capacity `+0x28`, 0x58-byte slots at the pointer at `+0x30`), stores the hash at slot `+0x50` and copies the text into the slot's own buffer (clamped to its size minus 1); a full ring ends in the abort `f_8351c280`. The applier then writes the live text and the saved copy. Used by the co-op progress mend to equip a shared ocarina (`PlayerStatus.EquipOcarina`) | read |
| `f_83781720` | `GameDataMgr_SetKey64(mgr, value, key)` | Same search; if found pushes {value&1, record index} through `f_80f271c0(mgr+0xc58, value&1, key, index)`; key 0 or absent: nothing | read |
| `f_80f271c0` | `KeyContainer_PushWrite(container, value, key, index)` | Take a slot (taken < cap at container+0x10 else abort), store u8 value at slot+0 and the u32 record index at slot+4 (8-byte slots, ptr container+0x18), then finish-count on the word at container+0x20; round change between take and finish aborts | read |

### Reading values

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_808073d0` | `GameDataMgr_GetEnum(mgr, out*, hash)` | Reads an Enum's live u32 (entry 0x38 bytes, value +0x1c) from the Enum container K=0x248 by hash; 1 on success, EnumArray first element as fallback; ignores the pending ring | read |
| `f_8059a4e0` | `GameDataMgr_GetUInt(mgr, out*, hash)` | Reads a UInt's live u32 (entry 0x28 bytes, +0x1c) by hash from K=0x788, UIntArray fallback; ignores the ring | read |
| `f_83781680` | `GameDataMgr_GetKey64(mgr, out*, key)` | Binary search (ascending, unsigned) of the 16-byte records at mgr+0xc60 (count mgr+0xc58); stores the u8 live value (+0xc), returns 1 if found | read |
| `f_80183d20` | `GameDataMgr_GetIntQueued(mgr, out*, hash)` | Int read that first scans the pending ring newest-to-oldest (assign = value, add = accumulate) and then the table; the only queue-aware getter found | read |
| `f_805a1170` | `GameDataMgr_GetStructBool(mgr, out*, handle, memberHash)` | Reads one Bool member of a game-data struct by its member hash (the plain hash of the member name, not the flat `Struct.member` hash): finds the member through the handle's table (`handle+0`: table `+8`, size `+20`, as in `f_809d39e0`), which gives the member's flat hash, copies that Bool's live value byte (entry `+22`) to `*out` and returns 1; a member not found tail-calls `f_805a12c0` with 0; a handle whose byte `+12` has bit 0 set is handed to `f_837645e0` first (not read). The played flags' struct is read this way | read |
| `f_80403cc0` | `StoryFlagTable_FillBits(group, bitset*)` | Walks one of 5 groups of 47 story-progress flag hashes (a rodata table of 235 at `0x83f2a9f8`; `group` 0 to 4) and sets bit *i* of a bitset of 64-bit words for the flag at table index *i* when it is set; three entries are read by rules of their own (through `f_804029e0`). Caller `f_805996e0` packs flag groups into one record | read |

### The applier and its module

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_80bb9980` | `GameDataMgr_ApplyQueued(mgr)` | Per frame: for containers t0..t31 then the key container (then other kinds) walks each ring from slot 0 to the first empty hash, assigns/adds, writes live + saved + changed + file mask + change ring, clears slots, and exchanges the ring word to {taken 0, finished kept, round+1 (15 wraps to 0)}. The Int branch assigns `entry+28` and, unless the manager word at `+3340` is set, `entry+32`; a second pass at the head of each container resets changed entries whose mask (`entry+8`, the entry's file mask) intersects the manager's mask (`+3256`) to their default | read |
| `f_80bc24b0` | `KeyContainer_Apply(container, resetMask, mode)` | Optional reset of live-1 keys of the files in resetMask (mgr+0xcb8), then drains the key ring: sets live +0xc, saved bits in flags +0xe when file index >= 0, ORs the record mask into container+0x50, clears slots to {0, 0xffffffff}, exchanges the word | read |
| `f_83b700a0` | `GameDataModule_Calc(module, frame)` | Slot 2 of the GameData module vtable 0x84c84158 (no direct callers): locks the mutex at module+0x80 (`nn::os::LockMutex`), runs `f_80bb9980([0x84ea42a8])`, unlocks. It is run by the generic module calc job inside the ModuleSystem's job graph, once a frame ([jobs.md](jobs.md)), so not by the present thread; this function itself does not show the frequency or the thread | read |
| `f_83b70100` | `GameDataModule_Name` | Slot 25 of 0x84c84158: returns "GameData" (0x83de1161) | read |

### Making the manager and its capacities

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_8121cf90` | `GameDataMgr_Create` | Makes the 0xd38-byte manager (heap "GameDataMgr") and stores it in the holder 0x84ea42a8; constructor `f_8121d010` | read |
| `f_80e1f1c0` | `GameDataMgr_LoadAllTypes` | Calls each type's loader with its ring capacity from the 300-byte parameter block | read |
| `f_805d18f0` | `IntContainer_Load` | Reads the Int entries and ends in the container's reserve (vtable slot 2) with (heap, multiplier, ringCap, changeCap) | read |
| `f_8119b190` | `IntContainer_Reserve(container, heap, mult, ringCap, changeCap)` | Counter 0; ring of 12-byte slots (cap at +0x28, pointer +0x30) and change ring of u32s; negative cap = entries x mult, 0 frees | read |

### The ChallengeMgr (quest steps)

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_82d154a0` | `ChallengeMgr_RequestStep(mgr, challenge, step, flagA, flagB, force)` | Writes the asked step to entry +0xa4 and flags (+0x16: bit 1, bit 3 if flagA is 0, 0x400); does not write the current step +0x10; refuses when the step is at one of two terminal hashes unless forced | read |
| `f_82d15270` | `ChallengeMgr_FindEntry(mgr, &entry, hash)` | Searches three arrays of 0x160-byte entries (count +0x40/+0x50/+0x60, ptr +0x48/+0x58/+0x68) for hash at entry+8 | read |
| `f_82d12910` | `ChallengeEntry_SetCurrentStep(entry, step, f2, f3, f4)` | Writes the entry's current step (+0x10) and its flag word (+0x16); the terminal hash 0x57b849f0 takes a different branch (sets 0x4). The direct writer of the field the Kakariko gate reads; not read to the end | guess |
| `f_8320fb60` | `TriggerChallengeSetStep_Calc` | Slot 40 of the Logic node TriggerChallengeSetStep: looks up the challenge by the node's hash (+0x30), hashes the step name string (+0x50), calls RequestStep (0,0,0) unless the step is at a terminal hash | read |
| `f_828de1a0` | `OneShotChallengeSetStep_Calc` | Slot 39 of the AI node OneShotChallengeSetStep, calling RequestStep (not read in detail) | guess |

## Known values

| Hash | Type | What it is | Sure |
|---|---|---|---|
| `0x1a49c4f6` | | `SelectedCaptionIndex` | tested |
| `0xef2b60c2` | Bool | `Sequence_IsLoadingBanc`: a map is loading | tested |
| `0xcea220d3` | Bool | `Sequence_IsChildhood`: Link is a child | tested |
| `0xa2995097` | Int | The save list's last picked index | tested |
| `0x46926d32` | Struct | CaptionData; its field `0xd13d898b` is the picked slot | read |
| `0x605e5df8` | Bool | `IsLastSelectedMQMode` (murmur3 checked): Master Quest mode. In `account.sav`; restored at boot and cleared when the add-on is not owned ([master-quest.md](master-quest.md)) | tested |
| `0x5526db84` | Bool | `IsGameClearAtLeastOnce`, in `account.sav`; set with `IsGameClear` when the game is cleared (`f_83051aa0`) | tested |
| `0xb4962fee` | Bool | `IsGameClear` | tested |
| `0x8b95f6eb` | Bool | `IsClear`, a field of CaptionData | tested |
| `0xfb4b52f6` | Struct | `DefeatedEnemyNum`; its fields include `Enemy_DungeonBoss_Ganon` (0x2b9afb24) and `Enemy_DungeonBoss_Ganondorf` (0x367c8cc6), also fields of struct 0x42b90553 (name not found) | tested |
| `0x58131bc2` | Struct | `DebugParam`, not saved (SaveFileIndex −1). Fields found: `IsEnterMQScene` (0x3c3171e5; the full name `DebugParam.IsEnterMQScene` is 0x11b16e68), `IsSetChildhoodManually` (0x078ef520), IsSkipForceResetGameData, IsGameDataAllResetOnSceneDestroy, IsOverturnTerrainSetupAndLoadBanc, IsRequestedResetGimmick, IsOverrideTraversePos, IsKeepLoading | tested |
| `0xdd80b066` | Struct | `AutogenGameDataLogicNode` (murmur3 checked): 191 members in the game's list, 190 of them Bools saved in `progress.sav` (reset type 8, file 0). The list gives its members by hash only: the 15 looked at (room and dungeon state, for example a refill's respawn marker in a Bottom of the Well room) have no name in the game's data | read |
| `0xf5a32cdc` | Struct | `DungeonInfo` (murmur3 checked): the per-dungeon values. Members: the Bools `IsGetMap` (0x58aeb8fb), `IsGetCompass` (0xc7692e3f) and `IsGetBossKey` (0x5fb83617), which the HUD's getters read (`f_80ec0210`, `f_80eaa260`, `f_80ec0350`, [menus.md](menus.md)), and `SmallKeyNum` (0x1af87831), the small key count. The hashes were computed from the names, not seen in a run | read |
| `0xbe9f04bd` | | `Account`: GameDataList's SaveTypeHash for `account.sav` (`Option` is 0xa60ba395, `Caption` 0x26f3523b, and `Game` 0xa3db7114 is `progress.sav`'s: each is the murmur3 of that word) | tested |

## Data

| Address | Name | What it is | Sure |
|---|---|---|---|
| `0x84ea42a8` | `g_GameDataBlackboard` | The game-data manager as the save code loads it (`[0x84ea42a8]`): the file list, CaptionData | read |
| `0x84c9e180` | `g_GameDataMgrHolder` | The game-data manager as ReserveBancChange's readers load it (`[[0x84c9e180]]`); the debug tools read and write flags through it. Its static value is `0x84ea42a8`, so it is the same manager as `[0x84ea42a8]` | tested |

## Structures

### The game-data manager (0xd38 bytes, `[0x84ea42a8]`)

Made by `f_8121cf90` (heap "GameDataMgr"). Typed containers sit 0x60 bytes apart from `mgr+0x08`. **read**

| Offset | Field | Sure |
|---|---|---|
| `+0x008` | Bool container (type 0); BoolArray `+0x068` (1), Int `+0x0c8` (2), IntArray `+0x128` (3), Float `+0x188` (4), FloatArray `+0x1e8` (5), Enum `+0x248` (6), EnumArray `+0x2a8` (7), String64 `+0x608` (16), UInt `+0x788` (20), UIntArray `+0x7e8` (21): the types seen | read |
| `+0xc58` | The 64-bit key container (below) | read |
| `+0xca8` | The key container's dirty save-file mask | read |
| `+0xcb8` | A file mask: when non-zero the key applier resets the live keys of those files, and the applier makes a mask pass over the 128-byte records at `+0xcc8` (count `+0xcc0`); the records are the save files' own, one per file index (the file's buffers and the result of its load, [save-format.md](save-format.md)); what the mask does is not determined | read |
| `+0xd0c` | When non-zero the applier marks an entry dirty instead of copying its saved value; meaning not determined | read |
| `+0xd10` | A byte; when 1 the applier first makes a virtual call (slot `+0x48`) on the object at `+0xce0`; meaning not determined | read |

### A typed container (0x60 bytes; offsets from the container's base `K`)

| Offset | Field | Sure |
|---|---|---|
| `K+0x08` | The number of entries | read |
| `K+0x10` | The entries (Bool 0x18 bytes, UInt 0x28, Enum 0x38) | read |
| `K+0x18` | The hash table: 8-byte `{hash, index}` | read |
| `K+0x24` | The hash table's capacity | read |
| `K+0x28` | The ring's capacity (u32) | read |
| `K+0x30` | The ring's slots (Bool and Enum 8 bytes, Int, UInt and Float 12) | read |
| `K+0x38` | The ring word: bits 0 to 19 slots taken, 20 to 27 finished, 28 to 31 the round (0 to 15) | read |
| `K+0x40` | The change ring: u32 hashes (pointer `+0x40`, capacity `+0x48`, head `+0x4c`, count `+0x50`) | read |
| `K+0x58` | The dirty save-file mask (u32) | read |
| `K+0x5c` | The dirty byte | read |

An entry (the live value of a Bool at `+0x16` with its saved copy at `+0x17`; the others keep the value at `+0x1c` and the saved copy at `+0x20`): `+0x08` the entry's save-file mask, `+0x0c` the changed byte, `+0x10` its flag word (bit 31: no saved copy is written), `+0x14` 0 after a saved copy is written and 1 when it is not (and the container's dirty byte is then set). A ring slot is `{value, hash, mode}`, mode 0 assign and 1 add (Int, UInt; Float is left 0); Bool and Enum slots have no mode.

### The key container (`mgr+0xc58`)

| Offset | Field | Sure |
|---|---|---|
| `+0x00` | The number of records | read |
| `+0x08` | The records, sorted ascending, compared unsigned: 16 bytes `{u64 key, u32 file mask +8, u8 live +0xc, s8 file index +0xd, u8 flags +0xe}` | read |
| `+0x10` | The ring's capacity | read |
| `+0x18` | The ring's slots: 8 bytes `{u8 value, u32 record index}`, `0xffffffff` when empty | read |
| `+0x20` | The ring word, as in a typed container | read |
| `+0x50` | The dirty save-file mask | read |

## The save files

Each profile folder holds `account.sav`, `option.sav` and `slot_00 … slot_NN` with `progress.sav` and `caption.sav` in each
(see `docs/saves.md`). The files are flat lists of values keyed by hash, in the same family as Tears of the
Kingdom's saves. Their bytes, a table of every type of value and how a flag is found in a file are in
[save-format.md](save-format.md); in short each file is:

- A header: `04 03 02 01`, then the flag-list revision (`0x002d80eb`, 2,982,123) and the **offset where the table ends and the
  data section begins** (the third word is not the file's size: it equals the size only in `account.sav`, which has no data
  section), then zeros to `0x28`.
- A table of 8-byte entries in 32 groups: a u32 hash followed by its u32 value for the simple types (for the others, the offset
  of the bytes in the data section), each group closed by a `{0, k}` marker, and a last entry holding the file kind's hash.
- A data section for the other types and, in `progress.sav`, a run of 64-bit keys (the `Bool64bitKey` flags that are true).

**tested** (account.sav here; the others on 144 files in [save-format.md](save-format.md))

### account.sav (320 bytes)

GameDataList declares only two values for it (`SaveFileIndex` 3), both Bool, both false by default:

| Offset | Hash | Value in our saves |
|---|---|---|
| `0x28` | `0x605e5df8` | 0 |
| `0x30` | `0x5526db84` | 0 |

Then the table's 32 group markers `{0, k}` for k = 1 … 32, one per group, all empty here but group 1, which holds the two flags
(every file has the same 32 markers). The file ends with `0xbe9f04bd` followed by 0: `Account`, the file's SaveTypeHash in
GameDataList (murmur3 checked: it is the hash of that word), not a value. The 2 flags, the 32 markers and that last entry are
35 entries of 8 bytes after the header's 40, which makes the 320 bytes. **tested**

**The two bools are `IsLastSelectedMQMode` (0x605e5df8) and `IsGameClearAtLeastOnce` (0x5526db84)** (murmur3 checked against
names from the game's data). Setting either or both to 1 in a test copy changed nothing on the title screen, and no Master
Quest option appeared. **tested** That fits the code: `SeqOneShotSetMQMode` clears `IsLastSelectedMQMode` when the add-on is
not owned ([master-quest.md](master-quest.md)), and `IsGameClearAtLeastOnce` is set at the game's end. **read**


## Notes

- More known hashes: `OptionData` 0x834d9d9e, `VoiceLanguage` 0x74b1edd9, `OptionData.VoiceLanguage` 0xa2dcdc9d (the voice language option, default Japanese: [audio.md](audio.md)); `f_809d3eb0` and `f_809d3ba0` are used there as a find-struct / set-enum-field pair. **read**

### How a set reaches a value

A setter does not write the value. It looks the hash up (to see that the value exists), takes a slot on its container's ring with a compare-and-swap on the ring word, writes `{value, hash, mode}` into it and finishes with a second compare-and-swap. A full ring (slots taken at capacity), or a round that changed between the two steps, ends the game (`f_8351c280`). Only the applier `f_80bb9980` writes entries. **read**

- **The applier** is run once a frame by the GameData module's calc (`f_83b700a0`, slot 2 of the module vtable `0x84c84158`, under a mutex at `module+0x80`) inside the ModuleSystem's job graph. That is whichever pool thread claims the job (the main thread while it joins the module phase, or a ModuleSystem worker), never the present thread. It walks the containers of type 0 to 31 in order, then the key container, then the other kinds. For each container it reads the ring word once, walks the slots from 0 up to the first slot whose hash is 0, applies each (an assign that changes nothing is skipped), clears it, and then **exchanges the ring word without a compare** for `{taken 0, finished as it was read, round + 1}` (the round is 4 bits: 15 goes to 0). **read**
- **A changed entry** gets its live value, its saved copy (unless the entry's flag word has bit 31 or the manager's `+0xd0c` is non-zero: then the entry's `+0x14` is 1 and the container's dirty byte is set), the changed byte, its file mask ORed into the container's dirty mask, and its hash appended to the container's change ring while that has room. **read**
- **The setters take no lock.** A set from another thread (the port's progress sync sets flags from the present thread: `host/oot_coop.c`) can straddle the applier's exchange: a slot taken before it and finished after it differs in round and ends the game, and a slot taken but not yet filled (hash still 0) ends the scan and is left behind. Whether the overlap can happen in a real run is **not shown either way**. Safe places for a set from outside: on the applier's own thread just before it runs, or on the main thread outside the module phase. **read**
- **Getters** read the live value and never the ring; the exception is `f_80183d20`, which walks the pending Int ring newest to oldest first. A hash that is not in a typed container's table falls through to the matching Array container: the element's own virtual call (vtable `+0x20`) is made, and for a getter a result of 1 or more reads the array's first element, for a setter it queues the write on the Array container's own ring (`f_8378a590` for IntArray, `f_8378a0b0` for BoolArray); a hash in neither table is ignored without a message. Read for Int and Bool; the Enum, Float and UInt setters have the same shape and were not followed to that point. **read**
- **Modes.** The Int and UInt applier treats a slot's third word as 0 assign, 1 add (a signed delta with an overflow guard for Int; for UInt an overflow is dropped). `f_8059af30` writes mode 1, so it adds: the assigning UInt setter is `f_8059bcc0`. Nothing found in the port's code calls either. **read**
- **`PlayerStatus.MP` is the game's to write.** Every frame, after Link's update and before the applier runs, the game queues `PlayerStatus.MP` = the value it holds and `PlayerStatus.MPEconomy` (0x3afa3349) = 0 on the Int ring, behind any slot queued earlier that frame; the applier takes slots in order, so a set of MP from outside (from the present thread or the game thread, through `f_80183b70` or `f_809d39e0`) is replaced in the same pass. The held value changes through the game's own pickup (`f_8112d570`, about a frame after its writes), not through the flag. `MPEconomy` is not an accumulator the game turns into MP: an add to it (`f_80fe42d0`) from either thread is undone by the game's own assign of 0 behind it. The held magic is clamped to the size: setting `PlayerStatus.MPMax` to 0 by flag took MP to 0 within ten presents, while setting it to 240 or 480 left MP where it was. Seen in a game with a debugger on the applier; which function queues the per-frame write was not found. **tested**
- **`[[0x84c9e180]]` and `[0x84ea42a8]` are the same manager:** the holder's static value is `0x84ea42a8`. `SaveCard_FillFromRecord` (`f_833ec8f0`) passes `[[0x84c9e180]]` as the first argument of `f_80183b70`, writing a save slot's date numbers as Int flags that the card's text reads ([save-list.md](save-list.md)). **read**

### Ring capacities

The capacity of each ring is data, not code: the module's setup (`f_83b6f570`, slot 7) makes the manager (`f_8121cf90`), `f_80e1f010` copies a 300-byte parameter block from the module's setup information, and `f_80e1f1c0` gives each type's loader the ring capacity `block[4*t]` and the change-ring capacity `block[132+4*t]` (only when the byte `block[264+t]` is 1, else 0). The loaders end in the container's reserve (vtable slot 2; Bool `f_811f41b0`, Int `f_8119b190`, BoolArray `f_81213630`), where a positive capacity is that many slots, a negative one is the entry count times a multiplier and 0 frees the ring. The default for an unset type is all ones (negative), so a type the setup information does not mention gets entries times the multiplier. The 512 of the Int ring and the 96 of the String64 ring are therefore in the setup information; where that is filled was not found. **read**

### The ChallengeMgr

`0x84e49950` holds the manager's pointer (the GOT cell `0x84c9f9f0` holds that address). The manager keeps three arrays of 0x160-byte challenge entries (count and pointer pairs at `+0x40/+0x48`, `+0x50/+0x58`, `+0x60/+0x68`; the entry's hash is at `+8`). A step is asked for, not set: `f_82d154a0` returns 0 for an unknown challenge, returns 0 when the entry's current step (`+0x10`) is one of two terminal hashes (`0x4c0a63f4`, `0x57b849f0`) unless forced, returns 1 when the step is already the asked one, and otherwise writes the asked step to `+0xa4` and sets flag bits in the u16 at `+0x16` (bit 1, bit 3 when flag A is 0, then `0x400`); flag B also marks the child records of a sub-object. The current step `+0x10` changes later, in the manager's own update, through `f_82d12910` (reached from `f_82d113a0`, called from `f_82d10eb0` and `f_82d11830`). Callers: the nodes `TriggerChallengeSetStep` (`f_8320fb60`) and `OneShotChallengeSetStep` (`f_828de1a0`), and a scripted call (`f_832cf0d0`) with a fixed challenge `0x01e5c1d7` and step `0xd2f8add5` when a flag holds. **read**

## Open questions

- What `f_83b700a0` runs on exactly: which stage of the module graph is the GameData calc (and so whether an actor-stage setter can overlap it). The module vtable has no stage slot; the graph builders (`f_83b797e0`, `f_80b222e0`, `f_80b21f90`) add module calcs by index through `f_80b21bf0` and the registration order was not found. One observation: break on `f_83b700a0`, log the guest thread's name and the order against the actor update (`f_82c3fab0`) in the same frame; expected a ModuleSystem worker or the main thread, once a frame.
- Where the ring capacities come from (Int 512, String64 96): read the u32 at `K+0x28` of each container after setup (Bool `mgr+0x30`, Int `+0xf0`, Float `+0x1b0`, Enum `+0x270`, UInt `+0x7b0`, String64 `+0x630`); expected to equal the setup block.
- `f_8059af30` adds and `f_8059bcc0` assigns: call each once on a UInt holding 2 with the value 3 and read the entry's `+0x1c` after the next applier run; expected 5 and 3.
- What `mgr+0xd0c`, `+0xcb8` and the object at `+0xce0` (called when byte `+0xd10` is 1) do; the Int and Float add pushers (mode 1), the String64 ring's pusher and slot size (the kit assumes 12), and the container kinds the applier handles beyond the typed ones (a flag-driven loop over the 128-byte records at `+0xcc8`; struct, vector, BoolExp). The applier was read in full for Bool and Int and in part for the other typed containers, which are taken to follow the same walk.
- The ChallengeMgr: that its update turns `+0xa4` into `+0x10` through `f_82d12910` (the read of `+0xa4` was not found); the two terminal step hashes' names; `f_828de1a0`'s argument handling. One observation: read entry `+0x10` and `+0xa4` before and after the next frame's update following one `f_82d154a0` call; expected `+0xa4` at once, `+0x10` later.
