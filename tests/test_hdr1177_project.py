"""Item 1177: in the one slim header the project name is a button (.hdr-project) that opens the project list; choosing another project
switches to it; Enter and Space open it from the keyboard and Esc closes it. Chrome is required: these tests fail, never skip, without it.

Run: python3 dev/run_tests.py test_hdr1177_project
"""
from test_inline_67 import SIZES, size
from test_report_editor import Base
from test_server import chrome

TWO = [{"code": "ABC", "name": "Harbour Bridge Programme", "open": 3}, {"code": "XYZ", "name": "Second Programme", "open": 1}]
NAME = "document.querySelector('.top .hdr-project')"
MENU = "document.querySelector('#project-menu')"
ROWS = "[].map.call(document.querySelectorAll('#project-menu [role=menuitemradio]'), function(e){return e.textContent.replace('\\u2713','')})"      # the open project's row starts with its tick (test_project_switch strips it the same way)


class HeaderProject(Base):
    def setUp(self):
        super().setUp()
        self.s.httpd.projects = lambda archived=False: TWO

    def page(self, cdp, width):
        p = self.visit(cdp)
        size(cdp, p, width, 800)
        p.until(f"!!{NAME} && {NAME}.textContent.indexOf('Example Programme') >= 0", "item 1177: the project name is in the header (the header shows the open project's own name, Example Programme in the test page, not the list's; measured)")
        return p

    def press(self, p, key, code, vk):
        """A real Enter carries its text, and a button is pressed by Enter only when the key does (as test_filter_line_keys.press does); Space and Esc are sent as they are."""
        for kind in ("keyDown", "keyUp"):
            ev = {"type": kind, "key": key, "code": code, "windowsVirtualKeyCode": vk, "modifiers": 0}
            if key == "Enter" and kind == "keyDown":
                ev["text"] = "\r"
            p.cdp.call("Input.dispatchKeyEvent", ev, p.sid)

    def test_the_project_name_is_a_button_in_the_header_with_the_name_in_it(self):
        for w in SIZES:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp, w)
                got = p.js(f"(function(){{var b={NAME}; return [b.tagName, !!b.closest('.top'), b.textContent.indexOf('Example Programme') >= 0, "
                           "document.querySelectorAll('.top .hdr-project').length, b.getBoundingClientRect().width > 40];})()")
                self.assertEqual(got, ["BUTTON", True, True, 1, True], f"{w}: .hdr-project is one visible button in .top holding the project name")

    def test_the_banner_no_longer_repeats_the_name(self):
        for w in SIZES:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp, w)
                n = p.js("[...document.querySelectorAll('h1, h2')].filter(e => e.textContent.indexOf('Example Programme') >= 0 && e.getClientRects().length).length")
                self.assertEqual(n, 0, f"{w}: the name is shown once, in the header, not again as a heading")

    def test_a_click_opens_the_project_list_and_a_second_click_shuts_it(self):
        for w in SIZES:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp, w)
                p.js(f"{NAME}.click()")
                p.until(f"!!{MENU}", f"{w}: the click opens the project list")
                self.assertEqual(p.js(f"{NAME}.getAttribute('aria-expanded')"), "true", f"{w}: aria-expanded is true while open")
                self.assertEqual(p.js(ROWS), ["Harbour Bridge Programme3 open items", "Second Programme1 open item"], f"{w}: the list has both projects")
                below = p.js(f"{MENU}.getBoundingClientRect().top >= {NAME}.getBoundingClientRect().bottom - 2")
                self.assertTrue(below, f"{w}: the list opens under the name")
                p.js(f"{NAME}.click()")
                p.until(f"!{MENU}", f"{w}: a second click shuts the list")

    def test_choosing_another_project_switches_to_it(self):
        for w in SIZES:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp, w)
                p.js(f"{NAME}.click()")
                p.until(f"!!{MENU}", f"{w}: the list is open")
                p.js("[].filter.call(document.querySelectorAll('#project-menu [role=menuitemradio]'), function(e){return e.textContent.indexOf('Second Programme') === 0;})[0].click()")
                p.until("location.href.indexOf('XYZ') >= 0", f"{w}: the address names the chosen project")
                p.until(f"!{MENU}", f"{w}: the list is shut after the choice")

    def test_enter_and_space_open_the_list_from_the_keyboard(self):
        for key, code, vk in (("Enter", "Enter", 13), (" ", "Space", 32)):
            with self.subTest(key=code), chrome() as cdp:
                p = self.page(cdp, 1400)
                p.js(f"{NAME}.focus()")
                p.until(f"document.activeElement === {NAME}", "the name has focus")
                self.press(p, key, code, vk)
                p.until(f"!!{MENU}", f"{code} opens the project list")

    def test_esc_shuts_the_list_and_puts_focus_back_on_the_name(self):
        for w in SIZES:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp, w)
                p.js(f"{NAME}.focus()")
                self.press(p, "Enter", "Enter", 13)
                p.until(f"!!{MENU}", f"{w}: Enter opened the list")
                p.key("Escape", code="Escape", vk=27)
                p.until(f"!{MENU}", f"{w}: Esc shut the list")
                p.until(f"document.activeElement === {NAME}", f"{w}: focus is back on the name")

    def test_the_name_button_has_a_visible_focus_ring_and_a_pointer_cursor(self):
        with chrome() as cdp:
            p = self.page(cdp, 1400)
            p.js(f"{NAME}.focus()")
            p.key("Tab", code="Tab", vk=9, modifiers=8)      # shift-Tab then Tab lands on it by keyboard, so :focus-visible applies
            p.key("Tab", code="Tab", vk=9)
            p.until(f"document.activeElement === {NAME}", "the name has focus by keyboard")
            got = p.js(f"(function(){{var s=getComputedStyle({NAME}); return [s.cursor, s.outlineStyle !== 'none' || s.boxShadow !== 'none' || s.backgroundColor !== 'rgba(0, 0, 0, 0)'];}})()")
            self.assertEqual(got, ["pointer", True], "a pointer cursor and a visible focus mark")
