"""The View | Edit switch (#665): on the Dashboard it is a pill at the left of the report bar and not in the top bar; on every other
tab there is no switch at all (row 804). Chrome is required: these tests fail, never skip, without it.

Run: python3 dev/run_tests.py test_mode_pill
"""
import re
import unittest
from pathlib import Path

from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome

GROUP = "document.querySelector('[aria-label=\"View or Edit\"]')"
COUNT = "document.querySelectorAll('[aria-label=\"View or Edit\"]').length"
MODE = "document.querySelector('#report').dataset.mode"
PLACE = (f"(function(){{var g={GROUP}; return [{COUNT}, !!g.closest('#report-bar'), !!g.closest('header.top')];}})()")


class ModePill(Base):
    def tab(self, p, name, count=1):
        p.js(f"document.querySelector('.tab[data-view=\"{name}\"]').click()")
        p.until(f"document.querySelector('.tab[data-view=\"{name}\"]').getAttribute('aria-selected') === 'true'", f"{name} open")
        p.until(f"{COUNT} === {count}", f"{name}: {count} switch(es)")

    def test_on_the_dashboard_it_is_in_the_report_bar_at_its_left_and_not_in_the_top_bar(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertEqual(p.js(PLACE), [1, True, False])
            got = p.js(f"(function(){{var g={GROUP}.getBoundingClientRect(), b=document.querySelector('#report-bar'), "
                       "first=[...b.children].filter(c => c.getClientRects().length)[0], "
                       "x=document.querySelector('#week-ending').getBoundingClientRect();"
                       f"return [first === {GROUP}, g.left - b.getBoundingClientRect().left < 4, g.right <= x.left];}})()")
            self.assertEqual(got, [True, True, True])

    def test_on_the_other_tabs_there_is_no_switch_at_all(self):      # row 804: View | Edit is the Dashboard's alone
        with chrome() as cdp:
            p = self.visit(cdp)
            for name in ("work", "milestones", "usecases", "settings"):
                self.tab(p, name, 0)
                self.assertEqual(p.js(COUNT), 0, name)
            self.tab(p, "dashboard")
            self.assertEqual(p.js(PLACE), [1, True, False])

    def test_clicking_edit_and_view_switches_the_mode_and_keeps_aria_and_data_mode(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.js(f"{GROUP}.querySelector('[data-mode=\"edit\"]').click()")
            p.until(f"{MODE} === 'edit'", "edit")
            self.assertEqual(p.js(f"[...{GROUP}.querySelectorAll('button')].map(b => b.dataset.mode + b.getAttribute('aria-pressed') + b.textContent)"),
                             ["viewfalseView", "edittrueEdit"])
            p.js(f"{GROUP}.querySelector('[data-mode=\"view\"]').click()")
            p.until(f"{MODE} === 'view'", "view")

    def test_the_chosen_half_is_the_aqua_pill_with_dark_text_in_both_themes_edit_has_a_pencil_and_the_chip_is_13px(self):
        for theme in ("light", "dark"):
            with self.subTest(theme=theme), chrome() as cdp:
                p = self.visit(cdp)
                p.js(f"document.documentElement.dataset.theme = '{theme}'")
                got = p.js(f"(function(){{var b={GROUP}.querySelector('[aria-pressed=\"true\"]'), s=getComputedStyle(b), r=document.querySelector('#report-state');"
                           "var root=getComputedStyle(document.documentElement);"
                           "return [(s.backgroundImage.indexOf('linear-gradient') === 0 || getComputedStyle(" + GROUP + ", '::before').backgroundImage.indexOf('linear-gradient') === 0), s.color === (function(){var e=document.createElement('i'); e.style.color=root.getPropertyValue('--pill-fg'); document.body.appendChild(e); var c=getComputedStyle(e).color; e.remove(); return c;})(), "
                           f"getComputedStyle(r).fontSize, !!{GROUP}.querySelector('[data-mode=\"edit\"] svg[aria-hidden=\"true\"]'), !{GROUP}.querySelector('[data-mode=\"view\"] svg'), "
                           "getComputedStyle(document.querySelector('#week-ending')).borderRadius !== '4px'];})()")
                self.assertEqual(got, [True, True, "13px", True, True, True])

    def test_the_v_and_e_keys_work_on_the_dashboard(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.key("e", code="KeyE", vk=69)
            p.until(f"{MODE} === 'edit'", "E")
            p.key("v", code="KeyV", vk=86)
            p.until(f"{MODE} === 'view'", "V")

    def test_the_v_and_e_listener_is_installed_at_boot_not_by_the_switch(self):
        # The switch moves between the top bar and the report bar; a listener that lived in it was missing before the report bar drew (the
        # first E press on a slow runner was lost). boot.jsx installs it once, from the start.
        page = Path(__file__).resolve().parents[1] / "src/clark/page/src"
        read = lambda name: (page / name).read_text(encoding="utf-8")
        switch = read("edit/Toggle.jsx")
        self.assertIsNone(re.search(r"keydown|keyup|onKey|addEventListener", switch), "the switch adds no key listener of its own")
        self.assertIsNotNone(re.search(r"modeKeys\s*\.\s*install\s*\(", read("boot.jsx")), "boot installs the V and E listener")
        self.assertIsNotNone(re.search(r"modeKeys\s*:\s*\{\s*install\s*:\s*installModeKeys", read("edit/index.js")), "the edit tools expose it")
        self.assertIsNotNone(re.search(r"function\s+installModeKeys[^}]*addEventListener\(\s*[\"']keydown", read("edit/keys.js")), "keys.js adds the listener")

    def test_the_keys_still_work_after_a_round_trip_through_another_tab(self):
        # keys.js acts on the Dashboard only; the switch moves between the top bar and the report bar, and one listener must survive that
        with chrome() as cdp:
            p = self.visit(cdp)
            self.tab(p, "work", 0)
            p.key("e", code="KeyE", vk=69)
            self.assertEqual(p.js(COUNT), 0)      # off the Dashboard E draws nothing
            self.tab(p, "dashboard")
            p.key("e", code="KeyE", vk=69)
            p.until(f"{MODE} === 'edit'", "E")
            p.key("v", code="KeyV", vk=86)
            p.until(f"{MODE} === 'view'", "V: one listener, one switch")

    def test_no_overlap_at_the_four_widths_in_both_colours(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for scheme in ("light", "dark"):
                p.js(f"document.documentElement.dataset.theme = '{scheme}'")
                for w in (1400, 901, 900, 800):
                    size(cdp, p, w, 700)
                    p.js("window.scrollTo(0, 0)")
                    got = p.js("(function(){var g=document.querySelector('[aria-label=\"View or Edit\"]').getBoundingClientRect(), bad=[];"
                               "var bs=[...document.querySelectorAll('[aria-label=\"View or Edit\"] button')].map(b => b.getBoundingClientRect());"
                               "for (const c of document.querySelectorAll('#report-bar > *')) { if (c === document.querySelector('[aria-label=\"View or Edit\"]')) continue;"
                               "var r=c.getBoundingClientRect(); if (r.width && r.left < g.right && r.right > g.left && r.top < g.bottom && r.bottom > g.top) bad.push(c.className || c.id); }"
                               "var o = bs[0].right > bs[1].left + 1;"
                               "return [bad, o, g.right <= innerWidth, document.documentElement.scrollWidth <= innerWidth];})()")
                    self.assertEqual(got, [[], False, True, True], f"{scheme} {w}")


if __name__ == "__main__":
    unittest.main()
