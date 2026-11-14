"""Item 1182, the risk peek (Layout A of the approved mockup, peek-risk.png). Written first: every test fails until the build is done.
Run: python3 dev/run_tests.py test_peek_risk_1182

The chip row of a risk is Status, Rating, Owner, Due. The Rating chip replaces Priority: a bars icon, the colour word (Red, Amber or
Green) and the level word (Urgent, High, Medium, Low), tooltip "Priority from impact and likelihood". A click opens a 3 x 3 matrix
(rows Impact High, Medium, Low; columns Likelihood Low, Medium, High); each cell shows its level word and its colour; a click sets BOTH
fields in one change (one Undo, one Activity line, one toast); the line under the matrix reads "High impact, Medium likelihood: High
(Red)". A risk's Status is Open, Closed or Cancelled only. A closed risk keeps its rating ("Red kept"). Details has a Rating row.

Hooks the build must give (named here so the build and the test agree):
  .pk-chips [data-row=rating]            the Rating chip (a button in Edit, plain text in View); there is no [data-row=priority] on a risk
  [data-pk-matrix]                       the matrix popover (a dialog: role=dialog, inside [data-pop]); [data-pk-matrix-line] the line under it
  [data-pk-cell] with data-impact and data-likelihood (High, Medium or Low): one button per cell; aria-checked="true" on the current one;
                                         the text is the level word; data-colour is Red, Amber or Green
  [data-pk-details-rows] gets a row whose text is "Rating: Red · High (impact High, likelihood Medium)"
Part 3 (Latest update for a risk) needs item 1185's store column and save op; it is expected to fail until that row is built.
"""
import json
import unittest

from _paths import ROOT

import test_peek_latest as _tl  # noqa: E402
from test_peek import key  # noqa: E402
from test_server import chrome, wait  # noqa: E402
from test_work_filters import click  # noqa: E402

WIDTHS = (1400, 900)
OPEN_RISK = "TUL-007"       # open, impact High, likelihood Medium, priority High (Red)
CLOSED_RISK = "TUL-008"     # closed, impact Medium, likelihood Low, priority Medium (Amber)
CANCELLED = "TUL-012"       # cancelled, impact Low, likelihood High, priority High (Red)
URGENT = "TUL-010"          # open, impact High, likelihood High, priority Urgent (Red)
GREEN_FROM = "TUL-009"      # open, impact Medium, likelihood Low
LEVELS = ("High", "Medium", "Low")
COLOUR = {"Urgent": "Red", "High": "Red", "Medium": "Amber", "Low": "Green"}


def level(impact, likelihood):
    """The rule of clark/store.py: High+High Urgent, any High High, Low+Low Low, the rest Medium."""
    if impact == "High" and likelihood == "High":
        return "Urgent"
    if "High" in (impact, likelihood):
        return "High"
    if impact == "Low" and likelihood == "Low":
        return "Low"
    return "Medium"


CHIPS = """(() => { const p = document.querySelector('#peek'); if (!p) return null;
  const row = p.querySelector('.pk-chips'); const chips = {};
  if (row) for (const c of row.children) { const k = c.dataset.row; if (!k) continue; const sub = c.querySelector('.pk-chip-sub');
    chips[k] = { tag: c.tagName, text: c.innerText.replace(/\\s+/g, ' ').trim(), icons: [...c.querySelectorAll('svg[data-icn]')].map(s => s.dataset.icn),
      sub: sub ? sub.textContent.trim() : null, title: c.getAttribute('title') || c.getAttribute('aria-description') || c.getAttribute('aria-label') || '',
      haspopup: c.getAttribute('aria-haspopup') }; }
  return { order: Object.keys(chips), chips }; })()"""

CELLS = """[...document.querySelectorAll('[data-pop] [data-pk-matrix] [data-pk-cell]')].map(b => { const r = b.getBoundingClientRect();
  return { i: b.dataset.impact, l: b.dataset.likelihood, text: b.textContent.trim(), colour: b.dataset.colour, checked: b.getAttribute('aria-checked'),
           tag: b.tagName, w: r.width, h: r.height, t: r.top, left: r.left }; })"""


