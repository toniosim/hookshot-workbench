"""Debug-tool wire records and the operator-registered game info (schema 1).

Nothing about the game is built in: names, action numbers and memory layout arrive at run time in a private JSON file
that the operator registers per build (``BuildEntry.game_info``). The file is validated here and never echoed.
"""
import re
from typing import Annotated, Literal
from pydantic import ConfigDict, Field, field_validator, model_validator
from src.models import Artifact, Record
from src.models.session import GameSample

# A flag is addressed by name (letters, digits, underscore, dot) or by its 32-bit hash written as 0x + 8 hex digits.
FLAG_PATTERN = r"^(?:0x[0-9a-fA-F]{8}|[A-Za-z0-9_.]{1,47})$"
FlagName = Annotated[str, Field(pattern=FLAG_PATTERN)]
FlagKind = Literal["bool", "int", "uint", "float"]
ItemName = Annotated[str, Field(min_length=1, max_length=80)]
Count = Annotated[int, Field(ge=0, le=2**31 - 1)]
Address = Annotated[int, Field(ge=0, lt=2**63)]
Offset = Annotated[int, Field(ge=0, le=1 << 24)]
Coordinate = Annotated[float, Field(ge=-100000, le=100000, allow_inf_nan=False)]   # metres, in the frame of the map Link is in


class TimeAction(Record):
    kind: Literal["time"]
    hour: int = Field(ge=0, le=23)


class ItemAction(Record):
    kind: Literal["item"]
    name: ItemName
    change: int = Field(ge=-64, le=63)

    @field_validator("change")
    @classmethod
    def nonzero(cls, value: int) -> int:
        if value == 0:
            raise ValueError("change must not be zero")
        return value


class ItemToggleAction(Record):
    kind: Literal["item_toggle"]
    name: ItemName


class MarkAction(Record):
    kind: Literal["mark"]


class ReturnAction(Record):
    kind: Literal["return_to_mark"]


DebugAction = Annotated[TimeAction | ItemAction | ItemToggleAction | MarkAction | ReturnAction, Field(discriminator="kind")]


class GameActions(Record):
    model_config = ConfigDict(populate_by_name=True)
    time_base: Count
    time_hours: int = Field(ge=1, le=24)
    mark: Count
    return_to_mark: Count = Field(alias="return")
    item_base: Count
    item_stride: int = Field(ge=1, le=2**31 - 1)
    item_bias: Count
    item_toggle: Count


class GameItem(Record):
    index: int = Field(ge=0, le=65535)
    name: str = Field(min_length=1, max_length=80)
    label: str = Field(default="", max_length=80)
    kind: Literal[0, 1]

    @field_validator("name", "label")
    @classmethod
    def printable(cls, value: str) -> str:
        if not value.isprintable():
            raise ValueError("control characters are not allowed")
        return value


class KindLayout(Record):
    at: Offset
    stride: int = Field(ge=1, le=1 << 24)
    value: Offset


class BoxLayout(Record):
    count: Offset
    entries: Offset
    table: Offset
    size: Offset


class GameLayout(Record):
    holder: Address
    kinds: dict[FlagKind, KindLayout] = Field(min_length=1)
    box: BoxLayout


class ItemFlags(Record):
    # Templates of flag names holding an item's quantity / possession; "{name}" is replaced by the item name.
    count: str | None = Field(default=None, max_length=47)
    have: str | None = Field(default=None, max_length=47)

    @field_validator("count", "have")
    @classmethod
    def template(cls, value: str | None) -> str | None:
        if value is not None and (value.count("{name}") != 1 or not re.fullmatch(r"[A-Za-z0-9_.]*", value.replace("{name}", ""))):
            raise ValueError("a template holds {name} once and only letters, digits, '_' and '.'")
        return value


