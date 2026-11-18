# Actors

What an actor is in this game, how actors are made and removed, and how each one is updated every frame: the one actor
class, its components and parameter files, the managers that create and delete actors, the five jobs each actor runs on
the BaseProcExecutors, the resident actors (Link among them), and the settings that decide how often an actor is
updated at all. Looked at in November 2026 by static analysis of the binary, for the frame-rate work:
[jobs.md](jobs.md) found the frame bound by the game's logic on the CPU, and the actors are most of that logic.

**LS code:** `host/hos_main.c` (`hos_oot_is_player`, `hos_oot_lift_player`, the flight and the
pouch calls), `host/oot_coop_players.c` (request lifetime and placement),
`nx2/oot_patches.py` (`patch_life`, `patch_movement`)
**See also:** [jobs.md](jobs.md) (the pools, stage 5, the BaseProc phase), [player.md](player.md) (Link's movement, health
and pouch), [maps.md](maps.md) (the layouts, the actor packs and ActorParam, the actor registry), [culling.md](culling.md),
[events.md](events.md)

## In short

1. **There is one actor class.** The game registers a single class with its actor factory, "GameActor" (`f_83392300`):
   every actor, from a wall piece (`Land_*`) to an enemy to Link, is a 0x788-byte GameActor (vtable `0x84b45e18`), built
   on the engine's actor base (vtable `0x84c7b7a8`). What an actor does comes from its **components**, named by its
   ActorParam's `Components` ([maps.md](maps.md), *What an actor is made of*): two registries map a component's name to
   its maker, the engine's 28 (`f_81209b40`: AS, AIInfo, Physics, Model, LOD, CalcSkip, …) and the game's
   (`f_8122db20`, about 109 entries: Life, Player, BSA, HS, Npc…, Weapon, …). **read**
2. **Creating and deleting** goes through requests. A placement (a map's layout, [maps.md](maps.md)) or an event node
   (`SeqExecuteCreateActor`, `ExecuteGenericRequestCreateActor`) asks the actor manager for an actor by name
   (`f_80392a70`: the pack is loaded, the instance registered); the BaseProc manager (`[0x84eb0d90]`) keeps three request
   queues, and **six "BaseProcCreateAndDeleteThread" threads** create and delete from them (`f_83ad0bf0`), off the frame.
   `SeqExecuteWaitCreateActor` waits for the queues to empty (`f_83acff00`). **read**
3. **Each actor has five jobs** (`f_83af21f0`, at actor `+0x2c0` to `+0x2e0`), each a small functor pointing at the
   actor. In stage 5 of the frame ([jobs.md](jobs.md)) the BaseProcExecutors run them, and each calls one or two of the
   actor's virtual update methods (slots 50 to 56). The game's big per-frame update is slot 52 (`f_82c3fab0`), reached
   from the second job, `f_800b3ce0`, which is the job [jobs.md](jobs.md)'s profile found on 18% of the frame's critical
   path. **read** The game names four BaseProc phases (`PreCalc`, `PostCalc`, `PostSensor`, `PostUpdateMatrix`); which
   job is which phase was not worked out (**guess**: the five are those four and a "Blank" one, from the LOD settings'
   names).
4. **How much an actor is updated is data:** its LOD and calc-skip settings (`engine__component__LODParam`,
   `engine__cskip__…`) say, per actor, whether each phase's job is pushed at all (`ForbidPushJobPreCalc`, `…PostCalc`,
   `…PostSensor`, `…Blank`), beyond what distance or outside the view it stops (`ForbidPushJobDistance`,
   `ForbidPushJobRadiusOutsideView`), whether it may be updated only every few frames (`EnableCalcSkip`,
   `CalcIntervalOnCalcSkipForce`) and whether its cloth, drawing and effects may skip too. **read** (the fields), **guess**
   (what each does, from its name)
5. **Link is a resident actor**, made by the scene's ResidentActorMgr (`Player_Child` or `Player_Adult`, `f_80964800`),
   not by a map. The host finds him by an object every character has (vtable `0x84b6c460`) whose resource record is
   named "Player" (`hos_oot_is_player`). **read**

## Functions

