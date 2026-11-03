"""B-5 and #450 row 38, Show archived on Work items: a pill in the Work items bar with the count, remembered for each project
across a reload, archived rows read only (Restore is in the archived peek, row 39), Restore and Undo against the
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
                self.assertEqual(cdp.js("document.querySelector('#showArchived').textContent", sid), "Show archived 2")
                self.assertTrue(cdp.js("!!document.querySelector('#work .wbar .vctl #showArchived')", sid), "the pill is in the Work items bar")
                self.assertTrue(cdp.js("(() => { const p = document.querySelector('#showArchived'), v = p.nextElementSibling; return !!v && !!document.querySelector('#work .wbar .vctl') && p.parentElement === v.parentElement; })()", sid), "the pill sits before View, as in the prototype")
                self.assertFalse(cdp.js("!!document.querySelector('#archived-list')", sid), "the list is shut until asked for")
                self.assertEqual(cdp.js("document.querySelector('#showArchived').getAttribute('aria-pressed')", sid), "false")
                self.assertFalse(cdp.js("!!document.querySelector('#work-list tr[data-id=\"%s\"]')" % self.gone[0], sid), "an archived row is not in the table")
                click(cdp, sid, "#showArchived")
                self.until(cdp, sid, "document.querySelectorAll('#archived-list .arch-row').length === 2", "the archived rows")
                self.assertEqual(cdp.js("[...document.querySelectorAll('#archived-list .tag')].map(t => t.textContent).join()", sid), "Archived,Archived")
                self.assertEqual(cdp.js("document.querySelectorAll('#archived-list input, #archived-list select, #archived-list textarea, #archived-list [contenteditable], #archived-list button').length", sid), 0,
                                 "read only: Restore is in the peek (row 39), not on the row")
                self.assertFalse(cdp.js("document.documentElement.scrollWidth > window.innerWidth", sid), "no sideways scroll")

    def test_the_choice_is_remembered_for_the_project_across_a_reload(self):
        from test_server import chrome
        for width, scheme in VARIANTS:
            with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                sid = self.visit(cdp, width=width)
                self.scheme(cdp, sid, scheme)
                cdp.js("try { localStorage.removeItem('clark.workArchived.ABC'); } catch (e) {}", sid)
                cdp.call("Page.reload", {}, sid)
                self.until(cdp, sid, "!!document.querySelector('#showArchived')", "the pill")
                self.assertEqual(cdp.js("document.querySelector('#showArchived').getAttribute('aria-pressed')", sid), "false")
                off = cdp.js("getComputedStyle(document.querySelector('#showArchived')).backgroundColor", sid)
                click(cdp, sid, "#showArchived")
                self.until(cdp, sid, "document.querySelector('#showArchived').getAttribute('aria-pressed') === 'true'", "the pill on")
                self.until(cdp, sid, "!!document.querySelector('#archived-list')", "the list")
                on = cdp.js("getComputedStyle(document.querySelector('#showArchived')).backgroundColor", sid)
                self.assertNotEqual(on, off, "the pressed pill looks pressed")
                self.assertEqual(cdp.js("localStorage.getItem('clark.workArchived.ABC')", sid), "on")
                self.assertFalse(cdp.js("document.documentElement.scrollWidth > window.innerWidth", sid), "no sideways scroll")
                cdp.call("Page.reload", {}, sid)
                self.until(cdp, sid, "!!document.querySelector('#archived-list .arch-row')", "the list again after the reload")
                self.assertEqual(cdp.js("document.querySelector('#showArchived').getAttribute('aria-pressed')", sid), "true")
                self.assertEqual(cdp.js("document.querySelector('#showArchived').textContent", sid), "Show archived 2")
                click(cdp, sid, "#showArchived")
                self.until(cdp, sid, "!document.querySelector('#archived-list')", "the list shut")
                self.assertIsNone(cdp.js("localStorage.getItem('clark.workArchived.ABC')", sid))
                cdp.call("Page.reload", {}, sid)
                self.until(cdp, sid, "!!document.querySelector('#showArchived')", "the pill after the second reload")
                self.assertEqual(cdp.js("document.querySelector('#showArchived').getAttribute('aria-pressed')", sid), "false")
                self.assertFalse(cdp.js("!!document.querySelector('#archived-list')", sid))

    def test_restore_puts_the_item_back_and_undo_archives_it_again(self):
        from test_server import chrome
        with chrome() as cdp:
            sid = self.visit(cdp)
            click(cdp, sid, "#showArchived")
            self.until(cdp, sid, "document.querySelectorAll('#archived-list .arch-row').length === 2", "the rows")
            before = self.steps()
            click(cdp, sid, f"#archived-list tr[data-arch-id='{self.gone[0]}']")
            self.until(cdp, sid, "!!document.querySelector('#peek-archived #pk-restore')", "the archived peek")
            click(cdp, sid, "#peek-archived #pk-restore")
            self.until(cdp, sid, f"!!document.querySelector('#work-list tr[data-id=\"{self.gone[0]}\"]')", "the restored row in the table")
            self.assertEqual(self.archived_flags(), {self.gone[0]: 0, self.gone[1]: 1})
            self.assertEqual(self.steps(), before + 1, "one step, one Undo")
            self.until(cdp, sid, "document.querySelector('#showArchived').textContent === 'Show archived 1'", "the count")
            self.assertIn(f"{self.gone[0]} restored.", cdp.js("document.querySelector('.toast-text').textContent", sid))
            click(cdp, sid, ".toast [data-undo]")
            self.until(cdp, sid, "document.querySelector('#showArchived').textContent === 'Show archived 2'", "the count after Undo")
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
            self.assertEqual(cdp.js("document.querySelectorAll('#showArchived, #archived, .arch-pill, .arch-row').length", sid), 0)
            self.assertFalse(cdp.js("/Show archived/.test(document.body.textContent)", sid))

    def test_the_source_stays_in_the_edit_parts(self):
        src = SRC / "clark" / "page" / "src"
        self.assertTrue((src / "edit" / "ArchivedItems.jsx").is_file())
        work = (src / "components" / "WorkItems.jsx").read_text(encoding="utf-8")
        self.assertNotIn("getArchived", work)
        self.assertNotIn("workArchived", work, "the remembered choice is read in the Edit parts only")
        self.assertNotIn("localStorage", work)


if __name__ == "__main__":
    unittest.main()
