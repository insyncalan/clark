"""Row 1371: the words of the quiet index status under a source folder, and when the screen-reader line speaks (pure functions, run in node).

Run: python3 dev/run_tests.py test_index_note
The state is a stand-in for what the index will report. Node is required: fails, never skips.
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src/clark/page/src/edit/indexNote.js"


def run(expr):
    node = shutil.which("node")
    assert node, "node is required"
    js = "import('" + SRC.as_uri() + "').then(m => console.log(JSON.stringify(" + expr + ")))"
    out = subprocess.run([node, "-e", js], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def note(s):
    return run("m.note(" + json.dumps(s) + ")")


class IndexNote(unittest.TestCase):
    def test_each_state_has_its_words(self):
        cases = [
            ({"phase": "waiting"}, "Waiting to index", ""),
            ({"phase": "reading", "read": 21, "total": 50}, "Indexing… 42%", ""),
            ({"phase": "done", "read": 9, "total": 9, "left_out": 0}, "100% indexed", ""),
            ({"phase": "done", "total": 9, "left_out": 12}, "100% indexed. 12 files could not be read", "why"),
            ({"phase": "done", "total": 9, "left_out": 1}, "100% indexed. 1 file could not be read", "why"),
            ({"phase": "updating", "changed": 3}, "Updating… 3 files changed", ""),
            ({"phase": "paused"}, "Indexing paused. It carries on when clark is open", ""),
            ({"phase": "failed"}, "Could not index this folder.", "retry"),
            ({"phase": "cleared"}, "Not indexed.", "reindex"),
        ]
        for state, text, link in cases:
            self.assertEqual(note(state), {"text": text, "link": link}, state)

    def test_the_links_are_built_with_their_words(self):
        self.assertEqual(run("m.LINKS"), {"why": "(why)", "retry": "Try again", "reindex": "Index again"})

    def test_the_all_projects_note(self):
        self.assertEqual(run("m.projectsNote(3, 3)"), "Indexed for 3 of 3 projects")

    def test_a_done_note_has_no_date_and_no_file_count(self):
        self.assertEqual(note({"phase": "reading", "read": 180, "total": 422})["text"], "Indexing… 42%")
        self.assertEqual(note({"phase": "done", "total": 9, "date": "2026-11-19"})["text"], "100% indexed")

    def test_no_readable_files_is_not_100_percent(self):
        self.assertEqual(note({"phase": "done", "total": 0})["text"], "No files to index")

    def test_percent_is_files_read_and_never_100_while_one_is_unread(self):
        self.assertEqual(run("[m.percent(1,3), m.percent(199,200), m.percent(3,3), m.percent(9,3), m.percent(0,0)]"), [33, 99, 100, 100, 0])

    def test_percent_ignores_a_negative_or_missing_count(self):
        self.assertEqual(run("[m.percent(-5,10), m.percent(-1,3), m.percent(0,10)]"), [0, 0, 0])
        self.assertEqual(note({"phase": "reading", "read": -5, "total": 10})["text"], "Indexing… 0%")
        self.assertEqual(note({"phase": "reading", "total": 10})["text"], "Indexing… 0%")
        self.assertEqual(note({"phase": "reading", "read": 4})["text"], "Indexing… 0%")
        self.assertEqual(run("[m.percent(5, -3), m.percent(5, Infinity), m.percent(NaN, 5)]"), [0, 0, 0])

    def test_percent_steps_at_the_milestones(self):
        self.assertEqual(run("[0,25,50,75,100].map(r => m.percent(r, 100))"), [0, 25, 50, 75, 100])
        self.assertEqual(run("[m.percent(1,4), m.percent(2,4), m.percent(3,4), m.percent(4,4), m.percent(7,4)]"), [25, 50, 75, 100, 100])

    def test_updating_with_no_count_says_zero_files(self):
        self.assertEqual(note({"phase": "updating"})["text"], "Updating… 0 files changed")
        self.assertEqual(note({"phase": "updating", "changed": 1})["text"], "Updating… 1 file changed")

    def test_a_done_state_with_no_files_never_speaks(self):
        self.assertEqual(run('m.milestone({phase:"done",total:0})'), -1)
        self.assertEqual(run('m.announce(null,{phase:"done",total:0})'), "")
        self.assertEqual(run('m.announce({phase:"reading",read:0,total:5},{phase:"done",total:0})'), "")

    def test_a_reading_state_with_every_file_read_is_still_the_75_milestone(self):
        self.assertEqual(run('m.milestone({phase:"reading",read:5,total:5})'), 75)
        self.assertEqual(run('m.announce(null,{phase:"reading",read:5,total:5})'), "Indexing… 75%")
        self.assertEqual(run('m.announce({phase:"reading",read:5,total:5},{phase:"done",total:5})'), "100% indexed")

    def test_the_live_region_speaks_at_the_milestones_only(self):
        said = run("""(() => { const out = []; let prev = null;
            for (let r = 0; r <= 100; r++) { const s = {phase: r === 100 ? "done" : "reading", read: r, total: 100};
              const a = m.announce(prev, s); if (a) out.push([r, a]); prev = s; } return out; })()""")
        self.assertEqual([r for r, _ in said], [0, 25, 50, 75, 100])
        self.assertEqual([t for _, t in said], ["Indexing started", "Indexing… 25%", "Indexing… 50%", "Indexing… 75%", "100% indexed"])

    def test_no_speech_for_a_state_that_is_not_moving(self):
        self.assertEqual(run('m.announce({phase:"done",total:3},{phase:"done",total:3})'), "")
        self.assertEqual(run('m.announce(null,{phase:"paused"})'), "")

    def test_no_path_name_text_jargon_or_money_in_any_note(self):
        every = [{"phase": p, "read": 1, "total": 2, "left_out": 2, "changed": 2, "date": "2026-11-19",
                  "path": "/home/x/secret.docx", "file": "secret.docx", "text": "passwords"}
                 for p in ("waiting", "reading", "done", "updating", "paused", "failed", "cleared")]
        for s in every:
            t = note(s)["text"]
            self.assertNotRegex(t, r"secret|/home|passwords|embedding|FTS|passage|[$£€]|\bcolor\b|\bcancelled\b", s["phase"])


if __name__ == "__main__":
    unittest.main()
