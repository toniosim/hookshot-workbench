# The world's environment

The world manager (`WorldMgr`, the game's `wm::` code) and what it drives: the time of day, the sun and the moon, the
weather, the wind and the clouds, the environment palettes that set the light, fog and sky for each hour and weather, and
the parameter files they come from. Looked at in November 2026 by static analysis of the binary, to see how the game
decides that the sun is visible and what it changes when the sun is hidden (the open question in
[culling.md](culling.md) under *The sun*), and where the fog and exposure that LS's renderer has struggled with
are set.

**LS code:** `host/hos_main.c` (`oot_set_time`, the debug tools' time of day),
the fog and exposure factors that were in `gpu/vk/vk_shader.cpp` (`oot_visual`) and
`oot_visual_workaround.h` until HS #2042 removed them, `gpu/vk/vk_replay.cpp` (the samples-passed reports, which
the sun's haze followed: PR #487), `gpu/vk/vk_memory.cpp` (the exposure meter's readback page)
**See also:** [events.md](events.md) (`ExecuteWmSetTime` and the world manager's holder), [frame-time.md](frame-time.md)
(`f_803edf70`, the time of day above 60 fps), [rendering.md](rendering.md) (the sky's tables, the froxel fog, the
lighting composite), [culling.md](culling.md) (occlusion queries), [jobs.md](jobs.md), `docs/design.md`

## In short

1. **One world manager, a request block each frame.** Script nodes (`ExecuteWm*`, `HoldWm*`, `OneShotWm*`) don't change
   the world directly: each calls a setter on the world manager that, under its lock, sets a bit in a 64-bit request word
   and writes its values into the request block being filled. Once a frame `WorldMgr_Calc` (`f_803ec480`, run as a job)
   swaps the two blocks, carries the persistent bits over to the new one, clears the one-frame bits, and runs the clock,
   the environment's updates and the sky on the block it took. **read**
2. **The time of day is the clock's.** The clock (`[WorldMgr+0x510]`) holds the seconds of the day and the day; it is
   stepped by `f_803edf70` ([frame-time.md](frame-time.md)) at the frame's step times two rate factors, and stands still
   while one request bit (`0x800000`) or a manager flag is set. `ExecuteWmSetTime` hands it `TimeHour * 3600 + TimeMin *
   60`. **read**
3. **The sun model's visibility is not an occlusion result.** The environment object (`[WorldMgr+0x578]`) keeps the sun
   and the moon's state in one flag word. "The sun is appearing" is a day/night value; "the sun model is visible" is a copy
   of it, cleared while `HoldWmSunMoonInvisible` or `ExecuteWmSetSunMoonModelInvisibleForTimeline` is in force, and both
   are cleared by a flag in the update's arguments. Nothing in that update reads a query count. The lens flare has its own
   enable bit: a time window, unless `ExecuteWmSetDisableLensFlare` is in force. **read**
4. **The sun's occlusion is measured on the GPU.** A compute program named `effect_sun_occlusion_cs` binds the reduced
   depth (`cReducedBuffer`), its parameters and an `Occlusion` buffer; the cloud layers have a `SunOccBufSize`, the
   volumetric clouds a `SunOccChkSize`, and the lens flare's elements `IsEnableOccludedScaling`, `IsEnableOccludedDec` and
   `IsEnableOccludedAlpha`. No CPU reader of that buffer was found. **read** (the names), **guess** (that the GPU reads it)
   So what PR #487 saw (the haze brightening when the counts dropped) most likely went through what the counts cull (see
   [Notes](#notes)), not through a sun query. **guess**
5. **`SkyOcclusion*`, `InCaveOcclusion*` and `InDoor*` are sound parameters**, volumes and filters for the ambient and
   weather sounds, not graphics. **read**
6. **The light, fog and sky come from palettes.** An environment palette (`ResEnvPalette`) sets exposure, the lights,
   the volume fog, white balance, bloom, the sky's scattering and the plain fog; a time table picks palettes by the hour
   and the weather; fixed, area-unique, demo and indoor palettes override parts of it. All are `.gyml` files under
   `Work/WorldMgr/`, packed in `Pack/EnvPalette.pack`. **read**

## The world manager

The world manager is `[0x84e9eab0]` (the holder `0x84c9e898` that [events.md](events.md) documents is the address of that
variable). Its setters all have one shape: take the lock at `+0x490`, pick the request block being filled
(`+0xde8 + index * 0x11a0`, the index at `+0x3128`), set a bit in its first word and store any values, unlock.

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_803ec2a0` | `WorldMgr_CalcJob` | A job delegate's invoke (slot 2 of the vtable at `0x84c14638`): copies the frame's arguments from the delegate's block (`delegate+24`) to the stack, files `delegate+40` in the running thread's slot of a six-entry table while it runs (cleared after), and calls `f_803ec480` with the world manager `[0x84e9eab0]` (read through `0x84c9e898`) and those arguments | read |
| `f_803ec480` | `WorldMgr_Calc(world, args)` | The world manager's frame. It tries the lock at `+0x4b0` and does nothing that frame when it fails, moves `+0x4d8` into `+0x4d4`, calls `f_803edb40` (the WorldParam check), then under the lock at `+0x490` flips the index at `+0x3128`, copies the block it took into the new one and keeps only the persistent bits (the mask `0xffffe07edfd80004`). It sets the clock's rate (below), calls `f_803edf70` (the time of day) with the taken block, then `f_803e9130` and `f_803eb170` on the environment object (`+0x578`), and `f_803ed930` when `+0x4d1` bit 2 is set. It copies request bit 20 into `+0x4d0` bit 11. A non-negative word at `+0x38d8` is applied as a pending hour (`f_80f0e640`, flag 0, day -1) and stops the clock | read |
| `f_803edb40` | `WorldMgr_LoadWorldParam` | The WorldParam check `WorldMgr_Calc` makes every frame: formats `Work/WorldMgr/WorldParam/%s.game__wm__WorldParam.gyml` and, when the name differs from the current one (`+0x598`), drops the old environment object and makes the new one (with `f_81216060`), stored at `+0x578` | read |
| `f_803eed30` | `WorldParam_Params` | Declares the WorldParam's fields: `WorldType`, the base palettes (`BasePalette_Bluesky`, `BasePalette_Cloudy`), the wind's limits, `IsSolarMotion`, `SunRiseAzimuth`, `SunElevation`, `MoonElevation`, `SunriseHoure`/`SunriseMin`, `SunsetHoure`/`SunsetMin`, `IsExistSunMoon`, `SunMoonDist`, `SunSize`, `MoonSize`, `CloudShadowOnOff`, the volume fog's start and end distances, noise and resolution scales (`VolumeFogResScaleConsole`, `VolumeFogResScaleHandheld`), and others | read |
| `f_834722f0` | `WorldMgr_RequestImmTrans` | `ExecuteWmRequestImmTrans`: sets bit 0 of `+0x4d4`, which the frame passes on as the environment update's "immediate" flag | read |
| `f_83472300` | `WorldMgr_SetCloudShape(world, …)` | `ExecuteWmSetCloudShape`: request bit `0x1`, the shape in the block's `+0xc`, `+0x10`, `+0x14` | read |
| `f_834723b0` | `WorldMgr_SetCloudShadowPos(world, x, y)` | `ExecuteWmSetCloudShadowPos`: request bit `0x2`, the position at `+0x18`, `+0x1c` | read |
| `f_83473380` | `WorldMgr_SetWeather(world, name, …)` | `HoldWmSetWeather`: copies the name (a 256-byte string) and the integer argument into the block being filled at `+0x670`; it sets no request bit itself. `f_83473830(world, w)` calls it with the empty string (`HoldWmSetWeatherDefault`) | guess |
| `f_83473840` | `WorldMgr_SetEnvEffect` | `HoldWmSetEnvEffect` and `HoldWmSetForceDefaultEnvPalette`: request bit `0x800` and a value at `+0x9e4` | read |
| `f_834738c0` | `WorldMgr_HoldSunMoonInvisible` | `HoldWmSunMoonInvisible`: request bit `0x40000` (one frame, so the hold sets it every frame) | read |
| `f_83473970` | `WorldMgr_SetEnvPalette` | `ExecuteWmSetEnvPaletteForTimeline` and `…ForFlowchart`: the palette names at `+0xa18` and `+0xb38` | read |
| `f_83473b80` | `WorldMgr_ResetEnvPalette(world, flag)` | `ExecuteWmResetEnvPaletteForFlowchart` (and the OnLeave of `ExecuteWmSetEnvPaletteForTimeline`, slot 31): clears the two palette names at `+0xa18` and `+0xb38`; when `flag` is 1 it also sets request bit `0x200000` | read |
| `f_83474560` | `WorldMgr_SetCloudShadowOff` | `ExecuteWmSetCloudShadowOffForTimeline`: request bit `0x400000`; the sky then uses 0 for the cloud shadow's rate | read |
| `f_83474620` | `WorldMgr_SetWorldShadow` | `ExecuteWmSetWorldShadowForTimeline`: a value at `+0x112c` | read |
| `f_834747e0` | `WorldMgr_SetSunMoonModelInvisible` | `ExecuteWmSetSunMoonModelInvisibleForTimeline` (its slot 29): request bit `0x8000000`, persistent | read |
| `f_83474840` | `WorldMgr_ClearSunMoonModelInvisible` | Clears `0x8000000`; called from the same node's slot 31 (`f_828b0d00`) | read |
| `f_834748a0` | `WorldMgr_SetDisableLensFlare` | `ExecuteWmSetDisableLensFlare`: request bit `0x1000000000`, persistent | read |
| `f_83474900` | `WorldMgr_ResetDisableLensFlare` | `ExecuteWmResetDisableLensFlare`: clears it | read |
| `f_834749d0` | `WorldMgr_SetWorldBaseParam` | `ExecuteWmSetWorldBaseParamForTimeline`: request bit `0x1000000`, a value at `+0x10e0` | read |
| `f_83474f10` | `WorldMgr_SetLunarAge` | `ExecuteWmSetLunarAgeForTimeline`: the lunar age at `+0x10fc` | read |
| `f_83474fb0` | `WorldMgr_SetWeatherTransition` | `ExecuteWmSetWeatherTransitionForTimeline` and `OneShotWmSetWeatherForFlowchart`: request bit `0x10000000`, values at `+0x10d0` and `+0xfb0` | read |
| `f_83475120` | `WorldMgr_ResetWeather` | `OneShotWmResetWeatherForFlowchart`: request bit `0x20000000` | read |
| `f_83475190` | `WorldMgr_SetWind` | `ExecuteWmSetWindForTimeline`, `…ForFlowchart` and the update of `ExecuteWmSetWindTransitionForTimeline`: request bits `0x40000000` and `0x100000000`, the wind vector at `+0x1100 … +0x1108`. `ExecuteWmResetWindForFlowchart` (and the OnLeave of the timeline nodes) goes to `f_83475250`, which clears `0x40000000` | read |
| `f_834752d0` | `WorldMgr_SetUsePlayerPos` | `OneShotWmSetUsePlayerPosForEvent`: request bit `0x100000` | read |
| `f_80c91790` | `WorldMgr_SetSunActor(world, actor)` | Points the actor link at `+0x528` at the sun's actor (or releases it for 0) | read |
| `f_80c91830` | `WorldMgr_SetMoonActor(world, actor)` | The same for the moon, `+0x540` | read |

The world manager's setter for the time, `f_834722d0`, has its row in [events.md](events.md).

## The script nodes

The nodes' own functions (their vtable slots: 29 for an Execute node's run, 39 for a Query or OneShot node's, 40 for a
Hold node's; [master-quest.md](master-quest.md) has the layout). Most nodes are a thin call into a setter above.

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_828b0e80` | `ExecuteWmSetTime_Run` | Calls `f_834722d0` with `TimeHour * 3600 + TimeMin * 60` (its inputs at `node+0x20` and `+0x28`) on `[[0x84c9e898]]` | read |
| `f_828b0cf0` | `ExecuteWmSetSunMoonModelInvisibleForTimeline_Run` | Calls `f_834747e0` | read |
| `f_8320b6d0` | `HoldWmSunMoonInvisible_Hold` | While its input is 1, calls `f_834738c0` | read |
| `f_80c916f0` | `OneShotWmSetSunActor_Run` | With `IsSun` set, gives the world manager its actor as the sun (`f_80c91790`), otherwise as the moon (`f_80c91830`); with no actor, releases it | read |
| `f_82a3faf0` | `QueryGetSunDir_Evaluate` | Outputs `SunDir`, `IsSunAppearing` and `IsSunModelVisible` from the environment object's slots `+0x88`, `+0x70` and `+0x78` | read |
| `f_82a373f0` | `QueryGetMoonDir_Evaluate` | The moon's outputs `MoonDir`, `IsMoonAppearing`, `LunarAge` and `IsMoonModelVisible`, from the environment object's slots `+0xa8`, `+0x90`, `+0xb0` and `+0x98` (their getters below) | read |
| `f_82b22d10` | `QueryWorldGetCurrentTime_Evaluate` | Splits the environment's seconds of the day (slot `+0x30`) into its outputs | read |
| `f_83209860` | `HoldWmGetTimeDiv_Hold` | Outputs `Day` (the time division is 0) and `Night` (it is 1), from slot `+0x38` | read |
| `f_82b22b40` | `QueryWeather_Evaluate` | Outputs the weather (slot `+0xf0`), 0 when it is above 4 | read |

## The environment object

`[WorldMgr+0x578]`, made from the WorldParam. At least four vtables carry the same getters (`0x84c12040`, `0x84c123a0`,
`0x84c12610` and `0x84c12880`, in slots `+0x70` and `+0x78`); the start of each is a **guess**, and the first two differ at `+0x220`.

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_803eb170` | `WorldEnv_Update(env, args, block)` | Builds the sky's arguments, calls the object's `+0x220` with the block, then `f_803ce120` on `env+0x10` | read |
| `f_803ce120` | `WorldEnv_UpdateSunMoon(sky, args, block)` | The sun, moon, sky and clouds' state from the block (about 4,100 instructions). The flag word at `sky+0x28` (`env+0x38`): its bits as in *Structures*. Among what it reads: request bits `0x40000` and `0x8000000` (the models hidden), `0x1000000000` (no lens flare), `0x400000` (no cloud shadow: the rate at `+0xb70` is 0), `0x2` (the cloud shadow's position), `0x10000000` and `0x20000000` (the weather) | read |
| `f_803e9130` | `WorldEnv_UpdateMain(env, args, block)` | The environment's other update: looks up an entry named `Main`, takes the wind vector from the block when request bit `0x40000000` is set, and reads request bits `0x2000000000` and `0x4000000000` | read |
| `f_83444700` | `WorldEnv_IsSunAppearing` | Slot `+0x70`: bit 4 of `env+0x38` | read |
| `f_83444710` | `WorldEnv_IsSunModelVisible` | Slot `+0x78`: bit 7 of `env+0x38` | read |
| `f_83444730` | `WorldEnv_SunDir` | Slot `+0x88`: the sun's direction, `env+0xb0c` | read |
| `f_83444740` | `WorldEnv_IsMoonAppearing` | Slot `+0x90`: bit 5 of `env+0x38` | read |
| `f_83444750` | `WorldEnv_IsMoonModelVisible` | Slot `+0x98`: bit 8 (bit 0 of `env+0x39`) | read |
| `f_83444770` | `WorldEnv_MoonDir` | Slot `+0xa8`: `env+0xb24` | read |
| `f_83444010` | `WorldEnv_LunarAge` | Slot `+0xb0`: the clock's `+0x68` when it is not negative; otherwise (day + 1 before noon, day + 2 after, mod 8) from the clock's current day block | read |
| `f_802c8de0` | `WorldEnv_SecondsOfDay` | Slot `+0x30`: the clock's (`env+0xd48`) seconds of the day, at `+0x28`, or at `+0x58` when the clock's `+9` bit 1 is set (a second time: `OneShotRequestVisualOnlyTime` is a likely user, **guess**) | read |
| `f_8006cd50` | `WorldEnv_TimeDivision` | Slot `+0x38`: the clock's `+0x40` (0 day, 1 night) | read |

## The clock

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_80f0e640` | `Clock_SetTime(clock, seconds, flag, day)` | What `f_834722d0` calls with `(seconds, 1, -1)`: stores the seconds and the day at `+0x48` and `+0x4c` and sets bit 1 (and bit 2, when `flag` bit 0 is set, otherwise clears it) of `+8`, then builds a default request block on the stack and calls `f_803edf70` on the clock with a zero step, so the set takes hold at once, and sets bit 3 of `+8` (the next step clears it) | read |
| `f_83472280` | `WorldMgr_ReadTime(world)` | Returns (hidden result pointer x8) a 24-byte time snapshot: vtable pointer, then one u64 = seconds of the day (low) and day (high) of the clock block at `clock+0x20` (or `clock+0x50` while bit 0x200 of `clock+8` is set), then that block's u32 at `+0x10`; empty snapshot when `[world+0x510]` is null. Callers `f_803ff420`, `f_80401980` | read |
| `f_83445090` | `Clock_LoadFromGameData(clock)` | Sets bit 8 of `clock+8`, reads the saved seconds and day from the game-data time object `[world+0x508]+8`, calls `Clock_SetTime(seconds, 0, saved day)`, stages the minute words, sets bit 0. The save-load / load-sequence set. Its only caller is `f_83472050`. (it was first guessed to be a visual-only time request; it loads the saved time) | read |
| `f_83472050` | `WorldMgr_ApplyGameDataState(world)` | Takes the lock at `+0x4b0`, copies the saved environment values (three floats) into `world+0xdb8…` when they are non-zero (and sets bits 7 and 8 of `world+0x4d0`), calls `f_83445090` when the clock exists, then lets the four sub-objects at `+0x558…+0x570` refresh (slot 57) and clears request bit 23 of the block being filled. Callers: `f_832f8690`, `f_830513c0`. Read in outline: the control flow; the offsets are as the lifted code prints them | read |
| `f_832f8690` | `SeqOneShotOnloadGameSaveDataWorldMgr_Calc` | The node calc (vtable `0x84bd4558`, slot 39): after a save is loaded, applies the saved state to the world manager through `f_83472050` (argument: `[[0x84c9e898]]`), i.e. the saved time goes into the clock; node done | read |
| `f_828d7e20` | `OneShotAutoPlacementMgrSetIsTimeElapsedToNightByOcarinaSunSong_Calc` | Stores 72000 (20:00) into the auto-placement manager entry 0x23 at `+116`; node done. Run only by the Sun's Song flow | read |
| `f_828b0ec0` | `ExecuteWmSetTime_OnUpdate` | Marks the node finished (OnEnter `f_828b0e80` did the set) | read |
| `f_828b1060` | `ExecuteWmSetTimeTransitionForTimeline_OnUpdate` | The timeline's time transition: from start hour/minute to end hour/minute by the node's progress, through `f_83474aa0` into the world's request block (bit 0x2000000, times at block `+0x10e4…`); never calls Clock_SetTime. OnLeave `f_828b11a0` -> `f_83474e10`. Read in outline: the two functions and their stores | read |
| `f_829428b0` | `OneShotRequestVisualOnlyTime_Calc` | Hour*3600 + minute*60 + second from the node's inputs plus a float (a fade time), into `f_83474f00` -> `f_83445140`: that stores the target seconds at `clock+0x6c`, a flag at `+0x74` (0 while a fade runs, 1 when the time is about 0) and a rate (a constant divided by the float) at `+0x78`; not Clock_SetTime | read |
| `f_8347c020` | `GameData_ClockHeld` | A game-data lookup by a constant hash that returns a bit; `f_803edf70` calls it right after cutting the frame's seconds (`+60`) and stores 0 there when it is true, and takes the seconds from game data (`f_8347c450`) while it holds. So the clock stands while the bit holds. The name is a guess: which game-data bool it is, and what in a save holds it, is not known | read |

`f_803edf70`, which steps the seconds of the day (`+40`) and the day (`+44`), has its row in [frame-time.md](frame-time.md).
It gets the taken request block and tests request bits `0x1000000` and `0x2000000`. The rate it steps by is set in
`WorldMgr_Calc`: the frame's step times `+0x3768` and times `+0x376c` (kept at `+0xde0`), or 0 while request bit
`0x800000` or `+0x4d0` bit 13 is set; `+0x4d0` bit 14 says the clock is stopped. **read** (who sets `0x800000` was not found)

## Palettes and parameter files

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_80fd3370` | `WmResMgr_LoadPacks` | `wm::ResMgr`: loads `Pack/EnvPalette.pack` and `Pack/DemoPalette.pack` and sorts their files by type (`ResEnvPalette`, `ResFixedEnvPaletteParam`, `ResEnvPaletteTimeTable`, `ResEnvPaletteAreaUnique`, `ResWeatherInfluenceParam`) | read |
| `f_81215080` | `ResEnvPalette_Load` | Formats `Work/WorldMgr/ResEnvPalette/%s.game__wm__ResEnvPalette.gyml` | read |
| `f_8119a030` | `ResEnvPaletteTimeTable_Load` | Formats `Work/WorldMgr/ResEnvPaletteTimeTable/%s.game__wm__ResEnvPaletteTimeTable.gyml` | read |
| `f_81197aa0` | `ResEnvPaletteAreaUnique_Load` | Formats `Work/WorldMgr/ResEnvPaletteAreaUnique/%s.game__wm__ResEnvPaletteAreaUnique.gyml` | read |
| `f_8343ba70` | `ResFixedEnvPalette_Load` | Formats `Work/WorldMgr/ResFixedEnvPalette/%s.game__wm__ResFixedEnvPaletteParam.gyml` | read |
| `f_811f6b40` | `ResDemoPalette_Load` | Formats `Work/WorldMgr/ResDemoPalette/%s.game__wm__ResDemoPalette.gyml` (the cutscenes' palettes) | read |
| `f_811971a0` | `ResWeatherInfluenceParam_Load` | Formats `Work/WorldMgr/ResWeatherInfluenceParam/%s.game__wm__ResWeatherInfluenceParam.gyml` | read |
| `f_82849ab0` | `VolumeFogAreaParam_Load` | Formats `Work/System/GameGraphics/VolumeFogAreaParam/%s.game__gfx__VolumeFogAreaParam.gyml` (its `FogParams`); `ExecuteRegisterVolumeFogArea` registers such areas | read |
| `f_83452160` | `ResEnvPalette_Params` | Declares an environment palette's fields: `ExposureValue` and its corrections, the lights' intensities (character, sub-character, field-object, specular), the bake and sky light scales, the hemisphere light, the volume fog block (`VolumeFogIsEnabled`, `VolumeFogMainLightScale`, the probe light scales, `VolumeFogEnableFog1`/`2`), white balance, bloom, caustics, the sky's sun colour and scattering (`SkyRParam_rayleigh_amplifier`, `SkyRParam_mie_*`), the scatter fog (`SfParam_*`), `CloudShadowRate`, `RainExposureRate`, `HumidityWetRatio`, the plain fog (`FogColor`, `FogStart`, `FogEnd`, `AfParam_attenuationForGrd`/`ForSky`), `AmbientIntensity` and the cube map's ambient and fog | read |
| `f_83451e40` | `ResEnvPalette_VolumeFogParams` | The palette's two volume fog blocks, `VolumeFogParams1` and `VolumeFogParams2` (`game__wm__ResEnvPalette_VolumeFog`) | read |
| `f_83466620` | `FixedEnvPalette_Params` | Fields that each come with an `IsOverwrite…` switch: exposure, character light, specular, hemisphere light, the volume fog's scales and densities (`VF…`), white balance, bloom, caustics, wetness | read |
| `f_834477e0` | `DemoPalette_Params` | A cutscene palette's fields: a fixed sun direction (`IsDirectSunAzimuth`, `DirectSunElevation`, …), fog and volume fog overrides, exposure compensation, character lights, local depth shadow, vignetting, Navi's light, bloom | read |
| `f_831d2870` | `VolumeFogAreaParam_Params` | Declares the fields of `game__gfx__VolumeFogAreaParam` (vtable `0x84ba8d50`): `NoiseParams` (`game__gfx__VolumeFogNoiseParam`) and `Fog1Params`/`Fog2Params` (`game__gfx__VolumeFogCommonParam`) | read |

`Work/WorldMgr/WorldParam/MainField.game__wm__WorldParam.gyml` and `Viewer.game__wm__WorldParam.gyml` are named outright,
as are `ResEnvPalette/Default` and `ResEnvPaletteTimeTable/MainField_Bluesky`; `PrequelPrCloud/%03d` and
`PrequelDofMgrParam/000` are the other `Work/WorldMgr/` files.

## The sky, the sun's occlusion and the lens flare

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_80b6bdd0` | `SkyScattering_Bind` | Uses the atmosphere tables' names: `cTexTransmittance`, `cTexDeltaSR`, `cTexDeltaSM`, `cTexIrradiance`, `cTexDeltaE`, `cTexDeltaJ`, `cTexInscatter`, `cTexBakedInscatter`, `cTexBakedIrradiance`, `cTexFogDensity`, `cTexCloud`: the sky's precomputed scattering ([rendering.md](rendering.md): `Single Scattering Rayleigh`/`Mie`) | read |
| `f_80b673a0` | `SceneAnalyze_Bind` | Uses `ShadowAnalyzeParam`/`Result`, `SkyAnalyzeParam`, `ProbeAnalyzeParam`/`Result`, `InnerMaskAnalyzeParam`/`Result`, `SceneShadingAnalyzeInfo`, `cTexBakedInscatter` and `cQuatDepth`: a GPU analysis of the scene from the quarter-size depth | read |
| `f_80ddaa40` | `SunOcclusion_Construct` | Makes a 0x40-byte object (vtable `0x84baa188`) that `f_80ddab00` keeps at `[gfx+0xb50]` | read |
| `f_80ecdd80` | `SunOcclusion_Init` | Finds the program `effect_sun_occlusion_cs` (the name at `0x84baa198`) and makes two small buffers in each 0x118-byte entry | read |
| `f_80b693b0` | `SunOcclusion_BindProgram` | Finds `effect_sun_occlusion_cs` and binds `cReducedBuffer` (a texture), `cParameters` and `Occlusion` (a buffer) | read |
| `f_834d13c0` | `CloudParam_Params` | The cloud's own fields, class `agl__CloudParam` (vtable `0x84c1b898`): `IsEnable`, `IsDrawReduceBuffer`, `IsDisableFarClip`, `IsDisableDepthTest`, `IsSyncSunPosition`, `DrawOrder`, `CloudColorScale`, `FogColor`/`Near`/`Far`, `AttenuationForSky`, `SunOccBufSize`; its slot 2 (`f_834d1bc0`) declares `Textures` and `Layers` | read |
| `f_834cb420` | `CloudLayerParam_Params` | One cloud layer's fields, class `agl__CloudLayerParam` (vtable `0x84c1b7d0`): `IsEnable`, the base and noise texture numbers, `ScatterHeight`, `ScatterAmb`, `SunOccChkSize`, the noise, backlight and colour parameters, the far/near fades and `UseScatter` | read |
| `f_834f7570` | `LensFlareElement_Params` | A lens flare element's fields: textures, position, rotation, size, colour, and `IsEnableOccludedScaling`, `IsEnableOccludedDec`, `IsEnableOccludedAlpha`, `IsEnableAngleOcclusion` | read |

The pipeline has a switch for the occluded effect (`CreateOccludedEffect`, [rendering.md](rendering.md)) and limits for
lens flares (`OfxNumLensFlare` and its rigs, presets and dynamic presets). The agl shader table lists
`occluded_effect_lensflare` beside `occlusion_query`, `occlusion_renderer` and `occlusion_renderer_clear_buf`. **read**
(the names)

## The sound's occlusion

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_83357770` | `EnvSoundRainSetting_Params` | Declares the fields of `game__sound__EnvSoundRainSetting` (vtable `0x84bf4830`): `SkyOcclusionNear/Far/SHeavySnow` `VolumeMin`/`FilterMax`, the same for `InDoor`, `InDoorDist` and `Height` (how far a sound's volume and filter drop under a roof, indoors and in heavy snow), the spatial doubler's sends, the rain and snow move and smoothing times, `RainFilterType` and the height and distance limits | read |
| `f_81097c50` | `WindSound_Params` | The wind sound's fields, among them `InCaveOcclusionVolumeBasic`/`Strong` and `InCaveOcclusionFilterBasic`/`Strong`, `BasicWindCaveRateMin` and `BasicWindSkyRateMin` | read |

## The bake workers

Two worker threads of the baked-lighting side (probes and baked resources). Looked at for the port's virtual-core
waits while a save loads, where both show up as waiters.

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_80b15710` | `BakeProbe_Init` | Creates the `BakeProbe` worker with its configured priority and a one-core mask, bound to `f_80866480` | read |
| `f_80866480` | `BakeProbe_RunEntries` | The `BakeProbe` worker's body: calls each registered entry while holding the manager's mutex | read |
| `f_80b15d80` | `BakeModuleMgr_Init` | Creates the `bake::ModuleMgr` worker when configured, bound to `f_80b41070`; its setup registers the baked-resource and light handlers | read |
| `f_80b41070` | `BakeModuleMgr_DrainQueue` | The `bake::ModuleMgr` worker's body: pops queued work under a mutex, runs each item with the mutex released, and yields between items | read |

## Data

| Address | Name | What it is | Sure |
|---|---|---|---|
| `0x84e9eab0` | `g_WorldMgr` | The world manager's pointer (`[0x84c9e898]` is this address) | read |
| `0x84baa198` | `SunOcclusion_ProgramName` | A pointer to the name `effect_sun_occlusion_cs`, the key its program is found by | read |
| `0x83f21bb0` | `WeatherNames` | The names `Invalid`, `Bluesky`, `Rain`, `Snow`, `Thunderstorm`, `Cloudy`, in that order (the weather's names; their values were not checked) | guess |

## Structures

### The world manager

| Offset | Field | Sure |
|---|---|---|
| `+0x490` | The requests' lock | read |
| `+0x4b0` | A lock the frame takes first (it does nothing that frame when it can't); `f_83472050` also takes it around the saved-state apply | guess |
| `+0x4d0` | Flags: bit 11 a copy of request bit 20 (use the player's position), bit 13 stops the clock, bit 14 the clock is stopped | read |
| `+0x4d4` | Flags: bit 0 "immediate" (`ExecuteWmRequestImmTrans` sets it; `WorldMgr_Calc` begins by copying `+0x4d8` here and zeroing `+0x4d8`, and passes the bit on to the environment update) | read |
| `+0x510` | The clock (must be set before `f_834722d0` is called) | read |
| `+0x528` | The sun's actor link | read |
| `+0x540` | The moon's actor link | read |
| `+0x578` | The environment object | read |
| `+0xddc` | The frame's step times `+0x3768` | read |
| `+0xde0` | The clock's rate: `+0xddc` times `+0x376c`, or 0 while stopped | read |
| `+0xde8` | Two request blocks of 0x11a0 bytes | read |
| `+0x3128` | The index of the block being filled (0 or 1) | read |

### A request block (0x11a0 bytes)

| Offset | Field | Sure |
|---|---|---|
| `+0` | The request bits (64-bit). Kept from frame to frame: those in `0xffffe07edfd80004`, among them `0x100000`, `0x400000`, `0x1000000`, `0x8000000`, `0x10000000`, `0x40000000`, `0x1000000000`. One frame only: the rest, among them `0x1`, `0x2`, `0x800`, `0x40000`, `0x200000`, `0x20000000`, `0x100000000` | read |
| `+0xc … +0x14` | The cloud shape (bit `0x1`) | read |
| `+0x18`, `+0x1c` | The cloud shadow's position (bit `0x2`) | read |
| `+0x9e4` | The environment effect (bit `0x800`) | read |
| `+0xa18`, `+0xb38` | Palette names (256-byte strings); `+0xc50` the third argument of `f_83473970` | read |
| `+0x10fc` | The lunar age | read |
| `+0x1100 … +0x1108` | The wind vector | read |

### The clock

| Offset | Field | Sure |
|---|---|---|
| `+8` | Flags: bit 1 (and bit 2, when `flag` bit 0 is set) set by `Clock_SetTime`, which also sets bit 3 (the step clears it again; a set leaves `+8` at 0x4, seen), bit 8 marked by the game-data load, `0x30`, `0xc0` and `0x200` tested by the frame | tested |
| `+9` | Bit 1: read the second time block (`+0x50`) instead of the first (`+0x20`) | read |
| `+40` | The seconds of the day (0 to 86399): 120 game seconds a real second, so a day in 12 real minutes; stopped by the pause menu and for 1 to 3 s at a map load | tested |
| `+44` | The day, kept mod 8 (7 then 0 seen) | tested |
| `+0xc`, `+0x10` | The minute of the day and the second of the minute (both are the save's "auxiliary words"); standing while the seconds stand | tested |
| `+0x40` | The time division (0 day, 1 night): 1 at 20:15 and 00:15, 0 from 06:00 to 15:00 | tested |
| `+0x48`, `+0x4c` | The time and day asked for by `Clock_SetTime` (a script set leaves `+0x4c` at -1, "leave the day") | tested |
| `+0x68` | The lunar age (negative: not set; `WorldEnv_LunarAge` then derives it from the day) | read |
| `+0x20` | Block A: `+0x28` the seconds, `+0x2c` the day, `+0x30` a u32 that is zeroed whenever a requested time is applied (meaning not found) | read |
| `+0x50` | Block B, the second time block the visual-only time uses (`+0x58`, `+0x5c`, `+0x60`); selected while bit 0x200 of `+8` is set | read |
| world `+0x38d8` | A signed pending hour (negative: none): `WorldMgr_Calc` applies it with `Clock_SetTime(hour * 3600, flag 0, day -1)`, sets bit 13 of `world+0x4d0` (the bit that stops the clock) and writes -1 back; who writes it was not found | read |
| world `+0x508` | The holder of the game-data time object `Clock_LoadFromGameData` reads (`+8` of it) | read |
| world `+0x3768`, `+0x376c` | The two float multipliers on the step: read 1.0 throughout 200 s of sets and loads, and also in a game whose clock stood; nobody was found who writes them | tested |

### The environment object's sun and moon flags (`env+0x38`, 32-bit)

| Offset | Field | Sure |
|---|---|---|
| bit 2, bit 3 | Day, night (the day/night value passed in the update's arguments is 0 or 1); bit 3 is slot `+0x68` | read |
| bit 4 | The sun is appearing (day): bit 2's twin; cleared with bit 5 by a second condition, and with bits 2, 3 and 5 by a flag in the arguments (`args+5`) | read |
| bit 5 | The moon is appearing (night) | read |
| bit 7 | The sun model is visible: a copy of bit 4, cleared while request bit `0x40000` or `0x8000000` is set | read |
| bit 8 | The moon model is visible: a copy of bit 5, cleared the same way | read |
| bits 9, 10 | Bits 7 and 8 of the frame before | read |
| bit 11 | The lens flare is on: set when the time of day is inside a window worked out modulo 86,400 seconds, and request bit `0x1000000000` is clear | read |

## Notes

### How the sun's visibility is decided

The sun model's visibility (`IsSunModelVisible`, bit 7 above) depends on three things only: whether it is day, whether
the world shows the sun and moon at all, and whether a script hides the models. **read** Whether terrain, a wall or a cave
ceiling is in front of the sun doesn't enter into it.

What the window for the lens flare's bit is was not worked out; the WorldParam's `SunriseHoure`/`SunriseMin` and
`SunsetHoure`/`SunsetMin` are the likely bounds. **guess**

The sun's actor (`OneShotWmSetSunActor`) and the queries `QueryGetSunDir` and `HoldCheckIsReticleDirectedToTheSun` are how
the game's scripts see the sun. The CPU-read sphere queries (`QueryGenericIsVisibleByOcclusionQuery`,
[culling.md](culling.md)) are read only by that script node; which actors' scripts use it is in their AI data, not the
code. Whether the sun's actor is one of them was not checked. **open**

### What PR #487 saw

With the per-draw count, a samples-passed report sometimes read 0, and for that frame "the sunlight left the ground and the
haze brightened over the whole picture" (PR #487). The world manager and the environment object read no query, so the
sun's own state did not change. Two paths fit what was seen, and neither has been traced:

- The z-prepass culling: an object whose count read 0 is left out of the later passes for a frame
  ([culling.md](culling.md)). If the depth that `effect_sun_occlusion_cs` reads (`cReducedBuffer`) or the scene analysis
  reads (`cQuatDepth`) lost the objects in front of the sun, the sun would count as unoccluded and the glare and haze
  would brighten. **guess**
- The scene analysis (`f_80b673a0`): an inner-mask (indoor) and shadow analysis over the quarter-size depth, whose
  results could move the sunlight. **guess**

So the cost that culling.md fears (whatever the game does when the sun is hidden never happens) is a cost to the GPU's
sun occlusion and the culling, if any; the sun model's visibility is not involved. With every report at 4096 nothing is
culled, so the depth is complete and the GPU's own sun occlusion should be right. **guess**

### LS

- `oot_set_time` calls `f_834722d0` directly with `hour * 3600`, as `ExecuteWmSetTime` would with `TimeMin` 0. It checks
  the clock (`world+0x510`) first. **read**
- The time of day above 60 fps is `f_803edf70`'s cut to whole seconds ([frame-time.md](frame-time.md), PR #2093).
- The fog and exposure factors: no factor of LS's scales them any more. The OoT fog (0.25) and exposure (0.65)
  factors, from Orchid's workaround, were off from 11-07 and removed in HS #2042 (`RX_VK_OOT`, `RX_VK_OOT_EXPOSURE`,
  `RX_VK_OOT_FOG` and `RX_VK_OOT_VISUAL` are now only logged as doing nothing). What they scaled is the froxel fog's
  integration (a compute program; the volume fog of the palettes above) and the final pass's exposure (`c3+0x38`). The
  game sets its exposure from the palette (`ExposureValue`, `IsExposureLow`, `RainExposureRate`) and from its auto
  exposure (`agl::pfx::AutoExposure`), whose meter the CPU reads back (`gpu/vk/vk_memory.cpp`).
- The volume fog's resolution is set separately for the console and handheld (`VolumeFogResScaleConsole`,
  `VolumeFogResScaleHandheld`, in the WorldParam).
- The volume fog reads the light probes (`VolumeFogProbeBakeLightScale`, `…SkyLightScale`, `…BounceLightScale`): the
  probes past the pool's end were the white haze ([rendering.md](rendering.md), *Fixes by pass*).

### What sets the time of day

`Clock_SetTime` (`f_80f0e640`, arguments clock, seconds, flag, day) has exactly three direct callers. Flag bit 0 decides `clock+8`: set, bits 1 and 2 are set (a set to an earlier time of day counts a day, and bit 2 stays until a flag-0 set); clear, bit 2 is cleared (the day is not counted; the given day is stored when it is not -1). **read**

1. **`f_834722d0` (`WorldMgr_SetTime`; flag 1, day -1): the script set.** Its only caller is `f_828b0e80`, `ExecuteWmSetTime` OnEnter (slot 29 of `0x84a02b58`; no direct callers: node graphs run it). Every Sun's Song, bed, tomb gimmick, Door of Time, cutscene and opening set arrives here, with nothing in the node that tells them apart. The debug `oot_set_time` also calls it. The nodes are used by one actor, `EventWorldManagerController`, from event flows; the flows set fixed hours only: the Sun's Song (and a bed, `LinkSleepInBed`) asks the clock's division first and sets day to 20:00, or 00:00 where the map says "the song makes a middle time here", night to 06:00, or 12:00 there; a tomb gimmick 20:00 and 06:00; the Door of Time, a Jabu Jabu cutscene and "escape a dungeon" 12:00 (05:30 once); two Hyrule Field cutscenes 07:00 and 07:30; the opening 06:00. **read** (nothing else in the flow data uses them; a string search, so an undercount is possible)
2. **`f_803ec480` (`WorldMgr_Calc`), return site `f_803ed5cc`: a pending hour.** If the signed word at `world+0x38d8` is not negative the frame sets the time to that hour (flag 0, day -1) and stops the clock (see the structures). **read**
3. **`f_83445090`, return site `f_834450f4`: the saved time.** Its only caller is `f_83472050`, called from `f_832f8690` (the node `SeqOneShotOnloadGameSaveDataWorldMgr`: the save-load set) and from `f_830513c0` (a load-sequence state machine, on its state 4 after a load-complete flag; run from `f_832962b0`). **read**

**Not through `Clock_SetTime`:** the cutscene timeline's time transition (`ExecuteWmSetTimeTransitionForTimeline`, OnUpdate `f_828b1060` -> `f_83474aa0`) and the one-shot `OneShotRequestVisualOnlyTime` (`f_829428b0` -> `f_83474f00` -> `f_83445140`) only write the world's request block and the second time block; the real seconds at `+0x28` are untouched. The Sun's Song's 3 to 4 s lerp (19:30, 18:45, 05:45, 05:00) is of that kind. **read**

**What a classifier can stand on** (a song or bed set against a cutscene set): (a) a wrap of `f_80f0e640` sees seconds, flag, day and the return address, which tells a load (flag 0, day given) and a pending hour (flag 0, day -1) from a script set (flag 1) with no table; (b) for a script set, the playing event's name `[[mgr+104]+8]` at that moment ([events.md](events.md)); the events' names live in the flow files, not in the image; (c) the node `OneShotAutoPlacementMgrSetIsTimeElapsedToNightByOcarinaSunSong` (calc `f_828d7e20`, vtable `0x84a12540`) exists only in the song's flow and stores 72000 (20:00) into the auto-placement manager's entry `0x23` at `+116`: a clean "Sun's Song toward night" signal; no signal for the other direction was found; (d) the map flag `IsSunSongMakesMiddleTime` chooses 00:00 or 12:00 over 20:00 or 06:00 (a string only, not traced); (e) the hour alone cannot separate them (06:00 and 12:00 overlap). **read**

### The clock in play

- A game's clock can **stand** and a set does not release it: a child early-story save (`coop-deku-tree-child`) kept the seconds at 06:00:00 in every scene and recorded the set requests at `+0x48` without applying them, while both multipliers read 1.0; a late-story adult save loaded directly into the Forest Temple ran at 120 s/s. So the state of the save decides, not loading into a dungeon. The branch of `f_803edf70` that takes the seconds from game data while `f_8347c020` holds fits a held clock (an inference). **tested** (the stand and the set; the cause is open)
- A set to a time of day lower than the current one counts a day, a higher one does not (six sets: 13:18 to 14:00 no, 14:28 to 13:00, 13:28 to 13:00, 14:41 to 12:00 and 12:16 to 00:00 each plus a day, 00:16 to 20:00 no); a set is applied within one frame and the clock never stood after it. **tested**
- **Scene rules** (the maps' world parameters): dungeons use a fixed default palette and the display reads a constant 06:00; the "fixed field" maps (Market, Kakariko, Graveyard, Zora's River and Fountain, Gerudo, Death Mountain Trail, Hyrule Castle) follow the clock's palette time table with a still sun; Hyrule Field has the full sun and moon (sunrise 04:00 in its own parameter); the "special field" maps (Kokiri Forest, Lost Woods, Sacred Forest Meadow, Zora's Domain) use the palette table and have no sun or moon model. **read**

### The environment objects (`EnvObj`)

The lights placed in a map are gsys environment objects: `gsys__EnvObjSetParam`, `gsys__EnvObjSetMgrParam`,
`EnvObjPointLightNum`, `EnvObjSpotLightRigNum`, `EnvObjPlaneLightRigNum`, `EnvObjForLightprepass`. An environment set
(`gsys__EnvSetParam`, applied by `SeqExecuteApplyEnvSet`) has sections for `AreaEnv`, `Bloom`, `DoF`, `ColorCorrect`,
`LightMap`, `Shadow`, `Light`, `AutoExposure`, `OccludedEffect`, `Sky`, `LocalExposure`, `Star`, `Cloud`,
`VolumetricCloud`, `EnvMapRuntime`, `SnapshotEnvObj`, `LightProbe` and others (the names `f_8357e250` uses). Not read
further. **read** (the names)

## Open questions

- What in a save holds the clock (the `f_8347c020` bool), why a child early-story save's clock stood, and the meaning of the clock block's third word (`+0x30`) and of block B's day word (`+0x5c`). Whether `f_83445090` also fires on an ordinary map change or only on a save or title load: wrap `f_80f0e640` and log the return address (`x30`) during a door transition and a save load from the title; expected a script set at `f_834722d0`'s return site, a load at `f_834450f4`, a pending hour at `f_803ed5cc`. Whether `f_830513c0` state 4 runs for every map change; what `f_832962b0` is. The event names of the Sun's Song, a bed and the Door of Time: read `[mgr+104]+8` and the C string it points to once during each; expected three distinct names (this also confirms that `player+8` is the event's name).
- What reads the `Occlusion` buffer of `effect_sun_occlusion_cs`, and what does it change: the lens flare's alpha and
  scale (`IsEnableOccludedAlpha`), the clouds' `SunOccBufSize`, the haze? Where is the program dispatched?
- Does the depth that the sun occlusion and the scene analysis read lose the objects the z-prepass culling leaves out?
  That would explain PR #487's flicker.
- The lens flare's time window: sunrise to sunset, or something else?
- Who sets request bits `0x800000` (the clock stopped), `0x2000000` and `0x4000000000`, and what bits 24 and 25 do in the
  time of day.
- Which of the weather's names goes with which value of `QueryWeather`.
- Whether the sun's actor uses `QueryGenericIsVisibleByOcclusionQuery`, and whether its glare depends on it.
- Which volume fog resolution (console or handheld) LS's game runs with.
