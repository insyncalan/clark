"""Row 1278: markdown the page shows is drawn formatted, never as raw text. The places, found by reading the page source (git grep):
  1. Settings > Version and updates, the review panel's release notes (edit/Update.jsx, panel.view.notes)         -> formatted here
  2. the same card, the newest release's notes under "What is new in this version" (edit/Update.jsx, f.notes)    -> formatted here
  3. ask clark answers (edit/AskPanel.jsx, FormattedAnswer, row 1217)                                              -> already formatted
  4. Help text (help/helpText.jsx Md: **bold**, `code`, keys, links; the strings hold no heading or bullet marks)  -> checked below
  Peek and Prep notes are plain typed text by design (ruled, plan comment 17-11) and are not markdown places.
The renderer is the one ask clark uses (edit/askFormat.js, edit/AskFormat.jsx): text nodes only, no HTML read. Copy keeps the original markdown.
Classic only: Cards is frozen (ruling 19-11); with no Classic layer the notes stay the raw <pre> they are on main (pinned in CardsUnchanged below).

Run: python3 dev/run_tests.py test_markdown_notes_1278
"""
import json
import re
import unittest

from _paths import SRC
from test_update_page import REVIEW, STATUS, InBrowser, OK, lit
from test_update_fetch_page_1327 import AVAIL, BASE

NOTES = ("## What is changed\n\n### Dashboard\n\n- First **bold** point\n- Second point with `code`\n\n#### Small heading\n\n"
         "A line with <script>window.hacked = 1</script> and <img src=\"http://example.invalid/x.png\"> in it.\n"
         "A second line.\n\n1. one\n2. two\n\n" + "x" * 300 + "\n")
EDIT_CSS = SRC / "clark" / "page" / "src" / "edit" / "edit.css"
MARKERS = re.compile(r"(^|\n)\s*(#{1,6} |[-*+] |\d+[.)] )|\*\*|```")


