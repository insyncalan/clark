"""Row 1316 (Table and Status cell) in the Classic Theme, as Chrome computes it at 1400 and 900 px, light and dark; the same elements under Cards.

Run: python3 dev/run_tests.py test_theme_classic_1316b
Fails, never skips, without Chrome. Sizes are by eye (+/-2 px): the prototype files are not on the box that built this.
Cards is the page without the <style id="theme"> block, so the Cards page is byte for byte what it was.
"""
import re
import tempfile
import time
import unittest
from pathlib import Path

from _paths import ROOT  # noqa: F401
from test_server import chrome

from clark import page

NAME = "prototype-2.0"
SIZES = (1400, 900)
ROWS = """<div id="t" class="ucl-box"><div class="ucl-cols"><span class="ucl-c1">Use case</span><span>Where it stands</span><span>Status</span><span>Next steps</span><span></span></div>
<ul class="ucl-list"><li class="ucl-row"><span class="ucl-ref"></span><button class="ucl-go">Alpha</button><span class="ucl-head">Head</span>
<span class="ucl-st ucstc"><span class="pill g">On track</span><span class="cchip cc-committed">Committed</span></span>
<span class="ucl-steps ucsteps some"><b class="ucn-b">2</b> next steps</span><button class="ucl-eye"></button></li>
<li class="ucl-row"><span class="ucl-ref"></span><button class="ucl-go">Beta</button><span class="ucl-head">Head</span>
<span class="ucl-st ucstc"><span class="pill a">Watch</span><span class="cchip cc-planned-2026">Planned 2026</span></span>
<span class="ucl-steps ucsteps some"><b class="ucn-b">1</b> next step</span><button class="ucl-eye"></button></li></ul></div>"""
PROBE = """(() => { const q = (s) => document.querySelector(s), g = (e, p) => getComputedStyle(e)[p];
  const probe = document.createElement('i'); document.body.appendChild(probe);
  const col = (v) => { probe.style.color = 'var(' + v + ')'; return g(probe, 'color'); };
  const box = q('#t'), cols = q('.ucl-cols'), row = q('.ucl-row'), chip = q('.cchip.cc-committed'), plan = q('.cchip.cc-planned-2026'), pill = q('.pill');
  const r = (e) => e.getBoundingClientRect();
  /* macOS Chrome 157.0.8103.79 prints the computed align-items: flex-start as 'flow-start' (Ubuntu .78 prints flex-start); this maps that ONE engine spelling and nothing else, so the expected value in the test stays 'flex column flex-start 3px' */
  const engineSpelling = (v) => (v === 'flow-start' ? 'flex-start' : v);
  return { boxBorder: g(box, 'borderTopWidth'), boxBorderColor: g(box, 'borderTopColor'), line: col('--line-soft'), boxRadius: g(box, 'borderTopLeftRadius'), boxOverflow: g(box, 'overflow'),
    colsBg: g(cols, 'backgroundColor'), grey50: col('--grey-50'), colsCase: g(cols, 'textTransform'), colsSize: g(cols, 'fontSize'), colsColor: g(cols, 'color'), muted: col('--text-muted'),
    colsPadL: g(cols, 'paddingLeft'), rowPadL: g(row, 'paddingLeft'),
    chipRadius: g(chip, 'borderTopLeftRadius'), chipBg: g(chip, 'backgroundColor'), chipStyle: g(plan, 'borderTopStyle'), chipStyleC: g(chip, 'borderTopStyle'), planBg: g(plan, 'backgroundColor'), chipColor: g(chip, 'color'),
    chipBelow: r(chip).top >= r(pill).bottom - 0.5, chipLeft: Math.abs(r(chip).left - r(pill).left) < 1,
    boxBg: g(box, 'backgroundColor'), surface: col('--surface'), colsBorderB: g(cols, 'borderBottomWidth') + ' ' + g(cols, 'borderBottomColor'), lineB: '1px ' + col('--line-soft'),
    colsWeight: g(cols, 'fontWeight'), colsTrack: g(cols, 'letterSpacing'), colsPadT: g(cols, 'paddingTop'), rowPadR: g(row, 'paddingRight'),
    st: [g(q('.ucl-st'), 'display'), g(q('.ucl-st'), 'flexDirection'), engineSpelling(g(q('.ucl-st'), 'alignItems')), g(q('.ucl-st'), 'rowGap')].join(' '),
    chipPad: g(chip, 'paddingTop') + ' ' + g(chip, 'paddingLeft'), chipBorderW: g(chip, 'borderTopWidth'), chipBorderC: g(chip, 'borderTopColor'), grey300: col('--grey-300'), chipSize: g(chip, 'fontSize'), chipWeight: g(chip, 'fontWeight'),
    fits: document.documentElement.scrollWidth <= window.innerWidth }; })()"""


