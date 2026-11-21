"""Row 1365 (part 3): the name scan skips left-out folders, and the route action saves them.

Run: python3 dev/run_tests.py test_ask_exclude_route_1365
Pins: that the people or contract scan no longer names or counts what is left out, that each hit says whether it is a folder, and the route action that saves
the flagged subfolders (one Undo, fails closed on a list it cannot read, the limit, each project's own list). Made-up names only; no file is read by the name scan.
"""
import json
import os
import shutil
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

from test_ask_exclude_1365 import Base
from clark import ask_exclude as ex, ask_folders, sensitive_names as sn



class Scan(Base):
    def test_left_out_subfolders_are_no_longer_named_or_counted(self):
        self.put("Contract/a.txt")
        self.put("Contract/Payroll/b.txt")
        self.put("Other/Salary/c.txt")
        names = lambda left: sorted((r["name"], r["readable_files"]) for r in sn.scan(self.root, left))
        self.assertEqual(names(()), [("Contract", 2), ("Salary", 1)])
        self.assertEqual(names(["Contract"]), [("Salary", 1)])
        self.assertEqual(names(["contract/payroll"]), [("Contract", 1), ("Salary", 1)], "nested under a flagged folder: not counted")
        self.assertEqual(names(["Other/Salary"]), [("Contract", 2)], "found below an unflagged folder")
        self.assertEqual(names(["Other"]), [("Contract", 2)])

    def test_a_left_out_file_inside_a_flagged_folder_is_not_counted_and_a_left_out_folder_is_not_opened(self):
        self.put("Contract/a.txt")
        self.put("Contract/b.txt")
        self.put("Contract/sub/c.txt")
        self.assertEqual([r["readable_files"] for r in sn.scan(self.root, ["Contract/a.txt"])], [2])
        opened = []
        real = os.scandir

        def watch(path=".", *a, **k):
            opened.append(os.fspath(path))
            return real(path, *a, **k)

        with mock.patch.object(os, "scandir", side_effect=watch):
            sn.scan(self.root, ["Contract/sub"])
        self.assertFalse([p for p in opened if p.endswith("sub")], opened)

    def test_a_left_out_folder_deep_inside_a_flagged_folder_is_not_counted(self):
        self.put("Contract/x/y/a.txt")
        self.put("Contract/x/b.txt")
        self.put("Contract/c.txt")
        self.assertEqual([r["readable_files"] for r in sn.scan(self.root, ())], [3])
        self.assertEqual([r["readable_files"] for r in sn.scan(self.root, ["Contract/x/y"])], [2])
        self.assertEqual([r["readable_files"] for r in sn.scan(self.root, ["Contract/x/b.txt"])], [2])

    def test_each_hit_says_whether_it_is_a_folder(self):
        self.put("Contract/a.txt")
        self.put("Payroll 2026.csv")
        self.assertEqual(sorted((r["name"], r["dir"]) for r in sn.scan(self.root)), [("Contract", True), ("Payroll 2026.csv", False)])




