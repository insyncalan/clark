"""B-5, Show archived on Work items, as the prototype has it: a pill in the bar with the count (remembered), the archived rows
listed with the word Archived, a row opening read only in the side peek with one Restore (with its history), Restore and Undo
against the real change route; a published file has none of it (it carries no archived row).

Run: python3 dev/run_tests.py test_work_archived_page
Headless Chrome (required: fails, never skips, without it). Desktop (1400) and 900 px, light and dark.
"""
import json
import tempfile
import unittest
from pathlib import Path

from _demo import USER
from _paths import SRC

from clark import page, publish  # noqa: E402
from test_work_board_page import Base  # noqa: E402
from test_work_filters import click  # noqa: E402

VARIANTS = [(w, s) for w in (1400, 900) for s in ("light", "dark")]


class Archived(Base):
    def setUp(self):
        super().setUp()
        from clark import activity_read
        self.s.httpd.activity = activity_read.make_read(self.store.path, self.store.data_for)     # the seam the real app gives the peek's Activity tab
        self.gone = [self.id_of("Book the training room"), self.id_of("Supplier slips")]
        with self.store.step("dashboard", USER) as st:
            for ref in self.gone:
                st.archive("actions" if "-A-" in ref else "raid", ref)

    def scheme(self, cdp, sid, scheme):
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)

    def archived_flags(self):
        return {r: self.row(r)["archived"] for r in self.gone}

    def test_the_pill_is_in_the_bar_with_the_count_and_is_remembered(self):
        from test_server import chrome
        for width, scheme in VARIANTS:
            with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                self.scheme(cdp, sid, scheme)
                self.until(cdp, sid, "!!document.querySelector('.wbar #showArchived')", "the Show archived pill in the bar")
                self.assertEqual(cdp.js("document.querySelector('#showArchived').textContent.trim()", sid), "Show archived 2")
                self.assertEqual(cdp.js("!!document.querySelector('#showArchived svg[data-icn=archive]')", sid), True, "the archive icon")
                self.assertFalse(cdp.js("!!document.querySelector('#archived-list')", sid), "the list is shut until asked for")
                self.assertFalse(cdp.js("!!document.querySelector('#work-list tr[data-id=\"%s\"]')" % self.gone[0], sid), "an archived row is not in the table")
                click(cdp, sid, "#showArchived")
                self.until(cdp, sid, "document.querySelectorAll('#archived-list tr.arch').length === 2", "the archived rows")
                self.assertEqual(cdp.js("document.querySelector('#showArchived').getAttribute('aria-pressed')", sid), "true")
                self.assertEqual(cdp.js("[...document.querySelectorAll('#archived-list .tag')].map(t => t.textContent).join()", sid), "Archived,Archived")
                self.assertEqual(cdp.js("document.querySelectorAll('#archived-list input, #archived-list select, #archived-list textarea, #archived-list button, #archived-list [contenteditable]').length", sid), 0, "no Restore on the row, nothing to type into")
                self.assertFalse(cdp.js("document.documentElement.scrollWidth > window.innerWidth", sid), "no sideways scroll")
                # remembered: a reload brings the list back, switching it off is remembered too
                self.reload(cdp, sid)
                self.until(cdp, sid, "document.querySelectorAll('#archived-list tr.arch').length === 2", "the list after a reload")
                click(cdp, sid, "#showArchived")
                self.until(cdp, sid, "!document.querySelector('#archived-list')", "the list shut")
                self.reload(cdp, sid)
                self.until(cdp, sid, "!!document.querySelector('#showArchived')", "the pill after a reload")
                self.assertFalse(cdp.js("!!document.querySelector('#archived-list')", sid))

    def test_a_row_opens_read_only_in_the_peek_with_one_restore(self):
        from test_server import chrome
        for width, scheme in VARIANTS:
            with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                self.scheme(cdp, sid, scheme)
                self.until(cdp, sid, "!!document.querySelector('#showArchived')", "the pill")
                click(cdp, sid, "#showArchived")
                self.until(cdp, sid, "document.querySelectorAll('#archived-list tr.arch').length === 2", "the rows")
                click(cdp, sid, f"#archived-list tr[data-id='{self.gone[0]}']")
                self.until(cdp, sid, f"document.querySelector('#peek[data-archived]') && document.querySelector('#peek').dataset.peek === '{self.gone[0]}'", "the archived peek")
                self.assertEqual(cdp.js("document.querySelectorAll('#peek #pkRestore').length", sid), 1, "one Restore")
                self.assertEqual(cdp.js("document.querySelectorAll('#peek input, #peek select, #peek textarea, #peek [contenteditable], #peek [data-sneak], #peek .pk-words').length", sid), 0, "read only")
                note = cdp.js("document.querySelector('#peek [data-archived-note]').textContent", sid)
                self.assertIn("Archived, so it is read-only.", note)
                self.assertIn("nothing in it was deleted", note)
                facts = cdp.js("[...document.querySelectorAll('#peek .pk-rofacts dt')].map(e => e.textContent).join()", sid)
                self.assertEqual(facts, "Type,Status,Priority,Owner,Due,Workstream,Milestone")
                self.assertIn("Restore it to make a change", cdp.js("document.querySelector('#peek .pk-saved').textContent", sid))
                self.assertTrue(cdp.js("!!document.querySelector('#peek [data-pk-tab=activity]')", sid), "the history tab")
                self.assertFalse(cdp.js("document.documentElement.scrollWidth > window.innerWidth", sid), "no sideways scroll")

    def test_the_history_of_an_archived_item_is_read(self):
        from test_server import chrome
        with chrome() as cdp:
            sid = self.visit(cdp)
            self.until(cdp, sid, "!!document.querySelector('#showArchived')", "the pill")
            click(cdp, sid, "#showArchived")
            self.until(cdp, sid, "document.querySelectorAll('#archived-list tr.arch').length === 2", "the rows")
            click(cdp, sid, f"#archived-list tr[data-id='{self.gone[0]}']")
            self.until(cdp, sid, "!!document.querySelector('#peek [data-pk-tab=activity]')", "the tabs")
            click(cdp, sid, "#peek [data-pk-tab=activity]")
            self.until(cdp, sid, "document.querySelector('#peek [data-activity-missing]') || document.querySelector('#peek [data-activity-row]')", "the history")
            self.assertFalse(cdp.js("!!document.querySelector('#peek [data-activity-missing]')", sid), "the history is read, not 'not in the open lists'")

    def test_restore_in_the_peek_puts_the_item_back_and_undo_archives_it_again(self):
        from test_server import chrome
        with chrome() as cdp:
            sid = self.visit(cdp)
            self.until(cdp, sid, "!!document.querySelector('#showArchived')", "the pill")
            click(cdp, sid, "#showArchived")
            self.until(cdp, sid, "document.querySelectorAll('#archived-list tr.arch').length === 2", "the rows")
            click(cdp, sid, f"#archived-list tr[data-id='{self.gone[0]}']")
            self.until(cdp, sid, "!!document.querySelector('#pkRestore')", "Restore")
            before = self.steps()
            click(cdp, sid, "#pkRestore")
            self.until(cdp, sid, f"!!document.querySelector('#work-list tr[data-id=\"{self.gone[0]}\"]')", "the restored row in the table")
            self.assertEqual(self.archived_flags(), {self.gone[0]: 0, self.gone[1]: 1})
            self.assertEqual(self.steps(), before + 1, "one step, one Undo")
            self.until(cdp, sid, "!document.querySelector('#peek[data-archived]') && !!document.querySelector('#peek')", "the peek shows it as a live item")
            self.assertEqual(cdp.js("document.querySelectorAll('#pkRestore').length", sid), 0)
            self.until(cdp, sid, "document.querySelector('#showArchived').textContent.trim() === 'Show archived 1'", "the count")
            self.assertIn(f"{self.gone[0]} restored.", cdp.js("document.querySelector('.toast-text').textContent", sid))
            click(cdp, sid, ".toast [data-undo]")
            self.until(cdp, sid, "document.querySelector('#showArchived').textContent.trim() === 'Show archived 2'", "the count after Undo")
            self.assertEqual(self.archived_flags(), {self.gone[0]: 1, self.gone[1]: 1})

    def test_the_peek_has_no_restore_in_view(self):
        from test_server import chrome
        with chrome() as cdp:
            sid = self.visit(cdp, edit=False)
            self.until(cdp, sid, "!!document.querySelector('#showArchived')", "the pill")
            click(cdp, sid, "#showArchived")
            self.until(cdp, sid, "document.querySelectorAll('#archived-list tr.arch').length === 2", "the rows")
            click(cdp, sid, f"#archived-list tr[data-id='{self.gone[0]}']")
            self.until(cdp, sid, "!!document.querySelector('#peek[data-archived]')", "the archived peek")
            self.assertEqual(cdp.js("document.querySelectorAll('#pkRestore').length", sid), 0, "View changes nothing")
            self.assertIn("Switch to Edit to restore it", cdp.js("document.querySelector('#peek .pk-saved').textContent", sid))

    def test_a_published_file_has_no_show_archived_and_no_archived_row(self):
        from test_server import chrome, wait
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        out = Path(publish.publish(self.store, "ABC", folder, by_user=USER, now="2026-10-29", branding=tempfile.mkdtemp())["path"])
        html = out.read_text(encoding="utf-8")
        self.assertNotIn("Show archived", html)
        self.assertNotIn("pkRestore", html)
        for ref in self.gone:
            self.assertNotIn(ref, html)
        with chrome() as cdp:
            from test_work_items import page_target
            sid = page_target(cdp)
            cdp.call("Page.enable", {}, sid)
            cdp.call("Page.navigate", {"url": out.as_uri()}, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
            cdp.js("[...document.querySelectorAll('.tab')].find(t => /Work items/.test(t.textContent)).click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#work h1')", sid)))
            self.assertEqual(cdp.js("document.querySelectorAll('#showArchived, #archived').length", sid), 0)

    def test_the_source_stays_in_the_edit_parts(self):
        src = SRC / "clark" / "page" / "src"
        self.assertTrue((src / "edit" / "ArchivedItems.jsx").is_file())
        self.assertNotIn("getArchived", (src / "components" / "WorkItems.jsx").read_text(encoding="utf-8"))
        self.assertFalse((src / "components" / "Peek.jsx").read_text(encoding="utf-8").count("restoreItem"), "Restore is the Edit part's")
        self.assertTrue((src / "edit" / "ArchivedPeek.jsx").is_file())
        self.assertIn("clark.showArchived", (src / "stores" / "archived.js").read_text(encoding="utf-8"), "the choice is remembered")
        self.assertNotIn("#showArchived", (src / "edit" / "edit.css").read_text(encoding="utf-8"))

    def test_the_activity_read_finds_an_archived_item_and_still_not_a_stranger(self):
        from clark import activity_read
        read = activity_read.make_read(self.store.path, self.store.data_for)
        got = read("ABC", self.gone[0])
        self.assertIsNotNone(got, "an archived item's history is read")
        self.assertIn("rows", got)
        self.assertIsNone(read("ABC", "ABC-A-999"))
        self.assertIsNone(read("ZZZ", self.gone[0]))


if __name__ == "__main__":
    unittest.main()
