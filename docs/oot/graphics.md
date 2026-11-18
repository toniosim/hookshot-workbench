# Resolution, output size and graphics memory

How the game sizes its picture and its 3D: the dynamic resolution path and the fixed one, the scale table, the output size
and where it is read, and the memory the render targets come from. Also the viewport helper the save picture is drawn
through. Looked at for the Insert menu's Resolution and Output resolution rows, native scene resolution and widescreen.

**LS code:** `nx2/oot_patches.py` (`patch_dynres`, `fixed_scale`, `apply_output_size`),
`nx2/oot_wide.py`, `host/nn_applet.c` (`hos_output_size`, `hos_rt_pool_size`)
**See also:** [frame-time.md](frame-time.md), [nvn-driver.md](nvn-driver.md)

## The 3D's scale

The engine's config flag at `+0x94` picks the path: one follows the GPU-time controller (dynamic resolution, which made a
new set of render targets at each size, about 11 images a frame at times), the other renders the 3D at a fixed scale. Lichii's
"Max Resolution" patch (main+0x805BD0) and `patch_dynres` take the fixed path.

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_831f3200` | `Scene_Update` | The scene's update. Recomputes the 3D's scale (`+0xe5c = scale * +0xe58 / +0xe50`) only while `+0xe2c` bit 3 is set; the dynamic path sets it on a level change. On the fixed path the flags `+0xe20` bits 3 and 4 put a hardcoded 0.75 or 0.5 in place of the scale. Its copy of the picture's size is at `+0xb68`. Hooked by `fixed_scale`: a cached scale that differs from the one asked for sets the dirty bit (HS's `patch_scene` did it too, until #2042) | tested |
| `f_831f41d0` | `Scene_RequestRefresh` | Called for the fixed path's flag 1. Its bit 3 is cleared by the apply block in the same frame, before any recompute, so the fixed path kept the dynamic path's last scale (0.75 docked: 1536×864) until the fix | tested |
| `f_806702e0` | `GraphicsScale_SelectMode` | Picks the graphics scale's mode and tells the resources about a change. The scale table is (1.0, 0.8, 2/3) for each axis, in two profiles; the game runs in mode 1, so the fixed path's 100% sized the scene at 0.8 of the picture (2048×1152 in 2560×1440). Its factor times the base is the frame, capped by the scale's display class (docked 3840×2160 at scale 0). HS's `patch_config` made mode 1's 0.8 1.0, until #2042 removed it | tested |

## The output size

The Insert menu's Output resolution (2560×1440 as shipped). `apply_output_size` changes each of these.

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_81222ce0` | `nnMain` | Puts the display size in the framework's create arg (`+20`/`+24`, the framework's `+156`/`+160`); the window textures are made at it. The picture's 2560×1440 is built in `nnMain` itself (`apply_output_size` replaces it); `0x81202ee4`, in `f_81202b30`, only forms an address | tested |
| `f_810a7b70` | `DisplaySize_Setup(…, x1 = config)` | Sets up the display-size object (`[[0x84ca29c0]+216]`) from a config: its docked size list (`+8`, first 2560×1440) is the frame's base (`+244`) | tested |
| `f_80ea2f30` | `Scene_MaxSize` | The 3D's largest size: ResolutionParam's BaseResolution (or 1920×1080 as constants), 3/4 of 2560×1440. Above it the game takes a smaller upscale network (1/3: 1280×720 at 4K) | tested |
| `f_831cca50` | `ResolutionParam_Get` | Called by `f_80ea2f30` (returning at 0x80ea2ffc); the pair at its result is the base size | read |

## Render target memory

