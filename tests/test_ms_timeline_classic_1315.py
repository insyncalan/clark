"""Row 1315 part A: the Milestones page's timeline in the Classic theme (prototype 2.0): every name above its mark, the Today name under the line,
the bottom edge zooms, the hint says 'Drag the bottom edge to zoom'. The Cards theme draws what it always did.

Run: python3 dev/run_tests.py test_ms_timeline_classic_1315
Chrome launches at 1400 and 900 px, light and dark. Positions are computed in Chrome (getBoundingClientRect), not read from the source.
"""
import tempfile
import unittest

from _demo import USER
from _paths import ROOT
from clark import page
from test_milestones_page import BrowserBase, EMPTY_BRANDING
import test_ms_header_1230 as H
from test_server import Running, chrome, wait

HASH = "#milestones&p=TUL"
GRIP = "(() => { const r = document.querySelector('[data-grip]').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; })()"
HINT = "Drag the bottom edge to zoom"
GEOM = """(() => { const r = (e) => e.getBoundingClientRect(), wrap = r(document.querySelector('.mv-wrap')), line = r(document.querySelector('.mv-line')),
  g = document.querySelector('.mv-grip'), gr = r(g), t = document.querySelector('.mv-today b');
  const labs = [...document.querySelectorAll('.mv-lab')].map((l) => { const b = r(l), m = r(document.querySelector(`.mv-mk[data-ms="${l.dataset.lab.split(':')[0]}"]`));
    return { bottom: b.bottom, mid: (b.left + b.right) / 2, markMid: (m.left + m.right) / 2, markTop: m.top }; });
  const months = [...document.querySelectorAll('.mv-month')].map((e) => r(e).top);
  return { wrapTop: wrap.top, wrapBottom: wrap.bottom, wrapLeft: wrap.left, wrapRight: wrap.right, lineTop: line.top, labs, months,
    grip: { top: gr.top, bottom: gr.bottom, left: gr.left, right: gr.right, role: g.getAttribute('role'), tab: g.tabIndex, cursor: getComputedStyle(g).cursor, now: g.getAttribute('aria-valuenow') },
    today: t ? { top: r(t).top, left: r(t).left } : null, zoom: document.querySelector('.mv-wrap').dataset.zoomPct, bars: document.querySelector('.mv-wrap').offsetHeight - document.querySelector('.mv-wrap').clientHeight - 2,
    hint: (document.querySelector('.mv-bar .mv-zoom') || {}).textContent, label: document.querySelector('.mv-wrap').getAttribute('aria-label'),
    look: document.querySelector('.mv').dataset.look || '', box: getComputedStyle(document.querySelector('.mv-box')).paddingBottom }; })()"""


class Base(BrowserBase):
    THEME = "prototype-2.0"

    def serve(self):
        theme = self.THEME
        s = Running(data_for=self.store.data_for, projects=lambda archived=False: self.projects,
                    page_html=lambda: page.page_html(EMPTY_BRANDING, theme=theme))
        self.addCleanup(s.close)
        return s.port

    def show(self, cdp, width, mode):
        sid = self.visit(cdp, width, HASH, self.serve())
        cdp.js(f"document.documentElement.dataset.theme = '{mode}'", sid)
        self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.mv-lab').length > 0", sid)))
        return sid

    def every(self):
        for width in (1400, 900):
            for mode in ("light", "dark"):
                with self.subTest(width=width, mode=mode), chrome() as cdp:
                    yield cdp, self.show(cdp, width, mode), width


