"""Item 1182 (and 1183, the same peek for an issue): the Risk peek's Rating chip and its 3 x 3 matrix. Run: python3 dev/run_tests.py test_peek_risk_1182

Part 1 runs the page's own rules (src/clark/page/src/edit/ratingMatrix.js) in headless Chrome and pins them to clark's rule (store.priority)
for all nine cells. Part 2 drives the committed page over a real server whose `change` and `undo` are the real clark.changes over a real demo
store (fictional data) at 1400 and 900 px: the chip says the colour and the level word, the matrix opens on the rating the item has, one click
sets impact AND likelihood in ONE change (one step, one Undo, one Activity line), the keys move along rows and columns, a closed item keeps its
rating ("Red kept"), the peek's Status picker offers Open, Closed and Cancelled only, and the sizes hold (text 12 px, targets 24 px).
test_peek_issue_1183 runs the same checks on an issue (it subclasses `Peek`).
The browser parts are required: they fail, never skip, without Chrome (set CLARK_CHROME to its path).
"""
import contextlib
import json
import unittest

import test_inline_edits as ie
from test_inline_edits import PAGE_SRC, click, dblclick, key, need_chrome
from test_server import chrome
from test_work_items import TODAY, bundled, page_target

from clark.store import priority as store_priority

LEVELS = ("High", "Medium", "Low")
COLOUR = {"Urgent": "Red", "High": "Red", "Medium": "Amber", "Low": "Green"}


class Rules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        need_chrome()
        cls.stack = contextlib.ExitStack()
        cls.cdp = cls.stack.enter_context(chrome())
        cls.sid = page_target(cls.cdp)
        res = cls.cdp.call("Runtime.evaluate", {"expression": bundled(PAGE_SRC / "edit" / "ratingMatrix.js", "M") + "; true", "returnByValue": True}, cls.sid)
        assert "exceptionDetails" not in res, res

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def js(self, expr):
        res = self.cdp.call("Runtime.evaluate", {"expression": expr, "returnByValue": True}, self.sid)
        self.assertNotIn("exceptionDetails", res, (expr, res))
        return res["result"].get("value")

    def test_the_nine_cells_are_clarks_own_rule_and_colour(self):
        for im in LEVELS:
            for li in LEVELS:
                with self.subTest(impact=im, likelihood=li):
                    level = store_priority(im, li)
                    cell = self.js(f"M.cellOf({json.dumps(im)}, {json.dumps(li)})")
                    self.assertEqual((cell["level"], cell["colour"]), (level, COLOUR[level]))
                    self.assertEqual(cell["label"], f"{im} impact, {li} likelihood: {level} ({COLOUR[level]})")

    def test_the_line_under_the_matrix_is_the_tickets_sentence(self):
        self.assertEqual(self.js("M.sentenceOf('High', 'Medium')"), "High impact, Medium likelihood: High (Red)")
        self.assertEqual(self.js("M.sentenceOf('High', 'High')"), "High impact, High likelihood: Urgent (Red)")
        self.assertEqual(self.js("M.sentenceOf('Low', 'Low')"), "Low impact, Low likelihood: Low (Green)")

    def test_the_axes_run_as_the_mockup_has_them(self):
        self.assertEqual(self.js("[M.IMPACTS, M.LIKELIHOODS]"), [["High", "Medium", "Low"], ["Low", "Medium", "High"]])

    def test_a_click_is_one_change_with_both_fields_and_the_same_cell_sends_nothing(self):
        row = {"id": "ABC-007", "kind": "risk", "impact": "High", "likelihood": "Medium", "priority": "High"}
        got = self.js(f"M.matrixChange({json.dumps(row)}, 'Low', 'Low')")
        self.assertEqual(got, {"changes": {"impact": "Low", "likelihood": "Low"}, "words": "ABC-007 rated Low (Green).", "back": "ABC-007 is back to High (Red)."})
        self.assertIsNone(self.js(f"M.matrixChange({json.dumps(row)}, 'High', 'Medium')"))
        self.assertIn("error", self.js(f"M.matrixChange({json.dumps(row)}, 'Urgent', 'Low')"))
        blank = {**row, "impact": None, "likelihood": None, "priority": None}
        self.assertEqual(self.js(f"M.matrixChange({json.dumps(blank)}, 'Low', 'Low')")["back"], "Rating of ABC-007 is blank again.")


