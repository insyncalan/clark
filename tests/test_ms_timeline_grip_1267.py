"""Row 1267: the Timeline's height grip sits on the centre of the bottom edge (not the browser's corner handle), drags and keys zoom the line, and the grip shows only when the line overflows its box.

Run: python3 dev/run_tests.py test_ms_timeline_grip_1267
Chrome launches at 1400 and 900 px.
"""
import copy
import tempfile
import unittest

from clark import page
from _new_page import reload_to_new_page_cdp
from test_milestones_page import BrowserBase
from test_server import Running, chrome, wait
from test_work_items import page_target

HASH = "#milestones&p=TUL"
CLASSIC = "prototype-2.0"
GEO = """(() => { const w = document.querySelector('.mv-wrap').getBoundingClientRect(), g = document.querySelector('[data-grip]').getBoundingClientRect();
  return [(g.left + g.width / 2) - (w.left + w.width / 2), w.bottom - g.bottom, w.bottom - g.top, getComputedStyle(document.querySelector('.mv-wrap')).resize]; })()"""
PCT = "document.querySelector('.mv-wrap').dataset.zoomPct"
KEY = "(k) => { const g = document.querySelector('[data-grip]'); g.focus(); g.dispatchEvent(new KeyboardEvent('keydown', {key: k, bubbles: true, cancelable: true})); }"


class Classic:
    """Row 1267 is a Classic rule: the look of the grip is on both pages; the slider keys and the no-grip-on-a-short-line rule are Classic only (Cards is frozen). serve() is the Cards page, serve(CLASSIC) the Classic one."""

    def serve(self, theme=None):
        s = Running(data_for=self.store.data_for, projects=lambda archived=False: self.projects, page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=theme))
        self.addCleanup(s.close)
        return s.port

    def press(self, cdp, sid, key):
        cdp.js(f"({KEY})('{key}')", sid)