### The actor class and its components

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_83392300` | `GameActor_RegisterClass` | Registers the class "GameActor" (`0x83d2d9a4`) with its maker `f_80ad3230` in the actor manager's class table (`[[0x84c9f3e0]]+8`, through `f_8120a760`). It is that function's only caller: no other actor class is registered | read |
| `f_8120a760` | `ClassTable_Add(table, &name, &entry, &flags)` | Adds a name and its maker to a class table | read |
| `f_80ad3230` | `GameActor_Create(heap, align, arg)` | Allocates 0x788 bytes from the heap (its vtable `+0x30`), runs the engine's actor constructor `f_80ad3480` and sets the vtable `0x84b45e18` | read |
| `f_80ad3480` | `ActorBase_Construct(actor, arg)` | The engine's actor constructor: sets the base vtable `0x84c7b7a8` and clears the fields. Also called from `f_83af00a0` (the maker of the engine's 0x520-byte `ActorBase` class) | read |
| `f_81209b40` | `EngineComponents_Register` | Registers the engine's components by their ActorParam names: Blackboard, ModelInfo, ModelBind, ASInfo, ASOptimize, Animation, RetargetScale, AS, AIInfo, Physics, ELink, SLink, XLink, Reaction, EventMember, EventPerformer, BeforehandLoadEvent, Camera, GameParameterTable, LOD, CalcSkip, CppExecutorParam, NaviAnimator, Pathfinding, Obstacle, BoneBind, Destruction, MotionMatching. The registered names carry a `Ref` suffix (`BlackboardRef`, `ModelInfoRef`, ...) except `ASOptimize` and `CppExecutorParam`; the same function registers the class `ActorBase` first (maker `f_83af00a0`). | read |
| `f_8122db20` | `GameComponents_Register` | Registers the game's components (about 109 entries), each a `{type, name, maker}` entry (from `0x84e42f90` on): Accessory to WorldInfo, with Life (0x280 bytes), Player, BSA (0xc0), Physics, HS, NpcMovementInfo, Weapon and others | read |
| `f_829c3780` | `QueryActorGetBaseProcId_Evaluate` | Slot 39 of the AI query node `QueryActorGetBaseProcId` (vtable `0x84a81040`; its name getter `f_829c38c0` is slot 19). Writes the node's actor's BaseProc ID, the 32-bit word at actor `+0x18`, to the node's output at `node+0x20` (the actor is the node's `f_80853d60`, `[[[node+8]+8]+0x1f0]`), calls `f_80856e80` on `node+0x28` when bit 0 of the byte at `node+0x28` is set, and sets bit 0 of the byte at `node+0x1f` | read |
| `f_80853e00` | `Actor_GetLifeComponent(actor)` | `[[actor+0x270]+0x2b8]`, the actor's Life component ([player.md](player.md)), or 0 when the actor has no component table | read |
| `f_82c3f780` | `Actor_GetComponent1d8(actor)` | `[[actor+0x270]+472]`, or 0 when there is no component table. The co-op duel code reads it as the equipment component; [ai.md](ai.md) lists the equipment component at `+0x1f8`, so the name is not settled | read |
| `f_8084acc0` | `Actor_GetComponent358(actor)` | `[[actor+0x270]+856]`, or 0 when there is no component table: the same accessor as `Actor_VirtualKeys` (`f_80964e50`, [input.md](input.md)), a second copy. The co-op duel code reads it as a player component | read |

### The five jobs each actor runs

`f_83af21f0` is slot 12 of the actor vtable (the base's and GameActor's are the same function). The five jobs' runs
each first record the actor being run against the current executor thread (in a six-entry table at `[[0x84c9dc40]]+0x80`,
keyed by the thread's `+0xa8`), then call the actor's method; most of them also call slot 57 first.

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_83af21f0` | `ActorBase_CreateJobs` | Makes the actor's five jobs, each a 0x38-byte node and a 0x30-byte functor that points back at the actor (layout below), with the vtables `0x84c7bed8`, `0x84c7bf00`, `0x84c7bf28`, `0x84c7bf50`, `0x84c7bf78`, stored at actor `+0x2c0`, `+0x2c8`, `+0x2d0`, `+0x2d8` and `+0x2e0` (the last also at `+0x138`). It also makes a 0x100-byte block at `+0x470`. Jobs 0 to 3 get 0x38-byte nodes; job 4's node is 0x20 bytes with its functor at node `+0x10`. After the jobs it goes on with more virtual calls and `f_83ace620`, `f_83ace750`, `f_83af88d0` and returns a flag. | read |
| `f_800b73d0` | `ActorJob0_Run` | Job 0 (`+0x2c0`): calls the actor's slot 50 (`+0x190`) with the job's argument, then slot 51 (`+0x198`) | read |
| `f_83af59c0` | `ActorJob2_Run` | Job 2 (`+0x2d0`): slot 57, then slot 53 (`+0x1a8`) | read |
| `f_83af6150` | `ActorJob3_Run` | Job 3 (`+0x2d8`): slot 57, then slot 54 (`+0x1b0`) and slot 56 (`+0x1c0`) | read |
| `f_800b9420` | `ActorJob4_Run` | Job 4 (`+0x2e0`), the largest (3,480 instructions, about 45 indirect calls): slot 55 (`+0x1b8`) and much besides, among them actor links (`f_802dc440`, [events.md](events.md)) and the components at actor `+0x270` | read |
| `f_82c46560` | `GameActor_vt57` | Slot 57: returns the word at actor `+0x5f8` (the base's returns 0). The jobs call it before their method | read |
| `f_82c3fab0` | `GameActor_Calc52` | Slot 52, run by job 1 (`f_800b3ce0`, row in [jobs.md](jobs.md)): the game's main update, 1,724 instructions calling about 40 subsystems by the components present, among them Link's movement update (`f_82c415e0`, twice, [player.md](player.md)), the bones, cloth and look IK (`f_8018dba0`), the player's climb and ladder states (`f_82ea25b0`), the player's game parameters (`f_80609d00`), NPC talk (`f_802c91f0`) and the engine's slot 54 (`f_800cdbe0`) | read |
| `f_800cdbe0` | `ActorBase_vt54` | GameActor's slot 54 (6,236 instructions), run by job 3 and also called from slot 52 and from the actor's slot 53 (`f_82c43780`; `0x82c43898` is the call inside it, not a function) | read |
| `f_800c34e0` | `GameActor_vt56` | Slot 56 (3,052 instructions), run by job 3 | read |
| `f_8018dba0` | `Skeleton_Update` | A 6,004-instruction update with the labels "OffHelperBone", "OffSupportBone", "OffCloth" and "LookIK": the skeleton's helper and support bones, cloth and look IK. The strings also name HandIK, FootIK, FloorContact, TailBone, FixedChain, BoneModifier (and PostIK), RagdollReaction and the eye variations, so it is the skeleton's IK and bone modifier update as a whole; also called from `f_802ca820`. | guess |
| `f_82ea25b0` | `Player_UpdateClimb` | A 5,100-instruction state update named by its strings ClimbEd, ClimbMoveUpEd, Crouch, LadderUp, LadderDown, and more. Its strings also include the player's camera behaviour parameters (CameraBehavior, LatCalcType, SpCameraType, ...) and SwordBlurParam, so it is broader than a climb update; the name stays a guess. | guess |
| `f_80b4eaa0` | `GameActor_SleepToPreActor` | Slot 72, with the string "SleepToPreActor": puts the actor to sleep as its PreActor (below) | guess |

The other method slots GameActor overrides, from the engine's: 0, 1, 7–9, 11, 14, 16, 17, 21, 23, 35, 37, 44–58, 65, 66,
68–82, 86, 87, 89, 92, 93 and 95. Slots 75 and 77 name "Logic_Disappear", slot 49 "Logic_Appear". **read**

### The managers: creating and deleting

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_83aff1f0` | `ActorModule_Calc` | The Actor module's calc (its vtable `+16`, [jobs.md](jobs.md)): among others, calls `f_83afbfb0` on the actor manager and `f_83acf9b0` / `f_83acfa30` on the BaseProc manager | read |
| `f_83afef50` | `ActorModule_Init` | The Actor module's slot 7: builds a settings block (`f_80b5e290`), then `f_80ed5d00` on the BaseProc manager, `f_83afb830` on the actor manager, `f_83b059a0` on the actor registry (`[0x84eb1940]`, [maps.md](maps.md)), and makes a 0x188-byte object (`f_80b5ef60`) kept at Actor module `+0x1b0` | read |
| `f_80ed5d00` | `BaseProcMgr_Init(mgr, settings)` | Sets the BaseProc manager up and calls `f_80ed7f60` | read |
| `f_80ed7f60` | `BaseProcMgr_CreateThreads` | Makes six "BaseProcCreateAndDeleteThread" threads (0x160 bytes each, sead::Thread `f_8069dbe0`, vtable `0x84c79680`), each given its core mask from settings `+0x60`, `+0x64`, … `+0x74` (`f_80ed84a0`) | read |
| `f_80ed84a0` | `Thread_SetCoreMask(thread, &mask)` | Keeps the mask at thread `+0xb0` and sets it on the thread | read |
| `f_83ad0bf0` | `BaseProcCreateAndDeleteThread_Run` | Slot 14 of that thread: works through the manager's requests (`[thread+0xd8]`), creating and deleting, with the profiler labels "UpdateRequestQueue", "%s(%p)" and "Delete %s(%p)" | read |
| `f_83acff00` | `BaseProcMgr_IsRequestEmpty(mgr)` | Under the mutex at `+0x3c8`: true when the three request counts (`+0x3f8`, `+0x410`, `+0x428`) are 0 | read |
| `f_83acf390` | `BaseProcMgr_DestroyInstance` | Destroys the BaseProc manager instance: first releases the object at `0x84eb0d78` through its vtable slot 0 and clears that pointer, then destroys `[0x84eb0d90]` (`f_83acf400`, 0x470 bytes, freed with `f_8021dea0`) and clears it | read |
| `f_83afb830` | `ActorMgr_MakeHeaps` | Makes the heaps "ActorInstanceHeap", "BaseProcCreateOrderHeap" and "DynamicParamHeap" | read |
| `f_83afbfb0` | `ActorMgr_Calc` | The actor manager's per-frame step (972 instructions), from the module's calc | guess |
| `f_80392a70` | `ActorMgr_RequestCreateByName` | Creates an actor by name: loads `Pack/Actor/<name>.pack` (`f_8002f220`), finds the archetype (`f_802dbd90`) and adds the instance (`f_83b072b0`, both [maps.md](maps.md)), then hands it on (`f_83afdf90`). `f_8121f9a0` and `f_82c4b220` have the same strings (**guess**: copies for other callers) | read |
| `f_83afdf90` | `ActorMgr_PushCreate` | Queues the creation (604 instructions; slot of vtable `0x84c7c778`) | guess |
| `f_832dca10` | `SeqExecuteCreateActor_Enter` | The script node SeqExecuteCreateActor (parameters ActorName, InitPos, IsSleep, OverwriteParam, ActorLink) starting: calls `f_80392a70` | read |
| `f_808e90a0` | `SeqExecuteWaitCreateActor_Update` | SeqExecuteWaitCreateActor (parameter IsWaitBaseProcRequestEmpty): waits on `f_83acff00` | read |
| `f_805cf0e0` | `Placement_ReadCreateParams` | Reads a placed actor's creation fields: Presence (FlagName, IsNegation, IsCheckLazy), ExtraCreateRadius, IsForceActive, IsShortCreateRadiusInHeavy, MoveRadius, IsPhysicsStable, IsInWater, ExternalParameter, … and the AreaCulling block (`f_805cefb0`) | read |
| `f_805cefb0` | `Placement_ReadAreaCulling` | The AreaCulling block: AreaCullingActivationArea, AreaCullingTargetArea | read |
| `f_80ed6f00` | `PreActorModelWorkers_Init` | Creates the PreActor model-composition workers: threads all named `PreActorModelCompose`, priority 26, each pinned to one of the selected cores 0 to 5. What a PreActor is exactly (a light stand-in for a far or sleeping actor) is a guess | read |

### Request lifetime and placement

These call roles first came from `host/oot_coop_players.c` at `2f01e1b4bdb6e1629c54a998f0403519fe4e5c74`. The rows marked **read** have since been read in the lifted code (take, drop, delete and the transform setters); the pending-queue rows are still the host's contract only. Creation itself is `f_80392a70` above.

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_8038fbd0` | `ActorRequest_Take(request, flag, arg)` | Takes the actor a completed create request produced, for the caller (the host's `actor_take` calls it as `(request, 1, 0)` once the request reports ready, then tracks the actor's identity and lifetime). Under the BaseProc manager's lock (`[0x84eb0d90]+968`) and the request's own (`+0x10`) it takes the actor (request `+0x08`); when bit 0 of `flag` is set it first calls `f_800b4f30(actor, 1, arg)` (what that call does was not worked out); then `f_8038f990(manager, actor)`, which returns 0 for an actor whose state is 7 to 11 and otherwise sets bit 25 of the actor's `+0x30` atomically and, if it was clear, queues the actor with `f_800d3db0`. Returns the actor pointer, or 0 when the request has none | read |
| `f_8038fde0` | `ActorRequest_Drop(request)` | Gives up a create request that reports it was abandoned (state, the low 16 bits of `+0x00`, equal to 4: the game gave it up), without adopting an actor from it (the host's `actor_take`): tail-calls `f_80b4e2e0(request, 0)`, which goes to `f_80b4e6e0(request)`; that clears the state bits by compare-and-swap, zeroes `request+8` and returns the request to the pool, all under locks, and the answer is 1. Any other state returns 0. It does not delete an actor | read |
| `f_80b4e020` | `ActorRequest_FindPending` | Walks the manager's pending-create tables (three sets at `+0x60`, `+0x88`, `+0xb0` and a list under the lock at `+0x100`): for every entry the matcher object (argument 2, virtual call slot 0) accepts, and whose flag word at entry `+0x150` has its low two bits clear, sets bit 0 of that word by compare-and-swap; returns true when any entry matched. Used by the host's `request_cancel` | guess |
| `f_80b4e6e0` | `ActorRequest_FreePending` | Cancels/releases the pending create request selected by the caller's queue check (`request_cancel`). Reached with a request in state 4 from `f_8038fde0` it clears the request's state bits by compare-and-swap, zeroes `request+8` and returns the request to the pool under locks | guess |
| `f_80b4e2e0` | `ActorRequest_DeleteResult` | Cancels a request that is no longer pending by requesting removal of its actor result (`request_cancel`). For a request in state 4 it goes on to `f_80b4e6e0`, which recycles the request (see `ActorRequest_Drop`). Read: it takes `(request, flag)` under the manager's and the request's locks; a request in state 4 goes to `f_80b4e6e0`; one in state 2 or 3 gets its state set to 5 (6 when bit 0 of `flag` is set) by compare-and-swap and its actor result (request `+8`) is removed with `f_800c6490(actor, 2)`; returns 1 when handled. | guess |
| `f_800c6490` | `Actor_RequestDelete(actor, mode)` | Requests an actor's removal (the host's `puppet_remove`, for an actor it adopted). Returns 0 at once when the actor's state (`+0x2c`) is 7 to 11 (already on its way out) or bit 16 of its flags (`+0x30`) is already set (both re-checked under the lock). Modes 0, 3, 4, 6 and 8 are first checked against a 9-bit field of `[[actor+0x1b0]+0x50]` (mask `0x1ff` shifted by 18, 27, 36, 45 and 54 for modes 0, 3, 4, 8 and 6; table at `0x83f8f1b0`); a field that is non-zero and not all ones calls the actor's vtable slot `+0xe8` instead and returns 0. Otherwise it sets bit 16 of `+0x30` atomically (mode 2 also bit 22, and queues the actor a second time when that bit was clear); when bit 16 was clear it queues the actor with the BaseProc manager (`f_800d3db0(manager, actor)`) and calls the actor's vtable slot `+0xe0` with the mode. Returns 1 on every path past the early exits. The manager's lock at `+968` is taken on the slow path only: a calling thread that is one of the manager's own threads skips it | read |
| `f_80c8fd60` | `Actor_SetTransform(actor, matrix*, w2)` | Takes a row-major 3x4 float matrix (three rows of rotation, rotation, rotation, position) and, when the actor has a physics component (`[[actor+0x270]+0x50]`), passes position and rotation to `f_804e6630` with `pending` = bit 0 of `w2` inverted; if that returns true it stops. Otherwise (or with no physics component) it copies the matrix into the actor's own spare transform block (position at `+0x358`, rotation at `+0x364`; a position starting with the quiet NaN `0x7fc00000` zeroes the position block, a rotation starting with it fills the rotation block with the identity) and sets (when bit 0 of `w2` is 1) or clears bit 15 of the actor flags `+0x4a8` atomically. It does not touch `+0x31c` or `+0x328` and never sets bit 23: the host's bodies write those words themselves (`actor_place`, called with `w2` = 0). It and `f_804e6580` are two ways into the same sink, `f_804e6630`; the host's bodies use this one (pair sessions), the game's own node uses `f_804e6580` | read |
| `f_804e6580` | `Actor_ApplyMtxToPhysics(actor, w1)` | The actor's vtable slot `+0x218` (slot 67; `0x84b46030`): hands the transform the caller has just written into the actor itself (position `+0x31c`, three floats; rotation `+0x328`, nine floats) to the actor's physics component (`[actor+0x270]+0x50`). Does nothing when the actor's state (`+0x2c`) is 1. Otherwise it first sets bit 23 of the actor flags `+0x4a8` atomically (the "warp" bit of another co-op project; set even when the actor has no physics component), then, when it has one, calls `f_804e6630(component, &position, &rotation, pending)` with `pending` = bit 0 of `w1` inverted (`w1` = 0 for the normal call: the new transform is also queued as the body's pending target). The game's own AI node `ExecuteActorForceSetMtx` (`f_82642e50`) writes `+0x31c..+0x34b` and tail-jumps to this slot with `w1` = 0 | read |
| `f_804e6630` | `PhysicsComponent_SetTransform(component, position*, rotation*, pending)` | Moves the actor's physics body (body = `[component+0x20]`; none: returns 0). `position` is three floats, `rotation` nine floats (a 3x3); either pointer may begin with the quiet NaN `0x7fc00000` to mean "keep the current value": taken from the body's pending target (body `+0x1d0`, when body `+0x228` has bit 0 or bit 1 set: one is queued) or else from the actor at `component+0x38` (`+0x31c` / `+0x328`). With bit 0 of `pending` set it stores the result as the body's pending target (a 3x4 matrix, 48 bytes at body `+0x1d0`, marked in body `+0x228` bits 0 and 1) and flags the object at body `+0x1c8` (byte `+0x1f2` bit 7; without it body `+0x22e` bit 7). It then applies the new place to the body's character controller (body `+0x190`): through the owning object's virtual call (vtable `+0xc8`, with the 3x4 block) when that object's controller is the body's, else directly (position `f_80182250`, rotation `f_806d8a40`, each skipped when its pointer began with the NaN), and finishes through `f_804e6870`; bit 0 of the result is returned. After storing a pending target, if the object at body `+0x1c8` has a non-zero count at `+0x130` it walks the pointer array at `+0x138` and calls `f_837fcca0` on each entry's `+0x10` that is not null. 26 direct callers, `f_804e6580` and `f_80c8fd60` among them | read |
| `f_82642e50` | `ExecuteActorForceSetMtx_Run` | The script node that sets an actor's transform from its inputs: computes position and rotation from the node's matrix inputs, stores them at actor `+0x31c..+0x34b`, then tail-jumps to the actor's vtable slot `+0x218` (`f_804e6580`) with `x1` = 0. The name is the other co-op project's (its node-run address converts to this function), the behaviour read here. Inputs: a nine-float block (the rotation) through `[[node+0x20]]` and a three-float block through the tagged pointer at `node+0x28`; the actor is `[[[node+8]+8]+0x1f0]` | read |
| `f_80b4fbc0` | `ActorRequestCell_Release(cellAddr)` | If `*cell` is non-null calls `f_8038fde0` (the drop of the request) and clears the cell. | read |

