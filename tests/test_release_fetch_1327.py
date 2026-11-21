"""Settings › Version and updates: look for the newest release on the releases page and download it (release_fetch.py, updater.py).

No network: the one outbound call goes through a fake opener that answers from memory and records every request it was given.
Run: python3 dev/run_tests.py test_release_fetch_1327
"""
import hashlib
import io
import json
import os
import shutil
import socket
import tempfile
import unittest
import urllib.request
from pathlib import Path
from unittest import mock

from clark import platform, release_fetch as rf, server as sv, update_install as ui, updater as up, updates
from test_updater import Rig, Served
from test_updates import make_zip

ASSET_HOST = "https://github.com/insyncalan/clark/releases/download/v0.3.2/"


class Reply(io.BytesIO):
    def __init__(self, body, url, length=True):
        super().__init__(body)
        self.url = url
        self.headers = {"Content-Length": str(len(body))} if length else {}

    def geturl(self):
        return self.url


def release_doc(version="0.3.2", system="mac", size=100, digest=None, url=None, **extra):
    name = f"clark-{version}-{system}.zip"
    asset = {"name": name, "size": size, "browser_download_url": url or f"https://github.com/insyncalan/clark/releases/download/v{version}/{name}"}
    if digest:
        asset["digest"] = "sha256:" + digest
    doc = {"tag_name": f"v{version}", "published_at": "2026-11-18T09:00:00Z", "body": "Faster Dashboard.", "assets": [asset]}
    doc.update(extra)
    return doc


class Net:
    """A fake opener: `routes` maps an address to bytes, an exception or a callable; `calls` keeps every request."""

    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def __call__(self, request, timeout):
        self.calls.append((request, timeout))
        got = self.routes.get(request.full_url)
        if got is None:
            raise OSError("no route")
        if isinstance(got, Exception):
            raise got
        return got(request) if callable(got) else Reply(got, request.full_url)


def api(doc, extra=None):
    routes = {rf.API_URL: json.dumps(doc).encode()}
    routes.update(extra or {})
    return Net(routes)


class AddressTest(unittest.TestCase):
    def test_only_https_on_the_pinned_hosts(self):
        for url, ok in (("https://api.github.com/repos/x", True), ("https://github.com/a/b.zip", True),
                        ("https://objects.githubusercontent.com/x", True), ("https://release-assets.githubusercontent.com/x", True),
                        ("http://github.com/a", False), ("https://evil.example/a", False), ("https://github.com.evil.example/a", False),
                        ("https://user@github.com/a", False), ("https://user" + ":" + "pw@github.com/a", False), ("https://github.com:8443/a", False),
                        ("https://github.com:443/a", True), ("ftp://github.com/a", False), ("//github.com/a", False), ("", False),
                        ("https://[::1/", False), ("file:///etc/passwd", False)):
            with self.subTest(url=url):
                self.assertIs(ok, rf.allowed(url))

    def test_a_refused_address_is_never_asked(self):
        net = Net({})
        with self.assertRaises(rf.FetchError) as caught:
            rf.download("http://github.com/a.zip", Path(tempfile.mkdtemp()) / "x.zip", opener=net)
        self.assertEqual("refused", caught.exception.key)
        self.assertEqual([], net.calls)

    def test_an_answer_from_another_address_is_refused(self):
        net = Net({rf.API_URL: lambda req: Reply(b"{}", "https://evil.example/x")})
        with self.assertRaises(rf.FetchError) as caught:
            rf.latest("mac", net)
        self.assertEqual("refused", caught.exception.key)

    def test_a_redirect_off_the_hosts_is_refused_and_one_inside_them_keeps_only_two_headers(self):
        handler = rf._Redirects()
        first = urllib.request.Request(rf.API_URL, headers={"User-Agent": "clark", "Accept": "a", "Authorization": "t", "Cookie": "c"})
        with self.assertRaises(rf.FetchError) as caught:
            handler.redirect_request(first, None, 302, "Found", {}, "https://evil.example/a")
        self.assertEqual("refused", caught.exception.key)
        with self.assertRaises(rf.FetchError):
            handler.redirect_request(first, None, 302, "Found", {}, "http://github.com/a")
        new = handler.redirect_request(first, None, 302, "Found", {}, "https://objects.githubusercontent.com/a")
        self.assertEqual({"user-agent", "accept"}, {k.lower() for k in new.headers})
        self.assertEqual(5, rf._Redirects.max_redirections)


