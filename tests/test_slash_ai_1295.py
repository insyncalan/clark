"""Row 1295 items 1 and 2: AI help in the slash commands editor and the AI check, in Chrome in Classic at 1400, against the real server with a FAKE provider (no model, no sign-in).

Run: python3 dev/run_tests.py test_slash_ai_1295
Describe-and-write-all, Write it, Make it clearer, Shorter and Undo fill the form for the person to read and change nothing on disk; a command written with AI says so; only the
person's own words go to the provider, never a placeholder's value; a secret, an empty box, AI off and a failure each have a line and the provider is not asked. The AI check shows
the size in tokens and the warnings at once and asks for its three verdicts only when asked. Chrome is required: fails, never skips."""
import json
import threading
import time

from _paths import SRC  # noqa: F401
from test_ai_route import Fake
from test_server import chrome, wait
from test_slash_editor_1295 import Base, EDITOR, EditorStates

from clark import ai_service, ask_service

DESCRIBE = "Name: who-owns\nMenu: Who owns an item\nWhere: item\nGets: answer\nInstructions: Tell me who owns {item} and when it is due."
MENU = "Who owns this work item"
CLEARER_ADD = "Dates as DD-MM-YYYY"
SECRET_LINE = "Use the " + "pass" + "word: " + "hunter2" * 2 + " to log in"      # built here so the file holds no password-shaped text
VERDICT = "Clear: yes, it says what to read.\nReads: only work items.\nChanges: nothing."


def wrap(text):
    return "<<<SUGGESTION\n" + text + "\nSUGGESTION>>>"


class Scripted(Fake):
    """Replies by what the prompt asks for; keeps every prompt it was given."""

    def __init__(self):
        super().__init__()
        self.replies = {}

    def ask(self, request):
        self.prompts = getattr(self, "prompts", [])
        self.prompts.append(request.text)
        for key, reply in self.replies.items():
            if key in request.text:
                self.reply = wrap(reply)
                break
        return super().ask(request)


class AiBase(Base):
    def setUp(self):
        super().setUp()
        self.provider = Scripted()
        self.addCleanup(self.provider.release.set)
        self.provider.replies = {"Write a slash command": DESCRIBE, "Write the line a menu shows": MENU, "Add short plain-English lines": "Overdue by owner\n" + CLEARER_ADD,
                                 "Make the text shorter": "Overdue by owner", "Judge these": VERDICT}
        self.s.httpd.app_settings.change_ask({"enabled": True})
        svc = ask_service.AskService(self.s.httpd.app_settings.db_path, self.provider, [])
        self.s.httpd.ask = svc
        self.s.httpd.ai = ai_service.AiService(svc)

    def ready(self, js):
        self.until(js, "!!document.querySelector('#slash-ai-write')", "the AI help is on the page")
        self.until(js, "document.querySelector('#slash-ai-write').disabled === false", "the AI state is known")

    def new_form(self, cdp):
        js = self.editor(cdp, EDITOR + "&new=1")
        self.until(js, "!!document.querySelector('#sl-menu')", "the form opens")
        self.ready(js)
        return js

    def val(self, js, sel):
        return js(f"document.querySelector({sel!r}).value")

    def done(self, js):
        self.until(js, "!document.querySelector('#slash-ai-stop')", "the run ends")


