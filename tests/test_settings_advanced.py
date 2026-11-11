"""The Advanced group of the Settings menu (item 1024c). Run: python3 dev/run_tests.py test_settings_advanced

What is asserted: Advanced is the last group, set apart from the others, and carries the owner's one plain line under its heading
("These are for setting up Claude, and for when something goes wrong. Most people never need them."), at 1400 and at 900 px, light and dark;
no other group has a line; the line is the page's muted colour (4.5:1 on its ground); the entries of Advanced are still reachable and the
current one is marked. Chrome is required: these tests fail, never skip, without it.
"""
import unittest

import test_settings_head as H
from test_server import chrome

LINE = "These are for setting up Claude, and for when something goes wrong. Most people never need them."


class Menu(H.Head):
    def test_C_advanced_is_last_set_apart_and_has_its_line(self):
        for w in (1400, 900):
            for mode in ("light", "dark"):
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_settings(p, w, mode)
                    self.assertEqual(p.js("[...document.querySelectorAll('.set-group')].map(g => g.querySelector('.set-group-h').textContent).slice(-1)[0]"), "Advanced")
                    self.assertEqual(p.js("[...document.querySelectorAll('.set-group-note')].map(n => n.textContent)"), [LINE])
                    self.assertEqual(p.js("document.querySelector('.set-group-note').closest('.set-group').classList.contains('set-advanced')"), True)
                    self.assertEqual(p.js("[...document.querySelectorAll('.set-advanced .set-item')].map(b => b.textContent)"),
                                     ["Claude and AI", "Logs and diagnostics", "Version and updates"])
                    color = p.js("getComputedStyle(document.querySelector('.set-group-note')).color")
                    ground = p.js("getComputedStyle(document.querySelector('.set-menu')).backgroundColor")
                    self.assertGreaterEqual(H.ratio(H.rgb(color), H.rgb(ground)), 4.5, "the line is readable")
                    self.assertEqual(p.js("document.documentElement.scrollWidth <= window.innerWidth"), True, "no sideways scroll")
                    if w == 1400:
                        # set apart: a rule above the group, and it stands below the other groups
                        self.assertNotEqual(p.js("getComputedStyle(document.querySelector('.set-advanced')).borderTopWidth"), "0px")
                        last = p.js("document.querySelector('.set-advanced').getBoundingClientRect().top >= document.querySelectorAll('.set-group')[3].getBoundingClientRect().bottom")
                        self.assertEqual(last, True)

    def test_C_an_advanced_page_opens_and_is_marked(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_settings(p, 1400, "light", "logs")
            self.assertEqual(self.marked(p), ["Logs and diagnostics=page"])


if __name__ == "__main__":
    unittest.main()
