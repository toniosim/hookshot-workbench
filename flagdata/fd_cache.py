"""The private cache of a build: every Bool and Int flag with its name, family, category and default mode, for the log annotator.

It is made from a player's own game files, so it lives under the user's own state folder (`$LS_FLAGDATA_STATE`, else
`$XDG_STATE_HOME/ls-workbench/flagdata`, else `~/.local/state/ls-workbench/flagdata`), mode 0600 in a 0700 folder, and is never written
under a git checkout of the workbench.
"""
import hashlib
import json
import os
import time
from pathlib import Path

VERSION = 1


def state_dir(override=None):
    if override:
        return Path(override).expanduser()
    if os.environ.get("LS_FLAGDATA_STATE"):
        return Path(os.environ["LS_FLAGDATA_STATE"]).expanduser()
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return Path(base) / "ls-workbench" / "flagdata"


def make_key(*blobs):
    h = hashlib.sha256()
    for b in blobs:
        h.update(hashlib.sha256(b).digest())
    return h.hexdigest()[:16]


def entry(row, left=False):
    """The cache record of a row of fd_report.make_rows."""
    if left:
        return dict(k=row["kind"], c="", s=0, m="", n=row["name"], f="", a=row["map"], d=row["default"], r=row["reason"])
    return dict(k=row["kind"], c=row["category"], s=1 if row["scene"] == "yes" else 0, m=row["default_mode"], n=row["name"],
                f=row["family"], a=row["map"], d=row["default"], r="")


def write(directory, key, rows, left, meta):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    flags = {}
    for row, is_left in [(r, False) for r in rows] + [(r, True) for r in left]:
        flags.setdefault(row["hash"], []).append(entry(row, is_left))
    doc = dict(version=VERSION, key=key, made=time.strftime("%Y-%m-%dT%H:%M:%S"), meta=meta, flags=flags)
    path = directory / ("table-%s.json" % key)
    tmp = path.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(doc, f, separators=(",", ":"))
    os.replace(tmp, path)
    latest = directory / "LATEST"
    latest.write_text(path.name + "\n", encoding="utf-8")
    os.chmod(latest, 0o600)
    return path


def find(directory=None, path=None):
    """The cache file to read: `path`, else the one LATEST names under the state folder."""
    if path:
        return Path(path)
    directory = state_dir(directory)
    latest = directory / "LATEST"
    if not latest.is_file():
        raise FileNotFoundError("no flag table under %s: make one with `flagdata.py build` (it is made from your own game files)" % directory)
    return directory / latest.read_text(encoding="utf-8").strip()


def load(path):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("version") != VERSION:
        raise ValueError("%s: cache version %s, expected %s: make it again with `flagdata.py build`" % (path, doc.get("version"), VERSION))
    return doc
