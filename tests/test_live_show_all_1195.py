"""Item 1195, slice S4: the live Work items page draws the first LIVE_MAX rows and offers Show all items / Show only N under the table.
The section template's own link (data-wil-all) is not touched. Quick tier: pure rules in node plus a source check. Browser tier: the real page with 55 more actions (the link, the cut, the board and Hand over).

Run: python3 dev/run_tests.py test_live_show_all_1195
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _demo import USER
from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402
from test_board import ME  # noqa: E402
from test_server import chrome, wait  # noqa: E402,F401  (chrome: the runner tells a browser file by this import)
from test_work_board_page import Base, setUpModule, tearDownModule  # noqa: E402,F401  (the shared Chrome of the board tests)
from test_work_filters import click  # noqa: E402

ENTRY = ROOT / "tests" / "fixtures" / "liveshowall_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}


def run_node(probe):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        if "code" not in _BUNDLE:
            out = Path(tmp) / "w.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=W", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
        script = Path(tmp) / "probe.js"
        script.write_text(_BUNDLE["code"] + ";\nconsole.log(JSON.stringify(" + probe + "));", encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


def window(total, show_all):
    return run_node("(() => { const r = W.liveWindow(Array.from({length: %d}, (_, i) => i), %s); return {n: r.rows.length, link: r.link}; })()"
                    % (total, "true" if show_all else "false"))


class LiveWindow(unittest.TestCase):
    def test_the_live_max_is_fifty(self):
        self.assertEqual(run_node("W.LIVE_MAX"), 50)

    def test_a_list_up_to_the_max_has_no_link(self):
        self.assertEqual(window(50, False), {"n": 50, "link": ""})
        self.assertEqual(window(0, False), {"n": 0, "link": ""})

    def test_one_over_the_max_cuts_to_the_max_and_offers_show_all_items(self):
        self.assertEqual(window(51, False), {"n": 50, "link": "Show all items"})

    def test_open_shows_every_row_and_the_link_reads_show_only_50(self):
        self.assertEqual(window(51, True), {"n": 51, "link": "Show only 50"})
        self.assertEqual(window(50, True), {"n": 50, "link": ""})

    def test_the_first_rows_kept_are_the_first_in_order(self):
        self.assertEqual(run_node("W.liveWindow(Array.from({length: 60}, (_, i) => i), false).rows.slice(-1)"), [49])


class Source(unittest.TestCase):
    def test_the_live_list_draws_the_link_and_the_template_link_is_not_reused(self):
        src = (PAGE_SRC / "components" / "WorkItems.jsx").read_text(encoding="utf-8")
        self.assertIn("data-work-all", src)
        self.assertIn("liveWindow(", src)
        self.assertNotIn("data-wil-all", src, "the section template's link and its tests stay untouched")


ALL = "#work&p=ABC&f=mode:all"
ROWS = "[...document.querySelectorAll('#work-list tr[data-id]')].map(r => r.dataset.id)"
LINK = "document.querySelector('[data-work-all]')"


class Page(Base):
    """The real page with 55 more actions (67 items in all). The new ones are made with the due dates falling, so the order drawn is not the order made."""

    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            for n in range(55):
                st.create("actions", {"project": "ABC", "raised": "2026-10-01", "source": "demo", "owner": ME, "priority": "Low",
                                      "description": f"Extra item {n:02d}", "due_date": f"2027-{12 - n // 28:02d}-{28 - n % 28:02d}"})

    def load(self, cdp, hash_=ALL, **kw):
        sid = self.visit(cdp, hash_=hash_, **kw)
        self.until(cdp, sid, "document.querySelectorAll('#work-list tr[data-id]').length >= 2", "the rows")
        return sid

    def test_the_table_draws_fifty_rows_and_the_link_opens_and_shuts_the_rest(self):
        with chrome() as cdp:
            sid = self.load(cdp)
            first = cdp.js(ROWS, sid)
            self.assertEqual(len(first), 50)
            text = cdp.js("document.querySelector('#work-list').innerText", sid)      # the page groups its table; the cut is made on the order by due date (earliest first)
            self.assertIn("Extra item 54", text)
            self.assertNotIn("Extra item 00", text)
            self.assertEqual(cdp.js(LINK + ".textContent", sid), "Show all items")
            self.assertEqual(cdp.js(LINK + ".getAttribute('aria-expanded')", sid), "false")
            self.assertIn("67 items", cdp.js("document.querySelector('#work').innerText", sid), "the count is of the filtered rows, not of the cut")
            click(cdp, sid, "[data-work-all]")
            self.until(cdp, sid, "document.querySelectorAll('#work-list tr[data-id]').length === 67", "every row")
            every = cdp.js(ROWS, sid)
            self.assertEqual(set(first) - set(every), set())
            self.assertEqual(cdp.js(LINK + ".textContent", sid), "Show only 50")
            self.assertEqual(cdp.js(LINK + ".getAttribute('aria-expanded')", sid), "true")
            click(cdp, sid, "[data-work-all]")
            self.until(cdp, sid, "document.querySelectorAll('#work-list tr[data-id]').length === 50", "back to 50")
            self.assertEqual(cdp.js(LINK + ".textContent", sid), "Show all items")

    def test_a_list_of_fifty_or_fewer_has_no_link(self):
        with chrome() as cdp:
            sid = self.load(cdp, "#work&p=ABC&f=mode:all;type:decision")
            self.assertEqual(cdp.js("document.querySelectorAll('[data-work-all]').length", sid), 0)

    def test_the_link_sits_under_the_table_and_the_template_link_is_not_drawn(self):
        with chrome() as cdp:
            sid = self.load(cdp)
            self.assertTrue(cdp.js("(() => { const t = document.querySelector('#work-list'), l = " + LINK + ";"
                                   " return !!(t && l) && !!(t.compareDocumentPosition(l) & Node.DOCUMENT_POSITION_FOLLOWING); })()", sid))
            self.assertEqual(cdp.js("document.querySelectorAll('[data-wil-all]').length", sid), 0)
            self.assertEqual(cdp.js("[" + LINK + ".type, " + LINK + ".className, " + LINK + ".parentNode.className, getComputedStyle(" + LINK + ").textDecorationLine].join('|')", sid),
                             "button|wil-all-b|wil-all|underline", "a plain button in the template link's own look")

    def test_the_board_draws_every_card_and_no_link(self):
        with chrome() as cdp:
            sid = self.visit(cdp, hash_=ALL, preset={"view": "board", "group": "status", "lane": None, "collapsed": []}, wait_for="#work-board")
            self.until(cdp, sid, "document.querySelectorAll('#work-board [data-id]').length >= 67", "every card")
            self.assertEqual(cdp.js("document.querySelectorAll('[data-work-all]').length", sid), 0)

    def test_hand_over_draws_every_row_and_no_link(self):
        with chrome() as cdp:
            sid = self.load(cdp, ALL + ";owner:" + ME.replace(" ", "%20"))
            self.assertEqual(len(cdp.js(ROWS, sid)), 50)
            self.assertEqual(cdp.js(LINK + ".textContent", sid), "Show all items")
            click(cdp, sid, "#hand-over")
            self.until(cdp, sid, "!!document.querySelector('#hand-bar')", "pick mode")
            self.until(cdp, sid, "document.querySelectorAll('#work-list tr[data-id]').length > 50", "every row")
            self.assertEqual(cdp.js("document.querySelectorAll('[data-work-all]').length", sid), 0)


if __name__ == "__main__":
    unittest.main()
