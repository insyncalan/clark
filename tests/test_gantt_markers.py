"""publish_flow.markers_for carries the Gantt (guarded): what publish.gantt_for_client leaves out of the client's copy (owner, note,
budget, effort, baseline dates, and the id and name of an eye-off line) is looked for in the finished file; a shown value is not.
Fictional data only. Lines are planted past the writer.

Run: python3 dev/run_tests.py test_gantt_markers
"""
import sqlite3
import unittest

from unittest import mock

from _demo import DemoStore
from clark import pdf, publish, publish_flow, publish_pdf, to_client, word_route

HIDE_DEFAULT = "show,note,budget,effort,baseline_start,baseline_end,owner"


class Markers(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.n = 0
        self.project(show=1, hidden=HIDE_DEFAULT)

    def sql(self, q, args=()):
        con = sqlite3.connect(str(self.s.path))
        con.execute(q, args)
        con.commit()
        con.close()

    def project(self, show=1, hidden=HIDE_DEFAULT):
        self.sql("UPDATE projects SET show_gantt_client = ?, gantt_hidden_columns = ? WHERE code = 'ABC'", (show, hidden))

    def extra(self, ref, **cols):
        """Set more columns of a line, past the writer."""
        for k, v in cols.items():
            self.sql(f"UPDATE gantt_lines SET {k} = ? WHERE id = ?", (v, ref))

    def bare(self, name, show=1, **cols):
        """A line whose owner, note, budget, effort and baseline dates carry nothing, so only `cols` can be a marker."""
        ref = self.line(name, owner="", note="", budget=None, effort=None, bs=None, be=None, show=show)
        self.extra(ref, **cols)
        return ref

    def line(self, name, owner="ZQ-OWNER-ONE", note="ZQ-NOTE-ONE-X", budget=424242.5, effort=765432.5, bs="2031-05-06", be="2031-05-07", show=1):
        self.n += 1
        ref = f"ABC-GNT-{self.n:03d}"
        self.sql("INSERT INTO gantt_lines (project, id, type, name, start, end, pct, owner, note, budget, effort, baseline_start, baseline_end, show, sort_order)"
                 " VALUES ('ABC',?,'task',?,'2031-06-01','2031-06-10',0,?,?,?,?,?,?,?,?)",
                 (ref, name, owner, note, budget, effort, bs, be, show, self.n * 1024))
        return ref

    def got(self):
        built = publish.build(self.s, "ABC", now="2031-06-15")
        return built, list(publish_flow.markers_for(self.s, "ABC", built["published"]))

    def test_hidden_columns_and_an_eye_off_line_are_markers_and_shown_values_are_not(self):
        shown = self.line("ZQ-SHOWN-LINE")
        off = self.line("ZQ-EYE-OFF-LINE", owner="ZQ-OFF-OWNER", note="ZQ-OFF-NOTE-X", show=0)
        built, got = self.got()
        self.assertIn("ZQ-SHOWN-LINE", built["body"].decode("utf-8"), msg="the shown line is in the file")
        for m in ("ZQ-OWNER-ONE", "ZQ-NOTE-ONE-X", "424242.5", "765432.5", "2031-05-06", "2031-05-07",
                  off, "ZQ-EYE-OFF-LINE", "ZQ-OFF-OWNER", "ZQ-OFF-NOTE-X"):
            self.assertIn(m, got, msg=f"{m!r} is left out of the client copy, so it is a marker")
        for m in (shown, "ZQ-SHOWN-LINE"):
            self.assertNotIn(m, got, msg=f"{m!r} is shown, so it is not a marker")
        self.assertEqual(len(got), len(set(got)), msg="no marker twice")

    def test_a_shown_column_is_not_a_marker(self):
        self.project(hidden="show,note,budget,effort,baseline_start,baseline_end")      # owner shown
        self.line("ZQ-SHOWN-LINE")
        built, got = self.got()
        self.assertNotIn("ZQ-OWNER-ONE", got, msg="the owner is a shown column")
        self.assertIn("ZQ-OWNER-ONE", built["body"].decode("utf-8"), msg="and it is in the file")
        self.assertIn("ZQ-NOTE-ONE-X", got, msg="the note is still hidden")
        self.assertEqual(to_client.check_copy(built["body"], markers=got, folder=None), [], msg="the file as built passes the scan")

    def test_empty_hidden_list_hides_nothing_and_an_unknown_name_hides_the_default(self):
        self.line("ZQ-SHOWN-LINE")
        self.project(hidden="")
        built, got = self.got()
        self.assertEqual([m for m in got if m.startswith("ZQ-") or m in ("424242.5", "2031-05-06")], [], msg="exactly '' hides nothing: nothing to look for")
        self.assertEqual(to_client.check_copy(built["body"], markers=got, folder=None), [], msg="and the file passes")
        self.project(hidden="NOTE")                                                      # an unknown name voids the list
        built, got = self.got()
        for m in ("ZQ-OWNER-ONE", "ZQ-NOTE-ONE-X", "424242.5"):
            self.assertIn(m, got, msg=f"{m!r}: an unknown name hides the default seven")
        self.assertEqual(to_client.check_copy(built["body"], markers=got, folder=None), [], msg="and the file passes")

    def test_no_gantt_tab_means_every_line_is_a_marker(self):
        ref = self.line("ZQ-SHOWN-LINE")
        self.project(show=0)
        built, got = self.got()
        for m in (ref, "ZQ-SHOWN-LINE", "ZQ-OWNER-ONE", "ZQ-NOTE-ONE-X"):
            self.assertIn(m, got, msg=f"{m!r}: the file has no Gantt, so none of it may be in the file")
        self.assertEqual(to_client.check_copy(built["body"], markers=got, folder=None), [], msg="and the file as built passes")

    def test_a_leak_in_a_built_file_is_caught_and_the_clean_file_passes(self):
        self.line("ZQ-SHOWN-LINE")
        self.line("ZQ-EYE-OFF-LINE", show=0)
        built, got = self.got()
        self.assertEqual(to_client.check_copy(built["body"], markers=got, folder=None), [], msg="the file as built passes")
        for leak in ("ZQ-OWNER-ONE", "ZQ-NOTE-ONE-X", "424242.5", "765432.5", "2031-05-06", "ZQ-EYE-OFF-LINE", "ABC-GNT-002"):
            body = built["body"].replace(b"</body>", b"<p>" + leak.encode() + b"</p></body>")
            self.assertTrue(to_client.check_copy(body, markers=got, folder=None), msg=f"a file carrying {leak!r} must be refused")

    def test_baseline_start_alone_is_a_marker_on_a_kept_line(self):
        self.bare("ZQ-SHOWN-LINE", baseline_start="2031-05-06")
        built, got = self.got()
        self.assertIn("2031-05-06", got, msg="the baseline start is left out of the copy")
        self.assertNotIn("2031-05-07", got)

    def test_baseline_end_alone_is_a_marker_on_a_kept_line(self):
        self.bare("ZQ-SHOWN-LINE", baseline_end="2031-05-07")
        built, got = self.got()
        self.assertIn("2031-05-07", got, msg="the baseline end is left out of the copy")
        self.assertNotIn("2031-05-06", got)

    def test_baseline_dates_are_markers_on_an_eye_off_line_whatever_the_list_says(self):
        self.project(hidden="")                                    # the project hides nothing, yet an eye-off line is not in the file at all
        self.bare("ZQ-SHOWN-LINE")
        self.bare("ZQ-EYE-OFF-LINE", show=0, baseline_start="2031-05-06")
        off2 = self.bare("ZQ-EYE-OFF-TWO", show=0, baseline_end="2031-05-08")
        built, got = self.got()
        self.assertIn("2031-05-06", got, msg="an eye-off line's baseline start")
        self.assertIn("2031-05-08", got, msg="an eye-off line's baseline end")
        self.assertIn(off2, got)

    def test_a_column_the_project_adds_to_its_hidden_list_is_a_marker_on_kept_and_eye_off_lines(self):
        self.project(hidden=HIDE_DEFAULT + ",deliverable,workstream,priority,health")
        self.bare("ZQ-SHOWN-LINE", deliverable="ZQ-DELIVERABLE-K", workstream="ZQ-WORKSTREAM-K", priority="High", health="Red")
        self.bare("ZQ-EYE-OFF-LINE", show=0, deliverable="ZQ-DELIVERABLE-O", workstream="ZQ-WORKSTREAM-O")
        built, got = self.got()
        for m in ("ZQ-DELIVERABLE-K", "ZQ-WORKSTREAM-K", "ZQ-DELIVERABLE-O", "ZQ-WORKSTREAM-O"):
            self.assertIn(m, got, msg=f"{m!r} is a column the project hides")
        self.assertNotIn("ZQ-DELIVERABLE-K", built["body"].decode("utf-8"))
        self.assertEqual(to_client.check_copy(built["body"], markers=got, folder=None), [], msg="the file as built passes")
        body = built["body"].replace(b"</body>", b"<p>ZQ-DELIVERABLE-K</p></body>")
        self.assertTrue(to_client.check_copy(body, markers=got, folder=None), msg="a hidden deliverable in the file is refused")

    def test_a_shown_deliverable_is_not_a_marker(self):
        self.bare("ZQ-SHOWN-LINE", deliverable="ZQ-DELIVERABLE-K")
        built, got = self.got()
        self.assertNotIn("ZQ-DELIVERABLE-K", got, msg="the deliverable is not on the project's list, so it is shown")
        self.assertIn("ZQ-DELIVERABLE-K", built["body"].decode("utf-8"))
        self.assertEqual(to_client.check_copy(built["body"], markers=got, folder=None), [], msg="the file as built passes")

    def test_the_word_check_uses_the_gantt_markers(self):
        self.line("ZQ-SHOWN-LINE")
        built, _ = self.got()
        for leak in ("ZQ-OWNER-ONE", "2031-05-06"):
            with mock.patch.object(word_route, "_file_text", return_value=f"page text {leak} end".encode()):
                said = word_route._held_back(self.s, "ABC", built["published"], b"x", None)
            self.assertTrue(said, msg=f"a Word file showing the hidden {leak!r} is held back")
        with mock.patch.object(word_route, "_file_text", return_value=b"page text ZQ-SHOWN-LINE end"):
            self.assertEqual(word_route._held_back(self.s, "ABC", built["published"], b"x", None), "", msg="a shown line is not")

    def test_the_pdf_check_uses_the_gantt_markers(self):
        self.line("ZQ-SHOWN-LINE")
        built, _ = self.got()
        seen = []

        def spy(data, markers, folder=None, body=None):
            seen.append(list(markers))
            return ["stop"]
        pub = mock.Mock()
        pub.branding = None
        step = publish_pdf.Step({"on": True, "choice": None, "new_name": None, "confirmed": False, "error": None}, pub)
        built = dict(built, number=1)
        with mock.patch.object(pdf, "find_chrome", return_value="chrome"), mock.patch.object(publish_pdf, "make", return_value=b"%PDF"), \
                mock.patch.object(publish_pdf, "problems", spy), mock.patch.object(publish_pdf.Path, "exists", return_value=False):
            step.prepare(pub, "/tmp/x.html", built, "2031-06-15", self.s, "ABC", None, None)
        self.assertEqual(len(seen), 1, msg="the PDF was checked")
        for m in ("ZQ-OWNER-ONE", "ZQ-NOTE-ONE-X", "2031-05-06", "2031-05-07"):
            self.assertIn(m, seen[0], msg=f"{m!r} is a marker for the PDF as well")


if __name__ == "__main__":
    unittest.main()
