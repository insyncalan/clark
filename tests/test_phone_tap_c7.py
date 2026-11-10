"""Sweep c7: at phone width (640 px and under) the People table, the edit rows, the Settings chips, the use case list and the menus fit and are 44 px to tap.

Run: python3 dev/run_tests.py test_phone_tap_c7

The style sheet tests read the sheets only; PhoneLayout measures a real browser. No new words.
"""
import json
import re
import time
import unittest

from _paths import ROOT

import test_peek as tp  # noqa: E402
from test_server import chrome, wait  # noqa: E402

PAGE = ROOT / "src" / "clark" / "page"


def phone_css(path):
    """The text of every @media (max-width: 640px) block in the file."""
    text = path.read_text(encoding="utf-8")
    out = []
    for m in re.finditer(r"@media \(max-width: 640px\)\s*\{", text):
        depth, i = 1, m.end()
        while depth:
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        out.append(text[m.end():i - 1])
    return "\n".join(out)


def rule(css, selector):
    """The declarations of the rule whose selector list holds this selector."""
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        if selector in [s.strip() for s in m.group(1).split(",")]:
            return m.group(2)
    return ""


class PhoneWidth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shell = phone_css(PAGE / "shell.css")
        cls.edit = phone_css(PAGE / "src" / "edit" / "edit.css")

    def test_people_table_does_not_run_past_the_window(self):
        self.assertIn("table-layout: fixed", rule(self.shell, "table.pp-table"))

    def test_edit_row_meta_wraps_and_its_pieces_shrink(self):
        self.assertIn("flex-wrap: wrap", rule(self.edit, ".item-rows-edit .wl-meta .cell-val"))
        self.assertIn("min-width: 0", rule(self.edit, ".item-rows-edit .wl-meta .cell-val"))
        late = rule(self.edit, ".item-rows-edit .wl-meta .late")
        self.assertIn("min-width: 0", late)
        self.assertIn("overflow-wrap: anywhere", late)

    def test_settings_chips_are_44_px(self):
        self.assertIn("min-height: 44px", rule(self.shell, ".set-item"))

    def test_use_case_link_and_eye_are_44_px(self):
        self.assertIn("min-height: 44px", rule(self.edit, ".ucl-go"))
        eye = rule(self.edit, ".ucl-eye")
        self.assertIn("width: 44px", eye)
        self.assertIn("height: 44px", eye)

    def test_profile_menu_items_are_44_px(self):
        for sel in ('.ddmenu [role="menuitem"]', '.ddmenu [role="menuitemradio"]'):
            self.assertIn("min-height: 44px", rule(self.shell, sel), sel)
        self.assertIn("min-height: 44px", rule(self.shell, '.ddmenu [role="menuitemradio"].hp'))


    def test_the_36_px_use_case_columns_of_the_widths_sweep_are_gone(self):
        """One source of truth on a phone: the sweep b5 block (56px 1fr 36px) is deleted, only the 44 px columns remain."""
        css = phone_css(PAGE / "src" / "edit" / "edit.css")
        for decl in re.findall(r"\.ucl-row\s*\{([^{}]*)\}", css):
            self.assertNotIn("36px", decl)
        self.assertEqual(len(re.findall(r"\.ucl-row\s*\{", css)), 1)
        self.assertEqual(len(re.findall(r"\.ucl-hd\s*\{", css)), 1)
        self.assertIn("56px minmax(0, 1fr) 44px", rule(css, ".ucl-row"))


WIDE = "(() => { const d = document.documentElement; return d.scrollWidth - d.clientWidth; })()"


class PhoneLayout(unittest.TestCase):
    setUpClass = tp.Browser.__dict__["setUpClass"]
    tearDownClass = tp.Browser.__dict__["tearDownClass"]
    load_page = tp.Browser.load_page
    edit_mode = tp.Browser.edit_mode

    def go(self, cdp, sid, hash_, ready):
        cdp.js(f"location.hash = {json.dumps(hash_)}", sid)
        self.assertTrue(wait(lambda: cdp.js(ready, sid)), hash_)
        time.sleep(0.4)

    def test_use_cases_and_settings_fit_and_the_taps_are_44_px_at_375_and_640(self):
        for width in (375, 640):
            with chrome() as cdp:
                s, sid = self.load_page(cdp, width)
                cdp.js("document.documentElement.dataset.theme = 'light'", sid)
                self.edit_mode(cdp, sid)
                self.go(cdp, sid, f"#usecases&p={self.code}", "!!document.querySelector('.ucl-row .ucl-eye')")
                self.assertLessEqual(cdp.js(WIDE, sid), 0, f"use cases scroll sideways at {width}")
                self.assertEqual(cdp.js("getComputedStyle(document.querySelector('.ucl-hd')).display", sid), "none")
                sizes = cdp.js("(() => { const r = e => { const b = e.getBoundingClientRect(); return [b.width, b.height]; }; const g = document.querySelector('.ucl-row .ucl-go'); const e = document.querySelector('.ucl-row .ucl-eye'); return [r(g), r(e)]; })()", sid)
                self.assertGreaterEqual(sizes[0][1], 44, f"link height at {width}")
                self.assertGreaterEqual(sizes[1][0], 44, f"eye width at {width}")
                self.assertGreaterEqual(sizes[1][1], 44, f"eye height at {width}")
                self.go(cdp, sid, f"#settings&p={self.code}&s=people", "!!document.querySelector('#people')")
                self.assertLessEqual(cdp.js(WIDE, sid), 0, f"Settings (People table) scroll sideways at {width}")


if __name__ == "__main__":
    unittest.main()
