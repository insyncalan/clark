"""Row 1324 (Grouped view, Option A), Use cases (commit c-d): the editor list and the published list draw the Work items heading line, as Chrome computes it, at 1400 and 900 px, light and dark.

Run: python3 dev/run_tests.py test_grouped_heading_1324_cases
Cards and Classic: the group is a heading line (no tile, no band), the column header is drawn once on top, the rows keep their hairlines (the last row of a group too),
the flat list keeps its card, the collapse button keeps its focus ring and a contrast of 4.5 to 1. A published file draws the same heading (same classes, no new design).
"""
import json
import unittest

from _grouped_1324 import LiveBase, NAME, SIZES, FACTS, RATIO, RING, contrast_ok, chrome, wait, tearDownModule  # noqa: F401
import test_use_cases_list as T


class Live(LiveBase):
    def test_use_cases_groups_are_heading_lines_with_one_column_header(self):
        for scheme in ("light", "dark"):
            for width in SIZES:
                for theme in (None, NAME):
                    with self.subTest(scheme=scheme, width=width, theme=theme), chrome() as cdp:
                        sid = self.cases(cdp, width, scheme, theme)
                        f = self.facts(cdp, sid, "#usecases", ".ucl-group", ".ucl-grp")
                        tag = f"cases {theme} {scheme} {width}"
                        self.line(tag, f, f["heading"], f["muted"])
                        got = json.loads(cdp.js("""JSON.stringify((() => { const g = (e, k) => getComputedStyle(e)[k], box = document.querySelector('#usecases .ucl-box'), cols = [...document.querySelectorAll('#usecases .ucl-cols')];
                          const lasts = [...document.querySelectorAll('#usecases .ucl-group .ucl-list > li:last-child .ucl-row, #usecases .ucl-group .ucl-list > .ucl-row:last-child')];
                          const rows = [...document.querySelectorAll('#usecases .ucl-group .ucl-row')];
                          return { box: [g(box, 'borderTopWidth'), g(box, 'borderTopLeftRadius'), g(box, 'backgroundColor'), g(box, 'overflowX')], cols: cols.length, colsBg: g(cols[0], 'backgroundColor'),
                            colsAbove: cols[0].getBoundingClientRect().bottom <= document.querySelector('#usecases .ucl-group').getBoundingClientRect().top + 1, colsCase: g(cols[0], 'textTransform'),
                            lasts: lasts.map((e) => g(e, 'borderBottomWidth')), lastCount: lasts.length, groups: document.querySelectorAll('#usecases .ucl-group').length,
                            rowPadL: [...new Set(rows.map((e) => g(e, 'paddingLeft')))], colsPadL: g(cols[0], 'paddingLeft') }; })())""", sid))
                        self.assertEqual(got["box"], ["0px", "0px", "rgba(0, 0, 0, 0)", "visible"], tag + ": the list box is not a tile")
                        self.assertEqual(got["cols"], 1, tag + ": the column header is drawn once")
                        self.assertEqual(got["colsBg"], "rgba(0, 0, 0, 0)", tag + ": no grey strip behind the column header")
                        self.assertEqual(got["colsCase"], "none", tag + ": the column header is not in capitals")
                        self.assertTrue(got["colsAbove"], tag + ": on top of the first group")
                        self.assertEqual(got["lastCount"], got["groups"], tag + ": a last row in every group")
                        self.assertEqual(set(got["lasts"]), {"1px"}, tag + ": the last row of a group keeps its bottom hairline")
                        self.assertEqual(got["rowPadL"], [got["colsPadL"]], tag + ": the rows and the column header start at the same place")

    def test_use_cases_flat_list_keeps_its_card_under_classic(self):
        with chrome() as cdp:
            sid = self.cases(cdp, 1400, "light", NAME, group="nothing")
            box = json.loads(cdp.js("JSON.stringify((() => { const s = getComputedStyle(document.querySelector('#usecases .ucl-box')); return [s.borderTopWidth, s.borderTopLeftRadius, s.overflowX]; })())", sid))
            self.assertEqual((box[0], box[2]), ("1px", "hidden"), "the flat Classic list is still the framed card")
            self.assertNotEqual(box[1], "0px")

    def test_use_cases_collapse_button_focus_ring_and_contrast(self):
        for scheme in ("light", "dark"):
            for width in SIZES:
                for theme in (None, NAME):
                    with self.subTest(scheme=scheme, width=width, theme=theme), chrome() as cdp:
                        sid = self.cases(cdp, width, scheme, theme)
                        ring = json.loads(cdp.js("JSON.stringify(%s('#usecases .ucl-group .grp-b'))" % RING, sid))
                        self.assertEqual((ring["clipped"], ring["style"], ring["width"], ring["focused"]), (False, "solid", "2px", True), f"cases {scheme} {width} {theme}")
                        low = contrast_ok(json.loads(cdp.js("JSON.stringify(%s(['#usecases .grp-b .gl', '#usecases .grp-b .gc']))" % RATIO, sid)))
                        self.assertEqual(low, [], f"cases heading and count contrast {scheme} {width} {theme}")


class Published(T.Published):
    """The published file (the setup of test_use_cases_list.Published, without its tests)."""


for _n in [n for n in dir(Published) if n.startswith("test")]:
    setattr(Published, _n, None)


class PublishedCases(Published):
    def test_a_published_use_case_group_is_the_heading_line_of_work_items(self):
        path = self.publish()
        for scheme in ("light", "dark"):
            for width in SIZES:
                with self.subTest(scheme=scheme, width=width), chrome() as cdp:
                    p = self.draw(cdp, path, "#usecases&p=ABC")
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                    p.js("document.documentElement.dataset.theme = %s" % json.dumps(scheme))
                    p.js("document.querySelector('#ucp-group, [aria-label^=\"Group by\"]').click()")
                    p.until("!![...document.querySelectorAll('[role^=menuitem]')].find(e => e.textContent.trim() === 'Status')", "the menu")
                    p.js("[...document.querySelectorAll('[role^=menuitem]')].find(e => e.textContent.trim() === 'Status').click()")
                    p.until("document.querySelectorAll('.ucp-group').length >= 1", "grouped")
                    f = json.loads(p.js("JSON.stringify(%s('#usecases-file', '.ucp-group', '.ucp-grp'))" % FACTS))
                    self.assertTrue(f["groups"])
                    for n, w in enumerate(f["groups"]):
                        t = f"published cases {scheme} {width} group {n}"
                        self.assertEqual((w["bw"], w["radius"], w["bg"], w["ox"], w["oy"], w["mt"]), ("0px0px0px0px", "0px", "rgba(0, 0, 0, 0)", "visible", "visible", "18px"), t)
                        self.assertEqual((w["hBg"], w["hLine"], w["pad"].split()[2], w["fw"], w["fs"], w["gcSize"]), ("rgba(0, 0, 0, 0)", "1px solid", "6px", "600", "15px", "13px"), t)
                        self.assertIn("Montserrat", w["font"], t)
                        self.assertEqual((w["color"], w["gcColor"]), (f["heading"], f["muted"]), t)
                    low = contrast_ok(json.loads(p.js("JSON.stringify(%s(['#usecases-file .grp-b .gl', '#usecases-file .grp-b .gc']))" % RATIO)))
                    self.assertEqual(low, [], f"published contrast {scheme} {width}")


if __name__ == "__main__":
    unittest.main()
