"""Settings › Version and updates, the server's side: src/clark/updater.py and its routes in server.py, and the launcher's
finish of an update that stopped part way (launch.finish_update).

Builds a fake installed app folder, a data folder with a small database, and a fake Downloads folder in a temporary place; the
helper is run in this process with its platform seams faked. No network, no Chrome, no real system dialog.
Run: python3 dev/run_tests.py test_updater
"""
import http.client
import json
import os
import shutil
import sys
import threading
import time
import unittest
from pathlib import Path

from _paths import ROOT
from clark import launch, server as sv, update_helper as h, update_install as ui, updater as up, updates
from test_update_helper import FakeSeams, snapshot
from test_update_install import Base as InstallBase
from test_updates import make_zip


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class Rig(InstallBase):
    """An Updater over the fixture of test_update_install. The helper it starts runs here, at once, with faked seams."""

    def setUp(self):
        super().setUp()
        self.clock = Clock()
        self.chosen = None
        self.started = []
        self.seams = FakeSeams()
        self.up = self.make()

    def make(self, **kw):
        def start(argv, env, log_path, cwd=None):
            self.started.append(argv)
            marker = Path(argv[argv.index("--marker") + 1])
            doc = json.loads(marker.read_text(encoding="utf-8"))
            doc["phase"] = "ready"
            h.write_json(marker, doc)
            self.run_helper = lambda: h.run_update(marker, self.seams)
        args = dict(app_dir=self.app, system="mac", version="0.3.0", schema=2, choose=lambda prompt, start=None: self.chosen,
                    downloads=self.downloads, clock=self.clock, start=start, server_pid=4321)
        args.update(kw)
        return up.Updater(self.data, self.db, 8765, **args)

    def reviewed(self, **req):
        status, body = self.up.review({"from": "downloads", **req})
        self.assertEqual(200, status, body)
        return body

    def installed(self):
        body = self.reviewed()
        status, done = self.up.install({"review_id": body["review_id"]})
        self.assertEqual(200, status, done)
        code, _ = self.run_helper()
        self.assertEqual(h.OK, code)
        return done


class StatusTest(Rig):
    def test_installed_and_an_update_in_downloads(self):
        status, body = self.up.status()
        self.assertEqual(200, status)
        self.assertEqual("Version 0.3.0, released 27-10-2026.", body["installed"])
        self.assertEqual({"version": "0.3.1", "label": "Review 0.3.1"}, body["update"])
        self.assertIsNone(body["line"])
        self.assertIsNone(body["blocked"])

    def test_up_to_date_when_downloads_holds_nothing_newer(self):
        os.unlink(self.download)
        make_zip(self.downloads, version="0.2.0")
        self.assertEqual("Up to date.", self.up.status()[1]["line"])
        self.assertIsNone(self.up.status()[1]["update"])

    def test_a_copy_that_runs_from_its_source_says_so_and_offers_nothing(self):
        (self.app / ".git").mkdir()
        body = self.up.status()[1]
        self.assertEqual(updates.MESSAGES["git"], body["blocked"])
        self.assertIsNone(body["update"])
        status, said = self.up.review({"from": "downloads"})
        self.assertEqual((409, "blocked"), (status, said["code"]))


class ReviewTest(Rig):
    def test_the_review_and_its_checksum_are_of_the_copy_taken_in(self):
        body = self.reviewed()
        r = body["review"]
        self.assertEqual("Version 0.3.0 → 0.3.1. Released 27-10-2026.", r["heading"])
        self.assertEqual(["src/clark/added.py"], r["added"]["names"])
        kept = self.data / "releases" / "clark-0.3.1-mac.zip"
        self.assertEqual(ui.take_in(kept, self.root / "elsewhere", "mac")[1], r["checksum"])

    def test_a_request_with_anything_else_is_refused(self):
        for req in ({}, {"from": "path"}, {"from": "downloads", "path": "/etc"}, {"from": "file", "reinstall": "yes"}, [], "x"):
            with self.subTest(req=req):
                self.assertEqual(400, self.up.review(req)[0])

    def test_nothing_in_downloads(self):
        os.unlink(self.download)
        status, body = self.up.review({"from": "downloads"})
        self.assertEqual((404, "none_found"), (status, body["code"]))

    def test_choose_a_file_with_the_wrong_name_or_githubs_source_zip(self):
        for name, key in (("update.zip", "name"), ("clark-0.3.1.zip", "source")):
            with self.subTest(name=name):
                self.chosen = self.downloads / name
                shutil.copyfile(self.download, self.chosen)
                status, body = self.up.review({"from": "file"})
                self.assertEqual((409, key), (status, body["code"]))
                self.assertEqual(updates.MESSAGES[key].format(ours="mac"), body["message"])

    def test_choose_a_browser_copy_and_cancel(self):
        self.chosen = self.downloads / "clark-0.3.1-mac (1).zip"
        shutil.copyfile(self.download, self.chosen)
        self.assertEqual(200, self.up.review({"from": "file"})[0])
        self.chosen = None
        self.assertEqual((200, {"ok": True, "cancelled": True}), self.up.review({"from": "file"}))

    def test_the_same_version_needs_install_again(self):
        os.unlink(self.download)
        make_zip(self.downloads, version="0.3.0")
        self.chosen = self.downloads / "clark-0.3.0-mac.zip"
        status, body = self.up.review({"from": "file"})
        self.assertEqual((409, "same", True), (status, body["code"], body["again"]))
        self.assertEqual(200, self.up.review({"from": "file", "reinstall": True})[0])


