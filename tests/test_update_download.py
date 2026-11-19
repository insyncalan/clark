"""Row 1327-B: Settings > Version and updates, the server's side of "check the newest release and download it inside clark".

The Updater gets a `fetch` seam (the module of row 1327-A, src/clark/update_fetch.py, in a real run): `latest(system)` answers the
offer or None, `download(asset, folder, progress, cancelled)` writes the file into `folder` and answers (path, sha256), and
`FetchError` (with a `kind` of "offline" or "unavailable") and `Cancelled` are its two exceptions. Here the seam is a fake: no
network, no sockets to the outside, no Chrome. The file it "downloads" is the fixture's real 0.3.1 update, so the checks that run
after it are the real ones (take_in, read_taken, plan, review).
Run: python3 dev/run_tests.py test_update_download
"""
import json
import logging
import threading
from pathlib import Path
from unittest import mock

from clark import platform, server as sv, update_install as ui, updater as up, updates
from test_update_helper import snapshot
from test_updater import Rig, Served
from test_updates import make_zip

NAME = "clark-0.3.1-mac.zip"
URL = "https://api.github.com/repos/example/clark/releases/assets/1"

# Every sentence this row adds for a person to read (the ruling table is ~/ag/1327-words.md). None starts with the product name,
# none holds a path, a zip, a manifest or a checksum, and none says "signed" or "signature" (the ticket's decision 3).
WORDS = {
    "READY": "Version {to} is ready to download.",
    "DOWNLOADING": "Downloading version {to}.",
    "CHECKED": "Downloaded and checked.",
    "NEWEST": "You have the newest version.",
    "OFFLINE": "Couldn't reach the releases page. Check your connection, then try again, or use a file instead.",
    "FAILED_CHECK": "This download didn't pass the checks, so nothing was installed. Download it again.",
    "CHECK_FIRST": "Look for a newer version first, then download it.",
}


class FetchError(Exception):
    def __init__(self, kind, detail=""):
        super().__init__(detail)
        self.kind = kind


class Cancelled(Exception):
    pass


class FakeFetch:
    """The seam. `gate` (an Event) holds a download after its first progress call until set; a cancel while held raises Cancelled
    the way the real one does, leaving its half file behind (the Updater tidies the folder)."""
    FetchError = FetchError
    Cancelled = Cancelled

    def __init__(self, payload, version="0.3.1", gate=None, error=None, download_error=None, chunk=1000):
        self.payload, self.gate, self.error, self.download_error, self.chunk = payload, gate, error, download_error, chunk
        self.offer = {"version": version, "date": "2026-11-18", "size": len(payload), "notes": "Fixes a typo.\n", "url": URL,
                      "name": f"clark-{version}-mac.zip"}
        self.latest_calls, self.download_calls, self.asked = 0, 0, []
        self.started = threading.Event()

    def latest(self, system):
        self.latest_calls += 1
        if self.error:
            raise self.error
        return dict(self.offer) if self.offer else None

    def download(self, asset, folder, progress, cancelled):
        self.download_calls += 1
        self.asked.append(asset["url"])
        folder = Path(folder)
        (folder / (asset["name"] + ".part")).write_bytes(self.payload[:self.chunk])
        progress(self.chunk, len(self.payload))
        self.started.set()
        if self.download_error:
            raise self.download_error
        if self.gate is not None:
            for _ in range(1000):
                if cancelled():
                    raise Cancelled()
                if self.gate.wait(0.01):
                    break
        if cancelled():
            raise Cancelled()
        path = folder / asset["name"]
        path.write_bytes(self.payload)
        (folder / (asset["name"] + ".part")).unlink(missing_ok=True)
        import hashlib
        progress(len(self.payload), len(self.payload))
        return path, hashlib.sha256(self.payload).hexdigest()


