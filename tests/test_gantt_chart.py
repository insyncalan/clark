"""#926, the Gantt chart on the page (src/clark/page/src/gantt/components/GanttChart.jsx): View and Edit, at 1400 and 900 px, light and dark.
It mounts the component on a bare page with fictional lines (tests/fixtures/gantt_demo.jsx, a test-only mount that plays the part of the page
holding it: the chart has no store and saves nothing, so every change comes back as a callback that the mount records). The rules themselves
are tested in test_gantt_logic.py.

Run: python3 dev/run_tests.py test_gantt_chart
Needs Chrome: these tests fail, never skip, without it.
"""
import contextlib
import json
import re
import sys
import unittest

from _paths import SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402

from test_gantt_logic import LINES, TODAY, ln, page_html  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402

GANTT_SRC = SRC / "clark" / "page" / "src" / "gantt"


def lit(x):
    return json.dumps(x)


def rgb(text):
    nums = [float(n) for n in re.findall(r"[\d.]+", text)[:3]]
    if text.startswith("color(srgb"):      # a mixed colour comes back as fractions of 1 (color-mix)
        nums = [n * 255 for n in nums]
    return nums


def lum(c):
    f = lambda v: (v / 255 / 12.92) if v / 255 <= 0.03928 else (((v / 255) + 0.055) / 1.055) ** 2.4
    r, g, b = (f(v) for v in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def over(top, back, alpha):
    return [top[i] * alpha + back[i] * (1 - alpha) for i in range(3)]


class Static(unittest.TestCase):
    def test_the_chart_uses_tokens_only_and_no_person_is_named(self):
        css = (build_page.PAGE / "shell.css").read_text(encoding="utf-8")
        block = css[css.index("The project Gantt chart (row 926)"):]
        self.assertNotRegex(block, r"#[0-9a-fA-F]{3,8}\b", "a colour in the chart's rules is a token, never a hex")
        self.assertNotRegex(block, r"\brgba?\(", "a colour in the chart's rules is a token")
        widths = set(re.findall(r"@media \(max-width: (\d+)px\)", block))
        self.assertLessEqual(widths, {"900"}, "only the widths 1400 and 900 are designed for")
        for f in GANTT_SRC.rglob("*.js*"):
            text = f.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"#[0-9a-fA-F]{6}\b", f"{f.name}: no hex colour")


