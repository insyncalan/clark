"""Spacing (item 1025, PR 5): the peek and the dialogs follow the density. Run: python3 dev/run_tests.py test_spacing_peek_dialogs

In the stylesheet: the peek's bar, title, field rows and property cards, and the dialog's form, option list, options and button row take
their gaps from --d-* tokens, each defined once for Compact (the standard and the fallback) and once for Comfortable. In a real browser
at 1400 and 900 px: Compact computes the values the page had, Comfortable is looser for each, an unknown or missing word is Compact, and
the type size and the 32 px peek buttons do not move. Chrome is required: the browser tests fail, never skip, without it.
"""
import re
import unittest

from _new_page import reload_to_new_page
from _paths import SRC
from test_publish_dialog import Base
from test_server import chrome

CSS = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")

TOKENS = ["--d-pk-bar-b", "--d-pk-title-t", "--d-pk-title-b", "--d-pk-row-y", "--d-pk-card", "--d-pk-card-gap",
          "--d-dlg-y", "--d-dlg-narrow", "--d-dlg-opts", "--d-dlg-opt-y", "--d-dlg-foot"]
RULES = {".pk-bar {": ["--d-pk-bar-b"], ".pk-title {": ["--d-pk-title-t", "--d-pk-title-b"], ".pk-row {": ["--d-pk-row-y"],
         ".pk-fields > .pk-row[data-row] {": ["--d-pk-card", "--d-pk-card-gap"], ".dlg-form {": ["--d-dlg-y"],
         ".pubopts, .pub-clash {": ["--d-dlg-opts"], ".pubopt {": ["--d-dlg-opt-y"], ".dlg-f {": ["--d-dlg-foot"]}
PROBE = """(() => { try { const mk = (cls, tag) => { const e = document.createElement(tag || 'div'); e.className = cls; document.body.appendChild(e); return e; };
  const px = (e, k) => parseFloat(getComputedStyle(e)[k]); const b = mk('pk-bar'); const t = mk('pk-title', 'h2'); const r = mk('pk-row'); const f = mk('dlg-form');
  const o = mk('pubopt'); const d = mk('dlg-f'); const w = mk('pkp-btn', 'button');
  const out = {bar: px(b, 'paddingBottom'), title: [px(t, 'marginTop'), px(t, 'marginBottom')], row: px(r, 'paddingTop'), form: px(f, 'paddingTop'),
    opt: px(o, 'paddingTop'), foot: px(d, 'marginTop'), size: getComputedStyle(t).fontSize, btn: [px(w, 'width'), px(w, 'height')]};
  [b, t, r, f, o, d, w].forEach(e => e.remove()); return out; } catch (e) { return String(e); } })()"""


def rule(selector):
    m = re.search(r"^" + re.escape(selector) + r"[^\n]*", CSS, re.M)
    assert m, selector
    return m.group(0)


class Sheet(unittest.TestCase):
    def test_the_rules_read_the_tokens(self):
        for sel, names in RULES.items():
            for n in names:
                self.assertIn(f"var({n})", rule(sel), f"{sel} should use {n}")

    def test_the_narrow_dialog_form_reads_its_token(self):
        self.assertRegex(CSS, r"@media \(max-width: 900px\) \{[^\n]*\.dlg-form \{ padding: var\(--d-dlg-narrow\); \}")

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
            reload_to_new_page(p.js, "!!document.body && !!document.querySelector('main')", "the page reloaded")
            p.until("document.readyState === 'complete' && !!document.body && !!document.querySelector('main')", "the page drew")
            got = p.js(PROBE)
            self.assertIsInstance(got, dict, got)
            return got

    def test_compact_is_what_the_page_had_and_comfortable_is_looser(self):
        for w in (1400, 900):
            with self.subTest(width=w):
                c = self.measure(w, "compact")
                self.assertEqual((c["bar"], c["title"], c["row"], c["opt"], c["foot"]), (10, [16, 12], 8, 8, 16))
                f = self.measure(w, "comfortable")
                self.assertGreater(f["bar"], c["bar"])
                self.assertGreater(f["title"][0], c["title"][0])
                self.assertGreater(f["row"], c["row"])
                self.assertGreater(f["form"], c["form"])
                self.assertGreater(f["opt"], c["opt"])
                self.assertGreater(f["foot"], c["foot"])
                self.assertEqual(f["size"], c["size"], "type size does not change with the density")
                self.assertEqual(f["btn"], c["btn"], "the peek buttons keep their size")

    def test_a_missing_or_unknown_word_is_compact(self):
        base = self.measure(1400, "compact")
        self.assertEqual(self.measure(1400, None), base)
        self.assertEqual(self.measure(1400, "roomy"), base)


if __name__ == "__main__":
    unittest.main()