class Base(Rig):
    def setUp(self):
        super().setUp()
        patch = mock.patch.object(updates, "RELEASE_PUBLIC_KEY", updates.PLACEHOLDER_KEY)     # 1.3 is unsigned (ticket decision 3)
        patch.start()
        self.addCleanup(patch.stop)
        self.payload = self.download.read_bytes()
        self.fetch = FakeFetch(self.payload)
        self.up = self.make(fetch=self.fetch)

    def make(self, **kw):
        kw.setdefault("fetch", getattr(self, "fetch", None))
        return super().make(**kw)

    def check(self, **req):
        return self.up.check(req)

    def wait(self):
        thread = self.up._thread
        if thread is not None:
            thread.join(20)
            self.assertFalse(thread.is_alive())

    def begin(self, fetch=None):
        """Start a download held at its gate; waits until the fake is in it."""
        fetch = fetch or self.fetch
        self.assertEqual("ready", self.check()[1]["state"])
        status, body = self.up.download({})
        self.assertEqual((200, "downloading"), (status, body["state"]), body)
        self.assertTrue(fetch.started.wait(10))
        return body

    def releases(self):
        return sorted(p.name for p in (self.data / ui.RELEASES).glob("**/*") if p.is_file())

    def finished(self, look=True):
        """Download to the end (looking first unless `look` is False: Download again after a failed one needs no new look)."""
        if look:
            self.assertEqual("ready", self.check()[1]["state"])
        self.assertEqual("downloading", self.up.download({})[1]["state"])
        self.wait()
        return self.up.progress()[1]


class WordsTest(Base):
    def test_the_new_sentences_are_these_and_never_say_signed_or_signature(self):
        for key, text in WORDS.items():
            with self.subTest(key=key):
                self.assertEqual(text, getattr(up, key))
                self.assertNotRegex(text.lower(), r"signed|signature|\bzip\b|manifest|sha|/")
                self.assertFalse(text.startswith("clark"))

    def test_every_state_message_a_reply_carries_is_one_of_them_or_an_existing_refusal(self):
        said = []
        said.append(self.check()[1])
        said.append(self.up.download({})[1])
        self.wait()
        said.append(self.up.progress()[1])
        self.fetch.error = FetchError("offline")
        said.append(self.check(force=True)[1])
        for body in said:
            self.assertNotRegex(json.dumps(body).lower(), r"signed|signature")


class SignatureTest(Base):
    def test_with_a_real_key_in_force_a_download_with_no_signature_beside_it_fails_the_checks_in_plain_words(self):
        import _signing
        with mock.patch.object(updates, "RELEASE_PUBLIC_KEY", _signing.TEST_PUBLIC):
            body = self.finished()
        self.assertEqual(("failed", "unsigned", WORDS["FAILED_CHECK"]), (body["state"], body["code"], body["message"]))
        self.assertEqual([], self.releases())


class StatusTest(Base):
    def test_the_status_and_the_progress_never_reach_the_network(self):
        self.up.status()
        self.up.progress()
        self.up.status()
        self.assertEqual((0, 0), (self.fetch.latest_calls, self.fetch.download_calls))


