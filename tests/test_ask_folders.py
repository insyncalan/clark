"""#47: GET and POST /api/ask-folders (src/clark/ask_folders.py, routed by server.py). Every test talks to a real server.

Run: python3 dev/run_tests.py test_ask_folders
The data is a temporary clark database with fictional projects; "home" and "OneDrive" are folders made for the test.
"""
import http.client
import json
import os
import tempfile
import threading
import unittest
from unittest import mock
from pathlib import Path

from _paths import SRC  # noqa: F401

from clark import ask_folders, platform as pl, server as sv, store as st


class Running:
    """A server on a free port in a thread (the same checks as the other route tests, without Chrome)."""

    def __init__(self):
        self.httpd = sv.LocalServer((sv.HOST, 0))
        self.port = self.httpd.server_port
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def ask(self, method, path, headers=None, body=None, host="default"):
        conn = http.client.HTTPConnection(sv.HOST, self.port, timeout=10)
        try:
            conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            if host == "default":
                host = f"127.0.0.1:{self.port}"
            if host is not None:
                conn.putheader("Host", host)
            for k, v in (headers or {}).items():
                conn.putheader(k, v)
            conn.endheaders(body)
            r = conn.getresponse()
            return r.status, r.msg, r.read()
        finally:
            conn.close()

    def api(self, method, path, body=None, ctype="application/json", token=None, extra=None, host="default"):
        h = {sv.TOKEN_HEADER: sv.TOKEN if token is None else token, **(extra or {})}
        if body is not None:
            h["Content-Type"] = ctype
            h["Content-Length"] = str(len(body))
        return self.ask(method, path, h, body, host=host)


PLAIN_WORDS = "Nothing was changed."


