"""Row 1195: the eye on a work item row says its ruled words in the screen reader label and the tooltip, and the ruled toast after a toggle, and a short
tooltip (logic/eyeWords.js). The two screens that draw the eye (the dashboard's item rows and the Work items table) use it, not words of their own.

Run: python3 dev/run_tests.py test_eye_words_node
Quick tier: no browser. Bundled by the pinned esbuild and run in node (skipped when node is not on the machine).
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

ENTRY = ROOT / "tests" / "fixtures" / "eyewords_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}


def bundle():
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "ew.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=EW", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    return _BUNDLE["code"]


def words(on, row):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(bundle() + ";\nconsole.log(JSON.stringify(EW.eyeWords(%s, %s)));" % (json.dumps(on), json.dumps(row)), encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


class EyeWords(unittest.TestCase):
    def test_on_the_page_offers_to_take_it_off(self):
        self.assertEqual(words(True, {"id": "ABC-A-001", "title": "Send the plan"}),
                         {"label": "Take ABC-A-001 Send the plan off the page", "title": "Take off the page", "said": "ABC-A-001 is off the page."})

    def test_off_the_page_offers_to_put_it_on(self):
        self.assertEqual(words(False, {"id": "ABC-A-001", "title": "Send the plan"}),
                         {"label": "Put ABC-A-001 Send the plan on the page", "title": "Put on the page", "said": "ABC-A-001 is on the page."})

    def test_an_empty_title_means_the_id_alone(self):
        for title in ("", "   ", None):
            row = {"id": "ABC-R-002", "title": title}
            self.assertEqual(words(True, row)["label"], "Take ABC-R-002 off the page")
            self.assertEqual(words(False, row)["label"], "Put ABC-R-002 on the page")
        self.assertEqual(words(True, {"id": "ABC-R-002"})["label"], "Take ABC-R-002 off the page")

    def test_the_toast_after_a_toggle_says_the_id_and_where_the_item_is_now(self):
        self.assertEqual(words(True, {"id": "X-1", "title": "T"})["said"], "X-1 is off the page.")
        self.assertEqual(words(False, {"id": "X-1", "title": "T"})["said"], "X-1 is on the page.")


class BothScreensUseIt(unittest.TestCase):
    def read(self, *parts):
        return (PAGE_SRC.joinpath(*parts)).read_text(encoding="utf-8")

    def test_the_work_items_table_eye_uses_the_words_for_label_title_and_announcement(self):
        eye = self.read("edit", "cells", "Eye.jsx")
        self.assertIn("eyeWords(on, row)", eye)
        self.assertIn("aria-label={w.label} title={w.title}", eye)
        self.assertEqual(len(re.findall(r"\bw\.said\b", eye)), 3, "all three changes announce the same string")
        for old in ("hidden from the client.", "shown to the client.", "Select to hide", "Internal only"):
            self.assertNotIn(old, eye)

    def test_the_dashboard_row_eye_uses_the_words_for_label_title_and_announcement(self):
        rows = self.read("edit", "ItemRowsEdit.jsx")
        self.assertIn("aria-label={w.label} title={w.title}", rows)
        self.assertIn("eyeWords(true, row)", rows)
        self.assertIn("w.said", rows)
        self.assertNotIn("is off the page.", rows)
        self.assertNotIn('title="Take off the page"', rows)


if __name__ == "__main__":
    unittest.main()
