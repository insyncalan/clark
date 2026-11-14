#!/bin/bash
# Start clark with one double-click (row 1161), or in a Terminal: bash docker/start.command
# It tries Docker first. If Docker is not running, or will not start clark, it starts clark with Python instead (the same start as
# clark.command). Then it opens clark in Chrome, or tells you the address. It asks you nothing and waits for no key.
# Before Docker starts, it refuses a data folder inside OneDrive, Dropbox, iCloud Drive or Google Drive (row 512).
# Extra words typed after the command go on to docker compose up -d. Needs the python3 this Mac already has; nothing is installed.
here="${0%/*}"; case "$0" in */*) ;; *) here=. ;; esac
cd "$here/.." || exit 1
if [ -d .app ]; then check=.app/src/clark/starter_check.py; else check=src/clark/starter_check.py; fi
export PYTHONDONTWRITEBYTECODE=1
port="${CLARK_PORT-8766}"
say() { echo "$*"; }

if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
  say "clark needs Python 3.9 or newer, and this Mac does not have it. Install it from https://www.python.org/downloads/ and double-click this file again."
  exit 1
fi

# Python: the same start as clark.command. It opens Chrome (or your default browser) itself and says what it did.
start_with_python() {
  if [ -d .app ]; then PYTHONPATH="$PWD/.app${PYTHONPATH:+:$PYTHONPATH}"; export PYTHONPATH; fi
  exec python3 -m clark.launch
}

# Docker: only when it answers. docker info fails when Docker is not installed or its app is not running.
if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
  say "Docker is not running, so clark is starting without it."
  start_with_python
fi

say "Docker is running. Starting clark in Docker."
python3 "$check" --env-file "$PWD/docker/.env" || exit 1
if ! docker compose -f "$PWD/docker/compose.yaml" up -d "$@"; then
  say "Docker could not start clark, so clark is starting without it."
  start_with_python
fi

address="http://localhost:$port"
if curl -fsS --max-time 3 --retry 30 --retry-delay 1 --retry-connrefused "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
  say "clark is running in Docker."
else
  say "clark is still starting in Docker. If the page does not open, wait a minute and open $address again."
fi
if open -a "Google Chrome" "$address" >/dev/null 2>&1; then
  say "Opened clark in Chrome."
else
  say "Chrome was not found. To use clark, open this address in your browser: $address"
fi
