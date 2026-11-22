"""Row 1367: ask clark reads the project's own data (hidden rows included, archived left out), and says what it cut with counts.

Run: python3 dev/run_tests.py test_ask_1367
Fictional data only (the publish plant). Ruling 19-11 reverses the earlier "report only" rule for ask clark; the published file is unchanged.
"""
import re
import unittest
from dataclasses import replace
from unittest import mock

from _paths import SRC  # noqa: F401

import _publish_fixture as plant
import test_ask_route as route
from clark import ask, ask_data, ask_passages, ask_service, publish


def read(question="what is there?", budget=ask.BUDGET, edit=None):
    given = plant.inputs()
    given["as_at"] = "2026-11-17"
    if edit:
        edit(given)
    with mock.patch.object(publish, "read_inputs", return_value=given):
        return ask_data.project_data(object(), "PUB", question, budget, as_at="2026-11-17"), given


def text_of(got):
    return "\n".join(p.text for p in got.passages)


class HiddenRowsAreRead(unittest.TestCase):
    def test_an_eye_off_row_and_a_report_hidden_row_are_read(self):
        text = text_of(read()[0])
        for ref in ("PUB-M-003", "PUB-A-010", "PUB-A-011", "PUB-M-004", "PUB-002", "PUB-D-002", "PUB-U-002"):
            self.assertIn(ref, text)

    def test_a_hidden_milestones_section_does_not_stop_the_read(self):
        def hide(given):
            given["sections"] = [{**s, "hidden": 1 if s.get("type") == "milestones" else 0} for s in publish.DEFAULT_SECTIONS]
        self.assertIn("PUB-M-001", text_of(read("milestones?", edit=hide)[0]))

    def test_the_published_file_still_leaves_the_hidden_rows_out(self):
        given = read()[1]
        ids = {r["id"] for k in ("milestones", "actions") for r in publish.select(given)["data"][k]}
        self.assertNotIn("PUB-M-003", ids)
        self.assertNotIn("PUB-A-011", ids)

    def test_workstreams_are_read_as_their_own_kind(self):
        got, given = read("workstreams?")
        hidden = plant.load()["markers"]["PUB-W-002"]
        self.assertIn(hidden, text_of(got), "the workstream the report leaves out is read")
        self.assertIn(hidden, "\n".join(p.text for p in got.passages if p.label == ask_data.LABELS["workstreams"]))
        total = len([w for w in given["data"]["workstreams"] if not w.get("archived") and w.get("project", "PUB") == "PUB"])
        self.assertIn(("workstreams", total, total), got.counts)
        cut = ask_data.left_out_lines([("workstreams", total - 1, total)])
        self.assertEqual(cut, [f"Sent {total - 1} of {total} workstreams (the closest to your question); 1 was left out."])


class WhatStaysOut(unittest.TestCase):
    def test_an_archived_row_is_not_read(self):
        self.assertNotIn("PUB-A-016", text_of(read()[0]))

    def test_a_sensitive_labelled_row_is_not_read(self):
        text = text_of(read()[0])
        self.assertNotIn("PUB-A-012", text)
        self.assertNotIn("PUB-A-015", text)

    def test_a_line_that_looks_like_a_password_is_left_out_and_counted(self):
        def plant_secret(given):
            for r in given["data"]["actions"]:
                r["description"] = "x " * ask_data.MAX_PASSAGE + "pass" + "word: Welcome" + "2026!"
        got, _ = read(edit=plant_secret)
        self.assertGreater(got.secret, 0)
        self.assertNotIn("Welcome", text_of(got))

    def test_no_report_left_out_passage_or_kinds_field_remains(self):
        got, _ = read()
        self.assertFalse([p for p in got.passages if p.label == "report: left out"])
        self.assertFalse(hasattr(got, "kinds_left_out"))