def html_of(theme):
    return page.page_html(branding=page.NO_BRAND, theme=theme)


class Cards(unittest.TestCase):
    def test_cards_is_the_classic_page_without_its_theme_block_and_has_none_of_the_new_rules(self):
        classic, cards = html_of(NAME), html_of(None)
        self.assertEqual(re.sub(r'<style id="theme">.*?</style>\n', "", classic, count=1, flags=re.S), cards)
        self.assertNotIn("Row 1316", cards)
        self.assertNotIn("#usecases .ucl-box .ucl-cols", cards)


class Computed(unittest.TestCase):
    def load(self, cdp, theme, width, scheme):
        path = Path(tempfile.mkdtemp(prefix="clark-test-")) / "p.html"
        path.write_text(html_of(theme), encoding="utf-8")
        self.addCleanup(lambda: (path.unlink(), path.parent.rmdir()))
        tid = cdp.call("Target.createTarget", {"url": "about:blank"})["targetId"]
        sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
        end = time.monotonic() + 20
        while cdp.js("document.readyState", sid) != "complete" and time.monotonic() < end:
            time.sleep(0.05)
        cdp.js("(() => { document.documentElement.setAttribute('data-theme', %r); const d = document.createElement('div'); d.id = 'usecases'; d.innerHTML = %r; document.body.appendChild(d); })()" % (scheme, ROWS), sid)
        return cdp.js(PROBE, sid)

    def test_classic_table_and_status_cell(self):
        with chrome() as cdp:
            for scheme in ("light", "dark"):
                for w in SIZES:
                    tag = f"classic {scheme} {w}"
                    c = self.load(cdp, NAME, w, scheme)
                    self.assertEqual(c["boxBorder"], "1px", tag)
                    self.assertEqual(c["boxBorderColor"], c["line"], tag)
                    self.assertEqual(c["boxRadius"], "8px", tag)
                    self.assertEqual(c["boxOverflow"], "hidden", tag)
                    self.assertEqual(c["colsBg"], c["grey50"], tag)
                    self.assertEqual(c["colsCase"], "uppercase", tag)
                    self.assertEqual(c["colsSize"], "13px", tag)
                    self.assertEqual(c["colsColor"], c["muted"], tag)
                    self.assertEqual(c["colsPadL"], "16px", tag)
                    self.assertEqual(c["rowPadL"], "16px", tag)
                    self.assertEqual(c["chipRadius"], "999px", tag)
                    self.assertEqual(c["chipBg"], "rgba(0, 0, 0, 0)", tag)
                    self.assertEqual(c["planBg"], "rgba(0, 0, 0, 0)", tag)
                    self.assertEqual(c["chipStyle"], "solid", tag)
                    self.assertEqual(c["chipStyleC"], "solid", tag)
                    self.assertEqual(c["chipColor"], c["muted"], tag)
                    self.assertTrue(c["chipBelow"] and c["chipLeft"], tag)
                    self.assertEqual(c["boxBg"], c["surface"], tag)
                    self.assertEqual(c["colsBorderB"], c["lineB"], tag)
                    self.assertEqual((c["colsWeight"], c["colsSize"], c["colsPadT"], c["rowPadR"]), ("700", "13px", "10px", "16px"), tag)
                    self.assertNotIn(c["colsTrack"], ("normal", "0px"), tag)
                    self.assertEqual(c["st"], "flex column flex-start 3px", tag)
                    self.assertEqual((c["chipPad"], c["chipBorderW"], c["chipSize"], c["chipWeight"]), ("2px 9px", "1px", "14px", "400"), tag)
                    self.assertEqual(c["chipBorderC"], c["grey300"], tag)
                    self.assertTrue(c["fits"], tag)

    def test_the_same_elements_under_cards_are_as_they_were(self):
        with chrome() as cdp:
            for scheme in ("light", "dark"):
                for w in SIZES:
                    tag = f"cards {scheme} {w}"
                    c = self.load(cdp, None, w, scheme)
                    self.assertEqual(c["boxBorder"], "0px", tag)
                    self.assertEqual(c["boxOverflow"], "visible", tag)
                    self.assertNotEqual(c["colsCase"], "uppercase", tag)
                    self.assertNotEqual(c["colsBg"], c["grey50"], tag)
                    self.assertEqual(c["rowPadL"], "4px", tag)
                    self.assertEqual(c["chipRadius"], "4px", tag)
                    self.assertNotEqual(c["chipBg"], "rgba(0, 0, 0, 0)", tag)       # the dark filled Committed
                    self.assertEqual(c["chipStyle"], "dashed", tag)                 # the dashed Planned 2026


if __name__ == "__main__":
    unittest.main()
