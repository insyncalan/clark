"""Row 1292 (S12): the Draft beside the ask panel, in a real browser against the real page and routes.

Run: flock <lock> ~/bin/clark-chrome-slot env CLARK_CHROME=/usr/local/bin/clark-chrome python3 dev/run_tests.py test_ask_draft
The server's `ask` is the stub of test_ask_panel, here with a draft in its answer. Covers: the answer shows "Draft ready" and the Draft opens
beside the panel with the words of the mock-up and an editable body; nothing is in the report until "Add to the report"; the menu offers each Text
section and a new one; a replace and an add are each one step that Undo takes back; Esc and the close button leave the report as it was; closing
the panel closes the draft. Fictional text only.
"""
import time
import unittest

from test_ask_panel import Panel, Stub
from test_server import chrome

DRAFT = {"html": "<p>The pilot is on track.</p><p>Two actions are overdue.</p>", "title": "This week's summary", "sec": ""}
SECTIONS = "document.querySelectorAll('.secs > .sec[data-id]').length"


class DraftStub(Stub):
    def ask(self, body):
        status, out = super().ask(body)
        if out.get("ok"):
            out["draft"] = dict(DRAFT)
        return status, out


class Draft(Panel):
    def setUp(self):
        super().setUp()
        self.stub = DraftStub()
        self.s.httpd.ask = self.stub

    def drafted(self, cdp):
        p = self.opened(cdp, before="document.querySelector('[data-mode=edit]').click()")
        self.ask(p, "Summarise this week")
        p.until("!!document.querySelector('#ask-draft')", "the draft opened beside the panel")
        return p

    def test_the_answer_offers_the_draft_and_it_opens_beside_the_panel_with_its_words(self):
        with chrome() as cdp:
            p = self.drafted(cdp)
            self.assertIn("Draft ready", p.js("document.querySelector('[data-ask-draftcard]').textContent"))
            self.assertEqual(p.js("document.querySelector('#ask-draft h2').textContent"), "Draft")
            self.assertEqual(p.js("document.querySelector('#ask-draft .ad-hint').textContent"), "Edit it freely. Nothing is in the report yet.")
            self.assertIn("The pilot is on track.", p.js("document.querySelector('#ask-draft-doc').innerText"))
            self.assertEqual(p.js("document.querySelector('#ask-draft-doc').getAttribute('contenteditable')"), "true")
            self.assertEqual(p.js("document.querySelector('#ask-draft-add').textContent"), "Add to the report")
            self.assertEqual(p.js("document.querySelector('#ask-draft-copy').textContent"), "Copy")
            left = p.js("document.querySelector('#ask-draft').getBoundingClientRect().right")
            panel = p.js("document.querySelector('#ask-panel').getBoundingClientRect().left")
            self.assertAlmostEqual(left, panel, delta=2, msg="the draft's right edge is the panel's left edge")

    def test_closing_it_leaves_the_report_as_it_was(self):
        with chrome() as cdp:
            p = self.drafted(cdp)
            before = p.js(SECTIONS)
            p.js("document.querySelector('#ask-draft-close').click()")
            p.until("document.querySelector('#ask-draft') === null", "closed by its button")
            self.assertEqual(p.js(SECTIONS), before)
            p.js("document.querySelector('[data-ask-draftcard] button').click()")
            p.until("!!document.querySelector('#ask-draft')", "the card opens it again")
            p.js("document.querySelector('#ask-draft-doc').focus()")
            p.key("Escape", code="Escape", vk=27)
            p.until("document.querySelector('#ask-draft') === null", "closed by Esc")
            self.assertTrue(p.js("!!document.querySelector('#ask-panel')"), "Esc in the draft does not close the panel")
            self.assertEqual(p.js(SECTIONS), before)

    def test_closing_the_panel_closes_the_draft(self):
        with chrome() as cdp:
            p = self.drafted(cdp)
            p.js("document.querySelector('#ask-close').click()")
            p.until("document.querySelector('#ask-draft') === null", "the draft went with the panel")

    def test_the_menu_offers_each_text_section_and_a_new_one(self):
        with chrome() as cdp:
            p = self.drafted(cdp)
            p.js("document.querySelector('#ask-draft-add').click()")
            p.until("!!document.querySelector('#ask-draft-menu')", "the menu opened")
            labels = p.js("[...document.querySelectorAll('#ask-draft-menu [role=menuitem]')].map(b => b.textContent)")
            self.assertTrue(any(x.startswith("Replace the text of ") and x.endswith(" now)") for x in labels), labels)
            self.assertEqual(labels[-1], "Add as a new Text section at the end")

    def test_add_as_a_new_section_is_one_step_and_undo_takes_it_back(self):
        with chrome() as cdp:
            p = self.drafted(cdp)
            before = p.js(SECTIONS)
            p.js("document.querySelector('#ask-draft-doc').innerHTML = '<p>Edited by hand.</p>'")
            p.js("document.querySelector('#ask-draft-add').click()")
            p.js("[...document.querySelectorAll('#ask-draft-menu [role=menuitem]')].pop().click()")
            p.until(f"{SECTIONS} === {before + 1}", "the new Text section is in the report")
            self.assertIn("Edited by hand.", p.js("document.querySelector('.secs').innerText"))
            p.until("document.querySelector('#ask-draft') === null", "the sheet is done")
            p.js("document.querySelector('[data-undo]').click()")
            p.until(f"{SECTIONS} === {before}", "Undo took the one step back")

    def test_replace_writes_the_edited_text_into_the_section(self):
        with chrome() as cdp:
            p = self.drafted(cdp)
            p.js("document.querySelector('#ask-draft-doc').innerHTML = '<p>Replaced words zebra.</p>'")
            p.js("document.querySelector('#ask-draft-add').click()")
            p.js("document.querySelector('#ask-draft-menu [data-kind=replace]').click()")
            p.until("document.querySelector('.secs').innerText.includes('Replaced words zebra.')", "the section has the edited draft")
            time.sleep(0.2)
            self.assertEqual(p.js("document.querySelector('#ask-draft') === null"), True)


if __name__ == "__main__":
    unittest.main()
