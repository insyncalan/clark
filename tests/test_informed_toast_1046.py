"""Row 1046: the message that only informs ("Database refreshed") is a toast kind of its own: a database icon, its lead, a sentence, Close and
no Undo, a teal edge, 8 seconds (held while focus is in it), and its own place, so a change's message never replaces it. The real page and a
real server over the fictional demo report (the harness of tests/test_report_editor.py), headless Chrome at 1400 px (the message is one pill; its look at 900 is the change toast's).

Run: python3 dev/run_tests.py test_informed_toast_1046
"""
import time
import unittest

from test_report_editor import Base  # noqa: E402
from test_server import chrome  # noqa: E402

INF = ".toasts-informed .toast.informed"
SAY = "window.clarkPage.sayInformed('The shared database has new data.')"
GONE = f"!document.querySelector('{INF}')"


class InformedToast(Base):
    def start(self, cdp):
        p = self.visit(cdp)
        p.edit()
        p.js(SAY)
        p.until(f"!!document.querySelector('{INF}')", "the message is drawn")
        self.t0 = time.monotonic()
        return p

    def at(self, seconds):
        wait = self.t0 + seconds - time.monotonic()
        if wait > 0:
            time.sleep(wait)

    def test_it_has_icon_lead_sentence_and_close_but_no_undo_and_a_teal_edge(self):
        with chrome() as cdp:
            p = self.start(cdp)
            got = p.js(f"(() => {{ const t = document.querySelector('{INF}'); return JSON.stringify({{lead: t.querySelector('.toast-lead').textContent,"
                       " text: t.querySelector('.toast-text').textContent, icon: !!t.querySelector('svg.toast-ico'), undo: !!t.querySelector('[data-undo]'),"
                       " close: !!t.querySelector('[data-dismiss]'), kind: t.dataset.kind, edge: getComputedStyle(t).borderTopColor,"
                       " green: getComputedStyle(document.documentElement).getPropertyValue('--status-green').trim(), live: t.closest('[aria-live]').getAttribute('aria-live')}); })()")
            import json
            g = json.loads(got)
            self.assertEqual(g["lead"], "Database refreshed")
            self.assertEqual(g["text"], "Database refreshed The shared database has new data.")
            self.assertTrue(g["icon"], "a database icon")
            self.assertFalse(g["undo"], "no Undo: the person changed nothing")
            self.assertTrue(g["close"])
            self.assertEqual(g["kind"], "informed")
            self.assertNotIn("rgba(0, 0, 0, 0)", g["edge"], "the edge is coloured")
            self.assertTrue(g["green"], "the edge is the page's teal-green token")
            self.assertEqual(g["live"], "polite")

    def test_it_stays_past_5_seconds_and_is_gone_by_9(self):
        with chrome() as cdp:
            p = self.start(cdp)
            p.js("document.activeElement && document.activeElement.blur()")
            self.at(6.5)
            self.assertTrue(p.js(f"!!document.querySelector('{INF}')"), "still there at 6.5 seconds (a change's message has gone by 5)")
            p.until(GONE, "gone by itself", 4)
            self.assertGreater(time.monotonic() - self.t0, 7.5, "not before about 8 seconds")

    def test_focus_in_it_holds_the_time_and_close_ends_it_at_once(self):
        with chrome() as cdp:
            p = self.start(cdp)
            p.js(f"document.querySelector('{INF} [data-dismiss]').focus()")
            self.at(9.5)
            self.assertTrue(p.js(f"!!document.querySelector('{INF}')"), "held while focus is in it")
            p.js(f"document.querySelector('{INF} [data-dismiss]').click()")
            self.assertTrue(p.js(GONE), "Close takes it away")

    def test_a_second_message_restarts_the_8_seconds(self):
        with chrome() as cdp:
            p = self.start(cdp)
            p.js("document.activeElement && document.activeElement.blur()")
            self.at(5.0)
            p.js("window.clarkPage.sayInformed('Newer.', 'Database refreshed')")
            self.at(10.0)
            self.assertTrue(p.js(f"document.querySelector('{INF} .toast-text').textContent.includes('Newer.')"), "the newer words, and still there 5 seconds after them")
            p.until(GONE, "gone 8 seconds after the newer one", 5)

    def test_a_second_message_is_a_new_element_so_its_bar_and_clock_start_again(self):
        with chrome() as cdp:
            p = self.start(cdp)
            p.js(f"document.querySelector('{INF}').dataset.first = '1'")
            p.js("window.clarkPage.sayInformed('Newer.', 'Database refreshed')")
            p.until(f"(() => {{ const t = document.querySelector('{INF}'); return !!t && t.textContent.includes('Newer.'); }})()", "the newer words are drawn")
            self.assertTrue(p.js(f"document.querySelector('{INF}').dataset.first === undefined"), "a new id makes a new element (the key), not the old one re-worded")

    def test_it_sits_in_its_own_slot_72px_above_the_bottom(self):
        with chrome() as cdp:
            p = self.start(cdp)
            off = p.js(f"window.innerHeight - document.querySelector('.toasts-informed').getBoundingClientRect().bottom")
            self.assertAlmostEqual(off, 72, delta=1, msg="the informed slot's bottom edge is 72px above the window bottom")

    def test_a_change_message_does_not_replace_it(self):
        with chrome() as cdp:
            p = self.start(cdp)
            p.js("document.querySelector('[data-id=\"ABC-S-003\"] [data-options]').click()")
            p.until("!!document.querySelector('[data-id=\"ABC-S-003\"] .menu')", "the menu opened")
            p.js("document.querySelector('[data-id=\"ABC-S-003\"] [data-act=add]').click()")
            p.until("!!document.querySelector('[data-template=gantt] input')", "Add a section offers Gantt")
            p.js("document.querySelector('[data-template=gantt] input').click()")
            p.js("document.querySelector('button[data-place]').click()")
            p.until("!!document.querySelector('.toast [data-undo]')", "the change message offers Undo")
            self.assertTrue(p.js(f"!!document.querySelector('{INF}')"), "the informed message is still there beside it")
            boxes = p.js(f"(() => {{ const a = document.querySelector('{INF}').getBoundingClientRect(), b = document.querySelector('.toast [data-undo]').closest('.toast').getBoundingClientRect(); return a.bottom <= b.top + 1 || b.bottom <= a.top + 1; }})()")
            self.assertTrue(boxes, "they do not overlap")
            off = p.js(f"window.innerHeight - document.querySelector('.toasts-informed').getBoundingClientRect().bottom")
            self.assertAlmostEqual(off, 72, delta=1, msg="the informed slot keeps its slot with a change message beside it")


if __name__ == "__main__":
    unittest.main()
