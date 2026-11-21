"""Row 1405: the ungrouped Use cases list under Classic: the box kept, shaded column heads 8px 12px, row sides 12, no line under the last row.
Chrome required. 1400 and 900 px, light and dark. Cards is pinned elsewhere (test_use_cases_redesign_1325)."""
import unittest

from clark import page, theme
from _demo import USER
from _real_server import real_server
import _testpage as testpage
from test_report_editor import Base, Pg, tearDownModule  # noqa: F401
from test_server import chrome
from test_use_cases_list import plant

MEASURE = """(() => {
  const q = (s, r) => (r || document).querySelector(s), cs = (e) => getComputedStyle(e);
  const box = q('#usecases .ucl-wrap > .wgroup'), th = [...document.querySelectorAll('#usecases thead tr.colh th')].filter((t) => t.getBoundingClientRect().width > 1);
  const rows = [...document.querySelectorAll('#usecases tbody tr[data-uc]')];
  const last = rows[rows.length - 1], first = rows[0];
  const side = (r) => [...r.children].filter((c) => c.getBoundingClientRect().width > 1);
  const bb = (e) => [cs(e).borderBottomWidth, cs(e).borderBottomStyle];
  const hd = th[0];
  return { box: [cs(box).borderTopWidth, cs(box).borderTopStyle, cs(box).borderTopColor, cs(box).borderTopLeftRadius, cs(box).overflow, cs(box).backgroundColor],
    th: th.map((t) => [cs(t).backgroundColor, cs(t).paddingTop, cs(t).paddingBottom, cs(t).paddingLeft, cs(t).paddingRight, cs(t).borderBottomWidth, cs(t).borderBottomStyle, cs(t).borderBottomColor, cs(t).fontSize, cs(t).fontWeight, cs(t).letterSpacing, cs(t).color]),
    firstL: cs(side(first)[0]).paddingLeft, lastR: cs(side(first).slice(-1)[0]).paddingRight,
    lastRowRules: [...last.children].map((c) => bb(c).join(' ')), firstRowTop: [...first.children].map((c) => cs(c).borderTopWidth),
    midRule: bb(rows[0].querySelector('td.c-item')) , rowCount: rows.length,
    bg: cs(document.body).backgroundColor, hdLeftGap: hd.getBoundingClientRect().left - box.getBoundingClientRect().left,
    heads: th.length }; })()"""

LIGHT = {"bg": "rgb(243, 245, 251)", "border": "rgb(217, 224, 239)", "color": "rgb(71, 85, 119)"}


class Box(Base):
    css = theme.css("prototype-2.0")

    def setUp(self):
        super().setUp()
        plant(self)
        self.s.close()
        html = page.layer_theme(testpage.html(), self.css)
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: html, seam=self.seam)
        self.addCleanup(self.s.close)

    def measure(self, cdp, width, scheme):
        p = Pg.at(self, cdp, self.s.port, "#usecases&p=ABC")
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, p.sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, p.sid)
        p.js(f"document.documentElement.setAttribute('data-theme', '{scheme}')")
        p.until("document.querySelectorAll('#usecases [data-uc]').length > 1", "the list drew")
        return p.js(MEASURE)

    def test_the_box_the_shaded_heads_the_side_padding_and_the_last_row(self):
        for w in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=w, scheme=scheme), chrome() as cdp:
                    m = self.measure(cdp, w, scheme)
                    self.assertEqual(m["box"][:2], ["1px", "solid"], "the box is kept (1 px line)")
                    self.assertEqual(m["box"][3], "12px", "the box keeps its 12 px radius")
                    self.assertEqual(m["box"][4], "hidden", "the box clips its corners")
                    self.assertGreaterEqual(m["heads"], 5)
                    for t in m["th"]:
                        self.assertEqual(t[1:5], ["8px", "8px", "12px", "12px"], "heads 8px 12px")
                        self.assertEqual(t[5:7], ["1px", "solid"], "one line under the heads")
                        self.assertEqual(t[8:11], ["13px", "500", "1.04px"], "13px / 500 / .08em")
                    self.assertEqual(m["firstL"], "12px")
                    self.assertEqual(m["lastR"], "12px")
                    for r in m["lastRowRules"]:
                        self.assertTrue(r.startswith("0px"), "no line under the last row: " + r)
                    self.assertEqual(m["firstRowTop"], ["0px"] * len(m["firstRowTop"]), "the heads' line is the only one above the first row")
                    self.assertTrue(m["midRule"][0] == "1px", "the rows above the last keep their line")
                    if scheme == "light":
                        self.assertEqual(m["box"][2], LIGHT["border"])
                        for t in m["th"]:
                            self.assertEqual(t[0], LIGHT["bg"], "heads fill #F3F5FB")
                            self.assertEqual(t[7], LIGHT["border"])
                            self.assertEqual(t[11], LIGHT["color"], "heads text #475577")
                    else:
                        for t in m["th"]:
                            self.assertNotEqual(t[0], LIGHT["bg"], "dark: the strip is the dark band, not the light fill")
                            self.assertNotEqual(t[0], "rgba(0, 0, 0, 0)", "dark: the strip is filled")


if __name__ == "__main__":
    unittest.main()
