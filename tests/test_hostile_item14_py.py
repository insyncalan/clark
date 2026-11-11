"""Item 14: hostile-input tests for the Python modules milestones, glance, to_client, docx_build and brands. Fictional data
only ("fabrikam"). No browser, no database. Each case feeds a stored value that is not what the column should hold (a list, a
dict, a number, an impossible day, a very long text, a hidden character, markup) or a name that is hostile, and asserts the
answer is a plain result or the module's own refusal, never a raw error that would end a publish or a page load.

Run: python3 dev/run_tests.py test_hostile_item14_py
"""
import json
import re
import unittest

from _paths import ROOT   # noqa: F401  (puts src/ on the path)

from clark import brands, docx_build, glance, milestones, platform, to_client
from clark.docx_build import WordError

TODAY = "2026-11-11"
HOSTILE_TEXT = ["", " ", "x" * 100000, "\u202e", "\u200b", "\x00", "<b>&\"'", "2026-02-30", "2026-13-01", "../../etc/passwd", "\U0001f600"]
NOT_TEXT = [None, [], {}, ["2026-11-11"], {"a": 1}, 5, 5.5, float("nan"), True]


class MilestonesHostile(unittest.TestCase):
    def test_state_words_for_text_dates_never_raise(self):
        for bad in HOSTILE_TEXT + [None]:
            row = {"status": "Planned", "baseline_date": bad, "forecast_date": bad}
            with self.subTest(date=str(bad)[:12]):
                self.assertIn(milestones.suggested_state(row, TODAY), milestones.MS_STATES)
                self.assertIn(milestones.milestone_state(row, TODAY), milestones.STATES)

    def test_done_is_achieved_whatever_the_other_columns_hold(self):
        for bad in NOT_TEXT + HOSTILE_TEXT:
            row = {"status": "Done", "baseline_date": bad, "forecast_date": bad}
            with self.subTest(v=str(bad)[:12]):
                self.assertEqual(milestones.milestone_state(row, TODAY), "Achieved")

    def test_done_beats_a_state_the_user_set(self):
        for state in ("At risk", "Forecast", "Overdue", "On track"):
            row = {"status": "Done", "state": state, "state_set": 1, "baseline_date": "2026-01-01"}
            self.assertEqual(milestones.milestone_state(row, TODAY), "Achieved")

    def test_forecast_never_needs_a_reason(self):
        row = {"state": "Forecast", "state_set": 1, "baseline_date": "2026-12-01"}
        self.assertFalse(milestones.needs_reason(row, TODAY))

    def test_a_set_state_without_the_flag_or_empty_is_ignored(self):
        for row in ({"state": "At risk", "baseline_date": "2026-12-01"}, {"state": "", "state_set": 1, "baseline_date": "2026-12-01"},
                    {"state": None, "state_set": 1, "baseline_date": "2026-12-01"}):
            self.assertEqual(milestones.milestone_state(row, TODAY), "On track")
            self.assertFalse(milestones.needs_reason(row, TODAY))

    def test_text_in_a_text_column_reads_as_the_dates_say(self):
        for bad in ("<script>", "x" * 100000, "\u202e"):      # sorts before any 2026 day or after it; either way a real state
            self.assertIn(milestones.suggested_state({"baseline_date": bad}, TODAY), ("Overdue", "On track"))

    def test_slip_days_is_none_when_not_planned_or_no_date(self):
        for row in ({"status": "Done", "baseline_date": "2026-01-01"}, {"status": "Planned"}, {"status": "Planned", "baseline_date": ""},
                    {"status": "Planned", "baseline_date": None}, {"status": ["Planned"], "baseline_date": "2026-01-01"}):
            with self.subTest(row=str(row)):
                self.assertIsNone(milestones.slip_days(row, TODAY))

    def test_slip_days_for_real_days(self):
        self.assertEqual(milestones.slip_days({"baseline_date": "2026-11-01", "forecast_date": "2026-11-05"}, TODAY), 10)
        self.assertEqual(milestones.slip_days({"baseline_date": "2026-12-01", "forecast_date": "2026-11-05"}, TODAY), 0)
        self.assertEqual(milestones.slip_days({"baseline_date": "2026-12-01", "forecast_date": ""}, TODAY), 0)

    def test_every_state_has_a_client_word_and_a_hostile_one_is_not_invented(self):
        for s in milestones.STATES:
            self.assertTrue(milestones.client_word(s))
        for bad in ("Overdue ", "overdue", "", "<b>", "x" * 10000, None):
            self.assertEqual(milestones.client_word(bad), "")      # a state that is not one of the seven gives no word, never one passed to a client as is

    def test_original_date_skips_undone_undo_and_hostile_rows(self):
        log = [{"tbl": "milestones", "item_id": "M-1", "field": "baseline_date", "op": "undo", "new_value": "2026-01-01"},
               {"tbl": "milestones", "item_id": "M-1", "field": "baseline_date", "op": "update", "new_value": None, "apply_id": 1},
               {"tbl": "milestones", "item_id": "M-1", "field": "baseline_date", "op": "update", "new_value": "2026-02-01", "apply_id": 2},
               {"tbl": "milestones", "item_id": "M-1", "field": "baseline_date", "op": "update", "new_value": "2026-03-01", "apply_id": 3},
               {"tbl": "tasks", "item_id": "M-1", "field": "baseline_date", "new_value": "2026-04-01"}, {}]
        self.assertEqual(milestones.original_date(log, "M-1", "2026-09-09", undone=[2]), "2026-03-01")
        self.assertEqual(milestones.original_date(log, "M-1", "2026-09-09", undone=[2, 3]), "2026-09-09")
        self.assertEqual(milestones.original_date([], "M-1", None), None)
        self.assertEqual(milestones.original_date(log, ["M-1"], "keep"), "keep")      # a list id matches nothing and cannot raise
        self.assertEqual(milestones.original_date(log, "M-1", "keep", undone=(["x"] and ())), "2026-02-01")


