"""Row 926: the client-leak gate for the Gantt (src/clark/publish.py, guarded). Fictional data only.

One rule, decided in publish.select before anything is copied, so every client file made from its output (the published page, its Word
copy, the PDF's page, the client workbook, the ask-clark feed) is gated alike: a line whose eye (`show`) is not 1 is dropped; the
columns in the project's gantt_hidden_columns are not in the copy at all (not hidden by a style); a dependency on a dropped line is
dropped; the Gantt tab is in the file only when show_gantt_client is 1 AND at least one eye-on line is left. The editor's own read keeps
everything. Every value is checked again at publish time, so a row written around the writer cannot get through.

Run: python3 dev/run_tests.py test_gantt_publish
"""
import copy
import json
import unittest

import _publish_fixture as fixture
from _demo import USER, DemoStore
from _paths import SRC  # noqa: F401
from clark import changes, publish, store as store_module

PH, A, B, C, D = (f"PUB-GNT-00{n}" for n in range(1, 6))
SECRET = "ZQ-EYE-OFF-LINE"
NAME = fixture.load()["data"]["project"]["name"]
SECRET_NOTE, SECRET_BUDGET = "ZQ-INTERNAL-NOTE", 424242.5


def line(ident, name, **kw):
    base = {"id": ident, "project": "PUB", "type": "task", "name": name, "parent": None, "start": "2026-11-02", "end": "2026-11-13", "pct": 10,
            "health": "Green", "depends": "", "owner": "A. Builder", "workstream": "Build", "priority": "High", "baseline_start": "2026-11-01",
            "baseline_end": "2026-11-12", "effort": 8.0, "budget": SECRET_BUDGET, "deliverable": "Trench", "show": 1, "note": SECRET_NOTE,
            "sort_order": (int(ident[-3:]) if isinstance(ident, str) and ident[-3:].isdigit() else 7) * 1024}
    base.update(kw)
    return base


def plant(lines=None, **project):
    """The publish plant with a Gantt added: a phase, two eye-on tasks and one eye-off task that the others depend on."""
    inputs = fixture.inputs()
    d = inputs["data"]
    d["project"].update(show_gantt_client=1, gantt_tab_name="Plan", gantt_title="", gantt_hidden_columns="show,note,budget,effort,baseline_start,baseline_end",
                        gantt_default_rows=None)
    d["project"].update(project)
    d["gantt_lines"] = lines if lines is not None else [
        line(PH, "Build", type="phase", parent=None),
        line(A, "Dig", parent=PH, depends=f"{D}"),
        line(B, "Pour", parent=PH, depends=f"{A},{D}"),
        line(D, SECRET, parent=PH, show=0),
    ]
    return inputs


def chosen(inputs):
    return publish.select(copy.deepcopy(inputs))


