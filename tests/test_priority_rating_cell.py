"""#210 (option C), item 1182: a risk's or an issue's Priority cell opens the 3 x 3 matrix (impact down, likelihood across, one pick sets both), the two its priority is worked out from.

Run: python3 dev/run_tests.py test_priority_rating_cell
Part 1 runs the page's own rules (src/clark/page/src/edit/itemEdit.js) in headless Chrome: what a pick sends, what is refused in
the picker before anything is sent, and which kinds have the picker. Part 2 drives the committed page over a real server whose
`change` and `undo` are the real clark.changes over a real demo store (fictional data), at 1400 and 900 px in light and dark: the
cell opens the picker by a click and by the keyboard, a pick is one step with Undo, the cell then shows the priority clark worked
out, Esc leaves it as it was, a decision keeps its dash, and a click on the row away from the cell still opens the peek.
The browser parts are required: they fail, never skip, without Chrome (set CLARK_CHROME to its path).
"""
import contextlib
import json
import re
import unittest

import test_inline_edits as ie
from test_inline_edits import PAGE_SRC, click, dblclick, key, need_chrome
from test_server import chrome
from test_work_items import TODAY, bundled, page_target

RISK = {"id": "ABC-007", "kind": "risk", "owner": "TBC", "priority": "High", "impact": "High", "likelihood": "Medium", "status": "Open"}
WORDS = "Impact and likelihood are each High, Medium or Low, so nothing was changed. Pick one from the list."


# ---- part 1: the rules ----
class Rules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        need_chrome()
        cls.stack = contextlib.ExitStack()
        cls.cdp = cls.stack.enter_context(chrome())
        cls.sid = page_target(cls.cdp)
        res = cls.cdp.call("Runtime.evaluate", {"expression": bundled(PAGE_SRC / "edit" / "itemEdit.js", "E") + "; true", "returnByValue": True}, cls.sid)
        assert "exceptionDetails" not in res, res

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def js(self, expr):
        res = self.cdp.call("Runtime.evaluate", {"expression": expr, "returnByValue": True}, self.sid)
        self.assertNotIn("exceptionDetails", res, (expr, res))
        return res["result"].get("value")

    def change(self, row, value):
        return self.js(f"E.changeFor({json.dumps(row)}, 'priority', {json.dumps(value)}, {json.dumps(TODAY)})")

    def test_a_pick_sends_only_impact_or_likelihood_as_one_item(self):
        self.assertEqual(self.change(RISK, "likelihood:High"), {"changes": {"likelihood": "High"}, "words": "Likelihood of ABC-007 changed to High.",
                                                               "back": "Likelihood of ABC-007 is back to Medium.", "one": True})
        self.assertEqual(self.change({**RISK, "kind": "issue"}, "impact:Low"), {"changes": {"impact": "Low"}, "words": "Impact of ABC-007 changed to Low.",
                                                                               "back": "Impact of ABC-007 is back to High.", "one": True})
        self.assertEqual(self.change({**RISK, "impact": None}, "impact:Low")["back"], "Impact of ABC-007 is blank again.")
        self.assertIsNone(self.change(RISK, "impact:High"), "the value it has: nothing is sent")

    def test_a_matrix_pick_sends_both_fields_as_one_item(self):          # item 1182: the table cell's pick is "impact/likelihood"
        self.assertEqual(self.change(RISK, "Low/Low"), {"changes": {"impact": "Low", "likelihood": "Low"}, "words": "Impact and likelihood of ABC-007 changed to Low and Low.",
                                                       "back": "Impact and likelihood of ABC-007 are back to High and Medium.", "one": True})
        self.assertEqual(self.change({**RISK, "impact": None, "likelihood": None}, "High/Low")["back"], "Impact and likelihood of ABC-007 are back to blank and blank.")
        self.assertIsNone(self.change(RISK, "High/Medium"), "the two it has: nothing is sent")

    def test_each_bad_value_is_refused_in_the_picker_and_sends_nothing(self):
        for bad in ("Low", "impact:Urgent", "impact:low", "likelihood:", "impact: High", "priority:Low", "rating:Red", "", None, 3):
            with self.subTest(bad=bad):
                self.assertEqual(self.change(RISK, bad), {"error": WORDS})

    def test_only_a_risk_and_an_issue_have_the_picker(self):
        kinds = ["risk", "issue", "assumption", "dependency", "action", "decision"]
        self.assertEqual(self.js(f"{json.dumps(kinds)}.map(k => E.canPick({{...{json.dumps(RISK)}, kind: k}}, 'priority'))"), [True, True, False, False, True, False])
        self.assertEqual(self.js(f"{json.dumps(kinds)}.map(k => E.ratingGroups({{...{json.dumps(RISK)}, kind: k}}).length)"), [2, 2, 0, 0, 0, 0])
        g = self.js(f"E.ratingGroups({json.dumps(RISK)})")
        self.assertEqual([(x["heading"], x["current"], [c["value"] for c in x["choices"]]) for x in g],
                         [("Impact", "High", ["impact:High", "impact:Medium", "impact:Low"]), ("Likelihood", "Medium", ["likelihood:High", "likelihood:Medium", "likelihood:Low"])])
        self.assertEqual(self.js("E.LEVELS"), ["High", "Medium", "Low"])


