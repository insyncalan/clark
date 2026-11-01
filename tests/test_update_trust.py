"""Where an update's trust comes from (#282, point 1): src/clark/updates.py.

An update file is checked against the list of checksums INSIDE it (clark-release.json). That proves the file is whole, not that
it is clark's: whoever builds a download can write a list that matches whatever they put in it. This test builds such a
download, a changed store.py and a list rewritten to match, and says what should happen: it is refused, because nothing
ties it to the people who make clark. It fails today, so it is marked as an expected failure; when the update checks a
signature or a pinned source, remove the marker.
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

    @unittest.expectedFailure       # no signature or pinned source is checked yet (#282 point 1)
    def test_a_changed_file_with_a_matching_list_is_refused(self):
        files = listed_files()
        files["src/clark/store.py"] = b"# a different file from the one clark published\n"
        with self.assertRaises(updates.UpdateError):
            updates.read_release(make_zip(self.tmp, files=files), SYSTEM, "0.3.0", 2)


if __name__ == "__main__":
    unittest.main()
