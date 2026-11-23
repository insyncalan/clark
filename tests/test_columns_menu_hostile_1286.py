"""Row 1286 (PR 1993), hostile pass on the NEW logic only: ColsPanel (ColumnsMenu.jsx, the Classic placement of the Columns menu, one microtask after MenuPanel)
and the three AP4 icon-tone selectors (rules-2.css). Fictional data only.

Run: python3 dev/run_tests.py test_columns_menu_hostile_1286
Real page in headless Chrome (Classic): absurd window heights (1, 8, 20, 50, 5000), the heading at the foot of the window, ten quick open and close rounds, a
second window size between opens; and a probe page with the theme CSS for the selectors (odd aria-labels).
"""
import json
import tempfile
import time
import unittest
from pathlib import Path

import _testpage as testpage
import test_tpl_workitems as base
from _paths import ROOT

import build_page  # noqa: E402
from clark import page, theme as themes
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome, wait

MEASURE = """(() => { const el = document.querySelector('.cols-menu'); if (!el) return null; const r = el.getBoundingClientRect(), c = getComputedStyle(el);
 const bar = document.querySelector('.top'), bb = bar ? bar.getBoundingClientRect().bottom : 0;
 return {floor: Math.round(bb), top: Math.round(r.top), bottom: Math.round(r.bottom), h: innerHeight, oy: c.overflowY, mh: el.style.maxHeight, scroll: el.scrollHeight, client: el.clientHeight}; })()"""


class ColsPanelHostile(base.InThePage):
    def setUp(self):
        super().setUp()
        plain = testpage.html
        testpage.html = lambda branding=None: page.layer_theme(plain(branding), themes.css("prototype-2.0"))
        self.addCleanup(setattr, testpage, "html", plain)

    def ready(self, cdp):
        ref = self.add({"mode": "all", "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo"]})
        p = self.show(cdp)
        p.edit()
        self.head = f"[data-id=\"{ref}\"] [data-wil-edit] .wil-table th.wil-c-owner"
        p.until(f"!!document.querySelector({json.dumps(self.head)})", "the list")
        p.js("window.__errs = []; addEventListener('error', function(e){window.__errs.push(String(e.message))}); addEventListener('unhandledrejection', function(e){window.__errs.push('rej')})")
        return p

    def size(self, cdp, p, w, h):
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": h, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.until(f"innerHeight === {h}", f"window {w}x{h}")

    def open(self, p, block="start"):
        p.js(f"document.querySelector({json.dumps(self.head)}).scrollIntoView({{block:{json.dumps(block)}}})")
        time.sleep(0.25)
        p.js(f"document.querySelector({json.dumps(self.head)}).dispatchEvent(new MouseEvent('contextmenu', {{bubbles: true, cancelable: true}}))")
        p.until(f"!!({MEASURE})", "the Columns menu opened")
        time.sleep(0.15)
        return p.js(MEASURE)

    def shut(self, p):
        p.js("document.querySelector('.cols-menu') && document.querySelector('.cols-menu').dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))")
        p.until("!document.querySelector('.cols-menu')", "closed")

    def test_absurd_window_heights_never_throw_and_always_close(self):
        with chrome() as cdp:
            p = self.ready(cdp)
            for h in (1, 8, 20, 50, 96, 5000):
                self.size(cdp, p, 1400, h)
                got = self.open(p)
                self.assertEqual(p.js("window.__errs"), [], f"h={h}")
                self.assertIsNotNone(got, f"h={h}")
                self.assertNotIn("NaN", json.dumps(got), f"h={h}: {got}")
                self.shut(p)

    def test_a_very_tall_window_leaves_the_menu_uncut_and_unmoved(self):
        with chrome() as cdp:
            p = self.ready(cdp)
            self.size(cdp, p, 1400, 900)
            ref = self.open(p)
            self.shut(p)
            self.size(cdp, p, 1400, 5000)
            got = self.open(p)
            self.assertEqual(got["mh"], "", f"nothing cut: {got}")
            self.assertEqual(got["bottom"] - got["top"], ref["bottom"] - ref["top"], f"same height: {got} vs {ref}")
            self.assertLessEqual(got["bottom"], got["h"])

    def test_a_foot_one_to_seven_pixels_above_the_window_bottom_is_lifted_to_the_8px_margin(self):
        with chrome() as cdp:
            p = self.ready(cdp)
            self.size(cdp, p, 1400, 900)
            tall = self.open(p)
            self.shut(p)
            for gap in (1, 4, 7):
                h = tall["bottom"] + gap
                self.size(cdp, p, 1400, h)
                got = self.open(p)
                self.assertLessEqual(got["bottom"], h - 8 + 1, f"gap {gap}: {got}")
                self.assertGreaterEqual(got["top"], got["floor"], f"gap {gap}: {got}")
                self.shut(p)
            self.size(cdp, p, 1400, tall["bottom"] + 8)      # exactly the margin: no move
            got = self.open(p)
            self.assertEqual(got["bottom"], tall["bottom"], f"foot exactly 8 above the bottom stays: {got}")
            self.shut(p)

    def test_heading_at_the_foot_of_the_window_keeps_the_menu_inside(self):
        with chrome() as cdp:
            p = self.ready(cdp)
            for h in (260, 420, 700):
                self.size(cdp, p, 1400, h)
                got = self.open(p, block="end")
                self.assertGreaterEqual(got["top"], got["floor"], f"h={h}: {got}")
                self.assertLessEqual(got["bottom"], got["h"], f"h={h}: {got}")
                self.shut(p)

    def test_ten_quick_rounds_give_the_same_place_each_time_and_leave_nothing_behind(self):
        with chrome() as cdp:
            p = self.ready(cdp)
            self.size(cdp, p, 1400, 300)
            first = self.open(p)
            self.shut(p)
            for i in range(10):
                got = self.open(p)
                self.assertEqual((got["top"], got["bottom"]), (first["top"], first["bottom"]), f"round {i}: {got} vs {first}")
                self.assertEqual(p.js("document.querySelectorAll('.cols-menu').length"), 1)
                self.shut(p)
            self.assertEqual(p.js("window.__errs"), [])

    def test_open_and_close_in_one_task_does_not_throw_from_the_microtask(self):
        with chrome() as cdp:
            p = self.ready(cdp)
            self.size(cdp, p, 1400, 300)
            p.js(f"(function(){{var h=document.querySelector({json.dumps(self.head)}); h.dispatchEvent(new MouseEvent('contextmenu',{{bubbles:true,cancelable:true}}));"
                 "var m=document.querySelector('.cols-menu'); if (m) m.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}));})()")
            time.sleep(0.5)
            self.assertEqual(p.js("window.__errs"), [])



