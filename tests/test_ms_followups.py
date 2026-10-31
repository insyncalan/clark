"""

Run: python3 dev/run_tests.py test_ms_followups
1. A milestone whose agreed or forecast date cannot be read gives no 'N days later' text (the rail read '20756 days later').
2. Escape shuts the Legend card and puts focus back on its button, at 1400 and 900 px, in light and dark.
3. The rail's rows stay list items: each li holds a button (role, keys, accessible name) and the list keeps its semantics.
The browser parts are required: they fail, never skip, without Chrome.
"""
import json
import shutil
import tempfile
import unittest

from _paths import SRC

from clark import page
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, bundled, load_demo, page_target

MODULE = SRC / "clark" / "page" / "src" / "logic" / "milestones.js"
TODAY = "2026-10-28"


def row(**kw):
    base = {"id": "X-M-001", "name": "A milestone", "status": "Planned", "baseline_date": None, "forecast_date": None,
            "actual_date": None, "state": None, "state_set": 0, "archived": 0, "sort_order": 0, "client_visible": 1}
    base.update(kw)
    return base


# Dates the page cannot read, and one real slip as the control.
BAD = [
    row(id="Y-M-001", name="Unreadable agreed date", baseline_date="soon", forecast_date="2026-12-14"),
    row(id="Y-M-002", name="Impossible agreed date", baseline_date="2026-13-45"),
    row(id="Y-M-003", name="No agreed date, a forecast", forecast_date="2026-12-14"),
    row(id="Y-M-004", name="Agreed date, unreadable forecast", baseline_date="2026-11-30", forecast_date="soon"),
    row(id="Y-M-005", name="Agreed date, a real slip", baseline_date="2026-11-30", forecast_date="2026-12-14"),
]


class UnreadableDates(unittest.TestCase):
    def test_an_unreadable_date_gives_no_days_later_text(self):
        script = (bundled(MODULE, "MS") + ";\n(" + """(c) => MS.milestoneRows(c.cases, c.today, false)
            .map((r) => ({ id: r.id, slip: r.slip, slipText: r.slipText, expected: r.expected }))""" + ")("
                  + json.dumps({"cases": BAD, "today": TODAY}) + ")")
        with chrome() as cdp:
            sid = page_target(cdp)
            res = cdp.call("Runtime.evaluate", {"expression": script, "returnByValue": True}, sid)
            assert "exceptionDetails" not in res, res
            got = {r["id"]: r for r in res["result"]["value"]}
        for case in BAD[:4]:
            with self.subTest(case["id"]):
                r = got[case["id"]]
                self.assertIsNone(r["slip"], "no slip number")
                self.assertIsNone(r["slipText"], "no 'N days later' text: the plain fallback, as for a row with no slip")
                self.assertIsNone(r["expected"], "no expected date")
        self.assertEqual(got["Y-M-005"]["slip"], 14, "the control still shows its slip")
        self.assertEqual(got["Y-M-005"]["slipText"], "14 days later")


DEMO_HASH = "#milestones&p=TUL"


class Browser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, _ = load_demo()
        cls.projects = cls.store.read("projects")

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def visit(self, cdp, width, dark):
        s = Running(data_for=self.store.data_for, projects=lambda: self.projects, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": "about:blank"}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/{DEMO_HASH}"}, sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.mv-wrap')", sid)), "the block drew")
        if dark:
            cdp.js("document.documentElement.dataset.theme = 'dark'", sid)
        return sid

    def key(self, cdp, sid, name, code, vk):
        for kind in ("keyDown", "keyUp"):
            cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": name, "code": code, "windowsVirtualKeyCode": vk}, sid)


class LegendEscape(Browser):
    def test_escape_shuts_the_legend_and_returns_focus_to_its_button(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    sid = self.visit(cdp, width, dark)
                    cdp.js("document.querySelector('.mlg-b').focus()", sid)
                    shown = "getComputedStyle(document.querySelector('.mlg-p')).visibility"
                    self.assertTrue(wait(lambda: cdp.js(shown, sid) == "visible"), "the card opens on focus")
                    self.key(cdp, sid, "Escape", "Escape", 27)
                    self.assertTrue(wait(lambda: cdp.js(shown, sid) == "hidden"), "Escape shuts the card")
                    self.assertTrue(cdp.js("document.activeElement.classList.contains('mlg-b')", sid), "focus is back on the Legend button")
                    self.assertTrue(cdp.js("document.querySelector('.mlg').classList.contains('mlg-shut')", sid))
                    self.assertEqual(cdp.js("getComputedStyle(document.querySelector('.mlg-p')).opacity", sid), "0", "shut card is clear")
                    # focus leaves the Legend, so it clears; focus back opens it again
                    cdp.js("document.querySelector('.mlg-b').blur()", sid)
                    self.assertTrue(wait(lambda: not cdp.js("document.querySelector('.mlg').classList.contains('mlg-shut')", sid)), "leaving clears the shut state")
                    cdp.js("document.querySelector('.mlg-b').focus()", sid)
                    self.assertTrue(wait(lambda: cdp.js(shown, sid) == "visible"), "focus opens it again")


class RailList(Browser):
    def test_each_row_is_a_list_item_with_a_button_inside_that_opens_by_keyboard(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    sid = self.visit(cdp, width, dark)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.msl-row .msl-cells')", sid)), "the rail drew")
                    self.assertEqual(cdp.js("[...document.querySelectorAll('ul.msl')].map(u => [...u.children].every(c => c.tagName === 'LI' && !c.getAttribute('role')))", sid),
                                     [True], "the list's children are plain list items")
                    self.assertEqual(cdp.js("document.querySelectorAll('ul.msl > li.msl-row > .msl-cells[role=button][tabindex=\"0\"]').length", sid),
                                     cdp.js("document.querySelectorAll('ul.msl > li.msl-row').length", sid), "a button inside every row")
                    self.assertEqual(cdp.js("document.querySelectorAll('li[role=button]').length", sid), 0, "no row is a button itself")
                    # the accessible name starts with the visible words (the milestone's name, then its state word)
                    names = cdp.js("[...document.querySelectorAll('.msl-cells')].map(b => [b.getAttribute('aria-label'), b.querySelector('.msl-name').textContent])", sid)
                    self.assertTrue(names)
                    for label, visible in names:
                        self.assertTrue(label.startswith(visible), f"{label!r} starts with {visible!r}")
                    # keyboard: focus the first row's button and press Enter; the peek opens for that milestone
                    cdp.js("document.querySelector('.msl-row .msl-cells').focus()", sid)
                    first = cdp.js("document.querySelector('.msl-row').dataset.ms", sid)
                    self.key(cdp, sid, "Enter", "Enter", 13)
                    self.assertTrue(wait(lambda: f"ms={first}" in cdp.js("location.hash", sid)), "Enter opens that milestone")
                    cdp.js("location.hash = '#milestones&p=TUL'", sid)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.msl-row .msl-cells')", sid)))
                    cdp.js("document.querySelector('.msl-row .msl-cells').focus()", sid)
                    self.key(cdp, sid, " ", "Space", 32)
                    self.assertTrue(wait(lambda: f"ms={first}" in cdp.js("location.hash", sid)), "Space opens it too")


if __name__ == "__main__":
    unittest.main()
