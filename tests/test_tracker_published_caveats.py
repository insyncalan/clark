"""#275: pins for the published progress tracker's caveats (source and behaviour checks; no browser).

Decisions recorded here:
- A tracker with an overall figure but no lines is left out of the published page. Kept as it is: figures with nothing under
  them say little, and the page works totals out from lines. This test pins it.
- Published tracker strings are raw text. Any renderer for them must use textContent, never innerHTML.
- There is no per-line client_visible flag: everything in a visible tracker is published, by design.

Run: python3 dev/run_tests.py test_tracker_published_caveats
"""
import re
import unittest

from _paths import ROOT, SRC
from clark import section_bodies as sb

PAGE_SRC = ROOT / "src" / "clark" / "page" / "src"
RAW_HTML = re.compile(r"innerHTML|dangerouslySetInnerHTML|insertAdjacentHTML|outerHTML")


def line(**more):
    got = {"no": "1", "text": "Set up", "start": "2030-01-01", "end": "2030-02-01", "status": "inprogress",
           "weight": 400, "planned": 1000, "achieved": 800}
    got.update(more)
    return got


class TrackerPublishedCaveatsTest(unittest.TestCase):
    def test_overall_only_tracker_is_left_out(self):
        overall = {"actual": 625, "planned": 700, "health": "atrisk", "note": "Late."}
        self.assertIsNone(sb.published("tracker", {"v": 1, "overall": overall, "columns": {}, "groups": []}))
        self.assertIsNone(sb.published("tracker", {"v": 1, "overall": overall, "columns": {}, "groups": [{"name": "Build", "lines": []}]}))

    def test_tracker_with_a_line_is_published_as_raw_text(self):
        got = sb.published("tracker", {"v": 1, "overall": {}, "columns": {}, "groups": [{"name": "<b>Build</b>", "lines": [line(text="<i>x</i>")]}]})
        self.assertEqual(got["groups"][0]["name"], "<b>Build</b>")
        self.assertEqual(got["groups"][0]["lines"][0]["text"], "<i>x</i>")

    def test_no_tracker_renderer_uses_raw_html(self):
        files = [p for p in PAGE_SRC.rglob("*") if p.is_file() and p.suffix in (".js", ".jsx")
                 and ("tracker" in p.name.lower() or "tracker" in p.read_text(encoding="utf-8", errors="ignore").lower())]
        for p in files:
            text = p.read_text(encoding="utf-8")
            if "tracker" in p.name.lower():
                self.assertIsNone(RAW_HTML.search(text), f"{p.name}: a tracker renderer must use textContent")
                continue
            for n, row in enumerate(text.splitlines(), 1):
                if "tracker" in row.lower():
                    self.assertIsNone(RAW_HTML.search(row), f"{p.name}:{n}: tracker text must not go through raw HTML")

    def test_publisher_source_never_writes_tracker_html(self):
        text = (SRC / "clark" / "publish.py").read_text(encoding="utf-8")
        self.assertIsNone(RAW_HTML.search(text))


if __name__ == "__main__":
    unittest.main()
