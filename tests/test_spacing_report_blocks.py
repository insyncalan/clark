"""Spacing (item 1025, PR 6): the report blocks follow the density. Run: python3 dev/run_tests.py test_spacing_report_blocks

In the stylesheet: the callout, contact cards (and their grid gap), table cells, dates rows and checklist rows take their gaps from --d-blk-*
tokens, each defined once for Compact (the standard and the fallback) and once for Comfortable. In a real browser at 1400 and 900 px:
Compact computes the values the page had, Comfortable is looser for each, an unknown or missing word is Compact, and the type size does not
move. Chrome is required: the browser tests fail, never skip, without it.
"""
import re
import time
import unittest

from _paths import SRC
from test_publish_dialog import Base
from test_server import chrome

CSS = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")

TOKENS = ["--d-blk-callout-y", "--d-blk-contact", "--d-blk-contacts-gap", "--d-blk-cell-y", "--d-blk-date-y", "--d-blk-check-y"]
RULES = {".tpl-callout {": ["--d-blk-callout-y"], ".tpl-contacts {": ["--d-blk-contacts-gap"], ".tpl-contact {": ["--d-blk-contact"],
         ".tpl-table th, .tpl-table td {": ["--d-blk-cell-y"], ".tpl-dates-row {": ["--d-blk-date-y"], ".tpl-check-row {": ["--d-blk-check-y"]}
PROBE = """(() => { try { const mk = (cls, tag) => { const e = document.createElement(tag || 'div'); e.className = cls; document.body.appendChild(e); return e; };
  const px = (e, k) => parseFloat(getComputedStyle(e)[k]); const a = mk('tpl-callout'); const c = mk('tpl-contact'); const g = mk('tpl-contacts', 'ul');
  g.appendChild(document.createElement('li')); g.appendChild(document.createElement('li'));
  const t = document.createElement('table'); t.className = 'tpl-table'; t.innerHTML = '<tbody><tr><td>x</td></tr></tbody>'; document.body.appendChild(t);
  const d = mk('tpl-dates-row'); const k = mk('tpl-check-row');
  const out = {callout: px(a, 'paddingTop'), contact: px(c, 'paddingTop'), gap: px(g, 'rowGap'), cell: px(t.querySelector('td'), 'paddingTop'),
    date: px(d, 'paddingTop'), check: px(k, 'paddingTop'), size: getComputedStyle(t).fontSize};
  [a, c, g, t, d, k].forEach(e => e.remove()); return out; } catch (e) { return String(e); } })()"""


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
                self.assertEqual((c["callout"], c["contact"], c["gap"], c["cell"], c["date"], c["check"]), (12, 12, 12, 8, 8, 6))
                f = self.measure(w, "comfortable")
                for k in ("callout", "contact", "gap", "cell", "date", "check"):
                    self.assertGreater(f[k], c[k], k)
                self.assertEqual(f["size"], c["size"], "type size does not change with the density")

    def test_a_missing_or_unknown_word_is_compact(self):
        base = self.measure(1400, "compact")
        self.assertEqual(self.measure(1400, None), base)
        self.assertEqual(self.measure(1400, "roomy"), base)


if __name__ == "__main__":
    unittest.main()
