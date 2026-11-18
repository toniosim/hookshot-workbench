# Layout panes, text and animations

The game's UI is built from layouts: trees of panes (text, pictures, parts, captures) with animations that show, hide and
move them. These are the functions for finding a pane, setting its text and playing its animations, as the save list, the
menu mouse and the text speed and size options use them.

**LS code:** `host/oot_menu.c` (panes by name and their positions),
`nx2/oot_patches.py` (text speed and size), `host/nn_vi.c` (`hos_text_scale`)
**See also:** [save-list.md](save-list.md), [menus.md](menus.md)

## Panes and text

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_8045c040` | `Layout_PaneTable(layout + 64)` | A layout's pane table: `+256` the array (0xb0 bytes a pane), `+316` the count | tested |
| `f_8045b1f0` | `PaneTable_At(table, i)` | Pane `i` of the table. A pane's flags are at `+168`; bit 0 is "shown" for text panes and the root, but not for panes inside a capture (below) | tested |
| `f_8045b790` | `Layout_FindTextPane(layout, name)` | Finds a **text** pane by name (it skips other kinds) | read |
| `f_8045c4a0` | `Layout_ResolvePath(path, layout, &owner)` | Resolves a pane path ("Pa_Info_00/T_Caption_00"): returns the last name and the layout that holds it | tested |
| `f_8045a9d0` | `TextPane_NameHolder(pane)` | With `f_8045b2a0`, a text pane's name: `f_8045b2a0(f_8045a9d0(pane)+8)`. Other kinds of pane keep no name there | tested |
| `f_8045b2a0` | `TextPane_NameString` | The second half of a text pane's name (above) | tested |
| `f_80a87d30` | `Layout_SetText(layout, pane name, &text, 1, 0)` | Sets a text pane's string. `text` is `{UTF-16 data, length in bytes (32-bit), -1}` | tested |
| `f_8045b970` | `Layout_SetTextWorker` | The text setter's worker (loops over the text panes) | read |
| `f_80a8a480` | `Text_FromMessageName(&text, &source)` | Makes a text from `source` = `{char *data, int size}` **as a label of the message file "LocationMsg/Location"** (the file is fixed in the function; the lookup is `f_80a8b060`, as in `f_80a8afe0`): a plain string that is no label there gives "MsgNotFound" and the answer 0 | tested |
| `f_80a8afe0` | `Text_FromMessage(&text, file, label)` | Makes a text from a message file and a label (the lookup `f_80a8b060`; no message arguments are passed here). A failed lookup gives "MsgNotFound" and the answer 0; `f_80a8a480` is the same with the file fixed | read |
| `f_8379ac00` | `Pane_LayoutNow(obj)` | Makes a layout context in its frame (a default size of 100 x 100 and fixed factors) and runs `Pane_Layout` (`f_8154a820`) on the pane it gets from `[obj+24]`: a layout done at once. That it fits a text to its box is not shown: the sizing is `f_8154a820`'s | read |
| `f_8078e2b0` | `Layout_FindPane(layout, name)` | A pane by name, of any kind (the menu mouse finds the buttons with it). It looks the name up in the layout's own name table first (`f_8045e300`) and returns a hit unless its kind bits (`flags & 0x3c80000`) equal `0x1800000`, a nested-layout instance; then it walks the nested layouts (list head `table+0x128`, first `table+0x130`, next `+8`, name at node `+0x148`) and returns pane 0 of the one with that name. No match returns what the first lookup gave (0 if nothing). The table is `[layout+0x80]` and pane `i` is `[table+0x100] + 0xb0*i` | tested |
| `f_8078fcb0` | `Pane_Position(pane)` | A pane's position: its translation `x, y` (`+0x6c`, `+0x70`) in `s0` and `s1`, and `z` in `s2` (read from the animation track when flag bit 8 is set). Local to the parent, not screen coordinates | tested |
| `f_8152b670` | `TextBox_Draw(box)` | A text box's draw, each time the game shows it (`x0` the box). Hooked by `patch_text_draw`: `hos_prompts_text_draw` first rewrites the box's button-prompt codes when the prompts changed while the game runs, and marks the box to be laid out again (`host/prompts.c`) | read |
| `f_8152aec0` | `TextBox_Layout(box)` | A text box's layout (`x0` the box; the pane's kind 2 call in `Pane_Layout`, `f_8154a820`). It lays the text out and clears status bits `0x40000`, `0x20000` and `0x100000` in the status words at `[box+8]`; which of them makes it lay out again was not confirmed (the port's comment says `0x20000`). Hooked by `patch_text_layout`, which does the same as the draw's hook first (`hos_prompts_text_layout`) | read |
| `f_81680c60` | `ft_smooth_render(…, slot)` | FreeType's smooth glyph renderer (`x1` the glyph slot). Hooked by `patch_glyph`: `hos_prompts_glyph` learns where the game keeps the button prompts' font, for a change while it runs | read |

## The letter animation

Dialogue, Navi and signs show their text letter by letter: the panes with "LetterAnimOn" user data have a LetterAnimControl.

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_80b1e140` | `LetterAnimControl_Step(ctl, s0 = time)` | Steps a text pane's letter animation. The time moves the letters' clock (`+0x60 += rate +0x4c * time`, the rate from the message's speed tag) and the pauses' timer (`+0x58 -= time`); the auto-advance timer (`+0x5c`) is stepped before them, apart. Hooked by `patch_text_speed`: the time is multiplied by `hos_text_scale` (1.0 as shipped), and the pane is handed to the host for the text size | tested |
| `f_80794b00` | `TextWindow_Update(window, pressed)` | A text window's per-frame update (about 440 lines: calls the window's slot 40, adds to its float at `+780`, and so on). One branch, taken when bit 0 of the second argument is set (the A press) and byte `+842` bit 0 is clear, is the game's own skip on A: it sets byte `+841` and the LetterAnimControl's (`[window+688]`) `+0x72` to 2, which shows the page at once. A huge text scale has the same effect without its flags | read |

