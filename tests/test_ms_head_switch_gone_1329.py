"""Row 1329 (Classic only; ruling 20-11: Cards code and Cards pins stay as they were): the Classic Milestones page has no forecast sentence under its title ("Public launch is forecast for ..., N achieved, N to come.") and no
Plan | Movement switch with its hint ("Every milestone is on the timeline. ..."). Each test below is written to FAIL on the page as it was
before the row and to name the wrong build (mutant) it kills.

Run: CLARK_CHROME=/usr/local/bin/clark-chrome python3 dev/run_tests.py test_ms_head_switch_gone_1329
Without a browser: the sources and the built pages. With headless Chrome (required): the served page and a published file, 1400 and 900 px.
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
from test_movement_page import GO_LIVE, PILOT, Base
from test_server import chrome, wait
from test_work_items import page_target

PAGE_SRC = SRC / "clark" / "page" / "src"
SENTENCE = re.compile(r"(forecast for|agreed for|has no date yet|now expected|\d+ achieved|\d+ to come)")
HINTS = ("Every milestone is on the timeline. ", "The list shows where each one stands", "Milestones view")
REAL_PAGE_HTML = page.page_html
HELP_LINE = "Milestones shows every milestone for the project, including internal ones. Where the page has a Plan and Movement switch, Movement shows slippage, for you and the team only."
SWITCH = "[data-mspage-switch], [data-mspv], [data-mspage-hint], #milestones .seg:not(.cal-sc)"


class Sources(unittest.TestCase):
    def read(self, *path):
        return (PAGE_SRC.joinpath(*path)).read_text(encoding="utf-8")

    def test_mutant_classic_gate_dropped_or_inverted_in_the_head_or_the_wrap(self):
        # kills: Wrap or the sentence no longer gated by classicTheme(); gate written the wrong way round (Cards would lose its switch)
        views = self.read("components", "Views.jsx")
        self.assertIn('import { classicTheme } from "./Contents.jsx";', views)
        self.assertIn("const Wrap = !classicTheme() && tools && tools.MilestonesPage;", views)
        self.assertRegex(views, r"classic\s*\?\s*\(line \? null : <p class=\"head-sub\">\{emptyHead\(rows\)\}</p>\)")

    def test_mutant_cards_side_removed_with_the_classic_one(self):
        # kills: MilestonesPage / headLine deleted or unregistered: Cards still draws the switch and the sentence from them
        self.assertTrue((PAGE_SRC / "edit" / "MilestonesPage.jsx").exists())
        self.assertIn("MilestonesPage", self.read("edit", "index.js"))
        words = self.read("logic", "milestones.js")
        self.assertIn("export function headLine", words)
        self.assertIn('id="ms-summary"', self.read("components", "Views.jsx"))

    def test_the_empty_head_words_stay_in_the_source(self):
        # guard (passes today and must keep passing): only the forecast sentence goes, the empty and all-cancelled lines are not part of the ask
        words = self.read("logic", "milestones.js")
        for sentence in ("No milestones yet.", "The only milestone is cancelled.", "milestones are cancelled."):
            self.assertIn(sentence, words)


def classic_page(case):
    patch = mock.patch.object(page, "page_html", lambda branding=None, view=False, brand_id=None, theme=None: REAL_PAGE_HTML(branding, view, brand_id, "prototype-2.0"))
    patch.start()
    case.addCleanup(patch.stop)


def help_milestones_line(case, p):
    p.cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, p.sid)
    p.js("document.querySelector('#profile-btn').click()")
    p.until("!!document.querySelector('#profile-menu')", "profile menu")
    p.js("[...document.querySelectorAll('#profile-menu [role=menuitem]')].find(e => e.textContent === 'Help').click()")
    p.until("!!document.querySelector('#help') || !!document.querySelector('#help-peek')", "Help opened")
    if p.js("!!document.querySelector('#help-peek')"):
        p.js("document.querySelector('#help-peek [data-hpk-full]').click()")
        p.until("!!document.querySelector('#hpTab-start')", "the full Help")
    p.js("document.querySelector('#hpTab-start').click()")
    p.until("!!document.querySelector('#help .hp-where-g li')", "the Help drew the screens")
    line = p.js("[...document.querySelectorAll('#help .hp-where-g li')].map(l => l.textContent).join(' | ')")
    case.assertIn(HELP_LINE, " ".join(line.split()))


def milestones_text(p):
    return p.js("document.querySelector('#milestones').textContent")


class Served(Base):
    """The Classic page (Theme prototype-2.0)."""
    def setUp(self):
        classic_page(self)
        super().setUp()

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

    def test_help_milestones_line_is_the_approved_text_in_this_theme(self):
        # Row 1329: Help is shared by both looks; the Milestones line says where the switch exists. kills: the line reworded for one look, or the Movement entries dropped
        with chrome() as cdp:
            help_milestones_line(self, self.visit(cdp))

    def test_mutant_h1_gap_under_the_title_is_zero(self):
        # kills: .head h1 { margin-bottom } given a value (the title then floats away from the list at both widths)
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit(cdp, width=width)
                p.until("!!document.querySelector('#milestones .msl-row')", "the list drew")
                self.assertEqual(p.js("getComputedStyle(document.querySelector('#milestones .head h1')).marginBottom"), "0px")

    def test_mutant_the_served_page_lost_the_archived_button_or_the_peek_its_editor(self):
        # kills: {Archived ? <Archived /> : null} replaced by null (Show archived gone from the page); MilestoneEdit missing (the peek reads only)
        with self.store.step("dashboard", USER) as st:
            st.archive("milestones", PILOT)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.until("!!document.querySelector('#milestones .msl-row')", "the list drew")
            p.until("!!document.querySelector('#milestones #ms-archived-pill')", "Show archived is on the Milestones page")
            p.js(f"location.hash = '#milestones&p=ABC&ms={GO_LIVE}'")
            p.until("!!document.querySelector('#peek')", "the peek drew")
            p.until("!!document.querySelector('#peek [data-ms-edit], #peek textarea[data-ms-field], #peek .pk-title .pkh-title-txt')", "the milestone peek is the editor's")

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
            reload_to_new_page(p.js, "!!document.querySelector('#milestones .msl-row')", "the NEW page drew its plan list after the reload")
            self.assertEqual(p.js("!!document.querySelector('#movement')"), False, "no Movement section")
            self.assertEqual(self.reads, [], "no Movement request is made")


class Cards(Base):
    """Cards (no Theme) keeps what main had: the forecast sentence (hidden by its own rule) and the Plan | Movement switch."""
    def test_help_milestones_line_is_the_approved_text_in_this_theme(self):
        # Row 1329: Help is shared by both looks; the Milestones line says where the switch exists. kills: the line reworded for one look, or the Movement entries dropped
        with chrome() as cdp:
            help_milestones_line(self, self.visit(cdp))

    def test_mutant_cards_lost_its_switch_or_its_sentence_node(self):
        # kills: the Classic gate applied to every theme
        self.assertEqual(REAL_PAGE_HTML(EMPTY_BRANDING).count("data-mspage-switch"), 1)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.until("!!document.querySelector('#milestones .msl-row')", "the list drew")
            self.assertEqual(p.js("document.querySelectorAll('#milestones [data-mspv]').length"), 2, "the Plan | Movement switch")
            self.assertEqual(p.js("document.querySelectorAll('#ms-summary').length"), 1, "the sentence node")
            self.assertRegex(p.js("document.querySelector('#ms-summary').textContent"), r"achieved, \d+ to come\.$")


class Classic(Base):
    """The Classic hint line had a rule of its own; the hint and that rule are gone, and the title must still show."""
    def setUp(self):
        classic_page(self)
        super().setUp()

    def test_mutant_classic_rule_left_in_the_theme_or_the_title_hidden_with_it(self):
        # kills: the hint-hiding rule kept in Classic's rules.css; a replacement rule that also hides the title; Classic not the page under test
        rules = (SRC / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")
        g4 = [ln for ln in rules.split("\n") if ln.startswith("/* Row 1260 G4:") or ("[data-mspage-hint]" in ln and "[data-mspv" in ln)]
        self.assertEqual(len(g4), 2, "the restored Row 1260 G4 rule (comment + rule) is still in the theme")      # it stays: the Row 1260 test pins it; dead in Classic now the switch is gone
        rules = "\n".join(ln for ln in rules.split("\n") if ln not in g4)
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
    def setUp(self):
        classic_page(self)

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
