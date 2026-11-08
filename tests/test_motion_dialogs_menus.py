"""Rows 877 and 878 (motion): a dialog and its dim background ease in, and a menu or picker drops in. Run: python3 dev/run_tests.py test_motion_dialogs_menus

Dialogs rise 12 px and scale in over --dur-state and the dim background fades over the same time; a menu drops 4 px over --dur-instant.
Both sit in the one Motion block, so under reduced motion (the computer's setting) nothing animates. Opacity and transform only.
Checked at 1400 and 900 px, light and dark.
"""
import re
import unittest
from _editor_checks import for_url

from _paths import ROOT
import _testpage as testpage

from _real_server import real_server
from test_server import chrome, wait  # noqa: E402
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402

CSS = (ROOT / "src/clark/page/shell.css").read_text(encoding="utf-8")
# A native dialog opened as a modal, and the Add a section box on its scrim, the way the page draws them.
MAKE = """(() => { const d = document.createElement('dialog'); d.className = 'dlg'; d.id = 'row877-dlg'; d.textContent = 'x'; document.body.appendChild(d); d.showModal();
  const s = document.createElement('div'); s.className = 'ad-scrim'; s.id = 'row877-scrim'; const f = document.createElement('form'); f.className = 'ad'; f.id = 'row877-ad'; s.appendChild(f); document.body.appendChild(s);
  const an = (e, ps) => { const c = getComputedStyle(e, ps); return c.animationName; };
  return JSON.stringify({dlg: an(d), backdrop: an(d, '::backdrop'), scrim: an(s), ad: an(f)}); })()"""
MENU = "document.querySelector('#profile-btn').click()"
MENU_NAME = "(() => { const m = document.querySelector('.ddmenu'); return m ? getComputedStyle(m).animationName : null; })()"


class MotionDialogsMenus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, cls.ids = load_demo()
        cls.code = next(iter(cls.ids))

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        import shutil
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def load(self, cdp, width, scheme, motion):
        projects = self.store.read("projects")
        s = real_server(self.store.path, self.store.data_for, who="Demo User", projects=lambda archived=False: projects,
                        page_html=lambda: testpage.html())
        self.addCleanup(s.close)
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme},
                                                              {"name": "prefers-reduced-motion", "value": motion}]}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{s.port}/#dashboard&p={self.code}")}, sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#profile-btn')", sid)))
        return sid

    def test_row_877_dialogs_and_their_dim_background_ease_in_and_are_still_when_reduced(self):
        import json
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                for motion, want in (("no-preference", "m-dlg"), ("reduce", "none")):
                    with self.subTest(width=width, scheme=scheme, motion=motion), chrome() as cdp:
                        sid = self.load(cdp, width, scheme, motion)
                        got = json.loads(cdp.js(MAKE, sid))
                        self.assertEqual(got["dlg"], want)
                        self.assertEqual(got["ad"], want)
                        fade = "m-in" if motion == "no-preference" else "none"
                        self.assertEqual(got["backdrop"], fade)
                        self.assertEqual(got["scrim"], fade)

    def test_row_878_menus_drop_in_and_are_still_when_reduced(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                for motion, want in (("no-preference", "m-drop"), ("reduce", "none")):
                    with self.subTest(width=width, scheme=scheme, motion=motion), chrome() as cdp:
                        sid = self.load(cdp, width, scheme, motion)
                        cdp.js(MENU, sid)
                        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.ddmenu')", sid)), "the menu opened")
                        self.assertEqual(cdp.js(MENU_NAME, sid), want)

    def test_rows_877_878_are_inside_the_motion_block_use_tokens_and_move_only_opacity_and_transform(self):
        block = CSS[CSS.index("Motion: motion that explains"):]
        block = block[:block.index("@media (hover: hover)")]
        for sel, name in ((".dlg[open], .ad", "m-dlg"), (".dlg[open]::backdrop, .ad-scrim", "m-in"), (".menu, .ddmenu, .cpop", "m-drop")):
            m = re.search(re.escape(sel) + r" \{ animation: " + name + r" var\(--dur-(state|instant)\) var\(--ease-enter\) 1; \}", block)
            self.assertTrue(m, sel)
        self.assertNotRegex(CSS.replace(block, ""), r"animation:\s*m-(dlg|drop)")
        for name in ("m-dlg", "m-drop"):
            body = re.search(r"@keyframes " + name + r" \{(.*?)\}\s*\}", CSS, re.S).group(1)
            self.assertNotRegex(body, r"height|margin|padding|top|left|width")
            self.assertRegex(body, r"opacity: 0; transform: translateY\(")


if __name__ == "__main__":
    unittest.main()
