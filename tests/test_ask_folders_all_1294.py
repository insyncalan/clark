"""Row 1294, slice 4: the folders for all projects (GET /api/ask-folders?scope=all, POST /api/ask-folders {scope: "all", ...}).

Run: python3 dev/run_tests.py test_ask_folders_all_1294
A real server and a temporary clark database with fictional projects; "home" and "OneDrive" are folders made for the test. The list for all projects is
read in every project and counts towards each project's 20; Remove touches no file; the too-wide places are refused as for a project's own folder.
"""
import json
import os
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401
from test_ask_folders import Base, PLAIN_WORDS

from clark import ask_folders, ask_service, store as st


def all_post(case, action, path=None):
    body = {"scope": "all", "action": action}
    if path is not None:
        body["path"] = str(path)
    return case.post(body)


class AllFolders(Base):
    def read_all(self):
        status, _, data = self.s.api("GET", "/api/ask-folders?scope=all")
        return status, json.loads(data)

    def test_add_read_and_remove_one_for_all_projects_and_the_folder_stays_on_disk(self):
        self.assertEqual(self.read_all(), (200, {"ok": True, "folders": []}))
        status, body = all_post(self, "add", self.docs)
        self.assertEqual((status, body["ok"], body["folders"]), (200, True, [str(self.docs)]))
        self.assertEqual(body["message"], ask_folders.MESSAGES["added"])
        self.assertEqual(all_post(self, "add", self.more)[1]["folders"], [str(self.docs), str(self.more)])
        self.assertEqual(self.read_all()[1]["folders"], [str(self.docs), str(self.more)])
        (self.docs / "keep.txt").write_text("x", encoding="utf-8")
        status, body = all_post(self, "remove", self.docs)
        self.assertEqual((status, body["folders"], body["message"]), (200, [str(self.more)], ask_folders.MESSAGES["removed"]))
        self.assertTrue((self.docs / "keep.txt").exists(), "Remove touches no file")
        self.assertEqual(self.read_all()[1]["folders"], [str(self.more)])

    def test_every_project_reads_them_as_shared_and_a_projects_own_list_stays_its_own(self):
        all_post(self, "add", self.docs)
        self.add(self.more, "ABC")
        for code, own in (("ABC", [str(self.more)]), ("OLD", [])):
            status, body = self.get(code)
            self.assertEqual((status, body["folders"], body["shared"]), (200, own, [str(self.docs)]), code)
        self.assertEqual(self.stored("ABC"), [str(self.more)])
        self.assertEqual(self.stored("OLD"), [])

    def test_a_projects_remove_changes_only_that_project_and_a_shared_folder_is_not_in_its_list(self):
        all_post(self, "add", self.docs)
        self.add(self.more, "ABC")
        status, body = self.post({"project": "ABC", "action": "remove", "path": str(self.docs)})
        self.assertEqual(status, 409)
        self.assertEqual(body["code"], "not_in_list")
        self.assertEqual(self.read_all()[1]["folders"], [str(self.docs)])

    def test_the_same_folder_twice_is_one_and_a_project_does_not_add_what_all_projects_already_read(self):
        all_post(self, "add", self.docs)
        self.assertEqual(all_post(self, "add", str(self.docs) + "/")[1]["folders"], [str(self.docs)])
        status, body = self.add(self.docs)
        self.assertEqual((status, body["folders"], body["message"]), (200, [], ask_folders.MESSAGES["already"]))
        self.assertEqual(self.stored(), [])

    def test_the_folders_for_all_projects_count_towards_a_projects_20(self):
        many = []
        for n in range(ask_folders.MAX_FOLDERS - 1):
            p = self.home / f"f{n}"
            p.mkdir()
            many.append(p)
        for p in many[:3]:
            all_post(self, "add", p)
        for p in many[3:]:
            self.assertEqual(self.add(p)[0], 200)
        self.assertEqual(len(self.stored()) + 3, ask_folders.MAX_FOLDERS - 1)
        last = self.home / "last"
        last.mkdir()
        self.assertEqual(self.add(last)[0], 200)                          # the 20th
        over = self.home / "over"
        over.mkdir()
        self.refused(self.add(over), 409, "too_many")
        self.assertEqual(len(self.stored()), ask_folders.MAX_FOLDERS - 3)

    def test_twenty_for_all_projects_is_the_most_and_the_21st_says_so(self):
        for n in range(ask_folders.MAX_FOLDERS):
            p = self.home / f"g{n}"
            p.mkdir()
            self.assertEqual(all_post(self, "add", p)[0], 200)
        extra = self.home / "extra"
        extra.mkdir()
        got = all_post(self, "add", extra)
        self.refused(got, 409, "all_too_many")
        self.assertEqual(len(self.read_all()[1]["folders"]), ask_folders.MAX_FOLDERS)

    def test_the_too_wide_places_are_refused_with_nothing_changed(self):
        for typed, code in ((self.home, "home_folder"), (self.cloud, "onedrive_root"), ("/", "top_of_disk"), ("/tmp", "wide_place"),
                            ("relative/path", "not_full_path"), (self.d / "missing", "not_a_folder")):
            got = all_post(self, "add", typed)
            self.assertEqual(got[1].get("code"), code, (typed, got))
            self.assertTrue(got[1]["message"].endswith(PLAIN_WORDS), got)
        self.assertEqual(self.read_all()[1]["folders"], [])
        self.assertFalse((self.data / ask_folders.SHARED_FILE).exists(), "a refusal writes nothing")

    def test_a_folder_clark_keeps_closed_is_refused(self):
        got = all_post(self, "add", self.data)
        self.assertEqual(got[1]["code"], "closed_place", got)
        self.assertEqual(self.read_all()[1]["folders"], [])

    def test_a_removed_name_that_is_not_listed_and_bad_requests_change_nothing(self):
        all_post(self, "add", self.docs)
        self.refused(all_post(self, "remove", self.more), 409, "not_in_list")
        self.assertEqual(self.post({"scope": "all", "action": "add"})[0], 400)                                  # no path
        self.assertEqual(self.post({"scope": "all", "action": "undo", "path": "/x"})[0], 400)                   # no undo here
        self.assertEqual(self.post({"scope": "all", "action": "add", "path": str(self.more), "project": "ABC"})[0], 400)
        self.assertEqual(self.post({"scope": "all", "action": "add", "path": ""})[0], 400)
        self.assertEqual(self.post({"scope": "all", "action": "add", "path": "/a\x00b"})[0], 400)
        self.assertEqual(self.post({"scope": "some", "action": "add", "path": str(self.more)})[0], 400)
        self.assertEqual(self.read_all()[1]["folders"], [str(self.docs)])

    def test_choose_adds_what_the_window_picked_and_a_cancelled_window_changes_nothing(self):
        self.service.choose_folder = lambda prompt, start=None: self.more
        status, body = all_post(self, "choose")
        self.assertEqual((status, body["folders"]), (200, [str(self.more)]))
        self.service.choose_folder = lambda prompt, start=None: None
        status, body = all_post(self, "choose")
        self.assertEqual((status, body["folders"]), (200, [str(self.more)]))
        self.service.choose_folder = lambda prompt, start=None: self.home
        self.assertEqual(all_post(self, "choose")[1]["code"], "home_folder")
        self.assertEqual(self.read_all()[1]["folders"], [str(self.more)])

    def test_a_question_in_any_project_may_read_the_shared_folders_first_then_its_own_without_repeats_and_at_most_20(self):
        all_post(self, "add", self.docs)
        self.add(self.more, "ABC")
        svc = ask_service.AskService.__new__(ask_service.AskService)
        svc.data_dir = self.data
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            self.assertEqual(svc.folders_for(store, "ABC"), [str(self.docs), str(self.more)])
            self.assertEqual(svc.folders_for(store, "OLD"), [str(self.docs)])
        finally:
            store.close()

    def test_a_folder_in_both_lists_is_read_once_and_a_hand_made_long_list_is_cut_at_20(self):
        self.add(self.docs)
        all_post(self, "add", self.docs)                                  # a project's own folder, then the same one for all projects
        svc = ask_service.AskService.__new__(ask_service.AskService)
        svc.data_dir = self.data
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            self.assertEqual(svc.folders_for(store, "ABC"), [str(self.docs)])
            (self.data / ask_folders.SHARED_FILE).write_text(json.dumps([f"/Example/n{n}" for n in range(25)]), encoding="utf-8")
            self.add(self.more)
            got = svc.folders_for(store, "ABC")
            self.assertEqual(len(got), ask_folders.MAX_FOLDERS)
            self.assertEqual(got[0], "/Example/n0")
        finally:
            store.close()

    def test_a_request_for_another_scope_is_not_the_folders_for_all_projects(self):
        self.assertEqual(self.service.change_all({"scope": "some", "action": "add", "path": str(self.more)})[0], 400)
        self.assertEqual(self.service.change_all(["all"])[0], 400)
        self.assertEqual(self.read_all()[1]["folders"], [])

    def test_a_broken_shared_file_reads_as_none_and_the_list_can_be_added_to_again(self):
        (self.data / ask_folders.SHARED_FILE).write_text("{not json", encoding="utf-8")
        self.assertEqual(self.read_all()[1]["folders"], [])
        (self.data / ask_folders.SHARED_FILE).write_text(json.dumps({"a": 1}), encoding="utf-8")
        self.assertEqual(self.read_all()[1]["folders"], [])
        (self.data / ask_folders.SHARED_FILE).write_text(json.dumps(["relative", 3, str(self.docs)]), encoding="utf-8")
        self.assertEqual(self.read_all()[1]["folders"], [str(self.docs)])
        self.assertEqual(all_post(self, "add", self.more)[1]["folders"], [str(self.docs), str(self.more)])

    def test_a_file_that_cannot_be_written_says_so_and_changes_nothing(self):
        with mock.patch.object(os, "replace", side_effect=OSError("no")):
            got = all_post(self, "add", self.docs)
        self.refused(got, 409, "cant_save")
        self.assertEqual(self.read_all()[1]["folders"], [])
        all_post(self, "add", self.docs)
        with mock.patch.object(os, "replace", side_effect=OSError("no")):
            self.refused(all_post(self, "remove", self.docs), 409, "cant_save")
        self.assertEqual(self.read_all()[1]["folders"], [str(self.docs)])

    def test_a_server_without_the_folder_service_answers_not_found_and_the_token_is_needed(self):
        status, _, _ = self.s.api("GET", "/api/ask-folders?scope=all", token="wrong")
        self.assertIn(status, (401, 403))
        self.s.httpd.ask_folders = None
        self.assertEqual(self.s.api("GET", "/api/ask-folders?scope=all")[0], 404)
        self.assertEqual(self.s.api("POST", "/api/ask-folders", json.dumps({"scope": "all", "action": "choose"}).encode())[0], 404)


if __name__ == "__main__":
    unittest.main()