The render targets' GPU pool is 0x13100000 bytes, sized for 2560×1440: a 3840×2160 3D at the 4K output ran out of it.
`apply_output_size` scales the pool with the output's pixels (687 MB at 3840×2160), and grows the "Graphics" heap by as much.

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_836ce9d0` | `Graphics_MakeTargetPool` | Reads the pool's size (the graphics config's `+1464`), takes its storage from the "Graphics" heap and makes a physical pool and a virtual one over it, through `f_80c4a1c0`. It is the graphics system's whole bring-up, the pool one step of it: it also builds the frame context (`f_81028640`), the stage jobs (`f_836d0880`) and the display-size object (`f_810a7b70`) and makes dozens of other set-up calls | tested |
| `f_80c4a1c0` | `GraphicsMemory_Init` | Builds the graphics memory systems, not only the target pool: the GPU memory manager, the texture allocator (`f_80c49070`), the dynamic uniform block (`f_80c4acc0`, [shaders.md](shaders.md)) and its allocator (`f_80c49c80`), the shader storage allocator (`f_80c4ab80`), the occlusion query allocator (`f_80c4da80`) and more. The first of the chain `f_80c4a1c0` → `f_80c49070` → `f_80c49380` → `f_811c9ba0` that makes the pools. Formerly `TargetPool_Create` | read |
| `f_80c49070` | `TextureAllocator_Init(alloc, cfg)` | Sets up the target allocator in the global `0x84ea1b80`; the second of the chain. Formerly `TargetPool_Create2` | read |
| `f_80c49380` | `TextureAllocator_Construct` | Constructs the allocator (agl::utl::DynamicTextureAllocator), initialises each of its seven entries (`f_80063090`) and, when the attribute word has bit 8, makes the virtual pool through `f_811c9ba0`; the third of the chain. Formerly `TargetPool_Create3` | read |
| `f_811c9ba0` | `TextureAllocator_MakeVirtualPool` | Makes the virtual pool (NVN flags: the translated flags masked with 0x1f8, ORed with 0x201: 0x2a1) and maps the physical pool into it (512 MB in the traced runs; 0x13100000 as shipped, scaled with the output, above) with one `nvnMemoryPoolMapVirtual`; the last of the chain. Seen: one call, at the start, never again. Formerly `TargetPool_Create4` | tested |
| `f_8005ed00` | `DynamicTextureAllocator_Alloc(alloc, ctx, desc, transient)` | The pool's allocator, agl::utl::DynamicTextureAllocator (its `+0x28` the size, 0x13100000; reached through the global `0x84ea1b80`). It hashes the target's description (CRC32C) into 256 buckets. A transient request (bit 0 of the fourth argument) first looks for a free record of the same description and reuses it (a cache hit), else evicts the least recently used free record (`f_80057580`); the memory is the first fitting free range from offset 0 upward (size + 0x200, starts 512-aligned) in the entry that a byte of the context names (`+0x186`). A persistent request skips the cache and uses entry 6 from the top. Then it makes the NVN texture (`f_80065880`, `nvnTextureInitialize`), registers it (`f_80064920`) and writes the texture's slot in the pool's CPU map (flushed when the pool is cached). Its own `nvnMemoryPoolMapVirtual` site sits in a branch that makes a pool for a further segment and did not run: the pool's one mapping is made once by `f_811c9ba0`, and a run in play showed none from here (about 46 allocations a frame, each an `nvnTextureInitialize`). The terrain's temporary textures come from it too ([textures.md](textures.md)). When the pool is full it logs one line for every live record (name, size, format), and when the pool ran out the next target came back null and the game crashed here | tested |
| `f_83b7a2c0` | `ModuleHeaps_Setup` | Makes the module heaps through `f_83b7b340`, called at eight sites (one heap each) between other set-up calls; the Graphics heap's size, 0x34900000 as shipped, is the value `f_83b7b340` tests | read |
| `f_83b7b340` | `ModuleHeaps_Make` | Makes the module heaps (the Graphics heap kept at 0x348ffe20, which had under 16 MB to spare), creating each through `f_809df710`. Then takes each heap's use (its vtable +120) off its module's budget (the configured size, a table of slots) and aborts below zero (`f_8351c280`). It also calls each module's create function through a member pointer (at `0x83b7b478`): an abort inside one of them (the database manager's, `f_808103c0`, in [resources.md](resources.md)) puts this function in the backtrace but is not the budget abort at `0x83b7b578` | tested |
| `f_809df710` | `Heap_Create` | Makes a heap: `x0` the size (rounded up to 8), `x1` the name, `x2` the parent heap (null: the current heap), `w3` the alignment, `w4` and `w5` its direction and flags. It takes the heap object from the parent (vtable `+48`), sets its vtable (`0x84c172c8`), lock and lists and registers it with the parent (`+232`). Called from `f_83b7b340` (returning at 0x83b7b440), `nnMain` and many others | read |
| `f_8351c280` | `Abort` | The abort `f_83b7b340` calls when a module is over its budget. A generic abort: 85 or more callers, among them the game-data setters when a ring is full or its round changed (see [game-data.md](game-data.md)). It calls the import stub `f_85059010` (`nn::diag::detail::AbortImpl`) and the game ends there | read |
| `f_836cf4b0` | `Graphics_Init` | The graphics module's init: `f_809eaf70` (which tail-calls `f_80b72340`, the agl shader holder's set-up), then `f_80b7cc30` ([shaders.md](shaders.md)), `f_80c75b70` and `EffectMgr_Create` (`f_8087c140`). Called by `f_83b71980` | read |
| `f_80b72340` | `AglShaderHolder_Init` | The agl shader holder's set-up (10,143 instructions; strings of [shaders.md](shaders.md)'s agl programs). It starts by making the heap "agl::detail::ShaderHolder" of what the Graphics heap can still give, through `f_809df700`, then loads agl's `sharc`/`sharcb` archives (`Common`) and sets up their programs with their uniform and sampler names (`uProjViewWorld[0]`, `uColorMatrix[0]`, `cNV12DecodeParam1`, `uCasParam[0]`, …); the name slots of a program object come from `f_80b72180` ([shaders.md](shaders.md)). Reached by a tail call from `f_809eaf70`. It would take the growth too (0x1b6cb48 bytes as shipped, 0x1996cb48 grown) and leave too little for the pool, so it keeps its shipped size | tested |
| `f_809df700` | `Heap_CreateFrom` | A tail call of `f_809df710` (same arguments); called from `f_80b72340` (returning at 0x80b723ac) and about 30 other heap makers | read |
| `f_80672260` | `SceneBuffer_PickFormat` | Picks the format of the scene buffer the game tone maps into (at 0x80672340: RGBA16F, 44, under two of its flags, else R11G11B10F, 26) and makes the buffer again when the one it has differs (`+440`). R11G11B10F has no sign and 6 bits of mantissa, so native HDR banded. Hooked by `patch_scene_format`: with `hos_scene_rgba16f` (the Insert menu's HDR at Native with the PsychoV35 tone mapper) both choices are RGBA16F, after RenoDX's zelda-oot-oz patch | read |

## Graphics memory

How the game gets from its memory to NVN pools, buffers and textures: the GPU memory's pool, the allocators of the frame's dynamic data (uniforms, storage blocks, occlusion queries) and the texture helpers. Read from the lifted code and checked against runs that logged every NVN pool and texture made, with host call counters and guest-memory snapshots. What the driver does with the pool flags is on [nvn-driver.md](nvn-driver.md).

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_8005e7c0` | `GpuMemoryPool_Create(mgr, mem, heap, size, align, attrs, …)` | Makes a GPU memory's NVN pool: turns the game's attribute word into NVN pool flags with the config object `[0x84e9fcb8]` (4: GPU-only compressible 0xa1; 2, 3, 32: CPU write-combined 0x22; 1, 16: uncached 0x12; 0, 8, 1024: CPU-cached 0x24; 0x100: physical 0x18c), then makes the pool through `f_809de920` (CPU-mapped) or `f_834be840`. Called by `GpuMemory_Alloc` and the target allocator | tested |
| `f_809de920` | `GpuMemoryPool_CreateMapped` | Makes the NVN memory pool over the game's memory in one of three layouts (`nvnMemoryPoolInitialize`) and maps it for the CPU (`nvnMemoryPoolMap`); the flags are the caller's, low 28 bits | read |
| `f_834be840` | `GpuMemoryPool_InitMapped(pool, mem, size, rec)` | `nvnMemoryPoolInitialize` plus `nvnMemoryPoolMap`; stores the CPU pointer at `pool+0x100`, the flags at `+0x108` (bit 31: initialised) and a running id at `+0x10c` | read |
| `f_80f6c9d0` | `GpuMemory_InitOverStorage(mem, size, storage, info, attrs)` | The same attribute translation over storage the caller owns; used by `TextureDataMgr_Init` (`f_80f6c580`, attrs 8: the 2,432 MB 0x24 pool), the terrain's file resource manager (`f_80f6cf50`, attrs 8) and three others | tested |
| `f_80521840` | `GpuBuffer_Init(buf, info, align, count)` | An NVN buffer over a GPU memory (`BufferBuilderSetStorage`, `nvnBufferInitialize`, `nvnBufferGetAddress` kept at `+0x80`); counts the live buffers at `[device+0xd2c]` | read |
| `f_80063090` | `TextureAllocatorEntry_Init` | Initialises one of the allocator's seven 0xe8-byte entries (its used, free, by-offset and spare-node lists) | guess |
| `f_802737a0` | `DynamicTextureAllocator_Free(alloc, record)` | Gives the record's memory block back to the entry's free list at once (merging neighbours), and keeps the record, with its NVN texture and its last offset, in the LRU list and the hash, so a transient target given back is ready for an equal description. No NVN call. 378 callers, among them the pass sequencer and the handlers ([drawing.md](drawing.md)); `f_802731c0` releases by mask | tested |
| `f_80057580` | `TextureRecord_Destroy` | Destroys a cached record when the cache evicts it (its texture, through `f_80057c40`) | guess |
| `f_80064bf0` | `Texture_Finalize` | A 16-instruction wrapper of `nvnTextureFinalize` | read |
| `f_80064920` | `TexturePool_Register` | Registers a texture in the texture pool: an id from `f_80557420`, then `nvnTexturePoolRegisterTexture` | read |
| `f_800656b0` | `TextureObject_Acquire` | Takes a texture object slot from the device manager's pool (under a lock) | guess |
| `f_80065880` | `TextureBuilder_FromDesc(desc, builder)` | Fills an NVN texture builder from the game's description (target, size, levels, format, swizzle, samples, flags) | read |
| `f_80c49c80` | `DynamicUniformBlockAllocator_Init` | Makes `agl::utl::DynamicUniformBlockAllocator`: a GPU memory (attribute 2, align 0x100; 16 MB, NVN 0x22) in 64 KB blocks of 256-byte units; the global `0x84ea1470` | tested |
| `f_80c4ab80` | `DynamicShaderStorageBlockAllocator_Init` | Makes `agl::utl::DynamicShaderStorageBlockAllocator`; its pool is 8 KB, NVN 0x24; the global `0x84ea2c78` | read |
| `f_8066ff60` | `DynamicAllocators_BeginFrame` | Called by `Draw(TV)` (`f_8066fc80`): flips the frame half of the uniform, storage and query allocators (byte `+0x80`), zeroes their use counters and tracks their high-water marks, and flips the frame context index. The dynamic data is double buffered by the frame's parity | read |
| `f_80966440` | `GfxTexturePool_Initialize` | Makes the texture descriptor pool's memory (NVN 0x22; 1.1 MB at boot) and `nvnTexturePoolInitialize` | read |
| `f_8114e4f0` | `Texture_InitWithOwnPool` | A texture over a pool of its own (NVN 0x21, sized by `GetStorageSize`); in a vtable | guess |
| `f_80b65f00` | `ShaderMemory_Init` | A SHADER_CODE pool (NVN 0x62) and a buffer over it | guess |
| `f_812c35f0` | `GfxMemoryPool_SetFlags(builder, props)` | `nvnMemoryPoolBuilderSetFlags` with the game-level word's bit 16 cleared | read |
| `f_834bf750` | `GfxTexture_Initialize` | The generic texture initialiser (298 callers in 121 functions): storage over a pool and an offset, `GetStorageSize`, `nvnTextureInitialize`, registration, then a flush or an invalidate of the pool's range by the pool's flags | read |

