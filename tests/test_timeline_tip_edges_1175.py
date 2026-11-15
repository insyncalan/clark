"""Row 1175: the name tip of a mark at either end of the line stays inside the line while the mark is open (scaled up).

The open mark is drawn larger about its centre, so the tip is kept inside the line after that scale.
Run: python3 dev/run_tests.py test_timeline_tip_edges_1175
Chrome launches at 1400 and 900 px, Quarter scale.
"""
import copy
import datetime
import tempfile
import unittest

from test_milestones_page import BrowserBase, Running, page
from test_server import chrome, wait

PROBE = """((i) => {
  const wrap = document.querySelector('.mv-wrap'), w = wrap.getBoundingClientRect(), strip = document.querySelector('.mv-strip').getBoundingClientRect();
  const m = document.querySelectorAll('.mv-mk[data-hid]')[i]; m.focus({preventScroll: true});
  const r = m.getBoundingClientRect(), c = getComputedStyle(m, '::after');
  const tx = new DOMMatrix(c.transform).m41, k = r.width / 24, wd = parseFloat(c.width);
  return {k, tipL: r.left + r.width / 2 + tx * k, tipR: r.left + r.width / 2 + (tx + wd) * k, boxL: w.left, boxR: w.right, stripL: strip.left, stripR: strip.right,
    scrollW: wrap.scrollWidth, clientW: wrap.clientWidth}; })"""


class TipEdges(BrowserBase, unittest.TestCase):
    def serve(self):
        base = self.store.data_for

        def data_for(code, **kw):
            d = copy.deepcopy(base(code, **kw))
            ms = d["milestones"] if code == "TUL" else []
            dates = sorted(x for m in ms for x in (m["baseline_date"], m["forecast_date"], m["actual_date"]) if x)
            if dates:      # a call that carries no dated milestone (a view of archived ones, say) is passed on as it is
                lo, hi = (datetime.date.fromisoformat(dates[0]), datetime.date.fromisoformat(dates[-1]))
                for i in range(4):   # four long names close together at each end: all but one are hidden; the late ones lie years out, so the line scrolls
                    for tag, day in (("E", lo - datetime.timedelta(days=30 - i)), ("L", hi + datetime.timedelta(days=1000 + i))):
                        ms.append(dict(ms[0], id=f"TUL-M-{tag}{i}", name=f"{'Early' if tag == 'E' else 'Late'} long milestone name number {i}",
                                       baseline_date=str(day), actual_date=None, status="Planned", sort_order=80 + i))
            return d
        s = Running(data_for=data_for, projects=lambda archived=False: self.projects, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        return s.port

    def test_a_tip_at_either_end_stays_inside_the_line_at_full_scale(self):
        port = self.serve()
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width, "#milestones&p=TUL", port)
                cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, sid)   # the page has the focus, so element.focus() matches :focus-visible on a Mac runner too
                cdp.js("document.querySelector('.mv-bar [data-scale-b=quarter]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.mv-mk[data-hid]').length", sid) > 4), f"{width}: names are hidden")
                n = cdp.js("document.querySelectorAll('.mv-mk[data-hid]').length", sid)
                for end, scroll in (("left", "0"), ("right", "w.scrollWidth")):
                    cdp.js(f"(() => {{ const w = document.querySelector('.mv-wrap'); w.scrollLeft = {scroll}; }})()", sid)
                    for i in range(n):
                        cdp.js(f"({PROBE})({i})", sid)
                        self.assertTrue(wait(lambda: cdp.js(f"({PROBE})({i})", sid)["k"] > 1.17), f"{width} mark {i}: the mark reaches its full scale")
                        got = cdp.js(f"({PROBE})({i})", sid)
                        where = f"{width} {end} mark {i} of {n}"
                        self.assertGreaterEqual(got["tipL"], got["stripL"] - 0.5, f"{where}: the tip does not pass the left end of the line")
                        self.assertLessEqual(got["tipR"], got["stripR"] + 0.5, f"{where}: the tip does not pass the right end of the line")


if __name__ == "__main__":
    unittest.main()
