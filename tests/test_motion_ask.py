"""Row 885 (motion): the ask clark panel rises from the bottom of the window and sinks back. Run: python3 dev/run_tests.py test_motion_ask

Opening runs ask-up over --dur-layout with --ease-enter; closing runs ask-down over --dur-state with --ease-exit, and the panel stays drawn
until that ends (a 400 ms timer guards it). Transform only: the panel's place (fixed, full height, right edge) is not touched. Under reduced
motion it appears and leaves at once, as before. Checked at 1400 and 900 px, light and dark.
"""
import re
import unittest

from _paths import ROOT
from test_ask_panel import Panel

CSS = (ROOT / "src/clark/page/shell.css").read_text(encoding="utf-8")
EDIT = (ROOT / "src/clark/page/src/edit/edit.css").read_text(encoding="utf-8")
JSX = (ROOT / "src/clark/page/src/edit/AskPanel.jsx").read_text(encoding="utf-8")
NAME = "getComputedStyle(document.querySelector('#ask-panel')).animationName"


class MotionAsk(Panel):
    def test_row_885_the_panel_rises_and_sinks_and_is_still_when_reduced(self):
        from test_server import chrome
        with chrome() as cdp:
            p = self.visit(cdp)
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                for theme in ("light", "dark"):
                    p.js(f"document.documentElement.dataset.theme = '{theme}'")
                    for motion, up, down in (("no-preference", "ask-up", "ask-down"), ("reduce", "none", None)):
                        with self.subTest(width=width, theme=theme, motion=motion):
                            cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": motion}]}, p.sid)
                            p.key("/", code="Slash", vk=191)
                            p.until("!!document.querySelector('#ask-panel')", "opened")
                            self.assertEqual(p.js(NAME), up)
                            p.until("document.querySelector('#ask-panel').getAnimations().length === 0", "settled")
                            p.key("Escape", code="Escape", vk=27)
                            if down:
                                self.assertEqual(p.js(NAME), down, "it sinks before it goes")
                                self.assertTrue(p.js("document.querySelector('#ask-panel').classList.contains('leaving')"))
                            p.until("document.querySelector('#ask-panel') === null", "gone", seconds=0.5 if down else 10)

    def test_row_885_is_edit_only_gated_uses_tokens_and_moves_only_transform(self):
        i = EDIT.index("row 885:")
        block = EDIT[i:EDIT.index("\n}\n", i)]
        self.assertIn("prefers-reduced-motion: no-preference", block)
        self.assertRegex(block, r'\[data-motion="reduce"\]\) \.ask-panel \{ animation: ask-up var\(--dur-layout\) var\(--ease-enter\) 1; \}')
        self.assertRegex(block, r"\.ask-panel\.leaving \{[^}]*animation: ask-down var\(--dur-state\) var\(--ease-exit\) forwards;")
        self.assertNotRegex(CSS, r"ask-panel|ask-up|ask-down", "the published page's stylesheet has none of it")
        for name in ("ask-up", "ask-down"):
            body = re.search(r"@keyframes " + name + r" \{(.*)\}\s*\n", EDIT[i:]).group(1)
            self.assertRegex(body, r"translateY\(100%\)")
            self.assertNotRegex(body, r"height|margin|padding|top|left|width|bottom")
        self.assertRegex(JSX, r"setTimeout\(finish, 400\)")
        self.assertRegex(JSX, r"if \(!open && !leaving\) return null")


if __name__ == "__main__":
    unittest.main()
