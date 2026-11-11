"""Row 938-6 (motion): a Gantt task or phase bar drawn for the first time grows from its start (--dur-state, --ease-out), once.
Run: python3 dev/run_tests.py test_motion_gantt_bars
Needs Chrome: these tests fail, never skip, without it.

GanttChart.jsx puts .gt-grow on a bar the first time its line is drawn in a mount and takes it off when the animation ends; edit/edit.css animates
it inside a gate (no-preference and not data-motion="reduce"), never a dragged bar. A milestone (a rotated diamond) is left out. The rule is in
edit.css, not shell.css, because shell.css is also the published page's. The test page here is built with the SERVED entry's CSS (page_css(main.jsx),
which adds edit.css); the bare page of test_gantt_logic carries only the published CSS and would show no animation anywhere.
"""
import contextlib
import json
import re
import sys
import unittest

from _paths import SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402

from test_gantt_logic import LINES, TODAY, page_html as bare_html  # noqa: E402
import test_gantt_page  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402

EDIT = (SRC / "clark" / "page" / "src" / "edit" / "edit.css").read_text(encoding="utf-8")
SHELL = (build_page.PAGE / "shell.css").read_text(encoding="utf-8")
_P = {}


def served_html():
    """The chart's bare test page, but with the served entry's CSS (shell + edit.css)."""
    if "h" not in _P:
        view, served = build_page.page_css(), build_page.page_css(build_page.ENTRY)
        base = bare_html()
        old = view.replace("</style", "<\\/style")
        assert old in base
        _P["h"] = base.replace(old, served.replace("</style", "<\\/style"), 1)
    return _P["h"]


def lit(x):
    return json.dumps(x)


GROW = "document.getAnimations().filter(a => a.animationName === 'm-grow')"
BARS = "[data-g-bar]:not([data-g-type=\"milestone\"])"


class Static(unittest.TestCase):
    def test_the_rule_is_in_edit_css_inside_the_gate_with_tokens_and_not_in_the_shared_sheet(self):
        gate = EDIT[EDIT.index("row 938-6"):]
        self.assertIn("@media (prefers-reduced-motion: no-preference)", gate)
        self.assertIn(':root:not([data-motion="reduce"])', gate)
        self.assertEqual(EDIT.count("@keyframes m-grow"), 1)
        self.assertRegex(gate, r"\.gt-b\.gt-grow:not\(\.drag\) \{ transform-origin: left center; animation: m-grow var\(--dur-state\) var\(--ease-out\) 1; \}")
        self.assertNotRegex(gate.split("@keyframes m-grow")[0], r"infinite|\d+m?s\b(?!\))")
        self.assertNotIn("m-grow", SHELL)
        self.assertNotIn("gt-grow", SHELL)

    def test_the_published_bundle_holds_no_keyframe_of_it(self):
        view = build_page.build(build_page.ENTRY_VIEW)
        self.assertIn("data-g-bar", view, "the published page does draw the Gantt bars")
        self.assertNotIn("m-grow", view)
        self.assertNotRegex(view, r"\.gt-grow\s*[{:,]")
        self.assertNotIn("m-grow", build_page.page_css())


