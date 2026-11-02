"""B-16, the Work items board's columns moved and resized from their headings, in the real page: Alt+Left and Alt+Right move a
focused heading, dragging a heading moves it, the grip on a heading's right edge resizes (260 to 640 px, arrow keys, double-click
and Enter put it back), and both are remembered in this browser only, never sent to the server. The pure rules are in test_board.

Run: python3 dev/run_tests.py test_board_columns
Real DevTools input events in headless Chrome against the real server; desktop (1400) and 900 px only.
"""
import json
import unittest

from test_server import chrome
from test_work_board_page import Base
from test_work_filters import KEYS, click, where  # noqa: E402

ARROWS = {"ArrowLeft": 37, "ArrowRight": 39}


def alt_key(cdp, sid, name):
    common = {"key": name, "code": name, "windowsVirtualKeyCode": ARROWS[name], "modifiers": 1}
    cdp.call("Input.dispatchKeyEvent", {"type": "rawKeyDown", **common}, sid)
    cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", **common}, sid)


def plain_key(cdp, sid, name):
    vk = ARROWS.get(name) or KEYS[name][0]
    common = {"key": name, "code": name, "windowsVirtualKeyCode": vk}
    cdp.call("Input.dispatchKeyEvent", {"type": "rawKeyDown", **common}, sid)
    cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", **common}, sid)


