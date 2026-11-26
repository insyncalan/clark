"""Row 1270 (PM ruling 26-11): the card's item list refuses an item the published page would leave out (hidden from the client, archived), as the
picker does; an item a card already holds that later becomes hidden stays stored in Edit, and the published page leaves it out.

Run: python3 dev/run_tests.py test_raid_choose_publishable_1270
Fictional rows. Chrome at 1400 and 900 (the only widths checked).
"""
import json
import unittest

from _demo import USER
from _publish import PublishedFile
import test_glance_page as glance
import test_tpl_raid3 as three
from test_report_editor import Base as PageBase
from test_server import chrome


def seed(self):
    self.demo.plant_builtin_sections()
    with self.store.step("dashboard", USER) as st:
        held = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Fictional held risk", "raised": "2026-10-01", "source": "demo"})
        shown = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Fictional shown risk", "raised": "2026-10-01", "source": "demo"})
        hid = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Fictional hidden risk", "raised": "2026-10-01", "source": "demo"})
        old = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Fictional archived risk", "raised": "2026-10-01", "source": "demo"})
        st.update("raid", hid, {"client_visible": 0})
        st.archive("raid", old)
        ref = st.create("report_sections", {"project": "ABC", "type": "raid4", "title": "Fictional cards", "sort_order": 999,
                                            "body": json.dumps({"v": 2, "across": 3, "cards": [{"id": held, "source": "client"}]})})
    return ref, held, shown, hid, old


def stored(self, sec):
    return json.loads(next(r for r in self.store.read("report_sections", "ABC") if r["id"] == sec)["body"])


class Choose(PageBase):
    set_select = three.PageSide.set_select
    wait_for = three.PageSide.wait_for

    def test_choose_refuses_a_hidden_or_archived_item_and_keeps_the_card_at_both_widths(self):
        sec, held, shown, hid, old = seed(self)
        q = f"[data-id={json.dumps(sec)}]"
        with chrome() as cdp:
            cdp.FOCUS_EMULATION = False
            p = self.visit(cdp)
            p.edit()
            for w in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                for bad in (hid,):      # an archived item is not in the list at all, so the browser cannot pick it
                    for slot, keeps in ((1, held), (2, "")):
                        sel = f"{q} select[aria-label='Card {slot} item']"
                        if slot == 2 and not p.js(f"!!document.querySelector({json.dumps(sel)})"):
                            continue
                        self.set_select(p, sel, bad)
                        self.assertFalse(self.wait_for(lambda: bad in [c["id"] for c in stored(self, sec)["cards"]], 1.5), "a refused pick is not stored (%s, slot %d, %d)" % (bad, slot, w))
                        self.assertEqual(p.js(f"document.querySelector({json.dumps(sel)}).value"), keeps, "the list goes back to what the card held")
                self.assertEqual([c["id"] for c in stored(self, sec)["cards"]], [held])
                # a shown item is still chosen
                self.set_select(p, f"{q} select[aria-label='Card 2 item']", shown)
                self.assertTrue(self.wait_for(lambda: [c["id"] for c in stored(self, sec)["cards"]] == [held, shown]), "a publishable pick is saved at %d" % w)
                self.set_select(p, f"{q} select[aria-label='Card 2 item']", "")
                self.assertTrue(self.wait_for(lambda: [c["id"] for c in stored(self, sec)["cards"]] == [held]), "and can be taken out again")

    def test_a_held_item_that_becomes_hidden_stays_stored_and_selected_in_edit(self):
        sec, held, shown, hid, old = seed(self)
        with self.store.step("dashboard", USER) as st:
            st.update("raid", held, {"client_visible": 0})
        q = f"[data-id={json.dumps(sec)}]"
        with chrome() as cdp:
            cdp.FOCUS_EMULATION = False
            p = self.visit(cdp)
            p.edit()
            for w in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.until(f"!!document.querySelector('{q} select[aria-label=\"Card 1 item\"]')", "the card row")
                self.assertEqual(p.js(f"document.querySelector('{q} select[aria-label=\"Card 1 item\"]').value"), held, "the held item is still the one selected at %d" % w)
            self.set_select(p, f"{q} select[aria-label='Card 2 item']", shown)
            self.assertTrue(self.wait_for(lambda: [c["id"] for c in stored(self, sec)["cards"]] == [held, shown]), "adding another card keeps the held, now hidden, item stored")


class Published(PublishedFile, glance.Setup):
    def test_the_published_page_leaves_out_a_held_item_that_became_hidden(self):
        sec, held, shown, hid, old = seed(self)
        with self.store.step("dashboard", USER) as st:
            st.update("report_sections", sec, {"body": json.dumps({"v": 2, "across": 3, "cards": [{"id": held, "source": "client"}, {"id": shown, "source": "client"}]})})
            st.update("raid", held, {"client_visible": 0})
        self.assertEqual([c["id"] for c in stored(self, sec)["cards"]], [held, shown], "still stored")
        path = self.publish()
        with chrome() as cdp:
            for w in (1400, 900):
                got = self.draw(cdp, path, width=w).js("[...document.querySelectorAll('.raid-card')].map(c => c.dataset.card)")
                self.assertEqual(got, [shown], "the file draws the shown item only at %d" % w)


if __name__ == "__main__":
    unittest.main()