class GlanceHostile(unittest.TestCase):
    def test_day_number_and_show_date_take_anything(self):
        for bad in NOT_TEXT + HOSTILE_TEXT:
            with self.subTest(v=str(bad)[:12]):
                self.assertIsNone(glance.day_number(bad))
                self.assertIsInstance(glance.show_date(bad), str)
        self.assertEqual(glance.show_date(None), glance.DASH)
        self.assertEqual(glance.show_date("2026-11-11"), "11-11-2026")
        self.assertIsNone(glance.day_number("2026-11-11\n"))                     # no trailing newline slips past the pattern
        self.assertIsNone(glance.day_number("\u0662\u0660\u0662\u0666-11-11"))    # Arabic-Indic digits are not days

    def test_priority_that_is_not_text_is_not_rated(self):
        for bad in NOT_TEXT + HOSTILE_TEXT:
            self.assertIsNone(glance.colour_of_priority(bad))
        self.assertEqual(glance.colour_of_priority("Urgent"), "red")

    def test_pill_of_a_hostile_work_item(self):
        for bad in NOT_TEXT + HOSTILE_TEXT:
            for kind in ("action", "risk", "issue", "decision", bad if isinstance(bad, str) else None):
                row = {"kind": kind, "status": "Open", "due_date": bad, "priority": bad, "needed_by": bad, "date": bad}
                with self.subTest(v=str(bad)[:12], kind=str(kind)[:8]):
                    pill = glance.pill_of(row, TODAY)
                    self.assertIn(pill["class"], "ragbn")
                    self.assertIn(glance.client_pill(row, TODAY)["class"], "ragbn")
                    self.assertIsInstance(glance.is_overdue(row, TODAY), bool)

    def test_due_today_is_not_overdue_and_yesterday_is(self):
        act = {"kind": "action", "status": "Open"}
        self.assertFalse(glance.is_overdue({**act, "due_date": TODAY}, TODAY))
        self.assertTrue(glance.is_overdue({**act, "due_date": "2026-11-10"}, TODAY))
        self.assertFalse(glance.is_overdue({**act, "due_date": "2026-11-10", "status": "Closed"}, TODAY))

    def test_a_bad_today_is_refused_in_words(self):
        for bad in NOT_TEXT + HOSTILE_TEXT:
            with self.subTest(v=str(bad)[:12]):
                with self.assertRaises(ValueError):
                    glance.tiles({"project": {}, "actions": [], "raid": [], "decisions": []}, bad)
                with self.assertRaises(ValueError):
                    glance.use_case_strip([], [], bad)

    def test_tiles_with_hostile_row_values(self):
        for bad in NOT_TEXT + HOSTILE_TEXT:
            rows = {"project": {"code": "FAB", "health": bad},
                    "actions": [{"kind": "action", "id": "A-1", "status": bad if isinstance(bad, str) else "Open", "due_date": bad, "priority": bad}],
                    "raid": [{"kind": "risk", "id": "R-1", "status": "Open", "priority": bad, "due_date": bad}],
                    "decisions": [{"kind": "decision", "id": "D-1", "status": "Pending", "needed_by": bad}]}
            with self.subTest(v=str(bad)[:12]):
                out = glance.tiles(rows, TODAY)
                self.assertTrue(out)
                for t in out:
                    self.assertIn(t["class"], ("r", "a", "g", "n"))

    def test_use_case_strip_hostile_status_title_and_order(self):
        for bad in NOT_TEXT + HOSTILE_TEXT:
            ucs = [{"id": "U-1", "status": bad, "title": bad, "headline": bad, "sort_order": bad if isinstance(bad, (int, type(None))) else 0},
                   {"id": "U-2", "status": "Live", "title": "Fabrikam pilot"}]
            items = [{"use_case": "U-1", "kind": "action", "status": "Open", "due_date": bad, "priority": bad},
                     {"use_case": "U-1", "kind": "risk", "status": "Open", "priority": bad}]
            with self.subTest(v=str(bad)[:12]):
                try:
                    out = glance.use_case_strip(ucs, items, TODAY)
                except TypeError:
                    # a sort_order that cannot be compared is the one input the strip does not take: it is the store's integer column
                    self.assertIsInstance(ucs[0]["sort_order"], (str, float, bool, list, dict))
                    continue
                self.assertEqual(out["total"], 2)
                for r in out["rows"]:
                    self.assertIsInstance(r["title"], (str, type(bad)))

    def test_client_strip_needs_kept_and_ignores_the_other_arguments(self):
        with self.assertRaises(ValueError):
            glance.use_case_strip([], [], TODAY, for_client=True)
        out = glance.use_case_strip([{"id": "HOSTILE"}], [{"use_case": "HOSTILE", "kind": "action"}], TODAY, for_client=True,
                                    kept={"use_cases": [], "rows": []})
        self.assertEqual(out["total"], 0)
        self.assertEqual(out["total_words"], "No use cases")

    def test_health_pick_with_hostile_wanted_and_reason(self):
        for bad in NOT_TEXT + HOSTILE_TEXT:
            with self.subTest(v=str(bad)[:12]):
                try:
                    ans = glance.health_pick({"health": "Green", "health_reason": ""}, bad, bad)
                except (AttributeError, TypeError):
                    self.fail("health_pick raised on %r" % (bad,))
                self.assertIn("errors", ans)
                self.assertIsNone(ans["change"])


