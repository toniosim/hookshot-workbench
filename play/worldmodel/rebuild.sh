#!/bin/bash
# Rebuild the world model from an extracted RomFS: build.py, then flows.py, then story.py, from this folder.
#   WORLD_GAME=<extracted RomFS folder> ./rebuild.sh
# Needs the tables file (tables.json in the data folder, or $WORLD_TABLES: see tables.py). The data folder is
# $PILOT_WORLD, else world/ beside this folder's parent; the logs of the three steps go there too.
set -u
here=$(cd "$(dirname "$0")" && pwd)
: "${WORLD_GAME:?set WORLD_GAME to the extracted RomFS folder}"
data=${PILOT_WORLD:-$(dirname "$here")/world}
mkdir -p "$data" || exit 1
echo "start $(date '+%F %T') load $(cut -d' ' -f1-3 /proc/loadavg)"
for s in build flows story; do
    t0=$(date +%s)
    nice -n 19 python3 -I -u "$here/$s.py" --game "$WORLD_GAME" > "$data/logs-$s.log" 2>&1
    echo "$s exit $? seconds $(( $(date +%s) - t0 )) at $(date '+%T') load $(cut -d' ' -f1-3 /proc/loadavg)"
done
echo "end $(date '+%F %T')"