class Help(AiBase):
    def test_describe_fills_every_field_for_reading_and_saves_nothing(self):
        with chrome() as cdp:
            js = self.new_form(cdp)
            self.assertEqual(js("document.querySelectorAll('#slash-ai-note').length"), 0)
            self.type_into(js, "#slash-ai-describe-in", "Tell me who owns an item")
            self.click(js, "#slash-ai-describe")
            self.until(js, "document.querySelector('#sl-name').value === 'who-owns'", "the name is written")
            self.done(js)
            self.assertEqual(self.val(js, "#sl-menu"), "Who owns an item")
            self.assertEqual(self.val(js, "#sl-text"), "Tell me who owns {item} and when it is due.")
            self.assertEqual(js("document.querySelector('[data-scope=item]').getAttribute('aria-pressed')"), "true")
            self.assertEqual(js("document.querySelector('[data-result=answer]').getAttribute('aria-pressed')"), "true")
            self.assertEqual(js("document.querySelector('#slash-ai-note').innerText"), "Written with AI. Read it before you save.")
            self.assertEqual(self.files(), [])
            self.assertEqual(len(self.provider.requests), 1)
            self.assertIn("Tell me who owns an item", self.provider.prompts[0])
            self.click(js, "#slash-ai-undo")
            self.until(js, "document.querySelector('#sl-name').value === ''", "Undo gives the form back")
            self.assertEqual(self.val(js, "#sl-text"), "")
            self.assertEqual(js("document.querySelectorAll('#slash-ai-note').length"), 0)

    def test_a_command_written_with_ai_is_saved_marked_as_ai(self):
        with chrome() as cdp:
            js = self.new_form(cdp)
            self.type_into(js, "#slash-ai-describe-in", "Tell me who owns an item")
            self.click(js, "#slash-ai-describe")
            self.until(js, "document.querySelector('#sl-name').value === 'who-owns'", "written")
            self.done(js)
            self.click(js, "#slash-save")
            self.until(js, "!!document.querySelector('.slash-side [data-pick=who-owns]')", "saved")
            self.assertEqual(json.loads((self.d / "ask-commands" / "ABC" / "who-owns.json").read_text(encoding="utf-8")).get("ai"), True)

    def test_write_it_writes_the_menu_line_from_the_instructions_only(self):
        with chrome() as cdp:
            js = self.new_form(cdp)
            self.type_into(js, "#sl-text", "Tell me who owns {item}. Today is {today}. Asked: {input}")
            self.type_into(js, "#sl-input", "Priya")
            self.click(js, "#slash-ai-write")
            self.until(js, f"document.querySelector('#sl-menu').value === {MENU!r}", "the menu line is written")
            self.assertEqual(js("document.querySelector('#slash-ai-note').innerText"), "Written with AI. Read it before you save.")
            sent = self.provider.prompts[0]
            self.assertIn("{item}", sent)                       # the placeholder goes as written; nothing is filled from the project
            self.assertNotIn("Priya", sent)
            self.assertEqual(self.files(), [])

    def test_make_it_clearer_shows_what_was_added_and_undo_restores_the_text(self):
        with chrome() as cdp:
            js = self.new_form(cdp)
            self.type_into(js, "#sl-text", "Overdue by owner")
            self.click(js, "#slash-ai-clearer")
            self.until(js, f"document.querySelector('#sl-text').value.includes({CLEARER_ADD!r})", "the lines are added")
            self.done(js)
            self.assertEqual(js("document.querySelector('#slash-ai-added').innerText").strip().endswith(CLEARER_ADD), True)
            self.click(js, "#slash-ai-undo")
            self.until(js, "document.querySelector('#sl-text').value === 'Overdue by owner'", "Undo restores the text")
            self.assertEqual(js("document.querySelectorAll('#slash-ai-added').length"), 0)

    def test_shorter_replaces_the_text_and_undo_restores_it(self):
        with chrome() as cdp:
            js = self.new_form(cdp)
            self.type_into(js, "#sl-text", "Please list everything that is overdue, grouped by owner, oldest first")
            self.click(js, "#slash-ai-shorter")
            self.until(js, "document.querySelector('#sl-text').value === 'Overdue by owner'", "shorter")
            self.click(js, "#slash-ai-undo")
            self.until(js, "document.querySelector('#sl-text').value.startsWith('Please list')", "Undo restores it")

    def test_an_empty_box_says_so_and_the_provider_is_not_asked(self):
        with chrome() as cdp:
            js = self.new_form(cdp)
            for button in ("#slash-ai-write", "#slash-ai-clearer", "#slash-ai-shorter"):
                self.click(js, button)
                self.until(js, "!!document.querySelector('#slash-ai-line')", "a line is shown")
                self.assertEqual(js("document.querySelector('#slash-ai-line').innerText"), "The instructions are empty.")
            self.click(js, "#slash-ai-describe")
            self.until(js, "document.querySelector('#slash-ai-line').innerText === 'Say what you want first.'", "the sentence is asked for")
            self.assertEqual(len(self.provider.requests), 0)

    def test_a_secret_is_never_sent(self):
        with chrome() as cdp:
            js = self.new_form(cdp)
            self.type_into(js, "#sl-text", SECRET_LINE)
            self.click(js, "#slash-ai-shorter")
            self.until(js, "!!document.querySelector('#slash-ai-line')", "a line is shown")
            self.done(js)
            self.assertEqual(js("document.querySelector('#slash-ai-line').innerText"), "No suggestion came back. Try again.")
            self.assertEqual(len(self.provider.requests), 0)
            self.assertEqual(self.val(js, "#sl-text"), SECRET_LINE)

    def test_ai_off_has_its_line_and_asks_nothing(self):
        self.s.httpd.app_settings.change_ask({"enabled": False})
        with chrome() as cdp:
            js = self.editor(cdp, EDITOR + "&new=1")
            self.until(js, "!!document.querySelector('#slash-ai-write')", "the AI help is on the page")
            self.until(js, "!!document.querySelector('#slash-ai-line')", "the line is shown")
            self.assertEqual(js("document.querySelector('#slash-ai-line').innerText"), "AI is switched off in Settings.")
            self.assertTrue(js("document.querySelector('#slash-ai-write').disabled"))
            self.assertEqual(len(self.provider.requests), 0)

    def test_not_signed_in_has_its_line(self):
        self.provider.connected = False
        with chrome() as cdp:
            js = self.editor(cdp, EDITOR + "&new=1")
            self.until(js, "!!document.querySelector('#slash-ai-line')", "the line is shown")
            self.assertEqual(js("document.querySelector('#slash-ai-line').innerText"), "Connect Claude in Settings to use this.")

    def test_a_failure_says_so_and_changes_nothing(self):
        self.provider.fault = "boom"
        with chrome() as cdp:
            js = self.new_form(cdp)
            self.type_into(js, "#sl-text", "Overdue by owner")
            self.click(js, "#slash-ai-shorter")
            self.until(js, "!!document.querySelector('#slash-ai-line')", "a line is shown")
            self.assertEqual(js("document.querySelector('#slash-ai-line').innerText"), "No suggestion came back. Try again.")
            self.assertEqual(self.val(js, "#sl-text"), "Overdue by owner")
            self.assertEqual(js("document.querySelectorAll('#slash-ai-note').length"), 0)

    def test_a_reply_that_is_not_a_command_changes_nothing(self):
        self.provider.replies["Write a slash command"] = "I could not do that."
        with chrome() as cdp:
            js = self.new_form(cdp)
            self.type_into(js, "#slash-ai-describe-in", "Tell me who owns an item")
            self.click(js, "#slash-ai-describe")
            self.until(js, "!!document.querySelector('#slash-ai-line')", "a line is shown")
            self.assertEqual(js("document.querySelector('#slash-ai-line').innerText"), "No suggestion came back. Try again.")
            self.assertEqual(self.val(js, "#sl-name"), "")

    def test_stop_ends_a_run_and_changes_nothing(self):
        self.provider.hold = True
        with chrome() as cdp:
            js = self.new_form(cdp)
            self.type_into(js, "#sl-text", "Overdue by owner")
            self.click(js, "#slash-ai-shorter")
            self.until(js, "!!document.querySelector('#slash-ai-stop')", "Stop is shown while it works")
            self.assertTrue(js("document.querySelector('#slash-ai-write').disabled"))
            self.assertTrue(wait(self.provider.entered.is_set, 10))
            self.click(js, "#slash-ai-stop")
            self.done(js)
            self.assertEqual(self.val(js, "#sl-text"), "Overdue by owner")
            self.provider.release.set()

    def test_the_state_is_asked_again_at_the_click_and_a_switched_off_ai_asks_nothing(self):
        with chrome() as cdp:
            js = self.new_form(cdp)
            self.type_into(js, "#sl-text", "Overdue by owner")
            self.s.httpd.app_settings.change_ask({"enabled": False})      # switched off after the page was drawn
            self.click(js, "#slash-ai-shorter")
            self.until(js, "!!document.querySelector('#slash-ai-line')", "a line is shown")
            self.assertEqual(js("document.querySelector('#slash-ai-line').innerText"), "AI is switched off in Settings.")
            self.assertEqual(len(self.provider.requests), 0)
            self.assertEqual(self.val(js, "#sl-text"), "Overdue by owner")

    def test_a_run_is_dropped_when_the_person_keeps_typing(self):
        self.provider.hold = True
        self.provider.replies["Make the text shorter"] = "Overdue"
        with chrome() as cdp:
            js = self.new_form(cdp)
            self.type_into(js, "#sl-text", "Overdue by owner")
            self.click(js, "#slash-ai-shorter")
            self.assertTrue(wait(self.provider.entered.is_set, 10))
            self.type_into(js, "#sl-text", "Overdue by owner, newest first")
            self.provider.release.set()
            self.done(js)
            time.sleep(0.5)
            self.assertEqual(self.val(js, "#sl-text"), "Overdue by owner, newest first")
            self.assertEqual(js("document.querySelectorAll('#slash-ai-note').length"), 0)

    def test_a_built_in_keeps_its_name_when_ai_describes_it(self):
        with chrome() as cdp:
            js = self.editor(cdp, EDITOR + "&name=check")
            self.until(js, "!!document.querySelector('#slash-builtin-note')", "the built-in opens")
            self.ready(js)
            self.type_into(js, "#slash-ai-describe-in", "Tell me who owns an item")
            self.click(js, "#slash-ai-describe")
            self.until(js, "document.querySelector('#sl-menu').value === 'Who owns an item'", "written")
            self.assertEqual(self.val(js, "#sl-name"), "check")

    def test_no_project_data_is_sent_while_the_ai_writes(self):
        """Row 1541 AP2: all five requests hold the instruction text and the fixed instruction only, never the project's name, items or files."""
        project_words = ("Example Programme", "On track", "Pilot live", "Agree the cut-over plan", "ABC-M-001", "ABC-A-001")
        with chrome() as cdp:
            js = self.new_form(cdp)
            self.type_into(js, "#sl-text", "Overdue by owner")
            self.type_into(js, "#slash-ai-describe-in", "Overdue by owner sentence")
            for button in ("#slash-ai-describe", "#slash-ai-write", "#slash-ai-clearer", "#slash-ai-shorter", "#slash-check-run"):
                before = len(self.provider.requests)
                self.type_into(js, "#sl-text", "Overdue by owner")
                self.click(js, button)
                self.assertTrue(wait(lambda: len(self.provider.requests) > before, 20), button)
                self.done(js)
            self.assertEqual(len(self.provider.prompts), 5)
            for sent in self.provider.prompts:
                self.assertIn("Overdue by owner", sent)
                for word in project_words:
                    self.assertNotIn(word, sent)


