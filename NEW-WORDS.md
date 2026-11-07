# Words that do not exist yet (for approval). Nothing here is in shipped text.

The prototype shows only existing lines. These are what the owner would need to approve first.

## Task A (opening in Chrome)
1. Opened line. Today: "Opened clark in its own window." It is now a tab in the Chrome window, not its own window.
   Proposed: "Opened clark in Chrome." (kept unchanged in the prototype)
2. Doctor line. Today (doctor.py:142): "Chrome is there, so clark opens in its own window." Proposed: "Chrome is there, so clark opens in Chrome."
3. Doctor line (doctor.py:143) and launcher line (launch.py:210) end "Install Chrome to give clark its own window." Proposed ending: "Install Chrome to open clark there."

## Task C (the applet)
4. Python missing, applet version. The two reused lines are clark.command's. Its last lines name clark.command ("double-click clark.command again", "type xcode-select --install in this window"). Proposed ending: "When that has finished, open clark again."
5. Launcher lines that say "Close this window" or "double-click clark.command" (launch.py:92 and :193, the launcher's "report") are wrong in an app dialog. Proposed app versions:
   - "Nothing was started: clark is already open, or another program is using the connection it needs. Close it, then open clark again."
   - "Nothing opened, because clark did not finish starting. Open clark again. If it still does not start, send the file {log} to the clark team. It records what went wrong."
6. Dialog button: "OK" (a macOS word; no clark wording needed, listed for completeness).
7. Folder not found (if the applet is moved away from its folder): "clark can't find its files. Keep clark.app in the clark folder, beside clark.command."

## Task D (setup page; each is a line the page would show)
8. Heading: "Setting up clark" and button "Check again".
9. Dropbox / iCloud Drive / Google Drive data folder: "Your clark data is set to go in {folder}, which is inside {Dropbox}. It copies files while they are being written, which damages the data. Choose a folder on this computer that it doesn't sync." (the OneDrive line, doctor.py:125-130, names OneDrive only)
10. "Everything is ready. Opening clark." (shown once all checks pass)
11. Per-check status words reuse the doctor's READY / ADVICE / FIX markers; the page needs a label for each: "Ready", "Worth fixing", "Needs fixing" (the doctor's own marker words are in doctor.py; check them before approving these labels).
12. Setup mode notice: "clark is in setup mode. Nothing is saved until the checks below pass."