class CheckTest(Base):
    def test_a_newer_release_is_offered_with_its_version_date_size_and_notes(self):
        status, body = self.check()
        self.assertEqual(200, status)
        self.assertEqual("ready", body["state"])
        self.assertEqual({"ok": True, "state": "ready", "version": "0.3.1", "date": "18-11-2026", "size": len(self.payload),
                          "notes": "Fixes a typo.", "message": WORDS["READY"].format(to="0.3.1")},
                         {k: body[k] for k in ("ok", "state", "version", "date", "size", "notes", "message")})

    def test_the_same_version_and_an_older_one_are_up_to_date_never_a_downgrade(self):
        for offered in ("0.3.0", "0.2.9"):
            with self.subTest(offered=offered):
                fetch = FakeFetch(self.payload, version=offered)
                self.up = self.make(fetch=fetch)
                status, body = self.check()
                self.assertEqual((200, "uptodate", WORDS["NEWEST"]), (status, body["state"], body["message"]))
                self.assertEqual("uptodate", self.up.progress()[1]["state"])

    def test_versions_compare_as_numbers_not_as_text(self):
        self.up = self.make(version="1.9.0", fetch=FakeFetch(self.payload, version="1.10.0"))
        self.assertEqual("ready", self.check()[1]["state"])
        self.up = self.make(version="1.10.0", fetch=FakeFetch(self.payload, version="1.9.0"))
        self.assertEqual("uptodate", self.check()[1]["state"])

    def test_a_release_with_no_file_for_this_system_is_up_to_date_and_a_bad_version_is_unavailable(self):
        self.fetch.offer = None
        self.assertEqual("uptodate", self.check()[1]["state"])
        self.fetch.offer = {"version": "1.x", "date": "2026-11-18", "size": 1, "notes": "", "url": URL, "name": NAME}
        self.up = self.make(fetch=self.fetch)
        self.assertEqual("unavailable", self.check()[1]["state"])

    def test_the_quiet_check_is_cached_for_sixty_seconds_and_the_button_is_not(self):
        self.check()
        self.check()
        self.assertEqual(1, self.fetch.latest_calls)
        self.clock.now += 59
        self.check()
        self.assertEqual(1, self.fetch.latest_calls)
        self.check(force=True)
        self.assertEqual(2, self.fetch.latest_calls, "Check now looks at once")
        self.check(force=True)
        self.assertEqual(3, self.fetch.latest_calls, "and every time")
        self.clock.now += 61
        self.check()
        self.assertEqual(4, self.fetch.latest_calls, "the cache ends after sixty seconds")

    def test_check_now_while_a_download_runs_makes_no_lookup_and_keeps_the_state(self):
        self.fetch.gate = threading.Event()
        self.addCleanup(self.fetch.gate.set)
        self.begin()
        calls = self.fetch.latest_calls
        status, body = self.check(force=True)
        self.assertEqual((200, "downloading"), (status, body["state"]))
        self.assertEqual(calls, self.fetch.latest_calls, "no outbound lookup while a download runs")
        self.fetch.gate.set()
        self.wait()

    def test_an_offline_lookup_says_so_in_plain_words_with_no_reason_and_no_address(self):
        self.fetch.error = FetchError("offline", "boom https://secret.example/x?q=1 /home/someone/clark")
        status, body = self.check()
        self.assertEqual((200, "offline", WORDS["OFFLINE"]), (status, body["state"], body["message"]))
        self.assertNotRegex(json.dumps(body), r"boom|http|secret|/home")

    def test_a_lookup_that_fails_for_any_other_reason_is_its_own_state_with_the_same_words(self):
        self.fetch.error = FetchError("unavailable", "403 rate limit")
        status, body = self.check()
        self.assertEqual((200, "unavailable", WORDS["OFFLINE"]), (status, body["state"], body["message"]))
        self.assertNotIn("403", json.dumps(body))
        self.fetch.error = RuntimeError("an unexpected one: /home/x")
        status, body = self.check(force=True)
        self.assertEqual((200, "unavailable"), (status, body["state"]))
        self.assertNotIn("/home", json.dumps(body))

    def test_a_failed_lookup_is_logged_once_by_kind_only(self):
        self.fetch.error = FetchError("offline", "https://secret.example/x?q=1 /home/someone/clark")
        with self.assertLogs("clark.updater", level="INFO") as logged:
            self.check()
        self.assertEqual(1, len(logged.records))
        self.assertNotRegex(logged.output[0], r"http|secret|/home|someone")
        self.assertIn("offline", logged.output[0])

    def test_the_request_is_checked(self):
        for bad in ({"force": "yes"}, {"x": 1}, {"force": 1}, [], "force"):
            with self.subTest(bad=bad):
                self.assertEqual((400, "bad_request"), (lambda r: (r[0], r[1]["code"]))(self.up.check(bad)))
        self.assertEqual(0, self.fetch.latest_calls)
        self.assertEqual(200, self.up.check(None)[0])
        self.assertEqual(200, self.up.check({"force": False})[0])

    def test_a_blocked_copy_gets_its_sentence_and_makes_no_outbound_call(self):
        with mock.patch.object(platform, "container_mode", return_value=True):
            status, body = self.check(force=True)
            self.assertEqual((409, "blocked", up.CONTAINER), (status, body["code"], body["message"]))
            self.assertEqual(409, self.up.download({})[0])
        with mock.patch.object(updates, "check_app_folder", side_effect=updates.UpdateError("git", "a source checkout")):
            status, body = self.check(force=True)
            self.assertEqual((409, "blocked", updates.MESSAGES["git"]), (status, body["code"], body["message"]))
            self.assertEqual(409, self.up.download({})[0])
        self.assertEqual((0, 0), (self.fetch.latest_calls, self.fetch.download_calls))


