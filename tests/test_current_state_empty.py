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
HINTS = default_sections.SECTION_HINTS
TITLES = ("Header", "This week", "Next week")                # items 1188, 1193, row 1266: the three default text sections that start empty (the first was called Current state)
IDS = dict(zip(TITLES, ("ABC-S-003", "ABC-S-004", "ABC-S-005")))
EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")
FIRST = "ABC-S-003"


def leaks(text):
    return [h for h in HINTS.values() if h in text]


def tearDownModule():
    shutil.rmtree(EMPTY_BRANDING, ignore_errors=True)


class Data(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store

    def say(self, body, title="Header"):
        with self.store.step("dashboard", USER) as st:
            st.update("report_sections", IDS[title], {"body": body})



    def built(self):
        return publish.build(self.store, "ABC", now="2030-01-15")

    def test_the_store_seeds_an_empty_body_and_the_line_is_kept_once_as_a_constant(self):
        first = next(s for s in self.store.data_for("ABC")["report_sections"] if s["id"] == FIRST)
        self.assertEqual((first["type"], first["title"], first["body"]), ("text", "Header", ""))
        self.assertTrue(LINE.startswith("Say where the project stands today"))

    def test_item_1193_new_project_seed_gives_all_four_text_sections_an_empty_body(self):
        """The first path: AFTER_NEW seeds a new project."""
        rows = {s["title"]: s for s in self.store.data_for("ABC")["report_sections"] if s["type"] == "text"}
        self.assertEqual(list(rows), list(TITLES))
        self.assertEqual({t: rows[t]["id"] for t in TITLES}, IDS)
        self.assertEqual([rows[t]["body"] for t in TITLES], [""] * 3)
        self.assertEqual(rows["This week"]["beside"], 1)
        self.assertNotIn("Summary", HINTS)      # row 1266: no default Summary
        self.assertEqual(HINTS["This week"], "List what was done this week, and what moved forward.")
        self.assertEqual(HINTS["Next week"], "List what is planned for next week, and who is doing it.")

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
        first = next(s for s in rows if s["type"] == "text" and s["title"] == "Header")
        self.assertEqual(first.get("body") or "", "")
        self.assertFalse([s for s in rows if LINE in (s.get("body") or "")])
        texts = {s["title"]: s.get("body") or "" for s in rows if s["type"] == "text"}
        self.assertEqual(texts, {t: "" for t in TITLES}, "item 1193: This week and Next week start empty on this path too")
        self.assertFalse([s for s in rows if leaks(s.get("body") or "")])

    def test_the_published_data_and_file_do_not_carry_the_line(self):
        built = self.built()
        first = next(s for s in built["published"]["sections"] if s["id"] == FIRST)
        self.assertEqual(first.get("body", ""), "", "an empty text section is published with an empty body, as any other")
        self.assertNotIn(LINE, built["body"].decode("utf-8"))
        self.assertNotIn("Say where the project stands", built["body"].decode("utf-8"))
        for t in TITLES:
            sec = next(s for s in built["published"]["sections"] if s["id"] == IDS[t])
            self.assertEqual(sec.get("body", ""), "", t)
        self.assertEqual(leaks(built["body"].decode("utf-8")), [], "item 1193: none of the guiding lines is in the published file")

    def test_the_page_source_omits_an_empty_text_section_from_a_file(self):
        dash = (ROOT / "src" / "clark" / "page" / "src" / "components" / "Dashboard.jsx").read_text(encoding="utf-8")
        self.assertIn('s.type === "text" ? !emptyBody(s.body)', dash)

    def test_word_leaves_the_empty_section_out_and_draws_it_once_it_has_words(self):
        heads = lambda: [b["text"] for b in docx_read.read(docx_build.build(self.built()["published"]), "r.docx").blocks if b["kind"] == "heading"]
        for t in TITLES:
            self.assertNotIn(t, heads())
        for t in TITLES:
            self.say("<p>Scanning is two thirds done.</p>", t)
            self.assertIn(t, heads())
            self.say("", t)
            self.assertNotIn(t, heads(), "clearing the words puts it back to nothing")

    def test_excel_cover_leaves_the_empty_section_out_and_draws_it_once_it_has_words(self):
        def lines():
            data = self.store.data_for("ABC")
            got = excel_cover.lines(project=data["project"], sections=data["report_sections"], tiles=[], exported="01-06-2030 20:30 (UTC+04:00)",
                                    by="Sam Example", owner="Kim Example", email="kim.example@example.com", internal="INTERNAL")
            return [x["text"] for x in got]
        for t in TITLES:
            self.assertNotIn(t, lines())
        self.assertEqual(leaks("\n".join(lines())), [])
        for t in TITLES:
            self.say("<p>Scanning is two thirds done.</p>", t)
            self.assertIn(t, lines())
            self.say("", t)
            self.assertNotIn(t, lines())
        self.say("<p>Done.</p>", "This week")
        self.say("<p>Planned.</p>", "Next week")
        got = [x for x in excel_cover.lines(project=self.store.data_for("ABC")["project"], sections=self.store.data_for("ABC")["report_sections"], tiles=[],
                                            exported="x", by="Sam Example", owner="Kim Example", email="kim.example@example.com", internal="") if x["kind"] == "pair"]
        self.assertEqual([(x["left"]["title"], x["right"]["title"]) for x in got], [("This week", "Next week")], "both written: drawn side by side")


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
            for t in TITLES[1:]:                                                                        # item 1193
                one = f"document.querySelector('[data-id=\"{IDS[t]}\"]')"
                self.assertEqual(cdp.js(f"{one}.querySelector('[data-rich=body] .quiet').textContent", sid), HINTS[t], f"Edit: the hint of {t}")
            cdp.js(f"{first}.querySelector('[data-rich=body]').click()", sid)           # it still opens the editor in place
            self.assertTrue(wait(lambda: cdp.js(f"!!{first}.querySelector('[contenteditable]')", sid), 15), "the editor opens")
        with store.step("dashboard", USER) as st:
            st.update("report_sections", "ABC-S-004", {"body": "<p>Some words</p>"})
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(shutil.rmtree, folder, True)
        done = publish.publish(store, "ABC", folder, by_user=USER, now="2026-10-28", branding=EMPTY_BRANDING)
        text = Path(done["path"]).read_text(encoding="utf-8")
        self.assertNotIn("Say where the project stands", text)
        self.assertEqual(leaks(text), [], "item 1193: no guiding line in the published file")
        with chrome() as cdp:
            tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
            cdp.call("Page.navigate", {"url": Path(done["path"]).as_uri()}, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.sec')", sid), 15), "the file drew")
            self.assertEqual(cdp.js(f"document.querySelectorAll('[data-id=\"{FIRST}\"]').length", sid), 0, "the file does not draw the empty section")
            self.assertEqual(cdp.js("[...document.querySelectorAll('.sec-h')].some(e => e.textContent === 'Header')", sid), False)


if __name__ == "__main__":
    unittest.main()
