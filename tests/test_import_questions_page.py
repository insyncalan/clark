"""Row 1156 in a real browser: the Import workbook box asks about a milestone and a use case clark does not have (ImportWorkbook.jsx, dataCard.js).
Run: python3 dev/run_tests.py test_import_questions_page

The server is the real one over the #39 plant in a temporary folder with the real workbook import (as tests/test_settings_data_page.py).
A workbook whose one new work item names an unknown milestone and use case is imported at 1400 and 900: the box lists both with the two
choices, Import stays off until each is answered, Create it then Import writes both and links the item, the keys work, and one Undo puts it all back.
Chrome is required: these tests fail, never skip, without it.
"""
import base64
import os
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

import test_settings_data_page as sdp
from test_server import chrome

MS, UC, TEXT = "Pilot wave 2", "Reporting set-up", "Set up the test rig"
SHOTS = os.environ.get("CLARK_SHOTS")                      # a folder to save a screenshot of each state into; nothing is saved without it


def with_unknowns(rig, folder):
    """The exported workbook plus one new Actions row that names MS and UC; base64."""
    b64, _, _ = sdp.workbook(rig, folder, "Agree the cut-over plan, version two")
    path = Path(folder) / "PUB work items.xlsx"
    wb = load_workbook(str(path))
    ws = wb["Actions"]
    head = {c.value: c.column for c in ws[1]}
    row = ws.max_row + 1
    for label, value in {"Description": TEXT, "Milestone": MS, "Use case": UC}.items():
        ws.cell(row, head[label]).value = value
    wb.save(str(path))
    return base64.b64encode(path.read_bytes()).decode()