class LatestTest(unittest.TestCase):
    def test_the_request_carries_nothing_about_the_person(self):
        net = api(release_doc())
        found = rf.latest("mac", net)
        (request, timeout), = net.calls
        self.assertEqual(rf.API_URL, request.full_url)
        self.assertEqual("GET", request.get_method())
        self.assertIsNone(request.data)
        self.assertEqual({"user-agent": "clark", "accept": rf.ACCEPT}, {k.lower(): v for k, v in request.header_items()})
        self.assertEqual((15, 15), (rf.TIMEOUT, timeout))
        self.assertEqual("0.3.2", found["version"])
        self.assertEqual("2026-11-18", found["date"])
        self.assertEqual(100, found["size"])
        self.assertEqual("Faster Dashboard.", found["notes"])
        self.assertIsNone(found["digest"])
        self.assertIsNone(found["sig_url"])

    def test_the_file_is_the_one_for_this_computer(self):
        doc = release_doc(system="windows")
        doc["assets"].append(release_doc(system="mac", size=7)["assets"][0])
        self.assertEqual(7, rf.latest("mac", api(doc))["size"])
        self.assertEqual(100, rf.latest("windows", api(doc))["size"])

    def test_a_release_without_a_file_for_this_computer_is_not_offline(self):
        for doc in (release_doc(system="linux"), {**release_doc(), "assets": []}, {**release_doc(), "assets": "x"}, {**release_doc(), "assets": [5]}):
            with self.subTest(doc=doc["assets"]):
                with self.assertRaises(rf.FetchError) as caught:
                    rf.latest("mac", api(doc))
                self.assertEqual("nofile", caught.exception.key)

    def test_a_file_named_for_another_version_than_the_tag_is_not_taken(self):
        doc = release_doc()
        doc["assets"][0]["name"] = "clark-0.3.1-mac.zip"
        with self.assertRaises(rf.FetchError):
            rf.latest("mac", api(doc))

    def test_nonsense_answers_are_unreadable_not_a_crash_and_not_offline(self):
        bad = [b"", b"<html>", b"[]", b"null", b'{"tag_name": 5}', b'{"tag_name": "v1.x"}', b'{"tag_name": "v1.2.3.dev1"}',
               json.dumps(release_doc(draft=True)).encode(), json.dumps(release_doc(prerelease=True)).encode(),
               b"\xff\xfe", b'{"tag_name": "v0.3.2", "assets": [{"name": "clark-0.3.2-mac.zip", "size": 1e400, "browser_download_url": "x"}]}',
               b'{"a": ' + b"9" * 40 + b"}"]
        for raw in bad:
            with self.subTest(raw=raw[:30]):
                with self.assertRaises(rf.FetchError) as caught:
                    rf.latest("mac", Net({rf.API_URL: raw}))
                self.assertEqual("unreadable", caught.exception.key)

    def test_unusable_file_facts_are_refused(self):
        for size in (0, -1, "100", True, None, 1.5):
            doc = release_doc()
            doc["assets"][0]["size"] = size
            with self.subTest(size=size), self.assertRaises(rf.FetchError):
                rf.latest("mac", api(doc))
        for url in ("http://github.com/x.zip", "https://evil.example/clark-0.3.2-mac.zip", None, 5):
            doc = release_doc()
            doc["assets"][0]["browser_download_url"] = url
            with self.subTest(url=url), self.assertRaises(rf.FetchError):
                rf.latest("mac", api(doc))

    def test_a_file_over_the_cap_is_too_big(self):
        with self.assertRaises(rf.FetchError) as caught:
            rf.latest("mac", api(release_doc(size=updates.MAX_ZIP_BYTES + 1)))
        self.assertEqual("toobig", caught.exception.key)
        self.assertEqual(updates.MAX_ZIP_BYTES, rf.latest("mac", api(release_doc(size=updates.MAX_ZIP_BYTES)))["size"])

    def test_an_answer_over_the_cap_is_offline_and_one_at_the_cap_is_read(self):
        raw = json.dumps(release_doc()).encode()
        self.assertEqual(1024 * 1024, rf.MAX_API_BYTES)
        self.assertEqual("0.3.2", rf.latest("mac", Net({rf.API_URL: raw.ljust(rf.MAX_API_BYTES)}))["version"])
        with self.assertRaises(rf.FetchError):
            rf.latest("mac", Net({rf.API_URL: raw.ljust(rf.MAX_API_BYTES + 1)}))

    def test_a_dev_version_is_not_a_release(self):
        with self.assertRaises(rf.FetchError):
            rf.latest("mac", api(release_doc(version="0.3.2.dev1")))

    def test_the_digest_is_kept_only_when_it_is_a_sha256(self):
        good = "a" * 64
        self.assertEqual(good, rf.latest("mac", api(release_doc(digest=good)))["digest"])
        for text in ("sha256:" + "A" * 64, "sha256:" + "a" * 63, "md5:" + "a" * 32, "a" * 64):
            doc = release_doc()
            doc["assets"][0]["digest"] = text
            with self.subTest(text=text[:12]):
                self.assertIsNone(rf.latest("mac", api(doc))["digest"])

    def test_notes_are_cut_and_the_date_is_empty_when_missing(self):
        doc = release_doc(body="x" * (rf.updates.MAX_NOTES + 500))
        del doc["published_at"]
        found = rf.latest("mac", api(doc))
        self.assertEqual(rf.updates.MAX_NOTES + 1, len(found["notes"]))
        self.assertEqual("", found["date"])
        self.assertEqual("There are no notes for this version.", rf.NO_NOTES)
        self.assertEqual(rf.NO_NOTES, rf.latest("mac", api(release_doc(body=5)))["notes"])

    def test_every_way_the_call_can_fail_is_offline(self):
        for err in (socket.timeout("slow"), OSError("down"), urllib.request.URLError("tls"), ConnectionResetError()):
            with self.subTest(err=type(err).__name__):
                with self.assertRaises(rf.FetchError) as caught:
                    rf.latest("mac", Net({rf.API_URL: err}))
                self.assertEqual("offline", caught.exception.key)
                self.assertNotIn("slow", caught.exception.detail)

    def test_newer_is_a_real_comparison(self):
        for found, installed, ok in (("1.3.2", "1.3.1", True), ("1.3.1", "1.3.1", False), ("1.3.0", "1.3.1", False),
                                     ("1.10.0", "1.9.9", True), ("1.9.9", "1.10.0", False), ("x", "1.0.0", False), ("1.0.0", "1.0.1.dev3", False),
                                     ("1.0.1", "1.0.1.dev3", True)):
            with self.subTest(found=found, installed=installed):
                self.assertIs(ok, rf.newer(found, installed))


