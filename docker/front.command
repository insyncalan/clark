#!/bin/bash
# clark served from Docker, with clark itself on the Mac (item 1100). Run it in a Terminal in the clark folder:
#   bash docker/front.command server    start clark's own server on this Mac (leave the window open)
#   bash docker/front.command           check the server, then start the web server in Docker
#   bash docker/front.command stop      stop the web server in Docker
# CLARK_PORT is the port you open (default 8766), CLARK_SERVER_PORT the one clark's server uses on this Mac (default 8767),
# CLARK_DATA_DIR the data folder (default ~/Library/Application Support/clark, the same as clark.command). Nothing else is read.
here="${0%/*}"; case "$0" in */*) ;; *) here=. ;; esac
cd "$here/.." || exit 1
export PYTHONDONTWRITEBYTECODE=1
port="${CLARK_PORT-8766}"; sport="${CLARK_SERVER_PORT-8767}"
data="${CLARK_DATA_DIR-$HOME/Library/Application Support/clark}"

say() { echo "$*" >&2; }
# A port is 1024 to 65535, digits only, no leading zero (so nothing typed can reach a command or the proxy's settings file, and the
# browser's own spelling of the port, which never has a zero in front, is the one the proxy matches).
valid_port() { case "$1" in ""|0*|*[!0-9]*) return 1 ;; esac; [ "${#1}" -le 5 ] && [ "$1" -ge 1024 ] && [ "$1" -le 65535 ]; }
valid_port "$port" || { say "CLARK_PORT must be a number from 1024 to 65535."; exit 1; }
valid_port "$sport" || { say "CLARK_SERVER_PORT must be a number from 1024 to 65535."; exit 1; }
[ "$port" != "$sport" ] || { say "CLARK_PORT and CLARK_SERVER_PORT must be two different numbers (both are $port)."; exit 1; }
if [ -d .app ]; then check=.app/src/clark/starter_check.py; else check=src/clark/starter_check.py; fi
# The same refusal as the other routes: no OneDrive, Dropbox, iCloud Drive or Google Drive data folder (before anything starts).
CLARK_DATA_DIR="$data" python3 "$check" || exit 1

case "$1" in
  server)
    # clark's own server on this Mac: it listens on 127.0.0.1 only. A refusal (newer data, data folder in use) ends it; it is never restarted.
    [ -d .app ] && PYTHONPATH="$PWD/.app${PYTHONPATH:+:$PYTHONPATH}" && export PYTHONPATH
    export CLARK_PUBLISHED_PORT="$port" CLARK_TYPED="bash docker/front.command server"
    exec python3 -m clark --data "$data" --port "$sport"
    ;;
  stop)
    exec docker compose -f "$PWD/docker/compose.front.yaml" down
    ;;
  "")
    command -v docker >/dev/null 2>&1 || { say "Docker is not installed or not on this Mac's path. Use the Terminal route instead: bash clark.command"; exit 1; }
    # The Mac's server must already answer, so a front never starts alone and shows only a "not running" page.
    if ! curl -fsS --max-time 3 "http://127.0.0.1:$sport/health" 2>/dev/null | grep -q '"ok"'; then
      say "clark is not running on this Mac yet (nothing answers on 127.0.0.1:$sport)."
      say "Open another Terminal window in this folder and type: bash docker/front.command server"
      say "When it says it is running, type bash docker/front.command here again."
      exit 1
    fi
    export CLARK_PORT="$port" CLARK_SERVER_PORT="$sport"
    docker compose -f "$PWD/docker/compose.front.yaml" up -d || { say "Docker could not start. clark itself is still running: open http://127.0.0.1:$sport instead, or use bash clark.command."; exit 1; }
    echo "Open http://localhost:$port to use clark."
    ;;
  *)
    say "Type: bash docker/front.command server, or bash docker/front.command, or bash docker/front.command stop"
    exit 1
    ;;
esac
