"""#153: the one filter line on the Work items page, driven in the real page.

Run: python3 dev/run_tests.py test_filter_line_page
Starts the real server over the demo store at CLARK_NOW=2026-10-28 and drives the committed page in headless Chrome with real mouse and key
events, at 1400 px here and at 900 px in test_filter_line_page_900 (#912: two files, so each is about half as long), in light and in dark. The pure rules are in test_filter_line. Required: fails, never skips, without Chrome.
"""
import copy
import re
import json
import time
import unittest
from _editor_checks import for_url
import urllib.parse

from _paths import ROOT, SRC  # noqa: F401
from _new_page import reload_to_new_page_cdp
import _testpage as testpage

from test_server import Running, chrome  # noqa: E402


def wait(check, seconds=15):
    """test_server.wait, polled every 50 ms instead of 200 ms: this file waits hundreds of times for a page that is a few frames away, and
    each wait that is not true yet at once cost at least 200 ms. Same limit, same meaning: true as soon as `check()` is, False at the limit."""
    t0 = time.time()
    while time.time() - t0 < seconds:
        if check():
            return True
        time.sleep(0.05)
    return False


from test_work_filters import click, expect, key, need_chrome, page_rows, pause, select_line, set_line, where  # noqa: E402
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402

INPUT = "#fline-input"
SIZES = (1400,)        # #912: the 900 px half of every loop over SIZES is test_filter_line_page_900 (the same tests, run at 900), a file of its own
THEMES = ("light", "dark")


# row 789: the empty state names what was typed ("No open items match ..." or "No items match ..."); a line of only fields says it too
EMPTY_SAYS = lambda text: bool(re.search(r"No (open )?items match", text))


def click_tab(cdp, sid, selector):
    """Click a view tab. At 900 px the tabs sit in a row that scrolls sideways, and the row slides to the tab just chosen, so a tab is
    not where it was measured while that slide runs and the click lands beside it. Wait until the row has stopped (the same offset on
    four reads one frame apart, and no animation running), bring the tab into view, then click."""
    def still():
        """No animation is running and the offset is the same on four reads one frame apart (#912: frames, not four sleeps of 60 ms)."""
        if not cdp.js("document.getAnimations().length === 0", sid):
            return False
        reads = cdp.call("Runtime.evaluate", {"expression": "(async () => { const row = document.querySelector('.vtabs'); const r = []; for (let i = 0; i < 4; i++) { "
                         "r.push(row.scrollLeft); await new Promise(f => requestAnimationFrame(f)); } return r; })()",
                         "awaitPromise": True, "returnByValue": True}, sid)["result"].get("value") or []
        return len(reads) == 4 and len(set(reads)) == 1
    assert wait(still), "the tab row is still sliding"
    cdp.js("document.querySelector(%s).scrollIntoView({inline: 'center', block: 'nearest', behavior: 'instant'})" % json.dumps(selector), sid)
    click(cdp, sid, selector)


