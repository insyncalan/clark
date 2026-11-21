"""Row 1373: the Work items Configure box is the approved mock-up's box (line 61 of work-items-mockup.html), in the Classic theme layer only.

Run: python3 dev/run_tests.py test_work_items_cfg_1373
Measured in Chrome at 1400 (the priority width): box 300 wide, padding 14, radius 12, shadow (the page token --shadow), 6 below the gear, heading 15, labels 12.5,
fields 38 tall, ticks 32 tall with an 18 box. The Cards files do not carry any of it. Not checked here: 900, dark mode.
"""
import json
import re

import test_server  # noqa: F401  this file drives Chrome through the template harness (the browser tier reads this line)

import test_tpl_workitems as T
import test_work_items_mockup_1195 as M

LIST = {"mode": "all", "columns": ["id", "owner", "due", "priority"], "owner": ["Pat Demo", "Lee Demo"]}

MEASURE = ("JSON.stringify((() => { const s = %s, q = (x) => document.querySelector(s + ' ' + x), c = (e) => getComputedStyle(e), r = (e) => e.getBoundingClientRect();"
           "const box = q('.wil-cfg'), bc = c(box), g = r(q('[data-wil-gear]')), sel = q('.wil-sel select'), sc = c(sel), lab = q('.wil-sel > span'), lg = q('.wil-f legend'), ck = q('.wil-opts input[value=status]'), ckl = ck.closest('label');"
           "const top = r(box).top - g.bottom, bw = r(box).width, ckr = r(ck), selr = r(sel), rowh = r(ckl).height; ck.focus(); const kf = c(ck); const f = {w: kf.outlineWidth, o: kf.outlineOffset, c: kf.outlineColor}; sel.focus(); const sf = c(sel);"
           "return {box: {w: bw, top: top, pad: bc.paddingTop + ' ' + bc.paddingLeft, rad: bc.borderTopLeftRadius, sh: bc.boxShadow, bord: bc.borderTopWidth + ' ' + bc.borderTopColor, gap: bc.rowGap},"
           "h4: {fs: c(q('.wil-cfg h4')).fontSize, fw: c(q('.wil-cfg h4')).fontWeight, ff: c(q('.wil-cfg h4')).fontFamily}, label: {fs: c(lab).fontSize, fw: c(lab).fontWeight}, legend: {fs: c(lg).fontSize, fw: c(lg).fontWeight},"
           "sel: {w: selr.width, h: selr.height, rad: sc.borderTopLeftRadius, pad: sc.paddingLeft + ' ' + sc.paddingRight, fw: sc.fontWeight, bg: sc.backgroundColor, bord: sc.borderTopWidth + ' ' + sc.borderTopColor, focus: sf.outlineWidth + ' ' + sf.outlineOffset + ' ' + sf.outlineColor},"
           "ck: {w: ckr.width, h: ckr.height, rowh: rowh, fs: c(ckl).fontSize, fw: c(ckl).fontWeight, gap: c(ckl).columnGap, focus: f}}; })())")


class Rule(M.unittest.TestCase):
    def test_the_block_is_in_the_classic_layer_before_row_1314(self):
        self.assertIn("Row 1373", M.RULES)
        self.assertLess(M.RULES.index("/* Row 1318"), M.RULES.index("/* Row 1373"))
        self.assertLess(M.RULES.index("/* Row 1373"), M.RULES.index("/* Row 1393"))

    def test_the_cards_files_do_not_carry_it(self):
        self.assertNotIn("Row 1373", M.SHELL_CSS + M.EDIT_CSS)
        css = re.sub(r"\s+", " ", M.EDIT_CSS)
        self.assertIn("width: min(calc(var(--space-4) * 20), 100%)", css)


