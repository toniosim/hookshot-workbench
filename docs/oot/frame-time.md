# Frame time and frame rate

How the game steps its frames: the frame step and the game clock, the frame limiter, movie and cutscene timing, and the sites
examined for a frame-rate cap above 60 (issue #1742). Above a cap of 60 the game's frame step is the frame's own time (0.42 at
144 fps), so a site that cuts the step to whole frames or counts updates goes wrong there.

**LS code:** `nx2/oot_patches.py` (`patch_frame_seconds`, `patch_movie_frames`,
`patch_whole_frames`), `host/nn_vi.c` (`hos_frame_seconds_bits`, `hos_movie_frames`, the frame limiter)
**See also:** [graphics.md](graphics.md)

## The step and the clock

The engine has two places where its integer nominal rate (`+0x2c8` of the graphics module) becomes a time step, both a float
divide "base / nominal". The engine's own rate is 60 / whole display intervals, never above 60, and its controller puts 60
back over a higher value written from outside before either divide runs.

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_80706be0` | `ModuleSystem_ModuleCalc` | The ModuleSystem's calc: runs the frame's two module job graphs ([jobs.md](jobs.md)), and in it the frame's step, base 60.0 (30.0 in the half-rate mode): added to the game clock (the double at `[x19+0xd58]`, in 1/60 s) and handed on as the frame's seconds. Hooked by `patch_frame_seconds`: base times the host's measured frame time | tested |
| `f_83b6ea90` | `Frame_GlobalStep` | The global step (60.0 / nominal, the float at `0x84d61fc8`) the rest of the engine reads. Hooked by `patch_frame_seconds` | tested |
| `f_83b6e300` | `FrameTime_Update` | The frame-time keeper (`[[0x84c9e890]]`). This function writes `+16` the step, `+20` 1/step, `+24` the scaled step and `+28` the rate as an integer (60 over the step), and pairs from `+0x144`; `Timer_Step` reads the scaled step from `+0` and from per-slot blocks at `+32 + 48k` (k below 6), which this function does not write | read |
| `f_8042cd20` | `Frame_Limit` | The frame limiter (slot `+0x110` of the framework). With `fw[0x24f] & 3` equal to 3 it sleeps to the next 1 / `+0xfc` period of the graphics module; otherwise it waits on the GPU fence of the frame before last (the ring at `g_GfxDevice+0xb8`, parity `+0x168`) and on the window's acquire sync (`win+0x78`), timing optional callbacks at `fw+0x188`, and ends with a tail call of `nvnEventSignal(events[+0x164], 0, 1)`: the CPU opens the frame's GPU gate. The fence waits were seen in a run | tested |
| `f_804fc0f0` | `Display_SetRefreshRate(display, &out, rate)` | The display's refresh-rate request: `x0` the display object, `x1` an optional out pointer, `w2` the rate. With variable refresh on (byte `+0x231` is 1), a rate of 40 or more and byte `+0x232` set, it stores the rate itself at `+0xfc`. Otherwise a rate that divides 60 exactly sets the swap interval 60 / rate (through `f_80f69970`) and stores the rate at `+0xfc`; any other rate is refused, and when the out pointer is given it receives 60 over the rounded-up interval count (the next lower supported rate). A rate of 0 or less is refused with 1 in the out word. Returns 1 when the rate was taken. Callers `f_804fbda0`, `f_8348c660`, `f_83b6f160` | read |
| `f_8060d3d0` | `Timer_Step(timer)` | A generic timer, 332 direct callers: `{value +0, previous +4, rate +8}`: previous = value, value += rate times the frame-time keeper's scaled step (or a per-slot copy of it); returns the new value in `s0`. At 60 fps the step is 1.0, so a timer's unit is a 60 Hz frame. The counter node steps its timer with it ([ai.md](ai.md)) | read |

## Movies and cutscenes

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_83b7c710` | `MoviePlayer_CountFrame` | Counts the movie player's updates while a movie plays: one more at `player+760` each frame (#1875). Hooked by `patch_movie_frames`: the count grows by the frame's time, as the clock does | tested |
| `f_83b7ca60` | `MoviePlayer_Accumulate` | The movie's timed accumulator (it keeps its remainder: fine above 60) | read |
| `f_83b5ec10` | `Cutscene_MovieFrame` | A cutscene that shows a movie takes the player's count as its timeline's frame (with `f_83b5e9a0`): the narration, the rumble and the cutscene's end are placed by it | tested |
| `f_83b5e9a0` | `Cutscene_MovieFrame2` | The other half of that, with `f_83b5ec10` | read |
| `f_8124cfc0` | `Timeline_FireEvents` | Fires the events whose time lies between the timeline's last frame and the new one, walking a list sorted by time. The in-engine timelines run it with a rate times the time step | tested |

