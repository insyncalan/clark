"""#721: what Help says about ask clark and Sneak peek is what the page does. Reads the whole helpContent.json (held entries too)."""
import json
import re
import unittest

from _help_shown import RAW
from _paths import ROOT

PAGE = ROOT / "src" / "clark" / "page" / "src"
BUTTON = PAGE / "edit" / "AskButton.jsx"
TOP_BAR_ASK_BUTTON = BUTTON.exists() and "AskButton" in (PAGE / "components" / "TopBar.jsx").read_text(encoding="utf-8")
TEXT = json.dumps(RAW, ensure_ascii=False)


def entry(kind, id_):
    seq = RAW["howto"]["tasks"] if kind == "howto" else RAW["reference"]["sections"]
    return json.dumps(next(x for x in seq if x["id"] == id_), ensure_ascii=False)


def strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, list):
        for x in o:
            yield from strings(x)
    elif isinstance(o, dict):
        for k, v in o.items():
            if k not in ("id", "g", "go", "ic"):
                yield from strings(v)


SNEAK = "\n".join([entry("howto", "change-an-item-in-words"), entry("reference", "sneak-peek")])
ASK = "\n".join([entry("howto", "check-the-report"), entry("reference", "ask-clark")])
ALL = list(strings(RAW))


class HelpAskAndSneakPeek(unittest.TestCase):
    def test_mod_j_is_named_because_the_page_binds_it(self):
        # edit/askPanelState.js installAskKeys opens the panel on Ctrl or Cmd + J; the bar button is a separate question
        self.assertIn("[[Mod+J]]", TEXT)

    def test_the_top_bar_ask_button_is_described_as_the_page_has_it(self):
        """The Help names a top-bar ask button only if the page has one, by the label and picture it really has (edit/AskButton.jsx)."""
        about_bar = [s for s in ALL if re.search(r"(?i)top bar", s) and re.search(r"(?i)ask clark", s)]
        if not TOP_BAR_ASK_BUTTON:
            self.assertEqual(about_bar, [])
            return
        code = BUTTON.read_text(encoding="utf-8")
        label = re.search(r'aria-label="([^"]+)"', code).group(1)
        self.assertEqual(label, "ask clark")
        self.assertIn("<svg", code)                       # the button draws a speech bubble (a rounded outline with a tail)
        self.assertIn("M4 5.5A2.5 2.5 0 0 1 6.5 3h7", code)
        self.assertIn("<kbd", code)                       # and shows its key, "/"
        one = "ask: the speech-bubble button in the top bar, or press [[/]]"
        self.assertIn(one, RAW["start"]["text"]["keyline"])        # the one place the Help names the button
        self.assertEqual([s for s in ALL if "top bar" in s and re.search(r"(?i)\bask\b", s) and one not in s], [],
                         "no other Help text carries top-bar ask words")
        self.assertNotRegex(" ".join(ALL), r"(?i)ask button|top-bar button|ask icon")

    def test_sneak_peek_says_what_it_can_change_and_that_it_is_edit_only(self):
        self.assertNotRegex(SNEAK, r"(?i)progress 40|For a milestone|forecast 12")
        e = entry("reference", "sneak-peek")
        self.assertIn("a work item", e)
        self.assertIn("a milestone or a use case", e)
        self.assertIn("in Edit only", e)
        self.assertIn("Not its owner or its agreed date", e)

    def test_no_up_key_recall(self):
        self.assertNotRegex(SNEAK + json.dumps(RAW["reference"]["keys"]), r"(?i)last instruction|\[\[Up\]\] brings back|empty (Sneak peek )?box|Sneak peek box")
        self.assertNotIn("[[Up]]", [k for k, d in RAW["reference"]["keys"] if "Sneak" in d])

    def test_no_fields_the_code_does_not_read(self):
        for bad in ("show to client", "hide from client", "rename to", "use case 3.1", "update: …", "red · amber · green", "next week"):
            self.assertNotIn(bad, SNEAK)

    def test_ask_clark_is_not_off_until_switched_on(self):
        self.assertNotRegex(ASK + json.dumps(RAW["start"]) + json.dumps(RAW["reference"]["keys"]), r"(?i)off until|until you (switch|turn) (it )?on|Turn on asking|switch(ed)? on (in|from) Settings")
        ref = entry("reference", "ask-clark")
        self.assertIn("on from the first start", ref)
        self.assertIn("**Turn off asking**", ref)
        settings = (PAGE / "edit" / "AskSettings.jsx").read_text(encoding="utf-8")
        for name in ("Turn off asking", "Folders asking may read", ">Asking<"):
            self.assertIn(name, settings)

    def test_ask_clark_changes_work_items_and_milestones_not_use_cases(self):
        self.assertNotRegex(ASK, r"(?i)change[^\"]{0,40}use cases?\b(?! need)")
        self.assertIn("never archives or restores anything", entry("reference", "ask-clark"))

    def test_panel_buttons_and_pills_are_the_pages(self):
        words = (PAGE / "edit" / "askWords.js").read_text(encoding="utf-8")
        pills = re.findall(r'^  "(.+?)",$', re.search(r"SUGGESTIONS = \[(.*?)\];", words, re.S).group(1), re.M)
        self.assertEqual(len(pills), 6)
        for pill in pills:
            self.assertIn(f"**{pill}**", entry("reference", "ask-clark"))
        self.assertIn('NEW_CHAT = "New chat"', words)
        self.assertIn('CLOSE = "Close"', words)
        self.assertNotRegex(ASK, r"\*\*\+\*\*|\*\*×\*\*|What’s overdue|\*\*Next milestone|\*\*Use cases\*\*|Item IDs in an answer open|IDs open the item")
        self.assertIn("**New chat**", ASK)
        self.assertIn("**Close**", ASK)
        self.assertNotRegex(ASK, r"double-click puts it back")

    def test_slash_text_matches_the_key_code(self):
        row = next(d for k, d in RAW["reference"]["keys"] if k == "[[/]]")
        self.assertIn("no peek, menu or box is open", row)
        self.assertNotRegex(row, r"(?i)ask clark[^.]*Single-key|Like the letter keys")
        self.assertNotIn("Single-key", row)      # the switch is named only in the V and E rows (test_single_keys); the Personal › Keys line says "/" and "?" follow it too
        self.assertIn("singleKeys.value", (PAGE / "edit" / "askPanelState.js").read_text(encoding="utf-8"))   # "/" for ask follows that switch

    def test_double_slash_is_in_the_peek_code(self):
        self.assertRegex((PAGE / "components" / "Peek.jsx").read_text(encoding="utf-8"), r'e\.key === "/".*Words')
        self.assertIn("[[/]] [[/]]", TEXT)


def ask_clark_rows(o):
    if isinstance(o, list):
        if len(o) >= 2 and o[0] == "ask clark" and all(isinstance(x, str) for x in o):
            yield o
        for x in o:
            yield from ask_clark_rows(x)
    elif isinstance(o, dict):
        for v in o.values():
            yield from ask_clark_rows(v)


class AskClarkRowNamesBothKeys(unittest.TestCase):
    def test_the_ask_clark_row_names_slash_and_mod_j_and_the_palette(self):
        rows = list(ask_clark_rows(RAW))
        self.assertTrue(rows, "no ask clark row found")
        for row in rows:
            for key in ("[[/]]", "[[Mod+J]]", "[[Mod+K]]"):
                self.assertIn(key, row[1])


if __name__ == "__main__":
    unittest.main()