class Measured(M.Look):
    """The served Edit page, the Configure box open, at 1400."""

    def look(self, width):
        ref = self.add(LIST)
        with T.chrome() as cdp:
            p = self.show(cdp, width)
            sec = f'[data-id="{ref}"]'
            p.edit()
            p.until(f"!!document.querySelector('{sec} [data-wil-gear]')", "drew")
            p.js(f"document.querySelector('{sec} [data-wil-gear]').click()")
            p.until(f"!!document.querySelector('{sec} .wil-cfg:not([hidden])')", "the box")
            return json.loads(p.js(MEASURE % json.dumps(sec)))

    def test_classic_select_is_270_wide_at_1400(self):
        got = self.look(1400)
        self.assertEqual(got["sel"]["w"], 270, got)  # .wil-cfg .wil-sel select, 1400

    def test_classic_box_is_the_mockup_box_at_1400(self):
        got = self.look(1400)
        b = got["box"]
        self.assertEqual((b["w"], b["top"], b["pad"], b["rad"], b["sh"], b["gap"]),
                         (300, 6, "14px 14px", "12px", "rgba(6, 47, 58, 0.18) 0px 8px 24px 0px", "12px"), got)
        self.assertEqual(b["bord"], "1px rgb(217, 224, 239)", got)            # the mock-up line #D9E0EF
        self.assertEqual((got["h4"]["fs"], got["h4"]["fw"]), ("15px", "700"), got)
        self.assertIn("Montserrat", got["h4"]["ff"], got)
        self.assertEqual((got["label"]["fs"], got["label"]["fw"], got["legend"]["fs"], got["legend"]["fw"]), ("12.5px", "600", "12.5px", "600"), got)
        s = got["sel"]
        self.assertEqual((s["h"], s["rad"], s["pad"], s["fw"], s["bg"], s["bord"]),
                         (38, "8px", "10px 10px", "400", "rgb(255, 255, 255)", "1px rgb(217, 224, 239)"), got)
        self.assertEqual(s["focus"], "2px 1px rgb(91, 71, 216)", got)
        k = got["ck"]
        self.assertEqual((k["w"], k["h"], k["rowh"], k["fs"], k["fw"], k["gap"]), (18, 18, 32, "14px", "400", "8px"), got)
        self.assertEqual(k["focus"], {"w": "2px", "o": "1px", "c": "rgb(91, 71, 216)"}, got)


    def test_label_to_field_gap_is_4px_at_1400_and_900(self):
        # mock-up line 61: .cfg label{display:flex;flex-direction:column;gap:4px}
        for w in (1400, 900):
            ref = self.add(LIST)
            with T.chrome() as cdp:
                p = self.show(cdp, w)
                sec = f'[data-id="{ref}"]'
                p.edit()
                p.until(f"!!document.querySelector('{sec} [data-wil-gear]')", "drew")
                p.js(f"document.querySelector('{sec} [data-wil-gear]').click()")
                p.until(f"!!document.querySelector('{sec} .wil-cfg:not([hidden])')", "the box")
                got = json.loads(p.js("JSON.stringify((() => { const l = document.querySelector('%s .wil-cfg .wil-sel'), c = getComputedStyle(l), s = l.querySelector('span').getBoundingClientRect(), f = l.querySelector('select,input').getBoundingClientRect(); return {row: c.rowGap, disp: c.display, between: f.top - s.bottom}; })())" % sec))
            self.assertEqual((got["row"], got["between"]), ("4px", 4), (w, got))

    PINS = ("JSON.stringify((() => { const s = %s, q = (x) => document.querySelector(s + ' ' + x), c = (e) => getComputedStyle(e), r = (e) => e.getBoundingClientRect();"
            "const box = q('.wil-cfg'), opts = q('.wil-opts'), oc = c(opts), lab = q('.wil-sel > span'), sel = q('.wil-sel select'), lg = q('.wil-f legend');"
            "return {cols: oc.gridTemplateColumns.split(' '), disp: oc.display, rowGap: oc.rowGap, colGap: oc.columnGap, labelGap: r(sel).top - r(lab).bottom, h4m: c(q('.wil-cfg h4')).marginTop + ' ' + c(q('.wil-cfg h4')).marginBottom,"
            "legPad: c(lg).paddingBottom, right: c(box).right, parentRight: r(box.offsetParent).right - r(box).right, boxW: r(box).width}; })())")

    def test_classic_grid_gaps_label_heading_legend_and_right_edge_at_1400(self):
        """Each pin goes red when its CSS value changes: opts grid 1fr 1fr, gap 4px 10px, label 4px above select, h4 margin 0, legend padding-bottom 4, box right 0."""
        ref = self.add(LIST)
        with T.chrome() as cdp:
            p = self.show(cdp, 1400)
            sec = f'[data-id="{ref}"]'
            p.edit()
            p.until(f"!!document.querySelector('{sec} [data-wil-gear]')", "drew")
            p.js(f"document.querySelector('{sec} [data-wil-gear]').click()")
            p.until(f"!!document.querySelector('{sec} .wil-cfg:not([hidden])')", "the box")
            got = json.loads(p.js(self.PINS % json.dumps(sec)))
        self.assertEqual(got["disp"], "grid", got)
        self.assertEqual(len(got["cols"]), 2, got)                                  # two columns
        self.assertEqual(got["cols"][0], got["cols"][1], got)                       # 1fr 1fr: equal
        self.assertEqual(2 * float(got["cols"][0][:-2]) + 10, 300 - 30, got)         # and they fill the 270 inside the box (300, 14 padding, 1 line) with the 10 gap
        self.assertEqual((got["rowGap"], got["colGap"]), ("4px", "10px"), got)       # gap 4px 10px
        self.assertEqual(got["labelGap"], 4, got)                                   # label 4px above the select
        self.assertEqual(got["h4m"], "0px 0px", got)                                # h4 margin 0
        self.assertEqual(got["legPad"], "4px", got)                                 # legend padding-bottom 4
        self.assertEqual(got["right"], "0px", got)                                  # box right 0 ...
        self.assertEqual(got["parentRight"], 0, got)                                # ... and flush with its parent's right edge


class CardsMeasured(Measured):
    classic = False

    def test_classic_box_is_the_mockup_box_at_1400(self):
        self.skipTest("Classic only")

    def test_classic_select_is_270_wide_at_1400(self):
        self.skipTest("Classic only")

    def test_classic_grid_gaps_label_heading_legend_and_right_edge_at_1400(self):
        self.skipTest("Classic only")

    def test_cards_box_keeps_320_and_12_padding(self):
        got = self.look(1400)
        self.assertEqual((got["box"]["w"], got["box"]["pad"]), (320, "12px 12px"), got)
