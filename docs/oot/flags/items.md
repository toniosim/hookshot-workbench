# Flag map: Items, songs, quest items, counters

The flags of what Link carries and has learned: each item's first-pickup marker and count, the capacities, the songs, the quest items, the small-key counters, the rupee counter and the ammunition counters. 331 rows on this page. Columns, values and how sure a row is: [README.md](README.md).

### ammo

| Hash | Name | Named by | Kind | Default | Reset | File | Group | Co-op | Map | Note | What it is | Sure | Source |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `518ec74b` | `PouchData.Item_Arrow_Normal.StockNum` | struct | Int | 0 | 32 | progress | 3 | ammo, own |  |  | How many arrows Link holds (capped by the quiver); ammunition is each player's own by default and can be pooled by the room (coop_ammo). | read | LS oot_coop.c |
| `db1bcd4f` | `PouchData.Item_Bomb.StockNum` | struct | Int | 0 | 32 | progress | 3 | ammo, own |  |  | How many bombs Link holds (capped by the bomb bag); ammunition is each player's own by default and can be pooled by the room (coop_ammo). | read | LS oot_coop.c |
| `df7c517a` | `PouchData.Item_Bombchu.StockNum` | struct | Int | 0 | 32 | progress | 3 | ammo, own |  |  | How many bombchus Link holds; ammunition is each player's own by default and can be pooled by the room (coop_ammo). | read | LS oot_coop.c |
| `f30d9f54` | `PouchData.Item_DekuNut.StockNum` | struct | Int | 0 | 32 | progress | 3 | ammo, own |  |  | How many Deku Nuts Link holds (capped by the nut bag); ammunition is each player's own by default and can be pooled by the room (coop_ammo). | read | LS oot_coop.c |
| `5fadf7fc` | `PouchData.Item_DekuSeed.StockNum` | struct | Int | 0 | 32 | progress | 3 | ammo, own |  |  | How many Deku Seeds Link holds (capped by the seed bag); ammunition is each player's own by default and can be pooled by the room (coop_ammo). | read | LS oot_coop.c |
| `b9494411` | `PouchData.Item_DekuStick.StockNum` | struct | Int | 0 | 32 | progress | 3 | ammo, own |  |  | How many Deku Sticks Link holds (capped by the stick bag); ammunition is each player's own by default and can be pooled by the room (coop_ammo). | read | LS oot_coop.c |
| `b003124d` | `PouchData.Item_MagicBean.StockNum` | struct | Int | 0 | 32 | progress | 3 | ammo, own |  |  | How many magic beans Link holds; ammunition is each player's own by default and can be pooled by the room (coop_ammo). | read | LS oot_coop.c |

### items: capacity

| Hash | Name | Named by | Kind | Default | Reset | File | Group | Co-op | Map | Note | What it is | Sure | Source |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `418db791` |  |  | Int | 0 | 32 | progress | 3 | items, shared |  | member "Arrow" of group 0xf80f8077 | Capacity of the quiver (arrows): the most Link can carry; it is an item value co-op shares, and caps the matching pooled count. | read | LS oot_coop.c |
| `457616b0` |  |  | Int | 0 | 32 | progress | 3 | items, shared |  | member "DekuStick" of group 0xf80f8077 | Capacity of the stick bag (Deku Sticks): the most Link can carry; it is an item value co-op shares, and caps the matching pooled count. | read | LS oot_coop.c |
| `735b00f7` |  |  | Int | 0 | 32 | progress | 3 | items, shared |  | member "DekuNut" of group 0xf80f8077 | Capacity of the nut bag (Deku Nuts): the most Link can carry; it is an item value co-op shares, and caps the matching pooled count. | read | LS oot_coop.c |
| `ae8cc742` |  |  | Int | 0 | 32 | progress | 3 | items, shared |  | member "DekuSeed" of group 0xf80f8077 | Capacity of the seed bag (Deku Seeds): the most Link can carry; it is an item value co-op shares, and caps the matching pooled count. | read | LS oot_coop.c |
| `e0010a50` |  |  | Int | 0 | 32 | progress | 3 | items, shared |  | member "Rupee" of group 0xf80f8077 | Capacity of the wallet (rupees): the most Link can carry; it is an item value co-op shares, and caps the matching pooled count. | read | LS oot_coop.c |
| `e753508b` |  |  | Int | 0 | 32 | progress | 3 | items, shared |  | member "Bomb" of group 0xf80f8077 | Capacity of the bomb bag (bombs): the most Link can carry; it is an item value co-op shares, and caps the matching pooled count. | read | LS oot_coop.c |

### items: first-get marker

