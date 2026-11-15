"""item 1188: the first default section, Current state, starts with an EMPTY body; its starting line is the editor's hint only.

Instruction text must never reach a client unedited. So the store seeds "", the page shows the line as the empty field's hint in Edit
(the build writes default_sections.CURRENT_STATE_PREFILL into the page), and every export treats the empty text body as nothing, as it
does for any empty text section: the published file (publish.py, and the page's fileDraws), the Word report (docx_build), the Excel
cover (excel_cover) and the page clark serves in View ("Nothing recorded.").

Run: python3 dev/run_tests.py test_current_state_empty    (the browser class needs the lock; without a browser it is skipped)
"""
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _demo import USER, DemoStore
from _paths import ROOT
from clark import default_sections, docx_build, docx_read, excel_cover, page, publish, server as sv
from test_page import navigate
from test_server import Running, chrome, wait

LINE = default_sections.CURRENT_STATE_PREFILL
EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")
FIRST = "ABC-S-001"


def tearDownModule():
    shutil.rmtree(EMPTY_BRANDING, ignore_errors=True)


class Data(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store

    def say(self, body):
        with self.store.step("dashboard", USER) as st:
            st.update("report_sections", FIRST, {"body": body})

    def built(self):
        return publish.build(self.store, "ABC", now="2030-01-15")

    def test_the_store_seeds_an_empty_body_and_the_line_is_kept_once_as_a_constant(self):
        first = next(s for s in self.store.data_for("ABC")["report_sections"] if s["id"] == FIRST)
        self.assertEqual((first["type"], first["title"], first["body"]), ("text", "Current state", ""))
        self.assertTrue(LINE.startswith("Say where the project stands today"))

    def test_an_older_project_with_no_section_rows_gets_the_empty_body_on_its_first_change(self):
        """The second path: seed_sections (the first change of a project made before the sections), not the new-project seed."""
        from clark import store as store_module
        with mock.patch.dict(store_module.AFTER_NEW, clear=True):
            with self.store.step("dashboard", USER) as st:
                st.create("projects", {"code": "OLD", "name": "Older Programme"})
        self.assertEqual(self.store.read("report_sections", "OLD"), [])
        with self.store.step("dashboard", USER) as st:
            st.seed_sections("OLD")
        rows = self.store.read("report_sections", "OLD")
        first = next(s for s in rows if s["type"] == "text" and s["title"] == "Current state")
        self.assertEqual(first.get("body") or "", "")
        self.assertFalse([s for s in rows if LINE in (s.get("body") or "")])

    def test_the_published_data_and_file_do_not_carry_the_line(self):
        built = self.built()
        first = next(s for s in built["published"]["sections"] if s["id"] == FIRST)
        self.assertEqual(first.get("body", ""), "", "an empty text section is published with an empty body, as any other")
        self.assertNotIn(LINE, built["body"].decode("utf-8"))
        self.assertNotIn("Say where the project stands", built["body"].decode("utf-8"))

    def test_the_page_source_omits_an_empty_text_section_from_a_file(self):
        dash = (ROOT / "src" / "clark" / "page" / "src" / "components" / "Dashboard.jsx").read_text(encoding="utf-8")
        self.assertIn('s.type === "text" ? !emptyBody(s.body)', dash)

    def test_word_leaves_the_empty_section_out_and_draws_it_once_it_has_words(self):
        heads = lambda: [b["text"] for b in docx_read.read(docx_build.build(self.built()["published"]), "r.docx").blocks if b["kind"] == "heading"]
        self.assertNotIn("Current state", heads())
        self.say("<p>Scanning is two thirds done.</p>")
        self.assertIn("Current state", heads())
        self.say("")
        self.assertNotIn("Current state", heads(), "clearing the words puts it back to nothing")

    def test_excel_cover_leaves_the_empty_section_out_and_draws_it_once_it_has_words(self):
        def lines():
            data = self.store.data_for("ABC")
            got = excel_cover.lines(project=data["project"], sections=data["report_sections"], tiles=[], exported="01-06-2030 20:30 (UTC+04:00)",
                                    by="Sam Example", owner="Kim Example", email="kim.example@example.com", internal="INTERNAL")
            return [x["text"] for x in got]
        self.assertNotIn("Current state", lines())
        self.assertNotIn(LINE, "\n".join(lines()))
        self.say("<p>Scanning is two thirds done.</p>")
        self.assertIn("Current state", lines())


class Browser(unittest.TestCase):
    def test_edit_shows_the_line_as_the_hint_view_says_nothing_recorded_and_the_file_does_not_draw_it(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        store = demo.store
        s = Running(data_for=store.data_for, page_html=lambda: page.page_html(EMPTY_BRANDING))
        self.addCleanup(s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)
        with chrome() as cdp:
            sid = navigate(cdp, s.port, "#dashboard&p=ABC")
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.sec').length > 0", sid), 15))
            first = f"document.querySelector('[data-id=\"{FIRST}\"]')"
            self.assertEqual(cdp.js(f"{first}.querySelector('.quiet').textContent", sid), "Nothing recorded.", "View")
            self.assertNotIn(LINE, cdp.js(f"{first}.textContent", sid))
            cdp.js("document.querySelector('[data-mode=edit]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('#report').dataset.mode === 'edit'", sid), 15))
            self.assertEqual(cdp.js(f"{first}.querySelector('[data-rich=body] .quiet').textContent", sid), LINE, "Edit: the hint")
            cdp.js(f"{first}.querySelector('[data-rich=body]').click()", sid)           # it still opens the editor in place
            self.assertTrue(wait(lambda: cdp.js(f"!!{first}.querySelector('[contenteditable]')", sid), 15), "the editor opens")
        with store.step("dashboard", USER) as st:
            st.update("report_sections", "ABC-S-006", {"body": "<p>Some words</p>"})
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(shutil.rmtree, folder, True)
        done = publish.publish(store, "ABC", folder, by_user=USER, now="2026-10-28", branding=EMPTY_BRANDING)
        text = Path(done["path"]).read_text(encoding="utf-8")
        self.assertNotIn("Say where the project stands", text)
        with chrome() as cdp:
            tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
            cdp.call("Page.navigate", {"url": Path(done["path"]).as_uri()}, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.sec')", sid), 15), "the file drew")
            self.assertEqual(cdp.js(f"document.querySelectorAll('[data-id=\"{FIRST}\"]').length", sid), 0, "the file does not draw the empty section")
            self.assertEqual(cdp.js("[...document.querySelectorAll('.sec-h')].some(e => e.textContent === 'Current state')", sid), False)


if __name__ == "__main__":
    unittest.main()
