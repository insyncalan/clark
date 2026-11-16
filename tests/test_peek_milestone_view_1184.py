"""Row 1184: the milestone peek's redesign changes the editor, never what a client sees. In View (the Dashboard) and in a published file the
chips are read only (no tools), the rows are the client's rows, and none of the editor's new words reach the client.

What this pins, apart from test_peek_milestone_1184 (the editor) and test_milestone_peek_1078 (rows and flatness):
 - the published page (View bundle) carries none of the approved new words: the placeholder "What changed? Add the latest update...", "Add description",
   "Add workstream", "Select use case", "Add client wording", the hint "not shown to the client", the tooltip "Turn on Client visible to edit",
   "Cmd or Ctrl and Enter saves.", the progress blocks' tooltips and aria labels (10% ... 100%, "10 percent" ... "100 percent");
 - a file's chips are four spans (State, Owner, Progress, Forecast date) with the peek's own icons: no button, no tab stop, no popup, and a click or
   Enter opens nothing;
 - a file's milestone peek has no Use case row, no Client visible line, no Latest update box, no hint after Agreed date, no empty-row prompt;
 - a client's words stay: "Cmd or Ctrl and Enter saves." and "Client not visible" are the editor's (the work item's Details line says Client not visible
   only in Edit), so neither is in the milestone peek of a file or of View.
Run: python3 dev/run_tests.py test_peek_milestone_view_1184
Without a browser: the sources and the built View page. With headless Chrome (fails, never skips, without it): a published file and the Dashboard
in View, at 1400 and 900 px.
"""
import datetime
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from _demo import USER
from _paths import SRC
import _publish_fixture as fx

from clark import page, publish  # noqa: E402
from test_movement_page import GO_LIVE, PILOT, Base  # noqa: E402
from test_server import chrome, wait  # noqa: E402
import test_publish as tp  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
NEW_WORDS = [
    "What changed? Add the latest update", "Add description", "Add workstream", "Select use case", "Add client wording",
    "not shown to the client", "Turn on Client visible to edit", "Cmd or Ctrl and Enter saves.",
] + [f"{n} percent" for n in range(10, 101, 10)]
EDIT_HOOKS = ("data-ms-block", "data-ms-wording-off", "data-ms-wording-hint", "data-pk-ms-hint", "data-ms-ucs", "data-pk-latest-hint")      # the editor's module alone
CLIENT_ROWS = ["Description", "Agreed date", "Workstream", "Client wording"]      # row 1184: Forecast date is a chip, Latest update sits above Details, Achieved on only when achieved
CHIP_ORDER = ["state", "owner", "progress", "forecast"]
CHIPS = ("(() => Object.fromEntries([...document.querySelectorAll('#peek .pk-chips > [data-row]')].map(c => [c.dataset.row, { text: c.innerText.replace(/\\s+/g, ' ').trim(),"
         " icons: [...c.querySelectorAll('svg[data-icn]')].map(i => i.dataset.icn), sub: (c.querySelector('.pk-chip-sub') || {}).textContent || null, tag: c.tagName,"
         " late: c.classList.contains('late'), ro: c.classList.contains('ro'), label: c.getAttribute('aria-label') }])))()")
LABELS = "[...document.querySelectorAll('#peek [data-ms-fields] dt')].map(d => d.textContent.trim())"
PEEK_TEXT = "document.querySelector('#peek').innerText.replace(/\\s+/g, ' ')"
# everything a person could press, tab to, or that says it pops something up, anywhere in the peek except the toolbar's buttons (prev, next, wide, close), the resize edge and the Details fold
INERT = ("(() => { const sel = 'button, input, textarea, select, a[href], [contenteditable], [role=textbox], [role=combobox], [role=button], [role=slider], [tabindex], [aria-haspopup], [aria-expanded]';"
         " return [...document.querySelectorAll('#peek ' + sel.split(', ').join(', #peek '))].filter(e => !e.matches('.pkp-btn, .pk-edge') && !e.hasAttribute('data-pk-details') && !e.matches('.pk-title')).map(e => e.outerHTML.slice(0, 80)); })()")