class NoteTellsTheTruth(unittest.TestCase):
    def test_nothing_cut_gives_no_note(self):
        got, _ = read()
        self.assertEqual(got.left_out, 0)
        self.assertEqual(ask_data.left_out_lines(got.counts), [])

    def test_a_cut_gives_one_line_per_cut_kind_with_both_numbers(self):
        self.assertEqual(ask_data.left_out_lines([("milestones", 20, 47), ("actions", 5, 5), ("raid", 1, 2)]),
                         ["Sent 20 of 47 milestones (the closest to your question); 27 were left out.",
                          "Sent 1 of 2 risks and issues (the closest to your question); 1 was left out."])

    def test_a_tight_budget_counts_what_was_sent_and_left_out(self):
        got, _ = read(budget=400)
        lines = ask_data.left_out_lines(got.counts)
        self.assertTrue(lines)
        for kind, sent, total in got.counts:
            self.assertLessEqual(sent, total)
        self.assertTrue(any(w in lines[0] for w in ("of", "left out")))

    def test_a_seven_zero_decision_project_says_nothing_about_decisions(self):
        def no_decisions(given):
            given["data"]["decisions"] = []
        got, _ = read(edit=no_decisions)
        self.assertNotIn("decisions", " ".join(ask_data.left_out_lines(got.counts)))


