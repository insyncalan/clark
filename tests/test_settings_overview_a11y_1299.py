"""Row 1299 slice 2: Settings > Projects overview, the empty and failed states and the reading structure (names, roles, scopes) a screen reader uses.
Killers for the words and roles in Overview.jsx; the contract of the page itself is in test_settings_overview_1299.py (its helpers are reused here).

Run: python3 dev/run_tests.py test_settings_overview_a11y_1299
Chrome is required: the browser tests fail, never skip, without it. Widths 1400 and 900 only.
"""
import unittest
from unittest import mock

from _editor_checks import for_url
from clark import overview_read, server as sv
from test_server import chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target

import test_settings_overview_1299 as base

NONE_WORDS = "No projects yet."
FAILED_WORDS = "The projects could not be read. Choose Try again. If it happens again, restart clark."
COLUMNS = ["Project", "Asking", "Brand", "Read folders", "Review days", "Client folder", "Last backup"]


class OverviewReading(unittest.TestCase):
    setUpClass = classmethod(base.Overview.setUpClass.__func__)
    tearDownClass = classmethod(base.Overview.tearDownClass.__func__)
    serve = base.Overview.serve
    visit = base.Overview.visit
    until = base.Overview.until
    listed = base.Overview.listed
    chip = base.Overview.chip

    def open_plain(self, cdp, port, width):
        """Open the overview without waiting for table rows (an empty or failed read has none)."""
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": "about:blank"}, sid)
        cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{port}/#settings&p={self.codes[0]}&s=overview")}, sid)
        self.until(cdp, sid, "document.querySelector('#overview-h')", "the overview heading")
        return sid

    def test_no_projects_says_so_and_draws_no_table_chips_or_banner(self):
        for width in base.WIDTHS:
            s = self.serve()
            none = mock.patch.object(overview_read, "overview", return_value={"ok": True, "asking": True, "last_backup": None, "projects": [], "archived_count": 0})
            none.start()
            self.addCleanup(none.stop)
            with chrome() as cdp:
                sid = self.open_plain(cdp, s.port, width)
                self.until(cdp, sid, f"document.querySelector('#overview').innerText.includes('{NONE_WORDS}')", "the no projects words")
                self.assertFalse(cdp.js("document.querySelector('#overview').innerText.includes('Looking for your projects.')", sid))
                for sel in ("#overview-table", "button[data-filter]", "#overview-attention", "[role=alert]"):
                    self.assertIsNone(cdp.js(f"document.querySelector('{sel}')", sid), f"{sel} at {width}")

    def test_a_read_that_fails_says_so_in_an_alert_and_try_again_reads_again(self):
        s = self.serve()
        busy = mock.patch.object(overview_read, "overview", side_effect=sv.Busy("The project file is being restored."))       # the route answers 503; /api/projects is untouched
        busy.start()
        self.addCleanup(busy.stop)
        with chrome() as cdp:
            sid = self.open_plain(cdp, s.port, 1400)
            self.until(cdp, sid, "document.querySelector('#overview [role=alert]')", "the alert")
            self.assertEqual(cdp.js("document.querySelector('#overview [role=alert]').innerText.replace(/\\s+/g, ' ').trim()", sid), FAILED_WORDS + " Try again")
            self.assertIsNone(cdp.js("document.querySelector('#overview-table')", sid), "no table over a failed read")
            self.assertFalse(cdp.js("document.querySelector('#overview').innerText.includes('No projects yet.')", sid), "a failed read is not an empty list")
            busy.stop()
            cdp.js("document.querySelector('#overview [role=alert] button').click()", sid)
            self.until(cdp, sid, f"document.querySelectorAll('#overview-table tbody tr[data-project]').length === {len(self.rows)}", "the table after Try again")
            self.assertIsNone(cdp.js("document.querySelector('#overview [role=alert]')", sid))

    def test_the_table_the_chips_and_the_banner_have_names_and_roles(self):
        for width in base.WIDTHS:
            s = self.serve()
            with chrome() as cdp:
                sid = self.visit(cdp, s.port, width)
                got = cdp.js("(function(){ var t = document.querySelector('#overview-table'); var g = document.querySelector('.ov-chips');"
                             " return {label: t.getAttribute('aria-label'), heads: [...t.tHead.rows[0].cells].map(c => [c.tagName, c.textContent.trim(), c.getAttribute('scope')]),"
                             " group: [g.getAttribute('role'), g.getAttribute('aria-label')], banner: document.querySelector('#overview-attention').getAttribute('role'),"
                             " heading: document.querySelector('#overview-h').tagName}; })()", sid)
                self.assertEqual(got["label"], "Projects overview", width)
                self.assertEqual(got["heads"], [["TH", c, "col"] for c in COLUMNS], width)
                self.assertEqual(got["group"], ["group", "Show"])
                self.assertEqual(got["banner"], "status")
                self.assertEqual(got["heading"], "H2")

    def test_every_value_is_a_real_link_the_keyboard_reaches_and_nothing_else_is_in_the_rows(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.visit(cdp, s.port, 1400)
            got = cdp.js("[...document.querySelectorAll('#overview-table tbody td a')].map(e => [e.tagName, e.tabIndex, !!e.getAttribute('href')])", sid)
            self.assertEqual(len(got), len(self.rows) * 7, "seven values in each row, each a link")
            self.assertEqual(set(map(tuple, got)), {("A", 0, True)})
            self.assertEqual(cdp.js("document.querySelectorAll('#overview-table tbody button, #overview-table tbody input, #overview-table tbody [role=switch]').length", sid), 0)

    def test_the_chips_say_which_one_is_on_and_only_one_is_on(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.visit(cdp, s.port, 900)
            self.assertEqual([self.chip(cdp, sid, w)[1] for w in ("all", "attn")], ["true", "false"])
            cdp.js("document.querySelector('button[data-filter=attn]').click()", sid)
            self.until(cdp, sid, "document.querySelector('button[data-filter=attn]').getAttribute('aria-pressed') === 'true'", "the chip to turn on")
            self.assertEqual([self.chip(cdp, sid, w)[1] for w in ("all", "attn")], ["false", "true"])




class OverviewReplyShape(unittest.TestCase):
    setUpClass = classmethod(base.Overview.setUpClass.__func__)
    tearDownClass = classmethod(base.Overview.tearDownClass.__func__)
    serve = base.Overview.serve
    visit = base.Overview.visit
    until = base.Overview.until
    listed = base.Overview.listed
    chip = base.Overview.chip
    open_plain = OverviewReading.open_plain

    def test_a_reply_with_no_projects_list_is_a_failed_read_not_an_empty_one(self):
        s = self.serve()
        odd = mock.patch.object(overview_read, "overview", return_value={"ok": True, "asking": True, "last_backup": None})
        odd.start()
        self.addCleanup(odd.stop)
        with chrome() as cdp:
            sid = self.open_plain(cdp, s.port, 1400)
            self.until(cdp, sid, "document.querySelector('#overview [role=alert]')", "the alert")
            self.assertFalse(cdp.js("document.querySelector('#overview').innerText.includes('No projects yet.')", sid))

    def test_asking_that_is_not_true_or_false_reads_not_known_and_a_blank_client_folder_reads_not_set(self):
        s = self.serve()
        row = {"code": self.codes[0], "name": self.names[self.codes[0]], "brand": "b", "review_days": 7, "client_folder": "   ", "read_folders": 2}
        odd = mock.patch.object(overview_read, "overview", return_value={"ok": True, "asking": "yes", "last_backup": None, "projects": [row], "archived_count": 0})
        odd.start()
        self.addCleanup(odd.stop)
        with chrome() as cdp:
            sid = self.visit(cdp, s.port, 1400)
            cells = cdp.js("[...document.querySelector('#overview-table tbody tr[data-project]').cells].map(c => c.innerText.trim())", sid)
            self.assertEqual(cells[1], "not known", "a text is not on or off")
            self.assertEqual(cells[5], "Not set", "spaces only is no client folder")
            self.assertIn("has no client folder", cdp.js("document.querySelector('#overview-attention').innerText", sid))


if __name__ == "__main__":
    unittest.main()
