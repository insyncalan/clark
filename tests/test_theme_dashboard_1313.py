"""Row 1313: the Classic Theme's dashboard style gaps against prototype 2.0 (At a glance strip, section heading, top bar, Milestones switch, narrow bar).

Run: python3 dev/run_tests.py test_theme_dashboard_1313
Two kinds of check. The text of the row 1313 block of rules.css is pinned line by line (a change of the look must change this file too),
and the served page, with the Classic Theme layered, is measured in Chrome at 1400 and 900 px, light and dark. Cards (no Theme) is the
page byte for byte: nothing of the block may reach it. Sizes are the numbers in the issue (the prototype files are not here), so the
page checks are on those numbers, plus 4.5:1 for every text colour the block touches. Fictional data only.
"""
import re
import unittest
from unittest import mock

from _paths import ROOT  # noqa: F401
from test_glance_page import Setup
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome
from _publish import PublishedFile
import _testpage as testpage
from clark import page, theme

NAME = "prototype-2.0"
FOLDER = ROOT / "src" / "clark" / "themes" / NAME
RULES = (FOLDER / "rules.css").read_text(encoding="utf-8")
TOKENS = (FOLDER / "tokens.css").read_text(encoding="utf-8")
MARK = "/* Row 1313 block"
BLOCK = RULES[RULES.index(MARK):].split("\n/* Row ", 1)[0] + "\n"      # from its comment up to the next row comment, so stacked row blocks do not break the pin
LINES = [
    '.glance[data-glance] { gap: 0; }',
    '.glance[data-glance] .fig { border: 0; border-radius: 0; background: none; }',
    '.glance[data-glance] .fig::after { display: none; }',
    '.glance[data-glance] .tcell + .tcell { border-left: 1px solid var(--line-soft); }',
    '.glance[data-glance] .fig .tw { padding: 0; border: 0; }',
    '@media (max-width: 1180px) { .glance[data-glance] .tcell.health + .tcell { border-left: 0; } .glance[data-glance] .tcell.health { border-bottom: 1px solid var(--line-soft); } }',
    '.secs .sec-head::before { font-family: var(--font-head); }',
    '.msv-sw, .mv-txt { gap: 0; padding: 0; border: 1px solid var(--heading); border-radius: var(--radius); overflow: hidden; background: var(--surface); }',
    '.msv-sw .msv-b, .mv-txt button { border-radius: 0; border-bottom: 0; background: var(--surface); color: var(--text); padding: 0 var(--space-3); }',
    '.mv-txt > span { display: none; }',
    '.msv-sw .msv-b + .msv-b, .mv-txt button:not(:first-of-type) { border-left: 1px solid var(--heading); }',
    '.msv-sw .msv-b[aria-current="true"], .mv-txt button[aria-current="true"] { background: var(--heading); color: var(--surface); }',
    'html:has(.top-hdr) :is(.hdr-project, .hdr-project > span) { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }',
    '@media screen { #report.frame.report:not(.asat-frame) { background: transparent; border: 0; box-shadow: none; } }',
    '@media (max-width: 900px) {',
    '  html:has(.top-hdr) { --topbar: 103px; --bar-min: 103px; }',
    '  .top-hdr { display: flex; flex-wrap: nowrap; align-items: center; gap: 12px; padding: 10px 20px; height: 103px; }',
    '  .top-hdr .hdr-id { flex: 1 1 0; }',
    '  .top-hdr .tabs { flex: 0 1 auto; min-width: 0; margin: 0; padding: 0; border-top: 0; align-self: stretch; }',
    '}',
]


