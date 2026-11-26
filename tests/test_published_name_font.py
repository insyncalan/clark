"""Row 1228: in a published report the project name in the bar is drawn in the same face, weight, size and letter spacing on every tab. It is
the heading element on the Dashboard and a plain box on the other tabs, and the box took the text face where the heading took the heading face.
In a real browser, at 1400 and 900 px, light look. Fictional data.

Run: python3 -m unittest test_published_name_font      (from tests/, with PYTHONPATH=../src:../vendor:.; needs Chrome)
"""
import re
import unittest

import test_glance_page as _test_glance_page
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

from _paths import SRC

CSS = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
LOOK = """(() => {
  const n = document.querySelector('.top-file .top-name'), l = document.querySelector('.top-file .top-line'), t = document.querySelector('.top-file .tab');
  const s = (e) => { const c = getComputedStyle(e); return [c.fontFamily, c.fontWeight, c.fontSize, c.letterSpacing]; };
  return {tag: n.tagName, name: s(n), line: s(l), tab: s(t), head: getComputedStyle(document.documentElement).getPropertyValue('--font-head').trim()};
})()"""


class NameFont(_test_glance_page.Published):
    def test_the_project_name_has_one_look_on_every_tab(self):
        path = self.publish()
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.draw(cdp, path, width)
                p.until("!!document.querySelector('.top-file .tab') && !!document.querySelector('.glance')", "the bar drew")
                first = p.js(LOOK)
                self.assertEqual(first["tag"], "H1", "the Dashboard's name is the heading")
                self.assertIn("Montserrat", first["name"][0], "the name takes the heading face")
                names = p.js("[...document.querySelectorAll('.top-file .tab')].map(t => t.dataset.view)")
                self.assertGreaterEqual(len(names), 3)
                for view in names[1:]:
                    p.js(f"document.querySelector('.top-file .tab[data-view=\"{view}\"]').click()")
                    p.until(f"document.querySelector('.top-file .tab[aria-selected=true]').dataset.view === '{view}'", f"{view} opened")
                    here = p.js(LOOK)
                    self.assertEqual(here["tag"], "DIV", f"{view} has its own heading, so the name is a box")
                    self.assertEqual(here["name"], first["name"], f"the name on {view} is drawn as on the Dashboard")
                    self.assertEqual(here["line"], first["line"], f"the report line on {view} is drawn as on the Dashboard")

    def test_the_name_rule_names_the_heading_face_by_its_token(self):
        rule = re.search(r"^\.top-name \{([^}]*)\}", CSS, re.M).group(1)
        self.assertIn("font-family: var(--font-head)", rule)
        self.assertIn("letter-spacing: -.01em", rule)


if __name__ == "__main__":
    unittest.main()
