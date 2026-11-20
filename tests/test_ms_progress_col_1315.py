"""Row 1315 part B: the Milestones list's Progress column in the Classic theme (prototype 2.0): a bar on a light track and a bold percent,
read only from the milestone's stored percent_complete (0 to 100); a milestone with none keeps its existing words "Progress not set".
Cards is untouched. Chrome at 1400 and 900, light and dark; every number is computed in the page.

Run: python3 -m unittest test_ms_progress_col_1315      (from tests/, with PYTHONPATH=../src:../vendor:.; needs Chrome)
"""
import json
import re
import unittest
from pathlib import Path

from _demo import USER
from _paths import ROOT
from _publish import PublishedFile
from test_glance_page import Setup
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

# The heading row's own grid (the saved-width rule is left out on purpose: the test shows the Classic default steps aside), taken from the Edit stylesheet (a published file does not carry Edit's CSS).
_EDIT = (Path(__file__).resolve().parent.parent / "src" / "clark" / "page" / "src" / "edit" / "edit.css").read_text(encoding="utf-8")
EDIT_RULE = "@media (min-width: 1201px) {" + "\n".join(l for l in _EDIT.splitlines() if re.match(r"\s*\.msl-hc \{ grid-template-columns: minmax\(240px", l)) + "}"
PROBE = r"""(() => {
  const rgb = (s) => s.match(/[\d.]+/g).slice(0, 4).map(Number);
  const lin = (c) => { c /= 255; return c <= .03928 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4; };
  const lum = (c) => .2126 * lin(c[0]) + .7152 * lin(c[1]) + .0722 * lin(c[2]);
  const bg = (el) => { for (let e = el; e; e = e.parentElement) { const c = rgb(getComputedStyle(e).backgroundColor); if (c.length < 4 || c[3] > 0) return c; } return [255, 255, 255]; };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };
  const tok = (v) => { const t = document.createElement('i'); t.style.color = 'var(' + v + ')'; document.body.appendChild(t); const c = getComputedStyle(t).color; t.remove(); return c; };
  const heading = tok('--heading'), muted = tok('--muted');
  return [...document.querySelectorAll('.msl-row')].map((row) => {
    const p = row.querySelector('.msl-prog'), bar = p.querySelector('.pbar'), n = p.querySelector('.num'), cr = row.querySelector('.msl-cells').getBoundingClientRect();
    const pb = p.getBoundingClientRect();
    const fill = bar && bar.querySelector('i');
    return {name: row.querySelector('.msl-name').textContent.trim(), text: p.textContent.trim(), hasBar: !!bar,
      barW: bar ? bar.getBoundingClientRect().width : 0, barH: bar ? bar.getBoundingClientRect().height : 0,
      fillW: fill ? fill.getBoundingClientRect().width : 0, fillBg: fill ? getComputedStyle(fill).backgroundColor : "",
      trackBg: bar ? getComputedStyle(bar).backgroundColor : "",
      numColor: n ? getComputedStyle(n).color : "", heading, muted,
      weight: n ? getComputedStyle(n).fontWeight : "", tab: n ? getComputedStyle(n).fontVariantNumeric : "", numAlign: n ? getComputedStyle(n).textAlign : "", numW: n ? n.getBoundingClientRect().width : 0,
      contrast: n ? ratio(rgb(getComputedStyle(n).color), bg(n)) : 0, inRow: pb.left >= cr.left - 1 && pb.right <= cr.right + 1,
      right: cr.right - pb.right, ok: p.scrollWidth <= p.clientWidth + 1};
  });
})()"""


