"""Row 1205 Help words, items 9, 10, 14, 15 and 16: each ruled sentence is in the Help text, the old wording is gone,
and the code facts the sentences state are in the source."""
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "clark"
PAGE = SRC / "page"


def read(p):
    return pathlib.Path(p).read_text(encoding="utf-8")


HELP = read(PAGE / "src" / "help" / "helpContent.json")
json.loads(HELP)


class HelpWordsB(unittest.TestCase):
    def test_new_sentences(self):
        for s in (
            "a mark per milestone with its name and date below it; a name that has no room shows when you point at the mark or tab to it.",
            "a dashed red ring on its expected date, joined by a dashed line to its agreed date",
            "and again as “Expected”, in a dashed red outline.",
            "one line says that the backup was restored; when it put back over data that was there, the line adds that your data from before is kept in case you need it.",
            "The words you typed in the box show as their own Search: chip among the filters.",
        ):
            self.assertEqual(HELP.count(s), 1, s)
        self.assertEqual(HELP.count("Open** (not on the project already open)"), 2)
        self.assertEqual(HELP.count("Open (not on the project already open)"), 0)   # the Settings card line stays short: test_help_guides allows under 115 characters

    def test_item_3_chips(self):
        new = ("the chips **Status**, **Priority** (a risk or issue says **Rating**), **Owner** and **Due**, "
               "each in colour.")
        self.assertEqual(HELP.count(new), 2)
        self.assertEqual(HELP.count("**The title**, then " + new), 1)
        self.assertEqual(HELP.count("Under the title are " + new + " In Edit, click **Status** to choose"), 1)
        for old in ("each with its icon in colour", "In Edit, under the title are **Status**", "red when late",
                    "amber when due within a week", "the state\u2019s colour"):
            self.assertNotIn(old, HELP, old)
        pk = read(PAGE / "src" / "components" / "Peek.jsx")
        self.assertIn('"Rating" : "Priority"', pk)
        self.assertIn('row.kind === "decision" ? "Decider" : "Owner"', pk)

    def test_old_sentences_gone(self):
        for s in ("a faint mark on its expected date", "again, faintly, as", "restored and that your data from before is kept",
                  "with its name and date below.", "Each project has **Open**, **Edit**"):
            self.assertNotIn(s, HELP, s)

    def test_code_facts(self):
        tl = read(PAGE / "src" / "components" / "MsTimeline.jsx")
        self.assertIn("title={say}", tl)
        self.assertIn('class="mv-ghost"', tl)
        css = read(PAGE / "shell.css")
        self.assertIn(".mv-ghost {", css)
        # a name with no room: the mark (a button when the page can open it) shows the name on hover and on keyboard focus
        self.assertIn(".mv-mk[data-hid]:hover::after, .mv-mk[data-hid]:focus-visible::after { content: attr(data-hid)", css)
        self.assertIn("type: \"button\", onClick: () => open(r.id)", tl)
        self.assertIn("border: 2px dashed var(--status-red)", css)
        self.assertIn(".cal-ms.ghost { background: transparent; border: 1px dashed var(--status-red)", css)
        safety = read(SRC / "safety.py")
        self.assertIn("Your data from before is kept in case you need it.", safety)
        self.assertIn('"restored_empty": "Restored the backup from {date}."', safety)
        pr = read(PAGE / "src" / "pages" / "Projects.jsx") if (PAGE / "src" / "pages" / "Projects.jsx").exists() else "".join(
            read(p) for p in PAGE.rglob("Projects.jsx"))
        self.assertIn("r.code !== openCode.value", pr)
        wi = read(PAGE / "src" / "components" / "WorkItems.jsx")
        self.assertIn('data-chip="search"', wi)
        self.assertIn("`Search: ${query.value.trim()}`", wi)


if __name__ == "__main__":
    unittest.main()
