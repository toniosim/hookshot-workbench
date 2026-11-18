---
name: ls-skill-upkeep
description: >
  Use when a skill misled you, was out of date or lacked a step, when you repeated a procedure that no skill covers,
  when writing or changing a skill, or (main session) when triaging workers' skill notes and publishing skill changes:
  how to report a skill problem, how to check all skills mechanically, when a new skill is worth it, and how a change
  is tested and published.
---

# Keeping the skills right

A skill is only worth its place in every session's catalogue if it is true today. Skills go stale quietly: a path
moves, a script gains a flag, a rule changes on the forge. Two things keep them right: every agent says what was wrong
with the skills it used, and one mechanical check finds the rot nobody noticed.

## Every agent: say what was wrong (takes two minutes)

End your final report with a section **Skill notes**, one line per finding, or `Skill notes: none`:

```markdown
## Skill notes
- ls-function-map, "1. Look it up": `find` did not match `F_803EDF70` in capitals; I had to lower-case it.
- ls-workbench: says the gate script is at <path>; it is at <path> now.
- no skill covers: carrying a measured branch onto a newer main and deciding what must be measured again (done 3 times).
```

What belongs there:
- **wrong**: a command, path, flag or rule in a skill that did not work as written. Quote the line.
- **missing**: something you had to work out that the skill should have told you. Say what you needed.
- **misleading**: the description made you open a skill that was not for your task, or you only found the right skill late.
- **no skill covers**: a procedure you had to invent and expect to repeat.

Workers do not edit skills: a dozen sessions read them at once, and a half-written skill breaks all of them. Report;
the main session changes.

## Main session: triage, change, test, publish

1. **Collect.** Copy each note into `/home/tonesi/hookshot-wt/reports/SKILL-NOTES.md` with the date, who reported
   it and a status: `applied <commit>`, `declined: <why>`, `open`.
2. **Check mechanically**, before and after any change:
   ```sh
   python3 /home/tonesi/.claude/skills/ls-skill-upkeep/check_skills.py --only ls- hookshot-
   ```
   FAIL lines are broken references; WARN `path not found` is the usual sign of a stale skill. Each WARN is either
   fixed or is a deliberate example; do not leave ones you have not read.
   `check_skills.py` takes a backticked path that starts with `scripts/`, `references/` or `assets/` for a script the
   skill ships, and warns when it is in neither the skill's folder nor the port: for anything else write prose ("the
   port's scripts folder") or another first folder. A `*` in an absolute path ends the checked part there: stop such a
   path at a whole folder name.
   For the published tree, run `python3 skills/ls-skill-upkeep/check_skills.py --root skills` from the
   workbench checkout. The live command above deliberately includes the still-installed older prefix.
3. **Change the smallest thing that fixes the note.** Correct the line; add the missing step where a reader would look
   for it. Keep a skill a procedure: what to do, in order, with the commands. Reasons in one clause; history nowhere.
4. **A new skill, or a line in an old one?** A new skill when the procedure has its own trigger (a reader would not
   think to open an existing skill for it), has been needed at least twice, and takes more than a few lines. Otherwise
   add to the skill whose trigger already covers it. Name new skills `ls-<topic>`.
5. **The description is the trigger.** It is all a session sees before deciding to read the skill. Start with *Use
   when* or *Use before*, name the concrete things a task would mention (file names, words, symptoms), and keep it
   under 700 characters. If workers found the skill late, the description is what to fix.
6. **Test with a blank worker.** Give a fresh subagent a real task the skill should serve, **without naming the
   skill**, and ask it to end with Skill notes and to say which skills it read and when. It passed if the worker found
   the skill from the catalogue, the steps worked as written, and it needed nothing the skill did not say. Fix and
   repeat with a new worker; a worker that has already read the old text proves nothing.
   Not for a live skill that is a symlink into a system package (`ls -l ~/.claude/skills`: `diagnose-crash` is one): it
   is not ours and is not in `SKILL_MAP`, so it cannot be tested by editing and re-running a worker or published, and
   replacing the link with a copy cuts it off from the package's updates. Put the pointer a worker needs into one of our
   skills and leave the link.
   A **new** skill is not in the session catalogue: the list is read once, when the main session starts, so `skill://<name>`
   answers `Unknown skill` for it until then. Test it by the brief's table row and the file's path (put the row in first and
   say so in the task); "found it from the catalogue" cannot pass for a skill made today.
