"""Item 1005 (hostile data): plainFromEditor (edit/plainWords.js), the step that turns what the one editor gives into the plain one-line
text a milestone's Client wording and a picture's caption keep, and the save path those take (the milestone change route, the
imagecap section body). Made-up data only.

Run: python3 dev/run_tests.py test_plain_words_hostile_1005
Quick tier: no page. The module is bundled by the pinned esbuild and run in node (skipped when node is not on the machine).
Whatever the editor hands back, the result is text for a text node: no tag survives that the editor did not carry as words,
the one-line form has no line break of any kind, and what it gives is accepted (or refused in plain words) by the server.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from _paths import ROOT, SRC, TOOLS
from clark import changes
from clark.section_kinds import imagecap

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

ENTRY = ROOT / "tests" / "fixtures" / "plainwords_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}


def bundle():
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "pw.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=PW", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    return _BUNDLE["code"]


def plain(value, one=False):          # one=None leaves the argument out, to read its default
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(bundle() + ";\nconsole.log(JSON.stringify(PW.plainFromEditor(" + json.dumps(value) + ("" if one is None else ", " + json.dumps(one)) + ")));",
                          encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


def node_eval(expr):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(bundle() + ";\nconsole.log(JSON.stringify(" + expr + "));", encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


class PlainThatLooksLikeHtml(unittest.TestCase):
    """Row 1005: a plain one-line value typed as tags round-trips through the editor; a rich field's stored HTML still reads as rich."""
    LITERAL = "<p>use <b>x</b></p>"

    def test_plain_value_that_looks_like_html_loads_as_its_own_text(self):
        html = node_eval("PW.plainToHtml(" + json.dumps(self.LITERAL) + ")")
        self.assertEqual(html, "<p>&lt;p&gt;use &lt;b&gt;x&lt;/b&gt;&lt;/p&gt;</p>")
        self.assertEqual(plain(html, True), self.LITERAL)

    def test_plain_values_that_do_not_look_like_html_load_as_before(self):
        for v in ("Cut-over plan", "a < b & c", "x"):
            self.assertEqual(node_eval("PW.plainToHtml(" + json.dumps(v) + ")"), node_eval("PW.richOrPlain(" + json.dumps(v) + ")"), v)
        self.assertEqual(node_eval("PW.plainToHtml(null)"), "")

    def test_stored_rich_html_still_reads_as_rich(self):
        self.assertEqual(node_eval("PW.richOrPlain('<p>x</p>')"), "<p>x</p>")


LINE_BREAKS = ("\n", "\r", " ", " ", "\u0085", "\v", "\f")


class Hostile(unittest.TestCase):
    def test_script_tag_is_not_kept_as_markup(self):
        out = plain('<p>hi<script>alert(1)</script></p>', True)
        self.assertNotIn("<", out.replace("&lt;", ""))      # the tags are gone; only the script's own text could remain
        self.assertTrue(out.startswith("hi"))

    def test_escaped_script_stays_text_not_a_tag(self):
        self.assertEqual(plain("<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>", True), "<script>alert(1)</script>")

    def test_double_encoded_entity_is_decoded_once(self):
        self.assertEqual(plain("<p>&amp;lt;b&amp;gt;</p>", True), "&lt;b&gt;")

    def test_huge_string_is_fast_and_whole(self):
        words = "word " * 200000
        out = plain("<p>" + words + "</p>", True)
        self.assertEqual(out, words.strip())

    def test_huge_unclosed_tag_does_not_hang(self):
        out = plain("<p>a</p><" + "x" * 300000, True)
        self.assertTrue(out.startswith("a"))

    def test_only_whitespace_is_empty(self):
        for v in ("", "   ", "<p></p>", "<p> </p><p> </p>", "<p> </p>", "\n\n\t", "<ul><li></li></ul>"):
            self.assertEqual(plain(v, True), "", repr(v))
            self.assertEqual(plain(v, False), "", repr(v))

    def test_none_and_non_strings_are_text(self):
        self.assertEqual(plain(None, True), "")
        self.assertEqual(plain(12, True), "12")

    def test_rtl_text_is_kept_in_order(self):
        s = "שלום עולם مرحبا"
        self.assertEqual(plain("<p>" + s + "</p><p>abc</p>", True), s + " abc")

    def test_rtl_marks_are_not_dropped_silently(self):
        s = "abc‏א‮"
        self.assertEqual(plain("<p>" + s + "</p>", True), s)

    def test_emoji_and_zwj_sequences_survive(self):
        s = "ok \U0001F468‍\U0001F469‍\U0001F467 \U0001F1E6\U0001F1EA ❤️"
        self.assertEqual(plain("<p>" + s + "</p>", True), s)

    def test_nested_lists_are_one_line_each_item_in_order(self):
        h = "<ul><li>a<ul><li>b</li><li>c<ol><li>d</li></ol></li></ul></li><li>e</li></ul>"
        self.assertEqual(plain(h, True), "a b c d e")
        self.assertEqual(plain(h, False).split("\n"), ["a", "b", "c", "d", "e"])

    def test_unicode_line_separators_never_survive_one_line(self):
        s = "a b c\u0085d\u000be\u000cf\r\ng\rh\ni"
        out = plain("<p>" + s + "</p>", True)
        for br in LINE_BREAKS:
            self.assertNotIn(br, out)
        self.assertEqual(out.split(" "), list("abcdefghi"))

    def test_nel_and_vertical_tab_split_words(self):
        out = plain("<p>one\u0085two\u000bthree</p>", True)
        self.assertNotIn("\u0085", out)
        self.assertNotIn("\u000b", out)

    def test_multi_line_form_has_no_trailing_spaces_and_no_cr(self):
        out = plain("<p>a  \t</p><p>b  </p>\r\n<p>c</p>", False)
        self.assertNotIn("\r", out)
        for l in out.split("\n"):
            self.assertEqual(l, l.rstrip(" \t"))

    def test_the_default_is_the_lines_form(self):
        self.assertEqual(plain("<p>a</p><p>b</p>", None), "a\nb")

    def test_br_and_hr_make_breaks(self):
        self.assertEqual(plain("<p>a<br>b<br/>c</p><hr><p>d</p>", False).split("\n"), ["a", "b", "c", "d"])
        self.assertEqual(plain("<p>a<br>b</p>", True), "a b")

    def test_plain_older_value_with_angle_brackets_is_returned_as_text(self):
        self.assertEqual(plain("a < b & c > d\nsecond", True), "a < b & c > d second")

    def test_idempotent_on_its_own_output(self):
        for h in ("<p>x &amp; y</p><p>z</p>", "<ul><li>1</li><li>2</li></ul>", "plain & text"):
            once = plain(h, True)
            self.assertEqual(plain(once, True), once)


