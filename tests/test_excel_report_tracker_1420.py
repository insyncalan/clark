"""Row 1420: the Excel cover draws one overall tracker line from the published tracker entry, and nothing else of it.

Run: python3 dev/run_tests.py test_excel_report_tracker_1420
"""
import json
import unittest

from clark import excel_cover


def entry(actual, lines=True):
    return {"type": "tracker", "title": "Progress", "hidden": 0, "size": "medium",
            "overall": {"actual": actual, "planned": 700, "health": "atrisk", "note": "NOTE-WORDS"},
            "columns": {}, "groups": [{"name": "GROUP-NAME", "lines": [{"text": "LINE-TEXT"}]}] if lines else []}


def drawn(*sections):
    return excel_cover.lines({"name": "Example Programme"}, list(sections), [], "exported now")


class Drawn(unittest.TestCase):
    def test_the_report_sheet_has_one_overall_tracker_line_1420(self):
        got = [l["text"] for l in drawn({"type": "text", "title": "Before", "body": "<p>x</p>", "hidden": 0}, entry(625))]
        at = got.index("Achieved 62.5%")
        self.assertEqual(got.count("Achieved 62.5%"), 1)
        self.assertEqual(got[at - 1], "x", "in the section's own place")
        text = json.dumps(drawn(entry(625)))
        for word in ("GROUP-NAME", "LINE-TEXT", "NOTE-WORDS", "Planned", "atrisk", "Progress"):
            self.assertNotIn(word, text)
        self.assertEqual([l["text"] for l in drawn(entry(940)) if l["text"].startswith("Achieved")], ["Achieved 94%"])
        self.assertEqual([l["text"] for l in drawn(entry(5)) if l["text"].startswith("Achieved")], ["Achieved 0.5%"])

    def test_no_tracker_line_and_no_missing_note_when_nothing_is_published_1420(self):
        base = json.dumps(drawn())
        self.assertEqual(json.dumps(drawn()), base)
        self.assertEqual(json.dumps(drawn(entry(None))), base)
        self.assertEqual(json.dumps(drawn(dict(entry(625), hidden=1))), base)
        self.assertEqual(json.dumps(drawn({"type": "tracker", "title": "Progress", "hidden": 0})), base)
        self.assertEqual(json.dumps(drawn(dict(entry(625), overall="x"))), base)
        self.assertNotIn("racker", base)

    def test_the_client_copy_has_the_line_only_for_a_published_tracker_1420(self):
        from clark import publish
        import test_publish_section_bodies as t

        class Client(t.Published):
            def runTest(self):
                tracker = self.section("tracker")
                self.write(tracker, json.dumps({"overall": {"actual": 100}, "groups": [{"name": "G", "lines": [{"text": "L", "planned": 400, "achieved": 250}]}]}))
                shown = publish.select(publish.read_inputs(self.s, "ABC", "2030-01-15"))
                got = [l["text"] for l in excel_cover.lines({"name": "P"}, [dict(s, hidden=0) for s in shown["sections"]], [], "x")]
                self.assertEqual(got.count("Achieved 25%"), 1, "the sum of the lines, not the typed 10%")
                self.ok("update", id=tracker, changes={"hidden": 1})
                shown = publish.select(publish.read_inputs(self.s, "ABC", "2030-01-15"))
                got = [l["text"] for l in excel_cover.lines({"name": "P"}, [dict(s, hidden=0) for s in shown["sections"]], [], "x")]
                self.assertFalse([x for x in got if x.startswith("Achieved")])
        case = Client()
        case.setUp()
        try:
            case.runTest()
        finally:
            case.tearDown()


if __name__ == "__main__":
    unittest.main()
