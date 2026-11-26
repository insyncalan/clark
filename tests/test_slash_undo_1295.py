"""Row 1572 AP4 (row 1295 AP11): each change in the slash command editor that has an Undo gives one Undo, and one press puts the editor back to what it was before that change.

Run: python3 dev/run_tests.py test_slash_undo_1295
Remove gives one #slash-undo; Make it clearer, Shorter and Write it all (describe) each give one #slash-ai-undo; a second change replaces the first Undo, so there are never two at once;
typing clears the AI Undo. At 1400 and 900. Chrome is required: fails, never skips."""
from test_server import chrome
from test_slash_ai_1295 import AiBase, CLEARER_ADD, EDITOR
import test_slash_editor_1295 as _test_slash_editor_1295

FIELDS = "JSON.stringify(['#sl-name', '#sl-menu', '#sl-text'].map((s) => document.querySelector(s).value))"
COUNTS = "[document.querySelectorAll('#slash-undo').length, document.querySelectorAll('#slash-ai-undo').length]"


class SlashUndo(AiBase):
    def test_one_undo_per_change_and_one_press_restores_it(self):
        start = "Please list everything that is overdue, grouped by owner, oldest first"
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                js = _test_slash_editor_1295.EditorStates.open_at(self, cdp, width, False, EDITOR + "&new=1")
                self.ready(js)
                for button, wait_for in (("#slash-ai-clearer", f"document.querySelector('#sl-text').value.includes({CLEARER_ADD!r})"),
                                         ("#slash-ai-shorter", "document.querySelector('#sl-text').value === 'Overdue by owner'")):
                    self.type_into(js, "#sl-text", start)
                    self.assertEqual(js(COUNTS), [0, 0])
                    before = js(FIELDS)
                    self.click(js, button)
                    self.until(js, wait_for, button)
                    self.done(js)
                    self.assertEqual(js(COUNTS), [0, 1], button)
                    self.assertNotEqual(js(FIELDS), before)
                    self.click(js, "#slash-ai-undo")
                    self.assertEqual(js(FIELDS), before, f"one press restores the editor after {button}")
                    self.assertEqual(js(COUNTS), [0, 0])
                # Write it all: the fields before and after one press are the same
                self.type_into(js, "#slash-ai-describe-in", "Who owns an item")
                before = js(FIELDS)
                self.click(js, "#slash-ai-describe")
                self.until(js, "document.querySelector('#sl-name').value === 'who-owns'", "describe fills the form")
                self.done(js)
                self.assertEqual(js(COUNTS), [0, 1])
                self.click(js, "#slash-ai-undo")
                self.assertEqual(js(FIELDS), before)
                self.assertEqual(js(COUNTS), [0, 0])
                # a second change replaces the first Undo, never two at once
                self.type_into(js, "#sl-text", start)
                self.click(js, "#slash-ai-clearer")
                self.until(js, f"document.querySelector('#sl-text').value.includes({CLEARER_ADD!r})", "first")
                self.done(js)
                self.click(js, "#slash-ai-shorter")
                self.until(js, "document.querySelector('#sl-text').value === 'Overdue by owner'", "second")
                self.done(js)
                self.assertEqual(js(COUNTS), [0, 1])
                self.type_into(js, "#sl-text", "typed")
                self.assertEqual(js(COUNTS), [0, 0], "typing clears the AI Undo")
                # Remove: one Undo, one press brings the command back
                self.type_into(js, "#sl-name", f"monday{width}")
                self.type_into(js, "#sl-menu", "Monday summary")
                self.type_into(js, "#sl-text", "Group the overdue items by owner.")
                self.until(js, "!document.querySelector('#slash-save').disabled", "Save is on")
                self.click(js, "#slash-save")
                self.until(js, f"!!document.querySelector('.slash-side [data-pick=monday{width}]')", "saved")
                self.click(js, "#slash-remove")
                self.until(js, "!!document.querySelector('#slash-undo')", "Remove gives an Undo")
                self.assertEqual(js(COUNTS), [1, 0])
                self.click(js, "#slash-undo")
                self.until(js, f"!!document.querySelector('.slash-side [data-pick=monday{width}]')", "restored")
                self.assertEqual(js(COUNTS), [0, 0])