class TheGate(unittest.TestCase):
    def test_an_eye_off_line_is_in_no_part_of_the_client_copy(self):
        out = chosen(plant())
        text = json.dumps(out, ensure_ascii=False)
        self.assertNotIn(SECRET, text)
        self.assertNotIn(D, text)                                             # not even as a dependency, nor as a parent's child
        self.assertEqual([l["id"] for l in out["data"]["gantt"]["lines"]], [PH, A, B])

    def test_the_hidden_columns_are_not_in_the_copy_at_all(self):
        out = chosen(plant())
        g = out["data"]["gantt"]
        for key in ("show", "note", "budget", "effort", "baseline_start", "baseline_end"):
            self.assertNotIn(key, g["columns"])
            self.assertTrue(all(key not in l for l in g["lines"]), key)
        text = json.dumps(out, ensure_ascii=False)
        for secret in (SECRET_NOTE, "424242", "2026-11-01"):
            self.assertNotIn(secret, text)
        self.assertEqual(g["columns"][:2], ["id", "name"])
        self.assertTrue({"type", "parent", "start", "end", "pct", "health", "depends", "owner", "workstream", "priority", "deliverable"} <= set(g["columns"]))

    def test_the_project_chooses_which_columns_go(self):
        out = chosen(plant(gantt_hidden_columns="owner,health"))
        g = out["data"]["gantt"]
        self.assertNotIn("owner", g["columns"])
        self.assertNotIn("health", g["columns"])
        self.assertIn("note", g["columns"])                                    # shown now: not on the list
        self.assertEqual(g["lines"][0]["note"], SECRET_NOTE)
        self.assertTrue(all("owner" not in l and "health" not in l for l in g["lines"]))
        none_hidden = chosen(plant(gantt_hidden_columns=""))["data"]["gantt"]
        self.assertEqual(set(none_hidden["columns"]), set(publish.PUBLISH_FIELDS["gantt_lines"]))
        self.assertNotIn("show", none_hidden["columns"])                       # the eye is a gate, never a column

    def test_the_id_and_the_name_can_never_be_hidden_and_a_damaged_list_hides_the_default(self):
        g = chosen(plant(gantt_hidden_columns="id,name,owner"))["data"]["gantt"]
        self.assertTrue({"id", "name"} <= set(g["columns"]))
        self.assertNotIn("owner", g["columns"])
        for damaged in (None, 5, ["note"]):
            g = chosen(plant(gantt_hidden_columns=damaged))["data"]["gantt"]
            self.assertTrue(set(store_module.GANTT_DEFAULT_HIDDEN).isdisjoint(g["columns"]), damaged)

    def test_owner_is_hidden_where_nothing_is_saved_and_kept_where_a_list_is_saved(self):
        self.assertIn("owner", store_module.GANTT_DEFAULT_HIDDEN)
        for nothing_saved in (None, 5):
            g = chosen(plant(gantt_hidden_columns=nothing_saved))["data"]["gantt"]
            self.assertNotIn("owner", g["columns"], nothing_saved)
            self.assertNotIn("A. Builder", json.dumps(g), nothing_saved)
        saved = chosen(plant(gantt_hidden_columns="show,note,budget,effort,baseline_start,baseline_end"))["data"]["gantt"]
        self.assertIn("owner", saved["columns"])                               # a saved list is not changed by the new default
        for kept in ("type", "start", "end", "pct"):
            self.assertIn(kept, chosen(plant(gantt_hidden_columns=None))["data"]["gantt"]["columns"])

    def test_a_malformed_stored_list_hides_the_default_and_leaks_no_internal_column(self):
        for bad in ("NOTE,Budget", '["note"]', "note,nonsense", "id,name", "type", "start,end,pct", "Owner", "note;budget"):
            g = chosen(plant(gantt_hidden_columns=bad))["data"]["gantt"]
            text = json.dumps(g)
            for col in store_module.GANTT_DEFAULT_HIDDEN:
                self.assertNotIn(col, g["columns"], (bad, col))
            for secret in (SECRET_NOTE, str(SECRET_BUDGET), "A. Builder"):
                self.assertNotIn(secret, text, bad)
        empty = chosen(plant(gantt_hidden_columns=""))["data"]["gantt"]          # empty text is a choice: nothing is hidden
        self.assertIn("owner", empty["columns"])

    def test_blank_or_comma_only_text_hides_the_default_and_only_the_empty_text_hides_nothing(self):
        z = "\u200b"
        for blank in (" ", ",", ",,", ", ,", " , ", "\t", z, "," + z, "owner" + z, z + ",note" + z):
            g = chosen(plant(gantt_hidden_columns=blank))["data"]["gantt"]
            text = json.dumps(g)
            for col in store_module.GANTT_DEFAULT_HIDDEN:
                self.assertNotIn(col, g["columns"], (blank, col))
            for secret in (SECRET_NOTE, str(SECRET_BUDGET), "A. Builder"):
                self.assertNotIn(secret, text, repr(blank))
        self.assertIn("note", chosen(plant(gantt_hidden_columns=""))["data"]["gantt"]["columns"])

    def test_a_stored_list_that_names_start_end_pct_or_type_still_leaves_them_in_the_copy(self):
        g = chosen(plant(gantt_hidden_columns="type,start,end,pct,owner"))["data"]["gantt"]       # written before these four were un-hideable
        self.assertTrue({"type", "start", "end", "pct"} <= set(g["columns"]))
        self.assertNotIn("owner", g["columns"])
        for line in g["lines"]:
            self.assertIn("start", line)
            self.assertIn("end", line)

    def test_a_dependency_on_a_dropped_line_is_dropped_and_the_rest_stay(self):
        lines = {l["id"]: l for l in chosen(plant())["data"]["gantt"]["lines"]}
        self.assertEqual(lines[A]["depends"], [])
        self.assertEqual(lines[B]["depends"], [A])

    def test_a_task_under_a_dropped_phase_stands_alone_and_a_parent_is_always_a_phase_in_the_copy(self):
        lines = [line(PH, "Build", type="phase", show=0), line(A, "Dig", parent=PH), line(B, "Pour", parent=A)]
        got = {l["id"]: l for l in chosen(plant(lines))["data"]["gantt"]["lines"]}
        self.assertEqual((got[A]["parent"], got[B]["parent"]), (None, None))     # the dropped phase is not named; a task is no parent

    def test_the_tab_is_in_only_when_the_client_switch_is_on_and_a_line_has_its_eye_on(self):
        on = chosen(plant())
        self.assertIn("gantt", on["tabs"])
        self.assertEqual((on["data"]["gantt"]["tab_name"], on["data"]["gantt"]["title"]), ("Plan", NAME))
        off = chosen(plant(show_gantt_client=0))
        self.assertNotIn("gantt", off["tabs"])
        self.assertNotIn("gantt", off["data"])
        self.assertNotIn(SECRET, json.dumps(off))
        for switch in (2, True, "1", None):                                     # exactly 1, nothing that looks like it
            self.assertNotIn("gantt", chosen(plant(show_gantt_client=switch))["tabs"], switch)
        none_on = [line(PH, "Build", type="phase", show=0), line(A, "Dig", show=0)]
        out = chosen(plant(none_on))
        self.assertNotIn("gantt", out["tabs"])
        self.assertNotIn("gantt", out["data"])
        for eye in (0, 2, True, "1", None):
            self.assertNotIn("gantt", chosen(plant([line(A, "Dig", show=eye)]))["tabs"], eye)
        self.assertNotIn("gantt", chosen(plant([]))["tabs"])

    def test_the_other_tabs_are_as_they_were(self):
        without = fixture.inputs()
        base = publish.select(copy.deepcopy(without))
        withg = chosen(plant())
        self.assertEqual([t for t in withg["tabs"] if t != "gantt"], base["tabs"])
        self.assertEqual(withg["sections"], base["sections"])

    def test_the_project_block_carries_the_tab_name_and_title_only_with_the_tab(self):
        proj = chosen(plant(gantt_title="Rollout plan", gantt_default_rows=12))["data"]["project"]
        self.assertEqual((proj["gantt_tab_name"], proj["gantt_title"], proj["gantt_default_rows"]), ("Plan", "Rollout plan", 12))
        proj = chosen(plant(show_gantt_client=0))["data"]["project"]
        self.assertNotIn("gantt_tab_name", proj)
        self.assertNotIn("gantt_title", proj)
        self.assertNotIn("show_gantt_client", proj)                              # the switches decide; they are not copied
        self.assertNotIn("gantt_hidden_columns", chosen(plant())["data"]["project"])

    def test_an_empty_title_is_the_project_name_and_an_empty_tab_name_is_gantt(self):
        g = chosen(plant(gantt_title="", gantt_tab_name=""))["data"]["gantt"]
        self.assertEqual((g["title"], g["tab_name"]), (NAME, "Gantt"))

    def test_the_editors_input_is_not_changed_by_the_gate(self):
        inputs = plant()
        before = copy.deepcopy(inputs)
        publish.select(inputs)
        self.assertEqual(inputs, before)

    def test_the_allow_list_and_the_gate_columns(self):
        self.assertEqual(publish.GATES["gantt_lines"], ("show", "project"))
        self.assertNotIn("show", publish.PUBLISH_FIELDS["gantt_lines"])
        self.assertTrue(set(publish.PUBLISH_FIELDS["gantt_lines"]) <= {"id", "name", *store_module.GANTT_COLUMNS})
        self.assertTrue(set(publish.PUBLISH_FIELDS["gantt_lines"]).isdisjoint(store_module.NEVER_PUBLISH))


