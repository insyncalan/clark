"""#1292 S10: slash commands in the ask clark box.

Run: python3 dev/run_tests.py test_ask_slash
Logic (askSlash.js) runs in node (skips without node). The panel part is headless Chrome, the real page, a stub for the server's ask.
Covers: "/" at the start of the box opens the menu with the eight commands, typing filters it, "/" later in a line opens nothing,
arrows move and wrap, Enter runs the chosen command (a question command asks its question; /new starts a chat; /history shows Earlier
chats), Esc closes the menu first and a second Esc closes the panel, and the box and menu are named for a screen reader.
"""
import json
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from _paths import SRC
from test_ask_panel import Stub
from test_report_editor import Base
from test_server import chrome

import esbuild  # noqa: E402  (dev/tools)

EDIT = SRC / "clark" / "page" / "src" / "edit"
NAMES = ["check", "summary", "overdue", "risks", "milestones", "usecases", "history", "new"]
ROWS = "JSON.stringify(Array.from(document.querySelectorAll('#ask-slash [role=option]')).map(function(o){return o.getAttribute('data-name')}))"
PICKED = "(function(){var o=document.querySelector('#ask-slash [aria-selected=true]');return o?o.getAttribute('data-name'):null})()"


def run_node(probe):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "as.js"
        done = esbuild.run(["--bundle", "--format=iife", "--global-name=AS", str(EDIT / "askSlash.js"), f"--outfile={out}"], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        script = Path(tmp) / "probe.js"
        script.write_text(out.read_text(encoding="utf-8") + ";\nconsole.log(JSON.stringify(" + probe + "));", encoding="utf-8")
        got = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert got.returncode == 0, got.stderr
        return json.loads(got.stdout)


class SlashLogic(unittest.TestCase):
    def test_the_menu_opens_only_for_a_slash_at_the_start(self):
        self.assertEqual(run_node("AS.slashMatches('/').map(c=>c.name)"), NAMES)
        self.assertIsNone(run_node("AS.slashMatches('')"))
        self.assertIsNone(run_node("AS.slashMatches('what is /risks')"))
        self.assertIsNone(run_node("AS.slashMatches(' /risks')"))
        self.assertIsNone(run_node("AS.slashMatches('/risks now')"), "a space ends the command word")
        self.assertIsNone(run_node("AS.slashMatches('/1')"))

    def test_typing_filters_by_the_start_of_the_name_in_any_case(self):
        self.assertEqual(run_node("AS.slashMatches('/m').map(c=>c.name)"), ["milestones"])
        self.assertEqual(run_node("AS.slashMatches('/S').map(c=>c.name)"), ["summary"])
        self.assertEqual(run_node("AS.slashMatches('/zzz')"), [])

    def test_arrows_wrap_and_the_ends_are_reachable(self):
        self.assertEqual(run_node("[AS.stepSlash(0,'ArrowDown',8),AS.stepSlash(7,'ArrowDown',8),AS.stepSlash(0,'ArrowUp',8),AS.stepSlash(3,'Home',8),AS.stepSlash(3,'End',8),AS.stepSlash(5,'x',3),AS.stepSlash(2,'ArrowDown',0)]"),
                         [1, 0, 7, 0, 7, 2, 0])

    def test_every_command_asks_or_acts_never_both(self):
        for c in run_node("AS.COMMANDS"):
            self.assertEqual(bool(c.get("ask")) + bool(c.get("act")), 1, c["name"])


class SlashPanel(Base):
    def setUp(self):
        super().setUp()
        self.stub = Stub()
        self.s.httpd.ask = self.stub

    def open_panel(self, cdp, width=1400):
        p = self.visit(cdp)
        p.key("/", code="Slash", vk=191)
        p.until("!!document.querySelector('#ask-panel')", "the panel opened")
        p.until("document.querySelector('#ask-panel').getAnimations().length === 0", "the panel has risen")
        p.until("!document.querySelector('#ask-send').disabled", "ready")
        p.js("document.querySelector('#ask-box').focus()")
        return p

    def asked(self):
        return [b["question"] for k, b in self.stub.calls if k == "ask"]

    def test_slash_opens_the_menu_and_typing_filters_it(self):
        with chrome() as cdp:
            p = self.open_panel(cdp)
            self.assertEqual(p.js("!!document.querySelector('#ask-slash')"), False)
            p.type("/")
            p.until("!!document.querySelector('#ask-slash')", "the menu opened")
            self.assertEqual(json.loads(p.js(ROWS)), NAMES)
            self.assertEqual(p.js(PICKED), "check", "the first row is chosen")
            p.type("ri")
            p.until(ROWS + " === JSON.stringify(['risks'])", "filtered")
            self.assertEqual(p.js("document.querySelector('#ask-slash').getAttribute('role')"), "listbox")
            self.assertEqual(p.js("document.querySelector('#ask-box').getAttribute('aria-expanded')"), "true")
            self.assertEqual(p.js("document.querySelector('#ask-box').getAttribute('aria-controls')"), "ask-slash")

    def test_the_menu_opens_filters_and_runs_a_command_at_900(self):
        """Row 1578 AP4: the panel tests above never set a width; at 900 the menu lists the 8 commands, filters and /risks asks its question."""
        with chrome() as cdp:
            p = self.open_panel(cdp)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": 900, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
            p.type("/")
            p.until("!!document.querySelector('#ask-slash')", "the menu opened at 900")
            self.assertEqual(json.loads(p.js(ROWS)), NAMES)
            p.type("ri")
            p.until(ROWS + " === JSON.stringify(['risks'])", "filtered at 900")
            self.assertTrue(p.js("(() => { const r = document.querySelector('#ask-slash').getBoundingClientRect(); return r.width > 0 && r.left >= 0 && r.right <= window.innerWidth; })()"), "the menu is inside the window")
            p.key("Enter", code="Enter", vk=13)
            p.until("!document.querySelector('#ask-stop') && document.querySelectorAll('.ask-turn').length >= 2", "answered", 20)
            self.assertEqual(len(self.asked()), 1)
            self.assertEqual(p.js("document.querySelector('#ask-box').value"), "")

    def test_a_slash_later_in_the_line_opens_nothing(self):
        with chrome() as cdp:
            p = self.open_panel(cdp)
            p.type("what about /ri")
            self.assertEqual(p.js("!!document.querySelector('#ask-slash')"), False)

    def test_arrows_move_and_enter_asks_the_chosen_question_and_empties_the_box(self):
        with chrome() as cdp:
            p = self.open_panel(cdp)
            p.type("/")
            p.until("!!document.querySelector('#ask-slash')", "open")
            p.key("ArrowDown", code="ArrowDown", vk=40)
            p.key("ArrowDown", code="ArrowDown", vk=40)
            p.until(PICKED + " === 'overdue'", "two down is /overdue")
            p.key("ArrowUp", code="ArrowUp", vk=38)
            p.until(PICKED + " === 'summary'", "one up is /summary")
            p.key("Enter", code="Enter", vk=13)
            p.until("!document.querySelector('#ask-stop') && document.querySelectorAll('.ask-turn').length >= 2", "answered", 20)
            self.assertEqual(self.asked(), ["Summarise this week"])
            self.assertEqual(p.js("document.querySelector('#ask-box').value"), "")
            self.assertEqual(p.js("!!document.querySelector('#ask-slash')"), False)

    def test_enter_with_a_typed_prefix_runs_the_first_match(self):
        with chrome() as cdp:
            p = self.open_panel(cdp)
            p.type("/mil")
            p.until(ROWS + " === JSON.stringify(['milestones'])", "filtered")
            p.key("Enter", code="Enter", vk=13)
            p.until("document.querySelectorAll('.ask-turn').length >= 2", "answered", 20)
            self.assertEqual(self.asked(), ["What is the next milestone?"])

    def test_new_starts_a_chat_and_sends_nothing(self):
        with chrome() as cdp:
            p = self.open_panel(cdp)
            p.type("Summarise the risks")
            p.key("Enter", code="Enter", vk=13)
            p.until("!document.querySelector('#ask-stop') && document.querySelectorAll('.ask-turn').length >= 2", "answered", 20)
            p.js("document.querySelector('#ask-box').focus()")
            p.type("/new")
            p.key("Enter", code="Enter", vk=13)
            p.until("document.querySelectorAll('.ask-turn').length === 0", "the chat is new")
            self.assertEqual(self.asked(), ["Summarise the risks"], "/new asked nothing")

    def test_history_shows_earlier_chats_and_sends_nothing(self):
        with chrome() as cdp:
            p = self.open_panel(cdp)
            p.type("/history")
            p.key("Enter", code="Enter", vk=13)
            p.until("document.querySelector('#ask-history').getAttribute('aria-pressed') === 'true'", "the list is showing")
            self.assertEqual(self.asked(), [])

    def test_escape_closes_the_menu_first_and_then_the_panel(self):
        with chrome() as cdp:
            p = self.open_panel(cdp)
            p.type("/")
            p.until("!!document.querySelector('#ask-slash')", "open")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('#ask-slash')", "the menu closed")
            self.assertEqual(p.js("!!document.querySelector('#ask-panel')"), True, "the panel stayed")
            self.assertEqual(p.js("document.querySelector('#ask-box').value"), "/", "the text stayed")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('#ask-panel')", "the second Esc closed the panel")

    def test_first_escape_leaves_the_panel_open_even_with_motion_reduced(self):
        """With reduced motion a close is instant (no leaving animation), so a panel still there after 1 s was never closed by the first Esc."""
        with chrome() as cdp:
            p = self.open_panel(cdp)
            cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]}, p.sid)
            p.type("/")
            p.until("!!document.querySelector('#ask-slash')", "open")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('#ask-slash')", "the menu closed")
            time.sleep(1)
            self.assertEqual(p.js("!!document.querySelector('#ask-panel')"), True, "the panel stayed after the first Esc")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('#ask-panel')", "the second Esc closed the panel")

    def test_no_match_says_so_and_enter_sends_nothing(self):
        with chrome() as cdp:
            p = self.open_panel(cdp)
            p.type("/zzz")
            p.until("!!document.querySelector('#ask-slash')", "open")
            self.assertEqual(p.js("document.querySelector('#ask-slash').textContent.trim()"), "No command by that name")
            p.key("Enter", code="Enter", vk=13)
            self.assertEqual(self.asked(), [])


if __name__ == "__main__":
    unittest.main()
