"""Row 1403: the Dashboard Use cases list as the prototype draws it (Classic, 1400 px, light): no column heading row, the row grid, hover and ID badge, the commitment pill.

Run: python3 dev/run_tests.py test_dash_uc_list_1403
Chrome required. Values are computed styles in Chrome at 1400; the prototype is the Classic prototype index.html lines 160-169 (the grid line 162,
hover 163, ID badge 165, chip 169). Cards (no Theme layer) keeps the shared rules: CardsKeepsShared pins them. The Edit heading row is pinned at 1400 and 900 in test_edit_keeps_its_heading_row (the 900 case runs while test_server.PAUSED_900 is None, and is skipped if it is set).
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


    def test_edit_keeps_its_heading_row(self):
        """Row 1 hides the heading row in View only: Edit keeps .ucheads-ed drawn, with a height, and each label starts over its control column (1400 and 900)."""
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.open_page(cdp, width)
                self.assertEqual(p.js("getComputedStyle(document.querySelector('.uc .ucheads')).display"), "none", "View: no heading row")
                p.js("document.querySelector('[data-mode=edit]').click()")
                p.until("!!document.querySelector('.uc .ucheads-ed') && !!document.querySelector('.uc .ucrow-ed .ucbar [data-uccol=steps]')", "Edit drew its heading row and rows")
                p.until("document.getAnimations().length === 0", "the animations to end before anything is measured")
                g = p.js("""(() => { const h = document.querySelector('.uc .ucheads-ed'), cs = getComputedStyle(h), r = h.getBoundingClientRect();
                  const kids = [...h.children].filter((c) => c.textContent.trim()), hb = kids.map((c) => c.getBoundingClientRect());
                  const row = document.querySelector('.uc .ucrow-ed').getBoundingClientRect();
                  const left = (e) => e.getBoundingClientRect().left, cols = ["ref", "title", "status", "commit", "steps"];
                  return { display: cs.display, height: r.height, labels: kids.length, texts: kids.map((c) => c.textContent.trim()), above: r.bottom <= row.top + 1,
                    inside: hb.every((b) => b.left >= r.left - 1 && b.right <= r.right + 1 && b.width > 0),
                    heads: kids.map((c) => left(c)), ctrls: cols.map((c) => left(document.querySelector('.uc .ucrow-ed .ucbar [data-uccol=' + c + ']'))) }; })()""")
                self.assertNotEqual(g["display"], "none", f"Edit heading row is drawn: {g}")
                self.assertGreater(g["height"], 0, f"Edit heading row has a height: {g}")
                self.assertEqual(g["labels"], 5, f"Edit heading row has its five labels: {g}")
                self.assertEqual(g["texts"], ["Ref", "Use case", "Status", "Commitment", "Next steps"], f"Edit heading labels and their order: {g}")
                self.assertTrue(g["inside"], f"labels sit inside the row: {g}")
                self.assertTrue(g["above"], f"the heading row is above the first Edit row: {g}")
                for i, (h, c) in enumerate(zip(g["heads"], g["ctrls"])):
                    self.assertAlmostEqual(h, c, delta=2, msg=f"label {i} starts over its control column: {g}")


class ChipStyles(Dash, Base):
    css = theme.css("prototype-2.0")
    WANT = ["solid", "1px", "rgb(217, 224, 239)", "999px", "400", "rgba(0, 0, 0, 0)", "18px"]
    PROBE = "(() => { const c = getComputedStyle(document.querySelector('.uc .cchip')); return [c.borderTopStyle, c.borderTopWidth, c.borderTopColor, c.borderTopLeftRadius, c.fontWeight, c.backgroundColor, c.lineHeight, c.color]; })()"
    # the muted token resolved to rgb by the page itself, and the contrast of the chip text against the first opaque background behind it
    TOKEN = """(() => { const p = document.createElement('i'); p.style.color = 'var(--text-muted)'; document.body.appendChild(p); const t = getComputedStyle(p).color; p.remove(); return t; })()"""
    CONTRAST = """(() => {
      const lum = (c) => { const m = c.match(/[\\d.]+/g).map(Number); return [0, 1, 2].map((i) => { const v = m[i] / 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }).reduce((a, v, i) => a + v * [0.2126, 0.7152, 0.0722][i], 0); };
      const chip = document.querySelector('.uc .cchip'); let e = chip, bg = 'rgba(0, 0, 0, 0)';
      while (e && /rgba\\(.*, 0\\)$/.test(bg)) { bg = getComputedStyle(e).backgroundColor; e = e.parentElement; }
      const a = lum(getComputedStyle(chip).color), b = lum(bg);
      return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05); })()"""

    def read_all(self, width, dark=False):
        got = {}
        with chrome() as cdp:
            p = self.open_page(cdp, width)
            if dark:
                p.js("document.documentElement.setAttribute('data-theme', 'dark')")
            self.token = p.js(self.TOKEN)
            for k in ("cc-committed", "cc-planned-2026", "cc-planned-2027"):
                p.js("document.querySelector('.uc .cchip').className = 'cchip %s'" % k)
                got[k] = p.js(self.PROBE)
                self.contrast = getattr(self, "contrast", {})
                self.contrast[k] = p.js(self.CONTRAST)
        return got

    def read_edit(self, width, dark=False):
        with chrome() as cdp:
            p = self.open_page(cdp, width)
            p.js("document.querySelector('[data-mode=edit]').click()")
            p.until("!!document.querySelector('.uc .ucrow-ed .cchip')", "Edit rows drew a chip")
            p.until("document.getAnimations().length === 0", "the animations to end")
            if dark:
                p.js("document.documentElement.setAttribute('data-theme', 'dark')")
            line = p.js(self.TOKEN.replace("--text-muted", "--grey-200").replace("style.color", "style.borderColor").replace("getComputedStyle(p).color", "getComputedStyle(p).borderTopColor"))
            return p.js(self.PROBE), p.js(self.TOKEN), line

    def test_committed_planned_2026_and_planned_2027_are_one_solid_muted_pill_at_1400_and_900(self):
        """Committed, Planned 2026 and Planned 2027 are solid 1px D9E0EF, pill 999, weight 400, no fill, muted text (light)."""
        for w in (1400, 900):
            got = self.read_all(w)
            for k, g in got.items():
                self.assertEqual(g[:7], self.WANT, f"{w} {k}: {g}")
                self.assertEqual(g[7], "rgb(71, 85, 119)", f"{w} {k} colour: {g}")

    def test_the_same_in_the_dark_theme(self):
        """In the dark theme all three have the same line, radius, weight and no fill (the shell dark fill on Committed is gone)."""
        for w in (1400, 900):
            got = self.read_all(w, dark=True)
            for k, g in got.items():
                self.assertEqual([g[0], g[1], g[3], g[4], g[5]], ["solid", "1px", "999px", "400", "rgba(0, 0, 0, 0)"], f"dark {w} {k}: {g}")
            self.assertEqual(len({tuple(g) for g in got.values()}), 1, f"dark {w}: the three differ: {got}")

    def test_dark_text_is_the_muted_token_and_reads_at_4_5(self):
        """In dark the chip text is the page's own --text-muted value (read from the page) and contrast against the background behind it is at least 4.5."""
        light = self.read_all(1400)["cc-committed"][7]
        for w in (1400, 900):
            got = self.read_all(w, dark=True)
            self.assertNotEqual(self.token, light, "the dark token differs from light, so the dark theme is really on")
            for k, g in got.items():
                self.assertEqual(g[7], self.token, f"dark {w} {k}: colour {g[7]} is not --text-muted {self.token}")
                self.assertGreaterEqual(self.contrast[k], 4.5, f"dark {w} {k}: contrast {self.contrast[k]}")

    def test_the_edit_rows_chip_is_the_same_pill_light_and_dark(self):
        """The commitment chip in an Edit row is measured like View: solid, 1px, 999, 400, 18px line, no fill, muted text."""
        for dark in (False, True):
            for w in (1400, 900):
                g, token, line = self.read_edit(w, dark)
                want = list(self.WANT)
                want[2] = line   # the line is the --grey-200 token: D9E0EF in light, the page's own dark value in dark
                if not dark:
                    self.assertEqual(line, "rgb(217, 224, 239)")
                self.assertEqual(g[:7], want, f"edit {w} dark={dark}: {g}")
                self.assertEqual(g[7], token, f"edit {w} dark={dark}: colour is not --text-muted {token}")


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
