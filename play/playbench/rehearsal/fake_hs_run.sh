#!/bin/bash
# Stands in for hs-run.sh in a rehearsal (no game, no GPU gate, no model): hsap calls it as `hs-run.sh <copy> <tag> <wall> [--user <save>] K=V...`.
# It starts the fake game (fake_game.py, a real-time simulated bridge) for <wall> seconds at the control socket and live file hsap asked for.
set -u
copy=$1; tag=$2; wall=$3; shift 3
ctl=""; live=""
while [ $# -gt 0 ]; do
    case "$1" in
        HOS_CONTROL=*) ctl=${1#*=} ;;
        HOS_INPUT_LIVE=*) live=${1#*=} ;;
        --user) shift ;;
    esac
    shift
done
exec timeout --signal=TERM "$wall" python3 -I -B "$(dirname "$0")/fake_game.py" "$ctl" "$live" "$copy/runs/$tag" "${REHEARSE_SCENARIO:?}"
