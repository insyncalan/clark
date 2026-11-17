"""Row 1264: Remove tile is also offered on a new draft tile (mock-up, ruled 17-11). On a draft it drops the draft: nothing is stored,
the editor closes and the focus goes where Cancel puts it. A stored tile keeps the Removed toast. Fictional data only.

Run: python3 dev/run_tests.py test_tpl_glance_remove_draft_1264
"""
import unittest

from test_server import chrome, wait  # noqa: F401
from test_tpl_glance_editor_1264 import Editor, OWN
from test_report_editor import tearDownModule  # noqa: F401


class RemoveDraft(Editor):
    def test_R1_a_new_draft_has_remove_tile_first_and_pressing_it_drops_the_draft_storing_nothing(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_add(p)
            p.js("document.querySelector('.ddmenu[role=menu] [role=menuitem]').click()")
            self.editor_open(p)
            before = self.applies()
            self.assertEqual(p.js(f"[...document.querySelectorAll({self.q('[data-tile-editor] .foot button')})].map(b => b.textContent.trim())"),
                             ["Remove tile", "Cancel", "Done"])
            self.click(p, "[data-tile-editor] [data-remove]")
            p.until(f"!document.querySelector({self.q('[data-tile-editor]')})", "the editor closed")
            self.assertEqual(p.js("document.body.innerText.includes('Changes to the tile cancelled')"), False, "not the cancel words")
            self.assertEqual(p.js("document.body.innerText.includes('Removed: New tile')"), True, "the mock-up words: Removed: and the name")
            p.until("document.activeElement.classList.contains('tileadd')", "focus on Add a tile")
            self.assertEqual(self.applies(), before, "nothing was stored")
            self.assertFalse(self.body().get("bespoke"))
            self.assertFalse(p.js("!!document.querySelector('[data-undo]')"), "no Undo for a draft that was never stored")

    def test_R2_a_stored_tile_still_removes_with_the_removed_toast(self):
        self.seed([OWN])
        with chrome() as cdp:
            p = self.page(cdp)
            self.click(p, "[data-tile=t1] [data-tile-pencil]")
            self.editor_open(p)
            self.click(p, "[data-tile-editor] [data-remove]")
            self.assertTrue(wait(lambda: not self.body().get("bespoke"), 10), f"stored: {self.body()}")
            p.until("!!document.querySelector('[data-undo]')", "the toast")
            self.assertEqual(self.toast(p), "Removed: Fictional own tile")


if __name__ == "__main__":
    unittest.main()
