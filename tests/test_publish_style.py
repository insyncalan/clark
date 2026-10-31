"""#45: the published file carries the report's section style (publish.section_style, add_glance, data_block; guarded: the publish module).

Run: python3 dev/run_tests.py test_publish_style
The style is one of slim, roomy, grey or card; anything else is replaced by slim. All rows are fictional.
"""
import json
import re
import unittest
from pathlib import Path

from clark import publish
from test_glance import ON, RULES, data, sections


def inputs(**more):
    d = data()
    return {"data": d, "hidden": [], "sections": sections(), "label_rules": RULES, "as_at": ON, "glance_tiles": [], **more}


def block(i):
    published = publish.add_glance(publish.select(i), i)
    text = publish.data_block(published, ON)
    return json.loads(re.search(r">(.*)</script>", text, re.S).group(1)), text


class Style(unittest.TestCase):
    def test_the_four_styles_are_carried_next_to_as_at(self):
        self.assertEqual(publish.STYLES, ("slim", "roomy", "grey", "card"))
        for name in publish.STYLES:
            got, text = block(inputs(section_style=name))
            self.assertEqual((got["style"], got["as_at"]), (name, ON))
            self.assertLess(text.index('"as_at"'), text.index('"style"'), "sorted keys: as_at, data, sections, style, tabs, v")

    def test_nothing_stored_gives_slim(self):
        self.assertEqual(block(inputs())[0]["style"], "slim")

    def test_anything_else_is_replaced_by_slim(self):
        for bad in ("", "Slim", "wide", "slim ", "card\n", None, 3, True, ["card"], {"a": 1}, "<script>"):
            self.assertEqual(block(inputs(section_style=bad))[0]["style"], "slim", repr(bad))

    def test_data_block_never_carries_an_unknown_word_even_when_published_was_changed_by_hand(self):
        published = publish.add_glance(publish.select(inputs()), inputs())
        for bad in ("wide", None, 3, "<b>"):
            published["style"] = bad
            got = json.loads(re.search(r">(.*)</script>", publish.data_block(published, ON), re.S).group(1))
            self.assertEqual(got["style"], "slim")

    def test_the_style_is_a_word_the_page_knows(self):
        page = (Path(publish.__file__).parent / "page" / "src" / "stores" / "style.js").read_text(encoding="utf-8")
        self.assertIn('export const IDS = ["slim", "roomy", "grey", "card"];', page)


if __name__ == "__main__":
    unittest.main()
