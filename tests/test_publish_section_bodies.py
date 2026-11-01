"""A needs or tracker section in the published file (src/clark/publish.py; guarded): kept only when its body checks again at publish
time, hidden ones absent, and nothing of a body (no markup, no script) reaches the file in this base.

Run: python3 dev/run_tests.py test_publish_section_bodies
"""
import json
import re
import sqlite3
import unittest
from unittest import mock

from _demo import USER
from _publish_fixture import spellings
from clark import changes, publish, section_bodies as sb, store as store_module
from test_changes import Api, KIND

MARK = "ZQ-PUBLISH-MARK"
HOSTILE = ["<script>alert('" + MARK + "')</script>", '"><img src=x onerror=alert(1)>', "</script><script>x", "javascript:alert(1)",
           "<!--", "]]>", "&lt;b&gt;&amp;"]
SEPARATORS = MARK + "\u2028" + MARK + "\u2029"                  # refused when a body is saved; a later item's published data could still hold one


def body(*words):
    """A body both content types take: for needs, rows of the shape its checker rebuilds (the text goes in `what` and `from`)."""
    return json.dumps({"v": 1, "rows": [{"what": w, "kind": "decision", "from": w[:100], "by": "", "hidden": 0} for w in words]})


class Published(Api):
    def section(self, kind="needs", title=None, **more):
        return self.ok("new", values={"type": kind, "title": title or ("Needs from you" if kind == "needs" else "Progress")}, **more)["ref"]

    def write(self, ref, text):
        status, got = self.change(self.req("update", id=ref, changes={"body": text}))
        self.assertEqual(status, 200, got)

    def raw(self, ref, text):
        """A body written past the writer (an older clark, or by hand): the store's own rules are not asked."""
        con = sqlite3.connect(str(self.path))
        con.execute("UPDATE report_sections SET body = ? WHERE id = ?", (text, ref))
        con.commit()
        con.close()

    def build(self):
        return publish.build(self.s, "ABC", now="2030-01-15")

    def file(self):
        return self.build()["body"].decode("utf-8")

    def sections(self):
        return {s["id"]: s for s in self.build()["published"]["sections"]}


