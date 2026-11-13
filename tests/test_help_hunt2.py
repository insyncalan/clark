"""Hunt 2: Help text that did not match the code (top bar, ask suggestions, published page tabs, Sneak peek confirm, PDF asking,
Settings cards, brand kit limits and folder, Backups count).

Run: python3 dev/run_tests.py test_help_hunt2
No browser: it reads src/clark/page/src/help/helpContent.json and a few source files as text.
"""
import json
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
HELP = json.loads((ROOT / "src/clark/page/src/help/helpContent.json").read_text(encoding="utf-8"))


def walk(x):
    if isinstance(x, dict):
        yield x
        for v in x.values():
            yield from walk(v)
    elif isinstance(x, list):
        for v in x:
            yield from walk(v)


def strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, dict):
        for v in x.values():
            yield from strings(v)
    elif isinstance(x, list):
        for v in x:
            yield from strings(v)


def entry(title):
    found = [e for e in walk(HELP) if e.get("t") == title and "b" in e]
    assert len(found) == 1, (title, len(found))
    return json.dumps(found[0], ensure_ascii=False)


def guide(gid):
    found = [e for e in walk(HELP) if e.get("id") == gid and "steps" in e]
    assert len(found) == 1, gid
    return json.dumps(found[0], ensure_ascii=False)


class HelpHunt2(unittest.TestCase):
    def test_top_bar_names_every_tab(self):
        text = entry("The top bar")
        self.assertNotIn("three screens", text)
        self.assertIn("Use cases", text)

    def test_published_page_does_not_claim_three_tabs(self):
        text = entry("The published client page")
        self.assertNotIn("Three tabs", text)
        self.assertIn("Use cases", text)
        self.assertIn("Gantt", text)

    def test_sneak_peek_says_some_changes_ask_first(self):
        text = entry("Sneak peek")
        self.assertIn("This change needs your OK", text)
        self.assertIn("Confirm and apply", text)
        self.assertIn("**Make the change**, **Confirm and apply** or", text)
        self.assertIn("move it back out of done", text)
        self.assertIn("[[Mod+Enter]]", text)

    def test_help_says_pdf_files_are_read_and_the_note_does_not_say_unsupported(self):
        text = entry("Settings")
        self.assertNotIn("PDF files are not read yet", text)
        self.assertIn("Word, PDF, text", text)
        service = (ROOT / "src/clark/ask_service.py").read_text(encoding="utf-8")
        self.assertNotIn("PDF is not supported yet", service)

    def test_settings_help_has_a_card_for_every_named_settings_card(self):
        views = (ROOT / "src/clark/page/src/components/Views.jsx").read_text(encoding="utf-8")
        block = re.search(r"const CARDS = \[(.*?)\];", views, re.S).group(1)
        names = [n for n in re.findall(r'\["\w+", "([^"]*)", "[\w-]+"\]', block) if n]
        self.assertIn("Asking", names)
        ctx = next(c for c in walk(HELP) if c.get("page") == "settings")
        titles = [k["title"] for k in ctx["cards"]]
        for n in names:
            self.assertIn(n, titles)

    def test_brand_kit_guide_gives_the_stricter_file_limits(self):
        from clark import brands, excel_picture
        text = guide("the-brand-kit-guide")
        self.assertEqual(brands.TOKENS_CAP, 256 * 1024)
        self.assertEqual(excel_picture.MAX_BYTES, 1024 * 1024)
        self.assertEqual(excel_picture.MAX_PIXELS, 2000)
        self.assertIn("at most 256 KB", text)
        self.assertIn("at most 1 MB and 2000 pixels each way", text)

    def test_brand_kit_guide_says_the_files_sit_in_one_folder_named_after_the_id(self):
        text = guide("the-brand-kit-guide")
        self.assertIn("one folder, named with the brand", text)
        self.assertIn("must match the folder name", text)

    def test_backups_text_says_what_the_number_counts(self):
        from clark import backup, settings
        self.assertEqual(backup.FLOOR, {"restore": 2, "migrate": 3})
        self.assertEqual(backup.FAMILY["changes"], backup.FAMILY["import"])
        for text in (settings.BACKUPS_KEPT_HELP, guide("back-up-and-restore-your-data")):
            self.assertIn("share one count", text)
            self.assertIn("at least 2", text)
            self.assertIn("at least 3", text)
