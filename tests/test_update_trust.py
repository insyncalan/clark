"""Where an update's trust comes from (ticket #282, point 1): src/clark/updates.py.

An update file is checked against the list of checksums INSIDE it (clark-release.json). That proves the file is whole, not that
it is clark's: whoever builds a download can write a list that matches whatever they put in it. This test builds such a
download, a store.py that differs from the published one and a list rewritten to match, and says what should happen: it is
refused, because nothing ties it to the people who make clark. The refusal must be the one for the signature ("badsig" when another key signed it, "unsigned" when nothing did), not any
error: an unrelated check that starts rejecting this file must not make the failure look cured. The control test beside them
shows the same forged file IS read when the release key signed it, so the refusals come from the signature alone.
Builds fake downloads in temporary folders; reads only, no network.
Run: python3 dev/run_tests.py test_update_trust
"""
import shutil
import tempfile
import unittest

import _signing
from clark import updates
from test_updates import SYSTEM, listed_files, make_zip


class ProvenanceTest(unittest.TestCase):
    def setUp(self):
        _signing.trust_test_key(self)
        self.tmp = tempfile.mkdtemp(prefix="clark trust ")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_a_changed_file_with_a_matching_list_is_still_read_today(self):
        """The part that holds: the list inside the file is trusted as it stands (this passes now, and shows the gap)."""
        files = listed_files()
        files["src/clark/store.py"] = b"# a different file from the one clark published\n"
        release = updates.read_release(make_zip(self.tmp, files=files), SYSTEM, "0.3.0", 2)
        self.assertEqual("0.3.1", release.version)

    def test_a_member_changed_after_the_list_was_written_is_refused_as_damaged(self):
        """The control: the hash check does refuse a file that does not match its list, so a refusal below can't come from there."""
        def change(files):
            files["README.md"] = files["README.md"].upper()
        with self.assertRaises(updates.UpdateError) as caught:
            updates.read_release(make_zip(self.tmp, tweak=change), SYSTEM, "0.3.0", 2)
        self.assertEqual("damaged", caught.exception.key)

    def test_a_changed_file_with_a_matching_list_signed_by_another_key_is_refused(self):
        """The forged download is signed, but not by the release key: refused as a bad signature (the old marked test signed
        it with the trusted key, so it was a genuine release and failed as expected for the wrong reason)."""
        files = listed_files()
        files["src/clark/store.py"] = b"# a different file from the one clark published\n"
        path = make_zip(self.tmp, files=files, sign=False)
        _signing.sign_file(path, _signing.OTHER_SEED)
        with self.assertRaises(updates.UpdateError) as caught:
            updates.read_release(path, SYSTEM, "0.3.0", 2)
        self.assertEqual("badsig", caught.exception.key)

    def test_a_changed_file_with_a_matching_list_and_no_signature_is_refused(self):
        files = listed_files()
        files["src/clark/store.py"] = b"# a different file from the one clark published\n"
        with self.assertRaises(updates.UpdateError) as caught:
            updates.read_release(make_zip(self.tmp, files=files, sign=False), SYSTEM, "0.3.0", 2)
        self.assertEqual("unsigned", caught.exception.key)

if __name__ == "__main__":
    unittest.main()
