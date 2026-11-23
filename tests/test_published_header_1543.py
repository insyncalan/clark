"""Row 1543, the published report's header (part 1): no "As at" anywhere in the header or its menu, the light and dark switcher and the
profile circle are 32 x 32 px, and no edit control in the header. In a real browser, at 1400 and 900 px, light and dark. Fictional data.

Run: python3 dev/run_tests.py test_published_header_1543        (needs Chrome; run only while the machine's load is under 70)
"""
import re
import unittest

from _demo import USER
import test_glance_page
from _publish import PublishedFile
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

CASES = ((1400, False), (1400, True), (900, False), (900, True))

BAR = """(() => {
  const bar = document.querySelector('header.top'), box = (e) => { if (!e) return null; const b = e.getBoundingClientRect(); return {w: Math.round(b.width * 10) / 10, h: Math.round(b.height * 10) / 10, r: b.right}; };
  const vis = (e) => { const s = getComputedStyle(e), b = e.getBoundingClientRect(); return s.display !== 'none' && s.visibility !== 'hidden' && b.width > 0 && b.height > 0; };
  return {text: bar.textContent, theme: box(bar.querySelector('#client-theme-btn')), badge: box(bar.querySelector('#client-menu-btn')),
    weekEnding: /Week ending/.test(bar.textContent), dates: [...bar.querySelectorAll('*')].filter((e) => vis(e) && !e.children.length && /\\b\\d\\d-\\d\\d-\\d{4}\\b/.test(e.textContent)).map((e) => e.textContent.trim()),
    controls: [...bar.querySelectorAll('button, a[href], input, select, [role=tab], [role=menuitem], [role=switch]')].filter(vis).map((e) => ((e.getAttribute('aria-label') || '') + '|' + (e.id || '') + '|' + e.className + '|' + (e.textContent || '').trim()).toLowerCase())};
})()"""


class Header1543(PublishedFile, test_glance_page.Setup):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"week_ending": "2026-10-23"})
        self._cm = None
        self.addCleanup(self.close)

    def close(self):
        if self._cm:
            self._cm.__exit__(None, None, None)
            self._cm = None

    def bar(self, width, dark):
        self.close()
        if not getattr(self, "_path", None):
            self._path = self.publish()
        self._cm = chrome()
        cdp = self._cm.__enter__()
        p = self.draw(cdp, self._path, width, dark)
        p.until("!!document.querySelector('header.top .tab') && !!document.querySelector('#client-menu-btn')", "the bar drew")
        return p

    def test_published_header_no_as_at(self):
        for width, dark in CASES:
            with self.subTest(width=width, dark=dark):
                p = self.bar(width, dark)
                b = p.js(BAR)
                self.assertNotRegex(b["text"], r"(?i)as at", "no As at in the header")
                self.assertTrue(b["weekEnding"], "Week ending stays")
                self.assertEqual(p.js("document.querySelectorAll('.asat, .asat-wrap, .asat-box, .asat-note').length"), 0, "no As at element")
                self.assertEqual(len(b["dates"]), 1, f"one date in the header, the week ending: {b['dates']}")
                self.assertIn("23-10-2026", b["dates"][0])
                p.js("document.querySelector('#client-menu-btn').click()")
                p.until("!!document.querySelector('[role=menu]')", "the menu opened")
                self.assertNotRegex(p.js("document.querySelector('[role=menu]').textContent"), r"(?i)as at", "no As at in the profile menu")

    def test_published_header_switcher_and_profile_sizes(self):
        for width, dark in CASES:
            with self.subTest(width=width, dark=dark):
                b = self.bar(width, dark).js(BAR)
                self.assertEqual((b["theme"]["w"], b["theme"]["h"]), (32, 32), "the light and dark switcher")
                self.assertEqual((b["badge"]["w"], b["badge"]["h"]), (32, 32), "the profile circle")

    def test_published_header_no_edit_controls(self):
        for width, dark in CASES:
            with self.subTest(width=width, dark=dark):
                b = self.bar(width, dark).js(BAR)
                bad = [c for c in b["controls"] if re.search(r"ask clark|client visible|eye|edit|publish|rename|asat", c)]
                self.assertEqual(bad, [], f"no ask clark, edit control, Client visible or eye in the header: {b['controls']}")
                self.assertTrue(any("client-menu-btn" in c for c in b["controls"]), "the profile circle is there")


if __name__ == "__main__":
    unittest.main()
