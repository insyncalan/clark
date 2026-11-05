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
# In a download the program files are in one hidden folder, ".app", beside this file (issue 694); in a source checkout they are "src"
# and "clark" beside it. An update swaps ".app" (a download) or "src" and "clark" (a checkout) by moving the old one into .clark-old-<time> and then the new one in. If the Mac stopped between
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
if [ ! -e .app ] && { [ ! -e src ] || [ ! -e clark ]; }; then
  stamp=$(python3 -c 'import json, re, sys
try:
    s = json.load(open(sys.argv[1] + "/updates/.installing.json", encoding="utf-8")).get("stamp")
    print(s if isinstance(s, str) and re.fullmatch(r"[0-9A-Za-z]+", s) else "")
except Exception:
    print("")' "$data" 2>/dev/null)
fi
if [ -n "$stamp" ]; then
  for part in .app src clark; do
    if [ ! -e "$part" ] && [ -d ".clark-old-$stamp/$part" ]; then
      mv ".clark-old-$stamp/$part" "$part"
    fi
  done
fi
# A download: the program files are in .app. The folder stays this one (so a relative --data means what it always did, and can
# never land inside .app, which an update replaces), and python3 -m finds the stand-in package in .app through PYTHONPATH.
if [ -d .app ]; then PYTHONPATH="$PWD/.app${PYTHONPATH:+:$PYTHONPATH}"; export PYTHONPATH; fi
# These are typed in a Terminal, so they run as python3 -m would, and they give back their own exit code and wording.
case "$1" in
  --check) shift; python3 -m clark.doctor "$@"; exit $? ;;
  restore) python3 -m clark "$@"; exit $? ;;
esac
for arg in "$@"; do
  case "$arg" in --demo) python3 -m clark "$@"; exit $? ;; esac
done
python3 -m clark.launch "$@"
status=$?
if [ "$status" -ne 0 ]; then
  echo
  read -r -n 1 -p "Press any key to close this window. " _
fi
exit "$status"
