"""Row 1327 slice 2: Settings > Version and updates, the newest release inside clark (check, download, cancel), the page's side.
The routes are tests/test_release_fetch_1327.py and tests/test_updater.py. Classic, 1400 then 900. The words are logic/update.js FETCH.

Run: python3 dev/run_tests.py test_update_fetch_page_1327
"""
import unittest

from test_update_page import CONTRAST, OK, REVIEW, STATUS, InBrowser, lit

BASE = {**STATUS, "available": None, "line": None, "last": None}
AVAIL = {"state": "avail", "version": "0.3.2", "notes": "Faster Dashboard.", "checked": "19-11-2026 11:42", "date": "18-11-2026", "size": "38 MB"}
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
        self.assertIn("never installs by itself", self.text("#update-hint"))
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

    def test_not_now_puts_the_download_away(self):
        self.show(AVAIL, READY, cancel=OK({"ok": True}))
        self.click("[data-fetch-cancel]")
        self.assertEqual(self.calls(), ["status", "cancel", "status"])

    def test_up_to_date_and_offline_and_failed_each_have_their_line_and_their_button(self):
        self.show({"state": "latest", "checked": "19-11-2026 11:42"}, check=OK({"ok": True}))
        self.assertEqual(self.text("#update-line"), "You have the latest version (0.3.0). Last checked 19-11-2026 11:42.")
        self.click("[data-check]")
        self.assertEqual(self.calls(), ["status", "check", "status"])
        self.show({"state": "offline", "message": "Could not reach the releases page.", "checked": "x"})
        self.assertEqual(self.text("#update-line"), "Could not reach the releases page.")
        self.assertEqual(self.text("[data-check]"), "Try again")
        self.show(AVAIL, {"state": "failed", "version": "0.3.2", "message": "The download failed its check."})
        self.assertEqual(self.text("#update-line"), "The download failed its check.")
        self.assertEqual(self.text("[data-download]"), "Download again")

    def test_an_older_server_with_no_newest_block_draws_the_card_as_before(self):
        self.replies(status=OK(STATUS))
        self.mount()
        self.assertEqual(self.text("[data-review]"), "Review 0.3.1")
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
