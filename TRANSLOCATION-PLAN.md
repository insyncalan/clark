# App Translocation test plan for clark.app (#836)

Risk: macOS runs a quarantined app that was opened from where it was unzipped (not moved by the person in Finder) from a random read-only copy under /private/var/folders/.../AppTranslocation/. `path to me` then gives that path, so the applet looks for clark.command, `.app` (or src) and the data beside it and finds nothing.

What I tried (06-11, this Mac): I built the applet in a scratch folder (scratchpad/treeQ) and set `com.apple.quarantine` on a COPY with `xattr -w` (flags 0081, 00a1, 0181), then opened a path-reporting probe applet with `open -W`. Result: not reproducible unattended. For every flag value the open stopped at macOS's own "downloaded from the Internet" prompt (CoreServicesUIAgent, on screen), so the probe never ran and no path was reported. Setting the attribute does not skip Gatekeeper's first-open check for an ad-hoc-signed app. I dismissed the prompts (killed the agent); no real data folder, installed clark or setting was touched.

So the test needs a person at the screen and a really downloaded zip:
1. Build the zip with the applet inside (or add the applet beside clark.command by hand) and upload it as a private file, or AirDrop or download it to a second Mac or user account, so it carries the quarantine attribute for real.
2. In Downloads (not moved), unzip with Finder's double-click. Confirm: `xattr -l clark/clark.app` shows com.apple.quarantine.
3. Replace the applet with a probe once: the build script's `--test-data` build writes its result next to a scratch data folder; add a probe line that writes `POSIX path of (path to me)`. Double-click clark.app, choose Open when macOS asks. Record the path. If it starts with /private/var/folders/ and contains AppTranslocation, translocation happened.
4. With translocation: does the applet find the clark folder? Expected no (the translocated copy sits alone). Record the dialog text the person sees.
5. Same zip, but drag the clark folder from Downloads to Applications (or Desktop) first, then open. Record the path again. Expected: the real path, and clark starts (Finder's move clears translocation).
6. Same zip, run `xattr -dr com.apple.quarantine clark` first, then open. Expected: real path, starts. (This is the fallback to put in the words if needed.)
7. Same zip opened from a folder on an external or network volume. Record (translocation does not apply to some volumes).
8. If 4 fails, test both fixes on the same zip: (a) the program files inside clark.app/Contents/Resources so the applet needs nothing beside it; (b) the applet asks once for the clark folder (choose folder dialog) and remembers it in the data folder, never in the app. Record which works from Downloads with no move.
9. Each run uses a scratch --data folder and a scratch --port; clean up with `xattr -dr com.apple.quarantine` then delete the copy.
10. Pass: clark starts from Downloads on a fresh download with at most the one Gatekeeper "Open" click; or the failure comes with a dialog that says what to do in plain words.
