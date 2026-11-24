"""Row 1270 slice 1: the RAID card in the published file has a rating edge and band, the whole description, a Latest update part for
every kind, and a foot line pinned to the bottom so foot lines line up across a row.

Run: python3 dev/run_tests.py test_raid_cards_view_1270
Fictional rows. Opened in headless Chrome at 1400 and 900 (the only widths checked).
"""
import json
import unittest

from _demo import USER
from _publish import PublishedFile
import test_glance_page as glance
from test_server import chrome

LONG = "The kiln roof may leak in the wet season and ruin the stock that is stored under it for the whole winter, which is long text"


class RaidCardsView(PublishedFile, glance.Setup):
    def seed(self):
        ids = []
        self.demo.plant_builtin_sections()      # the cards are drawn beside the built-in sections (row 1193)
        with self.store.step("dashboard", USER) as st:
            ids.append(st.create("raid", {"project": "ABC", "type": "Risk", "description": LONG, "raised": "2026-10-01", "source": "demo",
                                          "impact": "High", "likelihood": "High", "client_message": "Words for the client.", "owner": "Pat", "latest_update": "Roof survey booked."}))
            ids.append(st.create("raid", {"project": "ABC", "type": "Issue", "description": "Crane down", "raised": "2026-10-01", "source": "demo", "impact": "Low", "likelihood": "Low"}))
            ids.append(st.create("raid", {"project": "ABC", "type": "Risk", "description": "Tide table", "raised": "2026-10-01", "source": "demo"}))
            ref = st.create("report_sections", {"project": "ABC", "type": "raid3", "title": "Fictional cards", "sort_order": 993})
            st.update("report_sections", ref, {"body": json.dumps({"v": 1, "cards": [{"id": i, "source": "client"} for i in ids]})})
        return ids

    def read(self, p):
        return p.js("""(() => { const cs = [...document.querySelectorAll('.raid-card')]; return cs.map(c => { const r = c.getBoundingClientRect(), m = c.querySelector('.raid-meta'), t = c.querySelector('.raid-title');
            return { cls: c.className, top: getComputedStyle(c).borderTopWidth, rating: (c.querySelector('.raid-rating') || {}).textContent || '', label: !!c.querySelector('.raid-label'),
              latest: (c.querySelector('.raid-latest') || {}).textContent || '', h: Math.round(r.height), foot: m ? Math.round(r.bottom - m.getBoundingClientRect().bottom) : -1,
              cut: t.scrollHeight > t.clientHeight + 1 || getComputedStyle(t).textOverflow === 'ellipsis', ws: getComputedStyle(t).whiteSpace }; }); })()""")

    def test_card_look_at_both_widths(self):
        self.seed()
        path = self.publish()
        with chrome() as cdp:
            for w in (1400, 900):
                p = self.draw(cdp, path, width=w)
                cs = self.read(p)
                self.assertEqual(len(cs), 3, w)
                self.assertEqual([c["rating"] for c in cs], ["Red", "Green", "Not rated"], w)
                self.assertIn("rc-r", cs[0]["cls"]); self.assertIn("rc-g", cs[1]["cls"]); self.assertIn("rc-n", cs[2]["cls"])
                self.assertEqual({c["top"] for c in cs}, {"4px"}, "a 4 px rating edge")
                self.assertEqual([c["label"] for c in cs], [True, False, False], "Latest update only where there is text")
                self.assertEqual(cs[0]["latest"], "Roof survey booked.")
                self.assertTrue(all(c["ws"] != "nowrap" and not c["cut"] for c in cs), "the description is whole: " + str(cs))
                self.assertEqual(len({c["foot"] for c in cs[:3 if w == 1400 else 2]}), 1, "foot lines line up across a row at %d: %s" % (w, cs))
                self.assertEqual(len({c["h"] for c in cs[:3 if w == 1400 else 2]}), 1, "same height in a row at %d" % w)

    def test_action_and_decision_have_no_rating_word(self):
        self.demo.plant_builtin_sections()      # the cards are drawn beside the built-in sections (row 1193)
        with self.store.step("dashboard", USER) as st:
            a = st.create("actions", {"project": "ABC", "description": "Book the crane", "owner": "Pat", "due_date": "2026-12-01", "raised": "2026-10-01", "source": "demo", "client_message": "Words.", "latest_update": "Called them."})
            ref = st.create("report_sections", {"project": "ABC", "type": "raid3", "title": "Fictional cards", "sort_order": 993})
            st.update("report_sections", ref, {"body": json.dumps({"v": 1, "cards": [{"id": a, "source": "client"}]})})
        path = self.publish()
        with chrome() as cdp:
            cs = self.read(self.draw(cdp, path, width=1400))
        self.assertEqual(len(cs), 1)
        self.assertEqual(cs[0]["rating"], "")
        self.assertIn("rc-b", cs[0]["cls"])
        self.assertEqual(cs[0]["latest"], "Called them.")
