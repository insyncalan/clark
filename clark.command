#!/bin/bash
# clark: double-click this file to start clark and open its window (#71). Run it again to open another window.
# It runs clark's launcher with the Python this Mac already has. Nothing is installed or downloaded.
case "$0" in */*) cd "${0%/*}" || exit 1 ;; esac      # the folder this file is in (the Terminal may be anywhere)
if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
  echo
  echo "This Mac needs Python 3.9 or newer to run clark, and doesn't have it yet."
  echo "Apple's free Command Line Tools include it. If a window just asked to install them, choose Install."
  echo "Otherwise type this in this window: xcode-select --install"
  echo "When that has finished, double-click clark.command again."
  echo
  read -r -n 1 -p "Press any key to close this window. " _
  exit 1
fi
# An update swaps "src" and "clark" by moving the old one into .clark-old-<time> and then the new one in. If the Mac stopped between
# the two moves, one of them is missing and nothing below could start. Put the old one back first; the launcher then finishes
# the update the usual way (it puts everything else back too). Only a missing folder is touched, and only from the folder the
# update's own marker names: with no marker (or an older set-aside folder left over), nothing is put back.
data="$HOME/Library/Application Support/clark"
prev=""
for arg in "$@"; do
  case "$prev" in --data) data="$arg" ;; esac
  case "$arg" in --data=*) data="${arg#--data=}" ;; esac
  prev="$arg"
done
stamp=""
if [ ! -e src ] || [ ! -e clark ]; then
  stamp=$(python3 -c 'import json, re, sys
try:
    s = json.load(open(sys.argv[1] + "/updates/.installing.json", encoding="utf-8")).get("stamp")
    print(s if isinstance(s, str) and re.fullmatch(r"[0-9A-Za-z]+", s) else "")
except Exception:
    print("")' "$data" 2>/dev/null)
fi
if [ -n "$stamp" ]; then
  for part in src clark; do
    if [ ! -e "$part" ] && [ -d ".clark-old-$stamp/$part" ]; then
      mv ".clark-old-$stamp/$part" "$part"
    fi
  done
fi
python3 -m clark.launch "$@"
status=$?
if [ "$status" -ne 0 ]; then
  echo
  read -r -n 1 -p "Press any key to close this window. " _
fi
exit "$status"