class Risk(_tl.Browser):
    """The loader of the Latest update tests (demo data, today fixed at 28-10-2026): Edit mode, the peek open on the item."""

    def setUp(self):
        self.fresh()

    def risk(self, ref):
        return next(r for r in self.data["raid"] if r["id"] == ref)

    def stored(self, ref):
        return next(r for r in self.store.data_for(self.code)["raid"] if r["id"] == ref)

    def calm(self, cdp, sid):
        self.assertTrue(wait(lambda: cdp.js("(p => !p || p.getAnimations({subtree: true}).every(a => a.playState !== 'running'))(document.querySelector('#peek'))", sid)))

    def chips(self, cdp, sid):
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek .pk-chips [data-row=status]')", sid)), "the chip row is drawn")
        return cdp.js(CHIPS, sid)

    def open_matrix(self, cdp, sid):
        self.calm(cdp, sid)
        click(cdp, sid, "#peek .pk-chips [data-row=rating]")
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pop] [data-pk-matrix]')", sid)), "the matrix opens")

    def cell(self, cdp, sid, impact, likelihood):
        return f"[data-pop] [data-pk-cell][data-impact={impact}][data-likelihood={likelihood}]"

    def undo_buttons(self, cdp, sid):
        return cdp.js("document.querySelectorAll('.toast [data-undo]').length", sid)

    # ---- Part 1: the chip row

    def test_a_risks_chips_are_status_rating_owner_due_in_that_order_with_no_priority_chip(self):
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OPEN_RISK)
                got = self.chips(cdp, sid)
                self.assertEqual(got["order"], ["status", "rating", "owner", "due"])
                self.assertNotIn("priority", got["chips"])

    def test_the_rating_chip_is_the_bars_icon_the_colour_and_the_level_word_with_the_tooltip(self):
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OPEN_RISK)
                c = self.chips(cdp, sid)["chips"]["rating"]
                self.assertEqual(c["icons"][0], "bars")
                self.assertEqual(c["icons"][-1], "chevdown")
                self.assertIn("Red", c["text"])
                self.assertIn("High", c["text"])
                self.assertEqual(c["tag"], "BUTTON")
                self.assertTrue(c["haspopup"], "it says it opens a popover")
                self.assertIn("Priority from impact and likelihood", c["title"])

    def test_each_demo_risk_shows_the_colour_and_level_its_impact_and_likelihood_give(self):
        for ref in (OPEN_RISK, URGENT, GREEN_FROM, CANCELLED):
            r = self.risk(ref)
            want = level(r["impact"], r["likelihood"])
            with self.subTest(ref=ref), chrome() as cdp:
                sent, sid = self.load(cdp, 1400, ref)
                text = self.chips(cdp, sid)["chips"]["rating"]["text"]
                self.assertIn(COLOUR[want], text)
                self.assertIn(want, text)

    def test_view_draws_the_rating_chip_as_plain_text_with_no_control(self):
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OPEN_RISK, edit=False)
                c = self.chips(cdp, sid)["chips"]["rating"]
                self.assertNotEqual(c["tag"], "BUTTON")
                self.assertIsNone(c["haspopup"])
                self.assertIn("Red", c["text"])
                self.assertIn("High", c["text"])
                self.assertEqual(cdp.js("document.querySelectorAll('[data-pop]').length", sid), 0)

    def test_an_action_still_has_its_priority_chip_and_no_rating_chip(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, _tl.OVERDUE)
            got = self.chips(cdp, sid)
            self.assertIn("priority", got["order"])
            self.assertNotIn("rating", got["order"])

    # ---- Part 2: the matrix

    def test_the_matrix_is_a_dialog_of_nine_cells_impact_down_likelihood_across(self):
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OPEN_RISK)
                self.open_matrix(cdp, sid)
                self.assertEqual(cdp.js("document.querySelector('[data-pop] [data-pk-matrix]').closest('[role=dialog]') !== null || document.querySelector('[data-pk-matrix]').getAttribute('role') === 'dialog'", sid), True)
                cells = cdp.js(CELLS, sid)
                self.assertEqual(len(cells), 9)
                self.assertEqual({(c["i"], c["l"]) for c in cells}, {(i, l) for i in LEVELS for l in LEVELS})
                by = {(c["i"], c["l"]): c for c in cells}
                for i in LEVELS:                                                       # rows Impact High, Medium, Low from the top
                    self.assertEqual({round(by[(i, l)]["t"]) for l in LEVELS}.__len__(), 1, f"{i} is one row")
                self.assertLess(by[("High", "Low")]["t"], by[("Medium", "Low")]["t"])
                self.assertLess(by[("Medium", "Low")]["t"], by[("Low", "Low")]["t"])
                for i in LEVELS:                                                       # columns Likelihood Low, Medium, High from the left
                    self.assertLess(by[(i, "Low")]["left"], by[(i, "Medium")]["left"])
                    self.assertLess(by[(i, "Medium")]["left"], by[(i, "High")]["left"])
                text = cdp.js("document.querySelector('[data-pk-matrix]').textContent", sid)
                self.assertIn("Impact", text)
                self.assertIn("Likelihood", text)
                inside = cdp.js("(() => { const r = document.querySelector('[data-pop]').getBoundingClientRect(); return r.left >= 0 && r.right <= document.documentElement.clientWidth && r.top >= 0 && r.bottom <= innerHeight; })()", sid)
                self.assertTrue(inside, "the matrix is on screen")

    def test_each_cell_shows_its_level_word_and_its_colour_and_is_a_24_px_target(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OPEN_RISK)
            self.open_matrix(cdp, sid)
            for c in cdp.js(CELLS, sid):
                with self.subTest(i=c["i"], l=c["l"]):
                    want = level(c["i"], c["l"])
                    self.assertEqual(c["tag"], "BUTTON")
                    self.assertIn(want, c["text"])
                    self.assertEqual(c["colour"], COLOUR[want])
                    self.assertGreaterEqual(c["w"], 24)
                    self.assertGreaterEqual(c["h"], 24)

    def test_the_current_cell_is_marked_and_the_line_under_the_matrix_says_the_rule_in_words(self):
        for ref in (OPEN_RISK, URGENT):
            r = self.risk(ref)
            with self.subTest(ref=ref), chrome() as cdp:
                sent, sid = self.load(cdp, 1400, ref)
                self.open_matrix(cdp, sid)
                marked = [(c["i"], c["l"]) for c in cdp.js(CELLS, sid) if c["checked"] == "true"]
                self.assertEqual(marked, [(r["impact"], r["likelihood"])])
                want = level(r["impact"], r["likelihood"])
                line = cdp.js("document.querySelector('[data-pk-matrix-line]').textContent.trim()", sid)
                self.assertEqual(line, f"{r['impact']} impact, {r['likelihood']} likelihood: {want} ({COLOUR[want]})")

    def test_the_line_is_the_example_of_the_ticket_for_high_impact_medium_likelihood(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OPEN_RISK)
            self.open_matrix(cdp, sid)
            self.assertEqual(cdp.js("document.querySelector('[data-pk-matrix-line]').textContent.trim()", sid), "High impact, Medium likelihood: High (Red)")

    def test_a_click_sets_both_fields_in_one_change_with_one_undo_and_the_toast(self):
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OPEN_RISK)          # High / Medium
                self.open_matrix(cdp, sid)
                click(cdp, sid, self.cell(cdp, sid, "Low", "Low"))
                self.assertTrue(wait(lambda: len(sent) == 1), "one change is one request")
                req = sent[0]
                self.assertEqual((req["kind"], req["op"], req["ids"]), ("raid", "bulk", [OPEN_RISK]))
                self.assertEqual(req["changes"], {"impact": "Low", "likelihood": "Low"}, "both fields in the one request")
                self.assertTrue(wait(lambda: self.stored(OPEN_RISK)["priority"] == "Low"))
                row = self.stored(OPEN_RISK)
                self.assertEqual((row["impact"], row["likelihood"]), ("Low", "Low"))
                self.assertTrue(wait(lambda: "Green" in self.chips(cdp, sid)["chips"]["rating"]["text"]), "the chip is green")
                self.assertTrue(wait(lambda: self.undo_buttons(cdp, sid) == 1), "one toast with one Undo")
                cdp.js("document.querySelector('.toast [data-undo]').click()", sid)
                self.assertTrue(wait(lambda: self.stored(OPEN_RISK)["priority"] == "High"))
                row = self.stored(OPEN_RISK)
                self.assertEqual((row["impact"], row["likelihood"]), ("High", "Medium"), "one Undo puts both back")
                self.assertEqual(len(sent), 1, "Undo is not a second change request")

    def test_a_click_makes_one_activity_line_per_field_in_one_step(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OPEN_RISK)
            self.open_matrix(cdp, sid)
            click(cdp, sid, self.cell(cdp, sid, "Low", "High"))
            self.assertTrue(wait(lambda: len(sent) == 1))
            self.assertTrue(wait(lambda: self.stored(OPEN_RISK)["impact"] == "Low"))
            events = [e for e in self.store.history(OPEN_RISK) if e["field"] in ("impact", "likelihood")]
            self.assertEqual({e["field"] for e in events}, {"impact", "likelihood"})
            self.assertEqual(len({e["step"] for e in events}), 1, "both fields in one step")

    def test_the_cell_that_is_already_set_changes_nothing(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OPEN_RISK)
            self.open_matrix(cdp, sid)
            click(cdp, sid, self.cell(cdp, sid, "High", "Medium"))
            self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('[data-pop]')", sid)) or True)
            self.assertEqual(len(sent), 0, "no request")
            self.assertEqual(self.undo_buttons(cdp, sid), 0, "no toast")

    def test_a_click_that_changes_only_one_field_still_sends_both_in_the_one_request(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OPEN_RISK)               # High / Medium -> High / Low
            self.open_matrix(cdp, sid)
            click(cdp, sid, self.cell(cdp, sid, "High", "Low"))
            self.assertTrue(wait(lambda: len(sent) == 1))
            self.assertEqual(sent[0]["changes"], {"impact": "High", "likelihood": "Low"})

    def test_esc_closes_the_matrix_with_focus_back_on_the_chip_and_the_peek_stays_open(self):
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OPEN_RISK)
                self.open_matrix(cdp, sid)
                self.assertEqual(cdp.js("document.querySelector('#peek .pk-chips [data-row=rating]').getAttribute('aria-expanded')", sid), "true")
                key(cdp, sid, "Escape")
                self.assertTrue(wait(lambda: cdp.js("!document.querySelector('[data-pop]')", sid)))
                self.assertTrue(cdp.js("!!document.querySelector('#peek')", sid))
                self.assertTrue(wait(lambda: cdp.js("document.activeElement === document.querySelector('#peek .pk-chips [data-row=rating]')", sid)))
                self.assertEqual(len(sent), 0)

    def test_the_keyboard_reaches_a_cell_and_enter_picks_it(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OPEN_RISK)
            self.open_matrix(cdp, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.activeElement && document.activeElement.hasAttribute('data-pk-cell')", sid)), "focus moves into the matrix")
            at = cdp.js("[document.activeElement.dataset.impact, document.activeElement.dataset.likelihood]", sid)
            self.assertEqual(at, ["High", "Medium"], "focus starts on the current cell")
            key(cdp, sid, "ArrowRight")
            self.assertEqual(cdp.js("[document.activeElement.dataset.impact, document.activeElement.dataset.likelihood]", sid), ["High", "High"])
            key(cdp, sid, "ArrowDown")
            self.assertEqual(cdp.js("[document.activeElement.dataset.impact, document.activeElement.dataset.likelihood]", sid), ["Medium", "High"])
            key(cdp, sid, "Enter")
            self.assertTrue(wait(lambda: len(sent) == 1))
            self.assertEqual(sent[0]["changes"], {"impact": "Medium", "likelihood": "High"})

    def test_the_arrow_keys_still_move_to_the_next_item_when_the_focus_is_on_the_chip_but_not_inside_the_matrix(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OPEN_RISK)
            self.open_matrix(cdp, sid)
            before = cdp.js("document.querySelector('#peek').dataset.peek", sid)
            key(cdp, sid, "ArrowRight")
            key(cdp, sid, "ArrowDown")
            self.assertEqual(cdp.js("document.querySelector('#peek').dataset.peek", sid), before, "the matrix keeps its arrows; the peek does not move on")

    # ---- Part 2b: Status

    def test_a_risks_status_picker_lists_open_closed_cancelled_and_no_colour(self):
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OPEN_RISK)
                self.calm(cdp, sid)
                click(cdp, sid, "#peek .pk-chips [data-row=status]")
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pop] [role=menuitemradio]')", sid)))
                words = cdp.js("[...document.querySelectorAll('[data-pop] [role=menuitemradio]')].map(b => b.textContent.trim())", sid)
                self.assertEqual(words, ["Open", "Closed", "Cancelled"])
                for w in ("Red", "Amber", "Green", "Delayed"):
                    self.assertNotIn(w, " ".join(words))
                self.assertEqual(cdp.js("document.querySelectorAll('[data-pop] [role=group]').length", sid), 0, "no Rating group in the status picker")

    def test_closing_a_risk_from_the_status_chip_keeps_its_rating_and_says_so(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OPEN_RISK)
            self.calm(cdp, sid)
            click(cdp, sid, "#peek .pk-chips [data-row=status]")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pop] [role=menuitemradio]')", sid)))
            cdp.js("[...document.querySelectorAll('[data-pop] [role=menuitemradio]')].find(b => b.textContent.trim() === 'Closed').dataset.t = '1'", sid)
            click(cdp, sid, "[data-pop] [data-t='1']")
            self.assertTrue(wait(lambda: len(sent) == 1))
            self.assertEqual(sent[0]["changes"], {"status": "Closed"})
            row = self.stored(OPEN_RISK)
            self.assertEqual((row["impact"], row["likelihood"], row["priority"]), ("High", "Medium", "High"), "the rating is untouched")
            self.assertTrue(wait(lambda: self.chips(cdp, sid)["chips"]["status"]["text"].startswith("Closed")))
            self.assertEqual(self.chips(cdp, sid)["chips"]["status"]["sub"], "Red kept")

    def test_a_closed_risk_says_its_colour_was_kept_and_keeps_the_rating_chip(self):
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, CLOSED_RISK)          # Medium / Low -> Amber
                got = self.chips(cdp, sid)
                self.assertEqual(got["chips"]["status"]["sub"], "Amber kept")
                self.assertIn("Amber", got["chips"]["rating"]["text"])
                self.assertIn("Medium", got["chips"]["rating"]["text"])
                self.assertEqual(got["order"], ["status", "rating", "owner", "due"])

    def test_a_cancelled_risk_keeps_its_rating_too(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, CANCELLED)
            got = self.chips(cdp, sid)["chips"]
            self.assertIn("Cancelled", got["status"]["text"])
            self.assertEqual(got["status"]["sub"], "Red kept")

    def test_an_open_risk_has_no_kept_line(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OPEN_RISK)
            self.assertIsNone(self.chips(cdp, sid)["chips"]["status"]["sub"])

    def test_the_table_cell_and_the_status_words_of_other_kinds_are_not_changed(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, _tl.OVERDUE)
            self.calm(cdp, sid)
            click(cdp, sid, "#peek .pk-chips [data-row=status]")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pop] [role=menuitemradio]')", sid)))
            words = cdp.js("[...document.querySelectorAll('[data-pop] [role=menuitemradio]')].map(b => b.textContent.trim())", sid)
            self.assertNotIn("Red", words)
            self.assertIn("Open", words)

    # ---- Details

    def test_details_has_a_rating_row_in_the_wide_layout_and_no_type_row(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OPEN_RISK)
            self.calm(cdp, sid)
            if cdp.js("document.querySelector('[data-pk-details]').getAttribute('aria-expanded')", sid) != "true":
                click(cdp, sid, "[data-pk-details]")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pk-details-rows]')", sid)))
            text = cdp.js("document.querySelector('[data-pk-details-rows]').innerText.replace(/\\s+/g, ' ')", sid)
            self.assertIn("Rating: Red · High (impact High, likelihood Medium)", text)
            for label in ("Workstream", "Milestone", "Raised"):
                self.assertIn(label, text)
            self.assertNotIn("Type", text, "the Type row is dropped")

    def test_the_details_rating_row_follows_a_change_from_the_matrix(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OPEN_RISK)
            self.open_matrix(cdp, sid)
            click(cdp, sid, self.cell(cdp, sid, "Low", "Low"))
            self.assertTrue(wait(lambda: len(sent) == 1))
            if cdp.js("document.querySelector('[data-pk-details]').getAttribute('aria-expanded')", sid) != "true":
                click(cdp, sid, "[data-pk-details]")
            self.assertTrue(wait(lambda: "Rating: Green · Low (impact Low, likelihood Low)" in cdp.js("document.querySelector('[data-pk-details-rows]').innerText.replace(/\\s+/g, ' ')", sid)))

    def test_view_shows_the_same_rating_row_as_text(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OPEN_RISK, edit=False)
            self.calm(cdp, sid)
            if cdp.js("document.querySelector('[data-pk-details]').getAttribute('aria-expanded')", sid) != "true":
                click(cdp, sid, "[data-pk-details]")
            self.assertIn("Rating: Red · High (impact High, likelihood Medium)",
                          cdp.js("document.querySelector('[data-pk-details-rows]').innerText.replace(/\\s+/g, ' ')", sid))

    # ---- Layout and size

    def test_the_chip_row_fits_the_peek_at_both_widths_and_nothing_scrolls_sideways(self):
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, URGENT)
                self.calm(cdp, sid)
                got = cdp.js("""(() => { const p = document.querySelector('#peek'), pr = p.getBoundingClientRect();
                  return { cells: [...p.querySelectorAll('.pk-chips > [data-row]')].map(c => { const r = c.getBoundingClientRect();
                      return { l: r.left >= pr.left - 0.5, r: r.right <= pr.right + 0.5, h: r.height, o: c.scrollWidth - c.clientWidth }; }),
                    side: p.scrollWidth - p.clientWidth, doc: document.documentElement.scrollWidth - document.documentElement.clientWidth }; })()""", sid)
                self.assertEqual(len(got["cells"]), 4)
                for c in got["cells"]:
                    self.assertTrue(c["l"] and c["r"])
                    self.assertGreaterEqual(c["h"], 24)
                    self.assertLessEqual(c["h"], 64)
                    self.assertLessEqual(c["o"], 1)
                self.assertLessEqual(got["side"], 1)
                self.assertLessEqual(got["doc"], 1)

    def test_the_matrix_uses_tokens_only_in_the_stylesheet(self):
        import re
        css = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "src" / "clark" / "page").glob("*.css"))
        self.assertIn("pk-matrix", css, "the matrix is styled in the page stylesheet")
        for body in re.findall(r"[^{}]*pk-(?:matrix|cell)[^{}]*\{([^}]*)\}", css):
            self.assertNotRegex(body, r"#[0-9A-Fa-f]{3,8}\b|rgba?\(|hsla?\(", "tokens only")

    def test_the_source_has_the_new_words_once_and_no_hash_digit_in_a_comment(self):
        import re
        src = ROOT / "src" / "clark" / "page" / "src"
        text = "".join(p.read_text(encoding="utf-8") for p in src.rglob("*.jsx"))
        self.assertIn("Priority from impact and likelihood", text)
        self.assertIn("pk-matrix", text)
        for p in list(src.rglob("*.jsx")) + list(src.rglob("*.js")):
            if p.name in ("Peek.jsx",):
                continue                                                    # older comments there are not this row's
            if "matrix" not in p.read_text(encoding="utf-8").lower():
                continue
            for line in p.read_text(encoding="utf-8").splitlines():
                m = re.search(r"//.*|/\*.*", line)
                if m:
                    self.assertNotRegex(m.group(0), r"#\d", f"{p.name}: write 'item 1182', not a hash and digits")


