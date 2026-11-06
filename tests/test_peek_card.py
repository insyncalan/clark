"""Row 766: the peek's card. Status, Priority, Owner and Due are four cells above the other fields (the prototype's property row).

Run: python3 dev/run_tests.py test_peek_card

The page is measured in a real browser at 1400 and 900 px, light and dark, in View and in Edit: the cells sit in a card order
(Status, Priority, Owner, Due) above Type and the other rows, two by two in the usual width and four across when the panel is
widened, each with a visible edge in the theme's own grey, none cut off or pushing the panel sideways. A decision has no Priority
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
  const probe = (name) => { const e = document.createElement('i'); e.style.cssText = 'border:1px solid var(' + name + ')'; document.body.appendChild(e); const c = getComputedStyle(e).borderTopColor; e.remove(); return c; };
  const cells = {};
  for (const k of ['status', 'priority', 'owner', 'due']) {
    const el = peek.querySelector('.pk-fields > [data-row=' + k + ']'); if (!el) continue;
    const dd = el.querySelector('dd'), cs = getComputedStyle(el);
    cells[k] = { ...box(el), border: cs.borderTopWidth, borderColor: cs.borderTopColor, radius: cs.borderTopLeftRadius, label: el.querySelector('dt').textContent,
      overflow: dd.scrollWidth - dd.clientWidth };
  }
  const type = [...peek.querySelectorAll('.pk-fields > .pk-row')].find((r) => r.querySelector('dt').textContent === 'Type');
  const labels = [...peek.querySelectorAll('.pk-fields > .pk-row dt')].map((d) => d.textContent);
  return { id: peek.dataset.peek, cells, type: type ? box(type) : null, labels, peek: box(peek), edge: probe('--grey-200'),
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
        self.assertTrue(wait(lambda: cdp.js("(() => { const p = document.querySelector('#peek'); return !!p && p.dataset.peek === " + json.dumps(item) + " && !!p.querySelector('.pk-fields [data-row=status]'); })()", sid)), item)
        self.assertTrue(wait(lambda: cdp.js("document.querySelector('#peek').getAnimations().length === 0", sid)), "the slide-in has ended")
        return cdp.js(READ, sid)

    def decision(self):
        return next(r["id"] for r in self.data["decisions"])

    def check(self, got, where, across):
        cells = got["cells"]
        self.assertEqual(list(cells), ["status", "priority", "owner", "due"] if "priority" in cells else ["status", "owner", "due"], where)
        for k, c in cells.items():
            self.assertEqual(c["border"], "1px", f"{where} {k}: a visible edge")
            self.assertEqual(c["borderColor"], got["edge"], f"{where} {k}: the edge is the theme's own grey")
            self.assertGreater(float(c["radius"].replace("px", "")), 0, f"{where} {k}: rounded like the other cards")
            self.assertLessEqual(c["overflow"], 1, f"{where} {k}: nothing cut off")
            self.assertGreaterEqual(c["w"], 100, f"{where} {k}: wide enough to read")
            self.assertGreaterEqual(c["l"], got["peek"]["l"], where)
            self.assertLessEqual(c["r"], got["peek"]["r"] + 0.5, where)
        self.assertLessEqual(got["sideways"], 1, f"{where}: the panel does not scroll sideways")
        self.assertLessEqual(got["doc"], 1, f"{where}: the page does not scroll sideways")
        order = list(cells.values())
        if across:
            self.assertEqual({round(c["t"]) for c in order}, {round(order[0]["t"])}, f"{where}: one line of cells")
            self.assertEqual([c["l"] for c in order], sorted(c["l"] for c in order), f"{where}: left to right in order")
        else:
            self.assertEqual(round(order[0]["t"]), round(order[1]["t"]), f"{where}: the first two share a line")
            self.assertGreater(order[2]["t"], order[0]["b"] - 1, f"{where}: the next cells sit below")
            self.assertEqual(round(order[0]["l"]), round(order[2]["l"]), f"{where}: two columns")
            self.assertEqual(round(order[0]["w"]), round(order[1]["w"]), f"{where}: equal cells")
        self.assertIsNotNone(got["type"], where)
        self.assertGreaterEqual(got["type"]["t"], max(c["b"] for c in order) - 1, f"{where}: Type and the rest sit below the card")
        known = {"Type", "Owner", "Decision by", "Due", "Needed by", "Date", "Priority", "Status", "Workstream", "Milestone", "Use case", "Shown to client", "Raised", "Last reviewed"}
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
                                self.check(got, where, across=False)
                                if it == item:
                                    click(cdp, sid, "[data-pk-wide]")
                                    self.assertTrue(wait(lambda: cdp.js("document.querySelector('#peek').classList.contains('wide')", sid)))
                                    self.assertTrue(wait(lambda: cdp.js("document.querySelector('#peek').getBoundingClientRect().width", sid) >= cdp.js("document.documentElement.clientWidth", sid) - 1))
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
        self.assertIn("@container (min-width: 560px)", block)
        self.assertNotRegex(block, r"#[0-9A-Fa-f]{3,8}\b|rgba?\(|hsla?\(", "tokens only")
        self.assertNotRegex(block, r"font-size:\s*\d", "sizes come from the scale")


if __name__ == "__main__":
    unittest.main()
