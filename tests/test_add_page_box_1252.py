"""Row 1252 slice 4b-2: the Add page box that the Add page button asks for (Classic only, 1400 and 900).

ACCEPTANCE VALUES (written first; sources: the issue's AP2, AP3, AP4 and the approved mock-up frames 2 and 5; words only from the issue's approved list)
  Opens: the Add page button (Pages card) fires the window event clark:add-page; the box is a modal dialog titled "Add page"; Esc, Cancel or a click on the
    backdrop close it and give the focus back to the button.
  Step 1 heading "Choose a starter": five starters in order Blank with prompts, Status, Documents, Gantt, People and next steps, each a radio-style choice
    with its template names as chips (Blank: Text, Text with image (the template's name, ruled 24-11); Status: Report headline, Numbers, Item cards, three, Coming dates;
    Documents: Text, Files and links; Gantt: Header and Text, Gantt, Work items; People and next steps: Who to ask, Next steps; the template names on main since row 1262, no new words). Only the Gantt starter
    shows a description (the approved line); the others show none (no approved line yet). The first starter is chosen when the box opens.
  Step 2 heading "Name it": a one-line text box, at most 40 letters, holding the chosen starter's name until typed over.
  Preview (right column at 1400, below at 900): a heading with the chosen starter's name, then one block per part: the template's name and, where the
    part has an approved prompt, that prompt. A part that fills itself from the project shows its name only.
  Layout: 2 columns (list left, preview right) at 1400, 1 column at 900; box at most 980 wide; no sideways scroll.
  Buttons: Cancel and Add page. Add page is off while the name is blank.
  Add: a starter other than Gantt stores one added_pages row (that starter, the typed name, the starter's sections, client 0, hidden 0, placed after the last
    added page), closes the box and the toast reads: Added “<name>” to the menu. with Undo, which removes the page again.
  Gantt starter: switches the prebuilt Gantt page on (show_gantt_editor 1, its tab name is the typed name when it is not "Gantt"), stores no row, same toast.
    It cannot be chosen while the Gantt page is already on.
  Limit: the prebuilt Gantt page always counts; with 4 added pages the Add page button is disabled so the box cannot open (the server refuses a sixth too).
Run: python3 dev/run_tests.py test_add_page_box_1252
"""
import json
import sqlite3
import time
import unittest

from _classic_page import classic
from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome

WIDTHS = (1400, 900)
# Two templates carry the name Numbers (figures-4 and figures-3), so the Status starter's Numbers chip and part are pinned by template id
# (figures-4, templates.js) beside the name; 'Item cards, three' is main's exact string (raid-3).
STATUS_IDS = ["report-headline", "figures-4", "raid-3", "key-dates"]
STARTERS = [("Blank with prompts", ["Text", "Text with image"]),
            ("Status", ["Report headline", "Numbers", "Item cards, three", "Coming dates"]),
            ("Documents", ["Text", "Files and links"]),
            ("Gantt", ["Header and Text", "Gantt", "Work items"]),
            ("People and next steps", ["Who to ask", "Next steps"])]
GANTT_WORDS = "A Gantt page with a header and text, a Gantt section and a Work items section."
BOX = "document.querySelector('#add-page-box')"
CHOICES = "[...document.querySelectorAll('#add-page-box .ap-choice')]"
SECS = json.dumps([{"id": "s1", "type": "text", "title": "Supplier notes head", "body": "<p>x</p>"}])


