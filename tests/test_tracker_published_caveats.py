"""#275: pins for the published progress tracker's caveats (a real publish, source and behaviour checks; no browser).

Decisions recorded here:
- A tracker with an overall figure but no lines is left out of the published page. Kept as it is: figures with nothing under
  them say little, and the page works totals out from lines. This test pins it.
- Published tracker strings are raw text. Any renderer for them must use textContent, never innerHTML.
- There is no per-line client_visible flag: everything in a visible tracker is published, by design. The test below publishes
  a real tracker and checks every line is in the file.
- Still open on #275: the owner note in Help (there is no tracker screen to attach it to yet) and the guard in published() so a
  kind that is not needs goes to the tracker path only when it is a tracker (open PR 160).

Run: python3 dev/run_tests.py test_tracker_published_caveats
"""
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from _paths import ROOT, SRC
from clark import changes, publish, section_bodies as sb

PAGE_SRC = ROOT / "src" / "clark" / "page" / "src"
RAW_HTML = re.compile(r"innerHTML|dangerouslySetInnerHTML|insertAdjacentHTML|outerHTML")
NO_BRAND = tempfile.mkdtemp(prefix="clark-no-brand-")        # so a brand on this laptop never changes a test


def line(**more):
    got = {"no": "1", "text": "Set up", "start": "2030-01-01", "end": "2030-02-01", "status": "inprogress",
           "weight": 400, "planned": 1000, "achieved": 800}
    got.update(more)
    return got


def tracker_renderers_with_raw_html(root):
    """Where tracker text could go through raw HTML under `root`: a file named for the tracker may not use it at all; in any
    other .js or .jsx file, no line that names the tracker may. Returns (files that name the tracker, [where it is used])."""
    seen, bad = [], []
    for p in sorted(root.rglob("*")):
        if not (p.is_file() and p.suffix in (".js", ".jsx")):
            continue
        text = p.read_text(encoding="utf-8", errors="ignore")
        if "tracker" in p.name.lower():
            seen.append(p.name)
            if RAW_HTML.search(text):
                bad.append(p.name)
        elif "tracker" in text.lower():
            seen.append(p.name)
            bad += [f"{p.name}:{n}" for n, row in enumerate(text.splitlines(), 1) if "tracker" in row.lower() and RAW_HTML.search(row)]
    return seen, bad


