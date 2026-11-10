"""#160: "Not reviewed after (days)" in Settings, in a real browser; row 910: the Not reviewed tile is gone.

Run: python3 dev/run_tests.py test_glance_not_reviewed
The page is the committed one, served by a real server whose change route is the real clark.changes over a real store in a temporary
folder (fictional data). The store's clock is set ten days ahead, so every item was last reviewed ten days ago: with 14 days none is
not reviewed, with 7 every open one is. Laptop widths only: 1400 and 900 px, light and dark. Chrome is required: these tests fail,
never skip, without it.
"""
import json
import unittest
from datetime import date, timedelta
from unittest import mock

from _demo import USER
from clark import history, store as store_module
from test_glance_page import Setup
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

AHEAD = (date.today() + timedelta(days=10)).isoformat()
REFUSED = "Choose a whole number of days from 1 to 365. Nothing was changed."
CLOSED = ("Closed", "Cancelled", "Made", "Withdrawn")
SIZES = ((1400, False), (1400, True), (900, False), (900, True))


class NotReviewed(Setup):
    def setUp(self):
        clock = mock.patch.object(store_module, "today", return_value=AHEAD)
        clock.start()
        self.addCleanup(clock.stop)
        super().setUp()

    def expected(self):
        """The open items the store itself calls not reviewed now, at the project's own number."""
        d = self.store.data_for("ABC")
        return sum(1 for t in ("actions", "raid", "decisions") for r in d.get(t) or []
                   if not r.get("archived") and r.get("status") not in CLOSED and (r.get("freshness") or {}).get("not_reviewed"))

    def open_items(self):
        d = self.store.data_for("ABC")
        return sum(1 for t in ("actions", "raid", "decisions") for r in d.get(t) or [] if not r.get("archived") and r.get("status") not in CLOSED)

    def stale(self, p):
        return p.js("document.querySelectorAll('[data-tile=stale]').length")

    def set_days(self, p, text):
        """Open Settings, put `text` in the box and press Enter."""
        p.js("location.hash = '#settings&p=ABC&s=reports'")
        p.until("!!document.querySelector('#review-days')", "the Freshness card drew")
        p.js("(() => { const el = document.querySelector('#review-days'); el.focus(); el.select(); })()")
        if text:
            p.type(text)
        else:
            p.key("Backspace", code="Backspace", vk=8)
        p.key("Enter", code="Enter", vk=13)

    def test_there_is_no_not_reviewed_tile_in_view_or_edit_even_with_an_old_browser_flag(self):
        """Row 910: the tile is gone. A flag an older page left in this browser is ignored; the four stored tiles are all there is."""
        for width, dark in SIZES:
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.show(cdp, width, dark)
                p.js("localStorage.setItem('clark.glance.notReviewed.ABC', 'true')")
                p.reload()
                p.until("document.querySelectorAll('.glance > .tcell').length > 0", "the tiles drew")
                self.assertEqual(self.stale(p), 0, "View has no Not reviewed tile")
                self.assertEqual(p.js("document.querySelectorAll('[data-fig=stale]').length"), 0)
                self.assertEqual(self.tiles(p), ["health", "overdue", "risks"], "View: the shown stored tiles only")
                p.edit()
                self.assertEqual(self.tiles(p), ["health", "overdue", "risks", "decisions"], "Edit: the four stored tiles, no Not reviewed tile")
                self.assertEqual(self.stale(p), 0)

    def test_a_bad_value_keeps_the_old_one_and_a_good_one_is_saved(self):
        for width, dark in SIZES:
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                with self.store.step("dashboard", USER) as st:
                    st.update("projects", "ABC", {"review_after_days": 14})
                del self.sent[:]
                p = self.show(cdp, width, dark)
                for bad in ("0", "abc", "14.5", ""):
                    self.set_days(p, bad)
                    p.until(f"(document.querySelector('[data-review-days-bad]') || {{}}).textContent === {json.dumps(REFUSED)}", f"{bad!r} is refused in plain words")
                    self.assertEqual(p.js("document.querySelector('#review-days').value"), "14", "the box shows the old number again")
                    self.assertEqual(p.js("document.querySelector('#review-days').getAttribute('aria-invalid')"), "true")
                    self.assertEqual(self.project()["review_after_days"], 14, "nothing was changed")
                self.assertEqual(self.sent, [], "a refused value is never sent")
                self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")
                self.set_days(p, "7")
                p.saved()
                self.assertEqual(self.project()["review_after_days"], 7)
                self.assertEqual(p.js("document.querySelector('[data-review-days-bad]').textContent"), "", "the refusal went once a good number was saved")
                self.assertEqual(p.js("document.querySelector('#review-days').value"), "7")

    def test_the_history_says_who_how_and_when_the_number_changed(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.set_days(p, "21")
            p.saved()
            rows = [r for r in history.view_for_project(self.store.con, "ABC")["rows"] if r["table"] == "projects" and r["field"] == "Not reviewed after (days)"]
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual((row["from"], row["to"], row["who"], row["kind"]), ("14", "21", USER, "Changed"))
            self.assertEqual(row["how"], history.HOW_TABLE)
            self.assertRegex(row["when"], r"^\d{2}-\d{2}-\d{4} \d{2}:\d{2}$")
            self.undo(p)
            self.assertEqual(self.project()["review_after_days"], 14, "Undo puts the old number back")

    def test_the_published_file_has_no_not_reviewed_tile(self):
        """The file carries no freshness (main's Freshness filter and is:quiet are the editor's alone), so the tile is never in it."""
        from pathlib import Path
        import tempfile
        from clark import publish
        from test_report_editor import EMPTY_BRANDING
        from test_server import wait
        from test_work_items import page_target
        with self.store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"review_after_days": 7})
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(__import__("shutil").rmtree, folder, True)
        done = publish.publish(self.store, "ABC", folder, by_user=USER, now=AHEAD, branding=EMPTY_BRANDING)
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.navigate", {"url": Path(done["path"]).as_uri()}, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.glance')", sid)), "the file drew its tiles")
            self.assertEqual(cdp.js("document.querySelectorAll('[data-tile=stale], [data-fig=stale]').length", sid), 0)
            held = cdp.js("document.getElementById('clark-data').textContent", sid)
            for word in ("review_after_days", "not_reviewed", "last_reviewed"):
                self.assertNotIn(word, held, "the file's data holds no freshness")


if __name__ == "__main__":
    unittest.main()
