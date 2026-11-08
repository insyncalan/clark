"""Spacing (item 1025, PR 4): Milestones (the list) and Use cases follow the density. Run: python3 dev/run_tests.py test_spacing_milestones_usecases

In the stylesheet: the milestone list, its row and detail toggle, and the use-case strip, row bar and detail take their gaps from --d-*
tokens, each defined once for Compact (the standard and the fallback) and once for Comfortable. In a real browser at 1400 and 900 px:
Compact computes exactly the values the page had (a list 14 px down, a row 2 px above and below (Milestones tighter, item 1020), a use-case strip 10 px), Comfortable is
looser for each, an unknown or missing word is Compact, and the type size does not move. The timeline is placed by dates, so its
geometry is not density-driven. Chrome is required: the browser tests fail, never skip, without it.
"""
import re
import time
import unittest

from _paths import SRC
from test_publish_dialog import Base
from test_server import chrome

CSS = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")

TOKENS = ["--d-msl-top", "--d-msl-y", "--d-msl-det-y", "--d-uc-strip-b", "--d-uc-bar-y", "--d-uc-detail-b"]
RULES = {".msl {": ["--d-msl-top"], ".msl-cells {": ["--d-msl-y"], ".msl-bar {": ["--d-msl-det-y"], ".ucstrip {": ["--d-uc-strip-b"],
         ".ucbar {": ["--d-uc-bar-y"], ".ucdetail {": ["--d-uc-detail-b"]}
PROBE = """(() => { try { const mk = (cls, tag) => { const e = document.createElement(tag || 'div'); e.className = cls; document.body.appendChild(e); return e; };
  const px = (e, k) => parseFloat(getComputedStyle(e)[k]); const l = mk('msl', 'ul'); const c = mk('msl-cells'); const s = mk('ucstrip'); const d = mk('ucdetail');
  const out = {list: px(l, 'marginTop'), cell: [px(c, 'paddingTop'), px(c, 'paddingBottom')], strip: px(s, 'paddingBottom'), detail: px(d, 'paddingBottom'), size: getComputedStyle(s).fontSize};
  [l, c, s, d].forEach(e => e.remove()); return out; } catch (e) { return String(e); } })()"""


def rule(selector):
    m = re.search(r"^" + re.escape(selector) + r"[^\n]*", CSS, re.M)
    assert m, selector
    return m.group(0)


class Sheet(unittest.TestCase):
    def test_the_rules_read_the_tokens(self):
        for sel, names in RULES.items():
            for n in names:
                self.assertIn(f"var({n})", rule(sel), f"{sel} should use {n}")

    def test_each_token_is_defined_once_per_density(self):
        compact = re.search(r"^:root \{ --d-row-y[^\n]*", CSS, re.M).group(0)
        comfy = re.search(r'^html\[data-density="comfortable"\] \{[^\n]*--d-row-y[^\n]*', CSS, re.M).group(0)
        for n in TOKENS:
            self.assertEqual(len(re.findall(re.escape(n) + ":", compact)), 1, n)
            self.assertEqual(len(re.findall(re.escape(n) + ":", comfy)), 1, n)


class Browser(Base):
    def measure(self, width, word):
        with chrome() as cdp:
            p = self.page(cdp)
            p.width(width)
            p.js(f"localStorage.setItem('clark.density', {word!r})" if word else "localStorage.removeItem('clark.density')")
            p.js("location.reload()")
            time.sleep(1.5)
            p.until("document.readyState === 'complete' && !!document.body && !!document.querySelector('main')", "the page drew")
            got = p.js(PROBE)
            self.assertIsInstance(got, dict, got)
            return got

    def test_compact_is_what_the_page_had_and_comfortable_is_looser(self):
        for w in (1400, 900):
            with self.subTest(width=w):
                c = self.measure(w, "compact")
                self.assertEqual((c["list"], c["cell"], c["strip"]), (14, [2, 2], 10))
                f = self.measure(w, "comfortable")
                self.assertGreater(f["list"], c["list"])
                self.assertGreater(f["cell"][0], c["cell"][0])
                self.assertGreater(f["strip"], c["strip"])
                self.assertGreater(f["detail"], c["detail"])
                self.assertEqual(f["size"], c["size"], "type size does not change with the density")

    def test_a_missing_or_unknown_word_is_compact(self):
        base = self.measure(1400, "compact")
        self.assertEqual(self.measure(1400, None), base)
        self.assertEqual(self.measure(1400, "roomy"), base)


if __name__ == "__main__":
    unittest.main()