| Hash | Name | Named by | Kind | Default | Reset | File | Group | Co-op | Map | Note | What it is | Sure | Source |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `40b68073` | `IsGet.Animal_Fish_Blue` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `4506012d` | `IsGet.Animal_Insect` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `b24c3bcf` | `IsGet.Armor_Adult_Default_Head` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `3ef15ec4` | `IsGet.Armor_Adult_Gauntlet_Gold` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `87e58de3` | `IsGet.Armor_Adult_Gauntlet_Silver` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `ae5611af` | `IsGet.Armor_Adult_Goron` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `5fa190e6` | `IsGet.Armor_Adult_HeavyBoot` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `1109c920` | `IsGet.Armor_Adult_HoverBoot` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `de513abd` | `IsGet.Armor_Adult_Normal` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `4f5a929c` | `IsGet.Armor_Adult_Zora` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `809787e7` | `IsGet.Armor_Child_Default_Head` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `9880707e` | `IsGet.Armor_Child_Gauntlet_Goron` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `06f13bb2` | `IsGet.Armor_Child_Mask_Amiibo0` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `09df9d25` | `IsGet.Armor_Child_Mask_Amiibo1` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `65aebe17` | `IsGet.Armor_Child_Mask_Bunny` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `b1fc4c1d` | `IsGet.Armor_Child_Mask_Gerudo` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `adfccd91` | `IsGet.Armor_Child_Mask_Goron` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `35c60e1d` | `IsGet.Armor_Child_Mask_Keaton` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `d097482a` | `IsGet.Armor_Child_Mask_Skull` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `c0cf68a7` | `IsGet.Armor_Child_Mask_Spooky` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `f7d5bd9c` | `IsGet.Armor_Child_Mask_Truth` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `280eb00e` | `IsGet.Armor_Child_Mask_Zora` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `7fe2a5b2` | `IsGet.Armor_GlassTruth` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `b6e096ae` | `IsGet.Armor_Mask_Base` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `dd587ed8` | `IsGet.Item_AgonyStone` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `14909166` | `IsGet.Item_AlarmCucco` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `4db7eae0` | `IsGet.Item_Arrow_Fire` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `5c8f3099` | `IsGet.Item_Arrow_Ice` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `8637bab4` | `IsGet.Item_Arrow_Light` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `572701ea` | `IsGet.Item_Arrow_Normal` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `2bb00768` | `IsGet.Item_Bomb` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `968a5a79` | `IsGet.Item_BombBag_Large` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `b2c478da` | `IsGet.Item_BombBag_Medium` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `a63f1e2d` | `IsGet.Item_BombBag_Small` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `8286c23f` | `IsGet.Item_BombBundle_Small` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `5ab49c8e` | `IsGet.Item_Bombchu` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `3d6caa5c` | `IsGet.Item_BombchuBundle_Large` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `e43215db` | `IsGet.Item_BombchuBundle_Medium` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `e01518e8` | `IsGet.Item_BombchuBundle_Small` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `7f4ce38d` | `IsGet.Item_Boomerang` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `1106b082` | `IsGet.Item_Bottle` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `03463ab6` | `IsGet.Item_Bottle_BigPoe` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `53db16a6` | `IsGet.Item_Bottle_BlueFire` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `ea0729fe` | `IsGet.Item_Bottle_BluePotion` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `cf2d3db4` | `IsGet.Item_Bottle_Bug` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `124c4d3a` | `IsGet.Item_Bottle_Fairy` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `b46a0394` | `IsGet.Item_Bottle_Fish` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `75abc14b` | `IsGet.Item_Bottle_GreenPotion` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `21fe9ffa` | `IsGet.Item_Bottle_HalfMilk` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `170b5df2` | `IsGet.Item_Bottle_Letter` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `f1232980` | `IsGet.Item_Bottle_Milk` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `f2001cfd` | `IsGet.Item_Bottle_Poe` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `d8ffafd1` | `IsGet.Item_Bottle_RedPotion` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `645a8175` | `IsGet.Item_BrokenSword` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `b669f025` | `IsGet.Item_BulletBag_Large` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `e6cd55d2` | `IsGet.Item_BulletBag_Medium` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `488ca1be` | `IsGet.Item_BulletBag_Small` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `8b54e680` | `IsGet.Item_ClaimCheck` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `fb4442de` | `IsGet.Item_CojiroCucco` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `00c2ee37` | `IsGet.Item_DekuNut` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `29888e1e` | `IsGet.Item_DekuSeed` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `c4e21ac2` | `IsGet.Item_DekuStick` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `fb777163` | `IsGet.Item_DekuStickBundle_Small` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `fa04e611` | `IsGet.Item_DinFire` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `6ac27606` | `IsGet.Item_Dungeon_BossKey` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `14fcc563` | `IsGet.Item_Dungeon_Compass` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `ffe25805` | `IsGet.Item_Dungeon_Map` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `154ef588` | `IsGet.Item_Dungeon_SmallKey` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `8e02d1ca` | `IsGet.Item_EyeballFrog` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `b7bdd577` | `IsGet.Item_EyeDrop` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `944b78be` | `IsGet.Item_FairyBless_DefenseDouble` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `b1309073` | `IsGet.Item_FairyBless_MP` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `87ca4826` | `IsGet.Item_FairyBless_MPDouble` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `ffabf058` | `IsGet.Item_FaroreWind` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `10c5b9bf` | `IsGet.Item_FishingRod` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `7227efd8` | `IsGet.Item_Hammer` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `af176ab2` | `IsGet.Item_Hat_FishingPondOwner` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `ff98ed58` | `IsGet.Item_Hookshot` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  | Force-progress flag of step Step03 of the SageOfForest quest in the game's quest table (read by the world model). | read | world model |
| `38aea3bb` | `IsGet.Item_Longshot` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `6d39c600` | `IsGet.Item_MagicBean` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `103a0dc7` | `IsGet.Item_Medal_Fire` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `fcd8d653` | `IsGet.Item_Medal_Forest` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `9026c187` | `IsGet.Item_Medal_Light` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `12d63ac6` | `IsGet.Item_Medal_Shadow` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `e269df38` | `IsGet.Item_Medal_Spirit` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `cf64e780` | `IsGet.Item_Medal_Water` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `00b44241` | `IsGet.Item_NayruLove` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `7215060c` | `IsGet.Item_NormalBoot` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `9a5db0b6` | `IsGet.Item_NutBag_Large` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `960820db` | `IsGet.Item_NutBag_Medium` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `2bedd82e` | `IsGet.Item_NutBag_Small` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `42bd296f` | `IsGet.Item_Ocarina_Fairy` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `1da2c511` | `IsGet.Item_Ocarina_Time` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `cbd7852a` | `IsGet.Item_OddMushroom` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `b75acaad` | `IsGet.Item_OddPowder` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `888d5059` | `IsGet.Item_PoacherSaw` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `e82e6413` | `IsGet.Item_PocketCucco` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `ec9c3136` | `IsGet.Item_PocketEgg` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `d8f1521e` | `IsGet.Item_Prescription` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `21985b09` | `IsGet.Item_Quiver_Large` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `9d872202` | `IsGet.Item_Quiver_Medium` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `0a550531` | `IsGet.Item_Quiver_Small` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `ccc1909a` | `IsGet.Item_Scale_Gold` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `1208fb3e` | `IsGet.Item_Scale_Silver` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `cfbb16f6` | `IsGet.Item_ScrubBusinessSeed` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `a10f2dcf` | `IsGet.Item_StickBag_Large` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `cbf00480` | `IsGet.Item_StickBag_Medium` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `de2389d4` | `IsGet.Item_StickBag_Small` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `8908d6ad` | `IsGet.Item_Stone_Fire` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `110b83ec` | `IsGet.Item_Stone_Forest` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `eec383f5` | `IsGet.Item_Stone_Water` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `0e6264c7` | `IsGet.Item_Token_Gerudo` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `6ba394fe` | `IsGet.Item_Token_Gold` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `b5031190` | `IsGet.Item_Wallet_Large` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `d1360de8` | `IsGet.Item_Wallet_Medium` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `b6e5a3a5` | `IsGet.Item_Wallet_Small` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `44ab1487` | `IsGet.Item_WeirdEgg` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `f19393b5` | `IsGet.Item_ZeldaLetter` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `f9594156` | `IsGet.Obj_Armor_Child_Normal` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `d6168ea8` | `IsGet.Obj_ArrowBundle_Large` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `8d073dca` | `IsGet.Obj_ArrowBundle_Medium` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `e15586a1` | `IsGet.Obj_ArrowBundle_Small` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `c635dd5b` | `IsGet.Obj_BlueFire_A_01` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `4d779571` | `IsGet.Obj_DekuSeed` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `597fca19` | `IsGet.Obj_Fairy` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `551d74fa` | `IsGet.Obj_FairySpirit` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `31b8cfe3` | `IsGet.Obj_Heart` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `bb4e20c9` | `IsGet.Obj_Heart_Container` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `e6aaab65` | `IsGet.Obj_Heart_Piece` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `f400dafb` | `IsGet.Obj_Item_Base` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `778416bd` | `IsGet.Obj_MagicJar_Large` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `ea1484d6` | `IsGet.Obj_MagicJar_Small` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `8f7916a0` | `IsGet.Obj_MiniGame_SmallKey` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `818e5801` | `IsGet.Obj_Rupee_Blue` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `7017ee2f` | `IsGet.Obj_Rupee_Gold` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `ae1a944a` | `IsGet.Obj_Rupee_Green` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `50c65358` | `IsGet.Obj_Rupee_Purple` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `7637800a` | `IsGet.Obj_Rupee_Red` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `96835f39` | `IsGet.Obj_Rupee_Silver` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `7f967a10` | `IsGet.Obj_Spirit_Poe` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `34078e23` | `IsGet.Obj_Spirit_Poe_Big` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `198e75f0` | `IsGet.Obj_Spirit_PoeFlat` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `3644577a` | `IsGet.Obj_Spirit_PoeSharp` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `6f6dc253` | `IsGet.Obj_ZoraDomain_DivingGame_A_01` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `3506a557` | `IsGet.Pouch_Amiibo` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `f9fe4ffc` | `IsGet.Pouch_Range_BowAndArrow_Fire` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `0989e62d` | `IsGet.Pouch_Range_BowAndArrow_Ice` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `b03ae135` | `IsGet.Pouch_Range_BowAndArrow_Light` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `4ca4e4d9` | `IsGet.Shop_ArrowBundle_01` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `9b844298` | `IsGet.Shop_ArrowBundle_02` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `8b36ffa1` | `IsGet.Shop_ArrowBundle_03` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `cebaf02f` | `IsGet.Shop_BombBundle_01` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `0731d7c1` | `IsGet.Shop_BombBundle_02` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `e3eb54da` | `IsGet.Shop_BombBundle_03` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `4e172ee0` | `IsGet.Shop_BombBundle_04` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `c83ec0d7` | `IsGet.Shop_BombchuBundle_01` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `d60acfc5` | `IsGet.Shop_BombchuBundle_02` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `f77eb960` | `IsGet.Shop_BombchuBundle_03` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `e31e56fa` | `IsGet.Shop_BombchuBundle_04` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `26171e2f` | `IsGet.Shop_BombchuBundle_05` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `f31a8caf` | `IsGet.Shop_BombchuBundle_06` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `0ef99e5b` | `IsGet.Shop_BombchuBundle_07` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `4f50f7b9` | `IsGet.Shop_BombchuBundle_08` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `16cdcb17` | `IsGet.Shop_DekuNutBundle_01` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `22892eb4` | `IsGet.Shop_DekuNutBundle_02` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `b680b8e3` | `IsGet.Shop_DekuSeedBundle_01` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `8c3ac4c3` | `IsGet.Shop_DekuSeedBundle_02` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `690da0dd` | `IsGet.Shop_DekuStickBundle_Medium` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `a5060f08` | `IsGet.Shop_Heart_Bundle` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `f22a7811` | `IsGet.TBox_DekuNutBundle` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `75b6ccfe` | `IsGet.TBox_DekuSeedBundle` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `eea74f29` | `IsGet.Weapon_Base` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `e044b44f` | `IsGet.Weapon_Lure` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `69ec28be` | `IsGet.Weapon_Range_Bow` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `0ec22ee1` | `IsGet.Weapon_Range_SlingShot` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `24570b07` | `IsGet.Weapon_Shield_DarkLinkShield` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `5217da1e` | `IsGet.Weapon_Shield_Deku` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `2f817d54` | `IsGet.Weapon_Shield_Hylian` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `75e94e42` | `IsGet.Weapon_Shield_Mirror` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `474f9eb9` | `IsGet.Weapon_SinkingLure` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `33466812` | `IsGet.Weapon_Sword_Biggoron` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `720df203` | `IsGet.Weapon_Sword_BrokenGiant` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `a54698c9` | `IsGet.Weapon_Sword_DarkLinkSword` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `1e824efa` | `IsGet.Weapon_Sword_Giant` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |
| `405d8a0f` | `IsGet.Weapon_Sword_Kokiri` | files | Bool | 0 | 8 | progress | 1 | items, shared |  |  | Got-it-once marker of the Kokiri Sword; seen 0 to 1 when Link got it, and sent to and applied in a second game in a two-game run (its pause menu showed the sword). | tested | CoopGame |
| `7ae38e5b` | `IsGet.Weapon_Sword_Master` | struct | Bool | 0 | 8 | progress | 1 | items, shared |  |  |  | read |  |

