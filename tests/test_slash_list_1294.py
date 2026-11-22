"""Row 1294: the slash commands part of the ask clark page (A8 items 5; ticket test 8), in Chrome in Classic at 1400.

Run: python3 dev/run_tests.py test_slash_list_1294
The All projects list shows every command with its tag (Built in, Yours, Action for /history and /new), the three links open the editor in a new tab and the Settings
window stays; the project tab lists only that project's own commands (or says there are none) and has a "From All projects" row whose See them goes to the All projects tab.
The list and the editor are Row 1295's; this file pins only what the 1294 page adds. Chrome is required: fails, never skips."""
import unittest

from test_server import chrome

from test_slash_editor_1295 import Base

ALL_LINE = "These are the slash commands available in every project. A project can have its own with the same name; its own wins there. Built-in ones can be edited or copied."
PROJECT_LINE = "Slash commands that exist only in this project. One with the same name as one for all projects wins here."


class AllTab(Base):
    def test_every_command_has_its_tag_and_the_links_open_new_tabs_and_the_foot_counts(self):
        svc = self.s.httpd.ask_commands
        rec = {"menu": "Monday summary", "text": "Overdue by owner", "scope": "anywhere", "result": "answer"}
        svc.change({"scope": "all", "action": "save", "record": {**rec, "name": "monday"}})
        with chrome() as cdp:
            js = self.settings(cdp, "all")
            self.until(js, "!!document.querySelector('#slash-all [data-slash-row]')", "the list is read")
            tags = js("Object.fromEntries([...document.querySelectorAll('#slash-all [data-slash-row]')].map(r => [r.dataset.slashRow, r.querySelector('.slash-tag').innerText]))")
            self.assertEqual(tags, {"monday": "Yours", "check": "Built in", "summary": "Built in", "overdue": "Built in", "risks": "Built in", "milestones": "Built in",
                                    "usecases": "Built in", "history": "Action", "new": "Action"})
            self.assertEqual(js("document.querySelector('#slash-all-line').innerText"), "Type / in the box. " + ALL_LINE)
            self.assertEqual(js("document.querySelector('#slash-all-foot').innerText"), "The editor is its own page: it opens in a new tab. 1 yours, 6 built in, 2 actions.")
            links = js("[...document.querySelectorAll('#slash-all a')].map(a => [a.innerText, a.target, a.rel])")
            self.assertEqual([l[0] for l in links[:3]], ["Open the editor ↗", "New slash command ↗", "Edit ↗"])
            self.assertTrue(all(l[1] == "_blank" and l[2] == "noopener" for l in links))
            self.assertEqual(js("location.hash"), "#settings&p=ABC&s=claude")      # the Settings window is not replaced
            self.assertFalse(js("!!document.querySelector('#slash-all [data-slash-row=history] a')"))


class ProjectTab(Base):
    def test_a_project_without_its_own_says_so_and_points_to_all_projects(self):
        svc = self.s.httpd.ask_commands
        rec = {"menu": "Monday summary", "text": "Overdue by owner", "scope": "anywhere", "result": "answer"}
        svc.change({"scope": "all", "action": "save", "record": {**rec, "name": "monday"}})
        with chrome() as cdp:
            js = self.settings(cdp)
            self.until(js, "!!document.querySelector('#slash-from-all')", "the row is shown")
            self.assertEqual(js("document.querySelectorAll('#slash-project [data-slash-row]').length"), 0)
            self.assertEqual(js("document.querySelector('#slash-none').innerText"), "None yet. The ones for all projects work here too.")
            self.assertEqual(js("document.querySelector('#slash-project-line').innerText"), "Only in ABC. " + PROJECT_LINE)
            self.assertEqual(js("document.querySelector('#slash-from-all').innerText"), "From All projects The 9 slash commands for all projects (1 yours, 6 built in, 2 actions).\nSee them")
            self.assertEqual(js("document.querySelector('#slash-project-foot').innerText"), "The editor opens in a new tab.")
            js("document.querySelector('[data-slash-see]').click()")
            self.until(js, "!!document.querySelector('#slash-all [data-slash-row]')", "the All projects tab opens")
            self.assertEqual(js("document.querySelector('[data-ask-tab=all]').getAttribute('aria-current')"), "true")

    def test_a_server_without_the_route_shows_no_none_yet_and_no_all_projects_row(self):
        self.s.httpd.ask_commands = None
        with chrome() as cdp:
            js = self.settings(cdp)
            self.until(js, "!!document.querySelector('#slash-note')", "the unavailable line is shown")
            self.assertEqual(js("[!!document.querySelector('#slash-none'), !!document.querySelector('#slash-from-all')]"), [False, False])


if __name__ == "__main__":
    unittest.main()


class Singular(unittest.TestCase):
    """The count words are singular at 1: '1 slash command', '1 action' (the real lines of SlashCommandsList.jsx run under node)."""
    def run_node(self, call):
        import json
        import re
        import subprocess
        from _paths import ROOT
        src = (ROOT / "src" / "clark" / "page" / "src" / "edit" / "SlashCommandsList.jsx").read_text(encoding="utf-8")
        lines = [re.search(r"^export const %s = .*?;$" % name, src, re.M).group(0).replace("export ", "", 1) for name in ("counts", "SLASH_ALL_COUNTS")]
        out = subprocess.run(["node", "-e", "\n".join(lines) + "\nconsole.log(JSON.stringify(" + call + "))"], capture_output=True, text=True, check=True)
        return json.loads(out.stdout)

    def test_one_slash_command_and_one_action(self):
        self.assertEqual(self.run_node("SLASH_ALL_COUNTS(1, 0, 0, 1)"), "The 1 slash command for all projects (0 yours, 0 built in, 1 action).")

    def test_zero_slash_commands_and_zero_actions(self):
        self.assertEqual(self.run_node("SLASH_ALL_COUNTS(0, 0, 0, 0)"), "The 0 slash commands for all projects (0 yours, 0 built in, 0 actions).")

    def test_two_slash_commands_and_two_actions(self):
        self.assertEqual(self.run_node("SLASH_ALL_COUNTS(2, 0, 0, 2)"), "The 2 slash commands for all projects (0 yours, 0 built in, 2 actions).")

    def test_the_foot_counts_are_singular_at_one_action(self):
        self.assertEqual(self.run_node("counts(1, 1, 1)"), "1 yours, 1 built in, 1 action")
