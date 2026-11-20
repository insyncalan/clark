"""Row 1094: the Ask clark panel shows the 150 office quips while it works, dealt from a shuffled deck.

The words file holds the 150 (a copy of the creaite list, each ending in an ellipsis, none twice). The deal is the real code from
askPanelState.js, run under node: a deck holds every quip once, a pass shows all 150 before any comes round again, and the quip
that ended one pass never opens the next. The wave stops under reduced motion and the screen-reader word stays.
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
CSS = (EDIT / "edit.css").read_text(encoding="utf-8")
PANEL = (EDIT / "AskPanel.jsx").read_text(encoding="utf-8")


def quips():
    return json.loads("[" + ",".join(re.findall(r'^  ("[^\n]+"),$', WORDS[WORDS.index("export const QUIPS"):], re.M)) + "]")


def func(name):
    m = re.search(r"^export (?:function " + name + r"\(.*?^\}|const " + name + r" = .*?;$)", STATE, re.M | re.S)
    assert m, name
    return m.group(0).replace("export ", "", 1)


def run_node(body):
    src = "const QUIPS = " + json.dumps(quips()) + ";\n" + func("quipDeal") + "\n" + func("nextQuip") + "\nlet deck = [], lastQuip = '';\n" + func("drawQuip") + "\n" + body
    out = subprocess.run(["node", "-e", src], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


@unittest.skipUnless(shutil.which("node"), "node is needed")
class QuipDeck(unittest.TestCase):
    def test_150_quips_none_twice_each_with_an_ellipsis(self):
        q = quips()
        self.assertEqual(len(q), 150)
        self.assertEqual(len(set(q)), 150)
        self.assertTrue(all(x.endswith("…") for x in q))
        self.assertIn("Percolating coffee…", q)
        self.assertIn("Circling back…", q)

    def test_a_deck_holds_every_quip_once_and_is_shuffled(self):
        r = run_node("const a = quipDeal(), b = quipDeal(); console.log(JSON.stringify([[...a].sort((x, y) => x - y), a.join() !== b.join()]));")
        self.assertEqual(r[0], list(range(150)))
        self.assertTrue(r[1], "two deals came out in the same order")

    def test_none_comes_round_again_until_all_have_been_shown(self):
        r = run_node("const d = []; let p = ''; const s = []; for (let i = 0; i < 450; i++) { p = nextQuip(d, p); s.push(p); } console.log(JSON.stringify(s));")
        for k in range(3):
            self.assertEqual(len(set(r[k * 150:(k + 1) * 150])), 150, "pass %d repeated a quip" % k)
        self.assertTrue(all(r[i] != r[i + 1] for i in range(449)), "the same quip twice running")

    def test_the_last_of_a_pass_never_opens_the_next(self):
        # rand always 0 fixes the shuffle; hand in the quip that would come up first as the one just shown
        r = run_node("const first = QUIPS[quipDeal(() => 0).pop()]; console.log(JSON.stringify([first, nextQuip([], first, () => 0)]));")
        self.assertNotEqual(r[0], r[1])

    def test_no_repeat_across_questions(self):
        # each "question" draws a few quips, as a wait does; the one deck carries on, so 3 passes of 150 never repeat inside a pass
        r = run_node("const s = []; for (let q = 0; q < 150; q++) { for (let i = 0; i < 3; i++) s.push(drawQuip()); } console.log(JSON.stringify(s));")
        for k in range(3):
            self.assertEqual(len(set(r[k * 150:(k + 1) * 150])), 150, "pass %d repeated a quip" % k)
        self.assertTrue(all(r[i] != r[i + 1] for i in range(449)), "the same quip twice running")

    def test_no_quip_names_a_day_or_uses_office_jargon(self):
        bad = re.compile(r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|RACI|RAG\b|synerg|leverag|stakeholder|ideat|baselin|sign-off|steering|quorum", re.I)
        self.assertEqual([x for x in quips() if bad.search(x)], [])

    def test_the_panel_deals_from_a_deck_with_5_to_10_seconds(self):
        self.assertIn("drawQuip()", PANEL)
        self.assertNotIn("const deck", PANEL, "the deck is not made per question")
        self.assertIn("5000 + Math.floor(rand() * 5001)", STATE)


class Look(unittest.TestCase):
    def test_dots_wave_and_stop_under_reduced_motion(self):
        self.assertRegex(CSS, r"\.ask-dots i \{[^}]*animation: ask-dot ")
        self.assertIn("@keyframes ask-dot", CSS)
        self.assertRegex(CSS, r"prefers-reduced-motion: reduce\)[^\n]*\.ask-dots i \{ animation: none;")

    def test_the_screen_reader_word_stays_and_the_quip_is_hidden_from_it(self):
        self.assertIn('export const WORKING = "Working";', WORDS)
        self.assertIn("{busy ? W.WORKING :", PANEL)
        self.assertRegex(PANEL, r'id="ask-quip" aria-hidden="true"')


if __name__ == "__main__":
    unittest.main()