### Death, destruction and a placed object that stays broken

An actor's Death component (slot `+0x1c0` of its components, [ai.md](ai.md)) runs a death in stages; the break of a pot or a crate is one such death. A death is asked for by the AI one-shot `OneShotDeathRequestDeath` or by the Life step, and a placed object that dies for good writes the Key64 flag of its placement so that it stays gone. Looked at for co-op's shared breakables. Every row is **read** from the lifted code; none was run. See *The Death component and a break* in Notes.

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_803c8bb0` | `Death_Request(death, reason, arg, force)` | Starts a death on an actor's Death component (`death` is `[actor+0x270]+0x1c0`): sets bit 14 of `[death+0x20]`, stages bits 1 to 3, finds the reason's row (the reasons are listed at `0x83f18090`) and, for some procedures, calls `f_800c6490(actor, 0)`. Called by the AI one-shot `f_80c905f0` and by the Life step | read |
| `f_803c88b0` | `Death_Step(death)` | The Death component's per-frame step, run after the Life step (both from `GameActor_Calc51`, `f_82c3d740`): consumes the deferred request at `+0x8c` to `+0x94` and runs the staged finish `f_80e71650` | read |
| `f_80e71650` | `Death_Finish(death)` | The staged procedure runner: at the last stage it runs the row's procedures through `f_82e08210`, and it ends with `f_800c6490(actor, 0)` or `f_800bf550`. It was seen with two delete-like exits whose guards were not resolved | read |
| `f_82e08210` | `Death_RunProcedures(death, row)` | Runs the death row's procedures: reads the row's IsEmitDeathEffect and IsRequestDestruction and the respawn flag (the last through `f_80f26de0`, which calls `f_80f26e80`), so the effect, the destruction and the placement's flag follow from the row | read |
| `f_80f26e80` | `Death_ApplyRespawnFlag(death, row)` | When the row sets IsSetRespawnFlagToFalse, calls `f_80f27040(actor, IsSetGmdRespawnFlagToFalse)`. Both branches end in a tail call (`f_80f27250` when the row sets it, `f_82e06d50` otherwise); the other branch first calls `f_82c44db0(actor, 1)`. | read |
| `f_80f27040` | `Actor_MarkPlacementRemoved(actor, gmd)` | Sets bit 0 of `[rec+0x98]` (`rec` is the actor's instance record, `[actor+0x3d8]`). When `gmd` is set and bit 3 of `[rec+0x14]` is set and the placement hash `[rec+0x88]` is not 0, writes 1 to the Key64 flag of that hash through `f_80f27130`: the write that keeps a placed object broken in the game's own save, as far as read. It also calls `f_80713fd0` on the record when none of the bits `0x800783` of `[rec+0x98]` was set before, and when bit 5 of `[rec+0x14]` is set and `[rec+8]` is not 0 it writes a named Bool flag (through `f_809d3eb0` and `f_80628a10`) before the Key64 write. | read |
| `f_80f27130` | `GameDataMgr_SetKey64ByKey(mgr, value, key)` | Binary search of the Key64 records (16 bytes each at `mgr+0xc60`, count `mgr+0xc58`), then `f_80f271c0` pushes `{value & 1, record index}`; key 0 or an absent key does nothing. The same job as `f_83781720` ([game-data.md](game-data.md)): a second copy | read |
| `f_80c905f0` | `OneShotDeathRequestDeath_Calc` | The calc of the AI node `OneShotDeathRequestDeath`: calls `f_803c8bb0(death, reason, 0, 0)`. The reason input defaults to 10 (LifeDepleted) when it is not wired, as in a pot's graph | read |
| `f_800b1bb0` | `ActorTree_VisitDelete(node, visitor)` | A recursive walk of the actor system's tree over the entries whose actor state is 2 or above; where the visitor accepts an actor it calls `f_800c6490`. The tree is at `[0x84eb0d90]+0x38` (left `[node]`, right `[node+8]`, the entry is node minus 8, its actor `[entry+0x28]`, the chain of entries with the same key `[entry+0x38]`) | read |
| `f_80c6dc00` | `DestructionRef_Make` | The maker of an actor's Destruction component: allocates the 0x170-byte object (a quiet NaN at `+0x58`) that sits in slot `+0xf0` of its components. The registry lists it next to BoneBind, the entry before Destruction: the maker column is one entry early (see Notes). Corrects the name `BoneBindRef_Make` it had on [animation.md](animation.md) | read |

### The instance record and the create path

An actor made from a placement or a request carries an instance record and the name of its actor file; the create path stores both (see *Structures*).

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_80a04860` | `QueryGenericGetInstanceId_Evaluate` | Slot 33 of the AI query node `QueryGenericGetInstanceId` (the cell is `0x84aa99e0`; no direct callers): after its input preamble (`f_80a04900`) it follows `[[[node+8]+8]+0x1f0]` (the actor) `-> +0x3d8 -> +0x88`, stores that u64 at `node+0x20` and formats it as decimal text (`%llu`) into the node's output string at `node+0x28`, the `InstanceIDString`. It is where the decimal placement hash comes from that the chest's opened-flag name (`IsTreasureBoxOpen.<hash>`) is made of; that consumer was not traced here | read |
| `f_83b04310` | `ActorInstance_Reset(record)` | Resets an instance record to its idle values: scale words 1.0, the u64 id at `+0x88` all ones, flags and links cleared, a quiet NaN at `+0xf0..`. Called twice by the instance add `f_83b072b0` | read |
| `f_83af0700` | `Actor_SetInstanceAndName(actor, record, name)` | Stores `record` at actor `+0x3d8` and `name` at actor `+0x260` (and marks the 384 bytes from `+0x260`); the create path `f_82c4e160` calls it with the create parameters' `+0x00` and `+0x10` | read |
| `f_82c4e160` | `Actor_CreateFromParams(params, factory, flags)` | The create path after a request is ready: the factory (`x1`, virtual call at vtable `+0`) makes the actor; `Actor_SetInstanceAndName` records the parameters' instance record and name; with `flags` bit 0 set, bits 8 and 9 of the actor's flag word `+0x4a8` follow the parameters' bytes `+9` and `+10` | read |
| `f_814e6c90` | `Libc_Malloc(size)` | The C library's `malloc`: a block of `size` bytes from the process allocator (through the hook at `0x84d68658`), or 0 with `errno` = 12 when none; 187 direct callers. A co-op project's guest-heap allocations (a spawn director's, the play requests') use it | read |

