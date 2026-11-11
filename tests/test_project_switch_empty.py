"""Row 1092 read fix: with no project listed and none open the project button's menu holds only the list, so with nothing to list the button opens no menu and says no extra words (no row, no Settings link) (in a real browser at 1400 and 900; the old source-only pins are gone).

Run: python3 dev/run_tests.py test_project_switch_empty
"""
import unittest

from test_publish_dialog import Base, WIDTHS
from test_server import chrome, wait


class EmptyMenu(Base):
    def test_C_an_empty_project_list_shows_nothing_but_the_list(self):
        self.rig.httpd.projects = lambda archived=False: []
        with chrome() as cdp:
            p = self.page(cdp, "#settings")
            p.until("document.querySelector('#project-name') && document.querySelector('#project-name').tagName === 'BUTTON'", "the menu button")
            self.assertEqual(tuple(WIDTHS), (1400, 900))
            for w in WIDTHS:
                p.width(w)
                p.js("document.querySelector('#project-name').click()")
                wait(lambda: False, 1)                      # a second for a menu that would wrongly open
                self.assertEqual(p.js("!!document.querySelector('#project-menu')"), False, "nothing opens: the menu holds only the list, and the list is empty")
                self.assertEqual(p.js("document.querySelector('#project-name').getAttribute('aria-expanded') === 'true'"), False)
                body = p.js("document.body.textContent")
                self.assertNotIn("No project yet", body)
                self.assertNotIn("Open Settings to add one", body)


if __name__ == "__main__":
    unittest.main()
