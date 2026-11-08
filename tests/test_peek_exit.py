"""#450 row 66: the peek slides out when it closes (prototype app.css:416-18). Run: python3 dev/run_tests.py test_peek_exit

A copy of the closed panel slides right over var(--dur-instant) with var(--ease-exit) and removes itself; the live panel (#peek)
is gone at once, so nothing that waits for it to close is slowed. The copy has no id, is inert and hidden from reading aids,
and under reduced motion none is made. Checked at 1400 and 900 px, light and dark.
"""
import unittest

from _paths import ROOT
import _testpage as testpage

from _real_server import real_server
from test_server import chrome, wait  # noqa: E402
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402

WATCH = """(() => { window.__seen = []; new MutationObserver(ms => { for (const m of ms) for (const n of m.addedNodes)
  if (n.nodeType === 1 && n.classList.contains('leaving')) window.__seen.push({
    id: n.id, inert: n.hasAttribute('inert'), hidden: n.getAttribute('aria-hidden'), peeks: document.querySelectorAll('#peek').length,
    anim: getComputedStyle(n).animationName, dur: getComputedStyle(n).animationDuration, text: n.textContent.length }); })
  .observe(document.body, { childList: true }); })()"""


# Where the world stands at the moment the copy goes into the page: how many live panels are still in the document.
APPEND_PROBE = """(() => { window.__live = []; const a = document.body.appendChild.bind(document.body);
  document.body.appendChild = (n) => { if (n && n.classList && n.classList.contains('leaving'))
    window.__live.push(document.querySelectorAll('#peek, #help-peek').length); return a(n); }; })()"""


class PeekExit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, cls.ids = load_demo()
        cls.code = next(iter(cls.ids))
        base = cls.store.data_for(cls.code)
        cls.item = next(a["id"] for a in base["actions"] if a["status"] not in ("Closed", "Cancelled"))

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        import shutil
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def load(self, cdp, width, scheme, motion="no-preference"):
        projects = self.store.read("projects")            # read here: the store's connection belongs to this thread, and the server answers on another
        s = real_server(self.store.path, self.store.data_for, who="Demo User", projects=lambda archived=False: projects,
                        page_html=lambda: testpage.html())
        self.addCleanup(s.close)
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme},
                                                              {"name": "prefers-reduced-motion", "value": motion}]}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#work&p={self.code}&item={self.item}"}, sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek dt')", sid)))
        return sid

    def close(self, cdp, sid):
        cdp.js(WATCH, sid)
        cdp.js("document.querySelector('[data-pk-close]').click()", sid)
        self.assertTrue(wait(lambda: cdp.js("!document.querySelector('#peek')", sid)))

    def test_closing_slides_a_copy_out_and_it_goes_away(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    sid = self.load(cdp, width, scheme)
                    self.close(cdp, sid)
                    seen = cdp.js("window.__seen", sid)
                    self.assertEqual(len(seen), 1, "one copy slides out")
                    c = seen[0]
                    self.assertEqual((c["id"], c["inert"], c["hidden"], c["peeks"]), ("", True, "true", 0))
                    self.assertEqual((c["anim"], c["dur"]), ("pk-out", "0.12s"))
                    self.assertGreater(c["text"], 0, "it is the panel's own content")
                    self.assertTrue(wait(lambda: cdp.js("!document.querySelector('.peek.leaving')", sid)), "the copy removes itself")

    def test_under_reduced_motion_nothing_slides(self):
        with chrome() as cdp:
            sid = self.load(cdp, 1400, "light", motion="reduce")
            self.close(cdp, sid)
            self.assertEqual(cdp.js("window.__seen", sid), [])

    def test_the_copy_is_made_after_the_render_when_the_live_panel_is_gone(self):
        """Item 567: the copy is made in an effect, not while the component renders (when the old panel is still in the page)."""
        for motion in ("no-preference", "reduce"):
            with self.subTest(motion=motion), chrome() as cdp:
                sid = self.load(cdp, 1400, "light", motion=motion)
                cdp.js(APPEND_PROBE, sid)
                self.close(cdp, sid)
                self.assertTrue(wait(lambda: cdp.js("document.getAnimations().length === 0", sid)), "the motion has ended")
                live = cdp.js("window.__live", sid)
                self.assertEqual(live, [0] if motion == "no-preference" else [], "no live panel was in the page when the copy went in")

    def test_the_stylesheet_has_the_prototypes_exit(self):
        css = (ROOT / "src/clark/page/shell.css").read_text(encoding="utf-8")
        self.assertIn("animation: pk-out var(--dur-instant) var(--ease-exit) forwards", css)
        self.assertIn("@keyframes pk-out { to { transform: translateX(104%); } }", css)


if __name__ == "__main__":
    unittest.main()
