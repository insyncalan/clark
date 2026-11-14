"""Item 1180: the peek's chip row. The four tall property cells become one flat row of chips; each chip is a coloured icon, the value
and a small chevron, and opens a popover. The date chip says "overdue 2 days" in red beneath the date; a closed risk's rating chip says
"<colour> kept". The published file and the Dashboard in View draw the same chips with no control.

Run: python3 dev/run_tests.py test_peek_chips_1180

Measured in a real browser at 1400 and 900 px with the demo data (fictional). Fixed date 28-10-2026. The chips are `.pk-chips > [data-row]`
(status, priority, owner, due); the second line of a chip is `.pk-chip-sub`; the chevron is the `chevdown` icon.
"""
import json
import unittest
from unittest import mock

from _paths import ROOT

import test_peek as tp  # noqa: E402
from test_peek_card import CardBrowser  # noqa: E402
from test_server import chrome, wait  # noqa: E402
from test_work_filters import click  # noqa: E402

OVERDUE = "TUL-A-001"     # open action; the test sets its due date two days before the fixed date
CLOSED_RISK = "TUL-008"   # closed risk in the demo data

READ = """(() => { const p = document.querySelector('#peek'); if (!p) return null;
  const box = (e) => { const r = e.getBoundingClientRect(); return { l: r.left, t: r.top, r: r.right, b: r.bottom, w: r.width, h: r.height }; };
  const row = p.querySelector('.pk-chips');
  const chips = {};
  if (row) for (const c of row.children) { const k = c.dataset.row; if (!k) continue; const cs = getComputedStyle(c);
    const sub = c.querySelector('.pk-chip-sub');
    chips[k] = { ...box(c), tag: c.tagName, text: c.innerText.replace(/\\s+/g, ' ').trim(), aria: c.getAttribute('aria-label') || '',
      icons: [...c.querySelectorAll('svg[data-icn]')].map(s => s.dataset.icn), iconBox: c.querySelector('svg[data-icn]') ? box(c.querySelector('svg[data-icn]')) : null,
      sub: sub ? sub.textContent.trim() : null, subColour: sub ? getComputedStyle(sub).color : null,
      expanded: c.getAttribute('aria-expanded'), haspopup: c.getAttribute('aria-haspopup'),
      border: cs.borderTopWidth, radius: cs.borderTopLeftRadius, overflow: c.scrollWidth - c.clientWidth }; }
  const probe = (name) => { const e = document.createElement('i'); e.style.color = 'var(' + name + ')'; document.body.appendChild(e); const c = getComputedStyle(e).color; e.remove(); return c; };
  return { id: p.dataset.peek, hasRow: !!row, chips, rowBox: row ? box(row) : null, peek: box(p), oldCells: p.querySelectorAll('.pk-fields > .pk-row[data-row]').length,
    red: probe('--red-600'), sideways: p.scrollWidth - p.clientWidth, doc: document.documentElement.scrollWidth - document.documentElement.clientWidth }; })()"""