POPS = "document.querySelectorAll('[data-pop], [role=dialog], [role=listbox], [role=menu], .popover').length"


TODAY = datetime.date.today()      # the page counts "overdue N days" from the browser's clock, so the dates below are set from today, never fixed
PAST, FUTURE = TODAY - datetime.timedelta(days=13), TODAY + datetime.timedelta(days=30)
shown = lambda d: d.strftime("%d-%m-%Y")


def view_page():
    return page.page_html(tp.EMPTY_BRANDING, view=True)


def file_with(mutate=None):
    plant = fx.load()
    if mutate:
        mutate(plant)
    pub = publish.select(fx.inputs(plant))
    return publish.render(pub, view_page(), plant["as_at"], pub["data"]["project"]["name"])


class Sources(unittest.TestCase):
    def test_the_published_page_carries_none_of_the_editors_new_words_or_hooks(self):
        text = view_page()
        for word in NEW_WORDS + list(EDIT_HOOKS):
            self.assertNotIn(word, text, f"{word!r} is the editor's alone: a published page must not carry it")
        self.assertNotIn("Draft with AI", text)

    def test_the_chip_row_in_a_file_is_drawn_with_no_tools_and_the_milestone_page_look_is_untouched(self):
        peek = (PAGE_SRC / "components" / "Peek.jsx").read_text(encoding="utf-8")
        self.assertIn("<MilestoneChips m={m} tools={tools} editing={msEditing} />", peek, "the chips are editable only when msEditing")
        self.assertRegex(peek, r"const msEditing = !!tools && !!tools\.MilestoneEdit && !fromFile\.value", "a file is never msEditing")
        chips = (PAGE_SRC / "components" / "PeekMilestoneChips.jsx").read_text(encoding="utf-8")
        self.assertIn("editing && tools && tools.PeekMsChipPop", chips, "no popover without the editing flag and the editor's tool")
        self.assertIn("editing && tools && tools.PeekChipLive", chips)
        for name in ("PeekMsLatest", "PeekMilestoneTitle", "RecordMore", "PeekMsUseCase"):
            self.assertNotIn(name, chips, "the shared chip row names no editor module")
        self.assertNotRegex(chips, r"from \"\.\./edit/", "the shared chip row imports nothing from the editor")
        self.assertIn("MsLatest && m ?", peek, "the Latest update box is the editor's (msEditing) alone")
        fields = peek[peek.index("function MilestoneFields"):peek.index("// The edge you drag")]
        self.assertNotIn("Use case", fields, "a file has no use case row")
        self.assertNotIn("Visible to client", fields)
        self.assertNotIn("Client visible", fields)
        self.assertNotIn("Toned", fields)
        for lst in ("MsList.jsx", "MsCalendar.jsx", "UseCaseFilePage.jsx"):
            self.assertIn("MsMark", (PAGE_SRC / "components" / lst).read_text(encoding="utf-8"), f"{lst} keeps the Milestones page's own marks (the client's lists)")

    def test_the_file_shows_latest_update_only_when_it_carries_one_and_above_details(self):
        peek = (PAGE_SRC / "components" / "Peek.jsx").read_text(encoding="utf-8")
        fields = peek[peek.index("function MilestoneFields"):peek.index("// The edge you drag")]
        self.assertLess(fields.index('name="Latest update"'), fields.index("<PeekDetails"), "above the Details fold")
        self.assertIn("latest ? <dl", fields, "no latest update, no row")
        self.assertIn("fromFile.value ? richOf(tools, m.latest_update) : \"\"", fields, "the live peek has its own box, so the fields draw none")


