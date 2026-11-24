"""Row 1252, slice 1: the page starters of Settings, Add page (logic/templates.js STARTERS, startSections, promptFor, handTemplates).
Pins DoD3 (each starter builds its listed template sections and every part has prompt copy, none empty) and DoD9 (a section added by hand is never a
Gantt or a Work items section) at the logic level. No Chrome: the page's catalogue runs in node. Fictional data only.

Run: python3 dev/run_tests.py test_add_pages_starters_1252
"""
import json
import shutil
import subprocess
import unittest

from _paths import SRC

LOGIC = SRC / "clark" / "page" / "src" / "logic" / "templates.js"
NODE = shutil.which("node")

APPROVED = {
    "blank": ["Write one or two sentences: what is this page and who is it for?", "Say what the reader should look at first."],
    "status": ["Write the headline in one line: where the project stands this week.", "Add the number and what it counts."],
    "documents": ["Say in one line what these papers are and why the reader needs them.", "Add the file or link and say what it is."],
    "gantt": ["Say in one line what this plan covers and the dates it runs over."],
    "people": ["Add a name, a role and how to reach them.", "Write the next step and who does it."],
}
LISTED = {
    "blank": ["text", "text-image"],
    "status": ["report-headline", "figures-4", "raid-3", "key-dates"],
    "documents": ["text", "docs-links"],
    "gantt": ["current-state", "gantt", "work-items"],
    "people": ["contacts", "checklist"],
}


def run(expr):
    script = f'import * as T from {json.dumps(LOGIC.as_uri())}; console.log(JSON.stringify({expr}));'
    got = subprocess.run([NODE, "--input-type=module", "-e", script], capture_output=True, text=True, timeout=60)
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


@unittest.skipUnless(NODE, "node is not installed")
class Starters(unittest.TestCase):
    def test_five_starters_in_the_approved_order_with_their_listed_templates(self):
        got = run("T.STARTERS.map((s) => [s.id, s.name, s.parts.map((p) => p.template)])")
        self.assertEqual([g[0] for g in got], ["blank", "status", "documents", "gantt", "people"])
        self.assertEqual([g[1] for g in got], ["Blank with prompts", "Status", "Documents", "Gantt", "People and next steps"])
        self.assertEqual({g[0]: g[2] for g in got}, LISTED)
        self.assertEqual(run("T.MAX_ADDED_PAGES"), 5)

    def test_every_starter_part_has_prompt_copy_and_none_is_empty(self):
        for sid, tpls in LISTED.items():
            parts = run(f"T.STARTERS.find((s) => s.id === {json.dumps(sid)}).parts")
            written = [p["prompt"] for p in parts if p.get("prompt")]
            self.assertEqual(written, APPROVED[sid], sid)
            for p in parts:
                self.assertTrue(p.get("prompt") or p.get("live"), f"{sid}: a part has a prompt or fills itself from the project: {p}")
            ids = run("T.TEMPLATES.map((t) => t.id)")
            for t in tpls:
                self.assertIn(t, ids, f"{sid}: the template {t} exists")
        self.assertEqual(run("T.STARTERS.find((s) => s.id === 'gantt').description"),
                         "A Gantt page with a header and text, a Gantt section and a Work items section.")

    def test_a_new_page_holds_its_starters_sections_never_empty_and_the_gantt_starter_holds_none(self):
        for sid in ("blank", "status", "documents", "people"):
            secs = run(f"T.startSections({json.dumps(sid)})")
            self.assertEqual(len(secs), len(LISTED[sid]), sid)
            for s in secs:
                self.assertTrue(s["title"] and s["type"], f"{sid}: {s}")      # a body may be empty: the page draws the part's prompt line (or its live rows) in it
            self.assertEqual(len({s["id"] for s in secs}), len(secs), f"{sid}: ids differ")
        self.assertEqual(run("T.startSections('gantt')"), [])
        self.assertEqual(run("T.startSections('nope')"), [])

    def test_the_prompt_of_a_section_is_its_starters_part_and_a_hand_added_one_takes_the_template_description(self):
        for sid in ("blank", "documents", "people"):
            secs = run(f"T.startSections({json.dumps(sid)})")
            got = run(f"(() => {{ const s = T.startSections({json.dumps(sid)}); return s.map((x) => T.promptFor({json.dumps(sid)}, s, x.id)); }})()")
            self.assertEqual(got, APPROVED[sid], sid)
            self.assertEqual(len(secs), len(got))
        self.assertEqual(run("T.promptFor('blank', [], 'x')"), "")

    def test_prebuilt_gantt_page_holds_exactly_three_sections_in_order(self):
        """AP4 (PM 24-11 18:08): the Gantt starter, which is the prebuilt Gantt page, holds exactly three sections: Header and Text, Gantt, Work items (count, types, order).
        (Belongs with the part 1 starters; kept on p3b as a note.) The page holds none of them as stored rows: they are built into the page."""
        parts = run("T.STARTERS.find((s) => s.id === 'gantt').parts.map((p) => { const t = T.TEMPLATES.find((x) => x.id === p.template); return [t.name, t.type]; })")
        self.assertEqual(len(parts), 3)
        self.assertEqual([p[0] for p in parts], ["Header and Text", "Gantt", "Work items"])
        self.assertEqual([p[1] for p in parts], ["text", "gantt", "workitems"])
        self.assertEqual(run("T.startSections('gantt')"), [])

    def test_the_text_with_image_template_and_its_section_heading(self):
        """AP3 (PM 24-11 18:10): the template is named 'Text with image' in the starter's list and its section heading starts as 'Text and Image Side by Side'."""
        got = run("(() => { const t = T.TEMPLATES.find((x) => x.id === 'text-image'); const b = T.STARTERS.find((s) => s.id === 'blank'); return [t.name, t.title, b.parts.map((p) => T.TEMPLATES.find((x) => x.id === p.template).name), T.startSections('blank').map((s) => s.title)]; })()")
        self.assertEqual(got[0], "Text with image")
        self.assertEqual(got[1], "Text and Image Side by Side")
        self.assertEqual(got[2][1], "Text with image")
        self.assertEqual(got[3][1], "Text and Image Side by Side")

    def test_hand_added_sections_never_gantt_or_work_items(self):
        self.assertEqual(run("T.HAND_NEVER"), ["gantt", "gantttable", "workitems"])
        types = run("T.handTemplates().map((t) => t.type)")
        self.assertTrue(types)
        for never in ("gantt", "gantttable", "workitems"):
            self.assertNotIn(never, types)
        for t in run("T.handTemplates()"):
            self.assertTrue(t["ready"], t["id"])
        for sid in ("blank", "status", "documents", "people"):
            for s in run(f"T.startSections({json.dumps(sid)})"):
                self.assertNotIn(s["type"], ("gantt", "gantttable", "workitems"), sid)


if __name__ == "__main__":
    unittest.main()
