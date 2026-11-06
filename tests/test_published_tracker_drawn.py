"""Row 933: a progress tracker with lines is drawn in the published file (it was left out before): the overall tile with its figures and the groups with their lines, at 1400 and 900 px, light and dark.

Run: python3 dev/run_tests.py test_published_tracker_drawn
Headless Chrome (required)."""
import json, shutil, tempfile, unittest
from pathlib import Path
from test_publish_section_bodies import Published
from test_published_work_no_add import open_page, VARIANTS
from test_server import chrome, wait
BODY = {"v": 1, "overall": {"actual": 625, "planned": 700, "health": "atrisk", "note": "A week behind plan."}, "columns": {}, "groups": [
  {"name": "Build", "lines": [{"no": "1", "text": "Set up the environment", "start": "2030-01-01", "end": "2030-02-01", "status": "completed", "weight": 300, "planned": 300, "achieved": 300},
                               {"no": "2", "text": "Matching rules", "start": "2030-02-01", "end": "2030-03-15", "status": "inprogress", "weight": 400, "planned": 300, "achieved": 150}]},
  {"name": "Roll-out", "lines": [{"no": "3", "text": "Training", "start": "2030-03-15", "end": "2030-04-30", "status": "planned", "weight": 300, "planned": 0, "achieved": 0}]}]}
class Drawn(Published):
    def test_the_published_file_draws_the_tracker_tile_and_its_lines(self):
        ref = self.section("tracker", title="Progress")
        self.write(ref, json.dumps(BODY))
        d = Path(tempfile.mkdtemp(prefix="clark-933-"))
        self.addCleanup(shutil.rmtree, str(d), True)
        f = d / "r.html"
        f.write_bytes(self.build()["body"])
        for width, scheme in VARIANTS:
            with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                sid = open_page(cdp, f.as_uri(), width, scheme)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-tr-tile]')", sid)), "the tracker tile is drawn in the file")
                self.assertTrue(wait(lambda: cdp.js("document.getAnimations().length === 0", sid)), "motion finished")
                text = cdp.js("document.body.innerText", sid)
                for word in ("Progress", "Build", "Roll-out", "Set up the environment", "Matching rules", "Training", "A week behind plan."):
                    self.assertIn(word, text, f"{word} is in the published tracker")
                self.assertLessEqual(cdp.js("document.documentElement.scrollWidth", sid), width, "the page does not scroll sideways")


if __name__ == "__main__":
    unittest.main()
