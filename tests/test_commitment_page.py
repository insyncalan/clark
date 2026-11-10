"""#709 page side: the commitment chip (Candidate, Committed, Planned 2027, or none) in a real browser.

Run: python3 dev/run_tests.py test_commitment_page
Where it is drawn: the Dashboard's use case rows, the Use cases page and a use case's own page, and the published file (its dashboard and
its Use cases tab). A use case with no flag has NO chip in View and on the published page; in Edit it has the quiet "Set commitment"
menu button, which is not in the published file's bytes. Widths 1400 and 900 px, light and dark: nothing overlaps or runs
out of its cell. Fictional data; the page is the committed one, served by a real server over a real store.
"""
import tempfile
import unittest
from pathlib import Path

from _paths import SRC
from _publish import PublishedFile
from test_glance_page import Setup, USER, tearDownModule  # noqa: F401
from test_publish import EMPTY_BRANDING, made
from test_report_editor import Pg
from test_server import chrome

from clark import page, publish

WORDS = ["Candidate", "Committed", "Planned 2027"]
CHIPS = "[...document.querySelectorAll('%s [data-commit]')].map(e => e.textContent)"

# Pairs of a row's cells that overlap, and cells that run out of their box. `row` and `cell` are selectors.
OVERLAP = """((row, cells) => {
  const bad = [];
  const r = (e) => e.getBoundingClientRect();
  for (const bar of document.querySelectorAll(row)) {
    const kids = [...bar.children].filter((e) => r(e).width > 0 && getComputedStyle(e).display !== 'none');
    for (let i = 0; i < kids.length; i++) for (let j = i + 1; j < kids.length; j++) {
      const a = r(kids[i]), b = r(kids[j]);
      if (a.left < b.right - 0.5 && b.left < a.right - 0.5 && a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5) bad.push('overlap ' + kids[i].className + ' / ' + kids[j].className);
    }
    for (const cell of bar.querySelectorAll(cells)) {
      if (cell.scrollWidth > cell.clientWidth + 1) bad.push('cell runs over: ' + cell.className);
      for (const chip of cell.querySelectorAll('.cchip')) {
        if (r(chip).right > r(cell).right + 0.5 || r(chip).left < r(cell).left - 0.5) bad.push('chip outside its cell: ' + chip.textContent);
        if (r(chip).height > 26) bad.push('chip wraps: ' + chip.textContent);
      }
    }
    if (r(bar).right > window.innerWidth + 0.5) bad.push('row wider than the window');
  }
  if (document.documentElement.scrollWidth > window.innerWidth) bad.push('the page scrolls sideways');
  return bad;
})"""

RATIO = """(() => {
  const rgb = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number);
  const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const ratio = (a, b) => { const x = lum(rgb(a)), y = lum(rgb(b)); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  return [...document.querySelectorAll('.cchip')].map((el) => {
    let bg = el, back = 'rgba(0, 0, 0, 0)';
    while (bg && /rgba\\(.*, 0\\)|transparent/.test(back)) { back = getComputedStyle(bg).backgroundColor; bg = bg.parentElement; }
    return [el.textContent, ratio(getComputedStyle(el).color, back)];
  });
})()"""


class Flags(Setup):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            st.update("use_cases", self.demo.use_case, {"commitment": "Committed"})      # 1.1; 1.2 has none

    def flag(self, id_=None):
        return self.store.con.execute("SELECT commitment FROM use_cases WHERE id = ?", (id_ or self.demo.use_case,)).fetchone()[0]

    def menu(self, p, id_, pick=None):
        p.js(f"document.querySelector('[data-uc-commit=\"{id_}\"] button').click()")
        p.until("!!document.querySelector('[role=menu][aria-label=Commitment]')", "the menu opened")
        words = p.js("[...document.querySelectorAll('[role=menu][aria-label=Commitment] [role^=menuitem]')].map(e => e.textContent.replace(/^[\\u2713]/, ''))")
        if pick:
            p.js(f"[...document.querySelectorAll('[role=menu][aria-label=Commitment] [role^=menuitem]')].find(e => e.textContent.includes({pick!r})).click()")
        return words


