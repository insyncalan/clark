"""Row 1273 (Classic): the first head of a card's Move to menu holds the card id ("Move <id> to"); Cards keeps "Move to Status".

Run: python3 dev/run_tests.py test_work_board_move_head_1273
The Cards words are pinned in test_work_board_page (Moves); here the same card is opened in the Classic layer, at 1400 and 900.
"""
import tempfile
import unittest

import test_work_board_page as wb
from test_work_board_page import setUpModule, tearDownModule  # noqa: F401  (the one shared Chrome of the board file)
from test_work_filters import click
from test_server import chrome  # noqa: F401  (the harness: this file drives Chrome, so the tier reader sees it)
from clark import page, theme
from _real_server import real_server


class MoveHead(wb.Base):
    def setUp(self):
        super().setUp()
        self.s.close()
        css = theme.css("prototype-2.0")
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.layer_theme(page.page_html(tempfile.mkdtemp()), css), seam=lambda real, which: real)
        self.addCleanup(self.s.close)

    def test_the_classic_head_holds_the_card_id_and_the_lane_head_is_unchanged(self):
        for width in (1400, 900):
            with self.subTest(width=width), wb.shared.page() as cdp:
                sid = self.visit(cdp, width=width)
                self.board(cdp, sid, "status", lane="workstream")
                a = self.id_of("Order the laptops")
                click(cdp, sid, f"[data-move='{a}']")
                self.until(cdp, sid, "!!document.querySelector('.ddmenu')", "the menu")
                heads = cdp.js("[...document.querySelectorAll('.ddmenu .mh')].map(h => h.textContent)", sid)
                self.assertEqual(heads, [f"Move {a} to", "Move to Workstream"])   # the lane head is not in capitals: code measurement, not mock
                tt = cdp.js("[...document.querySelectorAll('.ddmenu .mh')].map(h => getComputedStyle(h).textTransform)", sid)
                self.assertEqual(tt, ["uppercase", "none"], "only the card's head is drawn in capitals")

                # the capitals rule reads the tokens (a probe set to the same tokens resolves to the same px), on the card's head only
                probe = cdp.js("""(() => { const m = document.querySelector('.ddmenu'); const p = document.createElement('span'); p.style.cssText = 'font-size:var(--size-caption);letter-spacing:.08em;font-weight:var(--weight-regular)'; m.appendChild(p); const q = getComputedStyle(p); const r = [q.fontSize, q.letterSpacing, q.fontWeight]; p.remove(); return r; })()""", sid)
                head = cdp.js("(() => { const q = getComputedStyle(document.querySelector('.ddmenu .mh.caps.mh-card')); return [q.fontSize, q.letterSpacing, q.fontWeight]; })()", sid)
                self.assertEqual(head, probe, "the card's head takes the caption size, .08em tracking and the normal weight")
                self.assertNotEqual(probe[1], "normal")
                # the Move to line is a centred flex row; the tick is on the RIGHT of the word (ruling 9A), the text starts at x36 (10 + 16 icon + 10)
                row = cdp.js("""(() => { const ck = document.querySelector('.ddmenu [role="menuitem"] > .ck'); if (!ck) return null; const it = ck.parentElement; const q = getComputedStyle(it);
                  const tn = [...it.childNodes].find(n => n.nodeType === 3 && n.textContent.trim()); const rg = document.createRange(); rg.selectNodeContents(tn); const tr = rg.getBoundingClientRect(); const ir = it.getBoundingClientRect(); const kr = ck.getBoundingClientRect();
                  return {display: q.display, align: q.alignItems, tx: tr.left - ir.left, ckAfter: kr.left >= tr.right - 0.5, ckRight: ir.right - kr.right}; })()""", sid)
                self.assertIsNotNone(row, "an item of the Move to menu with a tick")
                self.assertEqual((row["display"], row["align"]), ("flex", "center"))
                self.assertTrue(row["ckAfter"], "the tick is right of the word")
                self.assertAlmostEqual(row["tx"], 36, delta=0.5, msg="the words start at x36, no tick slot before the icon")


if __name__ == "__main__":
    unittest.main()
