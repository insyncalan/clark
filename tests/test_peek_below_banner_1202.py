"""Item 1202: every peek starts below the nav banner and runs to the bottom of the screen. Row 1258 (v1.1.1) made the item, milestone and archived peeks
a floating card; row 1289 (v1.3) reverses that: every peek is flush right, banner to window bottom, square (test_peek_anchor_1289 and test_peek_frame_1258 measure it).
Run: python3 dev/run_tests.py test_peek_below_banner_1202

Part 1 reads the stylesheets: every peek (the item, milestone, archived and Help peeks all carry class peek) takes its place from one rule
that starts at the banner's height (--topbar), stays flush right and to the bottom, and has no inset and no rounded outer corners; no other
rule moves a peek back to the top or shortens it; the prototype's peek follows.
Part 2 is a real browser at 1400 and 900 px, light and dark: one peek of each kind of work item on the page (action, risk, issue, decision,
whichever the demo has) has its top edge on the banner's bottom edge, its bottom edge on the bottom of the window, and its right edge on the
window's; the banner stays on top of it and its buttons stay clickable.
"""
import json
import re
import unittest

from _paths import ROOT

import test_peek as tp  # noqa: E402
from test_server import chrome, wait  # noqa: E402

PAGE = ROOT / "src" / "clark" / "page"
CSS = (PAGE / "shell.css").read_text(encoding="utf-8")
EDIT_CSS = (PAGE / "src" / "edit" / "edit.css").read_text(encoding="utf-8")
PROTO = (ROOT / "system" / "prototype" / "app.css").read_text(encoding="utf-8")


def rule(text, selector):
    m = re.search(r"^" + re.escape(selector) + r" \{([^}]*)\}", text, re.M)
    assert m, selector
    return m.group(1)


class PeekBelowBanner(unittest.TestCase):
    def test_starts_below_the_banner(self):
        body = rule(CSS, ".peek")
        self.assertRegex(body, r"position:\s*fixed")
        self.assertRegex(body, r"top:\s*var\(--topbar\)")
        self.assertRegex(body, r"right:\s*0[;\s]")
        self.assertRegex(body, r"bottom:\s*0[;\s]")        # row 1289: the one base rule is the whole frame, flush to the bottom for every peek

    def test_the_item_milestone_and_archived_peeks_are_the_16_px_card(self):
        self.assertNotRegex(CSS, r"(?m)^\.peek:not\(\.hpk\) \{")      # row 1289 reverses row 1258: no card rule is left, every peek is flush
        self.assertNotIn("border-radius", rule(CSS, ".peek"))
        self.assertNotRegex(rule(CSS, ".peek"), r"top:\s*(0|16px)\b")

    def test_the_help_peek_keeps_the_banner_line_and_sets_no_height(self):
        body = rule(CSS, ".hpk")
        self.assertRegex(body, r"top:\s*var\(--topbar\)")
        self.assertNotRegex(body, r"(^|[;\s])(height|max-height|bottom):")

    def test_no_other_rule_moves_a_peek_to_the_top_or_shortens_it(self):
        for name, text in (("shell.css", CSS), ("edit.css", EDIT_CSS)):
            for m in re.finditer(r"([^{}\n]*)\{([^}]*)\}", text):
                sel, body = m.group(1), m.group(2)
                if not re.search(r"(^|[\s,>])(\.peek|\.hpk|#peek|#help-peek|#archived-peek|#peek-archived)([\s,.:\[{]|$)", sel.strip() + " "):
                    continue
                if re.search(r"\.peek\s+\S|\.hpk\s+\S|#\w+\s+\S", sel.strip()):
                    continue                                                    # a rule for something inside the peek
                if sel.strip() in (".peek", ".hpk", ".peek:not(.hpk)"):
                    continue                                                    # checked above
                self.assertNotRegex(body, r"(^|[;\s])(top|bottom|height|max-height|inset):", f"{name}: {sel.strip()}")

    def test_the_prototype_peek_starts_below_its_banner(self):
        body = rule(PROTO, ".peek")
        self.assertRegex(body, r"top:\s*var\(--topbar\)")
        self.assertRegex(body, r"bottom:\s*0[;\s]")
        self.assertNotIn("border-radius", body)
        built = (ROOT / "system" / "prototype" / "app-css.js").read_text(encoding="utf-8")
        self.assertIn(".peek { position: fixed; top: var(--topbar); right: 0; bottom: 0;", built, "app-css.js is made by build_css.py from app.css")


GEOM = """(() => {
  const p = document.querySelector('#peek'), t = document.querySelector('header.top');
  const r = p.getBoundingClientRect(), b = t.getBoundingClientRect();
  const probe = document.elementFromPoint(b.left + 40, b.top + b.height / 2);
  return [r.top, r.bottom, r.right, b.bottom, innerHeight, document.documentElement.clientWidth, !!probe && t.contains(probe), getComputedStyle(p).borderTopLeftRadius];
})()"""


class PeekBrowser(unittest.TestCase):
    setUpClass = tp.Browser.__dict__["setUpClass"]
    tearDownClass = tp.Browser.__dict__["tearDownClass"]
    load_page = tp.Browser.load_page
    ids_on_page = tp.Browser.ids_on_page

    def test_every_kind_of_peek_sits_below_the_banner_to_the_bottom(self):
        for width in (1400, 900):
            with chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                ids = self.ids_on_page(cdp, sid)
                kinds = {}
                for i in ids:
                    kinds.setdefault(i.split("-")[1], i)
                self.assertGreaterEqual(len(kinds), 2, "the demo page has more than one kind of item")
                for theme in ("light", "dark"):
                    cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", sid)
                    for kind, item in kinds.items():
                        where = f"{width} {theme} {kind}"
                        with self.subTest(where):
                            cdp.js(f"location.hash = '#work&p={self.code}&item={item}'", sid)
                            self.assertTrue(wait(lambda: cdp.js("(() => { const p = document.querySelector('#peek'); return !!p && p.dataset.peek === " + json.dumps(item) + "; })()", sid)), where)
                            self.assertTrue(wait(lambda: cdp.js("document.querySelector('#peek').getAnimations().length === 0", sid)), where)
                            top, bottom, right, banner, height, win, banner_on_top, radius = cdp.js(GEOM, sid)
                            self.assertEqual(round(top), round(banner), f"{where}: starts on under the banner's bottom edge")
                            self.assertEqual(round(bottom), round(height), f"{where}: runs to the bottom of the screen")
                            self.assertEqual(round(right), round(win), f"{where}: flush to the right edge")
                            self.assertTrue(banner_on_top, f"{where}: the banner stays on top and clickable")
                            self.assertEqual(radius, "0px", where)
                cdp.js("document.documentElement.dataset.theme = 'light'", sid)


if __name__ == "__main__":
    unittest.main()
