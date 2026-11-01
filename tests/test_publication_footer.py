"""#120: the footer of a published file, read in a real browser (a browser file, so outside the quick tier).

Run: python3 dev/run_tests.py test_publication_footer
"""
import tempfile
import unittest
from pathlib import Path

import _publish_fixture as fx
from _demo import USER
from _paths import SRC  # noqa: F401
from clark import publish
from clark.store import open_store
from test_publish import opened, wait
from test_publish_route import EMPTY_BRANDING
from test_server import chrome


class TheFooter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.db = fx.build_db(Path(cls.tmp.name) / "clark.db")
        cls.store = open_store(cls.db, onedrive_roots=[])
        cls.addClassCleanup(cls.store.close)

    def footer(self, path):
        with chrome() as cdp:
            sid = opened(cdp, Path(path).as_uri(), 1400)
            self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"))
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#publication-footer').length", sid) == 1))
            return cdp.js("document.querySelector('#publication-footer').textContent", sid)

    def test_a_published_file_reads_publication_n_and_the_date(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        done = publish.publish(self.store, "PUB", folder.name, by_user=USER, now="2026-10-28", branding=EMPTY_BRANDING)
        self.assertEqual(self.footer(done["path"]), f"Publication {done['number']} · 28-10-2026")

    def test_a_file_with_no_date_reads_publication_n_alone(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        done = publish.publish(self.store, "PUB", folder.name, by_user=USER, now="2026-10-28", branding=EMPTY_BRANDING)
        path = Path(done["path"])
        path.write_text(path.read_text(encoding="utf-8").replace('"as_at":"2026-10-28"', '"as_at":""'), encoding="utf-8")
        self.assertEqual(self.footer(path), f"Publication {done['number']}")

    def test_a_preview_has_no_footer(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        built = publish.build(self.store, "PUB", "2026-10-28", EMPTY_BRANDING, number=0)
        path = Path(folder.name) / "preview.html"
        path.write_bytes(built["body"])
        with chrome() as cdp:
            sid = opened(cdp, path.as_uri(), 1400)
            self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"))
            self.assertEqual(cdp.js("document.querySelectorAll('#publication-footer').length", sid), 0)


if __name__ == "__main__":
    unittest.main()
