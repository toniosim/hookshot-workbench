# Link: movement, health and items

Link's character controller and its speed, the write that takes his health, his movement update, and the pouch (the items he
carries). Looked at for the Debug tab's rows: movement speed, protected hearts, flight, and adding and removing items;
also for co-op's native attack observations, equipment display and pouch selection.

**LS code:** `nx2/oot_patches.py` (`patch_cct_speed`, `patch_life`, `patch_movement`,
`patch_flight_rotation`; and `patch_attacks`, on the co-op branches only), `host/hos_main.c` (`hos_oot_cct_speed`, the flight, the pouch calls),
`host/oot_coop_hits.c`, `host/oot_coop_players.c` (equipment), `host/oot_coop_kit.c` (capacity and selection)
**See also:** [camera.md](camera.md), [events.md](events.md) (the teleport), [game-data.md](game-data.md)

## Movement speed

A character controller's forward speed (`s0`) goes to `[controller+40]+472`, which the physics step moves the body by, with
its collisions.

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_809552f0` | `Player_Move(…, x1 = direction)` | The move Link's own walk, run and swim go through (the speed in metres a frame). It inlines the speed setter at two calls, each after it took the controller into `x0`. A climb up a ledge goes through it too, at some 55 m/s for a frame. Hooked by `patch_cct_speed` | tested |
| `f_80559df0` | `Cct_SetForwardSpeed(controller, s0 = speed)` | The controller's speed setter (its vtable +0x70), the speed in metres a second. Hooked by `patch_cct_speed` | tested |
| `f_80964bf0` | `CctComponent_SetForwardSpeed` | Takes the CCT component and inlines the setter (OneShotPhysicsCctSetForwardSpeedMpf and others). Hooked by `patch_cct_speed` | tested |

## Health

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_804bd8c0` | `LifeComponent_Step(life)` | One frame of one Life component. `x0` (`x19`) is the **Life component**, the object at `[actor+0x270]+0x2b8` whose `+0x18` is its actor (its only direct caller is `f_82c3d740`), not the actor. It zeroes `+0x1c20`, clears bit 12 of `+0x1d18`, adds the frame's damage terms into a signed total stored at `+0x1cb0` (`+0x1350` plus the hit amount `+0x228`, which another word replaces when bit 5 of the byte `+0x252` is set, plus a term from the request block at `+0x28` when its byte `+0x2c` is 1), compares the incoming hit (attacker qword `+0x240` against `+0x1b10`, hit id `+0x248` against `+0x1b18`, and two byte checks) to decide whether the weak actor handle at `+0x1b08` is released and set again, and copies the hit record `+0x250..+0x2d7` to `+0x1b20..` once a step. Unless bit 8 of `+0x1d18` is set it then takes the damage: new life = max(0, min(old - total, max)) by compare-and-swap into the life cell's value (`[+0x1c10]+8`, the maximum from `[+0x1c18]+8`, a missing maximum cell counting as 0), so a positive total lowers life and a negative one is clamped to 0 first. There are three compare-and-swap sites: the damage one; a heal by `+0x1c20` (the request's amount, run before the damage one) and, when life is 0 or below afterwards, one that heals by what `f_804bd6b0` returns (not hooked). Hooked by `patch_life` at the damage and the heal sites (the port's test counts two): with the hearts cheat on, a write that would lower the player's life keeps it. At the damage site `w9` holds the total (a negative one already clamped to 0), `w10` the old life and `x13` the address of the cell's value; the instruction that sums the terms, `0x804bdcb0`, is a place inside this function (there is no `f_804bdcb0`) | tested |
| `f_82e10fb0` | `LifeQuery_BelowTwo_Evaluate` | A query node's calc: false unless the node's mode word (`+0x38`) is 1; true when the life cell pointer (`+0x1c10` of the Life component, reached as `[[[node+0x18]+0x270]+0x2b8]`) is missing or the cell's value is below 2, as a signed compare (a missing component table or Life component gives false). Its only direct caller passes `[[actor+0x270]+472]` as the argument (a component whose `+0x18` is its actor), so the argument is that component, not a node. Quarter hearts and the query framing are the names' reading, not shown | read |
| `f_82e97da0` | `LifeQuery_LowForMax_Evaluate` | True when the life value is at or below a threshold that depends on the maximum: 4 while the maximum is under 21, 6 for 21 to 40, 8 for 41 to 60 and 10 above (a missing maximum cell gives 4; a missing life cell counts as life 0). It reads both cells (`[+0x1c10]+8`, `[+0x1c18]+8`). Its caller `f_80233970` passes `[[actor+0x270]+0x358]`, a component whose `+0x18` is its actor; there is no null check on the tables. That it is the low-health warning's condition (the maximum counted in quarter hearts) is a guess | read |
| `f_82a52460` | `LifeQuery_AnyCountPositive_Evaluate` | A query node's calc: writes `(s32 at +7280 > 0) or (s32 at +7224 > 0)` of the actor's Life component (the actor is `[[node+8]+8]+0x1f0`) to the node's output slot (`node+0x20`, notified when the value changes); with no Life component it sets bits 30 and 31 of the u32 at `node+0x18` and writes nothing. It only reads: that the two counts make the actor invulnerable is a reading of the counts, not shown by this function. `f_82e67dd0` turns the same two counts into the state word at `+0x1ca0` (2 when `+0x1c70 > 0`, else 1 when `+0x1c38 > 0`, else 0), which the life step reads to skip its damage swap, so a protection count is plausible there. The node class is `QueryIsInvincibleAny` (calc in slot 39 of vtable `0x84ac1a40`), which supports that reading. | read |
| `f_82a0c530` | `Query_GuardBit_Evaluate` | A query node's calc: sets its output slot (`node+0x20`) false, then takes the node's actor, its component at `[actor+0x270]+472` (no null check), asks `f_80813ea0` whether the handle at `[component+32]` is usable and `f_809575f0(handle, 0, 1)` for the actor it names, follows that actor's `[+0x270]+856` (`f_8084acc0`) and sets the output true when bit 4 of the byte at `+50` of that component is set. The second chain runs on the actor from the handle, not on the node's own actor. The node class is `QueryDynamicEquipmentIsPlayerGuardFront` (calc in slot 39 of vtable `0x84a9ee78`), so bit 4 is the guard-front flag. The `+472` component is not the equipment user (`f_80817690` reads that at table `+512`): it holds an actor handle at `+32`, here the actor whose player component (`+856`) is asked | read |