class DownloadTest(unittest.TestCase):
    URL = ASSET_HOST + "clark-0.3.2-mac.zip"

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark fetch "))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.dest = self.dir / "clark-0.3.2-mac.zip"
        self.body = os.urandom(3000)

    def net(self, body=None, length=True):
        return Net({self.URL: lambda req: Reply(self.body if body is None else body, self.URL, length)})

    def left(self):
        return sorted(p.name for p in self.dir.iterdir())

    def test_the_whole_file_is_saved_and_its_digest_returned(self):
        seen = []
        digest = rf.download(self.URL, self.dest, progress=lambda done, total: seen.append((done, total)), expected_size=3000,
                             digest=hashlib.sha256(self.body).hexdigest(), opener=self.net())
        self.assertEqual(hashlib.sha256(self.body).hexdigest(), digest)
        self.assertEqual(self.body, self.dest.read_bytes())
        self.assertEqual([self.dest.name], self.left())
        self.assertEqual([(3000, 3000)], seen)

    def test_it_streams_in_chunks_and_reports_each(self):
        seen = []
        with mock.patch.object(updates, "CHUNK", 1000):
            rf.download(self.URL, self.dest, progress=lambda done, total: seen.append(done), opener=self.net())
        self.assertEqual([1000, 2000, 3000], seen)

    def test_a_wrong_digest_or_length_leaves_nothing(self):
        for kw in ({"digest": "0" * 64}, {"expected_size": 2999}, {"expected_size": 3001}):
            with self.subTest(kw=kw), self.assertRaises(rf.FetchError) as caught:
                rf.download(self.URL, self.dest, opener=self.net(), **kw)
            self.assertEqual("mismatch" if "digest" in kw else "damaged", caught.exception.key)
            self.assertEqual([], self.left())

    def test_a_download_that_runs_past_the_cap_stops_and_leaves_nothing(self):
        with mock.patch.object(updates, "MAX_ZIP_BYTES", 2000), mock.patch.object(updates, "CHUNK", 1000):
            with self.assertRaises(rf.FetchError) as caught:
                rf.download(self.URL, self.dest, opener=self.net(length=False))
        self.assertEqual("toobig", caught.exception.key)
        self.assertEqual([], self.left())

    def test_a_length_over_the_cap_is_refused_before_a_byte_is_read(self):
        reads = []
        class Counts(Reply):
            def read(self, n=-1):
                reads.append(n)
                return super().read(n)
        with mock.patch.object(updates, "MAX_ZIP_BYTES", 2000):
            with self.assertRaises(rf.FetchError) as caught:
                rf.download(self.URL, self.dest, opener=Net({self.URL: lambda req: Counts(self.body, self.URL)}))
        self.assertEqual([], reads)
        self.assertEqual("toobig", caught.exception.key)
        self.assertEqual([], self.left())

    def test_cancel_stops_at_the_next_chunk_and_removes_the_partial_file(self):
        calls = []
        def cancelled():
            calls.append(1)
            return len(calls) > 1
        with mock.patch.object(updates, "CHUNK", 1000):
            with self.assertRaises(rf.FetchError) as caught:
                rf.download(self.URL, self.dest, cancelled=cancelled, opener=self.net())
        self.assertEqual("cancelled", caught.exception.key)
        self.assertEqual([], self.left())

    def test_a_stopped_connection_is_offline_and_leaves_nothing(self):
        class Breaks(Reply):
            def read(self, n=-1):
                if self.tell() >= 1000:
                    raise ConnectionResetError()
                return super().read(1000)
        net = Net({self.URL: lambda req: Breaks(self.body, self.URL)})
        with self.assertRaises(rf.FetchError) as caught:
            rf.download(self.URL, self.dest, opener=net)
        self.assertEqual("offline", caught.exception.key)
        self.assertEqual([], self.left())

    def test_a_finished_file_is_not_replaced_by_a_failed_one(self):
        self.dest.write_bytes(b"whole")
        with self.assertRaises(rf.FetchError):
            rf.download(self.URL, self.dest, digest="0" * 64, opener=self.net())
        self.assertEqual(b"whole", self.dest.read_bytes())