class Peek:
    """The live checks for one kind; test_peek_issue_1183 sets the item. Not a TestCase itself, so it runs once per kind."""
    REF, KIND = "TUL-007", "risk"
    WORD, LEVEL = "Red", "High"                      # what the chip says before any pick
    FROM = ("High", "Medium")                        # its impact and likelihood
    CHOICE = ("Low", "Low")                          # a cell to pick, and what it works out to
    TO_LEVEL, TO_WORD = "Low", "Green"

    setUp, read, row, steps, open_page, until, toast, no_panel, undo, changed_once = (
        ie.Live.setUp, ie.Live.read, ie.Live.row, ie.Live.steps, ie.Live.open_page, ie.Live.until, ie.Live.toast, ie.Live.no_panel,
        ie.Live.undo, ie.Live.changed_once)

    def open_peek(self, cdp, width, scheme="light"):
        sid = self.open_page(cdp, width, edit=False)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
        dblclick(cdp, sid, f"tr[data-id='{self.REF}'] .t")
        self.until(cdp, sid, f"location.hash.includes('item={self.REF}') && !!document.querySelector('#peek [data-pk-pick=rating]')", "the peek opened with its Rating chip")
        return sid

    def chip_text(self, cdp, sid):
        return cdp.js("[document.querySelector('#peek [data-pk-rating-word]').textContent, (document.querySelector('#peek [data-pk-level]') || {textContent: ''}).textContent]", sid)

    def open_matrix(self, cdp, sid):
        click(cdp, sid, "#peek [data-pk-pick=rating]")
        self.until(cdp, sid, "!!document.querySelector('[data-pop][role=dialog] .mx')", "the matrix opened")

    def activity_rows(self, cdp, sid):
        return cdp.js("document.querySelectorAll('#peek [data-activity-row]').length", sid)

    def test_the_chip_says_the_colour_and_the_level_word_and_why(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_peek(cdp, width)
                self.assertEqual(self.chip_text(cdp, sid), [self.WORD, self.LEVEL])
                chip = cdp.js("(() => { const b = document.querySelector('#peek [data-pk-pick=rating]'), r = b.getBoundingClientRect();"
                              " return [b.dataset.tip, !!b.querySelector('svg'), r.height, b.getAttribute('aria-haspopup'), b.getAttribute('aria-label'),"
                              " document.querySelector('#peek [data-row=priority] dt').textContent]; })()", sid)
                self.assertEqual(chip[0], "Priority from impact and likelihood")
                self.assertTrue(chip[1], "the bars icon is there")
                self.assertGreaterEqual(chip[2], 24, "a target of 24 px at least")
                self.assertEqual(chip[3], "dialog")
                self.assertEqual(chip[4], f"Rating of {self.REF}: {self.WORD}, {self.LEVEL}. Change")
                self.assertEqual(chip[5], "Rating", "the row is called Rating, not Priority")

    def test_the_matrix_has_its_nine_cells_in_the_tickets_order_and_says_what_a_cell_means(self):
        for scheme in ("light", "dark"):
            with self.subTest(scheme=scheme), chrome() as cdp:
                sid = self.open_peek(cdp, 1400, scheme)
                self.open_matrix(cdp, sid)
                got = cdp.js("(() => { const m = document.querySelector('[data-pop] .mx');"
                             " return {cells: [...m.querySelectorAll('button.mc')].map(b => [b.dataset.impact, b.dataset.likelihood, b.textContent, b.getAttribute('aria-pressed')]),"
                             " rows: [...m.querySelectorAll('.mr')].map(e => e.textContent), cols: [...m.querySelectorAll('.mh')].map(e => e.textContent),"
                             " say: document.querySelector('[data-mx-say]').textContent, live: document.querySelector('[data-mx-say]').getAttribute('aria-live'),"
                             " focus: document.activeElement.dataset.impact + '/' + document.activeElement.dataset.likelihood,"
                             " tabstops: [...m.querySelectorAll('button.mc')].filter(b => b.tabIndex === 0).length}; })()", sid)
                self.assertEqual([c[:3] for c in got["cells"]], [
                    ["High", "Low", "High"], ["High", "Medium", "High"], ["High", "High", "Urgent"],
                    ["Medium", "Low", "Medium"], ["Medium", "Medium", "Medium"], ["Medium", "High", "High"],
                    ["Low", "Low", "Low"], ["Low", "Medium", "Medium"], ["Low", "High", "High"]])
                self.assertEqual([c[0] + "/" + c[1] for c in got["cells"] if c[3] == "true"], ["/".join(self.FROM)], "the cell the item has is the pressed one")
                self.assertEqual(got["rows"], ["High", "Medium", "Low"])
                self.assertEqual(got["cols"], ["Impact ↓", "Likelihood →", "Low", "Medium", "High"])
                self.assertEqual(got["say"], f"{self.FROM[0]} impact, {self.FROM[1]} likelihood: {self.LEVEL} ({self.WORD})")
                self.assertEqual(got["live"], "polite")
                self.assertEqual(got["focus"], "/".join(self.FROM), "focus starts on the cell the item has")
                self.assertEqual(got["tabstops"], 1, "one tab stop in the grid")
                # each cell shows its colour AND its word; the label carries both
                look = cdp.js("[...document.querySelectorAll('[data-pop] .mx button.mc')].map(b => [b.getAttribute('aria-label'), getComputedStyle(b).backgroundColor, getComputedStyle(b).color, b.getBoundingClientRect().width, b.getBoundingClientRect().height, parseFloat(getComputedStyle(b).fontSize)])", sid)
                self.assertEqual(look[2][0], "High impact, High likelihood: Urgent (Red)")
                self.assertEqual(len({c[1] for c in look}), 4, "Urgent, Red, Amber and Green are four different looks")
                for c in look:
                    self.assertGreaterEqual(min(c[3], c[4]), 24, c)
                    self.assertGreaterEqual(c[5], 12, c)

    def test_one_click_sets_impact_and_likelihood_in_one_change_with_one_undo_and_one_activity_line(self):
        self.one_click(1400)

    def test_one_click_is_one_change_at_900(self):                              # its own test: each one starts on a fresh store
        self.one_click(900)

    def one_click(self, width):
        if True:
            with chrome() as cdp:
                self.sent.clear()
                sid = self.open_peek(cdp, width)
                click(cdp, sid, "#peek [data-pk-tab=activity]")
                self.until(cdp, sid, "!!document.querySelector('#peek [data-pk-tab=activity].on') && !document.querySelector('#peek').textContent.includes('Reading the history')", "the Activity tab opened and read")
                lines = self.activity_rows(cdp, sid)
                click(cdp, sid, "#peek [data-pk-tab=details]")
                before = self.steps()
                self.open_matrix(cdp, sid)
                click(cdp, sid, f"[data-pop] button.mc[data-impact='{self.CHOICE[0]}'][data-likelihood='{self.CHOICE[1]}']")
                self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "the toast offers Undo")
                self.changed_once(before, "one click")
                r = self.row("raid", self.REF)
                self.assertEqual((r["impact"], r["likelihood"], r["priority"]), (*self.CHOICE, self.TO_LEVEL))
                asks = [req for which, req in self.sent if req.get("kind") == "raid"]
                self.assertEqual(len(asks), 1, f"one request, not two: {asks}")
                self.assertEqual(asks[0]["changes"], {"impact": self.CHOICE[0], "likelihood": self.CHOICE[1]})
                self.assertEqual(asks[0]["place"], "peek")
                self.assertEqual(self.toast(cdp, sid), f"{self.REF} rated {self.TO_LEVEL} ({self.TO_WORD}).")
                self.until(cdp, sid, f"document.querySelector('#peek [data-pk-rating-word]').textContent === {json.dumps(self.TO_WORD)}", "the chip shows the new colour")
                self.assertEqual(self.chip_text(cdp, sid), [self.TO_WORD, self.TO_LEVEL])
                self.assertTrue(self.no_panel(cdp, sid), "the matrix closed")
                self.assertTrue(cdp.js("document.activeElement.matches('[data-pk-pick=rating]')", sid), "focus is back on the chip")
                click(cdp, sid, "#peek [data-pk-tab=activity]")
                self.until(cdp, sid, f"document.querySelectorAll('#peek [data-activity-row]').length > {lines} && !document.querySelector('#peek').textContent.includes('Reading the history')", "the Activity tab has a new line")
                self.assertEqual(self.activity_rows(cdp, sid), lines + 1, "one Activity line for the step (not one for impact, one for likelihood and one for priority)")
                click(cdp, sid, "#peek [data-pk-tab=details]")
                self.undo(cdp, sid, "the matrix pick", f"{self.REF} is back to {self.LEVEL} ({self.WORD}).")
                r = self.row("raid", self.REF)
                self.assertEqual((r["impact"], r["likelihood"], r["priority"]), (*self.FROM, self.LEVEL), "one Undo puts both back")
                self.until(cdp, sid, f"document.querySelector('#peek [data-pk-rating-word]').textContent === {json.dumps(self.WORD)}", "Undo draws the chip as it was")

    def test_the_keys_move_along_rows_and_columns_stop_at_the_edge_pick_with_enter_and_leave_with_esc(self):
        with chrome() as cdp:
            self.sent.clear()
            sid = self.open_peek(cdp, 1400)
            shown = cdp.js("location.hash", sid)
            self.open_matrix(cdp, sid)
            at = lambda: cdp.js("document.activeElement.dataset.impact + '/' + document.activeElement.dataset.likelihood", sid)
            say = lambda: cdp.js("document.querySelector('[data-mx-say]').textContent", sid)
            key(cdp, sid, "Home")
            self.assertEqual(at(), f"{self.FROM[0]}/Low")
            key(cdp, sid, "ArrowLeft")
            self.assertEqual(at(), f"{self.FROM[0]}/Low", "no wrap at the left edge")
            key(cdp, sid, "End")
            self.assertEqual(at(), f"{self.FROM[0]}/High")
            key(cdp, sid, "ArrowRight")
            self.assertEqual(at(), f"{self.FROM[0]}/High", "no wrap at the right edge")
            key(cdp, sid, "ArrowUp")
            key(cdp, sid, "ArrowUp")
            self.assertEqual(at(), "High/High", "no wrap at the top")
            key(cdp, sid, "ArrowDown")
            key(cdp, sid, "ArrowDown")
            key(cdp, sid, "ArrowDown")
            self.assertEqual(at(), "Low/High", "no wrap at the bottom")
            self.assertEqual(say(), "Low impact, High likelihood: High (Red)", "the live line follows the cell the focus is on")
            self.assertEqual(cdp.js("location.hash", sid), shown, "Up and Down did not step the peek to another item while the matrix was open")
            self.assertEqual(len(self.sent), 0, "moving sends nothing")
            key(cdp, sid, "Escape")
            self.until(cdp, sid, "document.querySelectorAll('[data-pop]').length === 0", "one Esc closes the matrix")
            self.assertTrue(cdp.js("document.activeElement.matches('[data-pk-pick=rating]')", sid), "focus is back on the chip")
            self.assertIn(f"item={self.REF}", cdp.js("location.hash", sid), "Esc closed the matrix, not the peek")
            self.assertEqual((len(self.sent), self.row("raid", self.REF)["impact"]), (0, self.FROM[0]), "Esc leaves it as it was")
            # Enter on a cell picks it
            before = self.steps()
            key(cdp, sid, "Enter")                                   # the chip is focused: Enter opens it
            self.until(cdp, sid, "!!document.querySelector('[data-pop][role=dialog] .mx')", "Enter opened the matrix")
            key(cdp, sid, "End")
            key(cdp, sid, "ArrowDown")
            key(cdp, sid, "Enter")
            self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "Enter picked a cell")
            self.changed_once(before, "a key pick")
            r = self.row("raid", self.REF)
            self.assertEqual((r["impact"], r["likelihood"]), ("Medium", "High"), "End then Down is Medium impact, High likelihood")

    def test_the_peeks_status_picker_has_open_closed_and_cancelled_only_and_a_closed_item_keeps_its_rating(self):
        self.status_at(1400)

    def test_the_peeks_status_picker_and_the_kept_rating_at_900(self):          # its own test: each one starts on a fresh store, and the first leaves the item closed
        self.status_at(900)

    def status_at(self, width):
        if True:
            with chrome() as cdp:
                sid = self.open_peek(cdp, width)
                cell = f"[data-cell='peek:{self.REF}:status']"
                click(cdp, sid, cell)
                self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "the status picker opened")
                got = cdp.js("[...document.querySelectorAll('[data-pop] [role=menuitemradio]')].map(b => b.textContent + (b.getAttribute('aria-checked') === 'true' ? '*' : ''))", sid)
                self.assertEqual(got, ["Open*", "Closed", "Cancelled"], "no Red, Amber or Green in the peek's Status picker")
                self.assertEqual(cdp.js("document.querySelectorAll('[data-pop] [role=group]').length", sid), 0, "no Rating section either")
                click(cdp, sid, "[data-pop] [data-value='Closed']")
                self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "Closed saved")
                r = self.row("raid", self.REF)
                self.assertEqual((r["status"], r["impact"], r["likelihood"]), ("Closed", *self.FROM), "closing changes the status and nothing else")
                self.until(cdp, sid, "!!document.querySelector('#peek [data-pk-rating]')", "the sub-line is there")
                self.assertEqual(cdp.js("document.querySelector('#peek [data-pk-rating]').textContent.trim()", sid), f"{self.WORD} kept")
                self.assertEqual(self.chip_text(cdp, sid), [self.WORD, self.LEVEL], "the Rating chip keeps its colour and level")

    def test_the_other_pickers_and_the_tables_own_cell_are_as_they_were(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400, edit=False)
            click(cdp, sid, f"[data-cell='{self.REF}:status']")
            self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "the table's status picker opened")
            got = cdp.js("[...document.querySelectorAll('[data-pop] [role=menuitemradio]')].map(b => b.dataset.value)", sid)
            self.assertEqual(got, ["Open", "Closed", "Cancelled", "rating:Red", "rating:Amber", "rating:Green"], "item 1182 is the peek's; the list's cell is not changed here")


class RiskPeek(Peek, unittest.TestCase):
    pass


if __name__ == "__main__":
    unittest.main()
