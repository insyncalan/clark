"""#518: what the absolute rules in shell.css and edit.css stand on.

`main` is position: relative, so an absolute element in it that has no positioned ancestor of its own is drawn against `main`.
- Static: shell.css keeps `main { position: relative }`.
- Page (View and Edit, 1400 px): every absolutely placed element under `main` has an offsetParent; one that stands on `main` itself
  is only a one-pixel reader-only label (class sr, tpl-sr or ask-who); every other one stands on its own wrapper, and lies inside
  the box of `main` (to a pixel), unless it is out of sight on purpose or inside a strip that scrolls (the milestone strip).

Run: python3 dev/run_tests.py test_main_anchor
Needs Chrome (the #33 harness): the page test fails, never skips, without it. Fictional data only.
"""
import re
import unittest

from _paths import SRC
from test_report_editor import Base as PageBase, tearDownModule  # noqa: F401
from test_server import chrome

SHELL = SRC / "clark" / "page" / "shell.css"
READER_ONLY = {"sr", "tpl-sr", "ask-who"}

FIND = """(() => {
  const main = document.querySelector('main'), box = main.getBoundingClientRect(), out = [];
  for (const e of main.querySelectorAll('*')) {
    if (getComputedStyle(e).position !== 'absolute') continue;
    const at = e.offsetParent, r = e.getBoundingClientRect();
    if (!at && r.width === 0 && r.height === 0) continue;                           // not drawn at all (display: none)
    const cs = getComputedStyle(e);
    let moves = cs.opacity === '0' || cs.visibility === 'hidden';                    // out of sight on purpose (a card shown on hover)
    for (let a = e.parentElement; a && a !== main; a = a.parentElement) if (getComputedStyle(a).overflowX !== 'visible' && a.scrollWidth > a.clientWidth) moves = true;   // inside a strip that scrolls
    out.push({moves, tag: e.tagName.toLowerCase(), cls: String(e.className), on: at === main ? 'main' : (at ? at.tagName.toLowerCase() + '.' + String(at.className) : 'none'),
              inside: moves || r.left >= box.left - 1 && r.right <= box.right + 1 && r.top >= box.top - 1 && r.bottom <= box.bottom + 1,
              tiny: r.width <= 1 && r.height <= 1});
  }
  return out;
})()"""


class Static(unittest.TestCase):
    def test_main_is_the_positioned_box_the_absolute_rules_fall_back_on(self):
        css = SHELL.read_text(encoding="utf-8")
        rule = re.search(r"(?m)^main\s*\{([^}]*)\}", css)
        self.assertIsNotNone(rule, "shell.css has a bare main rule")
        self.assertRegex(rule.group(1), r"position:\s*relative", "main is position: relative")


class InThePage(PageBase):
    def look(self, cdp, edit):
        p = self.visit(cdp)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        if edit:
            p.edit()
        return p.js(FIND)

    def check(self, found):
        for e in found:
            with self.subTest(e=e):
                classes = set(e["cls"].split())
                self.assertNotEqual(e["on"], "none", "a drawn absolute element has an offsetParent")
                if e["on"] == "main":
                    self.assertTrue(classes & READER_ONLY and e["tiny"], "only a one-pixel reader-only label stands on main itself")
                else:
                    self.assertTrue(e["inside"], "an absolute element lies inside the box of main")

    def test_view_absolute_elements_have_their_own_anchor(self):
        with chrome() as cdp:
            self.check(self.look(cdp, False))

    def test_edit_absolute_elements_have_their_own_anchor(self):
        with chrome() as cdp:
            found = self.look(cdp, True)
            self.assertTrue([e for e in found if "sec-ctl" in e["cls"]], "Edit draws the section controls, so the audit saw them")
            self.check(found)


if __name__ == "__main__":
    unittest.main()
