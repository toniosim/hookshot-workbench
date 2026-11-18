---
name: ls-function-map
description: >
  Use before reading lifted game code and whenever a task meets an `f_<address>` function, a game structure or field
  offset, a `patch_*` hook in nx2/oot_*.py, a frame-rate site, or a game subsystem you do not know (jobs, physics,
  drawing, shaders, textures, input, audio, saves): look the address or the subject up in the function map first, weigh
  the row by how sure it is, and hand back a row for what you worked out. Also for checking the map against the port's code,
  for the function that contains a backtrace's return address, for a flag's hash or name in a co-op log (section 6), and
  for reading the game's own data files, not code (section 7).
---

# The function map: look it up first, add what you learn

The game ships without symbols, so the lifted code calls every function `f_<address>`. The map says what the ones
somebody already looked at do: about 2,000 rows over 35 pages, one page per part of the game, each row with how sure it
is. Reading it takes seconds; working a function out again from lifted C takes an hour and may get it wrong.

- Pages and conventions: `/home/tonesi/hookshot-workbench/docs/oot/` (`README.md` is the index).
- Tool: `/home/tonesi/hookshot-workbench/docs/oot/fnmap.py` (standard library; it only reads files, so it needs
  no lock).
- Published in the workbench repository; written by dyst.

## 1. Look it up

```sh
M=/home/tonesi/hookshot-workbench/docs/oot
python3 $M/fnmap.py find f_803edf70        # an address: its page and its one row
python3 $M/fnmap.py find 0x84e98e38        # a data address
python3 $M/fnmap.py find "time of day"     # words: rows that have all of them (first 20)
python3 $M/fnmap.py find BakeProbe         # a thread, class or job name from a log line works the same way
```

- Every function has **one row on one page**. `mentioned, no row` lists the lines that name what you searched for
  without describing it (each cut at 240 characters: open the page for the rest): another function's row, or a page's
  prose (its *Notes* and *Open questions* often say more than its rows). `find` stops after 20 hits, so do not pipe it
  into `head`: that ends in a `BrokenPipeError` traceback, harmless but it looks like a failure.
- `find` prints, under a row, how the recheck of 17 Nov 2026 judged it (`docs/oot/rechecks.md`): `rechecked …: agrees`
  is a row whose claims were found in the code; `partly` or `corrected` says what the row got wrong; `cannot-check yet:
  <reason>` and `not rechecked` mean nobody has verified the row since it was written, so weigh it by its *Sure* alone.
- `find` knows function **starts**. A place inside a function answers `nothing`: every line of a guest backtrace (those
  are return addresses) and a fault's pc are such places. Find the containing function first (rules for lifted code
  below), then look that function up.
- No hit at all: find the subject instead. The index in `README.md` says which page covers which part of the game;
  read that page's "In short" before concluding the map has nothing.
- Read the whole row and the page's first paragraph before the lifted code. A row that says `Hooked by patch_x` tells
  you which function in `nx2/oot_*.py` changes it; the patch's own comment says what the patch does.
- **No shell (a read-only worker)?** The tool is a convenience, not a requirement: every function is one line of one
  page, so search the pages themselves for `f_<8 hex digits>` (or `0x<address>`, or the words) under
  `docs/oot/*.md`. Read the line's whole row and its page's "In short".
- **Also search the earlier investigations** before working anything out again: the reports folder (the one the
  brief, `AGENT-BRIEF.md`, lives in; its `*.md` files) holds findings that never became rows (chests and item giving,
  crashes, frame-rate sites). Search it for the address or the game's name for the thing. A report can be older than the map
  and wrong where they differ; say which you used, and hand the report's still-true findings back as rows (section 4).

### When the map has nothing: reading the lifted code

The lifted C of a build is in its work folder, `<worktree>/work/build/sa/gen/code_*.c`; use a retained build of the
commit you are asking about (the brief and `reports/LOG.md` name them; one of main is
`/home/tonesi/hookshot-wt/longshot-base-d3bd2805/work/build/sa/gen`). It is game-derived: it never leaves the PC.

