"""Row 1264 slice 6, logic fixes of the tile editor: a bin in one section does not close another section's editor; a double Done is one step;
a failed Done puts the focus on the Label; a tile with no tone opens as Neutral. Real browser. Fictional data only.

Run: python3 dev/run_tests.py test_tpl_glance_editor_logic_1264
"""
import json
import time
import unittest

from _demo import USER
from test_changes import KIND
from test_tpl_glance_editor_1264 import Editor, OWN, tearDownModule  # noqa: F401
from test_server import chrome, wait


class Logic(Editor):
    def pencil(self, p, tid="t1"):
        self.click(p, f"[data-tile={tid}] [data-tile-pencil]")
        self.editor_open(p)

    def test_a_bin_in_another_section_with_the_same_tile_id_leaves_this_editor_open(self):
        with self.store.step("dashboard", USER) as st:
            other = st.create("report_sections", {"project": "ABC", "type": "glancetemplate", "title": "Fictional other glance", "sort_order": 999})
        self.seed([OWN])
        status, got = self.real_change({"project": "ABC", "kind": KIND, "op": "update", "id": other,
                                        "changes": {"body": json.dumps({"v": 1, "bespoke": [OWN]})}})
        self.assertEqual(status, 200, got)
        with chrome() as cdp:
            p = self.page(cdp)
            p.until(f"!!document.querySelector('[data-id=\"{other}\"] [data-tile=t1] [data-tile-bin]')", "the other section drew its tile")
            self.pencil(p)
            p.js(f"document.querySelector('[data-id=\"{other}\"] [data-tile=t1] [data-tile-bin]').click()")
            p.until(f"!document.querySelector('[data-id=\"{other}\"] [data-tile=t1]')", "the other tile is gone")
            self.assertTrue(p.js(f"!!document.querySelector({self.q('[data-tile-editor]')})"), "this section's editor stays open")

    def test_a_double_done_is_one_step(self):
        self.seed([OWN])
        with chrome() as cdp:
            p = self.page(cdp)
            self.pencil(p)
            self.fill(p, "label", "Fictional twice")
            before = self.applies()
            p.js(f"var b = document.querySelector({self.q('[data-tile-editor] [data-done]')}); b.click(); b.click();")
            self.assertTrue(wait(lambda: self.body()["bespoke"][0]["label"] == "Fictional twice", 10))
            p.until(f"!document.querySelector({self.q('[data-tile-editor]')})", "the editor closed")
            time.sleep(1.5)
            self.assertEqual(self.applies(), before + 1)

    def test_a_done_after_a_done_is_saved_too(self):
        self.seed([OWN])
        with chrome() as cdp:
            p = self.page(cdp)
            for word in ("Fictional first", "Fictional second"):
                self.pencil(p)
                self.fill(p, "label", word)
                self.click(p, "[data-tile-editor] [data-done]")
                self.assertTrue(wait(lambda w=word: self.body()["bespoke"][0]["label"] == w, 10), word)
                p.until(f"!document.querySelector({self.q('[data-tile-editor]')})", "the editor closed")

    def test_a_failed_done_puts_the_focus_on_the_label(self):
        self.seed([OWN])
        with chrome() as cdp:
            p = self.page(cdp)
            self.pencil(p)
            self.fill(p, "label", "")
            p.js(f"document.querySelector({self.q('[data-tile-editor] [data-done]')}).focus()")
            self.assertEqual(p.js("document.activeElement.hasAttribute('data-done')"), True)
            self.click(p, "[data-tile-editor] [data-done]")
            p.until("document.activeElement.dataset.f === 'label'", "the label has the focus")

    def test_a_tile_with_no_tone_opens_as_neutral(self):
        self.seed([{"id": "t1", "label": "Fictional plain", "figure": "1"}])
        with chrome() as cdp:
            p = self.page(cdp)
            self.pencil(p)
            self.assertEqual(p.js(f"document.querySelector({self.q('[data-tile-editor] [role=radio][aria-checked=true]')}).dataset.tone"), "neutral")
            self.click(p, "[data-tile-editor] [data-done]")
            p.until(f"!document.querySelector({self.q('[data-tile-editor]')})", "closed")
            self.assertEqual(p.js(f"document.querySelector({self.q('[data-tile=t1] .tpl-gt-tile')}).classList.contains('tone-n')"), True)


if __name__ == "__main__":
    unittest.main()
