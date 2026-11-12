"""Row 1074: Help says one more thing, in the sentence the owner approved (ruling 11, option A).

Run: python3 dev/run_tests.py test_help_r11_1074
Quick tier: reads helpContent.json only; no page layout changes, so there is nothing to see at 1400 or 900, light or dark.
"""
import json
import unittest

from _help_shown import RAW

SENTENCE = 'The menus for status, priority, due date, owner, workstream and milestone show a small picture before each choice.'
ENTRY = next(e for e in RAW['reference']['sections'] if e["id"] == 'work-items')


def strings(x):
    if isinstance(x, str):
        yield x
    elif isinstance(x, (list, tuple)):
        for i in x:
            yield from strings(i)
    elif isinstance(x, dict):
        for i in x.values():
            yield from strings(i)


class HelpSaysIt(unittest.TestCase):
    def test_the_entry_holds_the_sentence_once(self):
        text = "\n".join(strings(ENTRY))
        self.assertEqual(text.count(SENTENCE), 1)

    def test_the_sentence_is_in_no_other_entry(self):
        total = "\n".join(strings(RAW))
        self.assertEqual(total.count(SENTENCE), 1)

    def test_the_source_is_still_json(self):
        self.assertIsInstance(json.dumps(RAW), str)


if __name__ == "__main__":
    unittest.main()
