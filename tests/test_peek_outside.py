"""Row 814: the peek closes on Esc and on a click outside it.

Run: python3 dev/run_tests.py test_peek_outside

In a real browser at 1400 and 900 px, light and dark, in View and in Edit, on Work items and on the Dashboard: Esc closes the peek
(focus on the page, and on a button inside the peek); a click on blank page outside it closes it; a click inside it, a click on another
row (which moves the peek), a click inside a menu or dialog standing over the page, and a press inside that ends outside (a drag that
selects text) do not. No new words: the test reads no text.
"""
import json
import re
import time
import unittest

from _paths import ROOT

import test_peek as tp  # noqa: E402
from test_peek import key  # noqa: E402
from test_server import chrome, wait  # noqa: E402
from test_work_filters import click  # noqa: E402

SRC = ROOT / "src" / "clark" / "page" / "src"

PROBE = """(() => {
  document.querySelectorAll('[data-outside-probe]').forEach((e) => e.removeAttribute('data-outside-probe'));
  const peek = document.querySelector('#peek'), left = peek ? peek.getBoundingClientRect().left : innerWidth;
  const pick = [...document.querySelectorAll('body *')].find((e) => {
    if (e.closest('#peek, [role=menu], dialog, button, a, tr, article, .wl-row, input, select, textarea, label, [tabindex]:not([tabindex="-1"]), [role=button], [role=tab], svg, nav') || e.childElementCount || !e.textContent.trim() || getComputedStyle(e).visibility !== 'visible') return false;
    const r = e.getBoundingClientRect(); return r.width > 10 && r.height > 5 && r.top >= 0 && r.bottom < innerHeight && r.left + r.width / 2 < left - 8 && r.left >= 0 && r.right < left - 8;
  });
  if (!pick) return false; pick.setAttribute('data-outside-probe', '1'); return true;
})()"""


class OutsideBrowser(unittest.TestCase):
    setUpClass = tp.Browser.__dict__["setUpClass"]
    tearDownClass = tp.Browser.__dict__["tearDownClass"]
    load_page = tp.Browser.load_page
    edit_mode = tp.Browser.edit_mode
    ids_on_page = tp.Browser.ids_on_page

    def show(self, cdp, sid, view, item):
        cdp.js(f"location.hash = '#{view}&p={self.code}&item={item}'", sid)
        self.assertTrue(wait(lambda: cdp.js("(() => { const p = document.querySelector('#peek'); return !!p && p.dataset.peek === " + json.dumps(item) + "; })()", sid)), item)
        self.assertTrue(wait(lambda: cdp.js("document.querySelector('#peek').getAnimations().length === 0", sid)))
        time.sleep(0.2)

    def is_open(self, cdp, sid, settle=0.7):
        time.sleep(settle)
        return bool(cdp.js("!!document.querySelector('#peek')", sid))

    def test_esc_and_a_click_outside_close_it_and_clicks_that_belong_to_it_do_not(self):
        for width in (1400, 900):
            with chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                ids = self.ids_on_page(cdp, sid)
                item, other = ids[0], ids[1]
                for mode in ("view", "edit"):
                    if mode == "edit":
                        self.edit_mode(cdp, sid)
                    for theme in ("light", "dark"):
                        cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", sid)
                        for view in ("work", "dashboard"):
                            where = f"{width} {mode} {theme} {view}"
                            with self.subTest(where):
                                if view == "dashboard":
                                    cdp.js("document.querySelector('[data-view=dashboard]').click()", sid)
                                    time.sleep(0.5)
                                else:
                                    cdp.js("document.querySelector('[data-view=work]').click()", sid)
                                    self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid) > 0))
                                # Esc, with the focus on the page and on a button in the peek
                                self.show(cdp, sid, view, item)
                                cdp.js("document.activeElement.blur()", sid)
                                key(cdp, sid, "Escape")
                                self.assertFalse(self.is_open(cdp, sid), f"{where}: Esc with the focus on the page")
                                self.show(cdp, sid, view, item)
                                cdp.js("document.querySelector('#peek [data-pk-next]').focus()", sid)
                                key(cdp, sid, "Escape")
                                self.assertFalse(self.is_open(cdp, sid), f"{where}: Esc with the focus in the peek")
                                # a click inside it keeps it
                                self.show(cdp, sid, view, item)
                                click(cdp, sid, "#peek .pk-title")
                                self.assertTrue(self.is_open(cdp, sid), f"{where}: a click inside the peek keeps it")
                                # a click inside a menu or a dialog over the page keeps it
                                cdp.js("(() => { const m = document.createElement('div'); m.setAttribute('role', 'menu'); m.id = 'probe-menu'; m.style.cssText = 'position:fixed;left:8px;top:8px;width:120px;height:40px;z-index:99'; document.body.appendChild(m); })()", sid)
                                click(cdp, sid, "#probe-menu")
                                self.assertTrue(self.is_open(cdp, sid), f"{where}: a click inside a menu keeps it")
                                cdp.js("document.getElementById('probe-menu').remove()", sid)
                                # a press inside that ends outside (selecting text) keeps it
                                # below 1000 px the peek fills the window (row 847): there is no page outside it to click, so Esc and Close are the way out
                                if width < 1000:
                                    self.assertEqual(round(cdp.js("document.querySelector('#peek').getBoundingClientRect().left", sid)), 0, where)
                                    continue
                                cdp.js("document.querySelector('#peek .pk-title').dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}))", sid)
                                self.assertTrue(cdp.js(PROBE, sid), f"{where}: a blank place outside the peek to click")
                                cdp.js("document.querySelector('[data-outside-probe]').click()", sid)
                                self.assertTrue(self.is_open(cdp, sid), f"{where}: a drag that ends outside keeps it")
                                # a click on another row moves the peek (Work items)
                                if view == "work":
                                    visible = cdp.js("(() => { const r = document.querySelector('#work tbody tr[data-id=\"" + other + "\"] .c-item'); if (!r) return false; const b = r.getBoundingClientRect(); const p = document.querySelector('#peek').getBoundingClientRect(); return b.right < p.left; })()", sid)
                                    if visible:
                                        click(cdp, sid, f"#work tbody tr[data-id='{other}'] .c-item")
                                        self.assertTrue(wait(lambda: cdp.js("(document.querySelector('#peek') || {dataset: {}}).dataset.peek", sid) == other), f"{where}: a click on a row moves the peek")
                                        self.show(cdp, sid, view, item)
                                # a click on blank page outside closes it
                                self.assertTrue(cdp.js(PROBE, sid), f"{where}: a blank place outside the peek to click")
                                click(cdp, sid, "[data-outside-probe]")
                                self.assertFalse(self.is_open(cdp, sid), f"{where}: a click outside closes it")
                                self.assertNotIn("item=", cdp.js("location.hash", sid), where)
                cdp.js("document.documentElement.dataset.theme = 'light'", sid)

    def test_the_rule_is_in_the_source_and_adds_no_words(self):
        src = (SRC / "peek" / "outside.js").read_text(encoding="utf-8")
        peek = (SRC / "components" / "Peek.jsx").read_text(encoding="utf-8")
        self.assertIn("closesPeek", peek)
        self.assertRegex(src, r"\[role=menu\]")
        self.assertNotRegex(src, r"#\d{3}", "no hash and digits in a comment")


if __name__ == "__main__":
    unittest.main()