class Grip(Classic, BrowserBase, unittest.TestCase):
    def test_the_grip_is_centred_on_the_bottom_edge_and_the_corner_handle_is_gone(self):
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, HASH, port)
                dx, below, top, native = cdp.js(GEO, sid)
                self.assertLess(abs(dx), 1.5, f"{width}: centred")
                self.assertLessEqual(below, -10, f"{width}: it hangs under the strip's bottom edge, over no label")
                self.assertTrue(-3 <= top <= 12, f"{width}: its 24px box starts at the bottom edge and hangs under it ({top})")
                self.assertEqual(native, "none", f"{width}: no browser handle in the corner")

    def test_the_grip_is_a_named_slider_with_a_value(self):
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, HASH, port)
                got = cdp.js("(() => { const g = document.querySelector('[data-grip]'); return [g.getAttribute('role'), g.getAttribute('aria-label'), g.getAttribute('aria-valuenow'), g.getAttribute('aria-valuetext'), g.tabIndex]; })()", sid)
                self.assertEqual(got, ["slider", "Timeline height", "100", "Zoom 100%", 0], width)
                bounds = cdp.js("(() => { const g = document.querySelector('[data-grip]'); return [g.getAttribute('aria-orientation'), g.getAttribute('aria-valuemin'), g.getAttribute('aria-valuemax')]; })()", sid)
                self.assertEqual(bounds, ["vertical", "70", "300"], f"{width}: the slider says which way it moves and where it ends")

    def test_slider_keys_up_and_right_raise_down_and_left_lower_home_is_100_end_the_most(self):
        port = self.serve(CLASSIC)
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, HASH, port)
                now = "document.querySelector('[data-grip]').getAttribute('aria-valuenow')"
                self.assertEqual(cdp.js("[document.querySelector('[data-grip]').getAttribute('aria-valuemin'), document.querySelector('[data-grip]').getAttribute('aria-valuemax')]", sid), ["70", "300"])
                self.press(cdp, sid, "ArrowUp")
                self.assertTrue(wait(lambda: cdp.js(PCT, sid) == "110"), f"{width}: Up is one step more")
                self.assertEqual(cdp.js(now, sid), "110")
                self.assertEqual(cdp.js("document.querySelector('[data-grip]').getAttribute('aria-valuetext')", sid), "Zoom 110%")
                self.assertEqual(cdp.js("document.querySelector('[data-grip]') === document.activeElement", sid), True, f"{width}: focus stays on the grip")
                self.press(cdp, sid, "ArrowRight")
                self.assertTrue(wait(lambda: cdp.js(PCT, sid) == "120"), f"{width}: Right is one step more")
                self.press(cdp, sid, "ArrowDown"); self.press(cdp, sid, "ArrowLeft"); self.press(cdp, sid, "ArrowDown")
                self.assertTrue(wait(lambda: cdp.js(PCT, sid) == "90"), f"{width}: Down and Left are one step less each")
                self.assertEqual(cdp.js("localStorage.getItem('clark.tlZoom.page')", sid), "0.9", f"{width}: remembered")
                self.press(cdp, sid, "End")
                self.assertTrue(wait(lambda: cdp.js(PCT, sid) == "300"), f"{width}: End is the most")
                self.assertEqual(cdp.js(now, sid), "300")
                self.press(cdp, sid, "Home")
                self.assertTrue(wait(lambda: cdp.js(PCT, sid) == "100"), f"{width}: Home is 100%")
                self.assertEqual(cdp.js(now, sid), "100")
                self.assertEqual(cdp.js("(() => { const e = new KeyboardEvent('keydown', {key: 'a', bubbles: true, cancelable: true}); document.querySelector('[data-grip]').dispatchEvent(e); return e.defaultPrevented; })()", sid), False, f"{width}: other keys are left alone")

    def test_dragging_the_grip_down_zooms_and_is_remembered(self):
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, HASH, port)
                h = cdp.js("document.querySelector('.mv-wrap').offsetHeight", sid)
                x, y = cdp.js("(() => { const r = document.querySelector('[data-grip]').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; })()", sid)
                cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1}, sid)
                for i in range(1, 7):
                    cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y + i * 20, "button": "left", "buttons": 1}, sid)
                cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y + 120, "button": "left", "clickCount": 1}, sid)
                self.assertTrue(wait(lambda: float(cdp.js(PCT, sid)) > 100), f"{width}: zoomed in")
                self.assertGreater(cdp.js("document.querySelector('.mv-wrap').offsetHeight", sid), h + 60, f"{width}: taller")
                self.assertTrue(wait(lambda: cdp.js("localStorage.getItem('clark.tlZoom.page')", sid) not in (None, "1")), f"{width}: remembered")

    def test_the_words_say_what_the_grip_does_not_that_the_edge_drags(self):
        import json, pathlib
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, HASH, port)
                cap = cdp.js("(document.querySelector('.mv-zoom, .mv-cap') || {}).textContent || ''", sid)
                label = cdp.js("document.querySelector('.mv-wrap').getAttribute('aria-label')", sid)
                self.assertIn("Drag the grip below the timeline to zoom", cap, width)
                self.assertIn("drag the grip below it to zoom", label, width)
                self.assertNotIn("bottom edge", cap + label, width)
        help_text = (pathlib.Path(__file__).resolve().parent.parent / "src/clark/page/src/help/helpContent.json").read_text(encoding="utf-8")
        json.loads(help_text)
        self.assertNotIn("bottom edge to zoom", help_text)
        self.assertNotIn("its bottom edge to zoom", help_text)
        self.assertEqual(help_text.count("grip below it to zoom"), 2, "both Timeline help lines name the grip")

    def test_a_touch_drag_on_the_grip_zooms_by_pointer_events(self):
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, HASH, port)
                h = cdp.js("document.querySelector('.mv-wrap').offsetHeight", sid)
                self.assertEqual(cdp.js("getComputedStyle(document.querySelector('[data-grip]')).touchAction", sid), "none", f"{width}: the grip holds the touch")
                x, y = cdp.js("(() => { const r = document.querySelector('[data-grip]').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; })()", sid)
                cdp.js("(() => { window.__pt = []; for (const t of ['pointerdown', 'pointermove', 'pointerup']) document.addEventListener(t, (e) => window.__pt.push(e.pointerType), true); })()", sid)
                cdp.call("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]}, sid)
                for i in range(1, 7):
                    cdp.call("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y + i * 20}]}, sid)
                cdp.call("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []}, sid)
                self.assertTrue(wait(lambda: float(cdp.js(PCT, sid)) > 100), f"{width}: zoomed in by touch")
                self.assertGreater(cdp.js("document.querySelector('.mv-wrap').offsetHeight", sid), h + 60, f"{width}: taller")
                self.assertIn("touch", cdp.js("window.__pt", sid), f"{width}: the events were touch pointers")

    def test_the_ends_hold_once_settled_home_is_remembered_and_the_grip_is_off_the_paper(self):
        port = self.serve(CLASSIC)
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, HASH, port)
                for _ in range(12):
                    self.press(cdp, sid, "ArrowDown")
                self.assertTrue(wait(lambda: cdp.js(PCT, sid) == "70"), f"{width}: floor")
                cdp.js("new Promise((r) => setTimeout(r, 400))", sid)
                self.assertEqual(cdp.js(PCT, sid), "70", f"{width}: the floor holds after settling")
                self.assertEqual(cdp.js("document.querySelector('[data-grip]').getAttribute('aria-valuenow')", sid), "70")
                for _ in range(30):
                    self.press(cdp, sid, "ArrowUp")
                self.assertTrue(wait(lambda: cdp.js(PCT, sid) == "300"), f"{width}: ceiling")
                cdp.js("new Promise((r) => setTimeout(r, 400))", sid)
                self.assertEqual(cdp.js(PCT, sid), "300", f"{width}: the ceiling holds after settling")
                self.assertEqual(cdp.js("localStorage.getItem('clark.tlZoom.page')", sid), "3", f"{width}: ceiling remembered")
                self.press(cdp, sid, "Home")
                self.assertTrue(wait(lambda: cdp.js(PCT, sid) == "100"), f"{width}: Home is 100%")
                self.assertEqual(cdp.js("localStorage.getItem('clark.tlZoom.page')", sid), "1", f"{width}: Home remembered")

    def test_reset_puts_it_back_and_the_grip_is_off_the_paper(self):
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, HASH, port)
                self.press(cdp, sid, "ArrowDown")
                self.assertTrue(wait(lambda: cdp.js(PCT, sid) == "110"), f"{width}: Down raises on the Cards page")
                cdp.js("document.querySelector('[data-zreset]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js(PCT, sid) == "100"), f"{width}: Reset puts it back")
                self.assertNotEqual(cdp.js("getComputedStyle(document.querySelector('[data-grip]')).display", sid), "none", f"{width}: shown on screen")
                self.assertNotEqual(cdp.js("getComputedStyle(document.querySelector('.mv-box')).paddingBottom", sid), "0px", f"{width}: the screen keeps room for the grip")
                cdp.js("document.documentElement.classList.add('print-all')", sid)
                cdp.call("Emulation.setEmulatedMedia", {"media": "print"}, sid)
                self.assertEqual(cdp.js("getComputedStyle(document.querySelector('[data-grip]')).display", sid), "none", f"{width}: left off the paper")
                self.assertEqual(cdp.js("getComputedStyle(document.querySelector('.mv-box')).paddingBottom", sid), "0px", f"{width}: no room kept for a grip that is not printed")

    def test_the_zoom_caption_stays_inside_the_strip_above_the_grip(self):
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, "#dashboard&p=TUL", port)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.mv-cap')", sid), 10), f"{width}: the Dashboard section draws the caption")
                lift = cdp.js("(() => { const b = document.querySelector('.mv-box'); return b.getBoundingClientRect().bottom - document.querySelector('.mv-cap').getBoundingClientRect().bottom - parseFloat(getComputedStyle(b).getPropertyValue('--sb')); })()", sid)
                self.assertGreaterEqual(lift, 18, f"{width}: the caption is lifted over the strip's bottom edge, clear of the grip's room ({lift})")

    def test_the_arrow_keys_are_taken_by_the_grip_and_other_keys_are_not(self):
        port = self.serve(CLASSIC)
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, HASH, port)
                fire = "(k) => { const g = document.querySelector('[data-grip]'); g.focus(); return g.dispatchEvent(new KeyboardEvent('keydown', {key: k, bubbles: true, cancelable: true})); }"
                for k in ("ArrowDown", "ArrowUp", "Home"):
                    self.assertFalse(cdp.js(f"({fire})('{k}')", sid), f"{width}: {k} is handled, so the page does not scroll")
                self.assertTrue(cdp.js(f"({fire})('Tab')", sid), f"{width}: Tab is left alone")

    def synth(self, cdp, sid, kind, dy, pid=7, button=0):
        cdp.js(f"""(() => {{ const g = document.querySelector('[data-grip]'), r = g.getBoundingClientRect();
          g.dispatchEvent(new PointerEvent('{kind}', {{bubbles: true, cancelable: true, pointerId: {pid}, button: {button}, clientX: r.left + 5, clientY: r.top + 5 + {dy}}})); }})()""", sid)

    def test_a_cancelled_drag_stops_and_a_right_button_press_does_not_start_one(self):
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, HASH, port)
                self.synth(cdp, sid, "pointerdown", 0, button=2)
                self.synth(cdp, sid, "pointermove", 120)
                cdp.js("new Promise((r) => setTimeout(r, 200))", sid)
                self.assertEqual(cdp.js(PCT, sid), "100", f"{width}: the right button starts no drag")
                self.synth(cdp, sid, "pointerup", 120)
                self.synth(cdp, sid, "pointerdown", 0)
                self.assertEqual(cdp.js("document.querySelector('[data-grip]') === document.activeElement", sid), True, f"{width}: pressing the grip focuses it")
                self.synth(cdp, sid, "pointermove", 60)
                self.assertTrue(wait(lambda: float(cdp.js(PCT, sid)) > 100), f"{width}: a left press drags")
                self.synth(cdp, sid, "pointercancel", 60)
                now = cdp.js(PCT, sid)
                self.synth(cdp, sid, "pointermove", 200)
                cdp.js("new Promise((r) => setTimeout(r, 200))", sid)
                self.assertEqual(cdp.js(PCT, sid), now, f"{width}: after a cancel the grip no longer follows the pointer")