class Selectors(unittest.TestCase):
    """The AP4 tone selectors, on a probe page with the real theme CSS: odd aria-labels."""
    NAME = "prototype-2.0"
    # (aria-label, id, class, red tone wanted)
    CASES = [
        ("Add a work item", None, "ddmenu", True), ("Add ", None, "ddmenu", True), ("Add", None, "ddmenu", False), ("Address book", None, "ddmenu", False),
        ("add a work item", None, "ddmenu", False), ("ADD A", None, "ddmenu", False), (" Add a", None, "ddmenu", False), ("Add a", None, "ddmenu", False),
        ("Move item to", None, "ddmenu", True), ("Move to", None, "ddmenu", True), ("Move  to", None, "ddmenu", True), ("Move item to…", None, "ddmenu", False),
        ("Move item to ", None, "ddmenu", False), ("Move due date", None, "ddmenu", False), ("Move X to" + "x" * 5000 + " to", None, "ddmenu", True),
        ("Add \u0000 a", None, "ddmenu", True), ("Add \U0001f600", None, "ddmenu", True), ("Move ‮ to", None, "ddmenu", True),
        ("Add a milestone to use case", None, "cpop", False), ("Add a", None, "", False), ("Group by", "viewMenuList", "ddmenu", True), ("Group by", "viewMenuList", "", True),
        ("Group by", None, "ddmenu", False), ("x", "newBtnMenu", "", True), ("x", "newBtnMenu2", "ddmenu", False),
    ]

    def test_selectors_match_only_what_they_name(self):
        rules = "".join((ROOT / "src" / "clark" / "themes" / self.NAME / f).read_text(encoding="utf-8") for f in ("rules.css", "rules-2.css"))
        parts = []
        for i, (label, ident, cls, _want) in enumerate(self.CASES):
            attrs = f' id="{ident}"' if ident else ""
            attrs += f' class="{cls}"' if cls else ""
            lab = label.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
            parts.append(f'<div{attrs} aria-label="{lab}" data-case="{i}"><i class="ic-r" data-probe="{i}r"></i><i class="ic-g" data-probe="{i}g"></i><i class="ic-b" data-probe="{i}b"></i></div>')
        # duplicate ids on a probe page are legal for the CSS test; give each its own container so the tones are read per case
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "page.html"
            path.write_text(f'<!doctype html><meta charset=utf-8><style>{build_page.page_css()}</style><style>{themes.css(self.NAME)}</style><body>{"".join(parts)}<i class="ic-r" data-probe="outr"></i><i class="ic-g" data-probe="outg"></i><i class="ic-b" data-probe="outb"></i></body>', encoding="utf-8")
            with chrome() as cdp:
                tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
                sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
                cdp.call("Page.enable", {}, sid)
                cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
                self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('[data-probe]').length", sid) == len(self.CASES) * 3 + 3))
                got = cdp.js("(function(){var o={};document.querySelectorAll('[data-probe]').forEach(function(e){o[e.dataset.probe]=getComputedStyle(e).color});return o})()", sid)
        prod = {"r": got["outr"], "g": got["outg"], "b": got["outb"]}
        for i, (label, ident, cls, want) in enumerate(self.CASES):
            with self.subTest(label=label[:30], ident=ident, cls=cls):
                for t in "rgb":
                    self.assertEqual(got[f"{i}{t}"] != prod[t], want, t)


for _name in dir(base.InThePage):      # the Work items tests of the base class are run by their own file, not again here
    if _name.startswith("test_") and _name not in ColsPanelHostile.__dict__:
        setattr(ColsPanelHostile, _name, None)

if __name__ == "__main__":
    unittest.main()