class SavePath(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)

    def send(self, value):
        status, body = self.change({"project": "ABC", "kind": "milestones", "op": "update", "id": self.demo.milestone,
                            "changes": {"client_message": value}, "place": "peek"})
        return status, body

    def stored(self):
        return self.s.read("milestones", ref=self.demo.milestone)["client_message"]

    def test_hostile_editor_output_saves_as_one_plain_line(self):
        out = plain('<p>Go <script>x()</script>live</p><ul><li>one</li><li>two</li></ul><p> end</p>', True)
        self.assertEqual(self.send(out)[0], 200)
        saved = self.stored()
        self.assertEqual(saved, out)
        for br in LINE_BREAKS:
            self.assertNotIn(br, saved)

    def test_rtl_mark_and_zwj_are_refused_in_plain_words_not_a_crash(self):
        for s in ("abc\u200f\u05d0", "\U0001F468\u200d\U0001F469"):
            status, body = self.send(plain("<p>" + s + "</p>", True))
            self.assertEqual((status, body["ok"]), (400, False))
            self.assertIn("plain text", body["message"])

    def test_a_long_wording_is_refused_and_the_old_one_kept(self):
        self.assertEqual(self.send("kept")[0], 200)
        status, body = self.send(plain("<p>" + "w" * 501 + "</p>", True))
        self.assertEqual((status, body["ok"]), (400, False))
        self.assertEqual(self.stored(), "kept")

    def test_blank_wording_clears(self):
        self.send("kept")
        self.assertEqual(self.send(None)[0], 200)
        self.assertFalse(self.stored())

    def test_a_pasted_next_line_character_saves_as_a_space(self):
        out = plain("<p>one\u0085two</p>", True)
        self.assertEqual(self.send(out)[0], 200)
        self.assertEqual(self.stored(), "one two")

    def test_forty_items_fit_or_are_refused_cleanly(self):
        h = "<ul>" + "".join(f"<li>item {i}</li>" for i in range(40)) + "</ul>"
        out = plain(h, True)
        self.assertEqual(out.count("item"), 40)
        self.assertEqual(self.send(out)[0], 200)
        self.assertEqual(self.stored(), out)

    def test_a_row_wording_saves_as_one_plain_line_on_each_work_item_table(self):
        """Row 1005: a report row's and the peek's Client wording (actions, raid, decisions) take what the editor gives as one plain line."""
        out = plain('<p>Go <script>x()</script>live</p><ul><li>one</li><li>two</li></ul>', True)
        for kind in ("actions", "raid", "decisions"):
            row = self.s.read(kind, "ABC")
            if not row:
                continue
            status, body = self.change({"project": "ABC", "kind": kind, "op": "update", "id": row[0]["id"], "changes": {"client_message": out}, "place": "report"})
            self.assertEqual(status, 200, (kind, body))
            self.assertEqual(next(r for r in self.s.read(kind, "ABC") if r["id"] == row[0]["id"])["client_message"], out, kind)
            for br in LINE_BREAKS:
                self.assertNotIn(br, out)

    def test_the_row_words_source_flattens_with_plainFromEditor_one_line(self):
        text = (PAGE_SRC / "edit" / "ItemRowsEdit.jsx").read_text(encoding="utf-8")
        self.assertRegex(text, r"plainFromEditor\([^)]*true\)")

    def test_caption_one_line_passes_the_picture_section_check(self):
        cap = plain("<p>A &lt;b&gt; caption</p><p>second line</p>", True)
        body = imagecap.check({"v": 1, "caption": cap}, {})
        self.assertEqual(body["caption"], cap)
        self.assertNotIn(" ", body["caption"])


if __name__ == "__main__":
    unittest.main()