class UndoAndStates(AiBase):
    def test_one_undo_per_ai_result_and_a_typed_edit_clears_it(self):
        """Row 1541 AP3: an AI result gives exactly one #slash-ai-undo; a second result still gives one, keeping the fields that result replaced; a click restores them and uses the step up; a typed edit clears it."""
        with chrome() as cdp:
            js = self.new_form(cdp)
            count = lambda: js("document.querySelectorAll('#slash-ai-undo').length")   # noqa: E731
            first = "Please list everything that is overdue, grouped by owner, oldest first"
            self.type_into(js, "#sl-text", first)
            self.assertEqual(count(), 0)
            self.click(js, "#slash-ai-shorter")
            self.until(js, "document.querySelector('#sl-text').value === 'Overdue by owner'", "the first result")
            self.assertEqual(count(), 1)
            self.assertEqual(js("document.querySelectorAll('#slash-undo').length"), 0)
            self.done(js)
            self.click(js, "#slash-ai-clearer")
            self.until(js, f"document.querySelector('#sl-text').value.includes({CLEARER_ADD!r})", "the second result")
            self.done(js)
            self.assertEqual(count(), 1)
            self.click(js, "#slash-ai-undo")
            self.until(js, "document.querySelector('#sl-text').value === 'Overdue by owner'", "the click restores the fields the second result replaced")
            self.assertEqual(count(), 0)
            self.type_into(js, "#sl-text", first)                # the same reply as the text is no suggestion, so the text is made longer again
            before = len(self.provider.requests)
            self.click(js, "#slash-ai-shorter")
            self.assertTrue(wait(lambda: len(self.provider.requests) > before, 20), "asked again")
            self.until(js, "document.querySelectorAll('#slash-ai-undo').length === 1", "an Undo again", 20)
            self.done(js)
            self.type_into(js, "#sl-text", "A typed change")
            self.until(js, "document.querySelectorAll('#slash-ai-undo').length === 0", "a typed edit clears the Undo")

    def states_at_both_widths(self, check):
        for width, tracks in ((1400, 3), (900, 1)):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    js = EditorStates.open_at(self, cdp, width, dark, EDITOR + "&new=1")
                    self.until(js, "!!document.querySelector('#slash-ai-write')", "the AI help is on the page", 30)
                    self.until(js, "document.querySelector('#slash-ai-write').disabled === false", "the AI state is known", 30)
                    check(js, tracks)

    def grid(self, js, tracks):
        self.until(js, "!!document.querySelector('.slash-grid')", "the grid is drawn")
        self.assertEqual(js(EditorStates.TRACKS), tracks)

    def test_the_ai_check_verdict_shows_at_both_widths(self):
        """Row 1541 AP4 state 5: #slash-check-run shows the verdict (#slash-check with -clear, -reads, -changes) in light and dark at 1400 and 900."""
        def check(js, tracks):
            self.type_into(js, "#sl-text", "Tell me who owns {item}")
            self.click(js, "#slash-check-run")
            self.until(js, "!!document.querySelector('#slash-check-clear')", "the verdict is shown")
            self.done(js)
            self.grid(js, tracks)
            for part in ("clear", "reads", "changes"):
                self.assertTrue(js(f"document.querySelector('#slash-check-{part}').offsetHeight > 0"), part)
            self.assertEqual(js("document.querySelector('#slash-check-reads').innerText"), "only work items.")
        self.states_at_both_widths(check)

    def test_an_error_message_is_a_role_alert_at_both_widths(self):
        """Row 1541 AP4 state 5: a save the server cannot do shows its error in .pub-msg with role alert, in light and dark at 1400 and 900."""
        def check(js, tracks):
            self.assertEqual(js("document.querySelector('.pub-msg').getAttribute('role')"), "status")
            self.type_into(js, "#sl-name", "monday")
            self.type_into(js, "#sl-menu", "Monday summary")
            self.type_into(js, "#sl-text", "Group the overdue items by owner.")
            self.until(js, "!document.querySelector('#slash-save').disabled", "Save is on")
            store = self.s.httpd.ask_commands
            self.s.httpd.ask_commands = None                     # the store goes away after the page loaded
            self.addCleanup(setattr, self.s.httpd, "ask_commands", store)
            self.click(js, "#slash-save")
            self.until(js, "document.querySelector('.pub-msg').getAttribute('role') === 'alert'", "the message is an alert")
            self.s.httpd.ask_commands = store
            self.assertTrue(js("document.querySelector('.pub-msg p.error').innerText.length > 0"))
            self.assertTrue(js("document.querySelector('.pub-msg').offsetHeight > 0"))
            self.grid(js, tracks)
        self.states_at_both_widths(check)