class DownloadTest(Base):
    def test_a_download_needs_an_offer_first(self):
        status, body = self.up.download({})
        self.assertEqual((409, "check_first", WORDS["CHECK_FIRST"]), (status, body["code"], body["message"]))
        self.assertEqual(0, self.fetch.download_calls)

    def test_the_request_is_checked(self):
        self.check()
        self.assertEqual(400, self.up.download({"url": "https://evil.example/x.zip"})[0])
        self.assertEqual(400, self.up.cancel({"x": 1})[0])
        self.assertEqual(0, self.fetch.download_calls)

    def test_a_second_start_while_one_runs_is_the_same_state_and_no_second_download(self):
        self.fetch.gate = threading.Event()
        self.addCleanup(self.fetch.gate.set)
        self.begin()
        first = self.up._thread
        status, body = self.up.download({})
        self.assertEqual((200, "downloading"), (status, body["state"]))
        self.assertIs(first, self.up._thread)
        self.assertEqual(1, self.fetch.download_calls)
        self.fetch.gate.set()
        self.wait()
        self.assertEqual(1, self.fetch.download_calls)

    def test_the_asset_asked_for_is_the_one_the_lookup_gave_and_only_that_one(self):
        self.finished()
        self.assertEqual([URL], self.fetch.asked)

    def test_the_progress_says_how_far_and_ends_checked_with_the_review_text_and_an_id_install_takes(self):
        self.fetch.gate = threading.Event()
        self.addCleanup(self.fetch.gate.set)
        self.begin()
        status, body = self.up.progress()
        self.assertEqual((200, "downloading", self.fetch.chunk, len(self.payload)),
                         (status, body["state"], body["done"], body["size"]))
        self.assertEqual(WORDS["DOWNLOADING"].format(to="0.3.1"), body["message"])
        self.assertNotIn("review_id", body)
        self.fetch.gate.set()
        self.wait()
        status, body = self.up.progress()
        self.assertEqual((200, "checked", WORDS["CHECKED"]), (status, body["state"], body["message"]))
        self.assertEqual("0.3.0", body["review"]["from"])
        self.assertEqual("0.3.1", body["review"]["to"])
        self.assertIn(".app/src/clark/added.py", body["review"]["added"]["names"])
        status, done = self.up.install({"review_id": body["review_id"]})
        self.assertEqual((200, True), (status, done["restart"]), done)

    def test_the_bytes_go_through_take_in_and_read_taken_once_and_come_from_the_downloaded_file(self):
        with mock.patch.object(ui, "read_taken", wraps=ui.read_taken) as read, mock.patch.object(ui, "take_in", wraps=ui.take_in) as take:
            body = self.finished()
        self.assertEqual("checked", body["state"])
        self.assertEqual(1, read.call_count)
        self.assertEqual(1, take.call_count)
        self.assertEqual(self.payload, (self.data / ui.RELEASES / NAME).read_bytes())
        self.assertEqual([NAME], self.releases(), "the working folder is empty once the file is kept")

    def test_a_file_whose_checksum_differs_from_the_one_the_download_reported_is_refused(self):
        real_download = self.fetch.download

        def lying(asset, folder, progress, cancelled):
            path, digest = real_download(asset, folder, progress, cancelled)
            return path, "0" * 64
        self.fetch.download = lying
        body = self.finished()
        self.assertEqual(("failed", "damaged"), (body["state"], body["code"]))
        self.assertEqual([], self.releases())

    def test_nothing_installs_itself_a_day_later(self):
        with mock.patch.object(ui, "hand_over") as hand_over, mock.patch.object(ui, "back_up") as back_up:
            self.assertEqual("checked", self.finished()["state"])
            self.clock.now += 24 * 3600
            self.up.status()
            self.up.progress()
            self.check()
        self.assertEqual((0, 0, 0), (hand_over.call_count, back_up.call_count, len(self.started)))
        self.assertFalse(self.up.installing())

    def test_the_review_expires_after_fifteen_minutes_and_then_the_state_is_ready_again(self):
        body = self.finished()
        self.clock.now += up.REVIEW_SECONDS + 60
        self.assertEqual("ready", self.up.progress()[1]["state"])
        status, said = self.up.install({"review_id": body["review_id"]})
        self.assertEqual((409, "review_again"), (status, said["code"]))

    def test_a_review_made_from_a_file_instead_takes_the_checked_state_away(self):
        self.finished()
        self.assertEqual(200, self.up.review({"from": "downloads"})[0])
        self.assertEqual("ready", self.up.progress()[1]["state"])

    def test_a_download_refuses_while_an_install_runs(self):
        self.check()
        self.up._installing = True
        status, body = self.up.download({})
        self.assertEqual((409, "busy"), (status, body["code"]))
        self.assertEqual(0, self.fetch.download_calls)
        self.assertEqual(409, self.up.check({"force": True})[0])
        self.assertEqual(1, self.fetch.latest_calls)

    def test_a_download_that_breaks_offline_is_the_offline_state_and_leaves_nothing_behind(self):
        self.fetch.download_error = FetchError("offline", "https://secret.example")
        body = self.finished()
        self.assertEqual(("offline", WORDS["OFFLINE"]), (body["state"], body["message"]))
        self.assertNotRegex(json.dumps(body), r"http|secret")
        self.assertEqual([], self.releases())

    def test_an_unexpected_error_in_the_download_is_the_failed_state_with_the_general_words(self):
        self.fetch.download_error = RuntimeError("/home/someone/x")
        body = self.finished()
        self.assertEqual(("failed", up.MESSAGES["generic"]), (body["state"], body["message"]))
        self.assertNotIn("/home", json.dumps(body))
        self.assertEqual([], self.releases())
        self.fetch.download_error = None
        self.assertEqual("checked", self.finished(look=False)["state"], "Download again starts clean")