## The graphics queues

The queues the frame is submitted through, made at start.

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_80f69040` | `GfxQueue_Init` | Makes the graphics queue (`g_GfxDevice+0x68`; flags 9) in the nn::gfx style: the queue's memory, a 4 KB event pool (NVN 0x12), two events, the command-buffer memory (a 48 MB 0x12 pool: (command size + 0x20) × count), the frame's primary command buffer, buffers over it and the fence syncs. Called once by `GameFramework_InitNvn` | read |
| `f_80c51190` | `QueueArray_Init` | `agl::driver::QueueArray(SyncEvent)`: six 0x60-byte queue slots at `g_GfxSystem+0x30` with per-slot flags (0x10, 4, 4, 6, 8, 0xa), builds the enabled ones, those with bit 2 as secondary queues of the primary (`SetPrimaryQueue`), six sync objects and the event array. The queue count was seen in a run | read |
| `f_812c3b90` | `VfxQueue_Init` | Makes the Vfx3 readback queue (a "CopyImageToBuffer" helper, `f_812bc110`) | read |

## The save picture's viewport

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_802a46e0` | `Gfx_SetViewportScissor` | The viewport-and-scissor helper: SetScissor, then SetViewport(x, y, w, h) in `w1`-`w4` from `[x8]`, called by `blr x8`. The pause menu draws the whole picture into a 543×306 texture (the save's JPEG) through it; `nx2/oot_wide.py` makes that one viewport wider or taller than the texture away from 16:9 (issue 952) | tested |

## Data

| Address | Name | What it is | Sure |
|---|---|---|---|
| `0x84ca29c0` | `g_DisplaySizeHolder` | The display-size object is `[[0x84ca29c0]+216]` | tested |
| `0x84ea1b80` | `g_DynamicTextureAllocator` | Pointer to the target allocator (its object is at the same place in every run); GOT slot `0x84ca9c68` | tested |
| `0x84ea1470` | `g_DynamicUniformBlockAllocator` | Pointer to the uniform block allocator; GOT slot `0x84cb4fc8` | tested |
| `0x84ea2c78` | `g_DynamicShaderStorageBlockAllocator` | The storage block allocator; GOT slot `0x84cb5658` | read |
| `0x84ea2cc8` | `g_DynamicOcclusionQueryAllocator` | The occlusion query allocator (1.5 MB, NVN 0x22); GOT slot `0x84cb5640` | tested |
| `0x84e9fcb8` | `g_GpuMemoryConfig` | Pointer to the config the attribute translation reads: `+0x8` flags (0x20), `+0xc` mask of CPU-write attributes (0x8f3), `+0x10` mask of GPU-uncached attributes (0xa51), `+0x14` tile size (16 × 16); GOT slot `0x84ca3178` | tested |
| `0x84e9fc58` | `g_GpuMemoryIds` | Holds the counter whose `+0x48` is handed out as a pool's id (`pool+0x10c`) | guess |

## Structures

### The scene (from `f_831f3200`)

| Offset | Field | Sure |
|---|---|---|
| `+0xb68` | A copy of the picture's size | read |
| `+0xe20` | Flags: bits 3 and 4 put a hardcoded 0.75 or 0.5 in place of the scale | tested |
| `+0xe2c` | Flags: bit 3, recompute the scale | tested |
| `+0xe50`, `+0xe58` | The terms of the scale's recompute | read |
| `+0xe5c` | The 3D's scale | tested |

### The display-size object

| Offset | Field | Sure |
|---|---|---|
| `+244` | The frame's base | tested |

### The target allocator (0x2b00 bytes, from `f_8005ed00` and a snapshot)

| Offset | Field | Sure |
|---|---|---|
| `+0x8` | Memory descriptors, 0x288 bytes each (byte `+0x281` selects the entry) | read |
| `+0x11c0` / `+0x11c8` | Record count (768) / record array | tested |
| `+0x11d0` | 256 hash buckets of 0x18 bytes (list: first, last, count, link offset) | read |
| `+0x29d0` / `+0x29e0` / `+0x29e4` | LRU list of free records / its count / its link offset (0x170) | tested |
| `+0x29e8`, `+0x2a08` | Locks (cache, segments) | read |
| `+0x2a28` | Flags (0x10c0 seen; bit 0 debug, bit 6 cache on, bits 9, 10, 13, 14 checks) | read |
| `+0x2a48` / `+0x2a50` | Segment count (1) / segment array | tested |
| `+0x2a58` | Bound on live records (37 to 46 seen) | tested |

### A texture record (0x180 bytes)

| Offset | Field | Sure |
|---|---|---|
| `+0x0` | Storage offset in the pool | tested |
| `+0x40` `+0x42` `+0x44` `+0x46` | Width, height, depth, format (u16 each) | tested |
| `+0x50` / `+0x58` | Size / alignment (0x200) | tested |
| `+0x80` .. `+0xb8` | The description it was last initialised with | read |
| `+0xc0` | Its memory block (0 when free) | tested |
| `+0x108` | The memory it is placed in (`+0x281` is that memory's entry byte) | read |
| `+0x13a` `+0x13e` | Segment index, use count | read |
| `+0x15c` | Description hash | read |

### An allocator entry (0xe8 bytes; seven per segment)

| Offset | Field | Sure |
|---|---|---|
| `+0x30` / `+0x38` | Bytes in use / high water (200-210 MB in entries 0-5, 30 MB in entry 6) | tested |
| `+0x58` `+0x70` `+0x88` `+0xb0` `+0xc8` | Lists: used blocks, free ranges, spare nodes, blocks by offset, node pool (each: first, last, count, link) | tested |
| node `+0x10` / `+0x30` | A block's offset / size | tested |

### A GPU memory pool record (0x118 bytes)

| Offset | Field | Sure |
|---|---|---|
| `+0x0` | The NVN pool object | read |
| `+0x100` / `+0x108` / `+0x10c` | CPU map pointer / game-level flags (bit 31: initialised) / id | tested |
