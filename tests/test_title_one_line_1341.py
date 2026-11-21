"""Issue 1341: in Classic the project title in the editor bar stays on one line on every page, and the 900 px bar holds it.
Run: python3 dev/run_tests.py test_title_one_line_1341
Measured in Chrome at 1400 and 900 px with the Classic Theme layered: a long project name on the Gantt, Work items, Milestones and
Use cases pages, and the 'No project open' text on Settings. The title is one line (height not above its line height), the line under it
('Weekly report') stays inside the bar, and the page does not scroll sideways. Fictional data only.
"""
import re
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
    nameInside: nn.bottom <= b.bottom + 0.5 && nn.right <= b.right + 0.5, wide: document.documentElement.scrollWidth <= innerWidth,
    token: (() => { const r = document.documentElement; r.style.removeProperty('--topbar'); return parseFloat(getComputedStyle(r).getPropertyValue('--topbar')); })(),
    tabs: (() => { const t = [...document.querySelectorAll('.top-hdr .tab')], st = document.querySelector('.top-hdr .tabs'), inside = (e) => { const r = R(e); return r.top >= b.top - 0.5 && r.bottom <= b.bottom + 0.5 && r.left >= b.left - 0.5 && r.right <= b.right + 0.5; };
      return {n: t.length, all: t.every(inside), strip: !!st && inside(st)}; })()}; })()"""


class Title(Setup):
    def setUp(self):
        orig = testpage.html
        self.m = mock.patch.object(testpage, "html", lambda branding=None: page.layer_theme(orig(), theme.css("prototype-2.0")))
        self.m.start()
        self.addCleanup(self.m.stop)
        super().setUp()
        self.store.con.execute("UPDATE projects SET show_gantt_editor = 1 WHERE code = 'ABC'")      # the Gantt tab is on, so its page can be drawn

    def mock_off(self):
        self.m.stop()      # the Classic layer off: the page is the Cards one

    def look(self, width, view):
        with chrome() as cdp:
            p = self.show(cdp, width, False, standard=True)
            if view:
                p.js(f"document.querySelector('.tab[data-view={view}]').click()")
                p.until(f"!!document.querySelector('.tab[data-view={view}][aria-selected=true]')", "the page opened")
            p.js("(() => { const n = document.querySelector('.hdr-project'); window.__orig = (n.querySelector('span') || n).textContent.trim(); (n.querySelector('span') || n).textContent = %r; })()" % LONG)
            g = p.js(PROBE)
            g["orig"] = p.js("window.__orig")
            return g

    def check(self, width, view):
        g = self.look(width, view)
        self.assertEqual(g["text"], LONG)
        self.assertLessEqual(g["nameH"], g["lh"] + 1, "one line: %r" % (g,))
        self.assertEqual((g["ws"], g["to"], g["ov"]), ("nowrap", "ellipsis", "hidden"))
        self.assertTrue(g["lineInside"], "Weekly report stays in the bar: %r" % (g,))
        self.assertTrue(g["nameInside"])
        self.assertTrue(g["wide"], "no sideways scroll")
        self.assertEqual(g["tip"], g["orig"] + ". Click to change project", "the tooltip is the full project name with Click to change project, as row 1305 pins it (the aria-label keeps Change project)")
        self.assertEqual(g["barH"], g["token"], "the bar is as tall as the real --topbar token, read with the inline value removed")
        self.assertGreaterEqual(g["tabs"]["n"], 1, "at least one tab is drawn")
        self.assertTrue(g["tabs"]["all"] and g["tabs"]["strip"], "every tab and the tab strip lie inside the bar: %r" % (g,))
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

    def test_the_static_title_span_carries_the_full_name_as_its_tooltip(self):
        """Ruling a (12:43): the plain title span in the bar (no project switch) has title = the full name in Classic, and none in Cards.
        The standard test page always mounts the switch, so the span is pinned in the source: the title is the full name behind the Classic gate."""
        src = (ROOT / "src/clark/page/src/components/TopBar.jsx").read_text(encoding="utf-8")
        m = re.search(r'<span class="hdr-project hdr-static" id="project-name" title=\{classicTheme\(\) \? ([^}]*) : undefined\}>\{([^}]*)\}</span>', src)
        self.assertTrue(m, "the static title span has a title attribute, set only in Classic")
        self.assertEqual(m.group(1).strip(), m.group(2).strip(), "title and text are the same full name")
        self.assertEqual(len(re.findall(r'import \{ classicTheme \}', src)), 1)

    def test_cards_keep_the_change_project_tooltip(self):
        """With the Cards theme (no Classic layer) the header switch tooltip stays 'Click to change project' and the static span has no title."""
        src = (ROOT / "src/clark/page/src/edit/ProjectSwitch.jsx").read_text(encoding="utf-8")
        self.assertIn('tip={classicTheme() ? `${shown}. Click to change project` : "Click to change project"}', src)
        self.assertEqual(len(re.findall(r'import \{ classicTheme \}', src)), 1)
        self.assertIn("title={classicTheme() ? name || project.value || \"No project open\" : undefined}", (ROOT / "src/clark/page/src/components/TopBar.jsx").read_text(encoding="utf-8"))
        self.mock_off()
        with chrome() as cdp:
            p = self.show(cdp, 1400, False, standard=True)
            g = p.js("(() => { const n = document.querySelector('.hdr-project'); return {theme: !!document.getElementById('theme'), tip: n.getAttribute('title') || n.parentElement.getAttribute('title') || '', stat: !!document.querySelector('.hdr-static[title]')}; })()")
        self.assertFalse(g["theme"])
        self.assertEqual(g["tip"], "Click to change project")
        self.assertFalse(g["stat"])


for _w in (1400, 900):
    for _v in ("gantt", "work", "milestones", "usecases"):
        setattr(Title, f"test_{_v}_{_w}", lambda self, w=_w, v=_v: self.check(w, v))


if __name__ == "__main__":
    unittest.main()