class Classic(Base, unittest.TestCase):
    def test_each_name_sits_above_its_mark_centred_and_the_month_row_above_the_names(self):
        for cdp, sid, w in self.every():
            g = cdp.js(GEOM, sid)
            self.assertEqual(g["look"], "classic")
            self.assertGreater(len(g["labs"]), 1)
            for lab in g["labs"]:
                self.assertLessEqual(lab["bottom"], lab["markTop"] + 1, "the name ends above its mark")
                self.assertAlmostEqual(lab["mid"], lab["markMid"], delta=2, msg="centred on the mark unless it is held inside the line")
            self.assertLess(max(g["months"]) + 17, min(l["bottom"] for l in g["labs"]) - 22, "month row clear of the names")

    def test_every_visible_name_is_in_the_one_lane_28px_below_the_top_of_the_strip(self):
        for cdp, sid, w in self.every():
            tops = cdp.js("[...document.querySelectorAll('.mv-lab')].map((l) => Math.round(l.getBoundingClientRect().top - document.querySelector('.mv-strip').getBoundingClientRect().top))", sid)
            self.assertGreater(len(tops), 1)
            self.assertEqual(set(tops), {28}, f"each name's top edge is 28px under the strip's top at {w}: {tops}")

    def test_the_today_name_is_under_the_line(self):
        for cdp, sid, w in self.every():
            g = cdp.js(GEOM, sid)
            self.assertGreater(g["today"]["top"], g["lineTop"] + 8, "under the line")
            self.assertLess(g["today"]["top"] + 18, g["wrapBottom"] + 1, "inside the strip")
            self.assertAlmostEqual(g["today"]["top"] - g["lineTop"], 14, delta=0.5, msg=f"the Today name is 14px under the line at {w}")

    def test_the_hint_and_the_name_of_the_strip_say_bottom_edge(self):
        for cdp, sid, w in self.every():
            g = cdp.js(GEOM, sid)
            self.assertEqual(g["hint"], HINT)
            self.assertIn("drag the bottom edge to zoom", g["label"])
            self.assertNotIn("grip", g["label"])

    def test_the_grip_is_the_bottom_edge_across_the_strip_with_a_corner_mark_and_still_a_slider(self):
        for cdp, sid, w in self.every():
            g = cdp.js(GEOM, sid)["grip"]
            wrap = cdp.js(GEOM, sid)
            self.assertAlmostEqual(g["left"], wrap["wrapLeft"], delta=1)
            self.assertAlmostEqual(g["right"], wrap["wrapRight"], delta=1)
            self.assertLessEqual(g["bottom"], wrap["wrapBottom"] + 1)
            self.assertEqual(round(g["bottom"] - g["top"]), 10, "a thin edge")
            self.assertLessEqual(g["bottom"], wrap["wrapBottom"] - wrap["bars"] + 2, "above a sideways scrollbar, never over it")
            self.assertGreater(g["top"], wrap["wrapBottom"] - 30, "on the bottom edge")
            self.assertEqual((g["role"], g["tab"], g["cursor"]), ("slider", 0, "ns-resize"))
            self.assertEqual(wrap["box"], "0px", "no spare row under the strip")
            corner = cdp.js("(() => { const b = document.querySelector('.mv-grip span').getBoundingClientRect(), g = document.querySelector('.mv-grip').getBoundingClientRect(); return [g.right - b.right, g.bottom - b.bottom, b.width, b.height]; })()", sid)
            self.assertLessEqual(corner[0], 4); self.assertLessEqual(corner[1], 4); self.assertEqual(corner[2:], [10, 10])

    def drag(self, mouse, y, dy):
        mouse("mousePressed", y, button="left", clickCount=1)
        for i in range(1, 7):
            mouse("mouseMoved", y + dy * i // 6, button="left", buttons=1)
        mouse("mouseReleased", y + dy, button="left", clickCount=1)

    def test_dragging_the_bottom_edge_down_grows_the_strip_and_up_shrinks_it_and_a_reset_shows_when_not_100(self):
        for cdp, sid, w in self.every():
            h0 = cdp.js("document.querySelector('.mv-wrap').offsetHeight", sid)
            x, y = cdp.js(GRIP, sid)
            mouse = lambda kind, py, **kw: cdp.call("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": py, **kw}, sid)
            self.drag(mouse, y, 80)
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('.mv-wrap').offsetHeight", sid) > h0 + 40), "taller after a drag down")
            g = cdp.js(GEOM, sid)
            self.assertTrue(170 <= int(g["zoom"]) <= 215, f"80px down on a 110px strip is about (112 + 80) / 112, a little more while the scrollbar goes: {g['zoom']}")
            self.assertEqual(cdp.js("!!document.querySelector('[data-zreset]')", sid), True, "the Reset link shows once the zoom is not 100%")
            self.assertAlmostEqual(g["lineTop"] - g["wrapTop"] - 1, cdp.js("document.querySelector('.mv-line').offsetTop", sid), delta=1, msg="the line keeps its place")
            cdp.js("document.querySelector('[data-zreset]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('.mv-wrap').dataset.zoomPct", sid) == "100"))
            self.assertEqual(cdp.js("document.querySelector('.mv-wrap').offsetHeight", sid), h0)

    def test_the_strip_is_112_tall_at_100_percent_with_the_line_78_from_its_top(self):
        for cdp, sid, w in self.every():
            g = cdp.js(GEOM, sid)
            own = cdp.js("parseFloat(document.querySelector('.mv-wrap').style.height) - parseFloat(getComputedStyle(document.querySelector('.mv-box')).getPropertyValue('--sb'))", sid)
            self.assertEqual(own, 112, "the strip's own height at 100%: 110 inside the 1px border (the line 78, the Today name 14 under it, 18 for its text), so the name ends inside the strip when there is no sideways scrollbar")
            self.assertAlmostEqual(g["lineTop"] - g["wrapTop"], 79, delta=1)


HIDDEN = """[...document.querySelectorAll('.mv-mk[data-hid]')].map((m) => { const r = m.getBoundingClientRect(); return { id: m.dataset.ms, hid: m.dataset.hid, title: m.title, aria: m.getAttribute('aria-label'),
  name: (document.querySelector(`.mv-meas[data-lab="${m.dataset.ms}:main"] b`) || {}).textContent, x: r.left + r.width / 2, y: r.top + r.height / 2, shown: !!document.querySelector(`.mv-lab[data-lab="${m.dataset.ms}:main"]`) }; })"""


