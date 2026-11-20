"""Row 1324 (rest after PR 1973): the Work items grouped view as Option A in the three places the audit found open (Classic only):
(1) the PUBLISHED Work items tab draws the same heading line (no tile, no band, one hairline, column names once on top);
(2) dark: the same look in dark, and the heading and the count read at 4.5:1 in light and dark, in the editor page and the published file;
(3) the heading weight is 600 (the --weight-medium token) in the computed style, light and dark.
Design and format only: no word is new. 900 wide is out (Tech Debt, ticket comment 20-11).

Run: python3 dev/run_tests.py test_gap_1324_published_dark
"""
import tempfile
import unittest
from pathlib import Path

from test_server import chrome, wait  # noqa: E402
import test_gap_1324_workitems as base  # noqa: E402
import test_publish_uc_list_1114 as pub  # noqa: E402
import test_use_cases_list as ucl  # noqa: E402
from test_publish import EMPTY_BRANDING, opened  # noqa: E402
import _publish_fixture as fx  # noqa: E402
from clark import page, publish  # noqa: E402

PROBE = base.PROBE
SELS = ["#work .grp-b .gl", "#work .grp-b .gc"]


DARK = """(() => { const rgb = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number);
  const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  let e = document.querySelector('#work'), back = 'rgba(0, 0, 0, 0)';
  while (e && /rgba\\(.*, 0\\)|transparent/.test(back)) { back = getComputedStyle(e).backgroundColor; e = e.parentElement; }
  const h = getComputedStyle(document.querySelector('#work .grp-b .gl')).color;
  return { back: lum(rgb(back)), head: lum(rgb(h)), headColour: h }; })()"""

# The page is really dark: the surface behind the heading is dark and the heading text is light (the reverse in light).
# The emulated media alone proved nothing: light text on white passes the same contrast asserts.
SURFACE = {"light": (0.6, 1.01), "dark": (-0.01, 0.2)}


def really(test, cdp, sid, scheme, ctx, seen):
    got = cdp.js(DARK, sid)
    lo, hi = SURFACE["dark" if scheme == "dark" else "light"]
    test.assertTrue(lo <= got["back"] <= hi, f"{ctx}: the surface luminance {got['back']:.3f} is {scheme}")
    test.assertTrue((got["head"] > got["back"]) == (scheme == "dark"), f"{ctx}: the heading is {'lighter' if scheme == 'dark' else 'darker'} than its surface")
    if scheme == "os-dark":
        return
    seen[scheme] = got["headColour"]
    if len(seen) == 2:
        test.assertNotEqual(seen["light"], seen["dark"], f"{ctx}: the heading colour differs between light and dark")


HOVER = """(() => { const rgb = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number);
  const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const ratio = (a, b) => { const x = lum(rgb(a)), y = lum(rgb(b)); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const b = document.querySelector('#work .grp-b'); let e = b, back = 'rgba(0, 0, 0, 0)';
  while (e && /rgba\\(.*, 0\\)|transparent/.test(back)) { back = getComputedStyle(e).backgroundColor; e = e.parentElement; }
  const c = getComputedStyle(b), i = getComputedStyle(b.querySelector('.i')), l = getComputedStyle(b.querySelector('.gl')), n = getComputedStyle(b.querySelector('.gc'));
  const brand = (() => { const t = document.createElement('i'); t.style.color = 'var(--brand-blue)'; document.body.appendChild(t); const v = getComputedStyle(t).color; t.remove(); return v; })();
  return { hovered: b.matches(':hover'), brand, word: l.color, chev: i.color, wordRatio: ratio(l.color, back), chevRatio: ratio(i.color, back), countRatio: ratio(n.color, back),
    ring: [c.outlineWidth, c.outlineStyle, c.outlineOffset, c.borderTopLeftRadius, c.outlineColor], ringRatio: ratio(c.outlineColor, back) }; })()"""


def move(cdp, sid, x, y):
    cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, sid)


