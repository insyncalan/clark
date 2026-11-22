"""Row 1270 sweep killers, quick tier: the pure part of the RAID cards (templates/raid.js, RaidCards.jsx) read in node, no browser.
Fictional rows. Bundled by the pinned esbuild and run in node (skipped when node is not on the machine).

Run: python3 dev/run_tests.py test_raid_pure_node_1270
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

ENTRY = ROOT / "tests" / "fixtures" / "raid_pure_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}
SHIM = "globalThis.addEventListener = () => {}; globalThis.removeEventListener = () => {};\n"


def bundle():
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "rp.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=RP", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    return _BUNDLE["code"]


def run(expr):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(SHIM + bundle() + ";\nconsole.log(JSON.stringify(%s));" % expr, encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


def body(across, n, v=2):
    return json.dumps({"v": v, "across": across, "cards": [{"id": f"ABC-{i:03d}", "source": "client"} for i in range(1, n + 1)]})


class Pure(unittest.TestCase):
    def test_a_body_of_version_two_reads_its_choice_whichever_it_is(self):
        self.assertEqual(run("[RP.acrossOf(%s), RP.acrossOf(%s)]" % (json.dumps(body(3, 2)), json.dumps(body(4, 2)))), [3, 4])
        self.assertEqual(run("[RP.acrossOf(%s), RP.acrossOf(%s)]" % (json.dumps(body(5, 2)), json.dumps(body(4, 2, v=1)))), [0, 0])

    def test_the_served_page_lays_out_a_body_of_version_two_by_its_choice(self):
        for across in (3, 4):
            got = run("[RP.layoutOf({body: %s}, 4), RP.layoutOf({body: %s}, 3)]" % (json.dumps(body(across, 8)), json.dumps(body(across, 8))))
            self.assertEqual(got, [{"across": across, "max": 8}] * 2)
        self.assertEqual(run("RP.layoutOf({body: %s}, 4)" % json.dumps(body(3, 2, v=1))), {"across": 4, "max": 4})

    def test_the_latest_update_has_no_stray_space_around_it(self):
        self.assertEqual(run('[RP.latestOf({latest_update: "  Roof survey booked.  "}), RP.latestOf({latest_update: null}), RP.latestOf(null)]'),
                         ["Roof survey booked.", "", ""])

    def test_a_card_with_no_own_words_draws_no_empty_paragraph(self):
        data = {"project": {"code": "ABC"}, "raid": [{"id": "ABC-001", "type": "Risk", "description": "Tide table", "client_message": "", "latest_update": "Called them.", "archived": 0, "client_visible": 1, "project": "ABC"}]}
        sec = {"title": "Fictional cards", "type": "raid4", "body": json.dumps({"v": 1, "cards": [{"id": "ABC-001", "source": "own"}]})}
        html = run("RP.RaidView({section: %s, data: %s, size: 4}).props.children.map(c => c.props.children.map(x => x && x.props && x.props.class || ''))" % (json.dumps(sec), json.dumps(data)))
        self.assertTrue(html and html[0], html)
        self.assertNotIn("raid-text", [c for row in html for c in row], html)

    def test_each_card_names_its_part_and_its_id_button_says_details(self):
        rows = {"raid": [{"id": "ABC-001", "type": "Risk"}, {"id": "ABC-002", "type": "Issue"}], "actions": [{"id": "ABC-003"}],
                "decisions": [{"id": "ABC-004", "status": "Pending"}, {"id": "ABC-005", "status": "Made"}]}
        got = run("[%s].map(([r, k]) => RP.partWords(r, k))" % ", ".join("[%s, %s]" % (json.dumps(rows[k][i]), json.dumps(k)) for k, i in (("raid", 0), ("raid", 1), ("actions", 0), ("decisions", 0), ("decisions", 1))))
        self.assertEqual(got, ["The risk", "The issue", "The action", "The decision needed", "The decision"])
        src = (PAGE_SRC / "templates" / "RaidCards.jsx").read_text(encoding="utf-8")
        self.assertIn("aria-label={`Open ${c.id} details`}", src)
        self.assertIn("{partWords(c.row, c.kind)}", src)

    def test_the_edit_counts_the_picked_cards_and_names_the_remove_choice(self):
        src = (PAGE_SRC / "edit" / "templates" / "raidEdit.jsx").read_text(encoding="utf-8")
        self.assertIn("`${cards.length} of ${size} picked`", src)
        self.assertIn("`Remove card ${i + 1}`", src)
        self.assertIn("{card ? `Remove card ${i + 1}` : \"Choose an item…\"}", src)       # row 1270: the empty choice of a filled card says Remove card N
        self.assertNotIn("No item (remove this card)", src)

    def test_the_library_card_sketch_is_three_columns_with_three_edges(self):
        cols, edges = run('RP.SKETCHES["raid-cards"]')
        self.assertEqual(cols, "grid-template-columns:repeat(3,1fr)")
        self.assertEqual(len(edges), 3)


class Prototype(unittest.TestCase):
    DESC = "Highlight the biggest risks, actions, issues or decisions as cards. You pick which ones to show, three or four across. Each card shows the description and the latest update."

    def test_the_prototype_has_the_one_raid_cards_row_in_the_page_words(self):
        views = (ROOT / "system" / "prototype" / "views.js").read_text(encoding="utf-8")
        help_ = (ROOT / "system" / "prototype" / "help.js").read_text(encoding="utf-8")
        self.assertIn("{ id: 'raid-cards', name: 'RAID cards', kind: 'raid', fit: ['Full'], d: '" + self.DESC + "', els: ['Heading', 'RAID card ×3', 'Text source', 'Text']", views)
        self.assertIn("['RAID cards', '" + self.DESC + "', 'Full']", help_)
        self.assertNotIn("RAID cards, three", views + help_)
        self.assertNotIn("RAID cards, four", views + help_)


if __name__ == "__main__":
    unittest.main()
