"""Issue 713: the published file's badge and menu (Report menu) at the top right of the bar, in a real window.

Run: python3 dev/run_tests.py test_client_menu
The rows, the reader's profile (kept in their own browser only), Dark mode, Past reports, Export to Excel and Export to PDF, the
keys, and the bar at 1400, 901 and 900 px in light and dark. Chrome is required: these tests fail, never skip, without it.
"""
import base64
import json
import re
import tempfile
import unittest
from pathlib import Path

from clark import page, publish
from test_publish import EMPTY_BRANDING, block, made, opened, tearDownModule  # noqa: F401
from test_report_editor import Base
from _new_page import reload_to_new_page, reload_to_new_page_cdp
from test_server import chrome, wait

NAME = "ZQ-NAME Probe"            # a distinctive name: it must be found in the browser's storage and nowhere in the file
SHEET = base64.b64encode(b"PK-stub-workbook-bytes").decode()
BADGE = "document.querySelector('#client-menu-btn')"
MENU = "document.querySelector('#client-menu')"
ROWS = "[...document.querySelectorAll('#client-menu > [data-row], #client-menu > .cm-group')].map(e => e.dataset.row)"
SPACE = """(function(){var o=document.documentElement; return [o.scrollWidth <= o.clientWidth + 1, document.body.scrollWidth <= o.clientWidth + 1];})()"""


def make(extra=None):
    """A finished published file's text, with `extra` added to the data block's data (what publish will write for the menu)."""
    _, pub, _ = made()
    pub["data"].update(extra or {})
    return publish.render(pub, page.page_html(EMPTY_BRANDING, view=True), "2026-10-28", pub["data"]["project"]["name"])