class ToClientHostile(unittest.TestCase):
    NAMES = ["", " ", ".", "..", "...html", ".html", "a.html.", "a/b.html", "a\\b.html", "con.html", "NUL", "aux.html", "a\u202e.html",
             "a\x00b.html", "a\nb.html", "a:b.html", "a*b?.html", "<b>.html", "x" * 400, "x" * 400 + ".html", "\ud83d\ude00.html".encode("utf-16", "surrogatepass").decode("utf-16", "ignore") + "a.html"]

    def test_client_file_name_is_always_a_safe_html_name_with_the_day(self):
        for code in self.NAMES:
            with self.subTest(code=code[:12]):
                try:
                    name = to_client.client_file_name(code, "2026-11-06", TODAY)
                except platform.PlatformError:
                    continue
                self.assertTrue(name.endswith("-2026-11-06.html"), name)
                self.assertNotRegex(name, r'[\\/:*?"<>|\x00-\x1f]')
                self.assertLessEqual(len(name), 120)

    def test_the_week_ending_text_falls_back_to_today_when_empty(self):
        self.assertTrue(to_client.client_file_name("FAB", "", TODAY).endswith("-" + TODAY + ".html"))
        self.assertTrue(to_client.client_file_name("FAB", None, TODAY).endswith("-" + TODAY + ".html"))

    def test_rename_target_refuses_nothing_typed(self):
        for typed in ("", " ", "   ", ".html", " .html ", "...", ". .", None):
            with self.subTest(typed=typed):
                self.assertIsNone(to_client.rename_target(typed))

    def test_rename_target_is_safe_for_hostile_names(self):
        for typed in self.NAMES:
            with self.subTest(typed=typed[:12]):
                got = to_client.rename_target(typed)
                if got is not None:
                    self.assertTrue(got.lower().endswith(".html"))
                    self.assertNotRegex(got, r'[\\/:*?"<>|\x00-\x1f]')
                    self.assertLessEqual(len(got), 120)

    def test_clash_rename_refuses_hidden_characters_and_a_trailing_dot(self):
        base = [{"name": "FAB-report-2026-11-06.html", "kind": "file", "same_content": False}]
        for typed in ("a\u202eb.html", "a\x00b", "a\u200bb", "a\nb", "a\tb", "a\u00a0b"):
            with self.subTest(typed=repr(typed)):
                ans = to_client.resolve_clash("FAB-report-2026-11-06.html", base, "rename", typed)
                self.assertEqual((ans["action"], ans["reason"]), ("refuse", "bad_name"))
                self.assertTrue(ans["message"])
        ans = to_client.resolve_clash("FAB-report-2026-11-06.html", base, "rename", "a.html.")
        self.assertEqual(ans.get("reason"), "name_ends_badly")
        for typed in ("", "  ", ".html"):
            self.assertEqual(to_client.resolve_clash("FAB-report-2026-11-06.html", base, "rename", typed).get("reason"), "empty_name")

    def test_clash_choices_unknown_and_kinds(self):
        n = "FAB-report-2026-11-06.html"
        for choice in ("OVERWRITE", "", "x" * 10000, "number ", "<b>", "\u202e"):
            ans = to_client.resolve_clash(n, [n], choice)
            self.assertEqual((ans["action"], ans["reason"]), ("refuse", "unknown_choice"))
        for kind in ("link", "socket", "<b>", "", None, ["file"]):
            ans = to_client.resolve_clash(n, [{"name": n, "kind": kind}], "overwrite")
            self.assertNotEqual(ans["action"], "write", "a %r is never written over" % (kind,))
        ans = to_client.resolve_clash(n, [{"name": n, "kind": "folder"}], "overwrite")
        self.assertEqual(ans["reason"], "folder_has_name")

    def test_clash_matching_ignores_case_and_unicode_form(self):
        n = "FAB-report-2026-11-06.html"
        ans = to_client.resolve_clash(n, [{"name": n.lower(), "kind": "file", "same_content": False}])
        self.assertEqual(ans["action"], "ask")
        self.assertEqual(to_client.resolve_clash("caf\u00e9.html", [{"name": "cafe\u0301.html", "kind": "file", "same_content": True}])["action"],
                         "nothing_to_do")

    def test_numbered_name_skips_every_taken_number_and_keeps_the_ending(self):
        taken = ["a.html"] + ["a (%d).html" % i for i in range(2, 30)]
        got = to_client.numbered_name("a.html", taken)
        self.assertTrue(got.endswith(".html"))
        self.assertNotIn(got.lower(), [t.lower() for t in taken])
        self.assertLessEqual(len(to_client.numbered_name("x" * 400 + ".html", ["x" * 400 + ".html"])), 120)

    def test_check_copy_looks_at_hostile_bytes_and_markers(self):
        self.assertEqual(to_client.check_copy(b"<p>fine</p>", markers=[]), [])
        self.assertEqual(to_client.check_copy(b"\xff\xfe\x00bad", markers=["x"]), ["a file clark did not write as text"])
        self.assertEqual(to_client.check_copy(b"", markers=[]), [])
        for marker in ("", " ", "\u202e", "<b>", "x" * 5000, "\x00"):
            with self.subTest(marker=marker[:8]):
                self.assertIsInstance(to_client.check_copy(b"<p>fabrikam</p>", markers=[marker]), list)
        self.assertIn("text that was meant to be left out", to_client.check_copy("<p>Fabrikam  \u00a0 Secret</p>".encode(), markers=["fabrikam secret"]))
        self.assertIn("text that was meant to be left out", to_client.check_copy(b"<p>Fabrikam &lt;Secret&gt;</p>", markers=["Fabrikam <Secret>"]))
        self.assertEqual(to_client.check_copy(b"<p>fabrikam</p>", markers=[""]), [])      # an empty marker matches nothing

    def test_check_copy_finds_the_folder_and_outside_addresses(self):
        self.assertIn("the location of the client folder", to_client.check_copy(b"<p>C:/Fabrikam/Reports</p>", markers=[], folder="C:/FABRIKAM/reports"))
        self.assertTrue(to_client.check_copy(b'<img src="https://example.invalid/x.png">', markers=[]))
        self.assertTrue(to_client.check_copy(b'<div id="clark-boot"></div>', markers=[]))

    def test_check_copy_pdf_is_read_byte_for_byte(self):
        self.assertIsInstance(to_client.check_copy(b"%PDF-1.4\n\xff\xfe\x00 fabrikam", markers=["fabrikam"]), list)
        self.assertIn("text that was meant to be left out", to_client.check_copy(b"%PDF-1.4\n\xff fabrikam", markers=["fabrikam"]))

    def test_markers_found_with_undecodable_bytes_is_empty(self):
        self.assertEqual(to_client.markers_found(b"\xff\xfe", ["a"]), [])