class Kept(Published):
    def test_a_good_needs_body_keeps_its_shown_rows_and_a_tracker_body_keeps_its_place_and_title_only(self):
        needs = self.section("needs")
        tracker = self.section("tracker")
        self.write(needs, body("one"))
        self.write(tracker, body("two"))
        got = self.sections()
        self.assertEqual(got[needs], {"id": needs, "type": "needs", "title": "Needs from you", "beside": 0,
                                      "rows": [{"what": "one", "kind": "decision", "from": "one", "by": ""}]})
        self.assertEqual(got[tracker], {"id": tracker, "type": "tracker", "title": "Progress", "beside": 0})

    def test_an_empty_body_is_left_out(self):
        needs = self.section("needs")
        self.assertNotIn(needs, self.sections())
        self.write(needs, body("one"))
        self.assertIn(needs, self.sections())
        self.write(needs, "")
        self.assertNotIn(needs, self.sections())

    def test_a_bad_body_is_left_out_whatever_is_stored(self):
        needs = self.section("needs")
        for bad in ('{"a": 1.5}', "not json", "<script>" + MARK + "</script>", '"x"', "[" * 50, '{"a": "x\\u202ey"}', '{"a": 1, "a": 2}',
                    '{"a": "%s"}' % ("x" * 70000), "   ", "null"):
            with self.subTest(body=bad[:30]):
                self.raw(needs, bad)
                self.assertNotIn(needs, self.sections())
                self.assertNotIn(MARK, self.file())

    def test_the_body_is_checked_again_at_publish_time_with_the_limits_of_that_time(self):
        needs = self.section("needs")
        self.write(needs, body("x" * 300))
        self.assertIn(needs, self.sections())
        with mock.patch.dict(sb.LIMITS, {"needs": 100}):                      # a limit made stricter after the body was saved
            self.assertNotIn(needs, self.sections())
        self.assertIn(needs, self.sections())

    def test_the_stored_text_is_checked_by_the_checker_of_its_type_at_publish_time(self):
        needs, tracker = self.section("needs"), self.section("tracker")
        self.write(needs, body("a"))
        self.write(tracker, body("b"))
        calls = []

        def checker(kind):
            def check(value, rules):
                calls.append(kind)
                if kind == "tracker":
                    raise sb.Bad("Not valid.")
                return value
            return check
        with mock.patch.dict(sb.CHECKERS, {"needs": checker("needs"), "tracker": checker("tracker")}):
            got = self.sections()
        self.assertIn(needs, got)
        self.assertNotIn(tracker, got)
        self.assertEqual(sorted(set(calls)), ["needs", "tracker"])

    def test_a_hidden_section_is_absent_with_its_content(self):
        needs = self.section("needs")
        self.write(needs, body(MARK))
        self.ok("update", id=needs, changes={"hidden": 1})
        self.assertNotIn(needs, self.sections())
        text = self.file()
        for spelling in spellings(MARK):
            self.assertNotIn(spelling, text)

    def test_a_section_left_out_does_not_leave_its_partner_marked_as_half_of_a_pair(self):
        first = self.section("needs")
        second = self.section("tracker", after=first, beside=1)
        self.write(first, body("one"))
        got = self.sections()
        self.assertEqual((got[first]["beside"], second in got), (0, False))        # the partner has no body: out, so the first takes the full row
        self.write(second, body("two"))
        got = self.sections()
        self.assertEqual((got[first]["beside"], got[second]["beside"]), (1, 0))      # both in: a pair
        self.raw(second, "not json")
        self.assertEqual(self.sections()[first]["beside"], 0)

    def test_text_sections_and_the_others_are_published_as_before(self):
        before = {k: v for k, v in self.sections().items()}
        needs = self.section("needs")
        self.write(needs, body("one"))
        after = {k: v for k, v in self.sections().items() if k != needs}
        self.assertEqual(after, before)


class NothingOfABodyReachesTheFile(Published):
    def test_a_tracker_body_full_of_markup_is_not_in_the_file_in_any_spelling(self):
        needs, tracker = self.section("needs"), self.section("tracker")
        self.write(needs, body("one"))
        self.write(tracker, json.dumps({"groups": [{"name": h, "lines": [{"text": h}]} for h in HOSTILE]}))
        baseline_scripts = self.baseline()
        text = self.file()
        self.assertEqual(len(re.findall(r'id="clark-data"', text)), 1)
        self.assertEqual(len(re.findall(r"<script\b", text)), baseline_scripts)
        for marker in HOSTILE + [MARK, "Example team"]:
            for spelling in spellings(marker):
                self.assertNotIn(spelling, text, marker)         # the tracker's content is not published yet; needs holds only "one"
        data = self.data_block(text)
        self.assertEqual({s["type"] for s in data["sections"] if s["id"] in (needs, tracker)}, {"needs", "tracker"})
        self.assertNotIn("body", json.dumps([s for s in data["sections"] if s["id"] in (needs, tracker)]))      # a needs row is published as rows, never as a body

    def baseline(self):
        return len(re.findall(r"<script\b", self.file()))

    def data_block(self, text):
        found = re.findall(r'<script type="application/json" id="clark-data">(.*?)</script>', text, re.S)
        self.assertEqual(len(found), 1)
        return json.loads(found[0])

    def test_what_a_later_item_publishes_is_escaped_in_the_data_block_and_can_not_overwrite_the_entry(self):
        """The plug-in point: section_bodies.published(). Whatever a later item hands back is JSON-escaped (< > & and the two
        line separators) and merged without overwriting id, type, title or beside."""
        needs = self.section("needs")
        self.write(needs, body("one"))
        given = {"rows": [{"what": h} for h in HOSTILE + [SEPARATORS]], "id": "ZQ-OVER", "type": "text", "title": "ZQ-OVER", "beside": 7}
        with mock.patch.object(sb, "published", return_value=given):
            text = self.file()
            entry = {s["id"]: s for s in self.data_block(text)["sections"]}[needs]
        self.assertEqual((entry["id"], entry["type"], entry["title"], entry["beside"]), (needs, "needs", "Needs from you", 0))
        self.assertEqual([r["what"] for r in entry["rows"]], HOSTILE + [SEPARATORS])                    # arrives intact as data
        block = re.search(r'<script type="application/json" id="clark-data">(.*?)</script>', text, re.S).group(1)
        for ch in "<>&\u2028\u2029":
            self.assertNotIn(ch, block)                                                    # none of them is raw inside the block
        self.assertEqual(len(re.findall(r'id="clark-data"', text)), 1)
        self.assertNotIn("<script>alert", text)

    def test_a_later_item_can_leave_a_section_out_by_returning_nothing(self):
        needs = self.section("needs")
        self.write(needs, body("one"))
        with mock.patch.object(sb, "published", return_value=None):
            self.assertNotIn(needs, self.sections())

    def test_clean_html_is_never_used_on_a_body(self):
        src = (store_module.Path(publish.__file__)).read_text(encoding="utf-8")
        content = src.split("def _content")[1].split("\ndef ")[0]
        self.assertNotIn("clean_html(", content)