### The Shooter component and its shots

A shooter (Link's slingshot and boomerang, enemies that shoot) keeps a list of shot records; each shot makes one actor through the create request. See *The Shooter component* in Notes.

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_80c36cf0` | `ShooterComp_ShootOne(record, shooter, desc)` | Makes one shootable actor for a Shooter component: copies the actor name from `desc`, builds a creation request (shooter's position, identity rotation, unit scale, creator = shooter actor and Shooter type object, two override records KeyHash and OverrideParamNum), calls the create request `f_80392a70` at 0x80c372fc with the record's cell as request out, stores the result in the record and returns 0/1/3 (2 = previous request still pending). Sets no velocity. | read |
| `f_800f36a0` | `ShooterComp_TickShots(comp)` | Walks the Shooter component's entries (`+0x20`, count `+0x2c`) and their records; asks `f_83056970` for each record's state and calls `ShooterComp_ShootOne` for states 1 and 4 and up; state 0 goes to `f_83056240`, state 3 to `f_83056bd0`; writes the entry's "all ok" bit. Called from `BSA_Update` (`f_800eb9c0`) on `[comps+0x3d8]`. What it calls is read; the name is a guess | read |
| `f_809b2df0` | `ShooterComp_TickShotsGuarded(comp)` | Same loop as `f_800f36a0` behind a guard (owner state `[actor+0x2c]` in 7..11, `[actor+0x30]` bit 16 clear, manager no-create flag clear); returns the AND of the records' results. Called by `f_809b2ff0`. | guess |
| `f_82ed07d0` | `ShooterComp_Slot10` | Slot 10 of vtable `0x84b6ff90`: when `+0x18` is empty takes the owner actor from `*arg`, then loops the entry list and calls `ShooterComp_ShootOne` (call at 0x82ed114c). | read |
| `f_83056970` | `ShotRecord_GetState(record)` | Returns the record's state 0 to 9 from its flags (`+0xdb`, `+0xdc`, `+0x30`) and the request cell's u16 state; the Shooter loops fire on states 1 and 4 and up. Its first half and its two callers were read; the meaning of the states is a guess | guess |

### Resident actors

The resident actors live with the scene, not with a map: Link, among others (a `game__scene__ResidentActor` holds
`Actor`, `IsCancelSleepAtEnterBanc`, `HasCancelSleepPos` and `CancelSleepPos`). Their manager, "ResidentActorMgr", is
one of the scene components `f_832d4720` makes ([culling.md](culling.md)). Script nodes create, delete and put them to
sleep: `SeqOneShotSceneRequestCreateResidentActors` (IsCreateChildPlayer), `SeqOneShotSceneRequestDeleteResidentActors`,
`SeqExecuteSceneRequestSleepResidentActors` and `SeqExecuteSceneRequestCancelSleepResidentActors` (CancelSleepPos,
CancelSleepRot).

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_80965170` | `Scene_GetResidentActorMgr(scene)` | The scene's component at `[scene+0x58]+0x78`, checked by type, when the count at `scene+0x50` is at least 16 | read |
| `f_832fe900` | `SeqOneShotSceneRequestCreateResidentActors_Evaluate` | Asks the ResidentActorMgr to create the residents (`f_80965610`, with IsCreateChildPlayer), sets bit 0x2000 of `[0x84e40e20]+0x34` and ends the node | read |
| `f_80965130` | `SeqOneShotSceneRequestDeleteResidentActors_Evaluate` | Asks it to delete them (`f_809659f0`) | read |
| `f_809650c0` | `SeqExecuteSceneRequestSleepResidentActors_Update` | Asks it to put them to sleep (`f_80963920`) and ends the node when that returns true | read |
| `f_80965610` | `ResidentActorMgr_RequestCreate(mgr, child)` | Requests the residents' creation: stores the child flag (`+112`), picks the child or the adult resident name and requests its creation; returns a flag | read |
| `f_809659f0` | `ResidentActorMgr_RequestDelete(mgr)` | Requests their deletion | guess |
| `f_80963920` | `ResidentActorMgr_SleepStep(mgr)` | One step of putting the residents to sleep; true when done | guess |
| `f_80964800` | `ResidentActorMgr_FindByName(mgr, &name)` | Looks a resident up by name; the player's names (`Player`, `Player_Base`, `Player_Child`, `Player_Adult`) are matched as one | read |

### The foliage cut queue

Cutting grass and bushes: callers put a cut request on a queue that the foliage scene's consumer reads (see *The foliage cut queue* in Notes).

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_80ba0800` | `FoliageModule_PushCut(module, cut)` | Copies a 0x3c-byte cut request into a free slot of the foliage scene and queues it (see Q4); ignores radius < 0.01; returns 0 when no module scene or no free slot, else 1. | read |
| `f_80ba08f0` | `MpmcQueue_Push(queue, item)` | Bounded sequence-ring push of a pointer, wakes the consumer, returns 1 / 0 (full). Used for the cut queue at S+0x20. | read |
| `f_82ec3ef0` | `Actor_QueueSwingFoliageCuts(component, steps)` | Per-frame swing handler of the component at `[comps+0x3b8]`: from the label `0x82ec4880` (an instruction inside this function, not a function) it pushes one cut slot per frame step to the foliage queue (radius halved, three swing points from the attack volume). Called only by `f_82c3d740` at 0x82c3e428. The producer part is read; the first half (an animation-slot loop) was only skimmed | read |
| `f_829876a0` | `OneshotTryCutFoliage_Calc` | Slot 39 of the AI node of that name (vtable `0x84a6a848`): builds a cut from position, radius and kind ports and calls `f_80ba0800`. | read |
| `f_8305e390` | `Foliage_CutFromHit` | A hit-reaction style handler (`x1` the hit record, `x0` a component whose `+0x18` is the actor) that cuts through `f_80ba0800` (call at 0x8305e464): radius 2.0, NaN swing points, for certain hit kinds. Called through a function pointer (no vtable cell found). Only the part that builds and passes the cut was read | guess |
| `f_8305e4c0` | `Foliage_CutFromHit2` | The same kind of handler (call at 0x8305e5c4); the cut's kind byte is 0 where `f_8305e390`'s is 4 | guess |
| `f_80458ab0` | `Foliage_CutFromSensorWalk` | A per-frame walk over a manager's actor list that cuts at each match, building the request from sensor data (call at 0x80458c9c); reads the module through the GOT cell | guess |

### The update settings

Reflection visitors: each names a parameter and the field it fills (offsets in *Structures*).

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_83c0dd50` | `LODParam_Visit` | `engine__component__LODParam` (0xd8 bytes, its name at `0x83d6f614`): 44 fields, the pushing and skipping of the actor's jobs (below). Its twin `f_83c0f780` names the same fields | read |
| `f_83c077b0` | `CalcSkipParam_Visit` | `engine__component__CalcSkipParam` (0x88 bytes): InitParam (`+0x40`) and DefaultPresetParam (`+0x38`) | read |
| `f_83c21730` | `CalcSkipInitParameters_Visit` | `engine__cskip__InitParameters` (0xd8 bytes): the same pushing fields as LODParam and the calc skip's (EnableCalcSkipGlobal, EnableCalcAndPhysicsSkip, CalcSkipRescuePriority, CalcSkipRescueDistance, EnableDrawSkip, EnableClothSkip, IsKinematicsSkipKeepAtInit, …). Its twin `f_83c23280` names the same fields | read |
| `f_83c20470` | `CalcSkipDefaultPresetParameters_Visit` | `engine__cskip__DefaultPresetParameters` (0x58 bytes): ForbidPushJobSetting, DisableDefaultForbidPushJob, DisableForbidPushJobByArea, IsOverwriteForbidPushJobDis (the game's spelling), OverwriteForbidPushJobDistance, DisableSkipAll, DisableSkipProc, DisableSkipKinematics, DisableSkipAppearance, DisableSkipXLink, DisplayRadius | read |
| `f_83c0d650` | `BaseProcPhase_Name(phase, &out)` | Copies the name of phase 0–3 (`[phase+8]`) from the table `0x83f90ae0` ([jobs.md](jobs.md)): PreCalc, PostCalc, PostSensor, PostUpdateMatrix | read |

## Data

| Address | Name | What it is | Sure |
|---|---|---|---|
| `0x84eb0d90` | `g_BaseProcMgr` | The BaseProc manager (0x470 bytes): the request queues, the create and delete threads; `f_83acfb90` runs the BaseProc phase on it ([jobs.md](jobs.md)) | read |
| `0x84eb1888` | `g_ActorMgr` | The variable that holds the pointer to the actor manager (0 in the static image, filled at run time). The code reaches it through the GOT cell `0x84c9f3e0` and loads it twice: the cell gives this address, the variable gives the manager (`[0x84eb1888]`; `host/` reads it that way). The manager has the class table at `+8` and the actor heaps (`f_83afb830`); about 116 functions use the cell, jobs 1 and 4's runs among them | read |
| `0x84c9f3e0` | `got_ActorMgr` | The GOT cell holding `0x84eb1888`, the address of the variable that holds the actor manager | read |
| `0x84b45e18` | `GameActor_vtable` | The only actor class's vtable (96 slots). `hos_oot_lift_player` checks for it | read |
| `0x84c7b7a8` | `ActorBase_vtable` | The engine's actor base vtable | read |
| `0x84b6c460` | `CharacterObj_vtable` | The vtable of a 0x1d20-byte object made by `f_80d1fbb0`, the Life component's maker (`f_8122db20` lists it under the name "InactiveCounterRef", the entry before Life: its maker column is one entry early, see Notes). Other actors than Link have one; its `+16` record is named "Player" for Link (`hos_oot_is_player`), and the object `f_804bd8c0` steps (x19, `[actor+0x270]+0x2b8`, the Life component of [player.md](player.md)) is one: its `+7184` is the life cell's pointer | read |
| `0x84c7bed8` | `ActorJob0_vtable` | Job 0's functor (run `f_800b73d0`) | read |
| `0x84c7bf00` | `ActorJob1_vtable` | Job 1's functor (run `f_800b3ce0`) | read |
| `0x84c7bf28` | `ActorJob2_vtable` | Job 2's functor (run `f_83af59c0`) | read |
| `0x84c7bf50` | `ActorJob3_vtable` | Job 3's functor (run `f_83af6150`) | read |
| `0x84c7bf78` | `ActorJob4_vtable` | Job 4's functor (run `f_800b9420`) | read |
| `0x84c79680` | `BaseProcCreateAndDeleteThread_vtable` | The create and delete threads' vtable (slot 14 `f_83ad0bf0`) | read |
| `0x83d2d9a4` | `str_GameActor` | "GameActor" | read |
| `0x83d7c824` | `str_BaseProcCreateAndDeleteThread` | "BaseProcCreateAndDeleteThread" | read |
| `0x84b6ff90` | `ShooterComp_vtable` | Address point of the Shooter component's vtable (slot 1 returns type object `0x84e43cd8`, slot 10 = `f_82ed07d0`, slot 27 returns the Japanese label for "shooter", slot 28 the editor icon `ShooterParam`). Instances are 0x140 bytes made by `f_80e641d0`. | read |
| `0x84b8e6c8` | `CreateInitCallback_vtable` | Closure with one captured pointer to a bool: slot 0 `f_83056e40(closure, creationInfo)` sets bit 0x10000 in the u32 at creationInfo+0x14 from that bool; slot 3 is a no-op. The shoot function passes one that carries the shooter's `actor+0x6a4` bit 0. | read |
| `0x84e42540` | `g_FoliageModule` | The pointer to the foliage module (0 in the image, filled at run time; 50 or more functions load it, none was found that stores it); `+0xf0` holds an object whose `+0x338` is the foliage scene. The GOT cell `0x84c9f2c8` holds this address | read |
| `0x83f18090` | `DeathReason_names` | The names of the 16 death reasons, as a blob of names followed by a table of 16 u32 offsets into it (the table starts 208 bytes after this address): 0 AI, 1 ChemicalCriticalHitFire, 2 Drowned, 3 Eaten, 4 PickedUp, 5 Exploded, 6 Burned, 7 Unequiped, 8 FallIntoAbyss, 9 PhysicsKinematicCollision, 10 LifeDepleted, 11 LifeCondition, 12 UpperCrushed, 13 SideCrushed, 14 Frozen, 15 AutoPlacementMgr. The reason is the second argument of `f_803c8bb0` | read |

## Structures

### A GameActor (0x788 bytes)

| Offset | Field | Sure |
|---|---|---|
| `+0x0` | The vtable, `0x84b45e18` | read |
| `+0x18` | The BaseProc ID, 32 bits (QueryActorGetBaseProcId); its low byte goes into each job's functor | read |
| `+0x28` | A byte copied into each job node's `+0x20` and `+0x21` | read |
| `+0x138` | Job 4 again | read |
| `+0x270` (624) | The components; `hos_oot_lift_player` follows `+800` of it to Link's movement component | read |
| `+0x2c0` … `+0x2e0` | The five jobs (`f_83af21f0`) | read |
| `+0x31c` … `+0x324` (796–804) | The position, three floats (the host's flight reads them as Link's position) | read |
| `+0x330`, `+0x348` (816, 840) | Two matrix elements the host takes the heading from | read |
| `+0x3d8` | The actor's instance record (stored by `f_83af0700` with the name at `+0x260`): its `+0x58` holds the settings a job's `+0x20` byte is taken from (`+0x9c`, `+0xbe`) and its u64 at `+0x88` is the placement's hash (see *The instance record*) | read |
| `+0x470` | A 0x100-byte block made with the jobs | read |
| `+0x5f8` | The word slot 57 returns | read |
| `+0x2c` | u32 state: 1 makes `f_804e6580` refuse; 3 "made" and 4 "in the map" are the values the host relies on (tested by its bodies); 7 to 11: on its way out, `f_800c6490` and `f_8038f990` refuse | read |
| `+0x30` | u32 flags: bit 16 delete requested (`f_800c6490`), bit 22 set by delete mode 2, bit 25 set by `f_8038f990` | read |
| `+0x260` | A pointer to the actor file's name string (stored by `f_83af0700`; `Obj_TBox_A_01` for a chest, seen in play; the same field as `+608` in the co-op notes) | tested |
| `+0x328` | The rotation, nine floats (a 3x3); `+0x31c` is the position, `+0x330` and `+0x348` are among its elements | read |
| `+0x358`, `+0x364` | The spare transform `f_80c8fd60` writes: position, three floats; rotation, nine floats | read |
| `+0x4a8` | u32 flags: bit 23 set by `f_804e6580`, bit 15 set or cleared by `f_80c8fd60`, bits 8 and 9 set by `f_82c4e160` from its parameter bytes `+9` and `+10` | read |

### The instance record (`[actor+0x3d8]`)

Reset by `f_83b04310`. **read**

| Offset | Field | Sure |
|---|---|---|
| `+0x14` | u32 flags: bit 3 set means the object is kept by its placement (`f_80f27040` writes the Key64 flag only then). Not seen live | read |
| `+0x58` | An object holding the settings a job's `+0x20` byte is taken from | read |
| `+0x88` | u64 id, the placement's hash (the original byte-YAML key): all ones (`0xffffffffffffffff`) for an actor the game made without a placement. Found in play for chests and for a placed enemy | tested |
| `+0x94` | u16 flags (bit 2 cleared by the reset) | read |
| `+0x98` | u32 flags: bit 0 is set by `f_80f27040` when the object is removed for good; the placement loader (`f_832e5b70`, **guess**) reads the Key64 flag by `[rec+0x88]` and syncs this bit with it. Not seen live | read |
| `+0xf0` | A quiet NaN from the reset | read |


### An actor job (`f_83af21f0`)

| Offset | Field | Sure |
|---|---|---|
| node `+0x10` | The actor (jobs 0 to 3; job 4's 0x20-byte node holds its functor here) | read |
| node `+0x22` | 1 | read |
| node `+0x28`, `+0x30` | The functor | read |
| functor `+0x0` | Its vtable; `+16` of it is the run | read |
| functor `+0x10` | −1 | read |
| functor `+0x15` | The actor's BaseProc ID's low byte | read |
| functor `+0x18` | The run's argument, set when the job is pushed: two floats and a pointer (**guess**: the frame's time step) | read |
| functor `+0x20` | A byte from the actor's settings | read |
| functor `+0x28` | The actor | read |

### The BaseProc manager (`[0x84eb0d90]`, 0x470 bytes)

| Offset | Field | Sure |
|---|---|---|
| `+0x80` | Its pool A, through `+0x10` ([jobs.md](jobs.md)) | read |
| `+0x3c8` | The request queues' mutex | read |
| `+0x3f8`, `+0x410`, `+0x428` | The three request queues' counts | read |

### LODParam (`engine__component__LODParam`, 0xd8 bytes)

The fields about updating. The rest: IsCharacter `+0x7c`, IsConstActor `+0x84`, UsePhysicsPause `+0x8c`,
UseActiveAsMoving `+0xa3`, CheckMainRigidBodyTrackingBone `+0x92`, IsNoAutoParentOnModelBind `+0xa1`,
IsCheckKinematicRigidBodyMove `+0xa0`, JudgeCalcSupportBoneWithCloth `+0xa2`, IgnoreProhibitionByXLink `+0x9c`,
IsAlwaysDisableInEventMember `+0x9e`. **read** (`f_83c0dd50`)

| Offset | Field | Sure |
|---|---|---|
| `+0x9f` | IsAutoPause | read |
| `+0x95`, `+0x93`, `+0x94` | DefaultForbidPushJobPreCalc, DefaultForbidPushJobPostCalc, DefaultForbidPushJobPostSensor | read |
| `+0x58` | DefaultForbidPushJobBlank | read |
| `+0x91` | AlwaysForbidPushJob | read |
| `+0x74` | ForbidPushJobDistance | read |
| `+0x78` | ForbidPushJobRadiusOutsideView | read |
| `+0x70` | ForbidPushJobBlank | read |
| `+0x3c` | ApplyScaleTypeToForbidPushJob | read |
| `+0x90` | AlwaysForbidCalcOnSleepJob | read |
| `+0x9b`, `+0x99`, `+0x9a` | ForbidPushJobPreCalc, ForbidPushJobPostCalc, ForbidPushJobPostSensor | read |
| `+0xa4` | UseAreaJudge | read |
| `+0x88`, `+0xa5` | UseOcclusionQuery, UseOcclusionQuerySphere ([culling.md](culling.md)) | read |
| `+0x38`, `+0x44`, `+0x40` | ActorRadiusScale, AreaNearDistance, AreaMiddle0DistanceScale | read |
| `+0x5c` | EnableCalcSkip | read |
| `+0x48` | CalcIntervalOnCalcSkipForce | read |
| `+0x6c` | ForbidCalcSkipInFrontViewDist | read |
| `+0x50`, `+0x96`, `+0x4c`, `+0x97` | CalcSkipRescuePriority, EnableRescueDistanceLimit, CalcSkipRescueDistance, EnableRescueInOutsideViewFar | read |
| `+0x68` | EnableDrawSkip | read |
| `+0x60`, `+0x9d`, `+0x64`, `+0x54`, `+0x80` | EnableClothSkip, IsAlwaysClothSkip, EnableClothSkipRescue, ClothSkipNearestPriority, IsClothSkipKeepAtInit | read |
| `+0x98` | EnableXLinkSkip | read |

### A shot record (0xf8 bytes, an element of a Shooter list entry)

| Offset | Field | Sure |
|---|---|---|
| `+0x18` | u64 request cell: a pointer to the request record (u16 state at its `+0`: 3 ready, 4 done or taken) | read |
| `+0xdb` | u8 last create result code | read |
| `+0xdc` | u8 requested flag | read |
| `+0xde` | u8 cleared at each shot | read |
| `+0xe0` | u8 pending flag | read |

### The Shooter component (vtable `0x84b6ff90`, 0x140 bytes) and its list entries

| Offset | Field | Sure |
|---|---|---|
| `+0x10` | u64 parameter object | read |
| `+0x18` | u64 owner actor | read |
| `+0x20` | u64 list of 0x38-byte entries | read |
| `+0x2c` | u32 entry count | read |
| `+0x130` | u32 cleared by slot 10 | read |
| `+0x139` | u8 flag | read |
| entry `+0x00` | u32 valid | read |
| entry `+0x08` | u32 count (or the u8 at `+0x34`) | read |
| entry `+0x10` | u64 array of 0xf8-byte records | read |
| entry `+0x18` | the projectile actor's name (a string object) | read |
| entry `+0x20` | u32 key hash | read |
| entry `+0x34`, `+0x36` | u8 count; u8 flags (bit 1 all shots of the entry made, bit 2 forwarded) | read |

### The foliage scene S (`[[module+0xf0]+0x338]`) and a cut slot (0x3c bytes)

| Offset | Field | Sure |
|---|---|---|
| module `+0xf0` | u64: null means cuts are refused; `[+0xf0]+0x338` is S | read |
| module `+0x141`, `+0x2b0` | Gate bytes read by the hit reaction `f_82c01120`: `+0x141` bit 0 set skips, `+0x2b0` bit 1 set skips; `[S+8]` bit 1 must be set | read |
| S `+0x20` | The cut queue: u32 capacity (a power of two, mask = capacity - 1) | read |
| S `+0x28` | u64 ring base: 16-byte entries, the item pointer then a sequence word | read |
| S `+0x30` | The consumer index (producers do not touch it) | read |
| S `+0x38` | u64 producer ticket | read |
| S `+0x48` | u64 base of the slot array (0x3c bytes a slot; a free slot's first u32 is the next free index) | read |
| S `+0x50` | u64 free-list head: low u32 the index (0xffffffff empty), high u32 a counter that rises by one per pop (an ABA guard) | read |
| slot `+0x00` | vec3 centre | read |
| slot `+0x0c` | f32 radius | read |
| slot `+0x10` | f32 (the producers set 0.3) | read |
| slot `+0x14` | u8 kind (kind << 2 in the oneshot node; 4 in `f_8305e390`; 0 in `f_8305e4c0`) | read |
| slot `+0x18`, `+0x24`, `+0x30` | Three vec3 swing points; the first float is the quiet NaN `0x7fc00000` when not given | read |

## Notes

- Job 0 sets the actor's time group before slot 51 runs: it fills its core's frame-time slot (`keeper+0x20+0x30*core`) with the step scaled by the group's rate and its inverse, scales slot 51's step by the group's rate over group 0's and keeps the ratio at `actor+0x2e8`; the group comes from slot 57 ([animation.md](animation.md)). **read**
- The component-offset map is on [ai.md](ai.md); the base slots 60, 61 and 63 also run AI units, and `f_8018dba0` is called from slot 51 as well as slot 52. `f_802ca820` (hot rank 64) has the shape of job 1's run (`f_800b3ce0`): another actor-job run. **read**

### The Shooter component

- **What it is.** `f_80c36cf0` is a plain helper (no vtable slot) of the actor's Shooter component: class vtable `0x84b6ff90`, found at `[actor+0x270]+0x3d8`, 0x140 bytes, made by `f_80e641d0`, registry name `ShooterRef` (the registry table's maker column sits one entry early: the maker printed next to `ShooterRef` builds a class labelled "shop" and the one next to `ShootableRef` builds this Shooter class). Three callers walk the component's shot list and call it once per record, first asking `f_83056970` for the record's state and calling only for state 1 and states 4 and up: `f_82ed07d0` (slot 10 of the class's vtable; call at 0x82ed114c), `f_800f36a0` (run from `BSA_Update` on `[comps+0x3d8]`; call at 0x800f37cc) and `f_809b2df0` (the same loop behind a guard, run from `f_809b2ff0`; call at 0x809b2f64). **read**
- **Arguments.** `x0` one shot record; `x1` the shooter context (its first 8 bytes the shooter actor; the callers store `[component+0x18]` there); `x2` the shot description: `+0` a pointer to a string object whose first word is the projectile actor's name (copied into a 0x40-byte local string), `+8` u32 the `Shootable_KeyHash` value, `+12` u32 (goes to the create call's `x4`), `+16` u8 the `Shootable_OverrideParamNum` value (the loops pass a constant 12 or a byte of the list entry). **read**
- **What it does.** It checks the record's request cell first: a non-null cell in state 4 is released (`f_80b4fbc0`) and `record+0xdc` cleared; a non-null cell in any other non-zero state returns 2 (a previous request still pending, nothing created). Otherwise it clears `record+0xe0` and `+0xde`, builds a creation request and calls `f_80392a70` with the manager, the name, the request, `record+0x18` (receives the request cell), `desc+12` and a small closure object (vtable `0x84b8e6c8`: slot 0 `f_83056e40` sets bit 0x10000 in the u32 at the creation info's `+0x14` when the shooter actor's byte at `+0x6a4` has bit 0, slot 3 `f_80c379a0` does nothing). The request holds the shooter actor's position (`+0x31c`), the identity rotation, unit scale, the shooter actor as creator (`request+0x80`), the Shooter type object `0x84e43cd8` as creator type (`request+0x88`) and two parameter overrides of 0xc8 bytes, `Shootable_KeyHash` (tag 0xc) and `Shootable_OverrideParamNum` (tag 0xa). The result code is 0 queued, 1 the manager refuses creates (its byte `+0x109` bit 1), 2 an empty name; it goes to `record+0xdb`, `record+0xdc` is set to 1 if not set, and the function returns 0, 1 or 3. **No velocity or aim is set here**: the created shootable has to read the two overrides and its creator itself (an inference; not read). **read**
- **Two places inside it,** the first instruction after the prologue (`0x80c36d24`: `x22` the shooter context, `x21` the description, the name `[[x21]]`) and the create call (`0x80c372fc`, returning to `0x80c37300`); the create function's own refusal path is at its start (byte `+0x109` bit 1 of the manager). Neither is a function.

### The foliage cut queue

- **The module and the queue.** `[0x84e42540]` is the foliage module and `[[module+0xf0]+0x338]` the scene S whose queue the cuts go to (the structures above). `f_80ba0800(module, cut)` returns 0 if `module+0xf0` is null or the free list is empty; does nothing and returns 1 when the radius at `cut+0x0c` is below 0.01; otherwise pops a free slot, copies the 0x3c bytes, sets `slot+0x10` to 0.3, pushes it with `f_80ba08f0(S+0x20, slot)` and returns 1. It ignores a failed push, so a full queue leaks the slot (no hand-back was seen). `f_80ba08f0` is a bounded multi-producer queue push on a sequence-numbered ring: take the next ticket, need the entry's sequence word to equal it, write the item, publish ticket + 1, call `f_85786920` (wakes the consumer) and return 1; a full ring returns 0 and a ticket race retries. **read**
- **Callers of `f_80ba0800`:** `f_829876a0` (slot 39 of the AI node `OneshotTryCutFoliage`, vtable `0x84a6a848`; position from two ports, the radius from a float port, the kind byte shifted left 2, three NaN points), `f_8305e390`, `f_8305e4c0` and `f_80458ab0`. The module argument is `[0x84e42540]` in all but `f_80458ab0`. **read**
- **The sword's cut producer** is not a function of its own: `0x82ec4880` is an instruction label inside `f_82ec3ef0` (the function spans `0x82ec3ef0` to `0x82ec4d00`). From that label the code halves the swing radius (times 0.75 first when the attack state is 2), reloads the module, checks `module+0xf0` and the 0.01 limit, pops a free slot itself (the same pop), fills all 0x3c bytes (centre from the actor's position, radius, 0.3, the kind byte, three swing points from the attack volume's start, middle and end, or NaN when the attack component is not in state 1 or 2) and pushes with `f_80ba08f0` (call at 0x82ec494c), without `f_80ba0800`. `f_82ec3ef0(C, &steps)` is called only by `GameActor_Calc51` (`f_82c3d740`, call at 0x82c3e428) with C = `[components+0x3b8]`, only when C is non-null and `C+0x22` has bit 1; inside it walks the actor's animation slots (the AS chain at `components+0x40`) and the attack component at `components+0x458` (state u32 at `+0x1e4`), and runs only for actors whose current state tests true in `f_82ec4d00` / `f_80b41a80`. **read** (the producer part)

### The engine's list and the actor list

- **The engine's circular list** (as read in `f_800d3db0`, the BaseProc manager's insert and remove, and `f_80389b00`, a walk of such a list): the head is its own sentinel; `+0x00` points to the last node and `+0x08` to the first (both the head itself when empty), `+0x10` is the u32 node count and `+0x14` the s32 offset of the node inside its object (an object is node minus that offset). A node is `{+0x00 previous, +0x08 next}`; insert writes the old last node's next and the head's last and adds one to the count; removal clears the node and counts down. Walk `+0x08` for the first-to-last order. **read**
- **The actor list** was not found in any function that walks it (searched: every function that loads a manager's `+0x118`, adds `0x670` or subtracts `0x538`), so these offsets are another project's live claim: `[0x84eb1888]` is the manager M, the head is `[M+0x118] + 0x670` with the count u32 at `+0x10` of it, the actor's node is at `actor+0x538` (so the head's offset word `+0x14` should read `0x538`) and the node's `+0x10` holds the actor pointer. The engine list's layout agrees with their "u32 at head + 0x10 is its length" and "owner = node - 0x538". **guess** (the offsets `0x118`, `0x670`, `0x538`, `+0x10`)
- **Two ways to move an actor, one sink.** `f_804e6580` (actor vtable slot `+0x218`; what the game's own node `ExecuteActorForceSetMtx` calls) and `f_80c8fd60` (what the host's bodies call) both end in `f_804e6630`. Slot `+0x218` takes the transform the caller wrote into `+0x31c..+0x34b` and sets bit 23 of `+0x4a8`; `f_80c8fd60` takes a row-major 3x4 matrix, never sets bit 23 and keeps a spare copy at `+0x358`. For an enemy's copy the game's own path (slot `+0x218`) is the one another project's runs proved; the host's is proved only for puppets. **read**

### From a placement to a running actor

1. The map's layout names each actor's archetype and instance; the layout's reader adds them to the actor registry
   ([maps.md](maps.md)). The placement's own fields (`f_805cf0e0`) carry its creation radius (ExtraCreateRadius,
   IsShortCreateRadiusInHeavy), IsForceActive, the Presence flag and its area culling. The ActorInfo row gives the
   create, delete, calc and display radii ([maps.md](maps.md), `f_805cb760`). **read** (the fields), **guess** (that the
   PlacementMgr creates and deletes by those radii)