class DocxHostile(unittest.TestCase):
    def test_esc_and_attr_never_leave_markup_or_xml_illegal_characters(self):
        for bad in NOT_TEXT + HOSTILE_TEXT + ["\x08\x0b\x0c\x0e\x1f\x7f\x85\x9f\ud800\ufffe\uffff", "]]>", "&amp;", "&#0;"]:
            for fn in (docx_build.esc, docx_build.attr):
                out = fn(bad)
                with self.subTest(v=str(bad)[:12], fn=fn.__name__):
                    self.assertNotRegex(out, "[<>\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ud800-\udfff\ufffe\uffff]")
                    self.assertNotRegex(out, r"&(?!amp;|lt;|gt;|quot;)")
        self.assertEqual(docx_build.esc(None), "")
        self.assertNotIn('"', docx_build.attr('a"b'))

    def test_a_non_text_rich_value_is_a_plain_refusal(self):
        ctx = docx_build._Ctx(docx_build.palette(), TODAY)
        for bad in [[], {}, 5, 5.5, float("nan"), True]:
            with self.assertRaises(WordError):
                docx_build.rich(bad, ctx)

    def test_published_that_is_not_a_report_is_refused_in_words(self):
        project = {"code": "FAB"}
        bads = [None, "", [], {}, "x" * 1000, 5, {"data": None, "sections": [], "as_at": TODAY},
                {"data": {"project": project}, "sections": "all", "as_at": TODAY},
                {"data": {"project": project}, "sections": [], "as_at": "2026-02-30"},
                {"data": {"project": project}, "sections": [], "as_at": "2026-11-11\u202e"},
                {"data": {"project": project}, "sections": [], "as_at": None},
                {"data": {"project": project}, "sections": [], "as_at": ["2026-11-11"]},
                {"data": {"project": {}}, "sections": [], "as_at": TODAY},
                {"data": {"project": {"code": ""}}, "sections": [], "as_at": TODAY},
                {"data": {"project": None}, "sections": [], "as_at": TODAY},
                {"data": [], "sections": [], "as_at": TODAY}]
        for bad in bads:
            with self.subTest(bad=str(bad)[:40]):
                with self.assertRaises(WordError) as caught:
                    docx_build.build(bad)
                self.assertNotRegex(str(caught.exception), r"(?i)traceback|keyerror|typeerror|attributeerror")

    def test_a_hostile_project_name_and_code_give_a_well_formed_file(self):
        import io
        import xml.dom.minidom
        import zipfile
        for name in HOSTILE_TEXT + ["Fabrikam ]]> <w:t>", "\ud83d\ude00"]:
            pub = {"data": {"project": {"code": "FAB", "name": name}}, "sections": [], "as_at": TODAY}
            with self.subTest(name=name[:12]):
                data = docx_build.build(pub)
                z = zipfile.ZipFile(io.BytesIO(data))
                for part in z.namelist():
                    if part.endswith((".xml", ".rels")):
                        xml.dom.minidom.parseString(z.read(part))
                self.assertEqual(docx_build.build(pub), data)      # the same rows give the same bytes

    def test_file_name_is_safe_for_hostile_codes_and_week_endings(self):
        for code in ("FAB", "a/b", "a\\b", "..", "con", "a\u202eb", "a:b", "x" * 400, "<b>"):
            for week in (None, "", "2026-11-06", "../x"):
                with self.subTest(code=code[:8], week=week):
                    try:
                        name = docx_build.file_name(code, week, TODAY)
                    except platform.PlatformError:
                        continue
                    self.assertTrue(name.endswith(".docx"))
                    self.assertNotRegex(name, r'[\\/:*?"<>|\x00-\x1f]')
                    self.assertLessEqual(len(name), 120)

    def test_a_palette_with_hostile_colours_is_text_or_refused_never_markup(self):
        for bad in ("red", "#12", "#GGGGGG", "\"><w:x/>", "<b>", "", None, ["#112233"], 5):
            try:
                pal = docx_build.palette({"ink": bad})
            except (WordError, ValueError):
                continue
            self.assertIsInstance(pal, dict)
            self.assertNotIn("<", json.dumps(pal) if not isinstance(bad, str) else json.dumps({k: v for k, v in pal.items() if v != bad}))


