"""The board's icon-button rule is scoped to the board (class `bib`), so it never resizes another page's `.ib` buttons.

Run: python3 dev/run_tests.py test_ib_scope
Why: the Work items board (#68) styled its icon buttons with a class called `ib` (34 x 32), while the Milestones page (#44) already
used `ib` for its Earlier, Later and view-switch buttons (28 x 28). Two rules with one name made the board's look win on the
Milestones toolbar. The board now uses `bib`. This test checks, in headless Chrome (required: it fails, never skips, without it), at
1400 and 900 px in light and dark: the board's buttons measure 34 x 32 and keep their pressed look; no rule in the page's style
sheets gives an `.ib` button the board's size; and, where the Milestones page is in this build, its buttons measure 28 x 28.
Desktop widths only.
"""
import json
import unittest

from _paths import SRC

from clark import page
from test_server import Running, chrome, wait
from test_work_board_page import Base
from test_work_items import load_demo, page_target
from test_work_filters import need_chrome

import tempfile
import shutil

PAGE_SRC = SRC / "clark" / "page" / "src"
HAS_MILESTONES = (PAGE_SRC / "components" / "MsTimeline.jsx").exists()
MEASURE = ("[...document.querySelectorAll(%s)].map(b => { const r = b.getBoundingClientRect(); const c = getComputedStyle(b);"
           " return {w: Math.round(r.width), h: Math.round(r.height), pressed: b.getAttribute('aria-pressed'), bg: c.backgroundColor,"
           " border: c.borderTopColor, label: b.getAttribute('aria-label') || b.id || ''}; })")
LEAK = ("[...document.styleSheets].flatMap(s => { try { return [...s.cssRules]; } catch (e) { return []; } })"
        ".filter(r => r.selectorText && /\\.ib(?![a-z-])/.test(r.selectorText) && r.style.width === '34px').map(r => r.selectorText)")


SHARED = ("[...document.styleSheets].flatMap(s => { try { return [...s.cssRules]; } catch (e) { return []; } })"
          ".filter(r => r.selectorText && r.selectorText.split(',').some(x => /^\\.(mv|ghost)$/.test(x.trim()))).map(r => r.selectorText)")


def themes(cdp, sid, theme):
    cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", sid)


class BoardButtons(Base):
    def test_the_boards_buttons_are_34_by_32_and_keep_the_pressed_look(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.visit(cdp, width)
                    themes(cdp, sid, theme)
                    self.board(cdp, sid)
                    themes(cdp, sid, theme)
                    got = cdp.js(MEASURE % json.dumps(".bib"), sid)
                    self.assertGreaterEqual(len(got), 3, "the two layout buttons and full screen")
                    for b in got:
                        self.assertEqual((b["w"], b["h"]), (34, 32), b)
                    layout = cdp.js(MEASURE % json.dumps("[data-layout]"), sid)
                    on = [b for b in layout if b["pressed"] == "true"]
                    off = [b for b in layout if b["pressed"] == "false"]
                    self.assertEqual((len(on), len(off)), (1, 1))
                    self.assertNotEqual(on[0]["bg"], off[0]["bg"], "the pressed button has its own background")
                    self.assertNotEqual(on[0]["border"], off[0]["border"], "and its own border")
                    self.assertEqual(cdp.js("document.querySelectorAll('.ib').length", sid), 0, "the board no longer uses the shared name")

    def test_no_rule_gives_an_ib_button_the_boards_size(self):
        with chrome() as cdp:
            sid = self.visit(cdp, 1400)
            self.assertEqual(cdp.js(LEAK, sid), [])

    def test_the_boards_move_and_drag_classes_are_its_own(self):
        """The Milestones page also names a wrapper `mv` and a calendar mark `ghost`; the board's rules for those names would move them."""
        with chrome() as cdp:
            sid = self.visit(cdp, 1400)
            bare = cdp.js(SHARED, sid)
            self.assertEqual(bare, [], "a bare .mv or .ghost rule would also hit the Milestones page")
            self.board(cdp, sid)
            self.assertEqual(cdp.js("document.querySelectorAll('.mv, .ib').length", sid), 0)
            self.assertGreaterEqual(cdp.js("document.querySelectorAll('.bmv').length", sid), 1, "the cards' move menus")


@unittest.skipUnless(HAS_MILESTONES, "the Milestones page is not in this build yet; the check runs once it is")
class MilestonesButtons(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        need_chrome()
        cls.store, cls.folder, _ = load_demo()
        cls.projects = cls.store.read("projects")

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def test_earlier_later_and_the_view_switch_stay_28_by_28(self):
        s = Running(data_for=self.store.data_for, projects=lambda: self.projects, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = page_target(cdp)
                    cdp.call("Page.enable", {}, sid)
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                    cdp.call("Page.navigate", {"url": "about:blank"}, sid)
                    cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#milestones&p=TUL"}, sid)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.mv-wrap')", sid)), "the timeline drew")
                    themes(cdp, sid, theme)
                    seen = {}
                    for b in cdp.js(MEASURE % json.dumps("button.ib"), sid):
                        seen[b["label"]] = b
                    views = cdp.js("[...document.querySelectorAll('[data-msvb]')].map(b => b.dataset.msvb)", sid)
                    self.assertGreaterEqual(len(views), 2, "the view switch")
                    for v in views:
                        cdp.js(f"document.querySelector('[data-msvb={json.dumps(v)}]').click()", sid)
                        wait(lambda: True, 1)
                        for b in cdp.js(MEASURE % json.dumps("button.ib"), sid):
                            seen[b["label"] + "/" + v] = b
                    labels = " ".join(seen)
                    self.assertIn("Earlier", labels)
                    self.assertIn("Later", labels)
                    for k, b in seen.items():
                        self.assertEqual((b["w"], b["h"]), (28, 28), k)


if __name__ == "__main__":
    unittest.main()