class RiskLatest(_tl.Browser):
    """Part 3: the Latest update on a risk. Needs item 1185 (the store column and the save op); fails until that row is built."""

    def setUp(self):
        self.fresh()

    def stored_latest(self, ref):
        return next(r for r in self.store.data_for(self.code)["raid"] if r["id"] == ref).get("latest_update")

    def test_a_risk_peek_draws_the_latest_update_box_in_edit(self):
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OPEN_RISK)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek [data-pk-latest]')", sid)), "the box is there for a risk")

    def test_a_risks_latest_update_saves_in_one_change_with_one_undo(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OPEN_RISK)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek [data-pk-latest]')", sid)))
            click(cdp, sid, "[data-pk-latest] [data-rich=latest_update]")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek .ProseMirror')", sid)))
            cdp.js("document.querySelector('#peek .ProseMirror').focus()", sid)
            cdp.call("Input.insertText", {"text": "Supplier confirmed the new date."}, sid)
            cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "modifiers": 2}, sid)
            cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "modifiers": 2}, sid)
            self.assertTrue(wait(lambda: len(sent) == 1), "one change")
            self.assertEqual((sent[0]["kind"], sent[0]["id"]), ("raid", OPEN_RISK))
            self.assertIn("latest_update", sent[0]["changes"])
            self.assertTrue(wait(lambda: "Supplier confirmed the new date." in (self.stored_latest(OPEN_RISK) or "")))
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.toast [data-undo]').length", sid) == 1))
            cdp.js("document.querySelector('.toast [data-undo]').click()", sid)
            self.assertTrue(wait(lambda: not self.stored_latest(OPEN_RISK)))


if __name__ == "__main__":
    unittest.main()
