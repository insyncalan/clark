"""#450 row 39, the archived work item peek (prototype views.js:1006-10, peek.js:409-30): under Show archived the archived items
are a table, each tagged Archived; a row opens the side peek, read only, with one Restore. Restore puts the item back in one step
(one Undo) and leaves the peek open on it, now editable. Esc and Close shut it and put the focus back on its row. Only one peek is
open at a time. A published file has none of it.

Run: python3 dev/run_tests.py test_work_archived_peek
Headless Chrome (required: fails, never skips, without it). Desktop (1400) and 900 px, light and dark.
"""
import tempfile
import unittest
from pathlib import Path

from _demo import USER
from _paths import SRC

from clark import publish  # noqa: E402
from test_work_board_page import Base  # noqa: E402
from test_work_filters import click, dblclick, key  # noqa: E402

VARIANTS = [(w, s) for w in (1400, 900) for s in ("light", "dark")]
NOTE = "Archived, so it is read-only."


class ArchivedPeek(Base):
    def setUp(self):
        super().setUp()
        self.gone = [self.id_of("Book the training room"), self.id_of("Supplier slips")]
        with self.store.step("dashboard", USER) as st:
            for ref in self.gone:
                st.archive("actions" if "-A-" in ref else "raid", ref)

    def open_list(self, cdp, sid, scheme="light"):
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
        cdp.js("try { localStorage.removeItem('clark.workArchived.ABC'); } catch (e) {}", sid)
        self.until(cdp, sid, "!!document.querySelector('#showArchived')", "the Show archived pill")
        click(cdp, sid, "#showArchived")
        self.until(cdp, sid, "document.querySelectorAll('#archived-list tr.arch-row').length === 2", "the archived table")

    def open_peek(self, cdp, sid, ref):
        click(cdp, sid, f"#archived-list tr[data-arch-id='{ref}']")
        self.until(cdp, sid, f"document.querySelector('#peek-archived')?.dataset.peekArchived === '{ref}'", "the archived peek")
        self.until(cdp, sid, "document.activeElement && document.activeElement.matches('#peek-archived [data-pk-close]')", "the focus in the peek")

    def test_a_row_opens_the_peek_read_only_with_one_restore(self):
        from test_server import chrome
        for width, scheme in VARIANTS:
            with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                self.open_list(cdp, sid, scheme)
                self.assertEqual(cdp.js("[...document.querySelectorAll('#archived-list thead th')].map(t => t.textContent).join()", sid), "Type,Item,Owner,Due,Status")
                self.assertEqual(cdp.js("document.querySelectorAll('#archived-list tr.arch-row .tag.arch').length", sid), 2, "each row says Archived")
                self.open_peek(cdp, sid, self.gone[0])
                pk = "#peek-archived"
                self.assertFalse(cdp.js("!!document.querySelector('#peek')", sid), "one peek at a time")
                self.assertIn(NOTE, cdp.js(f"document.querySelector('{pk} .pk-archnote').textContent", sid))
                self.assertIn("Book the training room", cdp.js(f"document.querySelector('{pk} .pk-title').textContent", sid))
                self.assertIn("Low", cdp.js(f"document.querySelector('{pk} .pk-fields').textContent", sid), "the peek's own fields, as they were")
                self.assertEqual(cdp.js(f"[...document.querySelectorAll('{pk} button')].filter(b => /Restore/.test(b.textContent)).length", sid), 1, "one Restore")
                self.assertEqual(cdp.js(f"document.querySelectorAll('{pk} input, {pk} select, {pk} textarea, {pk} [contenteditable], {pk} [role=tab], {pk} [data-words], {pk} .cell-pick').length", sid), 0, "read only: nothing to type into, no tabs")
                self.assertEqual(cdp.js(f"[...document.querySelectorAll('{pk} button')].map(b => b.id || b.dataset.pkClose !== undefined && 'close' || b.dataset.pkWide !== undefined && 'wide' || b.textContent).sort().join()", sid), "close,pk-restore,wide",
                                 "Restore is the only change offered")
                self.until(cdp, sid, f"!document.querySelector('{pk}').getAnimations().some(a => a.playState === 'running')", "the slide in to end")
                box = cdp.js(f"(() => {{ const r = document.querySelector('{pk}').getBoundingClientRect(); return [Math.round(r.right), Math.round(r.top), Math.round(r.width)]; }})()", sid)
                self.assertEqual(box[0], cdp.js("document.documentElement.clientWidth", sid), "the side peek is at the right edge")
                self.assertLessEqual(box[0], width)
                self.assertEqual(box[1], 0)
                self.assertGreaterEqual(box[2], 420)
                bg, fg = cdp.js(f"(() => {{ const s = getComputedStyle(document.querySelector('{pk}')); const n = getComputedStyle(document.querySelector('{pk} .pk-archnote p')); return [s.backgroundColor, n.color]; }})()", sid)
                self.assertNotEqual(bg, fg)
                dark = cdp.js(f"(() => {{ const m = getComputedStyle(document.querySelector('{pk}')).backgroundColor.match(/\\d+/g).map(Number); return (m[0] + m[1] + m[2]) / 3 < 100; }})()", sid)
                self.assertEqual(dark, scheme == "dark", "the peek follows the colour scheme")
                self.assertFalse(cdp.js("document.documentElement.scrollWidth > window.innerWidth", sid), "no sideways scroll")
                self.assertEqual(cdp.js(f"document.querySelector('#archived-list tr[data-arch-id=\"{self.gone[0]}\"]').classList.contains('sel')", sid), True)

    def test_esc_and_close_shut_it_and_the_focus_goes_back_to_its_row(self):
        from test_server import chrome
        for width, scheme in VARIANTS:
            with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                self.open_list(cdp, sid, scheme)
                self.open_peek(cdp, sid, self.gone[1])
                key(cdp, sid, "Escape")
                self.until(cdp, sid, "!document.querySelector('#peek-archived')", "the peek shut by Esc")
                self.until(cdp, sid, f"document.activeElement && document.activeElement.dataset.archId === '{self.gone[1]}'", "the focus on the row")
                key(cdp, sid, "Enter")
                self.until(cdp, sid, f"document.querySelector('#peek-archived')?.dataset.peekArchived === '{self.gone[1]}'", "Enter opens it again")
                click(cdp, sid, "#peek-archived [data-pk-close]")
                self.until(cdp, sid, "!document.querySelector('#peek-archived')", "the peek shut by Close")
                self.until(cdp, sid, f"document.activeElement && document.activeElement.dataset.archId === '{self.gone[1]}'", "the focus on the row after Close")
                self.assertFalse(cdp.js("document.documentElement.scrollWidth > window.innerWidth", sid), "no sideways scroll")

    def test_if_its_row_has_gone_the_focus_falls_back_never_to_the_body(self):
        from test_server import chrome
        with chrome() as cdp:
            sid = self.visit(cdp, width=900)
            self.open_list(cdp, sid)
            self.open_peek(cdp, sid, self.gone[1])            # the row clicked is the opener too
            cdp.js(f"document.querySelector('#archived-list tr[data-arch-id=\"{self.gone[1]}\"]').remove()", sid)
            key(cdp, sid, "Escape")
            self.until(cdp, sid, "!document.querySelector('#peek-archived')", "the peek shut by Esc")
            self.until(cdp, sid, f"document.activeElement && document.activeElement.dataset.archId === '{self.gone[0]}'", "the focus on the list's first row")
            self.open_peek(cdp, sid, self.gone[0])
            cdp.js("document.querySelectorAll('#archived-list tr.arch-row').forEach(r => r.remove())", sid)
            click(cdp, sid, "#peek-archived [data-pk-close]")
            self.until(cdp, sid, "!document.querySelector('#peek-archived')", "the peek shut by Close")
            self.until(cdp, sid, "document.activeElement && document.activeElement.id === 'showArchived'", "the focus on the Show archived pill")
            self.assertFalse(cdp.js("document.activeElement === document.body", sid))

    def test_a_live_row_takes_the_place_of_the_archived_peek(self):
        from test_server import chrome
        with chrome() as cdp:
            sid = self.visit(cdp)
            self.open_list(cdp, sid)
            self.open_peek(cdp, sid, self.gone[0])
            live = cdp.js("document.querySelector('#work-list tr[data-id]').dataset.id", sid)
            click(cdp, sid, f"#work-list tr[data-id='{live}'] .t")   # in Edit a click picks the row and opens its peek (row 806)
            self.until(cdp, sid, f"document.querySelector('#peek')?.dataset.peek === '{live}'", "the live peek")
            self.until(cdp, sid, "!document.querySelector('#peek-archived')", "the archived peek gone")
            self.open_peek(cdp, sid, self.gone[1])
            self.until(cdp, sid, "!document.querySelector('#peek')", "the live peek gone")

    def test_restore_puts_it_back_and_leaves_the_peek_open_on_it(self):
        from test_server import chrome
        with chrome() as cdp:
            sid = self.visit(cdp)
            self.open_list(cdp, sid)
            self.open_peek(cdp, sid, self.gone[0])
            before = self.steps()
            click(cdp, sid, "#peek-archived #pk-restore")
            self.until(cdp, sid, f"document.querySelector('#peek')?.dataset.peek === '{self.gone[0]}'", "the live peek on the restored item")
            self.assertFalse(cdp.js("!!document.querySelector('#peek-archived')", sid))
            self.assertEqual(self.row(self.gone[0])["archived"], 0)
            self.assertEqual(self.steps(), before + 1, "one step, one Undo")
            self.until(cdp, sid, f"!!document.querySelector('#work-list tr[data-id=\"{self.gone[0]}\"]')", "the row back in the list")
            self.until(cdp, sid, "document.querySelector('#showArchived').textContent === 'Show archived 1'", "the count")
            self.assertIn(f"{self.gone[0]} restored.", cdp.js("document.querySelector('.toast-text').textContent", sid))
            click(cdp, sid, ".toast [data-undo]")
            self.until(cdp, sid, "document.querySelector('#showArchived').textContent === 'Show archived 2'", "archived again after Undo")
            self.assertEqual(self.row(self.gone[0])["archived"], 1)

    def test_a_published_file_has_no_archived_peek(self):
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        out = Path(publish.publish(self.store, "ABC", folder, by_user=USER, now="2026-10-29", branding=tempfile.mkdtemp())["path"])
        html = out.read_text(encoding="utf-8")
        for words in (NOTE, "Restore it to make a change", "peek-archived", "pk-archnote"):
            self.assertNotIn(words, html)
        for ref in self.gone:
            self.assertNotIn(ref, html)
        view = (SRC / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        self.assertNotIn("peek-archived", view, "the view bundle carries no archived peek")

    def test_the_source_stays_in_the_edit_parts(self):
        src = SRC / "clark" / "page" / "src"
        peek = (src / "components" / "Peek.jsx").read_text(encoding="utf-8")
        self.assertNotIn("archived=only", peek)
        self.assertNotIn("getArchived", peek)
        arch = (src / "edit" / "ArchivedItems.jsx").read_text(encoding="utf-8")
        self.assertIn('from "../components/Peek.jsx"', arch, "the archived peek reuses the peek's own parts")


if __name__ == "__main__":
    unittest.main()
