#!/bin/bash
# Start clark with Docker (item 427), after checking the data folder (row 512). Run it in a Terminal: bash docker/start.command
# It refuses a data folder inside OneDrive, Dropbox, iCloud Drive or Google Drive BEFORE the container starts, then runs
# docker compose -f docker/compose.yaml up -d with whatever else you typed. Needs the python3 this Mac already has; nothing is installed.
here="${0%/*}"; case "$0" in */*) ;; *) here=. ;; esac
cd "$here/.." || exit 1
# The check is one file with no imports from clark, run by its path (a download keeps src in .app).
if [ -d .app ]; then check=.app/src/clark/starter_check.py; else check=src/clark/starter_check.py; fi
export PYTHONDONTWRITEBYTECODE=1
python3 "$check" || exit 1
exec docker compose -f "$PWD/docker/compose.yaml" up -d "$@"
