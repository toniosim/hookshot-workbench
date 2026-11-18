# Workbench repository checks (not the game suite)

Reference for `SKILL.md`; read it when you change this tools repository (the harness, drivers, skills, MCP server).

This tools repository has no `tests/run_all.py` or checked-in CI workflow. From its reviewed checkout (the repository
the skills are published from, or your own worktree of it; the agent brief names its folder), run the direct drivers
separately: generic unittest discovery misses the plain-assert play drivers, and rolling must use this checkout's rules.
The loop takes about one minute; the MCP suite below about four.

```sh
set -e
ulimit -S -c 0
for test in tests/test_*.py harness/test_*.py play/test_*.py play/*/test_*.py perf/test_*.py regress/test_*.py nightly/test_*.py skills/*/scripts/test_*.py; do
  if [ "$test" = nightly/test_rolling.py ]; then
    python3 -I -B "$test" --shared-dir "$PWD/regress"
  else
    python3 -I -B "$test"
  fi
done
python3 -I -B nightly/test_compare.py --mutations
node --test skills/ls-discord-updates/scripts/test_discord_tab.mjs
python3 -I -B skills/ls-skill-upkeep/check_skills.py --root skills
python3 -I -B name_policy.py
bash publish-check.sh
```

For MCP, install the selected checkout's package metadata and locked dev dependencies into its own environment;
`PYTHONPATH` alone is insufficient. Do not borrow another checkout's editable package registration.
Use the pinned Python 3.12 for the current fixtures: Python 3.14's automatic Unix-socket cleanup breaks the
stale-socket broker fixture before its production assertion; retain that failure rather than weakening the check.

```sh
uv sync --locked --project mcp --python "$P"
TEST_TMP=$(mktemp -d /tmp/ls-wb-tests.XXXXXX)
TMPDIR="$TEST_TMP" uv run --project mcp --locked --no-sync python -B -m pytest -q -p no:cacheprovider mcp/tests --basetemp "$TEST_TMP/pytest"
```

Fixture state must have **no `.git` ancestor**; keep `TMPDIR` and pytest's base outside all repositories. Suppress
cores with the soft limit only, not `ulimit -c 0` or a hard-zero wrapper: the MCP worker sets `(1, 1)`.
An offline setup needs the locked packages already cached. A setup failure is not a test result. These suites use
synthetic fixtures, not a game, live gate or account. Keep every failed attempt and its setup correction.
Run `uv sync --locked` again after every branch switch: a worktree's `mcp/.venv` keeps the package name of the branch it
was synced on, and `workbench_status` then fails with `backend_failed` (`PackageNotFoundError`) and six tests fail.
A registered session launch that fails with `refused_by_policy path_read` and no path means the operator's read roots
lack the harness folder (`hs_names.py`) or the gate: that is configuration, not a game fault.
Publication maps are in `publish.py`; repository-only tests are not automatically installed into the live harness.

Publication traps (`publish-check.sh`): a folder named `world/` is private data to the repository (`.gitignore`, check 1):
code for the world model lives in `worldmodel/`. A fake key such as `sk-test-...` in a test matches check 3 (a key or token):
build it at run time. The private word list (check 6) has short words, so an ordinary variable name can contain one: when
check 6 flags a line you did not expect, rename the variable.
