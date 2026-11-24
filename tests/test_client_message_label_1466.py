"""Row 1466: "Client wording" is now "Client Message" wherever a person reads it (the peeks, the table columns, the data card, the
Excel header, Help, the raid card source), and a published file never draws the "Client visible" or "Client not visible" line or its eye.
Local View and Edit keep the line (test_client_line_1256c). The import still reads the old header "Client wording" (test_excel_import_names).
Run: CLARK_CHROME=/usr/local/bin/creaite-chrome python3 dev/run_tests.py test_client_message_label_1466
"""
import re
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT

import test_peek_ruled_1077 as base  # noqa: E402

from clark import excel, page  # noqa: E402
from openpyxl import load_workbook  # noqa: E402
from test_excel_import_names import NameCase  # noqa: E402
import test_publish as tp  # noqa: E402
from test_server import chrome, wait  # noqa: E402

OLD = re.compile(r"client wording", re.I)
HELP = ROOT / "src/clark/page/src/help/helpContent.json"


class Words(unittest.TestCase):
    def test_no_client_wording_in_built_pages_and_help(self):          # AP4
        for view in (True, False):
            with self.subTest(view=view):
                html = page.page_html(tp.EMPTY_BRANDING, view=view)
                hit = OLD.search(html)
                self.assertIsNone(hit, "Client wording is on a built page" + (": " + html[hit.start() - 60:hit.end() + 40] if hit else ""))
                self.assertIn("Client Message", html)
        text = HELP.read_text(encoding="utf-8")
        self.assertIsNone(OLD.search(text), "Client wording is in Help")
        self.assertIn("Client Message", text)

    def test_the_spelling_is_exactly_client_message_wherever_a_person_reads_it(self):          # ruling 1466: capital M, nothing else
        """Every "client message" in the built pages and Help, in any case, is "Client Message" (the one other form is the milestone box's
        placeholder "Add client message", a sentence); the Excel headers, the history label and the raid card words use the same spelling."""
        loose = re.compile(r"client message", re.I)
        for name, text in (("page", page.page_html(tp.EMPTY_BRANDING, view=False)), ("view page", page.page_html(tp.EMPTY_BRANDING, view=True)),
                           ("Help", HELP.read_text(encoding="utf-8"))):
            for m in loose.finditer(text):
                with self.subTest(where=name, at=m.start()):
                    self.assertTrue(m.group(0) == "Client Message" or text[max(0, m.start() - 4):m.start()] == "Add ", text[m.start() - 30:m.end() + 20])
        from clark import history
        from clark.section_kinds import raid3
        for table in ("actions", "raid", "decisions", "milestones"):
            self.assertEqual(history.field_name(table, "client_message"), "Client Message")
            self.assertIn("Client Message", excel.COLUMN_OF[table])
            self.assertEqual([k for k in excel.COLUMN_OF[table] if k.lower() == "client message"], ["Client Message"])
        for words in (raid3.BAD_SOURCE, raid3.NO_LATEST):
            self.assertEqual([m.group(0) for m in loose.finditer(words)], ["Client Message"])

    def test_the_history_label_for_client_message_is_client_message(self):
        from clark import history
        for table in ("actions", "raid", "decisions", "milestones"):
            with self.subTest(table=table):
                self.assertEqual(history.field_name(table, "client_message"), "Client Message")

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

    def test_published_file_has_no_client_visible_or_eye(self):
        _plant, _pub, text = tp.made()
        folder = Path(tempfile.mkdtemp(prefix="clark-1466-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(str(folder), ignore_errors=True))
        path = folder / "report.html"
        path.write_text(text, encoding="utf-8")
        for width, dark in ((1400, False), (900, False), (1400, True), (900, True)):
            for hash_, who in (("#work&p=PUB&item=PUB-A-001", "action"), ("#work&p=PUB&item=PUB-001", "risk"),
                               ("#work&p=PUB&item=PUB-D-001", "decision"), ("#dashboard&p=PUB&ms=PUB-M-001", "milestone")):
                with self.subTest(width=width, dark=dark, kind=who), chrome() as cdp:
                    sid = tp.opened(cdp, path.as_uri() + hash_, width)
                    if dark:
                        cdp.js("document.documentElement.dataset.theme = 'dark'", sid)
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

    def published(self):
        _plant, _pub, text = tp.made()
        folder = Path(tempfile.mkdtemp(prefix="clark-1466-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(str(folder), ignore_errors=True))
        path = folder / "report.html"
        path.write_text(text, encoding="utf-8")
        return path

    KINDS = (("#work&p=PUB&item=PUB-A-001", "action"), ("#work&p=PUB&item=PUB-001", "risk"),
             ("#work&p=PUB&item=PUB-D-001", "decision"), ("#dashboard&p=PUB&ms=PUB-M-001", "milestone"))
    OPEN = ("(() => { const d = document.querySelector('#peek [data-pk-details]'); if (d && d.getAttribute('aria-expanded') !== 'true') d.click(); })()")
    VISIBLE = r"(?i)client[ -]?(not )?visible|(not )?visible to (the )?client|(not )?shown to (the )?client"

    def test_published_file_no_client_visibility_words_anywhere(self):          # AP6
        """Every page of the published file (Dashboard, Work, Use cases, and the peek of each kind) is read as a person reads it: no words about client visibility, no eye."""
        path = self.published()
        pages = [("#dashboard&p=PUB", "dashboard"), ("#work&p=PUB", "work"), ("#usecases&p=PUB&uc=1.1", "use case")] + list(self.KINDS)
        for width in (1400, 900):
            for hash_, who in pages:
                with self.subTest(width=width, page=who), chrome() as cdp:
                    sid = tp.opened(cdp, path.as_uri() + hash_, width)
                    self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"))
                    if who in ("action", "risk", "decision", "milestone"):
                        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek .pk-fields dt')", sid)), "the peek drew")
                        cdp.js(self.OPEN, sid)
                    self.assertGreater(len(cdp.js("document.body.innerText", sid)), 50, "the page drew text")
                    self.assertNotRegex(cdp.js("document.body.innerText", sid), self.VISIBLE)
                    self.assertEqual(cdp.js("document.querySelectorAll('.cv, .ucd-eye, [data-eye], [data-pk-client-row], [data-pk-client-read], [data-pk-client], svg[data-icon=eye], svg[data-icon=eyeoff]').length", sid), 0)

    def test_published_peek_layout_unchanged_1400_900(self):          # AP8
        """Taking the line out leaves no empty row: every row of the Details body has a label and a value, none is the line's label-less row,
        and the rows are the same at 1400 and 900 (the ticket gives no spec for the layout; only the absence of a gap is pinned)."""
        path = self.published()
        allowed = {"Workstream", "Milestone", "Use case", "Raised", "Description", "Agreed date", "Forecast date", "Achieved on", "Reasoning", "Options considered",
                   "Revisit", "Replaces", "Latest update", "Client Message"}
        rows = ("[...document.querySelectorAll('#peek .pk-fields .pk-row')].map(r => { const dt = r.querySelector('dt'), dd = r.querySelector('dd');"
                " return [dt ? dt.textContent.trim() : null, dd ? dd.textContent.trim() : null, r.getBoundingClientRect().height]; })")
        for hash_, who in self.KINDS:
            seen = {}
            for width in (1400, 900):
                with self.subTest(kind=who, width=width), chrome() as cdp:
                    sid = tp.opened(cdp, path.as_uri() + hash_, width)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek .pk-fields dt')", sid)), "the peek drew")
                    cdp.js(self.OPEN, sid)
                    self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#peek .pk-fields .pk-row').length", sid) > 0))
                    got = cdp.js(rows, sid)
                    for label, value, height in got:
                        self.assertIsNotNone(label, "a row with no label is an empty gap row (the removed line was one)")
                        self.assertIn(label, allowed)
                        self.assertTrue(value, f"row {label} has a value")
                        self.assertGreater(height, 10)
                    self.assertEqual(cdp.js("document.querySelectorAll('#peek .pk-row:not(:has(dt))').length", sid), 0)
                    seen[width] = [r[0] for r in got]
            self.assertEqual(seen[1400], seen[900], who)


class Import(NameCase):
    def read_with(self, header):
        self.rename(None, Actions=("Client Message", header), **{"RAID": ("Client Message", header)})
        self.edit("Actions", self.a1, header, "Plan is on its way")
        self.edit("RAID", self.r1, header, "Still watching")
        p = self.read()
        self.assertEqual(p.problems, [])
        return {(c.table, c.id): c.after for c in p.changes}

    def test_import_old_header_client_wording_still_fills_client_message(self):          # AP3
        got = self.read_with("Client wording")
        self.assertEqual(got[("actions", self.a1)], {"client_message": "Plan is on its way"})
        self.assertEqual(got[("raid", self.r1)], {"client_message": "Still watching"})

    def test_import_new_header_client_message(self):          # AP3
        heads = [c.value for c in load_workbook(str(self.path))["Actions"][1]]
        self.assertIn("Client Message", heads)
        got = self.read_with("Client Message")
        self.assertEqual(got[("actions", self.a1)], {"client_message": "Plan is on its way"})
        self.assertEqual(got[("raid", self.r1)], {"client_message": "Still watching"})


class Labels(base.Peeks):
    LINE = "(e => e ? { tag: e.tagName, text: e.textContent.trim(), eye: !!e.querySelector('svg') } : null)(document.querySelector('#peek [data-pk-client-row] .cv'))"
    CLIENT = "client_visible"

    def test_view_and_edit_keep_client_visible_line_with_undo(self):          # AP7
        on, off = "TUL-007", "TUL-008"
        with self.store.step("dashboard", "Demo User") as st:
            st.update("raid", off, {self.CLIENT: 0})
        for width in (1400, 900):
            for ref, text in ((on, "Client visible"), (off, "Client not visible")):
                with self.subTest(width=width, ref=ref, mode="view"), chrome() as cdp:
                    sid = self.dashboard_in_view(cdp, width, self.store, self.code)
                    self.open_peek(cdp, sid, ref, "item")
                    self.assertTrue(wait(lambda: cdp.js(self.LINE, sid) is not None), "the line drew in View")
                    got = cdp.js(self.LINE, sid)
                    self.assertEqual((got["text"], got["tag"], got["eye"]), (text, "SPAN", True))
            with self.subTest(width=width, mode="edit"), chrome() as cdp:
                sid = self.dashboard_in_view(cdp, width, self.store, self.code)
                self.to_edit(cdp, sid)
                self.open_peek(cdp, sid, on, "item")
                self.assertTrue(wait(lambda: cdp.js(self.LINE, sid) is not None), "the line drew in Edit")
                self.assertEqual(cdp.js(self.LINE, sid)["tag"], "BUTTON")
                self.assertEqual(cdp.js(self.LINE, sid)["text"], "Client visible")
                cdp.js("document.querySelector('#peek [data-pk-client-row] .cv').click()", sid)
                self.assertTrue(wait(lambda: cdp.js(self.LINE, sid)["text"] == "Client not visible"), "one click changes it")
                self.assertTrue(wait(lambda: not self.store.read("raid", ref=on)[self.CLIENT]), "and the change is saved")
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.toast [data-undo]')", sid)), "the toast offers Undo")
                cdp.js("document.querySelector('.toast [data-undo]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js(self.LINE, sid)["text"] == "Client visible"), "Undo puts it back")
                self.assertTrue(wait(lambda: bool(self.store.read("raid", ref=on)[self.CLIENT])), "and saved again")


if __name__ == "__main__":
    unittest.main()
