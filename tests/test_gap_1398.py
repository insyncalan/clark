"""Row 1398 gap: the Classic Milestones calendar as the prototype draws it (cell 78, soft rules, weekend tint only, today box, weekday names 13px 600, one-line chips).
Run: python3 dev/run_tests.py test_gap_1398   Chrome required."""
import tempfile
import unittest

from clark import page
from test_milestones_page import BrowserBase
from test_server import Running, chrome, wait
from test_work_filters import need_chrome

JS = """(() => { const q = s => document.querySelector(s), cs = (e, p) => getComputedStyle(e)[p], cells = [...document.querySelectorAll('.cal-g > .cal-d')];
  const out = cells.find(c => c.classList.contains('out')), plain = cells.find((c, i) => i % 7 < 5 && !c.classList.contains('out') && !c.classList.contains('today')), t = q('.cal-d.today'), d = q('.cal-dow span'), chip = q('.cal-ms'), n = t && t.querySelector('.cal-n');
  return {minH: Math.round(plain.getBoundingClientRect().height), border: cs(plain, 'borderBottomColor'), outBg: out ? cs(out, 'backgroundColor') : 'none', satBg: cs(cells[5], 'backgroundColor'), sunBg: cs(cells[6], 'backgroundColor'), plainBg: cs(plain, 'backgroundColor'),
    todayShadow: t ? cs(t, 'boxShadow') : '', todayNumBg: n ? cs(n, 'backgroundColor') : '', todayNumW: n ? cs(n, 'fontWeight') : '',
    gridBorder: [cs(q('.cal-g'), 'borderTopColor'), cs(q('.cal-g'), 'borderLeftColor')], cellRight: cs(plain, 'borderRightColor'), dowRowBorder: [cs(q('.cal-dow'), 'borderTopColor'), cs(q('.cal-dow'), 'borderLeftColor'), cs(d, 'borderRightColor'), cs(d, 'borderBottomColor')], upper: cs(d, 'textTransform'),
    chipClip: chip ? [cs(chip.querySelector('span'), 'overflow'), cs(chip.querySelector('span'), 'textOverflow')] : [],
    dowSize: cs(d, 'fontSize'), dowW: cs(d, 'fontWeight'), dowCase: cs(d, 'textTransform'), dowBorder: cs(d, 'borderBottomWidth'),
    chipSize: chip ? cs(chip, 'fontSize') : '', chipPad: chip ? cs(chip, 'paddingTop') + ' ' + cs(chip, 'paddingLeft') : '', chipBg: chip ? cs(chip, 'backgroundColor') : '', chipWs: chip ? cs(chip.querySelector('span'), 'whiteSpace') : '', scroll: document.documentElement.scrollWidth <= window.innerWidth}; })()"""


class Gap1398(BrowserBase, unittest.TestCase):
    def serve(self):
        s = Running(data_for=self.store.data_for, projects=lambda archived=False: self.projects, page_html=lambda: page.page_html(tempfile.mkdtemp(), theme="prototype-2.0"))
        self.addCleanup(s.close)
        return s.port

    def test_calendar_at_1400(self):
        need_chrome()
        port = self.serve()
        with chrome() as cdp:
            sid = self.open_calendar(cdp, port)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.cal-d.today .cal-n') && !!document.querySelector('.cal-ms')", sid)))
            g = cdp.js(JS, sid)
        print("GAP1398", g)
        self.assertEqual(g["minH"], 78)
        self.assertEqual(g["border"], "rgb(233, 237, 246)")
        self.assertEqual(g["outBg"], "rgba(0, 0, 0, 0)")
        self.assertEqual((g["satBg"], g["sunBg"]), ("rgb(246, 248, 252)",) * 2)
        self.assertEqual(g["plainBg"], "rgba(0, 0, 0, 0)")
        self.assertIn("rgb(91, 71, 216)", g["todayShadow"])
        self.assertIn("2px", g["todayShadow"])
        self.assertEqual(g["todayNumBg"], "rgba(0, 0, 0, 0)")
        self.assertEqual(g["todayNumW"], "700")
        self.assertEqual((g["dowSize"], g["dowW"], g["dowCase"], g["dowBorder"]), ("13px", "600", "none", "1px"))
        self.assertEqual((g["chipSize"], g["chipPad"], g["chipBg"], g["chipWs"]), ("13px", "1px 4px", "rgb(243, 245, 251)", "nowrap"))
        soft = "rgb(233, 237, 246)"
        self.assertEqual(g["gridBorder"], [soft, soft])
        self.assertEqual(g["cellRight"], soft)
        self.assertEqual(g["dowRowBorder"], [soft] * 4)
        self.assertEqual(g["chipClip"], ["hidden", "ellipsis"])
        self.assertTrue(g["scroll"])

    def test_cards_keeps_its_own_calendar_at_1400(self):
        need_chrome()
        s = Running(data_for=self.store.data_for, projects=lambda archived=False: self.projects, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        with chrome() as cdp:
            sid = self.open_calendar(cdp, s.port)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.cal-d.today .cal-n') && !!document.querySelector('.cal-ms')", sid)))
            g = cdp.js(JS, sid)
        self.assertEqual(g["minH"], 88)
        self.assertEqual(g["dowCase"], "uppercase")
        self.assertEqual(g["chipWs"], "normal")


if __name__ == "__main__":
    unittest.main()
