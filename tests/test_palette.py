"""#198: the command palette (Cmd or Ctrl+K), in a real browser against the real page and fictional data.

Run: python3 dev/run_tests.py test_palette
The page is the real one served by a real server over two fictional projects. Covers: it opens from anywhere, even a box, and
Esc or the same keys close it with focus back; every kind of result (command, page, project, work item by ID and by words,
milestone) with its kind in words; Enter on each; Up and Down wrap and pass over a result that cannot run now, which says why;
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

    def key(self, key, modifiers=0, code=None, vk=0):
        for kind in ("keyDown", "keyUp"):
            self.cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": key, "code": code or key, "windowsVirtualKeyCode": vk,
                                                      "modifiers": modifiers}, self.sid)

    def palette_key(self):
        self.key("k", CTRL, "KeyK", 75)

    def open(self):
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
            p.open()
            self.assertEqual(p.js("document.activeElement.id"), "palette-q", "the search box has focus")
            p.key("Escape", 0, "Escape", 27)
            p.until("!document.querySelector('#palette')", "Esc closed it")
            self.assertEqual(p.js("document.activeElement.id"), "tb", "focus went back to the box")
            p.open()
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
            p.open()
            p.key("Escape", 0, "Escape", 27)
            p.until("!document.querySelector('#palette')", "the palette closed")
            self.assertTrue(p.js("!!document.querySelector('#help')"), "Help is still open under it")


class Results(Base):
    def test_every_kind_in_order_with_its_kind_in_words(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.open()
            kinds = [r[0] for r in p.rows()]
            self.assertEqual(kinds[:6], ["Command"] * 6)
            self.assertEqual(p.rows()[0][1], "Publish…")
            self.assertEqual([r[1] for r in p.rows() if r[0] == "Page"], ["Dashboard", "Work items", "Milestones"])
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
            p.open()
            p.find("abc-r-002")
            self.assertEqual([r[1] for r in p.rows()], ["Supplier may slip", "Check ABC-R-002 with the supplier"])

    def test_up_and_down_wrap_and_skip_what_cannot_run(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.open()
            self.assertEqual(p.active(), "Publish…")
            names = [r[1] for r in p.rows() if not r[2]]
            p.key("ArrowUp", 0, "ArrowUp", 38)
            self.assertEqual(p.active(), names[-1], "Up from the first wraps to the last")
            p.key("ArrowDown", 0, "ArrowDown", 40)
            self.assertEqual(p.active(), names[0], "Down from the last wraps to the first")
            for _ in range(len(names)):
                p.key("ArrowDown", 0, "ArrowDown", 40)
                self.assertNotEqual(p.active(), "Dark mode", "the disabled result is passed over")

    def test_a_result_that_cannot_run_says_why_and_does_nothing(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.open()
            p.find("dark")
            row = p.js("[document.querySelector('#palette .pal-row').getAttribute('aria-disabled'), document.querySelector('#palette .pal-why').textContent]")
            self.assertEqual(row[0], "true")
            self.assertIn("light or dark setting of your computer", row[1])
            p.key("Enter", 0, "Enter", 13)
            self.assertTrue(p.js("!!document.querySelector('#palette[open]')"), "Enter on it leaves the palette open")
            self.assertEqual(p.js("document.querySelector('#palette .pal-row').getAttribute('aria-selected')"), "false")

    def test_an_item_hidden_from_the_project_is_not_offered(self):
        """The page only holds what the server gave it, and the palette searches that and nothing else."""
        with chrome() as cdp:
            p = self.visit(cdp)
            p.open()
            p.find("ABC-A-099")
            self.assertEqual(p.rows(), [])


class Enter(Base):
    def run_first(self, p, text):
        p.open()
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

    def test_the_item_opens_from_settings_by_leaving_for_a_page_that_has_a_peek(self):
        with chrome() as cdp:
            p = self.visit(cdp, "#settings&p=ABC")
            self.run_first(p, "abc-a-001")
            p.until("location.hash.indexOf('#settings') !== 0 && location.hash.indexOf('item=ABC-A-001') > 0", "left Settings for the item")


class Looks(Base):
    def test_both_widths_light_and_dark(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in (1400, 900):
                for dark in (False, True):
                    p.width(w)
                    p.dark(dark)
                    p.open()
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
        for needle in ("Search commands, pages", "pal-row", "palette-q", "Go to or do", "light or dark setting of your computer"):
            self.assertNotIn(needle, view)
        self.assertIn("palette-q", page.PAGE.read_text(encoding="utf-8"))

    def test_the_words_are_plain(self):
        text = (PAGE_SRC / "edit" / "Palette.jsx").read_text(encoding="utf-8") + (PAGE_SRC / "edit" / "palette.js").read_text(encoding="utf-8")
        for s in re.findall(r'(?:placeholder|aria-label|DARK_WHY =|NEED_PROJECT =)\s*=?\s*"([^"]+)"', text) + re.findall(r">([A-Z][^<{]{12,})<", text):
            self.assertIsNone(NEVER.search(s), s)


if __name__ == "__main__":
    unittest.main()
