"""Row 1543, AP13 (part 3 of the search): the published report stays one self-contained file. Searching it, with the index inside
the file, asks the network for nothing. The size is REPORTED in bytes (no pass limit, Romanoff PM ruling 23-11). Fictional data.

Run: python3 dev/run_tests.py test_published_self_contained_1543        (needs Chrome; run only while the machine's load is under 70)
The size line is printed as `1543 AP13 size: <bytes> bytes (project PUB)`; the "before" figure is the same run on origin/main.
"""
import re
import sys
import tempfile
import time
import unittest
from pathlib import Path

from _paths import ROOT, SRC  # noqa: F401
import _publish_fixture as fx

from clark import publish
from clark.store import open_store
from test_publish import EMPTY_BRANDING, opened
from test_server import chrome, wait

SEARCH_BUTTON = "document.querySelector('header.top-file [aria-label=\"Go to or do\"]')"
# Ways a page can reach out, searched for in the file's own text.
EXTERNAL_ATTR = re.compile(r"""<(?:script|img|iframe|embed|source|video|audio|link)\b[^>]*\b(?:src|href|srcset|data)\s*=\s*["']?(?!data:|#)[^"'\s>]+""", re.I)
EXTERNAL_CSS = re.compile(r"@import|url\(\s*(?![\"']?(?:data:|#))", re.I)


class SelfContained1543(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        db = fx.build_db(Path(cls.tmp.name) / "clark.db")
        cls.store = open_store(db, onedrive_roots=[])
        cls.addClassCleanup(cls.store.close)
        cls.done = publish.publish(cls.store, "PUB", cls.tmp.name, by_user="Demo User", now="2026-10-28", branding=EMPTY_BRANDING)
        cls.path = Path(cls.done["path"])
        cls.text = cls.path.read_text(encoding="utf-8")

    def drive(self, width, dark):
        """Open the file from disk, visit every tab, and if the file has the search button use it (open, type, arrows, Enter, Esc)."""
        with chrome() as cdp:
            sid = opened(cdp, self.path.as_uri(), width)
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('h1') && document.documentElement.dataset.ready", sid) == "1"), "the file drew")
            if dark:
                cdp.js("document.documentElement.dataset.theme = 'dark'", sid)
            for view in ("work", "milestones", "usecases", "dashboard"):
                cdp.js(f"(document.querySelector('[data-view={view}]') || {{click() {{}}}}).click()", sid)
            has_search = bool(cdp.js(f"!!{SEARCH_BUTTON}", sid))
            if has_search:
                cdp.js(f"{SEARCH_BUTTON}.click()", sid)
                for key in ("a", "ArrowDown", "ArrowUp", "Enter", "Escape"):
                    cdp.js("document.activeElement.dispatchEvent(new KeyboardEvent('keydown', {key: %r, bubbles: true}))" % key, sid)
            time.sleep(1)
            cdp.js("1", sid)
            violations = cdp.js("window.violations", sid)
        asked = [e["params"]["request"]["url"] for e in cdp.events if e.get("method") == "Network.requestWillBeSent"]
        return asked, violations, has_search

    def test_published_file_stays_self_contained(self):
        size = len(self.text.encode("utf-8"))
        self.assertEqual(size, self.path.stat().st_size, "the size counted is the file's size on disk")
        print(f"1543 AP13 size: {size} bytes (project PUB)", file=sys.stderr)
        self.assertGreater(size, 0)

        # 1. the file's own text: nothing it loads comes from outside, and the policy forbids the network
        csp = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]*)"', self.text).group(1)
        for want in ("default-src 'none'", "connect-src 'none'", "img-src data:", "font-src data:", "object-src 'none'", "form-action 'none'"):
            self.assertIn(want, csp, f"the file's policy holds {want}")
        self.assertNotRegex(csp, r"https?:|\*", "the policy names no outside address")
        self.assertEqual(EXTERNAL_ATTR.findall(self.text), [], "no tag points at a file or address outside the report")
        self.assertEqual(EXTERNAL_CSS.findall("".join(re.findall(r"<style\b[^>]*>(.*?)</style>", self.text, re.S))), [], "no stylesheet import or url() outside the file")
        self.assertEqual(len(re.findall(r"<script\b[^>]*\bsrc=", self.text)), 0, "no script is loaded from outside")

        # 2. in a real browser, 1400 and 900, light and dark: with every tab visited (and the search used when the file has it),
        # the only request is the document itself, and the policy blocked nothing the page needed
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark):
                    asked, violations, _ = self.drive(width, dark)
                    self.assertEqual([u for u in asked if not u.startswith("data:")], [self.path.as_uri()], f"only the document: {asked}")
                    self.assertEqual(violations, [], "the policy blocked nothing")

    def test_the_size_is_measured_not_limited(self):
        """The size reported grows with the report: a bigger report gives a bigger file, and nothing caps it (no pass limit)."""
        first = self.path.stat().st_size
        with self.store.step("dashboard", "Demo User") as st:
            st.create("milestones", {"project": "PUB", "name": "ZQ extra milestone " + "x" * 5000, "forecast_date": "2026-12-01", "baseline_date": "2026-12-01", "source": "demo"})
        out = tempfile.mkdtemp(dir=self.tmp.name)
        again = Path(publish.publish(self.store, "PUB", out, by_user="Demo User", now="2026-10-28", branding=EMPTY_BRANDING)["path"])
        self.assertGreater(again.stat().st_size, first, "the report with more in it is a bigger file; the size is reported, not capped")


if __name__ == "__main__":
    unittest.main()
