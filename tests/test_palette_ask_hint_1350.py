"""Row 1350: the quick bar's ask row hint and the order of the groups for a typed word that is not a question.

Run: python3 dev/run_tests.py test_palette_ask_hint_1350
The hint is "Cmd+Enter" on a Mac and "Ctrl+Enter" elsewhere (sendKey() in src/clark/page/src/edit/palette.js, run on the real source, and the drawn row at
1400 and 900); a typed word that is not a question lists Commands, then Pages, then the rest, and the ask row last; with nothing typed the order stays
Pages, Actions, Projects, Commands. Chrome is required: it fails, never skips, without it (set CLARK_CHROME).
"""
import json
import unittest

from test_palette import Base
from test_palette_ask_row_logic import AskRowLogic
from test_server import chrome

MAC = {"platform": "MacIntel"}
MAC_HINTS = {"userAgentData": {"platform": "macOS"}, "platform": "MacIntel"}


class SendKeyPick(AskRowLogic):
    def test_the_word_follows_the_platform(self):
        cases = [MAC, MAC_HINTS, {"platform": "iPhone"}, {"platform": "Win32"}, {"platform": "Linux x86_64"}, {"userAgentData": {"platform": "Windows"}, "platform": "MacIntel"}, {"platform": "Win32 (not a Mac)"},
                 {"userAgentData": {"platform": "macOS"}, "platform": "Win32"}, {}, None]
        got = self.js("return " + json.dumps(cases) + ".map((n) => PAL.sendKey(n));")
        self.assertEqual(got, ["Cmd+Enter", "Cmd+Enter", "Cmd+Enter", "Ctrl+Enter", "Ctrl+Enter", "Ctrl+Enter", "Ctrl+Enter", "Cmd+Enter", "Ctrl+Enter", "Ctrl+Enter"])

    def test_the_row_carries_the_word_and_the_rest_of_the_row_is_unchanged(self):
        got = self.js("const r = PAL.askRow('zzqx'); return [r.more, r.label, r.kind, r.first];")
        self.assertEqual(got, ["Ctrl+Enter", "Ask “zzqx” in ask clark", "ask clark", False], "headless Chrome here reports Linux")


class OnThePage(Base):
    def hints(self, p, q):
        p.find(q)
        return p.js("(function(){var e=document.querySelector('#pal-ask-row'); return [e.querySelector('.pal-more').textContent, [...e.children].map(c => c.className.split(' ')[0])];})()")

    def test_the_hint_reads_ctrl_enter_here_and_cmd_enter_on_a_mac_at_both_widths(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in (1400, 900):
                p.width(w)
                p.show()
                self.assertEqual(self.hints(p, "pilot"), ["Ctrl+Enter", ["pal-kind", "pal-label", "pal-more"]], f"at {w} px")
                p.key("Escape", 0, "Escape", 27)
            p.js("Object.defineProperty(navigator, 'userAgentData', {value: undefined, configurable: true}); Object.defineProperty(navigator, 'platform', {value: 'MacIntel', configurable: true});")
            for w in (1400, 900):
                p.width(w)
                p.show()
                self.assertEqual(self.hints(p, "pilot")[0], "Cmd+Enter", f"at {w} px")
                p.key("Escape", 0, "Escape", 27)

    def test_a_word_that_is_not_a_question_lists_command_page_then_ask_last(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in (1400, 900):
                p.width(w)
                p.show()
                p.find("work")
                kinds = [r[0] for r in p.rows(True)]
                runs = [k for i, k in enumerate(kinds) if i == 0 or k != kinds[i - 1]]
                self.assertEqual(runs[:2], ["Command", "Page"], f"at {w} px: {runs}")
                self.assertEqual(runs[-1], "ask clark", f"at {w} px")
                p.key("Escape", 0, "Escape", 27)

    def test_a_question_stays_first_and_an_empty_bar_keeps_its_order(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for w in (1400, 900):
                p.width(w)
                p.show()
                kinds = [r[0] for r in p.rows(True)]
                self.assertEqual([k for i, k in enumerate(kinds) if i == 0 or k != kinds[i - 1]], ["Page", "Action", "Project", "Command"], f"at {w} px")
                p.find("what is work?")
                self.assertEqual(p.rows(True)[0][0], "ask clark", f"at {w} px")
                p.key("Escape", 0, "Escape", 27)


if __name__ == "__main__":
    unittest.main()
