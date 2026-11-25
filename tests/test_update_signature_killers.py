"""Row 1328: the paths of the signed download that a hand mutation sweep found untested (updates.check_signature, updater._run_download).

Each test names the one line it holds in place. No network: the releases page is the fake opener of test_release_fetch_1327, and the
only keys are the throw-away test keys of _signing.py.
Run: python3 dev/run_tests.py test_update_signature_killers
"""
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

from clark import release_fetch as rf, updater as up, updates
import _signing as sg
import test_release_fetch_1327 as rfx


class Killers(rfx.Served2):
    WORDS = "The download failed its check. It was not installed."

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(updates, "FIRST_SIGNED", (1, 3, 4))
        patcher.start()
        self.addCleanup(patcher.stop)

    def release(self, version="1.3.4", sig_asset=True):
        self.set_release(version)
        if not sig_asset:
            self.doc["assets"] = self.doc["assets"][:1]
            self.net.routes[rf.API_URL] = json.dumps(self.doc).encode()
        self.up.status()

    def urls(self):
        return [c[0].full_url for c in self.net.calls]

    def reviews(self):
        """Wrap _review_file: the list of (version-file exists, signature file bytes) seen at each review."""
        seen = []
        real = self.up._review_file
        def wrapped(dest, *a, **k):
            sig = Path(str(dest) + updates.SIGNATURE_SUFFIX)
            seen.append((Path(dest).exists(), sig.read_bytes() if sig.exists() else None))
            return real(dest, *a, **k)
        self.up._review_file = wrapped
        return seen

    def late_flag(self, url):
        """Make the body served at `url` set the cancel flag as it ends (after its last chunk, before any further check)."""
        body = self.net.routes[url](None).getvalue()
        flag = self.up
        class Ends(rfx.Reply):
            def read(inner, n=-1):
                got = super().read(n)
                if not got:
                    flag.cancel_flag.set()
                return got
        self.net.routes[url] = lambda req: Ends(body, url)


class VerifyLibraryTest(unittest.TestCase):
    def test_a_missing_verify_library_is_refused_with_nokey_not_accepted(self):      # updates.check_signature, the ImportError branch
        data = b"bytes"
        with mock.patch.dict(sys.modules, {"ed25519_verify": None}):
            with self.assertRaises(updates.UpdateError) as caught:
                updates.check_signature(data, sg.signature_for(data), public_key=sg.TEST_PUBLIC)
        self.assertEqual("nokey", caught.exception.key)
        updates.check_signature(data, sg.signature_for(data), public_key=sg.TEST_PUBLIC)       # and with the library it is accepted


class SignatureFetchTest(Killers):
    def test_the_signature_is_fetched_and_lies_beside_the_download_when_it_is_reviewed(self):    # updater: the .sig fetch is not skipped
        self.release()
        seen = self.reviews()
        self.up.download({})
        self.assertIn(self.sig_url, self.urls())
        self.assertEqual([(True, self.sig)], seen)
        self.assertEqual("ready", self.up.status()[1]["fetch"]["state"])

    def test_the_version_decides_whether_the_signature_is_asked_for_even_with_the_placeholder_key(self):    # signature_required(version=version)
        self.release()
        seen = self.reviews()
        with mock.patch.object(updates, "RELEASE_PUBLIC_KEY", updates.PLACEHOLDER_KEY):
            self.up.download({})
        self.assertIn(self.sig_url, self.urls())
        self.assertEqual([(True, self.sig)], seen)

    def test_a_signature_fetch_that_fails_for_another_reason_stops_the_download_before_any_review(self):    # the non-cancel error is raised, not swallowed
        self.release()
        self.net.routes[self.sig_url] = rf.FetchError("nofile", "gone")
        seen = self.reviews()
        self.up.download({})
        fetch = self.up.status()[1]["fetch"]
        self.assertEqual(("failed", self.WORDS), (fetch["state"], fetch["message"]))
        self.assertEqual([], seen)

    def test_a_signature_file_over_its_cap_stops_the_download_before_any_review(self):     # max_bytes=SIGNATURE_BYTES on the .sig fetch
        self.release()
        big = b"s" * (updates.SIGNATURE_BYTES * 4)
        self.net.routes[self.sig_url] = lambda req: rfx.Reply(big, self.sig_url)
        seen = self.reviews()
        self.up.download({})
        fetch = self.up.status()[1]["fetch"]
        self.assertEqual(("failed", self.WORDS), (fetch["state"], fetch["message"]))
        self.assertEqual([], seen)

    def test_a_cancel_during_the_signature_fetch_ends_idle_and_is_not_a_failed_check(self):     # the cancel is re-raised from the .sig fetch
        self.release()
        sig = self.sig
        def serve(req):
            self.up.cancel({})
            return rfx.Reply(sig, self.sig_url)
        self.net.routes[self.sig_url] = serve
        seen = self.reviews()
        with self.assertLogs("clark.updater", "INFO") as logged:
            self.up.download({})
        self.assertEqual("idle", self.up.status()[1]["fetch"]["state"])
        self.assertEqual([], seen)
        self.assertIsNone(self.up.fetched)
        self.assertEqual(["INFO:clark.updater:a download was stopped: cancelled"], logged.output)     # a cancel, not a failed signature

    def test_a_cancel_after_the_last_signature_chunk_is_honoured_before_the_review(self):     # the flag check after the .sig fetch
        self.release()
        self.up.status()
        self.late_flag(self.sig_url)
        seen = self.reviews()
        self.up.download({})
        self.assertEqual("idle", self.up.fetch["state"])
        self.assertEqual([], seen)

    def test_a_cancel_after_the_last_download_chunk_is_honoured_before_the_review(self):      # same check, an older version with no signature
        self.release("1.3.3", sig_asset=False)
        self.late_flag(self.url)
        seen = self.reviews()
        self.up.download({})
        self.assertEqual("idle", self.up.fetch["state"])
        self.assertEqual([], seen)


class CancelDuringReviewTest(Killers):
    def cancel_in_review(self):
        self.release()
        real = self.up._review_file
        def review(*a, **k):
            got = real(*a, **k)
            self.up.cancel_flag.set()
            return got
        self.up._review_file = review
        self.up.download({})

    def test_a_cancel_while_the_review_runs_ends_idle_not_ready(self):       # the flag check after the review
        self.cancel_in_review()
        self.assertEqual("idle", self.up.status()[1]["fetch"]["state"])

    def test_a_cancelled_run_leaves_no_ready_slot_behind(self):             # _drop_fetched on the cancelled run
        self.cancel_in_review()
        self.assertIsNone(self.up.fetched)
        self.assertIsNone(self.up.reviewed)
        self.assertEqual([], [p.name for p in (self.data / "fetched").iterdir()])


class MessageTest(Killers):
    def test_unsigned_and_badsig_reviews_both_say_the_check_words_not_the_general_ones(self):      # the unsigned/badsig mapping
        self.assertNotEqual(self.WORDS, up.FETCH_BAD)
        for name, kw in (("badsig", {}),):      # row 1328 ruling: a release with no .sig installs; only a bad .sig is the check words
            with self.subTest(name):
                self.release(**kw)
                if name == "badsig":
                    self.net.routes[self.sig_url] = lambda req: rfx.Reply(b"x" * updates.SIGNATURE_BYTES, self.sig_url)
                self.up.download({})
                fetch = self.up.status()[1]["fetch"]
                self.assertEqual(("failed", self.WORDS), (fetch["state"], fetch["message"]))


if __name__ == "__main__":
    unittest.main()
