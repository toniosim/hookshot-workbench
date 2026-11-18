# Recipes for evidence, reviews, rebases and hand-offs

Pointed to from `SKILL.md`. Paths with `reports/` are in the work area beside the worktrees, not inside a branch worktree.

## Designing from another project's behaviour (no code taken)

1. Tag every claim by where it was read: their documents, their code, our code, a run.
2. Say what was not run, and list the checks that would close each unknown (a game run, a test, a probe).
3. Hand back the function-map rows the design needs and the ones it found missing (`skill://ls-function-map`).
4. Keep the credit and licence wording of `SKILL.md`, "Before any push", item 2.

## The test both ways without a second worktree

- A test that reads a few files: copy only those from the old commit (`git show <old>:<path>`: the source under test
  and its two or three neighbours) into a temporary tree beside the new `tests/` file and run it there (seconds).
- A test that imports the build tooling needs the whole tree: `git archive <old> | tar -x -C <dir>` (no worktree entry
  in `.git`).
- Mutation check of a source-text test: damage one line of the source under test in a copy (drop a lookahead, move a
  boundary); the test must fail. A test whose point is a boundary or a negative case that still passes is the weak one.
  Patterns: `reports/PortInviteMasks-files/mutate_masks.py` and `reports/MaskTokens-files/mutate.py [worktree]
  [all|old|new]`. Their anchors are source text: renaming a function makes them refuse, so change the script in the same
  commit.

## Timing a whole-suite run

`hs-idle.sh` takes one of three test slots (`flock -n`) and only then waits for the shared quiet lock: a run queued
behind an exclusive GPU hold sits on a slot and prints nothing until it is admitted (waits of 372 s and about five
minutes seen). The 1-minute load average swings between 9 and 100 with other sessions, and identical runs differ by 40 %
in wall time (314 s at load 40 to 47, 178 s at load 10 to 22); a quiet-machine figure (about 160 s) does not apply.

1. Wrap each run: `reports/Review893-files/timed.py <label> <out.jsonl> -- <command>` writes wall seconds, the children's
   CPU seconds (`RUSAGE_CHILDREN`) and the load before and after; record the request time yourself.
2. Alternate A and B runs; judge by CPU seconds and by runs at similar load, never by one wall time.
3. `bc` and `/usr/bin/time` are not installed here: do arithmetic in Python, time with the shell's `time` or a
   `date +%s` pair (a launcher that execs `/usr/bin/time` exits 127).

## Reviewing a cache or a cache key

Look for every way the compile's result can change while the key stays the same; a probe that still hits is a gap:
a header edited through each include route, a flag, an object input, a compiler script, `LIBRARY_PATH`, a `.C` source,
`-Xlinker -Map`, `__builtin_LINE`, `CCC_ADD_ARGS`, clang against clang++. Then concurrency: the same key from 32
processes on a cold cache, and a pruner emptying the cache in a loop beside 16 workers compiling the same program.
`reports/Review893-files/probes.py` and `stress.py` (take the cache driver's path and a scratch folder; written for one
driver, adapt the calls) and `misc-probes.sh` are the starting points.

## Is an open pull request superseded by a merged one?

Edit the repository path in the two scripts first (`reports/DataReview-files/`), then:

1. `git merge-tree --write-tree --name-only <main> <head>`: the conflict list.
2. `cmp.py <head> [<main>]`: per changed file, identical to main's, absent from it, or how many of the pull request's
   added lines are on main and how many of its removed lines are gone (multisets of stripped lines against the merge
   base).
3. `lines.py <head> <main> <files...>`: the added lines main lacks and the removed lines main still has, with line
   numbers.
4. Search main for the pull request's new symbols. Superseded only when every file is identical or every leftover line
   is accounted for; say which leftovers remain.

## Rebases and carries

- A force-push changes every commit hash. A description that names commits by hash needs the old -> new map once
  (`git range-diff <old-base>..<old-head> <new-base>..<new-head>` pairs them); heads that only ran tests keep their own
  hashes and get a one-line map.
- When the author or a maintainer rebased the pull request, `git range-diff` needs the old head, which a fetch no
  longer brings after a force-push unless you fetched it before: `git show <commit> | git patch-id --stable` for each
  earlier head and for the new one proves an identical patch.
