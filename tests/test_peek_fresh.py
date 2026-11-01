"""#158: Raised, Last reviewed and the 'Not reviewed in 14 days' chip in the peek. Run: python3 dev/run_tests.py test_peek_fresh

The page reads an item's freshness from its data (`freshness`: raised, last_reviewed, days, not_reviewed; the server fills it from
history with clark.freshness). Here the data is given it by a wrapper, so the page is tested on its own at 1400 and 900 px, light and dark.
"""
import copy
import unittest

from _paths import ROOT
import _testpage as testpage

from clark import changes, sneak  # noqa: E402
from test_peek import key  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402
from test_work_filters import click  # noqa: E402

STALE = {"raised": "2026-09-01", "last_reviewed": "2026-10-02", "days": 14, "not_reviewed": True}
FRESH = {"raised": "2026-10-20", "last_reviewed": None, "days": 14, "not_reviewed": False}


class PeekFresh(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, cls.ids = load_demo()
        cls.code = next(iter(cls.ids))
        base = cls.store.data_for(cls.code)
        cls.open = [a["id"] for a in base["actions"] if a["status"] not in ("Closed", "Cancelled")][:2]
        cls.closed = next(a["id"] for a in base["actions"] if a["status"] in ("Closed", "Cancelled"))

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        import shutil
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def data_for(self, code, **kw):
        d = copy.deepcopy(self.store.data_for(code, **kw))
        for a in d["actions"]:
            if a["id"] == self.open[0]:
                a["freshness"] = STALE
            elif a["id"] == self.open[1]:
                a["freshness"] = FRESH
            elif a["id"] == self.closed:
                a["freshness"] = {**STALE, "not_reviewed": False}        # the server never flags a closed item; the page must not show it either
        return d

    def load(self, cdp, width, item, scheme):
        s = Running(data_for=self.data_for, projects=lambda: self.store.read("projects"), page_html=lambda: testpage.html(), sneak=sneak.make_read(self.data_for),
                    change=changes.make_change(self.store.path, [], "Demo User"), undo=changes.make_undo(self.store.path, [], "Demo User"))
        self.addCleanup(s.close)
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#work&p={self.code}&item={item}"}, sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek dt')", sid)))
        return sid

    def rows(self, cdp, sid):
        return cdp.js("Object.fromEntries([...document.querySelectorAll('#peek .pk-row')].map(r => [r.querySelector('dt').textContent, r.querySelector('dd').textContent]))", sid)

    def test_a_stale_item_shows_both_dates_and_the_chip_in_every_view(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    sid = self.load(cdp, width, self.open[0], scheme)
                    got = self.rows(cdp, sid)
                    self.assertEqual((got["Raised"], got["Last reviewed"]), ("01-09-2026", "02-10-2026"))
                    self.assertEqual(cdp.js("[...document.querySelectorAll('#peek [data-stale]')].map(c => c.textContent)", sid), ["Not reviewed in 14 days"])
                    box = cdp.js("(c => { const r = c.getBoundingClientRect(), p = document.querySelector('#peek').getBoundingClientRect(); return [r.left >= p.left, r.right <= p.right, getComputedStyle(c).color, getComputedStyle(document.body).backgroundColor]; })(document.querySelector('#peek [data-stale]'))", sid)
                    self.assertTrue(box[0] and box[1], "the chip sits inside the peek")
                    self.assertNotEqual(box[2], box[3], "text is not the colour of the page")

    def test_a_reviewed_item_has_no_chip_and_a_never_reviewed_item_has_a_dash(self):
        with chrome() as cdp:
            sid = self.load(cdp, 1400, self.open[1], "light")
            got = self.rows(cdp, sid)
            self.assertEqual((got["Raised"], got["Last reviewed"]), ("20-10-2026", "Not yet"))
            self.assertEqual(cdp.js("document.querySelectorAll('#peek [data-stale]').length", sid), 0)

    def test_a_closed_item_never_shows_the_chip(self):
        with chrome() as cdp:
            sid = self.load(cdp, 1400, self.closed, "light")
            self.assertEqual(self.rows(cdp, sid)["Raised"], "01-09-2026")
            self.assertEqual(cdp.js("document.querySelectorAll('#peek [data-stale]').length", sid), 0)

    def test_an_item_with_no_freshness_in_its_data_shows_neither_row_nor_chip(self):
        decision = next(d["id"] for d in self.store.data_for(self.code)["decisions"])
        with chrome() as cdp:
            sid = self.load(cdp, 1400, decision, "light")
            got = self.rows(cdp, sid)
            self.assertNotIn("Raised", got)
            self.assertNotIn("Last reviewed", got)
            self.assertEqual(cdp.js("document.querySelectorAll('#peek [data-stale]').length", sid), 0)


if __name__ == "__main__":
    unittest.main()