class TrackerPublishedCaveatsTest(unittest.TestCase):
    def test_overall_only_tracker_is_left_out(self):
        overall = {"actual": 625, "planned": 700, "health": "atrisk", "note": "Late."}
        self.assertIsNone(sb.published("tracker", {"v": 1, "overall": overall, "columns": {}, "groups": []}))
        self.assertIsNone(sb.published("tracker", {"v": 1, "overall": overall, "columns": {}, "groups": [{"name": "Build", "lines": []}]}))

    def test_tracker_with_a_line_is_published_as_raw_text(self):
        got = sb.published("tracker", {"v": 1, "overall": {}, "columns": {}, "groups": [{"name": "<b>Build</b>", "lines": [line(text="<i>x</i>")]}]})
        self.assertEqual(got["groups"][0]["name"], "<b>Build</b>")
        self.assertEqual(got["groups"][0]["lines"][0]["text"], "<i>x</i>")

    def test_every_field_of_a_line_is_published(self):
        got = sb.published("tracker", {"v": 1, "overall": {}, "columns": {}, "groups": [{"name": "Build", "lines": [line()]}]})
        self.assertEqual(got["groups"][0]["lines"][0], {"no": "1", "text": "Set up", "start": "01-01-2030", "end": "01-02-2030",
                                                       "status": "inprogress", "weight": 400, "planned": 1000, "achieved": 800,
                                                       "tasks": None, "agents": None, "workflows": None})

    def test_the_scan_finds_raw_html_in_a_tracker_renderer(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.assertEqual(tracker_renderers_with_raw_html(root), ([], []))
            (root / "Other.jsx").write_text("el.innerHTML = a\n", encoding="utf-8")
            self.assertEqual(tracker_renderers_with_raw_html(root), ([], []), "a file that never names the tracker is not a renderer")
            (root / "Other.jsx").write_text("const tracker = 1\nel.innerHTML = a\nrow(tracker); el.outerHTML = b\n", encoding="utf-8")
            self.assertEqual(tracker_renderers_with_raw_html(root), (["Other.jsx"], ["Other.jsx:3"]))
            (root / "Tracker.jsx").write_text("node.textContent = a\n", encoding="utf-8")
            self.assertEqual(tracker_renderers_with_raw_html(root)[1], ["Other.jsx:3"])
            (root / "Tracker.jsx").write_text("node.insertAdjacentHTML('x', a)\n", encoding="utf-8")
            self.assertEqual(tracker_renderers_with_raw_html(root)[1], ["Other.jsx:3", "Tracker.jsx"])

    def test_no_tracker_renderer_uses_raw_html(self):
        seen, bad = tracker_renderers_with_raw_html(PAGE_SRC)
        if not seen:
            self.skipTest("the page has no tracker renderer yet (open PR 160); this runs once one lands")
        self.assertEqual(bad, [], "a tracker renderer must use textContent")

    def test_the_sources_that_make_the_published_tracker_never_write_html(self):
        for name in ("publish.py", "section_bodies.py"):
            text = (SRC / "clark" / name).read_text(encoding="utf-8")
            self.assertIsNone(RAW_HTML.search(text), name)


class RealPublishTest(unittest.TestCase):
    """A real tracker in a real store, published by publish.publish, and the file it wrote read back."""

    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.change = changes.make_change(self.demo.store.path, [], USER)

    def tracker(self, title, body, hidden=0):
        status, got = self.change({"project": "ABC", "kind": "report_sections", "op": "new", "values": {"type": "tracker", "title": title}})
        self.assertEqual(status, 200, got)
        ref = got["ref"]
        status, got = self.change({"project": "ABC", "kind": "report_sections", "op": "update", "id": ref, "changes": {"body": json.dumps(body)}})
        self.assertEqual(status, 200, got)
        if hidden:
            status, got = self.change({"project": "ABC", "kind": "report_sections", "op": "update", "id": ref, "changes": {"hidden": 1}})
            self.assertEqual(status, 200, got)
        return ref

    def published_file(self):
        done = publish.publish(self.demo.store, "ABC", self.folder, by_user=USER, now="2030-01-15", branding=NO_BRAND)
        text = Path(done["path"]).read_text(encoding="utf-8")
        block = re.search(r'id="clark-data">(.*?)</script>', text, re.S).group(1)
        return text, json.loads(block)

    def test_the_file_carries_the_caveats(self):
        markup = "<b>Build</b> & <i>more</i>"
        overall = {"actual": 625, "planned": 700, "health": "atrisk", "note": "Late."}
        full = self.tracker("Progress", {"v": 1, "overall": overall, "columns": {"tasks": True}, "groups": [
            {"name": markup, "lines": [line(text="<i>x</i>", tasks=5), line(no="2", text="Second", status="planned")]},
            {"name": "Empty group", "lines": []}]})
        only_overall = self.tracker("Only figures", {"v": 1, "overall": overall, "columns": {}, "groups": []})
        hidden = self.tracker("Hidden", {"v": 1, "overall": {}, "columns": {}, "groups": [{"name": "Gone", "lines": [line(text="Hidden line")]}]}, hidden=1)
        text, data = self.published_file()
        by_id = {s["id"]: s for s in data["sections"]}
        self.assertIn(full, by_id)
        self.assertNotIn(only_overall, by_id, "figures with no line are left out")
        self.assertNotIn(hidden, by_id)
        shown = by_id[full]
        self.assertEqual([g["name"] for g in shown["groups"]], [markup], "a group with no line is left out")
        self.assertEqual([l["text"] for l in shown["groups"][0]["lines"]], ["<i>x</i>", "Second"], "every line is published, raw")
        self.assertEqual(shown["groups"][0]["lines"][0]["tasks"], 5)
        self.assertEqual(shown["overall"], {"actual": 625, "planned": 700, "health": "atrisk", "note": "Late."})
        self.assertNotIn("Hidden line", text)
        self.assertNotIn("<b>Build</b>", text, "the text is in the file only as an escaped value in the data block")
        self.assertNotIn("<i>x</i>", text)
        self.assertIn("\\u003cb\\u003eBuild\\u003c/b\\u003e", text)
        self.assertIsNone(RAW_HTML.search(text.split('id="clark-data">', 1)[1]))


if __name__ == "__main__":
    unittest.main()
