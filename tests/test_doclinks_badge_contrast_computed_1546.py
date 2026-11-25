"""Row 1546 AP7: in the browser, the text on every drawn badge is white on its fill and reaches 4.5:1 (the editor's drawn page icon and the published tile), light and dark, 1400 and 900.
Split from test_doclinks_badge_contrast.py (the static contrast tables) so that file stays out of the browser tier: the tier test files a test by whether its text opens the browser."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_tpl_doclinks as T
from test_server import chrome


class ComputedContrast(T.ClassicPage):
    """Row 1546 AP7: in the browser, the text on every drawn badge is white on its fill and reaches 4.5:1 (the editor's drawn page icon and the published tile), light and dark, 1400 and 900."""
    add = T.InThePage.add
    JS = ("""(() => { const num = c => c.match(/[0-9.]+/g).slice(0, 3).map(Number); const L = c => { const [r, g, b] = num(c).map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
        const R = (a, b) => { const [hi, lo] = [L(a), L(b)].sort((x, y) => y - x); return (hi + 0.05) / (lo + 0.05); };
        return [...document.querySelectorAll('.tpl-dl-i .tpl-badge')].map(el => { const s = el.querySelector('svg'); let fg, bg;
          if (!s) { const c = getComputedStyle(el); fg = c.color; bg = c.backgroundColor; }
          else if (el.classList.contains('tpl-mail')) { fg = getComputedStyle(s.querySelector('text')).fill; bg = getComputedStyle(s.querySelector('circle')).fill; }
          else { fg = getComputedStyle(s.querySelector('text')).fill; bg = getComputedStyle([...s.querySelectorAll('path')].pop()).fill; }
          return [el.textContent, fg, R(fg, bg)]; }); })()""")
    ITEMS = [("pdf", "Plan.pdf"), ("docx", "Scope.docx"), ("xlsx", "Budget.xlsx"), ("pptx", "Deck.pptx"), ("jpg", "Site.jpg"), ("png", "Map.png"), ("txt", "Notes.txt")]

    def check(self, p, where):
        got = p.js(self.JS)
        self.assertEqual({g[0] for g in got} >= {"PDF", "DOC", "XLS", "PPT", "JPG", "PNG", "TXT", "URL"}, True, (where, got))
        for label, fg, r in got:
            self.assertEqual(fg.replace(" ", ""), "rgb(255,255,255)", (where, label))
            self.assertGreaterEqual(r, 4.5, "%s %s %.2f:1" % (where, label, r))

    def test_the_badge_computed_contrast_all_kinds_light_dark_1400_900(self):
        ref = self.add([T.a_file(name, 2048) for _, name in self.ITEMS] + [T.a_link("https://example.org/x", "A page"), T.a_link("mailto:team@example.org", "Team")])
        for width, dark in ((1400, False), (900, True), (900, False), (1400, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.visit(cdp)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                if dark:
                    p.js("document.documentElement.dataset.theme = 'dark'")
                p.until(f"document.querySelectorAll('[data-id={json.dumps(ref)}] .tpl-dl-i').length === 9", "the list drew")
                self.check(p, "editor %d %s" % (width, dark))


if __name__ == "__main__":
    unittest.main()
