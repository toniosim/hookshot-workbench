# Save files, slots and captions

Where a save goes: the files and their slots, the worker that reads and writes them, and the caption manager that holds what
the save list shows of each slot (place, date, screenshot, hearts, medallions). Looked at for the save slots work (November
2026).

**LS code:** `host/nn_fs.c` (the `save:` mount)
**See also:** [save-list.md](save-list.md), [game-data.md](game-data.md) (what declares the values in the files),
[save-format.md](save-format.md) (the files' bytes), [master-quest.md](master-quest.md) (its slots), `docs/saves.md` (where LS keeps saves)

## The caption manager

A singleton (`[0x84e98e38]`) holding each slot's caption.

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_80ee9370` | `CaptionMgr_Create` | Makes the manager (0xb8 bytes) | read |
| `f_80ee8d00` | `CaptionMgr_Construct` | Constructs it: two arrays `{num, max, ptrs}` of **6**, inline (see [Structures](#structures)) | read |
| `f_80ee8bf0` | `CaptionArray_Init(arr, 6, buffer)` | Sets an array's buffer and capacity | read |
| `f_80bd00c0` | `CaptionMgr_MakeRecords` | Makes the records (0x5a0 bytes each), up to each array's capacity | read |
| `f_80bcff10` | `CaptionRecord_Init(rec, slot, mq)` | Sets `rec+4` = slot and `rec+1434` = Master Quest | read |
| `f_833cd490` | `CaptionMgr_Record(mgr, &rec, i)` | The record of slot `i`. Fails unless the manager is ready (`+140 == 4`), every record is loaded (state 5) and `i < num` | tested |
| `f_833cd530` | `CaptionMgr_RecordAt(mgr, &rec, i, mq)` | Like `CaptionMgr_Record`, but the array is chosen by bit 0 of the fourth argument (1: the Master Quest array) instead of `+145`. Same checks (ready, every record loaded, `i < num`); answers 1 and the record, else 0 | read |
| `f_80505420` | `CaptionMgr_LoadStep` | The manager's load state machine, on `+140`: 0 starts (to 1) when bit 0 of `+141` is set; 1 steps every record by its own state byte (`+0`: 0 asks for its file with `f_80cdc350`, 1 `f_8050a190`, 3 `f_80bce850`, 4 `f_809e5320`; 5 is loaded) and, once all are loaded, sets `+142` (and `+143` for a usable Master Quest record) and goes to 2; 2 sorts both arrays (`f_80bce520`, comparator `[0x84ca90a0]`), clears bit 0 of `+141` and goes to 4 (ready); 3 tail-calls `f_809e5210`; 4 does the per-frame record work (about 5,000 lifted lines, not read) | read |
| `f_80cdc350` | `CaptionRecord_RequestFile(rec)` | Asks for a record's caption file: finds the request object through the game-data holder's resource list, sets its slot to `rec+4` (plus 6 when `rec+1434`, Master Quest) and sets the record's state byte (`+0`) to 1 (requested) | read |
| `f_833cd5d0` | `CaptionMgr_LatestIndex` | The latest save's slot: the cached `+136` when it is not negative; otherwise the slot (`+4`) of the first record of the current array (`+145`; `f_80505420` sorts the arrays by date), and only when that is negative does it copy the record pointers into a local array of **6** (`f_833cd680`), sort it (`f_80bce520`) and answer the first record's slot if its usable bit (`+640` bit 0) is set, else -1 | read |
| `f_833cd680` | `CaptionArray_CopyTo(dst, src)` | Not a second latest index: makes `dst` an array of capacity **6** (`f_80ee8bf0`, buffer at `dst+16`) and copies up to 6 of `src`'s record pointers into it (`memcpy`). `f_833cd5d0` uses it for its local copy | read |

## Save files and slots

The file names are not in the code: they come from the game data's `SaveDirectory` ([game-data.md](game-data.md)):
`slot_%02d/progress.sav`, `option.sav`, `slot_%02d/caption.sav`, `account.sav`. What is inside them, byte by byte: [save-format.md](save-format.md).

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_80e00260` | `SaveWorker_Run` | The save worker's message handler: the code in the third argument picks the command: 'read', 'size', 'writ' (write), 'cmit' (commit; the code spells "cmit"), and also 'copy' and 'delt' (delete), which tail-call `f_83761da0` and `f_83761e30` | read |
| `f_806a3aa0` | `SaveFile_Write` | Writes a file: the name formatted with the slot (`f_80062b70`) and posted to the worker | read |
| `f_83051c60` | `SaveFile_Read` | A file request's state machine (state at `+8`, 0 to 8): 0 picks the entry from the flags at `+312`; 1 formats the name with the slot (`f_80062b70`) and posts 'size' to the worker; 2 takes the size and allocates the buffer (`+304`), or goes to 8; 3 posts 'read'; 4 to 6 wait for the worker, store the buffer in the file entry (`+104`) and mark it loaded (entry flag byte `+120`, bit 1); 7 done, 8 failed | read |
| `f_811f4910` | `Save_SetSlot` | Sets which slot a save writes (Master Quest adds 6) | read |
| `f_830506a0` | `Save_ChooseSlot` | Picks the slot of an existing save, not a free one: needs the manager ready (`+140 == 4`) and every record loaded, collects the usable records (`+640` bit 0) of the current array (up to **6**) into a local list sorted by date (`f_80bce620`) and answers the slot (`+4`) of the first one that is not an Autosave (`+472` bit 0 clear), -1 when none; a later pass compares name strings (`+560`) and was not followed. The first free place of 0…5 is `f_83310630`. The caller was not read | read |
| `f_83310630` | `SeqQueryGameDataGetManualSaveIndex` | The manual save's index: needs the manager ready and every record loaded, collects the usable records of the current array (up to **6**) sorted by date, and ends by answering the first slot of 0…5 that no usable record has, -1 when all six are taken. An earlier part answers an existing record's own slot (not followed) | read |
| `f_832e1db0` | `SeqExecuteLoadSaveData` | Loads slot "Index" (Master Quest adds 6). No limit of 6: slot 7 opens `slot_07` | read |
| `f_80bc72d0` | `SaveRequest_Allowed(?, reason, mode, value)` | A check made before a save is requested: answers 1 to go on or 0 to refuse. Reads two game-data values (a bool by hash `0x7c138e1f`, and a value by hash `0x5e776346` that, when it already equals the fourth argument, makes it refuse), the object's flags (`+344` bits 2 and 3 refuse), and takes a different path for reason 1 or 3. Its caller `f_80bc7730` (reason, value; passes mode 0) queues the request only on 1, then stores the value in that game-data value; the map transition `f_80bc76b0` asks with reason 6 (from `0x80bc7710`). The mode argument is not read in the body. Hooked by LS #614's transition autosave switch (`hos_oot_trace_save`: it sets `x0` to 0 and returns before the body, so the caller does not queue; it logs under `HOS_OOT_TRACE_SAVES`) | guess |

## Data

| Address | Name | What it is | Sure |
|---|---|---|---|
| `0x84e98e38` | `g_CaptionMgr` | The caption manager's holder | tested |

## Structures

### The caption manager (0xb8 bytes)

| Offset | Field | Sure |
|---|---|---|
| `+8` | The normal array `{num, max, ptrs}` (its buffer at `+24`) | read |
| `+72` | The Master Quest array (its buffer at `+88`) | read |
| `+136` | The latest index | read |
| `+140` | The state (4: ready) | tested |
| `+142`, `+143` | Whether a save exists, and whether a Master Quest one does ([master-quest.md](master-quest.md)) | read |
| `+145` | Which array: normal or Master Quest. Set by `SeqOneShotSetMQMode` (`f_83305480`, [master-quest.md](master-quest.md)) | read |

### A caption record (0x5a0 bytes)

| Offset | Field | Sure |
|---|---|---|
| `+4` | The slot | read |
| `+240` | The screenshot (-1: none) | tested |
| `+448 … +468` | The date: six 32-bit values (`+448`, `+452`, `+456`, `+460`, `+464`, `+468`), compared in that order by the sort's comparator `f_80bce620` | read |
| `+472` | The Autosave flag | read |
| `+473` | Clear | read |
| `+480` | The place (`{char *, size}`) | read |
| `+640` | Flags (the bit with mask 1, bit 0: usable; `f_80bcff10` starts it at 0xfc) | tested |
| `+1384 … +1392` | Medallions | read |
| `+1408` | Health | read |
| `+1412` | The maximum | read |
| `+1432` | Extra hearts | read |
| `+1434` | Master Quest | read |

## Notes

- `f_832e1db0` is `SeqExecuteLoadSaveData`'s slot 29 (OnEnter), not an evaluate: Execute nodes have no slot 39 ([sequences.md](sequences.md)). **read**
- Six is everywhere: the caption arrays, the slot chooser (`f_830506a0`), the manual save index (`f_83310630`), the latest
  index's copy (`f_833cd5d0`) and the save list's length. Loading (`f_832e1db0`) has no such limit.
- LS's side is `host/nn_fs.c`: `MountSaveData` mounts `save:` on `<game>\user\save\<user id>`, once, at boot;
  `mount()` adds or replaces a mount's folder; `host_path()` turns `save:/slot_00/progress.sav` into the file on disk, one to
  one.

### Game Over and Try Again

No function of this path has a row yet; what is known comes from the names in the game's sequence and event-flow data, not from lifted code, and none of it was hooked or run.

- **The Retry graph.** Game Over's Try Again goes through the sequence graph `Sequence/Retry.module`: from its node names it loads the latest save's index and then runs `OnLoadGameSaveData` and `ChangeBanc`. **guess**
- **A node in two graphs.** `SeqExecuteAutoSaveMgrLastGameOverSave` is a node of both the Retry graph and the `EventToTitle` graph (`Sequence/EventToTitle.module`). **guess**
- **The Game Over event flow.** `DmF_SY_GameOver.bfevfl` has two entry points, Retry and Title, and a screen that checks the return to the title. **read** (from the flow file's names)
- **What a load opens.** In a trace of the game's file opens for the title's Continue, `save:/slot_NN/progress.sav` is opened twice before the state leaves the menu for loading. **tested** for Continue; whether Try Again opens the same file in the same way, and whether it avoids the title's own event flow (`TitleEvent.bfevfl`), was not seen.
