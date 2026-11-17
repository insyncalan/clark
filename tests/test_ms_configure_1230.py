"""Row 1230, PR 1: Configure for the Milestones section (Edit only): number shown, viewers can scroll, tracker position, kept in the section's body.
Run: ~/ag/slot.sh with, inside tests/: PYTHONPATH=../src:../vendor:. python3 -m unittest test_ms_configure_1230
Widths 1400 and 900 only. The words are the ruled ones (edit/ucConfigureWords.js, MS_ constants; the rest are the ruled Use case summary words).
"""
import json
import unittest

from _demo import USER
from _uc_view import put_view  # noqa: F401  (the use case twin's helper; the Milestones one is below)
from test_glance_page import Setup, tearDownModule  # noqa: F401
from test_server import chrome, wait

ROWS = ".msv[data-place^=sec-] .msl > li"
SEE = """(() => {
  const box = document.querySelector('.msv[data-place^=sec-]'), ul = box && box.querySelector('.msl'), t = box && box.querySelector('[data-tracker]');
  const lis = ul ? [...ul.children] : [];
  return {rows: lis.length, all: !!(box && box.querySelector('[data-msall]')), tracker: !!t, trackerFirst: !!t && !!(box.querySelector('.msl-box').compareDocumentPosition(t) & 2),
          trackerLast: !!t && box.lastElementChild === t, scrolls: !!ul && ul.scrollHeight > ul.clientHeight + 1, overflow: ul ? getComputedStyle(ul).overflowY : '',
          tall: ul && lis.length > 1 ? Math.round(ul.getBoundingClientRect().height) : 0,
          twoRows: lis.length > 1 ? Math.round(lis[1].getBoundingClientRect().bottom - lis[0].getBoundingClientRect().top) : 0,
          noScroll: document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1};
})()"""


def put_ms_view(test, view):
    ref = next(r["id"] for r in test.store.read("report_sections", "ABC") if r["type"] == "milestones")
    with test.store.con:
        test.store.con.execute("UPDATE report_sections SET body = ? WHERE id = ?", ("" if view is None else json.dumps(view), ref))
    return ref