REAL = {"ArrowUp": 38, "ArrowDown": 40, "End": 35, "Home": 36}


def real_press(cdp, sid, key):
    """A real key press through the browser's input (not a dispatched event)."""
    for kind in ("rawKeyDown", "keyUp"):
        cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": key, "code": key, "windowsVirtualKeyCode": REAL[key]}, sid)


class DarkAndSideways(Classic, BrowserBase, unittest.TestCase):
    def test_the_grip_in_the_dark_theme_uses_the_dark_tokens_and_still_works(self):
        port = self.serve()
        read = """(() => { const g = document.querySelector('[data-grip]'), s = g.querySelector('span'), root = getComputedStyle(document.documentElement);
          const r = g.getBoundingClientRect(), w = document.querySelector('.mv-wrap').getBoundingClientRect();
          return {bar: getComputedStyle(s).borderTopColor, grey500: root.getPropertyValue('--grey-500').trim(), bg: getComputedStyle(document.body).backgroundColor,
                  dx: (r.left + r.width / 2) - (w.left + w.width / 2), shown: getComputedStyle(g).display, native: getComputedStyle(document.querySelector('.mv-wrap')).resize}; })()"""
        seen = {}
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with chrome() as cdp:
                    sid = page_target(cdp)
                    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
                    sid = self.visit(cdp, width, HASH, port)
                    got = cdp.js(read, sid)
                    where = f"{width} {scheme}"
                    self.assertNotEqual(got["shown"], "none", where)
                    self.assertEqual(got["native"], "none", where)
                    self.assertLess(abs(got["dx"]), 1.5, f"{where}: centred")
                    seen[(width, scheme)] = got
                    cdp.js("document.querySelector('[data-grip]').focus(); true", sid)
                    self.assertEqual(cdp.js("getComputedStyle(document.querySelector('[data-grip]')).outlineStyle", sid), "solid", f"{where}: a visible focus ring")
                    if scheme == "dark":
                        real_press(cdp, sid, "ArrowDown")
                        self.assertTrue(wait(lambda: cdp.js(PCT, sid) == "110"), f"{where}: a real Down press zooms one step")
                        real_press(cdp, sid, "Home")
                        self.assertTrue(wait(lambda: cdp.js(PCT, sid) == "100"), f"{where}: a real Home press goes to 100%")
        for width in (1400, 900):
            light, dark = seen[(width, "light")], seen[(width, "dark")]
            self.assertNotEqual(light["bg"], dark["bg"], f"{width}: the dark theme is really on")
            self.assertNotEqual(light["bar"], dark["bar"], f"{width}: the grip's bar follows the theme")
            self.assertNotEqual(dark["bar"], light["bar"])
            self.assertNotEqual(dark["bar"], dark["bg"], f"{width}: the bar can be seen against the dark page")

    def test_the_grip_stays_put_when_the_strip_scrolls_sideways(self):
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, HASH, port)
                cdp.js("document.querySelector('[data-grip]').focus(); true", sid)
                for _ in range(21):
                    real_press(cdp, sid, "ArrowDown")
                self.assertTrue(wait(lambda: cdp.js(PCT, sid) == "300"), f"{width}: zoomed to the most so the strip is wide")
                self.assertTrue(wait(lambda: cdp.js("(() => { const w = document.querySelector('.mv-wrap'); return w.scrollWidth > w.clientWidth + 50; })()", sid)), f"{width}: the strip scrolls sideways")
                spot = "(() => { const r = document.querySelector('[data-grip]').getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top), Math.round(r.width)]; })()"
                def settled():
                    a = cdp.js(spot, sid)
                    cdp.js("new Promise((r) => setTimeout(r, 350))", sid)
                    return cdp.js(spot, sid) == a
                self.assertTrue(wait(settled, 20), f"{width}: the strip finished growing before the scroll starts")
                before = cdp.js(spot, sid)
                seen = []
                for left in ("1e6", "200", "0"):
                    got = cdp.js(f"(() => {{ const w = document.querySelector('.mv-wrap'); w.scrollTo({{left: {left}, behavior: 'instant'}}); return w.scrollLeft; }})()", sid)
                    seen.append(round(got))
                    cdp.js("new Promise((r) => setTimeout(r, 150))", sid)
                    now = cdp.js(spot, sid)
                    self.assertEqual(now[0], before[0], f"{width}: the grip did not move sideways with the strip (scrollLeft {got})")
                    self.assertEqual(now[2], before[2], f"{width}: its width held (scrollLeft {got})")
                    self.assertLessEqual(abs(now[1] - before[1]), 2, f"{width}: it did not move up or down either (scrollLeft {got})")
                self.assertGreater(seen[0], 200, f"{width}: the strip really scrolled to its far end ({seen})")
                self.assertEqual(seen[2], 0, f"{width}: and back to the start ({seen})")
                self.assertEqual(cdp.js("document.querySelector('.mv-wrap').contains(document.querySelector('[data-grip]'))", sid), False, f"{width}: it sits in the box, outside the scrolling strip")
                self.assertEqual(cdp.js("document.querySelector('[data-grip]') === document.activeElement", sid), True, f"{width}: focus stayed on it")