class Bars(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=served_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, cls.sid)

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def js(self, expr):
        return self.cdp.js(expr, self.sid)

    def val(self, expr):
        return json.loads(self.js(f"JSON.stringify({expr})"))

    def until(self, expr, what, t=8):
        self.assertTrue(wait(lambda: self.js(f"!!({expr})"), t), what)

    def page(self, width=1400, scheme="light", motion="no-preference", attr=False):
        self.cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme},
                                                                   {"name": "prefers-reduced-motion", "value": motion}]}, self.sid)
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        self.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.server.port}/"}, self.sid)
        self.until("window.mountGantt && window.K", "the test bundle ran")
        self.js(f"document.documentElement.dataset.theme = {lit(scheme)}; document.body.style.margin = '0'")
        if attr:
            self.js("document.documentElement.dataset.motion = 'reduce'")
        self.js("window.__st = []; document.addEventListener('animationstart', e => { if (e.animationName !== 'm-grow') return; var c = getComputedStyle(e.target); "
                "window.__st.push({id: e.target.dataset.gBar, type: e.target.dataset.gType, dur: c.animationDuration, ease: c.animationTimingFunction, iter: c.animationIterationCount, origin: c.transformOrigin.split(' ')[0]}); }, true)")

    def mount(self, edit=True, lines=LINES):
        w = int(self.js("innerWidth")) - 40
        self.js(f"mountGantt({lit(lines)}, {lit({'edit': edit, 'today': TODAY, 'width': w})})")
        self.until("document.querySelector('[data-g-bar]')", "bars are drawn")

    def grow(self):
        """How many m-grow animations have started since the last reset (the events, so a slow poll cannot miss a 220 ms run); settle first."""
        self.settle()
        self.js("0")
        return len(self.starts())

    def starts(self):
        return self.val("window.__st")

    def reset(self):
        self.settle()
        self.js("window.__st = []")

    def settle(self):
        self.until("document.getAnimations().length === 0", "every animation ended")

    def n_bars(self):
        return self.val(f"document.querySelectorAll('{BARS}').length")

    def test_first_draw_grows_every_task_and_phase_bar_once_for_220ms_at_every_look(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme):
                    self.page(width, scheme)
                    self.mount(edit=True)
                    n = self.n_bars()
                    self.assertGreater(n, 5)
                    self.settle()
                    got = self.starts()
                    self.assertEqual(len(got), n, "one growing animation per task or phase bar")
                    ease = self.js("getComputedStyle(document.documentElement).getPropertyValue('--ease-out').trim()")
                    for g in got:
                        self.assertEqual(g["dur"], "0.22s")
                        self.assertEqual(g["iter"], "1")
                        self.assertEqual(g["origin"], "0px", "grows from the start")
                        self.assertNotEqual(g["type"], "milestone", "milestones are left out")
                        self.assertEqual(re.sub(r"\b0\.", ".", g["ease"]).replace(" ", ""), ease.replace(" ", ""))
                    self.assertEqual(self.val(f"[...document.querySelectorAll('{BARS}')].every(b => getComputedStyle(b).transform === 'none')"), True)
                    self.assertEqual(self.val("document.getAnimations().length"), 0)
                    self.page(width, scheme)
                    self.mount(edit=False)
                    self.assertEqual(self.grow(), self.n_bars(), "View draws and grows its bars too")

    def test_a_drag_or_a_grab_during_the_first_moments_adds_and_leaves_nothing(self):
        self.page()
        self.mount()
        # grab at once (inside the first 220 ms): the dragged bar has no growing animation. The bar grows from its left edge and is 0 px wide in its
        # very first frame, so a click on its centre then lands on the row behind it: wait until it has some width, and press just inside its left edge.
        self.until("(function(){ var b = document.querySelector('[data-g-bar=\"GNT-006\"]'); return !!b && b.getBoundingClientRect().width >= 4; })()", "the bar has started to grow")
        r = self.val("(function(){ var r = document.querySelector('[data-g-bar=\"GNT-006\"]').getBoundingClientRect(); return {x: r.left + 2, y: r.top + r.height / 2}; })()")
        self.cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": r["x"], "y": r["y"], "button": "left"}, self.sid)
        self.cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": r["x"], "y": r["y"], "button": "left", "buttons": 1, "clickCount": 1}, self.sid)
        for k in range(1, 5):
            self.cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": r["x"] + 15 * k, "y": r["y"], "button": "left", "buttons": 1}, self.sid)
        self.until("document.querySelector('[data-g-bar=\"GNT-006\"].drag')", "the bar is being dragged")
        self.assertEqual(self.val("document.querySelector('[data-g-bar=\"GNT-006\"]').getAnimations().length"), 0)
        self.cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": r["x"] + 60, "y": r["y"], "button": "left", "buttons": 0, "clickCount": 1}, self.sid)
        self.until("window.calls.some(c => c[0] === 'change')", "the move was recorded")
        self.settle()
        self.assertEqual(self.val("document.querySelector('[data-g-bar=\"GNT-006\"]').classList.contains('gt-grow')"), False)
        # a drag when settled: no animation during or after
        self.reset()
        r = self.val("(function(){ var r = document.querySelector('[data-g-bar=\"GNT-005\"]').getBoundingClientRect(); return {x: r.left + r.width / 2, y: r.top + r.height / 2}; })()")
        self.cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": r["x"], "y": r["y"], "button": "left"}, self.sid)
        self.cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": r["x"], "y": r["y"], "button": "left", "buttons": 1, "clickCount": 1}, self.sid)
        for k in range(1, 5):
            self.cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": r["x"] + 15 * k, "y": r["y"], "button": "left", "buttons": 1}, self.sid)
            self.assertEqual(self.val("document.getAnimations().length"), 0)
        self.cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": r["x"] + 60, "y": r["y"], "button": "left", "buttons": 0, "clickCount": 1}, self.sid)
        self.assertEqual(self.val("window.calls.filter(c => c[0] === 'change').length >= 2"), True)
        self.assertEqual(self.grow(), 0, "nothing starts during or after a drag")

    def test_scale_resize_select_and_filter_changes_replay_nothing_and_an_added_line_grows_alone(self):
        self.page()
        self.mount()
        self.reset()
        for s in ("week", "month", "quarter", "month"):
            self.js(f"document.querySelector('[data-g-scale={s}]').click()")
            self.assertEqual(self.grow(), 0, f"scale {s}")
        self.js("document.getElementById('host').style.width = '700px'")
        self.js("document.querySelector('[data-g-bar=\"GNT-005\"]').click()")
        self.assertEqual(self.grow(), 0, "resize and select")
        self.js("document.querySelector('[data-g-show]').click()")
        self.until("document.querySelector('[data-g-showmenu]')", "the menu")
        self.js("document.querySelector('[data-g-filter=phases]').click()")
        self.assertEqual(self.grow(), 0)
        self.js("document.querySelector('[data-g-show]').click()")
        self.until("document.querySelector('[data-g-showmenu]')", "the menu")
        self.js("document.querySelector('[data-g-filter=all]').click()")
        self.until(f"document.querySelectorAll('{BARS}').length === {len([1 for l in LINES if l['type'] != 'milestone'])}", "all bars back")
        self.assertEqual(self.grow(), 0, "hide then show does not replay")
        self.js("document.querySelector('[data-g-add=GNT-004]').click()")
        self.until("document.querySelector('[data-g-addmenu]')", "the add menu")
        self.js("document.querySelector('[data-g-addtype=task]').click()")
        self.until(f"document.querySelectorAll('{BARS}').length === {len([1 for l in LINES if l['type'] != 'milestone']) + 1}", "the new bar")
        self.assertEqual(self.grow(), 1, "only the new line's bar grows")
        self.settle()
        self.js("window.calls.length = 0")

    def mount_key(self, key, lines=LINES):
        w = int(self.js("innerWidth")) - 40
        self.js(f"mountGantt({lit(lines)}, {lit({'edit': True, 'today': TODAY, 'width': w, 'projectKey': key})})")
        self.until("document.querySelector('[data-g-bar]')", "bars are drawn")

    def test_bars_grow_once_per_page_open_or_project_not_per_mount(self):
        self.page()
        self.mount_key("PRJ-A")
        n = self.n_bars()
        self.assertEqual(self.grow(), n, "the first draw grows every bar")
        # a tab return is a new mount of the same project: nothing grows
        self.reset()
        self.mount_key("PRJ-A")
        self.assertEqual(self.grow(), 0, "a remount replays nothing")
        # a resize and a layout of the host: nothing grows
        self.js("document.getElementById('host').style.width = '700px'")
        self.assertEqual(self.grow(), 0, "a resize replays nothing")
        # delete a line in the edit box, then put it back (what Undo does): its id was seen, so no grow
        self.js("window.prev = window.hostLines()")
        self.js("document.querySelector('[data-g-bar=\"GNT-006\"]').dispatchEvent(new MouseEvent('dblclick', {bubbles: true}))")
        self.until("document.querySelector('[data-g-bdel]')", "the edit box")
        self.js("document.querySelector('[data-g-bdel]').click()")
        self.until("!document.querySelector('[data-g-bar=\"GNT-006\"]')", "the line is deleted")
        self.js("window.hostSet(window.prev)")
        self.until("document.querySelector('[data-g-bar=\"GNT-006\"]')", "the line is back")
        self.assertEqual(self.grow(), 0, "the deleted line restored (Undo): no grow")
        # one added line grows alone
        extra = dict(next(l for l in LINES if l["id"] == "GNT-005"), id="GNT-099")
        self.mount_key("PRJ-A", LINES + [extra])
        self.assertEqual(self.grow(), 1, "only the added bar grows")
        # another project: all bars grow once, then it is quiet again
        self.reset()
        self.mount_key("PRJ-B")
        self.assertEqual(self.grow(), n, "another project grows all bars")
        self.reset()
        self.mount_key("PRJ-B")
        self.assertEqual(self.grow(), 0)
        # and going back to the first project draws nothing again: each project keeps its own memory for the session (ultrareview-105 section 10)
        self.reset()
        self.mount_key("PRJ-A")
        self.assertEqual(self.grow(), 0, "back to the first project: its bars already grew once")
        self.reset()
        self.mount_key("PRJ-B")
        self.assertEqual(self.grow(), 0, "and the second project is still remembered")

    def test_reduced_motion_by_the_computer_or_the_setting_runs_nothing(self):
        for motion, attr in (("reduce", False), ("no-preference", True)):
            with self.subTest(motion=motion, attr=attr):
                self.page(motion=motion, attr=attr)
                self.mount()
                self.assertEqual(self.grow(), 0)
                self.assertEqual(self.val("getComputedStyle(document.querySelector('.gt-b')).animationName"), "none")
                self.assertEqual(self.val("document.getAnimations().length"), 0)

    def test_drawn_under_reduced_motion_then_switched_off_nothing_grows_row_1000(self):
        """Drawn while reduced (by the computer or by the app's switch), then the setting goes OFF with the Gantt still open: no bar grows."""
        for how in ("computer", "switch"):
            with self.subTest(how=how):
                self.page(motion="reduce" if how == "computer" else "no-preference", attr=(how == "switch"))
                self.mount()
                self.assertEqual(self.grow(), 0)
                self.assertEqual(self.val(f"document.querySelectorAll('{BARS}.gt-grow').length"), 0, "no bar carries the grow class while reduced")
                self.reset()
                if how == "computer":
                    self.cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "no-preference"}]}, self.sid)
                else:
                    self.js("delete document.documentElement.dataset.motion")
                self.assertEqual(self.grow(), 0, "switching reduced motion off replays nothing")
                self.assertEqual(self.val("document.getAnimations().length"), 0)
                # a redraw after the switch (selecting a bar) still grows nothing
                self.js(f"document.querySelector('{BARS}').click()")
                self.assertEqual(self.grow(), 0)

    def test_the_published_stylesheet_alone_runs_nothing(self):
        self.page()
        self.mount()
        self.reset()
        # the same page with edit.css taken away (what a published file carries): no animation although the class is set
        self.js("document.querySelectorAll('style').forEach(s => { s.textContent = s.textContent.replace(/m-grow/g, 'm-gone'); })")
        self.js(f"mountGantt({lit(LINES)}, {lit({'edit': False, 'today': TODAY, 'width': 900})})")
        self.until("document.querySelector('[data-g-bar]')", "bars")
        self.assertEqual(self.grow(), 0)


    def test_a_childs_animationend_bubbling_to_the_bar_does_not_end_its_grow(self):
        self.page()
        self.mount_key("PRJ-A")
        self.until("document.querySelector('.gt-b-task.gt-grow i')", "a task bar is growing")
        id_ = self.js("document.querySelector('.gt-b-task.gt-grow').dataset.gBar")
        bar = f"document.querySelector('[data-g-bar=\"{id_}\"]')"
        # the nested progress fill reports an animationend that bubbles to the bar; a redraw (selecting it) then shows whether the grow was ended
        self.js(f"{bar}.querySelector('i').dispatchEvent(new AnimationEvent('animationend', {{bubbles: true, animationName: 'x'}}))")
        self.js(f"{bar}.click()")
        self.until(f"{bar}.classList.contains('sel')", "the bar is selected")
        self.assertTrue(self.js(f"{bar}.classList.contains('gt-grow')"), "a child's animationend left the grow in place")
        self.js(f"{bar}.dispatchEvent(new AnimationEvent('animationend', {{bubbles: true, animationName: 'm-grow'}}))")
        self.js(f"document.querySelector('{BARS}:not([data-g-bar=\"{id_}\"])').click()")
        self.until(f"!{bar}.classList.contains('sel')", "another bar is selected")
        self.assertFalse(self.js(f"{bar}.classList.contains('gt-grow')"), "its own animationend ends the grow")


