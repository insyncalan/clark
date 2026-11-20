"""Row 1353: the Work items PAGE priority pills (.wil-pr in the table) in the Classic theme, measured as computed style at 1400 and 900, light and dark.

Run: python3 dev/run_tests.py test_classic_work_pills_1353
What is asserted, per pill (Low, Medium, High, Urgent):
  colour   the fill and the text are the row 1409 pair, read from the page itself through a probe element that names the --pri-* tokens (no literals here);
  border   1px solid, in the fill colour (rules.css draws the width and style from .wil-pr; the colour comes from the --pri-* pair, not from --wil-pr-bd);
  radius   6px.
Ticket 1353 history: items 3 and 4 of its first table (Urgent red / High amber / rest grey, and the widened --wil-pr-* scope) are superseded by the row 1409 ruling
(Low green, Medium amber, High red, Urgent maroon; Romanoff, Wanda 20-11). Items 5 and 6 (border from the page variables, radius 6 not 999) are accepted: the radius is 6px,
and the border is built as the one-pixel line in the fill colour. The Cards class skips: the pills are a Classic-layer look.
"""
import json

import test_server  # noqa: F401  this file drives Chrome through the template harness (the browser tier reads this line)

import test_tpl_workitems as T
import test_work_items_mockup_1195 as M

LIST = {"mode": "all", "columns": ["id", "owner", "due", "priority"], "max": 40}
TOKENS = {"Low": "low", "Medium": "medium", "High": "high", "Urgent": "urgent"}

MEASURE = ("JSON.stringify((() => { const s = %s, out = {}, pr = document.createElement('span'); document.body.appendChild(pr);"
           "const probe = (lv) => { pr.style.cssText = 'background:var(--pri-' + lv + '-bg);color:var(--pri-' + lv + '-fg)'; const c = getComputedStyle(pr); return {bg: c.backgroundColor, fg: c.color}; };"
           "for (const e of document.querySelectorAll(s + ' .wil-table td .wil-pr')) { const c = getComputedStyle(e);"
           "out[e.textContent] = {bg: c.backgroundColor, fg: c.color, bw: c.borderTopWidth, bs: c.borderTopStyle, bc: c.borderTopColor, rad: c.borderTopLeftRadius, want: probe(%s[e.textContent] || 'low')}; }"
           "pr.remove(); return out; })())")


class Pills(M.Look):
    def setUp(self):
        super().setUp()
        for lv, (im, li) in {"Low": ("Low", "Low"), "Medium": ("Medium", "Low"), "High": ("High", "Medium"), "Urgent": ("High", "High")}.items():
            with self.store.step("dashboard", T.USER) as st:
                st.create("raid", {"project": "ABC", "type": "Risk", "description": f"Pill {lv}", "raised": "2026-10-01", "source": "demo",
                                   "impact": im, "likelihood": li, "owner": "Pat Demo"})

    def look(self, width, dark):
        ref = self.add(LIST)
        with T.chrome() as cdp:
            p = self.show(cdp, width, dark=dark)
            p.edit()
            sel = f'[data-id="{ref}"]'
            p.until(f"document.querySelectorAll('{sel} .wil-table td .wil-pr').length > 3", "the pills drew")
            return json.loads(p.js(MEASURE % (json.dumps(sel), json.dumps(TOKENS))))

    def test_classic_pills_colour_border_and_radius(self):
        for dark in (False, True):
            for width in (1400, 900):
                where = f"{'dark' if dark else 'light'} {width}"
                got = self.look(width, dark)
                self.assertEqual(set(got), set(TOKENS), where)
                for word, g in got.items():
                    with self.subTest(where=where, pill=word):
                        self.assertEqual((g["bg"], g["fg"]), (g["want"]["bg"], g["want"]["fg"]), (where, got))
                        self.assertNotEqual(g["bg"], "rgba(0, 0, 0, 0)", (where, got))
                        self.assertEqual((g["bw"], g["bs"], g["bc"]), ("1px", "solid", g["bg"]), (where, got))
                        self.assertEqual(g["rad"], "6px", (where, got))
                self.assertEqual(len({g["bg"] for g in got.values()}), 4, (where, got))


class CardsPills(Pills):
    classic = False

    def test_classic_pills_colour_border_and_radius(self):
        self.skipTest("Classic only")


if __name__ == "__main__":
    M.unittest.main()
