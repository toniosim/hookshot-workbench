# Flag map: Dungeons: rooms, maps, logic nodes (1 of 3)

The per-room state of every dungeon and its Master Quest twin, each dungeon's map, compass and boss key flags and key counter, and the logic nodes the game names only by an id. 1089 rows on this page. Columns, values and how sure a row is: [README.md](README.md).

### AutogenGameDataLogicNode.*

| Hash | Name | Named by | Kind | Default | Reset | File | Group | Co-op | Map | Note | What it is | Sure | Source |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `a82cc7a2` | `AutogenGameDataLogicNode.15744991116824525035-1232849570` | names file | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |

### DungeonInfo.*

| Hash | Name | Named by | Kind | Default | Reset | File | Group | Co-op | Map | Note | What it is | Sure | Source |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `95d169fe` | `DungeonInfo.BottomOfTheWell.BossRetryNum` | struct | Int | 0 | 160 | none | - | out: Int in no group | BottomOfTheWell |  |  | read |  |
| `9402715c` | `DungeonInfo.BottomOfTheWell.IsGetBossKey` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | BottomOfTheWell |  | Set once Link has the boss key of Bottom of the Well; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `9d6efaac` | `DungeonInfo.BottomOfTheWell.IsGetCompass` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | BottomOfTheWell |  | Set once Link has the compass of Bottom of the Well; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `77c47ec9` | `DungeonInfo.BottomOfTheWell.IsGetMap` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | BottomOfTheWell |  | Set once Link has the map of Bottom of the Well; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `524465db` | `DungeonInfo.DodongoCavern.BossRetryNum` | files | Int | 0 | 160 | none | - | out: Int in no group | DodongoCavern |  |  | read |  |
| `faabc084` | `DungeonInfo.DodongoCavern.IsGetBossKey` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DodongoCavern |  | Set once Link has the boss key of Dodongo's Cavern; the game has the flag but that boss door has no lock; co-op shares it and refreshes the HUD map after a hand-over. | read | boss points |
| `8b93edf9` | `DungeonInfo.DodongoCavern.IsGetCompass` | files | Bool | 0 | 8 | progress | 1 | progress, shared | DodongoCavern |  | Set once Link has the compass of Dodongo's Cavern; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `a52c3a19` | `DungeonInfo.DodongoCavern.IsGetMap` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DodongoCavern |  | Set once Link has the map of Dodongo's Cavern; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `5e698f1f` | `DungeonInfo.FinalBattleField.BossRetryNum` | files | Int | 0 | 160 | none | - | out: Int in no group | FinalBattleField |  |  | read |  |
| `6d0fea11` | `DungeonInfo.FinalBattleField.IsGetBossKey` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FinalBattleField |  | Set once Link has the boss key of Ganon's arena (FinalBattleField); co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `874493ce` | `DungeonInfo.FinalBattleField.IsGetCompass` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FinalBattleField |  | Set once Link has the compass of Ganon's arena (FinalBattleField); co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `b3b65c1a` | `DungeonInfo.FinalBattleField.IsGetMap` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FinalBattleField |  | Set once Link has the map of Ganon's arena (FinalBattleField); co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `744f77a3` | `DungeonInfo.FireTemple.BossRetryNum` | files | Int | 0 | 160 | none | - | out: Int in no group | FireTemple |  |  | read |  |
| `b72d73df` | `DungeonInfo.FireTemple.IsGetBossKey` | files | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  | Set once Link has the boss key of Fire Temple; BossPoints reads it as what the chained boss door needs; co-op shares it and refreshes the HUD afterwards. | read | boss points |
| `0aa068b6` | `DungeonInfo.FireTemple.IsGetCompass` | files | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  | Set once Link has the compass of Fire Temple; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `5b3ac0ba` | `DungeonInfo.FireTemple.IsGetMap` | files | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  | Set once Link has the map of Fire Temple; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `1a678f6d` | `DungeonInfo.ForestTemple.BossRetryNum` | files | Int | 0 | 160 | none | - | out: Int in no group | ForestTemple |  |  | read |  |
| `427333a0` | `DungeonInfo.ForestTemple.IsGetBossKey` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  | Set once Link has the boss key of Forest Temple; test saves set it and the boss door opened (BossPoints); co-op shares it and refreshes the HUD afterwards. | tested | boss points |
| `f240eeb2` | `DungeonInfo.ForestTemple.IsGetCompass` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  | Set once Link has the compass of Forest Temple; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `e704f9b4` | `DungeonInfo.ForestTemple.IsGetMap` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  | Set once Link has the map of Forest Temple; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `270b462d` | `DungeonInfo.GerudoFortress.BossRetryNum` | struct | Int | 0 | 160 | none | - | out: Int in no group | GerudoFortress |  |  | read |  |
| `95fbcb7c` | `DungeonInfo.GerudoFortress.IsGetBossKey` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | GerudoFortress |  | Set once Link has the boss key of Gerudo Fortress; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `5eb80679` | `DungeonInfo.GerudoFortress.IsGetCompass` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | GerudoFortress |  | Set once Link has the compass of Gerudo Fortress; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `bcaad6ce` | `DungeonInfo.GerudoFortress.IsGetMap` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | GerudoFortress |  | Set once Link has the map of Gerudo Fortress; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `aed356ef` | `DungeonInfo.GerudoTrainingGround.BossRetryNum` | struct | Int | 0 | 160 | none | - | out: Int in no group | GerudoTrainingGround |  |  | read |  |
| `6d155841` | `DungeonInfo.GerudoTrainingGround.IsGetBossKey` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | GerudoTrainingGround |  | Set once Link has the boss key of Gerudo Training Ground; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `3d9a2750` | `DungeonInfo.GerudoTrainingGround.IsGetCompass` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | GerudoTrainingGround |  | Set once Link has the compass of Gerudo Training Ground; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `4b36041e` | `DungeonInfo.GerudoTrainingGround.IsGetMap` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | GerudoTrainingGround |  | Set once Link has the map of Gerudo Training Ground; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `187419de` | `DungeonInfo.IceCavern.BossRetryNum` | struct | Int | 0 | 160 | none | - | out: Int in no group | IceCavern |  |  | read |  |
| `275f4512` | `DungeonInfo.IceCavern.IsGetBossKey` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | IceCavern |  | Set once Link has the boss key of Ice Cavern; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `ea1846e6` | `DungeonInfo.IceCavern.IsGetCompass` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | IceCavern |  | Set once Link has the compass of Ice Cavern; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `322f2a94` | `DungeonInfo.IceCavern.IsGetMap` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | IceCavern |  | Set once Link has the map of Ice Cavern; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `86042b9d` | `DungeonInfo.InsideGanonCastle.BossRetryNum` | struct | Int | 0 | 160 | none | - | out: Int in no group | InsideGanonCastle |  |  | read |  |
| `2fd59293` | `DungeonInfo.InsideGanonCastle.IsGetBossKey` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  | Set once Link has the boss key of Ganon's Castle; test saves set it and the boss door opened (BossPoints); co-op shares it and refreshes the HUD afterwards. | tested | boss points |
| `c4d4734e` | `DungeonInfo.InsideGanonCastle.IsGetCompass` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  | Set once Link has the compass of Ganon's Castle; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `9bbc0c4a` | `DungeonInfo.InsideGanonCastle.IsGetMap` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  | Set once Link has the map of Ganon's Castle; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `a0d51ec6` | `DungeonInfo.InsideJabuJabuBelly.BossRetryNum` | files | Int | 0 | 160 | none | - | out: Int in no group | InsideJabuJabuBelly |  |  | read |  |
| `656bd5ee` | `DungeonInfo.InsideJabuJabuBelly.IsGetBossKey` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideJabuJabuBelly |  | Set once Link has the boss key of Jabu-Jabu's Belly; the game has the flag but that boss door has no lock; co-op shares it and refreshes the HUD map after a hand-over. | read | boss points |
| `9a2218db` | `DungeonInfo.InsideJabuJabuBelly.IsGetCompass` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideJabuJabuBelly |  | Set once Link has the compass of Jabu-Jabu's Belly; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `fcadd210` | `DungeonInfo.InsideJabuJabuBelly.IsGetMap` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideJabuJabuBelly |  | Set once Link has the map of Jabu-Jabu's Belly; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `dfc39d4e` | `DungeonInfo.InsideTheDekuTree.BossRetryNum` | files | Int | 0 | 160 | none | - | out: Int in no group | InsideTheDekuTree |  |  | read |  |
| `f6995cee` | `DungeonInfo.InsideTheDekuTree.IsGetBossKey` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  | Set once Link has the boss key of Deku Tree; the game has the flag but that boss door has no lock; co-op shares it and refreshes the HUD map after a hand-over. | read | boss points |
| `06c51ff2` | `DungeonInfo.InsideTheDekuTree.IsGetCompass` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  | Set once Link has the compass of Deku Tree; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `89787395` | `DungeonInfo.InsideTheDekuTree.IsGetMap` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  | Set once Link has the Deku Tree's map; co-op shares it and refreshes the HUD about 300 ms later; in a two-game run the other player's minimap lit up. | tested | Fold68 |
| `460cb4fa` | `DungeonInfo.ShadowTemple.BossRetryNum` | files | Int | 0 | 160 | none | - | out: Int in no group | ShadowTemple |  |  | read |  |
| `c33c66cf` | `DungeonInfo.ShadowTemple.IsGetBossKey` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  | Set once Link has the boss key of Shadow Temple; test saves set it and the boss door opened (BossPoints); co-op shares it and refreshes the HUD afterwards. | tested | boss points |
| `1e2feec5` | `DungeonInfo.ShadowTemple.IsGetCompass` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  | Set once Link has the compass of Shadow Temple; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `f6177b93` | `DungeonInfo.ShadowTemple.IsGetMap` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  | Set once Link has the map of Shadow Temple; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `36dd30a1` | `DungeonInfo.SpiritTemple.BossRetryNum` | struct | Int | 0 | 160 | none | - | out: Int in no group | SpiritTemple |  |  | read |  |
| `1984c03f` | `DungeonInfo.SpiritTemple.IsGetBossKey` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  | Set once Link has the boss key of Spirit Temple; test saves set it and the boss door opened (BossPoints); co-op shares it and refreshes the HUD afterwards. | tested | boss points |
| `9bd1181c` | `DungeonInfo.SpiritTemple.IsGetCompass` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  | Set once Link has the compass of Spirit Temple; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `b85002ba` | `DungeonInfo.SpiritTemple.IsGetMap` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  | Set once Link has the map of Spirit Temple; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `4cde1d31` | `DungeonInfo.WaterTemple.BossRetryNum` | files | Int | 0 | 160 | none | - | out: Int in no group | WaterTemple |  |  | read |  |
| `79daf80a` | `DungeonInfo.WaterTemple.IsGetBossKey` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | WaterTemple |  | Set once Link has the boss key of Water Temple; test saves set it and the boss door opened (BossPoints); co-op shares it and refreshes the HUD afterwards. | tested | boss points |
| `2e82c8fe` | `DungeonInfo.WaterTemple.IsGetCompass` | files | Bool | 0 | 8 | progress | 1 | progress, shared | WaterTemple |  | Set once Link has the compass of Water Temple; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |
| `4a4402ab` | `DungeonInfo.WaterTemple.IsGetMap` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | WaterTemple |  | Set once Link has the map of Water Temple; co-op shares it and refreshes the HUD map about 300 ms after the room hands it over. | read | LS docs/coop.md |

