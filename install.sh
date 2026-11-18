#!/usr/bin/env bash
# Puts this checkout's tools where its scripts expect them on this machine, as SYMLINKS back into the checkout (so an
# edit here is live at once, and `git diff` here shows every local change). Makes the work folders and the local
# switches. Idempotent: run it again after pulling. Never overwrites a real file: an existing non-link is reported.
#
#   ./install.sh            install / refresh
#   ./install.sh --check    say what is missing, change nothing
#
#   ~/Games/.hookshot-harness/          hs-*.sh, hs-*.py, tools/deps-local.sh, playthrough/, regress/, nightly/,
#                                       runs.log, gpu-slots (=1), live/, saves/ (local, empty: saves are game data)
#   ~/Games/hs-{gpu,intel,build}-slot, ~/Games/.hookshot-harness/gpu-guard.sh   the gates and the guard
#   ~/.claude/skills/ls-*               the skills, for Claude Code (all but ls-discord-updates: posting to
#                                       Discord as you through your browser is against Discord's terms; link it
#                                       yourself if you decide otherwise). Upstream renamed them hookshot-* -> ls-*
#                                       on 2026-11-17: a stale hookshot-* link into this checkout is removed.
#   ~/.local/bin/magick                 tools/magick6, only while there is no real `magick` (ImageMagick 6 here)
#   ~/hookshot-wt/{reports,reports/drafts}   worktrees and reports; reports/AGENT-BRIEF.md -> docs/agent-brief.md
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
check=0; [ "${1:-}" = --check ] && check=1
G=$HOME/Games; H=$G/.hookshot-harness; S=$HOME/.claude/skills; WT=$HOME/hookshot-wt
miss=0
dir() { [ -d "$1" ] && return; if [ "$check" = 1 ]; then echo "missing dir  $1"; miss=1; else mkdir -p "$1"; fi; }
link() {   # target link
    if [ -L "$2" ] && [ "$(readlink "$2")" = "$1" ]; then return; fi
    if [ -e "$2" ] && [ ! -L "$2" ]; then echo "NOT A LINK   $2 (left alone; move it away and run again)"; miss=1; return; fi
    if [ "$check" = 1 ]; then echo "missing link $2 -> $1"; miss=1; else ln -sfn "$1" "$2"; echo "linked $2"; fi
}
file() {   # path content
    [ -e "$1" ] && return
    if [ "$check" = 1 ]; then echo "missing file $1"; miss=1; else printf '%s\n' "$2" > "$1"; echo "made $1"; fi
}

dir "$H"; dir "$H/tools"; dir "$H/playthrough"; dir "$H/regress"; dir "$H/nightly"; dir "$H/live"; dir "$H/saves"
dir "$S"; dir "$WT/reports/drafts"
for f in "$here"/harness/*; do
    case $f in */__pycache__) continue ;; esac
    case $f in */deps-local.sh) link "$f" "$H/tools/deps-local.sh" ;; *) link "$f" "$H/$(basename "$f")" ;; esac
done
for f in "$here"/play/*.py; do link "$f" "$H/playthrough/$(basename "$f")"; done
for f in "$here"/regress/*.py; do link "$f" "$H/regress/$(basename "$f")"; done
for f in "$here"/nightly/*; do link "$f" "$H/nightly/$(basename "$f")"; done
link "$here/perf" "$H/perf"                   # hs_perf.py, read by ls-perf-monitor
for g in hs-gpu-slot hs-intel-slot hs-build-slot; do link "$here/gates/$g" "$G/$g"; done
link "$here/gates/gpu-guard.sh" "$H/gpu-guard.sh"
for s in "$here"/skills/ls-*; do
    [ "$(basename "$s")" = ls-discord-updates ] && continue
    link "$s" "$S/$(basename "$s")"
done
for old in "$S"/hookshot-*; do      # the pre-rename links: only ones that point into this checkout, never a real folder
    [ -L "$old" ] || continue
    case $(readlink "$old") in "$here"/skills/hookshot-*) ;; *) continue ;; esac
    if [ "$check" = 1 ]; then echo "stale link   $old (the skill is ls-${old##*/hookshot-} now)"; miss=1; else rm "$old"; echo "removed stale link $old"; fi
done
for old in "$H"/* "$H"/*/*; do        # links this checkout no longer has (a file upstream removed or renamed)
    [ -L "$old" ] && [ ! -e "$old" ] || continue
    case $(readlink "$old") in "$here"/*) ;; *) continue ;; esac
    if [ "$check" = 1 ]; then echo "dangling    $old"; miss=1; else rm "$old"; echo "removed dangling link $old"; fi
done
# ImageMagick 6 has no `magick`: the author's play/ and regress/ tools call it (tools/magick6 maps it to convert & co)
if ! { command -v magick > /dev/null 2>&1 && [ ! -L "$HOME/.local/bin/magick" ]; }; then dir "$HOME/.local/bin"; link "$here/tools/magick6" "$HOME/.local/bin/magick"; fi
link "$here/docs/agent-brief.md" "$WT/reports/AGENT-BRIEF.md"
file "$H/gpu-slots" 1                       # one game at a time (the gate enforces it on this machine anyway)
file "$WT/reports/LOG.md" "# Mistakes and guard lines, one dated line each"
[ -e "$H/runs.log" ] || { [ "$check" = 1 ] || : > "$H/runs.log"; }
if [ "$check" = 1 ]; then [ "$miss" = 0 ] && echo "install: complete" || { echo "install: incomplete"; exit 1; }; fi