class Look(PublishedFile, Setup):
    theme = None

    def setUp(self):
        super().setUp()
        self.store.con.execute("UPDATE app_settings SET theme = 'classic' WHERE id = 1")
        self.store.con.commit()
        with self.store.step("dashboard", USER) as st:
            for i, pct in enumerate((100, 60, 40, 20, 10, None)):
                row = {"project": "ABC", "name": f"Probe {i}", "baseline_date": f"2026-12-{10 + i}", "forecast_date": f"2026-12-{10 + i}", "client_visible": 1, "source": "demo", "sort_order": 90 + i}
                if pct is not None:
                    row["percent_complete"] = pct
                st.create("milestones", row)

    def heads(self, width, saved=False):
        path = self.publish()
        with chrome() as cdp:
            p = self.draw(cdp, path, width)
            p.until("!!document.querySelector('.top-file .tab')", "the bar drew")
            p.js("[...document.querySelectorAll('.top-file .tab')].find(t => /Milestones/.test(t.textContent)).click()")
            p.until("!!document.querySelector('.msl-row')", "the list drew")
            p.js("(() => { const b = document.querySelector('.msl-all'); if (b && /^Show all/.test(b.textContent)) b.click(); })()")
            p.until("document.querySelectorAll('.msl-row').length >= 7", "all rows shown")
            # a published file has no heading row: draw one the way Edit does, from the same classes, to see its tracks
            p.js("(() => { const sh = new CSSStyleSheet(); sh.replaceSync(%s); document.adoptedStyleSheets = [...document.adoptedStyleSheets, sh]; })()" % json.dumps(EDIT_RULE))
            p.js("""(() => { const box = document.querySelector('.msl-box'); if (%s) box.setAttribute('style', '--msl-cols: 400px 300px 150px 90px; --msl-cols-w: 400px 300px 150px 90px');
              const hc = document.createElement('div'); hc.className = 'msl-hc'; hc.style.display = 'grid'; hc.innerHTML = '<span>a</span><span>b</span><span>c</span><span id="hp">d</span>';
              const ul = box.querySelector('.msl-row').parentNode; ul.parentNode.insertBefore(hc, ul); })()""" % ("true" if saved else "false"))
            res = p.js(PROBE)
            more = p.js("""(() => { const t = (e) => getComputedStyle(e).gridTemplateColumns;
              return {cells: t(document.querySelector('.msl-cells')), head: t(document.querySelector('.msl-hc')), classicDefault: document.querySelector('.msl-cells').matches('.msl-box[data-place="page"]:not([style*="--msl-cols:"]) .msl-cells')}; })()""")
            return dict(more, rows=[r for r in res if r["hasBar"]])

    def rows(self, width, dark):
        path = self.publish()
        with chrome() as cdp:
            p = self.draw(cdp, path, width, dark=dark)
            p.until("!!document.querySelector('.top-file .tab')", "the bar drew")
            p.js("[...document.querySelectorAll('.top-file .tab')].find(t => /Milestones/.test(t.textContent)).click()")
            p.until("!!document.querySelector('.msl-row')", "the list drew")
            p.js("(() => { const b = document.querySelector('.msl-all'); if (b && /^Show all/.test(b.textContent)) b.click(); })()")
            p.until("document.querySelectorAll('.msl-row').length >= 7", "all rows shown")
            return p.js(PROBE)

    def test_the_bar_and_percent_come_from_the_stored_number_in_classic(self):
        for w in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=w, dark=dark):
                    got = {r["name"]: r for r in self.rows(w, dark)}
                    for name, pct in (("Probe 0", 100), ("Probe 1", 60), ("Probe 2", 40), ("Probe 3", 20), ("Probe 4", 10)):
                        r = got[name]
                        self.assertEqual(r["text"], f"Progress {pct}%")
                        self.assertTrue(r["hasBar"])
                        self.assertAlmostEqual(r["fillW"] / r["barW"], pct / 100, delta=.01, msg=name)
                        self.assertEqual(r["barH"], 6)
                        self.assertEqual(r["weight"], "600", "the percent is 600 (row 1396 ruling)")
                        self.assertEqual(r["numAlign"], "right")
                        self.assertEqual(r["tab"], "tabular-nums")
                        self.assertEqual(r["numColor"], r["heading"], "the percent is the heading colour (row 1315)")
                        self.assertNotEqual(r["heading"], r["muted"], "the probe can tell the heading colour from the muted one")
                        self.assertGreaterEqual(r["numW"], 4 * 7, "the number cell keeps room for 100%")
                        self.assertGreaterEqual(r["contrast"], 4.5, f"{name} contrast")
                        self.assertTrue(r["inRow"] and r["ok"])
                        self.assertEqual(r["fillBg"], "rgb(143, 123, 255)" if dark else "rgb(91, 71, 216)", "the fill is --brand-blue")
                    bars = {round(got[n]["barW"], 1) for n in ("Probe 0", "Probe 1", "Probe 4")}
                    self.assertEqual(len(bars), 1, f"every bar is the same length, whatever the percent ({bars})")
                    self.assertEqual(got["Probe 5"]["text"], "Progress not set")
                    self.assertFalse(got["Probe 5"]["hasBar"], "no number, no bar")

    def test_the_bar_is_145px_at_1400_and_the_heading_row_lines_up(self):
        got = self.heads(1400)
        for r in got["rows"]:
            self.assertAlmostEqual(r["barW"], 145, delta=2, msg=r["name"])
        self.assertTrue(got["rows"])
        self.assertEqual(got["head"].split()[2:], got["cells"].split()[2:], "Edit's heading row takes the same State and Progress tracks as the cells")
        self.assertEqual(got["cells"].split()[3], "197px")
        self.assertEqual(self.heads(1100)["cells"].split()[3], "130px", "below 1201 px the column is as it was")
        self.assertEqual(len(got["cells"].split()), 4)

    def test_a_saved_width_wins(self):
        """Edit stores a chosen width as --msl-cols on the box and its own rule (edit.css, same attribute test) sets the grid from it.
        The Classic default must not match then: checked by the browser's own selector matching, saved and not saved."""
        for saved in (False, True):
            got = self.heads(1400, saved=saved)
            last = got["cells"].split()[3]
            self.assertEqual(last, "130px" if saved else "197px", f"saved={saved}: the Classic default track applies only with no saved width ({got['cells']})")
            if not saved:
                self.assertEqual(got["cells"].split()[2], "150px")
        self.assertIn('.msl-box[style*="--msl-cols:"] .msl-cells', _EDIT, "Edit's saved-width rule uses the same attribute test")

    @unittest.skip("Cards is unmaintained (row 1363): a stored Cards value now publishes and renders Classic")
    def test_cards_keeps_the_list_as_it_was(self):
        self.store.con.execute("UPDATE app_settings SET theme = 'cards' WHERE id = 1")
        self.store.con.commit()
        got = {r["name"]: r for r in self.rows(1400, False)}
        self.assertEqual(got["Probe 1"]["weight"], "400")
        self.assertEqual(got["Probe 1"]["numAlign"], "start")


class ProgressRulesPinned(unittest.TestCase):
    def test_the_progress_block_is_exact(self):
        # this part's block, from its Row comment to the next Row comment (not the last N lines)
        rules = (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")
        start = rules.index("/* Row 1315, progress part")
        got = [l for l in rules[start:].split("\n/* Row ", 2)[0].split("\n") if l.strip()]
        self.assertEqual(got, [
            '/* Row 1315, progress part (Classic only): the Milestones list Progress bar is 145px with a right-aligned percent at weight 600. */',
            '.msl-box[data-place="page"] .msl-prog .num { min-width: 36px; width: 2.75rem; flex: none; text-align: right; font-weight: var(--weight-medium); font-variant-numeric: tabular-nums; color: var(--heading); }      /* min-width 36px is the ticket value (prototype); it is inert beside the fixed 2.75rem slot, which keeps every bar the same length */',
            '@media (min-width: 1201px) { .msl-box[data-place="page"]:not([style*="--msl-cols:"]) :is(.msl-cells, .msl-hc) { grid-template-columns: minmax(240px, 17rem) minmax(160px, 1fr) 150px calc(145px + var(--space-2) + 2.75rem); } }',
        ])
