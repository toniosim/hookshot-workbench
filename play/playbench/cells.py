"""Freezing a cell: copy a segment (or chapter) file and a save into the scoreboard's private folder, set the budgets, and make sure the proof's flags are watched.

The scoreboard is FIXED: a cell is the frozen copy under playbench-local/segments and playbench-local/saves, not the pilot's source segment (which people edit) or
the save library entry (which grows). `board.fingerprint` hashes the frozen files, so changing one on purpose starts a new series. A builder script of the private
folder (it names the places) calls these helpers; the game-derived values never enter this file.
"""
import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import board  # noqa: E402


def toml_value(v):
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return json.dumps(v)   # a JSON string is a TOML basic string
    if isinstance(v, (list, tuple)):
        return '[' + ', '.join(toml_value(x) for x in v) + ']'
    if isinstance(v, dict):
        return '{' + ', '.join(f'{k} = {toml_value(x)}' for k, x in v.items()) + '}'
    raise TypeError(f'cannot write {type(v).__name__}')


def dumps(doc, header=''):
    """A segment or chapter dict (as tomllib loads it) written back as TOML: top-level values, then each array of tables ([[goal]], [[progress]], [[objective]])."""
    out = [f'# {h}' for h in header.splitlines()] if header else []
    for k, v in doc.items():
        if not (isinstance(v, list) and v and isinstance(v[0], dict)):
            out.append(f'{k} = {toml_value(v)}')
    for k, v in doc.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            for item in v:
                out += ['', f'[[{k}]]']
                for kk, vv in item.items():
                    if kk == 'targets' and isinstance(vv, list):
                        out.append('targets = [' + ',\n           '.join(toml_value(t) for t in vv) + ']')
                    else:
                        out.append(f'{kk} = {toml_value(vv)}')
    return '\n'.join(out) + '\n'


def freeze_segment(src, dest, cell, *, save_abs=None, watch=(), header=''):
    """Write the frozen segment of `cell` (a board.Cell) from the source TOML `src` to `dest`: name pb-<cell>, the cell's budget and decision limit and its wall,
    humanize 0 (every line goes out as made), the save by absolute path when given, and `watch` extended with the proof's flags. Returns the dict written."""
    doc = tomllib.loads(Path(src).read_text())
    doc['name'] = f'pb-{cell.id}'
    doc['budget_seconds'] = float(cell.budget_s)
    doc['wall'] = cell.wall_s
    doc['humanize'] = 0
    if cell.kind == 'segment':
        doc['max_decisions'] = cell.max_decisions
    elif 'max_objectives' in doc:
        doc['decisions_per_objective'] = doc.get('decisions_per_objective', 30)
    if save_abs:
        doc['save'] = str(save_abs)
    if cell.kind == 'segment':
        flags = sorted(set(doc.get('watch', [])) | board.proof_flags(cell.proof) | set(watch))
        if flags:
            doc['watch'] = flags
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    Path(dest).write_text(dumps(doc, header))
    return doc


def freeze_save(src, dest):
    """Copy a user folder (<src>/save/<id>/...) to dest (replaced); refuses an `src` that is no user folder."""
    src, dest = Path(src), Path(dest)
    if not (src / 'save').is_dir():
        raise ValueError(f'{src} holds no save/ folder')
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    return dest


def make_start_save(tool, base, dest, start, age=None, time_of_day=None, extra=()):
    """hs_make_save.py --from base --out dest --start <start> [--age] [--time]: a save whose first sample is at `start` (`<map>:x,y,z,yaw`). Raises with the tool's
    words when it fails."""
    argv = [sys.executable, str(tool), '--from', str(base), '--out', str(dest), '--start', start]
    if age:
        argv += ['--age', age]
    if time_of_day:
        argv += ['--time', time_of_day]
    argv += list(extra)
    r = subprocess.run(argv, capture_output=True, text=True, timeout=300)
    if r.returncode:
        raise RuntimeError(f'hs_make_save {start}: {(r.stderr or r.stdout).strip()[-400:]}')
    return r.stdout