2. A creation goes through the actor manager (`f_80392a70`) into the BaseProc manager's request queues; the six create
   and delete threads make the GameActor (`f_80ad3230`) and its components and jobs. So creating an actor costs no frame
   time on the BaseProcExecutors, but a burst of creations is bounded by those threads. **read** (the path), **guess**
   (when a created actor joins the frame)
3. Each frame, in stage 5 ([jobs.md](jobs.md)), the actor's jobs that are pushed run on the BaseProcExecutors. Which are
   pushed follows its LOD and calc-skip settings (pushing, distance, view, calc skipping).
4. Far or put to sleep, an actor can turn into its **PreActor**: a light stand-in kept for placed actors that are not
   created (the strings PreActor, `SleepToPreActor`, `Actor2PreActor`, `IsTurnToPreActor`, `UsePreActorRenderer`,
   `IsFarActor`, `MaxPreActors`, `UsePreActorAreaCulling`, and the job "PreActorRendererUpdateJob", `f_80d32160`).
   **guess**

### Link

Link is GameActor too, made by the ResidentActorMgr (`Player_Child` or `Player_Adult`) rather than by a map, so he
survives a change of map. The host knows him in two ways: in `patch_life` by the object `Actor_WriteLife` has in `x19`
(vtable `0x84b6c460`, its `+16` record named "Player"); in `patch_movement` by the GameActor vtable, then his components
(`+624`), their `+800` (the movement component, whose `+24` is the actor), and `hos_oot_is_player` on the address 0x1d50
before that component. **read**