class Menu(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def show(self, cdp, extra=None, width=1400, text=None, name="report.html"):
        path = Path(self.tmp.name) / name
        path.write_text(text if text is not None else make(extra), encoding="utf-8")
        sid = opened(cdp, path.as_uri(), width)
        self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"), "the file drew")
        self.assertTrue(wait(lambda: cdp.js(f"!!{BADGE}", sid)), "the badge is there")
        self.sid = sid
        return lambda e: cdp.js(e, sid)

    def key(self, cdp, key, vk):
        for kind in ("keyDown", "keyUp"):
            cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": key, "code": key, "windowsVirtualKeyCode": vk, "modifiers": 0}, self.sid)

    def menu(self, cdp, js):
        js(f"{BADGE}.focus(); {BADGE}.click()")
        self.assertTrue(wait(lambda: js(f"!!{MENU}")), "the menu opened")

    def pick(self, cdp, js, sel):
        js(f"{MENU}.querySelector({json.dumps(sel)}).click()")

    # --- the badge and the rows -------------------------------------------------------------------------------------------

    def test_the_badge_is_named_and_the_rows_are_exactly_these_in_order(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.assertEqual(js(f"[{BADGE}.getAttribute('aria-label'), {BADGE}.title, {BADGE}.getAttribute('aria-haspopup'), {BADGE}.getAttribute('aria-expanded'), "
                                f"!!{BADGE}.querySelector('svg'), {BADGE}.tagName]"), ["Report menu", "Report menu", "menu", "false", True, "BUTTON"])
            self.menu(cdp, js)
            self.assertEqual(js(f"{BADGE}.getAttribute('aria-expanded')"), "true")
            self.assertEqual(js(ROWS), ["profile", "pdf", "past", "dark"], "no workbook in the file: Export to Excel is not drawn")
            self.assertEqual(js(f"[...{MENU}.querySelectorAll('[data-row=profile], [data-row=pdf], .cm-group .lab')].map(e => e.textContent)"),
                             ["Profile", "Export to PDF", "Past reports", "Dark mode"])
            self.assertEqual(js(f"[...{MENU}.querySelectorAll('[data-look]')].map(e => e.textContent.replace('✓', '') + ':' + e.getAttribute('aria-checked'))"),
                             ["Light:false", "Dark:false", "System:true"])
            self.assertEqual(js("window.violations"), [])

    def test_the_source_draws_it_only_from_a_file(self):
        src = (Path(__file__).resolve().parent.parent / "src/clark/page/src/components/TopBar.jsx").read_text(encoding="utf-8")
        self.assertRegex(src, r"fromFile\.value \? <ClientMenu />")
        self.assertNotIn("ClientMenu", (Path(__file__).resolve().parent.parent / "src/clark/page/src/main.jsx").read_text(encoding="utf-8"))

    # --- the profile ------------------------------------------------------------------------------------------------------

    def test_profile_saves_a_name_the_badge_shows_initials_and_remove_clears_it(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.menu(cdp, js)
            self.pick(cdp, js, "[data-row=profile]")
            self.assertTrue(wait(lambda: js("document.activeElement.id") == "client-profile-name"), "the name field has the focus")
            self.assertEqual(js("(function(){var b=document.querySelector('#client-profile');return [b.getAttribute('role'), b.getAttribute('aria-modal'), "
                                "document.getElementById(b.getAttribute('aria-labelledby')).textContent, b.querySelector('label').textContent, "
                                "[...b.querySelectorAll('button')].map(x => x.textContent), b.querySelector('.cm-note').textContent, "
                                "document.activeElement.id];})()"),
                             ["dialog", "true", "Your profile", "Your name", ["Cancel", "Save"], "Kept only in this browser. It is never put in the report or sent anywhere.", "client-profile-name"])
            js("document.querySelector('#client-profile-name').value = " + json.dumps(NAME) + "; document.querySelector('#client-profile-name').dispatchEvent(new Event('input', {bubbles: true}))")
            js("document.querySelector('#client-profile [data-act=save]').click()")
            self.assertTrue(wait(lambda: not js("!!document.querySelector('#client-profile')")))
            self.assertEqual(js(f"{BADGE}.textContent"), "ZP")
            self.assertTrue(wait(lambda: js("document.activeElement.id") == "client-menu-btn"), "focus is back on the badge")
            self.menu(cdp, js)
            self.pick(cdp, js, "[data-row=profile]")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#client-profile')")))
            self.assertEqual(js("document.querySelector('#client-profile-name').value"), NAME)
            self.assertEqual(js("[...document.querySelectorAll('#client-profile button')].map(x => x.textContent)"), ["Remove my profile", "Cancel", "Save"])
            js("document.querySelector('#client-profile [data-act=remove]').click()")
            self.assertTrue(wait(lambda: not js("!!document.querySelector('#client-profile')")))
            self.assertEqual(js(f"[{BADGE}.textContent, !!{BADGE}.querySelector('svg')]"), ["", True])
            self.assertIsNone(js(f"localStorage.getItem('clark.reader.name')"))
            self.menu(cdp, js)
            self.pick(cdp, js, "[data-row=profile]")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#client-profile')")))
            self.assertEqual(js("[...document.querySelectorAll('#client-profile button')].map(x => x.textContent)"), ["Cancel", "Save"], "no profile: no Remove")

    def test_escape_and_cancel_close_the_box_and_change_nothing(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.menu(cdp, js)
            self.pick(cdp, js, "[data-row=profile]")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#client-profile')")))
            js("document.querySelector('#client-profile-name').value = 'Typed'; document.querySelector('#client-profile-name').dispatchEvent(new Event('input', {bubbles: true}))")
            self.key(cdp, "Escape", 27)
            self.assertTrue(wait(lambda: not js("!!document.querySelector('#client-profile')")))
            self.assertTrue(wait(lambda: js("document.activeElement.id") == "client-menu-btn"), "focus is back on the badge")
            self.assertEqual(js(f"[{BADGE}.textContent, !!{BADGE}.querySelector('svg')]"), ["", True])
            self.menu(cdp, js)
            self.pick(cdp, js, "[data-row=profile]")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#client-profile')")))
            js("document.querySelector('#client-profile [data-act=cancel]').click()")
            self.assertTrue(wait(lambda: not js("!!document.querySelector('#client-profile')")))
            self.assertIsNone(js("localStorage.getItem('clark.reader.name')"))

    def test_the_name_and_the_dark_choice_live_only_in_this_browser(self):
        with chrome() as cdp:
            js = self.show(cdp, {"past_reports": [{"week_ending": "2026-10-21", "file": "PUB-report-2026-10-21.html"}]})
            self.menu(cdp, js)
            self.pick(cdp, js, "[data-row=profile]")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#client-profile')")))
            js("document.querySelector('#client-profile-name').value = " + json.dumps(NAME) + "; document.querySelector('#client-profile-name').dispatchEvent(new Event('input', {bubbles: true}))")
            js("document.querySelector('#client-profile [data-act=save]').click()")
            self.assertTrue(wait(lambda: not js("!!document.querySelector('#client-profile')")))
            self.menu(cdp, js)
            self.pick(cdp, js, "[data-look=dark]")
            self.menu(cdp, js)       # the menu open: its links are in the page
            self.assertEqual(js("localStorage.getItem('clark.reader.name')"), NAME)
            self.assertEqual(js("localStorage.getItem('clark.reader.look')"), "dark")
            everywhere = js("[document.documentElement.outerHTML, document.getElementById('clark-data').textContent, location.href, location.hash, location.search, "
                            "[...document.querySelectorAll('[href]')].map(a => a.getAttribute('href') + ' ' + a.href).join(' '), document.title].join('\\n')")
            self.assertNotIn("ZQ-NAME", everywhere)
            self.assertNotIn("ZQ-NAME", self.text_of_file())
            self.assertNotRegex(js("document.documentElement.outerHTML"), r'data-look="dark"[^>]*ZQ-NAME')

    def text_of_file(self):
        return (Path(self.tmp.name) / "report.html").read_text(encoding="utf-8")

    def test_the_name_is_remembered_after_a_reload(self):
        with chrome() as cdp:
            js = self.show(cdp)
            js(f"localStorage.setItem('clark.reader.name', {json.dumps(NAME)})")
            reload_to_new_page_cdp(cdp, self.sid, ready=f"!!{BADGE} && {BADGE}.textContent === 'ZP'", what="the reloaded page shows the initials")
            self.assertEqual(js(f"{BADGE}.textContent"), "ZP")

    # --- dark mode --------------------------------------------------------------------------------------------------------

    def test_dark_mode_switches_the_theme_and_survives_a_reload(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.assertEqual(js("document.documentElement.dataset.theme || 'none'"), "auto", "System is the default and follows the computer")
            self.menu(cdp, js)
            self.pick(cdp, js, "[data-look=dark]")
            self.assertEqual(js("document.documentElement.dataset.theme"), "dark")
            reload_to_new_page_cdp(cdp, self.sid, ready=f"document.documentElement.dataset.ready === '1' && !!{BADGE}", what="the reloaded page drew its badge")
            self.assertEqual(js("document.documentElement.dataset.theme"), "dark")
            self.menu(cdp, js)
            self.assertEqual(js(f"{MENU}.querySelector('[data-look=dark]').getAttribute('aria-checked')"), "true")
            self.pick(cdp, js, "[data-look=light]")
            self.assertEqual(js("document.documentElement.dataset.theme || 'none'"), "none")
            self.menu(cdp, js)
            self.pick(cdp, js, "[data-look=system]")
            self.assertEqual(js("document.documentElement.dataset.theme"), "auto")

    def test_a_dark_page_prints_light_and_the_bar_with_the_menu_does_not_print(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.menu(cdp, js)
            self.pick(cdp, js, "[data-look=dark]")
            cdp.call("Emulation.setEmulatedMedia", {"media": "print"}, self.sid)
            js("window.dispatchEvent(new Event('beforeprint'))")
            self.assertTrue(wait(lambda: js("document.documentElement.classList.contains('print-all')")))
            self.assertEqual(js("[document.documentElement.dataset.theme || 'none', getComputedStyle(document.querySelector('.top')).display]"), ["none", "none"])
            self.assertEqual(js("document.querySelector('.cm-wrap').getClientRects().length + ' ' + getComputedStyle(document.body).backgroundColor"), "0 rgb(255, 255, 255)")
            cdp.call("Emulation.setEmulatedMedia", {"media": ""}, self.sid)
            js("window.dispatchEvent(new Event('afterprint'))")
            self.assertEqual(js("document.documentElement.dataset.theme"), "dark", "back to the reader's choice afterwards")

    def test_export_to_pdf_calls_the_browsers_print(self):
        with chrome() as cdp:
            js = self.show(cdp)
            js("window.__printed = 0; window.print = function(){ window.__printed++; }")
            self.menu(cdp, js)
            self.pick(cdp, js, "[data-row=pdf]")
            self.assertTrue(wait(lambda: js("window.__printed") == 1))

    # --- past reports -----------------------------------------------------------------------------------------------------

    def test_past_reports_are_links_in_this_folder_with_their_dates(self):
        past = [{"week_ending": "2026-10-14", "file": "PUB-report-2026-10-14.html"}, {"week_ending": "2026-10-21", "file": "PUB-report-2026-10-21.html"},
                {"week_ending": "2026-10-07", "file": "../elsewhere/x.html"}, {"week_ending": "bad", "file": "y.html"}, {"week_ending": "2026-09-30", "file": "https://x.test/a.html"}]
        with chrome() as cdp:
            js = self.show(cdp, {"past_reports": past})
            self.menu(cdp, js)
            self.assertEqual(js(f"[...{MENU}.querySelectorAll('a')].map(a => [a.textContent, a.title, a.getAttribute('href'), a.getAttribute('role')])"),
                             [["21-10-2026", "Report of 21-10-2026", "PUB-report-2026-10-21.html", "menuitem"],
                              ["14-10-2026", "Report of 14-10-2026", "PUB-report-2026-10-14.html", "menuitem"]], "newest first; a folder, an address or a bad date is left out")
            self.assertEqual(js(f"{MENU}.querySelector('[data-row=past]').lastElementChild.textContent"), "Opens the earlier report if it is in the same folder as this one.")
            self.assertNotIn("No earlier reports.", js(f"{MENU}.innerText"))

    def test_no_past_reports_says_so(self):
        with chrome() as cdp:
            js = self.show(cdp)
            self.menu(cdp, js)
            self.assertEqual(js(f"{MENU}.querySelector('[data-row=past]').lastElementChild.textContent"), "No earlier reports.")
            self.assertEqual(js(f"{MENU}.querySelectorAll('[data-row=past] a').length"), 0)

    # --- export to Excel --------------------------------------------------------------------------------------------------

    def test_export_to_excel_is_drawn_only_with_a_workbook_and_downloads_it_from_a_blob(self):
        with chrome() as cdp:
            js = self.show(cdp, {"client_workbook": {"name": "Report-2026-10-28.xlsx", "base64": SHEET}})
            js("window.__got = []; var make = URL.createObjectURL; URL.createObjectURL = function(b){ window.__got.push([b.size, b.type]); return make.call(URL, b); };"
               "HTMLAnchorElement.prototype.click = function(){ window.__got.push([this.download, this.href.slice(0, 5)]); };")
            self.menu(cdp, js)
            self.assertEqual(js(ROWS), ["profile", "excel", "pdf", "past", "dark"])
            self.assertEqual(js(f"{MENU}.querySelector('[data-row=excel]').textContent"), "Export to Excel")
            self.pick(cdp, js, "[data-row=excel]")
            self.assertEqual(js("window.__got"), [[22, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"], ["Report-2026-10-28.xlsx", "blob:"]])
            self.assertNotIn("data:", js("[...document.querySelectorAll('a[download]')].map(a => a.href).join()"))

    def test_a_too_large_report_shows_the_row_disabled_with_the_line(self):
        with chrome() as cdp:
            js = self.show(cdp, {"client_workbook_too_large": True})
            self.menu(cdp, js)
            self.assertEqual(js(ROWS), ["profile", "excel", "pdf", "past", "dark"])
            self.assertEqual(js(f"(function(){{var r={MENU}.querySelector('[data-row=excel]'); return [r.getAttribute('aria-disabled'), r.textContent, r.nextElementSibling.textContent];}})()"),
                             ["true", "Export to Excel", "This report is too large to include a spreadsheet."])
            js("window.__got = 0; URL.createObjectURL = function(){ window.__got++; return ''; }")
            self.pick(cdp, js, "[data-row=excel]")
            self.assertEqual(js("window.__got"), 0)
    def test_the_disabled_excel_row_can_be_reached_by_the_keys_and_does_nothing(self):
        # The row is aria-disabled but stays in the arrow-key order, so a keyboard user reaches it and hears why (its note is the description).
        with chrome() as cdp:
            js = self.show(cdp, {"client_workbook_too_large": True})
            self.menu(cdp, js)
            js("window.__got = 0; URL.createObjectURL = function(){ window.__got++; return ''; }")
            js(f"{MENU}.querySelector('[data-row=profile]').focus()")
            self.key(cdp, "ArrowDown", 40)
            self.assertTrue(wait(lambda: js("document.activeElement.getAttribute('data-row')") == "excel"), "the arrow key reaches the disabled row")
            self.assertEqual(js("document.activeElement.getAttribute('aria-describedby') === document.querySelector('.cm-note').id"), True)
            self.key(cdp, "Enter", 13)
            self.key(cdp, "ArrowDown", 40)
            self.assertTrue(wait(lambda: js("document.activeElement.getAttribute('data-row')") == "pdf"), "and the next arrow goes on to the next row")
            self.assertEqual(js("window.__got"), 0, "Enter on it did nothing")

    def test_initials_skip_marks_that_are_not_letters_and_never_exceed_two(self):
        for name, want in (("(Bob) Smith", "BS"), ("(Bob)", "B"), ("\u00df \u00df", "SS"), ("ada king lovelace", "AL"), ("42 !!", "")):
            with self.subTest(name=name), chrome() as cdp:
                js = self.show(cdp)
                js("localStorage.setItem('clark.reader.name', " + json.dumps(name) + ")")
                reload_to_new_page(js, ready=f"!!{BADGE} && document.documentElement.dataset.ready === '1'", what="the reloaded page drew its badge")
                self.assertEqual(js(f"{BADGE}.textContent"), want, name)

    def test_a_bad_workbook_is_not_offered(self):
        with chrome() as cdp:
            js = self.show(cdp, {"client_workbook": {"name": "x.xlsx", "base64": "not base64 !!"}, "past_reports": "nope"})
            self.menu(cdp, js)
            self.assertEqual(js(ROWS), ["profile", "pdf", "past", "dark"])

    # --- keys -------------------------------------------------------------------------------------------------------------

    def test_keys_arrows_move_escape_closes_and_focus_returns_to_the_badge(self):
        with chrome() as cdp:
            js = self.show(cdp)
            js(f"{BADGE}.focus()")
            self.key(cdp, "ArrowDown", 40)
            self.assertTrue(wait(lambda: js(f"!!{MENU}")), "Down opens it")
            self.assertEqual(js("document.activeElement.dataset.row"), "profile", "the first row has the focus")
            self.key(cdp, "ArrowDown", 40)
            self.assertEqual(js("document.activeElement.dataset.row"), "pdf")
            self.key(cdp, "End", 35)
            self.assertEqual(js("document.activeElement.dataset.look"), "system")
            self.key(cdp, "Home", 36)
            self.assertEqual(js("document.activeElement.dataset.row"), "profile")
            self.key(cdp, "Escape", 27)
            self.assertTrue(wait(lambda: not js(f"!!{MENU}")))
            self.assertTrue(wait(lambda: js("document.activeElement.id") == "client-menu-btn"), "focus is back on the badge")
            self.assertEqual(js(f"{BADGE}.getAttribute('aria-expanded')"), "false")

    def click_badge(self, cdp, js):
        """A real mouse click on the badge (a scripted click() is not a pointer press, so it cannot show the pointer case)."""
        r = js(f"(function(){{var b={BADGE}.getBoundingClientRect(); return [b.x + b.width / 2, b.y + b.height / 2];}})()")
        common = {"x": r[0], "y": r[1], "button": "left"}
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": r[0], "y": r[1]}, self.sid)
        cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "buttons": 1, "clickCount": 1, **common}, self.sid)
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "buttons": 0, "clickCount": 1, **common}, self.sid)

    def test_row_800_opened_by_the_mouse_the_first_row_has_no_ring_and_by_the_keys_it_has_one(self):
        ring = "(function(){var e=document.activeElement, s=getComputedStyle(e); return [e.dataset.row, s.outlineStyle, parseFloat(s.outlineWidth)];})()"
        with chrome() as cdp:
            for width in (1400, 900):
                for theme in ("light", "dark"):
                    js = self.show(cdp, width=width)
                    if theme == "dark":
                        js("document.documentElement.dataset.theme = 'dark'")
                    self.click_badge(cdp, js)
                    self.assertTrue(wait(lambda: js(f"!!{MENU}")), "the mouse opened it")
                    got = js(ring)
                    self.assertEqual(got[0], "profile", "the first row still has the focus")
                    self.assertTrue(got[1] == "none" or got[2] == 0, f"no ring after a mouse open at {width} px, {theme}: {got}")
                    self.key(cdp, "Escape", 27)
                    self.assertTrue(wait(lambda: not js(f"!!{MENU}")))
                    js(f"{BADGE}.focus()")
                    self.key(cdp, "ArrowDown", 40)
                    self.assertTrue(wait(lambda: js(f"!!{MENU}")), "Down opens it")
                    got = js(ring)
                    self.assertEqual(got[1:], ["solid", 2], f"the ring shows after a keyboard open at {width} px, {theme}")

    # --- the bar ----------------------------------------------------------------------------------------------------------

    def test_no_overlap_and_no_sideways_scroll_at_these_widths_light_and_dark(self):
        extra = {"past_reports": [{"week_ending": "2026-10-21", "file": "PUB-report-2026-10-21.html"}], "client_workbook": {"name": "a.xlsx", "base64": SHEET}}
        with chrome() as cdp:
            js = self.show(cdp, extra)
            for width in (1400, 901, 900, 800):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                for theme in ("light", "dark"):
                    js(f"document.documentElement.dataset.theme = {json.dumps(theme if theme == 'dark' else '')} || null; if (!{json.dumps(theme == 'dark')}) delete document.documentElement.dataset.theme;")
                    here = f"at {width} px, {theme}"
                    self.assertEqual(js(SPACE), [True, True], "no sideways scroll " + here)
                    bad = js("(function(){var b=document.querySelector('#client-menu-btn').getBoundingClientRect(), out=[];"
                             "if (b.right > document.documentElement.clientWidth || b.left < 0) out.push('badge off screen');"
                             "[...document.querySelectorAll('.top > *')].forEach(function(e){ if (e.classList.contains('cm-wrap')) return; var r=e.getBoundingClientRect();"
                             "if (r.width && r.left < b.right && r.right > b.left && r.top < b.bottom && r.bottom > b.top) out.push(e.className); });return out;})()")
                    self.assertEqual(bad, [], "the badge overlaps nothing " + here)
                    js(f"if (!{MENU}) {BADGE}.click()")
                    self.assertTrue(wait(lambda: js(f"!!{MENU}")))
                    inside = js(f"(function(){{var r={MENU}.getBoundingClientRect(), w=document.documentElement.clientWidth; return r.left >= 0 && r.right <= w && r.top >= 0;}})()")
                    self.assertTrue(inside, "the open menu is on screen " + here)
                    self.assertEqual(js(SPACE), [True, True], "no sideways scroll with the menu open " + here)
                    self.key(cdp, "Escape", 27)
                    self.assertTrue(wait(lambda: not js(f"!!{MENU}")))


class Editor(Base):
    def test_the_editor_has_no_client_badge_and_keeps_its_own_theme(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertEqual(p.js("[document.querySelectorAll('#client-menu-btn, .cm-wrap').length, !!document.querySelector('#profile-btn')]"), [0, True])
            p.js("localStorage.setItem('clark.reader.look', 'dark')")
            p.reload()
            self.assertEqual(p.js("[document.querySelectorAll('.cm-wrap').length, document.documentElement.dataset.theme || 'none']"), [0, "auto"], "the editor's own appearance, not the reader's")


class Words(unittest.TestCase):
    def test_the_css_for_the_menu_has_tokens_only(self):
        css = (Path(__file__).resolve().parent.parent / "src/clark/page/shell.css").read_text(encoding="utf-8")
        mine = "\n".join(l for l in css.splitlines() if re.search(r"\.cm(-|-wrap)|\.ddmenu(\.cm-menu|\.cm| \.cm| a\.cm)|\.asat \+ \.cm-wrap", l))
        self.assertGreater(len(mine), 500)
        self.assertNotIn("rgba(", mine)
        self.assertNotRegex(mine, r"font-size:\s*\d")
        self.assertNotRegex(mine, r"#[0-9a-fA-F]{3,}")

    def test_row_802_the_top_bar_rules_use_color_mix_tokens_and_no_rgba(self):
        css = (Path(__file__).resolve().parent.parent / "src/clark/page/shell.css").read_text(encoding="utf-8")
        self.assertNotIn("rgba(", css, "colours in shell.css come from the tokens")
        for sel in (".top .divider", ".projbtn:hover", ".tab", ".modes", ".hp-top", ".toast-btn:hover"):
            line = next(l for l in css.splitlines() if l.startswith(sel + " "))
            self.assertIn("color-mix(in srgb, var(--white)", line, sel)

    def test_row_800_the_menu_source_marks_a_mouse_open_and_the_css_drops_the_ring_for_it(self):
        root = Path(__file__).resolve().parent.parent / "src/clark/page"
        js = (root / "src/components/Menu.jsx").read_text(encoding="utf-8")
        css = (root / "shell.css").read_text(encoding="utf-8")
        self.assertRegex(js, r":focus-visible[\s\S]{0,80}dataset\.pointer")
        self.assertRegex(css, r"\[data-pointer\][^{]*\.cm-row:focus-visible[^{]*\{[^}]*outline:\s*none")


if __name__ == "__main__":
    unittest.main()
