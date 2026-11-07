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

# Row 938-3: records, from before the open, the longest end time (delay + duration, in ms) of every animation drawn on a .ddmenu, by name.
WATCH_ANIMATIONS = """(() => { window.__menuAnims = {}; const tick = () => { for (const a of document.getAnimations()) { const t = a.effect && a.effect.target;
  if (t && t.closest && t.closest('.ddmenu') && a.animationName) window.__menuAnims[a.animationName] = Math.max(window.__menuAnims[a.animationName] || 0, a.effect.getComputedTiming().endTime); }
  requestAnimationFrame(tick); }; tick(); return true; })()"""


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
                        self.assertTrue(wait(lambda: cdp.js("document.getAnimations().length === 0", sid), 15), "no animation is left running after the exit")
                        self.assertTrue(wait(lambda: cdp.js("document.activeElement.id === 'profile-btn'", sid), 15), "focus is back on the button")

    def test_row_922_reduced_motion_never_draws_the_leaving_menu(self):
        from test_server import chrome, wait
        # a MutationObserver installed before the Esc records any node that ever carries class leaving, so a one-frame appearance is not missed
        WATCH = """(() => { window.__sawLeaving = false; const see = () => { if (document.querySelector('.ddmenu.leaving')) window.__sawLeaving = true; };
          new MutationObserver((rs) => { see(); for (const r of rs) { if (r.target.classList && r.target.classList.contains('leaving')) window.__sawLeaving = true;
            for (const n of r.addedNodes) if (n.classList && n.classList.contains('leaving')) window.__sawLeaving = true; } })
            .observe(document.body, {subtree: true, childList: true, attributes: true, attributeFilter: ['class']}); return true; })()"""
        with chrome() as cdp:
            sid = self.load(cdp, 1400, "light", "reduce")
            cdp.js(MENU, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.ddmenu')", sid)), "opened")
            cdp.js(WATCH, sid)
            cdp.js("document.querySelector('.ddmenu').dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))", sid)
            gone = wait(lambda: cdp.js("document.querySelector('.ddmenu') === null", sid), 0.3)
            self.assertFalse(cdp.js("window.__sawLeaving", sid), "reduced motion: the menu was never drawn leaving")
            self.assertTrue(gone, "reduced motion: the menu is gone at once, within 300 ms")

    def test_row_922_the_guard_timer_removes_a_menu_whose_animation_never_ends(self):
        import time
        from test_server import chrome, wait
        with chrome() as cdp:
            sid = self.load(cdp, 1400, "light", "no-preference")
            cdp.js(MENU, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.ddmenu')", sid)), "opened")
            # a constructed style sheet: the page's content policy refuses an inline <style> element (it was tried and had no effect)
            cdp.js("(() => { const sh = new CSSStyleSheet(); sh.replaceSync('.ddmenu.leaving { animation: none !important; }'); document.adoptedStyleSheets = [...document.adoptedStyleSheets, sh]; })()", sid)
            t0 = time.monotonic()
            cdp.js("document.querySelector('.ddmenu').dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))", sid)
            gone = False
            while time.monotonic() - t0 < 1.5:        # the guard is 400 ms: not the 15 s budget, so removing the guard fails this
                if cdp.js("document.querySelector('.ddmenu') === null", sid):
                    gone = True
                    break
                time.sleep(0.05)
            self.assertTrue(gone, "with no animation to end, the 400 ms guard removed the menu within 1.5 s")
            self.assertTrue(wait(lambda: cdp.js("document.activeElement.id === 'profile-btn'", sid), 3), "focus is back on the button")

    def test_row_922_css_is_inside_the_motion_block_with_tokens_and_the_menu_keeps_its_guard(self):
        block = CSS[CSS.index("Motion: motion that explains"):]
        block = block[:block.index("@media (hover: hover)")]
        self.assertRegex(block, r"\.ddmenu\.leaving \{ pointer-events: none; animation: m-out var\(--dur-instant\) var\(--ease-exit\) forwards; \}")
        self.assertNotRegex(CSS.replace(block, ""), r"\.ddmenu\.leaving")
        self.assertRegex(JSX, r"setTimeout\(gone, 400\)")
        self.assertRegex(JSX, r'inert=\{leaving \? true : undefined\} aria-hidden=\{leaving \? "true" : undefined\}')
        self.assertRegex(JSX, r"stillMotion\(\) \|\| !menu \? \"closed\" : \"leaving\"")
        self.assertRegex(re.search(r"@keyframes m-out \{(.*?)\}\s*\}?", CSS).group(0), r"opacity: 0")

    def test_row_938_3_every_menu_opens_and_closes_in_under_180_ms_and_a_reduced_motion_menu_runs_nothing(self):
        import json
        from test_server import chrome, wait
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                for motion in ("no-preference", "reduce"):
                    with self.subTest(width=width, scheme=scheme, motion=motion), chrome() as cdp:
                        sid = self.load(cdp, width, scheme, motion)
                        cdp.js(WATCH_ANIMATIONS, sid)
                        cdp.js(MENU, sid)
                        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.ddmenu')", sid)), "opened")
                        self.assertTrue(wait(lambda: cdp.js("document.getAnimations().length === 0", sid), 15), "the open finished")
                        cdp.js("document.querySelector('.ddmenu').dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))", sid)
                        self.assertTrue(wait(lambda: cdp.js("document.querySelector('.ddmenu') === null", sid), 15), "gone")
                        self.assertTrue(wait(lambda: cdp.js("document.getAnimations().length === 0", sid), 15), "the close finished")
                        self.assert_timings(json.loads(cdp.js("JSON.stringify(window.__menuAnims)", sid)), motion)

    def assert_timings(self, seen, motion, closes_instantly=False):
        if motion == "reduce":
            self.assertEqual(seen, {}, "reduced motion: no menu animation ever ran")
            return
        # the client Report menu has no leaving phase: it is removed at once (0 ms), which is under 180 ms too
        self.assertEqual(sorted(seen), ["m-drop"] if closes_instantly else ["m-drop", "m-out"], "the open and the close each ran one animation")
        for name, end in seen.items():
            self.assertTrue(0 < end < 180, f"{name} ends at {end} ms: under 180 ms (the --dur-view token)")

    def test_row_938_3_the_published_page_menus_open_and_close_in_under_180_ms(self):
        """The published Group by menu and the client Report menu are the same .ddmenu from the shared stylesheet (shell.css)."""
        import json
        import test_client_page_filters as cpf
        from test_server import chrome, wait
        cpf.ClientPageFilters.setUpClass()
        self.addCleanup(cpf.ClientPageFilters.tearDownClass)
        path = cpf.ClientPageFilters.path
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                for button, motion in (("#group-by", "no-preference"), ("#client-menu-btn", "no-preference"), ("#group-by", "reduce"), ("#client-menu-btn", "reduce")):
                    with self.subTest(width=width, scheme=scheme, button=button, motion=motion), chrome() as cdp:
                        sid = cpf.open_page(cdp, path.as_uri() + "#work", width, scheme)
                        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}, {"name": "prefers-reduced-motion", "value": motion}]}, sid)
                        self.assertTrue(wait(lambda: cdp.js(f"!!document.querySelector({json.dumps(button)})", sid)), "the page drew")
                        cdp.js(WATCH_ANIMATIONS, sid)
                        cdp.js(f"document.querySelector({json.dumps(button)}).click()", sid)
                        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.ddmenu')", sid)), "opened")
                        self.assertTrue(wait(lambda: cdp.js("document.getAnimations().length === 0", sid), 15), "the open finished")
                        cdp.js("document.querySelector('.ddmenu').dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))", sid)
                        self.assertTrue(wait(lambda: cdp.js("document.querySelector('.ddmenu') === null", sid), 15), "gone")
                        self.assertTrue(wait(lambda: cdp.js("document.getAnimations().length === 0", sid), 15), "the close finished")
                        self.assert_timings(json.loads(cdp.js("JSON.stringify(window.__menuAnims)", sid)), motion, button == "#client-menu-btn")

    def test_row_938_3_no_menu_rule_uses_a_duration_of_180_ms_or_more(self):
        block = CSS[CSS.index("Motion: motion that explains"):]
        block = block[:block.index("@media (hover: hover)")]
        for line in block.splitlines():
            if re.search(r"\.(ddmenu|menu|cpop)\b[^{]*\{[^}]*animation:", line):
                self.assertRegex(line, r"var\(--dur-instant\)", line.strip())
                self.assertNotRegex(line, r"--dur-(view|state|layout|enter)")


for _n in [n for n in dir(Base) if n.startswith("test_") and "row_922" not in n]:
    setattr(MotionMenuExit, _n, None)     # the inherited row 877 and 878 tests belong to their own file

if __name__ == "__main__":
    unittest.main()