class BudgetEdge(unittest.TestCase):
    """The cut at the char limit, exactly at, below and above, on 180 passages of 100 characters."""
    passages = [ask.Passage("p", "x" * 100) for _ in range(180)]

    def test_all_180_fit_under_the_budget(self):
        kept, left = ask_data.choose(self.passages, "q", 40000)
        self.assertEqual((len(kept), left), (180, 0))      # 180 x 100 = 18,000 chars, under the 1,200,000 budget

    def test_one_char_below_drops_the_last_passage(self):
        kept, left = ask_data.choose(self.passages, "q", 17999)
        self.assertEqual((len(kept), left), (179, 1))

    def test_exactly_at_a_whole_number_of_passages(self):
        kept, left = ask_data.choose(self.passages, "q", 10000)
        self.assertEqual((len(kept), left), (100, 80))

    def test_one_char_over_a_whole_number_adds_nothing(self):
        self.assertEqual(len(ask_data.choose(self.passages, "q", 10099)[0]), 100)

    def test_a_project_over_the_share_is_cut_at_the_share_and_the_count_is_said(self):
        whole = ask_service.PROJECT_SHARE // 100
        many = [ask.Passage("p", "x" * 100) for _ in range(whole + 1)]        # one passage over the share
        kept, left = ask_data.choose(many, "q", ask_service.PROJECT_SHARE)
        self.assertEqual((len(kept), left), (whole, 1))
        self.assertEqual(ask_data.left_out_lines([("actions", len(kept), len(many))]),
                         [f"Sent {whole} of {whole + 1} actions (the closest to your question); 1 was left out."])

    def test_exactly_the_share_is_kept_whole(self):
        kept, left = ask_data.choose(many := [ask.Passage("p", "x" * 100) for _ in range(ask_service.PROJECT_SHARE // 100)], "q", ask_service.PROJECT_SHARE)
        self.assertEqual((len(kept), left), (len(many), 0))

    def test_no_keyword_hit_keeps_path_order(self):
        kept, _ = ask_data.choose([ask.Passage("p", f"{i:03d} " + "x" * 96) for i in range(180)], "zzzz", 1000)
        self.assertEqual([p.text[:3] for p in kept], [f"{i:03d}" for i in range(10)])

    def test_a_keyword_hit_beats_path_order(self):
        ps = [ask.Passage("p", "x" * 100) for _ in range(179)] + [ask.Passage("p", "needle " + "x" * 93)]
        kept, _ = ask_data.choose(ps, "needle", 1000)
        self.assertIn(ps[-1], kept)


def add_row(given, kind, **fields):
    row = {"id": "PUB-Z-900", "project": "PUB", "archived": 0, **fields}
    given["data"][kind] = list(given["data"][kind]) + [row]
    return row


class OwnRowsKillers(unittest.TestCase):
    """Mutation sweep of the row 1367 lines (ruling 19-11): each test pins one comparison or default in own_rows, project_data or the note."""

    def test_a_row_of_another_project_is_not_read(self):
        def other(given):
            add_row(given, "actions", id="OTH-A-900", project="OTH", description="ZQ-OTHER-ROW")
        self.assertNotIn("ZQ-OTHER-ROW", text_of(read(edit=other)[0]))

    def test_a_row_with_no_project_field_is_read(self):
        def bare(given):
            row = add_row(given, "actions", id="PUB-A-901", description="ZQ-BARE-ROW")
            del row["project"]
        self.assertIn("ZQ-BARE-ROW", text_of(read(edit=bare)[0]))

    def test_the_stored_rows_are_not_changed_by_the_read(self):
        def milestone(given):
            add_row(given, "milestones", id="PUB-M-901", name="ZQ-MS", baseline_date="2026-11-18")
        got, given = read(edit=milestone)
        row = [r for r in given["data"]["milestones"] if r["id"] == "PUB-M-901"][0]
        self.assertNotIn("state_word", row)
        self.assertNotIn("state", row)

    def test_a_plain_text_update_keeps_its_angle_brackets(self):
        def plain_text(given):
            add_row(given, "actions", id="PUB-A-902", description="ZQ-LEGACY", latest_update="ZQ-LEFT <keep> ZQ-RIGHT")
        self.assertIn("ZQ-LEFT <keep> ZQ-RIGHT", text_of(read(edit=plain_text)[0]))

    def test_a_milestone_line_has_its_state_word_as_at_the_report_day(self):
        def milestone(given):
            add_row(given, "milestones", id="PUB-M-901", name="ZQ-MS", baseline_date="2026-11-18", forecast_date="2026-11-18")
        line = [l for l in text_of(read(edit=milestone)[0]).split("\n") if "PUB-M-901" in l][0]
        self.assertIn("On track", line)       # as at 17-11 the agreed date has not passed (a read as at today would say Late)
        self.assertNotIn("Late", line)

    def test_a_milestone_past_its_date_is_late_in_the_facts(self):
        def milestone(given):
            add_row(given, "milestones", id="PUB-M-901", name="ZQ-MS", owner="Delivery lead", baseline_date="2026-11-10")
        got, _ = read(edit=milestone)
        self.assertEqual(got.facts["PUB-M-901"]["state"], ["overdue"])

    def test_the_project_block_is_in_the_passages(self):
        got, _ = read()
        self.assertIn("sponsor: Programme sponsor", text_of(got))

    def test_counts_name_only_kinds_that_have_rows(self):
        def no_decisions(given):
            given["data"]["decisions"] = []
        got, _ = read(edit=no_decisions)
        self.assertNotIn("decisions", [k for k, _s, _t in got.counts])
        self.assertTrue(all(t > 0 for _k, _s, t in got.counts))

    def test_counts_are_the_exact_rows_sent_when_nothing_is_cut(self):
        got, _ = read()
        for kind, sent, total in got.counts:
            lines = sum(p.text.count("\n") + 1 for p in got.passages if p.label == ask_data.LABELS[kind])
            self.assertEqual((sent, total), (lines, lines))

    def test_the_same_one_line_per_kind_count_when_cut(self):
        got, _ = read(budget=400)
        for kind, sent, total in got.counts:
            lines = sum(p.text.count("\n") + 1 for p in got.passages if p.label == ask_data.LABELS[kind])
            self.assertEqual(sent, lines)
        self.assertGreater(sum(1 for _k, s, t in got.counts if s < t), 0)

    def test_one_left_out_is_said_in_the_singular_and_more_in_the_plural(self):
        self.assertIn("1 was left out.", ask_data.left_out_lines([("actions", 4, 5)])[0])
        self.assertIn("2 were left out.", ask_data.left_out_lines([("actions", 3, 5)])[0])
        self.assertEqual(ask_data.left_out_lines([("actions", 5, 5)]), [])


class AsAtAndNoteOrder(unittest.TestCase):
    def test_facts_are_judged_as_at_the_report_day(self):
        def action(given):
            add_row(given, "actions", id="PUB-A-903", description="ZQ-DUE", owner="Site manager", status="Open", due_date="2026-11-18")
        got, _ = read(edit=action)
        self.assertNotIn("overdue", got.facts["PUB-A-903"]["state"])      # due 18-11 is not late as at 17-11

    def test_an_open_action_due_before_the_report_day_is_overdue_in_the_facts(self):
        def action(given):
            add_row(given, "actions", id="PUB-A-904", description="ZQ-LATE", owner="Site manager", status="Open", due_date="2026-11-16")
        got, _ = read(edit=action)
        self.assertIn("overdue", got.facts["PUB-A-904"]["state"])         # no day passed to facts_of would give no overdue at all


class NoteThroughTheRoute(route.Base):
    def test_the_counts_line_comes_straight_after_the_report_line_position_and_before_folder_lines(self):
        with mock.patch.object(ask_service, "folder_notes", return_value=["ZQ-FOLDER-LINE"]), mock.patch.object(ask_service, "PROJECT_SHARE", 600):
            status, got = self.question("what is late?")
        self.assertEqual(status, 200, got)
        notes = got["notes"]
        first = min(i for i, n in enumerate(notes) if n.startswith("Sent "))
        self.assertLess(first, notes.index("ZQ-FOLDER-LINE"))

    def test_a_tight_share_puts_the_counts_line_in_the_notes_and_not_the_report_line(self):
        with mock.patch.object(ask_service, "PROJECT_SHARE", 600):
            status, got = self.question("what is late?")
        self.assertEqual(status, 200, got)
        self.assertTrue([n for n in got["notes"] if n.startswith("Sent ") and "left out." in n], got["notes"])
        self.assertFalse([n for n in got["notes"] if "too long to send in full" in n], got["notes"])

    def test_the_reply_notes_say_how_many_passages_were_left_out(self):
        with mock.patch.object(ask_service, "folder_notes", return_value=[]), mock.patch.object(ask, "MAX_PASSAGES", 1):
            status, got = self.question("what is late?")
        self.assertEqual(status, 200, got)
        lines = [n for n in got["notes"] if n.startswith("Left out to keep this question under the size limit: ")]
        self.assertEqual(len(lines), 1, got["notes"])
        self.assertRegex(lines[0], r": [1-9][0-9]* passages?\.$")

    def test_the_size_limit_line_says_the_sum_of_the_project_cut_and_the_request_cut(self):
        real = ask_data.project_data

        def cut_by(extra):
            def fake(*a, **k):
                got = real(*a, **k)
                return replace(got, left_out=extra)
            return fake

        def number(extra):
            folder = ask_passages.FolderData(passages=(ask.Passage("a.md", "plan one"), ask.Passage("b.md", "plan two"), ask.Passage("c.md", "plan three")), left_out=0)
            with mock.patch.object(ask_service.ask_passages, "folder_data", return_value=folder), mock.patch.object(ask_service, "folder_notes", return_value=[]), \
                    mock.patch.object(ask, "MAX_PASSAGES", 2), mock.patch.object(ask_service.ask_data, "project_data", side_effect=cut_by(extra)):
                status, got = self.question("what is late?")
            self.assertEqual(status, 200, got)
            lines = [n for n in got["notes"] if n.startswith("Left out to keep this question under the size limit: ")]
            self.assertEqual(len(lines), 1, got["notes"])
            return int(re.search(r": ([0-9]+) passages?\.$", lines[0]).group(1))

        request_only = number(0)
        self.assertGreaterEqual(request_only, 1)                 # the request cut leaves something out on its own
        self.assertEqual(number(3), request_only + 3)            # and the project cut of 3 is added to it, not dropped and not alone

    def test_the_notes_come_in_one_fixed_order_with_the_size_limit_line_after_the_report_line(self):
        """The order of the reply notes: earlier messages, secret, report too long, size limit, counts, folders, hidden characters."""
        with mock.patch.object(ask, "dropped_note", return_value="N1-DROPPED"), mock.patch.object(ask, "secret_note", return_value="N2-SECRET"), \
                mock.patch.object(ask_service, "left_out_note", return_value="N3-REPORT"), mock.patch.object(ask, "left_out_text", side_effect=lambda c: "N4-SIZE-%d" % c), \
                mock.patch.object(ask_data, "left_out_lines", return_value=["N5-COUNTS"]), mock.patch.object(ask_service, "folder_notes", return_value=["N6-FOLDER"]), \
                mock.patch.object(ask_service, "hidden_notes", return_value=["N7-HIDDEN"]), mock.patch.object(ask, "MAX_PASSAGES", 1):
            status, got = self.question("what is late?")
        self.assertEqual(status, 200, got)
        ours = [n for n in got["notes"] if n.startswith("N") and n[1:2].isdigit()]
        self.assertEqual(len(ours), 7, got["notes"])
        self.assertEqual([n[:2] for n in ours], ["N1", "N2", "N3", "N4", "N5", "N6", "N7"], got["notes"])
        self.assertEqual([n for n in ours if n.startswith("N4")][0] != "N4-SIZE-0", True, ours)      # the request cut reached it as a count

    def test_a_count_that_is_not_a_whole_number_of_one_or_more_gives_no_line(self):
        for bad in (True, False, 0, -1, 1.0, "2", None):
            self.assertEqual(ask.left_out_text(bad), "", repr(bad))
            self.assertEqual(ask_service.left_out_note(bad), "", repr(bad))

    def test_the_reply_notes_say_1_passage_and_n_passages(self):
        counts = {}
        for keep in range(1, 12):
            with mock.patch.object(ask_service, "folder_notes", return_value=[]), mock.patch.object(ask, "MAX_PASSAGES", keep):
                status, got = self.question("what is late?")
            self.assertEqual(status, 200, got)
            for n in got["notes"]:
                m = re.match(r"Left out to keep this question under the size limit: (\d+) (passages?)\.$", n)
                if m:
                    counts[int(m.group(1))] = m.group(2)
        self.assertEqual(counts.get(1, "passage"), "passage", counts)
        self.assertTrue(counts and all(w == ("passage" if k == 1 else "passages") for k, w in counts.items()), counts)
        self.assertIn(1, counts, counts)
        self.assertIn(2, counts, counts)

    def test_a_file_cut_and_a_request_cut_are_both_said_in_their_own_words(self):
        folder = ask_passages.FolderData(passages=(ask.Passage("a.md", "plan one"), ask.Passage("b.md", "plan two"), ask.Passage("c.md", "plan three")), left_out=2)
        with mock.patch.object(ask_service.ask_passages, "folder_data", return_value=folder), mock.patch.object(ask_service, "folder_notes", return_value=[]), \
                mock.patch.object(ask, "MAX_PASSAGES", 100):
            status, base = self.question("what is late?")
        self.assertEqual(status, 200, base)
        with mock.patch.object(ask_service.ask_passages, "folder_data", return_value=folder), mock.patch.object(ask_service, "folder_notes", return_value=[]):
            with mock.patch.object(ask, "MAX_PASSAGES", 2):
                status, got = self.question("what is late?")
        self.assertEqual(status, 200, got)
        old = [n for n in got["notes"] if "too long to send in full" in n]
        new = [n for n in got["notes"] if n.startswith("Left out to keep this question under the size limit: ")]
        self.assertEqual(old, [ask_service.left_out_note(2)], got["notes"])
        self.assertEqual(len(new), 1, got["notes"])
        self.assertRegex(new[0], r": [1-9][0-9]* passages?\.$")
        self.assertEqual(ask_service.left_out_note(2), "Some of the report was too long to send in full, so only the parts closest to your question were used.")
        self.assertEqual(ask_service.left_out_note(0), "")
        self.assertFalse([n for n in base["notes"] if n.startswith("Left out to keep")], base["notes"])
        self.assertEqual([n for n in base["notes"] if "too long to send in full" in n], [ask_service.left_out_note(2)], base["notes"])      # files cut, request not cut
        with mock.patch.object(ask_service, "folder_notes", return_value=[]), mock.patch.object(ask, "MAX_PASSAGES", 1):
            status, only = self.question("what is late?")                                                                                  # request cut, no file cut
        self.assertEqual(status, 200, only)
        self.assertFalse([n for n in only["notes"] if "too long to send in full" in n], only["notes"])
        self.assertTrue([n for n in only["notes"] if n.startswith("Left out to keep")], only["notes"])

    def test_the_folders_get_what_the_project_left_of_the_whole_budget(self):
        from clark import ask_passages
        with mock.patch.object(ask_passages, "folder_data", wraps=ask_passages.folder_data) as spy:
            status, got = self.question("what is late?")
        self.assertEqual(status, 200, got)
        budget = spy.call_args[0][3]
        self.assertLess(budget, ask.BUDGET)                          # the project's own passages came off it
        self.assertGreater(budget, ask_service.PROJECT_SHARE)        # and the folders may use more than the project's share of what is left

    def test_a_whole_project_gives_no_counts_line(self):
        status, got = self.question("what is late?")
        self.assertEqual(status, 200, got)
        self.assertFalse([n for n in got["notes"] if n.startswith("Sent ")], got["notes"])


if __name__ == "__main__":
    unittest.main()
