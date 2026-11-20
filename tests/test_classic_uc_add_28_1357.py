"""Row 1357 item 8 (Use cases page, Classic only): the Add button on the page is 28 px high with a 1px line, as the prototype's add button (usecases.css:19, height 28px). The ticket text says 30 px; the prototype file says 28 px and the page already draws 28 px.

Run: python3 dev/run_tests.py test_classic_uc_add_28_1357
Chrome at 1400 and 900 px (fictional data). Page words: none new.
"""
import unittest

from test_server import chrome

import test_use_cases_list as ucl

PROBE = """(() => { const e = document.getElementById('ucAddPage'); const c = getComputedStyle(e);
  return { h: e.getBoundingClientRect().height, style: c.borderTopStyle, w: c.borderTopWidth }; })()"""


class App(ucl.Setup):
    THEME = "prototype-2.0"

    def test_add_button_is_28_high_and_dashed_at_1400_and_900(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width=width, dark=False)
                got = p.js(PROBE)
                self.assertEqual(got["h"], 28, f"{width}: Add button 28 px high")
                self.assertEqual((got["w"], got["style"]), ("1px", "dashed"))


if __name__ == "__main__":
    unittest.main()