class Hidden(Base, unittest.TestCase):
    """A name with no room beside it is hidden (as before), and stays reachable: the mark carries the name in its title and its accessible name, and hover shows it."""
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with cls.store.step("dashboard", USER) as st:
            for i, d in enumerate(("2026-10-02", "2026-10-08", "2026-10-14", "2026-10-26", "2026-10-30", "2026-11-05")):
                st.create("milestones", {"project": "TUL", "name": f"Crowded milestone number {i + 1}", "baseline_date": d, "source": "demo"})

    def test_every_hidden_name_is_in_its_marks_title_and_accessible_name_and_hover_shows_it(self):
        for cdp, sid, w in self.every():
            got = cdp.js(HIDDEN, sid)
            self.assertGreaterEqual(len(got), 3, "the crowd hides several names")
            for h in got:
                self.assertFalse(h["shown"], "a hidden name has no label")
                self.assertTrue(h["name"], "the measured name is there")
                self.assertIn(h["name"], h["title"], "the name is in the title")
                self.assertIn(h["name"], h["aria"], "and in the accessible name")
                self.assertEqual(h["title"], h["hid"])
                cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 1, "y": 1}, sid)
                cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": h["x"], "y": h["y"]}, sid)
                shown = cdp.js(f"getComputedStyle(document.querySelector('.mv-mk[data-ms=\"{h['id']}\"]'), '::after').content", sid)
                self.assertEqual(shown.strip('"'), h["hid"], "hover shows the name")
            cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 1, "y": 1}, sid)
            self.assertEqual(cdp.js(f"getComputedStyle(document.querySelector('.mv-mk[data-ms=\"{got[0]['id']}\"]'), '::after').content", sid), "none", "and only on hover")


class Cards(Base, unittest.TestCase):
    THEME = None

    def test_cards_draws_what_it_always_did(self):
        for cdp, sid, w in self.every():
            g = cdp.js(GEOM, sid)
            self.assertEqual(g["look"], "")
            self.assertIn("grip", g["hint"])
            self.assertIn("grip below it", g["label"])
            self.assertEqual(g["box"], "14px")
            self.assertAlmostEqual(g["grip"]["right"] - g["grip"]["left"], 64, delta=1)
            for lab in g["labs"]:
                self.assertGreater(lab["bottom"], g["lineTop"], "Cards keeps the names under the markers")
            self.assertAlmostEqual(g["lineTop"] - g["wrapTop"], 51, delta=1)


class Dashboard(H.Base):
    """The Dashboard's Milestones section keeps its own layout (row 1230) in Classic: only the Milestones page changes."""
    def setUp(self):
        super().setUp()
        self.s.close()
        self.s = Running(data_for=self.store.data_for, page_html=lambda: page.page_html(H.EMPTY_BRANDING, theme="prototype-2.0"))
        self.addCleanup(self.s.close)

    def test_the_section_is_not_drawn_the_page_way(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, "#dashboard&p=ABC", width, False, ".msv .mv-wrap")
                got = cdp.js("(() => { const m = document.querySelector('.msv[data-place^=sec-] .mv'); return [m.dataset.look || '', m.querySelectorAll('.mv-lab2').length > 0, m.querySelectorAll('.mv-lab').length, (m.querySelector('.mv-cap') || {}).textContent || '']; })()", sid)
                self.assertEqual(got[:3], ["", True, 0])
                self.assertIn("Drag the grip below the timeline to zoom", got[3])


class ClassicRulesPinned(unittest.TestCase):
    def test_the_timeline_block_is_exact(self):
        # this part's block, from its Row comment to the next Row comment (not the last N lines)
        rules = (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")
        start = rules.index("/* Row 1315, timeline part")
        got = [l for l in rules[start:].split("\n/* Row ", 2)[0].split("\n") if l.strip()]
        self.assertEqual(got, [
            "/* Row 1315, timeline part (Classic only): the Milestones page's line as prototype 2.0 draws it. MsTimeline.jsx reads --tl-classic and sets data-look on the line, so Cards draws what it always did. */",
            ':root { --tl-classic: 1; }',
            '.mv[data-look="classic"] .mv-box { padding-bottom: 0; }',
            '.mv[data-look="classic"] .mv-today b { top: calc(var(--ly) + 14px); left: 6px; }',
            '.mv[data-look="classic"] .mv-grip { left: 0; right: 0; bottom: var(--sb); width: auto; height: 10px; margin-left: 0; border-radius: 0; justify-content: flex-end; align-items: flex-end; }',
            '.mv[data-look="classic"] .mv-grip span { width: 10px; height: 10px; border: 0; border-radius: 0; margin: 0 2px 2px 0; background: linear-gradient(135deg, transparent 0 45%, var(--grey-500) 45% 55%, transparent 55% 70%, var(--grey-500) 70% 80%, transparent 80%); }',
            '.mv[data-look="classic"] .mv-grip:hover span { background: linear-gradient(135deg, transparent 0 45%, var(--text-muted) 45% 55%, transparent 55% 70%, var(--text-muted) 70% 80%, transparent 80%); }',
        ])


if __name__ == "__main__":
    unittest.main()