class Route(Base):
    def setUp(self):
        super().setUp()
        self.cloud = self.home / "OneDrive-Test"
        self.cloud.mkdir()
        s = self.store()
        with s.step("dashboard", "tester", place="menu") as step:
            step.create("projects", {"code": "ABC", "name": "Example Programme"})
        self.svc = ask_folders.AskFolders(self.db, [self.cloud], data_dir=self.data, home=self.home, by_user=lambda: "tester")
        self.tree()

    def stored(self):
        return self.store().read("source_folders", "ABC")[0]["excluded"]

    def add(self):
        return self.svc.change({"project": "ABC", "action": "add", "path": str(self.root)})

    def test_leave_out_saves_the_flagged_subfolders_and_the_warning_goes(self):
        status, body = self.add()
        self.assertEqual([i["name"] for w in body["warnings"] for i in w["items"]], ["Contract"])
        status, body = self.svc.change({"project": "ABC", "action": "exclude", "path": str(self.root)})
        self.assertEqual((status, body["ok"], body["warnings"], body["folders"]), (200, True, [], [str(self.root)]))
        self.assertIn("apply_id", body)
        self.assertEqual(json.loads(self.stored()), ["Contract"])
        self.assertEqual(self.svc.read("ABC")[1]["warnings"], [], "the list read later does not warn again")

    def test_a_second_leave_out_changes_nothing_and_writes_no_step(self):
        self.add()
        self.svc.change({"project": "ABC", "action": "exclude", "path": str(self.root)})
        steps = len(self.store().con.execute("SELECT 1 FROM sqlite_master").fetchall())
        status, body = self.svc.change({"project": "ABC", "action": "exclude", "path": str(self.root)})
        self.assertEqual((status, body["ok"], "apply_id" in body), (200, True, False))
        self.assertEqual(json.loads(self.stored()), ["Contract"])
        self.assertEqual(steps, len(self.store().con.execute("SELECT 1 FROM sqlite_master").fetchall()))

    def test_it_adds_to_what_is_already_left_out_and_never_drops_it(self):
        self.add()
        with self.store().step("dashboard", "tester", place="menu") as step:
            step.update("source_folders", f"ABC|{self.root}", {"excluded": '["Notes"]'})
        self.svc.change({"project": "ABC", "action": "exclude", "path": str(self.root)})
        self.assertEqual(json.loads(self.stored()), ["Contract", "Notes"])

    def test_one_undo_takes_it_back(self):
        self.add()
        body = self.svc.change({"project": "ABC", "action": "exclude", "path": str(self.root)})[1]
        status, got = self.svc.change({"project": "ABC", "action": "undo", "apply_id": body["apply_id"]})
        self.assertEqual((status, got["ok"]), (200, True))
        self.assertEqual(self.stored(), "[]")

    def test_a_folder_that_is_not_saved_is_refused_and_nothing_is_written(self):
        self.add()
        for path in (str(self.home), "relative", str(self.root / "Contract")):
            status, body = self.svc.change({"project": "ABC", "action": "exclude", "path": path})
            self.assertEqual((status, body["code"]), (409, "not_in_list"), path)
        self.assertEqual(self.stored(), "[]")

    def test_exactly_the_limit_is_saved_and_a_nested_flagged_folder_is_kept_by_its_path(self):
        shutil.rmtree(self.root / "Contract")
        for i in range(ex.MAX_LEFT_OUT - 1):
            self.put(f"Contract {i:02d}/x.txt")
        self.put("HR/Contract/y.txt")
        self.add()
        status, body = self.svc.change({"project": "ABC", "action": "exclude", "path": str(self.root)})
        self.assertEqual((status, body["ok"]), (200, True), body)
        got = json.loads(self.stored())
        self.assertEqual(len(got), ex.MAX_LEFT_OUT)
        self.assertIn("HR/Contract", got)

    def test_a_flagged_folder_whose_name_cannot_be_kept_is_not_left_out_and_the_others_are(self):
        self.put("Contract|2026/z.txt")
        self.add()
        status, body = self.svc.change({"project": "ABC", "action": "exclude", "path": str(self.root)})
        self.assertEqual((status, body["ok"]), (200, True), body)
        self.assertEqual(json.loads(self.stored()), ["Contract"])

    def test_a_save_that_fails_says_so_and_changes_nothing(self):
        self.add()
        self.svc.save = lambda store, make: False
        status, body = self.svc.change({"project": "ABC", "action": "exclude", "path": str(self.root)})
        self.assertEqual((status, body["code"]), (409, "cant_save"))
        self.assertEqual(self.stored(), "[]")

    def test_the_saved_folder_may_be_named_through_a_link_to_it(self):
        self.add()
        link = self.d / "link-to-lib"
        os.symlink(self.root, link)
        status, body = self.svc.change({"project": "ABC", "action": "exclude", "path": str(link)})
        self.assertEqual((status, body["ok"]), (200, True))
        self.assertEqual(json.loads(self.stored()), ["Contract"])

    def test_the_body_is_checked(self):
        self.add()
        for body in ({"project": "ABC", "action": "exclude"}, {"project": "ABC", "action": "exclude", "path": str(self.root), "x": 1},
                     {"project": "ABC", "action": "exclude", "path": ""}, {"project": "ABC", "action": "exclude", "path": 5},
                     {"project": "ABC", "action": "exclude", "path": "/a\nb"}, {"project": "abc", "action": "exclude", "path": str(self.root)}):
            self.assertEqual(self.svc.change(body)[0], 400, body)
        self.assertEqual(self.stored(), "[]")

    def test_a_stored_list_that_cannot_be_read_fails_closed_and_is_not_overwritten(self):
        self.add()
        self.store().con.execute("UPDATE source_folders SET excluded = 'garbage'")
        self.store().con.commit()
        status, body = self.svc.change({"project": "ABC", "action": "exclude", "path": str(self.root)})
        self.assertEqual((status, body["code"]), (409, "cant_save"))
        self.assertEqual(self.stored(), "garbage")
        self.assertEqual(self.svc.read("ABC")[1]["warnings"], [], "no scan for a folder whose list cannot be read")

    def test_more_than_the_limit_is_refused_not_cut(self):
        for i in range(ex.MAX_LEFT_OUT):
            self.put(f"Contract {i:02d}/x.txt")
        self.add()
        with mock.patch.object(self.svc, "save", wraps=self.svc.save) as saving:
            status, body = self.svc.change({"project": "ABC", "action": "exclude", "path": str(self.root)})
        self.assertEqual((status, body["code"]), (409, "cant_save"))
        self.assertEqual(self.stored(), "[]")
        saving.assert_not_called()      # refused before any step is tried, not left to the store's own check

    def test_only_folders_are_left_out_a_flagged_file_is_not(self):
        shutil.rmtree(self.root / "Contract")
        self.put("Payroll 2026.csv", "x")
        self.add()
        status, body = self.svc.change({"project": "ABC", "action": "exclude", "path": str(self.root)})
        self.assertEqual((status, "apply_id" in body), (200, False))
        self.assertEqual(self.stored(), "[]")
        self.assertEqual([i["dir"] for w in body["warnings"] for i in w["items"]], [False])

    def test_the_same_folder_saved_in_two_projects_keeps_each_projects_own_list(self):
        self.add()
        with self.store().step("dashboard", "tester", place="menu") as step:
            step.create("projects", {"code": "OTH", "name": "Other Programme"})
            step.create("source_folders", {"project": "OTH", "path": str(self.root), "sort_order": 0, "excluded": '["Notes"]'})
        body = self.svc.change({"project": "ABC", "action": "exclude", "path": str(self.root)})[1]
        self.assertTrue(body["ok"])
        rows = {r["project"]: r["excluded"] for r in self.store().read("source_folders")}
        self.assertEqual({k: json.loads(v) for k, v in rows.items()}, {"ABC": ["Contract"], "OTH": ["Notes"]})
        self.assertEqual(len(self.svc.read("OTH")[1]["warnings"]), 1, "the other project's list is its own: its flagged Contract is still named")

    def test_a_saved_entry_for_a_folder_that_is_not_there_yet_is_kept_by_a_later_leave_out(self):
        self.add()
        with self.store().step("dashboard", "tester", place="menu") as step:
            step.update("source_folders", f"ABC|{self.root}", {"excluded": '["Archive"]'})
        self.svc.change({"project": "ABC", "action": "exclude", "path": str(self.root)})
        self.assertEqual(json.loads(self.stored()), ["Archive", "Contract"])

    def test_the_scan_for_a_leave_out_does_not_count_what_is_already_left_out_against_its_entry_cap(self):
        wide = Path(os.path.realpath(self.home)) / "Wide"
        for rel in ("Archive/a.txt", "Archive/b.txt", "Archive/c.txt", "Contract/t.txt"):
            (wide / rel).parent.mkdir(parents=True, exist_ok=True)
            (wide / rel).write_text("text", encoding="utf-8")
        with self.store().step("dashboard", "tester", place="menu") as step:
            step.create("source_folders", {"project": "ABC", "path": str(wide), "sort_order": 0, "excluded": '["Archive"]'})
        with mock.patch.object(sn, "MAX_ENTRIES", 3):
            body = self.svc.change({"project": "ABC", "action": "exclude", "path": str(wide)})[1]
        self.assertTrue(body["ok"])
        rows = {r["path"]: r["excluded"] for r in self.store().read("source_folders", "ABC")}
        self.assertEqual(json.loads(rows[str(wide)]), ["Archive", "Contract"], "Archive and its three files would have used the cap before Contract was reached")

    def test_a_folder_taken_out_and_put_back_starts_with_nothing_left_out(self):
        self.add()
        self.svc.change({"project": "ABC", "action": "exclude", "path": str(self.root)})
        self.assertEqual(json.loads(self.stored()), ["Contract"])
        self.assertTrue(self.svc.change({"project": "ABC", "action": "remove", "path": str(self.root)})[1]["ok"])
        body = self.add()[1]
        self.assertEqual(self.stored(), "[]")
        self.assertEqual([i["name"] for w in body["warnings"] for i in w["items"]], ["Contract"], "named again, as for a new folder")

    def test_the_page_is_told_which_hits_are_folders(self):
        status, body = self.add()
        self.assertEqual([i["dir"] for i in body["warnings"][0]["items"]], [True])