class Columns(Base):
    def order(self, cdp, sid):
        return cdp.js("[...document.querySelectorAll('.lane:first-child .col')].map(c => c.dataset.col)", sid)

    def width(self, cdp, sid, col):
        return cdp.js(f"Math.round(document.querySelector(\".col[data-col='{col}']\").getBoundingClientRect().width)", sid)

    def kept(self, cdp, sid):
        return cdp.js("JSON.parse(localStorage.getItem('clark.work.v1')).ABC", sid)

    def test_alt_arrows_move_a_focused_heading_and_it_is_remembered(self):
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width=width)
                self.board(cdp, sid, "status")
                first = self.order(cdp, sid)
                self.assertGreaterEqual(len(first), 3)
                cdp.js(f"document.querySelector(\".col[data-col='{first[0]}'] .col-b\").focus()", sid)
                alt_key(cdp, sid, "ArrowRight")
                self.until(cdp, sid, f"document.querySelectorAll('.col')[1].dataset.col === {json.dumps(first[0])}", "the column moved right")
                self.assertEqual(self.order(cdp, sid)[:2], [first[1], first[0]])
                self.until(cdp, sid, f"document.activeElement.closest && document.activeElement.closest('.col') && document.activeElement.closest('.col').dataset.col === {json.dumps(first[0])}", "focus stays on the heading")
                self.assertIn("moved to place 2", cdp.js("document.body.textContent", sid))
                self.assertEqual(self.kept(cdp, sid)["order"]["status"][:2], [first[1], first[0]])
                alt_key(cdp, sid, "ArrowLeft")
                alt_key(cdp, sid, "ArrowLeft")                       # already first: says so, changes nothing
                self.until(cdp, sid, f"document.querySelectorAll('.col')[0].dataset.col === {json.dumps(first[0])}", "back to first")
                self.assertEqual(self.order(cdp, sid), first)
                alt_key(cdp, sid, "ArrowRight")
                self.reload(cdp, sid)
                self.until(cdp, sid, "!!document.querySelector('#work-board')")
                self.assertEqual(self.order(cdp, sid)[:2], [first[1], first[0]], "the order survives a reload")
                self.assertEqual(self.sent, [], "a layout choice is never sent to the server")

    def test_dragging_a_heading_moves_the_column_and_does_not_collapse_it(self):
        with chrome() as cdp:
            sid = self.visit(cdp)
            self.board(cdp, sid, "status")
            first = self.order(cdp, sid)
            x0, y0 = where(cdp, sid, f".lane .col[data-col='{first[0]}'] .col-b")
            x1, y1 = where(cdp, sid, f".lane .col[data-col='{first[1]}'] .col-b")
            mouse = lambda kind, x, y, **kw: cdp.call("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, **kw}, sid)
            mouse("mouseMoved", x0, y0)
            mouse("mousePressed", x0, y0, button="left", buttons=1, clickCount=1)
            for i in range(1, 9):
                mouse("mouseMoved", x0 + (x1 - x0 + 90) * i / 8, y0, buttons=1)
            mouse("mouseReleased", x1 + 90, y0, button="left", buttons=0, clickCount=1)
            self.until(cdp, sid, f"document.querySelectorAll('.col')[1].dataset.col === {json.dumps(first[0])}", "the heading dragged one place on")
            self.assertEqual(cdp.js("document.querySelectorAll('.col.shut').length", sid), 0, "the drop is not a click")
            self.assertEqual(self.sent, [])

    def test_the_grip_resizes_within_260_and_640_and_keys_and_double_click_work(self):
        for width in (1400, 900):
            with chrome() as cdp:
                sid = self.visit(cdp, width=width, edit=False)
                self.board(cdp, sid, "status")
                col = self.order(cdp, sid)[0]
                grip = f".col[data-col='{col}'] .col-rz"
                self.assertEqual(cdp.js(f"document.querySelector(\"{grip}\").getAttribute('role')", sid), "separator")
                self.assertEqual(cdp.js(f"document.querySelector(\"{grip}\").getAttribute('aria-valuenow')", sid), "272")
                self.assertEqual(self.width(cdp, sid, col), 272)
                x, y = where(cdp, sid, grip)
                mouse = lambda kind, px, **kw: cdp.call("Input.dispatchMouseEvent", {"type": kind, "x": px, "y": y, **kw}, sid)
                mouse("mouseMoved", x)
                mouse("mousePressed", x, button="left", buttons=1, clickCount=1)
                mouse("mouseMoved", x + 40, buttons=1)
                mouse("mouseMoved", x + 80, buttons=1)
                mouse("mouseReleased", x + 80, button="left", buttons=0, clickCount=1)
                self.until(cdp, sid, f"Math.abs(document.querySelector(\".col[data-col='{col}']\").getBoundingClientRect().width - 352) <= 2", "dragged wider")
                self.assertEqual(self.kept(cdp, sid)["widths"]["status"][col] // 10, 35)
                self.assertEqual(cdp.js("document.querySelectorAll('.col.shut').length", sid), 0)
                cdp.js(f"document.querySelector(\"{grip}\").focus()", sid)
                plain_key(cdp, sid, "ArrowRight")
                self.until(cdp, sid, f"+document.querySelector(\"{grip}\").getAttribute('aria-valuenow') >= 366", "ArrowRight widens by 16")
                for _ in range(40):
                    plain_key(cdp, sid, "ArrowRight")
                self.assertEqual(self.width(cdp, sid, col), 640, "never wider than 640")
                plain_key(cdp, sid, "Home")
                self.assertEqual(self.width(cdp, sid, col), 260, "never narrower than 260")
                plain_key(cdp, sid, "ArrowLeft")
                self.assertEqual(self.width(cdp, sid, col), 260)
                plain_key(cdp, sid, "End")
                self.reload(cdp, sid)
                self.until(cdp, sid, "!!document.querySelector('#work-board')")
                self.assertEqual(self.width(cdp, sid, col), 640, "the width survives a reload")
                plain_key(cdp, sid, "Enter") if cdp.js(f"document.querySelector(\"{grip}\").focus() || true", sid) else None
                self.until(cdp, sid, f"Math.round(document.querySelector(\".col[data-col='{col}']\").getBoundingClientRect().width) === 272", "Enter resets")
                cdp.js(f"document.querySelector(\"{grip}\").focus()", sid)
                plain_key(cdp, sid, "End")
                x, y = where(cdp, sid, grip)
                for kind, n in (("mousePressed", 1), ("mouseReleased", 1), ("mousePressed", 2), ("mouseReleased", 2)):
                    cdp.call("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, "button": "left", "buttons": 1 if kind == "mousePressed" else 0, "clickCount": n}, sid)
                self.until(cdp, sid, f"Math.round(document.querySelector(\".col[data-col='{col}']\").getBoundingClientRect().width) === 272", "a double-click resets")
                self.assertEqual(self.sent, [])

    def test_widths_and_order_belong_to_the_grouping(self):
        with chrome() as cdp:
            sid = self.visit(cdp, edit=False)
            self.board(cdp, sid, "status")
            col = self.order(cdp, sid)[0]
            cdp.js(f"document.querySelector(\".col[data-col='{col}'] .col-rz\").focus()", sid)
            plain_key(cdp, sid, "End")
            self.until(cdp, sid, f"document.querySelector(\".col[data-col='{col}'] .col-rz\").getAttribute('aria-valuenow') === '640'", "widened")
            cdp.js("(() => { const a = JSON.parse(localStorage.getItem('clark.work.v1')); a.ABC.group = 'owner'; localStorage.setItem('clark.work.v1', JSON.stringify(a)); })()", sid)
            self.reload(cdp, sid)
            self.until(cdp, sid, "!!document.querySelector('#work-board .col')", "the owner board")
            self.assertEqual(cdp.js("document.querySelector('.col').dataset.col === " + json.dumps(col), sid), False)
            self.assertEqual({self.width(cdp, sid, c) for c in self.order(cdp, sid)}, {272}, "another grouping keeps its own widths")
            self.assertEqual(self.kept(cdp, sid)["widths"]["status"][col], 640, "and the first still has its own")

    def test_a_collapsed_column_has_no_grip_and_the_heading_still_toggles(self):
        with chrome() as cdp:
            sid = self.visit(cdp, edit=False)
            self.board(cdp, sid, "status")
            col = self.order(cdp, sid)[0]
            click(cdp, sid, f".lane .col[data-col='{col}'] .col-b")
            self.until(cdp, sid, f"!!document.querySelector(\".col.shut[data-col='{col}']\")", "collapsed")
            self.assertEqual(cdp.js(f"document.querySelectorAll(\".col.shut[data-col='{col}'] .col-rz\").length", sid), 0)


if __name__ == "__main__":
    unittest.main()