- A function starts at `void f_<address>(Ctx *__restrict A64_NOESC c) {` in exactly one file. The files are tens of
  megabytes: find the file first (`G=<worktree>/work/build/sa/gen`, then
  `grep -l -m1 '^void f_803edf70(Ctx \*__restrict' $G/code_*.c`; under a second), then read that one function. Search
  `code_*.c`, not `code_0*.c`: it includes the `code_hot_*.c` files that hold the hot functions. Match the definition
  with `\*__restrict`: a bare `f_<address>(Ctx` also hits the forward declaration (`void f_<address>(Ctx *A64_NOESC);`)
  that a dozen files carry. Searching many of these files in one call for other patterns can silently miss matches;
  search one file at a time for those, or loop over the files in a script (a scan of all of them for one register's
  constants takes seconds).
  The link map names the file in one grep: `grep -m1 '(.text.f_803edf70)' <worktree>/work/build/sa/build/longshot.map`
  shows the object (`code_001.o` is `code_001.c`), which beats searching the code files.
- The guest image is on disk too: `<worktree>/work/build/sa/image/image.bin` (its first byte is guest address
  `0x80000000`, so a file offset is the address minus `0x80000000`; that is the image's base, **not** the main module's,
  which is `0x80020000`: see the bullet on another project's addresses below) holds the relocated vtables, registry
  tables and every string. A vtable slot is `vtable + 8 * slot`; read a string or a table at its address directly
  instead of searching the C for who loads it.
- Which file holds an address is decided per build. Do not work it out from a `chunks.txt` or an image listing that
  belongs to another build's work folder; search the files of the build you are reading.
- Strings are not in the C: a thread or class name is loaded from the game image by address. To get from a name in a
  log to its function, find who references the string's address, or start from a neighbour the map already has.
- Thread names are not unique: a pool's workers share one name (six `BaseProcCreateAndDeleteThread`, one
  `PreActorModelCompose` per core). A name in a log line or a sampler does not identify which worker it was.