class InstallTest(Rig):
    def test_install_hands_over_raises_the_flag_and_asks_for_a_restart(self):
        planted = self.planted()
        body = self.reviewed()
        status, done = self.up.install({"review_id": body["review_id"]})
        self.assertEqual((200, True), (status, done["restart"]))
        self.assertEqual("Installing version 0.3.1. One moment while clark restarts. Don't close this window.", done["message"])
        self.assertTrue(self.up.installing())
        self.assertEqual((409, "busy"), (self.up.review({"from": "downloads"})[0], self.up.review({"from": "downloads"})[1]["code"]))
        self.assertTrue(h.marker_path(self.data).exists())
        self.assertEqual(h.OK, self.run_helper()[0])
        self.assertEqual(planted, self.planted())
        after = self.make(version="0.3.1")
        self.assertTrue(after.settle())
        st = after.status()[1]
        self.assertEqual("Version 0.3.1 is installed.", st["notice"])
        self.assertIsNone(after.status()[1]["notice"], "said once")
        self.assertEqual("Last update: 0.3.0 → 0.3.1 on " + ui.stamp_now()[6:8] + "-" + ui.stamp_now()[4:6] + "-"
                         + ui.stamp_now()[0:4] + ".", st["last"]["line"])
        self.assertFalse(any(n.startswith(h.OLD_PREFIX) for n in os.listdir(self.app)), "tidied once settled")

    def test_only_the_held_review_once_and_not_too_old(self):
        self.assertEqual("review_again", self.up.install({"review_id": "made-up"})[1]["code"])
        body = self.reviewed()
        self.clock.now += up.REVIEW_SECONDS + 1
        self.assertEqual("review_again", self.up.install({"review_id": body["review_id"]})[1]["code"])
        self.assertEqual(400, self.up.install({"review_id": body["review_id"], "path": "x"})[0])
        self.assertFalse(h.marker_path(self.data).exists())

    def test_a_step_that_fails_before_the_hand_over_changes_nothing_and_lowers_the_flag(self):
        before = snapshot(self.app)
        body = self.reviewed()
        failing = self.make(start=lambda *a, **k: (_ for _ in ()).throw(OSError("no")))
        failing.reviewed = self.up.reviewed
        status, said = failing.install({"review_id": body["review_id"]})
        self.assertEqual((409, "helper"), (status, said["code"]))
        self.assertFalse(failing.installing())
        self.assertEqual(before, snapshot(self.app))
        self.assertFalse((self.data / "updates" / up.PENDING).exists())
        self.assertIsNone(ui.last_update(self.data), "the update never went in, so there is nothing to undo")

    def test_a_rolled_back_update_is_said_once_and_leaves_nothing_to_undo(self):
        body = self.reviewed()
        self.up.install({"review_id": body["review_id"]})
        self.seams.check_install = lambda app: (_ for _ in ()).throw(h.StepError("damaged", "x"))
        self.assertEqual(h.ROLLED_BACK, self.run_helper()[0])
        after = self.make()
        after.settle()
        self.assertEqual(h.MESSAGES["damaged"], after.status()[1]["notice"])
        self.assertIsNone(ui.last_update(self.data))


