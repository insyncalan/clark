"""Row 1299 AP10: the look of the project tabs on the five Project settings pages, in a real browser at 1400 and 900 px, light and dark.
Run: python3 dev/run_tests.py test_settings_tabs_1299

What is asserted (Classic): a tab is a pill (radius 999px, padding 5px 14px, 13.5px type); the open one has the brand fill (--brand-navy) with white text and weight 600, the others
no fill; the bar is pinned under the top bar (sticky, top = the top bar's height), one row, never taller than 44px, and scrolls sideways when the projects do not fit; the order is the
project list's order; an archived project has no tab. Chrome is required: these tests fail, never skip, without it.
"""
import unittest

from clark import page, theme
import _testpage as testpage
from test_publish_dialog import Base
from test_publish_route import Rig
from test_server import chrome
from test_settings_bar import calm
from test_settings_head import address

WIDTHS = (1400, 900)
MODES = ("light", "dark")
LIVE = [{"code": "PUB", "name": "Harbour Bridge Programme"}, {"code": "ABC", "name": "Second Programme"}, {"code": "ZED", "name": "Third Programme"}]
GONE = {"code": "OLD", "name": "Archived Programme"}
TABS = "[...document.querySelectorAll('.set-tabs .set-tab:not([data-all])')]"      # the project tabs (ask clark's leading All projects tab is data-all)


class Rigged(Base):
    """A Classic page whose project list is `listed` (`archived=True` adds the archived one, which the page never asks for)."""
    listed = LIVE

    def setUp(self):
        css = theme.css("prototype-2.0")
        self.rig = Rig(self, saved=self.saved, page_html=lambda: page.layer_theme(testpage.html(), css))
        self.rig.httpd.projects = lambda archived=False: list(self.listed) + ([GONE] if archived else [])

    def open_settings(self, p, w, mode="light", slug="people", project="PUB"):
        p.width(w)
        calm(p, mode)
        p.js(f"location.hash = '{address(slug, project)}'")
        p.until("!!document.querySelector('.set-nav .set-chip[aria-current]') && !!document.querySelector('.set-cards').children.length", "Settings drew")


class TabLook(Rigged):
    listed = LIVE + [{"code": f"P{i:02d}", "name": f"A programme with a long name number {i}"} for i in range(12)]

    def test_tabs_look_order_and_archived(self):
        want = [p["name"] for p in self.listed]
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_settings(p, w, mode, slug="brand")
                    p.until(f"{TABS}.length === {len(want)}", "the tabs drew")
                    self.assertEqual(p.js(f"{TABS}.map(b => b.textContent)"), want, "the project list's order, no archived project")
                    look = p.js(f"""(() => {{ const [a, b] = {TABS}, cs = (e) => getComputedStyle(e), probe = document.createElement('i'); probe.style.background = 'var(--brand-navy)'; document.body.append(probe);
                        const navy = cs(probe).backgroundColor; probe.remove();
                        return {{ radius: cs(a).borderTopLeftRadius, pad: cs(a).padding, size: cs(a).fontSize, fill: cs(a).backgroundColor, navy, ink: cs(a).color, weight: cs(a).fontWeight,
                                 other: cs(b).backgroundColor, otherWeight: cs(b).fontWeight, tops: {TABS}.map(t => Math.round(t.getBoundingClientRect().top)) }}; }})()""")
                    self.assertEqual((look["radius"], look["pad"], look["size"]), ("999px", "5px 14px", "13.5px"), "a pill")
                    self.assertEqual(look["fill"], look["navy"], "the open tab has the brand fill")
                    self.assertEqual(look["ink"], "rgb(255, 255, 255)", "white text on the fill")
                    self.assertEqual(look["weight"], "600")
                    self.assertNotEqual(look["other"], look["navy"], "the other tabs have no fill")
                    self.assertNotEqual(look["otherWeight"], "600")
                    self.assertEqual(len(set(look["tops"])), 1, "one row")
                    bar = p.js("""(() => { const n = document.querySelector('.set-tabs'), ul = n.querySelector('ul'), cs = getComputedStyle(n);
                        return { h: n.getBoundingClientRect().height, pos: cs.position, top: cs.top, wide: ul.scrollWidth > ul.clientWidth, over: cs.overflowX + '/' + getComputedStyle(ul).overflowX,
                                 bar: getComputedStyle(document.documentElement).getPropertyValue('--topbar').trim() }; })()""")
                    self.assertLessEqual(bar["h"], 44, "never taller than 44px")
                    self.assertEqual((bar["pos"], bar["top"]), ("sticky", bar["bar"]), "pinned under the top bar")
                    self.assertTrue(bar["wide"], "more tabs than fit: the row scrolls sideways")
                    self.assertEqual(p.js("document.querySelector('.set-tabs ul').style.flexWrap || getComputedStyle(document.querySelector('.set-tabs ul')).flexWrap"), "nowrap")
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "the page does not scroll sideways")


if __name__ == "__main__":
    unittest.main()
