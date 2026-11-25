"""Row 1270: the RAID card foot line adds impact and likelihood (risk and issue, Classic only), the card's "Also show" choices are kept and
published, and Edit has the picker, the count, Remove and the choices.

Run: python3 dev/run_tests.py test_raid_foot_pick_1270
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
from clark.section_kinds import base, raid4


class Rules:
    def visible(self, text):
        return True


class Kind(unittest.TestCase):
    def body(self, show):
        return {"v": 2, "across": 3, "cards": [{"id": "ABC-001", "source": "client", "show": show}]}

    def test_show_is_kept_in_version_two(self):
        got = raid4.check(self.body({"latest": False, "meta": True}), Rules())
        self.assertEqual(got["cards"][0]["show"], {"latest": False, "meta": True})

    def test_show_is_refused_when_not_booleans_or_unknown_keys_or_version_one(self):
        for bad in ({"latest": "no"}, {"colour": True}, "all", []):
            with self.assertRaises(base.Bad):
                raid4.check(self.body(bad), Rules())
        with self.assertRaises(base.Bad):
            raid4.check({"v": 1, "cards": [{"id": "ABC-001", "source": "client", "show": {"latest": False}}]}, Rules())


class Page(PublishedFile, glance.Setup):
    def seed(self, show):
        self.demo.plant_builtin_sections()
        with self.store.step("dashboard", USER) as st:
            a = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Fictional risk", "raised": "2026-10-01", "source": "demo", "impact": "High", "likelihood": "Medium", "owner": "Pat", "client_message": "Words.", "latest_update": "Survey booked."})
            ref = st.create("report_sections", {"project": "ABC", "type": "raid4", "title": "Fictional cards", "sort_order": 993})
            card = {"id": a, "source": "client"}
            if show is not None:
                card["show"] = show
            st.update("report_sections", ref, {"body": json.dumps({"v": 2, "across": 3, "cards": [card]})})

    def foot(self, p):
        return p.js("""(() => { const c = document.querySelector('.raid-card'); const m = c.querySelector('.raid-meta');
            return { foot: m ? m.textContent : '', latest: !!c.querySelector('.raid-latest'), bits: m ? m.querySelectorAll('.raid-bit').length : 0 }; })()""")

    def test_foot_line_has_impact_and_likelihood_at_both_widths(self):
        self.seed(None)
        path = self.publish()
        with chrome() as cdp:
            for w in (1400, 900):
                got = self.foot(self.draw(cdp, path, width=w))
                self.assertIn("impact high", got["foot"], w)
                self.assertIn("likelihood medium", got["foot"], w)
                self.assertIn("owner Pat", got["foot"], w)
                self.assertTrue(got["latest"])

    def test_the_choices_take_parts_off_the_card(self):
        self.seed({"latest": False, "rating": False})
        path = self.publish()
        with chrome() as cdp:
            got = self.foot(self.draw(cdp, path, width=1400))
        self.assertFalse(got["latest"])
        self.assertNotIn("impact", got["foot"])
        self.assertIn("owner Pat", got["foot"])

    def test_impact_without_likelihood_adds_nothing_to_the_foot_line(self):
        """The ticket: impact and likelihood show together or not at all; one of them alone is not drawn."""
        self.seed(None)
        with self.store.step("dashboard", USER) as st:
            for r in self.store.read("raid", "ABC"):
                st.update("raid", r["id"], {"likelihood": None})
        path = self.publish()
        with chrome() as cdp:
            got = self.foot(self.draw(cdp, path, width=1400))
        self.assertNotIn("impact", got["foot"])
        self.assertNotIn("likelihood", got["foot"])
        self.assertIn("owner Pat", got["foot"])

    def test_meta_off_leaves_impact_and_likelihood_only(self):
        self.seed({"meta": False})
        path = self.publish()
        with chrome() as cdp:
            got = self.foot(self.draw(cdp, path, width=900))
        self.assertNotIn("owner", got["foot"])
        self.assertIn("impact high", got["foot"])


class Edit(PageBase):
    arr = three.PageSide.arr
    set_select = three.PageSide.set_select
    wait_for = three.PageSide.wait_for

    def seed(self):
        self.demo.plant_builtin_sections()
        with self.store.step("dashboard", USER) as st:
            made = [st.create("raid", {"project": "ABC", "type": "Risk", "description": f"Fictional risk {w}", "raised": "2026-10-01", "source": "demo",
                                       "impact": "High", "likelihood": "Low", "latest_update": "Update." if i == 0 else ""}) for i, w in enumerate(["kiln", "crane", "tide"])]
            ref = st.create("report_sections", {"project": "ABC", "type": "raid4", "title": "Fictional cards", "sort_order": 999,
                                                "body": json.dumps({"v": 2, "across": 3, "cards": [{"id": made[0], "source": "client"}, {"id": made[1], "source": "client"}]})})
        return ref, made

    def stored(self, sec):
        return json.loads(next(r for r in self.store.read("report_sections", "ABC") if r["id"] == sec)["body"])

    def test_picker_count_remove_and_choices(self):
        sec, made = self.seed()
        q = f"[data-id={json.dumps(sec)}]"
        click = lambda p, sel: p.js(f"document.querySelector({json.dumps(sel)}).click()")
        with chrome() as cdp:
            cdp.FOCUS_EMULATION = False
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!document.querySelector('{q} .rce-count')", "the count is there")
            self.assertEqual(p.js(f"document.querySelector('{q} .rce-count').textContent"), "2 of 8 picked")
            click(p, f"{q} .rce-pick")
            p.until(f"!!document.querySelector('{q} input[type=search]')", "the search is there")
            self.assertEqual(p.js(f"document.querySelectorAll('{q} .rce-opts button').length"), 1, "an item already picked is not offered")
            p.js(f"(function(){{ const i = document.querySelector('{q} input[type=search]'); i.value = 'zzz'; i.dispatchEvent(new Event('input', {{bubbles: true}})); }})()")
            p.until(f"(document.querySelector('{q} .rce-none')||{{}}).textContent === 'No item matches'", "the empty state")
            p.js(f"(function(){{ const i = document.querySelector('{q} input[type=search]'); i.value = '{made[2]}'; i.dispatchEvent(new Event('input', {{bubbles: true}})); }})()")
            p.until(f"document.querySelectorAll('{q} .rce-opts button').length === 1", "search by id")
            click(p, f"{q} .rce-opts button")
            self.assertTrue(self.wait_for(lambda: len(self.stored(sec)["cards"]) == 3), "the pick is saved")
            p.until(f"document.querySelector('{q} .rce-count').textContent === '3 of 8 picked'", "count follows")
            # the second card's latest update is empty: its box is off and explained; the first card's is on
            self.assertEqual(p.js(f"[...document.querySelectorAll('{q} [data-slot=\"1\"] .rce-ck')].map(l => l.textContent)"),
                             ["Latest updateThis item has no latest update yet.", "Owner, status and date", "Impact and likelihood"])
            self.assertTrue(p.js(f"document.querySelector('{q} [data-slot=\"1\"] .rce-ck input').disabled"))
            click(p, f"{q} [data-slot='0'] .rce-ck:nth-of-type(3) input")
            self.assertTrue(self.wait_for(lambda: self.stored(sec)["cards"][0].get("show") == {"rating": False}), str(self.stored(sec)))
            click(p, f"{q} button[aria-label='Remove card 1']")
            self.assertTrue(self.wait_for(lambda: [c["id"] for c in self.stored(sec)["cards"]] == made[1:]), "Remove card 1 takes the first card out")

    def test_the_picker_refuses_hidden_and_archived_items(self):
        sec, made = self.seed()
        with self.store.step("dashboard", USER) as st:
            keep = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Fictional shown risk", "raised": "2026-10-01", "source": "demo"})
            old = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Fictional archived risk", "raised": "2026-10-01", "source": "demo"})
            hid = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Fictional hidden risk", "raised": "2026-10-01", "source": "demo"})
            st.archive("raid", old)
            st.update("raid", hid, {"client_visible": 0})
        q = f"[data-id={json.dumps(sec)}]"
        opts = f"{q} .rce-opts button"
        search = lambda p, v: p.js(f"(function(){{ const i = document.querySelector('{q} input[type=search]'); i.value = {json.dumps(v)}; i.dispatchEvent(new Event('input', {{bubbles: true}})); }})()")
        with chrome() as cdp:
            cdp.FOCUS_EMULATION = False
            p = self.visit(cdp)
            p.edit()
            for w in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                p.until(f"!!document.querySelector('{q} .rce-pick')", "the picker button")
                if not p.js(f"!!document.querySelector('{q} input[type=search]')"):
                    p.js(f"document.querySelector('{q} .rce-pick').click()")
                p.until(f"!!document.querySelector('{q} input[type=search]')", "the search is there")
                search(p, "")
                p.until(f"document.querySelectorAll('{opts}').length > 0", "the list")
                listed = p.js(f"[...document.querySelectorAll('{opts}')].map(b => b.dataset.pick)")
                self.assertIn(keep, listed, "a shown item is offered at %d" % w)
                self.assertNotIn(old, listed, "an archived item is not offered at %d" % w)
                self.assertNotIn(hid, listed, "an item hidden from the client is not offered at %d" % w)
                self.assertFalse(p.js(f"[...document.querySelectorAll('{opts}')].some(b => b.scrollWidth > b.clientWidth + 1)"), "no sideways overflow in the list at %d" % w)
                for gone in (old, hid):
                    search(p, gone)
                    p.until(f"(document.querySelector('{q} .rce-none')||{{}}).textContent === 'No item matches' && document.querySelectorAll('{opts}').length === 0", "No item matches for %s at %d" % (gone, w))
                search(p, keep)
                p.until(f"document.querySelectorAll('{opts}').length === 1", "its own ID finds a shown item")


if __name__ == "__main__":
    unittest.main()
