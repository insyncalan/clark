"""Row 1375 (every Dashboard scroll section): a wheel at the end of a scrolling Dashboard section keeps moving the page (Classic).
The Dashboard scrollers are the Work items box (.wil-scroll, covered by test_wil_scroll_chain_1375), the Milestones list (.msl-scroll),
the Use case summary rows (.ucrows) and the Contents column (.cnt, drawn at 1400 only; display none at 900). Only .wil-scroll was held by shell.css (contain); the others never set a
value, so they chain. This file pins all four, a real wheel at the end of the Milestones list and the Use case rows at 1400 and 900 px (the Work items box wheel is in test_wil_scroll_chain_1375), the
rule text, and that the Cards page keeps its own value. Not in scope: dialogs, Gantt, menus, the Work items page's board (not on the Dashboard).
Run: cd tests && PYTHONPATH=../src bash ~/ag/slot.sh python3 -m unittest test_dashboard_scroll_chain_1375b
"""
import re
import tempfile
import time
import unittest

from _demo import USER
from _paths import SRC
from _real_server import real_server
from _uc_view import put_view
from clark import page, theme
from test_glance_page import Setup, tearDownModule  # noqa: F401
from test_ms_configure_1230 import put_ms_view
from test_server import chrome

PAGE_Y = "Math.round(window.scrollY)"
MS = ".msv[data-place^=sec-] .msl-scroll"
UC = ".ucrows"
RULES = (SRC / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")
SHELL = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")


class Chain(Setup):
    classic = True

    def setUp(self):
        super().setUp()
        self.s.close()
        css = theme.css("prototype-2.0") if self.classic else None
        self.s = real_server(self.store.path, self.store.data_for,
                             page_html=lambda: page.layer_theme(page.page_html(tempfile.mkdtemp()), css) if css else page.page_html(tempfile.mkdtemp()), seam=self.seam)
        self.addCleanup(self.s.close)
        with self.store.step("dashboard", USER) as st:
            for i, name in enumerate(["Kick-off", "Design signed", "Build done", "Training", "Go live", "Handover"]):
                st.create("milestones", {"project": "ABC", "name": name, "baseline_date": f"2030-0{i + 1}-01", "source": "demo"})
            for i in range(4):
                st.create("use_cases", {"project": "ABC", "title": f"Extra case {i}", "status": "Flag", "ref": f"2.{i}", "headline": "Filler", "standing": "<p>Filler.</p>", "source": "demo"})
        put_ms_view(self, {"n": 2, "scroll": True, "tracker": "bottom"})
        put_view(self, {"n": 2, "scroll": True, "tracker": "off"})

    def load(self, cdp, sel, width):
        p = self.show(cdp, width)
        p.until(f"!!document.querySelector('{sel}')", "the section drew")
        p.js("(() => { const s = document.createElement('div'); s.style.height = '4000px'; document.body.appendChild(s); })()")
        p.js(f"document.querySelector('{sel}').scrollIntoView({{block: 'center'}})")
        self.settle(p)
        return p

    def settle(self, p):
        """Wait until the page scroll position is the same on two reads 50 ms apart (max 5 s)."""
        last, end = None, time.time() + 5
        while time.time() < end:
            now = p.js(PAGE_Y)
            if now == last:
                return
            last = now
            time.sleep(0.05)
        self.fail("the page scroll did not settle within 5 s")

    def wheel(self, p, sel, dy):
        x, y = p.js(f"(() => {{ const r = document.querySelector('{sel}').getBoundingClientRect(); return [Math.round(r.left + r.width / 2), Math.round(r.top + r.height / 2)]; }})()")
        p.cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, p.sid)
        p.cdp.call("Input.dispatchMouseEvent", {"type": "mouseWheel", "x": x, "y": y, "deltaX": 0, "deltaY": dy, "pointerType": "mouse"}, p.sid)
        last, still, end = None, 0, time.time() + 5
        while still < 3 and time.time() < end:
            time.sleep(0.1)
            now = p.js(f"[{PAGE_Y}, Math.round(document.querySelector('{sel}').scrollTop)]")
            still = still + 1 if now == last else 0
            last = now
        return last

    def both_ways(self, width, sel):
        with chrome() as cdp:
            p = self.load(cdp, sel, width)
            self.assertEqual(p.js(f"getComputedStyle(document.querySelector('{sel}')).overscrollBehaviorY"), "auto")
            self.assertTrue(p.js(f"(b => b.scrollHeight > b.clientHeight + 20)(document.querySelector('{sel}'))"), "the section scrolls (the test's own check)")
            p.js(f"document.querySelector('{sel}').scrollTop = 0")
            _, top = self.wheel(p, sel, 40)
            self.assertGreater(top, 0, f"{width} {sel}: it still scrolls its own rows")
            p.js(f"(b => b.scrollTop = b.scrollHeight)(document.querySelector('{sel}'))")
            self.wheel(p, sel, 3)       # settles a fractional end
            y1 = p.js(PAGE_Y)
            page_y, _ = self.wheel(p, sel, 300)
            self.assertGreater(page_y, y1, f"{width} {sel}: a wheel down at the bottom moved the page")
            p.js(f"document.querySelector('{sel}').scrollTop = 0")
            y2 = p.js(PAGE_Y)
            page_y, _ = self.wheel(p, sel, -300)
            self.assertLess(page_y, y2, f"{width} {sel}: a wheel up at the top moved the page")

    def test_milestones_list_passes_the_wheel_to_the_page_1400_900(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                self.both_ways(width, MS)

    def test_use_case_rows_pass_the_wheel_to_the_page_1400_900(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                self.both_ways(width, UC)

    def test_every_dashboard_scroller_is_auto_in_classic_1400_900(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.load(cdp, MS, width)
                for name, sel in (("Milestones list", MS), ("Use case rows", UC)):
                    self.assertEqual(p.js(f"getComputedStyle(document.querySelector('{sel}')).overscrollBehaviorY"), "auto", f"{width}: {name} chains to the page")
                # the Work items box (.wil-scroll) at both widths is held by test_wil_scroll_chain_1375, not repeated here
                cnt = p.js("[...document.querySelectorAll('.cnt')].map(e => [getComputedStyle(e).display, getComputedStyle(e).overscrollBehaviorY])")
                self.assertTrue(cnt, f"{width}: the Contents column is in the page")
                if width == 900:
                    # vacuous by design: the Contents column is display none below 1000 px, so it cannot scroll or chain at 900
                    for display, _ in cnt:
                        self.assertEqual(display, "none", "900: the Contents column is not drawn (nothing to scroll; overscroll is not checked)")
                else:
                    for display, ob in cnt:
                        self.assertEqual(display, "block", f"{width}: the Contents column is drawn")
                        self.assertEqual(ob, "auto", f"{width}: the Contents column chains to the page")


class Cards(Chain):
    classic = False

    def test_the_cards_page_keeps_its_own_value(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.load(cdp, MS, width)
                # the Cards look layers none of Classic: the shared rule still holds the Work items box (contain), the others never set one
                self.assertEqual(p.js("(() => { const e = document.querySelector('.wil-scroll'); return e ? getComputedStyle(e).overscrollBehaviorY : 'contain'; })()"), "contain")
                self.assertEqual(p.js(f"getComputedStyle(document.querySelector('{MS}')).overscrollBehaviorY"), "auto")

    test_milestones_list_passes_the_wheel_to_the_page_1400_900 = None
    test_use_case_rows_pass_the_wheel_to_the_page_1400_900 = None
    test_every_dashboard_scroller_is_auto_in_classic_1400_900 = None


class RuleText(unittest.TestCase):
    def test_the_classic_layer_sets_auto_in_its_window(self):
        a, b = RULES.index("/* Row 1318"), RULES.index("/* Row 1393")
        self.assertRegex(RULES[a:b], r"(?m)^\.wil-scroll \{ overscroll-behavior-y: auto; \}$")
        self.assertEqual(len(re.findall(r"\.wil-scroll \{ overscroll-behavior-y: auto; \}", RULES)), 1)

    def test_shell_holds_only_the_work_items_box_and_never_the_other_dashboard_scrollers(self):
        self.assertIn(".wil-scroll { overflow-y: auto; overscroll-behavior-y: contain; }", SHELL)
        for cls in (".msl-scroll", ".ucrows", ".cnt"):
            for line in SHELL.splitlines():
                if re.match(re.escape(cls) + r"\b[^{]*\{", line):
                    self.assertNotIn("overscroll-behavior", line, cls)
        self.assertNotIn("overscroll-behavior", RULES.split(".cnt {", 1)[1].split("}", 1)[0])


if __name__ == "__main__":
    unittest.main()
