"""Row 878, the exit (motion): a menu that closes fades out in --dur-instant (opacity only, --ease-exit). Run: python3 dev/run_tests.py test_motion_menu_exit

The live menu is gone at once (aria-expanded false, focus back on the button, nothing a menu query finds); what fades is an inert copy with no class,
role or id. Under reduced motion (the computer's setting, or data-motion=reduce) there is no copy and no wait. A menu opened again removes the copy.
"""
import json
import re
import unittest

from _paths import ROOT
import _testpage as testpage
from _real_server import real_server
from test_server import chrome, wait  # noqa: E402
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402

PAGE = ROOT / "src/clark/page"
CSS = (PAGE / "shell.css").read_text(encoding="utf-8")
HELPER = (PAGE / "src/logic/menuFade.js").read_text(encoding="utf-8")
# Watch for the copy: when it is added, write down what the page looks like at that moment (the copy lasts only 120 ms, so it is read in the page, not polled).
WATCH = """(() => { window.__snaps = []; new MutationObserver((ms) => { for (const m of ms) for (const n of m.addedNodes) if (n.nodeType === 1 && n.hasAttribute('data-fade')) {
  const b = document.querySelector('#profile-btn'), c = getComputedStyle(n);
  window.__snaps.push({anim: c.animationName, dur: c.animationDuration, ease: c.animationTimingFunction, pe: c.pointerEvents, inert: n.hasAttribute('inert'), hidden: n.getAttribute('aria-hidden'),
    cls: n.className, role: n.querySelector('[role]') ? 1 : 0, menus: document.querySelectorAll('.ddmenu, [role=menu]').length, expanded: b.getAttribute('aria-expanded'), focus: document.activeElement === b,
    pos: c.position, transform: c.transform}); } }).observe(document.body, {childList: true}); window.__closed = 0; })()"""
OPEN = "document.querySelector('#profile-btn').click()"
ESC = "document.querySelector('.ddmenu').dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true}))"
MENU_UP = "!!document.querySelector('.ddmenu')"
FADES = "document.querySelectorAll('[data-fade]').length"


class MotionMenuExit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, cls.ids = load_demo()
        cls.code = next(iter(cls.ids))

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        import shutil
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def load(self, cdp, motion, attr=False):
        projects = self.store.read("projects")
        s = real_server(self.store.path, self.store.data_for, who="Demo User", projects=lambda archived=False: projects, page_html=lambda: testpage.html())
        self.addCleanup(s.close)
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": motion}]}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#dashboard&p={self.code}"}, sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#profile-btn')", sid)))
        if attr:
            cdp.js("document.documentElement.dataset.motion = 'reduce'", sid)
        cdp.js(WATCH, sid)
        return sid

    def open_menu(self, cdp, sid):
        cdp.js(OPEN, sid)
        self.assertTrue(wait(lambda: cdp.js(MENU_UP, sid)), "the menu opened")

    def close_by_esc(self, cdp, sid):
        cdp.js(ESC, sid)
        self.assertTrue(wait(lambda: not cdp.js(MENU_UP, sid)), "the menu closed")

    def test_a_closing_menu_is_closed_at_once_and_what_fades_is_an_inert_copy_that_then_goes(self):
        with chrome() as cdp:
            sid = self.load(cdp, "no-preference")
            self.open_menu(cdp, sid)
            self.close_by_esc(cdp, sid)
            self.assertTrue(wait(lambda: cdp.js("window.__snaps.length", sid)), "a fading copy was drawn")
            s = json.loads(cdp.js("JSON.stringify(window.__snaps[0])", sid))
            self.assertEqual(s["anim"], "m-out")
            self.assertEqual(s["dur"], "0.12s")
            self.assertEqual(s["pe"], "none")
            self.assertTrue(s["inert"])
            self.assertEqual(s["hidden"], "true")
            self.assertEqual((s["cls"], s["role"], s["menus"]), ("", 0, 0), "nothing that looks for a menu finds the copy")
            self.assertEqual(s["expanded"], "false")
            self.assertTrue(wait(lambda: cdp.js("document.activeElement === document.querySelector('#profile-btn')", sid)), "focus is back on the button")
            self.assertTrue(wait(lambda: cdp.js(FADES, sid) == 0), "the copy removed itself")

    def test_reduced_motion_by_the_computer_or_by_the_page_setting_closes_at_once_with_no_copy(self):
        for motion, attr in (("reduce", False), ("no-preference", True)):
            with self.subTest(motion=motion, attr=attr), chrome() as cdp:
                sid = self.load(cdp, motion, attr)
                self.open_menu(cdp, sid)
                self.close_by_esc(cdp, sid)
                self.assertEqual(cdp.js("window.__snaps.length + ':' + " + FADES, sid), "0:0")
                self.assertEqual(cdp.js("document.querySelector('#profile-btn').getAttribute('aria-expanded')", sid), "false")

    def test_opening_the_menu_again_at_once_takes_the_fading_copy_away_and_nothing_stacks(self):
        with chrome() as cdp:
            sid = self.load(cdp, "no-preference")
            self.open_menu(cdp, sid)
            # in the page, as the copy is drawn the button is pressed again; when the new menu is drawn, note how many copies are still on the page
            cdp.js("""(() => { window.__again = null; let pressed = false;
              new MutationObserver((ms) => { for (const m of ms) for (const n of m.addedNodes) {
                if (n.nodeType !== 1) continue;
                if (n.hasAttribute('data-fade') && !pressed) { pressed = true; document.querySelector('#profile-btn').click(); }
                else if (pressed && n.classList.contains('ddmenu') && window.__again === null) window.__again = document.querySelectorAll('[data-fade]').length; } })
              .observe(document.body, {childList: true, subtree: true}); })()""", sid)
            cdp.js(ESC, sid)
            self.assertTrue(wait(lambda: cdp.js("window.__again !== null", sid)), "it opened again")
            self.assertEqual(cdp.js("window.__again", sid), 0, "the older copy was taken away as the new menu opened")
            self.assertEqual(cdp.js("document.querySelectorAll('.ddmenu').length", sid), 1)

    def test_the_fade_uses_the_existing_tokens_opacity_only_and_the_four_menu_kinds_use_it(self):
        self.assertIn("m-out var(--dur-instant) var(--ease-exit) forwards", HELPER)
        self.assertRegex(CSS, r"@keyframes m-out \{ to \{ opacity: 0; \} \}")
        self.assertIn("setTimeout", HELPER)
        self.assertIn("clearTimeout", HELPER)
        for rel, name in (("components/Menu.jsx", "useFadeOut"), ("edit/cells/Pop.jsx", "useFadeOut"), ("edit/RowMenu.jsx", "useFadeOut"), ("edit/Gutter.jsx", "useFadeRef")):
            src = (PAGE / "src" / rel).read_text(encoding="utf-8")
            self.assertTrue(re.search(r"import \{[^}]*\b" + name + r"\b[^}]*\} from \"[./]+/logic/menuFade.js\"", src), rel)
            self.assertIn(name + "(", src, rel)


if __name__ == "__main__":
    unittest.main()