That object is 0x1d20 bytes as `f_80d1fbb0` allocates it, 0x30 less than the 0x1d50 the host steps back. So the
component the host starts from is not inside it: the check holds because of where the two are allocated, one after the
other in the actor's heap, not because of a field. It works in the game; it would fail quietly (the cheats would see no
Link) if the allocation order changed. **guess** (from the sizes; not checked live)

### What an actor's update costs

From the code's size and what it calls, not measured (**guess** unless a measurement is cited):

- **Job 1, slot 52 (`f_82c3fab0`)** is the main game update: movement and the character controller, the skeleton's
  helper bones, cloth and look IK (`f_8018dba0`, 6,004 instructions), the player's state machines (`f_82ea25b0`,
  `f_82e44040`, `f_80609d00`, 3,500–5,100 each), NPC talk, the engine's slot 54 (6,236). [jobs.md](jobs.md) measured its
  job (`f_800b3ce0`) at 12% of the BaseProcExecutors' running time and 18% of the frame's critical path in the Temple of
  Time. **tested** (that measurement, [jobs.md](jobs.md))
- **Physics** runs as a BaseProc of its own ("PhysicsSystemBaseProc", [jobs.md](jobs.md)), Havok's tasks on the same
  executors: the narrow phase (`f_8191ee00`, 14% of their running time) and cloth (`f_8016b320`, which runs "TtCloth",
  9%). **tested** (the shares, [jobs.md](jobs.md)); each actor's physics component (PhysicsRef) feeding that world is
  a **guess**
