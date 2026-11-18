# Events and the world

How code asks the game to play an event (a scripted sequence such as a change of map), and how the world's clock is set.
Looked at for the debug tools' teleport and time of day.

**LS code:** `host/hos_main.c` (`oot_teleport`, `oot_event_arg`, `oot_set_time`)
**See also:** [game-data.md](game-data.md) (the flags the teleport checks first), [player.md](player.md)

## Requesting an event

A request is built in an EventRequestArg, which names the event and carries its arguments, then handed to the event manager.
The teleport asks for `Dm_SY_BancChangeGo` with the arguments NextBanc, NextStartPos, BootEventName and IsCheckAir, and Link
as its starter, as SeqOneShotRequestEvent and OneShotEventMemberRequestEventByEventName do.

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_80d99f10` | `EventRequestArg_Init(arg)` | Makes an empty EventRequestArg in place | tested |
| `f_829df380` | `QueryBancChangeEventRequestArg` | Fills an EventRequestArg's arguments for a change of map (the entries' layout below). A query node (class `QueryBancChangeEventRequestArg`, vtable `0x84a8e1a8`, calc in slot 39) that never sends: another node sends the request. Builds the next map's name, NextBanc, as described in [Notes](#notes) under *The next map's name*: the base name by Link's age, "_MQ" in Master Quest mode, "_Alternative" by a game-data bool | read |
| `f_802dc440` | `ActorLink_Set(link, actor, 0)` | Points an actor link at an actor (the request's starter at `arg+0x1950`) | tested |
| `f_80d9a820` | `EventMgr_Request(events, arg)` | Asks the event manager to play the event the arg describes; the result is in `x0`. The event reads its string arguments after this returns, so they must stay in memory | tested |
| `f_8022b6f0` | `ActorLink_Release(link)` | Releases an actor link. After a request, SeqOneShotRequestEvent stores `0x84994b20` in each of the arg's two links and releases them | tested |
| `f_83b5bfb0` | `EventPlayer_StartTimeline(player, &namePtr, mode, params, …)` | The general timeline starter (it was listed here as the opening's, and as starting its two movies: it is not specific to the opening). Finds the entry by name (`f_83b5bf30`; no entry: returns with no effect), increments `player+0xf18` and swaps the found entry into that slot, making it the current entry. Then it moves the parameter block into the entry that was current *before* the advance (a list-node splice at `+0x128` and the fields at `+0x138`, `+0x140`, `+0x144`, `+0x148`, `+0x150`, `+0x151`; the source block is reset; skipped when `params` already equals that entry's `+0x128`), ORs flag bits into the new current entry's `+0x3b8` (`0x2_0000_0000` for mode 1, `0x4_0000_0000` for mode 2, nothing for other modes) and copies bit 28 of it from the previous entry. It may build the entry's argument buffer: only when three argument decoders succeed, it calls `f_83b5aac0`, which only allocates and initialises the 0xc98-byte buffer at `entry+0x3b0` when that is null (sixteen 0xc8-byte slots); the appending of one 0xc8-byte element when `entry+0x290` is below `+0x294` is in this function, starts the entry (`f_80c40370(entry, 0)`) and, on that path, sets `player+0xf25` to 1. Its only caller is `f_80eab5f0` (the EventTransition node, the case whose kind input is 1; return site `0x80eaba04`). Hooked by `patch_opening`: the opening's two timelines (`Dm_Kokiri_0000`, `Dm_Kokiri_0030`) are two uses of it, so while the opening is skipped (`hos_oot_opening`) the movies are not started | read |
| `f_80de6cb0` | `Opening_SkipQuery` | The opening's skip query. Hooked by `patch_opening`: answered yes while the opening is skipped | read |
| `f_8022e220` | `ActorLink_Resolve(link, 0, &pending, 1)` | Returns the actor an actor link refers to (checked against the actor manager's lists and the record's generation) and a pending flag byte; 0 when it is gone. Read in part (shape only) | read |
| `f_80813ea0` | `ActorLink_IsAlive(link)` | True when the actor link `{+8 holder pointer, +16 s32 generation}` (a generation of all ones is empty: false) names a live actor: the holder's generation (`[holder+72]`) equals the link's, the holder's actor (`[holder+64]`) is not null and its state word (`+44`) is not 7 to 11 (on its way out). It first compares through the actor manager's tables (`[[0x84c9d000+3136]]`) and otherwise takes the manager's lock (`nn::os::LockMutex`) and tests again. The co-op duel code uses it on the equipment slot's handle. Read in outline | guess |
| `f_809575f0` | `ActorLink_Get(link, a, b)` | Returns the actor an actor link names, by the same lookup as `f_80813ea0` (its fast path compares through the actor manager's tables, its slow path takes the lock). The co-op duel code calls it as `(link, 0, 1)`; what the two flags choose was not worked out. Read in outline | guess |

### The event manager and its players

The manager makes one **event player** per accepted request (0xf78 bytes); a player holds the event's timelines as **entries**, and the index of its current entry works as a stack top. See *The event manager* in Notes and the structures below.

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_80bec100` | `EventMgr_IsEventRunning(mgr, strict)` | Returns 1 when an event plays: `mgr+104` is not null; with `strict` (bit 0 of `x1`) also the current entry's playback object must be in its playing state (the entry at `[[player+0xeb8] + 8*u32[player+0xf18]]`, its index below the count `u32[player+0xeb0]`, the count above 0, the entry not null; then its playback object `[entry+0x220]` is asked through its vtable slot 8, whose default `f_82bfe3b0` tests that the state word `+0x2c` equals 3). 53 direct callers, almost all with strict 0: `SeqQueryIsEventRunning` publishes it with 0, as does the host's `events+104` test. Strict is used by the boomerang nodes `f_8285fab0` (`ExecuteSetBoomerangAngularVelocity`), `f_82865b10` (`ExecuteSetBoomerangLinearVelocityLockOn`) and `f_828612c0` (not named), which pass `1 & ~their last result` (strict only until they have seen an event run once) | read |
| `f_80bec0b0` | `EventMgr_CurrentTimelineName(mgr)` | Returns the string object (`+8` of the current entry: buffer pointer at +0, capacity at +8) of the current timeline, after writing a terminator at its last byte; a static empty string object (`0x849a1930`) when there is no player or entry | read |
| `f_80f0dd80` | `EventMgr_IsEventNamed(mgr, &namePtr, strict)` | 1 when the current player's own name (`[player+8]`) equals the C string at `[namePtr]`; with `strict` also requires the playing state like IsEventRunning. Callers: `SeqExecuteWaitEventEnd` (`f_83bd06e0`), `SeqExecuteWaitEventStart` (`f_83bd0960`), `f_802d57c0`, `f_828348d0`, `f_80f0dcf0` | read |
| `f_83b6c300` | `EventMgr_HasEventDefinition(mgr, &namePtr)` | 1 when the manager's table of event definitions (`mgr+608` count, `mgr+616` array of 0xa8-byte records, name at record+0) holds the name | read |
| `f_83b6b870` | `EventMgr_Calc(mgr, args)` | The manager's frame: stores the step (`args+4`) at `mgr+8`, walks the pending request records (list head `mgr+768`, count `+784`, free list `+792`), makes an event player (0xf78 bytes, `f_80c3f480`) for each accepted record, appends it to `mgr+632` (count `+624`) and, unless the record's byte `+181` bit 0 is set, makes it current (`mgr+104`). Read in outline: the control flow and stores; the constructor `f_80c3f480` was not read | read |
| `f_83b6c1d0` | `EventMgr_RemoveFinished(mgr)` | For each player with byte `+0xf24` equal 1 calls `f_83b5bb60`; a player that answers "finished" is removed from `mgr+632`, freed (0xf78), and `mgr+104` is cleared if it was current. Returns 1 when all answered finished or no player remained | read |
| `f_83b5bb60` | `EventPlayer_Update(player)` | One player's end/advance step: ends the current entry's timeline, then either chains to the entry named in `entry+0x98` (found by `f_83b5bf30`, swapped into the current place, started with `f_80c40370`) or pops the index; returns 1 when the event is finished (no array, index outside, nothing left). Counts ended entries at `+0xf1c`, adds the manager's step to the float at `+0xf20`, uses `+0xf25` as a busy byte. Read in outline: the chain and pop logic; the callee `f_80c40370` was not read | read |
| `f_83b5bf30` | `EventPlayer_FindEntry(player, &namePtr)` | Index of the entry whose name (`entry+8`) equals the string at `[namePtr]`, or -1 | read |