OVER = "(() => { const w = document.querySelector('.mv-wrap'); return [w.scrollWidth, w.clientWidth, document.querySelectorAll('[data-grip]').length, document.querySelectorAll('.mv-mk').length]; })()"


class Overflow(Classic, BrowserBase, unittest.TestCase):
    """Row 1267 (AP5): the grip shows only when the timeline overflows its box (scrollWidth > clientWidth), whatever the number of milestones."""

    DATES = ["2026-11-10"]

    def serve(self, theme=CLASSIC, dates=None):
        want = dates or self.DATES

        def shaped(code, archived="hide"):
            d = copy.deepcopy(self.store.data_for(code, archived))
            ms = []
            for i, at in enumerate(want):
                m = copy.deepcopy(d["milestones"][i % len(d["milestones"])])
                m.update({"id": f"{code}-M-9{i}", "name": f"Step {i + 1}", "baseline_date": at, "forecast_date": None, "actual_date": None, "status": "Planned", "state": None, "state_set": 0, "movement": None})
                ms.append(m)
            d["milestones"] = ms
            return d
        s = Running(data_for=shaped, projects=lambda archived=False: self.projects, page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=theme))
        self.addCleanup(s.close)
        return s.port

    def check(self, dates, grip, count=None):
        port = self.serve(dates=dates)
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, HASH, port)
                sw, cw, grips, marks = cdp.js(OVER, sid)
                self.assertEqual(marks, count or len(dates), f"{width}: the line is drawn")
                self.assertEqual(sw > cw, grip, f"{width}: the line {'overflows' if grip else 'fits'} its box ({sw} in {cw})")
                self.assertEqual(grips, 1 if grip else 0, f"{width}: the grip shows exactly when the line overflows ({sw} in {cw})")

    def test_one_milestone_that_fits_has_no_grip(self):
        self.check(["2026-11-10"], False)

    def test_six_milestones_close_together_fit_and_have_no_grip(self):
        self.check(["2026-11-02", "2026-11-05", "2026-11-09", "2026-11-12", "2026-11-16", "2026-11-20"], False)

    def test_six_milestones_spread_over_years_overflow_and_have_the_grip(self):
        self.check(["2026-06-01", "2026-12-01", "2027-06-01", "2027-12-01", "2028-06-01", "2028-12-01"], True)

    def test_one_milestone_far_from_today_overflows_and_has_the_grip(self):
        self.check(["2029-06-01"], True)

    def test_two_milestones_far_apart_overflow_though_few(self):
        self.check(["2026-06-01", "2028-06-01"], True)

    def test_a_stored_zoom_keeps_the_grip_on_a_line_that_fits_so_it_can_be_put_back(self):
        port = self.serve(dates=["2026-11-10"])
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, HASH, port)
                cdp.js("localStorage.setItem('clark.tlZoom.page', '0.7'); true", sid)
                reload_to_new_page_cdp(cdp, sid, what=f"{width}: the page reloaded")
                self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.mv-mk').length", sid) == 1), f"{width}: drawn")
                sw, cw, grips, _ = cdp.js(OVER, sid)
                self.assertLessEqual(sw, cw, f"{width}: fits")
                self.assertEqual(grips, 1, f"{width}: a zoom other than 100% is stored: the grip stays though it fits")

    def test_the_grip_comes_when_the_window_narrows_and_goes_when_it_widens(self):
        port = self.serve(dates=["2026-09-01", "2027-01-01"])
        with chrome() as cdp:
            sid = self.visit(cdp, 1400, HASH, port)
            def metrics(width):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
            sw, cw, grips, _ = cdp.js(OVER, sid)
            self.assertLessEqual(sw, cw, "wide window: the line fits")
            self.assertEqual(grips, 0, "wide window: no grip")
            metrics(900)
            self.assertTrue(wait(lambda: cdp.js(OVER, sid)[2] == 1), "the window narrowed, the line overflows: the grip comes")
            metrics(1400)
            self.assertTrue(wait(lambda: cdp.js(OVER, sid)[2] == 0), "the window widened, the line fits: the grip goes")


