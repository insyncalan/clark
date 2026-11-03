"""#613: the Alias clark suggests from a full name (src/clark/page/src/logic/alias.js): the first name, then the initials, comma-separated.
"Jane Doe" suggests "Jane,JD"; a one-word name suggests only that word; an empty name suggests nothing; a suggestion never overwrites
an Alias already typed. Fictional names only. The Alias box waits for a stored Alias field (a guarded change), so this is the pure part.

Run: python3 dev/run_tests.py test_alias_suggest
The plain-JS logic runs inside headless Chrome (the #33 harness, as test_placement.py does), bundled with the pinned esbuild into a
temporary folder (never the repo). Chrome is required: these tests fail, never skip, without it.
"""
import contextlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

from test_server import Running, chrome, wait  # noqa: E402  (the #33 browser harness, shared)

ALIAS_JS = SRC / "clark" / "page" / "src" / "logic" / "alias.js"
_PAGE = {}


def test_page_html():
    """alias.js, bundled by the pinned esbuild in a temporary folder, on a bare page as window.T."""
    if "html" not in _PAGE:
        with tempfile.TemporaryDirectory() as tmp:
            entry, out = Path(tmp) / "entry.js", Path(tmp) / "t.js"
            entry.write_text(f"import * as alias from {json.dumps(ALIAS_JS.as_posix())};\nwindow.T = {{ alias }};\n", encoding="utf-8")
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), str(entry), f"--outfile={out}"], cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            script = out.read_text(encoding="utf-8").replace("</script", "<\\/script")
        _PAGE["html"] = (f'<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><title>t</title></head>\n'
                         f'<body>\n<script>{script}</script>\n</body></html>\n')
    return _PAGE["html"]


class Suggest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=test_page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{cls.server.port}/"}, cls.sid)
        assert wait(lambda: cls.cdp.js("!!(window.T && window.T.alias)", cls.sid)), "the test bundle ran"

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def call(self, fn, *args):
        got = self.cdp.js(f"JSON.stringify(T.alias.{fn}({', '.join(json.dumps(a) for a in args)}))", self.sid)
        self.assertIsNotNone(got, fn)
        return json.loads(got)

    def test_a_full_name_suggests_the_first_name_then_the_initials(self):
        self.assertEqual(self.call("suggestAlias", "Jane Doe"), "Jane,JD")
        self.assertEqual(self.call("suggestAlias", "Sam Lee"), "Sam,SL")
        self.assertEqual(self.call("suggestAlias", "Mary Ann Smith"), "Mary,MAS")

    def test_the_initials_are_capitals_whatever_was_typed(self):
        self.assertEqual(self.call("suggestAlias", "jane doe"), "jane,JD")
        self.assertEqual(self.call("suggestAlias", "Pia van Berg"), "Pia,PVB")
        self.assertEqual(self.call("suggestAlias", "Éla Ørn"), "Éla,ÉØ")

    def test_spaces_and_commas_in_the_name_do_not_spoil_the_suggestion(self):
        self.assertEqual(self.call("suggestAlias", "  Jane   Doe  "), "Jane,JD")
        self.assertEqual(self.call("suggestAlias", "Doe, Jane"), "Doe,DJ")
        self.assertEqual(self.call("suggestAlias", "Jane\tDoe"), "Jane,JD")

    def test_a_word_with_no_letter_adds_no_initial(self):
        self.assertEqual(self.call("suggestAlias", "Jane Doe 2"), "Jane,JD")

    def test_a_one_word_name_suggests_only_that_word(self):
        self.assertEqual(self.call("suggestAlias", "Jane"), "Jane")
        self.assertEqual(self.call("suggestAlias", " Jane "), "Jane")

    def test_an_empty_name_suggests_nothing(self):
        for empty in ("", "   ", ",", None):
            self.assertEqual(self.call("suggestAlias", empty), "", repr(empty))

    def test_a_suggestion_is_offered_only_while_the_alias_is_empty(self):
        self.assertEqual(self.call("aliasOffer", "Jane Doe", ""), "Jane,JD")
        self.assertEqual(self.call("aliasOffer", "Jane Doe", "   "), "Jane,JD")
        self.assertEqual(self.call("aliasOffer", "Jane Doe", "JJ"), "", "an Alias the person typed is never overwritten")
        self.assertEqual(self.call("aliasOffer", "Jane Doe", None), "Jane,JD")
        self.assertEqual(self.call("aliasOffer", "", ""), "")


if __name__ == "__main__":
    unittest.main()