7. **Publish.** Add a new skill to `SKILL_MAP` in the workbench's `publish.py` (an identity entry when its live name
   already starts with `ls-`). `sync-from-live.sh` copies **live → repository**, not the reverse: reconcile both
   versions first so an older live skill cannot overwrite a newer repository edit. It stages the proposed tree and
   checks `docs/names-kept.md` before replacing any checkout file; a names failure leaves the checkout untouched.
   `sync-from-live.sh --check` compares without writing, but its names stage runs first: with excess old-name literals
   it stops there and prints no differences. To compare anyway, run `publish.files()` and `publish.normalise()` over the
   live files and diff against the checkout (`reports/SkillPublish-files/live_vs_repo.py` does it). The legacy live
   folder names are mapped, not renamed.
   A new skill also needs its row in the README's table and the counts in `tests/test_publication.py`; any literal that
   contains an old project name (a lock path, an options file, a repository URL) needs a counted record in
   `docs/names-kept.md` or `name_policy.py` fails. Write the old names in prose as LS or HS and keep them to code spans.
   Do all of it in your own worktree of the workbench repository (`git worktree add <path> -b <branch> origin/main` from
   the checkout; `git worktree list` shows who has what): the checkout is shared with the main session and every skills
   worker, and its branch is never switched. Run `publish-check.sh`, the skill check above and the workbench-repository
   tests in `ls-workbench`, read the diff, then commit and push. A branch that renames a skill or removes a name is
   rewritten (rebase or squash) **before** its first push: pushed history keeps the old name.
   Nothing game-derived goes into a skill: commands, paths and procedure only. A machine's SSH alias, key or address
   goes in no skill or brief: write `<win>` or `<relay>`. The alias is written once, in the section "Hosts" of
   `$H/LOCAL-NOTES.md` (`H` as in `skill://ls-workbench`; never published), and `.private/publish-forbidden.txt` lists
   it, so `publish-check.sh` fails if it ever reaches a published file.
   Main alone synchronises live copies when no queued/running worker depends on them: as a reviewed patch of the
   changed lines (`git apply --check`, then `git apply`, with the old files kept), followed by the skill check; never by
   copying the published tree over the live folders, whose names and unrelated text differ.
   - **Build the live patch from a scratch copy, not from the branch's diff:** live prose differs in the context lines
     (names, rename paragraphs), so a repository diff does not apply. Copy the live skills to a scratch folder; apply
     the patch that already worked; apply only what changed since (`git diff --no-renames <old tip> HEAD -- skills
     docs/agent-brief.md`, paths and names mapped to the live ones); `git apply --check` there; compare the scratch tree
     with the checkout through `publish.normalise()`; the patch is the diff of the scratch tree against live.
     `reports/SkillsNight-files/mklive2.py` does it end to end (a base commit per skill, `git apply -C0 --reject`, and
     `live-manual.json` for the few hunks whose removed lines differ in the live prose: the ten older skills still use the
     old project names where the published text says HS and LS, the others never did); an edit made straight to a live
     skill (`SKILL.md.prev-*` beside it) moves that skill's base, so check which commit each live copy equals.
     `reports/SkillPublish-files/mklive.py` and `live_vs_repo.py` are the earlier versions.
   - **While workers read the live skills, edit the repository directly** and let the live copies follow in one step:
     Main applies the reviewed patch built as above, with `reports/SkillsNight-files/apply-live-morning.sh`, which
     keeps a backup of the live skills first. Until then do not run `sync-from-live.sh`: it copies live over the
     repository.
     Keep any other backup of live skills outside the skills tree too (`~/.agents/skill-backups/<date>-<who>`): a `*.prev-*`
     file beside a skill is a stray (seven were moved out on 17 Nov).
   - **The brief** exists twice, live `reports/AGENT-BRIEF.md` and published `docs/agent-brief.md`, and both get edits.
     Merge them; where the same passage differs, the live text wins (workers read it and the next sync copies it),
     except the LS/HS name wording, which the published copy keeps. An edit made only in the published copy is lost at
     the next sync: carry it into the live brief too.

## What the check cannot see

Whether a procedure is still the right one: a rule the maintainers changed, a tool that does it better now, two skills
that say different things. Those only show up in the notes, so read them, and when a task goes badly ask first whether
a skill sent it that way.

## The harness can also learn by itself

omp has an auto-learn feature (`autolearn.enabled`, off by default): its `learn` and `manage_skill` tools store a
lesson and can write a *managed* skill under `~/.omp/agent/managed-skills`. Authored skills such as these always
outrank a managed skill of the same name, managed skills are not part of the workbench repository, and subagents do
not get the tools unless asked. It suits personal lessons; the shared, published skills are kept by the steps above.
