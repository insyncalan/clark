"""Spacing (item 1025, PR 7): the Settings cards and the Help pages follow the density. Run: python3 dev/run_tests.py test_spacing_settings_help

In the stylesheet: the Settings cards (card padding, the gap between cards, the button row and the label-and-control rows) and the Help page
(tabs, sections, hero, loop, the card grids and the job links) take their gaps from --d-set-* and --d-hp-* tokens, each defined once for Compact
(the standard and the fallback) and once for Comfortable. In a real browser at 1400 and 900 px: Compact computes the values the page had,
Comfortable is looser for each, an unknown or missing word is Compact, and the type size does not move. Chrome is required: the browser tests
fail, never skip, without it.
"""
import re
import unittest

from _new_page import reload_to_new_page
from _paths import SRC
from test_publish_dialog import Base
from test_server import chrome

CSS = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")

TOKENS = ["--d-set-gap", "--d-set-card-y", "--d-set-row", "--d-set-fld", "--d-hp-sec", "--d-hp-tabs", "--d-hp-hero-y", "--d-hp-loop-y",
          "--d-hp-card-y", "--d-hp-job-y", "--d-hp-grid"]
RULES = {".setting { margin-top:": ["--d-set-gap"], ".set-cards .frame {": ["--d-set-card-y"], ".setting .row {": ["--d-set-row"],
         ".set-cards .fld, .set-cards .fld.copy-fld {": ["--d-set-fld"], ".hp-tabs {": ["--d-hp-tabs"], ".hp-sec {": ["--d-hp-sec"],
         ".hp-hero {": ["--d-hp-hero-y"], ".hp-loop {": ["--d-hp-loop-y"], ".hp-first li, .hp-where-g li, .hp-rules li {": ["--d-hp-card-y"],
         ".hp-job {": ["--d-hp-job-y"], ".hp-first {": ["--d-hp-grid"], ".hp-jobs {": ["--d-hp-grid"], ".hp-where-g {": ["--d-hp-grid"],
         ".hp-rules {": ["--d-hp-grid"]}
PROBE = """(() => { try { const mk = (cls, tag, parent) => { const e = document.createElement(tag || 'div'); e.className = cls; (parent || document.body).appendChild(e); return e; };
  const px = (e, k) => parseFloat(getComputedStyle(e)[k]); const made = [];
  const cards = mk('set-cards'); made.push(cards); mk('x', 'div', cards); const set = mk('setting', 'section', cards); const card = mk('frame', 'div', cards);
  const row = mk('row', 'div', set); const fld = mk('fld', 'div', cards);
  const sec = mk('hp-sec', 'section'); const tabs = mk('hp-tabs'); const hero = mk('hp-hero'); const loop = mk('hp-loop');
  const first = mk('hp-first', 'ol'); const li = mk('x', 'li', first); const jobs = mk('hp-jobs', 'ul'); const job = mk('hp-job', 'a', jobs);
  const rules = mk('hp-rules', 'ul'); rules.appendChild(document.createElement('li')); rules.appendChild(document.createElement('li'));
  made.push(sec, tabs, hero, loop, first, jobs, rules);
  const out = {set: px(set, 'marginTop'), card: px(card, 'paddingTop'), row: px(row, 'marginTop'), fld: px(fld, 'marginBottom'),
    sec: px(sec, 'marginTop'), tabs: px(tabs, 'marginBottom'), hero: px(hero, 'paddingTop'), loop: px(loop, 'paddingTop'),
    cell: px(li, 'paddingTop'), job: px(job, 'paddingTop'), grid: px(rules, 'rowGap'), size: getComputedStyle(hero).fontSize};
  made.forEach(e => e.remove()); return out; } catch (e) { return String(e); } })()"""
KEYS = ("set", "card", "row", "fld", "sec", "tabs", "hero", "loop", "cell", "job", "grid")


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
            reload_to_new_page(p.js, "!!document.body && !!document.querySelector('main')", "the page reloaded")
            p.until("document.readyState === 'complete' && !!document.body && !!document.querySelector('main')", "the page drew")
            got = p.js(PROBE)
            self.assertIsInstance(got, dict, got)
            return got

    def test_compact_is_what_the_page_had_and_comfortable_is_looser(self):
        for w in (1400, 900):
            with self.subTest(width=w):
                c = self.measure(w, "compact")
                self.assertEqual(tuple(c[k] for k in KEYS), (12, 16, 8, 12, 34, 22, 26, 20, 14, 16, 12))
                f = self.measure(w, "comfortable")
                for k in KEYS:
                    self.assertGreater(f[k], c[k], k)
                self.assertEqual(f["size"], c["size"], "type size does not change with the density")

    def test_a_missing_or_unknown_word_is_compact(self):
        base = self.measure(1400, "compact")
        self.assertEqual(self.measure(1400, None), base)
        self.assertEqual(self.measure(1400, "roomy"), base)


if __name__ == "__main__":
    unittest.main()