- Another project's addresses (a co-op mod's, say) are offsets into the game's main module, which is loaded at
  **`0x80020000`**: our address is their offset **plus `0x80020000`**, and their offset is our address minus
  `0x80020000`. Their `0x57af30` is `f_8059af30`; their `0x33e4200` is `f_83404200` (`0x033e4200 + 0x80020000`), data
  converts the same way (their `0x4e94840` is `0x84eb4840`). Do not use `0x80000000` (the image file's base above): it
  lands `0x20000` too low, and their `0x33e4200` becomes `f_833e4200`, an address where no function starts (once
  copied into reports as the HUD refresh, which is `f_83404200`). Convert in the shell:
  `printf '%08x\n' $((0x57af30 + 0x80020000))`. A converted address is a function only if `$G/functions.txt` has a
  line for it (`grep '^8059af30 ' $G/functions.txt`): check that before you write a row. Every one checked by reading
  the function was the one their comment names, but a comment in their code is only a lead: a row built from it without
  reading the function is **guess**. An offset can land inside a function (their `0x49dcb0` is a place inside
  `f_804bd8c0`, not a function: find the function that contains it, below, and put the place in its row as `at 0x...`),
  and a name can belong to the next class's function; read it before you trust it.
- Another project's **code** cannot be dropped in, only translated: `host/` is C only (no `.cpp`; the C++ is the
  renderer's), and the game is recompiled from its lifted C, so the only way to hook it is at lift time: a `patch_*` text
  patch over the lifted C in `nx2/oot_patches.py` (found by a function's head or an anchor line) or a hook in the
  lifter's `after[pc]` (`nx2/oot_fov.py` is the short example). Two patches on one function must coexist: each adds its
  line after the head or anchor, or appends to what `after[pc]` already holds, and neither rewrites text the other
  anchors on.
- `$G/functions.txt` lists every function of the build sorted by address, one `<8 hex digits> <instruction count>`
  line each (written by the lifter; the same set as the definition lines): the quick test whether an address starts a
  function, and the index for the next bullet.
- **Which function contains an address** (a place inside a function): the last `functions.txt` line at or below it. A
  backtrace's lines are return addresses, so look up each one minus 4, the call itself (a call that ends a function
  returns to the next one's first address). The link map is not in address order, so it cannot say. Then `find` the
  function's `f_<start>` for its row, and put the place in a row as `at 0x...`. Without a `functions.txt`, list the
  starts file by file: `grep -o '^void f_[0-9a-f]\{8\}(Ctx \*__restrict' $G/code_001.c`.

  ```sh
  python3 -I -B - $G/functions.txt 0x803edf74 <<'PY'      # any number of addresses
  import bisect, sys
  rows = [(int(a, 16), int(n)) for a, n in (l.split() for l in open(sys.argv[1]))]
  starts = [a for a, _ in rows]
  for arg in sys.argv[2:]:
      pc = int(arg, 16)
      a, n = rows[bisect.bisect_right(starts, pc) - 1]
      print("%#x  f_%08x +%#x%s" % (pc, a, pc - a, "" if pc < a + 4 * n else "  (past its end)"))
  PY
  ```
- A flag or a struct member is named in code by the hash of its name, a 32-bit constant built in a register. In the
  lifted C that is three statements: `c->x[N] = 0x<low half>ULL;`, `c->x[N] &= 0xFFFFFFFFULL;`, then
  `c->x[N] = (c->x[N] & ~(0xFFFFULL<<16)) | (0x<high half>ULL<<16);`. Grep the low half and read the next two lines for
  the high half, or scan every file per register in a script. A flag can also be read as a member of a struct, by the
  plain hash of its name instead of the flat `Struct.member` hash: scan for both (`docs/oot/game-data.md`).
- **Where the real body is.** Many functions start with a 1 to 20 instruction stub, a thunk or a destructor next to the
  body (a `functions.txt` count of 1 to 5 flags one). A row that sits on one is a wrong address: search the string's or
  the vtable's users first, then read the neighbours. A cross-file tail call is `TAILCALL(f_x);` (count it as a call when
  you list callers, and search all `code_*.c`; a function missing from the link map is in `code_hot_*.c`). Import
  stubs (`f_85...`) are in `$G/a64_hooks.c`, which names the import, not in `functions.txt` (it is in `$G` too).
- **Without a disassembler.** `llvm-mc --disassemble --triple=aarch64` on the 4-byte words of `image.bin` gives the
  instructions of a stub. Find a function's vtable slot by searching `image.bin` for its address as 8 little-endian bytes
  (it has the vtables and GOT cells, not the registry entries a static initialiser writes at run time).
- **Reading the C.** An address constant is a page base plus a displacement, which can be negative (`g_module_base +
  0x80de9000 + (-N)`): add them before you search. `recomp_load8` is a byte load. A `_Params` class name is returned by
  the function 6 slots before its visitor in the vtable (7 for `WorldParam`). A script node's name getter is slot 19, its
  Execute 29, 30 or 31, OneShot and Query 39, Hold 40.
- **The retained build is older than main:** its C has only the port's patches of its own date, so a hook on newer main
  is not in it; read the port's `nx2/` at the rev you ask about. A row's `at 0x...` is the call; a backtrace or `lr` line
  is the return address, 4 after it.
- What you work out this way is exactly what section 4 is for: hand the rows back.

## 2. Weigh the row before you build on it

| Sure | What it means | How to use it |
|---|---|---|
| **tested** | seen in the game, or a shipping patch relies on it | rely on it for the role the row states, not beyond |
| **read** | worked out from the lifted code, never run | a strong lead: confirm the part you depend on in the lifted code or in a run |
| **guess** | from names, constants or neighbours | a hint where to look, nothing more |

Nine rows in ten are **read**. The addresses belong to the supported game build, which never changes, so a row does not
go stale by itself; what goes stale is what a row says about the port (`Hooked by`, "the fix is ...", hot ranks). When a
row and the port's code disagree, the code is right: say so in your report and propose the corrected row.

## 3. Use what you found

- In a report to the main session, cite it: page, address, the row's *Sure*. Say whether you confirmed it and how.
- In anything public (a pull request, an issue, a comment, the team room) write what the change needs **in your own
  words**. Never paste pages, tables or runs of rows, and never lifted code. The port's own rule stands: nothing made
  from the game leaves the PC.

## 4. Add what you learn

Add a row when you worked out what a function or a data address does, when a patch or a host file newly names a game
function, when you confirmed a **read** or **guess** row in the game (raise its *Sure*), or when a row is wrong.

A row is an address, a working name of ours in `Owner_Action` form, what it does in our own words, and one of the three
*Sure* values. The format, the page template and what may not go in are in `README.md` ("Conventions", "A page", "What
may go here"). Not allowed in a row: lifted C, disassembly, text or file contents copied from the game, and the state
of a pull request ("open", "fixed in"): describe the game, not the tracker.

```markdown
| `f_80652cb0` | `FloorWeb_Simulate` | The floor web's simulation: `(int)step` steps a frame, clamped to 0..3. Cut to 0 above 60 fps, the web stayed rigid. Its remainder is kept per web (`+2296`). Hooked by `patch_whole_frames` | tested |
```

**A worker does not commit in the workbench repository.** Put this in your final report and the main session adds it:

```markdown
## Function map rows
- page: frame-time.md, table "Sites examined above 60"; current row (from `find`): none | page:line; new | corrects | extends | confirms f_...
- how I know: <the lifted lines you read, the run, the test>
| `f_...` | `Name` | What it does | read |
```

The main session edits the page, runs the check below, commits and pushes.

One address per row, alone in the first cell as `` `f_80652cb0` ``: `fnmap.py` reads a first cell such as
`` `f_8305e390`, `f_8305e4c0` `` or `` `0x84b6ff90` (vtable) `` as no row at all.

## 5. Check the map against the port's code

```sh
LS_REPO=/home/tonesi/Hookshot python3 $M/fnmap.py check --rev forge/main
```

It fails when the port's code (`nx2/oot_*.py`, `host/`) names a game function that has no row, when an address has two
rows, when a row is malformed, or when a page names a patch that does not exist; it notes patched functions whose row
does not say `Hooked by`. Run it after the port's main moved and before adding rows. A function the code names without
a row is the usual way the map falls behind: write its row from the patch's own comment and mark it **tested** only if
the patch ships.

The check looks for `f_<8 hex digits>` spellings only: a game function the port reaches through a hexadecimal
call-target constant is not seen, so inventory those by exact address yourself. `--repo` names the port's clone and
`--rev` the revision it reads (default `HEAD`): a row that documents a patch of a branch not yet on `forge/main` fails
against `forge/main`; check against the branch that holds the patch.

## 6. Game data: a flag in a co-op log, and what co-op shares

The game names its flags by hash only. A co-op log line such as `applied progress <8 hex digits> = 1` says which flag by its hash; the
page `docs/oot/flag-names.md` explains how names are recovered from the player's own files, what stays unnamed and why, and how the
co-op layer sorts flags into categories (and which a default room shares). Two tools, in `flagdata/`, run on the player's own game:

```sh
W=$M/../../flagdata    # (M: the map's folder, section 1)
python3 -I -B $W/coop_log.py LOG                  # each co-op flag line with its flag's name, family, category and default mode
python3 -I -B $W/coop_log.py --summary LOG        # what was applied, held, sent and received, per category and family
python3 -I -B $W/flagdata.py lookup 1a2b3c4d      # one hash
python3 -I -B $W/flagdata.py build --romfs <RomFS> --repo <LS clone> --rev <commit> --out <folder outside any repository>
```

`coop_log.py` reads the private table `build` made under the user's state folder (`$XDG_STATE_HOME/ls-workbench/flagdata`); without it, it
says how to make one. **The names are game data**: outside the workbench repository's flag map they stay in that table, in `--out` and in your
report's files folder, never in a skill, a pull request, an issue or a comment. Look a flag up first in the published flag map:
`python3 docs/oot/flagmap.py find <hash|name|words>` and `show <hash>` (every flag of the game's list, its name where one was recovered,
its save file and group, what co-op does with it; the file layout is `docs/oot/save-format.md`). In LS pull requests, issues and comments
say "a played event of the room's data" or give the hash and the family, not the name; the exceptions are names LS's own source already
quotes. A hash with no name is normal (about half of the list's entries have none): say so, and say the family.

**A value the game re-writes every frame itself** (seen once: an Int whose own code queues it each frame) cannot be set
from outside by a flag set: the applier `f_80bb9980` walks each ring in slot order, so the last slot wins, and the
game's slot is queued after yours. A scan of the pending ring at present time misses the game's slots, because the
drain empties the ring before the next present. Find what the game itself writes each frame and change that source,
as the game's own pickup does (`docs/oot/game-data.md`, "Setting values: the rings").

## 7. Reading the game's data (not code)

The map holds code addresses only. The game's data names (actors, events, flags, maps), its text and its option values
are not in it, in a skill or in anything public: a scenario author reads them from the player's own files, and keeps
the results in the report's files folder (section 6); a skill or a pull request gets the procedure, not the names. The
readers are `$W/fd_romfs.py` (`W` as in section 6; standard library; zstd with the game's own dictionaries, SARC,
BYML, the game's hash): `Romfs(<RomFS folder>).read(<path>)` decodes a `.zs` file, `sarc()` lists a SARC's members,
`byml()` reads a BYML.

```sh
python3 -I -B - $W <RomFS folder> <<'PY'      # every actor pack, one member-path test: seconds
import os, sys
sys.path.insert(0, sys.argv[1])
import fd_romfs as f
r = f.Romfs(sys.argv[2])
for pack in sorted(os.listdir(r.root / "Pack/Actor")):
    if any(m.startswith("<member folder>/") for m in f.sarc(r.read("Pack/Actor/" + pack))):
        print(pack)
PY
```

Reading what each member holds, over every pack, took 3 minutes:
`reports/SharedWorld-files/scan_packs.py` (the harness's `world.game_files.load_mts` and `mts.sarc`) is the template; its
output stays local.

- **Flag names:** the game stores hashes only. `flagdata.py build` already hashes every identifier of the `AI`, `Logic`,
  `Event/EventFlow` and other files against the `GameDataList` (`docs/oot/flag-names.md`); `--names FILE` adds names you
  found. A one-off over other files: `f.murmur3(<string>)` of each string of the decoded file against the `Hash` of
  each entry in `f.byml(r.read("GameData/GameDataList.Product.<n>.byml.zs"))["Data"]["Bool"]`.
- **Game text:** `Mals/<language>.Product.<n>.sarc.zs` is a SARC of `.msbt` files. No reader is in the repository:
  parse each file's `TXT2` section by hand (a count, then each string's offset from the section's data start). The
  strings are NUL-terminated UTF-8 (the encoding byte at offset 12 is 0), not UTF-16.
- **Option values:** `python3 $H/tools/hs_make_save.py --from <save> --flag OptionData.<Name>=?` prints the type and,
  for an enum, the names of its values (`H` as in `skill://ls-workbench`; an option-file value says `not saved in
  progress.sav`: its value is in `option.sav`).

## When this skill let you down

If a lookup that should have worked did not, a step here was wrong or missing, or you needed something the tool cannot
do, say so under **Skill notes** in your report (see `skill://ls-skill-upkeep`). That is how this page gets better.