class Hostile(unittest.TestCase):
    def ids(self, lines, **project):
        return [l["id"] for l in chosen(plant(lines, **project))["data"].get("gantt", {"lines": []})["lines"]]

    def test_an_id_from_another_project_is_dropped_as_a_line_and_as_a_dependency_and_as_a_parent(self):
        lines = [line(PH, "Build", type="phase"), line("OTH-GNT-001", "Theirs", project="OTH"), line("OTH-GNT-002", "Theirs too"),
                 line(A, "Dig", parent="OTH-GNT-001", depends="OTH-GNT-001," + PH)]
        out = chosen(plant(lines))
        got = {l["id"]: l for l in out["data"]["gantt"]["lines"]}
        self.assertEqual(sorted(got), [PH, A])
        self.assertEqual((got[A]["parent"], got[A]["depends"]), (None, [PH]))
        self.assertNotIn("Theirs", json.dumps(out))

    def test_a_depends_loop_is_cut_and_nothing_hangs(self):
        lines = [line(A, "Dig", depends=f"{B}"), line(B, "Pour", depends=f"{C}"), line(C, "Cure", depends=f"{A},{C}")]
        got = {l["id"]: l for l in chosen(plant(lines))["data"]["gantt"]["lines"]}
        edges = {(k, d) for k, l in got.items() for d in l["depends"]}

        def reaches(a, b, seen=()):
            return any(d == b or (d not in seen and reaches(d, b, seen + (d,))) for k, d in edges if k == a)
        self.assertTrue(all(not reaches(k, k) for k in got), edges)
        self.assertNotIn((C, C), edges)
        self.assertGreaterEqual(len(edges), 2)                                   # the loop is cut at one edge, not everywhere

    def test_a_start_after_an_end_or_a_milestone_on_two_days_is_left_out(self):
        lines = [line(A, "Dig"), line(B, "Pour", start="2026-11-20", end="2026-11-01"), line(C, "Handover", type="milestone", start="2026-11-02", end="2026-11-09")]
        self.assertEqual(self.ids(lines), [A])

    def test_a_date_that_is_not_a_real_day_or_not_a_date_is_left_out(self):
        for bad in ("2026-02-30", "20261102", "02-11-2026", "", None, 5, "2026-11-2", "<b>"):
            self.assertEqual(self.ids([line(A, "Dig"), line(B, "Pour", start=bad)]), [A], bad)
            self.assertEqual(self.ids([line(A, "Dig"), line(B, "Pour", end=bad)]), [A], bad)

    def test_a_ten_thousand_character_note_is_cut_and_a_long_name_too(self):
        lines = [line(A, "N" * 10000, note="x" * 10000, owner="o" * 5000, deliverable="d" * 5000)]
        g = chosen(plant(lines, gantt_hidden_columns=""))["data"]["gantt"]["lines"][0]
        self.assertEqual((len(g["name"]), len(g["note"]), len(g["owner"]), len(g["deliverable"])), (200, 2000, 200, 500))

    def test_script_text_is_kept_as_text_and_never_as_markup_in_the_file(self):
        evil = '<script>alert(1)</script><img src=x onerror=alert(2)>'
        lines = [line(A, evil, owner=evil, workstream=evil, deliverable=evil, note=evil)]
        inputs = plant(lines, gantt_hidden_columns="", gantt_tab_name=evil, gantt_title=evil)
        out = chosen(inputs)
        g = out["data"]["gantt"]
        self.assertEqual(g["lines"][0]["name"], evil)                              # data is text: the page writes it as text
        block = publish.data_block(out, "2026-11-06", 1)
        self.assertNotIn("<script>alert(1)", block)
        self.assertNotIn("<img", block)
        self.assertIn("\\u003cscript", block)
        self.assertEqual(block.count("</script>"), 1)                              # only the block's own closing tag

    def test_a_deleted_parent_and_a_parent_that_is_not_a_phase(self):
        lines = [line(A, "Dig", parent="PUB-GNT-099"), line(B, "Pour", parent=A), line(C, "Cure", parent=None)]
        got = {l["id"]: l for l in chosen(plant(lines))["data"]["gantt"]["lines"]}
        self.assertEqual({k: l["parent"] for k, l in got.items()}, {A: None, B: None, C: None})

    def test_a_phase_never_has_a_parent_in_the_copy(self):
        lines = [line(PH, "Build", type="phase"), line(A, "Rollout", type="phase", parent=PH)]
        got = {l["id"]: l for l in chosen(plant(lines))["data"]["gantt"]["lines"]}
        self.assertIsNone(got[A]["parent"])

    def test_wrong_types_everywhere_do_not_break_the_gate(self):
        lines = [line(A, "Dig", pct="50", health="Purple", priority=7, effort="lots", budget=float("nan"), depends=5, parent=7, sort_order="x"),
                 line(B, None), line(C, "Cure", type="epic"), line(5, "Numbered"), line("ABC-GNT-001", "Wrong code"), line("PUB-GNT-1", "Short id"),
                 line(D, "Fine", pct=101)]
        got = {l["id"]: l for l in chosen(plant(lines, gantt_hidden_columns=""))["data"]["gantt"]["lines"]}
        self.assertEqual(sorted(got), sorted([A, D]))
        self.assertEqual((got[A]["pct"], got[A]["health"], got[A]["priority"], got[A]["effort"], got[A]["budget"], got[A]["depends"], got[A]["parent"]),
                         (0, "", "", None, None, [], None))
        self.assertEqual(got[D]["pct"], 0)

    def test_two_lines_with_one_id_publish_once_and_a_row_of_another_project_in_the_rows_is_not_read(self):
        lines = [line(A, "First"), line(A, "Second"), line(B, "Other", project="OTH")]
        got = chosen(plant(lines))["data"]["gantt"]["lines"]
        self.assertEqual([(l["id"], l["name"]) for l in got], [(A, "First")])

    def test_the_cut_off_lines_are_logged_by_id_only(self):
        with self.assertLogs("clark.publish", "WARNING") as logs:
            chosen(plant([line(A, "Dig"), line(B, "Secret name here", start="2026-12-31", end="2026-01-01")]))
        text = "\n".join(logs.output)
        self.assertIn(B, text)
        self.assertNotIn("Secret name here", text)


