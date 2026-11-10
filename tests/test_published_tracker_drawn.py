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
                overlap = cdp.js("""(() => { const bad = []; for (const t of document.querySelectorAll('table.tracker')) { const heads = [...t.querySelectorAll('thead th')].map(h => h.textContent.trim().toLowerCase()); const pi = heads.indexOf('planned'), ai = heads.indexOf('achieved'); if (pi < 0 || ai < 0) continue;
                  for (const tr of t.querySelectorAll('tbody tr')) { const cells = tr.cells; if (cells.length <= Math.max(pi, ai)) continue; const pc = cells[pi], ac = cells[ai]; const pr = pc.getBoundingClientRect(), ar = ac.getBoundingClientRect();
                    const parts = [...ac.querySelectorAll('.tr-pbar, b, .tr-behind')].map((e) => e.getBoundingClientRect()).filter((r) => r.width > 0);
                    if (!parts.length) continue;
                    const content = { left: Math.min(...parts.map((r) => r.left)), right: Math.max(...parts.map((r) => r.right)), top: Math.min(...parts.map((r) => r.top)), bottom: Math.max(...parts.map((r) => r.bottom)) }, planned = { width: 1 };
                    if (content.left < ar.left - 1 || content.right > ar.right + 1 || content.left < pr.right - 1 && planned.width > 0 && content.top < pr.bottom && content.bottom > pr.top) bad.push([tr.textContent.slice(0, 30), Math.round(content.left), Math.round(content.right), Math.round(ar.left), Math.round(ar.right), Math.round(pr.right), innerWidth, document.documentElement.dataset.theme || '']); } }
                  return bad; })()""", sid)
                self.assertEqual(overlap, [], "the Achieved cell's bar and chip stay inside the Achieved cell and clear of the Planned figure")
                self.assertEqual(cdp.js("[...document.querySelectorAll('table.tracker thead th')].filter(h => h.scrollWidth > h.clientWidth + 1).length", sid), 0, "no table heading is cut or run into the next")
                self.assertEqual(cdp.js("[...document.querySelectorAll('table.tracker tbody td.t-date')].filter(c => c.getClientRects()[0] && Math.round(c.getBoundingClientRect().height) > 60).length", sid), 0, "a date stays on one line")

    def test_the_tracker_health_tile_and_progress_bars_keep_their_fill_when_the_page_is_printed_to_pdf(self):
        # #1012: the PDF is the browser's print of this page. A bar with no painted fill prints as an empty slot, so under print media the
        # overall tile, the line progress bars and their fill must each be painted and ask the printer to keep it (print-color-adjust: exact).
        ref = self.section("tracker", title="Progress")
        self.write(ref, json.dumps(BODY))
        d = Path(tempfile.mkdtemp(prefix="clark-1012-"))
        self.addCleanup(shutil.rmtree, str(d), True)
        f = d / "r.html"
        f.write_bytes(self.build()["body"])
        probe = """JSON.stringify(['.tr-tile', '.tr-pbar', '.tr-pbar i'].map((sel) => { const e = document.querySelector('[data-tr-tile] ' + sel) || document.querySelector(sel); if (!e) return [sel, null];
          const c = getComputedStyle(e), r = e.getBoundingClientRect(); return [sel, c.backgroundColor, c.backgroundImage, c.printColorAdjust || c.webkitPrintColorAdjust, Math.round(r.width), Math.round(r.height)]; }))"""
        for width, scheme in VARIANTS:
            with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                sid = open_page(cdp, f.as_uri(), width, scheme)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-tr-tile]')", sid)))
                cdp.call("Emulation.setEmulatedMedia", {"media": "print"}, sid)
                self.assertTrue(wait(lambda: cdp.js("document.getAnimations().length === 0", sid)), "motion finished")
                for sel, bg, image, adjust, w, h in json.loads(cdp.js(probe, sid)):
                    self.assertTrue(bg not in ("rgba(0, 0, 0, 0)", "transparent") or image != "none", f"{sel} is painted in print")
                    self.assertEqual(adjust, "exact", f"{sel} asks the printer to keep its colour")
                    self.assertGreater(w, 0, sel)
                    self.assertGreater(h, 0, sel)


if __name__ == "__main__":
    unittest.main()
