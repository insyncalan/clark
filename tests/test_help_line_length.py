"""Row 1043: Help text lines run a readable length (about 65 to 75 characters), not about 130, at 1400 and 900 px.

Run: python3 dev/run_tests.py test_help_line_length
The real page in headless Chrome. The How do I tab is opened; the widest step line of every task is measured as characters per line
(the width of the text box divided by the width of one "0" in that font), and must stay under 80.
"""
import unittest

from _paths import TOOLS  # noqa: F401
import test_help_nav_page as nav
from test_report_editor import Base

MAX_CH = 80


class LineLength(Base):
    def test_how_do_i_steps_stay_a_readable_measure(self):
        from test_server import chrome
        with chrome() as cdp:
            p = nav.Nav.in_help(self, cdp, "howto")
            for w in nav.SIZES:
                nav.set_size(cdp, p, w)
                got = p.js("""(() => {
                  const out = [];
                  for (const li of document.querySelectorAll('.hp-task li')) {
                    const cs = getComputedStyle(li);
                    const c = document.createElement('canvas').getContext('2d');
                    c.font = cs.fontWeight + ' ' + cs.fontSize + ' ' + cs.fontFamily;
                    const box = li.getBoundingClientRect().width - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
                    out.push(box / c.measureText('0').width);
                  }
                  return out;
                })()""")
                self.assertTrue(got, f"{w}: tasks are drawn")
                self.assertLess(max(got), MAX_CH, f"{w}: widest step line is {max(got):.0f} characters")


if __name__ == "__main__":
    unittest.main()
