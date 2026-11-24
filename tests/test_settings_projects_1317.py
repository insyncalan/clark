"""Row 1317 DoD6-9 (AP6, AP7, AP8, AP9): the Projects th and td spec at 1400 and 900, and the Settings h1 and th/td parity at 900, on the REAL Settings page (Classic, demo data, fictional), light and dark, as Chrome computes it.
AP8: the Settings h1 is 30px, weight 600 at 900 as at 1400. AP9: the Projects th and td values at 900 equal those at 1400, and no media rule sets them.

Run: python3 dev/run_tests.py test_settings_projects_1317
While test_server.PAUSED_900 is set the 900 half is skipped; run with it switched off to see it pass."""
import time
import unittest

import test_theme_classic_1317 as t13
from test_theme_classic_1317 import NAME, page_target, for_url, wait, FIXED_DATE
from test_server import Running, chrome  # noqa: F401  the browser harness, named so the browser tier reads this file as a browser test

PROBE = """(() => { const q = (s) => document.querySelector(s), g = (e, p) => getComputedStyle(e)[p];
  const th = q('#projects-table thead th'), td = q('#projects-table tbody td'), h1 = [...document.querySelectorAll('h1')].filter((e) => !e.classList.contains('hdr-h1'))[0];
  const cell = (e) => ['fontSize', 'fontWeight', 'color', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'borderBottomWidth', 'borderBottomStyle', 'borderBottomColor'].map((p) => g(e, p)).join('|');
  const props = ['font-weight', 'color', 'padding', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left', 'border-bottom', 'border-bottom-width', 'border-bottom-style', 'border-bottom-color'];
  const media = [];
  const walk = (rules, inMedia) => { for (const r of rules) { if (r.cssRules) walk(r.cssRules, inMedia || r.constructor.name === 'CSSMediaRule'); else if (inMedia && r.selectorText && /proj-table/.test(r.selectorText) && /\\b(th|td)\\b/.test(r.selectorText) && props.some((p) => r.style.getPropertyValue(p))) media.push(r.selectorText); } };
  for (const sh of document.styleSheets) { try { walk(sh.cssRules, false); } catch (e) {} }
  const line = (v) => { const e = document.createElement('i'); e.style.borderBottom = '1px solid var(' + v + ')'; document.body.appendChild(e); const c = g(e, 'borderBottomColor'); e.remove(); return c; };
  const rd = (e) => ({ w: g(e, 'fontWeight'), pad: [g(e, 'paddingTop'), g(e, 'paddingRight'), g(e, 'paddingBottom'), g(e, 'paddingLeft')].join(' '), bw: g(e, 'borderBottomWidth'), bs: g(e, 'borderBottomStyle'), bc: g(e, 'borderBottomColor') });
  return { grey200: line('--grey-200'), lineSoft: line('--line-soft'), thR: rd(th), tdR: rd(td), h1: h1 ? [g(h1, 'fontSize'), g(h1, 'fontWeight')] : null, th: cell(th), td: cell(td), media: media }; })()"""


class Settings900(t13.RealSettings):
    test_classic_settings_sidebar_cards_table_and_add_project = test_classic_projects_code_cell_stays_on_one_line = None
    test_classic_projects_table_never_breaks_a_word_in_the_middle = test_cards_keeps_its_own_settings_look = test_the_cards_page_is_byte_for_byte_what_it_was = None

    def look(self, cdp, port, width, scheme):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
        cdp.call("Page.navigate", {"url": "about:blank"}, sid)
        cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{port}/#settings&p=TUL")}, sid)
        self.assertTrue(wait(lambda: bool(cdp.js("!!document.querySelector('#projects-table tbody tr') && !!document.querySelector('h1')", sid)), 30), "timed out waiting for Settings")
        time.sleep(0.3)
        return cdp.js(PROBE, sid)

    def test_th_spec_at_1400_and_900(self):
        for tag, c in self.each(NAME):
            t = c["thR"]
            self.assertEqual((t["w"], t["pad"]), ("600", "6px 10px 6px 0px"), tag + ": th weight 600, padding 6px 10px 6px 0")
            self.assertEqual((t["bw"], t["bs"], t["bc"]), ("1px", "solid", c["grey200"]), tag + ": th border-bottom 1px var(--grey-200) (rules.css:893; the ticket's var(--line) is undefined in Classic)")

    def test_td_spec_at_1400_and_900(self):
        for tag, c in self.each(NAME):
            t = c["tdR"]
            self.assertEqual(t["pad"], "8px 10px 8px 0px", tag + ": td padding 8px 10px 8px 0")
            self.assertEqual((t["bw"], t["bs"], t["bc"]), ("1px", "solid", c["lineSoft"]), tag + ": td border-bottom 1px var(--line-soft)")

    def test_settings_h1_30px_at_900(self):
        for tag, c in self.each(NAME):
            self.assertEqual(c["h1"], ["30px", "600"], tag + ": the Settings h1 is 30px, weight 600")

    def test_th_td_same_at_900(self):
        got = {tag: c for tag, c in self.each(NAME)}
        for scheme in ("light", "dark"):
            a, b = got[f"{NAME} {scheme} 1400"], got[f"{NAME} {scheme} 900"]
            self.assertEqual(b["th"], a["th"], scheme + ": th values at 900 equal those at 1400")
            self.assertEqual(b["td"], a["td"], scheme + ": td values at 900 equal those at 1400")
            self.assertEqual(b["media"], [], scheme + ": no media rule sets the Projects th/td font-weight, colour, padding or bottom border")


class RulesCssTh(unittest.TestCase):
    """Row 1583: the dead weight 700 on the Projects th is gone from rules.css (rules-2.css sets 600)."""

    def test_rules_css_th_rule_has_no_font_weight_700(self):
        import pathlib
        css = (pathlib.Path(__file__).resolve().parent.parent / "src" / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")
        rules = [ln for ln in css.splitlines() if ln.startswith(".projects table.proj-table th {")]
        self.assertEqual(len(rules), 1, "one th rule in rules.css")
        self.assertNotIn("font-weight", rules[0])
        self.assertIn("text-transform: none", rules[0])
        self.assertIn("border-top: 0", rules[0])


if __name__ == "__main__":
    unittest.main()
