"""Row 1270 slice 2: a RAID card in the published file is one tab stop (its ID button); a click, Enter or Space on it opens the read-only Peek,
and Esc closes it. No new words: the button shows the ID that was already there.

Run: python3 dev/run_tests.py test_raid_cards_peek_1270
Fictional rows. Opened in headless Chrome at 1400 and 900 (the only widths checked).
"""
import json

from _demo import USER
from _publish import PublishedFile
import test_glance_page as glance
from test_server import chrome, wait

STATE = """(() => { const p = document.querySelector('#peek'); const a = document.activeElement;
  return { stops: [...document.querySelectorAll('.raid-card button, .raid-card a, .raid-card [tabindex]')].map(e => e.className + ':' + e.textContent),
           open: !!p && !p.hidden && p.getBoundingClientRect().width > 0, text: p ? p.textContent : '', active: a ? (a.className + ':' + a.textContent) : '' }; })()"""


class RaidCardsPeek(PublishedFile, glance.Setup):
    def seed(self):
        self.demo.plant_builtin_sections()      # the cards are drawn beside the built-in sections (row 1193)
        with self.store.step("dashboard", USER) as st:
            i = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Kiln roof may leak", "raised": "2026-10-01", "source": "demo",
                                   "impact": "High", "likelihood": "High", "client_message": "Words for the client."})
            ref = st.create("report_sections", {"project": "ABC", "type": "raid3", "title": "Fictional cards", "sort_order": 993})
            st.update("report_sections", ref, {"body": json.dumps({"v": 1, "cards": [{"id": i, "source": "client"}]})})
        return i

    def test_the_id_button_is_the_only_stop_and_opens_and_closes_the_peek(self):
        rid = self.seed()
        path = self.publish()
        with chrome() as cdp:
            for w in (1400, 900):
                p = self.draw(cdp, path, width=w)
                s = p.js(STATE)
                self.assertEqual(s["stops"], ["idl raid-id:" + rid], "one tab stop per card, the ID button: %s" % s["stops"])
                self.assertFalse(s["open"], w)
                p.js("document.querySelector('.raid-card .idl').click()")
                self.assertTrue(wait(lambda: p.js(STATE)["open"]), "the peek opens at %d" % w)
                self.assertIn(rid, p.js(STATE)["text"])
                p.js("document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
                self.assertTrue(wait(lambda: not p.js(STATE)["open"]), "Esc closes it at %d" % w)

    def test_enter_and_space_on_the_focused_id_button_open_the_peek(self):
        rid = self.seed()
        path = self.publish()
        with chrome() as cdp:
            for w, key, code, vk, text in [(w,) + k for w in (1400, 900) for k in (("Enter", "Enter", 13, "\r"), (" ", "Space", 32, " "))]:
                p = self.draw(cdp, path, width=w)
                p.js("document.querySelector('.raid-card .idl').focus()")
                for kind in ("keyDown", "keyUp"):       # a real key press
                    cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": key, "code": code, "windowsVirtualKeyCode": vk, **({"text": text} if kind == "keyDown" else {})}, p.sid)
                self.assertTrue(wait(lambda: p.js(STATE)["open"]), "%s on the ID button opens the peek at %d" % (code, w))

    def test_a_cards_peek_fills_the_window_at_900_light_and_dark(self):
        """'Fills the window' is the page's client width (the window less a scrollbar gutter), from the left edge."""
        rid = self.seed()
        path = self.publish()
        box = "(() => { const r = document.querySelector('#peek').getBoundingClientRect(); return [Math.round(r.left), Math.round(r.width), document.documentElement.clientWidth]; })()"
        with chrome() as cdp:
            for dark in (False, True):
                p = self.draw(cdp, path, width=900, dark=dark)
                p.js("document.querySelector('.raid-card .idl').click()")
                self.assertTrue(wait(lambda: p.js(STATE)["open"] and rid in p.js(STATE)["text"]), "the peek opens")
                self.assertTrue(wait(lambda: (lambda b: b[0] == 0 and b[1] == b[2])(p.js(box))), "the peek spans the client width from the left at 900, dark=%s: %s" % (dark, p.js(box)))