### items: item count

| Hash | Name | Named by | Kind | Default | Reset | File | Group | Co-op | Map | Note | What it is | Sure | Source |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `40ae1183` | `PouchData.Armor_Adult_Gauntlet_Gold.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  | Count of the Golden Gauntlets; after the room gives them, co-op raises PlayerStatus.LiftGrade to High so Link can lift the heaviest objects. | read | LS oot_coop.c |
| `0012b8c0` | `PouchData.Armor_Adult_Gauntlet_Silver.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  | Count of the Silver Gauntlets; after the room gives them, co-op raises PlayerStatus.LiftGrade to Middle so Link can lift bigger objects. | read | LS oot_coop.c |
| `21ecbd19` | `PouchData.Armor_Adult_Goron.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `2bad189a` | `PouchData.Armor_Adult_HeavyBoot.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `c9220366` | `PouchData.Armor_Adult_HoverBoot.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `6f631388` | `PouchData.Armor_Adult_Normal.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `b816af94` | `PouchData.Armor_Adult_Zora.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `d1317941` | `PouchData.Armor_Child_Gauntlet_Goron.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  | Count of the Goron's Bracelet; it arrived in a second game through the room (pair run); co-op then raises LiftGrade to Low so Link can lift bombs. | tested | PreMergeChecks |
| `49d1c374` | `PouchData.Armor_GlassTruth.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `d53ce3a7` | `PouchData.BottleA.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `fca29a04` | `PouchData.BottleB.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `893216a1` | `PouchData.BottleC.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `5324f9d3` | `PouchData.BottleD.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `c92b16be` | `PouchData.BottleE.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `5e529ab9` | `PouchData.Item_Arrow_Fire.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `40735a8d` | `PouchData.Item_Arrow_Ice.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `bfb285c8` | `PouchData.Item_Arrow_Light.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `bd3ca2c6` | `PouchData.Item_BombBag_Large.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `e5ff45aa` | `PouchData.Item_BombBag_Medium.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `b0a1bf51` | `PouchData.Item_BombBag_Small.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `a1d76d31` | `PouchData.Item_Boomerang.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `7b9673f5` | `PouchData.Item_BulletBag_Large.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `9a30a9e5` | `PouchData.Item_BulletBag_Medium.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `dc52acaf` | `PouchData.Item_BulletBag_Small.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `b796c16d` | `PouchData.Item_DinFire.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `9a826fab` | `PouchData.Item_FairyBless_DefenseDouble.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `5e671d92` | `PouchData.Item_FairyBless_MP.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `5f043856` | `PouchData.Item_FairyBless_MPDouble.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `47f2ca87` | `PouchData.Item_FaroreWind.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `1aafdb66` | `PouchData.Item_Hammer.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `8573d2cd` | `PouchData.Item_Hookshot.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `8499ea34` | `PouchData.Item_Longshot.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `f0828cd0` | `PouchData.Item_NayruLove.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `55e804de` | `PouchData.Item_NormalBoot.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `d60e4b23` | `PouchData.Item_NutBag_Large.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `eaa1785e` | `PouchData.Item_NutBag_Medium.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `19b80dbc` | `PouchData.Item_NutBag_Small.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `b7df60f1` | `PouchData.Item_Ocarina_Fairy.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  | Count of the Fairy Ocarina (0 to 1 when Link got it from a chest in a test run); co-op names it for the D-pad when the room gives one. | tested | ClawshotChests |
| `54e2a3d1` | `PouchData.Item_Ocarina_Time.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  | Count of the Ocarina of Time; when the room gives it, co-op writes its name into the equipped-ocarina string, never replacing it with a lower ocarina. | read | LS docs/coop.md |
| `d331c7da` | `PouchData.Item_Quiver_Large.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `3bb370e1` | `PouchData.Item_Quiver_Medium.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `a8c3e1fb` | `PouchData.Item_Quiver_Small.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `4aeb140a` | `PouchData.Item_Scale_Gold.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `1240044b` | `PouchData.Item_Scale_Silver.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `48e53698` | `PouchData.Item_StickBag_Large.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `41db7ab5` | `PouchData.Item_StickBag_Medium.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `2fe6ab1a` | `PouchData.Item_StickBag_Small.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `afa4bb52` | `PouchData.Item_Wallet_Large.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `2d2c874b` | `PouchData.Item_Wallet_Medium.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `1d74617e` | `PouchData.Item_Wallet_Small.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `84ba0d24` | `PouchData.Obj_Armor_Child_Normal.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `e32ad20f` | `PouchData.Pouch_Range_BowAndArrow_Fire.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `667c7ba3` | `PouchData.Pouch_Range_BowAndArrow_Ice.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `28298287` | `PouchData.Pouch_Range_BowAndArrow_Light.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `938d56bf` | `PouchData.Weapon_Range_Bow.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `80d34ce9` | `PouchData.Weapon_Range_SlingShot.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `7ca64f23` | `PouchData.Weapon_Shield_Deku.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `08befd3a` | `PouchData.Weapon_Shield_Hylian.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `f58e0e2f` | `PouchData.Weapon_Shield_Mirror.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `b0b3e399` | `PouchData.Weapon_Sword_Biggoron.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |
| `eeb495b9` | `PouchData.Weapon_Sword_Kokiri.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  | Count of Kokiri Swords held; it went to 1 in game B after the other player opened the sword chest in a two-game run (the chest gives nothing twice). | tested | CoopGame |
| `f1c45294` | `PouchData.Weapon_Sword_Master.StockNum` | struct | Int | 0 | 32 | progress | 3 | items, shared |  |  |  | read |  |

### items: magic meter size

| Hash | Name | Named by | Kind | Default | Reset | File | Group | Co-op | Map | Note | What it is | Sure | Source |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `12d63a97` | `PlayerStatus.MPMax` | files | Int | 0 | 8 | progress | 3 | items, shared |  |  | Size of Link's magic meter (240 single, 480 double); the room shares the size, and in a pair run it arrived in game B without any magic in it. | tested | PreMergeChecks |

### keys

| Hash | Name | Named by | Kind | Default | Reset | File | Group | Co-op | Map | Note | What it is | Sure | Source |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `7dd79d10` | `DungeonInfo.BottomOfTheWell.SmallKeyNum` | struct | Int | 0 | 8 | progress | 3 | keys, pool | BottomOfTheWell |  | Small keys held for Bottom of the Well; co-op pools the count by default (rule coop_keys) so every player adds to and spends from one total. | read | LS oot_coop.c |
| `3fdbc3d0` | `DungeonInfo.DodongoCavern.SmallKeyNum` | struct | Int | 0 | 8 | progress | 3 | keys, pool | DodongoCavern |  | Small keys held for Dodongo's Cavern; co-op pools the count by default (rule coop_keys) so every player adds to and spends from one total. | read | LS oot_coop.c |
| `a04bfd48` | `DungeonInfo.FinalBattleField.SmallKeyNum` | struct | Int | 0 | 8 | progress | 3 | keys, pool | FinalBattleField |  | Small keys held for Ganon's arena (FinalBattleField); co-op pools the count by default (rule coop_keys) so every player adds to and spends from one total. | read | LS oot_coop.c |
| `1df11487` | `DungeonInfo.FireTemple.SmallKeyNum` | struct | Int | 0 | 8 | progress | 3 | keys, pool | FireTemple |  | Small keys held for Fire Temple; co-op pools the count by default (rule coop_keys) so every player adds to and spends from one total. | read | LS oot_coop.c |
| `90237092` | `DungeonInfo.ForestTemple.SmallKeyNum` | struct | Int | 0 | 8 | progress | 3 | keys, pool | ForestTemple |  | Small keys held for the Forest Temple, pooled by co-op; in a two-game run one chest raised both players' count from 3 to 4 (no double give). | tested | ChestDedupe |
| `3a28b6a4` | `DungeonInfo.GerudoFortress.SmallKeyNum` | struct | Int | 0 | 8 | progress | 3 | keys, pool | GerudoFortress |  | Small keys held for Gerudo Fortress; co-op pools the count by default (rule coop_keys) so every player adds to and spends from one total. | read | LS oot_coop.c |
| `ea9786f5` | `DungeonInfo.GerudoTrainingGround.SmallKeyNum` | struct | Int | 0 | 8 | progress | 3 | keys, pool | GerudoTrainingGround |  | Small keys held for Gerudo Training Ground; co-op pools the count by default (rule coop_keys) so every player adds to and spends from one total. | read | LS oot_coop.c |
| `fa5d133d` | `DungeonInfo.IceCavern.SmallKeyNum` | struct | Int | 0 | 8 | progress | 3 | keys, pool | IceCavern |  | Small keys held for Ice Cavern; co-op pools the count by default (rule coop_keys) so every player adds to and spends from one total. | read | LS oot_coop.c |
| `fbfd2910` | `DungeonInfo.InsideGanonCastle.SmallKeyNum` | struct | Int | 0 | 8 | progress | 3 | keys, pool | InsideGanonCastle |  | Small keys held for Ganon's Castle; co-op pools the count by default (rule coop_keys) so every player adds to and spends from one total. | read | LS oot_coop.c |
| `1470a816` | `DungeonInfo.InsideJabuJabuBelly.SmallKeyNum` | struct | Int | 0 | 8 | progress | 3 | keys, pool | InsideJabuJabuBelly |  | Small keys held for Jabu-Jabu's Belly; co-op pools the count by default (rule coop_keys) so every player adds to and spends from one total. | read | LS oot_coop.c |
| `0914ba07` | `DungeonInfo.InsideTheDekuTree.SmallKeyNum` | struct | Int | 0 | 8 | progress | 3 | keys, pool | InsideTheDekuTree |  | Small keys held for Deku Tree; co-op pools the count by default (rule coop_keys) so every player adds to and spends from one total. | read | LS oot_coop.c |
| `5edda9e3` | `DungeonInfo.ShadowTemple.SmallKeyNum` | struct | Int | 0 | 8 | progress | 3 | keys, pool | ShadowTemple |  | Small keys held for Shadow Temple; co-op pools the count by default (rule coop_keys) so every player adds to and spends from one total. | read | LS oot_coop.c |
| `79eeec8e` | `DungeonInfo.SpiritTemple.SmallKeyNum` | struct | Int | 0 | 8 | progress | 3 | keys, pool | SpiritTemple |  | Small keys held for Spirit Temple; co-op pools the count by default (rule coop_keys) so every player adds to and spends from one total. | read | LS oot_coop.c |
| `877bdcee` | `DungeonInfo.WaterTemple.SmallKeyNum` | struct | Int | 0 | 8 | progress | 3 | keys, pool | WaterTemple |  | Small keys held for Water Temple; co-op pools the count by default (rule coop_keys) so every player adds to and spends from one total. | read | LS oot_coop.c |

### PouchData.*

| Hash | Name | Named by | Kind | Default | Reset | File | Group | Co-op | Map | Note | What it is | Sure | Source |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `f5e647da` | `PouchData.Armor_Child_Mask_Amiibo0.StockNum` | struct | Int | 0 | 32 | progress | 3 | out: own count |  |  | Count of an amiibo mask, an item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `486c59a4` | `PouchData.Armor_Child_Mask_Amiibo1.StockNum` | struct | Int | 0 | 32 | progress | 3 | out: own count |  |  | Count of an amiibo mask, an item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `7e607033` | `PouchData.Armor_Child_Mask_Bunny.StockNum` | struct | Int | 0 | 32 | progress | 3 | out: own count |  |  | Count of the Bunny Hood, a rented mask the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `0e94a8df` | `PouchData.Armor_Child_Mask_Gerudo.StockNum` | struct | Int | 0 | 32 | progress | 3 | out: own count |  |  | Count of the Gerudo Mask, a rented mask the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `fc508da7` | `PouchData.Armor_Child_Mask_Goron.StockNum` | struct | Int | 0 | 32 | progress | 3 | out: own count |  |  | Count of the Goron Mask, a rented mask the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `b5c10899` | `PouchData.Armor_Child_Mask_Keaton.StockNum` | struct | Int | 0 | 32 | progress | 3 | out: own count |  |  | Count of the Keaton Mask, a rented mask the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `47b2d775` | `PouchData.Armor_Child_Mask_Skull.StockNum` | struct | Int | 0 | 32 | progress | 3 | out: own count |  |  | Count of the Skull Mask, a rented mask the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `f046629e` | `PouchData.Armor_Child_Mask_Spooky.StockNum` | struct | Int | 0 | 32 | progress | 3 | out: own count |  |  | Count of the Spooky Mask, a rented mask the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `96459cd3` | `PouchData.Armor_Child_Mask_Truth.StockNum` | struct | Int | 0 | 32 | progress | 3 | out: own count |  |  | Count of the Mask of Truth, a rented mask the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `924e9a46` | `PouchData.Armor_Child_Mask_Zora.StockNum` | struct | Int | 0 | 32 | progress | 3 | out: own count |  |  | Count of the Zora Mask, a rented mask the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `b6ca6093` | `PouchData.Item_AlarmCucco.StockNum` | struct | Int | 0 | 32 | progress | 3 | out: own count |  |  | Count of the alarm Cucco, a trading-sequence item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `2815c82a` | `PouchData.Item_BrokenSword.StockNum` | struct | Int | 0 | 32 | progress | 3 | out: own count |  |  | Count of the broken sword, a trading-sequence item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `ded8e8d3` | `PouchData.Item_ClaimCheck.StockNum` | struct | Int | 0 | 32 | progress | 3 | out: own count |  |  | Count of the Claim Check, a trading-sequence item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `51d89ef0` | `PouchData.Item_CojiroCucco.StockNum` | struct | Int | 0 | 32 | progress | 3 | out: own count |  |  | Count of Cojiro the Cucco, a trading-sequence item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `919ea324` | `PouchData.Item_EyeballFrog.StockNum` | struct | Int | 0 | 32 | progress | 3 | out: own count |  |  | Count of the Eyeball Frog, a trading-sequence item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `5c41a6b1` | `PouchData.Item_EyeDrop.StockNum` | struct | Int | 0 | 32 | progress | 3 | out: own count |  |  | Count of the Eye Drops, a trading-sequence item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `07de3e6f` | `PouchData.Item_OddMushroom.StockNum` | struct | Int | 0 | 32 | progress | 3 | out: own count |  |  | Count of the Odd Mushroom, a trading-sequence item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `58c9bc78` | `PouchData.Item_OddPowder.StockNum` | struct | Int | 0 | 32 | progress | 3 | out: own count |  |  | Count of the Odd Powder, a trading-sequence item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `a862d276` | `PouchData.Item_PoacherSaw.StockNum` | struct | Int | 0 | 32 | progress | 3 | out: own count |  |  | Count of the Poacher's Saw, a trading-sequence item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `0165e7ca` | `PouchData.Item_PocketCucco.StockNum` | struct | Int | 0 | 32 | progress | 3 | out: own count |  |  | Count of the Pocket Cucco, a trading-sequence item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `07f10aaf` | `PouchData.Item_PocketEgg.StockNum` | struct | Int | 0 | 32 | progress | 3 | out: own count |  |  | Count of the Pocket Egg, a trading-sequence item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `897cf7eb` | `PouchData.Item_Prescription.StockNum` | struct | Int | 0 | 32 | progress | 3 | out: own count |  |  | Count of the Prescription, a trading-sequence item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `600e29eb` | `PouchData.Item_ScrubBusinessSeed.StockNum` | struct | Int | 0 | 32 | progress | 3 | out: own count |  |  | Count of the business scrub's seed item; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `04735978` | `PouchData.Item_Token_Gold.StockNum` | files | Int | 0 | 32 | progress | 3 | out: own count |  |  | Gold Skulltula tokens collected; co-op keeps this count each player's own, since a shared count would pay twice. | read | LS docs/coop.md |
| `24596e8e` | `PouchData.Item_WeirdEgg.StockNum` | struct | Int | 0 | 32 | progress | 3 | out: own count |  |  | Count of the Weird Egg, a trading-sequence item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `6be5c3b0` | `PouchData.Item_ZeldaLetter.StockNum` | struct | Int | 0 | 32 | progress | 3 | out: own count |  |  | Count of Zelda's Letter, a trading-sequence item the game takes away again; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `51ec97b3` | `PouchData.Obj_Heart_Piece.StockNum` | struct | Int | 0 | 32 | progress | 3 | out: own count |  |  | Heart pieces held toward the next heart; co-op keeps the count each player's own, since a shared count would pay twice. | read | LS docs/coop.md |
| `20820479` | `PouchData.Pouch_Amiibo.StockNum` | struct | Int | 0 | 32 | progress | 3 | out: own count |  |  | Count of the amiibo pouch, an amiibo-linked item; co-op keeps this count each player's own (own_counts). | read | LS oot_coop.c |
| `8d02f5ea` | `PouchData.Weapon_Sword_BrokenGiant.StockNum` | struct | Int | 0 | 32 | progress | 3 | out: own count |  |  | Count of the broken Giant's Knife, the knife that breaks; co-op keeps this count each player's own (own_counts). | read | LS docs/coop.md |
| `396a5c02` | `PouchData.Weapon_Sword_Giant.StockNum` | struct | Int | 0 | 32 | progress | 3 | out: own count |  |  | Count of the Giant's Knife, the knife that can break; co-op keeps this count each player's own (own_counts). | read | LS docs/coop.md |

### quest

| Hash | Name | Named by | Kind | Default | Reset | File | Group | Co-op | Map | Note | What it is | Sure | Source |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `f3b14ce2` | `PouchData.Item_AgonyStone.StockNum` | struct | Int | 0 | 32 | progress | 3 | quest, shared |  |  | Count of the Stone of Agony held (1 once Link has it); co-op treats it as a quest item and shares it between players by default (coop_quest). | read | LS oot_coop.c |
| `5ce254a6` | `PouchData.Item_Medal_Fire.StockNum` | struct | Int | 0 | 32 | progress | 3 | quest, shared |  |  | Count of the Fire Medallion held (1 once Link has it); co-op treats it as a quest item and shares it between players by default (coop_quest). | read | LS oot_coop.c |
| `692d57cb` | `PouchData.Item_Medal_Forest.StockNum` | struct | Int | 0 | 32 | progress | 3 | quest, shared |  |  | Count of the Forest Medallion held (1 once Link has it); co-op treats it as a quest item and shares it between players by default (coop_quest). | read | LS oot_coop.c |
| `235c7d9a` | `PouchData.Item_Medal_Light.StockNum` | struct | Int | 0 | 32 | progress | 3 | quest, shared |  |  | Count of the Light Medallion held (1 once Link has it); co-op treats it as a quest item and shares it between players by default (coop_quest). | read | LS oot_coop.c |
| `204d2063` | `PouchData.Item_Medal_Shadow.StockNum` | struct | Int | 0 | 32 | progress | 3 | quest, shared |  |  | Count of the Shadow Medallion held (1 once Link has it); co-op treats it as a quest item and shares it between players by default (coop_quest). | read | LS oot_coop.c |
| `0c7a5fd0` | `PouchData.Item_Medal_Spirit.StockNum` | struct | Int | 0 | 32 | progress | 3 | quest, shared |  |  | Count of the Spirit Medallion held (1 once Link has it); co-op treats it as a quest item and shares it between players by default (coop_quest). | read | LS oot_coop.c |
| `0151a68f` | `PouchData.Item_Medal_Water.StockNum` | struct | Int | 0 | 32 | progress | 3 | quest, shared |  |  | Count of the Water Medallion held (1 once Link has it); co-op treats it as a quest item and shares it between players by default (coop_quest). | read | LS oot_coop.c |
| `7d69ad47` | `PouchData.Item_Stone_Fire.StockNum` | struct | Int | 0 | 32 | progress | 3 | quest, shared |  |  | Count of Goron's Ruby held (1 once Link has it); co-op treats it as a quest item and shares it between players by default (coop_quest). | read | LS oot_coop.c |
| `cbd1e58c` | `PouchData.Item_Stone_Forest.StockNum` | struct | Int | 0 | 32 | progress | 3 | quest, shared |  |  | Count of Kokiri's Emerald held (1 once Link has it); co-op treats it as a quest item and shares it between players by default (coop_quest). | read | LS oot_coop.c |
| `b8e3bf45` | `PouchData.Item_Stone_Water.StockNum` | struct | Int | 0 | 32 | progress | 3 | quest, shared |  |  | Count of Zora's Sapphire held (1 once Link has it); co-op treats it as a quest item and shares it between players by default (coop_quest). | read | LS oot_coop.c |
| `feb4d56b` | `PouchData.Item_Token_Gerudo.StockNum` | struct | Int | 0 | 32 | progress | 3 | quest, shared |  |  | Count of Gerudo's Card held (1 once Link has it); co-op treats it as a quest item and shares it between players by default (coop_quest). | read | LS oot_coop.c |

### rupees

| Hash | Name | Named by | Kind | Default | Reset | File | Group | Co-op | Map | Note | What it is | Sure | Source |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `a77921d7` | `PlayerStatus.CurrentRupee` | files | Int | 0 | 8 | progress | 3 | rupees, own |  |  | Rupees Link holds; each player's own by default, poolable by the room (coop_rupees). Seen rising 0 to 5 in a test run after a blue rupee. | tested | PlayHarness |

### songs

| Hash | Name | Named by | Kind | Default | Reset | File | Group | Co-op | Map | Note | What it is | Sure | Source |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `b492ac33` | `IsGet.Item_Melody_EponaSong` | struct | Bool | 0 | 8 | progress | 1 | songs, shared |  |  | Set once Link has learned Epona's Song; co-op counts the 13 songs as one category (coop_songs) and shares them between players by default. | read | LS oot_coop.c |
| `49041ab9` | `IsGet.Item_Melody_FireBolero` | files | Bool | 0 | 8 | progress | 1 | songs, shared |  |  | Set once Link has learned the Bolero of Fire; co-op counts the 13 songs as one category (coop_songs) and shares them between players by default. | read | LS oot_coop.c |
| `dc0a0b54` | `IsGet.Item_Melody_ForestMinuet` | files | Bool | 0 | 8 | progress | 1 | songs, shared |  |  | Set once Link has learned the Minuet of Forest; co-op counts the 13 songs as one category (coop_songs) and shares them between players by default. | read | LS oot_coop.c |
| `d6320ba4` | `IsGet.Item_Melody_LightPrelude` | struct | Bool | 0 | 8 | progress | 1 | songs, shared |  |  | Set once Link has learned the Prelude of Light; co-op counts the 13 songs as one category (coop_songs) and shares them between players by default. | read | LS oot_coop.c |
| `d3f8bfcc` | `IsGet.Item_Melody_SariaSong` | files | Bool | 0 | 8 | progress | 1 | songs, shared |  |  | Set once Link has learned Saria's Song; co-op counts the 13 songs as one category (coop_songs) and shares them between players by default. | read | LS oot_coop.c |
| `5e86fb4d` | `IsGet.Item_Melody_ScarecrowSong` | struct | Bool | 0 | 8 | progress | 1 | songs, shared |  |  | Set once Link has learned the Scarecrow's Song; co-op counts the 13 songs as one category (coop_songs) and shares them between players by default. | read | LS oot_coop.c |
| `c2fb95f4` | `IsGet.Item_Melody_ShadowNocturne` | files | Bool | 0 | 8 | progress | 1 | songs, shared |  |  | Set once Link has learned the Nocturne of Shadow; co-op counts the 13 songs as one category (coop_songs) and shares them between players by default. | read | LS oot_coop.c |
| `802a36a8` | `IsGet.Item_Melody_SpiritRequiem` | files | Bool | 0 | 8 | progress | 1 | songs, shared |  |  | Set once Link has learned the Requiem of Spirit; co-op counts the 13 songs as one category (coop_songs) and shares them between players by default. | read | LS oot_coop.c |
| `2b39dd4f` | `IsGet.Item_Melody_StormSong` | files | Bool | 0 | 8 | progress | 1 | songs, shared |  |  | Set once Link has learned the Song of Storms; co-op counts the 13 songs as one category (coop_songs) and shares them between players by default. | read | LS oot_coop.c |
| `165dd1ad` | `IsGet.Item_Melody_SunSong` | files | Bool | 0 | 8 | progress | 1 | songs, shared |  |  | Set once Link has learned the Sun's Song; co-op counts the 13 songs as one category (coop_songs) and shares them between players by default. | read | LS oot_coop.c |
| `03b3450e` | `IsGet.Item_Melody_TimeSong` | struct | Bool | 0 | 8 | progress | 1 | songs, shared |  |  | Set once Link has learned the Song of Time; co-op counts the 13 songs as one category (coop_songs) and shares them between players by default. | read | LS oot_coop.c |
| `3fa63986` | `IsGet.Item_Melody_WaterSerenade` | files | Bool | 0 | 8 | progress | 1 | songs, shared |  |  | Set once Link has learned the Serenade of Water; co-op counts the 13 songs as one category (coop_songs) and shares them between players by default. | read | LS oot_coop.c |
| `01c20002` | `IsGet.Item_Melody_ZeldaLullaby` | files | Bool | 0 | 8 | progress | 1 | songs, shared |  |  | Set once Link has learned Zelda's Lullaby; co-op counts the 13 songs as one category (coop_songs) and shares them between players by default. | read | LS oot_coop.c |
