"""B-5, Show archived on Work items: a button with the count, archived rows read only with Restore, Restore and Undo against the
real change route; a published file has none of it (it carries no archived row).

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
        self.gone = [self.id_of("Book the training room"), self.id_of("Supplier slips")]
        with self.store.step("dashboard", USER) as st:
            for ref in self.gone:
                st.archive("actions" if "-A-" in ref else "raid", ref)

    def scheme(self, cdp, sid, scheme):
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)

    def archived_flags(self):
        return {r: self.row(r)["archived"] for r in self.gone}

    def test_the_pill_counts_and_the_list_is_read_only_with_restore(self):
        from test_server import chrome
        for width, scheme in VARIANTS:
            with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                self.scheme(cdp, sid, scheme)
                self.until(cdp, sid, "!!document.querySelector('#showArchived')", "the Show archived button")
                self.assertEqual(cdp.js("document.querySelector('#showArchived').textContent", sid), "Show archived (2)")
                self.assertFalse(cdp.js("!!document.querySelector('#archived-list')", sid), "the list is shut until asked for")
                self.assertFalse(cdp.js("!!document.querySelector('#work-list tr[data-id=\"%s\"]')" % self.gone[0], sid), "an archived row is not in the table")
                click(cdp, sid, "#showArchived")
                self.until(cdp, sid, "document.querySelectorAll('#archived-list .arch-row').length === 2", "the archived rows")
                self.assertEqual(cdp.js("[...document.querySelectorAll('#archived-list .tag')].map(t => t.textContent).join()", sid), "Archived,Archived")
                self.assertEqual(cdp.js("document.querySelectorAll('#archived-list input, #archived-list select, #archived-list textarea, #archived-list [contenteditable]').length", sid), 0)
                click(cdp, sid, f"#archived-list li[data-id='{self.gone[0]}'] .arch-open")
                self.until(cdp, sid, "!!document.querySelector('#archived-list .arch-read')", "the read-only fields")
                self.assertIn("Low", cdp.js("document.querySelector('#archived-list .arch-read').textContent", sid))
                self.assertFalse(cdp.js("document.documentElement.scrollWidth > window.innerWidth", sid), "no sideways scroll")

    def test_restore_puts_the_item_back_and_undo_archives_it_again(self):
        from test_server import chrome
        with chrome() as cdp:
            sid = self.visit(cdp)
            click(cdp, sid, "#showArchived")
            self.until(cdp, sid, "document.querySelectorAll('#archived-list .arch-row').length === 2", "the rows")
            before = self.steps()
            click(cdp, sid, f"#archived-list li[data-id='{self.gone[0]}'] .arch-restore")
            self.until(cdp, sid, f"!!document.querySelector('#work-list tr[data-id=\"{self.gone[0]}\"]')", "the restored row in the table")
            self.assertEqual(self.archived_flags(), {self.gone[0]: 0, self.gone[1]: 1})
            self.assertEqual(self.steps(), before + 1, "one step, one Undo")
            self.until(cdp, sid, "document.querySelector('#showArchived').textContent === 'Show archived (1)'", "the count")
            self.assertIn(f"{self.gone[0]} restored.", cdp.js("document.querySelector('.toast-text').textContent", sid))
            click(cdp, sid, ".toast [data-undo]")
            self.until(cdp, sid, "document.querySelector('#showArchived').textContent === 'Show archived (2)'", "the count after Undo")
            self.assertEqual(self.archived_flags(), {self.gone[0]: 1, self.gone[1]: 1})

    def test_a_published_file_has_no_show_archived_and_no_archived_row(self):
        from test_server import chrome, wait
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        out = Path(publish.publish(self.store, "ABC", folder, by_user=USER, now="2026-10-29", branding=tempfile.mkdtemp())["path"])
        html = out.read_text(encoding="utf-8")
        self.assertNotIn("Show archived", html)
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


if __name__ == "__main__":
    unittest.main()
