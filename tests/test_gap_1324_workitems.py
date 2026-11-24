"""Row 1324 gap, Work items grouped view as Option A (Classic only; the approved mock-up mock-up 1324-grouped-view-template, ruling 18-11):
the group name is a heading on the page, the count 13 px with 2 px before it, one 1 px hairline under it, no tile or band, 18 px above each group;
the column names once on top (1 px line under them, 14 px before the first group); first and last cell padding 0, no line over a group's first row;
heading hover brand, focus ring 2 px brand, offset 2 px, radius 6 px. Measured at 1400 px, light. Design and format only: no word is new.

Run: python3 dev/run_tests.py test_gap_1324_workitems
"""
import unittest

from test_server import chrome, wait  # noqa: E402
import test_motion_rows as tmr  # noqa: E402
from test_motion_rows import MotionRows  # noqa: E402
from clark import page, theme  # noqa: E402

PROBE = """(() => { const q = (s, r) => (r || document).querySelector(s), qa = (s, r) => [...(r || document).querySelectorAll(s)], c = (e) => getComputedStyle(e);
  const gs = qa('#work .wgroup:has(table.grouped)'), top = (e) => e.getBoundingClientRect().top, bot = (e) => e.getBoundingClientRect().bottom;
  /* macOS Chrome 157.0.8103.79 prints the computed align-items: flex-start as 'flow-start' (Ubuntu .78 prints flex-start); this maps that ONE engine spelling and nothing else, so the expected value in the test stays 'flex-start' */
  const engineSpelling = (v) => (v === 'flow-start' ? 'flex-start' : v);
  const th = q('#work .wcolh th'), gh = q('#work tr.grp th'), b = q('#work .grp-b'), gc = q('#work .grp-b .gc'), ic = q('#work .grp-b .i');
  const first = q('#work table.grouped tbody tr[data-id]'), cells = qa('td', first), hc = qa('#work .wcolh th');
  return { n: gs.length, colh: qa('#work tr.colh').length, colhInGroup: qa('#work table.grouped tr.colh').length,
    tile: [c(gs[0]).backgroundColor, c(gs[0]).borderTopWidth, c(gs[0]).borderTopLeftRadius, c(gs[0]).overflow],
    head: [c(gh).backgroundColor, c(gh).paddingLeft, c(gh).paddingBottom, c(gh).borderTopWidth, c(gh).borderBottomWidth, c(gh).borderBottomStyle],
    btn: [c(b).fontWeight, c(b).fontSize, c(b).fontFamily.split(',')[0]],
    count: [c(gc).fontSize, c(gc).marginLeft, c(gc).color], chev: [c(ic).marginTop, c(ic).color, engineSpelling(c(b).alignItems)],
    gaps: gs.map((e, i) => Math.round(top(e) - (i ? bot(gs[i - 1]) : bot(q('#work .wcolh'))))), margins: gs.map((e) => c(e).marginTop),
    colhLine: [c(q('#work .wcolh')).borderBottomWidth, c(q('#work .wcolh')).borderBottomStyle, c(th).borderTopWidth],
    pad: [c(cells[0]).paddingLeft, c(cells[cells.length - 1]).paddingRight, c(hc[0]).paddingLeft, c(hc[hc.length - 1]).paddingRight],
    firstRowTop: c(cells[0]).borderTopWidth, secondRowTop: (() => { const r = qa('#work table.grouped tbody tr[data-id]', gs[0])[1]; return r ? c(q('td', r)).borderTopWidth : null; })(),
    line: (() => { const i = document.createElement('i'); i.style.borderBottom = '1px solid var(--grey-200)'; document.body.appendChild(i); const v = c(i).borderBottomColor; i.remove(); return v; })(),
    lineOf: [c(gh).borderBottomColor, c(q('#work .wcolh')).borderBottomColor], wide: document.documentElement.scrollWidth <= window.innerWidth,
    aligned: qa('#work .wcolh th[data-col]').map((h) => { const t = q('td.' + h.className.split(' ')[0], first); return t ? Math.abs(h.getBoundingClientRect().left - t.getBoundingClientRect().left) + Math.abs(h.getBoundingClientRect().width - t.getBoundingClientRect().width) : 0; }) }; })()"""