## Native attack observations

The rows retain **read** from the supported-build static investigation. Their observation points are in
`nx2/oot_patches.py`, `patch_attacks`, on the co-op branches (forge/main has no such patch, so these rows do not say
`Hooked by`), with the host-side interpretation in `host/oot_coop_hits.c`
at `2f01e1b4bdb6e1629c54a998f0403519fe4e5c74`. Observing setup, renewal or off does not establish a swing,
victim contact or actor ownership.

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_82ec53d0` | `SensorHit_SetupAttack` | Installs a prepared attack in a bounded sensor record and requests activation. A repeated setup may retain existing IDs; it is not proof of a new swing or victim contact. On the co-op branches `patch_attacks` observes it after the setup | read |
| `f_82ec6680` | `AttackRecord_RenewIds` | Explicitly renews the record's secondary filter ID and its already-present primary ID from the native counter. The co-op branches' `patch_attacks` observes the IDs here, not established actor ownership | read |
| `f_808f56f0` | `SensorHit_RequestOff` | Requests the selected sensor layer off through its physics body; completion is not solver-state readback, and missing bodies need not change state. Layer 18 takes another path: it only zeroes the word at `+420` of the object at `+136`. On the co-op branches `patch_attacks` observes it | read |

## Movement update and flight

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_82c415e0` | `Player_UpdateMovement` | The player actor's movement update (`x19` the actor, `x25` its matrix). Hooked by `patch_movement`: the host can lift the player (`hos_oot_lift_player`) before its branch on bit 1, and set the pose while flying (`hos_oot_flight_pose`) | tested |
| `f_806d2530` | `Controller_SetPosition(controller, &position)` | A character controller's position setter (slot 29, `+0xe8`, of the controller vtable `0x84c54f10`). `x0` is the controller, `x1` points at three floats (the new position). It copies the body's current rotation rows into a 3x4 matrix on its stack, writes the three floats into that matrix's translation column and calls the controller's vtable slot `+592` with `(controller, &matrix, &flag 1)`. Hooked by `patch_flight_rotation`: the hook runs just before that call with `x1` the local matrix, so while flying the host writes the flight's heading into the matrix first | tested |