class GameInfo(Record):
    """Schema 1. Extra fields are refused everywhere except as keys of ``names``."""
    model_config = ConfigDict(populate_by_name=True)
    schema_version: Literal[1] = Field(alias="schema")
    actions: GameActions
    items: list[GameItem] = Field(default_factory=list, max_length=1024)
    layout: GameLayout | None = None
    item_flags: ItemFlags | None = None
    names: dict[Annotated[str, Field(pattern=r"^[A-Za-z0-9_.]{1,47}$")], FlagName] = Field(default_factory=dict, max_length=64)

    @model_validator(mode="after")
    def unique_items(self):
        if len({item.index for item in self.items}) != len(self.items) or len({item.name for item in self.items}) != len(self.items):
            raise ValueError("item indexes and names must be unique")
        return self


class DebugItem(Record):
    name: str = Field(max_length=80)
    index: int = Field(ge=0)
    # Quantity (item) or possession (item_toggle) read through a flag subscription; null without configured flags.
    count_before: int | None = None
    count_after: int | None = None
    # The game's own words, parsed from its log; never turned into a verification.
    had: int | None = None
    now: int | None = None


class DebugResult(Record):
    kind: Literal["time", "item", "item_toggle", "mark", "return_to_mark"]
    line_sent: Literal[True] = True
    action_number: int = Field(ge=0)
    game_said: list[Annotated[str, Field(max_length=200)]] = Field(max_length=8)
    effect: Literal["verified", "requested", "not_applied"]
    before: GameSample
    after: GameSample
    item: DebugItem | None = None
    observed_at: str


class WarpSample(Record):
    t: float
    pos: list[float] | None = Field(default=None, min_length=3, max_length=3)
    dist: float | None = None
    stale: bool = False    # read before the game applied the warp (the state sample is the previous update's)


class WarpResult(Record):
    line_sent: Literal[True] = True
    target: list[float] = Field(min_length=3, max_length=3)
    game_said: list[Annotated[str, Field(max_length=200)]] = Field(max_length=8)
    effect: Literal["verified", "partial", "not_applied"]
    samples: list[WarpSample] = Field(max_length=64)
    before: GameSample
    after: GameSample
    note: str | None = Field(default=None, max_length=300)
    observed_at: str


FlagValue = int | float | Annotated[str, Field(max_length=64)] | None


class FlagsRead(Record):
    flags: dict[str, FlagValue] = Field(max_length=16)
    frame: int | None = None
    sample_frame: int | None = None
    observed_at: str


class FlagWritten(Record):
    name: str = Field(pattern=FLAG_PATTERN)
    hash: str = Field(pattern=r"^0x[0-9a-f]{8}$")
    kind: FlagKind
    before: bool | int | float
    written: bool | int | float
    after_memory: bool | int | float | None
    after_flag: int | float | str | None
    effect: Literal["verified", "not_applied"]
    observed_at: str


class SaveListing(Record):
    slot: str = Field(pattern=r"^[0-9]{1,3}$")
    mtime: float | None = None


class SnapshotState(Record):
    map: str | None = Field(default=None, max_length=80)
    age: str | None = Field(default=None, max_length=32)
    pos: list[Annotated[float, Field(allow_inf_nan=False)]] | None = Field(default=None, min_length=3, max_length=3)
    life: int | None = Field(default=None, ge=0)
    max_life: int | None = Field(default=None, ge=0)
    rupees: int | None = Field(default=None, ge=0)
    frame: int | None = None  # the game's own sampled frame
    fresh: bool | None = None
    observed_at: str
    saves_listing: list[SaveListing] | None = Field(default=None, max_length=100)


class SnapshotResult(Record):
    save_id: str = Field(pattern=r"^save_[0-9a-f]{32}$")
    file_count: int = Field(ge=0)
    copy_hash_manifest: Artifact
    state: SnapshotState
    slot_age_seconds: float | None = None
    matches_state: None = None
    validation_status: Literal["copy_only_not_a_checkpoint"] = "copy_only_not_a_checkpoint"
    note: str = Field(max_length=1024)
