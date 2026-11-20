"""Issue 1341: in Classic the project title in the editor bar stays on one line on every page, and the 900 px bar holds it.
Run: python3 dev/run_tests.py test_title_one_line_1341
Measured in Chrome at 1400 and 900 px with the Classic Theme layered: a long project name on the Gantt, Work items, Milestones and
Use cases pages, and the 'No project open' text on Settings. The title is one line (height not above its line height), the line under it
('Weekly report') stays inside the bar, and the page does not scroll sideways. Fictional data only.
"""
import unittest
from unittest import mock

from _paths import ROOT  # noqa: F401
from test_glance_page import Setup
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome
import _testpage as testpage
from clark import page, theme

LONG = "Example Client Records Migration Programme, phase two, northern region, including the extended regional rollout and wind-down"
PROBE = """(() => { const R = (e) => e.getBoundingClientRect(), bar = document.querySelector('.top-hdr'), n = document.querySelector('.hdr-project'),
  s = n.querySelector('span') || n, l = document.querySelector('.hdr-line'), c = getComputedStyle(s), b = R(bar), nn = R(n), ll = R(l);
  return {view: document.querySelector('.tab[aria-selected=true]') ? document.querySelector('.tab[aria-selected=true]').dataset.view : null, text: s.textContent,
    nameH: nn.height, tip: n.getAttribute('title') || n.parentElement.getAttribute('title') || '', nameTop: nn.top, lh: parseFloat(getComputedStyle(n).lineHeight), ws: c.whiteSpace, to: c.textOverflow, ov: c.overflow,
    lineInside: ll.top >= b.top - 0.5 && ll.bottom <= b.bottom + 0.5 && ll.right <= b.right + 0.5, lineBottom: ll.bottom, barBottom: b.bottom, barH: b.height,
    nameInside: nn.bottom <= b.bottom + 0.5 && nn.right <= b.right + 0.5, wide: document.documentElement.scrollWidth <= innerWidth}; })()"""


class Title(Setup):
    def setUp(self):
        orig = testpage.html
        m = mock.patch.object(testpage, "html", lambda branding=None: page.layer_theme(orig(), theme.css("prototype-2.0")))
        m.start()
        self.addCleanup(m.stop)
        super().setUp()
        self.store.con.execute("UPDATE projects SET show_gantt_editor = 1 WHERE code = 'ABC'")      # the Gantt tab is on, so its page can be drawn

    def look(self, width, view):
        with chrome() as cdp:
            p = self.show(cdp, width, False, standard=True)
            if view:
                p.js(f"document.querySelector('.tab[data-view={view}]').click()")
                p.until(f"!!document.querySelector('.tab[data-view={view}][aria-selected=true]')", "the page opened")
            p.js("(() => { const n = document.querySelector('.hdr-project'); (n.querySelector('span') || n).textContent = %r; })()" % LONG)
            return p.js(PROBE)

    def check(self, width, view):
        g = self.look(width, view)
        self.assertEqual(g["text"], LONG)
        self.assertLessEqual(g["nameH"], g["lh"] + 1, "one line: %r" % (g,))
        self.assertEqual((g["ws"], g["to"], g["ov"]), ("nowrap", "ellipsis", "hidden"))
        self.assertTrue(g["lineInside"], "Weekly report stays in the bar: %r" % (g,))
        self.assertTrue(g["nameInside"])
        self.assertTrue(g["wide"], "no sideways scroll")
        self.assertEqual(g["tip"], g["text"], "row 1341 ruling: the tooltip is the full project name (the aria-label keeps Change project)")
        if width == 1400:
            self.assertEqual(g["barH"], 85, "row 1341 ruling: the bar is 85 px at 1400 (Classic prototype)")
        else:
            self.assertEqual(g["barH"], 103, "the 900 bar stays at its fixed 103 px (note, not ruled)")

    def test_the_static_title_with_no_inner_span_is_one_line(self):
        """The bar's plain name (Settings with no project open) is the .hdr-project element itself, with no span inside."""
        for width in (1400, 900):
            for text in ("No project open", LONG):
                with chrome() as cdp:
                    p = self.show(cdp, width, False, standard=True)
                    p.js("location.hash = '#settings'")
                    p.until("location.hash.startsWith('#settings')", "Settings opened")
                    p.js("document.querySelector('.hdr-project').textContent = %r" % text)
                    g = p.js(PROBE.replace("s = n.querySelector('span') || n", "s = n"))
                    self.assertEqual(g["text"], text)
                    self.assertLessEqual(g["nameH"], g["lh"] + 1, (width, text, g))
                    self.assertEqual((g["ws"], g["to"], g["ov"]), ("nowrap", "ellipsis", "hidden"), (width, text))
                    self.assertTrue(g["lineInside"] and g["wide"], (width, text, g))


for _w in (1400, 900):
    for _v in ("gantt", "work", "milestones", "usecases"):
        setattr(Title, f"test_{_v}_{_w}", lambda self, w=_w, v=_v: self.check(w, v))


if __name__ == "__main__":
    unittest.main()