class FromTheStore(unittest.TestCase):
    """The same gate, from rows a real store gives (the editor's writer and publish.read_inputs)."""

    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        for kind, op, extra in (("projects", "update", {"changes": {"show_gantt_client": 1, "gantt_tab_name": "Plan"}}),):
            self.assertEqual(self.change({"project": "ABC", "kind": kind, "op": op, **extra})[0], 200)
        self.new("phase", "Build")
        self.new("task", "Dig", after="ABC-GNT-001", show=1, note="internal words", budget=900)
        self.new("task", SECRET, after="ABC-GNT-002")                        # the eye is off (a new line starts off)
        self.change({"project": "ABC", "kind": "gantt_lines", "op": "update", "id": "ABC-GNT-001", "changes": {"show": 1}})
        self.change({"project": "ABC", "kind": "gantt_lines", "op": "update", "id": "ABC-GNT-002", "changes": {"depends": "ABC-GNT-003"}})

    def new(self, kind, name, after=None, **more):
        status, body = self.change({"project": "ABC", "kind": "gantt_lines", "op": "new", "values": {"type": kind, "name": name, **more}, "after": after})
        self.assertEqual(status, 200, body)

    def inputs(self):
        return publish.read_inputs(self.s, "ABC", "2026-11-06")

    def test_the_read_asks_for_the_columns_by_name_and_the_gate_does_the_rest(self):
        inputs = self.inputs()
        self.assertEqual({l["id"] for l in inputs["data"]["gantt_lines"]}, {"ABC-GNT-001", "ABC-GNT-002", "ABC-GNT-003"})     # read for the gate; select drops
        self.assertTrue(all(set(l) == set(publish.PUBLISH_FIELDS["gantt_lines"]) | {"show", "project"} for l in inputs["data"]["gantt_lines"]))
        out = publish.select(inputs)
        text = json.dumps(out, ensure_ascii=False)
        self.assertEqual([l["id"] for l in out["data"]["gantt"]["lines"]], ["ABC-GNT-001", "ABC-GNT-002"])
        for secret in (SECRET, "internal words", "900", "ABC-GNT-003"):
            self.assertNotIn(secret, text)
        self.assertEqual(out["data"]["gantt"]["lines"][1]["depends"], [])

    def test_the_editors_own_read_keeps_everything(self):
        data = self.s.data_for("ABC")
        self.assertEqual(len(data["gantt_lines"]), 3)
        mine = next(l for l in data["gantt_lines"] if l["id"] == "ABC-GNT-002")
        self.assertEqual((mine["note"], mine["budget"], mine["depends"]), ("internal words", 900.0, "ABC-GNT-003"))
        self.assertEqual(data["project"]["gantt_hidden_columns"], "show,note,budget,effort,baseline_start,baseline_end,owner")

    def test_every_client_file_made_from_the_selection_is_clean(self):
        out = publish.select(self.inputs())
        from clark import docx_build, excel_client
        word = docx_build.build(out)
        sheet = excel_client.workbook_bytes(out)
        for blob in (word, sheet):
            self.assertTrue(blob[:2] == b"PK")
        import io
        import zipfile
        for blob in (word, sheet):
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                joined = b"".join(z.read(n) for n in z.namelist())
            self.assertNotIn(SECRET.encode(), joined)
            self.assertNotIn(b"internal words", joined)

    def test_the_page_file_made_by_build_carries_no_eye_off_line(self):
        built = publish.build(self.s, "ABC", now="2026-11-06")
        body = built["body"].decode("utf-8")
        self.assertNotIn(SECRET, body)
        self.assertNotIn("internal words", body)
        self.assertIn('"gantt"', body)
        self.assertIn("Dig", body)

    def test_a_project_with_the_switch_off_publishes_no_gantt_at_all(self):
        self.change({"project": "ABC", "kind": "projects", "op": "update", "changes": {"show_gantt_client": 0}})
        built = publish.build(self.s, "ABC", now="2026-11-06")
        body = built["body"].decode("utf-8")
        self.assertNotIn('"gantt"', body)
        self.assertNotIn("Dig", body)
        self.assertNotIn("gantt", built["published"]["tabs"])


if __name__ == "__main__":
    unittest.main()
