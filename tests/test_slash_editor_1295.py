"""Row 1295: the slash commands list in Settings and the editor page (a page of its own, opened in a new tab), in Chrome in Classic at 1400. Cards shows none of it.

Run: python3 dev/run_tests.py test_slash_editor_1295
The list names every command with its tag and opens the editor in a new tab; the editor lists Yours then Built in, keeps the name rules, saves a command as a file,
edits a built-in as the person's own version (Reset brings the original back), copies, removes (with Undo), shows /history and /new locked, opens the placeholders
popup (Esc closes it and the focus returns), and fills the placeholders in the test. Chrome is required: fails, never skips."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from _editor_checks import for_project
from test_ask_settings import make_db, service
from test_page import DATA, navigate
from test_server import Running, chrome, wait

from clark import ask_commands_service, page

EDITOR = "/?slash-editor=1&project=ABC"


class Base(unittest.TestCase):
    theme = "prototype-2.0"

    def setUp(self):
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=self.theme))
        self.addCleanup(self.s.close)
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.s.httpd.app_settings = service(make_db(self.d))
        self.s.httpd.ask_commands = ask_commands_service.AskCommandsService(self.d)

    def until(self, js, expr, what, seconds=20):
        self.assertTrue(wait(lambda: js(expr), seconds), f"{what}: {expr}")

    def settings(self, cdp, tab="project"):
        sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=claude"))
        js = lambda e: cdp.js(e, sid)          # noqa: E731
        self.until(js, "!!document.querySelector('[data-ask-tab]')", "the tabs are on the page", 30)
        if tab == "all":
            js("document.querySelector('[data-ask-tab=all]').click()")
        return js

    def editor(self, cdp, path=EDITOR):
        sid = navigate(cdp, self.s.port, "")
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}{path}"}, sid)
        js = lambda e: cdp.js(e, sid)          # noqa: E731
        self.until(js, "!!document.querySelector('#slash-page') && !!document.querySelector('.slash-side button')", "the editor is on the page", 30)
        return js

    def type_into(self, js, selector, text):
        js(f"(() => {{ const e = document.querySelector('{selector}'); e.focus(); e.value = {text!r}; e.dispatchEvent(new Event('input', {{bubbles: true}})); }})()")

    def click(self, js, selector):
        js(f"document.querySelector({selector!r}).click()")

    def files(self, sub=""):
        return sorted(p.name for p in (self.d / "ask-commands" / sub).glob("*.json"))


class SettingsList(Base):
    def test_the_project_tab_lists_every_command_and_opens_the_editor_in_a_new_tab(self):
        with chrome() as cdp:
            js = self.settings(cdp)
            self.until(js, "!!document.querySelector('#slash-project [data-slash-row]')", "the list is read")
            self.assertEqual(js("document.querySelector('#slash-project h2').innerText"), "Slash commands in ABC")
            rows = js("[...document.querySelectorAll('#slash-project [data-slash-row]')].map(r => [r.dataset.slashRow, r.querySelector('.slash-tag').innerText, !!r.querySelector('.slash-edit')])")
            self.assertEqual([r[0] for r in rows], ["check", "summary", "overdue", "risks", "milestones", "usecases", "history", "new"])
            self.assertEqual({r[0]: r[1] for r in rows}["history"], "Action")
            self.assertEqual({r[0]: r[2] for r in rows}, {"check": True, "summary": True, "overdue": True, "risks": True, "milestones": True, "usecases": True, "history": False, "new": False})
            links = js("[...document.querySelectorAll('#slash-project a')].map(a => [a.innerText, a.target, a.rel, a.getAttribute('href')])")
            self.assertEqual(links[0], ["Open the editor ↗", "_blank", "noopener", "/?slash-editor=1&project=ABC"])
            self.assertEqual(links[1][0], "New slash command ↗")
            self.assertIn("new=1", links[1][3])
            self.assertEqual(links[2], ["Edit ↗", "_blank", "noopener", "/?slash-editor=1&project=ABC&name=check"])

    def test_a_file_of_yours_and_one_of_the_project_show_their_tags_and_the_project_one_wins(self):
        svc = self.s.httpd.ask_commands
        rec = {"menu": "Monday summary", "text": "Overdue by owner", "scope": "anywhere", "result": "answer"}
        svc.change({"scope": "all", "action": "save", "record": {**rec, "name": "monday"}})
        svc.change({"scope": "all", "action": "save", "record": {**rec, "name": "shared"}})
        svc.change({"scope": "project", "project": "ABC", "action": "save", "record": {**rec, "menu": "Own line", "name": "monday"}})
        svc.change({"scope": "all", "action": "save", "record": {**rec, "name": "check", "replaces": "check", "menu": "My check"}})
        with chrome() as cdp:
            js = self.settings(cdp)
            self.until(js, "document.querySelectorAll('#slash-project [data-slash-row]').length > 8", "the list is read")
            got = js("Object.fromEntries([...document.querySelectorAll('#slash-project [data-slash-row]')].map(r => [r.dataset.slashRow, [r.querySelector('.slash-menu').innerText, r.querySelector('.slash-tag').innerText]]))")
            self.assertEqual(got["monday"], ["Own line", "ABC only"])
            self.assertEqual(got["shared"], ["Monday summary", "Yours"])
            self.assertEqual(got["check"], ["My check", "Built in · edited"])
            self.assertEqual(js("document.querySelectorAll('#slash-project [data-slash-row=monday]').length"), 1)
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.until(js, "!!document.querySelector('#slash-all [data-slash-row]')", "the all projects list is read")
            self.assertEqual(js("document.querySelector('#slash-all h2').innerText"), "Slash commands for all projects")
            self.assertEqual(js("[...document.querySelectorAll('#slash-all [data-slash-row]')].slice(0, 2).map(r => r.dataset.slashRow)"), ["monday", "shared"])

    def test_a_server_without_the_route_says_so_in_one_line(self):
        self.s.httpd.ask_commands = None
        with chrome() as cdp:
            js = self.settings(cdp)
            self.until(js, "!!document.querySelector('#slash-note')", "the line is shown")
            self.assertEqual(js("document.querySelector('#slash-note').innerText"), "Slash commands aren't ready on this computer yet.")
            self.assertEqual(js("document.querySelectorAll('#slash-project [data-slash-row]').length"), 0)


class CardsKeepsItsPage(Base):
    theme = None

    def test_cards_has_no_list_and_no_editor(self):
        with chrome() as cdp:
            js = self.settings(cdp)
            self.until(js, "!!document.querySelector('#ask-settings')", "Settings is drawn")
            self.assertEqual(js("document.querySelectorAll('.slash-list').length"), 0)
            self.editor_cards(cdp)

    def editor_cards(self, cdp):
        sid = navigate(cdp, self.s.port, "")
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}{EDITOR}"}, sid)
        js = lambda e: cdp.js(e, sid)          # noqa: E731
        self.until(js, "document.documentElement.dataset.ready === '1'", "the page is drawn")
        self.assertEqual(js("document.querySelectorAll('#slash-page').length"), 0)


class Editor(Base):
    def test_the_page_is_its_own_with_a_back_link_and_the_list_in_order(self):
        with chrome() as cdp:
            js = self.editor(cdp)
            self.assertEqual(js("document.querySelector('#slash-back').innerText"), "← Back to Settings")
            self.assertEqual(js("document.querySelector('#slash-back').getAttribute('href')"), "/?project=ABC#settings&s=claude")
            self.assertEqual(js("document.querySelector('#slash-h').innerText"), "Slash commands in ABC")
            self.assertEqual(js("[...document.querySelectorAll('.slash-side h2')].map(h => h.innerText)"), ["Yours", "Built in"])
            self.assertEqual(js("document.querySelector('#slash-new').innerText"), "+ New slash command")
            self.assertEqual(js("[...document.querySelectorAll('.slash-side [data-pick]')].map(b => [b.dataset.pick, b.disabled])"),
                             [["check", False], ["summary", False], ["overdue", False], ["risks", False], ["milestones", False], ["usecases", False], ["history", True], ["new", True]])
            self.assertEqual(js("document.querySelector('[data-pick=history]').title"), "An action, not a question: it cannot be edited")
            self.assertEqual(js("document.querySelectorAll('#slash-save').length"), 0)       # nothing is chosen yet

    def test_the_name_rules_give_their_messages_and_save_stays_off(self):
        with chrome() as cdp:
            js = self.editor(cdp)
            self.click(js, "#slash-new")
            self.until(js, "!!document.querySelector('#sl-name')", "the form opens")
            for name, word in (("a", "at least"), ("Abc", "lower case"), ("a b", "spaces"), ("1ab", "start with a letter"), ("a_b", "only lower case"), ("check", "built-in")):
                self.type_into(js, "#sl-name", name)
                self.until(js, f"document.querySelector('#sl-name-m').innerText.includes({word!r})", f"{name!r} says {word!r}")
                self.assertEqual(js("document.querySelector('#sl-name').getAttribute('aria-invalid')"), "true")
                self.assertTrue(js("document.querySelector('#slash-save').disabled"))
            self.type_into(js, "#sl-name", "monday")
            self.until(js, "document.querySelector('#sl-name-m').innerText.startsWith('Free.')", "a good name")
            self.assertEqual(js("document.querySelector('#sl-name').getAttribute('aria-invalid')"), None)

    def test_a_new_command_is_saved_as_a_file_listed_and_removed_with_undo(self):
        with chrome() as cdp:
            js = self.editor(cdp, EDITOR + "&new=1")
            self.until(js, "!!document.querySelector('#sl-name')", "the form opens")
            self.type_into(js, "#sl-name", "monday")
            self.type_into(js, "#sl-menu", "Monday summary")
            self.type_into(js, "#sl-text", "Group the overdue items by owner on {today}.")
            self.until(js, "!document.querySelector('#slash-save').disabled", "Save is on")
            self.click(js, "#slash-save")
            self.until(js, "!!document.querySelector('.slash-side [data-pick=monday]')", "monday is in Yours")
            self.assertEqual(self.files("ABC"), ["monday.json"])
            self.assertEqual(json.loads((self.d / "ask-commands" / "ABC" / "monday.json").read_text(encoding="utf-8"))["menu"], "Monday summary")
            self.assertEqual(js("document.querySelector('.slash-side h2 + button').dataset.pick"), "monday")
            self.click(js, "#slash-remove")
            self.until(js, "!document.querySelector('.slash-side [data-pick=monday]')", "monday is gone")
            self.assertEqual(self.files("ABC"), [])
            self.click(js, "#slash-undo")
            self.until(js, "!!document.querySelector('.slash-side [data-pick=monday]')", "Undo brings it back")
            self.assertEqual(self.files("ABC"), ["monday.json"])

    def test_a_built_in_is_saved_as_your_version_reset_and_copied(self):
        with chrome() as cdp:
            js = self.editor(cdp, EDITOR + "&name=check")
            self.until(js, "!!document.querySelector('#sl-text')", "the built-in opens")
            self.assertEqual(js("document.querySelector('#sl-text').value"), "Check this report")
            self.assertTrue(js("document.querySelector('#sl-name').readOnly"))
            self.assertIn("A built-in name cannot change", js("document.querySelector('#sl-name-m').innerText"))
            self.assertEqual(js("[...document.querySelectorAll('.slash-actions button')].map(b => b.id)"), ["slash-save", "slash-copy", "slash-cancel"])
            self.type_into(js, "#sl-text", "Check this report and list what is wrong")
            self.click(js, "#slash-save")
            self.until(js, "!!document.querySelector('#slash-reset')", "Reset appears once it is your version")
            rec = json.loads((self.d / "ask-commands" / "ABC" / "check.json").read_text(encoding="utf-8"))
            self.assertEqual((rec["replaces"], rec["text"]), ("check", "Check this report and list what is wrong"))
            self.assertEqual(js("document.querySelector('[data-pick=check] .slash-tag').innerText.trim()"), "edited")
            self.click(js, "#slash-copy")
            self.until(js, "!!document.querySelector('.slash-side [data-pick=check-2]')", "the copy is named check-2")
            self.assertEqual(sorted(self.files("ABC")), ["check-2.json", "check.json"])
            self.assertEqual(json.loads((self.d / "ask-commands" / "ABC" / "check-2.json").read_text(encoding="utf-8"))["text"], "Check this report and list what is wrong")
            self.click(js, "[data-pick=check]")
            self.until(js, "!!document.querySelector('#slash-reset')", "check is opened again")
            self.click(js, "#slash-reset")
            self.until(js, "!document.querySelector('#slash-reset')", "Reset is done")
            self.assertEqual(js("document.querySelector('#sl-text').value"), "Check this report")
            self.assertEqual(self.files("ABC"), ["check-2.json"])

    def test_the_placeholders_popup_opens_and_esc_closes_it_and_the_focus_returns(self):
        with chrome() as cdp:
            js = self.editor(cdp, EDITOR + "&name=summary")
            self.until(js, "!!document.querySelector('#slash-help')", "the ? is there")
            self.assertEqual(js("document.querySelector('#slash-help').getBoundingClientRect().width"), 24)
            self.click(js, "#slash-help")
            self.until(js, "!!document.querySelector('#slash-pop')", "the popup opens")
            self.assertEqual(js("[...document.querySelectorAll('#slash-pop th')].map(t => t.innerText)"), ["Write", "It becomes", "Works when it appears"])
            self.assertEqual(js("document.querySelectorAll('#slash-pop tbody tr').length"), 5)
            self.until(js, "document.activeElement && document.activeElement.id === 'slash-pop'", "the focus moves in")
            cdp_key = "document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))"
            js(cdp_key)
            self.until(js, "!document.querySelector('#slash-pop')", "Esc closes it")
            self.until(js, "document.activeElement && document.activeElement.id === 'slash-help'", "the focus returns to the ?")

    def test_the_test_fills_each_placeholder_or_says_not_set(self):
        with chrome() as cdp:
            js = self.editor(cdp, EDITOR + "&new=1")
            self.until(js, "!!document.querySelector('#sl-name')", "the form opens")
            self.type_into(js, "#sl-text", "Look at {item} on {today} for {input}.")
            self.type_into(js, "#sl-input", "Priya")
            self.until(js, "document.querySelectorAll('#slash-reads .ph-off').length === 1", "the reads are drawn")
            self.assertEqual(js("[...document.querySelectorAll('#slash-reads .ph-off')].map(e => e.innerText)"), ["not set"])
            self.assertEqual(js("document.querySelector('#slash-reads').innerText").count("Priya"), 1)
            self.assertRegex(js("document.querySelector('#slash-reads .ph-on').innerText"), r"^\d\d-\d\d-\d{4}$")
            self.click(js, "[data-scope=item]")
            self.assertEqual(js("document.querySelectorAll('#slash-reads .ph-off').length"), 1)       # {item} still has no item to fill in the test
            self.click(js, "[data-scope=anywhere]")
            self.until(js, "!!document.querySelector('#slash-warn')", "{item} has nothing to fill where this appears: Anywhere")
            self.assertEqual(js("document.querySelector('#slash-warn').innerText"), "{item} has nothing to fill where this appears.")
            self.type_into(js, "#sl-text", "Look at {today}.")
            self.until(js, "!document.querySelector('#slash-warn')", "no warning for {today}")
            self.type_into(js, "#sl-text", "Look at {section}.")
            self.until(js, "!!document.querySelector('#slash-warn')", "the warning shows")
            self.assertIn("{section}", js("document.querySelector('#slash-warn').innerText"))

    def test_locked_commands_cannot_be_opened_by_address(self):
        with chrome() as cdp:
            js = self.editor(cdp, EDITOR + "&name=history")
            self.assertEqual(js("document.querySelectorAll('#sl-text').length"), 0)


if __name__ == "__main__":
    unittest.main()
