# Flag descriptions

What we know a flag is, in our own words: one row for each flag we can describe, joined to the flag map's pages by `flagmap.py build`
(never edit a page by hand: `flagmap.py check` fails when a page disagrees with this file). Where a flag has no row here its name,
if it has one, is all there is.

| Column | Meaning |
|---|---|
| Hash | The flag's hash as the map has it: 8 hexadecimal digits (16 for a per-object key), lower case, once in this file |
| What it is | One sentence of ours (no bar, no newline, no position or coordinate, never the game's code or a value from a save): what the flag means and, where the source says so, what it gates or what co-op does with it |
| Sure | **tested** (seen in a running game, a test run or the game's own log), **read** (from the game's data or graphs, or stated by LS's source or by the function map's pages), **guess** (from the words of a name; use sparingly) |
| Source | Where it comes from: `LS oot_coop.c` and `LS docs/coop.md` (LS's co-op source and notes), `world model` (the test player's model of the game's data: gates, quests), `boss points` (the test player's boss start points and the report that proved them), a page of this folder (`game-data.md`), or the name of a report of the co-op or test work |

The rows were written from LS's `host/oot_coop.c` at `29b087a83` (every list in it), the world model's gates and quest steps, the boss
start points and their report, and the co-op work's reports; the function map's pages gave the known values. The 2,168 story scenes
have no row of their own: a story scene is a played event no other file of the game names (so nothing reads it), and co-op keeps it each
player's own by default ([flag-names.md](../flag-names.md)).

| Hash | What it is | Sure | Source |
|---|---|---|---|
| `9a9506e7` | One of four unsaved Bools that are set while a scene (map) change is in progress; co-op reads and writes no flag while any of them is set. | read | LS oot_coop.c |
| `f8633c7f` | One of four unsaved Bools that are set while a scene (map) change is in progress; co-op reads and writes no flag while any of them is set. | read | LS oot_coop.c |
| `f96989b6` | One of four unsaved Bools that are set while a scene (map) change is in progress; co-op reads and writes no flag while any of them is set. | read | LS oot_coop.c |
| `e19dfdd6` | One of four unsaved Bools that are set while a scene (map) change is in progress; co-op reads and writes no flag while any of them is set. | read | LS oot_coop.c |
| `01c20002` | Set once Link has learned Zelda's Lullaby; co-op counts the 13 songs as one category (coop_songs) and shares them between players by default. | read | LS oot_coop.c |
| `b492ac33` | Set once Link has learned Epona's Song; co-op counts the 13 songs as one category (coop_songs) and shares them between players by default. | read | LS oot_coop.c |
| `d3f8bfcc` | Set once Link has learned Saria's Song; co-op counts the 13 songs as one category (coop_songs) and shares them between players by default. | read | LS oot_coop.c |
| `165dd1ad` | Set once Link has learned the Sun's Song; co-op counts the 13 songs as one category (coop_songs) and shares them between players by default. | read | LS oot_coop.c |
| `03b3450e` | Set once Link has learned the Song of Time; co-op counts the 13 songs as one category (coop_songs) and shares them between players by default. | read | LS oot_coop.c |
| `2b39dd4f` | Set once Link has learned the Song of Storms; co-op counts the 13 songs as one category (coop_songs) and shares them between players by default. | read | LS oot_coop.c |
| `dc0a0b54` | Set once Link has learned the Minuet of Forest; co-op counts the 13 songs as one category (coop_songs) and shares them between players by default. | read | LS oot_coop.c |
| `49041ab9` | Set once Link has learned the Bolero of Fire; co-op counts the 13 songs as one category (coop_songs) and shares them between players by default. | read | LS oot_coop.c |
| `3fa63986` | Set once Link has learned the Serenade of Water; co-op counts the 13 songs as one category (coop_songs) and shares them between players by default. | read | LS oot_coop.c |
| `c2fb95f4` | Set once Link has learned the Nocturne of Shadow; co-op counts the 13 songs as one category (coop_songs) and shares them between players by default. | read | LS oot_coop.c |
| `802a36a8` | Set once Link has learned the Requiem of Spirit; co-op counts the 13 songs as one category (coop_songs) and shares them between players by default. | read | LS oot_coop.c |
| `d6320ba4` | Set once Link has learned the Prelude of Light; co-op counts the 13 songs as one category (coop_songs) and shares them between players by default. | read | LS oot_coop.c |
| `5e86fb4d` | Set once Link has learned the Scarecrow's Song; co-op counts the 13 songs as one category (coop_songs) and shares them between players by default. | read | LS oot_coop.c |
| `6b8fc751` | Heart-piece reward flag from the business scrub on Death Mountain; co-op keeps heart rewards each player's own (a shared count would pay twice). | read | LS oot_coop.c |
| `1d1793e9` | Heart-piece reward flag from the Goron's large pot; co-op keeps heart rewards each player's own (a shared count would pay twice). | read | LS oot_coop.c |
| `b5127e75` | Heart-piece reward flag from the graveyard's digging tour; co-op keeps heart rewards each player's own (a shared count would pay twice). | read | LS oot_coop.c |
| `e41e1597` | Heart-piece reward flag from the business scrub in Hyrule Field; co-op keeps heart rewards each player's own (a shared count would pay twice). | read | LS oot_coop.c |
| `98ca7aab` | Taken flag of the Deku Tree's heart container, the only heart flag the data names for a boss; co-op keeps it each player's own, never shared. | read | LS oot_coop.c |
| `f1891f6e` | Heart-piece reward flag from the fishing minigame; co-op keeps heart rewards each player's own (a shared count would pay twice). | read | LS oot_coop.c |
| `3f43245b` | Heart-piece reward flag from the horseback archery minigame; co-op keeps heart rewards each player's own (a shared count would pay twice). | read | LS oot_coop.c |
| `1657d7d8` | Heart-piece reward flag from the Skull Kid's playing session; co-op keeps heart rewards each player's own (a shared count would pay twice). | read | LS oot_coop.c |
| `a666baa8` | Heart-piece reward flag from a Hyrule townsperson; co-op keeps heart rewards each player's own (a shared count would pay twice). | read | LS oot_coop.c |
| `5ff7aa30` | Heart-piece reward flag from the child Skull Kid; co-op keeps heart rewards each player's own (a shared count would pay twice). | read | LS oot_coop.c |
| `f2fab510` | Heart-piece reward flag from the find-Richard side quest; co-op keeps heart rewards each player's own (a shared count would pay twice). | read | LS oot_coop.c |
| `0dcdd8ed` | Played flag of a Fire Temple cutscene that the game's code reads (LS found it there), so it stays shared even when story scenes are per player. | read | LS oot_coop.c |
| `19984997` | Played flag of a Fire Temple cutscene that the game's code reads (LS found it there), so it stays shared even when story scenes are per player. | read | LS oot_coop.c |
| `1f1ea94d` | Played flag of a Fire Temple cutscene that the game's code reads (LS found it there), so it stays shared even when story scenes are per player. | read | LS oot_coop.c |
| `2e91309b` | Played flag of a Fire Temple cutscene that the game's code reads (LS found it there), so it stays shared even when story scenes are per player. | read | LS oot_coop.c |
| `42f2a2b5` | Played flag of a Fire Temple cutscene that the game's code reads (LS found it there), so it stays shared even when story scenes are per player. | read | LS oot_coop.c |
| `44ca113d` | Played flag of a Fire Temple cutscene that the game's code reads (LS found it there), so it stays shared even when story scenes are per player. | read | LS oot_coop.c |
| `6c763708` | Played flag of a Fire Temple cutscene that the game's code reads (LS found it there), so it stays shared even when story scenes are per player. | read | LS oot_coop.c |
| `ac8176c5` | Played flag of a Fire Temple cutscene that the game's code reads (LS found it there), so it stays shared even when story scenes are per player. | read | LS oot_coop.c |
| `ace7885f` | Played flag of a Fire Temple cutscene that the game's code reads (LS found it there), so it stays shared even when story scenes are per player. | read | LS oot_coop.c |
| `15b67d0e` | Played flag of the opening that the game's code reads (LS found it there), so it stays shared even when story scenes are per player. | read | LS oot_coop.c |
| `47607f90` | Played flag of a talk with Kaepora at Zora's River that the game's code reads (LS found it there), so it stays shared even when story scenes are per player. | read | LS oot_coop.c |
| `48d0a2b4` | Played flag of the Song of Storms played at the Desert Colossus that the game's code reads (LS found it there), so it stays shared even when story scenes are per player. | read | LS oot_coop.c |
| `60992704` | Played flag of a Hyrule Field cutscene that the game's code reads (LS found it there), so it stays shared even when story scenes are per player. | read | LS oot_coop.c |
| `78525c68` | Played flag of a Kokiri Forest cutscene that the game's code reads (LS found it there), so it stays shared even when story scenes are per player. | read | LS oot_coop.c |
| `78a420f6` | Played flag of the Ocarina of Time scene at the Door of Time that the game's code reads (LS found it there), so it stays shared even when story scenes are per player. | read | LS oot_coop.c |
| `a8bf4fdd` | Played flag of a graveyard cutscene that the game's code reads (LS found it there), so it stays shared even when story scenes are per player. | read | LS oot_coop.c |
| `e9235fd3` | Played flag of a Shadow Temple cutscene that the game's code reads (LS found it there), so it stays shared even when story scenes are per player. | read | LS oot_coop.c |
| `f66ceb94` | Played flag of a Goron City cutscene that the game's code reads (LS found it there), so it stays shared even when story scenes are per player. | read | LS oot_coop.c |
| `692d57cb` | Count of the Forest Medallion held (1 once Link has it); co-op treats it as a quest item and shares it between players by default (coop_quest). | read | LS oot_coop.c |
| `5ce254a6` | Count of the Fire Medallion held (1 once Link has it); co-op treats it as a quest item and shares it between players by default (coop_quest). | read | LS oot_coop.c |
| `0151a68f` | Count of the Water Medallion held (1 once Link has it); co-op treats it as a quest item and shares it between players by default (coop_quest). | read | LS oot_coop.c |
| `0c7a5fd0` | Count of the Spirit Medallion held (1 once Link has it); co-op treats it as a quest item and shares it between players by default (coop_quest). | read | LS oot_coop.c |
| `204d2063` | Count of the Shadow Medallion held (1 once Link has it); co-op treats it as a quest item and shares it between players by default (coop_quest). | read | LS oot_coop.c |
| `235c7d9a` | Count of the Light Medallion held (1 once Link has it); co-op treats it as a quest item and shares it between players by default (coop_quest). | read | LS oot_coop.c |
| `cbd1e58c` | Count of Kokiri's Emerald held (1 once Link has it); co-op treats it as a quest item and shares it between players by default (coop_quest). | read | LS oot_coop.c |
| `7d69ad47` | Count of Goron's Ruby held (1 once Link has it); co-op treats it as a quest item and shares it between players by default (coop_quest). | read | LS oot_coop.c |
| `b8e3bf45` | Count of Zora's Sapphire held (1 once Link has it); co-op treats it as a quest item and shares it between players by default (coop_quest). | read | LS oot_coop.c |
| `f3b14ce2` | Count of the Stone of Agony held (1 once Link has it); co-op treats it as a quest item and shares it between players by default (coop_quest). | read | LS oot_coop.c |
| `feb4d56b` | Count of Gerudo's Card held (1 once Link has it); co-op treats it as a quest item and shares it between players by default (coop_quest). | read | LS oot_coop.c |
| `07f10aaf` | Count of the Pocket Egg, a trading-sequence item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `0165e7ca` | Count of the Pocket Cucco, a trading-sequence item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `51d89ef0` | Count of Cojiro the Cucco, a trading-sequence item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `07de3e6f` | Count of the Odd Mushroom, a trading-sequence item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `58c9bc78` | Count of the Odd Powder, a trading-sequence item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `a862d276` | Count of the Poacher's Saw, a trading-sequence item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `2815c82a` | Count of the broken sword, a trading-sequence item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `897cf7eb` | Count of the Prescription, a trading-sequence item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `919ea324` | Count of the Eyeball Frog, a trading-sequence item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `5c41a6b1` | Count of the Eye Drops, a trading-sequence item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `ded8e8d3` | Count of the Claim Check, a trading-sequence item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `24596e8e` | Count of the Weird Egg, a trading-sequence item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `b6ca6093` | Count of the alarm Cucco, a trading-sequence item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `6be5c3b0` | Count of Zelda's Letter, a trading-sequence item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `7e607033` | Count of the Bunny Hood, a rented mask the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `0e94a8df` | Count of the Gerudo Mask, a rented mask the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `fc508da7` | Count of the Goron Mask, a rented mask the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `b5c10899` | Count of the Keaton Mask, a rented mask the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `47b2d775` | Count of the Skull Mask, a rented mask the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `f046629e` | Count of the Spooky Mask, a rented mask the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `96459cd3` | Count of the Mask of Truth, a rented mask the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `924e9a46` | Count of the Zora Mask, a rented mask the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `f5e647da` | Count of an amiibo mask, an item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `486c59a4` | Count of an amiibo mask, an item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `20820479` | Count of the amiibo pouch, an amiibo-linked item; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `396a5c02` | Count of the Giant's Knife, the knife that can break; co-op keeps this count each player's own (own_counts). | read | LS docs/coop.md |
| `8d02f5ea` | Count of the broken Giant's Knife, the knife that breaks; co-op keeps this count each player's own (own_counts). | read | LS docs/coop.md |
| `600e29eb` | Count of the business scrub's seed item; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `51ec97b3` | Heart pieces held toward the next heart; co-op keeps the count each player's own, since a shared count would pay twice. | read | LS docs/coop.md |
| `04735978` | Gold Skulltula tokens collected; co-op keeps this count each player's own, since a shared count would pay twice. | read | LS docs/coop.md |
| `d1317941` | Count of the Goron's Bracelet; it arrived in a second game through the room (pair run); co-op then raises LiftGrade to Low so Link can lift bombs. | tested | PreMergeChecks |
| `0012b8c0` | Count of the Silver Gauntlets; after the room gives them, co-op raises PlayerStatus.LiftGrade to Middle so Link can lift bigger objects. | read | LS oot_coop.c |
| `40ae1183` | Count of the Golden Gauntlets; after the room gives them, co-op raises PlayerStatus.LiftGrade to High so Link can lift the heaviest objects. | read | LS oot_coop.c |
| `59979321` | What Link can lift (None, Low, Middle, High); co-op never shares it but raises it when a strength item arrives; before that, a pair run left game B at None. | tested | PreMergeChecks |
| `db1bcd4f` | How many bombs Link holds (capped by the bomb bag); ammunition is each player's own by default and can be pooled by the room (coop_ammo). | read | LS oot_coop.c |
| `df7c517a` | How many bombchus Link holds; ammunition is each player's own by default and can be pooled by the room (coop_ammo). | read | LS oot_coop.c |
| `518ec74b` | How many arrows Link holds (capped by the quiver); ammunition is each player's own by default and can be pooled by the room (coop_ammo). | read | LS oot_coop.c |
| `f30d9f54` | How many Deku Nuts Link holds (capped by the nut bag); ammunition is each player's own by default and can be pooled by the room (coop_ammo). | read | LS oot_coop.c |
| `5fadf7fc` | How many Deku Seeds Link holds (capped by the seed bag); ammunition is each player's own by default and can be pooled by the room (coop_ammo). | read | LS oot_coop.c |
| `b9494411` | How many Deku Sticks Link holds (capped by the stick bag); ammunition is each player's own by default and can be pooled by the room (coop_ammo). | read | LS oot_coop.c |
| `b003124d` | How many magic beans Link holds; ammunition is each player's own by default and can be pooled by the room (coop_ammo). | read | LS oot_coop.c |
| `7dd79d10` | Small keys held for Bottom of the Well; co-op pools the count by default (rule coop_keys) so every player adds to and spends from one total. | read | LS oot_coop.c |
| `3fdbc3d0` | Small keys held for Dodongo's Cavern; co-op pools the count by default (rule coop_keys) so every player adds to and spends from one total. | read | LS oot_coop.c |
| `a04bfd48` | Small keys held for Ganon's arena (FinalBattleField); co-op pools the count by default (rule coop_keys) so every player adds to and spends from one total. | read | LS oot_coop.c |
| `1df11487` | Small keys held for Fire Temple; co-op pools the count by default (rule coop_keys) so every player adds to and spends from one total. | read | LS oot_coop.c |
| `90237092` | Small keys held for the Forest Temple, pooled by co-op; in a two-game run one chest raised both players' count from 3 to 4 (no double give). | tested | ChestDedupe |
| `3a28b6a4` | Small keys held for Gerudo Fortress; co-op pools the count by default (rule coop_keys) so every player adds to and spends from one total. | read | LS oot_coop.c |
| `ea9786f5` | Small keys held for Gerudo Training Ground; co-op pools the count by default (rule coop_keys) so every player adds to and spends from one total. | read | LS oot_coop.c |
| `fa5d133d` | Small keys held for Ice Cavern; co-op pools the count by default (rule coop_keys) so every player adds to and spends from one total. | read | LS oot_coop.c |
| `fbfd2910` | Small keys held for Ganon's Castle; co-op pools the count by default (rule coop_keys) so every player adds to and spends from one total. | read | LS oot_coop.c |
| `1470a816` | Small keys held for Jabu-Jabu's Belly; co-op pools the count by default (rule coop_keys) so every player adds to and spends from one total. | read | LS oot_coop.c |
| `0914ba07` | Small keys held for Deku Tree; co-op pools the count by default (rule coop_keys) so every player adds to and spends from one total. | read | LS oot_coop.c |
| `5edda9e3` | Small keys held for Shadow Temple; co-op pools the count by default (rule coop_keys) so every player adds to and spends from one total. | read | LS oot_coop.c |
| `79eeec8e` | Small keys held for Spirit Temple; co-op pools the count by default (rule coop_keys) so every player adds to and spends from one total. | read | LS oot_coop.c |
| `877bdcee` | Small keys held for Water Temple; co-op pools the count by default (rule coop_keys) so every player adds to and spends from one total. | read | LS oot_coop.c |
| `77c47ec9` | Set once Link has the map of Bottom of the Well; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `9d6efaac` | Set once Link has the compass of Bottom of the Well; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `9402715c` | Set once Link has the boss key of Bottom of the Well; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `a52c3a19` | Set once Link has the map of Dodongo's Cavern; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `8b93edf9` | Set once Link has the compass of Dodongo's Cavern; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `faabc084` | Set once Link has the boss key of Dodongo's Cavern; the game has the flag but that boss door has no lock; co-op shares it and refreshes the HUD map after a hand-over. | read | boss points |
| `b3b65c1a` | Set once Link has the map of Ganon's arena (FinalBattleField); co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `874493ce` | Set once Link has the compass of Ganon's arena (FinalBattleField); co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `6d0fea11` | Set once Link has the boss key of Ganon's arena (FinalBattleField); co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `5b3ac0ba` | Set once Link has the map of Fire Temple; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `0aa068b6` | Set once Link has the compass of Fire Temple; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `b72d73df` | Set once Link has the boss key of Fire Temple; BossPoints reads it as what the chained boss door needs; co-op shares it and refreshes the HUD afterwards. | read | boss points |
| `e704f9b4` | Set once Link has the map of Forest Temple; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `f240eeb2` | Set once Link has the compass of Forest Temple; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `427333a0` | Set once Link has the boss key of Forest Temple; test saves set it and the boss door opened (BossPoints); co-op shares it and refreshes the HUD afterwards. | tested | boss points |
| `bcaad6ce` | Set once Link has the map of Gerudo Fortress; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `5eb80679` | Set once Link has the compass of Gerudo Fortress; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `95fbcb7c` | Set once Link has the boss key of Gerudo Fortress; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `4b36041e` | Set once Link has the map of Gerudo Training Ground; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `3d9a2750` | Set once Link has the compass of Gerudo Training Ground; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `6d155841` | Set once Link has the boss key of Gerudo Training Ground; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `322f2a94` | Set once Link has the map of Ice Cavern; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `ea1846e6` | Set once Link has the compass of Ice Cavern; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `275f4512` | Set once Link has the boss key of Ice Cavern; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `9bbc0c4a` | Set once Link has the map of Ganon's Castle; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `c4d4734e` | Set once Link has the compass of Ganon's Castle; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `2fd59293` | Set once Link has the boss key of Ganon's Castle; test saves set it and the boss door opened (BossPoints); co-op shares it and refreshes the HUD afterwards. | tested | boss points |
| `fcadd210` | Set once Link has the map of Jabu-Jabu's Belly; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `9a2218db` | Set once Link has the compass of Jabu-Jabu's Belly; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `656bd5ee` | Set once Link has the boss key of Jabu-Jabu's Belly; the game has the flag but that boss door has no lock; co-op shares it and refreshes the HUD map after a hand-over. | read | boss points |
| `89787395` | Set once Link has the Deku Tree's map; co-op shares it and refreshes the HUD about 300 ms later; in a two-game run the other player's minimap lit up. | tested | Fold68 |
| `06c51ff2` | Set once Link has the compass of Deku Tree; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `f6995cee` | Set once Link has the boss key of Deku Tree; the game has the flag but that boss door has no lock; co-op shares it and refreshes the HUD map after a hand-over. | read | boss points |
| `f6177b93` | Set once Link has the map of Shadow Temple; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `1e2feec5` | Set once Link has the compass of Shadow Temple; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `c33c66cf` | Set once Link has the boss key of Shadow Temple; test saves set it and the boss door opened (BossPoints); co-op shares it and refreshes the HUD afterwards. | tested | boss points |
| `b85002ba` | Set once Link has the map of Spirit Temple; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `9bd1181c` | Set once Link has the compass of Spirit Temple; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `1984c03f` | Set once Link has the boss key of Spirit Temple; test saves set it and the boss door opened (BossPoints); co-op shares it and refreshes the HUD afterwards. | tested | boss points |
| `4a4402ab` | Set once Link has the map of Water Temple; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `2e82c8fe` | Set once Link has the compass of Water Temple; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `79daf80a` | Set once Link has the boss key of Water Temple; test saves set it and the boss door opened (BossPoints); co-op shares it and refreshes the HUD afterwards. | tested | boss points |
| `a77921d7` | Rupees Link holds; each player's own by default, poolable by the room (coop_rupees). Seen rising 0 to 5 in a test run after a blue rupee. | tested | PlayHarness |
| `12d63a97` | Size of Link's magic meter (240 single, 480 double); the room shares the size, and in a pair run it arrived in game B without any magic in it. | tested | PreMergeChecks |
| `b7df60f1` | Count of the Fairy Ocarina (0 to 1 when Link got it from a chest in a test run); co-op names it for the D-pad when the room gives one. | tested | ClawshotChests |
| `54e2a3d1` | Count of the Ocarina of Time; when the room gives it, co-op writes its name into the equipped-ocarina string, never replacing it with a lower ocarina. | read | LS docs/coop.md |
| `b72cd3fc` | Name of the ocarina that D-pad Left takes out ("" until Link has one); co-op writes it for a player given an ocarina; seen working in a two-game run. | tested | Fold68 |
| `e573f564` | The save's total play time, never reset by an area change; co-op uses it to see the game's clock standing (pause) or another save loading. | read | LS oot_coop.c |
| `e53eb6d1` | Older counter of seconds in the current area; every area change reset it, so LS no longer uses it to tell a load from an area change. | read | LS oot_coop.c |
| `f5deef0a` | Set while a save is being loaded; co-op reads and writes nothing until it clears. | read | LS oot_coop.c |
| `1d6189da` | Name of the map Link is in; co-op reads it to tell a boss dungeon or the dream world; the harness's reading matched the pictures in test runs. | tested | PlayHarness |
| `3da094e3` | Struct holding one sub-struct per item with its count; co-op reads it to find the item counts to share. | read | LS oot_coop.c |
| `ade0ef78` | Struct of the "got it once" markers, one per item; co-op reads it to find the first-get flags to share. | read | LS oot_coop.c |
| `f5a32cdc` | Struct with one entry per dungeon: map, compass, boss key and small keys; co-op reads it for the key counters and the HUD map flags. | read | LS oot_coop.c |
| `f80f8077` | Struct of the six capacities (wallet, bomb bag, quiver, seed bag, stick and nut sizes) that cap the counts co-op shares. | read | LS oot_coop.c |
| `418db791` | Capacity of the quiver (arrows): the most Link can carry; it is an item value co-op shares, and caps the matching pooled count. | read | LS oot_coop.c |
| `457616b0` | Capacity of the stick bag (Deku Sticks): the most Link can carry; it is an item value co-op shares, and caps the matching pooled count. | read | LS oot_coop.c |
| `735b00f7` | Capacity of the nut bag (Deku Nuts): the most Link can carry; it is an item value co-op shares, and caps the matching pooled count. | read | LS oot_coop.c |
| `ae8cc742` | Capacity of the seed bag (Deku Seeds): the most Link can carry; it is an item value co-op shares, and caps the matching pooled count. | read | LS oot_coop.c |
| `e0010a50` | Capacity of the wallet (rupees): the most Link can carry; it is an item value co-op shares, and caps the matching pooled count. | read | LS oot_coop.c |
| `e753508b` | Capacity of the bomb bag (bombs): the most Link can carry; it is an item value co-op shares, and caps the matching pooled count. | read | LS oot_coop.c |
| `e44433dc` | Door that shuts behind whoever enters Queen Gohma's room; one player's own fight state, so LS never shares it (shared, it locked others out). | read | LS oot_coop.c |
| `88b1b922` | Switches the Deku Tree boss arena's environment for the fight; one player's own state, never shared by LS (also a fight flag of Gohma's set). | read | LS oot_coop.c |
| `f0adbc2e` | Set when Bongo Bongo's fight starts in the Shadow Temple; one player's own state, kept each game's own by LS. | read | LS oot_coop.c |
| `3822d87a` | Set while a player has entered Ganondorf's boss room in Ganon's Castle; one player's own state, kept each game's own by LS. | read | LS oot_coop.c |
| `8046b089` | King Dodongo's arena floor change, set as his fight ends; LS keeps it each game's own, though his end set writes it back to a game that did not fight. | read | LS oot_coop.c |
| `0d94327f` | Volvagia's arena floor change, set as her fight ends; LS keeps it each game's own, though her end set writes it back to a game that did not fight. | read | LS oot_coop.c |
| `cea220d3` | True while Link is a child (starts true); a player's age is his own, so LS never shares it (shared, it turned child players adult). | read | LS oot_coop.c |
| `ece4e747` | Position flag: Link is in the Forest Temple's falling-ceiling room; a room sensor sets and clears it; one player's own, so LS never shares it. | read | LS docs/coop.md |
| `aa70c440` | Position flag: Link is left of the Forest Temple's Song of Time block; one player's own, so LS never shares it: set in one game it never reached the other (pair run). | tested | Fold68 |
| `4777f331` | Position flag: Link is in the centre area of Bottom of the Well room 1; a room sensor sets and clears it; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `c6a4aa65` | Position flag: Link is in the diving area of Bottom of the Well room 1; a room sensor sets and clears it; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `99da5f45` | Position flag: Link is in the return area of Bottom of the Well room 1; a room sensor sets and clears it; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `5601772d` | Position flag: Link is near the rock in Bottom of the Well room 9; a room sensor sets and clears it; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `7d1f6539` | Position flag: the player is out of Dodongo's Cavern room 10; a room sensor sets and clears it; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `6aaaf7d2` | Position flag: Link is at the correct area in Fire Temple room 4; a room sensor sets and clears it; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `bfe66553` | Position flag: Link is at the correct area in Fire Temple room 12; a room sensor sets and clears it; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `7c5d6ee1` | Position flag: Link is near the climbable ivy in Forest Temple room 8; a room sensor sets and clears it; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `ef8de0e5` | Position flag: Link is in the secret room of Gerudo Training Ground room 3; a room sensor sets and clears it; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `fe3d998c` | Position flag: Link is in the secret room of Gerudo Training Ground room 8; a room sensor sets and clears it; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `111201d5` | Position flag: Link is far from the demo point of Ice Cavern room 1; a room sensor sets and clears it; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `f99477ee` | Position flag: Link is at the chest near Ruto in Jabu-Jabu's room 9; a room sensor sets and clears it; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `c3cf4176` | Position flag: Link is at the chest near Ruto in Jabu-Jabu's room 12; a room sensor sets and clears it; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `d0440e02` | Position flag: Link is near the gimmick of Jabu-Jabu's room 14; a room sensor sets and clears it; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `afd95a4a` | Position flag: the player is underneath in Jabu-Jabu's room 14; a room sensor sets and clears it; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `3d1102e5` | Position flag: Link is in the hidden area of Jabu-Jabu's room 18; a room sensor sets and clears it; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `e27b79a0` | Position flag: Link is near the scaffold in Deku Tree room A; a room sensor sets and clears it; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `645bf023` | Position flag: Link is away from the spot in Shadow Temple room 9; a room sensor sets and clears it; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `89758470` | Position flag: the player-position check of Shadow Temple room 13; a room sensor sets and clears it; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `9121e5ba` | Position flag: one of four player-position flags of Spirit Temple room 2; a room sensor sets and clears it; one player's own, so LS never shares it. | read | LS docs/coop.md |
| `58b66e09` | Position flag: one of four player-position flags of Spirit Temple room 2; a room sensor sets and clears it; one player's own, so LS never shares it. | read | LS docs/coop.md |
| `1632014b` | Position flag: one of four player-position flags of Spirit Temple room 2; a room sensor sets and clears it; one player's own, so LS never shares it. | read | LS docs/coop.md |
| `2ea866dc` | Position flag: one of four player-position flags of Spirit Temple room 2; a room sensor sets and clears it; one player's own, so LS never shares it. | read | LS docs/coop.md |
| `833295b6` | Position flag: the player-position check of Spirit Temple room 16; a room sensor sets and clears it; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `c0f55710` | Position flag: Link is near the switch's platform in Water Temple room 0; a room sensor sets and clears it; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `2f3bb3de` | Position flag: Link is near the switch's shutter in Water Temple room 0; a room sensor sets and clears it; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `3b9398e7` | Set while a player is in the Water Temple's Dark Link room; one player's own, kept each game's own by LS. | read | LS docs/coop.md |
| `127c57f8` | Set while a player's Dark Link fight is on; one player's own: set in one game it never reached the other in a two-game run. | tested | Fold68 |
| `670a179c` | Which side of the door a player stands on in the Water Temple's Dark Link room; kept each game's own by LS. | read | LS docs/coop.md |
| `3ff7a89a` | Whether a player is on the right side of the Water Temple's Dark Link room; kept each game's own by LS. | read | LS docs/coop.md |
| `e1006e4c` | Whether a player is on the right side of Water Temple room 2; kept each game's own by LS. | read | LS docs/coop.md |
| `a0c0e173` | Whether a player is on the right side of Ice Cavern room 7; kept each game's own by LS. | read | LS docs/coop.md |
| `15c45ec4` | Set while a player is in the water source of Bottom of the Well room 1; kept each game's own by LS. | read | LS docs/coop.md |
| `f0368aad` | Records that one player's try at Deku Tree room K failed; set by the room graph, read by none; in a two-game run it stayed in the game that set it. | tested | Fold68 |
| `55e67eba` | Records that one player's switch in Fire Temple room 8 was reset (a failed try); set by a room graph, read by none, so LS keeps it each game's own. | read | LS oot_coop.c |
| `92ac81e8` | Records that one player's switch in Fire Temple room 10 was reset (a failed try); set by a room graph, read by none, so LS keeps it each game's own. | read | LS oot_coop.c |
| `0e86f3db` | Records that one player's switch in Fire Temple room 13 was reset (a failed try); set by a room graph, read by none, so LS keeps it each game's own. | read | LS oot_coop.c |
| `e5ba1fc5` | Records that one player's candle in Ganon's Castle room 8 was reset (a failed try); set by a room graph, read by none; LS keeps it each game's own. | read | LS oot_coop.c |
| `85dc97ff` | Unnamed Bottom of the Well room Bool: a pot or grass refill that comes back for a player with none; one player's own: set in one game, it stayed there in a two-game run. | tested | Fold68 |
| `9c7297e5` | Unnamed Bottom of the Well room Bool: a pot or grass refill that comes back for a player with none; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `bf6652d9` | Unnamed Bottom of the Well room Bool: a pot or grass refill that comes back for a player with none; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `aecf3cfe` | Unnamed Dodongo's Cavern room Bool: a gossip stone's fairy; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `bd902a5b` | Unnamed Forest Temple room Bool: a pot or grass refill that comes back for a player with none; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `58445aa7` | Unnamed Gerudo Training Ground room Bool: a pot or grass refill that comes back for a player with none; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `cfcfd932` | Unnamed Gerudo Training Ground room Bool: a pot or grass refill that comes back for a player with none; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `9de51737` | Unnamed Ganon's Castle room Bool: a record that one player walked into an area; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `21958973` | Unnamed Deku Tree room Bool: a pot or grass refill that comes back for a player with none; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `fe6d1779` | Unnamed Deku Tree room Bool: a pot or grass refill that comes back for a player with none; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `0fa9d971` | Unnamed Shadow Temple room Bool: a pot or grass refill that comes back for a player with none; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `20062808` | Unnamed Shadow Temple room Bool: a pot or grass refill that comes back for a player with none; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `47c1b028` | Unnamed Shadow Temple room Bool: a pot or grass refill that comes back for a player with none; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `695215f6` | Unnamed Shadow Temple room Bool: a pot or grass refill that comes back for a player with none; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `186adf43` | Unnamed Spirit Temple room Bool: a pot or grass refill that comes back for a player with none; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `291f87b2` | Malon's appearance in the Market (a set-and-clear by the game's logic, not progress); LS keeps it each game's own so a 1 never comes back. | read | LS oot_coop.c |
| `fd1b310e` | Malon's appearance at Hyrule Castle the second time (a set-and-clear by the game's logic, not progress); LS keeps it each game's own. | read | LS oot_coop.c |
| `c6724c2e` | Kokiri guard flag in Kokiri Forest, set and cleared again by the game's own logic; LS keeps it each game's own so a 1 never comes back. | read | LS oot_coop.c |
| `a1eb22e6` | Kokiri guard flag in the Lost Woods, set and cleared again by the game's own logic; LS keeps it each game's own so a 1 never comes back. | read | LS oot_coop.c |
| `f0fde374` | Kokiri guard flag at the forest exit (a child Kokiri's blocker), set and cleared again by the game's own logic; LS keeps it each game's own. | read | LS oot_coop.c |
| `6b093b51` | Proof of Queen Gohma's defeat: her own defeat flag, set by the end of the fight. In a two-game run the other game held it, then was given the end set once. | tested | Fold68 |
| `3419ccb3` | Proof of Queen Gohma's defeat: the played flag of her death setting. In a two-game run the other game held it, then was given the end set once. | tested | Fold68 |
| `5882768c` | Proof of Queen Gohma's defeat: the played flag of her outro cutscene. In a two-game run the other game held it, then was given the end set once. | tested | Fold68 |
| `00c0a2f6` | Part of Queen Gohma's end set: the played flag of her intro cutscene; written with the proof to a game that did not fight, never alone. | read | LS oot_coop.c |
| `3d5c0bad` | Fight flag of Queen Gohma: the room lighting for her battle, set when the fight begins; each game keeps its own, so co-op never sends or takes it. | read | LS oot_coop.c |
| `6eef10c6` | Played flag of Gohma's appearance scene; BossPoints watches it as the sign her fight began (never seen to rise in a hold); each game's own in co-op. | read | boss points |
| `ffde6400` | Fight flag of Queen Gohma: the played flag of the scene when the boss door shuts behind Link; each game keeps its own, so co-op never sends or takes it. | read | LS oot_coop.c |
| `7f08acdb` | Fight flag of Queen Gohma: the played flag of the cutscene after the door shuts; each game keeps its own, so co-op never sends or takes it. | read | LS oot_coop.c |
| `66b97a4a` | Fight flag of Queen Gohma: the played flag of the boss-area warp (the way out); each game keeps its own, so co-op never sends or takes it. | read | LS oot_coop.c |
| `1776df84` | Fight flag of Queen Gohma: the played flag of the cutscene the boss-area warp plays; each game keeps its own, so co-op never sends or takes it. | read | LS oot_coop.c |
| `c1df671e` | Proof of King Dodongo's defeat: the played flag of his death setting. Co-op holds it back and writes the boss's end set once every proof is here. | read | LS oot_coop.c |
| `764b65d6` | Proof of King Dodongo's defeat: the played flag of his outro cutscene. Co-op holds it back and writes the boss's end set once every proof is here. | read | LS oot_coop.c |
| `a3003ce0` | Played flag of King Dodongo's intro cutscene, part of his end set; BossPoints watches it with the appearance flag (no hold saw his fight start). | read | boss points |
| `e7922fed` | Appear flag of King Dodongo: 1 while he is present, back to 0 as the fight ends; both a fight flag each game keeps and a member his end set writes (as 0). | read | LS oot_coop.c |
| `7653b7e0` | Played flag of King Dodongo's appearance scene; BossPoints expects it to rise when the fight starts (not yet seen); each game's own in co-op. | read | boss points |
| `c930ec0e` | Proof of Barinade's defeat: the played flag of his death setting. Co-op holds it back and writes the boss's end set once every proof is here. | read | LS oot_coop.c |
| `8ad33d7f` | Proof of Barinade's defeat: the played flag of his outro cutscene. Co-op holds it back and writes the boss's end set once every proof is here. | read | LS oot_coop.c |
| `5c3d744e` | Played flag of Barinade's intro cutscene; part of his end set. It rose from 0 to 1 when the fight began in a BossPoints test run. | tested | boss points |
| `234d84c4` | Played flag of Barinade's appearance scene; it rose from 0 to 1 when the fight began in a BossPoints test run; each game's own in co-op. | tested | boss points |
| `7a50372a` | Proof of Phantom Ganon's defeat: the played flag of his death setting. Co-op holds it back and writes the boss's end set once every proof is here. | read | LS oot_coop.c |
| `da2c0485` | Proof of Phantom Ganon's defeat: the played flag of his outro cutscene. Co-op holds it back and writes the boss's end set once every proof is here. | read | LS oot_coop.c |
| `94a743fb` | Proof of Phantom Ganon's defeat: starts true and the death flow sets it to 0. Co-op writes that 0 with his end set once every proof is here. | read | LS oot_coop.c |
| `06c2973a` | Played flag of Phantom Ganon's intro cutscene; part of his end set. It rose from 0 to 1 when the fight began in a BossPoints test run. | tested | boss points |
| `d99e718a` | Fight flag of Phantom Ganon: set by the appearance flow when he shows up; each game keeps its own, so co-op never sends or takes it. | read | LS oot_coop.c |
| `9d5dc65e` | Played flag of Phantom Ganon's appearance scene; it rose from 0 to 1 when the fight began in a BossPoints test run; each game's own in co-op. | tested | boss points |
| `e8a30d2a` | Proof of Volvagia's defeat: her presence flag, set when she is removed after the fight. Co-op holds it back and writes the boss's end set once every proof is here. | read | LS oot_coop.c |
| `19b706f1` | Proof of Volvagia's defeat: the played flag of her death setting. Co-op holds it back and writes the boss's end set once every proof is here. | read | LS oot_coop.c |
| `9aed592a` | Proof of Volvagia's defeat: the played flag of her outro cutscene. Co-op holds it back and writes the boss's end set once every proof is here. | read | LS oot_coop.c |
| `dfe6ba57` | Played flag of Volvagia's intro cutscene, part of her end set; BossPoints watches it with the appearance flag (no hold saw her fight start). | read | boss points |
| `b0d64502` | Appear flag of Volvagia: 1 while she is present, back to 0 as the fight ends; both a fight flag each game keeps and a member her end set writes (as 0). | read | LS oot_coop.c |
| `bda88571` | Played flag of Volvagia's appearance scene; BossPoints expects it to rise when the fight starts (not yet seen); each game's own in co-op. | read | boss points |
| `cbcb98fc` | Proof of Morpha's defeat: the flag that deletes his water, set by the end of the fight. Co-op holds it back and writes the boss's end set once every proof is here. | read | LS oot_coop.c |
| `4a9f3392` | Proof of Morpha's defeat: the played flag of his death setting. Co-op holds it back and writes the boss's end set once every proof is here. | read | LS oot_coop.c |
| `65f3ba2e` | Proof of Morpha's defeat: the played flag of his outro cutscene. Co-op holds it back and writes the boss's end set once every proof is here. | read | LS oot_coop.c |
| `fe39c09c` | Played flag of Morpha's intro cutscene; part of his end set. It rose from 0 to 1 when the fight began in a BossPoints test run. | tested | boss points |
| `fa2798b1` | Fight flag of Morpha: room 23 light switch of the Water Temple, true at the start, cleared as he appears; each game keeps its own, so co-op never sends or takes it. | read | LS oot_coop.c |
| `713abc8f` | Played flag of Morpha's appearance scene; it rose from 0 to 1 when the fight began in a BossPoints test run; each game's own in co-op. | tested | boss points |
| `6f8c3f4d` | Proof of Bongo Bongo's defeat: the played flag of his death setting. Co-op holds it back and writes the boss's end set once every proof is here. | read | LS oot_coop.c |
| `3dfbf016` | Proof of Bongo Bongo's defeat: the played flag of his outro cutscene. Co-op holds it back and writes the boss's end set once every proof is here. | read | LS oot_coop.c |
| `9789a176` | Played flag of Bongo Bongo's intro cutscene; part of his end set. It rose from 0 to 1 when the fight began in a BossPoints test run. | tested | boss points |
| `64eabea6` | Played flag of Bongo Bongo's appearance scene; it rose from 0 to 1 when the fight began in a BossPoints test run; each game's own in co-op. | tested | boss points |
| `24c35501` | Fight flag of Bongo Bongo: the played flag of the warp scene out of the boss area; each game keeps its own, so co-op never sends or takes it. | read | LS oot_coop.c |
| `1960bfaf` | Fight flag of Bongo Bongo: the played flag of the cutscene the boss-area warp plays; each game keeps its own, so co-op never sends or takes it. | read | LS oot_coop.c |
| `d044d7f8` | Fight flag of Bongo Bongo: the played flag of entering the boss room after his defeat; each game keeps its own, so co-op never sends or takes it. | read | LS oot_coop.c |
| `0a789ead` | Proof of Twinrova's defeat: the played flag of her death setting. Co-op holds it back and writes the boss's end set once every proof is here. | read | LS oot_coop.c |
| `9c48fb26` | Proof of Twinrova's defeat: the played flag of her outro cutscene. Co-op holds it back and writes the boss's end set once every proof is here. | read | LS oot_coop.c |
| `ae65c8f6` | Played flag of Twinrova's intro cutscene, part of her end set; BossPoints saw the intro scene play but the flag was not read as rising. | read | boss points |
| `fadc6f48` | Fight flag of Twinrova: set when the sisters' fight starts; each game keeps its own, so co-op never sends or takes it. | read | LS oot_coop.c |
| `b1c575c1` | Played flag of Twinrova's fight start; BossPoints expects it to rise when the fight starts (the intro scene played, the rise was not seen); each game's own. | read | boss points |
| `97cda54b` | Fight flag of Twinrova: the played flag of the mid-fight change of the sisters; each game keeps its own, so co-op never sends or takes it. | read | LS oot_coop.c |
| `8191398d` | Fight flag of Twinrova: the played flag of the cutscene of that mid-fight change; each game keeps its own, so co-op never sends or takes it. | read | LS oot_coop.c |
| `c2a38cd0` | Fight flag of Twinrova: set when the sisters are switched off in the arena; each game keeps its own, so co-op never sends or takes it. | read | LS oot_coop.c |
| `5a371d47` | Played flag of Ganondorf's appearance scene; BossPoints expects it to rise when his fight starts (only the intro scene was seen). | read | boss points |
| `5db588a6` | Played flag of Ganondorf's intro cutscene; BossPoints watches it with the appearance flag (the scene played, the flag was not seen to rise). | read | boss points |
| `1f7fd85b` | Played flag of Ganon's appearance scene; it rose from 0 to 1 when the fight began in a BossPoints test run from the arena save. | tested | boss points |
| `2814399e` | Played flag of the intro cutscene of Ganon's fight; it rose from 0 to 1 when the fight began in a BossPoints test run. | tested | boss points |
| `d2f46f66` | Set by the Deku Scrub Brothers' puzzle (room K); at 0 the Deku Tree boss door is locked from outside, with it set the door opened; it also crossed between two games. | tested | boss points |
| `0fd4f9c9` | The box-on-switch puzzle of room 19 in Dodongo's Cavern; while it is 0 the boss door is locked on the outside; set together with the next flag, the door opened. | tested | boss points |
| `6e5f3718` | Set when the room 19 event of Dodongo's Cavern finishes; BossPoints sets it with the switch flag so the boss door is unlocked (the door opened in a test run). | tested | boss points |
| `b4efc381` | Set when the Forest Temple boss-key door is opened (by the door itself); BossPoints reads it as a door-lock flag set by the door, not by progress. | read | boss points |
| `3be64998` | Barinade's boss-door flag, not saved; raised while the door opens and cleared again after; BossPoints found no lock against Link on the outside. | read | boss points |
| `864da3e3` | Played flag of Darunia's demo at the Fire Temple boss door; at 0 Darunia stood in front of Link, with it set he was gone (test runs); the demo also gives the key. | tested | boss points |
| `f3cc3759` | Clear flag of Shadow Temple room 22; with the quest step it forms the lock on the boss side of the Bongo Bongo door (BossPoints read it from the room's logic graph). | read | boss points |
| `e4938d0e` | Played flag of meeting Zelda at Hyrule Castle; with the Prelude flag it unlocks the bed's Hall of Fallen Foes choice (BossPoints read it in the data). | read | boss points |
| `0895a9ff` | Set once Link has learned the Prelude of Light in the adult Market; with the Zelda meeting flag it unlocks the bed's Hall of Fallen Foes choice. | read | boss points |
| `655d0f9c` | Set by the Hyrule Field cutscene Dm_HrlField_0080; another door into the Dream World besides the bed; BossPoints found no reader. | read | boss points |
| `06fd4977` | Set by the Defeat Ganon quest flow; another door into the Dream World (the Hall of Fallen Foes); BossPoints did not find what reads it. | read | boss points |
| `8857aedb` | Set when Link chooses to sleep at his bed; in a test run it rose 0 to 1 and the game then loaded the Hall of Fallen Foes (Dream World). | tested | boss points |
| `e73deaa8` | Played flag of the first talk with the Hall of Fallen Foes owl; the hall's save flags set it so the bed offers the four-line menu. | read | boss points |
| `34c4d703` | Set when Link accepts the owl's boss-rush challenge at the first monument; it rose 0 to 1 at the accept in a BossPoints test run. | tested | boss points |
| `ee850ad3` | Kill counter of Queen Gohma; BossPoints saves set it to 1 so the Hall of Fallen Foes shows its statue and monument (the game raises it when the boss dies). | read | boss points |
| `1da458d0` | Kill counter of King Dodongo; BossPoints saves set it to 1 so the Hall of Fallen Foes shows its statue and monument (the game raises it when the boss dies). | read | boss points |
| `725379e3` | Kill counter of Barinade; BossPoints saves set it to 1 so the Hall of Fallen Foes shows its statue and monument (the game raises it when the boss dies). | read | boss points |
| `c9175b2a` | Kill counter of Phantom Ganon; BossPoints saves set it to 1 so the Hall of Fallen Foes shows its statue and monument (the game raises it when the boss dies). | read | boss points |
| `f6bbb871` | Kill counter of Volvagia; BossPoints saves set it to 1 so the Hall of Fallen Foes shows its statue and monument (the game raises it when the boss dies). | read | boss points |
| `88461890` | Kill counter of Morpha; BossPoints saves set it to 1 so the Hall of Fallen Foes shows its statue and monument (the game raises it when the boss dies). | read | boss points |
| `b4396bb4` | Kill counter of Bongo Bongo; BossPoints saves set it to 1 so the Hall of Fallen Foes shows its statue and monument (the game raises it when the boss dies). | read | boss points |
| `76eb9d9e` | Kill counter of Twinrova; BossPoints saves set it to 1 so the Hall of Fallen Foes shows its statue and monument (the game raises it when the boss dies). | read | boss points |
| `e349f29f` | Kill counter of Ganondorf; a real game clear sets it to 1 (seen in a finished save), and the Hall of Fallen Foes needs it for its statue. | tested | ClearedSave |
| `6d834709` | Kill counter of Ganon; a real game clear sets it to 1 (seen in a finished save), and the Hall of Fallen Foes needs it for its statue and the third monument. | tested | ClearedSave |
| `5b227a8b` | Int set along with the boss-rush flag when Link accepts the owl's challenge; it rose from 0 to 1 at the accept in a BossPoints test run. | tested | boss points |
| `ec8e66c5` | Pierre the scarecrow is present at spot 01 of Death Mountain Crater only while this is true; the scarecrow-song flow sets it to false. | read | world model |
| `ef23f4c9` | Pierre the scarecrow is present at spot 02 of Death Mountain Crater only while this is true; the scarecrow-song flow sets it to false. | read | world model |
| `847f10a8` | Pierre the scarecrow is present at spot 01 of Dodongo Cavern only while this is true; the scarecrow-song flow sets it to false. | read | world model |
| `a9625065` | Pierre the scarecrow is present at spot 01 of Fire Temple only while this is true; the scarecrow-song flow sets it to false. | read | world model |
| `a59e52af` | Pierre the scarecrow is present at spot 01 of Forest Temple only while this is true; the scarecrow-song flow sets it to false. | read | world model |
| `2fc3c354` | Pierre the scarecrow is present at spot 01 of Gerudo Fortress only while this is true; the scarecrow-song flow sets it to false. | read | world model |
| `2db46763` | Pierre the scarecrow is present at spot 01 of Gerudo Training Ground only while this is true; the scarecrow-song flow sets it to false. | read | world model |
| `1b7a6a8c` | Pierre the scarecrow is present at spot 03 of Lake Hylia only while this is true; the scarecrow-song flow sets it to false. | read | world model |
| `bb44bb12` | Pierre the scarecrow is present at spot 02 of Lake Hylia only while this is true; the scarecrow-song flow sets it to false. | read | world model |
| `2b722e36` | Pierre the scarecrow is present at spot 01 of Lake Hylia only while this is true; the scarecrow-song flow sets it to false. | read | world model |
| `3bbbecd1` | Pierre the scarecrow is present at spot 01 of Sacred Forest Meadow only while this is true; the scarecrow-song flow sets it to false. | read | world model |
| `2739a26f` | Pierre the scarecrow is present at spot 01 of Shadow Temple only while this is true; the scarecrow-song flow sets it to false. | read | world model |
| `a1f553de` | Pierre the scarecrow is present at spot 02 of Shadow Temple only while this is true; the scarecrow-song flow sets it to false. | read | world model |
| `8ba87bac` | Pierre the scarecrow is present at spot 01 of Spirit Temple only while this is true; the scarecrow-song flow sets it to false. | read | world model |
| `eb383915` | Pierre the scarecrow is present at spot 01 of Water Temple only while this is true; the scarecrow-song flow sets it to false. | read | world model |
| `00894c33` | Pierre the scarecrow is present at spot 01 of Zora Fountain only while this is true; the scarecrow-song flow sets it to false. | read | world model |
| `acf493ff` | Expression flag: true once the Fire sage quest is Complete; five Goron people in adult Goron City are present only while it is true. | read | world model |
| `93064625` | Expression flag: true once the Goron Ruby quest (Get_StoneOfFire) is Complete; child Goron City and Market people depend on it. | read | world model |
| `c7efcd7a` | Expression flag: the Goto_HyruleCastle counter from Step03_02 on (read as at-or-after; strictly-after is open); Malon, Talon and a castle wall are placed by it. | read | world model |
| `2a85ce98` | Expression flag: the Door of Time counter from Step2_2 on (read as at-or-after; strictly-after is open); Zelda's castle placement shows while it is false. | read | world model |
| `b2f32349` | Expression flag: the Door of Time counter from Step01 on (read as at-or-after; strictly-after is open); Impa's castle placement shows while it is false. | read | world model |
| `b85ad172` | Expression flag: the Door of Time counter from Step03 on (read as at-or-after; strictly-after is open); two castle guards are placed by it (false or true). | read | world model |
| `e871d99c` | Expression flag: the Water sage counter from Step03 on (read as at-or-after; strictly-after is open); two invisible walls at Lake Hylia stand while it is false. | read | world model |
| `8568e5a6` | Expression flag: the scarecrow side quest is Complete; an invisible Pierre placement in Hyrule Field is present only while it is false. | read | world model |
| `75b83388` | Expression flag: the Zora Sapphire quest (Get_StoneOfWater) is Complete; Zora people in Zora's Domain are placed by it (present true or false). | read | world model |
| `e0c49ba6` | Expression flag: the Zora Sapphire counter from Step13_01 on (read as at-or-after; strictly-after is open); Ruto in Jabu-Jabu's Belly shows while true. | read | world model |
| `51c6ab41` | Expression flag: the Forest sage quest is Complete; ten Kokiri house doors in the adult forest are placed by it (present true or false). | read | world model |
| `a5e46899` | Expression flag: the running-race counter from Ready on (read as at-or-after; strictly-after is open); the running man in the forest shows while true. | read | world model |
| `8bddcf41` | Expression flag: the Forest sage counter from Step08 on (read as at-or-after; strictly-after is open); four adult Kokiri placements are placed by it. | read | world model |
| `f7b3c902` | Expression flag: the Meet_DekuTree counter from Step02 on (read as at-or-after; strictly-after is open); the Kokiri shop's two shopkeepers are placed by it. | read | world model |
| `b78a4007` | Expression flag: the Giant's Knife counter from Step04 on (read as at-or-after; strictly-after is open); two Lost Woods people are placed by it. | read | world model |
| `aa19e3f0` | Expression flag: Link is a child and the Spirit sage quest is past Step04 (and another flag is off); Nabooru's child placement in the Spirit Temple shows only while true. | read | world model |
| `8faedf45` | Expression flag: the Water sage quest is Complete; a Zora person and two invisible walls at Zora's Fountain are present only while it is true. | read | world model |
| `580c19f4` | Expression flag: the Spirit sage counter from Step01 on (read as at-or-after; strictly-after is open); it picks the fixed-bridge walking mesh of Gerudo Valley. | read | world model |
| `a14867ac` | Picks the alternative adult Kakariko for eight exits: true when Link is an adult and the Shadow sage's Kakariko flag is set. | read | world model |
| `e2716851` | Picks the alternative adult Zora's Domain for six exits: true when Link is an adult and the Water sage quest is Complete. | read | world model |
| `f6566559` | Expression flag on the Forest sage counter: the boss-side door lock reads it, and BossPoints found Phantom Ganon's appearance trigger is deleted from this flag on. | read | boss points |
| `b9776994` | Expression flag on the Spirit sage counter: the lock on the boss side of the Twinrova room's shutter is NOT this flag (BossPoints read it from the door graph). | read | boss points |
| `1c8f9186` | Expression flag: the Jabu-Jabu boss prefab creates Barinade only from this flag on; BossPoints' test saves at Step13 got the boss to appear. | tested | boss points |
| `fb431b47` | Expression flag on the AllSage quest counter; monument 02 of the Hall of Fallen Foes' boss rush needs it (BossPoints read the monuments' presence flags). | read | boss points |
| `f840a744` | Played flag of a Temple of Time cutscene; Kaepora's two child placements (Death Mountain Trail and Lake Hylia) are present only while it is false. | read | world model |
| `3f7ecd36` | Water Temple room 7 flag; while false, two hook-shot air walls in Hyrule Field stand; no event flow sets it. | read | world model |
| `0bf7ce9d` | Set by Talon's flows (a Cucco talk and the Giant's Knife quest) when he leaves Kakariko; four Lon Lon gates and two people are placed by it. | read | world model |
| `47693791` | Lon Lon Ranch gamble-race flag; while true, three invisible walls (one for the player, two for animals) stand; no event flow sets it. | read | world model |
| `01a718c3` | Played flag of a Lon Lon cutscene; eight invisible player walls in Hyrule Field stand only until it is played. | read | world model |
| `8a3e5a4c` | Jabu-Jabu's room 9 chest-demo flag; an invisible wall stands until the focus-gimmick flow of the chest scene with Ruto sets it. | read | world model |
| `a3f0a3c6` | Set by the horse race flows when a new record is made; an unridable air wall stands while it is true. | read | world model |
| `502f6cea` | Mido's blocker in the child Kokiri Forest: an invisible wall stands while true; Mido's talk and the Forest Stone scene clear it. | read | world model |
| `e5dc5674` | Blocker flag of a child Kokiri: an invisible wall stands while true; his talk clears it once the Forest Stone quest is Complete. | read | world model |
| `3b320c55` | Mido's blocker in the adult Lost Woods: two invisible walls stand while true; the Forest sage flow's blocker move clears it. | read | world model |
| `19898d14` | Set when the Kakariko gate guard lets Link through (the letter, or the Kakariko gate scene); a Market shop person is present only while true. | read | world model |
| `f00c3fd1` | Played flag of the first Water Temple water-level change; an unridable air wall stands only until it is played. | read | world model |
| `f8561347` | Water Temple room 22 is cleared; a switch shutter of the temple is placed only while this is true. | read | world model |
| `bf9dfc7e` | Played flag of a Zora's Domain cutscene; an invisible player wall in Zora's Domain stands only until it is played. | read | world model |
| `e7c63c37` | Played flag of a Jabu-Jabu cutscene; Ruto's second placement in Zora's Domain is present only after it is played. | read | world model |
| `abb13cc8` | Played flag of the scene Dm_Awake_Water; until it is played, the Hyrule Field walking mesh uses the variant with Lake Hylia drained. | read | world model |
| `6c009086` | Expression flag of the frog choir: true when the game is playing or the Sun's Song is played; an unridable air wall around the red frog stands while it is true. | read | world model |
| `6fb1ea9f` | Expression flag of the frog choir: true when the game is playing or the Song of Time is played; an unridable air wall around the light-blue frog stands while it is true. | read | world model |
| `ab7ce091` | Expression flag of the frog choir: true when Epona's Song is played or the game is playing; an unridable air wall around the gray frog stands while it is true. | read | world model |
| `2a10e827` | Expression flag of the frog choir: true when the game is playing or Saria's Song is played; an unridable air wall around the yellow frog stands while it is true. | read | world model |
| `635fa146` | Expression flag of the frog choir: true when both Saria's Song and the Song of Time are played; an unridable air wall at Zora's River stands while it is true. | read | world model |
| `bbd67a5a` | Expression flag of the frog choir: true when both Saria's Song and the Sun's Song are played; an unridable air wall at Zora's River stands while it is true. | read | world model |
| `46f3efd9` | Expression flag of the frog choir: true when both the Sun's Song and Epona's Song are played; an unridable air wall at Zora's River stands while it is true. | read | world model |
| `6d033b74` | Played flag that 3 map exits check to play the event DeathMountainTrail_Arrive only the first time Link uses them. | read | world model |
| `520f5421` | Played flag that 2 map exits check to play the event InsideTheDekuTree_Arrive only the first time Link uses them. | read | world model |
| `7607c748` | Played flag that 2 map exits check to play the event FromWasteland_ArriveColossus only the first time Link uses them. | read | world model |
| `6dde323f` | Played flag that 2 map exits check to play the event Dm_ForestTemple_0000 only the first time Link uses them. | read | world model |
| `bcaa9db1` | Played flag that 1 map exit checks to play the event GanonCastle_Adult_Field_EntryGanonCastle only the first time Link uses it. | read | world model |
| `6c4c8438` | Played flag that 1 map exit checks to play the event Dm_Gerudo_0000 only the first time Link uses it. | read | world model |
| `8ab78984` | Played flag that 2 map exits check to play the event GoronCity_InitDemo_Arrive only the first time Link uses them. | read | world model |
| `50044004` | Played flag that 3 map exits check to play the event Dm_Graveyard_0000 only the first time Link uses them. | read | world model |
| `fd925132` | Played flag that 1 map exit checks to play the event Dm_HrlCastle_0000 only the first time Link uses it. | read | world model |
| `adbfc26a` | Played flag that 3 map exits check to play the event Dm_SY_BancChangeArrive_Market only the first time Link uses them. | read | world model |
| `b38319ab` | Played flag that 3 map exits check to play the event FromZoraDomain_arriveZoraFountain only the first time Link uses them. | read | world model |
| `c06dceb8` | Played flag that 2 map exits check to play the event Goto_ZoraDomain only the first time Link uses them. | read | world model |
| `de8666fa` | Played flag that 2 map exits check to play the event Goto_FireTemple only the first time Link uses them. | read | world model |
| `d76c2b35` | Played flag that 1 map exit checks to play the event FromGerudoFortress_ArriveTrainingGround only the first time Link uses it. | read | world model |
| `8b591e04` | Played flag that 3 map exits check to play the event Goto_KakarikoWells only the first time Link uses them. | read | world model |
| `5ef2693a` | Played flag that 2 map exits check to play the event Goto_SpritTemple only the first time Link uses them. | read | world model |
| `816983e3` | Played flag that 4 map exits check to play the event Goto_ZoraRiver only the first time Link uses them. | read | world model |
| `48377421` | First-time arrival flag for Death Mountain Crater: 4 map exits play it once (events GoTo_DeathMountainCrater, GoTo_DeathMountainCrater_FromGoronCity). | read | world model |
| `b95d533b` | First-time arrival flag for Kakariko Village: 7 map exits play it once (event Dm_Kakariko_0000). | read | world model |
| `dae7b2c7` | First-time arrival flag for Lake Hylia: 5 map exits play it once (events Dm_LakeHrl_0003, Dm_LakeHrl_0005). | read | world model |
| `003694b5` | Step counter of the AllSage quest (11 steps, NotReady to Complete); the game's quest table files it as a main quest. | read | world model |
| `746f47c0` | Step counter of the Defeat Ganon quest (12 steps); BossPoints' saves use Step04 for Ganondorf's door and Step07 for Ganon's arena, where the fight began (proven). | tested | boss points |
| `378913ca` | Step counter of the DoorOfTime quest (12 steps, NotReady to Complete); the game's quest table files it as a main quest. | read | world model |
| `4661f050` | Step counter of the escape from the crumbling Ganon's Castle (17 steps); BossPoints' Ganon saves set Step09 or Complete; a real finished save never reached it. | read | boss points |
| `8c5e9f84` | Step counter of the GatheringTokenGold quest (5 steps, NotReady to Complete); the game's quest table files it as a side quest. | read | world model |
| `92431c55` | Step counter of the Get_Epona quest (11 steps, NotReady to Complete); the game's quest table files it as a side quest. | read | world model |
| `1002b466` | Step counter of the Goron Ruby quest (21 steps), King Dodongo's; his death raises it to EscapeDungeon (only upward); BossPoints' door save sets DungeonStart. | read | LS oot_coop.c |
| `7d776b61` | Step counter of the Forest Stone quest (8 steps), Queen Gohma's; her death raises it to GoToWarpPoint (only upward); BossPoints' door save sets GoToBossRoom. | read | LS oot_coop.c |
| `5bca02a6` | Step counter of the Zora Sapphire quest (20 steps), Barinade's; his death raises it to Step14; BossPoints' door save sets Step13 and the boss appeared (proven). | tested | boss points |
| `db89c1a9` | Step counter of the Goto_HyruleCastle quest (10 steps, NotReady to Complete); the game's quest table files it as a main quest. | read | world model |
| `78a93b78` | Step counter of the Market_Item_Bottle_TutorialEvent quest (4 steps, NotReady to Complete); the game's quest table files it as neither main nor side. | read | world model |
| `3372689b` | Step counter of the Meet_DekuTree quest (6 steps, NotReady to Complete); the game's quest table files it as a main quest. | read | world model |
| `682d1169` | Step counter of the Meet_GreatFairy quest (7 steps, NotReady to Complete); the game's quest table files it as a main quest. | read | world model |
| `7a6d0096` | Step counter of the MiniGame_BombchuBowling quest (6 steps, NotReady to Complete); the game's quest table files it as neither main nor side. | read | world model |
| `e73daf62` | Step counter of the MiniGame_DampeRace quest (10 steps, NotReady to Complete); the game's quest table files it as neither main nor side. | read | world model |
| `37a4567e` | Step counter of the MiniGame_DiggingHole quest (5 steps, NotReady to Complete); the game's quest table files it as neither main nor side. | read | world model |
| `a4ed3902` | Step counter of the MiniGame_Diving quest (6 steps, NotReady to Complete); the game's quest table files it as neither main nor side. | read | world model |
| `f6e99816` | Step counter of the MiniGame_Fishing quest (4 steps, NotReady to Complete); the game's quest table files it as neither main nor side. | read | world model |
| `916e55c8` | Step counter of the MiniGame_FrogTenors quest (4 steps, NotReady to Complete); the game's quest table files it as neither main nor side. | read | world model |
| `4969f026` | Step counter of the MiniGame_GambleRace quest (5 steps, NotReady to Complete); the game's quest table files it as neither main nor side. | read | world model |
| `a3404532` | Step counter of the MiniGame_HitTarget quest (6 steps, NotReady to Complete); the game's quest table files it as neither main nor side. | read | world model |
| `d601ee20` | Step counter of the MiniGame_HorseRace quest (4 steps, NotReady to Complete); the game's quest table files it as neither main nor side. | read | world model |
| `1193a73e` | Step counter of the MiniGame_SequentialChoiceTreasure quest (4 steps, NotReady to Complete); the game's quest table files it as neither main nor side. | read | world model |
| `147138e3` | Step counter of the Minigame_CatchCucco quest (5 steps, NotReady to Complete); the game's quest table files it as a side quest. | read | world model |
| `3e7d10c0` | Step counter of the Minigame_FindOutCucco quest (7 steps, NotReady to Complete); the game's quest table files it as neither main nor side. | read | world model |
| `55bfddfa` | Step counter of the Minigame_HorsebackArchery quest (5 steps, NotReady to Complete); the game's quest table files it as neither main nor side. | read | world model |
| `474f4ca5` | Step counter of the Minigame_SkullKidSession quest (4 steps, NotReady to Complete); the game's quest table files it as neither main nor side. | read | world model |
| `eea87aec` | Step counter of the Fire sage quest (14 steps), Volvagia's; her death raises it to GoToWarpPoint; BossPoints' door save sets MeetDarunia (her fight was not started). | read | LS oot_coop.c |
| `a9632cca` | Step counter of the Forest sage quest (16 steps), Phantom Ganon's; his death raises it to Step09; BossPoints' door save sets Step07 and he appeared (proven). | tested | boss points |
| `606c3207` | Step counter of the SageOfLight quest (3 steps, NotReady to Complete); the game's quest table files it as a main quest. | read | world model |
| `7a91dbd5` | Step counter of the Shadow sage quest (11 steps), Bongo Bongo's; his death raises it to GoToWarpPoint; BossPoints' door save sets BeforeBossRoom and he appeared (proven). | tested | boss points |
| `19189e9d` | Step counter of the Spirit sage quest (20 steps), Twinrova's; her death raises it to Step10; BossPoints' door save sets Step09 (intro seen, fight start not seen). | read | LS oot_coop.c |
| `560a64af` | Step counter of the Water sage quest (15 steps), Morpha's; his death raises it to Step08; BossPoints' door save sets Step07_1_Safety and he appeared (proven). | tested | boss points |
| `be19d91a` | Step counter of the SubEvent_AllBossBattle quest (6 steps, NotReady to Complete); the game's quest table files it as a side quest. | read | world model |
| `93e84ee3` | Step counter of the SubEvent_FindRichard quest (4 steps, NotReady to Complete); the game's quest table files it as a side quest. | read | world model |
| `110f26e4` | Step counter of the SubEvent_GetFireArrow quest (6 steps, NotReady to Complete); the game's quest table files it as a side quest. | read | world model |
| `4dd52013` | Step counter of the SubEvent_GetGlassTruth quest (7 steps, NotReady to Complete); the game's quest table files it as a side quest. | read | world model |
| `f7176a52` | Step counter of the SubEvent_GetIceArrow quest (5 steps, NotReady to Complete); the game's quest table files it as a side quest. | read | world model |
| `44063c4e` | Step counter of the SubEvent_GetMelodySun quest (4 steps, NotReady to Complete); the game's quest table files it as a side quest. | read | world model |
| `9472302b` | Step counter of the SubEvent_GetScarecrow quest (8 steps, NotReady to Complete); the game's quest table files it as a side quest. | read | world model |
| `7a5b9537` | Step counter of the SubEvent_GetStormSong quest (9 steps, NotReady to Complete); the game's quest table files it as a side quest. | read | world model |
| `26a2e01c` | Step counter of the SubEvent_GetSwordBigGoron quest (27 steps, NotReady to Complete); the game's quest table files it as a main quest. | read | world model |
| `6e9b2539` | Step counter of the SubEvent_GhostShop quest (4 steps, NotReady to Complete); the game's quest table files it as a side quest. | read | world model |
| `ea010310` | Step counter of the SubEvent_MaskSalesman quest (19 steps, NotReady to Complete); the game's quest table files it as a main quest. | read | world model |
| `f6eb33a1` | Step counter of the SubEvent_RunningRace quest (4 steps, NotReady to Complete); the game's quest table files it as a side quest. | read | world model |
| `467020fd` | Opened flag of a chest in Mido's house in Kokiri Forest whose own content is a blue rupee; seen False then True when Link opened it in a test run. | tested | ItemHook |
| `15c74de1` | Opened flag of the big chest that holds the Kokiri Sword; seen True after Link opened it in test runs. | tested | ItemHook |
| `f870d00b` | Opened flag of a chest in Mido's house in Kokiri Forest (one of four); seen False then True when Link opened it in a test run. | tested | ClawshotChests |
| `316d8a20` | Opened flag of a chest in Mido's house in Kokiri Forest (one of four); seen set after Link opened it in a test run. | tested | ClawshotChests |
| `c8643846` | Opened flag of a chest in Mido's house in Kokiri Forest (one of four); seen False then True when Link opened it in a test run. | tested | ClawshotChests |
| `31a0367c` | Opened flag of a large chest in the Deku Tree (it held the compass); seen 0 then 1 when a pilot run opened it. | tested | PilotProof3 |
| `8b9a3d0f` | Opened flag of a small-key chest in Forest Temple room 0; in a two-game run it went 0 to 1 in both games when it was opened, and the key was counted once. | tested | ChestDedupe |
| `ce0c4dfe` | Struct whose members are the opened flags of treasure chests, one per chest; co-op reads them every frame to count a chest's key or item once. | read | ChestDedupe |
| `04df9a16` | Played flag of the "you got the Kokiri Sword" scene; sent when A took the sword from its chest and applied in game B in a two-game run. | tested | CoopGame |
| `405d8a0f` | Got-it-once marker of the Kokiri Sword; seen 0 to 1 when Link got it, and sent to and applied in a second game in a two-game run (its pause menu showed the sword). | tested | CoopGame |
| `eeb495b9` | Count of Kokiri Swords held; it went to 1 in game B after the other player opened the sword chest in a two-game run (the chest gives nothing twice). | tested | CoopGame |
| `b4962fee` | Set when a slot has been cleared; the real finished saves have it, and the Load list then draws its Clear mark (small triforce) after the date. | tested | ClearedSave |
| `c72044fc` | The save caption's Clear byte; a real clear sets it, and the game derives it from IsGameClear whenever it writes a caption, which draws the Clear mark. | tested | ClearedSave |
| `5526db84` | Account-wide Bool in account.sav: some game was cleared at least once; the real finished account has it true. | read | ClearedSave |
| `31ab5580` | Link's life in quarter hearts; the game rewrites this table copy every frame from his own life cell, so a set by flag shows for one sample and is put back. | tested | Fold68 |
| `fbe01da1` | Link's maximum life in quarter hearts (default 12 = 3 hearts, cap 80 = 20 hearts, as the Load card draws it). | read | SaveCatalogue |
| `76b18200` | Link's current magic (an Int); the game assigns its own held value every frame, and setting the meter size to 0 by flag took it to 0 within ten presents. | tested | MeterFix3 |
| `3afa3349` | Int the game assigns to 0 every frame behind any queued write; an add to it from either thread did not fill the magic bar (solo test). | tested | MeterFix3 |
| `008d7f0c` | Name of the tunic or armor Link wears; BossPoints sets the Goron tunic for the Fire Temple and his life then stayed full in a test run (--give alone does not equip it). | tested | boss points |
| `bc32ce24` | The adult Link's item-button choice (an Enum; Bomb in the test saves). | read | PadInput |
| `a0029837` | The child Link's item-button choice (an Enum; Bomb in the test saves). | read | PadInput |
| `da87a986` | Option Enum (Disable, Instrument, Voice) for matching played ocarina notes; Disable in every library save; the estimator's song floats are set only when not Disable. | read | PadInput |
| `9824206c` | String64 holding the A-button prompt text (Open, Crawl, Empty ...); test runs read Open at a door and Empty elsewhere. | tested | PlayHarness |
| `ef2b60c2` | Set while the game loads a map; the test harness reads it as its loading field, which stayed 0 in the first runs (no map change in them). | read | PlayHarness |
| `411c8572` | Set the moment Saria's tutorial with Navi begins in Kokiri Forest; the test harness saw it rise at that moment. | tested | PlayHarness |
| `9b1b27d2` | Set when Link's house door is opened (the A prompt reads Open); seen 0 to 1 in a pilot run as the door opened. | tested | PilotProof2 |
| `ed698ecf` | Set on the first talk with a Kokiri girl; seen 0 to 1 in one pilot talk step. | tested | PilotProof2 |
| `392b86fb` | Played flag of the scene that the Lake Hylia gate switch starts; once set the gate shutter stays open and the scene is skipped (read from the gate's logic graph). | read | ClawshotHelp |
| `ab74fd3c` | While true the gate pillar of the Lake Hylia gate is on (read from the gate's logic graph; it was False in the test saves). | read | ClawshotHelp |
| `8f8af32e` | Forest Temple room 8 ivy flag; used as a shared control in a two-game run: set in one game, it arrived in the other (the position flags did not). | tested | Fold68 |
| `17729b10` | Expression flag on the AllSage counter: true from step Step01_00_02 on (read as at-or-after, strictly-after is open); used by 3 quest-step conditions. | read | world model |
| `4c9a9b67` | Expression flag on the AllSage counter: true from step Step01 on (read as at-or-after, strictly-after is open); used by 2 quest-step conditions. | read | world model |
| `6148ad2b` | Expression flag on the SageOfShadow counter: true once the quest is Complete (the world model's reading); 3 quest-step conditions read it. | read | world model |
| `67097980` | Expression flag on the Get_StoneOfWater counter: true from step Ready on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `6c1119b9` | Expression flag over several quest counters; the world model lists the comparisons but not how they combine. | read | world model |
| `b4e83eaf` | Expression flag on the DoorOfTime counter: true from step Step04 on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `fa98fdf6` | Expression flag on the GatheringTokenGold counter: true from step Ready on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `ca8ee260` | Expression flag on the Get_Epona counter: true from step ReadyForGetEponaSong on (read as at-or-after, strictly-after is open); used by 3 quest-step conditions. | read | world model |
| `6b8c1072` | Expression flag on the Get_Epona counter: true from step ReadyForGambleRace on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `3450a85a` | Expression flag on the Get_StoneOfFire counter: true from step GoronCityIn on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `e648ef8b` | Expression flag on the Get_StoneOfFire counter: true from step DarniaRoomKokiriTalk on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `08b3bbde` | Expression flag on the Get_StoneOfFire counter: true from step GoronCityDarniaTalk on (read as at-or-after, strictly-after is open); used by 2 quest-step conditions. | read | world model |
| `77c4e91a` | Expression flag on the Get_StoneOfFire counter: true from step KokiriForestIn on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `502b9b21` | Expression flag on the Get_StoneOfFire counter: true from step KokiriForestNPCTalk on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `b21f3148` | Expression flag on the Get_StoneOfWater counter: true from step Step03 on (read as at-or-after, strictly-after is open); used by 3 quest-step conditions. | read | world model |
| `d1493432` | Expression flag on the Get_StoneOfWater counter: true from step Step03_Impa on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `af6dce21` | Expression flag on the Goto_HyruleCastle counter: true from step Step02_01 on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `dec110ce` | Expression flag on the Meet_DekuTree counter: true from step Step01 on (read as at-or-after, strictly-after is open); used by 2 quest-step conditions. | read | world model |
| `856b0371` | Expression flag on the Meet_GreatFairy counter: true from step GoToTopOfMountain on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `c714f3a0` | Expression flag that compares the MiniGame_Diving counter (== Step01); the world model lists that comparison, not the whole expression. | read | world model |
| `8d93dcdf` | Expression flag on the MiniGame_HitTarget counter: true from step Ready on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `38f33e5c` | Expression flag that compares the Minigame_FindOutCucco counter (== Playing); the world model lists that comparison, not the whole expression. | read | world model |
| `5f5416ce` | Expression flag on the SageOfForest counter: true from step Ready on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `44efa2c6` | Expression flag on the SageOfForest counter: true from step Step01 on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `df6b9422` | Expression flag on the SageOfShadow counter: true from step DefeatBoss on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `07fc4217` | Expression flag on the SageOfShadow counter: true from step MeetBoss on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `700a2ea9` | Expression flag on the SageOfShadow counter: true from step GetGlassTruth on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `b1efd9c9` | Expression flag on the SageOfSpirit counter: true from step Step05_02 on (read as at-or-after, strictly-after is open); used by 3 quest-step conditions. | read | world model |
| `391bf510` | Expression flag on the SageOfSpirit counter: true from step Step04 on (read as at-or-after, strictly-after is open); used by 3 quest-step conditions. | read | world model |
| `e4c52b13` | Expression flag on the SageOfSpirit counter: true from step Step05_01 on (read as at-or-after, strictly-after is open); used by 2 quest-step conditions. | read | world model |
| `b9ed1739` | Expression flag on the SageOfSpirit counter: true from step Step05 on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `fe0c6854` | Expression flag on the SageOfWater counter: true from step Step00 on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `89b945d0` | Expression flag on the SageOfWater counter: true from step Step01 on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `1a374048` | Expression flag on the SageOfWater counter: true from step Step05 on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `a26f5142` | Expression flag on the SageOfWater counter: true from step Step04 on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `73ec71e7` | Expression flag on the SubEvent_FindRichard counter: true from step Ready on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `f52b89c0` | Expression flag on the SubEvent_FindRichard counter: true once the quest is Complete (the world model's reading); 1 quest-step condition read it. | read | world model |
| `f41eacbf` | Expression flag that compares the SubEvent_FindRichard counter (== Complete); the world model lists that comparison, not the whole expression. | read | world model |
| `7ed3452e` | Expression flag on the SubEvent_GetFireArrow counter: true from step Ready on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `425392dd` | Expression flag on the SubEvent_GetFireArrow counter: true from step Step01 on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `3f3545ad` | Expression flag on the SubEvent_GetIceArrow counter: true once the quest is Complete (the world model's reading); 1 quest-step condition read it. | read | world model |
| `54539d36` | Expression flag on the SubEvent_GetIceArrow counter: true from step Ready on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `2d24426d` | Expression flag on the SubEvent_GetScarecrow counter: true from step Ready on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `12bc2a20` | Expression flag on the SubEvent_GetScarecrow counter: true from step MeetPierre on (read as at-or-after, strictly-after is open); used by 2 quest-step conditions. | read | world model |
| `a5a25551` | Expression flag on the SubEvent_GetScarecrow counter: true from step IntoThePast on (read as at-or-after, strictly-after is open); used by 2 quest-step conditions. | read | world model |
| `5b2d3f91` | Expression flag on the SubEvent_GetScarecrow counter: true from step PlayScarecrowSong on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `c5debf42` | Expression flag on the SubEvent_GetStormSong counter: true from step Ready on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `87f647f0` | Expression flag on the SubEvent_GetSwordBigGoron counter: true from step Ready on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `c736c801` | Expression flag on the Get_Epona counter: true once the quest is Complete (the world model's reading); 3 quest-step conditions read it. | read | world model |
| `7311de29` | Expression flag on the SubEvent_GetSwordBigGoron counter: true from step WaitEggHatch on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `cf76e357` | Expression flag on the SubEvent_GetSwordBigGoron counter: true from step Step01_01 on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `d49095a7` | Expression flag on the SubEvent_GetSwordBigGoron counter: true from step Step02 on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `f4d5d3b9` | Expression flag that compares the SubEvent_GetSwordBigGoron counter (>= Ready); the world model lists that comparison, not the whole expression. | read | world model |
| `53e17d55` | Expression flag over several quest counters; the world model lists the comparisons but not how they combine. | read | world model |
| `02290236` | Expression flag on the SubEvent_GetSwordBigGoron counter: true from step Step09 on (read as at-or-after, strictly-after is open); used by 4 quest-step conditions. | read | world model |
| `1db90015` | Expression flag on the SubEvent_GetSwordBigGoron counter: true from step Step03_03 on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `0701493a` | Expression flag on the SubEvent_GetSwordBigGoron counter: true from step Step05_01 on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `e6a0f278` | Expression flag on the SubEvent_GetSwordBigGoron counter: true from step Step06_02 on (read as at-or-after, strictly-after is open); used by 2 quest-step conditions. | read | world model |
| `64639baa` | Expression flag on the SubEvent_GetSwordBigGoron counter: true from step Step08_01 on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `bc2c61b7` | Expression flag on the SubEvent_GetSwordBigGoron counter: true once the quest is Complete (the world model's reading); 2 quest-step conditions read it. | read | world model |
| `ee85fa6f` | Expression flag on the SubEvent_GetSwordBigGoron counter: true from step Step09_01 on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `a8874f3f` | Expression flag on the SubEvent_GetSwordBigGoron counter: true from step Step10 on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `05ed5e6a` | Expression flag on the SubEvent_GhostShop counter: true once the quest is Complete (the world model's reading); 1 quest-step condition read it. | read | world model |
| `97bc46b0` | Expression flag on the SubEvent_MaskSalesman counter: true from step Step01 on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `eb305063` | Expression flag on the SubEvent_MaskSalesman counter: true from step Ready on (read as at-or-after, strictly-after is open); used by 4 quest-step conditions. | read | world model |
| `ca8294c8` | Expression flag on the SubEvent_MaskSalesman counter: true from step Step03 on (read as at-or-after, strictly-after is open); used by 1 quest-step condition. | read | world model |
| `bb72f7bc` | Expression flag on the SubEvent_MaskSalesman counter: true from step Step05 on (read as at-or-after, strictly-after is open); used by 2 quest-step conditions. | read | world model |
| `c2e8486b` | Force-progress flag of step CollectToken of the GatheringTokenGold quest in the game's quest table (read by the world model). | read | world model |
| `b041ae87` | Force-progress flag of step Ready of the Meet_DekuTree quest in the game's quest table (read by the world model). | read | world model |
| `ff98ed58` | Force-progress flag of step Step03 of the SageOfForest quest in the game's quest table (read by the world model). | read | world model |
| `d161ea38` | Force-progress flag of step UntilRentMaskOfKeaton of the SubEvent_MaskSalesman quest in the game's quest table (read by the world model). | read | world model |
| `0e76cf87` | Force-progress flag of step UntilRentMaskOfSkull of the SubEvent_MaskSalesman quest in the game's quest table (read by the world model). | read | world model |
| `d0ac7e3f` | Force-progress flag of step UntilRentMaskOfSpooky of the SubEvent_MaskSalesman quest in the game's quest table (read by the world model). | read | world model |
| `f93b67d0` | Force-progress flag of step UntilRentMaskOfBunny of the SubEvent_MaskSalesman quest in the game's quest table (read by the world model). | read | world model |
| `0fdeaa7a` | Dependency flag of the DoorOfTime quest in the game's quest table: the quest depends on it (read by the world model). | read | world model |
| `077a5709` | Dependency flag of the SubEvent_GetFireArrow quest in the game's quest table: the quest depends on it (read by the world model). | read | world model |
| `c866bdaa` | Expression flag over the kill counter of Queen Gohma: true once the boss is killed; the Hall of Fallen Foes then shows its statue (BossPoints read it in the data). | read | boss points |
| `e4e3fdb8` | Expression flag over the kill counter of King Dodongo: true once the boss is killed; the Hall of Fallen Foes then shows its statue (BossPoints read it in the data). | read | boss points |
| `52c59ec3` | Expression flag over the kill counter of Barinade: true once the boss is killed; the Hall of Fallen Foes then shows its statue (BossPoints read it in the data). | read | boss points |
| `92cb86bb` | Expression flag over the kill counter of Phantom Ganon: true once the boss is killed; the Hall of Fallen Foes then shows its statue (BossPoints read it in the data). | read | boss points |
| `e46a9e97` | Expression flag over the kill counter of Volvagia: true once the boss is killed; the Hall of Fallen Foes then shows its statue (BossPoints read it in the data). | read | boss points |
| `4c96eb50` | Expression flag over the kill counter of Morpha: true once the boss is killed; the Hall of Fallen Foes then shows its statue (BossPoints read it in the data). | read | boss points |
| `a386fb13` | Expression flag over the kill counter of Bongo Bongo: true once the boss is killed; the Hall of Fallen Foes then shows its statue (BossPoints read it in the data). | read | boss points |
| `4fe914e3` | Expression flag over the kill counter of Twinrova: true once the boss is killed; the Hall of Fallen Foes then shows its statue (BossPoints read it in the data). | read | boss points |
| `0c3743b0` | Expression flag over the kill counter of Ganondorf: true once the boss is killed; the Hall of Fallen Foes then shows its statue (BossPoints read it in the data). | read | boss points |
| `e84b960e` | Expression flag over the kill counter of Ganon: true once the boss is killed; the Hall of Fallen Foes then shows its statue (BossPoints read it in the data). | read | boss points |
| `77917e05` | Set true by Ganondorf's death flow; not saved (reset 9). | read | ClearedSave |
| `33ea811a` | Set true by Ganondorf's death flow; the name says his dead body then appears. | read | ClearedSave |
| `8b3406cc` | Set true at the start of Ganon's death flow; not saved. | read | ClearedSave |
| `04d31e64` | Set true by the ending flow during the credits; not saved (reset 0); it marks the return to the title after the clear. | read | ClearedSave |
| `7c138e1f` | Set true by the ending flow together with a temporary save of the slot. | read | ClearedSave |
| `36aadc2d` | Set by each of the six barrier-removal entries of Ganon's Castle, with the barrier-guide flag; read from the Defeat Ganon flow. | read | ClearedSave |
| `c9a9b801` | Set by each of the six barrier-removal entries of Ganon's Castle, with the all-barriers flag; read from the Defeat Ganon flow. | read | ClearedSave |
| `c666d018` | Set true by Phantom Ganon's death flow; not saved (reset 9); it is not in his end set. | read | ClearedSave |
| `605e5df8` | Account Bool (account.sav) for whether the last chosen mode was Master Quest; false in the real finished account, which has no Master Quest slots. | read | ClearedSave |
| `46926d32` | Struct of the save caption (caption.sav) the Load list draws: life, maximum life, the Clear mark and mirrors of the items and songs. | read | ClearedSave |
| `dba154a6` | Struct in the save caption that mirrors the items and songs as Bools, so the Load list can draw them. | read | NgPlus |
| `74bd05d0` | Maximum life in quarter hearts as the save caption records it (caption.sav, file index 2). | read | NgPlus |
| `1e55ecc5` | Life in quarter hearts as the save caption records it (caption.sav, file index 2). | read | NgPlus |
| `2b05cbb9` | Struct of the played-event flags, one per row of the game's EventSetting table (2,380 rows); co-op shares most of them and keeps story scenes per player by default. | read | LS docs/coop.md |
| `fb4b52f6` | Struct of kill counters, one Int per enemy actor, including the ten bosses; the Hall of Fallen Foes reads them for its statues. | read | SaveCatalogue |
| `060890b0` | Struct of Link's status: life, magic, rupees, the names of the worn equipment, lift grade, the saved place and more. | read | SaveCatalogue |
| `dd80b066` | Struct that keeps the unnamed room Bools of the logic graphs; 15 of them are one player's own and stay each game's own in co-op. | read | LS oot_coop.c |
| `a95a3521` | Name of the sword Link wears; the worn equipment stays each player's own choice and is never merged by progress sync. | read | LS docs/coop.md |
| `ee463235` | Name of the shield Link wears; the worn equipment stays each player's own choice and is never merged by progress sync. | read | LS docs/coop.md |
| `d107a85d` | Name of the boots Link wears; the worn equipment stays each player's own choice and is never merged by progress sync. | read | LS docs/coop.md |
| `7ce1cb81` | Name of the gauntlets Link wears; the worn equipment stays each player's own choice and is never merged by progress sync. | read | LS docs/coop.md |
| `59d9c7b3` | Name of the headgear Link wears; the worn equipment stays each player's own choice and is never merged by progress sync. | read | LS docs/coop.md |
| `a1f7ee2b` | Name of the sword worn by Link's other age; New Game+ copies it when the age differs (NgPlus design). | read | NgPlus |
| `2342b619` | Name of the shield worn by Link's other age; New Game+ copies it when the age differs (NgPlus design). | read | NgPlus |
| `c884818d` | Link's saved place, written by the game when it saves where he stands; the game's own travel is an event with a map and start name. | read | SaveEditGame |
| `1ea93bd8` | Link's saved facing (a Y rotation), written by the game together with the saved place. | read | SaveEditGame |
| `a4aee8cd` | Float of Link's facing for the map; the test harness adds 180 degrees to read his heading, which matched his motion in test runs (not kept during scenes). | tested | PlayHarness |
| `37d3074a` | Set by the shop flow when the Deku Shield is the selected goods in the Kokiri shop (PlayHarness read it from the flow DisplayShop). | read | PlayHarness |
| `a2995097` | The save list's last picked index (the slot the list's cursor was on); the save card's pick writes it. | tested | game-data.md |
| `a2dcdc9d` | The voice language option (an enum, default Japanese, set from the region-language type by the options' reset); the NPC voice resource reads it. | read | audio.md |
| `834d9d9e` | The struct of the game's options; VoiceLanguage is one of its members. | read | audio.md |
| `58131bc2` | The game's debug parameters, never saved; the members found include the Master Quest scene flag and the manual childhood switch. | tested | game-data.md |
| `11b16e68` | Set when a map's name contains `_MQ`: the game is entering a Master Quest scene. | read | events.md |

## Not described

**LS `host/oot_coop.c` at `29b087a83`.** Every list is used: scene-change flags (4), songs (13), heart rewards (11), the 67 unshared flags with their comments, the eight boss sets (proof, members, fight), code-read scenes (18), quest counts (11), own counts (30), strength items (3), ammunition (7), the key counters (14), the `#define`d flags (rupees, magic size, lift grade, equipped ocarina, both ocarina counts, play clock, former area counter, loading, current map) and the struct rows. Not usable: the member and value hashes (`M_STOCK` 22344481, `M_SMALL_KEYS` 1af87831, `M_GET_MAP` 58aeb8fb, `M_GET_COMPASS` c7692e3f, `M_GET_BOSS_KEY` 5fb83617, `CAP_RUPEES` 3b58ca14, the five capacity-member hashes of the ammo table, `BOSS_ASK` b05500a5, the four lift-value hashes and every boss quest step's enumerator hash) have no row of their own in the three csv files. The source says nothing per flag about the 184 first-get markers of the items group (`IsGet.*`, only "got it once markers, one per item") or the 56 remaining item counts (`PouchData.*.StockNum`, only "an item's count"): that is a family reading, left for the README. The 9,235 other progress rows have no comment in the source.

**LS `host/coop_scenes.c`.** It holds only the scan of the game's own files (the folders read, the `HavePlayedEvent.` prefix rule, the murmur hash and a cache format); no flag hash or name. The 2,168 story scenes therefore cannot be described one by one from it; the rule that any `HavePlayedEvent.*` flag no other file names is a story scene belongs in the README.

**LS `docs/coop.md` ("What is shared", "A beaten boss", "Story scenes").** Used for the map, compass and boss-key flags, the position flags it names, the heart and token reasons, the equipped-ocarina and lift-grade paragraphs and the beaten-boss sets. Not usable per row: the 44 Navi hint and two camera-look flags ("shared like any flag", no hash or name), "bottle contents", "the time of day" and "the equipment worn" (no flag names), and the Known-limits notes.

**World model (`gates.json`, `story.json`, `flag_names.json`, `flags.json`, `links.json`).** From `gates.json` all 83 distinct gate flags with a `present_when`, `flag_means`, exit event or flow setting are used (17 scarecrow presence flags, the expression flags, blockers, doors, exits, the two nav-mesh variants, the two alternative-area flags). Not used: the 579 doors "named with flags by their logic module" (strength `mention`: a name occurring in a graph, a lead, not a condition), the 81 locked doors with no flag, and the edge kinds `logic-names` (1,886), `flow-names` (513) and `expression-reads` (175), which only say a name occurs. `story.json` gives the 45 `Step_<quest>` Enum rows and the comparisons for 81 expression flags used in quest-step conditions; the step enumerators are hashes of step names and no row. Caveat for every `IsAfter` flag: the data's operator code 12 is read as at-or-after but BossPoints and ClawshotHelp could not rule out strictly-after, so the sentences say so. `flags.json` holds names, hashes and types only, `links.json` only exits (used through the gates). `flag_names.json` agrees with the csv except one hash, `82daaab7`, which it names `zSA` and the csv row leaves unnamed. The 25 open questions (flags no event flow names, e.g. room 7 of the Water Temple, the Lon Lon chair flag) say what a flag gates but not what sets it.

**Boss points (`bosspoints-table.json`) and `BossPoints.md`.** Every flag the table sets, watches or lists as boss key is used, with the door locks of section 2b and the Hall of Fallen Foes flags; fights proven in a hold are `tested`: Barinade, Phantom Ganon, Morpha, Bongo Bongo and Ganon (arena start), and the quest steps of those holds. Not usable: positions, loadouts (`give` lists), scenario steps, and the three fights that never started (Gohma, King Dodongo, Volvagia: their appearance flags are `read`), Twinrova's and Ganondorf's appearance flags (the intro scenes played, the rise was not read), the Dream World's per-boss stage maps and `DreamWorldPlate_Enemy_*` presence flags (no row), and `HaveDefeatedEnemy_*` for the non-boss enemies (the report names the pattern, not each flag).

**`CoopHints` and `FlagList`.** `CoopHints-files/counts.md` has family counts only (Navi balloons 506, tutorial hints 106, first talks 224, special talks 402, location markers 36, get scenes 199, "read by nothing"): no statement about a particular flag. `FlagList-files/flags.md` is the earlier build of the same table with name-word readings; nothing beyond what the csv already holds.

**`ChestDedupe`, `ClawshotChests`, `ClawshotHelp`, `ItemHook`, `PilotProof3`, `CoopGame`.** Used for the chest opened-flags seen set in running games (seven chests), the `IsTreasureBoxOpen` struct, the Kokiri Sword chest in a two-game run and the Lake Hylia gate's logic graph. Not usable: the 16-hex per-object keys of those chests (the reports give the placement hash in decimal, not what the key row does) and the rando-chest contents of `ClawshotChests`, which are one seed, not the game.

**`Fold68`.** Used for the three Gohma proof flags, the four per-game flags and two controls of the flags stage, the Deku Tree map flag, the equipped-ocarina name and `PlayerStatus.Life`. Its `bosses.out` agrees with the LS boss lists; the 29 fight flags are covered by them.

**`ClearedSave`, `SaveCatalogue`, `NgPlus`, `SaveEditGame`.** Used for the clear marks, the ending-flow flags, the caption struct, `DefeatedEnemyNum`, the saved place and the worn-equipment names. `SaveCatalogue` reads the per-object keys as a family ("this instance was taken or broken" for the 3,686 keys that equal a placed actor's hash; 639 of the 740 keys set in the real file are placements; exactly 100 Gold Skulltula keys) and chest opened flags as `IsTreasureBoxOpen.<hash>` for 184 chests: family readings, not used per row. The other 7,971 keys have no known meaning.

**`PlayHarness`, `PilotProof*`, `PadInput`, `MeterFix*`, `PreMergeChecks`, `Pickups1450`.** Used for the rows marked with those names. Not usable: `PilotProof` and `PadInput` read three flags by hash alone with readings that disagree: `5f959a6d` (named `HavePlayedEvent.PlayStormSong_InWindmill_Adult`, seen rising when the ocarina came out or went away, not on a song), `16bf1503` (named `UI_IsShortCutBCancel`, "wheel open" in one report and "not a wheel flag" in the next) and `67ac7142` (named `IsUnvisiblePlayerStatusScreenForEventToMain`, seen set to 0 after a play). `Pickups1450` studies a pickup bug and does not say what a first-get marker does.

**`PortSquadala` and `DauroskScan2`.** They describe the other co-op's flag lists and code (its own rules for the same flags); the game facts in them (lift grade, equipped ocarina, quest enums as step-name hashes without order, the 29 position flags) are the same as the LS source says, so no row rests on them alone.
