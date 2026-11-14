"""Row 1159: the Milestones Timeline has Week, Month and Quarter like the Calendar; a name with no room is hidden and its mark keeps it.

Run: python3 dev/run_tests.py test_milestones_timeline_zoom_1159
Chrome launches at 1400 and 900 px.
"""
import unittest

from test_milestones_page import BrowserBase
from test_server import chrome, wait

HASH = "#milestones&p=TUL"
SPACING = """(() => { const m = [...document.querySelectorAll('.mv-mk[data-mark-at]')].sort((a, b) => a.dataset.markAt < b.dataset.markAt ? -1 : 1);
  const a = m[0], b = m[m.length - 1], days = (Date.parse(b.dataset.markAt) - Date.parse(a.dataset.markAt)) / 86400000;
  return (b.getBoundingClientRect().left - a.getBoundingClientRect().left) / days; })()"""


class Zoom(BrowserBase, unittest.TestCase):
    def pick(self, cdp, sid, scale):
        cdp.js(f"document.querySelector('.mv-bar [data-scale-b={scale}]').click()", sid)
        self.assertTrue(wait(lambda: cdp.js(f"document.querySelector('.mv-bar [data-scale-b={scale}]').getAttribute('aria-current')", sid) == "true"))

    def test_the_control_has_the_three_choices_and_each_changes_the_spacing(self):
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, HASH, port)
                self.assertEqual(cdp.js("[...document.querySelectorAll('.mv-bar .cal-sc button')].map(b => b.dataset.scaleB + ':' + b.getAttribute('aria-current'))", sid),
                                 ["week:false", "month:true", "quarter:false"], width)
                self.assertLessEqual(cdp.js("document.documentElement.scrollWidth - innerWidth", sid), 0, "no sideways scroll of the page")
                got = {}
                for s in ("week", "month", "quarter"):
                    self.pick(cdp, sid, s)
                    got[s] = cdp.js(SPACING, sid)
                self.assertGreater(got["week"], got["month"], width)
                self.assertGreater(got["month"], got["quarter"], width)

    def test_a_tight_scale_hides_names_that_have_no_room_and_the_mark_keeps_the_name(self):
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, HASH, port)
                self.pick(cdp, sid, "quarter")
                wait(lambda: cdp.js("document.querySelectorAll('.mv-lab').length", sid) < cdp.js("document.querySelectorAll('.mv-mk').length", sid))
                labs = cdp.js("document.querySelectorAll('.mv-lab').length", sid)
                marks = cdp.js("document.querySelectorAll('.mv-mk').length", sid)
                self.assertLess(labs, marks, f"{width}: some names are hidden")
                self.assertEqual(cdp.js("new Set([...document.querySelectorAll('.mv-lab')].map(e => e.style.top)).size", sid), 1, "one lane")
                self.assertEqual(cdp.js("[...document.querySelectorAll('.mv-mk[data-hid]')].every(e => e.getAttribute('aria-label') === e.dataset.hid && e.title === e.dataset.hid)", sid), True)
                self.assertEqual(cdp.js("document.querySelectorAll('.mv-mk[data-hid]').length", sid), marks - labs)
                self.assertEqual(cdp.js("document.querySelectorAll('.mv-meas[aria-hidden=true]').length", sid), marks - labs, "hidden names are not read twice")
                self.pick(cdp, sid, "week")
                wait(lambda: cdp.js("document.querySelectorAll('.mv-lab').length", sid) > labs)
                self.assertGreater(cdp.js("document.querySelectorAll('.mv-lab').length", sid), labs, "more room, more names")

    def test_the_scale_is_remembered_for_the_place_only(self):
        port = self.serve()
        with chrome() as cdp:
            sid = self.visit(cdp, 1400, HASH, port)
            self.pick(cdp, sid, "quarter")
            sid = self.visit(cdp, 1400, HASH, port)
            self.assertEqual(cdp.js("document.querySelector('.mv-bar [data-scale-b=quarter]').getAttribute('aria-current')", sid), "true")
            self.assertEqual(cdp.js("Object.keys(localStorage).filter(k => k.startsWith('clark.tlScale.'))", sid), ["clark.tlScale.page"])
            cdp.js("localStorage.setItem('clark.tlScale.page', JSON.stringify('decade'))", sid)
            sid = self.visit(cdp, 1400, HASH, port)
            self.assertEqual(cdp.js("document.querySelector('.mv-bar [data-scale-b=month]').getAttribute('aria-current')", sid), "true")


if __name__ == "__main__":
    unittest.main()