class KeyGuards(Classic, BrowserBase, unittest.TestCase):
    def test_a_modified_key_is_left_to_the_browser_and_a_handled_key_is_claimed(self):
        port = self.serve(CLASSIC)
        fire = """(init) => { const g = document.querySelector('[data-grip]'); g.focus();
          return [['ArrowUp', {}], ['ArrowUp', {altKey: true}], ['ArrowUp', {ctrlKey: true}], ['ArrowUp', {metaKey: true}], ['Home', {ctrlKey: true}]].map(([key, m]) => {
            const e = new KeyboardEvent('keydown', Object.assign({key, bubbles: true, cancelable: true}, m)); g.dispatchEvent(e); return e.defaultPrevented; }); }"""
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, HASH, port)
                self.assertEqual(cdp.js(f"({fire})()", sid), [True, False, False, False, False], f"{width}: only the bare key is claimed")
                self.assertTrue(wait(lambda: cdp.js(PCT, sid) == "110"), f"{width}: one bare Up moved it, the modified ones did not")


class CardsKeepsItsGrip(Overflow):
    """Cards is frozen: it has none of the Classic grip rule (the grip stays on a short line, Up lowers and Down raises as on main, End is not a key), and Classic has all of it."""
    DATES = ["2026-11-10", "2026-11-12"]

    def serve(self, theme=None):
        return super().serve(theme)

    def test_one_milestone_that_fits_has_no_grip(self): pass
    def test_six_milestones_close_together_fit_and_have_no_grip(self): pass
    def test_six_milestones_spread_over_years_overflow_and_have_the_grip(self): pass
    def test_one_milestone_far_from_today_overflows_and_has_the_grip(self): pass
    def test_two_milestones_far_apart_overflow_though_few(self): pass
    def test_a_stored_zoom_keeps_the_grip_on_a_line_that_fits_so_it_can_be_put_back(self): pass
    def test_the_grip_comes_when_the_window_narrows_and_goes_when_it_widens(self): pass

    def test_cards_keeps_the_grip_on_a_line_of_two_and_its_old_keys(self):
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, HASH, port)
                self.assertEqual(cdp.js("document.querySelectorAll('[data-grip]').length", sid), 1, f"{width}: Cards draws the grip on two milestones")
                self.assertEqual(cdp.js("!document.querySelector('#theme')", sid), True, f"{width}: this is the Cards page")
                self.press(cdp, sid, "ArrowDown")
                self.assertTrue(wait(lambda: cdp.js(PCT, sid) == "110"), f"{width}: Down raises, as on main")
                self.press(cdp, sid, "ArrowUp")
                self.assertTrue(wait(lambda: cdp.js(PCT, sid) == "100"), f"{width}: Up lowers, as on main")
                self.press(cdp, sid, "ArrowRight")
                self.press(cdp, sid, "End")
                cdp.js("new Promise((r) => setTimeout(r, 300))", sid)
                self.assertEqual(cdp.js(PCT, sid), "100", f"{width}: Right and End are not Cards grip keys")
                self.assertEqual(cdp.js("(() => { const g = document.querySelector('[data-grip]'); const e = new KeyboardEvent('keydown', {key: 'End', bubbles: true, cancelable: true}); g.dispatchEvent(e); return e.defaultPrevented; })()", sid), False, f"{width}: End is left to the browser")

    def test_classic_gets_the_rule_on_the_same_data(self):
        port = Overflow.serve(self, CLASSIC)
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, HASH, port)
                self.assertEqual(cdp.js("!!document.querySelector('#theme')", sid), True, f"{width}: this is the Classic page")
                self.assertEqual(cdp.js("document.querySelectorAll('[data-grip]').length", sid), 0, f"{width}: Classic leaves the grip off two milestones")
                self.assertEqual(cdp.js("document.querySelectorAll('.mv-mk').length", sid), 2, f"{width}: the line is drawn")


if __name__ == "__main__":
    unittest.main()
