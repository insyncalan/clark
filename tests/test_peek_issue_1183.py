"""Item 1183: the Issue peek is the Risk peek with the kind changed (approved mockup, Layout A, peek-issue.png). Written first: it fails until built.
Run: python3 dev/run_tests.py test_peek_issue_1183

Real browser at 1400 and 900 px, Edit, the fictional demo project, fixed date 28-10-2026. TUL-010 is an open issue (High impact, High likelihood: Urgent, Red);
TUL-012 is a cancelled issue (Low impact, High likelihood: High, Red); TUL-007 is an open risk.
Hooks the build must give (named here so the build and the test agree):
  .pk-chips [data-row=rating]      the Rating chip (replaces data-row=priority for a risk and an issue); its tooltip (data-tip) is "Priority from impact and likelihood"
  [data-pk-matrix]                 the 3 x 3 popover (inside [data-pop]); nine cells [data-pk-cell][data-impact=High|Medium|Low][data-likelihood=High|Medium|Low]
                                   (role=radio, aria-checked on the current one; the one matrix of the Risk peek, PeekRiskBody.jsx); [data-pk-matrix-line] the sentence for the focused or hovered cell
  [data-pk-rating-line]            the Rating line in Details; [data-pk-raised] the Raised row in Details
Left for item 1185 (the store): saving a Latest update on an issue and the published file's / Excel's copy of it. Here only the request is checked.
"""
import json
import re
import unittest

from _paths import ROOT

import test_peek_latest  # noqa: E402
from test_peek import key  # noqa: E402
from test_server import chrome, wait  # noqa: E402
from test_work_filters import click  # noqa: E402

ISSUE, CLOSED_ISSUE, RISK = "TUL-010", "TUL-012", "TUL-007"
PEEK_DIR = ROOT / "src/clark/page/src"
LEVELS = ("High", "Medium", "Low")
CHIPS = """(() => { const p = document.querySelector('#peek'); const o = {};
  for (const c of p.querySelectorAll('.pk-chips > [data-row]')) { const s = c.querySelector('.pk-chip-sub'); const r = c.getBoundingClientRect();
    o[c.dataset.row] = { text: c.innerText.replace(/\\s+/g, ' ').trim(), tip: c.getAttribute('data-tip') || c.getAttribute('title') || '', tag: c.tagName, sub: s ? s.textContent.trim() : null, h: r.height }; }
  return o; })()"""


def colour(impact, likelihood):
    """The rating colour and level word clark works out (store.priority, workItems.colourOf)."""
    if impact == "High" and likelihood == "High":
        lvl = "Urgent"
    elif "High" in (impact, likelihood):
        lvl = "High"
    elif impact == "Low" and likelihood == "Low":
        lvl = "Low"
    else:
        lvl = "Medium"
    return lvl, {"Urgent": "Red", "High": "Red", "Medium": "Amber", "Low": "Green"}[lvl]


