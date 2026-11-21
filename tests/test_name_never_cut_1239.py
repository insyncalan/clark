"""Row 1239: the project name in the header is never cut with an ellipsis and never clipped. A long name is shown whole: it wraps to more
lines and the bar grows to hold it (the --topbar token follows the bar's real height). In the editor header at 1400
and 900 px (Cards; the Classic look and the published file are one line since row 1305). Chrome is required: these tests fail, never skip, without it.

Run: python3 dev/run_tests.py test_name_never_cut_1239
"""
import unittest

import test_publish_dialog as dialog
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

LONG = "Example Client Records Migration Programme, phase two, northern region, including the extended regional rollout and wind-down"
ONE_WORD = "ExampleClientRecordsMigrationProgrammePhaseTwoNorthernRegionExtendedRegionalRolloutAndWindDownWorkstream"

MEASURE = """(() => {
  const bar = document.querySelector('header.top'), name = document.querySelector(%s), text = name.textContent;
  const chain = []; for (let e = name; e && e !== bar; e = e.parentElement) chain.push(e);
  const line = document.querySelector('.top .hdr-line, .top .top-line'), css = getComputedStyle(name);
  const b = bar.getBoundingClientRect(), n = name.getBoundingClientRect();
  return {text: text, ellipsis: chain.filter((e) => getComputedStyle(e).textOverflow === 'ellipsis').length,
    clipped: chain.filter((e) => { const r = e.getBoundingClientRect(); return n.bottom > r.bottom + 0.5 || n.right > r.right + 0.5; }).map((e) => e.tagName + '.' + e.className),
    hidden: chain.filter((e) => getComputedStyle(e).overflow !== 'visible').length,
    lines: Math.round(n.height / parseFloat(css.lineHeight)), nameBottom: n.bottom, nameRight: n.right,
    lineBottom: line ? line.getBoundingClientRect().bottom : 0, barBottom: b.bottom, barHeight: b.height,
    topbar: getComputedStyle(document.documentElement).getPropertyValue('--topbar').trim(), win: innerWidth,
    page: document.documentElement.scrollWidth - document.documentElement.clientWidth};
})()"""


class Check:
    def whole(self, p, selector, name, where):
        p.js(f"document.querySelector({selector!r}).textContent = {name!r}")
        p.until("getComputedStyle(document.documentElement).getPropertyValue('--topbar').trim() === document.querySelector('header.top').getBoundingClientRect().height + 'px'", "--topbar followed the bar's height")
        got = p.js(MEASURE % repr(selector))
        self.assertEqual(got["text"], name, "the whole name is in the page " + where)
        self.assertEqual(got["ellipsis"], 0, "no element around the name ends in an ellipsis " + where)
        self.assertEqual(got["hidden"], 0, "no element around the name hides what runs past it " + where)
        self.assertEqual(got["clipped"], [], "the name is not clipped " + where)
        self.assertLessEqual(got["nameRight"], got["win"] + 0.5, "the name runs past the window " + where)
        self.assertLessEqual(got["page"], 0, "the page scrolls sideways " + where)
        self.assertGreaterEqual(got["barBottom"], got["nameBottom"] - 0.5, "the bar holds the name " + where)
        self.assertGreaterEqual(got["barBottom"], got["lineBottom"] - 0.5, "the bar holds the line under the name " + where)
        self.assertAlmostEqual(float(got["topbar"][:-2]), got["barHeight"], places=2, msg="--topbar is the bar's real height " + where)
        return got


class Editor(Check, dialog.Base):
    def check(self, width, name):
        with chrome() as cdp:
            p = self.page(cdp)
            p.width(width)
            p.until("!!document.querySelector('.top .hdr-project > span')", "the bar shows")
            got = self.whole(p, ".top .hdr-project > span", name, f"in the editor at {width} px")
            if name == LONG:
                self.assertGreater(got["lines"], 1, f"a long name wraps to more lines at {width} px")


for _cls in (Editor,):
    for _w in (1400, 900):
        for _k, _n in (("words", LONG), ("one_word", ONE_WORD)):
            setattr(_cls, f"test_{_w}_{_k}", lambda self, w=_w, n=_n: self.check(w, n))


if __name__ == "__main__":
    unittest.main()