def edges(test, cdp, sid, ctx):
    """Hover (a real pointer over the first heading) and keyboard focus, measured in the scheme the page is in: the word and the
    chevron go --brand-blue (the word 4.5 to 1; the chevron is the same colour, so 4.5 too); the resting chevron 3 to 1 (an icon,
    the design system's floor); the focus ring is 2 px --brand-blue at 3 to 1. A one-item group reads "1 item", the rest "N items",
    and no group is drawn with no row. Returns the count labels."""
    box = cdp.js("(() => { const r = document.querySelector('#work .grp-b').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; })()", sid)
    move(cdp, sid, 1, 1)
    rest = cdp.js(HOVER, sid)
    test.assertFalse(rest["hovered"], f"{ctx}: no pointer over the heading yet")
    move(cdp, sid, box[0], box[1])
    test.assertTrue(wait(lambda: cdp.js(HOVER, sid)["word"] == cdp.js(HOVER, sid)["brand"]), f"{ctx}: hover turns the word --brand-blue")
    hov = cdp.js(HOVER, sid)
    test.assertTrue(hov["hovered"] and hov["chev"] == hov["brand"], f"{ctx}: hover turns the chevron --brand-blue")
    test.assertNotEqual(rest["word"], hov["word"], f"{ctx}: hover changes the word colour")
    test.assertGreaterEqual(hov["wordRatio"], 4.5, f"{ctx}: hovered word 4.5 to 1: {hov['wordRatio']}")
    test.assertGreaterEqual(hov["chevRatio"], 4.5, f"{ctx}: hovered chevron 4.5 to 1: {hov['chevRatio']}")
    test.assertGreaterEqual(rest["chevRatio"], 3, f"{ctx}: resting chevron 3 to 1: {rest['chevRatio']}")
    test.assertGreaterEqual(rest["countRatio"], 4.5, f"{ctx}: count 4.5 to 1: {rest['countRatio']}")
    move(cdp, sid, 1, 1)
    cdp.js("document.querySelector('#work .grp-b').focus()", sid)
    foc = cdp.js(HOVER, sid)
    test.assertEqual(foc["ring"][:4], ["2px", "solid", "2px", "6px"], f"{ctx}: the ring is 2 px, offset 2 px, radius 6 px")
    test.assertEqual(foc["ring"][4], foc["brand"], f"{ctx}: the ring is --brand-blue")
    test.assertGreaterEqual(foc["ringRatio"], 3, f"{ctx}: the ring reads 3 to 1: {foc['ringRatio']}")
    labels = cdp.js("[...document.querySelectorAll('#work .grp-b .gc')].map((e) => e.textContent.trim())", sid)
    for t in labels:
        n = int(t.split()[0])
        test.assertGreater(n, 0, f"{ctx}: no group is drawn empty: {labels}")
        test.assertEqual(t, "1 item" if n == 1 else f"{n} items", f"{ctx}: the count label")
    return labels


def check(test, got, ctx):
    test.assertGreaterEqual(got["n"], 2, f"{ctx}: grouped")
    test.assertEqual((got["colh"], got["colhInGroup"]), (1, 0), f"{ctx}: the column names once, on top")
    test.assertEqual(got["tile"], ["rgba(0, 0, 0, 0)", "0px", "0px", "visible"], f"{ctx}: no tile")
    test.assertEqual(got["head"][:5], ["rgba(0, 0, 0, 0)", "0px", "6px", "0px", "1px"], f"{ctx}: no band, one hairline")
    test.assertEqual(got["btn"], ["600", "15px", "Montserrat"], f"{ctx}: heading weight 600, 15 px, heading face")
    test.assertEqual(got["count"][:2], ["13px", "2px"], f"{ctx}: count 13 px, 2 px before it")
    test.assertEqual(got["lineOf"], [got["line"]] * 2, f"{ctx}: the lines are the --grey-200 token")
    test.assertEqual(got["margins"], ["14px"] + ["18px"] * (got["n"] - 1), f"{ctx}: 14 px under the column names, 18 px between groups")
    test.assertTrue(got["wide"], f"{ctx}: no sideways scroll")


class EditorDark(base.WorkItemsOptionA):
    """The editor's grouped Work items page in dark and in light, with contrast (the inherited tests run again in light: left out below)."""

    def test_option_a_light_and_dark_with_contrast(self):
        seen = {}
        for scheme in ("light", "dark"):
            with self.subTest(scheme=scheme), chrome() as cdp:
                sid = self.load(cdp, 1400, scheme, "no-preference")
                really(self, cdp, sid, scheme, f"editor {scheme}", seen)
                check(self, cdp.js(PROBE, sid), f"editor {scheme}")
                edges(self, cdp, sid, f"editor {scheme}")
                ratios = cdp.js(ucl.contrast_script(SELS), sid)
                self.assertTrue(ratios and all(r[1] >= 4.5 for r in ratios), f"editor {scheme}: heading and count read at 4.5 to 1: {ratios}")

    test_the_grouped_list_is_option_a_at_1400 = None
    test_hover_and_focus_of_the_heading = None
    test_a_group_shuts_and_the_one_column_row_stays = None