### Skipping an event

"Skip the playing event" flags the **current timeline** of the current player; it does not end the event, and the skip is taken by the timeline's own update on a later frame (who reads the flag was not found).

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_83b5af30` | `EventEntry_RequestSkip(entry)` | Calls slot 11 of `entry+0x220` (the playback object) when not null: asks the current timeline to end early (sets flag 0x20 at the object's `+0x28` when running, skippable and unlocked). Callers: the three force-skip nodes | read |
| `f_83b61630` | `TimelinePlayback_RequestSkip` | Slot 11 of the playback class: sets bit 5 of the flag word `+0x28` only if the object runs (slot 8), its definition byte `+955` has bit 1, and `f_83b60640` accepts `[obj+0x20]` (no skip lock) | read |
| `f_82bfe3b0` | `TimelinePlayback_IsRunning` | Default slot 8: the state word at `+0x2c` equals 3. The class's debug state names (developer table at `0x83f8f9f0`+offsets) read: 0 idle, 1 loading resources, 2 setup, 3 playing, 4 delete, 5 restore, 6 end, 7 continue | read |
| `f_832f1890` | `SeqOneShotEventRequestForceSkip_Calc` | The node's calc (slot 39, vtable `0x84bd0970`, name `f_832f19b0`): if the manager exists and `IsEventRunning(mgr,0)`, `EventEntry_RequestSkip` on the current entry of `[mgr+104]`; node done. Sibling: `SeqExecuteEventForceSkipAndWaitFinish` (vtable `0x84bc5c50`) | read |
| `f_832df870` | `SeqExecuteEventForceSkipAndWaitFinish_OnEnter` | Same skip as above, then stage 1 (`node+0x20` = 1) | read |
| `f_832df8e0` | `SeqExecuteEventForceSkipAndWaitFinish_OnUpdate` | Counts updates at `node+0x20`; every 60th re-issues the skip; done when no event runs (or `mgr+184` bit 14 is set) | read |

### Requesting an event: the requesters and the nodes

Every way to start an event ends in `f_80d9a820` (`EventMgr_Request`); see *Who can start an event* in Notes.

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_804ca890` | `EventPerformer_RequestByName(performer, &namePtr)` | Starts an event by name with the performer's actor (`[performer+16]`) as starter; no argument list; asks `f_80f81460`; returns bit 0 = accepted. 14 callers. It adds no argument list, so it cannot start `Dm_SY_BancChangeGo` (which needs NextBanc and the others): the host's own builder (`oot_teleport`) stays the way for that. Its advantage: the performer's state is set to 1. For Link the performer is `f_80c90560(link)` | read |
| `f_80f81460` | `EventPerformer_Request(performer, arg, direct)` | Wraps `EventMgr_Request`: returns 1 at once if the performer's state (`+0x28`) is 3 and the debug override is off; makes a copy of the request; when the starter link is empty it links the performer's actor; hands the copy to `f_80d9a820`; on acceptance stores state 1 at `performer+0x28`; releases the copy's links. Read in outline: the starter-validation branch (a lookup of the starter's actor id in a table at `[0x84c9d000+3136]`) was only skimmed. One probe run saw it accepted for `Dm_SY_Get` | read |
| `f_80bf1670` | `ActorEventRequest_SendKind(this, kind, actor)` | The event-request component's sender: name property chosen by kind from the offset table `0x83f17f58`, read with `f_80bf1240`; kinds other than 5 request through `f_804ca890` (performer `[[this+24]+0x270]+0x88`), kind 5 builds the arg itself and calls `f_80d9a820`; for kinds 2, 4, 7 also bit 0 of `this+0x168` and a distance-based wait at `+0x16c`. Returns 1 when the name was read and the request accepted. Callers `f_802d57c0` (BSA update's part), `f_82dd2d80`. Read in outline: the property reader and the distance arithmetic were skimmed | read |
| `f_802de720` | `ActorEventTrigger_Update(this, …)` | Per-frame update of a component with the owner at `+0x18`, flags at `+0x160`, a countdown at `+0xd8`: when it may, requests the talk/trigger event whose name it reads from one of two attached holders (`+0x98`, `+0xb0`) through `f_804ca890` with the performer at `[[owner+0x270]+0x88]`, then sets bit 0 of `+0x160`. The two call sites of `f_804ca890` in it (`f_802deedc`, `f_802df064` as places) are its only ones | read |
| `f_8281e410` | `ExecutePlayerReactionPreAbyss_OnUpdate` | The pit-fall reaction node's update (vtable `0x849e8258`, slot 39; name at slot 18): when requested, asks Link's performer (`f_80c90560`) for the event `DmF_SY_FallDown` through `f_804ca890` unless its state is already 3; otherwise tail-calls `f_8060d3d0` | read |
| `f_80c90560` | `Actor_GetPerformer(actor)` | `[[actor+0x270]+0x90]`, or 0: the event performer used for Link and by the Performer node. `f_80e77080` is the same for `+0x88` (the event-member performer used by the Member nodes and the sender) | read |
| `f_828f4fe0` | `OneShotEventPerformerRequestEventByEventName_Calc` | Node calc: performer from `f_80c90560`, the name from the node's input, `f_804ca890`; node done on acceptance, failed otherwise | read |
| `f_828f44f0` | `OneShotEventMemberRequestEventBase_Calc` | Builds an arg, lets the subclass fill it (vtable slot 40), asks `f_80f81460` with the member performer (`+0x88`), writes accepted to the node's output; `f_828f4c20` (ByEventName) calls it when its bool input is set | read |
| `f_83bdc4a0` | `SeqQueryIsEventRunning_Calc` | The calc of the query node `SeqQueryIsEventRunning` (listed in the catalogue of [sequences.md](sequences.md)): writes `IsEventRunning(mgr, 0)` to the node's output when the manager exists | read |

