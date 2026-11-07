"""#436 row 18: the Milestones page's Plan / Movement switch is in View as well as Edit (system/prototype/views.js:1188-95), with the
prototype's hint that Movement is never published. Row 823: the Milestones page has no mode, so Movement has its choices and the
Internal note in View too.

Run: CLARK_CHROME=/usr/local/bin/clark-chrome python3 dev/run_tests.py test_movement_in_view
Without a browser: the published file holds no switch, no hint and nothing of Movement. With headless Chrome (fails, never skips,
without it): in View the switch shows, Movement reads GET /api/movement and draws the sentence, the rows and the card with its
choices and note, makes no change request until one is used, and a row still picks the card; Edit looks the same. At 1400
and 900 px, light and dark. The published file in the browser has neither the switch nor Movement.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from clark import movement_view as mv, publish
from test_movement_page import AUDIT, GO_LIVE, EMPTY_BRANDING, PILOT, Base, js_constants
from test_server import chrome, wait
from test_work_items import page_target

CHOICES = "#mv-hold, #mv-move, #mv-recover, #mv-escalate, #mvNote, .mvm-form, .mvm-actions"
FIELDS = "(() => [...document.querySelectorAll('#milestones input, #milestones textarea, #milestones select, #milestones [contenteditable], #milestones [data-edit-only]')].map(e => e.tagName + '#' + e.id + '.' + e.className))()"


class InView(Base):
    def view_movement(self, p):
        p.until("!!document.querySelector('[data-mspage-switch] [data-mspv=move]')", "View has the switch")
        p.js("document.querySelector('[data-mspv=move]').click()")
        p.until("!!document.querySelector('#movement .mvm-card')", "Movement drew in View")

    def test_view_has_the_switch_and_movement_with_its_choices_at_1400_and_900_light_and_dark(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    self.reads.clear()
                    self.sent.clear()
                    p = self.visit(cdp, width=width, theme=theme)
                    p.until("!!document.querySelector('[data-mspage-switch]')", "View has the switch")
                    self.assertEqual(p.js("[...document.querySelectorAll('[data-mspv]')].map(b => b.textContent)"), ["Plan", "Movement"])
                    self.view_movement(p)
                    self.assertIn("Undo", p.js("document.querySelector('[data-mspage-hint]').textContent"), "the page is live: the hint says each move can be undone")
                    self.assertEqual(p.js("document.querySelector('[data-mspv=move]').getAttribute('aria-pressed')"), "true")
                    self.assertEqual(p.js("document.querySelector('#movement .tag').textContent"), mv.TAG_INTERNAL)
                    self.assertEqual(p.js("document.querySelector('.mvm-sentence').textContent"), "1 of 2 open milestones are behind their agreed date; 1 overdue.")
                    self.assertEqual(p.js("[...document.querySelectorAll('.mvm-row .mvm-name')].map(e => e.textContent)"), ["Go live", "Pilot live"])
                    text = p.js("document.querySelector('.mvm-card').textContent")
                    for want in ("Original", "Agreed", "Forecast", "What changed", "Priya Example"):
                        self.assertIn(want, text)
                    for want in ("Decide what to do", mv.HOLD_LABEL, mv.MOVE_LABEL, "Add a recovery action", "Escalate to steering", "Internal note"):
                        self.assertIn(want, text, want)
                    self.assertEqual(p.js("document.querySelectorAll('[data-mode]').length"), 0, "no View | Edit switch off the Dashboard: the page is always editable")
                    self.assertEqual(p.js("!!document.querySelector('#mv-hold') && !!document.querySelector('#mv-move') && !!document.querySelector('#mvNote')"), True, "the choices and the note are there in View")
                    self.assertEqual(p.js("!!document.querySelector('#movement[data-readonly]')"), False)
                    p.js("document.querySelector('.mvm-row[data-id=\"%s\"]').click()" % PILOT)
                    p.until("document.querySelector('#mv-card-h').textContent === 'Pilot live'", "a row still picks the card in View")
                    self.assertEqual(json.loads(p.js(AUDIT)), [])
                    dark = p.js("getComputedStyle(document.documentElement).colorScheme")
                    self.assertEqual("dark" in dark, theme == "dark", dark)
                    self.assertTrue(self.reads, "View reads what Edit reads: GET /api/movement")
                    self.assertEqual(self.sent, [], "nothing changes until a choice is used")
                    p.js("document.querySelector('[data-mspv=plan]').click()")
                    p.until("!!document.querySelector('.msv') && !document.querySelector('#movement')", "Plan in View")

    def test_hold_works_in_view_and_one_undo_takes_it_back(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.view_movement(p)
            self.assertEqual(p.js("document.querySelectorAll('[data-mode]').length"), 0, "no View | Edit switch off the Dashboard: the page is always editable")
            p.js("document.querySelector('#mv-hold').click()")
            p.until("(document.querySelector('.toast .toast-text') || {}).textContent === 'Hold recorded in the note. Undo.'", "the Hold toast in View")
            self.assertEqual(self.store.read("milestones", ref=GO_LIVE)["movement"], "hold")
            p.js("document.querySelector('.toast [data-undo]').click()")
            p.until("(document.querySelector('.toast .toast-text') || {}).textContent === 'Undone.'", "Undone")
            self.assertIsNone(self.store.read("milestones", ref=GO_LIVE)["movement"])


class Published(unittest.TestCase):
    def test_the_published_file_has_no_switch_and_no_movement(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        with demo.store.step("dashboard", USER) as step:
            step.update("milestones", demo.milestone, {"client_visible": 1})
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(shutil.rmtree, folder, True)
        done = publish.publish(demo.store, "ABC", folder, by_user=USER, now="2030-01-15", branding=EMPTY_BRANDING)
        text = Path(done["path"]).read_text(encoding="utf-8")
        for never in ("data-mspage-switch", "data-mspv", "data-mspage-hint", "msp.view", "/api/movement", "mvm-", mv.HELP_LINE, mv.TAG_INTERNAL):
            self.assertNotIn(never, text, never)
        for name, words in js_constants().items():
            if len(words) > 12 and name not in ("NOT_HERE", "ARCHIVED"):
                self.assertNotIn(words, text, name)
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.navigate", {"url": Path(done["path"]).as_uri()}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready === '1'", sid)))
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
            cdp.js("try { localStorage.setItem('clark.msp.view', JSON.stringify('move')); } catch (e) {}", sid)
            cdp.js("[...document.querySelectorAll('.tab')].find(t => /Milestones/.test(t.textContent)).click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#ms-summary')", sid)), "the Milestones page drew")
            self.assertEqual(cdp.js("document.querySelectorAll('[data-mspage-switch], [data-mspv], #movement, .mvm-card').length", sid), 0,
                             "a published file has neither the switch nor Movement")
            self.assertNotIn("never published", cdp.js("document.body.textContent", sid))


if __name__ == "__main__":
    unittest.main()
