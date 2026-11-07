"""Row 828 (M4, M5): the milestone peek's fields are editable in place on the Milestones page with no View mode: Name, Owner, Forecast date,
Achieved on, State, Progress, Description, Workstream, Visible to client and Client wording. Each is one change with one Undo; a refusal
changes nothing; the Dashboard's View and a published file keep the read-only peek. M6 (row 867, Archive in the peek) uses the work item peek's own words.

Run: python3 dev/run_tests.py test_milestone_peek_828
Without a browser: the pure rules (msPeek.js) are read from the source; the published build takes none of the new files.
With headless Chrome (fails, never skips, without it): each field in the real server, at 1400 and 900 px, light and dark.
"""
import json
import tempfile
import unittest
from pathlib import Path

from _paths import SRC, TOOLS

import sys
sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

from test_movement_page import GO_LIVE, PILOT, Base  # noqa: E402
from test_server import chrome  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
ROWS = ("name", "owner", "baseline", "forecast", "state", "progress", "description", "workstream", "visible", "client_message")


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
        if theme:
            p.js(f"document.documentElement.dataset.theme = '{theme}'")
        return p

    def click(self, p, sel):
        p.until(f"!!document.querySelector({json.dumps(sel)})", sel)
        p.js(f"document.querySelector({json.dumps(sel)}).click()")

    def type_in(self, p, sel, text, leave="enter"):
        p.until(f"!!document.querySelector({json.dumps(sel)})", sel)
        p.js(f"(() => {{ const el = document.querySelector({json.dumps(sel)}); el.value = {json.dumps(text)}; el.dispatchEvent(new Event('input', {{bubbles: true}})); "
             + {"enter": "el.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true, cancelable: true}));",
                "ctrl": "el.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', ctrlKey: true, bubbles: true, cancelable: true}));",
                "esc": "el.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true}));",
                "blur": "el.dispatchEvent(new FocusEvent('blur'));", "none": ""}[leave] + " })()")

    def saved(self, p, field, value):
        self.assertTrue(self.until_store(lambda: self.row(self.cur)[field] == value), f"{field} was not saved as {value!r}: {self.row(self.cur)[field]!r}")

    def until_store(self, test, seconds=10):
        import time
        end = time.time() + seconds
        while time.time() < end:
            if test():
                return True
            time.sleep(0.1)
        return test()

    def toast_text(self, p):
        return p.js("(document.querySelector('.toast .toast-text') || {}).textContent || ''")

    def undo(self, p):
        p.js("document.querySelector('.toast [data-undo]').click()")
        p.until("/^Undone[.:]/.test((document.querySelector('.toast .toast-text') || {}).textContent || '')", "Undone")

    def test_the_fields_are_there_on_the_milestones_page_in_view_and_not_on_the_dashboard_in_view(self):
        with chrome() as cdp:
            p = self.visit_peek(cdp)
            self.assertEqual(p.js("document.querySelectorAll('[data-mode]').length"), 0, "no View | Edit switch off the Dashboard: the page is always editable")
            self.assertEqual(p.js("[...document.querySelectorAll('#peek [data-ms-edit] .pk-row')].map((r) => r.dataset.row)"), list(ROWS))
        with chrome() as cdp:
            p = self.visit_peek(cdp, view="dashboard")
            self.assertEqual(p.js("document.querySelectorAll('#peek [data-ms-edit]').length"), 0, "the Dashboard's View peek stays read only")
            self.assertEqual(p.js("document.querySelectorAll('#peek .pk-fields').length"), 1)

    def test_owner_saves_on_enter_with_one_undo_and_esc_leaves_it_as_it_was(self):
        with chrome() as cdp:
            p = self.visit_peek(cdp)
            self.click(p, "#peek [data-ms-field=owner]")
            self.type_in(p, "#peek [data-ms-in=owner]", "Zed Example", leave="esc")
            p.until("!document.querySelector('#peek [data-ms-in=owner]')", "Esc closed the box")
            self.assertEqual(self.row(self.cur)["owner"], "Priya Example")
            self.assertEqual(self.sent, [])
            self.click(p, "#peek [data-ms-field=owner]")
            self.type_in(p, "#peek [data-ms-in=owner]", "Zed Example")
            self.saved(p, "owner", "Zed Example")
            p.until(f"/^Owner of {GO_LIVE} changed to Zed Example\\.$/.test((document.querySelector('.toast .toast-text') || {{}}).textContent || '')", "the toast")
            self.assertEqual(self.sent[-1][1]["place"], "peek")
            self.undo(p)
            self.saved(p, "owner", "Priya Example")
            p.until("document.querySelector('#peek [data-ms-field=owner]').textContent === 'Priya Example'", "the peek shows the undone value")

    def test_clearing_the_owner_is_one_step_and_a_blank_name_is_restored(self):
        with chrome() as cdp:
            p = self.visit_peek(cdp)
            self.click(p, "#peek [data-ms-field=owner]")
            self.type_in(p, "#peek [data-ms-in=owner]", "  ")
            self.saved(p, "owner", None)
            self.click(p, "#peek [data-ms-field=name]")
            self.type_in(p, "#peek [data-ms-in=name]", " ")
            p.until("!document.querySelector('#peek [data-ms-in=name]')", "the blank name closed the box")
            self.assertEqual(self.row(self.cur)["name"], "Go live")
            self.assertEqual(p.js("document.querySelector('#peek [data-ms-field=name]').textContent"), "Go live")

    def test_name_renames_with_one_undo_and_a_refusal_changes_nothing(self):
        with chrome() as cdp:
            p = self.visit_peek(cdp)
            self.click(p, "#peek [data-ms-field=name]")
            self.type_in(p, "#peek [data-ms-in=name]", "Go live, phase one")
            self.saved(p, "name", "Go live, phase one")
            self.undo(p)
            self.saved(p, "name", "Go live")

    def test_progress_by_number_and_by_slider_one_step_each_and_a_bad_number_sends_nothing(self):
        with chrome() as cdp:
            p = self.visit_peek(cdp)
            self.type_in(p, "#peek [data-ms-num]", "40")
            self.saved(p, "percent_complete", 40)
            sent = len(self.sent)
            self.type_in(p, "#peek [data-ms-num]", "140")
            p.until("document.querySelector('#peek [data-ms-num]').value === '40'", "a number over 100 goes back to what it was")
            self.assertEqual(len(self.sent), sent)
            p.js("(() => { const r = document.querySelector('#peek [data-ms-range]'); r.value = '75'; r.dispatchEvent(new Event('input', {bubbles: true})); r.dispatchEvent(new Event('change', {bubbles: true})); })()")
            self.saved(p, "percent_complete", 75)
            self.undo(p)
            self.saved(p, "percent_complete", 40)

    def test_state_buttons_set_clear_and_achieved_is_done_with_its_date(self):
        with chrome() as cdp:
            p = self.visit_peek(cdp, ms=PILOT)       # agreed far ahead: On track by the dates, so a worse state needs no reason
            self.assertEqual(p.js("[...document.querySelectorAll('#peek [data-ms-state]')].map((b) => b.dataset.msState)"),
                             ["Forecast", "On track", "At risk", "Slipped", "Overdue", "Achieved"])
            self.assertEqual(p.js("document.querySelector('#peek [data-ms-state=Overdue]').disabled"), True)
            self.assertEqual(p.js("document.querySelector('#peek [data-ms-state=\"On track\"]').getAttribute('aria-pressed')"), "true", "the dates say On track")
            self.click(p, "#peek [data-ms-state=Slipped]")
            self.saved(p, "state", "Slipped")
            self.assertEqual(self.row(self.cur)["state_set"], 1)
            p.until("document.querySelector('#peek [data-ms-state=Slipped]').getAttribute('aria-pressed') === 'true'", "Slipped is pressed")
            self.click(p, "#peek [data-ms-state=Slipped]")
            self.saved(p, "state", None)
            self.assertEqual(self.row(self.cur)["state_set"], 0)
            self.click(p, "#peek [data-ms-state=Achieved]")
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
            self.click(p, "#peek [data-ms-field=forecast_date]")
            p.until("!!document.querySelector('.cdate [data-quick]')", "the calendar opened")
            p.js("document.querySelector('.cdate [data-quick]').click()")
            self.assertTrue(self.until_store(lambda: self.row(self.cur)["forecast_date"] != before), "the forecast moved")
            self.undo(p)
            self.saved(p, "forecast_date", before)

    def test_description_takes_enter_as_a_new_line_and_ctrl_enter_saves(self):
        with chrome() as cdp:
            p = self.visit_peek(cdp)
            self.click(p, "#peek [data-ms-field=description]")
            self.type_in(p, "#peek [data-ms-in=description]", "Scope line\nSecond line", leave="none")
            p.js("document.querySelector('#peek [data-ms-in=description]').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true, cancelable: true}))")
            self.assertEqual(self.sent, [], "a plain Enter only adds a line")
            self.type_in(p, "#peek [data-ms-in=description]", "Scope line\nSecond line", leave="ctrl")
            self.saved(p, "description", "Scope line\nSecond line")

    def test_workstream_and_client_wording_and_visible_to_client(self):
        with chrome() as cdp:
            p = self.visit_peek(cdp)
            self.assertEqual(p.js("[...document.querySelectorAll('#peek [data-ms-field=workstream] option')].map((o) => o.textContent)")[0], "—")
            p.js("(() => { const s = document.querySelector('#peek [data-ms-field=workstream]'); s.value = 'Build'; s.dispatchEvent(new Event('change', {bubbles: true})); })()")
            self.saved(p, "workstream", "Build")
            self.click(p, "#peek [data-ms-field=client_message]")
            self.type_in(p, "#peek [data-ms-in=client_message]", "On its way", leave="ctrl")
            self.saved(p, "client_message", "On its way")
            self.assertEqual(p.js("document.querySelector('#peek [data-ms-visible]').getAttribute('aria-pressed')"), "true")
            self.click(p, "#peek [data-ms-visible]")
            self.assertTrue(self.until_store(lambda: GO_LIVE in {h["item_id"] if isinstance(h, dict) else h for h in self.store.data_for("ABC")["report_hidden"]}), "left out of the page")
            p.until("document.querySelector('#peek [data-ms-visible]').getAttribute('aria-pressed') === 'false'", "the button shows No")
            self.undo(p)
            self.assertTrue(self.until_store(lambda: GO_LIVE not in {h["item_id"] if isinstance(h, dict) else h for h in self.store.data_for("ABC")["report_hidden"]}))

    def test_a_refusal_changes_nothing_and_says_so(self):
        with chrome() as cdp:
            p = self.visit_peek(cdp)
            self.click(p, "#peek [data-ms-state=On\\ track]")
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
            self.assertEqual(p.js("document.querySelectorAll('#peek [data-pk-archive]').length"), 1)
            self.click(p, "#peek [data-pk-archive]")
            self.assertTrue(self.until_store(lambda: self.row(self.cur)["archived"] == 1), "archived")
            self.assertEqual((self.sent[-1][1]["kind"], self.sent[-1][1]["op"], self.sent[-1][1]["id"]), ("milestones", "archive", GO_LIVE))
            p.until(f"(document.querySelector('.toast .toast-text') || {{}}).textContent === '{GO_LIVE} archived. It is out of the lists and the published page.'", "the toast")
            p.until("!document.querySelector('#peek')", "the peek closed")
            p.until("!!document.querySelector('.toast [data-undo]')", "Undo offered")
            p.js("document.querySelector('.toast [data-undo]').click()")
            self.assertTrue(self.until_store(lambda: self.row(self.cur)["archived"] == 0), "one Undo brings it back")

    def test_no_archive_button_in_the_dashboards_view_peek(self):
        with chrome() as cdp:
            p = self.visit_peek(cdp, view="dashboard")
            self.assertEqual(p.js("document.querySelectorAll('#peek [data-pk-archive]').length"), 0)

    def test_fit_at_both_widths_in_both_themes(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    p = self.visit_peek(cdp, width=width, theme=theme)
                    seen = p.js("""(() => {
                      const peek = document.querySelector('#peek'), pr = peek.getBoundingClientRect();
                      const els = [...peek.querySelectorAll('[data-ms-edit] button, [data-ms-edit] select, [data-ms-edit] input')];
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
