"""Row 828 (M4, M5): the milestone peek's fields are editable in place on the Milestones page with no View mode: Name, Owner, Forecast date,
Achieved on, State, Progress, Description, Workstream, Visible to client and Client Message. Each is one change with one Undo; a refusal
changes nothing; the Dashboard's View and a published file keep the read-only peek. M6 (row 867, Archive in the peek) uses the work item peek's own words.
Row 1078: the name is the title and the owner, state and progress are the header line (test_milestone_peek_1078 pins the layout); the rows
below are plain rows (data-ms-row), and Client Message is on the rich editor like the description.

Run: python3 dev/run_tests.py test_milestone_peek_828
Without a browser: the pure rules (msPeek.js) are read from the source; the published build takes none of the new files.
With headless Chrome (fails, never skips, without it): each field in the real server, at 1400 and 900 px, light and dark.
"""
import json
import tempfile
import unittest
from pathlib import Path

from _demo import USER
from _paths import SRC, TOOLS

import sys
sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

from test_movement_page import GO_LIVE, PILOT, Base  # noqa: E402
from test_server import chrome  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
ROWS = ("description", "baseline", "workstream", "use_cases", "client_message", "visible")      # row 1184: the state, owner, progress and forecast date are the chip row, the Latest update is a box above Details, Visible is the Client visible line after the rows


