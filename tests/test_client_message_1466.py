"""Row 1466: "Client wording" is now "Client Message" wherever a person reads it (the peeks, the table columns, the data card, the
Excel header, Help, the raid card source), and a published file never draws the "Client visible" or "Client not visible" line or its eye.
Local View and Edit keep the line (test_client_line_1256c). The import still reads the old header "Client wording" (test_excel_import_names).
Run: CLARK_CHROME=/usr/local/bin/creaite-chrome python3 dev/run_tests.py test_client_message_1466
"""
import re
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT

from clark import excel, page  # noqa: E402
import test_publish as tp  # noqa: E402
from test_server import chrome, wait  # noqa: E402

OLD = re.compile(r"client wording", re.I)
HELP = ROOT / "src/clark/page/src/help/helpContent.json"


class Words(unittest.TestCase):
    def test_the_built_pages_say_client_message_and_never_client_wording(self):
        for view in (True, False):
            with self.subTest(view=view):
                html = page.page_html(tp.EMPTY_BRANDING, view=view)
                hit = OLD.search(html)
                self.assertIsNone(hit, "Client wording is on a built page" + (": " + html[hit.start() - 60:hit.end() + 40] if hit else ""))
                self.assertIn("Client Message", html)

    def test_the_history_label_for_client_message_is_client_message(self):
        from clark import history
        for table in ("actions", "raid", "decisions", "milestones"):
            with self.subTest(table=table):
                self.assertEqual(history.field_name(table, "client_message"), "Client Message")

    def test_the_row_editor_label_and_toasts_say_client_message_of(self):
        html = page.page_html(tp.EMPTY_BRANDING, view=False)
        for words in ("`Client Message of ${", "} changed.`", "} is back as it was.`"):
            with self.subTest(words=words):
                self.assertIn(words, html)
        self.assertNotIn("`Wording of ${", html)

    def test_help_says_client_message(self):
        text = HELP.read_text(encoding="utf-8")
        self.assertIsNone(OLD.search(text))
        self.assertIn("Client Message", text)

    def test_the_excel_export_headers_say_client_message(self):
        for table in ("actions", "raid", "decisions", "milestones"):
            with self.subTest(table=table):
                self.assertEqual(excel.COLUMN_OF[table].get("Client Message"), "client_message")
                self.assertNotIn("Client wording", excel.COLUMN_OF[table])

    def test_the_ask_clark_words_and_the_raid_card_source_say_client_message(self):
        from clark.section_kinds import raid3
        for words in (raid3.BAD_SOURCE, raid3.NO_LATEST):
            self.assertIn("Client Message", words)
            self.assertIsNone(OLD.search(words))


class Published(unittest.TestCase):
    """A published file (local mode and To client mode make the same file): no Client visible line, no Client not visible line, no eye."""
    GONE = ("document.querySelectorAll('#peek [data-pk-client-row], #peek [data-pk-client-read], #peek [data-pk-client], #peek .cv, "
            "#peek .cv svg').length")

    def test_no_item_kind_draws_the_line_or_the_eye(self):
        _plant, _pub, text = tp.made()
        folder = Path(tempfile.mkdtemp(prefix="clark-1466-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(str(folder), ignore_errors=True))
        path = folder / "report.html"
        path.write_text(text, encoding="utf-8")
        for width in (1400, 900):
            for hash_, who in (("#work&p=PUB&item=PUB-A-001", "action"), ("#work&p=PUB&item=PUB-001", "risk"),
                               ("#work&p=PUB&item=PUB-D-001", "decision"), ("#dashboard&p=PUB&ms=PUB-M-001", "milestone")):
                with self.subTest(width=width, kind=who), chrome() as cdp:
                    sid = tp.opened(cdp, path.as_uri() + hash_, width)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek .pk-fields dt')", sid)), "the published peek drew")
                    if cdp.js("!!document.querySelector('#peek [data-pk-details]')", sid) and cdp.js("document.querySelector('#peek [data-pk-details]').getAttribute('aria-expanded')", sid) != "true":
                        cdp.js("document.querySelector('#peek [data-pk-details]').click()", sid)
                    self.assertEqual(cdp.js(self.GONE, sid), 0)
                    shown = cdp.js("document.querySelector('#peek').innerText", sid)
                    self.assertNotRegex(shown, r"(?i)client (not )?visible")
                    self.assertNotRegex(shown, r"(?i)client wording")

    def test_the_use_case_page_draws_no_client_visible_line_or_eye(self):
        # Rule 2 names the use case too. Rule 1 has nothing to check there: the use-case page has no Client Message row (its words are the headline and the standing text).
        # The published file draws UseCaseFilePage (read only); the Edit page's .ucd-eye ("On the dashboard") is an Edit-only button, so the file must have no eye at all.
        _plant, _pub, text = tp.made()
        folder = Path(tempfile.mkdtemp(prefix="clark-1466-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(str(folder), ignore_errors=True))
        path = folder / "report.html"
        path.write_text(text, encoding="utf-8")
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = tp.opened(cdp, path.as_uri(), width)
                self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"))
                cdp.js("location.hash = '#usecases&p=PUB&uc=1.1'", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-ucf]')", sid)), "the published use-case page drew")
                shown = cdp.js("document.querySelector('[data-ucf]').innerText", sid)
                self.assertTrue(cdp.js("!!document.querySelector('[data-ucf-details]')", sid), "the Details card drew")
                self.assertNotRegex(shown, r"(?i)client (not )?visible")
                self.assertNotRegex(shown, r"(?i)client wording")
                self.assertEqual(cdp.js("document.querySelectorAll('[data-ucf] .ucd-eye, [data-ucf] [data-eye], [data-ucf] .ucf-eye, [data-ucf] [data-pk-client-row], "
                                        "[data-ucf] [data-pk-client-read], [data-ucf] [data-pk-client], [data-ucf] .cv').length", sid), 0)

    def test_the_built_published_page_has_no_client_visible_line_in_the_view_source(self):
        src = (ROOT / "src/clark/page/src/components/PeekActionBody.jsx").read_text(encoding="utf-8")
        self.assertIn("onFile ? null :", src, "the read-only line is left out for a published file")


if __name__ == "__main__":
    unittest.main()