class Chart(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, cls.sid)
        cls.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{cls.server.port}/"}, cls.sid)
        assert wait(lambda: cls.cdp.js("!!(window.mountGantt && window.K)", cls.sid)), "the test bundle ran"

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    # ── helpers ──────────────────────────────────────────────────────────────

    def js(self, expr):
        return self.cdp.js(expr, self.sid)

    def val(self, expr):
        got = self.js(f"(function(){{ try {{ return JSON.stringify({expr}); }} catch (e) {{ return 'ERROR ' + e.message; }} }})()")
        self.assertIsNotNone(got, expr)
        self.assertFalse(got.startswith("ERROR"), f"{expr}: {got}")
        return json.loads(got)

    def until(self, expr, what):
        self.assertTrue(wait(lambda: self.js(f"!!({expr})"), 8), what)

    def look(self, width, scheme):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        self.js(f"document.documentElement.dataset.theme = {lit(scheme)}; document.body.style.margin = '0'; document.body.style.padding = '0 20px'")
        self.motion("no-preference")      # the clash arrow's dash is a Motion-block rule: a Mac set to reduce motion would otherwise lose it and this test would fail by the runner's own setting

    def motion(self, value):
        self.cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": value}]}, self.sid)

    def mount(self, edit=False, width=None, lines=LINES, **opts):
        width = width or int(self.js("innerWidth")) - 40
        self.js(f"mountGantt({lit(lines)}, {lit({'edit': edit, 'today': TODAY, 'width': width, **opts})})")
        self.until("document.querySelector('[data-gantt]')", "the chart is on the page")
        self.until("document.querySelector('[data-g-bar]')", "bars are drawn")

    def calls(self):
        return self.val("window.calls")

    def count(self, sel):
        return self.val(f"document.querySelectorAll({lit(sel)}).length")

    def text(self, sel):
        return self.js(f"(function(){{ var e = document.querySelector({lit(sel)}); return e ? e.textContent.replace(/\\s+/g, ' ').trim() : null; }})()")

    def mouse(self, kind, x, y, **kw):
        self.cdp.call("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, "button": "left", **kw}, self.sid)

    def drag(self, x0, y0, dx):
        self.mouse("mouseMoved", x0, y0)
        self.mouse("mousePressed", x0, y0, buttons=1, clickCount=1)
        for step in range(1, 5):
            self.mouse("mouseMoved", x0 + dx * step / 4, y0, buttons=1)
        self.mouse("mouseReleased", x0 + dx, y0, buttons=0, clickCount=1)

    def centre(self, sel):
        r = self.val(f"(function(){{ var r = document.querySelector({lit(sel)}).getBoundingClientRect(); return {{x: r.left + r.width / 2, y: r.top + r.height / 2, l: r.left, r: r.right, w: r.width}}; }})()")
        return r

    def ppd(self, id):
        return self.val(f"(function(){{ var el = document.querySelector('[data-g-bar=\"{id}\"]'); var l = hostLines().find(x => x.id === '{id}'); return el.getBoundingClientRect().width / K.gantt.spanDays(l); }})()")

    def keypress(self, sel, key):
        self.js(f"document.querySelector({lit(sel)}).dispatchEvent(new KeyboardEvent('keydown', {{key: {lit(key)}, bubbles: true}}))")

    def set_input(self, sel, value):
        self.js(f"(function(){{ var e = document.querySelector({lit(sel)}); e.value = {lit(value)}; e.dispatchEvent(new Event('change', {{bubbles: true}})); }})()")

    def checks_for_every_look(self, edit):
        """What holds at every width and in both colour schemes."""
        fits = self.val("(function(){ var h = document.getElementById('host').getBoundingClientRect(); var out = [];"
                        "document.querySelectorAll('.gt-bar > *, .gt-grip, .gt-legend, .gt-detail, .gt-gx').forEach(function(e){ var r = e.getBoundingClientRect();"
                        "if (r.width && (r.left < h.left - 1 || r.right > h.right + 1)) out.push(e.className + ' ' + Math.round(r.left) + '-' + Math.round(r.right) + ' in ' + Math.round(h.left) + '-' + Math.round(h.right)); });"
                        "if (document.documentElement.scrollWidth > innerWidth) out.push('page scrolls sideways'); return out; })()")
        self.assertEqual(fits, [], "nothing runs outside the chart's box and the page never scrolls sideways")
        small = self.val("(function(){ var out = []; document.querySelectorAll('.gt *').forEach(function(e){ if (!e.childNodes.length) return;"
                         "var t = [].some.call(e.childNodes, function(n){ return n.nodeType === 3 && n.textContent.trim(); }); if (!t) return;"
                         "var s = parseFloat(getComputedStyle(e).fontSize); if (s < 13) out.push(e.className + ' ' + s); }); return out; })()")
        self.assertEqual(small, [], "no text under 13 px")
        self.assertEqual(self.val("getComputedStyle(document.querySelector('.gt-gx')).scrollbarWidth"), "none", "no scrollbars")
        # text on a task bar, on its lighter done part, on a phase bar, and on the Today flag
        c = self.val("(function(){ var s = function(sel, p){ return getComputedStyle(document.querySelector(sel))[p]; };"
                     "return {tb: s('.gt-b-task', 'backgroundColor'), tf: s('.gt-b-task', 'color'), pb: s('.gt-b-phase', 'backgroundColor'), pe: s('.gt-b-phase', 'borderTopColor'), pf: s('.gt-phlab', 'color'), pr: s('.gt-rw.gt-phase', 'backgroundColor'),"
                     "fb: s('.gt-tflag', 'backgroundColor'), ff: s('.gt-tflag', 'color'), white: s('.gt-b-task', 'color')}; })()") if self.count(".gt-b-task") else None
        if c:
            white = [255, 255, 255]
            self.assertGreaterEqual(contrast(rgb(c["tf"]), rgb(c["tb"])), 4.5, "task bar text")
            self.assertGreaterEqual(contrast(rgb(c["tf"]), over(white, rgb(c["tb"]), 0.3)), 4.5, "task bar text on the lighter done part")
            self.assertGreaterEqual(contrast(rgb(c["pf"]), rgb(c["pr"])), 4.5, "phase name beside its bar, on the phase row")   # the name sits beside a thin bar since the polish
            self.assertGreaterEqual(max(contrast(rgb(c["pe"]), rgb(c["pr"])), contrast(rgb(c["pb"]), rgb(c["pr"]))), 3, "the phase bar (its fill or its edge) against its row")
            self.assertGreaterEqual(contrast(rgb(c["ff"]), rgb(c["fb"])), 4.5, "Today flag text")
        flag, upper = self.val("[document.querySelector('.gt-tflag').getBoundingClientRect().bottom, document.querySelector('.gt-hc.gt-u').getBoundingClientRect().top]")
        self.assertLessEqual(flag, upper + 1, "the Today flag sits above the dates")

    # ── View ─────────────────────────────────────────────────────────────────

    def test_row_988_the_header_row_stays_in_view_with_many_lines(self):
        """#988: with 500 lines the chart is bounded and scrolls inside itself, so the header row is never scrolled off the window."""
        many = [ln(f"GNT-{i:03d}", f"Task {i}", "task", "2026-09-01", "2026-10-14") for i in range(1, 501)]
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme):
                    self.look(width, scheme)
                    self.mount(edit=False, lines=many)
                    self.js("window.scrollTo(0, 3000)")
                    top, bottom, vh = self.val("(function(){ var r = document.querySelector('.gt-rhead').getBoundingClientRect(); return [r.top, r.bottom, innerHeight]; })()")
                    self.assertGreaterEqual(top, 0, "the header row is not above the window")
                    self.assertLessEqual(bottom, vh, "the header row is inside the window")
                    gx = self.val("(function(){ var g = document.querySelector('.gt-gx'); return [g.clientHeight, g.scrollHeight]; })()")
                    self.assertLess(gx[0], gx[1], "the chart scrolls inside its own box")

    def test_view_at_every_width_and_in_both_schemes(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme):
                    self.look(width, scheme)
                    self.mount(edit=False)
                    self.checks_for_every_look(False)
                    self.assertEqual(self.val("[...document.querySelectorAll('[data-g-row]')].map(e => e.dataset.gRow)"),
                                     ["GNT-001", "GNT-003", "GNT-004", "GNT-007", "GNT-008", "GNT-011"], "View draws only the lines whose eye is on")
                    self.assertEqual(self.val("[...document.querySelectorAll('[data-g-no]')].map(e => e.dataset.gNo)"), ["1", "M-1", "2", "M-2", "3", "M-3"])
                    self.assertEqual(self.count("input, [data-g-eye], [data-g-add], [data-g-coleye], [data-rz]"), 0, "View has nothing to change")
                    self.assertEqual(self.count("[data-g-bar][data-g-type=phase]"), 3)
                    self.assertEqual(self.count("[data-g-bar][data-g-type=milestone]"), 3)
                    self.assertEqual(self.count("[data-g-count]"), 0)
                    self.assertEqual(self.text("[data-g-cell=start]"), "01-09-2026")
                    self.assertEqual(self.val("[...document.querySelectorAll('.gt-lhead .gt-h')].map(e => e.textContent.trim())"), ["Phase / task", "Start", "End", "Done"])
                    self.assertEqual(self.text("[data-g-today]"), "Today")

    def test_every_bar_carries_its_name_as_text(self):
        self.look(1400, "light")
        self.mount(edit=True)
        names = self.val("(function(){ var out = []; hostLines().forEach(function(l){ var q = document.querySelector('.gt-canvas'); if (q.textContent.indexOf(l.name) < 0) out.push(l.name); }); return out; })()")
        self.assertEqual(names, [], "a bar's name is in the page as text, inside the bar or beside it")

    def test_start_end_and_done_are_always_drawn_and_have_no_eye(self):
        self.look(1400, "light")
        for edit in (False, True):
            self.mount(edit=edit)
            self.assertEqual(self.val("[...document.querySelectorAll('.gt-lhead .gt-h')].map(e => e.textContent.trim())"), ["Phase / task", "Start", "End", "Done"])
            self.assertEqual(self.count("[data-g-coleye]"), 0, "the data layer never hides these, so the chart offers no eye on them")

    def test_a_clash_arrow_with_reduced_motion_has_no_dash_but_is_still_heavier_than_a_link(self):
        """The dash is set only where motion is allowed (the Motion block), so with reduced motion the clash is told apart by the heavier stroke, not colour alone."""
        self.look(1400, "light")
        self.motion("reduce")
        self.mount(edit=True)
        self.assertEqual(self.val("getComputedStyle(document.querySelector('[data-g-clash-arrow] path')).strokeDasharray"), "none")
        clash = float(self.val("parseFloat(getComputedStyle(document.querySelector('[data-g-clash-arrow] path')).strokeWidth)"))
        link = float(self.val("parseFloat(getComputedStyle(document.querySelector('[data-g-arrow]:not([data-g-clash-arrow]) path')).strokeWidth)"))
        self.assertGreater(clash, link, "the clash arrow is heavier than an ordinary link")

    def test_selecting_a_bar_says_its_details_in_words(self):
        self.look(1400, "light")
        self.mount(edit=False)
        self.assertIn("Select a bar or a milestone", self.text("[data-g-detail]"))
        self.js("document.querySelector('[data-g-bar=GNT-004]').click()")
        self.until("document.querySelector('[data-g-detail] b')", "the details")
        d = self.text("[data-g-detail]")
        self.assertIn("2 Migration · Phase · 22-10-2026 to 26-02-2027", d)
        self.assertIn("30% done · In progress", d)
        self.assertIn("On the dashboard: Yes", d)

    def test_scales_zoom_and_the_height_grip_in_view(self):
        self.look(1400, "light")
        self.mount(edit=False)
        month = self.text(".gt-rhead")
        self.assertIn("Sep 26", month)
        self.js("document.querySelector('[data-g-scale=quarter]').click()")
        self.until("document.querySelector('.gt-rhead').textContent.indexOf('Q4 2026') >= 0", "the quarter scale")
        self.js("document.querySelector('[data-g-scale=week]').click()")
        self.until("document.querySelector('[data-g-scale=week]').getAttribute('aria-pressed') === 'true'", "the week scale")
        self.js("document.querySelector('[data-g-scale=month]').click()")
        self.until("document.querySelector('[data-g-scale=month]').getAttribute('aria-pressed') === 'true'", "back to month")
        self.assertTrue(self.val("document.querySelector('[data-g-zout]').disabled"), "zoom out is not offered at fit: never below fit")
        w0 = self.val("document.querySelector('[data-g-canvas]').getBoundingClientRect().width")
        self.js("document.querySelector('[data-g-zin]').click()")
        self.until("document.querySelector('[data-g-fit]').textContent === '125%'", "zoomed in")
        self.assertGreater(self.val("document.querySelector('[data-g-canvas]').getBoundingClientRect().width"), w0 * 1.2)
        self.js("document.querySelector('[data-g-fit]').click()")
        self.until("document.querySelector('[data-g-fit]').textContent === '100%'", "back to fit")
        self.assertAlmostEqual(self.val("document.querySelector('[data-g-canvas]').getBoundingClientRect().width"), w0, delta=1)
        # the grip: a viewer changes only their own height, in whole rows
        self.assertEqual(self.val("document.querySelector('[data-g-grip]').getAttribute('aria-valuenow')"), "6")
        self.keypress("[data-g-grip]", "ArrowUp")
        self.until("document.querySelector('[data-g-grip]').getAttribute('aria-valuenow') === '5'", "one row fewer")
        self.assertEqual(self.val("Math.round(document.querySelector('[data-g-gx]').getBoundingClientRect().height)"), 68 + 5 * 32 + 2)
        self.keypress("[data-g-grip]", "Home")
        self.until("document.querySelector('[data-g-grip]').getAttribute('aria-valuenow') === '1'", "never below one row")
        self.keypress("[data-g-grip]", "ArrowUp")
        self.keypress("[data-g-grip]", "End")
        self.until("document.querySelector('[data-g-grip]').getAttribute('aria-valuenow') === '6'", "never beyond the last row")
        self.assertEqual(self.calls(), [], "a viewer's own height is never sent anywhere")

    def test_the_grip_follows_the_pointer_by_whole_rows(self):
        self.look(1400, "light")
        self.mount(edit=False, defaultRows=3)
        self.assertEqual(self.val("document.querySelector('[data-g-grip]').getAttribute('aria-valuenow')"), "3")
        g = self.centre("[data-g-grip]")
        self.mouse("mouseMoved", g["x"], g["y"])
        self.mouse("mousePressed", g["x"], g["y"], buttons=1, clickCount=1)
        self.mouse("mouseMoved", g["x"], g["y"] + 70, buttons=1)
        self.mouse("mouseReleased", g["x"], g["y"] + 70, buttons=0, clickCount=1)
        self.until("document.querySelector('[data-g-grip]').getAttribute('aria-valuenow') === '5'", "two rows more (70 px is 2.2 rows)")
        self.assertEqual(self.calls(), [])

    def test_expand_to_full_screen_and_back(self):
        self.look(1400, "light")
        self.mount(edit=False)
        self.js("document.querySelector('[data-g-expand]').click()")
        self.until("document.querySelector('[data-gantt]').dataset.full === '1'", "full screen")
        self.assertEqual(self.val("getComputedStyle(document.querySelector('[data-gantt]')).position"), "fixed")
        self.assertEqual(self.val("document.querySelector('[data-g-expand]').getAttribute('aria-label')"), "Back to page width")
        # the page listens for Escape once its effect has run (a moment after the screen changes), so a key sent that first instant may find no listener: send it until it is heard
        esc = "document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true})), document.querySelector('[data-gantt]').dataset.full === '0'"
        self.assertTrue(wait(lambda: self.js(f"!!({esc})"), 8), "Escape goes back")

    def test_the_show_menu_has_no_ticked_lines_in_view(self):
        self.look(1400, "light")
        self.mount(edit=False)
        self.js("document.querySelector('[data-g-show]').click()")
        self.until("document.querySelector('[data-g-showmenu]')", "the menu")
        self.assertEqual(self.val("[...document.querySelectorAll('[data-g-filter]')].map(e => e.textContent.replace('✓', '').trim())"), ["All lines", "Phases only", "Phases and milestones"])
        self.js("document.querySelector('[data-g-filter=phases]').click()")
        self.until("document.querySelectorAll('[data-g-row]').length === 3", "phases only")
        self.assertEqual(self.val("document.querySelector('[data-g-show]').getAttribute('aria-label')"), "Show: Phases only")

    def test_an_empty_plan_says_so(self):
        self.look(1400, "light")
        self.js(f"mountGantt([], {lit({'edit': False, 'today': TODAY})})")
        self.until("document.querySelector('[data-g-none]')", "the empty words")
        self.assertEqual(self.text("[data-g-none]"), "No lines to show.")

    # ── Edit ─────────────────────────────────────────────────────────────────

    def test_edit_at_every_width_and_in_both_schemes(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme):
                    self.look(width, scheme)
                    self.mount(edit=True)
                    self.checks_for_every_look(True)
                    self.assertEqual(self.count("[data-g-row]"), 11, "Edit draws every line")
                    self.assertEqual(self.count("[data-g-eye]"), 11)
                    self.assertEqual(self.count("[data-g-add]"), 11)
                    self.assertEqual(self.text("[data-g-count]"), "11 of 11 lines shown")
                    self.assertEqual(self.count("[data-g-arrow]"), 6)
                    self.assertEqual(self.count("[data-g-clash-arrow]"), 1, "one arrow is a clash")
                    self.assertEqual(self.val("getComputedStyle(document.querySelector('[data-g-clash-arrow] path')).strokeDasharray"), "4px, 3px", "the clash arrow is dashed")
                    self.assertEqual(self.count("[data-g-clash]"), 1)
                    self.assertEqual(self.val("document.querySelector('[data-g-clash]').dataset.gClash"), "GNT-006")
                    self.assertEqual(self.val("[...document.querySelectorAll('.gt-lhead .gt-h')].map(e => e.textContent.trim())"), ["Phase / task", "Start", "End", "Done"])
                    self.assertEqual(self.val("document.querySelectorAll('[data-g-rz]').length"), 4, "each of the four columns can be resized")

    def test_a_clash_is_said_in_words(self):
        self.look(1400, "light")
        self.mount(edit=True)
        self.js("document.querySelector('[data-g-bar=GNT-006]').click()")
        self.until("document.querySelector('[data-g-detail-clash]')", "the clash is named")
        self.assertEqual(self.text("[data-g-detail-clash]"), "Starts before 2.1 ends")
        self.assertEqual(self.val("document.querySelector('[data-g-clash]').title"), "Starts before 2.1 ends")

    def test_the_eye_puts_a_line_on_and_takes_it_off_the_client_view(self):
        self.look(1400, "light")
        self.mount(edit=True)
        self.assertEqual(self.val("document.querySelector('[data-g-eye=GNT-002]').getAttribute('aria-pressed')"), "false")
        self.js("document.querySelector('[data-g-eye=GNT-002]').click()")
        self.until("window.calls.length", "the click was passed on")
        self.assertEqual(self.calls(), [["eye", "GNT-002"]])
        self.until("document.querySelector('[data-g-eye=GNT-002]').getAttribute('aria-pressed') === 'true'", "the eye is on")

    def test_an_inline_cell_changes_a_line_and_a_bad_value_is_refused_in_words(self):
        self.look(1400, "light")
        self.mount(edit=True)
        self.set_input('[data-g-edit="GNT-005:name"]', "Train the staff")
        self.until("window.calls.length", "the name change")
        self.assertEqual(self.calls(), [["change", "GNT-005", "name", "Train the staff"]])
        self.set_input('[data-g-edit="GNT-005:pct"]', "75")
        self.until("window.calls.length === 2", "the done change")
        self.assertEqual(self.calls()[1], ["change", "GNT-005", "pct", 75])
        self.set_input('[data-g-edit="GNT-005:end"]', "10-12-2026")
        self.until("window.calls.length === 3", "the end change")
        self.assertEqual(self.calls()[2], ["change", "GNT-005", "dates", {"start": "2026-10-22", "end": "2026-12-10"}])
        for field, text, words in (("start", "next week", "Use DD-MM-YYYY, for example 06-11-2026."), ("end", "01-01-2026", "The end cannot be before the start."),
                                   ("pct", "101", "Done % is a number from 0 to 100."), ("name", " ", "A line needs a name.")):
            self.set_input(f'[data-g-edit="GNT-005:{field}"]', text)
            self.until(f"document.querySelector('[data-g-msg]') && document.querySelector('[data-g-msg]').textContent === {lit(words)}", f"{field}: the refusal is shown in words")
            self.assertEqual(len(self.calls()), 3, f"{field}: nothing was sent")
        self.assertEqual(self.count('[data-g-edit="GNT-003:end"]'), 0, "a milestone has one date: it has no End cell")

    def test_add_a_line_below_asks_what_kind(self):
        self.look(1400, "light")
        self.mount(edit=True)
        self.js("document.querySelector('[data-g-add=GNT-004]').click()")
        self.until("document.querySelector('[data-g-addmenu]')", "the menu")
        self.assertEqual(self.val("[...document.querySelectorAll('[data-g-addtype]')].map(e => e.textContent.trim())"),
                         ["Add a task below", "Add a phase below", "Add a milestone below"])
        self.js("document.querySelector('[data-g-addtype=task]').click()")
        self.until("document.querySelectorAll('[data-g-row]').length === 12", "the line is added")
        self.assertEqual(self.calls(), [["add", "GNT-004", "task"]])
        self.assertEqual(self.val("document.querySelectorAll('[data-g-row]')[4].dataset.gNo"), "2.1", "the new task is 2.1 and the others moved down")
        self.assertEqual(self.val("document.querySelector('[data-g-row=GNT-005]').dataset.gNo"), "2.2")
        self.assertEqual(self.text("[data-g-count]"), "12 of 12 lines shown")

    def test_double_click_a_bar_opens_the_edit_box(self):
        self.look(1400, "light")
        self.mount(edit=True)
        self.js("document.querySelector('[data-g-bar=GNT-005]').dispatchEvent(new MouseEvent('dblclick', {bubbles: true}))")
        self.until("document.querySelector('[data-g-box]')", "the box")
        self.assertEqual(self.val("document.querySelector('[data-g-bn]').value"), "Staff training")
        self.assertEqual(self.val("document.querySelector('[data-g-bs]').value"), "22-10-2026")
        self.assertEqual(self.val("document.querySelector('[data-g-be]').value"), "04-12-2026")
        self.assertEqual(self.val("document.querySelector('[data-g-bp]').value"), "60")
        self.until("document.activeElement === document.querySelector('[data-g-bn]')", "the name is ready to type over (focus is set in an effect, just after the box appears)")
        # a bad end keeps the box open and says why
        self.set_input("[data-g-be]", "01-10-2026")
        self.js("(function(){ var e = document.querySelector('[data-g-be]'); e.value = '01-10-2026'; e.dispatchEvent(new Event('input', {bubbles: true})); })()")
        self.js("document.querySelector('[data-g-bsave]').click()")
        self.until("document.querySelector('[data-g-bmsg]').textContent", "the refusal")
        self.assertEqual(self.text("[data-g-bmsg]"), "The end cannot be before the start.")
        self.assertEqual(self.calls(), [])
        # a good change is sent as the changes only
        self.js("(function(){ var s = function(sel, v){ var e = document.querySelector(sel); e.value = v; e.dispatchEvent(new Event('input', {bubbles: true})); };"
                "s('[data-g-be]', '10-12-2026'); s('[data-g-bp]', '80'); })()")
        self.js("document.querySelector('[data-g-bsave]').click()")
        self.until("window.calls.length === 2", "two changes")
        self.assertEqual(self.calls(), [["change", "GNT-005", "dates", {"start": "2026-10-22", "end": "2026-12-10"}], ["change", "GNT-005", "pct", 80]])
        self.until("!document.querySelector('[data-g-box]')", "the box closed")

    def test_the_edit_box_stays_inside_the_window_at_900_and_1400(self):
        for width in (900, 1400):
            for scheme, shift in (("light", 0), ("dark", 0), ("light", 45), ("dark", 45)):
                with self.subTest(width=width, scheme=scheme, shift=shift):
                    self.look(width, scheme)
                    self.mount(edit=True)
                    # the live page sits in a moved box (a transform makes a fixed box start from that box, not the window): 45 px in
                    self.js(f"document.body.style.transform = {lit(f'translate({shift}px, {shift}px)') if shift else lit('')}")
                    for bar in ("GNT-005", "GNT-007", "GNT-001"):
                        self.js(f"document.querySelector('[data-g-bar={bar}]').dispatchEvent(new MouseEvent('dblclick', {{bubbles: true}}))")
                        self.until("document.querySelector('[data-g-box]')", "the box")
                        r = self.val("(function(){ var r = document.querySelector('[data-g-box]').getBoundingClientRect(); return {l: r.left, t: r.top, r: r.right, b: r.bottom, w: innerWidth, h: innerHeight, s: document.querySelector('[data-g-bsave]').getBoundingClientRect().right}; })()")
                        self.assertGreaterEqual(r["l"], 0, f"{bar} {r}")
                        self.assertGreaterEqual(r["t"], 0, f"{bar} {r}")
                        self.assertLessEqual(r["r"], r["w"] - 8, f"{bar} {r}")
                        self.assertLessEqual(r["b"], r["h"] - 8, f"{bar} {r}")
                        self.assertLessEqual(r["s"], r["w"], f"Save is inside {bar} {r}")
                        self.js("document.querySelector('[data-g-bcancel]').click()")
                        self.until("!document.querySelector('[data-g-box]')", "closed")
                    self.js("document.body.style.transform = ''")

    def test_the_edit_box_can_be_cancelled_and_can_delete_the_line(self):
        self.look(1400, "light")
        self.mount(edit=True)
        self.js("document.querySelector('[data-g-bar=GNT-003]').dispatchEvent(new MouseEvent('dblclick', {bubbles: true}))")
        self.until("document.querySelector('[data-g-box]')", "the box")
        self.assertEqual(self.count("[data-g-be], [data-g-bp]"), 0, "a milestone has one date and no done box")
        self.assertEqual(self.text("label[for=gt-bs]"), "Date (DD-MM-YYYY)")
        self.js("document.querySelector('[data-g-bcancel]').click()")
        self.until("!document.querySelector('[data-g-box]')", "cancelled")
        self.assertEqual(self.calls(), [])
        self.js("document.querySelector('[data-g-bar=GNT-010]').dispatchEvent(new MouseEvent('dblclick', {bubbles: true}))")
        self.until("document.querySelector('[data-g-bdel]')", "the delete button")
        self.assertEqual(self.text("[data-g-bdel]"), "Delete this line")
        self.js("document.querySelector('[data-g-bdel]').click()")
        self.until("document.querySelectorAll('[data-g-row]').length === 10", "the line is gone")
        self.assertEqual(self.calls(), [["delete", "GNT-010"]])

    def test_drag_a_bar_to_move_it_and_its_right_edge_to_stretch_it(self):
        self.look(1400, "light")
        self.mount(edit=True)
        ppd = self.ppd("GNT-010")
        bar = self.centre("[data-g-bar=GNT-010]")
        self.drag(bar["x"], bar["y"], ppd * 5)
        self.until("window.calls.length", "the move")
        self.assertEqual(self.calls(), [["change", "GNT-010", "dates", {"start": "2027-03-06", "end": "2027-04-14"}]], "moved 5 days: same length")
        bar = self.centre("[data-g-bar=GNT-010]")
        edge = self.val("(function(){ var r = document.querySelector('[data-g-bar=GNT-010] [data-rz]').getBoundingClientRect(); return {x: r.left + r.width / 2, y: r.top + r.height / 2}; })()")
        self.drag(edge["x"], edge["y"], ppd * 3)
        self.until("window.calls.length === 2", "the stretch")
        self.assertEqual(self.calls()[1], ["change", "GNT-010", "dates", {"start": "2027-03-06", "end": "2027-04-17"}], "only the end moved")
        # a milestone moves its one date
        ms = self.centre("[data-g-bar=GNT-007]")
        self.drag(ms["x"], ms["y"], -ppd * 4)
        self.until("window.calls.length === 3", "the milestone move")
        self.assertEqual(self.calls()[2], ["change", "GNT-007", "dates", {"start": "2026-12-14", "end": "2026-12-14"}])

    def test_a_click_without_a_drag_changes_nothing(self):
        self.look(1400, "light")
        self.mount(edit=True)
        bar = self.centre("[data-g-bar=GNT-010]")
        self.drag(bar["x"], bar["y"], 1)
        self.until("document.querySelector('[data-g-bar=GNT-010]').classList.contains('sel')", "selected")
        self.assertEqual(self.calls(), [])

    def test_dragging_a_bar_earlier_than_what_it_follows_shows_a_clash_as_it_moves(self):
        self.look(1400, "light")
        self.mount(edit=True)
        self.assertEqual(self.count("[data-g-clash]"), 1)
        ppd = self.ppd("GNT-009")
        bar = self.centre("[data-g-bar=GNT-009]")
        self.drag(bar["x"], bar["y"], -ppd * 10)
        self.until("window.calls.length", "the move")
        self.until("document.querySelectorAll('[data-g-clash]').length === 2", "the new clash is flagged")
        self.assertEqual(self.count("[data-g-clash-arrow]"), 2)

    def test_edit_sets_the_saved_plan_height_in_rows(self):
        self.look(1400, "light")
        self.mount(edit=True, defaultRows=8)
        self.assertEqual(self.val("document.querySelector('[data-g-grip]').getAttribute('aria-valuenow')"), "8")
        self.keypress("[data-g-grip]", "ArrowUp")
        self.until("window.calls.length", "the height is passed up to be saved")
        self.assertEqual(self.calls(), [["rows", 7]])
        self.assertEqual(self.val("document.querySelector('[data-g-grip]').getAttribute('aria-valuenow')"), "7")
        self.keypress("[data-g-grip]", "End")
        self.until("window.calls.length === 2", "all rows")
        self.assertEqual(self.calls()[1], ["rows", None], "every row shown is saved as no limit")
        self.keypress("[data-g-grip]", "Home")
        self.until("window.calls.length === 3", "one row")
        self.assertEqual(self.calls()[2], ["rows", 1])

    def test_a_viewer_can_change_only_their_own_height_when_a_default_is_saved(self):
        self.look(1400, "light")
        self.mount(edit=False, defaultRows=4)
        self.assertEqual(self.val("document.querySelector('[data-g-grip]').getAttribute('aria-valuenow')"), "4")
        self.keypress("[data-g-grip]", "ArrowDown")
        self.until("document.querySelector('[data-g-grip]').getAttribute('aria-valuenow') === '5'", "their own height")
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