class PublishedFile(unittest.TestCase):
    """A file with a milestone that has everything (PUB-M-001, 13 days past its forecast), one with nothing (PUB-M-002) and an achieved one."""

    def folder(self, text, name):
        folder = Path(tempfile.mkdtemp(prefix=f"clark-1184v-{name}-"))
        self.addCleanup(lambda: shutil.rmtree(str(folder), ignore_errors=True))
        path = folder / "report.html"
        path.write_text(text, encoding="utf-8")
        return path

    def opened(self, cdp, path, ms, width):
        sid = tp.opened(cdp, path.as_uri() + f"#dashboard&p=PUB&ms={ms}", width)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek .pk-chips')", sid)), f"the {ms} peek drew its chips")
        return sid

    def inert(self, cdp, sid, what):
        self.assertEqual(cdp.js(INERT, sid), [], f"{what}: nothing to press, tab to or open (chips are plain spans; only the toolbar and the Details fold)")

    def nothing_new(self, cdp, sid, what):
        text = cdp.js(PEEK_TEXT, sid)
        for word in NEW_WORDS + ["Client visible", "Client not visible", "Use case", "read only", "Draft with AI", "Add "]:
            self.assertNotIn(word, text, f"{what}: {word!r} is the editor's, not the client's: {text}")
        self.assertEqual(cdp.js("document.querySelectorAll('#peek [title]').length", sid), cdp.js("document.querySelectorAll('#peek .pkp-btn[title]').length", sid), f"{what}: no tooltips outside the toolbar")
        for hook in EDIT_HOOKS:
            self.assertEqual(cdp.js(f"document.querySelectorAll('#peek [{hook}]').length", sid), 0, f"{what}: {hook}")

    def test_a_file_with_everything_draws_read_only_chips_the_clients_rows_and_none_of_the_new_words(self):
        def full(plant):
            for m in plant["data"]["milestones"]:
                if m["id"] == "PUB-M-001":
                    m.update(forecast_date=PAST.isoformat(), client_message="<p>Wording ZQ-WORDS</p>", description="<p>Describe ZQ-DESC</p>", latest_update="<p>Latest ZQ-LATEST</p>", percent_complete=60)
        path = self.folder(file_with(full), "full")
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.opened(cdp, path, "PUB-M-001", width)
                chips = cdp.js(CHIPS, sid)
                self.assertEqual(list(chips), CHIP_ORDER)
                self.assertEqual([c["tag"] for c in chips.values()], ["SPAN"] * 4, "plain spans, no buttons")
                self.assertTrue(all(c["ro"] for c in chips.values()), "every chip is the read only look")
                self.assertEqual((chips["state"]["text"], chips["owner"]["text"], chips["progress"]["text"]), ("At risk", "Delivery lead", "60%"))
                self.assertEqual(chips["state"]["icons"], ["sRisk"], "the peek's own State icon")
                self.assertEqual(chips["progress"]["icons"], ["bars"])
                self.assertEqual(chips["owner"]["icons"], ["user"])
                self.assertEqual(chips["forecast"]["icons"], ["cal"])
                self.assertEqual(chips["forecast"]["text"], shown(PAST) + " overdue 13 days")
                self.assertEqual(chips["forecast"]["sub"], "overdue 13 days")
                self.assertTrue(chips["forecast"]["late"], "red when past")
                self.assertEqual(chips["state"]["label"], "State: At risk", "a screen reader hears the field and its value")
                self.assertEqual(chips["progress"]["label"], "Progress: 60%")
                self.inert(cdp, sid, "file")
                self.assertEqual(cdp.js(LABELS, sid), CLIENT_ROWS, "no Forecast date row, no Use case row, no Client visible line, no Achieved on (not achieved)")
                text = cdp.js(PEEK_TEXT, sid)
                for word in ("ZQ-WORDS", "ZQ-DESC", "ZQ-LATEST"):
                    self.assertIn(word, text)
                self.assertTrue(cdp.js("(() => { const l = document.querySelector('#peek [data-ms-row=latest_update]'), d = document.querySelector('#peek [data-pk-details]'); return !!l && !!d && !!(l.compareDocumentPosition(d) & Node.DOCUMENT_POSITION_FOLLOWING); })()", sid), "Latest update is above the Details fold")
                self.assertEqual(cdp.js("document.querySelectorAll('#peek [data-ms-fields] [data-ms-row=latest_update]').length", sid), 0, "and not a Details row")
                self.nothing_new(cdp, sid, "file")
                # a click and Enter on every chip open nothing
                for key in CHIP_ORDER:
                    cdp.js(f"document.querySelector('#peek .pk-chips [data-row={key}]').click()", sid)
                    cdp.js(f"document.querySelector('#peek .pk-chips [data-row={key}]').dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', bubbles: true }}))", sid)
                    cdp.js(f"document.querySelector('#peek .pk-chips [data-row={key}]').dispatchEvent(new KeyboardEvent('keydown', {{ key: 'ArrowDown', altKey: true, bubbles: true }}))", sid)
                self.assertEqual(cdp.js(POPS, sid), 0, "no popover opened")
                self.assertEqual(cdp.js(CHIPS, sid), chips, "nothing changed")
                self.assertEqual(cdp.js("(window.violations || []).length", sid), 0, "no policy violation, no stray request")
                self.assertTrue(cdp.js("(p => p.scrollWidth <= p.clientWidth + 1)(document.querySelector('#peek'))", sid), "no sideways scroll")

    def test_a_file_with_nothing_to_say_draws_dashes_and_no_prompt_words(self):
        def bare(plant):
            for m in plant["data"]["milestones"]:
                if m["id"] == "PUB-M-002":
                    m["forecast_date"] = FUTURE.isoformat()
        path = self.folder(file_with(bare), "bare")
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.opened(cdp, path, "PUB-M-002", width)
                chips = cdp.js(CHIPS, sid)
                self.assertEqual(chips["progress"]["text"], "Progress not set")
                self.assertEqual(chips["forecast"]["text"], shown(FUTURE), "a future date has no overdue word")
                self.assertIsNone(chips["forecast"]["sub"])
                self.assertFalse(chips["forecast"]["late"])
                self.assertEqual(cdp.js(LABELS, sid), ["Agreed date", "Workstream"], "no wording, no description (row 560), and no empty row for them")
                self.assertEqual(cdp.js("document.querySelector('#peek [data-ms-row=workstream] dd').textContent.trim()", sid), "—", "an empty workstream is the dash, not 'Add workstream'")
                self.assertEqual(cdp.js("document.querySelectorAll('#peek [data-ms-row=latest_update]').length", sid), 0)
                self.inert(cdp, sid, "bare file")
                self.nothing_new(cdp, sid, "bare file")

    def test_a_file_milestone_with_no_forecast_date_has_a_dash_chip(self):
        def none(plant):
            for m in plant["data"]["milestones"]:
                if m["id"] == "PUB-M-002":
                    m["forecast_date"] = None
        path = self.folder(file_with(none), "nodate")
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.opened(cdp, path, "PUB-M-002", width)
                chips = cdp.js(CHIPS, sid)
                self.assertEqual((chips["forecast"]["text"], chips["forecast"]["sub"], chips["forecast"]["late"]), ("\u2014", None, False))
                self.inert(cdp, sid, "file, no forecast date")
                self.nothing_new(cdp, sid, "file, no forecast date")

    def test_an_achieved_milestone_in_a_file_has_the_achieved_on_row_and_no_overdue_word(self):
        def done(plant):
            for m in plant["data"]["milestones"]:
                if m["id"] == "PUB-M-001":
                    m.update(status="Done", state="Achieved", state_set=1, actual_date="2026-10-20", percent_complete=100, client_message="<p>Done ZQ-W</p>")
        path = self.folder(file_with(done), "done")
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.opened(cdp, path, "PUB-M-001", width)
                chips = cdp.js(CHIPS, sid)
                self.assertEqual((chips["state"]["text"], chips["state"]["icons"], chips["progress"]["text"]), ("Achieved", ["sClosed"], "100%"))
                self.assertIsNone(chips["forecast"]["sub"], "an achieved milestone is never overdue")
                self.assertFalse(chips["forecast"]["late"])
                self.assertEqual(cdp.js(LABELS, sid), ["Agreed date", "Achieved on", "Workstream", "Client wording"])
                self.assertEqual(cdp.js("document.querySelector('#peek [data-ms-row=actual] dd').textContent.trim()", sid), "20-10-2026")
                self.inert(cdp, sid, "achieved file")
                self.nothing_new(cdp, sid, "achieved file")

    def test_the_client_lists_and_use_case_page_keep_the_milestone_pages_marks_in_a_file(self):
        path = self.folder(file_with(), "lists")
        with chrome() as cdp:
            sid = tp.opened(cdp, path.as_uri() + "#milestones&p=PUB", 1400)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-ms]')", sid)), "the file's Milestones list drew")
            self.assertEqual(cdp.js("document.querySelectorAll('[data-ms] .pkc, [data-ms] .pk-chips').length", sid), 0, "the list keeps its own state mark, not the peek's chips")
            self.assertGreater(cdp.js("document.querySelectorAll('[data-ms] svg').length", sid), 0)


