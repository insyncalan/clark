"""Row 1214: a layout change must not move content or lose template settings, in headless Chrome (1400 px and 900 px).

Run: python3 dev/run_tests.py test_layout_change_keeps_content_1214
A Key figures section (a stored setting: typed and live figures) and a rich text section are added to the fictional report. The
Key figures section is put beside another (at 1400 px by the real grip drag onto the right half of At a glance; at 900 px the page is
one column and has no half to drop on, so from its menu: Place beside the next section), then made full width again from its menu. After each step the store and the page are compared with how they were: every stored field except the layout ones (beside,
sort_order) is the same on every section, the other sections keep their order, and the Key figures section draws the same words in
the same order. The browser parts are required: they fail, never skip, without Chrome (set CLARK_CHROME to its path).
"""
import json
import unittest

from _demo import USER
from test_report_editor import Base, IDS  # noqa: E402
from test_server import chrome  # noqa: E402

LAYOUT = ("beside", "sort_order")
FIGURES = {"v": 1, "figures": [{"mode": "live", "metric": "risks"},
                               {"mode": "typed", "label": "Scanned", "value": "62%", "detail": "of the boxes", "asof": ""},
                               {"mode": "typed", "label": "Cut-over", "value": "Friday", "detail": "", "asof": ""},
                               {"mode": "live", "metric": "overdue"}]}
STORY = "<h2>Where we are</h2><p>Scanning is two thirds done.</p><ul><li>Order the labels</li><li>Book the van</li></ul>"
WORDS = ("(function(id){var c=document.querySelector('[data-id=\"' + id + '\"]').cloneNode(true);"
         "c.querySelectorAll('[data-drag], [data-options], .menu, button, .sec-tools, .tag.chg').forEach(e => e.remove());"
         "return c.textContent.replace(/\\s+/g, ' ').trim();})")


class LayoutKeepsContent(Base):
    def add(self, kind, title, body):
        with self.store.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": kind, "title": title, "sort_order": 1024 * (12 + len(self.added))})
        with self.store.step("dashboard", USER) as st:
            st.update("report_sections", ref, {"body": body})
        self.added.append(ref)
        return ref

    def rows(self):
        """Every section's stored fields but the layout ones, by id."""
        return {r["id"]: {k: v for k, v in r.items() if k not in LAYOUT} for r in self.store.read("report_sections", "ABC")}

    def words(self, p, ref):
        return p.js(f"{WORDS}({json.dumps(ref)})")

    def run_at(self, width):
        self.added = []
        figs = self.add("figures4", "Key figures", json.dumps(FIGURES))
        story = self.add("text", "Story", STORY)
        every = IDS + [figs, story]
        with chrome() as cdp:
            p = self.visit(cdp)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 6000, "deviceScaleFactor": 1, "mobile": False}, p.sid)
            p.until(f"window.innerWidth === {width}", "resized")
            p.edit()
            p.order_is(every, "the report to start with")
            rows, said, flags = self.rows(), self.words(p, figs), self.beside_flags()
            self.assertIn("Scanned", said)
            self.assertIn("Cut-over", said)
            self.assertLess(said.index("Scanned"), said.index("Cut-over"), "the figures draw in the stored order")
            story_said = self.words(p, story)
            self.assertEqual(json.loads(rows[figs]["body"]), FIGURES)

            if width > 900:                                                 # two columns: drag it onto the right half of At a glance
                target = p.rect("ABC-S-002")
                p.drag(figs, target["left"] + (target["right"] - target["left"]) * 0.75, (target["top"] + target["bottom"]) / 2)
                p.until(f"document.querySelector('[data-id=\"{figs}\"]').classList.contains('slot-right') && "
                        "document.querySelector('[data-id=\"ABC-S-002\"]').classList.contains('slot-left')", "beside At a glance")
                self.assertEqual(self.beside_flags()["ABC-S-002"], 1)
                beside = [i for i in every if i != figs]
                beside.insert(2, figs)
            else:                                                           # one column (no half to drop on): the menu's Place beside
                p.menu(figs, "beside")
                p.until(f"document.querySelector('[data-id=\"{figs}\"]').classList.contains('slot-left')", "beside the next section")
                self.assertEqual(self.beside_flags()[figs], 1)
                beside = every
            self.assertEqual(self.ids_in_store(), beside, "only the dragged section moved")
            self.assertEqual(self.rows(), rows, "beside: every stored field is as it was")
            self.assertEqual(self.words(p, figs), said, "beside: the figures draw the same words in the same order")
            self.assertEqual(self.words(p, story), story_said)
            p.order_is(beside, "beside: the page has the stored order")

            p.menu(figs, "full")
            p.until(f"document.querySelector('[data-id=\"{figs}\"]').classList.contains('slot-full')", "full width again")
            self.assertEqual(self.beside_flags(), flags, "the pairs are as they were: the dragged section is on its own again")
            self.assertEqual(self.ids_in_store(), beside, "full width moves nothing")
            self.assertEqual(self.rows(), rows, "full width: every stored field is as it was")
            self.assertEqual(self.words(p, figs), said, "full width: the figures draw the same words in the same order")
            self.assertEqual(self.words(p, story), story_said)
            p.order_is(beside, "full width: the page has the stored order")

            p.reload()
            p.edit()
            self.assertEqual(self.words(p, figs), said, "after a reload the figures draw the same words")
            self.assertEqual(self.rows(), rows)

    def test_layout_change_at_1400(self):
        self.run_at(1400)

    def test_layout_change_at_900(self):
        self.run_at(900)

    def test_right_half_made_full_width_frees_its_partner_at_900(self):
        """A real pair (This week, Next week): the right half goes full width from its menu; the left half, its old partner, is
        alone and full width too, so it does not pair with the section after it."""
        with chrome() as cdp:
            p = self.visit(cdp)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": 900, "height": 6000, "deviceScaleFactor": 1, "mobile": False}, p.sid)
            p.until("window.innerWidth === 900", "resized")
            p.edit()
            order = self.ids_in_store()
            flags = self.beside_flags()
            self.assertEqual((flags["ABC-S-004"], flags["ABC-S-005"]), (1, 0), "This week and Next week are a pair to start with")
            p.menu("ABC-S-005", "full")
            p.until("!document.querySelector('[data-id=\"ABC-S-004\"]').classList.contains('slot-left')", "the old partner is alone")
            flags = self.beside_flags()
            self.assertEqual((flags["ABC-S-004"], flags["ABC-S-005"]), (0, 0), "neither half is beside anything now")
            self.assertEqual(self.ids_in_store(), order, "nothing moved")
            for ref in ("ABC-S-004", "ABC-S-005"):
                p.until(f"document.querySelector('[data-id=\"{ref}\"]').classList.contains('slot-full')", ref + " is full width")


if __name__ == "__main__":
    unittest.main()