- **AI:** each actor with AIInfo runs its `.ainb` graphs; the AI groups run in their own job ("AIGroupParallelCalc",
  [jobs.md](jobs.md)), and Havok AI's character step (`f_820da77c`) is the longest single piece of the critical path.
- **Animation:** the AS component plays `AS/<name>.asb` (`f_803fbc80`, `f_8071f0a0`) with its animation events
  (`AnimationEvent/AsNode/…baev`, `f_803fb0c0`); ASOptimize is a component of its own. Where AS's update runs (which
  job) was not traced.
- **How many run:** the Forest Temple's layouts place 3,213 actors ([maps.md](maps.md)), 2,236 of them room pieces with
  only a model and a static body. Every one is a GameActor with five jobs; how many jobs are pushed a frame depends on
  the LOD settings, which for a room piece likely forbid them all. Counting the pushed jobs live is the next step.

### The Death component and a break

- **The component.** Made by `f_809e5480` (0xe8 bytes), at `[actor+0x270]+0x1c0`. The flags at `+0x20`: bit 13 armed, bit 14 a death was requested, bits 1 to 3 the stage (2, 4, 6, up to 0xe). `+0x88` to `+0x94` hold a deferred request (byte `+0x8c`, a cookie `0x613b0000` at `+0x90`, the reason at `+0x94`) that the step consumes. **read**
- **Who asks.** A pot's AI graph has three triggers, all ending in the one-shot `OneShotDeathRequestDeath` with its reason unwired (so 10): ground contact while thrown or falling, its own thrown-attack sensor hitting something (unless the hit actor carries a tag), and a hit from a tagged attacker. It never reads the life. A crate's graph has only the contact trigger, so a sword or bomb break of a crate comes from the Life step: once the life cell (`[life+0x1c10]+8`) is at or below 0, or the cell is null, the step calls `f_803c8bb0(comps[+0x1c0], 10, 0, comps[+0x1d8] == 0)` in the same step in which the compare-and-swap that took the life to 0 ran, and only while the death flags are idle and armed (`(flags & 0x6000) == 0x2000` and `(flags & 0xe) == 0`). `+0x1d18` of the Life component has its bit 12 cleared every step; its bits 3 and 11 are early exits whose meaning was not resolved. "Dead" is an intra-frame call into the Death component, not a message and not a flag the AI reads. **read**
- **What a break does.** The LifeDepleted row of the Default table, which a pot's own table inherits, has the drop on, the effect on, the respawn flag on and IsWaitForSignal off; the row for reason 9 has the effect on and no drop flag and no respawn flag, which may mean a break without loot or a save write (**guess**). The actor stays at state 4 (`+0x2c`) until a delete is requested; `f_800c6490` sets bit 16 of `+0x30` and queues it, and the states 7 to 11 mean it is leaving. `f_800c6490(actor, 0)` alone runs no death procedure: no drop, no effect, no Key64 write. A thrown pot or a sensor hit probably breaks with its life still 1, because that path writes no life (**guess**). A store of 0 into the life cell is expected to make the next step take the at-or-below-0 branch and ask with reason 10, which gives the full result (drop, effect, Key64 write, delete) (**guess**, not run). **read**
- **What stays broken.** In the data, 511 of 564 placed pots and 44 of 52 placed crates have a placement hash that is a Key64 flag of the game's own save (reset type 88, bits 8, 16 and 64, and save file 0), written by the death procedure above. The `_Respawn` and `_Dream` variants are unkeyed (their settings say AlwaysRespawn and their death tables do not set the flag), and nine placements of one base pot are unkeyed, so the bit is per placed object. Whether a save reload restores the flags (bit 8 among the reset bits that `OnLoadGameSaveData` asks for) is a guess. **read** (the data), **guess** (the reload)
- **Telling a breakable from an enemy.** The component slots (with the rest in [ai.md](ai.md)): Destruction `+0xf0`, Death `+0x1c0`, Drop `+0x1c8`, Life `+0x2b8`, Liftable `+0x2c0`, Player `+0x358`, Target `+0x418`. A breakable has Destruction, Life, Death and Drop and no Target and no Player component: of 92 packs that have both Destruction and Life, the 17 enemy and boss ones have a Target and the 75 others have none, and Link and the pouch player have no Destruction. **read**
- **The registry's maker column is one entry early here too.** In the game's registry `f_8122db20` the makers `f_809e5480` (Death), `f_80d1fbb0` (Life), `f_80c84f80` (Drop) and `f_809bfe60` (Liftable) are listed against the entry before the component they make, and in the engine's registry `f_81209b40` so is `f_80c6dc00` (Destruction), as the Shooter bullet above found for its entries. The slots were cross-checked against the Life step, the Player and Target uses and the field at `+0x58` of the Destruction object. **read**
- **Not known.** The frames from request to delete and what the standard procedure does at its end; the two death procedure hashes `321054246` and `3265626599` and how they differ; which object holds the fracture pieces; the default of IsSetGmdRespawnFlagToFalse (inferred true, never read: no table sets it true and eight set it false); which events clear the reset bits of the keyed flags; and whether calling `f_803c8bb0` from another thread than the actor's is safe. A run that breaks a pot with a sword and logs `+0x2c`, bit 16 of `+0x30`, the life cell, `[death+0x20]` and the Key64 flag for 60 frames would settle most of it: expected the life to go 1 to 0 and the death flags to read `0x4000` in the same frame, the stage bits to rise, the state to go from 4 to 7 or above, and the Key64 flag to read 1.