class Check(AiBase):
    def test_size_and_warnings_are_live_and_nothing_is_asked(self):
        with chrome() as cdp:
            js = self.new_form(cdp)
            self.until(js, "!!document.querySelector('#slash-check')", "the check is on the page")
            self.assertEqual(js("document.querySelector('#slash-tokens').innerText"), "0 tokens")
            self.assertIn("The instructions are empty.", js("document.querySelector('#slash-warn').innerText"))
            self.type_into(js, "#sl-text", "a" * 400)
            self.until(js, "document.querySelector('#slash-tokens').innerText === '100 tokens'", "the size follows the text")
            self.assertEqual(js("document.querySelectorAll('#slash-warn').length"), 0)
            self.type_into(js, "#sl-text", "{item} " + "a" * 900)
            self.until(js, "document.querySelector('#slash-warn').innerText.includes('The instructions are long.')", "long is said")
            self.assertEqual(len(self.provider.requests), 0)

    def test_the_verdicts_come_only_when_asked_and_use_the_instructions_alone(self):
        with chrome() as cdp:
            js = self.new_form(cdp)
            self.type_into(js, "#sl-text", "Tell me who owns {item} for {input}")
            self.type_into(js, "#sl-input", "Priya")
            time.sleep(0.5)
            self.assertEqual(len(self.provider.requests), 0)
            self.click(js, "#slash-check-run")
            self.until(js, "!!document.querySelector('#slash-check-clear')", "the verdicts are shown")
            self.assertEqual(js("[...document.querySelectorAll('#slash-check dt')].map(e => e.innerText)"), ["Clear?", "Reads only what a question reads?", "What it can change?"])
            self.assertEqual(js("document.querySelector('#slash-check-clear').innerText"), "yes, it says what to read.")
            self.assertEqual(js("document.querySelector('#slash-check-changes').innerText"), "nothing.")
            self.assertEqual(len(self.provider.requests), 1)
            self.assertNotIn("Priya", self.provider.prompts[0])
            self.type_into(js, "#sl-text", "Tell me who owns {item}")
            self.until(js, "!document.querySelector('#slash-check-clear')", "an old verdict goes when the text changes")

    def test_the_check_has_its_own_lines_for_empty_off_and_failure(self):
        with chrome() as cdp:
            js = self.new_form(cdp)
            self.click(js, "#slash-check-run")
            self.until(js, "!!document.querySelector('#slash-ai-line')", "a line is shown")
            self.assertEqual(js("document.querySelector('#slash-ai-line').innerText"), "The instructions are empty.")
            self.assertEqual(len(self.provider.requests), 0)
            self.provider.replies["Judge these"] = "Nothing in the right shape"
            self.type_into(js, "#sl-text", "Tell me who owns {item}")
            self.click(js, "#slash-check-run")
            self.until(js, "document.querySelector('#slash-ai-line') && document.querySelector('#slash-ai-line').innerText.startsWith('No suggestion')", "the failure line")
            self.assertEqual(js("document.querySelectorAll('#slash-check-clear').length"), 0)
