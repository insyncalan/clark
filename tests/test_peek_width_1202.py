"""Item 1202: the peek is 640 px wide by default and can be dragged no wider than the window minus 32 px (420 px at least).

Run: python3 dev/run_tests.py test_peek_width_1202

Part 1 is the pure rule (page/src/peek/width.js), run in node when node is on the machine. Part 2 reads the source: the peek's state
module takes the rule from that file. No new words: the test reads no text.
"""
import json
import subprocess
import unittest

from _paths import ROOT
from test_publish_style import need_node  # noqa: E402

SRC = ROOT / "src" / "clark" / "page" / "src"


class WidthRule(unittest.TestCase):
    def run_js(self, body):
        node = need_node(self)
        code = f'import * as W from "{(SRC / "peek" / "width.js").as_uri()}"; {body}'
        done = subprocess.run([node, "--input-type=module", "-e", code], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_the_default_is_640_and_the_minimum_420(self):
        self.assertEqual(self.run_js("console.log(JSON.stringify([W.DEFAULT, W.MIN, W.GAP]))"), [640, 420, 32])

    def test_the_most_is_the_window_minus_32(self):
        out = self.run_js("console.log(JSON.stringify([W.limit(5000, 1400), W.limit(1400, 1400), W.limit(1368, 1400), W.limit(1000, 1000), W.limit(900, 1000)]))")
        self.assertEqual(out, [1368, 1368, 1368, 968, 900])

    def test_the_least_is_420_even_in_a_small_window(self):
        out = self.run_js("console.log(JSON.stringify([W.limit(100, 1400), W.limit(0, 1400), W.limit(700, 440), W.limit(300, 300)]))")
        self.assertEqual(out, [420, 420, 420, 420])

    def test_a_width_that_is_not_a_number_gives_the_default(self):
        out = self.run_js("console.log(JSON.stringify([W.limit(NaN, 1400), W.limit('x', 1400), W.limit(undefined, 1400)]))")
        self.assertEqual(out, [640, 640, 640])

    def test_the_default_fits_a_window_from_1000_px(self):
        self.assertEqual(self.run_js("console.log(JSON.stringify(W.limit(W.DEFAULT, 1000)))"), 640)

    def test_the_state_module_takes_the_rule_from_that_file(self):
        text = (SRC / "stores" / "peekState.js").read_text(encoding="utf-8")
        self.assertIn('from "../peek/width.js"', text)
        self.assertNotIn("= 560", text)


if __name__ == "__main__":
    unittest.main()
