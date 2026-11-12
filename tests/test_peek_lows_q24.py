"""Three small looks found by eye (CMD 11-12-024): the milestone peek's empty Progress number box draws the dash the other empty fields draw
(a placeholder: the saved value stays empty, so clearing and 0 are still two things); the peek's field cards share one left edge with the title and
the tab underline (the body no longer adds 20 px of its own inside the peek's padding); and a phase bar on the Gantt is a solid fill that stands
off the row in dark as it does in light (the dark theme sets --phase-bar; light keeps the navy). No new words.

Run: python3 dev/run_tests.py test_peek_lows_q24
Browser parts at 1400 and 900 px, light and dark.
"""
import json
import unittest

import test_gantt_chart as tg
from test_gantt_chart import contrast, rgb
from test_gantt_logic import LINES
from test_milestone_peek_828 import GO_LIVE, Fields
from test_movement_page import Base
from test_peek_card import CardBrowser
from test_server import chrome, wait

EDGES = """(() => {
  const l = (s) => { const e = document.querySelector(s); return e ? Math.round(e.getBoundingClientRect().left * 10) / 10 : null; };
  return { title: l('#peek .pk-title'), tabs: l('#peek .pk-tabs'), card: Math.min(...[...document.querySelectorAll('#peek .pk-fields > .pk-row[data-row], #peek .pk-fields > .pk-row[data-ms-row]')].map((e) => Math.round(e.getBoundingClientRect().left * 10) / 10)), fields: l('#peek .pk-fields') };
})()"""


class Progress(Base):
    cur = GO_LIVE
    visit_peek = Fields.visit_peek

    def test_an_empty_progress_box_draws_the_dash_and_stays_empty(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    p = self.visit_peek(cdp, width=width, theme=theme)
                    p.until("!!document.querySelector('#peek [data-ms-num]')", "the number box")
                    self.assertEqual(p.js("document.querySelector('#peek [data-ms-num]').value"), "", "the saved value is empty")
                    self.assertEqual(p.js("document.querySelector('#peek [data-ms-num]').placeholder"), "—", "the same dash the other empty fields draw")
                    self.assertGreaterEqual(p.js("document.querySelector('#peek [data-ms-num]').getBoundingClientRect().width"), 40)

    def test_the_dash_is_drawn_in_the_muted_text_colour_not_the_browsers_default(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    p = self.visit_peek(cdp, width=width, theme=theme)
                    p.until("!!document.querySelector('#peek [data-ms-num]')", "the number box")
                    got = p.js("""(() => { const i = document.querySelector('#peek [data-ms-num]'); const probe = document.createElement('i');
                      probe.style.color = 'var(--text-muted)'; document.body.appendChild(probe);
                      const want = getComputedStyle(probe).color; probe.remove();
                      return JSON.stringify({got: getComputedStyle(i, '::placeholder').color, want}); })()""")
                    got = json.loads(got)
                    self.assertEqual(got["got"], got["want"], "the placeholder rule sets the muted colour at full strength")


class MilestoneEdges(Base):
    cur = GO_LIVE
    visit_peek = Fields.visit_peek

    def test_the_cards_start_where_the_title_and_the_tabs_start(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    p = self.visit_peek(cdp, width=width, theme=theme)
                    p.until("!!document.querySelector('#peek .pk-fields')", "the fields")
                    e = json.loads(p.js(f"JSON.stringify({EDGES})"))
                    self.assertAlmostEqual(e["fields"], e["title"], delta=1, msg=str(e))
                    self.assertAlmostEqual(e["card"], e["title"], delta=1, msg=str(e))
                    if e["tabs"] is not None:
                        self.assertAlmostEqual(e["tabs"], e["title"], delta=1, msg=str(e))


class ItemEdges(unittest.TestCase):
    setUpClass = CardBrowser.__dict__["setUpClass"]
    tearDownClass = CardBrowser.__dict__["tearDownClass"]
    load_page = CardBrowser.load_page
    edit_mode = CardBrowser.edit_mode
    ids_on_page = CardBrowser.ids_on_page
    show_item = CardBrowser.show_item

    def test_the_cards_start_where_the_title_and_the_tabs_start(self):
        for width in (1400, 900):
            with chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                item = self.ids_on_page(cdp, sid)[0]
                self.edit_mode(cdp, sid)
                for theme in ("light", "dark"):
                    cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", sid)
                    with self.subTest(width=width, theme=theme):
                        self.show_item(cdp, sid, item)
                        e = cdp.js(f"JSON.stringify({EDGES})", sid)
                        e = json.loads(e)
                        self.assertIsNotNone(e["tabs"], "Edit draws the tabs")
                        self.assertAlmostEqual(e["card"], e["title"], delta=1, msg=str(e))
                        self.assertAlmostEqual(e["tabs"], e["title"], delta=1, msg=str(e))


class PhaseBar(unittest.TestCase):
    setUpClass = tg.Chart.__dict__["setUpClass"]
    tearDownClass = tg.Chart.__dict__["tearDownClass"]
    js, val, until, look, motion, mount = (tg.Chart.__dict__[k] for k in ("js", "val", "until", "look", "motion", "mount"))

    def test_a_phase_bar_is_a_solid_fill_that_stands_off_its_row_in_both_themes(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme):
                    self.look(width, scheme)
                    self.mount(edit=False, lines=LINES)
                    c = self.val("(function(){ var s = function(sel, p){ return getComputedStyle(document.querySelector(sel))[p]; };"
                                 "return {pb: s('.gt-b-phase', 'backgroundColor'), pr: s('.gt-rw.gt-phase', 'backgroundColor'), sw: s('.gt-sw-p', 'backgroundColor')}; })()")
                    self.assertGreaterEqual(contrast(rgb(c["pb"]), rgb(c["pr"])), 3, f"the fill alone stands off its row: {c}")
                    self.assertEqual(c["sw"], c["pb"], "the legend swatch is the bar's own fill")
                    if scheme == "light":
                        self.assertEqual(c["pb"], "rgb(6, 47, 58)", "light keeps the navy")

    def test_a_phase_bar_stands_off_its_row_when_the_page_follows_a_dark_computer(self):
        # data-theme=auto reads the second copy of the dark tokens, inside the prefers-color-scheme block
        for width in (1400, 900):
            with self.subTest(width=width):
                self.look(width, "auto")
                self.cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": "dark"}, {"name": "prefers-reduced-motion", "value": "no-preference"}]}, self.sid)
                try:
                    self.mount(edit=False, lines=LINES)
                    c = self.val("(function(){ var s = function(sel, p){ return getComputedStyle(document.querySelector(sel))[p]; };"
                                 "return {pb: s('.gt-b-phase', 'backgroundColor'), pr: s('.gt-rw.gt-phase', 'backgroundColor')}; })()")
                    self.assertGreaterEqual(contrast(rgb(c["pb"]), rgb(c["pr"])), 3, f"the fill alone stands off its row: {c}")
                finally:
                    self.cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": ""}]}, self.sid)


if __name__ == "__main__":
    unittest.main()
