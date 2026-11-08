#!/usr/bin/env bash
# build_app.sh: build clark.app, a small applet that starts clark with no Terminal window (#836, Phase 1). Run BY HAND on a Mac; it
# installs nothing, writes only into the folder you name, and the .app is never committed.
#
#   dev/tools/build_app.sh [OUTPUT_FOLDER]          builds OUTPUT_FOLDER/clark.app (default: a new scratch folder, printed)
#
# The applet is osacompile's (built into every Mac). It finds the folder it sits in, runs  /usr/bin/python3 -m clark.launch  there,
# hidden, and on any failure shows the launcher's own lines in a native dialog. Nothing is stopped by the applet: the server stops
# itself a minute after the last window closes (idle.py). It sits BESIDE clark.command and needs the same folder (a download's .app
# folder, or a checkout's src): see TRANSLOCATION-PLAN.md for what that means for a quarantined download.
#
# Test build only (never for a shipped app): --test-data FOLDER --test-port N  bake a scratch data folder and port into the applet,
# and CLARK_BROWSER=/usr/bin/true (a stub, so no window opens) and write the dialog text to FOLDER/../applet-out.txt instead of
# showing it, so the applet can be run unattended.
#
# Exit codes: 0 built, 1 stopped (the reason is said).
set -u

out="" test_data="" test_port="" port_given=""
while [ $# -gt 0 ]; do
  case "$1" in
    --test-data) test_data="${2:-}"; shift 2 ;;
    --test-port) test_port="${2:-}"; port_given=1; shift 2 ;;
    -*) echo "build_app.sh: unknown option $1" >&2; exit 1 ;;
    *) out="$1"; shift ;;
  esac
done
# Both values are pasted into the applet's source (the port into a shell command, the folder into an AppleScript string), so
# only plain values pass: ASCII digits for the port; no double quote, backslash or line break in the folder.
if [ -n "$port_given" ]; then
  case "$test_port" in
    ''|*[!0123456789]*) echo "build_app.sh: --test-port must be digits only (0-9)." >&2; exit 1 ;;
  esac
fi
case "$test_data" in
  *'"'*|*'\'*|*$'\n'*|*$'\r'*) echo "build_app.sh: --test-data must not contain a double quote, a backslash or a line break." >&2; exit 1 ;;
esac
if [ "$(uname -s)" != "Darwin" ] || ! command -v osacompile >/dev/null 2>&1; then
  echo "build_app.sh: osacompile (macOS) is needed." >&2
  exit 1
fi
[ -n "$out" ] || out="$(mktemp -d "${TMPDIR:-/tmp}/clark-app.XXXXXX")" || exit 1
mkdir -p "$out" || exit 1
if [ -e "$out/clark.app" ]; then
  echo "build_app.sh: $out/clark.app is already there. Name another folder or move it aside." >&2
  exit 1
fi

extra="" env_stub="" report='display dialog msg buttons {"OK"} default button "OK" with icon caution'
if [ -n "$test_data" ] || [ -n "$test_port" ]; then
  extra="\" & \" --data \" & quoted form of \"$test_data\" & \" --port $test_port"
  env_stub=" CLARK_BROWSER=/usr/bin/true"
  report='do shell script "printf %s " & quoted form of msg & " > " & quoted form of "'"$test_data"'.applet-out.txt"'
fi

src="$(mktemp "${TMPDIR:-/tmp}/clark-applet.XXXXXX")" || exit 1
trap 'rm -f "$src"' EXIT
# The python check and its two lines are clark.command's own words. The remaining lines of that message name clark.command and
# need new wording (NEW-WORDS.md), so the applet says only the first two.
cat > "$src" <<APPLESCRIPT
on run
	set appPath to POSIX path of (path to me)
	set clarkFolder to do shell script "dirname " & quoted form of (text 1 thru -2 of appPath)
	set needPython to "This Mac needs Python 3.9 or newer to run clark, and doesn't have it yet." & return & "Apple's free Command Line Tools include it. If a window just asked to install them, choose Install."
	try
		do shell script "/usr/bin/python3 -c 'import sys; sys.exit(sys.version_info < (3, 9))'"
	on error
		set msg to needPython
		$report
		return
	end try
	set cmd to "cd " & quoted form of clarkFolder & " && export PYTHONDONTWRITEBYTECODE=1 CLARK_TYPED='bash clark.command'$env_stub && if [ -d .app ]; then export PYTHONPATH=\"\$PWD/.app\"; fi && /usr/bin/python3 -m clark.launch$extra 2>&1"
	try
		do shell script cmd
	on error msg
		$report
	end try
end run
APPLESCRIPT

if ! osacompile -o "$out/clark.app" "$src"; then
  echo "build_app.sh: osacompile stopped." >&2
  exit 1
fi
echo "Built $out/clark.app"