class FailedCheckTest(Base):
    def bad_payload(self):
        def tweak(files):
            rel = next(r for r in files if r.endswith("src/clark/x.py"))
            files[rel] = files[rel] + b"# changed\n"
        folder = self.root / "bad"
        folder.mkdir()
        return make_zip(folder, version="0.3.1", tweak=tweak).read_bytes()

    def test_a_file_that_fails_the_checks_is_failed_nothing_is_changed_and_the_kept_copy_goes(self):
        self.fetch.payload = self.bad_payload()
        before = snapshot(self.app)
        body = self.finished()
        self.assertEqual(("failed", WORDS["FAILED_CHECK"]), (body["state"], body["message"]))
        self.assertEqual(before, snapshot(self.app))
        self.assertEqual([], self.releases())
        self.assertIsNone(self.up.reviewed)
        self.fetch.payload = self.payload
        self.assertEqual("checked", self.finished(look=False)["state"], "Download again starts clean")

    def refusal(self, payload, installed):
        """The sentence the existing checks give for these bytes (what Use a file instead would say)."""
        folder = self.root / "oracle"
        folder.mkdir(exist_ok=True)
        source = folder / NAME
        source.write_bytes(payload)
        kept, digest = ui.take_in(source, self.data, "mac")
        try:
            ui.read_taken(kept, digest, "mac", installed, 2)
        except updates.UpdateError as e:
            return e
        finally:
            kept.unlink(missing_ok=True)
        self.fail("the existing checks did not refuse")

    def test_a_file_for_another_system_an_older_or_the_same_version_say_the_existing_sentence(self):
        folder = self.root / "other"
        folder.mkdir()
        windows = make_zip(folder, version="0.3.1", system="windows").read_bytes()
        for key, payload, installed in (("system", windows, "0.3.0"), ("older", self.payload, "0.4.0"),
                                        ("same", self.payload, "0.3.1")):
            with self.subTest(key=key):
                self.fetch.payload = payload
                self.up = self.make(fetch=self.fetch)
                self.assertEqual("ready", self.check()[1]["state"])
                self.up.version = installed
                self.assertEqual("downloading", self.up.download({})[1]["state"])
                self.wait()
                body = self.up.progress()[1]
                expected = self.refusal(payload, installed)
                self.assertEqual(key, expected.key)
                self.assertEqual(("failed", key, expected.message), (body["state"], body["code"], body["message"]))
                self.assertEqual([], self.releases())


class CancelTest(Base):
    def test_cancel_ends_ready_again_the_half_file_goes_and_an_older_kept_copy_stays(self):
        kept = self.data / ui.RELEASES
        kept.mkdir(exist_ok=True)
        (kept / "clark-0.3.0-mac.zip").write_bytes(b"an older kept copy")
        self.fetch.gate = threading.Event()
        self.addCleanup(self.fetch.gate.set)
        self.begin()
        status, body = self.up.cancel({})
        self.assertEqual((200, "ready"), (status, body["state"]))
        self.assertEqual("ready", self.up.progress()[1]["state"])
        self.assertEqual(["clark-0.3.0-mac.zip"], self.releases())
        self.assertEqual(b"an older kept copy", (kept / "clark-0.3.0-mac.zip").read_bytes())
        self.assertEqual(1, self.fetch.download_calls)

    def test_a_cancelled_download_can_be_started_again(self):
        self.fetch.gate = threading.Event()
        self.addCleanup(self.fetch.gate.set)
        self.begin()
        self.up.cancel({})
        self.fetch.gate.set()
        self.fetch.started.clear()
        self.assertEqual("downloading", self.up.download({})[1]["state"])
        self.wait()
        self.assertEqual("checked", self.up.progress()[1]["state"])

    def test_cancel_when_nothing_runs_changes_nothing(self):
        self.assertEqual("idle", self.up.cancel({})[1]["state"])
        self.check()
        self.assertEqual("ready", self.up.cancel({})[1]["state"])
        self.up.download({})
        self.wait()
        self.assertEqual("checked", self.up.cancel({})[1]["state"])


