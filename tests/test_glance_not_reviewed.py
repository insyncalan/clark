"""#160: "Not reviewed after (days)" in Settings and the optional Not reviewed tile, in a real browser.

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
        p.js("location.hash = '#settings&p=ABC'")
        p.until("!!document.querySelector('#review-days')", "the Freshness card drew")
        p.js("(() => { const el = document.querySelector('#review-days'); el.focus(); el.select(); })()")
        if text:
            p.type(text)
        else:
            p.key("Backspace", code="Backspace", vk=8)
        p.key("Enter", code="Enter", vk=13)

    def test_off_by_default_turned_on_by_the_eye_and_remembered(self):
        for width, dark in SIZES:
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.show(cdp, width, dark)
                self.assertEqual(self.stale(p), 0, "View has no Not reviewed tile until it is turned on")
                p.edit()
                p.until("!!document.querySelector('[data-tile=stale]')", "Edit draws the tile, dimmed")
                self.assertEqual(self.tiles(p), ["health", "overdue", "risks", "decisions", "stale"], "it comes last")
                self.assertTrue(p.js("document.querySelector('[data-tile=stale]').classList.contains('is-hidden')"))
                eye = "document.querySelector('[data-tile=stale] [data-tile-eye]')"
                self.assertEqual(p.js(f"{eye}.getAttribute('aria-pressed')"), "true")
                self.assertEqual(p.js(f"{eye}.getAttribute('aria-label')"), "Show Not reviewed on the Dashboard")
                self.assertEqual(p.js("document.querySelector('[data-tile=stale] .thid').textContent"), "Off. Never in the published report.")
                self.assertEqual(p.js("document.querySelectorAll('[data-tile=stale] [data-tile-grip]').length"), 0, "it is not moved")
                p.js(f"{eye}.click()")
                p.until("!document.querySelector('[data-tile=stale]').classList.contains('is-hidden')", "the eye turned it on")
                self.assertEqual(p.js(f"{eye}.getAttribute('aria-label')"), "Hide Not reviewed from the Dashboard")
                self.assertEqual(self.sent, [], "the eye asks the server for nothing")
                p.view()
                self.assertEqual(self.tiles(p), ["health", "overdue", "risks", "stale"])
                self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")
                p.reload()
                p.until("!!document.querySelector('[data-tile=stale]')", "still on after a reload")
                p.edit()
                p.js(f"{eye}.click()")
                p.until("document.querySelector('[data-tile=stale]').classList.contains('is-hidden')", "the eye turned it off")
                p.view()
                self.assertEqual(self.stale(p), 0)

    def test_the_count_and_its_text_are_readable_in_light_and_dark(self):
        script = """(() => {
          const rgb = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number);
          const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
          const ratio = (a, b) => { const x = lum(rgb(a)), y = lum(rgb(b)); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
          const out = [];
          for (const sel of ['.k', '.v', '.dd', '.thid']) {
            const el = document.querySelector('[data-tile=stale] ' + sel); if (!el) { out.push([sel, 0]); continue; }
            let bg = el, back = 'rgba(0, 0, 0, 0)';
            while (bg && /rgba\\(.*, 0\\)|transparent/.test(back)) { back = getComputedStyle(bg).backgroundColor; bg = bg.parentElement; }
            out.push([sel, ratio(getComputedStyle(el).color, back)]);
          }
          return out;
        })()"""
        for width, dark in SIZES:
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.show(cdp, width, dark)
                p.edit()
                p.until("!!document.querySelector('[data-tile=stale]')", "the tile drew")
                for sel, r in p.js(script):
                    self.assertGreaterEqual(r, 4.5, f"{sel} (0 means missing)")
                tag, fig = p.js("(() => { const t = document.querySelector('[data-tile=stale] .thid').getBoundingClientRect(), d = document.querySelector('[data-tile=stale] .dd').getBoundingClientRect(); return [t.top, d.bottom]; })()")
                self.assertGreaterEqual(tag, fig, "the tag sits under the detail, never over it")

    def test_the_count_is_the_list_it_opens_with_the_freshness_filter_on(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.js("localStorage.setItem('clark.glance.notReviewed.ABC', 'true')")
            p.reload()
            p.until("!!document.querySelector('[data-fig=stale]')", "the tile is on")
            self.assertEqual(self.expected(), 0, "ten days since review is not more than 14")
            self.assertEqual(p.js("document.querySelector('[data-fig=stale] .v').textContent"), "0")
            self.assertEqual(p.js("document.querySelector('[data-fig=stale] .dd').textContent"), f"Not reviewed for more than 14 days, of {self.open_items()} open items")
            self.assertEqual(p.js("document.querySelector('[data-fig=stale] .k').textContent"), "Not reviewed")
            self.assertTrue(p.js("document.querySelector('[data-fig=stale]').getAttribute('aria-label').endsWith('Opens Work items showing these')"))
            with self.store.step("dashboard", USER) as st:
                st.update("projects", "ABC", {"review_after_days": 7})
            p.reload()
            p.until("!!document.querySelector('[data-fig=stale]')", "the tile is on")
            want = self.expected()
            self.assertGreater(want, 0, "with 7 days every open item is not reviewed")
            self.assertEqual(want, self.open_items())
            self.assertEqual(p.js("document.querySelector('[data-fig=stale] .v').textContent"), str(want))
            self.assertEqual(p.js("document.querySelector('[data-fig=stale] .tw').textContent"), "To review")
            p.js("document.querySelector('[data-fig=stale]').click()")
            p.until("location.hash.startsWith('#work&p=ABC&f=')", "Work items opened")
            p.until(f"document.querySelectorAll('#work tbody tr[data-id]').length === {want}", f"the list holds the {want} it counted")
            chips = p.js("[...document.querySelectorAll('.fline .fchip .ft')].map(c => c.textContent)")
            self.assertEqual(chips, ["is:open", "is:quiet"], "the line shows the Freshness filter")

    def test_the_setting_changes_the_tile_and_the_filter_at_once_and_a_bad_value_keeps_the_old_one(self):
        for width, dark in SIZES:
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                with self.store.step("dashboard", USER) as st:
                    st.update("projects", "ABC", {"review_after_days": 14})
                del self.sent[:]
                p = self.show(cdp, width, dark)
                p.js("localStorage.setItem('clark.glance.notReviewed.ABC', 'true')")
                p.reload()
                p.until("document.querySelector('[data-fig=stale] .v') && document.querySelector('[data-fig=stale] .v').textContent === '0'", "0 at 14 days")
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
                p.js("location.hash = '#dashboard&p=ABC'")
                want = self.expected()
                p.until(f"document.querySelector('[data-fig=stale] .v') && document.querySelector('[data-fig=stale] .v').textContent === '{want}'", "the tile follows the number")
                self.assertEqual(p.js("document.querySelector('[data-fig=stale] .dd').textContent"), f"Not reviewed for more than 7 days, of {self.open_items()} open items")
                self.set_days(p, "1")
                p.saved()
                p.js("location.hash = '#dashboard&p=ABC'")
                p.until(f"document.querySelector('[data-fig=stale] .dd') && document.querySelector('[data-fig=stale] .dd').textContent === 'Not reviewed for more than 1 day, of {self.open_items()} open items'", "one day is singular")
                self.set_days(p, "7")
                p.saved()                     # the Undo toast of the save to 1 may still be up, so this alone does not mean 7 has landed:
                p.js("location.hash = '#dashboard&p=ABC'")
                p.until(f"document.querySelector('[data-fig=stale] .dd') && document.querySelector('[data-fig=stale] .dd').textContent === 'Not reviewed for more than 7 days, of {self.open_items()} open items'", "the page has the new number before the tile is clicked")
                self.assertEqual(self.project()["review_after_days"], 7)
                p.js("document.querySelector('[data-fig=stale]').click()")
                p.until("!!document.querySelector('#freshMenu')", "Work items with the Freshness filter")
                p.js("document.querySelector('#freshMenu').click()")
                p.until("!!document.querySelector('#freshMenu[aria-expanded=true]')", "the Freshness menu opened")
                names = p.js("[...document.querySelectorAll('[role=menu] [role^=menuitem]')].map(e => e.textContent.trim())")
                self.assertEqual(names[0], "Not reviewed in 7 days (on)", "the filter's value says the new number")

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
