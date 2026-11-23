"""Row 1252 slice 4b-1: Settings, Reports: the Pages card with the Add page row, the page list and the Configure group (Classic only, 1400 and 900).

ACCEPTANCE VALUES (written first; sources: the issue's AP1, AP5, AP6, AP7, AP11 and the approved mock-up frames 1, 3, 4, 6, 7)
  Card: heading "Pages", on the Reports page after Gantt; Classic only (Cards: no card, no row), a project open, Edit.
  Row 1, "Add page": help "A custom page for <project>, built from a template, then named, placed and marked client or internal"; button "Add page".
  Limit line (always): "Up to 5 added pages per project". Meter text: "<n> of 5 added pages", n = the added pages + 1 (the prebuilt Gantt page counts ALWAYS,
  hidden or shown), so 1 of 5 with none added and 5 of 5 with four. At 5: the button is disabled (background var(--hover)) and the amber box reads
  "You have 5 added pages. Remove one to add another." No "no pages yet" text: with none added the list holds only the Gantt row.
  List order: the prebuilt Gantt row first (name "Gantt", words "Hidden from you and from the client. Counts as one of the 5. Sections built in: Header and
  Text, Gantt, Work items.", "You: on|off", "Client: on|off", a Remove page button only while the Gantt is on in the menu), then each added page in menu order
  with its name and a Configure button (aria-expanded).
  Configure rows, in this order, no Icon row: Name, Menu position, Shown to the client, Sections, Hide from the menu, Remove page.
    Name: help "Shown in the menu and at the top of the page."; a text box, saved on Enter or leaving it; a refused name shows the server's words and the old name returns.
    Menu position: help "After Gantt, before Settings. Move one step at a time, with Undo."; a strip of the menu's tab names ending in Settings with this page marked;
      Move left and Move right (disabled at the first and the last visible page), Undo (disabled until a move; puts the move back).
    Shown to the client: help "Off: the page is in the editor only, not in the published report."; a tick, off for a new page.
    Sections: help "Built from the starter's templates. Open the page to change them with Add a template below. Sections you add by hand cannot be Gantt or Work items; only the Gantt template contains them."; button "Open the page".
    Hide from the menu: help "The page and its sections are kept; it stays here to switch back on."; a tick.
    Remove page: help "Deletes the page and its sections. Undo stays for this session."; button "Remove page"; the toast carries Undo, which brings the page back.
Run: python3 dev/run_tests.py test_added_page_rows_1252
"""
import json
import sqlite3
import time
import unittest

from _classic_page import classic
from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome

SECS = json.dumps([{"id": "s1", "type": "text", "title": "Supplier notes head", "body": "<p>Supplier notes body text</p>"}])
WIDTHS = (1400, 900)
NAMES = "[...document.querySelectorAll('#ap-configure .set-row-name')].map(e => e.textContent.trim())"
LIST = "[...document.querySelectorAll('#add-pages .ap-page .ap-name')].map(e => e.textContent.trim())"
STRIP = "[...document.querySelectorAll('#add-pages .ap-strip li')].map(e => e.textContent.trim())"
ROWS = "[...document.querySelectorAll('#add-pages .set-row')].map(e => e.querySelector('.set-row-name').textContent.trim())"
HELP = {"Name": "Shown in the menu and at the top of the page.",
        "Menu position": "After Gantt, before Settings. Move one step at a time, with Undo.",
        "Shown to the client": "Off: the page is in the editor only, not in the published report.",
        "Sections": "Built from the starter's templates. Open the page to change them with Add a template below. Sections you add by hand cannot be Gantt or Work items; only the Gantt template contains them.",
        "Hide from the menu": "The page and its sections are kept; it stays here to switch back on.",
        "Remove page": "Deletes the page and its sections. Undo stays for this session."}
CAP = "You have 5 added pages. Remove one to add another."


