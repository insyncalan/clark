"""#198: the command palette (Cmd or Ctrl+K), in a real browser against the real page and fictional data.

Run: python3 dev/run_tests.py test_palette
The page is the real one served by a real server over two fictional projects. Covers: it opens from anywhere, even a box, and
Esc or the same keys close it with focus back; every kind of result (command, page, project, work item by ID and by words,
milestone) with its kind in words; Enter on each, and a mouse click on a result (the peek opens, the slash key still works); Up and Down wrap and pass over a result that cannot run now, which says why;
Help lists the key; the published page has no palette; both widths, light and dark. Chrome is required.
"""
import re
import tempfile
import unittest

from _paths import SRC
from clark import page
from test_page import navigate
from test_server import Running, chrome, wait

PAGE_SRC = SRC / "clark" / "page" / "src"
CTRL, SHIFT = 2, 8
NEVER = re.compile(r"\w*(Error|Exception)\b|Traceback|JSON|Not allowed|Bad request|[Rr]eport editor|\bClark\b|\bUC\b|!")


def project(code, name, extra=""):
    return {"project": {"code": code, "name": name, "health": "On track", "client_name": None},
            "milestones": [{"id": code + "-M-001", "name": "Pilot live"}], "workstreams": [], "use_cases": [], "links": [],
            "actions": [{"id": code + "-A-001", "description": "Agree the cut-over plan" + extra, "status": "Open", "owner": "Sam"}],
            "raid": [{"id": code + "-R-002", "type": "Risk", "description": "Supplier may slip", "status": "Open", "priority": "High"}],
            "decisions": [], "labels": {}}


DATA = {"ABC": project("ABC", "Example Programme"), "DEF": project("DEF", "Second Programme")}
LIST = [{"code": "ABC", "name": "Example Programme"}, {"code": "DEF", "name": "Second Programme"}]


class Pg:
    def __init__(self, test, cdp, sid):
        self.t, self.cdp, self.sid = test, cdp, sid

    def js(self, expr):
        return self.cdp.js(expr, self.sid)

    def until(self, expr, what, seconds=15):
        self.t.assertTrue(wait(lambda: self.js(expr), seconds), what)

    def until_new_page(self, expr, what, seconds=15):
        """until(), but a call made while the page is navigating is waited out: Chrome answers it with 'Inspected target navigated
        or closed' (seen on the hosted macOS runner), and the next poll sees the new page. Any other error still fails."""
        def ask():
            try:
                return self.js(expr)
            except RuntimeError as e:
                if "navigated or closed" in str(e):
                    return False
                raise
        self.t.assertTrue(wait(ask, seconds), what)

    def key(self, key, modifiers=0, code=None, vk=0):
        for kind in ("keyDown", "keyUp"):
            self.cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": key, "code": code or key, "windowsVirtualKeyCode": vk,
                                                      "modifiers": modifiers}, self.sid)

    def palette_key(self):
        self.key("k", CTRL, "KeyK", 75)

    def show(self):
        self.palette_key()
        self.until("!!document.querySelector('#palette[open]')", "the palette opened")

    def type(self, text):
        self.cdp.call("Input.insertText", {"text": text}, self.sid)

    def rows(self):
        return self.js("[...document.querySelectorAll('#palette .pal-row')].map(e => [e.dataset.kind, e.querySelector('.pal-label').textContent, e.getAttribute('aria-disabled') === 'true'])")

    def find(self, text):
        self.js("(function(){var q=document.querySelector('#palette-q'); q.value=''; q.focus();})()")
        self.type(text)
        self.until(f"document.querySelector('#palette-q').value === {text!r}", "typed")

    def click(self, selector):
        """A real mouse click (move, press, release) in the middle of the first element the selector finds."""
        x, y = self.js(f"(function(){{var r=document.querySelector({selector!r}).getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2];}})()")
        self.cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, self.sid)
        for kind, buttons in (("mousePressed", 1), ("mouseReleased", 0)):
            self.cdp.call("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, "button": "left", "buttons": buttons, "clickCount": 1}, self.sid)

    def active(self):
        return self.js("(document.querySelector('#palette .pal-row.on .pal-label') || {}).textContent || ''")

    def width(self, w):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)

    def dark(self, on):
        self.cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": "dark" if on else "light"}]}, self.sid)