class Issue(test_peek_latest.Browser):
    def chips(self, cdp, sid):
        return cdp.js(CHIPS, sid)

    def settled(self, cdp, sid, item):
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek .pk-chips [data-row=status]')", sid)), item)
        self.assertTrue(wait(lambda: cdp.js("document.querySelector('#peek').getAnimations().length === 0", sid)))

    def go(self, cdp, sid, item):
        cdp.js(f"clarkPage.openPeek({json.dumps(item)})", sid)
        self.assertTrue(wait(lambda: cdp.js(f"(p => !!p && p.dataset.peek === {json.dumps(item)})(document.querySelector('#peek'))", sid)))
        self.settled(cdp, sid, item)

    def open_matrix(self, cdp, sid):
        click(cdp, sid, "#peek .pk-chips [data-row=rating]")
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pop] [data-pk-matrix]')", sid)), "the matrix opens")

    # --- 1. the chip row ------------------------------------------------------------------------------------------
    def test_an_issue_has_status_rating_owner_and_due_chips_like_a_risk(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, ISSUE)
                self.settled(cdp, sid, ISSUE)
                got = self.chips(cdp, sid)
                self.assertEqual(list(got), ["status", "rating", "owner", "due"])
                self.assertNotIn("priority", got, "the Priority chip is replaced")
                self.go(cdp, sid, RISK)
                self.assertEqual(list(self.chips(cdp, sid)), ["status", "rating", "owner", "due"], "a risk too")

    def test_the_rating_chip_says_the_colour_and_the_level_with_the_tooltip(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, ISSUE)
                self.settled(cdp, sid, ISSUE)
                chip = self.chips(cdp, sid)["rating"]
                self.assertEqual(chip["tag"], "BUTTON")
                self.assertIn("Red", chip["text"])
                self.assertIn("Urgent", chip["text"], "the level word beside the colour")
                self.assertEqual(chip["tip"], "Priority from impact and likelihood")
                self.assertGreaterEqual(chip["h"], 24)
                self.assertTrue(cdp.js("!!document.querySelector('#peek .pk-chips [data-row=rating] svg[data-icn=bars]')", sid), "the bars icon")

    def test_a_closed_or_cancelled_issue_keeps_its_colour_and_says_kept_on_the_status_chip(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, CLOSED_ISSUE)
                self.settled(cdp, sid, CLOSED_ISSUE)
                got = self.chips(cdp, sid)
                self.assertIn("Cancelled", got["status"]["text"])
                self.assertEqual(got["status"]["sub"], "Red kept", "the Status chip's sub-line, as for a risk (ticket 1182)")
                self.assertIn("Red", got["rating"]["text"], "the rating chip keeps its colour")

    # --- 3. status ------------------------------------------------------------------------------------------------
    def test_status_offers_open_closed_cancelled_and_no_rating_group(self):
        for kind_item in (ISSUE, RISK):
            with self.subTest(item=kind_item), chrome() as cdp:
                sent, sid = self.load(cdp, 1400, kind_item)
                self.settled(cdp, sid, kind_item)
                click(cdp, sid, "#peek .pk-chips [data-row=status]")
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pop] [role=menuitemradio]')", sid)))
                words = cdp.js("[...document.querySelectorAll('[data-pop] [role=menuitemradio]')].map(b => b.textContent.trim())", sid)
                self.assertEqual(words, ["Open", "Closed", "Cancelled"])
                self.assertFalse(cdp.js("!!document.querySelector('[data-pop] [data-group=rating], [data-pop] [data-value^=\"rating:\"]')", sid), "no Rating group")
                for w in ("Red", "Amber", "Green", "Delayed"):
                    self.assertNotIn(w, cdp.js("document.querySelector('[data-pop]').innerText", sid))

    def test_closing_an_issue_keeps_the_rating_and_says_so(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, ISSUE)
            self.settled(cdp, sid, ISSUE)
            click(cdp, sid, "#peek .pk-chips [data-row=status]")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pop] [role=menuitemradio]')", sid)))
            cdp.js("[...document.querySelectorAll('[data-pop] [role=menuitemradio]')].find(b => b.textContent.trim() === 'Closed').dataset.t = '1'", sid)
            click(cdp, sid, "[data-pop] [data-t='1']")
            self.assertTrue(wait(lambda: self.chips(cdp, sid)["status"]["sub"] == "Red kept"))
            self.assertIn("Closed", self.chips(cdp, sid)["status"]["text"])

    # --- 2. the matrix --------------------------------------------------------------------------------------------
    def test_the_rating_chip_opens_a_3_by_3_matrix_with_the_current_cell_ticked(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, ISSUE)
                self.settled(cdp, sid, ISSUE)
                self.open_matrix(cdp, sid)
                cells = cdp.js("""[...document.querySelectorAll('[data-pop] [data-pk-matrix] [data-pk-cell]')].map(c => { const r = c.getBoundingClientRect();
                    return [c.dataset.impact, c.dataset.likelihood, c.getAttribute('aria-checked'), c.getAttribute('role'), Math.round(r.width), Math.round(r.height), Math.round(r.left), Math.round(r.top)]; })""", sid)
                self.assertEqual(len(cells), 9)
                self.assertEqual({(c[0], c[1]) for c in cells}, {(i, l) for i in LEVELS for l in LEVELS})
                self.assertEqual([c[:2] for c in cells if c[2] == "true"], [["High", "High"]], "only the current cell is ticked")
                for c in cells:
                    self.assertEqual(c[3], "radio")
                    self.assertGreaterEqual(min(c[4], c[5]), 24, "a 24 px target")
                self.assertEqual(len({c[7] for c in cells}), 3, "three rows")
                self.assertEqual(len({c[6] for c in cells}), 3, "three columns")
                self.assertFalse(cdp.js("!!document.querySelector('[data-pop].rpick, [data-pop] .rp-head')", sid), "the two-list picker is gone")
                on = cdp.js("(r => r.left >= 0 && r.right <= document.documentElement.clientWidth && r.bottom <= innerHeight)(document.querySelector('[data-pop]').getBoundingClientRect())", sid)
                self.assertTrue(on, "on screen")

    def test_the_matrix_names_the_result_for_every_cell(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, ISSUE)
            self.settled(cdp, sid, ISSUE)
            self.open_matrix(cdp, sid)
            for i in LEVELS:
                for l in LEVELS:
                    cdp.js(f"document.querySelector('[data-pk-cell][data-impact={i}][data-likelihood={l}]').focus()", sid)
                    lvl, col = colour(i, l)
                    want = f"{i} impact, {l} likelihood: {lvl} ({col})"
                    self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-pk-matrix-line]').textContent.trim()", sid) == want), want)

    def test_picking_a_cell_sets_impact_and_likelihood_in_one_change_with_one_undo(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, ISSUE)
                self.settled(cdp, sid, ISSUE)
                self.open_matrix(cdp, sid)
                n = len(sent)
                click(cdp, sid, "[data-pk-cell][data-impact=Low][data-likelihood=Low]")
                self.assertTrue(wait(lambda: "Green" in self.chips(cdp, sid)["rating"]["text"]), "the chip shows the new rating")
                self.assertIn("Low", self.chips(cdp, sid)["rating"]["text"])
                new = sent[n:]
                self.assertEqual(len(new), 1, "one request for both fields")
                ch = new[0]["changes"]
                self.assertEqual((ch.get("impact"), ch.get("likelihood")), ("Low", "Low"))
                self.assertFalse(cdp.js("!!document.querySelector('[data-pop]')", sid), "the pick closes the matrix")
                row = next(r for r in self.store.data_for(self.code)["raid"] if r["id"] == ISSUE)
                self.assertEqual((row["impact"], row["likelihood"], row["priority"]), ("Low", "Low", "Low"))
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.toast [data-undo], .toast button')", sid)), "a toast with Undo")
                cdp.js("(document.querySelector('.toast [data-undo]') || document.querySelector('.toast button')).click()", sid)
                self.assertTrue(wait(lambda: "Red" in self.chips(cdp, sid)["rating"]["text"]), "one Undo puts both back")
                row = next(r for r in self.store.data_for(self.code)["raid"] if r["id"] == ISSUE)
                self.assertEqual((row["impact"], row["likelihood"]), ("High", "High"))

    def test_a_pick_adds_one_activity_line(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, ISSUE)
            self.settled(cdp, sid, ISSUE)
            count = "document.querySelectorAll('#peek [data-pk-hrow=activity]').length"
            click(cdp, sid, "#peek [data-pk-htab=activity]")
            before = cdp.js(count, sid)
            self.open_matrix(cdp, sid)
            click(cdp, sid, "[data-pk-cell][data-impact=Medium][data-likelihood=Medium]")
            self.assertTrue(wait(lambda: cdp.js(count, sid) == before + 1), "exactly one new Activity line")

    def test_keys_roam_the_matrix_and_esc_returns_focus_to_the_chip(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, ISSUE)
            self.settled(cdp, sid, ISSUE)
            self.open_matrix(cdp, sid)
            self.assertTrue(wait(lambda: cdp.js("document.activeElement.hasAttribute('data-pk-cell')", sid)), "focus starts on a cell, the ticked one")
            self.assertEqual(cdp.js("[document.activeElement.dataset.impact, document.activeElement.dataset.likelihood]", sid), ["High", "High"])
            key(cdp, sid, "ArrowRight")
            moved = cdp.js("[document.activeElement.dataset.impact, document.activeElement.dataset.likelihood]", sid)
            self.assertNotEqual(moved, ["High", "High"], "an arrow key moves between cells")
            key(cdp, sid, "Escape")
            self.assertTrue(wait(lambda: cdp.js("!document.querySelector('[data-pop]')", sid)))
            self.assertTrue(wait(lambda: cdp.js("document.activeElement === document.querySelector('#peek .pk-chips [data-row=rating]')", sid)))
            self.assertTrue(cdp.js("!!document.querySelector('#peek')", sid), "the first Esc leaves the peek open")

    # --- 4. Latest update -----------------------------------------------------------------------------------------
    def test_an_issue_peek_draws_the_latest_update_block_and_opens_the_box_with_its_hint(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, ISSUE)
                self.settled(cdp, sid, ISSUE)
                self.assertTrue(cdp.js("!!document.querySelector('#peek [data-pk-latest]')", sid), "the block")
                click(cdp, sid, "#peek [data-pk-latest] [data-rich=latest_update]")
                self.assertTrue(wait(lambda: cdp.js("document.activeElement.classList.contains('ProseMirror')", sid)))
                self.assertTrue(cdp.js("!!document.querySelector('#peek [data-pk-hint]')", sid), "the Cmd/Ctrl+Enter hint")

    def test_saving_an_issues_latest_update_sends_one_change_to_the_raid_table(self):
        """The request only: whether clark stores it is item 1185."""
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, ISSUE)
            self.settled(cdp, sid, ISSUE)
            self.open_box(cdp, sid)
            self.type_in(cdp, sid, "Feed fixed, watching overnight.")
            n = len(sent)
            cdp.js("document.querySelector('#peek .ProseMirror').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', ctrlKey: true, bubbles: true, cancelable: true}))", sid)
            self.assertTrue(wait(lambda: len(sent) > n))
            req = sent[n]
            self.assertEqual((req["kind"], req["id"]), ("raid", ISSUE), "the issue's table, not actions")
            self.assertIn("Feed fixed", req["changes"]["latest_update"])

    # --- 5. Details -----------------------------------------------------------------------------------------------
    def test_details_has_a_read_only_raised_row_and_the_rating_line_and_no_type_or_priority_row(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, ISSUE)
                self.settled(cdp, sid, ISSUE)
                if cdp.js("document.querySelector('[data-pk-details]').getAttribute('aria-expanded')", sid) != "true":
                    click(cdp, sid, "[data-pk-details]")
                labels = cdp.js("[...document.querySelectorAll('#peek [data-pk-details-rows] dt')].map(d => d.textContent.trim())", sid)
                self.assertIn("Raised", labels)
                self.assertNotIn("Type", labels)
                self.assertNotIn("Priority", labels)
                raised = cdp.js("(r => r ? [r.innerText.replace(/\\s+/g, ' ').trim(), !!r.querySelector('button, input, textarea, [contenteditable=true]')] : null)(document.querySelector('#peek [data-pk-raised]'))", sid)
                self.assertIsNotNone(raised, "the Raised row")
                self.assertRegex(raised[0], r"\d{2}-\d{2}-\d{4}|not set|read only")
                self.assertFalse(raised[1], "read only: no control")
                line = cdp.js("(e => e ? e.textContent.replace(/\\s+/g, ' ').trim() : null)(document.querySelector('#peek [data-pk-rating-line]'))", sid)
                self.assertEqual(line, "Rating: Red · Urgent (impact High, likelihood High)")

    def test_the_rating_line_follows_a_change(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, ISSUE)
            self.settled(cdp, sid, ISSUE)
            if cdp.js("document.querySelector('[data-pk-details]').getAttribute('aria-expanded')", sid) != "true":
                click(cdp, sid, "[data-pk-details]")
            self.open_matrix(cdp, sid)
            click(cdp, sid, "[data-pk-cell][data-impact=Medium][data-likelihood=Medium]")
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('#peek [data-pk-rating-line]').textContent.replace(/\\s+/g, ' ').trim()", sid)
                                 == "Rating: Amber · Medium (impact Medium, likelihood Medium)"))

    def test_the_id_tag_is_the_items_id_and_the_closed_details_line_keeps_raised(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, ISSUE)
            self.settled(cdp, sid, ISSUE)
            self.assertEqual(cdp.js("document.querySelector('#peek [data-pk-idtag]').textContent.trim()", sid), ISSUE)
            if cdp.js("document.querySelector('[data-pk-details]').getAttribute('aria-expanded')", sid) == "true":
                click(cdp, sid, "[data-pk-details]")
            self.assertIn("Raised", cdp.js("document.querySelector('[data-pk-details-sum]').textContent", sid))

    # --- a risk is untouched by the Latest update rule, an action keeps its own ---------------------------------------
    def test_an_action_still_has_the_priority_chip_and_a_decision_no_rating(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, "TUL-A-002")
            self.settled(cdp, sid, "TUL-A-002")
            keys = list(self.chips(cdp, sid))
            self.assertIn("priority", keys)
            self.assertNotIn("rating", keys)
            self.go(cdp, sid, self.data["decisions"][0]["id"])
            self.assertNotIn("rating", self.chips(cdp, sid))