class DashboardInView(Base):
    """The Dashboard in View: the live page with no editing tools for a milestone."""
    cur = PILOT

    def visit(self, cdp, ms, width, view="dashboard"):
        from test_report_editor import Pg
        self.cur = ms
        p = Pg.at(self, cdp, self.s.port, f"#{view}&p=ABC&ms={ms}")
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.until("!!document.querySelector('#peek .pk-chips')", "the peek drew its chip row")
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]}, p.sid)
        p.until("document.getAnimations().length === 0", "no animation running")
        return p

    def test_view_draws_read_only_chips_and_the_clients_rows_for_a_milestone_with_and_without_words(self):
        with self.store.step("dashboard", USER) as st:
            st.update("milestones", PILOT, {"state": "At risk", "state_set": 1, "percent_complete": 40, "client_message": "<p>Going <strong>well</strong></p>", "description": "<p>Scope</p>", "latest_update": "<p>Latest ZQ</p>"})
            st.update("milestones", GO_LIVE, {"description": "", "client_message": "", "workstream": ""})
        for width in (1400, 900):
            for ms, rows in ((PILOT, ["Description", "Agreed date", "Workstream", "Client wording"]), (GO_LIVE, None)):
                with self.subTest(width=width, ms=ms), chrome() as cdp:
                    p = self.visit(cdp, ms, width)
                    chips = p.js(CHIPS)
                    self.assertEqual(list(chips), CHIP_ORDER)
                    self.assertEqual([c["tag"] for c in chips.values()], ["SPAN"] * 4, "View: no tools, no buttons")
                    self.assertTrue(all(c["ro"] for c in chips.values()))
                    self.assertEqual(p.js(INERT), [], "nothing to press, tab to or open in View")
                    if ms == PILOT:
                        self.assertEqual((chips["state"]["text"], chips["state"]["icons"], chips["progress"]["text"]), ("At risk", ["sRisk"], "40%"))
                        self.assertEqual(p.js(LABELS), rows, "no Use case row, no Client visible line, no Forecast date row")
                        self.assertNotIn("Latest update", p.js(PEEK_TEXT), "today View (not a file) draws no latest update for a milestone: facts in the findings")
                    text = p.js(PEEK_TEXT)
                    for word in NEW_WORDS + ["Client visible", "Client not visible", "Select use case", "Draft with AI"]:
                        self.assertNotIn(word, text, f"View: {word!r} is the editor's: {text}")
                    for hook in EDIT_HOOKS:
                        self.assertEqual(p.js(f"document.querySelectorAll('#peek [{hook}]').length"), 0, hook)
                    for key in CHIP_ORDER:
                        p.js(f"document.querySelector('#peek .pk-chips [data-row={key}]').click()")
                    self.assertEqual(p.js(POPS), 0, "a click opens nothing in View")

    def test_the_milestones_page_in_edit_still_has_its_own_chips_so_the_pins_above_are_not_vacuous(self):
        with chrome() as cdp:
            p = self.visit(cdp, PILOT, 1400, view="milestones")
            chips = p.js(CHIPS)
            self.assertEqual(p.js("document.querySelectorAll('#peek .pk-chips > [data-row] button').length"), 4, "the editor's chips are buttons")
            self.assertGreater(len(p.js(INERT)), 0)


if __name__ == "__main__":
    unittest.main()
