"""Row 1292 (S6, no streaming): in Classic the working line says the one step the page knows and counts seconds; Cards keeps its 150 quips.

The words are the real code from askWords.js, run under node. The panel source draws the line from the words file and counts from the send.
"""
import json
import re
import shutil
import subprocess
import unittest
from unittest import mock

import _testpage as testpage
from _paths import ROOT

from clark import page
from clark import theme as themes
import test_ask_panel as TAP
from test_report_editor import Base
from test_server import chrome

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
    def test_cards_keeps_its_quips_and_classic_gets_the_line(self):
        for name in ("QUIPS", "drawQuip", "quipDelay"):
            self.assertIn(name, WORDS + STATE, name)
        self.assertIn("if (classicTheme()) {", PANEL)
        self.assertIn('{classic ? <span class="ask-quip ask-step" id="ask-step" aria-hidden="true">{W.workingLine(askProvider.value, secs)}</span> : <span class="ask-quip" id="ask-quip" aria-hidden="true">{quip}</span>}', PANEL)

    def test_the_panel_draws_the_line_from_the_words_and_counts_from_the_send(self):
        self.assertIn("W.workingLine(askProvider.value, secs)", PANEL)
        self.assertIn('id="ask-step"', PANEL)
        self.assertIn("setInterval", PANEL)
        self.assertIn("clearInterval", PANEL)
        self.assertIn("if (!busy) { setSecs(0); setQuip(\"\"); return undefined; }", PANEL)

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


class LayeredBase(Base):
    """The real page with the Classic Theme layered in, as the server layers it; Cards is the unlayered page."""
    classic = True
    __test__ = False

    def setUp(self):
        full = testpage.html()
        html = page.layer_theme(full, themes.css("prototype-2.0")) if self.classic else full
        m = mock.patch.object(testpage, "html", lambda branding=None: html)
        m.start()
        self.addCleanup(m.stop)
        super().setUp()
        self.stub = TAP.Stub()
        self.s.httpd.ask = self.stub

    opened = TAP.Panel.opened
    ask = TAP.Panel.ask


class LayeredClassic(LayeredBase):
    __test__ = True

    def test_classic_counts_the_seconds_and_draws_no_quip(self):
        self.stub.hold.clear()
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask(p, "Anything?")
            p.until("!!document.querySelector('#ask-step') && document.querySelector('#ask-step').textContent === 'Asking Claude \u00b7 Working 0s'", "the step and the clock at zero")
            p.until("document.querySelector('#ask-step').textContent === 'Asking Claude \u00b7 Working 2s'", "the clock went on", seconds=6)
            self.assertIsNone(p.js("document.querySelector('#ask-quip')"))
            self.stub.hold.set()
            p.until("document.querySelector('#ask-step') === null", "the line went when the answer came")


class LayeredCards(LayeredBase):
    __test__ = True
    classic = False

    def test_cards_keeps_the_quip_and_draws_no_working_line(self):
        self.stub.hold.clear()
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask(p, "Anything?")
            p.until("!!document.querySelector('#ask-quip') && document.querySelector('#ask-quip').textContent !== ''", "a quip while waiting")
            self.assertIsNone(p.js("document.querySelector('#ask-step')"), "Cards draws no working line")
            self.stub.hold.set()
            p.until("document.querySelector('#ask-quip') === null", "the quip went when the answer came")


if __name__ == "__main__":
    unittest.main()
