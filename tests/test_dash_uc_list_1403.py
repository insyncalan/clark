"""Row 1403: the Dashboard Use cases list as the prototype draws it (Classic, 1400 px, light): no column heading row, the row grid, hover and ID badge, the commitment pill.

Run: python3 dev/run_tests.py test_dash_uc_list_1403
Chrome required. Values are computed styles in Chrome at 1400; the prototype is the Classic prototype index.html lines 160-169 (the grid line 162,
hover 163, ID badge 165, chip 169). Cards (no Theme layer) keeps the shared rules: CardsKeepsShared pins them. 900 px is not built (NINE lines in the report).
"""
import unittest

from clark import page, theme
from _demo import USER
from _real_server import real_server
import _testpage as testpage
from test_report_editor import Base, Pg, tearDownModule  # noqa: F401
from test_server import chrome
from test_use_cases_list import plant

READ = """(() => {
  const q = (s, r) => (r || document).querySelector(s), cs = (e) => getComputedStyle(e);
  const bar = q('.uc .ucrow .ucbar'), ref = q('.uc .ucref'), chip = q('.uc .cchip:not(.cc-committed)'), heads = q('.uc .ucheads');
  const kids = [...bar.children].filter((c) => cs(c).display !== 'contents').concat([...bar.querySelectorAll('.uctitle, .uchead')]);
  const box = (e) => { const r = e.getBoundingClientRect(); return [Math.round(r.left - bar.getBoundingClientRect().left), Math.round(r.width)]; };
  const b = cs(bar), r = cs(ref), c = chip && cs(chip);
  return { heads: heads ? [cs(heads).display, heads.getBoundingClientRect().height] : null,
    cols: b.gridTemplateColumns, gap: [b.columnGap, b.rowGap], pad: [b.paddingTop, b.paddingRight, b.paddingBottom, b.paddingLeft], minH: b.minHeight,
    title: box(q('.uctitle', bar)), head: box(q('.uchead', bar)), status: box(q('[data-uccol=status]', bar)), commit: box(q('[data-uccol=commit]', bar)), steps: box(q('[data-uccol=steps]', bar)),
    statusTop: Math.round(q('[data-uccol=status]', bar).getBoundingClientRect().top), commitTop: Math.round(q('[data-uccol=commit]', bar).getBoundingClientRect().top),
    ref: [r.borderTopWidth, r.borderTopStyle, r.borderTopColor, r.paddingTop, r.paddingRight, r.fontWeight],
    chip: c && [c.borderTopWidth, c.borderTopColor, c.borderTopLeftRadius, c.color, c.fontWeight, c.lineHeight], chipShown: !!chip,
    root: [cs(document.documentElement).getPropertyValue('--band-bg').trim(), cs(document.documentElement).getPropertyValue('--grey-500').trim(), cs(document.documentElement).getPropertyValue('--grey-200').trim()] }; })()"""


class Dash:
    css = None

    def setUp(self):
        super().setUp()
        plant(self)
        with self.store.step("dashboard", USER) as st:
            st.update("use_cases", self.uc1, {"commitment": "Planned 2026"})
        self.s.close()
        html = testpage.html()
        if self.css:
            html = page.layer_theme(html, self.css)
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: html, seam=self.seam)
        self.addCleanup(self.s.close)

    def open_page(self, cdp, width=1400):
        p = Pg.at(self, cdp, self.s.port, "#dashboard&p=ABC")
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.until("document.querySelectorAll('.uc .ucrow .ucbar').length > 0", "the Use cases list drew")
        return p

    def measure(self):
        with chrome() as cdp:
            return self.open_page(cdp).js(READ)


