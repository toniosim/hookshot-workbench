---
name: ls-pr-tagging
description: >
  Use when asked to tag, label or triage-label LS pull requests on git.magicbean.dev ("PR tagging run",
  "label the PRs", "tag untagged pull requests", kind/ priority/ area/ platform/ gpu/ labels), including the user's
  own and his Mac session's: plan every open pull request's missing labels from its title, reason and changed files,
  review the flagged ones, then add them. Adds only; never removes or sets maintainer and bot labels.
---

# Tagging the open pull requests

Main session only: it writes to the forge as the user. Read `skill://ls-pr-evidence` for the rules on acting
as the user.

## The labels and what sets them

| Scope | Rule (in `scripts/pr_tags.py`) |
|---|---|
| `kind/` (one) | The title's Conventional Commit type: feat → feature, fix and revert → bug, perf → performance, docs → docs, chore/build/ci/test/refactor/style → chore. Docs-only file lists → docs. No type: flagged. |
| `priority/` (one) | bug and performance: high; everything else: low. Never critical by script: a bug whose title says crash, data loss, corrupt or fails to start is flagged for a person to decide (titles only: reasons often say what a fix is not). |
| `area/` (up to 3) | Changed source files (tests and docs only when nothing else): renderer, upscaling, menu, input, audio, saves, install; plus title words (accessibility and the same areas). Tooling, CI and runtime changes often have none: flagged, left without. |
| `platform/` | macOS words in the title, or only Mac files → macos only. Steam Deck in the title → steam-deck and linux. Windows-only or Linux-only files or title → that one. Everything else → windows and linux (the label's own rule: a change for every system carries both), plus macos when the reason mentions the Mac (shared code found or wanted there; flagged). |
| `gpu/` | Vendor words in the title only (reasons name the tester's card too often). |
| `regression` | A bug whose title or reason says so (flagged). |

Never set: `beanstalk: …`, `ci: approved`, `preview`, `testing wanted`, `needs measurements`, `good first issue`,
`help wanted`, `status/…`. They belong to maintainers or bots. A scope the pull request already has a label in is
left alone; the script reports what it would have added there under `not_added_scope_taken`.

## Steps

1. Plan (reads the forge only, under the forge sign-in lock; writes the plan files):
   ```sh
   export HOME=/home/tonesi
   python3 /home/tonesi/.claude/skills/ls-pr-tagging/scripts/pr_tags.py plan [--numbers 355 68] [--out <dir>]
   ```
   It writes `<dir>/plan.json` and `plan.md` (default `reports/PrTags/<date-time>/`) and prints the counts. About
   350 pull requests take two minutes (one files request per pull request).
2. Review `plan.md`. Read every row with notes (no type, crash words, regression, macOS, no area) and a sample of the
   rest. Wrong proposals: edit `plan.json`'s `add` list for that number (labels must exist in `labels`), or drop the
   number with `--numbers` on apply. An empty `add` means every proposed label is there already, or its scope
   carries another label (see `not_added_scope_taken`); the issue's label events (`GET .../issues/<n>/timeline`)
   say who set them.
3. Dry run, then apply:
   ```sh
   python3 /home/tonesi/.claude/skills/ls-pr-tagging/scripts/pr_tags.py apply --plan <dir>/plan.json
   python3 /home/tonesi/.claude/skills/ls-pr-tagging/scripts/pr_tags.py apply --plan <dir>/plan.json --go
   ```
   Apply rereads each pull request's labels first, so a label a maintainer set meanwhile wins. It writes
   `applied.json` beside the plan.
4. Report to the user: how many were labelled, the flagged ones you changed, and the `not_added_scope_taken`
   disagreements worth a maintainer's look (not changed by you).

## Notes

- Forge calls must not run beside another process renewing the sign-in (`token was already used` breaks it for
  everyone): the script takes `/tmp/longshot-forge-auth.lock`; run nothing else signed meanwhile.
- The user's own pull requests and those his Mac session opened under his account are tagged like everyone's.
