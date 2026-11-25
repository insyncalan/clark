"""Row 1270: the RAID part word (The risk, The issue, ...) is drawn in Classic only; Cards draws no raid-part.

Run: python3 dev/run_tests.py test_raid_part_classic_only_1270
Fictional rows. Page checks at 1400 and 900 only.
"""
import json
import unittest

from _demo import USER
from _publish import PublishedFile
import test_glance_page as glance
from test_server import chrome

PARTS = "(() => [...document.querySelectorAll('.raid-card .raid-part')].map(e => e.textContent))()"
THEME = "!!document.getElementById('theme')"


class Parts(PublishedFile, glance.Setup):
    def put(self, rows, body_cards, kind="raid3", across=0):
        ids = []
        self.demo.plant_builtin_sections()      # the cards are drawn beside the built-in sections (row 1193)
        with self.store.step("dashboard", USER) as st:
            for table, fields in rows:
                ids.append(st.create(table, dict({"project": "ABC", "raised": "2026-10-01", "source": "demo"}, **fields)))
            ref = st.create("report_sections", {"project": "ABC", "type": kind, "title": "Fictional cards", "sort_order": 993})
            st.update("report_sections", ref, {"body": json.dumps(dict({"v": 2, "across": across} if across else {"v": 1}, cards=[dict(c, id=ids[i]) for i, c in enumerate(body_cards)]))})
        return ids

    def rows(self):
        self.put([("raid", {"type": "Risk", "description": "Tide table"}), ("raid", {"type": "Issue", "description": "Crane down"})],
                 [{"source": "client"}, {"source": "client"}])

    def seen(self, cards=False):
        self.rows()
        path = self.publish()
        if cards:      # a published file is always Classic (row 1363): take the Theme mark off, so the page draws as Cards does
            raw = path.read_bytes()
            self.assertEqual(raw.count(b'id="theme"'), 1)
            path.write_bytes(raw.replace(b'id="theme"', b'data-was="theme"'))
        out = {}
        with chrome() as cdp:
            for w in (1400, 900):
                p = self.draw(cdp, path, width=w)
                out[w] = (p.js(THEME), p.js(PARTS), p.js("document.querySelectorAll('.raid-card').length"))
        return out

    def test_classic_draws_the_part_word(self):
        for w, (classic, parts, cards) in self.seen().items():
            self.assertTrue(classic, w)
            self.assertEqual((cards, len(parts)), (2, 2), w)
            self.assertTrue(all(parts), w)


class CardsParts(Parts):
    def test_cards_draws_no_part_word(self):
        for w, (classic, parts, cards) in self.seen(cards=True).items():
            self.assertFalse(classic, w)
            self.assertEqual(cards, 2, w)
            self.assertEqual(parts, [], w)

    test_classic_draws_the_part_word = None