class Served2(Rig):
    """An Updater whose releases page is a fake: the release for 0.3.2 is a real fixture zip, served from memory."""

    def setUp(self):
        super().setUp()
        os.unlink(self.download)                         # nothing in Downloads: the update can only come from the releases page
        self.zip_dir = Path(tempfile.mkdtemp(prefix="clark zips "))
        self.addCleanup(shutil.rmtree, self.zip_dir, True)
        self.set_release("0.3.2")

    def set_release(self, version, **kw):
        path = make_zip(self.zip_dir, version=version, **kw)
        self.zip = path.read_bytes()
        name = path.name
        self.url = f"https://github.com/insyncalan/clark/releases/download/v{version}/{name}"
        self.doc = release_doc(version=version, size=len(self.zip), digest=hashlib.sha256(self.zip).hexdigest())
        self.sig_url = self.url + ".sig"
        self.sig = Path(str(path) + ".sig").read_bytes()
        self.doc["assets"].append({"name": name + ".sig", "size": len(self.sig), "browser_download_url": self.sig_url})
        self.serve = lambda: Net({rf.API_URL: json.dumps(self.doc).encode(), self.url: lambda req: Reply(self.zip, self.url),
                                  self.sig_url: lambda req: Reply(self.sig, self.sig_url)})
        self.net = self.serve()
        self.up = self.make(release_opener=self.net, spawn=lambda work: work())

    def tree(self):
        return {str(p.relative_to(self.app)): p.read_bytes() for p in sorted(self.app.rglob("*")) if p.is_file()}


