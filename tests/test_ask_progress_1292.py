"""Row 1292 (S6, no streaming): the working line says the one step the page knows and counts seconds; the 150 quips are gone.

The words are the real code from askWords.js, run under node. The panel source draws the line from the words file and counts from the send.
"""
import json
import re
import shutil
import subprocess
import unittest

from _paths import ROOT

EDIT = ROOT / "src" / "clark" / "page" / "src" / "edit"
WORDS = (EDIT / "askWords.js").read_text(encoding="utf-8")
STATE = (EDIT / "askPanelState.js").read_text(encoding="utf-8")
PANEL = (EDIT / "AskPanel.jsx").read_text(encoding="utf-8")
WORKITEMS = (ROOT / "src" / "clark" / "page" / "src" / "workItems.js").read_text(encoding="utf-8")
CSS = (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")


def run_node(body):
    named = re.search(r"^export const named = .*?;", WORDS, re.M).group(0).replace("export ", "", 1)
    step = re.search(r"^export const STEP_ASKING = .*?;", WORDS, re.M).group(0).replace("export ", "", 1)
    fns = "\n".join(re.search(r"^export const " + n + r" = .*?;$", WORDS, re.M).group(0).replace("export ", "", 1) for n in ("workingFor", "workingLine"))
    out = subprocess.run(["node", "-e", named + "\n" + step + "\n" + fns + "\n" + body], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@unittest.skipUnless(shutil.which("node"), "node is needed")
class WorkingLine(unittest.TestCase):
    def test_seconds_count_from_zero_and_are_whole(self):
        r = run_node("console.log(JSON.stringify([0, 0.9, 1, 8.4, 59.99, 61, -3].map(workingFor)));")
        self.assertEqual(r, ["Working 0s", "Working 0s", "Working 1s", "Working 8s", "Working 59s", "Working 61s", "Working 0s"])

    def test_the_step_names_the_provider_in_use(self):
        r = run_node("console.log(JSON.stringify([workingLine('Claude', 8), workingLine('ChatGPT', 3), workingLine(undefined, 0)]));")
        self.assertEqual(r, ["Asking Claude · Working 8s", "Asking ChatGPT · Working 3s", "Asking Claude · Working 0s"])


class Gone(unittest.TestCase):
    def test_no_quip_is_left_in_the_words_the_state_or_the_panel(self):
        for name, src in (("words", WORDS), ("state", STATE), ("panel", PANEL)):
            self.assertNotRegex(src.replace("ask-quip ask-step", ""), r"(?i)quip", name)      # the one old class name stays on the span so the Cards style block is as on main

    def test_the_panel_draws_the_line_from_the_words_and_counts_from_the_send(self):
        self.assertIn("W.workingLine(askProvider.value, secs)", PANEL)
        self.assertIn('id="ask-step"', PANEL)
        self.assertIn("setInterval", PANEL)
        self.assertIn("clearInterval", PANEL)
        self.assertIn("if (!busy) { setSecs(0); return undefined; }", PANEL)

    def test_the_line_is_hidden_from_screen_readers_so_the_clock_is_not_read_each_second(self):
        self.assertRegex(PANEL, r'id="ask-step" aria-hidden="true"')

    def test_the_clock_ticks_each_second_from_the_moment_of_the_send_in_whole_seconds_of_ms(self):
        self.assertIn('export const nowMs = () => Date.now();', WORKITEMS)
        self.assertIn('import { nowMs } from "../workItems.js";', PANEL)
        self.assertIn("const from = nowMs();", PANEL)
        self.assertIn("setSecs((nowMs() - from) / 1000), 1000)", PANEL)

    def test_the_line_stays_on_one_row_and_shrinks_with_an_ellipsis(self):
        rule = re.search(r"\.ask-step \{([^}]*)\}", CSS).group(1)
        for part in ("min-width: 0", "overflow: hidden", "text-overflow: ellipsis", "white-space: nowrap"):
            self.assertIn(part, rule)


if __name__ == "__main__":
    unittest.main()
