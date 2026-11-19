"""Row 1329: the Milestones page has no forecast sentence under its title ("Public launch is forecast for ..., N achieved, N to come.") and no
Plan | Movement switch with its hint ("Every milestone is on the timeline. ..."). Each test below is written to FAIL on the page as it was
before the row and to name the wrong build (mutant) it kills.

Run: CLARK_CHROME=/usr/local/bin/clark-chrome python3 dev/run_tests.py test_ms_head_switch_gone_1329
Without a browser: the sources and both built pages. With headless Chrome (required): the served page and a published file, 1400 and 900 px.
"""
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _demo import USER, DemoStore
from _paths import SRC

from clark import page, publish
from test_milestones_page import EMPTY_BRANDING, TODAY
from test_movement_page import Base
from test_server import chrome, wait
from test_work_items import page_target

PAGE_SRC = SRC / "clark" / "page" / "src"
SENTENCE = re.compile(r"(forecast for|agreed for|has no date yet|now expected|\d+ achieved|\d+ to come)")
HINTS = ("Every milestone is on the timeline", "The list shows where each one stands", "Milestones view")
REAL_PAGE_HTML = page.page_html
SWITCH = "[data-mspage-switch], [data-mspv], [data-mspage-hint], #milestones .seg:not(.cal-sc)"


class Sources(unittest.TestCase):
    def read(self, *path):
        return (PAGE_SRC.joinpath(*path)).read_text(encoding="utf-8")

    def test_mutant_sentence_kept_but_hidden_or_emptied_the_head_has_no_summary_paragraph(self):
        # kills: sentence hidden by CSS / left as an empty #ms-summary / words swapped to "agreed for" / headLine still computed and only not drawn
        views = self.read("components", "Views.jsx")
        for text in ("ms-summary", "head-sub-off", "headLine", "forecast", "agreed", "toCome", "achieved"):
            self.assertNotIn(text, views, f"{text!r} is still in the Milestones head")

    def test_mutant_dead_headline_left_behind(self):
        self.assertNotIn("headLine", self.read("logic", "milestones.js"), "headLine is dead code once the sentence is gone")

    def test_mutant_switch_component_left_registered_or_in_the_tree(self):
        # kills: MilestonesPage kept in EDIT but unused / file kept / Views still wraps the plan in the tool
        self.assertFalse((PAGE_SRC / "edit" / "MilestonesPage.jsx").exists(), "the switch's file is deleted")
        self.assertNotIn("MilestonesPage", self.read("edit", "index.js"))
        views = self.read("components", "Views.jsx")
        self.assertNotIn("MilestonesPage", views)
        self.assertNotIn("Wrap", views)

    def test_mutant_switch_hidden_by_css_only_or_hint_kept_the_built_pages_have_neither(self):
        # kills: switch/hint hidden by a rule but still in the bundle; hint kept without the switch; the served page only fixed
        for view in (False, True):
            text = page.page_html(EMPTY_BRANDING, view=view)
            for word in ("data-mspage-switch", "data-mspage-hint", "msp.view", *HINTS):
                self.assertNotIn(word, text, f"{word!r} in the {'published' if view else 'served'} page")
            self.assertNotIn("head-sub-off", text)
            self.assertNotIn("ms-summary", text, f"the summary paragraph is in the {'published' if view else 'served'} page")

    def test_the_empty_head_words_stay_in_the_source(self):
        # guard (passes today and must keep passing): only the forecast sentence goes, the empty and all-cancelled lines are not part of the ask
        words = self.read("logic", "milestones.js")
        for sentence in ("No milestones yet.", "The only milestone is cancelled.", "milestones are cancelled."):
            self.assertIn(sentence, words)


def milestones_text(p):
    return p.js("document.querySelector('#milestones').textContent")