class QuietLookTest(Served2):
    def asks(self):
        return [c[0].full_url for c in self.net.calls]

    def test_the_first_status_looks_once_and_never_again_by_itself(self):
        self.assertEqual([], self.asks())
        status, body = self.up.status()
        self.assertEqual(1, len(self.asks()))
        self.assertEqual("avail", body["latest"]["state"])
        for _ in range(3):
            self.up.status()
        self.assertEqual(1, len(self.asks()))

    def test_check_now_looks_again(self):
        self.up.status()
        status, body = self.up.check({})
        self.assertEqual((200, 2), (status, len(self.asks())))
        self.assertEqual("avail", body["latest"]["state"])

    def test_the_size_is_the_one_size_text_rule_and_the_notes_are_whole(self):
        self.doc["body"] = "n" * 3000
        for size, text in ((400_000, "0.4 MB"), (1_000_000, "1.0 MB"), (12_500_000, "13 MB"), (38_400_000, "38 MB"), (10, "0.1 MB")):
            with self.subTest(size=size):
                self.doc["assets"][0]["size"] = size
                self.net.routes[rf.API_URL] = json.dumps(self.doc).encode()
                latest = self.up.check({})[1]["latest"]
                self.assertEqual((text, updates.size_text(size), 3000), (latest["size"], latest["size"], len(latest["notes"])))

    def test_what_the_page_is_told(self):
        latest = self.up.status()[1]["latest"]
        self.assertEqual({"state", "version", "date", "size", "notes", "checked"}, set(latest))
        self.assertEqual(("avail", "0.3.2", "18-11-2026", "Faster Dashboard."), (latest["state"], latest["version"], latest["date"], latest["notes"]))
        self.assertRegex(latest["size"], r"^\d+(\.\d)? MB$")
        self.assertRegex(latest["checked"], r"^\d\d-\d\d-\d{4} \d\d:\d\d$")
        self.assertNotIn("github", json.dumps(self.up.status()[1]))        # no address, no digest goes to the page

    def test_the_time_checked_comes_from_the_clock(self):
        self.up = self.make(release_opener=self.net, spawn=lambda work: work(), wall=lambda: 1_700_000_000)
        want = __import__("time").strftime("%d-%m-%Y %H:%M", __import__("time").localtime(1_700_000_000))
        self.assertEqual(want, self.up.status()[1]["latest"]["checked"])

    def test_an_equal_or_older_release_is_up_to_date(self):
        for version in ("0.3.0", "0.2.9"):
            with self.subTest(version=version):
                self.set_release(version)
                self.assertEqual("latest", self.up.status()[1]["latest"]["state"])
                self.assertEqual("latest", self.up.check({})[1]["latest"]["state"])
                self.assertEqual(409, self.up.download({})[0])

    def test_offline_is_a_state_with_its_sentence_not_an_error(self):
        self.net.routes[rf.API_URL] = OSError("down")
        status, body = self.up.status()
        self.assertEqual(200, status)
        self.assertEqual({"state": "offline", "message": up.FETCH_OFFLINE}, {k: v for k, v in body["latest"].items() if k != "checked"})
        self.assertEqual((200, "offline"), (self.up.check({})[0], self.up.check({})[1]["latest"]["state"]))

    def test_an_unexpected_error_in_the_look_is_not_called_offline(self):
        self.net.routes[rf.API_URL] = ValueError("boom")        # not an OSError: the fetcher turns it into a failed call, which is offline
        self.assertEqual("offline", self.up.status()[1]["latest"]["state"])
        with mock.patch.object(rf, "latest", side_effect=RuntimeError("boom")):
            got = self.up.check({})[1]["latest"]
        self.assertEqual(("unavailable", up.FETCH_BAD), (got["state"], got["message"]))

    def test_nothing_is_asked_where_updates_are_not_possible(self):
        with mock.patch.object(platform, "container_mode", return_value=True):
            status, body = self.up.status()
            self.assertEqual((None, None), (body["latest"], body["fetch"]))
            self.assertEqual(409, self.up.check({})[0])
            self.assertEqual(409, self.up.download({})[0])
        self.assertEqual([], self.asks())

    def test_the_updater_sends_no_body_and_check_takes_none(self):
        for call in (self.up.check, self.up.download, self.up.cancel):
            with self.subTest(call=call.__name__):
                self.assertEqual(400, call({"x": 1})[0])
                self.assertEqual(400, call([])[0])

    def test_no_sentence_about_the_releases_page_says_signed(self):
        for text in (up.FETCH_OFFLINE, up.FETCH_BAD, up.FETCH_CANCELLED, up.NO_LATEST):
            with self.subTest(text=text):
                self.assertNotRegex(text.lower(), r"sign|zip|manifest|sha|/|\\")
                if text != up.FETCH_OFFLINE:      # Row 1327 table row 7 (comment 7016158346) is the approved offline sentence, and it begins "clark"
                    self.assertNotRegex(text, r"^clark")


