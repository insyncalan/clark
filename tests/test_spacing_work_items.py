"""Spacing (item 1025, PR 3): Work items follow the density. Run: python3 dev/run_tests.py test_spacing_work_items

Two kinds of check. In the stylesheet: the table cells, group headings, filter bar and line, board columns and cards take their gaps and
paddings from the --d-* tokens (no hand-set pixels left in those rules), and every token is defined once for Compact (the standard and the
fallback) and once for Comfortable. In a real browser at 1400 and 900 px: Compact computes exactly the values the page had before this
item (a cell 9 px above and below, a group heading gap of 12 px, a board card 7 px and so on), Comfortable is looser for every one of
them, an unknown or missing density word is Compact, and the type size does not move.
Chrome is required: the browser tests fail, never skip, without it.
"""
import re
import unittest

from _new_page import reload_to_new_page
from _paths import SRC
from test_publish_dialog import Base
from test_server import chrome

CSS = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")

TOKENS = ["--d-row-y", "--d-colh-y", "--d-grp-y", "--d-group-gap", "--d-card-gap", "--d-card-row-y", "--d-bcard-y", "--d-colbody-top",
          "--d-colbody-bottom", "--d-fbar-top", "--d-fbar-gap", "--d-fline-top", "--d-fline-y"]
# the rules that must read the tokens: the start of the rule -> the tokens it uses
RULES = {
    "table.items th {": ["--d-colh-y"], "table.items td {": ["--d-row-y"], ".fbar {": ["--d-fbar-gap", "--d-fbar-top"],
    ".fline-wrap {": ["--d-fline-top"], ".fline {": ["--d-fline-y"], "table.items.grouped tr.grp th {": ["--d-grp-y"],
    ".wgroup {": ["--d-group-gap"], ".lane + .lane {": ["--d-group-gap"], ".cols {": ["--d-group-gap"],
    ".col-body {": ["--d-card-gap", "--d-colbody-top", "--d-colbody-bottom"], ".bcard {": ["--d-bcard-y"],
}
PROBE = """(() => { try { const out = {}; const mk = (tag, cls, parent) => { const e = document.createElement(tag); if (cls) e.className = cls; (parent || document.body).appendChild(e); return e; };
  const t = mk('table', 'items'); const tb = mk('tbody', '', t); const tr = mk('tr', '', tb); const td = mk('td', '', tr); td.textContent = 'x';
  const th = mk('th', '', mk('tr', '', mk('thead', '', t))); th.textContent = 'X';
  const px = (e, k) => parseFloat(getComputedStyle(e)[k]);
  out.row = [px(td, 'paddingTop'), px(td, 'paddingBottom')]; out.colh = px(th, 'paddingTop'); out.size = getComputedStyle(td).fontSize;
  const g = mk('div', 'wgroup'); out.gap = px(g, 'marginBottom'); const c = mk('div', 'bcard'); out.card = px(c, 'paddingTop');
  const b = mk('div', 'fbar'); out.fbar = px(b, 'marginTop'); const w = mk('div', 'fline-wrap'); out.fline = px(w, 'marginTop');
  const body = mk('div', 'col-body'); out.colbody = [px(body, 'paddingTop'), px(body, 'paddingBottom')];
  [t, g, c, b, w, body].forEach(e => e.remove()); return out; } catch (e) { return String(e); } })()"""


def rule(selector):
    m = re.search(r"^" + re.escape(selector) + r"[^\n]*", CSS, re.M)
    assert m, selector
    return m.group(0)


class Sheet(unittest.TestCase):
    def test_the_rules_read_the_tokens(self):
        for sel, names in RULES.items():
            line = rule(sel)
            for n in names:
                self.assertIn(f"var({n})", line, f"{sel} should use {n}")

    def test_each_token_is_defined_once_per_density(self):
        compact = re.search(r"^:root \{ --d-row-y[^\n]*", CSS, re.M).group(0)
        comfy = re.search(r'^html\[data-density="comfortable"\] \{[^\n]*', CSS, re.M).group(0)
        for n in TOKENS:
            self.assertEqual(len(re.findall(re.escape(n) + ":", compact)), 1, n)
            self.assertEqual(len(re.findall(re.escape(n) + ":", comfy)), 1, n)

    def test_the_density_rules_do_not_use_the_old_section_attribute(self):
        self.assertNotIn("data-secstyle", "\n".join(l for l in CSS.splitlines() if "--d-" in l))


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
                self.assertEqual(c["row"], [9, 9])
                self.assertEqual((c["colh"], c["gap"], c["card"], c["fbar"], c["fline"]), (8, 12, 7, 10, 12))
                self.assertEqual(c["colbody"], [10, 14])
                f = self.measure(w, "comfortable")
                self.assertGreater(f["row"][0], c["row"][0])
                for k in ("colh", "gap", "card", "fbar", "fline"):
                    self.assertGreater(f[k], c[k], k)
                self.assertGreater(f["colbody"][0], c["colbody"][0])
                self.assertEqual(f["size"], c["size"], "type size does not change with the density")

    def test_a_missing_or_unknown_word_is_compact(self):
        base = self.measure(1400, "compact")
        self.assertEqual(self.measure(1400, None), base)
        self.assertEqual(self.measure(1400, "roomy"), base)


if __name__ == "__main__":
    unittest.main()