class Base(unittest.TestCase):
    def setUp(self):
        self.s = Running(data_for=DATA.get, page_html=lambda: page.page_html(tempfile.mkdtemp()), projects=lambda: LIST)
        self.addCleanup(self.s.close)

    def visit(self, cdp, hash_="#dashboard&p=ABC"):
        p = Pg(self, cdp, navigate(cdp, self.s.port, hash_))
        p.until("document.documentElement.dataset.ready === '1' && !!document.querySelector('.tab')", "the page drew")
        p.until("document.querySelector('#main').children.length > 0 && !/Loading/.test(document.querySelector('#main').innerText)", "the project loaded")
        p.until("!!document.querySelector('#profile-btn')", "the top bar drew")
        return p


class Opening(Base):
    def test_opens_from_a_box_and_focus_goes_back(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.js("var i=document.createElement('input'); i.id='tb'; document.body.appendChild(i); i.focus()")
            p.show()
            self.assertEqual(p.js("document.activeElement.id"), "palette-q", "the search box has focus")
            p.key("Escape", 0, "Escape", 27)
            p.until("!document.querySelector('#palette')", "Esc closed it")
            self.assertEqual(p.js("document.activeElement.id"), "tb", "focus went back to the box")
            p.show()
            p.palette_key()
            p.until("!document.querySelector('#palette')", "the same keys closed it")
            self.assertEqual(p.js("document.activeElement.id"), "tb")

    def test_a_plain_k_in_a_box_is_just_a_letter(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.js("var i=document.createElement('input'); document.body.appendChild(i); i.focus()")
            p.key("k", 0, "KeyK", 75)
            self.assertFalse(p.js("!!document.querySelector('#palette')"))
            p.key("k", CTRL | SHIFT, "KeyK", 75)
            self.assertFalse(p.js("!!document.querySelector('#palette')"), "Shift as well is not ours")

    def test_over_help_esc_closes_the_palette_first(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.key("?", 0, "Slash", 191)
            p.until("!!document.querySelector('#help')", "Help opened")
            p.show()
            p.key("Escape", 0, "Escape", 27)
            p.until("!document.querySelector('#palette')", "the palette closed")
            self.assertTrue(p.js("!!document.querySelector('#help')"), "Help is still open under it")


    def test_it_stands_aside_for_a_question_box_and_a_menu(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for role in ("alertdialog", "menu"):
                p.js(f"var d=document.createElement('div'); d.id='layer'; d.setAttribute('role','{role}'); document.body.appendChild(d)")
                p.palette_key()
                self.assertFalse(p.js("!!document.querySelector('#palette')"), role + " keeps the page")
                p.js("document.getElementById('layer').remove()")
            p.show()


class Results(Base):
    def test_every_kind_in_order_with_its_kind_in_words(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.show()
            kinds = [r[0] for r in p.rows()]
            self.assertEqual(kinds[:6], ["Command"] * 6)
            self.assertEqual(p.rows()[0][1], "Publish…")
            self.assertEqual([r[1] for r in p.rows() if r[0] == "Page"], ["Dashboard", "Work items", "Milestones", "Use cases", "Client Requested Report View"])     # the Use cases page (#157) is a tab of the Edit page; the client report (#192) after it
            self.assertEqual([r[1] for r in p.rows() if r[0] == "Project"], ["Example Programme", "Second Programme"])
            p.find("a-001")
            self.assertEqual([r[:2] for r in p.rows()], [["Action", "Agree the cut-over plan"]])
            p.find("supplier")
            self.assertEqual([r[:2] for r in p.rows()], [["Risk", "Supplier may slip"]])
            p.find("pilot")
            self.assertEqual([r[:2] for r in p.rows()], [["Milestone", "Pilot live"]])
            p.find("second")
            self.assertEqual([r[:2] for r in p.rows()], [["Project", "Second Programme"]])
            p.find("export")
            self.assertEqual([r[:2] for r in p.rows()], [["Command", "Export to Excel"]])
            p.find("work items")
            self.assertEqual([r[:2] for r in p.rows()], [["Page", "Work items"]])
            p.find("zzzz")
            self.assertEqual(p.rows(), [])
            self.assertIn("Nothing matches", p.js("document.querySelector('#palette .pal-none').innerText"))

    def test_an_id_match_comes_before_a_title_match(self):
        data = project("ABC", "Example Programme")
        data["actions"].insert(0, {"id": "ABC-A-009", "description": "Check ABC-R-002 with the supplier", "status": "Open", "owner": "Sam"})
        DATA["ABC"] = data
        self.addCleanup(DATA.update, {"ABC": project("ABC", "Example Programme")})
        with chrome() as cdp:
            p = self.visit(cdp)
            p.show()
            p.find("abc-r-002")
            self.assertEqual([r[1] for r in p.rows()], ["Supplier may slip", "Check ABC-R-002 with the supplier"])

    def test_up_and_down_wrap_and_skip_what_cannot_run(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.show()
            self.assertEqual(p.active(), "Publish…")
            names = [r[1] for r in p.rows() if not r[2]]
            p.key("ArrowUp", 0, "ArrowUp", 38)
            self.assertEqual(p.active(), names[-1], "Up from the first wraps to the last")
            p.key("ArrowDown", 0, "ArrowDown", 40)
            self.assertEqual(p.active(), names[0], "Down from the last wraps to the first")
            for _ in range(len(names)):
                p.key("ArrowDown", 0, "ArrowDown", 40)
                self.assertNotEqual(p.js("document.querySelector('#palette .pal-row.on').getAttribute('aria-disabled')"), "true", "a result that cannot run is passed over")

    def test_a_result_that_cannot_run_says_why_and_does_nothing(self):
        with chrome() as cdp:
            p = Pg(self, cdp, navigate(cdp, self.s.port, "#dashboard&p=NOSUCH"))
            p.until("document.documentElement.dataset.ready === '1'", "the page drew")
            p.until("document.body.innerText.length > 20", "the page has words")
            p.show()
            p.find("publish")
            p.until("document.querySelector('#palette .pal-row') && document.querySelector('#palette .pal-row').getAttribute('aria-disabled') === 'true'", "Publish cannot run without a project")
            self.assertIn("Open a project first", p.js("document.querySelector('#palette .pal-why').textContent"))
            p.key("Enter", 0, "Enter", 13)
            self.assertTrue(p.js("!!document.querySelector('#palette[open]')"), "Enter on it leaves the palette open")
            self.assertEqual(p.js("document.querySelector('#palette .pal-row').getAttribute('aria-selected')"), "false")

    def test_the_appearance_commands_use_the_real_setting(self):
        """Light, Dark and System each change the page's own appearance (the one Settings and the profile menu set), say which is in use, and a reload keeps it."""
        theme = {"light": "none", "dark": "dark", "system": "auto"}
        with chrome() as cdp:
            p = self.visit(cdp)
            p.show()
            p.find("appearance")
            self.assertEqual([r[1] for r in p.rows()], ["Appearance: System", "Appearance: Light", "Appearance: Dark"])
            self.assertEqual(p.js("[...document.querySelectorAll('#palette .pal-row')].map(e => !!e.querySelector('.pal-more.muted:not(.num)') && /In use/.test(e.textContent))"), [True, False, False], "System is in use first")
            p.key("Escape", 0, "Escape", 27)
            for mode in ("dark", "light", "system", "dark"):
                p.show()
                p.find("appearance: " + mode)
                self.assertEqual(p.active(), "Appearance: " + mode.capitalize())
                p.key("Enter", 0, "Enter", 13)
                p.until("!document.querySelector('#palette')", "the palette closed")
                p.until(f"(document.documentElement.dataset.theme || 'none') === {theme[mode]!r}", f"{mode} applied")
                self.assertEqual(p.js("localStorage.getItem('clark.appearance')"), mode)
                self.assertTrue(p.js("document.activeElement !== null"), "focus is back in the page")
                p.show()
                p.find("appearance")
                self.assertEqual(p.js("[...document.querySelectorAll('#palette .pal-row')].filter(e => /In use/.test(e.textContent)).map(e => e.querySelector('.pal-label').textContent)"),
                                 ["Appearance: " + mode.capitalize()], "the one in use says so")
                p.key("Escape", 0, "Escape", 27)
            p.js("window.__old_document = true")
            p.js("location.reload()")
            p.until_new_page("window.__old_document === undefined && !!document.querySelector('#profile-btn') && document.documentElement.dataset.theme === 'dark'",
                             "Dark again after a reload")

    def test_an_item_hidden_from_the_project_is_not_offered(self):
        """The page only holds what the server gave it, and the palette searches that and nothing else."""
        with chrome() as cdp:
            p = self.visit(cdp)
            p.show()
            p.find("ABC-A-099")
            self.assertEqual(p.rows(), [])


class Enter(Base):
    def run_first(self, p, text):
        p.show()
        p.find(text)
        p.key("Enter", 0, "Enter", 13)
        p.until("!document.querySelector('#palette')", "the palette closed on Enter")

    def test_enter_runs_a_page_a_project_an_item_and_a_milestone(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.run_first(p, "milestones")
            p.until("location.hash.indexOf('#milestones') === 0", "the Milestones page opened")
            self.assertEqual(p.js("document.querySelector('.tab[aria-selected=true]').textContent"), "Milestones")
            self.run_first(p, "second")
            p.until("location.hash.indexOf('p=DEF') > 0", "the other project opened")
            p.until("document.querySelector('#project-name').textContent === 'Second Programme'", "its name is in the top bar")
            self.run_first(p, "def-a-001")
            p.until("location.hash.indexOf('item=DEF-A-001') > 0", "the item's peek address")
            self.run_first(p, "pilot")
            p.until("location.hash.indexOf('ms=DEF-M-001') > 0", "the milestone's peek address")

    def test_enter_on_the_commands_calls_what_the_menu_calls(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.run_first(p, "settings")
            p.until("location.hash.indexOf('#settings') === 0", "Settings opened")
            self.run_first(p, "help")
            p.until("!!document.querySelector('#help')", "Help opened")
            p.key("Escape", 0, "Escape", 27)
            p.until("!document.querySelector('#help')", "Help closed")
            self.run_first(p, "publish")
            p.until("!!document.querySelector('#publish-dialog[open]')", "the Publish dialog opened (the menu's own)")
            self.assertEqual(p.js("document.querySelectorAll('dialog[open]').length"), 1, "the palette is gone, not stacked under it")
            p.js("document.querySelector('[data-cancel]').click()")
            p.until("!document.querySelector('#publish-dialog')", "closed")
            with_download = p.js("window.__asked = []; var f = window.fetch; window.fetch = function(u){ window.__asked.push(String(u)); return f.apply(this, arguments); }; 1")
            self.assertEqual(with_download, 1)
            self.run_first(p, "export")
            p.until("window.__asked.some(u => u.indexOf('/api/export') >= 0 || u.indexOf('xport') >= 0)", "Export asked the menu's own route")

    def test_the_ask_command_opens_the_ask_panel(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.run_first(p, "ask about")
            p.until("!!document.querySelector('#ask-panel')", "the ask panel opened (the one the slash key opens)")
            self.assertFalse(p.js("!!document.querySelector('#palette[open]')"), "the palette closed first")

    def test_the_item_opens_from_settings_by_leaving_for_a_page_that_has_a_peek(self):
        with chrome() as cdp:
            p = self.visit(cdp, "#settings&p=ABC")
            self.run_first(p, "abc-a-001")
            p.until("location.hash.indexOf('#settings') !== 0 && location.hash.indexOf('item=ABC-A-001') > 0", "left Settings for the item")


class Click(Base):
    def test_a_click_on_a_result_opens_the_peek_and_the_slash_key_still_works_after(self):
        """The mouse runs a result as Enter does: the palette closes for good (an open one would hold the slash key), the peek opens
        with focus in it and keeps the slash for its own words box; once the peek is shut the slash opens the ask panel."""
        with chrome() as cdp:
            p = self.visit(cdp)
            p.js("document.activeElement && document.activeElement.blur()")
            p.show()
            p.find("abc-a-001")
            p.until("document.querySelectorAll('#palette .pal-row').length === 1", "one result")
            p.click("#palette .pal-row")
            p.until("!document.querySelector('#palette')", "the palette closed on the click")
            p.until("!!document.querySelector('#peek[data-peek=\"ABC-A-001\"]')", "the peek opened on the item")
            self.assertTrue(p.js("location.hash.indexOf('item=ABC-A-001') > 0"), "the item's peek address")
            self.assertEqual(p.js("document.querySelectorAll('dialog[open]').length"), 0, "no dialog is left open")
            p.until("document.activeElement.hasAttribute('data-pk-close')", "focus went into the peek")
            p.key("/", 0, "Slash", 191)
            self.assertFalse(p.js("!!document.querySelector('#ask-panel')"), "the peek keeps the slash: one of them does not open the ask panel")
            p.key("Escape", 0, "Escape", 27)
            p.until("!document.querySelector('#peek')", "Esc closed the peek")
            p.js("document.activeElement && document.activeElement.blur()")
            p.key("/", 0, "Slash", 191)
            p.until("!!document.querySelector('#ask-panel')", "the slash opens the ask panel once the peek is shut")


class Looks(Base):
    def test_both_widths_light_and_dark(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in (1400, 900):
                for dark in (False, True):
                    p.width(w)
                    p.dark(dark)
                    p.show()
                    p.find("e")
                    box = p.js("(function(){var r=document.querySelector('#palette').getBoundingClientRect(), c=document.documentElement.clientWidth;"
                               "return [r.left >= 0, r.right <= c, r.top >= 0, r.bottom <= document.documentElement.clientHeight, "
                               "document.documentElement.scrollWidth <= c, document.querySelector('#palette').scrollWidth <= document.querySelector('#palette').clientWidth]})()")
                    self.assertTrue(all(box), f"the palette fits at {w} px (dark={dark}): {box}")
                    colours = p.js("(function(){var d=getComputedStyle(document.querySelector('#palette')), r=getComputedStyle(document.querySelector('#palette .pal-label'));"
                                   "return [d.backgroundColor, r.color]})()")
                    self.assertNotEqual(colours[0], colours[1], "the text is not the colour of the box")
                    p.key("Escape", 0, "Escape", 27)
                    p.until("!document.querySelector('#palette')", "closed")

    def test_help_lists_the_key(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.key("?", 0, "Slash", 191)
            p.until("!!document.querySelector('#help')", "Help opened")
            p.js("document.querySelector('#hpTab-reference').click()")
            p.until("!!document.querySelector('#hp-ref-keys .hp-keys')", "the keys table drew")
            text = p.js("document.querySelector('#hp-ref-keys .hp-keys').innerText")
            self.assertRegex(text, r"(⌘|Ctrl)\s*\+?\s*K")
            self.assertIn("The palette", text)


class Published(unittest.TestCase):
    def test_the_published_page_has_no_palette(self):
        view = (page.PAGE.parent / "page-view.html").read_text(encoding="utf-8")
        for needle in ("Search commands, pages", "pal-row", "palette-q", "Go to or do", "Appearance: Dark"):
            self.assertNotIn(needle, view)
        self.assertIn("palette-q", page.PAGE.read_text(encoding="utf-8"))

    def test_the_words_are_plain(self):
        text = (PAGE_SRC / "edit" / "Palette.jsx").read_text(encoding="utf-8") + (PAGE_SRC / "edit" / "palette.js").read_text(encoding="utf-8")
        for s in re.findall(r'(?:placeholder|aria-label|NEED_PROJECT =)\s*=?\s*"([^"]+)"', text) + re.findall(r">([A-Z][^<{]{12,})<", text):
            self.assertIsNone(NEVER.search(s), s)


if __name__ == "__main__":
    unittest.main()