class Rules(unittest.TestCase):
    def read(self, rel):
        return (PEEK_DIR / rel).read_text(encoding="utf-8")

    def test_status_pick_has_no_rating_group_and_the_status_words_are_three(self):
        self.assertNotIn("ratingChoices", self.read("edit/cells/StatusPick.jsx"))
        self.assertNotRegex(self.read("edit/cells/StatusPick.jsx"), r"rating:")
        self.assertRegex(self.read("edit/itemEdit.js"), r'raid:\s*\["Open", "Closed", "Cancelled"\]')

    def test_the_matrix_source_and_style(self):
        src = self.read("components/PeekRiskBody.jsx")          # the one matrix: the table's RatingPick draws it too
        for hook in ("data-pk-matrix", "data-pk-cell", "data-pk-matrix-line", "data-impact", "data-likelihood"):
            self.assertIn(hook, src)
        picker = self.read("edit/cells/RatingPick.jsx")
        self.assertIn("RatingMatrix", picker)
        self.assertNotIn("ratingGroups", picker, "the two lists are replaced")
        css = (PEEK_DIR / "edit/edit.css").read_text(encoding="utf-8") + (PEEK_DIR.parent / "shell.css").read_text(encoding="utf-8")
        for sel in re.findall(r"[^}]*pk-matrix[^{]*\{([^}]*)\}", css):
            self.assertNotRegex(sel, r"#[0-9A-Fa-f]{3,8}\b|rgba?\(|hsla?\(", "tokens only")

    def test_the_rating_chip_and_the_tooltip_are_in_the_peek_source(self):
        src = self.read("components/Peek.jsx") + self.read("components/PeekRiskBody.jsx")      # Peek.jsx draws RatingChip for a risk and an issue
        self.assertIn('field="rating"', src)
        self.assertIn("Priority from impact and likelihood", src + self.read("logic/riskRating.js"))

    def test_the_latest_update_is_no_longer_gated_to_actions(self):
        src = self.read("edit/PeekLatest.jsx")
        self.assertNotIn('changeCell("actions"', src, "the table comes from the row")
        self.assertIn("tableOf", src)


if __name__ == "__main__":
    unittest.main()
