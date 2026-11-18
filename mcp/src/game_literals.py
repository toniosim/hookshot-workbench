"""External runtime contracts, not LS workbench branding.

The game's own file and environment names are resolved at run time from the configured harness (`hs_names.py`, see `src/effects/names.py`).
What stays here is the one name no resolver supplies: the media type under which the harness stores a retained pixel-capture log.
This table is not runtime discovery and does not add support for another game's identity.
"""

HS_GAME = {
    "framelog_mime": "application/x-hookshot-framelog",
}