## Sites examined above 60

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_80a87e50` | `PickupCounter_Update` | The pickup counter above Link's head: moves the count it shows toward the new total by `(int)(step * …)`. Stalled above 60 (#1832). Hooked by `patch_whole_frames` | tested |
| `f_803edf70` | `TimeOfDay_Update` | The time of day: adds `(int)(2 * step)` game seconds a frame (`+60`) to the seconds of the day (`+40`, mod 86400), then the day (`+44`). Cut, it added 1 a frame below 120 fps (the day slower: 83% at 100) and 0 above 120, where the clock stood still. Before stepping, it also reads a played flag besides the Deku Tree story step (the test of `f_8043e980`, inlined): it steps the seconds as above if the step is Ready or the flag is set, otherwise it takes another branch. That test was read, not run, and the other branch was not read to the end. Hooked by `patch_whole_frames` | tested |
| `f_8043e980` | `TimeOfDay_IsNotYetPlayed(w1)` | The test `f_803edf70` makes, as a function: false when `w1` is not 0 or the Deku Tree story step is Ready (the step is a ChallengeMgr entry's current step, `+16`, [game-data.md](game-data.md)); otherwise true while a played flag is clear. `f_8347c880` is a second copy | read |
| `f_800672e0` | `WaterRipple_SubSteps` | The water renderer's ripple simulation: runs `(int)step` times the water's sub-steps (`pass+76`) each frame (called from `f_80660320`). Cut to 0 above 60 fps, the rings the player and the actors make in water stood still. Its remainder is kept per water object (`x21`). Hooked by `patch_whole_frames` | tested |
| `f_832b32b0` | `ScarecrowSong_Playback` | Scarecrow's Song playback: the elapsed-frame counter at `obj+0x265fc` (`x19` here) advances the saved note delays by `(int)step`. Cut to 0 above 60 fps, the song waited on one note until a slow frame let the counter move. Hooked by `patch_whole_frames` | tested |
| `f_832b6840` | `ScarecrowSong_Record` | The eight-note recording (mode 10): the same elapsed counter is reset between notes and gaps, then saved as their lengths. Cut to 0, the timing was lost though the eight pitches were recorded. At the cut `x9` holds the counter's address (`x0+0x265fc`: set from `x0+0x26000` plus 1532 on both ways into it, by falling through and from `0x832b6e00`; the store at `0x832b6dac` writes through it), so the three Scarecrow sites share one remainder. The other recording mode (13) cuts the same way with an `x12` addition and is left as the game's. Hooked by `patch_whole_frames` | tested |
| `f_832b2690` | `ScarecrowSong_RecordEnd` | Recording completion: after the eighth note starts it times that note and writes its final delay into the same recording (`x19+0x265fc`). Its unsigned cut must carry the fraction too, or the eighth note is saved with zero length and not played. Hooked by `patch_whole_frames` | tested |
| `f_80652cb0` | `FloorWeb_Simulate` | The floor web's simulation: `(int)step` steps a frame, clamped to 0..3. Cut to 0 above 60 fps, the web stayed rigid when the player landed on it, though it still held him. Its remainder is kept per web (`+2296`), before the clamp. Hooked by `patch_whole_frames` | tested |
| `f_83be20b0` | `UnchangedTimeout` | A 300-update timeout on an unchanged value (would run fast above 60) | read |
| `f_83c53620` | `ListEntryTimer` | A 180-update timer per list entry (would run fast above 60) | read |
| `f_8057fd20` | `DirectionLookup` | An angle lookup that sorts nearby objects into 16 or 32 directions (fine) | read |
| `f_806d4720` | `NearestHeapA` | A "nearest N" heap by squared distance (fine) | read |
| `f_806d5410` | `NearestHeapB` | Another of the same (fine) | read |
| `f_800fb340` | `HitTest_RoundUp` | A hit test that rounds up (fine) | read |
| `f_802c0540` | `FractionalTimerA` | A timer that copes with fractional steps (fine) | read |
| `f_80596c60` | `FractionalTimerB` | The same (fine) | read |
| `f_80746660` | `FractionalTimerC` | The same (fine) | read |
| `f_8156f0c0` | `RectOffset_Apply` | Not a timer. It searches the keyed arrays of its owner (`+8`, `+24`, `+32`) for the index of a key range, calls the matching element's virtuals (`+96`, `+104`) and shifts two ints of the out record (`+4`, `+8`) by a float offset scaled by `0.5` and cut to an integer. The frame step does not appear in it, so it is no frame-rate site | read |
| `f_83423a90` | `IntegerBucketCompare` | Compares the integer buckets of a current value and of that value minus the step; it does not add a separately cut delta to a timer (fine) | read |
| `f_8337b110` | `FloatPhaseAdd` | Adds time to a float phase and writes the fractional remainder after removing whole periods (fine) | read |
| `f_80a28f90` | `ScaledTimeAccumulator` | Adds scaled time into a float accumulator before deriving whole cycles; the subtraction or wrap keeps the remainder (fine) | read |
| `f_8055d8d0` | `PhasePrecisionIndex` | High-precision phase increments feed table indexing and interpolation, scaled by 2^32. Not a whole-frame timer: changing it as a display counter would be unsafe | read |
| `f_833dc4c0` | `IntegerFractionSplit_A` | An integer-and-fraction splitting helper: the fraction is returned or stored separately, not a discarded elapsed step (fine) | read |
| `f_83a6ce60` | `IntegerFractionSplit_B` | The same kind of helper (fine) | read |
| `f_8333c4b0` | `WeightedRecordAccumulate_A` | Weighted record accumulation: the caller takes the coefficient from a selected record, not from the frame-step keeper; several integer fields are gated at weight 1 or more. No temporal provenance was found | read |
| `f_8333c520` | `WeightedRecordAccumulate_B` | The same kind of accumulation (see `f_8333c4b0`) | read |
| `f_83755490` | `TimeUnitConvert_A` | A large-unit time or tick conversion (the first pair scales by 1e9): not a demonstrated gate on a step under one frame | read |
| `f_83755540` | `TimeUnitConvert_B` | The same kind of conversion | read |
| `f_82733050` | `QuantizedPositionConvert` | Quantized position, angle or range values or indices, not an elapsed-step counter; it binds to horse rail following | read |
| `f_807f75e0` | `QuantizedConvert` | Quantized shape or index conversions, not an identified elapsed-step counter | read |

## Data

| Address | Name | What it is | Sure |
|---|---|---|---|
| `0x84d61fc8` | `g_GlobalStep` | The global step float `f_83b6ea90` writes | read |
| `0x84c9e890` | `g_FrameTimeHolder` | The frame-time keeper, `[[0x84c9e890]]` | read |

## Notes

- A signed truncation of the update context's step at `+0xf44` of `f_80d90e60` (the `ExecuteMovableBoxControl` OnUpdate, the movable boxes' and the Forest Temple box puzzle's class, called for a tombstone through `f_82892650`) is added to a count at `+0x124` (a state byte is set when it reaches 3). No patch covers it, so above 60 fps the count may stand; the context's `+8` behaves as a delta in the neighbouring movement integration, but its provenance and the visible settling it would break were not observed. A carry that survives the condition that clears the count could advance a later episode early. Row on [ai.md](ai.md). **read** (the arithmetic and the class), **guess** (the delta and the failure)
- More sites counted in frames, from the later pages (each runs proportionally more often in real time above 60 fps): the actors' calc-skip intervals (`(frame - phase) mod interval`, the frame at `[0x84eb0d90]+0x440`) and the LOD module's `mod N` / `mod 5` staggering ([animation.md](animation.md)); AI and NPC component work every 10, 30, 60 or 150 frames by BaseProc id, and AIGroupParallelCalc's every-N ([ai.md](ai.md)). **read**
- The physics world's base step is the literal 1/60 s at 0x83b89578 (`DF+0x24`), and the frame step reaches the solver through its step count, set each update from it (`DF+0x38`); LS rounds the count up above 60 fps (issue 1798, `host/oot_high_fps.h`; [physics.md](physics.md)). **read** Cloth also follows the frame's step.
- `0x84d61fc8` (the global step) has one reader, `f_834a3680` ([physics.md](physics.md)'s scan). **read**

- Above 60 fps, before the step hooks, every frame still stepped 1/60 s and the game ran fps / 60 times too fast.
- A movie's picture follows the clock, but its cues follow the update count, so above 60 they ran ahead (fps / 60 times).
  The timeline doesn't need every frame value, since it fires everything in between: measured at 36 fps under a cap of 120,
  steps of 1 and 2 gave every narration line and the rumble as at 60.
