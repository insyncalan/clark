"""Row 1264, mock-up item B4: a glance template section whose tiles are all hidden shows the mock-up sentence in the View (v2:539,
approved word, group 11) instead of leaving the section out; a fresh section (no body) and a section with tiles are not changed.
Fictional data only.

Run: python3 dev/run_tests.py test_tpl_glance_b4_1264
"""
import json

from _paths import SRC
from _demo import USER
from test_report_editor import Base, tearDownModule  # noqa: F401
from test_server import chrome
from test_changes import KIND
from test_tpl_glance_page_1264 import seed_rows

SHELL = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
SENTENCE = "No tiles on this section."
OFF = {n: {"hidden": True} for n in ("overdue", "risks", "decisions")}
B = {"id": "b1", "label": "Fictional bespoke", "figure": "7", "tag": "Fine", "tone": "green"}


class B4(Base):
    def setUp(self):
        super().setUp()
        seed_rows(self)

    def make(self, body):
        with self.store.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": "glancetemplate", "title": "Fictional glance template", "sort_order": 999})
        if body is not None:
            status, got = self.real_change({"project": "ABC", "kind": KIND, "op": "update", "id": ref, "changes": {"body": json.dumps(body)}})
            assert status == 200, got
        return ref

    def look(self, ref):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.until("!!document.querySelector('#report .sec')", "the page")
            sec = f"document.querySelector('[data-id={json.dumps(ref)}]')"
            if not p.js(f"!!{sec}"):
                return None
            return p.js(f"""(() => {{ const s = {sec}, e = s.querySelector('.tile-empty');
              return {{tiles: s.querySelectorAll('[data-tile]').length, empty: e ? e.textContent : null, tag: e ? e.tagName : '',
                       inGt: !!(e && e.closest('[data-gt]')), color: e ? getComputedStyle(e).color : '', pad: e ? getComputedStyle(e).paddingLeft : '',
                       text: s.textContent}}; }})()""")

    def test_every_tile_hidden_shows_the_mock_up_sentence(self):
        got = self.look(self.make({"v": 1, "builtin": OFF, "bespoke": [{**B, "hidden": True}]}))
        self.assertIsNotNone(got, "the section stays on the page")
        self.assertEqual(got["empty"], SENTENCE)
        self.assertEqual((got["tag"], got["inGt"], got["tiles"]), ("P", True, 0))
        self.assertEqual(got["pad"], "16px")

    def test_the_three_counting_tiles_hidden_and_no_bespoke_tile_shows_it_too(self):
        self.assertEqual(self.look(self.make({"v": 1, "builtin": OFF}))["empty"], SENTENCE)

    def test_the_sentence_is_muted_text(self):
        got = self.look(self.make({"v": 1, "builtin": OFF}))
        ref = self.look(self.make({"v": 1, "builtin": OFF, "bespoke": [B]}))
        self.assertNotEqual(got["color"], "")
        self.assertIsNone(ref["empty"])

    def test_a_shown_tile_means_no_sentence(self):
        got = self.look(self.make({"v": 1, "health": {"shown": False}, "builtin": OFF, "bespoke": [B]}))        # Project health off: the one own tile is the only tile
        self.assertIsNone(got["empty"])
        self.assertEqual(got["tiles"], 1)
        self.assertNotIn(SENTENCE, got["text"])

    def test_a_counting_tile_left_shown_means_no_sentence(self):
        got = self.look(self.make({"v": 1, "health": {"shown": False}, "builtin": {"overdue": {"hidden": True}, "risks": {"hidden": True}}}))
        self.assertIsNone(got["empty"])
        self.assertEqual(got["tiles"], 1)

    def test_a_fresh_section_with_no_body_is_still_left_out(self):
        self.assertIsNone(self.look(self.make(None)))

    def test_the_sentence_rule_is_in_the_stylesheet(self):
        self.assertRegex(SHELL, r"\.tpl-gt \.tile-empty \{[^}]*padding: var\(--space-4\)[^}]*color: var\(--text-muted\)")


class B4NoRows(B4):
    """No work items at all: a counting tile has no rows, so only the person's own hiding makes the sentence."""

    def setUp(self):
        Base.setUp(self)

    test_a_counting_tile_left_shown_means_no_sentence = None      # needs rows to count

    def test_one_or_two_eyes_off_and_no_rows_is_a_section_with_nothing_to_say_and_is_left_out(self):
        for off in (("overdue",), ("overdue", "risks")):
            with self.subTest(off=off):
                self.assertIsNone(self.look(self.make({"v": 1, "builtin": {n: {"hidden": True} for n in off}})))

    def test_all_three_eyes_off_and_no_rows_shows_the_sentence(self):
        self.assertEqual(self.look(self.make({"v": 1, "builtin": OFF}))["empty"], SENTENCE)