class Configure(Setup):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            for i, name in enumerate(["Kick-off", "Design signed", "Build done", "Training", "Go live", "Handover"]):
                st.create("milestones", {"project": "ABC", "name": name, "baseline_date": f"2030-0{i + 1}-01", "source": "demo"})

    def edit(self, p):
        p.js("document.querySelector('[data-mode=edit]').click()")
        p.until("!!document.querySelector('[data-ms-configure]')", "Edit")

    def stored(self):
        row = next(r for r in self.store.read("report_sections", "ABC") if r["type"] == "milestones")
        return json.loads(row["body"]) if row["body"] else None

    def wait_body(self, check, what):
        self.assertTrue(wait(lambda: (lambda v: bool(v) and check(v))(self.stored())), what)
        return self.stored()

    def open_panel(self, p):
        p.js("document.querySelector('[data-ms-configure]').click()")
        p.until("!!document.querySelector('#ucCfgN')", "panel")

    def test_view_has_no_configure_button_and_edit_has_one_beside_the_use_case_one(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.until(f"!!document.querySelector('{ROWS}')", "milestones")
                self.assertIsNone(p.js("document.querySelector('[data-ms-configure]')"))
                self.edit(p)
                self.assertEqual(p.js("document.querySelector('[data-ms-configure]').textContent"), "Configure")
                self.assertEqual(p.js("document.querySelector('[data-ms-configure]').closest('article').dataset.type"), "milestones")
                self.assertEqual(p.js("document.querySelector('[data-uc-configure]').closest('article').dataset.type"), "usecases")
                self.assertEqual(p.js("document.querySelectorAll('[data-ms-configure]').length"), 1)

    def test_the_panel_uses_the_ruled_words_and_counts_the_dashboard_milestones(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                put_ms_view(self, None)
                p = self.show(cdp, width)
                self.edit(p)
                self.open_panel(p)
                self.assertEqual(p.js("document.querySelector('#uccfg-title').textContent"), "Configure milestones")
                self.assertEqual(p.js("document.querySelector('label[for=ucCfgN]').textContent"), "Milestones shown in the list")
                self.assertEqual(p.js("document.querySelector('#ucCfgN').getAttribute('aria-label')"), "Milestones shown")
                self.assertEqual(p.js("document.querySelector('label[for=ucCfgS]').textContent"), "Viewers can scroll the list")
                self.assertEqual(p.js("document.querySelector('#ucCfgN').lastElementChild.textContent"), "All")
                self.assertEqual(p.js("document.querySelector('[data-uc-of]').textContent"), "of 7")
                self.assertEqual(p.js("document.querySelector('[data-uc-cfg-help]').textContent"),
                                 "On: the list is 5 rows tall and scrolls up and down to the rest. Off: viewers see only the first 5.")
                self.assertEqual(p.js("[...document.querySelectorAll('[data-uc-tracker] button')].map((b) => b.textContent + b.getAttribute('aria-pressed')).join()"),
                                 "Topfalse,Bottomtrue,Offfalse", "the Milestones tracker starts at the bottom")
                self.assertEqual(p.js("document.querySelector('[data-uc-cfg-same]').textContent"),
                                 "Edit uses the same number but scrolls whenever a number is set, so you can reach every milestone; viewers get the scrolling only when it is On.")
                self.assertEqual(p.js("document.querySelector('[data-uc-cfg-tracker]').textContent"),
                                 "The counts by state; they double as the key. Top or bottom of the list, or off.")
                self.assertTrue(p.js("(r => r.left >= 0 && r.right <= innerWidth)(document.querySelector('#ucCfg').getBoundingClientRect())"), "fits the width")

    def test_changes_are_saved_in_the_milestones_body_and_read_back_after_a_reload(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                put_ms_view(self, None)
                p = self.show(cdp, width)
                self.edit(p)
                self.open_panel(p)
                p.js("(s => { s.value = '2'; s.dispatchEvent(new Event('change', {bubbles: true})); })(document.querySelector('#ucCfgN'))")
                self.wait_body(lambda v: v["n"] == 2, "n saved")
                p.js("document.querySelector('#ucCfgS').click()")
                self.wait_body(lambda v: v["scroll"] is True, "scroll saved")
                p.js("document.querySelector('[data-tracker=top]').click()")
                v = self.wait_body(lambda v: v["tracker"] == "top", "tracker saved")
                self.assertEqual(v, {"n": 2, "scroll": True, "tracker": "top"})
                self.assertIsNone(next(r for r in self.store.read("report_sections", "ABC") if r["type"] == "usecases")["body"] or None, "the use case summary is untouched")
                p.reload()
                self.edit(p)
                self.open_panel(p)
                self.assertEqual(p.js("document.querySelector('#ucCfgN').value"), "2")
                self.assertTrue(p.js("document.querySelector('#ucCfgS').checked"))
                self.assertEqual(p.js("document.querySelector('[data-tracker=top]').getAttribute('aria-pressed')"), "true")

    def test_a_tracker_only_change_writes_the_tracker_alone(self):
        with chrome() as cdp:
            put_ms_view(self, None)
            p = self.show(cdp, 1400)
            self.edit(p)
            self.open_panel(p)
            p.js("document.querySelector('[data-tracker=off]').click()")
            self.assertEqual(self.wait_body(lambda v: v.get("tracker") == "off", "saved"), {"tracker": "off"})

    def test_view_draws_the_first_n_when_scroll_is_off_and_scrolls_when_it_is_on(self):
        for width in (1400, 900):
            for view, rows, scrolls in (({"n": 2, "scroll": False, "tracker": "bottom"}, 2, False), ({"n": 2, "scroll": True, "tracker": "bottom"}, 7, True),
                                        ({"n": "all", "scroll": False, "tracker": "bottom"}, 7, False)):
                with self.subTest(width=width, view=view), chrome() as cdp:
                    put_ms_view(self, view)
                    p = self.show(cdp, width)
                    p.until(f"!!document.querySelector('{ROWS}')", "milestones")
                    got = p.js(SEE)
                    self.assertEqual((got["rows"], got["scrolls"], got["all"]), (rows, scrolls, False), "no Show all once a number is stored")
                    if scrolls:
                        self.assertEqual(got["overflow"], "auto")
                        self.assertLessEqual(abs(got["tall"] - got["twoRows"]), 2, "the list is as tall as its first two rows")
                    self.assertTrue(got["noScroll"])

    def test_edit_follows_the_number_and_scrolls_even_when_viewers_cannot(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                put_ms_view(self, {"n": 2, "scroll": False, "tracker": "bottom"})
                p = self.show(cdp, width)
                self.edit(p)
                got = p.js(SEE)
                self.assertEqual((got["rows"], got["scrolls"], got["all"]), (7, True, False))
                self.assertLessEqual(abs(got["tall"] - got["twoRows"]), 2)

    def test_with_no_number_stored_the_first_five_and_show_all_stay_as_they_were(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                put_ms_view(self, {"tracker": "bottom"})
                p = self.show(cdp, width)
                p.until(f"!!document.querySelector('{ROWS}')", "milestones")
                got = p.js(SEE)
                self.assertEqual((got["rows"], got["all"], got["scrolls"]), (5, True, False))

    def test_the_tracker_sits_top_or_bottom_or_is_off_and_the_default_is_the_bottom(self):
        for width in (1400, 900):
            for view, place in ((None, "bottom"), ({"tracker": "top"}, "top"), ({"tracker": "bottom"}, "bottom"), ({"tracker": "off"}, "off")):
                with self.subTest(width=width, tracker=place), chrome() as cdp:
                    put_ms_view(self, view)
                    p = self.show(cdp, width)
                    p.until(f"!!document.querySelector('{ROWS}')", "milestones")
                    got = p.js(SEE)
                    self.assertEqual(got["tracker"], place != "off")
                    self.assertEqual((got["trackerFirst"], got["trackerLast"]), (place == "top", place == "bottom"))

    def test_the_list_notes_say_what_the_published_page_shows(self):
        on = "Same as the published page: 2 of 7 milestones show at a time; scroll the list for the rest. Change this in Configure."
        off = ("Same as the published page: 2 of 7 milestones show at a time. Viewers cannot scroll, so they see only the first 2; "
               "scroll here to reach the others. Change this in Configure.")
        note = "(n => n ? n.textContent : null)(document.querySelector('.msv[data-place^=sec-] [data-msl-note]'))"
        region = "document.querySelector('.msv[data-place^=sec-] .msl').getAttribute('aria-label')"
        for width in (1400, 900):
            for scroll, edit_note, view_note in ((True, on, "Showing 2 of 7 \u00b7 scroll the list for the rest"), (False, off, "Showing 2 of 7 milestones")):
                with self.subTest(width=width, scroll=scroll), chrome() as cdp:
                    put_ms_view(self, {"n": 2, "scroll": scroll, "tracker": "bottom"})
                    p = self.show(cdp, width)
                    p.until(f"!!document.querySelector('{ROWS}')", "milestones")
                    self.assertEqual(p.js(note), view_note)
                    self.assertEqual(p.js(region), "Milestones; scroll to see more" if scroll else None)
                    self.assertEqual(p.js(SEE)["rows"], 7 if scroll else 2, "View slices to the first 2 when scroll is Off, the whole list when On")
                    self.edit(p)
                    self.assertEqual(p.js(note), edit_note)
                    self.assertEqual(p.js(region), "Milestones; scroll to see more", "Edit always scrolls once a number is set")
                    self.assertTrue(p.js("(r => r.left >= 0 && r.right <= innerWidth)(document.querySelector('[data-msl-note]').getBoundingClientRect())"))

    def test_no_note_without_a_number_or_when_the_number_covers_every_row(self):
        note = "!!document.querySelector('.msv[data-place^=sec-] [data-msl-note]')"
        for width in (1400, 900):
            for view in ({"tracker": "bottom"}, {"n": "all"}, {"n": 7}, {"n": 9, "scroll": True}):
                with self.subTest(width=width, view=view), chrome() as cdp:
                    put_ms_view(self, view)
                    p = self.show(cdp, width)
                    p.until(f"!!document.querySelector('{ROWS}')", "milestones")
                    self.assertFalse(p.js(note))
                    self.edit(p)
                    self.assertFalse(p.js(note))

    def test_the_milestones_page_ignores_the_setting(self):
        put_ms_view(self, {"n": 2, "scroll": False, "tracker": "off"})
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.js("location.hash = '#milestones&p=ABC'")
                p.until("!!document.querySelector('.msv[data-place=page] .msl > li')", "page rows")
                self.assertEqual(p.js("document.querySelectorAll('.msv[data-place=page] .msl > li').length"), 5)
                self.assertFalse(p.js("!!document.querySelector('.msv[data-place=page] [data-tracker]')"))


if __name__ == "__main__":
    unittest.main()
