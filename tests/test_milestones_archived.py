"""C-M4, Show archived on Milestones: a button with the count of the project's archived milestones, an Archived box of read-only
rows (name, the word Archived, agreed date, work items still linked) with Restore as the only action, Restore and Undo against the
real change route; a failed read never shows a count of 0; a project change clears the rows; a published file has none of it.

Run: python3 dev/run_tests.py test_milestones_archived
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
PILL = "#ms-archived-pill"
ROWS = "#ms-archived-list .ma-row"
PAGE_SRC = SRC / "clark" / "page" / "src"


class Archived(Base):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            self.dated = self.id_of_ms("Go live")
            self.undated = st.create("milestones", {"project": "ABC", "name": "Hand over the keys", "source": "demo"})
            st.create("projects", {"code": "XYZ", "name": "Second Programme", "health": "On track"})
            st.create("milestones", {"project": "XYZ", "name": "Other launch", "baseline_date": "2030-09-01", "source": "demo"})
            st.create("milestones", {"project": "XYZ", "name": "Other cleanup", "baseline_date": "2030-10-01", "source": "demo"})
        self.other_gone = [r["id"] for r in self.query("SELECT id FROM milestones WHERE project = 'XYZ' ORDER BY id")]
        self.gone = [self.dated, self.undated]
        with self.store.step("dashboard", USER) as st:
            for ref in self.gone + self.other_gone[:1]:
                st.archive("milestones", ref)

    def id_of_ms(self, name):
        return self.query("SELECT id FROM milestones WHERE name = ?", name)[0]["id"]

    def flags(self):
        return {r: self.query("SELECT archived FROM milestones WHERE id = ?", r)[0][0] for r in self.gone}

    def scheme(self, cdp, sid, scheme):
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)

    def go(self, cdp, width=1400, edit=True, project="ABC"):
        return self.visit(cdp, width=width, hash_=f"#milestones&p={project}", edit=edit, wait_for=".msv, [data-no-milestones]")

    def pill(self, cdp, sid):
        return cdp.js(f"(document.querySelector('{PILL}') || {{}}).textContent || null", sid)

    def test_the_pill_counts_and_the_box_is_read_only_with_the_words(self):
        from test_server import chrome
        for width, scheme in VARIANTS:
            with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                sid = self.go(cdp, width)
                self.scheme(cdp, sid, scheme)
                self.until(cdp, sid, f"!!document.querySelector('{PILL}')", "the Show archived button")
                self.assertEqual(self.pill(cdp, sid), "Show archived (2)")
                self.assertEqual(cdp.js(f"document.querySelector('{PILL}').tagName", sid), "BUTTON")
                self.assertEqual(cdp.js(f"document.querySelector('{PILL}').getAttribute('aria-pressed')", sid), "false")
                self.assertFalse(cdp.js(f"document.querySelector('{PILL}').hasAttribute('aria-controls')", sid), "no aria-controls while the list is off")
                self.assertFalse(cdp.js("!!document.querySelector('#ms-archived-list')", sid), "the box is shut until asked for")
                self.assertFalse(cdp.js("document.querySelector('.msv').textContent.includes('Go live')", sid), "an archived milestone is not on the Plan")
                off = cdp.js(f"(() => {{ const s = getComputedStyle(document.querySelector('{PILL}')); return [s.backgroundColor, s.borderTopColor, s.fontWeight].join('|'); }})()", sid)
                click(cdp, sid, PILL)
                self.until(cdp, sid, f"document.querySelectorAll('{ROWS}').length === 2", "the archived rows")
                self.assertEqual(cdp.js(f"document.querySelector('{PILL}').getAttribute('aria-pressed')", sid), "true")
                self.assertEqual(cdp.js(f"document.querySelector('{PILL}').getAttribute('aria-controls')", sid), "ms-archived-list")
                on = cdp.js(f"(() => {{ const s = getComputedStyle(document.querySelector('{PILL}')); return [s.backgroundColor, s.borderTopColor, s.fontWeight].join('|'); }})()", sid)
                self.assertNotEqual(on, off, "the pressed state looks different")
                self.assertEqual(cdp.js(f"getComputedStyle(document.querySelector('{PILL}'), '::before').content", sid), '"✓"', "and a mark, not colour alone")
                self.assertIn("Archived 2 milestones", cdp.js("document.querySelector('#ms-archived-list .ma-h').textContent.replace(/\\s+/g, ' ')", sid))
                self.assertEqual(cdp.js("[...document.querySelectorAll('#ms-archived-list .tag')].map(t => t.textContent).join()", sid), "Archived,Archived")
                said = cdp.js(f"[...document.querySelectorAll('{ROWS}')].map(r => r.dataset.id + '|' + r.querySelector('.ma-name').textContent + '|' + r.querySelector('.ma-meta').textContent)", sid)
                self.assertIn(f"{self.dated}|Go live|Agreed 01-06-2030 · 1 work item still linked", said)
                self.assertIn(f"{self.undated}|Hand over the keys|No agreed date · 0 work items still linked", said)
                self.assertEqual(cdp.js("document.querySelectorAll('#ms-archived input, #ms-archived select, #ms-archived textarea, #ms-archived [contenteditable]').length", sid), 0)
                self.assertEqual(cdp.js("[...document.querySelectorAll('#ms-archived-list button')].map(b => b.textContent).join()", sid), "Restore,Restore", "Restore is the only action")
                self.assertFalse(cdp.js("document.documentElement.scrollWidth > window.innerWidth", sid), "no sideways scroll")
                click(cdp, sid, PILL)
                self.until(cdp, sid, "!document.querySelector('#ms-archived-list')", "the box shut again")

    def test_view_shows_the_rows_but_offers_no_restore(self):
        from test_server import chrome
        with chrome() as cdp:
            sid = self.go(cdp, edit=False)
            self.until(cdp, sid, f"!!document.querySelector('{PILL}')", "the button in View")
            click(cdp, sid, PILL)
            self.until(cdp, sid, f"document.querySelectorAll('{ROWS}').length === 2", "the rows")
            self.assertEqual(cdp.js("document.querySelectorAll('#ms-archived-list button, [data-edit-only]').length", sid), 0)
            self.assertIn("switch to Edit", cdp.js("document.querySelector('#ms-archived-list').textContent", sid))

    def test_restore_puts_the_milestone_back_with_one_undo_and_focus_goes_to_the_button(self):
        from test_server import chrome
        with chrome() as cdp:
            sid = self.go(cdp)
            click(cdp, sid, PILL)
            self.until(cdp, sid, f"document.querySelectorAll('{ROWS}').length === 2", "the rows")
            self.assertEqual(cdp.js(f"document.querySelector('{ROWS}[data-id=\"{self.dated}\"] .ma-restore').getAttribute('aria-label')", sid), "Restore Go live")
            before = self.steps()
            click(cdp, sid, f"{ROWS}[data-id='{self.dated}'] .ma-restore")
            self.until(cdp, sid, f"document.querySelector('.msv').textContent.includes('Go live')", "the restored milestone on the Plan")
            self.assertEqual(self.flags(), {self.dated: 0, self.undated: 1})
            self.assertEqual(self.steps(), before + 1, "one step, one Undo")
            self.until(cdp, sid, f"document.querySelector('{PILL}').textContent === 'Show archived (1)'", "the count")
            self.assertEqual(cdp.js("document.querySelectorAll('#ms-archived-list .ma-row').length", sid), 1)
            self.assertIn("Go live restored.", cdp.js("document.querySelector('.toast-text').textContent", sid))
            self.until(cdp, sid, f"document.activeElement && document.activeElement.id === 'ms-archived-pill'", "focus on the button")
            click(cdp, sid, ".toast [data-undo]")
            self.until(cdp, sid, f"document.querySelector('{PILL}').textContent === 'Show archived (2)'", "the count after Undo")
            self.assertEqual(self.flags(), {self.dated: 1, self.undated: 1})
            self.assertFalse(cdp.js("document.querySelector('.msv').textContent.includes('Go live')", sid), "gone from the Plan again")
            for ref in self.gone:
                click(cdp, sid, f"{ROWS}[data-id='{ref}'] .ma-restore")
                self.until(cdp, sid, f"document.querySelector('{PILL}').textContent === 'Show archived ({1 if ref == self.gone[0] else 0})'", "the count")
            self.until(cdp, sid, "document.querySelector('#ms-archived-list').textContent.includes('No archived milestones.')", "the empty words")

    def test_a_failed_read_never_says_zero_and_keeps_the_last_good_rows(self):
        from test_server import chrome
        real, down = self.s.httpd.data_for, {"on": False}

        def data_for(code, archived="hide"):
            if archived == "only" and down["on"]:
                raise RuntimeError("the read failed")
            return real(code, archived=archived)
        self.s.httpd.data_for = data_for
        with chrome() as cdp:
            down["on"] = True
            sid = self.go(cdp)
            self.until(cdp, sid, "!!document.querySelector('.msv')", "the Plan")
            import time
            time.sleep(1.5)
            self.assertFalse(cdp.js(f"!!document.querySelector('{PILL}')", sid), "no button, so no false count, when the first read fails")
            self.assertNotIn("(0)", cdp.js("document.querySelector('#milestones').textContent", sid))
            down["on"] = False
            cdp.call("Page.reload", {}, sid)
            self.until(cdp, sid, "!!document.querySelector('.msv') && !!document.querySelector('[data-mode=edit]')", "the Plan after a reload")
            cdp.js("document.querySelector('[data-mode=edit]').click()", sid)
            self.until(cdp, sid, f"!!document.querySelector('{PILL}')", "the button once the read works")
            click(cdp, sid, PILL)
            self.until(cdp, sid, f"document.querySelectorAll('{ROWS}').length === 2", "the rows")
            down["on"] = True
            click(cdp, sid, f"{ROWS}[data-id='{self.dated}'] .ma-restore")
            self.until(cdp, sid, "document.querySelector('.msv').textContent.includes('Go live')", "the restored milestone")
            time.sleep(1.5)
            self.assertEqual(self.pill(cdp, sid), "Show archived (2)", "the rows last read stay while the read fails")
            self.assertEqual(cdp.js(f"document.querySelectorAll('{ROWS}').length", sid), 2)

    def test_a_project_change_clears_the_rows(self):
        from test_server import chrome
        with chrome() as cdp:
            sid = self.go(cdp)
            click(cdp, sid, PILL)
            self.until(cdp, sid, f"document.querySelectorAll('{ROWS}').length === 2", "the rows")
            cdp.js("location.hash = '#milestones&p=XYZ'", sid)
            self.until(cdp, sid, f"document.querySelector('{PILL}') && document.querySelector('{PILL}').textContent === 'Show archived (1)'", "the other project's count")
            self.until(cdp, sid, f"document.querySelectorAll('{ROWS}').length === 1", "its one row")
            text = cdp.js("document.querySelector('#ms-archived').textContent", sid)
            self.assertIn("Other launch", text)
            self.assertNotIn("Go live", text)
            self.assertNotIn("Hand over the keys", text)

    def test_a_published_file_has_no_show_archived_and_no_archived_milestone(self):
        from test_server import chrome, wait
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        out = Path(publish.publish(self.store, "ABC", folder, by_user=USER, now="2026-10-29", branding=tempfile.mkdtemp())["path"])
        html = out.read_text(encoding="utf-8")
        for never in ("Show archived", "Hand over the keys", "ms-archived", "No archived milestones"):
            self.assertNotIn(never, html)
        self.assertNotIn("Go live", html)
        with chrome() as cdp:
            from test_work_items import page_target
            sid = page_target(cdp)
            cdp.call("Page.enable", {}, sid)
            cdp.call("Page.navigate", {"url": out.as_uri()}, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
            cdp.js("[...document.querySelectorAll('.tab')].find(t => /Milestones/.test(t.textContent)).click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#milestones h1')", sid)))
            self.assertEqual(cdp.js("document.querySelectorAll('#ms-archived, #ms-archived-pill').length", sid), 0)
            self.assertNotIn("Go live", cdp.js("document.querySelector('#milestones').textContent", sid))

    def test_the_source_stays_in_the_edit_parts_and_no_archived_row_reaches_the_plan(self):
        self.assertTrue((PAGE_SRC / "edit" / "ArchivedMilestones.jsx").is_file())
        view = (page.__file__ and Path(page.__file__).with_name("page-view.html")).read_text(encoding="utf-8")
        for never in ("getArchivedMilestones", "ms-archived-list", "restoreMilestone"):
            self.assertNotIn(never, view)
        block = (PAGE_SRC / "edit" / "ArchivedMilestones.jsx").read_text(encoding="utf-8")
        self.assertNotIn("data.value =", block, "the archived rows are never merged into the page's data")
        self.assertIn("archived=only", (PAGE_SRC / "api.js").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