### DungeonRoomStep.*

| Hash | Name | Named by | Kind | Default | Reset | File | Group | Co-op | Map | Note | What it is | Sure | Source |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `4f73daa4` | `DungeonRoomStep.BottomOfTheWell.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | BottomOfTheWell |  |  | read |  |
| `d00df327` | `DungeonRoomStep.BottomOfTheWell.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | BottomOfTheWell |  |  | read |  |
| `696d6d75` | `DungeonRoomStep.BottomOfTheWell.DungeonRoom001.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | BottomOfTheWell |  |  | read |  |
| `5e29adad` | `DungeonRoomStep.BottomOfTheWell.DungeonRoom001.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | BottomOfTheWell |  |  | read |  |
| `bcc7c886` | `DungeonRoomStep.BottomOfTheWell.DungeonRoom002.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | BottomOfTheWell |  |  | read |  |
| `e9fd05b9` | `DungeonRoomStep.BottomOfTheWell.DungeonRoom002.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | BottomOfTheWell |  |  | read |  |
| `3bb9b6c8` | `DungeonRoomStep.BottomOfTheWell.DungeonRoom003.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | BottomOfTheWell |  |  | read |  |
| `c6a8c7f8` | `DungeonRoomStep.BottomOfTheWell.DungeonRoom003.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | BottomOfTheWell |  |  | read |  |
| `e1fbe6cc` | `DungeonRoomStep.BottomOfTheWell.DungeonRoom004.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | BottomOfTheWell |  |  | read |  |
| `eeedae79` | `DungeonRoomStep.BottomOfTheWell.DungeonRoom004.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | BottomOfTheWell |  |  | read |  |
| `8ea6506c` | `DungeonRoomStep.BottomOfTheWell.DungeonRoom005.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | BottomOfTheWell |  |  | read |  |
| `490400f1` | `DungeonRoomStep.BottomOfTheWell.DungeonRoom005.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | BottomOfTheWell |  |  | read |  |
| `c54ef668` | `DungeonRoomStep.BottomOfTheWell.DungeonRoom006.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | BottomOfTheWell |  |  | read |  |
| `1b2bd15a` | `DungeonRoomStep.BottomOfTheWell.DungeonRoom006.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | BottomOfTheWell |  |  | read |  |
| `f7ef1d7f` | `DungeonRoomStep.BottomOfTheWell.DungeonRoom007.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | BottomOfTheWell |  |  | read |  |
| `7d32f106` | `DungeonRoomStep.BottomOfTheWell.DungeonRoom007.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | BottomOfTheWell |  |  | read |  |
| `edf76ac9` | `DungeonRoomStep.BottomOfTheWell.DungeonRoom008.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | BottomOfTheWell |  |  | read |  |
| `c27bd37f` | `DungeonRoomStep.BottomOfTheWell.DungeonRoom008.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | BottomOfTheWell |  |  | read |  |
| `07b25b90` | `DungeonRoomStep.BottomOfTheWell.DungeonRoom009.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | BottomOfTheWell |  |  | read |  |
| `c160f1f3` | `DungeonRoomStep.BottomOfTheWell.DungeonRoom009.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | BottomOfTheWell |  |  | read |  |
| `4669aa67` | `DungeonRoomStep.BottomOfTheWell.DungeonRoom010.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | BottomOfTheWell |  |  | read |  |
| `dee37df4` | `DungeonRoomStep.BottomOfTheWell.DungeonRoom010.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | BottomOfTheWell |  |  | read |  |
| `10e7b51b` | `DungeonRoomStep.BottomOfTheWell.DungeonRoom011.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | BottomOfTheWell |  |  | read |  |
| `1ee0c650` | `DungeonRoomStep.BottomOfTheWell.DungeonRoom011.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | BottomOfTheWell |  |  | read |  |
| `cee35aeb` | `DungeonRoomStep.BottomOfTheWell.DungeonRoom012.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | BottomOfTheWell |  |  | read |  |
| `08d88d98` | `DungeonRoomStep.BottomOfTheWell.DungeonRoom012.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | BottomOfTheWell |  |  | read |  |
| `7103a12e` | `DungeonRoomStep.BottomOfTheWell_MQ.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `4a9ff61e` | `DungeonRoomStep.BottomOfTheWell_MQ.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `1fc76664` | `DungeonRoomStep.BottomOfTheWell_MQ.DungeonRoom001.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `3b4a0efc` | `DungeonRoomStep.BottomOfTheWell_MQ.DungeonRoom001.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `3502d3a7` | `DungeonRoomStep.BottomOfTheWell_MQ.DungeonRoom002.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `36e9683d` | `DungeonRoomStep.BottomOfTheWell_MQ.DungeonRoom002.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `11339f70` | `DungeonRoomStep.BottomOfTheWell_MQ.DungeonRoom003.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `d7127f71` | `DungeonRoomStep.BottomOfTheWell_MQ.DungeonRoom003.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `59fa199a` | `DungeonRoomStep.BottomOfTheWell_MQ.DungeonRoom004.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `00d4fc35` | `DungeonRoomStep.BottomOfTheWell_MQ.DungeonRoom004.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `8131518d` | `DungeonRoomStep.BottomOfTheWell_MQ.DungeonRoom005.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `5df477f0` | `DungeonRoomStep.BottomOfTheWell_MQ.DungeonRoom005.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `af049286` | `DungeonRoomStep.BottomOfTheWell_MQ.DungeonRoom006.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `7594791b` | `DungeonRoomStep.BottomOfTheWell_MQ.DungeonRoom006.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `fa16614d` | `DungeonRoomStep.BottomOfTheWell_MQ.DungeonRoom007.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `a83fd291` | `DungeonRoomStep.BottomOfTheWell_MQ.DungeonRoom007.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `418ab0db` | `DungeonRoomStep.BottomOfTheWell_MQ.DungeonRoom008.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `c8a504c5` | `DungeonRoomStep.BottomOfTheWell_MQ.DungeonRoom008.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `a08cbcbc` | `DungeonRoomStep.BottomOfTheWell_MQ.DungeonRoom009.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `deb4fda5` | `DungeonRoomStep.BottomOfTheWell_MQ.DungeonRoom009.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `03250199` | `DungeonRoomStep.BottomOfTheWell_MQ.DungeonRoom010.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `fa3d4038` | `DungeonRoomStep.BottomOfTheWell_MQ.DungeonRoom010.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `19a14c15` | `DungeonRoomStep.BottomOfTheWell_MQ.DungeonRoom011.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `3dee37d0` | `DungeonRoomStep.BottomOfTheWell_MQ.DungeonRoom011.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `51ca716c` | `DungeonRoomStep.BottomOfTheWell_MQ.DungeonRoom012.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `65d50c3e` | `DungeonRoomStep.BottomOfTheWell_MQ.DungeonRoom012.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `3e84d35b` | `DungeonRoomStep.DeathMountainCrater_Adult.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DeathMountainCrater |  |  | read |  |
| `4c8a90b1` | `DungeonRoomStep.DeathMountainCrater_Adult.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DeathMountainCrater |  |  | read |  |
| `55380808` | `DungeonRoomStep.DeathMountainCrater_Adult.DungeonRoom001.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DeathMountainCrater |  |  | read |  |
| `fa6effb9` | `DungeonRoomStep.DeathMountainCrater_Adult.DungeonRoom001.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DeathMountainCrater |  |  | read |  |
| `862e2f02` | `DungeonRoomStep.DeathMountainCrater_Adult.DungeonRoom002.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DeathMountainCrater |  |  | read |  |
| `bb9415c5` | `DungeonRoomStep.DeathMountainCrater_Adult.DungeonRoom002.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DeathMountainCrater |  |  | read |  |
| `30a0bd95` | `DungeonRoomStep.DeathMountainCrater_Adult.DungeonRoom003.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DeathMountainCrater |  |  | read |  |
| `54ecb343` | `DungeonRoomStep.DeathMountainCrater_Adult.DungeonRoom003.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DeathMountainCrater |  |  | read |  |
| `df9e2586` | `DungeonRoomStep.DeathMountainCrater_Child.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DeathMountainCrater |  |  | read |  |
| `56f2c9b7` | `DungeonRoomStep.DeathMountainCrater_Child.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DeathMountainCrater |  |  | read |  |
| `355cb0b0` | `DungeonRoomStep.DeathMountainCrater_Child.DungeonRoom001.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DeathMountainCrater |  |  | read |  |
| `0e612e94` | `DungeonRoomStep.DeathMountainCrater_Child.DungeonRoom001.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DeathMountainCrater |  |  | read |  |
| `fb8616e8` | `DungeonRoomStep.DeathMountainCrater_Child.DungeonRoom002.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DeathMountainCrater |  |  | read |  |
| `eb3a020b` | `DungeonRoomStep.DeathMountainCrater_Child.DungeonRoom002.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DeathMountainCrater |  |  | read |  |
| `5783b61f` | `DungeonRoomStep.DeathMountainCrater_Child.DungeonRoom003.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DeathMountainCrater |  |  | read |  |
| `e64fbd4c` | `DungeonRoomStep.DeathMountainCrater_Child.DungeonRoom003.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DeathMountainCrater |  |  | read |  |
| `e608c714` | `DungeonRoomStep.DesertColossus_Adult.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DesertColossus |  |  | read |  |
| `07a5607e` | `DungeonRoomStep.DesertColossus_Adult.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DesertColossus |  |  | read |  |
| `3dc43aaa` | `DungeonRoomStep.DodongoCavern.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DodongoCavern |  |  | read |  |
| `f615d970` | `DungeonRoomStep.DodongoCavern.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DodongoCavern |  |  | read |  |
| `b45b1690` | `DungeonRoomStep.DodongoCavern.DungeonRoom001.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DodongoCavern |  |  | read |  |
| `d79030bc` | `DungeonRoomStep.DodongoCavern.DungeonRoom001.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DodongoCavern |  |  | read |  |
| `cdc83a27` | `DungeonRoomStep.DodongoCavern.DungeonRoom002.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DodongoCavern |  |  | read |  |
| `5178f214` | `DungeonRoomStep.DodongoCavern.DungeonRoom002.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DodongoCavern |  |  | read |  |
| `8f0bb7e6` | `DungeonRoomStep.DodongoCavern.DungeonRoom003.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DodongoCavern |  |  | read |  |
| `de20de3a` | `DungeonRoomStep.DodongoCavern.DungeonRoom003.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DodongoCavern |  |  | read |  |
| `8d78b325` | `DungeonRoomStep.DodongoCavern.DungeonRoom004.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DodongoCavern |  |  | read |  |
| `e247d812` | `DungeonRoomStep.DodongoCavern.DungeonRoom004.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DodongoCavern |  |  | read |  |
| `e57277ba` | `DungeonRoomStep.DodongoCavern.DungeonRoom005.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DodongoCavern |  |  | read |  |
| `d9aada0e` | `DungeonRoomStep.DodongoCavern.DungeonRoom005.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DodongoCavern |  |  | read |  |
| `dd168541` | `DungeonRoomStep.DodongoCavern.DungeonRoom006.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DodongoCavern |  |  | read |  |
| `b73cd674` | `DungeonRoomStep.DodongoCavern.DungeonRoom006.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DodongoCavern |  |  | read |  |
| `aaf20b73` | `DungeonRoomStep.DodongoCavern.DungeonRoom007.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DodongoCavern |  |  | read |  |
| `92bb3914` | `DungeonRoomStep.DodongoCavern.DungeonRoom007.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DodongoCavern |  |  | read |  |
| `6a8fd944` | `DungeonRoomStep.DodongoCavern.DungeonRoom008.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DodongoCavern |  |  | read |  |
| `748aa51a` | `DungeonRoomStep.DodongoCavern.DungeonRoom008.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DodongoCavern |  |  | read |  |
| `595d21f7` | `DungeonRoomStep.DodongoCavern.DungeonRoom009.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DodongoCavern |  |  | read |  |
| `1b1efe2b` | `DungeonRoomStep.DodongoCavern.DungeonRoom009.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DodongoCavern |  |  | read |  |
| `9f00ac79` | `DungeonRoomStep.DodongoCavern.DungeonRoom010.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DodongoCavern |  |  | read |  |
| `050d9011` | `DungeonRoomStep.DodongoCavern.DungeonRoom010.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DodongoCavern |  |  | read |  |
| `55c3d987` | `DungeonRoomStep.DodongoCavern.DungeonRoom011.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DodongoCavern |  |  | read |  |
| `f4870197` | `DungeonRoomStep.DodongoCavern.DungeonRoom011.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DodongoCavern |  |  | read |  |
| `05b7c9e1` | `DungeonRoomStep.DodongoCavern.DungeonRoom012.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DodongoCavern |  |  | read |  |
| `08577a98` | `DungeonRoomStep.DodongoCavern.DungeonRoom012.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DodongoCavern |  |  | read |  |
| `baf3da45` | `DungeonRoomStep.DodongoCavern.DungeonRoom013.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DodongoCavern |  |  | read |  |
| `a92f31ec` | `DungeonRoomStep.DodongoCavern.DungeonRoom013.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DodongoCavern |  |  | read |  |
| `e39afb3e` | `DungeonRoomStep.DodongoCavern.DungeonRoom014.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DodongoCavern |  |  | read |  |
| `bde2d210` | `DungeonRoomStep.DodongoCavern.DungeonRoom014.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DodongoCavern |  |  | read |  |
| `41541eea` | `DungeonRoomStep.DodongoCavern.DungeonRoom015.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DodongoCavern |  |  | read |  |
| `9bf86684` | `DungeonRoomStep.DodongoCavern.DungeonRoom015.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DodongoCavern |  |  | read |  |
| `b59a71af` | `DungeonRoomStep.DodongoCavern.DungeonRoom016.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DodongoCavern |  |  | read |  |
| `f722b0a8` | `DungeonRoomStep.DodongoCavern.DungeonRoom016.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DodongoCavern |  |  | read |  |
| `181bc4e5` | `DungeonRoomStep.DodongoCavern.DungeonRoom017.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DodongoCavern |  |  | read |  |
| `96d46c28` | `DungeonRoomStep.DodongoCavern.DungeonRoom017.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DodongoCavern |  |  | read |  |
| `9081f74b` | `DungeonRoomStep.DodongoCavern.DungeonRoom018.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DodongoCavern |  |  | read |  |
| `f31f2b0c` | `DungeonRoomStep.DodongoCavern.DungeonRoom018.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DodongoCavern |  |  | read |  |
| `3f6999cc` | `DungeonRoomStep.DodongoCavern.DungeonRoom019.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DodongoCavern |  |  | read |  |
| `db93223d` | `DungeonRoomStep.DodongoCavern.DungeonRoom019.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DodongoCavern |  |  | read |  |
| `87d32666` | `DungeonRoomStep.DodongoCavern.DungeonRoom020.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DodongoCavern |  |  | read |  |
| `e924bce5` | `DungeonRoomStep.DodongoCavern.DungeonRoom020.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DodongoCavern |  |  | read |  |
| `34eb03bb` | `DungeonRoomStep.DodongoCavern.DungeonRoom021.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DodongoCavern |  |  | read |  |
| `4803430d` | `DungeonRoomStep.DodongoCavern.DungeonRoom021.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DodongoCavern |  |  | read |  |
| `19417868` | `DungeonRoomStep.DodongoCavern.DungeonRoom022.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | DodongoCavern |  |  | read |  |
| `58806919` | `DungeonRoomStep.DodongoCavern.DungeonRoom022.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | DodongoCavern |  |  | read |  |
| `b7b699d6` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `6092e672` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `5e6e34b2` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom001.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `3a551f72` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom001.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `5ad5f065` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom002.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `9f5fd590` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom002.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `d7b5e7fe` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom003.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `04d663b7` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom003.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `aa8c657a` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom004.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `c44623f6` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom004.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `a500d9c1` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom005.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `37652f81` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom005.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `0fbca9d5` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom006.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `da2b6f36` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom006.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `d0e00e9c` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom007.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `7dc38671` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom007.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `07588a42` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom008.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `42247bcf` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom008.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `2b7d8b8b` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom009.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `3f5d9220` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom009.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `c1e47b29` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom010.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `184629bf` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom010.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `025e7f71` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom011.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `ee848746` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom011.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `abb4d4c5` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom012.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `cf71f84b` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom012.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `c070d246` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom013.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `e356c1b2` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom013.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `4ba88641` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom014.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `df13e56b` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom014.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `6a7cbbdc` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom015.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `d1e4c980` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom015.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `4b879ae9` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom016.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `1a3a16cc` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom016.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `07e993d2` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom017.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `1ee989e3` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom017.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `e20cf38d` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom018.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `5c99e6a7` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom018.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `002c18ad` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom019.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `c5b425df` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom019.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `18ecd7bc` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom020.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `7ecfdec8` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom020.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `a3f17c18` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom021.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `6d8fc957` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom021.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `5a4a636c` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom022.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `0f0d441b` | `DungeonRoomStep.DodongoCavern_MQ.DungeonRoom022.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `530d6db0` | `DungeonRoomStep.DreamWorld.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `2577f148` | `DungeonRoomStep.DreamWorld.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `802d69f4` | `DungeonRoomStep.DreamWorld.DungeonRoom001.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `ca1eb5f4` | `DungeonRoomStep.DreamWorld.DungeonRoom001.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `4f30f378` | `DungeonRoomStep.FinalBattleField.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FinalBattleField |  |  | read |  |
| `6feca4fd` | `DungeonRoomStep.FinalBattleField.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FinalBattleField |  |  | read |  |
| `98970744` | `DungeonRoomStep.FireTemple.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `b4009ce9` | `DungeonRoomStep.FireTemple.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `8c3643fa` | `DungeonRoomStep.FireTemple.DungeonRoom001.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `226bc5d4` | `DungeonRoomStep.FireTemple.DungeonRoom001.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `ec6bff41` | `DungeonRoomStep.FireTemple.DungeonRoom002.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `bd8ad189` | `DungeonRoomStep.FireTemple.DungeonRoom002.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `d10452c2` | `DungeonRoomStep.FireTemple.DungeonRoom003.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `220fb8b9` | `DungeonRoomStep.FireTemple.DungeonRoom003.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `ceb0c2d5` | `DungeonRoomStep.FireTemple.DungeonRoom004.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `a3944bf1` | `DungeonRoomStep.FireTemple.DungeonRoom004.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `b591d776` | `DungeonRoomStep.FireTemple.DungeonRoom005.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `342500e1` | `DungeonRoomStep.FireTemple.DungeonRoom005.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `ba714d43` | `DungeonRoomStep.FireTemple.DungeonRoom006.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `0fbb53d9` | `DungeonRoomStep.FireTemple.DungeonRoom006.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `a1eb24d9` | `DungeonRoomStep.FireTemple.DungeonRoom007.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `4ff58c03` | `DungeonRoomStep.FireTemple.DungeonRoom007.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `9f0d47ed` | `DungeonRoomStep.FireTemple.DungeonRoom008.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `7c1528d6` | `DungeonRoomStep.FireTemple.DungeonRoom008.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `996071c4` | `DungeonRoomStep.FireTemple.DungeonRoom009.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `ced18370` | `DungeonRoomStep.FireTemple.DungeonRoom009.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `5fa4205c` | `DungeonRoomStep.FireTemple.DungeonRoom010.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `58f5ae98` | `DungeonRoomStep.FireTemple.DungeonRoom010.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `e3218d18` | `DungeonRoomStep.FireTemple.DungeonRoom011.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `3249df15` | `DungeonRoomStep.FireTemple.DungeonRoom011.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `f0f67937` | `DungeonRoomStep.FireTemple.DungeonRoom012.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `8fc3b9ba` | `DungeonRoomStep.FireTemple.DungeonRoom012.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `5970dce2` | `DungeonRoomStep.FireTemple.DungeonRoom013.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `55a193c4` | `DungeonRoomStep.FireTemple.DungeonRoom013.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `493f98f7` | `DungeonRoomStep.FireTemple.DungeonRoom014.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `37426f12` | `DungeonRoomStep.FireTemple.DungeonRoom014.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `be80ded1` | `DungeonRoomStep.FireTemple.DungeonRoom015.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `876f4cbd` | `DungeonRoomStep.FireTemple.DungeonRoom015.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `ea13a90b` | `DungeonRoomStep.FireTemple.DungeonRoom016.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `cb321b63` | `DungeonRoomStep.FireTemple.DungeonRoom016.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `3004821d` | `DungeonRoomStep.FireTemple.DungeonRoom017.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `9222de54` | `DungeonRoomStep.FireTemple.DungeonRoom017.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `32b858a6` | `DungeonRoomStep.FireTemple.DungeonRoom018.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `1acc700c` | `DungeonRoomStep.FireTemple.DungeonRoom018.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `17bb18d0` | `DungeonRoomStep.FireTemple.DungeonRoom019.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `e14285fa` | `DungeonRoomStep.FireTemple.DungeonRoom019.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `672e97e0` | `DungeonRoomStep.FireTemple.DungeonRoom020.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `de45b022` | `DungeonRoomStep.FireTemple.DungeonRoom020.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `919074e3` | `DungeonRoomStep.FireTemple.DungeonRoom021.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `28157d12` | `DungeonRoomStep.FireTemple.DungeonRoom021.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `79037a54` | `DungeonRoomStep.FireTemple.DungeonRoom022.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `b54a0245` | `DungeonRoomStep.FireTemple.DungeonRoom022.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `c3a7a2f1` | `DungeonRoomStep.FireTemple.DungeonRoom023.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `491c3a97` | `DungeonRoomStep.FireTemple.DungeonRoom023.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `b55dfe7b` | `DungeonRoomStep.FireTemple.DungeonRoom024.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `4792bcbd` | `DungeonRoomStep.FireTemple.DungeonRoom024.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `04e5f8b2` | `DungeonRoomStep.FireTemple.DungeonRoom025.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `cf53bfcb` | `DungeonRoomStep.FireTemple.DungeonRoom025.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `64e72a2e` | `DungeonRoomStep.FireTemple.DungeonRoom026.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `fb0e8d65` | `DungeonRoomStep.FireTemple.DungeonRoom026.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `2ea35e6e` | `DungeonRoomStep.FireTemple.DungeonRoom027.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `2d3ada68` | `DungeonRoomStep.FireTemple.DungeonRoom027.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `8bb3d253` | `DungeonRoomStep.FireTemple.DungeonRoom028.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `5d99d91b` | `DungeonRoomStep.FireTemple.DungeonRoom028.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `5859bb27` | `DungeonRoomStep.FireTemple.DungeonRoom029.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `93ab842c` | `DungeonRoomStep.FireTemple.DungeonRoom029.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `2104e695` | `DungeonRoomStep.FireTemple.DungeonRoom030.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `1b822827` | `DungeonRoomStep.FireTemple.DungeonRoom030.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `6745fab7` | `DungeonRoomStep.FireTemple.DungeonRoom031.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `273648f7` | `DungeonRoomStep.FireTemple.DungeonRoom031.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `4823b3e7` | `DungeonRoomStep.FireTemple.DungeonRoom032.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `c8752212` | `DungeonRoomStep.FireTemple.DungeonRoom032.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `a1013d4a` | `DungeonRoomStep.FireTemple.DungeonRoom033.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | FireTemple |  |  | read |  |
| `7d4cf5ad` | `DungeonRoomStep.FireTemple.DungeonRoom033.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | FireTemple |  |  | read |  |
| `9d8eb1d9` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `a5854d61` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `a32ed0c4` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom001.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `31d666b3` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom001.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `aa85fad3` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom002.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `7bef4634` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom002.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `9b7d5609` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom003.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b9c93ad8` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom003.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `a02b5ba4` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom004.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `f5c5a2c2` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom004.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `e9099b87` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom005.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b0aa8554` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom005.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `b7513d27` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom006.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `53e3b81e` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom006.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `e5ba0c92` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom007.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `04d30dec` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom007.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `685abee0` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom008.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `ff4ce6c5` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom008.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `de72108b` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom009.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `af357130` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom009.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `7bc88f9b` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom010.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `d5a65ada` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom010.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `485ca34a` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom011.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `f840c971` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom011.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `699e5276` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom012.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `ef56faee` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom012.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `9aea414b` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom013.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `0cf040d0` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom013.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `38da8845` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom014.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `9fb3b1dd` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom014.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `3cede3c8` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom015.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `5606a1d1` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom015.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `32b51ec1` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom016.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `3520d78e` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom016.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `14a96a77` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom017.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `0dd4ff5d` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom017.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `c4bfa8eb` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom018.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `7b1490a0` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom018.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `69ea9117` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom019.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `6b007218` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom019.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `8a26904e` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom020.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `bb94ccc7` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom020.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `2211ecbb` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom021.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `9f61c788` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom021.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `4ad55fdb` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom022.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `5faa43ff` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom022.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `dfa3487b` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom023.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b41780af` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom023.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `74c09ba6` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom024.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `8626c553` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom024.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `a7404c03` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom025.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `cbbb8771` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom025.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `fa78174f` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom026.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `34ab4dc4` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom026.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `585b1b23` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom027.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `a7092d76` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom027.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `cfc7e8d0` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom028.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `038cac80` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom028.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `9baf0613` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom029.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `38a51670` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom029.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `ecb85c06` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom030.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `53afb5ca` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom030.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `760e1049` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom031.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `57d5c70d` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom031.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `37910bce` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom032.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `0d43e1c1` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom032.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `29faf3c9` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom033.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `011e360f` | `DungeonRoomStep.FireTemple_MQ.DungeonRoom033.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `e2f1c243` | `DungeonRoomStep.ForestTemple.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `e7c8c8bc` | `DungeonRoomStep.ForestTemple.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `9b13ae0a` | `DungeonRoomStep.ForestTemple.DungeonRoom001.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `f8a9d10c` | `DungeonRoomStep.ForestTemple.DungeonRoom001.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `4a1a8186` | `DungeonRoomStep.ForestTemple.DungeonRoom002.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `9acd7550` | `DungeonRoomStep.ForestTemple.DungeonRoom002.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `f8dbad38` | `DungeonRoomStep.ForestTemple.DungeonRoom003.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `ce8a32a3` | `DungeonRoomStep.ForestTemple.DungeonRoom003.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `0211652f` | `DungeonRoomStep.ForestTemple.DungeonRoom004.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `4474c86e` | `DungeonRoomStep.ForestTemple.DungeonRoom004.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `9976825a` | `DungeonRoomStep.ForestTemple.DungeonRoom005.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `14486049` | `DungeonRoomStep.ForestTemple.DungeonRoom005.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `99006bee` | `DungeonRoomStep.ForestTemple.DungeonRoom006.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `a474241e` | `DungeonRoomStep.ForestTemple.DungeonRoom006.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `f528aa8b` | `DungeonRoomStep.ForestTemple.DungeonRoom007.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `084dc50c` | `DungeonRoomStep.ForestTemple.DungeonRoom007.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `f3482c4a` | `DungeonRoomStep.ForestTemple.DungeonRoom008.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `967d94c0` | `DungeonRoomStep.ForestTemple.DungeonRoom008.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `e7556442` | `DungeonRoomStep.ForestTemple.DungeonRoom009.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `1429c9ca` | `DungeonRoomStep.ForestTemple.DungeonRoom009.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `08155b86` | `DungeonRoomStep.ForestTemple.DungeonRoom010.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `6713986c` | `DungeonRoomStep.ForestTemple.DungeonRoom010.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `503a0cab` | `DungeonRoomStep.ForestTemple.DungeonRoom011.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `0f46603f` | `DungeonRoomStep.ForestTemple.DungeonRoom011.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `987c3fc0` | `DungeonRoomStep.ForestTemple.DungeonRoom012.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `a0c88e7b` | `DungeonRoomStep.ForestTemple.DungeonRoom012.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `b38bd0f9` | `DungeonRoomStep.ForestTemple.DungeonRoom013.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `451158e7` | `DungeonRoomStep.ForestTemple.DungeonRoom013.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `eadb5bb2` | `DungeonRoomStep.ForestTemple.DungeonRoom014.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `8e3af296` | `DungeonRoomStep.ForestTemple.DungeonRoom014.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `6727db04` | `DungeonRoomStep.ForestTemple.DungeonRoom015.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `4c70fa88` | `DungeonRoomStep.ForestTemple.DungeonRoom015.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `d917a2b6` | `DungeonRoomStep.ForestTemple.DungeonRoom016.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `9eab8d59` | `DungeonRoomStep.ForestTemple.DungeonRoom016.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `6a7119a1` | `DungeonRoomStep.ForestTemple.DungeonRoom017.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `54a847e1` | `DungeonRoomStep.ForestTemple.DungeonRoom017.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `8703ecaa` | `DungeonRoomStep.ForestTemple.DungeonRoom018.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `8d0e12a7` | `DungeonRoomStep.ForestTemple.DungeonRoom018.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `dd6f1587` | `DungeonRoomStep.ForestTemple.DungeonRoom019.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `c057af9c` | `DungeonRoomStep.ForestTemple.DungeonRoom019.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `0230987e` | `DungeonRoomStep.ForestTemple.DungeonRoom020.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `d2bd2ad3` | `DungeonRoomStep.ForestTemple.DungeonRoom020.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `d9ba1bff` | `DungeonRoomStep.ForestTemple.DungeonRoom021.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `c8163dcb` | `DungeonRoomStep.ForestTemple.DungeonRoom021.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `a8a9dc6b` | `DungeonRoomStep.ForestTemple.DungeonRoom022.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `c5d45788` | `DungeonRoomStep.ForestTemple.DungeonRoom022.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `bf8f2cf9` | `DungeonRoomStep.ForestTemple.DungeonRoom023.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `f4fd2ca4` | `DungeonRoomStep.ForestTemple.DungeonRoom023.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `751b464f` | `DungeonRoomStep.ForestTemple.DungeonRoom024.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `2a8458a8` | `DungeonRoomStep.ForestTemple.DungeonRoom024.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `ed7cf7e1` | `DungeonRoomStep.ForestTemple.DungeonRoom025.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `77f36b57` | `DungeonRoomStep.ForestTemple.DungeonRoom025.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `fc4f84e2` | `DungeonRoomStep.ForestTemple.DungeonRoom026.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `eb5ef719` | `DungeonRoomStep.ForestTemple.DungeonRoom026.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `dd800615` | `DungeonRoomStep.ForestTemple.DungeonRoom027.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `5b486141` | `DungeonRoomStep.ForestTemple.DungeonRoom027.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `76ef4e44` | `DungeonRoomStep.ForestTemple.DungeonRoom028.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `210af4d9` | `DungeonRoomStep.ForestTemple.DungeonRoom028.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `7a5a3fe3` | `DungeonRoomStep.ForestTemple.DungeonRoom029.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `e28849d2` | `DungeonRoomStep.ForestTemple.DungeonRoom029.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `bc0aeeef` | `DungeonRoomStep.ForestTemple.DungeonRoom030.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ForestTemple |  |  | read |  |
| `b608b966` | `DungeonRoomStep.ForestTemple.DungeonRoom030.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ForestTemple |  |  | read |  |
| `d9d3bcf8` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `beab4e53` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `888be39d` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom001.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `5618227a` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom001.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `2e1a0797` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom002.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `fd920b53` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom002.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `517ff499` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom003.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `1c559dfe` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom003.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `2bcebe40` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom004.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `95bfda07` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom004.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `4b5ee4af` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom005.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `dab4b55f` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom005.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `53715ddd` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom006.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `46f7de45` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom006.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `125eb43d` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom007.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `d8349b02` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom007.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `58244901` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom008.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `fc0d58c6` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom008.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `27add423` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom009.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `82960b02` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom009.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `2c742843` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom010.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `1c0ce5b2` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom010.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `e0f402a1` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom011.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `c4bd4bae` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom011.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `30609644` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom012.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `f0f7e40f` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom012.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `eb5665b3` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom013.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `e87f88b3` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom013.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `82bf064b` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom014.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `46934a98` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom014.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `2b8a3c29` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom015.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `4e7bc6ae` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom015.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `f3aec7fd` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom016.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `80027cb3` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom016.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `c4a3459f` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom017.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `34fb60b3` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom017.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `140d3811` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom018.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `9b44b791` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom018.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `5ee3623f` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom019.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `072db4c0` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom019.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `d5e0cad0` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom020.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `40142338` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom020.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `f026c964` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom021.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `38d68fab` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom021.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `f9a8e335` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom022.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `f2bc1ee5` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom022.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `43bba5b2` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom023.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `ca2c8633` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom023.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `8c74f1a2` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom024.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `27c3de20` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom024.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `b50bdd50` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom025.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `e53de78f` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom025.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `66b3b714` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom026.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `fb47f867` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom026.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `da281fd1` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom027.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `bbbd8b11` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom027.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `3d2fda5a` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom028.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `a10d31b8` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom028.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `02276835` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom029.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `5f8291a5` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom029.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `999273ae` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom030.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `e5abc884` | `DungeonRoomStep.ForestTemple_MQ.DungeonRoom030.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `a50fbc4e` | `DungeonRoomStep.GerudoFortress_Adult.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | GerudoFortress |  |  | read |  |
| `cab71395` | `DungeonRoomStep.GerudoFortress_Adult.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | GerudoFortress |  |  | read |  |
| `b97d563a` | `DungeonRoomStep.GerudoTrainingGround.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | GerudoTrainingGround |  |  | read |  |
| `89542aff` | `DungeonRoomStep.GerudoTrainingGround.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | GerudoTrainingGround |  |  | read |  |
| `4b5f28ee` | `DungeonRoomStep.GerudoTrainingGround.DungeonRoom001.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | GerudoTrainingGround |  |  | read |  |
| `5ea321d9` | `DungeonRoomStep.GerudoTrainingGround.DungeonRoom001.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | GerudoTrainingGround |  |  | read |  |
| `49936a0b` | `DungeonRoomStep.GerudoTrainingGround.DungeonRoom002.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | GerudoTrainingGround |  |  | read |  |
| `8f863d97` | `DungeonRoomStep.GerudoTrainingGround.DungeonRoom002.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | GerudoTrainingGround |  |  | read |  |
| `fb226c6f` | `DungeonRoomStep.GerudoTrainingGround.DungeonRoom003.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | GerudoTrainingGround |  |  | read |  |
| `626c1835` | `DungeonRoomStep.GerudoTrainingGround.DungeonRoom003.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | GerudoTrainingGround |  |  | read |  |
| `76815a0f` | `DungeonRoomStep.GerudoTrainingGround.DungeonRoom004.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | GerudoTrainingGround |  |  | read |  |
| `2b0a5979` | `DungeonRoomStep.GerudoTrainingGround.DungeonRoom004.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | GerudoTrainingGround |  |  | read |  |
| `78f6dbdb` | `DungeonRoomStep.GerudoTrainingGround.DungeonRoom005.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | GerudoTrainingGround |  |  | read |  |
| `0f0137ba` | `DungeonRoomStep.GerudoTrainingGround.DungeonRoom005.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | GerudoTrainingGround |  |  | read |  |
| `88d8f768` | `DungeonRoomStep.GerudoTrainingGround.DungeonRoom006.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | GerudoTrainingGround |  |  | read |  |
| `94d9ee1e` | `DungeonRoomStep.GerudoTrainingGround.DungeonRoom006.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | GerudoTrainingGround |  |  | read |  |
| `a3a004c7` | `DungeonRoomStep.GerudoTrainingGround.DungeonRoom007.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | GerudoTrainingGround |  |  | read |  |
| `07073e9a` | `DungeonRoomStep.GerudoTrainingGround.DungeonRoom007.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | GerudoTrainingGround |  |  | read |  |
| `7cf7bb2a` | `DungeonRoomStep.GerudoTrainingGround.DungeonRoom008.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | GerudoTrainingGround |  |  | read |  |
| `25f4859f` | `DungeonRoomStep.GerudoTrainingGround.DungeonRoom008.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | GerudoTrainingGround |  |  | read |  |
| `85a46e60` | `DungeonRoomStep.GerudoTrainingGround.DungeonRoom009.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | GerudoTrainingGround |  |  | read |  |
| `95d8ab84` | `DungeonRoomStep.GerudoTrainingGround.DungeonRoom009.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | GerudoTrainingGround |  |  | read |  |
| `732c04c5` | `DungeonRoomStep.GerudoTrainingGround.DungeonRoom010.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | GerudoTrainingGround |  |  | read |  |
| `cd063bd2` | `DungeonRoomStep.GerudoTrainingGround.DungeonRoom010.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | GerudoTrainingGround |  |  | read |  |
| `703c1390` | `DungeonRoomStep.GerudoTrainingGround_MQ.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `a667b65a` | `DungeonRoomStep.GerudoTrainingGround_MQ.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `abce1fb0` | `DungeonRoomStep.GerudoTrainingGround_MQ.DungeonRoom001.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `13945b37` | `DungeonRoomStep.GerudoTrainingGround_MQ.DungeonRoom001.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `8ebcce84` | `DungeonRoomStep.GerudoTrainingGround_MQ.DungeonRoom002.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `d8426eea` | `DungeonRoomStep.GerudoTrainingGround_MQ.DungeonRoom002.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `ab2f5d80` | `DungeonRoomStep.GerudoTrainingGround_MQ.DungeonRoom003.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `8c3c2df6` | `DungeonRoomStep.GerudoTrainingGround_MQ.DungeonRoom003.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `5f074a98` | `DungeonRoomStep.GerudoTrainingGround_MQ.DungeonRoom004.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `459038e5` | `DungeonRoomStep.GerudoTrainingGround_MQ.DungeonRoom004.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `77a7d6d8` | `DungeonRoomStep.GerudoTrainingGround_MQ.DungeonRoom005.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b9e0767a` | `DungeonRoomStep.GerudoTrainingGround_MQ.DungeonRoom005.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `af2d612e` | `DungeonRoomStep.GerudoTrainingGround_MQ.DungeonRoom006.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `4c56fc44` | `DungeonRoomStep.GerudoTrainingGround_MQ.DungeonRoom006.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `7a5913f9` | `DungeonRoomStep.GerudoTrainingGround_MQ.DungeonRoom007.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `fde9be64` | `DungeonRoomStep.GerudoTrainingGround_MQ.DungeonRoom007.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `833e9356` | `DungeonRoomStep.GerudoTrainingGround_MQ.DungeonRoom008.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `3639700a` | `DungeonRoomStep.GerudoTrainingGround_MQ.DungeonRoom008.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `52148232` | `DungeonRoomStep.GerudoTrainingGround_MQ.DungeonRoom009.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `fd18ad75` | `DungeonRoomStep.GerudoTrainingGround_MQ.DungeonRoom009.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `9c1704bb` | `DungeonRoomStep.GerudoTrainingGround_MQ.DungeonRoom010.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `13558572` | `DungeonRoomStep.GerudoTrainingGround_MQ.DungeonRoom010.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `0a9c715e` | `DungeonRoomStep.HountedWasteland_Adult.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | HountedWasteland |  |  | read |  |
| `c01e5f13` | `DungeonRoomStep.HountedWasteland_Adult.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | HountedWasteland |  |  | read |  |
| `b97ad4b1` | `DungeonRoomStep.HountedWasteland_Child.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | HountedWasteland |  |  | read |  |
| `c4911f30` | `DungeonRoomStep.HountedWasteland_Child.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | HountedWasteland |  |  | read |  |
| `20f471da` | `DungeonRoomStep.IceCavern.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | IceCavern |  |  | read |  |
| `aa7df4f6` | `DungeonRoomStep.IceCavern.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | IceCavern |  |  | read |  |
| `4dcd45a6` | `DungeonRoomStep.IceCavern.DungeonRoom001.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | IceCavern |  |  | read |  |
| `09f38b12` | `DungeonRoomStep.IceCavern.DungeonRoom001.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | IceCavern |  |  | read |  |
| `51040b35` | `DungeonRoomStep.IceCavern.DungeonRoom002.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | IceCavern |  |  | read |  |
| `53e6da81` | `DungeonRoomStep.IceCavern.DungeonRoom002.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | IceCavern |  |  | read |  |
| `d7aec551` | `DungeonRoomStep.IceCavern.DungeonRoom003.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | IceCavern |  |  | read |  |
| `c196d42a` | `DungeonRoomStep.IceCavern.DungeonRoom003.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | IceCavern |  |  | read |  |
| `2d0aa1d8` | `DungeonRoomStep.IceCavern.DungeonRoom004.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | IceCavern |  |  | read |  |
| `b2ef3175` | `DungeonRoomStep.IceCavern.DungeonRoom004.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | IceCavern |  |  | read |  |
| `45aa9e9b` | `DungeonRoomStep.IceCavern.DungeonRoom005.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | IceCavern |  |  | read |  |
| `00a18856` | `DungeonRoomStep.IceCavern.DungeonRoom005.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | IceCavern |  |  | read |  |
| `6e1bab7b` | `DungeonRoomStep.IceCavern.DungeonRoom006.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | IceCavern |  |  | read |  |
| `3f323c82` | `DungeonRoomStep.IceCavern.DungeonRoom006.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | IceCavern |  |  | read |  |
| `b93686ed` | `DungeonRoomStep.IceCavern.DungeonRoom007.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | IceCavern |  |  | read |  |
| `672b5c2e` | `DungeonRoomStep.IceCavern.DungeonRoom007.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | IceCavern |  |  | read |  |
| `3e6c5c4c` | `DungeonRoomStep.IceCavern.DungeonRoom008.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | IceCavern |  |  | read |  |
| `08876a79` | `DungeonRoomStep.IceCavern.DungeonRoom008.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | IceCavern |  |  | read |  |
| `3823865e` | `DungeonRoomStep.IceCavern.DungeonRoom009.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | IceCavern |  |  | read |  |
| `4386c12f` | `DungeonRoomStep.IceCavern.DungeonRoom009.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | IceCavern |  |  | read |  |
| `700459ba` | `DungeonRoomStep.IceCavern.DungeonRoom010.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | IceCavern |  |  | read |  |
| `747da740` | `DungeonRoomStep.IceCavern.DungeonRoom010.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | IceCavern |  |  | read |  |
| `387bd50e` | `DungeonRoomStep.IceCavern.DungeonRoom011.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | IceCavern |  |  | read |  |
| `d94a20d3` | `DungeonRoomStep.IceCavern.DungeonRoom011.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | IceCavern |  |  | read |  |
| `fbf9d64e` | `DungeonRoomStep.IceCavern_MQ.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `74005d90` | `DungeonRoomStep.IceCavern_MQ.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `2ff9f77c` | `DungeonRoomStep.IceCavern_MQ.DungeonRoom001.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `dba34e99` | `DungeonRoomStep.IceCavern_MQ.DungeonRoom001.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `1b815e8d` | `DungeonRoomStep.IceCavern_MQ.DungeonRoom002.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `75c7845a` | `DungeonRoomStep.IceCavern_MQ.DungeonRoom002.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `24d11591` | `DungeonRoomStep.IceCavern_MQ.DungeonRoom003.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `54add6ac` | `DungeonRoomStep.IceCavern_MQ.DungeonRoom003.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `d5698322` | `DungeonRoomStep.IceCavern_MQ.DungeonRoom004.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `9d5142ec` | `DungeonRoomStep.IceCavern_MQ.DungeonRoom004.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `e624b84f` | `DungeonRoomStep.IceCavern_MQ.DungeonRoom005.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `252621c0` | `DungeonRoomStep.IceCavern_MQ.DungeonRoom005.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `0cbd4832` | `DungeonRoomStep.IceCavern_MQ.DungeonRoom006.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `d85addfb` | `DungeonRoomStep.IceCavern_MQ.DungeonRoom006.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `57b9abe3` | `DungeonRoomStep.IceCavern_MQ.DungeonRoom007.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `dea4102f` | `DungeonRoomStep.IceCavern_MQ.DungeonRoom007.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `73438a46` | `DungeonRoomStep.IceCavern_MQ.DungeonRoom008.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `7b2fcf1d` | `DungeonRoomStep.IceCavern_MQ.DungeonRoom008.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `f8d035a6` | `DungeonRoomStep.IceCavern_MQ.DungeonRoom009.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `88c74d7f` | `DungeonRoomStep.IceCavern_MQ.DungeonRoom009.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `300cc3a9` | `DungeonRoomStep.IceCavern_MQ.DungeonRoom010.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b4b0e92b` | `DungeonRoomStep.IceCavern_MQ.DungeonRoom010.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `28b7f40b` | `DungeonRoomStep.IceCavern_MQ.DungeonRoom011.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `203c5aea` | `DungeonRoomStep.IceCavern_MQ.DungeonRoom011.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `0b92ea02` | `DungeonRoomStep.IceCavern_MQ.DungeonRoom012.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `37f0f7ff` | `DungeonRoomStep.IceCavern_MQ.DungeonRoom012.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `223decd0` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  |  | read |  |
| `30e1177d` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideGanonCastle |  |  | read |  |
| `f922d5ee` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom001.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  |  | read |  |
| `5dab70d4` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom001.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideGanonCastle |  |  | read |  |
| `9b2d4c96` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom002.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  |  | read |  |
| `2c713462` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom002.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideGanonCastle |  |  | read |  |
| `94aa04ad` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom003.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  |  | read |  |
| `1971f10f` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom003.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideGanonCastle |  |  | read |  |
| `9f2d126f` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom004.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  |  | read |  |
| `72d5869f` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom004.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideGanonCastle |  |  | read |  |
| `b95727b0` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom005.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  |  | read |  |
| `f874deeb` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom005.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideGanonCastle |  |  | read |  |
| `b9f66a33` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom006.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  |  | read |  |
| `bcd60ef9` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom006.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideGanonCastle |  |  | read |  |
| `841d062b` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom007.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  |  | read |  |
| `04560f67` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom007.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideGanonCastle |  |  | read |  |
| `72c5e803` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom008.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  |  | read |  |
| `147b4324` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom008.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideGanonCastle |  |  | read |  |
| `32c0eb6b` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom009.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  |  | read |  |
| `1eba330b` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom009.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideGanonCastle |  |  | read |  |
| `31c9417a` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom010.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  |  | read |  |
| `2111edaf` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom010.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideGanonCastle |  |  | read |  |
| `6d059c1d` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom011.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  |  | read |  |
| `6076053a` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom011.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideGanonCastle |  |  | read |  |
| `66b7b8f1` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom012.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  |  | read |  |
| `2dffcafc` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom012.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideGanonCastle |  |  | read |  |
| `1445abf8` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom013.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  |  | read |  |
| `9218d93f` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom013.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideGanonCastle |  |  | read |  |
| `13b8229b` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom014.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  |  | read |  |
| `e3c031b8` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom014.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideGanonCastle |  |  | read |  |
| `7b933340` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom015.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  |  | read |  |
| `ba5d7a4e` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom015.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideGanonCastle |  |  | read |  |
| `05b226d4` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom016.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  |  | read |  |
| `4c5b7875` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom016.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideGanonCastle |  |  | read |  |
| `85bfa555` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom017.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  |  | read |  |
| `c25083a6` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom017.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideGanonCastle |  |  | read |  |
| `1fb29dd4` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom018.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  |  | read |  |
| `3d284db1` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom018.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideGanonCastle |  |  | read |  |
| `0a85a2fd` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom019.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  |  | read |  |
| `12267bd1` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom019.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideGanonCastle |  |  | read |  |
| `1eda3944` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom020.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  |  | read |  |
| `84b12d71` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom020.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideGanonCastle |  |  | read |  |
| `163a0365` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom021.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  |  | read |  |
| `154211ac` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom021.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideGanonCastle |  |  | read |  |
| `d0858061` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom022.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  |  | read |  |
| `85a93149` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom022.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideGanonCastle |  |  | read |  |
| `f00c9c5d` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom023.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  |  | read |  |
| `d4c69670` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom023.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideGanonCastle |  |  | read |  |
| `91035b99` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom024.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  |  | read |  |
| `15ccb0e8` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom024.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideGanonCastle |  |  | read |  |
| `40574d87` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom025.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  |  | read |  |
| `6e7ec293` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom025.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideGanonCastle |  |  | read |  |
| `87c87c63` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom026.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideGanonCastle |  |  | read |  |
| `0039771e` | `DungeonRoomStep.InsideGanonCastle.DungeonRoom026.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideGanonCastle |  |  | read |  |
| `1894b0ad` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `48405c56` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `a95212f6` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom001.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `7528e44c` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom001.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `26d1e136` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom002.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `4d9806d8` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom002.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `0f28b0f8` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom003.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `565f43fd` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom003.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `14a77005` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom004.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b543d0f2` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom004.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `3027ca96` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom005.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `02d309f6` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom005.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `0da0d270` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom006.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `93a87bda` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom006.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `dc75744e` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom007.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `49cf4e40` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom007.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `1d1ff201` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom008.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `8020df49` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom008.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `707661b8` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom009.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `349d8bea` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom009.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `8c99e8c3` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom010.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `fefe8fab` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom010.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `c07bcb12` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom011.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `dfc57451` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom011.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `df59861a` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom012.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `f4df29d6` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom012.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `1dafcfba` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom013.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `1854e48e` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom013.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `434effd7` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom014.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `49f9ca40` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom014.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `8212b306` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom015.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `8485bf6e` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom015.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `82717d29` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom016.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `cbede572` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom016.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `4969a543` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom017.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `e55b49d4` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom017.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `f430f54e` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom018.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `15fc9103` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom018.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `94d414be` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom019.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `217c2fcf` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom019.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `d2d52c96` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom020.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `72cb8450` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom020.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `fedfae78` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom021.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `8b1e2b1d` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom021.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `3ee63293` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom022.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `259b906f` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom022.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `128db3c0` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom023.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `85bb1cf7` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom023.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `857747de` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom024.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `1833bb77` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom024.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `e874292c` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom025.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `8b1b0a89` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom025.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `8cad5dde` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom026.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `d8b0faca` | `DungeonRoomStep.InsideGanonCastle_MQ.DungeonRoom026.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `d289e9e6` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideJabuJabuBelly |  |  | read |  |
| `d41d783b` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideJabuJabuBelly |  |  | read |  |
| `4fa3a3da` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom001.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideJabuJabuBelly |  |  | read |  |
| `1cbf1159` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom001.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideJabuJabuBelly |  |  | read |  |
| `f7042037` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom002.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideJabuJabuBelly |  |  | read |  |
| `09d94fd5` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom002.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideJabuJabuBelly |  |  | read |  |
| `65e25f22` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom003.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideJabuJabuBelly |  |  | read |  |
| `08f6cfc0` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom003.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideJabuJabuBelly |  |  | read |  |
| `592ccd8b` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom004.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideJabuJabuBelly |  |  | read |  |
| `bcbac6c1` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom004.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideJabuJabuBelly |  |  | read |  |
| `f1e03cf2` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom005.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideJabuJabuBelly |  |  | read |  |
| `1cdcff9e` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom005.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideJabuJabuBelly |  |  | read |  |
| `a272cba7` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom006.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideJabuJabuBelly |  |  | read |  |
| `663cd775` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom006.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideJabuJabuBelly |  |  | read |  |
| `d3b2ccf1` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom007.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideJabuJabuBelly |  |  | read |  |
| `62873246` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom007.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideJabuJabuBelly |  |  | read |  |
| `46236491` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom008.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideJabuJabuBelly |  |  | read |  |
| `6a56c5c3` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom008.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideJabuJabuBelly |  |  | read |  |
| `1c8fc21d` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom009.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideJabuJabuBelly |  |  | read |  |
| `7e9b5b75` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom009.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideJabuJabuBelly |  |  | read |  |
| `74d439c9` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom010.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideJabuJabuBelly |  |  | read |  |
| `2586a0b3` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom010.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideJabuJabuBelly |  |  | read |  |
| `c1b1a52c` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom011.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideJabuJabuBelly |  |  | read |  |
| `08d15d8c` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom011.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideJabuJabuBelly |  |  | read |  |
| `c744e771` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom012.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideJabuJabuBelly |  |  | read |  |
| `3fe1e9b9` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom012.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideJabuJabuBelly |  |  | read |  |
| `e90c2d7b` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom013.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideJabuJabuBelly |  |  | read |  |
| `31364a0f` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom013.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideJabuJabuBelly |  |  | read |  |
| `5c78e182` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom014.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideJabuJabuBelly |  |  | read |  |
| `88899aca` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom014.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideJabuJabuBelly |  |  | read |  |
| `d1df3639` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom015.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideJabuJabuBelly |  |  | read |  |
| `5d2b12c1` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom015.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideJabuJabuBelly |  |  | read |  |
| `bbf9349a` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom016.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideJabuJabuBelly |  |  | read |  |
| `4b0134e1` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom016.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideJabuJabuBelly |  |  | read |  |
| `a32a3742` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom017.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideJabuJabuBelly |  |  | read |  |
| `c2716c14` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom017.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideJabuJabuBelly |  |  | read |  |
| `2f813787` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom018.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideJabuJabuBelly |  |  | read |  |
| `2380b1e4` | `DungeonRoomStep.InsideJabuJabuBelly.DungeonRoom018.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideJabuJabuBelly |  |  | read |  |
| `4b69b7f6` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `98d79602` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `b0ee0f9e` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom001.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `de9bc0f7` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom001.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `abebdaa9` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom002.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `f44e2f02` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom002.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `6624c370` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom003.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `0d3d8eac` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom003.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `3b47876f` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom004.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `e31fa3f7` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom004.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `f5e59fac` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom005.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `37a288de` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom005.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `88092cf6` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom006.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `0db7ec85` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom006.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `e03a2794` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom007.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `4903eb25` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom007.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `1a49c2c1` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom008.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `3873aeec` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom008.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `61a147a3` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom009.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `92a72b2b` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom009.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `aeae57c2` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom010.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `6cbf49ed` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom010.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `ef1db69c` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom011.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `5a924f39` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom011.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `203e3fd9` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom012.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `226a0632` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom012.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `62367823` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom013.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `755ab6ae` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom013.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `833f2b7b` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom014.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `5af2e9c4` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom014.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `2a926441` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom015.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `f2aa3491` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom015.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `af115626` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom016.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `79997318` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom016.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `2469cbbc` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom017.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b68064b4` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom017.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `46b9672d` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom018.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `476e54d9` | `DungeonRoomStep.InsideJabuJabuBelly_MQ.DungeonRoom018.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `389cbbc6` | `DungeonRoomStep.InsideTheDekuTree.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `0dd584e5` | `DungeonRoomStep.InsideTheDekuTree.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideTheDekuTree |  |  | read |  |
| `76783779` | `DungeonRoomStep.InsideTheDekuTree.DungeonRoom001.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `b4621236` | `DungeonRoomStep.InsideTheDekuTree.DungeonRoom001.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideTheDekuTree |  |  | read |  |
| `a12eeeaa` | `DungeonRoomStep.InsideTheDekuTree.DungeonRoom002.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `a9181179` | `DungeonRoomStep.InsideTheDekuTree.DungeonRoom002.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideTheDekuTree |  |  | read |  |
| `26dc9499` | `DungeonRoomStep.InsideTheDekuTree.DungeonRoom003.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `22dcb5f6` | `DungeonRoomStep.InsideTheDekuTree.DungeonRoom003.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideTheDekuTree |  |  | read |  |
| `386dec15` | `DungeonRoomStep.InsideTheDekuTree.DungeonRoom004.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `3b81cbd2` | `DungeonRoomStep.InsideTheDekuTree.DungeonRoom004.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideTheDekuTree |  |  | read |  |
| `ba1b0e7e` | `DungeonRoomStep.InsideTheDekuTree.DungeonRoom005.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `8c2876e6` | `DungeonRoomStep.InsideTheDekuTree.DungeonRoom005.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideTheDekuTree |  |  | read |  |
| `8b1a2ab4` | `DungeonRoomStep.InsideTheDekuTree.DungeonRoom006.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `aa36dc86` | `DungeonRoomStep.InsideTheDekuTree.DungeonRoom006.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideTheDekuTree |  |  | read |  |
| `80a8ee0e` | `DungeonRoomStep.InsideTheDekuTree.DungeonRoom007.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `3f19e1e4` | `DungeonRoomStep.InsideTheDekuTree.DungeonRoom007.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideTheDekuTree |  |  | read |  |
| `3f2ec191` | `DungeonRoomStep.InsideTheDekuTree.DungeonRoom008.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `8a0417a6` | `DungeonRoomStep.InsideTheDekuTree.DungeonRoom008.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideTheDekuTree |  |  | read |  |
| `241938de` | `DungeonRoomStep.InsideTheDekuTree.DungeonRoom009.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `12b71815` | `DungeonRoomStep.InsideTheDekuTree.DungeonRoom009.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideTheDekuTree |  |  | read |  |
| `da7f1dbd` | `DungeonRoomStep.InsideTheDekuTree.DungeonRoom010.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `d7c78a74` | `DungeonRoomStep.InsideTheDekuTree.DungeonRoom010.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideTheDekuTree |  |  | read |  |
| `3773f5cc` | `DungeonRoomStep.InsideTheDekuTree.DungeonRoom011.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `cf12d696` | `DungeonRoomStep.InsideTheDekuTree.DungeonRoom011.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideTheDekuTree |  |  | read |  |
| `e9d86523` | `DungeonRoomStep.InsideTheDekuTree.DungeonRoom012.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `2a1f3cfa` | `DungeonRoomStep.InsideTheDekuTree.DungeonRoom012.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | InsideTheDekuTree |  |  | read |  |
| `f0e259a9` | `DungeonRoomStep.InsideTheDekuTree_MQ.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `7315a8bb` | `DungeonRoomStep.InsideTheDekuTree_MQ.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `9bd02c0b` | `DungeonRoomStep.InsideTheDekuTree_MQ.DungeonRoom001.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `9b8960ed` | `DungeonRoomStep.InsideTheDekuTree_MQ.DungeonRoom001.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `72c548c7` | `DungeonRoomStep.InsideTheDekuTree_MQ.DungeonRoom002.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `316cb941` | `DungeonRoomStep.InsideTheDekuTree_MQ.DungeonRoom002.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `bd12786f` | `DungeonRoomStep.InsideTheDekuTree_MQ.DungeonRoom003.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `6b01fc6f` | `DungeonRoomStep.InsideTheDekuTree_MQ.DungeonRoom003.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `a5c3e8ff` | `DungeonRoomStep.InsideTheDekuTree_MQ.DungeonRoom004.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `8ee6a6cf` | `DungeonRoomStep.InsideTheDekuTree_MQ.DungeonRoom004.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `e64d47fe` | `DungeonRoomStep.InsideTheDekuTree_MQ.DungeonRoom005.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `435122bd` | `DungeonRoomStep.InsideTheDekuTree_MQ.DungeonRoom005.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `1389fcfe` | `DungeonRoomStep.InsideTheDekuTree_MQ.DungeonRoom006.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `056d9ac6` | `DungeonRoomStep.InsideTheDekuTree_MQ.DungeonRoom006.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `eaea33cf` | `DungeonRoomStep.InsideTheDekuTree_MQ.DungeonRoom007.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `8e42e38e` | `DungeonRoomStep.InsideTheDekuTree_MQ.DungeonRoom007.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `81a28cd4` | `DungeonRoomStep.InsideTheDekuTree_MQ.DungeonRoom008.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `9f04c8cf` | `DungeonRoomStep.InsideTheDekuTree_MQ.DungeonRoom008.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `90194e6b` | `DungeonRoomStep.InsideTheDekuTree_MQ.DungeonRoom009.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `fbd72164` | `DungeonRoomStep.InsideTheDekuTree_MQ.DungeonRoom009.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `83b147e7` | `DungeonRoomStep.InsideTheDekuTree_MQ.DungeonRoom010.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `58d38128` | `DungeonRoomStep.InsideTheDekuTree_MQ.DungeonRoom010.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `fc3f964b` | `DungeonRoomStep.InsideTheDekuTree_MQ.DungeonRoom011.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b21ffafd` | `DungeonRoomStep.InsideTheDekuTree_MQ.DungeonRoom011.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `6f3bd93b` | `DungeonRoomStep.InsideTheDekuTree_MQ.DungeonRoom012.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `fac773ca` | `DungeonRoomStep.InsideTheDekuTree_MQ.DungeonRoom012.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `15f50da3` | `DungeonRoomStep.KokiriForest_Adult.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `e42e1dbf` | `DungeonRoomStep.KokiriForest_Adult.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | KokiriForest |  |  | read |  |
| `562397ad` | `DungeonRoomStep.KokiriForest_Child.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `475056f2` | `DungeonRoomStep.KokiriForest_Child.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | KokiriForest |  |  | read |  |
| `382999fb` | `DungeonRoomStep.ShadowTemple.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `2dee3fc4` | `DungeonRoomStep.ShadowTemple.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `6af330cc` | `DungeonRoomStep.ShadowTemple.DungeonRoom001.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `d1d1280a` | `DungeonRoomStep.ShadowTemple.DungeonRoom001.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `c9829991` | `DungeonRoomStep.ShadowTemple.DungeonRoom002.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `faf76baf` | `DungeonRoomStep.ShadowTemple.DungeonRoom002.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `8bafc710` | `DungeonRoomStep.ShadowTemple.DungeonRoom003.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `81c654a7` | `DungeonRoomStep.ShadowTemple.DungeonRoom003.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `722dacaa` | `DungeonRoomStep.ShadowTemple.DungeonRoom004.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `5bb4a242` | `DungeonRoomStep.ShadowTemple.DungeonRoom004.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `2e032b5c` | `DungeonRoomStep.ShadowTemple.DungeonRoom005.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `170b0257` | `DungeonRoomStep.ShadowTemple.DungeonRoom005.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `9cf0ee81` | `DungeonRoomStep.ShadowTemple.DungeonRoom006.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `b1f987fd` | `DungeonRoomStep.ShadowTemple.DungeonRoom006.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `de0e8065` | `DungeonRoomStep.ShadowTemple.DungeonRoom007.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `ca631176` | `DungeonRoomStep.ShadowTemple.DungeonRoom007.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `5fbab824` | `DungeonRoomStep.ShadowTemple.DungeonRoom008.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `d43b8972` | `DungeonRoomStep.ShadowTemple.DungeonRoom008.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `34d50b40` | `DungeonRoomStep.ShadowTemple.DungeonRoom009.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `cd57f1f4` | `DungeonRoomStep.ShadowTemple.DungeonRoom009.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `d0009fb0` | `DungeonRoomStep.ShadowTemple.DungeonRoom010.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `192cd777` | `DungeonRoomStep.ShadowTemple.DungeonRoom010.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `fdbcd247` | `DungeonRoomStep.ShadowTemple.DungeonRoom011.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `85edde37` | `DungeonRoomStep.ShadowTemple.DungeonRoom011.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `29c117db` | `DungeonRoomStep.ShadowTemple.DungeonRoom012.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `5ba31784` | `DungeonRoomStep.ShadowTemple.DungeonRoom012.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `1ef2f750` | `DungeonRoomStep.ShadowTemple.DungeonRoom013.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `99aadf20` | `DungeonRoomStep.ShadowTemple.DungeonRoom013.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `4a82ba65` | `DungeonRoomStep.ShadowTemple.DungeonRoom014.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `231f354a` | `DungeonRoomStep.ShadowTemple.DungeonRoom014.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `225d3225` | `DungeonRoomStep.ShadowTemple.DungeonRoom015.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `88591c22` | `DungeonRoomStep.ShadowTemple.DungeonRoom015.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `19d39e4f` | `DungeonRoomStep.ShadowTemple.DungeonRoom016.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `5e583ed1` | `DungeonRoomStep.ShadowTemple.DungeonRoom016.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `0abc0a7c` | `DungeonRoomStep.ShadowTemple.DungeonRoom017.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `0b88f09e` | `DungeonRoomStep.ShadowTemple.DungeonRoom017.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `06ecb6f7` | `DungeonRoomStep.ShadowTemple.DungeonRoom018.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `9632906c` | `DungeonRoomStep.ShadowTemple.DungeonRoom018.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `af0a4c40` | `DungeonRoomStep.ShadowTemple.DungeonRoom019.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `b0e29836` | `DungeonRoomStep.ShadowTemple.DungeonRoom019.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `a3fea0da` | `DungeonRoomStep.ShadowTemple.DungeonRoom020.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `f97d5aa8` | `DungeonRoomStep.ShadowTemple.DungeonRoom020.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `79e6ad73` | `DungeonRoomStep.ShadowTemple.DungeonRoom021.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `591fa9a1` | `DungeonRoomStep.ShadowTemple.DungeonRoom021.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `14179a8c` | `DungeonRoomStep.ShadowTemple.DungeonRoom022.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `cd36acd0` | `DungeonRoomStep.ShadowTemple.DungeonRoom022.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `0fc68fbc` | `DungeonRoomStep.ShadowTemple.DungeonRoom023.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `87ba7822` | `DungeonRoomStep.ShadowTemple.DungeonRoom023.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `65685522` | `DungeonRoomStep.ShadowTemple.DungeonRoom024.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `9bc62dd3` | `DungeonRoomStep.ShadowTemple.DungeonRoom024.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `b202b22a` | `DungeonRoomStep.ShadowTemple.DungeonRoom025.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `bb1ece56` | `DungeonRoomStep.ShadowTemple.DungeonRoom025.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `0ea4c47d` | `DungeonRoomStep.ShadowTemple.DungeonRoom026.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `73affd8c` | `DungeonRoomStep.ShadowTemple.DungeonRoom026.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `ef3e205d` | `DungeonRoomStep.ShadowTemple.DungeonRoom027.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `922f2021` | `DungeonRoomStep.ShadowTemple.DungeonRoom027.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `87cde6fd` | `DungeonRoomStep.ShadowTemple.DungeonRoom028.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `63354357` | `DungeonRoomStep.ShadowTemple.DungeonRoom028.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `d96298d5` | `DungeonRoomStep.ShadowTemple.DungeonRoom029.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `f86b6742` | `DungeonRoomStep.ShadowTemple.DungeonRoom029.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `7216ea25` | `DungeonRoomStep.ShadowTemple.DungeonRoom030.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `5f625f53` | `DungeonRoomStep.ShadowTemple.DungeonRoom030.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `8d86d52f` | `DungeonRoomStep.ShadowTemple.DungeonRoom031.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | ShadowTemple |  |  | read |  |
| `f4abbd78` | `DungeonRoomStep.ShadowTemple.DungeonRoom031.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | ShadowTemple |  |  | read |  |
| `335ea612` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `830080ff` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `baaacfad` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom001.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `54f83ab2` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom001.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `14015fd6` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom002.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b6402e55` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom002.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `81164874` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom003.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `72143bbc` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom003.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `9691ef83` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom004.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `f18b1bd8` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom004.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `a8e0ab56` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom005.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `8fa36a4f` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom005.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `9ca6ea2c` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom006.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `897ceee7` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom006.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `9166af8e` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom007.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `7d0f31e6` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom007.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `68009916` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom008.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `48fa0620` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom008.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `4b35d94e` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom009.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `0f7c8e4e` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom009.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `a3069888` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom010.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `e6e537e6` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom010.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `14631ac9` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom011.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `d1199d93` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom011.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `173fbbb8` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom012.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `4ddd3f54` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom012.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `69e1aab2` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom013.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `df26a539` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom013.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `1817fbb3` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom014.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `57910ac1` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom014.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `3512bccd` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom015.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b6e82186` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom015.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `e0e72aa6` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom016.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `67f515ac` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom016.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `5b1f6f78` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom017.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `56756925` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom017.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `d0cdb0d2` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom018.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `e625e466` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom018.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `e4e233c2` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom019.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `6b05d1d6` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom019.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `5e7fea15` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom020.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `e587cf29` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom020.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `f642239f` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom021.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `17d1cf92` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom021.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `8384c560` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom022.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `d7486bb6` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom022.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `4c37bd3a` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom023.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `71038512` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom023.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `f5118f0b` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom024.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `0f02eb41` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom024.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `a5024a4f` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom025.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b1090bd5` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom025.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `22c3250e` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom026.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `0f7d8e25` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom026.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `ce248fba` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom027.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `719059d3` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom027.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `8a34f7c9` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom028.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `a25911f3` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom028.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `9ff5d7f7` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom029.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `3e89e429` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom029.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `c66352f8` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom030.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `d7e50815` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom030.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `d6e27275` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom031.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b7f8d53a` | `DungeonRoomStep.ShadowTemple_MQ.DungeonRoom031.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `d5a37434` | `DungeonRoomStep.SpiritTemple.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `a53075db` | `DungeonRoomStep.SpiritTemple.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `f85e2705` | `DungeonRoomStep.SpiritTemple.DungeonRoom001.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `a92c7c09` | `DungeonRoomStep.SpiritTemple.DungeonRoom001.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `780c7526` | `DungeonRoomStep.SpiritTemple.DungeonRoom002.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `25536cff` | `DungeonRoomStep.SpiritTemple.DungeonRoom002.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `efd05779` | `DungeonRoomStep.SpiritTemple.DungeonRoom003.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `d99d4103` | `DungeonRoomStep.SpiritTemple.DungeonRoom003.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `cacfb396` | `DungeonRoomStep.SpiritTemple.DungeonRoom004.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `91399ac8` | `DungeonRoomStep.SpiritTemple.DungeonRoom004.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `6e08b3e7` | `DungeonRoomStep.SpiritTemple.DungeonRoom005.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `3d16b618` | `DungeonRoomStep.SpiritTemple.DungeonRoom005.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `4d285809` | `DungeonRoomStep.SpiritTemple.DungeonRoom006.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `94bf92ba` | `DungeonRoomStep.SpiritTemple.DungeonRoom006.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `f0267b73` | `DungeonRoomStep.SpiritTemple.DungeonRoom007.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `e7ba7010` | `DungeonRoomStep.SpiritTemple.DungeonRoom007.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `903ba1a1` | `DungeonRoomStep.SpiritTemple.DungeonRoom008.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `1248eabf` | `DungeonRoomStep.SpiritTemple.DungeonRoom008.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `7874025a` | `DungeonRoomStep.SpiritTemple.DungeonRoom009.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `669f0af7` | `DungeonRoomStep.SpiritTemple.DungeonRoom009.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `928ff615` | `DungeonRoomStep.SpiritTemple.DungeonRoom010.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `733bddeb` | `DungeonRoomStep.SpiritTemple.DungeonRoom010.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `b1c34133` | `DungeonRoomStep.SpiritTemple.DungeonRoom011.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `b7c5ff52` | `DungeonRoomStep.SpiritTemple.DungeonRoom011.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `165f9a1f` | `DungeonRoomStep.SpiritTemple.DungeonRoom012.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `a6db1894` | `DungeonRoomStep.SpiritTemple.DungeonRoom012.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `f306204a` | `DungeonRoomStep.SpiritTemple.DungeonRoom013.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `c75f6e45` | `DungeonRoomStep.SpiritTemple.DungeonRoom013.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `ec53fdd4` | `DungeonRoomStep.SpiritTemple.DungeonRoom014.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `30169f5c` | `DungeonRoomStep.SpiritTemple.DungeonRoom014.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `1ec13816` | `DungeonRoomStep.SpiritTemple.DungeonRoom015.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `ba33f54b` | `DungeonRoomStep.SpiritTemple.DungeonRoom015.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `8c3b5b52` | `DungeonRoomStep.SpiritTemple.DungeonRoom016.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `7011e506` | `DungeonRoomStep.SpiritTemple.DungeonRoom016.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `0703ba2d` | `DungeonRoomStep.SpiritTemple.DungeonRoom017.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `09705f2f` | `DungeonRoomStep.SpiritTemple.DungeonRoom017.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `d668f485` | `DungeonRoomStep.SpiritTemple.DungeonRoom018.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `1b13ff65` | `DungeonRoomStep.SpiritTemple.DungeonRoom018.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `58afe8d4` | `DungeonRoomStep.SpiritTemple.DungeonRoom019.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `b4387727` | `DungeonRoomStep.SpiritTemple.DungeonRoom019.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `b772bfbb` | `DungeonRoomStep.SpiritTemple.DungeonRoom020.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `dae6367a` | `DungeonRoomStep.SpiritTemple.DungeonRoom020.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `7cfab22f` | `DungeonRoomStep.SpiritTemple.DungeonRoom021.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `986c76b0` | `DungeonRoomStep.SpiritTemple.DungeonRoom021.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `67286ca4` | `DungeonRoomStep.SpiritTemple.DungeonRoom022.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `146a90b4` | `DungeonRoomStep.SpiritTemple.DungeonRoom022.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `5f34de67` | `DungeonRoomStep.SpiritTemple.DungeonRoom023.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `774aec7a` | `DungeonRoomStep.SpiritTemple.DungeonRoom023.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `572d5e27` | `DungeonRoomStep.SpiritTemple.DungeonRoom024.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `4a25e273` | `DungeonRoomStep.SpiritTemple.DungeonRoom024.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `2ea9a129` | `DungeonRoomStep.SpiritTemple.DungeonRoom025.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `bb226721` | `DungeonRoomStep.SpiritTemple.DungeonRoom025.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `195df2b0` | `DungeonRoomStep.SpiritTemple.DungeonRoom026.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `28ad0eb9` | `DungeonRoomStep.SpiritTemple.DungeonRoom026.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `9eaa976c` | `DungeonRoomStep.SpiritTemple.DungeonRoom027.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `a34617da` | `DungeonRoomStep.SpiritTemple.DungeonRoom027.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `d3afd9a9` | `DungeonRoomStep.SpiritTemple.DungeonRoom028.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `f8395dbb` | `DungeonRoomStep.SpiritTemple.DungeonRoom028.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `f2f4d3b5` | `DungeonRoomStep.SpiritTemple.DungeonRoom029.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `720341e0` | `DungeonRoomStep.SpiritTemple.DungeonRoom029.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `a9649f1f` | `DungeonRoomStep.SpiritTemple.DungeonRoom030.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `c4f5861b` | `DungeonRoomStep.SpiritTemple.DungeonRoom030.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `9eb99810` | `DungeonRoomStep.SpiritTemple.DungeonRoom031.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `934e9c15` | `DungeonRoomStep.SpiritTemple.DungeonRoom031.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `6cdfda00` | `DungeonRoomStep.SpiritTemple.DungeonRoom032.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `6d3b978e` | `DungeonRoomStep.SpiritTemple.DungeonRoom032.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `1e0a82af` | `DungeonRoomStep.SpiritTemple.DungeonRoom033.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared | SpiritTemple |  |  | read |  |
| `535a1e42` | `DungeonRoomStep.SpiritTemple.DungeonRoom033.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group | SpiritTemple |  |  | read |  |
| `d1a13a82` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom000.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `5bf571fd` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom000.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `00a83541` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom001.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `ee1d5c9c` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom001.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `4422dabf` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom002.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `43300540` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom002.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `c3b2ca5a` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom003.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `8cb8d519` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom003.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `212a5821` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom004.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `c2a0cb32` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom004.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `499fabc6` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom005.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `0c5295c7` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom005.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `119181c0` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom006.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `423a0aa9` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom006.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `9b8f53aa` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom007.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `e9e0ddd8` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom007.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `408ac744` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom008.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `027e6855` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom008.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `33e7ed85` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom009.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `c0933b53` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom009.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `37760d0d` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom010.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `113b58f9` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom010.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `477ce9e0` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom011.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `aa9b3125` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom011.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `3e6cc5eb` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom012.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `c7b94ab9` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom012.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `7383780d` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom013.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `186617f4` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom013.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `bc26648f` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom014.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `ac5d2c39` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom014.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `8f21c491` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom015.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b5adfcd3` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom015.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `d2136087` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom016.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `4fad4395` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom016.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `81a213e0` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom017.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `3f89874d` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom017.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `b38f504d` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom018.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `4c6fa075` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom018.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `0cc7a4a2` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom019.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `80c9a8ab` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom019.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `aa2f53d0` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom020.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `61fc1dfd` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom020.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `e16f63ef` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom021.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `f3aebb9a` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom021.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `5582983d` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom022.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `35134517` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom022.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `6f4a7f17` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom023.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `a7f88e85` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom023.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `fce10d65` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom024.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `c8841cff` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom024.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `5b08cf31` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom025.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `beba424d` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom025.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `d50b9a7f` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom026.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `397eb679` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom026.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `09033695` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom027.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `07eb8ef8` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom027.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `8b675d27` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom028.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `a1137ccc` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom028.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `e9f8fbe2` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom029.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `0d6ee41b` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom029.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `25db9fee` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom030.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `9356a988` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom030.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `631b444e` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom031.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `7feb4c7a` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom031.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `53a45194` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom032.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `1dac18ed` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom032.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `140d3fd7` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom033.ClearRoom` | struct | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `9a909096` | `DungeonRoomStep.SpiritTemple_MQ.DungeonRoom033.Step` | struct | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