class Rows(Base):
    def setUp(self):
        super().setUp()
        classic(self)

    def add(self, name, **values):
        status, body = self.real_change({"project": "ABC", "kind": "added_pages", "op": "new", "values": {"name": name, "starter": "blank", "sections": SECS, **values}})
        self.assertEqual(status, 200, body)
        return self.store.read("added_pages", project="ABC")[-1]["id"]

    def pages(self):
        return [(r["name"], r["sort_order"], r["client"], r["hidden"]) for r in sorted(self.store.read("added_pages", project="ABC"), key=lambda r: (r["sort_order"], r["id"]))]

    def open(self, cdp, width):
        p = self.visit(cdp)
        size(cdp, p, width, 900)
        p.js("location.hash = '#settings&p=ABC&s=reports'")
        p.until("!!document.querySelector('#add-pages .ap-meter')", "the Pages card drew")
        return p

    def until_stored(self, ok, what):
        for _ in range(100):
            if ok():
                return
            time.sleep(0.1)
        self.fail("the store never showed: " + what)

    def configure(self, p, name):
        p.js("[...document.querySelectorAll('#add-pages .ap-page')].filter(e => e.querySelector('.ap-name').textContent.trim() === %s)[0].querySelector('.ap-cfg').click()" % json.dumps(name))
        p.until("!!document.querySelector('#ap-configure')", "Configure opened")

    def test_add_page_row_cap_line_and_meter_count_the_gantt_always(self):
        self.add("Supplier status")
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.open(cdp, w)
                self.assertEqual(p.js("document.querySelector('#add-pages-h').textContent"), "Pages")
                self.assertEqual(p.js(ROWS)[0], "Add page")
                self.assertEqual(p.js("document.querySelector('#add-pages .set-row small').textContent"), "A custom page for Example Programme, built from a template, then named, placed and marked client or internal")
                self.assertEqual(p.js("document.querySelector('#add-page').textContent"), "Add page")
                self.assertFalse(p.js("document.querySelector('#add-page').disabled"))
                self.assertEqual(p.js("document.querySelector('.ap-cap').textContent"), "Up to 5 added pages per project")
                self.assertEqual(p.js("document.querySelector('.ap-meter').textContent"), "2 of 5 added pages")      # one added, the hidden Gantt page counts
                self.assertEqual(p.js(LIST), ["Gantt", "Supplier status"])
                self.assertEqual(p.js("document.querySelector('#add-pages .ap-page.ap-gantt small').textContent"),
                                 "Hidden from you and from the client. Counts as one of the 5. Sections built in: Header and Text, Gantt, Work items.")
                self.assertEqual(p.js("!!document.querySelector('#ap-gantt-remove')"), False)      # off in the menu: nothing to remove
                self.assertEqual(p.js("document.documentElement.scrollWidth - document.documentElement.clientWidth"), 0, "no sideways scroll")
                self.assertEqual(p.js("document.querySelector('.ap-limit')"), None)

    def test_cap_of_five_counts_the_hidden_gantt_disables_add_and_says_so(self):
        for n in range(4):
            self.add(f"Page {n}")
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.open(cdp, w)
                self.assertEqual(p.js("document.querySelector('.ap-meter').textContent"), "5 of 5 added pages")
                self.assertTrue(p.js("document.querySelector('#add-page').disabled"))
                self.assertEqual(p.js("document.querySelector('.ap-limit').textContent"), CAP)
                got = p.js("""(() => { const probe = document.createElement('i'); probe.style.background = 'var(--hover)'; document.querySelector('#add-pages').appendChild(probe);
                    const want = getComputedStyle(probe).backgroundColor; probe.remove(); return [getComputedStyle(document.querySelector('#add-page')).backgroundColor, want]; })()""")
                self.assertEqual(got[0], got[1], "the disabled button is var(--hover)")
                self.assertNotEqual(got[1], "rgba(0, 0, 0, 0)")
                self.assertEqual(p.js("document.documentElement.scrollWidth - document.documentElement.clientWidth"), 0)

    def check_configure(self, w):
        self.add("Supplier status")
        with chrome() as cdp:
            p = self.open(cdp, w)
            self.assertEqual(p.js("!!document.querySelector('#ap-configure')"), False)
            self.configure(p, "Supplier status")
            self.assertEqual(p.js(NAMES), list(HELP))
            self.assertNotIn("Icon", " ".join(p.js(NAMES)))
            for row in p.js("[...document.querySelectorAll('#ap-configure .set-row')].map(e => [e.querySelector('.set-row-name').textContent.trim(), e.querySelector('small').textContent])"):
                self.assertEqual(row[1], HELP[row[0]], row[0])
            self.assertEqual(p.js("document.querySelector('#ap-name').value"), "Supplier status")
            self.assertFalse(p.js("document.querySelector('#ap-client').checked"))
            self.assertFalse(p.js("document.querySelector('#ap-hide').checked"))
            self.assertEqual(p.js(STRIP), ["Dashboard", "Work items", "Milestones", "Use cases", "Supplier status", "Settings"])
            self.assertEqual(p.js("document.querySelector('#add-pages .ap-strip [aria-current]').textContent"), "Supplier status")
            self.assertEqual(p.js("document.documentElement.scrollWidth - document.documentElement.clientWidth"), 0)

    def test_configure_rows_in_order_1400(self):
        self.check_configure(1400)

    def test_configure_rows_in_order_900(self):
        self.check_configure(900)

    def test_name_client_hide_and_open_the_page(self):
        pid = self.add("Supplier status")
        with chrome() as cdp:
            p = self.open(cdp, 1400)
            self.configure(p, "Supplier status")
            p.js("(() => { const i = document.querySelector('#ap-name'); i.focus(); i.value = 'Handover papers'; i.dispatchEvent(new Event('input', {bubbles: true})); })()")
            p.js("document.querySelector('#ap-name').blur()")
            p.until("document.querySelector('#ap-name').value === 'Handover papers' && [...document.querySelectorAll('.top .tabs .tab')].some(t => t.textContent.trim() === 'Handover papers')", "renamed")
            self.assertEqual(self.pages()[0][0], "Handover papers")
            p.js("document.querySelector('#ap-name').focus(); document.querySelector('#ap-name').value = '  '; document.querySelector('#ap-name').dispatchEvent(new Event('input', {bubbles: true}))")
            p.js("document.querySelector('#ap-name').blur()")
            p.until("document.querySelector('#ap-name').value === 'Handover papers'", "a blank name is refused and the old name returns")
            self.assertEqual(self.pages()[0][0], "Handover papers")
            p.js("document.querySelector('#ap-client').click()")
            self.until_stored(lambda: self.pages()[0][2] == 1, "client on")
            p.js("document.querySelector('#ap-hide').click()")
            self.until_stored(lambda: self.pages()[0][3] == 1, "hidden on")
            p.until("![...document.querySelectorAll('.top .tabs .tab')].some(t => t.textContent.trim() === 'Handover papers')", "the tab left the menu")
            self.assertEqual(len(json.loads(sqlite3.connect(str(self.store.path)).execute("SELECT sections FROM added_pages WHERE id = ?", (pid,)).fetchone()[0])), 1, "hiding keeps the sections")
            p.js("document.querySelector('#ap-hide').click()")
            p.until("!document.querySelector('#ap-hide').checked", "back in the menu")
            self.until_stored(lambda: self.pages()[0][3] == 0, "hidden off")
            p.js("document.querySelector('#ap-open').click()")
            p.until("location.hash.split('&')[0] === '#page:%s'" % pid, "Open the page goes to the page")

    def test_menu_position_moves_one_step_with_undo(self):
        self.add("Alpha page")
        self.add("Beta page")
        self.add("Gamma page")
        with chrome() as cdp:
            p = self.open(cdp, 1400)
            self.configure(p, "Beta page")
            self.assertEqual(p.js(STRIP)[-4:], ["Alpha page", "Beta page", "Gamma page", "Settings"])
            self.assertTrue(p.js("document.querySelector('#ap-undo').disabled"))
            p.js("document.querySelector('#ap-left').click()")
            p.until("[...document.querySelectorAll('.top .tabs .tab')].map(t => t.textContent.trim()).slice(-3).join() === 'Beta page,Alpha page,Gamma page'", "moved left")
            self.assertEqual([n for n, *_ in self.pages()], ["Beta page", "Alpha page", "Gamma page"])
            self.assertTrue(p.js("document.querySelector('#ap-left').disabled"), "first after Gantt: Move left is off")
            p.until("!document.querySelector('#ap-undo').disabled", "Undo is on once the move is done")
            p.js("document.querySelector('#ap-undo').click()")
            p.until("[...document.querySelectorAll('.top .tabs .tab')].map(t => t.textContent.trim()).slice(-3).join() === 'Alpha page,Beta page,Gamma page'", "undone")
            self.assertEqual([n for n, *_ in self.pages()], ["Alpha page", "Beta page", "Gamma page"])
            p.js("document.querySelector('#ap-right').click()")
            p.until("[...document.querySelectorAll('.top .tabs .tab')].map(t => t.textContent.trim()).slice(-3).join() === 'Alpha page,Gamma page,Beta page'", "moved right")
            self.assertTrue(p.js("document.querySelector('#ap-right').disabled"), "last before Settings: Move right is off")
            self.assertEqual(p.js("document.documentElement.scrollWidth - document.documentElement.clientWidth"), 0)

    def test_remove_page_is_undone_from_the_toast_and_keeps_its_sections(self):
        self.add("Supplier status")
        with chrome() as cdp:
            p = self.open(cdp, 900)
            self.configure(p, "Supplier status")
            p.js("document.querySelector('#ap-remove').click()")
            p.until("!document.querySelector('#ap-configure') && document.querySelectorAll('#add-pages .ap-page').length === 1", "removed")
            self.assertEqual(self.pages(), [])
            p.until("!![...document.querySelectorAll('.toasts button')].find(b => b.textContent.trim() === 'Undo')", "the toast offers Undo")
            p.js("[...document.querySelectorAll('.toasts button')].find(b => b.textContent.trim() === 'Undo').click()")
            p.until("[...document.querySelectorAll('#add-pages .ap-name')].some(e => e.textContent.trim() === 'Supplier status')", "back")
            row = self.store.read("added_pages", project="ABC")[0]
            self.assertEqual(json.loads(row["sections"])[0]["title"], "Supplier notes head")

    def test_gantt_row_follows_its_switch_and_remove_turns_it_off_with_undo(self):
        with sqlite3.connect(str(self.store.path)) as con:
            con.execute("UPDATE projects SET show_gantt_editor = 1, show_gantt_client = 1 WHERE code = 'ABC'")
        with chrome() as cdp:
            p = self.open(cdp, 1400)
            self.assertEqual(p.js("[...document.querySelectorAll('#add-pages .ap-gantt .st')].map(e => e.textContent)"), ["You: on", "Client: on"])
            self.assertEqual(p.js("document.querySelector('.ap-meter').textContent"), "1 of 5 added pages")
            p.js("document.querySelector('#ap-gantt-remove').click()")
            p.until("!document.querySelector('#ap-gantt-remove')", "Gantt off in the menu")
            self.assertEqual(self.store.read("projects", ref="ABC")["show_gantt_editor"], 0)
            self.assertEqual(p.js("document.querySelector('.ap-meter').textContent"), "1 of 5 added pages", "the Gantt page still counts")

    def test_cards_shows_no_pages_card(self):
        self.s.close()
        from _real_server import real_server
        import _testpage as testpage
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: testpage.html(), seam=self.seam)
        self.addCleanup(self.s.close)
        self.add("Supplier status")
        with chrome() as cdp:
            p = self.visit(cdp)
            size(cdp, p, 1400, 900)
            p.js("location.hash = '#settings&p=ABC&s=reports'")
            p.until("!!document.querySelector('#review-days')", "Reports drew")
            self.assertEqual(p.js("!!document.querySelector('#add-pages') || !!document.querySelector('#add-page') || !!document.querySelector('#ap-configure')"), False)


if __name__ == "__main__":
    unittest.main()
