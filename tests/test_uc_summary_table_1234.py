"""Row 1234: the dashboard's Use case summary in View is a table: a heading row (Ref, Use case, Status, Commitment, Next steps),
fixed column widths, a Commitment column (a dash when empty) and a whole row that opens.

Run: ~/ag/slot.sh with, inside tests/: PYTHONPATH=../src:../vendor:. python3 -m unittest test_uc_summary_table_1234
Data: tests/fixtures/uc_summary_demo.json (6 use cases), fictional. Laptop widths only: 1400 and 900 px.

Written ahead of the build, nothing skipped, so some fail until it exists. The hooks they assume are named once here;
when the build names them differently, change them here only.
  HEADS   the heading row, one child per heading, in order
  CELL    on each cell of a row's bar: data-uccol = ref | title | status | commit | steps
The words are those of comms/uxui-findings/row1234-new-words-16-11.md section 1; the dash is the symbol, not a word.
"""
import json
import unittest

from _demo import USER
from _paths import ROOT
from test_glance_page import Setup, tearDownModule  # noqa: F401
from test_server import chrome

HEADS = ".uc .ucheads > *"
HEAD_WORDS = ["Ref", "Use case", "Status", "Commitment", "Next steps"]
CELLS = ["ref", "title", "status", "commit", "steps"]
FIXED = ["ref", "status", "commit", "steps"]          # the title cell takes what is left
DASH = "—"
DEMO = json.loads((ROOT / "tests" / "fixtures" / "uc_summary_demo.json").read_text(encoding="utf-8"))["use_cases"]
BOXES = """(() => {
  const box = e => { const r = e.getBoundingClientRect(); return [r.left, r.width]; };
  const heads = [...document.querySelectorAll('%s')].map(box);
  const rows = [...document.querySelectorAll('.ucrows > .ucrow')].map(li => Object.fromEntries(
    [...li.querySelectorAll('.ucbar [data-uccol]')].map(c => [c.dataset.uccol, box(c)])));
  return {heads, rows};
})()""" % HEADS


class Table(Setup):
    def setUp(self):
        super().setUp()
        made = {}
        with self.store.step("dashboard", USER) as st:
            for u in DEMO:
                made[u["ref"]] = st.create("use_cases", {"project": "ABC", "title": u["title"], "status": u["status"], "ref": u["ref"],
                                                         "headline": u["headline"], "commitment": u["commitment"], "source": "demo"})
        for u in DEMO:                                    # the fixture's open steps: actions raised against the use case
            for n in range(u["open_steps"]):
                self.demo.action(description=f"Step {n + 1} for {u['ref']}", owner="Pat Demo", due_date="2099-01-01", use_case=made[u["ref"]])

    def page(self, cdp, width, all_rows=True):
        p = self.show(cdp, width)
        if all_rows:
            p.js("localStorage.setItem('clark.ucAll', 'true')")
            p.reload()
        p.until("!!document.querySelector('.uc')", "the summary drew")
        return p

    def row(self, p, ref):
        """The js expression for the row of use case `ref`."""
        return f"[...document.querySelectorAll('.ucrows > .ucrow')].find(li => /\\b{ref.replace('.', chr(92) + '.')}\\b/.test(li.querySelector('[data-ref]')?.textContent || ''))"


class Harness(Table):
    def test_the_row_lookup_finds_each_demo_row_by_its_ref_in_the_page_as_it_is_today(self):
        """Passes before the build: proves the failures below are the missing table, not a bad lookup."""
        with chrome() as cdp:
            p = self.page(cdp, 1400)
            for u in DEMO:
                with self.subTest(ref=u["ref"]):
                    self.assertEqual(p.js(f"({self.row(p, u['ref'])}).querySelector('[data-word]').textContent.trim()"), u["status"])


