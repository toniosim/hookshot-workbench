# On the LS forge

LS's pull requests live on the team's forge; the GitHub-era `gh` routes and scripts are gone (the upstream answers 404):

```sh
REPO=MagicBeanDev/Longshot
API=https://git.magicbean.dev/api/v1/repos/$REPO
FORGE="python -I /home/tonesi/Tooling/scripts/forge.py --repo $REPO"   # this machine: Tooling is cloned beside the game clone; run it from /home/tonesi/Hookshot
```

- **Posting is Main's.** *This machine has no `ls_post.py`* (the author's helper): `$FORGE` does every post, `pr create` with
  `--tested-in-game` where it asks for it. The author's `ls_post.py` has `pr`, `update` and `issue`: no
  comment-only command, no title edit, no `--tested-in-game`; it refuses a body with `/home/`, an `hs-` tool name or
  `agent://` (a posted test description names no local path and no tool). `$FORGE` does the rest (`scripts/forge.py` in the
  game repository only forwards to it, and `--repo` goes **before** the subcommand): `$FORGE pr comment N`,
  `pr edit N --title T`, `pr ready N` (runs the description check), `pr status N`, `search WORD ... --state all`.
  `pr create` for a branch that touches `gpu/`, `host/`, `nx2/`, `assets/` or `third_party/` needs
  `--tested-in-game "<where it ran and what was seen>"`, even for a game-free engine the game does not build; `--force`
  only when the person asks.
  `ls_post.py` is bound to the game's repository (`REPO`; a post to another repository of the organisation needs another
  route) and does `os.chdir` into the main worktree when imported: a script that imports it writes relative paths there,
  so give absolute ones.
- **`pr create` has no `--base`**: it opens a pull request from a branch of your fork into the repository's main, as WIP
  unless `--ready` (which runs the description check). A stacked follow-up cannot open onto another pull request's
  branch: its draft says it opens after the base merges. The `--tested-in-game` rule is main's (`AGENTS.md`): a series
  that touches those folders needs a game run per pull request, so plan the runs before the series.
- **Reading** the public repository needs no credential: `GET $API/pulls/N`, `pulls/N.diff`, `pulls/N/files`,
  `pulls/N/reviews`, `issues/N/comments`, `issues/N/timeline`, `issues/comments/<id>`, `statuses/<sha>`. A 403 means
  stop and tell Main; do not look for a credential. `pr://N` and `issue://N` are GitHub routes and do not read the forge,
  and the page reader of a pull request or comment URL returns only the feed's one-line title: take the body and reviews
  from `pulls/N` and `pulls/N/reviews`, a comment from `issues/comments/<id>`.
  Python's `urllib` is refused with 403 even for public reads: read with `curl`, and a 403 from `curl` is the stop above.
  The timeline is paged (`issues/N/timeline?limit=50&page=K`, `X-Total-Count`); its `pull_push` events name the pusher
  (`user`) and say in `body` whether it was a force-push, which settles who pushed last.
- **The issue-comments endpoint is not paged**: `page=2` returns the same list, so a `page` loop never ends. Count
  unique ids against the `X-Total-Count` header, and read `pulls/N/reviews` and the inline discussions separately. The
  list endpoints are paged (`pulls?state=open&limit=50&page=N`, at most 50 a page; 242 were open on 2026-11-15).
- **Overlaps**: take each open pull request's `pulls/N/files`, fetch the heads of those that share files with yours (`git fetch forge
  +refs/pull/N/head:refs/remotes/pr/N`; `refs/pull/*/head` is 1,239 refs, closed pull requests too, and took 4.5 minutes
  and a shared lock where the 112 candidates took under a second) and run
  `git merge-tree --write-tree --name-only <base> <head>` against your branch **and** against forge main: only a conflict
  that appears with your branch is an overlap (21 of 38 already conflicted with main). Without Git against the forge
  remote, apply each public `.diff` with `git apply --check` to pinned main and to your branch and compare. A page list
  that stops at its limit, or a Git error, is an incomplete answer, not a clean one.
- **The description** is checked by `scripts/check_pr_description.py` of the checkout (see `SKILL.md`, "The body"); a
  pull request is work in progress (`WIP:` title) until `pr ready N` passes it.
- **Another person's pull request**: body, comments, reviews and `pulls/N/files` from the API; the head with
  `git fetch forge pull/N/head` in the forge-main clone; its CI from `$API/commits/<sha>/statuses?limit=100`, taking the
  **latest status per `context`** (older rows stay `pending`; `commits/<sha>/status` is the combined view).
  The API's `mergeable` is `false` for every `WIP:` title (131 of 131 on 17 Nov): a "not mergeable" work-in-progress pull
  request needs a `git merge-tree` against main, not a rebase.
- **What CI covers**: read `.forgejo/workflows/ci.yml` before saying. A pull request runs the title check, the
  description check and the guide-screenshot check; the Python source checks are `workflow_dispatch` only ("off for
  now") and no Windows runner exists. A fork pull request gets CircleCI only after a maintainer adds the label
  `ci: approved` (`docs/ci.md`). "Skipped" and "no CircleCI status" are normal, not a result. The forge's pre-push check
  is the description checker plus `pr create`; no script compares a branch with main (read `git merge-tree`), and none
  of the GitHub-era readers (`hs-pr-ci.sh`, `hs-fork-ci.sh`, `hs-pr-check.sh`) works any more.
  A context can read **`Has been cancelled`** (the description check did on a head): a superseded duplicate, not a result;
  read the latest status per `context` and ignore the cancelled ones. A pull request whose CI never started (only the
  description check after 50 minutes) gets it when Main closes and reopens the pull request (nine contexts then ran). The
  guide-screenshot check can be red on main itself (since #1309): `python3 -I -B scripts/check_guide_screenshots.py
  --review-sources` runs it offline on a `git archive`, so read which rows fail before blaming a head.
- **The checker's less obvious rules**: the description's **first line** is the status line, `**Type:** <the title's type> ·
  **Risk:** low|medium|high · **Tested on:** <OS, GPU> · **Needs:** <OS, GPU, or none>` (`Risk:` is exactly low, medium or
  high; a type unlike the title's, or a `Needs:` that disagrees with `Must be tested`, only warns); a before column that is
  not main, or an after column that is not this PR,
  needs a `Baseline:` line; each `Must be tested` item reads `<where>: <steps>, expecting <result>` and says who
  (`@Beanstalk ...` or by hand); a line starting with `#` inside a fenced block (a shell comment) ends the section it is
  in; in `--pr` mode a `Before: main @ <hash>` that is not the merge base is warned about. A revert's commit message is
  this form too (`git log --grep='^revert(' -3` on main shows one). The checker does not count characters: keep a
  description under 65,000 (`wc -m`; the forge's limit as two drafters reported it). The template moves: run the checker
  again on every old draft after a rebase (eleven errors found once).
- **Other repositories of the organisation**: the Beanstalk repository and its wiki clone without a token
  (`https://git.magicbean.dev/MagicBeanDev/Beanstalk.git`, `.../Beanstalk.wiki.git`; the live wiki is newer than a copy
  in `reports/`). The data-service repositories (`DataServicesAPI`, `DataServicesInfra`) are pull mirrors with pull
  requests switched off (`/pulls` answers 404; the repository record has `mirror: true` and an `original_url`, the forge
  where their pull requests are). A mirror's `refs/pull/*/head` lists the heads; a head that is an ancestor of `main` is
  merged.
  A public shallow clone of `DataServicesAPI` works (`telemetry/perf/` holds the performance relay and its tests): the
  relay's code can be read there.
