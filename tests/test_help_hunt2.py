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

    def test_ask_suggestions_are_not_one_fixed_list(self):
        text = entry("ask clark")
        self.assertIn("follow the page that is open", text)
        words = (ROOT / "src/clark/page/src/edit/askWords.js").read_text(encoding="utf-8")
        general = re.search(r"export const SUGGESTIONS = \[(.*?)\];", words, re.S).group(1)
        item = next(i for i in strings(HELP) if i.startswith("The suggestions sit in one row"))
        for quoted in re.findall(r"\*\*(.+?)\*\*", item):
            self.assertIn(f'"{quoted}"', general, quoted)
