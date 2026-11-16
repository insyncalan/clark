"""Row 1234: the add-a-use-case picker's logic (logic/useCasePicker.js), run in node without a browser.
Run: python3 dev/run_tests.py test_use_case_picker_node
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import SRC

MOD = SRC / "clark" / "page" / "src" / "logic" / "useCasePicker.js"
ROWS = [
    {"id": "U1", "ref": "UC 1", "name": "Invoices", "status": "On track", "commitment": "Committed", "steps": 0, "total": 2},
    {"id": "U2", "ref": "UC 2", "name": "Payments", "status": "Flag", "commitment": "Planned 2026", "steps": 3, "total": 5},
    {"id": "U3", "ref": "UC 3", "name": "Refunds", "status": "High risk", "commitment": "", "steps": 3, "total": 0},
    {"id": "U4", "ref": "UC 4", "name": "Reports", "status": "Done", "commitment": "Committed", "steps": 1, "total": 2},
]


def run(body, mod=None):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(mod or MOD).read_text(encoding="utf-8")
        (Path(tmp) / "m.mjs").write_text(src, encoding="utf-8")
        (Path(tmp) / "p.mjs").write_text('import * as P from "./m.mjs";\nconst ROWS = ' + json.dumps(ROWS) + ";\nconst ids = (a) => a.map((r) => r.id);\nconsole.log(JSON.stringify(" + body + "));", encoding="utf-8")
        done = subprocess.run([node, str(Path(tmp) / "p.mjs")], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


class Picker(unittest.TestCase):
    def test_search_name_id_status_ref(self):
        self.assertEqual(run('ids(P.visible(ROWS, {...P.emptyState(), q: "pay"}))'), ["U2"])
        self.assertEqual(run('ids(P.visible(ROWS, {...P.emptyState(), q: "u3"}))'), ["U3"])
        self.assertEqual(run('ids(P.visible(ROWS, {...P.emptyState(), q: "HIGH"}))'), ["U3"])
        self.assertEqual(run('ids(P.visible(ROWS, {...P.emptyState(), q: "uc 4"}))'), ["U4"])
        self.assertEqual(run('ids(P.visible(ROWS, {...P.emptyState(), q: "  "}))'), ["U1", "U2", "U3", "U4"])
        self.assertEqual(run('ids(P.visible(ROWS, {...P.emptyState(), q: "pay done"}))'), [])

    def test_is_and_is_not_any_of(self):
        self.assertEqual(run('ids(P.visible(ROWS, P.toggleValue(P.toggleValue(P.emptyState(), "status", "Flag"), "status", "Done")))'), ["U2", "U4"])
        self.assertEqual(run('ids(P.visible(ROWS, P.setMode(P.toggleValue(P.toggleValue(P.emptyState(), "status", "Flag"), "status", "Done"), "status", "not")))'), ["U1", "U3"])
        self.assertEqual(run('ids(P.visible(ROWS, P.toggleValue(P.emptyState(), "commitment", "Committed")))'), ["U1", "U4"])

    def test_more_fields_and_two_filters_together(self):
        self.assertEqual(run('ids(P.visible(ROWS, P.toggleValue(P.emptyState(), "steps", 3)))'), ["U2", "U3"])
        self.assertEqual(run('ids(P.visible(ROWS, P.toggleValue(P.toggleValue(P.emptyState(), "steps", "3"), "total", "5")))'), ["U2"])

    def test_options_select_all_clear_toggle_off(self):
        self.assertEqual(run('P.optionsOf(ROWS, "commitment")'), [{"value": "Committed", "count": 2}, {"value": "Planned 2026", "count": 1}])
        self.assertEqual(run('P.optionsOf(ROWS, "steps").map((o) => o.value)'), ["0", "1", "3"])
        self.assertEqual(run('P.selectAllValues(P.emptyState(), "status", ROWS).filters.status.values'), ["Done", "Flag", "High risk", "On track"])
        self.assertEqual(run('P.clearField(P.selectAllValues(P.emptyState(), "status", ROWS), "status").filters'), {})
        self.assertEqual(run('P.toggleValue(P.toggleValue(P.emptyState(), "status", "Flag"), "status", "Flag").filters.status.values'), [])
        self.assertEqual(run('P.activeCount(P.toggleValue(P.emptyState(), "status", "Flag"))'), 1)
        self.assertEqual(run('P.activeCount(P.emptyState())'), 0)

    def test_selection_counts_and_words(self):
        self.assertEqual(run('(() => { let s = P.toggleValue(P.emptyState(), "status", "Flag"); s = P.pickAllShown(s, ROWS); return [s.picked, P.counts(ROWS, s), P.resultWords(P.counts(ROWS, s)), P.addWords(P.counts(ROWS, s))]; })()'),
                         [["U2"], {"shown": 1, "total": 4, "picked": 1}, "Result: 1 of 4 shown", "Add 1"])
        # a picked row stays picked when a filter hides it; Add counts it; a gone id is dropped; Clear empties
        self.assertEqual(run('(() => { let s = P.toggleRow(P.toggleRow(P.emptyState(), "U1"), "GONE"); s = P.toggleValue(s, "status", "Flag"); return [P.pickedIds(s, ROWS), P.counts(ROWS, s), P.clearPicked(s).picked]; })()'),
                         [["U1"], {"shown": 1, "total": 4, "picked": 1}, []])
        self.assertEqual(run('P.toggleRow(P.toggleRow(P.emptyState(), "U1"), "U1").picked'), [])
        # a count of 0 shows no number
        self.assertEqual(run('[P.addWords({picked: 0}), P.addWords({picked: 2})]'), ["Add selected", "Add 2"])
        self.assertEqual(run('P.pickAllShown(P.toggleValue(P.toggleRow(P.emptyState(), "U1"), "status", "Flag"), ROWS).picked'), ["U1", "U2"])
        self.assertEqual(run('P.pickAllShown(P.pickAllShown(P.emptyState(), ROWS), ROWS).picked'), ["U1", "U2", "U3", "U4"])


if __name__ == "__main__":
    unittest.main()
