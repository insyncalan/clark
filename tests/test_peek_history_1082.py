"""Row 1082 added 'Show history' under the peek's Latest update; row 1258 (the owner, 16-11: "mockup rules") removed it, because the peek's
history tabs (PeekActivity.jsx PeekHistory, the Updates tab) list the changes of that one field. This file now holds that.
Run: python3 dev/run_tests.py test_peek_history_1082

Cards is frozen (WO-M10803): the removal is Classic only. Part 1 is the source: the component and its style stay (Cards draws them), and the
box draws the link only when classicTheme() is false. Part 2 is the page in a real browser at 1400 and 900 px, light and dark: seven stored changes of
the Latest update; Classic (the <style id="theme"> layer) has no Show history link and the Updates tab counts and lists exactly those seven, newest
first, drawn as text; Cards (no layer) still draws the Show history link, unchanged.
"""
import json
import shutil
import unittest

from _editor_checks import for_url
from _paths import ROOT
import _testpage as testpage

from clark import activity_read, changes, sneak  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402

SRC = ROOT / "src" / "clark" / "page" / "src"
ITEM = "TUL-A-002"
LAYER = "(function(){var s=document.createElement('style'); s.id='theme'; document.head.appendChild(s);})()"


class Source(unittest.TestCase):
    def test_the_link_is_drawn_for_cards_only_and_its_component_and_style_stay(self):
        self.assertTrue((SRC / "edit" / "PeekLatestHistory.jsx").exists())
        box = (SRC / "edit" / "PeekLatest.jsx").read_text(encoding="utf-8")
        self.assertIn("classicTheme()", box)
        self.assertIn("{classic ? null : <PeekLatestHistory", box)
        self.assertIn(".pk-lh-btn", (SRC / "edit" / "edit.css").read_text(encoding="utf-8"), "Cards keeps its style: edit.css is not edited")


class Browser(unittest.TestCase):
    def load(self, cdp, width, dark=False, classic=True):
        self.store, folder, ids = load_demo()
        self.code = next(iter(ids))
        self.addCleanup(lambda: (self.store.close(), shutil.rmtree(str(folder), ignore_errors=True)))
        change = changes.make_change(self.store.path, [], "Demo User")
        for n in range(1, 8):
            self.assertEqual(change({"project": self.code, "kind": "actions", "op": "update", "id": ITEM, "changes": {"latest_update": f"Version {n} <b>x</b>"}, "place": "peek"})[0], 200)
        change({"project": self.code, "kind": "actions", "op": "update", "id": ITEM, "changes": {"owner": "Someone Else"}, "place": "peek"})
        projects = self.store.read("projects")
        s = Running(data_for=self.store.data_for, projects=lambda archived=False: projects, page_html=lambda: testpage.html(),
                    sneak=sneak.make_read(self.store.data_for), change=change, undo=changes.make_undo(self.store.path, [], "Demo User"))
        s.httpd.activity = activity_read.make_read(self.store.path, self.store.data_for)      # the seam the Activity route reads
        self.addCleanup(s.close)
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, sid)
        cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{s.port}/#work&p={self.code}")}, sid)
        self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid) > 0))
        if dark:
            cdp.js("document.documentElement.dataset.theme = 'dark'", sid)
        if classic:
            cdp.js(LAYER, sid)      # the Classic layer: classicTheme() reads it when the peek draws
        cdp.js(f"clarkPage.openPeek({json.dumps(ITEM)})", sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek [data-pk-history]')", sid)))
        return sid

    ROWS = "#peek [data-pk-history] [data-activity-row]"

    def test_classic_has_no_link_and_the_updates_tab_lists_the_seven_changes(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    sid = self.load(cdp, width, dark)
                    self.assertFalse(cdp.js("!!document.querySelector('[data-pk-lh-btn], [data-pk-lh]')", sid), "row 1258: no Show history link")
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek [data-pk-htab=updates]')", sid)))
                    self.assertTrue(wait(lambda: cdp.js("document.querySelector('#peek [data-pk-htab=updates] .pk-hcount').textContent", sid) == "7"), "only the Latest update's seven changes, not the owner change")
                    cdp.js("document.querySelector('#peek [data-pk-htab=updates]').click()", sid)
                    self.assertTrue(wait(lambda: cdp.js(f"document.querySelectorAll({json.dumps(self.ROWS)}).length", sid) == 7))
                    first = cdp.js(f"document.querySelector({json.dumps(self.ROWS)}).textContent", sid)
                    self.assertIn("Version 6", first, "newest first (the Updates tab draws the change as a word diff: 6 kept, 7 added)")
                    self.assertIn("7", first)
                    self.assertFalse(cdp.js(f"!!document.querySelector({json.dumps(self.ROWS)} + ' b')", sid), "drawn as text, never as markup")

    def test_cards_still_draws_the_show_history_link(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.load(cdp, width, classic=False)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek [data-pk-lh-btn]')", sid)), "Cards keeps its Show history link")
                self.assertEqual(cdp.js("document.querySelector('#peek [data-pk-lh-btn]').textContent", sid), "Show history")


if __name__ == "__main__":
    unittest.main()
