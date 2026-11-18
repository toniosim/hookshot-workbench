# The NVN driver

The SDK's implementation of NVN: the code every `nvn…` call of the game ends in. [nvn-calls.md](nvn-calls.md) is the game's side of
that boundary (which calls, how often, from where); this page is the other side. Each NVN function the game calls is a 16-byte
trampoline that jumps through a table the device fills in, and behind it are the functions below: the memory pools and the
buffers over them, textures and their layout, the texture and sampler pools and the handles, what a command buffer writes and
what it leaves as a record for the queue, the queue itself, syncs, events and barriers. The rows span 0x855a1b40 to 0x856500e0 in
the SDK module. Looked at to see what the real driver does where LS's recorder and renderer stand in for it.

**LS code:** none (LS puts `host/nvn_native.c` in the driver's place, [nvn-calls.md](nvn-calls.md))
**See also:** [nvn-calls.md](nvn-calls.md), [graphics.md](graphics.md) (the game's memory pools), [textures.md](textures.md),
[shaders.md](shaders.md), [drawing.md](drawing.md)

Every row is **read** from the driver's code. A row that says "Also run in an emulator" had its code executed in an emulator on a
fake command buffer, which is not a run of the game: no row here is **tested**. Names are ours: `Object_Action` after the NVN
object (`CommandBuffer_`, `Queue_`, `MemoryPool_`, `Device_`…), and `NvnDrv_` for what belongs to the driver as a whole.

## Functions

### Reaching the driver

The trampolines and the table they jump through. `nvnDeviceGetProcAddress` itself (`f_855f6f80`) is on [nvn-calls.md](nvn-calls.md).

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_855f4ca0` | `NvnDrv_ProcTrampoline(index)` | Returns the trampoline for NVN proc number `index` from the table at `0x85e17fd0` (735 entries, sorted-name order), 0 above 734 | read |
| `f_855f6e00` | `NvnDrv_SetDispatchTable(table)` | Registers the device word at `0x85ff20c0` and copies every non-null entry of a 735-slot table into the dispatch table at `0x85ff0978`, which every proc trampoline (`0x855f1de0` + 16 per proc) jumps through | read |

### The device

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_855f5350` | `Device_InitImpl` | Zeroes the 0x2320-byte device, reads the GPU info, sets flags and tables | read |
| `f_855f6210` | `Device_GetInteger` | The device-info switch behind `nvnDeviceGetInteger`: constants (descriptor sizes, pool maxima, binding counts) or fields of the device object (id 58 is the mapping granularity, id 154 whether a unified address space is present). Also run in an emulator for every id | read |
| `f_855f1da0` | `Device_SetDepthMode(device, mode)` | Stores the mode at device +4 (window origin at +0 by `f_855f1dc0`) | read |

### Memory pools

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_855fdf60` | `MemoryPoolBuilder_SetDevice` | Stores the device at +8 | read |
| `f_855fdf70` | `MemoryPoolBuilder_SetDefaults` | Flags 0x21 (CPU no access, GPU cached), storage, size and handle zero | read |
| `f_855fdf90` | `MemoryPoolBuilder_SetStorage` | Pointer and size at +0x10/+0x18, clears the handle at +0x20; no checks | read |
| `f_855fdfa0` | `MemoryPoolBuilder_SetStorageHandle` | Internal: stores a handle at +0x20, clears pointer and size | guess |
| `f_855fe000` | `MemoryPoolBuilder_GetRegionList` | Internal: returns the region count and pointer at +0x28/+0x30 | read |
| `f_855fe020` | `MemoryPoolBuilder_SetRegionCount` | Internal: stores +0x28 | read |
| `f_855fe040` | `MemoryPoolBuilder_SetRegionList` | Internal: stores +0x30 | read |
| `f_855fe060` | `MemoryPoolBuilder_SetFlags` | Stores the flag word unchanged at +4 | read |
| `f_855fe070` | `MemoryPoolBuilder_GetDevice` | Returns +8 | read |
| `f_855fe080` | `MemoryPoolBuilder_GetMemory` | Returns the storage pointer at +0x10 | read |
| `f_855fe090` | `MemoryPoolBuilder_GetSize` | Returns +0x18 | read |
| `f_855fe0a0` | `MemoryPoolBuilder_GetFlags` | Returns the raw builder flags | read |
| `f_855fe0c0` | `MemoryPool_Initialize` | Zeroes the 0x100-byte pool, normalises the flags (one CPU mode, one GPU mode), picks the ordinary or virtual set-up, creates the backing, and adds the pool to the device's list under its lock | read |
| `f_855fe3a0` | `MemoryPool_Finalize` | Removes the pool from the device list, calls the debug hook, releases its mappings and handle | read |
| `f_855fe460` | `MemoryPool_Map` | Returns the CPU pointer, or null when the pool has no CPU access | read |
| `f_855fe480` | `MemoryPool_FlushMappedRange` | Tail-calls an empty function: does nothing | read |
| `f_855fe490` | `MemoryPool_InvalidateMappedRange` | The same empty function | read |
| `f_855fe4a0` | `MemoryPool_GetBufferAddress` | Returns the pool's GPU address (+0x18) | read |
| `f_855fe4b0` | `MemoryPool_MapVirtual` | Takes the device-wide lock and maps or unmaps ranges of physical pools in a virtual pool | read |
| `f_855fe510` | `MemoryPool_GetSize` | Returns +0x38 | read |
| `f_855fe520` | `MemoryPool_GetFlags` | Returns the normalised flags, low 21 bits | read |
| `f_855fe540` | `MemoryPool_InitBase` | Fills kind, device, flags, size; clears the address and handle fields | read |
| `f_855fe570` | `MemoryPool_CreateBacking` | Virtual pools to the virtual set-up, others to the ordinary one | read |
| `f_855fe5a0` | `MemoryPool_GetTextureAddress` | Virtual pools: base plus offset; others: the alias-aware address function | read |
| `f_855fe5c0` | `MemoryPool_MapVirtualDispatch` | Runs the remap for virtual pools, returns false for others | read |
| `f_855fe5e0` | `MemoryPool_InitByKind` | Flag bit 9 picks the virtual initialiser, else the ordinary one | read |
| `f_855fe5f0` | `MemoryPool_ReleaseBacking` | Virtual pools to the virtual release, others to the ordinary one | read |
| `f_855f99c0` | `Driver_EmptyReturn` | A bare return; target of every flush and invalidate call | read |
| `f_8560dfa0` | `MemoryPool_CallDebugHook` | Calls the optional debug hook pointer (null in the image) with the device | read |

### Pool backings and the GPU address space

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_8560dfc0` | `GpuAs_MapRangeRequest` | Builds a 0x20-byte range-map request and sends it to the GPU address-space device | read |
| `f_8560e070` | `MemoryPool_ResolveTextureAddress` | Address of a texture in a pool: default kind uses the base mapping or the alias, other kinds need a compressible pool, page alignment and a kernel kind change, and use the compressed alias | read |
| `f_8560e210` | `MemoryPool_MapToGpu` | Maps the pool's handle into the GPU address space (fixed address when given), with cached bit and page size | read |
| `f_8560e350` | `MemoryPool_InitOrdinary` | Sets kind 0 and clears the mapping fields | read |
| `f_8560e390` | `MemoryPool_CreateOrdinaryBacking` | Validates size and pointer, creates the handle with the right cache mode, maps it | read |
| `f_8560e5a0` | `MemoryPool_CreateFromRegions` | Internal path: maps a list of region requests into a pool | read |
| `f_8560e900` | `MemoryPool_AttachHandle` | Stores the handle, maps it for the GPU (base, and compressible alias when asked), maps the CPU pointer when needed | read |
| `f_8560eb40` | `MemoryPool_ReleaseOrdinary` | Unmaps the three GPU mappings and frees the handle if the pool owns it | read |
| `f_8560ebc0` | `MemoryPool_InitVirtual` | Sets kind 1, clears the virtual fields | read |
| `f_8560ec10` | `MemoryPool_CreateVirtualBacking` | Requires no storage and a granular size; reserves the GPU address range | read |
| `f_8560ed60` | `MemoryPool_ReleaseVirtual` | Unmaps the pages and frees the address reservation | read |
| `f_8560ee00` | `MemoryPool_MapVirtualRanges` | Checks granularity, turns requests into kernel entries, sends them in batches | read |
| `f_8560efd0` | `MemoryPool_VirtualAddress` | Pool GPU address plus the sign-extended 48-bit offset | read |
| `f_855a1b40` | `NvMem_CreateHandle` | Creates a memory handle (alignment, cache mode, size, optional user pointer) | guess |
| `f_855c63b0` | `GpuAs_MapAtAddress` | Maps a handle at a given GPU address | guess |
| `f_855c64e0` | `GpuAs_Map` | Maps a handle at a kernel-chosen GPU address | guess |
| `f_855c6240` | `GpuAs_ReserveRange` | Reserves a GPU address range for a virtual pool | guess |
| `f_855c6320` | `GpuAs_FreeRange` | Frees a reservation | guess |
| `f_855df7d0` | `GpuAs_RemapBatch` | Maps or unmaps a batch of page ranges in a reservation | guess |
| `f_855df800` | `GpuAs_SetKind` | Changes the memory kind of a range of a mapping | guess |
| `f_855ff000` | `AsRegion_FindByRange` | Finds the address-space region record containing an address range | read |
| `f_855fdea0` | `Log2_U32` | Index of the top set bit | read |

### Buffers

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_855ea6d0` | `BufferBuilder_SetDevice` | Stores the device at +8 | read |
| `f_855ea6e0` | `BufferBuilder_SetDefaults` | Zeroes pool, offset and size | read |
| `f_855ea6f0` | `BufferBuilder_SetStorage` | Stores pool, offset and size; no checks | read |
| `f_855ea700` | `BufferBuilder_GetDevice` | Returns +8 | read |
| `f_855ea710` | `BufferBuilder_GetMemoryPool` | Returns +0x10 | read |
| `f_855ea720` | `BufferBuilder_GetMemoryOffset` | Returns +0x18 | read |
| `f_855ea730` | `BufferBuilder_GetSize` | Returns +0x20 | read |
| `f_855ea740` | `Buffer_Initialize` | Zeroes 0x30 bytes, refuses physical pools, copies device, pool, offset and size | read |
| `f_855ea790` | `Buffer_Finalize` | A bare return | read |
| `f_855ea7a0` | `Buffer_MapChecked` | Pool CPU pointer plus offset, null for virtual or no-CPU pools | read |
| `f_855ea7d0` | `Buffer_Map` | Pool CPU pointer plus offset, null when the pool has no CPU access | read |
| `f_855ea800` | `Buffer_GetAddress` | Pool GPU address plus offset | read |
| `f_855ea810` | `Buffer_FlushMappedRange` | Calls the empty function | read |
| `f_855ea820` | `Buffer_InvalidateMappedRange` | Calls the empty function | read |
| `f_855ea830` | `Buffer_GetMemoryPool` | Returns +0x10 | read |
| `f_855ea840` | `Buffer_GetMemoryOffset` | Returns +0x18 | read |
| `f_855ea850` | `Buffer_GetSize` | Returns +0x20 | read |
| `f_855ea860` | `Buffer_GetDebugID` | Returns 0 | read |

### Textures and their layout

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_8560a8c0` | `TextureBuilder_GetStorageAlignment` | 128 for linear render targets, 32 linear, element size for buffers, else 512; page size for compressed kinds | read |
| `f_8560ac80` | `TextureBuilder_GetStorageSize` | 0 with a GL name or non-texturable format, else the block-linear size (page rounded for compressed kinds) | read |
| `f_8560ad10` | `TextureBuilder_GetStorageClass` | Default kind for linear and buffer textures, else the kernel's kind for the format | read |
| `f_8560b190` | `TextureBuilder_ComputeLayout` | Builds the layout record: block dimensions, bytes per element, size, kind | read |
| `f_8560bac0` | `Texture_Initialize` | Fills the texture object; refuses physical pools and compressible textures in plain pools; resolves the GPU address into +0x60 | read |
| `f_855e84f0` | `TextureLayout_Setup` | Copies width, height, depth, levels, samples, block size into the layout record | read |
| `f_855e85a0` | `TextureLayout_PickBlockDims` | Chooses block height and depth (log2 GOBs) | read |
| `f_855e8960` | `TextureLayout_StorageSize` | Size of the whole mip chain for the chosen block dimensions | read |
| `f_85650040` | `TextureLayout_BlockHeightForRows` | Block height from 1.5 times the rows: 128+ rows 16 GOBs, 64+ 8, 32+ 4, 16+ 2, else 1 | read |
| `f_856500e0` | `TextureLayout_MipChainSize` | Sums the mip levels in whole blocks | guess |
| `f_85600420` | `Format_QueryCompressionKind` | Asks the kernel for the compressed kind of a format/sample class; 0 when the format cannot compress | read |

### Handles and descriptor pools

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_855f1bd0` | `Device_GetImageHandle(device, id)` | The image handle: the texture id as it is, sign-extended | read |
| `f_855f1c30` | `Device_GetSeparateSamplerHandle(device, id)` | The separate sampler handle: the sampler id sign-extended and shifted left 20 (into bits 31:20) | read |
| `f_855f1c40` | `Device_GetSeparateTextureHandle` | Texture id as-is | read |
| `f_855f1c50` | `Device_GetTexelFetchHandle` | Texture id as-is (no sampler field) | read |
| `f_855f1c60` | `Device_GetTextureHandle(device, tex, samp)` | The combined handle: the texture id sign-extended with the sampler id (sign-extended, shifted left 20) ORed in; zero when the texture id is zero | read |
| `f_85614650` | `Device_GetUniformBufferHandle` | Bindless constant-buffer handle: address in 16-byte units, size in 16-byte units in the top bits | read |
| `f_8560c3e0` | `TexturePool_Initialize` | Stores pool arguments and writes the null descriptor 0 | read |
| `f_8560c450` | `TexturePool_Finalize` | Does nothing | read |
| `f_8560c460` | `TexturePool_RegisterTexture` | Builds a 32-byte texture descriptor and stores it at id*32 | read |
| `f_8560c5e0` | `TexturePool_RegisterImage` | Same with the image flag | read |
| `f_8560c760` | `TexturePool_WriteDescriptors` | Copies caller's raw 32-byte descriptors into the pool | read |
| `f_856080c0` | `SamplerPool_Initialize` | Stores pool arguments, writes three default samplers at ids 0..2 | read |
| `f_856081c0` | `SamplerPool_RegisterSampler` | Builds a sampler descriptor from a sampler and stores it at id*32 | read |
| `f_856081e0` | `SamplerPool_RegisterSamplerBuilder` | The same from a sampler builder | read |
| `f_856081f0` | `SamplerPool_StoreDescriptor` | Shared body: build + store at id*32 | read |
| `f_856082e0` | `SamplerPool_WriteDescriptors` | Copies caller's raw 32-byte sampler descriptors into the pool | read |
| `f_85639630` | `Sampler_BuildDescriptor` | Turns builder fields into the 8-word sampler state (wrap, filters, LOD, aniso, compare, border). Also run in an emulator | read |
| `f_8563a460` | `Texture_BuildDescriptor` | Turns texture + view into the 8-word texture header | read |
| `f_8563ac70` | `Texture_ApplySwizzle` | Merges the NVN swizzle with the format's own channel sources | read |

### Binding textures, samplers, images and buffers

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_8561d9c0` | `CommandBuffer_BindTexture` | Writes one handle into the stage's driver table at 0x20+8*index. Also run in an emulator | read |
| `f_8561f0e0` | `CommandBuffer_BindTextures` | Writes a run of 64-bit handles into that table. Also run in an emulator | read |
| `f_8561f550` | `CommandBuffer_BindTexturesDeferred` | Records stage/first/count/array pointer for submit time | read |
| `f_8561f5e0` | `Queue_ExpandBindTexturesDeferred` | Submit-time expander of the deferred texture bind (same words as the immediate form). Also run in an emulator | read |
| `f_8561db30` | `CommandBuffer_BindSeparateTexture` | One separate texture handle at table 0x168+8*index. Also run in an emulator | read |
| `f_8561dca0` | `CommandBuffer_BindSeparateTextures` | Run of separate texture handles. Also run in an emulator | read |
| `f_8561e110` | `CommandBuffer_BindSeparateTexturesDeferred` | Deferred record | read |
| `f_8561e600` | `CommandBuffer_BindSeparateSampler` | One sampler handle at table 0x568+8*index. Also run in an emulator | read |
| `f_8561e780` | `CommandBuffer_BindSeparateSamplers` | Run of sampler handles. Also run in an emulator | read |
| `f_8561ebf0` | `CommandBuffer_BindSeparateSamplersDeferred` | Deferred record | read |
| `f_8561fa40` | `CommandBuffer_BindImage` | One image handle at table 0x120+8*index. Also run in an emulator | read |
| `f_8561fbc0` | `CommandBuffer_BindImages` | Run of image handles. Also run in an emulator | read |
| `f_85620030` | `CommandBuffer_BindImagesDeferred` | Deferred record | read |
| `f_8561bc80` | `CommandBuffer_BindUniformBuffer(cmd, stage, slot, addr, size)` | Binds a user constant buffer. The graphics stages write straight into command memory: the buffer becomes hardware slot `index+3` of the stage's group, its size rounded up to 256 bytes. Compute with the command buffer's direct-mode bit (`+0xa8`) writes the rounded size as a macro-83 call into the DRAM tables; compute without it appends a type 0x0d record and stage 8 (ray tracing) a type 0x4a one. `f_856271f0` is the translator's shadow update for a record. Also run in an emulator | read |
| `f_8561be20` | `CommandBuffer_BindUniformBuffers` | Run of uniform buffers. Also run in an emulator | read |
| `f_8561c380` | `CommandBuffer_BindUniformBuffersDeferred` | Deferred record | read |
| `f_8561ce70` | `CommandBuffer_BindStorageBuffer` | Writes address/size into the shared driver table at the stage's base + 16*index. Also run in an emulator | read |
| `f_8561cfe0` | `CommandBuffer_BindStorageBuffers` | Run of storage buffers. Also run in an emulator | read |
| `f_8561d4a0` | `CommandBuffer_BindStorageBuffersDeferred` | Deferred record | read |
| `f_856241d0` | `CommandBuffer_SetTexturePool` | Records the pool for submit time | read |
| `f_85624330` | `CommandBuffer_SetSamplerPool` | Records the pool for submit time | read |
| `f_856240b0` | `Queue_ApplyTexturePool` | Emits texture-pool address/size, copies the address into the shared driver table (0x100) and the compute data RAM. Also run in an emulator | read |
| `f_85624210` | `Queue_ApplySamplerPool` | Same for the sampler pool (shared table 0x108). Also run in an emulator | read |
| `f_85613c60` | `Queue_StoreRayTextureHandle` | Stores a ray-stage texture handle in the queue's table | read |
| `f_85627170` | `Queue_StoreComputeTextureHandle` | Stores a compute texture handle in the queue-side shadow table | read |
| `f_85606e98` | `Translator_ComputeBindTextureRecord` | Submit-time handler of the compute bind-texture record | read |
| `f_85614680` | `CommandBuffer_PushGraphicsConstants(cmd, stages, offset, size, data)` | Writes up to 256 bytes into the hardware root table (selector word then data words). No LS handler | read |

### Command buffers and their records

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_855ebfe0` | `CommandBuffer_Initialize(cmd, device)` | Zeroes the object, keeps the device at +0x70, recording mode 0, callbacks enabled | read |
| `f_855ebc80` | `CommandBuffer_AllocRecord(cmd, &out, size)` | Reserves a typed record in control memory (the type byte is written by the caller) | read |
| `f_855ec0d0` | `CommandBuffer_AddCommandMemory` | Closes the open command segment into a control record (type 3, merging adjacent ones below 2 MiB words) and starts a new one | read |
| `f_855ec2c0` | `CommandBuffer_AddControlMemory` | Links a new control block (a type-4 record) | read |
| `f_855ec440` | `CommandBuffer_BeginRecording` | Opens a recording: writes a 16-byte header record | read |
| `f_855ec500` | `CommandBuffer_EndRecording` | Closes the last segment, appends the terminator record, returns the command handle (a control pointer or a packed address+size word with a tag in the low bits) | read |
| `f_855eda40` | `CommandBuffer_CallCommands(cmd, n, handles)` | One call record per handle (`f_855ecea0`) | read |
| `f_855ec430` | `CommandBuffer_SetRecordingMode` | Stores the recording mode (the engine kind, 0 to 4) at `+0x18`; a plain store | read |
| `f_855edba0` | `CommandBuffer_AddControlRecord` | Closes the current command segment and reserves a control record | read |

### Drawing and compute

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_85620520` | `CommandBuffer_DrawArrays(cmd, mode, first, count)` | One macro-37 call: begin, vertex array start = first, count, end. Writes nothing to the driver bank (base vertex stays 0) | read |
| `f_856205a0` | `CommandBuffer_DrawElements(cmd, mode, type, count, indexAddr)` | One macro-2 call: begin, index buffer address, size, first 0, draw, end | read |
| `f_85620630` | `CommandBuffer_DrawElementsBaseVertex(…, baseVertex)` | With a non-zero base vertex: selects the driver bank at +0x640, writes the base vertex there and to the hardware vertex-id base and global base words, calls macro 2, then resets all three to 0 | read |
| `f_85620740` | `CommandBuffer_DrawArraysInstanced(…, baseInstance, instanceCount)` | Macro 39; with a non-zero base instance macro 27 (bank at +0x640) then 79, which writes the base instance to +0x644 and the global base word and resets after. Instance count 0 still draws one | read |
| `f_856207e0` | `CommandBuffer_DrawElementsInstanced(…)` | Macro 41 when base vertex and base instance are 0, else macro 27 + 80 writing +0x640 = base vertex, +0x644 = base instance (reset after). Count 0 draws nothing | read |
| `f_856208c0` | `CommandBuffer_DrawArraysIndirect(cmd, mode, argsAddr)` | Tag word, macro 27, macro 38 with the mode, then a control record that makes the GPU read {count, instances, first, baseInstance} from the game's buffer as the macro's parameters; ends with a marker word | read |
| `f_85620ad0` | `CommandBuffer_DrawElementsIndirect(…)` | The same for indexed draws with macro 40 and {count, instances, firstIndex, baseVertex, baseInstance}; writes +0x640 and +0x644 from the record | read |
| `f_85620d00` | `CommandBuffer_MultiDrawArraysIndirectCount(…)` | Macro 43: reads the count from memory, loops the draws, writes +0x644 per draw and the draw index at +0x648 | read |
| `f_85621290` | `CommandBuffer_MultiDrawElementsIndirectCount(…)` | Macro 44: per draw base vertex (+0x640), base instance (+0x644), draw index (+0x648) | read |
| `f_85621470` | `CommandBuffer_DrawMeshTasks(cmd, first, count)` | Macro 81: a points draw of `count` task launches from `first` | read |
| `f_856214e0` | `CommandBuffer_DrawMeshTasksIndirect(cmd, argsAddr)` | Macro 49 with the record {count, first} read by the GPU | read |
| `f_856216e0` | `CommandBuffer_MultiDrawMeshTasksIndirect(…)` | Macro 108: loops the records, draw index at +0x648 | read |
| `f_856217e0` | `CommandBuffer_MultiDrawMeshTasksIndirectCount(…)` | Macro 50 with the count read from memory | read |
| `f_856218f0` | `CommandBuffer_DrawMeshTasks3D(cmd, x, y, z)` | Macro 100: group counts to +0x8e0..+0x8e8, then a points draw of x*y*z | read |
| `f_85621970` | `CommandBuffer_DrawMeshTasks3DIndirect(…)` | Macro 110 | read |
| `f_85623ad0` | `CommandBuffer_DrawTransformFeedback(cmd, mode, buffer)` | Macro 42 (draw auto) with a record | read |
| `f_85627060` | `CommandBuffer_DispatchCompute(cmd, x, y, z)` | Appends a 16-byte record of type 0xf (x, y, z); the queue emits the launch at submit | read |
| `f_856270c0` | `CommandBuffer_DispatchComputeIndirect(cmd, addr)` | A record of type 0x10 holding the address | read |

### Syncs

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_85609510` | `Sync_Initialize` | Sets the device, state 0 and clears the payload of a sync object; always succeeds | read |
| `f_85609570` | `Sync_Finalize` | Releases the external object when the sync wraps one (state 4) and clears the payload (a second copy of the body sits at `f_85609520`) | read |
| `f_85609520` | `Sync_FinalizeAlias` | Duplicate of Sync_Finalize's body | read |
| `f_856095c0` | `Sync_InitFromFences` | Builds a state-5 sync from up to four kernel fences taken from another object | guess |
| `f_85609930` | `Queue_EmitFence` | Takes the queue's next counter value, writes the sync (state 2), emits the release of that value into the semaphore slot and the syncpoint bump. Also run in an emulator | read |
| `f_85609a90` | `Queue_FenceSync` | The body of nvnQueueFenceSync and of the command-buffer fence record: trace words around Queue_EmitFence. Also run in an emulator | read |
| `f_85609c40` | `Queue_FenceSyncEntry` | The `nvnQueueFenceSync` entry: passes zero flags to `Queue_FenceSync` | read |
| `f_85609c60` | `Sync_Wait` | CPU wait: polls the slot with wrap-around compare, blocks on the kernel fence in 100 ms slices, returns 0/1/2/3 | read |
| `f_85609f20` | `Queue_EmitSyncWait` | Emits the GPU-side wait for a sync (host semaphore acquire on the slot, or on syncpoints). Also run in an emulator | read |
| `f_8560a020` | `Queue_WaitSync` | Trace words plus Queue_EmitSyncWait; flag chooses the compute subchannel | read |
| `f_8560a190` | `Queue_WaitSyncEntry` | The `nvnQueueWaitSync` entry | read |
| `f_8560a1a0` | `Sync_InitFromGLSync` | Wraps an external GL fence object into a state-4 sync | read |
| `f_8560a280` | `Sync_CreateGLSync` | Exports a sync as a GL fence description | read |
| `f_8560a3c0` | `Queue_BarrierIndirectData` | Translator step of the indirect-data barrier: host reference write, or a fence plus wait on itself | read |
| `f_855edb00` | `CommandBuffer_FenceSync` | Appends a fence record with the compute/copy flags | read |
| `f_855edd80` | `CommandBuffer_WaitSync` | Appends a wait record (compute kinds use a different type) | read |

### Events

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_855fc9b0` | `EventBuilder_SetDefaults` | Clears the builder | read |
| `f_855fc9c0` | `EventBuilder_SetStorage` | Stores pool and offset | read |
| `f_855fc9d0` | `EventBuilder_GetStorage` | Returns the pool and writes the offset | read |
| `f_855fc9e0` | `EventBuilder_GetMemoryPool` | Returns the pool | read |
| `f_855fc9f0` | `EventBuilder_GetMemoryOffset` | Returns the offset | read |
| `f_855fca00` | `Event_Initialize` | Fills GPU address, CPU pointer, pool and offset of the event word. Also run in an emulator | read |
| `f_855fca50` | `Event_Finalize` | Nothing | read |
| `f_855fca60` | `Event_GetValue` | Plain 32-bit read of the event word | read |
| `f_855fca70` | `Event_GetMemoryPool` | Returns the pool | read |
| `f_855fca80` | `Event_GetMemoryOffset` | Returns the offset | read |
| `f_855fca90` | `Event_Signal` | CPU set or add of the word, then a store barrier | read |
| `f_855fcab0` | `CommandBuffer_WaitEvent` | Writes the markers, trace words and a host acquire (equal or greater-or-equal) straight into command memory. Also run in an emulator | read |
| `f_855fccd0` | `Queue_EmitEventSignal` | Translator step for a signal record: host release (top), 3D release (vertex pipe or all), compute or copy release. Also run in an emulator | read |
| `f_855fd000` | `CommandBuffer_SignalEvent` | Appends a signal record (mode, location, flags, value, event) to control memory | read |

### Barriers, counters and conditional rendering

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_85637670` | `CommandBuffer_Barrier` | Maps each barrier bit to idle waits, cache invalidates, a pixel-shader barrier or a flush, plus markers. Also run in an emulator | read |
| `f_856296e0` | `CommandBuffer_BarrierCompute` | Barrier for compute kinds. Also run in an emulator | read |
| `f_85629e60` | `Queue_BarrierCompute` | Translator step for the compute order-primitives record | read |
| `f_85637a90` | `CommandBuffer_ReportCounter` | Emits the 16-byte counter report of the chosen type (timestamps, occlusion, shader counts). Also run in an emulator | read |
| `f_85637e90` | `CommandBuffer_ReportValue` | Writes a user value plus timestamp as a 16-byte report. Also run in an emulator | read |
| `f_85638020` | `CommandBuffer_ResetCounter` | Clears the hardware counter of the type. Also run in an emulator | read |
| `f_85638090` | `CommandBuffer_SetRenderEnable` | Writes the render enable through a macro. Also run in an emulator | read |
| `f_85638100` | `CommandBuffer_SetRenderEnableConditional` | Macro that compares two 64-bit counters at addr and addr+16 on the GPU and sets the enable. Also run in an emulator | read |
| `f_85629d70` | `CommandBuffer_SetComputeEnable` | Compute-subchannel enable through a macro. Also run in an emulator | read |
| `f_85629de0` | `CommandBuffer_SetComputeEnableConditional` | Same, conditional. Also run in an emulator | read |
| `f_855f0d50` | `CommandBuffer_SetCopyEnable` | Copy-class enable writes. Also run in an emulator | read |
| `f_855f0de0` | `CommandBuffer_SetCopyEnableConditional` | Same, conditional. Also run in an emulator | read |

### Queues

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_85604490` | `QueueBuilder_SetDefaults` | Clears the builder, priority 100 | read |
| `f_85604530` | `QueueBuilder_Validate` | Checks sizes against device limits and fills defaults (64 KiB / 256 KiB / 16 KiB) | read |
| `f_856048c0` | `Queue_InitializeImpl` | Builds the queue: channel, slot, internal command buffer, memory split, flush threshold | read |
| `f_85605a60` | `Queue_InitializeEntry` | The `nvnQueueInitialize` entry | read |
| `f_85605a70` | `Queue_CloseInternalSegment` | Turns the queue's own pending words into a control segment | read |
| `f_856056d0` | `Queue_EndFlushStream` | Appends the flush tail: L2 invalidate and cache-invalidate barrier, last segments | read |
| `f_856058b0` | `Queue_Flush` | Closes the queue stream, appends the tail and kicks the pending entries | read |
| `f_856059d0` | `Queue_Finish` | Fence with flush, flush, infinite wait | read |
| `f_856060d0` | `Queue_KickPending` | Marks the fence counter flushed and appends the internal command memory | read |
| `f_85606b60` | `Queue_TranslateRecords(queue, records)` | Loops the typed control records and switches on the type through a halfword jump table at `0x85c208b2` (types 3 to 0x6f); each case updates the queue's shadow state or pushes the queue-level words at submit | read |
| `f_85607560` | `Queue_SubmitCommands(queue, n, handles)` | Walks the handles (a tag in the low 2 bits says list or packed segment), gives each to the record translator (`f_85606b60`) and appends their segments and records to the pending ring; starts nothing, the GPU starts when the queue is flushed | read |
| `f_8560f980` | `Gpfifo_AppendSegments` | Converts control segments to fetch entries; kicks when nearly full | read |
| `f_8560fab0` | `Gpfifo_AppendEntry` | Wrapper with flag 1 | read |
| `f_8560fda0` | `Gpfifo_Kick` | Vtable +0x18: hands pending entries to the kernel (not read) | guess |
| `f_855f63d0` | `Queue_MarkFlushedFence` | Copies the issued counter into the flushed counter of the queue's slot | read |
| `f_856104b0` | `Queue_EmitSyncpointIncrement` | Emits the release that bumps the queue's syncpoint and returns its id and threshold. Also run in an emulator | read |
| `f_85610440` | `Queue_WaitSyncpoint` | Emits a GPU wait on a syncpoint threshold | read |
| `f_8562a580` | `Queue_EmitRingRelease` | Release through the secondary-queue ring (macro) or the compute release | guess |
| `f_8562b2c0` | `Queue_InitMacros(params, queue, subchannel)` | Uploads the 110 GPU macros (start-address and instruction RAM, 1,274 three-word instructions) | read |
| `f_85630a00` | `Queue_InitState(queue)` | Writes the queue's default hardware state, the driver bank selectors, the bank 2 images and the stage group binds | read |

### Words the driver emits

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_8563ae60` | `Gpu_EmitHostAcquire` | Emits the host semaphore acquire (greater-or-equal, signed, switch enabled). Also run in an emulator | read |
| `f_8563aee0` | `Gpu_Emit3dRelease` | Emits the 3D-class semaphore release (one word, after earlier writes, optional vertex-pipe location, flush control). Also run in an emulator | read |
| `f_8563afd0` | `Gpu_EmitComputeRelease` | Same for the compute subchannel; mode 1 adds instead of writing. Also run in an emulator | read |
| `f_8563b0a0` | `Gpu_EmitCopyRelease` | Same for the copy engine; mode 1 uses the semaphore reduction add. Also run in an emulator | read |
| `f_8563b160` | `Gpu_EmitCacheFlush` | Emits the L2 flush/membar/sysmem invalidate host operations for CPU visibility. Also run in an emulator | read |
| `f_8563b250` | `Gpu_EmitHostAcquireMode` | Host acquire for an event wait (equal or greater-or-equal) | read |
| `f_8563b2e0` | `Gpu_EmitHostRelease` | Host semaphore release at top of pipe: set, or reduction add; no wait for idle. Also run in an emulator | read |
| `f_8563bf00` | `Trace_MakeDescriptor` | Packs the descriptor word of the no-op trace macro. Also run in an emulator | read |

## Data

| Address | Name | What it is | Sure |
|---|---|---|---|
| `0x85ff0978` | `NvnDrv_DispatchTable` | The 735 live implementation pointers the trampolines call (zero until the device registers) | read |
| `0x85e56528` | `NvnDrv_ProcImplTable` | The default table of the real implementations (742 slots), what GetProcAddress returns before a device exists | read |
| `0x85e17fd0` | `NvnDrv_ProcTrampolineTable` | The 735 trampoline addresses | read |

## Notes

- Flushing and invalidating a mapped range does nothing in this driver: `f_855fe480`, `f_855fe490`, `f_855ea810` and `f_855ea820` all
  reach the one empty function `f_855f99c0`. Memory is kept coherent only by the CPU and GPU access modes chosen when the pool is
  made and by fences and syncs, so the game's `GetFlags` plus flush or invalidate pairs ([nvn-calls.md](nvn-calls.md)) cost nothing on
  the console. **read**, and run in an emulator for every flag combination.
- The binds of the graphics stages (`BindTexture`, `BindSeparate…`, `BindImage`, `BindStorageBuffer`, `BindUniformBuffer`, and their
  array forms) write their words straight into command memory when called. Only compute without the direct-mode bit, stage 8 (ray
  tracing), every `…Deferred` form and the two pool setters append a record for the queue to translate at submit; a deferred record
  keeps a pointer to the caller's array, which is read at submit time. **read**, and run in an emulator.

## Open questions

- The values the game passes to `SetRecordingMode`: the kind changes the words and records a command buffer emits.
- Sync states 1 and 3 and what sets them, the housekeeping at the end of `Queue_Finish` (`f_856077f0`), the kick `f_8560fda0`, the
  secondary or compute ring queue and the control record types 0x25 and 0x26 were not decoded.
- The device fields that decide the compressed-kind alignment and size (`+0xd4`, `+0xd8`, `+0x9f8`) are set at device start from the
  GPU's info, so the image alone does not give their values.
- Which size of constant bank the game's device uses for the texture, image and sampler tables (device flag bits 8 and 9), and the order
  of the tables the compute dispatch macro copies.
