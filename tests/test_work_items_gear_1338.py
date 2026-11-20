"""Row 1338: in Work items Edit the gear is 32 px (it was 36) and the Changed tag stands left of it, not under it.

Run: python3 dev/run_tests.py test_work_items_gear_1338
The change is in the Classic theme layer only (src/clark/themes/prototype-2.0/rules.css); the Cards gear stays 36 px and the Cards page is
proved unchanged by test_work_items_mockup_1195 (style md5 and rendered DOM).
Not checked here: the Owner cell (see the report), dark mode.
"""
import json
import re

import test_server  # noqa: F401  this file drives Chrome through the template harness (the browser tier reads this line)

import test_tpl_workitems as T
import test_work_items_mockup_1195 as M

LIST = {"mode": "all", "columns": ["id", "owner", "due", "priority"], "owner": ["Pat Demo", "Lee Demo"]}

MEASURE = ("JSON.stringify((() => { const s = %s, r = (q) => { const b = document.querySelector(s + ' ' + q).getBoundingClientRect(); return {l: b.left, r: b.right, t: b.top, b: b.bottom, w: b.width, h: b.height}; };"
           "return {gear: r('[data-wil-gear]'), gearcss: (g => ({bw: g.borderTopWidth, bg: g.backgroundColor, br: g.borderRadius}))(getComputedStyle(document.querySelector(s + ' [data-wil-gear]'))), tag: (document.querySelector(s + ' .sec-head .tag.chg') ? r('.sec-head .tag.chg') : null), head: r('.sec-head'), title: r('.sec-h')}; })())")


class Rule(M.unittest.TestCase):
    def test_the_classic_rules_set_the_gear_to_32_and_free_the_right_end_of_the_title_row(self):
        css = re.sub(r"\s+", " ", M.RULES)
        self.assertIn(".wil-gear { min-width: var(--space-6); min-height: var(--space-6); }", css)
        self.assertIn(".sec:has(.wil-cw) > .sec-head { padding-right: calc(var(--space-6) + var(--space-2) + 2px); }", css)

    def test_the_gear_is_round_borderless_transparent_and_muted(self):
        css = re.sub(r"\s+", " ", M.RULES)
        for part in (".wil-gear { border: 0; background: transparent; color: var(--text-muted); }",
                     ".wil-gear:hover, .wil-gear[aria-expanded=true] { background: var(--grey-100); color: var(--text); }"):
            self.assertIn(part, css)

    def test_the_owner_name_is_one_line_with_an_ellipsis(self):
        css = re.sub(r"\s+", " ", M.RULES)
        self.assertIn(".wil-table .wil-own .nm { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }", css)
        self.assertNotIn("overflow-wrap: anywhere; }", css.split(".wil-own .nm")[1].split("}")[0] + "}")

    def test_the_cards_files_do_not_carry_it(self):
        self.assertNotIn("Row 1338", M.SHELL_CSS + M.EDIT_CSS)
        self.assertIn("min-width: calc(var(--space-6) + var(--space-1))", M.EDIT_CSS)


class Measured(M.Look):
    """The served Edit page with a changed Work items section, at 1400 and 900."""

    def look(self, width):
        ref = self.add(LIST)
        with T.chrome() as cdp:
            p = self.show(cdp, width)
            sec = f'[data-id="{ref}"]'
            p.edit()
            p.until(f"!!document.querySelector('{sec} [data-wil-gear]')", "drew")
            p.js("window.clarkPage.markChanged(['" + ref + "'])")
            p.until(f"!!document.querySelector('{sec}.sec-sweep, {sec}.is-changed')", "the changed sign")
            return json.loads(p.js(MEASURE % json.dumps(sec)))

    def owner(self, width):
        self.demo.action(description="Long name step", owner="Cressida Pennywhistle-Featherstonehaugh", due_date="2030-01-10", priority="High")
        ref = self.add({"mode": "all", "columns": ["id", "owner", "due", "priority"], "owner": ["Cressida Pennywhistle-Featherstonehaugh"]})
        with T.chrome() as cdp:
            p = self.show(cdp, width)
            sec = f'[data-id="{ref}"]'
            p.until(f"!!document.querySelector('{sec} .wil-table .wil-own .nm')", "drew")
            return json.loads(p.js("JSON.stringify((() => { const n = document.querySelector('%s .wil-table .wil-own .nm'), c = getComputedStyle(n);"
                                   "return {colw: Math.round(n.closest('td').getBoundingClientRect().width), white: c.whiteSpace, ell: c.textOverflow, nmh: n.getBoundingClientRect().height, sw: n.scrollWidth, cw: n.clientWidth}; })())" % sec))

    def test_classic_gear_is_32_and_the_changed_tag_is_left_of_it_at_1400_and_900(self):
        for width in (1400, 900):
            got = self.look(width)
            self.assertEqual((got["gear"]["w"], got["gear"]["h"]), (32, 32), (width, got))
            if self.classic:
                self.assertIsNone(got["tag"], (width, got))      # row 1408: Classic shows a line under the title, no Changed tag
            else:
                self.assertEqual(got["gear"]["l"] - got["tag"]["r"], 10, (width, got))      # the mock-up gap 10
            self.assertEqual(got["head"]["r"] - got["gear"]["r"], 0, (width, got))
            self.assertLessEqual(got["gear"]["r"], got["head"]["r"], (width, got))
            self.assertLess(got["title"]["r"], got["gear"]["l"], (width, got))
            self.assertEqual(got["gearcss"], {"bw": "0px", "bg": "rgba(0, 0, 0, 0)", "br": "50%"}, (width, got))

    def test_a_long_owner_name_stays_on_one_line_with_an_ellipsis_in_the_170_column_at_1400_and_900(self):
        for width in (1400, 900):
            got = self.owner(width)
            self.assertEqual(got["colw"], 170, (width, got))
            self.assertEqual(got["white"], "nowrap", (width, got))
            self.assertEqual(got["ell"], "ellipsis", (width, got))
            self.assertLess(got["nmh"], 30, (width, got))
            self.assertGreater(got["sw"], got["cw"], (width, got))      # the name is longer than its box, so it is cut by the ellipsis


class CardsMeasured(Measured):
    classic = False

    def test_classic_gear_is_32_and_the_changed_tag_is_left_of_it_at_1400_and_900(self):
        self.skipTest("Classic only")

    def test_a_long_owner_name_stays_on_one_line_with_an_ellipsis_in_the_170_column_at_1400_and_900(self):
        self.skipTest("Cards is unmaintained (ruling 19-11)")

    def test_cards_gear_stays_36(self):
        for width in (1400, 900):
            got = self.look(width)
            self.assertEqual((got["gear"]["w"], got["gear"]["h"]), (36, 36), (width, got))