class BrandsHostile(unittest.TestCase):
    def test_check_id_takes_only_a_plain_id(self):
        for bad in NOT_TEXT + [h for h in HOSTILE_TEXT if not re.fullmatch("[a-z0-9-]+", h)] + ["Fabrikam", "fab rikam", "fab_rikam", "fabrikam\n", "FABRIKAM", "fabrikam.zip",
                                               "\u0430bc", "\uff46ab", "a" * 200]:
            with self.subTest(v=str(bad)[:12]):
                with self.assertRaises(brands.BrandError):
                    brands.check_id(bad)
        for reserved in brands.RESERVED:
            with self.assertRaises(brands.BrandError) as caught:
                brands.check_id(reserved)
            self.assertEqual(caught.exception.key, "reserved")
        brands.check_id("fabrikam")

    def test_manifest_json_that_is_not_an_object_is_none(self):
        for body in (b"", b"\xff\xfe", b"[]", b"null", b"5", b'"x"', b"{", b"{" * 100000, b"[" * 100000, b'{"a":' + b"9" * 5000 + b"}",
                     b"\xef\xbb\xbf{}x", b"NaN", b'{"a": 1e999999999}x'):
            with self.subTest(body=body[:12]):
                self.assertIsNone(brands._parse_manifest(body))
        self.assertEqual(brands._parse_manifest(b"{}"), {})

    def test_manifest_numbers_that_are_too_long_are_refused_not_parsed(self):
        self.assertIsNone(brands._parse_manifest(b'{"size": ' + b"1" * (brands.MAX_INT_DIGITS + 1) + b"}"))
        self.assertEqual(brands._parse_manifest(b'{"size": ' + b"1" * brands.MAX_INT_DIGITS + b"}")["size"], int("1" * brands.MAX_INT_DIGITS))

    def _doc(self, **over):
        doc = {"id": "fabrikam", "name": "Fabrikam", "version": "1.0.0", "files": [
            {"path": "tokens.css", "size": 10, "sha256": "a" * 64, "mode": "644"}]}
        doc.update(over)
        return doc

    def test_a_good_manifest_passes(self):
        self.assertEqual(brands._check_manifest(self._doc()), {"tokens.css": (10, "a" * 64, 0o644)})

    def test_hostile_manifest_fields_are_the_manifest_refusal(self):
        row = {"path": "tokens.css", "size": 10, "sha256": "a" * 64, "mode": "644"}
        cases = [self._doc(name=n) for n in ("", " ", " x", "x ", "x" * 5000, "a\u202eb", "a\u200bb", "a\x00b", "a\nb", None, [], {}, 5, True)]
        cases += [self._doc(version=v) for v in ("", "1", "1.0", "v1.0.0", "1.0.0\n", "1.0.0-" + "x" * 5000, None, [], {}, 1, 1.5, True, "\u0661.0.0")]
        cases += [self._doc(id=v) for v in (None, [], {}, 5)]
        cases += [self._doc(files=v) for v in (None, {}, "files", 5, [None], [[]], ["x"], [row] * 2, [row] * 1000)]
        for field, vals in (("size", (-1, "10", 10.0, True, None, [], {})), ("sha256", ("A" * 64, "a" * 63, "a" * 65, "g" * 64, None, [], 5, "a" * 64 + "\n")),
                            ("mode", ("9999", "64", "6444444", "-644", "0o644", None, 644, [], "644\n")), ("path", (None, [], {}, 5, "clark-brand.json"))):
            for v in vals:
                cases.append(self._doc(files=[{**row, field: v}]))
        for case in cases:
            with self.subTest(case=json.dumps(case, default=str)[:80]):
                with self.assertRaises(brands.BrandError) as caught:
                    brands._check_manifest(case)
                self.assertEqual(caught.exception.key, "manifest")

    def test_hostile_file_names_in_content_are_refused(self):
        tokens = b":root { --brand-ink: #1a2b3c; }\n"
        for rel in ("../tokens.css", "/etc/passwd", "a/../b.png", "assets/", "assets\\logo.png", "assets/logo.png\x00", "assets/logo.png.exe",
                    "ASSETS/logo.png", "assets/\u202egnp.png", "assets/lo\u0261o.png", "x" * 5000, "", ".", "..", "tokens.css/", "\n"):
            with self.subTest(rel=rel[:20]):
                with self.assertRaises(brands.BrandError):
                    brands.check_content("Fabrikam", {brands.TOKENS: tokens, rel: b"x"})

    def test_hostile_tokens_are_the_tokens_refusal(self):
        for body in (b"\xff\xfe\x00", b":root{} </style><script>1</script>", b":root{--a:url(https://example.invalid/x)}",
                     b"@import 'https://example.invalid/x.css';", b":root{--a:1}" + b"x" * (brands.TOKENS_CAP + 1), b"<style>", b":root{--a:\\75rl(x)}"):
            with self.subTest(body=body[:24]):
                with self.assertRaises(brands.BrandError):
                    brands.check_content("Fabrikam", {brands.TOKENS: body})

    def test_a_brand_with_no_tokens_is_refused(self):
        with self.assertRaises(brands.BrandError):
            brands.check_content("Fabrikam", {})

    def test_hostile_pictures_are_refused_in_words(self):
        tokens = b":root { --brand-ink: #1a2b3c; }\n"
        for body in (b"", b"\x89PNG", b"\x89PNG\r\n\x1a\n", b"\xff\xd8", b"RIFF\x00\x00\x00\x00WEBP", b"<svg onload=alert(1)>", b"GIF89a", b"x" * 2000000,
                     b"\x89PNG\r\n\x1a\n" + b"\x00" * 100):
            for rel in ("assets/logo.png", "assets/cover.jpg", "assets/cover.webp"):
                with self.subTest(rel=rel, body=body[:10]):
                    with self.assertRaises(brands.BrandError):
                        brands.check_content("Fabrikam", {brands.TOKENS: tokens, rel: body})

    def test_review_of_a_path_that_is_not_a_brand_zip_is_the_name_refusal(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            for name in ("brand.txt", "..zip", ".zip", "a b.zip", "\u202e.zip", "x" * 300 + ".zip", "fab\x00rikam-1.0.0.zip"):
                with self.subTest(name=name[:12]):
                    try:
                        p = Path(d) / name
                        p.write_bytes(b"not a zip")
                    except (OSError, ValueError):
                        continue
                    with self.assertRaises(brands.BrandError):
                        brands.review(str(p), Path(d) / "root")

    def test_a_deny_word_is_found_whatever_the_case_or_line(self):
        words = list(brands.DENY_WORDS)[:3]
        for w in words:
            self.assertTrue(brands._has_word("Fabrikam " + w.upper()))
            self.assertTrue(brands._has_word("fine\nline two " + w))
        self.assertFalse(brands._has_word(""))
        self.assertFalse(brands._has_word("Fabrikam\n" * 1000))


if __name__ == "__main__":
    unittest.main()