class Published(unittest.TestCase):
    """The published Work items tab, Classic Theme layered, grouped by Priority."""

    def go(self, cdp, tmp, scheme, by="Priority", plant=None):
        plant = plant or fx.load()
        p = publish.select(fx.inputs(plant))
        text = publish.render(p, page.page_html(EMPTY_BRANDING, view=True, theme=pub.THEME), plant["as_at"], p["data"]["project"]["name"])
        path = Path(tmp) / "w.html"
        path.write_text(text, encoding="utf-8")
        sid = opened(cdp, path.as_uri())
        # A published file carries no data-theme (stores/appearance.js:5), so the computer's own scheme never darkens it: "os-dark" is that
        # case (the computer is dark, the file stays light); "dark" sets data-theme=dark by hand, the one way the dark tokens reach it.
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": "light" if scheme == "light" else "dark"}]}, sid)
        self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"))
        if scheme == "dark":
            # after the page has started, so its own start-up cannot put the theme back (a slow runner did that); then wait until it shows
            cdp.js("document.documentElement.dataset.theme = 'dark'", sid)
            self.assertTrue(wait(lambda: cdp.js("(() => { const c = getComputedStyle(document.body).backgroundColor.match(/[\\d.]+/g).slice(0, 3).map(Number); return c[0] + c[1] + c[2] < 300; })()", sid)), "the dark tokens reached the file")
        cdp.js("document.querySelector('[data-view=work]').click()", sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#work h1')", sid)), "the Work items tab drew")
        cdp.js("document.querySelector('#group-by, [aria-label^=\"Group by\"]').click()", sid)
        self.assertTrue(wait(lambda: cdp.js("!![...document.querySelectorAll('[role^=menuitem]')].find(e => e.textContent.replace('✓', '').trim() === '" + by + "')", sid)))
        cdp.js("[...document.querySelectorAll('[role^=menuitem]')].find(e => e.textContent.replace('✓', '').trim() === '%s').click()", sid)
        self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work .grp-b').length", sid) >= 2))
        if scheme == "dark":
            cdp.js("document.documentElement.dataset.theme = 'dark'", sid)       # again, in case the page's own redraw took it off
            self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.theme", sid) == "dark"))
        return sid

    def test_the_published_group_is_a_heading_line_in_light_and_dark(self):
        seen = {}
        for scheme in ("light", "os-dark", "dark"):
            with self.subTest(scheme=scheme), tempfile.TemporaryDirectory() as tmp, chrome() as cdp:
                sid = self.go(cdp, tmp, scheme)
                really(self, cdp, sid, scheme, f"published {scheme}", seen)
                check(self, cdp.js(PROBE, sid), f"published {scheme}")
                edges(self, cdp, sid, f"published {scheme}")
                ratios = cdp.js(ucl.contrast_script(SELS), sid)
                self.assertTrue(ratios and all(r[1] >= 4.5 for r in ratios), f"published {scheme}: 4.5 to 1: {ratios}")

    def test_a_published_group_shuts_and_keeps_one_column_row(self):
        rows = "[...document.querySelectorAll('#work tr[data-id]')].filter((r) => r.getClientRects().length).length"
        for scheme in ("light", "dark"):
            with self.subTest(scheme=scheme), tempfile.TemporaryDirectory() as tmp, chrome() as cdp:
                sid = self.go(cdp, tmp, scheme)
                before = cdp.js(rows, sid)
                inside = cdp.js("document.querySelectorAll('#work .wgroup')[1].querySelectorAll('tr[data-id]').length", sid)
                self.assertGreater(inside, 0)
                cdp.js("document.querySelector('#work .grp-b').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("document.querySelector('#work .grp-b').getAttribute('aria-expanded')", sid) == "false"))
                self.assertTrue(wait(lambda: cdp.js(rows, sid) < before), f"{scheme}: the shut group's rows are not shown")
                self.assertEqual(cdp.js("document.querySelectorAll('#work tr.colh').length", sid), 1)
                self.assertEqual(cdp.js("document.querySelector('#work .grp-b').getAttribute('aria-expanded')", sid), "false")
                self.assertEqual(cdp.js("document.querySelectorAll('#work .grp-b').length", sid) >= 2, True, f"{scheme}: the shut group's heading stays")

    def test_the_published_tab_grouped_by_workstream(self):
        """The mock-up groups by workstream. The fixture has one workstream with rows (Delivery) and rows with none, so the
        grouping gives those groups; the Priority run above has the group count and the labels."""
        with tempfile.TemporaryDirectory() as tmp, chrome() as cdp:
            sid = self.go(cdp, tmp, "dark", by="Workstream")
            check(self, cdp.js(PROBE, sid), "published workstream dark")
            labels = edges(self, cdp, sid, "published workstream dark")
            self.assertGreaterEqual(len(labels), 2, labels)


if __name__ == "__main__":
    unittest.main()