class UndoTest(Rig):
    def test_arm_then_confirm_puts_back_the_old_version_and_settings(self):
        old = snapshot(self.app)
        self.installed()
        now = self.make(version="0.3.1")
        now.settle()
        (self.data / "settings.json").write_text(json.dumps({"backups_kept": 2}), encoding="utf-8")
        status, armed = now.arm_undo({})
        self.assertEqual((200, "full"), (status, armed["choice"]))
        self.assertEqual("Choose Undo update again within 5 seconds to put back version 0.3.0.", armed["line"])
        status, done = now.undo({"arm_id": armed["arm_id"]})
        self.assertEqual((200, True), (status, done["restart"]))
        self.assertEqual(h.OK, self.run_helper()[0])
        back = self.make()
        back.settle()
        self.assertEqual(old, snapshot(self.app))
        self.assertEqual({"backups_kept": 9}, json.loads((self.data / "settings.json").read_text(encoding="utf-8")))
        self.assertEqual("Version 0.3.0 has been put back. Your projects are as they were.", back.status()[1]["notice"])
        self.assertEqual("undone", back.arm_undo({})[1]["code"])

    def test_the_second_click_must_come_in_time_and_name_the_arm(self):
        self.installed()
        now = self.make(version="0.3.1")
        now.settle()
        armed = now.arm_undo({})[1]
        self.clock.now += up.ARM_SECONDS + 0.5
        self.assertEqual("arm_again", now.undo({"arm_id": armed["arm_id"]})[1]["code"])
        armed = now.arm_undo({})[1]
        self.assertEqual("arm_again", now.undo({"arm_id": "other"})[1]["code"])
        self.assertEqual("arm_again", now.undo({"arm_id": armed["arm_id"]})[1]["code"], "a wrong try disarms")
        self.assertFalse(h.marker_path(self.data).exists())

    def test_changed_data_refuses_the_full_undo_and_offers_the_app_and_settings_only(self):
        self.installed()
        now = self.make(version="0.3.1")
        now.settle()
        from _demo import USER
        from clark.store import open_store
        s = open_store(self.db, onedrive_roots=[])
        with s.step("dashboard", USER) as st:
            st.create("actions", {"project": "ABC", "description": "after", "raised": "2026-11-01", "source": "demo"})
        s.close()
        armed = now.arm_undo({})[1]
        self.assertEqual("app_only", armed["choice"])
        self.assertIn("Put back the app and settings only", armed["line"])
        status, said = now.undo({"arm_id": armed["arm_id"]})
        self.assertEqual((409, "data_changed"), (status, said["code"]))
        armed = now.arm_undo({})[1]
        self.assertEqual(200, now.undo({"arm_id": armed["arm_id"], "app_only": True})[0])


class Served:
    """A real server over an Updater, on a free port, in a thread."""

    def __init__(self, case, updater):
        self.httpd = sv.LocalServer((sv.HOST, 0), updater=updater, change=lambda req: (200, {"ok": True}))
        self.httpd.handle_error = lambda *a: None
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        case.addCleanup(self.stop)

    def stop(self):
        if self.thread.is_alive():
            self.httpd.shutdown()
        self.httpd.server_close()

    def call(self, method, path, body=None, token=None, host=None, raw=None, origin=None):
        conn = http.client.HTTPConnection(sv.HOST, self.httpd.server_port, timeout=20)
        try:
            data = raw if raw is not None else (None if body is None else json.dumps(body).encode())
            headers = {"Host": host or f"127.0.0.1:{self.httpd.server_port}"}
            if token is not False:
                headers[sv.TOKEN_HEADER] = token or sv.TOKEN
            if origin:
                headers["Origin"] = origin
            if data is not None:
                headers.update({"Content-Type": "application/json", "Content-Length": str(len(data))})
            conn.request(method, path, data, headers)
            r = conn.getresponse()
            got = r.read()
            return r.status, json.loads(got) if got else None
        finally:
            conn.close()


class RoutesTest(Rig):
    def test_each_route_needs_the_token_the_host_and_this_site(self):
        s = Served(self, self.up)
        for method, path, body in (("GET", "/api/update", None), ("POST", "/api/update/review", {"from": "downloads"}),
                                   ("POST", "/api/update/install", {"review_id": "x"}), ("POST", "/api/update/arm-undo", {}),
                                   ("POST", "/api/update/undo", {"arm_id": "x"})):
            with self.subTest(path=path):
                self.assertEqual(403, s.call(method, path, body, token=False)[0])
                self.assertEqual(403, s.call(method, path, body, host="example.org")[0])
                self.assertEqual(403, s.call(method, path, body, origin="http://example.org")[0])
        self.assertEqual(200, s.call("GET", "/api/update")[0])

    def test_a_body_over_one_kilobyte_is_refused(self):
        s = Served(self, self.up)
        status, body = s.call("POST", "/api/update/review", raw=json.dumps({"from": "downloads", "x": "a" * 2000}).encode())
        self.assertEqual((400, "too_large"), (status, body["code"]))

    def test_while_installing_every_other_route_answers_503_and_the_server_stops_after_the_answer(self):
        s = Served(self, self.up)
        status, body = s.call("POST", "/api/update/review", {"from": "downloads"})
        self.assertEqual(200, status)
        status, done = s.call("POST", "/api/update/install", {"review_id": body["review_id"]})
        self.assertEqual((200, True), (status, done["restart"]))
        s.thread.join(10)
        self.assertFalse(s.thread.is_alive(), "the server stopped so the helper can swap the files")
        other = Served(self, self.up)             # the same flag, if another request had come in time
        status, said = other.call("POST", "/api/change", {"x": 1})
        self.assertEqual((503, "updating"), (status, said["code"]))
        self.assertEqual(503, other.call("GET", "/api/projects")[0])
        self.assertEqual(200, other.call("GET", "/api/update")[0])

    def test_without_an_updater_the_routes_answer_in_plain_words(self):
        s = Served(self, None)
        status, body = s.call("GET", "/api/update")
        self.assertEqual((503, "no_updates"), (status, body["code"]))

    def test_no_request_body_is_logged(self):
        s = Served(self, self.up)
        with self.assertLogs("clark", level="DEBUG") as logs:
            s.call("POST", "/api/update/review", {"from": "downloads", "reinstall": False, "x": "secret-words"})
            sv.LOG.info("end")
        self.assertNotIn("secret-words", "\n".join(logs.output))