## Open questions

- The actor list's offsets: in a field read `[0x84eb1888]` = M and `[M+0x118]` = L; the u32 at `L+0x680` should be the actor count (changing with the room), the s32 at `L+0x684` should read `0x538`, and nodes at `L+0x670` walked by `+0x08` should have owners `+0x10` = node - `0x538`. Read `[actor+0x3d8]+0x88` of a pot or a chest (not all ones) and of a rupee dropped from a cut bush (all ones). Place a field enemy with each of slot `+0x218` and `f_80c8fd60`: does it stay (another project found only slot `+0x218` does)?
- The Shooter and the foliage cuts: at the hook point `0x80c36d24` of a slingshot shot print `[[x2]]` as a C string and `[x1]` (expect Link and the name of the created actor), and read the created actor's velocity fields one frame later to see who sets them. In a field scene read `[0x84e42540]`, `[module+0xf0]` and `[[module+0xf0]+0x338]`: expected non-null. During a sword swing log the byte `C+0x22` (C = `[comps+0x3b8]`) and the state at `[comps+0x458]+0x1e4`; expected bit 1 set and state 1 or 2 when the three swing points are not NaN. Which component C and `[comps+0x458]` are (a swing or attack tracker is the guess); who creates the foliage module pointer and reads the queue (the renderer side); what `module+0x141` and `+0x2b0` mean; who calls `f_8305e390` and `f_8305e4c0` (function pointers, no vtable cell found); how a created shootable gets its velocity.
- Which job is which phase (PreCalc, PostCalc, PostSensor, PostUpdateMatrix, and a "Blank" one?), and the order the
  five run in within stage 5.
- How many actors exist and how many jobs are pushed a frame in a busy scene (Kokiri Forest, Hyrule Field): a live count
  of the BaseProc manager's lists, or of the five job vtables' runs, would say how much the frame depends on actor count.
- Where the LOD settings are read each frame (the code that checks `ForbidPushJob*` and the distances), and what calc
  skipping does to an actor's update (every Nth frame, or interpolated).
- Who reads `actor+0x3d8` and what its `+0x58` object is (LODParam or the calc skip's InitParameters).
- What slots 50, 51, 53, 55 and 56 do, and where AS and the AI graphs are updated.
- The PreActor: what it holds, when an actor becomes one and back, and what "PreActorRendererUpdateJob" draws.
- Whether every maker in the component registry tables is listed one entry early. It is for Shooter (see *The Shooter component*) and for Death, Life, Drop, Liftable and Destruction (see *The Death component and a break*); the engine's makers on [animation.md](animation.md) were not rechecked one by one.
- What the six create and delete threads' core masks are (the settings at `+0x60` to `+0x74` are filled at run time).
