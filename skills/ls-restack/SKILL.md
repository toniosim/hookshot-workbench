---
name: ls-restack
description: >
  Use when our own long linear branch (27 commits and more, cherry-picked or replayed) must move onto a main that has
  moved: replay, re-carry, restack, rebase --onto, "prove authors, dates and messages unchanged", range-diff `=` and
  `!`, merge conflicts in the menu translation counts or keep-both blocks, tests to run before a queued hold, a hold
  whose base moves while it waits. Not for carrying a test result of someone else's pull request across an identical
  rebase: that is the carry section of ls-pr-loop.
---

# Restacking a long branch onto a moved main

Twelve workers re-carried stacks of 27 to 264 commits by hand. The pieces below exist; the order matters because the
queued hold is hours long and a mistake found after admission costs the whole wait.

## 1. Pin, then see the conflicts before you pick

- Assert that the old range is linear and has N commits, and name the old base, the new base and the branch. A replay
  script that does not assert them can pair the wrong commits.
- `git merge-tree --write-tree --name-only --merge-base=<oldbase> <newbase> <oldhead>` lists, without touching a tree,
  the files that will conflict. Read it, and the intervening main changes to the same files, before the first pick.

## 2. Replay one commit at a time

Copy `/home/tonesi/hookshot-wt/reports/Replay18b-files/replay.py` and edit its constants (worktree, bases,
branch names, N); do not run it as it is. It does `git cherry-pick --no-commit` and then
`git commit --cleanup=verbatim -F -` with the original `GIT_AUTHOR_*` name, address, date and message, rerere off, no `-x`,
the committer set with `-c` as the brief says. It stops at a conflict (`pending.json`) and resumes, asserts author and
message per commit and records an empty pick as dropped. With few conflicts `git rebase --onto` does the same; if the
committer date must follow the author date use `rebase --committer-date-is-author-date`: `git cherry-pick` has no such
option. A commit keeps its own trailers; only a new commit carries ours.

Recurring conflicts and their tools (all under `/home/tonesi/hookshot-wt/reports/`):

- Translation counts in `gpu/vk/menu_i18n.h`, and sorted tables: `Integrate18-files/carry-d9/carry-i18n.py WT LOG RANGE`
  (resets every count to its table length after each touching pick) or `Integrate18-files/final68/carry/i18n-merge.py WT LOG`.
  Equal counts merge silently and wrong: `tests/test_menu_i18n.py` is the guard; run it after each such pick.
- Keep-both blocks (adjacent rows or jobs added on both sides): `Integrate18-files/resolve.py WT LOG PATH BLOCK MODE`
  records a resolution keyed on the (file, ours, theirs) text and `reapply.py WT LOG RANGE` replays it on the next
  attempt; it exits 3 on a block it has no record for.
- A branch that changes an input a generator turns into committed files (`tests/coop_vectors.txt`): leave no stale
  output; run each generator's `--check` (for example `tests/fuzz/make_seeds.py --check`) after every such pick.
- Option ids, enum numbers and API numbers that two lines both claim: renumber in the commit that owns them, and take the
  next number no open pull request claims (list the ones that touch `gpu/vk/vk_api.h` through the forge's `pulls/N/files`:
  on 17 Nov two claimed 30, others 31 and 33, and two agents bumped to 29 at once). Guards that compare the version
  (`host->version >= N`) move with it. A test that pins the version with `==` (`tests/test_audio_output_devices.py` pins
  `MKWVK_API_VERSION`) fails after a bump from either side: move the pin in the commit that owns the bump, and scan
  **every carried commit** for such pins (`version !=`, `==`) before the replay: a new commit at the end is not enough
  when the old line was green at each commit (`reports/Carry68g-files/rebase/replay.py`'s `TRANSFORMS` shows the way).
- `Replay18*-files/resolve-version-check.py`'s assertion ends in `or True`; do not rely on it.

## 3. Prove it

```sh
R=/home/tonesi/hookshot-wt/reports
python3 -I -B $R/Integrate18-files/prove_carry.py REPO OLD_BASE..OLD_HEAD NEW_BASE..NEW_HEAD OUT.json
python3 -I -B $R/Carry68-files/compare-patches.py OLD_BASE OLD_HEAD NEW_BASE NEW_HEAD OUT.json
git range-diff OLD_BASE..OLD_HEAD NEW_BASE..NEW_HEAD
```

`prove_carry.py` (read-only) shows every commit pair kept its author, author date and message byte for byte and that the
committer is ours. `compare-patches.py` compares each commit's added and deleted lines ignoring context; edit its hard-coded
repository path. `git range-diff` must pair each commit once: a `!` whose added/deleted lines are equal changed only
context (say so, with the counts, for example `24 =, 4 !`). Cross-check the whole: the files that differ between the old
head and the new head are the files that differ between the old base and the new base, plus the conflict resolutions.
`Replay18b-files/prove-replay.py` bundles these checks; its constants need the same editing as `replay.py`.

## 4. Tests before the hold, not in it

1. Run the tests that read a file the branch changes **and** main's own changed tests that read such a file, as one
   focused selection (`tests/run_all.py ... --strict --exact`; confirm `--exact` on the head's `run_all.py --help`).
   A textual merge hides the ones that cut functions or tables out of source by their text (`ls-workbench`, section 3):
   fix them in a test-only commit or a `--fixup` plus autosquash.
   A main that adds a table or a source-text rule over names (the switch table, the MSVC old names) fails the line's new
   names: run `tests/test_switch_table.py` and `tests/test_msvc_oldnames.py` first. A test that fixes which files may name
   a variable (`tests/test_coop_invite.py`) fails a fix that mentions it in a comment.
   Start it, and every long run, from a throwaway worktree of the head (`git worktree add --detach <path> <head>`), not
   the carry's own folder: other workers read and reset that folder while the run goes.
2. A branch that "passes in its worktree" can depend on files `.gitignore` hides (a `*.bin` corpus did): run
   `git status --ignored` in the donor and the focused tests in a clean `git archive` checkout.
3. The whole suite runs inside the hold on main, the base and the head (`reports/tools/verify_heads.py OUT.json
   LABEL=SHA ...`; it takes a global lock and `--jobs 6`). A head-only failure is rerun once with `--exact`. It compares
   failing names only: read the two `suite.json` failing lists too.
4. Run the other branches' fixtures on the merged head before anything is built on it: a clean merge and green branch
   tests do not mean the integrated head passes the older branches' tests.
5. The guide pictures: `python3 -I -B scripts/check_guide_screenshots.py --review-sources` (the forge runs it on every
   pull request) fails on a head whose menu inputs differ from the manifest's; run it on main first, which can fail it
   too on another toolchain. If it fails on the head, render the Graphics view again with `scripts/screenshots/capture_menu.py --source
   <tree> --output <new dir>` from the head and from main as a control on this machine: the difference to the control
   is the change's, the control against the published picture is the toolchain. `reports/Carry68d-files/make-guide-commit.py`
   does the whole guide commit (edit its constants).

## 5. The hold

Its scripts bake the head, base and main hashes and read them at admission. Finish and prove the carry first (queue waits
were 5,000 to 6,900 seconds). If main moves while it waits: requeue, or keep the slot with the `EDITING` marker and a
retarget (`skill://ls-hold-chain`). A new waiter is stopped (`T`) at once by the dispatcher, not by Main or a guard of
yours: never continue it. After admission a stale head is only covered by focused checks: carry only the new
commits and say what was not rerun. Rebase note form and `--imported`: `skill://ls-pr-evidence`.