class ThePageDrawsNeedsAndLeavesTheTrackerQuiet(unittest.TestCase):
    """The live page says 'Not shown on this page yet.' for a type it can't draw (the tracker, until #189), and a published file
    leaves that type out; needs is drawn (#121). Read from the page's source, so no browser is needed."""

    PAGE = store_module.Path(publish.__file__).parent / "page" / "src" / "components"

    def test_the_live_page_has_a_quiet_line_for_every_type_it_does_not_draw(self):
        src = (self.PAGE / "Section.jsx").read_text(encoding="utf-8")
        self.assertIn('<p class="quiet">Not shown on this page yet.</p>', src)
        self.assertIn('section.type === "needs"', src)
        self.assertNotIn("tracker", src)

    def test_a_published_file_draws_no_type_it_does_not_know(self):
        src = (self.PAGE / "Dashboard.jsx").read_text(encoding="utf-8")
        line = next(l for l in src.splitlines() if "const fileDraws" in l)
        self.assertTrue(line.rstrip().endswith(": false);"), line)             # every other type: not drawn, so left out of the file
        self.assertIn("needs", line)
        self.assertNotIn("tracker", line)

    def test_the_page_writes_no_body_of_a_text_section(self):
        rich = (self.PAGE.parent / "edit" / "richSave.js").read_text(encoding="utf-8")
        self.assertIn("export const RICH_WRITES = {};", rich)


class ExportsLeaveThemOut(Published):
    def test_the_excel_cover_leaves_out_a_needs_and_a_tracker_section(self):
        from clark import excel_cover
        sections = [{"type": "needs", "title": "Needs from you", "body": body(MARK), "hidden": 0},
                    {"type": "tracker", "title": "Progress", "body": body(MARK), "hidden": 0}]
        lines = excel_cover.lines({"name": "Example Programme"}, sections, [], "exported now")
        self.assertNotIn(MARK, json.dumps(lines))
        self.assertNotIn("Needs from you", json.dumps(lines))
        self.assertNotIn("Progress", json.dumps(lines))

    def test_the_word_report_leaves_out_a_needs_and_a_tracker_section(self):
        from clark import docx_build
        self.assertFalse({"needs", "tracker"} & set(docx_build.TITLES))
        published = {"sections": [{"id": "a", "type": "needs", "title": "Needs from you", "beside": 0},
                                  {"id": "b", "type": "tracker", "title": "Progress", "beside": 0}], "data": {}}
        self.assertEqual(docx_build.sections(published, None), [])


if __name__ == "__main__":
    unittest.main()
