"""Row 922 (motion): a menu fades out as it closes. Run: python3 dev/run_tests.py test_motion_menu_exit

Follow-up to row 878 (the drop-in). Menu.jsx keeps a closed menu drawn for its fade (class leaving, inert and aria-hidden so it is out of the tab
order and takes no key or pointer), runs m-out over --dur-instant with --ease-exit, and removes it when the animation ends (a 400 ms timer guards it).
Opacity only, inside the Motion block of shell.css. Under reduced motion it goes at once. Checked at 1400 and 900 px, light and dark.
"""
import re
import unittest

from _paths import ROOT
from test_motion_dialogs_menus import MotionDialogsMenus as Base, MENU

CSS = (ROOT / "src/clark/page/shell.css").read_text(encoding="utf-8")
JSX = (ROOT / "src/clark/page/src/components/Menu.jsx").read_text(encoding="utf-8")
STATE = """(() => { const m = document.querySelector('.ddmenu'); return m ? JSON.stringify({name: getComputedStyle(m).animationName, leaving: m.classList.contains('leaving'),
  inert: m.inert, hidden: m.getAttribute('aria-hidden')}) : null; })()"""


class MotionMenuExit(Base):
    def test_row_922_a_menu_fades_out_and_is_gone_at_once_when_reduced(self):
        import json
        from test_server import chrome, wait
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                for motion in ("no-preference", "reduce"):
                    with self.subTest(width=width, scheme=scheme, motion=motion), chrome() as cdp:
                        sid = self.load(cdp, width, scheme, motion)
                        cdp.js(MENU, sid)
                        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.ddmenu')", sid)), "opened")
                        cdp.js("document.querySelector('.ddmenu').dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))", sid)
                        if motion == "no-preference":
                            got = json.loads(cdp.js(STATE, sid))
                            self.assertEqual(got, {"name": "m-out", "leaving": True, "inert": True, "hidden": "true"})
                        self.assertTrue(wait(lambda: cdp.js("document.querySelector('.ddmenu') === null", sid), 15), "gone after the fade (or the guard)")
                        self.assertTrue(wait(lambda: cdp.js("document.activeElement.id === 'profile-btn'", sid), 15), "focus is back on the button")

    def test_row_922_css_is_inside_the_motion_block_with_tokens_and_the_menu_keeps_its_guard(self):
        block = CSS[CSS.index("Motion: motion that explains"):]
        block = block[:block.index("@media (hover: hover)")]
        self.assertRegex(block, r"\.ddmenu\.leaving \{ pointer-events: none; animation: m-out var\(--dur-instant\) var\(--ease-exit\) forwards; \}")
        self.assertNotRegex(CSS.replace(block, ""), r"\.ddmenu\.leaving")
        self.assertRegex(JSX, r"setTimeout\(gone, 400\)")
        self.assertRegex(JSX, r'inert=\{leaving \? true : undefined\} aria-hidden=\{leaving \? "true" : undefined\}')
        self.assertRegex(JSX, r"stillMotion\(\) \|\| !menu \? \"closed\" : \"leaving\"")
        self.assertRegex(re.search(r"@keyframes m-out \{(.*?)\}\s*\}?", CSS).group(0), r"opacity: 0")


for _n in [n for n in dir(Base) if n.startswith("test_") and "row_922" not in n]:
    setattr(MotionMenuExit, _n, None)     # the inherited row 877 and 878 tests belong to their own file

if __name__ == "__main__":
    unittest.main()
