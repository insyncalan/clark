"""Row 1205, follow-up: the two Import Help lines that did not match the box.

Run: python3 dev/run_tests.py test_help_import_1205
The What to import line says which sheets start ticked (the ones ticked last time, every sheet the first time) and the Check the import line says
that at most 300 changes are listed and a line under the list counts the rest. The 300 is read from the real box. Chrome is required.
"""
import json
import unittest

from _paths import SRC
from test_import_box_keys import ImportBox as _Box

HELP = SRC / "clark" / "page" / "src" / "help" / "helpContent.json"
WIDTHS = (1400, 900)


def every_string(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from every_string(v)
    elif isinstance(node, list):
        for v in node:
            yield from every_string(v)


TEXT = "\n".join(every_string(json.loads(HELP.read_text(encoding="utf-8"))))


class HelpSaysIt(unittest.TestCase):
    def test_the_two_lines_say_what_the_box_does_and_the_old_words_are_gone(self):
        self.assertEqual(TEXT.count("the Gantt sheet after the others. The sheets you ticked last time are ticked again (every sheet, the first time). Tick"), 1)
        self.assertEqual(TEXT.count("with the changes listed, up to 300 of them; a line under the list says how many more there are."), 1)
        for old in ("They all start ticked", "with the first few"):
            self.assertNotIn(old, TEXT, old)


class ThreeHundredListed(_Box):
    def test_301_changes_list_300_and_a_line_says_how_many_more(self):
        its = [{"n": n, "kind": "new", "table": "actions", "text": f"Row {n}", "default": True} for n in range(1, 302)]
        for width in WIDTHS:
            with self.subTest(width=width):
                self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.to_plan(its)
                self.until("document.querySelectorAll('.st-act').length === 300", "300 changes drew")
                self.assertEqual(self.js("document.querySelectorAll('.st-act').length"), 300)
                self.assertTrue(self.js("document.querySelector('#import-more').textContent").startswith("and 1 more"))


for _n in [n for n in dir(_Box) if n.startswith("test_") and n not in vars(ThreeHundredListed)]:
    setattr(ThreeHundredListed, _n, None)
del _Box


if __name__ == "__main__":
    unittest.main()
