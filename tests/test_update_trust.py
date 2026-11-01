"""Where an update's trust comes from (insyncalan/clark-plan#282, point 1): src/clark/updates.py.

An update file is checked against the list of checksums INSIDE it (clark-release.json). That proves the file is whole, not that
it is clark's: whoever builds a download can write a list that matches whatever they put in it. This test builds such a
download, a store.py that differs from the published one and a list rewritten to match, and says what should happen: it is
refused, because nothing ties it to the people who make clark. The refusal must be the one named "signature", not any
error: an unrelated check that starts rejecting this file must not make the expected failure look cured.
It fails today, so it is marked as an expected failure. When the update checks a signature or a pinned source, add the
"signature" sentence to MESSAGES, remove the marker from the refusal test, and delete or turn round the first test too
(it will then fail, because the file is no longer read). If #282 point 1 is instead closed by writing the gap into the
release notes, change both tests to say so.
Builds fake downloads in temporary folders; reads only, no network.
Run: python3 dev/run_tests.py test_update_trust
"""
import shutil
import tempfile
import unittest

from clark import updates
from test_updates import SYSTEM, listed_files, make_zip


class ProvenanceTest(unittest.TestCase):
    def setUp(self):
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

    @unittest.expectedFailure       # no signature or pinned source is checked yet (insyncalan/clark-plan#282 point 1)
    def test_a_changed_file_with_a_matching_list_is_refused(self):
        files = listed_files()
        files["src/clark/store.py"] = b"# a different file from the one clark published\n"
        with self.assertRaises(updates.UpdateError) as caught:
            updates.read_release(make_zip(self.tmp, files=files), SYSTEM, "0.3.0", 2)
        self.assertEqual("signature", caught.exception.key)


if __name__ == "__main__":
    unittest.main()