## Animations

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_802f0f00` | `Anim_Show(anim)` | Puts the animation at its last frame, enabled, and queues it (request 5). The game's "show" | tested |
| `f_802f0fe0` | `Anim_Hide(anim)` | Puts it at frame 0, enabled, and queues it (request 4). The game's "hide", but it only works on a card that has not been changed before (see [Capture panes](#capture-panes)) | tested |
| `f_802f2d90` | `Anim_SetFrame(anim, s0 = frame)` | Puts it at a given frame (heart fills, icon kinds) | read |
| `f_802ee030` | `Anim_Play(anim, loop, s0 = speed)` | Plays it over time at a speed (negative: backwards) | read |
| `f_80bcce80` | `Anim_PlayFade(anim, s0 = speed)` | Plays the screenshot's fade: `f_802ee030` with a layout flag (`f_8045bf30`) | tested |
| `f_802f1340` | `AnimPlayer_Length(player)` | The player's length | read |
| `f_802f1350` | `AnimPlayer_SetFrame(player, s0)` | The player's frame | read |
| `f_802f2b80` | `AnimPlayer_SetEnabled(player, on)` | The player's enabled bit | read |

## Capture panes

A card's base, hearts, Autosave badge and screenshot are drawn into a texture by the capture pane `C_Base_00`, and that texture
is shown by `P_Base_00` (run-time pane 31). The capture is taken once, so changing those parts afterwards does not show: hiding
them, stopping or reversing their animations and clearing their flags all failed on a reused card (tested). The card's text,
its divider and the medallion frame are drawn live, on top.

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_8154ec00` | `CapturePane_Draw` | The capture pane's draw (a 1.7 KB stack frame) | read |
| `f_8154ebc0` | `CapturePane_vtA` | One of the capture pane's other methods (four of them are empty) | read |
| `f_8154ebf0` | `CapturePane_vtB` | Slot 3 (`+0x18`, the one `Pane_Update` calls) of the capture pane's vtable: tail-calls `f_8150d680` with the object at `+8` and two words of its second argument | read |
| `f_8154fc30` | `CapturePane_DeleteThunk` | Slot 9 of the capture pane's vtable block: runs the destructor `f_8154eaa0` on the object and frees it (`Heap_FreeByAddress`, `f_8021dea0`, size 0x10): a deleting destructor | read |

## The pane's update

