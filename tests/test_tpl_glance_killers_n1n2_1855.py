"""Row 1264, PR 1855: the Done in flight is kept per section, and Remove waits for it. Real browser, behaviour not source text.
A held request keeps a Done in flight. Fictional data only.

Run: python3 dev/run_tests.py test_tpl_glance_killers_n1n2_1855
"""
import json
import time
import unittest

from test_tpl_glance_editor_1264 import Editor, OWN, tearDownModule  # noqa: F401
from test_server import chrome, wait

HOLD = """window.__sent = 0; window.__gate = null; var real = window.fetch;
window.fetch = function (u, o) {
  if (String(u).indexOf('/api/section-body') >= 0 || String(u).indexOf('/api/change') >= 0) {
    window.__sent++;
    if (window.__gate) { var g = window.__gate; return g.then(function () { return real(u, o); }); }
  }
  return real(u, o);
};"""


class InFlight(Editor):
    def pencil(self, p, sid=None, tid="t1"):
        root = f'[data-id="{sid or self.ref}"]'
        p.js(f"document.querySelector('{root} [data-tile={tid}] [data-tile-pencil]').click()")
        p.until(f"!!document.querySelector('{root} [data-tile-editor]')", "the editor")

    def hold(self, p):
        p.js(HOLD)
        p.js("window.__gate = new Promise(function (r) { window.__open = r; }); 0")        # js() waits for a promise: the gate is opened later, so it is not the value

    def release(self, p):
        p.js("window.__open()")

    def test_n1_a_second_done_in_the_same_section_sends_nothing_more(self):
        self.seed([OWN])
        with chrome() as cdp:
            p = self.page(cdp)
            self.hold(p)
            self.pencil(p)
            self.fill(p, "label", "Fictional held")
            p.js(f"var b = document.querySelector({self.q('[data-tile-editor] [data-done]')}); b.click(); b.click(); b.click();")
            p.js("new Promise(r => setTimeout(r, 400))")
            self.release(p)
            self.assertTrue(wait(lambda: self.body()["bespoke"][0]["label"] == "Fictional held", 10))
            p.until(f"!document.querySelector({self.q('[data-tile-editor]')})", "the editor closed")
            time.sleep(1)
            self.assertEqual(p.js("window.__sent"), 1, "one request for three presses")

    def test_n1_after_a_done_ends_the_same_section_can_save_again(self):
        self.seed([OWN])
        with chrome() as cdp:
            p = self.page(cdp)
            p.js(HOLD)
            for word in ("Fictional one", "Fictional two"):
                self.pencil(p)
                self.fill(p, "label", word)
                self.click(p, "[data-tile-editor] [data-done]")
                self.assertTrue(wait(lambda w=word: self.body()["bespoke"][0]["label"] == w, 10), word)
                p.until(f"!document.querySelector({self.q('[data-tile-editor]')})", "the editor closed")
            self.assertEqual(p.js("window.__sent"), 2)

    def test_n2_remove_pressed_while_its_done_is_in_flight_does_not_drop_the_tile(self):
        self.seed([OWN])
        with chrome() as cdp:
            p = self.page(cdp)
            self.hold(p)
            self.pencil(p)
            self.fill(p, "label", "Fictional kept")
            self.click(p, "[data-tile-editor] [data-done]")
            p.js("new Promise(r => setTimeout(r, 300))")
            self.click(p, "[data-tile-editor] [data-remove]")
            p.js("new Promise(r => setTimeout(r, 300))")
            self.release(p)
            self.assertTrue(wait(lambda: self.body().get("bespoke") and self.body()["bespoke"][0]["label"] == "Fictional kept", 10), f"stored: {self.body()}")
            time.sleep(1.5)
            self.assertEqual(p.js("window.__sent"), 1, "Remove sent nothing")
            self.assertEqual(self.body()["bespoke"][0]["label"], "Fictional kept", "the tile is still there")

    def test_n2_a_draft_with_a_blank_label_removes_with_the_untitled_words(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.click(p, ".tileadd")
            p.js("document.querySelector('.ddmenu[role=menu] [role=menuitem]').click()")
            self.editor_open(p)
            self.fill(p, "label", "   ")
            self.click(p, "[data-tile-editor] [data-remove]")
            p.until(f"!document.querySelector({self.q('[data-tile-editor]')})", "the editor closed")
            self.assertEqual(self.toast(p), "Removed: Untitled")


if __name__ == "__main__":
    unittest.main()