class Notes(InBrowser):
    def prep(self, width, latest=False, notes=NOTES, classic=True):
        self.load(width=width)
        if classic:
            self.js("(() => { const t = document.createElement('div'); t.id = 'theme'; document.body.appendChild(t); })()")      # the Classic layer: classicTheme() is true
        self.replies(review=OK({"ok": True, "review_id": "r1", "review": {**REVIEW, "notes": notes, "notes_text": notes}}),
                     status=OK({**BASE, "latest": {**AVAIL, "notes": NOTES}, "fetch": {"state": "idle"}}) if latest else OK(STATUS))

    def styled(self):
        self.js("(() => { const s = document.createElement('style'); s.textContent = " + lit(EDIT_CSS.read_text(encoding="utf-8")) + "; document.head.appendChild(s); })()")

    def check_formatted(self, box):
        shown = self.text(box)
        self.assertIsNone(MARKERS.search(shown), f"a markdown mark shows as text: {shown[:120]!r}")
        for want in ("What is changed", "Dashboard", "First bold point", "Second point with code", "one", "two"):
            self.assertIn(want, shown)
        self.assertEqual(self.val(f"[...document.querySelectorAll({lit(box + ' h3, ' + box + ' h4, ' + box + ' h5')})].map(h => h.tagName)"), ["H4", "H5", "H5"])
        self.assertEqual(self.val(f"document.querySelectorAll({lit(box + ' ul > li')}).length"), 2)
        self.assertEqual(self.val(f"document.querySelectorAll({lit(box + ' ol > li')}).length"), 2)
        self.assertEqual(self.val(f"document.querySelector({lit(box + ' strong')}).textContent"), "bold")
        self.assertEqual(self.val(f"document.querySelector({lit(box + ' li code')}).textContent"), "code")

    def check_safe(self, box):
        self.assertIn("<script>window.hacked = 1</script>", self.text(box), "the tag stays as the text it is")
        self.assertIn('<img src="http://example.invalid/x.png">', self.text(box))
        self.assertEqual(self.val(f"document.querySelectorAll({lit(box + ' script, ' + box + ' img')}).length"), 0)
        self.assertIsNone(self.val("window.hacked || null"))

    def check_fits(self, box):
        self.assertTrue(self.val("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), "no sideways scroll")
        self.assertTrue(self.val(f"(b => b.scrollWidth <= b.clientWidth)(document.querySelector({lit(box)}))"), "nothing clipped at the right of the notes box")
        self.assertEqual(self.val(f"document.querySelector({lit(box)}).scrollTop"), 0, "the box starts at its first line")
        self.assertTrue(self.val(f"(b => b.firstElementChild.getBoundingClientRect().top >= b.getBoundingClientRect().top)(document.querySelector({lit(box)}))"),
                        "the first line is not cut off at the top")
        self.assertTrue(self.val(f"[...document.querySelectorAll({lit(box + ' *')})].every(e => e.getBoundingClientRect().right <= document.querySelector({lit(box)}).getBoundingClientRect().right + 1)"))

    def test_the_review_panel_notes_are_formatted_and_copy_keeps_the_markdown(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                self.prep(width)
                self.styled()
                self.mount()
                self.click("[data-review]")
                self.check_formatted("#update-panel #update-notes")
                self.check_safe("#update-panel #update-notes")
                self.check_fits("#update-panel #update-notes")
                self.click("[data-copy]")
                self.assertEqual(self.val("T.copied"), [NOTES])

    def test_the_newest_release_notes_are_formatted(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                self.prep(width, latest=True)
                self.styled()
                self.mount()
                self.js("document.querySelector('#update-avail details').open = true")
                self.check_formatted("#update-avail #update-notes")
                self.check_safe("#update-avail #update-notes")
                self.check_fits("#update-avail #update-notes")

    def test_plain_one_line_notes_and_the_no_notes_line_still_read(self):
        self.prep(1400)
        self.replies(review=OK({"ok": True, "review_id": "r1", "review": {**REVIEW, "notes": "", "notes_text": "No release notes."}}))
        self.mount()
        self.click("[data-review]")
        self.assertEqual(self.text("#update-notes"), "No release notes.")
        self.assertFalse(self.present("[data-copy]"))


class CardsUnchanged(InBrowser):
    """The default Cards look (no Classic theme layer in the page) keeps the raw <pre> notes of main in both places."""

    prep = Notes.prep

    def check_cards(self, box):
        self.assertFalse(self.js("!!document.getElementById('theme')"), "this is Cards: no Classic layer")
        self.assertTrue(self.present(box.replace("#update-notes", "pre#update-notes")))
        self.assertEqual(self.val(f"document.querySelectorAll({lit(box + ' h3, ' + box + ' h4, ' + box + ' h5, ' + box + ' ul, ' + box + ' strong')}).length"), 0)
        self.assertIn("## What is changed", self.text(box), "the marks show as typed, as on main")

    def test_cards_review_panel_notes_stay_raw_at_1400_and_900(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                self.prep(width, classic=False)
                self.mount()
                self.click("[data-review]")
                self.check_cards("#update-panel #update-notes")

    def test_cards_newest_release_notes_stay_raw_at_1400_and_900(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                self.prep(width, latest=True, classic=False)
                self.mount()
                self.js("document.querySelector('#update-avail details').open = true")
                self.check_cards("#update-avail #update-notes")


class HelpHasNoUnrenderedMarks(unittest.TestCase):
    def test_no_help_string_holds_a_heading_or_bullet_mark_the_help_renderer_does_not_draw(self):
        content = json.loads((SRC / "clark" / "page" / "src" / "help" / "helpContent.json").read_text(encoding="utf-8"))
        strings = []

        def walk(x):
            if isinstance(x, str):
                strings.append(x)
            elif isinstance(x, dict):
                for v in x.values():
                    walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)
        walk(content)
        self.assertGreater(len(strings), 50)
        for s in strings:
            self.assertIsNone(re.search(r"(^|\n)\s*(#{1,6} |[-*+] |\d+[.)] )|```|\[[^\]]+\]\((?!#|go:)", s), s)


if __name__ == "__main__":
    unittest.main()
