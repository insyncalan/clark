"""Row 1329: the Milestones page has no forecast sentence, no Plan | Movement switch and no hint beside it, in Classic and in Cards.
They are not drawn at all (not hidden by a rule); the page shows the Plan list straight under the title, with no gap where the bar was.

Run: python3 dev/run_tests.py test_ms_head_switch_gone_1329
Without a browser: the sources. With headless Chrome (required): the served page at 1400 and 900 px, light and dark, in both looks, and a published file.
"""
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _demo import USER, DemoStore
from _new_page import reload_to_new_page
from _paths import SRC

from clark import page, publish
from test_milestones_page import EMPTY_BRANDING, TODAY
from test_movement_page import Base
from test_server import chrome, wait
from test_work_items import page_target

PAGE_SRC = SRC / "clark" / "page" / "src"
SENTENCE = re.compile(r"(forecast for|agreed for|has no date yet|now expected|\d+ achieved|\d+ to come)")
HINTS = ("Every milestone is on the timeline", "The list shows where each one stands", "Each move changes the milestone straight away", "Milestones view")
REAL_PAGE_HTML = page.page_html
SWITCH = "[data-mspage-switch], [data-mspv], [data-mspage-hint], #milestones .wbar"


def classic_page(case):
    patch = mock.patch.object(page, "page_html", lambda branding=None, view=False, brand_id=None, theme=None: REAL_PAGE_HTML(branding, view, brand_id, "prototype-2.0"))
    patch.start()
    case.addCleanup(patch.stop)


class Sources(unittest.TestCase):
    def read(self, *path):
        return PAGE_SRC.joinpath(*path).read_text(encoding="utf-8")

    def test_the_milestones_view_never_draws_the_switch_wrap_or_the_forecast_sentence(self):
        views = self.read("components", "Views.jsx")
        self.assertNotIn("head-sub-off", views)
        self.assertNotIn("tools.MilestonesPage", views)
        self.assertNotIn("<Wrap", views)
        self.assertNotIn("line.toCome", views)

    def test_the_empty_head_words_stay(self):
        words = self.read("logic", "milestones.js")
        for sentence in ("No milestones yet.", "The only milestone is cancelled.", "milestones are cancelled."):
            self.assertIn(sentence, words)

    def test_movement_code_is_kept_but_only_unreachable(self):
        self.assertTrue((PAGE_SRC / "edit" / "Movement.jsx").exists())
        self.assertTrue((PAGE_SRC / "edit" / "MilestonesPage.jsx").exists())

    def test_classic_has_no_rule_for_the_hint(self):
        rules = (SRC / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")
        self.assertNotIn("data-mspage", rules)
        self.assertNotIn("data-mspv", rules)

    def test_no_help_line_sends_the_reader_to_a_movement_switch(self):
        text = self.read("help", "helpContent.json")
        for gone in ("Movement** switch", "press **Movement**", "switch next to **Plan**", "**Plan** shows every milestone"):
            self.assertNotIn(gone, text)


class Look:
    """The same checks in both looks, at both widths, in both themes."""
    def check(self, p, width, theme):
        p.until("!!document.querySelector('#milestones .msl-row')", "the list drew")
        self.assertEqual(p.js(f"document.querySelectorAll({json.dumps(SWITCH)}).length"), 0, "no switch, bar or hint in the DOM")
        self.assertEqual(p.js("document.querySelectorAll('#ms-summary, .head-sub, .head-sub-off').length"), 0, "no summary paragraph in the DOM")
        self.assertIsNone(SENTENCE.search(p.js("document.querySelector('#milestones .head').textContent")), "no forecast sentence")
        body = p.js("document.querySelector('#milestones').textContent")
        for word in HINTS:
            self.assertNotIn(word, body)
        for word in ("Plan", "Movement"):
            self.assertEqual(p.js("[...document.querySelectorAll('#milestones button')].filter(b => b.textContent.trim() === %s).length" % json.dumps(word)), 0, word)
        self.assertTrue(p.js("!!document.querySelector('.msv[data-place=page]')"), "the Plan is drawn straight in the page")
        self.assertEqual(p.js("document.querySelector('#milestones h1').textContent"), "Milestones")
        gap = p.js("""(() => { const h = document.querySelector('#milestones .head').getBoundingClientRect(), v = document.querySelector('#milestones .msv').getBoundingClientRect(); return v.top - h.bottom; })()""")
        self.assertLess(gap, 40, "no empty bar between the title and the list (%s px at %s %s)" % (gap, width, theme))
        self.assertEqual(p.js("document.documentElement.scrollWidth <= window.innerWidth"), True, "no sideways scroll")

    def test_both_widths_and_themes(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    self.check(self.visit(cdp, width=width, theme=theme), width, theme)

    def test_a_remembered_movement_choice_shows_no_movement(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.js("localStorage.setItem('clark.msp.view', JSON.stringify('move'))")
            reload_to_new_page(p.js, "!!document.querySelector('#milestones .msl-row')", "the page drew its plan list after the reload")
            self.assertEqual(p.js("!!document.querySelector('#movement')"), False)
            self.assertEqual(self.reads, [], "no Movement request is made")


class Cards(Look, Base):
    def test_the_page_under_test_is_cards(self):
        self.assertNotEqual(REAL_PAGE_HTML(EMPTY_BRANDING, theme="prototype-2.0"), REAL_PAGE_HTML(EMPTY_BRANDING))


class Classic(Look, Base):
    def setUp(self):
        classic_page(self)
        super().setUp()


class Published(unittest.TestCase):
    def test_the_published_file_has_no_sentence_node(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        with demo.store.step("dashboard", USER) as step:
            step.update("milestones", demo.milestone, {"client_visible": 1})
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(shutil.rmtree, folder, True)
        done = publish.publish(demo.store, "ABC", folder, by_user=USER, now=TODAY, branding=EMPTY_BRANDING)
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.navigate", {"url": Path(done["path"]).as_uri()}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready === '1'", sid)))
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
            cdp.js("[...document.querySelectorAll('.tab')].find(t => /Milestones/.test(t.textContent)).click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#milestones .msl-row')", sid)))
            self.assertEqual(cdp.js("document.querySelectorAll('#ms-summary, .head-sub-off, [data-mspage-switch]').length", sid), 0)
            self.assertIsNone(SENTENCE.search(cdp.js("document.querySelector('#milestones .head').textContent", sid)))


if __name__ == "__main__":
    unittest.main()
