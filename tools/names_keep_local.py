#!/usr/bin/env python3
"""tonesi-machine only: list this branch's own HS/LS-name literals in docs/names-kept.md.

The author's name policy (name_policy.py, tests/test_names.py, publish-check.sh) counts every literal that contains
"hookshot" or "longshot" and refuses an unlisted one: it keeps the *published* workbench free of old names. This branch
writes this PC's paths (~/Hookshot, ~/hookshot-wt, .hookshot-harness), the forge's names and the runtime file names into
skills, the brief and the gates on purpose, so after a merge the excess is listed here instead of left failing:

    python3 -I -B tools/names_keep_local.py          # add the excess (counts raised, never lowered)
    python3 -I -B tools/names_keep_local.py --prune  # also lower or drop rows that no longer match

Rows it adds carry the reason REASON, so `git diff docs/names-kept.md` shows them and the author's rows stay untouched."""
import json, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import name_policy as np  # noqa: E402

REASON = "tonesi-machine: this PC's layout, the Longshot forge or the runtime file names (tools/names_keep_local.py)"


def main(prune):
    manifest = ROOT / np.MANIFEST
    text = manifest.read_text()
    rows = np.records(text)
    seen = np.observed(ROOT)
    allowed = Counter()
    for path, literal, count, _ in rows:
        allowed[(path, literal)] += count
    out = []
    for path, literal, count, reason in rows:
        if prune and reason == REASON:
            count = min(count, seen[(path, literal)])
            if count < 1:
                continue
        out.append([path, literal, count, reason])
    index = {(r[0], r[1]): r for r in out}
    added = 0
    for key, n in sorted((seen - allowed).items()):
        if key in index:
            index[key][2] += n
        else:
            row = [key[0], key[1], n, REASON]
            out.append(row); index[key] = row
        added += n
    body = '\n```jsonl\n' + '\n'.join(json.dumps(r, ensure_ascii=False) for r in sorted(out)) + '\n```\n'
    before, rest = text.split(np.BEGIN, 1)
    _, after = rest.split(np.END, 1)
    manifest.write_text(before + np.BEGIN + body + np.END + after)
    print(f'names_keep_local: {added} occurrence(s) listed')


if __name__ == '__main__':
    main('--prune' in sys.argv)