Each frame the calculate pass visits the panes of a layout (`f_8154a730`). A pane's state word (`+0x00`) holds dirty bits: bit 2 its size, bit 3 its local transform, bit 5 its alpha, bit 6 its global transform. The pane record is under *Structures*.

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_8154a730` | `Pane_Update(pane, ctx)` | A pane's per-frame update: returns at once when the state word (`+0x00`) is 0. For a text pane (kind bits `0x800000`) with state bits `0x60000` set it first calls `f_8152ae70`, then `f_8152bf20`; then for every pane `f_8078a750`, the size step `Pane_Layout` (`f_8154a820`), bit 3 (local transform changed: clears it, `f_8154b9c0`), the alpha step `f_8154c890` (tests bit 5 itself), the matrix step `f_8154caa0` (tests bit 6 itself), and, while any state bit is left, the pane kind's slot 3 (`+0x18`) with a stack argument. Hooked by `UI_SITES` of `nx2/oot_wide.py` (`hos_wide_ui_force`), at its first look at the state word: while the wide HUD forces it, bit 6 is set there, so a pane that never changes still reaches the matrix step | read |
| `f_8154a820` | `Pane_Layout(pane, ctx)` | The part of a pane's update that sizes it: when dirty bit 2 of the state word (`+0x00`) is set it clears it, reads the pane's size (`+0x58`, `+0x5c`; the float at `+0x80` is added to the height, or to the width when flag bit 9 is set, when flag bit 10 is set), derives the origin from flag bits 11 to 17 (two base-3 digits; for the horizontal one 0 is left, 1 centre, 2 right) and lets the pane's kind (flag bits 22 to 25) lay itself out: the text box's layout `f_8152aec0` among others. Read in outline: what each kind's call does was not followed | read |
| `f_8154ac30` | `Pane_GetDrawnSize(pane, out)` | A pane's size as drawn: `(+0x58, +0x5c)`, the float at `+0x80` added to the height (to the width when flag bit 9 is set) when flag bit 10 is set; hands the result to the object in `x1` (`f_8154f830`, then `+0x8c` to `f_8154f880`, ending in `f_8154f840`) together with a scale taken from `+0x74`/`+0x78` (own alpha when flag bit 3 is set, else 1) and the parent's. A capture pane is not drawn through it. Hooked by `UI_SITES` of `nx2/oot_wide.py` (`hos_wide_ui_size`), at the size load, the fifth instruction after its prologue (`0x8154ac40`): a pane that the plan widens is drawn the screen's width. Read in outline | guess |
| `f_8154c890` | `Pane_UpdateAlpha(pane)` | Stores at `+0x78` the pane's alpha with its parents': (`+0x74` if flag bit 3 else 1.0) times the parent's `+0x78` unless flag bit 4; marks the pane and its kind object changed | read |
| `f_8154caa0` | `Pane_CalcMatrix(pane)` | Writes the pane's global 3x4 matrix by column at `+0x28, +0x34, +0x40, +0x4c` (translation `+0x4c,+0x50,+0x54`) from the local scale `+0x60`, translation `+0x6c`, angle (`+0x7c`) and the parent's matrix. Hooked by `UI_SITES` of `nx2/oot_wide.py` (`hos_wide_ui_force`), at its first look at the pane's dirty bits: while the wide HUD forces it, bit 6 is set there, so every pane remakes its transform | read |
| `f_8022a3e0` | `Pane_SetTranslate(pane, s0 x, s1 y, s2 z)` | Sets the pane's translation `x,y` at `+0x6c,+0x70` (z goes to the animation track if the pane has one, flag bit 8) and marks it changed | read |
| `f_8022a390` | `Pane_GetScale(pane)` | Returns the pane's scale `x,y` (`+0x60,+0x64`) in `s0,s1` and z in `s2` (1.0 unless a track) | read |

## The canvas

| Function | Name | What it does | Sure |
|---|---|---|---|
| `f_80794330` | `Canvas_MakeProjection(canvas, view, proj)` | A 2D layout canvas's projection step: loads two 4x4 float matrices (`x1`, `x2`) and multiplies them lane by lane (shuffles and fused multiply-adds), storing the result at `canvas+8` (64 bytes) and the next block at `canvas+72`. The canvas's own projection is the full-screen orthographic one on a 3840 x 2160 grid (`m00 = 2/3840`, `m11 = 2/2160`). LS's wide-HUD patch (`nx2/oot_wide.py`, the `HUD` site at `0x80794368`, the instruction after `ldp q1, q4, [x2]`) squeezes those projection rows when the screen is not 16:9; the canvas is `x0` and its screen sits `0x1b8` before it. Read in outline, the roles of the arguments from the patch | guess |

## Data

| Address | Name | What it is | Sure |
|---|---|---|---|
| `0x8489ad88` | `CapturePane_vtable` | The vtable of the capture pane's kind object (`pane+8`): slot 0 the destructor `f_8154eaa0`, 2 `f_8154ebc0`, 3 `f_8154ebf0`, 4 `f_8154ec00` (the draw), 9 `f_8154fc30`, 10 to 13 empty. The object's word 20 is its texture, 256×208 (a word of the object, not of this table) | tested |

## Structures

### An animation object

| Offset | Field | Sure |
|---|---|---|
| `+16` | A request (32-bit: 4 hide, 5 show) | tested |
| `+20` | Flags | read |
| `+24` | The owner | read |
| `+32` | The player | read |

### An animation player

| Offset | Field | Sure |
|---|---|---|
| `+24` | The frame (float) | read |
| `+28` | Bit 0: enabled | read |

### A LetterAnimControl

| Offset | Field | Sure |
|---|---|---|
| `+0x4c` | The letters' rate (from the message's speed tag) | tested |
| `+0x58` | The pauses' timer | tested |
| `+0x5c` | The auto-advance timer | read |
| `+0x60` | The letters' clock | tested |
| `+0x72` | 2: show the page at once (the skip on A) | read |

### A pane (0xb0 bytes, the table's array `[table+0x100]`)

| Offset | Field | Sure |
|---|---|---|
| `+0x00` | u32: the state and dirty bits: bit 2 size changed (`f_8154a820`), bit 3 local transform changed, bit 5 alpha changed, bit 6 global transform to make (set by the setters) | read |
| `+0x08` | u64: the pane kind object (its slot 3 is called by the update) | read |
| `+0x18` | u64: the owning pane table (used to find the parent) | read |
| `+0x28` | 12 x f32: global matrix, 3x4 by column; translation `+0x4c,+0x50,+0x54`; written by `f_8154caa0` | read |
| `+0x60`, `+0x64` | f32, f32: scale x, y | read |
| `+0x6c`, `+0x70` | f32, f32: translation x, y (z in an animation track) | read |
| `+0x74` | f32: own alpha (used when flag bit 3 is set) | read |
| `+0x78` | f32: alpha with the parents' (written by `f_8154c890`) | read |
| `+0x7c` | f32: the rotation angle in radians (`f_8154caa0` feeds it to a sine and cosine evaluation); set by `f_8154b720`, which was not read | read |
| `+0x84` | 4 x f32: rectangle x, y, w, h | tested |
| `+0xa8` | u32: flags: bit 3 own alpha used, bit 4 ignore parent's alpha, bit 8 animated (a track), bit 9 add `+0x80` to the width instead of the height (with bit 10), bit 10 `+0x80` is added to the size, bits 11 to 17 the origin (two base-3 digits), bits 22 to 25 the kind (`0x3c00000`; 2 text) | read |

## Notes

- Requests are linked into the layout's list (`owner+40` → `+120`), and the screen applies them in its update.
- The UI shows and hides through animations. Pane flags are not a dependable switch.
- Panes found by their place in the table must be checked: the table's order at run time is not the layout file's, and the
  flags at run time are not the file's either (the file has `0x0255481b` where the game has `0x8011386b`).
- `f_80183b70` was listed here as a message-argument setter (`MsgArgs_Set`); it is the game-data manager's Int setter and its
  row is on [game-data.md](game-data.md). The card's date numbers reach the layout's text through game-data Int flags
  ([save-list.md](save-list.md)), which is why the save card calls it. **read**


- **The matrix and the alpha.** `f_8154caa0` stores a 3x4 float matrix by column at `+0x28, +0x34, +0x40, +0x4c` (columns of 3 floats; the translation column is `+0x4c, +0x50, +0x54`; the scale terms are `m[0]` at `+0x28` and `m[4]` at `+0x38`). The same field is what the menu mouse's `button_rect` reads on a button's box: the boxes are pane records too, with the same 0xb0 stride. The alpha at `+0x78` is `own * the parent's`, own being the float at `+0x74` when flag bit 3 is set, else 1.0; the parent is found through the table pointer at `+0x18` and its `+0x78` is multiplied in unless flag bit 4 is set (`f_8154c890`, run from the same update when dirty bit 5 is set). Other fields seen: scale `x, y` at `+0x60, +0x64` (`f_8022a390`), translation `x, y` at `+0x6c, +0x70` (`f_8022a3e0` sets, `Pane_Position` reads). **read** (`f_8154caa0` only its stores: the loads of `+0x6c` and `+0x7c` and the parent's matrix are visible, the algebra between them was not read)
- **A place, not a function.** The port's wide-UI code names `f_8154cab0`, the point where `f_8154caa0` has found dirty bit 6 set and begins to make the transform (the function's first four instructions test and clear the bit). It is the 5th instruction of `f_8154caa0`, not a function start, so it has no row of its own (`undocumented.txt`).

## Open questions

- Read the 12 floats at a minimap pane's `+0x28` and the float at `+0x78` while the minimap shows and while it is hidden: expected scale 1 or the game's zoom at `[0]` and `[4]`, alpha 1.0 shown and 0 hidden (the other co-op project's run saw 0 to 1 together). That would raise the pane-field rows to **tested**.
- What `f_8154b720` sets at `+0x7c` (probably the rotation; not confirmed), and what each pane kind's call in `f_8154a820` does.