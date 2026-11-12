"""Row 1114: a client sees only client-visible items on the published Milestones and Work items pages, and no count of the others.

Run: python3 dev/run_tests.py test_client_hidden_counts
The test plant gets hidden (not client-visible) milestones and Work items with words, owners, statuses and ids of their own. The
file must hold none of it: not in the page, not in the embedded data, not in the client workbook, and no count (tab number, list
header, tiles, timeline, titles or aria text) may include them. The Milestones and Work items pages carry no Excel export.
Desktop only: 1400 and 900 px.
"""
import base64
import io
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT  # noqa: F401  (puts src/ on the path)
import _publish_fixture as fx

from clark import publish
from clark.store import open_store
from test_server import chrome, wait
from test_work_filters import need_chrome
from test_work_items import page_target

TODAY = "2026-10-28"
EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")
HIDDEN_WORDS = ["ZQ-HIDE-ACTION-ONE", "ZQ-HIDE-ACTION-TWO", "ZQ-HIDE-ACTION-THREE", "ZQ-HIDE-MILESTONE-ONE", "ZQ-HIDE-MILESTONE-TWO",
                "Hidden Owner Zed", "Hidden Stream Zed"]
HIDDEN_IDS = ["PUB-A-901", "PUB-A-902", "PUB-A-903", "PUB-M-901", "PUB-M-902"]


def plant():
    p = fx.load()
    acts, mss = p["data"]["actions"], p["data"]["milestones"]
    base, ms = acts[0], next(m for m in mss if m.get("client_visible") == 1)
    for i, (word, status) in enumerate((("ONE", "Open"), ("TWO", "Delayed"), ("THREE", "Closed")), start=1):
        acts.append(dict(base, id=f"PUB-A-90{i}", description=f"ZQ-HIDE-ACTION-{word}", client_visible=0, client_message="", status=status,
                         owner="Hidden Owner Zed", workstream="Hidden Stream Zed", latest_update=f"ZQ-HIDE-ACTION-{word}",
                         closed="2026-10-02" if status == "Closed" else None))
    for i, word in enumerate(("ONE", "TWO"), start=1):
        mss.append(dict(ms, id=f"PUB-M-90{i}", name=f"ZQ-HIDE-MILESTONE-{word}", description=f"ZQ-HIDE-MILESTONE-{word}",
                        client_visible=0, owner="Hidden Owner Zed", workstream="Hidden Stream Zed", state=None, state_set=None))
    return p


def seen(rows, table):
    return [r for r in rows if r.get("client_visible", 1) == 1 and r.get("archived", 0) == 0]


class HiddenCounts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="clark-hc-"))
        cls.paths = {}
        cls.stores = []
        for name, p in (("seeded", plant()), ("plain", fx.load())):
            db = fx.build_db(cls.tmp / f"{name}.db", p)
            store = open_store(db, onedrive_roots=[])
            cls.stores.append(store)
            built = publish.build(store, "PUB", TODAY, EMPTY_BRANDING, number=1, workbook=True)
            cls.paths[name] = cls.tmp / f"{name}.html"
            cls.paths[name].write_bytes(built["body"])
        cls.path = cls.paths["seeded"]
        cls.html = cls.path.read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        for s in cls.stores:
            s.close()
        shutil.rmtree(cls.tmp, True)

    @staticmethod
    def data_of(html):
        m = re.search(r'<script type="application/json" id="clark-data">(.*?)</script>', html, re.S)
        return json.loads(m.group(1))

    def test_no_hidden_word_or_id_is_anywhere_in_the_file(self):
        for marker in HIDDEN_WORDS + HIDDEN_IDS:
            for spelling in fx.spellings(marker):
                self.assertNotIn(spelling, self.html, marker)

    def test_the_data_and_the_workbook_are_the_same_with_or_without_the_hidden_rows(self):
        d = self.data_of(self.html)
        self.assertEqual(d, self.data_of(self.paths["plain"].read_text(encoding="utf-8")), "hidden rows change nothing in the data")
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(base64.b64decode(d["data"]["client_workbook"]["base64"])))
        text = " ".join(str(c.value) for ws in wb for row in ws.iter_rows() for c in row if c.value is not None)
        for marker in HIDDEN_WORDS + HIDDEN_IDS:
            self.assertNotIn(marker, text, marker)

    def page(self, cdp, tab, width, which="seeded"):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": self.paths[which].as_uri() + "#" + tab}, sid)
        self.assertTrue(wait(lambda: cdp.js("document.body.innerText.length > 200", sid)), "the page drew")
        return sid

    ALL = """(() => { const out = [document.body.innerText, document.title];
        for (const e of document.querySelectorAll('*')) for (const a of ['title', 'aria-label', 'alt', 'data-id', 'data-name', 'value', 'placeholder'])
            if (e.hasAttribute(a)) out.push(e.getAttribute(a));
        return out.join('\\n'); })()"""

    def test_the_two_pages_show_no_hidden_text_no_extra_count_and_no_export_at_1400_and_900(self):
        need_chrome()
        for width in (1400, 900):
            for tab in ("work", "milestones"):
                with self.subTest(width=width, tab=tab):
                    got = {}
                    for which in ("seeded", "plain"):
                        with chrome() as cdp:
                            sid = self.page(cdp, tab, width, which)
                            cdp.js("(() => { const b = document.querySelector('[data-show=all]'); if (b) b.click(); })()", sid)
                            got[which] = cdp.js(self.ALL, sid)
                            controls = cdp.js("""[...document.querySelectorAll('button, a, [role=button]')].filter(e => !e.closest('[role=menu], [role=dialog], nav, header'))
                                .map(e => (e.innerText || '') + ' ' + (e.title || '') + ' ' + (e.getAttribute('aria-label') || ''))""", sid)
                            self.assertFalse([c for c in controls if re.search(r"excel|xlsx|export|download", c, re.I)], controls)
                    self.assertIn("ZQ-KEEP-ACTION-1" if tab == "work" else "ZQ-KEEP-MILESTONE-1", got["seeded"], "the client's own rows are drawn")
                    for marker in HIDDEN_WORDS + HIDDEN_IDS:
                        self.assertNotIn(marker, got["seeded"], marker)
                    self.assertEqual(got["seeded"], got["plain"], "every count, tile, header and title reads as without the hidden rows")


if __name__ == "__main__":
    unittest.main()