class OnThePage(unittest.TestCase):
    """The same rule through the real GanttPage (the fixture gantt_page_demo.jsx): the page hands the chart its project's key."""

    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=test_gantt_page.page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, cls.sid)

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def js(self, expr):
        return self.cdp.js(expr, self.sid)

    def until(self, expr, what, t=8):
        self.assertTrue(wait(lambda: self.js(f"!!({expr})"), t), what)

    def open_page(self):
        self.cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "no-preference"}]}, self.sid)
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        self.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.server.port}/"}, self.sid)
        self.until("window.P && window.P.mount", "the page demo ran")
        self.js("window.__st = []; document.addEventListener('animationstart', e => { if (e.animationName === 'm-grow') window.__st.push(e.target.dataset.gBar); }, true)")

    def mount(self, code):
        self.js(f"P.mount({lit({'project': {'name': 'Demo project', 'code': code, 'client_name': 'Example client', 'week_ending': '2026-11-06'}})})")
        self.until("document.querySelector('[data-g-bar]')", "bars are drawn")

    def bars(self):
        return int(self.js(f"document.querySelectorAll('{BARS}').length"))

    def grow(self):
        self.until("document.getAnimations().length === 0", "every animation ended")
        n = len(json.loads(self.js("JSON.stringify(window.__st)")))
        self.js("window.__st = []")
        return n

    def test_the_page_gives_each_project_its_own_first_grow(self):
        self.open_page()
        self.mount("PRJ-A")
        n = self.bars()
        self.assertGreater(n, 0)
        self.assertEqual(self.grow(), n, "the first project grows every bar")
        self.mount("PRJ-A")
        self.assertEqual(self.grow(), 0, "a remount of the same project grows none")
        self.mount("PRJ-B")
        self.assertEqual(self.grow(), n, "the second project grows every bar once")
        self.mount("PRJ-B")
        self.assertEqual(self.grow(), 0, "a remount of the second project grows none")
        self.mount("PRJ-A")
        self.assertEqual(self.grow(), 0, "back on the first project it grows none: each project keeps its own memory (ultrareview-105 section 10)")


if __name__ == "__main__":
    unittest.main()
