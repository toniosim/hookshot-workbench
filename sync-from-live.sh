#!/usr/bin/env bash
# Copies the tools and skills from where they live on my machine into this checkout, then runs publish-check.sh.
# It commits nothing and pushes nothing: read `git diff`, then commit.
#
#   ./sync-from-live.sh
#
# What is copied is listed here on purpose, file by file: nothing reaches this repository by a wildcard. To publish a
# new tool, add it to the list, run this, read publish-check.sh's output and the diff.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
H=/home/mooki/Games/.hookshot-harness
S=/home/mooki/.agents/skills

for s in hookshot-workbench hookshot-pr-evidence hookshot-perf-compare hookshot-scripted-play hookshot-issue-triage \
         hookshot-discord-updates hookshot-regression-hunt; do
    rm -rf "$here/skills/$s"
    cp -r "$S/$s" "$here/skills/$s"
done
mkdir -p "$here/harness" "$here/gates" "$here/play" "$here/docs" "$here/regress"
cp "$H/hs-run.sh" "$H/hs-idle.sh" "$H/hs-nocore.sh" "$H/hs-pr-check.sh" "$H/hs-save.sh" "$H/hs-watch-ends2.sh" \
   "$H/hs-watch-threads.py" "$H/hs-window.py" "$H/tools/deps-local.sh" "$here/harness/"
cp /home/mooki/Games/nx2navi-gpu-slot /home/mooki/Games/nx2navi-intel-slot /home/mooki/Games/nx2navi-build-slot \
   /home/mooki/Games/.nx2navi-harness/gpu-guard.sh "$here/gates/"
cp "$H/playthrough/hsap.py" "$H/playthrough/tapcheck.py" "$H/playthrough/test_hsap.py" "$here/play/"
cp "$H/regress/regress.py" "$H/regress/build_case.py" "$H/regress/run_case.py" "$H/regress/test_regress.py" "$here/regress/"
cp /home/mooki/Code/hookshot-wt/reports/AGENT-BRIEF.md "$here/docs/agent-brief.md"
find "$here" -name __pycache__ -prune -exec rm -rf {} +

"$here/publish-check.sh"
git -C "$here" status --short