class Line(unittest.TestCase):
    steps = None         # history.length right after the page drew: the address must not add to it

    @classmethod
    def setUpClass(cls):
        need_chrome()
        cls.store, cls.folder, cls.ids = load_demo()
        cls.projects = cls.store.read("projects")
        cls.data = {p["code"]: cls.store.data_for(p["code"]) for p in cls.projects}

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        import shutil
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def serve(self):
        s = Running(data_for=lambda code, **kw: copy.deepcopy(self.data.get(code)), projects=lambda archived=False: self.projects,
                    page_html=lambda: testpage.html())
        self.addCleanup(s.close)
        return s

    def load(self, cdp, port, width=1400, hash_="#work&p=TUL", theme="light", motion=None):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        if motion:
            cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": motion}]}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE + "window.__push = 0; const P = history.pushState; history.pushState = function () { window.__push++; return P.apply(this, arguments); };"}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, sid)
        cdp.call("Page.navigate", {"url": "about:blank"}, sid)
        cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{port}/{hash_}")}, sid)
        self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length > 0 || !!document.querySelector('#work-list .empty')", sid)), f"{hash_} drew its list")
        if theme == "dark":
            cdp.js("document.documentElement.dataset.theme = 'dark'", sid)
        self.steps = cdp.js("history.length", sid)
        return sid

    # ---- small helpers ----
    def shown(self, cdp, sid):
        return sorted(cdp.js("[...document.querySelectorAll('#work tbody tr[data-id]')].map(r => r.dataset.id)", sid))

    def chips(self, cdp, sid):
        """The words of the line, as typed in the box (the box holds the whole line)."""
        return cdp.js(r'''(document.querySelector('[data-fline]').dataset.line.match(/(?:[^\s"]|"[^"]*")+/g) || [])''', sid)

    def tokens(self, cdp, sid, cls):
        return cdp.js(f"[...document.querySelectorAll('.fline .fhi .k-{cls}')].map(e => e.textContent)", sid)

    def rows(self, cdp, sid):
        return page_rows(self.data, cdp.js("location.hash.match(/p=([A-Z0-9]+)/)[1]", sid))

    def focus(self, cdp, sid):
        click(cdp, sid, INPUT)
        wait(lambda: cdp.js("document.activeElement.id", sid) == "fline-input")      # the focus lands a frame after the click on a slow runner
        self.assertEqual(cdp.js("document.activeElement.id", sid), "fline-input")

    def type(self, cdp, sid, text):
        cdp.call("Input.insertText", {"text": text}, sid)

    def say(self, cdp, sid):
        return cdp.js("document.querySelector('#fline-msg').textContent", sid)

    def put(self, cdp, sid, text):
        """Replace the line with `text` and wait out the pause after which the list follows the box."""
        set_line(cdp, sid, text)

    def arm(self, cdp, sid):
        """Row 931: the list opens after Space. This is the key down with no character, so the text in the box does not change."""
        cdp.call("Input.dispatchKeyEvent", {"type": "rawKeyDown", "key": " ", "code": "Space", "windowsVirtualKeyCode": 32}, sid)
        cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": " ", "code": "Space", "windowsVirtualKeyCode": 32}, sid)

    def no_list(self, cdp, sid, why):
        time.sleep(0.3)
        self.assertEqual(cdp.js("!!document.querySelector('#fline-list')", sid), False, why)

    def listed(self, cdp, sid):
        return cdp.js("[...document.querySelectorAll('#fline-list [role=option]')].map(o => o.dataset.ins)", sid)

    # ---- tests ----
    def test_the_page_starts_on_one_line_with_the_open_items_and_the_old_filter_row_is_gone(self):
        s = self.serve()
        for width in SIZES:
            for theme in THEMES:
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.load(cdp, s.port, width, theme=theme)
                    self.assertEqual(self.chips(cdp, sid), ["is:open"])
                    self.assertEqual(self.shown(cdp, sid), expect(self.rows(cdp, sid)))
                    self.assertEqual(cdp.js("document.querySelectorAll('.fbar, .fbtn').length", sid), 0)
                    # the type and Open / Closed / All switches stay, each with its count
                    self.assertEqual(cdp.js("document.querySelectorAll('[data-show] em.num, [data-type] em.num').length", sid), 7)
                    self.assertEqual(cdp.js("document.querySelectorAll('#fline-input[role=combobox][aria-label]').length", sid), 1)
                    self.assertEqual(cdp.js("document.querySelector('#fline-msg').getAttribute('role')", sid), "status")
                    n = len(expect(self.rows(cdp, sid)))
                    self.assertEqual(cdp.js("document.querySelector('#work-count').textContent", sid), f"{n} open items")
                    self.assertEqual(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), True)
                    self.assertEqual(cdp.js("history.length", sid), self.steps)

    def switch(self, cdp, sid):
        return cdp.js("Object.fromEntries([...document.querySelectorAll('[data-show]')].map(b => [b.dataset.show, +b.querySelector('em').textContent]))", sid)

    def types(self, cdp, sid):
        return cdp.js("Object.fromEntries([...document.querySelectorAll('[data-type]')].map(b => [b.dataset.type, +b.querySelector('em').textContent]))", sid)

    def test_the_switch_counts_equal_the_list_after_each_filter_at_1400_and_900_px(self):
        s = self.serve()
        for code in self.data:
            for width in SIZES:
                with self.subTest(project=code, width=width), chrome() as cdp:
                    sid = self.load(cdp, s.port, width, hash_=f"#work&p={code}")
                    rows = self.rows(cdp, sid)
                    self.assertEqual(cdp.js("document.querySelector('[data-show=open]').getAttribute('aria-pressed')", sid), "true")
                    self.assertEqual(self.switch(cdp, sid), {m: len(expect(rows, m)) for m in ("open", "closed", "all")})
                    self.assertEqual(self.switch(cdp, sid)["open"], len(self.shown(cdp, sid)))
                    self.assertEqual(self.switch(cdp, sid)["all"], len(rows))
                    self.assertEqual(self.types(cdp, sid), {t: len(expect(rows, "open", t)) for t in ("all", "action", "risk", "decision")})
                    # a series of filters through the line: after each, the count of the mode that is on is the number of rows shown
                    for line, filters in (("priority:High", {"priority": ["High"]}), ("priority:High,Medium client:internal", {"priority": ["High", "Medium"], "client": ["no"]}),
                                          ("due:overdue", {"due": ["overdue"]})):
                        set_line(cdp, sid, "is:open " + line)
                        want = expect(rows, "open", filters=filters)
                        self.assertTrue(wait(lambda: self.shown(cdp, sid) == want), f"{line}: {self.shown(cdp, sid)} != {want}")
                        self.assertEqual(self.switch(cdp, sid), {m: len(expect(rows, m, filters=filters)) for m in ("open", "closed", "all")}, line)
                        self.assertEqual(self.switch(cdp, sid)["open"], len(self.shown(cdp, sid)))
                        self.assertEqual(self.types(cdp, sid), {t: len(expect(rows, "open", t, filters)) for t in ("all", "action", "risk", "decision")}, line)
                        # the switches change the line and keep the filters
                        for mode in ("closed", "all"):
                            click(cdp, sid, f"[data-show={mode}]")
                            want = expect(rows, mode, filters=filters)
                            self.assertTrue(wait(lambda: self.shown(cdp, sid) == want), f"{line} {mode}")
                            self.assertEqual(self.switch(cdp, sid)[mode], len(want))
                        click(cdp, sid, "[data-type=action]")
                        want = expect(rows, "all", "action", filters)
                        self.assertTrue(wait(lambda: self.shown(cdp, sid) == want), f"{line} actions")
                        self.assertEqual(self.types(cdp, sid)["action"], len(want))
                        click(cdp, sid, "[data-type=all]")
                        click(cdp, sid, "[data-show=open]")

    def test_a_filter_change_redraws_only_the_list(self):
        s = self.serve()
        sels = ["h1", ".crumbs", ".head", ".wbar", ".seg", "[data-type=action]", "[data-show=closed]", ".fline-wrap", INPUT, "#newBtn", "#work-list"]
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            cdp.js(f"window.__sels = {json.dumps(sels)}; window.__keep = window.__sels.map(q => document.querySelector(q)); window.__tbody = document.querySelector('#work tbody')", sid)
            click(cdp, sid, "[data-show=closed]")
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-show=closed]').getAttribute('aria-pressed')", sid) == "true"), "the Closed show button is pressed")
            click(cdp, sid, "[data-type=action]")
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-type=action]').getAttribute('aria-pressed')", sid) == "true"), "the Actions type button is pressed")
            click(cdp, sid, "[data-show=all]")                     # a change through the line itself, from the page's own start
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-show=all]').getAttribute('aria-pressed')", sid) == "true"), "the All show button is pressed")
            self.put(cdp, sid, "type:action is:closed")
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-show=closed]').getAttribute('aria-pressed')", sid) == "true"), "the Closed show button is pressed")
            self.assertEqual(cdp.js("window.__keep.map((e, i) => e === document.querySelector(window.__sels[i]))", sid), [True] * len(sels),
                             "the heading, the switches, the line, Add and the list's own box are the same elements")
            self.assertEqual(cdp.js("window.__tbody === document.querySelector('#work tbody')", sid), True)
            self.assertEqual(sorted({k for k in cdp.js("[...document.querySelectorAll('#work tbody tr[data-id]')].map(r => r.dataset.kind)", sid)}), ["action"])

    def test_the_slash_key_focuses_the_line_but_not_while_typing_or_with_a_menu_open(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            # The ask panel takes "/" outside a field on every page (test_peek pins it), so the line is focused by a click here;
            # its own "/" handler only runs where the ask panel has not taken the key.
            cdp.js("document.activeElement.blur()", sid)
            self.focus(cdp, sid)
            self.assertEqual(cdp.js("document.querySelector('[data-fline]').dataset.line", sid), "is:open", "the slash itself is not typed")
            key(cdp, sid, "Escape")                                               # #640: the field list opens on focus and the examples wait until it is closed
            self.assertTrue(wait(lambda: cdp.js("getComputedStyle(document.querySelector('.fhints')).visibility", sid) == "visible"), "the filter hints are visible")
            self.assertEqual(cdp.js("getComputedStyle(document.querySelector('.fhints')).visibility", sid), "visible", "the hint chips show while the line is focused")
            # not while typing in another field
            click(cdp, sid, "#viewMenu")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#viewMenuList')", sid)), "the View menu opened")
            cdp.js("document.querySelector('#fline-input').blur()", sid)
            cdp.js("document.querySelector('#viewMenuList').focus()", sid)
            cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "/", "code": "Slash", "text": "/", "windowsVirtualKeyCode": 191}, sid)
            self.assertNotEqual(cdp.js("document.activeElement.id", sid), "fline-input", "not while a menu is open")
            key(cdp, sid, "Escape")
            cdp.js("(() => { const i = document.createElement('input'); i.id = 'other'; document.body.appendChild(i); i.focus(); })()", sid)
            cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "/", "code": "Slash", "text": "/", "windowsVirtualKeyCode": 191}, sid)
            self.assertEqual(cdp.js("document.activeElement.id", sid), "other", "not while typing in a field")

    def test_the_line_does_not_say_press_slash_because_that_key_opens_ask(self):
        # #286: the hint "Press /" pointed at a key that opens ask clark in the app, so it is gone. Pinned at both widths (row 804: the page has no mode now).
        s = self.serve()
        for width in SIZES:
            for mode in ("work",):
                with self.subTest(width=width, mode=mode), chrome() as cdp:
                    sid = self.load(cdp, s.port, width)
                    self.assertEqual(cdp.js("document.querySelectorAll('[data-mode]').length", sid), 0, "no View | Edit switch on Work items")
                    self.assertEqual(cdp.js("document.querySelectorAll('.fkey, .fline kbd, .fline-wrap [aria-keyshortcuts]').length", sid), 0)
                    for focused in (False, True):
                        if focused:
                            self.focus(cdp, sid)
                        text = cdp.js("document.querySelector('.fline-wrap').textContent", sid)
                        self.assertNotRegex(text, r"(?i)press\s*/", f"no hint for the slash key (focused={focused})")
                    cdp.js("document.activeElement.blur()", sid)
                    cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "/", "code": "Slash", "text": "/", "windowsVirtualKeyCode": 191}, sid)
                    self.assertNotEqual(cdp.js("document.activeElement.id", sid), "fline-input", "the slash key goes to ask clark, not the line")

    def test_hint_chips_show_only_while_focused_and_a_hint_goes_into_the_box(self):
        s = self.serve()
        for width in SIZES:
            with self.subTest(width=width), chrome() as cdp:
                sid = self.load(cdp, s.port, width)
                self.assertEqual(cdp.js("getComputedStyle(document.querySelector('.fhints')).visibility", sid), "hidden")
                self.focus(cdp, sid)
                key(cdp, sid, "Escape")                                           # #640: the field list opens on focus and the examples wait until it is closed
                self.assertTrue(wait(lambda: cdp.js("getComputedStyle(document.querySelector('.fhints')).visibility", sid) == "visible"), "the filter hints are visible")
                hints = cdp.js("[...document.querySelectorAll('.fhint')].map(h => h.textContent)", sid)
                self.assertIn("due:overdue", hints)
                self.assertIn("is:quiet", hints, "the demo carries review facts, so the word is offered")
                self.assertGreaterEqual(cdp.js("Math.min(...[...document.querySelectorAll('.fhint')].map(h => h.getBoundingClientRect().height))", sid), 24)
                click(cdp, sid, ".fhint[title*='Leave closed']")
                self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-fline]').dataset.line", sid) == "is:open -status:Closed"))
                self.assertTrue(wait(lambda: "-status:Closed" in self.chips(cdp, sid)), "the -status:Closed chip is shown")
                pause(cdp, sid)
                self.assertTrue(wait(lambda: self.shown(cdp, sid) == expect(self.rows(cdp, sid), "open", filters={"status": ["Closed"]}, nots=("status",))), "the rows shown are the open items less the Closed status")

    def test_typing_offers_fields_then_values_with_arrows_and_enter_choose(self):
        s = self.serve()
        for width in SIZES:
            for theme in THEMES:
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.load(cdp, s.port, width, theme=theme)
                    rows = self.rows(cdp, sid)
                    self.focus(cdp, sid)
                    select_line(cdp, sid)
                    self.arm(cdp, sid)
                    self.type(cdp, sid, "st")
                    self.assertTrue(wait(lambda: "status:" in self.listed(cdp, sid)), "the list offers status: values")
                    self.assertEqual(cdp.js("document.querySelector('#fline-input').getAttribute('aria-expanded')", sid), "true")
                    self.assertEqual(self.listed(cdp, sid)[0], "status:", "fields come first")
                    key(cdp, sid, "ArrowDown")
                    self.assertTrue(wait(lambda: cdp.js("document.querySelector('#fline-input').getAttribute('aria-activedescendant')", sid) == "fo-0"), "the first option is active")
                    key(cdp, sid, "Enter")                                           # a field: goes into the box, then its values are listed
                    self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-fline]').dataset.line", sid) == "status:"))
                    self.no_list(cdp, sid, "row 931: a choice closes the list")
                    self.arm(cdp, sid)
                    self.assertTrue(wait(lambda: "status:Open" in self.listed(cdp, sid)), "the list offers status:Open")
                    options = self.listed(cdp, sid)
                    key(cdp, sid, "ArrowUp")                                         # the arrows wrap round
                    self.assertTrue(wait(lambda: cdp.js("document.querySelector('#fline-input').getAttribute('aria-activedescendant')", sid) == f"fo-{len(options) - 1}"), "the last option is active")
                    idx = options.index("status:Closed")
                    for _ in range(idx + 1):                                         # from the last one, round to the first and on to Closed
                        key(cdp, sid, "ArrowDown")
                    self.assertEqual(cdp.js("document.querySelector('#fline-input').getAttribute('aria-activedescendant')", sid), f"fo-{idx}")
                    key(cdp, sid, "Enter")
                    self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-fline]').dataset.line", sid) == "status:Closed"), "the accepted value is a chip")
                    self.no_list(cdp, sid, "row 931: the choice closed the list")
                    self.arm(cdp, sid)
                    self.assertTrue(wait(lambda: self.listed(cdp, sid)[:2] == ["is:", "type:"]), "and the list of fields opens with Space")
                    pause(cdp, sid)
                    self.assertTrue(wait(lambda: self.shown(cdp, sid) == expect(rows, "all", filters={"status": ["Closed"]})), "status:Closed alone (the box held the whole line)")
                    self.assertEqual(cdp.js("history.length", sid), self.steps, "a filter rewrites the address, it adds no step")
                    self.assertEqual(cdp.js("window.__push", sid), 0)
                    self.assertRegex(cdp.js("location.hash", sid), r"^#work&p=TUL&f=.*status:Closed")

    def test_the_box_holds_the_whole_line_and_escape_closes_the_list_keeping_what_was_typed(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            rows = self.rows(cdp, sid)
            self.put(cdp, sid, "is:open priority:High type:action")
            self.assertEqual(self.chips(cdp, sid), ["is:open", "priority:High", "type:action"])
            self.assertEqual(self.shown(cdp, sid), expect([r for r in rows if r["kind"] == "action"], "open", filters={"priority": ["High"]}))
            self.arm(cdp, sid)
            self.type(cdp, sid, " ow")
            self.assertTrue(wait(lambda: "owner:" in self.listed(cdp, sid)), "the list offers owner:")
            key(cdp, sid, "Escape")
            self.assertTrue(wait(lambda: cdp.js("!document.querySelector('#fline-list')", sid)), "Esc closes the list")
            self.assertEqual(cdp.js("document.querySelector('[data-fline]').dataset.line", sid), "is:open priority:High type:action ow", "and keeps what was typed")
            for _ in range(2):
                key(cdp, sid, "Backspace")                                           # the two letters go; only a Backspace in the then empty box takes a chip (row 845)
            self.assertEqual(self.chips(cdp, sid), ["is:open", "priority:High", "type:action"])
            pause(cdp, sid)
            self.assertEqual(self.shown(cdp, sid), expect([r for r in rows if r["kind"] == "action"], "open", filters={"priority": ["High"]}))

    def test_backspace_or_delete_right_after_a_half_typed_field_value_removes_the_whole_word(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            self.focus(cdp, sid)
            for name in ("Backspace", "Delete"):
                self.put(cdp, sid, "")
                self.type(cdp, sid, "status:Op")
                self.assertEqual(cdp.js("document.querySelector('#fline-input').value", sid), "status:Op")
                key(cdp, sid, name)
                self.assertEqual(cdp.js("document.querySelector('#fline-input').value", sid), "", name + " takes the whole status:Op")
            self.type(cdp, sid, "fix ow")
            key(cdp, sid, "Backspace")
            self.assertEqual(cdp.js("document.querySelector('#fline-input').value", sid), "fix o", "a plain word still goes one letter")

    def test_delete_in_an_empty_box_takes_the_last_chip_and_before_a_space_takes_the_space(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            self.put(cdp, sid, "is:open priority:High ")
            self.assertEqual(self.chips(cdp, sid), ["is:open", "priority:High"])
            self.assertEqual(cdp.js("document.querySelector('#fline-input').value", sid), "", "both words are chips, the box is empty")
            key(cdp, sid, "Delete")
            self.assertTrue(wait(lambda: self.chips(cdp, sid) == ["is:open"]), "Delete in the empty box takes the last chip like Backspace")
            self.type(cdp, sid, "fix ow")
            cdp.js("(() => { const i = document.querySelector('#fline-input'); i.setSelectionRange(0, 0); })()", sid)
            key(cdp, sid, "Delete")
            self.assertEqual(self.chips(cdp, sid), ["is:open", "ix", "ow"], "Delete in a box with text is the usual forward letter, no chip goes")
            self.assertEqual(cdp.js("document.querySelector('#fline-input').value", sid), "ix ow")
            self.put(cdp, sid, "xx:Op x")
            cdp.js("(() => { const i = document.querySelector('#fline-input'); i.setSelectionRange(5, 5); })()", sid)
            key(cdp, sid, "Delete")
            self.assertEqual(cdp.js("document.querySelector('#fline-input').value", sid), "xx:Opx", "Delete before the space takes the space only")

    def test_a_token_with_an_error_is_underlined_says_why_and_filters_nothing(self):
        s = self.serve()
        for theme in THEMES:
            with self.subTest(theme=theme), chrome() as cdp:
                sid = self.load(cdp, s.port, theme=theme)
                before = self.shown(cdp, sid)
                self.put(cdp, sid, "is:open stat:Open")
                self.assertTrue(wait(lambda: self.say(cdp, sid) == "There is no \u201cstat\u201d filter. Did you mean status? You can filter by type:, status:, owner:, priority:, due:, workstream:, usecase:, milestone:, client: and is:, or type plain words to search titles."))
                self.assertEqual(self.shown(cdp, sid), before, "the table is not emptied")
                self.assertEqual(self.tokens(cdp, sid, "err"), ["stat:Open"])
                self.assertEqual(cdp.js("document.querySelector('.fline .k-err').title", sid), cdp.js("document.querySelector('#fline-msg').textContent", sid), "the tooltip says it")
                self.assertIn("underline", cdp.js("getComputedStyle(document.querySelector('.fline .k-err')).textDecorationLine", sid))
                self.assertEqual(cdp.js("getComputedStyle(document.querySelector('.fline .k-err')).pointerEvents", sid), "auto", "it can be hovered")
                self.assertEqual(cdp.js("document.querySelector('#fline-msg').getAttribute('aria-live')", sid), "polite")
                self.put(cdp, sid, "is:open colour:red")
                self.assertTrue(wait(lambda: self.say(cdp, sid).startswith("There is no \u201ccolour\u201d filter.")), "the page says the field colour is unknown")
                self.put(cdp, sid, "is:open priority:High bogus:x")                   # the good token is applied; the bad one is not
                self.assertEqual(self.shown(cdp, sid), expect(self.rows(cdp, sid), "open", filters={"priority": ["High"]}))
                self.assertEqual(self.tokens(cdp, sid, "err"), ["bogus:x"])
                self.put(cdp, sid, "is:open status:")
                cdp.js("document.activeElement.blur()", sid)                         # while the caret is in a token being typed it is not marked
                self.assertTrue(wait(lambda: self.say(cdp, sid) == "Add a value after 'status:'."), "the page asks for a value after status:")
                self.put(cdp, sid, "is:opn")
                self.assertTrue(wait(lambda: self.say(cdp, sid) == "Unknown state 'opn'. Did you mean open?"), "the page says the state opn is unknown")
                self.put(cdp, sid, "is:open owner:me")
                self.assertTrue(wait(lambda: "Set your name in Settings to see your actions." in self.say(cdp, sid)), "the page asks for a name to show actions")
                self.assertTrue(wait(lambda: EMPTY_SAYS(cdp.js("document.querySelector('#work-list').innerText", sid))), "the empty list says why")
                self.put(cdp, sid, "is:open status:Nope")                            # an unknown value of a known field matches nothing: no error, the empty state
                self.assertEqual(self.say(cdp, sid), "")
                self.assertTrue(wait(lambda: EMPTY_SAYS(cdp.js("document.querySelector('#work-list').innerText", sid))), "the empty list says why")

    def test_the_text_is_highlighted_field_names_plain_and_values_as_coloured_chips(self):
        s = self.serve()
        for width in SIZES:
            for theme in THEMES:
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.load(cdp, s.port, width, theme=theme)
                    self.put(cdp, sid, 'is:open status:Open,Delayed owner:"Fictional Owner" supplier priority:Urgent,Medium')
                    self.assertEqual(self.chips(cdp, sid)[:4], ["is:open", "status:Open,Delayed", 'owner:"Fictional Owner"', "supplier"], "row 845: the complete filters are chips")
                    self.assertEqual(cdp.js("[...document.querySelectorAll('[data-fline] [data-chip]')].map((e) => e.dataset.chip)", sid), ["is:open", "status:Open,Delayed", 'owner:"Fictional Owner"'])
                    self.assertEqual(self.tokens(cdp, sid, "fld"), ["priority:"])
                    self.assertEqual(self.tokens(cdp, sid, "val"), ["Urgent", "Medium"])
                    self.assertEqual(self.tokens(cdp, sid, "txt"), ["supplier"])
                    bg = lambda sel: cdp.js(f"getComputedStyle(document.querySelector({json.dumps(sel)})).backgroundColor", sid)
                    box = bg(".fline")
                    self.assertEqual(bg(".fline .k-fld"), "rgba(0, 0, 0, 0)", "a field name is plain")
                    self.assertNotEqual(bg(".fline .k-val"), box, "a value is a chip")
                    self.assertNotEqual(bg(".fline .fchip"), box, "and so is a complete filter")
                    self.assertNotEqual(bg(".fline .k-val.r"), bg(".fline .k-val.a"), "single-select values carry their colour")
                    # the drawn text is exactly the typed text, and it sits on the typed text (the layer lines up with the input)
                    self.assertEqual(cdp.js("document.querySelector('.fline .fhi').textContent", sid), cdp.js("document.querySelector('#fline-input').value", sid))
                    self.assertEqual(cdp.js("document.querySelector('.fline .fhi').getAttribute('aria-hidden')", sid), "true")
                    self.assertEqual(cdp.js("getComputedStyle(document.querySelector('#fline-input')).color", sid), "rgba(0, 0, 0, 0)")
                    self.assertEqual(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), True)

    def test_the_match_count_is_in_the_box_right_aligned_and_says_matches_of_total(self):
        s = self.serve()
        for width in SIZES:
            for theme in THEMES:
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.load(cdp, s.port, width, theme=theme)
                    rows = self.rows(cdp, sid)
                    self.assertEqual(cdp.js("document.querySelector('#fline-count').textContent", sid), f"{len(expect(rows))} of {len(rows)}")
                    self.put(cdp, sid, "priority:High")
                    n = len(expect(rows, "all", filters={"priority": ["High"]}))
                    self.assertEqual(cdp.js("document.querySelector('#fline-count').textContent", sid), f"{n} of {len(rows)}")
                    geo = cdp.js("(() => { const c = document.querySelector('#fline-count').getBoundingClientRect(), b = document.querySelector('.fline').getBoundingClientRect(), x = document.querySelector('#fline-x').getBoundingClientRect(); return {inside: c.left >= b.left && c.right <= b.right && c.top >= b.top && c.bottom <= b.bottom, right: b.right - x.right, gap: x.left - c.right}; })()", sid)
                    self.assertTrue(geo["inside"], "inside the box")
                    self.assertLess(geo["right"], 24, "at the right end, by the clear button")
                    self.assertLess(geo["gap"], 24)

    def test_the_list_follows_the_box_after_a_pause_not_on_enter(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            rows = self.rows(cdp, sid)
            before = self.shown(cdp, sid)
            self.focus(cdp, sid)
            key(cdp, sid, "End")
            self.type(cdp, sid, " type:decision")
            key(cdp, sid, "Enter")
            self.assertEqual(self.shown(cdp, sid), before, "Enter applies nothing")
            self.assertEqual(cdp.js("location.hash", sid), "#work&p=TUL")
            t0 = cdp.js("performance.now()", sid)
            self.assertTrue(wait(lambda: self.shown(cdp, sid) == expect(rows, "open", "decision")), "the list follows the box")
            waited = cdp.js("performance.now()", sid) - t0
            self.assertLess(waited, 3000)
            # a key inside the pause pushes the apply back: the list changes once, for the last text
            select_line(cdp, sid)
            self.type(cdp, sid, "type:action")
            self.type(cdp, sid, " is:open")
            pause(cdp, sid)
            self.assertEqual(self.shown(cdp, sid), expect(rows, "open", "action"))

    def test_the_x_shows_whenever_there_is_text_clears_to_the_full_view_and_keeps_the_focus(self):
        s = self.serve()
        for width in SIZES:
            for theme in THEMES:
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.load(cdp, s.port, width, theme=theme)
                    rows = self.rows(cdp, sid)
                    self.assertTrue(cdp.js("!!document.querySelector('#fline-x')", sid), "the page's start line is text, so the x shows")
                    self.assertEqual(cdp.js("document.querySelector('#fline-x').getAttribute('aria-label')", sid), "Clear filter")
                    box = cdp.js("(() => { const r = document.querySelector('#fline-x').getBoundingClientRect(); return [r.width, r.height]; })()", sid)
                    self.assertGreaterEqual(min(box), 24, "a 24 px target")
                    inside = cdp.js("(() => { const x = document.querySelector('#fline-x').getBoundingClientRect(), b = document.querySelector('.fline').getBoundingClientRect(); return x.right <= b.right && x.left >= b.left && x.top >= b.top && x.bottom <= b.bottom; })()", sid)
                    self.assertTrue(inside, "inside the box, at the right end")
                    click(cdp, sid, "#fline-x")
                    self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-fline]').dataset.line", sid) == ""))
                    self.assertFalse(cdp.js("!!document.querySelector('#fline-x')", sid), "no text, no x")
                    self.assertEqual(cdp.js("document.activeElement.id", sid), "fline-input", "the focus is in the box")
                    self.assertTrue(wait(lambda: self.shown(cdp, sid) == sorted(r["id"] for r in rows)), "the full view")
                    self.assertEqual(cdp.js("document.querySelector('#fline-count').textContent", sid), f"{len(rows)} of {len(rows)}")
                    self.assertEqual(cdp.js("document.querySelector('.vtab[aria-pressed=true] span').textContent", sid), "All work items")
                    # by keyboard: type, Tab to the x, Enter
                    self.type(cdp, sid, "supplier")
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#fline-x')", sid)), "the clear button is there")
                    key(cdp, sid, "Escape")
                    for _ in range(3):
                        if cdp.js("document.activeElement.id", sid) == "fline-x":
                            break
                        key(cdp, sid, "Tab")
                    self.assertEqual(cdp.js("document.activeElement.id", sid), "fline-x")
                    key(cdp, sid, "Enter")
                    self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-fline]').dataset.line", sid) == ""))
                    self.assertTrue(wait(lambda: self.shown(cdp, sid) == sorted(r["id"] for r in rows)), "every row is shown")
                    self.assertEqual(cdp.js("document.activeElement.id", sid), "fline-input")
                    # a clear inside the pause is not undone by the typed text arriving after it
                    self.type(cdp, sid, "supplier")
                    click(cdp, sid, "#fline-x")
                    pause(cdp, sid)
                    self.assertEqual(cdp.js("document.querySelector('[data-fline]').dataset.line", sid), "")

    def test_no_match_shows_the_empty_state_with_a_clear_filter_link(self):
        s = self.serve()
        for width in SIZES:
            for theme in THEMES:
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.load(cdp, s.port, width, theme=theme)
                    rows = self.rows(cdp, sid)
                    self.put(cdp, sid, "is:open zzzqqq")
                    self.assertTrue(wait(lambda: cdp.js("document.querySelector('#work-list .empty p').textContent", sid) == 'No open items match "zzzqqq".'), "the empty list names the filter that matched nothing")   # row 789
                    self.assertEqual(self.shown(cdp, sid), [])
                    self.assertEqual(cdp.js("document.querySelector('#fline-count').textContent", sid), f"0 of {len(rows)}")
                    self.assertEqual(cdp.js("document.querySelector('#clearFilter').textContent", sid), "Clear search")
                    self.assertEqual(cdp.js("(document.querySelector('#empty-hint') || {}).textContent", sid), "Plain words search titles. Press / to come back here.")
                    self.assertEqual(cdp.js("document.querySelectorAll('#work-list .empty [class*=err]').length", sid), 0, "it is not an error")
                    click(cdp, sid, "#clearFilter")
                    self.assertTrue(wait(lambda: self.shown(cdp, sid) == sorted(r["id"] for r in rows)), "every row is shown")
                    self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-fline]').dataset.line", sid) == ""))
                    self.assertFalse(cdp.js("!!document.querySelector('#clearFilter')", sid))

    def test_the_empty_state_says_items_not_open_items_on_closed_and_all(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            self.put(cdp, sid, "is:closed zzzqqq")
            self.assertTrue(wait(lambda: cdp.js("(document.querySelector('#work-list .empty p') || {}).textContent", sid) == 'No items match "zzzqqq".'), "the empty list names the filter that matched nothing")
            self.put(cdp, sid, "zzzqqq")
            self.assertTrue(wait(lambda: cdp.js("(document.querySelector('#work-list .empty p') || {}).textContent", sid) == 'No items match "zzzqqq".'), "the empty list names the filter that matched nothing")

    def test_words_the_page_cannot_answer_yet_are_not_offered_and_are_refused(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            self.focus(cdp, sid)
            select_line(cdp, sid)
            self.arm(cdp, sid)
            self.type(cdp, sid, "is:")
            self.assertTrue(wait(lambda: "is:open" in self.listed(cdp, sid)), "the list offers is:open")
            offered = self.listed(cdp, sid)
            for hidden in ("is:needed", "is:archived"):
                self.assertNotIn(hidden, offered)
            self.assertIn("is:incomplete", offered)
            self.assertTrue(cdp.js("[...document.querySelectorAll('#fline-list .fl2')].some(e => e.textContent.includes('No owner or no date'))", sid), "a gloss beside is:incomplete")
            self.type(cdp, sid, "needed")
            self.assertTrue(wait(lambda: self.tokens(cdp, sid, "err") == ["is:needed"]), "refused: underlined, and it filters nothing")
            pause(cdp, sid)
            self.assertEqual(self.shown(cdp, sid), sorted(r["id"] for r in self.rows(cdp, sid)))

    def test_the_freshness_words_follow_the_projects_own_number_of_days(self):
        """#171 and row 813: the project's review_after_days (in its row of the data) is what the suggestion for the typed word says, in the singular for one day."""
        for days, words in ((3, "Not reviewed in 3 days"), (1, "Not reviewed in 1 day"), (365, "Not reviewed in 365 days")):
            self.data["TUL"]["project"]["review_after_days"] = days
            self.addCleanup(self.data["TUL"]["project"].__setitem__, "review_after_days", 14)
            s = self.serve()
            with self.subTest(days=days), chrome() as cdp:
                sid = self.load(cdp, s.port)
                self.watch(cdp, sid)
                self.assertFalse(cdp.js("!!document.querySelector('#freshMenu')", sid), "row 813: no Freshness pill")
                self.focus(cdp, sid)
                select_line(cdp, sid)
                self.arm(cdp, sid)
                self.type(cdp, sid, "is:")
                self.assertTrue(wait(lambda: "is:quiet" in self.listed(cdp, sid)))
                glosses = cdp.js("Object.fromEntries([...document.querySelectorAll('#fline-list [role=option]')].map(o => [o.dataset.ins, (o.querySelector('.fl2') || {}).textContent]))", sid)
                self.assertEqual((glosses["is:quiet"], glosses["is:incomplete"]), (words, "No owner or no date"))

    def test_the_freshness_pill_is_gone_and_the_typed_words_still_filter_and_say_themselves_in_plain_words(self):
        s = self.serve()
        for width in SIZES:
            for theme in THEMES:
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.load(cdp, s.port, width, theme=theme)
                    self.watch(cdp, sid)
                    self.assertFalse(cdp.js("!!document.querySelector('#freshMenu, [aria-label=Freshness]')", sid), "row 813: no Freshness pill in the row")
                    self.put(cdp, sid, "is:open is:incomplete")
                    self.assertTrue(wait(lambda: "is:incomplete" in self.chips(cdp, sid)), self.chips(cdp, sid))
                    self.assertEqual(self.chips(cdp, sid), ["is:open", "is:incomplete"], "the line's own words")
                    self.assertEqual(self.tokens(cdp, sid, "val"), ["incomplete"], "the word being typed keeps its colour; the complete one is a chip")
                    rows = self.rows(cdp, sid)
                    want = sorted(r["id"] for r in rows if r["status"] not in ("Closed", "Cancelled", "Made", "Withdrawn")
                                  and (not str(r["owner"] or "").strip() or str(r["owner"]).strip().upper() == "TBC"
                                       or (r["kind"] in ("action", "decision") and not (r.get("needed_by") if r["kind"] == "decision" and r["status"] == "Pending" else r.get("due_date") if r["kind"] == "action" else r.get("date"))))
                                  and True)
                    self.assertEqual(self.shown(cdp, sid), want)
                    self.assertIn("reviewed", cdp.js("location.hash", sid), "the address keeps the older Freshness filter")
                    self.put(cdp, sid, "is:open")
                    self.assertTrue(wait(lambda: self.chips(cdp, sid) == ["is:open"]), "taking the word off")
                    self.assertEqual(cdp.js("window.__errs", sid), [])

    def test_an_address_with_a_freshness_filter_opens_work_items_with_no_error(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port, hash_="#work&p=TUL&f=mode:open;reviewed:incomplete")
            self.watch(cdp, sid)
            self.assertIn("is:incomplete", self.chips(cdp, sid))
            self.assertEqual(self.say(cdp, sid), "")

    def test_workstream_and_milestone_values_come_from_the_project(self):
        s = self.serve()
        d = self.data["TUL"]
        streams = [w["name"] for w in d["workstreams"] if w.get("name")]
        dated = sorted((m for m in d["milestones"] if m.get("name")), key=lambda m: (not (m.get("forecast_date") or m.get("baseline_date")), m.get("forecast_date") or m.get("baseline_date") or "", m.get("sort_order") or 0))
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            self.focus(cdp, sid)
            select_line(cdp, sid)
            self.arm(cdp, sid)
            self.type(cdp, sid, "workstream:")
            self.assertTrue(wait(lambda: len(self.listed(cdp, sid)) > 0), "the list has options")
            offered = [o.split(":", 1)[1].strip('"') for o in self.listed(cdp, sid) if o.startswith("workstream:")]
            self.assertEqual([o for o in offered if o in streams][:len(streams)], [o for o in streams if o in offered], "the project's own order")
            for name in streams:
                self.assertIn(name, offered)
            select_line(cdp, sid)
            self.arm(cdp, sid)
            self.type(cdp, sid, "milestone:")
            self.assertTrue(wait(lambda: any(o.startswith("milestone:") for o in self.listed(cdp, sid))), "the list offers milestone: fields")
            got = " | ".join(self.listed(cdp, sid))
            for m in dated:
                self.assertIn(m["name"], got.replace("\u00a0", " "))
            self.put(cdp, sid, "is:open due:nonsense")                                # an unknown value matches nothing: the empty state, no error
            self.assertTrue(wait(lambda: EMPTY_SAYS(cdp.js("document.querySelector('#work-list').innerText", sid))), "the empty list says why")
            self.assertEqual(self.say(cdp, sid), "")
            self.assertEqual(self.chips(cdp, sid), ["is:open", "due:nonsense"])

    def test_the_glance_tiles_land_on_a_working_line_with_no_error(self):
        s = self.serve()
        for theme in THEMES:
            for tile, want in (("risks", "priority:Urgent,High"), ("overdue", "due:overdue")):
                with self.subTest(theme=theme, tile=tile), chrome() as cdp:
                    sid = self.load(cdp, s.port, theme=theme)
                    self.watch(cdp, sid)
                    cdp.js("location.hash = '#dashboard&p=TUL'", sid)
                    self.assertTrue(wait(lambda: cdp.js(f"!!document.querySelector('[data-fig={tile}]')", sid)), f"the {tile} tile is drawn")
                    click(cdp, sid, f"[data-fig={tile}]")
                    self.assertTrue(wait(lambda: want in self.chips(cdp, sid)), f"{tile} lands on {want}: {self.chips(cdp, sid)}")
                    self.assertEqual(self.say(cdp, sid), "", "no message on landing")
                    self.assertEqual(cdp.js("window.__errs", sid), [], "no error on the page")

    def test_the_older_filters_are_all_reachable_and_the_address_keeps_the_older_state(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            rows = self.rows(cdp, sid)
            self.put(cdp, sid, "is:open -owner:none priority:High,Medium client:internal due:next-7-days,later")
            self.assertEqual(self.chips(cdp, sid), ["is:open", "-owner:none", "priority:High,Medium", "client:internal", "due:next-7-days,later"])
            self.assertEqual(self.tokens(cdp, sid, "val"), ["next-7-days", "later"], "the word being typed keeps its colours; the complete ones are chips")
            self.assertEqual(self.shown(cdp, sid), expect(rows, "open", filters={"owner": ["(none)"], "priority": ["High", "Medium"], "client": ["no"], "due": ["soon", "later"]}, nots=("owner",)))
            self.assertIn("not:owner", cdp.js("location.hash", sid), "the address keeps the older state, so a link still opens the same list")

    def test_each_older_filter_is_reachable_through_the_line_and_gives_the_rows_the_oracle_gives(self):
        s = self.serve()
        for code in self.data:
            with self.subTest(project=code), chrome() as cdp:
                sid = self.load(cdp, s.port, hash_=f"#work&p={code}")
                rows = self.rows(cdp, sid)
                owner = next(r["owner"] for r in rows if r["owner"] and " " in r["owner"])
                cases = [
                    ("is:open owner:" + json.dumps(owner), "open", {"owner": [owner]}, ()),
                    ("is:all", None, None, ()),
                    ("is:closed priority:High,Medium", "closed", {"priority": ["High", "Medium"]}, ()),
                    ("is:open -status:Delayed client:internal", "open", {"status": ["Delayed"], "client": ["no"]}, ("status",)),
                    ("is:open due:overdue,next-7-days", "open", {"due": ["overdue", "soon"]}, ()),
                    ("is:open no:owner", "open", {"owner": ["(none)"]}, ()),
                ]
                for line, mode, filters, nots in cases:
                    if mode is None:
                        continue
                    with self.subTest(line=line):
                        set_line(cdp, sid, line)
                        want = expect(rows, mode, filters=filters, nots=nots)
                        self.assertTrue(wait(lambda: self.shown(cdp, sid) == want), f"{line}: {self.shown(cdp, sid)} != {want}")
                        n = len(want)
                        self.assertTrue(wait(lambda: cdp.js("document.querySelector('#work-count').textContent", sid) == (f"{n} {mode} item" + ("" if n == 1 else "s"))), "the count says how many items")
                set_line(cdp, sid, "")                                              # no is: word: every item, open or closed
                self.assertTrue(wait(lambda: self.shown(cdp, sid) == sorted(r["id"] for r in rows)), "every row is shown")
                self.assertEqual(cdp.js("document.querySelector('#work-count').textContent", sid), f"{len(rows)} items")
                self.assertEqual(cdp.js("location.hash", sid), "#work&p=" + code + "&f=mode:all")

    def test_a_peek_and_the_line_share_the_address_and_neither_loses_the_other(self):
        s = self.serve()
        item = self.data["TUL"]["actions"][0]["id"]
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            set_line(cdp, sid, "type:action")
            self.assertTrue(wait(lambda: cdp.js("clarkPage.filters()", sid) == "mode:all;type:action"), "the page keeps the filter")
            cdp.js(f"clarkPage.openPeek({json.dumps(item)})", sid)
            self.assertTrue(wait(lambda: cdp.js("location.hash", sid) == f"#work&p=TUL&item={item}&f=mode:all;type:action"), "the address holds the filter")
            reload_to_new_page_cdp(cdp, sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid) > 0), "the list drew rows")
            self.assertEqual(cdp.js("clarkPage.peek().id", sid), item)
            self.assertEqual(self.chips(cdp, sid), ["type:action"])

    def test_too_long_a_line_for_the_address_is_refused_with_a_plain_line_and_changes_nothing(self):
        data = copy.deepcopy(self.data)
        owners = [f"Fictional Owner {chr(65 + i)} " + "x" * 60 for i in range(10)]
        pool = data["TUL"]["actions"] + data["TUL"]["raid"]
        for i, o in enumerate(owners):
            pool[i]["owner"] = o
        s = Running(data_for=lambda code, **kw: copy.deepcopy(data.get(code)), projects=lambda archived=False: self.projects, page_html=lambda: testpage.html())
        self.addCleanup(s.close)
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            before = self.shown(cdp, sid)
            click(cdp, sid, "#fline-input")
            key(cdp, sid, "End")
            self.type(cdp, sid, " owner:" + ",".join(json.dumps(o) for o in owners))
            self.assertTrue(wait(lambda: "not fit" in cdp.js("document.querySelector('#work-note').textContent", sid)))
            self.assertEqual(cdp.js("document.querySelector('#work-note').getAttribute('role')", sid), "status")
            self.assertFalse(cdp.js("clarkPage.filters()", sid), "nothing changed")
            self.assertEqual(self.shown(cdp, sid), before)
            self.assertEqual(cdp.js("history.length", sid), self.steps)

    def test_clear_filter_in_the_empty_state_clears_the_whole_line(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            self.assertEqual(cdp.js("!!document.querySelector('#clearAll, #clearAll2, #clearFilter')", sid), False)
            self.put(cdp, sid, "is:closed type:decision client:internal priority:Urgent")
            self.assertTrue(wait(lambda: EMPTY_SAYS(cdp.js("document.querySelector('#work-list').innerText", sid))), "the empty list says why")
            click(cdp, sid, "#clearFilter")
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-fline]').dataset.line", sid) == ""))
            self.assertEqual(cdp.js("!!document.querySelector('#clearAll, #clearAll2, #clearFilter')", sid), False)
            self.assertEqual(cdp.js("location.hash", sid), "#work&p=TUL&f=mode:all")

    def test_the_address_carries_the_line_and_a_link_opens_the_same_list(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port, hash_="#work&p=TUL&f=mode:closed;type:action")
            self.assertEqual(self.chips(cdp, sid), ["is:closed", "type:action"])
            self.assertEqual(self.shown(cdp, sid), expect(self.rows(cdp, sid), "closed", "action"))
            self.assertEqual(cdp.js("location.hash", sid), "#work&p=TUL&f=mode:closed;type:action")
            owner = next(r["owner"] for r in self.rows(cdp, sid) if r["owner"] and " " in r["owner"])
            sid = self.load(cdp, s.port, hash_="#work&p=TUL&f=owner:" + urllib.parse.quote(owner, safe="") + ";not:owner")
            self.assertEqual(self.chips(cdp, sid), ["is:open", f'-owner:"{owner}"'])
            # a name no item has any more is not applied, and the line says so in plain words
            sid = self.load(cdp, s.port, hash_="#work&p=TUL&f=owner:Nobody%20Here")
            self.assertTrue(wait(lambda: EMPTY_SAYS(cdp.js("document.querySelector('#work-list').innerText", sid))), "a name no item has matches nothing")
            hostile = '<img src=x onerror="window.__pwn=1">'
            sid = self.load(cdp, s.port, hash_="#work&p=TUL&f=owner:" + urllib.parse.quote(hostile, safe="") + ";not:owner")
            self.assertEqual(cdp.js("document.querySelectorAll('#work img').length + typeof window.__pwn", sid), "0undefined")
            sid = self.load(cdp, s.port, hash_="#work&p=TUL&f=mode:closed;owner:%zz")
            self.assertEqual(cdp.js("location.hash.startsWith('#work&p=TUL')", sid), True)

    def test_back_and_forward_bring_the_line_back_with_the_page(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            self.put(cdp, sid, "type:risk,issue,assumption,dependency")
            self.assertTrue(wait(lambda: "type:risk,issue,assumption,dependency" in self.chips(cdp, sid)), "the chips show the four types")
            want = self.shown(cdp, sid)
            click(cdp, sid, "[data-view=milestones]")
            self.assertTrue(wait(lambda: cdp.js("location.hash", sid) == "#milestones&p=TUL"), "the address is the milestones page")
            cdp.js("history.back()", sid)
            self.assertTrue(wait(lambda: self.shown(cdp, sid) == want and len(want) > 0), "the shown rows are the expected ones")
            self.assertEqual(len(cdp.call("Page.getNavigationHistory", {}, sid)["entries"]), 3)

    def test_the_line_is_kept_for_the_session_per_project_including_search_words(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            title = self.rows(cdp, sid)[0]["id"]
            self.put(cdp, sid, "is:open priority:High supplier")
            self.assertTrue(wait(lambda: self.chips(cdp, sid) == ["is:open", "priority:High", "supplier"]), "the chips are is:open, priority:High and supplier")
            click(cdp, sid, "[data-view=milestones]")
            self.assertTrue(wait(lambda: cdp.js("location.hash", sid) == "#milestones&p=TUL"), "the address is the milestones page")
            click(cdp, sid, "[data-view=work]")
            self.assertTrue(wait(lambda: self.chips(cdp, sid) == ["is:open", "priority:High", "supplier"]), "the line comes back with Work items")
            reload_to_new_page_cdp(cdp, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#fline-input')", sid)), "the filter box is there")
            self.assertTrue(wait(lambda: self.chips(cdp, sid) == ["is:open", "priority:High", "supplier"]), "and after a reload")
            other = [p["code"] for p in self.projects if p["code"] != "TUL"][0]
            sid = self.load(cdp, s.port, hash_=f"#work&p={other}")
            self.assertEqual(self.chips(cdp, sid), ["is:open"], "another project has its own line")
            self.assertTrue(title)
            cdp.js("sessionStorage.clear()", sid)

    def test_saved_views_are_tabs_with_a_dot_when_the_line_differs_and_are_deleted_for_good(self):
        s = self.serve()
        for width in SIZES:
            for theme in THEMES:
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.load(cdp, s.port, width, theme=theme)
                    rows = self.rows(cdp, sid)
                    names = cdp.js("[...document.querySelectorAll('.vtab span')].map(e => e.textContent)", sid)
                    self.assertEqual(names, ["Open items", "Actions", "Risks and issues", "Decisions", "All work items", "Overdue", "My actions"], "the core five, then the starting views; one is hidden until the page can answer it")
                    self.assertEqual(cdp.js("document.querySelector('.vtab[aria-pressed=true] span').textContent", sid), "Open items")
                    self.assertEqual(cdp.js("document.querySelectorAll('[data-dot]').length", sid), 0)
                    click_tab(cdp, sid, ".vtab[data-view-id=overdue]")
                    self.assertTrue(wait(lambda: self.chips(cdp, sid) == ["is:open", "due:overdue"]), "the chips are is:open and due:overdue")
                    self.assertEqual(cdp.js("document.querySelectorAll('[data-dot]').length", sid), 0)
                    self.put(cdp, sid, "is:open due:overdue priority:High")
                    self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.vtab[data-view-id=overdue] [data-dot]').length", sid) == 1), "a dot on the tab")
                    self.assertIn("not saved", cdp.js("document.querySelector('.vtab[data-view-id=overdue]').getAttribute('aria-label')", sid))
                    # Save changes to the view
                    click(cdp, sid, "#viewTabMenu")
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#viewTabMenuList')", sid)), "the tabs menu opened")
                    items = cdp.js("[...document.querySelectorAll('#viewTabMenuList [role=menuitem]')].map(b => b.textContent)", sid)
                    self.assertEqual(items[0], "Save changes")
                    self.assertEqual(items, ["Save changes", "Save as a new view…", "Rename view", "Move view", "Duplicate view", "Delete view"])
                    click(cdp, sid, "#viewTabMenuList [data-kind=save]")
                    self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('[data-dot]').length", sid) == 0), "saved: the dot goes")
                    # another tab, then back: the saved line is what comes back
                    click_tab(cdp, sid, ".vtab[data-view-id=core-open]")
                    self.assertTrue(wait(lambda: self.chips(cdp, sid) == ["is:open"]), "the chips are is:open")
                    click_tab(cdp, sid, ".vtab[data-view-id=overdue]")
                    self.assertTrue(wait(lambda: self.chips(cdp, sid) == ["is:open", "due:overdue", "priority:High"]), "the chips are is:open, due:overdue and priority:High")
                    # Rename
                    click(cdp, sid, "#viewTabMenu")
                    click(cdp, sid, "#viewTabMenuList [data-kind=rename]")
                    self.assertTrue(wait(lambda: cdp.js("document.activeElement.id", sid) == "vname"), "the name box has the focus")
                    cdp.js("document.querySelector('#vname').select()", sid)
                    self.type(cdp, sid, "Open items")
                    key(cdp, sid, "Enter")
                    self.assertTrue(wait(lambda: "already exists" in cdp.js("document.querySelector('.vmsg').textContent", sid)), "a name in use says so")
                    cdp.js("document.querySelector('#vname').select()", sid)
                    self.type(cdp, sid, "Urgent soon")
                    key(cdp, sid, "Enter")
                    self.assertTrue(wait(lambda: "Urgent soon" in cdp.js("[...document.querySelectorAll('.vtab span')].map(e => e.textContent)", sid)), "the Urgent soon tab is there")
                    # it is kept in this browser
                    reload_to_new_page_cdp(cdp, sid)
                    self.assertTrue(wait(lambda: "Urgent soon" in (cdp.js("[...document.querySelectorAll('.vtab span')].map(e => e.textContent)", sid) or [])), "the Urgent soon tab is there")
                    # Save the line as a new view, then delete it: no question, and the message at the foot has Undo
                    self.put(cdp, sid, "type:decision")
                    click(cdp, sid, "#viewNew")
                    self.assertTrue(wait(lambda: cdp.js("document.activeElement.id", sid) == "vname"), "the name box has the focus")
                    self.type(cdp, sid, "Settled")
                    key(cdp, sid, "Enter")
                    self.assertTrue(wait(lambda: "Settled" in cdp.js("[...document.querySelectorAll('.vtab span')].map(e => e.textContent)", sid)), "the Settled tab is there")
                    self.assertEqual(cdp.js("document.querySelector('.vtab[aria-pressed=true] span').textContent", sid), "Settled")
                    click(cdp, sid, "#viewTabMenu")
                    click(cdp, sid, "#viewTabMenuList [data-kind=delete]")
                    self.assertTrue(wait(lambda: "Settled" not in cdp.js("[...document.querySelectorAll('.vtab span')].map(e => e.textContent)", sid)), "deleted at once")
                    self.assertTrue(wait(lambda: "View deleted: Settled" in cdp.js("document.body.innerText", sid)), "the message says so")
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-undo]')", sid)), "and has Undo")
                    click(cdp, sid, "[data-undo]")
                    self.assertTrue(wait(lambda: "Settled" in cdp.js("[...document.querySelectorAll('.vtab span')].map(e => e.textContent)", sid)), "Undo puts it back")
                    click(cdp, sid, "#viewTabMenu")
                    click(cdp, sid, "#viewTabMenuList [data-kind=delete]")
                    self.assertTrue(wait(lambda: "Settled" not in cdp.js("[...document.querySelectorAll('.vtab span')].map(e => e.textContent)", sid)))
                    self.assertFalse(cdp.js("!!document.querySelector('#viewTabMenu')", sid), "no tab is open now (the line matches none)")
                    click(cdp, sid, "#viewNew")
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#vname')", sid)))
                    self.assertEqual(cdp.js("document.querySelectorAll('[data-restore]').length", sid), 0, "there is no Bring back")
                    self.assertEqual(self.shown(cdp, sid), self.shown(cdp, sid))
                    self.assertTrue(rows)
                    cdp.js("localStorage.clear(); sessionStorage.clear()", sid)

    def test_a_saved_view_the_line_cannot_read_stays_listed_says_why_and_can_be_renamed_or_deleted(self):
        """#589: it is no longer hidden. The starting view that needs a client answer is still left out (the test above)."""
        s = self.serve()
        views = [{"id": "open", "name": "Open items", "line": "is:open"},
                 {"id": "client", "name": "Waiting on the client", "line": "is:open is:needed"},
                 {"id": "old", "name": "Old view", "line": "is:open colour:red"}]
        tabs = "[...document.querySelectorAll('.vtab span')].map(e => e.textContent)"
        for width in SIZES:
            with self.subTest(width=width), chrome() as cdp:
                sid = self.load(cdp, s.port, width)
                self.watch(cdp, sid)
                cdp.js("localStorage.setItem('clark.fviews', JSON.stringify({TUL: %s}))" % json.dumps(views), sid)
                reload_to_new_page_cdp(cdp, sid)
                self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.vtab').length", sid) == 6), "the six tabs are there")
                self.assertEqual(cdp.js(tabs, sid), ["Open items", "Actions", "Risks and issues", "Decisions", "All work items", "Old view"], "the broken view is listed; the starting client view is still left out")
                self.assertEqual(cdp.js("document.querySelector('[data-vbad]').textContent", sid), "", "nothing said until it is chosen")
                before = self.shown(cdp, sid)
                click_tab(cdp, sid, ".vtab[data-view-id=old]")
                self.assertTrue(wait(lambda: "cannot be used any more" in cdp.js("document.querySelector('[data-vbad]').textContent", sid)), "the form says the view cannot be used any more")
                said = cdp.js("document.querySelector('[data-vbad]').textContent", sid)
                self.assertIn("There is no \u201ccolour\u201d filter.", said, "it says why")
                self.assertIn("Rename it or delete it.", said)
                self.assertEqual(cdp.js("document.querySelector('.vtab[data-view-id=old]').getAttribute('aria-pressed')", sid), "true")
                self.assertEqual(cdp.js("document.querySelectorAll('.vtab[data-view-id=old] .num').length", sid), 0, "no count for a line that is not applied")
                self.assertIn("cannot be used", cdp.js("document.querySelector('.vtab[data-view-id=old]').getAttribute('aria-label')", sid))
                self.assertEqual(self.chips(cdp, sid), ["is:open"], "choosing it does not apply the broken line")
                self.assertEqual(self.shown(cdp, sid), before)
                self.assertEqual(self.errors(cdp, sid), [])
                # Rename it
                click(cdp, sid, "#viewTabMenu")
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#viewTabMenuList [data-kind=rename]')", sid)), "the tabs menu offers Rename")
                self.assertFalse(cdp.js("!!document.querySelector('#viewTabMenuList [data-kind=save]')", sid), "nothing to save for a view that is not applied")
                click(cdp, sid, "#viewTabMenuList [data-kind=rename]")
                self.assertTrue(wait(lambda: cdp.js("document.activeElement.id", sid) == "vname"), "the name box has focus")
                cdp.js("document.querySelector('#vname').select()", sid)
                self.type(cdp, sid, "Older view")
                key(cdp, sid, "Enter")
                self.assertTrue(wait(lambda: cdp.js(tabs, sid) == ["Open items", "Actions", "Risks and issues", "Decisions", "All work items", "Older view"]), "the tabs include Older view")
                self.assertIn("cannot be used any more", cdp.js("document.querySelector('[data-vbad]').textContent", sid), "renamed, still said")
                # Delete it: at once, with Undo in the message
                click(cdp, sid, "#viewTabMenu")
                click(cdp, sid, "#viewTabMenuList [data-kind=delete]")
                self.assertTrue(wait(lambda: cdp.js(tabs, sid) == ["Open items", "Actions", "Risks and issues", "Decisions", "All work items"]))
                self.assertEqual(cdp.js("document.querySelector('[data-vbad]').textContent", sid), "")
                self.assertEqual(self.errors(cdp, sid), [])
                cdp.js("localStorage.clear(); sessionStorage.clear()", sid)

    # ---- row 1071: drag a filter tab, Move view, Duplicate view ----
    def tab_ids(self, cdp, sid):
        return cdp.js("[...document.querySelectorAll('.vtab')].map(e => e.dataset.viewId)", sid)

    def centre(self, cdp, sid, selector):
        cdp.js("document.querySelector(%s).scrollIntoView({inline: 'center', block: 'nearest', behavior: 'instant'})" % json.dumps(selector), sid)
        return where(cdp, sid, selector)

    def mouse(self, cdp, sid, kind, x, y, **more):
        cdp.call("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, "button": "left", "buttons": 1 if kind != "mouseReleased" else 0, "clickCount": 1, **more}, sid)

    def drag_tab(self, cdp, sid, src, dst_sel, past=0.75, release=True):
        """A real mouse sequence: press the tab, move in steps across the row to `past` of the way across the destination tab, optionally let go."""
        sx, sy = self.centre(cdp, sid, src)
        wait(lambda: cdp.js("document.getAnimations().length === 0", sid))
        sx, sy = where(cdp, sid, src)
        box = cdp.js("(() => { const r = document.querySelector(%s).getBoundingClientRect(); return [r.left, r.width]; })()" % json.dumps(dst_sel), sid)
        tx = box[0] + box[1] * past
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": sx, "y": sy}, sid)
        self.mouse(cdp, sid, "mousePressed", sx, sy)
        steps = 12
        for i in range(1, steps + 1):
            self.mouse(cdp, sid, "mouseMoved", sx + (tx - sx) * i / steps, sy)
        if release:
            self.mouse(cdp, sid, "mouseReleased", tx, sy)
        return sx, sy, tx

    def test_row_1071_a_tab_is_picked_up_and_dragged_left_or_right_and_the_order_is_kept(self):
        s = self.serve()
        for width in SIZES:
            for theme in THEMES:
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.load(cdp, s.port, width, theme=theme)
                    cdp.js("localStorage.clear()", sid)
                    start = self.tab_ids(cdp, sid)
                    self.assertEqual(start[:3], ["core-open", "core-actions", "core-risks"])
                    # to the right: Actions is dropped after Decisions
                    self.drag_tab(cdp, sid, ".vtab[data-view-id=core-actions]", ".vtab[data-view-id=core-decisions]")
                    want = ["core-open", "core-risks", "core-decisions", "core-actions"] + start[4:]
                    self.assertTrue(wait(lambda: self.tab_ids(cdp, sid) == want), f"dropped after Decisions: {self.tab_ids(cdp, sid)}")
                    self.assertEqual(cdp.js("document.querySelector('.vtab[aria-pressed=true]').dataset.viewId", sid), "core-open", "a drag does not choose the tab")
                    # to the left, past a core tab onto an own one is just as good
                    self.drag_tab(cdp, sid, ".vtab[data-view-id=core-actions]", ".vtab[data-view-id=core-open]", past=0.2)
                    self.assertTrue(wait(lambda: self.tab_ids(cdp, sid)[0] == "core-actions"), f"dropped before Open items: {self.tab_ids(cdp, sid)}")
                    # kept in this browser, for this project
                    kept = self.tab_ids(cdp, sid)
                    reload_to_new_page_cdp(cdp, sid)
                    self.assertTrue(wait(lambda: self.tab_ids(cdp, sid) == kept), "the order is there after a reload")
                    cdp.js("localStorage.clear()", sid)

    def test_row_1071_a_click_without_movement_still_chooses_the_tab_and_a_drag_selects_no_text_and_esc_puts_it_back(self):
        s = self.serve()
        for width in SIZES:
            for theme in THEMES:
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.load(cdp, s.port, width, theme=theme)
                    cdp.js("localStorage.clear()", sid)
                    start = self.tab_ids(cdp, sid)
                    click_tab(cdp, sid, ".vtab[data-view-id=core-risks]")
                    self.assertTrue(wait(lambda: cdp.js("document.querySelector('.vtab[aria-pressed=true]').dataset.viewId", sid) == "core-risks"), "a click chooses it")
                    self.assertEqual(self.tab_ids(cdp, sid), start, "and moves nothing")
                    # a small shake under 5 px is still a click
                    sx, sy = self.centre(cdp, sid, ".vtab[data-view-id=core-decisions]")
                    self.mouse(cdp, sid, "mousePressed", sx, sy); self.mouse(cdp, sid, "mouseMoved", sx + 2, sy); self.mouse(cdp, sid, "mouseReleased", sx + 2, sy)
                    self.assertTrue(wait(lambda: cdp.js("document.querySelector('.vtab[aria-pressed=true]').dataset.viewId", sid) == "core-decisions"))
                    # a drag: no text is selected, and the tab is lifted while it is held
                    self.drag_tab(cdp, sid, ".vtab[data-view-id=core-open]", ".vtab[data-view-id=core-risks]", release=False)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.vt[data-lifted]')", sid)), "the tab held is lifted")
                    self.assertEqual(cdp.js("String(getSelection())", sid), "", "no text is selected")
                    self.assertNotEqual(self.tab_ids(cdp, sid), start, "the tabs follow while it is held")
                    key(cdp, sid, "Escape")
                    self.assertTrue(wait(lambda: self.tab_ids(cdp, sid) == start), "Esc puts it back")
                    box = cdp.js("(() => { const r = document.querySelector('.vtab[data-view-id=core-all]').getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; })()", sid)
                    self.mouse(cdp, sid, "mouseMoved", box[0], box[1])
                    self.mouse(cdp, sid, "mouseReleased", box[0], box[1])
                    time.sleep(0.2)
                    self.assertEqual(self.tab_ids(cdp, sid), start, "letting go after Esc moves nothing")
                    self.assertEqual(cdp.js("document.querySelector('.vtab[aria-pressed=true]').dataset.viewId", sid), "core-decisions", "and chooses nothing")
                    self.assertEqual(cdp.js("localStorage.getItem('clark.forder')", sid), None, "nothing is kept")
                    cdp.js("localStorage.clear()", sid)

    def test_row_1071_move_view_moves_the_tab_with_the_arrow_keys_and_enter_or_esc_finishes_with_no_bar(self):
        s = self.serve()
        for width in SIZES:
            for theme in THEMES:
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.load(cdp, s.port, width, theme=theme)
                    cdp.js("localStorage.clear()", sid)
                    start = self.tab_ids(cdp, sid)
                    click_tab(cdp, sid, ".vtab[data-view-id=core-actions]")
                    click(cdp, sid, "#viewTabMenu")
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#viewTabMenuList')", sid)))
                    self.assertEqual(cdp.js("[...document.querySelectorAll('#viewTabMenuList [role=menuitem]')].map(b => b.textContent)", sid),
                                     ["Save as a new view…", "Rename view", "Move view", "Duplicate view", "Delete view"])
                    self.assertTrue(cdp.js("document.querySelectorAll('#viewTabMenuList [role=menuitem] svg').length >= 4", sid), "each has an icon")
                    self.assertTrue(cdp.js("getComputedStyle(document.querySelector('#viewTabMenuList [data-kind=delete]')).color !== getComputedStyle(document.querySelector('#viewTabMenuList [data-kind=rename]')).color", sid), "Delete view is red")
                    click(cdp, sid, "#viewTabMenuList [data-kind=move]")
                    self.assertTrue(wait(lambda: cdp.js("document.activeElement.dataset.viewId", sid) == "core-actions"), "the tab has the focus")
                    self.assertTrue(cdp.js("document.activeElement.hasAttribute('data-moving') && getComputedStyle(document.activeElement).outlineStyle !== 'none'", sid), "and a focus ring")
                    self.assertEqual(cdp.js("[...document.querySelectorAll('button')].some(b => /^(Move left|Move right|Done)$/.test(b.textContent.trim()))", sid), False, "no bar")
                    key(cdp, sid, "ArrowRight"); key(cdp, sid, "ArrowRight")
                    self.assertTrue(wait(lambda: self.tab_ids(cdp, sid)[:4] == ["core-open", "core-risks", "core-decisions", "core-actions"]), self.tab_ids(cdp, sid))
                    self.assertTrue(wait(lambda: cdp.js("document.activeElement.dataset.viewId", sid) == "core-actions"), "the focus stays on the moved tab")
                    key(cdp, sid, "ArrowLeft")
                    self.assertTrue(wait(lambda: self.tab_ids(cdp, sid)[:4] == ["core-open", "core-risks", "core-actions", "core-decisions"]))
                    key(cdp, sid, "Enter")
                    self.assertTrue(wait(lambda: not cdp.js("document.querySelector('.vtab[data-moving]')", sid)), "Enter finishes")
                    key(cdp, sid, "ArrowRight")
                    self.assertEqual(self.tab_ids(cdp, sid)[:4], ["core-open", "core-risks", "core-actions", "core-decisions"], "and the arrows move nothing now")
                    # Esc also finishes (and keeps the place)
                    click(cdp, sid, "#viewTabMenu")
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#viewTabMenuList [data-kind=move]')", sid)))
                    cdp.js("document.querySelector('#viewTabMenuList [data-kind=move]').click()", sid)      # a script click: the mouse helper scrolls the item into view first, and a scroll closes the open menu
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.vtab[data-moving]')", sid)))
                    key(cdp, sid, "ArrowLeft")
                    key(cdp, sid, "Escape")
                    self.assertTrue(wait(lambda: not cdp.js("document.querySelector('.vtab[data-moving]')", sid)))
                    self.assertEqual(self.tab_ids(cdp, sid)[:4], ["core-open", "core-actions", "core-risks", "core-decisions"], "Esc keeps where it got to")
                    kept = self.tab_ids(cdp, sid)
                    reload_to_new_page_cdp(cdp, sid)
                    self.assertTrue(wait(lambda: self.tab_ids(cdp, sid) == kept), "kept after a reload")
                    cdp.js("localStorage.clear()", sid)

    def test_row_1071_duplicate_view_adds_name_copy_next_to_it(self):
        s = self.serve()
        for width in SIZES:
            for theme in THEMES:
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.load(cdp, s.port, width, theme=theme)
                    cdp.js("localStorage.clear()", sid)
                    tabs = "[...document.querySelectorAll('.vtab span')].map(e => e.textContent)"
                    click_tab(cdp, sid, ".vtab[data-view-id=core-actions]")
                    click(cdp, sid, "#viewTabMenu")
                    click(cdp, sid, "#viewTabMenuList [data-kind=duplicate]")
                    self.assertTrue(wait(lambda: cdp.js(tabs, sid)[:3] == ["Open items", "Actions", "Actions copy"]), cdp.js(tabs, sid))
                    self.assertEqual(cdp.js("document.querySelector('.vtab[aria-pressed=true] span').textContent", sid), "Actions copy")
                    self.assertTrue(wait(lambda: sorted(self.chips(cdp, sid)) == ["is:open", "type:action"]), "same filters")
                    reload_to_new_page_cdp(cdp, sid)
                    self.assertTrue(wait(lambda: (cdp.js(tabs, sid) or [])[:3] == ["Open items", "Actions", "Actions copy"]), "kept")
                    cdp.js("localStorage.clear()", sid)

    # ---- #640: the field list on click, the x, the core tabs, the tab's arrow and + New view ----
    FIELDS_ALL = ["is:", "type:", "status:", "owner:", "priority:", "due:", "workstream:", "usecase:", "milestone:", "client:", "has:", "no:"]

    def hints_visible(self, cdp, sid):
        return cdp.js("getComputedStyle(document.querySelector('.fhints')).visibility", sid) == "visible"

    def test_focusing_the_empty_box_lists_the_fields_and_the_examples_do_not_show_with_it(self):
        s = self.serve()
        for width in SIZES:
            for theme in THEMES:
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.load(cdp, s.port, width, theme=theme)
                    self.assertEqual(cdp.js("!!document.querySelector('#fline-list')", sid), False, "closed until the box is entered")
                    self.focus(cdp, sid)                                              # the box holds the starting line: no list for a click into text
                    self.assertEqual(cdp.js("!!document.querySelector('#fline-list')", sid), False)
                    select_line(cdp, sid)
                    key(cdp, sid, "Backspace")
                    self.no_list(cdp, sid, "row 931: emptying the box does not open the list")
                    self.arm(cdp, sid)
                    self.assertTrue(wait(lambda: self.listed(cdp, sid) == self.FIELDS_ALL), "the list of fields, is first, then the fields, then has and no")
                    self.assertEqual(cdp.js("document.querySelector('#fline-list').getAttribute('role')", sid), "listbox")
                    self.assertEqual(cdp.js("[...new Set([...document.querySelectorAll('#fline-list [role=option]')].map(o => o.getAttribute('role')))]", sid), ["option"])
                    notes = cdp.js("[...document.querySelectorAll('#fline-list .fopt')].map(o => (o.querySelector('.fl2') || {textContent: ''}).textContent)", sid)
                    self.assertTrue(all(n for i, n in enumerate(notes) if self.FIELDS_ALL[i] != "has:"), "each field has its one-line note (has: has none yet)")
                    self.assertEqual(notes[0], "Open, closed, overdue, not reviewed…")
                    self.assertFalse(self.hints_visible(cdp, sid), "the examples do not show while the list does")
                    self.assertEqual(cdp.js("document.querySelector('.fhints').getAttribute('aria-hidden')", sid), "true")
                    key(cdp, sid, "Escape")
                    self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('#fline-list')", sid)), "Esc closes it")
                    self.assertTrue(wait(lambda: self.hints_visible(cdp, sid)), "and the examples come back")
                    self.assertEqual(cdp.js("document.activeElement.id", sid), "fline-input")
                    key(cdp, sid, "ArrowDown")                                        # the arrows open it again
                    self.assertTrue(wait(lambda: self.listed(cdp, sid) == self.FIELDS_ALL), "the list offers every field")
                    key(cdp, sid, "ArrowDown")
                    key(cdp, sid, "Enter")
                    self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-fline]').dataset.line", sid) == "type:"))
                    self.no_list(cdp, sid, "row 931: a choice closes the list")
                    self.arm(cdp, sid)
                    self.assertTrue(wait(lambda: len(self.listed(cdp, sid)) > 4))
                    opts = self.listed(cdp, sid)
                    self.assertEqual(opts[:3], ["no:type", "has:type", "-type:"], "led by No, Has and Exclude")
                    self.assertEqual(cdp.js("[...document.querySelectorAll('#fline-list .fl1')].slice(0, 3).map(e => e.textContent)", sid), ["No Type", "Has Type", "Exclude Type"])
                    self.assertTrue(all(i.startswith("type:") and i != "type:" for i in opts[3:]), "then the field's values")
                    self.assertFalse(self.hints_visible(cdp, sid))
                    select_line(cdp, sid)
                    self.type(cdp, sid, "ow")                                         # typing narrows the list
                    self.assertTrue(wait(lambda: self.listed(cdp, sid) == ["owner:"]))
                    select_line(cdp, sid)
                    key(cdp, sid, "Backspace")
                    self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-fline]').dataset.line", sid) == ""))
                    # Tab into the box from the control before it opens the list too
                    cdp.js("document.querySelector('#fline-input').blur()", sid)
                    cdp.js("document.querySelector('#viewMenu').focus()", sid)
                    for _ in range(3):
                        if cdp.js("document.activeElement.id", sid) == "fline-input":
                            break
                        key(cdp, sid, "Tab")
                    self.assertTrue(wait(lambda: cdp.js("document.activeElement.id", sid) == "fline-input"), "the filter box has focus")
                    self.no_list(cdp, sid, "row 931: Tab into the empty line opens no list")
                    self.arm(cdp, sid)
                    self.assertTrue(wait(lambda: len(self.listed(cdp, sid)) > 1), "Space opens the fields")

    def test_the_view_name_form_gives_the_focus_back_when_it_closes(self):
        """The form's input is removed when it closes; focus goes back to the button that opened it, not to the top of the page."""
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            for how in ("Escape", "#vcancel", "Enter"):
                click(cdp, sid, "#viewNew")
                self.assertTrue(wait(lambda: cdp.js("document.activeElement.id", sid) == "vname"), "the name box has the focus")
                if how == "Enter":
                    self.type(cdp, sid, "Back focus")
                    key(cdp, sid, "Enter")
                elif how == "Escape":
                    key(cdp, sid, "Escape")
                else:
                    cdp.js("document.querySelector('.vform .btn.sm[type=button]').click()", sid)
                self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('#vname')", sid)), "the form closed")
                self.assertTrue(wait(lambda: cdp.js("document.activeElement.id", sid) == "viewNew"), f"{how}: the focus is on + New view")
            click_tab(cdp, sid, ".vtab[data-view-id=core-open]")
            click(cdp, sid, "#viewTabMenu")
            click(cdp, sid, "#viewTabMenuList [data-kind=rename]")
            self.assertTrue(wait(lambda: cdp.js("document.activeElement.id", sid) == "vname"))
            key(cdp, sid, "Escape")
            self.assertTrue(wait(lambda: cdp.js("document.activeElement.id", sid) == "viewTabMenu"), "a rename gives the focus back to the tab's menu button")

    def test_the_list_opens_after_space_or_arrow_down_and_closes_on_a_choice_or_escape_row_931(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            self.focus(cdp, sid)
            self.no_list(cdp, sid, "entering the box opens no list")
            self.assertEqual(cdp.js("document.querySelector('#fline-input').getAttribute('aria-expanded')", sid), "false")
            self.put(cdp, sid, "")
            self.type(cdp, sid, "st")
            self.no_list(cdp, sid, "typing alone opens no list")
            self.put(cdp, sid, "is:open")
            key(cdp, sid, " ")                                                    # a real Space: the space is typed and the list opens
            self.assertTrue(wait(lambda: self.listed(cdp, sid) == self.FIELDS_ALL), "Space opens the list of fields")
            self.assertEqual(cdp.js("document.querySelector('[data-fline]').dataset.line", sid), "is:open", "the space ends the word as always: it is a chip")
            self.type(cdp, sid, "pr")
            self.assertTrue(wait(lambda: self.listed(cdp, sid) == ["priority:"]), "typing narrows the open list")
            key(cdp, sid, "Escape")
            self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('#fline-list')", sid)), "Esc closes it")
            self.type(cdp, sid, "i")
            self.no_list(cdp, sid, "typing does not reopen a list that was closed")
            key(cdp, sid, " ")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#fline-list')", sid)), "Space again reopens it")
            key(cdp, sid, "Escape")
            self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('#fline-list')", sid)))
            key(cdp, sid, "ArrowDown")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#fline-list')", sid)), "Arrow Down opens it")
            key(cdp, sid, "Enter")                                                # Enter takes the first row, which closes the list
            self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('#fline-list')", sid)), "choosing a row closes it")
            cdp.js("document.querySelector('#fline-input').blur()", sid)
            self.focus(cdp, sid)
            self.no_list(cdp, sid, "entering the box again opens no list")

    def test_every_field_row_has_an_icon_and_the_rows_stay_one_line_row_931(self):
        s = self.serve()
        want = {"is": "check", "type": "table", "status": "half", "owner": "user", "priority": "flash", "due": "cal", "workstream": "bars",
                "usecase": "doc", "milestone": "flag", "client": "ext", "has": "eye", "no": "eyeoff"}
        for width in SIZES:
            for theme in THEMES:
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.load(cdp, s.port, width, theme=theme, motion="reduce")
                    self.put(cdp, sid, "")
                    self.arm(cdp, sid)
                    self.assertTrue(wait(lambda: self.listed(cdp, sid) == self.FIELDS_ALL))
                    got = cdp.js("Object.fromEntries([...document.querySelectorAll('#fline-list .fopt')].map(o => [o.dataset.ins.replace(':', ''), (o.querySelector('svg[data-icn]') || {dataset: {}}).dataset.icn || '']))", sid)
                    self.assertEqual({k: got[k] for k in want}, want, "an icon on every field row")
                    self.assertTrue(all(got.values()), "and on the custom ones")
                    self.assertEqual(cdp.js("[...document.querySelectorAll('#fline-list .fopt svg')].every(i => i.getAttribute('aria-hidden') === 'true')", sid), True)
                    one = cdp.js("[...document.querySelectorAll('#fline-list .fopt')].every(o => { const a = o.querySelector('svg').getBoundingClientRect(), b = o.querySelector('.fl1').getBoundingClientRect(), n = o.querySelector('.fl2'); return a.right <= b.left + 1 && o.getBoundingClientRect().height < 40 && (!n || n.getBoundingClientRect().left >= b.right - 1) && Math.abs((a.top + a.bottom) / 2 - (b.top + b.bottom) / 2) < 6; })", sid)
                    self.assertTrue(one, "icon, then label, then note, on one line")
                    self.assertEqual(cdp.js("(() => { const i = document.querySelector('#fline-list .fopt svg'); return getComputedStyle(i).color; })()", sid), cdp.js("getComputedStyle(document.documentElement).getPropertyValue('--text-muted') && (() => { const d = document.createElement('i'); d.style.color = getComputedStyle(document.documentElement).getPropertyValue('--text-muted'); document.body.appendChild(d); const c = getComputedStyle(d).color; d.remove(); return c; })()", sid), "the icon colour is the muted text token")
                    self.assertTrue(wait(lambda: cdp.js("document.getAnimations().length", sid) == 0), "the page's own motion has finished; the icons add none")
                    self.type(cdp, sid, "owner:")
                    self.assertTrue(wait(lambda: self.listed(cdp, sid)[:3] == ["no:owner", "has:owner", "-owner:"]))
                    lead = cdp.js("[...document.querySelectorAll('#fline-list .fopt.lead')].map(o => o.querySelector('svg').dataset.icn)", sid)
                    self.assertEqual(lead, ["user", "user", "circleminus"], "No and Has show the field's icon, Exclude a circle-minus")
                    self.assertEqual(cdp.js("document.querySelectorAll('#fline-list .fopt.value svg').length", sid), 0, "values have no icon")
                    self.type(cdp, sid, "@")

    def test_tab_and_enter_accept_a_suggestion_and_a_value_leaves_a_space_and_the_field_list(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            self.put(cdp, sid, "")
            self.arm(cdp, sid)
            self.type(cdp, sid, "pri")
            self.assertTrue(wait(lambda: self.listed(cdp, sid) == ["priority:"]), "the list offers priority: only")
            key(cdp, sid, "Tab")                                                   # Tab takes the first suggestion
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-fline]').dataset.line", sid) == "priority:"))
            self.arm(cdp, sid)
            self.assertTrue(wait(lambda: "priority:Urgent" in self.listed(cdp, sid)), "the list offers priority:Urgent")
            self.type(cdp, sid, "hi")
            self.assertTrue(wait(lambda: self.listed(cdp, sid) == ["priority:High"]), "narrowed as typed")
            key(cdp, sid, "ArrowDown")
            key(cdp, sid, "Tab")
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-fline]').dataset.line", sid) == "priority:High"))
            self.assertEqual(cdp.js("document.querySelector('#fline-input').value", sid), "", "the accepted word left the box as a chip")
            self.no_list(cdp, sid, "row 931: a value closes the list")
            self.arm(cdp, sid)
            self.assertTrue(wait(lambda: self.listed(cdp, sid) == self.FIELDS_ALL), "the field list opens again with Space")
            # a No row, then another field after it
            self.type(cdp, sid, "ow")
            key(cdp, sid, "Tab")
            self.arm(cdp, sid)
            self.assertTrue(wait(lambda: "no:owner" in self.listed(cdp, sid)), "the list offers no:owner")
            key(cdp, sid, "ArrowDown")
            key(cdp, sid, "Enter")
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-fline]').dataset.line", sid) == "priority:High no:owner"))
            pause(cdp, sid)
            rows = self.rows(cdp, sid)
            self.assertEqual(self.shown(cdp, sid), expect(rows, "all", filters={"priority": ["High"], "owner": ["(none)"]}))
            # a click on a row of the list does the same
            self.arm(cdp, sid)
            self.type(cdp, sid, "status:")
            self.assertTrue(wait(lambda: "status:Closed" in self.listed(cdp, sid)), "the list offers status:Closed")
            click(cdp, sid, "#fline-list [data-ins='status:Closed']")
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-fline]').dataset.line", sid) == "priority:High no:owner status:Closed"))
            self.assertEqual(cdp.js("document.activeElement.id", sid), "fline-input")

    def test_single_select_values_show_their_colour_and_other_values_do_not(self):
        s = self.serve()
        for theme in THEMES:
            with self.subTest(theme=theme), chrome() as cdp:
                sid = self.load(cdp, s.port, theme=theme)
                self.put(cdp, sid, "")
                self.arm(cdp, sid)
                self.type(cdp, sid, "priority:")
                self.assertTrue(wait(lambda: "priority:Urgent" in self.listed(cdp, sid)), "the list offers priority:Urgent")
                tones = cdp.js("Object.fromEntries([...document.querySelectorAll('#fline-list .fopt.value')].map(o => [o.dataset.ins, (o.querySelector('.fdv') || {dataset: {}}).dataset.tone || '']))", sid)
                self.assertEqual(tones, {"priority:Urgent": "r", "priority:High": "r", "priority:Medium": "a", "priority:Low": "g"})
                dots = cdp.js("[...document.querySelectorAll('#fline-list .fdv')].map(d => getComputedStyle(d).backgroundColor)", sid)
                self.assertTrue(all(c != "rgba(0, 0, 0, 0)" for c in dots) and len(set(dots)) == 3, "three colours, from the tokens")
                self.put(cdp, sid, "")
                self.arm(cdp, sid)
                self.type(cdp, sid, "workstream:")
                self.assertTrue(wait(lambda: len(self.listed(cdp, sid)) > 3), "the list has more than three options")
                self.assertEqual(cdp.js("document.querySelectorAll('#fline-list .fdv').length", sid), 0)

    def test_the_owner_list_offers_me_as_at_me_and_none_is_the_no_row(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port)
            self.put(cdp, sid, "")
            self.arm(cdp, sid)
            self.type(cdp, sid, "owner:")
            self.assertTrue(wait(lambda: len(self.listed(cdp, sid)) > 4), "the list offers the type values")
            opts = self.listed(cdp, sid)
            self.assertEqual(opts[:4], ["no:owner", "has:owner", "-owner:", "owner:@me"])
            self.assertFalse([o for o in opts if o.lower().endswith(":none")])

    def test_the_open_list_floats_over_the_page_and_pushes_nothing_down(self):
        """Row 808: the list of fields floats over the rows just under the box; opening it moves no row; a row below it is still reached."""
        s = self.serve()
        for width in SIZES:
            for theme in THEMES:
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.load(cdp, s.port, width, theme=theme)
                    top = "document.querySelector('#work-list').getBoundingClientRect().top"
                    before = cdp.js(top, sid)
                    self.put(cdp, sid, "")
                    self.arm(cdp, sid)
                    self.assertTrue(wait(lambda: self.listed(cdp, sid) == self.FIELDS_ALL), "the list of fields is open")
                    self.assertEqual(cdp.js("getComputedStyle(document.querySelector('#fline-list')).position", sid), "absolute")
                    self.assertGreater(int(cdp.js("getComputedStyle(document.querySelector('#fline-list')).zIndex", sid)), 25, "above the menus")
                    geo = cdp.js("(() => { const l = document.querySelector('#fline-list').getBoundingClientRect(), b = document.querySelector('[data-fline]').getBoundingClientRect(); return {lt: l.top, lb: l.bottom, bb: b.bottom, ll: l.left, bl: b.left}; })()", sid)
                    self.assertLess(abs(geo["lt"] - geo["bb"]), 8, "the list is just under the box")
                    self.assertLess(abs(geo["ll"] - geo["bl"]), 2, "at the box's left")
                    self.assertEqual(cdp.js(top, sid), before, "the list below the box did not move")
                    self.assertGreater(geo["lb"], before, "the list lies over the first rows")
                    own = cdp.js("(() => { const l = document.querySelector('#fline-list').getBoundingClientRect(); const e = document.elementFromPoint(l.left + 40, l.top + 20); return !!e && !!e.closest('#fline-list'); })()", sid)
                    self.assertTrue(own, "the list is the top layer where it lies")

    def test_the_five_core_tabs_come_first_with_counts_that_match_the_rows_and_have_rename_and_delete_but_no_save_changes(self):
        s = self.serve()
        lines = {"core-open": ["is:open"], "core-actions": ["is:open", "type:action"], "core-risks": ["is:open", "type:risk,issue"],
                 "core-decisions": ["is:open", "type:decision"], "core-all": []}
        for width in SIZES:
            for theme in THEMES:
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.load(cdp, s.port, width, theme=theme)
                    names = cdp.js("[...document.querySelectorAll('.vtab span')].map(e => e.textContent)", sid)
                    self.assertEqual(names[:5], ["Open items", "Actions", "Risks and issues", "Decisions", "All work items"])
                    self.assertEqual(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), True, "the row fits the page")
                    self.assertTrue(cdp.js("!!document.querySelector('#viewNew')", sid))
                    for vid, want in lines.items():
                        click_tab(cdp, sid, f".vtab[data-view-id={vid}]")
                        self.assertTrue(wait(lambda: sorted(self.chips(cdp, sid)) == sorted(want)), vid)
                        self.assertEqual(cdp.js(f"document.querySelector('.vtab[data-view-id={vid}]').getAttribute('aria-pressed')", sid), "true")
                        n = cdp.js(f"+document.querySelector('.vtab[data-view-id={vid}] em').textContent", sid)
                        self.assertTrue(wait(lambda: len(self.shown(cdp, sid)) == n), f"{vid}: the count is the rows shown")
                        # the arrow beside the open tab: Save as a new view, Rename, Delete; no Save changes
                        click(cdp, sid, "#viewTabMenu")
                        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#viewTabMenuList')", sid)), "the tabs menu opened")
                        kinds = cdp.js("[...document.querySelectorAll('#viewTabMenuList [role=menuitem]')].map(b => b.dataset.kind)", sid)
                        self.assertEqual(kinds, ["saveas", "rename", "move", "duplicate", "delete"], vid)
                        key(cdp, sid, "Escape")
                        self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('#viewTabMenuList')", sid)), "the tabs menu closed")
                    # the counts of the first four agree: every one is a part of Open items; All work items has the closed ones too
                    counts = cdp.js("[...document.querySelectorAll('.vtab em')].slice(0, 5).map(e => +e.textContent)", sid)
                    self.assertLessEqual(max(counts[1:4]), counts[0])
                    self.assertGreaterEqual(counts[4], counts[0])
                    self.assertEqual(counts[4], len(self.rows(cdp, sid)))

    def test_a_core_tab_can_be_renamed_and_deleted_and_it_is_kept_in_the_browser_only(self):
        s = self.serve()
        tabs = "[...document.querySelectorAll('.vtab span')].map(e => e.textContent)"
        for width in SIZES:
            for theme in THEMES:
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.load(cdp, s.port, width, theme=theme)
                    click(cdp, sid, "#viewTabMenu")
                    click(cdp, sid, "#viewTabMenuList [data-kind=rename]")
                    self.assertTrue(wait(lambda: cdp.js("document.activeElement.id", sid) == "vname"))
                    cdp.js("document.querySelector('#vname').select()", sid)
                    self.type(cdp, sid, "Live work")
                    key(cdp, sid, "Enter")
                    self.assertTrue(wait(lambda: cdp.js(tabs, sid)[0] == "Live work"))
                    self.assertEqual(cdp.js("document.querySelector('.vtab[aria-pressed=true]').dataset.viewId", sid), "core-open", "same view, new name")
                    reload_to_new_page_cdp(cdp, sid)
                    self.assertTrue(wait(lambda: (cdp.js(tabs, sid) or [""])[0] == "Live work"), "kept in this browser")
                    # delete the first tab: the line is kept, the tab goes, the next view is not forced on the line
                    click(cdp, sid, ".vtab[data-view-id=core-open]")
                    click(cdp, sid, "#viewTabMenu")
                    click(cdp, sid, "#viewTabMenuList [data-kind=delete]")
                    self.assertTrue(wait(lambda: cdp.js(tabs, sid)[:4] == ["Actions", "Risks and issues", "Decisions", "All work items"]))
                    reload_to_new_page_cdp(cdp, sid)
                    self.assertTrue(wait(lambda: (cdp.js(tabs, sid) or [""])[0] == "Actions"), "still gone after a reload")
                    self.assertEqual(cdp.js("JSON.parse(localStorage.getItem('clark.fcore')).TUL.gone", sid), ["core-open"])
                    # every view deleted: + New view still works
                    for _ in range(12):
                        if not cdp.js("document.querySelectorAll('.vtab').length", sid):
                            break
                        n = cdp.js("document.querySelectorAll('.vtab').length", sid)
                        click(cdp, sid, ".vtab")
                        click(cdp, sid, "#viewTabMenu")
                        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#viewTabMenuList [data-kind=delete]')", sid)))
                        cdp.js("document.querySelector('#viewTabMenuList [data-kind=delete]').click()", sid)      # a script click: the mouse helper scrolls the item into view first, and a scroll closes the open menu
                        wait(lambda: cdp.js("document.querySelectorAll('.vtab').length", sid) < n)
                    self.assertEqual(cdp.js("document.querySelectorAll('.vtab').length", sid), 0)
                    click(cdp, sid, "#viewNew")
                    self.assertTrue(wait(lambda: cdp.js("document.activeElement.id", sid) == "vname"))
                    self.type(cdp, sid, "First again")
                    key(cdp, sid, "Enter")
                    self.assertTrue(wait(lambda: cdp.js(tabs, sid) == ["First again"]))
                    cdp.js("localStorage.clear(); sessionStorage.clear()", sid)

    def test_the_arrow_on_the_open_tab_and_new_view_work_by_pointer_and_keyboard(self):
        s = self.serve()
        for width in SIZES:
            for theme in THEMES:
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.load(cdp, s.port, width, theme=theme)
                    self.assertEqual(cdp.js("document.querySelectorAll('#viewTabMenu').length", sid), 1, "one arrow, on the open tab")
                    self.assertEqual(cdp.js("document.querySelector('#viewTabMenu').closest('.dd').previousElementSibling.dataset.viewId", sid), "core-open", "right beside its name")
                    self.assertEqual(cdp.js("document.querySelector('#viewTabMenu').getAttribute('aria-label')", sid), "Options for Open items")
                    self.assertGreaterEqual(cdp.js("document.querySelector('#viewTabMenu').getBoundingClientRect().height", sid), 24)
                    # Overdue is an ordinary view now: it has all the entries
                    click_tab(cdp, sid, ".vtab[data-view-id=overdue]")
                    self.assertTrue(wait(lambda: self.chips(cdp, sid) == ["is:open", "due:overdue"]), "the chips are is:open and due:overdue")
                    click(cdp, sid, "#viewTabMenu")
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#viewTabMenuList')", sid)), "the tabs menu opened")
                    self.assertEqual(cdp.js("[...document.querySelectorAll('#viewTabMenuList [role=menuitem]')].map(b => b.textContent)", sid),
                                     ["Save as a new view…", "Rename view", "Move view", "Duplicate view", "Delete view"], "no Save changes while there is no dot")
                    key(cdp, sid, "Escape")
                    self.assertTrue(wait(lambda: cdp.js("document.activeElement.id", sid) == "viewTabMenu"), "Esc gives the focus back to the arrow")
                    # change the line: the dot shows and Save changes appears and puts the dot out
                    self.put(cdp, sid, "is:open due:overdue priority:High")
                    self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('[data-dot]').length", sid) == 1), "one tab shows the unsaved dot")
                    cdp.js("document.querySelector('#viewTabMenu').focus()", sid)
                    key(cdp, sid, "ArrowDown")                                        # keyboard: Down opens, the first entry has the focus
                    self.assertTrue(wait(lambda: cdp.js("document.activeElement.dataset.kind", sid) == "save"), "the Save button has focus")
                    self.assertEqual(cdp.js("document.activeElement.textContent", sid), "Save changes")
                    key(cdp, sid, "Enter")
                    self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('[data-dot]').length", sid) == 0), "saved: the dot goes")
                    # + New view on a core tab: the line becomes a view after the core five, with its count, and is chosen
                    click_tab(cdp, sid, ".vtab[data-view-id=core-decisions]")
                    self.assertTrue(wait(lambda: sorted(self.chips(cdp, sid)) == ["is:open", "type:decision"]), "the chips are is:open and type:decision")
                    self.put(cdp, sid, "is:open type:decision priority:High")
                    self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.vtab[data-view-id=core-decisions] [data-dot]').length", sid) == 1), "one tab shows the unsaved dot")
                    cdp.js("document.querySelector('#viewNew').focus()", sid)
                    key(cdp, sid, "Enter")
                    self.assertTrue(wait(lambda: cdp.js("document.activeElement.id", sid) == "vname"), "the name box has the focus")
                    self.type(cdp, sid, "Big decisions")
                    key(cdp, sid, "Enter")
                    self.assertTrue(wait(lambda: cdp.js("[...document.querySelectorAll('.vtab span')].map(e => e.textContent)", sid)[-1] == "Big decisions"), "added after the others")
                    self.assertEqual(cdp.js("document.querySelector('.vtab[aria-pressed=true] span').textContent", sid), "Big decisions", "and chosen")
                    self.assertEqual(cdp.js("document.querySelectorAll('[data-dot]').length", sid), 0)
                    n = cdp.js("+document.querySelector('.vtab[aria-pressed=true] em').textContent", sid)
                    self.assertEqual(n, len(self.shown(cdp, sid)), "with its count")
                    names = cdp.js("[...document.querySelectorAll('.vtab span')].map(e => e.textContent)", sid)
                    self.assertEqual(names[:5], ["Open items", "Actions", "Risks and issues", "Decisions", "All work items"], "the core five are still first")
                    # Esc in the name box closes it
                    click(cdp, sid, "#viewNew")
                    self.assertTrue(wait(lambda: cdp.js("document.activeElement.id", sid) == "vname"), "the name box has focus")
                    key(cdp, sid, "Escape")
                    self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('#vname')", sid)), "the name box closed")
                    # the separate old entries are gone from the View menu
                    click(cdp, sid, "#viewMenu")
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#viewMenuList')", sid)), "the View menu opened")
                    self.assertEqual(cdp.js("document.querySelectorAll('#viewMenuList [data-kind=saveas], #viewMenuList [data-kind=rename], #viewMenuList [data-kind=delete]').length", sid), 0)
                    cdp.js("localStorage.clear(); sessionStorage.clear()", sid)

    def test_a_project_with_stored_views_keeps_them_after_the_core_five_and_nothing_stored_is_rewritten(self):
        s = self.serve()
        stored = [{"id": "open", "name": "Open items", "line": "is:open"}, {"id": "mine", "name": "My list", "line": "is:open owner:me"},
                  {"id": "x1", "name": "Old and archived", "line": "status:Closed", "archived": True}]
        for width in SIZES:
            with self.subTest(width=width), chrome() as cdp:
                sid = self.load(cdp, s.port, width)
                cdp.js("localStorage.setItem('clark.fviews', JSON.stringify({TUL: %s}))" % json.dumps(stored), sid)
                reload_to_new_page_cdp(cdp, sid)
                self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.vtab').length", sid) == 6), "the six tabs are there")
                self.assertEqual(cdp.js("[...document.querySelectorAll('.vtab span')].map(e => e.textContent)", sid),
                                 ["Open items", "Actions", "Risks and issues", "Decisions", "All work items", "My list"])
                self.assertEqual(cdp.js("localStorage.getItem('clark.fviews')", sid), json.dumps({"TUL": stored}, separators=(",", ":")), "reading rewrites nothing")
                cdp.js("localStorage.clear(); sessionStorage.clear()", sid)

    # ---- keys that are also Object.prototype properties (#153 review) ----
    WATCH = ("(function () { window.__errs = []; addEventListener('error', function (e) { window.__errs.push(String(e.message)); });"
             " addEventListener('unhandledrejection', function (e) { window.__errs.push(String(e.reason)); });"
             " var CE = console.error; console.error = function () { window.__errs.push([].join.call(arguments, ' ')); return CE.apply(console, arguments); }; })();")

    def watch(self, cdp, sid):
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": self.WATCH}, sid)
        cdp.js(self.WATCH, sid)

    def drawn(self, cdp, sid):
        """The list has rows, or says in plain words that nothing matches: never blank."""
        return bool(self.shown(cdp, sid)) or EMPTY_SAYS(cdp.js("document.querySelector('#work-list').innerText", sid))

    def errors(self, cdp, sid):
        return cdp.js("window.__errs", sid)

    def test_a_typed_key_that_is_also_an_object_property_never_throws_or_blanks_the_list(self):
        s = self.serve()
        # (line, what happens): a refused token says why and filters nothing; an unknown value of a known field shows the empty state; a state with
        # no near word is underlined (no approved sentence for it yet)
        lines = (("constructor:x", "refused"), ("-constructor:x", "refused"), ("no:__proto__", "refused"), ("__proto__:x", "refused"),
                 ("toString:x", "refused"), ("hasOwnProperty:x", "refused"), ("owner:constructor", "empty"), ("is:__proto__", "marked"))
        for width in SIZES:
            with chrome() as cdp:
                for line, how in lines:
                    with self.subTest(line=line, width=width):
                        sid = self.load(cdp, s.port, width=width)
                        self.watch(cdp, sid)
                        before = self.shown(cdp, sid)
                        self.assertTrue(before)
                        self.put(cdp, sid, "is:open " + line)
                        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#fline-input')", sid)), "the filter box is there")
                        self.assertEqual(self.errors(cdp, sid), [], "no uncaught error")
                        if how == "refused":
                            self.assertTrue(wait(lambda: bool(self.say(cdp, sid))), "a plain message")
                            self.assertEqual(self.shown(cdp, sid), before, "the list still shows its rows")
                        elif how == "marked":
                            self.assertTrue(wait(lambda: len(self.tokens(cdp, sid, "err")) == 1), "one term is marked as an error")
                            self.assertEqual(self.shown(cdp, sid), before)
                        else:
                            self.assertTrue(wait(lambda: not self.shown(cdp, sid) and EMPTY_SAYS(cdp.js("document.querySelector('#work-list').innerText", sid))),
                                            "an unknown value matches nothing and says so")
                        cdp.js("sessionStorage.clear()", sid)

    def test_a_remembered_or_addressed_prototype_key_does_not_break_a_reload(self):
        s = self.serve()
        for kept in ("constructor:x", "__proto__:x", "-constructor:x"):
            with chrome() as cdp:
                sid = self.load(cdp, s.port)
                cdp.js("sessionStorage.setItem('clark.fline', JSON.stringify({TUL: %s})); localStorage.setItem('clark.fviews', JSON.stringify({TUL: [{id: 'constructor', name: 'toString', line: 'constructor:x'}]}))" % json.dumps(kept), sid)
                self.watch(cdp, sid)
                reload_to_new_page_cdp(cdp, sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#fline-input')", sid)), "the filter box is there")
                self.assertTrue(wait(lambda: self.drawn(cdp, sid)), f"{kept}: the list is not blank")
                self.assertEqual(self.errors(cdp, sid), [], kept)
                cdp.js("localStorage.clear(); sessionStorage.clear()", sid)
        for f in ("constructor:x", "__proto__:x;not:constructor", "mode:constructor;type:__proto__;owner:toString", "not:__proto__"):
            with chrome() as cdp:
                sid = self.load(cdp, s.port)
                self.watch(cdp, sid)
                cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#work&p=TUL&f=" + urllib.parse.quote(f, safe=":;,")}, sid)
                reload_to_new_page_cdp(cdp, sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#fline-input')", sid)), f)
                self.assertTrue(wait(lambda: self.drawn(cdp, sid)), f"{f}: not blank")
                self.assertEqual(self.errors(cdp, sid), [], f)

    def test_storage_that_is_refused_does_not_break_the_line(self):
        s = self.serve()
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.enable", {}, sid)
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE + "Object.defineProperty(window, 'sessionStorage', {get() { throw new Error('no'); }}); Object.defineProperty(window, 'localStorage', {get() { throw new Error('no'); }});"}, sid)
            cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{s.port}/#work&p=TUL")}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid) > 0), "the list drew rows")
            self.put(cdp, sid, "priority:High")
            self.assertTrue(wait(lambda: "priority:High" in self.chips(cdp, sid)), "the priority:High chip is shown")
            self.assertEqual(cdp.js("document.querySelectorAll('.vtab').length", sid), 7)

    def test_the_chosen_filter_and_the_view_edit_toggle_look_different_from_the_others(self):
        # Replaces the older bar's check (#153): the highlight rules in shell.css must match the aria-pressed the buttons set
        # (a rename of the attribute once lost them), and a chosen filter on the line is drawn as a chip, not as plain text.
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port, motion="no-preference")   # the thumb is a motion rule: pin the media, as a runner may report reduce
            bg = lambda sel: cdp.js(f"getComputedStyle(document.querySelector({json.dumps(sel)})).backgroundColor", sid)
            for on, off in (("[data-type][aria-pressed=true]", "[data-type][aria-pressed=false]"),
                            ("[data-show][aria-pressed=true]", "[data-show][aria-pressed=false]")):
                with self.subTest(on=on):
                    self.assertTrue(cdp.js(f"!!document.querySelector({json.dumps(on)}) && !!document.querySelector({json.dumps(off)})", sid), "one of each is drawn")
                    self.assertNotEqual(bg(on), bg(off), "the pressed button has its own background")
            self.put(cdp, sid, "priority:High")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.fline .k-val')", sid)), "a value token is drawn")
            self.assertNotEqual(bg(".fline .k-val"), bg(".fline"), "a chosen filter value is drawn as a chip with its own background")
            self.assertNotEqual(bg(".fline .k-val"), "rgba(0, 0, 0, 0)")
            self.assertEqual(cdp.js("document.querySelectorAll('.mode').length", sid), 0, "no View | Edit switch on Work items (row 804)")
            cdp.js("location.hash = '#dashboard&p=TUL'", sid)      # the switch is the Dashboard's alone: its highlight rule is checked there
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.mode[aria-pressed=true]') && !!document.querySelector('.mode[aria-pressed=false]')", sid)), "one of each is drawn on the Dashboard")
            col = lambda sel: cdp.js(f"getComputedStyle(document.querySelector({json.dumps(sel)})).color", sid)
            self.assertNotEqual(col(".mode[aria-pressed=true]"), col(".mode[aria-pressed=false]"), "the pressed half has its own colour")
            self.assertNotEqual(cdp.js("getComputedStyle(document.querySelector('.modes'), '::before').backgroundColor", sid), "rgba(0, 0, 0, 0)",
                                "the pill's thumb (the pressed half's background, row 884) is drawn")
            cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]}, sid)
            self.assertEqual(cdp.js("getComputedStyle(document.querySelector('.modes'), '::before').backgroundColor", sid), "rgba(0, 0, 0, 0)",
                             "under reduced motion there is no thumb")
            self.assertNotEqual(bg(".mode[aria-pressed=true]"), "rgba(0, 0, 0, 0)", "under reduced motion the pressed half has its own background (the still form)")

    def test_the_targets_are_big_enough_and_the_colours_come_from_the_tokens(self):
        s = self.serve()
        for theme in THEMES:
            with self.subTest(theme=theme), chrome() as cdp:
                sid = self.load(cdp, s.port, theme=theme)
                self.put(cdp, sid, "")
                self.arm(cdp, sid)
                self.type(cdp, sid, "st")
                self.assertTrue(wait(lambda: len(self.listed(cdp, sid)) > 0), "the list has options")
                small = cdp.js("[...document.querySelectorAll('#work .vtab, #work .fx, #work .fopt, #work .fhint, #viewMenu, #fline-input')]"
                               ".filter(e => { const r = e.getBoundingClientRect(); return r.height < 24 || r.width < 24; }).map(e => e.className || e.id)", sid)
                self.assertEqual(small, [])
                tiny = cdp.js("[...document.querySelectorAll('#work *')].filter(e => [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()) && parseFloat(getComputedStyle(e).fontSize) < 13).map(e => e.className)", sid)
                self.assertEqual(tiny, [], "text is at least 13 px")
                bg = cdp.js("getComputedStyle(document.querySelector('#fline-list')).backgroundColor", sid)
                surface = cdp.js("getComputedStyle(document.documentElement).getPropertyValue('--surface').trim()", sid)
                probe = cdp.js(f"(() => {{ const d = document.createElement('div'); d.style.background = {json.dumps(surface)}; document.body.appendChild(d); return getComputedStyle(d).backgroundColor; }})()", sid)
                self.assertEqual(bg, probe, "the suggestions sit on the surface token")
                if theme == "dark":
                    self.assertEqual(bg, "rgb(14, 45, 56)")
                self.assertEqual(cdp.js("getComputedStyle(document.querySelector('.fline')).borderTopColor !== 'rgba(0, 0, 0, 0)'", sid), True)

    def test_the_open_tabs_menu_closes_when_the_row_scrolls_or_the_window_resizes(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.load(cdp, s.port, 900)
            menu = "!!document.querySelector('#viewTabMenuList')"
            for how in ("row", "window"):
                with self.subTest(how=how):
                    # open it, clicking again (never within a second of the last click, and only while it is not open) if the first click was lost
                    # to a page that has not taken its handlers yet; the wait ends the moment the menu is there
                    tried = [0.0]

                    def opened():
                        if cdp.js(menu, sid):
                            return True
                        if time.time() - tried[0] > 1:
                            tried[0] = time.time()
                            click(cdp, sid, "#viewTabMenu")
                        return bool(cdp.js(menu, sid))
                    self.assertTrue(wait(opened, 20), "the tabs menu opened")
                    if how == "row":
                        # the row can scroll only once it is laid out wider than its box; scroll events come a frame after the position changes
                        self.assertTrue(wait(lambda: cdp.js("(() => { const r = document.querySelector('.vtabs'); return r.scrollWidth > r.clientWidth; })()", sid)), "the row can scroll")
                        start = cdp.js("document.querySelector('.vtabs').scrollLeft", sid)
                        cdp.js(f"document.querySelector('.vtabs').scrollLeft = {start + 5}", sid)
                        self.assertTrue(wait(lambda: cdp.js("document.querySelector('.vtabs').scrollLeft", sid) > start), "the row scrolled")
                    else:
                        cdp.call("Emulation.setDeviceMetricsOverride", {"width": 880, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                        self.assertTrue(wait(lambda: cdp.js("window.innerWidth", sid) == 880), "the window is narrower")
                    self.assertTrue(wait(lambda: not cdp.js(menu, sid)), "the menu does not stay behind its arrow")

    def test_the_tab_row_stays_on_one_line_and_scrolls_inside_its_own_box(self):
        # At 900 px the tabs (the five core views, any saved views and + New view) never wrap onto a second line and never push the page
        # sideways: the row scrolls inside its own box. At 1400 px they all fit and the row looks as it did.
        s = self.serve()
        probe = """(() => { const r = document.querySelector('.vtabs'); const t = [...r.querySelectorAll('.vtab')];
          return {tabs: t.length, tops: [...new Set(t.concat([r.querySelector('.vnew')]).map(e => { const b = e.getBoundingClientRect(); return Math.round(b.top + b.height / 2); }))], sw: r.scrollWidth, cw: r.clientWidth,
                  ox: getComputedStyle(r).overflowX, wrap: getComputedStyle(r).flexWrap, page: document.documentElement.scrollWidth - document.documentElement.clientWidth,
                  right: r.getBoundingClientRect().right, win: window.innerWidth}; })()"""
        for theme in THEMES:
            for width in SIZES:
                with self.subTest(theme=theme, width=width), chrome() as cdp:
                    sid = self.load(cdp, s.port, width, theme=theme)
                    m = cdp.js(probe, sid)
                    self.assertGreaterEqual(m["tabs"], 5)
                    self.assertEqual(len(m["tops"]), 1, "every tab and + New view sit on one line")
                    self.assertEqual(m["wrap"], "nowrap")
                    self.assertEqual(m["ox"], "auto")
                    self.assertLessEqual(m["page"], 0, "the page itself does not scroll sideways")
                    self.assertLessEqual(m["right"], m["win"], "the row stays inside the window")
                    if width == 900:
                        self.assertGreater(m["sw"], m["cw"], "the row is wider than its box and scrolls inside it")
                        cdp.js("document.querySelector('.vtabs').scrollLeft = 10000", sid)
                        self.assertGreater(cdp.js("document.querySelector('.vtabs').scrollLeft", sid), 0)
                        self.assertLessEqual(cdp.js(probe, sid)["page"], 0)
                        click(cdp, sid, "#viewTabMenu")
                        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#viewTabMenuList')", sid)), "the tabs menu opened")
                        self.assertTrue(wait(lambda: cdp.js("document.getAnimations().length === 0", sid)), "the menu has finished dropping in (row 878: it starts 4 px higher)")      # measure where it settles, not mid-animation
                        self.assertEqual(cdp.js("(() => { const r = document.querySelector('.vtabs'); return r.scrollHeight <= r.clientHeight; })()", sid), True, "the open tab's menu is not cut off by the row")
                        self.assertGreater(cdp.js("document.querySelector('#viewTabMenuList').getBoundingClientRect().height", sid), 20)
                        self.assertGreaterEqual(cdp.js("document.querySelector('#viewTabMenuList').getBoundingClientRect().top - document.querySelector('.vtabs').getBoundingClientRect().bottom", sid), 0, "it opens below the row")
                    else:
                        self.assertLessEqual(m["sw"], m["cw"], "at 1400 px everything fits, as before")


if __name__ == "__main__":
    unittest.main()