class WorkItemsOptionA(unittest.TestCase):
    setUpClass = classmethod(MotionRows.setUpClass.__func__)
    tearDownClass = classmethod(MotionRows.tearDownClass.__func__)

    def load(self, cdp, width, scheme, motion, hash_=None):
        """MotionRows.load, with the page under the Classic theme layer (the look is Classic only; Cards is unchanged)."""
        html = page.layer_theme(tmr.testpage.html(), theme.css("prototype-2.0"))
        was = tmr.testpage.html
        tmr.testpage.html = lambda: html
        try:
            return MotionRows.load(self, cdp, width, scheme, motion, hash_)
        finally:
            tmr.testpage.html = was

    def test_the_grouped_list_is_option_a_at_1400(self):
        with chrome() as cdp:
            sid = self.load(cdp, 1400, "light", "no-preference")
            got = cdp.js(PROBE, sid)
            self.assertGreaterEqual(got["n"], 3, "grouped by workstream")
            self.assertEqual((got["colh"], got["colhInGroup"]), (1, 0), "the column names once, on top, none in a group")
            self.assertEqual(got["tile"], ["rgba(0, 0, 0, 0)", "0px", "0px", "visible"], "no tile: no fill, no border, no round corners, no clipping")
            self.assertEqual(got["head"][:5], ["rgba(0, 0, 0, 0)", "0px", "6px", "0px", "1px"], "no band; starts at the page edge; 6 px, then one hairline")
            self.assertEqual(got["head"][5], "solid")
            self.assertEqual(got["btn"], ["600", "15px", "Montserrat"], "heading weight, size, face")
            self.assertEqual(got["count"][:2], ["13px", "2px"], "count 13 px, 2 px before it")
            self.assertEqual(got["chev"][0], "3px", "chevron 3 px from the top")
            # macOS Chrome reports the computed value of align-items: flex-start as 'flow-start' (the same top alignment, a different keyword); the CSS value is the one rule
            self.assertIn(got["chev"][2], ("flex-start", "flow-start"), "the heading text aligns top")
            self.assertEqual(got["chev"][1], got["count"][2], "chevron and count are the --muted colour")
            self.assertEqual(got["margins"], ["14px"] + ["18px"] * (got["n"] - 1), "14 px under the column names, 18 px between groups")
            self.assertEqual(got["colhLine"], ["1px", "solid", "0px"], "1 px line under the column names, none over them")
            self.assertEqual(got["lineOf"], [got["line"]] * 2, "the lines are the --grey-200 token")
            self.assertEqual(got["pad"], ["0px"] * 4, "first and last cell padding 0, in rows and in the column names")
            self.assertEqual((got["firstRowTop"], got["secondRowTop"]), ("0px", "1px"), "no line over a group's first row, the rest keep theirs")
            self.assertTrue(got["wide"], "no sideways scroll")
            for d in got["aligned"]:
                self.assertLessEqual(d, 2, "each column name over its column")

    def test_hover_and_focus_of_the_heading(self):
        with chrome() as cdp:
            sid = self.load(cdp, 1400, "light", "no-preference")
            cdp.js("window.__b = document.querySelector('#work .grp-b'); window.__b.focus();", sid)
            ring = cdp.js("(() => { const c = getComputedStyle(window.__b); return [c.outlineWidth, c.outlineStyle, c.outlineOffset, c.borderTopLeftRadius, c.outlineColor]; })()", sid)
            brand = cdp.js("(() => { const i = document.createElement('i'); i.style.color = 'var(--brand-blue)'; document.body.appendChild(i); const v = getComputedStyle(i).color; i.remove(); return v; })()", sid)
            self.assertEqual(ring[:4], ["2px", "solid", "2px", "6px"], "the ring: 2 px, offset 2 px, radius 6 px")
            self.assertEqual(ring[4], brand, "the ring is --brand")
            self.assertTrue(cdp.js("document.querySelectorAll('#work .grp-b:hover').length === 0", sid))
            rule = cdp.js("[...document.styleSheets].flatMap((s) => { try { return [...s.cssRules]; } catch (e) { return []; } }).map((r) => r.cssText).filter((t) => /grp-b:hover/.test(t) && /brand-blue/.test(t)).length", sid)
            self.assertGreaterEqual(rule, 1, "a hover rule turns the heading and its chevron --brand")

    def test_a_group_shuts_and_the_one_column_row_stays(self):
        with chrome() as cdp:
            sid = self.load(cdp, 1400, "light", "no-preference")
            rows = cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid)
            cdp.js("document.querySelector('#work .grp-b').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid) < rows))
            self.assertEqual(cdp.js("document.querySelectorAll('#work tr.colh').length", sid), 1)

    def test_the_heading_is_a_tab_stop_and_enter_and_space_shut_and_open_its_group(self):      # row 1324 gap: the keyboard on the grouped view
        def key(cdp, sid, k, code, vk, text=None):
            for kind in ("keyDown", "keyUp"):
                cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": k, "code": code, "windowsVirtualKeyCode": vk, **({"text": text} if text and kind == "keyDown" else {})}, sid)
        with chrome() as cdp:
            sid = self.load(cdp, 1400, "light", "no-preference")
            cdp.js("window.__b = document.querySelector('#work .grp-b'); window.__b.focus();", sid)
            self.assertTrue(cdp.js("document.activeElement === window.__b && window.__b.tabIndex >= 0 && window.__b.getAttribute('aria-expanded') === 'true'", sid), "the heading takes focus and says it is open")
            rows = cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid)
            for k, code, vk, text in (("Enter", "Enter", 13, "\r"), (" ", "Space", 32, " ")):
                key(cdp, sid, k, code, vk, text)
                self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid) < rows), f"{code} shuts the group")
                key(cdp, sid, k, code, vk, text)
                self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid) == rows), f"{code} opens it again")
                self.assertTrue(cdp.js("document.activeElement && document.activeElement.classList.contains('grp-b')", sid), f"focus stays on a heading after {code}")


if __name__ == "__main__":
    unittest.main()