## The world's clock

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_834722d0` | `WorldMgr_SetTime(world, seconds)` | ExecuteWmSetTime's call: sets the world manager's time of day, in seconds since midnight. The world manager is `[[0x84c9e898]]`, and `world+0x510` must be set | tested |

## Data

| Address | Name | What it is | Sure |
|---|---|---|---|
| `0x84c9e090` | `g_EventMgrHolder` | The event manager, `[[0x84c9e090]]` (as SeqOneShotRequestEvent loads it) | tested |
| `0x84c9e898` | `g_WorldMgrHolder` | The world manager, `[[0x84c9e898]]` | tested |
| `0x84994b20` | `ActorLink_Empty` | What SeqOneShotRequestEvent stores in an actor link before releasing it (likely an empty link's vtable) | guess |
| `0x84eb4840` | `g_EventMgr` | The 8-byte variable that holds the event manager's pointer (0 in the image, filled at run time); the holder `0x84c9e090` holds this address, so `[[0x84c9e090]]` is the manager. Code that skips the holder loads it directly (`f_82f9e270`). Another project's offset `0x4e94840` is this variable | read |

## Structures

### The event manager

| Offset | Field | Sure |
|---|---|---|
| `+104` | Not 0 while an event plays (the Main sequence's "Event" test) | tested |
| `+8` | f32 the frame step (stored by `f_83b6b870`) | read |
| `+184` | u32 flags: bit 1 skips the pending-request pass, bit 9 is cleared when a new player becomes current, bit 14 is tested by the skip-and-wait node | read |
| `+608`, `+616` | u32 count and pointer of the event definition table: 0xa8-byte records, the name pointer at record `+0`, its capacity at `+8` | read |
| `+624`, `+628`, `+632` | u32 live player count, u32 capacity, pointer to the player array | read |
| `+768`, `+784`, `+792` | The list head of pending request records (a record's node at record `+0xeb0`: next, previous), its count, the free list | read |

### An event player (0xf78 bytes)

| Offset | Field | Sure |
|---|---|---|
| `+8`, `+16` | A name: buffer pointer and capacity. The event's own name: `f_80f0dd80` compares it with a given name and the two wait nodes (`SeqExecuteWaitEventStart`, `SeqExecuteWaitEventEnd`) use that, so it is the playing event's name; that it is the requested event's name and not a timeline's is an inference from those nodes | read |
| `+0xeb0` | u32 number of entries (0 at construction) | read |
| `+0xeb4` | u32 the array's capacity | read |
| `+0xeb8` | The array of entry pointers | read |
| `+0xf08` | The definition source (`[mgr+72]`, given to the constructor) | read |
| `+0xf18` | u32 index of the current entry | read |
| `+0xf1c` | u32 counter of ended entries | read |
| `+0xf20` | f32 time accumulated from the manager's step | read |
| `+0xf24` | u8: 1 while the manager processes the player | read |
| `+0xf25` | u8 busy or started guard | read |

### A timeline entry and its playback object

| Offset | Field | Sure |
|---|---|---|
| entry `+8`, `+16` | The timeline's name (pointer, capacity) | read |
| entry `+0x98`, `+0xa0` | The next entry's name (the chain) | read |
| entry `+0x218`, `+0x220` | Two sub-objects; the second is the playback object | read |
| entry `+0x3b8` | u64 flags (bits 6, 11, 12, 28, 33, 34 and 0x200 seen) | read |
| playback `+0x10` | The timeline definition (`+955` bit 1: skippable) | read |
| playback `+0x20` | The controller | read |
| playback `+0x28` | u32 flags: bit 0, bit 2, bit 5 skip requested | read |
| playback `+0x29` | u8 flags read by slots 9 and 10 | read |
| playback `+0x2c` | u32 state: 3 playing (the debug names: 0 idle, 1 loading resources, 2 set-up, 3 playing, 4 delete, 5 restore, 6 end, 7 continue); vtable slot 8 IsRunning, slot 11 RequestSkip | read |

### An EventRequestArg

| Offset | Field | Sure |
|---|---|---|
| `+0` | The arguments' capacity | tested |
| `+8` | The arguments: 200-byte entries | tested |
| `+16` | The number of arguments | tested |
| `+0x1950` | The starter actor's link | tested |
| `+0x1968` | Another actor link (released after the request) | tested |
| `+6800` | The event name's buffer | tested |
| `+6808` | Its capacity | tested |

### An event argument (200 bytes)

| Offset | Field | Sure |
|---|---|---|
| `+0` | The type: 1 a string pointer, 4 a bool | tested |
| `+8` | The name's buffer | tested |
| `+16` | Its capacity | tested |
| `+152` | The value (a string value is a pointer the request does not copy) | tested |

## Notes

### The event manager

- **`0x84eb4840` is not an object** but the 8-byte variable holding the manager's pointer (0 in the image), as `0x84e9eab0` holds the world manager's. The holder cell `0x84c9e090` holds its address. So `[[0x84c9e090]]` is the manager and `mgr+104` the current event player. **read**
- **The player.** `EventMgr_Calc` (`f_83b6b870`) makes one per accepted request, keeps them in a list at `mgr+632` (count `mgr+624`) and removes one when `f_83b5bb60` says it finished (`f_83b6c1d0`). `mgr+104` is set to the newest player when it is created (unless the request record's flag byte `+181` bit 0 is set) and cleared when that player is freed. An entry is one timeline (a cutscene part): it has a name (`entry+8`) and a playback object at `entry+0x220`. Starting a timeline (`f_83b5bfb0`) looks the entry up by name (`f_83b5bf30`), swaps it to index + 1 and makes that current; ending one (`f_83b5bb60`) chains to the entry named at `entry+0x98` or pops the index. **read**
- **Skipping.** `f_83b5af30(entry)` is a request: slot 11 of the playback object (both known vtables, `0x84b41610` and `0x84c82f20`, use `f_83b61630`; which one `entry+0x220` holds was not checked) sets bit 5 of the flag word at `+0x28` only if the object runs (slot 8), its definition byte `+955` has bit 1 ("skippable" is the reading of that bit) and the check `f_83b60640` on `[obj+0x20]` passes (slot 9 of that object returns an object whose byte `+422` is zero and signed byte `+421` is at most 0; that this means "unlocked" is a reading). The skip is taken by the timeline's own update later. The one-shot node `SeqOneShotEventRequestForceSkip` (vtable `0x84bd0970`) does it for the current entry of `[mgr+104]` when `IsEventRunning(mgr, 0)`; `SeqExecuteEventForceSkipAndWaitFinish` does it on enter, then on update waits until no event runs and repeats the skip every 60 updates (the compiler's modulo idiom), so a chain of timelines is skipped one after another. A host can do the same without a node: manager, `f_80bec100(mgr, 0)`, player `[mgr+104]`, entry = the array's element at the index, `f_83b5af30(entry)`; strict 1 skips only a timeline that is really playing. **read**
- **Who can start an event.** Every way ends in `f_80d9a820` (the choke point; tested): `SeqOneShotRequestEvent` (both copies `f_832fb1a0`, `f_83bd3cd0`), `SeqExecuteKeepRequestEvent` (`f_80d9a3f0`, `f_80d9a5a0`), `f_80f81460`, `f_80bf1670` (kind 5) and three unidentified internal callers (`f_8328bef0`, `f_832d0800`, `f_832a57b0`). **Usable from the host as is:** `f_804ca890` (starts an event by name with the performer's actor as the starter, no arguments; for Link `f_80c90560(link)` is `[[link+0x270]+0x90]`). **Needing a request already built:** `f_80f81460` (returns 1 at once when the performer's state `+0x28` is 3; fills the starter with the performer's actor when the argument names none; on acceptance stores state 1 at `performer+0x28`). **Needing a game object:** `f_80bf1670` takes the name from one of its name properties by kind (the offset table at `0x83f17f58`) into a 0x80-byte buffer, goes through `f_804ca890` with the performer `[[this+24]+0x270]+0x88` for kinds other than 5 and builds the argument itself for kind 5; the nodes `OneShotEventPerformerRequestEventByEventName` (`f_828f4fe0`, performer at `+0x90`) and the `OneShotEventMember…` family (`f_828f44f0`, `f_828f4c20`; performer at `+0x88`) do the same from graphs. `f_802de720` requests an actor's talk or trigger event every frame it may; `f_8281e410` (`ExecutePlayerReactionPreAbyss`) requests the fall event `DmF_SY_FallDown` through Link's performer unless it is already in state 3. **Only reporting or preparing:** `f_829df380`, `f_80c90560`, `f_80bec100`, `f_80bec0b0`, `f_80f0dd80`. **To observe the starts**, one wrap on `f_80d9a820` sees every request with its name at `arg+6800` and the accepted result in `x0`; `patch_opening` already patches its head, so the two hooks must coexist. The host's teleport builder (`f_80d99f10`, `f_80d9a820`, `f_802dc440`, `f_8022b6f0`) is the argument-carrying form of exactly this chain. **read**
- **The map change's arrival event.** The map-change request's `BootEventName`, `Dm_SY_BancChangeArrive`, plays after the new map and Link exist: 0.14 to 0.59 s after the first sample in the new map (the event flag at `[[0x84c9e090]]+104` true for 0.5 to 0.7 s); its start puts Link at the destination's start position (the field's entrance for `HyruleField_FrontOfLostWoodBridge`), and a placement made before it ends is undone. Seen in nine map changes and the two "Go to friend" arrivals of two games. **tested**
- The performer slots `+0x88` and `+0x90` of the component table are expected to be one class (both go to the same request code and hold the actor at `+0x10` and the state at `+0x28`); their vtables were not compared.

- `0x84c9e898` holds the address of the world manager's variable `0x84e9eab0`; `world+0x510` is its clock (`Clock_SetTime`, `f_80f0e640`). See [environment.md](environment.md). **read**

### The next map's name

How `f_829df380` builds NextBanc, in order. **read**

1. **The base name:** NextBancParamNameChild or NextBancParamNameAdult, by `Sequence_IsChildhood` (0xcea220d3), into its
   name buffer (`+6976`, its length `+6984`).
2. **No "_MQ" for these:** a name that contains "_Child" or "_Adult" (an inline substring search), or that is
   FinalBattleField, HyruleCastle or GanonCastle, goes on to step 4. Those are the overworld maps with an age variant and
   the three castle maps.
3. **"_MQ":** it looks `IsLastSelectedMQMode` (0x605e5df8) up in the game-data manager (`[[0x84c9e180]]`,
   [game-data.md](game-data.md)): first in the bool table (the hash index at `+32`, its size at `+44`; the entries at `+24`,
   0x18 bytes each, their count at `+16`; the value at `+22`), then in a second table (the index at `+128`, size `+140`;
   64-byte entries at `+120`, read through their vtable's `+32`). When the bool is 1 it appends "_MQ" (`0x83d0488a`, with
   `f_8572f020`); not found or 0, nothing.
4. **"_Alternative":** appended when a local flag is 1; the flag is a game-data bool named by the IsAlternativeGameDataBool
   argument (hashed with `f_801939e0`, read with `f_800b2720`). The two alternative maps are the burned Kakariko and the
   thawed Zora's Domain, with the bools `Sequence_IsAlternative_KakarikoAdult` and `Sequence_IsAlternative_ZoraDomainAdult`
   ([maps.md](maps.md), *Variant maps*).
5. **NextBanc** is the result. NextStartPos goes the same way, with "_Air" for NextStartPosAir (IsCheckAir).

Step 3 doesn't check a list of dungeons (unlike `QueryGameBancParamMQName`, [master-quest.md](master-quest.md)): in Master
Quest mode any next map without an age suffix, other than the three castle maps, gets "_MQ". Whether boss rooms or other
age-less maps are ever reached through this query was not checked. **read** (the code), open (the maps it is used for)

- The teleport waits while an event plays (`events+104`) and while a map loads (`Sequence_IsLoadingBanc`), and picks the
  child or adult map by `Sequence_IsChildhood` ([game-data.md](game-data.md#known-values)).


### The teleport's destinations

- **A list of the port's, not a table of the game's.** The destinations the debug tools offer are `oot_destinations` in `host/hos_main.c`: 31 pairs of a map (named for Link's age) and a start position, picked by index. No table of the game's entrances is documented on these pages; the arrival event puts Link at the destination's start position (*The map change's arrival event* above). **read**
- **Two destinations can share a map.** Hyrule Field and Lake Hylia are both `HyruleField_*` maps and differ only in the start position. Destination 7 is the Lake Hylia side (Link lands swimming); destination 3, the Market, and destination 0, Kokiri Forest, are dry. **tested** (a real game; a picture of the swimming arrival was looked at)
- **The age change** flips Link's age at once and reloads the current map as the other age through the same map-change event; the arrival is control in the other map. **tested**
- **After a map change** the first seconds are a fade from black: a picture taken at arrival can be black, and was lit once the tool waited 120 presents. The game saves a few seconds after a debug map change (its "Saving..." text shows), so the slot files hold the new place only after that. **tested**

## Open questions

- Skip a playing cutscene (a Navi talk or the Door of Time) with `f_83b5af30(entry)` from the game thread and read `[entry+0x220]+0x28` and `+0x2c` over the next ten frames: expected bit 0x20 set, then the state leaves 3 (to 6, the end state) within a few frames. Who reads bit 0x20 of the playback object's `+0x28` was not found (the base class's other slots are empty stubs; the derived classes' overrides were not enumerated).
- One accepted request through `f_804ca890` with Link's performer and a short event name, then a read of `[performer+0x28]`: expected 1.
- What `f_8328bef0` (from `f_8328b6e0`), `f_832d0800` (from `f_832d0ba0`) and `f_832a57b0` are: other callers of `f_80d9a820`.
- The names of the Sun's Song, bed and Door of Time events (they live in the flow files, not in the image; the image's strings hold only node, class and item names for them, `Dm_SY_Ocarina` being the only ocarina-related event name found). See [environment.md](environment.md), *What sets the time of day*.