class Headings(Table):
    def test_the_heading_row_reads_ref_use_case_status_commitment_next_steps_in_that_order(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.page(cdp, width)
                self.assertEqual(p.js(f"[...document.querySelectorAll('{HEADS}')].map(e => e.textContent.trim())"), HEAD_WORDS)

    def test_the_heading_row_sits_above_the_first_row_and_is_not_one_of_the_rows(self):
        with chrome() as cdp:
            p = self.page(cdp, 1400)
            self.assertTrue(p.js("(h => !!h && h.getBoundingClientRect().bottom <= document.querySelector('.ucrows > .ucrow').getBoundingClientRect().top + 1)(document.querySelector('.uc .ucheads'))"))
            self.assertEqual(p.js("document.querySelectorAll('.ucrows > .ucrow').length"), 8, "the demo's 6 and Setup's 2, all shown")


class Widths(Table):
    def test_each_fixed_column_has_one_width_and_one_left_edge_in_every_row_and_in_its_heading(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.page(cdp, width)
                b = p.js(BOXES)
                self.assertEqual(len(b["heads"]), 5)
                self.assertEqual(len(b["rows"]), 8)
                for i, name in enumerate(CELLS):
                    if name not in FIXED:
                        continue
                    for n, row in enumerate(b["rows"]):
                        with self.subTest(column=name, row=n):
                            self.assertIn(name, row, "the cell exists")
                            self.assertAlmostEqual(row[name][0], b["heads"][i][0], delta=1, msg="same left edge as the heading")
                            self.assertAlmostEqual(row[name][1], b["heads"][i][1], delta=1, msg="same width as the heading")

    def test_the_title_column_takes_the_rest_and_the_columns_do_not_overlap(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.page(cdp, width)
                b = p.js(BOXES)
                for n, row in enumerate(b["rows"]):
                    edges = [row[c] for c in CELLS if c in row]
                    self.assertEqual(len(edges), 5, f"row {n} has the five cells")
                    for a, c in zip(edges, edges[1:]):
                        self.assertLessEqual(a[0] + a[1], c[0] + 1, f"row {n}: a cell runs into the next")
                    self.assertGreater(row["title"][1], 100, "the title keeps room")

    def test_the_widths_of_the_fixed_columns_are_the_same_at_1400_and_900(self):
        got = {}
        for width in (1400, 900):
            with chrome() as cdp:
                heads = self.page(cdp, width, all_rows=False).js(BOXES)["heads"]
                self.assertEqual(len(heads), 5, "the heading row exists")
                got[width] = [round(heads[i][1]) for i in (0, 2, 3, 4)]
        self.assertEqual(got[1400], got[900])


class Commitment(Table):
    def test_a_commitment_shows_in_its_own_cell_and_an_empty_one_shows_a_dash(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.page(cdp, width)
                for u in DEMO:
                    with self.subTest(ref=u["ref"]):
                        want = u["commitment"] or DASH
                        self.assertEqual(p.js(f"({self.row(p, u['ref'])}).querySelector('[data-uccol=commit]').textContent.trim()"), want)

    def test_the_commitment_is_not_inside_the_status_cell(self):
        with chrome() as cdp:
            p = self.page(cdp, 1400)
            self.assertFalse(p.js("!!document.querySelector('.ucbar [data-uccol=status] [data-commit]')"))
            self.assertTrue(p.js("!!document.querySelector('.ucbar [data-uccol=commit] [data-commit]')"), "a set commitment keeps its chip, in its own cell")

    def test_the_dash_is_a_symbol_hidden_from_a_screen_reader_or_named_as_none(self):
        with chrome() as cdp:
            p = self.page(cdp, 1400)
            r = self.row(p, "6.4")
            hidden = p.js(f"(c => c.querySelector('[aria-hidden=true],[aria-label]') !== null || c.getAttribute('aria-label') !== null)(({r}).querySelector('[data-uccol=commit]'))")
            self.assertTrue(hidden, "the dash is not read out as a word")

    def test_the_status_cell_says_the_status_word_and_the_steps_cell_the_open_steps_words(self):
        with chrome() as cdp:
            p = self.page(cdp, 1400)
            r = self.row(p, "6.2")
            self.assertEqual(p.js(f"({r}).querySelector('[data-uccol=status]').textContent.trim()"), "Flag")
            self.assertEqual(p.js(f"({r}).querySelector('[data-uccol=steps]').textContent.trim()"), "3 next steps")
            r = self.row(p, "6.4")
            self.assertEqual(p.js(f"({r}).querySelector('[data-uccol=steps]').textContent.trim()"), "No open steps")


class WholeRowOpens(Table):
    def test_a_press_on_any_cell_opens_the_row_and_a_second_press_closes_it(self):
        for width in (1400, 900):
            for cell in CELLS:
                with self.subTest(width=width, cell=cell), chrome() as cdp:
                    p = self.page(cdp, width)
                    r = self.row(p, "6.1")
                    p.js(f"({r}).querySelector('[data-uccol={cell}]').click()")
                    p.until(f"!!({r}).querySelector('.ucdetail')", "opened")
                    self.assertEqual(p.js(f"({r}).querySelector('.ucbar').getAttribute('aria-expanded')"), "true")
                    p.js(f"({r}).querySelector('[data-uccol={cell}]').click()")
                    p.until(f"!({r}).querySelector('.ucdetail')", "closed")

    def test_a_press_on_the_bar_outside_every_cell_also_opens_it(self):
        with chrome() as cdp:
            p = self.page(cdp, 1400)
            r = self.row(p, "6.3")
            p.js(f"({r}).querySelector('.ucbar').click()")
            p.until(f"!!({r}).querySelector('.ucdetail')", "opened")

    def test_the_row_has_no_chevron_and_no_separate_open_button(self):
        with chrome() as cdp:
            p = self.page(cdp, 1400)
            self.assertFalse(p.js("!!document.querySelector('.ucrows .ucbar .chev, .ucrows .ucbar [data-chev], .ucrows .ucbar svg')"))
            self.assertEqual(p.js("document.querySelectorAll('.ucrows > .ucrow').length === document.querySelectorAll('.ucrows .ucbar[role=button]').length"), True)


if __name__ == "__main__":
    unittest.main()