class FinishAtLaunchTest(Rig):
    def stopped_mid_way(self):
        body = self.reviewed()
        self.up.install({"review_id": body["review_id"]})

        def kill(name):
            if name == "swap:new:src":
                raise SystemExit("killed")
        try:
            h.run_update(h.marker_path(self.data), self.seams, fault=kill)
        except SystemExit:
            pass
        marker = h.marker_path(self.data)
        doc = json.loads(marker.read_text(encoding="utf-8"))
        doc["helper_pid"] = None                     # the helper was this test process; a killed helper's process is gone
        h.write_json(marker, doc)

    def test_the_launcher_puts_the_old_version_back_before_it_starts(self):
        old = snapshot(self.app)
        self.stopped_mid_way()
        said = []
        self.assertTrue(launch.finish_update(self.data, said.append))
        self.assertEqual(old, snapshot(self.app))
        self.assertFalse(h.marker_path(self.data).exists())
        self.assertEqual([h.MESSAGES["finished"]], said)
        self.assertTrue(launch.finish_update(self.data, said.append), "a second run does nothing")
        self.assertEqual(1, len(said))

    def test_no_marker_means_nothing_to_do(self):
        said = []
        self.assertTrue(launch.finish_update(self.data, said.append, run=lambda *a, **k: self.fail("nothing is run")))
        self.assertEqual([], said)

    def test_a_helper_still_running_stops_the_launch(self):
        said = []
        (self.data / "updates").mkdir(exist_ok=True)
        h.write_json(h.marker_path(self.data), {"helper_dir": ""})
        self.assertFalse(launch.finish_update(self.data, said.append, run=lambda *a, **k: (h.BUSY, "")))
        self.assertEqual([h.MESSAGES["busy"]], said)

    def test_a_helper_dir_outside_the_updates_folder_is_never_run(self):
        self.stopped_mid_way()
        marker = h.marker_path(self.data)
        doc = json.loads(marker.read_text(encoding="utf-8"))
        evil = self.root / "helper-evil"
        evil.mkdir()
        (evil / "update_helper.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
        doc["helper_dir"] = str(evil)
        h.write_json(marker, doc)
        ran = []
        launch.finish_update(self.data, lambda t: None, run=lambda py, code, args, timeout=0: ran.append(args[0]) or (0, ""))
        self.assertEqual([Path(h.__file__).resolve()], ran)

    def test_launch_stops_when_the_finish_says_so(self):
        self.assertEqual(1, launch.launch(8765, self.data, say=lambda t: None, finish=lambda folder, say: False,
                                          health=lambda *a: self.fail("nothing is asked")))


class WordsTest(unittest.TestCase):
    BANNED = __import__("re").compile(r"\b(zip|manifest|sha|path|vault|tracker|database|stage|staging|apply|refused|invalid)\b", 2)

    def test_every_sentence_is_plain(self):
        texts = list(up.MESSAGES.values()) + [up.UP_TO_DATE, up.INSTALLING, up.UNDOING, up.ARMED_FULL, up.ARMED_APP_ONLY,
                                              up.UNDO_DONE, up.INSTALLED, sv.MESSAGES["updating"], sv.MESSAGES["no_updates"]]
        for text in texts:
            with self.subTest(text=text):
                self.assertFalse(text.lower().startswith("clark"), text)
                self.assertIsNone(self.BANNED.search(text), text)
                self.assertTrue(text.endswith("."), text)

    def test_the_server_imports_no_clark_module_for_this(self):
        source = (ROOT / "src" / "clark" / "server.py").read_text(encoding="utf-8")
        self.assertNotIn("import updater", source)
        self.assertNotRegex(source, r"(?m)^(from clark|import clark)")


if __name__ == "__main__":
    unittest.main()
