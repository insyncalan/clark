"""Row 1270 slice 2: ONE library card 'RAID cards' (store type raid4) with a choice of three or four across and up to eight cards.
The old sections of type raid3 and raid4 (body version 1) load and publish exactly as before; only a body of version 2 carries the choice.

Run: python3 dev/run_tests.py test_raid_cards_one_1270
Fictional rows. Page checks at 1400 and 900 only.
"""
import json
import unittest

from _demo import USER
from _publish import PublishedFile
from _paths import SRC
import test_glance_page as glance
from test_server import chrome
from clark.section_kinds import base, raid3, raid4


def ids(n):
    return [f"ABC-{i:03d}" for i in range(1, n + 1)]


def v2(across, n):
    return {"v": 2, "across": across, "cards": [{"id": i, "source": "client"} for i in ids(n)]}


class Rules:
    def visible(self, text):
        return True


class Kind(unittest.TestCase):
    def test_version_two_holds_eight_cards_and_the_choice(self):
        for across in (3, 4):
            self.assertEqual(raid4.check(v2(across, 8), Rules()), v2(across, 8))

    def test_nine_cards_and_other_choices_are_refused(self):
        with self.assertRaises(base.Bad):
            raid4.check(v2(4, 9), Rules())
        for across in (2, 5, "4", None, True):
            with self.assertRaises(base.Bad):
                raid4.check({**v2(4, 2), "across": across}, Rules())
        with self.assertRaises(base.Bad):
            raid4.check({"v": 2, "cards": []}, Rules())

    def test_version_one_is_unchanged(self):
        one = {"v": 1, "cards": [{"id": i, "source": "client"} for i in ids(4)]}
        self.assertEqual(raid4.check(one, Rules()), one)
        self.assertEqual(raid3.check({"v": 1, "cards": one["cards"][:3]}, Rules()), {"v": 1, "cards": one["cards"][:3]})
        with self.assertRaises(base.Bad):
            raid4.check({"v": 1, "cards": [{"id": i, "source": "client"} for i in ids(5)]}, Rules())
        with self.assertRaises(base.Bad):
            raid3.check(v2(3, 3), Rules())

    def test_the_largest_body_fits_the_limit(self):
        self.assertGreaterEqual(raid4.LIMIT, 8 * (6 * raid3.OWN_MAX + 40))


class Page(PublishedFile, glance.Setup):
    def seed(self, across, n, kind="raid4"):
        made = []
        self.demo.plant_builtin_sections()      # the cards are drawn beside the built-in sections (row 1193)
        with self.store.step("dashboard", USER) as st:
            for i in range(n):
                made.append(st.create("raid", {"project": "ABC", "type": "Risk", "description": f"Fictional risk {i}", "raised": "2026-10-01", "source": "demo"}))
            ref = st.create("report_sections", {"project": "ABC", "type": kind, "title": "Fictional cards", "sort_order": 993})
            body = {"v": 2, "across": across, "cards": [{"id": i, "source": "client"} for i in made]} if across else {"v": 1, "cards": [{"id": i, "source": "client"} for i in made]}
            st.update("report_sections", ref, {"body": json.dumps(body)})
        return made

    def read(self, p):
        return p.js("""(() => { const ul = document.querySelector('.raid-cards'); const cs = [...ul.querySelectorAll('.raid-card')];
            return { cls: ul.className, n: cs.length, h: cs.map(c => Math.round(c.getBoundingClientRect().height)), left: [...new Set(cs.map(c => Math.round(c.getBoundingClientRect().left)))].length }; })()""")

    def test_eight_cards_three_across_same_height_in_each_row(self):
        self.seed(3, 8)
        path = self.publish()
        with chrome() as cdp:
            for w, cols in ((1400, 3), (900, 2)):
                got = self.read(self.draw(cdp, path, width=w))
                self.assertEqual(got["n"], 8, w)
                self.assertIn("raid-n3", got["cls"])
                self.assertEqual(got["left"], cols, f"columns at {w}")
                for row in range(0, 8, cols):
                    self.assertEqual(len(set(got["h"][row:row + cols])), 1, f"a row is one height at {w}: {got}")

    def test_eight_cards_four_across(self):
        self.seed(4, 8)
        path = self.publish()
        with chrome() as cdp:
            for w, dark in ((1400, False), (900, False), (1400, True), (900, True)):
                got = self.read(self.draw(cdp, path, width=w, dark=dark))
                cols = 4 if w == 1400 else 2
                self.assertEqual(got["n"], 8, w)
                self.assertIn("raid-n4", got["cls"])
                self.assertEqual(got["left"], cols, f"four across hold at 1400 and go two across at 900 (dark={dark}): {got}")
                for row in range(0, 8, cols):
                    self.assertEqual(len(set(got["h"][row:row + cols])), 1, f"a row is one height at {w}, dark={dark}: {got}")

    def test_four_across_at_1400_fit_a_whole_owner(self):
        made = []
        self.demo.plant_builtin_sections()      # the cards are drawn beside the built-in sections (row 1193)
        with self.store.step("dashboard", USER) as st:
            for i in range(4):
                made.append(st.create("raid", {"project": "ABC", "type": "Risk", "description": f"Fictional risk {i}", "raised": "2026-10-01", "source": "demo",
                                               "status": "Open", "owner": "Alexandria Montgomery", "due_date": "2026-12-01"}))
            ref = st.create("report_sections", {"project": "ABC", "type": "raid4", "title": "Fictional cards", "sort_order": 993})
            st.update("report_sections", ref, {"body": json.dumps({"v": 2, "across": 4, "cards": [{"id": i, "source": "client"} for i in made]})})
        path = self.publish()
        with chrome() as cdp:
            got = self.draw(cdp, path, width=1400).js("""[...document.querySelectorAll('.raid-card')].map(c => { const m = c.querySelector('.raid-meta');
                return { top: Math.round(c.getBoundingClientRect().top), w: Math.round(c.getBoundingClientRect().width), over: c.scrollWidth > c.clientWidth + 1 || m.scrollWidth > m.clientWidth + 1,
                         owner: m.textContent.includes('owner Alexandria Montgomery') }; })""")
        self.assertEqual(len({c["top"] for c in got}), 1, f"one line of four: {got}")
        self.assertTrue(all(c["owner"] and not c["over"] for c in got), f"a whole owner fits in each card: {got}")

    def test_an_old_body_of_version_one_publishes_four_across_and_no_more(self):
        self.seed(0, 4)
        path = self.publish()
        with chrome() as cdp:
            got = self.read(self.draw(cdp, path, width=1400))
        self.assertEqual(got["n"], 4)
        self.assertIn("raid-n4", got["cls"])