class NoBrowser(unittest.TestCase):
    def test_the_published_build_takes_none_of_the_new_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta = Path(tmp) / "meta.json"
            done = esbuild.run(["--bundle", "--format=iife", "--tsconfig-raw={}", *build_page.preact_flags(), build_page.ENTRY_VIEW,
                                f"--outfile={Path(tmp) / 'p.js'}", f"--metafile={meta}"], cwd=build_page.SRC, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            inputs = list(json.loads(meta.read_text(encoding="utf-8"))["inputs"])
        for name in inputs:
            self.assertFalse(name.endswith(("MilestonePeek.jsx", "msPeek.js")), name)

    def test_the_new_words_of_the_owner_are_not_in_the_build(self):
        text = "".join(p.read_text(encoding="utf-8") for p in (PAGE_SRC / "edit").glob("MilestonePeek.jsx")) \
            + (PAGE_SRC / "edit" / "msPeek.js").read_text(encoding="utf-8")
        for sentence in ("Overdue follows the dates", "It's out of the lists and counts", "work items still point at it", "Archived "):
            self.assertNotIn(sentence, text, sentence)


class Fields(Base):
    cur = GO_LIVE

    def visit_peek(self, cdp, ms=GO_LIVE, width=1400, theme=None, view="milestones"):
        from test_report_editor import Pg
        self.cur = ms
        p = Pg.at(self, cdp, self.s.port, f"#{view}&p=ABC&ms={ms}")
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.until("!!document.querySelector('#peek')", "the peek drew")
        # Row 1588: the metrics override sends the page a resize a frame later; a picker opened before it lands is closed by it (Pop.jsx closes on resize).
        p.until(f"window.innerWidth === {width}", f"the window is {width} wide")
        p.js("window.__f2 = 0; requestAnimationFrame(() => requestAnimationFrame(() => { window.__f2 = 1; }))")
        p.until("window.__f2 === 1", "two frames drew after the resize")
        if theme:
            p.js(f"document.documentElement.dataset.theme = '{theme}'")
        return p

    def click(self, p, sel):
        p.until(f"!!document.querySelector({json.dumps(sel)})", sel)
        p.js(f"document.querySelector({json.dumps(sel)}).click()")

    def chip(self, p, field):
        """Row 1184: open the popover of one chip (State, Owner, Progress, Forecast date)."""
        self.click(p, f"#peek .pk-chips [data-row={field}] button")
        p.until("!!document.querySelector('[data-pop]')", f"the {field} popover opened")

    def archive_in_peek(self, p):
        """Item 1148: Archive is the first entry of the milestone peek's More actions menu."""
        self.click(p, "#peek #pk-more")
        self.click(p, ".ddmenu [data-kind=archive]")

    def type_in(self, p, sel, text, leave="enter"):
        p.until(f"!!document.querySelector({json.dumps(sel)})", sel)
        p.js(f"(() => {{ const el = document.querySelector({json.dumps(sel)}); el.value = {json.dumps(text)}; el.dispatchEvent(new Event('input', {{bubbles: true}})); "
             + {"enter": "el.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true, cancelable: true}));",
                "ctrl": "el.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', ctrlKey: true, bubbles: true, cancelable: true}));",
                "esc": "el.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true}));",
                "blur": "el.dispatchEvent(new FocusEvent('blur'));", "none": ""}[leave] + " })()")

    def type_owner(self, p, text, leave="enter"):
        """The owner popover reads what is typed from the box's state: let the page draw the typed text before the key (a person's keystrokes always do)."""
        sel = ".cowner input.cp-in"
        self.type_in(p, sel, text, leave="none")
        p.js("window.__drawn = 0; requestAnimationFrame(() => requestAnimationFrame(() => { window.__drawn = 1; }))")
        p.until("window.__drawn === 1", "the page drew the typed text")
        key = {"enter": "Enter", "esc": "Escape"}[leave]
        p.js(f"document.querySelector({json.dumps(sel)}).dispatchEvent(new KeyboardEvent('keydown', {{key: '{key}', bubbles: true, cancelable: true}}))")

    def saved(self, p, field, value):
        self.assertTrue(self.until_store(lambda: self.row(self.cur)[field] == value), f"{field} was not saved as {value!r}: {self.row(self.cur)[field]!r}")

    def until_store(self, test, seconds=10):
        from _rich_page import wait_for
        return wait_for(test, seconds) or test()

    def toast_text(self, p):
        return p.js("(document.querySelector('.toast .toast-text') || {}).textContent || ''")

    def undo(self, p, said=""):
        """The toast lives 5 seconds and a loaded runner can poll late: wait for the Undo button of THIS change (its words, `said`: the toast of the save before it has an Undo too, and a click on that one is not the change the test asks about), then record every toast text from the click on, so a short-lived Undone line is never missed."""
        p.until("!!document.querySelector('.toast [data-undo]') && (document.querySelector('.toast .toast-text').textContent || '').includes(%s)" % json.dumps(said), "the Undo button of " + (said or "the toast"))
        p.js("(() => { window.__toastSeen = []; const note = () => { const t = document.querySelector('.toast .toast-text'); if (t) window.__toastSeen.push(t.textContent || ''); };"
             " window.__toastWatch && window.__toastWatch.disconnect(); window.__toastWatch = new MutationObserver(note);"
             " window.__toastWatch.observe(document.body, {subtree: true, childList: true, characterData: true}); document.querySelector('.toast [data-undo]').click(); })()")
        p.until("window.__toastSeen.some((t) => /^Undone[.:]/.test(t))", "Undone", 30)      # item 1850: the Undo save waits behind a loaded Mac runner; 10 s was not enough there

    def test_the_fields_are_there_on_the_milestones_page_in_view_and_not_on_the_dashboard_in_view(self):
        with chrome() as cdp:
            p = self.visit_peek(cdp)
            self.assertEqual(p.js("document.querySelectorAll('[data-mode]').length"), 0, "no View | Edit switch off the Dashboard: the page is always editable")
            self.assertEqual(p.js("[...document.querySelectorAll('#peek [data-ms-edit] .pk-row')].map((r) => r.dataset.msRow)"), list(ROWS))
            self.assertEqual(p.js("[...document.querySelectorAll('#peek .pk-chips > [data-row]')].map((e) => e.dataset.row)"), ["state", "owner", "progress", "forecast"], "the state, owner, progress and forecast date are the chips above the rows (row 1184)")
            self.assertEqual(p.js("document.querySelectorAll('#peek [data-ms-head], #peek [data-ms-range], #peek [data-ms-num]').length"), 0, "the old header line, slider and number box are gone")
        with chrome() as cdp:
            p = self.visit_peek(cdp, view="dashboard")
            self.assertEqual(p.js("document.querySelectorAll('#peek [data-ms-edit]').length"), 0, "the Dashboard's View peek stays read only")
            self.assertEqual(p.js("document.querySelectorAll('#peek .pk-fields').length"), 1)

    def test_owner_saves_on_enter_with_one_undo_and_esc_leaves_it_as_it_was(self):
        with chrome() as cdp:
            p = self.visit_peek(cdp)
            self.chip(p, "owner")
            self.type_owner(p, "Zed Example", leave="esc")
            p.until("!document.querySelector('[data-pop]')", "Esc closed the popover")
            self.assertEqual(self.row(self.cur)["owner"], "Priya Example")
            self.assertEqual(self.sent, [])
            self.chip(p, "owner")
            self.type_owner(p, "Zed Example")
            self.saved(p, "owner", "Zed Example")
            p.until(f"/^Owner of {GO_LIVE} changed to Zed Example\\.$/.test((document.querySelector('.toast .toast-text') || {{}}).textContent || '')", "the toast")
            self.assertEqual(self.sent[-1][1]["place"], "peek")
            self.undo(p)
            self.saved(p, "owner", "Priya Example")
            p.until("document.querySelector('#peek .pk-chips [data-row=owner]').textContent.includes('Priya Example')", "the peek shows the undone value")

    def test_clearing_the_owner_is_one_step_and_a_blank_name_is_restored(self):
        with chrome() as cdp:
            p = self.visit_peek(cdp)
            self.chip(p, "owner")
            self.type_owner(p, "  ")
            self.saved(p, "owner", None)
            self.click(p, "#peek .pk-title .pkh-title-txt")
            self.type_in(p, "#peek textarea[data-ms-field=name]", " ")
            p.until("!document.querySelector('#peek textarea[data-ms-field=name]')", "the blank name closed the box")
            self.assertEqual(self.row(self.cur)["name"], "Go live")
            self.assertEqual(p.js("document.querySelector('#peek .pk-title').textContent"), "Go live")

    def test_name_renames_with_one_undo_and_a_refusal_changes_nothing(self):
        with chrome() as cdp:
            p = self.visit_peek(cdp)
            self.click(p, "#peek .pk-title .pkh-title-txt")
            self.type_in(p, "#peek textarea[data-ms-field=name]", "Go live, phase one")
            self.saved(p, "name", "Go live, phase one")
            self.undo(p)
            self.saved(p, "name", "Go live")

    def test_progress_by_blocks_one_step_each_and_the_same_block_sets_it_back_to_0(self):
        with chrome() as cdp:
            p = self.visit_peek(cdp)
            self.chip(p, "progress")
            self.assertEqual(p.js("document.querySelectorAll('[data-pop] [data-ms-block]').length"), 10, "ten blocks")
            self.click(p, "[data-pop] [data-ms-block='40']")
            self.saved(p, "percent_complete", 40)
            p.until("document.querySelector('#peek .pk-chips [data-row=progress]').textContent.includes('40%')", "the chip says 40%")
            self.chip(p, "progress")
            self.click(p, "[data-pop] [data-ms-block='40']")
            self.saved(p, "percent_complete", 0)       # ruled: the block that equals the progress sets it back to 0
            self.chip(p, "progress")
            self.click(p, "[data-pop] [data-ms-block='70']")
            self.saved(p, "percent_complete", 70)
            self.undo(p, "70%")
            self.saved(p, "percent_complete", 0)

    def test_state_popover_sets_clears_and_achieved_is_done_with_its_date(self):
        with chrome() as cdp:
            p = self.visit_peek(cdp, ms=PILOT)       # agreed far ahead: On track by the dates, so a worse state needs no reason
            self.chip(p, "state")
            self.assertEqual(p.js("[...document.querySelectorAll('[data-pop] [data-ms-state]')].map((b) => b.dataset.msState)"),
                             ["Forecast", "On track", "At risk", "Slipped", "Achieved"])      # row 1184 (ruled): Overdue is shown on the chip when the dates make it so, and is not an option
            self.assertEqual(p.js("document.querySelectorAll('[data-pop] [data-ms-state=Overdue]').length"), 0)
            self.assertEqual(p.js("document.querySelector('[data-pop] [data-ms-state=\"On track\"]').getAttribute('aria-pressed')"), "true", "the dates say On track")
            self.click(p, "[data-pop] [data-ms-state=Slipped]")
            self.saved(p, "state", "Slipped")
            self.assertEqual(self.row(self.cur)["state_set"], 1)
            self.chip(p, "state")
            p.until("document.querySelector('[data-pop] [data-ms-state=Slipped]').getAttribute('aria-pressed') === 'true'", "Slipped is pressed")
            self.click(p, "[data-pop] [data-ms-state=Slipped]")
            self.saved(p, "state", None)
            self.assertEqual(self.row(self.cur)["state_set"], 0)
            self.chip(p, "state")
            self.click(p, "[data-pop] [data-ms-state=Achieved]")
            self.saved(p, "status", "Done")
            row = self.row(self.cur)
            self.assertEqual((row["state"], row["state_set"]), ("Achieved", 1))
            self.assertTrue(row["actual_date"])
            p.until("!!document.querySelector('#peek [data-ms-field=actual_date]')", "Achieved on is shown for a Done milestone")
            self.undo(p)
            self.saved(p, "status", "Planned")
            self.assertIsNone(self.row(self.cur)["actual_date"])

    def test_forecast_date_is_picked_from_the_calendar_and_cleared_with_one_undo(self):
        with chrome() as cdp:
            p = self.visit_peek(cdp)
            before = self.row(self.cur)["forecast_date"]
            self.chip(p, "forecast")
            p.until("!!document.querySelector('.cdate [data-quick]')", "the calendar opened")
            p.js("document.querySelector('.cdate [data-quick]').click()")
            self.assertTrue(self.until_store(lambda: self.row(self.cur)["forecast_date"] != before), "the forecast moved")
            self.undo(p)
            self.saved(p, "forecast_date", before)

    def test_description_is_a_one_line_editor_enter_saves_the_line_one_undo(self):
        """Row 1288: the description is One line (RichField oneLine): no toolbar blocks, Enter saves the one line, one Undo."""
        with chrome() as cdp:
            p = self.visit_peek(cdp)
            self.click(p, "#peek [data-rich=description]")
            p.until("!!document.querySelector('#peek .ProseMirror') && document.activeElement.classList.contains('ProseMirror')", "the editor opened with the focus")
            self.assertEqual(p.js("document.querySelectorAll('#peek textarea[data-ms-in=description]').length"), 0, "not a plain box")
            self.assertEqual(p.js("document.querySelectorAll('#peek .rt-style, #peek .rt-bubble').length"), 0, "One line: no style menu")
            p.js("document.querySelector('#peek .ProseMirror').cxed.editor.commands.insertContent('Scope line'); true")
            self.assertEqual(self.sent, [], "typing sends nothing")
            p.key("Enter", code="Enter", vk=13)
            self.saved(p, "description", "<p>Scope line</p>")
            self.assertEqual(self.sent[-1][1]["changes"]["description"], "<p>Scope line</p>")
            p.until("!document.querySelector('#peek .ProseMirror')", "the editor closed after the save")
            self.assertEqual(p.js("[...document.querySelectorAll('#peek [data-rich=description] p')].map((e) => e.textContent)"), ["Scope line"])
            self.assertIn("Description of", self.toast_text(p))
            self.undo(p)
            self.saved(p, "description", None)

    def test_a_legacy_plain_description_reads_as_paragraphs_and_is_not_saved_by_looking(self):
        """Item 1005: an old row holds plain text (newlines, <, &, quotes); it is drawn escaped, opens in the editor, and leaving it saves nothing."""
        legacy = 'Line one: a < b & "c"\nLine two'
        with chrome() as cdp:
            with self.store.step("dashboard", USER) as st:
                st.update("milestones", GO_LIVE, {"description": legacy})
            p = self.visit_peek(cdp)
            self.assertEqual(p.js("[...document.querySelectorAll('#peek [data-rich=description] p')].map((e) => e.textContent)"), ['Line one: a < b & "c"', "Line two"])
            self.assertEqual(p.js("document.querySelectorAll('#peek [data-rich=description] script, #peek [data-rich=description] b').length"), 0)
            self.click(p, "#peek [data-rich=description]")
            p.until("!!document.querySelector('#peek .ProseMirror')", "the editor opened")
            self.assertEqual(p.js("[...document.querySelectorAll('#peek .ProseMirror p')].map((e) => e.textContent)"), ['Line one: a < b & "c" Line two'], "One line: the old lines joined with one space")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('#peek .ProseMirror')", "Esc closed it")
            self.assertEqual(self.sent, [], "looking saved nothing")
            self.assertEqual(self.row(GO_LIVE)["description"], legacy, "the old row is still plain text")

    def test_an_old_several_paragraph_description_is_one_joined_line_in_the_editor_and_stays_as_stored_until_edited(self):
        """Row 1288 (ruling WO-M10443): a description an earlier editor saved as several paragraphs with bold and a list. The One line editor
        shows its words joined with one space, nothing is dropped from the row by looking or by saving untouched, and an edit of the joined
        line replaces the lines (the row then holds that one paragraph)."""
        old = "<p>Scope <strong>line</strong> one</p><p>Second paragraph</p><ul><li>List item</li></ul>"
        joined = "Scope line one Second paragraph List item"
        with chrome() as cdp:
            with self.store.step("dashboard", USER) as st:
                st.update("milestones", GO_LIVE, {"description": old})
            p = self.visit_peek(cdp)
            self.click(p, "#peek [data-rich=description]")
            p.until("!!document.querySelector('#peek .ProseMirror') && document.activeElement.classList.contains('ProseMirror')", "the editor opened")
            self.assertEqual(p.js("[...document.querySelectorAll('#peek .ProseMirror p')].map((e) => e.textContent)"), [joined], "one line, the words joined with one space")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('#peek .ProseMirror')", "Esc closed it")
            self.assertEqual(self.sent, [], "looking saved nothing")
            self.assertEqual(self.row(GO_LIVE)["description"], old, "the old row is byte for byte as it was")
            self.click(p, "#peek [data-rich=description]")
            p.until("!!document.querySelector('#peek .ProseMirror') && document.activeElement.classList.contains('ProseMirror')", "the editor opened again")
            p.key("Enter", code="Enter", vk=13)                      # saving untouched
            p.until("!document.querySelector('#peek .ProseMirror')", "Enter closed it")
            self.assertEqual(self.sent, [], "an untouched save sends nothing")
            self.assertEqual(self.row(GO_LIVE)["description"], old, "every stored line is still there")
            self.click(p, "#peek [data-rich=description]")
            p.until("!!document.querySelector('#peek .ProseMirror') && document.activeElement.classList.contains('ProseMirror')", "the editor opened a third time")
            p.js("document.querySelector('#peek .ProseMirror').cxed.editor.chain().focus('end').insertContent(' ZQ').run(); true")
            p.key("Enter", code="Enter", vk=13)
            self.saved(p, "description", f"<p>{joined} ZQ</p>")

    def test_workstream_and_client_wording_and_visible_to_client(self):
        with chrome() as cdp:
            p = self.visit_peek(cdp)
            self.assertEqual(p.js("document.querySelector('#peek [data-ms-field=workstream]').textContent"), "Add workstream")
            self.click(p, "#peek [data-ms-field=workstream]")
            p.until("!!document.querySelector('[data-pop][role=menu]')", "the workstream menu opened")
            self.assertEqual(p.js("document.querySelectorAll('[data-pop] [role=menuitemradio] svg.i').length"), p.js("document.querySelectorAll('[data-pop] [role=menuitemradio]').length"), "every choice has its icon (row 1074)")
            self.click(p, "[data-pop] [role=menuitemradio][data-value=Build]")
            self.saved(p, "workstream", "Build")
            self.click(p, "#peek [data-ms-row=client_message] [data-rich=client_message]")           # row 1078: the one rich editor, as the description
            p.until("!!document.querySelector('#peek .ProseMirror') && document.activeElement.classList.contains('ProseMirror')", "the editor opened with the focus")
            p.js("document.querySelector('#peek .ProseMirror').cxed.editor.commands.insertContent('On its way'); true")
            p.key("Enter", modifiers=4 if p.js("/Mac/.test(navigator.platform)") else 2, code="Enter", vk=13)
            self.saved(p, "client_message", "<p>On its way</p>")
            p.until("!document.querySelector('#peek .ProseMirror')", "the editor closed after the save")
            self.assertEqual(p.js("document.querySelector('#peek [data-ms-visible]').getAttribute('aria-pressed')"), "true")
            self.click(p, "#peek [data-ms-visible]")
            self.assertTrue(self.until_store(lambda: GO_LIVE in {h["item_id"] if isinstance(h, dict) else h for h in self.store.data_for("ABC")["report_hidden"]}), "left out of the page")
            p.until("document.querySelector('#peek [data-ms-visible]').getAttribute('aria-pressed') === 'false'", "the button shows No")
            self.undo(p)
            self.assertTrue(self.until_store(lambda: GO_LIVE not in {h["item_id"] if isinstance(h, dict) else h for h in self.store.data_for("ABC")["report_hidden"]}))

    def test_a_refusal_changes_nothing_and_says_so(self):
        with chrome() as cdp:
            p = self.visit_peek(cdp)
            self.chip(p, "state")
            self.click(p, "[data-pop] [data-ms-state=On\\ track]")
            p.until("!!document.querySelector('.toast.problem, .toast[data-kind=problem]') || /couldn|nothing was changed/i.test((document.querySelector('.toast .toast-text') || {}).textContent || '')", "a refusal is said")
            self.assertIsNone(self.row(self.cur)["state"])

    def calm(self, p):
        p.cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]}, p.sid)
        p.until("document.getAnimations().length === 0", "no animation running")

    def test_archive_in_the_milestone_peek_hides_it_closes_the_peek_and_one_undo_brings_it_back(self):
        """Row 867 (M6): the existing Archive button of the peek, with the existing words (no new sentence)."""
        with chrome() as cdp:
            p = self.visit_peek(cdp)
            self.calm(p)
            self.assertEqual(p.js("document.querySelectorAll('#peek #pk-more').length"), 1)
            self.archive_in_peek(p)
            self.assertTrue(self.until_store(lambda: self.row(self.cur)["archived"] == 1), "archived")
            self.assertEqual((self.sent[-1][1]["kind"], self.sent[-1][1]["op"], self.sent[-1][1]["id"]), ("milestones", "archive", GO_LIVE))
            p.until(f"(document.querySelector('.toast .toast-text') || {{}}).textContent === '{GO_LIVE} archived. It is out of the lists and the published page.'", "the toast")
            p.until("!document.querySelector('#peek')", "the peek closed")
            p.until("!!document.querySelector('.toast [data-undo]')", "Undo offered")
            # row 1054: the focus goes to the next milestone row's cells, or to Undo where there is no next row (never to the page body)
            p.until("document.activeElement && (document.activeElement.hasAttribute('data-undo') || (document.activeElement.classList.contains('msl-cells') && !!document.activeElement.closest('li.msl-row')))", "the focus moved to the next row or to Undo, not to the page body")
            p.js("document.querySelector('.toast [data-undo]').click()")
            self.assertTrue(self.until_store(lambda: self.row(self.cur)["archived"] == 0), "one Undo brings it back")

    def test_after_archive_in_the_peek_focus_goes_to_the_next_row_or_to_undo(self):
        """Row 1054: the peek closes with its item; focus must not drop to the page. Next row's cell, else the toast's Undo."""
        for ms in (GO_LIVE, PILOT):
            for width in (1400, 900):
                with self.subTest(ms=ms, width=width), chrome() as cdp:
                    self.setUp()
                    p = self.visit_peek(cdp, ms=ms, width=width)
                    self.calm(p)
                    want = p.js(f"(() => {{ const n = document.querySelector('li.msl-row[data-ms=\"{ms}\"]'); const x = n && n.nextElementSibling; "
                                "return x ? x.getAttribute('data-ms') : ''; })()")
                    self.archive_in_peek(p)
                    p.until("!document.querySelector('#peek') && !!document.querySelector('.toast [data-undo]')", "closed, Undo offered")
                    p.until("document.activeElement !== document.body", "focus did not drop to the page")
                    got = p.js("(() => { const a = document.activeElement; const r = a.closest('li.msl-row'); "
                               "return r && a.classList.contains('msl-cells') ? r.getAttribute('data-ms') : a.matches('.toast [data-undo]') ? 'undo' : a.tagName; })()")
                    self.assertEqual(got, want or "undo")

    def test_no_archive_button_in_the_dashboards_view_peek(self):
        with chrome() as cdp:
            p = self.visit_peek(cdp, view="dashboard")
            self.assertEqual(p.js("document.querySelectorAll('#peek [data-pk-archive], #peek #pk-more').length"), 0)

    def test_fit_at_both_widths_in_both_themes(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    p = self.visit_peek(cdp, width=width, theme=theme)
                    seen = p.js("""(() => {
                      const peek = document.querySelector('#peek'), pr = peek.getBoundingClientRect();
                      const els = [...peek.querySelectorAll('.pk-title [data-ms-field], #peek .pk-chips button, [data-ms-edit] button, [data-ms-edit] select, [data-ms-edit] input')];
                      return {inside: els.every((e) => { const r = e.getBoundingClientRect(); return r.right <= pr.right + 1 && r.left >= pr.left - 1; }),
                              small: els.filter((e) => e.getBoundingClientRect().height < 24 && e.type !== 'range').map((e) => e.outerHTML.slice(0, 80)),
                              scroll: peek.scrollWidth <= peek.clientWidth + 1, n: els.length,
                              size: Math.min(...els.filter((e) => e.type !== 'range').map((e) => parseFloat(getComputedStyle(e).fontSize)))};
                    })()""")
                    self.assertTrue(seen["inside"], "every control is inside the peek")
                    self.assertEqual(seen["small"], [])
                    self.assertTrue(seen["scroll"], "no sideways scroll in the peek")
                    self.assertGreaterEqual(seen["size"], 13)


if __name__ == "__main__":
    unittest.main()
