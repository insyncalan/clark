"""Row 1341: the Classic top bar shows the project title on ONE line on every page (nowrap + ellipsis), the full name is the tooltip.

Run: python3 dev/run_tests.py test_title_one_line_1341
Real Chrome, Classic Theme layered, 1400 and 900 px, on Gantt, Work items, Milestones and Settings, with an 80 character name.
The bar's height is the --topbar token the stylesheet gives (85 px at 1400, 103 px at 900 in Classic); the title never grows it.
Fictional data only.
"""
import unittest
from unittest import mock

from _paths import ROOT  # noqa: F401
from _demo import USER
from test_glance_page import Setup
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome
import _testpage as testpage
from clark import page, theme

LONG = "Northern Harbour Payments Modernisation Programme Phase Two Delivery Plan 2026-27 Extended"
PROBE = """(() => { const q = (s) => document.querySelector(s), R = (e) => e.getBoundingClientRect(), bar = q('.top-hdr'), btn = q('.top-hdr .hdr-project'),
  box = btn.querySelector('span') || btn, line = q('.top-hdr .hdr-line .hdr-kind'), root = document.documentElement;
  const inline = root.style.getPropertyValue('--topbar'); root.style.removeProperty('--topbar'); const token = getComputedStyle(root).getPropertyValue('--topbar').trim();
  if (inline) root.style.setProperty('--topbar', inline);
  const c = getComputedStyle(box), lh = parseFloat(getComputedStyle(btn).lineHeight), b = R(bar), l = R(line), n = R(btn);
  return {text: btn.textContent.trim(), tip: btn.getAttribute('title'), aria: btn.getAttribute('aria-label'), h: R(box).height, lh, ws: c.whiteSpace, to: c.textOverflow, ov: c.overflow,
    barH: b.height, token, sh: bar.scrollHeight, ch: bar.clientHeight, wide: root.scrollWidth <= window.innerWidth,
    lineIn: l.top >= b.top && l.bottom <= b.bottom && l.left >= b.left && l.right <= b.right, nameIn: n.top >= b.top && n.bottom <= b.bottom}; })()"""


class OneLine(Setup):
    def setUp(self):
        orig = testpage.html
        m = mock.patch.object(testpage, "html", lambda branding=None: page.layer_theme(orig(), theme.css("prototype-2.0")))
        m.start()
        self.addCleanup(m.stop)
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"name": LONG})

    def check(self, view, width):
        with chrome() as cdp:
            p = self.show(cdp, width, hash_="#%s&p=ABC" % view, settings=True, standard=True)
            p.until("!!document.querySelector('.top-hdr .hdr-project') && document.querySelector('.top-hdr .hdr-project').textContent.includes('Northern Harbour')", "the bar shows the long name")
            p.until("!!document.querySelector('main') && document.querySelector('main').innerText.length > 20", "the page drew")
            g = p.js(PROBE)
        ctx = (view, width, g)
        self.assertEqual(g["text"], LONG, ctx)
        self.assertLessEqual(g["h"], g["lh"] + 1, ("one line", ctx))
        self.assertEqual((g["ws"], g["to"], g["ov"]), ("nowrap", "ellipsis", "hidden"), ctx)
        self.assertEqual(g["sh"], g["ch"], ("nothing overflows the bar", ctx))
        self.assertEqual(g["barH"], float(g["token"][:-2]), ("the bar is exactly the --topbar token", ctx))
        self.assertEqual(g["token"], "85px" if width == 1400 else "103px", ctx)
        self.assertTrue(g["lineIn"], ("WEEKLY REPORT is inside the bar", ctx))
        self.assertTrue(g["nameIn"], ctx)
        self.assertTrue(g["wide"], ("no sideways scroll", ctx))
        self.assertEqual(g["tip"], LONG, ("the tooltip is the full name", ctx))
        self.assertNotIn("Click to change project", g["tip"])
        self.assertEqual(g["aria"], "Project: %s. Change project" % LONG, ctx)


for _view in ("gantt", "work", "milestones", "settings"):
    for _w in (1400, 900):
        setattr(OneLine, "test_%s_%d" % (_view, _w), (lambda v, w: lambda self: self.check(v, w))(_view, _w))


class Others(unittest.TestCase):
    def test_the_header_switch_is_the_only_button_that_lost_the_click_hint_and_cards_is_unchanged(self):
        src = (ROOT / "src" / "clark" / "page" / "src" / "edit" / "ProjectSwitch.jsx").read_text(encoding="utf-8")
        self.assertEqual(src.count('tip="Click to change project"'), 2, "the Cover and the other button keep it")
        self.assertIn('btnCls="hdr-project" label={shown} tip={classicTheme() ? shown : "Click to change project"}', src)
        bar = (ROOT / "src" / "clark" / "page" / "src" / "components" / "TopBar.jsx").read_text(encoding="utf-8")
        self.assertIn('id="project-name" title={classicTheme() ? (name || project.value || "No project open") : undefined}', bar, "the static title carries the full name")
        cards = page.page_html(branding=page.NO_BRAND)
        self.assertNotIn("Row 1341", cards)


if __name__ == "__main__":
    unittest.main()