- Before writing "Rebased on current main": fetch the forge's main and run `git merge-tree --write-tree --name-only
  <forge main> <head>` (one command; main had moved 36 commits under a draft that no longer merged). The checker's
  `--pr` mode warns when the measurement table's `Before: main @ <hash>` is not the pull request's merge base: a
  rebase or carry changes that cell too.
- A draft that waits for a run marks each open slot `PENDING:<neutral-slug>` (a word for the content, not a worker or
  hold name): one `grep PENDING` lists them, and none may remain at the push.
- Two builds said to share one lift: `generated_fingerprint` and the generated tree's hash differ between work
  folders (the tree contains the folder name), and `lift_key` can differ with equal inputs (it covers `hot_pieces.txt`,
  which follows the work folder's history; seen once for one pull request's pair, cause not established). Compare the
  lift inputs by hash, the HLE names, the profile and `image.bin` byte for byte, not only the key
  (`reports/tools/wincross/lift-identity.py` writes the identity record).
- A pairwise trial merge against a pull request that itself conflicts with main: `git merge-tree` cannot separate your
  hunks from theirs. Write a scratch commit (your resolved tree, parent main) with `git commit-tree` and merge that
  against each head: it costs only objects.

## Claims and issues

- No issue, and the pull request can be opened the same day: no issue. Its first paragraph and its Problem section carry
  what the issue would have said, and it names the review or pull request it follows.
- No issue, and the work takes longer or needs a decision before it starts (a feature, a change of behaviour): open one.
  Blank issues are switched off, so write the body with the form's own headings (`.forgejo/ISSUE_TEMPLATE/1-game-problem.yml`,
  `2-install-problem.yml`, `3-save-problem.yml`, `4-idea.yml`, read from the default branch) and end it with the claim.
  Small fixes of one kind share one issue. The maintainer may close it once the pull request exists. Main opens it with
  `reports/tools/ls_post.py issue --title-file <t> --body-file <b>`.
- Main announces claims and PRs through the project team-update tool, following its own `.claude/skills/team-updates/SKILL.md`,
  not a browser-form copy. Rows go into `reports/POSTED.md` and `reports/PR-INDEX.md`. The browser is only for Discord reads
  or a specifically named user-requested message.

## Imported authors

A whole unchanged cherry-pick keeps the same patch, author and message, committed by the user: do **not** append a
provenance line to that unchanged message. When only selected files can be carried, every touched file must be
byte-identical at the same path in the source tree, the author must match the source author, and the message must contain
`Imported from <owner>/<repo>#<n> at <source-hash>` (at least its first eight hex digits). Keep the original assistance
trailers; commit adaptations separately under our identity. Name the author and source in the handoff and body.

## Text and kits for testers on other machines

- Link the base repository, not the user's fork: the fork is not public (a signed-out visitor gets 404 and `git clone`
  asks for a user name), while the base repository serves every pull request head as `refs/pull/<n>/head`
  (`git fetch origin pull/<n>/head`) and as `<repository page>/src/commit/<sha>`. Fetch each link signed out
  (`curl -s -o /dev/null -w '%{http_code}'`) before it goes into a guide.
- A probe kit for the user's other machine (a reachability test, a log collector), as built once
  (`reports/drafts/mac-udp-kit/`): one standard-library script for the oldest Python that machine ships; a `--self-test`
  that needs no network; one report file with addresses cut; a plain-words verdict; a README that marks what never ran
  on that OS as [INFERENCE]. Run it first against the real service on loopback and from this PC.

## Pictures and clips

- ImageMagick `-annotate +x+y`: with `-gravity NorthWest` the string is placed by its ink top, so rows with and
  without ascenders drift; leave the gravity unset and `+x+y` is the baseline. `%` in the text must be `%%`, and a
  leading `@` reads a file.
- ffmpeg's concat demuxer repeats or ignores the last image's duration (seen once: a clip one frame too long); a
  numbered constant-rate sequence (`-framerate N -i %06d.jpg`) gives the exact length.
- A mockup for a design pull request (a menu page or a counter column that does not exist yet): write an SVG and render it
  with `rsvg-convert -o <png> <svg>`. A menu's own colours come from a guide picture
  (`docs/images/guide/settings-graphics.png`: page `#1E170F`, row `#392D1E`, row edge `#52422C`, gold `#EBA532`, text
  `#F0E8D6`, top bar `#AE8959`). `reports/LinkLook-files/01-look-page.svg` and `reports/Work562-files/mockup.py` (a
  generator, made-up numbers) are two; the caption says it is a mockup, not a screenshot.
- A contact sheet to find the right frames among many: `montage -label '%t' <every nth frame> -tile 6x -geometry
  426x240+2+2 sheet.jpg`.
