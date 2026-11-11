"""Row 1099: Risks and issues, Open actions and every other half-width template fit inside their card, in View and in Edit.

Run: python3 dev/run_tests.py test_half_cards_1099
The defect: in a half-width card the one-line rows of row 1021 kept their full-width columns, so the Title and Owner headers printed on
top of each other, the Id and its eye sat outside the card's edge, the owner name was cut, and View showed no title at all. A real
browser at 1400 and 900 px (900 is one column, so the card is full width there; the rows must fit that too), light and dark, with
the two sections side by side.
"""
import unittest

from test_item_one_line import Base, width, Pg
from test_server import chrome, wait

PAIR = """(() => { const a = document.querySelector('.sec[data-type=raid]'), b = document.querySelector('.sec[data-type=actions]');
  a.className = a.className.replace(/slot-\\w+/, 'slot-left'); b.className = b.className.replace(/slot-\\w+/, 'slot-right');
  a.parentNode.insertBefore(a, b); return true; })()"""
# For each half card: any row part or header word that is outside the card's content edge, any two header words overlapping,
# the owner names that are cut, and the one-line title's width.
MEASURE = r"""(() => { const out = {edge: [], head: [], owner: [], title: [], card: []};
 for (const t of ['raid', 'actions']) { const sec = document.querySelector('.sec[data-type=' + t + ']'), cb = sec.getBoundingClientRect(); out.card.push(t + ' ' + Math.round(cb.width));
  const vis = (e) => { const b = e.getBoundingClientRect(); return b.width > 1 && b.height > 1 && getComputedStyle(e).display !== 'none'; };
  for (const e of sec.querySelectorAll('.irows .wl-head > *, .irows .wl-row > *, .irows .wl-row button, .irows .wl-row .ico')) if (vis(e) && e.getBoundingClientRect().right > cb.right - 1) out.edge.push(t + ' ' + e.className + ' ' + Math.round(e.getBoundingClientRect().right - cb.right));
  const hs = [...sec.querySelectorAll('.irows .wl-head > *')].filter(vis);
  for (let i = 0; i < hs.length; i++) for (let j = i + 1; j < hs.length; j++) { const p = hs[i].getBoundingClientRect(), q = hs[j].getBoundingClientRect(); if (Math.min(p.right, q.right) - Math.max(p.left, q.left) > 0.5 && Math.min(p.bottom, q.bottom) - Math.max(p.top, q.top) > 0.5) out.head.push(t + ' ' + hs[i].textContent + '/' + hs[j].textContent); }
  for (const r of sec.querySelectorAll('.irows .wl-row')) { const nm = r.querySelector('.c-owner .nm'), tt = r.querySelector('.wl-title'), tb = tt.getBoundingClientRect();
   if (nm && vis(nm) && nm.scrollWidth > nm.clientWidth + 1) out.owner.push(t + ' ' + nm.textContent);
   out.title.push(t + ' ' + Math.round(tb.width) + ' ' + r.getBoundingClientRect().height); } }
 out.side = document.documentElement.scrollWidth - document.documentElement.clientWidth; return out; })()"""


class HalfCards(Base):
    def test_half_width_cards_fit_in_view_and_edit_light_and_dark(self):
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.served().port)
            p.ready()
            p.js(PAIR)
            for mode in ("view", "edit"):
                if mode == "edit":
                    p.edit()
                for w in (1400, 900):
                    width(cdp, p.sid, w)
                    for dark in (False, True):
                        p.js(f"document.documentElement.setAttribute('data-theme', '{'dark' if dark else 'light'}')")
                        got = p.js(MEASURE)
                        where = f"{mode} {w} {'dark' if dark else 'light'}"
                        self.assertEqual(got["edge"], [], f"{where}: parts outside the card edge")
                        self.assertEqual(got["head"], [], f"{where}: header words overlap")
                        self.assertEqual(got["owner"], [], f"{where}: owner names cut")
                        self.assertLessEqual(got["side"], 0, f"{where}: page scrolls sideways")
                        for t in got["title"]:
                            self.assertGreaterEqual(int(t.split()[1]), 90, f"{where}: title column too narrow: {t}")

    def test_every_section_as_a_half_keeps_its_parts_inside_its_card_in_view_and_edit(self):
        every = r"""(() => { [...document.querySelectorAll('.secs > .sec')].forEach((e, i) => { e.className = e.className.replace(/slot-\\w+/, i % 2 ? 'slot-right' : 'slot-left'); });
          const bad = [], clipped = (e, sec) => { for (let a = e.parentElement; a && a !== sec; a = a.parentElement) if (getComputedStyle(a).overflowX !== 'visible') return true; return false; };
          for (const sec of document.querySelectorAll('.secs > .sec')) { const cb = sec.getBoundingClientRect();
           for (const e of sec.querySelectorAll('*')) { const b = e.getBoundingClientRect(); if (b.width > 1 && b.height > 1 && getComputedStyle(e).display !== 'none' && !e.closest('.sec-ctl, [data-tip], .toast') && b.right > cb.right + 1 && getComputedStyle(e).position !== 'absolute' && !clipped(e, sec)) bad.push(sec.dataset.type + ' ' + e.tagName + '.' + e.className + ' ' + Math.round(b.right - cb.right)); } }
          return bad.slice(0, 12); })()"""
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.served().port)
            p.ready()
            width(cdp, p.sid, 1400)
            for mode in ("view", "edit"):
                if mode == "edit":
                    p.edit()
                self.assertEqual(p.js(every), [], f"{mode}: parts outside their half card")

    def test_view_shows_the_description_on_one_line_where_the_title_is_and_a_click_opens_the_peek(self):
        titles = "[...document.querySelectorAll('.sec[data-type=%s] .irows .wl-title')].map(e => e.textContent.trim())"
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.served().port)
            p.ready()
            p.js(PAIR)
            for w in (1400, 900):
                width(cdp, p.sid, w)
                actions = p.js(titles % "actions")
                self.assertIn("Agree the cut-over plan", actions, f"{w}: the description, not the client wording")
                self.assertNotIn("Cut-over plan to be agreed", actions)
                self.assertIn("Supplier may deliver late", p.js(titles % "raid"))
                self.assertIn("title", p.js("document.querySelector('.sec[data-type=actions] .irows .wl-title').getAttributeNames()"))
            p.js("[...document.querySelectorAll('.sec[data-type=actions] .wl-row')].find(r => r.textContent.includes('Agree the cut-over')).click()")
            self.assertTrue(wait(lambda: p.js("location.hash.includes('item=')")), "a click opens the peek")


if __name__ == "__main__":
    unittest.main()