class Base(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.object(pl, "system", return_value=pl.MAC)       # the never-read list is the Mac's; a Linux runner has none
        patch.start()
        self.addCleanup(patch.stop)
        self.d = Path(os.path.realpath(tempfile.mkdtemp()))
        self.data = self.d / "data"
        self.data.mkdir()
        self.home = self.d / "home"
        self.cloud = self.home / "OneDrive-Test"
        self.docs = self.home / "docs"
        self.more = self.home / "more"
        for p in (self.cloud, self.docs, self.more):
            p.mkdir(parents=True)
        self.db = self.data / "clark.db"
        store = st.open_store(self.db, onedrive_roots=[])
        with store.step("dashboard", "tester", place="menu") as s:
            s.create("projects", {"code": "ABC", "name": "Example Programme"})
            s.create("projects", {"code": "OLD", "name": "Old Programme"})
        store.close()
        self.service = ask_folders.AskFolders(self.db, [self.cloud], data_dir=self.data, home=self.home, by_user=lambda: "tester")
        self.s = Running()
        self.s.httpd.ask_folders = self.service
        self.addCleanup(self.s.close)

    def post(self, body, **kw):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        status, _, data = self.s.api("POST", "/api/ask-folders", raw, **kw)
        return status, json.loads(data)

    def get(self, project="ABC", **kw):
        status, _, data = self.s.api("GET", f"/api/ask-folders?project={project}", **kw)
        return status, json.loads(data)

    def add(self, path, project="ABC"):
        return self.post({"project": project, "action": "add", "path": str(path)})

    def stored(self, project="ABC"):
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            return [r["path"] for r in store.read("source_folders", project)]
        finally:
            store.close()

    def archive_old(self):
        store = st.open_store(self.db, onedrive_roots=[])
        try:
            with store.step("dashboard", "tester", place="menu") as s:
                s.archive("projects", "OLD")
        finally:
            store.close()

    def refused(self, got, status, code):
        self.assertEqual(got[0], status, got)
        self.assertEqual((got[1]["ok"], got[1]["code"]), (False, code), got)
        self.assertTrue(got[1]["message"].endswith(PLAIN_WORDS) or code in ("bad_action",), got)
        self.assertFalse(got[1]["message"].startswith("clark's data"), got)


class Allowed(Base):
    def test_an_empty_list_then_add_then_read_then_remove(self):
        self.assertEqual(self.get(), (200, {"ok": True, "folders": []}))
        status, body = self.add(self.docs)
        self.assertEqual((status, body["ok"], body["folders"]), (200, True, [str(self.docs)]))
        self.assertTrue(body["message"])
        self.assertEqual(self.get()[1]["folders"], [str(self.docs)])
        self.assertEqual(self.add(self.more)[1]["folders"], [str(self.docs), str(self.more)])
        status, body = self.post({"project": "ABC", "action": "remove", "path": str(self.docs)})
        self.assertEqual((status, body["folders"]), (200, [str(self.more)]))

    def test_adding_twice_is_one_folder_and_no_new_step(self):
        first = self.add(self.docs)[1]
        again = self.add(self.docs)
        self.assertEqual((again[0], again[1]["folders"]), (200, [str(self.docs)]))
        self.assertNotIn("apply_id", again[1])
        self.assertTrue(first["apply_id"])

    def test_a_trailing_slash_and_a_link_to_a_good_folder_are_saved_as_the_real_folder(self):
        link = self.home / "shortcut"
        link.symlink_to(self.docs)
        self.assertEqual(self.add(str(self.docs) + "/")[1]["folders"], [str(self.docs)])
        self.assertEqual(self.add(link)[1]["folders"], [str(self.docs)])

    def test_a_removed_folder_that_has_gone_from_the_disk_can_still_be_removed(self):
        self.add(self.docs)
        self.docs.rmdir()
        self.assertEqual(self.post({"project": "ABC", "action": "remove", "path": str(self.docs)})[1]["folders"], [])

    def test_one_project_does_not_see_anothers_folders(self):
        self.add(self.docs)
        self.assertEqual(self.get("OLD")[1]["folders"], [])


class Undo(Base):
    def test_undo_of_an_add_takes_the_folder_back_in_one_step(self):
        step = self.add(self.docs)[1]["apply_id"]
        status, body = self.post({"project": "ABC", "action": "undo", "apply_id": step})
        self.assertEqual((status, body["folders"]), (200, []))
        self.assertEqual(self.stored(), [])

    def test_undo_of_a_remove_puts_the_folder_back(self):
        self.add(self.docs)
        step = self.post({"project": "ABC", "action": "remove", "path": str(self.docs)})[1]["apply_id"]
        self.assertEqual(self.stored(), [])
        self.assertEqual(self.post({"project": "ABC", "action": "undo", "apply_id": step})[1]["folders"], [str(self.docs)])

    def test_a_step_can_be_undone_once_and_only_by_its_own_project(self):
        step = self.add(self.docs)[1]["apply_id"]
        self.refused(self.post({"project": "OLD", "action": "undo", "apply_id": step}), 409, "no_undo")
        self.assertEqual(self.post({"project": "ABC", "action": "undo", "apply_id": step})[0], 200)
        self.refused(self.post({"project": "ABC", "action": "undo", "apply_id": step}), 409, "no_undo")

    def test_a_step_that_is_not_a_folder_step_is_not_undone_here(self):
        self.refused(self.post({"project": "ABC", "action": "undo", "apply_id": 1}), 409, "no_undo")      # the project's own creation
        self.assertEqual(self.get()[0], 200)

    def test_bad_step_numbers(self):
        for bad in (0, -1, 2 ** 70, "1", 1.5, True, None, [1]):
            self.refused(self.post({"project": "ABC", "action": "undo", "apply_id": bad}), 400, "no_undo")


class Refused(Base):
    def test_the_home_folder_and_the_onedrive_root(self):
        self.refused(self.add(self.home), 400, "home_folder")
        self.refused(self.add(self.cloud), 400, "onedrive_root")
        self.refused(self.add(str(self.cloud) + "/"), 400, "onedrive_root")
        link = self.d / "tohome"
        link.symlink_to(self.home)
        self.refused(self.add(link), 400, "home_folder")
        self.assertEqual(self.stored(), [])

    def test_a_folder_inside_onedrive_is_fine(self):
        inner = self.cloud / "Engagements"
        inner.mkdir()
        self.assertEqual(self.add(inner)[0], 200)

    def test_the_top_of_the_disk(self):
        for p in ("/", "//", "/."):
            self.refused(self.add(p), 400, "top_of_disk")

    def test_a_file_and_a_missing_path(self):
        f = self.home / "notes.txt"
        f.write_text("x", encoding="utf-8")
        self.refused(self.add(f), 409, "not_a_folder")
        self.refused(self.add(self.home / "nothing"), 409, "not_a_folder")

    def test_relative_and_tilde_paths(self):
        for p in ("docs", "./docs", "~/docs", "~", "relative/path"):
            self.refused(self.add(p), 400, "not_full_path")

    def test_dot_dot_segments(self):
        self.refused(self.add(f"{self.docs}/../more"), 400, "dots")
        self.refused(self.add(f"{self.docs}/.."), 400, "dots")

    def test_newline_and_control_characters(self):
        for bad in (f"{self.docs}\n", f"{self.docs}\n/etc", f"{self.docs}\x00", f"{self.docs}\x1b[0m", f"{self.docs} x",
                    f"{self.docs}​x", f"{self.docs}\r"):
            self.refused(self.add(bad), 400, "not_a_path")
        self.assertEqual(self.stored(), [])

    def test_a_link_to_a_closed_place_is_judged_by_where_it_leads(self):
        link = self.home / "innocent"
        link.symlink_to(self.data)                          # clark's own data folder
        self.refused(self.add(link), 409, "closed_place")
        self.refused(self.add(self.data), 409, "closed_place")
        self.refused(self.add(self.data / "sub"), 409, "not_a_folder")
        ssh = self.home / ".ssh"
        ssh.mkdir()
        alias = self.home / "keys"
        alias.symlink_to(ssh)
        self.refused(self.add(alias), 409, "closed_place")
        self.assertEqual(self.stored(), [])

    def test_a_path_that_is_not_text_or_is_too_long(self):
        for bad in (None, 5, ["/a"], {"a": 1}, "", "/" + "a" * 1001):
            self.refused(self.post({"project": "ABC", "action": "add", "path": bad}), 400, "not_a_path")

    def test_project_problems(self):
        self.refused(self.post({"project": "ZZZ", "action": "add", "path": str(self.docs)}), 404, "project_not_found")
        for bad in ("abc", "A", "ABC/../x", "", None, 5, "ABC\n"):
            self.refused(self.post({"project": bad, "action": "add", "path": str(self.docs)}), 400, "bad_project_code")
        self.assertEqual(self.get("ZZZ")[0], 404)
        self.assertEqual(self.get("abc")[0], 400)

    def test_an_archived_project_cannot_be_changed(self):
        self.add(self.docs, "OLD")
        self.archive_old()
        self.refused(self.add(self.more, "OLD"), 409, "project_archived")
        self.refused(self.post({"project": "OLD", "action": "remove", "path": str(self.docs)}), 409, "project_archived")
        self.assertEqual(self.stored("OLD"), [str(self.docs)])

    def test_removing_a_folder_that_is_not_listed(self):
        self.refused(self.post({"project": "ABC", "action": "remove", "path": str(self.docs)}), 409, "not_in_list")

    def test_actions(self):
        for bad in ("pick", "clear", "ADD", "", None, 1, ["add"]):
            got = self.post({"project": "ABC", "action": bad, "path": str(self.docs)})
            self.assertEqual((got[0], got[1]["code"]), (400, "bad_action"))

    def test_unknown_missing_and_mixed_fields(self):
        for body in ({"project": "ABC", "action": "add", "path": str(self.docs), "sort_order": 0},
                     {"project": "ABC", "action": "add", "path": str(self.docs), "extra": 1},
                     {"project": "ABC", "action": "add"},
                     {"project": "ABC", "action": "remove"},
                     {"project": "ABC", "action": "undo"},
                     {"project": "ABC", "action": "undo", "apply_id": 2, "path": str(self.docs)},
                     {"project": "ABC", "action": "add", "path": str(self.docs), "apply_id": 2}):
            got = self.post(body)
            self.assertEqual((got[0], got[1]["code"]), (400, "bad_request"), body)
        self.assertEqual(self.stored(), [])

    def test_a_body_that_is_not_an_object(self):
        for raw in (b"[]", b'"x"', b"5", b"null"):
            got = self.post(raw)
            self.assertEqual((got[0], got[1]["code"]), (400, "bad_request"), raw)

    def test_no_more_than_twenty_folders(self):
        for i in range(ask_folders.MAX_FOLDERS):
            p = self.home / f"f{i}"
            p.mkdir()
            self.assertEqual(self.add(p)[0], 200)
        self.refused(self.add(self.docs), 409, "too_many")


class Doorway(Base):
    """The checks every /api/ route gets, shown for this one."""

    def test_no_token_or_a_wrong_one(self):
        for token in ("", "wrong"):
            status, _, _ = self.s.api("GET", "/api/ask-folders?project=ABC", token=token)
            self.assertEqual(status, 403)
            status, _, _ = self.s.api("POST", "/api/ask-folders", b"{}", token=token)
            self.assertEqual(status, 403)
        self.assertEqual(self.stored(), [])

    def test_another_host_or_origin(self):
        body = json.dumps({"project": "ABC", "action": "add", "path": str(self.docs)}).encode()
        for host in ("evil.example", None, "127.0.0.1.evil.example"):
            self.assertEqual(self.s.api("POST", "/api/ask-folders", body, host=host)[0], 403, host)
            self.assertEqual(self.s.api("GET", "/api/ask-folders?project=ABC", host=host)[0], 403, host)
        for origin in ("https://evil.example", "null", "http://127.0.0.1:1"):
            self.assertEqual(self.s.api("POST", "/api/ask-folders", body, extra={"Origin": origin})[0], 403, origin)
            self.assertEqual(self.s.api("GET", "/api/ask-folders?project=ABC", extra={"Origin": origin})[0], 403, origin)
        self.assertEqual(self.stored(), [])

    def test_json_only(self):
        body = json.dumps({"project": "ABC", "action": "add", "path": str(self.docs)}).encode()
        self.assertEqual(self.s.api("POST", "/api/ask-folders", body, ctype="text/plain")[0], 415)
        self.assertEqual(self.stored(), [])

    def test_a_big_body(self):
        big = json.dumps({"project": "ABC", "action": "add", "path": "/" + "a" * 5000}).encode()
        self.assertEqual(self.s.api("POST", "/api/ask-folders", big)[0], 400)
        self.assertEqual(self.stored(), [])

    def test_malformed_json(self):
        for raw in (b"{", b"not json", b'{"project": "ABC",', b"\xff\xfe"):
            self.assertEqual(self.s.api("POST", "/api/ask-folders", raw)[0], 400, raw)
        self.assertEqual(self.stored(), [])

    def test_no_length(self):
        status, _, _ = self.s.ask("POST", "/api/ask-folders", {sv.TOKEN_HEADER: sv.TOKEN, "Content-Type": "application/json"})
        self.assertEqual(status, 411)

    def test_a_server_without_it_answers_not_found(self):
        self.s.httpd.ask_folders = None
        self.assertEqual(self.get()[0], 404)
        self.assertEqual(self.post({"project": "ABC", "action": "add", "path": str(self.docs)})[0], 404)

    def test_two_requests_at_once_leave_one_folder(self):
        outs = []
        t = [threading.Thread(target=lambda: outs.append(self.add(self.docs)[0])) for _ in range(4)]
        for x in t:
            x.start()
        for x in t:
            x.join()
        self.assertEqual((sorted(outs), self.stored()), ([200] * 4, [str(self.docs)]))


class Choosing(Base):
    """#47 fix 2 and 4: the folder is picked in the system's own window; the words never say 'full path' or '..' and the save
    failure does not start with the product's name."""

    def pick(self, answer):
        calls = []

        def fake(prompt, start=None):
            calls.append((prompt, start))
            if isinstance(answer, Exception):
                raise answer
            return answer
        self.service.choose_folder = fake
        return calls

    def choose(self):
        return self.post({"project": "ABC", "action": "choose"})

    def test_choosing_saves_the_picked_folder_as_one_step(self):
        calls = self.pick(self.docs)
        status, body = self.choose()
        self.assertEqual((status, body["folders"], self.stored()), (200, [str(self.docs)], [str(self.docs)]))
        self.assertEqual(str(calls[0][1]), str(self.cloud))
        self.assertEqual(self.post({"project": "ABC", "action": "undo", "apply_id": body["apply_id"]})[0], 200)
        self.assertEqual(self.stored(), [])

    def test_cancelling_the_window_changes_nothing(self):
        self.pick(None)
        self.assertEqual(self.choose(), (200, {"ok": True, "folders": []}))

    def test_a_picked_folder_is_checked_like_a_typed_one(self):
        self.pick(self.home)
        self.refused(self.choose(), 400, "home_folder")
        self.assertEqual(self.stored(), [])

    def test_a_window_that_will_not_open_says_so_with_a_next_step(self):
        self.pick(ask_folders.platform.PlatformError("no window"))
        got = self.choose()
        self.refused(got, 409, "dialog_failed")
        self.assertIn("Try Choose folder again", got[1]["message"])

    def test_choose_takes_no_path(self):
        self.pick(self.docs)
        self.refused(self.post({"project": "ABC", "action": "choose", "path": str(self.docs)}), 400, "bad_request")

    def test_no_refusal_says_full_path_or_dots_and_none_starts_with_the_product_name(self):
        for code, text in ask_folders.MESSAGES.items():
            self.assertNotIn("full path", text.lower(), code)
            self.assertNotIn("..", text, code)
            self.assertFalse(text.lower().startswith("clark"), code)

    def test_a_failed_save_has_a_next_step(self):
        text = ask_folders.MESSAGES["cant_save"]
        self.assertIn("Try Choose folder again", text)
        self.assertIn("start it again", text)


if __name__ == "__main__":
    unittest.main()