class Served(Base):
    def test_mutant_sentence_or_switch_only_gone_at_one_width_or_theme(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    p = self.visit(cdp, width=width, theme=theme)
                    p.until("!!document.querySelector('#milestones .msl-row')", "the list drew")
                    self.assertEqual(p.js("document.querySelectorAll('#ms-summary, .head-sub').length"), 0, "no summary paragraph (not even an empty one)")
                    self.assertIsNone(SENTENCE.search(p.js("document.querySelector('#milestones .head').textContent")), "no forecast sentence in the head")
                    self.assertEqual(p.js(f"document.querySelectorAll({json.dumps(SWITCH)}).length"), 0, "no switch or hint in the DOM (not hidden by CSS)")
                    body = milestones_text(p)
                    for word in HINTS:
                        self.assertNotIn(word, body)
                    for word in ("Plan", "Movement"):
                        self.assertEqual(p.js("[...document.querySelectorAll('#milestones button')].filter(b => b.textContent.trim() === %s).length" % json.dumps(word)), 0, word)

    def test_mutant_the_head_lost_more_than_the_sentence(self):
        # kills: title, crumbs, Add milestone, the list or the timeline removed together with the sentence
        with chrome() as cdp:
            p = self.visit(cdp)
            p.until("!!document.querySelector('#milestones .msl-row')", "the list drew")
            self.assertEqual(p.js("document.querySelector('#milestones h1').textContent"), "Milestones")
            self.assertTrue(p.js("!!document.querySelector('#milestones .crumbs')"))
            self.assertTrue(p.js("!!document.querySelector('#addMs')"), "the owner's Add milestone")
            self.assertTrue(p.js("!!document.querySelector('.msv[data-place=page]')"), "the plan is drawn straight in the page")
            self.assertTrue(p.js("!!document.querySelector('#milestones .msl-row button[data-ms-eye]')"), "the rows keep their eye")

    def test_mutant_a_remembered_movement_choice_still_shows_movement(self):
        # kills: the old msp.view=move kept in this browser still opens Movement through another route
        with chrome() as cdp:
            p = self.visit(cdp)
            p.js("localStorage.setItem('clark.msp.view', JSON.stringify('move'))")
            p.js("location.reload()")
            p.until("!!document.querySelector('#milestones .msl-row')", "the plan list drew after the reload")
            self.assertEqual(p.js("!!document.querySelector('#movement')"), False, "no Movement section")
            self.assertEqual(self.reads, [], "no Movement request is made")


class Classic(Base):
    """The Classic theme once hid the Milestones hint line with a rule of its own; the hint and that rule are gone, and the title must still show."""
    def setUp(self):
        patch = mock.patch.object(page, "page_html", lambda branding=None, view=False, brand_id=None, theme=None: REAL_PAGE_HTML(branding, view, brand_id, "prototype-2.0"))
        patch.start()
        self.addCleanup(patch.stop)
        super().setUp()

    def test_mutant_classic_rule_left_in_the_theme_or_the_title_hidden_with_it(self):
        # kills: the hint-hiding rule kept in Classic's rules.css; a replacement rule that also hides the title; Classic not the page under test
        rules = (SRC / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")
        self.assertNotIn("mspage", rules)
        self.assertNotIn("[data-mspv", rules)
        self.assertNotEqual(REAL_PAGE_HTML(EMPTY_BRANDING, theme="prototype-2.0"), REAL_PAGE_HTML(EMPTY_BRANDING), "the page under test is Classic, not Cards")
        with chrome() as cdp:
            p = self.visit(cdp)
            p.until("!!document.querySelector('#milestones .msl-row')", "the list drew")
            self.assertEqual(p.js("document.querySelectorAll('[data-mspage-hint], [data-mspage-switch], #milestones .head-sub').length"), 0, "no hint element in the Classic head")
            self.assertEqual(p.js("document.querySelector('#milestones h1').textContent"), "Milestones")
            self.assertTrue(p.js("(() => { const h = document.querySelector('#milestones h1'); const r = h.getBoundingClientRect(); return getComputedStyle(h).display !== 'none' && getComputedStyle(h).visibility === 'visible' && r.width > 0 && r.height > 0; })()"), "the h1 is visible")


class Published(unittest.TestCase):
    def test_mutant_only_the_served_page_was_fixed_the_published_file_keeps_the_sentence(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        with demo.store.step("dashboard", USER) as step:
            for n in range(1, 6):
                step.create("milestones", {"project": "ABC", "name": f"Extra {n}", "baseline_date": f"2027-0{n}-10", "client_visible": 1,
                                           "forecast_date": f"2027-0{n}-20" if n % 2 else None, "internal_note": "x", "source": "demo"})
            step.update("milestones", demo.milestone, {"client_visible": 1})
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(shutil.rmtree, folder, True)
        done = publish.publish(demo.store, "ABC", folder, by_user=USER, now=TODAY, branding=EMPTY_BRANDING)
        path = Path(done["path"])
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready === '1'", sid)))
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
            cdp.js("[...document.querySelectorAll('.tab')].find(t => /Milestones/.test(t.textContent)).click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#milestones .msl-row')", sid)), "the list drew")
            self.assertEqual(cdp.js("document.querySelectorAll('#ms-summary, .head-sub').length", sid), 0)
            self.assertIsNone(SENTENCE.search(cdp.js("document.querySelector('#milestones .head').textContent", sid)))
            self.assertEqual(cdp.js("document.querySelector('#milestones h1').textContent", sid), "Milestones")
            self.assertEqual(cdp.js("document.querySelectorAll('.msl-row').length", sid), 5, "the owner's ruling: five rows, unchanged")
            self.assertTrue(cdp.js("!!document.querySelector('.msl-all')", sid), "Show all stays")


if __name__ == "__main__":
    unittest.main()