## The pouch

The capacity and selected-equipment rows retain **read** from the supported-build static investigation;
their call sites are `kit_capacity` and `kit_equip` in `host/oot_coop_kit.c`
at `2f01e1b4bdb6e1629c54a998f0403519fe4e5c74`.

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_828d4a70` | `OneShotAddOrRemovePouchContent` | The event that adds or removes a pouch content by actor name (its parameters are read through pointers; the delta's sign picks add or remove). The status is the top bits of the result word. The event is asynchronous: a give from Link's update returns status 2 at the call whether or not the pickup will write anything (also for a single magic meter given with a size already set, which writes nothing), and the count the pouch getter `f_805b63e0` reads is unchanged at the call; the effect shows within ten presents, so the status is not a proof of the effect | tested |
| `f_82a3c260` | `QueryGetPouchContentNumByActorName` | The query of how many of a content the pouch holds, through `f_805b63e0` | read |
| `f_805b63e0` | `Pouch_Count(manager, &name, 0, 0)` | Counts one content | tested |
| `f_805b5cf0` | `Pouch_CapacityByActorName` | With the pouch manager and a pointer to an actor-name pointer, resolves the content's capacity. Non-count equipment can return a fixed one; stockable contents use their declared capacity source. Missing lookup paths return zero (`kit_capacity`) | read |
| `f_80a9acd0` | `Pouch_SelectEquipmentByActorName` | Resolves a named content's equipment category, queues its selected equipment name through game-data setters, and refreshes the pouch's equipment request state. Native give callers pass manager, name wrapper, policy 3 and flag 0; its answer is not proof that the live equipment actor finished appearing (`kit_equip`) | read |
| `f_8112d570` | `Pouch_AddByActorName(manager, &name, meta, quantity)` | The shared give-by-name routine: `x1` points at a word that points at the actor-name string, `w3` is the quantity. It can issue further gives itself, so one call is not always one item. For an item with an `ExpansionAbilityActor.MPMax` parameter it first reads `PlayerStatus.MPMax` (`f_805b60b0`); for the doubling kind (12) it always sets both `PlayerStatus.MPMax` and `PlayerStatus.MP` to 10 times the parameter (24 gives 240, 48 gives 480) through `f_809d39e0`, for the single meter only while MPMax is 0 or less, so a meter whose size a flag set first is never filled by this pickup. It then posts a record (`f_826df110`, key `{counter, 0x2f4d0000}`, value the new size) from pouch manager `+840..+852` under the mutex at `+0x3b70`. Seen in a game, given from Link's update: the single meter from size 0 made both 240, the doubling one made both 480 from 240 and from 0 (also with the item's count already 1), and the values stayed; the single meter with the size already 240 did nothing | read |
| `f_826df110` | `Event_PostWithKey(queue, key*, params*)` | Posts a keyed message under the mutex at its queue's `+112`; `f_8112d570` posts the magic meter's record with it. Not a store of MP | read |
| `f_8112d370` | `SeqOneShotPushToPouch` | Reads the name and the quantity through the node's tagged pointers at `+0x20` and `+0x30`, then calls `f_8112d570` | read |
| `f_80c8f590` | `OneShotPouchContentPushToPouchOwnInEvent` | A picked-up item's event: finds the owning actor's pouch-content component and calls `f_80c8f620` | read |
| `f_80c8f620` | `PouchContent_Push(component)` | Gives the component's owner by its actor name (the owner is `+0x18`, its name `+0x260`) through `f_8112d570`, quantity 1. The component's state word at `+96` (0, 1 or 2) picks the path; after the give it calls `f_8112d0b0` with the name. | read |
| `f_82b00750` | `Chest_FillGetRequest(node, request)` | Fills a chest's get-event request, the helper behind `QuerySetTreasureboxGetEventRequestArg`. The argument named `ContentName` carries the reward's actor name, set through `f_81003fe0` at two places. It picks what the chest asks for; the pouch write comes later, through the rows above. Seen in an earlier build's runs: the request's `ContentName` was logged | tested |
| `f_80d472f0` | `OneShotActorHolderTryRequestCreateActorWithActorFileName` | Creates a holder's content actor (a chest's shown item among others) by actor-file name; the name comes through the tagged pointer at the node's `+0x38`. For a chest, the file name it passes is what Link later holds up in the get scene, and the request's `ContentName` follows it: with the name swapped here Link held up the Boomerang (an earlier build, seen) | tested |
| `f_82971f50` | `Player_SyncEquipmentAndPouchNode` | The `OneShotSyncPlayerEquipmentAndPouch` node's calc: calls the item-system helper with mode 0 (`f_80f401b0` with flag 0, [below](#equipment-pieces-and-hand-state)) and marks the node complete. This is separate from choosing a pouch item's selected equipment | read |
| `f_81231c00` | `Pouch_SelectAssignedTool` | Writes an age-specific assigned-tool selection from the local tool catalog and starts its refresh/event work. Its native catalog concerns tools and traded items, not the sword/shield worn slots; it is not used by this kit family. | read |
| `f_8019b6e0` | `Pouch_GetAssignedTool` | Reads the age-selected assigned-tool value and resolves it to an index in the native tool catalog, returning minus one when unresolved. It is not used as a sword/shield ownership or wear check. | read |

## Equipment pieces and hand state

These rows retain **read** from the supported-build static investigation of the equipment routines and their native
callers. The host callers are `equipment_read` and `equipment_play` in `host/oot_coop_players.c`
at `2f01e1b4bdb6e1629c54a998f0403519fe4e5c74`. Requesting a visible piece is separate from pouch ownership
or selected-equipment consistency; the latter uses `f_80a9acd0` above.

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_82e17b20` | `EquipmentUser_RequestPiece` | Requests a locally named piece for an equipment kind; name is passed by pointer cell, with initial state and variant. Cancels an earlier request for the same kind before creating the replacement. Kinds and hand slots are distinct (`equipment_play`) | read |
| `f_80d07ab0` | `EquipmentUser_GetHandState` | Resolves the live slot handle and reports its effective hand state. Pending requests can override it; after the request byte clears it consults the piece's model-binding state, rather than treating zero as sheathed (`equipment_read`, `equipment_play`) | read |
| `f_80e54c40` | `EquipmentUser_ChangeHandState` | Routes a hand slot's state request, in-hand, sheathed or inactive, to the corresponding native operation (`equipment_play`) | read |
| `f_82e1d1b0` | `EquipmentUser_RemoveHandPiece` | Cancels the slot's outstanding creation and removes its current linked piece, with explicit policy parameters controlling ancillary native behavior (`equipment_play`) | read |
| `f_80817690` | `Actor_GetEquipmentUser` | Returns the actor's equipment-user component, or null when the component table is absent. | read |
| `f_810cceb0` | `EquipmentUser_RemoveArmourLink(eu, link, flag)` | Removes the live piece in armour link `link` (0 to 12; an index above 12 counts as 0). The 13 link records are at `eu+0xe0+0x18*link` (the host's records 8 to 20 after the hand slots, `eu+0x20+0x18*(8+n)`); a record is `{+0x8 holder pointer, +0x10 s32 generation}`, all ones when empty. Link 0 first runs `f_804d8240`. An **empty record** cancels the pending create request of the kind that the link-to-kind table (`0x83f195d0`; an index above 12 means kind 7) gives: if the kind's state word (u32 at `eu+0x12d4+8*kind`) is 1 it frees the request found in the request cell (u64 at `eu+0x10b0+8*kind`), writes the state `{0, 2}`, clears the cell and returns 1. A **filled record** resolves the linked piece actor (the generation is checked against the holder) and deletes it with `f_800c6490(actor, 0)` (when `flag` is 0, after an owner check `f_80e51d10(mgr, piece, [eu+0x18])`; when bit 0 of `flag` is set it starts the piece's own disappear `f_80d0feb0(actor, 0)` if a float at its component's `+0x80` is positive, else deletes at once: this branch is a guess), releases the record (`f_8022b6f0`: the generation becomes all ones) and, for links 1 to 3, sets bit 0x1000 in the u64 at `eu+0x13a0` and calls `f_802347a0(eu)` (appearance changed). Returns bool in bit 0 of `x0`: 1, or 0 when the piece cannot be resolved or the delete is refused. The host calls it with `(eu, link, 0)`, the cleaned path | read |
| `f_82e16c80` | `EquipmentUser_RefreshKind(eu, kind)` | Re-derives one kind's piece from what the player has chosen. The kinds are: Weapon 0, SubWeapon 1, ThirdWeapon 2, Sheath 3, Quiver 4, Bow 5, Shield 6, ArmorHead 7, ArmorUpper 8, ArmorLower 9, ArmorHand 10, Tool 11, SubTool 12, Accessory1 to 4 13 to 16, Extra 17. `x0` is the equipment user (its `+24` is the owner actor), `x1` the kind (u32); it answers a bool in `x0` (a request was made). It reads the chosen name through three typed game-data getters by hash (`0x11c90470`, `0x23745682`, `0x16329625`), looks up two special flags for kinds 14 and 15 (hashes `0xade0ef78` and `0x060890b0`, in the container at `mgr+0xc08`), builds the piece name (kinds 13 and 16 build the flag name `EquipOcarina`, its tail written inline) and then either asks for the piece (`f_82e17b20` for the armour kinds, state 1 or 2; `f_81033f20` or `f_82e21a90` for the others) or, when no piece is wanted, **removes the armour link: kinds 7 to 10 go to `f_810cceb0(eu, kind - 7, 0)`**, links 0 to 3. It removes nothing for kinds 11 to 17: the game's own refresh of every slot, `f_80f401b0`, removes links 8, 9, 10 and 12 first and then asks for kinds 13 to 16, and what a request does over a piece that already exists in those kinds was not worked out. For the tunic (kind 8) the name `Armor_Adult_Normal` (the string at `0x83d0610e`, the default tunic) counts as none: the game's own "no tunic" removes link 1. Callers: `f_80f401b0`, `f_80f402c0`, `f_82e16290`, the AI node `f_8292b1b0`. Hooked by nothing; the port's co-op code calls it for kinds 13 and 16 (`mend_equip` in `host/oot_coop.c`) so that a changed saved ocarina name shows on a Link who is already standing | read |
| `f_8292b1b0` | `OneShotPlayerEquipDynamicEquipmentFromGameData_Evaluate(node)` | The AI node that re-derives one equipment slot from the game data (the name is from another project's notes, which give its offset `0x290b1b0` into the main module). Gets the node's actor (`f_80c90e70`, named in those notes, not read here) and its equipment user (`f_80817690`); when there is one, asks `f_82e16c80(eu, kind)` with the kind held as the first u32 of the node's parameter block (`[node+32] & ~3`), with no link removal first; then sets the node's status (`+24` bits 30 to 31) to 2, done, whether or not an equipment user was found | read |
| `f_82e16290` | `EquipmentUser_Setup(eu, &ownerRef)` | Reached only through the function table (no direct caller). Sets `eu+24`, the owner actor, from `[x1]` when it is null, then asks for pieces for every kind: kinds 0, 6 to 10 and 13 to 16 through `f_82e16c80` on one branch, and on the other kinds 0, 6 and 7 through `f_82e21a90` with a default and kinds 13 to 16 through `f_82e16c80`. That it is the equipment user's own setup is a guess from its shape | guess |
| `f_80f401b0` | `Player_RefreshAllEquipmentPieces(controller, flag)` | The equipment user is at `controller+0x470` (returns at once if null). With flag 0 it calls `f_82e1dd30(eu, 4)`, then in this order refreshes kinds 0, 6, 7, 8, 9 and 10; removes link 8 and refreshes kind 13; removes link 9 and refreshes kind 14; removes link 10 and refreshes kind 15; removes link 12 and refreshes kind 16 (links 8, 9, 10 and 12 are kinds 13 to 16 by the table: the game removes the link, then asks again from the saved choice). With flag 1 it tail-calls `f_80f402c0` with `x0` = the object at `[[0x84e9c000+4008]]+0x4e8` (not read further). Callers `f_80f40110`, `f_80f40160`, `f_82971f50`, `f_833c4fa0` | read |
| `f_80c98ab0` | `EquipmentUser_BindBlackboard` | Loops the 18 equipment kinds and binds each one's blackboard key `EquipmentUser_<KindName>` (format string at 0x83cfa373, names through the offset table at 0x83f19540 into the blob at 0x83f19490); kinds 0, 6, 5, 11, 12 get hand-state handling. Kind names: 0 Weapon, 1 SubWeapon, 2 ThirdWeapon, 3 Sheath, 4 Quiver, 5 Bow, 6 Shield, 7 ArmorHead, 8 ArmorUpper, 9 ArmorLower, 10 ArmorHand, 11 Tool, 12 SubTool, 13 to 16 Accessory1 to 4, 17 Extra | read |
| `f_81033ea0` | `EquipmentUser_RequestNamed` | `(eu, kind, nameCell, a, b)`: for kind 8 (ArmorUpper) and the name `Armor_Adult_Normal` (literal at 0x83d0610e) it removes the upper-armour link instead (`f_810cceb0(eu, 1, 0)`, returns 1); every other case tail-calls `f_81033f20(eu, kind, nameCell, a & 1, b & 1)` | read |
| `f_81033f20` | `EquipmentUser_RequestPieceGeneric` | The non-special-kind request that `f_82e17b20` forwards to with `(eu, kind, nameCell, 0, 1)`: with the parameter flag at +667 set it refuses kinds 8 to 10 for **the player** (`f_804d6db0`) and kind 14 for anyone else; otherwise builds the creation request from the owner actor's placement | read |

## Data

| Address | Name | What it is | Sure |
|---|---|---|---|
| `0x84c9e2a8` | `g_GameStateHolder` | A state singleton the pouch event needs ready | tested |
| `0x84eb6888` | `g_ActorDb` | The actor database, which the pouch event needs | tested |
| `0x84e8c060` | `g_ActorInfo` | Actor info, which the pouch event needs | tested |
| `0x84e98e28` | `g_PouchMgrHolder` | The pouch manager's holder (for `f_805b63e0`). The same variable menus.md calls the item database: GOT cell `0x84c9e0d0` holds this address, so `[[0x84c9e0d0]]` is the pouch manager. Read by `f_828d4a70` and `f_805b63e0`. | tested |
| `0x83f0a6d8` | `str_Script` | The string "Script", the pouch event's caller | tested |
| `0x83f195d0` | `EquipmentUser_LinkKindTable` | 13 u64: the kind of each armour link, 8, 8, 9, 10, 3, 7, 7, 4, 13, 14, 15, 17, 16. Used only for the empty-record cancel in `f_810cceb0`. It gives link 0 the kind 8 (tunic) where the host's `armour_link_kind[0]` is 7 (mask): see Open questions | read |
| `0x83f0a928` | `HandSlotKindTable` | The kind of each hand slot: 1, 0, 5, 6, 11, 12, twice (bytes read from the image). It indexes hand slots differently from the statement in Notes that kinds 0, 1, 5, 6, 11 and 12 have hand slots 0, 1, 3, 4, 5 and 6 | read |

The item database `[[0x84c9e0d0]]` the pouch event loads is on [menus.md](menus.md).

## Structures

### A character controller

| Offset | Field | Sure |
|---|---|---|
| `+40` | Its body; `+472` of that is the forward speed the physics step uses | tested |

### The Life component (`[actor+0x270]+0x2b8`)

A 0x1d20-byte object with the vtable `0x84b6c460` (`hos_oot_is_player` checks it); the offsets below are what `f_804bd8c0` and the queries read. **read**

| Offset | Field | Sure |
|---|---|---|
| `+0x18` | The actor | read |
| `+0x28` to `+0x3d` | The request block (22 bytes), folded in by the step and then cleared: s32 id at `+0x28` (idle -1), u8 pending at `+0x2c`, s32 amount at `+0x30` (a negative amount counts as its absolute value when bit 0 of the u16 at `+0x3c` is set; bit 2 of it takes the maximum life instead and sets bit 14 of `+0x1d18`), s32 at `+0x34` (added atomically to the maximum cell's value when the flag word's bit 1 is set; a negative one goes to `f_82e68030`), f32 at `+0x38` (idle 8576.0), u16 flags at `+0x3c` | read |
| `+0x224` | s32, zeroed after a hit was taken | read |
| `+0x228` | s32, the hit amount the step adds to the total (a positive amount lowers life) | read |
| `+0x240` to `+0x2d7` | The incoming hit record: attacker qword `+0x240`, hit id s32 `+0x248`, bytes at `+0x24c` and `+0x24d`, bit 5 of the byte `+0x252`; copied whole to `+0x1b20..+0x1ba7` once a step. The rest of its fields were not worked out | read |
| `+0x1350` | s32, another damage term | read |
| `+0x1b08` | A weak actor handle: the last attacker (u64 `+0x1b10`) and last hit id (s32 `+0x1b18`); the bytes `+0x1b1c`, `+0x1b1d` and the u16 `+0x1b1e` are compared too | read |
| `+0x1c10` | The pointer to the life cell (the value is the s32 at the cell's `+8`; quarter hearts is the working unit, not shown by the code) | read |
| `+0x1c18` | The pointer to the maximum cell (value s32 at `+8`) | read |
| `+0x1c20` | s32, zeroed at the start of the step, then the heal amount | read |
| `+0x1c38`, `+0x1c70` | s32 counts (7224 and 7280) that `f_82a52460` tests above 0 | read |
| `+0x1ca0` | A state word: 2 when `+0x1c70 > 0`, else 1 when `+0x1c38 > 0`, else 0 (written by `f_82e67dd0`) | read |
| `+0x1cb0` | s32, the step's total | read |
| `+0x1d18` | u32 flag bits: bit 8 skips the damage swap (cleared and set again during the step from the hit-state bytes `+0x136c` and `+0x2cf`), bit 12 cleared at entry, bit 14 set from the request's bit 2 | read |
| `+0x1d1c` | s32 | read |

## Notes

### Equipment kinds and links

The equipment user (`Actor_GetEquipmentUser`, `f_80817690`) keeps one record pointer per kind at `eu+0x10b0+8*kind` (18 kinds) with a state word at `eu+0x12d4+8*kind`, the hand-slot records at `eu+0x20+0x18*n` (records 0 to 7) and the 13 armour-link records at `eu+0xe0+0x18*link`. `f_80c98ab0` binds each kind's blackboard key `EquipmentUser_<KindName>` (a format string at `0x83cfa373`, the names through the offset table at `0x83f19540` into the blob at `0x83f19490`; kinds 0, 6, 5, 11 and 12 get hand-state handling). `f_82e17b20` for kinds 0, 1, 5, 6, 11 and 12 has hand slots 0, 1, 3, 4, 5 and 6 (read from the code). `f_81033ea0(eu, kind, nameCell, a, b)` removes the upper-armour link instead (`f_810cceb0(eu, 1, 0)`, returns 1) for kind 8 and the name `Armor_Adult_Normal`; every other case tail-calls `f_81033f20(eu, kind, nameCell, a & 1, b & 1)`, the request `f_82e17b20` forwards to with `(eu, kind, nameCell, 0, 1)`: with the parameter flag at `+667` set it refuses kinds 8 to 10 for the player (`f_804d6db0`) and kind 14 for anyone else, otherwise it builds the creation request from the owner actor's placement. The player's equipment-user parameter resource names the blackboard keys, the hidden material groups `G_Body`, `G_Glove` and `G_Boots` and the default head piece actor `Armor_*_Default_Head`. Kinds mask 7, tunic 8 and boots 9 were settled from the image, not from a game. **read**

### Item actors

Both ocarina actors' ActorParam name the `Common` event performer, where every other item actor read names `PouchContent`; the game's two grappling items (the first and the upgraded one) share one model. **read**

- `f_82c415e0` (the movement update) also runs the AI component's unit at index `+0x18` ([ai.md](ai.md)). **read**

- An event node's status is bits 30-31 of its `+24`: 2 done, 3 probably failed ([sequences.md](sequences.md)). `host/hos_main.c` calls `OneShotAddOrRemovePouchContent`'s calc on a stand-in node, which works because that calc never touches the node's vtable or its graph at `+8`. **read**
- Only a walk's, run's or swim's speed is scaled. Scaled, the ledge climb's 55 m/s frame threw Link past the ledge. The first
  of the three places inlines the setter, so no speed is scaled twice.

## Open questions

- Which armour link holds a worn mask. The game's link-to-kind table gives link 0 the kind 8 (tunic) and puts kind 7 (mask) in links 5 and 6, where the host's `armour_link_kind[0] = 7` and its comment say a mask landed in link 0 in a game. The table is used only for the empty-record cancel in `f_810cceb0`, so `outfit_remove` of link 0 on an empty link 0 would cancel the kind-8 request, not a waiting mask request; the filled-link path does not use the table. One look at a worn mask settles it: read `eu+0xe0+0x18*0`, `0x18*5` and `0x18*6`; expected link 0 per the host's observation.
- The two statements about hand slots (the table at `0x83f0a928` and "kinds 0, 1, 5, 6, 11, 12 have hand slots 0, 1, 3, 4, 5, 6") index them differently; which is right was not reconciled.
- The three getter hashes' names in `f_82e16c80` (`0x11c90470`, `0x23745682`, `0x16329625`), the flag bit 0 branch of `f_810cceb0`, and `f_82e21a90` (a request builder; the kind to option-index table 0, 3, 4, 6, 9, 10 was seen, not read further).
- What `f_82e16c80` does for kinds 13 to 16 when a piece of the kind already exists (a different ocarina asked for over one that is out). The game's own refresh of every slot (`f_80f401b0`) removes the link first (`f_810cceb0(eu, 8, 0)` and the others for links 9, 10 and 12); the AI node `f_8292b1b0` and the co-op mend ask without removing. A run that gives one ocarina over the other would settle it: expected two pieces if the request does not replace.