# ---- part 2: the real page, the real routes, a real store ----
def _lum(rgb):
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def _rgb(css):
    return tuple(int(x) for x in re.findall(r"\d+", css)[:3])


def contrast(fg, bg):
    a, b = sorted((_lum(_rgb(fg)), _lum(_rgb(bg))), reverse=True)
    return (a + 0.05) / (b + 0.05)


class Live(unittest.TestCase):
    # the same real server, store and helpers as test_inline_edits (borrowed, so its own tests don't run twice)
    setUp, read, row, steps, open_page, until, cell_text, toast, focused, no_panel, undo, changed_once = (
        ie.Live.setUp, ie.Live.read, ie.Live.row, ie.Live.steps, ie.Live.open_page, ie.Live.until, ie.Live.cell_text,
        ie.Live.toast, ie.Live.focused, ie.Live.no_panel, ie.Live.undo, ie.Live.changed_once)

    def test_a_risks_priority_sets_impact_and_likelihood_in_place_light_and_dark(self):
        cell = "[data-cell='TUL-007:priority']"
        self.seen = []                                          # the history lines of the earlier runs (one store for all four)
        for scheme in ("light", "dark"):
            for width in (1400, 900):
                with self.subTest(scheme=scheme, width=width), chrome() as cdp:
                    where = f"{scheme} {width}"
                    sid = self.open_page(cdp, width, edit=False)        # Work items are always editable (#442)
                    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
                    self.until(cdp, sid, f"matchMedia('(prefers-color-scheme: {scheme})').matches", f"{where}: {scheme}")
                    dark = _lum(_rgb(cdp.js("getComputedStyle(document.body).backgroundColor", sid))) < 0.2
                    self.assertEqual(dark, scheme == "dark", f"{where}: the page is in {scheme}")
                    self.assertEqual(self.cell_text(cdp, sid, "TUL-007", "priority"), "High")
                    # by click: the 3 x 3 matrix (item 1182), the risk's own cell ticked and focused
                    before = self.steps()
                    click(cdp, sid, cell)
                    self.until(cdp, sid, "!!document.querySelector('[data-pop] [data-pk-matrix]')", f"{where}: the matrix opened")
                    got = cdp.js("[...document.querySelectorAll('[data-pop] [data-pk-cell]')].map(b => b.dataset.impact + '/' + b.dataset.likelihood + (b.getAttribute('aria-checked') === 'true' ? '*' : ''))", sid)
                    self.assertEqual(got, ["High/Low", "High/Medium*", "High/High", "Medium/Low", "Medium/Medium", "Medium/High", "Low/Low", "Low/Medium", "Low/High"], where)
                    self.assertEqual(self.cell_at(cdp, sid), "High/Medium", f"{where}: focus starts on the cell it has")
                    pop = cdp.js("(() => { const p = document.querySelector('[data-pop]'), h = p.querySelector('.pk-mx-head'), c = p.querySelector('[data-pk-cell]'), b = p.getBoundingClientRect();"
                                 " return [getComputedStyle(p).backgroundColor, getComputedStyle(h).color, getComputedStyle(c).color, getComputedStyle(c).backgroundColor, b.left >= 0 && b.right <= innerWidth, b.top >= 0 && b.bottom <= innerHeight]; })()", sid)
                    self.assertGreaterEqual(contrast(pop[1], pop[0]), 4.5, f"{where}: the axis words can be read ({pop})")
                    self.assertGreaterEqual(contrast(pop[2], pop[3]), 4.5, f"{where}: a cell can be read ({pop})")
                    self.assertEqual(_lum(_rgb(pop[0])) < 0.2, dark, f"{where}: the matrix follows the theme")
                    self.assertEqual(pop[4:], [True, True], f"{where}: the matrix is whole on screen")
                    click(cdp, sid, "[data-pop] [data-pk-cell][data-impact=High][data-likelihood=High]")
                    self.until(cdp, sid, "!!document.querySelector('[data-undo]')", f"{where}: the toast offers Undo")
                    r = self.row("raid", "TUL-007")
                    self.assertEqual((r["impact"], r["likelihood"], r["priority"]), ("High", "High", "Urgent"), where)
                    self.changed_once(before, where)
                    self.until(cdp, sid, f"document.querySelector(\"{cell}\").textContent === 'Urgent'", f"{where}: the cell shows the priority clark worked out")
                    self.assertEqual(self.toast(cdp, sid), "Impact and likelihood of TUL-007 changed to High and High. Its priority is now Urgent.")
                    self.assertEqual(self.sent[-1][1], {"project": "TUL", "kind": "raid", "op": "bulk", "ids": ["TUL-007"], "changes": {"impact": "High", "likelihood": "High"}, "place": "cell"})
                    self.assertNotIn("item=", cdp.js("location.hash", sid), f"{where}: a cell click never opens the peek")
                    self.assertTrue(self.no_panel(cdp, sid))
                    lines = [(e["before"], e["after"], e["place"], bool(e["by_user"]), bool(e["at"])) for e in self._history("TUL-007")
                             if e["field"] == "likelihood" and e["after"] == "High"]
                    self.assertEqual(lines[len(self.seen):], [("Medium", "High", "cell", True, True)], f"{where}: the history says who, how and when")
                    self.seen = lines
                    self.undo(cdp, sid, where, "Impact and likelihood of TUL-007 are back to High and Medium.")
                    r = self.row("raid", "TUL-007")
                    self.assertEqual((r["likelihood"], r["priority"]), ("Medium", "High"), f"{where}: one Undo puts both back")
                    self.until(cdp, sid, f"document.querySelector(\"{cell}\").textContent === 'High'", f"{where}: Undo draws the cell as it was")
                    # by keyboard: Enter opens on the ticked cell, Down moves, Enter picks; focus comes back to the cell
                    cdp.js(f"document.querySelector(\"{cell}\").focus()", sid)
                    key(cdp, sid, "Enter")
                    self.until(cdp, sid, "!!document.querySelector('[data-pop] [data-pk-matrix]')", f"{where}: Enter opens the matrix")
                    key(cdp, sid, "ArrowDown")
                    self.assertEqual(self.cell_at(cdp, sid), "Medium/Medium")
                    key(cdp, sid, "Enter")
                    self.until(cdp, sid, f"!!document.querySelector('[data-undo]') && document.querySelector(\"{cell}\").textContent === 'Medium'", f"{where}: the keyboard pick saved")
                    self.assertEqual(self.row("raid", "TUL-007")["impact"], "Medium")
                    self.until(cdp, sid, f"document.activeElement === document.querySelector(\"{cell}\")", f"{where}: focus is back on the cell")
                    self.undo(cdp, sid, f"{where} keyboard", "Impact and likelihood of TUL-007 are back to High and Medium.")
                    # Esc leaves it as it was, nothing sent
                    n, before = len(self.sent), self.steps()
                    cdp.js(f"document.querySelector(\"{cell}\").focus()", sid)
                    key(cdp, sid, "Enter")
                    self.until(cdp, sid, "!!document.querySelector('[data-pop] [data-pk-matrix]')", "open again")
                    key(cdp, sid, "ArrowDown")
                    key(cdp, sid, "Escape")
                    self.until(cdp, sid, "document.querySelectorAll('[data-pop]').length === 0", f"{where}: one Esc closes it")
                    self.assertEqual((len(self.sent), self.steps(), self.row("raid", "TUL-007")["impact"]), (n, before, "High"), f"{where}: Esc leaves it as it was")
                    # an issue has the picker too; an assumption and a decision do not
                    self.assertEqual(cdp.js("['TUL-010', 'TUL-009', 'TUL-D-016'].map(i => !!document.querySelector(`[data-cell='${i}:priority']`))", sid), [True, False, False], where)
                    self.assertEqual(cdp.js("document.querySelector(\"tr[data-id='TUL-D-016'] .c-prio\").textContent", sid), "—", f"{where}: a decision keeps its dash")
                    self.assertTrue(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), f"{where}: no sideways scroll")
                    # a double click on the row away from the cell still opens the peek
                    dblclick(cdp, sid, "tr[data-id='TUL-007'] .t")
                    self.until(cdp, sid, "location.hash.includes('item=TUL-007')", f"{where}: the row still opens the peek")

    def test_a_refusal_from_clark_is_said_and_nothing_changes(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400, edit=False)
            self.failure = lambda req: (400, {"ok": False, "message": "That choice isn't one clark has.", "code": "refused"})
            click(cdp, sid, "[data-cell='TUL-010:priority']")
            self.until(cdp, sid, "!!document.querySelector('[data-pop] [data-pk-matrix]')", "the matrix opened")
            click(cdp, sid, "[data-pop] [data-pk-cell][data-impact=Low][data-likelihood=Low]")
            self.until(cdp, sid, "(document.querySelector('.toast-text') || {}).textContent === \"That choice isn't one clark has.\"", "the refusal is said")
            self.assertEqual(self.row("raid", "TUL-010")["impact"], "High")
            self.assertEqual(self.cell_text(cdp, sid, "TUL-010", "priority"), "Urgent", "the cell is as clark has it")

    def cell_at(self, cdp, sid):
        return cdp.js("(a => a && a.dataset.impact ? a.dataset.impact + '/' + a.dataset.likelihood : '')(document.activeElement)", sid)

    def _history(self, ref):
        from clark.store import open_store
        st = open_store(self.path, onedrive_roots=[])
        try:
            return st.history(ref)
        finally:
            st.close()


if __name__ == "__main__":
    unittest.main()
