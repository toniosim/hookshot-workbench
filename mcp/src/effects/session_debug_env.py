"""Launch-time switches of a debug profile: environment lines and the owned live-input file.

The three catalogue fields are operator-only and each needs ``debug``; nothing changes for a profile that sets none.
"""
from pathlib import Path


def debug_launch(profile, root: Path) -> tuple[list[str], dict[str, str], Path | None]:
    """(extra environment lines, {file name: initial content} to create before the process starts, live-input path)."""
    lines, files, live = [], {}, None
    if profile.debug_tools:
        # An owned, initially empty live-input file; session_debug appends `!cheat` lines to it.
        live = root / "debug-live.txt"
        files[live.name] = ""
        lines += ["HOS_OOT_CHEATS=1", "HOS_INPUT_LIVE=" + str(live)]
    if profile.memory == "rw":
        lines.append("HOS_CONTROL_MEM=rw")
    if profile.protect_hearts:
        lines.append("HOS_OOT_PROTECT_HEARTS=1")
    return lines, files, live
