"""Row 1357 item 8 (Use cases page, Classic only): the Add button on the page is 30 px high with a 1px dashed line (ruling 20-11: the ticket's 30).

Run: python3 dev/run_tests.py test_classic_uc_add_30_1357
Chrome at 1400 and 900 px (fictional data). Page words: none new.
"""
import unittest

from test_server import chrome

import test_use_cases_list as ucl

PROBE = """(() => { const e = document.getElementById('ucAddPage'); const c = getComputedStyle(e);
  return { h: e.getBoundingClientRect().height, style: c.borderTopStyle, w: c.borderTopWidth }; })()"""


class App(ucl.Setup):
    THEME = "prototype-2.0"

    def test_add_button_is_30_high_and_dashed_at_1400_and_900(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width=width, dark=False)
                got = p.js(PROBE)
                self.assertEqual(got["h"], 30, f"{width}: Add button 30 px high")
                self.assertEqual((got["w"], got["style"]), ("1px", "dashed"))


if __name__ == "__main__":
    unittest.main()
