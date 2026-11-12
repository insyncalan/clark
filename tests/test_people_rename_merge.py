"""Row 875: renaming or merging a person carries every use case they own, with the work items and milestones, in the same step
(store.OWNER_ID_TABLES), every live one (an archived one stays as it was, as for the other tables), and leaves a use case with only a typed name alone, all in one step.

Run: python3 dev/run_tests.py test_people_rename_merge
"""
import unittest

from _demo import USER, DemoStore


class Carried(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.anna, self.ben = self.person("Anna Example"), self.person("Ben Example")
        with self.s.step("dashboard", USER) as st:
            self.uc2 = st.create("use_cases", {"project": "ABC", "title": "Badge printing", "status": "On track", "source": "demo"})
            self.uc3 = st.create("use_cases", {"project": "ABC", "title": "Gate scans", "status": "On track", "source": "demo"})
            self.uc4 = st.create("use_cases", {"project": "ABC", "title": "Typed only", "status": "On track", "source": "demo"})
        self.ucs = (self.demo.use_case, self.uc2, self.uc3)
        for uc in self.ucs:
            self.own(uc, "Anna Example")
        self.own(self.uc4, "Someone Typed")
        with self.s.step("dashboard", USER) as st:
            st.archive("use_cases", self.uc3)

    def person(self, name):
        with self.s.step("dashboard", USER) as st:
            return st.add_person(name=name, source="People list")

    def own(self, uc, name):
        with self.s.step("dashboard", USER) as st:
            st.update("use_cases", uc, {"owner": name, "owner_id": next((p["id"] for p in self.s.read("people") if p["name"] == name), None)})

    def owners(self):
        return {uc: tuple(self.s.read("use_cases", ref=uc)[k] for k in ("owner", "owner_id")) for uc in self.ucs + (self.uc4,)}

    def test_a_rename_carries_every_use_case_the_person_owns_and_not_the_typed_one(self):
        self.assertEqual(self.owners()[self.uc2], ("Anna Example", self.anna))
        with self.s.step("dashboard", USER) as st:
            st.rename_person(self.anna, "Anna Renamed")
        got = self.owners()
        for uc in self.ucs[:2]:
            self.assertEqual(got[uc], ("Anna Renamed", self.anna), uc)
        self.assertEqual(got[self.uc3], ("Anna Example", self.anna), "archived: left as it was")
        self.assertEqual(got[self.uc4], ("Someone Typed", None))

    def test_a_merge_moves_every_use_case_to_the_kept_person(self):
        with self.s.step("dashboard", USER) as st:
            st.merge_people(self.anna, self.ben)
        got = self.owners()
        for uc in self.ucs[:2]:
            self.assertEqual(got[uc], ("Ben Example", self.ben), uc)
        self.assertEqual(got[self.uc3], ("Anna Example", self.anna), "archived: left as it was")
        self.assertEqual(got[self.uc4], ("Someone Typed", None))

    def test_a_rename_is_one_step_for_every_use_case_it_carries(self):
        with self.s.step("dashboard", USER) as st:
            st.rename_person(self.anna, "Anna Renamed")
        apply_id = self.demo.last_step()
        rows = self.s.con.execute("SELECT DISTINCT item_id FROM change_log WHERE apply_id = ? AND tbl = 'use_cases' AND field = 'owner'", (apply_id,)).fetchall()
        self.assertEqual(sorted(r[0] for r in rows), sorted(self.ucs[:2]))


if __name__ == "__main__":
    unittest.main()