class Questions(sdp.Card):
    def rows(self, table):
        return self.rig.store.read(table, "PUB")

    def steps(self):
        return self.rig.store.con.execute("SELECT count(*) FROM applies").fetchone()[0]

    def new_item(self):
        return [a for a in self.rows("actions") if a["description"] == TEXT]

    def to_questions(self, cdp, w, name):
        folder = Path(self.tmp.name) / name
        folder.mkdir()
        b64 = with_unknowns(self.rig, folder)
        p = self.page(cdp)
        p.width(w)
        self.open_settings(p)
        p.js("document.querySelector('#import-workbook').click()")
        p.until("!!document.querySelector('#import-box')", "the box opened")
        self.choose(p, b64)
        p.until("!!document.querySelector('#import-unknowns')", "the check lists what is not in clark")
        return p

    def shot(self, cdp, p, w, name):
        if SHOTS:
            p.settled()
            Path(SHOTS, "import-questions-%s-%d.png" % (name, w)).write_bytes(base64.b64decode(cdp.call("Page.captureScreenshot", {"format": "png"}, p.sid)["data"]))

    def pick(self, p, label, value):
        p.js("document.querySelector('[data-unknown] [aria-label=%r] input[value=%s]').click()" % (label, value) if False else
             "[...document.querySelectorAll('[data-unknown]')].find(li => li.innerText.includes(%r)).querySelector('input[value=%s]').click()" % (label, value))

    def test_both_are_listed_with_the_two_choices_and_import_waits_for_each_answer(self, w):
        if True:
            with chrome() as cdp:
                p = self.to_questions(cdp, w, "a%d" % w)
                before, n = (len(self.rows("milestones")), len(self.rows("use_cases"))), self.steps()
                self.assertEqual(p.js("[...document.querySelectorAll('[data-unknown]')].map(li => li.querySelector('.tag').textContent + ':' + li.querySelector('.imp-main span:last-child').textContent).sort()"),
                                 ["Milestone:" + MS, "Use case:" + UC])
                self.assertEqual(p.js("[...document.querySelectorAll('[data-unknown]:first-child label')].map(l => l.textContent)"), ["Create it", "Use an existing one"])
                self.assertEqual(p.js("document.querySelector('#import-unanswered').textContent"), "Each milestone and use case that is not in clark needs an answer.")
                self.assertTrue(p.js("document.querySelector('#import-go').disabled"), "Import is off with nothing answered")
                self.shot(cdp, p, w, "asked")
                self.pick(p, MS, "create")
                p.until("!!document.querySelector('#import-unanswered')", "one answer left")
                self.assertTrue(p.js("document.querySelector('#import-go').disabled"), "Import is still off with one answered")
                p.js("document.querySelector('#import-go').click()")
                self.assertEqual((self.steps(), len(self.rows("milestones")), self.new_item()), (n, before[0], []), "a click on a disabled Import writes nothing")
                self.pick(p, UC, "use")                          # Use an existing one, with no item chosen yet, is not an answer
                p.until("!!document.querySelector('select')", "the list of existing use cases")
                self.assertTrue(p.js("document.querySelector('#import-go').disabled"), "no item chosen is not an answer")
                self.assertLessEqual(p.js("document.documentElement.scrollWidth"), w)
                self.shot(cdp, p, w, "use-existing")
                self.pick(p, UC, "create")
                p.until("!document.querySelector('#import-unanswered') && !document.querySelector('#import-go').disabled", "Import is on once each is answered")
                self.assertEqual((self.steps(), len(self.rows("milestones")), len(self.rows("use_cases"))), (n, before[0], before[1]), "answering writes nothing")
                self.shot(cdp, p, w, "answered")

    def test_create_it_then_import_writes_both_links_the_item_and_one_undo_reverses(self, w):
        if True:
            with chrome() as cdp:
                p = self.to_questions(cdp, w, "b%d" % w)
                snap = lambda: (sorted(a["id"] for a in self.rows("actions")), sorted(m["id"] for m in self.rows("milestones")), sorted(u["id"] for u in self.rows("use_cases")))  # noqa: E731
                before, n = snap(), self.steps()
                self.pick(p, MS, "create")
                self.pick(p, UC, "create")
                p.until("!document.querySelector('#import-go').disabled", "Import is on")
                p.js("document.querySelector('#import-go').click()")
                p.until("!!document.querySelector('#import-result')", "the result")
                self.shot(cdp, p, w, "imported")
                self.assertEqual(self.steps(), n + 1, "ONE step")
                (m,) = [r for r in self.rows("milestones") if r["name"] == MS]
                (u,) = [r for r in self.rows("use_cases") if r["title"] == UC]
                (a,) = self.new_item()
                self.assertEqual((a["milestone"], a["use_case"]), (m["id"], u["id"]))
                p.js("document.querySelector('#import-undo').click()")
                p.until("document.querySelector('#import-result') && document.querySelector('#import-result').textContent.startsWith('Put back')", "Undo")
                self.assertEqual(snap(), before, "one Undo takes the item and both created items away")

    def test_the_keys_esc_tab_and_enter(self, w):
        if True:
            with chrome() as cdp:
                p = self.to_questions(cdp, w, "c%d" % w)
                n, before = self.steps(), len(self.rows("milestones"))
                inside = "(() => { const e = document.activeElement, li = e && e.closest('[data-unknown]'); return !!li; })()"
                p.js("document.querySelector('#import-box').querySelector('[data-unknown] input').focus()")
                self.assertTrue(p.js(inside))
                p.key("Tab", vk=9)
                p.until("document.activeElement.closest('[data-unknown]') && document.activeElement.closest('[data-unknown]') !== document.querySelector('[data-unknown]')", "Tab moves on to the next question")
                # Space on a radio answers it; Enter on Import imports
                for label in (MS, UC):
                    p.js("[...document.querySelectorAll('[data-unknown]')].find(li => li.innerText.includes(%r)).querySelector('input[value=create]').focus()" % label)
                    p.key(" ", "Space", 32)
                p.until("!document.querySelector('#import-go').disabled", "both answered from the keyboard")
                p.js("document.querySelector('#import-go').focus()")
                p.key("Enter", vk=13)
                p.until("!!document.querySelector('#import-result')", "Enter on Import imported")
                self.assertEqual((self.steps(), len(self.new_item())), (n + 1, 1))
                self.assertEqual(len(self.rows("milestones")), before + 1)
                # Esc closes the finished box
                self.settle(p, "document.activeElement && document.activeElement.id === 'import-close'", "focus moved to Close")
                p.key("Escape", "Escape", 27)
                p.until("!document.querySelector('#import-box')", "Esc closed the box")

    def test_esc_before_import_closes_the_box_and_writes_nothing(self, w):
        if True:
            with chrome() as cdp:
                p = self.to_questions(cdp, w, "d%d" % w)
                n, before = self.steps(), (len(self.rows("milestones")), len(self.rows("use_cases")))
                self.pick(p, MS, "create")
                p.key("Escape", "Escape", 27)
                p.until("!document.querySelector('#import-box')", "Esc closed the box")
                self.assertEqual((self.steps(), len(self.rows("milestones")), len(self.rows("use_cases")), self.new_item()), (n, before[0], before[1], []))


for _name in [n for n in vars(Questions) if n.startswith("test_")]:
    for _w in sdp.WIDTHS:
        setattr(Questions, "%s_%d" % (_name, _w), (lambda f, w: lambda self: f(self, w))(getattr(Questions, _name), _w))
    delattr(Questions, _name)


if __name__ == "__main__":
    unittest.main()