class Box(Base):
    def setUp(self):
        super().setUp()
        classic(self)

    def add(self, name):
        status, body = self.real_change({"project": "ABC", "kind": "added_pages", "op": "new", "values": {"name": name, "starter": "blank", "sections": SECS}})
        self.assertEqual(status, 200, body)

    def rows(self):
        return sorted(self.store.read("added_pages", project="ABC"), key=lambda r: (r["sort_order"], r["id"]))

    def open(self, cdp, width):
        p = self.visit(cdp)
        size(cdp, p, width, 900)
        p.js("location.hash = '#settings&p=ABC&s=reports'")
        p.until("!!document.querySelector('#add-pages .ap-meter')", "the Pages card drew")
        return p

    def opened(self, cdp, width):
        p = self.open(cdp, width)
        p.js("document.querySelector('#add-page').click()")
        p.until("!!" + BOX, "the box opened")
        # The box takes the focus in an effect after it is drawn (Dialog.jsx). The focus goes back only for a box whose effect ran: wait for it, as a person does.
        p.until("!!document.activeElement && document.activeElement.id === 'add-page-name'", "the focus is in the box")
        return p

    def pick(self, p, i):
        p.js("%s[%d].click()" % (CHOICES, i))

    def type_name(self, p, text):
        p.js("(() => { const i = document.querySelector('#add-page-name'); i.focus(); i.value = %s; i.dispatchEvent(new Event('input', {bubbles: true})); })()" % json.dumps(text))

    def toast_says(self, p, text):
        p.until("document.querySelector('.toasts') && document.querySelector('.toasts').textContent.includes(%s)" % json.dumps(text), "toast " + text)

    def gantt_on(self):
        with sqlite3.connect(str(self.store.path)) as con:
            return con.execute("SELECT show_gantt_editor FROM projects WHERE code = 'ABC'").fetchone()[0]

    def until_stored(self, ok, what):
        for _ in range(100):
            if ok():
                return
            time.sleep(0.1)
        self.fail("the store never showed: " + what)

    def check_box(self, w):
        with chrome() as cdp:
            p = self.opened(cdp, w)
            self.assertEqual(p.js(BOX + ".getAttribute('role')"), "dialog")
            self.assertEqual(p.js("document.querySelector('#add-page-box-t').textContent"), "Add page")
            self.assertEqual(p.js("[...document.querySelectorAll('#add-page-box .ap-pick h3')].map(e => e.textContent.trim())"), ["Choose a starter", "Name it"])
            got = p.js("%s.map(e => [e.querySelector('b').textContent.trim(), [...e.querySelectorAll('.ap-chips i')].map(c => c.textContent.trim())])" % CHOICES)
            self.assertEqual([tuple(g) for g in got], STARTERS)
            self.assertEqual(p.js("[...%s[1].querySelectorAll('.ap-chips i')].map(c => c.dataset.template)" % CHOICES), STATUS_IDS, "Numbers is figures-4, not figures-3")
            self.assertEqual(p.js("%s.map(e => e.querySelector('small') ? e.querySelector('small').textContent : '')" % CHOICES), ["", "", "", GANTT_WORDS, ""])
            self.assertEqual(p.js("%s.map(e => e.getAttribute('aria-checked'))" % CHOICES), ["true", "false", "false", "false", "false"])
            self.assertEqual(p.js("document.querySelector('#add-page-name').maxLength"), 40)
            self.assertEqual(p.js("document.querySelector('#add-page-name').value"), "Blank with prompts")
            cols = p.js("getComputedStyle(document.querySelector('#add-page-box .ap-cols')).gridTemplateColumns.split(' ').length")
            self.assertEqual(cols, 2 if w == 1400 else 1)
            self.assertLessEqual(p.js(BOX + ".getBoundingClientRect().width"), 980)
            self.assertEqual(p.js("document.documentElement.scrollWidth - document.documentElement.clientWidth"), 0)
            self.assertEqual(p.js("[...document.querySelectorAll('#add-page-box .ad-foot button')].map(b => b.textContent.trim())"), ["Cancel", "Add page"])
            left = p.js("document.querySelector('#add-page-box .ap-pick').getBoundingClientRect().left")
            r = p.js("(() => { const a = document.querySelector('#add-page-box .ap-pick').getBoundingClientRect(), b = document.querySelector('#add-page-box .ap-preview').getBoundingClientRect(); return [a.right <= b.left + 1, a.bottom <= b.top + 1]; })()")
            self.assertEqual(r, [True, False] if w == 1400 else [False, True], "list left and preview right at 1400, preview below at 900")
            self.assertGreaterEqual(left, 0)
            # the preview follows the choice: heading is the starter's name; a part shows its name and, if it has one, its approved prompt
            self.assertEqual(p.js("document.querySelector('#add-page-box .ap-preview h3').textContent.trim()"), "Blank with prompts")
            parts = p.js("[...document.querySelectorAll('#add-page-box .ap-part')].map(e => [e.querySelector('b').textContent.trim(), e.querySelector('span') ? e.querySelector('span').textContent : ''])")
            self.assertEqual(parts, [["Text", "Write one or two sentences: what is this page and who is it for?"], ["Text with image", "Say what the reader should look at first."]])
            self.pick(p, 1)
            p.until("document.querySelector('#add-page-name').value === 'Status'", "the name follows the starter")
            parts = p.js("[...document.querySelectorAll('#add-page-box .ap-part')].map(e => [e.querySelector('b').textContent.trim(), e.querySelector('span') ? e.querySelector('span').textContent : ''])")
            self.assertEqual(parts, [["Report headline", "Write the headline in one line: where the project stands this week."], ["Numbers", "Add the number and what it counts."],
                                      ["Item cards, three", ""], ["Coming dates", ""]])
            self.assertEqual(p.js("[...document.querySelectorAll('#add-page-box .ap-part')].map(e => e.dataset.template)"), STATUS_IDS, "the Numbers part is the figures-4 template")
            self.type_name(p, "Mine")
            self.pick(p, 2)
            p.until("document.querySelector('.ap-preview h3').textContent.trim() === 'Documents'", "preview follows")
            self.assertEqual(p.js("document.querySelector('#add-page-name').value"), "Mine", "a typed name stays")
            self.type_name(p, "   ")
            self.assertTrue(p.js("document.querySelector('#add-page-box .ad-foot .btn.pri, #add-page-box .ad-foot button:last-child').disabled"), "a blank name: Add page is off")

    def test_box_opens_with_five_starters_and_preview_1400(self):
        self.check_box(1400)

    def test_box_opens_with_five_starters_and_preview_900(self):
        self.check_box(900)

    def test_cancel_and_escape_close_and_return_focus(self):
        with chrome() as cdp:
            p = self.opened(cdp, 1400)
            p.js("document.querySelector('#add-page-box .ad-foot button').click()")
            p.until("!" + BOX, "Cancel closed")
            self.until_stored(lambda: p.js("document.activeElement && document.activeElement.id === 'add-page'"), "focus back on the button")
            p.js("document.querySelector('#add-page').click()")
            p.until("!!" + BOX, "reopened")
            p.js("document.querySelector('#add-page-name').dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
            p.until("!" + BOX, "Esc closed")
            self.until_stored(lambda: p.js("document.activeElement && document.activeElement.id === 'add-page'"), "focus back on the button after Esc")
            self.assertEqual(self.rows(), [])

    def check_add(self, w):
        self.add("Existing page")
        with chrome() as cdp:
            p = self.opened(cdp, w)
            self.pick(p, 1)
            self.type_name(p, "Supplier status")
            p.js("document.querySelector('#add-page-box .ad-foot button:last-child').click()")
            p.until("!" + BOX, "the box closed")
            self.until_stored(lambda: len(self.rows()) == 2, "the row")
            row = self.rows()[-1]
            self.assertEqual((row["name"], row["starter"], row["client"], row["hidden"]), ("Supplier status", "status", 0, 0))
            self.assertGreater(row["sort_order"], self.rows()[0]["sort_order"] - 1)
            self.assertEqual([s["type"] for s in json.loads(row["sections"])], ["reportheadline", "figures4", "raid3", "keydates"])
            self.toast_says(p, "Added “Supplier status” to the menu.")
            p.until("[...document.querySelectorAll('.top .tabs .tab')].map(t => t.textContent.trim()).join().includes('Existing page,Supplier status')", "tab after the others")
            self.assertEqual(p.js("document.querySelector('.ap-meter').textContent"), "3 of 5 added pages (Gantt counts)")
            p.until("!![...document.querySelectorAll('.toasts button')].find(b => b.textContent.trim() === 'Undo')", "Undo in the toast")
            p.js("[...document.querySelectorAll('.toasts button')].find(b => b.textContent.trim() === 'Undo').click()")
            self.until_stored(lambda: len(self.rows()) == 1, "undone")

    def test_blank_starter_page_starts_with_the_text_and_image_side_by_side_heading(self):
        """AP3: the starter's list names the template 'Text with image'; the section a new page starts with has the heading 'Text and Image Side by Side'."""
        with chrome() as cdp:
            p = self.opened(cdp, 1400)
            self.type_name(p, "Plain page")
            p.js("document.querySelector('#add-page-box .ad-foot button:last-child').click()")
            p.until("!" + BOX, "the box closed")
            self.until_stored(lambda: len(self.rows()) == 1, "the row")
            secs = json.loads(self.rows()[0]["sections"])
            self.assertEqual([s["type"] for s in secs], ["text", "textimage"])
            self.assertEqual(secs[1]["title"], "Text and Image Side by Side")

    def test_add_a_starter_stores_page_toast_and_undo_1400(self):
        self.check_add(1400)

    def test_add_a_starter_stores_page_toast_and_undo_900(self):
        self.check_add(900)

    def test_gantt_starter_switches_the_prebuilt_page_on_and_cannot_be_chosen_twice(self):
        with chrome() as cdp:
            p = self.opened(cdp, 1400)
            self.assertEqual(self.gantt_on(), 0)
            self.pick(p, 3)
            p.until("document.querySelector('#add-page-name').value === 'Gantt'", "named Gantt")
            self.assertEqual(p.js("[...document.querySelectorAll('#add-page-box .ap-part')].map(e => e.querySelector('b').textContent.trim())"), ["Header and Text", "Gantt", "Work items"])
            p.js("document.querySelector('#add-page-box .ad-foot button:last-child').click()")
            p.until("!" + BOX, "closed")
            self.until_stored(lambda: self.gantt_on() == 1, "Gantt on")
            self.assertEqual(self.rows(), [])
            self.toast_says(p, "Added “Gantt” to the menu.")
            p.js("document.querySelector('#add-page').click()")
            p.until("!!" + BOX, "box again")
            self.assertTrue(p.js("%s[3].getAttribute('aria-disabled') === 'true'" % CHOICES))
            self.pick(p, 3)
            self.assertEqual(p.js("%s[3].getAttribute('aria-checked')" % CHOICES), "false", "a disabled starter is not chosen")

    def test_fourth_added_page_fills_the_five_and_the_button_goes_off(self):
        for n in range(3):
            self.add(f"Page {n}")
        with chrome() as cdp:
            p = self.opened(cdp, 900)
            p.js("document.querySelector('#add-page-box .ad-foot button:last-child').click()")
            p.until("!" + BOX, "closed")
            self.until_stored(lambda: len(self.rows()) == 4, "fourth")
            p.until("document.querySelector('#add-page').disabled", "the button is off at 5 of 5")
            self.assertEqual(p.js("document.querySelector('.ap-meter').textContent"), "5 of 5 added pages (Gantt counts)")


if __name__ == "__main__":
    unittest.main()
