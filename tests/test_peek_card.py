"""Row 766 (re-pointed by row 1180: the four cells are the chip row now, so the card is checked as chips): the peek's property row. Status, Priority, Owner and Due are four cells above the other fields (the prototype's property row);
row 1077 (the owner's ruling of 10-11-2026) makes them FLAT: no tile edge, no rounding, no fill, one hairline under the row (the first
ordinary row's top edge), in the editor and in a published file alike (shell.css is the published page's).

Run: python3 dev/run_tests.py test_peek_card

The page is measured in a real browser at 1400 and 900 px, light and dark, in View and in Edit: the cells sit in a row order
(Status, Priority, Owner, Due) above Type and the other rows, two by two in the usual width and four across when the panel is
widened, none boxed, none cut off or pushing the panel sideways. A decision has no Priority
cell and keeps the other three. The look needs no new words: the rows are the same ones, so the labels are checked unchanged.
"""
import json
import re
import unittest

from _paths import ROOT

import test_peek as tp  # noqa: E402
from test_server import chrome, wait  # noqa: E402
from test_work_filters import click, dblclick  # noqa: E402

SHELL = ROOT / "src" / "clark" / "page" / "shell.css"

READ = """(() => {
  const peek = document.querySelector('#peek'); if (!peek) return null;
  const box = (el) => { const r = el.getBoundingClientRect(); return { l: r.left, t: r.top, r: r.right, b: r.bottom, w: r.width, h: r.height }; };
  const cells = {};
  for (const k of ['status', 'priority', 'owner', 'due']) {
    const el = peek.querySelector('.pk-chips > [data-row=' + k + ']'); if (!el) continue;
    const cs = getComputedStyle(el);
    cells[k] = { ...box(el), shadow: cs.boxShadow, overflow: el.scrollWidth - el.clientWidth };
  }
  const labels = [...peek.querySelectorAll('.pk-fields > .pk-row dt')].map((d) => d.textContent);
  return { id: peek.dataset.peek, cells, labels, peek: box(peek),
    sideways: peek.scrollWidth - peek.clientWidth, doc: document.documentElement.scrollWidth - document.documentElement.clientWidth };
})()"""


class CardBrowser(unittest.TestCase):
    setUpClass = tp.Browser.__dict__["setUpClass"]
    tearDownClass = tp.Browser.__dict__["tearDownClass"]
    load_page = tp.Browser.load_page
    edit_mode = tp.Browser.edit_mode
    ids_on_page = tp.Browser.ids_on_page

    def show_item(self, cdp, sid, item):
        cdp.js(f"location.hash = '#work&p={self.code}&item={item}'", sid)
        self.assertTrue(wait(lambda: cdp.js("(() => { const p = document.querySelector('#peek'); return !!p && p.dataset.peek === " + json.dumps(item) + " && !!p.querySelector('.pk-chips [data-row=status]'); })()", sid)), item)
        self.assertTrue(wait(lambda: cdp.js("document.querySelector('#peek').getAnimations().length === 0", sid)), "the slide-in has ended")
        return cdp.js(READ, sid)

    def decision(self):
        return next(r["id"] for r in self.data["decisions"])

    def check(self, got, where, across):
        cells = got["cells"]
        self.assertEqual(list(cells), ["status", "priority", "owner", "due"] if "priority" in cells else ["status", "owner", "due"], where)
        for k, c in cells.items():
            self.assertEqual(c["shadow"], "none", f"{where} {k}: no shadow")
            self.assertLessEqual(c["overflow"], 1, f"{where} {k}: nothing cut off")
            self.assertGreaterEqual(c["l"], got["peek"]["l"], where)
            self.assertLessEqual(c["r"], got["peek"]["r"] + 0.5, where)
        self.assertLessEqual(got["sideways"], 1, f"{where}: the panel does not scroll sideways")
        self.assertLessEqual(got["doc"], 1, f"{where}: the page does not scroll sideways")
        known = {"Type", "Owner", "Made by", "Decision by", "Made on", "Reasoning", "Options considered", "Revisit", "Replaces", "Visible to client", "Due", "Needed by", "Date", "Priority", "Status", "Workstream", "Milestone", "Use case", "Shown to client", "Client wording", "Raised", "Last reviewed", "Description", "Client visible", "Rating"}
        self.assertLessEqual(set(got["labels"]), known, f"{where}: the same labels as before (no new words)")

    def test_the_card_in_view_and_edit_light_and_dark_at_both_widths(self):
        for width in (1400, 900):
            with chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                ids = self.ids_on_page(cdp, sid)
                item, dec = ids[0], self.decision()
                for mode in ("view", "edit"):
                    if mode == "edit":
                        self.edit_mode(cdp, sid)
                    for theme in ("light", "dark"):
                        cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", sid)
                        for it in (item, dec):
                            where = f"{width} {mode} {theme} {it}"
                            with self.subTest(where):
                                got = self.show_item(cdp, sid, it)
                                self.check(got, where, across=width < 1000)
                                if it == item:
                                    click(cdp, sid, "[data-pk-wide]")
                                    self.assertTrue(wait(lambda: cdp.js("document.querySelector('#peek').classList.contains('wide')", sid)))
                                    self.assertTrue(wait(lambda: cdp.js("document.querySelector('#peek').getBoundingClientRect().width", sid) >= cdp.js("document.documentElement.clientWidth", sid) - 1))      # row 1289: flush, full width
                                    self.check(cdp.js(READ, sid), where + " wide", across=True)
                                    click(cdp, sid, "[data-pk-wide]")
                                    self.assertTrue(wait(lambda: not cdp.js("document.querySelector('#peek').classList.contains('wide')", sid)))
                cdp.js("document.documentElement.dataset.theme = 'light'", sid)


class CardRule(unittest.TestCase):
    def test_the_card_rules_are_in_the_stylesheet_in_tokens_only(self):
        css = SHELL.read_text(encoding="utf-8")
        start = css.index("/* The peek's card (row 766)")
        block = css[start:css.index("\n\n", start)]
        self.assertIn("container-type: inline-size", block)
        self.assertIn("@container (min-width: 600px)", block)
        flat = next(l for l in block.splitlines() if l.startswith(".pk-fields > .pk-row[data-row] {"))
        for boxed in ("border: 1px", "border-radius: var(", "background: var("):
            self.assertNotIn(boxed, flat, "row 1077: the four cells are flat")
        self.assertNotIn(".pk-row[data-row]", (ROOT / "src" / "clark" / "page" / "src" / "edit" / "edit.css").read_text(encoding="utf-8"), "one rule for the cells, the published page's")
        self.assertNotRegex(block, r"#[0-9A-Fa-f]{3,8}\b|rgba?\(|hsla?\(", "tokens only")
        self.assertNotRegex(block, r"font-size:\s*\d", "sizes come from the scale")


if __name__ == "__main__":
    unittest.main()