class Chips(unittest.TestCase):
    setUpClass = tp.Browser.__dict__["setUpClass"]
    tearDownClass = tp.Browser.__dict__["tearDownClass"]
    load_page = tp.Browser.load_page
    edit_mode = tp.Browser.edit_mode
    ids_on_page = tp.Browser.ids_on_page
    show_item = CardBrowser.show_item

    def open_item(self, cdp, sid, item):
        cdp.js(f"location.hash = '#work&p={self.code}&item={item}'", sid)
        self.assertTrue(wait(lambda: cdp.js("(() => { const p = document.querySelector('#peek'); return !!p && p.dataset.peek === " + json.dumps(item) + " && !!p.querySelector('.pk-chips [data-row=status]'); })()", sid)), item)
        self.assertTrue(wait(lambda: cdp.js("document.querySelector('#peek').getAnimations().length === 0", sid)), "the slide-in has ended")
        return cdp.js(READ, sid)

    def with_overdue(self):
        real = self.store.data_for

        def data_for(code, *a, **k):
            d = real(code, *a, **k)
            return dict(d, actions=[dict(r, due_date="2026-10-26") if r["id"] == OVERDUE else r for r in d["actions"]])
        return mock.patch.object(self.store, "data_for", data_for)

    def test_one_flat_row_of_chips_replaces_the_four_cells_in_view_and_edit(self):
        for width in (1400, 900):
            with chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                item = self.ids_on_page(cdp, sid)[0]
                for mode in ("view", "edit"):
                    if mode == "edit":
                        self.edit_mode(cdp, sid)
                    where = f"{width} {mode}"
                    with self.subTest(where):
                        got = self.open_item(cdp, sid, item)
                        self.assertTrue(got["hasRow"], f"{where}: a .pk-chips row")
                        self.assertEqual(got["oldCells"], 0, f"{where}: the four tall cells are gone")
                        self.assertEqual(list(got["chips"]), ["status", "priority", "owner", "due"] if "priority" in got["chips"] else ["status", "owner", "due"], where)
                        tops = {round(c["t"]) for c in got["chips"].values()}
                        self.assertLessEqual(len(tops), 2, f"{where}: one flat row (it may wrap once at 900)")
                        for k, c in got["chips"].items():
                            self.assertGreaterEqual(c["l"], got["peek"]["l"], f"{where} {k}")
                            self.assertLessEqual(c["r"], got["peek"]["r"] + 0.5, f"{where} {k}")
                            self.assertLessEqual(c["overflow"], 1, f"{where} {k}: nothing cut off")
                            self.assertLessEqual(c["h"], 64, f"{where} {k}: a chip, not a tall cell ({c['h']})")
                            self.assertGreaterEqual(c["h"], 24, f"{where} {k}: a 24 px target")
                        self.assertLessEqual(got["sideways"], 1, where)
                        self.assertLessEqual(got["doc"], 1, where)

    def test_each_chip_is_icon_then_value_then_a_chevron_and_never_colour_alone(self):
        want = {"status": "half", "priority": "bars", "owner": "user", "due": "cal"}
        for width in (1400, 900):
            with chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                item = self.ids_on_page(cdp, sid)[0]
                self.edit_mode(cdp, sid)
                got = self.open_item(cdp, sid, item)
                for k, c in got["chips"].items():
                    with self.subTest(f"{width} {k}"):
                        self.assertEqual(c["icons"][0], want[k], "the field's own icon first")
                        self.assertEqual(c["icons"][-1], "chevdown", "the small chevron last")
                        self.assertTrue(c["text"].strip(), "the words sit beside the icon")
                        self.assertLess(c["iconBox"]["l"], c["r"] - 20, "icon at the start")
                        self.assertEqual(c["tag"], "BUTTON", "a control in Edit")
                        self.assertIn(item, c["aria"], "the control names the item")
                        self.assertEqual(c["haspopup"] is not None, True, "it says it opens a popover")

    def test_a_chip_opens_its_popover_and_esc_closes_it_with_focus_back_on_the_chip(self):
        for width in (1400, 900):
            with chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                item = self.ids_on_page(cdp, sid)[0]
                self.edit_mode(cdp, sid)
                self.open_item(cdp, sid, item)
                for k in ("status", "priority", "owner", "due"):
                    with self.subTest(f"{width} {k}"):
                        sel = f"#peek .pk-chips [data-row={k}]"
                        click(cdp, sid, sel)
                        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pop]')", sid)), f"{k}: a popover opens")
                        self.assertEqual(cdp.js(f"document.querySelector({json.dumps(sel)}).getAttribute('aria-expanded')", sid), "true")
                        inside = cdp.js("(() => { const r = document.querySelector('[data-pop]').getBoundingClientRect(); return r.left >= 0 && r.right <= document.documentElement.clientWidth && r.top >= 0 && r.bottom <= innerHeight; })()", sid)
                        self.assertTrue(inside, f"{k}: the popover is on screen")
                        tp.key(cdp, sid, "Escape")
                        self.assertTrue(wait(lambda: cdp.js("!document.querySelector('[data-pop]')", sid)), f"{k}: Esc closes it")
                        self.assertTrue(cdp.js("!!document.querySelector('#peek')", sid), f"{k}: the first Esc leaves the peek open")
                        self.assertTrue(wait(lambda: cdp.js(f"document.activeElement === document.querySelector({json.dumps(sel)})", sid)), f"{k}: focus returns to the chip")

    def test_picking_a_priority_from_the_chip_changes_it_with_a_toast_and_one_undo(self):
        with chrome() as cdp:
            s, sid = self.load_page(cdp, 1400)
            item = self.ids_on_page(cdp, sid)[0]
            self.edit_mode(cdp, sid)
            before = self.open_item(cdp, sid, item)["chips"]["priority"]["text"]
            click(cdp, sid, "#peek .pk-chips [data-row=priority]")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pop] [role=menuitemradio]')", sid)))
            other = cdp.js("(() => { const b = [...document.querySelectorAll('[data-pop] [role=menuitemradio]')].find(x => x.getAttribute('aria-checked') !== 'true'); b.dataset.t = '1'; return b.textContent.trim(); })()", sid)
            click(cdp, sid, "[data-pop] [data-t='1']")
            self.assertTrue(wait(lambda: other in cdp.js("document.querySelector('#peek .pk-chips [data-row=priority]').innerText", sid)), "the chip shows the new value")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.toast [data-undo], .toast button')", sid)), "a toast with Undo")
            self.assertNotIn(other, before)

    def test_an_overdue_date_chip_says_overdue_2_days_in_red_under_the_date(self):
        for width in (1400, 900):
            with self.with_overdue(), chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                for mode in ("view", "edit"):
                    if mode == "edit":
                        self.edit_mode(cdp, sid)
                    with self.subTest(f"{width} {mode}"):
                        got = self.open_item(cdp, sid, OVERDUE)
                        due = got["chips"]["due"]
                        self.assertEqual(due["sub"], "overdue 2 days")
                        self.assertEqual(due["subColour"], got["red"], "the sub-line is in the red token")
                        self.assertIn("26-10-2026", due["text"], "the date stays on the chip")
                        self.assertEqual(due["icons"][0], "cal")
                        self.assertLessEqual(due["h"], 64)
                        self.assertGreaterEqual(due["h"], 24)

    def test_a_chip_with_nothing_to_add_has_no_sub_line(self):
        with chrome() as cdp:
            s, sid = self.load_page(cdp, 1400)
            got = self.open_item(cdp, sid, self.ids_on_page(cdp, sid)[0])
            self.assertIsNone(got["chips"]["owner"]["sub"])
            self.assertIsNone(got["chips"]["status"]["sub"])
            self.assertIsNone(got["chips"]["due"]["sub"], "not overdue: no sub-line")

    def test_a_closed_risk_says_its_rating_was_kept_on_the_chip(self):
        for width in (1400, 900):
            with chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                for mode in ("view", "edit"):
                    if mode == "edit":
                        self.edit_mode(cdp, sid)
                    with self.subTest(f"{width} {mode}"):
                        got = self.open_item(cdp, sid, CLOSED_RISK)
                        chips = got["chips"]
                        self.assertIn("Closed", chips["status"]["text"])
                        kept = [c["sub"] for c in chips.values() if c["sub"] and "kept" in c["sub"]]
                        self.assertEqual(len(kept), 1, "one chip carries the sub-line")
                        self.assertRegex(kept[0], r"^(Red|Amber|Green|Not rated) kept$")
                        self.assertNotIn(" · ", chips["status"]["text"], "the old dotted form is gone")

    def test_an_open_risk_has_no_kept_line(self):
        with chrome() as cdp:
            s, sid = self.load_page(cdp, 1400)
            got = self.open_item(cdp, sid, "TUL-007")
            self.assertFalse([c for c in got["chips"].values() if c["sub"] and "kept" in c["sub"]])

    def test_a_decision_has_no_priority_chip_and_a_risk_keeps_its_rating_picker(self):
        with chrome() as cdp:
            s, sid = self.load_page(cdp, 1400)
            self.edit_mode(cdp, sid)
            dec = self.open_item(cdp, sid, self.decision())
            self.assertEqual(list(dec["chips"]), ["status", "owner", "due"])
            self.open_item(cdp, sid, "TUL-007")
            click(cdp, sid, "#peek .pk-chips [data-row=priority]")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pop].rpick')", sid)), "a risk's priority opens the impact and likelihood picker")

    def decision(self):
        return next(r["id"] for r in self.data["decisions"])

    def test_view_draws_the_same_chips_as_plain_text_with_no_control_and_no_popover(self):
        for width in (1400, 900):
            with chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                item = self.ids_on_page(cdp, sid)[0]
                view = self.open_item(cdp, sid, item)
                self.edit_mode(cdp, sid)
                edit = self.open_item(cdp, sid, item)
                with self.subTest(width):
                    self.assertEqual(list(view["chips"]), list(edit["chips"]), "the same chips")
                    for k, c in view["chips"].items():
                        self.assertNotEqual(c["tag"], "BUTTON", f"{k}: read only in View")
                        self.assertIsNone(c["haspopup"], f"{k}: no popover in View")
                        self.assertEqual(c["icons"][0], edit["chips"][k]["icons"][0], f"{k}: same icon")
                        self.assertEqual(c["text"].replace(" ", ""), edit["chips"][k]["text"].replace(" ", ""), f"{k}: same words")


class ChipRules(unittest.TestCase):
    def test_the_chip_row_is_in_the_page_stylesheet_in_tokens_only(self):
        import re
        css = (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
        self.assertIn(".pk-chips", css, "the row is the published page's too")
        self.assertIn(".pk-chip-sub", css)
        for sel in re.findall(r"\.pk-chips[^{]*\{([^}]*)\}", css):
            self.assertNotRegex(sel, r"#[0-9A-Fa-f]{3,8}\b|rgba?\(|hsla?\(", "tokens only")
            self.assertNotRegex(sel, r"font-size:\s*\d", "sizes come from the scale")

    def test_the_peek_source_draws_the_row_for_all_kinds(self):
        src = (ROOT / "src" / "clark" / "page" / "src" / "components" / "Peek.jsx").read_text(encoding="utf-8")
        self.assertIn("pk-chips", src)
        self.assertIn("pk-chip-sub", src)


if __name__ == "__main__":
    unittest.main()