class UseAFileTest(Base):
    def test_use_a_file_instead_still_reviews_the_newest_file_in_downloads(self):
        self.check()
        body = self.reviewed()
        self.assertEqual("0.3.1", body["review"]["to"])
        self.chosen = self.download
        status, body = self.up.review({"from": "file"})
        self.assertEqual(200, status)
        self.assertEqual(0, self.fetch.download_calls)


class RoutesTest(Base):
    ROUTES = (("POST", "/api/update/check", {}), ("POST", "/api/update/download", {}), ("POST", "/api/update/cancel", {}),
              ("GET", "/api/update/progress", None))

    def test_each_new_route_needs_the_token_the_host_and_this_site(self):
        s = Served(self, self.up)
        for method, path, body in self.ROUTES:
            with self.subTest(path=path):
                self.assertEqual(403, s.call(method, path, body, token=False)[0])
                self.assertEqual(403, s.call(method, path, body, host="example.org")[0])
                self.assertEqual(403, s.call(method, path, body, origin="http://example.org")[0])
        self.assertEqual(0, self.fetch.latest_calls)

    def test_a_post_route_does_not_answer_a_get_and_the_progress_does_not_answer_a_post(self):
        s = Served(self, self.up)
        for path in ("/api/update/check", "/api/update/download", "/api/update/cancel"):
            self.assertEqual(404, s.call("GET", path)[0], path)
        self.assertEqual(404, s.call("POST", "/api/update/progress", {})[0])

    def test_the_post_routes_have_a_body_cap_of_one_kilobyte_or_less_and_are_in_the_update_list(self):
        for path in ("/api/update/check", "/api/update/download", "/api/update/cancel"):
            self.assertLessEqual(sv.ROUTE_BODY_LIMITS[path], 1024, path)
            self.assertIn(path, sv.POST_ROUTES)
        self.assertIn("/api/update/progress", sv.GET_ROUTES)
        self.assertEqual(set(sv.UPDATE_ROUTES) - {"/api/update", "/api/update/review", "/api/update/install",
                                                  "/api/update/arm-undo", "/api/update/undo"},
                         {"/api/update/check", "/api/update/download", "/api/update/cancel", "/api/update/progress"})
        s = Served(self, self.up)
        status, body = s.call("POST", "/api/update/check", raw=json.dumps({"force": True, "x": "a" * 2000}).encode())
        self.assertEqual((400, "too_large"), (status, body["code"]))

    def test_the_whole_way_through_the_server_check_download_progress_install(self):
        s = Served(self, self.up)
        status, body = s.call("POST", "/api/update/check", {"force": True})
        self.assertEqual((200, "ready"), (status, body["state"]))
        self.assertEqual("downloading", s.call("POST", "/api/update/download", {})[1]["state"])
        self.wait()
        status, body = s.call("GET", "/api/update/progress")
        self.assertEqual((200, "checked"), (status, body["state"]))
        status, done = s.call("POST", "/api/update/install", {"review_id": body["review_id"]})
        self.assertEqual((200, True), (status, done["restart"]))

    def test_while_installing_the_new_routes_answer_with_the_updaters_own_words_not_the_503(self):
        s = Served(self, self.up)
        self.up._installing = True
        status, body = s.call("POST", "/api/update/check", {})
        self.assertEqual((409, "busy"), (status, body["code"]))
        self.assertEqual(200, s.call("GET", "/api/update/progress")[0])

    def test_without_an_updater_the_new_routes_are_unavailable(self):
        s = Served(self, None)
        self.assertEqual(503, s.call("POST", "/api/update/check", {})[0])
        self.assertEqual(503, s.call("GET", "/api/update/progress")[0])


if __name__ == "__main__":
    import unittest
    unittest.main()
