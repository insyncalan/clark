"""Row 1269, slice B: the Theme reaches the served page and the published web file only. Word and the client Excel workbook are the
same bytes with either Theme; the Draft email text, the web app manifest, the service worker and the offline page do not change.
Help says it in one sentence: The Theme changes the pages. Word, Excel and email files, and the installed app, keep clark’s own colours.
Fictional data only. Run: python3 dev/run_tests.py test_theme_other_outputs
"""
import re
import unittest
from pathlib import Path

import _paths  # noqa: F401
import _publish_fixture as fixture
from _demo import DemoStore
from clark import appfiles, docx_build, draft_email, excel_client, publish

SRC_CLARK = Path(_paths.SRC) / "clark"
THEMES = ("classic", "cards")
EMAIL = {"mode": "update_request", "name": "Dana Hart", "email": "dana@example.com", "own_domains": ["example.com"], "from": "Sam",
         "now": "2026-10-20 09:00", "project_names": {"ABC": "Example Programme"},
         "items": [{"id": "ABC-A-001", "kind": "actions", "project": "ABC", "text": "Send the plan", "due": "2026-10-15",
                    "owner": "Dana Hart", "status": "Open", "client_visible": 1}]}


class Outputs(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store

    def set_theme(self, value):
        with self.s.con:
            self.s.con.execute("UPDATE app_settings SET theme = ? WHERE id = 1", (value,))
        self.assertEqual(self.s.theme(), value)

    def under_each(self, make):
        """What `make()` gives under each Theme, as {theme: result}."""
        got = {}
        for t in THEMES:
            self.set_theme(t)
            got[t] = make()
        return got

    def selected(self):
        return publish.select(publish.read_inputs(self.s, "ABC", as_at="2030-01-15"))

    def test_word_is_the_same_bytes_with_either_theme(self):
        got = self.under_each(lambda: docx_build.build(self.selected()))
        self.assertTrue(got["classic"])
        self.assertEqual(got["classic"], got["cards"])

    def test_the_client_workbook_is_the_same_bytes_with_either_theme(self):
        got = self.under_each(lambda: excel_client.workbook_bytes(self.selected()))
        self.assertTrue(got["classic"])
        self.assertEqual(got["classic"], got["cards"])

    def test_word_and_workbook_from_the_plant_are_the_same_bytes_with_either_theme(self):
        def both():
            chosen = publish.select(fixture.inputs())
            return docx_build.build(chosen), excel_client.workbook_bytes(chosen)
        got = self.under_each(both)
        self.assertEqual(got["classic"], got["cards"])

    def test_the_published_file_carries_the_same_client_workbook_with_either_theme(self):
        def workbook_in_file():
            text = publish.build(self.s, "ABC", now="2030-01-15", number=1, workbook=True)["body"].decode("utf-8")
            found = re.search(r'"client_workbook":\s*\{[^}]*?"base64":\s*"([^"]*)"', text)
            self.assertIsNotNone(found)
            return found.group(1)
        got = self.under_each(workbook_in_file)
        self.assertTrue(got["classic"])
        self.assertEqual(got["classic"], got["cards"])

    def test_the_draft_email_is_the_same_with_either_theme(self):
        got = self.under_each(lambda: draft_email.build(dict(EMAIL)))
        self.assertTrue(got["classic"]["html"])
        self.assertEqual(got["classic"], got["cards"])


class AppFiles(unittest.TestCase):
    def test_manifest_service_worker_and_offline_page_do_not_read_the_theme(self):
        a = (appfiles.manifest_json(), appfiles.service_worker(), appfiles.offline_page("clark.command", False),
             appfiles.offline_page("clark.command", True))
        again = (appfiles.manifest_json(), appfiles.service_worker(), appfiles.offline_page("clark.command", False),
                 appfiles.offline_page("clark.command", True))
        self.assertEqual(a, again)

    def test_offline_page_colours_come_from_the_committed_tokens_not_a_theme(self):
        page = appfiles.offline_page("clark.command", False).decode("utf-8")
        self.assertNotIn('id="theme"', page)
        self.assertNotIn("prototype-2.0", page)
        self.assertNotIn("@", re.sub(r"[\w.-]+@[\w.-]+", "", re.sub(r"@(media|font-face|keyframes|import)", "", page)))

    def test_no_word_excel_email_or_app_file_source_names_the_theme(self):
        for name in ("docx_build", "docx_graphics", "docx_fullimage", "excel_client", "excel", "excel_cover", "excel_palette", "draft_email",
                     "draft_email_feed", "appfiles"):
            text = (SRC_CLARK / f"{name}.py").read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"\bimport theme\b|\btheme\.|from clark\.theme|clark import [^\n]*\btheme\b|\.theme\(\)", text), name)
        for name in ("sw.js", "offline.html"):
            text = (SRC_CLARK / "app" / name).read_text(encoding="utf-8")
            self.assertNotIn("prototype-2.0", text, name)
            self.assertNotIn('id="theme"', text, name)


if __name__ == "__main__":
    unittest.main()
