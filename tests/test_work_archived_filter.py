"""Row 1067: Work items has no Show archived pill; archived work is reached with the filter word is:archived (Edit page only).
The word lists the project's archived items, muted and marked Archived; a row opens the read-only peek with one Restore (one step,
one Undo). Clearing the line brings the live list back. A published file has no archived row and no such word.

Run: python3 dev/run_tests.py test_work_archived_filter
Headless Chrome (required: fails, never skips, without it). Desktop (1400) and 900 px only.
"""
import tempfile
import unittest
from pathlib import Path

from _demo import USER
from _paths import SRC

from clark import publish  # noqa: E402
from test_work_board_page import Base  # noqa: E402
from test_work_filters import click, key, set_line  # noqa: E402

WIDTHS = (1400, 900)
NOTE = "Archived, so it is read-only."


class ArchivedFilter(Base):
    def setUp(self):
        super().setUp()
        self.gone = [self.id_of("Book the training room"), self.id_of("Supplier slips")]
        with self.store.step("dashboard", USER) as st:
            for ref in self.gone:
                st.archive("actions" if "-A-" in ref else "raid", ref)

    def show(self, cdp, sid):
        set_line(cdp, sid, "is:archived")
        self.until(cdp, sid, "document.querySelectorAll('#archived-list tr.arch-row').length === 2", "the archived rows")

    def test_no_pill_and_no_show_archived_words_on_work_items(self):
        from test_server import chrome
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                self.until(cdp, sid, "!!document.querySelector('#fline-input')", "the filter line")
                self.assertEqual(cdp.js("document.querySelectorAll('#showArchived, .arch-pill, #archived-list').length", sid), 0)
                self.assertFalse(cdp.js("/Show archived/.test(document.querySelector('#work').textContent)", sid))
                self.assertFalse(cdp.js("!!document.querySelector('#work-list tr[data-id=\"%s\"]')" % self.gone[0], sid), "an archived row is not in the table")

    def test_is_archived_lists_the_archived_items_read_only_and_clearing_brings_back_the_list(self):
        from test_server import chrome
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                self.show(cdp, sid)
                self.assertEqual(cdp.js("document.querySelectorAll('#archived-list .tag.arch').length", sid), 2)
                self.assertEqual(cdp.js("document.querySelectorAll('#archived-list input, #archived-list select, #archived-list textarea, #archived-list [contenteditable], #archived-list button').length", sid), 0)
                self.assertFalse(cdp.js("!!document.querySelector('#work-list tr[data-id]')", sid), "the live list is not drawn beside it")
                self.assertFalse(cdp.js("document.documentElement.scrollWidth > window.innerWidth", sid), "no sideways scroll")
                set_line(cdp, sid, "")
                self.until(cdp, sid, "!document.querySelector('#archived-list') && !!document.querySelector('#work-list tr[data-id]')", "the live list back")

    def test_is_archived_with_type_action_narrows_to_archived_action_items_only(self):
        from test_server import chrome
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                self.show(cdp, sid)
                set_line(cdp, sid, "is:archived type:action")
                self.until(cdp, sid, "document.querySelectorAll('#archived-list tr.arch-row').length === 1", "only the archived action")
                ids = cdp.js("[...document.querySelectorAll('#archived-list tr.arch-row')].map(r => r.dataset.archId)", sid)
                self.assertEqual(ids, [i for i in self.gone if "-A-" in i])
                self.assertFalse(cdp.js("!!document.querySelector('#work-list tr[data-id]')", sid), "the live list is not drawn beside it")

    def test_a_row_opens_the_read_only_peek_and_restore_puts_it_back_with_one_undo(self):
        from test_server import chrome
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                self.show(cdp, sid)
                click(cdp, sid, f"#archived-list tr[data-arch-id='{self.gone[0]}']")
                self.until(cdp, sid, f"document.querySelector('#peek-archived')?.dataset.peekArchived === '{self.gone[0]}'", "the archived peek")
                self.assertIn(NOTE, cdp.js("document.querySelector('#peek-archived .pk-archnote').textContent", sid))
                self.assertEqual(cdp.js("[...document.querySelectorAll('#peek-archived button')].filter(b => /Restore/.test(b.textContent)).length", sid), 1, "one Restore")
                self.until(cdp, sid, "!document.querySelector('#peek-archived').getAnimations({subtree: true}).some(a => a.playState === 'running')", "the slide in")
                before = self.steps()
                click(cdp, sid, "#peek-archived #pk-restore")
                self.until(cdp, sid, f"document.querySelector('#peek')?.dataset.peek === '{self.gone[0]}'", "the live peek on the restored item")
                self.assertEqual(self.row(self.gone[0])["archived"], 0)
                self.assertEqual(self.steps(), before + 1, "one step, one Undo")
                self.until(cdp, sid, "document.querySelectorAll('#archived-list .arch-row').length === 1", "one archived row left")
                self.assertIn(f"{self.gone[0]} restored.", cdp.js("document.querySelector('.toast-text').textContent", sid))
                click(cdp, sid, ".toast [data-undo]")
                self.until(cdp, sid, "document.querySelectorAll('#archived-list .arch-row').length === 2", "archived again after Undo")
                self.assertEqual(self.row(self.gone[0])["archived"], 1)

    def test_esc_shuts_the_peek_and_the_focus_goes_back_to_its_row(self):
        from test_server import chrome
        with chrome() as cdp:
            sid = self.visit(cdp, width=900)
            self.show(cdp, sid)
            click(cdp, sid, f"#archived-list tr[data-arch-id='{self.gone[1]}']")
            self.until(cdp, sid, "!!document.querySelector('#peek-archived')", "the peek")
            self.until(cdp, sid, "!document.querySelector('#peek-archived').getAnimations({subtree: true}).some(a => a.playState === 'running')", "the slide in")
            key(cdp, sid, "Escape")
            self.until(cdp, sid, "!document.querySelector('#peek-archived')", "the peek shut")
            self.until(cdp, sid, f"document.activeElement && document.activeElement.dataset.archId === '{self.gone[1]}'", "the focus on the row")

    def test_a_published_file_has_no_archived_row_no_pill_and_no_archived_peek(self):
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        out = Path(publish.publish(self.store, "ABC", folder, by_user=USER, now="2026-10-29", branding=tempfile.mkdtemp())["path"])
        html = out.read_text(encoding="utf-8")
        for words in ("Show archived", "peek-archived", "pk-archnote", NOTE, *self.gone):
            self.assertNotIn(words, html)

    def test_the_source_has_no_pill(self):
        src = SRC / "clark" / "page" / "src"
        self.assertNotIn("ArchivedPill", (src / "edit" / "index.js").read_text(encoding="utf-8"))
        self.assertNotIn("showArchived", (src / "edit" / "ArchivedItems.jsx").read_text(encoding="utf-8"))
        self.assertNotIn("workArchived", (src / "edit" / "ArchivedItems.jsx").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