class View(Flags):
    def test_the_chip_is_on_the_flagged_row_only_and_nothing_is_drawn_for_none(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertEqual(p.js(CHIPS % ".uc"), ["Committed"])
            self.assertEqual(p.js("document.querySelectorAll('.ucrow').length"), 2)
            self.assertEqual(p.js("document.querySelectorAll('.ucrow:nth-child(2) .cchip').length"), 0, "no flag: no chip, no placeholder")
            body = p.js("document.querySelector('.uc').innerText")
            for word in ("Set commitment", "No flag", "None"):
                self.assertNotIn(word, body)
            self.assertEqual(p.js("document.querySelectorAll('.uc [data-uc-commit], .uc .ucw-btn').length"), 0, "plain text in View")
            self.assertEqual(p.js("document.querySelector('.ucrow .cchip').tagName"), "SPAN")

    def test_the_chip_does_not_look_like_a_status_word(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertEqual(p.js("document.querySelector('.ucrow .cchip').closest('.ucword')"), None)
            self.assertEqual(p.js("document.querySelectorAll('.ucrow .cchip .ragdot, .ucrow .cchip[class*=rag-]').length"), 0, "no status dot or colour class")
            self.assertEqual(p.js("getComputedStyle(document.querySelector('.ucrow .cchip')).borderRadius"), "4px", "a square chip; the status is a dot and a word")

    def test_each_word_has_its_own_look_and_the_text_reads_at_4_5_to_1_in_light_and_dark(self):
        for uc, word in ((self.demo.use_case, "Candidate"), (self.demo.use_case, "Planned 2027"), (self.demo.use_case, "Committed")):
            with self.store.step("dashboard", USER) as st:
                st.update("use_cases", uc, {"commitment": word})
        with self.store.step("dashboard", USER) as st:
            st.update("use_cases", self.uc2, {"commitment": "Candidate"})
        looks = {}
        for dark in (False, True):
            with self.subTest(dark=dark), chrome() as cdp:
                p = self.show(cdp, 1400, dark)
                for text, ratio in p.js(RATIO):
                    self.assertGreaterEqual(ratio, 4.5, f"{text} in {'dark' if dark else 'light'}: {ratio:.1f}")
                looks[dark] = p.js("[...document.querySelectorAll('.ucrow .cchip')].map(e => { const c = getComputedStyle(e); return [e.textContent, c.borderTopStyle, c.backgroundColor]; })")
        self.assertEqual(looks[False][0][1], "solid")
        self.assertEqual(looks[False][1][1], "dashed", "Candidate is a dashed outline")

    def test_the_use_cases_page_row_and_search(self):
        with chrome() as cdp:
            p = self.show(cdp, 1400, False, "#usecases&p=ABC", settings=True)
            p.until("!!document.querySelector('.ucl-row[data-uc]')", "the list drew")
            self.assertEqual(p.js(CHIPS % ".ucl-list"), ["Committed"])
            self.assertEqual(p.js("document.querySelector('.ucl-row[data-uc]').getAttribute('data-uc') && document.querySelectorAll('.ucl-list .ucl-row').length"), 2)
            self.assertIn("Committed", p.js("document.querySelector('.ucl-go').getAttribute('aria-label')"))
            p.js("(() => { const q = document.querySelector('#ucl-q'); q.value = 'committed'; q.dispatchEvent(new Event('input', {bubbles: true})); })()")
            p.until("document.querySelectorAll('.ucl-list .ucl-row').length === 1", "the search finds the flagged one by its word")
            self.assertEqual(p.js(CHIPS % ".ucl-list"), ["Committed"])

    def test_the_detail_commitment_is_the_menu_with_no_edit_mode_row_825(self):
        with self.store.step("dashboard", USER) as st:
            st.update("use_cases", self.demo.use_case, {"commitment": "Planned 2027"})
        with chrome() as cdp:
            p = self.show(cdp, 1400, False, "#usecases&p=ABC&uc=1.1", settings=True)
            p.until("!!document.querySelector('.ucd-sub')", "the detail drew")
            self.assertEqual(p.js("[...document.querySelectorAll('.ucd-sub [data-uc-commit] button')].map(e => e.textContent.trim())"), ["Planned 2027"])
            p = self.show(cdp, 1400, False, "#usecases&p=ABC&uc=1.2", settings=True)
            p.until("!!document.querySelector('.ucd-sub')", "the detail drew")
            self.assertEqual(p.js("[...document.querySelectorAll('.ucd-sub [data-uc-commit] button')].map(e => e.textContent.trim())"), ["Set commitment"], "no flag: the quiet menu")


class Fit(Flags):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            st.update("use_cases", self.uc2, {"commitment": "Planned 2027", "status": "High risk"})

    def test_nothing_overlaps_or_wraps_at_1400_and_900_light_and_dark(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.show(cdp, width, dark)
                    where = f"{width}px {'dark' if dark else 'light'}"
                    self.assertEqual(p.js(f"{OVERLAP}('.ucbar', '.ucstc')"), [], f"View, dashboard, {where}")
                    p.js("document.querySelector('.ucbar').click()")            # an open row too
                    p.edit()
                    p.until("!!document.querySelector('[data-uc-commit]')", "Edit drew the chip button")
                    self.assertEqual(p.js(f"{OVERLAP}('.ucbar', '.ucstc')"), [], f"Edit, dashboard, {where}")
                    p.js("location.hash = '#usecases&p=ABC'")
                    p.until("!!document.querySelector('.ucl-row[data-uc]')", "the list drew")
                    self.assertEqual(p.js(f"{OVERLAP}('.ucl-row[data-uc]', '.ucl-st')"), [], f"Use cases page, {where}")


class Edit(Flags):
    def test_in_edit_the_chip_is_a_menu_and_a_choice_is_one_change_with_one_undo(self):
        uc1, uc2 = self.demo.use_case, self.uc2
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            lab = p.js("document.querySelector('[data-uc-commit=\"%s\"] button').getAttribute('aria-label')" % uc1)
            self.assertEqual(lab, "Commitment: Committed. Change")
            self.assertEqual(p.js("document.querySelector('[data-uc-commit=\"%s\"] button').getAttribute('aria-haspopup')" % uc1), "menu")
            self.assertEqual(p.js("document.querySelector('[data-uc-commit=\"%s\"] button').getAttribute('aria-expanded')" % uc1), "false")
            # no flag: the quiet "Set commitment" button, only in Edit
            self.assertEqual(p.js("document.querySelector('[data-uc-commit=\"%s\"] button').textContent" % uc2), "Set commitment")
            words = self.menu(p, uc2, "Planned 2027")
            self.assertEqual(words, WORDS + ["No flag"], "the words come from the server, then No flag")
            p.saved()
            self.assertEqual(self.flag(uc2), "Planned 2027")
            self.assertEqual(p.toast(), f"Use case 1.2: commitment set to Planned 2027.")
            p.until("document.querySelector('[data-uc-commit=\"%s\"] button').textContent === 'Planned 2027'" % uc2, "the chip shows it")
            self.undo(p)
            self.assertIsNone(self.flag(uc2), "one Undo puts it back")
            p.until("document.querySelector('[data-uc-commit=\"%s\"] button').textContent === 'Set commitment'" % uc2, "back to none")
            # clear the flagged one with No flag
            self.menu(p, uc1, "No flag")
            p.until("!!document.querySelector('[data-undo]')", "saved")
            self.assertIsNone(self.flag(uc1))
            self.undo(p)
            self.assertEqual(self.flag(uc1), "Committed")
            n = self.store.con.execute("SELECT COUNT(*) FROM change_log WHERE tbl = 'use_cases' AND field = 'commitment'").fetchone()[0]
            self.assertGreaterEqual(n, 2)

    def test_the_menu_is_keyboard_operable(self):
        uc2 = self.uc2
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            p.js("document.querySelector('[data-uc-commit=\"%s\"] button').focus()" % uc2)
            p.key("ArrowDown", code="ArrowDown", vk=40)
            p.until("!!document.querySelector('[role=menu][aria-label=Commitment]')", "Down opens it")
            self.assertEqual(p.js("document.querySelector('[data-uc-commit=\"%s\"] button').getAttribute('aria-expanded')" % uc2), "true")
            p.key("ArrowDown", code="ArrowDown", vk=40)
            p.cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "text": "\r"}, p.sid)
            p.cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13}, p.sid)
            p.saved()
            self.assertEqual(self.flag(uc2), "Committed", "the second word")

    def test_a_row_click_is_not_taken_by_the_chip_button(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            p.js("document.querySelector('[data-uc-commit] button').click()")
            self.assertEqual(p.js("document.querySelectorAll('.ucrow.open').length"), 0, "opening the menu does not open the row")

    def test_view_after_edit_draws_no_set_affordance(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            p.view()
            p.until("document.querySelectorAll('[data-uc-commit]').length === 0", "the Edit buttons are gone")
            self.assertNotIn("Set commitment", p.js("document.querySelector('.uc').innerText"))


class Pub(PublishedFile, Flags):
    def test_the_file_shows_the_chip_on_the_dashboard_and_the_use_cases_tab_and_no_empty_one(self):
        path = self.publish()
        for width, dark in ((1400, False), (900, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.draw(cdp, path, width, dark)
                self.assertEqual(p.js(CHIPS % ".uc"), ["Committed"])
                self.assertEqual(p.js("document.querySelectorAll('.ucrow:nth-child(2) .cchip').length"), 0)
                self.assertEqual(p.js("document.querySelectorAll('.uc button, [data-uc-commit], .ucw-btn').length"), 0)
                self.assertNotIn("Set commitment", p.js("document.body.innerText"))
                self.assertEqual(p.js(f"{OVERLAP}('.ucbar', '.ucstc')"), [])
                p.js("[...document.querySelectorAll('.tab')].find(e => e.textContent.includes('Use cases')).click()")
                p.until("!!document.querySelector('#usecases-file .ucp')", "the Use cases tab drew")
                self.assertEqual(p.js(CHIPS % "#usecases-file"), ["Committed"])
                self.assertEqual(p.js("document.querySelectorAll('#usecases-file .cchip').length"), 1)

    def test_the_published_build_has_no_commitment_editing_code(self):
        text = (SRC / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for edit_only in ("Set commitment", "No flag", "uccm", "data-uc-commit", "Commitment: none", "commitment set to", "commitment cleared"):
            self.assertNotIn(edit_only, text, edit_only)
        self.assertIn("data-commit", text, "the chip itself is in the build")
        self.assertIn("Set commitment", (SRC / "clark" / "page" / "page.html").read_text(encoding="utf-8"), "the editor's page has the menu")


class OldFile(PublishedFile, Flags):
    def test_a_file_made_by_1_0_0_has_no_commitment_key_and_shows_no_chip(self):
        plant = __import__("_publish_fixture").load()
        pub = publish.select(__import__("_publish_fixture").inputs(plant))
        for u in pub["data"]["use_cases"]:
            u.pop("commitment", None)
        text = publish.render(pub, page.page_html(EMPTY_BRANDING), plant["as_at"], pub["data"]["project"]["name"])
        from test_publish import block
        self.assertTrue(all("commitment" not in u for u in block(text)["data"]["use_cases"]))
        tmp = tempfile.mkdtemp(prefix="clark-709-")
        self.addCleanup(__import__("shutil").rmtree, tmp, ignore_errors=True)
        path = Path(tmp) / "old.html"
        path.write_text(text, encoding="utf-8")
        with chrome() as cdp:
            p = self.draw(cdp, path)
            self.assertGreater(p.js("document.querySelectorAll('.ucrow').length"), 0)
            self.assertEqual(p.js("document.querySelectorAll('.cchip, [data-commit]').length"), 0)
            p.js("[...document.querySelectorAll('.tab')].find(e => e.textContent.includes('Use cases')).click()")
            p.until("!!document.querySelector('#usecases-file .ucp')", "the Use cases tab drew")
            self.assertEqual(p.js("document.querySelectorAll('#usecases-file .cchip').length"), 0)


if __name__ == "__main__":
    unittest.main()