class Classic(Dash, Base):
    css = theme.css("prototype-2.0")

    def test_row1_no_column_heading_row(self):
        """Spec row 1: the prototype draws no heading row (index.html:160-163); built on main a 14px capitals row."""
        g = self.measure()
        self.assertEqual(g["heads"], ["none", 0], f"the heading row is not drawn: {g['heads']}")

    def test_row2_the_row_grid(self):
        """Spec row 2: minmax(52px,max-content) 1fr 1.5fr 132px 112px, gap 12, padding 9px 8px (index.html:162)."""
        g = self.measure()
        cols = [float(c[:-2]) for c in g["cols"].split()]
        self.assertEqual(len(cols), 5, g["cols"])
        self.assertEqual(cols[3:], [132.0, 112.0], f"status 132 and next steps 112: {g['cols']}")
        self.assertAlmostEqual(cols[2] / cols[1], 1.5, delta=0.02, msg=f"the headline column is 1.5 times the title column: {g['cols']}")
        self.assertLess(cols[0], 64, f"the ref column is as wide as its badge, not 64: {g['cols']}")
        self.assertEqual(g["gap"][0], "12px", g["gap"])
        self.assertEqual(g["pad"], ["9px", "8px", "9px", "8px"], "padding 9px 8px")
        self.assertEqual(g["minH"], "0px", "no minimum row height")
        self.assertEqual([g["title"][1], g["head"][1]], [round(cols[1]), round(cols[2])], "title and headline sit in their own columns")
        self.assertEqual(g["status"][0], g["commit"][0], "the commitment sits in the status column")
        self.assertGreater(g["commitTop"], g["statusTop"], "and under the status word")

    def test_row3_hover_and_id_badge(self):
        """Spec row 3: hover the band tint F3F5FB; badge 1px outline in 8794B3, padding 1px 8px, weight 400 (index.html:163,165)."""
        g = self.measure()
        self.assertEqual(g["ref"], ["1px", "solid", "rgb(135, 148, 179)", "1px", "8px", "400"], f"badge: {g['ref']}")
        with chrome() as cdp:
            p = self.open_page(cdp)
            x, y = p.js("(() => { const r = document.querySelector('.uc .ucrow .ucbar').getBoundingClientRect(); return [r.left + 400, r.top + r.height / 2]; })()")
            cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 0, "y": 0}, p.sid)
            rest = p.js("getComputedStyle(document.querySelector('.uc .ucrow .ucbar')).backgroundColor")
            cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, p.sid)
            p.until("document.querySelector('.uc .ucrow .ucbar').matches(':hover')", "the pointer is over the row")
            hov = p.js("getComputedStyle(document.querySelector('.uc .ucrow .ucbar')).backgroundColor")
        self.assertNotEqual(rest, hov, "hover changes the row")
        self.assertEqual(hov, "rgb(243, 245, 251)", f"hover is F3F5FB: {hov}")

    def test_row4_the_commitment_pill(self):
        """Spec row 4: pill radius 999, 1px D9E0EF, muted, 400, line height 18 (index.html:169)."""
        g = self.measure()
        self.assertTrue(g["chipShown"], "a use case has a commitment chip")
        self.assertEqual(g["chip"], ["1px", "rgb(217, 224, 239)", "999px", "rgb(71, 85, 119)", "400", "18px"], f"chip: {g['chip']}")


class ChipStyles(Dash, Base):
    css = theme.css("prototype-2.0")
    WANT = ["solid", "1px", "rgb(217, 224, 239)", "999px", "400", "rgba(0, 0, 0, 0)"]
    PROBE = "(() => { const c = getComputedStyle(document.querySelector('.uc .cchip')); return [c.borderTopStyle, c.borderTopWidth, c.borderTopColor, c.borderTopLeftRadius, c.fontWeight, c.backgroundColor, c.color]; })()"

    def read_all(self, width, dark=False):
        got = {}
        with chrome() as cdp:
            p = self.open_page(cdp, width)
            if dark:
                p.js("document.documentElement.setAttribute('data-theme', 'dark')")
            for k in ("cc-committed", "cc-planned-2026", "cc-planned-2027"):
                p.js("document.querySelector('.uc .cchip').className = 'cchip %s'" % k)
                got[k] = p.js(self.PROBE)
        return got

    def test_committed_planned_2026_and_planned_2027_are_one_solid_muted_pill_at_1400_and_900(self):
        """Committed, Planned 2026 and Planned 2027 are solid 1px D9E0EF, pill 999, weight 400, no fill, muted text (light)."""
        for w in (1400, 900):
            got = self.read_all(w)
            for k, g in got.items():
                self.assertEqual(g[:6], self.WANT, f"{w} {k}: {g}")
                self.assertEqual(g[6], "rgb(71, 85, 119)", f"{w} {k} colour: {g}")

    def test_the_same_in_the_dark_theme(self):
        """In the dark theme all three have the same line, radius, weight and no fill (the shell dark fill on Committed is gone)."""
        for w in (1400, 900):
            got = self.read_all(w, dark=True)
            for k, g in got.items():
                self.assertEqual([g[0], g[1], g[3], g[4], g[5]], ["solid", "1px", "999px", "400", "rgba(0, 0, 0, 0)"], f"dark {w} {k}: {g}")
            self.assertEqual(len({tuple(g) for g in got.values()}), 1, f"dark {w}: the three differ: {got}")


class CardsKeepsShared(Dash, Base):
    """Cards (no Theme layer) keeps the shared rules: the heading row is drawn, the badge is 600 (grey-300 outline) and the chip radius 4."""
    def test_cards_as_on_main(self):
        g = self.measure()
        self.assertNotEqual(g["heads"][0], "none", g["heads"])
        self.assertEqual(g["ref"][5], "600", g["ref"])
        self.assertEqual(g["chip"][2], "4px", g["chip"])
        self.assertEqual(g["cols"].count("px"), 5, g["cols"])
        self.assertEqual(g["cols"].split()[0], "64px", g["cols"])


if __name__ == "__main__":
    unittest.main()
