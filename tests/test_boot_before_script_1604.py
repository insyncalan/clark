"""Row 1604: the token's data block is in the document BEFORE the page's inline script. A slow start used to run the script first,
read an empty token, and the first calls were refused. The live page, the placeholder and the dev copy are all checked."""
import os
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from clark import page, server as sv

BOOT = '<script type="application/json" id="clark-boot">'


def first_code_script(html):
    """Where the first script the browser would run starts (a script with a data type is not run)."""
    for m in re.finditer(r"<script(?P<attrs>[^>]*)>", html):
        if "application/json" not in m.group("attrs"):
            return m.start()
    return -1


class BootBeforeScript(unittest.TestCase):
    def check(self, html):
        at = html.find(BOOT)
        self.assertGreater(at, 0, "the boot block is in the page")
        self.assertEqual(html.count(BOOT), 1)
        script = first_code_script(html)
        self.assertGreater(script, 0, "the page has a script")
        self.assertLess(at, script, "the boot block comes before the first script that runs")

    def test_the_live_page(self):
        self.check(sv.with_boot(page.page_html()))

    def test_the_placeholder(self):
        self.check(sv.with_boot(sv.PLACEHOLDER))

    def test_the_dev_copy(self):
        with mock.patch.dict(os.environ, {"CLARK_DEV": "1"}):
            self.check(sv.with_boot(page.page_html()))

    def test_a_script_text_that_says_body_does_not_move_it(self):
        html = '<html><body class="a"><p>x</p><script>var s = "</body><body>";</script></body></html>'
        self.check(sv.with_boot(html))
        self.assertTrue(sv.with_boot(html).startswith('<html><body class="a">' + BOOT))

    def test_no_body_tag_still_gets_the_block(self):
        self.assertIn(BOOT, sv.with_boot("<p>x</p>"))


if __name__ == "__main__":
    unittest.main()
