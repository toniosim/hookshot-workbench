# Flag map: Single flags (2 of 3)

Flags that are not members of a struct: room, gimmick, boss, person and minigame flags named in full, and the ones with no name. 1308 rows on this page. Columns, values and how sure a row is: [README.md](README.md).

### flat flags (no group)

| Hash | Name | Named by | Kind | Default | Reset | File | Group | Co-op | Map | Note | What it is | Sure | Source |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `0d4ce67c` | `InsideJabuJabuBelly_TentacleRed_Camera` | files | Bool | 1 | 8 | progress | 1 | progress, shared | InsideJabuJabuBelly |  |  | read |  |
| `73a3875a` | `InsideJabuJabuBelly_TentacleRed_Obj00` | files | Bool | 1 | 8 | progress | 1 | progress, shared | InsideJabuJabuBelly |  |  | read |  |
| `b4ca4938` | `InsideJabuJabuBelly_TentacleRed_Obj02` | files | Bool | 1 | 8 | progress | 1 | progress, shared | InsideJabuJabuBelly |  |  | read |  |
| `2a020a15` | `InsideJabuJabuBelly_WarpPortal` | files | Bool | 0 | 8 | progress | 1 | progress, shared | InsideJabuJabuBelly |  |  | read |  |
| `332a79ec` | `Insidejaubjabu_Room06_OffRigLight` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `7c415fc9` | `InsidejaubjabuBelly_gimic_GetoffLift` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `c78981e6` | `InsidejaubjabuBelly_gimic_Liftposition_On` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `2439521c` | `InsidejaubjabuBelly_gimic_PlayerOnUpstairsOfLift` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `a969b54d` | `InsidejaubjabuBelly_gimic_switchOn_PlayerOnly` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b010d729` | `InsidejaubjabuBelly_gimic_switchOn_PlayerOnly_02` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `6fd2e588` | `InsidejaubjabuBelly_gimic_switchOn_Stone` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `88b1b922` | `InsideTheDekuTree_BossArea_ChangeENVForBoss` | source comment | Bool | 0 | 8 | progress | 1 | out: unshared list | InsideTheDekuTree |  | Switches the Deku Tree boss arena's environment for the fight; one player's own state, never shared by LS (also a fight flag of Gohma's set). | read | LS oot_coop.c |
| `e44433dc` | `InsideTheDekuTree_BossArea_ShutIn` | source comment | Bool | 0 | 8 | progress | 1 | out: unshared list | InsideTheDekuTree |  | Door that shuts behind whoever enters Queen Gohma's room; one player's own fight state, so LS never shares it (shared, it locked others out). | read | LS oot_coop.c |
| `1c594551` | `InsideTheDekuTree_Dungeon_EnemyScrubDekuDestroy_001` | files | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `1d493033` | `InsideTheDekuTree_Dungeon_EnemyScrubDekuDestroy_002` | files | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `60c22ed7` | `InsideTheDekuTree_Dungeon_EnemyScrubDekuDestroy_003` | files | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `98ca7aab` | `InsideTheDekuTree_Heart_Container_Obtained` | files | Bool | 0 | 8 | progress | 1 | out: heart reward | InsideTheDekuTree |  | Taken flag of the Deku Tree's heart container, the only heart flag the data names for a boss; co-op keeps it each player's own, never shared. | read | LS oot_coop.c |
| `fb39c3e6` | `InsideTheDekuTree_Level_RoomH_ClearBlock` | files | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `5f28addc` | `InsideTheDekuTree_OnThe1stFloor` | files | Bool | 0 | 1 | none | - | out: not saved | InsideTheDekuTree |  |  | read |  |
| `05d7b576` | `InsideTheDekuTree_OnThe2ndFloor` | files | Bool | 0 | 1 | none | - | out: not saved | InsideTheDekuTree |  |  | read |  |
| `f607f1ea` | `InsideTheDekuTree_OnThe3rdFloor` | files | Bool | 0 | 1 | none | - | out: not saved | InsideTheDekuTree |  |  | read |  |
| `8bb7cb87` | `InsideTheDekuTree_OnTheRoomH_MainRoom` | files | Bool | 0 | 8 | none | - | out: not saved | InsideTheDekuTree |  |  | read |  |
| `df7d4df0` | `InsideTheDekuTree_OnTheRoomI_MainRoom` | files | Bool | 0 | 8 | none | - | out: not saved | InsideTheDekuTree |  |  | read |  |
| `345532bf` | `InsideTheDekuTree_Room_KokiriCover` | files | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `8a06dc6b` | `InsideTheDekuTree_Room_KokiriCover_Irregular` | files | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `79c4cccf` | `InsideTheDekuTree_Room_Kokiridown` | files | Bool | 0 | 9 | progress | 1 | out: temporary | InsideTheDekuTree |  |  | read |  |
| `a356fb4c` | `InsideTheDekuTree_RoomA_Cleared` | files | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `e27b79a0` | `InsideTheDekuTree_RoomA_NearScaffold` | source comment | Bool | 0 | 8 | progress | 1 | out: unshared list | InsideTheDekuTree |  | Position flag: Link is near the scaffold in Deku Tree room A; a room sensor sets and clears it; one player's own, so LS never shares it. | read | LS oot_coop.c |
| `64edd2f3` | `InsideTheDekuTree_RoomB_Cleared` | files | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `77279a83` | `InsideTheDekuTree_RoomC_Cleared` | files | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `d0d8a271` | `InsideTheDekuTree_RoomD_Cleared` | files | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `6fb4f455` | `InsideTheDekuTree_RoomD_StepSwitch_On_01` | files | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `32797f0c` | `InsideTheDekuTree_RoomE_Cleared` | files | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `c0cd8da8` | `InsideTheDekuTree_RoomE_Cleared02` | files | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `a859e642` | `InsideTheDekuTree_RoomE_Enter` | files | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `46e8fcf9` | `InsideTheDekuTree_RoomE_KillSpiderWave` | files | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `c90d4ed1` | `InsideTheDekuTree_RoomF_Cleared` | files | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `27dfe587` | `InsideTheDekuTree_RoomG_Cleared` | files | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `8d2b85ef` | `InsideTheDekuTree_RoomG_WaterLevel` | files | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `392a228a` | `InsideTheDekuTree_RoomG_WaterLevel_timing` | files | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `f85ceb3f` | `InsideTheDekuTree_RoomH_Cleared` | files | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `a32a1bd0` | `InsideTheDekuTree_RoomI_Cleared` | files | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  |  | read |  |
| `d2f46f66` | `InsideTheDekuTree_RoomK_Cleared` | files | Bool | 0 | 8 | progress | 1 | progress, shared | InsideTheDekuTree |  | Set by the Deku Scrub Brothers' puzzle (room K); at 0 the Deku Tree boss door is locked from outside, with it set the door opened; it also crossed between two games. | tested | boss points |
| `f0368aad` | `InsideTheDekuTree_RoomK_Failure` | source comment | Bool | 0 | 8 | progress | 1 | out: unshared list | InsideTheDekuTree |  | Records that one player's try at Deku Tree room K failed; set by the room graph, read by none; in a two-game run it stayed in the game that set it. | tested | Fold68 |
| `9ef58bd8` | `InsideTheRoom_Npc_Hylia_013_Adult` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `78665409` | `InsideTheRoom_Npc_Hylia_014_Adult` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `375fd80e` | `InsideTheRoom_Npc_Hylia_015_Adult` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b594e494` | `InsideTheRoom_Npc_Hylia_016_Adult` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `7ae9c652` | `Introduction_FallingCeiling` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `7d3acd77` | `IsAfterSell_Mask_Bunny` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `33ea811a` | `IsAppear_GanondorfDeadBody` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  | Set true by Ganondorf's death flow; the name says his dead body then appears. | read | ClearedSave |
| `493997f2` | `IsArrived_LonLonRanch_AfterMalonAppear` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `7360ed12` | `IsBossBattle` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `084da83f` | `IsClear_Minigame_FindOutCucco` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `27cd4f2e` | `IsEnableUseAmiiboField` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `a74cb58e` | `IsExistMorpha_DreamWorld` | files | Bool | 1 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `b4962fee` | `IsGameClear` | names file | Bool | 0 | 8 | progress | 1 | progress, shared |  |  | Set when a slot has been cleared; the real finished saves have it, and the Load list then draws its Clear mark (small triforce) after the date. | tested | ClearedSave |
| `5526db84` | `IsGameClearAtLeastOnce` | names file | Bool | 0 | 0 | account | 1 | out: other file |  |  | Account-wide Bool in account.sav: some game was cleared at least once; the real finished account has it true. | read | ClearedSave |
| `2fd0bc6c` | `IsGameOverTrig` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `673fc08a` | `IsHyruleFieldBridgeClose` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `8e6ad5d3` | `IsInSneakArea` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `605e5df8` | `IsLastSelectedMQMode` | files | Bool | 0 | 0 | account | 1 | out: other file |  |  | Account Bool (account.sav) for whether the last chosen mode was Master Quest; false in the real finished account, which has no Master Quest slots. | read | ClearedSave |
| `ec5b415d` | `IsMalonAppear_And_NearLonLon` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `fd1b310e` | `IsMalonAppear_HyruleCastleSecondTime` | source comment | Bool | 0 | 8 | progress | 1 | out: unshared list |  |  | Malon's appearance at Hyrule Castle the second time (a set-and-clear by the game's logic, not progress); LS keeps it each game's own. | read | LS oot_coop.c |
| `291f87b2` | `IsMalonAppear_Market` | source comment | Bool | 0 | 8 | progress | 1 | out: unshared list |  |  | Malon's appearance in the Market (a set-and-clear by the game's logic, not progress); LS keeps it each game's own so a 1 never comes back. | read | LS oot_coop.c |
| `f800e596` | `IsNpc_Hylia_Malon_Child_Talk_00_Played` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `10d47e08` | `IsNpc_Hylia_Malon_Child_Talk_02_Played` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `f6fa4671` | `IsNpc_Hylia_Malon_Child_Talk_All` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `f7425fac` | `IsOcarinaEvent_BottomOfTheWell_Level_Room_01_Ocarina` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `5ae1a8d6` | `IsOcarinaEvent_Cow_GiveMilk_Ocarina` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `e9bf6230` | `IsPlayerDead` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `1203f6ff` | `IsPlayerLeavesHyruleCastleArea` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `c513b9af` | `IsPlayingFirstTruthMaskGetDemo` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `48d854ef` | `IsRead_FairyNote_FirstTime` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `34f53922` | `IsSettingMapPlayerIconAnchor` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `c320ab72` | `IsSkipRetrySequence` | files | Bool | 0 | 0 | none | - | out: not saved |  |  |  | read |  |
| `f10803e7` | `IsStart_FairySpiritMove` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `548128dd` | `IsTalk_MalonInLonLonRanch` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `67ac7142` | `IsUnvisiblePlayerStatusScreenForEventToMain` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `453e571b` | `IsZeldaLullabyPlayed_DaruniaEntrance` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `afe0b8c4` | `Item_Melody_SariaSong_Place` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `005b450f` | `Item_Melody_SariaSong_Story` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `9e6e284f` | `Item_Melody_SariaSong_Story_HaveRead` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `eec1481d` | `Item_Melody_SariaSong_Story_Step` | files | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `abb715f7` | `Item_Melody_SariaSong_Time` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `a49cb68c` | `JabJabOpenedMouth` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `848adb40` | `Kakariko_Sighboard_Break_01` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `b8888b26` | `KakarikoVillage_Adult_NaviGuideTimeTemple` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `dffd0247` | `KakarikoVillage_AfterBurned_NpcStayedFrontWell` | files | Bool | 0 | 9 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `512a6f59` | `KakarikoVillage_Burning_Start` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `edd7e863` | `KakarikoVillage_CarpentersArrived_MeetingPosition` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `b4991768` | `KakarikoVillage_CarpentersTalk01` | files | Bool | 0 | 10 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `84f352da` | `KakarikoVillage_CarpentersTalk02` | files | Bool | 0 | 10 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `8cad46ff` | `KakarikoVillage_Child_NaviGuide_TokenGold_Over10` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `8eabe2a4` | `KakarikoVillage_Child_NaviGuideSkulltulaHouse` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `7207ede9` | `KakarikoVillage_CrowedCucco_Npc_Hylia_Talon_Adult` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `eecaa92a` | `KakarikoVillage_DeleteDummyLadder` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `b10b5dc1` | `KakarikoVillage_DrugStore_FirstTalk` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `8665d8ca` | `KakarikoVillage_GatheringTokenGold_ActionGuide_AgonyStone_True` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `8848b5ff` | `KakarikoVillage_GatheringTokenGold_AfterHintTalk01` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `f9cb1cd4` | `KakarikoVillage_GatheringTokenGold_AfterHintTalk02` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `f13fb5a7` | `KakarikoVillage_GatheringTokenGold_CleanUp` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `cb1a74bb` | `KakarikoVillage_GatheringTokenGold_DoorClosed` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `9086a22e` | `KakarikoVillage_GatheringTokenGold_GetReward10` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `39dad76d` | `KakarikoVillage_GatheringTokenGold_GetReward20` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `cdcc9add` | `KakarikoVillage_GatheringTokenGold_GetReward30` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `8dc37ac6` | `KakarikoVillage_GatheringTokenGold_GetReward40` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `e3c6e4a3` | `KakarikoVillage_GatheringTokenGold_GetReward50` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `bdbf9ba5` | `KakarikoVillage_Gimmick_IsReDeadDestroyed` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `9ee9a7d5` | `KakarikoVillage_Hylia_015_NoticedComplete` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `7414cc9e` | `KakarikoVillage_Hylia_018_Shop_FlavorTalk_Int` | files | Int | 0 | 9 | progress | 3 | out: Int in no group | KakarikoVillage |  |  | read |  |
| `8813e0e7` | `KakarikoVillage_Hylia_018_Shop_Talking` | files | Bool | 0 | 9 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `8f2219ba` | `KakarikoVillage_Hylia_020_Shop_FlavorTalk_Int` | files | Int | 0 | 9 | progress | 3 | out: Int in no group | KakarikoVillage |  |  | read |  |
| `a5dd238b` | `KakarikoVillage_Hylia_020_Shop_Talking` | files | Bool | 0 | 9 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `97133763` | `KakarikoVillage_Ichiro_ArrivedGasaGosoPosition_AfterGetStones` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `644d80ea` | `KakarikoVillage_Ichiro_PlayerOntheWorkPlace` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `c1941648` | `KakarikoVillage_IchiroArrived_Action3` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `441b4ba8` | `KakarikoVillage_IchiroArrived_Action4` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `4cd0ee74` | `KakarikoVillage_IchiroArrived_MeetingPosition` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `3a27c499` | `KakarikoVillage_IsAfterCarpenterTalk` | files | Bool | 0 | 9 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `da9a2a49` | `KakarikoVillage_IsAfterFirstTalk_MakeBluePotion` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `85d8113a` | `KakarikoVillage_IsAfterSave_Npc_Hylia_025` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `5663a132` | `KakarikoVillage_IsIndoor_Npc_Hylia_007_Adult` | files | Bool | 0 | 9 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `7fbe00d4` | `KakarikoVillage_IsNearWell_Npc_Hylia_007_Adult` | files | Bool | 0 | 9 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `401949b7` | `KakarikoVillage_Jiro_ArrivedGasaGosoPosition` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `f1ffc737` | `KakarikoVillage_Jiro_ArrivedGasaGosoPosition_AfterGetStones` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `cfa112ff` | `KakarikoVillage_Jiro_PlayerOntheWorkPlace` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `c54ba883` | `KakarikoVillage_JiroArrived_Action4` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `4f41dfc6` | `KakarikoVillage_JiroArrived_Action6` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `2111df94` | `KakarikoVillage_JiroArrived_MeetingPosition` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `0bf7ce9d` | `KakarikoVillage_LeaveKakariko_Npc_Hylia_Talon_Adult` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  | Set by Talon's flows (a Cucco talk and the Giant's Knife quest) when he leaves Kakariko; four Lon Lon gates and two people are placed by it. | read | world model |
| `74791bda` | `KakarikoVillage_MiniGame_HitTarget_FirstTalk` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `483bf3c7` | `KakarikoVillage_NandemoShop_FirstTalk` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `1fe78249` | `KakarikoVillage_NoAttention_Npc_Hylia_002` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KakarikoVillage |  |  | read |  |
| `9e048f2a` | `KakarikoVillage_NoAttention_Npc_Hylia_003` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KakarikoVillage |  |  | read |  |
| `9f9b38ca` | `KakarikoVillage_NoAttention_Npc_Hylia_005` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KakarikoVillage |  |  | read |  |
| `45194d2d` | `KakarikoVillage_NoAttention_Npc_Hylia_007` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KakarikoVillage |  |  | read |  |
| `9fc3750f` | `KakarikoVillage_NoAttention_Npc_Hylia_010` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KakarikoVillage |  |  | read |  |
| `2ea8da13` | `KakarikoVillage_NoAttention_Npc_Hylia_012` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KakarikoVillage |  |  | read |  |
| `18b28a59` | `KakarikoVillage_NoAttention_Npc_Hylia_013` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KakarikoVillage |  |  | read |  |
| `f42da695` | `KakarikoVillage_NoAttention_Npc_Hylia_014` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KakarikoVillage |  |  | read |  |
| `c260b536` | `KakarikoVillage_NoAttention_Npc_Hylia_015` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KakarikoVillage |  |  | read |  |
| `b793f1d0` | `KakarikoVillage_NoAttention_Npc_Hylia_049` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KakarikoVillage |  |  | read |  |
| `080c2d49` | `KakarikoVillage_NoAttention_Npc_Hylia_051` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KakarikoVillage |  |  | read |  |
| `3e22f3aa` | `KakarikoVillage_NoAttention_Npc_Hylia_052` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KakarikoVillage |  |  | read |  |
| `6593d759` | `KakarikoVillage_NoAttention_Npc_Hylia_Soldier_002` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KakarikoVillage |  |  | read |  |
| `5ae62852` | `KakarikoVillage_Npc_Hylia_005_Adult_ArrivedAction6` | files | Bool | 0 | 32 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `b677f55c` | `KakarikoVillage_Npc_Hylia_005_Adult_ArrivedCocco` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `7836aa0e` | `KakarikoVillage_Npc_Hylia_005_Adult_ArrivedHome` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `9d8ab7db` | `KakarikoVillage_Npc_Hylia_005_Adult_IsInHouse` | files | Bool | 0 | 32 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `f2a6f558` | `KakarikoVillage_Npc_Hylia_005_Adult_IsInHouse_2F` | files | Bool | 0 | 40 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `63642c50` | `KakarikoVillage_Npc_Hylia_005_Adult_Wander1` | files | Bool | 0 | 32 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `7423bd80` | `KakarikoVillage_Npc_Hylia_007_Adult_ArrivedAction05` | files | Bool | 0 | 32 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `f4b51b7c` | `KakarikoVillage_Npc_Hylia_007_Adult_ArrivedAction2` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `2ef7b5e0` | `KakarikoVillage_Npc_Hylia_007_Adult_ArrivedAction4` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `4099916b` | `KakarikoVillage_Npc_Hylia_007_Adult_ArrivedAction9` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `dcb2af49` | `KakarikoVillage_Npc_Hylia_007_Adult_GroupTalk_2` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `570b52da` | `KakarikoVillage_Npc_Hylia_007_Adult_IsAfterTalk_Well` | files | Bool | 0 | 1 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `8f90c55c` | `KakarikoVillage_Npc_Hylia_009_Adult_BeforeStormSong` | files | Bool | 0 | 9 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `bcfbcb64` | `KakarikoVillage_Npc_Hylia_009_Adult_PlayedStormSong_1stFloor` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `bddab6e0` | `KakarikoVillage_Npc_Hylia_009_Adult_PlayedStormSong_2ndFloor` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `61960b30` | `KakarikoVillage_Npc_Hylia_009_Child_DeleteWaterPlane` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `a017cc88` | `KakarikoVillage_Npc_Hylia_009_Child_ForWaterways` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `5097976f` | `KakarikoVillage_Npc_Hylia_009_Child_OcarinaPlayedFirsttime` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `15e328bf` | `KakarikoVillage_Npc_Hylia_009_OcarinaStormSong_PlayedFront` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KakarikoVillage |  |  | read |  |
| `480b4a25` | `KakarikoVillage_Npc_Hylia_009_SoonAfterStormSong` | files | Bool | 0 | 9 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `56f8cc0d` | `KakarikoVillage_Npc_Hylia_010_Adult_ArrivedAction2` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `2c61d369` | `KakarikoVillage_Npc_Hylia_010_Adult_ArrivedAction3` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `2cd4ff5b` | `KakarikoVillage_Npc_Hylia_010_Adult_IsAfterFirstTalk_FrontHouse` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `e615d8ff` | `KakarikoVillage_Npc_Hylia_010_Adult_IsAfterTalk_Well` | files | Bool | 0 | 1 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `e36039c9` | `KakarikoVillage_Npc_Hylia_010_AfterTalked_BrokenWindmill` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KakarikoVillage |  |  | read |  |
| `1e208c82` | `KakarikoVillage_Npc_Hylia_010_Child_ArrivedAction2` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `0f0d0b89` | `KakarikoVillage_Npc_Hylia_010_Child_ArrivedAction3` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `61b94293` | `KakarikoVillage_Npc_Hylia_010_Child_IsAfterFirstTalk` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `1b4e07c8` | `KakarikoVillage_Npc_Hylia_010_Child_IsAfterFirstTalk_Action7` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `6edbb8a8` | `KakarikoVillage_Npc_Hylia_010_Child_IsAfterFirstTalk_FrontHouse` | files | Bool | 0 | 9 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `834f0018` | `KakarikoVillage_Npc_Hylia_010_Child_IsAfterTalk_ImpaHouse` | files | Bool | 0 | 9 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `67f2923a` | `KakarikoVillage_Npc_Hylia_010_GotoWell` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KakarikoVillage |  |  | read |  |
| `6a0df582` | `KakarikoVillage_Npc_Hylia_012_Child_Action0` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `7ec244e4` | `KakarikoVillage_Npc_Hylia_012_Child_Action1` | files | Bool | 0 | 11 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `f9771eed` | `KakarikoVillage_Npc_Hylia_012_Child_Action2` | files | Bool | 0 | 11 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `ef0fb635` | `KakarikoVillage_Npc_Hylia_012_Child_AriivedHome` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `82d41b23` | `KakarikoVillage_Npc_Hylia_012_Child_IsAfterTalkEvent01` | files | Bool | 0 | 9 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `bb3d98a0` | `KakarikoVillage_Npc_Hylia_012_Child_IsAfterTalkEvent02` | files | Bool | 0 | 9 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `36a9e316` | `KakarikoVillage_Npc_Hylia_013_Child_Action1` | files | Bool | 0 | 11 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `d3dac900` | `KakarikoVillage_Npc_Hylia_013_Child_ArrivedGasaGosoPosition` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `dcbc1acd` | `KakarikoVillage_Npc_Hylia_013_Child_Wander1` | files | Bool | 0 | 11 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `deb0f6fe` | `KakarikoVillage_Npc_Hylia_015_Child_About_CuccoSister` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `880e7f14` | `KakarikoVillage_Npc_Hylia_016_Child_Night` | files | Bool | 0 | 11 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `e6d7336d` | `KakarikoVillage_Npc_Hylia_049_Child_ArriveImpaHouse` | files | Bool | 0 | 9 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `bb5fefc5` | `KakarikoVillage_Npc_Hylia_049_Child_Hint5` | files | Bool | 0 | 9 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `0709a17a` | `KakarikoVillage_Npc_Hylia_049_Child_IsAfterTalk_ImpaHouse` | files | Bool | 0 | 9 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `47819438` | `KakarikoVillage_Npc_Hylia_051_Adult_ArrivedAction2` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `0dbf2002` | `KakarikoVillage_Npc_Hylia_051_Adult_ArrivedAction3` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `8c24af4d` | `KakarikoVillage_Npc_Hylia_051_Adult_ArrivedAction4` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `0a05fd95` | `KakarikoVillage_Npc_Hylia_051_Adult_Assembled` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `da55b1ed` | `KakarikoVillage_Npc_Hylia_051_Adult_IsAfterFirstTalk_FrontHouse` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `99f419cc` | `KakarikoVillage_Npc_Hylia_051_Adult_IsAfterTalk01` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KakarikoVillage |  |  | read |  |
| `d24efb14` | `KakarikoVillage_Npc_Hylia_051_Adult_IsAfterTalk02` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KakarikoVillage |  |  | read |  |
| `67154b39` | `KakarikoVillage_Npc_Hylia_051_Adult_IsAfterTalk03` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KakarikoVillage |  |  | read |  |
| `581ba6ec` | `KakarikoVillage_Npc_Hylia_051_Child_ArrivedAction2` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `7c6f4477` | `KakarikoVillage_Npc_Hylia_051_Child_Assembled` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `0e25e1f0` | `KakarikoVillage_Npc_Hylia_051_Child_IsAfterFirstTalk_FrontHouse` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KakarikoVillage |  |  | read |  |
| `cdad4064` | `KakarikoVillage_Npc_Hylia_051_Child_IsAfterFirstTalk_InHouse` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `8bdfd7a6` | `KakarikoVillage_Npc_Hylia_051_Child_IsAfterFirstTalk_Waiting` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KakarikoVillage |  |  | read |  |
| `6812031d` | `KakarikoVillage_Npc_Hylia_051_Child_IsAfterInpaTalked_Waiting` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KakarikoVillage |  |  | read |  |
| `f4c5a104` | `KakarikoVillage_Npc_Hylia_051_Child_IsAfterTalk01` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KakarikoVillage |  |  | read |  |
| `636a1134` | `KakarikoVillage_Npc_Hylia_051_Child_IsAfterTalk02` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KakarikoVillage |  |  | read |  |
| `bf593c05` | `KakarikoVillage_Npc_Hylia_051_Child_IsAfterTalk03` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KakarikoVillage |  |  | read |  |
| `7ba5a2e6` | `KakarikoVillage_Npc_Hylia_051_Child_IsAfterTalk_WindMillAndWell` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `832f9e3c` | `KakarikoVillage_Npc_Hylia_051_GotoWell` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KakarikoVillage |  |  | read |  |
| `ac8c0d96` | `KakarikoVillage_Npc_Hylia_052_Adult_RunningRichard` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `bb7314f0` | `KakarikoVillage_Npc_Hylia_052_Child_DisableInterestDog` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `6d6ac34c` | `KakarikoVillage_Npc_MenTalk_GuideHookshot` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `75d6c63b` | `KakarikoVillage_Npc_Soldier_002_GotoWell` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KakarikoVillage |  |  | read |  |
| `6aa99461` | `KakarikoVillage_Npc_Soldier_002_OutOfTopic` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `6d6f4245` | `KakarikoVillage_NpcAttentionLimitter` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KakarikoVillage |  |  | read |  |
| `56cfb614` | `KakarikoVillage_NPCNearWell` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `4c27cd43` | `KakarikoVillage_NpcSkullDad_IsAfterFirstTalk_Adult` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `2db98239` | `KakarikoVillage_NpcSkullDad_IsAfterFirstTalk_Child` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `2b476343` | `KakarikoVillage_NpcSkullDad_IsAfterTimeLeap` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `dd3306bf` | `KakarikoVillage_ObabaShop_FirstTalk` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `89458099` | `KakarikoVillage_Saburo_ArrivedGasaGosoPosition` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `2ec2d8eb` | `KakarikoVillage_Saburo_ArrivedGasaGosoPosition_AfterGetStones` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `c95c76c5` | `KakarikoVillage_Saburo_PlayerOntheWorkPlace` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `98230af0` | `KakarikoVillage_SaburoArrived_Action4` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `e8ff9d36` | `KakarikoVillage_SaburoArrived_GasaGosoPosition` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `6b9f4b26` | `KakarikoVillage_SaburoArrived_MeetingPosition` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `aab2ff2f` | `KakarikoVillage_Shiro_ArrivedGasaGosoPosition` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `5b8edcbd` | `KakarikoVillage_Shiro_ArrivedGasaGosoPosition_AfterGetStones` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `a2a30668` | `KakarikoVillage_Shiro_PlayerOntheWorkPlace` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `2feba0e2` | `KakarikoVillage_ShiroArrived_Action1` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `d43637d5` | `KakarikoVillage_ShiroArrived_Action4` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `a64bbc13` | `KakarikoVillage_ShiroArrived_Action6` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `0903eb03` | `KakarikoVillage_ShiroArrived_MeetingPosition` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `73ce3fea` | `KakarikoVillage_Soldier_002_HaveTalked_DampeDiary` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `4bc2a8a1` | `KakarikoVillage_Soldier_002_HaveTalked_Impa` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `ac27a6ff` | `KakarikoVillage_Soldier_002_HaveTalked_Sentry` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `158553f0` | `KakarikoVillage_Soldier_002_HaveTalked_SkullFamily` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `794fc7a9` | `KakarikoVillage_Soldier_002_HaveTalked_Well` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `b0edb11f` | `KakarikoVillage_Talon_HaveTalked_aboutLonLonRanch` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KakarikoVillage |  |  | read |  |
| `a6d4e3f2` | `KakarikoVillage_Talon_HaveTalked_RemindLonLonRanch` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KakarikoVillage |  |  | read |  |
| `689dc73d` | `KakarikoVillage_Talon_TurnOverInBed_SunSong` | files | Bool | 0 | 9 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `c7fe3216` | `KakarikoVillage_Windmill_DoorOpened` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `db551fb0` | `KakarikoVillage_Windmill_IsHighSpeed` | files | Bool | 0 | 1 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `9a83859f` | `KakarikoVillage_Windmill_PlayerInFrontDoor` | files | Bool | 0 | 8 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `bbf4977c` | `KakarikoVillage_Windmill_StartSlowdown` | files | Bool | 0 | 1 | none | - | out: not saved | KakarikoVillage |  |  | read |  |
| `08795b06` | `KingZora_Child_DeactivateInterestToPlayer` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `8e57d527` | `KokiriForest_Adult_Arrived` | names file | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `9b0dbe55` | `KokiriForest_Adult_IsEnter` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KokiriForest |  |  | read |  |
| `bb6ebebb` | `KokiriForest_AfterShieldTalk_Npc_Kokiri_008_Child` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `6d622288` | `KokiriForest_Get_StoneOfForest_IsCompleted_MaxNumberOfTalkedNpc` | files | Int | 3 | 8 | none | - | out: Int in no group | KokiriForest |  |  | read |  |
| `eb6355a3` | `KokiriForest_Get_StoneOfForest_IsCompleted_NumberOfTalkedNpc` | files | Int | 0 | 8 | progress | 3 | out: Int in no group | KokiriForest |  |  | read |  |
| `4c657880` | `KokiriForest_IsAfterGoronCityDarniaroomOpen_Npc_Kokiri_003_Child` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `bf8f71f8` | `KokiriForest_IsTalked_Cow` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `f8af0af3` | `KokiriForest_Kokiri_011_NaviAttentionFirstZL` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `173fe02a` | `KokiriForest_Kokiri_011_NaviAttentionNow` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `fadf413f` | `KokiriForest_Kokiri_011_StopInFrontOfShop_00` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `ff05ecf0` | `KokiriForest_LinkHouseDoor_DoAction` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `9b1b27d2` | `KokiriForest_LinkHouseDoor_Open` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  | Set when Link's house door is opened (the A prompt reads Open); seen 0 to 1 in a pilot run as the door opened. | tested | PilotProof2 |
| `1afd0ad0` | `KokiriForest_LinkHouseGoDown` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `1ec2cf04` | `KokiriForest_Meet_DekuTree_BoughtDekuShield` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `9a60a460` | `KokiriForest_Meet_DekuTree_OpenDekuTreeMouth` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `a033d7a1` | `KokiriForest_NaviHint_HaveBeenToTheCave` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `89fee8ba` | `KokiriForest_Npc_006_LockOnA` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KokiriForest |  |  | read |  |
| `5ec4d18f` | `KokiriForest_Npc_006_LockOnB` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KokiriForest |  |  | read |  |
| `6b7adbf7` | `KokiriForest_Npc_Kokiri_004_Adult_IsSuprisedNearEvent` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KokiriForest |  |  | read |  |
| `d84ec01b` | `KokiriForest_Npc_Kokiri_004_Adult_SuprisedFlag` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `47823545` | `KokiriForest_Npc_Kokiri_004_Child_IsAfterFirstTalk` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `289ba610` | `KokiriForest_Npc_Kokiri_005_Adult_IsSuprisedNearEvent` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KokiriForest |  |  | read |  |
| `9792d3d1` | `KokiriForest_Npc_Kokiri_005_Adult_SuprisedFlag` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `8049d2e4` | `KokiriForest_Npc_Kokiri_005_Child_IsMowingTalked` | files | Bool | 0 | 8 | none | - | out: not saved | KokiriForest |  |  | read |  |
| `73e06b9d` | `KokiriForest_Npc_Kokiri_005_Child_Talk_01` | files | Bool | 1 | 8 | none | - | out: not saved | KokiriForest |  |  | read |  |
| `0179c4f4` | `KokiriForest_Npc_Kokiri_006_Adult_IsSuprisedNearEvent` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KokiriForest |  |  | read |  |
| `28923020` | `KokiriForest_Npc_Kokiri_006_Adult_SuprisedFlag` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `6760b452` | `KokiriForest_Npc_Kokiri_006_Child_ActionArea` | files | Bool | 0 | 9 | none | - | out: not saved | KokiriForest |  |  | read |  |
| `554c951d` | `KokiriForest_Npc_Kokiri_006_Child_ActionSuccess_once` | files | Bool | 0 | 8 | none | - | out: not saved | KokiriForest |  |  | read |  |
| `2f46882e` | `KokiriForest_Npc_Kokiri_006_Child_ActionTypeA_Clear` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `59ad7d26` | `KokiriForest_Npc_Kokiri_006_Child_ActionTypeA_Ready` | files | Bool | 0 | 9 | none | - | out: not saved | KokiriForest |  |  | read |  |
| `dd1ce944` | `KokiriForest_Npc_Kokiri_006_Child_ActionTypeB_Clear` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `3ca920a6` | `KokiriForest_Npc_Kokiri_006_Child_ActionTypeB_OperatedBackStep` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `bacca3c6` | `KokiriForest_Npc_Kokiri_006_Child_ActionTypeB_Ready` | files | Bool | 0 | 9 | none | - | out: not saved | KokiriForest |  |  | read |  |
| `2e74cd87` | `KokiriForest_Npc_Kokiri_006_Child_ActionTypeC_Ready` | names file | Bool | 0 | 9 | none | - | out: not saved | KokiriForest |  |  | read |  |
| `1526a508` | `KokiriForest_Npc_Kokiri_006_Child_ActionTypeD_AttentionHit` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `d7de808c` | `KokiriForest_Npc_Kokiri_006_Child_ActionTypeD_Clear` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `0dc3c61f` | `KokiriForest_Npc_Kokiri_006_Child_ActionTypeD_NotAttetion` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `c9d41c08` | `KokiriForest_Npc_Kokiri_006_Child_ActionTypeD_Ready` | files | Bool | 0 | 9 | none | - | out: not saved | KokiriForest |  |  | read |  |
| `63b24c04` | `KokiriForest_Npc_Kokiri_006_Child_ActionTypeZero_AttentionMove` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `bc1c4aed` | `KokiriForest_Npc_Kokiri_006_Child_ActionTypeZero_Clear` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `2307603e` | `KokiriForest_Npc_Kokiri_006_Child_ActionTypeZero_NotAttention` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `bd5c37a7` | `KokiriForest_Npc_Kokiri_006_Child_ActionTypeZero_Ready` | files | Bool | 0 | 9 | none | - | out: not saved | KokiriForest |  |  | read |  |
| `a6e896e2` | `KokiriForest_Npc_Kokiri_006_Child_AttentionAction` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `a87d3316` | `KokiriForest_Npc_Kokiri_006_Child_OnceBalloonGetSwordPlayer` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `41d4bdad` | `KokiriForest_Npc_Kokiri_006_Child_OperatedBackStep_IsTalked` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `613a8003` | `KokiriForest_Npc_Kokiri_006_Child_Talk_02` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `0817c135` | `KokiriForest_Npc_Kokiri_006_Child_Talk_04` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `f61420db` | `KokiriForest_Npc_Kokiri_006_Child_TurnToPlayerGotSword` | files | Bool | 1 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `6b8cabad` | `KokiriForest_Npc_Kokiri_006_Child_TutorialDangerArea_HiddenPos` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `0f3a5f1f` | `KokiriForest_Npc_Kokiri_006_Child_TutorialDangerArea_Left` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `a264f7be` | `KokiriForest_Npc_Kokiri_006_Child_TutorialDangerArea_NpcRoute` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `53b60e0f` | `KokiriForest_Npc_Kokiri_006_Child_TutorialDangerArea_Right` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `651afaa2` | `KokiriForest_Npc_Kokiri_006_Child_TutorialDangerArea_Self` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `f0fde374` | `KokiriForest_Npc_Kokiri_007_Child_Blocker` | source comment | Bool | 0 | 8 | progress | 1 | out: unshared list | KokiriForest |  | Kokiri guard flag at the forest exit (a child Kokiri's blocker), set and cleared again by the game's own logic; LS keeps it each game's own. | read | LS oot_coop.c |
| `e5dc5674` | `KokiriForest_Npc_Kokiri_007_Child_Blocker_00` | files | Bool | 1 | 8 | progress | 1 | progress, shared | KokiriForest |  | Blocker flag of a child Kokiri: an invisible wall stands while true; his talk clears it once the Forest Stone quest is Complete. | read | world model |
| `4097ed9c` | `KokiriForest_Npc_Kokiri_008_Child_AlreadyPaid` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `6090cf95` | `KokiriForest_Npc_Kokiri_008_Child_LiftRock_AllBroken` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `60e9c6e3` | `KokiriForest_Npc_Kokiri_008_Child_TalkedInFront` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `9c9d998c` | `KokiriForest_Npc_Kokiri_010_Adult_IsSuprisedNearEvent` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KokiriForest |  |  | read |  |
| `0b1d0647` | `KokiriForest_Npc_Kokiri_010_Adult_SuprisedFlag` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `fae64ad2` | `KokiriForest_Npc_Kokiri_011_Adult_IsSuprisedNearEvent` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KokiriForest |  |  | read |  |
| `099bff21` | `KokiriForest_Npc_Kokiri_011_Adult_SuprisedFlag` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `573ff74a` | `KokiriForest_Npc_Kokiri_011_Child_LockOnAttentionFlag` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `2276a48e` | `KokiriForest_Npc_Kokiri_011_Child_Near` | files | Bool | 0 | 8 | none | - | out: not saved | KokiriForest |  |  | read |  |
| `804893a5` | `KokiriForest_Npc_Kokiri_011_Child_Talk_LinkPosition_Left` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `026cf794` | `KokiriForest_Npc_Kokiri_011_Child_Talk_LinkPosition_Right` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `0edf90c2` | `KokiriForest_Npc_Kokiri_011_Child_Talk_LinkPosition_Under` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `bde8b617` | `KokiriForest_Npc_Kokiri_013_Adult_IsSuprisedNearEvent` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KokiriForest |  |  | read |  |
| `339f3933` | `KokiriForest_Npc_Kokiri_013_Adult_SuprisedFlag` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `c6724c2e` | `KokiriForest_Npc_Kokiri_Blocker` | source comment | Bool | 0 | 8 | progress | 1 | out: unshared list | KokiriForest |  | Kokiri guard flag in Kokiri Forest, set and cleared again by the game's own logic; LS keeps it each game's own so a 1 never comes back. | read | LS oot_coop.c |
| `8a987fe3` | `KokiriForest_Npc_Kokiri_Fado_Child_AttentionFlag` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `3b320c55` | `KokiriForest_Npc_Kokiri_Mido_Adult_Blocker` | files | Bool | 1 | 8 | progress | 1 | progress, shared | KokiriForest |  | Mido's blocker in the adult Lost Woods: two invisible walls stand while true; the Forest sage flow's blocker move clears it. | read | world model |
| `fa83da6c` | `KokiriForest_Npc_Kokiri_Mido_Adult_FirstNear` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `502f6cea` | `KokiriForest_Npc_Kokiri_Mido_Child_Blocker` | files | Bool | 1 | 8 | progress | 1 | progress, shared | KokiriForest |  | Mido's blocker in the child Kokiri Forest: an invisible wall stands while true; Mido's talk and the Forest Stone scene clear it. | read | world model |
| `f3eda168` | `KokiriForest_Npc_Kokiri_Mido_Child_Talk_01` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `7a754164` | `KokiriForest_Npc_Kokiri_Mido_Child_Talk_02` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `092699eb` | `KokiriForest_Npc_Kokiri_Saria_Child_Talk_01` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `6fda3c3d` | `KokiriForest_Npc_Kokiri_Saria_Child_Talk_02` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `693daff0` | `KokiriForest_PlayerAtLinkHouse` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `cd695012` | `KokiriForest_Shop_FlavorTalk_Int` | files | Int | 0 | 9 | progress | 3 | out: Int in no group | KokiriForest |  |  | read |  |
| `dea896e5` | `KokiriForest_Shop_SelectActor` | files | Bool | 0 | 9 | none | - | out: not saved | KokiriForest |  |  | read |  |
| `37d3074a` | `KokiriForest_Shop_SelectActor_Shield_Deku` | files | Bool | 0 | 9 | progress | 1 | out: temporary | KokiriForest |  | Set by the shop flow when the Deku Shield is the selected goods in the Kokiri shop (PlayHarness read it from the flow DisplayShop). | read | PlayHarness |
| `6e2e1c91` | `KokiriForest_Shop_Talking` | files | Bool | 0 | 9 | none | - | out: not saved | KokiriForest |  |  | read |  |
| `20d19893` | `KokiriForest_Success_RollAttack_Tree` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `136b46be` | `KokiriForest_TreasureBox_NaviChatOff` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `8c072678` | `KokiriForest_Tutorial_AttackGuide` | files | Bool | 1 | 8 | progress | 1 | progress, shared | KokiriForest |  |  | read |  |
| `411c8572` | `KokiriForest_Tutorial_BasicGuide` | files | Bool | 0 | 8 | progress | 1 | progress, shared | KokiriForest |  | Set the moment Saria's tutorial with Navi begins in Kokiri Forest; the test harness saw it rise at that moment. | tested | PlayHarness |
| `f43926e2` | `LakeHrl_Tombstone_AnswerPos` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `e1602368` | `LakeHylia_IsOnHouseOutside` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `54b613cf` | `LakeHylia_OverlapSharkAppearArea` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `8bb7f3ce` | `LakeHylia_secretHole_appearTreasureBox` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `4a155c46` | `Left_NoAttentionArea_ReDead` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `e69f1eb9` | `LiftUp_Ruto` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `c334954d` | `LiftUp_SuperCucco1` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `e072d0bc` | `LiftUp_SuperCucco2` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `88435cb6` | `LiftUp_SuperCucco3` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `8857aedb` | `LinkBed_DeepSleep` | files | Bool | 0 | 8 | none | - | out: not saved |  |  | Set when Link chooses to sleep at his bed; in a test run it rose 0 to 1 and the game then loaded the Hall of Fallen Foes (Dream World). | tested | boss points |
| `d95d320e` | `LonLonRanch_Adult_HaveTalkAboutEpona` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `d55d9221` | `LonLonRanch_ClearBlockPuzzle` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `840ca84a` | `LonLonRanch_GambleRace_IsInsideFence` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `47693791` | `LonLonRanch_GambleRace_NearChair` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  | Lon Lon Ranch gamble-race flag; while true, three invisible walls (one for the player, two for animals) stand; no event flow sets it. | read | world model |
| `8d4dff66` | `LonLonRanch_GambleRace_RideSideFence` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `d8b22cc7` | `LonLonRanch_GambleRaceAfterFirstDemo` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `36c8acf1` | `LonLonRanch_GambleRaceGoaledIngo` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `03c8d7f1` | `LonLonRanch_GambleRaceGoaledPlayer` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `88e7338c` | `LonLonRanch_GambleRaceLoseOtherThanEpona` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `eadaa283` | `LonLonRanch_GambleRaceProgressIngo` | files | Int | 0 | 8 | none | - | out: Int in no group |  |  |  | read |  |
| `897b8d5d` | `LonLonRanch_GambleRaceProgressPlayer` | files | Int | 0 | 8 | none | - | out: Int in no group |  |  |  | read |  |
| `924a0138` | `LonLonRanch_GambleRaceWinCount` | files | Int | 0 | 8 | none | - | out: Int in no group |  |  |  | read |  |
| `136a394b` | `LonLonRanch_HavePlayedGambleRace` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `fd901498` | `LonLonRanch_IsNearBed` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `39e7fd18` | `LonLonRanch_IsVisited_Child` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `a253721c` | `LonLonRanch_PlayingGambleRace` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `93a97087` | `LookedMask_Npc_Hylia_030_Child` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `bf981135` | `LookedMask_Npc_Hylia_RunningMan_Child` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `ed1442e5` | `LookedMask_Npc_Hylia_Soldier_003` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `af543a70` | `LookedMask_Npc_SkullKid_Child` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `77775e9e` | `LoopReadHrlField_Note` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `3c7b9388` | `Lostwood_BancChangeArrive_Kokiri` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `5ef24799` | `Lostwood_Enemy_Scrub_Business_DekuNutsPouch_01` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `8c98cf5a` | `LostWood_Enemy_Scrub_Business_DekuStickPouch_01` | files | Bool | 0 | 8 | progress | 1 | progress, shared | LostWood |  |  | read |  |
| `426980a6` | `LostWood_ForestStage_LowestRating` | files | Bool | 0 | 8 | progress | 1 | progress, shared | LostWood |  |  | read |  |
| `4bafdf70` | `LostWood_HitTargetOfDekuScrub_FirstClear` | files | Bool | 0 | 8 | progress | 1 | progress, shared | LostWood |  |  | read |  |
| `31dcaac2` | `LostWood_HitTargetOfDekuScrub_InvalidHit` | files | Bool | 0 | 8 | progress | 1 | progress, shared | LostWood |  |  | read |  |
| `def49685` | `Lostwood_HitTargetOfDekuScrub_IsEdgeHit` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `a26c859d` | `LostWood_HitTargetOfDekuScrub_IsReverseHit` | files | Bool | 0 | 8 | none | - | out: not saved | LostWood |  |  | read |  |
| `c101ffea` | `Lostwood_HitTargetOfDekuScrub_NumOfConsecutiveHit` | files | Int | 0 | 1 | none | - | out: Int in no group |  |  |  | read |  |
| `035a5e88` | `Lostwood_HitTargetOfDekuScrub_Talked_01` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `a1eb22e6` | `LostWood_Npc_Kokiri_Blocker` | source comment | Bool | 0 | 8 | progress | 1 | out: unshared list | LostWood |  | Kokiri guard flag in the Lost Woods, set and cleared again by the game's own logic; LS keeps it each game's own so a 1 never comes back. | read | LS oot_coop.c |
| `b96ea3a1` | `LostWood_Npc_SkullKid_Child_01` | files | Bool | 0 | 9 | progress | 1 | out: temporary | LostWood |  |  | read |  |
| `9927e531` | `LostWood_Npc_SkullKid_Child_02` | files | Bool | 0 | 9 | progress | 1 | out: temporary | LostWood |  |  | read |  |
| `2cc21916` | `Lostwood_Npc_SkullKid_Child_03` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `328401ce` | `LostWood_ScrubForestStage_EnableEventLaunch` | files | Bool | 1 | 9 | progress | 1 | out: temporary | LostWood |  |  | read |  |
| `e085793f` | `LostWood_ScrubForestStage_IsFirstTime` | files | Bool | 1 | 9 | progress | 1 | out: temporary | LostWood |  |  | read |  |
| `2751ac85` | `LostWood_ScrubForestStage_NaviChat_SameMask` | files | Bool | 0 | 8 | progress | 1 | progress, shared | LostWood |  |  | read |  |
| `5db0e8ed` | `LostWood_ScrubForestStage_SkullMaskEventLaunched` | files | Bool | 0 | 8 | progress | 1 | progress, shared | LostWood |  |  | read |  |
| `8058d89d` | `LostWood_ScrubForestStage_SurfaceFairPlayed` | files | Bool | 0 | 8 | progress | 1 | progress, shared | LostWood |  |  | read |  |
| `cdf86c43` | `LostWood_ScrubForestStage_TrueMaskEventLaunched` | files | Bool | 0 | 8 | progress | 1 | progress, shared | LostWood |  |  | read |  |
| `32c50f9c` | `LostWood_SkullkidArea_NaviChat_Check` | files | Bool | 0 | 8 | progress | 1 | progress, shared | LostWood |  |  | read |  |
| `6ed2dc56` | `MagicBean_Explanation` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `ea4532c2` | `MagicBean_FairySpiritAppear` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `5a684cc8` | `MagicBean_Talked` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `9a4dd779` | `MapIconDeactivateByAreaActor` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `dd6f294b` | `MapIconPlayerStop` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `d0ec0781` | `Market_Adult_Firsttime_GobacktoChild` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  |  | read |  |
| `0895a9ff` | `Market_Adult_GetLightPrelude` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  | Set once Link has learned the Prelude of Light in the adult Market; with the Zelda meeting flag it unlocks the bed's Hall of Fallen Foes choice. | read | boss points |
| `8a69733f` | `Market_BombchuShop_FirstTalk` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  |  | read |  |
| `a7017238` | `Market_Child_BombchuShop_KickedOut` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  |  | read |  |
| `6ee00820` | `Market_Child_BombchuShop_PromisedBuying` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  |  | read |  |
| `d5ce94f3` | `Market_Child_Firsttime_GotoAdult` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  |  | read |  |
| `d7beca06` | `Market_Child_FoundMasterSword` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  |  | read |  |
| `ddf45dbe` | `Market_Child_TimeTemple_DeleteLightShaft_FirstTime_00` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  |  | read |  |
| `727c2cbd` | `Market_Child_TimeTempleDoor_Opened` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  |  | read |  |
| `5acf6a1b` | `Market_DrugStore_FirstTalk` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  |  | read |  |
| `44d17738` | `Market_GossipMemberAssembled` | files | Bool | 0 | 32 | none | - | out: not saved | Market |  |  | read |  |
| `760f346e` | `Market_GossipMemberAssembled_01` | files | Bool | 0 | 8 | none | - | out: not saved | Market |  |  | read |  |
| `e2febd24` | `Market_HappyMaskShop_Angry` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  |  | read |  |
| `053d1a2e` | `Market_HappyMaskShop_FirstTalk` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  |  | read |  |
| `21b338c6` | `Market_HappyMaskShop_Talking` | files | Bool | 0 | 11 | none | - | out: not saved | Market |  |  | read |  |
| `4a224678` | `Market_Hylia_018_Shop_FlavorTalk_Int` | files | Int | 0 | 9 | progress | 3 | out: Int in no group | Market |  |  | read |  |
| `7434de7e` | `Market_Hylia_018_Shop_Talking` | files | Bool | 0 | 9 | none | - | out: not saved | Market |  |  | read |  |
| `34692674` | `Market_Hylia_020_Shop_FlavorTalk_Int` | files | Int | 0 | 9 | progress | 3 | out: Int in no group | Market |  |  | read |  |
| `b77abe56` | `Market_Hylia_020_Shop_Talking` | files | Bool | 0 | 9 | none | - | out: not saved | Market |  |  | read |  |
| `4f4f2a2c` | `Market_Hylia_021_Shop_FlavorTalk_Int` | files | Int | 0 | 9 | progress | 3 | out: Int in no group | Market |  |  | read |  |
| `a9eb4a31` | `Market_Hylia_021_Shop_Talking` | files | Bool | 0 | 9 | none | - | out: not saved | Market |  |  | read |  |
| `4dd067c5` | `Market_IsAfterAssembleTalk` | files | Bool | 0 | 1 | none | - | out: not saved | Market |  |  | read |  |
| `5f5fe121` | `Market_IsAfterGossipTalk` | files | Bool | 0 | 1 | none | - | out: not saved | Market |  |  | read |  |
| `4d62de75` | `Market_Item_Bottle_TutorialEvent_Cleared` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  |  | read |  |
| `90fc9481` | `Market_Item_Bottle_TutorialEvent_Insect_Delete` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  |  | read |  |
| `7390e3ba` | `Market_Item_Bottle_TutorialEvent_LotOfInsect` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  |  | read |  |
| `608908f6` | `Market_Item_Bottle_TutorialEvent_Shop_Bottle_Insect_Appeared` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  |  | read |  |
| `39d7877d` | `Market_Item_Bottle_TutorialEvent_Started` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  |  | read |  |
| `9a3d4dd1` | `Market_MemberAssembled` | files | Bool | 0 | 8 | none | - | out: not saved | Market |  |  | read |  |
| `e50e6e73` | `Market_MiniGame_BombchuBowling_FirstTalk` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  |  | read |  |
| `10e51015` | `Market_MiniGame_ChoiceTreasure_ChoiceNotPlay` | files | Bool | 0 | 11 | progress | 1 | out: temporary | Market |  |  | read |  |
| `b55e263b` | `Market_MiniGame_ChoiceTreasure_FirstTalk` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  |  | read |  |
| `6a65141d` | `Market_MiniGame_ChoiceTreasure_GameOver` | files | Bool | 0 | 10 | progress | 1 | out: temporary | Market |  |  | read |  |
| `ffa59212` | `Market_MiniGame_ChoiceTreasure_HowtoPlay` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  |  | read |  |
| `389f3a2c` | `Market_MiniGame_ChoiceTreasure_MissGame` | files | Bool | 0 | 10 | progress | 1 | out: temporary | Market |  |  | read |  |
| `2963a3cb` | `Market_Minigame_ChoiceTreasure_MissReplayTalk` | files | Bool | 0 | 11 | progress | 1 | out: temporary | Market |  |  | read |  |
| `5248291d` | `Market_MiniGame_ChoiceTreasure_NumOfHit` | files | Int | 0 | 8 | none | - | out: Int in no group | Market |  |  | read |  |
| `db4e01ca` | `Market_Minigame_HitHitTarget_CloseDoor` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  |  | read |  |
| `0a26461a` | `Market_MiniGame_HitTarget_FirstTalk` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  |  | read |  |
| `00a33ee8` | `Market_Minigame_HitTarget_IsTalk` | files | Bool | 0 | 9 | progress | 1 | out: temporary | Market |  |  | read |  |
| `708f4946` | `Market_NandemoShop_FirstTalk` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  |  | read |  |
| `0fd80c00` | `Market_NotEntryArea_WithDog` | files | Bool | 0 | 9 | none | - | out: not saved | Market |  |  | read |  |
| `ff6b6712` | `Market_Npc_Goron_012_Child_HaveTalkdBombchu` | files | Bool | 0 | 8 | none | - | out: not saved | Market |  |  | read |  |
| `78c28019` | `Market_Npc_Hylia_005_Child_ArrivedAction1` | files | Bool | 0 | 8 | none | - | out: not saved | Market |  |  | read |  |
| `2275b365` | `Market_Npc_Hylia_034_Stop` | files | Bool | 0 | 8 | none | - | out: not saved | Market |  |  | read |  |
| `0b7fb9a7` | `Market_Npc_Hylia_034_StopB` | files | Bool | 0 | 8 | none | - | out: not saved | Market |  |  | read |  |
| `98fcca2c` | `Market_Npc_Hylia_041_Child_FirstTalk` | files | Bool | 0 | 8 | none | - | out: not saved | Market |  |  | read |  |
| `2048e781` | `Market_Npc_Hylia_052_Child_AND_Richard_ArrivedHome` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  |  | read |  |
| `1c3654d1` | `Market_Npc_Hylia_052_Child_BringDog` | files | Bool | 0 | 8 | none | - | out: not saved | Market |  |  | read |  |
| `e446fd2f` | `Market_Npc_Hylia_052_Child_BringRichard` | files | Bool | 0 | 8 | none | - | out: not saved | Market |  |  | read |  |
| `3fa4fb51` | `Market_Npc_Hylia_052_Child_DisableInterestDog` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  |  | read |  |
| `d229c5e1` | `Market_Npc_Hylia_052_Child_IsAfterFirstExplain` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  |  | read |  |
| `e88a76f0` | `Market_Npc_Hylia_052_Child_IsArriving` | files | Bool | 0 | 8 | none | - | out: not saved | Market |  |  | read |  |
| `b0bae48f` | `Market_Npc_Hylia_052_Child_IsInHome` | files | Bool | 0 | 8 | none | - | out: not saved | Market |  |  | read |  |
| `36926085` | `Market_Npc_Hylia_052_Child_RichardGoHome` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  |  | read |  |
| `e07c5a44` | `Market_Npc_Hylia_052_Child_RunningRichard` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  |  | read |  |
| `d99b38cb` | `Market_Npc_Hylia_052_Child_SunSongWarp` | files | Bool | 0 | 9 | none | - | out: not saved | Market |  |  | read |  |
| `c29f20ab` | `Market_Npc_Hylia_065_Child_IsCuccoAngry` | files | Bool | 0 | 8 | none | - | out: not saved | Market |  |  | read |  |
| `3050f877` | `Market_Npc_Hylia_065_Child_IsCuccoInFountain` | files | Bool | 0 | 8 | none | - | out: not saved | Market |  |  | read |  |
| `2d6648bb` | `Market_Npc_Hylia_065_Child_IsCuccoLifted` | files | Bool | 0 | 8 | none | - | out: not saved | Market |  |  | read |  |
| `d56734a6` | `Market_Npc_Hylia_066_Child_ArrivedAction1` | files | Bool | 0 | 8 | none | - | out: not saved | Market |  |  | read |  |
| `c22b8080` | `market_Npc_Hylia_Soldier_007_Child_BreakAllPot` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `b31e8a60` | `market_Npc_Hylia_Soldier_007_Child_BreakPot` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `a8c7ba8d` | `Market_Npc_Hylia_Soldier_029_Child_BreakAllPot` | files | Bool | 0 | 8 | none | - | out: not saved | Market |  |  | read |  |
| `f7d64962` | `Market_Npc_Hylia_Soldier_029_Child_BreakPot` | files | Bool | 0 | 8 | none | - | out: not saved | Market |  |  | read |  |
| `475cb1c9` | `Market_OneOfMemberAssembled` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  |  | read |  |
| `38805263` | `Market_Shop_SelectActor_Shield_Hylia` | files | Bool | 0 | 9 | progress | 1 | out: temporary | Market |  |  | read |  |
| `177fa9ad` | `Market_Shop_SelectArrow` | files | Bool | 0 | 9 | none | - | out: not saved | Market |  |  | read |  |
| `34d97e94` | `Market_Shop_SelectBomb` | files | Bool | 0 | 9 | none | - | out: not saved | Market |  |  | read |  |
| `530501cf` | `Market_StreetShop_IgnoreAttentionArea` | files | Bool | 0 | 8 | progress | 1 | progress, shared | Market |  |  | read |  |
| `1a204231` | `Market_SubEvent_FindRichard_MadamSayThankyou` | files | Bool | 0 | 1 | none | - | out: not saved | Market |  |  | read |  |
| `9cfe9836` | `Meet_GreatFairy_01` | files | Bool | 1 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `f8106300` | `Meet_GreatFairy_02` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `3ff29ed3` | `Meet_GreatFairy_03` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `732acbf1` | `Meet_GreatFairy_04` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `be878637` | `Meet_GreatFairy_05` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `2fe03182` | `Meet_GreatFairy_CompleteMessage` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `53c5f0ea` | `Meet_GreatFairy_RemainNumber` | files | Int | 6 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `6ca1922d` | `Meet_Ruto_First` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `37a56b5d` | `MelodyGet_Sun_Flat_GotTalkEventTlakd` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `0a9ff094` | `MelodyGet_Sun_Sharp_GotTalkEventTlakd` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `be4e744f` | `MelodyGet_Time_EndConversationWithZelda` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `9612e656` | `MiniGame_BackMoveCounter_PlayerPosition_Nearby` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `73a1a516` | `MiniGame_BombchBowling_Dead` | files | Bool | 0 | 10 | progress | 1 | out: temporary |  |  |  | read |  |
| `306d4a2d` | `MiniGame_BombchuBowling_BreakIn` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `7e630d00` | `MiniGame_BombchuBowling_Choise_Hardmode` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `19e5a36b` | `MiniGame_BombchuBowling_ClearFirstTime` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `cdd1c1dd` | `MiniGame_BombchuBowling_ClearSecondTime` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `61cf7ba1` | `MiniGame_BombchuBowling_ClearThirdTime` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b1950b93` | `MiniGame_BombchuBowling_CounterSpawnFlag` | files | Bool | 1 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `d83e0660` | `MiniGame_BombchuBowling_CuccoDucking` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `adc6f64a` | `MiniGame_BombchuBowling_Easy` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `80d55d7f` | `MiniGame_BombchuBowling_ExplainRentalItem` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `920aa449` | `MiniGame_BombchuBowling_GimickRegeneration` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `33847c84` | `MiniGame_BombchuBowling_Hard` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `4b8d6ae7` | `MiniGame_BombchuBowling_JustAfterCleared` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `68fb23b1` | `MiniGame_BombchuBowling_Normal` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `a7310628` | `MiniGame_BombchuBowling_Prize` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `06882745` | `MiniGame_BombchuBowling_Progress` | files | Int | 0 | 8 | none | - | out: Int in no group |  |  |  | read |  |
| `2e8d25dd` | `MiniGame_BombchuBowling_Rule` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `4107a984` | `MiniGame_BombchuBowling_SecondTargetType` | files | Int | 0 | 8 | none | - | out: Int in no group |  |  |  | read |  |
| `c318fd31` | `MiniGame_CatchCucco_CuccoLifting` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `b2268e4a` | `MiniGame_CatchCucco_HasCrateAlive` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `32f319f0` | `MiniGame_CatchCucco_HasCuccoBeenMovedFromBrick` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `746f01d1` | `MiniGame_CatchCucco_HoldCoccoBeforeReady` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `79f4e2a8` | `MiniGame_CatchCucco_InFenceCount` | files | Int | 0 | 8 | none | - | out: Int in no group |  |  |  | read |  |
| `7a7961c3` | `MiniGame_CatchCucco_IsCompleted` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `3d28fd44` | `MiniGame_CatchCucco_IsCuccoIntheFence` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `e0c81d76` | `MiniGame_CatchCucco_IsLifting` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `d24adfcf` | `MiniGame_CatchCucco_PlayerInFence` | files | Bool | 0 | 32 | none | - | out: not saved |  |  |  | read |  |
| `f95297c8` | `MiniGame_CatchCucco_PlayerInfrontFence` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `22e4ab2e` | `MiniGame_ChoiceTreasure_GimickRegeneration` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b599aeed` | `MiniGame_ChoiceTreasure_IsClear` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `19163ef6` | `MiniGame_ChoiceTreasure_OpenedEitherBox` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `8d537537` | `MiniGame_ChoiceTreasure_TalkedAboutRules` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `09d50d72` | `MiniGame_DampeRace_BestTime_MilliSecond` | files | Int | 9 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `872eb46d` | `MiniGame_DampeRace_BestTime_Minutes` | files | Int | 9 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `9b6b4b33` | `MiniGame_DampeRace_BestTime_Second` | files | Int | 9 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `a4c6928e` | `MiniGame_DampeRace_ClearCount` | files | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `5a136452` | `MiniGame_DampeRace_Failed_Navi` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `8006b939` | `MiniGame_DampeRace_HeartResultFailTalked` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `f6952a32` | `MiniGame_DampeRace_HeartResultSuccessTalked` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `02ae93da` | `MiniGame_DampeRace_IsAppearTreasureBox` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `d000d5c1` | `MiniGame_DampeRace_IsClosedShutterInFrontGoal` | files | Bool | 1 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `09e9a8dc` | `MiniGame_DampeRace_NoRetry` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `727a8d1f` | `MiniGame_DampeRace_TalkAfterRaceWithD` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `30071ce0` | `MiniGame_DampeRace_TreasureBoxOpened` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `16e3c1cb` | `MiniGame_DiggingHole_DigFromTalk` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `21d9112d` | `MiniGame_DiggingHole_MinigameIconOn` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `cd0fedb9` | `MiniGame_DiggingHole_SetDoPlate` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `697507aa` | `MiniGame_Diving_Cleared` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `f4b5d6d2` | `MiniGame_Diving_Dead` | files | Bool | 0 | 10 | progress | 1 | out: temporary |  |  |  | read |  |
| `fa19d17d` | `MiniGame_Diving_Hard` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `af78f27c` | `MiniGame_Diving_IsNearWater` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `c304cacf` | `MiniGame_Diving_IsNearWaterFall` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `e236a01f` | `MiniGame_Diving_LimitDoArea` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `883165d1` | `MiniGame_Diving_Mapicon` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `e4747bbf` | `MiniGame_Diving_Navi_Failure` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `6fe25425` | `MiniGame_Diving_Normal` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `3c858942` | `MiniGame_Diving_PlayerWatch` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `21f90ccd` | `MiniGame_Diving_Playing` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `4147bf54` | `MiniGame_Diving_ShilverScale_First` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `db0ef4b8` | `Minigame_FindOutCucco_Counter` | files | Int | 0 | 8 | none | - | out: Int in no group |  |  |  | read |  |
| `5eea50a1` | `Minigame_FindOutCucco_Counter_Navi` | files | Int | 0 | 8 | none | - | out: Int in no group |  |  |  | read |  |
| `cc225a1e` | `MiniGame_FindOutCucco_GameOver` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `a0a80a40` | `Minigame_FindOutCucco_HasPlayed_Navi` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `77868f1c` | `MiniGame_FindOutCucco_ListenPlayGuide` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `52757680` | `MiniGame_FindOutCucco_PlayerInside` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `53f00df6` | `Minigame_FindOutCucco_WalkLoopCount` | files | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `b5be69c4` | `MiniGame_Fishing_Adult_IsFirstTalked` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `9180a890` | `MiniGame_Fishing_AfterFinishFishing` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `119f2862` | `MiniGame_Fishing_AfterGameOver` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `c713df14` | `MiniGame_Fishing_AfterTalkAboutHat` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `0a254068` | `MiniGame_Fishing_AfterUpdateRecord` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `8763293c` | `MiniGame_Fishing_CancelTutorialByTakeHat` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `ba221642` | `MiniGame_Fishing_CanRainyTalk` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `01c17f3b` | `MiniGame_Fishing_CatchFishSize` | files | Int | 0 | 8 | none | - | out: Int in no group |  |  |  | read |  |
| `e5a801eb` | `MiniGame_Fishing_CompletedTutorial` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `2079723b` | `MiniGame_Fishing_GetGoldScale` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `f1891f6e` | `MiniGame_Fishing_GetHeartPiece` | files | Bool | 0 | 8 | progress | 1 | out: heart reward |  |  | Heart-piece reward flag from the fishing minigame; co-op keeps heart rewards each player's own (a shared count would pay twice). | read | LS oot_coop.c |
| `7b12e40a` | `MiniGame_Fishing_GoOutPondAndIn` | files | Bool | 1 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `3beb5d70` | `MiniGame_Fishing_HaveTalkedChild` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b4ff17a3` | `MiniGame_Fishing_HaveTalkedFishingFailure_Adult` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `9468bf7a` | `MiniGame_Fishing_HaveTalkedFishingFailure_Child` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b56f6785` | `MiniGame_Fishing_HaveTalkedHookingFailure_Adult` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `113dade5` | `MiniGame_Fishing_HaveTalkedHookingFailure_Child` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `71a5455d` | `MiniGame_Fishing_HintSinkLure_AtEnd` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `e8e18ba0` | `MiniGame_Fishing_HintSinkLure_AtStart` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `97e40667` | `MiniGame_Fishing_IgnoreBalloonRequest` | files | Bool | 0 | 25 | progress | 1 | out: temporary |  |  |  | read |  |
| `ca606d1b` | `MiniGame_Fishing_In_AttentionDisableArea` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `b690db7a` | `MiniGame_Fishing_IsAccessDoor` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `7da2c34b` | `MiniGame_Fishing_IsActiveTutorial` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `7f65cfe4` | `MiniGame_Fishing_IsAfterTalkNearLure` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `616b6ebc` | `MiniGame_Fishing_IsAfterTalkNearLureNoHat` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `6be780c9` | `MiniGame_Fishing_IsCatchLoach` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `63cf2999` | `MiniGame_Fishing_IsDawnOrDusk` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `a439ff91` | `MiniGame_Fishing_IsFeverTime` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `e18e9f43` | `MiniGame_Fishing_isInCorner` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b36c50c8` | `MiniGame_Fishing_IsLPlayerInRoom` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `76198bc6` | `MiniGame_Fishing_IsLureDropInNoFishWater` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `ee508f3e` | `MiniGame_Fishing_IsLureDropInRoom` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `652d2af1` | `MiniGame_Fishing_IsLureDropNearFishman` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `35d4378f` | `MiniGame_Fishing_IsPlayInSouthWest` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `ceda0836` | `MiniGame_Fishing_IsRevenged` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `8407216e` | `Minigame_Fishing_IsUseSinkingLureTalk` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `420efba2` | `MiniGame_Fishing_KeepFish` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `782dfadc` | `MiniGame_Fishing_KeepFishSize` | files | Int | 0 | 8 | none | - | out: Int in no group |  |  |  | read |  |
| `6b8acce1` | `MiniGame_Fishing_KeepLoach` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b43df1a5` | `MiniGame_Fishing_MeetAgain` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `8df9cc1c` | `MiniGame_Fishing_NotYetHearSinkLureHintAtStart` | files | Bool | 1 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `196a1821` | `MiniGame_Fishing_OnceCatchFish` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `dd06672b` | `MiniGame_Fishing_OncePlayed` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `719de7ed` | `MiniGame_Fishing_OncePlayed_Child` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `d81f129e` | `MiniGame_Fishing_OnceUpdateRecord` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `f83d71ec` | `MiniGame_Fishing_OnceUpdateRecord_Adult` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `20113cb0` | `MiniGame_Fishing_PlayCount` | files | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `400ee935` | `MiniGame_Fishing_PlayCountUntileRainy` | files | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `d2e2adff` | `MiniGame_Fishing_Rainy` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `c0363f2e` | `MiniGame_Fishing_RecomendedPlaying` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `e1420c94` | `MiniGame_Fishing_RecordFishSize_Adult` | files | Int | 45 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `88c51151` | `MiniGame_Fishing_RecordFishSize_Child` | files | Int | 40 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `4a0941ee` | `MiniGame_Fishing_RecordWithSinkingLure_Adult` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `ae291698` | `MiniGame_Fishing_RecordWithSinkingLure_Child` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b9932b24` | `MiniGame_Fishing_ShowedTutorial_Interested` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `c506c1af` | `MiniGame_Fishing_ShowFishingTipsChoice` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `e695a20e` | `Minigame_Fishing_SinkingLure_IsConfiscated` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `ca226ec4` | `MiniGame_Fishing_SpawnedLoach` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `133620e3` | `MiniGame_Fishing_TalkedBeforeClearWaterTemple` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b84137b9` | `MiniGame_Fishing_TalkedFishingTips` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `49a4d15d` | `MiniGame_Fishing_TalkedHowToPlay` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `81351b39` | `MiniGame_Fishing_TalkedInRainy` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `08274826` | `MiniGame_Fishing_TalkedInRainy_TalkedBeforeClearWaterTemple` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `c5080130` | `MiniGame_Fishing_TalkedInRainyInCurrentPlay` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `fc8de335` | `MiniGame_Fishing_TalkedTutorial_Battle` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `896f8183` | `MiniGame_Fishing_TalkedTutorial_Chance` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `710e8a8b` | `MiniGame_Fishing_TalkedTutorial_Hooking` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `cd57f531` | `MiniGame_Fishing_Temporarily_AIScheduleReset` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `f8276a23` | `Minigame_Fishing_Tutorial_IsCaughtFishTalk` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `6c0072a6` | `MiniGame_Fishing_Tutorial_IsCleared` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `ba6c00e0` | `MiniGame_Fishing_Tutorial_IsFirstExplanation` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `587591de` | `MiniGame_Fishing_Tutorial_IsFirstInterestTalk` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `6fe1dbc1` | `MiniGame_Fishing_Tutorial_IsFirstRetrieveTalk` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `63e2897c` | `MiniGame_Fishing_Tutorial_LureOnGround` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `255acfbe` | `MiniGame_Fishing_TutorialInterrupted` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `e8e43190` | `MiniGame_Fishing_UseSinkingLure` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `ec2dba47` | `MiniGame_Fishing_WaitTutorial_Chance` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `5045547c` | `MiniGame_Fising_AfterGameOverAngry` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `614e578f` | `MiniGame_FrogTenors_AfterSongClear` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `54f29f99` | `MiniGame_FrogTenors_BeOnStage` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `8d068302` | `MiniGame_FrogTenors_EponaSong` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `6a6486eb` | `MiniGame_FrogTenors_GetCount` | files | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `8ffec767` | `MiniGame_FrogTenors_InsectRepellent` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `3adbd558` | `MiniGame_FrogTenors_InsectRepellent_ClearAfter` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b4339d09` | `MiniGame_FrogTenors_InsectRepellent_Clearnumber` | files | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `02ed661d` | `MiniGame_FrogTenors_InsectRepellent_Explanation` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `45a48103` | `MiniGame_FrogTenors_Navi_Failed` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `88b7b45b` | `MiniGame_FrogTenors_Navi_NewSong` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `08b45c5c` | `MiniGame_FrogTenors_Navi_Success` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `f6b5b932` | `MiniGame_FrogTenors_OneSongClear` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `16451868` | `MiniGame_FrogTenors_Playing` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `f675a0f2` | `MiniGame_FrogTenors_SariaSong` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `c69d8bbf` | `MiniGame_FrogTenors_SongClear` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `d578df95` | `MiniGame_FrogTenors_StormSong` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `61305ed4` | `MiniGame_FrogTenors_SunSong` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `cc4216b9` | `MiniGame_FrogTenors_TimeSong` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `6e3948e7` | `MiniGame_FrogTenors_ZeldaLullaby` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `1e9e1b91` | `MiniGame_HitTarget_BestScore` | files | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `9e06ed48` | `MiniGame_HitTarget_ExplainRentalItem` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b5f62c9b` | `MiniGame_HitTarget_HrlCity_ColdShoulder` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `a113c16c` | `MiniGame_HitTarget_HrlCity_FirstTimeClear` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `893fa7cb` | `MiniGame_HitTarget_HrlCity_Get_BulletBag` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `8f1ef00d` | `MiniGame_HitTarget_HrlCity_HitParsonOutGame` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `84ce822b` | `MiniGame_HitTarget_HrlCity_HitPerson` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `6874676c` | `MiniGame_HitTarget_HrlCity_NeverPlayed` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `941ff1f3` | `MiniGame_HitTarget_HrlCity_NewScore` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `24d3d904` | `MiniGame_HitTarget_HrlCity_NoMoney` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `84d0b3e2` | `MiniGame_HitTarget_HrlCity_OutShop` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `03ee62dc` | `MiniGame_HitTarget_HrlCity_TalkedAboutRules` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `321d7a81` | `MiniGame_HitTarget_IsAskedFinishBecauseOfZeroRemain` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `f1c21e3b` | `MiniGame_HitTarget_IsHardMode` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `380d4337` | `MiniGame_HitTarget_Kakariko_BestScore` | files | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `b57344b9` | `MiniGame_HitTarget_Kakariko_FirstTimeClear` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `dda8aaf7` | `MiniGame_HitTarget_Kakariko_Get_Quiver` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `f0c9fb29` | `MiniGame_HitTarget_Kakariko_NewScore` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `abc204bb` | `MiniGame_HitTarget_NoAttentionArea_On` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `b2a8bf4d` | `MiniGame_HitTarget_SulkyBefore` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `0cc6487f` | `MiniGame_HorseBackArcher_HaveTalkedAboutBow` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `d07e7738` | `MiniGame_HorseBackArcher_HaveTalkedAboutHorse` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `65a22427` | `MiniGame_HorseBackArcher_HaveTalkedAboutRentalHorse` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `f6da57d6` | `MiniGame_HorsebackArchery_BestScore` | files | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `e30b8022` | `MiniGame_HorsebackArchery_Establishing` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `4274ab3d` | `MiniGame_HorsebackArchery_ExplainRentalItem` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `7c6e3b6b` | `MiniGame_HorseBackArchery_Get_Quiver` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `3f43245b` | `MiniGame_HorsebackArchery_GotaHeart` | files | Bool | 0 | 8 | progress | 1 | out: heart reward |  |  | Heart-piece reward flag from the horseback archery minigame; co-op keeps heart rewards each player's own (a shared count would pay twice). | read | LS oot_coop.c |
| `d4b333f9` | `MiniGame_HorsebackArchery_Introduction` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `46e5bc53` | `MiniGame_HorsebackArchery_ISGetSpecialPrize` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `08c9aff3` | `MiniGame_HorsebackArchery_MapIcon_Flag` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `efd34ff6` | `MiniGame_HorsebackArchery_NewScore` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `4b11b9c4` | `MiniGame_HorsebackArchery_Played` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `a80196fc` | `MiniGame_HorsebackArchery_Progress` | files | Int | 0 | 8 | none | - | out: Int in no group |  |  |  | read |  |
| `625aeaae` | `MiniGame_HorsebackArchery_Retry` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `2960fefa` | `MiniGame_HorseRace_Around1stLap` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `a0b91e51` | `MiniGame_HorseRace_BestTime_MiliSecond` | files | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `1036e0df` | `MiniGame_HorseRace_BestTime_Minutes` | files | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `786b7095` | `MiniGame_HorseRace_BestTime_Second` | files | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `e14535ef` | `MiniGame_HorseRace_CheckPoint1` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `dbddbca5` | `MiniGame_HorseRace_CheckPoint2` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `66e1c34d` | `MiniGame_HorseRace_CheckPoint3` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `b5e8e8b7` | `MiniGame_HorseRace_Establishing` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `2602c10f` | `MiniGame_HorseRace_FirstTalkToMalon` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `38f61c8a` | `MiniGame_HorseRace_Goaled` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `feddfe4c` | `MiniGame_HorseRace_GoalRailPointIndex` | files | Int | 0 | 8 | none | - | out: Int in no group |  |  |  | read |  |
| `6176590f` | `MiniGame_HorseRace_IsNearEpona` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `a3f0a3c6` | `MiniGame_HorseRace_IsNewRecord` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  | Set by the horse race flows when a new record is made; an unridable air wall stands while it is true. | read | world model |
| `1dfa3bd1` | `MiniGame_HorseRace_IsRoundOne` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b9f81e33` | `MiniGame_HorseRace_LimitDoArea` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `07c55776` | `Minigame_HorseRace_MalonSayStart` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `6c25dcd9` | `MiniGame_HorseRace_Navi_Failed` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `97b87382` | `MiniGame_HorseRace_Navi_NewRecord` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `f68d9e33` | `MiniGame_HorseRace_PenaltyCount` | files | Int | 0 | 8 | none | - | out: Int in no group |  |  |  | read |  |
| `08005e3a` | `MiniGame_HorseRace_ProgressRound` | files | Int | 0 | 8 | none | - | out: Int in no group |  |  |  | read |  |
| `ff4bc2fd` | `MiniGame_HorseRace_Result_MiliSecond` | files | Int | 0 | 8 | none | - | out: Int in no group |  |  |  | read |  |
| `b6e46c9d` | `MiniGame_HorseRace_Result_Minutes` | files | Int | 0 | 8 | none | - | out: Int in no group |  |  |  | read |  |
| `f234135a` | `MiniGame_HorseRace_Result_Second` | files | Int | 0 | 8 | none | - | out: Int in no group |  |  |  | read |  |
| `54f91f97` | `MiniGame_HorseRace_Timeup` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `8684d2ea` | `MiniGame_HorseRace_UpdateBestTime` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `720a9e51` | `MiniGame_HorseRace_WrongWay` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `dd49184a` | `MiniGame_IsTimerCountDown` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `f0312188` | `MiniGame_IsTimerCounting` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `3340e10c` | `MiniGame_Score` | files | Int | 0 | 9 | none | - | out: Int in no group |  |  |  | read |  |
| `9075c015` | `MiniGame_Score_ForMessage` | files | Int | 0 | 9 | none | - | out: Int in no group |  |  |  | read |  |
| `64e3083b` | `MiniGame_ScoreMax` | files | Int | 0 | 9 | none | - | out: Int in no group |  |  |  | read |  |
| `9136751c` | `MiniGame_SequentialChoiceTreasure_Navi_IsAbort` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `e2af4392` | `Minigame_SkullKidSession_CurrentGradeSoundNumForSession` | files | Int | 5 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `fe153e69` | `Minigame_SkullKidSession_CurrentRallyCount` | files | Int | 1 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `9b5f6f52` | `Minigame_SkullKidSession_Delete` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `81b0ed2a` | `Minigame_SkullKidSession_HasFailed` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `76f1c783` | `MiniGame_SkullKidSession_IsAttackHit` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `1657d7d8` | `Minigame_SkullKidSession_IsGetHeartPiece` | files | Bool | 0 | 8 | progress | 1 | out: heart reward |  |  | Heart-piece reward flag from the Skull Kid's playing session; co-op keeps heart rewards each player's own (a shared count would pay twice). | read | LS oot_coop.c |
| `0dc0c88d` | `MiniGame_SkullKidSession_IsPlayingEvent` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `e22ff326` | `Minigame_SkullKidSession_MaxRallyCount` | files | Int | 3 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `9ec51bb7` | `Minigame_SkullKidSession_OnCenter` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `7f723f0e` | `Minigame_SkullKidSession_OnPoint` | files | Bool | 1 | 8 | none | - | out: not saved |  |  |  | read |  |
| `6c2634e1` | `MiniGame_SkullKidSession_PlaySkullKid` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `e45fac21` | `MiniGame_SmallKeyNum` | files | Int | 0 | 8 | none | - | out: Int in no group |  |  |  | read |  |
| `8389eb42` | `MiniGame_SpawnSinkLure` | files | Bool | 1 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `4269b3f2` | `MiniGame_TimerMilliSecond` | files | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `457fdd51` | `MiniGame_TimerMinute` | files | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `ed482220` | `MiniGame_TimerSecond` | files | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `2eb80116` | `MiniGame_Unlock_FindOutCucco` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `699df6b8` | `MiniGame_Unlock_GambleRace` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `fcb945b8` | `MiniGame_Unlock_HorseRace` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `3a55a53a` | `MinigGame_HorseRace_Permission` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `cbcb98fc` | `Morpha_DeleteWater` | source comment | Bool | 0 | 8 | progress | 1 | progress, shared | MorphaStage |  | Proof of Morpha's defeat: the flag that deletes his water, set by the end of the fight. Co-op holds it back and writes the boss's end set once every proof is here. | read | LS oot_coop.c |
| `f8f0a74c` | `MountainTrail_Adult_DropFirstFallingRock` | files | Bool | 0 | 8 | progress | 1 | progress, shared | DeathMountainTrail |  |  | read |  |
| `b63c6352` | `MountainTrail_AdultFallingRockDemoActivated` | files | Bool | 0 | 8 | progress | 1 | progress, shared | DeathMountainTrail |  |  | read |  |
| `b1ee4925` | `MountainTrail_AdultFallingRockDemoEnded` | files | Bool | 0 | 8 | progress | 1 | progress, shared | DeathMountainTrail |  |  | read |  |
| `2e7c6270` | `MountainTrail_ArriveFromDodongoCavern` | files | Bool | 0 | 8 | progress | 1 | progress, shared | DeathMountainTrail |  |  | read |  |
| `d1130b6e` | `MountainTrail_ArriveFromGoronCity` | files | Bool | 0 | 8 | progress | 1 | progress, shared | DeathMountainTrail |  |  | read |  |
| `f6d2d40b` | `MountainTrail_ArriveFromKakarikoVillage` | files | Bool | 1 | 8 | progress | 1 | progress, shared | DeathMountainTrail |  |  | read |  |
| `a31de6ca` | `MountainTrail_ArriveFromMountainCrater` | files | Bool | 0 | 8 | progress | 1 | progress, shared | DeathMountainTrail |  |  | read |  |
| `3d392072` | `MountainTrail_Child_DropFirstFallingRock` | files | Bool | 0 | 8 | progress | 1 | progress, shared | DeathMountainTrail |  |  | read |  |
| `dd7eb97e` | `MountainTrail_Child_PlayerIsInLargeRockDemo` | files | Bool | 0 | 8 | progress | 1 | progress, shared | DeathMountainTrail |  |  | read |  |
| `25a66234` | `MountainTrail_Child_PlayerLeftFallingRockArea` | files | Bool | 0 | 9 | progress | 1 | out: temporary | DeathMountainTrail |  |  | read |  |
| `0bb59c67` | `MountainTrail_ChildFallingRockDemoActivated` | files | Bool | 0 | 8 | progress | 1 | progress, shared | DeathMountainTrail |  |  | read |  |
| `82935a4b` | `MountainTrail_FairyRockBreak` | files | Bool | 0 | 8 | progress | 1 | progress, shared | DeathMountainTrail |  |  | read |  |
| `70493c09` | `MountainTrail_Goron009_BombHitTalk` | files | Bool | 0 | 1 | none | - | out: not saved | DeathMountainTrail |  |  | read |  |
| `18964061` | `MountainTrail_HasReachedPeak_Adult` | files | Bool | 0 | 8 | progress | 1 | progress, shared | DeathMountainTrail |  |  | read |  |
| `53d6140f` | `MountainTrail_HasReachedPeak_Child` | files | Bool | 0 | 8 | progress | 1 | progress, shared | DeathMountainTrail |  |  | read |  |
| `2aaa0d03` | `MountainTrail_isInsideFallingRockArea` | files | Bool | 0 | 8 | progress | 1 | progress, shared | DeathMountainTrail |  |  | read |  |
| `cf0017b1` | `Navi_Ban` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `e3e7d5f2` | `Navi_Chat_Attention_Kokiri113` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `204135e0` | `NaviAttention_Ganon` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `9feeb014` | `NaviAttentionBalloon_Obj_AttentionRock_A_01` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `365a584f` | `NaviChat_BottomOfTheWater_With_HeavyBoot` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `797c5b4d` | `NaviChat_Cancel_HorseRaceClear` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `fbc52596` | `NaviChat_Env_InSandStome` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `00b7ee18` | `NaviChat_Gerudo_2214_Talked` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `f314ebaf` | `NaviChat_HyruleCastle_FoundBySecurity` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `2a051d4b` | `NaviChat_Invalid_WaterDamage` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `5dd16bbe` | `NaviChat_IsArrived_LakeHylia_Adult` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `5971bd91` | `NaviChat_Kakariko_2106_Talked` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `18ddd695` | `NaviChat_Market_1701_Talked` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `82a3b6e7` | `NaviChat_MaxRupee_Displayed` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `272abe36` | `NaviChat_Reaction_Index` | files | Int | 0 | 9 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `177d58d6` | `NaviChat_Serious_Time` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `36edfe58` | `NaviHelp_BottomOfTheWell_Room01_Entrance` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `a2f86155` | `NaviHelp_Dungeon_Read` | names file | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `fec0ff26` | `NaviHelp_SageOfForest_Step02_1` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `ac382cee` | `NaviHelp_SageOfForest_Step02_2` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `f43da9d6` | `NaviHelp_ShadowTemple_17_A_01` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `425a85b1` | `NaviHint_Disp_FieldHint_01` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `01a3e450` | `NaviHint_DungeonBoss_Dodongo_FirstTime_HasRead` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `27a6d5ce` | `NaviHint_DungeonBoss_Ganon_FirstTime_HasRead` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `0cac9dec` | `NaviHint_DungeonBoss_Ganon_SecondHalfBattle_EvilEye_HasRead` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `6084fa6a` | `NaviHint_DungeonBoss_Ganon_SecondHalfBattle_Finish_HasRead` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `e8d8f752` | `NaviHint_DungeonBoss_Ganon_SecondHalfBattle_FirstTime_HasRead` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `2f1a27e3` | `NaviHint_DungeonBoss_Ganon_SecondHalfBattle_Invincible_HasRead` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `186b11b4` | `NaviHint_Enemy_Amos_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `716c9498` | `NaviHint_Enemy_Anubis_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `e1d1325c` | `NaviHint_Enemy_BabyDodongo_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `ab611736` | `NaviHint_Enemy_Bari_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `09487ba2` | `NaviHint_Enemy_Barinade_FirstTime_HasRead` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `a6d62f12` | `NaviHint_Enemy_Beamos_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `e6d353c6` | `NaviHint_Enemy_BigOcto_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `dd8d78f9` | `NaviHint_Enemy_Biri_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `3d5289ea` | `NaviHint_Enemy_BongoBongo_FirstTime_HasRead` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `bf154001` | `NaviHint_Enemy_Bubble_Blue_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `8f15a555` | `NaviHint_Enemy_Bubble_Green_Big_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `0748e8b7` | `NaviHint_Enemy_Bubble_Green_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `993f4e45` | `NaviHint_Enemy_Bubble_Red_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `0932be2d` | `NaviHint_Enemy_Bubble_White_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `97dfaf69` | `NaviHint_Enemy_CrazyFloorTile_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `097bf520` | `NaviHint_Enemy_DarkLink_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `10311394` | `NaviHint_Enemy_DeadHand_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `86c4d877` | `NaviHint_Enemy_Dekubaba_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `e2cf8945` | `NaviHint_Enemy_DekubabaWithered_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `89abeffe` | `NaviHint_Enemy_Dinolfos_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `4d0bea61` | `NaviHint_Enemy_Dodongo_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `17a21e34` | `NaviHint_Enemy_Dodongo_SpawnBabyDodongo_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `e7aebd03` | `NaviHint_Enemy_DungeonBoss_PhantomGanon_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `b7a787ca` | `NaviHint_Enemy_FireKeese_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `9fcacd99` | `NaviHint_Enemy_FlareDancer_FireBody_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `b77ae93f` | `NaviHint_Enemy_FlareDancer_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `749c80c9` | `NaviHint_Enemy_Floormaster_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `ef6a92ae` | `NaviHint_Enemy_Floormaster_Little_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `10916b0b` | `NaviHint_Enemy_FlyingPot_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `31acb00a` | `NaviHint_Enemy_Freezard_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `8236d78b` | `NaviHint_Enemy_GerudoThief_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `206185c2` | `NaviHint_Enemy_Gibdo_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `2e43010d` | `NaviHint_Enemy_Gohma_FirstTime_HasRead` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `f76bca68` | `NaviHint_Enemy_GohmaEgg_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `1e30daf1` | `NaviHint_Enemy_GohmaLarva_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `2a579327` | `NaviHint_Enemy_Guay_Boss_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `b2716dca` | `NaviHint_Enemy_Guay_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `9fb9841c` | `NaviHint_Enemy_Guay_Flock_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `d10c80d1` | `NaviHint_Enemy_IronKnuckle_Nabooru_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `7cc39bd5` | `NaviHint_Enemy_IronKnuckle_Silver_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `565451c8` | `NaviHint_Enemy_Keese_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `17361c40` | `NaviHint_Enemy_Keese_Ice_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `5076ba5d` | `NaviHint_Enemy_Kotake_FirstTime_HasRead` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `d383e119` | `NaviHint_Enemy_Koume_FirstTime_HasRead` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `cab6d61d` | `NaviHint_Enemy_Leever_Big_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `051a1cc4` | `NaviHint_Enemy_Leever_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `eae74878` | `NaviHint_Enemy_LikeLike_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `ada95dfe` | `NaviHint_Enemy_Lizalfos_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `0ee01930` | `NaviHint_Enemy_MiddleBoss_Poe_Meg_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `09fedb66` | `NaviHint_Enemy_Moblin_Club_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `7de20d33` | `NaviHint_Enemy_Moblin_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `6853fe40` | `NaviHint_Enemy_Morpha_FirstTime_HasRead` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `29ea9a79` | `NaviHint_Enemy_NoAttention` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `93fe99e0` | `NaviHint_Enemy_NotAppear` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `5b027fa6` | `NaviHint_Enemy_Octorok_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `f38b34d3` | `NaviHint_Enemy_Peahat_AircraftCarrier_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `3992cb2a` | `NaviHint_Enemy_Peahat_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `efeca51d` | `NaviHint_Enemy_Peahat_Larva_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `1a66a28a` | `NaviHint_Enemy_Poe_Amy_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `56830809` | `NaviHint_Enemy_Poe_Beth_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `45bd0439` | `NaviHint_Enemy_Poe_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `07ae7117` | `NaviHint_Enemy_Poe_Flat_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `6d1574b9` | `NaviHint_Enemy_Poe_Hyrule_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `46f17490` | `NaviHint_Enemy_Poe_Joelle_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `41acae1c` | `NaviHint_Enemy_Poe_Sharp_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `2c482a37` | `NaviHint_Enemy_ReDead_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `1cb78550` | `NaviHint_Enemy_Scrub_Business_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `56115d45` | `NaviHint_Enemy_Scrub_Mad_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `516387e6` | `NaviHint_Enemy_ScrubBrothers_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `09f1f681` | `NaviHint_Enemy_ScrubBrothers_FirstTime_HasRead_02` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `a00f7b43` | `NaviHint_Enemy_ScrubBrothers_FirstTime_HasRead_03` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `ca4e2cdf` | `NaviHint_Enemy_ScrubDeku_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `ecefc051` | `NaviHint_Enemy_Shabom_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `2eb156bd` | `NaviHint_Enemy_ShellBlade_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `545011ca` | `NaviHint_Enemy_SkullKid_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `ae83a316` | `NaviHint_Enemy_Skulltula_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `d443354f` | `NaviHint_Enemy_Skullwalltula_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `9d4b655b` | `NaviHint_Enemy_Spike_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `aa55d1c4` | `NaviHint_Enemy_Stalchild_Big_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `3178df5c` | `NaviHint_Enemy_Stalchild_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `c185a868` | `NaviHint_Enemy_Stalfos_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `e4f9e2ca` | `NaviHint_Enemy_Stinger_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `74f6a16d` | `NaviHint_Enemy_Stinger_UnderWater_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `6324a6f3` | `NaviHint_Enemy_Tailpasaran_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `0580cc9f` | `NaviHint_Enemy_Tektite_Blue_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `dc69525a` | `NaviHint_Enemy_Tektite_Red_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `e0b2e067` | `NaviHint_Enemy_Tentacle_Red_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `1b7f5c09` | `NaviHint_Enemy_TorchSlug_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `b3c8c24a` | `NaviHint_Enemy_Twinrova_FirstTime_HasRead` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `5b60a30a` | `NaviHint_Enemy_Volvagia_FirstTime_HasRead` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `9783c4d4` | `NaviHint_Enemy_Wallmaster_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `c8112cd6` | `NaviHint_Enemy_Wolfos_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `656bef4b` | `NaviHint_Enemy_Wolfos_White_FirstTime_HasRead` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `82e49fdb` | `NaviHint_Field_ShieldGuide_Now` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `79843ac9` | `NaviHint_Shield_Hylian_PlayedEventFlow` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `18f2fd41` | `NaviLakeFrozen_LakeTalkFinished` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `14133d56` | `NaviLiftRockCorrectedPos` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `da72cc21` | `NaviRepeat_Minigame_DampeRace_End` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `9f026be6` | `Npc_DekuTreeChild_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `7fe0addf` | `Npc_Dream_BossRush_Cleared` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `342c1141` | `Npc_Dream_BossRush_Cleared_01` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b0e8bd12` | `Npc_Dream_BossRush_Cleared_02` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b4cd5bf3` | `Npc_Dream_BossRush_First` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `0e370313` | `Npc_Dream_FirstTalk_Rematch` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `5d6c15df` | `Npc_Gerudo_002_Child_First` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `147324bc` | `Npc_Gerudo_003_Terror_IgnoreCowAttention` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `e7e16f39` | `Npc_Gerudo_004_TerrorReceived` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b963c3c0` | `Npc_Gerudo_005_WatchArchery_atFortress` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `23be1d6b` | `Npc_Gerudo_Nabooru_FlavorTalk_Int` | files | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `364ca911` | `Npc_Goron_001_Adult_FireTemple_Delete` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `963cce38` | `Npc_Goron_001_Delete` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `023e190f` | `Npc_Goron_001_ShutterisOpen` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `3258d00e` | `NPC_Goron_001_TalkAboutBrakeRock` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `82f96c80` | `Npc_Goron_002_Adult_FireTemple_Delete` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `9c059cb2` | `Npc_Goron_002_Child_ChoiceAgain` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `ff795385` | `Npc_Goron_002_Child_StoneOfFire_FirstTalk` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `7defc137` | `Npc_Goron_002_Delete` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `4e4c04bb` | `Npc_Goron_002_RedStone` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `7b118b57` | `Npc_Goron_002_ShutterisOpen` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `483f6db0` | `Npc_Goron_003_Adult_FireTemple_Delete` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `84236906` | `Npc_Goron_003_Child_ChoiceAgain_1` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `6b99d34a` | `Npc_Goron_003_Child_ChoiceAgain_2` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `72a843b9` | `Npc_Goron_003_Child_EventFlowTerminate` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `1e5efca0` | `Npc_Goron_003_Child_NearControl` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `453a0d7e` | `Npc_Goron_003_Delete` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `92cb9a2f` | `Npc_Goron_003_ShutterisOpen` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `dd85b926` | `Npc_Goron_004_Adult_FireTemple_Delete` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `4631d402` | `Npc_Goron_004_Delete` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `37362da5` | `Npc_Goron_004_PotBroken_AfterDodongoClear` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `f47dc213` | `Npc_Goron_004_PotBroken_BeforeDodongoClear` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `78d64599` | `Npc_Goron_004_PotBroken_HavePlayed_DekuStick_Near` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `175a7c64` | `Npc_Goron_004_PotBroken_HavePlayed_Pot_Near` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `61b1a755` | `Npc_Goron_004_ShutterisOpen` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `7dd185ea` | `Npc_Goron_005_Adult_FireTemple_Delete` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `5984f34c` | `Npc_Goron_005_Delete` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `4609c863` | `Npc_Goron_005_DontReactToZeldaLullaby` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `72ff8447` | `Npc_Goron_005_ShutterisOpen` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b7a66322` | `Npc_Goron_006_BreakSignBoradTalk` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `7c10cdd6` | `Npc_Goron_006_Child_NearWallPlayer` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `4c7b00b0` | `Npc_Goron_006_Child_PlayerOffsetNum` | files | Int | 0 | 8 | none | - | out: Int in no group |  |  |  | read |  |
| `8cb3fdb7` | `Npc_Goron_007_Adult_FireTemple_Delete` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `a5207b77` | `Npc_Goron_007_Delete` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `64b71b86` | `Npc_Goron_007_HaveTalked_DodongoCave` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `626ba2f4` | `Npc_Goron_007_HaveTalked_DodongoCaveOpen` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `366e9ddd` | `Npc_Goron_007_HaveTalkedAboutGoro` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `498a4cd5` | `Npc_Goron_007_HaveTalkedBefore` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `3599b45a` | `NPC_Goron_007_HaveTalkedGoronCity` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `9fd77d79` | `Npc_Goron_007_NoMaskTalk` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `69aeba66` | `Npc_Goron_007_ShutterisOpen` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `05f23212` | `Npc_Goron_008_Adult_FireTemple_Delete` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `0f931260` | `NPC_Goron_008_Child_HaveTalkedAboutBigFairy` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `7c6a945f` | `Npc_Goron_008_Delete` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `4d0e9191` | `NPC_Goron_008_HaveAsked_FallingRock` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `324f8187` | `Npc_Goron_008_HaveAskedGreatFairy` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `ac8c4c8a` | `Npc_Goron_008_HaveTalkedBefore` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `d6a8c454` | `Npc_Goron_008_ShutterisOpen` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `a3b2eb1c` | `Npc_Goron_009_Adult_FireTemple_Delete` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `0fa4811b` | `Npc_Goron_009_Delete` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `3fa18925` | `Npc_Goron_009_HaveTalked_DodongoCaveOpen` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `baafb458` | `Npc_Goron_009_HaveTalkedStop` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `1d5d75c3` | `Npc_Goron_009_ShutterisOpen` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `a4e7353f` | `Npc_Goron_010_Adult_FireTemple_Delete` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `198ed17e` | `Npc_Goron_010_Child_CaveOpen` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `f91c4900` | `Npc_Goron_010_Child_ChoiceCave` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `3dff9954` | `Npc_Goron_010_Child_ChoiceFlower` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `a9335f58` | `Npc_Goron_010_Child_ChoiceGauntlet` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `1f1c15a2` | `Npc_Goron_010_Child_FirstTalk` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `96c6f7f0` | `Npc_Goron_010_Child_PlayedHello` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `20dc1f8a` | `Npc_Goron_010_Delete` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `6948b592` | `Npc_Goron_010_ShutterisOpen` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `f7f9c9cc` | `Npc_Goron_011_Shop_Adult_GlassTruth` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `da89f4d2` | `Npc_Goron_011_Shop_Adult_StopSurprise` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `4e35b33e` | `Npc_Goron_011_Shop_Adult_Surprise` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `516b11d2` | `Npc_Goron_011_Shop_Child_ClearNormalEmotion` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `2eac4336` | `Npc_Goron_011_Shop_Child_GlassTruth` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `82ee41ba` | `Npc_Goron_011_Shop_Child_ResetDamageNum` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `6497bf8e` | `Npc_Goron_011_Shop_IgnoreBalloonRequest` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `20f13d5d` | `Npc_Goron_Biggoron_Adult_DoArea` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `4a43f627` | `Npc_Goron_Biggoron_Adult_DoArea_Far` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `7c0778a9` | `Npc_Goron_Biggoron_Adult_DoArea_Left` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `48751e07` | `Npc_Goron_Biggoron_Adult_DoArea_Near` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `52092646` | `Npc_Goron_Biggoron_Adult_DoArea_Ocarina` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `bc1d7673` | `Npc_Goron_Biggoron_Adult_DoArea_Right` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `7aff4762` | `Npc_Goron_Biggoron_Adult_Talk` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `bd53642c` | `Npc_Goron_Biggoron_Change_AISceduleto_Act_Smith_Wait` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `3f3a7865` | `Npc_Goron_DaruniaJr_HavePlayedStepOneNear` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `662bd378` | `Npc_Goron_DaruniaJr_HaveTalked_aboutArmorGoron` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `ab7c3d6f` | `Npc_Goron_DaruniaJr_HaveTalked_aboutFireTemple` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `8200f979` | `Npc_Goron_DaruniaJr_HaveTalked_aboutVolvagia` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `cf1570a4` | `Npc_Goron_DaruniaJr_HaveTalked_Rolling` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `64cdfd43` | `Npc_Goron_DaruniaJr_IsCrying` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `34f107ef` | `Npc_Goron_DaruniaJr_SageOfFireClearTalked` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `faaf778a` | `Npc_Goron_FireTemple_nullAttention` | files | Bool | 0 | 32 | none | - | out: not saved |  |  |  | read |  |
| `950e9f59` | `NPC_Goton_008_Child_HaveReported_GreatFairy` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `f3b91323` | `Npc_HHylia_Ingo_001_SayMaron` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `6b01cb89` | `Npc_Hylia_001_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `5280acb4` | `Npc_Hylia_001_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `a666baa8` | `Npc_Hylia_001_IsGetHeartPiece` | files | Bool | 0 | 8 | progress | 1 | out: heart reward |  |  | Heart-piece reward flag from a Hyrule townsperson; co-op keeps heart rewards each player's own (a shared count would pay twice). | read | LS oot_coop.c |
| `a06d8fc1` | `Npc_Hylia_001_IsOnTheRoof` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `d3c68380` | `Npc_Hylia_005_Adult_FirstTalk_AfterGetHookshot` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `ad2875b2` | `Npc_Hylia_005_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `b09fab87` | `Npc_Hylia_005_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `7bf83048` | `Npc_Hylia_007_Adult_Explain` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `35c0a54c` | `Npc_Hylia_007_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `c5ae55ef` | `Npc_Hylia_007_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `fb9746eb` | `Npc_Hylia_007_Child_HigeSensor` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `a830f0e4` | `Npc_Hylia_009_Adult_IsStormSongPlayed` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `7d19f101` | `Npc_Hylia_009_Adult_IsStormSongPlayed_FirstTalk` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `b98fc8ac` | `Npc_Hylia_009_Child_AfterStormFirstTalk` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `ba0a7dbb` | `Npc_Hylia_009_Child_IsInWindmill` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `f5be8a94` | `Npc_Hylia_009_Child_IsStormSongPlayed` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `6c2bf169` | `Npc_Hylia_010_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `6d0fad60` | `Npc_Hylia_010_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `6c399b53` | `Npc_Hylia_011_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `b83914fa` | `Npc_Hylia_011_Child_Guide` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `4478a3fb` | `Npc_Hylia_012_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `22b3a9ff` | `Npc_Hylia_012_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `944b71b4` | `Npc_Hylia_013_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `b95a4808` | `Npc_Hylia_013_Child_Act_RestingPlace_Near` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `98973103` | `Npc_Hylia_013_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `0a8ac371` | `Npc_Hylia_014_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `52b9460f` | `Npc_Hylia_014_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `f3a8420d` | `Npc_Hylia_015_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `d0e5b3fa` | `Npc_Hylia_015_Child_Act_RestingPlace_Near` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `83d8c710` | `Npc_Hylia_015_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `c59e1b23` | `Npc_Hylia_016_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `98f6e29b` | `Npc_Hylia_016_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `452b3f81` | `Npc_Hylia_017_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `aabd7d71` | `Npc_Hylia_017_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `780f08e8` | `Npc_Hylia_018_Shop_Child_CursorOnShield` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `88eafe2b` | `Npc_Hylia_018_Shop_Child_ShieldFirstTalk` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `582575cf` | `Npc_Hylia_020_Shop_Goodbye` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `6067ac7d` | `Npc_Hylia_020_Shop_Item_Bottle_Present` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `1c453117` | `Npc_Hylia_021_Shop_Child_NoFirearmsAllowed_BlueFire_Terror` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `736bee44` | `Npc_Hylia_023_64Link` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `eeff9684` | `Npc_Hylia_023_64Zelda` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `ae7265fa` | `Npc_Hylia_023_Bunny` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `882ab3cc` | `Npc_Hylia_023_Common` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `581134ab` | `Npc_Hylia_023_Gerudo` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `f9d9b8b5` | `Npc_Hylia_023_GlassTruth` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `8a112b4a` | `Npc_Hylia_023_Goron` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `f2a8817b` | `Npc_Hylia_023_Keaton` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `7c6e53b4` | `Npc_Hylia_023_Skull` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `c4398c2a` | `Npc_Hylia_023_Spooky` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `c7b87443` | `Npc_Hylia_023_Zora` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `92a03d48` | `Npc_Hylia_024_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `647983f1` | `Npc_Hylia_025_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `34840991` | `Npc_Hylia_026_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `76bdc216` | `Npc_Hylia_027_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `e6fd3ba1` | `Npc_Hylia_028_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `433c91d3` | `Npc_Hylia_029_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `096deff8` | `Npc_Hylia_030_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `4fe38418` | `Npc_Hylia_031_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `8fbe8d49` | `Npc_Hylia_032_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `9933bf01` | `Npc_Hylia_032_Child_MaskTruthTalk` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `65ac0428` | `Npc_Hylia_033_Child_GlassTruth` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `070610db` | `Npc_Hylia_033_Child_InHome` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `a6e8d5a5` | `Npc_Hylia_034_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `22fa37f7` | `Npc_Hylia_035_Child_CustomerArrived` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `fb77779f` | `Npc_Hylia_035_Child_CustomerArrivedNum` | files | Int | 0 | 8 | none | - | out: Int in no group |  |  |  | read |  |
| `5065c00d` | `Npc_Hylia_035_Child_CustomerMovedPlaza` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `b9142eb8` | `Npc_Hylia_035_Child_GlassTruth` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `d96d09af` | `Npc_Hylia_035_Child_Inside` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `89419331` | `Npc_Hylia_036_Child_Act_RestingPlace_Near` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `739b0ada` | `Npc_Hylia_036_Child_Act_RestingPlace_Near_02` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `32a3db73` | `Npc_Hylia_036_Child_CustomerArrived` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `4d9f932b` | `Npc_Hylia_036_Child_CustomerArrivedNum` | files | Int | 0 | 8 | none | - | out: Int in no group |  |  |  | read |  |
| `5bdbec4f` | `Npc_Hylia_036_Child_CustomerMovedPlaza` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `c702f261` | `Npc_Hylia_036_Child_GlassTruth` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `629c5732` | `Npc_Hylia_036_Child_Inside` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `ad4a035c` | `Npc_Hylia_036_Child_TalkAct2Arrival` | files | Bool | 0 | 11 | none | - | out: not saved |  |  |  | read |  |
| `7b542624` | `Npc_Hylia_036_Child_TalkAct2Move` | files | Bool | 0 | 11 | none | - | out: not saved |  |  |  | read |  |
| `a3269a63` | `Npc_Hylia_037_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `be1f5752` | `Npc_Hylia_037_DontStopInterestSpot` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `7f81a028` | `Npc_Hylia_038_Child_Act1Talk` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `7e13d2c2` | `Npc_Hylia_038_Child_GlassTruth` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `b1751623` | `Npc_Hylia_039_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `967475ea` | `Npc_Hylia_040_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `8cce9d75` | `Npc_Hylia_040_Item_Bottle_TutorialEvent_IsTalked` | files | Bool | 0 | 11 | progress | 1 | out: temporary |  |  |  | read |  |
| `5bc10553` | `Npc_Hylia_040_Kusuri` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `709e7468` | `Npc_Hylia_040_Onago` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `6ca10c1d` | `Npc_Hylia_041_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `acdcb376` | `Npc_Hylia_042_Child_TurnSchedule` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `b84d5a5c` | `Npc_Hylia_042_KanbanTalk` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `3c051f5a` | `Npc_Hylia_043_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `59492666` | `Npc_Hylia_043_Child_nullAttention` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `0964a1cf` | `Npc_Hylia_044_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `047ca246` | `Npc_Hylia_044_Buy` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `ad93b2b1` | `Npc_Hylia_045_Adult_FeelFlog` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `4e52e8fa` | `Npc_Hylia_045_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `789c50a3` | `Npc_Hylia_045_Adult_WhatHappened` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `23ae1ea7` | `Npc_Hylia_045_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `1519ba9f` | `Npc_Hylia_045_Child_Medicine` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `2a8c3cf1` | `Npc_Hylia_045_DepthOfDiving` | files | Int | 0 | 9 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `1062d0a5` | `Npc_Hylia_045_DivingChallenge_BottomTouched` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `56504cb1` | `Npc_Hylia_045_DivingChallenge_IsOncedTouchtheBottom_Adult` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `efc90911` | `Npc_Hylia_045_DivingChallenge_IsOncedTouchtheBottom_Child` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `595daed3` | `Npc_Hylia_045_DivingChallenge_SinkWithHeavyBoots` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `a339ba3a` | `Npc_Hylia_045_DivingChallenge_TouchtheBottom_Adult` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `00b58717` | `Npc_Hylia_045_DivingChallenge_TouchtheBottom_Child` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `a140c6d1` | `Npc_Hylia_045_DivingChallengeTalk_MaskReaction` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `788314ec` | `Npc_Hylia_045_Goodbye` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `ad7a21ce` | `Npc_Hylia_045_HasDived` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `35f5a3c2` | `Npc_Hylia_045_Obaba` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `807390fb` | `Npc_Hylia_046_BottleShop_HaveTalkedFirestTalk` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `30811f0d` | `Npc_Hylia_046_BottleShop_IgnoreAttentionArea` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `d88b6394` | `Npc_Hylia_046_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `5788e57b` | `Npc_Hylia_047_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `7e9f70d8` | `Npc_Hylia_048_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `c14d06d9` | `Npc_Hylia_048_BottleShop_aboutTalkBigPow` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `9e47f045` | `Npc_Hylia_048_BottleShop_Full` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `5075c6a5` | `Npc_Hylia_048_BottleShop_HaveSeeCamera` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `ab2f1614` | `Npc_Hylia_048_BottleShop_SellTalk` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `3645a671` | `Npc_Hylia_049_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `9805c9d1` | `Npc_Hylia_049_Adult_RailPoint3_Arrived` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `e7cfa25e` | `Npc_Hylia_049_Child_Cucco01_IsInTheCage` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `0ac4ec15` | `Npc_Hylia_049_Child_Cucco02_IsInTheCage` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `1141114f` | `Npc_Hylia_049_Child_Cucco04_IsInTheCage` | files | Bool | 0 | 11 | none | - | out: not saved |  |  |  | read |  |
| `dddc3954` | `Npc_Hylia_049_Child_Cucco06_IsInTheCage` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `5e3123ef` | `Npc_Hylia_049_Child_Cucco07_IsInTheCage` | files | Bool | 0 | 11 | none | - | out: not saved |  |  |  | read |  |
| `a850b5e8` | `Npc_Hylia_049_Child_Cucco_Navi_IsPlayerAccept` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `80ec3d16` | `Npc_Hylia_049_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `997115f0` | `Npc_Hylia_049_Child_HowManyCuccos` | files | Int | 7 | 8 | none | - | out: Int in no group |  |  |  | read |  |
| `17898320` | `Npc_Hylia_049_Child_IsCompleted` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `523b093b` | `Npc_Hylia_051_Adult_DanpesTalk` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `fa79dcdf` | `Npc_Hylia_051_Adult_FirstTalk` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `00ce59a8` | `Npc_Hylia_051_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `e67c7727` | `Npc_Hylia_051_Adult_WindmillMansTalk` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `a311474a` | `Npc_Hylia_051_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `144bec5e` | `Npc_Hylia_052_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `3e3a794e` | `Npc_Hylia_052_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `477f9555` | `Npc_Hylia_052_DogRun_Now` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `626ea742` | `Npc_Hylia_053_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `50486af6` | `Npc_Hylia_054_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `14cf036d` | `Npc_Hylia_055_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `0a98292a` | `Npc_Hylia_056_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `a6c6aa67` | `Npc_Hylia_057_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `a44e2de7` | `Npc_Hylia_058_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `329c2829` | `Npc_Hylia_059_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `c2349629` | `Npc_Hylia_059_Child_InHome` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `e596ae58` | `Npc_Hylia_060_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `e65a85a1` | `Npc_Hylia_061_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `4868e50f` | `Npc_Hylia_062_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `dccd0909` | `Npc_Hylia_063_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `cb4091b7` | `Npc_Hylia_064_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `f0224777` | `Npc_Hylia_064_Child_HyliaLakeTalk` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `64d0868a` | `Npc_Hylia_065_Child_ArrivedAction2` | files | Bool | 0 | 10 | progress | 1 | out: temporary |  |  |  | read |  |
| `e0ce73ad` | `Npc_Hylia_065_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `3fba2030` | `Npc_Hylia_066_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `4e442f4a` | `Npc_Hylia_Fishman_InSinkHatArea` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `b0074082` | `Npc_Hylia_Fishman_SinkHat` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `01235452` | `Npc_Hylia_Fishman_TakeOffHat` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `9f639dda` | `Npc_Hylia_Ingo_Adult_ByTheWay` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `71b985e2` | `Npc_Hylia_Ingo_Adult_Explained` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `3a9fe971` | `Npc_Hylia_Ingo_Adult_FallOff` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `d661c0f1` | `Npc_Hylia_Ingo_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `5353da95` | `Npc_Hylia_Ingo_Adult_Happy` | files | Bool | 0 | 264 | none | - | out: not saved |  |  |  | read |  |
| `5dbf06b8` | `Npc_Hylia_Ingo_Adult_NoMoney` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `69633eb0` | `Npc_Hylia_Ingo_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `cc617368` | `Npc_Hylia_Malon_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `9e152630` | `Npc_Hylia_Malon_Adult_Singing` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `0976fb50` | `Npc_Hylia_Malon_Adult_Talk_Action5` | files | Bool | 0 | 32 | none | - | out: not saved |  |  |  | read |  |
| `e930e446` | `Npc_Hylia_Malon_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `1e567bf7` | `Npc_Hylia_Malon_Child_IsSinging` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `25058790` | `Npc_Hylia_Malon_Child_NotAttentionEria` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `150d5f39` | `Npc_Hylia_Malon_Child_SeeTheCucco` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `bea00d8d` | `Npc_Hylia_RunningMan_Adult_Desert` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `57c19f5d` | `Npc_Hylia_RunningMan_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `a17c0014` | `Npc_Hylia_RunningMan_Child_FirstTalk` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `02981333` | `Npc_Hylia_RunningMan_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `b61f513d` | `Npc_Hylia_RunningMan_Child_IsArrivedRelayPoint` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `92996cef` | `Npc_Hylia_RunningMan_Child_LastPassedRailIndex` | files | Int | 0 | 8 | none | - | out: Int in no group |  |  |  | read |  |
| `c7ee3336` | `Npc_Hylia_RunnningMan_Child_BunnyMask_First` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `2f77dce2` | `Npc_Hylia_Soldier001_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `e4c9bab8` | `Npc_Hylia_Soldier002_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `0befc7ed` | `Npc_Hylia_Soldier003_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `838c43c0` | `Npc_Hylia_Soldier005_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `16caa105` | `Npc_Hylia_Soldier006_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `ee52a5a3` | `Npc_Hylia_Soldier007_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `e654a4f9` | `Npc_Hylia_Soldier008_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `0c6e5da0` | `Npc_Hylia_Soldier009_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `71c3ad2c` | `Npc_Hylia_Soldier029_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `b543f88a` | `Npc_Hylia_Soldier_002_Mansion` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `de3d7168` | `Npc_Hylia_Soldier_003_GateClose` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `19898d14` | `Npc_Hylia_Soldier_003_GateOpen` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  | Set when the Kakariko gate guard lets Link through (the letter, or the Kakariko gate scene); a Market shop person is present only while true. | read | world model |
| `88f8bc68` | `Npc_Hylia_Soldier_003_nullAttention` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `25a89768` | `Npc_Hylia_Soldier_008_Child_TalkChoice_Any` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `2ffad4ee` | `Npc_Hylia_Soldier_008_Child_TalkChoice_Castle` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `9552382e` | `Npc_Hylia_Soldier_008_Child_TalkChoice_Town` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `e6657791` | `Npc_Hylia_Soldier_008_Child_WhereIsHere` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `dc74e142` | `Npc_Hylia_Soldier_009_Child_FirstTalk` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `9547664c` | `Npc_Hylia_Soldier_009_Child_OpenTheGate` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `e95653c1` | `Npc_Hylia_Soldier_009_Child_SecondTalk` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `eaccaa95` | `Npc_Hylia_Soldier_027_NotStrayChild` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `37d87bb1` | `Npc_Hylia_Talon_Adult_GlassTruth` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `578490fc` | `Npc_Hylia_Talon_Adult_MaronsAngerTalk` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `bea0e200` | `Npc_Hylia_Talon_Adult_MaronsTalk` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `97e376a4` | `Npc_Hylia_Talon_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `2e290948` | `Npc_Hylia_Zelda_Adult_CanTalk` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `f8924c48` | `Npc_Hylia_Zelda_Adult_EnableBarrier` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `3cff3af2` | `Npc_Hylia_Zelda_Adult_EnableHoldEnemy` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `fcdf0e9f` | `Npc_Hylia_Zelda_Adult_EnableJumpOff` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `6e252d42` | `Npc_Hylia_Zelda_Adult_EndlessRailPointWaitAS` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `54cc634c` | `Npc_Hylia_Zelda_Adult_ExecuteInterruptSpecialAction01` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `a56fefd1` | `Npc_Hylia_Zelda_Adult_ExecuteInterruptSpecialAction02` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `1643c992` | `Npc_Hylia_Zelda_Adult_ExecuteInterruptSpecialAction03` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `dcef3194` | `Npc_Hylia_Zelda_Adult_ExecuteInterruptSpecialAction04` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `b50888fa` | `Npc_Hylia_Zelda_Adult_ExecuteInterruptSpecialAction05` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `1c88cfd4` | `Npc_Hylia_Zelda_Adult_ExecuteInterruptSpecialAction07` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `83f5a008` | `Npc_Hylia_Zelda_Adult_ForceDisableDash` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `7090cc5d` | `Npc_Hylia_Zelda_Adult_ForceEnableDash` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `0936d963` | `Npc_Hylia_Zelda_Adult_IsJumpSection` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `6ea5d6ba` | `Npc_Hylia_Zelda_Adult_ReachedCastleGate` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `61a44ef8` | `Npc_Hylia_Zelda_Adult_ReadyDoubleJumpOverCliff` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `819fe204` | `Npc_Hylia_Zelda_Adult_ReadyJumpOverCliff` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `0fa3ea61` | `Npc_Hylia_Zelda_Adult_ReserveJump` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `2a0a95ae` | `Npc_Hylia_Zelda_Child_Positioning_01` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `3ef77000` | `Npc_Hylia_Zelda_Child_Positioning_02` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `a4cead89` | `Npc_Ingo_Act_Farmear_Now` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `bc4786aa` | `Npc_Kaepora_DeathMountainTrail_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `7a3f44af` | `Npc_Kaepora_DeathMountainTrail_Turn` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `c57acbf9` | `Npc_Kaepora_DeathMountainTrail_TurnCheck1st` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `5882c2e3` | `Npc_Kaepora_LakeHrl_Appeared_FromValley` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `c15dd202` | `Npc_KingZora_Far` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `dd173204` | `Npc_KingZora_Near` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `b3464533` | `Npc_KingZora_Right` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `9501cf99` | `Npc_Kokiri_001_Shop_Child_Navi_HasTalked` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `5fd8490e` | `Npc_Kokiri_001_Shop_Child_Talk_Arrival` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `bd0958d7` | `Npc_Kokiri_002_Adult_After` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `1a07794e` | `Npc_Kokiri_002_Adult_Before` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `87ef6807` | `Npc_Kokiri_002_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `a0355fcc` | `Npc_Kokiri_002_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `db08f25d` | `Npc_Kokiri_003_Adult_After` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `d84ca7d2` | `Npc_Kokiri_003_Adult_Before` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `59c41388` | `Npc_Kokiri_003_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `03635780` | `Npc_Kokiri_003_Child` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `5798e9e8` | `Npc_Kokiri_003_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `6761fd94` | `Npc_Kokiri_004_Adult_After` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `aa2270f3` | `Npc_Kokiri_004_Adult_Before` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `f46e07db` | `Npc_Kokiri_004_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `9e23d00a` | `Npc_Kokiri_004_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `9e034154` | `Npc_Kokiri_005_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `52bc28ce` | `Npc_Kokiri_005_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `bc662e40` | `Npc_Kokiri_005_Child_NpcFairy_AvoidPlayer` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `13b0d97d` | `Npc_Kokiri_006_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `5a339e31` | `Npc_Kokiri_006_Child_FirstTalk` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `63687dd8` | `Npc_Kokiri_006_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `3829583d` | `Npc_Kokiri_007_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `f4baf422` | `Npc_Kokiri_007_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `83fd30dc` | `Npc_Kokiri_007_Child_OcarinaFirst` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `816957f7` | `Npc_Kokiri_008_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `3831979d` | `Npc_Kokiri_008_Child_AttentionFlag` | files | Bool | 1 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `94d38496` | `Npc_Kokiri_008_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `49776c8a` | `Npc_Kokiri_008_Child_HaveNoItems` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `40cb1948` | `Npc_Kokiri_008_Child_Sword` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `5f5bfacc` | `Npc_Kokiri_009_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `cc364bd7` | `Npc_Kokiri_009_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `f7f985f2` | `Npc_Kokiri_009_Child_MoneyTalkStart` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `1a9140ec` | `Npc_Kokiri_010_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `f4e5fc55` | `Npc_Kokiri_010_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `d2c144c6` | `Npc_Kokiri_010_Child_Teach` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `b9789806` | `Npc_Kokiri_011_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `9c3642e1` | `Npc_Kokiri_011_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `5c347858` | `Npc_Kokiri_011_FocusEvent_NearLeftWall` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `a33318e1` | `Npc_Kokiri_012_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `3349df9c` | `Npc_Kokiri_012_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `9b1e7950` | `Npc_Kokiri_013_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `1763785f` | `Npc_Kokiri_013_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `31fe5658` | `Npc_Kokiri_Fado_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `28e0a732` | `Npc_Kokiri_Fado_Child_CameraAtDekuTree` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `44f2cb83` | `Npc_Kokiri_Fado_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `a5c236a6` | `Npc_Kokiri_Mido_Adult_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `2c13577f` | `Npc_Kokiri_Mido_Adult_OcarinaReactionStop` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `5b0aea79` | `Npc_Kokiri_Mido_Adult_SageOfForest_IsCompleted_Near` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `03222aab` | `Npc_Kokiri_Mido_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `16f23af6` | `Npc_Kokiri_Mido_IgnoreAttentionArea` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `a3dc874f` | `Npc_Kokiri_Mido_LostForest` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `93e3da07` | `Npc_Kokiri_Noticed_PulledOut` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `9aa85b85` | `Npc_Kokiri_Saria_Child_DekuRoad` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `f7e3f55d` | `Npc_Kokiri_Saria_Child_IDontKnowBoy` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `0780db0b` | `Npc_Kokiri_Saria_Child_IKnow` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `a58c7a0e` | `Npc_Kokiri_Saria_Child_IKnowBoy` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `774bd9fd` | `Npc_Kokiri_Saria_Child_InHome_ChangeSchedule` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `18da5df2` | `Npc_Kokiri_Saria_Child_OcarinaHolder_IsPlayingSoundYourself` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `fb3d19dd` | `Npc_Kokiri_Saria_Child_OcarinaReactionStop` | files | Bool | 1 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `d40c23b9` | `Npc_Kokiri_Saria_Child_SacredForestMeadow_PlayedSariaSong` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `75d64853` | `Npc_Kokiri_Saria_Child_ScheduleChange` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `d852fccd` | `Npc_Kokiri_Saria_Child_WarpDone` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `27c52681` | `Npc_Kokiri_Saria_Child_WarpStandby` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `44a1689b` | `Npc_Kokiri_Saria_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `1c75a859` | `NPC_LakeHrl_0010_JustBeforeTalk` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `35ce1c6f` | `NPC_Pierre_TalkFlag` | files | Bool | 0 | 9 | progress | 1 | out: temporary |  |  |  | read |  |
| `5fde9b14` | `Npc_SkullDad_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `b73c50a0` | `Npc_SkullKid02_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `50f18601` | `Npc_SkullKid_Child_02_Talked` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `675608ce` | `Npc_SkullKid_Child_GlassTruth` | files | Bool | 0 | 33 | none | - | out: not saved |  |  |  | read |  |
| `5ff7aa30` | `Npc_SkullKid_Child_IsGetHeartPiece` | files | Bool | 0 | 8 | progress | 1 | out: heart reward |  |  | Heart-piece reward flag from the child Skull Kid; co-op keeps heart rewards each player's own (a shared count would pay twice). | read | LS oot_coop.c |
| `c955e971` | `Npc_SkullKid_Child_PlayOcarina_IsReacted` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `e35b53e6` | `Npc_SkullKid_Child_SkipNearBalloonMsg` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `c7ebe6d2` | `Npc_SkullKid_Child_Talked` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `bf7d403d` | `NPC_SkullKid_Delete` | files | Bool | 0 | 1 | none | - | out: not saved |  |  |  | read |  |
| `60342ad7` | `Npc_SkullKidSession_IgnoreOcarinaReaction` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `c7124be0` | `Npc_Talon_Act_Farmear_Now` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `4ccb5dac` | `Npc_Talon_Act_RestingPlace_Near` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `06c3484a` | `Npc_Zora_001_Child_Near` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b21f9819` | `Npc_Zora_001_Child_Near01` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `7658711b` | `Npc_Zora_002_Adult_GoldScale` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `91aee58d` | `Npc_Zora_003_Adult_Talked` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b7b2bfc5` | `Npc_Zora_004_isFrontOfJabujabuMural` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `fba52697` | `Npc_Zora_004_isInEntrance` | files | Bool | 1 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `eefa607e` | `Npc_Zora_004_isInKingRoom` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `f3ed0954` | `Npc_Zora_004_MoveToJabujabuMural` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `d10cc947` | `Npc_Zora_004_MoveToKingRoom` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `155006c6` | `NPC_Zora_006_NearEvent00` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `8f057b4d` | `NPC_Zora_006_NearEvent01` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `c148c5fb` | `NPC_Zora_006_NearEvent02` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `0f32dd3d` | `NPC_Zora_006_TalkArea` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `82c7c17f` | `Npc_Zora_007_Adult_Positioning_01` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `459411ec` | `Npc_Zora_007_Adult_Positioning_01_Talked` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `a6caf322` | `Npc_Zora_007_Adult_Positioning_02` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `b2899c99` | `Npc_Zora_007_Adult_Positioning_03` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `14e9f7f7` | `Npc_Zora_007_Adult_Positioning_Choice` | files | Int | 0 | 8 | progress | 3 | out: Int in no group |  |  |  | read |  |
| `89ea895f` | `Npc_Zora_007_HasWorried` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `0275b7d3` | `Npc_Zora_007_StoneOfWaterClearedTalk` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `76fda3e0` | `Npc_Zora_008_CaptureFish` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `24c4a596` | `Npc_Zora_008_ExistFish` | files | Bool | 0 | 8 | none | - | out: not saved |  |  |  | read |  |
| `f4fd35b0` | `Npc_Zora_009_PickUpItems` | files | Bool | 0 | 9 | none | - | out: not saved |  |  |  | read |  |
| `85e1e9bc` | `Npc_Zora_010_Mask00` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `7f4e8002` | `Npc_Zora_010_Mask01` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `c2203906` | `Npc_Zora_010_Mask02` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `62321760` | `Npc_Zora_010_Mask03` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `de25100d` | `Npc_Zora_010_Mask04` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `03f782d2` | `Npc_Zora_010_Mask05` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `790b233b` | `Npc_Zora_010_Mask06` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `7620b478` | `NPC_zora_010_Mask07` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `af65343b` | `NPC_zora_010_Mask08` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
| `2dd4220c` | `Npc_zora_010_Mask10` | files | Bool | 0 | 8 | progress | 1 | progress, shared |  |  |  | read |  |
