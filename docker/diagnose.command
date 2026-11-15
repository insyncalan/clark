#!/bin/bash
# Show what a Docker start of clark sees (row 1164): the data folder, what is in it, both data versions, the container and its last log lines.
# Run it in a Terminal: bash docker/diagnose.command   Nothing is changed.
here="${0%/*}"; case "$0" in */*) ;; *) here=. ;; esac
cd "$here/.." || exit 1
if [ -d .app ]; then check=.app/src/clark/starter_check.py; else check=src/clark/starter_check.py; fi
export PYTHONDONTWRITEBYTECODE=1
python3 "$check" --env-file "$PWD/docker/.env" --diagnose
echo "Container:"
docker compose -f "$PWD/docker/compose.yaml" ps 2>&1
echo "Last log lines:"
docker compose -f "$PWD/docker/compose.yaml" logs --tail 20 2>&1
