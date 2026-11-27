"""Row 1327 slice 2: Settings > Version and updates, the newest release inside clark (check, download, cancel), the page's side.
The routes are tests/test_release_fetch_1327.py and tests/test_updater.py. Classic, 1400 then 900. The words are logic/update.js FETCH.

Run: python3 dev/run_tests.py test_update_fetch_page_1327
"""
import unittest

import _paths  # noqa: F401
from clark import updates
from test_update_page import CONTRAST, OK, REVIEW, STATUS, InBrowser, lit

BASE = {**STATUS, "available": None, "line": None, "last": None}
AVAIL = {"state": "avail", "version": "0.3.2", "notes": "Faster Dashboard.", "checked": "19-11-2026 11:42", "date": "18-11-2026", "size": "38 MB"}
LABELS = "[...document.querySelectorAll('#update .upd-l')].map(e => e.textContent)"
QUIET = "The newest version is looked up quietly when you open this card and when you choose Check now. It never installs by itself."
FAILED = "It was not installed and nothing changed. Try the download again; if it happens again, use a file from the releases page."
OFFLINE = "clark could not reach the releases page. Check your connection, or use a file you downloaded."
READY = {"state": "ready", "version": "0.3.2", "review_id": "r9", "review": {**REVIEW, "added": {"label": "Added", "names": ["a", "b"]},
         "replaced": {"label": "Replaced", "names": ["c"]}, "removed": {"label": "Removed", "names": []}}}


def status(latest=None, fetch=None):
    return OK({**BASE, "latest": latest, "fetch": fetch or {"state": "idle"}})


