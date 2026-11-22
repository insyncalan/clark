"""Row 1264, mock-up item A6: in the View a counting tile of the glance template is a button that opens Work items with the tile's
filter, as the built-in At a glance does (Glance.jsx openWork(t.filter)); a bespoke tile stays plain; Edit draws no button.
Fictional data only.

Run: python3 dev/run_tests.py test_tpl_glance_a6_1264
"""
import json
import re

from _paths import SRC
from _demo import USER
from test_report_editor import Base, tearDownModule  # noqa: F401
from test_server import chrome
from test_changes import KIND
from test_tpl_glance_page_1264 import seed_rows

SHELL = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
BESPOKE = [{"id": "b1", "label": "Fictional bespoke", "figure": "7", "tag": "Fine", "tone": "green"}]


class A6(Base):
    def setUp(self):
        super().setUp()
        seed_rows(self)
        with self.store.step("dashboard", USER) as st:
            self.ref = st.create("report_sections", {"project": "ABC", "type": "glancetemplate", "title": "Fictional glance template", "sort_order": 999})
        status, got = self.real_change({"project": "ABC", "kind": KIND, "op": "update", "id": self.ref, "changes": {"body": json.dumps({"v": 1, "bespoke": BESPOKE})}})
        assert status == 200, got

    def sel(self, rest=""):
        return f'[data-id={json.dumps(self.ref)}] {rest}'.strip()

    def page(self, cdp):
        p = self.visit(cdp)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, p.sid)
        p.until(f"!!document.querySelector('{self.sel('[data-tile=decisions]')}')", "the tiles")
        return p

    def test_a_counting_tile_is_a_button_that_opens_the_work_items_it_counts(self):
        for key in ("overdue", "risks", "decisions"):
            with self.subTest(key=key), chrome() as cdp:
                p = self.page(cdp)
                self.assertEqual(p.js(f"document.querySelector('{self.sel(f'[data-tile={key}]')}').tagName"), "BUTTON")
                p.js(f"document.querySelector('{self.sel(f'[data-tile={key}]')}').click()")
                p.until("location.hash.startsWith('#work&p=ABC&f=')", "Work items opened with a filter")
                p.until("document.querySelectorAll('#work tbody tr[data-id]').length === 1", "the list holds the one row it counted")

    def test_the_button_has_the_built_in_class_type_and_a_name(self):
        with chrome() as cdp:
            p = self.page(cdp)
            got = p.js(f"(() => {{ const b = document.querySelector('{self.sel('[data-tile=overdue]')}'); return [b.type, b.classList.contains('fig'), b.classList.contains('go'), b.getAttribute('aria-label') || '']; }})()")
        self.assertEqual(got[:3], ["button", True, True])
        self.assertIn("Opens Work items", got[3])
        self.assertIn("Overdue actions", got[3])

    def test_tab_reaches_a_counting_tile_and_not_a_bespoke_one(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.js("document.activeElement && document.activeElement.blur(); window.scrollTo(0, 0)")
            seen = []
            for _ in range(80):
                p.key("Tab", code="Tab", vk=9)
                t = p.js("(document.activeElement.closest && document.activeElement.closest('[data-tile]') || {dataset: {}}).dataset.tile || ''")
                if t:
                    seen.append(t)
                    if t == "decisions":
                        break
            ring = p.js("(() => { const s = getComputedStyle(document.activeElement); return [s.outlineStyle, s.outlineWidth]; })()")
        self.assertEqual(seen[:3], ["overdue", "risks", "decisions"])
        self.assertNotIn("b1", seen)
        self.assertEqual(ring, ["solid", "2px"], "a focus ring like the built-in tiles")

    def test_a_bespoke_tile_is_not_a_button_and_has_no_stop(self):
        with chrome() as cdp:
            p = self.page(cdp)
            got = p.js(f"(() => {{ const b = document.querySelector('{self.sel('[data-tile=b1]')}'); return [b.tagName, b.tabIndex, b.querySelectorAll('button, a').length, b.classList.contains('go'), getComputedStyle(b).cursor]; }})()")
        self.assertEqual(got, ["DIV", -1, 0, False, "auto"])

    def test_edit_mode_tiles_are_not_buttons_of_this_template(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.edit()
            p.until("document.querySelector('#report').dataset.mode === 'edit'", "Edit mode")
            p.until(f"!!document.querySelector('{self.sel('[data-tile=b1] .tpl-gt-tile')}')", "the own tile drew in Edit")
            got = p.js(f"[document.querySelectorAll('{self.sel('button[data-tile]')}').length, [...document.querySelectorAll('{self.sel('.tpl-gt-tile')}')].filter(t => t.tagName !== 'DIV' || t.tabIndex >= 0 || t.classList.contains('go') || t.querySelector('button, a')).length, [...document.querySelectorAll('{self.sel('[data-tile]')}')].map(t => t.dataset.tile), document.querySelectorAll('{self.sel('[data-tile=b1] .tpl-gt-tile')}').length, [...document.querySelectorAll('{self.sel('[data-tile] .fig')}')].map(t => [t.closest('[data-tile]').dataset.tile, t.tagName, t.classList.contains('go')])]")
        self.assertEqual(got[:2], [0, 0], "the Edit part draws its own tiles (plain boxes), not the View's buttons")
        self.assertEqual(got[2], ["health", "overdue", "risks", "decisions", "b1"], "the counts are over real tiles: the four built-in ones and the own tile")
        self.assertEqual(got[3], 1, "the own tile that the test planted is one of them")
        self.assertEqual(got[4], [["health", "DIV", False], ["overdue", "BUTTON", True], ["risks", "BUTTON", True], ["decisions", "BUTTON", True], ["b1", "DIV", False]],
                         "Edit keeps the counting tiles' own buttons (they open Work items); the health tile and the own tile are plain boxes")

    def test_hover_and_focus_rules_are_the_built_in_ones(self):
        self.assertRegex(SHELL, r"\.tpl-gt-tile\.go \{[^}]*cursor: pointer")
        self.assertRegex(SHELL, r"\.tpl-gt-tile\.go:hover \{ border-color: var\(--brand-blue\); box-shadow: var\(--shadow\); \}")
        self.assertRegex(SHELL, r"\.tpl-gt-tile\.go:focus-visible \{ outline: 2px solid var\(--brand-blue\); outline-offset: 2px; \}")
