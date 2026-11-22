"""Row 1393: the Classic Work items table as the prototype draws it (title weight, row line, header, column widths, due words, status tile text, hover, eye).

Run: python3 dev/run_tests.py test_work_items_table_1393
One test per ticket row, each measured in Chrome at 1400 in the light Classic look; the colour rows also check the dark look against the Theme token.
Cards (shell.css) must not carry any of it. Widths at 900 are not part of this row.
"""
import re
import time
import unittest

from clark import page, theme
from _real_server import real_server
from test_server import chrome
from test_work_board_page import Base
from _paths import ROOT

RULES = ((ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8") + (ROOT / "src" / "clark" / "themes" / "prototype-2.0" / "rules-2.css").read_text(encoding="utf-8"))
SHELL = (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
MARK = RULES.index("/* Row 1393")
BLOCK = RULES[MARK:RULES.index("/* Row 1314")]

TOKEN = ("(() => { const t = (v, p) => { const e = document.createElement('i'); e.style[p] = 'var(' + v + ')'; document.body.append(e);"
         " const c = getComputedStyle(e)[p]; e.remove(); return c; }; return t; })()")


class Rules(unittest.TestCase):
    def test_the_block_comes_before_row_1314_which_stays_the_last_row_block(self):
        self.assertEqual(RULES.count("/* Row 1393"), 1)
        self.assertLess(MARK, RULES.index("/* Row 1314"))
        self.assertEqual(re.findall(r"/\* Row \d+", RULES)[-1], "/* Row 1314")

    def test_only_tokens_and_no_important(self):
        body = re.sub(r"/\*.*?\*/", "", BLOCK, flags=re.S)
        self.assertNotRegex(body, r"#[0-9a-fA-F]{3,6}\b")
        self.assertNotIn("!important", body)

    def test_cards_stylesheet_has_none_of_it(self):
        self.assertNotIn("Row 1393", SHELL)
        self.assertNotIn("table.items .t {", SHELL.replace("table.items tr.done .t {", ""))


class Browser(Base):
    """The Classic Work items page in Chrome (the Classic theme layered), 1400 wide, grouped table."""

    def setUp(self):
        super().setUp()
        self.s.close()
        css = theme.css("prototype-2.0")
        self.s = real_server(self.store.path, self.store.data_for,
                             page_html=lambda: page.layer_theme(page.page_html(__import__("tempfile").mkdtemp()), css), seam=lambda real, which: real)
        self.addCleanup(self.s.close)

    def look(self, mode="light"):
        cm = chrome()
        cdp = cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)
        sid = self.visit(cdp, width=1400)
        cdp.js("document.documentElement.dataset.theme = %r" % mode, sid)
        time.sleep(0.5)
        return cdp, sid

    def style(self, cdp, sid, sel, props, nth=0):
        return cdp.js("(() => { const e = document.querySelectorAll(%r)[%d], s = getComputedStyle(e); return %s; })()"
                      % (sel, nth, "{" + ",".join("%s: s.%s" % (p, p) for p in props) + "}"), sid)

    def token(self, cdp, sid, var, prop):
        return cdp.js("(() => { const e = document.createElement('i'); e.style.%s = 'var(%s)'; document.body.append(e); const c = getComputedStyle(e).%s; e.remove(); return c; })()" % (prop, var, prop), sid)

    # spec row 1: item title 500, heading colour
    def test_row1_item_title_is_weight_500_in_the_heading_colour(self):
        cdp, sid = self.look()
        got = self.style(cdp, sid, "#work table.items td.c-item .t", ["fontWeight", "color"])
        self.assertEqual(got, {"fontWeight": "500", "color": "rgb(15, 26, 46)"}, got)
        cdp.js("document.documentElement.dataset.theme = 'dark'", sid)
        time.sleep(0.4)
        self.assertEqual(self.style(cdp, sid, "#work table.items td.c-item .t", ["color"])["color"], self.token(cdp, sid, "--heading", "color"))

    # spec row 2: row divider 1px #D9E0EF
    def test_row2_row_divider_is_1px_grey_200(self):
        cdp, sid = self.look()   # a row after the first of its group: main draws no line over the first (row 1324)
        got = self.style(cdp, sid, "#work table.items tbody tr[data-id]:not(:first-child) td", ["borderTopWidth", "borderTopColor"], nth=1)
        self.assertEqual(got, {"borderTopWidth": "1px", "borderTopColor": "rgb(217, 224, 239)"}, got)
        cdp.js("document.documentElement.dataset.theme = 'dark'", sid)
        time.sleep(0.4)
        self.assertEqual(self.style(cdp, sid, "#work table.items tbody tr[data-id]:not(:first-child) td", ["borderTopColor"], nth=1)["borderTopColor"], self.token(cdp, sid, "--grey-200", "color"))

    # spec row 3: column header 13px, 500, padding 9px 10px
    def test_row3_column_header_is_13px_500_with_9px_above_and_below(self):
        cdp, sid = self.look()
        got = self.style(cdp, sid, "#work table.items tr.colh th.c-owner", ["fontSize", "fontWeight", "paddingTop", "paddingBottom", "paddingLeft", "paddingRight"])
        self.assertEqual(got, {"fontSize": "13px", "fontWeight": "500", "paddingTop": "9px", "paddingBottom": "9px", "paddingLeft": "10px", "paddingRight": "10px"}, got)

    # spec row 4: status / owner / due / priority columns 72 / 190 / 176 / 104
    def test_row4_columns_are_72_190_176_104_at_1400(self):
        cdp, sid = self.look()
        got = cdp.js("(() => { const o = {}; ['status', 'owner', 'due', 'prio'].forEach(k => { o[k] = document.querySelector('#work table.items tr.colh th.c-' + k).getBoundingClientRect().width; }); return o; })()", sid)
        self.assertEqual(got, {"status": 72, "owner": 190, "due": 176, "prio": 104}, got)

    # the Status column at 72 px: nothing in a Status cell is cut off
    def test_row4_status_cells_are_not_clipped_at_72(self):
        cdp, sid = self.look()
        got = cdp.js("(() => { const o = []; document.querySelectorAll('#work table.items tbody td.c-status').forEach(td => { const w = Math.max(td.scrollWidth, ...[...td.querySelectorAll('*')].map(e => e.scrollWidth)); o.push([td.clientWidth, w, td.textContent.trim()]); }); return o; })()", sid)
        head = cdp.js("(() => { const th = document.querySelector('#work table.items tr.colh th.c-status'); return [th.clientWidth, th.scrollWidth, th.textContent.trim()]; })()", sid)
        self.assertLessEqual(head[1], head[0], head)
        for cw, sw, txt in got:
            self.assertLessEqual(sw, cw, (txt, cw, sw))

    # spec row 5: due words 13px, late 600
    def test_row5_due_words_are_13px_and_the_late_one_is_600(self):
        cdp, sid = self.look()
        got = self.style(cdp, sid, "#work table.items td.c-due .due-l:not(.late)", ["fontSize", "fontWeight"])
        self.assertEqual(got, {"fontSize": "13px", "fontWeight": "400"}, got)
        late = self.style(cdp, sid, "#work table.items td.c-due .due-l.late", ["fontSize", "fontWeight", "color"])
        self.assertEqual(late, {"fontSize": "13px", "fontWeight": "600", "color": "rgb(163, 48, 31)"}, late)

    # spec row 6: status tile text, red #A3301F, green #006B5E (the fills stay)
    def test_row6_status_tile_text_is_the_red_and_green_status_tokens(self):
        cdp, sid = self.look()
        red = self.style(cdp, sid, "#work table.items .ico.r", ["color", "backgroundColor"])
        green = self.style(cdp, sid, "#work table.items .ico.g", ["color", "backgroundColor"])
        self.assertEqual(red, {"color": "rgb(163, 48, 31)", "backgroundColor": "rgb(251, 236, 234)"}, red)
        self.assertEqual(green, {"color": "rgb(0, 107, 94)", "backgroundColor": "rgb(224, 243, 239)"}, green)
        cdp.js("document.documentElement.dataset.theme = 'dark'", sid)
        time.sleep(0.4)
        self.assertEqual(self.style(cdp, sid, "#work table.items .ico.r", ["color"])["color"], self.token(cdp, sid, "--status-red-text", "color"))
        self.assertEqual(self.style(cdp, sid, "#work table.items .ico.g", ["color"])["color"], self.token(cdp, sid, "--status-green-text", "color"))

    # spec row 7: row hover #F3F5FB
    def test_row7_row_hover_is_f3f5fb(self):
        for mode, want in (("light", "rgb(243, 245, 251)"), ("dark", None)):
            with self.subTest(mode=mode):
                cdp, sid = self.look(mode)
                r = cdp.js("(() => { const b = document.querySelector('#work table.items tbody tr[data-id]').getBoundingClientRect(); return [b.left + b.width / 2, b.top + b.height / 2]; })()", sid)
                cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": r[0], "y": r[1]}, sid)
                time.sleep(0.4)
                got = self.style(cdp, sid, "#work table.items tbody tr[data-id]", ["backgroundColor"])["backgroundColor"]
                self.assertEqual(got, want or self.token(cdp, sid, "--band-bg", "backgroundColor"), got)

    # spec row 8: eye button 30 x 30
    def test_row8_eye_button_is_30_by_30(self):
        cdp, sid = self.look()
        got = cdp.js("(() => { const b = document.querySelector('#work table.items .weye').getBoundingClientRect(); return [b.width, b.height]; })()", sid)
        self.assertEqual(got, [30, 30], got)


if __name__ == "__main__":
    unittest.main()


class Clip900(Browser):
    """Row 1393, measured widths at 900 and the clip check on every named column (1400 and 900)."""

    def look_at(self, width):
        cm = chrome()
        cdp = cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)
        sid = self.visit(cdp, width=width)
        time.sleep(0.5)
        return cdp, sid

    def widths(self, cdp, sid):
        return cdp.js("(() => { const o = {}; ['status', 'owner', 'due', 'prio'].forEach(k => { o[k] = document.querySelector('#work table.items tr.colh th.c-' + k).getBoundingClientRect().width; }); return o; })()", sid)

    def clipped(self, cdp, sid):
        return cdp.js("(() => { const o = []; ['status', 'owner', 'due', 'prio'].forEach(k => { document.querySelectorAll('#work table.items th.c-' + k + ', #work table.items td.c-' + k).forEach(c => {"
                      " const w = Math.max(c.scrollWidth, ...[...c.querySelectorAll('*')].map(e => e.scrollWidth)); if (w > c.clientWidth) o.push([k, c.clientWidth, w, c.textContent.trim()]); }); }); return o; })()", sid)

    def test_row4_columns_at_900_keep_the_shared_widths_not_the_row_1393_ones(self):
        cdp, sid = self.look_at(900)
        got = self.widths(cdp, sid)
        self.assertEqual(got, {"status": 76, "owner": 130, "due": 139, "prio": 121}, got)

    def test_row4_no_named_cell_is_clipped_at_1400(self):
        cdp, sid = self.look_at(1400)
        self.assertEqual(self.clipped(cdp, sid), [])

    def test_row4_no_named_cell_is_clipped_at_900(self):
        cdp, sid = self.look_at(900)
        self.assertEqual(self.clipped(cdp, sid), [])