class Fetch(InBrowser):
    def show(self, latest=None, fetch=None, **more):
        self.replies(status=status(latest, fetch), **more)
        self.mount()

    def test_a_newer_release_is_ready_to_download_and_the_download_button_starts_it(self):
        self.show(AVAIL, download=OK({"ok": True}))
        self.assertEqual(self.text("#update-line"), "Version 0.3.2 is ready to download.")
        self.assertEqual(self.text("[data-download]"), "Download")
        self.assertEqual(self.text("[data-check]"), "Check now")
        self.assertIn("never installs by itself", self.text("#update-checked"))      # Row 1327 table row 2: the sentence is in the Last checked row
        self.assertIn("Faster Dashboard.", self.text("#update-notes"))
        self.click("[data-download]")
        self.assertEqual(self.calls(), ["status", "download", "status"], "one click starts the download and asks again; nothing is installed")

    def test_a_refused_download_says_why_and_changes_nothing_else(self):
        self.show(AVAIL, download=OK({"ok": False, "code": "no_latest"}, 409))
        self.click("[data-download]")
        self.assertEqual(self.text(".pub-msg"), self.val("T.logic.WORDS.no_latest"))
        self.assertEqual(self.calls(), ["status", "download", "status"])

    def test_the_bar_shows_the_percent_and_cancel_stops_it(self):
        self.show(AVAIL, {"state": "downloading", "version": "0.3.2", "pct": 41}, cancel=OK({"ok": True}))
        self.assertEqual(self.text("#update-line"), "Downloading version 0.3.2")
        self.assertEqual(self.val("document.querySelector('[role=progressbar]').getAttribute('aria-valuenow')"), "41")
        self.assertEqual(self.val("document.querySelector('[role=progressbar] i').style.width"), "41%")
        self.assertEqual(self.text("#update-pct"), "41%")
        self.assertIn("You do not need to sign in", self.text("#update-hint"))
        self.assertFalse(self.present("[data-download]"))
        self.click("[data-fetch-cancel]")
        self.assertEqual(self.calls(), ["status", "cancel", "status"])

    def test_the_page_asks_again_while_it_downloads_and_shows_the_checked_download_with_install_as_a_second_click(self):
        self.js("T.pollMs = 40; T.n = 0")
        self.js(f"T.replies.status = () => {{ T.n += 1; const f = T.n < 3 ? {{state: 'downloading', version: '0.3.2', pct: 10 * T.n}} : {lit(READY)};"
                f" return {{status: 200, body: Object.assign({lit({**BASE, 'latest': AVAIL})}, {{fetch: f}})}}; }}")
        self.js(f"T.replies.install = {{status: 200, body: {{ok: true, restart: true, message: 'x'}}}}; T.replies.who = 'new'")
        self.mount()
        self.cdp.call("Runtime.evaluate", {"expression": "new Promise(r => setTimeout(r, 400))", "awaitPromise": True}, self.sid)
        self.assertEqual(self.text("#update-line"), "Version 0.3.2 is downloaded and checked.")
        self.assertEqual(self.text("#update-hint"), "Will add 2 files, replace 1, remove 0. You can undo it afterwards.")
        self.assertNotIn("install", self.calls(), "nothing is installed by itself")
        self.click("[data-fetch-install]")
        self.assertEqual(self.val("T.calls.filter(c => c[0] === 'install')"), [["install", "r9"]])
        self.assertEqual(1, self.val("T.reloads"))

    def each(self, status):
        for width in (1400, 900):
            with self.subTest(width=width):
                self.load(width=width)
                self.replies(status=OK(status))
                self.mount()
                yield width

    def today(self):
        return self.val("T.logic.dayText(new Date())")

    def test_the_ready_card_line_reads_released_date_and_size(self):
        for _ in self.each({**BASE, "latest": AVAIL, "fetch": {"state": "idle"}}):
            self.assertEqual("Released 18-11-2026 · 38 MB.", self.text("#update-released"))
            self.assertEqual("Your projects, settings and published reports are kept.", self.text("#update-kept"))
            self.assertIn("Faster Dashboard.", self.text("#update-notes"))
            self.assertEqual(["Installed", "Update", "Last checked", "Use a file instead"], self.val(LABELS))
            self.assertTrue(self.val("document.documentElement.scrollWidth <= document.documentElement.clientWidth"))


    def test_the_ready_card_line_without_a_size_has_no_mb(self):
        for _ in self.each({**BASE, "latest": {**AVAIL, "size": ""}, "fetch": {"state": "idle"}}):
            self.assertEqual("Released 18-11-2026.", self.text("#update-released"))
        for _ in self.each({**BASE, "latest": {**AVAIL, "date": ""}, "fetch": {"state": "idle"}}):
            self.assertFalse(self.present("#update-released"))
        for _ in self.each({**BASE, "latest": {**AVAIL, "size": ""}, "fetch": {"state": "idle"}}):
            self.assertNotIn("MB", self.text("#update-released"))
            self.assertNotIn("unknown", self.text("#update-released"))


    def test_the_last_checked_row_today_older_and_not_checked_yet(self):
        for _ in self.each({**BASE, "latest": {**AVAIL, "checked": f"{self.today()} 11:42"}, "fetch": {"state": "idle"}}):
            self.assertEqual("Today 11:42. " + QUIET, self.text("#update-checked p"))
            self.assertEqual("Check now", self.text("#update-checked [data-check]"))
            self.assertFalse(self.present("#update-row [data-check]"), "the button is in its own row")
        for _ in self.each({**BASE, "latest": AVAIL, "fetch": {"state": "idle"}}):
            self.assertEqual("19-11-2026 11:42. " + QUIET, self.text("#update-checked p"))
        for _ in self.each({**BASE, "latest": {"state": "looking"}, "fetch": {"state": "idle"}}):
            self.assertEqual("Not checked yet.", self.text("#update-checked p"))
            self.assertEqual("Check now", self.text("#update-checked [data-check]"))


    def test_the_installed_row_names_the_new_version_and_offers_undo(self):
        last = {"from": "0.3.0", "to": "0.3.1", "line": "Last update: 0.3.0 → 0.3.1 on 01-11-2026."}
        for _ in self.each({**BASE, "last": last}):
            self.assertEqual("Updated to clark 0.3.1", self.text("#update-last-l"))
            self.assertEqual("Everything was kept when clark restarted. If something looks wrong you can go back to 0.3.0.", self.text("#update-last p"))
            self.assertEqual("Undo", self.text("#update-last [data-undo]"))
            self.assertEqual("Undo update", self.val("document.querySelector('#update-last [data-undo]').getAttribute('aria-label')"))
        for _ in self.each({**BASE, "last": {"line": "Last update: x."}}):
            self.assertEqual("Last update", self.text("#update-last-l"))
            self.assertEqual("x.", self.text("#update-last p"))


    def test_the_failed_check_has_its_title_text_and_download_again(self):
        for _ in self.each({**BASE, "latest": AVAIL, "fetch": {"state": "failed", "version": "0.3.2", "message": FAILED}}):
            self.assertEqual("The download failed its check", self.text("#update-row-l"))
            self.assertEqual(FAILED, self.text("#update-line"))
            self.assertEqual("Download again", self.text("#update-row [data-download]"))
        for _ in self.each({**BASE, "latest": AVAIL, "fetch": {"state": "failed", "version": "0.3.2", "message": "The check did not finish. Try again."}}):
            self.assertEqual("Update", self.text("#update-row-l"), "only a failed check takes the failed-check title")


    def test_a_failed_signature_shows_the_approved_sentence_in_full_at_1400_and_900(self):
        sentence = "The download failed its check. It was not installed."
        self.assertEqual(sentence, updates.MESSAGES["badsig"], "the words the app sends")
        # The row title is not asserted: Update.jsx:208 gives "The download failed its check" only for FAILED_TEXT, so a badsig message shows "Update" (reported on row 1328).
        for _ in self.each({**BASE, "latest": AVAIL, "fetch": {"state": "failed", "version": "0.3.2", "message": updates.MESSAGES["badsig"]}}):
            self.assertEqual(sentence, self.text("#update-line"))
            self.assertEqual("Download again", self.text("#update-row [data-download]"))
            self.assertTrue(self.val("(e => e.scrollWidth <= e.clientWidth && e.scrollHeight <= e.clientHeight + 1)(document.querySelector('#update-line'))"), "the sentence is not clipped")
            self.assertTrue(self.val("document.documentElement.scrollWidth <= document.documentElement.clientWidth"))

    def test_not_now_puts_the_download_away(self):
        self.show(AVAIL, READY, cancel=OK({"ok": True}))
        self.click("[data-fetch-cancel]")
        self.assertEqual(self.calls(), ["status", "cancel", "status"])

    def test_up_to_date_and_offline_and_failed_each_have_their_line_and_their_button(self):
        self.show({"state": "latest", "checked": "19-11-2026 11:42"}, check=OK({"ok": True}))
        self.assertEqual(self.text("#update-line"), "You have the latest version (0.3.0). Last checked 19-11-2026 11:42.")
        self.assertEqual("Update", self.text("#update-row-l"))
        self.click("[data-check]")
        self.assertEqual(self.calls(), ["status", "check", "status"])
        self.show({"state": "latest", "checked": f"{self.today()} 11:42"})
        self.assertEqual(self.text("#update-line"), "You have the latest version (0.3.0). Last checked today 11:42.")
        self.show({"state": "offline", "message": OFFLINE, "checked": "x"})
        self.assertEqual(self.text("#update-line"), OFFLINE)
        self.assertEqual(self.text("[data-check]"), "Try again")
        self.show(AVAIL, {"state": "failed", "version": "0.3.2", "message": FAILED})
        self.assertEqual(self.text("#update-line"), FAILED)
        self.assertEqual(self.text("#update-row-l"), "The download failed its check")
        self.assertEqual(self.text("[data-download]"), "Download again")

    def test_an_older_server_with_no_newest_block_draws_the_card_as_before(self):
        self.replies(status=OK(STATUS))
        self.mount()
        self.assertEqual(self.text("[data-review]"), "Review")      # Row 1327 table row 3
        self.assertFalse(self.present("[data-check]") or self.present("[data-download]"))

    def test_every_state_fits_and_reads_at_1400_and_900(self):
        states = [(AVAIL, None), (AVAIL, {"state": "downloading", "version": "0.3.2", "pct": 41}), (AVAIL, READY),
                  (AVAIL, {"state": "failed", "version": "0.3.2", "message": "The download failed its check."}),
                  ({"state": "latest", "checked": "x"}, None), ({"state": "offline", "message": "Offline.", "checked": "x"}, None)]
        for width in (1400, 900):
            for theme in ("light", "dark"):
                for latest, fetch in states:
                    with self.subTest(width=width, theme=theme, fetch=(fetch or {}).get("state"), latest=latest["state"]):
                        self.load(width=width, theme=theme)
                        self.show(latest, fetch)
                        self.assertTrue(self.val("document.documentElement.scrollWidth <= document.documentElement.clientWidth"))
                        self.assertTrue(self.val("[...document.querySelectorAll('#update button')].every(b => b.getBoundingClientRect().right <= innerWidth)"))
                        worst = self.val(f"Math.min(...[...document.querySelectorAll('#update p, #update summary')]"
                                         f".filter(e => e.textContent.trim()).map({CONTRAST}))")
                        self.assertGreaterEqual(worst, 4.5)


if __name__ == "__main__":
    unittest.main()
