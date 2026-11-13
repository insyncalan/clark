"""Esc in the middle of a Gantt bar drag cancels it: the bar goes back, nothing is saved, no toast, no Undo."""
import time
import unittest

import _paths  # noqa: F401
from test_gantt_e2e import E2E, Browser, CODE
from test_server import chrome, wait


class DragEsc(E2E):
    test_the_gantt_from_settings_to_the_published_file = None      # the parent's own flow is not re-run here

    def test_esc_cancels_a_bar_drag(self):
        with chrome() as cdp:
            br = Browser(self, cdp, self.rig.httpd.server_port)
            self.settings_and_the_tab(br)
            self.add_edit_drag_eye(br)
            before = self.line("Scan paper files")
            br.js("document.querySelectorAll('.toasts > *').forEach(function(t){t.remove()})")
            x, y, w, _h = br.where("[data-g-bar='GNT-002']")
            x = x - w / 2 + 12
            left0 = br.js("document.querySelector(\"[data-g-bar='GNT-002']\").getBoundingClientRect().left")
            br.mouse("mouseMoved", x, y)
            br.mouse("mousePressed", x, y, 1)
            for i in range(1, 6):
                br.mouse("mouseMoved", x + 12 * i, y, 1)
            self.assertNotEqual(br.js("document.querySelector(\"[data-g-bar='GNT-002']\").getBoundingClientRect().left"), left0, "the drag is under way")
            br.key("Escape")
            for i in range(6, 11):
                br.mouse("mouseMoved", x + 12 * i, y, 1)
            br.mouse("mouseReleased", x + 120, y)
            time.sleep(0.6)
            self.assertEqual(br.js("document.querySelector(\"[data-g-bar='GNT-002']\").getBoundingClientRect().left"), left0, "the bar is back")
            self.assertEqual(self.line("Scan paper files"), before, "nothing was saved")
            self.assertFalse(br.text(".toasts"), "no toast")


if __name__ == "__main__":
    unittest.main()
