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
python3 -m clark.launch "$@"
status=$?
if [ "$status" -ne 0 ]; then
  echo
  read -r -n 1 -p "Press any key to close this window. " _
fi
exit "$status"