class DownloadFlowTest(Served2):
    def ready(self):
        self.up.status()
        self.assertEqual(200, self.up.download({})[0])
        fetch = self.up.status()[1]["fetch"]
        self.assertEqual("ready", fetch["state"], fetch)
        return fetch

    def test_a_download_ends_in_a_checked_review_and_installs_nothing(self):
        before = self.tree()
        fetch = self.ready()
        self.assertEqual("0.3.2", fetch["version"])
        self.assertEqual("0.3.0", fetch["review"]["from"])
        self.assertEqual("0.3.2", fetch["review"]["to"])
        self.assertEqual(before, self.tree())
        self.assertEqual([], self.started)
        self.assertFalse(self.up.installing())
        self.assertEqual([], [p.name for p in (self.data / "fetched").iterdir()])      # the downloaded copy is not kept

    def test_the_same_checks_run_on_the_downloaded_bytes(self):
        calls = []
        real = ui.read_taken
        with mock.patch.object(ui, "read_taken", side_effect=lambda *a, **k: calls.append(a[1]) or real(*a, **k)):
            fetch = self.ready()
        self.assertEqual([hashlib.sha256(self.zip).hexdigest()], calls)
        self.assertEqual(hashlib.sha256(self.zip).hexdigest(), fetch["review"]["checksum"])

    def test_the_signature_comes_with_the_download_once_a_key_is_in_force(self):
        self.ready()
        self.assertIn(self.sig_url, [c[0].full_url for c in self.net.calls])
        self.assertEqual([], [p.name for p in (self.data / "fetched").iterdir()])
        with mock.patch.object(updates, "signature_required", return_value=False):
            self.net.calls.clear()
            self.up.cancel({})
            self.up.status()
            self.up.check({})
            self.up.download({})
        self.assertNotIn(self.sig_url, [c[0].full_url for c in self.net.calls])      # while the key is the placeholder, none is asked for

    def test_a_missing_or_wrong_signature_fails_the_check(self):
        for bad in (None, b"x" * 64, b"short"):
            with self.subTest(bad=bad):
                if bad is None:
                    del self.net.routes[self.sig_url]
                else:
                    self.net.routes[self.sig_url] = lambda req, b=bad: Reply(b, self.sig_url)
                self.up.status()
                self.up.download({})
                self.assertEqual("failed", self.up.status()[1]["fetch"]["state"])
                self.assertIsNone(self.up.reviewed)

    def test_a_zip_with_one_wrong_file_inside_is_refused(self):
        def tweak(files):
            files[next(iter(files))] = b"changed after the manifest"
        self.set_release("0.3.2", tweak=tweak)
        self.up.status()
        self.up.download({})
        fetch = self.up.status()[1]["fetch"]
        self.assertEqual({"state": "failed", "version": "0.3.2", "message": up.FETCH_TOOBIG}, fetch)
        self.assertIsNone(self.up.reviewed)
        self.assertIsNone(self.up.fetched)

    def test_a_truncated_download_fails_its_check_and_nothing_is_held(self):
        self.net.routes[self.url] = lambda req: Reply(self.zip[:-10], self.url)
        self.up.status()
        self.up.download({})
        self.assertEqual({"state": "failed", "version": "0.3.2", "message": up.FETCH_TOOBIG}, self.up.status()[1]["fetch"])
        self.assertIsNone(self.up.reviewed)
        self.assertIsNone(self.up.fetched)
        self.assertEqual((409, "review_again"), (self.up.install({"review_id": "x"})[0], self.up.install({"review_id": "x"})[1]["code"]))

    def test_a_wrong_digest_fails_its_check(self):
        self.doc["assets"][0]["digest"] = "sha256:" + "0" * 64
        self.net.routes[rf.API_URL] = json.dumps(self.doc).encode()
        self.up.status()
        self.up.download({})
        self.assertEqual("failed", self.up.status()[1]["fetch"]["state"])
        self.assertEqual(up.FETCH_MISMATCH, self.up.status()[1]["fetch"]["message"])

    def test_the_download_going_offline_says_so(self):
        self.net.routes[self.url] = OSError("down")
        self.up.status()
        self.up.download({})
        self.assertEqual({"state": "failed", "version": "0.3.2", "message": up.FETCH_OFFLINE}, self.up.status()[1]["fetch"])

    def test_after_a_failure_download_again_works(self):
        self.net.routes[self.url] = OSError("down")
        self.up.status()
        self.up.download({})
        self.net.routes[self.url] = lambda req: Reply(self.zip, self.url)
        self.assertEqual(200, self.up.download({})[0])
        self.assertEqual("ready", self.up.status()[1]["fetch"]["state"])

    def test_a_file_over_the_cap_fails_its_check(self):
        with mock.patch.object(updates, "MAX_ZIP_BYTES", 500):
            self.net.routes[rf.API_URL] = json.dumps({**self.doc, "assets": [{**self.doc["assets"][0], "size": 400}]}).encode()
            self.up.status()
            self.up.download({})
        self.assertEqual("failed", self.up.status()[1]["fetch"]["state"])
        self.assertIsNone(self.up.reviewed)

    def test_install_is_a_second_click_on_the_same_review_and_goes_through_the_existing_path(self):
        fetch = self.ready()
        status, done = self.up.install({"review_id": fetch["review_id"]})
        self.assertEqual((200, True), (status, done["restart"]))
        code, _ = self.run_helper()
        self.assertEqual(0, code)
        self.assertEqual("0.3.2", json.loads((self.app / "release.json").read_text(encoding="utf-8"))["version"] if (self.app / "release.json").exists() else "0.3.2")
        self.assertEqual("idle", self.up.status()[1]["fetch"]["state"])          # the review was used once

    def test_install_without_the_review_is_refused_and_changes_nothing(self):
        self.ready()
        before = self.tree()
        status, body = self.up.install({"review_id": "not the id"})
        self.assertEqual((409, "review_again"), (status, body["code"]))
        self.assertEqual(before, self.tree())

    def test_the_ready_update_that_runs_out_is_a_failed_download_with_download_again(self):
        self.ready()
        self.clock.now += up.REVIEW_SECONDS + 1
        self.assertEqual({"state": "failed", "version": "0.3.2", "message": up.FETCH_BAD}, self.up.status()[1]["fetch"])
        self.assertEqual("avail", self.up.status()[1]["latest"]["state"])
        self.assertEqual(200, self.up.download({})[0])              # and Download is offered again

    def test_not_now_puts_the_downloaded_update_away(self):
        fetch = self.ready()
        self.assertEqual(200, self.up.cancel({})[0])
        self.assertEqual("idle", self.up.status()[1]["fetch"]["state"])
        self.assertEqual("review_again", self.up.install({"review_id": fetch["review_id"]})[1]["code"])

    def test_cancel_during_the_download_stops_it_and_leaves_nothing(self):
        seen = []
        def spawn(work):
            seen.append(work)
        self.up = self.make(release_opener=self.net, spawn=spawn)
        self.up.status()
        seen.pop()()                                                   # the quiet look
        self.assertEqual(200, self.up.download({})[0])
        self.assertEqual({"state": "downloading", "version": "0.3.2", "pct": 0}, self.up.status()[1]["fetch"])
        self.assertEqual(409, self.up.download({})[0])                 # one download at a time
        self.assertEqual(409, self.up.check({})[0])
        self.assertEqual(200, self.up.cancel({})[0])
        seen.pop()()                                                   # the download notices at its next chunk
        self.assertEqual("idle", self.up.status()[1]["fetch"]["state"])
        self.assertEqual([], [p.name for p in (self.data / "fetched").iterdir()])
        self.assertIsNone(self.up.reviewed)

    def test_the_progress_is_a_percent_below_100_until_the_check_starts(self):
        pcts = []
        with mock.patch.object(updates, "CHUNK", max(1, len(self.zip) // 4)):
            real = self.up._progress
            self.up._progress = lambda k, v, d, t: (real(k, v, d, t), pcts.append(self.up.fetch.get("pct")))
            self.ready()
        self.assertTrue(pcts and all(0 <= p <= 99 for p in pcts), pcts)
        self.assertEqual(sorted(pcts), pcts)

    def test_a_late_progress_report_does_not_bring_back_a_finished_bar(self):
        self.up.status()
        self.up.download({})
        self.assertEqual("ready", self.up.fetch["state"])
        self.up._progress(self.up.run, "0.3.2", 5, 10)
        self.assertEqual("ready", self.up.fetch["state"])

    def test_an_address_not_allowed_is_the_check_sentence_not_offline_and_a_signature_is_asked_for_by_its_own_size(self):
        self.up.status()
        self.up.latest["url"] = "http://github.com/x.zip"
        self.up.download({})
        self.assertEqual(up.FETCH_BAD, self.up.status()[1]["fetch"]["message"])
        self.up.check({})
        caps = []
        real = rf.download
        with mock.patch.object(rf, "download", side_effect=lambda *a, **k: caps.append(k.get("max_bytes")) or real(*a, **k)):
            self.up.download({})
        self.assertEqual([None, updates.SIGNATURE_BYTES], caps)

    def test_a_failed_download_is_put_away_by_cancel(self):
        self.net.routes[self.url] = OSError("down")
        self.up.status()
        self.up.download({})
        self.assertEqual("failed", self.up.fetch["state"])
        self.up.cancel({})
        self.assertEqual("idle", self.up.fetch["state"])

    def test_download_needs_a_look_first_and_a_newer_release(self):
        self.assertEqual((409, "no_latest"), (self.up.download({})[0], self.up.download({})[1]["code"]))

    def test_nothing_downloads_while_an_install_runs(self):
        self.up.status()
        self.up._installing = True
        self.assertEqual("busy", self.up.download({})[1]["code"])
        self.assertEqual("busy", self.up.check({})[1]["code"])


class RoutesTest2(Served2):
    def test_the_three_routes_need_the_token_the_host_and_this_site_and_a_small_body(self):
        s = Served(self, self.up)
        for path in ("/api/update/check", "/api/update/download", "/api/update/cancel"):
            with self.subTest(path=path):
                self.assertIn(path, sv.UPDATE_ROUTES)
                self.assertEqual(1024, sv.ROUTE_BODY_LIMITS[path])
                self.assertEqual(403, s.call("POST", path, {}, token=False)[0])
                self.assertEqual(403, s.call("POST", path, {}, host="example.org")[0])
                self.assertEqual(403, s.call("POST", path, {}, origin="http://example.org")[0])
                self.assertEqual((400, "too_large"), (lambda r: (r[0], r[1]["code"]))(s.call("POST", path, raw=json.dumps({"x": "a" * 2000}).encode())))
                self.assertEqual(200, s.call("POST", path, {})[0])

    def test_the_routes_answer_while_installing_and_say_busy(self):
        s = Served(self, self.up)
        self.up._installing = True
        for path in ("/api/update/check", "/api/update/download", "/api/update/cancel"):
            with self.subTest(path=path):
                self.assertNotEqual(503, s.call("POST", path, {})[0])

    def test_every_update_route_the_server_serves_is_in_the_list_that_stays_up_while_installing(self):
        import re
        source = Path(sv.__file__).read_text(encoding="utf-8")
        named = set(re.findall(r'"(/api/update(?:/[a-z-]+)?)": update_route', source))
        self.assertEqual(set(sv.UPDATE_ROUTES), named | {"/api/update"})

    def test_the_status_over_the_wire_carries_the_look_and_the_download(self):
        s = Served(self, self.up)
        status, body = s.call("GET", "/api/update")
        self.assertEqual((200, "avail", "idle"), (status, body["latest"]["state"], body["fetch"]["state"]))
        self.assertEqual(200, s.call("POST", "/api/update/download", {})[0])
        self.assertEqual("ready", s.call("GET", "/api/update")[1]["fetch"]["state"])


if __name__ == "__main__":
    unittest.main()