class Text(unittest.TestCase):
    def test_the_block_is_exactly_these_lines_after_its_one_comment(self):
        lines = BLOCK.split("\n")
        self.assertTrue(lines[0].startswith(MARK) and lines[0].endswith("*/"), "one comment line opens the block")
        self.assertEqual([l for l in lines[1:] if l.strip()], LINES)
        self.assertEqual(RULES.count(MARK), 1)

    def test_no_colour_is_written_in_the_block_every_colour_is_a_token(self):
        body = "\n".join(BLOCK.split("\n")[1:])
        self.assertIsNone(re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(", body))
        for name in set(re.findall(r"var\((--[a-z0-9-]+)\)", body)):
            self.assertTrue(name in TOKENS or name in (ROOT / "src" / "clark" / "brand" / "tokens.css").read_text(encoding="utf-8")
                            or name in (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8"), name)

    def test_the_block_comment_has_no_hash_digits_and_no_path(self):
        c = BLOCK.split("\n")[0]
        self.assertIsNone(re.search(r"#\d", c))
        self.assertNotIn("/tmp", c)
        self.assertIn("row 1313", c.lower())

    def test_the_block_is_at_the_end_so_rules_above_it_are_not_touched(self):
        self.assertTrue(RULES.endswith("\n"))
        self.assertGreater(RULES.index(MARK), 0)
        self.assertNotIn(MARK, TOKENS)


class Cards(unittest.TestCase):
    def test_cards_has_none_of_the_block(self):
        cards = page.page_html(branding=page.NO_BRAND)
        self.assertNotIn('id="theme"', cards)
        for needle in (".glance[data-glance] .fig::after", "--topbar: 103px", ".msv-sw .msv-b[aria-current", "#report.frame.report:not(.asat-frame)"):
            self.assertNotIn(needle, cards)
        self.assertEqual(cards, page.page_html(branding=page.NO_BRAND, theme="not-a-theme"))
        self.assertEqual(page.page_html(branding=page.NO_BRAND, view=True), page.page_html(branding=page.NO_BRAND, view=True, theme=None))

    def test_classic_is_cards_plus_one_theme_style_that_holds_the_block(self):
        cards = page.page_html(branding=page.NO_BRAND)
        classic = page.page_html(branding=page.NO_BRAND, theme=NAME)
        self.assertEqual(classic.count('id="theme"'), 1)
        css = theme.css(NAME)
        self.assertIn(".glance[data-glance] .tcell + .tcell", css)
        self.assertIn("--topbar: 103px", css)
        self.assertEqual(classic.replace('\n<style id="theme">\n' + css + "\n</style>", "", 1), cards)

    def test_the_shell_does_not_carry_the_block(self):
        shell = (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
        self.assertNotIn("--topbar: 103px", shell)
        self.assertNotIn(".glance[data-glance] .fig::after", shell)


PROBE = """(() => { const q = (s) => document.querySelector(s), qa = (s) => [...document.querySelectorAll(s)], cs = (e, p, ps) => getComputedStyle(e, ps || null)[p];
  const cv = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const rgb = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number);
  const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const ratio = (a, b) => { const x = lum(rgb(a)), y = lum(rgb(b)); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const rgba = (c) => { const m = c.match(/[\\d.]+/g).map(Number); return [m[0], m[1], m[2], m.length > 3 ? m[3] : 1]; };
  const under = (e) => { const layers = []; for (; e; e = e.parentElement) { const c = rgba(cs(e, 'backgroundColor')); if (c[3] > 0) { layers.push(c); if (c[3] >= 1) break; } }
    let acc = [255, 255, 255]; for (const c of layers.reverse()) acc = acc.map((v, i) => i < 3 ? c[i] * c[3] + v * (1 - c[3]) : 1); return 'rgb(' + acc.slice(0, 3).map((v) => Math.round(v)).join(', ') + ')'; };      // translucent layers (a band at .72 white) are composited over what is behind them, from the back, up to the first opaque one
  const R = (e) => e.getBoundingClientRect(), tops = (sel) => qa(sel).map((e) => Math.round(R(e).top)), bar = q('.top-hdr');
  const figs = qa('.glance[data-glance] .fig'), cells = qa('.glance[data-glance] > .tcell');
  const sw = qa('.msv-sw .msv-b'), sc = qa('.mv-txt button'), head = q('.sec-head'), sech = q('.sec-h');
  const seg = (bs) => bs.map((b) => ({cur: b.getAttribute('aria-current'), bg: cs(b, 'backgroundColor'), color: cs(b, 'color'), radius: cs(b, 'borderTopLeftRadius'), left: cs(b, 'borderLeftWidth'), bottom: cs(b, 'borderBottomWidth')}));
  return {
    frame: (() => { const f = q('.frame.report'); return f ? {bg: cs(f, 'backgroundColor'), border: cs(f, 'borderTopWidth') + cs(f, 'borderLeftWidth'), shadow: cs(f, 'boxShadow'), radius: cs(f, 'borderTopLeftRadius')} : null; })(),
    theme: !!q('#theme'), heading: cv('--heading'), g500: cv('--grey-500'), radius: cv('--radius'), scrollW: document.documentElement.scrollWidth, innerW: window.innerWidth,
    figBorders: figs.map((e) => cs(e, 'borderTopWidth') + cs(e, 'borderLeftWidth')), figBg: figs.map((e) => cs(e, 'backgroundColor')), figRadius: figs.map((e) => cs(e, 'borderTopLeftRadius')),
    figAfter: figs.map((e) => cs(e, 'display', '::after')), tw: qa('.glance[data-glance] .fig .tw').map((e) => cs(e, 'borderTopWidth') + cs(e, 'paddingLeft')),
    gap: cs(q('.glance[data-glance]'), 'columnGap') + cs(q('.glance[data-glance]'), 'rowGap'),
    cells: cells.map((e) => ({left: Math.round(R(e).left), top: Math.round(R(e).top), bl: cs(e, 'borderLeftWidth'), bb: cs(e, 'borderBottomWidth'), br: cs(e, 'borderRightWidth'), rline: cs(e, 'borderRightColor'), health: e.classList.contains('health'), line: cs(e, 'borderLeftColor'), style: cs(e, 'borderLeftStyle')})),
    lineSoft: cv('--line-soft'),
    sech: {size: cs(sech, 'fontSize'), weight: cs(sech, 'fontWeight'), family: cs(sech, 'fontFamily'), color: cs(sech, 'color'), ratio: ratio(cs(sech, 'color'), under(sech))},
    num: {size: cs(head, 'fontSize', '::before'), weight: cs(head, 'fontWeight', '::before'), family: cs(head, 'fontFamily', '::before'), color: cs(head, 'color', '::before'), blue: cv('--brand-blue'), ratio: ratio(cs(head, 'color', '::before'), under(head)), content: cs(head, 'content', '::before')},
    narrow: (() => { const root = document.documentElement, t = q('.top-hdr .tabs'), id = q('.top-hdr .hdr-id'); root.style.removeProperty('--topbar'); const token = cv('--topbar'), min = cv('--bar-min'); bar.style.minHeight = '0'; const h = R(bar).height; bar.style.minHeight = '';      // the page's script writes --topbar from the bar's height, so the token is read with that override off, and the declared height with the min-height floor off
      return {token, min, h, ai: cs(bar, 'alignItems'), gap: cs(bar, 'columnGap'), pad: cs(bar, 'paddingTop') + ' ' + cs(bar, 'paddingRight') + ' ' + cs(bar, 'paddingBottom') + ' ' + cs(bar, 'paddingLeft'),
              id: cs(id, 'flexGrow') + ' ' + cs(id, 'flexShrink') + ' ' + cs(id, 'flexBasis'),
              tabs: t ? [cs(t, 'flexGrow'), cs(t, 'flexShrink'), cs(t, 'minWidth'), cs(t, 'marginTop') + cs(t, 'marginLeft'), cs(t, 'paddingTop') + cs(t, 'paddingLeft'), cs(t, 'borderTopWidth'), cs(t, 'alignSelf')].join(' ') : null}; })(),
    bar: {h: R(bar).height, before: cs(bar, 'display', '::before'), bg: cs(bar, 'backgroundImage'), cssTopbar: cv('--topbar'), kids: tops('.top-hdr > *'), flex: cs(bar, 'display'), wrap: cs(bar, 'flexWrap'),
          nameH: R(q('.hdr-project')).height, nameLH: parseFloat(cs(q('.hdr-project'), 'lineHeight')), nameWS: cs(q('.hdr-project > span'), 'whiteSpace'), nameTO: cs(q('.hdr-project > span'), 'textOverflow'),
          nameClip: q('.hdr-project > span').scrollWidth > q('.hdr-project > span').clientWidth, tabsRight: R(q('.top-hdr .tabs')).right, endLeft: R(q('.top-hdr .hdr-end')).left, barRight: R(bar).right, nameText: q('.hdr-project').textContent,
          idRatio: ratio(cs(q('.hdr-project'), 'color'), under(bar))},
    msvSw: sw.length ? {edge: ratio(cs(sw.find((b) => b.getAttribute('aria-current') === 'true'), 'backgroundColor'), under(q('.msv-sw').parentElement)), ground: under(q('.msv-sw').parentElement), gap: cs(q('.msv-sw'), 'columnGap'), rad: cs(q('.msv-sw'), 'borderTopLeftRadius'), ov: cs(q('.msv-sw'), 'overflow'), pad: cs(sw[0], 'paddingLeft') + ' ' + cs(sw[0], 'paddingRight'), div: cs(sw[1], 'borderLeftColor'), border: cs(q('.msv-sw'), 'borderTopWidth'), bc: cs(q('.msv-sw'), 'borderTopColor'), btns: seg(sw), ratios: sw.map((b) => ratio(cs(b, 'color'), cs(b, 'backgroundColor')))} : null,
    scale: sc.length ? {edge: ratio(cs(sc.find((b) => b.getAttribute('aria-current') === 'true'), 'backgroundColor'), under(q('.mv-txt').parentElement)), gap: cs(q('.mv-txt'), 'columnGap'), rad: cs(q('.mv-txt'), 'borderTopLeftRadius'), ov: cs(q('.mv-txt'), 'overflow'), pad: cs(sc[0], 'paddingLeft') + ' ' + cs(sc[0], 'paddingRight'), div: cs(sc[1], 'borderLeftColor'), btns: seg(sc), ratios: sc.map((b) => ratio(cs(b, 'color'), cs(b, 'backgroundColor'))), dots: qa('.mv-txt > span').map((e) => cs(e, 'display'))} : null,
  }; })()"""


MEASURED = {}


class Classic(Setup):
    def setUp(self):
        orig = testpage.html
        m = mock.patch.object(testpage, "html", lambda branding=None: page.layer_theme(orig(), theme.css(NAME)))
        m.start()
        self.addCleanup(m.stop)
        super().setUp()

    def measure(self, width, dark):
        if (width, dark) not in MEASURED:      # one measurement per width and scheme for the whole module: the tests only read it
            MEASURED[(width, dark)] = self.measure_now(width, dark)
        return MEASURED[(width, dark)]

    def measure_now(self, width, dark):
        with chrome() as cdp:
            p = self.show(cdp, width, False, standard=True)
            p.until("!!document.querySelector('.msv-sw') && !!document.querySelector('.mv-txt')", "the Milestones switch drew")
            if dark:
                p.js("document.documentElement.dataset.theme = 'dark'")
                p.until("getComputedStyle(document.documentElement).getPropertyValue('--heading').trim().toUpperCase() === '#F2F5FB'", "dark applied")
            got = p.js(PROBE)
            alpha = ".04" if dark else ".72"      # the odd-section bands of the stacked rows: translucent white over the page, composited, not read as solid
            p.js("document.querySelectorAll('.secs > .sec').forEach((e) => e.style.setProperty('background', 'rgba(255, 255, 255, %s)', 'important'))" % alpha)      # set through the object model: the page's policy refuses a new style element
            banded = p.js(PROBE)
            got["banded"] = {"sech": banded["sech"]["ratio"], "num": banded["num"]["ratio"]}
            got["others"] = p.js("""(() => { const out = {}; for (const [k, cls] of [['gantt', 'frame report gp'], ['milestones', 'frame milestones'], ['milestonesPub', 'frame milestones pub'], ['plain', 'frame'], ['asat', 'frame report asat-frame']]) {
                const e = document.createElement('section'); e.className = cls; if (k === 'asat') e.id = 'report'; document.body.appendChild(e); const c = getComputedStyle(e);
                out[k] = [c.borderTopWidth, c.boxShadow === 'none' ? 'none' : 'shadow']; e.remove(); } return out; })()""")
            got["longname"] = self.long_name(p)
            got["longname_off"] = p.js("""(() => { document.getElementById('report').id = 'report-off'; const n = document.querySelector('.hdr-project'), s = n.querySelector('span') || n, c = getComputedStyle(s); return [c.whiteSpace, c.textOverflow, c.overflow]; })()""")      # a page with no dashboard frame: the project name is not ellipsised
            return got

    def long_name(self, p):
        p.js("(() => { const n = document.querySelector('.hdr-project'); const t = n.querySelector('span') || n; t.textContent = 'A very long project name that goes on and on and on and on and on and on and on and on and on'; })()")
        return p.js("""(() => { const b = document.querySelector('.top-hdr'), n = document.querySelector('.hdr-project'), s = n.querySelector('span') || n, c = getComputedStyle(s);
          return {bar: b.getBoundingClientRect().height, name: n.getBoundingClientRect().height, lh: parseFloat(getComputedStyle(n).lineHeight), clip: s.scrollWidth > s.clientWidth,
                  ws: c.whiteSpace, to: c.textOverflow, ov: c.overflow, wide: document.documentElement.scrollWidth <= window.innerWidth}; })()""")

    def cases(self):
        return [(width, dark, self.measure(width, dark)) for width in (1400, 900) for dark in (False, True)]

    def test_the_glance_is_a_flat_strip_with_dividers_and_no_tile_look(self):
        for width, dark, g in self.cases():
            self.assertTrue(g["theme"])
            self.assertTrue(g["figBorders"])
            self.assertEqual(set(g["figBorders"]), {"0px0px"}, "no border on a figure")
            self.assertEqual(set(g["figBg"]), {"rgba(0, 0, 0, 0)"}, "no tile fill")
            self.assertEqual(set(g["figRadius"]), {"0px"})
            self.assertEqual(set(g["figAfter"]), {"none"}, "no tone outline")
            self.assertEqual(set(g["tw"]), {"0px0px"}, "the status word has no chip border or padding")
            self.assertEqual(g["gap"], "0px0px", "the figures touch: the dividers are the separation")
            self.assertGreaterEqual(len(g["cells"]), 3)
            rows = {}
            for c in g["cells"]:
                rows.setdefault(c["top"], []).append(c)
            for row in rows.values():
                row.sort(key=lambda c: c["left"])
                for i, c in enumerate(row):
                    self.assertEqual(c["bl"], "0px", (width, c))       # row 1345: the rule is on the right of a figure, none on the left
                    alone = len(row) == 1
                    self.assertEqual(c["br"], "0px" if (i == len(row) - 1 or alone) else "1px", (width, c))
            if width == 900:
                self.assertGreater(len(rows), 1, "Project health on its own row at 900")
                self.assertEqual([c["bb"] for r in rows.values() for c in r if c["health"]], ["1px"])
            else:
                self.assertEqual(len(rows), 1, "one strip of figures at 1400")
                self.assertEqual({c["bb"] for c in g["cells"]}, {"0px"})
            dividers = {c["rline"] for c in g["cells"] if c["br"] == "1px"}
            self.assertEqual(len(dividers), 1)
            self.assertTrue(g["scrollW"] <= g["innerW"])

    def test_the_section_number_is_20px_montserrat_bold_in_the_brand_colour(self):
        for width, dark, g in self.cases():
            print("row 1313 heading contrast", width, "dark" if dark else "light", "%.2f" % g["sech"]["ratio"])
            self.assertGreaterEqual(g["sech"]["ratio"], 4.5, "heading text on its composited ground")
            self.assertGreaterEqual(g["num"]["ratio"], 3.0, "the section number (large bold text) on its composited ground")
            self.assertEqual((g["num"]["size"], g["num"]["weight"]), ("20px", "700"))
            self.assertTrue(g["num"]["family"].startswith("Montserrat"))
            self.assertEqual(g["num"]["color"], rgb_of(g["num"]["blue"]))
            self.assertNotEqual(g["num"]["content"], "none")

    def test_the_heading_and_number_stay_readable_over_a_translucent_band(self):
        for width, dark, g in self.cases():
            print("row 1313 composited over a band", width, "dark" if dark else "light", "heading %.2f" % g["banded"]["sech"], "number %.2f" % g["banded"]["num"])
            self.assertGreaterEqual(g["banded"]["sech"], 4.5)
            self.assertGreaterEqual(g["banded"]["num"], 3.0)
            self.assertNotAlmostEqual(g["banded"]["sech"], 1.0, delta=0.5, msg="a translucent band read as solid would give about 1")

    def test_the_top_bar_is_85_tall_at_1400_and_one_row_103_tall_at_900(self):
        for width, dark, g in self.cases():
            b = g["bar"]
            self.assertEqual(b["h"], 85 if width == 1400 else 103)
            self.assertEqual(b["cssTopbar"].strip(), "85px" if width == 1400 else "103px")
            self.assertLessEqual(b["nameH"], b["nameLH"] + 1, "the demo name is one line")
            self.assertGreaterEqual(b["idRatio"], 4.5)
            self.assertLessEqual(b["tabsRight"], b["endLeft"] + 1, "the tabs end before the buttons: one row")
            self.assertLessEqual(b["endLeft"], b["barRight"])
            self.assertEqual(b["flex"], "flex")
            long = g["longname"]
            self.assertEqual(long["bar"], b["h"], "a long title does not change the bar's height")
            self.assertLessEqual(long["name"], long["lh"] + 1, "one line")
            self.assertEqual((long["ws"], long["to"], long["ov"]), ("nowrap", "ellipsis", "hidden"))
            self.assertTrue(long["clip"], "the long title is cut with an ellipsis")
            self.assertEqual(g["longname_off"], ["nowrap", "ellipsis", "hidden"], "row 1305: every Classic page's title takes the one-line ellipsis, not only the dashboard's")
            self.assertTrue(long["wide"], "no sideways scroll")
            n = g["narrow"]
            self.assertEqual((n["token"], n["min"]), (("85px", "85px") if width == 1400 else ("103px", "103px")), "the token the stylesheet gives, with the script's override off")
            if width == 900:
                self.assertEqual(b["wrap"], "nowrap")
                self.assertEqual(n["h"], 103, "the declared height, with the min-height floor off")
                self.assertEqual((n["ai"], n["gap"], n["pad"]), ("center", "12px", "10px 20px 10px 20px"))
                self.assertEqual(n["id"], "1 1 0px", "the name takes the spare room")
                self.assertEqual(n["tabs"], "0 1 0px 0px0px 0px0px 0px stretch", "the tabs shrink, sit flush and stretch")
                tops = b["kids"]
                self.assertLessEqual(max(tops) - min(tops), 40, "every part of the bar is in the one row")

    def test_the_milestones_switch_and_scale_are_joined_buttons_with_a_dark_active_one(self):
        for width, dark, g in self.cases():
            sw, sc = g["msvSw"], g["scale"]
            self.assertIsNotNone(sw)
            self.assertIsNotNone(sc)
            for grp in (sw, sc):
                self.assertEqual(grp["gap"], "0px", "joined")
                self.assertEqual(grp["rad"], "6px" if grp is sc else g["radius"], "the group keeps the rounded outer corners (the text tabs are radius 6, Row 1316 gap)")
                self.assertEqual(grp["ov"], "hidden", "the square buttons are clipped to the rounded outer corners")
                self.assertEqual(grp["pad"], "12px 12px", "each button keeps its side padding")
                self.assertEqual(grp["div"], rgb_of(g["g500"] if grp is sc else g["heading"]), "the rule between neighbours is the heading colour (the text tabs: --grey-500, Row 1316 gap)")
                self.assertEqual({b["radius"] for b in grp["btns"]}, {"0px"})
                self.assertEqual({b["bottom"] for b in grp["btns"]}, {"0px"}, "no underline")
                self.assertEqual([b["left"] for b in grp["btns"]], ["0px"] + ["1px"] * (len(grp["btns"]) - 1), "a rule between neighbours")
                active = [b for b in grp["btns"] if b["cur"] == "true"]
                self.assertEqual(len(active), 1)
                self.assertEqual(active[0]["bg"], "rgb(43, 56, 80)" if dark else rgb_of("#062F3A"), "row 1354: the chosen one is navy (light) or 2b3850 (dark)")
                for r in grp["ratios"]:
                    self.assertGreaterEqual(r, 4.5)
                self.assertNotEqual(active[0]["bg"], [b for b in grp["btns"] if b["cur"] != "true"][0]["bg"])
            for grp in (sw, sc) if not dark else ():      # dark: the fill is 1.46 to 1 on its ground, so row 1354 draws a 1px edge instead
                self.assertGreaterEqual(grp["edge"], 3.0, "the fill against the page beside it, as a control edge")
            print("row 1313 contrast", width, "dark" if dark else "light", "switch edge %.2f" % sw["edge"], "scale edge %.2f" % sc["edge"],
                  "active text %.2f" % min(r for r, b in zip(sw["ratios"], sw["btns"]) if b["cur"] == "true"), "ground", sw["ground"])
            self.assertEqual(sw["border"], "1px")
            self.assertEqual(sw["bc"], rgb_of(g["heading"]))
            self.assertEqual(set(sc["dots"]), {"none"}, "the dots between scales are gone")

    def test_only_the_dashboard_frame_goes_flat_the_gantt_page_the_milestones_frame_and_a_plain_frame_keep_their_card(self):
        for width, dark, g in self.cases():
            self.assertEqual(g["others"]["asat"][0], "3px", "the as-at-a-day frame keeps its dashed amber border: the flat rule skips it")
            for k in ("gantt", "plain"):
                self.assertEqual(g["others"][k], ["1px", "shadow"], k)
            self.assertEqual(g["others"]["milestonesPub"], ["1px", "shadow"], "the published Milestones frame is not matched: it carries no report class")
            self.assertEqual(g["others"]["milestones"][0], "0px", "the editor Milestones frame keeps the shell's own rule (frame.milestones:not(.pub), border 0); its Classic look is row 1315's")

    def test_the_report_frame_is_not_a_card(self):
        for width, dark, g in self.cases():
            f = g["frame"]
            self.assertIsNotNone(f)
            self.assertEqual((f["bg"], f["border"], f["shadow"]), ("rgba(0, 0, 0, 0)", "0px0px", "none"))


class Published(PublishedFile, Setup):
    theme = None      # set per case below
    """Row 1305 replaces the wrapping name of row 1239 in the published file (Classic, which a stored Cards value publishes too, row 1363): one line, ellipsis."""

    def look(self, theme_name, width):
        with self.store.con:
            self.store.con.execute("UPDATE app_settings SET theme = ? WHERE id = 1", (theme_name,))
        path = self.publish()
        with chrome() as cdp:
            p = self.draw(cdp, path, width)
            p.until("!!document.querySelector('.top-file .top-name')", "the bar drew")
            before = p.js("document.querySelector('.top-file').getBoundingClientRect().height")
            p.js("document.querySelector('.top-name').textContent = 'A very long project name that goes on and on and on and on and on and on and on and on and on'")
            got = p.js("""(() => { const b = document.querySelector('.top-file'), n = document.querySelector('.top-name'), c = getComputedStyle(n);
              return {theme: !!document.getElementById('theme'), ws: c.whiteSpace, to: c.textOverflow, ov: c.overflow, bar: b.getBoundingClientRect().height,
                      name: n.getBoundingClientRect().height, lh: parseFloat(c.lineHeight), clip: n.scrollWidth > n.clientWidth, wide: document.documentElement.scrollWidth <= window.innerWidth}; })()""")
            got["before"] = before
            return got

    def test_the_published_title_is_one_line_with_an_ellipsis_in_classic_at_1400_and_900(self):
        for name in ("classic", "cards"):      # row 1363: a stored Cards value publishes Classic
            for width in (1400, 900):
                with self.subTest(theme=name, width=width):
                    g = self.look(name, width)
                    self.assertTrue(g["theme"])
                    self.assertEqual((g["ws"], g["to"], g["ov"]), ("nowrap", "ellipsis", "hidden"))
                    self.assertLessEqual(g["name"], g["lh"] + 1, "one line")
                    self.assertTrue(g["clip"], "the 90 character name is cut")
                    self.assertEqual(g["bar"], g["before"], "the bar does not grow")
                    self.assertTrue(g["wide"])


def rgb_of(hex_colour):
    h = hex_colour.strip().lstrip("#")
    return "rgb(%d, %d, %d)" % tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


if __name__ == "__main__":
    unittest.main()
