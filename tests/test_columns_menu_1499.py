"""Row 1499: the Work items Columns menu as the approved mock-up (pick 7B), Classic only, measured in Chrome at 1400 and 900.

Run: python3 dev/run_tests.py test_columns_menu_1499
Asserts on the real Work items page: the heading 'Columns to show' (its text, size 12px, weight 600, muted colour, margin 4px 10px 6px), one tick line for
each column in the table's order (role menuitemcheckbox, aria-checked), no locked line (no aria-disabled, no data-keep) and no standard reset, the Item
not listed, the Status an ordinary line that can be turned off, a click that toggles and leaves the menu open with the focus on that line, and the panel
values (minimum width 200, radius 12, padding 6, the shadow). The Cards class keeps its old menu (locked Status, the standard line)."""
import json

import test_server  # noqa: F401  this file drives Chrome through the template harness (the browser tier reads this line)

import test_tpl_workitems as T
import test_work_items_mockup_1195 as M

OPEN = ("(() => { const b = document.querySelector('#work button.cols-btn'); b.click(); return !!b; })()")
LINES = ("JSON.stringify([...document.querySelectorAll('.cols-menu [role=menuitemcheckbox]')].map((b) => [b.dataset.colName, b.getAttribute('aria-checked'), b.getAttribute('aria-disabled'), b.hasAttribute('data-keep')]))")
PANEL = ("JSON.stringify((() => { const m = document.querySelector('.cols-menu'), c = getComputedStyle(m), h = m.querySelector('h5'), hc = h ? getComputedStyle(h) : null,"
         "line = m.querySelector('[role=menuitemcheckbox]'), lc = getComputedStyle(line), tk = getComputedStyle(line.querySelector('.tk')),"
         "tok = (v, p) => { const i = document.createElement('i'); i.style[p] = v; document.body.appendChild(i); const r = getComputedStyle(i)[p]; i.remove(); return r; };"
         "return { label: m.getAttribute('aria-label'), head: h && h.textContent, headSize: hc && hc.fontSize, headWeight: hc && hc.fontWeight, headMargin: hc && hc.margin, headColor: hc && hc.color, muted: tok('var(--text-muted)', 'color'),"
         "minW: c.minWidth, radius: c.borderTopLeftRadius, pad: c.padding, shadow: c.boxShadow, border: c.borderTopWidth + ' ' + c.borderTopColor, line: tok('var(--grey-200)', 'color'),"
         "lineGap: lc.columnGap, lineH: lc.minHeight, linePad: lc.padding, lineRadius: lc.borderTopLeftRadius, lineWeight: lc.fontWeight, tickW: tk.width, tickColor: tk.color, blue: tok('var(--brand-blue)', 'color'), tickWeight: tk.fontWeight,"
         "standard: !!m.querySelector('[data-cols-standard], [role=separator]') }; })())")


class Menu(M.Look):
    def opened(self, cdp, width):
        p = self.show(cdp, width)
        p.js("location.hash = '#work&p=ABC&f=mode:all'")
        p.until("!!document.querySelector('#work button.cols-btn')", "the Columns button drew")
        p.js(OPEN)
        p.until("!!document.querySelector('.cols-menu')", "the menu opened")
        return p

    def test_classic_menu_is_the_mock_up_menu(self):
        for width in (1400, 900):
            with T.chrome() as cdp:
                p = self.opened(cdp, width)
                lines = json.loads(p.js(LINES))
                names = [n for n, *_ in lines]
                self.assertEqual(names[:5], ["Status", "Owner", "Due", "Priority", "Id"], width)
                self.assertNotIn("Item", names, "the Item is always shown and is not a line")
                self.assertEqual(len(names), 14, width)
                for n, checked, disabled, keep in lines:
                    self.assertIn(checked, ("true", "false"), (width, n))
                    self.assertIsNone(disabled, (width, n))
                    self.assertFalse(keep, (width, n))
                self.assertEqual([c for n, c, *_ in lines if n in ("Status", "Owner", "Due", "Priority", "Id")], ["true"] * 5, width)
                got = json.loads(p.js(PANEL))
                self.assertEqual((got["label"], got["head"]), ("Columns to show", "Columns to show"), width)
                self.assertEqual((got["headSize"], got["headWeight"], got["headMargin"], got["headColor"]), ("12px", "600", "4px 10px 6px", got["muted"]), (width, got))
                self.assertEqual((got["minW"], got["radius"], got["pad"]), ("200px", "12px", "6px"), (width, got))
                self.assertIn("0px 10px 30px 0px", got["shadow"], (width, got))
                self.assertEqual(got["border"], "1px " + got["line"], (width, got))
                self.assertEqual((got["lineGap"], got["lineH"], got["linePad"], got["lineRadius"], got["lineWeight"], got["tickW"]), ("10px", "38px", "0px 10px", "8px", "500", "16px"), (width, got))
                self.assertEqual((got["tickColor"], got["tickWeight"]), (got["blue"], "700"), (width, got))
                self.assertFalse(got["standard"], "no standard reset and no separator")
                self.assertEqual(p.js("document.activeElement.dataset.colName"), "Status", "the first line takes the focus on open")

    def test_a_click_toggles_the_status_and_keeps_the_menu_open_with_the_focus_on_that_line(self):
        for width in (1400, 900):
            with T.chrome() as cdp:
                p = self.opened(cdp, width)
                p.js("document.querySelector('.cols-menu [data-col-name=Status]').click()")
                p.until("!document.querySelector('#work th[data-col=status]')", "the Status column went")
                self.assertTrue(p.js("!!document.querySelector('.cols-menu')"), "the menu stays open")
                self.assertEqual(p.js("document.activeElement.dataset.colName"), "Status")
                self.assertEqual(p.js("document.querySelector('.cols-menu [data-col-name=Status]').getAttribute('aria-checked')"), "false")
                self.assertFalse(p.js("!!document.querySelector('#work td.c-status')"), "no Status cell is left")
                self.assertTrue(p.js("!!document.querySelector('#work th[data-col=item]')"), "the Item stays")
                p.js("document.querySelector('.cols-menu [data-col-name=Status]').click()")
                p.until("!!document.querySelector('#work th[data-col=status]')", "the Status column is back")


class CardsMenu(Menu):
    classic = False

    def test_classic_menu_is_the_mock_up_menu(self):
        with T.chrome() as cdp:
            p = self.opened(cdp, 1400)
            lines = json.loads(p.js(LINES))
            self.assertEqual(lines[0][:3], ["Status", "true", "true"], "Cards keeps the locked Status line")
            self.assertTrue(p.js("!!document.querySelector('.cols-menu [data-cols-standard]')"), "Cards keeps the standard line")
            self.assertFalse(p.js("!!document.querySelector('.cols-menu h5')"))

    def test_a_click_toggles_the_status_and_keeps_the_menu_open_with_the_focus_on_that_line(self):
        self.skipTest("Classic only")


if __name__ == "__main__":
    M.unittest.main()
